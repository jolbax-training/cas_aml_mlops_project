def parse_settings(text: str) -> dict[str, str]:
    settings = {}
    for segment in text.split(";"):
        if segment.strip(" ") == "":
            continue
        key, _, value = segment.partition("=")
        settings[key.strip(" ")] = value.strip(" ")
    return settings
