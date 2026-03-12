import json
from pathlib import Path

import threading
import time
import torch
import os
import cv2
from magicgui import magicgui
from typing import TYPE_CHECKING
import numpy as np
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
from .layer_select import setup_layerselect
from napari.utils.action_manager import action_manager
from napari.utils.events.event import WarningEmitter
from napari.qt.threading import thread_worker
from qtpy.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QVBoxLayout,
    QWidget
)
from qtpy.QtGui import (
    QTextOption
)
import traceback

from napari._qt.layer_controls.qt_layer_controls_container import layer_to_controls

from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification
import SimpleITK as sitk
from scipy.interpolate import interpn

def interpolate_labels(label_a, label_b, num_steps):
    sitk_img_a = sitk.GetImageFromArray(label_a)
    sitk_distance_map_a = sitk.GetArrayFromImage(sitk.ApproximateSignedDistanceMap(sitk_img_a))
    
    sitk_img_b = sitk.GetImageFromArray(label_b)
    sitk_distance_map_b = sitk.GetArrayFromImage(sitk.ApproximateSignedDistanceMap(sitk_img_b))
    
    distance_map= np.zeros((2,) + label_a.shape, dtype=np.float32)
    distance_map[0,:,:] = sitk_distance_map_a
    distance_map[1,:,:] = sitk_distance_map_b
    
    x, y, z = np.meshgrid(np.linspace(0, num_steps-1, num_steps), np.arange(label_a.shape[0]), np.arange(label_a.shape[1]))
    
    labels_interp = interpn((np.array([0,num_steps-1]), np.arange(label_a.shape[0]), np.arange(label_a.shape[1])), distance_map, np.array([x,y,z]).T, bounds_error=False, fill_value=0)
    labels_interp = labels_interp.transpose(1,2,0)
    labels_interp = (labels_interp <= 0).astype(np.uint8)
    return labels_interp

class ShapeBasedInterpolationWidget(QWidget):
    def __init__(self, viewer: Viewer):
        super().__init__()
        self._viewer = viewer

        self.current_layer = None
        self.current_index = None
        self.manual_frames = None
        self.silence_events = False

        main_layout = QVBoxLayout(self)

        _scroll_widget, _scroll_layout = setup_vscrollarea(main_layout)
        _scroll_layout.setContentsMargins(0,0,0,0)
        _scroll_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        _ = setup_label(
            _scroll_layout, "Select label layer:")
        # layer select for image layer
        self.layerselect_a = setup_layerselect(
            _scroll_layout, self._viewer, Labels, function=lambda: self.on_layer_change()
        )
        
        self.run_button = setup_iconbutton(
            _scroll_layout,
            "Interpolate",
            "right_arrow",
            self._viewer.theme,
            function=lambda: self.run_shape_based_interpolation()
        )

        _container, _layout = setup_vcollapsiblegroupbox(
            _scroll_layout, "Settings:", collapsed=False)

        self.overwrite_existing_mm_ckbx = setup_checkbox(
            _layout,
            "Overwrite other labels (irreversible)",
            False,
            tooltips="If unchecked, interpolated frames will only be added to empty regions. If checked, interpolations will overwrite existing labels."
        )

        #self.autorun_checkbox = setup_checkbox(
        #    _scroll_layout,
        #    "Auto Run",
        #    False)
        
        self.setup_connections()

        self.current_index = None
    def on_layer_change(self):
        pass
        """
        Connect transform events (scale/rotate/translate) of the selected
        image layer to preview and prompt layers so they follow image
        transformations.
        """
        if self.current_layer is not None:
            self.current_layer.events.set_data.disconnect(self._on_set_data)
            self.current_layer.events.labels_update.disconnect(self._on_labels_update)
            self.current_layer.events.selected_label.disconnect(self.on_selected_label_update)
            self.current_layer = None

        label_layer, img_layer_idx = get_value(self.layerselect_a)

        if label_layer not in self._viewer.layers:
            return
        
        self.setup_connections()

    @thread_worker(start_thread=True)
    def run_shape_based_interpolation(self):

        if self.current_layer is None:
            show_warning("Please select a valid label layer.")
            return
        label_layer = self.current_layer

        label_data = np.transpose(label_layer.data, self._viewer.dims.order)
        N = len(label_data.shape)

        if N != 3:
            show_warning("Shape base interpolation only works on 3D data.")
            return
        
        current_index = self._viewer.dims.current_step[self._viewer.dims.order[0]]

        if label_layer.selected_label == 0:
            show_warning("Please select a valid label (non-zero).")
            return

        new_labels = label_data.copy()

        if self.manual_frames is not None and len(self.manual_frames) >= 2:
            non_empty_labels = self.manual_frames
        else:
            non_empty_labels = np.where(new_labels.sum(axis=(1,2)) == label_layer.selected_label)[0]
            self.manual_frames = non_empty_labels.tolist().sort()

        if len(non_empty_labels) < 2:
            if np.where(new_labels.sum(axis=(1,2)) >= 0)[0].shape[0] < 2:
                show_warning("At least two frames with labels are required for shape based interpolation. Did you select the correct label index?")
                return
            show_warning("At least two frames with labels are required for shape based interpolation.")
            return

        #print(non_empty_labels)
        # for each pair of non empty labels, interpolate
        for i in range(len(non_empty_labels) - 1):
            frame_a = non_empty_labels[i]
            frame_b = non_empty_labels[i+1]
            num_steps = frame_b - frame_a + 1
            if num_steps <= 2:
                continue
            #print(f"Interpolating between frames {frame_a} and {frame_b} with {num_steps} steps.")
            labels_a = (label_data[frame_a] == label_layer.selected_label).astype(np.uint8)
            labels_b = (label_data[frame_b] == label_layer.selected_label).astype(np.uint8)
            
            labels_interp = interpolate_labels(labels_a, labels_b, num_steps)
            
            labels_interp = labels_interp[1:-1] * label_layer.selected_label

            # assign interpolated labels to new_labels if not overwriting existing
            overlayed = np.logical_or(new_labels[frame_a+1:frame_b] == 0, new_labels[frame_a+1:frame_b] == label_layer.selected_label)
            
            if get_value(self.overwrite_existing_mm_ckbx):
                overlayed = np.logical_or(overlayed, labels_interp == label_layer.selected_label)
            
            #labels_to_assign[overlayed] = new_labels[frame_a+1:frame_b][overlayed]
            new_labels[frame_a+1:frame_b][overlayed] = labels_interp[overlayed]

        non_empty_labels_new = np.where(new_labels.sum(axis=(1,2)) != 0) 
        self.silence_events = True
        np.copyto(label_data, new_labels)
        self.silence_events = False
        label_layer.refresh()
        show_info("Shape based interpolation completed.")

    def setup_connections(self):
        label_layer, img_layer_idx = get_value(self.layerselect_a)
        if label_layer is None or img_layer_idx == -1 or label_layer not in self._viewer.layers:
            return
        label_layer = self._viewer.layers[label_layer]
        self.current_layer = label_layer

        self.current_layer.events.set_data.connect(self._on_set_data)
        self.current_layer.events.labels_update.connect(self._on_labels_update)
        self.current_layer.events.selected_label.connect(self.on_selected_label_update)
    
    def _on_set_data(self, event):
        """sync data modification from additional viewers"""
        # Ignore in-progress events for performance reasons
        if hasattr(event, 'action') and event.action in ['adding', 'removing', 'changing']:
            return

        if self.silence_events:
            return

    def _on_labels_update(self, event):
        """sync data modification from additional viewers"""
        # Ignore in-progress events for performance reasons
        if hasattr(event, 'action') and event.action in ['adding', 'removing', 'changing']:
            return

        if self.silence_events:
            return

        # add current frame to manual frames
        current_index = self._viewer.dims.current_step[self._viewer.dims.order[0]]
        if self.current_index is None or self.current_index != current_index:
            self.current_index = current_index
        else:
            return

        if self.manual_frames is None:
            self.manual_frames = [current_index]
        elif current_index not in self.manual_frames:
            self.manual_frames.append(current_index)
            self.manual_frames.sort()

    def on_selected_label_update(self, event):
        if self.current_layer is None:
            #show_warning("Please select a valid label layer.")
            return
        label_layer = self.current_layer
        
        selected_label = label_layer.selected_label

        # reset manual frames
        self.manual_frames = None

    def showEvent(self, event):
        self.setup_connections()
    
    def closeEvent(self, event):
        self.hideEvent(event)

    def hideEvent(self, event):
        self.manual_frames = None

        if self.current_layer is None:
            return
        self.current_layer.events.set_data.disconnect(self._on_set_data)
        self.current_layer.events.labels_update.disconnect(self._on_labels_update)
        self.current_layer.events.selected_label.disconnect(self.on_selected_label_update)
        self.current_layer = None