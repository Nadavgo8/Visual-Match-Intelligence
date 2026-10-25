"""'What did I miss?' window and selection rules, on small hand-made feeds."""

import pytest

from vmi.api import catchup


def item(cue, delivered, tier=1, t=None, text="x"):
    return {"kind": "feed", "cue_id": cue, "delivered": delivered, "t": delivered if t is None else t, "tier": tier,
            "text": {"basic": f"{text}.", "deep": f"{text} (deep)."}}


MARKS = [(0.0, "0:00"), (60.0, "1:00"), (300.0, "5:00"), (600.0, "10:00"), (900.0, "15:00")]
PROFILE = {"depth": "basic", "amount": "balanced"}


def test_first_use_covers_the_last_five_minutes_or_from_kick_off():
    assert catchup.window(None, 900.0) == (600.0, 900.0)
    assert catchup.window(None, 120.0) == (0.0, 120.0)


@pytest.mark.parametrize("since,expected", [(-5, (0.0, 900.0)), (950, (900.0, 900.0)), (300, (300.0, 900.0))])
def test_checkpoint_is_clamped_to_the_match_so_far(since, expected):
    assert catchup.window(since, 900.0) == expected


@pytest.mark.parametrize("bad", ["600", float("nan"), float("inf"), True])
def test_invalid_checkpoints_are_rejected(bad):
    with pytest.raises(ValueError):
        catchup.window(bad, 900.0)


def test_window_excludes_the_checkpoint_itself_and_includes_the_press_moment():
    feed = [item("seen", 300.0), item("a", 300.01), item("b", 900.0), item("after", 900.01)]
    assert [o["cue_id"] for o in catchup.select(feed, 300.0, 900.0, "balanced")] == ["a", "b"]


def test_items_count_by_delivery_not_by_when_they_happened():
    late = item("late", delivered=310.0, t=290.0)  # happened before the checkpoint, arrived after it
    early = item("seen", delivered=299.0, t=299.0)
    assert [o["cue_id"] for o in catchup.select([late, early], 300.0, 900.0, "balanced")] == ["late"]


def test_keeps_the_six_most_important_in_time_order_and_respects_the_feed_setting():
    feed = [item(f"t3-{i}", 400.0 + i, tier=3) for i in range(5)] + \
           [item(f"t1-{i}", 500.0 + i, tier=1) for i in range(4)] + [item("t2", 450.0, tier=2)]
    chosen = catchup.select(feed, 300.0, 900.0, "everything")
    assert [o["cue_id"] for o in chosen] == ["t3-3", "t3-4", "t2", "t1-0", "t1-1", "t1-2", "t1-3"][-6:]
    assert all(o["tier"] < 3 for o in catchup.select(feed, 300.0, 900.0, "balanced"))
    assert all(o["tier"] == 1 for o in catchup.select(feed, 300.0, 900.0, "big"))


def test_summary_states_the_range_and_says_when_nothing_happened():
    quiet = catchup.summary([], MARKS, 300.0, 900.0, PROFILE, "Score: A 1–0 B.")
    assert quiet["text"] == "Nothing important happened from 5:00 to 15:00. Score: A 1–0 B."
    assert (quiet["from_clock"], quiet["to_clock"], quiet["items"], quiet["first_use"]) == ("5:00", "15:00", [], False)
    busy = catchup.summary([item("g", 700.0, text="Goal for A")], MARKS, None, 900.0,
                           {"depth": "deep", "amount": "big"}, "Score: A 1–0 B.")
    assert busy["text"] == "From 10:00 to 15:00: Goal for A (deep). Score: A 1–0 B."
    assert busy["items"] == ["g"] and busy["first_use"] is True and busy["answer_kind"] == "template"


def test_clock_at_uses_the_last_clock_seen_at_or_before_t():
    assert catchup.clock_at(MARKS, 0.0) == "0:00"
    assert catchup.clock_at(MARKS, 599.9) == "5:00"
    assert catchup.clock_at(MARKS, 600.0) == "10:00"
    assert catchup.clock_at([], 10.0) == "0:00"
