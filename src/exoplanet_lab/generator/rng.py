"""Seeded random-number streams.

One scenario seed is split into several independent streams, one per job (drawing preset values,
placing gaps, shaping starspots, adding noise). Each part of the generator draws only from its
own stream, so adding or changing draws in one part never shifts the random values of another.
For example, turning extra gaps on or off leaves the noise exactly the same.
"""

from enum import IntEnum

import numpy as np


class Stream(IntEnum):
    """The generator's random streams. The numbers are part of the reproducibility contract:
    never renumber them, only add new ones at the end."""

    PRESET = 0
    """Preset draws: scenario type, Trap kind, physical values, target SNR."""
    GAPS = 1
    """Extra random data gaps."""
    ACTIVITY = 2
    """Starspot phases and envelope."""
    NOISE = 3
    """White noise on every grid point."""


def stream_rng(seed: int, stream: Stream) -> np.random.Generator:
    """A fresh random generator for one stream of one seed.

    Built from ``SeedSequence(seed, spawn_key=(stream,))``, which is NumPy's recommended way to
    get statistically independent child streams from a single seed. Calling it twice with the
    same arguments gives two generators that produce identical values.
    """
    if seed < 0:
        raise ValueError("seed must be non-negative")
    return np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(int(stream),)))
