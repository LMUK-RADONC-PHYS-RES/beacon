import time
import torch
import os
from magicgui import magicgui
from typing import TYPE_CHECKING
from functools import partial
import numpy as np

from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification
from napari import Viewer
from napari.layers import Labels, Shapes, Points, Image, Layer
from napari_toolkit.containers import setup_scrollarea, setup_vcollapsiblegroupbox, setup_vgroupbox, setup_vscrollarea
from napari_toolkit.containers.boxlayout import hstack
from napari_toolkit.utils import set_value
from napari_toolkit.data_structs import setup_list
from napari_toolkit.utils.widget_getter import get_value
from napari_toolkit.widgets import *
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
        self._guidance_layer = None

        self._reference_mask_data = None
        self._reference_mask_spacing = None
        self._reference_surface_data = None
        self._reference_distance_data = None

        self.edit_log = edit_log

        layout = QVBoxLayout(self)
        setup_label(layout, "Select comparison layer:")
        self.segmentation_layer_select = setup_layerselect(layout, viewer, Labels, function=self.on_segmentation_layer_changed)

        self.metrics_label = QLabel("DSC: --\nHD95: --")
        layout.addWidget(self.metrics_label)

        self.metrics_timer = QTimer(self)
        self.metrics_timer.setInterval(update_interval_ms)
        self.metrics_timer.timeout.connect(self.update_segmentation_metrics)

    def has_reference_mask(self) -> bool:
        return self._reference_mask_data is not None

    def set_reference_mask(self, reference_mask_layer:Labels, reference_mask: np.ndarray, spacing_xyz):
        self._guidance_layer = reference_mask_layer
        self._reference_mask_data = reference_mask.astype(bool)
        self._reference_mask_spacing = tuple(float(x) for x in spacing_xyz)

        ref_img = sitk.GetImageFromArray(self._reference_mask_data.astype(np.uint8))
        ref_img.SetSpacing(self._reference_mask_spacing)
        ref_surface = sitk.LabelContour(ref_img)
        ref_distance = sitk.Abs(
            sitk.SignedMaurerDistanceMap(ref_img, squaredDistance=False, useImageSpacing=True)
        )

        self._reference_surface_data = sitk.GetArrayFromImage(ref_surface) > 0
        self._reference_distance_data = sitk.GetArrayFromImage(ref_distance)

    def clear_reference_mask(self):
        self._guidance_layer = None
        self._reference_mask_data = None
        self._reference_mask_spacing = None
        self._reference_surface_data = None
        self._reference_distance_data = None
        self.metrics_label.setText("DSC: --\nHD95: --")

    def start_updates(self):
        self.metrics_timer.start()
        self.update_segmentation_metrics()

    def stop_updates(self):
        self.metrics_timer.stop()

    def on_segmentation_layer_changed(self):
        self.update_segmentation_metrics()

    def _compute_dsc_hd95(self, prediction_mask: np.ndarray):
        pred = prediction_mask.astype(bool)
        ref = self._reference_mask_data
        spacing_xyz = self._reference_mask_spacing

        pred_sum = pred.sum()
        ref_sum = ref.sum()
        if pred_sum == 0 and ref_sum == 0:
            return 1.0, 0.0
        if pred_sum == 0 or ref_sum == 0:
            return 0.0, np.nan

        dsc = 2.0 * np.logical_and(pred, ref).sum() / (pred_sum + ref_sum)

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
                self._reference_distance_data[pred_surface_arr],
                pred_distance_arr[self._reference_surface_data],
            ]
        )
        if surface_distances.size == 0:
            return float(dsc), 0.0

        hd95 = float(np.percentile(surface_distances, 95))
        return float(dsc), hd95

    def _get_current_segmentation_layer(self):
        segmentation_layer = get_value(self.segmentation_layer_select)
        if segmentation_layer is None:
            return None
        segmentation_layer = segmentation_layer[0]
        print(f"Selected segmentation layer: {segmentation_layer}")
        return self._viewer.layers[segmentation_layer] if segmentation_layer in self._viewer.layers else None

    def update_segmentation_metrics(self):
        if (
            self._reference_mask_data is None
            or self._reference_mask_spacing is None
            or self._reference_surface_data is None
            or self._reference_distance_data is None
        ):
            self.metrics_label.setText("DSC: --\nHD95: --")
            return

        segmentation_layer = self._get_current_segmentation_layer()
        if segmentation_layer is None:
            self.metrics_label.setText("DSC: --\nHD95: --")
            return

        segmentation = np.asarray(segmentation_layer.data) > 0
        if segmentation.shape != self._reference_mask_data.shape:
            self.metrics_label.setText("DSC: n/a\nHD95: n/a")
            return

        dsc, hd95 = self._compute_dsc_hd95(segmentation)
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
                }
            })