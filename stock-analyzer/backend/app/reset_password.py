"""Réinitialise le mot de passe d'un compte (mot de passe oublié).

Usage, depuis le dossier backend :  python -m app.reset_password ton@mail.be
Toutes les sessions du compte sont fermées : il faudra se reconnecter partout.
"""
from __future__ import annotations

import sys
from getpass import getpass

from .database import get_conn, init_db
from .services import auth


def main() -> int:
    init_db()
    email = (sys.argv[1] if len(sys.argv) > 1 else input("Adresse mail du compte : ")).strip().lower()
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        print(f"Aucun compte pour {email}.")
        return 1
    while True:
        pw = getpass(f"Nouveau mot de passe ({auth.PASSWORD_MIN} caractères minimum, invisible à la frappe) : ")
        problem = auth.password_problem(pw)
        if problem:
            print(problem)
            continue
        if getpass("Confirme le mot de passe : ") != pw:
            print("Les deux saisies sont différentes, recommence.")
            continue
        break
    with get_conn() as conn:
        auth.set_password(conn, row["id"], pw)
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
    print("Mot de passe modifié. Reconnecte-toi dans l'application.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
