# Auditoría mensual de PromosBanco

Historial de revisiones mensuales del proyecto **PromosBanco** ([promosbanco.github.io](https://promosbanco.github.io) · repositorio `promosbanco/promosbanco.github.io`). Cada mes se añade la nueva auditoría arriba del todo y su resumen se envía automáticamente a tu bot privado de Telegram.

---

## Auditoría mensual · Noviembre 2026 (2026-11-23)

### Resumen para Telegram

- **Estado general:** Todo operativo al 100 % y 0 €/mes sin tarjeta (`https://promosbanco.github.io` en directo, **28 ofertas activas**, canal de Telegram vacío esperando ofertas nuevas y workflows en verde).
- **URGENTE (dinero):** Las **28 ofertas** todavía enlazan a la web oficial del banco y no a tus enlaces/códigos de **Plan Amigo**. Hasta que pongas los tuyos (Santander 80 €, BBVA 50–70 €, MyInvestor 25 €, imagin 50–75 €, Revolut, Raisin) no cobras comisiones.
- **URGENTE (caducan en 7–9 días):** Openbank `OPEN325` (**30 nov**), BBVA Black Friday `TARJETA150` (**1 dic**) y Sabadell 400 € + 2,75 % TAE (**2 dic**). Revisa si los prorrogan para actualizar o publicar relevos.
- **Identidad Telegram:** El canal ya se llama **PromosBanco**, pero su enlace público sigue siendo `@comparador_finanzas_es`. Conviene cambiar el `@usuario` a `@promosbanco` o `@promosbanco_es` si está libre.
- **Deprecado detectado en GitHub Actions:** Avisos reales en logs de **`Node.js 20 is deprecated`** (`actions/checkout@v4`, `setup-python@v5`, `upload-artifact@v4`, `deploy-pages@v4`). Hay que subir `checkout@v5` y `setup-python@v6`.
- **Limpieza pendiente:** Quedan campos obsoletos en `ofertas.json` (`texto_telegram`, `categoria`, además de un pequeño desfase en `unicaja-nomina` dentro de ese campo sin uso), el repo antiguo `MiguelTelegram.github.io` y el workflow puntual `limpiar_canal.yml`.
- **Hueco importante (medición):** La web no tiene ninguna analítica. No sabes cuántas visitas entran ni qué bancos se pulsan más. Recomendado añadir **GoatCounter** o **Umami Cloud gratis** (0 € y sin banner de cookies).
- **Mejora rápida del monitor:** Añadir aviso por privado 3 días antes de que caduque una oferta (`fecha_fin_promo`) y vigilar también las páginas de Openbank, Bankinter y Sabadell en `fuentes.json`.
- **SEO y crecimiento gratis:** Dar de alta `sitemap.xml` en **Google Search Console**, crear una imagen horizontal (`1200x630`) para compartir bonito en WhatsApp/foros y añadir botón nativo de **Compartir** en móvil.

---

### Estado general del proyecto

- **Web (`web/`):** HTML5 + CSS3 + Vanilla JS puro (`index.html`, `styles.css`, `app.js`), sin dependencias externas ni rastreadores, carga rápida en `https://promosbanco.github.io` (`HTTP 200`).
- **Datos (`data/`):** **28 ofertas activas** cubriendo regalos por nómina, promos sin nómina, cuentas remuneradas, IBAN europeo y tarjetas cashback/cripto. Las 28 están marcadas en `data/publicadas.json` para no repetir mensajes antiguos en Telegram.
- **Automatización (`.github/workflows/`):**
  - `pipeline.yml`: se ejecuta cada 12 horas (`monitor.py` + `difusion.py`) y redespliega GitHub Pages si cambia `web/data/ofertas.json`. Últimas ejecuciones en verde (`27` enlaces comprobados en `[OK]`, `unicaja-nomina` omitido por geobloqueo).
  - `pages.yml`: despliegue automático al tocar `web/`.
  - `branding.yml` y `notificar_audit.yml`: operativos bajo demanda.
- **Coste mensual:** **0 €** (todo en GitHub Pages + GitHub Actions + Bot API de Telegram, sin tarjetas vinculadas).

---

### Qué está caducado, próximo a vencer o deprecado

1. **Promociones con fecha límite inminente en `data/ofertas.json`:**
   - **Openbank (`openbank-remunerada`, código `OPEN325`):** vence el **30/11/2026** (en 7 días).
   - **BBVA Black Friday (`bbva-black-friday`, código `TARJETA150`):** vence el **01/12/2026** (en 8 días).
   - **Banco Sabadell (`sabadell-online`, 400 € + 2,75 % TAE):** vence el **02/12/2026** (en 9 días).
   - **Bankinter Cuenta Digital (`bankinter-digital`, 3 % TAE sin nómina):** vence el **16/12/2026**.
   - **Kutxabank, MyInvestor Plan Amigo y Openbank `NOMINA300F`:** vencen el **31/12/2026**.
   - *Aunque `app.js` y `difusion.py` ya ocultan automáticamente ofertas pasadas de fecha, conviene revisar el 1–3 de diciembre qué bancos lanzan campaña nueva de Navidad para no perder tráfico.*
2. **Acciones deprecadas en GitHub Actions (aviso real en logs):**
   - Los runs recientes de `pages.yml` y `pipeline.yml` muestran el warning: `Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24`.
   - Solución sencilla: actualizar `actions/checkout@v4` → **`@v5`** y `actions/setup-python@v5` → **`@v6`** en `.github/workflows/` (y activar Dependabot para `github-actions`).
3. **Vigilancia incompleta en `data/fuentes.json`:**
   - Solo se monitorizan 5 páginas (`Trade Republic`, `bunq`, `Raisin`, `Crypto.com`, `MyInvestor`). Faltan páginas clave con promociones frecuentes como **Openbank**, **Bankinter** o **Sabadell**.

---

### Qué sobra o no tiene sentido mantener

1. **Campos heredados sin uso en `data/ofertas.json`:**
   - Tras simplificar el diseño a *PromosBanco*, el campo `texto_telegram` ya no lo leen ni `web/app.js` ni `scripts/difusion.py` (que ahora usan `gancho`, `requisito_corto`, `fecha_fin_promo` y `codigo_promo`). De hecho, en `unicaja-nomina`, `texto_telegram` todavía dice `20.000 €` mientras el dato real ya es `50.000 €`.
   - El campo `categoria` tampoco se filtra ya en `web/app.js`. Conviene eliminarlo en una limpieza futura para aligerar el JSON y evitar contradicciones.
2. **Repositorio antiguo `promosbanco/MiguelTelegram.github.io`:**
   - Era el acortador temporal previo a renombrar la cuenta. Ya no apunta a nada necesario y puedes borrarlo desde GitHub → Settings para dejar tu cuenta limpia con un único proyecto web.
3. **Workflow puntual `limpiar_canal.yml`:**
   - Cumplió su función de vaciar el canal. Si no piensas vaciarlo más veces, puede eliminarse o dejarse archivado en una sola rama/nota para mantener limpia la pestaña *Actions*.
4. **Duplicación manual de `ofertas.json` (`data/ofertas.json` y `web/data/ofertas.json`):**
   - Aunque `pipeline.yml` las sincroniza, en el día a día si editas solo `data/ofertas.json` en local hay que acordarse de copiarla a `web/data/`. Un paso de sincronización en `pages.yml` evitaría olvidos.

---

### Mejoras rápidas de mayor impacto

1. **Conectar tus enlaces/códigos de Plan Amigo reales (prioridad #1):**
   - Ahora mismo **28 de 28 ofertas** mandan a páginas genéricas de cada banco. Empieza por los que más pagan por amigo sin requerir gran infraestructura: **Banco Santander (80 €)**, **BBVA (50–70 €)**, **imagin (50–75 € sin nómina)**, **MyInvestor (25 € hasta 60 amigos)**, **Raisin (50 €)** y **Revolut**.
2. **Unificar el `@usuario` del canal de Telegram con la marca:**
   - La web es `promosbanco.github.io` y el canal se titula `PromosBanco`, pero la URL sigue siendo `t.me/comparador_finanzas_es`. Cambia el alias en Telegram (si está libre `@promosbanco` o `@promosbanco_es`) y actualízalo en `web/index.html`.
3. **Avisos privados de caducidad en `scripts/monitor.py`:**
   - Añadir una comprobación sencilla para que te avise al bot privado cuando falten 3 días para `fecha_fin_promo` de cualquier oferta. Así siempre sabes cuándo toca buscar el reemplazo.
4. **Imagen social panorámica (`1200x630`) + botón nativo de compartir en móvil:**
   - Ahora la etiqueta `og:image` usa `logo.png` cuadrado (`256x256`). Una imagen apaisada con «PromosBanco · Los bancos te pagan por abrir cuenta» hace que el enlace destaque muchísimo más al pegarlo en WhatsApp, Telegram o foros.
   - En móvil, usar la **Web Share API (`navigator.share`)** junto al botón de copiar facilita que cualquier visitante envíe la promo por WhatsApp en 1 toque.

---

### Nuevas funcionalidades y monetización

1. **Etiqueta clara «Con código de invitación» / tutorial en 3 pasos dentro de la ficha:**
   - En bancos donde el Plan Amigo funciona metiendo **código al darte de alta** (BBVA, MyInvestor, imagin) y no solo por URL, conviene destacar el paso exacto (*«1. Pulsa Abrir cuenta → 2. Pega el código XXX en el campo Plan Amigo»*) para no perder conversiones.
2. **Guía rápida de «Combinaciones ganadoras» (opcional, 1 bloque pequeño):**
   - Por ejemplo: cuenta nómina que paga bono alto en efectivo (Santander/BBVA/Sabadell) + cuenta remunerada sin nómina para el resto de ahorros (Bankinter Digital 3 % / Trade Republic 4,07 %). Da mucho valor al usuario y multiplica por 2 tus posibles altas.
3. **Alta en redes de afiliación gratuitas (fase 2, cuando tengas tráfico):**
   - En bancos donde no tengas Plan Amigo (Openbank, Bankinter, Sabadell, ING, Cajamar, Kutxabank), plataformas gratuitas como **Awin**, **TradeTracker** o **FinanceAds** permiten cobrar por cada alta válida sin límite de 10 amigos usando `https://promosbanco.github.io` como soporte.
4. **Indicador o filtro rápido de permanencia:**
   - Muchos usuarios en foros solo buscan promos *«Sin permanencia»* además de *«Sin nómina»*. Un pequeño chip o aviso visual mejora la confianza y reduce abandonos.

---

### Nuevas tecnologías y herramientas gratuitas (0 €/mes)

1. **Analítica sin cookies ni tarjeta (`GoatCounter` o `Umami Cloud` plan Hobby):**
   - Totalmente gratuitas, respetuosas con el RGPD (sin necesidad de poner un molesto banner de cookies si no se usan cookies/identificadores personales) y permiten ver páginas vistas, desde qué foro entran (Chollometro, Rankia, Telegram) y qué botón `Abrir cuenta en ...` recibe más clics.
2. **Google Search Console + Bing Webmaster Tools (gratis):**
   - Enviar `https://promosbanco.github.io/sitemap.xml` para empezar a indexar en Google y ver con qué palabras clave te encuentra la gente cada mes.
3. **JSON-LD ampliado (`ItemList` además de `FAQPage`):**
   - Manteniendo 0 frameworks y HTML puro, añadir un bloque ligero de datos estructurados y mantener la web instalable como **PWA básica (`manifest.webmanifest`)** permite que quien quiera pueda fijar PromosBanco en la pantalla del móvil.
4. **Validación automática en GitHub Actions + Dependabot:**
   - Un pequeño check automático en cada push (validar JSON, enlaces vacíos, fechas y `node --check`) evita subir por error un archivo roto que deje la web en blanco, y Dependabot mantiene las actions actualizadas sin Node 20 deprecado.

---

### Plan de acción sugerido para este mes

1. **[Esta semana · 10 min]** Sacar de tus apps tus primeros 3 enlaces/códigos de **Plan Amigo** (empezando por **Santander**, **BBVA**, **MyInvestor**, **imagin** o **Revolut**) y sustituir las URLs en `data/ofertas.json`.
2. **[Esta semana · 2 min]** Cambiar el `@usuario` del canal de Telegram a `@promosbanco` (o `@promosbanco_es`) y borrar el repositorio antiguo `MiguelTelegram.github.io`.
3. **[30 nov – 2 dic · 15 min]** Revisar qué sustituye a **Openbank `OPEN325`**, **BBVA `TARJETA150`** y **Sabadell 400 €** al expirar; en cuanto haya promo nueva, añadirla a `data/ofertas.json` para estrenar el canal vacío de **PromosBanco** con mensajes cortos.
4. **[Opcional · 10 min]** Actualizar `actions/checkout@v5` y `setup-python@v6`, enviar `sitemap.xml` a Google Search Console y valorar añadir analítica gratuita sin cookies (**GoatCounter**) para medir qué bancos convierten mejor.
