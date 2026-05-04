from .base import Standardizer, StandardizeResult
from .synthea import SyntheaStandardizer
# from .synthea_payer import SyntheaPayerStandardizer  # future
# from .epic_ehi import EpicEhiStandardizer            # future
# from .ccda import CCDAStandardizer                   # future
# from .lab_pdf import LabPDFStandardizer              # future

REGISTRY: dict[str, type[Standardizer]] = {
    "synthea": SyntheaStandardizer,
}

__all__ = [
    "Standardizer",
    "StandardizeResult",
    "SyntheaStandardizer",
    "REGISTRY",
]
