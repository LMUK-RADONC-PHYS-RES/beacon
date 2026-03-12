from typing import Any, List

import napari
import numpy as np
from napari.layers import Labels
from napari.layers.base._base_constants import ActionType
from napari.utils.events import EmitterGroup, Event

from napari._qt.layer_controls.qt_layer_controls_container import layer_to_controls
from napari_beacon_layers.controls.manual_labels_control import CustomQtManualLabelsControls
from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification

import SimpleITK as sitk
from scipy.ndimage import binary_fill_holes
from scipy.interpolate import interpn

def interpolate_labels(label_a, label_b, num_steps):
    sitk_img_a = sitk.GetImageFromArray(label_a)
    sitk_distance_map_a = sitk.GetArrayFromImage(sitk.ApproximateSignedDistanceMap(sitk_img_a))
    
    sitk_img_b = sitk.GetImageFromArray(label_b)
    sitk_distance_map_b = sitk.GetArrayFromImage(sitk.ApproximateSignedDistanceMap(sitk_img_b))
    
    distance_map= np.zeros((2,) + label_a.shape, dtype=np.float32)
    distance_map[0,:,:] = sitk_distance_map_a
    distance_map[1,:,:] = sitk_distance_map_b
    
    x, y, z = np.meshgrid(np.linspace(0, num_steps-1, num_steps), np.arange(label_a.shape[0]), np.arange(label_a.shape[1]))
    
    labels_interp = interpn((np.array([0,num_steps-1]), np.arange(label_a.shape[0]), np.arange(label_a.shape[1])), distance_map, np.array([x,y,z]).T, bounds_error=False, fill_value=0)
    labels_interp = labels_interp.transpose(1,2,0)
    labels_interp = (labels_interp <= 0).astype(np.uint8)
    return labels_interp


class ManualLabelsLayer(Labels):
    """
    A bounding box layer class that extends `BaseLayerClass` and `Shapes` with specific color
    management and interaction handling. This class manages the addition, removal, and color
    updating of bounding boxes and restricts rotation.
    """

    def __init__(self, data, *args, **kwargs):
        super().__init__(data, *args, **kwargs)
        self.mode = 'paint'  # default mode is paint

        self._autofill = True
        self.events.add(autofill=Event) 
        self.events.paint.connect(lambda event: self.apply_autofill() if self.autofill else None)
        self.events.autofill.connect(lambda event: self.apply_autofill() if self.autofill else None)

        self._shape_interpolation_start = 0
        self._shape_interpolation_stop = 0
        self.events.add(shape_interpolation_start=Event)
        self.events.add(shape_interpolation_stop=Event)

    
    @property
    def autofill(self):
        """bool: fill bucket changes only connected pixels of same label."""
        return self._autofill

    @autofill.setter
    def autofill(self, autofill):
        self._autofill = autofill
        self.events.autofill()

    def apply_autofill(self):
        viewer = napari.current_viewer()
        # get current view
        transposed_layer_data = np.transpose(self.data.copy(), viewer.dims.order)
        # get current slice in that view
        current_slice = (transposed_layer_data.shape[0] - 1 - viewer.dims.current_step[viewer.dims.order[0]]) \
            if self.scale[viewer.dims.order[0]] < 0 else \
            viewer.dims.current_step[viewer.dims.order[0]]
        current_slice_data = transposed_layer_data[current_slice]

        # fill holes using 
        filled_slice = binary_fill_holes(current_slice_data == self.selected_label)   

        # set the filled slice back to the layer data
        transposed_layer_data[current_slice] = filled_slice.astype(self.data.dtype) * self.selected_label
        # set the layer data back to the layer         
        with self.events.blocker():
            np.copyto(self.data, np.transpose(transposed_layer_data, viewer.dims.order))
            self.refresh()  # refresh the layer to update the view
    
    @property
    def shape_interpolation_start(self):
        """int: starting frame for shape-based interpolation."""
        return self._shape_interpolation_start
    
    @shape_interpolation_start.setter
    def shape_interpolation_start(self, shape_interpolation_start):
        self._shape_interpolation_start = shape_interpolation_start
        self.events.shape_interpolation_start()
    
    @property
    def shape_interpolation_stop(self):
        """int: stopping frame for shape-based interpolation."""
        return self._shape_interpolation_stop
    
    @shape_interpolation_stop.setter
    def shape_interpolation_stop(self, shape_interpolation_stop):
        self._shape_interpolation_stop = shape_interpolation_stop
        self.events.shape_interpolation_stop()

    def apply_shape_based_interpolation(self):
        viewer = napari.current_viewer()

        label_data = self.data
        N = len(label_data.shape)

        if N != 3:
            show_warning("Shape base interpolation only works on 3D data.")
            return
        
        if self.selected_label == 0:
            show_warning("Please select a valid label (non-zero).")
            return

        new_labels = label_data.copy()
        
        non_empty_labels = np.where((new_labels == self.selected_label).sum(axis=(1,2)))[0]
        print(non_empty_labels)
        if len(non_empty_labels) < 2:
            show_warning("At least two frames with labels are required for shape based interpolation.")
            return

        #print(non_empty_labels)
        # for each pair of non empty labels, interpolate
        for i in range(len(non_empty_labels) - 1):
            frame_a = non_empty_labels[i]
            frame_b = non_empty_labels[i+1]
            num_steps = frame_b - frame_a + 1
            if num_steps <= 2:
                continue
            #print(f"Interpolating between frames {frame_a} and {frame_b} with {num_steps} steps.")
            labels_a = (label_data[frame_a] == self.selected_label).astype(np.uint8)
            labels_b = (label_data[frame_b] == self.selected_label).astype(np.uint8)
            
            labels_interp = interpolate_labels(labels_a, labels_b, num_steps)
            labels_interp = labels_interp[1:-1] * self.selected_label

            # assign interpolated labels to new_labels if not overwriting existing
            overlayed = np.logical_or(new_labels[frame_a+1:frame_b] == 0, new_labels[frame_a+1:frame_b] == self.selected_label)
            overlayed = np.logical_or(overlayed, labels_interp == self.selected_label)
            
            #labels_to_assign[overlayed] = new_labels[frame_a+1:frame_b][overlayed]
            new_labels[frame_a+1:frame_b][overlayed] = labels_interp[overlayed]

        np.copyto(label_data, new_labels)
        self.refresh()
        show_info("Shape based interpolation completed.")


# register the custom layer controls
layer_to_controls[ManualLabelsLayer] = CustomQtManualLabelsControls
