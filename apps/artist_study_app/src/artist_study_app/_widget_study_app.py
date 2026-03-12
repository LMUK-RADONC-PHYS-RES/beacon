import json
from pathlib import Path

import threading
import time
import torch
from yaml import safe_load
import os
import cv2
from magicgui import magicgui
from napari.layers import Image
from typing import TYPE_CHECKING
from functools import partial
import numpy as np
import random
from itertools import product

from napari.utils.colormaps import CyclicLabelColormap, DirectLabelColormap, label_colormap
from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification
from napari import Viewer
from napari.layers import Labels, Shapes, Points, Image, Layer
from napari_toolkit.containers import setup_scrollarea, setup_vcollapsiblegroupbox, setup_vgroupbox, setup_vscrollarea
from napari_toolkit.containers.boxlayout import hstack
from napari_toolkit.utils import set_value
from napari_toolkit.data_structs import setup_list
from napari_toolkit.utils.widget_getter import get_value
from napari_toolkit.widgets import *
from napari.utils.action_manager import action_manager
from napari.utils.events.event import WarningEmitter
from napari.utils.notifications import show_info
from napari.qt.threading import thread_worker
from napari_toolkit.widgets import setup_iconbutton, setup_label
from qtpy.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QVBoxLayout,
    QPushButton,
    QWidget,
    QMessageBox
)
from qtpy.QtCore import Qt  # type: ignore[attr-defined]

from qtpy.QtGui import (
    QTextOption
)
import traceback
import glob
from napari._qt.layer_controls.qt_layer_controls_container import layer_to_controls

from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification
from napari import Viewer
import SimpleITK as sitk
from scipy.interpolate import interpn
from napari_quick_view._widget_file_list import FileListWidget

from napari_quick_view.file_select import setup_dirselect
from napari_quick_view.layer_select import setup_layerselect
from napari_beacon_layers import FixedImageLayer, PreviewLabelsLayer, ManualLabelsLayer, PreviewPointsLayer
from napari_manual_segmentation import ManualSegmentationWidget
from napari_manual_segmentation.utils.utils import ColorMapper, determine_layer_index

from .multi_viewer import setup_multiple_viewer_widget, MultipleViewerWidget

from napari_edit_log.edit_log import NapariEditLog
from napari_inverted_scrolling import invert_scrolling, reset_scrolling, is_inverted
from .acknowledgements import setup_acknowledgements
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
        self.file_select.set_file("./example_study/example_study.yaml")

        self.init_button = setup_iconbutton(
            _layout, "Initialize", "right_arrow", self._viewer.theme, self.initalize
        )
        setup_acknowledgements(_layout)
        #self.initalize()

    def initalize(self):
        # initialize
        physicsian_id = get_value(self.user_id_input)
        study_protocol_path = get_value(self.file_select)
        widget = StudyAppFullWidget(self._viewer, physicsian_id, study_protocol_path)
        self._viewer.window.add_dock_widget(
            widget, name="ARTIST study", area="left"
        )

        widget.parent()._close_btn = False
        #widget.parent().title.float_button.setHidden(True)
        #widget.parent().title.hide_button.setHidden(True)

        # close self
        self.close()
        self._viewer.window.remove_dock_widget(self)
        self.deleteLater()

    def hideEvent(self, event):
        # ignore
        event.ignore()
        pass

class StudyAppFullWidget(QWidget):
    def __init__(self, viewer: Viewer, user_id, study_protocol_path):
        super().__init__()
        self._viewer = viewer
        
        self.user_id = user_id
        self.study_protocol_path = study_protocol_path
        
        self.colormap = ColorMapper(49, seed=0.5, background_value=0)

        # read study
        with open(study_protocol_path, 'r') as f:
            self.study_protocol = safe_load(f)
        
        study_methods = self.study_protocol.get("methods", [])
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
        # cathesian product of methods and cases
        self.study_tasks = []

        for method, case in product(study_methods, study_cases):
            task = ({
                "task_id": f"{method}_{case['id']}",
                "method": method,
                "file": case["file"],
                "case_id": case["id"],
                "mask_file": case.get("mask", None),
                "name": case.get("name", None)
            }) 

            # check if there are existing approved segmentations
            if output_folder is not None and output_folder != "":
                existing_files = glob.glob(os.path.join(
                    output_folder,
                    f"{self.user_id}_case{case['id']}_method{method}_layer*.mha"
                ))
                if len(existing_files) > 0:
                    # Do not add approved tasks to the list if approve_mode is NextRemove
                    #if self.approve_mode == "NextRemove":
                    #    continue
                    pass
            
            self.study_tasks.append(task)

        if order == "random":
            # seed with sum of user_id characters
            # this way the order is reproducible for each user
            random.seed(sum(ord(c) for c in self.user_id))
            # shuffle tasks
            random.shuffle(self.study_tasks)
        elif order == "sequential-methods":
            # group by methods
            self.study_tasks.sort(key=lambda x: (x["method"], x["case_id"]))
        elif order == "sequential-cases":
            # group by cases
            self.study_tasks.sort(key=lambda x: (x["case_id"], x["method"]))
        elif order == "manual":
            manual_order = self.study_protocol.get("manual_order", [])
            self.study_tasks = [task for task in self.study_tasks if task["task_id"] in manual_order]
            self.study_tasks.sort(key=lambda x: manual_order.index(x["task_id"]) if x["task_id"] in manual_order else len(manual_order))

        main_layout = QVBoxLayout(self)

        self.current_task_index = 0
        self.image_layer = None
        self.guidance_layer = None

        self.manual_segmentation_widget = None
        self.automatic_segmentation_widget = None

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

        hstack(_layout, [ 
            setup_iconbutton(
                _layout, "Previous", "step_left", self._viewer.theme, self.load_previous_task),
            setup_iconbutton(
                _layout, "Next", "step_right", self._viewer.theme, self.load_next_task
            )], stretch=[0,0])

        #self.pause_button = setup_iconbutton(
        #    _layout, "Pause", "erase", self._viewer.theme, lambda: None
        #)

        self.approve_button = setup_iconbutton(
            _layout, "Approve", "erase", self._viewer.theme, self.approve
        )
        self.approve_button.setToolTip("Approve current segmentation and move to next case.")

        self.modify_napari_ui()
        #self._start_quicksave_timer(interval_seconds=300, check_intervall_seconds=1)

        self.edit_log = NapariEditLog(viewer)

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

    def load_next_task(self):
        if self.study_protocol.get("confirm_before_changing_tasks", True) and not self.confirm_dialog("Proceed", "The segmentation was not approved. Are you sure you want to proceed? Any segmentation done on this patient will be lost without approval."):
            return
        if self.current_task_index < len(self.study_tasks) - 1:
            self._task_combobox.setCurrentIndex(self.current_task_index + 1)
    
    def load_previous_task(self):
        if self.study_protocol.get("confirm_before_changing_tasks", True) and not self.confirm_dialog("Proceed", "The segmentation was not approved. Are you sure you want to proceed? Any segmentation done on this patient will be lost without approval."):
            return

        if self.current_task_index > 0:
            self._task_combobox.setCurrentIndex(self.current_task_index - 1)

    def clear_task(self):
        self.edit_log.stop()
        if self.image_layer is not None:
            self._viewer.layers.remove(self.image_layer)
            self.image_layer = None
        
        if self.guidance_layer is not None:
            self._viewer.layers.remove(self.guidance_layer)
            self.guidance_layer = None
        
        # remove other labels layers
        for layer in self._viewer.layers:
            if isinstance(layer, Labels):
                self._viewer.layers.remove(layer)

        if self.manual_segmentation_widget is not None:
            self.manual_segmentation_widget.allow_close = True
            self.manual_segmentation_widget.parent().hide()
        
        if self.automatic_segmentation_widget is not None:
            self.automatic_segmentation_widget.parent().hide()

        self.edit_log.clear()

    def load_task(self, task):
        method = task["method"]
        path = task["file"]
        case_id = task["case_id"]

        img_sitk = sitk.ReadImage(path)
        img = sitk.GetArrayFromImage(img_sitk)
        self.image_layer = FixedImageLayer(
            img,
            name=f'Image {case_id} {task["name"]}' if task["name"] is not None else f'Image {case_id}',
            colormap='gray',
            interpolation2d=self.study_protocol.get("interpolation", "nearest")
        )

        self.image_layer.scale = np.array([-1,1,1]) \
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


        # load guidance mask if provided
        if (task["mask_file"] is not None) and self.study_protocol.get("guidance", False):
            mask_sitk = sitk.ReadImage(task["mask_file"])
            mask = sitk.GetArrayFromImage(mask_sitk)

            from scipy.ndimage import center_of_mass
            com = np.array(center_of_mass(mask)).astype(np.int32)
            print("Guidance center of mass:", com)
            self.guidance_layer = PreviewPointsLayer(
                com[np.newaxis, :],
                name=f'Guidance {case_id}',
                size=2,
                face_color='red',
                border_color="white"
            )
            
            self.guidance_layer.scale = np.array([-1,1,1]) * np.array(mask_sitk.GetSpacing()[::-1])  # reverse for napari xyz vs sitk zyx
            self.guidance_layer.opacity = 0.8
            self.guidance_layer.editable = False
            self._viewer.add_layer(self.guidance_layer)
            self._viewer.dims.set_current_step(0, img.shape[0] - com[0] -1)
            self._viewer.dims.set_current_step(1, com[1])
            self._viewer.dims.set_current_step(2, com[2])

        # load approved segmentations if existing
        output_folder = self.study_protocol.get("output_folder", "")
        if output_folder != "":
            for i, file in enumerate(sorted(glob.glob(os.path.join(
                output_folder,
                f"{self.user_id}_case{case_id}_method{method}_layer*.mha"
            )))):
                layer_name = os.path.basename(file).split(f"{self.user_id}_case{case_id}_method{method}_layer")[-1].replace(".mha", "")
                seg_sitk = sitk.ReadImage(file)
                seg = sitk.GetArrayFromImage(seg_sitk)
                seg_layer = ManualLabelsLayer(
                    seg,
                    name=f"{layer_name}",
                )
                seg_layer.colormap = self.colormap[i%self.colormap.num_colors]
                seg_layer.contour = 1
                seg_layer.scale = np.array([-1,1,1]) * np.array(img_sitk.GetSpacing()[::-1])  # reverse for napari xyz vs sitk zyx

                self._viewer.add_layer(seg_layer)
        
        # setup segmentation method widget
        if method == "manual":
            if self.automatic_segmentation_widget is not None:
                self.automatic_segmentation_widget.parent().hide()
            if self.manual_segmentation_widget is None:
                self.manual_segmentation_widget = ManualSegmentationWidget(self._viewer)
                self._viewer.window.add_dock_widget(
                    self.manual_segmentation_widget, name="Manual Segmentation", area="right"
                )
                self.manual_segmentation_widget.parent()._close_btn = False
            else:
                self.manual_segmentation_widget.allow_close = False
                self.manual_segmentation_widget.parent().show()
        elif method == "nnInteractive":
            if self.manual_segmentation_widget is not None:
                self.manual_segmentation_widget.allow_close = True
                self.manual_segmentation_widget.parent().hide()
            if self.automatic_segmentation_widget is None:
                from napari_nninteractive_minimal import nnInteractiveWidgetMinimal
                self.automatic_segmentation_widget = nnInteractiveWidgetMinimal(self._viewer)
                self._viewer.window.add_dock_widget(
                    self.automatic_segmentation_widget, name="nnInteractive Segmentation", area="right"
                )
                self.automatic_segmentation_widget.parent()._close_btn=False
            else:
                self.automatic_segmentation_widget.parent().show()
        
        self.update_task_counter()

        # reload edit log if existing
        with self.edit_log.events.cleared.blocker():
            self.edit_log.clear()

        if output_folder != "":
            edit_log_path = os.path.join(
                output_folder,
                f"{self.user_id}_case{case_id}_method{method}_edit_log.json"
            )
            try:
                if os.path.exists(edit_log_path):
                    with open(edit_log_path, 'r') as f:
                        self.edit_log._log = json.load(f)
            except Exception as e:
                pass

        self.edit_log.start()

        self.edit_log.record({
            'event_group': 'study',
            'event_type': "load_task",
            'timestamp': time.time()
        })

    def approve(self):
        if self.study_protocol.get("confirm_before_approving", True) and not self.confirm_dialog("Approve", "Are you sure the target object is delineated correctly? Once you approve this segmentation, you will not be able to edit this patient anymore"):
            return

        show_info(f"Approved task {self.study_tasks[self.current_task_index]['task_id']}. Saving results...")
        # write all label layers to disk
        method = self.study_tasks[self.current_task_index]["method"]
        case_id = self.study_tasks[self.current_task_index]["case_id"]
        output_folder = self.study_protocol.get("output_folder", "")

        for layer in self._viewer.layers:
            if isinstance(layer, Labels):
                output_path = os.path.join(
                    output_folder,
                    f"{self.user_id}_case{case_id}_method{method}_layer{layer.name}.mha"
                )
                layer_data = layer.data.astype(np.uint8)
                sitk_img = sitk.GetImageFromArray(layer_data)
                sitk.WriteImage(sitk_img, output_path, useCompression=True)
                
                #show_info(f"Saved layer {layer.name} to {output_path}")
                
        self.edit_log.record({
            'event_group': 'study',
            'event_type': "approve",
            'timestamp': time.time()
        })

        self.edit_log.stop()
        # output edit log to disk
        if output_folder != "":
            edit_log_path = os.path.join(
                output_folder,
                f"{self.user_id}_case{case_id}_method{method}_edit_log.json"
            )
            with open(edit_log_path, 'w') as f:
                json.dump(self.edit_log.log, f, indent=4)
            #show_info(f"Saved edit log to {edit_log_path}")
        
        #self.edit_log.clear()

        show_info(f"Saved results for task {self.study_tasks[self.current_task_index]['task_id']}.")

        # reveal if specified in protocol
        if self.approve_mode == "Reveal":
            if self.guidance_layer is not None:
                self._viewer.layers.remove(self.guidance_layer)
                self.guidance_layer = None

            mask_file = self.study_tasks[self.current_task_index].get("mask_file", None)
            if mask_file is not None:
                mask_sitk = sitk.ReadImage(mask_file)
                mask = sitk.GetArrayFromImage(mask_sitk)

                self.guidance_layer = PreviewLabelsLayer(
                    mask,
                    name=f'Ground Truth {case_id}',
                )
                self.guidance_layer.contour = 1
                self.guidance_layer.colormap = self.colormap[len(self._viewer.layers)%self.colormap.num_colors]
                self.guidance_layer.scale = np.array([-1,1,1]) * np.array(mask_sitk.GetSpacing()[::-1])  # reverse for napari xyz vs sitk zyx
                self.guidance_layer.opacity = 1.0
                self.guidance_layer.editable = False
                self._viewer.add_layer(self.guidance_layer)

        elif self.approve_mode == "Next":
            self.clear_task()
            if self.current_task_index < len(self.study_tasks) - 1:
                self.current_task_index += 1
                self.load_task(self.study_tasks[self.current_task_index])
            else:
                show_info("No more tasks to load.")
        elif self.approve_mode == "NextRemove":
            self.study_tasks.pop(self.current_task_index)
            self._task_combobox.removeItem(self.current_task_index)

            if self.current_task_index == -1: # All tasks done
                show_info("All tasks approved. Reopening study selection.")
                # close self and reopen study app loading widget to reset state
                self.hide()
                self.close()
                self._viewer.window.remove_dock_widget(self)

                self._viewer.window.add_dock_widget(
                    StudyAppWidget(self._viewer), name="ARTIST study", area="left"
                )
                
        self.update_task_counter()
        
    def _start_quicksave_timer(self, interval_seconds=60, check_intervall_seconds=1):
        @thread_worker(start_thread=False)
        def quicksave_periodically():
            _counter = interval_seconds
            while True:
                time.sleep(check_intervall_seconds)
                _counter -= check_intervall_seconds
                if _counter <= 0:
                    yield
                    _counter = interval_seconds
        
        thread = quicksave_periodically()
        thread.yielded.connect(self.quicksave)
        thread.start()
    
    def quicksave(self):
        show_info(f"Quicksaving task {self.study_tasks[self.current_task_index]['task_id']}. Saving results...")
        # write all label layers to disk
        method = self.study_tasks[self.current_task_index]["method"]
        case_id = self.study_tasks[self.current_task_index]["case_id"]
        output_folder = self.study_protocol.get("output_folder", "")

        # skip if no edits (only loading event)
        if len(self.edit_log.log) <= 2:
            return
        # check if there are any 'edit' events
        present_event_groups = set([event['event_group'] for event in self.edit_log.log])
        if "edit" not in present_event_groups:
            return

        for layer in self._viewer.layers:
            if isinstance(layer, Labels):
                output_path = os.path.join(
                    output_folder,
                    f"{self.user_id}_case{case_id}_method{method}_layer{layer.name}.mha"
                )
                layer_data = layer.data.astype(np.uint8)
                sitk_img = sitk.GetImageFromArray(layer_data)
                sitk.WriteImage(sitk_img, output_path, useCompression=True)
                
                #show_info(f"Saved layer {layer.name} to {output_path}")
        
        if output_folder != "":
            edit_log_path = os.path.join(
                output_folder,
                f"{self.user_id}_case{case_id}_method{method}_edit_log.json"
            )
            with open(edit_log_path, 'w') as f:
                json.dump(self.edit_log.log, f, indent=4)
            #show_info(f"Saved edit log to {edit_log_path}")
        
        #self.edit_log.clear()

    def modify_napari_ui(self):
        viewer = self._viewer

        def set_axial_view():
            viewer.dims.order = (0,1,2)
        def set_coronal_view():
            viewer.dims.order = (1,0,2)
        def set_saggital_view():
            viewer.dims.order = (2,0,1)
        axial_button = QPushButton()
        axial_button.setText("A")
        axial_button.clicked.connect(set_axial_view)
        axial_button.setStyleSheet("""
            min-width : 28px;
            max-width : 28px;
            min-height : 28px;
            max-height : 28px;
            padding: 0px;
            """)
           
        viewer.window._qt_viewer._viewerButtons.layout().insertWidget(-1,axial_button)
        axial_button = QPushButton()
        axial_button.setText("C")
        axial_button.clicked.connect(set_coronal_view)
        axial_button.setStyleSheet("""
            min-width : 28px;
            max-width : 28px;
            min-height : 28px;
            max-height : 28px;
            padding: 0px;
            """)
        viewer.window._qt_viewer._viewerButtons.layout().insertWidget(-1,axial_button)
        axial_button = QPushButton()
        axial_button.setText("S")
        axial_button.clicked.connect(set_saggital_view)
        axial_button.setStyleSheet("""
            min-width : 28px;
            max-width : 28px;
            min-height : 28px;
            max-height : 28px;
            padding: 0px;
            """)
        viewer.window._qt_viewer._viewerButtons.layout().insertWidget(-1,axial_button)

        def show_multi_view():

            if hasattr(self, 'multi_viewer_widget'):
                viewer.window.remove_dock_widget(self.multi_viewer_widget)
                #self.multi_viewer_widget.close()
                del self.multi_viewer_widget
            else:
                self.multi_viewer_widget = MultipleViewerWidget(viewer=viewer, orientation=Qt.Orientation.Vertical)
                viewer.window.add_dock_widget(
                    self.multi_viewer_widget, name="Multi-View", area="right"
                )
                self.multi_viewer_widget.parent()._close_btn = False
                self.multi_viewer_widget.parent().title.float_button.setHidden(True)

                #self.multi_viewer_widget.setParent(self, Qt.Window)
                #self.multi_viewer_widget.setWindowFlags(self.multi_viewer_widget.windowFlags() | Qt.Tool)
                #self.multi_viewer_widget.show()

        #axial_button = QPushButton()
        #axial_button.setText("M")
        #axial_button.clicked.connect(show_multi_view)
        #axial_button.setStyleSheet("""
        #    min-width : 28px;
        #    max-width : 28px;
        #    min-height : 28px;
        #    max-height : 28px;
        #    padding: 0px;
        #    """)
        #viewer.window._qt_viewer._viewerButtons.layout().insertWidget(-1,axial_button)

        # Hide viewer buttons since we offer our own functionality
        viewer.window._qt_viewer._viewerButtons.rollDimsButton.setHidden(True)
        viewer.window._qt_viewer._viewerButtons.transposeDimsButton.setHidden(True)
        viewer.window._qt_viewer._viewerButtons.consoleButton.setHidden(True)
        viewer.window._qt_viewer._viewerButtons.gridViewButton.setHidden(True)
        viewer.window._qt_viewer._viewerButtons.ndisplayButton.setHidden(True)

        # Hide layer list buttons
        viewer.window._qt_viewer._layersButtons.setHidden(True)

        # Hotwire to disable delete/backspace/enter keys in layer list
        self._prev_layer_keyPressEvent_handler = viewer.window._qt_viewer._layers.keyPressEvent
        def new_func(e):
            if e is None:
                return
            if e.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                e.ignore()
            else:
                self._prev_layer_keyPressEvent_handler(e)
        viewer.window._qt_viewer._layers.keyPressEvent = new_func
    
    def revert_napari_ui(self):
        viewer = self._viewer
        viewer.window._qt_viewer._viewerButtons.rollDimsButton.setHidden(False)
        viewer.window._qt_viewer._viewerButtons.transposeDimsButton.setHidden(False)
        viewer.window._qt_viewer._viewerButtons.consoleButton.setHidden(False)
        viewer.window._qt_viewer._viewerButtons.gridViewButton.setHidden(False)
        viewer.window._qt_viewer._viewerButtons.ndisplayButton.setHidden(False)

        viewer.window._qt_viewer._layersButtons.setHidden(False)

        viewer.window._qt_viewer._layers.keyPressEvent = self._prev_layer_keyPressEvent_handler
        del self._prev_layer_keyPressEvent_handler

        for i in range(3):
            viewer.window._qt_viewer._viewerButtons.layout().removeWidget(
                viewer.window._qt_viewer._viewerButtons.layout().itemAt(
                    viewer.window._qt_viewer._viewerButtons.layout().count()-1
                ).widget()
            )

    def showEvent(self, event):
        pass
    
    def closeEvent(self, event):
        #event.ignore()
        self.revert_napari_ui()

        if self.image_layer is not None:
            self._viewer.layers.remove(self.image_layer)
            self.image_layer = None

        if self.guidance_layer is not None:
            self._viewer.layers.remove(self.guidance_layer)
            self.guidance_layer = None
        
        if self.manual_segmentation_widget is not None:
            self.manual_segmentation_widget.allow_close = True
            self._viewer.window.remove_dock_widget(self.manual_segmentation_widget)
            self.manual_segmentation_widget.close()
            self.manual_segmentation_widget = None
            self.manual_segmentation_widget.deleteLater()
        
        if self.automatic_segmentation_widget is not None:
            self._viewer.window.remove_dock_widget(self.automatic_segmentation_widget)
            self.automatic_segmentation_widget.close()
            self.automatic_segmentation_widget = None
            self.automatic_segmentation_widget.deleteLater()

        for shortcut in self.study_protocol.get("contrast_shortcuts", {}).keys():
            self._viewer.bind_key(shortcut, ..., overwrite=True)
        
        if self.study_protocol.get("inverted_scrolling", False) and is_inverted(self._viewer):
            reset_scrolling(self._viewer)

        # reopen the study app widget
        widget = StudyAppWidget(self._viewer)
        self._viewer.window.add_dock_widget(
            widget, name="ARTIST study", area="left"
        )

    def hideEvent(self, event):
        # ignore
        event.ignore()
        pass

    def confirm_dialog(self, title, message):
        reply = QMessageBox.question(self, title, message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return reply == QMessageBox.Yes
