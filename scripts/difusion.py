#!/usr/bin/env python3
"""
difusion.py — Publica en el canal de Telegram SOLO las ofertas nuevas.

Una oferta se considera nueva si está activa, no ha caducado y su `id` no
aparece todavía en /data/publicadas.json. Tras publicarla se añade a esa lista,
así nunca se repite un aviso.

Formato corto y fácil de leer (también sirve para copiar y pegar en foros):

    🏦 Openbank
    💶 200 € + 3,25% TAE

    ✅ Sin nómina: Bizum y 2 recibos
    ⏰ Hasta el 30 de noviembre
    🔑 Código: OPEN325

    👉 https://promosbanco.github.io

Variables de entorno: TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID,
TELEGRAM_ADMIN_CHAT_ID, SITE_URL.
"""
from __future__ import annotations

import html
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parent.parent
OFERTAS_PATH = ROOT / "data" / "ofertas.json"
PUBLICADAS_PATH = ROOT / "data" / "publicadas.json"
DEFAULT_SITE_URL = "https://promosbanco.github.io"
TIMEOUT = 20
MAX_POR_EJECUCION = 3

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
PAISES = {"DE": "IBAN alemán", "NL": "IBAN holandés", "NO": "IBAN noruego", "FR": "IBAN francés"}


def cargar(ruta: Path, defecto: Any) -> Any:
    if not ruta.exists():
        return defecto
    return json.loads(ruta.read_text(encoding="utf-8"))


def guardar(ruta: Path, datos: Any) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fecha_larga(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
        return f"{d.day} de {MESES[d.month - 1]}"
    except (TypeError, ValueError):
        return iso


def caducada(o: dict, hoy: str) -> bool:
    fin = (o.get("fecha_fin_promo") or "").strip()
    return bool(fin) and fin < hoy


def base_url(site_url: str) -> str:
    return (site_url or DEFAULT_SITE_URL).strip().rstrip("/") or DEFAULT_SITE_URL


def formatear_oferta(o: dict, site_url: str) -> str:
    esc = html.escape
    gancho = (o.get("gancho") or o.get("etiqueta_promo") or o.get("nombre") or "").strip()
    requisito = (o.get("requisito_corto") or o.get("requisitos_resumen") or "").strip()
    pais = (o.get("pais_iban") or "").upper()
    if pais in PAISES and "iban" not in requisito.lower():
        requisito = f"{requisito} ({PAISES[pais]})" if requisito else PAISES[pais]

    lineas = [f"🏦 <b>{esc(o.get('entidad', ''))}</b>", f"💶 <b>{esc(gancho)}</b>", ""]
    if requisito:
        lineas.append(f"✅ {esc(requisito)}")
    if o.get("fecha_fin_promo"):
        lineas.append(f"⏰ Hasta el {esc(fecha_larga(o['fecha_fin_promo']))}")
    if o.get("codigo_promo"):
        lineas.append(f"🔑 Código: <code>{esc(o['codigo_promo'])}</code>")
    lineas += ["", f"👉 {esc(base_url(site_url))}"]
    return "\n".join(lineas)


def botones(o: dict, site_url: str) -> Dict[str, Any]:
    query = urlencode({
        "o": o.get("id", ""),
        "utm_source": "telegram",
        "utm_medium": "canal",
        "utm_campaign": o.get("utm_campaign") or o.get("id", "oferta"),
    })
    return {"inline_keyboard": [[{"text": "Ver oferta →", "url": f"{base_url(site_url)}/?{query}"}]]}


def telegram(metodo: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Llama a la Bot API. Nunca imprime el token."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", json=payload, timeout=TIMEOUT)
        datos = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not r.ok or not datos.get("ok"):
            print(f"[error] Telegram {metodo} -> {r.status_code}: {datos.get('description', 'sin descripción')}", file=sys.stderr)
            return None
        res = datos.get("result")
        return res if isinstance(res, dict) else {"ok": True}
    except requests.RequestException as e:
        print(f"[error] Fallo al contactar con Telegram: {e.__class__.__name__}", file=sys.stderr)
        return None


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    canal = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    admin = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()
    site_url = os.getenv("SITE_URL", "").strip() or DEFAULT_SITE_URL
    hoy = date.today().isoformat()

    ofertas: List[dict] = cargar(OFERTAS_PATH, [])
    publicadas: List[str] = cargar(PUBLICADAS_PATH, [])
    ya = set(publicadas)

    nuevas = [o for o in ofertas if o.get("activa") is True and not caducada(o, hoy) and o.get("id") not in ya]
    if not nuevas:
        print("No hay ofertas nuevas. No se publica nada.")
        return 0

    lote = nuevas[:MAX_POR_EJECUCION]
    if not token or not canal:
        print(f"[aviso] {len(nuevas)} oferta(s) nueva(s) pendientes, pero falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHANNEL_ID.")
        for o in lote:
            print("----\n" + formatear_oferta(o, site_url))
        return 0

    ok: List[dict] = []
    fallidas: List[str] = []
    for o in lote:
        res = telegram("sendMessage", {
            "chat_id": canal,
            "text": formatear_oferta(o, site_url),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": botones(o, site_url),
        })
        if res is not None:
            publicadas.append(o["id"])
            ok.append(o)
            print(f"[OK] Oferta nueva publicada: {o['id']} (msg_id={res.get('message_id', '?')})")
        else:
            fallidas.append(o.get("id", "?"))
            print(f"[KO] No se pudo publicar: {o.get('id')}")

    if ok:
        guardar(PUBLICADAS_PATH, publicadas)
        if admin:
            texto = "✅ <b>Publicado en el canal</b>\n" + "\n".join(
                f"• {html.escape(o.get('entidad', ''))}: {html.escape(o.get('gancho', ''))}" for o in ok
            )
            restantes = len(nuevas) - len(lote)
            if restantes > 0:
                texto += f"\n\nQuedan {restantes} para la próxima ejecución."
            if fallidas:
                texto += "\n\n⚠️ Fallaron: " + ", ".join(html.escape(f) for f in fallidas)
            telegram("sendMessage", {"chat_id": admin, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True})

    return 1 if fallidas else 0


if __name__ == "__main__":
    sys.exit(main())
