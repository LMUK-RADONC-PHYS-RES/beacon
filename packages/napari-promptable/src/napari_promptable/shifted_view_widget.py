
from copy import deepcopy

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import qthrottled

import napari
from napari.components.viewer_model import ViewerModel
from napari.layers import Labels, Layer, Vectors
from napari.qt import QtViewer
from napari.utils.action_manager import action_manager
from napari.utils.events.event import WarningEmitter
from napari.utils.notifications import show_info


def copy_layer(layer: Layer, name: str = ''):
    data, state, layer_type_strin = layer.as_layer_data_tuple()
    res_layer = layer.__class__(layer.data, **state)
    res_layer.metadata['viewer_name'] = name
    return res_layer

def get_property_names(layer: Layer):
    klass = layer.__class__
    res = []
    for event_name, event_emitter in layer.events.emitters.items():
        if isinstance(event_emitter, WarningEmitter):
            continue
        if event_name in ('thumbnail', 'name'):
            continue
        if (
            isinstance(getattr(klass, event_name, None), property)
            and getattr(klass, event_name).fset is not None
        ):
            res.append(event_name)
    return res



class own_partial:
    """
    Workaround for deepcopy not copying partial functions
    (Qt widgets are not serializable)
    """

    def __init__(self, func, *args, **kwargs) -> None:
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __call__(self, *args, **kwargs):
        return self.func(*(self.args + args), **{**self.kwargs, **kwargs})

    def __deepcopy__(self, memodict=None):
        if memodict is None:
            memodict = {}
        return own_partial(
            self.func,
            *deepcopy(self.args, memodict),
            **deepcopy(self.kwargs, memodict),
        )

class QtViewerWrap(QtViewer):
    def __init__(self, main_viewer, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.main_viewer = main_viewer

    def _qt_open(
        self,
        filenames: list,
        stack: bool,
        plugin: str | None = None,
        layer_type: str | None = None,
        **kwargs,
    ):
        """for drag and drop open files"""
        self.main_viewer.window._qt_viewer._qt_open(
            filenames, stack, plugin, layer_type, **kwargs
        )

class ShiftedLabelWidget(QWidget):
    """Widget containing multiple viewers with shifted views."""

    def __init__(self, viewer: napari.Viewer) -> None:
        super().__init__()


class ShiftedViewerWidget(QSplitter):
    """The main widget of the example."""

    def __init__(self, viewer: napari.Viewer) -> None:
        super().__init__()
        self.viewer = viewer
        self.viewer_model1 = ViewerModel(title='model1')
        self._block = False
        self.qt_viewer1 = QtViewerWrap(viewer, self.viewer_model1)
        viewer_splitter = QSplitter()
        viewer_splitter.setOrientation(Qt.Orientation.Horizontal)
        viewer_splitter.addWidget(self.qt_viewer1)
        viewer_splitter.setContentsMargins(0, 0, 0, 0)

        self.addWidget(viewer_splitter)

        self.build_gui()
        self.setup_connections()

    def build_gui(self):

        main_layout = QVBoxLayout(self)

        _scroll_widget, _scroll_layout = setup_vscrollarea(main_layout)

        _container, _layout = setup_vgroupbox(
        _scroll_layout, "Image Selection:")
        # layer select for image layer
        self.layerselect_a = setup_layerselect(
            _layout, self._viewer, Image, function=lambda: self.on_image_layer_change()
        )


    def setup_connections(self):
        for layer in self.viewer.layers:
            self.viewer_model1.layers.append(copy_layer(layer, 'model1'))
            for name in get_property_names(layer):
                getattr(layer.events, name).connect(
                    own_partial(self._property_sync, name)
                )

            if isinstance(layer, Labels):
                layer.events.set_data.connect(self._set_data_refresh)
                layer.events.labels_update.connect(self._set_data_refresh)
                self.viewer_model1.layers[
                    layer.name
                ].events.set_data.connect(self._set_data_refresh)
                
                layer.events.labels_update.connect(self._set_data_refresh)
                self.viewer_model1.layers[
                    layer.name
                ].events.labels_update.connect(self._set_data_refresh)
                
            layer.events.name.connect(self._sync_name)


        self.viewer.layers.events.inserted.connect(self._layer_added)
        self.viewer.layers.events.removed.connect(self._layer_removed)
        self.viewer.layers.events.moved.connect(self._layer_moved)
        self.viewer.layers.selection.events.active.connect(
            self._layer_selection_changed
        )
        self.viewer.dims.events.current_step.connect(self._point_update)
        self.viewer_model1.dims.events.current_step.connect(self._point_update)
        self.viewer.dims.events.order.connect(self._order_update)
        self.viewer.events.reset_view.connect(self._reset_view)
        self.viewer_model1.events.status.connect(self._status_update)

    def _status_update(self, event):
        self.viewer.status = event.value

    def _reset_view(self):
        self.viewer_model1.reset_view()

    def _layer_selection_changed(self, event):
        """
        update of current active layer
        """
        if self._block:
            return

        if event.value is None:
            self.viewer_model1.layers.selection.active = None
            return

        self.viewer_model1.layers.selection.active = self.viewer_model1.layers[
            event.value.name
        ]

    def _point_update(self, event):
        for model in [self.viewer, self.viewer_model1]:
            if model.dims is event.source:
                continue
            if len(self.viewer.layers) != len(model.layers):
                continue
            # TODO show past
            model.dims.current_step = event.value 

    def _order_update(self):
        order = list(self.viewer.dims.order)
        self.viewer_model1.dims.order = order

    def _layer_added(self, event):
        """add layer to additional viewers and connect all required events"""
        self.viewer_model1.layers.insert(
            event.index, copy_layer(event.value, 'model1')
        )
       
        for name in get_property_names(event.value):
            getattr(event.value.events, name).connect(
                own_partial(self._property_sync, name)
            )

        if isinstance(event.value, Labels):
            event.value.events.set_data.connect(self._set_data_refresh)
            event.value.events.labels_update.connect(self._set_data_refresh)
            self.viewer_model1.layers[
                event.value.name
            ].events.set_data.connect(self._set_data_refresh)
            
            event.value.events.labels_update.connect(self._set_data_refresh)
            self.viewer_model1.layers[
                event.value.name
            ].events.labels_update.connect(self._set_data_refresh)
            
        if event.value.name != '.cross':
            self.viewer_model1.layers[event.value.name].events.data.connect(
                self._sync_data
            )

        event.value.events.name.connect(self._sync_name)

        self._order_update()

    def _sync_name(self, event):
        """sync name of layers"""
        index = self.viewer.layers.index(event.source)
        self.viewer_model1.layers[index].name = event.source.name

    def _sync_data(self, event):
        """sync data modification from additional viewers"""
        # Ignore events from the main viewer triggered from this widget to avoid recursion
        if self._block:
            return
        # Ignore in-progress events for performance reasons
        if hasattr(event, 'action') and event.action in ['adding', 'removing', 'changing']:
            return

        for model in [self.viewer, self.viewer_model1]:
            layer = model.layers[event.source.name]
            if layer is event.source:
                continue
            try:
                self._block = True
                layer.data = event.source.data
            finally:
                self._block = False

    def _set_data_refresh(self, event):
        """
        synchronize data refresh between layers
        """
        if self._block:
            return
        # Ignore in-progress events for performance reasons
        if hasattr(event, 'action') and event.action in ['adding', 'removing', 'changing']:
            return
        for model in [self.viewer, self.viewer_model1]:
            layer = model.layers[event.source.name]
            if layer is event.source:
                continue
            try:
                self._block = True
                layer.refresh()
            finally:
                self._block = False

    def _layer_removed(self, event):
        """remove layer in all viewers"""
        self.viewer_model1.layers.pop(event.index)

    def _layer_moved(self, event):
        """update order of layers"""
        dest_index = (
            event.new_index
            if event.new_index < event.index
            else event.new_index + 1
        )
        self.viewer_model1.layers.move(event.index, dest_index)

    def _property_sync(self, name, event):
        """Sync layers properties (except the name)"""
        if event.source not in self.viewer.layers:
            return
        try:
            self._block = True
            setattr(
                self.viewer_model1.layers[event.source.name],
                name,
                getattr(event.source, name),
            )
        finally:
            self._block = False

def _setup_multiple_viewer_widget(_layout=None, viewer: napari.Viewer=None):
    """
    Setup the MultipleViewerWidget and add it to the viewer.
    """
    widget = MultipleViewerWidget(viewer)
    
    if _layout is not None:
        _layout.addWidget(widget)
    
    return widget