"""
Desk Curfew: the logic, with no camera, screen or model in it, so it can be tested anywhere.

The rule this file exists to enforce: the CODE works out the facts of the night
(when you were last at the desk, how late that was, how often you came back),
and the language model is only allowed to put those facts into a sentence.
`check_sentence()` rejects a sentence that mentions a number or time that is not a fact.
"""
import datetime as dt
import json
import re

# ----------------------------------------------------------------------------- time helpers


def parse_ts(s):
    return dt.datetime.fromisoformat(s)


def ts(t):
    return t.isoformat(timespec="seconds")


def clock(t):
    """1:47am, 12:00am (midnight), 12:30pm."""
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d}{'am' if t.hour < 12 else 'pm'}"


def spoken(text):
    """Make times easier for Piper to say: 1:47am -> 1:47 a.m."""
    return re.sub(r"(\d)(am|pm)\b", lambda m: f"{m.group(1)} {m.group(2)[0]}.m.", text)


def resolve_curfew(hhmm, handoff):
    """'00:30' typed at 22:10 means 00:30 tomorrow; typed at 00:40 it means 00:30 tonight (already passed).
    Pick the occurrence closest to the hand-off, in the window [hand-off - 6 h, hand-off + 18 h]."""
    h, m = (int(x) for x in hhmm.split(":"))
    t = handoff.replace(hour=h, minute=m, second=0, microsecond=0)
    if t < handoff - dt.timedelta(hours=6):
        t += dt.timedelta(days=1)
    elif t > handoff + dt.timedelta(hours=18):
        t -= dt.timedelta(days=1)
    return t


def propose_curfew(now, step_min=30, lead_min=30):
    """The first time the bedtime dial offers: now + lead, rounded up to the next step."""
    t = now + dt.timedelta(minutes=lead_min)
    if t.second or t.microsecond:              # round up to the next whole minute
        t = t.replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    extra = (-t.minute) % step_min
    return t + dt.timedelta(minutes=extra)


# ----------------------------------------------------------------------------- the night shift


class Debouncer:
    """YOLO flickers: you turn your back, lean out of frame or the exposure shifts, and one look
    says 'empty'. A state only changes after `need` looks in a row agree. The ones that do not
    make it are counted, so the morning can say how many flickers were ignored."""

    def __init__(self, need=3, initial=None):
        self.need = need
        self.state = initial
        self.candidate, self.streak, self.first_seen = None, 0, None
        self.since = None          # when the current state was first seen (not when it was confirmed)
        self.suppressed = 0

    def update(self, raw, t=None):
        """Feed one look taken at time t. Returns the new state if it just changed, else None."""
        if self.state is None:                 # first look decides the starting state
            self.state, self.since = raw, t
            return raw
        if raw == self.state:
            if self.streak:                    # a run of disagreeing looks died out
                self.suppressed += 1
            self.candidate, self.streak = None, 0
            return None
        if raw == self.candidate:
            self.streak += 1
        else:
            self.candidate, self.streak, self.first_seen = raw, 1, t
        if self.streak >= self.need:
            self.state, self.since = raw, self.first_seen
            self.candidate, self.streak = None, 0
            return raw
        return None


def read_log(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def desk_changes(entries):
    """[(time, 'occupied'|'empty')] from a v2 log (lines with "desk")."""
    return [(parse_ts(e["t"]), e["desk"]) for e in entries if "desk" in e]


def light_changes(entries):
    return [(parse_ts(e["t"]), e["light"]) for e in entries if "light" in e]


def stock_changes(entries):
    """Same thing from the class overnight.py log (lines with "reading"): anything but 'nobody'
    counts as occupied. Used by v1 and by v1's --check."""
    out = []
    for e in entries:
        if "reading" in e:
            state = "empty" if e["reading"] == "nobody" else "occupied"
            if not out or out[-1][1] != state:
                out.append((parse_ts(e["t"]), state))
    return out


def sessions(changes, end):
    """Occupied intervals [(start, stop)] from a list of state changes, closing an open one at `end`."""
    out, start = [], None
    for t, state in changes:
        if state == "occupied" and start is None:
            start = t
        elif state == "empty" and start is not None:
            out.append((start, t))
            start = None
    if start is not None:
        out.append((start, max(start, end)))
    return out


def merge(spans, gap):
    """Absences shorter than `gap` (water, bathroom, a YOLO miss) are not 'leaving the desk'."""
    out = []
    for s, e in sorted(spans):
        if out and s - out[-1][1] < gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def clip(spans, lo, hi):
    out = []
    for s, e in spans:
        s, e = max(s, lo), min(e, hi)
        if e > s:
            out.append((s, e))
    return out


def watch_gaps(entries, max_gap):
    """Stretches with no log line at all longer than max_gap: the camera or script was down.
    v2 writes a heartbeat every few minutes, so a long silence means a crash, not a quiet night."""
    times = [parse_ts(e["t"]) for e in entries if "t" in e]
    return [(a, b) for a, b in zip(times, times[1:]) if b - a > max_gap]


# ----------------------------------------------------------------------------- the morning: facts


def minutes(td):
    return int(round(td.total_seconds() / 60))


def compute_facts(changes, handoff, curfew, reveal, *, merge_gap, morning_grace, on_time_grace,
                  morning_after=None, lights=None, gaps=None):
    """Everything the morning is allowed to say, worked out in code.

    handoff        when the bedtime ritual finished (the night starts)
    curfew         when you said you would leave the desk
    reveal         when you pressed the button in the morning (the night ends)
    morning_grace  ignore the last stretch before the reveal: that is you, walking up to press the button
    morning_after  a session that STARTS after this is the morning (coffee, email), not the night
    on_time_grace  leaving up to this long after curfew still counts as on time
    """
    window_end = reveal - morning_grace
    raw = clip(sessions(changes, reveal), handoff, window_end)
    if morning_after is not None:
        raw = [(s, e) for s, e in raw if s < morning_after]
    merged = merge(raw, merge_gap)
    after = clip(merged, curfew, window_end)

    last = merged[-1][1] if merged else None
    # count minutes between the clock times we SHOW, so "until 7:41pm, 8 minutes late" adds up
    late = minutes(last.replace(second=0, microsecond=0) - curfew.replace(second=0, microsecond=0)) if last else None
    facts = {
        "handoff": ts(handoff),
        "curfew": ts(curfew),
        "reveal": ts(reveal),
        "curfew_clock": clock(curfew),
        "watched_from": clock(handoff),
        "watched_until": clock(reveal),
        "sessions": [[ts(s), ts(e)] for s, e in merged],
        "raw_session_count": len(raw),
        "session_count": len(merged),
        "last_at_desk": ts(last) if last else None,
        "last_at_desk_clock": clock(last) if last else None,
        "minutes_late": max(0, late) if late is not None else 0,
        "minutes_early": max(0, -late) if late is not None else 0,
        "returns_after_curfew": sum(1 for s, _ in after if s > curfew),
        "minutes_at_desk_after_curfew": sum(minutes(e - s) for s, e in after),
        "still_there_at_reveal": bool(raw) and raw[-1][1] >= window_end,
        "lights_out_clock": None,
        "watch_gaps": [[clock(a), clock(b)] for a, b in (gaps or [])],
    }
    if lights:
        dark = [t for t, state in lights if state == "dark" and handoff <= t <= window_end]
        if dark:
            facts["lights_out_clock"] = clock(dark[-1])

    if not merged:
        facts["verdict"] = "away"            # never at the desk after the hand-off
    elif late <= minutes(on_time_grace):
        facts["verdict"] = "on_time"
    else:
        facts["verdict"] = "late"
    return facts


# ----------------------------------------------------------------------------- the morning: words


def headline(f):
    """Two short lines for the screen: (big, small, mood)."""
    if f["verdict"] == "late":
        return f"+{f['minutes_late']} MIN", f"last at desk {f['last_at_desk_clock']}", "late"
    if f["verdict"] == "on_time":
        return "ON TIME", f"left desk {f['last_at_desk_clock']}", "ok"
    return "ON TIME", "desk empty all night", "ok"


def template(f):
    """The sentence the device says when the model is not trusted. Always true."""
    cur = f["curfew_clock"]
    if f["verdict"] == "away":
        s = f"Good morning. Nobody was at the desk after you said goodnight, so bed by {cur} it was."
    elif f["verdict"] == "on_time":
        if f["minutes_early"]:
            s = (f"Good morning. You left the desk at {f['last_at_desk_clock']}, "
                 f"{f['minutes_early']} minutes before your {cur} curfew.")
        else:
            s = f"Good morning. You left the desk at {f['last_at_desk_clock']}, right on your {cur} curfew."
    else:
        s = (f"Good morning. You said bed by {cur}, but you were at the desk until "
             f"{f['last_at_desk_clock']}, {f['minutes_late']} minutes late.")
        if f["returns_after_curfew"]:
            n = f["returns_after_curfew"]
            s += f" You came back {n} time{'s' if n != 1 else ''} after curfew."
    if f["watch_gaps"]:
        a, b = f["watch_gaps"][0]
        s += f" I stopped watching between {a} and {b}, so I may have missed something."
    return s


def prompt_for(f):
    lines = [
        f"- curfew they set last night: {f['curfew_clock']}",
        f"- verdict: {f['verdict'].replace('_', ' ')}",
    ]
    if f["last_at_desk_clock"]:
        lines.append(f"- last time at the desk: {f['last_at_desk_clock']}")
    if f["verdict"] == "late":
        lines.append(f"- minutes past curfew: {f['minutes_late']}")
        lines.append(f"- times they came back to the desk after curfew: {f['returns_after_curfew']}")
    elif f["minutes_early"]:
        lines.append(f"- minutes before curfew: {f['minutes_early']}")
    if f["lights_out_clock"]:
        lines.append(f"- desk went dark at: {f['lights_out_clock']}")
    if f["watch_gaps"]:
        a, b = f["watch_gaps"][0]
        lines.append(f"- the camera was not watching between {a} and {b}")
    facts = "\n".join(lines)
    return f"""You are a small desk device. Last night the person told you when they would stop working and go to bed.
Here are the facts of the night, already checked:
{facts}

Write a good-morning message of at most two short sentences, speaking to them as "you".
Be warm but honest: if they were late, say so plainly. Use only the facts above.
Write every time exactly as it appears above. Do not add any other numbers or times."""


_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\s*(a\.?m\.?|p\.?m\.?)?", re.I)
_HOUR = re.compile(r"\b(\d{1,2})\s*(a\.?m\.?|p\.?m\.?)(?=\W|$)", re.I)     # "12am", "1 a.m."
_NUM = re.compile(r"\b\d+\b")
_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
          "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "twice": 2}


def _allowed(f):
    """The times and the bare numbers the morning sentence may contain. The minutes of a time are
    NOT allowed as a bare number: '1:47am' must not turn into '47 minutes late'."""
    times, nums = set(), set()
    values = [v for k, v in f.items() if k.endswith("_clock") and v]
    values += [v for pair in f["watch_gaps"] for v in pair]
    for value in values:
        m = _TIME.search(value)
        times.add((int(m.group(1)) % 12, int(m.group(2))))
    if f["verdict"] == "late":
        nums.update({f["minutes_late"], f["returns_after_curfew"]})
    else:
        nums.add(f["minutes_early"])
    return times, nums


def check_sentence(text, f):
    """Return None if the model's sentence only states facts, else the reason it was rejected."""
    if not text or not text.strip():
        return "empty answer"
    if len(text) > 400:
        return "too long"
    times, nums = _allowed(f)
    for m in _TIME.finditer(text):
        if (int(m.group(1)) % 12, int(m.group(2))) not in times:
            return f"made-up time '{m.group(0).strip()}'"
    rest = _TIME.sub(" ", text)
    for m in _HOUR.finditer(rest):
        if (int(m.group(1)) % 12, 0) not in times:
            return f"made-up time '{m.group(0).strip()}'"
    rest = _HOUR.sub(" ", rest)
    for m in _NUM.finditer(rest):
        if int(m.group(0)) not in nums:
            return f"made-up number '{m.group(0)}'"
    for word, n in _WORDS.items():
        if re.search(rf"\b{word}\b", rest, re.I) and n not in nums:
            return f"made-up number '{word}'"
    low = text.lower()
    if f["verdict"] == "late" and ("on time" in low or "early" in low):
        return "says on time, but the night was late"
    if f["verdict"] != "late" and re.search(r"\blate\b|past (your )?curfew", low):
        return "says late, but the night was on time"
    # Added after the first real demo night: Qwen wrote "over an hour past your curfew" for a
    # 7-minute night. Durations in words slipped past the number check, so they are checked too,
    # and a late sentence must state the actual number of minutes.
    if re.search(r"\bhours?\b|all night|whole night", low) and f["minutes_late"] < 55:
        return "talks about hours, but it was minutes"
    if f["verdict"] == "late" and str(f["minutes_late"]) not in _NUM.findall(rest):
        return f"does not say how late it was ({f['minutes_late']} minutes)"
    return None
