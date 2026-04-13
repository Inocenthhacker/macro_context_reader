"""Apply standardized CELL-<NN> IDs to all notebooks.

Protocol:
- Code cells: first line is `# CELL-<NN>` (after shebang if any, but notebooks don't have shebangs)
- Markdown cells: first line is `<!-- CELL-<NN> -->`
- Numbering: 0-indexed, zero-padded to 2 digits, sequential in notebook order
- Idempotent: existing correct IDs are preserved; wrong/missing IDs are corrected/added
- Bootstrap cells (containing `# Idempotent environment bootstrap` marker) keep their
  content after the CELL ID line

Usage:
    python scripts/apply_cell_ids.py              # apply to all notebooks in notebooks/
    python scripts/apply_cell_ids.py --dry-run    # show changes without writing
    python scripts/apply_cell_ids.py path/to/nb.ipynb  # apply to specific notebook
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import nbformat

CODE_ID_PATTERN = re.compile(r"^#\s*CELL-(\d{2,})\s*$")
MARKDOWN_ID_PATTERN = re.compile(r"^<!--\s*CELL-(\d{2,})\s*-->\s*$")

MAX_CELLS = 100  # notebooks >99 cells are a red flag


def _strip_existing_id(source: str, pattern: re.Pattern[str]) -> str:
    """Remove existing CELL-NN line if present as first non-empty line."""
    lines = source.split("\n")
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        if pattern.match(line):
            remainder = lines[i + 1 :]
            if remainder and remainder[0].strip() == "":
                remainder = remainder[1:]
            return "\n".join(remainder)
        break
    return source


def apply_ids_to_notebook(nb_path: Path, dry_run: bool = False) -> dict:
    """Apply CELL-NN IDs to all cells. Returns summary dict."""
    nb = nbformat.read(nb_path, as_version=4)

    if len(nb.cells) >= MAX_CELLS:
        raise ValueError(
            f"{nb_path.name} has {len(nb.cells)} cells (>={MAX_CELLS}). "
            "This is a red flag — split the notebook before applying IDs."
        )

    changed = 0
    skipped = 0

    for idx, cell in enumerate(nb.cells):
        cell_id = f"{idx:02d}"
        original_source = cell.source

        if cell.cell_type == "code":
            stripped = _strip_existing_id(original_source, CODE_ID_PATTERN)
            new_source = f"# CELL-{cell_id}\n{stripped}" if stripped.strip() else f"# CELL-{cell_id}\n"
        elif cell.cell_type == "markdown":
            stripped = _strip_existing_id(original_source, MARKDOWN_ID_PATTERN)
            new_source = f"<!-- CELL-{cell_id} -->\n{stripped}" if stripped.strip() else f"<!-- CELL-{cell_id} -->\n"
        else:
            skipped += 1
            continue

        if new_source != original_source:
            cell.source = new_source
            changed += 1

    if not dry_run and changed > 0:
        nbformat.write(nb, nb_path)

    return {
        "path": nb_path,
        "total_cells": len(nb.cells),
        "changed": changed,
        "skipped_raw": skipped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths", nargs="*", type=Path,
        help="Specific notebooks (default: all in notebooks/)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = parser.parse_args()

    if args.paths:
        targets = args.paths
    else:
        notebooks_dir = Path("notebooks")
        if not notebooks_dir.exists():
            print(f"ERROR: {notebooks_dir} does not exist", file=sys.stderr)
            return 1
        targets = sorted(
            p for p in notebooks_dir.rglob("*.ipynb")
            if ".ipynb_checkpoints" not in p.parts
        )

    if not targets:
        print("No notebooks found.")
        return 0

    print(f"Processing {len(targets)} notebook(s){' (DRY RUN)' if args.dry_run else ''}:\n")
    total_changed_cells = 0
    total_changed_notebooks = 0

    for nb_path in targets:
        result = apply_ids_to_notebook(nb_path, dry_run=args.dry_run)
        status = "+" if result["changed"] > 0 else "="
        print(
            f"  {status} {result['path'].name}: "
            f"{result['changed']}/{result['total_cells']} cells updated"
            + (f", {result['skipped_raw']} raw skipped" if result["skipped_raw"] else "")
        )
        if result["changed"] > 0:
            total_changed_cells += result["changed"]
            total_changed_notebooks += 1

    print(f"\nSummary: {total_changed_cells} cells updated across {total_changed_notebooks}/{len(targets)} notebooks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
