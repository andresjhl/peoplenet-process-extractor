from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "check_local_environment.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("check_local_environment", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_missing_environment_variable_fails() -> None:
    module = _load_script_module()

    check = module.check_environment({})

    assert not check.ok
    assert check.root is None
    assert "not defined" in check.errors[0]


def test_nonexistent_path_fails(tmp_path: Path) -> None:
    module = _load_script_module()
    missing = tmp_path / "missing"

    check = module.check_environment({module.ENV_VAR: str(missing)})

    assert not check.ok
    assert check.exists is False
    assert check.is_directory is False


def test_file_path_fails(tmp_path: Path) -> None:
    module = _load_script_module()
    file_path = tmp_path / "corpus.txt"
    file_path.write_text("not a directory")

    check = module.check_environment({module.ENV_VAR: str(file_path)})

    assert not check.ok
    assert check.exists is True
    assert check.is_directory is False


def test_valid_directory_passes(tmp_path: Path) -> None:
    module = _load_script_module()

    check = module.check_environment({module.ENV_VAR: str(tmp_path)})

    assert check.ok
    assert check.exists is True
    assert check.is_directory is True


def test_check_does_not_write_to_corpus(tmp_path: Path) -> None:
    module = _load_script_module()
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("unchanged")
    before = sorted(path.name for path in tmp_path.iterdir())

    check = module.check_environment({module.ENV_VAR: str(tmp_path)})

    after = sorted(path.name for path in tmp_path.iterdir())
    assert check.ok
    assert after == before
    assert existing_file.read_text() == "unchanged"
