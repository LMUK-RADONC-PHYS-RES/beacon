import numpy as np
import zlib
from base64 import b64encode, b64decode

def encode_labels_event_data(event, base64=False):
    # package the event data 
    # format:
    # int32 offset
    # uint32[2] shape of data array
    # zlib compressed bytes of data array
    # use np to convert to bytes

    time_bytes = np.array([event.time], dtype=np.float64).tobytes()
    offset_bytes = np.array([event.offset], dtype=np.uint32).tobytes()
    shape_bytes = np.array(event.data.shape, dtype=np.uint32).tobytes() # assuming 2D data
    dtype_byte = event.data.dtype.char.encode('ascii')
    data_bytes = zlib.compress(event.data.astype(np.uint8).tobytes())
    all_bytes = time_bytes + offset_bytes + shape_bytes + dtype_byte + data_bytes
    if not base64:
        return all_bytes
    else:
        return b64encode(all_bytes).decode('utf-8')

def decode_labels_event_data(encoded_bytes, base64=False):
    if base64:
        encoded_bytes = b64decode(encoded_bytes)
    
    time = np.frombuffer(encoded_bytes[0:8], dtype=np.float64)[0]
    offset = np.frombuffer(encoded_bytes[8:16], dtype=np.uint32)
    shape = np.frombuffer(encoded_bytes[16:24], dtype=np.uint32)
    dtype_byte = encoded_bytes[24:25] # single byte character
    dtype = np.dtype(dtype_byte.decode('ascii'))
    data_bytes = zlib.decompress(encoded_bytes[25:])
    data = np.frombuffer(data_bytes, dtype=np.uint8).reshape(shape)
    return offset, data
