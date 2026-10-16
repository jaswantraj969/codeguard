"""Built-in library names that always count as declared (SRS addendum §2.3)."""

import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

DATA_FILE = "known_library_functions.json"


@dataclass(frozen=True, slots=True)
class LibraryNames:
    functions: frozenset[str]
    constants: frozenset[str]

    def __contains__(self, name: object) -> bool:
        return name in self.functions or name in self.constants


def data_dir() -> Path:
    """backend/data, overridable with CODEGUARD_DATA_DIR."""
    override = os.environ.get("CODEGUARD_DATA_DIR")
    return Path(override) if override else Path(__file__).resolve().parents[2] / "data"


@cache
def load_library() -> LibraryNames:
    raw = json.loads((data_dir() / DATA_FILE).read_text(encoding="utf-8"))
    return LibraryNames(
        functions=frozenset(name for names in raw["functions"].values() for name in names),
        constants=frozenset(name for names in raw["constants"].values() for name in names),
    )
