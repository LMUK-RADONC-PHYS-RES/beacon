from napari._qt.layer_controls.qt_points_controls import QtPointsControls


class CustomQtManualPointsControls(QtPointsControls):
    """Custom Qt controls for editable points layers."""

    def __init__(self, layer):
        super().__init__(layer)

        self._projection_mode_control.projection_combobox.setHidden(True)
        self._projection_mode_control.projection_combobox_label.setHidden(True)
        self._symbol_combobox_control.symbol_combobox.setHidden(True)
        self._symbol_combobox_control.symbol_combobox_label.setHidden(True)
        self._text_visibility_control.text_disp_checkbox.setHidden(True)
        self._text_visibility_control.text_disp_label.setHidden(True)
        self._out_slice_checkbox_control.out_of_slice_checkbox.setHidden(True)
        self._out_slice_checkbox_control.out_of_slice_checkbox_label.setHidden(True)
