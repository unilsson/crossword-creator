from pathlib import Path

from crossword.normalize import normalize_word
from crossword.wordlist import WordIndex, load_index, normalize_pattern, read_wordlist, write_wordlist


def test_normalize_keeps_swedish_letters():
    assert normalize_word("ärta") == "ÄRTA"
    assert normalize_word("Ålder") == "ÅLDER"
    assert normalize_word("öga") == "ÖGA"


def test_normalize_strips_other_accents_and_hyphens():
    assert normalize_word("idé") == "IDE"
    assert normalize_word("müsli") == "MUSLI"
    assert normalize_word("e-post") == "EPOST"


def test_normalize_rejects_bad_words():
    assert normalize_word("i och med") is None
    assert normalize_word("cd4") is None
    assert normalize_word("") is None


def test_pattern_search():
    idx = WordIndex([("katt", 70), ("kort", 50), ("kant", 60), ("bil", 50)])
    total, hits = idx.search("K??T")
    assert total == 3
    assert [w for w, _ in hits] == ["KATT", "KANT", "KORT"]  # sorterat på poäng
    total, hits = idx.search("k?r?")
    assert [w for w, _ in hits] == ["KORT"]
    assert idx.search("XYZ")[0] == 0
    assert idx.search("??")[0] == 0


def test_contains_and_dedup():
    idx = WordIndex([("Katt", 40), ("katt", 70), ("kät", 50)])
    assert len(idx) == 2
    assert "katt" in idx and "KÄT" in idx and "kot" not in idx
    assert idx.score("KATT") == 70


def test_normalize_pattern():
    assert normalize_pattern("k.t*") == "K?T?"
    assert normalize_pattern("å_ä") == "Å?Ä"


def test_roundtrip_file(tmp_path: Path):
    p = tmp_path / "w.tsv"
    write_wordlist(p, [("KATT", 70), ("HUND", 60)])
    assert read_wordlist(p) == [("KATT", 70), ("HUND", 60)]
    assert len(load_index(p)) == 2


def test_sample_list_loads():
    idx = load_index(None)
    assert idx.source == "exempellista"
    assert len(idx) > 300
