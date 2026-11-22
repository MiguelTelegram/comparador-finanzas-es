#!/usr/bin/env python3
"""
difusion.py — Publica en el canal de Telegram ofertas y nuevas promociones.

Mensajes claros en español llano, traducidos a euros reales y con enlace
ultracorto visible a la web (https://migueltelegram.github.io) para poder hacer
copy-paste directo en foros como ForoCoches, Rankia, Reddit o Chollometro.

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
NOVEDADES_PATH = ROOT / "data" / "novedades.json"
DEFAULT_SITE_URL = "https://migueltelegram.github.io"
TIMEOUT = 20
MAX_NOVEDADES_POR_EJECUCION = 3

PAISES = {
    "ES": "IBAN español 🇪🇸",
    "DE": "IBAN alemán 🇩🇪",
    "NL": "IBAN de Países Bajos 🇳🇱",
    "NO": "IBAN noruego 🇳🇴",
    "FR": "IBAN francés 🇫🇷",
    "IE": "IBAN irlandés 🇮🇪",
    "LT": "IBAN lituano 🇱🇹",
}


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


def url_boton(site_url: str, oferta_id: Optional[str] = None, fragmento: str = "") -> str:
    base = url_corta_visible(site_url)
    if oferta_id:
        return f"{base}/?o={oferta_id}"
    if fragmento:
        return f"{base}/#{fragmento}"
    return f"{base}/"


def con_utm(url: str, campaign: str, source: str = "telegram", medium: str = "canal") -> Optional[str]:
    if not url or not url.startswith(("http://", "https://")):
        return None
    partes = urlsplit(url)
    query = dict(parse_qsl(partes.query, keep_blank_values=True))
    query.update({"utm_source": source, "utm_medium": medium, "utm_campaign": campaign})
    return urlunsplit((partes.scheme, partes.netloc, partes.path or "/", urlencode(query), partes.fragment))


def telegram(metodo: str, payload: Dict[str, Any]) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", json=payload, timeout=TIMEOUT)
        datos = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not r.ok or not datos.get("ok"):
            print(f"[error] Telegram {metodo} -> {r.status_code}: {datos.get('description', 'sin descripción')}", file=sys.stderr)
            return False
        return True
    except requests.RequestException as e:
        # No imprimimos str(e): la URL contiene el token.
        print(f"[error] Fallo al contactar con Telegram: {e.__class__.__name__}", file=sys.stderr)
        return False


# --------------------------------------------------------------------------- #
# Formatos claros y listos para copy-paste en foros
# --------------------------------------------------------------------------- #
def formatear_oferta(o: dict, site_url: str) -> str:
    esc = html.escape
    entidad = esc(o.get("entidad", ""))
    nombre = esc(o.get("nombre", ""))
    lineas: List[str] = [f"💰 <b>{entidad}: {nombre}</b>"]

    etiqueta = (o.get("etiqueta_promo") or "").strip()
    if etiqueta:
        lineas.append(f"🏷 <i>{esc(etiqueta)}</i>")

    lineas += ["", "👉 <b>Qué te llevas:</b>"]

    bono = num(o.get("bono_fijo_eur"))
    if bono > 0:
        lineas.append(f"• <b>{fmt_eur(bono)}</b> de regalo en efectivo")

    tae = num(o.get("tae"))
    if tae > 0:
        euros_10k = fmt_eur(10000 * (tae / 100.0))
        linea = f"• <b>{fmt_num(tae)}% TAE</b> (por cada 10.000 € son +{euros_10k}/año)"
        if o.get("saldo_maximo_remunerado") is not None:
            linea += f" hasta {fmt_eur(num(o['saldo_maximo_remunerado']))}"
        lineas.append(linea)

    cb = num(o.get("porcentaje_cashback"))
    if cb > 0:
        linea = f"• <b>{fmt_num(cb)}% de devolución</b> en compras"
        if o.get("tope_mensual_eur") is not None:
            linea += f" (máx. {fmt_eur(num(o['tope_mensual_eur']))}/mes)"
        lineas.append(linea)

    pais = (o.get("pais_iban") or "N/A").upper()
    iban_txt = "Servicio crypto" if pais == "N/A" else PAISES.get(pais, f"IBAN {pais}")

    req = (o.get("requisitos_resumen") or "").strip()
    if not req:
        req = "Sin nómina" if o.get("sin_nomina") else "Requiere domiciliar nómina"
    perm = (o.get("permanencia") or "").strip()

    partes_pide = [req]
    if perm and perm.lower() not in req.lower():
        partes_pide.append(perm)
    if "iban" not in req.lower() and "crypto" not in req.lower():
        partes_pide.append(iban_txt)
    if o.get("sin_comisiones"):
        partes_pide.append("0% comisiones")

    lineas += ["", f"✅ <b>Qué pide:</b> {esc(' · '.join(partes_pide))}"]

    codigo = (o.get("codigo_promo") or "").strip()
    if codigo:
        lineas.append(f"🔑 <b>Código promo:</b> <code>{esc(codigo)}</code>")

    if o.get("es_crypto") or pais not in ("ES", "N/A"):
        lineas += ["", "ℹ️ <i>Recuerda: saldos fuera de España &gt; 50.000 € (Modelo 720) y recompensas crypto tributan en IRPF.</i>"]

    lineas += [
        "",
        "🧮 Calcula cuánto ganarías tú aquí:",
        esc(url_corta_visible(site_url)),
    ]
    return "\n".join(lineas)


def botones(o: dict, site_url: str) -> Optional[Dict[str, Any]]:
    campaign = o.get("utm_campaign") or o.get("id", "oferta")
    url_btn = con_utm(url_boton(site_url, oferta_id=o.get("id")), campaign)
    if not url_btn:
        return None
    return {"inline_keyboard": [[{"text": "🧮 Calcular cuánto ganaría yo →", "url": url_btn}]]}


def formatear_novedad(n: dict, site_url: str) -> str:
    esc = html.escape
    titulo = esc(n.get("titulo", "Nueva promoción bancaria"))
    resumen = esc(n.get("resumen", "")).strip()
    link_corto = esc(url_corta_visible(site_url))

    partes = [f"🔥 <b>Nueva promoción bancaria: {titulo}</b>"]
    if resumen:
        partes += ["", resumen]
    partes += [
        "",
        "🧮 Mira los detalles y compara con todos los bancos aquí:",
        link_corto,
    ]
    return "\n".join(partes)


def botones_novedad(n: dict, site_url: str) -> Optional[Dict[str, Any]]:
    url_btn = con_utm(url_boton(site_url, fragmento="novedades"), f"novedad_{n.get('id', 'rss')}")
    if not url_btn:
        return None
    return {"inline_keyboard": [[{"text": "📊 Ver detalle y comparar bancos →", "url": url_btn}]]}


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
    novedades = cargar_lista(NOVEDADES_PATH)

    pendientes_ofertas = [o for o in ofertas if o.get("activa") is True and o.get("publicar_telegram") is True]
    pendientes_novedades = [n for n in novedades if n.get("publicar_telegram") is True][:MAX_NOVEDADES_POR_EJECUCION]

    if not pendientes_ofertas and not pendientes_novedades:
        print("No hay ofertas ni novedades pendientes de publicar.")
        return 0

    if not token or not canal:
        print(
            f"[aviso] Pendientes: {len(pendientes_ofertas)} oferta(s) y {len(pendientes_novedades)} novedad(es), "
            "pero faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHANNEL_ID. No se publica nada ni se modifican los JSON."
        )
        return 0

    publicadas_ofertas: List[dict] = []
    publicadas_novedades: List[dict] = []
    fallidas: List[str] = []

    for o in pendientes_ofertas:
        payload: Dict[str, Any] = {
            "chat_id": canal,
            "text": formatear_oferta(o, site_url),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        teclado = botones(o, site_url)
        if teclado:
            payload["reply_markup"] = teclado

        if telegram("sendMessage", payload):
            o["publicar_telegram"] = False
            publicadas_ofertas.append(o)
            print(f"[OK] Oferta publicada: {o.get('id')}")
        else:
            fallidas.append(str(o.get("id", "?")))
            print(f"[KO] No se pudo publicar oferta: {o.get('id')}")

    for n in pendientes_novedades:
        payload = {
            "chat_id": canal,
            "text": formatear_novedad(n, site_url),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        teclado = botones_novedad(n, site_url)
        if teclado:
            payload["reply_markup"] = teclado

        if telegram("sendMessage", payload):
            n["publicar_telegram"] = False
            publicadas_novedades.append(n)
            print(f"[OK] Novedad publicada: {n.get('id')}")
        else:
            fallidas.append(str(n.get("id", "?")))
            print(f"[KO] No se pudo publicar novedad: {n.get('id')}")

    if publicadas_ofertas:
        OFERTAS_PATH.write_text(json.dumps(ofertas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if publicadas_novedades:
        NOVEDADES_PATH.write_text(json.dumps(novedades, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    total_pub = len(publicadas_ofertas) + len(publicadas_novedades)
    if total_pub and admin:
        resumen_lineas = [
            f"• <b>{html.escape(o.get('entidad', ''))}</b> — {html.escape(o.get('nombre', ''))}"
            for o in publicadas_ofertas
        ] + [
            f"• <b>{html.escape(n.get('fuente', 'Promo'))}</b> — {html.escape(n.get('titulo', ''))}"
            for n in publicadas_novedades
        ]
        texto = (
            f"✅ <b>Publicado(s) {total_pub} aviso(s) en el canal</b>\n\n"
            + "\n".join(resumen_lineas)
            + "\n\n📋 Los mensajes ya incluyen el enlace corto listos para copiar y pegar en foros."
        )
        if fallidas:
            texto += "\n\n⚠️ Fallaron: " + ", ".join(html.escape(f) for f in fallidas)
        telegram("sendMessage", {"chat_id": admin, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True})

    return 1 if fallidas else 0


if __name__ == "__main__":
    sys.exit(main())
