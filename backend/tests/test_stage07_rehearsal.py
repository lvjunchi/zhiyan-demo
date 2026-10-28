from pathlib import Path
import importlib.util


def test_rehearsal_runs_from_file_to_frozen_package_and_clear(tmp_path):
    path = Path(__file__).resolve().parents[2] / "scripts" / "rehearse_demo.py"
    assert path.is_file()
    spec = importlib.util.spec_from_file_location("rehearse_demo", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.rehearse(tmp_path / "isolated")
    assert report["coverage_sequence"] == [80, 60, 80, 100]
    assert report["package_status"] == "human_approved"
    assert report["old_results_retained"] is True
    assert report["frozen_export_unchanged"] is True
    assert report["word_requirements"] == report["pdf_requirements"]
    assert report["post_clear_requirement_ids_disjoint"] is True
