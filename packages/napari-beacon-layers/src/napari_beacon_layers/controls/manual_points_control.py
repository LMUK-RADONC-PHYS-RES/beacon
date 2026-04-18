from napari._qt.layer_controls.qt_points_controls import QtPointsControls


class CustomQtManualPointsControls(QtPointsControls):
    """Custom Qt controls for editable points layers."""

    def __init__(self, layer):
        super().__init__(layer)
