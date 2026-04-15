# Edit Log Format

## Table of contents

- [Overview](#overview)
- [Recording behaviour](#recording-behaviour)
- [Events](#events)
	- [dims](#dims)
	- [labels_tool](#labels_tool)
	- [layer](#layer)
	- [edit](#edit)
		- [labels_update](#labels_update)
		- [data](#data)
		- [generic fallback](#generic-fallback)
	- [study](#study)
	- [metrics](#metrics)
- [Notes & behaviour summary](#notes--behaviour-summary)
- [Event Summary Reference](#event-summary-reference)

## Overview

This document describes the structure of events appended to the in-memory edit log by `napari_edit_log.edit_log.NapariEditLog`. Each logged entry is a Python `dict` with at least `event_group` and `event_type` plus additional fields depending on the event.

## Recording behaviour

- Events are appended only when `is_recording` is `True`, unless `force=True` is passed to `record()`.
- `record()` appends the event dict to the log and emits the `recorded` event.
- Certain handlers merge repeated events by updating the last entry instead of appending (see per-event details below).
- Merging updates emit an `updated` notification instead of `recorded`.

## Events

Each top-level event is grouped under `event_group`. The common groups are documented below; each section contains a short description, the typical fields, and example JSON payloads.

| Event Group | Event Type | Typical Context | Merges? | Key Fields |
|-------------|-----------|-----------------|---------|-----------|
| `dims` | `point` | Slice navigation | Yes (on repeat) | `order`, `current_step`, `timestamp`, `count`, `timestamp_final` |
| `dims` | `order` | Axis reordering | Yes (on repeat) | `order`, `current_step`, `timestamp`, `count`, `timestamp_final` |
| `labels_tool` | `selected_label` | Label value changed | Yes (on repeat) | `layer_name`, `selected_label`, `mode`, `timestamp` |
| `labels_tool` | `mode` | Painting mode changed | No | `layer_name`, `selected_label`, `mode`, `timestamp` |
| `layer` | `inserted` | Layer added to viewer | No | `layer_name`, `timestamp` |
| `layer` | `removed` | Layer removed from viewer | No | `layer_name`, `timestamp` |
| `edit` | `labels_update` | Pixel/label edits | Partially* | `layer_name`, `timestamp`, `timestamp_final`, `clicks`, `data_edits`, `data_initial` |
| `edit` | `data` | Layer data action (add/remove/change) | No | `action`, `value`, `timestamp` |
| `edit` | *(other)* | Other layer events | No | `timestamp`, (varies) |
| `study` | `load_task` | Study task loaded, recording starts | No | `timestamp` |
| `study` | `approve` | Study task approved, recording stops | No |`timestamp` |
|`metrics` | `metrics_updated` | Segmentation metrics computed | No | `timestamp`, `data` (with `dsc` and `hd95`) |

**Characteristics:**
- Rapid repeated events are merged by updating the last entry
- Merged entries include `count` and `timestamp_final`
- Two event types: dimension point changes or order changes

**Examples:**

First dims point event (user navigates to slice 5 in axis 1):
```json
{
	"event_group": "dims",
	"event_type": "point",  // 'point' for slice navigation or 'order' for axis reorder
	"order": "[0,1,2]",  // Viewer dims order as list string
	"current_step": "[0,5,10]",  // Viewer current step as list string
	"timestamp": 1681536000.123456  // Unix timestamp (seconds)
}
```

Merged dims changes (user scrolling through slices):
```json
{
	"event_group": "dims",
	"event_type": "point",
	"order": "[0,1,2]",
	"current_step": "[0,15,10]",  // Updated after multiple navigations
	"timestamp": 1681536000.123456,  // First occurrence
	"timestamp_final": 1681536001.654321,  // [optional, merged only] Last update time
	"count": 5  // [optional, merged only] Number of merged updates
}
```

Dims order change (reordering axes):
```json
{
	"event_group": "dims",
	"event_type": "order",  // Axis reordering event
	"order": "[2,0,1]",  // New dims order
	"current_step": "[0,5,10]",
	"timestamp": 1681536002.0
}
```

### labels_tool

Changes to the labels layer tool state (selected label, painting mode, etc.).

**Characteristics:**
- Rapid repeated `selected_label` events are merged into the previous entry, such that only the last selected tool is stored.
- Changing the active layer ends any ongoing edit series
- Recorded only for `Labels` layers in the viewer

**Examples:**

Selected label changed:
```json
{
	"event_group": "labels_tool",
	"event_type": "selected_label",  // 'selected_label', 'mode', or other tool event
	"layer_name": "segmentation",  // Active labels layer name
	"selected_label": 3,  // Currently selected label value
	"mode": "paint",  // Current painting mode (e.g., 'paint', 'pick', 'erase')
	"data": "Event of type \"selected_label\"",  // String representation of napari event
	"timestamp": 1681536001.234567  // Unix timestamp (seconds)
}
```

Labels tool mode changed:
```json
{
	"event_group": "labels_tool",
	"event_type": "mode",  // Mode change event
	"layer_name": "segmentation",
	"selected_label": 3,
	"mode": "erase",  // New painting mode
	"data": "Event of type \"mode\"",
	"timestamp": 1681536002.345678
}
```

### layer

High-level layer list events (layer added/removed from viewer).

**Characteristics:**
- Minimal fields recorded
- Fired when layers are added to or removed from the viewer
- Layer name is captured for auditing purposes

**Examples:**

Layer inserted:
```json
{
	"event_group": "layer",
	"event_type": "inserted",  // 'inserted' when layer added or 'removed' when removed
	"layer_name": "segmentation",  // Name of layer that was inserted or removed
	"timestamp": 1681536003.456789  // Unix timestamp (seconds)
}
```

Layer removed:
```json
{
	"event_group": "layer",
	"event_type": "removed",
	"layer_name": "segmentation",
	"timestamp": 1681536004.567890
}
```

### edit

Edits and data changes to layers. This group contains several sub-types described below.

#### labels_update

Logged when a `Labels` layer receives pixel/label edits. The implementation groups consecutive `labels_update` calls into a single edit series: the first labels update creates a new log entry, and subsequent updates within the same series update that entry (setting `timestamp_final`, incrementing `clicks`, and optionally appending to `data_edits`).

**Characteristics:**
- First edit in a series creates a new entry
- Consecutive edits within a series update the same entry
- Series ends when a different tool (label change, mode change) is used
- Optional detailed edit tracking via `data_edits` when `record_individual_edits=True`

**Examples:**

Single edit with minimal fields:
```json
{
	"event_group": "edit",
	"event_type": "labels_update",  // Always 'labels_update' for pixel/label edits
	"timestamp": 1681536002.0,  // Unix timestamp of first edit in series
	"timestamp_final": 1681536002.0,  // Unix timestamp of last edit in series
	"layer_name": "segmentation",  // Name of edited labels layer
	"layer_shape": "(512, 512, 100)",  // Stringified shape of layer data
	"viewer_dims_order": "[0,1,2]",  // Viewer dims order at time of edit
	"viewer_dims_current_step": "[2,100,256]",  // Viewer current step at time of edit
	"clicks": 1  // Number of individual edits (clicks) in this series
}
```

Multi-click edit series (user painted 4 strokes):
```json
{
	"event_group": "edit",
	"event_type": "labels_update",
	"timestamp": 1681536002.100,
	"timestamp_final": 1681536003.500,  // Updated as edits continue
	"layer_name": "segmentation",
	"layer_shape": "(512, 512, 100)",
	"viewer_dims_order": "[0,1,2]",
	"viewer_dims_current_step": "[2,100,256]",
	"clicks": 4  // Incremented with each new edit
}
```

Edit with detailed edit tracking (when `record_individual_edits=True`):
```json
{
	"event_group": "edit",
	"event_type": "labels_update",
	"timestamp": 1681536002.100,
	"timestamp_final": 1681536003.200,
	"layer_name": "segmentation",
	"layer_shape": "(512, 512, 100)",
	"viewer_dims_order": "[0,1,2]",
	"viewer_dims_current_step": "[2,100,256]",
	"clicks": 2,
	"data_edits": [  // [optional] Array of base64-encoded per-edit events
		"?gAB3q0DfA8AAAA...",
		"?gAB3q0DfA8AAAB..."
	],
	"data_initial": "?HQ8AAAA7zip..."  // [optional] Dtype char + base64(zlib-compressed) before-edit mask
}
```

**Decoding `data_initial` and `data_edits`:**

To reconstruct the before-edit state and individual edits:

```python
import base64
import zlib
import numpy as np

# Decode data_initial (before-edit mask)
dtype_char = data_initial[0]  # First character is dtype (e.g., '?')
dtype = np.dtype(dtype_char)
compressed = base64.b64decode(data_initial[1:])
decompressed = zlib.decompress(compressed)
before_mask = np.frombuffer(decompressed, dtype=dtype)
# Reshape to match the view dimensions

# Decode individual data_edits (from encode_labels_event_data)
for encoded_edit in data_edits:
	decoded = decode_labels_event_data(encoded_edit, base64=True)
	# decoded contains: offset, data, new_label
```

---

#### data (layer data changes)

Recorded when a layer's data attribute changes with an explicit action (e.g., color changes, metadata updates). This event is used by all non `Label` layers, such as `Points`, `Shapes`, etc. It captures the type of change via the `action` field and a string representation of the new value.

**Characteristics:**
- Only recorded when event has an `action` in `{'added', 'removed', 'changed'}`
- Generic fallback captures non `Labels` layer data changes

**Examples:**

Data added:
```json
{
	"event_group": "edit",
	"event_type": "data",  // Always 'data' for layer data changes
	"action": "added",  // Action type: 'added', 'removed', or 'changed'
	"value": "<event.value>",  // String representation of event.value
	"timestamp": 1681536004.0  // Unix timestamp (seconds)
}
```

Data changed:
```json
{
	"event_group": "edit",
	"event_type": "data",
	"action": "changed",
	"value": "<event.value>",
	"timestamp": 1681536005.0
}
```

Data removed:
```json
{
	"event_group": "edit",
	"event_type": "data",
	"action": "removed",
	"value": "<event.value>",
	"timestamp": 1681536006.0
}
```

---

#### generic fallback

Other data events without a specific action are recorded with their napari `event_type` and a `timestamp`.

**Examples:**

Layer refresh event:
```json
{
	"event_group": "edit",
	"event_type": "refresh",  // Napari layer event type (e.g., 'refresh', 'extent')
	"timestamp": 1681536007.0  // Unix timestamp (seconds)
}
```

Layer extent changed:
```json
{
	"event_group": "edit",
	"event_type": "extent",
	"timestamp": 1681536008.0
}
```

---

### study

Study-specific events from the artist study application (task management and workflow).

**Characteristics:**
- Records key workflow transitions: loading a task and approving a task
- `load_task` starts the edit log recording session
- `approve` stops the edit log recording session and triggers save operations
- Emitted by the artist study widget

**Examples:**

Task loaded (recording starts):
```json
{
	"event_group": "study",
	"event_type": "load_task",  // Task loaded event: starts edit log recording
	"timestamp": 1681536010.0  // Unix timestamp (seconds)
}
```

Task approved (recording stops):
```json
{
	"event_group": "study",
	"event_type": "approve",  // Task approved event: stops recording and triggers save
	"timestamp": 1681536120.0
}
```

---

### metrics

Segmentation quality metrics events from the artist study application. These metrics are only computed and logged, when a full segmentation mask was provided as guidance.

**Characteristics:**
- Recorded when segmentation metrics are computed (e.g., after each edit)
- Only recorded if the previous event was not `metrics_updated` (avoids duplicate entries)
- Contains Dice Similarity Coefficient (DSC) and Hausdorff Distance at 95th percentile (HD95)
- Emitted by the segmentation metrics preview widget

**Examples:**

Metrics updated with valid values:
```json
{
	"event_group": "metrics",
	"event_type": "metrics_updated",  // Always 'metrics_updated'
	"timestamp": 1681536015.0,  // Unix timestamp when metrics were computed
	"data": {  // Object containing computed segmentation quality metrics
		"dsc": 0.8745,  // Dice Similarity Coefficient (0.0-1.0)
		"hd95": 5.23  // Hausdorff Distance at 95th percentile (mm)
	}
}
```

Metrics updated with undefined distance (single region):
```json
{
	"event_group": "metrics",
	"event_type": "metrics_updated",
	"timestamp": 1681536020.0,
	"data": {
		"dsc": 0.9123,
		"hd95": null  // Undefined when only single segmentation region exists
	}
}
```

## Notes & behaviour summary

- **Every entry includes** `event_group` and `event_type` as identifiers.
- **Timestamps**: First occurrence writes `timestamp`; merged entries also set `timestamp_final` when updated.
- **Event merging**: Rapid repeated events are often merged instead of appended (e.g., `dims`, `labels_tool`, and multiple edits in one edit series). Merged entries may include `count`, `timestamp_final`, or accumulated fields like `clicks`.
- **Edit series**: `labels_update` events are grouped per user interaction session. Consecutive edits update the same entry. A new tool selection or layer change ends the series.
- **Optional detailed tracking**: When `record_individual_edits=True`, individual edit payloads are collected in `data_edits` and the before-state is stored in `data_initial`.



> Tipp: If you need to programmatically process these events, the [napari-edit-log](packages/napari-edit-log) package provides utilities for encoding/decoding edit data (see `encode_labels_event_data` and `decode_labels_event_data`).
