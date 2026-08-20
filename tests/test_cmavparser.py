"""Functional tests for both public result-delivery modes."""

from pathlib import Path
import math

import mavparser


DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "data"


def test_list_and_iterator_modes_return_identical_messages() -> None:
    log_path = next(DATA_DIRECTORY.glob("*.BIN"))

    all_messages = mavparser.parse(str(log_path), mode="all")
    streamed_messages = list(mavparser.parse(str(log_path), mode="iterator"))

    assert all_messages
    assert len(all_messages) == len(streamed_messages)
    for batch_message, streamed_message in zip(all_messages, streamed_messages):
        assert batch_message.keys() == streamed_message.keys()
        for key, batch_value in batch_message.items():
            streamed_value = streamed_message[key]
            if isinstance(batch_value, float) and math.isnan(batch_value):
                assert isinstance(streamed_value, float) and math.isnan(streamed_value)
            else:
                assert batch_value == streamed_value
    assert all(isinstance(message, dict) for message in all_messages)
    assert "mavpackettype" in all_messages[0]


def test_invalid_mode_has_a_clear_error() -> None:
    log_path = next(DATA_DIRECTORY.glob("*.BIN"))

    try:
        mavparser.parse(str(log_path), mode="unknown")
    except ValueError as error:
        assert "mode" in str(error)
    else:  # pragma: no cover - protects the public API contract
        raise AssertionError("parse accepted an invalid mode")
