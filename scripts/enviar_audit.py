#!/usr/bin/env python3
"""
enviar_audit.py — Envía el resumen de la última auditoría de AUDIT_MENSUAL.md
al chat privado del administrador en Telegram (TELEGRAM_ADMIN_CHAT_ID).

Variables de entorno: TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID,
GITHUB_REPOSITORY (opcional, por defecto promosbanco/promosbanco.github.io).
"""
from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
AUDIT_PATH = ROOT / "AUDIT_MENSUAL.md"
DEFAULT_REPO = "promosbanco/promosbanco.github.io"
TIMEOUT = 20
MAX_LEN = 3850


def extraer_ultima_auditoria(texto: str) -> tuple[str, str]:
    """Devuelve (titulo, bloque_resumen) de la entrada mensual más reciente."""
    secciones = re.split(r"(?m)^## ", texto)
    if len(secciones) < 2:
        return ("Auditoría mensual PromosBanco", texto.strip())

    ultima = secciones[1].strip()
    lineas = ultima.splitlines()
    titulo = lineas[0].strip()
    cuerpo = "\n".join(lineas[1:]).strip()

    # Si existe una subsección "### Resumen para Telegram", usamos esa para que sea directo.
    m = re.search(r"(?ms)^###\s+Resumen para Telegram\s*\n(.*?)(?:^###\s+|^---\s*$|\Z)", cuerpo)
    if m and m.group(1).strip():
        resumen = m.group(1).strip()
    else:
        resumen = cuerpo

    return titulo, resumen


def markdown_simple_a_html(md: str) -> str:
    """Convierte markdown sencillo (títulos ###, listas y **negritas**) a HTML válido para Telegram."""
    salida = []
    for linea in md.splitlines():
        l = linea.rstrip()
        if re.match(r"^\s*---+\s*$", l):
            continue
        m_h3 = re.match(r"^###\s+(.+)$", l)
        if m_h3:
            salida.append(f"\n<b>{html.escape(m_h3.group(1).strip())}</b>")
            continue
        m_li = re.match(r"^\s*[-*]\s+(.+)$", l)
        if m_li:
            contenido = m_li.group(1).strip()
            contenido = html.escape(contenido)
            contenido = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", contenido)
            contenido = re.sub(r"`([^`]+)`", r"<code>\1</code>", contenido)
            salida.append(f"• {contenido}")
            continue
        esc = html.escape(l)
        esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc)
        esc = re.sub(r"`([^`]+)`", r"<code>\1</code>", esc)
        salida.append(esc)

    texto = "\n".join(salida).strip()
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    admin = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()
    repo = os.getenv("GITHUB_REPOSITORY", "").strip() or DEFAULT_REPO

    if not AUDIT_PATH.exists():
        print("[error] No existe AUDIT_MENSUAL.md", file=sys.stderr)
        return 1

    titulo, resumen_md = extraer_ultima_auditoria(AUDIT_PATH.read_text(encoding="utf-8"))
    cuerpo_html = markdown_simple_a_html(resumen_md)

    cabecera = f"📋 <b>{html.escape(titulo)}</b>\n\n"
    pie = "\n\n📄 Informe completo guardado en <code>AUDIT_MENSUAL.md</code>."
    max_cuerpo = MAX_LEN - len(cabecera) - len(pie)
    if len(cuerpo_html) > max_cuerpo:
        cuerpo_html = cuerpo_html[: max_cuerpo - 20].rsplit("\n", 1)[0] + "\n…(ver archivo completo)"

    mensaje = cabecera + cuerpo_html + pie

    if not token or not admin:
        print("[aviso] Falta TELEGRAM_BOT_TOKEN o TELEGRAM_ADMIN_CHAT_ID. Mensaje:\n" + mensaje)
        return 0

    url_github = f"https://github.com/{repo}/blob/main/AUDIT_MENSUAL.md"
    payload = {
        "chat_id": admin,
        "text": mensaje,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": {
            "inline_keyboard": [[{"text": "📄 Ver auditoría completa →", "url": url_github}]]
        },
    }

    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=TIMEOUT)
        datos = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not r.ok or not datos.get("ok"):
            print(f"[error] Telegram respondió {r.status_code}: {datos.get('description', 'sin descripción')}", file=sys.stderr)
            return 1
        msg_id = (datos.get("result") or {}).get("message_id", "?")
        print(f"[OK] Auditoría enviada al bot de Telegram (msg_id={msg_id})")
        return 0
    except requests.RequestException as e:
        print(f"[error] Fallo al contactar con Telegram: {e.__class__.__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
