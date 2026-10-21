import guida


def test_tutti_i_moduli_hanno_passi():
    for s in ("credit", "bp", "cf", "pv", "sc", "sl", "ga", "fo", "sx", "mz", "og", "rp", "gt", "ca", "dd"):
        serve, passi, _ = guida.PASSI[s]
        assert serve and len(passi) >= 4
        for t, x, c in passi:
            assert t and x
            assert c is None or c.split(":")[0] in ("demo", "dati", "salvato", "dossier")
