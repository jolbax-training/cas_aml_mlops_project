import unicodedata


def count_vowels(text: str) -> int:
    count = 0
    for char in unicodedata.normalize("NFD", text):
        if char.lower() in ("a", "e", "i", "o", "u"):
            count += 1
    return count
