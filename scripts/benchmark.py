"""Compare mavparser and pymavlink on every bundled DataFlash BIN log."""

from __future__ import annotations

from array import array
import json
import math
from pathlib import Path
import time

import mavparser
from pymavlink import mavutil


def values_match(left: object, right: object) -> bool:
    """Compare pymavlink arrays, floating-point values, and ordinary scalars."""
    if isinstance(left, array):
        left = list(left)
    if isinstance(right, array):
        right = list(right)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(values_match(a, b) for a, b in zip(left, right))
    if isinstance(left, float) and isinstance(right, float):
        return (math.isnan(left) and math.isnan(right)) or math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-7)
    return left == right


def compare_log(path: Path) -> dict[str, object]:
    """Stream both parsers in lockstep and return speed plus compatibility data."""
    start = time.perf_counter()
    mavparser_count = sum(1 for _ in mavparser.iter_messages(str(path)))
    mavparser_seconds = time.perf_counter() - start

    start = time.perf_counter()
    pymavlink_count = 0
    speed_connection = mavutil.mavlink_connection(str(path))
    while speed_connection.recv_match() is not None:
        pymavlink_count += 1
    pymavlink_seconds = time.perf_counter() - start

    ours = mavparser.iter_messages(str(path))
    connection = mavutil.mavlink_connection(str(path))
    mismatch = None
    compared_messages = 0
    for index, our_message in enumerate(ours):
        message = connection.recv_match()
        if message is None:
            mismatch = f"message {index}: pymavlink ended early"
            break
        pymavlink_message = message.to_dict()
        compared_messages += 1
        if our_message.keys() != pymavlink_message.keys():
            mismatch = f"message {index}: keys differ"
            break
        for key in our_message:
            if not values_match(our_message[key], pymavlink_message[key]):
                mismatch = f"message {index}, field {key}: values differ"
                break
        if mismatch:
            break

    if mismatch is None and connection.recv_match() is not None:
        mismatch = "mavparser ended early"
    compatible = mismatch is None and mavparser_count == pymavlink_count
    return {
        "file": path.name,
        "bytes": path.stat().st_size,
        "mavparser_messages": mavparser_count,
        "pymavlink_messages": pymavlink_count,
        "mavparser_seconds": round(mavparser_seconds, 6),
        "pymavlink_seconds": round(pymavlink_seconds, 6),
        "speedup": round(pymavlink_seconds / mavparser_seconds, 2) if mavparser_seconds else None,
        "compatible": compatible,
        "mismatch": mismatch,
    }


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    results = [compare_log(path) for path in sorted((root / "data").glob("*.BIN"))]
    print(json.dumps(results, indent=2), flush=True)
