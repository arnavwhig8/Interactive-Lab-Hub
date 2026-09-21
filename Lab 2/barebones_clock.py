import time
from datetime import datetime

import board
import digitalio

from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789


# DISPLAY SETUP
cs_pin = digitalio.DigitalInOut(board.D5)
dc_pin = digitalio.DigitalInOut(board.D25)

spi = board.SPI()

disp = st7789.ST7789(
    spi,
    cs=cs_pin,
    dc=dc_pin,
    rst=None,
    baudrate=64000000,
    width=135,
    height=240,
    x_offset=53,
    y_offset=40,
)

height = disp.width
width = disp.height
rotation = 90

image = Image.new("RGB", (width, height))
draw = ImageDraw.Draw(image)


# FONT
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

big_font = ImageFont.truetype(BOLD, 25)
small_font = ImageFont.truetype(FONT, 14)


# BACKLIGHT
backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output(value=True)


def center_text(text, y, font):

    box = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = box[2] - box[0]

    x = (width - text_width) // 2

    draw.text(
        (x, y),
        text,
        font=font,
        fill=(255, 255, 255)
    )


try:

    while True:

        now = datetime.now()

        # Clear screen
        draw.rectangle(
            (0, 0, width, height),
            fill=(0, 0, 0)
        )

        # Current time
        center_text(
            now.strftime("%I:%M %p"),
            15,
            big_font
        )

        # Calculate progress through the day
        seconds_today = (
            now.hour * 3600
            + now.minute * 60
            + now.second
        )

        progress = seconds_today / 86400

        percent = int(progress * 100)

        center_text(
            f"DAY {percent}% COMPLETE",
            58,
            small_font
        )

        # Progress bar
        x = 20
        y = 88
        bar_width = 200
        bar_height = 16

        draw.rectangle(
            (
                x,
                y,
                x + bar_width,
                y + bar_height
            ),
            outline=(255, 255, 255),
            fill=(25, 25, 25)
        )

        filled = int(
            bar_width * progress
        )

        draw.rectangle(
            (
                x,
                y,
                x + filled,
                y + bar_height
            ),
            fill=(80, 200, 220)
        )

        disp.image(
            image,
            rotation
        )

        time.sleep(1)


except KeyboardInterrupt:

    print("\nBarebones clock stopped.")


finally:

    backlight.deinit()
    cs_pin.deinit()
    dc_pin.deinit()
