"""
Desk Curfew v1, step 1 of 3: tell the device your curfew.

v1 is the first prototype: the smallest change to the class pipeline that could work.
  1. bedtime_v1.py   type your curfew over ssh            (this file)
  2. overnight.py    the class's night shift, unchanged    (python overnight.py, in tmux)
  3. morning_v1.py   hand the raw log to Qwen and ask "did I go to bed on time?"

    python desk_curfew/v1/bedtime_v1.py 00:30          # a real night
    python desk_curfew/v1/bedtime_v1.py +3             # a demo night: curfew 3 minutes from now
    python desk_curfew/v1/bedtime_v1.py 00:30 --screen none
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import core                                   # noqa: E402
from hardware import LAB5, make_screen        # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("curfew", help="HH:MM, 24-hour (00:30 = half past midnight), or +N for N minutes from now")
p.add_argument("--screen", default="auto", choices=["auto", "pitft", "oled", "none"])
args = p.parse_args()

now = dt.datetime.now().replace(microsecond=0)
if args.curfew.startswith("+"):
    curfew = (now + dt.timedelta(minutes=int(args.curfew[1:]))).replace(second=0)
else:
    curfew = core.resolve_curfew(args.curfew, now)
here = pathlib.Path(__file__).resolve().parent
(here / "curfew.json").write_text(json.dumps({"set_at": core.ts(now), "curfew": core.ts(curfew)}, indent=2))

old = LAB5 / "night_log.jsonl"
if old.exists():
    print(f"note: {old.name} already has {sum(1 for _ in open(old))} lines from earlier runs; "
          "morning_v1.py only reads the lines written after now.")

screen = make_screen(args.screen)
screen.show("BED BY", core.clock(curfew), "start overnight.py", "night")
print(f"\nGot it: bed by {core.clock(curfew)}. Now start the night shift:\n"
      f"    tmux new -s night\n    python overnight.py\n"
      f"In the morning: Ctrl-C, then  python desk_curfew/v1/morning_v1.py")
