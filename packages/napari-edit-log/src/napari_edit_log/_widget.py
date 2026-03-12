import json
from pathlib import Path

import threading
import time
import cv2
import base64
import zlib
from magicgui import magicgui
from napari.layers import Image
from typing import TYPE_CHECKING
from functools import partial
import numpy as np
from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification
from napari import Viewer
from napari.layers import Labels
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
    setup_labeledslider,
    setup_pushbutton,
    setup_radiobutton,
    setup_savefileselect,
    setup_dirselect,
    setup_spinbox,
)
from napari.qt.threading import thread_worker
from qtpy.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from napari_edit_log.utils import encode_labels_event_data, decode_labels_event_data

from napari_edit_log.utils import encode_labels_event_data, decode_labels_event_data
from napari.utils.events import EventEmitter, EmitterGroup, Event, EventedList
from napari_edit_log.edit_log import NapariEditLog

class EditLogWidget(QWidget):
    def __init__(self, viewer: Viewer):
        super().__init__()
        self._viewer = viewer

        self.metadata = {}
        self.edit_log = NapariEditLog(viewer)

        self.edit_log.events.recorded.connect(self._on_log_recorded)
        self.edit_log.events.updated.connect(self._on_log_updated)
        self.edit_log.events.cleared.connect(self._on_log_cleared)

        self.build_gui()

    def _on_log_recorded(self):
        # update log view
        log_entry = self.edit_log.log[-1]
        i = len(self.edit_log.log)
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(log_entry['timestamp']))
        item_text = f"{i}. [{timestamp}] {log_entry['event_group']} - {log_entry['event_type']}"
        self.past_state_list.addItem(item_text)

    def _on_log_updated(self):
        # update log view
        log_entry = self.edit_log.log[-1]
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(log_entry['timestamp']))
        item_text = f"{len(self.edit_log.log)}. [{timestamp}] {log_entry['event_group']} - {log_entry['event_type']}"
        self.past_state_list.item(self.past_state_list.count()-1).setText(item_text)

    def _on_log_cleared(self):
        # update log view
        self.past_state_list.clear()
        
    @property
    def recording(self):
        return self.edit_log.is_recording

    # GUI
    def build_gui(self):
        main_layout = QVBoxLayout(self)

        _scroll_widget, _scroll_layout = setup_vscrollarea(main_layout)


        # buttons for recording and exporting
        _container, _layout = setup_vgroupbox(_scroll_layout, "")

        self.toogle_recording_btn = setup_pushbutton(_layout, "Start Recording", function=self.toogle_recording)
        
        # log view
        _container, _layout = setup_vcollapsiblegroupbox(_scroll_layout, "Log", False)

        self.past_state_list = setup_list(_layout, [], True, function=lambda: print("QListWidget"))
        _ = setup_iconbutton(
            _layout, "Clear Log", "erase", self._viewer.theme, self.clear_log
        )

        _container, _layout = setup_vgroupbox(_scroll_layout, "")
        _ = setup_iconbutton(
            _layout, "Export", "pop_out", self._viewer.theme, self.export_log
        )

    def export_log(self):
        print("Exporting edit log...")

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Edit Log", "", "JSON Files (*.json)")

        if not file_path:
            return

        with open(file_path, 'w') as f:
            json.dump(self.edit_log.log, f, indent=2)
        
        show_info(f"Edit log saved to {file_path}")

    def clear_log(self):
        self.edit_log.clear()
        self.past_state_list.clear()

    def toogle_recording(self):
        self.edit_log.toggle()
        if self.recording == False:
            self.toogle_recording_btn.setText("Start Recording")
        else:
            self.toogle_recording_btn.setText("Pause Recording")

   