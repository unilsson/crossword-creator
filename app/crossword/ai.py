"""AI-hjälp för ledtrådar, med utbytbara leverantörer.

Välj leverantör med miljövariabler:

    AI_PROVIDER=none        # standard: ingen AI, knappen säger att AI saknas
    AI_PROVIDER=anthropic   # Claude, kräver ANTHROPIC_API_KEY
    AI_PROVIDER=openai      # OpenAI eller annat OpenAI-kompatibelt API
                            # (Mistral, Ollama, LM Studio …), kräver
                            # OPENAI_API_KEY och ev. OPENAI_BASE_URL
    AI_MODEL=...            # valfritt, åsidosätter standardmodellen

Ny leverantör: skriv en klass med metoden `complete(system, prompt) -> str`
och lägg till den i `get_provider`.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

DIFFICULTIES = {
    "latt": "lätt – rak synonym eller enkel beskrivning, som i ett barnkorsord",
    "medel": "medel – som i ett vanligt dagstidningskorsord",
    "svar": "svår – gärna ordlek, dubbeltydighet eller oväntad vinkel, men fortfarande rättvis",
}

SYSTEM_PROMPT = (
    "Du är en erfaren svensk korsordskonstruktör. Du skriver korta, rättvisa och "
    "idiomatiska ledtrådar på svenska. En ledtråd får aldrig innehålla svaret eller "
    "en böjningsform av det. Om svaret är en böjd form (plural, bestämd form, "
    "verbform) ska ledtråden ha samma böjning. Svara ENDAST med en JSON-lista av strängar."
)


class AIError(Exception):
    pass


class Provider(Protocol):
    name: str
    model: str

    def complete(self, system: str, prompt: str) -> str: ...


def _post_json(url: str, headers: dict[str, str], body: dict, timeout: float = 60) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise AIError(f"AI-tjänsten svarade {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AIError(f"Kunde inte nå AI-tjänsten: {exc.reason}") from exc


@dataclass
class AnthropicProvider:
    api_key: str
    model: str = "claude-haiku-5-5"
    base_url: str = "https://api.anthropic.com"
    name: str = "anthropic"

    def complete(self, system: str, prompt: str) -> str:
        resp = _post_json(
            f"{self.base_url.rstrip('/')}/v1/messages",
            {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
            {
                "model": self.model,
                "max_tokens": 1024,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        parts = [b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text"]
        return "".join(parts)


@dataclass
class OpenAICompatibleProvider:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    name: str = "openai"

    def complete(self, system: str, prompt: str) -> str:
        headers = {"authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        resp = _post_json(
            f"{self.base_url.rstrip('/')}/chat/completions",
            headers,
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        try:
            return resp["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise AIError("Oväntat svar från AI-tjänsten") from exc


def get_provider(env: dict[str, str] | None = None) -> Provider | None:
    env = dict(os.environ) if env is None else env
    choice = env.get("AI_PROVIDER", "none").strip().lower()
    model = env.get("AI_MODEL", "").strip()
    if choice in ("", "none"):
        return None
    if choice == "anthropic":
        key = env.get("ANTHROPIC_API_KEY", "").strip()
        if not key:
            raise AIError("AI_PROVIDER=anthropic men ANTHROPIC_API_KEY saknas")
        return AnthropicProvider(api_key=key, **({"model": model} if model else {}))
    if choice == "openai":
        key = env.get("OPENAI_API_KEY", "").strip()
        base = env.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
        if not model:
            raise AIError("AI_PROVIDER=openai kräver AI_MODEL, t.ex. modellnamnet hos din leverantör")
        return OpenAICompatibleProvider(api_key=key, model=model, base_url=base)
    raise AIError(f"Okänd AI_PROVIDER: {choice}")


def build_clue_prompt(answer: str, difficulty: str, count: int, context: str = "") -> str:
    level = DIFFICULTIES.get(difficulty, DIFFICULTIES["medel"])
    lines = [
        f"Svar: {answer} ({len(answer)} bokstäver)",
        f"Svårighetsgrad: {level}",
        f"Ge {count} olika ledtrådar.",
    ]
    if context:
        lines.append(f"Sammanhang/tema: {context}")
    lines.append('Svara som JSON, t.ex. ["ledtråd 1", "ledtråd 2"].')
    return "\n".join(lines)


def parse_clue_list(text: str, answer: str) -> list[str]:
    """Plocka ut en lista av ledtrådar ur modellens svar och sålla bort fusk."""
    match = re.search(r"\[.*\]", text, re.S)
    items: list[str] = []
    if match:
        try:
            data = json.loads(match.group(0))
            items = [str(x).strip() for x in data if str(x).strip()]
        except json.JSONDecodeError:
            items = []
    if not items:
        items = [ln.strip(" -*•\t0123456789.)") for ln in text.splitlines() if ln.strip()]
    clean = [c for c in items if not _reveals_answer(c, answer)]
    # Ta bort dubbletter men behåll ordningen.
    seen: set[str] = set()
    out = []
    for c in clean:
        if c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out


def _reveals_answer(clue: str, answer: str) -> bool:
    """Grov kontroll: innehåller ledtråden svaret eller ordets stam?"""
    ans = answer.lower()
    tokens = re.findall(r"\w+", clue.lower())
    if len(ans) <= 3:
        return ans in tokens
    stem = ans[: len(ans) - 2] if len(ans) > 5 else ans[:-1]
    return any(t.startswith(stem) for t in tokens)


def suggest_clues(
    provider: Provider, answer: str, difficulty: str = "medel", count: int = 4, context: str = ""
) -> list[str]:
    text = provider.complete(SYSTEM_PROMPT, build_clue_prompt(answer, difficulty, count, context))
    return parse_clue_list(text, answer)
