# PromosBanco

Web y canal de Telegram gratuitos con **promociones reales de bancos y cuentas remuneradas en España**, publicados en **[https://promosbanco.github.io](https://promosbanco.github.io)**.

- **Web estática ultrarrápida** (`/web`: HTML + CSS + Vanilla JS, cero frameworks) alojada gratis en **GitHub Pages**.
- **Solo avisos de ofertas nuevas en Telegram:** `scripts/difusion.py` compara `data/ofertas.json` contra `data/publicadas.json` y publica únicamente las altas nuevas (sin repetir nunca una oferta).
- **Vigilancia privada** (`scripts/monitor.py`): revisa que ningún enlace esté roto y te avisa solo por privado si falla algo.
- **Automatización 100 % gratuita** cada 12 h en GitHub Actions (`.github/workflows/pipeline.yml`, `pages.yml` y `branding.yml`).

```
├── data/
│   ├── ofertas.json          ← catálogo de ofertas (fuente de verdad)
│   ├── publicadas.json       ← IDs ya anunciados en Telegram (evita duplicados)
│   ├── fuentes.json          ← páginas oficiales vigiladas por monitor.py
│   └── estado_previo.json    ← hashes SHA-256 de esas páginas
├── web/                      ← carpeta publicada en GitHub Pages
│   ├── index.html · styles.css · app.js · logo.png · favicon.png
│   └── data/ofertas.json     ← copia sincronizada automáticamente
├── scripts/
│   ├── monitor.py · difusion.py · requirements.txt
├── marketing/
│   ├── logo_promosbanco.png  ← logotipo corporativo (web + canal Telegram)
│   ├── guia_referidos.md     ← cómo obtener y poner tus enlaces de referido
│   └── mensajes_foros.md     ← textos listos para pegar en foros
└── .github/workflows/
    ├── pipeline.yml          ← monitor + publicación de ofertas nuevas cada 12 h
    ├── pages.yml             ← despliegue automático en GitHub Pages
    └── branding.yml          ← actualiza nombre, descripción y logo del canal
```

## Cómo añadir una oferta nueva

1. Añade el objeto en `data/ofertas.json` con un `"id"` nuevo (y tus campos `"gancho"`, `"requisito_corto"`, `"url_referido"`).
2. Haz push a `main`: en la siguiente ejecución de `pipeline.yml` se publicará automáticamente en Telegram porque su `id` no está todavía en `data/publicadas.json`, y se actualizará la web.

## Probar la web en local

```bash
cd web && python3 -m http.server 8080
# Abre http://localhost:8080
```

---

**Aviso:** información orientativa; no constituye asesoramiento financiero ni fiscal. Verifica siempre las condiciones en la web del banco antes de contratar.
