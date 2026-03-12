from napari import Viewer
from napari_toolkit.utils import set_value
from napari_toolkit.utils.widget_getter import get_value
from napari_toolkit.widgets import setup_label, setup_hswitch
from qtpy.QtWidgets import QVBoxLayout, QWidget

class ViewSwitchWidget(QWidget):
    def __init__(self, viewer:Viewer):
        super().__init__()

        self._viewer = viewer

        self._silence = False

        main_layout = QVBoxLayout(self)
        _layout = main_layout
        setup_label(_layout, "Switch to different view:")
        self.view_select = setup_hswitch(
            _layout, ["Axial", "Coronal", "Saggital", "Other"], default=0, function=lambda: self.set_view())

        self._viewer.dims.events.order.connect(self.on_dims_event)

    def set_view(self):
        """Switch the viewer dimension ordering based on the selected view.

        This method updates ``self._viewer.dims.order`` so that the napari
        display presents the chosen orthogonal slice ordering. If a caller
        wants to automatically set prompts on view change, they can call
        ``set_current_view_prompt`` (optionally controlled by a checkbox).
        """

        if self._silence:
            return

        # Set the current view based on the selected option in the view_select widget
        selected_view = get_value(self.view_select)[1]
        current_view = self._viewer.dims.order[0]
        if selected_view == 0:
            # Set the order of dimensions to A
            self._viewer.dims.order = (0, 1, 2)
        elif selected_view == 1:
            self._viewer.dims.order = (1, 0, 2)
        elif selected_view == 2:
            self._viewer.dims.order = (2, 0, 1)

    def on_dims_event(self, event):
        self._silence = True

        order = self._viewer.dims.order
        if order == (0, 1, 2):
            set_value(self.view_select, 0)
        elif order == (1, 0, 2):
            set_value(self.view_select, 1)
        elif order == (2, 0, 1):
            set_value(self.view_select, 2)
        else:
            set_value(self.view_select, 4)

        self._silence = False

    def closeEvent(self, event):
        self._viewer.dims.events.order.disconnect(self.on_dims_event)

    def hideEvent(self, event):
        self._viewer.dims.events.order.disconnect(self.on_dims_event)

    def showEvent(self, event):
        self._viewer.dims.events.order.connect(self.on_dims_event)

