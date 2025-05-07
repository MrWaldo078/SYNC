import os
import ctypes
import numpy as np

# Load the compiled library
_here = os.path.dirname(__file__)
_lib_path = os.path.join(_here, "sync.dll")    # or "libsync.so" on Unix
_lib = ctypes.CDLL(_lib_path)

# Tell ctypes the function signature
_lib.sync_rr_to_fit.argtypes = [
    np.ctypeslib.ndpointer(dtype=np.double, flags="C_CONTIGUOUS"),  # rr_times
    ctypes.c_size_t,                                                # rr_count
    np.ctypeslib.ndpointer(dtype=np.double, flags="C_CONTIGUOUS"),  # fit_times
    ctypes.c_size_t,                                                # fit_count
    np.ctypeslib.ndpointer(dtype=ctypes.c_size_t, flags="C_CONTIGUOUS")  # out_idx
]
_lib.sync_rr_to_fit.restype = None

def sync_rr_to_fit_cpp(fit_records, rri_series):
    """
    fit_records: list of dicts, each record['timestamp'] is a datetime
    rri_series:  list of dicts, each record['timestamp'] is datetime, record['value'] is RR ms
    Returns merged list of dicts (FIT fields + 'rr_interval_ms' + 'rr_timestamp').
    """
    # Build numpy arrays of POSIX times
    rr_times  = np.array([r['timestamp'].timestamp() for r in rri_series], dtype=np.double)
    fit_times = np.array([r['timestamp'].timestamp() for r in fit_records], dtype=np.double)

    # Prepare output index array
    out_idx = np.empty(rr_times.size, dtype=np.uintp)

    # Call the C++ sync
    _lib.sync_rr_to_fit(rr_times, rr_times.size,
                        fit_times, fit_times.size,
                        out_idx)

    # Merge results back into Python dicts
    synced = []
    for i, j in enumerate(out_idx):
        rec = fit_records[int(j)].copy()
        rec['rr_interval_ms'] = rri_series[i]['value']
        rec['rr_timestamp']   = rri_series[i]['timestamp']
        synced.append(rec)

    return synced
