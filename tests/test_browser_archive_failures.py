"""Publication failures must preserve inputs and clean private staging."""

import os
from pathlib import Path

import pytest
from test_browser_archive import inventory
from test_browser_contract import versioned_evaluation
from test_browser_controls_audit import nested_audit as nested_audit

from veriagent import browser_archive


@pytest.mark.parametrize("operation", ["archive", "restore"])
@pytest.mark.parametrize("phase", ["extract", "audit", "publish", "concurrent_file"])
def test_transfer_failure_cleanup_and_input_preservation(
    tmp_path, nested_audit, monkeypatch, operation, phase
):
    source = versioned_evaluation(tmp_path)
    incoming = tmp_path / "incoming.zip"
    browser_archive.archive_browser_controls(source, incoming)
    before_source, before_archive = inventory(source), incoming.read_bytes()
    destination = tmp_path / ("output.zip" if operation == "archive" else "restored")
    if phase == "extract":
        original = browser_archive._extract

        def extract_then_fail(archive, directory):
            original(archive, directory)
            (directory / "partial.txt").write_bytes(b"partial")
            raise OSError("Injected extraction write failure")

        monkeypatch.setattr(browser_archive, "_extract", extract_then_fail)
    elif phase == "audit":
        original = browser_archive._audit

        def staged_audit_failure(directory, require_contract):
            if directory != source:
                raise ValueError("Injected staged audit failure")
            return original(directory, require_contract)

        monkeypatch.setattr(browser_archive, "_audit", staged_audit_failure)
    elif operation == "archive":
        original = os.link

        def link_failure(first, second):
            if phase == "concurrent_file":
                Path(second).write_bytes(b"concurrent owner")
                return original(first, second)
            raise PermissionError("Injected archive publication failure")

        monkeypatch.setattr(browser_archive.os, "link", link_failure)
    else:
        original = Path.rename

        def rename_failure(first, second):
            if phase == "concurrent_file":
                Path(second).write_bytes(b"concurrent owner")
                return original(first, second)
            raise PermissionError("Injected restore publication failure")

        monkeypatch.setattr(Path, "rename", rename_failure)
    function = (
        browser_archive.archive_browser_controls
        if operation == "archive"
        else browser_archive.restore_browser_controls
    )
    with pytest.raises((OSError, ValueError)):
        function(source if operation == "archive" else incoming, destination)
    if phase == "concurrent_file":
        assert destination.read_bytes() == b"concurrent owner"
    else:
        assert not destination.exists()
    assert inventory(source) == before_source
    assert incoming.read_bytes() == before_archive
    assert not list(tmp_path.glob("veriagent-*"))


def test_destination_created_during_restore_audit_is_preserved(tmp_path, nested_audit, monkeypatch):
    source = versioned_evaluation(tmp_path)
    incoming = tmp_path / "incoming.zip"
    browser_archive.archive_browser_controls(source, incoming)
    destination = tmp_path / "restored"
    original = browser_archive._audit

    def audit_and_create(directory, require_contract):
        result = original(directory, require_contract)
        destination.mkdir()
        (destination / "owner.txt").write_bytes(b"keep")
        return result

    monkeypatch.setattr(browser_archive, "_audit", audit_and_create)
    with pytest.raises(ValueError, match="already exists"):
        browser_archive.restore_browser_controls(incoming, destination)
    assert [p.name for p in destination.iterdir()] == ["owner.txt"]
    assert (destination / "owner.txt").read_bytes() == b"keep"
    assert not list(tmp_path.glob("veriagent-*"))


@pytest.mark.parametrize("operation", ["archive", "restore"])
def test_missing_output_parent_is_not_created(tmp_path, nested_audit, operation):
    source = versioned_evaluation(tmp_path)
    incoming = tmp_path / "incoming.zip"
    browser_archive.archive_browser_controls(source, incoming)
    parent = tmp_path / "missing"
    function = (
        browser_archive.archive_browser_controls
        if operation == "archive"
        else browser_archive.restore_browser_controls
    )
    with pytest.raises(FileNotFoundError):
        function(source if operation == "archive" else incoming, parent / "output")
    assert not parent.exists()
