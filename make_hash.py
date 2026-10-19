"""
Genera l'hash di una password da incollare nei secrets di Streamlit, cosi' la password non compare mai in chiaro.

Uso:   python make_hash.py            (chiede la password senza mostrarla)
Poi nei secrets:
    [users.mario]
    hash = "pbkdf2_sha256$..."
    ruolo = "admin"
"""
import getpass

import auth

if __name__ == "__main__":
    pw = getpass.getpass("Password: ")
    err = auth.valida_password(pw)
    if err:
        raise SystemExit(err)
    if getpass.getpass("Ripeti la password: ") != pw:
        raise SystemExit("Le password non coincidono.")
    print(auth.hash_password(pw))
