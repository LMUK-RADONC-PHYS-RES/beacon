from typing import Any, List

import napari
import numpy as np
from napari.layers import Image
from napari.layers.base._base_constants import ActionType

from napari._qt.layer_controls.qt_layer_controls_container import layer_to_controls
from napari_beacon_layers.controls.fixed_image_controls import CustomQtFixedImageControls

class FixedImageLayer(Image):
    """
    A bounding box layer class that extends `BaseLayerClass` and `Shapes` with specific color
    management and interaction handling. This class manages the addition, removal, and color
    updating of bounding boxes and restricts rotation.
    """

    def __init__(self, data, *args, **kwargs):
        super().__init__(data, *args, **kwargs)

        self.mouse_drag_callbacks.append(self._adjust_contrast_on_drag)

    def _adjust_contrast_on_drag(self, layer, event):
        if not ("Control" in event._modifiers):
            return

        yield

        initial_postion = event.position[-2:]
        initial_gamma = layer.gamma
        initial_contrast = layer.contrast_limits
        contrast_range = layer.contrast_limits_range
        SENSITIVITY = 0.005
        range_width = contrast_range[1] - contrast_range[0]

        while event.type == 'mouse_move':
            current_position = event.position[-2:]
            
            # Calculate deltas scaled by zoom
            delta_x = (current_position[1] - initial_postion[1])
            delta_x = np.sign(delta_x) * max(abs(delta_x) - 5, 0)
            delta_y = (current_position[0] - initial_postion[0]) 
            delta_y = np.sign(delta_y) * max(abs(delta_y) - 5, 0)

            # 1. Calculate the 'Window' (Contrast)
            # Drag Right (Positive delta_x) = Wider Window = Lower Contrast
            initial_width = initial_contrast[1] - initial_contrast[0]
            new_width = initial_width + (delta_x * range_width * SENSITIVITY)
            new_width = np.clip(new_width, 1, contrast_range[1] - contrast_range[0])

            # 2. Calculate the 'Level' (Brightness)
            # Drag Up (Negative delta_y in screen space) = Higher Level = Darker Image
            initial_level = (initial_contrast[1] + initial_contrast[0]) / 2
            new_level = initial_level + (delta_y * range_width * SENSITIVITY)

            # 3. Convert Window/Level back to Contrast Limits (min/max)
            new_min = new_level - (new_width / 2)
            new_max = new_level + (new_width / 2)

            # 4. Apply limits and clip to the valid range of the data
            new_contrast_limits = (
                np.clip(new_min, contrast_range[0], contrast_range[1]-1),
                np.clip(new_max, contrast_range[0]+1, contrast_range[1])
            )

            layer.contrast_limits = new_contrast_limits

            yield

# register the custom layer controls
layer_to_controls[FixedImageLayer] = CustomQtFixedImageControls
