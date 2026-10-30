def digital_root(n: int) -> int:
    while n >= 10:
        total = 0
        while n:
            n, digit = divmod(n, 10)
            total += digit
        n = total
    return n
