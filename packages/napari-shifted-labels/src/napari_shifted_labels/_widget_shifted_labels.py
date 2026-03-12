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
from .layer_select import setup_layerselect
from napari.utils.action_manager import action_manager
from napari.utils.events.event import WarningEmitter
from napari.utils.notifications import show_info
from napari.qt.threading import thread_worker
from qtpy.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
import traceback

from napari._qt.layer_controls.qt_layer_controls_container import layer_to_controls

from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification
from napari import Viewer

def copy_layer(layer: Layer):
    data, state, layer_type_strin = layer.as_layer_data_tuple()
    res_layer = layer.__class__(layer.data, **state)
    #res_layer.metadata['viewer_name'] = name
    return res_layer

def get_property_names(layer: Layer):
    klass = layer.__class__
    res = []
    for event_name, event_emitter in layer.events.emitters.items():
        if isinstance(event_emitter, WarningEmitter):
            continue
        #if event_name in ('thumbnail', 'name', 'visible', 'selected'):
        #    continue
        if event_name not in ('scale', 'rotate', 'translate', 'affine'):
            continue
        if (
            isinstance(getattr(klass, event_name, None), property)
            and getattr(klass, event_name).fset is not None
        ):
            res.append(event_name)
    return res

class own_partial:
    """
    Workaround for deepcopy not copying partial functions
    (Qt widgets are not serializable)
    """

    def __init__(self, func, *args, **kwargs) -> None:
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *args, **kwargs):
        return self.func(*(self.args + args), **{**self.kwargs, **kwargs})

    def __deepcopy__(self, memodict=None):
        if memodict is None:
            memodict = {}
        return own_partial(
            self.func,
            *deepcopy(self.args, memodict),
            **deepcopy(self.kwargs, memodict),
        )

class ShiftedLabelsWidget(QWidget):
    def __init__(self, viewer: Viewer):
        super().__init__()
        self._viewer = viewer

        self.copied_layer = None
        
        self.preview_layer = None  # Layer to show the preview of the segmentation
        self.preview_label_data = None  # Data Label for the preview layer

        main_layout = QVBoxLayout(self)

        _scroll_widget, _scroll_layout = setup_vscrollarea(main_layout)
        
        setup_label(_scroll_layout, "Select label layer:")

        # layer select for image layer
        self.layerselect_a = setup_layerselect(
            _scroll_layout, self._viewer, Labels
        )

        setup_label(_scroll_layout, "Frame shift amount:")
        self.offset_number = setup_spinbox(
            _scroll_layout,
            default=-1,
            minimum=-5,
            maximum=5,
            step_size=1,
            function=lambda value: self.sync_data()
        )

        self.run_button = setup_iconbutton(
            _scroll_layout,
            "Start",
            "right_arrow",
            self._viewer.theme,
            function=lambda: self.on_layer_change()
        )

        self.setup_connections()
        # setup on start
        self.on_layer_change()

    def clear(self):
        if self.preview_layer is not None and self.preview_layer in self._viewer.layers:
            self._viewer.layers.remove(self.preview_layer)
            self.preview_layer = None
            
        if self.copied_layer is not None:
            # remove old connections
            for name in get_property_names(self.copied_layer):
                getattr(self.copied_layer.events, name).disconnect(
                    own_partial(self._property_sync, name)
                )

            if isinstance(self.copied_layer, Labels):
                self.copied_layer.events.set_data.disconnect(self._set_data_refresh)
                self.copied_layer.events.labels_update.disconnect(self._set_data_refresh)

            self.copied_layer.events.name.disconnect(self._sync_name)
        self.copied_layer = None

    def on_layer_change(self):
        pass
        """
        Connect transform events (scale/rotate/translate) of the selected
        image layer to preview and prompt layers so they follow image
        transformations.
        """
        label_layer, img_layer_idx = get_value(self.layerselect_a)

        if self.copied_layer is not None and self.copied_layer in self._viewer.layers and self._viewer.layers[label_layer] == self.copied_layer:
            return
        print("Layer changed")

        if self.preview_layer is not None:
            # remove old
            if self.preview_layer in self._viewer.layers:
                self._viewer.layers.remove(self.preview_layer)
            self.preview_layer = None

        if label_layer is None or img_layer_idx == -1:
            self.copied_layer = None
            return
        
        self.setup_connections()

        self.layerselect_a.filter_function = lambda layer, name: layer is not self.preview_layer

    def setup_connections(self):
        label_layer, img_layer_idx = get_value(self.layerselect_a)
        if label_layer is None or img_layer_idx == -1 or label_layer not in self._viewer.layers:
            return
        #print(f"Label layer selected: {label_layer}, idx: {img_layer_idx}")

        label_layer = self._viewer.layers[label_layer]
        self.copied_layer = label_layer
      
        self.preview_layer = self._viewer.add_labels(
            data=self.copied_layer.data.copy(),
            name="(shifted) " + self.copied_layer.name,
            opacity=0.5,
            visible=True,
        )
        self.preview_layer.contour = 0
        self.preview_layer.editable = False

        for name in get_property_names(self.copied_layer):
            getattr(self.copied_layer.events, name).connect(
                own_partial(self._property_sync, name)
            )

        if isinstance(self.copied_layer, Labels):
            self.copied_layer.events.set_data.connect(self._set_data_refresh)
            self.copied_layer.events.labels_update.connect(self._set_data_refresh)

        self.copied_layer.events.name.connect(self._sync_name)

    def sync_data(self):
        """Initial sync of data from source layer to preview layer"""
        if self.copied_layer is None or self.preview_layer is None:
            return

        offset = get_value(self.offset_number)
        if offset == 0:
            self.preview_layer.data = self.copied_layer.data.copy()
            self.preview_layer.refresh()
            return

        self.preview_layer.data = np.roll(self.copied_layer.data.copy(), -offset, axis=self._viewer.dims.order[0])
        np.transpose(self.preview_layer.data, self._viewer.dims.order)[0] = 0

        self.preview_layer.refresh()

    def _sync_name(self, event):
        """sync name of layers"""
        self.preview_layer.name = "(shifted) " + event.source.name

    def _sync_data(self, event):
        """sync data modification from additional viewers"""
        # Ignore in-progress events for performance reasons
        if hasattr(event, 'action') and event.action in ['adding', 'removing', 'changing']:
            return

        #self.preview_layer.data = event.source.data.copy() + 1

    def _set_data_refresh(self, event):
        """sync data modification from additional viewers"""
        # Ignore in-progress events for performance reasons
        if hasattr(event, 'action') and event.action in ['adding', 'removing', 'changing']:
            return

        self.sync_data()

    def _property_sync(self, name, event):
        """Sync layers properties (except the name)"""
        if event.source not in self._viewer.layers:
            return

        setattr(self.preview_layer, name, getattr(event.source, name))

    def closeEvent(self, event):
        if self.preview_layer is not None and self.preview_layer in self._viewer.layers:
            self._viewer.layers.remove(self.preview_layer)

    def hideEvent(self, event):
        if self.preview_layer is not None and self.preview_layer in self._viewer.layers:
            self._viewer.layers.remove(self.preview_layer)