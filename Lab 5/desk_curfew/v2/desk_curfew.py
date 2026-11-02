"""
Desk Curfew v2: the whole night in one script.

  BEFORE BED  The screen offers a bedtime ("BED BY 12:00am"). Tap the button to push it
              30 minutes later, hold it to confirm (or just wait 15 s). The device says it
              back, the screen goes dark and the button LED breathes dimly all night.
  ASLEEP      Every 10 s the camera looks at the desk chair. YOLO finds people, the
              interpreter turns that into "occupied/empty" and "light on/dark", and a state
              only changes after 3 looks in a row agree (no more flicker).
  AWAKE       Press the button. The code works out the facts (last time at the desk, minutes
              past curfew, returns after curfew), Qwen turns them into one or two sentences,
              and a checker throws the sentence out if it states a number that is not a fact.
              The verdict goes on the screen, Piper reads it aloud, and a timeline PNG is saved.

Run it from the Lab 5 folder, inside tmux:

    python desk_curfew/v2/desk_curfew.py                 # a real night
    python desk_curfew/v2/desk_curfew.py --demo          # a compressed night for testing and the video:
                                                         #   looks every 3 s, curfew dial in 1-minute steps
    python desk_curfew/v2/desk_curfew.py --check         # aim the camera: print what it sees for 30 s
    python desk_curfew/v2/desk_curfew.py --curfew 00:30  # skip the dial
    python desk_curfew/v2/desk_curfew.py --replay desk_curfew/nights/<folder>   # redo a morning from a saved night
                                                         #   (writes morning_report_replay.*, keeps the original)

Each night goes in desk_curfew/nights/<date-time>/: desk_log.jsonl, meta.json,
morning_report.json/.txt, night_timeline.png, and snaps/ (delete those after the demo).
Ctrl-C during the night also ends it and runs the morning.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys
import time

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import core                                                      # noqa: E402
from hardware import LAB5, Button, Voice, ask_qwen, make_screen  # noqa: E402

NIGHTS = LAB5 / "desk_curfew" / "nights"

# One knob set for a real night, one for a compressed demo night (same logic, shorter clocks).
PRESETS = {
    "night": dict(interval=10, need=3, merge_gap=180, morning_grace=180, on_time_grace=300,
                  step=30, lead=30, dial_span=240, morning_hours=5, beat=300, dial_timeout=15, quiet_start=60),
    "demo": dict(interval=3, need=2, merge_gap=30, morning_grace=60, on_time_grace=0,
                 step=1, lead=2, dial_span=15, morning_hours=None, beat=60, dial_timeout=15, quiet_start=10),
}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--demo", action="store_true", help="compressed night: fast looks, 1-minute curfew steps")
    p.add_argument("--check", action="store_true", help="aim the camera: print readings for 30 s, save aim.jpg")
    p.add_argument("--replay", metavar="NIGHT_DIR", help="re-run the morning on a saved night")
    p.add_argument("--curfew", metavar="HH:MM", help="set the curfew directly instead of using the dial")
    p.add_argument("--interval", type=float, help="seconds between looks (default 10, demo 3)")
    p.add_argument("--conf", type=float, default=0.4, help="YOLO confidence threshold")
    p.add_argument("--min-height", type=float, default=0.30,
                   help="a person counts as AT the desk only if their box is this tall (fraction of frame); "
                        "people far behind you, walking past, are ignored")
    p.add_argument("--dark", type=float, default=40, help="mean brightness (0-255) below which the desk is 'dark'")
    p.add_argument("--model", default="qwen3.5:0.8b", help="Ollama model for the morning sentence")
    p.add_argument("--button", default="auto", choices=["auto", "qwiic", "pitft", "keyboard"])
    p.add_argument("--screen", default="auto", choices=["auto", "pitft", "oled", "none"])
    p.add_argument("--no-voice", action="store_true")
    p.add_argument("--no-snaps", action="store_true", help="do not save a photo when someone sits down")
    p.add_argument("--say", action="store_true", help="with --replay: also show it on the screen and speak it")
    return p.parse_args()


# ============================================================================ the eyes


class Eyes:
    """Camera + YOLO + the desk interpreter."""

    def __init__(self, args):
        import cv2
        from ultralytics import YOLO
        self.cv2, self.args = cv2, args
        weights = LAB5 / "yolo26n_ncnn_model"
        if not weights.exists():
            sys.exit(f"no {weights.name} in {LAB5}: run the export step from Part A first")
        self.model = YOLO(str(weights))
        self.cap, self.fails = None, 0
        self.open()

    def open(self):
        if self.cap is not None:
            self.cap.release()
        self.cap = self.cv2.VideoCapture(0)
        self.cap.set(self.cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(self.cv2.CAP_PROP_FRAME_HEIGHT, 480)
        if not self.cap.isOpened():
            sys.exit("no webcam found: is it plugged in?")

    def frame(self):
        for _ in range(4):                      # skip stale buffered frames, as overnight.py does
            self.cap.grab()
        ok, frame = self.cap.read()
        if not ok:
            self.fails += 1
            if self.fails >= 3:                 # the webcam dropped out: reopen it
                self.open()
                self.fails = 0
            return None
        self.fails = 0
        return frame

    def look(self, frame):
        """The interpreter. Returns (desk, light, details).

        desk   'occupied' if a person box is tall enough to be someone sitting in front of the
               camera, 'empty' otherwise. A short box is someone across the room, not at the desk.
        light  'on' or 'dark' from the mean brightness. In the dark the camera cannot see, so
               'dark' is reported as its own state rather than silently treated as 'empty'.
        """
        h = frame.shape[0]
        r = self.model.predict(frame, imgsz=320, conf=self.args.conf, classes=[0], verbose=False)[0]
        heights = [(b.xyxy[0][3] - b.xyxy[0][1]).item() / h for b in r.boxes]
        confs = [float(b.conf) for b in r.boxes]
        at_desk = [c for c, hh in zip(confs, heights) if hh >= self.args.min_height]
        gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        desk = "occupied" if at_desk else "empty"
        light = "on" if brightness >= self.args.dark else "dark"
        details = {"people": len(confs), "conf": round(max(confs, default=0), 2),
                   "tallest": round(max(heights, default=0), 2), "brightness": round(brightness)}
        return desk, light, details, r


def check(args):
    """Thirty seconds of raw readings so you can aim the camera and tune --min-height / --dark."""
    eyes = Eyes(args)
    print("looking for 30 s: sit at the desk, lean back, walk behind it, turn the light off...\n")
    end, last = time.time() + 30, None
    while time.time() < end:
        frame = eyes.frame()
        if frame is None:
            continue
        desk, light, d, r = eyes.look(frame)
        print(f"{dt.datetime.now():%H:%M:%S}  desk={desk:<8} light={light:<4}  people={d['people']} "
              f"conf={d['conf']:.2f} tallest_box={d['tallest']:.2f} brightness={d['brightness']}", flush=True)
        last = r
        time.sleep(1)
    if last is not None:
        eyes.cv2.imwrite(str(LAB5 / "desk_curfew" / "aim.jpg"), last.plot())
        print("\nsaved desk_curfew/aim.jpg (the last frame with YOLO's boxes)")
    print("tallest_box under --min-height (now %.2f) is ignored; brightness under --dark (now %.0f) is 'dark'."
          % (args.min_height, args.dark))


# ============================================================================ before bed


def bedtime(args, cfg, button, screen, voice):
    now = dt.datetime.now()
    if args.curfew:
        curfew = core.resolve_curfew(args.curfew, now)
    else:
        first = core.propose_curfew(now, cfg["step"], cfg["lead"])
        curfew = first
        tap, hold = button.hints()
        print(f"\nBEDTIME: {tap} = +{cfg['step']} min, {hold} = confirm (or wait {cfg['dial_timeout']} s)")
        while True:
            screen.show("BED BY", core.clock(curfew), f"{tap} +{cfg['step']}m  ·  {hold} = OK", "night")
            print(f"  bed by {core.clock(curfew)}?", flush=True)
            ev = button.wait(cfg["dial_timeout"])
            if ev == "short":
                curfew += dt.timedelta(minutes=cfg["step"])
                if curfew - first > dt.timedelta(minutes=cfg["dial_span"]):
                    curfew = first               # wrap around instead of running off to noon
                continue
            break                                # 'long' or no press for a while = confirm
    handoff = dt.datetime.now().replace(microsecond=0)
    print(f"\nGoodnight. Curfew {core.clock(curfew)}. Watching the desk.")
    screen.show("GOODNIGHT", core.clock(curfew), "watching the desk", "night")
    button.led(40)
    voice.say(core.spoken(f"Okay. Bed by {core.clock(curfew)}. Goodnight, I'll watch the desk."))
    time.sleep(3)
    screen.off()
    button.breathe()
    return handoff, curfew


# ============================================================================ asleep


def night(args, cfg, button, eyes, folder, handoff, curfew):
    folder.mkdir(parents=True, exist_ok=True)
    snaps = folder / "snaps"
    log = open(folder / "desk_log.jsonl", "a")

    def write(entry):
        log.write(json.dumps(entry) + "\n")
        log.flush()

    meta = {"version": 2, "handoff": core.ts(handoff), "curfew": core.ts(curfew), "demo": args.demo,
            "settings": {**cfg, "conf": args.conf, "min_height": args.min_height, "dark": args.dark}}
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    write({"t": core.ts(handoff), "event": "handoff", "curfew": core.ts(curfew)})

    desk_db, light_db = core.Debouncer(cfg["need"]), core.Debouncer(cfg["need"])
    looks, last_beat = 0, handoff
    quiet_until = time.time() + cfg["quiet_start"]       # ignore the button right after confirming
    next_look = time.time()
    print(f"night shift: a look every {cfg['interval']:g} s. Press the button (or Ctrl-C) in the morning.\n",
          flush=True)
    try:
        while True:
            wait = next_look - time.time()
            if wait > 0:
                ev = button.wait(min(wait, 0.5))
                if ev and time.time() > quiet_until:
                    break
                continue
            next_look = time.time() + cfg["interval"]
            frame = eyes.frame()
            if frame is None:
                continue
            now = dt.datetime.now().replace(microsecond=0)
            desk, light, d, _ = eyes.look(frame)
            looks += 1
            new_desk = desk_db.update(desk, now)
            new_light = light_db.update(light, now)
            if new_desk or new_light:
                # time the change from the first look that saw it, not the look that confirmed it
                t = min(x for x in (desk_db.since if new_desk else None,
                                    light_db.since if new_light else None) if x)
                write({"t": core.ts(t), "desk": desk_db.state, "light": light_db.state, **d})
                print(f"{t:%H:%M:%S}  desk {desk_db.state:<8} light {light_db.state:<4} "
                      f"(conf {d['conf']:.2f}, box {d['tallest']:.2f}, brightness {d['brightness']})", flush=True)
                if new_desk == "occupied" and not args.no_snaps:
                    snaps.mkdir(exist_ok=True)
                    eyes.cv2.imwrite(str(snaps / f"{now:%Y%m%d-%H%M%S}.jpg"), frame)
            if (now - last_beat).total_seconds() > cfg["beat"]:
                write({"t": core.ts(now), "alive": True, "looks": looks, "brightness": d["brightness"]})
                last_beat = now
    except KeyboardInterrupt:
        print("\n(Ctrl-C: ending the night)")
    reveal = dt.datetime.now().replace(microsecond=0)
    write({"t": core.ts(reveal), "event": "reveal", "looks": looks,
           "flickers_ignored": desk_db.suppressed + light_db.suppressed})
    meta.update({"reveal": core.ts(reveal), "looks": looks,
                 "flickers_ignored": {"desk": desk_db.suppressed, "light": light_db.suppressed}})
    (folder / "meta.json").write_text(json.dumps(meta, indent=2))
    log.close()
    return reveal


# ============================================================================ awake


def morning(args, folder, screen=None, voice=None, button=None, tag=""):
    """tag: suffix for the report files, so a --replay never overwrites the night's original report."""
    meta = json.loads((folder / "meta.json").read_text())
    cfg = meta["settings"]
    entries = core.read_log(folder / "desk_log.jsonl")
    handoff, curfew = core.parse_ts(meta["handoff"]), core.parse_ts(meta["curfew"])
    reveal = core.parse_ts(meta.get("reveal") or entries[-1]["t"])
    morning_after = curfew + dt.timedelta(hours=cfg["morning_hours"]) if cfg.get("morning_hours") else None

    if screen:
        screen.show("GOOD MORNING", "...", "reading the night", "info")
    if button:
        button.led(0)

    facts = core.compute_facts(
        core.desk_changes(entries), handoff, curfew, reveal,
        merge_gap=dt.timedelta(seconds=cfg["merge_gap"]),
        morning_grace=dt.timedelta(seconds=cfg["morning_grace"]),
        on_time_grace=dt.timedelta(seconds=cfg["on_time_grace"]),
        morning_after=morning_after,
        lights=core.light_changes(entries),
        gaps=core.watch_gaps(entries, dt.timedelta(seconds=3 * cfg["beat"])))

    report = {"facts": facts, "model": args.model, "qwen_answer": None, "qwen_seconds": None,
              "rejected_because": None, "source": "template",
              "looks": meta.get("looks"), "flickers_ignored": meta.get("flickers_ignored")}
    sentence = core.template(facts)
    try:
        print("asking Qwen to phrase the facts...", flush=True)
        answer, took = ask_qwen(core.prompt_for(facts), model=args.model)
        report.update(qwen_answer=answer, qwen_seconds=round(took, 1))
        reason = core.check_sentence(answer, facts)
        if reason:
            report["rejected_because"] = reason
        else:
            sentence, report["source"] = answer, "qwen"
    except requests.ConnectionError:
        report["rejected_because"] = "Qwen unavailable (is Ollama running? try: sudo systemctl start ollama)"
    except Exception as err:
        report["rejected_because"] = f"Qwen failed: {type(err).__name__}: {err}"
    report["sentence"] = sentence

    big, small, mood = core.headline(facts)
    report["screen"] = [big, small]
    (folder / f"morning_report{tag}.json").write_text(json.dumps(report, indent=2))

    lines = [
        f"DESK CURFEW  night of {handoff:%a %b %d}",
        f"watched {facts['watched_from']} to {facts['watched_until']}, curfew {facts['curfew_clock']}",
        f"screen:   {big}  /  {small}",
        f"sentence: {sentence}",
        f"          (from {report['source']}"
        + (f"; Qwen took {report['qwen_seconds']} s" if report["qwen_seconds"] else "")
        + (f"; rejected Qwen because: {report['rejected_because']}" if report["rejected_because"] else "")
        + ")",
    ]
    if report["qwen_answer"] and report["source"] != "qwen":
        lines.append(f"Qwen said: {report['qwen_answer']}")
    lines += [
        f"sessions at the desk: {facts['session_count']} (from {facts['raw_session_count']} before merging short breaks)",
        f"flickers ignored by the debouncer: {meta.get('flickers_ignored')}",
        f"looks taken: {meta.get('looks')}",
    ]
    text = "\n".join(lines)
    (folder / f"morning_report{tag}.txt").write_text(text + "\n")
    print("\n" + text)

    try:
        import timeline
        timeline.draw_v2(entries, facts, folder / "night_timeline.png", title=f"Desk Curfew, night of {handoff:%b %d}")
        print(f"\ntimeline: {folder / 'night_timeline.png'}")
    except Exception as err:
        print(f"(timeline not drawn: {err})")

    if screen:
        screen.show("GOOD MORNING", big, small, mood)
    if voice:
        voice.say(core.spoken(sentence))
    return report


# ============================================================================ main


def main():
    args = parse_args()
    if args.check:
        return check(args)
    if args.replay:
        folder = pathlib.Path(args.replay).resolve()
        screen = make_screen(args.screen) if args.say else None
        voice = Voice(not args.no_voice) if args.say else None
        return morning(args, folder, screen, voice, tag="_replay")

    cfg = dict(PRESETS["demo" if args.demo else "night"])
    if args.interval:
        cfg["interval"] = args.interval
    button, screen, voice = Button(args.button), make_screen(args.screen), Voice(not args.no_voice)
    print("loading YOLO...", flush=True)
    eyes = Eyes(args)
    try:
        handoff, curfew = bedtime(args, cfg, button, screen, voice)
    except KeyboardInterrupt:
        screen.off()
        sys.exit("\ncancelled before bed")
    folder = NIGHTS / (f"{handoff:%Y%m%d-%H%M}" + ("-demo" if args.demo else ""))
    night(args, cfg, button, eyes, folder, handoff, curfew)
    morning(args, folder, screen, voice, button)
    eyes.cap.release()
    print("\nThe screen keeps the verdict up. Ctrl-C to quit.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        screen.off()


if __name__ == "__main__":
    main()
