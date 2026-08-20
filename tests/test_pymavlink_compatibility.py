"""Compatibility checks against pymavlink's DataFlash reader."""

from array import array
import math
from pathlib import Path

import mavparser
from pymavlink import mavutil


def read_with_pymavlink(path: Path) -> list[dict]:
    """Read every log message through pymavlink's public dictionary API."""
    connection = mavutil.mavlink_connection(str(path))
    messages = []
    while (message := connection.recv_match()) is not None:
        messages.append(message.to_dict())
    return messages


def values_match(left: object, right: object) -> bool:
    """Compare scalar and sequence values while handling float precision and NaN."""
    if isinstance(left, array):
        left = list(left)
    if isinstance(right, array):
        right = list(right)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(values_match(a, b) for a, b in zip(left, right))
    if isinstance(left, float) and isinstance(right, float):
        return (math.isnan(left) and math.isnan(right)) or math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-7)
    return left == right


def test_small_log_matches_pymavlink_message_for_message() -> None:
    """Keep a complete real-log comparison in CI without making tests slow."""
    log_path = Path(__file__).resolve().parents[1] / "data" / "00000081.BIN"
    ours = mavparser.parse(str(log_path))
    pymavlink_messages = read_with_pymavlink(log_path)

    assert len(ours) == len(pymavlink_messages)
    for index, (our_message, pymavlink_message) in enumerate(zip(ours, pymavlink_messages)):
        assert our_message.keys() == pymavlink_message.keys(), index
        for key in our_message:
            assert values_match(our_message[key], pymavlink_message[key]), (index, key)
