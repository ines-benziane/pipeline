"""Water/fat swap of one leg only (dixon3pt actions swap-right / swap-left).
Synthetic volumes: the patient's right leg is on the left of the image (small index i), as in DICOM."""

import numpy as np
import pytest

from methods.dixon3pt import Dixon3ptMethod
from runner.errors import SwapLegsError

RIGHT, LEFT = slice(1, 3), slice(7, 9)   # image columns i of each leg


def _legs(*columns):
    """Mask with one separate part per given column range; water everywhere in the mask, no fat."""
    mask = np.zeros((10, 4, 3), dtype=bool)
    for cols in columns:
        mask[cols] = True
    return np.where(mask, 1.0, 0.0), np.zeros(mask.shape), mask


@pytest.mark.parametrize("side, swapped, kept", [("right", RIGHT, LEFT), ("left", LEFT, RIGHT)])
def test_only_the_requested_leg_is_swapped(side, swapped, kept):
    water, fat, mask = _legs(RIGHT, LEFT)

    new_water, new_fat = Dixon3ptMethod()._swap_leg(water, fat, mask, side)

    assert np.all(new_water[swapped] == 0) and np.all(new_fat[swapped] == 1)
    assert np.all(new_water[kept] == 1) and np.all(new_fat[kept] == 0)


def test_input_maps_are_not_modified():
    water, fat, mask = _legs(RIGHT, LEFT)

    Dixon3ptMethod()._swap_leg(water, fat, mask, "right")

    assert np.all(water[RIGHT] == 1) and np.all(fat[RIGHT] == 0)


def test_legs_are_found_by_size_not_by_crumbs():
    """A crumb of the mask (isolated pixel) is never taken for a leg."""
    water, fat, mask = _legs(RIGHT, LEFT)
    mask[5, 0, 0] = True

    new_water, _ = Dixon3ptMethod()._swap_leg(water, fat, mask, "right")

    assert np.all(new_water[RIGHT] == 0) and new_water[5, 0, 0] == water[5, 0, 0]


@pytest.mark.parametrize("columns", [(RIGHT,), (slice(1, 9),)], ids=["single leg", "legs touching"])
def test_without_two_separate_legs_the_swap_is_refused(columns):
    water, fat, mask = _legs(*columns)

    with pytest.raises(SwapLegsError) as exc:
        Dixon3ptMethod()._swap_leg(water, fat, mask, "right")
    assert exc.value.hint


@pytest.mark.parametrize("action", ["swap-right", "swap-left"])
def test_swap_actions_are_accepted(action):
    Dixon3ptMethod()._check_action(action)
