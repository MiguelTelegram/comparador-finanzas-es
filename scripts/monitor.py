#!/usr/bin/env python3
"""
monitor.py — Vigilancia de enlaces de referido y páginas de condiciones.

1. Comprueba el estado HTTP de cada `url_referido` de las ofertas activas.
   Si alguna falla (status >= 400, timeout o error de conexión) avisa al admin.
2. Descarga cada fuente de /data/fuentes.json, extrae su texto (selector_css o
   <body>), calcula el SHA-256 y lo compara con /data/estado_previo.json.
3. Si hay cambios, actualiza /data/estado_previo.json y avisa al admin.
4. Regla del silencio: si todo está OK y no hay cambios, no envía nada.

Variables de entorno: TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OFERTAS_PATH = ROOT / "data" / "ofertas.json"
FUENTES_PATH = ROOT / "data" / "fuentes.json"
ESTADO_PATH = ROOT / "data" / "estado_previo.json"

TIMEOUT = 20
TELEGRAM_MAX_LEN = 4000
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

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
    try:
        r = SESSION.head(url, allow_redirects=True, timeout=TIMEOUT)
        # Algunos servidores no aceptan HEAD: reintentamos con GET.
        if r.status_code >= 400:
            r = SESSION.get(url, allow_redirects=True, timeout=TIMEOUT, stream=True)
            r.close()
        if r.status_code == 403 and (
            r.headers.get("cf-mitigated")
            or "cloudflare" in r.headers.get("server", "").lower()
        ):
            return None
        if r.status_code >= 400:
            return f"HTTP {r.status_code}"
        return None
    except requests.Timeout:
        return "Timeout"
    except requests.RequestException as e:
        return f"Error de conexión ({e.__class__.__name__})"


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

    # 2 y 3. Cambios en páginas de condiciones
    fuentes = cargar_json(FUENTES_PATH, [])
    estado = cargar_json(ESTADO_PATH, {})
    if not isinstance(estado, dict):
        estado = {}

    cambios, modificado = revisar_fuentes(fuentes if isinstance(fuentes, list) else [], estado)
    if modificado:
        guardar_json(ESTADO_PATH, estado)

    if cambios:
        lineas = [f"• <b>{html.escape(n)}</b>\n  {html.escape(u)}" for n, u in cambios]
        enviar_telegram(
            admin_chat,
            "🔔 <b>Cambios detectados en condiciones</b>\n\n"
            + "\n".join(lineas)
            + "\n\nRevisa las condiciones y actualiza <code>data/ofertas.json</code> si procede.",
        )

    # 4. Regla del silencio
    if not rotos and not cambios:
        print("Todo OK y sin cambios. Regla del silencio: no se envía ningún mensaje.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
