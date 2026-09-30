"""
Pipeline State Manager.

Tracks the current state of every running pipeline instance and
broadcasts real-time updates to connected WebSocket clients.

Each pipeline has:
    - A unique pipeline_id (e.g. "a1b2c3d4")
    - A PipelineState Pydantic model updated at each stage
    - A set of connected WebSocket clients to broadcast to

Thread-safety: updates are serialized via asyncio; no threading needed
since FastAPI runs in a single event loop.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from models.results import PipelineState, PipelineStage, DesignHistory

logger = logging.getLogger(__name__)


class PipelineStateManager:
    """
    In-memory store for all active pipeline states.

    Usage:
        manager = PipelineStateManager()
        await manager.create(pipeline_id)
        await manager.update(pipeline_id, stage=PipelineStage.MESHING, message="Meshing...")
        state = manager.get(pipeline_id)
    """

    def __init__(self):
        # pipeline_id → PipelineState
        self._states: dict[str, PipelineState] = {}
        # pipeline_id → set of WebSocket send callables
        self._ws_clients: dict[str, set] = {}

    # ─── Lifecycle ───────────────────────────────────────────────────────────

    def create(self, pipeline_id: str) -> PipelineState:
        """Create a new pipeline state entry."""
        state = PipelineState(
            pipeline_id=pipeline_id,
            stage=PipelineStage.IDLE,
            progress_percent=0.0,
            message="Pipeline initialised",
        )
        self._states[pipeline_id] = state
        self._ws_clients[pipeline_id] = set()
        logger.info("[StateManager] Created pipeline: %s", pipeline_id)
        return state

    def get(self, pipeline_id: str) -> PipelineState | None:
        """Return the current state for a pipeline."""
        return self._states.get(pipeline_id)

    def get_all(self) -> dict[str, PipelineState]:
        """Return all stored pipeline states."""
        return dict(self._states)

    def delete(self, pipeline_id: str) -> None:
        """Remove a pipeline state from memory."""
        self._states.pop(pipeline_id, None)
        self._ws_clients.pop(pipeline_id, None)

    # ─── State Updates ───────────────────────────────────────────────────────

    async def update(
        self,
        pipeline_id: str,
        *,
        stage: PipelineStage | None = None,
        progress_percent: float | None = None,
        message: str | None = None,
        # File paths
        cad_step_path: str | None = None,
        cad_stl_path: str | None = None,
        mesh_path: str | None = None,
        report_path: str | None = None,
        # Error
        error: str | None = None,
        # Design history
        design_history: DesignHistory | None = None,
    ) -> PipelineState:
        """
        Update pipeline state fields and broadcast to WebSocket clients.
        """
        if pipeline_id not in self._states:
            self.create(pipeline_id)

        state = self._states[pipeline_id]

        if stage is not None:
            state.stage = stage
        if progress_percent is not None:
            state.progress_percent = round(progress_percent, 1)
        if message is not None:
            state.message = message
        if cad_step_path is not None:
            state.cad_step_path = cad_step_path
        if cad_stl_path is not None:
            state.cad_stl_path = cad_stl_path
        if mesh_path is not None:
            state.mesh_path = mesh_path
        if report_path is not None:
            state.report_path = report_path
        if error is not None:
            state.error = error
        if design_history is not None:
            state.design_history = design_history

        state.updated_at = datetime.now()

        logger.info(
            "[%s] Stage=%-20s  %5.1f%%  %s",
            pipeline_id, state.stage.value, state.progress_percent, state.message,
        )

        # Broadcast to connected WebSocket clients
        await self._broadcast(pipeline_id, state)
        return state

    def update_sync(
        self,
        pipeline_id: str,
        stage: PipelineStage | None = None,
        progress_percent: float | None = None,
        message: str | None = None,
        **kwargs: Any,
    ) -> PipelineState:
        """
        Synchronous state update (no broadcast) — for use inside
        run_in_executor threads where asyncio is not available.
        """
        if pipeline_id not in self._states:
            self.create(pipeline_id)

        state = self._states[pipeline_id]

        if stage is not None:
            state.stage = stage
        if progress_percent is not None:
            state.progress_percent = round(progress_percent, 1)
        if message is not None:
            state.message = message

        for key, val in kwargs.items():
            if hasattr(state, key) and val is not None:
                setattr(state, key, val)

        state.updated_at = datetime.now()

        logger.info(
            "[%s] Stage=%-20s  %5.1f%%  %s",
            pipeline_id, state.stage.value, state.progress_percent, state.message,
        )
        return state

    # ─── WebSocket ───────────────────────────────────────────────────────────

    def register_ws(self, pipeline_id: str, send_fn) -> None:
        """Register a WebSocket send function for a pipeline."""
        if pipeline_id not in self._ws_clients:
            self._ws_clients[pipeline_id] = set()
        self._ws_clients[pipeline_id].add(send_fn)
        logger.debug("[StateManager] WS client registered for %s", pipeline_id)

    def unregister_ws(self, pipeline_id: str, send_fn) -> None:
        """Unregister a WebSocket send function."""
        if pipeline_id in self._ws_clients:
            self._ws_clients[pipeline_id].discard(send_fn)

    async def _broadcast(self, pipeline_id: str, state: PipelineState) -> None:
        """Send JSON state to all registered WebSocket clients."""
        clients = self._ws_clients.get(pipeline_id, set())
        if not clients:
            return

        payload = json.dumps({
            "pipeline_id": state.pipeline_id,
            "stage": state.stage.value,
            "progress_percent": state.progress_percent,
            "message": state.message,
            "cad_step_path": state.cad_step_path,
            "cad_stl_path": state.cad_stl_path,
            "mesh_path": state.mesh_path,
            "report_path": state.report_path,
            "error": state.error,
            "updated_at": state.updated_at.isoformat(),
        })

        dead_clients = set()
        for send_fn in list(clients):
            try:
                await send_fn(payload)
            except Exception as e:
                logger.warning("[StateManager] WS send failed: %s", e)
                dead_clients.add(send_fn)

        # Clean up dead connections
        for dc in dead_clients:
            clients.discard(dc)


# ─── Global singleton ────────────────────────────────────────────────────────
# Imported by main.py and pipeline.py

pipeline_state_manager = PipelineStateManager()
