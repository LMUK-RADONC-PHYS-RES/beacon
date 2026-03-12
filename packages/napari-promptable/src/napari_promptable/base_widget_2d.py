import json
import numpy as np
import threading
import torch
import os
import cv2
from functools import partial
from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification
from napari import Viewer
from napari.layers import Labels, Shapes, Points, Image, Layer
from napari_toolkit.utils import set_value
from napari_toolkit.utils.widget_getter import get_value
from napari_toolkit.widgets import *

import traceback

from .base_widget import BaseWidget


class BaseWidget2D(BaseWidget):
    def __init__(self, viewer: Viewer, **kwargs):
        super().__init__(viewer, **kwargs)

    @property
    def supported_prompt_types(self):
        return ["Points", "BBox", "Mask"]

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

    def update_prompt_type(self):
        super().update_prompt_type()
        self.run_button.setEnabled(True)

    # GUI

    def setup_view_control_gui(self, _scroll_layout):
        pass

    def closeEvent(self, event=None):
        super().closeEvent(event=event)
