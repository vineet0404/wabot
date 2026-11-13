"""Lambe text ko chhote tukdon (chunks) me todta hai. Django nahi chahiye."""

import re

MAX_CHARS = 600


def split_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    pieces: list[str] = []
    for para in paragraphs:
        if len(para) <= max_chars:
            pieces.append(para)
            continue
        # Bada paragraph: line ya vakya ke hisaab se todo
        current = ""
        for part in re.split(r"(?<=[.!?\n])\s+", para):
            if len(part) > max_chars:  # bina viram wala bahut lamba tukda
                if current:
                    pieces.append(current)
                    current = ""
                pieces.extend(part[i : i + max_chars] for i in range(0, len(part), max_chars))
            elif len(current) + len(part) + 1 > max_chars:
                pieces.append(current)
                current = part
            else:
                current = f"{current} {part}".strip()
        if current:
            pieces.append(current)

    # Chhote tukde aage ke saath jod do, taaki ek-do line ka chunk bekaar na jaye
    merged: list[str] = []
    for piece in pieces:
        if merged and len(merged[-1]) + len(piece) + 1 <= max_chars // 2:
            merged[-1] += "\n" + piece
        else:
            merged.append(piece)
    return merged
