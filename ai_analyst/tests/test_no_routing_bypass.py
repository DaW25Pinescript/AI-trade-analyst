"""Guard test: verify call sites do not bypass routing.

This test scans analyst_nodes.py and arbiter_node.py to confirm that
no direct resolve_profile().model access exists — all model/provider
resolution must go through resolve_profile_route() or resolve_task_route().

This prevents regression to the pre-centralisation pattern where call sites
assembled routing parameters themselves.
"""
import ast
from pathlib import Path

import pytest


_GRAPH_DIR = Path(__file__).resolve().parent.parent / "graph"
_ANALYST_NODES = _GRAPH_DIR / "analyst_nodes.py"
_ARBITER_NODE = _GRAPH_DIR / "arbiter_node.py"


def _find_resolve_profile_calls(filepath: Path) -> list[int]:
    """Return line numbers where resolve_profile() is called (not resolve_profile_route)."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # Direct call: resolve_profile(...)
            if isinstance(func, ast.Name) and func.id == "resolve_profile":
                violations.append(node.lineno)
            # Attribute call: module.resolve_profile(...)
            if isinstance(func, ast.Attribute) and func.attr == "resolve_profile":
                violations.append(node.lineno)
    return violations


def _find_direct_model_profile_imports(filepath: Path) -> list[str]:
    """Return import lines that import resolve_profile from model_profiles."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(filepath))
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and "model_profiles" in node.module:
                for alias in node.names:
                    if alias.name == "resolve_profile":
                        violations.append(
                            f"line {node.lineno}: from {node.module} import resolve_profile"
                        )
    return violations


class TestNoRoutingBypass:
    """Ensure call sites use resolved routes, not direct profile lookups."""

    def test_analyst_nodes_no_resolve_profile_calls(self):
        violations = _find_resolve_profile_calls(_ANALYST_NODES)
        assert not violations, (
            f"analyst_nodes.py still calls resolve_profile() directly at lines: {violations}. "
            "Use resolve_profile_route() instead."
        )

    def test_arbiter_node_no_resolve_profile_calls(self):
        violations = _find_resolve_profile_calls(_ARBITER_NODE)
        assert not violations, (
            f"arbiter_node.py still calls resolve_profile() directly at lines: {violations}. "
            "Use resolve_task_route() or resolve_profile_route() instead."
        )

    def test_analyst_nodes_no_model_profiles_import(self):
        violations = _find_direct_model_profile_imports(_ANALYST_NODES)
        assert not violations, (
            f"analyst_nodes.py imports resolve_profile from model_profiles: {violations}. "
            "Import resolve_profile_route from router instead."
        )

    def test_arbiter_node_no_model_profiles_import(self):
        violations = _find_direct_model_profile_imports(_ARBITER_NODE)
        assert not violations, (
            f"arbiter_node.py imports resolve_profile from model_profiles: {violations}. "
            "Import resolve_task_route from router instead."
        )
