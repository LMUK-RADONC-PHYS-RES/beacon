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
from napari_toolkit.widgets import (
    setup_checkbox,
    setup_combobox,
    setup_editcolorpicker,
    setup_editdoubleslider,
    setup_iconbutton,
    setup_label,
    setup_lineedit,
    setup_fileselect,
    setup_savefileselect,
    setup_labeledslider,
    setup_pushbutton,
    setup_hswitch,
    setup_radiobutton,
    setup_savefileselect,
    setup_dirselect,
    setup_spinbox,
)
from .layer_select import setup_layerselect

from napari.qt.threading import thread_worker, create_worker
from qtpy.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QMessageBox
)
import traceback

from napari._qt.layer_controls.qt_layer_controls_container import layer_to_controls

from napari.layers import Shapes, Points, Labels
from contextlib import contextmanager

from .base_widget import BaseWidget


class BaseWidget3D(BaseWidget):
    """Base class for 3D interactive segmentation widgets.

    This class extends the generic BaseWidget with
    helpers for orthogonal (three-view) prompting. It tracks whether a
    prompt (contour/mask) has been set for each orthogonal view and the
    associated slice/index for each view. Subclasses should implement
    model-specific methods like ``load_model``, ``predict`` and
    ``reset_model``.
    """

    def __init__(self, viewer: Viewer):
        """Initialize 3D prompt-tracking state.

        The constructor initializes boolean flags that indicate whether a
        prompt has been set for each of the three orthogonal views and
        stores the index (slice) for each view. These are used to control
        when prediction is allowed to run in multi-view workflows.
        """
        super().__init__(viewer)
        self.prompt_frame_set_view_1 = False
        self.prompt_frame_set_view_2 = False
        self.prompt_frame_set_view_3 = False

        self.prompt_frame_index_view_1 = 0
        self.prompt_frame_index_view_2 = 0
        self.prompt_frame_index_view_3 = 0

    @property
    def supported_prompt_types(self):
        return ["Mask"]  # ["Points", "BBox", "Mask"]

    def load_model(self):
        pass

    def predict(self):
        pass

    def reset_model(self):
        pass

    def setup_hyperparameter_gui(self, _layout):
        pass

    def setup_model_selection_gui(self, _scroll_layout):
        pass

    # GUI
    def setup_view_control_gui(self, _scroll_layout):
        """Build the view control section of the GUI.

        Adds a switch to choose the active orthogonal view, three progress
        indicators showing whether a prompt has been set for each view, and
        a button that copies the current mask into the prompt set for the
        selected view.
        """
        _container, _layout = setup_vgroupbox(_scroll_layout, "View Control:")
        self.view_select = setup_hswitch(
            _layout, ["View A", "View B", "View C"], default=0, function=lambda: self.set_view())

        # Progress indicatoin
        setup_label(_layout, "Progress:")
        self.progress_indicator_1 = setup_checkbox(
            _layout, "Contour in view 1", False)
        self.progress_indicator_1.setDisabled(True)
        self.progress_indicator_2 = setup_checkbox(
            _layout, "Contour in view 2", False)
        self.progress_indicator_2.setDisabled(True)
        self.progress_indicator_3 = setup_checkbox(
            _layout, "Contour in view 3", False)
        self.progress_indicator_3.setDisabled(True)

        # Button to set the current mask as prompt
        self.set_prompt_button = setup_iconbutton(
            _layout,
            "Set Prompt",
            "check",
            self._viewer.theme,
            function=lambda: self.set_current_view_prompt(),
            tooltips="Set the current mask as prompt.",
        )

    def set_view(self):
        """Switch the viewer dimension ordering based on the selected view.

        This method updates ``self._viewer.dims.order`` so that the napari
        display presents the chosen orthogonal slice ordering. If a caller
        wants to automatically set prompts on view change, they can call
        ``set_current_view_prompt`` (optionally controlled by a checkbox).
        """
        # Set the current view based on the selected option in the view_select widget
        selected_view = get_value(self.view_select)[1]

        print(f"Selected View: {selected_view}")

        current_view = self._viewer.dims.order[0]
        print(f"Current Order: {current_view}")

        # Update the prompt type based on the current view
        # if get_value(self.auto_set_prompt_ckbx):
        #    self.set_current_view_prompt(view=selected_view)

        if selected_view == 0:
            # Set the order of dimensions to A
            self._viewer.dims.order = (0, 1, 2)
        elif selected_view == 1:
            self._viewer.dims.order = (1, 0, 2)
        elif selected_view == 2:
            self._viewer.dims.order = (2, 0, 1)

    def increment_object_id(self):
        """Increment the current object id and reset orthogonal prompting.

        When the active object changes in a multi-object workflow, any
        previously-set orthogonal prompts are cleared so that the new
        object can be defined from scratch.
        """
        self.reset_orthogonal_prompting()
        super().increment_object_id()

    def reset_orthogonal_prompting(self):
        """Clear all orthogonal prompt flags and reset indices.

        This helper returns the widget to a state where no view prompts are
        considered set and disables the Predict button until new prompts are
        provided.
        """
        self.prompt_frame_set_view_1 = False
        self.prompt_frame_set_view_2 = False
        self.prompt_frame_set_view_3 = False

        self.prompt_frame_index_view_1 = 0
        self.prompt_frame_index_view_2 = 0
        self.prompt_frame_index_view_3 = 0
        self.run_button.setEnabled(False)

    def set_current_view_prompt(self, view=None):
        """Set the current mask as the prompt for the chosen orthogonal view.

        Args:
            view: optional int 0/1/2 indicating which orthogonal view to set.
                  If None, the currently selected view in the GUI is used.

        This method records that a prompt (mask/contour) exists for the
        selected view, stores the corresponding slice index, updates the
        progress indicator text and, if all three view prompts are present,
        enables the Predict button and optionally triggers an automatic run
        if autorun is enabled.
        """
        if view is None:
            view = get_value(self.view_select)[1]

        print(f"Setting prompt for view: {view}")

        mask_prompt_layer = self.prompt_layers['mask']
        prompt_frames = self._viewer.dims.current_step
        # prompt_frames = [self.prompt_frame_index_view_1, self.prompt_frame_index_view_2, self.prompt_frame_index_view_3]
        # mask_0 = np.take(mask_prompt_layer.data,prompt_frames[view], axis=view)  # Take the mask along the current view axis

        if view == 0:
            self.prompt_frame_set_view_1 = True
            self.prompt_frame_index_view_1 = prompt_frames[0]
            set_value(self.progress_indicator_1, self.prompt_frame_set_view_1)
            self.progress_indicator_1.setText(
                f"Contour in view 1 (slice {self.prompt_frame_index_view_1})")
        elif view == 1:
            self.prompt_frame_set_view_2 = True
            self.prompt_frame_index_view_2 = prompt_frames[1]
            set_value(self.progress_indicator_2, self.prompt_frame_set_view_2)
            self.progress_indicator_2.setText(
                f"Contour in view 2 (slice {self.prompt_frame_index_view_2})")
        elif view == 2:
            self.prompt_frame_set_view_3 = True
            self.prompt_frame_index_view_3 = prompt_frames[2]
            set_value(self.progress_indicator_3, self.prompt_frame_set_view_3)
            self.progress_indicator_3.setText(
                f"Contour in view 3 (slice {self.prompt_frame_index_view_3})")

        if self.prompt_frame_set_view_1 and self.prompt_frame_set_view_2 and self.prompt_frame_set_view_3:
            self.run_button.setEnabled(True)
            if get_value(self.autorun_ckbx):
                self.run_predict_in_thread()

    def closeEvent(self, event=None):
        super().closeEvent(event=event)
        self.prompt_frame_set_view_1 = False
        self.prompt_frame_set_view_2 = False
        self.prompt_frame_set_view_3 = False
