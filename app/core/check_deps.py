"""
Core dependency checker

This module enforces the architecture boundary between core and services layers.

Rules:
- app.core modules cannot import app.services
- Core should only depend on standard libraries and configuration
"""

import ast
import os
from pathlib import Path
from typing import List, Tuple


def check_core_imports(project_root: Path = Path(".")) -> tuple[bool, list[str]]:
    """
    Check that no core modules import from services layer.

    Args:
        project_root: Root of the project

    Returns:
        Tuple of (is_valid, error_messages)
    """
    core_dir = project_root / "app" / "core"
    errors: list[str] = []

    for py_file in core_dir.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue

        errors.extend(_check_file_imports(py_file, core_dir, project_root))

    return len(errors) == 0, errors


def _check_file_imports(
    file_path: Path, core_dir: Path, project_root: Path
) -> list[str]:
    """Check a single Python file for disallowed core->services imports."""
    errors: list[str] = []

    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_services_import(alias.name, core_dir, project_root):
                        errors.append(
                            f"{file_path.relative_to(project_root)}: "
                            f"Core module imports from services: {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                module = node.module
                if module and _is_services_import(module, core_dir, project_root):
                    errors.append(
                        f"{file_path.relative_to(project_root)}: "
                        f"Core module imports from services: from {module}"
                    )

    except SyntaxError as e:
        errors.append(f"{file_path.relative_to(project_root)}: Syntax error - {e}")

    return errors


def _is_services_import(import_name: str, core_dir: Path, project_root: Path) -> bool:
    """Check if an import comes from the services layer."""
    # Normalize import name
    normalized = import_name.replace(".", "/")

    # If module starts with 'app.services', it's from services layer
    return normalized.startswith("app/services") or import_name.startswith(
        "app.services"
    )
