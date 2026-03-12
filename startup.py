import napari
from napari import Viewer

viewer = Viewer()

from artist_study_app import StudyAppWidget
widget = StudyAppWidget(viewer)
viewer.window.add_dock_widget(
    widget, name="ARTIST study", area="left"
)

napari.run()