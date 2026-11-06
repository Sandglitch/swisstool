"""Output file naming and collision resolution helpers."""
from __future__ import annotations

from pathlib import Path


def make_output_path(
    source: Path,
    out_dir: Path | None = None,
    suffix: str = "",
    ext: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Generate a safe, collision-free destination path.
    
    Args:
        source: Original file path.
        out_dir: Target directory. If None, uses source.parent.
        suffix: Optional suffix appended to stem (e.g. '_resized').
        ext: Optional new extension (with or without dot). If None, keeps source.suffix.
        overwrite: If True, do not append numeric collision counter if file exists.
    """
    dest_dir = out_dir if out_dir is not None else source.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    if ext is not None:
        new_ext = ext if ext.startswith(".") else f".{ext}"
    else:
        new_ext = source.suffix

    base_stem = f"{source.stem}{suffix}"
    candidate = dest_dir / f"{base_stem}{new_ext}"

    if overwrite or not candidate.exists():
        return candidate

    counter = 2
    while True:
        candidate = dest_dir / f"{base_stem} ({counter}){new_ext}"
        if not candidate.exists():
            return candidate
        counter += 1

