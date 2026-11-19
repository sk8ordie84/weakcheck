#!/usr/bin/env python3
"""weakcheck: flag Python tests that got weaker between two versions of a repository.

Prototype. Compares test functions in test files between a commit and its first
parent and reports:

  flagged (weaker)
    removed_test             a test present before is absent after
    new_unconditional_skip   a test gains an unconditional skip or expected failure
    fewer_assertions         a test has fewer assertions than before
    tolerance_loosened       a numeric tolerance argument now accepts more

  listed separately (not flagged)
    new_conditional_skip     a test gains a skip that depends on a condition

It is a static comparison of source files, not a proof. See EXPECTED.md for the
definitions and known limits. MIT licence.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field

TEST_FILE = re.compile(r"(^|/)(test_[^/]*|[^/]*_test)\.py$")
LOOSER_IF_LARGER = {"rtol", "atol", "rel", "abs", "delta"}
LOOSER_IF_SMALLER = {"places", "decimal"}
SEVERITY = {"none": 0, "conditional": 1, "unconditional": 2}


@dataclass
class TestInfo:
    assertions: int = 0
    skip: str = "none"  # none | conditional | unconditional
    tolerances: dict = field(default_factory=dict)  # kw -> list of numbers


def dotted(node: ast.AST) -> str:
    """Dotted name of a Name/Attribute/Call target, e.g. 'pytest.mark.skipif'."""
    if isinstance(node, ast.Call):
        node = node.func
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def decorator_skip(dec: ast.AST) -> str:
    name = dotted(dec)
    last = name.rsplit(".", 1)[-1]
    if name.endswith("mark.skipif") or last in ("skipIf", "skipUnless"):
        return "conditional"
    if name.endswith("mark.xfail"):
        if isinstance(dec, ast.Call) and (dec.args or any(k.arg == "condition" for k in dec.keywords)):
            return "conditional"
        return "unconditional"
    if name.endswith("mark.skip") or last in ("skip", "expectedFailure"):
        return "unconditional"
    return "none"


def worst(*levels: str) -> str:
    return max(levels, key=lambda s: SEVERITY[s]) if levels else "none"


def number(node: ast.AST):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = number(node.operand)
        return -v if v is not None else None
    return None


class BodyScan(ast.NodeVisitor):
    """Collect assertions, skip calls and tolerance keywords inside one test function."""

    def __init__(self):
        self.info = TestInfo()
        self.if_depth = 0

    def visit_If(self, node):
        self.if_depth += 1
        self.generic_visit(node)
        self.if_depth -= 1

    def visit_Assert(self, node):
        self.info.assertions += 1
        self.generic_visit(node)

    def visit_Raise(self, node):
        if node.exc is not None and dotted(node.exc).rsplit(".", 1)[-1] == "SkipTest":
            self._skip()
        self.generic_visit(node)

    def visit_Call(self, node):
        name = dotted(node)
        last = name.rsplit(".", 1)[-1]
        if last.startswith("assert") or name in ("pytest.raises", "pytest.warns"):
            self.info.assertions += 1
        if name in ("pytest.skip", "pytest.xfail") or last == "skipTest":
            self._skip()
        if name == "pytest.importorskip":
            self.info.skip = worst(self.info.skip, "conditional")
        for kw in node.keywords:
            if kw.arg in LOOSER_IF_LARGER | LOOSER_IF_SMALLER:
                v = number(kw.value)
                if v is not None:
                    self.info.tolerances.setdefault(kw.arg, []).append(v)
        self.generic_visit(node)

    def _skip(self):
        self.info.skip = worst(self.info.skip, "conditional" if self.if_depth else "unconditional")


def module_skip(tree: ast.Module) -> str:
    """Skip level from a module-level `pytestmark = ...` assignment."""
    level = "none"
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
            values = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else [node.value]
            level = worst(level, *(decorator_skip(v) for v in values))
    return level


def extract(source: str) -> dict[str, TestInfo]:
    """Map 'Class.test_name' (or 'test_name') to TestInfo. Raises SyntaxError."""
    tree = ast.parse(source)
    tests: dict[str, TestInfo] = {}
    base_skip = module_skip(tree)

    def walk(body, prefix, inherited):
        for node in body:
            if isinstance(node, ast.ClassDef):
                level = worst(inherited, *(decorator_skip(d) for d in node.decorator_list))
                walk(node.body, prefix + node.name + ".", level)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                scan = BodyScan()
                for stmt in node.body:
                    scan.visit(stmt)
                info = scan.info
                info.skip = worst(info.skip, inherited, *(decorator_skip(d) for d in node.decorator_list))
                tests[prefix + node.name] = info

    walk(tree.body, "", base_skip)
    return tests


def compare(before: dict[str, TestInfo], after: dict[str, TestInfo]):
    """Return (flags, conditional_skips) for one file."""
    flags, conditional = [], []
    for name, old in before.items():
        new = after.get(name)
        if new is None:
            flags.append({"type": "removed_test", "test": name})
            continue
        if SEVERITY[new.skip] > SEVERITY[old.skip]:
            if new.skip == "unconditional":
                flags.append({"type": "new_unconditional_skip", "test": name, "detail": f"{old.skip} -> unconditional"})
            else:
                conditional.append({"type": "new_conditional_skip", "test": name})
        if new.assertions < old.assertions:
            flags.append({"type": "fewer_assertions", "test": name, "detail": f"{old.assertions} -> {new.assertions}"})
        for kw in set(old.tolerances) & set(new.tolerances):
            o, n = old.tolerances[kw], new.tolerances[kw]
            looser = max(n) > max(o) if kw in LOOSER_IF_LARGER else min(n) < min(o)
            if looser:
                flags.append({"type": "tolerance_loosened", "test": name, "detail": f"{kw}: {o} -> {n}"})
    return flags, conditional


def compare_sources(before_src: str | None, after_src: str | None):
    before = extract(before_src) if before_src else {}
    after = extract(after_src) if after_src else {}
    return compare(before, after)


# ---------- git ----------

def git(repo: str, *args: str) -> str:
    return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True).stdout


def show(repo: str, rev: str, path: str) -> str | None:
    r = subprocess.run(["git", "-C", repo, "show", f"{rev}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def diff_commits(repo: str, base: str, head: str):
    """Compare all changed test files between two revisions. Returns a result dict."""
    paths = [p for p in git(repo, "diff", "--no-renames", "--name-only", base, head).splitlines() if TEST_FILE.search(p)]
    out = {"files": len(paths), "flags": [], "conditional_skips": [], "parse_failures": []}
    for path in paths:
        try:
            flags, cond = compare_sources(show(repo, base, path), show(repo, head, path))
        except (SyntaxError, ValueError) as e:
            out["parse_failures"].append({"file": path, "error": type(e).__name__})
            continue
        for item in flags:
            out["flags"].append({"file": path, **item})
        for item in cond:
            out["conditional_skips"].append({"file": path, **item})
    return out


def history(repo: str, branch: str):
    commits = git(repo, "rev-list", "--first-parent", "--reverse", branch).split()
    report = {"repo": repo, "branch": branch, "commits_scanned": 0, "commits_touching_tests": 0,
              "parse_failures": [], "flags": [], "conditional_skips": []}
    for sha in commits:
        parents = git(repo, "rev-list", "--parents", "-n", "1", sha).split()[1:]
        if not parents:
            continue
        report["commits_scanned"] += 1
        res = diff_commits(repo, parents[0], sha)
        if res["files"]:
            report["commits_touching_tests"] += 1
        meta = git(repo, "show", "-s", "--format=%h%x09%ad%x09%s", "--date=short", sha).strip().split("\t", 2)
        tag = {"commit": meta[0], "date": meta[1], "subject": meta[2][:100]}
        for key in ("flags", "conditional_skips", "parse_failures"):
            report[key] += [{**tag, **item} for item in res[key]]
    counts = {}
    for f in report["flags"]:
        counts[f["type"]] = counts.get(f["type"], 0) + 1
    report["flag_counts"] = counts
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("diff", help="compare two revisions")
    d.add_argument("repo"); d.add_argument("base"); d.add_argument("head")
    h = sub.add_parser("history", help="compare every first-parent commit with its parent")
    h.add_argument("repo"); h.add_argument("--branch", default="main")
    args = ap.parse_args(argv)
    result = diff_commits(args.repo, args.base, args.head) if args.cmd == "diff" else history(args.repo, args.branch)
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    print()
    return 1 if result["flags"] else 0


if __name__ == "__main__":
    sys.exit(main())
