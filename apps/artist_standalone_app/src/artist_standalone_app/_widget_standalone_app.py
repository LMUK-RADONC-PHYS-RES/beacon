"""
Standalone single-case entrypoint for the ARTIST study workflow.

Flow:
  1. StandaloneAppWidget is added to napari (plugin widget or startup script).
  2. A setup dialog opens: file picker, method dropdown, structured config form.
  3. On accept, StandaloneStudyWidget loads the single task.
  4. On approve, a folder-picker dialog asks where to store the results.
"""

import json
import time
import os
from pathlib import Path

import numpy as np
import SimpleITK as sitk

from napari import Viewer
from napari.layers import Labels
from napari.utils.notifications import show_info
from napari_toolkit.utils.widget_getter import get_value
from napari_toolkit.containers import setup_vgroupbox
from napari_toolkit.widgets import (
    setup_iconbutton, setup_label, setup_combobox,
    setup_fileselect, setup_checkbox, setup_spinbox,
)

from qtpy.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QLabel,
    QMessageBox, QVBoxLayout, QWidget,
)

from artist_study_app._widget_study_app import StudyAppFullWidget


# ---------------------------------------------------------------------------
# Setup dialog
# ---------------------------------------------------------------------------

class StandaloneSetupDialog(QDialog):
    """
    Dialog that collects image path, method, and structured config settings
    before launching the single-task study widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ARTIST Standalone — Setup")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        # --- Image file ---
        self._image_select = setup_fileselect(
            layout,
            "Image file",
            filtering="Medical images (*.mha *.mhd *.nii *.nii.gz *.nrrd);;All files (*)",
        )

        # --- Method ---
        method_box, method_layout = setup_vgroupbox(layout, "Method")
        self._method_combo = setup_combobox(method_layout, ["manual", "nnInteractive"])
        self._method_combo.setMinimumWidth(200)

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

        setup_label(cfg_layout, "Labels")
        self._superresolution_spinbox = setup_spinbox(
            cfg_layout,
            minimum=1,
            maximum=5,
            step_size=1,
            default=1,
            prefix="Superresolution: ",
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
        self._disable_next_object_cb = setup_checkbox(
            cfg_layout, "Disable 'Next Object' after first use"
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

    def method(self) -> str:
        raw = get_value(self._method_combo)
        return raw[0] if isinstance(raw, tuple) else raw

    def config(self) -> dict:
        guidance_raw = get_value(self._guidance_combo)
        guidance = (guidance_raw[0] if isinstance(guidance_raw, tuple) else guidance_raw) or "none"

        interpolation_raw = get_value(self._interpolation_combo)
        interpolation = (interpolation_raw[0] if isinstance(interpolation_raw, tuple) else interpolation_raw) or "nearest"

        mask_path = get_value(self._mask_select) or None

        return {
            "mask": mask_path,
            "guidance": guidance,
            "superresolution": get_value(self._superresolution_spinbox),
            "interpolation": interpolation,
            "custom_contrast_presets": {},
            "contrast_shortcuts": {},
            "inverted_scrolling": bool(get_value(self._inverted_scrolling_cb)),
            "confirm_before_approving": bool(get_value(self._confirm_approve_cb)),
            "confirm_before_changing_tasks": bool(get_value(self._confirm_close_cb)),
            "disable_next_object_after_first_use": bool(get_value(self._disable_next_object_cb)),
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
            self._launch(dialog.image_path(), dialog.method(), dialog.config())
        else:
            self._close_self()

    def _launch(self, image_path: str, method: str, config: dict):
        widget = StandaloneStudyWidget(self._viewer, image_path, method, config)
        self._viewer.window.add_dock_widget(widget, name="ARTIST Standalone", area="left")
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
    Single-task study widget for the standalone ARTIST flow.
    Inherits all core logic from StudyAppFullWidget; constructs a synthetic
    single-task study protocol from the given parameters and overrides
    approve() to ask the user for an output folder at save time.
    """

    def __init__(self, viewer: Viewer, image_path: str, method: str, config: dict):
        case_id = Path(image_path).stem
        synthetic_protocol = {
            "methods": [method],
            "cases": [{"id": case_id, "file": image_path, "mask": config.get("mask"), "name": None}],
            "order": "sequential-cases",
            "output_folder": "",
            "approve_mode": "Next",
            "guidance": config.get("guidance", "none"),
            "superresolution": config.get("superresolution", 1),
            "interpolation": config.get("interpolation", "nearest"),
            "custom_contrast_presets": config.get("custom_contrast_presets", {}),
            "contrast_shortcuts": config.get("contrast_shortcuts", {}),
            "inverted_scrolling": config.get("inverted_scrolling", False),
            "confirm_before_approving": config.get("confirm_before_approving", False),
            "confirm_before_changing_tasks": config.get("confirm_before_changing_tasks", False),
            "disable_next_object_after_first_use": config.get("disable_next_object_after_first_use", False),
        }
        super().__init__(viewer, "", synthetic_protocol)

        self._reopen_on_close = False

        # Hide study-app navigation elements — irrelevant for a single task
        self.task_counter_label.hide()
        self._task_combobox.hide()
        if self._navigation_widget is not None:
            self._navigation_widget.hide()

        # Insert a header label at the top of the layout
        header = QLabel(f"{method}  |  {Path(image_path).name}")
        self.layout().insertWidget(0, header)

        # Clarify that approving also triggers a save dialog
        self.approve_button.setText("Approve / Save")
        self.approve_button.setToolTip(
            "Approve the current segmentation and choose where to save it."
        )

        # Close button
        self.close_button = setup_iconbutton(
            self.layout(), "Close", "visibility_off", self._viewer.theme, self._on_close_button
        )

    def _on_close_button(self):
        if self.study_protocol.get("confirm_before_changing_tasks", False) and not self.confirm_dialog(
            "Close",
            "Are you sure you want to close? Any unsaved segmentation will be lost.",
        ):
            return
        self.close()

    def approve(self):
        if self.study_protocol.get("confirm_before_approving", False) and not self.confirm_dialog(
            "Approve",
            "Are you sure the target object is delineated correctly?",
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

        show_info(f"Saving results for {case_id} ({method})…")

        for layer in self._viewer.layers:
            if not isinstance(layer, Labels):
                continue
            if layer.name.startswith("Guidance"):
                continue
            output_path = os.path.join(
                output_folder,
                f"case{case_id}_method{method}_layer{layer.name}.mha",
            )
            layer_data = layer.data.astype(np.uint8)
            sitk_img = sitk.GetImageFromArray(layer_data)
            spacing_zyx = np.abs(layer.scale)
            sitk_img.SetSpacing(spacing_zyx[::-1].tolist())
            sitk.WriteImage(sitk_img, output_path, useCompression=True)

        self.edit_log.record({
            "event_group": "study",
            "event_type": "approve",
            "timestamp": time.time(),
        })
        self.edit_log.stop()

        edit_log_path = os.path.join(
            output_folder,
            f"case{case_id}_method{method}_edit_log.json",
        )
        with open(edit_log_path, "w") as f:
            json.dump(self.edit_log.log, f, indent=4)

        show_info(f"Results saved to {output_folder}")
