"""Import av SALDO (Språkbanken Text, Göteborgs universitet).

SALDO distribueras under licensen CC BY 4.0. Den som publicerar korsord byggda
på ordlistan bör ange källan, t.ex. "Ordlista: SALDO, Språkbanken Text".

Filen är i LMF-format (XML). Strukturen är ungefär:

    <LexicalEntry>
      <Lemma>
        <FormRepresentation>
          <feat att="writtenForm" val="fotboll"/>
          <feat att="partOfSpeech" val="nn"/>
          ...

Parsern letar bara efter feat-elementen writtenForm och partOfSpeech inom varje
LexicalEntry, så den tål små skillnader i nästling mellan versioner.

Användning:

    python -m crossword.saldo fetch  --out /data/words.tsv
    python -m crossword.saldo build  saldo.xml --out /data/words.tsv
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

from .normalize import normalize_word
from .wordlist import MAX_LEN, MIN_LEN, write_wordlist

SALDO_URL = "https://svn.spraakbanken.gu.se/sb-arkiv/pub/lmf/saldo/saldo.xml"

# Ordklasser i SALDO (urval). pm = egennamn, nna/nnm/... = förkortningar.
# Källa: SALDO:s taggset. Okända ordklasser får standardpoäng.
POS_SCORES = {
    "nn": 60,  # substantiv
    "vb": 55,  # verb
    "av": 55,  # adjektiv
    "ab": 50,  # adverb
    "pp": 45,  # preposition
    "pn": 45,  # pronomen
    "kn": 40,  # konjunktion
    "in": 40,  # interjektion
    "nl": 40,  # räkneord
    "pm": 30,  # egennamn
}
DEFAULT_POS_SCORE = 35
# Ordklasser som hoppas över som standard: egennamn och förkortningar.
SKIP_POS_DEFAULT = {"pm", "nna", "nnm", "ava", "vba", "pma", "aba", "pmm", "abm", "avm", "vbm", "ppm", "pnm", "knm", "inm", "nlm", "snm"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def iter_entries(xml_path: Path) -> Iterator[tuple[str, str]]:
    """Ge (skriftform, ordklass) för varje lexikonpost."""
    form: str | None = None
    pos = ""
    depth_in_entry = False
    for event, elem in ET.iterparse(xml_path, events=("start", "end")):
        tag = _local(elem.tag)
        if event == "start":
            if tag == "LexicalEntry":
                form, pos, depth_in_entry = None, "", True
            continue
        if tag == "feat" and depth_in_entry:
            att, val = elem.get("att"), elem.get("val")
            if att == "writtenForm" and form is None and val:
                form = val
            elif att == "partOfSpeech" and not pos and val:
                pos = val
        elif tag == "LexicalEntry":
            depth_in_entry = False
            if form:
                yield form, pos
            elem.clear()


def build_entries(
    xml_path: Path, include_names: bool = False, min_len: int = MIN_LEN, max_len: int = MAX_LEN
) -> list[tuple[str, int]]:
    skip = set() if include_names else SKIP_POS_DEFAULT
    best: dict[str, int] = {}
    for form, pos in iter_entries(xml_path):
        if pos in skip:
            continue
        # Flerordsuttryck ("i och med") passar inte i ett rutnät.
        if " " in form.strip():
            continue
        word = normalize_word(form)
        if word is None or not (min_len <= len(word) <= max_len):
            continue
        score = POS_SCORES.get(pos, DEFAULT_POS_SCORE)
        # Korta och medellånga ord är mest användbara; väldigt långa
        # sammansättningar sänks lite.
        if len(word) > 12:
            score -= 10
        if score > best.get(word, -1):
            best[word] = score
    return sorted(best.items())


def download(url: str, dest: Path, progress: bool = True) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "crossword-creator/0.1"})
    with urllib.request.urlopen(req, timeout=60) as resp, tempfile.NamedTemporaryFile(
        dir=dest.parent, delete=False
    ) as tmp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            tmp.write(chunk)
            done += len(chunk)
            if progress and total:
                print(f"\r  {done >> 20} / {total >> 20} MB", end="", file=sys.stderr, flush=True)
        tmp_path = Path(tmp.name)
    if progress:
        print(file=sys.stderr)
    shutil.move(tmp_path, dest)


def fetch_and_build(out: Path, url: str = SALDO_URL, keep_xml: bool = False, include_names: bool = False) -> int:
    xml_path = out.parent / "saldo.xml"
    if not xml_path.exists():
        print(f"Hämtar SALDO från {url} …", file=sys.stderr)
        download(url, xml_path)
    print("Bygger ordlista …", file=sys.stderr)
    n = write_wordlist(out, build_entries(xml_path, include_names=include_names))
    if not keep_xml:
        xml_path.unlink(missing_ok=True)
    print(f"Klart: {n} ord i {out}", file=sys.stderr)
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m crossword.saldo", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="Ladda ner SALDO och bygg ordlistan")
    p_fetch.add_argument("--out", type=Path, default=Path("/data/words.tsv"))
    p_fetch.add_argument("--url", default=SALDO_URL)
    p_fetch.add_argument("--keep-xml", action="store_true", help="Spara den nedladdade XML-filen")
    p_fetch.add_argument("--include-names", action="store_true", help="Ta med egennamn och förkortningar")

    p_build = sub.add_parser("build", help="Bygg ordlistan från en redan nedladdad saldo.xml")
    p_build.add_argument("xml", type=Path)
    p_build.add_argument("--out", type=Path, default=Path("/data/words.tsv"))
    p_build.add_argument("--include-names", action="store_true")

    args = parser.parse_args(argv)
    if args.cmd == "fetch":
        fetch_and_build(args.out, args.url, args.keep_xml, args.include_names)
    else:
        n = write_wordlist(args.out, build_entries(args.xml, include_names=args.include_names))
        print(f"Klart: {n} ord i {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
