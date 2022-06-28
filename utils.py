from datetime import timedelta


# https://stackoverflow.com/a/1094933/245602
def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


# The default timedelta.__str__ is hard to read - this is an alternative.
def timedelta_fmt(td: timedelta):
    # Logic to decompose into hours etc. copied from timedelta.__str__.
    mm, ss = divmod(td.seconds, 60)
    hh, mm = divmod(mm, 60)
    days = td.days

    values = [days, hh, mm, ss]
    symbols = ["d", "h", "m", "s"]
    started = False
    result = []

    for i, s in enumerate(symbols):
        v = values[i]
        if v != 0:
            started = True
        if started:
            result.append(f"{v}{s}")

    return "0s" if len(result) == 0 else " ".join(result)
