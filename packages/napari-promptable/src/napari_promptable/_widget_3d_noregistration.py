import json
from pathlib import Path
import threading
import time
import torch
import os
import cv2
from magicgui import magicgui
from napari.layers import Image
import numpy as np
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
    setup_layerselect,
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
import traceback

from .base_widget_3d import BaseWidget3D


class PromptableSegmentationWidget3DNoRegistration(BaseWidget3D):
    def __init__(self, viewer: Viewer, **kwargs):
        super().__init__(viewer, **kwargs)

    def setup_hyperparameter_gui(self, _layout):
        pass

    def setup_model_selection_gui(self, _scroll_layout):
        pass

    def on_model_change(self):
        self.reset_model()
        self.load_model()

    def load_model(self):
        pass

    def reset_model(self):
        pass

    def predict(self):
        show_info("NoRegistration model used. Empty preview mask")
        pass
