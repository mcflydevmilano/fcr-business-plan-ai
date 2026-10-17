import pytest

import ai


class _Resp:
    def __init__(self, text):
        self.text = text


class _Models:
    def __init__(self, comportamento):
        self.comportamento = comportamento
        self.chiamati = []

    def generate_content(self, model, contents, config):
        self.chiamati.append(model)
        r = self.comportamento(model)
        if isinstance(r, Exception):
            raise r
        return r


def _stub(monkeypatch, comportamento):
    models = _Models(comportamento)

    class Client:
        def __init__(self, api_key):
            self.models = models

    monkeypatch.setattr(ai.genai, "Client", Client)
    return models


def test_ripiego_su_404(monkeypatch):
    m = _stub(monkeypatch, lambda mod: Exception("404 NOT_FOUND") if mod == "vecchio" else _Resp("ok"))
    testo, usato = ai.genera("k", "x", "vecchio", ["alias"])
    assert (testo, usato) == ("ok", "alias") and m.chiamati == ["vecchio", "alias"]


def test_altri_errori_non_ripiegano(monkeypatch):
    m = _stub(monkeypatch, lambda mod: Exception("403 PERMISSION_DENIED"))
    with pytest.raises(Exception, match="403"):
        ai.genera("k", "x", "a", ["b"])
    assert m.chiamati == ["a"]


def test_tutti_404_rilancia(monkeypatch):
    _stub(monkeypatch, lambda mod: Exception("404 NOT_FOUND"))
    with pytest.raises(Exception, match="404"):
        ai.genera("k", "x", "a", ["b"])


def test_risposta_vuota(monkeypatch):
    _stub(monkeypatch, lambda mod: _Resp(""))
    with pytest.raises(RuntimeError):
        ai.genera("k", "x", "a")


def test_pulisci_testo():
    assert ai.pulisci_testo("## Titolo\n**grassetto** `x`") == "Titolo\ngrassetto x"


def test_errore_quota():
    assert ai.errore_quota(Exception("429 RESOURCE_EXHAUSTED. You exceeded your current quota"))
    assert ai.errore_quota(Exception("RESOURCE_EXHAUSTED"))
    assert not ai.errore_quota(Exception("403 PERMISSION_DENIED"))
