def run_length_encode(text: str) -> str:
    parts = []
    index = 0
    while index < len(text):
        end = index
        while end < len(text) and text[end] == text[index]:
            end += 1
        parts.append(text[index] + str(end - index))
        index = end
    return "".join(parts)
