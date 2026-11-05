# Korsordsmakaren

Prototyp för att konstruera svenska korsord av den klassiska typen, med numrerade
rutor och ledtrådarna listade bredvid rutnätet (alltså inte bildkorsord).

- **Rutnätseditor**: svarta rutor (med eller utan symmetri), automatisk numrering och tangentbordsnavigering.
- **Ordförslag**: visar ord från ordlistan som passar mönstret i den markerade luckan.
- **Automatisk fyllning**: fyller resten av rutnätet. Bokstäver du själv skrivit in räknas som låsta.
- **Ordkontroll**: ifyllda ord som saknas i ordlistan markeras.
- **Ledtrådar**: vågrätt och lodrätt, med AI-förslag på tre svårighetsnivåer (valfritt).
- **Spara och öppna** som JSON-fil. Arbetet sparas också automatiskt i webbläsaren.
- **Utskrift**: tomt rutnät med nummer och ledtrådar.

## Kom igång

```bash
git clone https://github.com/unilsson/crossword-creator.git
cd crossword-creator
cp .env.example .env        # valfritt, för AI-inställningar
docker compose up -d --build
```

Öppna sedan **http://localhost:8083**.

Första gången laddar containern ner ordlistan SALDO (ca 70 MB) och bygger ett
ordindex. Det tar någon minut. Under tiden används en liten inbyggd exempellista,
och statusraden högst upp visar när SALDO är klar. Ordlistan sparas i
Docker-volymen `korsord-data`, så hämtningen görs bara en gång.

Vill du inte hämta automatiskt sätter du `AUTO_FETCH_SALDO=0` i `.env`. Då kan
du starta hämtningen med knappen **Hämta SALDO** i gränssnittet, eller med:

```bash
docker compose exec korsord python -m crossword.saldo fetch
```

### Använda gränssnittet

| Gör så här | Resultat |
|---|---|
| Klicka på en ruta | Markerar den; klicka igen för att byta riktning |
| Skriv bokstäver | Fyller i och hoppar till nästa ruta |
| `.` eller **Rita svarta** | Växlar svart ruta (speglas om *Symmetri* är på) |
| `Mellanslag` | Byter riktning vågrätt/lodrätt |
| `Tab` / `Shift+Tab` | Nästa/föregående ord |
| Klicka på ett ordförslag | Sätter in ordet i luckan |
| **Fyll automatiskt** | Fyller tomma rutor; autofyllda bokstäver visas i blått |
| **Töm autofyllt** | Tar bort bara det fyllmotorn satt in |

Tips: ju fler svarta rutor och ju kortare ord, desto lättare är det att fylla.
Stora öppna ytor utan svarta rutor är svåra, och fyllmotorn ger upp efter 15 sekunder.
Prova då att lägga till fler svarta rutor eller att låsa några bra ord först.

## AI för ledtrådar

AI är avstängt som standard. Slå på det i `.env` och starta om med
`docker compose up -d`.

**Claude (Anthropic):**
```env
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
# AI_MODEL=claude-haiku-5-5   (standard; byt t.ex. till claude-sonnet-5-5)
```

**OpenAI eller annat OpenAI-kompatibelt API** (Mistral, Groq, LM Studio, Ollama …):
```env
AI_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
AI_MODEL=<modellnamn>
```

För Ollama på samma dator: `OPENAI_BASE_URL=http://host.docker.internal:11434/v1`.
På Linux behöver du då också lägga till `extra_hosts: ["host.docker.internal:host-gateway"]`
under tjänsten i `docker-compose.yml`.

API-nycklarna stannar i servern och skickas aldrig till webbläsaren. AI:n används
bara för ledtrådar. Rutnätet fylls av en deterministisk motor och alla ord kommer
från ordlistan.

## Ordlistan

Standardkällan är **SALDO** från Språkbanken Text vid Göteborgs universitet,
licensierad under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Publicerar du korsord gjorda med appen: ange *"Ordlista: SALDO, Språkbanken Text"*.
Utskriften lägger till den raden automatiskt när SALDO används.

Importen:
- tar grundformer (inte böjningsformer),
- hoppar över egennamn, förkortningar och flerordsuttryck,
- gör om allt till versaler, behåller Å/Ä/Ö och tar bort övriga accenter (IDÉ → IDE),
- ger varje ord en poäng efter ordklass, så att substantiv prioriteras före t.ex. konjunktioner.

Du kan också använda en egen ordlista: en textfil med ett ord per rad,
valfritt följt av tabb och poäng 0–100. Peka ut den med `WORDLIST_PATH`.

```bash
# Bygg från en redan nedladdad saldo.xml, inklusive egennamn
python -m crossword.saldo build saldo.xml --out data/words.tsv --include-names
```

## Utveckling utan Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest                       # tester
PYTHONPATH=app WORDLIST_PATH=data/words.tsv python -m crossword.server
```

Gränssnittet är vanlig HTML, CSS och JavaScript i `app/crossword/static/` och
kräver inget byggsteg. Ladda bara om sidan efter en ändring.

### Struktur

```
app/crossword/
  normalize.py   bokstavsregler (Å/Ä/Ö, accenter, bindestreck)
  wordlist.py    ordindex med bitmängder per (position, bokstav)
  saldo.py       nedladdning och import av SALDO
  grid.py        rutnät, numrering, luckor
  fill.py        fyllmotor (backtracking + forward checking)
  ai.py          AI-leverantörer och ledtrådsprompt
  server.py      JSON-API + statiska filer
  static/        gränssnittet
tests/           pytest
```

### API

| Metod | Sökväg | Beskrivning |
|---|---|---|
| GET | `/api/status` | Ordlista, hämtningsstatus, AI-inställning |
| GET | `/api/words?pattern=K?T?` | Ord som matchar mönstret, sorterade på poäng |
| POST | `/api/fill` | `{grid, timeout, seed}` → ifyllt rutnät |
| POST | `/api/check` | `{grid}` → luckor och om orden finns i ordlistan |
| POST | `/api/clues` | `{answer, difficulty, count, context}` → ledtrådsförslag |
| POST | `/api/wordlist/fetch` | Starta SALDO-hämtning i bakgrunden |

I rutnätet är `"#"` en svart ruta, `""` en tom ruta och annars en bokstav.

## Nästa steg (idéer)

- Ordfrekvenser från Språkbankens korpusar, för bättre poäng.
- Egna svartlistor och favoritord.
- Temaord via AI, filtrerade mot ordlistan.
- AI-granskning av ledtrådar (entydighet, rätt böjning).
- Export till PDF och ipuz, och en spelbar webbversion.
- Bildkorsord (ledtrådar i rutorna med pilar).
