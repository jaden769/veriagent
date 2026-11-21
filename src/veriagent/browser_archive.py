"""Bounded ZIP transfer of complete, auditable browser evaluation trees."""

import os
import re
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from veriagent.browser_controls_audit import audit_browser_controls

MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_FILES = 4096


def _name(name):
    parts = PurePosixPath(name).parts
    if (
        not parts
        or len(parts) > 8
        or len(name) > 240
        or "/".join(parts) != name
        or any(
            not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", part)
            or part.endswith(".")
            or part.split(".")[0].upper()
            in {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *[f"COM{i}" for i in range(10)],
                *[f"LPT{i}" for i in range(10)],
            }
            for part in parts
        )
    ):
        raise ValueError("Unsafe archive member name")
    return parts


def _audit(directory, require_contract):
    result = audit_browser_controls(directory, require_contract=require_contract)
    if not result["evidence_passed"]:
        raise ValueError("Evaluation evidence audit failed")
    return result


def _members(source):
    members = source.infolist()
    if not 1 <= len(members) <= MAX_FILES:
        raise ValueError("Archive file count exceeds limit")
    names = set()
    total = 0
    for member in members:
        _name(member.filename)
        key = member.filename.casefold()
        mode = member.external_attr >> 16
        if (
            key in names
            or member.is_dir()
            or mode & 0o170000 not in (0, 0o100000)
            or member.flag_bits & 1
            or member.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
            or not 0 <= member.file_size <= MAX_FILE_BYTES
        ):
            raise ValueError("Unsupported or duplicate archive member")
        names.add(key)
        total += member.file_size
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Archive exceeds expanded size limit")
    for name in names:
        parts = name.split("/")
        if any("/".join(parts[:i]) in names for i in range(1, len(parts))):
            raise ValueError("Archive file conflicts with a parent directory")
    return members


def _open(archive):
    if archive.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("Archive exceeds compressed size limit")
    return zipfile.ZipFile(archive)


def inspect_browser_archive(archive: Path):
    archive = Path(archive)
    with _open(archive) as source:
        members = _members(source)
        return {
            "schema_version": 1,
            "scope": "archive_directory_metadata",
            "metadata_passed": True,
            "archive_bytes": archive.stat().st_size,
            "files": len(members),
            "declared_expanded_bytes": sum(m.file_size for m in members),
            "declared_compressed_bytes": sum(m.compress_size for m in members),
            "controls_json_present": any(m.filename == "controls.json" for m in members),
            "members": [
                {
                    "name": m.filename,
                    "declared_bytes": m.file_size,
                    "declared_compressed_bytes": m.compress_size,
                    "compression": "stored" if m.compress_type == 0 else "deflate",
                }
                for m in sorted(members, key=lambda m: m.filename)
            ],
            "limitations": (
                "ZIP directory metadata only; payloads are not decompressed, CRCs are not "
                "checked and evidence is not audited. Sizes are declared, not verified. "
                "Restoration must independently validate and audit the archive."
            ),
        }


def render_archive_inspection(result):
    lines = [
        "Browser evidence archive metadata",
        f"Files: {result['files']}",
        f"Archive bytes: {result['archive_bytes']}",
        f"Declared expanded bytes: {result['declared_expanded_bytes']}",
        f"Declared compressed bytes: {result['declared_compressed_bytes']}",
        f"Root controls.json present: {result['controls_json_present']}",
        "",
    ]
    lines.extend(f"- {m['name']}: {m['declared_bytes']} bytes" for m in result["members"])
    return "\n".join([*lines, "", result["limitations"], ""])


def _extract(archive, destination):
    with _open(archive) as source:
        # Inspect all members before creating any extracted file.
        for member in _members(source):
            target = destination.joinpath(*_name(member.filename))
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(member) as stream, target.open("xb") as output:
                data = stream.read(MAX_FILE_BYTES + 1)
                if len(data) != member.file_size or len(data) > MAX_FILE_BYTES:
                    raise ValueError("Archive member size mismatch")
                output.write(data)


def archive_browser_controls(directory: Path, archive: Path, *, require_contract=False):
    directory, archive = directory.resolve(), archive.absolute()
    if archive.exists() or archive.resolve().is_relative_to(directory):
        raise ValueError("Archive must be a new file outside the evaluation tree")
    _audit(directory, require_contract)
    with tempfile.TemporaryDirectory(prefix="veriagent-archive-", dir=archive.parent) as staging:
        temporary = Path(staging) / "evaluation.zip"
        total = count = 0
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as output:
            for path in sorted(directory.rglob("*")):
                if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                    raise ValueError("Linked evaluation entries are not supported")
                if path.is_dir():
                    continue
                name = path.relative_to(directory).as_posix()
                _name(name)
                count += 1
                with path.open("rb") as stream:
                    data = stream.read(MAX_FILE_BYTES + 1)
                total += len(data)
                if count > MAX_FILES or len(data) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
                    raise ValueError("Evaluation tree exceeds archive limits")
                output.writestr(name, data)
        restored = Path(staging) / "verification"
        restored.mkdir()
        _extract(temporary, restored)
        audit = _audit(restored, require_contract)
        # Publish without replacing an existing file, including concurrent creation.
        os.link(temporary, archive)
    return _result(archive, audit)


def restore_browser_controls(archive: Path, destination: Path, *, require_contract=False):
    archive, destination = archive.absolute(), destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError("Restore destination must not exist")
    with tempfile.TemporaryDirectory(
        prefix="veriagent-restore-", dir=destination.parent
    ) as staging:
        restored = Path(staging) / "evaluation"
        restored.mkdir()
        _extract(archive, restored)
        audit = _audit(restored, require_contract)
        if destination.exists():
            raise ValueError("Restore destination already exists")
        restored.rename(destination)
    return _result(destination, audit)


def _result(path, audit):
    return {
        "schema_version": 1,
        "path": str(path),
        "evidence_passed": True,
        "controls_passed": audit["controls_passed"],
        "matrix": audit["matrix"],
        "matrix_contract": audit["matrix_contract"],
        "limitations": "Unsigned evidence consistency; not authenticated provenance.",
    }
