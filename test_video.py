import video


def test_url_valido():
    assert video.url_valido("https://youtu.be/abc") == "https://youtu.be/abc"
    assert video.url_valido("http://x.it") == ""
    assert video.url_valido("javascript:alert(1)") == ""
    assert video.url_valido("https://a b.it") == ""


def test_salva_carica_e_riserva(tmp_path):
    p = str(tmp_path / "v.db")
    video.salva({"ru": "https://youtu.be/1", "pp_fatture": "https://youtu.be/2", "sc": "javascript:x"}, "lorenzo", p)
    assert video.link("ru", path=p) == "https://youtu.be/1"
    assert video.link("pp_cantieri", ["ru"], path=p) == "https://youtu.be/1"   # riserva: video del primo strumento
    assert video.link("pp_fatture", ["sc"], path=p) == "https://youtu.be/2"
    assert video.link("sc", path=p) == ""                                      # indirizzo non valido scartato
    assert video.link("bk", path=p) == ""
