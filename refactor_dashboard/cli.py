"""Command line interface: refactor a file with the same Ollama setup as the dashboard.

Examples:
    refactor myfile.py
    refactor myfile.py -i "add type hints" --write
    refactor myfile.py --diff
    refactor --history
    refactor --show 12
"""

import argparse
import asyncio
import difflib
import sys
from pathlib import Path

from . import __version__
from .config import get_settings
from .history import HistoryStore
from .languages import detect_language
from .ollama import OllamaClient
from .prompts import build_refactor_prompt, split_code_and_summary
from .schemas import DEFAULT_INSTRUCTION


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="refactor",
        description="Refactor a source file with your local Ollama model.",
    )
    p.add_argument("file", nargs="?", help="file to refactor (use - for stdin)")
    p.add_argument("-i", "--instruction", default=DEFAULT_INSTRUCTION, help="what to change")
    p.add_argument("-l", "--language", help="language name (guessed from the file extension by default)")
    p.add_argument("-m", "--model", help="Ollama model (defaults to OLLAMA_MODEL)")
    out = p.add_mutually_exclusive_group()
    out.add_argument("-w", "--write", action="store_true", help="overwrite the file with the result")
    out.add_argument("-o", "--output", help="write the result to this file")
    out.add_argument("-d", "--diff", action="store_true", help="print a unified diff instead of the code")
    p.add_argument("-q", "--quiet", action="store_true", help="don't print the summary")
    p.add_argument("--no-history", action="store_true", help="don't save this run to the local history")
    p.add_argument("--history", nargs="?", const=20, type=int, metavar="N", help="list the last N refactors")
    p.add_argument("--show", type=int, metavar="ID", help="print a past refactor's code and summary")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _print_history(store: HistoryStore, limit: int) -> int:
    rows = store.list(limit=limit)
    if not rows:
        print("No refactors saved yet.")
        return 0
    for row in rows:
        name = row["filename"] or "(pasted)"
        print(f"{row['id']:>5}  {row['created_at']}  {row['source']:<3}  {name}  - {row['instruction']}")
    return 0


def _show(store: HistoryStore, entry_id: int) -> int:
    entry = store.get(entry_id)
    if entry is None:
        print(f"No refactor with id {entry_id}.", file=sys.stderr)
        return 1
    print(entry.refactored_code)
    if entry.summary:
        print(f"\n--- What changed ---\n{entry.summary}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = get_settings()

    if args.history is not None or args.show is not None:
        store = HistoryStore(settings.history_db_path)
        return _show(store, args.show) if args.show is not None else _print_history(store, args.history)

    if not args.file:
        _parser().error("a file is required (or use --history / --show)")

    if args.file == "-":
        original, filename = sys.stdin.read(), None
    else:
        path = Path(args.file)
        if not path.is_file():
            print(f"refactor: {path} is not a file", file=sys.stderr)
            return 1
        original, filename = path.read_text(encoding="utf-8"), path.name
    if args.write and filename is None:
        print("refactor: --write needs a file, not stdin", file=sys.stderr)
        return 1
    language = args.language or detect_language(filename or "", default="python")

    if not args.quiet:
        print(
            f"Refactoring {filename or 'stdin'} ({language}) with {args.model or settings.ollama_model}...",
            file=sys.stderr,
        )
    try:
        raw = asyncio.run(
            OllamaClient(settings).generate(
                build_refactor_prompt(original, language, args.instruction), model=args.model
            )
        )
    except Exception as e:  # OllamaError, connection refused, timeouts
        print(f"refactor: {e or type(e).__name__}", file=sys.stderr)
        return 1
    code, summary = split_code_and_summary(raw)

    if settings.history_enabled and not args.no_history:
        entry_id = HistoryStore(settings.history_db_path).add(
            source="cli",
            filename=str(Path(args.file).resolve()) if filename else None,
            language=language,
            instruction=args.instruction,
            model=args.model or settings.ollama_model,
            original_code=original,
            refactored_code=code,
            summary=summary,
        )
    else:
        entry_id = None

    if args.write:
        Path(args.file).write_text(code.rstrip("\n") + "\n", encoding="utf-8")
    elif args.output:
        Path(args.output).write_text(code.rstrip("\n") + "\n", encoding="utf-8")
    elif args.diff:
        name = filename or "stdin"
        sys.stdout.writelines(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                (code.rstrip("\n") + "\n").splitlines(keepends=True),
                fromfile=f"a/{name}",
                tofile=f"b/{name}",
            )
        )
    else:
        print(code)

    if not args.quiet:
        if summary:
            print(f"\n--- What changed ---\n{summary}", file=sys.stderr)
        if args.write:
            print(f"\nWrote {args.file}.", file=sys.stderr)
        elif args.output:
            print(f"\nWrote {args.output}.", file=sys.stderr)
        if entry_id is not None:
            print(f"Saved to history as #{entry_id} (refactor --show {entry_id}).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
