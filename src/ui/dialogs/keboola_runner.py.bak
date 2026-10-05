# ----------------------------------------------------------------------
# SQL Schema Studio 0.9 - Keboola Pipeline Runner Dialog (GPLv3)
# Copyright (C) 2026 Peter Leukanič
# License: GNU GPL v3+ <https://www.gnu.org/licenses/gpl-3.0.txt>
# This is free software with NO WARRANTY.
# Feel free to distribute and modify.
# ----------------------------------------------------------------------

"""Dialog that runs a Keboola pipeline with live progress."""

from __future__ import annotations

import os

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from src.hooks.python_hooks.keboola.profiles import ProfileManager
from src.utils.gtk_helpers import run_async, set_margin
from src.utils.logging import get_logger

logger = get_logger(__name__)


class KeboolaRunnerDialog(Gtk.Window):
    """Pick a CSV, run the pipeline, show live progress."""

    def __init__(self, parent, csv_path: str, profile_name: str | None = None):
        super().__init__(
            title="Keboola Pipeline",
            transient_for=parent,
            modal=True,
        )
        self._window = parent
        self._csv_path = csv_path
        self._profile_name = profile_name
        self._on_report = None  # callback set by caller

        self.set_default_size(560, 420)
        self._build_ui()

        # Start the run as soon as the dialog is shown
        GLib.idle_add(self._start_run)

    def set_report_callback(self, cb):
        """Register a callback(report_dict) fired when the run finishes."""
        self._on_report = cb

    # ==================================================================

    def _build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        set_margin(box, 16)

        header = Gtk.Label()
        header.set_markup(f"<b>Running pipeline for:</b>\n{os.path.basename(self._csv_path)}")
        header.set_halign(Gtk.Align.START)
        header.set_wrap(True)
        box.append(header)

        self._progress = Gtk.ProgressBar()
        self._progress.set_show_text(True)
        box.append(self._progress)

        self._step_label = Gtk.Label()
        self._step_label.set_halign(Gtk.Align.START)
        self._step_label.set_wrap(True)
        self._step_label.set_text("Starting…")
        box.append(self._step_label)

        # Log view
        self._log_view = Gtk.TextView()
        self._log_view.set_editable(False)
        self._log_view.set_monospace(True)
        self._log_view.set_wrap_mode(Gtk.WrapMode.WORD)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(self._log_view)
        box.append(scroll)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)

        self._btn_show = Gtk.Button(label="Show File")
        self._btn_show.set_sensitive(False)
        self._btn_show.connect("clicked", self._on_show_file)
        btn_box.append(self._btn_show)

        self._btn_close = Gtk.Button(label="Close")
        self._btn_close.connect("clicked", lambda b: self.close())
        btn_box.append(self._btn_close)

        box.append(btn_box)
        self.set_child(box)

        self._last_downloaded = ""

    # ==================================================================

    def _log(self, msg: str):
        buffer = self._log_view.get_buffer()
        end = buffer.get_end_iter()
        buffer.insert(end, f"{msg}\n")
        self._log_view.scroll_to_iter(end, 0.0, False, 0.0, 0.0)

    def _on_progress(self, step: str, message: str):
        """Progress callback from the pipeline (runs on the worker thread).

        Must marshal back to the GTK main thread.
        """
        GLib.idle_add(self._apply_progress, step, message)

    def _apply_progress(self, step: str, message: str):
        self._step_label.set_text(f"[{step}] {message}")
        self._log(message)

        # Cheap progress approximation — map step names to fractions
        fractions = {
            "upload": 0.15,
            "transform": 0.35,
            "trigger": 0.50,
            "wait": 0.75,
            "download": 0.95,
            "done": 1.0,
            "error": 1.0,
        }
        frac = fractions.get(step, 0.05)
        self._progress.set_fraction(frac)
        return False

    # ==================================================================

    def _start_run(self):
        self._progress.set_fraction(0.0)

        profile_name = self._profile_name
        csv_path = self._csv_path

        def run():
            from src.hooks.python_hooks.keboola.pipeline import TransformationPipeline

            manager = ProfileManager()
            profile = manager.get(profile_name) if profile_name else manager.active
            if profile is None:
                return {
                    "status": "error",
                    "error": f"No profile found"
                    + (f" named '{profile_name}'" if profile_name else ""),
                }

            errors = profile.validate()
            if errors:
                return {
                    "status": "error",
                    "error": "Profile is not valid: " + "; ".join(errors),
                }

            try:
                pipeline = TransformationPipeline(profile, on_progress=self._on_progress)
                report = pipeline.run(csv_path, timeout=300)
                manager.add(profile)  # persist transformation_id if newly created
                return report.to_dict()
            except Exception as e:
                logger.exception("Pipeline run failed")
                return {"status": "error", "error": str(e)}

        def on_done(report: dict):
            status = report.get("status", "error")
            if status == "ok":
                self._progress.set_fraction(1.0)
                self._step_label.set_markup('<span foreground="green">✓ Pipeline finished</span>')
            else:
                self._progress.set_fraction(1.0)
                self._step_label.set_markup(
                    f'<span foreground="red">✗ {report.get("error", "failed")}</span>'
                )

            self._log("")
            self._log(f"--- Final report ---")
            import json as _json

            self._log(_json.dumps(report, indent=2, default=str))

            path = report.get("downloaded_csv") or ""
            self._last_downloaded = path
            self._btn_show.set_sensitive(bool(path))

            if self._on_report:
                try:
                    self._on_report(report)
                except Exception as e:
                    logger.warning(f"report callback failed: {e}")

        run_async(run, on_done)
        return False

    # ==================================================================

    def _on_show_file(self, _button):
        if not self._last_downloaded:
            return
        from src.hooks.python_hooks.keboola.client import KeboolaClient

        KeboolaClient.open_in_file_manager(self._last_downloaded)
