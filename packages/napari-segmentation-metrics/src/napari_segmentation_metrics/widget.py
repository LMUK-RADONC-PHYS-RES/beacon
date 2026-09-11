import numpy as np
import surface_distance
from scipy.ndimage import affine_transform

from napari.layers import Labels
from napari.viewer import Viewer

from qtpy.QtCore import (
    QObject,
    QRunnable,
    QThreadPool,
    QTimer,
    Qt,
    Signal,
    Slot,
)
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)




def _safe_assd(
    asd_ref_to_seg: float,
    asd_seg_to_ref: float,
) -> float:
    """
    Compute the symmetric average surface distance.
    """
    values = np.asarray(
        [asd_ref_to_seg, asd_seg_to_ref],
        dtype=float,
    )

    if np.all(np.isnan(values)):
        return float("nan")

    with np.errstate(invalid="ignore"):
        return float(np.nanmean(values))


def _compute_metrics(
    reference_data: np.ndarray,
    segmentation_data: np.ndarray,
    spacing_mm: tuple[float, ...],
    tolerance_mm: float,
    reference_label_id: int,
    segmentation_label_id: int,
) -> dict[str, float]:
    reference = np.asarray(reference_data) == reference_label_id
    segmentation = np.asarray(segmentation_data) == segmentation_label_id

    if reference.shape != segmentation.shape:
        raise ValueError(
            "Reference and segmentation shapes differ: "
            f"{reference.shape} != {segmentation.shape}."
        )

    if reference.ndim not in (2, 3):
        raise ValueError(
            "Only 2D and 3D segmentations are currently supported. "
            f"Received {reference.ndim}D data."
        )

    intersection = np.count_nonzero(reference & segmentation)

    n_reference = np.count_nonzero(reference)
    n_segmentation = np.count_nonzero(segmentation)

    dice_denominator = n_reference + n_segmentation

    if dice_denominator == 0:
        dice = float("nan")
    else:
        dice = float(
            2.0 * intersection / dice_denominator
        )

    union = np.count_nonzero(reference | segmentation)

    if union == 0:
        jaccard = float("nan")
    else:
        jaccard = float(intersection / union)

    with np.errstate(
        divide="ignore",
        invalid="ignore",
        over="ignore",
    ):
        surface_distances = (
            surface_distance.compute_surface_distances(
                reference,
                segmentation,
                spacing_mm=spacing_mm,
            )
        )

        (asd_ref_to_seg,asd_seg_to_ref) = surface_distance.compute_average_surface_distance(surface_distances)

        hd95 = surface_distance.compute_robust_hausdorff(
            surface_distances,
            95.0,
        )

        hausdorff = surface_distance.compute_robust_hausdorff(
            surface_distances,
            100.0,
        )

        surface_dice = (
            surface_distance.compute_surface_dice_at_tolerance(
                surface_distances,
                tolerance_mm=tolerance_mm,
            )
        )

    asd_ref_to_seg = float(asd_ref_to_seg)
    asd_seg_to_ref = float(asd_seg_to_ref)

    assd = _safe_assd(
        asd_ref_to_seg,
        asd_seg_to_ref,
    )

    return {
        "dice": float(dice),
        "jaccard": float(jaccard),
        "asd_ref_to_seg": asd_ref_to_seg,
        "asd_seg_to_ref": asd_seg_to_ref,
        "assd": float(assd),
        "hd95": float(hd95),
        "hausdorff": float(hausdorff),
        "surface_dice": float(surface_dice),
    }



class _MetricWorkerSignals(QObject):
    finished = Signal(object, int)
    failed = Signal(str, int)

class _MetricWorker(QRunnable):
    def __init__(
        self,
        reference_data: np.ndarray,
        segmentation_data: np.ndarray,
        spacing_mm: tuple[float, ...],
        tolerance_mm: float,
        reference_label_id: int,
        segmentation_label_id: int,
        state_serial: int,
        resample_matrix: np.ndarray | None = None,
        resample_offset: np.ndarray | None = None,
    ):
        super().__init__()
        self.reference_data = reference_data
        self.segmentation_data = segmentation_data
        self.spacing_mm = spacing_mm
        self.tolerance_mm = tolerance_mm
        self.reference_label_id = reference_label_id
        self.segmentation_label_id = segmentation_label_id
        self.state_serial = state_serial
        self.resample_matrix = resample_matrix
        self.resample_offset = resample_offset
        self.signals = _MetricWorkerSignals()

    @Slot()
    def run(self):
        try:
            segmentation_data = self.segmentation_data
            if self.resample_matrix is not None:
                segmentation_data = affine_transform(
                    segmentation_data,
                    matrix=self.resample_matrix,
                    offset=self.resample_offset,
                    output_shape=self.reference_data.shape,
                    order=0,
                    mode="constant",
                    cval=0,
                    prefilter=False,
                )

            result = _compute_metrics(
                reference_data=self.reference_data,
                segmentation_data=segmentation_data,
                spacing_mm=self.spacing_mm,
                tolerance_mm=self.tolerance_mm,
                reference_label_id=self.reference_label_id,
                segmentation_label_id=self.segmentation_label_id,
            )
        except Exception as exc:
            self.signals.failed.emit(
                f"{type(exc).__name__}: {exc}",
                self.state_serial,
            )
            return

        self.signals.finished.emit(result, self.state_serial)


class CollapsibleSection(QWidget):
    def __init__(
        self,
        title: str,
        expanded: bool = True,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(
            Qt.DownArrow if expanded else Qt.RightArrow
        )
        self.toggle_button.clicked.connect(self._set_expanded)

        self.content = QWidget()
        self.content.setVisible(expanded)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content)

    def set_content_layout(self, layout) -> None:
        layout.setContentsMargins(12, 2, 0, 6)
        self.content.setLayout(layout)

    def _set_expanded(self, expanded: bool) -> None:
        self.toggle_button.setArrowType(
            Qt.DownArrow if expanded else Qt.RightArrow
        )
        self.content.setVisible(expanded)


class SegmentationMetricsWidget(QWidget):
    """
    Standalone Napari widget for geometric segmentation metrics.

    Public API
    ----------
    set_reference_layer(layer_or_name)
    set_segmentation_layer(layer_or_name)
    set_reference_label_id(label_id)
    set_segmentation_label_id(label_id)
    set_surface_tolerance_mm(value)
    """

    def __init__(
        self,
        viewer: Viewer,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self.viewer = viewer

        self._thread_pool = QThreadPool(self)

        self._thread_pool.setMaxThreadCount(1)

        self._worker_running = False
        self._active_worker: _MetricWorker | None = None

        self._state_serial = 0

        self._running_state_serial: int | None = None
        self._recompute_pending = False

        self._watched_layers: set[Labels] = set()

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(300)
        self._debounce_timer.timeout.connect(self.compute)

        self._build_ui()

        self.viewer.layers.events.inserted.connect(
            self._on_layer_list_changed
        )

        self.viewer.layers.events.removed.connect(
            self._on_layer_list_changed
        )

        if hasattr(self.viewer.layers.events, "renamed"):
            self.viewer.layers.events.renamed.connect(
                self._on_layer_list_changed
            )

        self._refresh_layer_combos()


    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        layer_group = QGroupBox("Segmentation Metrics")
        layer_layout = QFormLayout(layer_group)

        self.reference_combo = QComboBox()
        self.segmentation_combo = QComboBox()
        self.reference_label_spin = QSpinBox()
        self.segmentation_label_spin = QSpinBox()

        for spin in (self.reference_label_spin, self.segmentation_label_spin):
            spin.setRange(0, 2_147_483_647)
            spin.setValue(1)
            spin.setKeyboardTracking(False)
            spin.valueChanged.connect(self._on_label_id_changed)

        self.reference_combo.currentIndexChanged.connect(
            self._on_layer_selection_changed
        )

        self.segmentation_combo.currentIndexChanged.connect(
            self._on_layer_selection_changed
        )

        layer_layout.addRow(
            "Reference",
            self.reference_combo,
        )
        layer_layout.addRow(
            "Reference label ID",
            self.reference_label_spin,
        )
        layer_layout.addRow(
            "Segmentation",
            self.segmentation_combo,
        )
        layer_layout.addRow(
            "Segmentation label ID",
            self.segmentation_label_spin,
        )

        main_layout.addWidget(layer_group)

        self.options_section = CollapsibleSection(
            "Options", expanded=False
        )
        options_layout = QFormLayout()

        self.surface_tolerance_spin = QDoubleSpinBox()

        self.surface_tolerance_spin.setRange(
            0.0,
            1000.0,
        )

        self.surface_tolerance_spin.setDecimals(2)
        self.surface_tolerance_spin.setSingleStep(0.5)
        self.surface_tolerance_spin.setValue(2.0)
        self.surface_tolerance_spin.setSuffix(" mm")

        self.surface_tolerance_spin.setKeyboardTracking(False)

        self.surface_tolerance_spin.valueChanged.connect(
            self._on_tolerance_changed
        )

        self.auto_update_checkbox = QCheckBox(
            "Auto update"
        )

        self.auto_update_checkbox.setChecked(True)

        self.auto_update_checkbox.toggled.connect(
            self._on_auto_update_toggled
        )

        options_layout.addRow(
            "Surface Dice tolerance",
            self.surface_tolerance_spin,
        )

        options_layout.addRow(
            "",
            self.auto_update_checkbox,
        )

        self.options_section.set_content_layout(options_layout)
        main_layout.addWidget(self.options_section)

        self.overlap_section = CollapsibleSection(
            "Overlap", expanded=True
        )
        overlap_layout = QFormLayout()

        self.dice_value = self._create_result_label()
        self.jaccard_value = self._create_result_label()

        overlap_layout.addRow(
            "Dice",
            self.dice_value,
        )

        overlap_layout.addRow(
            "Jaccard",
            self.jaccard_value,
        )

        self.overlap_section.set_content_layout(overlap_layout)
        main_layout.addWidget(self.overlap_section)

        self.surface_section = CollapsibleSection(
            "Surface distance", expanded=True
        )
        surface_layout = QFormLayout()

        self.asd_ref_to_seg_value = (
            self._create_result_label()
        )

        self.asd_seg_to_ref_value = (
            self._create_result_label()
        )

        self.assd_value = self._create_result_label()
        self.hd95_value = self._create_result_label()
        self.hausdorff_value = self._create_result_label()
        self.surface_dice_value = (
            self._create_result_label()
        )

        surface_layout.addRow(
            "ASD ref → seg",
            self.asd_ref_to_seg_value,
        )

        surface_layout.addRow(
            "ASD seg → ref",
            self.asd_seg_to_ref_value,
        )

        surface_layout.addRow(
            "ASSD",
            self.assd_value,
        )

        surface_layout.addRow(
            "HD95",
            self.hd95_value,
        )

        surface_layout.addRow(
            "Hausdorff",
            self.hausdorff_value,
        )

        self.surface_dice_title = QLabel()

        surface_layout.addRow(
            self.surface_dice_title,
            self.surface_dice_value,
        )

        self._update_surface_dice_title()

        self.surface_section.set_content_layout(surface_layout)
        main_layout.addWidget(self.surface_section)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.compute_button = QPushButton("Compute")
        self.compute_button.clicked.connect(self.compute)

        button_layout.addWidget(self.compute_button)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

        self.status_label = QLabel(
            "Select a reference and segmentation layer"
        )

        self.status_label.setWordWrap(True)

        main_layout.addWidget(self.status_label)

        main_layout.addStretch()

    @staticmethod
    def _create_result_label() -> QLabel:
        label = QLabel("—")

        try:
            label.setAlignment(
                Qt.AlignRight | Qt.AlignVCenter
            )
        except AttributeError:
            label.setAlignment(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            )

        return label


    def set_reference_layer(
        self,
        layer_or_name: Labels | str | None,
    ) -> None:
        """
        Programmatically select the reference Labels layer.
        """

        layer = self._resolve_label_layer(
            layer_or_name
        )

        self._set_combo_layer(
            self.reference_combo,
            layer,
        )

    def set_segmentation_layer(
        self,
        layer_or_name: Labels | str | None,
    ) -> None:
        """
        Programmatically select the segmentation Labels layer.
        """

        layer = self._resolve_label_layer(
            layer_or_name
        )

        self._set_combo_layer(
            self.segmentation_combo,
            layer,
        )

    def set_surface_tolerance_mm(
        self,
        tolerance_mm: float,
    ) -> None:
        """
        Programmatically set Surface Dice tolerance.
        """

        tolerance_mm = float(tolerance_mm)

        if not np.isfinite(tolerance_mm):
            raise ValueError(
                "Surface Dice tolerance must be finite."
            )

        if tolerance_mm < 0:
            raise ValueError(
                "Surface Dice tolerance cannot be negative."
            )

        self.surface_tolerance_spin.setValue(
            tolerance_mm
        )

    def set_reference_label_id(self, label_id: int) -> None:
        self.reference_label_spin.setValue(int(label_id))

    def set_segmentation_label_id(self, label_id: int) -> None:
        self.segmentation_label_spin.setValue(int(label_id))

    @property
    def reference_layer(self) -> Labels | None:
        return self.reference_combo.currentData()

    @property
    def segmentation_layer(self) -> Labels | None:
        return self.segmentation_combo.currentData()

    @property
    def surface_tolerance_mm(self) -> float:
        return float(
            self.surface_tolerance_spin.value()
        )

    def _labels_layers(self) -> list[Labels]:
        """
        Return every Labels layer currently present in Napari.

        No BEACON / nnInteractive-specific classes or names are used.
        """

        return [
            layer
            for layer in self.viewer.layers
            if isinstance(layer, Labels)
        ]

    def _on_layer_list_changed(
        self,
        event=None,
    ):
        self._refresh_layer_combos()

    def _refresh_layer_combos(self):
        """
        Repopulate both combo boxes while preserving selections whenever
        possible.
        """

        previous_reference = (
            self.reference_combo.currentData()
        )

        previous_segmentation = (
            self.segmentation_combo.currentData()
        )

        layers = self._labels_layers()

        self.reference_combo.blockSignals(True)
        self.segmentation_combo.blockSignals(True)

        try:
            self.reference_combo.clear()
            self.segmentation_combo.clear()

            self.reference_combo.addItem(
                "<none>",
                None,
            )

            self.segmentation_combo.addItem(
                "<none>",
                None,
            )

            for layer in layers:
                self.reference_combo.addItem(
                    layer.name,
                    layer,
                )

                self.segmentation_combo.addItem(
                    layer.name,
                    layer,
                )

            if previous_reference in layers:
                self._set_combo_layer_no_signal(
                    self.reference_combo,
                    previous_reference,
                )

            elif layers:
                self._set_combo_layer_no_signal(
                    self.reference_combo,
                    layers[0],
                )

            if previous_segmentation in layers:
                self._set_combo_layer_no_signal(
                    self.segmentation_combo,
                    previous_segmentation,
                )

            elif len(layers) >= 2:
                self._set_combo_layer_no_signal(
                    self.segmentation_combo,
                    layers[1],
                )

        finally:
            self.reference_combo.blockSignals(False)
            self.segmentation_combo.blockSignals(False)

        self._on_layer_selection_changed()

    def _resolve_label_layer(
        self,
        layer_or_name: Labels | str | None,
    ) -> Labels | None:
        if layer_or_name is None:
            return None

        if isinstance(layer_or_name, Labels):
            if layer_or_name not in self.viewer.layers:
                raise ValueError(
                    "The provided Labels layer is not present "
                    "in this Napari viewer."
                )

            return layer_or_name

        if isinstance(layer_or_name, str):
            for layer in self.viewer.layers:
                if (
                    isinstance(layer, Labels)
                    and layer.name == layer_or_name
                ):
                    return layer

            raise ValueError(
                f"No Labels layer named "
                f"'{layer_or_name}' exists."
            )

        raise TypeError(
            "Expected a napari.layers.Labels instance, "
            "layer name, or None."
        )

    @staticmethod
    def _combo_index_for_layer(
        combo: QComboBox,
        layer: Labels | None,
    ) -> int:
        for index in range(combo.count()):
            if combo.itemData(index) is layer:
                return index

        return -1

    def _set_combo_layer_no_signal(
        self,
        combo: QComboBox,
        layer: Labels | None,
    ):
        index = self._combo_index_for_layer(
            combo,
            layer,
        )

        if index < 0:
            raise ValueError(
                "Layer is not available in the selector."
            )

        combo.setCurrentIndex(index)

    def _set_combo_layer(
        self,
        combo: QComboBox,
        layer: Labels | None,
    ):
        index = self._combo_index_for_layer(
            combo,
            layer,
        )

        if index < 0:
            raise ValueError(
                "Layer is not available in the selector."
            )

        previous = combo.currentIndex()

        combo.setCurrentIndex(index)

        if previous == index:
            self._on_layer_selection_changed()

    def _disconnect_selected_layer_events(self):
        for layer in list(self._watched_layers):
            self._disconnect_layer_data_events(layer)

        self._watched_layers.clear()

    def _connect_selected_layer_events(self):
        layers = {
            layer
            for layer in (
                self.reference_layer,
                self.segmentation_layer,
            )
            if layer is not None
        }

        for layer in layers:
            self._connect_layer_data_events(layer)

        self._watched_layers = layers

    def _connect_layer_data_events(
        self,
        layer: Labels,
    ):
        event_names = (
            "data",
            "labels_update",
            "set_data",
        )

        for event_name in event_names:
            emitter = getattr(
                layer.events,
                event_name,
                None,
            )

            if emitter is None:
                continue

            try:
                emitter.connect(
                    self._on_selected_layer_data_changed
                )
            except Exception:
                pass

    def _disconnect_layer_data_events(
        self,
        layer: Labels,
    ):
        event_names = (
            "data",
            "labels_update",
            "set_data",
        )

        for event_name in event_names:
            emitter = getattr(
                layer.events,
                event_name,
                None,
            )

            if emitter is None:
                continue

            try:
                emitter.disconnect(
                    self._on_selected_layer_data_changed
                )
            except Exception:
                pass

    def _on_layer_selection_changed(
        self,
        *args,
    ):
        self._disconnect_selected_layer_events()
        self._connect_selected_layer_events()

        self._state_serial += 1

        self._clear_results()

        if (
            self.reference_layer is None
            or self.segmentation_layer is None
        ):
            self.status_label.setText(
                "Select a reference and segmentation layer."
            )
            return

        self.status_label.setText(
            "Ready."
        )

        self._schedule_compute()

    def _on_selected_layer_data_changed(
        self,
        event=None,
    ):
        self._state_serial += 1

        if not self.auto_update_checkbox.isChecked():
            self.status_label.setText(
                "Segmentation changed — click Compute."
            )
            return

        self.status_label.setText(
            "Segmentation changed…"
        )

        self._schedule_compute()


    def _schedule_compute(
        self,
        event=None,
    ):
        """Restart the debounce timer."""

        if not self.auto_update_checkbox.isChecked():
            return

        self._debounce_timer.start()

    def _on_label_id_changed(self, value: int):
        self._state_serial += 1
        self._clear_results()

        if self.auto_update_checkbox.isChecked():
            self._schedule_compute()
        else:
            self.status_label.setText(
                "Label ID changed — click Compute."
            )

    def _on_tolerance_changed(
        self,
        value: float,
    ):
        self._state_serial += 1

        self._update_surface_dice_title()

        if self.auto_update_checkbox.isChecked():
            self._schedule_compute()
        else:
            self.status_label.setText(
                "Surface Dice tolerance changed — click Compute."
            )

    def _on_auto_update_toggled(
        self,
        checked: bool,
    ):
        if not checked:
            self._debounce_timer.stop()
            return

        if (
            self.reference_layer is not None
            and self.segmentation_layer is not None
        ):
            self._debounce_timer.start()

    def _update_surface_dice_title(self):
        tolerance = float(
            self.surface_tolerance_spin.value()
        )

        if tolerance.is_integer():
            tolerance_text = str(int(tolerance))
        else:
            tolerance_text = (
                f"{tolerance:g}"
            )

        self.surface_dice_title.setText(
            f"Surface Dice @ {tolerance_text} mm"
        )

    @staticmethod
    def _layer_world_frame(
        layer: Labels,
        ndim: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        origin = np.zeros(ndim, dtype=float)
        origin_world = np.asarray(
            layer.data_to_world(tuple(origin)),
            dtype=float,
        )[-ndim:]

        axes = []
        for axis in range(ndim):
            point = origin.copy()
            point[axis] = 1.0
            point_world = np.asarray(
                layer.data_to_world(tuple(point)),
                dtype=float,
            )[-ndim:]
            axes.append(point_world - origin_world)

        return origin_world, np.column_stack(axes)

    @classmethod
    def _layers_share_grid(
        cls,
        reference_layer: Labels,
        segmentation_layer: Labels,
        reference_shape: tuple[int, ...],
        segmentation_shape: tuple[int, ...],
    ) -> bool:
        if reference_shape != segmentation_shape:
            return False

        ndim = len(reference_shape)
        ref_origin, ref_linear = cls._layer_world_frame(reference_layer, ndim)
        seg_origin, seg_linear = cls._layer_world_frame(segmentation_layer, ndim)

        return np.allclose(
            ref_origin, seg_origin, rtol=1e-5, atol=1e-5
        ) and np.allclose(
            ref_linear, seg_linear, rtol=1e-5, atol=1e-6
        )

    @classmethod
    def _reference_spacing_mm(
        cls,
        reference_layer: Labels,
        ndim: int,
    ) -> tuple[float, ...]:
        _, linear = cls._layer_world_frame(reference_layer, ndim)
        gram = linear.T @ linear
        diagonal = np.diag(np.diag(gram))

        if not np.allclose(gram, diagonal, rtol=1e-5, atol=1e-6):
            raise ValueError(
                "The reference layer uses a sheared/non-orthogonal grid."
            )

        spacing_mm = tuple(
            float(np.linalg.norm(linear[:, axis]))
            for axis in range(ndim)
        )
        if any(not np.isfinite(value) or value <= 0 for value in spacing_mm):
            raise ValueError(f"Invalid reference voxel spacing: {spacing_mm}")

        return spacing_mm

    @staticmethod
    def _reference_to_segmentation_mapping(
        reference_layer: Labels,
        segmentation_layer: Labels,
        ndim: int,
    ) -> tuple[np.ndarray, np.ndarray]:
        origin = np.zeros(ndim, dtype=float)
        world_origin = reference_layer.data_to_world(tuple(origin))
        seg_origin = np.asarray(
            segmentation_layer.world_to_data(world_origin),
            dtype=float,
        )[-ndim:]

        matrix = np.zeros((ndim, ndim), dtype=float)
        for axis in range(ndim):
            point = origin.copy()
            point[axis] = 1.0
            world_point = reference_layer.data_to_world(tuple(point))
            seg_point = np.asarray(
                segmentation_layer.world_to_data(world_point),
                dtype=float,
            )[-ndim:]
            matrix[:, axis] = seg_point - seg_origin

        return matrix, seg_origin

    @Slot()
    def compute(self):
        """Start metric calculation in the background worker."""

        reference_layer = self.reference_layer
        segmentation_layer = self.segmentation_layer

        if (
            reference_layer is None
            or segmentation_layer is None
        ):
            self._clear_results()

            self.status_label.setText(
                "Select a reference and segmentation layer."
            )
            return

        if self._worker_running:
            if (
                self._running_state_serial
                != self._state_serial
            ):
                self._recompute_pending = True

            return

        try:
            reference_raw = reference_layer.data
            segmentation_raw = segmentation_layer.data

            if isinstance(
                reference_raw,
                (list, tuple),
            ):
                raise ValueError(
                    "Multiscale reference Labels layers are not "
                    "supported."
                )

            if isinstance(
                segmentation_raw,
                (list, tuple),
            ):
                raise ValueError(
                    "Multiscale segmentation Labels layers are not "
                    "supported."
                )

            reference_data = np.array(
                reference_raw,
                copy=True,
            )

            segmentation_data = np.array(
                segmentation_raw,
                copy=True,
            )

            if reference_data.ndim not in (2, 3):
                raise ValueError(
                    "Only 2D and 3D segmentations are supported."
                )

            if segmentation_data.ndim != reference_data.ndim:
                raise ValueError(
                    "Reference and segmentation dimensionality differ."
                )

            spacing_mm = self._reference_spacing_mm(
                reference_layer,
                reference_data.ndim,
            )

            if self._layers_share_grid(
                reference_layer,
                segmentation_layer,
                reference_data.shape,
                segmentation_data.shape,
            ):
                resample_matrix = None
                resample_offset = None
            else:
                resample_matrix, resample_offset = (
                    self._reference_to_segmentation_mapping(
                        reference_layer,
                        segmentation_layer,
                        reference_data.ndim,
                    )
                )

        except Exception as exc:
            self._clear_results()

            self.status_label.setText(
                f"Error: {exc}"
            )
            return

        tolerance_mm = float(
            self.surface_tolerance_spin.value()
        )
        reference_label_id = self.reference_label_spin.value()
        segmentation_label_id = self.segmentation_label_spin.value()

        state_serial = self._state_serial

        worker = _MetricWorker(
            reference_data=reference_data,
            segmentation_data=segmentation_data,
            spacing_mm=spacing_mm,
            tolerance_mm=tolerance_mm,
            reference_label_id=reference_label_id,
            segmentation_label_id=segmentation_label_id,
            state_serial=state_serial,
            resample_matrix=resample_matrix,
            resample_offset=resample_offset,
        )

        worker.signals.finished.connect(
            self._on_metrics_finished
        )

        worker.signals.failed.connect(
            self._on_metrics_failed
        )

        self._active_worker = worker

        self._worker_running = True
        self._running_state_serial = (
            state_serial
        )

        self.compute_button.setText(
            "Computing…"
        )

        self.status_label.setText(
            "Computing metrics…"
        )

        self._thread_pool.start(worker)

    @Slot(object, int)
    def _on_metrics_finished(
        self,
        result: dict[str, float],
        state_serial: int,
    ):
        self._worker_running = False
        self._running_state_serial = None
        self._active_worker = None

        if state_serial == self._state_serial:
            self._display_results(result)

            self.status_label.setText(
                "Updated."
            )

        if self._recompute_pending:
            self._recompute_pending = False
            self.compute()
            return

        self.compute_button.setText(
            "Compute"
        )

    @Slot(str, int)
    def _on_metrics_failed(
        self,
        message: str,
        state_serial: int,
    ):
        self._worker_running = False
        self._running_state_serial = None
        self._active_worker = None

        if state_serial == self._state_serial:
            self._clear_results()

            self.status_label.setText(
                f"Error: {message}"
            )

        if self._recompute_pending:
            self._recompute_pending = False
            self.compute()
            return

        self.compute_button.setText(
            "Compute"
        )

    @staticmethod
    def _format_overlap(
        value: float,
    ) -> str:
        if np.isnan(value):
            return "n/a"

        if np.isposinf(value):
            return "∞"

        if np.isneginf(value):
            return "-∞"

        return f"{value:.4f}"

    @staticmethod
    def _format_distance(
        value: float,
    ) -> str:
        if np.isnan(value):
            return "n/a"

        if np.isposinf(value):
            return "∞ mm"

        if np.isneginf(value):
            return "-∞ mm"

        return f"{value:.2f} mm"

    def _display_results(
        self,
        result: dict[str, float],
    ):
        self.dice_value.setText(
            self._format_overlap(
                result["dice"]
            )
        )

        self.jaccard_value.setText(
            self._format_overlap(
                result["jaccard"]
            )
        )

        self.asd_ref_to_seg_value.setText(
            self._format_distance(
                result["asd_ref_to_seg"]
            )
        )

        self.asd_seg_to_ref_value.setText(
            self._format_distance(
                result["asd_seg_to_ref"]
            )
        )

        self.assd_value.setText(
            self._format_distance(
                result["assd"]
            )
        )

        self.hd95_value.setText(
            self._format_distance(
                result["hd95"]
            )
        )

        self.hausdorff_value.setText(
            self._format_distance(
                result["hausdorff"]
            )
        )

        self.surface_dice_value.setText(
            self._format_overlap(
                result["surface_dice"]
            )
        )

    def _clear_results(self):
        labels = (
            self.dice_value,
            self.jaccard_value,
            self.asd_ref_to_seg_value,
            self.asd_seg_to_ref_value,
            self.assd_value,
            self.hd95_value,
            self.hausdorff_value,
            self.surface_dice_value,
        )

        for label in labels:
            label.setText("—")

    def closeEvent(
        self,
        event,
    ):
        self._debounce_timer.stop()

        self._disconnect_selected_layer_events()

        try:
            self.viewer.layers.events.inserted.disconnect(
                self._on_layer_list_changed
            )
        except Exception:
            pass

        try:
            self.viewer.layers.events.removed.disconnect(
                self._on_layer_list_changed
            )
        except Exception:
            pass

        if hasattr(
            self.viewer.layers.events,
            "renamed",
        ):
            try:
                self.viewer.layers.events.renamed.disconnect(
                    self._on_layer_list_changed
                )
            except Exception:
                pass

        self._state_serial += 1

        super().closeEvent(event)


__all__ = [
    "SegmentationMetricsWidget",
]