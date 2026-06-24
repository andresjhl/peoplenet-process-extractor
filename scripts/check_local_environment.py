"""Check machine-local environment required for external PeopleNet corpus access."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


ENV_VAR = "PEOPLENET_CORPUS_ROOT"


@dataclass(frozen=True)
class EnvironmentCheck:
    root: str | None
    exists: bool | None
    is_directory: bool | None
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def check_environment(environ: Mapping[str, str] | None = None) -> EnvironmentCheck:
    env = os.environ if environ is None else environ
    root = env.get(ENV_VAR)

    if not root:
        return EnvironmentCheck(
            root=None,
            exists=None,
            is_directory=None,
            errors=(f"{ENV_VAR} is not defined",),
        )

    corpus_path = Path(root)
    exists = corpus_path.exists()
    is_directory = corpus_path.is_dir() if exists else False
    errors: list[str] = []

    if not exists:
        errors.append("Corpus path does not exist")
    elif not is_directory:
        errors.append("Corpus path is not a directory")

    return EnvironmentCheck(
        root=root,
        exists=exists,
        is_directory=is_directory,
        errors=tuple(errors),
    )


def _yes_no(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "yes" if value else "no"


def render_check(check: EnvironmentCheck) -> str:
    lines = [f"{ENV_VAR}: {check.root if check.root else '<not set>'}"]

    if check.root:
        lines.append(f"Corpus exists: {_yes_no(check.exists)}")
        lines.append(f"Corpus is directory: {_yes_no(check.is_directory)}")

    lines.append(f"Environment check: {'OK' if check.ok else 'FAILED'}")
    lines.extend(f"Error: {error}" for error in check.errors)
    return "\n".join(lines)


def main() -> int:
    check = check_environment()
    print(render_check(check))
    return 0 if check.ok else 1


if __name__ == "__main__":
    sys.exit(main())
