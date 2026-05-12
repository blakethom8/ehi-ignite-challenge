"""Per-episode narrative generator.

Given a patient's harmonized chart + patient-voice bundle + a curated
list of EpisodeOfCare resources, generate one FHIR ``Composition`` per
episode. Each Composition cites the merged resources it draws from,
with every claim grounded in a specific resource ID that appears in
the harmonized record.

See ``docs/architecture/LLM-CONTEXT-AUGMENTATION-PLAN.md`` §T5 for the
contract and §3.3 for the worked Composition example.
"""

from .generator import (
    EpisodeNarrativeGenerator,
    FakeNarrativeGenerator,
    SonnetNarrativeGenerator,
    generate_episode_narrative,
)
from .storage import (
    NARRATIVE_STORE_ROOT,
    episode_slug_for,
    history_dir_for,
    load_current_narrative,
    write_current_narrative,
)

__all__ = [
    "EpisodeNarrativeGenerator",
    "FakeNarrativeGenerator",
    "NARRATIVE_STORE_ROOT",
    "SonnetNarrativeGenerator",
    "episode_slug_for",
    "generate_episode_narrative",
    "history_dir_for",
    "load_current_narrative",
    "write_current_narrative",
]
