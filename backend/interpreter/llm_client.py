"""
LLM Client — Groq API wrapper for the AI Requirement Interpreter.

This module provides the bridge between natural language and structured engineering
specifications. It uses Groq's API with Llama 3 to force structured JSON output
matching our DesignSpecification schema.

Architecture:
    Natural Language Requirement
            ↓
    Groq API (Llama 3.3 70B)
            ↓
    Structured JSON
            ↓
    Schema Validation
            ↓
    DesignSpecification

Note: groq==0.25.0 only has the sync Groq client. We offload the blocking
call to asyncio's default thread-pool executor so the uvicorn event loop
is never blocked.
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL


class LLMClient:
    """
    Wrapper around Groq API for structured engineering parameter extraction.

    The key design principle: the LLM NEVER directly controls CAD/FEA.
    It only produces JSON, which is validated before reaching any engine.

        LLM → JSON → Validation → Engineering Engine
    """

    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY not set. Please add it to backend/.env"
            )
        # Sync client — calls are offloaded to run_in_executor so they
        # never block the FastAPI/uvicorn event loop.
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL

    async def extract_parameters(
        self, requirement: str, system_prompt: str
    ) -> dict:
        """
        Send a natural language requirement to the LLM and extract
        structured engineering parameters as JSON.

        Args:
            requirement: Natural language engineering requirement
            system_prompt: Instruction prompt for the LLM

        Returns:
            Parsed JSON dictionary of engineering parameters
        """
        loop = asyncio.get_event_loop()

        def _call_llm():
            content = ""
            try:
                # Try with JSON mode first
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": requirement},
                        ],
                        temperature=0,
                        max_tokens=4096,
                        response_format={"type": "json_object"},
                    )
                except Exception:
                    # Fallback: some models don't support response_format
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {
                                "role": "system",
                                "content": system_prompt + "\n\nIMPORTANT: Output ONLY valid JSON. No markdown, no explanations, no ```json blocks. No thinking tags.",
                            },
                            {"role": "user", "content": requirement},
                        ],
                        temperature=0,
                        max_tokens=4096,
                    )

                content = response.choices[0].message.content.strip()

                # Strip <think>...</think> blocks output by reasoning models
                # (e.g. qwen3.8-27b runs in thinking mode by default)
                import re
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

                # Strip markdown code fences if present
                if content.startswith("```"):
                    lines = content.split("\n")
                    lines = [l for l in lines if not l.strip().startswith("```")]
                    content = "\n".join(lines).strip()

                # If model returned empty after stripping, something went wrong
                if not content:
                    raise ValueError("LLM returned empty content after stripping thinking tags")

                return json.loads(content)

            except json.JSONDecodeError as e:
                raise ValueError(f"LLM returned invalid JSON: {e}\nRaw content: {content[:500]}")
            except Exception as e:
                raise RuntimeError(f"LLM API call failed: {e}")

        # Run the synchronous Groq call in a thread pool so the event loop stays free
        return await loop.run_in_executor(None, _call_llm)

    async def ask_clarification(
        self, requirement: str, missing_fields: list[str]
    ) -> str:
        """
        Generate a human-readable clarification request for missing parameters.

        Args:
            requirement: Original requirement text
            missing_fields: List of missing field names

        Returns:
            Formatted clarification message for the engineer
        """
        loop = asyncio.get_event_loop()

        def _call_llm():
            prompt = f"""The engineer provided this requirement:
"{requirement}"

The following engineering parameters could not be determined:
{', '.join(missing_fields)}

Generate a clear, professional message asking the engineer to provide
the missing information. Be specific about what each parameter means
and give an example value for each."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful engineering assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            return response.choices[0].message.content

        return await loop.run_in_executor(None, _call_llm)
