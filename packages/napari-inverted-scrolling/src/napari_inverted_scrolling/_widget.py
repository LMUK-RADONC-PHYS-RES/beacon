
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout
)
from napari_toolkit.widgets import setup_pushbutton, setup_label

from .inverted_scrolling import invert_scrolling, reset_scrolling, is_inverted

class ToggleInvertedScrollingWidget(QWidget):
    def __init__(self, viewer: 'napari.viewer.Viewer'):
        super().__init__()
        self.viewer = viewer

        main_layout = QVBoxLayout(self)

        self.button = setup_pushbutton(
            main_layout,
            "Invert Scrolling" if not is_inverted(viewer) else "Revert Scrolling",
            lambda: self.on_toggle()
        )

        setup_label(main_layout, "Default: Scrolling = Zooming, Ctrl + Scrolling = Slice Scrolling")

    def on_toggle(self):
        if is_inverted(self.viewer):
            invert_scrolling(self.viewer)
            self.button.setText("Revert Scrolling")
        else:
            reset_scrolling(self.viewer)
            self.button.setText("Invert Scrolling")

    def showEvent(self, event):
        self.button.setChecked(is_inverted(self.viewer))
    
    def closeEvent(self, event):
        reset_scrolling(self.viewer)
        pass

    def hideEvent(self, event):
        # ignore
        pass
