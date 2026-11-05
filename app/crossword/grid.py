"""Rutnät, numrering och luckor (slots).

Ett rutnät är en lista av rader där varje ruta är:
    "#"  svart ruta
    ""   tom ruta (även "." eller " " accepteras)
    "A"  en bokstav (A–Ö)

En lucka är en sammanhängande följd av minst två vita rutor vågrätt eller lodrätt.
Numreringen följer den vanliga konventionen: läs rad för rad, och varje ruta
som startar en vågrät eller lodrät lucka får nästa nummer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .normalize import normalize_letter

BLOCK = "#"
ACROSS = "across"
DOWN = "down"


@dataclass
class Slot:
    num: int
    direction: str
    row: int
    col: int
    length: int
    cells: list[tuple[int, int]] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.row},{self.col},{self.direction}"


def clean_grid(raw: list[list[str]]) -> list[list[str]]:
    """Normalisera inkommande rutnät till "#", "" eller en versal."""
    rows = len(raw)
    if rows == 0:
        raise ValueError("Rutnätet är tomt")
    cols = len(raw[0])
    out: list[list[str]] = []
    for r, row in enumerate(raw):
        if len(row) != cols:
            raise ValueError(f"Rad {r + 1} har fel längd")
        clean_row = []
        for cell in row:
            cell = (cell or "").strip()
            if cell == BLOCK:
                clean_row.append(BLOCK)
            elif cell in ("", ".", "?"):
                clean_row.append("")
            else:
                letter = normalize_letter(cell)
                if letter is None:
                    raise ValueError(f"Ogiltigt tecken i rutnätet: {cell!r}")
                clean_row.append(letter)
        out.append(clean_row)
    return out


def find_slots(grid: list[list[str]]) -> list[Slot]:
    rows, cols = len(grid), len(grid[0])

    def white(r: int, c: int) -> bool:
        return 0 <= r < rows and 0 <= c < cols and grid[r][c] != BLOCK

    slots: list[Slot] = []
    num = 0
    for r in range(rows):
        for c in range(cols):
            if not white(r, c):
                continue
            starts_across = not white(r, c - 1) and white(r, c + 1)
            starts_down = not white(r - 1, c) and white(r + 1, c)
            if not (starts_across or starts_down):
                continue
            num += 1
            if starts_across:
                cells = []
                cc = c
                while white(r, cc):
                    cells.append((r, cc))
                    cc += 1
                slots.append(Slot(num, ACROSS, r, c, len(cells), cells))
            if starts_down:
                cells = []
                rr = r
                while white(rr, c):
                    cells.append((rr, c))
                    rr += 1
                slots.append(Slot(num, DOWN, r, c, len(cells), cells))
    return slots


def slot_pattern(grid: list[list[str]], slot: Slot) -> str:
    return "".join(grid[r][c] or "?" for r, c in slot.cells)


def slot_answer(grid: list[list[str]], slot: Slot) -> str | None:
    pattern = slot_pattern(grid, slot)
    return None if "?" in pattern else pattern
