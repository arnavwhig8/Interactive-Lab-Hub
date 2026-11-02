"""
Desk Curfew: the parts you touch, see and hear. Every one of them has a fallback, so the
device still runs when a part is missing (no button -> the keyboard, no screen -> the terminal,
no Piper -> silence).

  Button  SparkFun Qwiic Button (Lab 4)  ->  Mini PiTFT buttons A/B (Lab 2)  ->  Enter key
  Screen  Mini PiTFT 240x135 (Lab 2)     ->  Qwiic OLED 128x32 (Lab 4)       ->  terminal
  Voice   Piper, en_US-lessac-medium (Lab 3)                                   ->  silence

The screen and button code is adapted from Lab 4's tipsy_tulip.py.
"""
import importlib.util
import os
import pathlib
import select
import shutil
import subprocess
import sys
import time

import requests

HERE = pathlib.Path(__file__).resolve().parent          # .../Lab 5/desk_curfew
LAB5 = HERE.parent                                       # .../Lab 5
LAB3 = LAB5.parent / "Lab 3"

LONG_PRESS = 1.2   # seconds held = "OK"


# ============================================================================ button


class Button:
    """One interface over three kinds of button. wait() returns 'short', 'long' or None (timeout).

    Qwiic Button : tap = short, hold 1.2 s = long
    PiTFT        : button A = short, button B = long
    keyboard     : Enter = short, 'ok' + Enter = long   (works over ssh inside tmux)
    """

    def __init__(self, choice="auto"):
        self.kind, self.qwiic, self.a, self.b = "keyboard", None, None, None
        self.keyboard = sys.stdin.isatty()
        if choice in ("auto", "qwiic"):
            try:
                import qwiic_button
                btn = qwiic_button.QwiicButton()
                if btn.begin():
                    self.qwiic, self.kind = btn, "qwiic"
                    btn.LED_off()
                elif choice == "qwiic":
                    print("(Qwiic Button not found on I2C)")
            except Exception as err:
                if choice == "qwiic":
                    print(f"(Qwiic Button didn't start: {err})")
        if self.kind == "keyboard" and choice in ("auto", "pitft"):
            try:
                import board
                import digitalio
                self.a = digitalio.DigitalInOut(board.D23)
                self.b = digitalio.DigitalInOut(board.D24)
                self.a.switch_to_input(pull=digitalio.Pull.UP)
                self.b.switch_to_input(pull=digitalio.Pull.UP)
                self.kind = "pitft"
            except Exception as err:
                if choice == "pitft":
                    print(f"(PiTFT buttons didn't start: {err})")
        print(f"Button: {self.kind}" + (" (+ Enter key)" if self.keyboard and self.kind != "keyboard" else ""))

    # -- hint text for the screen
    def hints(self):
        return {"qwiic": ("tap", "hold"), "pitft": ("btn A", "btn B"),
                "keyboard": ("Enter", "type ok")}[self.kind]

    def _key(self):
        if not self.keyboard:
            return None
        if select.select([sys.stdin], [], [], 0)[0]:
            line = sys.stdin.readline().strip().lower()
            return "long" if line in ("ok", "o", "y", "yes", "l") else "short"
        return None

    def wait(self, timeout=None):
        end = None if timeout is None else time.time() + timeout
        while end is None or time.time() < end:
            k = self._key()
            if k:
                return k
            if self.qwiic is not None:
                try:
                    if self.qwiic.is_button_pressed():
                        t0 = time.time()
                        while self.qwiic.is_button_pressed():
                            time.sleep(0.02)
                            if time.time() - t0 >= LONG_PRESS:
                                self.led(60)            # flash: you can let go now
                        return "long" if time.time() - t0 >= LONG_PRESS else "short"
                except OSError:                          # I2C hiccup: try again next poll
                    pass
            if self.a is not None:
                if not self.a.value:
                    while not self.a.value:
                        time.sleep(0.02)
                    return "short"
                if not self.b.value:
                    while not self.b.value:
                        time.sleep(0.02)
                    return "long"
            time.sleep(0.02)
        return None

    def pressed_now(self):
        """Non-blocking: was there a press since the last check? (used during the night)"""
        return self.wait(0.01)

    # -- the Qwiic Button's own LED
    def led(self, brightness):
        if self.qwiic is not None:
            try:
                self.qwiic.LED_on(brightness) if brightness else self.qwiic.LED_off()
            except Exception:
                pass

    def breathe(self, brightness=6):
        """Slow, dim pulse all night: it is watching, and it will not light up the room."""
        if self.qwiic is not None:
            try:
                self.qwiic.LED_config(brightness, 4000, 2000)
            except Exception:
                self.led(brightness)


# ============================================================================ screen


def _font(name, size):
    from PIL import ImageFont
    for path in (f"/usr/share/fonts/truetype/dejavu/{name}", name):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


class TerminalScreen:
    name = "terminal"

    def show(self, top, big, small="", mood="info"):
        print(f"[screen] {top} | {big} | {small}", flush=True)

    def off(self):
        print("[screen] (off)", flush=True)


class OledScreen:
    """Qwiic OLED 128x32 (Lab 4): two lines."""
    name = "OLED"

    def __init__(self):
        import board
        import busio
        import adafruit_ssd1306
        from PIL import Image, ImageDraw
        self.oled = adafruit_ssd1306.SSD1306_I2C(128, 32, busio.I2C(board.SCL, board.SDA))
        self.Image, self.ImageDraw = Image, ImageDraw

    def show(self, top, big, small="", mood="info"):
        img = self.Image.new("1", (128, 32))
        d = self.ImageDraw.Draw(img)
        d.text((0, -1), f"{top} {big}".strip(), font=_font("DejaVuSans-Bold.ttf", 14), fill=255)
        d.text((0, 18), small, font=_font("DejaVuSans.ttf", 11), fill=255)
        self.oled.image(img)
        self.oled.show()

    def off(self):
        self.oled.fill(0)
        self.oled.show()


class PitftScreen:
    """Mini PiTFT 240x135 (Lab 2), same pins and rotation as Lab 2 / Lab 4."""
    name = "PiTFT"
    COLORS = {"info": (70, 70, 70), "night": (25, 35, 90), "ok": (0, 150, 70),
              "late": (220, 120, 0), "bad": (190, 30, 30)}

    def __init__(self):
        import board
        import digitalio
        import adafruit_rgb_display.st7789 as st7789
        from PIL import Image, ImageDraw
        self.disp = st7789.ST7789(
            board.SPI(), cs=digitalio.DigitalInOut(board.D5), dc=digitalio.DigitalInOut(board.D25),
            rst=None, baudrate=64000000, width=135, height=240, x_offset=53, y_offset=40)
        self.backlight = digitalio.DigitalInOut(board.D22)
        self.backlight.switch_to_output()
        self.backlight.value = True
        self.Image, self.ImageDraw = Image, ImageDraw
        self.W, self.H = 240, 135

    def _fit(self, d, text, width, size, bold=True):
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        while size > 10:
            f = _font(name, size)
            if d.textlength(text, font=f) <= width:
                return f
            size -= 2
        return _font(name, 10)

    def _center(self, d, y, text, font, fill):
        d.text(((self.W - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)

    def show(self, top, big, small="", mood="info"):
        self.backlight.value = True
        color = self.COLORS.get(mood, self.COLORS["info"])
        img = self.Image.new("RGB", (self.W, self.H), (0, 0, 0))
        d = self.ImageDraw.Draw(img)
        d.text((8, 4), top, font=_font("DejaVuSans-Bold.ttf", 14), fill=(150, 150, 150))
        self._center(d, 24, big, self._fit(d, big, 228, 54), (255, 255, 255) if mood != "late" else color)
        d.rectangle((0, self.H - 36, self.W, self.H), fill=color)
        self._center(d, self.H - 30, small, self._fit(d, small, 228, 20, bold=False), (255, 255, 255))
        self.disp.image(img, 90)

    def off(self):
        self.disp.image(self.Image.new("RGB", (self.W, self.H)), 90)
        self.backlight.value = False


def make_screen(choice="auto"):
    """auto = Mini PiTFT if it is on the header, else the Qwiic OLED, else the terminal."""
    order = {"auto": [PitftScreen, OledScreen], "pitft": [PitftScreen], "oled": [OledScreen],
             "none": []}[choice]
    for kind in order:
        try:
            s = kind()
            print(f"Screen: {s.name}")
            return s
        except ImportError as err:
            print(f"({kind.name}: missing library '{err.name}', see desk_curfew/SETUP.md)")
        except Exception as err:
            if choice != "auto":
                print(f"({kind.name} didn't start: {err})")
    print("Screen: terminal only")
    return TerminalScreen()


# ============================================================================ voice


class Voice:
    """Piper from Lab 3. Uses the Lab 3 virtualenv and voices folder if Piper is not installed here."""

    def __init__(self, enabled=True, model="en_US-lessac-medium", voices=None):
        self.ok, self.model = False, model
        self.voices = pathlib.Path(voices) if voices else LAB3 / "voices"
        if not enabled:
            print("Voice: off")
            return
        candidates = []
        if importlib.util.find_spec("piper") is not None:
            candidates.append(sys.executable)
        candidates.append(str(LAB3 / ".venv" / "bin" / "python"))
        self.python = next((p for p in candidates if os.path.exists(p)), None)
        if self.python is None or shutil.which("aplay") is None:
            print("Voice: none (Piper or aplay not found, see desk_curfew/SETUP.md)")
            return
        if not (self.voices / f"{model}.onnx").exists():
            print(f"Voice: none (no {model}.onnx in {self.voices}, see desk_curfew/SETUP.md)")
            return
        self.ok = True
        print(f"Voice: Piper {model}")

    def say(self, text):
        if not self.ok:
            return
        try:
            piper = subprocess.Popen(
                [self.python, "-m", "piper", "--model", self.model, "--data-dir", str(self.voices),
                 "--output-raw", "--", text],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            subprocess.run(["aplay", "-q", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"],
                           stdin=piper.stdout, stderr=subprocess.DEVNULL, timeout=120)
            piper.wait(timeout=10)
        except Exception as err:
            print(f"(voice failed: {err})")


# ============================================================================ Qwen


def ask_qwen(prompt, model="qwen3.5:0.8b", max_tokens=120, timeout=300):
    """One request to Ollama on the Pi, thinking off. Returns (answer, seconds)."""
    t0 = time.time()
    r = requests.post("http://localhost:11434/api/generate", json={
        "model": model, "prompt": prompt, "think": False, "stream": False,
        "options": {"temperature": 0.3, "num_predict": max_tokens, "num_ctx": 4096},
    }, timeout=timeout)
    r.raise_for_status()
    return r.json()["response"].strip(), time.time() - t0
