import time
import torch
import os
from magicgui import magicgui
from typing import TYPE_CHECKING
from functools import partial
import numpy as np
from scipy.ndimage import zoom
from napari.qt.threading import thread_worker

from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification
from napari import Viewer
from napari.layers import Labels, Shapes, Points, Image, Layer
from napari_toolkit.containers import setup_scrollarea, setup_vcollapsiblegroupbox, setup_vgroupbox, setup_vscrollarea
from napari_toolkit.containers.boxlayout import hstack
from napari_toolkit.utils import set_value
from napari_toolkit.data_structs import setup_list
from napari_toolkit.utils.widget_getter import get_value
from napari_toolkit.widgets import *
from napari_toolkit.widgets import setup_checkbox, setup_pushbutton
from qtpy.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qtpy.QtCore import Qt, QTimer  # type: ignore[attr-defined]
import SimpleITK as sitk
from napari_beacon_layers import FixedImageLayer, PreviewLabelsLayer, ManualLabelsLayer, PreviewPointsLayer

METRICS_UPDATE_INTERVAL_MS = 3000

class SegmentationMetricsWidget(QWidget):
    def __init__(self, viewer: Viewer, update_interval_ms: int = METRICS_UPDATE_INTERVAL_MS, edit_log = None):
        super().__init__()
        self._viewer = viewer
        self.edit_log = edit_log

        layout = QVBoxLayout(self)
        
        
        self.layer_select_1 = setup_layerselect(None, viewer, Labels, function=self.on_layers_changed)
        hstack(layout,[
            QLabel("Reference:"),
            self.layer_select_1
        ], stretch=[0,1])

        self.layer_select_2 = setup_layerselect(None, viewer, Labels, function=self.on_layers_changed)
        hstack(layout,[
            QLabel("Segmentation:"),
            self.layer_select_2
        ], stretch=[0,1])

        self.metrics_label = setup_label(layout, "DSC: --\nHD95: --")

        self.auto_update_ckbx = setup_checkbox(
            None,
            "Auto Update",
            True,
            tooltips="Automatically recompute metrics on a timer and on layer changes.",
            function=self._on_auto_update_changed,
        )
        self.compute_btn = setup_pushbutton(
            None,
            "Compute",
            function=lambda: self.update_segmentation_metrics(),
            tooltips="Manually compute segmentation metrics now.",
        )
        self.compute_btn.setEnabled(False)
        hstack(layout, [self.auto_update_ckbx, self.compute_btn], stretch=[1, 0])

        self.metrics_timer = QTimer(self)
        self.metrics_timer.setInterval(update_interval_ms)
        self.metrics_timer.timeout.connect(lambda: self.update_segmentation_metrics())

    def has_reference_mask(self) -> bool:
        """Check if both layers are available."""
        return self._get_layer_1() is not None and self._get_layer_2() is not None

    def _on_auto_update_changed(self):
        """Called when the Auto Update checkbox is toggled."""
        auto = self.auto_update_ckbx.isChecked()
        self.compute_btn.setEnabled(not auto)
        if auto:
            self.metrics_timer.start()
            self.update_segmentation_metrics()
        else:
            self.metrics_timer.stop()

    def start_updates(self):
        if self.auto_update_ckbx.isChecked():
            self.metrics_timer.start()
            self.update_segmentation_metrics()

    def stop_updates(self):
        self.metrics_timer.stop()

    def _compute_dsc_hd95(self, mask1: np.ndarray, mask2: np.ndarray, spacing_xyz=None):
        """Compute DSC and HD95 metrics between two masks (values > 0)."""
        pred = (mask1 > 0).astype(bool)
        ref = (mask2 > 0).astype(bool)

        pred_sum = pred.sum()
        ref_sum = ref.sum()
        if pred_sum == 0 and ref_sum == 0:
            return 1.0, 0.0
        if pred_sum == 0 or ref_sum == 0:
            return 0.0, np.nan

        dsc = 2.0 * np.logical_and(pred, ref).sum() / (pred_sum + ref_sum)

        # If no spacing is provided, assume isotropic 1.0
        if spacing_xyz is None:
            spacing_xyz = (1.0, 1.0, 1.0) if pred.ndim == 3 else (1.0, 1.0)

        ref_img = sitk.GetImageFromArray(ref.astype(np.uint8))
        ref_img.SetSpacing(spacing_xyz)
        ref_surface = sitk.LabelContour(ref_img)
        ref_distance = sitk.Abs(
            sitk.SignedMaurerDistanceMap(ref_img, squaredDistance=False, useImageSpacing=True)
        )
        ref_surface_arr = sitk.GetArrayFromImage(ref_surface) > 0
        ref_distance_arr = sitk.GetArrayFromImage(ref_distance)

        pred_img = sitk.GetImageFromArray(pred.astype(np.uint8))
        pred_img.SetSpacing(spacing_xyz)
        pred_surface = sitk.LabelContour(pred_img)
        pred_distance = sitk.Abs(
            sitk.SignedMaurerDistanceMap(pred_img, squaredDistance=False, useImageSpacing=True)
        )
        pred_surface_arr = sitk.GetArrayFromImage(pred_surface) > 0
        pred_distance_arr = sitk.GetArrayFromImage(pred_distance)

        surface_distances = np.concatenate(
            [
                ref_distance_arr[pred_surface_arr],
                pred_distance_arr[ref_surface_arr],
            ]
        )
        if surface_distances.size == 0:
            return float(dsc), 0.0

        hd95 = float(np.percentile(surface_distances, 95))
        return float(dsc), hd95

    def _get_layer_1(self):
        """Get the first selected layer."""
        layer_name = get_value(self.layer_select_1)
        if layer_name is None:
            return None
        layer_name = layer_name[0]
        return self._viewer.layers[layer_name] if layer_name in self._viewer.layers else None

    def _get_layer_2(self):
        """Get the second selected layer."""
        layer_name = get_value(self.layer_select_2)
        if layer_name is None:
            return None
        layer_name = layer_name[0]
        return self._viewer.layers[layer_name] if layer_name in self._viewer.layers else None

    def on_layers_changed(self):
        """Called when either layer selection changes."""
        if self.auto_update_ckbx.isChecked():
            self.update_segmentation_metrics()

    @thread_worker(start_thread=True)
    def update_segmentation_metrics(self):
        """Compute and display metrics between the two selected layers."""
        layer1 = self._get_layer_1()
        layer2 = self._get_layer_2()

        if layer1 is None or layer2 is None:
            self.metrics_label.setText("DSC: --\nHD95: --")
            return

        data1 = np.asarray(layer1.data)
        data2 = np.asarray(layer2.data)

        if data1.shape != data2.shape:
            # Try to resample data2 onto data1's grid.  Use nearest-neighbour to preserve label values.
            zoom_factors = tuple(s1 / s2 for s1, s2 in zip(data1.shape, data2.shape))
            try:
                data2 = zoom(data2, zoom_factors, order=0, grid_mode=True).astype(data2.dtype)
            except Exception as exc:
                print(f"Segmentation metrics: resampling failed ({exc})")
                self.metrics_label.setText("DSC: n/a\nHD95: n/a")
                return
            if data2.shape != data1.shape:
                self.metrics_label.setText("DSC: n/a\nHD95: n/a")
                return

        # Use the reference layer's physical spacing (abs to remove the z-flip sign)
        spacing_zyx = tuple(abs(s) for s in layer1.scale)
        spacing_xyz = spacing_zyx[::-1]

        # Compute metrics between layers where values > 0
        dsc, hd95 = self._compute_dsc_hd95(data1, data2, spacing_xyz=spacing_xyz)
        hd95_text = "n/a" if np.isnan(hd95) else f"{hd95:.2f} mm"
        self.metrics_label.setText(f"DSC: {dsc:.4f}\nHD95: {hd95_text}")
        
        print(f"Updated metrics: DSC={dsc:.4f}, HD95={hd95_text}")

        if self.edit_log is not None and len(self.edit_log._log) > 0 and self.edit_log._log[-1]['event_type'] != "metrics_updated":
            self.edit_log.record({
                'event_group': 'metrics',
                'event_type': "metrics_updated",
                'timestamp': time.time(),
                'data': {
                    'dsc': dsc,
                    'hd95': hd95,
                    'layer_1': layer1.name,
                    'layer_2': layer2.name,
                }
            })

    def closeEvent(self, event=None):
        self.stop_updates()
        self._viewer.layers.events.inserted.disconnect(self.layer_select_1._update)
        self._viewer.layers.events.removed.disconnect(self.layer_select_1._update)
        for layer in self.layer_select_1.layer_names:
            layer.events.name.disconnect(self.layer_select_1._update)
        self.layer_select_1.close()
        self.layer_select_1.deleteLater()

        self._viewer.layers.events.inserted.disconnect(self.layer_select_2._update)
        self._viewer.layers.events.removed.disconnect(self.layer_select_2._update)
        for layer in self.layer_select_2.layer_names:
            layer.events.name.disconnect(self.layer_select_2._update)
        self.layer_select_2.close()
        self.layer_select_2.deleteLater()