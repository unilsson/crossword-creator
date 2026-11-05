"""Ordlista och snabb mönstersökning.

Filformat (UTF-8, en rad per ord):

    ORD<TAB>poäng

Poängen (0–100) är valfri; saknas den blir den 50. Rader som börjar med # ignoreras.
Orden normaliseras vid inläsning, så en vanlig ordlista med gemener fungerar också.

Sökindexet håller, för varje ordlängd, en bitmängd per (position, bokstav).
Ett mönster som K?R?? löses genom att AND:a bitmängderna för K på plats 0 och
R på plats 2. Pythons heltal fungerar utmärkt som godtyckligt stora bitmängder.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Iterable

from .normalize import normalize_word

MIN_LEN = 2
MAX_LEN = 21
DEFAULT_SCORE = 50
WILDCARDS = {"?", ".", "_", " "}


@dataclass
class _Bucket:
    """Alla ord av en viss längd."""

    words: list[str] = field(default_factory=list)
    scores: list[int] = field(default_factory=list)
    # bits[pos][bokstav] -> heltal där bit i är satt om words[i][pos] == bokstav
    bits: list[dict[str, int]] = field(default_factory=list)
    all_bits: int = 0


class WordIndex:
    def __init__(self, entries: Iterable[tuple[str, int]], source: str = "okänd") -> None:
        self.source = source
        best: dict[str, int] = {}
        for raw, score in entries:
            word = normalize_word(raw)
            if word is None or not (MIN_LEN <= len(word) <= MAX_LEN):
                continue
            if score > best.get(word, -1):
                best[word] = score
        self._buckets: dict[int, _Bucket] = {}
        for word in sorted(best):
            bucket = self._buckets.setdefault(len(word), _Bucket())
            bucket.words.append(word)
            bucket.scores.append(best[word])
        for length, bucket in self._buckets.items():
            bucket.bits = [dict() for _ in range(length)]
            for i, word in enumerate(bucket.words):
                bit = 1 << i
                for pos, ch in enumerate(word):
                    table = bucket.bits[pos]
                    table[ch] = table.get(ch, 0) | bit
            bucket.all_bits = (1 << len(bucket.words)) - 1

    # ------------------------------------------------------------------ info
    def __len__(self) -> int:
        return sum(len(b.words) for b in self._buckets.values())

    def __contains__(self, word: str) -> bool:
        norm = normalize_word(word)
        if norm is None:
            return False
        bucket = self._buckets.get(len(norm))
        if bucket is None:
            return False
        return self.match_bits(norm) != 0

    def length_counts(self) -> dict[int, int]:
        return {length: len(b.words) for length, b in sorted(self._buckets.items())}

    def score(self, word: str) -> int:
        bucket = self._buckets.get(len(word))
        if bucket is None:
            return 0
        bits = self.match_bits(word)
        if not bits:
            return 0
        return bucket.scores[bits.bit_length() - 1]

    # ---------------------------------------------------------------- search
    def match_bits(self, pattern: str) -> int:
        """Bitmängd över ord som matchar mönstret (samma längd som mönstret)."""
        bucket = self._buckets.get(len(pattern))
        if bucket is None:
            return 0
        bits = bucket.all_bits
        for pos, ch in enumerate(pattern):
            if ch in WILDCARDS:
                continue
            bits &= bucket.bits[pos].get(ch, 0)
            if not bits:
                return 0
        return bits

    def words_from_bits(self, length: int, bits: int) -> list[str]:
        bucket = self._buckets.get(length)
        if bucket is None:
            return []
        out = []
        while bits:
            low = bits & -bits
            out.append(bucket.words[low.bit_length() - 1])
            bits ^= low
        return out

    def scored_from_bits(self, length: int, bits: int) -> list[tuple[str, int]]:
        bucket = self._buckets.get(length)
        if bucket is None:
            return []
        out = []
        while bits:
            low = bits & -bits
            i = low.bit_length() - 1
            out.append((bucket.words[i], bucket.scores[i]))
            bits ^= low
        return out

    def search(self, pattern: str, limit: int = 100) -> tuple[int, list[tuple[str, int]]]:
        """Returnera (antal träffar, de bästa träffarna sorterade på poäng)."""
        pattern = normalize_pattern(pattern)
        bits = self.match_bits(pattern)
        total = bits.bit_count()
        scored = self.scored_from_bits(len(pattern), bits)
        scored.sort(key=lambda ws: (-ws[1], ws[0]))
        return total, scored[:limit]

    def random_words(self, length: int, n: int, rng: random.Random | None = None) -> list[str]:
        bucket = self._buckets.get(length)
        if bucket is None:
            return []
        rng = rng or random.Random()
        return rng.sample(bucket.words, min(n, len(bucket.words)))


def normalize_pattern(pattern: str) -> str:
    """Gör om ett sökmönster till versaler med ? som jokertecken."""
    out = []
    for ch in pattern.strip():
        if ch in WILDCARDS or ch == "*":
            out.append("?")
            continue
        norm = normalize_word(ch)
        out.append(norm if norm and len(norm) == 1 else "?")
    return "".join(out)


# ------------------------------------------------------------------- loading
def read_wordlist(path: Path) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            score = DEFAULT_SCORE
            if len(parts) > 1:
                try:
                    score = max(0, min(100, int(parts[1])))
                except ValueError:
                    pass
            entries.append((parts[0], score))
    return entries


def sample_wordlist_path() -> Path:
    return Path(str(resources.files("crossword") / "data" / "sample_words.txt"))


def load_index(path: Path | None) -> WordIndex:
    """Läs in en ordlista. Utan sökväg används den inbyggda exempellistan."""
    if path is not None and path.exists():
        return WordIndex(read_wordlist(path), source=str(path))
    sample = sample_wordlist_path()
    return WordIndex(read_wordlist(sample), source="exempellista")


def write_wordlist(path: Path, entries: Iterable[tuple[str, int]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    n = 0
    with tmp.open("w", encoding="utf-8") as fh:
        for word, score in entries:
            fh.write(f"{word}\t{score}\n")
            n += 1
    tmp.replace(path)
    return n
