from napari._qt.layer_controls.qt_points_controls import QtPointsControls
from napari.utils.action_manager import action_manager
import napari
from packaging.version import Version

class CustomQtPreviewPointsControls(QtPointsControls):
    """Custom Qt controls for points layer used for previewing points.
    
    Hides unnecessary controls and buttons since the layer is non-editable.

    Args:
        layer (Points): The points layer associated with this control panel.
    """

    def __init__(self, layer):
        super().__init__(layer)

        # We don't need this Fields -> Hide them
        self._current_size_slider_control.size_slider.setHidden(True)
        self._current_size_slider_control.size_slider_label.setHidden(True)

        self._projection_mode_control.projection_combobox.setHidden(True)
        self._projection_mode_control.projection_combobox_label.setHidden(True)

        self._symbol_combobox_control.symbol_combobox.setHidden(True)
        self._symbol_combobox_control.symbol_combobox_label.setHidden(True)

        self._border_color_control.border_color_edit.setHidden(True)
        self._border_color_control.border_color_edit_label.setHidden(True)

        self._face_color_control.face_color_edit.setHidden(True)
        self._face_color_control.face_color_label.setHidden(True)

        self._text_visibility_control.text_disp_checkbox.setHidden(True)
        self._text_visibility_control.text_disp_label.setHidden(True)

        self._out_slice_checkbox_control.out_of_slice_checkbox.setHidden(True)
        self._out_slice_checkbox_control.out_of_slice_checkbox_label.setHidden(True)

        # No need to hide the buttons, since we disabled the editability of the layer
        #return
        
        # We don't need all these button -> hide and disable tem + remove key binding
        buttons_to_hide = [
            {"button": self.select_button, "shortcut": "napari:activate_points_select_mode"},
            {"button": self.addition_button, "shortcut": "napari:activate_points_add_mode"},
            {"button": self.delete_button, "shortcut": "napari:delete_selected_points"},
            {"button": self.transform_button, "shortcut": "napari:activate_points_transform_mode"},
        ]

        for button in buttons_to_hide:
            button["button"].setDisabled(True)
            button["button"].hide()
            action_manager.unbind_shortcut(button["shortcut"])

        # Reorder the remaining buttons to not have a sparse layout
        #self.button_grid.addWidget(self.delete_button, 0, 1)
        #self.button_grid.addWidget(self.polygon_lasso_button, 0, 2)

