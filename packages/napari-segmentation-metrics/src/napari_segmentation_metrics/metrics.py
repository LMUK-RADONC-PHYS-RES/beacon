from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import surface_distance as sd


@dataclass(frozen=True)
class MetricsResult:
    dice: float
    jaccard: float
    asd_ref_to_seg_mm: float
    asd_seg_to_ref_mm: float
    assd_mm: float
    hd95_mm: float
    hausdorff_mm: float
    surface_dice: float


def _nan_result(dice: float, jaccard: float, surface_dice: float) -> MetricsResult:
    nan = float("nan")
    return MetricsResult(
        dice=dice,
        jaccard=jaccard,
        asd_ref_to_seg_mm=nan,
        asd_seg_to_ref_mm=nan,
        assd_mm=nan,
        hd95_mm=nan,
        hausdorff_mm=nan,
        surface_dice=surface_dice,
    )


def compute_segmentation_metrics(
    reference: np.ndarray,
    segmentation: np.ndarray,
    spacing_mm: tuple[float, ...],
    surface_tolerance_mm: float = 2.0,
) -> MetricsResult:
    reference = np.asarray(reference) > 0
    segmentation = np.asarray(segmentation) > 0

    if reference.shape != segmentation.shape:
        raise ValueError(
            "Reference and segmentation must have the same array shape. "
            "The plugin intentionally does not silently resample masks."
        )

    if reference.ndim not in (2, 3):
        raise ValueError("Only 2D and 3D label maps are supported.")

    if len(spacing_mm) != reference.ndim:
        raise ValueError(
            f"spacing_mm has {len(spacing_mm)} values but the mask is "
            f"{reference.ndim}D."
        )

    if surface_tolerance_mm < 0:
        raise ValueError("Surface Dice tolerance must be >= 0 mm.")

    n_ref = int(reference.sum())
    n_seg = int(segmentation.sum())

    if n_ref == 0 and n_seg == 0:
        return _nan_result(dice=1.0, jaccard=1.0, surface_dice=1.0)

    if n_ref == 0 or n_seg == 0:
        return _nan_result(dice=0.0, jaccard=0.0, surface_dice=0.0)

    intersection = int(np.logical_and(reference, segmentation).sum())
    union = int(np.logical_or(reference, segmentation).sum())

    dice = 2.0 * intersection / (n_ref + n_seg)
    jaccard = intersection / union

    surface_distances = sd.compute_surface_distances(
        reference,
        segmentation,
        spacing_mm=spacing_mm,
    )

    asd_ref_to_seg, asd_seg_to_ref = sd.compute_average_surface_distance(
        surface_distances
    )

    assd = 0.5 * (asd_ref_to_seg + asd_seg_to_ref)

    hd95 = sd.compute_robust_hausdorff(surface_distances, 95.0)
    hausdorff = sd.compute_robust_hausdorff(surface_distances, 100.0)

    surface_dice = sd.compute_surface_dice_at_tolerance(
        surface_distances,
        tolerance_mm=surface_tolerance_mm,
    )

    return MetricsResult(
        dice=float(dice),
        jaccard=float(jaccard),
        asd_ref_to_seg_mm=float(asd_ref_to_seg),
        asd_seg_to_ref_mm=float(asd_seg_to_ref),
        assd_mm=float(assd),
        hd95_mm=float(hd95),
        hausdorff_mm=float(hausdorff),
        surface_dice=float(surface_dice),
    )