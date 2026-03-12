import zlib
from base64 import b64encode, b64decode

from napari_edit_log.utils import encode_labels_event_data, decode_labels_event_data

def reconstruct_edit_series(encoded_series, base64=False):
    """Extracts a series of encoded edit events into offsets and data arrays.

    Parameters
    ----------
    encoded_series : list of bytes or str
        A list where each element is the encoded bytes (or base64 string) of an edit event.
    base64 : bool, optional
        Whether the encoded events are in base64 format, by default False.

    Returns
    -------
    list of tuples
        A list where each element is a tuple (offset, data) extracted from the encoded events.
    """
    extracted_series = []
    for encoded_event in encoded_series:
        offset, data = decode_labels_event_data(encoded_event, base64=base64)
        extracted_series.append((offset, data))
    return extracted_series

