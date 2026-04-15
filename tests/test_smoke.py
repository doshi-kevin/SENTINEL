"""
Minimal smoke tests — verify the package is structurally sound without
requiring heavy ML dependencies (torch, torch-geometric) to be installed.

These tests check:
  1. Every subpackage directory exists with an __init__.py
  2. Every .py file under src/ parses (no syntax errors)
  3. The pure-Python modules (no torch/sklearn) actually import
"""
from __future__ import annotations

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "sentinel_z"

EXPECTED_SUBPACKAGES = [
    "pipeline",
    "ingestion",
    "encoder",
    "detection",
    "narrative",
    "realtime",
    "api",
]


def test_subpackages_exist():
    for name in EXPECTED_SUBPACKAGES:
        sub = SRC / name
        assert sub.is_dir(), f"missing subpackage: {sub}"
        assert (sub / "__init__.py").is_file(), f"missing __init__.py in {sub}"


def test_all_python_files_parse():
    failures: list[tuple[pathlib.Path, str]] = []
    py_files = list((REPO_ROOT / "src").rglob("*.py"))
    assert py_files, "no python files found under src/"
    for p in py_files:
        try:
            ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            failures.append((p, str(exc)))
    assert not failures, "syntax errors:\n" + "\n".join(f"  {p}: {e}" for p, e in failures)


def test_scripts_parse():
    """Every .py under scripts/ must AST-parse — keeps bootstrap scripts honest."""
    failures: list[tuple[pathlib.Path, str]] = []
    py_files = list((REPO_ROOT / "scripts").rglob("*.py"))
    assert py_files, "no python files found under scripts/"
    for p in py_files:
        try:
            ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            failures.append((p, str(exc)))
    assert not failures, "scripts/ syntax errors:\n" + "\n".join(
        f"  {p}: {e}" for p, e in failures
    )


def test_realtime_event_buffer_imports():
    """event_buffer.py is pure-stdlib — must import without any optional deps."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "src"))
    try:
        from sentinel_z.realtime.event_buffer import EventBuffer

        buf = EventBuffer(window_size=1.0)
        assert buf.get_window() == []
    finally:
        sys.path.pop(0)
