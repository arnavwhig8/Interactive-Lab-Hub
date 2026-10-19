"""
Tipsy Tulip - Lab 4 Feast Automata
Arnav Whig (aw966)

A shot-glass stand with a paper flower that gets "drunk" along with you.

  glass on stand -> lift it, take the shot, put it back -> distance sensor counts 1 shot
  -> servo tips the flower a little further (and it starts to sway)
  -> the screen shows the count and whether you should drink or wait
  -> at MAX_SHOTS the flower flops over, the screen says CUT OFF, the button LED blinks
  -> press the button to sober the flower back up

Hardware
  - SparkFun Pi Servo pHAT, servo on channel 0 (pHAT powered by its own USB-C)
  - SparkFun Qwiic Proximity Sensor (VCNL4040) under the glass, facing up
  - SparkFun Qwiic Button (reset)
  - Screen (optional): Qwiic OLED 128x32 on the Qwiic chain, OR the Mini PiTFT on the
    GPIO header (then the Servo pHAT connects by Qwiic cable instead of stacking)

Usage
  python tipsy_tulip.py                 # calibrate with the button, then run
  python tipsy_tulip.py --setup         # nudge the flower to set its upright + flopped positions
  python tipsy_tulip.py --aim           # hold the servo upright so you can attach the flower
  python tipsy_tulip.py --threshold 40  # skip calibration and use a known threshold
  python tipsy_tulip.py --debug         # also print live sensor readings
  python tipsy_tulip.py --screen pitft  # force a screen: auto | oled | pitft | none
"""

import argparse
import json
import math
import os
import sys
import time

import pi_servo_hat
import qwiic_button
import qwiic_proximity

# ----------------------------- settings ---------------------------------
SERVO_CH = 0
UPRIGHT_ANGLE = 15        # flower standing straight up (sober)
FLOPPED_ANGLE = 105       # flower flopped over (done). Keep both within 0-120.
MAX_SHOTS = 4             # shots before the flower flops
PACE_SECONDS = 60         # wait this long between shots (60 s for the demo; ~15 min in real life)
LEAN_FRACTION = 0.55      # how far it leans (of the full travel) on the last shot before flopping
SWAY_MAX_DEG = 6          # how much it sways when tipsy
MIN_LIFT_SECONDS = 1.0    # glass must be off the stand at least this long to count as a shot
CONFIRM_SAMPLES = 3       # readings in a row needed before we believe the glass moved
LOOP_DELAY = 0.04         # seconds between sensor readings
# -------------------------------------------------------------------------

SAFE_MIN, SAFE_MAX = -30, 130   # servo limits (about 0.7-2.4 ms pulses)
ANGLES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tulip_angles.json")


def set_angles(upright, flopped):
    global UPRIGHT_ANGLE, FLOPPED_ANGLE, DIRECTION, TRAVEL
    UPRIGHT_ANGLE, FLOPPED_ANGLE = upright, flopped
    DIRECTION = 1 if FLOPPED_ANGLE >= UPRIGHT_ANGLE else -1
    TRAVEL = abs(FLOPPED_ANGLE - UPRIGHT_ANGLE)


def load_angles():
    """Use the angles saved by --setup, if there are any."""
    try:
        with open(ANGLES_FILE) as f:
            saved = json.load(f)
        set_angles(saved["upright"], saved["flopped"])
        print(f"Using saved angles: upright {UPRIGHT_ANGLE}, flopped {FLOPPED_ANGLE}")
    except (FileNotFoundError, KeyError, ValueError):
        set_angles(UPRIGHT_ANGLE, FLOPPED_ANGLE)


def clamp(angle):
    return max(SAFE_MIN, min(SAFE_MAX, angle))


class Tulip:
    """The servo-driven flower and its moods."""

    def __init__(self, servo):
        self.servo = servo
        self.angle = UPRIGHT_ANGLE
        self.servo.move_servo_position(SERVO_CH, self.angle)

    def _set(self, angle):
        self.angle = clamp(angle)
        self.servo.move_servo_position(SERVO_CH, round(self.angle))

    def glide(self, target, step=1.0, delay=0.012):
        """Move smoothly to target angle."""
        target = clamp(target)
        while abs(target - self.angle) > step:
            self._set(self.angle + (step if target > self.angle else -step))
            time.sleep(delay)
        self._set(target)

    def lean_for(self, shots):
        """Resting angle for a given shot count (before the flop)."""
        fraction = LEAN_FRACTION * shots / max(1, MAX_SHOTS - 1)
        return UPRIGHT_ANGLE + DIRECTION * TRAVEL * fraction

    def tipsy_lean(self, shots):
        """Lurch past the new lean, wobble back, settle."""
        target = self.lean_for(shots)
        self.glide(target + DIRECTION * 8, step=2, delay=0.01)
        self.glide(target - DIRECTION * 4, step=1, delay=0.015)
        self.glide(target, step=1, delay=0.02)

    def flop(self):
        """Fall over fast, bounce once, lie still."""
        self.glide(FLOPPED_ANGLE, step=4, delay=0.005)
        self.glide(FLOPPED_ANGLE - DIRECTION * 12, step=2, delay=0.01)
        self.glide(FLOPPED_ANGLE, step=3, delay=0.008)

    def twitch(self):
        """A feeble twitch when you keep drinking after the flop."""
        self.glide(FLOPPED_ANGLE - DIRECTION * 6, step=2, delay=0.01)
        self.glide(FLOPPED_ANGLE, step=2, delay=0.01)

    def sober_up(self):
        """Slowly stand back up and give a little shake."""
        self.glide(UPRIGHT_ANGLE, step=1, delay=0.02)
        for offset in (5, -5, 3, -3, 0):
            self.glide(UPRIGHT_ANGLE + offset, step=1, delay=0.01)

    def sway(self, shots, t):
        """Gentle, slightly irregular drunk sway around the current lean."""
        amplitude = SWAY_MAX_DEG * shots / max(1, MAX_SHOTS - 1)
        wobble = math.sin(t * 2 * math.pi / 2.2) + 0.35 * math.sin(t * 2 * math.pi / 0.8)
        self._set(self.lean_for(shots) + amplitude * wobble / 1.35)


def _font(ImageFont, name, size):
    for path in (f"/usr/share/fonts/truetype/dejavu/{name}", name):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


class NoScreen:
    """Used when no display is attached."""
    def show(self, line1, line2="", mood="info", shots=None):
        pass

    def clear(self):
        pass


class OledScreen:
    """Two-line status on the small 128x32 Qwiic OLED."""

    def __init__(self):
        import board
        import busio
        import adafruit_ssd1306
        from PIL import Image, ImageDraw, ImageFont
        self.oled = adafruit_ssd1306.SSD1306_I2C(128, 32, busio.I2C(board.SCL, board.SDA))
        self.Image, self.ImageDraw = Image, ImageDraw
        self.big = _font(ImageFont, "DejaVuSans-Bold.ttf", 15)
        self.small = _font(ImageFont, "DejaVuSans.ttf", 11)
        self.last = None

    def show(self, line1, line2="", mood="info", shots=None):
        if (line1, line2) == self.last:
            return
        self.last = (line1, line2)
        img = self.Image.new("1", (128, 32))
        draw = self.ImageDraw.Draw(img)
        draw.text((0, -1), line1, font=self.big, fill=255)
        draw.text((0, 18), line2, font=self.small, fill=255)
        self.oled.image(img)
        self.oled.show()

    def clear(self):
        self.oled.fill(0)
        self.oled.show()


class PitftScreen:
    """Big colour status on the Mini PiTFT (240x135), same setup as Lab 2."""

    COLORS = {
        "ready": (0, 170, 70), "ok": (0, 170, 70), "wait": (235, 150, 0),
        "lifted": (40, 120, 220), "warn": (235, 90, 20), "cutoff": (200, 25, 25),
        "info": (70, 70, 70),
    }

    def __init__(self):
        import board
        import digitalio
        import adafruit_rgb_display.st7789 as st7789
        from PIL import Image, ImageDraw, ImageFont
        self.disp = st7789.ST7789(
            board.SPI(),
            cs=digitalio.DigitalInOut(board.D5),
            dc=digitalio.DigitalInOut(board.D25),
            rst=None,
            baudrate=64000000,
            width=135,
            height=240,
            x_offset=53,
            y_offset=40,
        )
        self.backlight = digitalio.DigitalInOut(board.D22)
        self.backlight.switch_to_output()
        self.backlight.value = True
        self.Image, self.ImageDraw, self.ImageFont = Image, ImageDraw, ImageFont
        self.W, self.H = 240, 135
        self.last = None

    def _fit(self, draw, text, max_width, size, bold=True):
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        while size > 10:
            font = _font(self.ImageFont, name, size)
            if draw.textlength(text, font=font) <= max_width:
                return font
            size -= 2
        return _font(self.ImageFont, name, 10)

    def _centered(self, draw, y, text, font, fill):
        draw.text(((self.W - draw.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)

    def show(self, line1, line2="", mood="info", shots=None):
        if (line1, line2, mood) == self.last:
            return
        self.last = (line1, line2, mood)
        img = self.Image.new("RGB", (self.W, self.H), (0, 0, 0))
        draw = self.ImageDraw.Draw(img)
        color = self.COLORS.get(mood, self.COLORS["info"])
        if shots is None:  # plain message (start-up / calibration)
            self._centered(draw, 22, line1, self._fit(draw, line1, 228, 30), (255, 255, 255))
            self._centered(draw, 78, line2, self._fit(draw, line2, 228, 22, bold=False), (200, 200, 200))
        else:
            draw.text((8, 4), "TIPSY TULIP", font=_font(self.ImageFont, "DejaVuSans-Bold.ttf", 13), fill=(150, 150, 150))
            # one little glass per allowed shot, filled in as you drink
            for i in range(MAX_SHOTS):
                x = self.W - 14 - (MAX_SHOTS - 1 - i) * 16
                box = (x - 5, 5, x + 5, 19)
                if i < shots:
                    draw.rectangle(box, fill=color)
                else:
                    draw.rectangle(box, outline=(120, 120, 120))
            big = "CUT OFF" if mood == "cutoff" else f"{shots}/{MAX_SHOTS}"
            self._centered(draw, 20, big, self._fit(draw, big, 228, 58),
                           color if mood == "cutoff" else (255, 255, 255))
            draw.rectangle((0, self.H - 40, self.W, self.H), fill=color)
            self._centered(draw, self.H - 33, line2, self._fit(draw, line2, 228, 24), (255, 255, 255))
        self.disp.image(img, 90)

    def clear(self):
        self.disp.image(self.Image.new("RGB", (self.W, self.H)), 90)
        self.backlight.value = False


def make_screen(choice="auto"):
    """auto = use the Qwiic OLED if one is plugged in, otherwise the Mini PiTFT."""
    order = {"auto": [OledScreen, PitftScreen], "oled": [OledScreen],
             "pitft": [PitftScreen], "none": []}[choice]
    for kind in order:
        try:
            screen = kind()
            print(f"Screen: {kind.__name__.replace('Screen', '')}")
            return screen
        except ImportError as err:
            print(f"({kind.__name__}: missing library '{err.name}'. "
                  "Run: pip install pillow adafruit-circuitpython-rgb-display)")
        except Exception as err:
            if choice != "auto":
                print(f"({kind.__name__} didn't start: {err})")
    print("Screen: none")
    return NoScreen()


def status(shots, glass_on, last_shot_at, now, flash, flash_until):
    """What the screen should say right now: (line1, line2, mood)."""
    if shots >= MAX_SHOTS:
        line1 = f"CUT OFF ({shots})"
        line2 = f"STOP! That's {shots}" if shots > MAX_SHOTS else "No more. Press btn"
        mood = "cutoff"
    else:
        line1 = f"Shots: {shots}/{MAX_SHOTS}"
        wait = PACE_SECONDS - (now - last_shot_at) if last_shot_at is not None else 0
        if not glass_on:
            line2, mood = "Bottoms up!", "lifted"
        elif wait > 0:
            line2, mood = f"Wait {int(wait) // 60}:{int(wait) % 60:02d} - water!", "wait"
        elif shots == 0:
            line2, mood = "Ready - cheers!", "ready"
        elif shots == MAX_SHOTS - 1:
            line2, mood = "OK... last one!", "ok"
        else:
            line2, mood = "OK to drink", "ok"
    if now < flash_until:
        line2 = flash
        if mood != "cutoff":
            mood = "warn" if "fast" in flash.lower() else "ready"
    return line1, line2, mood


def average_reading(sensor, samples=20):
    values = []
    for _ in range(samples):
        values.append(sensor.get_proximity())
        time.sleep(0.03)
    return sum(values) / len(values)


def wait_for_press(button):
    while not button.is_button_pressed():
        time.sleep(0.02)
    while button.is_button_pressed():
        time.sleep(0.02)


def calibrate(sensor, button, screen):
    print("\nCalibration")
    print("  1. Take the glass OFF the stand, then press the button.")
    screen.show("Calibrate 1/2", "Glass OFF, press btn")
    wait_for_press(button)
    empty = average_reading(sensor)
    print(f"     empty reading: {empty:.0f}")

    print("  2. Put the glass ON the stand, then press the button.")
    screen.show("Calibrate 2/2", "Glass ON, press btn")
    wait_for_press(button)
    full = average_reading(sensor)
    print(f"     glass reading: {full:.0f}")

    gap = full - empty
    if gap < 5:
        screen.show("Can't see glass", "Add white tape")
        print("\nThe sensor can barely see the glass (difference of only "
              f"{gap:.0f}).\nStick a small piece of white paper or tape on the "
              "bottom of the glass, make sure it sits right over the sensor, "
              "and run the script again.")
        sys.exit(1)

    on_threshold = empty + 0.6 * gap
    off_threshold = empty + 0.4 * gap
    print(f"  Threshold set to {on_threshold:.0f}. "
          f"(Next time you can skip this with --threshold {on_threshold:.0f})")
    return on_threshold, off_threshold


def setup_hardware():
    sensor = qwiic_proximity.QwiicProximity()
    if not sensor.connected:
        sys.exit("Distance sensor not found. Check the Qwiic cable (i2cdetect should show 60).")
    sensor.begin()

    button = qwiic_button.QwiicButton()
    if not button.begin():
        sys.exit("Qwiic Button not found. Check the Qwiic cable (i2cdetect should show 6f).")
    button.LED_off()

    servo = pi_servo_hat.PiServoHat()
    servo.restart()
    return sensor, button, servo


def aim_mode(servo):
    tulip = Tulip(servo)
    print(f"Servo is at the UPRIGHT position ({UPRIGHT_ANGLE} deg).")
    print("Attach the horn + flower so it points straight up.")
    input("Press Enter to preview the flop...")
    tulip.flop()
    input("That's the flopped position. Press Enter to stand it back up...")
    tulip.sober_up()
    print("Done. If the position or direction is off, run: python tipsy_tulip.py --setup")


def pick_angle(tulip, prompt):
    """Let the user nudge the servo until the flower is where they want it."""
    while True:
        cmd = input(f"  [now {round(tulip.angle):>4}] {prompt}: ").strip()
        if cmd == "":
            return round(tulip.angle)
        step = {"+": 5, "-": -5, "++": 20, "--": -20}.get(cmd)
        try:
            target = tulip.angle + step if step is not None else float(cmd)
        except ValueError:
            print("  Type + or - (5 deg), ++ or -- (20 deg), a number, or just Enter.")
            continue
        if clamp(target) != target:
            print(f"  That's past the servo's limit ({SAFE_MIN} to {SAFE_MAX}) - not moving.")
            continue
        tulip.glide(target, step=1, delay=0.01)


def setup_mode(servo):
    tulip = Tulip(servo)
    print("\nFlower setup - nudge the flower into place, then press Enter.")
    print("  +  / -   move 5 degrees      ++ / --   move 20 degrees      or type an angle\n")
    print("Step 1: make the flower stand STRAIGHT UP (sober).")
    upright = pick_angle(tulip, "straight up?")
    print("\nStep 2: move it to where it should LIE when it flops -")
    print("        away from the glass (and your laptop). Roughly 90 degrees from upright.")
    flopped = pick_angle(tulip, "flopped?")
    if abs(flopped - upright) < 30:
        print("\nThat's a very small movement. If you can't get a bigger flop in the right")
        print("direction, pull the horn off, turn it about a quarter turn, and run --setup again.")
    set_angles(upright, flopped)
    with open(ANGLES_FILE, "w") as f:
        json.dump({"upright": upright, "flopped": flopped}, f)
    print(f"\nSaved (upright {upright}, flopped {flopped}). Preview: shots 1-3, flop, reset...")
    tulip.glide(UPRIGHT_ANGLE, step=2, delay=0.01)
    time.sleep(0.5)
    for shots in range(1, MAX_SHOTS):
        tulip.tipsy_lean(shots)
        time.sleep(0.6)
    tulip.flop()
    time.sleep(1)
    tulip.sober_up()
    print("Done! Run  python tipsy_tulip.py --screen oled  to use it.")


def run(sensor, button, servo, screen, on_threshold, off_threshold, debug=False):
    tulip = Tulip(servo)
    shots = 0
    glass_on = sensor.get_proximity() > on_threshold
    lifted_at = None
    last_shot_at = None
    streak = 0                    # readings in a row that disagree with the current state
    flash, flash_until = "", 0.0  # short message that temporarily replaces the status line

    print(f"\nTipsy Tulip ready! Glass is {'on' if glass_on else 'off'} the stand. "
          f"Flops after {MAX_SHOTS} shots. Ctrl+C to quit.\n")

    while True:
        now = time.monotonic()
        reading = sensor.get_proximity()
        if debug:
            print(f"  proximity {reading:4d}  glass_on={glass_on}  shots={shots}", end="\r")

        # --- glass detection with hysteresis + debounce ---
        looks_on = reading > on_threshold if not glass_on else reading > off_threshold
        streak = streak + 1 if looks_on != glass_on else 0

        if streak >= CONFIRM_SAMPLES:
            glass_on = looks_on
            streak = 0
            if not glass_on:
                lifted_at = now
                print("Glass lifted... bottoms up!")
            else:
                away = now - lifted_at if lifted_at is not None else 0
                lifted_at = None
                if away < MIN_LIFT_SECONDS:
                    print("Just a bump, not counted.")
                else:
                    too_fast = last_shot_at is not None and now - last_shot_at < PACE_SECONDS
                    shots += 1
                    last_shot_at = now
                    print(f"Shot #{shots}!" + ("  (too fast!)" if too_fast else ""))
                    if too_fast and shots < MAX_SHOTS:
                        flash, flash_until = "Too fast! Slow down", now + 3
                    if shots < MAX_SHOTS:
                        tulip.tipsy_lean(shots)
                        button.LED_on(int(255 * shots / MAX_SHOTS))
                    elif shots == MAX_SHOTS:
                        print("That's the limit - the flower is done. Press the button to reset.")
                        tulip.flop()
                        button.LED_config(255, 400, 400)   # blink: "press me"
                    else:
                        print("Still going?! The flower is already on the floor.")
                        tulip.twitch()

        # --- reset button ---
        if button.is_button_pressed():
            while button.is_button_pressed():
                time.sleep(0.02)
            print("Reset - sobering up.")
            button.LED_off()
            shots, last_shot_at = 0, None
            flash, flash_until = "Sobered up!", time.monotonic() + 2
            screen.show(f"Shots: 0/{MAX_SHOTS}", flash, "ready", 0)
            tulip.sober_up()

        # --- drunk sway while tipsy (not when sober or flopped) ---
        if 0 < shots < MAX_SHOTS:
            tulip.sway(shots, now)

        line1, line2, mood = status(shots, glass_on, last_shot_at, time.monotonic(), flash, flash_until)
        screen.show(line1, line2, mood, shots)
        time.sleep(LOOP_DELAY)


def main():
    parser = argparse.ArgumentParser(description="Tipsy Tulip shot counter")
    parser.add_argument("--aim", action="store_true", help="position the servo to attach the flower")
    parser.add_argument("--setup", action="store_true", help="set the upright and flopped positions")
    parser.add_argument("--threshold", type=float, help="skip calibration, use this proximity threshold")
    parser.add_argument("--debug", action="store_true", help="print live sensor readings")
    parser.add_argument("--screen", choices=["auto", "oled", "pitft", "none"], default="auto",
                        help="which display to use (auto = OLED if plugged in, else Mini PiTFT)")
    args = parser.parse_args()
    load_angles()

    if args.setup:
        servo = pi_servo_hat.PiServoHat()
        servo.restart()
        setup_mode(servo)
        return

    if args.aim:
        servo = pi_servo_hat.PiServoHat()
        servo.restart()
        aim_mode(servo)
        return

    sensor, button, servo = setup_hardware()
    screen = make_screen(args.screen)
    screen.show("Tipsy Tulip", "starting up...")
    try:
        if args.threshold is not None:
            on_threshold, off_threshold = args.threshold, args.threshold * 0.8
        else:
            on_threshold, off_threshold = calibrate(sensor, button, screen)
        run(sensor, button, servo, screen, on_threshold, off_threshold, debug=args.debug)
    except KeyboardInterrupt:
        print("\nGoodnight, tulip.")
        button.LED_off()
        screen.clear()
        servo.move_servo_position(SERVO_CH, UPRIGHT_ANGLE)


if __name__ == "__main__":
    main()
