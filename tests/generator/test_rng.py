"""Tests for the seeded random streams."""

import numpy as np
import pytest

from exoplanet_lab.generator.rng import Stream, stream_rng


def test_same_seed_and_stream_repeat_exactly() -> None:
    first = stream_rng(7, Stream.NOISE).random(100)
    second = stream_rng(7, Stream.NOISE).random(100)
    np.testing.assert_array_equal(first, second)


def test_streams_of_one_seed_differ() -> None:
    draws = [stream_rng(7, stream).random(10) for stream in Stream]
    for i in range(len(draws)):
        for j in range(i + 1, len(draws)):
            assert not np.array_equal(draws[i], draws[j])


def test_different_seeds_differ() -> None:
    assert not np.array_equal(
        stream_rng(1, Stream.NOISE).random(10), stream_rng(2, Stream.NOISE).random(10)
    )


def test_stream_numbers_are_fixed() -> None:
    # Renumbering a stream would silently change every saved scenario.
    assert [(s.name, s.value) for s in Stream] == [
        ("PRESET", 0),
        ("GAPS", 1),
        ("ACTIVITY", 2),
        ("NOISE", 3),
    ]


def test_negative_seed_is_rejected() -> None:
    with pytest.raises(ValueError):
        stream_rng(-1, Stream.NOISE)
