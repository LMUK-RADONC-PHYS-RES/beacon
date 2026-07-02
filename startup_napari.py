import napari
from napari import Viewer

viewer = Viewer()

from artist_standalone_app import StandaloneAppWidget
#widget = StandaloneAppWidget(viewer)
#viewer.window.add_dock_widget(widget, name="ARTIST Standalone", area="left")

napari.run()
