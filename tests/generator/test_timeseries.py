"""Tests for the TESS-like time grid (spec 2.2)."""

import numpy as np
import pytest

from exoplanet_lab.generator.timeseries import (
    CADENCE_DAYS,
    DOWNLINK_GAP_END,
    DOWNLINK_GAP_START,
    EXTRA_GAP_COUNT_RANGE,
    EXTRA_GAP_LENGTH_RANGE_DAYS,
    N_POINTS,
    SECTOR_DAYS,
    full_time_grid,
    make_time_grid,
    observed_mask,
)

SEEDS = range(50)


def rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


# --- the full grid -----------------------------------------------------------------------


def test_cadence_is_two_minutes() -> None:
    steps_minutes = np.diff(full_time_grid()) * 24 * 60
    assert np.allclose(steps_minutes, 2.0)


def test_grid_covers_one_sector_from_zero() -> None:
    time = full_time_grid()
    assert time.size == N_POINTS == 19_728
    assert time[0] == 0.0
    assert time[-1] == pytest.approx(SECTOR_DAYS - CADENCE_DAYS)


def test_720_points_per_day() -> None:
    assert round(1.0 / CADENCE_DAYS) == 720


# --- the downlink gap --------------------------------------------------------------------


def test_downlink_gap_is_one_day_in_the_middle() -> None:
    assert DOWNLINK_GAP_END - DOWNLINK_GAP_START == pytest.approx(1.0)
    assert (DOWNLINK_GAP_START + DOWNLINK_GAP_END) / 2 == pytest.approx(SECTOR_DAYS / 2)


def test_no_observed_points_in_downlink_gap() -> None:
    grid = make_time_grid(rng(), extra_gaps=False)
    t = grid.observed_time
    assert not np.any((t >= DOWNLINK_GAP_START) & (t < DOWNLINK_GAP_END))
    assert grid.gaps == ((DOWNLINK_GAP_START, DOWNLINK_GAP_END),)


def test_downlink_gap_removes_one_day_of_points() -> None:
    grid = make_time_grid(rng(), extra_gaps=False)
    assert N_POINTS - grid.observed.sum() == 720


def test_without_extra_gaps_the_seed_is_not_used() -> None:
    generator = rng(123)
    state_before = generator.bit_generator.state
    first = make_time_grid(generator, extra_gaps=False)
    assert generator.bit_generator.state == state_before
    second = make_time_grid(rng(999), extra_gaps=False)
    assert np.array_equal(first.observed, second.observed)


# --- extra random gaps -------------------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_extra_gaps_have_allowed_count_and_length(seed: int) -> None:
    grid = make_time_grid(rng(seed), extra_gaps=True)
    extra = grid.gaps[1:]
    low_count, high_count = EXTRA_GAP_COUNT_RANGE
    assert low_count <= len(extra) <= high_count
    low_len, high_len = EXTRA_GAP_LENGTH_RANGE_DAYS
    for start, end in extra:
        assert low_len <= end - start <= high_len
        assert 0.0 <= start and end <= SECTOR_DAYS


@pytest.mark.parametrize("seed", SEEDS)
def test_extra_gaps_only_remove_points(seed: int) -> None:
    base = make_time_grid(rng(seed), extra_gaps=False)
    gappy = make_time_grid(rng(seed), extra_gaps=True)
    assert np.array_equal(base.time, gappy.time)  # the full grid never changes
    assert not np.any(gappy.observed & ~base.observed)  # no point is added
    assert gappy.observed.sum() < base.observed.sum()  # at least one point is removed


@pytest.mark.parametrize("seed", SEEDS)
def test_mask_matches_gap_list(seed: int) -> None:
    grid = make_time_grid(rng(seed), extra_gaps=True)
    in_any_gap = np.zeros_like(grid.observed)
    for start, end in grid.gaps:
        in_any_gap |= (grid.time >= start) & (grid.time < end)
    assert np.array_equal(grid.observed, ~in_any_gap)


def test_extra_gaps_are_reproducible() -> None:
    first = make_time_grid(rng(7), extra_gaps=True)
    second = make_time_grid(rng(7), extra_gaps=True)
    assert first.gaps == second.gaps
    assert np.array_equal(first.observed, second.observed)


def test_different_seeds_give_different_gaps() -> None:
    gap_sets = {make_time_grid(rng(seed), extra_gaps=True).gaps for seed in SEEDS}
    assert len(gap_sets) == len(SEEDS)


# --- the mask helper ---------------------------------------------------------------------


def test_gap_start_is_excluded_and_end_is_included() -> None:
    time = np.array([0.9, 1.0, 1.5, 2.0, 2.1])
    assert observed_mask(time, ((1.0, 2.0),)).tolist() == [True, False, False, True, True]


def test_no_gaps_means_everything_observed() -> None:
    time = full_time_grid()
    assert observed_mask(time, ()).all()
