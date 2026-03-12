import importlib.resources

from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import QGroupBox, QLabel, QLayout, QSizePolicy, QSpacerItem, QVBoxLayout, QHBoxLayout
import os

def setup_acknowledgements(layout: QLayout, width: int = 225) -> QGroupBox:
    """Creates and adds an acknowledgements group box to the given layout.

    This function loads logos from the `napari_toolkit.resources` package, scales them,
    and displays them inside a `QGroupBox` with a white background.

    Args:
        layout (QLayout): The layout to which the acknowledgements group box will be added.
        width (int, optional): The width to which the logos should be scaled. Defaults to 300.

    Returns:
        QGroupBox: The initialized acknowledgements group box.
    """
    _group_box = QGroupBox("")
    
    _group_box.setStyleSheet(
        """
        QGroupBox {
            background-color: white;
        }
    """
    )
    _group_box.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    _layout = QHBoxLayout()
    path_logos = os.path.join(os.path.dirname(__file__), "../../../../images/logos.png")
    pixmap_logos = QPixmap(str(path_logos))
    pixmap_logos = pixmap_logos.scaledToWidth(width, Qt.SmoothTransformation)
    logo_logos = QLabel()
    logo_logos.setPixmap(pixmap_logos)
    _layout.addWidget(logo_logos)

    _group_box.setLayout(_layout)
    layout.addWidget(_group_box)
    return _group_box