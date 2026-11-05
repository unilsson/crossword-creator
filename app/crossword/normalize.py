"""Normalisering av ord till korsordsform.

Regler:
- Versaler.
- Å, Ä och Ö är egna bokstäver och behålls.
- Andra diakritiska tecken tas bort (IDÉ -> IDE, MÜSLI -> MUSLI).
- Bindestreck och apostrofer tas bort (E-POST -> EPOST).
- Ord med mellanslag, siffror eller andra tecken avvisas.
"""

from __future__ import annotations

import unicodedata

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZÅÄÖ"
ALPHABET_SET = frozenset(ALPHABET)

_KEEP = {"Å", "Ä", "Ö"}
_DROP = {"-", "'", "’", "."}


def normalize_word(raw: str) -> str | None:
    """Returnera ordet i korsordsform, eller None om det inte går att använda."""
    word = raw.strip().upper()
    if not word or " " in word:
        return None
    out: list[str] = []
    for ch in word:
        if ch in _DROP:
            continue
        if ch in ALPHABET_SET:
            out.append(ch)
            continue
        if ch in _KEEP:
            out.append(ch)
            continue
        # Plocka bort accenter: É -> E + kombinerande accent.
        base = unicodedata.normalize("NFD", ch)[0]
        if base in ALPHABET_SET and base not in _KEEP:
            out.append(base)
            continue
        return None
    result = "".join(out)
    return result or None


def normalize_letter(ch: str) -> str | None:
    """Normalisera en enskild bokstav som användaren skrivit in."""
    if not ch:
        return None
    word = normalize_word(ch)
    if word is None or len(word) != 1:
        return None
    return word
