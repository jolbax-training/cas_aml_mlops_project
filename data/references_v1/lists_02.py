def rotate_left(items: list[int], k: int) -> list[int]:
    if not items:
        return []
    return [items[(index + k) % len(items)] for index in range(len(items))]
