from ._widget_view_switch import ViewSwitchWidget

def set_axial(viewer):
    """Set the viewer to an axial view along the specified axis. Assuming (Z, Y, X) ordering."""
    viewer.dims.order = (0, 1, 2)

def set_coronal(viewer):
    """Set the viewer to a coronal view along the specified axis. Assuming (Z, Y, X) ordering."""
    viewer.dims.order = (1, 0, 2)

def set_saggital(viewer):
    """Set the viewer to a saggital view. Assuming (Z, Y, X) ordering."""
    viewer.dims.order = (2, 0, 1)

__all__ = ("ViewSwitchWidget", "set_axial", "set_coronal", "set_saggital")
