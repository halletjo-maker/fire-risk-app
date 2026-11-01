"""Remettre une sauvegarde reçue par mail.

Sur le serveur (Termius), après avoir copié le fichier .mm100 sur la machine :
    sudo systemctl stop analyse-boursiere
    cd /opt/analyse-boursiere/stock-analyzer/backend
    sudo -u analyse /opt/analyse-boursiere/venv/bin/python -m app.restore_backup /chemin/mm100-sauvegarde-AAAA-MM-JJ.mm100
    sudo systemctl start analyse-boursiere

L'ancienne base est gardée à côté (…db.avant-restauration).
"""
from __future__ import annotations

import getpass
import gzip
import os
import sqlite3
import sys
from pathlib import Path

from .config import get_settings
from .services.backup import decrypt


def restore(file: Path, passphrase: str, target: Path) -> Path:
    data = gzip.decompress(decrypt(file.read_bytes(), passphrase))
    tmp = target.with_name(target.name + ".restauration")
    tmp.write_bytes(data)
    with sqlite3.connect(tmp) as conn:  # vérifie que c'est bien une base lisible
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            tmp.unlink()
            raise ValueError("La sauvegarde est abîmée.")
    if target.exists():
        os.replace(target, target.with_name(target.name + ".avant-restauration"))
    for suffix in ("-wal", "-shm"):
        Path(str(target) + suffix).unlink(missing_ok=True)
    os.replace(tmp, target)
    return target


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    target = get_settings().database_path
    try:
        restore(Path(sys.argv[1]), getpass.getpass("Mot de passe de sauvegarde : "), target)
    except (OSError, ValueError) as exc:
        print(f"Échec : {exc}")
        return 1
    print(f"Sauvegarde remise en place : {target}. Redémarre l'application.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
