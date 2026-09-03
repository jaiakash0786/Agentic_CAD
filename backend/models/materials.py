"""
Material Library - Built-in engineering material database.

Each material contains the mechanical properties needed for FEA:
  - yield_strength: used to calculate safety factor
  - youngs_modulus: used in stiffness matrix (K)
  - poisson_ratio: used in material constitutive matrix (D)
  - density: used to calculate mass
"""
from pydantic import BaseModel, Field


class Material(BaseModel):
    """Engineering material with mechanical properties."""
    name: str = Field(..., description="Material identifier")
    display_name: str = Field(..., description="Human-readable name")
    yield_strength_mpa: float = Field(..., gt=0, description="Yield strength in MPa")
    ultimate_strength_mpa: float = Field(..., gt=0, description="Ultimate tensile strength in MPa")
    youngs_modulus_mpa: float = Field(..., gt=0, description="Young's modulus (E) in MPa")
    poisson_ratio: float = Field(..., gt=0, lt=0.5, description="Poisson's ratio (ν)")
    density_kg_m3: float = Field(..., gt=0, description="Density in kg/m³")
    density_g_mm3: float = Field(default=0, description="Density in g/mm³ (auto-calculated)")

    def model_post_init(self, __context):
        """Auto-calculate density in g/mm³ for FEA (which uses mm)."""
        if self.density_g_mm3 == 0:
            self.density_g_mm3 = self.density_kg_m3 / 1e6


class MaterialLibrary:
    """
    Built-in library of common engineering materials.

    Usage:
        mat = MaterialLibrary.get("aluminum_6061_t6")
        print(mat.yield_strength_mpa)  # 276.0
    """

    _materials: dict[str, Material] = {
        "aluminum_6061_t6": Material(
            name="aluminum_6061_t6",
            display_name="Aluminum 6061-T6",
            yield_strength_mpa=276.0,
            ultimate_strength_mpa=310.0,
            youngs_modulus_mpa=68900.0,
            poisson_ratio=0.33,
            density_kg_m3=2710.0,
        ),
        "aluminum_7075_t6": Material(
            name="aluminum_7075_t6",
            display_name="Aluminum 7075-T6",
            yield_strength_mpa=503.0,
            ultimate_strength_mpa=572.0,
            youngs_modulus_mpa=71700.0,
            poisson_ratio=0.33,
            density_kg_m3=2810.0,
        ),
        "steel_aisi_304": Material(
            name="steel_aisi_304",
            display_name="Stainless Steel AISI 304",
            yield_strength_mpa=215.0,
            ultimate_strength_mpa=505.0,
            youngs_modulus_mpa=193000.0,
            poisson_ratio=0.29,
            density_kg_m3=8000.0,
        ),
        "steel_aisi_1045": Material(
            name="steel_aisi_1045",
            display_name="Carbon Steel AISI 1045",
            yield_strength_mpa=530.0,
            ultimate_strength_mpa=625.0,
            youngs_modulus_mpa=206000.0,
            poisson_ratio=0.29,
            density_kg_m3=7850.0,
        ),
        "titanium_ti6al4v": Material(
            name="titanium_ti6al4v",
            display_name="Titanium Ti-6Al-4V",
            yield_strength_mpa=880.0,
            ultimate_strength_mpa=950.0,
            youngs_modulus_mpa=113800.0,
            poisson_ratio=0.342,
            density_kg_m3=4430.0,
        ),
        "copper_c11000": Material(
            name="copper_c11000",
            display_name="Copper C11000 (Pure)",
            yield_strength_mpa=69.0,
            ultimate_strength_mpa=220.0,
            youngs_modulus_mpa=117000.0,
            poisson_ratio=0.34,
            density_kg_m3=8960.0,
        ),
    }

    @classmethod
    def get(cls, name: str) -> Material:
        """Get a material by name. Raises KeyError if not found."""
        key = name.lower().replace(" ", "_").replace("-", "_")
        if key not in cls._materials:
            available = ", ".join(cls._materials.keys())
            raise KeyError(
                f"Material '{name}' not found. Available: {available}"
            )
        return cls._materials[key]

    @classmethod
    def list_all(cls) -> list[Material]:
        """Return all available materials."""
        return list(cls._materials.values())

    @classmethod
    def list_names(cls) -> list[str]:
        """Return all material identifiers."""
        return list(cls._materials.keys())

    @classmethod
    def exists(cls, name: str) -> bool:
        """Check if a material exists in the library."""
        key = name.lower().replace(" ", "_").replace("-", "_")
        return key in cls._materials
