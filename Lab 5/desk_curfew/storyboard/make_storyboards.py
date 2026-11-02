"""
Draws the Desk Curfew storyboards (v1 and the revised v2) and the Verplank diagram as SVG,
then PNG (needs rsvg-convert:  sudo apt install librsvg2-bin).

    python desk_curfew/storyboard/make_storyboards.py
"""
import pathlib
import shutil
import subprocess

OUT = pathlib.Path(__file__).resolve().parent
INK, MUTED, PAPER, NIGHT = "#22211f", "#6b6a66", "#f7f5ef", "#1c2240"
BLUE, ORANGE, AMBER, GREEN, LED = "#2a78d6", "#eb6834", "#eda100", "#1baf7a", "#e34948"
FONT = "DejaVu Sans, sans-serif"
PW, PH = 560, 400            # one panel


def text(x, y, s, size=15, fill=INK, anchor="start", weight="normal", family=FONT):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{s}</text>')


def lines(x, y, rows, size=14, fill=INK, gap=None, anchor="start", weight="normal", family=FONT):
    gap = gap or size * 1.3
    return "".join(text(x, y + i * gap, r, size, fill, anchor, weight, family) for i, r in enumerate(rows))


def desk(x, y, dark=False):
    c = "#8c8a84" if dark else INK
    return (f'<rect x="{x}" y="{y}" width="250" height="12" rx="3" fill="{"#3a3f5c" if dark else "#d9d3c4"}" stroke="{c}" stroke-width="2.5"/>'
            f'<line x1="{x + 14}" y1="{y + 12}" x2="{x + 14}" y2="{y + 100}" stroke="{c}" stroke-width="3"/>'
            f'<line x1="{x + 236}" y1="{y + 12}" x2="{x + 236}" y2="{y + 100}" stroke="{c}" stroke-width="3"/>')


def chair(x, y, dark=False):
    c = "#8c8a84" if dark else INK
    return (f'<path d="M{x} {y} L{x} {y + 70} M{x} {y + 70} L{x + 55} {y + 70} M{x + 8} {y + 70} L{x + 8} {y + 146} '
            f'M{x + 50} {y + 70} L{x + 50} {y + 146}" stroke="{c}" stroke-width="4" fill="none" stroke-linecap="round"/>')


def person_sitting(x, y, color=BLUE, arm="desk"):
    """x,y = top of head. Facing right, sitting on a chair."""
    arm_path = f"M{x + 6} {y + 52} L{x + 48} {y + 66} L{x + 78} {y + 60}" if arm == "desk" else \
               f"M{x + 6} {y + 52} L{x + 44} {y + 40} L{x + 70} {y + 22}"
    return (f'<circle cx="{x}" cy="{y + 16}" r="16" fill="{PAPER}" stroke="{color}" stroke-width="3.5"/>'
            f'<path d="M{x} {y + 32} L{x - 4} {y + 100} L{x + 50} {y + 102} L{x + 54} {y + 152} '
            f'{arm_path}" stroke="{color}" stroke-width="4.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')


def person_standing(x, y, color=BLUE, reach=None):
    """x,y = top of head; reach = (hx, hy) where the hand goes, e.g. the button."""
    if reach:
        hx, hy = reach
        arm = f"M{x} {y + 50} L{x + 46} {hy - 4} L{hx} {hy}"      # elbow up, so the arm stays above the box
    else:
        arm = f"M{x} {y + 50} L{x - 14} {y + 96}"
    return (f'<circle cx="{x}" cy="{y + 16}" r="16" fill="{PAPER}" stroke="{color}" stroke-width="3.5"/>'
            f'<path d="M{x} {y + 32} L{x} {y + 112} M{x} {y + 112} L{x - 18} {y + 178} M{x} {y + 112} L{x + 18} {y + 178} '
            f'{arm}" stroke="{color}" stroke-width="4.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/>')


def laptop(x, y, screen_rows=(), dark=False, glow=False):
    c = "#8c8a84" if dark else INK
    fill = "#0e1226" if dark else "#ffffff"
    g = f'<rect x="{x - 6}" y="{y - 6}" width="132" height="92" rx="10" fill="{AMBER}" opacity="0.25"/>' if glow else ""
    return (g + f'<rect x="{x}" y="{y}" width="120" height="78" rx="5" fill="{fill}" stroke="{c}" stroke-width="2.5"/>'
            f'<path d="M{x - 10} {y + 84} L{x + 130} {y + 84}" stroke="{c}" stroke-width="5" stroke-linecap="round"/>'
            + lines(x + 7, y + 17, screen_rows, size=10, fill=GREEN if dark else INK, gap=13, family="DejaVu Sans Mono, monospace"))


def device(x, y, screen=("",), mood=None, screen_on=True, led=None, dark=False, cam_dir="left"):
    """The Pi in its box: a screen on the front, the Qwiic Button on top, the webcam on a stalk."""
    c = "#a9a7a0" if dark else INK
    scr = {"late": AMBER, "ok": GREEN, "night": "#2b3570", None: "#2b3570"}[mood]
    body = f'<rect x="{x}" y="{y}" width="110" height="64" rx="8" fill="{"#2c3150" if dark else "#e9e4d8"}" stroke="{c}" stroke-width="2.5"/>'
    if screen_on:
        body += f'<rect x="{x + 10}" y="{y + 10}" width="90" height="44" rx="3" fill="#0b0d18"/>'
        body += lines(x + 55, y + 28, screen, size=11, fill="#ffffff", gap=14, anchor="middle", weight="bold")
        body += f'<rect x="{x + 10}" y="{y + 48}" width="90" height="6" fill="{scr}"/>'
    else:
        body += f'<rect x="{x + 10}" y="{y + 10}" width="90" height="44" rx="3" fill="#05060c" stroke="#3a3f5c"/>'
    # button on top
    body += f'<rect x="{x + 70}" y="{y - 12}" width="26" height="12" rx="3" fill="#bbb6a8" stroke="{c}" stroke-width="2"/>'
    if led:
        body += f'<circle cx="{x + 83}" cy="{y - 16}" r="{led}" fill="{LED}" opacity="0.55"/>'
    body += f'<circle cx="{x + 83}" cy="{y - 15}" r="6" fill="{LED if led else "#d8d2c4"}" stroke="{c}" stroke-width="1.5"/>'
    # webcam on a stalk, looking at the chair
    sx = x + 18
    body += f'<line x1="{sx}" y1="{y}" x2="{sx}" y2="{y - 34}" stroke="{c}" stroke-width="3"/>'
    body += f'<rect x="{sx - 16}" y="{y - 50}" width="32" height="18" rx="5" fill="#3d3b37" stroke="{c}" stroke-width="2"/>'
    lens_x = sx - 16 if cam_dir == "left" else sx + 16
    body += f'<circle cx="{lens_x}" cy="{y - 41}" r="5" fill="#6aa0e8" stroke="{c}" stroke-width="1.5"/>'
    return body


def view_cone(x, y, dark=False, to=None, top=None, bottom=None):
    """The webcam's field of view, from the lens at (x, y) to a vertical edge at x = to."""
    to = x - 190 if to is None else to
    top = y - 40 if top is None else top
    bottom = y + 130 if bottom is None else bottom
    return (f'<path d="M{x} {y} L{to} {top} L{to} {bottom} Z" fill="{"#8fa8ff" if dark else BLUE}" '
            f'opacity="{0.13 if dark else 0.10}"/>')


def watch_zone(x, dark=False):
    """Added after Shifeng's feedback: mark the chair as the one thing the camera watches."""
    c = "#f4c95d" if dark else AMBER
    return (f'<rect x="{x - 22}" y="170" width="100" height="168" rx="10" fill="none" stroke="{c}" '
            f'stroke-width="2.5" stroke-dasharray="7 5"/>'
            + text(x + 28, 360, "the camera watches", 12, c, anchor="middle", weight="bold")
            + text(x + 28, 376, "this chair only", 12, c, anchor="middle", weight="bold"))


def bubble(x, y, w, rows, tail="left", size=13, fill="#ffffff"):
    h = 18 + 18 * len(rows)
    tx = x + 24 if tail == "left" else x + w - 24
    path = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{INK}" stroke-width="2"/>'
            f'<path d="M{tx - 8} {y + h - 1} L{tx + (-14 if tail == "left" else 14)} {y + h + 18} L{tx + 8} {y + h - 1}" '
            f'fill="{fill}" stroke="{INK}" stroke-width="2"/>'
            f'<line x1="{tx - 7}" y1="{y + h - 1}" x2="{tx + 7}" y2="{y + h - 1}" stroke="{fill}" stroke-width="3"/>')
    return path + lines(x + 14, y + 22, rows, size=size, gap=18)


def window(x, y, night=True):
    sky = NIGHT if night else "#cfe3f7"
    s = (f'<rect x="{x}" y="{y}" width="92" height="76" fill="{sky}" stroke="{"#8c8a84" if night else INK}" stroke-width="3"/>'
         f'<line x1="{x + 46}" y1="{y}" x2="{x + 46}" y2="{y + 76}" stroke="{"#8c8a84" if night else INK}" stroke-width="2"/>')
    if night:
        s += f'<path d="M{x + 70} {y + 18} a12 12 0 1 0 6 22 a10 10 0 1 1 -6 -22" fill="#f4e7b0"/>'
        s += "".join(f'<circle cx="{x + a}" cy="{y + b}" r="1.6" fill="#fff"/>' for a, b in ((14, 14), (30, 40), (20, 60), (58, 56)))
    else:
        s += f'<circle cx="{x + 24}" cy="{y + 24}" r="11" fill="{AMBER}"/>'
    return s


def bed(x, y):
    return (f'<rect x="{x}" y="{y}" width="150" height="34" rx="6" fill="#3a3f5c" stroke="#8c8a84" stroke-width="2.5"/>'
            f'<rect x="{x}" y="{y - 30}" width="10" height="64" fill="#8c8a84"/>'
            f'<ellipse cx="{x + 32}" cy="{y - 4}" rx="20" ry="10" fill="#c9c6d8"/>'
            f'<circle cx="{x + 34}" cy="{y - 14}" r="12" fill="#4a5070" stroke="#c9c6d8" stroke-width="2"/>'
            f'<path d="M{x + 46} {y - 10} Q{x + 100} {y - 26} {x + 146} {y - 4} L{x + 146} {y + 4} L{x + 46} {y + 4} Z" fill="#6a72a8"/>'
            + text(x + 64, y - 34, "z z z", 16, "#c9c6d8", weight="bold"))


def panel(i, title, caption_rows, body, night=False):
    x = 20 + i * (PW + 20)
    bg = NIGHT if night else PAPER
    out = (f'<g transform="translate({x},74)">'
           f'<rect x="0" y="0" width="{PW}" height="{PH}" rx="14" fill="{bg}" stroke="{INK}" stroke-width="2.5"/>'
           f'<line x1="0" y1="{PH - 64}" x2="{PW}" y2="{PH - 64}" stroke="{"#8c8a84" if night else "#c9c3b4"}" stroke-width="2"/>'
           + body +
           f'<rect x="12" y="12" width="{len(title) * 10.4 + 26}" height="30" rx="15" fill="{INK if not night else "#f7f5ef"}"/>'
           + text(25, 33, title, 15, PAPER if not night else INK, weight="bold") + '</g>'
           + lines(x + 6, 74 + PH + 30, caption_rows, size=15, fill=INK, gap=21))
    return out


def sheet(title, subtitle, panels, name, height=600):
    w = 20 + 3 * (PW + 20)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{height}" viewBox="0 0 {w} {height}">'
           f'<rect width="100%" height="100%" fill="#ffffff"/>'
           + text(20, 34, title, 24, INK, weight="bold") + text(20, 58, subtitle, 15, MUTED)
           + "".join(panels) + "</svg>")
    save(svg, name)


def save(svg, name):
    (OUT / f"{name}.svg").write_text(svg)
    if shutil.which("rsvg-convert"):
        subprocess.run(["rsvg-convert", "-z", "1.5", "-o", str(OUT / f"{name}.png"), str(OUT / f"{name}.svg")], check=True)


# ============================================================================ v1


def v1():
    # 1. before bed: typing the curfew over ssh
    p1 = (window(420, 70, night=True) + desk(250, 236) + chair(150, 190)
          + person_sitting(170, 146, BLUE, arm="desk")
          + laptop(255, 150, ["$ python bedtime_v1", ".py 00:30", "Got it: bed by", "12:30am. Now start", "overnight.py"])
          + device(410, 172, ("BED BY", "12:30am"), "night", cam_dir="left")
          + bubble(50, 56, 220, ["Ugh, what time format", "does it want again?"], tail="right"))
    # 2. asleep: stock overnight.py, screen left glowing
    p2 = (window(420, 70, night=True) + bed(28, 300) + view_cone(428, 140, dark=True)
          + desk(250, 236, dark=True) + chair(150, 190, dark=True)
          + device(410, 172, ("BED BY", "12:30am"), "night", dark=True, cam_dir="left")
          + f'<circle cx="465" cy="194" r="58" fill="{AMBER}" opacity="0.12"/>'
          + bubble(200, 60, 200, ["night_log.jsonl", "01:12 nobody", "01:12 1 person(s)", "01:13 nobody  ..."], size=12, fill="#e8ecff"))
    # 3. morning: read Qwen's guess in the terminal
    p3 = (window(420, 70, night=False) + desk(250, 236) + chair(150, 190)
          + person_sitting(170, 146, BLUE, arm="desk")
          + laptop(255, 150, ["$ python morning_v1", "You came back 6", "times and were", "11 minutes late.", "  (wrong)"])
          + device(410, 172, ("BED BY", "12:30am"), "night", cam_dir="left")
          + bubble(40, 56, 200, ["6 times?? I only", "got up once..."], tail="right"))
    sheet("Desk Curfew v1", "First storyboard: the class pipeline, almost unchanged", [
        panel(0, "1  BEFORE BED", ["Type the curfew over ssh (bedtime_v1.py 00:30).",
                                   "The screen says BED BY 12:30am."], p1),
        panel(1, "2  WHILE ASLEEP", ["overnight.py logs the chair every 5 s.",
                                     "Every YOLO miss is a new log line. The screen glows all night."], p2, night=True),
        panel(2, "3  WHEN AWAKE", ["morning_v1.py pastes the raw log into Qwen and asks",
                                   "'did I go to bed on time?' The answer is a guess."], p3),
    ], "storyboard_v1")


# ============================================================================ v2


def v2():
    btn = (473, 152)            # the Qwiic Button on top of the device at x=390
    # 1. before bed: tap to set, hold to confirm, device answers
    p1 = (window(420, 70, night=True) + view_cone(408, 131, to=158, top=165, bottom=338)
          + desk(250, 236) + chair(180, 190) + watch_zone(180)
          + device(390, 172, ("BED BY", "12:30am"), "night", led=8, cam_dir="left")
          + person_standing(330, 158, BLUE, reach=btn)
          + bubble(30, 64, 250, ['"Okay. Bed by 12:30 a.m.', 'Goodnight, I\'ll watch', 'the desk."'], tail="right")
          + text(330, 372, "tap = +30 min · hold = OK", 13, MUTED))
    # 2. asleep: screen dark, LED breathing, debounced log
    p2 = (window(420, 70, night=True) + bed(20, 300) + view_cone(408, 131, dark=True, to=174, top=165, bottom=338)
          + desk(250, 236, dark=True) + chair(196, 190, dark=True) + watch_zone(196, dark=True)
          + device(390, 172, ("",), screen_on=False, led=10, dark=True, cam_dir="left")
          + bubble(150, 52, 228, ["desk_log.jsonl", "00:58 desk empty, light dark", "01:20 desk occupied, light on",
                                  "01:46 desk empty, light dark", "(a look every 10 s, 3 to agree)"], size=12, fill="#e8ecff"))
    # 3. morning: press, verdict on screen, Piper reads it, timeline saved
    p3 = (window(420, 70, night=False) + view_cone(408, 131, to=158, top=165, bottom=338)
          + desk(250, 236) + chair(180, 190) + watch_zone(180)
          + device(390, 172, ("+77 MIN", "last 1:46am"), "late", cam_dir="left")
          + person_standing(330, 158, BLUE, reach=btn)
          + bubble(24, 56, 286, ['"You said bed by 12:30 a.m., but', 'you were at the desk until', '1:46 a.m., 77 minutes late."'],
                   tail="right")
          + f'<g transform="translate(18,206)"><rect width="132" height="54" rx="6" fill="#fff" stroke="{INK}" stroke-width="2"/>'
          + f'<rect x="10" y="14" width="40" height="12" fill="{BLUE}"/><rect x="50" y="14" width="18" height="12" fill="{ORANGE}"/>'
          + f'<rect x="88" y="14" width="22" height="12" fill="{ORANGE}"/><line x1="50" y1="8" x2="50" y2="32" stroke="{INK}" stroke-dasharray="3 2"/>'
          + text(10, 46, "night_timeline.png", 11, MUTED) + "</g>")
    sheet("Desk Curfew v2", "Revised storyboard: one button, one sentence, and the code keeps the facts", [
        panel(0, "1  BEFORE BED", ["Tap to push the bedtime 30 min later, hold to confirm.",
                                   "It says it back, then the screen goes dark."], p1),
        panel(1, "2  WHILE ASLEEP", ["Screen off, button LED breathes dimly. The camera",
                                     "watches only the chair (dashed), never the bed."], p2, night=True),
        panel(2, "3  WHEN AWAKE", ["Press the button. The verdict is on the screen, Piper",
                                   "reads one checked sentence, a timeline is saved."], p3),
    ], "storyboard_v2")


# ============================================================================ Verplank


def verplank():
    w, h = 1300, 640
    cells = [
        # (col, row, label, colour, rows)
        (0, 0, "IDEA", INK, ["A desk that tells you in the", "morning whether you kept the", "bedtime you promised."]),
        (1, 0, "METAPHOR", INK, ["A roommate who saw you still", "up at 2am, and says so", "kindly but plainly at breakfast."]),
        (2, 0, "MODEL", INK, ["The night is a list of desk", "states (occupied / empty, light", "on / dark). Facts come from code."]),
        (3, 0, "DISPLAY", INK, ["Night: screen off, LED breathes.", "Morning: '+77 MIN' on the PiTFT,", "one sentence aloud, a timeline."]),
        (0, 1, "ERROR", ORANGE, ["YOLO misses you for one look;", "the room goes dark; Qwen invents", "a time. Debounce, 'dark' state,", "and a sentence checker."]),
        (1, 1, "SCENARIO", INK, ["11:40pm: set 12:30am, go back to", "work. Leave 12:58, return 1:20,", "leave 1:46. 8:30am: press, hear", "'77 minutes late'."]),
        (2, 1, "TASK", INK, ["Before bed: set a time and leave.", "Morning: press once and listen.", "No ssh, no typing."]),
        (3, 1, "CONTROL", INK, ["One Qwiic Button: tap = +30 min,", "hold = OK, press in the morning", "= reveal. Enter key as backup."]),
    ]
    cw, ch, gx, gy, x0, y0 = 290, 200, 26, 60, 40, 110
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           '<rect width="100%" height="100%" fill="#ffffff"/>',
           text(40, 50, "Desk Curfew: Verplank diagram", 26, INK, weight="bold"),
           text(40, 80, "How do you feel (idea, metaphor)?  How do you know (model, display)?  How do you do (task, control)?", 15, MUTED)]
    for col, row, label, color, rows in cells:
        x, y = x0 + col * (cw + gx), y0 + row * (ch + gy)
        out.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="14" fill="{PAPER}" stroke="{color}" stroke-width="2.5"/>')
        out.append(f'<rect x="{x + 14}" y="{y + 14}" width="{len(label) * 11.6 + 26}" height="30" rx="15" fill="{color}"/>')
        out.append(text(x + 26, y + 35, label, 15, "#ffffff", weight="bold"))
        out.append(lines(x + 18, y + 80, rows, size=15, gap=24))
    # arrows between cells, top row left to right, bottom row right to left (the Verplank loop)
    for col in range(3):
        x = x0 + (col + 1) * cw + col * gx
        out.append(f'<path d="M{x + 3} {y0 + ch / 2} L{x + gx - 5} {y0 + ch / 2}" stroke="{MUTED}" stroke-width="2.5" marker-end="url(#a)"/>')
        y = y0 + ch + gy + ch / 2
        out.append(f'<path d="M{x + gx - 3} {y} L{x + 5} {y}" stroke="{MUTED}" stroke-width="2.5" marker-end="url(#a)"/>')
    xr = x0 + 4 * cw + 3 * gx
    out.append(f'<path d="M{xr - cw / 2} {y0 + ch + 3} L{xr - cw / 2} {y0 + ch + gy - 5}" stroke="{MUTED}" stroke-width="2.5" marker-end="url(#a)"/>')
    out.insert(1, f'<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
                  f'<path d="M0 0 L10 5 L0 10 z" fill="{MUTED}"/></marker></defs>')
    out.append(text(40, h - 24, "Error is the box that changed most from v1 to v2.", 15, ORANGE, weight="bold"))
    out.append("</svg>")
    save("".join(out), "verplank")


if __name__ == "__main__":
    v1()
    v2()
    verplank()
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("*.png"))))
