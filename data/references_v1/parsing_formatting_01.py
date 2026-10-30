def format_duration(seconds: int) -> str:
    minutes_total, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes_total, 60)
    return "%d:%02d:%02d" % (hours, minutes, secs)
