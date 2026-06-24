import numpy as np
from napari.layers import Shapes
from napari.layers.base._base_constants import ActionType

from napari._qt.layer_controls.qt_layer_controls_container import layer_to_controls
from napari_beacon_layers.controls.line_prompt_controls import CustomQtLinePromptControls

class LineShapesLayer(Shapes):
    """A Shapes layer restricted to Line shapes only, keeping at most one line."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mode = "add_line"

# register the custom layer controls
layer_to_controls[LineShapesLayer] = CustomQtLinePromptControls
