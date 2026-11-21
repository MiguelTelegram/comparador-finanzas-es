#!/usr/bin/env python3
"""
difusion.py — Publica en el canal de Telegram las ofertas marcadas.

1. Lee /data/ofertas.json y selecciona las ofertas con
   "activa": true y "publicar_telegram": true.
2. Publica cada una en TELEGRAM_CHANNEL_ID (HTML + botón inline).
3. Envía una confirmación a TELEGRAM_ADMIN_CHAT_ID con un recordatorio de las
   plantillas para difusión manual (/marketing/mensajes_foros.md).
4. Pone "publicar_telegram": false en las ofertas publicadas y guarda el JSON.

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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

ROOT = Path(__file__).resolve().parent.parent
OFERTAS_PATH = ROOT / "data" / "ofertas.json"
TIMEOUT = 20

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


def fmt_fecha(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(iso)


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
# Formato del mensaje
# --------------------------------------------------------------------------- #
def formatear_oferta(o: dict) -> str:
    esc = html.escape
    lineas: List[str] = [f"🏦 <b>{esc(o.get('entidad', ''))}</b> · {esc(o.get('nombre', ''))}", ""]

    tae = num(o.get("tae"))
    if tae > 0:
        linea = f"📈 <b>TAE:</b> {fmt_num(tae)}%"
        if o.get("saldo_maximo_remunerado") is not None:
            linea += f" hasta {fmt_eur(num(o['saldo_maximo_remunerado']))}"
        lineas.append(linea)

    cashback = num(o.get("porcentaje_cashback"))
    if cashback > 0:
        linea = f"💳 <b>Cashback:</b> {fmt_num(cashback)}%"
        if o.get("tope_mensual_eur") is not None:
            linea += f" (máx. {fmt_eur(num(o['tope_mensual_eur']))}/mes)"
        lineas.append(linea)

    bono = num(o.get("bono_fijo_eur"))
    if bono > 0:
        lineas.append(f"🎁 <b>Bono de bienvenida:</b> {fmt_eur(bono)}")

    pais = (o.get("pais_iban") or "N/A").upper()
    if pais == "N/A":
        lineas.append("🪙 <b>IBAN:</b> No aplica (servicio crypto)")
    else:
        lineas.append(f"🏛 <b>IBAN:</b> {esc(PAISES.get(pais, pais))}")

    extras = []
    if o.get("sin_nomina"):
        extras.append("✅ Sin nómina")
    if o.get("sin_comisiones"):
        extras.append("✅ 0% comisiones")
    if extras:
        lineas.append(" · ".join(extras))

    lineas += ["", f"📝 {esc(o.get('resumen_condiciones', ''))}"]

    if o.get("es_crypto") or pais not in ("ES", "N/A"):
        lineas += ["", "<i>ℹ️ Recuerda: saldos en el extranjero &gt; 50.000 € → Modelo 720; recompensas crypto tributan en IRPF.</i>"]

    lineas += [
        "",
        f"<i>Condiciones a {esc(fmt_fecha(o.get('fecha_actualizacion', '')))}. "
        "Enlace de referido: sin coste adicional para ti.</i>",
    ]
    return "\n".join(lineas)


def botones(o: dict, site_url: str) -> Optional[Dict[str, Any]]:
    campaign = o.get("utm_campaign") or o.get("id", "oferta")
    filas = []
    url_oferta = con_utm(o.get("url_referido", ""), campaign)
    if url_oferta:
        filas.append([{"text": f"👉 Ver oferta de {o.get('entidad', '')}".strip(), "url": url_oferta}])
    url_site = con_utm(site_url, campaign)
    if url_site:
        filas.append([{"text": "📊 Comparar todas las ofertas", "url": url_site}])
    return {"inline_keyboard": filas} if filas else None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    canal = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    admin = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()
    site_url = os.getenv("SITE_URL", "").strip()

    ofertas = json.loads(OFERTAS_PATH.read_text(encoding="utf-8"))
    pendientes = [o for o in ofertas if o.get("activa") is True and o.get("publicar_telegram") is True]

    if not pendientes:
        print("No hay ofertas pendientes de publicar.")
        return 0

    if not token or not canal:
        print(
            f"[aviso] Hay {len(pendientes)} oferta(s) pendientes, pero faltan TELEGRAM_BOT_TOKEN "
            "o TELEGRAM_CHANNEL_ID. No se publica nada ni se modifica ofertas.json."
        )
        return 0

    publicadas: List[dict] = []
    fallidas: List[dict] = []

    for o in pendientes:
        payload: Dict[str, Any] = {
            "chat_id": canal,
            "text": formatear_oferta(o),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        teclado = botones(o, site_url)
        if teclado:
            payload["reply_markup"] = teclado

        if telegram("sendMessage", payload):
            o["publicar_telegram"] = False
            publicadas.append(o)
            print(f"[OK] Publicada: {o.get('id')}")
        else:
            fallidas.append(o)
            print(f"[KO] No se pudo publicar: {o.get('id')}")

    if publicadas:
        OFERTAS_PATH.write_text(json.dumps(ofertas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        if admin:
            lista = "\n".join(
                f"• <b>{html.escape(o.get('entidad', ''))}</b> — {html.escape(o.get('nombre', ''))}" for o in publicadas
            )
            texto = (
                f"✅ <b>Publicadas {len(publicadas)} oferta(s) en el canal</b>\n\n{lista}\n\n"
                "📣 Recuerda: tienes las plantillas para difusión manual en foros "
                "(Rankia, Reddit, ForoCoches, Chollometro) en <code>/marketing/mensajes_foros.md</code>."
            )
            if fallidas:
                texto += "\n\n⚠️ Fallaron: " + ", ".join(html.escape(o.get("id", "?")) for o in fallidas)
            telegram("sendMessage", {"chat_id": admin, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True})

    # Si alguna falló se devuelve error para que el workflow avise (las publicadas ya quedan guardadas).
    return 1 if fallidas else 0


if __name__ == "__main__":
    sys.exit(main())
