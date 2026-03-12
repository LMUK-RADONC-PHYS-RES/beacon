
<img src="images/logos.png" alt="Logos of the BZKF, Lighthouse, and LMU Klinikum" width="500" />

# BEACON - <ins>B</ins>ZKF int<ins>E</ins>ractive <ins>A</ins>I-based <ins>CON</ins>touring tool

A collection of napari plugins for interactive segmentation of multidimensional images, with a focus on medical imaging applications and high usability for non-technical users. 


<img src="images/Screenshot 2025-09-24 at 12.21.15.png" loading="lazy" alt="BEACON screenshot" width="500"/>

It also contains a number of applications built on top of these plugins, which implement specific workflows for different use cases. Most notably for the **ARTIST** study, which evaluates the effectiveness of interactive promptable image segmentation, provided by [nnInteractive](https://github.com/MIC-DKFZ/nnInteractive), for applications in treatment planning in radiotherapy.


## Overview

This repository is structured as a collection of napari plugins, located in either the `packages` (utility plugins) or `apps` (structured workflow plugins) subfolders. The repo also provides an example for setting up an ARTIST workflow study using a YAML config file located in `artist_study` and some example data in `example_data`.

### Workflow apps

- [**artist_study_app**](./apps/artist_study_app/) — a study management and annotation application for conducting controlled comparative segmentation studies. It supports loading YAML-based study protocols, managing multiple annotation methods (e.g. nnInteractive vs. manual segmentation), tracking user interactions, and multi-viewer setups.

- [**core_tool_apps**](./apps/core_tool_apps/) — a collection of lightweight utility widgets providing quick file browsing, manual editing, and view/size estimation functionality for segmentation workflows.


To implement these, a custom collection of napari layers was developed that hide unnecessary UI elements and restrict edits to those allowed in the workflow context. These include a [Labels](https://napari.org/stable/api/napari.layers.Labels.html) layer restricted to one object, a non-editable [Points](https://napari.org/stable/api/napari.layers.Points.html) layer for preview purposes, and a fixed [Image](https://napari.org/stable/api/napari.layers.Image.html) layer with support for quickly switching between different contrast presets.

- [**napari-beacon-layers**](./packages/napari-beacon-layers/) — custom napari layers for visualizing and editing segmentations.

### Individual plugins for AI-based segmentation

Two groups of plugins were developed for AI-based segmentation: one based on the [napari-nninteractive](https://github.com/MIC-DKFZ/napari-nninteractive) plugin for 3D segmentation, and another using [SAM2](https://github.com/facebookresearch/sam2) for 2D segmentation.

### For 3D segmentation 

- [**napari-nninteractive-minimal**](./packages/napari-nninteractive-minimal/) — a simplified version of the excellent [napari-nninteractive](https://github.com/MIC-DKFZ/napari-nninteractive) plugin for interactive segmentation using nnInteractive. This plugin removes some of the more advanced features of the original plugin to provide a more streamlined experience for non-technical users. It also prevents users from accidentally breaking out of the intended workflow, for example by accidentally loading a different image or modifying the napari viewer in a way that breaks the plugin.

- [**napari-manual-segmentation**](./packages/napari-manual-segmentation/) — a plugin for manual segmentation, with a workflow and UI aligned to the simplified napari-nninteractive-minimal plugin.

### For 2D segmentation 

- [**napari-promptable**](./packages/napari-promptable/) - an interactive segmentation widget that supports multi-object workflows and serves as the base class for model-specific plugins.
Based on this core plugin, several model-backed segmentation plugins are provided:
- [**napari-promptable-sam2**](packages/napari-promptable-sam2/) — segmentation in 2D, 2D+t, or 3D using a [sam2](https://github.com/facebookresearch/sam2)-based model

### Utility plugins

The repository also contains some utility plugins:

- [**napari-edit-log**](./packages/napari-edit-log/) — logs user interactions to a file for replay and analysis.
- [**napari-shifted-labels**](./packages/napari-shifted-labels/) — visualizes masks across frames to provide a more consistent segmentation experience.
- [**napari-size-estimator**](./packages/napari-size-estimator/) — quickly estimates the volume of a label in a labels layer.
- [**napari-inverted-scrolling**](./packages/napari-inverted-scrolling/) — inverts the scrolling behaviour in napari to match other software commonly used in medical imaging (scrolling through frames with the mouse wheel instead of zooming).
- [**napari-shape-based-interpolation**](./packages/napari-shape-based-interpolation/) — shape based interpolation of labels between keyframes. (As an alternative to AI-based methods.)
- [**napari-quick-view**](./packages/napari-quick-view/) — quickly cycle through different images.
- [**napari-view-switch**](./packages/napari-view-switch/) — quickly cycle through axial, coronal, and sagittal views with named buttons.

---

## Table of contents

- [Installation](#installation)
- [Development & contributing](#development--contributing)
- [Roadmap](#roadmap)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---
## Installation

### Requirements

BEACON can be used on any device that supports napari (Windows/Macos). However, some plugins may have additional requirements (for example a CUDA-capable GPU for model inference) for optimal experience. The project is tested on macOS and Linux.

### Local installation

For a local installation, clone the repository and install plugin packages in editable mode. We recommend [uv](https://github.com/astral-sh/uv) for this purpose.

```bash
# clone the repository and navigate into it
git clone <repo-url> core_project && cd core_project

# sync dependencies and install the plugins in editable mode
uv sync
# run the startup script. This opens napari with a demo study.
uv run startup.py
# alternatively start napari
uv run napari
```
<details>
  <summary>Alternatively using `pip` and `venv`</summary>

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate 
  for d in ./packages/napari-*/; do pip install -e "$d"; done
  pip install -e ./apps/artist_study_app/
  python3 startup.py

  ```
</details>

### In napari

In theory, you can also install the plugins directly from napari's plugin manager. However, this was not yet tested and will only be made available once the plugins are published to the napari hub.

### Docker

As an alternative to the local installation, napari can be run inside a container. Note to make sure to mount any datasets and (when needed) model checkpoints into the container. The example below mounts the `/project_data/` folder from the host into the container. You also need to run the container with access to display devices (X11 or similar) to see the napari GUI.

```bash
# clone the repository
docker build -f ./Dockerfile -t napari_core_project .

# run the container with access to gpus, the files you want to access, and display devices
docker run --rm -it --gpus=all -v /project_data/:/project_data/ -v ./artist_study:/app/artist_study --device=/dev/dri:/dev/dri -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:ro napari_core_project

```

<details>
 <summary>Using the tool in the browser:</summary>
  
  Alternatively, for example if no display devices are available, [xpra](https://github.com/Xpra-org/xpra?tab=readme-ov-file#usage) can be used to stream the application to a browser.

  ```bash
  docker build -f ./Dockerfile.web -t napari_core_web .
  docker run --rm -it --gpus=all -v /project_data/:/project_data/ -p 9876:9876 napari_core_web
  ```
</details>

## Usage overview

To learn how to use napari and the various plugins provided in this repository, please make use of the demos provided in the demo widget (loaded to the bottom left when starting the tool with `startup.py`).


Additionally please refer to the [Documentation](./Documentation.md) for more detailed information on the project and its plugins. The individual plugins also contain documentation on their usage in their respective folders.

## Development & contributing

We welcome any contributions (code or feature requests) that align with the goals of the project, such as adding support for other models, implementing other utility features, or UI changes that align the napari interface more closely to existing treatment planning software.

### Development setup

1. Follow the [local installation](#local-installation) steps above.

2. Make any desired changes to the source code, for example adding a new model/plugin.

3. (optionally) add a demo for your new plugin in `demo_widget.py`.

4. Use the `startup.ipynb` notebook for (semi-)hot-reloading. With the notebook you can re-run cells to reload your plugin/demo without restarting napari. (best-effort basis might fail for complex changes/plugins)

5. Alternatively, you can also start napari manually with `uv run napari` and load the plugin you are working on from the plugin menu. (Tipp: create a `startup_test.py` to load an image and the plugin of interest on startup.)

## Roadmap

Planned short- and mid-term improvements:

- Packaging and release relevant standalone plugins to napari hub/pypi.

## License

This repository is licensed under MIT license.

The UI is partly based upon the [napari-toolkit](https://github.com/MIC-DKFZ/napari_toolkit) project. It is licensed under the terms of the [Apache Software License 2.0](https://github.com/MIC-DKFZ/napari_toolkit/blob/master/LICENSE) license.
The toolkit is typically imported as a library, but some files are copied and adapted for use in this repository. These files are marked with a header comment containing the original license information.

## Acknowledgments

This project is developed and maintained by the [LMU Adaptive Radiation Therapy Lab](https://lmu-art-lab.userweb.mwn.de/) (LMU ART Lab) at the  [Department of Radiation Oncology, LMU University Hospital](https://www.lmu-klinikum.de/strahlentherapie-und-radioonkologie/forschung/physikalische-forschung/5e34c41a1e300c37), Munich, Germany, in the context of the [BZKF Lighthouse on Local Therapies](https://bzkf.de/f/forschung/leuchttuerme/lokale-therapien/).

<img src="images/logos.png" alt="Logos of the BZKF, Lighthouse, and LMU Klinikum" width="500" />

For more information about napari and the UI toolkit used:

- **napari**: https://github.com/napari/napari
- **napari_toolkit**: https://github.com/MIC-DKFZ/napari_toolkit

For more information on the models used in the model-backed plugins:

- **nnInteractive**: https://github.com/MIC-DKFZ/nnInteractive
- **napari-nninteractive** plugin: https://github.com/MIC-DKFZ/napari-nninteractive
- **SAM2** (segment-anything model 2): https://github.com/facebookresearch/sam2
