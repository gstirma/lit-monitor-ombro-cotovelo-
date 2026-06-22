"""Envio do digest por e-mail via SMTP. Credenciais via variáveis de ambiente."""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def send_email(html: str, subject: str) -> bool:
    """Envia o digest. Retorna True se enviado, False se faltam credenciais."""
    host = _env("SMTP_HOST", "smtp.gmail.com")
    port = int(_env("SMTP_PORT", "465") or "465")
    user = _env("SMTP_USER")
    password = _env("SMTP_PASS")
    sender = _env("EMAIL_FROM") or user
    to = _env("EMAIL_TO")

    if not (user and password and to):
        print("[email] credenciais/destinatário ausentes (SMTP_USER/SMTP_PASS/EMAIL_TO) "
              "— pulando envio. O HTML segue salvo como artifact.")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("Vigilância Ombro & Cotovelo", sender))
    msg["To"] = to
    msg.set_content("Seu cliente não suporta HTML. Veja o anexo/versão web.")
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=60) as s:
            s.login(user, password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=60) as s:
            s.ehlo()
            s.starttls(context=context)
            s.login(user, password)
            s.send_message(msg)

    print(f"[email] enviado para {to} via {host}:{port}")
    return True
