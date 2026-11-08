"""Definition store of issue #17: AC-17-02 (stored files) and AC-17-03 (durability).

Real files under ``tmp_path`` only; failure injection patches ``os`` calls. No device.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

import pytest

from tests.scene_support import canonical_scene, scene_document, write_raw
from wled_mcp.client import ClientFailure
from wled_mcp.groups import MAX_DOCUMENT_BYTES as MAX_GROUP_BYTES
from wled_mcp.groups import Group, group_document, parse_group
from wled_mcp.scene_store import DefinitionStore, serialize_document
from wled_mcp.scenes import MAX_DOCUMENT_BYTES, Scene, parse_scene
from wled_mcp.scenes import scene_document as to_document


def scene_store(directory: Path, max_items: int = 500) -> DefinitionStore[Scene]:
    return DefinitionStore(
        directory / "scenes",
        "scene",
        lambda raw: parse_scene(raw, allow_placeholders=False),
        lambda item: item.id,
        max_items=max_items,
        max_bytes=MAX_DOCUMENT_BYTES,
    )


def group_store(directory: Path) -> DefinitionStore[Group]:
    return DefinitionStore(
        directory / "groups",
        "group",
        parse_group,
        lambda item: item.id,
        max_items=100,
        max_bytes=MAX_GROUP_BYTES,
    )


def scene(scene_id: str = "evening", **extra: Any) -> Scene:
    return parse_scene(scene_document(id=scene_id, **extra), allow_placeholders=False)


def body_of(item: Scene) -> bytes:
    return serialize_document(to_document(item), "scene document", MAX_DOCUMENT_BYTES)


def save(store: DefinitionStore[Scene], item: Scene, **kwargs: Any):
    kwargs.setdefault("overwrite", False)
    kwargs.setdefault("dry_run", False)
    return store.save(item, body_of(item), **kwargs)


def refused(call: Any) -> ClientFailure:
    with pytest.raises(ClientFailure) as caught:
        call()
    return caught.value


def files(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir()) if directory.exists() else []


# ---------------------------------------------------------------------- round trip


def test_save_load_list_and_delete_round_trip(tmp_path):
    store = scene_store(tmp_path)
    assert store.list_items().items == () and not (tmp_path / "scenes").exists()
    first, second = scene("b_second"), scene("a_first")
    assert save(store, first).replaced is None
    assert save(store, second).stored is True
    assert [item.id for item in store.list_items().items] == ["a_first", "b_second"]
    assert store.load("a_first") == second
    raw = (tmp_path / "scenes" / "a_first.json").read_bytes()
    assert raw == body_of(second) and raw.endswith(b"\n")
    assert json.loads(raw) == to_document(second)
    assert store.delete("a_first", dry_run=False) == second
    assert files(tmp_path / "scenes") == ["b_second.json"]


def test_replacing_needs_overwrite_and_returns_the_previous_document(tmp_path):
    store = scene_store(tmp_path)
    original = scene()
    save(store, original)
    changed = scene(name="Replacement")
    error = refused(lambda: save(store, changed))
    assert error.error.code == "VALIDATION_ERROR" and "overwrite=true" in error.error.message
    assert store.load("evening") == original
    result = save(store, changed, overwrite=True)
    assert result.replaced == original and store.load("evening") == changed


def test_dry_run_creates_nothing_and_changes_nothing(tmp_path):
    store = scene_store(tmp_path)
    item = scene()
    result = save(store, item, dry_run=True)
    assert result.stored is False and result.replaced is None
    assert not (tmp_path / "scenes").exists(), "no directory, no temporary file"
    save(store, item)
    before = (tmp_path / "scenes" / "evening.json").read_bytes()
    result = save(store, scene(name="Other"), overwrite=True, dry_run=True)
    assert result.replaced == item and result.stored is False
    assert store.delete("evening", dry_run=True) == item
    assert (tmp_path / "scenes" / "evening.json").read_bytes() == before
    assert refused(lambda: save(store, item, dry_run=True)).error.code == "VALIDATION_ERROR"


def test_missing_scene_is_a_distinct_not_found_error(tmp_path):
    store = scene_store(tmp_path)
    error = refused(lambda: store.load("absent"))
    assert (
        error.error.code == "VALIDATION_ERROR"
        and "No scene with ID 'absent'" in error.error.message
    )
    assert "No scene" in refused(lambda: store.delete("absent", dry_run=False)).error.message


# ---------------------------------------------------------------------- path safety


@pytest.mark.parametrize(
    "identifier", ["../escape", "a/b", "a\\b", "", "Upper", "x" * 65, ".hidden", "a.json"]
)
def test_ids_are_path_safe_before_any_filesystem_access(tmp_path, identifier):
    store = scene_store(tmp_path)
    for call in (
        lambda: store.load(identifier),
        lambda: store.delete(identifier, dry_run=False),
    ):
        assert refused(call).error.code == "VALIDATION_ERROR"
    assert files(tmp_path) == []


def test_foreign_and_temporary_names_are_ignored_not_counted_invalid(tmp_path):
    store = scene_store(tmp_path)
    save(store, scene())
    directory = tmp_path / "scenes"
    for name in ("README.txt", ".evening.abc.tmp", "Bad Name.json", "notes.json.bak"):
        write_raw(directory / name, "x")
    listing = store.list_items()
    assert [item.id for item in listing.items] == ["evening"] and listing.invalid_count == 0
    assert listing.warnings == ()


# ----------------------------------------------------------------- versions and files


def newer(scene_id: str = "future", version: Any = 2) -> bytes:
    return json.dumps(scene_document(id=scene_id, format_version=version)).encode()


@pytest.mark.parametrize("version", [2, 9999])
def test_a_newer_version_file_is_counted_named_and_never_rewritten(tmp_path, version):
    store = scene_store(tmp_path)
    save(store, scene())
    path = tmp_path / "scenes" / "future.json"
    write_raw(path, newer("future", version))
    original, stamp = path.read_bytes(), path.stat().st_mtime_ns
    listing = store.list_items()
    assert [item.id for item in listing.items] == ["evening"]
    assert listing.invalid_count == 1
    assert any("1 stored scene file(s)" in warning for warning in listing.warnings)
    assert "future" not in " ".join(listing.warnings), "invalid entries are counted, not named"
    error = refused(lambda: store.load("future"))
    assert f"scene format_version {version}" in error.error.message
    assert "reads format_version 1" in error.error.message
    for overwrite in (False, True):
        refusal = refused(lambda o=overwrite: save(store, scene("future"), overwrite=o))
        assert refusal.error.code == "VALIDATION_ERROR"
        assert f"format_version {version}" in refusal.error.message
    assert refused(lambda: store.delete("future", dry_run=False)).error.code == "VALIDATION_ERROR"
    assert path.read_bytes() == original and path.stat().st_mtime_ns == stamp


def test_save_refuses_to_replace_an_unusable_file_even_with_overwrite(tmp_path):
    store = scene_store(tmp_path)
    directory = tmp_path / "scenes"
    for content in (b"{not json", b"[]", b"", b"\xff\xfe", newer("broken", "1")):
        path = directory / "broken.json"
        write_raw(path, content)
        for overwrite in (False, True):
            error = refused(lambda o=overwrite: save(store, scene("broken"), overwrite=o))
            assert error.error.code == "VALIDATION_ERROR"
            assert "left untouched" in error.error.reconciliation
        assert path.read_bytes() == content
        assert files(directory) == ["broken.json"], "no temporary file is left behind"


def test_a_file_whose_id_differs_from_its_name_is_unusable(tmp_path):
    store = scene_store(tmp_path)
    write_raw(tmp_path / "scenes" / "other.json", json.dumps(scene_document(id="evening")))
    assert store.list_items().invalid_count == 1
    assert "does not match the file name" in refused(lambda: store.load("other")).error.message


def test_an_oversized_file_is_unusable_and_the_read_is_bounded(tmp_path):
    store = scene_store(tmp_path)
    path = tmp_path / "scenes" / "big.json"
    write_raw(path, b" " * (MAX_DOCUMENT_BYTES * 3))
    assert store.list_items().invalid_count == 1
    assert "exceeds" in refused(lambda: store.load("big")).error.message


def test_directories_and_symlinks_are_refused_not_followed(tmp_path):
    store = scene_store(tmp_path)
    save(store, scene())
    directory = tmp_path / "scenes"
    (directory / "isdir.json").mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(scene_document(id="linked")), encoding="utf-8")
    try:
        (directory / "linked.json").symlink_to(outside)
        linked = True
    except (OSError, NotImplementedError):
        linked = False
    listing = store.list_items()
    assert [item.id for item in listing.items] == ["evening"]
    assert listing.invalid_count == (2 if linked else 1)
    assert "not a regular file" in refused(lambda: store.load("isdir")).error.message
    assert (
        refused(lambda: save(store, scene("isdir"), overwrite=True)).error.code
        == "VALIDATION_ERROR"
    )
    if linked:
        assert refused(lambda: store.load("linked")).error.code == "VALIDATION_ERROR"
        assert (
            refused(lambda: store.delete("linked", dry_run=False)).error.code == "VALIDATION_ERROR"
        )
        assert outside.exists(), "a symlink target is never deleted"
        assert json.loads(outside.read_text("utf-8"))["id"] == "linked"


def test_a_directory_symlink_in_place_of_the_store_is_not_followed(tmp_path):
    target = tmp_path / "elsewhere"
    target.mkdir()
    try:
        (tmp_path / "scenes").symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available")
    store = scene_store(tmp_path)
    assert store.list_items().items == ()
    assert refused(lambda: save(store, scene())).error.code == "STORAGE_FAILED"
    assert files(target) == []


# ----------------------------------------------------------------------- durability


def test_a_failed_replace_keeps_the_previous_file_and_leaves_no_temporary_file(
    tmp_path, monkeypatch
):
    store = scene_store(tmp_path)
    original = scene()
    save(store, original)
    path = tmp_path / "scenes" / "evening.json"
    before = path.read_bytes()

    def broken(*args: Any, **kwargs: Any) -> None:
        raise OSError("synthetic disk failure with /secret/path and a scene name")

    monkeypatch.setattr(os, "replace", broken)
    error = refused(lambda: save(store, scene(name="Replacement"), overwrite=True))
    assert error.error.code == "STORAGE_FAILED"
    assert "secret" not in error.error.message and "Replacement" not in error.error.message
    assert "previous version is intact" in error.error.message
    assert path.read_bytes() == before
    assert files(tmp_path / "scenes") == ["evening.json"]
    monkeypatch.undo()
    assert store.load("evening") == original


def test_a_failed_fsync_or_write_is_a_not_attempted_storage_failure(tmp_path, monkeypatch):
    store = scene_store(tmp_path)

    def broken(*args: Any, **kwargs: Any) -> None:
        raise OSError("synthetic")

    monkeypatch.setattr(os, "fsync", broken)
    error = refused(lambda: save(store, scene()))
    assert error.error.code == "STORAGE_FAILED"
    assert files(tmp_path / "scenes") == [], "the temporary file is removed"


def test_an_unwritable_data_directory_is_a_storage_failure_and_reads_stay_empty(tmp_path):
    blocked = tmp_path / "data_is_a_file"
    blocked.write_text("x", encoding="utf-8")
    store = scene_store(blocked)
    assert store.list_items().items == ()
    error = refused(lambda: save(store, scene()))
    assert error.error.code == "STORAGE_FAILED"
    assert "no device was contacted" in error.error.reconciliation
    assert blocked.read_text("utf-8") == "x"
    missing_parent = scene_store(tmp_path / "does" / "not" / "exist")
    assert refused(lambda: save(missing_parent, scene())).error.code == "STORAGE_FAILED"


def test_a_file_in_place_of_the_store_directory_is_a_storage_failure(tmp_path):
    (tmp_path / "scenes").write_text("x", encoding="utf-8")
    store = scene_store(tmp_path)
    assert refused(lambda: save(store, scene())).error.code == "STORAGE_FAILED"


def test_delete_failure_keeps_the_file_and_is_a_storage_failure(tmp_path, monkeypatch):
    store = scene_store(tmp_path)
    save(store, scene())

    def broken(self: Path, *args: Any, **kwargs: Any) -> None:
        raise OSError("synthetic")

    monkeypatch.setattr(Path, "unlink", broken)
    assert refused(lambda: store.delete("evening", dry_run=False)).error.code == "STORAGE_FAILED"
    monkeypatch.undo()
    assert files(tmp_path / "scenes") == ["evening.json"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_directory_is_0700_and_files_are_0600_on_posix(tmp_path):
    store = scene_store(tmp_path)
    save(store, scene())
    assert (tmp_path / "scenes").stat().st_mode & 0o777 == 0o700
    assert (tmp_path / "scenes" / "evening.json").stat().st_mode & 0o777 == 0o600


def test_diagnostics_never_carry_names_paths_or_document_text(tmp_path, monkeypatch, caplog):
    store = scene_store(tmp_path)

    def broken(*args: Any, **kwargs: Any) -> None:
        raise OSError(f"synthetic failure at {tmp_path}")

    monkeypatch.setattr(os, "replace", broken)
    with caplog.at_level(logging.DEBUG):
        refused(lambda: save(store, scene(name="Private Evening Name")))
    text = " ".join(record.getMessage() for record in caplog.records)
    assert "Private Evening Name" not in text and str(tmp_path) not in text
    assert "kind=scene" in text


# ------------------------------------------------------------------------- bounds


def test_the_item_bound_blocks_new_ids_but_not_replacing_existing_ones(tmp_path):
    store = scene_store(tmp_path, max_items=2)
    save(store, scene("one"))
    save(store, scene("two"))
    error = refused(lambda: save(store, scene("three")))
    assert error.error.code == "VALIDATION_ERROR" and "maximum of 2" in error.error.message
    assert not (tmp_path / "scenes" / "three.json").exists()
    assert save(store, scene("two", name="Again"), overwrite=True).replaced is not None
    store.delete("one", dry_run=False)
    save(store, scene("three"))


def test_unusable_files_count_toward_the_item_bound(tmp_path):
    store = scene_store(tmp_path, max_items=1)
    write_raw(tmp_path / "scenes" / "broken.json", b"{")
    assert "maximum of 1" in refused(lambda: save(store, scene("fresh"))).error.message


def test_an_oversized_document_is_refused_before_any_file_is_written(tmp_path):
    store = scene_store(tmp_path)
    item = scene()
    assert (
        "exceeds"
        in refused(
            lambda: store.save(
                item, b"x" * (MAX_DOCUMENT_BYTES + 1), overwrite=False, dry_run=False
            )
        ).error.message
    )
    assert not (tmp_path / "scenes").exists()


def test_the_directory_scan_is_bounded(tmp_path, monkeypatch):
    store = scene_store(tmp_path)
    save(store, scene("one"))
    monkeypatch.setattr("wled_mcp.scene_store.MAX_DIRECTORY_ENTRIES", 1)
    write_raw(tmp_path / "scenes" / "two.json", json.dumps(scene_document(id="two")))
    listing = store.list_items()
    assert any("scan limit" in warning for warning in listing.warnings)
    assert len(listing.items) <= 1


def test_concurrent_saves_of_one_id_serialize_and_keep_a_complete_file(tmp_path):
    store = scene_store(tmp_path)
    results: list[str] = []

    def worker(index: int) -> None:
        item = scene(name=f"Writer {index}")
        try:
            store.save(item, body_of(item), overwrite=True, dry_run=False)
            results.append("ok")
        except ClientFailure:
            results.append("failed")

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count("ok") == 8
    assert store.load("evening").name.startswith("Writer ")
    assert files(tmp_path / "scenes") == ["evening.json"]


# --------------------------------------------------------------------------- groups


def test_group_store_uses_the_same_rules(tmp_path):
    store = group_store(tmp_path)
    group = parse_group(
        {
            "format": "wled-mcp.group",
            "format_version": 1,
            "id": "shelf",
            "name": "Shelf",
            "members": [{"device": "desk"}],
        }
    )
    body = serialize_document(group_document(group), "group document", MAX_GROUP_BYTES)
    assert store.save(group, body, overwrite=False, dry_run=False).stored
    assert store.load("shelf") == group and files(tmp_path / "groups") == ["shelf.json"]
    path = tmp_path / "groups" / "future.json"
    path.write_text(
        json.dumps({**group_document(group), "id": "future", "format_version": 3}), encoding="utf-8"
    )
    assert "group format_version 3" in refused(lambda: store.load("future")).error.message
    assert store.list_items().invalid_count == 1


def test_canonical_document_is_stored_exactly_as_serialized(tmp_path):
    store = scene_store(tmp_path)
    item = parse_scene(canonical_scene(), allow_placeholders=False)
    save(store, item)
    assert (tmp_path / "scenes" / "evening.json").read_bytes() == body_of(item)
