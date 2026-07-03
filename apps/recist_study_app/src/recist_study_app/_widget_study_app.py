import json
import os
import glob
import random
import time
from itertools import product

import numpy as np
from yaml import safe_load
from scipy.ndimage import center_of_mass

from napari import Viewer
from napari.layers import Labels
from napari.utils.notifications import show_info, show_warning
from napari_toolkit.containers.boxlayout import stack, QHBoxLayout
from napari_toolkit.utils import set_value
from napari_toolkit.utils.widget_getter import get_value
from napari_toolkit.widgets import *
from napari_toolkit.widgets import setup_iconbutton, setup_label

from qtpy.QtWidgets import QVBoxLayout, QWidget, QMessageBox

import SimpleITK as sitk
from napari_beacon_layers import FixedImageLayer, PreviewLabelsLayer, PreviewPointsLayer, LinePromptLayer
from napari_inverted_scrolling import invert_scrolling, reset_scrolling, is_inverted

from .acknowledgements import setup_acknowledgements
from ._napari_ui import modify_napari_ui as _modify_napari_ui, revert_napari_ui as _revert_napari_ui


def _resample_sitk_to_isotropic(sitk_image, interpolator=sitk.sitkLinear):
    original_spacing = np.array(sitk_image.GetSpacing())
    original_size = np.array(sitk_image.GetSize())
    target_spacing = float(original_spacing.min())
    new_size = np.round(original_size * original_spacing / target_spacing).astype(int).tolist()
    resampler = sitk.ResampleImageFilter()
    resampler.SetOutputSpacing([target_spacing] * 3)
    resampler.SetSize(new_size)
    resampler.SetOutputDirection(sitk_image.GetDirection())
    resampler.SetOutputOrigin(sitk_image.GetOrigin())
    resampler.SetTransform(sitk.Transform())
    resampler.SetDefaultPixelValue(0)
    resampler.SetInterpolator(interpolator)
    return resampler.Execute(sitk_image)


class StudyAppWidget(QWidget):
    def __init__(self, viewer: Viewer):
        super().__init__()
        self._viewer = viewer

        main_layout = QVBoxLayout(self)

        _layout = main_layout

        self.user_id_input = setup_lineedit(
            _layout, "Physician ID", "Physician ID", function=lambda: None
        )
        self.file_select = setup_fileselect(
            _layout, "Select study file", filtering="YAML files (*.yaml *.yml)", function=lambda: None
        )
        self.file_select.set_file("./example_study/example_recist_study.yaml")

        self.init_button = setup_iconbutton(
            _layout, "Initialize", "right_arrow", self._viewer.theme, self.initalize
        )
        setup_acknowledgements(_layout)

    def initalize(self):
        physicsian_id = get_value(self.user_id_input)
        study_protocol_path = get_value(self.file_select)
        with open(study_protocol_path, 'r') as f:
            study_protocol = safe_load(f)
        widget = StudyAppFullWidget(self._viewer, physicsian_id, study_protocol)
        self._viewer.window.add_dock_widget(
            widget, name="RECIST study", area="left"
        )

        widget.parent()._close_btn = False

        # close self
        self.close()
        self._viewer.window.remove_dock_widget(self)
        self.deleteLater()

    def hideEvent(self, event):
        # ignore
        event.ignore()
        pass


class StudyAppFullWidget(QWidget):
    def __init__(self, viewer: Viewer, user_id, study_protocol):
        super().__init__()
        self._viewer = viewer

        self.user_id = user_id
        self.study_protocol = study_protocol

        study_methods = self.study_protocol.get("methods", ["line_prompt"])
        study_cases = self.study_protocol.get("cases", [])
        cases_root_dir = self.study_protocol.get("cases_root_dir", "")
        # prepend root dir to case paths
        if cases_root_dir != "":
            for case in study_cases:
                case["file"] = os.path.join(cases_root_dir, case["file"])
                if "mask" in case and case["mask"] is not None:
                    case["mask"] = os.path.join(cases_root_dir, case.get("mask", ""))

        order = self.study_protocol.get("order", "random")
        output_folder = self.study_protocol.get("output_folder")
        if output_folder is not None and output_folder != "":
            os.makedirs(output_folder, exist_ok=True)

        self.approve_mode = self.study_protocol.get("approve_mode", "Next")
        self._reopen_on_close = True

        # cartesian product of methods and cases
        self.study_tasks = []

        for method, case in product(study_methods, study_cases):
            task = ({
                "task_id": f"{method}_{case['id']}",
                "method": method,
                "file": case["file"],
                "case_id": case["id"],
                "mask_file": case.get("mask", None),
                "guidance_point": case.get("guidance_point", None),
                "name": case.get("name", None)
            })
            self.study_tasks.append(task)

        if order == "random":
            # seed with sum of user_id characters so the order is reproducible per user
            random.seed(sum(ord(c) for c in self.user_id))
            random.shuffle(self.study_tasks)
        elif order == "sequential-methods":
            self.study_tasks.sort(key=lambda x: (x["method"], x["case_id"]))
        elif order == "sequential-cases":
            self.study_tasks.sort(key=lambda x: (x["case_id"], x["method"]))
        elif order == "manual":
            manual_order = self.study_protocol.get("manual_order", [])
            self.study_tasks = [task for task in self.study_tasks if task["task_id"] in manual_order]
            self.study_tasks.sort(key=lambda x: manual_order.index(x["task_id"]) if x["task_id"] in manual_order else len(manual_order))

        main_layout = QVBoxLayout(self)

        self.current_task_index = 0
        self.image_layer = None
        self.guidance_layer = None
        self.line_layer = None
        self._original_img_sitk_reference = None
        self._display_img_sitk_reference = None

        _layout = main_layout

        self.task_counter_label = setup_label(_layout, f"")
        self.update_task_counter()

        def on_task_change():
            self.clear_task()
            self.current_task_index = get_value(self._task_combobox)[1]
            if self.current_task_index < len(self.study_tasks) and self.current_task_index >= 0:
                self.load_task(self.study_tasks[self.current_task_index])

        self._task_combobox = setup_combobox(
            _layout,
            [f"{task['method']} - {task['case_id']}" for task in self.study_tasks],
            function=on_task_change
        )

        self._navigation_widget = QWidget()
        self._navigation_layout = QHBoxLayout(self._navigation_widget)
        stack(self._navigation_layout, [
            setup_iconbutton(
                _layout, "Previous", "step_left", self._viewer.theme, self.load_previous_task),
            setup_iconbutton(
                _layout, "Next", "step_right", self._viewer.theme, self.load_next_task
            )], stretch=[0, 0])

        self.approve_button = setup_iconbutton(
            _layout, "Approve", "erase", self._viewer.theme, self.approve
        )
        self.approve_button.setToolTip("Save the current line prompt and move to the next case.")

        setup_acknowledgements(_layout)

        self.modify_napari_ui()

        self.load_task(self.study_tasks[self.current_task_index])

        def on_windowing_shortcut(preset):
            if self.image_layer is None:
                return
            image_layer_controls = self._viewer.window._qt_viewer._controls.widgets[self.image_layer]
            image_layer_controls._contrast_compobox.setCurrentText(preset)

        for shortcut, preset in self.study_protocol.get("contrast_shortcuts", {}).items():
            self._viewer.bind_key(shortcut, lambda _, p=preset: on_windowing_shortcut(p), overwrite=True)

        if self.study_protocol.get("inverted_scrolling", False) and not is_inverted(self._viewer):
            invert_scrolling(self._viewer)

    def update_task_counter(self):
        if len(self.study_tasks) == 0:
            self.task_counter_label.setText("All tasks done.")
            return
        current_task = self.study_tasks[self.current_task_index]
        self.task_counter_label.setText(
            f"Task: {current_task['method']} - {current_task['case_id']}  ({self.current_task_index+1}/{len(self.study_tasks)})"
        )

    def _get_guidance_mode(self):
        guidance = self.study_protocol.get("guidance", False)
        if isinstance(guidance, bool):
            return "point" if guidance else "none"
        if guidance is None:
            return "none"
        guidance = str(guidance).strip().lower()
        if guidance in ("false", "none", ""):
            return "none"
        if guidance in ("full-3d-mask", "full_3d_mask", "mask", "labels"):
            return "full-3d-mask"
        return "point"

    def load_next_task(self):
        if self.study_protocol.get("confirm_before_changing_tasks", True) and not self.confirm_dialog("Proceed", "The line prompt was not approved. Are you sure you want to proceed? Any unapproved line prompt for this case will be lost."):
            return
        if self.current_task_index < len(self.study_tasks) - 1:
            self._task_combobox.setCurrentIndex(self.current_task_index + 1)

    def load_previous_task(self):
        if self.study_protocol.get("confirm_before_changing_tasks", True) and not self.confirm_dialog("Proceed", "The line prompt was not approved. Are you sure you want to proceed? Any unapproved line prompt for this case will be lost."):
            return
        if self.current_task_index > 0:
            self._task_combobox.setCurrentIndex(self.current_task_index - 1)

    def clear_task(self):
        if self.image_layer is not None:
            self._viewer.layers.remove(self.image_layer)
            self.image_layer = None

        if self.guidance_layer is not None:
            self._viewer.layers.remove(self.guidance_layer)
            self.guidance_layer = None

        if self.line_layer is not None:
            self._viewer.layers.remove(self.line_layer)
            self.line_layer = None

        self._original_img_sitk_reference = None
        self._display_img_sitk_reference = None

    def _output_json_path(self, task):
        output_folder = self.study_protocol.get("output_folder", "")
        return os.path.join(
            output_folder,
            f"{self.user_id}_case{task['case_id']}_method{task['method']}_line_prompt.json"
        )

    def load_task(self, task):
        method = task["method"]
        path = task["file"]
        case_id = task["case_id"]

        isotropic_pixels = self.study_protocol.get("isotropic_pixels", False)

        img_sitk = sitk.ReadImage(path)
        # keep a reference to the original, non-resampled image so line prompt
        # coordinates can also be reported in the original image's index space
        self._original_img_sitk_reference = img_sitk
        if isotropic_pixels:
            print(f"[isotropic_pixels] image before: shape={img_sitk.GetSize()[::-1]}, spacing={img_sitk.GetSpacing()}")
            img_sitk = _resample_sitk_to_isotropic(img_sitk, sitk.sitkLinear)
            print(f"[isotropic_pixels] image after:  shape={img_sitk.GetSize()[::-1]}, spacing={img_sitk.GetSpacing()}")
        self._display_img_sitk_reference = img_sitk
        img = sitk.GetArrayFromImage(img_sitk)
        self.image_layer = FixedImageLayer(
            img,
            name=f'Image {case_id} {task["name"]}' if task["name"] is not None else f'Image {case_id}',
            colormap='gray',
            interpolation2d=self.study_protocol.get("interpolation", "nearest")
        )

        self.image_layer.scale = np.array([-1, 1, 1]) \
            * np.array(img_sitk.GetSpacing()[::-1])  # reverse for napari xyz vs sitk zyx

        self._viewer.add_layer(self.image_layer)

        image_layer_controls = self._viewer.window._qt_viewer._controls.widgets[self.image_layer]
        if self.study_protocol.get("custom_contrast_presets", False):
            for name, (center, width) in self.study_protocol.get("custom_contrast_presets", {}).items():
                image_layer_controls.CONTRAST_PRESETS[name] = (center, width)
                image_layer_controls._contrast_compobox.addItem(name)

        contrast_preset = self.study_protocol.get("contrast_preset", None)
        if contrast_preset is not None:
            if contrast_preset in image_layer_controls.CONTRAST_PRESETS:
                image_layer_controls._contrast_compobox.setCurrentText(contrast_preset)
            else:
                show_warning(f"Default contrast preset {contrast_preset} not found. Using full contrast range instead.")

        # load guidance mask / point if provided, to point the user to the lesion to measure
        com = None
        guidance_mode = self._get_guidance_mode()
        if (task["mask_file"] is not None) and guidance_mode != "none":
            mask_sitk = sitk.ReadImage(task["mask_file"])
            if isotropic_pixels:
                mask_sitk = _resample_sitk_to_isotropic(mask_sitk, sitk.sitkNearestNeighbor)
            mask = sitk.GetArrayFromImage(mask_sitk)

            com = np.array(center_of_mass(mask)).astype(np.int32)

            if task.get("guidance_point", None) is not None:
                com = np.array(task["guidance_point"])

            if guidance_mode == "full-3d-mask":
                self.guidance_layer = PreviewLabelsLayer(
                    mask,
                    name=f'Guidance {case_id}',
                )
                self.guidance_layer.contour = 1
                self.guidance_layer.opacity = 1.0
            else:
                self.guidance_layer = PreviewPointsLayer(
                    com[np.newaxis, :],
                    name=f'Guidance {case_id}',
                    size=2,
                    face_color='red',
                    border_color="white"
                )
                self.guidance_layer.opacity = 0.8

            self.guidance_layer.scale = np.array([-1, 1, 1]) * np.array(mask_sitk.GetSpacing()[::-1])
            self.guidance_layer.editable = False
            self._viewer.add_layer(self.guidance_layer)

        # set up the line prompt layer
        allow_multiple_lines = self.study_protocol.get("allow_multiple_lines", False)
        self.line_layer = LinePromptLayer(
            ndim=self.image_layer.ndim,
            scale=self.image_layer.scale,
            name=f'Line prompt {case_id}',
            edge_color='yellow',
            edge_width=1,
            limit_to_single_line=not allow_multiple_lines,
        )
        self._viewer.add_layer(self.line_layer)

        # reload an already-drawn line prompt if it was previously saved
        existing_json = self._output_json_path(task)
        if os.path.exists(existing_json):
            try:
                with open(existing_json, 'r') as f:
                    saved = json.load(f)
                self.line_layer.data = [np.array(line["line_points_index"]) for line in saved["lines"]]
            except Exception as e:
                show_warning(f"Could not load existing line prompt for this case: {e}")

        if com is not None:
            self._viewer.dims.set_current_step(0, img.shape[0] - com[0] - 1)
            self._viewer.dims.set_current_step(1, com[1])
            self._viewer.dims.set_current_step(2, com[2])

        self._viewer.layers.selection.active = self.line_layer

        self.update_task_counter()

    def _points_index_to_original_space(self, points_index):
        """Map line points from the (possibly resampled) display image's index
        space into the index space of the original, non-resampled image, via
        the physical (mm) space shared by both images."""
        display_img_sitk = self._display_img_sitk_reference
        original_img_sitk = self._original_img_sitk_reference
        if display_img_sitk is None or original_img_sitk is None:
            return points_index.tolist()

        points_index_original = []
        for point_zyx in points_index:
            z, y, x = (float(v) for v in point_zyx)
            physical_point = display_img_sitk.TransformContinuousIndexToPhysicalPoint((x, y, z))
            orig_x, orig_y, orig_z = original_img_sitk.TransformPhysicalPointToContinuousIndex(physical_point)
            points_index_original.append([orig_z, orig_y, orig_x])
        return points_index_original

    def _build_line_prompt_result(self, task):
        spacing_zyx = np.abs(self.line_layer.scale)
        original_spacing_zyx = np.array(self._original_img_sitk_reference.GetSpacing()[::-1]).tolist() \
            if self._original_img_sitk_reference is not None else None

        lines = []
        for line_data in self.line_layer.data:
            points_index = np.asarray(line_data)
            points_physical = points_index * spacing_zyx
            length_mm = float(np.linalg.norm(points_physical[1] - points_physical[0]))
            points_index_original = self._points_index_to_original_space(points_index)
            lines.append({
                "line_points_index": points_index.tolist(),
                "line_points_physical_mm": points_physical.tolist(),
                "line_points_index_original_space": points_index_original,
                "length_mm": length_mm,
            })

        return {
            "task_id": task["task_id"],
            "method": task["method"],
            "case_id": task["case_id"],
            "user_id": self.user_id,
            "file": task["file"],
            "spacing_zyx": spacing_zyx.tolist(),
            "original_spacing_zyx": original_spacing_zyx,
            "num_lines": len(lines),
            "lines": lines,
            "timestamp": time.time(),
        }

    def approve(self):
        if self.line_layer is None or len(self.line_layer.data) == 0:
            show_warning("Please draw a line prompt before approving this case.")
            return

        if self.study_protocol.get("confirm_before_approving", True) and not self.confirm_dialog("Approve", "Are you sure the line prompt is placed correctly? Once you approve, you will move on to the next case."):
            return

        task = self.study_tasks[self.current_task_index]
        output_folder = self.study_protocol.get("output_folder", "")

        result = self._build_line_prompt_result(task)
        num_lines = result["num_lines"]

        output_path = self._output_json_path(task)
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=4)

        show_info(f"Saved {num_lines} line prompt(s) for task {task['task_id']} to {output_path}")

        if self.approve_mode == "NextRemove":
            self.clear_task()
            self.study_tasks.pop(self.current_task_index)
            # removeItem() fires currentIndexChanged (and thus on_task_change,
            # which itself calls clear_task()/load_task()) whenever the removed
            # item was the current one. Block signals so that doesn't trigger a
            # second, duplicate load_task() call below.
            self._task_combobox.blockSignals(True)
            self._task_combobox.removeItem(self.current_task_index)
            self._task_combobox.blockSignals(False)

            if len(self.study_tasks) == 0:
                show_info("All tasks approved.")
                self.current_task_index = 0
                self.update_task_counter()
                return

            if self.current_task_index >= len(self.study_tasks):
                self.current_task_index = len(self.study_tasks) - 1
            self.load_task(self.study_tasks[self.current_task_index])
        else:  # "Next"
            self.clear_task()
            if self.current_task_index < len(self.study_tasks) - 1:
                self.current_task_index += 1
                self.load_task(self.study_tasks[self.current_task_index])
            else:
                show_info("No more tasks to load.")
                self.update_task_counter()

    def modify_napari_ui(self):
        _modify_napari_ui(
            self._viewer,
            get_image_layer=lambda: self.image_layer,
            get_interpolation=lambda: self.study_protocol.get("interpolation", "nearest"),
        )

        self._prev_layer_keyPressEvent_handler = self._viewer.window._qt_viewer._layers.keyPressEvent

        def _filtered_key_press(e):
            if e is None:
                return
            self._prev_layer_keyPressEvent_handler(e)

        self._viewer.window._qt_viewer._layers.keyPressEvent = _filtered_key_press

    def revert_napari_ui(self):
        _revert_napari_ui(self._viewer)
        self._viewer.window._qt_viewer._layers.keyPressEvent = self._prev_layer_keyPressEvent_handler
        del self._prev_layer_keyPressEvent_handler

    def showEvent(self, event):
        pass

    def closeEvent(self, event):
        self.revert_napari_ui()

        self.clear_task()

        for shortcut in self.study_protocol.get("contrast_shortcuts", {}).keys():
            self._viewer.bind_key(shortcut, ..., overwrite=True)

        if self.study_protocol.get("inverted_scrolling", False) and is_inverted(self._viewer):
            reset_scrolling(self._viewer)

        if self._reopen_on_close:
            widget = StudyAppWidget(self._viewer)
            self._viewer.window.add_dock_widget(
                widget, name="RECIST study", area="left"
            )

    def hideEvent(self, event):
        # ignore
        event.ignore()
        pass

    def confirm_dialog(self, title, message):
        reply = QMessageBox.question(self, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return reply == QMessageBox.Yes
