"""Workspace path sandboxing — prevent directory traversal.

Extracted from AutoGPT workspace.py.
Use in RAZ-Core's ingestor.py to ensure file operations stay inside
the allowed workspace directory.
"""

from pathlib import Path


def safe_path_join(base: str | Path, *paths: str | Path) -> Path:
    """Join path components, raising ValueError if result escapes base.

    Args:
        base: The trusted root directory.
        *paths: Relative path components to join.

    Returns:
        Resolved absolute path guaranteed to be under base.

    Raises:
        ValueError: If the resolved path is outside base.
    """
    base = Path(base).resolve()
    joined = base.joinpath(*paths).resolve()
    if not joined.is_relative_to(base):
        raise ValueError(
            f"Path traversal blocked: '{joined}' is outside workspace '{base}'"
        )
    return joined
