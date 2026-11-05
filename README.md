# Korsordsmakaren

Prototyp för att konstruera svenska korsord av den klassiska typen, med numrerade
rutor och ledtrådarna listade bredvid rutnätet (alltså inte bildkorsord).

- **Rutnätseditor**: svarta rutor, automatisk numrering och tangentbordsnavigering.
- **Ordförslag**: visar ord från ordlistan som passar mönstret i den markerade luckan.
- **Automatisk fyllning**: fyller resten av rutnätet. Bokstäver du själv skrivit in räknas som låsta.
- **Ordkontroll**: ifyllda ord som saknas i ordlistan markeras.
- **Ledtrådar**: vågrätt och lodrätt, med AI-förslag på tre svårighetsnivåer (valfritt).
- **Spara och öppna** som JSON-fil. Arbetet sparas också automatiskt i webbläsaren.
- **Utskrift och PDF**: tomt rutnät med nummer och ledtrådar på ett A4.

## Kom igång

```bash
git clone git@github.com:unilsson/crossword-creator.git
# eller via HTTPS: git clone https://github.com/unilsson/crossword-creator.git
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

### Stoppa, starta och uppdatera

```bash
docker compose down              # stoppa (ordlistan finns kvar i volymen)
docker compose up -d             # starta igen
git pull && docker compose up -d --build   # hämta senaste versionen
```

Ladda om sidan med `Ctrl+Shift+R` (`Cmd+Shift+R` på Mac) efter en uppdatering,
så att webbläsaren inte använder gamla filer.

## Så gör du ett korsord

**1. Vänta in ordlistan.** Uppe till höger står hur många ord som är inlästa.
Med exempellistan (cirka 450 ord) går det bara att fylla mycket små rutnät.
Vänta tills SALDO är klar, ungefär 100 000 ord.

**2. Skapa rutnätet.** Ange rader och kolumner (till exempel 9 × 9) och klicka
**Nytt rutnät**.

**3. Placera svarta rutor.** Klicka på en ruta och tryck `.` (punkt). Tryck `.`
igen för att ta bort en svart ruta du satt fel. Alternativt slår du på **Rita svarta**
och klickar direkt i rutnätet. Ett klick gör rutan svart, nästa gör den vit igen.

*Symmetri* (avstängt som standard) speglar varje svart ruta till motsatt
hörn, som i engelska tidningskorsord. Låt den vara av om du vill placera rutorna fritt.

**4. Lägg in egna ord (valfritt).** Klicka på startrutan och skriv. Klicka en gång
till på samma ruta, eller tryck mellanslag, för att byta mellan vågrätt och lodrätt.
Panelen till höger visar ord som passar i den markerade luckan. Klicka på ett
ord för att sätta in det. Bokstäver du själv skrivit in visas i svart och är låsta.

**5. Fyll resten automatiskt.** Klicka **Fyll automatiskt**. Ifyllda bokstäver
visas i blått.
- Gillar du inte resultatet: klicka **Töm autofyllt** och fyll igen. Varje gång blir det en ny variant.
- Vill du behålla ett autofyllt ord: skriv över dess bokstäver med samma bokstäver,
  så blir de låsta.
- Om fyllningen misslyckas: lägg till svarta rutor eller ta bort ett låst ord som
  är svårt att bygga runt. Stora öppna ytor är svåra, och motorn ger upp efter 15 sekunder.

Ord som saknas i ordlistan markeras med rött i ledtrådslistan,
till exempel egennamn. Det är bara en varning: ordet får stå kvar.

**6. Skriv ledtrådar.** Varje ord har en textruta under *Vågrätt* och *Lodrätt*.
Med AI påslaget (se nedan) ger **✨ Förslag** fyra förslag. Klicka på ett för att
använda det. Svårighetsgraden väljer du med *AI-nivå*.

**7. Spara.** Allt sparas automatiskt i webbläsaren. **Spara fil** laddar ner
korsordet som JSON. Det är den riktiga säkerhetskopian och öppnas igen med
**Öppna fil**.

**8. Skriv ut eller gör PDF.** **Skriv ut** ger rutnätet utan facit, med nummer
och ledtrådar i två kolumner på ett A4. Välj *Spara som PDF* i utskriftsdialogen
för att få en PDF. Om sidhuvud eller sidfot med URL och datum ändå syns: stäng av
*Skriv ut sidhuvud och sidfot* i dialogens fler inställningar.

### Kortkommandon

| Tangent | Gör |
|---|---|
| Bokstäver | Skriver och går till nästa ruta |
| `.` | Växlar svart ruta |
| `Mellanslag` | Byter riktning vågrätt/lodrätt |
| Piltangenter | Flyttar markören |
| `Tab` / `Shift+Tab` | Nästa/föregående ord |
| `Backsteg` | Raderar och går bakåt |
| `Delete` | Raderar utan att flytta |

## Felsökning

| Problem | Lösning |
|---|---|
| Porten är upptagen | Ändra `PORT` i `.env`, t.ex. `PORT=8090`, och kör `docker compose up -d` |
| SALDO blir aldrig klar | Håll muspekaren över statusraden för att se felet. Kör `docker compose logs korsord`. Starta om hämtningen med knappen **Hämta SALDO** |
| Gamla knappar eller utseende efter uppdatering | Ladda om med `Ctrl+Shift+R` |
| Vill börja om med ordlistan | `docker compose down -v` tar bort volymen. Nästa start hämtar SALDO på nytt |
| AI-knappen ger fel | Kontrollera `.env` och statusraden (*AI: …*). Felet från AI-tjänsten visas i en ruta längst ner |

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
- Facitutskrift, export till ipuz och en spelbar webbversion.
- Bildkorsord (ledtrådar i rutorna med pilar).
