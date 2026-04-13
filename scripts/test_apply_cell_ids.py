"""Smoke tests for apply_cell_ids.py — idempotency + correctness."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import nbformat
import pytest

from scripts.apply_cell_ids import apply_ids_to_notebook


def _make_nb(cells_spec: list[tuple[str, str]]) -> Path:
    """Create temp notebook from list of (type, source) tuples."""
    nb = nbformat.v4.new_notebook()
    for cell_type, source in cells_spec:
        if cell_type == "code":
            nb.cells.append(nbformat.v4.new_code_cell(source))
        elif cell_type == "markdown":
            nb.cells.append(nbformat.v4.new_markdown_cell(source))
    tmp = tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False, mode="w")
    nbformat.write(nb, tmp)
    tmp.close()
    return Path(tmp.name)


def test_adds_ids_to_clean_notebook():
    nb_path = _make_nb([
        ("markdown", "# Header"),
        ("code", "x = 1"),
        ("code", "print(x)"),
    ])
    apply_ids_to_notebook(nb_path)
    nb = nbformat.read(nb_path, as_version=4)
    assert nb.cells[0].source.startswith("<!-- CELL-00 -->")
    assert nb.cells[1].source.startswith("# CELL-01")
    assert nb.cells[2].source.startswith("# CELL-02")


def test_idempotent():
    nb_path = _make_nb([("code", "# CELL-00\nx = 1")])
    apply_ids_to_notebook(nb_path)
    result = apply_ids_to_notebook(nb_path)
    assert result["changed"] == 0


def test_corrects_wrong_id():
    nb_path = _make_nb([("code", "# CELL-05\nx = 1")])
    apply_ids_to_notebook(nb_path)
    nb = nbformat.read(nb_path, as_version=4)
    assert nb.cells[0].source.startswith("# CELL-00")
    assert "CELL-05" not in nb.cells[0].source


def test_preserves_bootstrap_content():
    bootstrap = "# Idempotent environment bootstrap\nimport os\nprint('ok')"
    nb_path = _make_nb([("code", bootstrap)])
    apply_ids_to_notebook(nb_path)
    nb = nbformat.read(nb_path, as_version=4)
    assert nb.cells[0].source == f"# CELL-00\n{bootstrap}"


def test_markdown_id():
    nb_path = _make_nb([("markdown", "# Title\nSome text")])
    apply_ids_to_notebook(nb_path)
    nb = nbformat.read(nb_path, as_version=4)
    assert nb.cells[0].source == "<!-- CELL-00 -->\n# Title\nSome text"


def test_corrects_shifted_markdown_id():
    nb_path = _make_nb([
        ("markdown", "<!-- CELL-03 -->\n# Title"),
        ("code", "# CELL-07\nx = 1"),
    ])
    apply_ids_to_notebook(nb_path)
    nb = nbformat.read(nb_path, as_version=4)
    assert nb.cells[0].source.startswith("<!-- CELL-00 -->")
    assert nb.cells[1].source.startswith("# CELL-01")
    assert "CELL-03" not in nb.cells[0].source
    assert "CELL-07" not in nb.cells[1].source


def test_dry_run_does_not_write():
    nb_path = _make_nb([("code", "x = 1")])
    result = apply_ids_to_notebook(nb_path, dry_run=True)
    assert result["changed"] == 1
    # File should be unchanged
    nb = nbformat.read(nb_path, as_version=4)
    assert not nb.cells[0].source.startswith("# CELL-00")
