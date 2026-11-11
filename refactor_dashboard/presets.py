"""Instruction presets offered in the dashboard."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    instruction: str


PRESETS: list[Preset] = [
    Preset(
        id="simplify",
        label="Simplify",
        instruction=(
            "Simplify this code: remove duplication and dead code, flatten deep nesting, "
            "use clear names, and prefer idiomatic constructs. Keep the behaviour exactly the same."
        ),
    ),
    Preset(
        id="optimize",
        label="Optimize performance",
        instruction=(
            "Optimize this code for performance: choose better algorithms and data structures, "
            "and avoid repeated work and unnecessary allocations. Keep the behaviour and public "
            "interface the same."
        ),
    ),
    Preset(
        id="types_docs",
        label="Add types/docs",
        instruction=(
            "Add type annotations and concise docstrings or doc comments to this code, following "
            "the conventions of the language. Do not change its behaviour."
        ),
    ),
    Preset(id="custom", label="Custom", instruction=""),
]

PRESETS_BY_ID = {p.id: p for p in PRESETS}
DEFAULT_PRESET_ID = "simplify"


def presets_payload() -> dict:
    return {"presets": [asdict(p) for p in PRESETS], "default": DEFAULT_PRESET_ID}


def resolve_instruction(preset: str | None, instruction: str | None, fallback: str) -> str:
    """Choose the instruction text for a request.

    An explicit instruction wins; otherwise the named preset's text is used; otherwise ``fallback``.
    """
    if instruction and instruction.strip():
        return instruction.strip()
    chosen = PRESETS_BY_ID.get(preset or "")
    if chosen and chosen.instruction:
        return chosen.instruction
    return fallback
