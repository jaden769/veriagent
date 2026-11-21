import hashlib
import json
import sys
import zipfile

import pytest
from test_browser_contract import versioned_evaluation
from test_browser_controls_audit import fixture_evaluation
from test_browser_controls_audit import nested_audit as nested_audit

from veriagent.browser_archive import archive_browser_controls, restore_browser_controls
from veriagent.cli import main


def inventory(directory):
    return {
        p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in directory.rglob("*")
        if p.is_file()
    }


def test_roundtrip_preserves_all_bytes_and_strict_contract(tmp_path, nested_audit):
    source = versioned_evaluation(tmp_path)
    before = inventory(source)
    archive = tmp_path / "transfer.zip"
    result = archive_browser_controls(source, archive, require_contract=True)
    assert result["evidence_passed"] and result["matrix_contract"]["status"] == "matched"
    destination = tmp_path / "restored tree"
    restore_browser_controls(archive, destination, require_contract=True)
    assert inventory(source) == inventory(destination) == before
    assert not list(tmp_path.glob("veriagent-*"))


@pytest.mark.parametrize(
    "name",
    ["../escape", "/absolute", "C:/drive", "a\\b", "a//b", "a/./b", "NUL.txt", "x.", "a/../../b"],
)
def test_unsafe_members_leave_no_destination(tmp_path, name):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr(name, b"bad")
    destination = tmp_path / "restored"
    with pytest.raises(ValueError):
        restore_browser_controls(archive, destination)
    assert not destination.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bad.zip"]


@pytest.mark.parametrize(
    "mutation", ["duplicate", "link", "large_file", "total", "count", "compressed", "bad_evidence"]
)
def test_unsupported_or_excessive_archives_fail_closed(tmp_path, monkeypatch, mutation):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        info = zipfile.ZipInfo("controls.json")
        if mutation == "link":
            info.create_system = 3
            info.external_attr = 0o120777 << 16
        output.writestr(info, b"{}")
        if mutation == "duplicate":
            output.writestr("CONTROLS.json", b"{}")
    limits = {
        "large_file": "MAX_FILE_BYTES",
        "total": "MAX_TOTAL_BYTES",
        "count": "MAX_FILES",
        "compressed": "MAX_ARCHIVE_BYTES",
    }
    if mutation in limits:
        monkeypatch.setattr("veriagent.browser_archive." + limits[mutation], 0)
    destination = tmp_path / "restored"
    with pytest.raises(ValueError):
        restore_browser_controls(archive, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob("veriagent-*"))


def test_no_overwrites_or_archive_inside_source(tmp_path, nested_audit):
    source = versioned_evaluation(tmp_path)
    archive = tmp_path / "existing.zip"
    archive.write_bytes(b"keep")
    with pytest.raises(ValueError):
        archive_browser_controls(source, archive)
    assert archive.read_bytes() == b"keep"
    with pytest.raises(ValueError):
        archive_browser_controls(source, source / "nested.zip")
    with pytest.raises(ValueError):
        restore_browser_controls(archive, source)


def test_invalid_source_never_publishes_archive(tmp_path):
    source = tmp_path / "invalid"
    source.mkdir()
    archive = tmp_path / "new.zip"
    with pytest.raises(ValueError, match="audit failed"):
        archive_browser_controls(source, archive)
    assert not archive.exists()


def test_changed_source_is_caught_by_audit_of_archived_bytes(tmp_path, nested_audit, monkeypatch):
    from veriagent import browser_archive

    source = versioned_evaluation(tmp_path)
    original = browser_archive._audit
    calls = 0

    def audit_then_change(directory, require_contract):
        nonlocal calls
        result = original(directory, require_contract)
        calls += 1
        if calls == 1:
            manifest = next(source.glob("*/manifest.json"))
            manifest.write_bytes(manifest.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(browser_archive, "_audit", audit_then_change)
    archive = tmp_path / "new.zip"
    with pytest.raises(ValueError, match="audit failed"):
        archive_browser_controls(source, archive)
    assert not archive.exists()
    assert not list(tmp_path.glob("veriagent-*"))


def test_cli_roundtrip_and_invalid_input(tmp_path, nested_audit, monkeypatch, capsys):
    source = versioned_evaluation(tmp_path)
    archive = tmp_path / "transfer.zip"
    destination = tmp_path / "restored"
    for command, first, second in (
        ("archive-browser-controls", source, archive),
        ("restore-browser-controls", archive, destination),
    ):
        monkeypatch.setattr(
            sys, "argv", ["veriagent", command, str(first), str(second), "--require-contract"]
        )
        main()
        assert json.loads(capsys.readouterr().out)["evidence_passed"]
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


@pytest.mark.parametrize("require_contract", [False, True])
@pytest.mark.parametrize("identity", ["legacy", "missing_modern", "mismatch"])
def test_archive_contract_compatibility_and_failed_publication(
    tmp_path, nested_audit, require_contract, identity
):
    source = fixture_evaluation(tmp_path / "source")
    controls = source / "controls.json"
    saved = json.loads(controls.read_text())
    if identity == "missing_modern":
        saved["schema_version"] = 2
    elif identity == "mismatch":
        from veriagent.browser_catalog import saved_control_matrix
        from veriagent.browser_controls import matrix_contract

        saved["matrix_contract"] = matrix_contract(saved_control_matrix(saved))
        saved["matrix_contract"]["sha256"] = "0" * 64
    controls.write_text(json.dumps(saved), encoding="utf-8")
    before = inventory(source)
    # An external ZIP lets restore policy be exercised even when creation rejects it.
    incoming = tmp_path / "incoming.zip"
    with zipfile.ZipFile(incoming, "w") as output:
        for path in source.rglob("*"):
            if path.is_file():
                output.write(path, path.relative_to(source).as_posix())
    incoming_before = incoming.read_bytes()
    archive, destination = tmp_path / "published.zip", tmp_path / "restored"
    if identity == "legacy" and not require_contract:
        created = archive_browser_controls(source, archive)
        restored = restore_browser_controls(incoming, destination)
        for result in (created, restored):
            assert result["matrix_contract"]["status"] == "legacy_missing"
        assert inventory(destination) == before
    else:
        with pytest.raises(ValueError, match="audit failed"):
            archive_browser_controls(source, archive, require_contract=require_contract)
        with pytest.raises(ValueError, match="audit failed"):
            restore_browser_controls(incoming, destination, require_contract=require_contract)
        assert not archive.exists() and not destination.exists()
    assert inventory(source) == before and incoming.read_bytes() == incoming_before
    assert not list(tmp_path.glob("veriagent-*"))


@pytest.mark.parametrize("strict", [False, True])
def test_cli_legacy_transfer_policy(tmp_path, nested_audit, monkeypatch, capsys, strict):
    source = fixture_evaluation(tmp_path / "source")
    archive = tmp_path / "legacy.zip"
    archive_browser_controls(source, archive)
    for command, first, second in (
        ("archive-browser-controls", source, tmp_path / "out.zip"),
        ("restore-browser-controls", archive, tmp_path / "restored"),
    ):
        argv = ["veriagent", command, str(first), str(second)]
        monkeypatch.setattr(sys, "argv", argv + (["--require-contract"] if strict else []))
        if strict:
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 2 and not second.exists()
            assert not capsys.readouterr().out
        else:
            main()
            result = json.loads(capsys.readouterr().out)
            assert result["matrix_contract"]["status"] == "legacy_missing"
