import os
import warnings
from pathlib import Path
from typing import Any, Optional

import numpy as np
from huggingface_hub import snapshot_download
from napari._qt.layer_controls.qt_layer_controls_container import layer_to_controls
from napari.layers import Labels, Image
from napari.layers.base._base_constants import ActionType
from napari.utils.notifications import show_warning
from napari.utils.transforms import Affine
from napari.viewer import Viewer
from qtpy.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QVBoxLayout,
    QPushButton,
    QWidget
)
from qtpy.QtCore import Qt  # type: ignore[attr-defined]
from napari_toolkit.containers import setup_scrollarea, setup_vcollapsiblegroupbox, setup_vgroupbox, setup_vscrollarea
from napari_toolkit.widgets import setup_iconbutton, setup_label, setup_layerselect
from napari_beacon_layers import ManualLabelsLayer, PreviewLabelsLayer, FixedImageLayer

from .utils.utils import ColorMapper, determine_layer_index
from .utils.affine import is_orthogonal
from napari.utils.transforms import Affine

class ManualSegmentationWidget(QWidget):
    def __init__(self, viewer: Viewer):
        super().__init__()
        self._width = 250
        self.setMinimumWidth(self._width)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self._viewer = viewer
        self.session_cfg = None

        self.allow_close = False

        self.colormap = ColorMapper(49, seed=0.5, background_value=0)
        self.object_index = 0

        self._viewer.layers.selection.events.active.connect(self.on_layer_selected)
        self.build_gui()

    def build_gui(self):
        main_layout = QVBoxLayout(self)

        _group_box, _layout = setup_vgroupbox(main_layout, text="Image Selection:")

        self.image_selection = setup_layerselect(
            _layout, viewer=self._viewer, layer_type=Image, function=self.on_image_selected
        )
        _group_box.setHidden(True)

        _group_box, _layout = setup_vgroupbox(main_layout, text="")


        self.init_button = setup_iconbutton(
            _layout,
            "Initialize",
            "new_labels",
            self._viewer.theme,
            self.on_init,
            tooltips="Initialize the Model and Image Pair",
        )
        #self.init_button.setHidden(True)

        self.reset_interaction_button = setup_iconbutton(
            _layout,
            "Delete Object",
            "delete",
            self._viewer.theme,
            self.on_reset_interactions,
            tooltips="Keep Model and Image Pair, just reset the interactions for the current object  - press R",
            shortcut="R",
        )
        self.reset_interaction_button.setDisabled(True)
        self.reset_button = setup_iconbutton(
            _layout,
            "New Object",
            "step_right",
            self._viewer.theme,
            self.on_next,
            tooltips="Keep current segmentation and go to the next object - press M",
            shortcut="M",
        )
        self.reset_button.setDisabled(True)
    
    def on_image_selected(self):
        """Reset the current sessions interaction but keep the session itself"""
        if self.session_cfg is not None:
            self.session_cfg = None
            self.object_index = 0
        self.init_button.setDisabled(False)
        self.reset_interaction_button.setDisabled(True)
        self.reset_button.setDisabled(True)

    # Layer Handling
    def add_label_layer(self, data, name) -> Labels:
        """
        Check if a layer with the layer_name already exists. If yes rename this by adding an index
        and afterward create the layer
        :return:
        :rtype:
        """

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
        label_layer._source = self.session_cfg["source"]
        label_layer.contour = 1
        label_layer.mode = "paint"

        self._viewer.add_layer(label_layer)
        return label_layer

    # Event Handlers
    def on_init(self, *args, **kwargs) -> None:
        """
        Initializes the session by configuring the selected model and image and creating a label layer.

        Retrieves the selected model and image names from the GUI, extracts relevant data from the
        image layer, and creates a corresponding label layer in the viewer.
        """
        # --- MODEL HANDLING --- #
        # Get all model and image from the GUI
        image_name = self.image_selection.currentText()

        if image_name == "":
            raise ValueError("No Image Layer selected")

        # --- DATA HANDLING --- #
        # Get everything we need from the image layer
        image_layer = self._viewer.layers[image_name]
        self.source_cfg = {
            "name": image_name,
            "model": "manual",
            "ndim": image_layer.ndim,
            "shape": image_layer.data.shape,
            "affine": image_layer.affine,
            "scale": image_layer.scale,
            "translate": image_layer.translate,
            "rotate": image_layer.rotate,
            "shear": image_layer.shear,
            "source": image_layer.source,
            "metadata": image_layer.metadata,
        }

        self.session_cfg = self.source_cfg.copy()

        # 1. Non - Othogonal Affine
        if not (
            is_orthogonal(
                self.source_cfg["affine"],
                image_layer.ndim,
                self._viewer.dims.order,
                self._viewer.dims.ndisplay,
            )
        ):
            show_warning(
                "Your data is non-orthogonal. This is not supported by napari. "
                "To fix this the direction and shear is ignored during visualizing which changes the appearance (only visual) of your data."
            )
            # 1. Make affine orthogonal -> ignore rotate and shear
            self.session_cfg["affine"] = Affine(
                scale=self.source_cfg["affine"].scale, translate=self.source_cfg["affine"].translate
            )
            # 2. Apply to Image Layer
            image_layer.affine = self.session_cfg["affine"]
            self._viewer.reset_view()

        # 1. Non - Othogonal Transforms
        # dummy affine to check if transforms are non-orthogonal
        _transform_matrix = Affine(
            scale=self.source_cfg["scale"],
            translate=self.source_cfg["translate"],
            rotate=self.source_cfg["rotate"],
            shear=self.source_cfg["shear"],
        )

        if not is_orthogonal(
            _transform_matrix,
            image_layer.ndim,
            self._viewer.dims.order,
            self._viewer.dims.ndisplay,
        ):
            show_warning(
                "Your data is non-orthogonal. This is not supported by napari. "
                "To fix this the direction and shear is ignored during visualizing which changes the appearance (only visual) of your data."
            )

            # 1. Make transforms orthogonal
            self.session_cfg["rotate"] = np.eye(self.source_cfg["ndim"])
            self.session_cfg["shear"] = np.zeros(self.source_cfg["ndim"])

            # 2. Apply to Image Layer
            image_layer.rotate = self.session_cfg["rotate"]
            image_layer.shear = self.session_cfg["shear"]
            self._viewer.reset_view()

        # 2. Convert 2D Data to dummy 3D Data
        if self.source_cfg["ndim"] == 2:
            self.session_cfg["ndim"] = 3
            self.session_cfg["shape"] = np.insert(self.session_cfg["shape"], 0, 1)

            # 1. to Affine
            self.session_cfg["affine"] = self.session_cfg["affine"].expand_dims([0])

            # 2. to Transforms
            self.session_cfg["scale"] = np.insert(self.session_cfg["scale"], 0, 1)
            self.session_cfg["translate"] = np.insert(self.session_cfg["translate"], 0, 0)
            if len(self.session_cfg["shear"]) == 1:
                self.session_cfg["shear"] = np.append(self.session_cfg["shear"], 0)
            self.session_cfg["shear"] = np.insert(self.session_cfg["shear"], 0, 0)
            _rot = np.eye(self.session_cfg["ndim"])
            _rot[-2:, -2:] = self.session_cfg["rotate"]
            self.session_cfg["rotate"] = _rot

        # Compute the overall spacing when considering both, affine and scale transform
        self.session_cfg["spacing"] = np.array(self.session_cfg["scale"]) * np.array(
            self.session_cfg["affine"].scale
        )

        # Add Layer
        self.object_index = 1
        _name = f"Segmentation {self.object_index} - {self.session_cfg['name']}"

        while _name in self._viewer.layers:
            self.object_index += 1
            _name = f"Segmentation {self.object_index} - {self.session_cfg['name']}"
            
        self.labels_layer = self.add_label_layer(np.zeros(self.session_cfg["shape"], dtype=np.uint8), _name)
        self.labels_layer.colormap = self.colormap[self.object_index]
        self.labels_layer.refresh()

        # disable init button
        self.init_button.setDisabled(True)
        self.reset_interaction_button.setDisabled(False)
        self.reset_button.setDisabled(False)

    def on_reset_interactions(self):
        """Reset only the current interaction"""
        if self.labels_layer is not None:
            if self.labels_layer in self._viewer.layers:
                self._viewer.layers.remove(self.labels_layer)
            self.labels_layer = None

    def on_layer_selected(self, *args, **kwargs) -> None:
        _layer = self._viewer.layers.selection.active

        if _layer is None:
            return
        elif isinstance(_layer, Labels):
            self.labels_layer = _layer
        else:
            self.labels_layer = None

    def on_next(self) -> None:
        # Rename the current layer and add a new one

        self.object_index += 1
        _name = f"Segmentation {self.object_index} - {self.session_cfg['name']}"

        while _name in self._viewer.layers:
            self.object_index += 1
            _name = f"Segmentation {self.object_index} - {self.session_cfg['name']}"

        self.labels_layer = self.add_label_layer(np.zeros(self.session_cfg["shape"], dtype=np.uint8), _name)
        self.labels_layer.colormap = self.colormap[self.object_index]

        # set active
        self._viewer.layers.selection.active = self.labels_layer
    
    def hideEvent(self, event):
        if self.allow_close:
            event.accept()
        else:
            event.ignore()
    
    def closeEvent(self, event):
        if self.allow_close:
            event.accept()
        else:
            event.ignore()

    def showEvent(self, event):
        self.init_button.setDisabled(False)
        self.reset_interaction_button.setDisabled(True)
        self.reset_button.setDisabled(True)
        #self.on_init()
    
