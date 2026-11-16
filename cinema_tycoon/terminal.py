"""Single-key terminal navigation, with line-input fallback for redirected scripts."""
import math
import sys

BAR = "─" * 76
TIME_FORMAT = "12h"


def format_time(hour, style=None):
    style = style or TIME_FORMAT
    if style == "24h":
        return f"{hour % 24:02d}:00"
    return f"{hour % 12 or 12}:00 {'AM' if hour % 24 < 12 else 'PM'}"


def time_range(start, duration):
    return f"{format_time(start)}–{format_time(start + duration)}" + (" (next day)" if start + duration >= 24 else "")


def interactive_terminal():
    return sys.stdin.isatty() and sys.stdout.isatty()


def money(amount):
    return f"-${abs(amount):,.2f}" if amount < 0 else f"${amount:,.2f}"


def header(title, *, clear=True):
    if clear and interactive_terminal():
        print("\033[2J\033[H", end="", flush=True)
    print(f"\n{BAR}\n  {title}\n{BAR}")


def read_key(prompt):
    if not interactive_terminal():
        return input(prompt + ": ").strip().lower()
    print(prompt + ": ", end="", flush=True)
    if sys.platform == "win32":
        import msvcrt
        value = msvcrt.getwch()
    else:
        import termios
        import tty
        descriptor = sys.stdin.fileno()
        previous = termios.tcgetattr(descriptor)
        try:
            tty.setraw(descriptor, termios.TCSANOW)
            value = sys.stdin.read(1)
        finally:
            termios.tcsetattr(descriptor, termios.TCSADRAIN, previous)
    if not value or value == "\x04":
        raise EOFError
    if value == "\x03":
        raise KeyboardInterrupt
    value = value.strip().lower()
    print(value)
    return value


def choice(prompt, allowed):
    while True:
        value = read_key(prompt)
        if value in allowed:
            return value
        print("Choose " + ", ".join(key.upper() if key else "Enter" for key in allowed) + ".")


def yes_no(prompt):
    return choice(prompt + " [Y/N]", ("y", "n")) == "y"


def pause():
    if interactive_terminal():
        choice("Press Enter to continue", ("",))


def ask(prompt, default=None):
    value = input(prompt + (f" [{default}]" if default is not None else "") + ": ").strip()
    return value or (str(default) if default is not None else "")


def whole(prompt, default=None, minimum=0, maximum=1000000):
    while True:
        try:
            value = int(ask(prompt, default))
            if minimum <= value <= maximum:
                return value
        except ValueError:
            pass
        print(f"Enter a whole number from {minimum:,} to {maximum:,}.")


def amount(prompt, default, minimum, maximum):
    while True:
        try:
            value = float(ask(prompt, default))
            if math.isfinite(value) and minimum <= value <= maximum:
                return round(value, 2)
        except ValueError:
            pass
        print(f"Enter an amount from {money(minimum)} to {money(maximum)}.")


def select(title, items, context=None):
    """Items carry stable values, but players select with a one-key page position."""
    page = 0
    while True:
        header(title)
        if context:
            context()
        pages = max(1, (len(items) + 8) // 9)
        visible = items[page * 9:page * 9 + 9]
        for i, (_, label) in enumerate(visible, 1):
            print(f"\n  [{i}] {label}")
        if not items:
            print("No choices are available here yet.")
        print(f"\nPage {page + 1}/{pages}  ·  [B] Back" + ("  [P] Previous" if page else "") + ("  [N] Next" if page + 1 < pages else ""))
        keys = [str(i) for i in range(1, len(visible) + 1)] + ["b"]
        if page:
            keys.append("p")
        if page + 1 < pages:
            keys.append("n")
        key = choice("Choose", keys)
        if key == "b":
            return None
        if key == "n":
            page += 1
        elif key == "p":
            page -= 1
        else:
            return visible[int(key) - 1][0]


def menu(title, options, context=None, notice=""):
    header(title)
    if context:
        context()
    for key, label in options:
        print(f"  [{key.upper()}] {label}")
    if notice:
        print(f"\n{notice}")
    return choice("Choose", [key for key, _ in options])
