def group_keys_by_value(mapping: dict[str, str]) -> dict[str, list[str]]:
    result = {}
    for key in sorted(mapping):
        result.setdefault(mapping[key], []).append(key)
    return result
