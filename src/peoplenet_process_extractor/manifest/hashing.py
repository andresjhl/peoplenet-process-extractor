import hashlib
from pathlib import Path

_CHUNK = 65536


def compute_file_hash_and_size(path: Path) -> tuple[str, int]:
    """Return (sha256_hex, size_bytes) reading the file incrementally without loading it all."""
    hasher = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size
