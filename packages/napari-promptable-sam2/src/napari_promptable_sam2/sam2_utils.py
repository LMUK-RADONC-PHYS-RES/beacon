import numpy as np
import torch
import cv2
import tqdm


from scipy.ndimage import find_objects,center_of_mass

def bounding_box(label):
    box = find_objects(label)[0]
    box_prompt = np.array([
        box[1].start, box[0].start, box[1].stop, box[0].stop
    ], dtype=np.float32)
    return box_prompt

from contextlib import nullcontext
def propagate_along_path(slices, predictor, threshold=0.5, reset_state=True, keep_logits=True,adaptive_thresholding=True,exit_early=True, autocast= False, initialization="point", point_prompts=None, point_labels=None, mask_prompt=None, box_prompt=None, disable_tqdm=True):
    results = {
        "masks": [],
    }
    if slices.shape[0] == 0:
        return None

    if keep_logits:
        results["logits"] = []
    image = cv2.cvtColor(slices[0], cv2.COLOR_GRAY2RGB)
    predictor.load_first_frame(image)
    if initialization == "point":
        _, out_obj_ids, out_mask_logits = predictor.add_new_points(frame_idx=0, obj_id=0, points=point_prompts, labels=point_labels)
    elif initialization == "mask":
        _, out_obj_ids, out_mask_logits = predictor.add_new_mask(frame_idx=0, obj_id=0, mask=mask_prompt)
    elif initialization == "box":
        _, out_obj_ids, out_mask_logits = predictor.add_new_prompt(frame_idx=0, obj_id=0, bbox=box_prompt)

    results["masks"].append(out_mask_logits>threshold)
    if keep_logits:
        results["logits"].append(out_mask_logits)
    
    for i in tqdm.tqdm(range(1, len(slices)), disable=disable_tqdm):
        image = cv2.cvtColor(slices[i], cv2.COLOR_GRAY2RGB)
        out_obj_ids, out_mask_logits = predictor.track(image)
        results["masks"].append(out_mask_logits>threshold)
        if keep_logits:
            results["logits"].append(out_mask_logits)
        if exit_early:
            mask_is_empty = (out_mask_logits> threshold).sum() == 0
            if mask_is_empty:
                print(f"Mask is empty at step {i}, stopping early.")
                # append missing masks
                skipped_steps = len(slices) - i - 1
                for j in range(skipped_steps):
                    results["masks"].append(torch.zeros_like(out_mask_logits))
                    if keep_logits:
                        results["logits"].append(torch.full_like(out_mask_logits, -1024))
                break

    results["masks"] = torch.stack(results["masks"], dim=0).squeeze().cpu().numpy()
    if keep_logits:
        results["logits"] = torch.stack(results["logits"], dim=0).squeeze().cpu().numpy()

    if keep_logits and adaptive_thresholding and initialization == "mask":
        from scipy.optimize import minimize_scalar
        def optimize_threshold(logits, label):
            def dice_loss(threshold):
                mask = logits > threshold
                intersection = np.sum(mask * label)
                union = np.sum(mask) + np.sum(label)
                dice = 2 * intersection / union
                return 1 - dice

            res = minimize_scalar(dice_loss, bounds=(-5.0,5.0), method="bounded")
            best_threshold = res.x
            best_dice = 1 - res.fun
            return best_threshold, best_dice
        x_test = []
        with torch.inference_mode():#, torch.autocast("cuda", dtype=torch.bfloat16):
            image = cv2.cvtColor(slices[0], cv2.COLOR_GRAY2RGB)
            predictor.load_first_frame(image)
            _, out_obj_ids, out_mask_logits = predictor.add_new_mask(frame_idx=0, obj_id=0, mask=mask_prompt)
            x_test.append(out_mask_logits)
            
            for i in tqdm.tqdm(range(1, 3), disable=disable_tqdm):
                image = cv2.cvtColor(slices[0], cv2.COLOR_GRAY2RGB)
                out_obj_ids, out_mask_logits = predictor.track(image)
                x_test.append(out_mask_logits)
            x_test = torch.stack(x_test, dim=0).squeeze().cpu().numpy()
        best_threshold, best_dice = optimize_threshold(x_test[-1], mask_prompt)
        
        results["masks"] = results["logits"] > best_threshold

    
    if reset_state:
        predictor.reset_state()
        torch.cuda.empty_cache()
    return results

def merge_results(results_rev, results_fw):
    results = {}
    if results_rev is None:
        return results_fw
    if results_fw is None:
        return results_rev

    for key in results_rev.keys():
        results[key] = np.concatenate([results_rev[key][1:][::-1], results_fw[key]])
    return results

# helper functions for consensus views
def view_1_to_view_2(volume_data):
    volume_data = np.rot90(volume_data, axes=(0,1))
    return volume_data
def view_1_to_view_3(volume_data):
    volume_data = np.rot90(volume_data, axes=(0,2))
    volume_data = np.rot90(volume_data, axes=(1,2))
    return volume_data
def mask_view_2_to_view_1(mask_data):
    mask_data = np.rot90(mask_data,k=3, axes=(0,1))
    return mask_data
def mask_view_3_to_view_1(mask_data):
    mask_data = np.rot90(mask_data,k=3, axes=(1,2))
    mask_data = np.rot90(mask_data,k=3, axes=(0,2))
    return mask_data

def point_view_1_to_view_2(points):
    #point_prompts = np.array([[initial_point[1], initial_point[0]]], dtype=np.float32)
    return np.array([[point[1], point[0]] for point in points], dtype=np.float32)
    
def point_view_1_to_view_3(points):
    return np.array([[point[2], point[0]] for point in points], dtype=np.float32)