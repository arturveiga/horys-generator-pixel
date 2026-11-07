"""Desafio e prova HMAC-SHA256 (docs/protocolo.md). O token nunca trafega."""
from __future__ import annotations

import hashlib
import hmac
import secrets


def nonce() -> str:
    return secrets.token_hex(16)


def prova(token: str, nonce_: str) -> str:
    return hmac.new(token.encode("ascii"), nonce_.encode("ascii"), hashlib.sha256).hexdigest()


def confere(token: str, nonce_: str, recebida: str) -> bool:
    return hmac.compare_digest(prova(token, nonce_), str(recebida or ""))
