from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import pytest

from ssscreen_web.domain.errors import DomainError
from ssscreen_web.infrastructure.artifacts import FileSystemArtifactStore


def test_put_and_read_are_atomic_and_hashed(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path / "artifacts")
    store.ensure_ready()
    stored = store.put_bytes(b"stable content", key="projects/p1/artifacts/a1/result.json")
    assert stored.sha256 == "ce382ddb3d232ecb903c37fe6bd4779a18c6d664a15d7ddee0e5ca7ea9406120"
    with store.open_read(stored.key) as handle:
        assert handle.read() == b"stable content"
    assert not list((tmp_path / "artifacts").rglob(".upload-*"))


def test_readiness_probe_leaves_no_files(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path / "artifacts")
    store.ensure_ready()
    assert list(store.root.iterdir()) == []


@pytest.mark.parametrize("key", ["../secret", "/etc/passwd", "projects/../../secret", "bad\x00key"])
def test_unsafe_keys_are_rejected(tmp_path: Path, key: str) -> None:
    store = FileSystemArtifactStore(tmp_path / "artifacts")
    store.ensure_ready()
    with pytest.raises(DomainError, match="key"):
        store.put_bytes(b"x", key=key)


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "projects").symlink_to(outside, target_is_directory=True)
    store = FileSystemArtifactStore(root)
    with pytest.raises(DomainError, match="escapes"):
        store.put_bytes(b"x", key="projects/p1/result.json")


def test_existing_artifact_is_immutable(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path / "artifacts")
    store.ensure_ready()
    key = "projects/p1/artifacts/a1/result.json"
    store.put_bytes(b"first", key=key)
    with pytest.raises(DomainError) as caught:
        store.put_bytes(b"second", key=key)
    assert caught.value.code == "artifact.immutable"


def test_hash_mismatch_is_rejected_before_publish(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path / "artifacts")
    store.ensure_ready()
    with pytest.raises(DomainError) as caught:
        store.put_bytes(b"content", key="projects/p1/a1/result.json", expected_sha256="0" * 64)
    assert caught.value.code == "artifact.hash_mismatch"
    assert not list(store.root.rglob("result.json"))


def test_partial_write_is_removed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = FileSystemArtifactStore(tmp_path / "artifacts")
    store.ensure_ready()

    def fail_replace(source: Path, target: Path) -> None:
        del source, target
        raise OSError("simulated publish failure")

    monkeypatch.setattr("ssscreen_web.infrastructure.artifacts.os.link", fail_replace)
    with pytest.raises(OSError, match="publish failure"):
        store.put_bytes(b"content", key="projects/p1/a1/result.json")
    assert not list(store.root.rglob(".upload-*"))


def test_same_display_filename_can_use_distinct_server_keys(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path / "artifacts")
    store.ensure_ready()
    first = store.put_bytes(b"one", key="projects/p1/a1/result.json")
    second = store.put_bytes(b"two", key="projects/p1/a2/result.json")
    assert first.key != second.key


def test_concurrent_publish_never_overwrites_existing_content(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path / "artifacts")
    store.ensure_ready()
    key = "projects/p1/a1/result.json"

    def publish(content: bytes) -> str:
        try:
            store.put_bytes(content, key=key)
        except DomainError as error:
            return error.code
        return "published"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(publish, (b"first", b"second")))
    assert sorted(outcomes) == ["artifact.immutable", "published"]
    with store.open_read(key) as handle:
        assert handle.read() in {b"first", b"second"}


def test_put_file_streams_without_reading_entire_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "large.df"
    source.write_bytes(b"chunked-content" * 1024)
    store = FileSystemArtifactStore(tmp_path / "artifacts")
    store.ensure_ready()

    def reject_read_bytes(self: Path) -> bytes:
        raise AssertionError(f"read_bytes must not be used for streaming publish: {self}")

    monkeypatch.setattr(Path, "read_bytes", reject_read_bytes)
    stored = store.put_file(
        source,
        key="projects/project-1/datasets/dataset-1/artifact-1/mp.df",
        content_type="application/x-pandas-pickle",
    )

    assert stored.size_bytes == source.stat().st_size


def test_put_stream_enforces_limit_and_removes_partial_file(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path / "uploads")
    store.ensure_ready()
    with pytest.raises(DomainError) as caught:
        store.put_stream(BytesIO(b"too-large"), key="uploads/input.extxyz", max_bytes=3)
    assert caught.value.code == "upload.too_large"
    assert not list(store.root.rglob("input.extxyz"))
    assert not list(store.root.rglob(".upload-*"))


def test_put_stream_hashes_content(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path / "uploads")
    stored = store.put_stream(BytesIO(b"abc"), key="uploads/input.extxyz", max_bytes=3)
    assert stored.size_bytes == 3
    assert stored.sha256 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
