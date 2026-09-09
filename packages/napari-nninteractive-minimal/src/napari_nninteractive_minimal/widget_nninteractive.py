from __future__ import annotations

from typing import Any

import numpy as np
from qtpy.QtWidgets import QGroupBox, QWidget

from napari.viewer import Viewer
from napari_nninteractive import nnInteractiveWidget
from napari_beacon_layers import ManualLabelsLayer, PreviewLabelsLayer
from napari.utils.events import EmitterGroup, Event


class nnInteractiveWidgetMinimal(nnInteractiveWidget):
    """BEACON wrapper around napari-nninteractive >= 2.5.

    Inference is delegated to upstream napari-nninteractive:
      - Local:  nnInteractiveInferenceSession
      - Remote: nnInteractiveRemoteInferenceSession

    This wrapper keeps only BEACON-specific layer classes, simplified UI and
    ARTIST study events.
    """

    def __init__(
        self,
        napari_viewer,
        inference_config: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        
        viewer = napari_viewer

        self._preserve_interaction_layers_on_next = False

        super().__init__(viewer, **kwargs)

        try:
            self.reset_button.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass

        self.reset_button.clicked.connect(self.on_next)
        self._width = 250
        self.setMinimumWidth(self._width)
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.events = EmitterGroup(
            self,
            next_object=Event,
            reset_interactions=Event,
            add_interaction=Event,
        )

        self.label_layer_name = "nnInteractive - Preview Layer"

        # ARTIST chooses the image and handles export itself. Keep the new
        # Local/Remote settings visible.
        self._hide_group_containing(self.image_selection)
        self._hide_group_containing(self.auto_refine)
        self._hide_group_containing(self.aggregation_output_combo)
        self._hide_group_containing(self.export_button)

        self._apply_inference_config(inference_config or {})

    @staticmethod
    def _find_ancestor_groupbox(widget: QWidget) -> QGroupBox | None:
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QGroupBox):
                return parent
            parent = parent.parentWidget()
        return None

    def _hide_group_containing(self, widget: QWidget) -> None:
        group = self._find_ancestor_groupbox(widget)
        if group is not None:
            group.setHidden(True)

    def _reset_interaction_layers_in_place(self) -> None:
        """Reset nnInteractive prompt layers without removing them from Napari.

        This avoids repeated VisPy/OpenGL resource destruction during Next Object
        (native glDeleteTexture access violation on Windows).
        """
        for layer_name in self.layer_dict.values():
            if layer_name not in self._viewer.layers:
                continue

            layer = self._viewer.layers[layer_name]

            with layer.events.blocker():
                if layer_name == self.scribble_layer_name:
                    layer.data.fill(0)

                    if hasattr(layer, "_last_slice_id"):
                        layer._last_slice_id = None

                    if hasattr(layer, "_last_dim_not_displayed"):
                        layer._last_dim_not_displayed = None

                    if hasattr(layer, "_is_free"):
                        layer._is_free = False

                    for history_name in (
                        "_undo_history",
                        "_redo_history",
                        "_staged_history",
                    ):
                        history = getattr(layer, history_name, None)
                        if hasattr(history, "clear"):
                            history.clear()

                else:
                    while len(layer.data) > 0:
                        layer.remove_last()

                    if hasattr(layer, "_is_free"):
                        layer._is_free = True

                    if hasattr(layer, "selected_data"):
                        layer.selected_data = set()

                    if hasattr(layer, "_finish_drawing"):
                        layer._finish_drawing()

            layer.refresh()
        self._interaction_history = []

    def _clear_layers(self) -> None:
        """Clear prompt layers.
        """

        if self._preserve_interaction_layers_on_next:
            self._reset_interaction_layers_in_place()
            return

        super()._clear_layers()
        
    def _apply_inference_config(self, config: dict[str, Any]) -> None:
        """Apply optional ARTIST defaults without duplicating backend logic.

        Supported keys:
          backend: "local" or "remote"
          server_url: URL of nninteractive-server
          local_checkpoint: optional local checkpoint path

        API keys deliberately do not come from YAML. If the API-key field is
        empty, nnInteractive uses NN_INTERACTIVE_API_KEY from the environment.
        """
        backend = config.get("backend")
        if backend is not None:
            backend = str(backend).strip().lower()
            if backend not in {"local", "remote"}:
                raise ValueError(
                    "nninteractive.backend must be either 'local' or 'remote'"
                )

            target_index = 1 if backend == "remote" else 0
            if self.mode_switch.index != target_index:
                self.mode_switch._uncheck()
                self.mode_switch._check(target_index)
                self.on_mode_switched()

        server_url = config.get("server_url")
        if server_url:
            self.server_url_edit.blockSignals(True)
            self.server_url_edit.setText(str(server_url))
            self.server_url_edit.blockSignals(False)

        local_checkpoint = config.get("local_checkpoint")
        if local_checkpoint:
            self.model_selection_local.blockSignals(True)
            self.model_selection_local.setText(str(local_checkpoint))
            self.model_selection_local.blockSignals(False)

    def add_preview_label_layer(self, data: np.ndarray, name: str) -> None:
        label_layer = PreviewLabelsLayer(
            data,
            name=name,
            opacity=0.9,
            affine=self.session_cfg["affine"],
            scale=self.session_cfg["scale"],
            translate=self.session_cfg["translate"],
            rotate=self.session_cfg["rotate"],
            shear=self.session_cfg["shear"],
            metadata=self.session_cfg["metadata"],
        )
        label_layer.contour = 1
        label_layer.editable = False
        label_layer._source = self.session_cfg["source"]
        self._viewer.add_layer(label_layer)

    def add_label_layer(self, data: np.ndarray, name: str) -> None:
        if name == self.label_layer_name:
            self.add_preview_label_layer(data, name)
            return

        label_layer = ManualLabelsLayer(
            data,
            name=name,
            opacity=0.9,
            affine=self.session_cfg["affine"],
            scale=self.session_cfg["scale"],
            translate=self.session_cfg["translate"],
            rotate=self.session_cfg["rotate"],
            shear=self.session_cfg["shear"],
            metadata=self.session_cfg["metadata"],
        )
        label_layer.contour = 1
        label_layer._source = self.session_cfg["source"]
        self._viewer.add_layer(label_layer)

    def add_point_layer(self) -> None:
        super().add_point_layer()
        self._viewer.layers[self.point_layer_name].opacity = 0.3

    def add_scribble_layer(self) -> None:
        # Keep the v2 ScribbleLayer. Its get_last() returns a cropped scribble
        # plus its bbox, which is efficient for remote inference.
        super().add_scribble_layer()
        self._viewer.layers[self.scribble_layer_name].opacity = 0.3

    def add_bbox_layer(self) -> None:
        super().add_bbox_layer()

    def add_lasso_layer(self) -> None:
        super().add_lasso_layer()

        lasso_layer = self._viewer.layers[self.lasso_layer_name]
        lasso_layer.opacity = 0.5

        def ensure_last_cursor_position(layer, event):
            if (
                getattr(layer, "_is_creating", False)
                and getattr(layer, "_last_cursor_position", None) is None
            ):
                layer._last_cursor_position = np.array(event.pos)

        lasso_layer.mouse_move_callbacks.insert(0, ensure_last_cursor_position)

    def add_interaction(self, *args: Any, **kwargs: Any) -> None:
        super().add_interaction(*args, **kwargs)
        # Preserve the current BEACON study-log behaviour for this first migration.
        # self.events.add_interaction()

    def on_reset_interactions(self) -> None:
        super().on_reset_interactions()
        self.events.reset_interactions()

    def on_next(self, *args, **kwargs) -> None:
        """Store the current object and prepare the next one.
        """
        if self.label_layer_name not in self._viewer.layers:
            return

        label_layer = self._viewer.layers[self.label_layer_name]

        if not np.any(label_layer.data):
            return

        self._preserve_interaction_layers_on_next = True

        try:
            super().on_next(*args, **kwargs)
        finally:
            self._preserve_interaction_layers_on_next = False

        self.events.next_object()