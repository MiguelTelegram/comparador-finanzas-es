#!/usr/bin/env python3
"""
monitor.py — Vigilancia de enlaces, páginas de condiciones y radar de nuevas promos.

1. Comprueba el estado HTTP de cada `url_referido` de las ofertas activas.
   Si alguna falla (404, 410, 5xx, timeout repetido o error de conexión) avisa al admin.
   Ignora respuestas 403 de protección anti-bot / WAF bancaria.
2. Descarga cada fuente de /data/fuentes.json, extrae su texto (selector_css o
   <body>), calcula el SHA-256 y lo compara con /data/estado_previo.json.
3. Lee feeds RSS españoles (TuCapital, HelpMyCash y Google News ES) para detectar
   promociones nuevas de bancos (Black Friday, regalos en efectivo, cuentas TAE)
   y guardarlas en /data/novedades.json marcadas para difundir en Telegram.
4. Regla del silencio: si todos los enlaces están OK y no hay cambios en fuentes.json,
   no envía alertas al admin (las novedades nuevas las publica difusion.py en el canal).

Variables de entorno: TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OFERTAS_PATH = ROOT / "data" / "ofertas.json"
FUENTES_PATH = ROOT / "data" / "fuentes.json"
ESTADO_PATH = ROOT / "data" / "estado_previo.json"
NOVEDADES_PATH = ROOT / "data" / "novedades.json"

TIMEOUT = 20
TELEGRAM_MAX_LEN = 4000
MAX_NOVEDADES = 12
MAX_RSS_VISTOS = 400
BOOTSTRAP_NOVEDADES = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

RSS_FUENTES = [
    {"nombre": "TuCapital", "url": "https://www.tucapital.es/feed/"},
    {"nombre": "HelpMyCash", "url": "https://www.helpmycash.com/blog/feed/"},
    {
        "nombre": "Google News · Promos Bancos",
        "url": (
            "https://news.google.com/rss/search?"
            "q=(%22cuenta+remunerada%22+OR+%22regala%22+OR+%22promoci%C3%B3n%22+OR+%22black+friday%22)"
            "+(BBVA+OR+Santander+OR+Sabadell+OR+ING+OR+Bankinter+OR+Revolut+OR+Openbank+OR+Abanca"
            "+OR+Unicaja+OR+Ibercaja+OR+CaixaBank)+when:14d&hl=es&gl=ES&ceid=ES:es"
        ),
    },
]

PALABRAS_INCLUIR = (
    "cuenta", "cuentas", "remunerada", "remuneradas", "ahorro", "depósito", "deposito",
    "depósitos", "depositos", "tae", "tin", "cashback", "saveback", "tarjeta", "tarjetas",
    "nómina", "nomina", "bienvenida", "promo", "promoción", "promocion", "bono", "regalo",
    "regala", "efectivo", "black friday", "plan amigo", "bizum", "recibos", "bonificación",
    "bonificacion", "interés", "interes", "intereses", "rentabilidad", "revolut",
    "trade republic", "raisin", "bunq", "nexo", "crypto", "ing ", "cetelem", "renault bank",
    "sabadell", "bbva", "santander", "bankinter", "openbank", "myinvestor", "imagin",
    "caixabank", "deutsche bank", "bank norwegian", "pibank", "evo", "unicaja", "abanca",
    "ibercaja", "b100", "n26", "wise", "klarna",
)

PALABRAS_EXCLUIR = (
    "hipoteca", "hipotecas", "vivienda", "viviendas", "alquiler", "inmobiliaria", "casino",
    "casinos", "jugador", "apuestas", "plan de pensiones", "planes de pensiones", "euríbor",
    "euribor", "bolsa", "ibex", "dividendo", "dividendos", "resultados", "beneficio neto",
    "cotización", "cotizacion", "préstamo", "prestamo", "préstamos", "prestamos",
    "seguro", "seguros", "guía para comprar", "guia para comprar", "méxico", "mexico",
    "buen fin", "etfs", "degiro", "crédito al consumo", "credito al consumo", "mapa de",
)

PALABRAS_PROMO_DESTACADA = (
    "black friday", "regala", "regalo", "bono", "plan", "efectivo", "promoción",
    "promocion", "tae", "cashback", "saveback", "sube la rentabilidad",
)

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def cargar_json(ruta: Path, por_defecto: Any) -> Any:
    try:
        with ruta.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return por_defecto
    except json.JSONDecodeError as e:
        print(f"[error] JSON no válido en {ruta}: {e}", file=sys.stderr)
        raise


def guardar_json(ruta: Path, datos: Any) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def enviar_telegram(chat_id: str, texto: str) -> bool:
    """Envía un mensaje HTML. Nunca imprime el token en los logs."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or not chat_id:
        print("[aviso] Telegram no configurado (TELEGRAM_BOT_TOKEN / chat_id). Mensaje no enviado:\n" + texto)
        return False

    if len(texto) > TELEGRAM_MAX_LEN:
        texto = texto[: TELEGRAM_MAX_LEN - 20] + "\n…(truncado)"

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": texto,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=TIMEOUT,
        )
        datos = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not r.ok or not datos.get("ok"):
            print(f"[error] Telegram respondió {r.status_code}: {datos.get('description', 'sin descripción')}", file=sys.stderr)
            return False
        return True
    except requests.RequestException as e:
        # No imprimimos str(e): la URL contiene el token.
        print(f"[error] Fallo al contactar con Telegram: {e.__class__.__name__}", file=sys.stderr)
        return False


# --------------------------------------------------------------------------- #
# 1. Enlaces de referido
# --------------------------------------------------------------------------- #
def comprobar_enlace(url: str) -> Optional[str]:
    """Devuelve None si el enlace está OK o una descripción del error."""
    for intento in range(2):
        try:
            r = SESSION.head(url, allow_redirects=True, timeout=TIMEOUT)
            if r.status_code == 403:
                return None
            # Algunos servidores no aceptan HEAD: reintentamos con GET.
            if r.status_code >= 400:
                r = SESSION.get(url, allow_redirects=True, timeout=TIMEOUT, stream=True)
                r.close()
            if r.status_code == 403:
                return None
            if r.status_code >= 400:
                return f"HTTP {r.status_code}"
            return None
        except requests.Timeout:
            if intento == 0:
                continue
            return "Timeout"
        except requests.RequestException as e:
            return f"Error de conexión ({e.__class__.__name__})"
    return None


def revisar_enlaces(ofertas: List[dict]) -> List[Tuple[dict, str]]:
    rotos: List[Tuple[dict, str]] = []
    for o in ofertas:
        if not o.get("activa"):
            continue
        url = (o.get("url_referido") or "").strip()
        if not url:
            rotos.append((o, "Sin url_referido"))
            print(f"[KO] {o.get('id')}: sin url_referido")
            continue
        error = comprobar_enlace(url)
        if error:
            rotos.append((o, error))
            print(f"[KO] {o.get('id')}: {error} -> {url}")
        else:
            print(f"[OK] {o.get('id')}")
    return rotos


# --------------------------------------------------------------------------- #
# 2. Cambios en páginas de condiciones
# --------------------------------------------------------------------------- #
def extraer_texto(contenido: str, selector: Optional[str]) -> str:
    soup = BeautifulSoup(contenido, "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "svg", "iframe"]):
        tag.decompose()

    if selector:
        nodo = soup.select_one(selector)
        if nodo is None:
            raise ValueError(f"selector '{selector}' no encontrado")
    else:
        nodo = soup.body or soup

    texto = nodo.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", texto).strip()


def revisar_fuentes(fuentes: List[dict], estado: dict) -> Tuple[List[Tuple[str, str]], bool]:
    cambios: List[Tuple[str, str]] = []
    modificado = False
    ahora = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    for fuente in fuentes:
        url = (fuente.get("url") or "").strip()
        if not url:
            continue
        nombre = fuente.get("nombre") or url
        selector = (fuente.get("selector_css") or "").strip() or None

        try:
            r = SESSION.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            texto = extraer_texto(r.text, selector)
        except (requests.RequestException, ValueError) as e:
            detalle = str(e) if isinstance(e, ValueError) else e.__class__.__name__
            print(f"[aviso] No se pudo analizar '{nombre}': {detalle}")
            continue

        if not texto:
            print(f"[aviso] '{nombre}' no contiene texto analizable")
            continue

        nuevo_hash = hashlib.sha256(texto.encode("utf-8")).hexdigest()
        previo = estado.get(url) if isinstance(estado.get(url), dict) else {}
        hash_previo = previo.get("hash")
        selector_previo = previo.get("selector_css")

        if hash_previo == nuevo_hash:
            print(f"[=] Sin cambios: {nombre}")
            continue

        estado[url] = {
            "nombre": nombre,
            "selector_css": selector,
            "hash": nuevo_hash,
            "ultimo_cambio": ahora,
        }
        modificado = True

        if hash_previo is None or selector_previo != selector:
            # Primera ejecución o selector editado: se guarda como línea base sin avisar.
            print(f"[+] Línea base registrada: {nombre}")
        else:
            cambios.append((nombre, url))
            print(f"[!] Cambio detectado: {nombre}")

    return cambios, modificado


# --------------------------------------------------------------------------- #
# 3. Radar de nuevas promociones (RSS)
# --------------------------------------------------------------------------- #
def es_promo_relevante(titulo: str) -> bool:
    t = f" {titulo.lower()} "
    if any(p in t for p in PALABRAS_EXCLUIR):
        return False
    return any(p in t for p in PALABRAS_INCLUIR)


def es_promo_destacada(titulo: str) -> bool:
    t = titulo.lower()
    return any(p in t for p in PALABRAS_PROMO_DESTACADA)


def limpiar_resumen_rss(raw_html: str, titulo: str = "") -> str:
    texto = BeautifulSoup(raw_html or "", "html.parser").get_text(" ", strip=True)
    texto = re.sub(r"\s*La entrada\b.*$", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s*The post\b.*$", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s+", " ", texto).strip()
    titulo_base = titulo.rsplit(" - ", 1)[0].strip() if " - " in titulo else titulo
    if titulo_base and texto.lower().startswith(titulo_base.lower()):
        resto = texto[len(titulo_base):].strip(" -–—·|")
        if len(resto) < 60:
            return ""
        texto = resto
    if len(texto) <= 220:
        return texto
    recortado = texto[:219].rsplit(" ", 1)[0].rstrip(".,;:")
    return f"{recortado}…"


def fecha_rss_iso(raw_date: str) -> str:
    if raw_date:
        try:
            dt = parsedate_to_datetime(raw_date.strip())
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).date().isoformat()
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc).date().isoformat()


def revisar_rss(estado: dict) -> Tuple[int, bool]:
    """Detecta promociones nuevas en RSS y actualiza data/novedades.json."""
    inicializado = bool(estado.get("_rss_inicializado"))
    vistos_raw = estado.get("_rss_vistos") if isinstance(estado.get("_rss_vistos"), list) else []
    vistos_list: List[str] = [str(x) for x in vistos_raw]
    vistos_set = set(vistos_list)

    novedades = cargar_json(NOVEDADES_PATH, [])
    if not isinstance(novedades, list):
        novedades = []
    novedades_ids = {n.get("id") for n in novedades if isinstance(n, dict) and n.get("id")}
    titulos_vistos = {
        (n.get("titulo") or "").strip().lower()
        for n in novedades
        if isinstance(n, dict) and n.get("titulo")
    }

    estado_modificado = False
    novedades_modificado = False
    nuevas_para_telegram = 0
    candidatas: List[Dict[str, Any]] = []

    for fuente in RSS_FUENTES:
        nombre = fuente["nombre"]
        url = fuente["url"]
        try:
            r = SESSION.get(url, timeout=TIMEOUT, headers={"Accept": "application/rss+xml, application/xml, text/xml, */*"})
            r.raise_for_status()
            root = ET.fromstring(r.content)
        except (requests.RequestException, ET.ParseError) as e:
            print(f"[aviso] No se pudo leer RSS '{nombre}': {e.__class__.__name__}")
            continue

        for item in root.findall(".//item"):
            titulo = re.sub(r"\s+", " ", (item.findtext("title") or "")).strip()
            link = (item.findtext("link") or "").strip()
            if not titulo or not link:
                continue

            item_id = hashlib.sha256(link.encode("utf-8")).hexdigest()[:12]
            if item_id in vistos_set:
                continue

            vistos_set.add(item_id)
            vistos_list.append(item_id)
            estado_modificado = True

            if not es_promo_relevante(titulo):
                continue

            titulo_norm = titulo.lower()
            if titulo_norm in titulos_vistos:
                continue
            titulos_vistos.add(titulo_norm)

            candidatas.append({
                "id": item_id,
                "titulo": titulo,
                "fuente": nombre,
                "resumen": limpiar_resumen_rss(item.findtext("description") or "", titulo=titulo),
                "url": link,
                "fecha": fecha_rss_iso(item.findtext("pubDate") or ""),
                "es_promo_destacada": es_promo_destacada(titulo),
                "publicar_telegram": inicializado,
            })

    if not inicializado and candidatas:
        candidatas.sort(key=lambda x: (bool(x["es_promo_destacada"]), x["fecha"]), reverse=True)
        seleccionadas = candidatas[:BOOTSTRAP_NOVEDADES]
        for n in seleccionadas:
            if n["id"] not in novedades_ids:
                novedades.append(n)
                novedades_ids.add(n["id"])
                novedades_modificado = True
        estado["_rss_inicializado"] = True
        estado_modificado = True
        print(f"[+] Radar RSS inicializado con {len(seleccionadas)} novedades (sin spamear Telegram).")
    elif not inicializado and not candidatas:
        if estado_modificado:
            estado["_rss_inicializado"] = True
    else:
        nuevas = [n for n in candidatas if n["id"] not in novedades_ids]
        if nuevas:
            nuevas.sort(key=lambda x: x["fecha"], reverse=True)
            novedades = nuevas + novedades
            novedades_modificado = True
            nuevas_para_telegram = len(nuevas)
            for n in nuevas:
                print(f"[+] Nueva promoción RSS detectada: {n['titulo']} ({n['fuente']})")
        else:
            print("[=] Sin promociones nuevas en RSS.")

    if novedades_modificado:
        # Prioriza conservar las pendientes de publicar en caso de superar MAX_NOVEDADES.
        pendientes = [n for n in novedades if n.get("publicar_telegram")]
        ya_publicadas = [n for n in novedades if not n.get("publicar_telegram")]
        novedades = (pendientes + ya_publicadas)[:MAX_NOVEDADES]
        novedades.sort(key=lambda x: (x.get("fecha", ""), bool(x.get("publicar_telegram"))), reverse=True)
        guardar_json(NOVEDADES_PATH, novedades)

    if estado_modificado:
        estado["_rss_vistos"] = vistos_list[-MAX_RSS_VISTOS:]

    return nuevas_para_telegram, estado_modificado


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    admin_chat = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "").strip()

    # 1. Enlaces de referido
    ofertas = cargar_json(OFERTAS_PATH, [])
    rotos = revisar_enlaces(ofertas if isinstance(ofertas, list) else [])
    if rotos:
        lineas = [
            f"• <b>{html.escape(o.get('entidad', o.get('id', '?')))}</b> — {html.escape(err)}\n"
            f"  {html.escape(o.get('url_referido') or '(vacío)')}"
            for o, err in rotos
        ]
        enviar_telegram(admin_chat, "🚨 <b>Enlaces de referido con error</b>\n\n" + "\n".join(lineas))

    # 2. Cambios en páginas de condiciones
    fuentes = cargar_json(FUENTES_PATH, [])
    estado = cargar_json(ESTADO_PATH, {})
    if not isinstance(estado, dict):
        estado = {}

    cambios, modificado_fuentes = revisar_fuentes(fuentes if isinstance(fuentes, list) else [], estado)

    # 3. Radar RSS de nuevas promociones
    _, modificado_rss = revisar_rss(estado)

    if modificado_fuentes or modificado_rss:
        guardar_json(ESTADO_PATH, estado)

    if cambios:
        lineas = [f"• <b>{html.escape(n)}</b>\n  {html.escape(u)}" for n, u in cambios]
        enviar_telegram(
            admin_chat,
            "🔔 <b>Cambios detectados en condiciones</b>\n\n"
            + "\n".join(lineas)
            + "\n\nRevisa las condiciones y actualiza <code>data/ofertas.json</code> si procede.",
        )

    # 4. Regla del silencio (las novedades RSS las difunde difusion.py directamente en el canal)
    if not rotos and not cambios:
        print("Todo OK y sin cambios en condiciones. Regla del silencio: sin alertas al admin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
