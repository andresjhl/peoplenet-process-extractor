import hashlib

import pytest

from peoplenet_process_extractor.manifest.hashing import compute_file_hash_and_size


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_empty_file(tmp_path):
    f = tmp_path / "empty.bin"
    f.write_bytes(b"")
    sha, size = compute_file_hash_and_size(f)
    assert sha == _sha256(b"")
    assert size == 0


def test_text_file(tmp_path):
    content = b"hello world\n"
    f = tmp_path / "text.txt"
    f.write_bytes(content)
    sha, size = compute_file_hash_and_size(f)
    assert sha == _sha256(content)
    assert size == len(content)


def test_binary_file(tmp_path):
    content = bytes(range(256)) * 16
    f = tmp_path / "binary.bin"
    f.write_bytes(content)
    sha, size = compute_file_hash_and_size(f)
    assert sha == _sha256(content)
    assert size == len(content)


def test_one_byte_change_produces_different_hash(tmp_path):
    f1 = tmp_path / "a.bin"
    f2 = tmp_path / "b.bin"
    f1.write_bytes(b"hello")
    f2.write_bytes(b"hellp")
    sha1, _ = compute_file_hash_and_size(f1)
    sha2, _ = compute_file_hash_and_size(f2)
    assert sha1 != sha2


def test_crlf_vs_lf_differ(tmp_path):
    lf = tmp_path / "lf.txt"
    crlf = tmp_path / "crlf.txt"
    lf.write_bytes(b"line1\nline2\n")
    crlf.write_bytes(b"line1\r\nline2\r\n")
    sha_lf, _ = compute_file_hash_and_size(lf)
    sha_crlf, _ = compute_file_hash_and_size(crlf)
    assert sha_lf != sha_crlf


def test_nonexistent_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        compute_file_hash_and_size(tmp_path / "ghost.bin")


def test_large_file_processed_incrementally(tmp_path):
    # File larger than the 65536-byte chunk size — must still produce correct hash.
    content = b"X" * (65536 * 3 + 1)
    f = tmp_path / "large.bin"
    f.write_bytes(content)
    sha, size = compute_file_hash_and_size(f)
    assert sha == _sha256(content)
    assert size == len(content)


def test_size_matches_file_byte_count(tmp_path):
    content = b"\x00\xff" * 512
    f = tmp_path / "mixed.bin"
    f.write_bytes(content)
    _, size = compute_file_hash_and_size(f)
    assert size == len(content)
