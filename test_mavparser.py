import ctypes
import math
import time
from pathlib import Path

# Define ctypes Structs matching MAVLink Payloads
class GlobalPositionInt(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("time_boot_ms", ctypes.c_uint32),
        ("lat", ctypes.c_int32),
        ("lon", ctypes.c_int32),
        ("alt", ctypes.c_int32),
        ("relative_alt", ctypes.c_int32),
        ("vx", ctypes.c_int16),
        ("vy", ctypes.c_int16),
        ("vz", ctypes.c_int16),
        ("hdg", ctypes.c_uint16),
    ]

    def to_dict(self, timestamp):
        return {
            "mavpackettype": "GLOBAL_POSITION_INT",
            "timestamp": timestamp,
            "time_boot_ms": self.time_boot_ms,
            "lat": self.lat / 1e7,
            "lon": self.lon / 1e7,
            "alt": self.alt / 1000.0,
            "relative_alt": self.relative_alt / 1000.0,
            "vx": self.vx / 100.0,
            "vy": self.vy / 100.0,
            "vz": self.vz / 100.0,
            "hdg": self.hdg / 100.0,
        }

class Attitude(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("time_boot_ms", ctypes.c_uint32),
        ("roll", ctypes.c_float),
        ("pitch", ctypes.c_float),
        ("yaw", ctypes.c_float),
        ("rollspeed", ctypes.c_float),
        ("pitchspeed", ctypes.c_float),
        ("yawspeed", ctypes.c_float),
    ]

    def to_dict(self, timestamp):
        rad2deg = 180.0 / math.pi
        return {
            "mavpackettype": "ATTITUDE",
            "timestamp": timestamp,
            "time_boot_ms": self.time_boot_ms,
            "roll": self.roll * rad2deg,
            "pitch": self.pitch * rad2deg,
            "yaw": self.yaw * rad2deg,
            "rollspeed": self.rollspeed,
            "pitchspeed": self.pitchspeed,
            "yawspeed": self.yawspeed,
        }

# Map MSG_ID to Python classes
MSG_PARSERS = {
    33: GlobalPositionInt,
    30: Attitude,
}

parsed_dicts = []

def py_msg_callback(timestamp, msg_id, payload_ptr, payload_len):
    parser_cls = MSG_PARSERS.get(msg_id)
    if parser_cls and payload_ptr:
        struct_inst = parser_cls.from_address(payload_ptr)
        msg_dict = struct_inst.to_dict(timestamp)
        parsed_dicts.append(msg_dict)

CALLBACK_FUNC = ctypes.CFUNCTYPE(
    None,
    ctypes.c_uint64, # timestamp
    ctypes.c_uint32, # msg_id
    ctypes.c_void_p, # payload memory address
    ctypes.c_uint8   # payload_len
)

BASE_DIR = Path(__file__).resolve().parent
LIB_PATH = BASE_DIR / "mavparser" / "libtlogparser.dylib"
TLOG_PATH = BASE_DIR / "data" / "ArduPlane-TerrainMission-autotest-1787233492431164.tlog"

if not LIB_PATH.exists():
    raise FileNotFoundError(f"Library not found at path: {LIB_PATH}")
if not TLOG_PATH.exists():
    raise FileNotFoundError(f"tlog file not found at path: {TLOG_PATH}")

tlog_lib = ctypes.CDLL(str(LIB_PATH))
tlog_lib.parse_tlog_fast.argtypes = [ctypes.c_char_p, CALLBACK_FUNC, ctypes.c_size_t]
tlog_lib.parse_tlog_fast.restype = ctypes.c_size_t

c_callback = CALLBACK_FUNC(py_msg_callback)

# Max callback quota set to 20M to ensure complete file scanning
MAX_CALLBACKS = 20_000_000

start_time = time.perf_counter()
total_messages = tlog_lib.parse_tlog_fast(str(TLOG_PATH).encode("utf-8"), c_callback, MAX_CALLBACKS)
elapsed = time.perf_counter() - start_time

print(f"\n=========================================")
print(f"Parsed {total_messages:,} total raw messages in {elapsed:.4f} seconds.")
print(f"Captured {len(parsed_dicts):,} matching dicts (GLOBAL_POSITION_INT / ATTITUDE).")
print(f"=========================================\n")

print("--- First 3 dict objects created in Python ---\n")
for d in parsed_dicts[:3]:
    print(d)
    print(f"Type: {type(d)} | lat: {d.get('lat')}\n")