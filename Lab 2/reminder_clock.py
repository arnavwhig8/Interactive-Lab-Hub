
import time
import math
from datetime import datetime, timedelta

import board
import digitalio

from PIL import Image, ImageDraw, ImageFont
import adafruit_rgb_display.st7789 as st7789


# ============================================================
# LIFE CLOCK
# ============================================================
#
# DEMO_MODE = True
#     Automatically cycles through feature screens.
#
# DEMO_MODE = False
#     Runs using real date/time and your real schedule.
#
# You can ALSO press BOTH PiTFT buttons together
# while running to turn Demo Mode on/off.
# ============================================================

DEMO_MODE = False

CLASS_WARNING_MINUTES = 30

WATER_INTERVAL_MINUTES = 60

BEDTIME = "23:30"

WIND_DOWN_MINUTES = 45

SNOOZE_MINUTES = 10


# ============================================================
# CLASS SCHEDULE
#
# Monday = 0
# Tuesday = 1
# Wednesday = 2
# Thursday = 3
# Friday = 4
# ============================================================

CLASSES = [

    # MONDAY
    {
        "name": "NBAY 5795",
        "day": 0,
        "start": "13:25",
        "end": "16:10",
    },

    {
        "name": "CS 5424",
        "day": 0,
        "start": "17:55",
        "end": "19:10",
    },

    {
        "name": "CS 5785",
        "day": 0,
        "start": "19:30",
        "end": "20:45",
    },


    # TUESDAY
    {
        "name": "TECH 5900",
        "day": 1,
        "start": "08:40",
        "end": "09:55",
    },

    {
        "name": "INFO 5600",
        "day": 1,
        "start": "11:40",
        "end": "12:55",
    },

    {
        "name": "CS 5854",
        "day": 1,
        "start": "17:55",
        "end": "20:35",
    },


    # WEDNESDAY
    {
        "name": "NBAY 5795",
        "day": 2,
        "start": "13:25",
        "end": "16:10",
    },

    {
        "name": "CS 5424",
        "day": 2,
        "start": "17:55",
        "end": "19:10",
    },

    {
        "name": "CS 5785",
        "day": 2,
        "start": "19:30",
        "end": "20:45",
    },


    # THURSDAY
    {
        "name": "TECH 5900",
        "day": 3,
        "start": "08:40",
        "end": "09:55",
    },

    {
        "name": "INFO 5600",
        "day": 3,
        "start": "11:40",
        "end": "12:55",
    },


    # FRIDAY
    {
        "name": "TECH 5900 Studio",
        "day": 4,
        "start": "08:40",
        "end": "14:40",
    },
]


# ============================================================
# DISPLAY SETUP
# ============================================================

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


# Landscape display
height = disp.width
width = disp.height

rotation = 90


image = Image.new(
    "RGB",
    (width, height)
)

draw = ImageDraw.Draw(image)


# ============================================================
# FONTS
# ============================================================

FONT = (
    "/usr/share/fonts/truetype/"
    "dejavu/DejaVuSans.ttf"
)

BOLD = (
    "/usr/share/fonts/truetype/"
    "dejavu/DejaVuSans-Bold.ttf"
)


font_big = ImageFont.truetype(
    BOLD,
    24
)

font_medium = ImageFont.truetype(
    BOLD,
    17
)

font_small = ImageFont.truetype(
    FONT,
    12
)

font_tiny = ImageFont.truetype(
    FONT,
    10
)


# ============================================================
# COLORS
# ============================================================

WHITE = (245, 245, 245)

SOFT = (175, 185, 200)

BLACK = (5, 8, 14)

BLUE = (50, 110, 240)

CYAN = (40, 210, 225)

GREEN = (60, 210, 125)

YELLOW = (250, 205, 65)

ORANGE = (250, 135, 40)

RED = (240, 65, 70)

PURPLE = (155, 85, 235)

PINK = (235, 90, 175)

NAVY = (10, 18, 42)


# ============================================================
# BACKLIGHT
# ============================================================

backlight = digitalio.DigitalInOut(
    board.D22
)

backlight.switch_to_output(
    value=True
)


# ============================================================
# BUTTONS
# ============================================================

button_a = digitalio.DigitalInOut(
    board.D23
)

button_a.switch_to_input(
    pull=digitalio.Pull.UP
)


button_b = digitalio.DigitalInOut(
    board.D24
)

button_b.switch_to_input(
    pull=digitalio.Pull.UP
)


# ============================================================
# PROGRAM STATE
# ============================================================

last_water = datetime.now()

water_count = 0

snoozed_until = {}

dismissed_until = {}


# Button B cycles these pages while idle
PAGES = [
    "HOME",
    "SCHEDULE",
    "WATER",
    "SLEEP",
]

page_index = 0


# Current Demo Mode
demo_mode = DEMO_MODE

demo_started = time.monotonic()

both_buttons_latched = False


# ============================================================
# BASIC DRAWING HELPERS
# ============================================================

def clear(background=BLACK):

    draw.rectangle(
        (0, 0, width, height),
        fill=background
    )


def center_text(
    text,
    y,
    font,
    color=WHITE
):

    box = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = (
        box[2] - box[0]
    )

    x = (
        width - text_width
    ) // 2

    draw.text(
        (x, y),
        text,
        font=font,
        fill=color
    )


def left_text(
    text,
    x,
    y,
    font,
    color=WHITE
):

    draw.text(
        (x, y),
        text,
        font=font,
        fill=color
    )


def progress_bar(
    x,
    y,
    w,
    h,
    progress,
    color
):

    progress = max(
        0,
        min(1, progress)
    )

    draw.rounded_rectangle(
        (x, y, x + w, y + h),
        radius=5,
        fill=(30, 35, 45),
        outline=(100, 110, 125)
    )

    filled = int(
        (w - 4) * progress
    )

    if filled > 0:

        draw.rounded_rectangle(
            (
                x + 2,
                y + 2,
                x + 2 + filled,
                y + h - 2
            ),
            radius=4,
            fill=color
        )


def pulse_dot(
    x,
    y,
    color,
    animation_time
):

    amount = (
        math.sin(
            animation_time * 4
        )
        + 1
    ) / 2

    radius = (
        3
        + int(amount * 2)
    )

    draw.ellipse(
        (
            x - radius,
            y - radius,
            x + radius,
            y + radius
        ),
        fill=color
    )


# ============================================================
# TIME HELPERS
# ============================================================

def make_datetime(
    date_value,
    time_string
):

    hour, minute = map(
        int,
        time_string.split(":")
    )

    return datetime.combine(
        date_value,
        datetime.min.time()
    ).replace(
        hour=hour,
        minute=minute
    )


def get_day_progress(now):

    seconds = (
        now.hour * 3600
        + now.minute * 60
        + now.second
    )

    return (
        seconds / 86400
    )


def get_theme(now):

    hour = now.hour

    # Morning
    if 6 <= hour < 11:

        return (
            (35, 22, 8),
            YELLOW
        )

    # Afternoon
    if 11 <= hour < 17:

        return (
            (7, 26, 42),
            CYAN
        )

    # Evening
    if 17 <= hour < 21:

        return (
            (38, 14, 42),
            PINK
        )

    # Night
    return (
        NAVY,
        PURPLE
    )


# ============================================================
# WATER
# ============================================================

def minutes_since_water(now):

    return int(
        (
            now - last_water
        ).total_seconds()
        / 60
    )


def water_due(now):

    if "water" in snoozed_until:

        if (
            now
            < snoozed_until["water"]
        ):

            return False

    return (
        minutes_since_water(now)
        >= WATER_INTERVAL_MINUTES
    )


def log_water():

    global last_water
    global water_count

    last_water = datetime.now()

    water_count += 1

    snoozed_until.pop(
        "water",
        None
    )

    print(
        "Water logged!"
    )


# ============================================================
# CLASS LOGIC
# ============================================================

def classes_today(now):

    result = []

    for class_info in CLASSES:

        if (
            class_info["day"]
            == now.weekday()
        ):

            result.append(
                class_info
            )

    return sorted(
        result,
        key=lambda c: c["start"]
    )


def get_current_class(now):

    for class_info in classes_today(now):

        start = make_datetime(
            now.date(),
            class_info["start"]
        )

        end = make_datetime(
            now.date(),
            class_info["end"]
        )

        if (
            start
            <= now
            < end
        ):

            return {
                "name":
                    class_info["name"],

                "start":
                    start,

                "end":
                    end,
            }

    return None


def get_next_class(now):

    options = []

    for days_ahead in range(8):

        date_value = (
            now.date()
            + timedelta(
                days=days_ahead
            )
        )

        weekday = (
            date_value.weekday()
        )

        for class_info in CLASSES:

            if (
                class_info["day"]
                != weekday
            ):

                continue

            start = make_datetime(
                date_value,
                class_info["start"]
            )

            if start > now:

                options.append(
                    (
                        start,
                        class_info
                    )
                )

    if not options:

        return None


    start, class_info = min(
        options,
        key=lambda item: item[0]
    )


    end = make_datetime(
        start.date(),
        class_info["end"]
    )


    return {

        "name":
            class_info["name"],

        "start":
            start,

        "end":
            end,
    }


def get_class_warning(now):

    next_class = get_next_class(now)

    if next_class is None:

        return None


    if (
        next_class["start"].date()
        != now.date()
    ):

        return None


    minutes = (
        next_class["start"]
        - now
    ).total_seconds() / 60


    key = (
        "class:"
        + next_class["name"]
        + ":"
        + str(now.date())
    )


    if key in snoozed_until:

        if (
            now
            < snoozed_until[key]
        ):

            return None


    if key in dismissed_until:

        if (
            now
            < dismissed_until[key]
        ):

            return None


    if (
        0
        < minutes
        <= CLASS_WARNING_MINUTES
    ):

        return {

            "type":
                "class",

            "key":
                key,

            "name":
                next_class["name"],

            "start":
                next_class["start"],

            "minutes":
                max(
                    1,
                    int(minutes)
                )
        }


    return None


# ============================================================
# SLEEP LOGIC
# ============================================================

def get_sleep_warning(now):

    bedtime = make_datetime(
        now.date(),
        BEDTIME
    )


    minutes = (
        bedtime - now
    ).total_seconds() / 60


    key = (
        "sleep:"
        + str(now.date())
    )


    if key in snoozed_until:

        if (
            now
            < snoozed_until[key]
        ):

            return None


    if key in dismissed_until:

        if (
            now
            < dismissed_until[key]
        ):

            return None


    if (
        0
        <= minutes
        <= WIND_DOWN_MINUTES
    ):

        return {

            "type":
                "sleep",

            "key":
                key,

            "bedtime":
                bedtime,

            "minutes":
                max(
                    1,
                    int(minutes)
                )
        }


    return None


# ============================================================
# REMINDER PRIORITY
# ============================================================

def get_active_reminder(now):

    class_warning = (
        get_class_warning(now)
    )

    if class_warning:

        return class_warning


    sleep_warning = (
        get_sleep_warning(now)
    )

    if sleep_warning:

        return sleep_warning


    if water_due(now):

        return {

            "type":
                "water",

            "key":
                "water",

            "minutes":
                minutes_since_water(now)
        }


    return None


# ============================================================
# HOME SCREEN
# ============================================================

def draw_home(
    now,
    animation_time
):

    background, accent = (
        get_theme(now)
    )

    clear(background)


    # Current time in corner
    left_text(
        now.strftime(
            "%I:%M %p"
        ),
        7,
        5,
        font_small,
        SOFT
    )


    # Animated "alive" indicator
    pulse_dot(
        width - 12,
        11,
        accent,
        animation_time
    )


    next_class = (
        get_next_class(now)
    )


    if next_class:

        minutes = int(
            (
                next_class["start"]
                - now
            ).total_seconds()
            / 60
        )


        center_text(
            "NEXT",
            23,
            font_tiny,
            SOFT
        )


        center_text(
            next_class["name"],
            38,
            font_medium
        )


        if minutes < 60:

            countdown = (
                "in "
                + str(minutes)
                + " min"
            )

        else:

            hours = (
                minutes // 60
            )

            remaining = (
                minutes % 60
            )

            countdown = (
                "in "
                + str(hours)
                + "h "
                + str(remaining)
                + "m"
            )


        center_text(
            countdown,
            61,
            font_small,
            accent
        )


    else:

        center_text(
            "NO MORE CLASSES",
            43,
            font_medium
        )


    # Day progress
    progress = (
        get_day_progress(now)
    )


    center_text(
        "DAY "
        + str(
            int(progress * 100)
        )
        + "% COMPLETE",
        83,
        font_tiny,
        SOFT
    )


    progress_bar(
        15,
        98,
        210,
        13,
        progress,
        accent
    )


    # Hydration dots
    visible_water = min(
        8,
        water_count
    )


    for index in range(8):

        x = (
            44
            + index * 18
        )

        if index < visible_water:

            color = CYAN

        else:

            color = (
                65,
                72,
                82
            )


        draw.ellipse(
            (
                x,
                119,
                x + 7,
                126
            ),
            fill=color
        )


    disp.image(
        image,
        rotation
    )


# ============================================================
# SCHEDULE SCREEN
# ============================================================

def draw_schedule(now):

    clear(
        (9, 15, 28)
    )


    center_text(
        "TODAY",
        4,
        font_medium,
        CYAN
    )


    todays_classes = (
        classes_today(now)
    )


    if not todays_classes:

        center_text(
            "No classes today",
            50,
            font_small,
            SOFT
        )


    else:

        y = 30


        for class_info in todays_classes[:4]:

            start = make_datetime(
                now.date(),
                class_info["start"]
            )

            end = make_datetime(
                now.date(),
                class_info["end"]
            )


            active = (
                start
                <= now
                < end
            )


            if active:

                color = GREEN

            else:

                color = WHITE


            left_text(
                class_info["name"],
                8,
                y,
                font_small,
                color
            )


            left_text(
                start.strftime(
                    "%I:%M"
                ),
                177,
                y,
                font_tiny,
                SOFT
            )


            y += 23


    center_text(
        "B: NEXT PAGE",
        118,
        font_tiny,
        SOFT
    )


    disp.image(
        image,
        rotation
    )


# ============================================================
# WATER PAGE
# ============================================================

def draw_water_page(
    now,
    animation_time
):

    clear(
        (4, 30, 40)
    )


    center_text(
        "HYDRATION",
        4,
        font_medium,
        CYAN
    )


    # Bottle
    bottle_x = 92
    bottle_y = 32

    bottle_width = 56
    bottle_height = 68


    draw.rounded_rectangle(
        (
            bottle_x,
            bottle_y,
            bottle_x
            + bottle_width,
            bottle_y
            + bottle_height
        ),
        radius=10,
        outline=WHITE,
        width=2
    )


    # Bottle cap
    draw.rectangle(
        (
            bottle_x + 18,
            bottle_y - 8,
            bottle_x + 38,
            bottle_y + 2
        ),
        outline=WHITE
    )


    fraction = min(
        1,
        water_count / 8
    )


    water_height = int(
        (
            bottle_height - 6
        )
        * fraction
    )


    wave = int(
        2
        * math.sin(
            animation_time * 4
        )
    )


    if water_height > 0:

        draw.rounded_rectangle(
            (
                bottle_x + 3,
                bottle_y
                + bottle_height
                - water_height
                - 3
                + wave,

                bottle_x
                + bottle_width
                - 3,

                bottle_y
                + bottle_height
                - 3
            ),
            radius=7,
            fill=CYAN
        )


    center_text(
        str(water_count)
        + "/8 today",
        106,
        font_small
    )


    if water_due(now):

        status = "WATER DUE"

        status_color = ORANGE

    else:

        status = (
            str(
                minutes_since_water(now)
            )
            + " min since last"
        )

        status_color = SOFT


    center_text(
        status,
        121,
        font_tiny,
        status_color
    )


    disp.image(
        image,
        rotation
    )


# ============================================================
# SLEEP PAGE
# ============================================================

def draw_sleep_page(
    now,
    animation_time
):

    background = (
        18,
        10,
        38
    )

    clear(background)


    # Moon
    draw.ellipse(
        (
            36,
            27,
            74,
            65
        ),
        fill=YELLOW
    )


    draw.ellipse(
        (
            49,
            20,
            79,
            58
        ),
        fill=background
    )


    # Animated stars
    stars = [
        (110, 18),
        (145, 33),
        (185, 18),
        (210, 48),
    ]


    for x, y in stars:

        radius = (
            1
            + int(
                (
                    math.sin(
                        animation_time * 3
                        + x
                    )
                    + 1
                )
                / 2
            )
        )


        draw.ellipse(
            (
                x - radius,
                y - radius,
                x + radius,
                y + radius
            ),
            fill=WHITE
        )


    bedtime = make_datetime(
        now.date(),
        BEDTIME
    )


    if bedtime < now:

        bedtime += timedelta(
            days=1
        )


    minutes = int(
        (
            bedtime - now
        ).total_seconds()
        / 60
    )


    hours = (
        minutes // 60
    )

    remaining = (
        minutes % 60
    )


    left_text(
        "WIND DOWN",
        92,
        24,
        font_medium,
        PURPLE
    )


    left_text(
        str(hours)
        + "h "
        + str(remaining)
        + "m",
        92,
        51,
        font_big
    )


    left_text(
        "until bedtime",
        94,
        84,
        font_tiny,
        SOFT
    )


    disp.image(
        image,
        rotation
    )


# ============================================================
# CURRENT CLASS SCREEN
# ============================================================

def draw_class_screen(
    class_info,
    now,
    animation_time
):

    clear(
        (6, 19, 45)
    )


    center_text(
        class_info["name"],
        4,
        font_medium
    )


    center_text(
        "IN CLASS",
        27,
        font_tiny,
        BLUE
    )


    total = (
        class_info["end"]
        - class_info["start"]
    ).total_seconds()


    elapsed = (
        now
        - class_info["start"]
    ).total_seconds()


    progress = (
        elapsed / total
    )


    progress = max(
        0,
        min(
            1,
            progress
        )
    )


    center_text(
        str(
            int(
                progress * 100
            )
        )
        + "% COMPLETE",
        49,
        font_small,
        SOFT
    )


    progress_bar(
        18,
        69,
        204,
        15,
        progress,
        BLUE
    )


    minutes_left = max(
        0,
        int(
            (
                class_info["end"]
                - now
            ).total_seconds()
            / 60
        )
    )


    center_text(
        str(minutes_left)
        + " MIN LEFT",
        92,
        font_small
    )


    if water_due(now):

        if (
            int(
                animation_time * 2
            )
            % 2
            == 0
        ):

            color = CYAN

        else:

            color = WHITE


        center_text(
            "WATER DUE  A:LOG  B:SNOOZE",
            117,
            font_tiny,
            color
        )


    else:

        center_text(
            "A: LOG WATER",
            117,
            font_tiny,
            SOFT
        )


    disp.image(
        image,
        rotation
    )


# ============================================================
# CLASS WARNING
# ============================================================

def draw_class_warning(
    reminder
):

    clear(
        (48, 22, 6)
    )


    center_text(
        "CLASS SOON",
        4,
        font_medium,
        ORANGE
    )


    center_text(
        reminder["name"],
        29,
        font_big
    )


    # Countdown ring
    center_x = 120
    center_y = 86
    radius = 29


    draw.ellipse(
        (
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius
        ),
        outline=(
            90,
            60,
            35
        ),
        width=5
    )


    fraction = (
        reminder["minutes"]
        / CLASS_WARNING_MINUTES
    )


    sweep = int(
        360 * fraction
    )


    draw.arc(
        (
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius
        ),
        start=-90,
        end=-90 + sweep,
        fill=ORANGE,
        width=5
    )


    center_text(
        str(
            reminder["minutes"]
        )
        + "m",
        77,
        font_medium
    )


    center_text(
        "A:DONE   B:SNOOZE",
        117,
        font_tiny,
        SOFT
    )


    disp.image(
        image,
        rotation
    )


# ============================================================
# WATER REMINDER
# ============================================================

def draw_water_reminder(
    reminder,
    animation_time
):

    clear(
        (0, 34, 48)
    )


    # Bouncing water drop
    bounce = int(
        7
        * abs(
            math.sin(
                animation_time * 3
            )
        )
    )


    center_x = 120

    top = (
        21 + bounce
    )


    draw.ellipse(
        (
            center_x - 12,
            top + 14,
            center_x + 12,
            top + 38
        ),
        fill=CYAN
    )


    draw.polygon(
        [
            (
                center_x,
                top
            ),

            (
                center_x - 12,
                top + 20
            ),

            (
                center_x + 12,
                top + 20
            )
        ],
        fill=CYAN
    )


    center_text(
        "DRINK WATER",
        66,
        font_big
    )


    center_text(
        str(
            reminder["minutes"]
        )
        + " min since last",
        96,
        font_small,
        SOFT
    )


    center_text(
        "A:DONE   B:SNOOZE",
        118,
        font_tiny,
        CYAN
    )


    disp.image(
        image,
        rotation
    )


# ============================================================
# SLEEP WARNING
# ============================================================

def draw_sleep_warning(
    reminder
):

    clear(
        (25, 10, 42)
    )


    center_text(
        "WIND DOWN",
        7,
        font_medium,
        PURPLE
    )


    center_text(
        str(
            reminder["minutes"]
        )
        + " MIN",
        38,
        font_big
    )


    center_text(
        "until bedtime",
        69,
        font_small,
        SOFT
    )


    progress = (
        reminder["minutes"]
        / WIND_DOWN_MINUTES
    )


    progress_bar(
        20,
        94,
        200,
        14,
        progress,
        PURPLE
    )


    center_text(
        "A:DONE   B:SNOOZE",
        118,
        font_tiny,
        SOFT
    )


    disp.image(
        image,
        rotation
    )


# ============================================================
# DEMO MODE
# ============================================================

DEMO_SCREEN_SECONDS = 4.5


def get_demo_screen():

    elapsed = (
        time.monotonic()
        - demo_started
    )


    screen = int(
        elapsed
        // DEMO_SCREEN_SECONDS
    )


    return (
        screen % 7
    )


def draw_demo(
    now,
    animation_time
):

    screen = (
        get_demo_screen()
    )


    # --------------------------------------------------------
    # DEMO 1 — INTRO
    # --------------------------------------------------------

    if screen == 0:

        clear(
            (12, 15, 28)
        )


        pulse = (
            18
            + int(
                6
                * (
                    (
                        math.sin(
                            animation_time * 4
                        )
                        + 1
                    )
                    / 2
                )
            )
        )


        draw.ellipse(
            (
                120 - pulse,
                54 - pulse,
                120 + pulse,
                54 + pulse
            ),
            outline=CYAN,
            width=4
        )


        center_text(
            "LIFE CLOCK",
            85,
            font_big
        )


        center_text(
            "personal time dashboard",
            117,
            font_tiny,
            SOFT
        )


        disp.image(
            image,
            rotation
        )


    # --------------------------------------------------------
    # DEMO 2 — HOME / DAY PROGRESS
    # --------------------------------------------------------

    elif screen == 1:

        clear(
            (7, 26, 42)
        )


        left_text(
            "04:37 PM",
            7,
            5,
            font_small,
            SOFT
        )


        pulse_dot(
            228,
            11,
            CYAN,
            animation_time
        )


        center_text(
            "NEXT",
            23,
            font_tiny,
            SOFT
        )


        center_text(
            "CS 5424",
            38,
            font_medium
        )


        center_text(
            "in 1h 18m",
            61,
            font_small,
            CYAN
        )


        center_text(
            "DAY 69% COMPLETE",
            83,
            font_tiny,
            SOFT
        )


        progress_bar(
            15,
            98,
            210,
            13,
            0.69,
            CYAN
        )


        # Demo hydration dots
        for index in range(8):

            x = (
                44
                + index * 18
            )

            if index < 4:

                color = CYAN

            else:

                color = (
                    65,
                    72,
                    82
                )


            draw.ellipse(
                (
                    x,
                    119,
                    x + 7,
                    126
                ),
                fill=color
            )


        disp.image(
            image,
            rotation
        )


    # --------------------------------------------------------
    # DEMO 3 — CLASS WARNING
    # --------------------------------------------------------

    elif screen == 2:

        reminder = {

            "name":
                "CS 5424",

            "minutes":
                12
        }


        draw_class_warning(
            reminder
        )


    # --------------------------------------------------------
    # DEMO 4 — IN CLASS + WATER
    # --------------------------------------------------------

    elif screen == 3:

        clear(
            (6, 19, 45)
        )


        center_text(
            "CS 5424",
            4,
            font_medium
        )


        center_text(
            "IN CLASS",
            27,
            font_tiny,
            BLUE
        )


        progress = 0.63


        center_text(
            "63% COMPLETE",
            49,
            font_small,
            SOFT
        )


        progress_bar(
            18,
            69,
            204,
            15,
            progress,
            BLUE
        )


        center_text(
            "31 MIN LEFT",
            92,
            font_small
        )


        if (
            int(
                animation_time * 2
            )
            % 2
            == 0
        ):

            water_color = CYAN

        else:

            water_color = WHITE


        center_text(
            "WATER DUE  A:LOG  B:SNOOZE",
            117,
            font_tiny,
            water_color
        )


        disp.image(
            image,
            rotation
        )


    # --------------------------------------------------------
    # DEMO 5 — ANIMATED HYDRATION
    # --------------------------------------------------------

    elif screen == 4:

        clear(
            (4, 30, 40)
        )


        center_text(
            "HYDRATION",
            4,
            font_medium,
            CYAN
        )


        bottle_x = 92
        bottle_y = 31
        bottle_width = 56
        bottle_height = 69


        draw.rounded_rectangle(
            (
                bottle_x,
                bottle_y,
                bottle_x
                + bottle_width,
                bottle_y
                + bottle_height
            ),
            radius=10,
            outline=WHITE,
            width=2
        )


        draw.rectangle(
            (
                bottle_x + 18,
                bottle_y - 8,
                bottle_x + 38,
                bottle_y + 2
            ),
            outline=WHITE
        )


        fraction = 5 / 8


        water_height = int(
            (
                bottle_height - 6
            )
            * fraction
        )


        wave = int(
            2
            * math.sin(
                animation_time * 4
            )
        )


        draw.rounded_rectangle(
            (
                bottle_x + 3,

                bottle_y
                + bottle_height
                - water_height
                - 3
                + wave,

                bottle_x
                + bottle_width
                - 3,

                bottle_y
                + bottle_height
                - 3
            ),
            radius=7,
            fill=CYAN
        )


        center_text(
            "5/8 today",
            106,
            font_small
        )


        center_text(
            "A: LOG WATER",
            121,
            font_tiny,
            SOFT
        )


        disp.image(
            image,
            rotation
        )


    # --------------------------------------------------------
    # DEMO 6 — SLEEP
    # --------------------------------------------------------

    elif screen == 5:

        background = (
            18,
            10,
            38
        )


        clear(
            background
        )


        # Moon
        draw.ellipse(
            (
                28,
                39,
                68,
                79
            ),
            fill=YELLOW
        )


        draw.ellipse(
            (
                42,
                30,
                74,
                70
            ),
            fill=background
        )


        # Stars
        stars = [
            (110, 18),
            (150, 32),
            (185, 18),
            (215, 48),
        ]


        for x, y in stars:

            radius = (
                1
                + int(
                    (
                        math.sin(
                            animation_time * 3
                            + x
                        )
                        + 1
                    )
                    / 2
                )
            )


            draw.ellipse(
                (
                    x - radius,
                    y - radius,
                    x + radius,
                    y + radius
                ),
                fill=WHITE
            )


        left_text(
            "WIND DOWN",
            92,
            25,
            font_medium,
            PURPLE
        )


        left_text(
            "42 MIN",
            92,
            51,
            font_big
        )


        left_text(
            "until bedtime",
            94,
            84,
            font_tiny,
            SOFT
        )


        disp.image(
            image,
            rotation
        )


    # --------------------------------------------------------
    # DEMO 7 — DAY SUMMARY
    # --------------------------------------------------------

    else:

        clear(
            (8, 28, 18)
        )


        center_text(
            "DAY COMPLETE",
            8,
            font_big,
            GREEN
        )


        center_text(
            "3 classes",
            51,
            font_medium
        )


        center_text(
            "5 water logs",
            76,
            font_medium,
            CYAN
        )


        center_text(
            "ready to wind down",
            104,
            font_small,
            SOFT
        )


        # Small animated completion indicator
        pulse_dot(
            120,
            126,
            GREEN,
            animation_time
        )


        disp.image(
            image,
            rotation
        )


# ============================================================
# BUTTON A
# ============================================================

def press_a(now):

    current_class = (
        get_current_class(now)
    )


    if current_class:

        log_water()

        return


    reminder = (
        get_active_reminder(now)
    )


    if (
        reminder is None
        or reminder["type"]
        == "water"
    ):

        log_water()


    elif (
        reminder["type"]
        == "class"
    ):

        dismissed_until[
            reminder["key"]
        ] = (
            reminder["start"]
        )


        print(
            "Class reminder acknowledged."
        )


    elif (
        reminder["type"]
        == "sleep"
    ):

        dismissed_until[
            reminder["key"]
        ] = (
            now
            + timedelta(
                hours=12
            )
        )


        print(
            "Sleep reminder acknowledged."
        )


# ============================================================
# BUTTON B
# ============================================================

def press_b(now):

    global page_index


    current_class = (
        get_current_class(now)
    )


    if current_class:

        if water_due(now):

            snoozed_until[
                "water"
            ] = (
                now
                + timedelta(
                    minutes=SNOOZE_MINUTES
                )
            )


            print(
                "Water snoozed."
            )


        return


    reminder = (
        get_active_reminder(now)
    )


    if reminder:

        snoozed_until[
            reminder["key"]
        ] = (
            now
            + timedelta(
                minutes=SNOOZE_MINUTES
            )
        )


        print(
            "Reminder snoozed."
        )


    else:

        page_index = (
            page_index + 1
        ) % len(PAGES)


        print(
            "Page:",
            PAGES[
                page_index
            ]
        )


# ============================================================
# START PROGRAM
# ============================================================

print()

print(
    "============================"
)

print(
    "LIFE CLOCK RUNNING"
)

print(
    "============================"
)

print(
    "A = action / log water"
)

print(
    "B = snooze / next page"
)

print(
    "A + B = toggle demo mode"
)

print(
    "Ctrl+C = quit"
)

print()

print(
    "Demo mode:",
    demo_mode
)

print()


previous_a = (
    button_a.value
)

previous_b = (
    button_b.value
)

last_refresh = 0


try:

    while True:

        now = datetime.now()

        animation_time = (
            time.monotonic()
        )


        # Read buttons
        a = button_a.value

        b = button_b.value


        # Buttons are active LOW
        both_pressed = (
            not a
            and not b
        )


        # --------------------------------------------
        # BOTH BUTTONS = TOGGLE DEMO MODE
        # --------------------------------------------

        if (
            both_pressed
            and not both_buttons_latched
        ):

            demo_mode = (
                not demo_mode
            )

            demo_started = (
                time.monotonic()
            )

            both_buttons_latched = True


            print(
                "Demo mode:",
                demo_mode
            )


        if not both_pressed:

            both_buttons_latched = False


        # --------------------------------------------
        # INDIVIDUAL BUTTONS
        # --------------------------------------------

        if not both_pressed:

            if (
                previous_a
                and not a
            ):

                press_a(now)


            if (
                previous_b
                and not b
            ):

                press_b(now)


        previous_a = a

        previous_b = b


        # --------------------------------------------
        # UPDATE SCREEN
        #
        # Roughly 8 frames per second
        # --------------------------------------------

        if (
            time.monotonic()
            - last_refresh
            >= 0.12
        ):


            # ========================================
            # DEMO MODE
            # ========================================

            if demo_mode:

                draw_demo(
                    now,
                    animation_time
                )


            # ========================================
            # REAL MODE
            # ========================================

            else:

                current_class = (
                    get_current_class(now)
                )


                if current_class:

                    draw_class_screen(
                        current_class,
                        now,
                        animation_time
                    )


                else:

                    reminder = (
                        get_active_reminder(
                            now
                        )
                    )


                    if reminder:


                        if (
                            reminder["type"]
                            == "class"
                        ):

                            draw_class_warning(
                                reminder
                            )


                        elif (
                            reminder["type"]
                            == "water"
                        ):

                            draw_water_reminder(
                                reminder,
                                animation_time
                            )


                        elif (
                            reminder["type"]
                            == "sleep"
                        ):

                            draw_sleep_warning(
                                reminder
                            )


                    else:

                        page = (
                            PAGES[
                                page_index
                            ]
                        )


                        if page == "HOME":

                            draw_home(
                                now,
                                animation_time
                            )


                        elif page == "SCHEDULE":

                            draw_schedule(
                                now
                            )


                        elif page == "WATER":

                            draw_water_page(
                                now,
                                animation_time
                            )


                        elif page == "SLEEP":

                            draw_sleep_page(
                                now,
                                animation_time
                            )


            last_refresh = (
                time.monotonic()
            )


        time.sleep(
            0.02
        )


except KeyboardInterrupt:

    print()

    print(
        "Life Clock stopped."
    )


finally:

    clear()

    disp.image(
        image,
        rotation
    )

    button_a.deinit()

    button_b.deinit()

    backlight.deinit()

    cs_pin.deinit()

    dc_pin.deinit()
