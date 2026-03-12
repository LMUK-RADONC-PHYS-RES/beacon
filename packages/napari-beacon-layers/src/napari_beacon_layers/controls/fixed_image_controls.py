from napari._qt.layer_controls.qt_image_controls import QtImageControls
from napari.utils.action_manager import action_manager
import napari

from napari_toolkit.widgets import setup_combobox
from napari._qt.layer_controls.widgets.qt_widget_controls_base import QtWrappedLabel
from napari._qt.layer_controls.widgets.qt_contrast_limits import range_to_decimals

class CustomQtFixedImageControls(QtImageControls):
    """Custom Qt controls for labels layer used for previewing labels.
    
    Hides unnecessary controls and buttons since the layer is non-editable.

    Args:
        layer (Labels): The labels layer associated with this control panel.
    """

    def __init__(self, layer):
        super().__init__(layer)

        # We don't need this Fields -> Hide them
        self._projection_mode_control.projection_combobox.setHidden(True)
        self._projection_mode_control.projection_combobox_label.setHidden(True)

        # We don't need all these button -> hide and disable tem + remove key binding
        buttons_to_hide = [
            {"button": self.transform_button, "shortcut": "napari:activate_image_transform_mode"},
        ]

        for button in buttons_to_hide:
            button["button"].setDisabled(True)
            button["button"].hide()
            action_manager.unbind_shortcut(button["shortcut"])

        # Reorder the remaining buttons to not have a sparse layout
        #self.button_grid.addWidget(self.delete_button, 0, 1)
        #self.button_grid.addWidget(self.polygon_lasso_button, 0, 2)
    
        # Contrast presets from raystation
        self.CONTRAST_PRESETS = {
            "CT: Bone": (450.0, 1600.0),
            "CT: Brain": (35.0, 100.0),
            "CT: Dental": (400.0, 2000.0),
            "CT: Inner ear": (700.0, 4000.0),
            "CT: Larynx": (40.0, 250.0),
            "CT: Liver": (50.0, 350.0),
            "CT: Lung": (-600.0, 1600.0), # -1350, 160
            "CT: Mediastinum": (40.0, 400.0),# should be -300 to 120
            "CT: Pelvis": (250.0, 1000.0),
            "CT: Soft tissue": (40.0, 350.0),
            "CT: Spine": (35.0, 300.0),
            "CT: Vertebrae": (350.0, 2000.0),
        }

        self._contrast_compobox = setup_combobox(None, ["Manual", *list(self.CONTRAST_PRESETS.keys())])
        self._contrast_compobox.setParent(self)
        self._contrast_compobox.setStyleSheet('font-size: 10px; padding: 3px 10px 3px 8px;')
        def on_contrast_manual(value):
            if value in self.CONTRAST_PRESETS:
                # start = level - window/2
                # end = level + window/2
                contrast_settings = self.CONTRAST_PRESETS[value]
                contrast_limits = [
                    (contrast_settings[0] - contrast_settings[1] / 2),
                    (contrast_settings[0] + contrast_settings[1] / 2)
                ]
                layer.contrast_limits = contrast_limits
                layer.contrast_limits_range = contrast_limits
            elif value == "Manual":
                layer.reset_contrast_limits()
                layer.contrast_limits_range = layer.contrast_limits
                self._contrast_limits_control.show_clim_popup()

                decimals_ = range_to_decimals(
                    layer.contrast_limits_range, layer.dtype
                )
                self._contrast_limits_control.clim_popup.slider.setRange(*layer.contrast_limits_range)
                self._contrast_limits_control.clim_popup.slider.setDecimals(decimals_)
                self._contrast_limits_control.clim_popup.slider.setSingleStep(10**-decimals_)
        self._contrast_compobox.textActivated.connect(on_contrast_manual)  
        self._contrast_compobox.currentTextChanged.connect(on_contrast_manual)  

        self.layout().insertRow(5,QtWrappedLabel("contrast preset:"), self._contrast_compobox)