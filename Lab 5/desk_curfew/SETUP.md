# Desk Curfew: setup and run sheet

Everything happens on the Pi, inside `~/Interactive-Lab-Hub/Lab 5` with the Lab 5 venv active.
Total time: about 15 min of setup, then ~15 min for the v1 run and ~20 min for the v2 run.

## 0. What you need already

- Lab 5 Part A done: `.venv`, `yolo26n_ncnn_model/` exported, Ollama running with `qwen3.5:0.8b`
- The webcam, pointed at your desk chair (not at a bed)
- Optional, all with fallbacks: Qwiic Button (Lab 4), Mini PiTFT (Lab 2) **or** Qwiic OLED (Lab 4), speaker + Piper (Lab 3)

## 1. Get the code onto the Pi

If it is pushed to your fork:

```bash
cd ~/Interactive-Lab-Hub && git pull
```

Otherwise copy the `desk_curfew` folder from your laptop:

```bash
scp -r desk_curfew pi@<your-pi>.local:"~/Interactive-Lab-Hub/Lab 5/"
```

## 2. Install the extras

```bash
cd ~/Interactive-Lab-Hub/Lab\ 5
source .venv/bin/activate
pip install -r desk_curfew/requirements-curfew.txt
python desk_curfew/tests/test_core.py          # the logic tests: every line should say ok
```

If `lgpio` fails to build: `sudo apt install -y swig liblgpio-dev` and retry. If it still fails, skip
the screen; the device runs with the terminal and the Enter key.

## 3. Check the parts

```bash
i2cdetect -y 1                 # Qwiic Button = 6f, OLED = 3c
sudo systemctl status ollama   # should be active (running)
ls "../Lab 3/voices"           # should contain en_US-lessac-medium.onnx
```

No voice file? Download it once with the Lab 3 venv:

```bash
"../Lab 3/.venv/bin/python" -m piper.download_voices en_US-lessac-medium --data-dir "../Lab 3/voices"
```

Desk Curfew finds Piper in the Lab 3 venv by itself. You do not need to install it into Lab 5.

## 4. Aim the camera (2 min)

```bash
python desk_curfew/v2/desk_curfew.py --check
```

For 30 s it prints `desk=occupied/empty light=on/dark tallest_box=… brightness=…` once a second.
Sit down, lean back, stand behind the chair, turn the lamp off. Then look at `desk_curfew/aim.jpg`.

- Sitting should give `tallest_box` around 0.5 or more. Someone walking past at the back should be below 0.30.
  If not, pass `--min-height 0.4` (or whatever splits them) to every v2 command below.
- With the lamp off, `brightness` should drop under 40. If your webcam brightens the dark a lot, use `--dark 60`.

**Screenshot this output for the README (Part H).**

---

## 5. Run v1: the first prototype (~15 min)

Start screen recording or film the screen with your phone. Two terminals (or two tmux windows):

```bash
rm -f night_log.jsonl                                  # start clean
python desk_curfew/v1/bedtime_v1.py +3                 # curfew 3 minutes from now
tmux new -s night
python overnight.py                                    # the class script, unchanged
```

Then act out the **same night** you will use for v2, so the two runs are comparable:

| minute | do this |
|---|---|
| 0 to 6 | sit and work (the curfew passes at minute 3) |
| 6 to 9 | leave the room |
| 9 to 12 | come back and sit down again (a "return after curfew") |
| 12 | stand up, turn the desk lamp off, leave |
| 15 | come back |

At minute 15: `Ctrl-C` in the tmux window, then

```bash
python desk_curfew/v1/morning_v1.py --check
```

It prints Qwen's answer and, under it, the true answer worked out in code from the same log.
Everything is saved in `desk_curfew/v1/results/<time>/` (log, prompt, answer, check, `night_timeline_v1.png`).
**Screenshot the terminal.** This is the evidence for "what v1 got wrong".

## 6. Run v2: the revised device (~20 min)

```bash
tmux new -s night2
python desk_curfew/v2/desk_curfew.py --demo
```

1. **Before bed.** The screen shows `BED BY <time>` about 2 minutes ahead. Tap the button to add a minute,
   hold it for 1 s to confirm (keyboard: Enter = tap, `ok` + Enter = hold). It says the time back, the screen
   goes dark, and the button LED starts to breathe. **Film this, it is the "before" video.**
2. **While asleep.** Act out the same night as in the table above.
3. **When awake.** Walk up and press the button within a minute or so. The screen shows the verdict
   (`+8 MIN` / `ON TIME`), Piper reads one sentence, and the terminal prints the report. **Film this.**

Everything is saved in `desk_curfew/nights/<date-time>-demo/`:
`desk_log.jsonl`, `meta.json`, `morning_report.txt/.json`, `night_timeline.png`, `snaps/`.

Try the morning again with the other model, without re-running the night:

```bash
python desk_curfew/v2/desk_curfew.py --replay desk_curfew/nights/<folder> --model qwen3:0.6b
```

## 7. Optional: a real night

If you have the time before the deadline, run it for real and use that log in the README:

```bash
tmux new -s night3
python desk_curfew/v2/desk_curfew.py           # real settings: a look every 10 s, 30-minute dial
```

Detach with `Ctrl-b d`; reattach in the morning with `tmux attach -t night3` and press the button.

## 8. What goes in the README

The README has `TODO` markers where your own material goes. Search for `TODO` and fill each one:

| TODO | from |
|---|---|
| Part A screenshot | `ollama list` |
| Part B screenshots + 3 failure cases | `yolo_person.py` runs |
| Part C screenshot | `hand_pose.py` |
| Part D table | three `ask_qwen.py` questions with timings |
| Part E output | `yolo_to_qwen.py` run |
| Feedback on storyboard | what classmates said |
| Part H screenshots | `--check` output, v2 night terminal |
| v1 vs v2 results table | step 5 and step 6 terminals |
| timeline images | copy `night_timeline_v1.png` and `night_timeline.png` into `desk_curfew/media/` |
| videos | before / morning clips, and one short whole-system video |

## 9. Afterwards

- Delete `desk_curfew/nights/*/snaps/` and `snaps/` (photos of you) before pushing. The logs are fine to keep.
- `git add "Lab 5" && git commit -m "Lab 5: Desk Curfew" && git push`

## Troubleshooting

| symptom | fix |
|---|---|
| `no yolo26n_ncnn_model` | run the export from Part A in the Lab 5 folder |
| `Qwen unavailable` in the report | `sudo systemctl start ollama`; the device still works, it uses its own sentence |
| button does nothing | `i2cdetect -y 1` should show `6f`; run with `--button keyboard` meanwhile |
| no voice | check `aplay -l` and the voice file; run with `--no-voice` meanwhile |
| UnicodeEncodeError from ultralytics | the locale fix in Part A |
| desk keeps flipping occupied/empty | raise `--min-height` or lower `--conf` after looking at `--check` |
