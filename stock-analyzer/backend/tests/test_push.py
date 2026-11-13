"""Notifications sur le téléphone : abonnement, réglages par sorte, appareils morts effacés."""
import json

PW = "correct-horse-42"
SUB = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc123", "keys": {"p256dh": "B" * 87, "auth": "a" * 22}}


def test_subscribe_kinds_and_delivery(auth_client, monkeypatch):
    from app.services import push

    c = auth_client
    c.post("/users/register", json={"email": "jean@exemple.be", "password": PW})
    st = c.get("/push").json()
    assert st["devices"] == 0 and len(st["public_key"]) > 80 and st["kinds"] == {"alerts": True, "trades": True, "access": True}
    assert c.get("/push").json()["public_key"] == st["public_key"]   # clés gardées
    assert c.post("/push/test").status_code == 409                    # aucun appareil
    assert c.post("/push/subscribe", json=SUB).json()["devices"] == 1
    assert c.post("/push/subscribe", json=SUB).json()["devices"] == 1  # même appareil : pas de doublon

    sent = []
    monkeypatch.setattr(push, "_deliver", lambda sub, payload, key: sent.append(json.loads(payload)) or True)
    assert c.post("/push/test").json() == {"sent": 1}
    assert sent[-1]["title"] == "MM100 ✅"

    uid = 1
    assert push.notify(uid, "trades", "Achat", "ASML") == 1
    c.put("/push/kinds", json={"trades": False})
    assert push.notify(uid, "trades", "Achat", "ASML") == 0          # désactivé par l'utilisateur
    assert push.notify(uid, "alerts", "Signal", "ASML") == 1

    monkeypatch.setattr(push, "_deliver", lambda sub, payload, key: False)  # appareil désinstallé (410)
    assert push.notify(uid, "alerts", "Signal", "ASML") == 0
    assert c.get("/push").json()["devices"] == 0


def test_real_vapid_signature(auth_client, monkeypatch):
    """La clé générée est acceptée par pywebpush (requête simulée, pas de réseau)."""
    import requests

    from app.services import push

    c = auth_client
    c.post("/users/register", json={"email": "jean@exemple.be", "password": PW})
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    import base64
    k = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": base64.urlsafe_b64encode(k).rstrip(b"=").decode(),
                                                           "auth": base64.urlsafe_b64encode(b"0123456789abcdef").rstrip(b"=").decode()}}
    c.post("/push/subscribe", json=sub)
    calls = []

    class Resp:
        status_code = 201
        text = ""
        headers = {}

    def fake_post(url, data=None, headers=None, timeout=None, **kw):
        calls.append(headers)
        return Resp()
    monkeypatch.setattr(requests, "post", fake_post)
    assert push.notify(1, "alerts", "Signal", "ASML") == 1
    assert calls and calls[0]["Authorization"].startswith("vapid t=")
