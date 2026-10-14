'use strict';
/* Telas "Demonstração" (CRUD) e "Bastidores" (recursos do Cassandra) */

const SIM = '<span class="sim" title="Valores simulados: não há Cassandra conectado">SIMULADO</span>';
const campo = (f) => {
  if (f.type === 'rider') return `<label class="full">${f.l}<div class="rider-pick"><input class="input" data-rider name="${f.n}" placeholder="Digite para buscar…" autocomplete="off"><ul class="pick-list"></ul></div></label>`;
  if (f.type === 'select') return `<label>${f.l}<select class="input" name="${f.n}">${f.opts.map(o => `<option value="${esc(o[0])}">${esc(o[1])}</option>`).join('')}</select></label>`;
  return `<label class="${f.full ? 'full' : ''}">${f.l}<input class="input" name="${f.n}" type="${f.type || 'text'}" placeholder="${esc(f.ph || '')}" ${f.n === 'pais' ? 'maxlength="3"' : ''}></label>`;
};
const post = (url, v, label, method = 'POST') => api(url, { method, body: JSON.stringify(v) }, label);
const ANO = { n: 'ano', l: 'Ano', type: 'number', ex: 2099 };
const ORD = { n: 'ordem', l: 'Ordem da etapa', type: 'number', ex: 1 };
const RIDER = { n: 'ciclista_id', l: 'Ciclista', type: 'rider' };
const TIPO_OPTS = [['Plain stage', 'Plano'], ['Hilly stage', 'Acidentada'], ['High mountain stage', 'Alta montanha'], ['Individual time trial', 'Contrarrelógio'], ['Team time trial', 'Contrarrelógio por equipes']];

const FORMS = [
  { tag: 'INSERT', t: 'Cadastrar ciclista', d: 'Com IF NOT EXISTS (transação leve): não duplica o mesmo nome.',
    f: [{ n: 'nome', l: 'Nome (Sobrenome Nome)', ex: 'Teste Demonstracao', full: 1 }, { n: 'pais', l: 'País (3 letras)', ex: 'BRA' }, { n: 'data_nascimento', l: 'Nascimento', type: 'date', ex: '1990-05-17' }],
    run: v => post('/crud/ciclista', v, 'INSERT ciclista'), after: (r, v) => { state.lastRider = { id: r.ciclista_id, nome: v.nome }; } },
  { tag: 'INSERT', t: 'Cadastrar etapa', d: 'Uma linha na tabela etapas, dentro da partição do ano.',
    f: [ANO, ORD, { n: 'numero', l: 'Número', ex: '1' }, { n: 'data_etapa', l: 'Data', type: 'date', ex: '2099-07-01' },
      { n: 'tipo', l: 'Tipo', type: 'select', opts: TIPO_OPTS }, { n: 'distancia_km', l: 'Distância (km)', type: 'number', ex: 180 },
      { n: 'origem', l: 'Origem', ex: 'Ibirubá' }, { n: 'destino', l: 'Destino', ex: 'Cruz Alta' }, { n: 'vencedor', l: 'Vencedor', ex: 'Teste Demonstracao', full: 1 }],
    run: v => post('/crud/etapa', v, 'INSERT etapa') },
  { tag: 'INSERT', t: 'Registrar resultado', d: 'Grava nas duas tabelas de resultados, em um LOGGED BATCH.',
    f: [ANO, ORD, RIDER, { n: 'posicao', l: 'Posição', type: 'number', ex: 1 },
      { n: 'status', l: 'Situação', type: 'select', opts: [['FIN', 'FIN · finalizou'], ['DNF', 'DNF · abandonou'], ['DNS', 'DNS · não largou'], ['OTL', 'OTL · fora do tempo']] },
      { n: 'equipe', l: 'Equipe', ex: 'Equipe Demo' }, { n: 'idade', l: 'Idade', type: 'number', ex: 30 }, { n: 'pontos', l: 'Pontos', type: 'number', ex: 50 }],
    run: v => post('/crud/resultado', v, 'INSERT resultado (batch)') },
  { tag: 'UPDATE', t: 'Atualizar cadastro', d: 'UPDATE ... IF EXISTS: só altera quem já existe.',
    f: [RIDER, { n: 'pais', l: 'País (3 letras)', ex: 'ARG' }, { n: 'data_nascimento', l: 'Nascimento', type: 'date', ex: '1991-02-03' }],
    run: v => post('/crud/ciclista', v, 'UPDATE cadastro', 'PUT') },
  { tag: 'UPDATE', t: 'Desclassificar ciclista', d: 'Corrige um resultado: a posição é chave de clustering, então vira DELETE + INSERT.',
    f: [ANO, ORD, RIDER], run: v => post('/crud/desclassificar', v, 'UPDATE desclassificação (batch)') },
  { tag: 'DELETE', t: 'Cancelar etapa', d: 'Apaga a etapa e todos os seus resultados nas duas tabelas.',
    f: [ANO, ORD], confirmar: true, run: v => api(`/crud/etapa/${+v.ano}/${+v.ordem}`, { method: 'DELETE' }, 'DELETE etapa') },
];

function ligaRider(inp) {
  const lista = inp.parentElement.querySelector('.pick-list');
  const busca = debounce(async () => {
    const q = inp.value.trim();
    if (q.length < 2) { lista.innerHTML = ''; return; }
    const rows = await api('/ciclistas?q=' + encodeURIComponent(q), {}, 'busca de ciclista');
    lista.innerHTML = rows.map(r => `<li data-id="${r.id}" data-n="${esc(r.nome)}"><span>${esc(r.nome)}</span><small>${esc(r.pais || '')}</small></li>`).join('');
  });
  inp.addEventListener('input', () => { delete inp.dataset.id; busca(); });
  lista.addEventListener('click', e => {
    const li = e.target.closest('li'); if (!li) return;
    e.preventDefault(); inp.value = li.dataset.n; inp.dataset.id = li.dataset.id; lista.innerHTML = '';
  });
}

window.demo = async function () {
  view.innerHTML = `
    <section class="banner"><div class="wrap">
      <div class="crumbs"><span>Demonstração</span></div>
      <h1 style="font-size:clamp(44px,7vw,84px);font-style:italic;font-weight:800;margin:10px 0 8px">Escrevendo no Cassandra</h1>
      <p style="max-width:62ch;margin:0;font-weight:500">Siga os passos na ordem. Os exemplos usam o ano fictício <b>2099</b>, para não mexer nos dados reais. Depois de cada operação, veja o resultado no painel ao lado e o CQL no botão <span class="mono">&lt;/&gt; CQL</span>.</p>
    </div></section>
    <div class="wrap" style="padding:26px clamp(16px,4vw,32px) 40px">
      <div class="layout">
        <div class="steps">${FORMS.map((f, i) => `
          <details class="card op" data-i="${i}" ${i === 0 ? 'open' : ''}>
            <summary><span class="no">${i + 1}</span><span class="tg ${f.tag}">${f.tag}</span><div><h4>${f.t}</h4><small>${f.d}</small></div></summary>
            <div class="opbody"><div class="fields">${f.f.map(campo).join('')}</div>
              <div class="actions"><button class="btn ${f.tag === 'DELETE' ? 'danger' : ''}" data-act="run">Executar</button><button class="btn ghost" data-act="ex">Preencher exemplo</button></div>
              <div class="out"></div></div></details>`).join('')}</div>
        <aside class="sticky"><div class="card sbox"><h3>Estado no banco</h3>
          <div class="row"><label>Ano<input id="vAno" class="input" type="number" value="2099"></label><label>Etapa<input id="vOrd" class="input" type="number" value="1"></label><button class="btn ghost" id="vGo">Ver</button></div>
          <div id="vOut" style="margin-top:12px"></div></div></aside>
      </div></div>`;

  const ver = async () => {
    const ano = +$('#vAno').value, ord = +$('#vOrd').value, out = $('#vOut');
    try {
      const d = await api(`/etapas/${ano}/${ord}`, {}, 'estado da etapa');
      const e = d.etapa, rs = d.resultados;
      out.innerHTML = `<p style="margin:0 0 8px"><b>${esc(numeroLabel(e.numero))}</b> · ${fdata(e.data_etapa)}<br>${esc(e.origem || '–')} → ${esc(e.destino || '–')} · ${nf1(e.distancia_km)} km · ${esc(tipoPt(e.tipo))}</p>
        ${rs.length ? `<div class="tw"><table class="mini"><thead><tr><th>Pos.</th><th>Ciclista</th><th>Situação</th></tr></thead><tbody>${rs.slice(0, 12).map(r => `<tr><td>${posBadge(r)}</td><td><a href="#/ciclista/${r.ciclista_id}">${esc(r.nome)}</a></td><td>${stBadge(r.status)}</td></tr>`).join('')}</tbody></table></div>${rs.length > 12 ? `<p style="color:var(--mute);font-size:13px;margin:6px 0 0">+ ${rs.length - 12} resultados</p>` : ''}` : '<div class="note">Etapa sem resultados.</div>'}`;
    } catch (e) { out.innerHTML = `<div class="note warn">${esc(e.message)}</div>`; }
  };
  $('#vGo').onclick = ver; ver();

  $$('.op').forEach(card => {
    const f = FORMS[+card.dataset.i], out = $('.out', card);
    $$('input[data-rider]', card).forEach(ligaRider);
    $('[data-act=ex]', card).onclick = () => {
      f.f.forEach(c => {
        const el = $(`[name=${c.n}]`, card);
        if (c.type === 'rider') { if (state.lastRider) { el.value = state.lastRider.nome; el.dataset.id = state.lastRider.id; } else el.placeholder = 'Cadastre o ciclista no passo 1 (ou busque um)'; }
        else if (c.ex != null) el.value = c.ex;
      });
    };
    $('[data-act=run]', card).onclick = async ev => {
      const btn = ev.currentTarget, v = {};
      f.f.forEach(c => { const el = $(`[name=${c.n}]`, card); v[c.n] = c.type === 'rider' ? (el.dataset.id || '') : el.value; });
      if (f.confirmar && !confirm(`Cancelar a etapa ${v.ano}/${v.ordem} e apagar seus resultados?`)) return;
      btn.disabled = true;
      try {
        const r = await f.run(v);
        if (f.after) f.after(r, v);
        invalidar();
        const link = r.ciclista_id ? ` <a href="#/ciclista/${r.ciclista_id}"><b>abrir ciclista</b></a>` : '';
        out.innerHTML = `<div class="result ok">✔ ${esc(r.mensagem)}${link}</div>`;
        toast('Executado com sucesso');
        if (v.ano && v.ordem) { $('#vAno').value = v.ano; $('#vOrd').value = v.ordem; }
        ver();
      } catch (e) { out.innerHTML = `<div class="result err">✖ ${esc(e.message)}</div>`; }
      btn.disabled = false;
    };
  });
};

/* ------------------------------------------------------------------ BASTIDORES */
const NODECOL = ['#D7263D', '#2D6CDF', '#1E9E5A', '#F08A24', '#12A4B8'];
const QUERIES = {
  ranking: 'ranking de uma etapa', ciclistas: 'dados cadastrais de um ciclista', edicoes: 'dados de uma edição',
  etapas: 'etapas de uma edição, em ordem', resultados_por_etapa: 'ranking de uma etapa', resultados_por_ciclista: 'histórico de um ciclista',
};
const EXEMPLOS = [
  ['Eficiente: pela chave', "SELECT posicao, nome, equipe FROM resultados_por_etapa WHERE ano = 2010 AND ordem = 4 LIMIT 5"],
  ['Token da partição', "SELECT token(ano, ordem), ano, ordem FROM resultados_por_etapa WHERE ano = 2010 AND ordem = 4 LIMIT 1"],
  ['Filtro sem chave (erro)', "SELECT * FROM etapas WHERE tipo = 'High mountain stage'"],
  ['ALLOW FILTERING (varredura)', "SELECT nome, pais FROM ciclistas WHERE pais = 'BRA' ALLOW FILTERING"],
];

function anel(d, nos) {
  const cx = 180, cy = 180, r = 128, cor = ip => NODECOL[Math.max(0, nos.indexOf(ip)) % NODECOL.length];
  const pos = f => { const a = f * 2 * Math.PI - Math.PI / 2; return [cx + r * Math.cos(a), cy + r * Math.sin(a)]; };
  let s = `<svg viewBox="0 0 360 360" role="img" aria-label="Anel de tokens"><circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#E7E0C6" stroke-width="20"/>
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="#11151C" stroke-width="2" stroke-dasharray="2 8"/>
    <text x="${cx}" y="${cy - 4}" text-anchor="middle" font-family="Barlow Condensed" font-weight="800" font-size="20" fill="#11151C">ANEL DE TOKENS</text>
    <text x="${cx}" y="${cy + 16}" text-anchor="middle" font-size="12" fill="#6B7280">Murmur3 · −2⁶³ … 2⁶³</text>`;
  d.resultados_por_etapa.forEach(p => {
    const [x, y] = pos(p.frac);
    s += `<circle cx="${x}" cy="${y}" r="9" fill="${cor(p.replicas[0])}" stroke="#fff" stroke-width="2.5" data-tt="<b>Etapa ${p.ordem}</b><br>token ${p.token}<br>réplicas: ${p.replicas.join(', ')}"/>`;
  });
  if (d.etapas) {
    const [x, y] = pos(d.etapas.frac);
    s += `<path d="M${x} ${y - 13}l11 13-11 13-11-13Z" fill="#FFD60A" stroke="#11151C" stroke-width="2.5" data-tt="<b>Tabela etapas</b><br>todas as etapas de ${d.ano} na mesma partição<br>token ${d.etapas.token}<br>réplicas: ${d.etapas.replicas.join(', ')}"/>`;
  }
  return s + '</svg>';
}

window.bastidores = async function () {
  const [info, eds] = await Promise.all([api('/avancado/cluster', {}, 'metadados do cluster'), getEdicoes()]);
  const anos = eds.filter(e => e.com_resultados).map(e => e.ano);
  const sim = info.simulado ? SIM : '';
  const ips = info.nos.map(n => n.endereco);
  view.innerHTML = `
    <section class="banner"><div class="wrap"><div class="crumbs"><span>Bastidores</span></div>
      <h1 style="font-size:clamp(44px,7vw,84px);font-style:italic;font-weight:800;margin:10px 0 8px">Por dentro do Cassandra</h1>
      <p style="max-width:64ch;margin:0;font-weight:500">Nós do cluster, chaves de cada tabela, onde cada partição mora, o que muda com o nível de consistência e um console CQL para testar consultas.</p>
    </div></section>
    <div class="wrap" style="padding-bottom:50px">
      <section class="sec"><div class="sec-h"><div><h2>Cluster ${sim}</h2><p>Keyspace <span class="mono">${esc(info.keyspace)}</span> com replicação <span class="mono">${esc(info.replicacao)}</span>: cada partição é copiada em ${info.rf} nó(s).</p></div></div>
        <div class="nodes">${info.nos.map((n, i) => `<div class="card node"><span class="dot" style="background:${n.ativo ? NODECOL[i % 5] : '#bbb'}"></span><div><b>${esc(n.endereco)}</b><small>${esc(n.dc)} · ${esc(n.rack)} · ${n.ativo ? 'ativo' : 'fora do ar'}</small></div></div>`).join('')}</div></section>

      <section class="sec"><div class="sec-h"><div><h2>Anatomia das chaves</h2><p>Chave de partição decide <b>onde</b> os dados ficam. Colunas de clustering decidem <b>a ordem</b> dentro da partição.</p></div></div>
        <div class="keys">${info.tabelas.map(t => `<div class="card kt"><h4>${esc(t.tabela)}</h4><p>${QUERIES[t.tabela] || ''}</p>
          <div class="k">partição ${t.particao.map(c => `<span class="key pk">${esc(c)}</span>`).join('')}</div>
          <div class="k">clustering ${t.clustering.length ? t.clustering.map(c => `<span class="key ck">${esc(c.coluna)} ${c.ordem}</span>`).join('') : '<span style="text-transform:none;letter-spacing:0;font-weight:500">nenhuma: uma linha por partição</span>'}</div></div>`).join('')}</div></section>

      <section class="sec"><div class="sec-h"><div><h2>Particionamento ${sim}</h2><p>Escolha uma edição e veja em que ponto do anel cada partição cai.</p></div>
        <label class="sw">Edição <select id="pAno" class="input">${anos.slice().reverse().map(a => `<option ${a === 2010 ? 'selected' : ''}>${a}</option>`).join('')}</select></label></div>
        <div class="card ringwrap"><div id="anel"></div><div id="anelTxt"></div></div></section>

      <section class="sec"><div class="sec-h"><div><h2>Consistência ${sim}</h2><p>O mesmo SELECT com níveis diferentes: quantas réplicas precisam responder antes de o Cassandra devolver o dado.</p></div></div>
        <div class="card" style="padding:18px"><div class="cl-grid" id="cls">
          ${[['ONE', 'rápido, tolera falhas'], ['QUORUM', 'maioria das réplicas'], ['ALL', 'todas as réplicas']].map((c, i) => `<button class="cl ${i === 0 ? 'on' : ''}" data-cl="${c[0]}"><b>${c[0]}</b><span>${c[1]}</span></button>`).join('')}</div>
          <button class="btn" id="cRun">Executar consulta</button>
          <div class="cons-out" id="cOut"></div>
          <div class="note" style="margin-top:14px">Para ver a tolerância a falhas: derrube um nó (<span class="mono">docker stop tdf-cassandra3</span>) e execute de novo. Com 3 réplicas, <b>ONE</b> e <b>QUORUM</b> continuam respondendo; <b>ALL</b> falha.</div></div></section>

      <section class="sec"><div class="sec-h"><div><h2>Console CQL</h2><p>Só SELECT. Teste consultas boas e ruins e veja a resposta do Cassandra.</p></div></div>
        <div class="card" style="padding:18px"><div class="chips" style="margin-bottom:10px">${EXEMPLOS.map((e, i) => `<button class="chip" data-e="${i}" style="cursor:pointer">${esc(e[0])}</button>`).join('')}</div>
          <textarea id="cql" class="cql" spellcheck="false">${esc(EXEMPLOS[0][1])}</textarea>
          <div class="actions" style="margin-top:10px"><button class="btn" id="qRun">Executar</button></div><div id="qOut" style="margin-top:12px"></div></div></section>
    </div>`;

  const pintaAnel = async () => {
    const ano = +$('#pAno').value;
    try {
      const d = await api(`/avancado/particoes/${ano}`, {}, `partições de ${ano}`);
      $('#anel').innerHTML = anel(d, ips);
      $('#anelTxt').innerHTML = `
        <p style="margin:0 0 10px">Em <span class="mono">resultados_por_etapa</span> cada etapa é uma <b>partição própria</b>: ${d.resultados_por_etapa.length} círculos espalhados, e o Cassandra distribui a carga entre os nós.</p>
        <p style="margin:0 0 14px">Em <span class="mono">etapas</span> a chave é só o ano, então todas as etapas de ${ano} ficam <b>juntas</b>, na partição do losango amarelo.</p>
        <div class="tw" style="max-height:230px"><table class="mini"><thead><tr><th>Etapa</th><th>Token</th><th>Réplicas</th></tr></thead><tbody>${d.resultados_por_etapa.map(p => `<tr><td>${p.ordem}</td><td class="mono" style="font-size:12px">${p.token}</td><td>${p.replicas.map(r => `<span class="chip" style="padding:1px 8px;border-color:${NODECOL[ips.indexOf(r) % 5]}">${r.split('.').slice(-1)[0]}</span>`).join(' ')}</td></tr>`).join('')}</tbody></table></div>`;
    } catch (e) { $('#anelTxt').innerHTML = `<div class="note warn">${esc(e.message)}</div>`; }
  };
  $('#pAno').onchange = pintaAnel; pintaAnel();

  let cl = 'ONE';
  $$('#cls .cl').forEach(b => b.onclick = () => { cl = b.dataset.cl; $$('#cls .cl').forEach(x => x.classList.toggle('on', x === b)); });
  $('#cRun').onclick = async () => {
    const out = $('#cOut'); out.innerHTML = loading('Consultando…');
    try {
      const ano = +$('#pAno').value, d = await api(`/avancado/consistencia?ano=${ano}&ordem=4&cl=${cl}`, {}, `consistência ${cl}`);
      out.innerHTML = d.ok
        ? `<div class="result ok">✔ <b>${d.cl}</b> respondeu em <b>${d.ms} ms</b>. Precisou de <b>${d.replicas_necessarias}</b> de ${d.rf} réplicas (${d.replicas.join(', ')}).${d.linhas.length ? '<br>' + d.linhas.map(r => `${r.posicao}º ${esc(r.nome)}`).join(' · ') : ''}</div>`
        : `<div class="result err">✖ <b>${d.cl}</b> falhou: precisava de ${d.replicas_necessarias} de ${d.rf} réplicas.<br><span class="mono" style="font-size:12.5px">${esc(d.erro)}</span></div>`;
    } catch (e) { out.innerHTML = `<div class="result err">✖ ${esc(e.message)}</div>`; }
  };

  $$('.chip[data-e]').forEach(c => c.onclick = () => { $('#cql').value = EXEMPLOS[+c.dataset.e][1]; });
  $('#qRun').onclick = async () => {
    const out = $('#qOut'); out.innerHTML = loading('Executando…');
    try {
      const d = await post('/avancado/console', { cql: $('#cql').value }, 'console CQL');
      out.innerHTML = d.linhas.length ? `<div class="tw card"><table class="mini"><thead><tr>${d.colunas.map(c => `<th>${esc(c)}</th>`).join('')}</tr></thead><tbody>${d.linhas.slice(0, 100).map(r => `<tr>${d.colunas.map(c => `<td>${esc(r[c] ?? '–')}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p style="color:var(--mute);font-size:13px">${d.linhas.length} linha(s)</p>` : '<div class="note">Consulta sem resultados.</div>';
    } catch (e) { out.innerHTML = `<div class="result err">✖ ${esc(e.message)}</div>`; }
  };
};

rota();
