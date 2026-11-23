/* =========================================================
   PromosBanco — lógica de la web (Vanilla JS, sin dependencias)
   ========================================================= */
'use strict';

(() => {
  const DATA_URL = 'data/ofertas.json';
  const SHORT_URL = 'https://migueltelegram.github.io';
  const GASTO_TARJETA_MES = 500;

  const COLORES = {
    'BBVA': '#004481', 'Banco Sabadell': '#006dff', 'Banco Santander': '#ec0000', 'ABANCA': '#0369a1',
    'Deutsche Bank': '#0018a8', 'Cajamar': '#1e3a8a', 'Kutxabank': '#111827', 'Unicaja': '#15803d',
    'CaixaBank': '#007eae', 'imagin': '#0f172a', 'ING': '#ea580c', 'Ibercaja': '#1e40af',
    'Bankinter': '#c2410c', 'Openbank': '#dc2626', 'MyInvestor': '#4f46e5', 'B100 (Abanca)': '#0ea5e9',
    'Renault Bank': '#ca8a04', 'N26': '#0d9488', 'Trade Republic': '#18181b', 'Revolut': '#2563eb',
    'Raisin': '#0f766e', 'bunq': '#16a34a', 'Bank Norwegian': '#b91c1c', 'Crypto.com': '#1d4ed8', 'Nexo': '#1e40af',
  };
  const INICIALES = {
    'Banco Sabadell': 'SB', 'Banco Santander': 'BS', 'Deutsche Bank': 'DB', 'B100 (Abanca)': 'B1',
    'Renault Bank': 'RB', 'Trade Republic': 'TR', 'Bank Norwegian': 'BN', 'Crypto.com': 'C', 'imagin': 'im',
    'MyInvestor': 'MI', 'Kutxabank': 'KB', 'Cajamar': 'CJ', 'CaixaBank': 'CX',
  };
  const PAISES = { DE: 'alemán', NL: 'holandés', NO: 'noruego', FR: 'francés', LT: 'lituano', IE: 'irlandés' };

  const fmtEUR = new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0, useGrouping: 'always' });
  const fmtFecha = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'long', timeZone: 'UTC' });
  const fmtMes = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

  const $ = (s) => document.querySelector(s);
  const ui = {
    tabs: Array.from(document.querySelectorAll('.tab')),
    buscar: $('#buscar'),
    sinNomina: $('#sin-nomina'),
    ahorros: $('#ahorros'),
    lista: $('#ofertas'),
    resumen: $('#resumen'),
    fecha: $('#fecha-actualizacion'),
    toast: $('#toast'),
  };

  const params = new URLSearchParams(location.search);
  const destacada = params.get('o') || params.get('oferta');
  const estado = { ofertas: [], tipo: 'todas', busqueda: '', scrollHecho: false, toastTimer: null };

  /* ---------- Utilidades ---------- */
  const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);
  const hoyISO = () => new Date().toISOString().slice(0, 10);
  const fecha = (iso) => {
    const d = new Date(`${iso}T00:00:00Z`);
    return Number.isNaN(d.getTime()) ? iso : fmtFecha.format(d);
  };
  const diasHasta = (iso) => Math.round((new Date(`${iso}T00:00:00Z`) - new Date(`${hoyISO()}T00:00:00Z`)) / 86400000);

  function el(tag, attrs = {}, children = []) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') n.className = v;
      else if (k === 'text') n.textContent = v;
      else if (k === 'style') n.style.cssText = v;
      else n.setAttribute(k, v === true ? '' : String(v));
    }
    for (const c of [].concat(children)) {
      if (c === null || c === undefined || c === false) continue;
      n.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return n;
  }

  function iniciales(entidad) {
    if (INICIALES[entidad]) return INICIALES[entidad];
    const t = String(entidad || '?').replace(/[^\p{L}\p{N} ]/gu, '').trim();
    return t.length <= 4 ? t : t.slice(0, 2).toUpperCase();
  }

  function urlConUtm(o) {
    try {
      const u = new URL(o.url_referido);
      u.searchParams.set('utm_source', 'promosbanco');
      u.searchParams.set('utm_medium', 'web');
      u.searchParams.set('utm_campaign', o.utm_campaign || o.id);
      return u.toString();
    } catch {
      return o.url_referido || '#';
    }
  }

  function toast(texto) {
    ui.toast.textContent = texto;
    ui.toast.hidden = false;
    clearTimeout(estado.toastTimer);
    estado.toastTimer = setTimeout(() => { ui.toast.hidden = true; }, 2400);
  }

  async function copiar(texto, mensaje) {
    try {
      await navigator.clipboard.writeText(texto);
      toast(mensaje);
    } catch {
      toast('No se pudo copiar automáticamente');
    }
  }

  /* ---------- Cálculo ---------- */
  function ganancia(o, ahorros) {
    const intereses = Math.min(ahorros, o.saldo_maximo_remunerado ?? Infinity) * (num(o.tae) / 100);
    const cashback = Math.min(GASTO_TARJETA_MES * (num(o.porcentaje_cashback) / 100), o.tope_mensual_eur ?? Infinity) * 12;
    const bono = num(o.bono_fijo_eur);
    return { intereses, cashback, bono, total: intereses + cashback + bono };
  }

  /* ---------- Texto para foros (igual que Telegram) ---------- */
  function textoForo(o) {
    const lineas = [`🏦 ${o.entidad}`, `💶 ${o.gancho || o.etiqueta_promo || o.nombre}`, ''];
    lineas.push(`✅ ${o.requisito_corto || o.requisitos_resumen || ''}`);
    if (o.fecha_fin_promo) lineas.push(`⏰ Hasta el ${fecha(o.fecha_fin_promo)}`);
    if (o.codigo_promo) lineas.push(`🔑 Código: ${o.codigo_promo}`);
    lineas.push('', `👉 ${SHORT_URL}`);
    return lineas.join('\n');
  }

  /* ---------- Render ---------- */
  function hechos(o) {
    const req = String(o.requisito_corto || o.requisitos_resumen || '');
    const reqLow = req.toLowerCase();
    const lista = [el('li', { text: req })];
    const perm = String(o.permanencia || '');
    if (perm && !/^sin permanencia/i.test(perm) && !reqLow.includes('mes')) {
      lista.push(el('li', { class: 'warn', text: `Permanencia: ${perm}` }));
    }
    if (o.es_crypto) {
      lista.push(el('li', { class: 'warn', text: 'Servicio cripto (sin fondo de garantía bancario)' }));
    } else if (o.pais_iban && o.pais_iban !== 'ES') {
      lista.push(el('li', { class: 'warn', text: `IBAN ${PAISES[o.pais_iban] || o.pais_iban} (lo declaras tú en la renta)` }));
    }
    if (o.sin_comisiones) lista.push(el('li', { text: 'Sin comisiones' }));
    return el('ul', { class: 'facts' }, lista);
  }

  function tarjeta(item, pos) {
    const { o, g } = item;
    const pills = [];
    if (pos === 1 && g.total > 0) pills.push(el('span', { class: 'pill pill-top', text: 'La que más da' }));
    if (o.fecha_fin_promo) {
      const d = diasHasta(o.fecha_fin_promo);
      if (d <= 14) pills.push(el('span', { class: 'pill pill-time', text: d <= 0 ? 'Último día' : `Quedan ${d} día${d === 1 ? '' : 's'}` }));
    }

    const clases = ['card'];
    if (pos === 1 && g.total > 0) clases.push('is-top');
    if (destacada === o.id) clases.push('is-highlight');

    const partes = [];
    if (g.bono > 0) partes.push(`${fmtEUR.format(g.bono)} de regalo`);
    if (g.intereses > 0) partes.push(`${fmtEUR.format(g.intereses)} de intereses`);
    if (g.cashback > 0) partes.push(`${fmtEUR.format(g.cashback)} en compras`);

    const detalles = [
      ['Condiciones', o.resumen_condiciones],
      o.permanencia ? ['Permanencia', o.permanencia] : null,
      o.fgd ? ['Protección', o.fgd] : null,
      o.fecha_fin_promo ? ['Válida hasta', fecha(o.fecha_fin_promo)] : null,
      g.cashback > 0 ? ['Cálculo', `Compras con tarjeta: suponemos ${fmtEUR.format(GASTO_TARJETA_MES)}/mes`] : null,
      ['Revisada', fmtMes.format(new Date(`${o.fecha_actualizacion}T00:00:00Z`))],
    ].filter(Boolean);

    return el('li', { id: `card-${o.id}`, class: clases.join(' ') }, [
      el('div', { class: 'card-head' }, [
        el('span', { class: 'avatar', 'aria-hidden': 'true', style: `background:${COLORES[o.entidad] || '#16a34a'}`, text: iniciales(o.entidad) }),
        el('div', {}, [el('h3', { class: 'entity', text: o.entidad }), el('p', { class: 'product', text: o.nombre })]),
        pills.length ? el('div', { class: 'pills' }, pills) : null,
      ]),
      el('p', { class: 'hook', text: o.gancho || o.etiqueta_promo }),
      el('p', { class: 'estimate' }, g.total > 0
        ? ['Con tus ahorros ganas ', el('strong', { text: `≈ ${fmtEUR.format(g.total)}` }), ` el primer año${partes.length > 1 ? ` (${partes.join(' + ')})` : ''}`]
        : ['Ventaja en tus compras con tarjeta']),
      hechos(o),
      o.codigo_promo ? el('button', { type: 'button', class: 'code', 'data-code': o.codigo_promo }, [
        el('span', {}, ['Código: ', el('b', { text: o.codigo_promo })]),
        el('span', { text: 'Copiar' }),
      ]) : null,
      el('div', { class: 'card-actions' }, [
        el('a', { class: 'btn btn-primary', href: urlConUtm(o), target: '_blank', rel: 'nofollow sponsored noopener', text: `Abrir cuenta en ${o.entidad} →` }),
        el('details', { class: 'details' }, [
          el('summary', { text: 'Ver detalles' }),
          el('dl', {}, detalles.flatMap(([k, v]) => [el('dt', { text: k }), el('dd', { text: v })])),
          el('button', { type: 'button', class: 'btn btn-ghost', 'data-copy': o.id, text: '📋 Copiar para compartir' }),
        ]),
      ]),
    ]);
  }

  function render() {
    const ahorros = num(ui.ahorros.value);
    const soloSinNomina = ui.sinNomina.checked;
    const hoy = hoyISO();
    const q = estado.busqueda.trim().toLowerCase();

    const visibles = estado.ofertas
      .filter((o) => o.activa === true && (!o.fecha_fin_promo || o.fecha_fin_promo >= hoy))
      .filter((o) => !soloSinNomina || o.sin_nomina === true)
      .filter((o) => estado.tipo === 'todas'
        || (estado.tipo === 'regalo' && num(o.bono_fijo_eur) > 0)
        || (estado.tipo === 'intereses' && num(o.tae) > 0))
      .filter((o) => !q || `${o.entidad} ${o.nombre} ${o.gancho || ''} ${o.requisito_corto || ''}`.toLowerCase().includes(q))
      .map((o) => ({ o, g: ganancia(o, ahorros) }))
      .sort((a, b) => b.g.total - a.g.total);

    const frag = document.createDocumentFragment();
    visibles.forEach((it, i) => frag.append(tarjeta(it, i + 1)));
    if (!visibles.length) frag.append(el('li', { class: 'empty', text: 'No hay ofertas con estos filtros. Prueba a quitar “Solo sin nómina”.' }));
    ui.lista.replaceChildren(frag);

    const n = visibles.length;
    ui.resumen.textContent = n
      ? `${n} ${n === 1 ? 'oferta' : 'ofertas'} ordenadas de más a menos dinero el primer año, con ${fmtEUR.format(ahorros)} de ahorros.`
      : '';

    if (destacada && !estado.scrollHecho) {
      const t = document.getElementById(`card-${destacada}`);
      if (t) {
        estado.scrollHecho = true;
        t.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }

  /* ---------- Eventos ---------- */
  function initEventos() {
    ui.tabs.forEach((tab) => tab.addEventListener('click', () => {
      estado.tipo = tab.dataset.tipo;
      ui.tabs.forEach((t) => t.setAttribute('aria-selected', String(t === tab)));
      render();
    }));
    if (ui.buscar) {
      ui.buscar.addEventListener('input', () => {
        estado.busqueda = ui.buscar.value;
        render();
      });
    }
    ui.sinNomina.addEventListener('change', render);
    ui.ahorros.addEventListener('change', render);

    ui.lista.addEventListener('click', (e) => {
      const t = e.target instanceof Element ? e.target : null;
      if (!t) return;
      const code = t.closest('[data-code]');
      if (code) {
        copiar(code.dataset.code, `Código ${code.dataset.code} copiado`);
        return;
      }
      const cp = t.closest('[data-copy]');
      if (cp) {
        const o = estado.ofertas.find((x) => x.id === cp.dataset.copy);
        if (o) copiar(textoForo(o), 'Texto copiado, ¡pégalo donde quieras!');
      }
    });
  }

  /* ---------- Arranque ---------- */
  async function init() {
    initEventos();
    try {
      const res = await fetch(DATA_URL, { cache: 'no-cache' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const datos = await res.json();
      if (!Array.isArray(datos)) throw new Error('Formato no válido');
      estado.ofertas = datos;
      const ultima = datos.map((o) => o.fecha_actualizacion).filter(Boolean).sort().pop();
      if (ultima && ui.fecha) ui.fecha.textContent = fmtMes.format(new Date(`${ultima}T00:00:00Z`));
      render();
    } catch (err) {
      console.warn('No se pudieron cargar las ofertas:', err);
      ui.resumen.textContent = 'No se pudieron cargar las ofertas. Recarga la página.';
    }
  }

  init();
})();
