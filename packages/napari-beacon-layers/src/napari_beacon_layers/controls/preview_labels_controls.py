from napari._qt.layer_controls.qt_labels_controls import QtLabelsControls
from napari.utils.action_manager import action_manager
import napari
from packaging.version import Version

class CustomQtPreviewLabelsControls(QtLabelsControls):
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

        self._brush_size_slider_control.brush_size_slider.setHidden(True)
        self._brush_size_slider_control.brush_size_slider_label.setHidden(True)

        self._display_selected_label_checkbox_control.selected_color_checkbox.setHidden(True)
        self._display_selected_label_checkbox_control.selected_color_checkbox_label.setHidden(True)

        self._colormode_combobox_control.color_mode_combobox.setHidden(True)
        self._colormode_combobox_control.color_mode_combobox_label.setHidden(True)

        self._label_control.selection_spinbox.setHidden(False)
        self._label_control.selection_spinbox.setDisabled(True)


        # No need to hide the buttons, since we disabled the editability of the layer
        return
        
        # We don't need all these button -> hide and disable tem + remove key binding
        buttons_to_hide = [
            {"button": self.ellipse_button, "shortcut": "napari:activate_add_ellipse_mode"},
            {"button": self.polygon_button, "shortcut": "napari:activate_add_polygon_mode"},
            {
                "button": self.rectangle_button,
                "shortcut": "napari:activate_add_rectangle_mode",
            },
            {"button": self.line_button, "shortcut": "napari:activate_add_line_mode"},
            {"button": self.path_button, "shortcut": "napari:activate_add_path_mode"},
            {"button": self.vertex_insert_button, "shortcut": "napari:activate_vertex_insert_mode"},
            {"button": self.vertex_remove_button, "shortcut": "napari:activate_vertex_remove_mode"},
            {"button": self.move_front_button, "shortcut": "napari:move_shapes_selection_to_front"},
            {"button": self.move_back_button, "shortcut": "napari:move_shapes_selection_to_back"},
            {"button": self.transform_button, "shortcut": "napari:activate_shapes_transform_mode"},
            {"button": self.direct_button, "shortcut": "napari:activate_direct_mode"},
            {"button": self.polyline_button, "shortcut": "napari:activate_add_polyline_mode"},
        ]

        for button in buttons_to_hide:
            button["button"].setDisabled(True)
            button["button"].hide()
            action_manager.unbind_shortcut(button["shortcut"])

        # Reorder the remaining buttons to not have a sparse layout
        #self.button_grid.addWidget(self.delete_button, 0, 1)
        #self.button_grid.addWidget(self.polygon_lasso_button, 0, 2)

