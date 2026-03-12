import json
from pathlib import Path
import os
import threading
import time
import torch
import numpy as np
import cv2
from magicgui import magicgui
from typing import TYPE_CHECKING
from contextlib import nullcontext
from napari.utils.notifications import show_info, show_warning, show_error, show_console_notification
from napari import Viewer
from napari.layers import Labels, Shapes, Points, Image, Layer
from napari_toolkit.containers import setup_scrollarea, setup_vcollapsiblegroupbox, setup_vgroupbox, setup_vscrollarea
from napari_toolkit.containers.boxlayout import hstack
from napari_toolkit.utils import set_value
from napari_toolkit.data_structs import setup_list
from napari_toolkit.utils.widget_getter import get_value
from napari_toolkit.widgets import *
import traceback
from napari.qt.threading import thread_worker
from qtpy.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from napari_promptable import BaseWidget2D
from ._widget_2d_sam import PromptableSegmentationWidget2DSAM


class PromptableSegmentationWidget2DTSAM(PromptableSegmentationWidget2DSAM):
    def __init__(self, viewer: Viewer, **kwargs):
        super().__init__(viewer, **kwargs)
        if get_value(self.layerselect_a)[1] != -1:
            img_layer = get_value(self.layerselect_a)[0]
            N_dim = len(self._viewer.layers[img_layer].data.shape)
            self.propagation_dim_spinbox.setMaximum(N_dim-3)
        
        self.stop_propagation_after_frame = False

    def on_image_layer_change(self):
        super().on_image_layer_change()
        if get_value(self.layerselect_a)[1] != -1:
            img_layer = get_value(self.layerselect_a)[0]
            N_dim = len(self._viewer.layers[img_layer].data.shape)
            self.propagation_dim_spinbox.setMaximum(N_dim-3)

    def setup_second_propagation_gui(self, _scroll_layout):
        _group_box, _layout = setup_vcollapsiblegroupbox(
            _scroll_layout, text="Propagation:", collapsed=False)

        _ = setup_label(
            _layout, "Propagate the masks from the current preview to the next frame.")

        self.propagate_button = setup_iconbutton(
            None,
            "Step",
            "right_arrow",
            self._viewer.theme,
            tooltips="Run propagation to the next frame.",
            function=lambda: self.run_propagate_in_thread(),
        )
        self.propagate_button_continuos = setup_iconbutton(
            None,
            "Run",
            "right_arrow",
            self._viewer.theme,
            tooltips="Run propagation until the end or until 'Stop' is pressed.",
            function=lambda: self.run_propagate_in_thread_until_end(),
        )
        _ = hstack(_layout, [self.propagate_button,
                   self.propagate_button_continuos], stretch=[1, 1, 1])

        self.propagate_status_label = setup_label(_layout, "Status: Ready")

        _label = setup_label(None, "Propagation Dimension:")
        self.propagation_dim_spinbox = setup_spinbox(
            None, 0, 0, 1, tooltips="Dimension to propagate over.")

        _ = hstack(
            _layout, [_label, self.propagation_dim_spinbox], stretch=[0, 1])

        self.reverse_direction = setup_checkbox(
            _layout,
            "Reverse Direction",
            False,
            tooltips="",
            function=lambda: None
        )
        self.propagate_overwrite_cbx = setup_checkbox(
            _layout,
            "Overwrite Existing",
            False,
            tooltips="",
            function=lambda: None
        )

        pass

    def run_propagate_in_thread(self):
        """Start a background worker that runs predict() safely with a lock.

        Ensures only one prediction runs at a time. If multiple triggers occur
        while a prediction is running, a single additional rerun will be
        scheduled and reflected in the status label as "Re-run scheduled".
        """

        # If a prediction is currently running, schedule a rerun and update
        # the status immediately.
        print(f"locked {self.propagating_lock.locked()}")
        if self.propagating_lock.locked():
            return

        @thread_worker
        def _worker():
            # Acquire the lock and run predictions; the loop allows a single
            # additional run if self.rerun_after_lock becomes True while
            # executing.
            with self.propagating_lock:
                try:
                    with torch.inference_mode(), (torch.autocast("cuda", dtype=torch.bfloat16) if get_value(self.autocast_cbk) else nullcontext()):
                        return self.propagate()
                except Exception as e:
                    print(f"Error in on_prompt_update_event: {e}")
                    print(f"Traceback: {traceback.format_exc()}")

        worker = _worker()

        start_time = 0
        # Update UI when worker starts
        def _on_started():
            nonlocal start_time
            start_time = time.perf_counter()
            self.propagate_status_label.setText("Status: Running...")
        # Update UI when worker finishes or errors

        def _on_done(*args, **kwargs):
            end_time = time.perf_counter()
            elapsed_time = end_time - start_time
            self.propagate_status_label.setText(f"Status: (completed in {elapsed_time:.3f} s)")
        # Connect signals (thread_worker exposes started, finished, errored)
        worker.started.connect(_on_started)
        worker.finished.connect(_on_done)
        worker.errored.connect(_on_done)

        worker.start()

    def run_propagate_in_thread_until_end(self):
        # If a prediction is currently running
        if self.propagating_lock.locked():
            self.stop_propagation_after_frame = True
            return

        @thread_worker
        def _worker():
            # Acquire the lock and run predictions; the loop allows a single
            # additional run if self.rerun_after_lock becomes True while
            # executing.
            with self.propagating_lock:
                try:
                    # change button_text to "Stop"
                    with torch.inference_mode(), (torch.autocast("cuda", dtype=torch.bfloat16) if get_value(self.autocast_cbk) else nullcontext()):
                        start_time = time.perf_counter()
                        propagated_successfully = self.propagate(initialize=True)
                        end_time = time.perf_counter()
                        self.propagate_status_label.setText(f"Status: Running until stopped... ({end_time - start_time:.3f} s)")
                        self.stop_propagation_after_frame = False
                        while propagated_successfully and not self.stop_propagation_after_frame:
                            start_time = time.perf_counter()
                            propagated_successfully = self.propagate(initialize=False)
                            end_time = time.perf_counter()
                            self.propagate_status_label.setText(f"Status: Running until stopped... ({end_time - start_time:.3f} s)")
                        
                except Exception as e:
                    print(f"Error in on_prompt_update_event: {e}")
                    print(f"Traceback: {traceback.format_exc()}")

        worker = _worker()

        # Update UI when worker starts
        def _on_started():
            self.propagate_status_label.setText("Status: Running until stopped...")
            self.propagate_button_continuos.setText("Stop")
            #self.propagate_button.setEnabled(False)
        # Update UI when worker finishes or errors

        def _on_done(*args, **kwargs):
            self.propagate_status_label.setText("Status: Ready")
            self.propagate_button_continuos.setText("Run")
            #self.propagate_button.setEnabled(True)
        # Connect signals (thread_worker exposes started, finished, errored)
        worker.started.connect(_on_started)
        worker.finished.connect(_on_done)
        worker.errored.connect(_on_done)

        worker.start()

    def propagate(self, initialize=True):
        """
        Propagate the masks from the current preview to the next frame.

        Returns True if propagation was successful, False otherwise.
        """
        img_layer = get_value(self.layerselect_a)[1]

        self.predictor.mask_threshold = get_value(self.threshold_slider)

        frames = np.transpose(
            self._viewer.layers[img_layer].data, self._viewer.dims.order)

        N = len(frames.shape)

        if N < 3:
            show_warning("The selected image layer is not at least 3D (or 2D+t).")
            return
        
        current_steps = [
            self._viewer.dims.current_step[self._viewer.dims.order[i]]
            for i in range(N-2)
        ]
        #print("current_steps", current_steps)

        propagated_dim = get_value(self.propagation_dim_spinbox)

        #print("propagated_dim", propagated_dim)

        current_frame_idx = current_steps[propagated_dim]

        next_frame_idx = current_frame_idx + \
            1 if not get_value(
                self.reverse_direction) else current_frame_idx - 1

        max_frame_idx = frames.shape[propagated_dim]

        if next_frame_idx >= max_frame_idx or next_frame_idx < 0:
            show_warning("No more frames to propagate to.")
            return False

        current_frame_selector = tuple([
            *[current_steps[i] for i in range(N-2)],
            slice(None), slice(None)
        ])
        next_frame_selector = tuple([
            current_frame_selector[i] if i != propagated_dim else next_frame_idx for i in range(N)
        ]) 

        #print("Current frame selector:", current_frame_selector)
        #print("Next frame selector:", next_frame_selector)

        current_frame = frames[current_frame_selector]
        current_frame = cv2.normalize(current_frame, None, alpha=0,
                                      beta=255, norm_type=cv2.NORM_MINMAX).astype(np.uint8)
        current_frame = cv2.cvtColor(current_frame, cv2.COLOR_GRAY2RGB)
        
        next_frame = frames[next_frame_selector]
        next_frame = cv2.normalize(next_frame, None, alpha=0,
                                   beta=255, norm_type=cv2.NORM_MINMAX).astype(np.uint8)
        next_frame = cv2.cvtColor(next_frame, cv2.COLOR_GRAY2RGB)

        if initialize:
            try:
                self.predictor.reset_state()
            except:
                pass

            self.predictor.load_first_frame(current_frame)

        if self.preview_layer is None:
            show_warning(
                "No preview layer found. Please run prediction first.")
            return False

        transposed_preview_layer_data = np.transpose(
            self.preview_layer.data, self._viewer.dims.order)

        current_mask = transposed_preview_layer_data[current_frame_selector]

        if np.sum(current_mask) == 0:
            show_warning(
                "No mask found in the current frame of the preview layer. Please run prediction first.")
            return False

        current_mask = current_mask
        visibile_object_ids = np.unique(current_mask)
        visibile_object_ids = visibile_object_ids[visibile_object_ids != 0]

        if len(visibile_object_ids) == 0:
            show_warning(
                "No object found in the current frame of the preview layer. Please run prediction first.")
            return False

        if initialize:
            for object_id in visibile_object_ids:
                obj_mask = (current_mask == object_id).astype(np.uint8)
                _, out_obj_ids, out_mask_logits = self.predictor.add_new_mask(
                    frame_idx=0, obj_id=object_id, mask=obj_mask)

        out_obj_ids, out_mask_logits = self.predictor.track(next_frame)

        out_mask_masks = (
            out_mask_logits > self.predictor.mask_threshold).cpu().numpy().astype(np.uint8)

        current_next_mask = transposed_preview_layer_data[next_frame_selector]
        visibile_object_ids_in_next = np.unique(current_next_mask)
        visibile_object_ids_in_next = visibile_object_ids_in_next[visibile_object_ids_in_next != 0]

        updated_next_mask = np.zeros_like(current_next_mask)
        # Write the new masks to the next frame, respecting the overwrite setting
        for i, object_id in enumerate(visibile_object_ids):
            if object_id in visibile_object_ids_in_next and not get_value(self.propagate_overwrite_cbx):
                updated_next_mask[current_next_mask == object_id] = object_id
                continue

            next_object_mask = (
                out_mask_masks[i, 0] * object_id).astype(np.uint8)
            # only write to pixels that are not already occupied if not overwriting
            # -> lower ids have priority
            np.copyto(updated_next_mask, next_object_mask, where=(
                (next_object_mask > 0) & (updated_next_mask == 0)))

        np.copyto(
            transposed_preview_layer_data[next_frame_selector], updated_next_mask)

        # Copy to the backup data
        self.preview_label_data = self.preview_layer.data.copy()
        # go to next frame

        self._viewer.dims.set_current_step(propagated_dim, next_frame_idx)

        self.preview_layer.refresh()
        return True