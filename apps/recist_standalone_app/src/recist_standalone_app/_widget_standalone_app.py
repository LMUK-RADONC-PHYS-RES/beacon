"""
Standalone single-case entrypoint for the RECIST study workflow.

Flow:
  1. StandaloneAppWidget is added to napari (plugin widget or startup script).
  2. A setup dialog opens: file picker and structured config form.
  3. On accept, StandaloneStudyWidget loads the single task.
  4. On approve, a folder-picker dialog asks where to store the line prompt.
"""

import json
import time
import os
from pathlib import Path

from napari import Viewer
from napari.utils.notifications import show_info, show_warning
from napari_toolkit.utils.widget_getter import get_value
from napari_toolkit.containers import setup_vgroupbox
from napari_toolkit.widgets import (
    setup_iconbutton, setup_label, setup_combobox,
    setup_fileselect, setup_checkbox,
)

from qtpy.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QLabel,
    QMessageBox, QVBoxLayout, QWidget,
)

from recist_study_app._widget_study_app import StudyAppFullWidget


# ---------------------------------------------------------------------------
# Setup dialog
# ---------------------------------------------------------------------------

class StandaloneSetupDialog(QDialog):
    """
    Dialog that collects the image path and structured config settings
    before launching the single-task study widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RECIST Standalone — Setup")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        # --- Image file ---
        self._image_select = setup_fileselect(
            layout,
            "Image file",
            filtering="Medical images (*.mha *.mhd *.nii *.nii.gz *.nrrd);;All files (*)",
        )

        # --- Configuration ---
        cfg_box, cfg_layout = setup_vgroupbox(layout, "Configuration")

        setup_label(cfg_layout, "Mask / guidance")
        self._mask_select = setup_fileselect(
            cfg_layout,
            "Mask file (optional)",
            filtering="Medical images (*.mha *.mhd *.nii *.nii.gz *.nrrd);;All files (*)",
        )
        self._guidance_combo = setup_combobox(
            cfg_layout,
            ["none", "point", "full-3d-mask"],
            placeholder="Guidance mode",
        )

        setup_label(cfg_layout, "Image display")
        self._interpolation_combo = setup_combobox(
            cfg_layout,
            ["nearest", "linear", "bicubic"],
            placeholder="Interpolation",
        )

        setup_label(cfg_layout, "Line prompt")
        self._isotropic_pixels_cb = setup_checkbox(
            cfg_layout, "Isotropic voxels (resample to isotropic on load)", True
        )
        self._allow_multiple_lines_cb = setup_checkbox(
            cfg_layout, "Allow multiple line prompts"
        )

        setup_label(cfg_layout, "Behaviour")
        self._inverted_scrolling_cb = setup_checkbox(
            cfg_layout, "Inverted scrolling"
        )
        self._confirm_approve_cb = setup_checkbox(
            cfg_layout, "Confirm before approving"
        )
        self._confirm_close_cb = setup_checkbox(
            cfg_layout, "Confirm before closing"
        )

        # --- Buttons ---
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        if not get_value(self._image_select):
            QMessageBox.warning(self, "Missing input", "Please select an image file.")
            return
        self.accept()

    def image_path(self) -> str:
        return get_value(self._image_select)

    def config(self) -> dict:
        guidance_raw = get_value(self._guidance_combo)
        guidance = (guidance_raw[0] if isinstance(guidance_raw, tuple) else guidance_raw) or "none"

        interpolation_raw = get_value(self._interpolation_combo)
        interpolation = (interpolation_raw[0] if isinstance(interpolation_raw, tuple) else interpolation_raw) or "nearest"

        mask_path = get_value(self._mask_select) or None

        return {
            "mask": mask_path,
            "guidance": guidance,
            "isotropic_pixels": bool(get_value(self._isotropic_pixels_cb)),
            "allow_multiple_lines": bool(get_value(self._allow_multiple_lines_cb)),
            "interpolation": interpolation,
            "custom_contrast_presets": {},
            "contrast_shortcuts": {},
            "inverted_scrolling": bool(get_value(self._inverted_scrolling_cb)),
            "confirm_before_approving": bool(get_value(self._confirm_approve_cb)),
            "confirm_before_changing_tasks": bool(get_value(self._confirm_close_cb)),
        }


# ---------------------------------------------------------------------------
# Napari plugin entrypoint widget
# ---------------------------------------------------------------------------

class StandaloneAppWidget(QWidget):
    """
    Napari plugin widget that immediately opens the setup dialog.
    After setup it replaces itself with StandaloneStudyWidget.
    """

    def __init__(self, viewer: Viewer):
        super().__init__()
        self._viewer = viewer

        # Create layout with setup button
        layout = QVBoxLayout(self)
        self.setup_button = setup_iconbutton(
            layout, " Open SetupDialog", "plus", viewer.theme, self._open_setup_dialog
        )

        from qtpy.QtCore import QTimer
        QTimer.singleShot(0, self._open_setup_dialog)

    def _open_setup_dialog(self):
        dialog = StandaloneSetupDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self._launch(dialog.image_path(), dialog.config())
        else:
            self._close_self()

    def _launch(self, image_path: str, config: dict):
        widget = StandaloneStudyWidget(self._viewer, image_path, config)
        self._viewer.window.add_dock_widget(widget, name="RECIST Standalone", area="left")
        self._close_self()

    def _close_self(self):
        self.close()
        try:
            self._viewer.window.remove_dock_widget(self)
        except Exception:
            pass
        self.deleteLater()

    def hideEvent(self, event):
        event.ignore()


# ---------------------------------------------------------------------------
# Single-task study widget
# ---------------------------------------------------------------------------

class StandaloneStudyWidget(StudyAppFullWidget):
    """
    Single-task study widget for the standalone RECIST flow.
    Inherits all core logic from StudyAppFullWidget; constructs a synthetic
    single-task study protocol from the given parameters and overrides
    approve() to ask the user for an output folder at save time.
    """

    def __init__(self, viewer: Viewer, image_path: str, config: dict):
        case_id = Path(image_path).stem
        synthetic_protocol = {
            "methods": ["line_prompt"],
            "cases": [{"id": case_id, "file": image_path, "mask": config.get("mask"), "name": None}],
            "order": "sequential-cases",
            "output_folder": "",
            "approve_mode": "Next",
            "guidance": config.get("guidance", "none"),
            "interpolation": config.get("interpolation", "nearest"),
            "custom_contrast_presets": config.get("custom_contrast_presets", {}),
            "contrast_shortcuts": config.get("contrast_shortcuts", {}),
            "inverted_scrolling": config.get("inverted_scrolling", False),
            "confirm_before_approving": config.get("confirm_before_approving", False),
            "confirm_before_changing_tasks": config.get("confirm_before_changing_tasks", False),
            "isotropic_pixels": config.get("isotropic_pixels", False),
            "allow_multiple_lines": config.get("allow_multiple_lines", False),
        }
        super().__init__(viewer, "", synthetic_protocol)

        self._reopen_on_close = False

        # Hide study-app navigation elements — irrelevant for a single task
        self.task_counter_label.hide()
        self._task_combobox.hide()
        if self._navigation_widget is not None:
            self._navigation_widget.hide()

        # Insert a header label at the top of the layout
        header = QLabel(f"line_prompt  |  {Path(image_path).name}")
        self.layout().insertWidget(0, header)

        # Clarify that approving also triggers a save dialog
        self.approve_button.setText("Approve / Save")
        self.approve_button.setToolTip(
            "Approve the current line prompt and choose where to save it."
        )

        # Close button
        self.close_button = setup_iconbutton(
            self.layout(), "Close", "visibility_off", self._viewer.theme, self._on_close_button
        )

    def _on_close_button(self):
        if self.study_protocol.get("confirm_before_changing_tasks", False) and not self.confirm_dialog(
            "Close",
            "Are you sure you want to close? Any unsaved line prompt will be lost.",
        ):
            return
        self.close()

    def approve(self):
        if self.line_layer is None or len(self.line_layer.data) == 0:
            show_warning("Please draw a line prompt before approving this case.")
            return

        if self.study_protocol.get("confirm_before_approving", False) and not self.confirm_dialog(
            "Approve",
            "Are you sure the line prompt is placed correctly?",
        ):
            return

        output_folder = QFileDialog.getExistingDirectory(
            self, "Select output folder", os.path.expanduser("~")
        )
        if not output_folder:
            return

        task = self.study_tasks[0]
        method = task["method"]
        case_id = task["case_id"]

        show_info(f"Saving line prompt for {case_id} ({method})…")

        result = self._build_line_prompt_result(task)
        num_lines = result["num_lines"]

        output_path = os.path.join(
            output_folder,
            f"case{case_id}_method{method}_line_prompt.json",
        )
        with open(output_path, "w") as f:
            json.dump(result, f, indent=4)

        show_info(f"Saved {num_lines} line prompt(s) to {output_path}")
