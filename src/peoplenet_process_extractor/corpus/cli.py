import argparse
import sys
from pathlib import Path

from .service import create_inventory, verify_corpus


def register_corpus_subparser(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    corpus = sub.add_parser("corpus", help="Corpus inventory commands")
    corpus_sub = corpus.add_subparsers(dest="corpus_command", required=True)

    # corpus inventory
    inv = corpus_sub.add_parser(
        "inventory",
        help="Build a versioned inventory of a corpus directory",
    )
    inv.add_argument(
        "--corpus-root",
        dest="corpus_root",
        required=True,
        help="Absolute path to the corpus directory (not stored in the manifest).",
    )
    inv.add_argument(
        "--output",
        "-o",
        required=True,
        help="Output path for corpus-manifest.json.",
    )
    inv.add_argument(
        "--corpus-id",
        dest="corpus_id",
        help="Corpus identifier (default: derived from directory name).",
    )
    inv.add_argument(
        "--source-root",
        dest="source_roots",
        action="append",
        metavar="NAME",
        help=(
            "Include only this first-level source root. "
            "Repeatable. Duplicates are normalized (equivalent to specifying once). "
            "If omitted, all roots are discovered."
        ),
    )
    inv.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output file.",
    )

    # corpus verify
    ver = corpus_sub.add_parser(
        "verify",
        help="Verify a corpus against a previously generated manifest",
    )
    ver.add_argument(
        "--corpus-root",
        dest="corpus_root",
        required=True,
        help="Absolute path to the corpus directory.",
    )
    ver.add_argument(
        "manifest",
        help="Path to the corpus-manifest.json to verify against.",
    )


def cmd_corpus_inventory(args: argparse.Namespace) -> int:
    corpus_root = Path(args.corpus_root)
    output_path = Path(args.output)
    source_roots: list[str] | None = args.source_roots

    exit_code, messages = create_inventory(
        corpus_root=corpus_root,
        output_path=output_path,
        corpus_id=getattr(args, "corpus_id", None),
        source_roots=source_roots,
        force=args.force,
    )

    stream = sys.stdout if exit_code == 0 else sys.stderr
    for msg in messages:
        if msg.startswith("Error:"):
            print(msg, file=sys.stderr)
        elif msg.startswith("  Warning:"):
            print(msg, file=sys.stderr)
        else:
            print(msg, file=stream)

    return exit_code


def cmd_corpus_verify(args: argparse.Namespace) -> int:
    corpus_root = Path(args.corpus_root)
    manifest_path = Path(args.manifest)

    exit_code, _diff, messages = verify_corpus(
        corpus_root=corpus_root,
        manifest_path=manifest_path,
    )

    stream = sys.stdout if exit_code == 0 else sys.stderr
    for msg in messages:
        if msg.startswith("Error:") or msg.startswith("Validation error"):
            print(msg, file=sys.stderr)
        elif msg.startswith("Warning:"):
            print(msg, file=sys.stderr)
        else:
            print(msg, file=stream)

    return exit_code
