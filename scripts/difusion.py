#!/usr/bin/env python3
"""
difusion.py — Publica en el canal de Telegram ofertas y nuevas promociones.

1. Lee /data/ofertas.json ("activa": true y "publicar_telegram": true) y
   /data/novedades.json ("publicar_telegram": true, máx. 3 por ejecución).
2. Publica mensajes limpios en TELEGRAM_CHANNEL_ID con enlace directo y visible
   a la web (listos para hacer copy-paste en foros) + botón inline hacia la web.
3. Envía confirmación breve a TELEGRAM_ADMIN_CHAT_ID.
4. Marca "publicar_telegram": false y guarda los JSON.

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
DEFAULT_SITE_URL = "https://migueltelegram.github.io/comparador-finanzas-es/"
TIMEOUT = 20
MAX_NOVEDADES_POR_EJECUCION = 3

PAISES = {
    "ES": "🇪🇸 España", "DE": "🇩🇪 Alemania", "NL": "🇳🇱 Países Bajos", "FR": "🇫🇷 Francia",
    "IE": "🇮🇪 Irlanda", "LT": "🇱🇹 Lituania", "BE": "🇧🇪 Bélgica", "IT": "🇮🇹 Italia",
    "PT": "🇵🇹 Portugal", "LU": "🇱🇺 Luxemburgo", "AT": "🇦🇹 Austria", "MT": "🇲🇹 Malta",
    "FI": "🇫🇮 Finlandia", "EE": "🇪🇪 Estonia", "LV": "🇱🇻 Letonia",
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


def url_web_limpia(site_url: str, oferta_id: Optional[str] = None, fragmento: str = "") -> str:
    """URL limpia visible en el texto para que funcione al copiar y pegar en foros."""
    base = (site_url or DEFAULT_SITE_URL).strip() or DEFAULT_SITE_URL
    if not base.endswith("/"):
        base += "/"
    if oferta_id:
        return f"{base}?oferta={oferta_id}"
    if fragmento:
        return f"{base}#{fragmento}"
    return base


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
# Formatos listos para copy-paste en foros (siempre dirigiendo a la web)
# --------------------------------------------------------------------------- #
def formatear_oferta(o: dict, site_url: str) -> str:
    esc = html.escape
    entidad = esc(o.get("entidad", ""))
    nombre = esc(o.get("nombre", ""))
    lineas: List[str] = [f"🔥 <b>{entidad} — {nombre}</b>", ""]

    tae = num(o.get("tae"))
    if tae > 0:
        linea = f"• <b>Rentabilidad:</b> {fmt_num(tae)}% TAE"
        if o.get("saldo_maximo_remunerado") is not None:
            linea += f" hasta {fmt_eur(num(o['saldo_maximo_remunerado']))}"
        lineas.append(linea)

    cashback = num(o.get("porcentaje_cashback"))
    if cashback > 0:
        linea = f"• <b>Cashback:</b> {fmt_num(cashback)}%"
        if o.get("tope_mensual_eur") is not None:
            linea += f" (máx. {fmt_eur(num(o['tope_mensual_eur']))}/mes)"
        lineas.append(linea)

    bono = num(o.get("bono_fijo_eur"))
    if bono > 0:
        lineas.append(f"• <b>Bono de bienvenida:</b> {fmt_eur(bono)}")

    pais = (o.get("pais_iban") or "N/A").upper()
    detalles_iban: List[str] = []
    if pais == "N/A":
        detalles_iban.append("Servicio crypto")
    else:
        detalles_iban.append(f"IBAN {PAISES.get(pais, pais)}")
    if o.get("sin_nomina"):
        detalles_iban.append("Sin nómina")
    if o.get("sin_comisiones"):
        detalles_iban.append("0% comisiones")
    lineas.append("• <b>Cuenta:</b> " + " · ".join(esc(d) for d in detalles_iban))

    resumen = (o.get("resumen_condiciones") or "").strip()
    if resumen:
        lineas += ["", esc(resumen)]

    if o.get("es_crypto") or pais not in ("ES", "N/A"):
        lineas += ["", "ℹ️ <i>Saldos en el extranjero &gt; 50.000 €: Modelo 720; recompensas crypto tributan en IRPF.</i>"]

    url_oferta_web = url_web_limpia(site_url, oferta_id=o.get("id"))
    lineas += [
        "",
        "👉 <b>Calcula cuánto te da al año y consulta las condiciones:</b>",
        esc(url_oferta_web),
    ]
    return "\n".join(lineas)


def botones(o: dict, site_url: str) -> Optional[Dict[str, Any]]:
    campaign = o.get("utm_campaign") or o.get("id", "oferta")
    url_oferta_web = url_web_limpia(site_url, oferta_id=o.get("id"))
    url_btn = con_utm(url_oferta_web, campaign)
    if not url_btn:
        return None
    return {"inline_keyboard": [[{"text": "📊 Ver detalles y calcular en la web", "url": url_btn}]]}


def formatear_novedad(n: dict, site_url: str) -> str:
    esc = html.escape
    titulo = esc(n.get("titulo", "Nueva promoción"))
    resumen = esc(n.get("resumen", "")).strip()
    url_novedades = esc(url_web_limpia(site_url, fragmento="novedades"))

    partes = [f"📢 <b>Nueva promoción detectada: {titulo}</b>"]
    if resumen:
        partes += ["", resumen]
    partes += [
        "",
        "👉 Ver detalles y comparar con las mejores cuentas y tarjetas en la calculadora:",
        url_novedades,
    ]
    return "\n".join(partes)


def botones_novedad(n: dict, site_url: str) -> Optional[Dict[str, Any]]:
    url_novedades = url_web_limpia(site_url, fragmento="novedades")
    url_btn = con_utm(url_novedades, f"novedad_{n.get('id', 'rss')}")
    if not url_btn:
        return None
    return {"inline_keyboard": [[{"text": "📊 Ver detalles y comparar en la web", "url": url_btn}]]}


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
            + "\n\n📋 Los mensajes del canal ya incluyen el enlace limpio a la web listos para copiar y pegar en foros."
        )
        if fallidas:
            texto += "\n\n⚠️ Fallaron: " + ", ".join(html.escape(f) for f in fallidas)
        telegram("sendMessage", {"chat_id": admin, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True})

    return 1 if fallidas else 0


if __name__ == "__main__":
    sys.exit(main())
