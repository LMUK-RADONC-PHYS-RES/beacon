from qtpy.QtWidgets import QGroupBox
import numpy as np
from scipy.ndimage import zoom

from napari_nninteractive import nnInteractiveWidget
from napari_nninteractive.layers.point_layer import SinglePointLayer
#from napari_nninteractive_minimal.single_point_layer import SinglePointLayer
from napari_nninteractive.utils.utils import ColorMapper, determine_layer_index

from napari_beacon_layers import ManualLabelsLayer, PreviewLabelsLayer, FixedImageLayer
from acvl_utils.cropping_and_padding.bounding_boxes import bounding_box_to_slice, crop_and_pad_nd
from napari.utils.events import EventEmitter, EmitterGroup, Event, EventedList

class nnInteractiveWidgetMinimal(nnInteractiveWidget):
    def __init__(self, viewer: 'napari.viewer.Viewer', **kwargs):
        super().__init__(viewer, **kwargs)
        self._width = 250
        self.superresolution = 1  # superresolution factor (1 = no superresolution)

        self.layout().setContentsMargins(0,0,0,0)

        # Define events
        self.events = EmitterGroup(self,
            next_object = Event,
            reset_interactions = Event,
            add_interaction = Event,
        )

        # Modify the UI
        self.model_selection.parent().setHidden(True)
        self.image_selection.parent().setHidden(True)
        self.instance_aggregation_ckbx.setHidden(True)
        self.auto_refine.setHidden(True)
        self.auto_refine.parent().setHidden(True)
        self.propagate_ckbx.setHidden(True)
        #self.run_ckbx.parent().setHidden(True)
        self.export_button.parent().setHidden(True)

        self._scribble_brush_size = 2

        self.label_layer_name = "nnInteractive - Preview Layer"
        self.semantic_layer_name = "nnInteractive - Preview Layer"

        self.prediction_colormap = ColorMapper(49, seed=0.75, background_value=0)

        self.preview_layer_edited = False
        # add listener that on manual update of the preview label layer, the point layer is updated as well
        def on_interaction(event):
            label_layer = self._viewer.layers[self.label_layer_name]
            if self._viewer.layers.selection.active == label_layer:
                self.preview_layer_edited = True
                return
            if self._viewer.layers.selection.active != label_layer and self.preview_layer_edited:
                self.preview_layer_edited = False
                # self.session
                # crop (as in preprocessing)
                initial_seg = label_layer.astype(np.uint8)
                initial_seg = crop_and_pad_nd(initial_seg, self.preprocessed_props['bbox_used_for_cropping'])

                # initial seg is written into initial seg buffer
                interaction_channel = -7
                self.interactions[interaction_channel] = initial_seg.to(self.interactions.device)

        #self._viewer.layers.selection.events.active.connect(on_interaction)

    def add_preview_label_layer(self, data, name) -> None:
        """
        Check if a layer with the layer_name already exists. If yes rename this by adding an index
        and afterward create the layer
        :return:
        :rtype:
        """
        label_layer = PreviewLabelsLayer(
            data,
            name=name,
            opacity=0.9,
            affine=self.session_cfg["affine"],
            scale=self.session_cfg["scale"],
            translate=self.session_cfg["translate"],
            rotate=self.session_cfg["rotate"],
            shear=self.session_cfg["shear"],
            # colormap=self.colormap[index],
            metadata=self.session_cfg["metadata"],
        )
        label_layer.contour = 1
        label_layer.editable = False
    
        label_layer._source = self.session_cfg["source"]

        self._viewer.add_layer(label_layer)

    def add_label_layer(self, data, name) -> None:
        """
        Check if a layer with the layer_name already exists. If yes rename this by adding an index
        and afterward create the layer
        :return:
        :rtype:
        """
        if name == self.label_layer_name:
            self.add_preview_label_layer(data, name)
            return

        # Apply superresolution upsampling for persistent segmentation layers
        sr = self.superresolution
        if sr > 1 and data.ndim == 3:
            data = zoom(data, (1, sr, sr), order=0).astype(data.dtype)
            scale = np.array(self.session_cfg["scale"])
            scale = np.array([scale[0], scale[1] / sr, scale[2] / sr])
        else:
            if sr > 1:
                import warnings
                warnings.warn(
                    f"superresolution={sr} requested but data.ndim={data.ndim} (expected 3). "
                    "Superresolution is only supported for 3D data; creating layer at original resolution."
                )
            scale = self.session_cfg["scale"]

        label_layer = ManualLabelsLayer(
            data,
            # self._data_result,
            name=name,
            opacity=0.9,
            affine=self.session_cfg["affine"],
            scale=scale,
            translate=self.session_cfg["translate"],
            rotate=self.session_cfg["rotate"],
            shear=self.session_cfg["shear"],
            # colormap=self.colormap[index],
            metadata=self.session_cfg["metadata"],
        )
        label_layer.contour = 1
        label_layer._source = self.session_cfg["source"]
        label_layer.colormap = self.colormap[self.object_index]

        self._viewer.add_layer(label_layer)


    def add_point_layer(self) -> None:
        """Adds a single point layer to the viewer."""
        point_layer = SinglePointLayer(
            name=self.point_layer_name,
            ndim=self.session_cfg["ndim"],
            affine=self.session_cfg["affine"],
            scale=self.session_cfg["scale"],
            translate=self.session_cfg["translate"],
            rotate=self.session_cfg["rotate"],
            shear=self.session_cfg["shear"],
            metadata=self.session_cfg["metadata"],
            opacity=0.7,
            size=2,
            prompt_index=self.prompt_button.index,
        )

        # point_layer.size = 0.2
        point_layer.events.finished.connect(self.on_interaction)
        self._viewer.add_layer(point_layer)
    
    def add_interaction(self,*args,**kwargs) -> None:
        super().add_interaction(*args,**kwargs)
        #self.events.add_interaction()

    def on_reset_interactions(self) -> None:
        super().on_reset_interactions()
        self.events.reset_interactions()
    
    def on_next(self) -> None:
        """
        Prepares the next label layer for interactions in the viewer.

        Retrieves the index of the last labeled object, renames the current label layer with
        this index, unbinds the original data by creating a deep copy, and clears all interaction
        layers. A new label layer with an updated colormap is then added to the viewer.
        """
        # Rename the current layer and add a new one
        label_layer = self._viewer.layers[self.label_layer_name]
        if not self.instance_aggregation_ckbx.isChecked():
            
            _name = f"Prediction {self.object_index+1}"
            self.add_preview_label_layer(label_layer.data.copy(), _name)
            self._viewer.layers[_name].colormap = self.prediction_colormap[(self.object_index+1) % 48]
            self._viewer.layers[_name].visible = False

            _name = f"Segmentation {self.object_index+1}"
            self.add_label_layer(label_layer.data.copy(), _name)

            self._viewer.layers[_name].colormap = self.colormap[self.object_index]

        else:
            _sem_name = f"semantic map - {self.session_cfg['name']}"
            if _sem_name not in self._viewer.layers:
                self.add_label_layer(np.zeros_like(label_layer.data), _sem_name)

            sem_layer = self._viewer.layers[_sem_name]

            sem_layer.data[label_layer.data == 1] = self.object_index + 1
            sem_layer.refresh()

        self.object_index += 1
        label_layer.colormap = self.colormap[self.object_index]
        
        self.events.next_object()

        self._clear_layers()
        self.prompt_button._uncheck()
        self.prompt_button._check(0)

    def closeEvent(self, event):
        super().closeEvent(event)
        self._viewer.layers.events.inserted.disconnect(self.image_selection._update)
        self._viewer.layers.events.removed.disconnect(self.image_selection._update)
        for layer in self.image_selection.layer_names:
            layer.events.name.disconnect(self.image_selection._update)
        self.image_selection.close()
        self.image_selection.deleteLater()

        
        self._viewer.layers.events.inserted.disconnect(self.label_for_init._update)
        self._viewer.layers.events.removed.disconnect(self.label_for_init._update)
        for layer in self.label_for_init.layer_names:
            layer.events.name.disconnect(self.label_for_init._update)
        self.label_for_init.close()
        self.label_for_init.deleteLater()

        self._viewer.layers.selection.events.active.disconnect(self.on_layer_selected)
        self._viewer.dims.events.order.disconnect(self.on_axis_change)
