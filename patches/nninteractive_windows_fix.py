import sys

from napari_nninteractive.widget_controls import LayerControls

if not hasattr(LayerControls, "_beacon_original_clear_layers"):
    LayerControls._beacon_original_clear_layers = LayerControls._clear_layers

if not hasattr(LayerControls, "_beacon_original_on_next"):
    LayerControls._beacon_original_on_next = LayerControls.on_next

_ORIGINAL_CLEAR_LAYERS = LayerControls._beacon_original_clear_layers
_ORIGINAL_ON_NEXT = LayerControls._beacon_original_on_next

def _reset_interaction_layers_in_place(self):
    """Clear prompt layers without destroying their VisPy/OpenGL resources."""

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


def _patched_clear_layers(self):
    if getattr(self, "_beacon_preserve_layers_on_next", False):
        _reset_interaction_layers_in_place(self)
        return

    return _ORIGINAL_CLEAR_LAYERS(self)


def _patched_on_next(self, *args, **kwargs):
    self._beacon_preserve_layers_on_next = True

    try:
        return _ORIGINAL_ON_NEXT(self, *args, **kwargs)
    finally:
        self._beacon_preserve_layers_on_next = False


def apply_nninteractive_windows_fix():
    """Apply the Windows VisPy glDeleteTexture workaround once."""

    # Since the crash is Windows-specific for now, leave Linux untouched.
    if sys.platform != "win32":
        return

    if getattr(LayerControls, "_beacon_gl_delete_texture_fix", False):
        return

    LayerControls._clear_layers = _patched_clear_layers
    LayerControls.on_next = _patched_on_next

    LayerControls._beacon_gl_delete_texture_fix = True

    print("Applied nnInteractive Windows Next Object workaround")