"""Structure detection look-ahead tests (Phase 3)."""

from __future__ import annotations

from app.ta.structure import SwingType, detect_swings, structure_snapshot


def _series_with_clear_swing() -> tuple[list[float], list[float]]:
    # index 5 is a clear swing high once right=2 confirms at index 7
    highs = [1, 2, 3, 4, 5, 10, 4, 3, 2, 2, 2, 2]
    lows = [0.5, 1, 2, 3, 4, 3, 2, 1, 0.5, 0.4, 0.3, 0.2]
    return highs, lows


def test_swing_not_visible_before_confirmation() -> None:
    highs, lows = _series_with_clear_swing()
    before = detect_swings(highs, lows, left=2, right=2, as_of_index=6)
    # pivot at 5 confirms at 7 — must not appear at as_of=6
    assert all(not (s.type == SwingType.HIGH and s.pivot_index == 5) for s in before)

    after = detect_swings(highs, lows, left=2, right=2, as_of_index=7)
    highs_found = [s for s in after if s.type == SwingType.HIGH and s.pivot_index == 5]
    assert len(highs_found) == 1
    assert highs_found[0].confirm_index == 7
    assert highs_found[0].price == 10


def test_structure_labels_hh_lh() -> None:
    highs = [1, 2, 3, 8, 3, 2, 1, 2, 9, 2, 1, 0, 1, 7, 1, 0]
    lows = [0, 1, 2, 2, 1, 0.5, 0, 1, 1, 0.5, 0, -1, 0, 0, -0.5, -1]
    swings = detect_swings(highs, lows, left=2, right=2)
    high_swings = [s for s in swings if s.type == SwingType.HIGH]
    assert len(high_swings) >= 2
    # Second labeled relative to first
    assert high_swings[1].label is not None


def test_snapshot_respects_as_of() -> None:
    highs, lows = _series_with_clear_swing()
    early = structure_snapshot(highs, lows, as_of_index=6)
    late = structure_snapshot(highs, lows, as_of_index=11)
    assert len(late.swings) >= len(early.swings)


def test_extending_future_bars_does_not_change_past_confirmed_swings() -> None:
    highs, lows = _series_with_clear_swing()
    base = detect_swings(highs, lows, as_of_index=9)
    extended_h = highs + [1, 1, 1]
    extended_l = lows + [0.1, 0.1, 0.1]
    later = detect_swings(extended_h, extended_l, as_of_index=9)
    assert [(s.type, s.pivot_index, s.price) for s in base] == [
        (s.type, s.pivot_index, s.price) for s in later
    ]
