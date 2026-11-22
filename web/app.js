/* =========================================================
   Comparador Finanzas ES — lógica interactiva completa
   Vanilla JS, sin dependencias.
   ========================================================= */
'use strict';

(() => {
  const DATA_URL = 'data/ofertas.json';
  const NOVEDADES_URL = 'data/novedades.json';
  const SHORT_URL = 'https://migueltelegram.github.io';
  const RETENCION_NETO = 0.81;

  const LIMITES = {
    gasto: { min: 0, max: 3000 },
    saldo: { min: 0, max: 100000 },
  };

  const PAISES = {
    ES: 'España', DE: 'Alemania', NL: 'Países Bajos', NO: 'Noruega',
    FR: 'Francia', IE: 'Irlanda', LT: 'Lituania', BE: 'Bélgica',
  };

  const AVATARES = {
    'bbva-black-friday': 'BB', 'bbva-plan-1060': 'BB', 'sabadell-online': 'SB',
    'santander-online': 'BS', 'abanca-nomina': 'AB', 'deutsche-bank-mas': 'DB',
    'unicaja-nomina': 'UN', 'caixabank-online': 'CX', 'imagin-nomina': 'im',
    'ing-nomina': 'ING', 'ibercaja-vamos': 'IB', 'bankinter-nomina': 'BK',
    'openbank-remunerada': 'OB', 'b100-health': 'B1', 'renault-bank-contigo': 'RB',
    'trade-republic': 'TR', 'revolut-remunerada': 'R', 'raisin-bienvenida': 'Ra',
    'bunq-free': 'bq', 'bank-norwegian': 'BN', 'cryptocom-levelup': 'C', 'nexo-card': 'Nx',
  };

  const FILTROS = {
    promos: (o) => o.es_promo_temporal === true || num(o.bono_fijo_eur) > 0,
    remunerada: (o) => num(o.tae) > 0,
    cashback: (o) => num(o.porcentaje_cashback) > 0,
    ibanES: (o) => o.pais_iban === 'ES',
    ibanUE: (o) => esIbanExtranjero(o),
    crypto: (o) => o.es_crypto === true,
    sinNomina: (o) => o.sin_nomina === true,
  };

  const fmtEUR = new Intl.NumberFormat('es-ES', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 2, useGrouping: 'always',
  });
  const fmtEURCorto = new Intl.NumberFormat('es-ES', {
    style: 'currency', currency: 'EUR', maximumFractionDigits: 0, useGrouping: 'always',
  });
  const fmtPct = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  const fmtFecha = new Intl.DateTimeFormat('es-ES', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

  const $ = (sel) => document.querySelector(sel);

  const ui = {
    gastoRange: $('#gasto-range'),
    gastoNum: $('#gasto-num'),
    saldoRange: $('#saldo-range'),
    saldoNum: $('#saldo-num'),
    presets: Array.from(document.querySelectorAll('.preset-btn')),
    toggleNomina: $('#toggle-nomina'),
    toggleNeto: $('#toggle-neto'),
    buscar: $('#buscar'),
    ordenar: $('#ordenar'),
    chips: Array.from(document.querySelectorAll('.chip')),
    comboBanner: $('#combo-banner'),
    lista: $('#resultados'),
    resumen: $('#resumen'),
    avisoFiscal: $('#aviso-fiscal'),
    statMejor: $('#stat-mejor'),
    statOfertas: $('#stat-ofertas'),
    statBonos: $('#stat-bonos'),
    novedadesSec: $('#novedades'),
    listaNovedades: $('#lista-novedades'),
    themeToggle: $('#theme-toggle'),
    compareBar: $('#compare-bar'),
    compareCount: $('#compare-count'),
    btnLimpiarComp: $('#btn-limpiar-comp'),
    btnAbrirComp: $('#btn-abrir-comp'),
    modalComparar: $('#modal-comparar'),
    btnCerrarComp: $('#btn-cerrar-comp'),
    tablaComparar: $('#tabla-comparar'),
    toast: $('#toast'),
  };

  const params = new URLSearchParams(window.location.search);
  const ofertaDestacada = params.get('o') || params.get('oferta');

  const estado = {
    ofertas: [],
    novedades: [],
    filtros: new Set(),
    comparar: new Set(),
    busqueda: '',
    orden: 'total',
    scrollHecho: false,
    toastTimer: null,
  };

  /* ---------- Tema claro / oscuro manual ---------- */
  function aplicarTema(tema) {
    const oscuro = tema === 'dark';
    document.documentElement.dataset.theme = oscuro ? 'dark' : 'light';
    if (ui.themeToggle) {
      ui.themeToggle.setAttribute('aria-pressed', String(oscuro));
      ui.themeToggle.title = oscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
    }
  }

  function initTema() {
    let guardado = 'light';
    try {
      if (localStorage.getItem('tema') === 'dark') guardado = 'dark';
    } catch { /* sin storage */ }
    aplicarTema(guardado);

    if (ui.themeToggle) {
      ui.themeToggle.addEventListener('click', () => {
        const siguiente = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        aplicarTema(siguiente);
        try { localStorage.setItem('tema', siguiente); } catch { /* noop */ }
      });
    }
  }

  /* ---------- Utilidades ---------- */
  function num(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  function clamp(v, { min, max }) {
    return Math.min(Math.max(num(v), min), max);
  }

  function esIbanExtranjero(o) {
    return Boolean(o.pais_iban) && o.pais_iban !== 'ES' && o.pais_iban !== 'N/A';
  }

  function actualizarProgreso(range, limites) {
    const val = clamp(range.value, limites);
    const pct = ((val - limites.min) / (limites.max - limites.min)) * 100;
    range.style.setProperty('--progress', `${pct}%`);
  }

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') node.className = v;
      else if (k === 'text') node.textContent = v;
      else node.setAttribute(k, v === true ? '' : String(v));
    }
    for (const child of [].concat(children)) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function formatearFecha(iso) {
    const d = new Date(`${iso}T00:00:00Z`);
    return Number.isNaN(d.getTime()) ? iso : fmtFecha.format(d);
  }

  function iniciales(o) {
    if (AVATARES[o.id]) return AVATARES[o.id];
    const palabras = String(o.entidad || '?').trim().split(/\s+/);
    return palabras.length > 1
      ? (palabras[0][0] + palabras[1][0]).toUpperCase()
      : String(o.entidad || '?').slice(0, 2);
  }

  function urlConUtm(oferta) {
    try {
      const url = new URL(oferta.url_referido);
      url.searchParams.set('utm_source', 'comparador');
      url.searchParams.set('utm_medium', 'web');
      url.searchParams.set('utm_campaign', oferta.utm_campaign || oferta.id);
      return url.toString();
    } catch {
      return oferta.url_referido || '#';
    }
  }

  function mostrarToast(texto) {
    if (!ui.toast) return;
    ui.toast.textContent = texto;
    ui.toast.hidden = false;
    clearTimeout(estado.toastTimer);
    estado.toastTimer = setTimeout(() => { ui.toast.hidden = true; }, 2600);
  }

  async function copiarTexto(texto, mensajeToast) {
    try {
      await navigator.clipboard.writeText(texto);
      mostrarToast(mensajeToast);
    } catch {
      mostrarToast('No se pudo copiar automáticamente.');
    }
  }

  /* ---------- Cálculo ---------- */
  function calcular(oferta, gastoMensual, saldo, esNeto) {
    const factor = esNeto ? RETENCION_NETO : 1;
    const intereses = Math.min(saldo, oferta.saldo_maximo_remunerado ?? Infinity) * (num(oferta.tae) / 100) * factor;
    const cashback = Math.min(
      gastoMensual * (num(oferta.porcentaje_cashback) / 100),
      oferta.tope_mensual_eur ?? Infinity,
    ) * 12;
    const bono = num(oferta.bono_fijo_eur) * factor;
    return { intereses, cashback, bono, total: intereses + cashback + bono };
  }

  function leerValores() {
    return {
      gasto: clamp(ui.gastoNum.value, LIMITES.gasto),
      saldo: clamp(ui.saldoNum.value, LIMITES.saldo),
      permiteNomina: ui.toggleNomina ? ui.toggleNomina.checked : true,
      esNeto: ui.toggleNeto ? ui.toggleNeto.checked : false,
    };
  }

  function actualizarPresets() {
    const { gasto, saldo } = leerValores();
    ui.presets.forEach((btn) => {
      const v = Number(btn.dataset.val);
      const actual = btn.dataset.target === 'saldo' ? saldo : gasto;
      btn.classList.toggle('is-active', actual === v);
    });
  }

  /* ---------- Texto para copiar y pegar en foros ---------- */
  function textoParaForo(oferta, res, esNeto) {
    const partes = [`💰 ${oferta.entidad} — ${oferta.nombre}`];
    if (oferta.etiqueta_promo) partes.push(`🏷 ${oferta.etiqueta_promo}`);
    partes.push(`👉 Beneficio estimado: +${fmtEUR.format(res.total)}/año (${esNeto ? 'neto aprox.' : 'bruto'})`);
    if (num(oferta.bono_fijo_eur) > 0) partes.push(`• Regalo efectivo: ${fmtEURCorto.format(oferta.bono_fijo_eur)} (bruto)`);
    if (num(oferta.tae) > 0) partes.push(`• Rentabilidad: ${fmtPct.format(oferta.tae)}% TAE`);
    if (num(oferta.porcentaje_cashback) > 0) partes.push(`• Cashback: ${fmtPct.format(oferta.porcentaje_cashback)}%`);
    if (oferta.requisitos_resumen) partes.push(`✅ Qué pide: ${oferta.requisitos_resumen}`);
    if (oferta.codigo_promo) partes.push(`🔑 Código promo: ${oferta.codigo_promo}`);
    partes.push(`🧮 Calcula cuánto ganarías tú aquí: ${SHORT_URL}`);
    return partes.join('\n');
  }

  /* ---------- Render combinación óptima ---------- */
  function renderCombo(items, esNeto) {
    if (!ui.comboBanner) return;
    if (items.length < 2) {
      ui.comboBanner.hidden = true;
      return;
    }

    const mejorCuenta = [...items]
      .filter(({ oferta }) => num(oferta.tae) > 0 || num(oferta.bono_fijo_eur) > 0)
      .sort((a, b) => (b.resultado.intereses + b.resultado.bono) - (a.resultado.intereses + a.resultado.bono))[0];

    const mejorTarjeta = [...items]
      .filter(({ oferta }) => (!mejorCuenta || oferta.id !== mejorCuenta.oferta.id) && num(oferta.porcentaje_cashback) > 0)
      .sort((a, b) => b.resultado.cashback - a.resultado.cashback)[0];

    if (!mejorCuenta || !mejorTarjeta || mejorTarjeta.resultado.cashback <= 0) {
      ui.comboBanner.hidden = true;
      return;
    }

    const gananciaCuenta = mejorCuenta.resultado.intereses + mejorCuenta.resultado.bono;
    const gananciaTarjeta = mejorTarjeta.resultado.cashback;
    const totalCombo = gananciaCuenta + gananciaTarjeta;
    const mejorIndividual = items.reduce((max, it) => Math.max(max, it.resultado.total), 0);

    if (totalCombo <= mejorIndividual + 5) {
      ui.comboBanner.hidden = true;
      return;
    }

    ui.comboBanner.replaceChildren(
      el('p', {}, [
        el('strong', { text: '✨ Estrategia combinada recomendada: ' }),
        `tu saldo y regalo en `,
        el('strong', { text: mejorCuenta.oferta.entidad }),
        ` (+${fmtEUR.format(gananciaCuenta)}) + tus compras con `,
        el('strong', { text: mejorTarjeta.oferta.entidad }),
        ` (+${fmtEUR.format(gananciaTarjeta)}).`,
      ]),
      el('span', { class: 'combo-total', text: `+${fmtEUR.format(totalCombo)} ${esNeto ? 'neto/año' : 'bruto/año'}` }),
    );
    ui.comboBanner.hidden = false;
  }

  /* ---------- Render tarjetas ---------- */
  function crearBadges(o, esMejor) {
    const badges = [];
    if (esMejor) badges.push(['Mejor opción', 'badge-best']);
    if (o.pais_iban === 'ES') badges.push(['IBAN ES', 'badge-es']);
    else if (esIbanExtranjero(o)) badges.push([`IBAN ${o.pais_iban}`, 'badge-eu']);
    if (o.es_crypto) badges.push(['Crypto', 'badge-crypto']);
    badges.push(o.sin_nomina ? ['Sin nómina', 'badge-ok'] : [`Nómina ≥ ${fmtEURCorto.format(o.nomina_minima_eur || 0)}`, 'badge-nomina']);
    if (o.sin_comisiones) badges.push(['0% Comisiones', 'badge-ok']);

    return el('ul', { class: 'badges', 'aria-label': 'Características' },
      badges.map(([texto, cls]) => {
        const titulo = texto.startsWith('IBAN ') && PAISES[o.pais_iban] ? `IBAN de ${PAISES[o.pais_iban]}` : null;
        return el('li', { class: `badge ${cls}`, title: titulo, text: texto });
      }));
  }

  function crearDesglose(r) {
    const partes = [
      ['Intereses TAE', r.intereses],
      ['Cashback', r.cashback],
      ['Regalo / Bono', r.bono],
    ];
    return el('dl', { class: 'breakdown', 'aria-label': 'Desglose anual' },
      partes.map(([nombre, valor]) => el('div', { class: valor > 0 ? null : 'is-zero' }, [
        el('dt', { text: nombre }),
        el('dd', { text: fmtEUR.format(valor) }),
      ])));
  }

  function crearTarjeta(item, posicion, esNeto) {
    const { oferta: o, resultado: r } = item;
    const esMejor = posicion === 1 && r.total > 0;
    const esDestacada = ofertaDestacada === o.id;
    const idTitulo = `oferta-${o.id}`;

    const clases = ['card', 'offer'];
    if (esMejor) clases.push('is-best');
    if (esDestacada) clases.push('is-highlighted');

    const extraMeta = [];
    if (o.permanencia) extraMeta.push(`Permanencia: ${o.permanencia}`);
    if (o.fgd) extraMeta.push(o.fgd);
    if (o.fecha_fin_promo) extraMeta.push(`Válida hasta ${formatearFecha(o.fecha_fin_promo)}`);

    const reqTexto = o.requisitos_resumen || (o.sin_nomina ? 'Sin nómina ni recibos' : 'Requiere domiciliar nómina');

    const checkComp = el('input', {
      type: 'checkbox',
      'data-compare-id': o.id,
      checked: estado.comparar.has(o.id) ? true : null,
    });

    return el('li', { id: `card-${o.id}`, class: clases.join(' '), 'aria-labelledby': idTitulo }, [
      o.etiqueta_promo ? el('span', { class: 'offer-promo-pill', text: o.etiqueta_promo }) : null,
      el('div', { class: 'offer-top' }, [
        el('div', { class: 'offer-brand' }, [
          el('span', { class: 'entity-avatar', 'data-entity': o.id, 'aria-hidden': 'true', text: iniciales(o) }),
          el('div', {}, [
            el('p', { class: 'offer-entity', text: o.entidad }),
            el('h3', { class: 'offer-name', id: idTitulo, text: o.nombre }),
          ]),
        ]),
        el('span', { class: 'offer-rank', 'aria-label': `Posición ${posicion}`, text: `#${posicion}` }),
      ]),
      el('div', { class: `offer-earnings${r.total > 0 ? '' : ' is-zero'}` }, [
        el('p', { class: 'offer-total' }, [
          `+${fmtEUR.format(r.total)}`,
          el('small', { text: esNeto ? 'neto aprox./año' : '/año' }),
        ]),
        crearDesglose(r),
      ]),
      crearBadges(o, esMejor),
      el('p', { class: 'offer-req' }, [
        el('strong', { text: 'Qué pide: ' }),
        reqTexto,
      ]),
      o.codigo_promo ? el('button', {
        type: 'button',
        class: 'code-chip',
        'data-copy-code': o.codigo_promo,
        title: 'Pulsa para copiar el código promocional',
        text: `🔑 Código: ${o.codigo_promo} (copiar)`,
      }) : null,
      el('details', { class: 'offer-details' }, [
        el('summary', { text: 'Ver condiciones y letra pequeña' }),
        el('p', { text: o.resumen_condiciones }),
        extraMeta.length ? el('p', { class: 'offer-meta-extra', text: extraMeta.join(' · ') }) : null,
      ]),
      el('div', { class: 'offer-foot' }, [
        el('div', { class: 'offer-actions' }, [
          el('label', { class: 'compare-check' }, [checkComp, 'Comparar']),
          el('span', { class: 'muted small', text: `Act. ${formatearFecha(o.fecha_actualizacion)}` }),
        ]),
        el('div', { class: 'offer-cta-row' }, [
          el('button', {
            type: 'button',
            class: 'btn btn-subtle btn-sm',
            'data-copy-offer': o.id,
            title: 'Copiar resumen listo para pegar en foros',
            text: '📋 Copiar',
          }),
          el('a', {
            class: 'btn btn-primary btn-sm',
            href: urlConUtm(o),
            target: '_blank',
            rel: 'nofollow sponsored noopener',
            text: `Ir a ${o.entidad} →`,
          }),
        ]),
      ]),
    ]);
  }

  function ordenarItems(items) {
    const modo = estado.orden;
    return items.sort((a, b) => {
      if (modo === 'bono') {
        return (b.resultado.bono - a.resultado.bono) || (b.resultado.total - a.resultado.total);
      }
      if (modo === 'tae') {
        return (num(b.oferta.tae) - num(a.oferta.tae)) || (b.resultado.total - a.resultado.total);
      }
      if (modo === 'cashback') {
        return (num(b.oferta.porcentaje_cashback) - num(a.oferta.porcentaje_cashback)) || (b.resultado.total - a.resultado.total);
      }
      return b.resultado.total - a.resultado.total;
    });
  }

  function render() {
    const { gasto, saldo, permiteNomina, esNeto } = leerValores();
    actualizarPresets();

    const filtros = Array.from(estado.filtros).map((f) => FILTROS[f]).filter(Boolean);
    const q = estado.busqueda.trim().toLowerCase();

    const visibles = ordenarItems(
      estado.ofertas
        .filter((o) => o.activa === true)
        .filter((o) => permiteNomina || o.sin_nomina === true)
        .filter((o) => filtros.every((fn) => fn(o)))
        .filter((o) => !q || `${o.entidad} ${o.nombre} ${o.resumen_condiciones} ${o.etiqueta_promo || ''}`.toLowerCase().includes(q))
        .map((oferta) => ({ oferta, resultado: calcular(oferta, gasto, saldo, esNeto) })),
    );

    const fragment = document.createDocumentFragment();
    visibles.forEach((item, i) => fragment.append(crearTarjeta(item, i + 1, esNeto)));

    if (!visibles.length) {
      fragment.append(el('li', { class: 'card empty-state' }, [
        'No hay ofertas que coincidan con tu búsqueda o filtros actuales. ',
        el('button', { type: 'button', class: 'btn btn-subtle', 'data-reset': true, text: 'Ver todas las ofertas' }),
      ]));
    }

    ui.lista.replaceChildren(fragment);
    renderCombo(visibles, esNeto);

    ui.avisoFiscal.hidden = !visibles.some(({ oferta }) => esIbanExtranjero(oferta) || oferta.es_crypto);

    const n = visibles.length;
    ui.resumen.textContent = n
      ? `${n} ${n === 1 ? 'oferta' : 'ofertas'} · saldo ${fmtEURCorto.format(saldo)} · gasto ${fmtEURCorto.format(gasto)}/mes${esNeto ? ' · neto aprox.' : ''}`
      : 'Sin resultados con estos filtros';

    if (ui.statMejor) {
      const mejor = visibles.reduce((max, it) => Math.max(max, it.resultado.total), 0);
      ui.statMejor.textContent = visibles.length ? `+${fmtEUR.format(mejor)}/año` : '—';
    }
    if (ui.statOfertas) {
      const activas = estado.ofertas.filter((o) => o.activa === true).length;
      ui.statOfertas.textContent = `${activas} entidades y promos`;
    }
    if (ui.statBonos) {
      const maxBono = estado.ofertas.reduce((m, o) => Math.max(m, num(o.bono_fijo_eur)), 0);
      ui.statBonos.textContent = maxBono > 0 ? `Hasta ${fmtEURCorto.format(maxBono)}` : '—';
    }

    if (ofertaDestacada && !estado.scrollHecho) {
      const target = document.getElementById(`card-${ofertaDestacada}`);
      if (target) {
        estado.scrollHecho = true;
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }

    actualizarBarraComparacion();
  }

  /* ---------- Comparador lado a lado ---------- */
  function actualizarBarraComparacion() {
    if (!ui.compareBar || !ui.compareCount) return;
    const count = estado.comparar.size;
    ui.compareBar.hidden = count === 0;
    ui.compareCount.textContent = `${count} ${count === 1 ? 'seleccionada' : 'seleccionadas'} (máx. 3)`;
    if (ui.btnAbrirComp) ui.btnAbrirComp.disabled = count < 2;
  }

  function abrirModalComparacion() {
    const { gasto, saldo, esNeto } = leerValores();
    const seleccion = Array.from(estado.comparar)
      .map((id) => estado.ofertas.find((o) => o.id === id))
      .filter(Boolean)
      .map((o) => ({ oferta: o, resultado: calcular(o, gasto, saldo, esNeto) }));

    if (seleccion.length < 2) return;

    const filas = [
      ['Ganancia anual estimada', (x) => el('span', { class: 'compare-highlight', text: `+${fmtEUR.format(x.resultado.total)} (${esNeto ? 'neto' : 'bruto'})` })],
      ['Regalo en efectivo', (x) => num(x.oferta.bono_fijo_eur) > 0 ? fmtEURCorto.format(x.oferta.bono_fijo_eur) : '—'],
      ['TAE', (x) => num(x.oferta.tae) > 0 ? `${fmtPct.format(x.oferta.tae)}%${x.oferta.saldo_maximo_remunerado ? ` hasta ${fmtEURCorto.format(x.oferta.saldo_maximo_remunerado)}` : ' sin límite'}` : '—'],
      ['Cashback tarjeta', (x) => num(x.oferta.porcentaje_cashback) > 0 ? `${fmtPct.format(x.oferta.porcentaje_cashback)}%${x.oferta.tope_mensual_eur ? ` (máx. ${fmtEURCorto.format(x.oferta.tope_mensual_eur)}/mes)` : ''}` : '—'],
      ['IBAN', (x) => x.oferta.pais_iban === 'N/A' ? 'Crypto (sin IBAN)' : `IBAN ${x.oferta.pais_iban}`],
      ['Nómina', (x) => x.oferta.sin_nomina ? 'Sin nómina' : `≥ ${fmtEURCorto.format(x.oferta.nomina_minima_eur || 0)}/mes`],
      ['Permanencia', (x) => x.oferta.permanencia || 'Sin permanencia'],
      ['Protección FGD', (x) => x.oferta.fgd || '—'],
      ['Qué pide', (x) => x.oferta.requisitos_resumen || x.oferta.resumen_condiciones],
    ];

    const thead = el('thead', {}, el('tr', {}, [
      el('th', { text: 'Característica' }),
      ...seleccion.map((x) => el('th', { text: `${x.oferta.entidad} · ${x.oferta.nombre}` })),
    ]));

    const tbody = el('tbody', {}, filas.map(([label, fn]) => el('tr', {}, [
      el('th', { text: label }),
      ...seleccion.map((x) => el('td', {}, fn(x))),
    ])));

    ui.tablaComparar.replaceChildren(el('table', { class: 'compare-table' }, [thead, tbody]));
    ui.modalComparar.showModal();
  }

  /* ---------- Render novedades ---------- */
  function renderNovedades() {
    if (!ui.novedadesSec || !ui.listaNovedades) return;
    if (!estado.novedades.length) {
      ui.novedadesSec.hidden = true;
      return;
    }

    const fragment = document.createDocumentFragment();
    estado.novedades.forEach((n) => {
      fragment.append(el('li', { class: 'card news-card' }, [
        el('div', { class: 'news-meta' }, [
          el('div', { class: 'news-badges' }, [
            n.es_promo_destacada ? el('span', { class: 'news-promo', text: '🔥 Promo' }) : null,
            el('span', { class: 'news-source', text: n.fuente || 'Radar' }),
          ]),
          n.fecha ? el('time', { datetime: n.fecha, text: formatearFecha(n.fecha) }) : null,
        ]),
        el('h3', { class: 'news-title', text: n.titulo }),
        n.resumen ? el('p', { class: 'news-excerpt', text: n.resumen }) : null,
        n.url ? el('a', {
          class: 'news-link',
          href: n.url,
          target: '_blank',
          rel: 'noopener noreferrer',
          text: 'Ver noticia original ↗',
        }) : null,
      ]));
    });

    ui.listaNovedades.replaceChildren(fragment);
    ui.novedadesSec.hidden = false;
  }

  /* ---------- Interacción ---------- */
  function sincronizar(range, input, limites) {
    actualizarProgreso(range, limites);

    range.addEventListener('input', () => {
      input.value = range.value;
      actualizarProgreso(range, limites);
      render();
    });
    input.addEventListener('input', () => {
      if (input.value === '') return;
      range.value = String(clamp(input.value, limites));
      actualizarProgreso(range, limites);
      render();
    });
    input.addEventListener('change', () => {
      const v = clamp(input.value, limites);
      input.value = String(v);
      range.value = String(v);
      actualizarProgreso(range, limites);
      render();
    });
  }

  function actualizarChips() {
    ui.chips.forEach((chip) => {
      const f = chip.dataset.filter;
      const activo = f === 'todos' ? estado.filtros.size === 0 : estado.filtros.has(f);
      chip.setAttribute('aria-pressed', String(activo));
    });
  }

  function alternarFiltro(f) {
    if (f === 'todos') {
      estado.filtros.clear();
      if (ui.buscar) {
        ui.buscar.value = '';
        estado.busqueda = '';
      }
      if (ui.toggleNomina) ui.toggleNomina.checked = true;
    } else if (estado.filtros.has(f)) {
      estado.filtros.delete(f);
    } else {
      estado.filtros.add(f);
    }
    actualizarChips();
    render();
  }

  function initEventos() {
    sincronizar(ui.gastoRange, ui.gastoNum, LIMITES.gasto);
    sincronizar(ui.saldoRange, ui.saldoNum, LIMITES.saldo);

    ui.presets.forEach((btn) => {
      btn.addEventListener('click', () => {
        const val = btn.dataset.val;
        if (btn.dataset.target === 'saldo') {
          ui.saldoNum.value = val;
          ui.saldoRange.value = val;
          actualizarProgreso(ui.saldoRange, LIMITES.saldo);
        } else {
          ui.gastoNum.value = val;
          ui.gastoRange.value = val;
          actualizarProgreso(ui.gastoRange, LIMITES.gasto);
        }
        render();
      });
    });

    if (ui.toggleNomina) ui.toggleNomina.addEventListener('change', render);
    if (ui.toggleNeto) ui.toggleNeto.addEventListener('change', render);

    if (ui.buscar) {
      ui.buscar.addEventListener('input', () => {
        estado.busqueda = ui.buscar.value;
        render();
      });
    }

    if (ui.ordenar) {
      ui.ordenar.addEventListener('change', () => {
        estado.orden = ui.ordenar.value;
        render();
      });
    }

    ui.chips.forEach((chip) => chip.addEventListener('click', () => alternarFiltro(chip.dataset.filter)));

    ui.lista.addEventListener('click', (e) => {
      const target = e.target instanceof Element ? e.target : null;
      if (!target) return;

      if (target.closest('[data-reset]')) {
        alternarFiltro('todos');
        return;
      }

      const copyCodeBtn = target.closest('[data-copy-code]');
      if (copyCodeBtn) {
        const code = copyCodeBtn.getAttribute('data-copy-code');
        copiarTexto(code, `Código ${code} copiado`);
        return;
      }

      const copyOfferBtn = target.closest('[data-copy-offer]');
      if (copyOfferBtn) {
        const id = copyOfferBtn.getAttribute('data-copy-offer');
        const oferta = estado.ofertas.find((o) => o.id === id);
        if (oferta) {
          const { gasto, saldo, esNeto } = leerValores();
          const res = calcular(oferta, gasto, saldo, esNeto);
          copiarTexto(textoParaForo(oferta, res, esNeto), `Resumen de ${oferta.entidad} copiado para foro`);
        }
      }
    });

    ui.lista.addEventListener('change', (e) => {
      const input = e.target instanceof HTMLInputElement ? e.target : null;
      if (!input || !input.hasAttribute('data-compare-id')) return;
      const id = input.getAttribute('data-compare-id');
      if (input.checked) {
        if (estado.comparar.size >= 3) {
          input.checked = false;
          mostrarToast('Puedes comparar hasta 3 ofertas a la vez');
          return;
        }
        estado.comparar.add(id);
      } else {
        estado.comparar.delete(id);
      }
      actualizarBarraComparacion();
    });

    if (ui.btnLimpiarComp) {
      ui.btnLimpiarComp.addEventListener('click', () => {
        estado.comparar.clear();
        render();
      });
    }

    if (ui.btnAbrirComp) ui.btnAbrirComp.addEventListener('click', abrirModalComparacion);
    if (ui.btnCerrarComp) ui.btnCerrarComp.addEventListener('click', () => ui.modalComparar.close());
    if (ui.modalComparar) {
      ui.modalComparar.addEventListener('click', (e) => {
        if (e.target === ui.modalComparar) ui.modalComparar.close();
      });
    }
  }

  /* ---------- Arranque ---------- */
  async function cargarJson(url) {
    const res = await fetch(url, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const datos = await res.json();
    if (!Array.isArray(datos)) throw new Error('Formato no válido');
    return datos;
  }

  async function init() {
    initTema();
    initEventos();

    const [resOfertas, resNovedades] = await Promise.allSettled([
      cargarJson(DATA_URL),
      cargarJson(NOVEDADES_URL),
    ]);

    if (resOfertas.status === 'fulfilled') {
      estado.ofertas = resOfertas.value;
      render();
    } else {
      console.warn('No se pudieron cargar las ofertas:', resOfertas.reason);
      ui.resumen.textContent = 'No se pudieron cargar las ofertas.';
      ui.lista.replaceChildren(el('li', { class: 'card empty-state' }, [
        'No se ha podido cargar data/ofertas.json. Sirve la carpeta /web con un servidor local (por ejemplo: python3 -m http.server).',
      ]));
    }

    if (resNovedades.status === 'fulfilled') {
      estado.novedades = resNovedades.value;
      renderNovedades();
    }
  }

  init();
})();
