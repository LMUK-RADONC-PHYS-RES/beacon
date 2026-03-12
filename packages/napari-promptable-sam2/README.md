# napari-promptable-sam2

This plugin for [napari](https://napari.org/) provides a ui to quickly cycle through different images in a napari viewer.

<img src="./quick-view-screenshot.png" loading="lazy" alt="Quick view screenshot" width="500"/>

## Usage

Once installed, the plugin can be accessed from the napari plugins menu: `Plugins -> Promptable Segmentation SAM2 -> Variant`.

### 2D segmentation

In 2D, usage follows the base promptable segmentation plugin described [here](). SAM2 supports (positive and negative) point prompts, bounding boxes and mask/manual prompts.

> Note that when prompted with a mask, SAM2 will output this mask without changes. Mask prompts may thus be not helpful when using SAM2 for 2D segmentation, but for 2D+t or 3D segmentation (see below), where the (unchanged) mask is then propagated.

### 2D+t (or 3D) segmentation

With the 2D+t (or 3D) variant, a new subsection is added to the widget, compared to the base variant. This `propagation` section can be used to propagate a 2D mask prompt through time (or the 3rd dimension). The controlls select which dimension is used for propagation, and if propagationg is performad forwards/backwards. 

After setting up the propagation parameters, the `Step` and `Run` buttons can be used to start the propagation.

> Nota that the step button resets the SAM2-predictor before each step, so that each frame is predicted only based on the original mask prompt. Depending on the set threshold, this may lead to masks expanding or shrinking over time. The `Run` button starts a continous propagating, without resetting the predictor.

### 3D segmentation (orthogonal masks)

With orthogonal masks, the user provides masks in the three orthogonal planes (XY, XZ, YZ) and the plugin fuses these into a 3D segmentation.

For this purpose, the `View Control` section of the widget can be used cycle though the views (use napari's the image rotation feature where needed). By clicking the `Set Prompt` button, the current view's mask is marked to be used by the segmentation. After masks in all three planes are added, the `Predict` button is activated.

## Notes & Limitations

- The plugin is still under development, and some features may not work as expected.
