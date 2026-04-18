from collections import deque
from contextlib import contextmanager
import copy
from app_model.types import KeyCode, KeyMod

import numpy as np
from napari.layers import Points
from napari.utils.events import Event

from napari._qt.layer_controls.qt_layer_controls_container import layer_to_controls
from napari_beacon_layers.controls.manual_points_control import CustomQtManualPointsControls


class ManualPointsLayer(Points):
    """Editable points layer with keyboard-driven undo/redo history.
    """

    def __init__(self, data=None, *args, max_history=100, **kwargs):
        super().__init__(data, *args, **kwargs)
        self._history_limit = max(1, int(max_history))
        self._reset_history()
        self._last_history_state = self._snapshot_data()
        self._is_restoring_history = False

        self.events.add(load_history=Event, undo=Event, redo=Event)
        self.events.data.connect(self._on_data_change)
        self.events.face_color.connect(self.on_face_color_change)
        self.events.border_color.connect(self.on_border_color_change)
        self.events.size.connect(self.on_size_change)

    def _snapshot_data(self) -> np.ndarray:
        return (np.asarray(self.data).copy(), list(self.selected_data), self.face_color.copy(), self.border_color.copy(), self.size.copy())

    def _reset_history(self, event: Event | None = None) -> None:
        self._undo_history = deque(maxlen=self._history_limit)
        self._redo_history = deque(maxlen=self._history_limit)
        self._staged_history = []
        self._block_history = False

    @contextmanager
    def block_history(self):
        prev = self._block_history
        self._block_history = True
        try:
            yield
            self._commit_staged_history()
        finally:
            self._block_history = prev

    def _commit_staged_history(self):
        if self._staged_history:
            first_before = self._staged_history[0][0]
            last_after = self._staged_history[-1][1]
            self._undo_history.append((first_before, last_after))
            self._staged_history = []

    def _save_history(self, value):
        self._redo_history.clear()
        if self._block_history:
            self._staged_history.append(value)
        else:
            self._append_to_undo_history(value)

    def _on_data_change(self, event=None):
        if hasattr(event, "action") and event.action in ["adding", "removing", "changing"]:
            return

        if self._is_restoring_history:
            return

        current = self._snapshot_data()
        previous = self._last_history_state

        self._save_history((copy.copy(previous), copy.copy(current)))
        self._last_history_state = current

    def on_face_color_change(self, event=None):
        self._on_data_change(event)

    def on_border_color_change(self, event=None):
        self._on_data_change(event)

    def on_size_change(self, event=None):
        self._on_data_change(event)

    def _load_history(self, before, after, undoing=True):
        if len(before) == 0:
            return False

        history_item = before.pop()
        after.append(history_item)

        self._is_restoring_history = True
        try:
            previous_data, next_data = history_item
            restored = previous_data if undoing else next_data
            self.data = restored[0].copy()
            self.selected_data = set(restored[1])
            if restored[0].shape[0] > 0:
                self.face_color = restored[2].copy()
                self.border_color = restored[3].copy()
                self.size = restored[4].copy()
        finally:
            self._is_restoring_history = False
        self._last_history_state = self._snapshot_data()
        self.refresh()
        self.events.load_history()
        return True

    def undo(self) -> bool:
        undo = self._load_history(self._undo_history, self._redo_history, undoing=True)
        self.events.undo()
        return undo

    def redo(self) -> bool:
        redo = self._load_history(self._redo_history, self._undo_history, undoing=False)
        self.events.redo()
        return redo

# register the custom layer controls
layer_to_controls[ManualPointsLayer] = CustomQtManualPointsControls

@ManualPointsLayer.bind_key(KeyMod.CtrlCmd | KeyCode.KeyZ, overwrite=True)
def undo(layer: ManualPointsLayer) -> None:
    layer.undo()

@ManualPointsLayer.bind_key(KeyMod.CtrlCmd | KeyMod.Shift | KeyCode.KeyZ, overwrite=True)
def redo(layer: ManualPointsLayer) -> None:
    layer.redo()