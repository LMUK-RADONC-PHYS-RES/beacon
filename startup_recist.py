import napari
from napari import Viewer

viewer = Viewer()

from recist_study_app import StudyAppWidget
widget = StudyAppWidget(viewer)
viewer.window.add_dock_widget(
    widget, name="RECIST study", area="left"
)
napari.run()
