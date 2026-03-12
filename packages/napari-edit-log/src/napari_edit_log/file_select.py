"""
Adapted from https://github.com/MIC-DKFZ/napari_toolkit
License:
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "{}"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright {yyyy} {name of copyright owner}

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""
import os
from typing import Callable, Optional

from qtpy.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from napari_toolkit.utils.utils import connect_widget


class QDirSelect(QWidget):
    """A widget for selecting and displaying a directory path.

    This widget consists of a button to open a directory selection dialog
    and a line edit to display the selected path.

    Attributes:
        default_dir (Optional[str]): The default directory for the selection dialog.
        button (QPushButton): The button that opens the directory selection dialog.
        line_edit (QLineEdit): The read-only field displaying the selected directory.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        text: str = "Select",
        read_only: bool = True,
        default_dir: Optional[str] = None,
    ) -> None:
        """Initializes the QDirSelect widget.

        Args:
            parent (Optional[QWidget], optional): The parent widget. Defaults to None.
            text (str, optional): The label text for the directory selection button. Defaults to "Select".
            read_only (bool, optional): Whether the line edit is read-only. Defaults to True.
            default_dir (Optional[str], optional): The initial directory to open in the dialog. Defaults to None.
        """
        super().__init__(parent)
        self.default_dir = default_dir

        self._layout = QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.button = QPushButton(text)
        self._layout.addWidget(self.button, stretch=1)

        self.line_edit = QLineEdit("")
        self.line_edit.setReadOnly(read_only)
        self._layout.addWidget(self.line_edit, stretch=2)

        self.button.clicked.connect(self.select_directory)

        self.setLayout(self._layout)

    def select_directory(self):
        """Opens a dialog to select a directory and updates the label."""
        _dialog = QFileDialog(self)
        _dialog.setDirectory(os.getcwd() if self.default_dir is None else self.default_dir)

        _output_dir = _dialog.getExistingDirectory(
            self,
            "Select an Output Directory",
            options=QFileDialog.DontUseNativeDialog | QFileDialog.ShowDirsOnly,
        )
        
        if _output_dir != "":
            self.set_dir(_output_dir)

    def set_dir(self, directory):
        """Sets the displayed directory in the line edit.

        Args:
            directory (str): The directory path to display.
        """
        self.line_edit.setText(f"{directory}")

    def get_dir(self):
        """Retrieves the currently selected directory.

        Returns:
            str: The currently displayed directory path.
        """
        return self.line_edit.text()


class QFileSelect(QWidget):
    """A widget for selecting and displaying a file path.

    This widget provides a button to open a file selection dialog and a line
    edit field to display the selected file path.

    Attributes:
        default_dir (Optional[str]): The default directory for the file selection dialog.
        save_file (bool): Whether the widget should open a save file dialog instead of an open file dialog.
        filtering (Optional[str]): A filter string for restricting file types (e.g., "Images (*.png *.jpg)").
        button (QPushButton): The button that opens the file selection dialog.
        line_edit (QLineEdit): The read-only field displaying the selected file path.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        filtering: Optional[str] = None,
        text: str = "Select",
        read_only: bool = True,
        default_dir: Optional[str] = None,
        save_file: bool = False,
    ) -> None:
        """Initializes the QFileSelect widget.

        Args:
            parent (Optional[QWidget], optional): The parent widget. Defaults to None.
            filtering (Optional[str], optional): A filter string to restrict file types (e.g., "Images (*.png *.jpg)"). Defaults to None.
            text (str, optional): The label text for the file selection button. Defaults to "Select".
            read_only (bool, optional): Whether the line edit is read-only. Defaults to True.
            default_dir (Optional[str], optional): The initial directory to open in the dialog. Defaults to None.
            save_file (bool, optional): Whether the widget should open a save file dialog instead of an open file dialog. Defaults to False.
        """

        super().__init__(parent)
        self.default_dir = default_dir
        self.save_file = save_file
        self.filtering = filtering

        self._layout = QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.button = QPushButton(text)
        self._layout.addWidget(self.button, stretch=1)

        self.line_edit = QLineEdit("")
        self.line_edit.setReadOnly(read_only)
        self._layout.addWidget(self.line_edit, stretch=2)

        self.button.clicked.connect(self.select_file)

        self.setLayout(self._layout)

    def select_file(self):
        """Opens a dialog to select a directory and updates the label."""
        _dialog = QFileDialog(self)
        _dialog.setDirectory(os.getcwd() if self.default_dir is None else self.default_dir)

        if self.save_file:
            _output_file, _filter = _dialog.getSaveFileName(
                self, "Select File", filter=self.filtering, options=QFileDialog.DontUseNativeDialog
            )
        else:
            _output_file, _filter = _dialog.getOpenFileName(
                self, "Select File", filter=self.filtering, options=QFileDialog.DontUseNativeDialog
            )
        if _filter != "":
            self.set_file(_output_file)

    def set_file(self, directory):
        """Sets the displayed file path in the line edit.

        Args:
            file_path (str): The file path to display.
        """
        self.line_edit.setText(f"{directory}")

    def get_file(self):
        """Retrieves the currently selected file path.

        Returns:
            str: The currently displayed file path.
        """
        return self.line_edit.text()


def setup_fileselect(
    layout: QLayout,
    text: str = "Select",
    read_only: bool = True,
    default_dir: str = None,
    filtering: str = None,
    function: Optional[Callable] = None,
    tooltips: Optional[str] = None,
    shortcut: Optional[str] = None,
    stretch: int = 1,
) -> QWidget:
    """Creates and adds a file selection widget to the given layout.

    This function initializes a `QFileSelect` widget configured for selecting
    existing files and integrates it into the provided layout.

    Args:
        layout (QLayout): The layout to which the file selection widget will be added.
        text (str, optional): The label text for the file selection button. Defaults to "Select".
        read_only (bool, optional): Whether the file path field is read-only. Defaults to True.
        default_dir (Optional[str], optional): The initial directory to open in the dialog. Defaults to None.
        filtering (Optional[str], optional): A filter string to restrict file types (e.g., "Images (*.png *.jpg)"). Defaults to None.
        function (Optional[Callable[[], None]], optional): A callback function triggered when a file is selected. Defaults to None.
        tooltips (Optional[str], optional): Tooltip text for the widget. Defaults to None.
        shortcut (Optional[str], optional): A keyboard shortcut for quick access. Defaults to None.
        stretch (int, optional): The stretch factor in the layout. Defaults to 1.

    Returns:
        QWidget: The initialized `QFileSelect` widget.
    """

    _widget = QFileSelect(
        text=text,
        filtering=filtering,
        read_only=read_only,
        default_dir=default_dir,
        save_file=False,
    )
    _widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return connect_widget(
        layout,
        _widget,
        widget_event=_widget.button.clicked,
        function=function,
        shortcut=shortcut,
        tooltips=tooltips,
        stretch=stretch,
    )


def setup_savefileselect(
    layout: QLayout,
    text: str = "Select",
    read_only: bool = True,
    default_dir: str = None,
    filtering: str = None,
    function: Optional[Callable] = None,
    tooltips: Optional[str] = None,
    shortcut: Optional[str] = None,
    stretch: int = 1,
) -> QWidget:
    """Creates and adds a file selection widget for saving files to the given layout.

    This function initializes a `QFileSelect` widget configured for saving files
    and integrates it into the provided layout.

    Args:
        layout (QLayout): The layout to which the save file selection widget will be added.
        text (str, optional): The label text for the file selection button. Defaults to "Select".
        read_only (bool, optional): Whether the file path field is read-only. Defaults to True.
        default_dir (Optional[str], optional): The initial directory to open in the dialog. Defaults to None.
        filtering (Optional[str], optional): A filter string to restrict file types (e.g., "Text Files (*.txt)"). Defaults to None.
        function (Optional[Callable[[], None]], optional): A callback function triggered when a file is selected. Defaults to None.
        tooltips (Optional[str], optional): Tooltip text for the widget. Defaults to None.
        shortcut (Optional[str], optional): A keyboard shortcut for quick access. Defaults to None.
        stretch (int, optional): The stretch factor in the layout. Defaults to 1.

    Returns:
        QWidget: The initialized `QFileSelect` widget for saving files.
    """
    _widget = QFileSelect(
        text=text, filtering=filtering, read_only=read_only, default_dir=default_dir, save_file=True
    )
    _widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    return connect_widget(
        layout,
        _widget,
        widget_event=_widget.button.clicked,
        function=function,
        shortcut=shortcut,
        tooltips=tooltips,
        stretch=stretch,
    )


def setup_dirselect(
    layout: QLayout,
    text: str = "Select",
    read_only: bool = True,
    default_dir: str = None,
    function: Optional[Callable] = None,
    tooltips: Optional[str] = None,
    shortcut: Optional[str] = None,
    stretch: int = 1,
) -> QWidget:
    """Creates and adds a directory selection widget to the given layout.

    This function initializes a `QDirSelect` widget configured for selecting directories
    and integrates it into the provided layout.

    Args:
        layout (QLayout): The layout to which the directory selection widget will be added.
        text (str, optional): The label text for the directory selection button. Defaults to "Select".
        read_only (bool, optional): Whether the directory path field is read-only. Defaults to True.
        default_dir (Optional[str], optional): The initial directory to open in the dialog. Defaults to None.
        function (Optional[Callable[[], None]], optional): A callback function triggered when a directory is selected. Defaults to None.
        tooltips (Optional[str], optional): Tooltip text for the widget. Defaults to None.
        shortcut (Optional[str], optional): A keyboard shortcut for quick access. Defaults to None.
        stretch (int, optional): The stretch factor in the layout. Defaults to 1.

    Returns:
        QWidget: The initialized `QDirSelect` widget.
    """
    _widget = QDirSelect(text=text, read_only=read_only, default_dir=default_dir)
    _widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return connect_widget(
        layout,
        _widget,
        widget_event=_widget.button.clicked,
        function=function,
        shortcut=shortcut,
        tooltips=tooltips,
        stretch=stretch,
    )