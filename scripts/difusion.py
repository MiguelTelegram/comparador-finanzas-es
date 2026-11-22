#!/usr/bin/env python3
"""
difusion.py — Publica en el canal de Telegram únicamente ofertas reales curadas.

Mensajes ultrasimples en español llano (3 bloques cortos sin jerga ni fuentes)
con enlace corto visible (https://migueltelegram.github.io) listos para copiar
y pegar directamente en foros.

Variables de entorno: TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID,
TELEGRAM_ADMIN_CHAT_ID, SITE_URL.
"""
from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

ROOT = Path(__file__).resolve().parent.parent
OFERTAS_PATH = ROOT / "data" / "ofertas.json"
DEFAULT_SITE_URL = "https://migueltelegram.github.io"
TIMEOUT = 20


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def num(valor: Any) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def fmt_num(valor: float, decimales: int = 2) -> str:
    """Formato español: 20.000,50"""
    texto = f"{valor:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if decimales and texto.endswith("," + "0" * decimales):
        texto = texto[: -(decimales + 1)]
    return texto


def fmt_eur(valor: float) -> str:
    return f"{fmt_num(valor)} €"


def url_corta_visible(site_url: str) -> str:
    """URL limpia y corta para copiar y pegar en foros."""
    base = (site_url or DEFAULT_SITE_URL).strip().rstrip("/")
    return base or DEFAULT_SITE_URL


def url_boton(site_url: str, oferta_id: Optional[str] = None) -> str:
    base = url_corta_visible(site_url)
    if oferta_id:
        return f"{base}/?o={oferta_id}"
    return f"{base}/"


def con_utm(url: str, campaign: str, source: str = "telegram", medium: str = "canal") -> Optional[str]:
    if not url or not url.startswith(("http://", "https://")):
        return None
    partes = urlsplit(url)
    query = dict(parse_qsl(partes.query, keep_blank_values=True))
    query.update({"utm_source": source, "utm_medium": medium, "utm_campaign": campaign})
    return urlunsplit((partes.scheme, partes.netloc, partes.path or "/", urlencode(query), partes.fragment))


def telegram(metodo: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Llama a la Bot API de Telegram. Nunca imprime el token en los logs."""
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
        # No imprimimos str(e): la URL contiene el token.
        print(f"[error] Fallo al contactar con Telegram: {e.__class__.__name__}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Formato ultrasimple listo para copy-paste en foros
# --------------------------------------------------------------------------- #
def formatear_oferta(o: dict, site_url: str) -> str:
    esc = html.escape
    entidad = (o.get("entidad") or "").strip()
    etiqueta = (o.get("etiqueta_promo") or o.get("nombre") or "").strip()
    titular = f"{entidad} · {etiqueta}" if etiqueta else entidad

    cuerpo = (o.get("texto_telegram") or "").strip()
    if not cuerpo:
        partes = []
        bono = num(o.get("bono_fijo_eur"))
        tae = num(o.get("tae"))
        cb = num(o.get("porcentaje_cashback"))
        if bono > 0:
            partes.append(f"{fmt_eur(bono)} de regalo")
        if tae > 0:
            t = f"{fmt_num(tae)}% TAE"
            if o.get("saldo_maximo_remunerado") is not None:
                t += f" hasta {fmt_eur(num(o['saldo_maximo_remunerado']))}"
            partes.append(t)
        if cb > 0:
            partes.append(f"{fmt_num(cb)}% de cashback en compras")
        req = (o.get("requisitos_resumen") or ("Sin nómina" if o.get("sin_nomina") else "Requiere nómina")).strip()
        cuerpo = f"{' + '.join(partes)}. {req}." if partes else req
        codigo = (o.get("codigo_promo") or "").strip()
        if codigo and codigo.lower() not in cuerpo.lower():
            cuerpo += f" Código: {codigo}."

    cuerpo_html = esc(cuerpo)
    codigo = (o.get("codigo_promo") or "").strip()
    if codigo:
        cuerpo_html = cuerpo_html.replace(esc(codigo), f"<code>{esc(codigo)}</code>", 1)

    lineas = [
        f"<b>{esc(titular)}</b>",
        "",
        cuerpo_html,
        "",
        "Más info y calculadora:",
        esc(url_corta_visible(site_url)),
    ]
    return "\n".join(lineas)


def botones(o: dict, site_url: str) -> Optional[Dict[str, Any]]:
    campaign = o.get("utm_campaign") or o.get("id", "oferta")
    url_btn = con_utm(url_boton(site_url, oferta_id=o.get("id")), campaign)
    if not url_btn:
        return None
    return {"inline_keyboard": [[{"text": "Ver oferta y calcular →", "url": url_btn}]]}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def cargar_lista(ruta: Path) -> List[dict]:
    if not ruta.exists():
        return []
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return datos if isinstance(datos, list) else []


def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    canal = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    admin = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()
    site_url = os.getenv("SITE_URL", "").strip() or DEFAULT_SITE_URL

    ofertas = cargar_lista(OFERTAS_PATH)
    pendientes = [o for o in ofertas if o.get("activa") is True and o.get("publicar_telegram") is True]

    if not pendientes:
        print("No hay ofertas pendientes de publicar.")
        return 0

    if not token or not canal:
        print(
            f"[aviso] Pendientes: {len(pendientes)} oferta(s), pero faltan "
            "TELEGRAM_BOT_TOKEN o TELEGRAM_CHANNEL_ID. No se publica nada ni se modifica el JSON."
        )
        return 0

    publicadas: List[dict] = []
    fallidas: List[str] = []

    for o in pendientes:
        payload: Dict[str, Any] = {
            "chat_id": canal,
            "text": formatear_oferta(o, site_url),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        teclado = botones(o, site_url)
        if teclado:
            payload["reply_markup"] = teclado

        res = telegram("sendMessage", payload)
        if res is not None:
            o["publicar_telegram"] = False
            publicadas.append(o)
            msg_id = res.get("message_id", "?")
            print(f"[OK] Oferta publicada: {o.get('id')} (msg_id={msg_id})")
        else:
            fallidas.append(str(o.get("id", "?")))
            print(f"[KO] No se pudo publicar oferta: {o.get('id')}")

    if publicadas:
        OFERTAS_PATH.write_text(json.dumps(ofertas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if publicadas and admin:
        resumen = [
            f"• <b>{html.escape(o.get('entidad', ''))}</b> — {html.escape(o.get('nombre', ''))}"
            for o in publicadas
        ]
        texto = f"✅ <b>Publicado(s) {len(publicadas)} aviso(s) en el canal</b>\n\n" + "\n".join(resumen)
        if fallidas:
            texto += "\n\n⚠️ Fallaron: " + ", ".join(html.escape(f) for f in fallidas)
        telegram("sendMessage", {"chat_id": admin, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True})

    return 1 if fallidas else 0


if __name__ == "__main__":
    sys.exit(main())
