import json

from scripts.prepare_agent_comparison import prepare
from scripts.export_workspace_package import build_package


def test_prepare_agent_comparison_run(tmp_path):
    package = tmp_path / "synthea-demo.zip"
    build_package("synthea-demo", package, include_originals=False)

    out_dir = tmp_path / "comparison"
    prepare("synthea-demo", package, out_dir, copy=True)

    manifest = json.loads((out_dir / "comparison-manifest.json").read_text())
    assert manifest["comparison_version"] == "atlas-agent-comparison.v1"
    assert {"raw", "package", "package-plus-raw"} == set(manifest["arms"])
    assert len(manifest["prompts"]) == 5
    assert (out_dir / "prompts" / "patient-summary.md").exists()
    assert (out_dir / "arms" / "raw" / "INSTRUCTIONS.md").exists()
    assert (out_dir / "arms" / "package" / "inputs" / package.name).exists()
