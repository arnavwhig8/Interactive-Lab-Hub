"""
Desk Curfew v1, step 3 of 3: ask Qwen whether you went to bed on time.

v1 trusts the language model with everything: it gets overnight.py's raw log and the curfew,
and has to work out by itself when you left, how late that was and how often you came back.

    python desk_curfew/v1/morning_v1.py              # ask Qwen
    python desk_curfew/v1/morning_v1.py --check      # also work out the true answer in code and compare
    python desk_curfew/v1/morning_v1.py --model qwen3:0.6b

Saves everything in desk_curfew/v1/results/<date-time>/ (the night's log, the prompt, Qwen's answer,
the check and a timeline) so the README can show what v1 got wrong.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import core                                   # noqa: E402
from hardware import LAB5, ask_qwen           # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent

p = argparse.ArgumentParser()
p.add_argument("--log", default=str(LAB5 / "night_log.jsonl"))
p.add_argument("--model", default="qwen3.5:0.8b")
p.add_argument("--check", action="store_true", help="compare Qwen's answer with the facts worked out in code")
args = p.parse_args()

if not (HERE / "curfew.json").exists():
    sys.exit("no curfew set: run desk_curfew/v1/bedtime_v1.py HH:MM first")
c = json.loads((HERE / "curfew.json").read_text())
set_at, curfew = core.parse_ts(c["set_at"]), core.parse_ts(c["curfew"])
entries = [e for e in core.read_log(args.log) if core.parse_ts(e["t"]) >= set_at]
readings = [e for e in entries if "reading" in e]
if not readings:
    sys.exit(f"no readings in {args.log} after {set_at:%H:%M}: did overnight.py run?")
reveal = dt.datetime.now().replace(microsecond=0)

digest = "\n".join(f'{e["t"][11:19]} {e["reading"]}' for e in readings[-300:])
prompt = f"""You are a desk device. Last night at {set_at:%H:%M} the person said they would be in bed by {curfew:%H:%M}.
A camera pointed at their desk chair logged what it saw, one line per change ("nobody" means the chair was empty):

{digest}

Did they go to bed on time? Say when they were last at the desk, how many minutes past {curfew:%H:%M} that was,
and how many times they came back to the desk after {curfew:%H:%M}. At most three sentences."""

print(f"{len(readings)} readings from {readings[0]['t'][11:16]} to {readings[-1]['t'][11:16]}, "
      f"curfew {curfew:%H:%M}\nasking Qwen ({args.model})...", flush=True)
try:
    answer, took = ask_qwen(prompt, model=args.model, max_tokens=200)
except Exception as err:
    answer, took = f"(Qwen failed: {err})", 0.0
print(f"\nQwen ({took:.1f} s):\n{answer}")

run = HERE / "results" / f"{reveal:%Y%m%d-%H%M}"
run.mkdir(parents=True, exist_ok=True)
with open(run / "night_log.jsonl", "w") as f:
    f.writelines(json.dumps(e) + "\n" for e in entries)
(run / "prompt.txt").write_text(prompt + "\n")
report = [f"curfew {curfew:%H:%M}, set at {set_at:%H:%M}, morning at {reveal:%H:%M}",
          f"Qwen ({args.model}, {took:.1f} s): {answer}"]

if args.check:
    changes = core.stock_changes(entries)
    raw = core.compute_facts(changes, set_at, curfew, reveal, merge_gap=dt.timedelta(0),
                             morning_grace=dt.timedelta(0), on_time_grace=dt.timedelta(0))
    merged = core.compute_facts(changes, set_at, curfew, reveal, merge_gap=dt.timedelta(minutes=1),
                                morning_grace=dt.timedelta(0), on_time_grace=dt.timedelta(0))
    check = [
        "",
        "CHECK (worked out in code from the same log):",
        f"  last at the desk:          {raw['last_at_desk_clock']}",
        f"  minutes past curfew:       {raw['minutes_late']}" + (" (left early)" if raw["verdict"] != "late" else ""),
        f"  'returns' after curfew:    {raw['returns_after_curfew']} counting every flicker, "
        f"{merged['returns_after_curfew']} if gaps under 1 min are ignored",
        f"  separate visits in log:    {raw['raw_session_count']} raw, {merged['session_count']} merged",
        f"  log lines (changes):       {len(readings)}",
    ]
    print("\n".join(check))
    report += check
    try:
        import timeline
        timeline.draw_v1(changes, curfew, set_at, reveal, run / "night_timeline_v1.png")
        print(f"\ntimeline: {run / 'night_timeline_v1.png'}")
    except Exception as err:
        print(f"(timeline not drawn: {err})")

(run / "morning_v1_report.txt").write_text("\n".join(report) + "\n")
print(f"\nsaved in {run.relative_to(LAB5)}/")
