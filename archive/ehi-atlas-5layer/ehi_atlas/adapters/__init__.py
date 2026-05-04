"""Layer 1 source adapters.

Adapters are registered here and dispatched by the CLI / pipeline. New adapters
extend `Adapter` ABC (in `base.py`) and add themselves to REGISTRY.

See docs/ADAPTER-CONTRACT.md.
"""

from .base import Adapter, SourceMetadata
from .ccda import CCDAAdapter
from .epic_ehi import EpicEhiAdapter
from .lab_pdf import LabPDFAdapter
from .synthea import SyntheaAdapter
from .synthea_payer import SyntheaPayerAdapter

REGISTRY: dict[str, type[Adapter]] = {
    "ccda": CCDAAdapter,
    "epic-ehi": EpicEhiAdapter,
    "lab-pdf": LabPDFAdapter,
    "synthea": SyntheaAdapter,
    "synthea-payer": SyntheaPayerAdapter,  # D10: payer-side split of Synthea bundle
    # populated by Stage 2 sub-agents:
    # "blue-button": BlueButtonAdapter,
}

__all__ = [
    "Adapter",
    "CCDAAdapter",
    "EpicEhiAdapter",
    "LabPDFAdapter",
    "SourceMetadata",
    "REGISTRY",
    "SyntheaAdapter",
    "SyntheaPayerAdapter",
]
