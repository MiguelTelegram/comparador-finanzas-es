# comparador-finanzas-es

Comparador estático de **cuentas remuneradas, tarjetas cashback y servicios crypto** en España, publicado en **[https://migueltelegram.github.io/comparador-finanzas-es/](https://migueltelegram.github.io/comparador-finanzas-es/)** con:

- Web 100 % estática (HTML + CSS + Vanilla JS, sin frameworks) desplegada gratis en **GitHub Pages** (y compatible con Cloudflare Pages).
- Scripts Python (`requests` + `beautifulsoup4`) que vigilan enlaces y condiciones, y publican ofertas en **Telegram**.
- **GitHub Actions** que lo ejecuta todo cada 12 horas (`.github/workflows/pipeline.yml`) y redespliega la web automáticamente si cambian las ofertas (`.github/workflows/pages.yml`).

```
├── data/
│   ├── ofertas.json          ← fuente de verdad de las ofertas
│   ├── fuentes.json          ← páginas de condiciones a vigilar
│   └── estado_previo.json    ← hashes SHA-256 (lo gestiona monitor.py)
├── web/                      ← carpeta publicada en GitHub Pages (o Cloudflare Pages)
│   ├── index.html · styles.css · app.js · robots.txt · sitemap.xml
│   └── data/ofertas.json     ← copia de data/ofertas.json (la sincroniza el workflow)
├── scripts/
│   ├── monitor.py · difusion.py · requirements.txt
├── marketing/mensajes_foros.md
└── .github/workflows/
    ├── pipeline.yml          ← monitor + difusión cada 12 h
    └── pages.yml             ← despliegue automático en GitHub Pages
```

---

## 1. Probar la web en local

La web carga `data/ofertas.json` con `fetch`, así que hay que servirla por HTTP (abrir el `index.html` con doble clic no funciona por las restricciones de `file://`):

```bash
cd web
python3 -m http.server 8080
# Abre http://localhost:8080
```

Para probar los scripts en local:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt
python scripts/monitor.py      # sin variables de Telegram, imprime los avisos por consola
python scripts/difusion.py
```

---

## 2. Crear el bot, el canal y obtener los IDs

1. En Telegram, abre **@BotFather** → `/newbot` → elige nombre y usuario. Guarda el **token** (`123456:ABC-...`) → será `TELEGRAM_BOT_TOKEN`.
2. Crea un **canal** (Nuevo canal → público o privado) y añade tu bot como **administrador** con permiso para *publicar mensajes*.
3. **ID del canal** (`TELEGRAM_CHANNEL_ID`):
   - Canal público: vale con `@nombre_del_canal`.
   - Canal privado: publica un mensaje en el canal, abre `https://api.telegram.org/bot<TOKEN>/getUpdates` y copia `channel_post.chat.id` (empieza por `-100…`).
4. **ID de tu chat de admin** (`TELEGRAM_ADMIN_CHAT_ID`): escribe `/start` a tu bot por privado, abre de nuevo `getUpdates` y copia `message.chat.id`.
5. Sustituye `https://t.me/TU_CANAL` en `web/index.html` por el enlace real de tu canal y quita el atributo `hidden` de los dos botones de Telegram.

---

## 3. Configurar los Secrets en GitHub

En **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Ejemplo |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `123456789:AAH...` |
| `TELEGRAM_CHANNEL_ID` | `@mi_canal` o `-1001234567890` |
| `TELEGRAM_ADMIN_CHAT_ID` | `987654321` |
| `SITE_URL` | `https://migueltelegram.github.io/comparador-finanzas-es/` |

---

## 4. Despliegue web (GitHub Pages activo / alternativa Cloudflare Pages)

El despliegue en **GitHub Pages** está automatizado en `.github/workflows/pages.yml`: cada push a `web/**` (y cada actualización automática de `web/data/ofertas.json` desde `pipeline.yml`) publica la web en `https://migueltelegram.github.io/comparador-finanzas-es/`.

Si en algún momento quieres desplegar también o migrar a **Cloudflare Pages**:

1. Entra en **Cloudflare Dashboard → Workers & Pages → Create → Pages → Connect to Git** y elige el repositorio.
2. Configuración de build:
   - **Framework preset:** `None`
   - **Build command:** *(vacío)*
   - **Build output directory:** `web`
3. **Save and Deploy** y actualiza el dominio en `web/index.html`, `web/robots.txt`, `web/sitemap.xml` y el secret `SITE_URL`.

---

## 5. Añadir o editar una oferta

Edita **`data/ofertas.json`** (la copia de `web/data/` la sincroniza el workflow; si pruebas en local, cópiala tú con `cp data/ofertas.json web/data/ofertas.json`).

```json
{
  "id": "mi-banco",                       // único, sin espacios
  "nombre": "Cuenta Ejemplo",
  "entidad": "Mi Banco",
  "categoria": "banca_fintech",           // banca_fintech | iban_extranjero | crypto
  "tipo": "cuenta_remunerada",            // cuenta_remunerada | cashback | mixto
  "pais_iban": "ES",                      // ES, DE, NL, LT... o "N/A"
  "es_crypto": false,
  "porcentaje_cashback": 0,               // % sobre el gasto con tarjeta
  "tope_mensual_eur": null,               // null = sin tope
  "tae": 3.0,                             // % TAE
  "saldo_maximo_remunerado": 30000,       // null = sin tope
  "bono_fijo_eur": 20,
  "sin_nomina": true,
  "sin_comisiones": true,
  "resumen_condiciones": "Texto breve con las condiciones.",
  "url_referido": "https://tu-enlace-de-referido",
  "utm_campaign": "mi_banco",
  "fecha_actualizacion": "2026-11-21",
  "activa": true,                         // false = se oculta en la web
  "publicar_telegram": true               // true = se publica en el canal en la próxima ejecución
}
```

*(Los comentarios `//` son solo explicativos: el JSON real no admite comentarios.)*

Para anunciar una oferta en el canal pon `"publicar_telegram": true`, haz commit y push, y lanza el workflow (o espera a la siguiente ejecución). `difusion.py` la publicará, te enviará la confirmación por privado y la volverá a poner a `false` automáticamente.

Para vigilar una nueva página de condiciones añade una entrada a `data/fuentes.json` (`nombre`, `url`, `selector_css`). Usa un selector lo más concreto posible (p. ej. `#tabla-tipos`) para evitar falsos positivos por banners o contenido dinámico; si lo dejas vacío se usa todo el `<body>`.

---

**Aviso:** la información es orientativa y no constituye asesoramiento financiero ni fiscal. Verifica siempre las condiciones en la web oficial de cada entidad.
