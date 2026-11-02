"""
Tests for the Desk Curfew logic. No camera, Pi or model needed:

    python -m pytest desk_curfew/tests -q        (or: python desk_curfew/tests/test_core.py)

The nights in here are made up to exercise the edge cases; they are test fixtures, not data.
"""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import core  # noqa: E402

D = dt.datetime(2026, 11, 1)


def at(h, m, s=0, day=0):
    return D + dt.timedelta(days=day, hours=h, minutes=m, seconds=s)


M = dt.timedelta(minutes=1)
KW = dict(merge_gap=3 * M, morning_grace=3 * M, on_time_grace=5 * M)


# ----------------------------------------------------------------------------- time


def test_clock():
    assert core.clock(at(0, 5)) == "12:05am"
    assert core.clock(at(13, 47)) == "1:47pm"
    assert core.clock(at(1, 47)) == "1:47am"
    assert core.spoken("bed by 12:30am.") == "bed by 12:30 a.m.."


def test_resolve_curfew():
    assert core.resolve_curfew("00:30", at(22, 10)) == at(0, 30, day=1)     # tonight, after midnight
    assert core.resolve_curfew("23:30", at(22, 10)) == at(23, 30)
    assert core.resolve_curfew("00:30", at(0, 40)) == at(0, 30)             # already passed
    assert core.resolve_curfew("23:00", at(0, 40, day=1)) == at(23, 0)      # yesterday's 23:00


def test_propose_curfew():
    assert core.propose_curfew(at(22, 47)) == at(23, 30)
    assert core.propose_curfew(at(23, 0)) == at(23, 30)
    assert core.propose_curfew(at(23, 10, 20), step_min=1, lead_min=2) == at(23, 13)


# ----------------------------------------------------------------------------- debouncer


def test_debouncer_ignores_single_flicker():
    db = core.Debouncer(3)
    looks = ["occupied"] * 4 + ["empty"] + ["occupied"] * 3 + ["empty"] * 2 + ["occupied"]
    changes = [db.update(x, i) for i, x in enumerate(looks)]
    assert [c for c in changes if c] == ["occupied"]
    assert db.state == "occupied" and db.suppressed == 2


def test_debouncer_times_change_from_first_look():
    db = core.Debouncer(3)
    for i, x in enumerate(["occupied", "occupied", "empty", "empty", "empty"]):
        db.update(x, i * 10)
    assert db.state == "empty" and db.since == 20


# ----------------------------------------------------------------------------- facts


def night(*pairs):
    return [(t, s) for t, s in pairs]


def test_late_night_with_returns():
    ch = night((at(22, 30), "occupied"), (at(0, 20, day=1), "empty"),          # left 20 min late
               (at(0, 21, day=1), "occupied"), (at(0, 22, day=1), "empty"),    # 1-min break: merged
               (at(1, 0, day=1), "occupied"), (at(1, 47, day=1), "empty"))     # came back
    f = core.compute_facts(ch, at(22, 30), at(0, 0, day=1), at(8, 0, day=1), **KW)
    assert f["verdict"] == "late"
    assert f["last_at_desk_clock"] == "1:47am"
    assert f["minutes_late"] == 107
    assert f["returns_after_curfew"] == 1
    assert f["raw_session_count"] == 3 and f["session_count"] == 2
    assert f["minutes_at_desk_after_curfew"] == 22 + 47


def test_on_time_and_early():
    ch = night((at(22, 30), "occupied"), (at(23, 52), "empty"))
    f = core.compute_facts(ch, at(22, 30), at(0, 0, day=1), at(8, 0, day=1), **KW)
    assert f["verdict"] == "on_time" and f["minutes_early"] == 8 and f["minutes_late"] == 0
    assert core.headline(f) == ("ON TIME", "left desk 11:52pm", "ok")


def test_within_grace_is_on_time():
    ch = night((at(22, 30), "occupied"), (at(0, 4, day=1), "empty"))
    f = core.compute_facts(ch, at(22, 30), at(0, 0, day=1), at(8, 0, day=1), **KW)
    assert f["verdict"] == "on_time"


def test_morning_press_is_not_a_late_night():
    # back at the desk at 8:50 for email, presses the button at 9:00
    ch = night((at(22, 30), "occupied"), (at(23, 50), "empty"), (at(8, 50, day=1), "occupied"))
    f = core.compute_facts(ch, at(22, 30), at(0, 0, day=1), at(9, 0, day=1),
                           morning_after=at(5, 0, day=1), **KW)
    assert f["verdict"] == "on_time" and f["last_at_desk_clock"] == "11:50pm"
    # without morning_after the 8:50 session would wrongly count
    g = core.compute_facts(ch, at(22, 30), at(0, 0, day=1), at(9, 0, day=1), **KW)
    assert g["verdict"] == "late"


def test_fell_asleep_at_desk():
    ch = night((at(22, 30), "occupied"),)
    f = core.compute_facts(ch, at(22, 30), at(0, 0, day=1), at(1, 0, day=1), **KW)
    assert f["verdict"] == "late" and f["still_there_at_reveal"]


def test_never_at_desk():
    f = core.compute_facts([(at(22, 30), "empty")], at(22, 30), at(0, 0, day=1), at(8, 0, day=1), **KW)
    assert f["verdict"] == "away"
    assert "Nobody was at the desk" in core.template(f)


def test_watch_gap_is_reported():
    entries = [{"t": core.ts(at(22, 30)), "desk": "occupied"},
               {"t": core.ts(at(23, 0)), "desk": "empty"},
               {"t": core.ts(at(3, 0, day=1)), "alive": True}]
    gaps = core.watch_gaps(entries, dt.timedelta(minutes=45))
    f = core.compute_facts(core.desk_changes(entries), at(22, 30), at(0, 0, day=1), at(8, 0, day=1),
                           gaps=gaps, **KW)
    assert f["watch_gaps"] == [["11:00pm", "3:00am"]]
    assert "stopped watching between 11:00pm and 3:00am" in core.template(f)


def test_stock_log_conversion():
    entries = [{"t": core.ts(at(23, 0)), "reading": "1 person(s) at center/close"},
               {"t": core.ts(at(23, 1)), "reading": "1 person(s) at left/close"},   # still occupied
               {"t": core.ts(at(23, 2)), "reading": "nobody"},
               {"t": core.ts(at(23, 3)), "alive": True}]
    assert core.stock_changes(entries) == [(at(23, 0), "occupied"), (at(23, 2), "empty")]


# ----------------------------------------------------------------------------- the sentence checker


def late_facts():
    ch = night((at(22, 30), "occupied"), (at(1, 0, day=1), "empty"),
               (at(1, 20, day=1), "occupied"), (at(1, 47, day=1), "empty"))
    return core.compute_facts(ch, at(22, 30), at(0, 0, day=1), at(8, 0, day=1), **KW)


def test_checker_accepts_faithful_sentence():
    f = late_facts()
    ok = ("Good morning! You meant to be in bed by 12:00am, but you were at the desk until 1:47 AM, "
          "107 minutes late, and you came back once after curfew.")
    assert core.check_sentence(ok, f) is None
    assert core.check_sentence(core.template(f), f) is None


def test_checker_rejects_made_up_numbers():
    f = late_facts()
    assert "made-up number" in core.check_sentence("You were 47 minutes late, last at 1:47am.", f)
    assert "made-up time" in core.check_sentence("You left at 2:15am.", f)
    assert "made-up number" in core.check_sentence("You came back three times after 12:00am.", f)


def test_checker_rejects_wrong_verdict():
    f = late_facts()
    assert "on time" in core.check_sentence("Great job, you were on time!", f)
    g = core.compute_facts(night((at(22, 30), "occupied"), (at(23, 52), "empty")),
                           at(22, 30), at(0, 0, day=1), at(8, 0, day=1), **KW)
    assert core.check_sentence("You stayed up late again.", g)
    assert core.check_sentence("Morning! You left at 11:52pm, 8 minutes before your 12:00am curfew.", g) is None


def test_templates_always_pass_their_own_checker():
    for ch, rev in [
        (night((at(22, 30), "occupied"), (at(23, 52), "empty")), at(8, 0, day=1)),
        (night((at(22, 30), "occupied"), (at(0, 0, day=1), "empty")), at(8, 0, day=1)),
        (night((at(22, 30), "occupied"), (at(2, 0, day=1), "empty")), at(8, 0, day=1)),
        (night((at(22, 30), "empty"),), at(8, 0, day=1)),
    ]:
        f = core.compute_facts(ch, at(22, 30), at(0, 0, day=1), rev, **KW)
        assert core.check_sentence(core.template(f), f) is None, core.template(f)


def test_real_demo_night_and_the_sentence_that_slipped_through():
    """The first real v2 demo night (Nov 1): curfew 10:46pm, left at 10:47, back at 10:50, left at 10:53.
    Qwen said 'over an hour past your curfew' and the first checker let it through."""
    T = lambda h, m, s=0: dt.datetime(2026, 11, 1, h, m, s)  # noqa: E731
    ch = [(T(22, 42, 36), "occupied"), (T(22, 47, 15), "empty"), (T(22, 50, 28), "occupied"), (T(22, 53, 31), "empty")]
    f = core.compute_facts(ch, T(22, 42, 36), T(22, 46), T(22, 56, 10), merge_gap=dt.timedelta(seconds=30),
                           morning_grace=dt.timedelta(seconds=60), on_time_grace=dt.timedelta(0))
    assert (f["verdict"], f["last_at_desk_clock"], f["minutes_late"], f["returns_after_curfew"]) == ("late", "10:53pm", 7, 1)
    qwen = ("It is 10:53pm and you have been awake for over an hour past your curfew. "
            "I know you are tired, but please rest now.")
    assert core.check_sentence(qwen, f) == "talks about hours, but it was minutes"
    assert "does not say how late" in core.check_sentence("You stayed at the desk until 10:53pm, past your 10:46pm curfew.", f)
    assert core.check_sentence("You said bed by 10:46pm but stayed until 10:53pm, 7 minutes late.", f) is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
