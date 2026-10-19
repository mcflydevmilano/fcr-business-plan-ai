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


def test_503_riprova_e_poi_riesce(monkeypatch):
    stato = {"n": 0}

    def comp(mod):
        stato["n"] += 1
        return Exception("503 UNAVAILABLE. This model is currently experiencing high demand") if stato["n"] < 3 else _Resp("ok")

    m = _stub(monkeypatch, comp)
    testo, usato = ai.genera("k", "x", "principale", ["alias"], attese=(0, 0))
    assert (testo, usato) == ("ok", "principale") and m.chiamati == ["principale"] * 3


def test_503_persistente_passa_al_modello_di_ripiego(monkeypatch):
    m = _stub(monkeypatch, lambda mod: Exception("503 UNAVAILABLE") if mod == "principale" else _Resp("dal ripiego"))
    testo, usato = ai.genera("k", "x", "principale", ["alias"], attese=(0, 0))
    assert (testo, usato) == ("dal ripiego", "alias") and m.chiamati == ["principale"] * 3 + ["alias"]


def test_503_ovunque_solleva_e_viene_riconosciuto(monkeypatch):
    _stub(monkeypatch, lambda mod: Exception("503 UNAVAILABLE"))
    with pytest.raises(Exception) as e:
        ai.genera("k", "x", "p", ["a"], attese=(0,))
    assert ai.errore_sovraccarico(e.value) and ai.errore_temporaneo(e.value) and not ai.errore_quota(e.value)
    assert "sovraccarico" in ai.messaggio_errore(e.value)


def test_errori_non_temporanei_non_vengono_ripetuti(monkeypatch):
    m = _stub(monkeypatch, lambda mod: Exception("400 API key not valid"))
    with pytest.raises(Exception):
        ai.genera("k", "x", "p", ["a"], attese=(0, 0))
    assert m.chiamati == ["p"]
    assert not ai.errore_temporaneo(Exception("400 API key not valid"))
