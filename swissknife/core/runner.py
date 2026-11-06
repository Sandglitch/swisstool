"""Background worker and thread execution runner for SwissKnife tools."""
from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from .tool import Tool, JobContext, RunResult, ToolError, CancelledError
from .settings import settings


class ToolWorker(QThread):
    """Executes a tool on a dedicated background thread with progress and cancel support."""

    progress_signal = Signal(int, int, str)
    log_signal = Signal(str)
    finished_signal = Signal(object)  # RunResult
    failed_signal = Signal(str)
    cancelled_signal = Signal()

    def __init__(
        self,
        tool: Tool,
        files: list[Path],
        params: dict[str, Any],
        is_dry_run: bool = False,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.tool = tool
        self.files = files
        self.params = params
        self.is_dry_run = is_dry_run
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Signal the running job to cancel."""
        self._cancel_event.set()

    def run(self) -> None:
        custom_out = settings.get("default_output_dir", "").strip()
        out_dir = Path(custom_out) if custom_out else None
        overwrite = bool(settings.get("overwrite", False))

        ctx = JobContext(
            cancel_event=self._cancel_event,
            progress_cb=self.progress_signal.emit,
            log_cb=self.log_signal.emit,
            out_dir=out_dir,
            overwrite=overwrite,
        )

        try:
            if self.is_dry_run:
                self.log_signal.emit(f"--- Dry Run: {self.tool.name} ---")
                plan_items = self.tool.plan(self.files, self.params, ctx)
                result = RunResult(
                    outputs=[],
                    text="\n".join(plan_items) if plan_items else "No changes would be made.",
                    message=f"Dry run complete: {len(plan_items)} item(s) planned.",
                )
            else:
                self.log_signal.emit(f"--- Starting: {self.tool.name} ---")
                result = self.tool.run(self.files, self.params, ctx)

            ctx.check_cancelled()
            self.finished_signal.emit(result)

        except CancelledError:
            self.log_signal.emit("[Cancelled by user]")
            self.cancelled_signal.emit()

        except ToolError as e:
            msg = str(e)
            self.log_signal.emit(f"[Error] {msg}")
            self.failed_signal.emit(msg)

        except Exception as e:
            trace = traceback.format_exc()
            self.log_signal.emit(f"[Unexpected Error] {e}\n{trace}")
            self.failed_signal.emit(f"An unexpected error occurred: {e}")

