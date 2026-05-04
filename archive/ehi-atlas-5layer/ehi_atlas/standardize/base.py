"""Layer 2 standardizer ABC. One implementation per source."""

from abc import ABC, abstractmethod
from pathlib import Path
from pydantic import BaseModel


class StandardizeResult(BaseModel):
    source: str
    patient_id: str
    silver_path: str           # absolute path to the bundle.json written
    sha256: str
    validation_errors: list[str]    # empty if valid; non-empty means strict failure
    validation_warnings: list[str]  # non-fatal


class Standardizer(ABC):
    name: str

    def __init__(self, bronze_root: Path, silver_root: Path):
        self.bronze_root = Path(bronze_root)
        self.silver_root = Path(silver_root)

    @abstractmethod
    def standardize(self, patient_id: str, *, strict: bool = False) -> StandardizeResult:
        """Read bronze, produce silver Bundle, validate. Idempotent."""
