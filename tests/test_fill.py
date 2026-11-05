from crossword.fill import fill_grid
from crossword.grid import ACROSS, DOWN, clean_grid, find_slots, slot_answer
from crossword.wordlist import WordIndex

WORDS = ["NÄT", "ORO", "SAK", "NOS", "ÄRA", "TOK", "BIL", "ELD", "RAD", "BER", "ILA", "LDD"]


def idx():
    return WordIndex([(w, 50) for w in WORDS])


def test_numbering():
    g = clean_grid([["", "", "#"], ["", "", ""], ["#", "", ""]])
    slots = find_slots(g)
    got = [(s.num, s.direction, s.row, s.col, s.length) for s in slots]
    assert got == [
        (1, ACROSS, 0, 0, 2),
        (1, DOWN, 0, 0, 2),
        (2, DOWN, 0, 1, 3),
        (3, ACROSS, 1, 0, 3),
        (4, DOWN, 1, 2, 2),
        (5, ACROSS, 2, 1, 2),
    ]


def test_fill_3x3_all_words_valid():
    index = idx()
    res = fill_grid([[""] * 3 for _ in range(3)], index, timeout_s=5, seed=1)
    assert res.ok, res.message
    answers = [slot_answer(res.grid, s) for s in find_slots(res.grid)]
    assert all(a in index for a in answers)
    assert len(set(answers)) == len(answers)  # inga dubbletter


def test_fill_respects_locked_letters():
    res = fill_grid([["N", "", ""], ["", "", ""], ["", "", "K"]], idx(), timeout_s=5, seed=3)
    assert res.ok
    assert res.grid[0][0] == "N" and res.grid[2][2] == "K"


def test_fill_impossible_reports_failure():
    res = fill_grid([["X", "", ""], ["", "", ""], ["", "", ""]], idx(), timeout_s=2)
    assert not res.ok
    assert "Inget ord passar" in res.message


def test_fill_keeps_complete_unknown_words():
    # Användaren har skrivit in ett ord som inte finns – det ska få stå kvar.
    res = fill_grid([["Q", "Q", "#"], ["", "", "#"], ["#", "#", "#"]], WordIndex([("QA", 1), ("QB", 1), ("AB", 1)]), timeout_s=2)
    assert res.ok
    assert res.grid[0][:2] == ["Q", "Q"]


def test_invalid_char_rejected():
    import pytest

    with pytest.raises(ValueError):
        clean_grid([["1", ""], ["", ""]])
