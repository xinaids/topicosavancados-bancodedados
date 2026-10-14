'use strict';
/* Le Tour · Estatísticas — front-end (JS puro, sem dependências) */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nf = n => (n == null ? '–' : Number(n).toLocaleString('pt-BR'));
const nf1 = n => (n == null ? '–' : Number(n).toLocaleString('pt-BR', { maximumFractionDigits: 1 }));
const fdata = iso => (iso ? new Date(iso + 'T12:00:00').toLocaleDateString('pt-BR', { day: 'numeric', month: 'short', year: 'numeric' }) : '–');
const fhoras = h => (h == null ? '–' : `${Math.floor(h)}h${String(Math.round((h % 1) * 60)).padStart(2, '0')}`);
const view = $('#view');

const TIPOS = {
  'Plain stage': 'Plano', 'Flat stage': 'Plano', 'Hilly stage': 'Acidentada', 'Stage with mountain(s)': 'Com montanhas',
  'Stage with mountain': 'Com montanhas', 'High mountain stage': 'Alta montanha', 'Mountain stage': 'Montanha',
  'Medium mountain stage': 'Média montanha', 'Individual time trial': 'Contrarrelógio', 'Team time trial': 'Contrarrelógio por equipes',
  'Mountain time trial': 'Contrarrelógio de montanha', 'Intermediate stage': 'Intermediária',
  'Flat cobblestone stage': 'Plano com pavê', 'Plain stage with cobblestones': 'Plano com pavê',
};
const tipoPt = t => TIPOS[t] || TIPOS[(t || '').replace('Mountain Stage', 'Mountain stage')] || t || '–';
const CATS = { plano: ['Plano', 'var(--plano)'], colinas: ['Colinas', 'var(--colinas)'], montanha: ['Montanha', 'var(--montanha)'], crl: ['Contrarrelógio', 'var(--crl)'], tte: ['Contrarrelógio por equipes', 'var(--tte)'] };
const CATHEX = { plano: '#1E9E5A', colinas: '#F08A24', montanha: '#D7263D', crl: '#2D6CDF', tte: '#12A4B8' };
const STATUS = { FIN: 'Finalizou', DNF: 'Abandonou', DNS: 'Não largou', OTL: 'Fora do tempo', DSQ: 'Desclassificado', NQ: 'Não classificado' };
const NC = 9999;

const state = { resumo: null, edicoes: null, lastRider: null, cql: [], cqlTotal: 0 };

/* ------------------------------------------------------------------ CQL drawer */
const TOK = /(--[^\n]*)|('(?:[^']|'')*')|\b(SELECT|FROM|WHERE|AND|INSERT\s+INTO|VALUES|UPDATE|SET|DELETE|IF\s+NOT\s+EXISTS|IF\s+EXISTS|LIMIT|ALLOW\s+FILTERING|BEGIN\s+BATCH|APPLY\s+BATCH|CONSISTENCY|AS|ORDER\s+BY)\b|\b(COUNT|AVG|SUM|MIN|MAX|CAST|token)(?=\()|\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b|\b(\d+(?:\.\d+)?)\b/gi;
function hl(src) {
  let out = '', last = 0;
  src.replace(TOK, (m, cm, str, kw, fn, uu, nu, off) => {
    out += esc(src.slice(last, off));
    const cls = cm ? 'cm' : str ? 'st-' : kw ? 'kw' : fn ? 'fn' : 'nu';
    out += `<span class="${cls}">${esc(m)}</span>`;
    last = off + m.length;
    return m;
  });
  return out + esc(src.slice(last));
}
function pushCql(list, label) {
  if (!list || !list.length) return;
  for (const q of list.slice().reverse()) state.cql.unshift({ ...q, label, t: new Date() });
  state.cqlTotal += list.length;
  state.cql.length = Math.min(state.cql.length, 80);
  $('#cqlCount').textContent = state.cqlTotal;
  if (!$('#drawer').hidden) renderDrawer();
}
function renderDrawer() {
  $('#drawerBody').innerHTML = state.cql.length ? state.cql.map(q => `
    <div class="q ${q.demo ? 'demo' : ''}">
      <div class="qh"><b>${esc(q.label)}</b><span>${q.n > 1 ? `× ${q.n} · ` : ''}${q.demo ? 'simulado' : q.ms + ' ms'}</span></div>
      <pre>${hl(q.cql)}</pre></div>`).join('') : '<div class="q"><pre class="cm">-- navegue pelo sistema: cada tela mostra aqui o CQL que executou</pre></div>';
}
$('#cqlBtn').onclick = () => { const d = $('#drawer'); d.hidden = !d.hidden; $('#cqlBtn').setAttribute('aria-expanded', !d.hidden); if (!d.hidden) renderDrawer(); };
$('#drawerClose').onclick = () => { $('#drawer').hidden = true; $('#cqlBtn').setAttribute('aria-expanded', 'false'); };

/* ------------------------------------------------------------------ utilidades */
async function api(path, opts = {}, label) {
  const r = await fetch('/api' + path, { headers: { 'Content-Type': 'application/json' }, ...opts });
  let j = null;
  try { j = await r.json(); } catch { /* corpo vazio */ }
  if (!r.ok) throw new Error((j && j.erro) || `Erro ${r.status}`);
  pushCql(j.cql, label || `${(opts.method || 'GET')} ${path.split('?')[0]}`);
  return j.data;
}
const toast = msg => { const t = $('#toast'); t.textContent = msg; t.classList.add('show'); clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('show'), 2600); };
const loading = (txt = 'Consultando o Cassandra…') => `<div class="loading"><span class="spinner"></span> ${txt}</div>`;
const errBox = e => `<div class="wrap"><div class="note warn" style="margin-top:40px"><b>Algo deu errado.</b> ${esc(e.message || e)}</div></div>`;
const jersey = (c = '#FFD60A') => `<svg class="jersey" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3 3 6l2 4 2-1v12h10V9l2 1 2-4-5-3c-1 2-7 2-8 0Z" fill="${c}" stroke="#11151C" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
const medalCls = p => (p === 1 ? 'm1' : p === 2 ? 'm2' : p === 3 ? 'm3' : '');
const posBadge = r => (r.posicao === NC ? '<span class="pos">–</span>' : `<span class="pos ${medalCls(r.posicao)}">${r.posicao}</span>`);
const stBadge = s => `<span class="st ${esc(s)}" title="${esc(STATUS[s] || s)}">${esc(s)}</span>`;
const debounce = (fn, ms = 200) => { let h; return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), ms); }; };
const nomeCurto = n => (n || '').trim();
const numeroLabel = n => (n === 'P' ? 'Prólogo' : `Etapa ${n}`);

function countUp(el, alvo, ms = 900) {
  if (alvo == null) { el.textContent = '–'; return; }
  const t0 = performance.now();
  const step = t => { const k = Math.min(1, (t - t0) / ms); el.textContent = nf(Math.round(alvo * (1 - Math.pow(1 - k, 3)))); if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}

/* tooltip global (barras do perfil e gráficos) */
const tip = document.createElement('div'); tip.className = 'tip'; document.body.appendChild(tip);
document.addEventListener('mousemove', e => {
  const t = e.target.closest('[data-tt]');
  if (!t) { tip.style.opacity = 0; return; }
  tip.innerHTML = t.dataset.tt;
  tip.style.opacity = 1;
  const w = tip.offsetWidth;
  tip.style.left = Math.min(window.innerWidth - w - 10, e.clientX + 14) + 'px';
  tip.style.top = (e.clientY + 18) + 'px';
});

/* ------------------------------------------------------------------ caches */
async function getResumo() { return state.resumo || (state.resumo = await api('/resumo')); }
async function getEdicoes() { return state.edicoes || (state.edicoes = await api('/edicoes')); }
function invalidar() { state.resumo = null; }

/* ------------------------------------------------------------------ busca de ciclistas (reutilizada) */
function bindSearch(input, box, { onEnter } = {}) {
  const run = debounce(async () => {
    const q = input.value.trim();
    if (q.length < 2) { box.innerHTML = ''; return; }
    try {
      const rows = await api('/ciclistas?q=' + encodeURIComponent(q), {}, 'busca de ciclista');
      box.innerHTML = rows.length ? rows.map(r => `<a href="#/ciclista/${r.id}"><span>${esc(r.nome)}</span><small>${esc(r.pais || '')}</small></a>`).join('')
        : '<a><span>Nenhum ciclista encontrado</span></a>';
    } catch (e) { box.innerHTML = `<a><span>${esc(e.message)}</span></a>`; }
  });
  input.addEventListener('input', run);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') { const a = $('a[href]', box); if (a) location.hash = a.getAttribute('href'); } if (e.key === 'Escape') box.innerHTML = ''; });
  document.addEventListener('click', e => { if (!box.contains(e.target) && e.target !== input) box.innerHTML = ''; });
}
const lupa = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#11151C" stroke-width="2.6" stroke-linecap="round"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m20 20-4.8-4.8"/></svg>';

/* ------------------------------------------------------------------ HOME */
async function home() {
  const [res, eds] = await Promise.all([getResumo(), getEdicoes()]);
  const decadas = [...new Set(eds.map(e => Math.floor(e.ano / 10) * 10))];
  const padrao = decadas.includes(2010) ? 2010 : decadas[decadas.length - 1];
  view.innerHTML = `
    <section class="hero"><div class="wrap">
      <div class="kicker">${res.ano_min} – ${res.ano_max}</div>
      <h1>A história do Tour em dados</h1>
      <p class="lead">Navegue pelas edições, veja o perfil de cada etapa, o pódio e o histórico de cada ciclista. Tudo vem de um banco Cassandra.</p>
      <div class="searchbox">${lupa}<input id="q" type="search" autocomplete="off" placeholder="Buscar ciclista: Merckx, Froome, Indurain…" aria-label="Buscar ciclista"><div class="sugg" id="sugg"></div></div>
    </div></section>
    <div class="wrap">
      <div class="counters">
        <div class="counter"><b data-n="${res.edicoes}">0</b><span>edições</span></div>
        <div class="counter"><b data-n="${res.etapas}">0</b><span>etapas</span></div>
        <div class="counter"><b data-n="${res.ciclistas}">0</b><span>ciclistas</span></div>
        <div class="counter"><b data-n="${res.resultados ?? ''}">0</b><span>resultados</span></div>
      </div>
      <section class="sec">
        <div class="sec-h"><div><h2>Escolha uma edição</h2><p>${res.edicoes_com_resultados} das ${res.edicoes} edições têm etapas e resultados completos. As demais mostram só o vencedor.</p></div>
          <div class="tabs" id="dec">${decadas.map(d => `<button class="tab ${d === padrao ? 'on' : ''}" data-d="${d}">${d}s</button>`).join('')}</div></div>
        <div class="cards" id="cards"></div>
      </section>
    </div>`;
  $$('.counter b').forEach(b => countUp(b, b.dataset.n === '' ? null : +b.dataset.n));
  bindSearch($('#q'), $('#sugg'));
  const pinta = d => {
    $('#cards').innerHTML = eds.filter(e => Math.floor(e.ano / 10) * 10 === d).map((e, i) => `
      <a class="ed" href="#/edicao/${e.ano}" style="animation-delay:${i * 28}ms">
        <span class="tag ${e.com_resultados ? '' : 'no'}">${e.com_resultados ? 'completa' : 'só vencedor'}</span>
        <span class="y">${e.ano}</span><span class="n">${e.edicao}ª edição</span>
        <span class="w">${jersey()}${esc(e.vencedor)}</span><span class="t">${esc(e.equipe_vencedora || '')}</span>
        <span class="km">${nf(e.distancia_km)} km${e.tempo_total_h ? ' · ' + fhoras(e.tempo_total_h) : ''}</span></a>`).join('');
  };
  pinta(padrao);
  $$('#dec .tab').forEach(b => b.onclick = () => { $$('#dec .tab').forEach(x => x.classList.toggle('on', x === b)); pinta(+b.dataset.d); });
}

/* ------------------------------------------------------------------ gráficos SVG */
function serie(rows, key, { tipo = 'linha', fmt = nf1, cor = '#11151C' } = {}) {
  const W = 560, H = 220, L = 42, R = 12, T = 14, B = 30;
  const vals = rows.map(r => r[key]).filter(v => v != null);
  if (!vals.length) return '<div class="empty">Sem dados para este gráfico</div>';
  let min = tipo === 'barra' ? 0 : Math.min(...vals), max = Math.max(...vals);
  if (tipo !== 'barra') { const m = (max - min) || 1; min = Math.max(0, Math.floor(min - m * .2)); max = Math.ceil(max + m * .2); }
  if (max === min) max = min + 1;
  const n = rows.length, iw = W - L - R, ih = H - T - B;
  const bw = iw / n;
  const x = i => (tipo === 'barra' ? L + bw * (i + .5) : L + (n === 1 ? iw / 2 : i * iw / (n - 1)));
  const y = v => T + ih * (1 - (v - min) / (max - min));
  let g = '';
  for (let k = 0; k <= 4; k++) { const v = min + (max - min) * k / 4; g += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="#E7E0C6" stroke-dasharray="3 4"/><text x="${L - 7}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="#6B7280">${fmt(v)}</text>`; }
  const step = Math.ceil(n / 14);
  rows.forEach((r, i) => { if (i % step === 0) g += `<text x="${x(i)}" y="${H - 9}" text-anchor="middle" font-size="12" font-weight="700" fill="#2A303B" font-family="Barlow Condensed,sans-serif">${esc(r.numero)}</text>`; });
  let marks = '';
  const pts = rows.map((r, i) => (r[key] == null ? null : [x(i), y(r[key]), r])).filter(Boolean);
  const tt = r => `data-tt="<b>${esc(numeroLabel(r.numero))}</b><br>${esc(tipoPt(r.tipo))} · ${nf1(r.distancia_km)} km<br>${esc(String(fmt(r[key])))}"`;
  if (tipo === 'barra') {
    rows.forEach((r, i) => { if (r[key] == null) return; marks += `<rect x="${x(i) - bw * .36}" y="${y(r[key])}" width="${bw * .72}" height="${Math.max(1, y(min) - y(r[key]))}" rx="3" fill="${CATHEX[r.categoria] || cor}" ${tt(r)}/>`; });
  } else {
    const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
    if (tipo === 'area') marks += `<path d="${d} L${pts[pts.length - 1][0]} ${y(min)} L${pts[0][0]} ${y(min)}Z" fill="#FFD60A" opacity=".55"/>`;
    marks += `<path d="${d}" fill="none" stroke="#11151C" stroke-width="2.5" stroke-linejoin="round"/>`;
    marks += pts.map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="5" fill="${CATHEX[p[2].categoria] || '#11151C'}" stroke="#11151C" stroke-width="1.5" ${tt(p[2])}/>`).join('');
  }
  return `<svg viewBox="0 0 ${W} ${H}" role="img">${g}${marks}</svg>`;
}
const hbars = (rows, lab, val, max = 10) => {
  const r = rows.slice(0, max), m = Math.max(...r.map(x => x[val]), 1);
  return r.length ? r.map(x => `<div class="hbar"><span class="lab" title="${esc(x[lab])}">${esc(x[lab])}</span><div class="tr"><div class="fl" style="width:${x[val] / m * 100}%"></div></div><b>${x[val]}</b></div>`).join('') : '<div class="empty">Sem dados</div>';
};

/* ------------------------------------------------------------------ EDIÇÃO */
async function edicao(anoStr, ordemStr) {
  const ano = +anoStr;
  const [{ edicao: e, etapas }, eds] = await Promise.all([api(`/edicoes/${ano}`, {}, `edição ${ano}`), getEdicoes()]);
  const anos = eds.map(x => x.ano), i = anos.indexOf(ano);
  const ant = anos[i - 1], prox = anos[i + 1];
  const temEtapas = etapas.length > 0;
  view.innerHTML = `
    <section class="banner"><div class="wrap">
      <div class="crumbs"><a href="#/">‹ Todas as edições</a><span>${e.edicao}ª edição</span></div>
      <div class="banner-main">
        <div><div class="year">${e.ano}</div>
          <div class="winner">${jersey()}<div><b>${esc(e.vencedor)}</b><span>${esc(e.equipe_vencedora || 'equipe não informada')}</span></div></div></div>
        <div class="nav-year"><a href="#/edicao/${ant}" aria-label="Edição anterior" aria-disabled="${!ant}">‹</a><a href="#/edicao/${prox}" aria-label="Próxima edição" aria-disabled="${!prox}">›</a></div>
      </div>
      <div class="facts">
        <div class="fact"><b>${nf(e.distancia_km)} km</b><span>distância total</span></div>
        <div class="fact"><b>${fhoras(e.tempo_total_h)}</b><span>tempo do campeão</span></div>
        <div class="fact"><b>${e.vitorias_etapa}</b><span>etapas vencidas por ele</span></div>
        <div class="fact"><b>${e.etapas_lideradas}</b><span>etapas na liderança</span></div>
        <div class="fact"><b>${temEtapas ? etapas.length : '–'}</b><span>etapas na base</span></div>
      </div>
    </div></section>
    <div class="wrap" style="padding-bottom:30px">
      ${temEtapas ? `<div class="tabs" style="margin-top:24px"><button class="tab on" data-t="e">Etapas e ranking</button><button class="tab" data-t="n">Números da edição</button></div><div id="painel"></div>`
        : `<div class="note" style="margin-top:28px"><b>Esta edição está só com o vencedor.</b> Os arquivos de etapas e resultados não puderam ser ligados com segurança para ${e.ano}, então a tabela <span class="mono">etapas</span> não tem linhas para ela. Isso é normal em Cassandra: cada partição guarda só o que existe, sem linhas vazias.</div>`}
    </div>`;
  if (!temEtapas) return;
  const painel = $('#painel');
  $$('.tab[data-t]').forEach(b => b.onclick = () => { $$('.tab[data-t]').forEach(x => x.classList.toggle('on', x === b)); (b.dataset.t === 'e' ? painelEtapas : painelNumeros)(); });

  function painelEtapas() {
    const max = Math.max(...etapas.map(x => +x.distancia_km || 0), 1);
    const cats = [...new Set(etapas.map(x => x.categoria))];
    painel.innerHTML = `
      <div class="card profile">
        <div class="profile-top"><h3>Perfil da edição</h3>
          <div class="legend">${cats.map(c => `<span><i class="i-${c}"></i>${CATS[c][0]}</span>`).join('')}</div></div>
        <div class="bars" id="bars">${etapas.map(x => `
          <button class="bar" data-o="${x.ordem}" aria-label="${esc(numeroLabel(x.numero))}"
            data-tt="<b>${esc(numeroLabel(x.numero))}</b><br>${esc(tipoPt(x.tipo))} · ${nf1(x.distancia_km)} km<br>${esc(x.origem || '')} → ${esc(x.destino || '')}<br>🏆 ${esc(x.vencedor || '–')}">
            <div class="col ${x.categoria}" style="height:calc((100% - 24px) * ${Math.max(.05, (+x.distancia_km || 0) / max)})"></div>
            <div class="lb">${esc(x.numero)}</div></button>`).join('')}</div>
        <p style="color:var(--mute);font-size:13px;margin:8px 0 0">A altura é a distância da etapa. Clique em uma barra para ver o ranking.</p>
      </div>
      <div id="etapa"></div>`;
    $$('#bars .bar').forEach(b => b.onclick = () => escolhe(+b.dataset.o));
    escolhe(ordemStr ? +ordemStr : etapas[0].ordem, false);
  }

  async function escolhe(ordem, rolar = true) {
    $$('#bars .bar').forEach(b => b.classList.toggle('on', +b.dataset.o === ordem));
    history.replaceState(null, '', `#/edicao/${ano}/${ordem}`);
    const box = $('#etapa');
    box.innerHTML = loading();
    try {
      const d = await api(`/etapas/${ano}/${ordem}`, {}, `ranking ${ano}/${ordem}`);
      box.innerHTML = etapaHtml(d);
      ligaTabela(d);
      if (rolar) box.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) { box.innerHTML = `<div class="note warn" style="margin-top:20px">${esc(err.message)}</div>`; }
  }

  function etapaHtml(d) {
    const et = d.etapa, rs = d.resultados, r = d.resumo;
    const cat = CATS[et.categoria] || ['', '#999'];
    const top = rs.filter(x => x.status === 'FIN').slice(0, 3);
    const pod = top.length === 3 && top[0].posicao === 1 ? [1, 0, 2].map(k => top[k]) : [];
    return `
      <div class="stagehead"><div>
        <h3>${esc(numeroLabel(et.numero))} <span style="color:var(--mute);font-weight:600">· ${fdata(et.data_etapa)}</span></h3>
        <div class="route">${esc(et.origem || '–')} → ${esc(et.destino || '–')}</div></div>
        <div class="chips"><span class="chip"><i style="background:${cat[1]}"></i>${esc(tipoPt(et.tipo))}</span><span class="chip">${nf1(et.distancia_km)} km</span>
          <span class="chip">${nf(r.participantes)} largaram</span><span class="chip">${nf(r.finalizaram)} chegaram</span>${r.idade_media ? `<span class="chip">idade média ${nf1(r.idade_media)}</span>` : ''}</div></div>
      ${rs.length ? '' : '<div class="note">Não há resultados individuais carregados para esta etapa.</div>'}
      ${pod.length ? `<div class="podium" style="margin-top:44px">${pod.map(p => `
        <div class="pod p${p.posicao}"><div class="medal">${p.posicao}</div><a href="#/ciclista/${p.ciclista_id}">${esc(nomeCurto(p.nome))}</a>
          <small>${esc(p.equipe || '—')}${p.idade ? ' · ' + p.idade + ' anos' : ''}</small>${p.pontos ? `<div class="pts">${p.pontos} pts</div>` : ''}</div>`).join('')}</div>` : ''}
      ${rs.length ? `<div class="card"><div class="tablebar"><input type="search" id="filtro" placeholder="Filtrar por nome ou equipe…" aria-label="Filtrar">
        <label class="sw"><input type="checkbox" id="nc"> Mostrar quem não terminou (${r.nao_classificados})</label></div>
        <div class="tw"><table><thead><tr><th>Pos.</th><th>Ciclista</th><th>Equipe</th><th class="num">Idade</th><th class="num">Pontos</th><th>Situação</th></tr></thead><tbody id="tb"></tbody></table></div>
        <div class="more" id="mais" hidden><button class="btn ghost" id="maisBtn">Mostrar mais</button></div></div>` : ''}`;
  }

  function ligaTabela(d) {
    const tb = $('#tb'); if (!tb) return;
    let lim = 40;
    const pinta = () => {
      const q = $('#filtro').value.trim().toLowerCase(), nc = $('#nc').checked;
      const lista = d.resultados.filter(r => (nc || r.status === 'FIN') && (!q || (r.nome + ' ' + (r.equipe || '')).toLowerCase().includes(q)));
      tb.innerHTML = lista.slice(0, lim).map(r => `<tr><td>${posBadge(r)}</td><td><a href="#/ciclista/${r.ciclista_id}">${esc(r.nome)}</a></td><td>${esc(r.equipe || '—')}</td>
        <td class="num">${r.idade ?? '–'}</td><td class="num">${r.pontos ?? '–'}</td><td>${stBadge(r.status)}</td></tr>`).join('') || '<tr><td colspan="6" class="empty">Nada encontrado</td></tr>';
      $('#mais').hidden = lista.length <= lim;
      $('#maisBtn').textContent = `Mostrar mais (${lista.length - lim})`;
    };
    $('#filtro').oninput = () => { lim = 40; pinta(); };
    $('#nc').onchange = () => { lim = 40; pinta(); };
    $('#maisBtn').onclick = () => { lim += 100; pinta(); };
    pinta();
  }

  async function painelNumeros() {
    painel.innerHTML = loading('Agregando no Cassandra, uma partição por etapa…');
    try {
      const d = await api(`/agg/edicao/${ano}`, {}, `números da edição ${ano}`);
      const rows = d.por_etapa;
      painel.innerHTML = `
        <div class="grid2" style="margin-top:20px">
          <div class="card chart"><h3>Tamanho do pelotão</h3><p>Quantos ciclistas largaram em cada etapa: dá para ver o desgaste da corrida.</p>${serie(rows, 'participantes', { tipo: 'area', fmt: nf })}
            <div class="cqlnote">SELECT COUNT(*) FROM resultados_por_etapa WHERE ano=? AND ordem=?</div></div>
          <div class="card chart"><h3>Idade média por etapa</h3><p>Média do pelotão (anos). A cor do ponto indica o tipo de etapa.</p>${serie(rows, 'idade_media', { tipo: 'linha', fmt: nf1 })}
            <div class="cqlnote">SELECT AVG(CAST(idade AS double)) FROM resultados_por_etapa WHERE ano=? AND ordem=?</div></div>
          <div class="card chart"><h3>Não classificados por etapa</h3><p>Abandonos, desclassificados e fora do tempo. A busca por <span class="mono">posicao = 9999</span> lê só uma fatia da partição.</p>${serie(rows, 'nao_classificados', { tipo: 'barra', fmt: nf })}
            <div class="cqlnote">SELECT COUNT(*) FROM resultados_por_etapa WHERE ano=? AND ordem=? AND posicao = 9999</div></div>
          <div class="card chart"><h3>Vitórias de etapa por equipe</h3><p>Quem mais venceu etapas nesta edição.</p>${hbars(d.vitorias_por_equipe, 'equipe', 'vitorias')}
            <div class="cqlnote">SELECT nome, equipe FROM resultados_por_etapa WHERE ano=? AND ordem=? AND posicao = 1 LIMIT 1</div></div>
        </div>
        <div class="note" style="margin-top:16px">Cada gráfico consulta <b>${rows.length} partições</b> (uma por etapa) e junta o resultado no cliente. O Cassandra agrega bem dentro de uma partição e mal entre partições, e é por isso que a consulta é feita assim.</div>`;
    } catch (err) { painel.innerHTML = `<div class="note warn" style="margin-top:20px">${esc(err.message)}</div>`; }
  }
  painelEtapas();
}

/* ------------------------------------------------------------------ CICLISTAS */
async function ciclistas() {
  view.innerHTML = `
    <section class="hero" style="padding-bottom:70px"><div class="wrap">
      <div class="kicker">Ciclistas</div><h1 style="font-size:clamp(40px,6vw,80px)">Quem pedalou?</h1>
      <p class="lead">Digite parte do nome. O histórico completo vem de uma única partição do Cassandra.</p>
      <div class="searchbox">${lupa}<input id="q" type="search" autocomplete="off" placeholder="Nome do ciclista…" aria-label="Buscar ciclista" autofocus><div class="sugg" id="sugg"></div></div>
      <div class="chips" style="margin-top:22px">${['Merckx', 'Hinault', 'Indurain', 'Froome', 'Cavendish', 'Contador'].map(n => `<button class="chip" data-q="${n}" style="cursor:pointer">${n}</button>`).join('')}</div>
    </div></section>`;
  bindSearch($('#q'), $('#sugg'));
  $$('.chip[data-q]').forEach(c => c.onclick = () => { const i = $('#q'); i.value = c.dataset.q; i.dispatchEvent(new Event('input')); i.focus(); });
}

function barrasAnos(anos) {
  const W = 760, H = 150, L = 8, R = 8, T = 8, B = 24, n = anos.length, iw = W - L - R;
  const bw = Math.min(46, iw / n), gap = n > 1 ? Math.min(14, (iw - bw * n) / (n - 1)) : 0;
  const total = n * bw + (n - 1) * gap, x0 = L + (iw - total) / 2;
  const max = Math.max(...anos.map(a => a.etapas), 1), y = v => T + (H - T - B) * (1 - v / max);
  return `<svg viewBox="0 0 ${W} ${H}" role="img" style="width:100%;height:auto">` + anos.map((a, i) => {
    const x = x0 + i * (bw + gap);
    return `<g data-tt="<b>${a.ano}</b><br>${a.etapas} etapas · ${a.vitorias} vitórias · ${a.top10} no top 10">
      <rect x="${x}" y="${y(a.etapas)}" width="${bw}" height="${y(0) - y(a.etapas)}" rx="4" fill="#E7E0C6"/>
      ${a.vitorias ? `<rect x="${x}" y="${y(a.vitorias)}" width="${bw}" height="${y(0) - y(a.vitorias)}" rx="4" fill="#FFD60A" stroke="#11151C" stroke-width="1.5"/>` : ''}
      <text x="${x + bw / 2}" y="${H - 7}" text-anchor="middle" font-size="${bw < 30 ? 9 : 11}" font-weight="700" fill="#2A303B">${bw < 30 ? String(a.ano).slice(2) : a.ano}</text></g>`;
  }).join('') + '</svg>';
}

async function ciclista(id) {
  const d = await api('/ciclistas/' + id, {}, 'histórico do ciclista');
  const c = d.ciclista, s = d.estatisticas, h = d.historico;
  const iniciais = c.nome.split(/\s+/).slice(0, 2).map(p => p[0]).join('').toUpperCase();
  const porAno = {};
  h.forEach(r => (porAno[r.ano] = porAno[r.ano] || []).push(r));
  const anosDesc = Object.keys(porAno).map(Number).sort((a, b) => b - a);
  view.innerHTML = `
    <section class="rider"><div class="wrap">
      <div class="crumbs" style="margin-bottom:16px"><a href="#/ciclistas" style="color:#fff;background:#ffffff1f">‹ Ciclistas</a></div>
      <div class="id"><div class="avatar">${esc(iniciais)}</div><div><h1>${esc(c.nome)}</h1>
        <div class="sub">${c.pais ? `<span class="chip">${esc(c.pais)}</span>` : ''}${c.data_nascimento ? `<span class="chip">nasc. ${fdata(c.data_nascimento)}</span>` : '<span class="chip">nascimento não informado</span>'}
        ${s.anos.length ? `<span class="chip">${s.anos[0].ano}${s.anos.length > 1 ? ' – ' + s.anos[s.anos.length - 1].ano : ''}</span>` : ''}</div></div></div>
    </div></section>
    <div class="wrap" style="padding-bottom:30px">
      <div class="tiles">
        <div class="tile y"><b>${nf(s.etapas)}</b><span>etapas disputadas</span></div>
        <div class="tile"><b>${s.vitorias}</b><span>vitórias de etapa</span></div>
        <div class="tile"><b>${s.podios}</b><span>pódios</span></div>
        <div class="tile"><b>${s.top10}</b><span>no top 10</span></div>
        <div class="tile"><b>${s.melhor_posicao ?? '–'}</b><span>melhor posição</span></div>
        <div class="tile"><b>${s.abandonos}</b><span>abandonos / DSQ</span></div>
      </div>
      ${h.length ? `
      <div class="card chart" style="margin-top:22px"><h3>Ano a ano</h3><p>Cinza: etapas disputadas. Amarelo: vitórias de etapa.</p>${barrasAnos(s.anos)}
        <div class="cqlnote">SELECT COUNT(*) AS etapas, MIN(posicao), SUM(pontos) FROM resultados_por_ciclista WHERE ciclista_id=? → ${nf(d.agregado_cql.etapas)} etapas, ${d.agregado_cql.pontos != null ? nf(d.agregado_cql.pontos) + ' pontos' : 'pontos não informados'}</div></div>
      <section class="sec" style="padding-top:30px"><div class="sec-h"><div><h2>Histórico</h2><p>Uma única partição, já ordenada da etapa mais recente para a mais antiga.</p></div></div>
      <div class="card">${anosDesc.map((a, i) => { const rs = porAno[a], v = rs.filter(r => r.status === 'FIN' && r.posicao === 1).length; return `
        <details class="year" ${i === 0 ? 'open' : ''}><summary><b>${a}</b><span>${rs.length} etapas</span>${v ? `<em>${v} vitória${v > 1 ? 's' : ''}</em>` : ''}</summary>
        <div class="tw"><table><thead><tr><th>Etapa</th><th>Data</th><th>Tipo</th><th class="num">km</th><th>Pos.</th><th>Equipe</th><th>Situação</th></tr></thead><tbody>
        ${rs.map(r => `<tr><td><a href="#/edicao/${r.ano}/${r.ordem}">Etapa ${r.ordem}</a></td><td>${fdata(r.data_etapa)}</td><td>${esc(tipoPt(r.tipo))}</td><td class="num">${nf1(r.distancia_km)}</td><td>${posBadge(r)}</td><td>${esc(r.equipe || '—')}</td><td>${stBadge(r.status)}</td></tr>`).join('')}
        </tbody></table></div></details>`; }).join('')}</div></section>`
      : '<div class="note" style="margin-top:22px">Este ciclista ainda não tem resultados.</div>'}
    </div>`;
}

/* ------------------------------------------------------------------ roteador */
const ROTAS = [
  [/^#\/?$/, home, 'home'], [/^#\/edicao\/(\d+)(?:\/(\d+))?$/, edicao, 'home'], [/^#\/ciclistas$/, ciclistas, 'ciclistas'],
  [/^#\/ciclista\/([0-9a-f-]+)$/i, ciclista, 'ciclistas'], [/^#\/demo$/, () => window.demo(), 'demo'], [/^#\/bastidores$/, () => window.bastidores(), 'bastidores'],
];
let ultimaRota = '';
async function rota() {
  const h = location.hash || '#/';
  for (const [re, fn, nav] of ROTAS) {
    const m = h.match(re);
    if (!m) continue;
    $$('#nav a').forEach(a => a.classList.toggle('on', a.dataset.nav === nav));
    ultimaRota = h;
    view.innerHTML = loading();
    window.scrollTo({ top: 0 });
    try { await fn(...m.slice(1)); } catch (e) { view.innerHTML = errBox(e); }
    document.title = 'Le Tour · Estatísticas';
    return;
  }
  location.hash = '#/';
}
window.addEventListener('hashchange', rota);

/* status do banco */
(async () => {
  try {
    const m = await (await fetch('/api/modo')).json();
    const s = $('#status');
    s.className = 'status ' + (m.modo === 'cassandra' ? '' : 'demo');
    s.innerHTML = m.modo === 'cassandra' ? '<i></i><span>Cassandra conectado</span>' : '<i></i><span>Modo demonstração (sem Cassandra)</span>';
    state.modo = m.modo;
  } catch { const s = $('#status'); s.className = 'status off'; s.innerHTML = '<i></i><span>API offline</span>'; }
})();
