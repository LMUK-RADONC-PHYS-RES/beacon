
from napari.components._viewer_mouse_bindings import dims_scroll

def inverted_scrolling(viewer, event):
    if "Control" in event.modifiers:
        # do normal zooming
        viewer.window._qt_viewer.canvas._scene_canvas.__class__.__bases__[0]._process_mouse_event(
            viewer.window._qt_viewer.canvas._scene_canvas, event)
        event.handled = True
    else:
        if event.native.inverted():
            viewer.dims._scroll_progress += event.delta[1]
        else:
            viewer.dims._scroll_progress -= event.delta[1]
        while abs(viewer.dims._scroll_progress) >= 1:
            if viewer.dims._scroll_progress < 0:
                viewer.dims._increment_dims_left()
                viewer.dims._scroll_progress += 1
            else:
                viewer.dims._increment_dims_right()
                viewer.dims._scroll_progress -= 1
        event.handled = True

def invert_scrolling(viewer: 'napari.viewer.Viewer'):
    if inverted_scrolling not in viewer.mouse_wheel_callbacks:
        viewer.mouse_wheel_callbacks.append(inverted_scrolling)
    if dims_scroll in viewer.mouse_wheel_callbacks:
        viewer.mouse_wheel_callbacks.remove(dims_scroll)

def reset_scrolling(viewer: 'napari.viewer.Viewer'):
    if inverted_scrolling in viewer.mouse_wheel_callbacks:
        viewer.mouse_wheel_callbacks.remove(inverted_scrolling)
    if dims_scroll not in viewer.mouse_wheel_callbacks:
        viewer.mouse_wheel_callbacks.insert(0,dims_scroll)

def is_inverted(viewer: 'napari.viewer.Viewer'):
    return inverted_scrolling in viewer.mouse_wheel_callbacks