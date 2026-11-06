"""Core contracts and declarative parameter schema for SwissKnife tools."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .naming import make_output_path


class ToolError(Exception):
    """User-facing error, displayed cleanly in the UI."""


class CancelledError(Exception):
    """Raised when an operation is cancelled by the user."""


# -----------------------------------------------------------------------------
# Categories
# -----------------------------------------------------------------------------

class Category:
    IMAGES = "images"
    PDF = "pdf"
    OFFICE = "office"
    FILES = "files"
    MEDIA = "media"
    OCR = "ocr"
    DATA = "data"
    DEV = "dev"


CATEGORY_META = [
    (Category.IMAGES, "Images"),
    (Category.PDF, "PDF"),
    (Category.OFFICE, "Office"),
    (Category.FILES, "Files & Disk"),
    (Category.MEDIA, "Audio & Video"),
    (Category.OCR, "OCR"),
    (Category.DATA, "Text & Data"),
    (Category.DEV, "Developer"),
]


# -----------------------------------------------------------------------------
# Declarative Parameter Schema
# -----------------------------------------------------------------------------

@dataclass
class Param:
    key: str
    label: str
    kind: str = "text"  # text | multiline | int | float | bool | choice | color
    default: Any = None
    choices: list[Any] = field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    suffix: str = ""
    placeholder: str = ""
    help: str = ""


def Choice(key: str, label: str, choices: list[Any], default: Any = None, help: str = "") -> Param:
    default_val = choices[0] if default is None and choices else default
    return Param(key=key, label=label, kind="choice", default=default_val, choices=list(choices), help=help)


def Int(key: str, label: str, default: int = 0, minimum: int = 0, maximum: int = 1_000_000,
        step: int = 1, suffix: str = "", help: str = "") -> Param:
    return Param(key=key, label=label, kind="int", default=default, minimum=minimum,
                 maximum=maximum, step=step, suffix=suffix, help=help)


def Float(key: str, label: str, default: float = 0.0, minimum: float = 0.0, maximum: float = 1_000_000.0,
          step: float = 0.1, suffix: str = "", help: str = "") -> Param:
    return Param(key=key, label=label, kind="float", default=default, minimum=minimum,
                 maximum=maximum, step=step, suffix=suffix, help=help)


def Bool(key: str, label: str, default: bool = False, help: str = "") -> Param:
    return Param(key=key, label=label, kind="bool", default=default, help=help)


def Text(key: str, label: str, default: str = "", placeholder: str = "", help: str = "") -> Param:
    return Param(key=key, label=label, kind="text", default=default, placeholder=placeholder, help=help)


def Multiline(key: str, label: str, default: str = "", placeholder: str = "", help: str = "") -> Param:
    return Param(key=key, label=label, kind="multiline", default=default, placeholder=placeholder, help=help)


def Color(key: str, label: str, default: str = "#000000", help: str = "") -> Param:
    return Param(key=key, label=label, kind="color", default=default, help=help)


# -----------------------------------------------------------------------------
# Results and Job Context
# -----------------------------------------------------------------------------

@dataclass
class RunResult:
    outputs: list[Path] = field(default_factory=list)
    text: str = ""
    message: str = ""


class JobContext:
    """Execution context passed to a tool during run() or plan()."""

    def __init__(
        self,
        cancel_event: threading.Event | None = None,
        progress_cb=None,
        log_cb=None,
        out_dir: Path | None = None,
        overwrite: bool = False,
    ):
        self._cancel_event = cancel_event or threading.Event()
        self._progress_cb = progress_cb or (lambda done, total, msg: None)
        self._log_cb = log_cb or (lambda msg: None)
        self.out_dir = out_dir
        self.overwrite = overwrite
        self.outputs: list[Path] = []

    def progress(self, done: int, total: int, label: str = "") -> None:
        self._progress_cb(done, total, label)

    def log(self, message: str) -> None:
        self._log_cb(message)

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def check_cancelled(self) -> None:
        if self._cancel_event.is_set():
            raise CancelledError("Operation cancelled by user.")

    def out_path(self, src: Path, suffix: str = "", ext: str | None = None) -> Path:
        """Create a safe destination path for an input file."""
        return make_output_path(
            source=src,
            out_dir=self.out_dir,
            suffix=suffix,
            ext=ext,
            overwrite=self.overwrite,
        )

    def dest_path(self, name: str, ext: str) -> Path:
        """Create a safe destination path for a standalone output file."""
        base_dir = self.out_dir or Path.cwd()
        return make_output_path(
            source=base_dir / name,
            out_dir=base_dir,
            ext=ext,
            overwrite=self.overwrite,
        )

    def add_output(self, path: Path) -> Path:
        self.outputs.append(path)
        return path


# -----------------------------------------------------------------------------
# Tool Base Class
# -----------------------------------------------------------------------------

class Tool:
    """Base class for all SwissKnife tools."""

    id: str = ""
    name: str = ""
    category: str = Category.IMAGES
    description: str = ""
    accepts: list[str] = ["*.*"]
    requires_files: bool = True
    params: list[Param] = []

    def get_default_params(self) -> dict[str, Any]:
        """Return a dictionary of default parameter values."""
        return {p.key: p.default for p in self.params}

    def plan(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> list[str]:
        """Dry-run preview. Returns a list of planned actions or file changes."""
        return []

    def run(self, files: list[Path], params: dict[str, Any], ctx: JobContext) -> RunResult:
        """Execute the batch tool operation."""
        raise NotImplementedError

