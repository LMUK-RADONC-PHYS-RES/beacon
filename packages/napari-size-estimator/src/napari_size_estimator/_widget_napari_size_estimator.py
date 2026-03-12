import json
from pathlib import Path

import threading
import time
import torch
import os
import cv2
from magicgui import magicgui
from napari.layers import Image
from typing import TYPE_CHECKING
from functools import partial
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
from .file_select import setup_dirselect
from .layer_select import setup_layerselect
from napari.utils.action_manager import action_manager
from napari.utils.events.event import WarningEmitter
from napari.utils.notifications import show_info
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
import glob
from napari._qt.layer_controls.qt_layer_controls_container import layer_to_controls

from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification
from napari import Viewer
import SimpleITK as sitk
from scipy.interpolate import interpn



class SizeEstimatorWidget(QWidget):
    def __init__(self, viewer: Viewer):
        super().__init__()
        self._viewer = viewer

        # Label select -> Labels layer

        # Size variables x,y,z

        # Output layer
        # Volume, Surface area, Mean Diameter, etc.
        self.current_layer = None
        self.silence_events = False
        self.is_running = False
        self.should_run = False

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
  
        _container, _layout = setup_vcollapsiblegroupbox(
            _scroll_layout, "Resolution:", collapsed=False)

        _resolution_label_x = setup_label(
            None, "Resolution in x:")
        self.resolution_x_spinbox = setup_doublespinbox(
            None,
            default=1.0,
            minimum=0.01,
            maximum=1000.0,
            step_size=0.1,
            )
        _ = hstack(_layout, [_resolution_label_x, self.resolution_x_spinbox], stretch=[0, 1])

        _resolution_label_y = setup_label(
            None, "Resolution in y:")
        self.resolution_y_spinbox = setup_doublespinbox(
            None,
            default=1.0,
            minimum=0.01,
            maximum=1000.0,
            step_size=0.1,
            )
        _ = hstack(_layout, [_resolution_label_y, self.resolution_y_spinbox], stretch=[0, 1])

        _resolution_label_z = setup_label(
            None, "Resolution in z:")
        self.resolution_z_spinbox = setup_doublespinbox(
            None,
            default=1.0,
            minimum=0.01,
            maximum=1000.0,
            step_size=0.1,
            )
        _ = hstack(_layout, [_resolution_label_z, self.resolution_z_spinbox], stretch=[0, 1])

        self.run_button = setup_iconbutton(
            _scroll_layout,
            "Run",
            "right_arrow",
            self._viewer.theme,
            function=lambda: self.run_size_estimation(),
        )
        
        self.autorun_checkbox = setup_checkbox(
            _scroll_layout,
            "Autorun",
            False)
        
        _ = setup_label(
            _scroll_layout, "Output:")
              
        self.text_output = setup_plaintextedit(
            _scroll_layout,
            "",
            readonly=True,
        )

        self.setup_connections()

    def run_size_estimation(self):
        label_layer, img_layer_idx = get_value(self.layerselect_a)
        if label_layer is None or img_layer_idx == -1 or label_layer not in self._viewer.layers:
            show_warning("Please select a valid label layer.")
            return
        label_layer = self._viewer.layers[label_layer]

        # get resolution
        res_x = self.resolution_x_spinbox.value()
        res_y = self.resolution_y_spinbox.value()
        res_z = self.resolution_z_spinbox.value()
        res = np.array((res_z, res_y, res_x))  # z,y,x order

        output = {}
        # iterate over labels
        for label in np.unique(label_layer.data):
            if label == 0:
                continue  # skip background

            # create binary mask for current label
            binary_mask = (label_layer.data == label).astype(np.uint8)

            # compute volume
            voxel_volume = np.prod(res)
            label_volume = np.sum(binary_mask) * voxel_volume
            output[str(label)] = float(label_volume)
        
        self.text_output.setPlainText(
            json.dumps(output, indent=4)
        )
    
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
            self.current_layer = None

        label_layer, img_layer_idx = get_value(self.layerselect_a)

        if label_layer not in self._viewer.layers:
            return
        
        self.setup_connections()

    def setup_connections(self):
        label_layer, img_layer_idx = get_value(self.layerselect_a)
        if label_layer is None or img_layer_idx == -1 or label_layer not in self._viewer.layers:
            return
        label_layer = self._viewer.layers[label_layer]
        self.current_layer = label_layer

        self.current_layer.events.set_data.connect(self._on_set_data)
        self.current_layer.events.labels_update.connect(self._on_labels_update)
    
    def _on_set_data(self, event):
        """sync data modification from additional viewers"""
        # Ignore in-progress events for performance reasons
        if hasattr(event, 'action') and event.action in ['adding', 'removing', 'changing']:
            return

        if self.silence_events or not get_value(self.autorun_checkbox):
            return

        self.run_size_estimation()

    def _on_labels_update(self, event):
        """sync data modification from additional viewers"""
        # Ignore in-progress events for performance reasons
        if hasattr(event, 'action') and event.action in ['adding', 'removing', 'changing']:
            return

        if self.silence_events or not get_value(self.autorun_checkbox):
            return
        
        #if self.is_running:
        #    self.should_run = True
        #else:
        self.run_size_estimation()

        # add current frame to manual frames

    # Setup / Teardown events
    def showEvent(self, event):
        pass
    
    def closeEvent(self, event):
        self.hideEvent(event)

    def hideEvent(self, event):
        if self.current_layer is None:
            return
        self.current_layer.events.set_data.disconnect(self._on_set_data)
        self.current_layer.events.labels_update.disconnect(self._on_labels_update)
        self.current_layer = None
