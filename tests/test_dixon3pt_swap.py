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


def test_split_mask_separates_touching_thighs():
    """Two thighs joined by a bridge on one slice (groin): one object, so swap is refused;
    after _split_mask (option -m dixon3pt:split_mask=1) they are two objects and swap-right works."""
    mask = np.zeros((30, 4, 3), dtype=bool)
    mask[3:13] = True               # right thigh
    mask[18:28] = True              # left thigh
    mask[12:19, :, 0] = True        # bridge on one slice
    water, fat = np.where(mask, 1.0, 0.0), np.zeros(mask.shape)
    method = Dixon3ptMethod()
    with pytest.raises(SwapLegsError):
        method._swap_leg(water, fat, mask, "right")

    split = method._split_mask(mask)
    new_water, new_fat = method._swap_leg(water, fat, split, "right")

    assert np.all(new_fat[3:10] == 1) and np.all(new_water[3:10] == 0)      # right thigh swapped
    assert np.all(new_water[18:28] == 1) and np.all(new_fat[18:28] == 0)    # left thigh kept
    assert mask.sum() > split.sum() and mask[3:10].all()                    # input mask untouched


@pytest.mark.parametrize("action", ["swap-right", "swap-left"])
def test_swap_actions_are_accepted(action):
    Dixon3ptMethod()._check_action(action)
