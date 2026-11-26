import zipfile
from pathlib import Path

import pytest

from research import reflection_evidence as evidence
from research.run_bounded_oracle import save

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "docs/evidence/reflection-comparison-2026-11-26.zip"
EXPECTED = "b15d202a3f160e4f9968b287c7a6f4ce46fdcc1834d3c885ab5fb91fb770660c"


@pytest.fixture
def relocated(tmp_path):
    evidence._extract(ARCHIVE, tmp_path)
    return tmp_path


def test_archive_audit_blocks_original_and_repository_metadata(monkeypatch):
    original = evidence._read

    def guarded(directory, name):
        if directory.resolve().is_relative_to(ROOT) or "62feb890e069465bae62ca45a0a3845c" in str(
            directory
        ):
            pytest.fail("Portable audit followed original or repo metadata")
        return original(directory, name)

    monkeypatch.setattr(evidence, "_read", guarded)
    result = evidence.audit_archive(ARCHIVE, EXPECTED)
    assert result["runs"] == 96 and result["files"] == 583
    assert result["false_successes"] == 10


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "manifest",
        "source",
        "corpus",
        "plan",
        "trace",
        "sql",
        "resource",
        "outcome",
        "duplicate",
        "path",
        "partial",
    ],
)
def test_reject_corruption(relocated, mutation):
    directory = relocated
    expected = EXPECTED
    manifest = evidence.read(directory / "manifest.json")
    if mutation == "extra":
        (directory / "extra.txt").write_text("unbound")
    elif mutation in {"source", "corpus", "plan", "trace", "sql"}:
        name = {
            "source": "runner-source.py",
            "corpus": "corpus.json",
            "plan": "plan.json",
            "trace": "trial-001/trace.json",
            "sql": "trial-001/state.sqlite",
        }[mutation]
        with (directory / name).open("ab") as stream:
            stream.write(b"changed")
    else:
        if mutation == "resource":
            manifest["runs"][0]["resources"]["actions"] += 1
            save(directory / "trial-001/result.json", manifest["runs"][0])
        elif mutation == "outcome":
            manifest["runs"][0]["ground_truth_success"] = False
            save(directory / "trial-001/result.json", manifest["runs"][0])
        elif mutation == "duplicate":
            manifest["runs"][1]["run_id"] = manifest["runs"][0]["run_id"]
        elif mutation == "path":
            manifest["runs"][0]["directory"] = "../outside"
        elif mutation == "partial":
            manifest["complete"] = False
        else:
            manifest["provider"] = "changed"
        save(directory / "manifest.json", manifest)
        if mutation != "manifest":
            expected = evidence.digest(directory / "manifest.json")
    with pytest.raises((ValueError, KeyError)):
        evidence.audit_directory(directory, expected)


def test_archive_traversal_rejected(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("../outside.txt", b"unsafe")
    with pytest.raises(ValueError):
        evidence.audit_archive(archive, EXPECTED)
    assert not (tmp_path / "outside.txt").exists()


def test_duplicate_json_keys_rejected(relocated):
    (relocated / "manifest.json").write_text('{"runs":[],"runs":[]}')
    expected = evidence.digest(relocated / "manifest.json")
    with pytest.raises(ValueError, match="Duplicate"):
        evidence.audit_directory(relocated, expected)


def test_missing_external_hash_rejected(relocated):
    with pytest.raises(ValueError, match="external"):
        evidence.audit_directory(relocated, "")


def test_package_never_overwrites(tmp_path):
    existing = tmp_path / "existing.zip"
    existing.write_bytes(b"keep")
    with pytest.raises(ValueError, match="new archive"):
        evidence.package(
            tmp_path, existing, ROOT / "docs/review/reflection-comparison-results.json"
        )
    assert existing.read_bytes() == b"keep"
