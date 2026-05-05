from qtpy.QtWidgets import QPushButton
from qtpy.QtCore import Qt


def modify_napari_ui(viewer, get_image_layer=None, get_interpolation=None):
    """
    Adds A/C/S view buttons, hides unused viewer/layer controls, and blocks
    delete-key removal of layers.  Returns the previous keyPressEvent handler
    so the caller can restore it later with revert_napari_ui().
    """
    if get_image_layer is None:
        get_image_layer = lambda: None
    if get_interpolation is None:
        get_interpolation = lambda: "nearest"

    def _refresh_view():
        layer = get_image_layer()
        if layer is not None:
            interp = layer.interpolation2d
            # toggle once to force napari to refresh rendering after dim change
            layer.interpolation2d = "linear" if interp != "linear" else "nearest"
            layer.interpolation2d = interp
            layer.refresh()

    def set_axial_view():
        viewer.dims.order = (0, 1, 2)
        _refresh_view()

    def set_coronal_view():
        viewer.dims.order = (1, 0, 2)
        _refresh_view()

    def set_sagittal_view():
        viewer.dims.order = (2, 0, 1)
        _refresh_view()

    _btn_style = (
        "min-width:28px; max-width:28px; "
        "min-height:28px; max-height:28px; padding:0px;"
    )
    for label, callback in [
        ("A", set_axial_view),
        ("C", set_coronal_view),
        ("S", set_sagittal_view),
    ]:
        btn = QPushButton(label)
        btn.clicked.connect(callback)
        btn.setStyleSheet(_btn_style)
        viewer.window._qt_viewer._viewerButtons.layout().insertWidget(-1, btn)

    vb = viewer.window._qt_viewer._viewerButtons
    vb.rollDimsButton.setHidden(True)
    vb.transposeDimsButton.setHidden(True)
    vb.consoleButton.setHidden(True)
    vb.gridViewButton.setHidden(True)
    vb.ndisplayButton.setHidden(True)

    viewer.window._qt_viewer._layersButtons.setHidden(True)


def revert_napari_ui(viewer):
    """Restores napari UI to the state before modify_napari_ui() was called."""
    vb = viewer.window._qt_viewer._viewerButtons
    vb.rollDimsButton.setHidden(False)
    vb.transposeDimsButton.setHidden(False)
    vb.consoleButton.setHidden(False)
    vb.gridViewButton.setHidden(False)
    vb.ndisplayButton.setHidden(False)

    viewer.window._qt_viewer._layersButtons.setHidden(False)

    layout = vb.layout()
    for _ in range(3):
        idx = layout.count() - 1
        if idx < 0:
            break
        item = layout.itemAt(idx)
        if item is not None:
            widget = item.widget()
            if widget is not None:
                layout.removeWidget(widget)
                widget.deleteLater()
