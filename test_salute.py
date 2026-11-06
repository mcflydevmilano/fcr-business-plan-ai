import salute


def test_memoria_e_giudizio():
    m = salute.memoria()
    if m:
        assert m["totale"] > 0 and 0 <= m["perc"] <= 100
    assert salute.giudizio_memoria(10)[0] == "ok"
    assert salute.giudizio_memoria(75)[0] == "attenzione"
    assert salute.giudizio_memoria(95)[0] == "critico"


def test_durata():
    assert salute.durata_it(90) == "1 min"
    assert salute.durata_it(3 * 3600 + 120) == "3 h 2 min"
    assert salute.durata_it(2 * 86400 + 3600) == "2 g 1 h"


def test_prova_conserva_e_confronta(tmp_path):
    p = str(tmp_path / "s.db")
    a = salute.prova(p)
    b = salute.prova(p)
    assert a["ram_mbs"] > 0 and a["db_scrivi_ms"] is not None
    assert len(salute.storico(p)) == 2
    assert set(salute.confronto(b, a)) >= {"cpu_s", "db_leggi_ms"}


def test_confronto_verso():
    v = {"cpu_s": 2.0, "ram_mbs": 1000, "disco_w": 100, "disco_r": 100, "db_scrivi_ms": 10, "db_leggi_ms": 1}
    n = {"cpu_s": 1.0, "ram_mbs": 2000, "disco_w": 100, "disco_r": 100, "db_scrivi_ms": 10, "db_leggi_ms": 1}
    c = salute.confronto(n, v)
    assert c["cpu_s"] == 50 and c["ram_mbs"] == 100 and c["disco_w"] == 0
