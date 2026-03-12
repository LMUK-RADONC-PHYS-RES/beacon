import json
from pathlib import Path

import threading
import time
import torch
import os
import cv2
from magicgui import magicgui
from typing import TYPE_CHECKING
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
from napari.qt.threading import thread_worker
from qtpy.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
import traceback

from napari_promptable import BaseWidget3D


class PromptableSegmentationWidget3DSAM(BaseWidget3D):
    def __init__(self, viewer: Viewer, **kwargs):
        super().__init__(viewer, **kwargs)
        self.autorun_ckbx.setChecked(False)
        self.run_button.setEnabled(False)

    def setup_hyperparameter_gui(self, _layout):
        _ = setup_label(_layout, "Threshold:")
        self.threshold_slider = setup_editdoubleslider(
            _layout, 2, -3, 3.0, 0.5, function=lambda: self.on_hyperparameter_update(), include_buttons=False
        )

        self.autocast_cbk = setup_checkbox(
            _layout, "Autocast to bfloat16", False, function=lambda: self.on_hyperparameter_update()
        )
        pass

    def setup_model_selection_gui(self, _scroll_layout):
        pass
        # log view
        _container, _layout = setup_vcollapsiblegroupbox(
            _scroll_layout, "Setup", True)

        _ = setup_label(_layout, "Select model:")

        model_options = ["MedSAM2-May2025"]

        self.model_selection = setup_combobox(
            _layout, options=model_options, function=lambda: print(
                "Model Selection Changed")
        )

        _ = setup_iconbutton(
            _layout, "Initialize", "new_labels", self._viewer.theme, lambda: self.on_model_change()
        )

    def on_model_change(self):
        self.reset_model()
        self.load_model()

    def load_model(self):
        try:
            from sam2.build_sam import build_sam2_camera_predictor, build_sam2
            from sam2.sam2_image_predictor import SAM2ImagePredictor

            checkpoint = "/app/MedSAM2_latest.pt"
            if not os.path.exists(checkpoint):
                base_path = os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                checkpoint = os.path.join(base_path, "MedSAM2_latest.pt")
            
            if not os.path.exists(checkpoint):
                show_info("Downloading MedSAM2 model from Huggingface...")
                from huggingface_hub import hf_hub_download
                local_checkpoints_dir = None
                if os.path.exists("/app/checkpoints"):
                    local_checkpoints_dir = "/app/checkpoints"
                checkpoint = hf_hub_download(repo_id="wanglab/MedSAM2", filename="MedSAM2_latest.pt", local_dir=local_checkpoints_dir)

            model_cfg = "configs/sam2.1_hiera_t512.yaml"
            self.predictor = build_sam2_camera_predictor(
                model_cfg, checkpoint, device="cuda" if torch.cuda.is_available() else "cpu")
            set_value(self.threshold_slider, self.predictor.mask_threshold)

        except Exception as e:
            self.predictor = None

            show_warning(f"Failed to load model. {e}")
            show_warning("Empty preditions will be returned.")
            return

    def reset_model(self):
        pass

    def predict(self):
        prompt_type = get_value(self.prompt_type_select)[0]
        img_layer = get_value(self.layerselect_a)[1]

        self.predictor.mask_threshold = get_value(self.threshold_slider)

        img_data = self._viewer.layers[img_layer].data.astype(np.float32)
        # normalize the image data to 0-255 range if it's not already
        img_data = (img_data - np.min(img_data)) / \
            (np.max(img_data) - np.min(img_data)) * 255
        img_data = img_data.astype(np.uint8)

        N = len(img_data.shape)
        if N != 3:
            show_warning(
                f"Input image must be 3D. Current dimension is {N}D.")
            return

        if prompt_type == "Mask":
            mask_prompt_layer = self.prompt_layers['mask']
            prompt_frames = self._viewer.dims.current_step
            print(self.prompt_frame_index_view_1,
                    self.prompt_frame_index_view_2, self.prompt_frame_index_view_3)
            prompt_frames = [self.prompt_frame_index_view_1,
                                self.prompt_frame_index_view_2, self.prompt_frame_index_view_3]
            scale_factors = self._viewer.layers[img_layer].scale
            # invert prompt frames where scale factor is negative to shape - frame
            # for i in range(3):
            #    if scale_factors[i] < 0:
            #        prompt_frames[i] = img_data.shape[i] - 1 - prompt_frames[i]
            # in a single line
            prompt_frames = [img_data.shape[i] - 1 - prompt_frames[i]
                                if scale_factors[i] < 0 else prompt_frames[i] for i in range(3)]

            def save_preview(img, mask, filename):
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
                contour, _ = cv2.findContours(mask.astype(
                    np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(img, contour, -1, (0, 255, 0), 2)
                cv2.imwrite(filename, img)

            mask_1 = mask_prompt_layer.data[prompt_frames[0]]
            mask_2 = mask_prompt_layer.data[:, prompt_frames[1]]
            mask_3 = mask_prompt_layer.data[:, :, prompt_frames[2]]

            #save_preview(
            #    img_data[prompt_frames[0]], mask_prompt_layer.data[prompt_frames[0]], "view1.png")
            #save_preview(img_data[:, prompt_frames[1]],
            #                mask_prompt_layer.data[:, prompt_frames[1]], "view2.png")
            #save_preview(img_data[:, :, prompt_frames[2]],
            #                mask_prompt_layer.data[:, :, prompt_frames[2]], "view3.png")

            print("USING SAM2")
            from napari_promptable_sam2.sam2_utils import propagate_along_path, merge_results, view_1_to_view_2, view_1_to_view_3, mask_view_2_to_view_1, center_of_mass, mask_view_3_to_view_1
            
            volume_labels = mask_prompt_layer.data
            volume_data = img_data
            sam_mask_threshold = self.predictor.mask_threshold
            center_slice = prompt_frames[0]
            
            with torch.inference_mode(), (torch.autocast("cuda", dtype=torch.bfloat16) if get_value(self.autocast_cbk) else nullcontext()):

                results_1 = merge_results(propagate_along_path(volume_data[:center_slice+1][::-1], self.predictor, threshold=sam_mask_threshold, keep_logits=True, reset_state=True, initialization="mask", mask_prompt=volume_labels[center_slice]),
                                                propagate_along_path(volume_data[center_slice:], self.predictor, threshold=sam_mask_threshold, keep_logits=True, reset_state=True, initialization="mask", mask_prompt=volume_labels[center_slice]))
                # do propagation
                volume_data_view2 = view_1_to_view_2(volume_data)
                volume_labels_view2 = view_1_to_view_2(volume_labels)
                center_slice_2 = prompt_frames[1]
                results_2 = merge_results(propagate_along_path(volume_data_view2[:center_slice_2+1][::-1], self.predictor, threshold=sam_mask_threshold, keep_logits=True, reset_state=True, initialization="mask", mask_prompt=volume_labels_view2[center_slice_2]),
                                            propagate_along_path(volume_data_view2[center_slice_2:], self.predictor, threshold=sam_mask_threshold, keep_logits=True, reset_state=True,  initialization="mask", mask_prompt=volume_labels_view2[center_slice_2]))
                results_2["masks"] = mask_view_2_to_view_1(results_2["masks"])
                # view 3
                volume_data_view3 = view_1_to_view_3(volume_data)
                volume_labels_view3 = view_1_to_view_3(volume_labels).copy()
                center_slice_3 = prompt_frames[2]
                results_3 = merge_results(propagate_along_path(volume_data_view3[:center_slice_3+1][::-1], self.predictor, threshold=sam_mask_threshold, keep_logits=True, reset_state=True, initialization="mask", mask_prompt=volume_labels_view3[center_slice_3]),
                                            propagate_along_path(volume_data_view3[center_slice_3:], self.predictor, threshold=sam_mask_threshold, keep_logits=True, reset_state=True, initialization="mask", mask_prompt=volume_labels_view3[center_slice_3]))
                results_3["masks"] = mask_view_3_to_view_1(results_3["masks"])
                m1 = results_1["masks"]
                m2 = results_2["masks"]
                m3 = results_3["masks"]
                # m_threshold2 = (np.array([m1.sum(), m2.sum(), m3.sum()])>20).sum()
                union = m1
                # union = np.sum([m1, m2, m3], axis=0) >= (m_threshold-1 if m_threshold>1 else 1)
                out_mask_masks = union.astype(np.uint8)  # Convert to uint8
        else:
            return
            
        # Merge the predicted mask into the preview using the base class
        # helper so overwrite/indices/object-id logic is respected.
        #self.add_prediction_to_preview(out_mask_masks, transposed=True)
        return out_mask_masks, None, True
