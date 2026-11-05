"""Automatisk fyllning av ett rutnät.

Klassisk villkorslösning med backtracking:

1. Välj den ofyllda lucka som har minst antal möjliga ord (MRV).
2. Prova kandidaterna i ordning efter poäng (med lite slump för variation).
3. Efter varje placerat ord: kontrollera att varje korsande lucka fortfarande
   har minst en kandidat (forward checking). Annars prova nästa ord.
4. Hittas inget ord: backa till föregående lucka.

Bokstäver som redan står i rutnätet behandlas som låsta. Luckor som redan är
helt ifyllda accepteras som de är, även om ordet saknas i ordlistan.
Samma ord används aldrig två gånger.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from .grid import Slot, clean_grid, find_slots, slot_answer, slot_pattern
from .wordlist import WordIndex

MAX_CANDIDATES_PER_STEP = 400


@dataclass
class FillResult:
    ok: bool
    grid: list[list[str]]
    message: str
    elapsed_ms: int
    steps: int


class _Timeout(Exception):
    pass


def fill_grid(
    raw_grid: list[list[str]],
    index: WordIndex,
    timeout_s: float = 10.0,
    seed: int | None = None,
    randomness: float = 15.0,
) -> FillResult:
    start = time.monotonic()
    grid = clean_grid(raw_grid)
    slots = find_slots(grid)
    rng = random.Random(seed)

    # Vilka luckor korsar en viss ruta?
    by_cell: dict[tuple[int, int], list[int]] = {}
    for i, slot in enumerate(slots):
        for cell in slot.cells:
            by_cell.setdefault(cell, []).append(i)

    crossings: list[list[int]] = []
    for i, slot in enumerate(slots):
        others = {j for cell in slot.cells for j in by_cell[cell] if j != i}
        crossings.append(sorted(others))

    used: set[str] = set()
    filled: list[bool] = [False] * len(slots)
    for i, slot in enumerate(slots):
        answer = slot_answer(grid, slot)
        if answer is not None:
            if answer in used:
                return _fail(grid, f"Ordet {answer} förekommer två gånger", start, 0)
            used.add(answer)
            filled[i] = True

    for i, slot in enumerate(slots):
        if not filled[i] and index.match_bits(slot_pattern(grid, slot)) == 0:
            return _fail(
                grid,
                f"Inget ord passar i {slot.num} {'vågrätt' if slot.direction == 'across' else 'lodrätt'} "
                f"({slot_pattern(grid, slot)})",
                start,
                0,
            )

    steps = 0
    deadline = start + timeout_s

    def candidates(slot: Slot) -> list[str]:
        bits = index.match_bits(slot_pattern(grid, slot))
        scored = index.scored_from_bits(slot.length, bits)
        scored = [(w, s) for w, s in scored if w not in used]
        # Poäng + slump; slumpen gör att man kan få olika fyllningar.
        scored.sort(key=lambda ws: -(ws[1] + rng.random() * randomness))
        return [w for w, _ in scored[:MAX_CANDIDATES_PER_STEP]]

    def place(slot: Slot, word: str) -> list[tuple[int, int]]:
        changed = []
        for (r, c), ch in zip(slot.cells, word):
            if grid[r][c] == "":
                grid[r][c] = ch
                changed.append((r, c))
        return changed

    def undo(changed: list[tuple[int, int]]) -> None:
        for r, c in changed:
            grid[r][c] = ""

    def choose_slot() -> tuple[int, int] | None:
        best_i, best_count = -1, math.inf
        for i, slot in enumerate(slots):
            if filled[i]:
                continue
            count = index.match_bits(slot_pattern(grid, slot)).bit_count()
            if count < best_count:
                best_i, best_count = i, count
                if count <= 1:
                    break
        return None if best_i < 0 else (best_i, int(best_count))

    def solve() -> bool:
        nonlocal steps
        steps += 1
        if steps % 64 == 0 and time.monotonic() > deadline:
            raise _Timeout
        choice = choose_slot()
        if choice is None:
            return True
        i, count = choice
        if count == 0:
            return False
        slot = slots[i]
        for word in candidates(slot):
            changed = place(slot, word)
            ok = True
            # Luckor som blev helt ifyllda av korsningar måste vara ord,
            # och övriga korsande luckor måste ha kvar minst en kandidat.
            completed: list[tuple[int, str]] = []
            for j in crossings[i]:
                if filled[j]:
                    continue
                pattern = slot_pattern(grid, slots[j])
                if "?" not in pattern:
                    if pattern in used or pattern == word or index.match_bits(pattern) == 0:
                        ok = False
                        break
                    completed.append((j, pattern))
                elif index.match_bits(pattern) == 0:
                    ok = False
                    break
            if ok:
                filled[i] = True
                used.add(word)
                for j, w in completed:
                    filled[j] = True
                    used.add(w)
                if solve():
                    return True
                filled[i] = False
                used.discard(word)
                for j, w in completed:
                    filled[j] = False
                    used.discard(w)
            undo(changed)
        return False

    try:
        ok = solve()
    except _Timeout:
        return _fail(clean_grid(raw_grid), f"Gav upp efter {timeout_s:.0f} s – prova fler svarta rutor eller en större ordlista", start, steps)
    except RecursionError:
        return _fail(clean_grid(raw_grid), "Rutnätet är för stort för fyllmotorn", start, steps)
    if not ok:
        return _fail(clean_grid(raw_grid), "Det finns ingen fyllning med nuvarande ordlista och låsta bokstäver", start, steps)
    return FillResult(True, grid, "Klart", _ms(start), steps)


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _fail(grid: list[list[str]], msg: str, start: float, steps: int) -> FillResult:
    return FillResult(False, grid, msg, _ms(start), steps)
