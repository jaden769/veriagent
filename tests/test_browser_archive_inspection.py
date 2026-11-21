import json
import sys
import zipfile

import pytest

from veriagent.browser_archive import inspect_browser_archive, restore_browser_controls
from veriagent.cli import main


def test_inspection_is_metadata_only_and_read_only(tmp_path, monkeypatch):
    archive = tmp_path / "evidence.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr("controls.json", b"not valid evidence")
        output.writestr("batch/data.txt", b"payload" * 100)
    before = archive.read_bytes()

    def forbidden(*args, **kwargs):
        pytest.fail("Inspection must not open member payloads, extract or audit evidence")

    monkeypatch.setattr(zipfile.ZipFile, "open", forbidden)
    monkeypatch.setattr("veriagent.browser_archive._audit", forbidden)
    result = inspect_browser_archive(archive)
    assert result["files"] == 2 and result["controls_json_present"]
    assert result["declared_expanded_bytes"] == 718
    assert result["scope"] == "archive_directory_metadata"
    assert [m["name"] for m in result["members"]] == ["batch/data.txt", "controls.json"]
    assert archive.read_bytes() == before
    assert list(tmp_path.iterdir()) == [archive]


@pytest.mark.parametrize(
    "names", [["../escape"], ["/root"], ["NUL.txt"], ["a", "A"], ["a", "a/b"], ["a/b", "A"]]
)
def test_unsafe_names_and_file_parent_conflicts_rejected(tmp_path, names):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name in names:
            output.writestr(name, b"x")
    with pytest.raises(ValueError):
        inspect_browser_archive(archive)
    with pytest.raises(ValueError):
        restore_browser_controls(archive, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


@pytest.mark.parametrize(
    "limit", ["MAX_ARCHIVE_BYTES", "MAX_TOTAL_BYTES", "MAX_FILE_BYTES", "MAX_FILES"]
)
def test_inspection_enforces_shared_resource_limits(tmp_path, monkeypatch, limit):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("controls.json", b"{}")
    monkeypatch.setattr("veriagent.browser_archive." + limit, 0)
    with pytest.raises(ValueError):
        inspect_browser_archive(archive)


def test_corrupt_payload_is_not_certified_by_inspection(tmp_path):
    archive = tmp_path / "corrupt.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("controls.json", b"unique-payload")
    archive.write_bytes(archive.read_bytes().replace(b"unique-payload", b"broken-payload"))
    result = inspect_browser_archive(archive)
    assert result["metadata_passed"]
    assert "CRCs are not checked" in result["limitations"]
    with pytest.raises(zipfile.BadZipFile):
        restore_browser_controls(archive, tmp_path / "restored")
    assert not (tmp_path / "restored").exists()


@pytest.mark.parametrize("output_format", ["text", "json"])
def test_cli_formats_and_failure(tmp_path, monkeypatch, capsys, output_format):
    archive = tmp_path / "data.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("data.txt", b"x")
    monkeypatch.setattr(
        sys,
        "argv",
        ["veriagent", "inspect-browser-archive", str(archive), "--format", output_format],
    )
    main()
    output = capsys.readouterr().out
    assert "Sizes are declared, not verified" in output
    if output_format == "json":
        assert not json.loads(output)["controls_json_present"]
    archive.write_bytes(b"not a zip")
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2
