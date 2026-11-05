import pytest

from crossword import ai


class FakeProvider:
    name = "fake"
    model = "fake-1"

    def __init__(self, reply: str):
        self.reply = reply
        self.prompts: list[str] = []

    def complete(self, system: str, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.reply


def test_parse_json_list_and_filter_answer():
    reply = 'Här:\n["Spinner i soffan", "Katten jamar", "Husdjur med morrhår"]'
    clues = ai.suggest_clues(FakeProvider(reply), "KATT")
    assert clues == ["Spinner i soffan", "Husdjur med morrhår"]


def test_parse_fallback_lines():
    clues = ai.parse_clue_list("1. Lyser på dagen\n2. Värmer\n", "SOL")
    assert clues == ["Lyser på dagen", "Värmer"]


def test_short_answer_does_not_overfilter():
    # "EN" får inte filtrera bort ord som bara börjar på "en".
    assert ai.parse_clue_list('["Enkel artikel", "Barrträd"]', "EN") == ["Enkel artikel", "Barrträd"]


def test_get_provider_from_env():
    assert ai.get_provider({}) is None
    assert ai.get_provider({"AI_PROVIDER": "none"}) is None
    p = ai.get_provider({"AI_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "x"})
    assert p.name == "anthropic"
    p = ai.get_provider({"AI_PROVIDER": "openai", "OPENAI_API_KEY": "x", "AI_MODEL": "m", "OPENAI_BASE_URL": "http://localhost:11434/v1"})
    assert p.model == "m" and p.base_url.startswith("http://localhost")
    with pytest.raises(ai.AIError):
        ai.get_provider({"AI_PROVIDER": "anthropic"})
    with pytest.raises(ai.AIError):
        ai.get_provider({"AI_PROVIDER": "openai", "OPENAI_API_KEY": "x"})
