from pathlib import Path

from crossword.saldo import build_entries, iter_entries

XML = """<?xml version="1.0" encoding="UTF-8"?>
<LexicalResource>
  <Lexicon>
    <LexicalEntry>
      <Lemma><FormRepresentation>
        <feat att="writtenForm" val="fotboll"/>
        <feat att="partOfSpeech" val="nn"/>
      </FormRepresentation></Lemma>
      <Sense id="fotboll..1"><feat att="primary" val="boll..1"/></Sense>
    </LexicalEntry>
    <LexicalEntry>
      <Lemma><FormRepresentation>
        <feat att="writtenForm" val="springa"/>
        <feat att="partOfSpeech" val="vb"/>
      </FormRepresentation></Lemma>
    </LexicalEntry>
    <LexicalEntry>
      <Lemma><FormRepresentation>
        <feat att="writtenForm" val="Göteborg"/>
        <feat att="partOfSpeech" val="pm"/>
      </FormRepresentation></Lemma>
    </LexicalEntry>
    <LexicalEntry>
      <Lemma><FormRepresentation>
        <feat att="writtenForm" val="i och med"/>
        <feat att="partOfSpeech" val="kn"/>
      </FormRepresentation></Lemma>
    </LexicalEntry>
    <LexicalEntry>
      <Lemma><FormRepresentation>
        <feat att="writtenForm" val="idé"/>
        <feat att="partOfSpeech" val="nn"/>
      </FormRepresentation></Lemma>
    </LexicalEntry>
  </Lexicon>
</LexicalResource>
"""


def test_iter_entries(tmp_path: Path):
    p = tmp_path / "saldo.xml"
    p.write_text(XML, encoding="utf-8")
    assert list(iter_entries(p)) == [
        ("fotboll", "nn"),
        ("springa", "vb"),
        ("Göteborg", "pm"),
        ("i och med", "kn"),
        ("idé", "nn"),
    ]


def test_build_entries_filters(tmp_path: Path):
    p = tmp_path / "saldo.xml"
    p.write_text(XML, encoding="utf-8")
    words = dict(build_entries(p))
    assert set(words) == {"FOTBOLL", "SPRINGA", "IDE"}
    assert words["FOTBOLL"] > words["SPRINGA"]  # substantiv före verb
    with_names = dict(build_entries(p, include_names=True))
    assert "GÖTEBORG" in with_names
