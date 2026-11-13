"""Customer ki lipi (Roman ya Devanagari) aur jawab ki lipi ka milan. Django nahi chahiye."""


def devanagari_ratio(text: str) -> float:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return 0.0
    return sum("\u0900" <= c <= "\u097f" for c in letters) / len(letters)


def script_fix_instruction(customer_text: str, reply_text: str) -> str | None:
    """Lipi alag ho to model ko dene layak ek line, warna None.

    Customer Roman me likhe aur jawab Devanagari me aaye (ya ulta) to galat hai.
    Bahut chhote text (jaise "ok", "6") par kuch nahi kehte.
    """
    if sum(c.isalpha() for c in customer_text or "") < 3:
        return None
    customer_dev = devanagari_ratio(customer_text) > 0.3
    reply_dev = devanagari_ratio(reply_text) > 0.3
    if customer_dev == reply_dev:
        return None
    if reply_dev:
        return (
            "IMPORTANT: The customer wrote in Roman letters. Reply in Roman letters only "
            "(Hinglish). Do not use Devanagari."
        )
    return "IMPORTANT: The customer wrote in Devanagari. Reply in Devanagari Hindi only."
