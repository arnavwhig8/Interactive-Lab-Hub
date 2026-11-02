"""
Desk Curfew: draw the night as a timeline PNG (for the README and the morning).

Two lanes: when someone was at the desk (blue before curfew, orange after it) and when
the desk light was on. Dashed lines mark goodnight, the curfew and the morning press.
"""
import datetime as dt

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt    # noqa: E402

import core                        # noqa: E402

SURFACE, INK, INK2, TRACK = "#fcfcfb", "#0b0b0b", "#52514e", "#ecebe7"
BEFORE, AFTER, LIGHT, IGNORED = "#2a78d6", "#eb6834", "#eda100", "#b9b7b0"


def _spans(changes, on, end):
    out, start = [], None
    for t, state in changes:
        if state == on and start is None:
            start = t
        elif state != on and start is not None:
            out.append((start, t))
            start = None
    if start is not None:
        out.append((start, max(start, end)))
    return out


def _bars(ax, y, spans, color, h=0.5):
    for s, e in spans:
        width = max((e - s).total_seconds(), 1) / 86400
        ax.barh(y, width, left=mdates.date2num(s), height=h, color=color, edgecolor=SURFACE, linewidth=1.5)


def _setup(ax, t0, t1, lanes):
    pad = (t1 - t0) * 0.02
    ax.set_xlim(mdates.date2num(t0 - pad), mdates.date2num(t1 + pad))
    ax.set_ylim(-0.6, len(lanes) - 0.4)
    ax.set_yticks(range(len(lanes)))
    ax.set_yticklabels(lanes, color=INK, fontsize=10)
    for i in range(len(lanes)):
        ax.barh(i, mdates.date2num(t1) - mdates.date2num(t0), left=mdates.date2num(t0),
                height=0.5, color=TRACK, zorder=0)
    span = t1 - t0
    fmt = "%H:%M:%S" if span < dt.timedelta(minutes=20) else "%H:%M"
    ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))
    ax.tick_params(axis="x", colors=INK2, labelsize=9, length=0)
    ax.tick_params(axis="y", length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#c9c8c2")


def _mark(ax, t, label, top, style="--", color=INK2, side="right"):
    x = mdates.date2num(t)
    ax.axvline(x, color=color, linestyle=style, linewidth=1.2, zorder=3)
    text = " " + label if side == "right" else label + " "
    ax.text(x, top, text, color=color, fontsize=9, va="bottom", ha="left" if side == "right" else "right")


def _legend(fig, keys, step):
    """Swatch in the series color, label in text ink (the label never wears the series color)."""
    for i, (label, color) in enumerate(keys):
        y = 0.93 - step * i
        t = fig.text(0.988, y, label, color=INK2, fontsize=9, ha="right", va="top")
        left = t.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted()).x0
        fig.text(left - 0.004, y, "■", color=color, fontsize=10, ha="right", va="top")


def draw_v2(entries, facts, path, title="Desk Curfew"):
    handoff, curfew = core.parse_ts(facts["handoff"]), core.parse_ts(facts["curfew"])
    reveal = core.parse_ts(facts["reveal"])
    desk = core.desk_changes(entries)
    lights = core.light_changes(entries)
    t0, t1 = min(handoff, curfew), max(reveal, curfew)

    fig, ax = plt.subplots(figsize=(10, 2.9), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    _setup(ax, t0, t1, ["Desk light on", "At the desk"])
    occupied = _spans(desk, "occupied", reveal)
    counted = [(core.parse_ts(a), core.parse_ts(b)) for a, b in facts["sessions"]]
    overlaps = lambda s, e: any(s < b and e > a for a, b in counted)  # noqa: E731
    kept = [(s, e) for s, e in occupied if overlaps(s, e)]
    ignored = [(s, e) for s, e in occupied if not overlaps(s, e)]
    _bars(ax, 1, core.clip(kept, t0, curfew), BEFORE)
    _bars(ax, 1, core.clip(kept, curfew, t1), AFTER)
    _bars(ax, 1, ignored, IGNORED)       # e.g. walking up in the morning to press the button
    _bars(ax, 0, _spans(lights, "on", reveal), LIGHT)

    top = 1.32
    _mark(ax, handoff, "goodnight", top)
    _mark(ax, curfew, f"curfew {facts['curfew_clock']}", top, color=INK)
    _mark(ax, reveal, "morning", top, side="left")

    big, small, _ = core.headline(facts)
    verdict = f"{big.lower().replace('min', 'min past curfew')}  ·  {small}" if facts["verdict"] == "late" \
        else f"{big.title()}  ·  {small}"
    fig.text(0.012, 0.93, title, fontsize=12, fontweight="bold", color=INK, va="top")
    fig.text(0.012, 0.83, verdict, fontsize=10, color=INK2, va="top")
    _legend(fig, [("before curfew", BEFORE), ("after curfew", AFTER)]
            + ([("not counted (morning)", IGNORED)] if ignored else []), step=0.08)
    fig.subplots_adjust(left=0.13, right=0.98, top=0.68, bottom=0.14)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def draw_v1(changes, curfew, handoff, reveal, path, title="Desk Curfew v1: raw readings"):
    """v1 has no debouncer: every flicker in overnight.py's log becomes its own visit."""
    t0, t1 = min(handoff, curfew), max(reveal, curfew)
    fig, ax = plt.subplots(figsize=(10, 2.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    _setup(ax, t0, t1, ["At the desk"])
    occupied = _spans(changes, "occupied", reveal)
    _bars(ax, 0, core.clip(occupied, t0, curfew), BEFORE)
    _bars(ax, 0, core.clip(occupied, curfew, t1), AFTER)
    _mark(ax, curfew, f"curfew {core.clock(curfew)}", 0.32, color=INK)
    _mark(ax, reveal, "morning", 0.32, side="left")
    fig.text(0.012, 0.93, title, fontsize=12, fontweight="bold", color=INK, va="top")
    fig.text(0.012, 0.80, f"{len(occupied)} separate 'visits' in the raw log", fontsize=10, color=INK2, va="top")
    _legend(fig, [("before curfew", BEFORE), ("after curfew", AFTER)], step=0.11)
    fig.subplots_adjust(left=0.13, right=0.98, top=0.62, bottom=0.18)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
