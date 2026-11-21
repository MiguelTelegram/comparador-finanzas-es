/* =========================================================
   Comparador Finanzas ES — lógica de la calculadora
   Vanilla JS, sin dependencias.
   ========================================================= */
'use strict';

(() => {
  const DATA_URL = 'data/ofertas.json';

  const LIMITES = {
    gasto: { min: 0, max: 3000 },
    saldo: { min: 0, max: 50000 },
  };

  const PAISES = {
    ES: 'España', DE: 'Alemania', NL: 'Países Bajos', FR: 'Francia', IE: 'Irlanda',
    LT: 'Lituania', BE: 'Bélgica', IT: 'Italia', PT: 'Portugal', LU: 'Luxemburgo',
    AT: 'Austria', MT: 'Malta', FI: 'Finlandia', EE: 'Estonia', LV: 'Letonia',
  };

  // Filtros combinables (lógica AND). "Todos" limpia la selección.
  const FILTROS = {
    ibanES: (o) => o.pais_iban === 'ES',
    ibanUE: (o) => esIbanExtranjero(o),
    crypto: (o) => o.es_crypto === true,
    cashback: (o) => num(o.porcentaje_cashback) > 0,
    remunerada: (o) => num(o.tae) > 0,
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
    chips: Array.from(document.querySelectorAll('.chip')),
    lista: $('#resultados'),
    resumen: $('#resumen'),
    avisoFiscal: $('#aviso-fiscal'),
  };

  const estado = {
    ofertas: [],
    filtros: new Set(),
  };

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

  /* ---------- Cálculo ---------- */
  function calcular(oferta, gastoMensual, saldo) {
    const intereses = Math.min(saldo, oferta.saldo_maximo_remunerado ?? Infinity) * (num(oferta.tae) / 100);
    const cashback = Math.min(
      gastoMensual * (num(oferta.porcentaje_cashback) / 100),
      oferta.tope_mensual_eur ?? Infinity,
    ) * 12;
    const bono = num(oferta.bono_fijo_eur);
    return { intereses, cashback, bono, total: intereses + cashback + bono };
  }

  function leerValores() {
    return {
      gasto: clamp(ui.gastoNum.value, LIMITES.gasto),
      saldo: clamp(ui.saldoNum.value, LIMITES.saldo),
    };
  }

  /* ---------- Render ---------- */
  function crearBadges(o, esMejor) {
    const badges = [];
    if (esMejor) badges.push(['Mejor opción', 'badge-best']);
    if (o.pais_iban === 'ES') badges.push(['IBAN ES', 'badge-es']);
    else if (esIbanExtranjero(o)) badges.push([`IBAN ${o.pais_iban}`, 'badge-eu']);
    if (o.es_crypto) badges.push(['Crypto', 'badge-crypto']);
    if (o.sin_comisiones) badges.push(['0% Comisiones', 'badge-ok']);
    if (o.sin_nomina) badges.push(['Sin nómina', 'badge-ok']);

    return el('ul', { class: 'badges', 'aria-label': 'Características' },
      badges.map(([texto, cls]) => {
        const titulo = texto.startsWith('IBAN ') && PAISES[o.pais_iban]
          ? `IBAN de ${PAISES[o.pais_iban]}` : null;
        return el('li', { class: `badge ${cls}`, title: titulo, text: texto });
      }));
  }

  function crearTasas(o) {
    const items = [];
    if (num(o.tae) > 0) {
      const tope = o.saldo_maximo_remunerado != null ? ` hasta ${fmtEURCorto.format(o.saldo_maximo_remunerado)}` : ' sin tope';
      items.push(el('span', {}, [el('strong', { text: `${fmtPct.format(o.tae)}% TAE` }), tope]));
    }
    if (num(o.porcentaje_cashback) > 0) {
      const tope = o.tope_mensual_eur != null ? ` (máx. ${fmtEURCorto.format(o.tope_mensual_eur)}/mes)` : ' sin tope';
      items.push(el('span', {}, [el('strong', { text: `${fmtPct.format(o.porcentaje_cashback)}% cashback` }), tope]));
    }
    return items.length ? el('p', { class: 'offer-rates' }, items) : null;
  }

  function crearDesglose(r) {
    const partes = [
      ['TAE', r.intereses],
      ['Cashback', r.cashback],
      ['Bono', r.bono],
    ];
    return el('dl', { class: 'breakdown', 'aria-label': 'Desglose anual' },
      partes.map(([nombre, valor]) => el('div', { class: valor > 0 ? null : 'is-zero' }, [
        el('dt', { text: nombre }),
        el('dd', { text: fmtEUR.format(valor) }),
      ])));
  }

  function crearTarjeta(item, posicion) {
    const { oferta: o, resultado: r } = item;
    const esMejor = posicion === 1 && r.total > 0;
    const idTitulo = `oferta-${o.id}`;

    return el('li', { class: `card offer${esMejor ? ' is-best' : ''}`, 'aria-labelledby': idTitulo }, [
      el('div', { class: 'offer-top' }, [
        el('div', {}, [
          el('p', { class: 'offer-entity', text: o.entidad }),
          el('h3', { class: 'offer-name', id: idTitulo, text: o.nombre }),
        ]),
        el('span', { class: 'offer-rank', 'aria-label': `Posición ${posicion}`, text: posicion }),
      ]),
      el('p', { class: `offer-total${r.total > 0 ? '' : ' is-zero'}` }, [
        `+${fmtEUR.format(r.total)}`,
        el('small', { text: '/año' }),
      ]),
      crearDesglose(r),
      crearBadges(o, esMejor),
      crearTasas(o),
      el('p', { class: 'offer-summary', text: o.resumen_condiciones }),
      el('div', { class: 'offer-foot' }, [
        el('p', { class: 'offer-date' }, [
          'Actualizado: ',
          el('time', { datetime: o.fecha_actualizacion, text: formatearFecha(o.fecha_actualizacion) }),
        ]),
        el('a', {
          class: 'btn btn-primary',
          href: urlConUtm(o),
          target: '_blank',
          rel: 'nofollow sponsored noopener',
          text: `Ver oferta de ${o.entidad}`,
        }),
      ]),
    ]);
  }

  function render() {
    const { gasto, saldo } = leerValores();
    const filtros = Array.from(estado.filtros).map((f) => FILTROS[f]).filter(Boolean);

    const visibles = estado.ofertas
      .filter((o) => o.activa === true)
      .filter((o) => filtros.every((fn) => fn(o)))
      .map((oferta) => ({ oferta, resultado: calcular(oferta, gasto, saldo) }))
      .sort((a, b) => b.resultado.total - a.resultado.total);

    const fragment = document.createDocumentFragment();
    visibles.forEach((item, i) => fragment.append(crearTarjeta(item, i + 1)));

    if (!visibles.length) {
      fragment.append(el('li', { class: 'card empty-state' }, [
        'No hay ofertas que cumplan todos los filtros seleccionados. ',
        el('button', { type: 'button', class: 'btn btn-subtle', 'data-reset': true, text: 'Ver todas' }),
      ]));
    }

    ui.lista.replaceChildren(fragment);

    // Aviso fiscal dinámico
    ui.avisoFiscal.hidden = !visibles.some(({ oferta }) => esIbanExtranjero(oferta) || oferta.es_crypto);

    const n = visibles.length;
    ui.resumen.textContent = n
      ? `${n} ${n === 1 ? 'oferta' : 'ofertas'} · gasto ${fmtEURCorto.format(gasto)}/mes · saldo ${fmtEURCorto.format(saldo)}`
      : 'Sin resultados con estos filtros';
  }

  /* ---------- Interacción ---------- */
  function sincronizar(range, input, limites) {
    range.addEventListener('input', () => {
      input.value = range.value;
      render();
    });
    input.addEventListener('input', () => {
      if (input.value === '') return;
      range.value = String(clamp(input.value, limites));
      render();
    });
    input.addEventListener('change', () => {
      const v = clamp(input.value, limites);
      input.value = String(v);
      range.value = String(v);
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
    if (f === 'todos') estado.filtros.clear();
    else if (estado.filtros.has(f)) estado.filtros.delete(f);
    else estado.filtros.add(f);
    actualizarChips();
    render();
  }

  function initEventos() {
    sincronizar(ui.gastoRange, ui.gastoNum, LIMITES.gasto);
    sincronizar(ui.saldoRange, ui.saldoNum, LIMITES.saldo);

    ui.chips.forEach((chip) => chip.addEventListener('click', () => alternarFiltro(chip.dataset.filter)));

    ui.lista.addEventListener('click', (e) => {
      if (e.target instanceof Element && e.target.closest('[data-reset]')) alternarFiltro('todos');
    });
  }

  /* ---------- Arranque ---------- */
  async function cargarOfertas() {
    const res = await fetch(DATA_URL, { cache: 'no-cache' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const datos = await res.json();
    if (!Array.isArray(datos)) throw new Error('Formato de ofertas no válido');
    return datos;
  }

  async function init() {
    initEventos();
    try {
      estado.ofertas = await cargarOfertas();
      render();
    } catch (err) {
      console.warn('No se pudieron cargar las ofertas:', err);
      ui.resumen.textContent = 'No se pudieron cargar las ofertas.';
      ui.lista.replaceChildren(el('li', { class: 'card empty-state' }, [
        'No se ha podido cargar data/ofertas.json. Si has abierto el archivo directamente desde el disco, ',
        'sirve la carpeta /web con un servidor local (por ejemplo: python3 -m http.server).',
      ]));
    }
  }

  init();
})();
