def unique_in_order(items: list[int]) -> list[int]:
    result = []
    for item in items:
        if item not in result:
            result.append(item)
    return result
