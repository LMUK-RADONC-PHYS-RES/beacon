from napari._qt.layer_controls.qt_labels_controls import QtLabelsControls
from napari.utils.action_manager import action_manager
import napari
from packaging.version import Version

import numpy as np

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QWidget,
    QCheckBox
)
from superqt import QLargeIntSpinBox

from napari._qt.layer_controls.widgets.qt_widget_controls_base import (
    QtWidgetControlsBase,
    QtWrappedLabel,
)
from napari._qt.utils import attr_to_settr
from napari.layers import Labels
from napari.layers.labels._labels_utils import get_dtype
from napari.utils._dtype import get_dtype_limits
from napari.utils.translations import trans
from napari._qt.utils import attr_to_settr, checked_to_bool
from napari.utils.events.event_utils import connect_setattr
from napari_toolkit.containers.boxlayout import hstack, vstack
from napari_toolkit.widgets import setup_pushbutton
from qtpy.QtWidgets import QHBoxLayout, QVBoxLayout

class QtAutofillCheckBoxControl(QtWidgetControlsBase):
    """
    Class that wraps the connection of events/signals between the layer autofill
    attribute and Qt widgets.

    Parameters
    ----------
    parent: qtpy.QtWidgets.QWidget
        An instance of QWidget that will be used as widgets parent
    layer : napari_beacon_layers.ManualLabelsLayer
        An instance of a napari_beacon_layers ManualLabelsLayer layer.

    Attributes
    ----------
    autofill_checkbox : qtpy.QtWidgets.QCheckBox
        Checkbox to control if label layer is autofilled.
    autofill_checkbox_label : napari._qt.layer_controls.widgets.qt_widget_controls_base.QtWrappedLabel
        Label for the autofill model chooser widget.
    """

    def __init__(self, parent: QWidget, layer: Labels) -> None:
        super().__init__(parent, layer)
        # Setup widgets
        self.autofill_checkbox = QCheckBox()
        self.autofill_checkbox.setChecked(layer.autofill)
        self.autofill_checkbox.setToolTip("Fill connected components after painting (only in paint mode)")
        self._callbacks.append(
            attr_to_settr(
                self._layer,
                'autofill',
                self.autofill_checkbox,
                'setChecked',
            )
        )
        connect_setattr(
            self.autofill_checkbox.stateChanged,
            layer,
            'autofill',
            convert_fun=checked_to_bool,
        )
        self.autofill_checkbox_label = QtWrappedLabel('autofill:')

    def get_widget_controls(self) -> list[tuple[QtWrappedLabel, QWidget]]:
        return [(self.autofill_checkbox_label, self.autofill_checkbox)]

class QtShapeBasedInterpolationControl(QtWidgetControlsBase):
    """
    Class that provides controls for shape-based interpolation.

    Parameters
    ----------
    parent: qtpy.QtWidgets.QWidget
        An instance of QWidget that will be used as widgets parent
    layer : napari_beacon_layers.ManualLabelsLayer
        An instance of a napari_beacon_layers ManualLabelsLayer layer.

    Attributes
    ----------
    shape_based_interpolation_btn : qtpy.QtWidgets.QPushButton
        Button to apply shape-based interpolation to the label layer.
    shape_based_interpolation_label : napari._qt.layer_controls.widgets.qt_widget_controls_base.QtWrappedLabel
        Label for the shape-based interpolation chooser widget.
    """

    def __init__(self, parent: QWidget, layer: Labels) -> None:
        super().__init__(parent, layer)
        # Setup widgets
       
        self.shape_based_interpolation_label = QtWrappedLabel('label interp.:')
        self.shape_based_interpolation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.apply_btn = setup_pushbutton(layout=None, text="Apply", function=lambda: layer.apply_shape_based_interpolation())
    
    def get_widget_controls(self) -> list[tuple[QtWrappedLabel, QWidget]]:
        return [(self.shape_based_interpolation_label, self.apply_btn)]

class CustomQtManualLabelsControls(QtLabelsControls):
    """Custom Qt controls for labels layer used for previewing labels.
    
    Hides unnecessary controls and buttons since the layer is non-editable.

    Args:
        layer (Labels): The labels layer associated with this control panel.
    """

    def __init__(self, layer):
        super().__init__(layer)

        # We don't need this Fields -> Hide them
        self._ndim_spinbox_control.ndim_spinbox.setHidden(True)
        self._ndim_spinbox_control.ndim_spinbox_label.setHidden(True)

        self._contiguous_checkbox_control.contiguous_checkbox.setHidden(True)
        self._contiguous_checkbox_control.contiguous_checkbox_label.setHidden(True)

        self._preserve_labels_checkbox_control.preserve_labels_checkbox.setHidden(True)
        self._preserve_labels_checkbox_control.preserve_labels_checkbox_label.setHidden(True)

        self._display_selected_label_checkbox_control.selected_color_checkbox.setHidden(True)
        self._display_selected_label_checkbox_control.selected_color_checkbox_label.setHidden(True)

        self._colormode_combobox_control.color_mode_combobox.setHidden(True)
        self._colormode_combobox_control.color_mode_combobox_label.setHidden(True)

        self._label_control.selection_spinbox.setHidden(False)
        self._label_control.selection_spinbox.setDisabled(True)

        # We don't need all these button -> hide and disable tem + remove key binding
        buttons_to_hide = [
            {"button": self.pick_button, "shortcut": "napari:activate_labels_picker_mode"},
            {"button": self.fill_button, "shortcut": "napari:activate_labels_fill_mode"},
            {"button": self.transform_button, "shortcut": "napari:activate_labels_transform_mode"},
        ]

        for button in buttons_to_hide:
            button["button"].setDisabled(True)
            button["button"].hide()
            action_manager.unbind_shortcut(button["shortcut"])

        # quickly switch to erase mode when holding shift and switch back to paint mode when releasing shift
        @layer.bind_key('Shift')
        def quick_switch_tool(viewer):
            print("quick_switch_tool")
            if layer.mode != "paint":
                return
            # on press
            # switch paint/erase mode
            layer.mode = 'erase'
            yield
            # on release
            # switch paint/erase mode back
            # only switch back to paint if we are still in erase mode, otherwise keep the current mode (e.g. if user switched to another mode while holding shift)
            if layer.mode == 'erase': 
                layer.mode = 'paint'

        # shortcuts for increasing/decreasing brush size with shift + plus/minus
        @layer.bind_key('Plus', overwrite=True)
        def increase_brush_size(viewer):
            # on press
            if layer.brush_size < 30:
                layer.brush_size += 1
        
        @layer.bind_key('-', overwrite=True)
        def decrease_brush_size(viewer):
            # on press
            if layer.brush_size > 1:
                layer.brush_size -= 1

        self._autofill_checkbox_control = QtAutofillCheckBoxControl(self, layer)
        self._add_widget_controls(self._autofill_checkbox_control)

        if len(layer.data.shape) == 3:
            self._shape_based_interpolation_control = QtShapeBasedInterpolationControl(self, layer)
            self._add_widget_controls(self._shape_based_interpolation_control)

