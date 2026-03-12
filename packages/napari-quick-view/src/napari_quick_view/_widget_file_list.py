import json
from pathlib import Path

import threading
import time
import torch
import os
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
import glob
from napari._qt.layer_controls.qt_layer_controls_container import layer_to_controls

from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification
from napari import Viewer
import SimpleITK as sitk

class FileListWidget(QWidget):
    def __init__(self, viewer, parent_layout, on_file_selected=lambda x: None):
        super().__init__()
        self._viewer = viewer
        self.on_file_selected = on_file_selected
        
        # File input
        _scroll_layout = parent_layout

        _container, _layout = setup_vcollapsiblegroupbox(
            _scroll_layout, "Folder selection:", collapsed=False)
        _ = setup_label(
            _layout, "Select a folder from which to ingress files.")

        self.import_dir_select = setup_dirselect(
            _layout,
            "Folder:",
            function=lambda: print("QDirSelect")
        )

        _ = setup_label(_layout, "Optionally provide a glob pattern: (relative to folder)")

        self.import_glob = setup_lineedit(_layout, "**/*.mha", "**/*.mha", function=lambda: print("QTextEdit"))

        _ = setup_iconbutton(
            _layout, "Load glob", "right_arrow", self._viewer.theme, self.load_file_list
        )
        self.count_label = setup_label(_layout, "No files loaded.")
        self.count_label.setVisible(False)

        self.select_file_container, _layout = setup_vcollapsiblegroupbox(
            _scroll_layout, "File selection:", collapsed=False)
        self.select_file_container.setVisible(False)
        # select qbox
        _ = setup_label(
            _layout, "Select a file:")
    
        self.file_select = setup_combobox(_layout, [], "No files available", function=lambda: None)
        
        #self.file_select =setup_list(_layout, [], "No files available", function=lambda: None)
        # buttons for cycling through labels

        # load button
        hstack(_layout, [ 
            setup_iconbutton(
                _layout, "Load", "right_arrow", self._viewer.theme, self.load_selected_file
            ),
            setup_iconbutton(
                _layout, "Load Next", "right_arrow", self._viewer.theme, self.load_next_file
            )], stretch=[0,0])


    def load_file_list(self):
        base_dir = self.import_dir_select.get_dir()
        glob_pattern = self.import_glob.text()

        file_list = glob.glob(os.path.join(base_dir, glob_pattern), recursive=True)
        file_list = sorted(file_list)
        file_list = [os.path.relpath(f, base_dir) for f in file_list]
        #print(file_list)
        self.file_select.clear()
        self.file_select.addItems(file_list)
        self.file_select.setCurrentIndex(0)
        if len(file_list) == 0:
            show_warning("No files found.")
            self.count_label.setText("No files found.")
            self.count_label.setVisible(True)
            self.select_file_container.setVisible(False)
        else:
            self.count_label.setText(f"{len(file_list)} files found.")
            self.count_label.setVisible(True)
            self.select_file_container.setVisible(True)

    def load_selected_file(self):
        show_info(f"Loading file:")
        base_dir = self.import_dir_select.get_dir()
        selected_file = self.file_select.currentText()
        full_path = os.path.join(base_dir, selected_file)
        #print(full_path)
        self.on_file_selected(full_path)

    def load_next_file(self):
        current_index = self.file_select.currentIndex()
        if current_index + 1 < self.file_select.count():
            self.file_select.setCurrentIndex(current_index + 1)
            self.load_selected_file()
        else:
            show_info("No more files to load.")


    # Setup / Teardown events
    def showEvent(self, event):
        pass
    
    def closeEvent(self, event):
        self.hideEvent(event)

    def hideEvent(self, event):
        pass