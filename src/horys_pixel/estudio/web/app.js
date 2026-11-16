// Horys Estúdio — interface local (estilo Noct): pastas, grade, inspetor com zoom de pixel, player de folha,
// riscar e mandar ao chat, aprovar/reprovar, paleta (recolor), boas práticas, Blender e pedidos.
"use strict";
const T = window.HORYS_TOKEN;
const $ = (s, el = document) => el.querySelector(s);
const el = (tag, attrs = {}, ...filhos) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v !== undefined && v !== null) e.setAttribute(k, v);
  }
  for (const f of filhos.flat()) if (f !== null && f !== undefined) e.append(f.nodeType ? f : document.createTextNode(String(f)));
  return e;
};
async function api(caminho, corpo) {
  const op = { headers: { "X-Horys-Token": T } };
  if (corpo !== undefined) { op.method = "POST"; op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(corpo); }
  const r = await fetch(caminho, op);
  const j = await r.json();
  if (!r.ok) throw new Error(j.erro || r.statusText);
  return j;
}
const arq = (p, v) => `/arquivo?t=${encodeURIComponent(T)}&p=${encodeURIComponent(p)}&v=${v || 0}`;
function toast(msg, erro) {
  const t = el("div", { class: "toast" + (erro ? " erro" : "") }, msg);
  document.body.append(t); setTimeout(() => t.remove(), erro ? 6000 : 3000);
}

// ------------------------------------------------------------------ estado
const S = {
  raizes: [], abertos: new Set(JSON.parse(localStorage.getItem("horys.abertos") || "[]")),
  pasta: null, info: null, item: null, img: null, quadro: 0, tocando: null,
  zoom: 4, fundo: "xadrez", grade: false, onion: false,
  ferramenta: "caneta", cor: "#ff3b6b", espessura: 2, marcas: [], desenhando: null,
  aba: "riscar", pedidos: [], jobs: [], jobsVistos: new Set(),
};
const salvarAbertos = () => { try { localStorage.setItem("horys.abertos", JSON.stringify([...S.abertos])); } catch (e) { /* sem storage */ } };

// ------------------------------------------------------------------ árvore
async function carregarArvore() {
  const j = await api("/api/arvore");
  S.raizes = j.raizes;
  for (const r of S.raizes) S.abertos.add(r.caminho);
  desenharArvore();
  $("#status").textContent = "conectado";
}
function desenharArvore() {
  const filtro = $("#busca").value.trim().toLowerCase();
  const box = $("#arvore"); box.innerHTML = "";
  const casa = (n) => !filtro || n.nome.toLowerCase().includes(filtro) || n.filhos.some(casa);
  const no = (n) => {
    if (!casa(n)) return null;
    const aberto = S.abertos.has(n.caminho) || !!filtro;
    const linha = el("div", { class: "linha" + (S.pasta === n.caminho ? " sel" : ""), title: n.caminho },
      el("span", { class: "seta" }, n.filhos.length ? (aberto ? "▾" : "▸") : ""),
      el("span", {}, n.nome),
      n.tipo !== "pasta" ? el("span", { class: "tag-tipo" }, n.tipo) : null,
      el("span", { class: "cont" }, n.total));
    linha.addEventListener("click", (ev) => {
      if (ev.target.classList.contains("seta") && n.filhos.length) {
        aberto ? S.abertos.delete(n.caminho) : S.abertos.add(n.caminho); salvarAbertos(); desenharArvore(); return;
      }
      S.abertos.add(n.caminho); salvarAbertos(); abrirPasta(n.caminho);
    });
    return el("div", { class: "no" }, linha, aberto && n.filhos.length ? el("div", { class: "filhos" }, n.filhos.map(no)) : null);
  };
  box.append(...S.raizes.map(no).filter(Boolean));
}

// ------------------------------------------------------------------ pasta (grade)
async function abrirPasta(caminho) {
  pararPlay();
  S.pasta = caminho; S.item = null;
  desenharArvore();
  try { S.info = await api("/api/pasta?p=" + encodeURIComponent(caminho)); } catch (e) { return toast(e.message, true); }
  desenharGrade();
  desenharPainel();
}
function desenharGrade() {
  const m = $("#principal"); m.innerHTML = "";
  const info = S.info;
  const nome = info.caminho.split(/[\\/]/).pop();
  const acoes = [];
  if (info.config_blender) {
    acoes.push(el("button", { onclick: () => blender(true), title: info.config_blender }, "Prévia no Blender"));
    acoes.push(el("button", { class: "prim", onclick: () => blender(false) }, "Render completo"));
  }
  if (info.itens.some((i) => i.folha && /_/.test(i.nome))) acoes.unshift(el("button", { class: "prim", onclick: abrirResultado }, "Ver resultado final"));
  const cab = el("div", { class: "cab-pasta" }, el("h2", {}, nome), ...acoes,
    el("span", { class: "dica" }, `${info.itens.length} imagens`), el("div", { class: "caminho" }, info.caminho));
  const filtro = $("#busca").value.trim().toLowerCase();
  const grade = el("div", { class: "grade" });
  for (const it of info.itens) {
    if (filtro && !it.nome.toLowerCase().includes(filtro) && !info.caminho.toLowerCase().includes(filtro)) continue;
    const meta = it.tipo === "modelo" ? "3D" : it.folha ? `${it.folha.quadros.length} quadros` : `${it.w}×${it.h}`;
    const mini = it.tipo === "modelo"
      ? (it.miniatura ? el("img", { src: arq(it.miniatura, it.mtime), loading: "lazy", alt: it.nome, style: "image-rendering:auto" }) : el("div", { style: "font-size:42px;color:var(--mudo)" }, "⬡"))
      : el("img", { src: arq(it.caminho, it.mtime), loading: "lazy", alt: it.nome });
    grade.append(el("div", { class: "card", onclick: () => (it.tipo === "modelo" ? abrirModelo(it) : abrirItem(it)) },
      el("div", { class: "mini" }, mini),
      el("div", { class: "rod" }, el("span", { class: "n", title: it.nome }, it.nome),
        it.estado ? el("span", { class: "est " + it.estado }, it.estado) : null,
        el("span", { class: "dica" }, meta))));
  }
  m.append(cab, grade);
}

// ------------------------------------------------------------------ inspetor
async function abrirItem(it, srcPronto) {
  pararPlay();
  S.item = it; S.quadro = 0; S.marcas = [];
  const img = new Image();
  img.src = srcPronto || arq(it.caminho, it.mtime);
  await img.decode().catch(() => {});
  S.img = img;
  const m = $("#principal"); m.innerHTML = "";
  m.append($("#tpl-inspetor").content.cloneNode(true));
  const ins = $(".inspetor", m);
  $(".titulo", ins).textContent = it.nome;
  ins.querySelectorAll(".so-folha").forEach((e) => (e.style.display = it.folha ? "" : "none"));
  const ctl = (n) => $(`[data-ctl=${n}]`, ins);
  ctl("zoom").value = String(S.zoom); ctl("fundo").value = S.fundo; ctl("grade").checked = S.grade; ctl("onion").checked = S.onion;
  ctl("zoom").onchange = (e) => { S.zoom = +e.target.value; render(); };
  ctl("fundo").onchange = (e) => { S.fundo = e.target.value; render(); };
  ctl("grade").onchange = (e) => { S.grade = e.target.checked; render(); };
  ctl("onion").onchange = (e) => { S.onion = e.target.checked; render(); };
  ins.querySelector("[data-acao=voltar]").onclick = () => { pararPlay(); S.item = null; desenharGrade(); desenharPainel(); };
  ins.querySelector("[data-acao=play]").onclick = alternarPlay;
  ins.querySelector("[data-acao=ant]").onclick = () => passo(-1);
  ins.querySelector("[data-acao=prox]").onclick = () => passo(1);
  ligarRisco($(".c-risco", ins));
  desenharTira();
  render();
  desenharPainel();
}
function quadroRect(i) {
  const it = S.item;
  if (it && it.folha) return it.folha.quadros[i];
  return { x: 0, y: 0, w: S.img.naturalWidth, h: S.img.naturalHeight, ms: 100 };
}
function render() {
  const ins = $(".inspetor"); if (!ins || !S.img) return;
  const r = quadroRect(S.quadro), z = S.zoom;
  const ci = $(".c-img", ins), cr = $(".c-risco", ins), tela = $(".tela", ins);
  for (const c of [ci, cr]) { c.width = r.w * z; c.height = r.h * z; }
  tela.style.width = r.w * z + "px"; tela.style.height = r.h * z + "px";
  tela.className = "tela fundo-" + S.fundo;
  const g = ci.getContext("2d"); g.imageSmoothingEnabled = false;
  if (S.onion && S.item.folha) {
    const ant = quadroRect((S.quadro - 1 + S.item.folha.quadros.length) % S.item.folha.quadros.length);
    g.globalAlpha = 0.3; g.drawImage(S.img, ant.x, ant.y, ant.w, ant.h, 0, 0, ant.w * z, ant.h * z); g.globalAlpha = 1;
  }
  g.drawImage(S.img, r.x, r.y, r.w, r.h, 0, 0, r.w * z, r.h * z);
  if (S.grade && z >= 4) {
    g.strokeStyle = "rgba(255,255,255,.08)"; g.lineWidth = 1; g.beginPath();
    for (let x = 0; x <= r.w; x++) { g.moveTo(x * z + .5, 0); g.lineTo(x * z + .5, r.h * z); }
    for (let y = 0; y <= r.h; y++) { g.moveTo(0, y * z + .5); g.lineTo(r.w * z, y * z + .5); }
    g.stroke();
  }
  desenharMarcas(cr.getContext("2d"), z);
  const n = $(".quadro-n", ins);
  if (n && S.item.folha) n.textContent = `${S.quadro + 1}/${S.item.folha.quadros.length} · ${r.ms} ms`;
  ins.querySelectorAll(".tira canvas").forEach((c, i) => c.classList.toggle("atual", i === S.quadro));
}
function desenharTira() {
  const tira = $(".tira"); if (!tira || !S.item.folha) return;
  tira.innerHTML = "";
  S.item.folha.quadros.forEach((q, i) => {
    const k = Math.max(1, Math.floor(64 / Math.max(q.w, q.h)));
    const c = el("canvas", { width: q.w * k, height: q.h * k, title: `quadro ${i + 1} · ${q.ms} ms` });
    const g = c.getContext("2d"); g.imageSmoothingEnabled = false;
    g.drawImage(S.img, q.x, q.y, q.w, q.h, 0, 0, q.w * k, q.h * k);
    c.onclick = () => { pararPlay(); S.quadro = i; render(); };
    tira.append(c);
  });
}
function passo(d) { if (!S.item || !S.item.folha) return; pararPlay(); const n = S.item.folha.quadros.length; S.quadro = (S.quadro + d + n) % n; render(); }
function alternarPlay() { S.tocando ? pararPlay() : tocar(); }
function tocar() {
  if (!S.item || !S.item.folha) return;
  const b = $("[data-acao=play]"); if (b) b.textContent = "⏸";
  const avanca = () => {
    const n = S.item.folha.quadros.length; S.quadro = (S.quadro + 1) % n; render();
    S.tocando = setTimeout(avanca, quadroRect(S.quadro).ms || 100);
  };
  S.tocando = setTimeout(avanca, quadroRect(S.quadro).ms || 100);
}
function pararPlay() { if (S.tocando) clearTimeout(S.tocando); S.tocando = null; const b = $("[data-acao=play]"); if (b) b.textContent = "▶"; }

// ------------------------------------------------------------------ modelo 3D (model-viewer)
let mvCarregado = null;
function carregarModelViewer() {
  if (!mvCarregado) mvCarregado = new Promise((ok, erro) => {
    const sc = el("script", { type: "module", src: "/static/model-viewer.min.js" });
    sc.onload = ok; sc.onerror = () => erro(new Error("não carregou o visualizador 3D (model-viewer.min.js)"));
    document.head.append(sc);
  });
  return mvCarregado;
}
// direções do jogo: câmera top-down (elevação 43° = polar 47°); 0° = frente (sul)
const DIRECOES_3D = [["S", 0], ["SE", 45], ["L", 90], ["NE", 135], ["N", 180], ["NO", 225], ["O", 270], ["SO", 315]];
const ELEVACAO_JOGO = 47;
async function abrirModelo(it) {
  pararPlay(); pararResultado();
  S.item = it; S.marcas = [];
  if (!S.marcas3d || S.marcas3d.asset !== it.caminho) S.marcas3d = { asset: it.caminho, lista: [] };
  S.apontando = false;
  try { await carregarModelViewer(); } catch (e) { toast(e.message, true); }
  const m = $("#principal"); m.innerHTML = "";
  const mv = el("model-viewer", { src: arq(it.caminho, it.mtime), "camera-controls": "", autoplay: "", "shadow-intensity": "0.7",
    exposure: "1", "camera-orbit": `0deg ${ELEVACAO_JOGO}deg auto`, "interaction-prompt": "none",
    style: "width:100%;height:100%;background:#2a2d33" });
  S.mv = mv;
  const selAnim = el("select", { title: "animação" });
  mv.addEventListener("load", () => {
    const an = mv.availableAnimations || [];
    selAnim.innerHTML = "";
    selAnim.append(el("option", { value: "" }, an.length ? "animação…" : "sem animação"), ...an.map((a) => el("option", { value: a }, a)));
    if (an.length) { mv.animationName = an[0]; selAnim.value = an[0]; mv.play(); }
    S.marcas3d.lista.forEach(colocarHotspot);
  });
  selAnim.onchange = (e) => { if (e.target.value) { mv.animationName = e.target.value; mv.play(); } };
  const playB = el("button", { class: "icone", title: "tocar/pausar a animação", onclick: () => (mv.paused ? mv.play() : mv.pause()) }, "⏯");
  const vel = el("select", { title: "velocidade" }, ["0.25", "0.5", "1", "1.5"].map((v) => el("option", { value: v, ...(v === "1" ? { selected: "" } : {}) }, v + "×")));
  vel.onchange = (e) => (mv.timeScale = +e.target.value);
  const giro = el("input", { type: "checkbox" });
  giro.onchange = (e) => (e.target.checked ? mv.setAttribute("auto-rotate", "") : mv.removeAttribute("auto-rotate"));
  const expo = el("input", { type: "range", min: "0.3", max: "2.5", step: "0.1", value: "1", style: "width:70px" });
  expo.oninput = (e) => mv.setAttribute("exposure", e.target.value);
  const fundo = el("select", {}, ["#2a2d33", "#68a057", "#111111", "#e6e2d8"].map((c) => el("option", { value: c }, c)));
  fundo.onchange = (e) => (mv.style.background = e.target.value);
  const dirs = el("span", { class: "player", title: "8 direções no ângulo do jogo" },
    DIRECOES_3D.map(([n, az]) => el("button", { class: "icone", onclick: () => {
      giro.checked = false; mv.removeAttribute("auto-rotate"); mv.cameraOrbit = `${az}deg ${ELEVACAO_JOGO}deg auto`;
    } }, n)),
    el("button", { onclick: () => (mv.cameraOrbit = "0deg 85deg auto"), title: "de frente, na altura" }, "frente"),
    el("button", { onclick: () => (mv.cameraOrbit = "0deg 5deg auto"), title: "de cima" }, "topo"));
  const apontar = el("button", { class: "prim" }, "Apontar defeito");
  apontar.onclick = () => {
    S.apontando = !S.apontando;
    apontar.textContent = S.apontando ? "Clique no modelo… (Esc sai)" : "Apontar defeito";
    mv.style.cursor = S.apontando ? "crosshair" : "";
  };
  mv.addEventListener("click", (ev) => {
    if (!S.apontando) return;
    const hit = mv.positionAndNormalFromPoint(ev.clientX, ev.clientY);
    if (!hit) return toast("Clique em cima do modelo.", true);
    const nota = prompt("Qual é o defeito aqui?");
    if (!nota) return;
    const v = (p) => `${p.x.toFixed(3)}m ${p.y.toFixed(3)}m ${p.z.toFixed(3)}m`;
    const mk = { tipo: "3d", n: S.marcas3d.lista.length + 1, nota, posicao: v(hit.position), normal: v(hit.normal),
      orbita: mv.getCameraOrbit().toString(), animacao: mv.animationName || "", tempo: +(mv.currentTime || 0).toFixed(2),
      foto: mv.toDataURL("image/png") };
    S.marcas3d.lista.push(mk); colocarHotspot(mk); desenharPainel();
  });
  const abrirBl = el("button", { onclick: async () => {
    try { await api("/api/abrir_blender", { caminho: it.caminho }); toast("Abrindo no Blender…"); } catch (e) { toast(e.message, true); }
  } }, "Abrir no Blender");
  const aprovar3d = el("button", { class: "ok", onclick: () => { S.aba = "aprovar"; desenharPainel(); } }, "Aprovar…");
  m.append(el("div", { class: "inspetor" },
    el("div", { class: "barra" },
      el("button", { class: "icone", onclick: () => { S.item = null; S.mv = null; desenharGrade(); desenharPainel(); } }, "←"),
      el("span", { class: "titulo" }, it.nome), selAnim, playB, vel, dirs,
      el("label", {}, giro, " girar"), el("label", {}, "luz ", expo), el("label", {}, "fundo ", fundo), apontar, abrirBl, aprovar3d),
    el("div", { class: "palco", style: "padding:0" }, mv)));
  if (S.aba !== "aprovar") S.aba = "riscar";
  desenharPainel();
}
function colocarHotspot(mk) {
  if (!S.mv) return;
  const b = el("button", { slot: "hotspot-" + mk.n, class: "hotspot", "data-position": mk.posicao, "data-normal": mk.normal, title: mk.nota }, String(mk.n));
  b.onclick = (ev) => { ev.stopPropagation(); irParaMarca(mk); };
  S.mv.append(b);
}
function irParaMarca(mk) {
  const mv = S.mv; if (!mv) return;
  mv.removeAttribute("auto-rotate");
  if (mk.animacao) { mv.animationName = mk.animacao; mv.pause(); mv.currentTime = mk.tempo || 0; }
  mv.cameraOrbit = mk.orbita;
}
function aba3d() {
  const s = el("div", { class: "secao" }, el("h3", {}, "Defeitos no 3D"),
    el("div", { class: "dica" }, "Gire, escolha a animação e o ângulo, clique em \"Apontar defeito\" e depois no ponto do modelo. Cada marca guarda o ponto, a câmera, a animação, o instante e uma foto."));
  const lista = S.marcas3d ? S.marcas3d.lista : [];
  for (const mk of lista) {
    s.append(el("div", { class: "pedido" },
      el("div", { class: "meta" }, `#${mk.n} · ${mk.animacao || "pose"} t=${mk.tempo}s`),
      el("div", {}, mk.nota),
      el("img", { src: mk.foto, style: "cursor:pointer", onclick: () => irParaMarca(mk) }),
      el("div", { class: "linha-ctl" }, el("button", { onclick: () => irParaMarca(mk) }, "ver"),
        el("button", { onclick: () => { S.marcas3d.lista = lista.filter((x) => x !== mk); S.marcas3d.lista.forEach((x, k) => (x.n = k + 1)); abrirModelo(S.item); } }, "apagar"))));
  }
  const nota = el("textarea", { placeholder: "Comentário geral (opcional)" });
  async function enviar3d(modo) {
    if (!lista.length && !nota.value.trim()) return toast("Aponte ao menos um defeito.", true);
    const texto = [nota.value.trim(), ...lista.map((m) => `#${m.n} (${m.animacao || "pose"}, t=${m.tempo}s): ${m.nota}`)].filter(Boolean).join("\n");
    try {
      const r = await api("/api/pedido", { nota: texto, asset: S.item.caminho, quadro: null, modo,
        marcas: lista.map(({ foto, ...resto }) => resto), anotado: S.mv ? S.mv.toDataURL("image/png") : null,
        vistas: lista.map((m) => m.foto) });
      toast(`Pedido ${r.id} com ${lista.length} defeito(s) enviado`);
      S.marcas3d.lista = []; abrirModelo(S.item); atualizarPedidos();
    } catch (e) { toast(e.message, true); }
  }
  s.append(el("h3", { style: "margin-top:12px" }, "Mandar"), nota, el("div", { class: "linha-ctl" },
    el("button", { class: "prim", onclick: () => enviar3d("chat") }, `Mandar ${lista.length} defeito(s) ao chat`),
    el("button", { onclick: () => enviar3d("motor") }, "ao motor")));
  return s;
}

// ------------------------------------------------------------------ resultado final (todas as direções animando juntas)
const ORDEM_DIR = ["sul", "sudoeste", "oeste", "noroeste", "norte", "nordeste", "leste", "sudeste"];
function abrirResultado() {
  pararPlay(); pararResultado();
  const info = S.info;
  const folhas = info.itens.filter((i) => i.folha && /_/.test(i.nome));
  if (!folhas.length) return toast("Nenhuma folha nesta pasta.", true);
  const acoes = [...new Set(folhas.map((i) => i.nome.replace(/\.png$/, "").split("_")[0]))];
  S.item = { tipo: "resultado", nome: "Resultado final", caminho: info.caminho };
  const m = $("#principal"); m.innerHTML = "";
  const selA = el("select", {}, acoes.map((a) => el("option", { value: a }, a)));
  const zoomS = el("select", {}, [1, 2, 3, 4, 6].map((z) => el("option", { value: z, ...(z === 3 ? { selected: "" } : {}) }, z + "×")));
  const fundoS = el("select", {}, [["grama", "#68a057"], ["escuro", "#111"], ["claro", "#e6e2d8"], ["xadrez", ""]].map(([n, c]) => el("option", { value: c }, n)));
  const grade = el("div", { style: "display:flex;flex-wrap:wrap;gap:18px;padding:20px;align-content:flex-start" });
  m.append(el("div", { class: "inspetor" }, el("div", { class: "barra" },
    el("button", { class: "icone", onclick: () => { pararResultado(); S.item = null; desenharGrade(); desenharPainel(); } }, "←"),
    el("span", { class: "titulo" }, "Resultado final"), el("span", { class: "sep" }), "ação", selA, "zoom", zoomS, "fundo", fundoS),
    el("div", { class: "palco", style: "display:block" }, grade)));
  async function montar() {
    pararResultado(); grade.innerHTML = "";
    const z = +zoomS.value;
    const dirDe = (i) => i.nome.replace(/\.png$/, "").split("_").slice(1).join("_");
    const daAcao = folhas.filter((i) => i.nome.startsWith(selA.value + "_"))
      .sort((a, b) => ORDEM_DIR.indexOf(dirDe(a)) - ORDEM_DIR.indexOf(dirDe(b)));
    const tocadores = [];
    for (const it of daAcao) {
      const img = new Image(); img.src = arq(it.caminho, it.mtime); await img.decode().catch(() => {});
      const q0 = it.folha.quadros[0];
      const c = el("canvas", { width: q0.w * z, height: q0.h * z, style: "image-rendering:pixelated;border-radius:4px;" + (fundoS.value ? "background:" + fundoS.value : "") });
      if (!fundoS.value) c.className = "fundo-xadrez";
      grade.append(el("div", { style: "text-align:center" }, c, el("div", { class: "dica" }, dirDe(it))));
      tocadores.push({ it, img, c, k: 0, prox: 0 });
    }
    const passo = (agora) => {
      for (const t of tocadores) {
        if (agora >= t.prox) {
          const q = t.it.folha.quadros[t.k];
          const g = t.c.getContext("2d"); g.imageSmoothingEnabled = false; g.clearRect(0, 0, t.c.width, t.c.height);
          g.drawImage(t.img, q.x, q.y, q.w, q.h, 0, 0, q.w * z, q.h * z);
          t.prox = agora + (q.ms || 100); t.k = (t.k + 1) % t.it.folha.quadros.length;
        }
      }
      S.rafResultado = requestAnimationFrame(passo);
    };
    S.rafResultado = requestAnimationFrame(passo);
  }
  selA.onchange = zoomS.onchange = fundoS.onchange = montar;
  montar(); desenharPainel();
}
function pararResultado() { if (S.rafResultado) cancelAnimationFrame(S.rafResultado); S.rafResultado = null; }

// ------------------------------------------------------------------ riscar (marcas em pixels do sprite)
function ligarRisco(c) {
  const ponto = (ev) => { const b = c.getBoundingClientRect(); return [(ev.clientX - b.left) / S.zoom, (ev.clientY - b.top) / S.zoom]; };
  c.addEventListener("pointerdown", (ev) => {
    c.setPointerCapture(ev.pointerId);
    const p = ponto(ev);
    S.desenhando = { tipo: S.ferramenta, cor: S.cor, esp: S.espessura, quadro: S.quadro, pontos: [p, p] };
    if (S.ferramenta === "texto") {
      const txt = prompt("Texto da marca:");
      if (txt) S.marcas.push({ ...S.desenhando, texto: txt });
      S.desenhando = null; render();
    }
  });
  c.addEventListener("pointermove", (ev) => {
    if (!S.desenhando) return;
    const p = ponto(ev);
    if (S.desenhando.tipo === "caneta") S.desenhando.pontos.push(p); else S.desenhando.pontos[1] = p;
    render();
  });
  c.addEventListener("pointerup", () => { if (S.desenhando) { S.marcas.push(S.desenhando); S.desenhando = null; render(); } });
}
function desenharMarcas(g, z, todas) {
  g.clearRect(0, 0, g.canvas.width, g.canvas.height);
  const lista = S.marcas.filter((m) => todas || !S.item.folha || m.quadro === S.quadro);
  if (S.desenhando) lista.push(S.desenhando);
  for (const m of lista) {
    g.strokeStyle = g.fillStyle = m.cor; g.lineWidth = m.esp * Math.max(1, z / 4); g.lineCap = g.lineJoin = "round";
    const P = m.pontos.map(([x, y]) => [x * z, y * z]);
    g.beginPath();
    if (m.tipo === "caneta") { P.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.stroke(); }
    else if (m.tipo === "retangulo") { const [[a, b], [c, d]] = P; g.strokeRect(Math.min(a, c), Math.min(b, d), Math.abs(c - a), Math.abs(d - b)); }
    else if (m.tipo === "circulo") { const [[a, b], [c, d]] = P; g.ellipse((a + c) / 2, (b + d) / 2, Math.abs(c - a) / 2 + 1, Math.abs(d - b) / 2 + 1, 0, 0, Math.PI * 2); g.stroke(); }
    else if (m.tipo === "seta") {
      const [[a, b], [c, d]] = P; const ang = Math.atan2(d - b, c - a), k = 8 * Math.max(1, z / 4);
      g.moveTo(a, b); g.lineTo(c, d); g.lineTo(c - k * Math.cos(ang - .5), d - k * Math.sin(ang - .5));
      g.moveTo(c, d); g.lineTo(c - k * Math.cos(ang + .5), d - k * Math.sin(ang + .5)); g.stroke();
    } else if (m.tipo === "texto") { g.font = `${12 * Math.max(1, z / 4)}px system-ui`; g.fillText(m.texto, P[0][0], P[0][1]); }
  }
}
function imagemAnotada() {
  const r = quadroRect(S.quadro), z = Math.max(4, S.zoom);
  const c = el("canvas", { width: r.w * z, height: r.h * z }); const g = c.getContext("2d"); g.imageSmoothingEnabled = false;
  g.fillStyle = "#68a057"; g.fillRect(0, 0, c.width, c.height);
  g.drawImage(S.img, r.x, r.y, r.w, r.h, 0, 0, r.w * z, r.h * z);
  const cr = el("canvas", { width: c.width, height: c.height }); desenharMarcas(cr.getContext("2d"), z);
  g.drawImage(cr, 0, 0);
  const o = el("canvas", { width: r.w, height: r.h }); o.getContext("2d").drawImage(S.img, r.x, r.y, r.w, r.h, 0, 0, r.w, r.h);
  return { anotado: c.toDataURL("image/png"), original: o.toDataURL("image/png"), zoom: z };
}

// ------------------------------------------------------------------ painel lateral (abas)
const ABAS = [["riscar", "Riscar e pedir"], ["aprovar", "Aprovar"], ["paleta", "Paleta"], ["praticas", "Boas práticas"], ["pedidos", "Pedidos"], ["tarefas", "Tarefas"]];
function desenharPainel() {
  const p = $("#painel"); p.classList.remove("escondido"); p.innerHTML = "";
  const abas = el("div", { class: "abas" });
  for (const [id, nome] of ABAS) {
    if (id === "paleta" && !(S.info && S.info.paleta)) continue;
    abas.append(el("button", { class: S.aba === id ? "on" : "", onclick: () => { S.aba = id; desenharPainel(); } }, nome));
  }
  p.append(abas);
  const f = { riscar: abaRiscar, aprovar: abaAprovar, paleta: abaPaleta, praticas: abaPraticas, pedidos: abaPedidos, tarefas: abaTarefas }[S.aba] || abaRiscar;
  p.append(f());
}
function abaRiscar() {
  if (S.item && S.item.tipo === "modelo") return aba3d();
  const s = el("div", { class: "secao" });
  if (!S.item || S.item.tipo === "resultado") return el("div", { class: "secao dica" }, "Abra uma imagem para riscar e pedir mudanças.");
  const ferr = el("div", { class: "linha-ctl ferr" });
  for (const [id, n] of [["caneta", "✎ caneta"], ["retangulo", "▭ caixa"], ["circulo", "◯ círculo"], ["seta", "➚ seta"], ["texto", "T texto"]])
    ferr.append(el("button", { class: S.ferramenta === id ? "on" : "", onclick: () => { S.ferramenta = id; desenharPainel(); } }, n));
  const cor = el("input", { type: "color", value: S.cor }); cor.oninput = (e) => (S.cor = e.target.value);
  const esp = el("select", {}, [1, 2, 3, 5].map((v) => el("option", { value: v, ...(v === S.espessura ? { selected: "" } : {}) }, v + " px")));
  esp.onchange = (e) => (S.espessura = +e.target.value);
  const nota = el("textarea", { placeholder: "O que mudar? Ex.: 'a perna de trás some no quadro 3', 'esse azul mais escuro', 'chifre mais curvo'" });
  const enviar = async (modo) => {
    if (!nota.value.trim() && !S.marcas.length) return toast("Escreva ou risque algo.", true);
    const img = imagemAnotada();
    const marcas = S.marcas.map((m) => ({ tipo: m.tipo, quadro: m.quadro, cor: m.cor, texto: m.texto, pontos: m.pontos.map(([x, y]) => [Math.round(x * 10) / 10, Math.round(y * 10) / 10]) }));
    try {
      const r = await api("/api/pedido", { nota: nota.value, asset: S.item.caminho, quadro: S.quadro, marcas, modo, ...img });
      toast(modo === "motor" ? `Pedido ${r.id} enviado ao motor` : `Pedido ${r.id} na caixa do chat`);
      S.marcas = []; nota.value = ""; render(); atualizarPedidos();
    } catch (e) { toast(e.message, true); }
  };
  s.append(el("h3", {}, "Riscar na imagem"), ferr,
    el("div", { class: "linha-ctl" }, "cor", cor, "traço", esp,
      el("button", { onclick: () => { S.marcas.pop(); render(); } }, "desfazer"),
      el("button", { onclick: () => { S.marcas = []; render(); } }, "limpar")),
    el("div", { class: "dica" }, "As marcas ficam no quadro atual e vão em coordenadas de pixel do sprite."),
    el("h3", { style: "margin-top:14px" }, "Pedido"), nota,
    el("div", { class: "linha-ctl" },
      el("button", { class: "prim", onclick: () => enviar("chat") }, "Mandar ao chat"),
      el("button", { onclick: () => enviar("motor"), title: "Roda o Claude sem terminal agora" }, "Mandar ao motor")),
    el("div", { class: "dica" }, "No chat, diga 'veja os pedidos do estúdio' (ou deixe o hook ligado): o agente lê com horys_estudio_pedidos."));
  return s;
}
function abaAprovar() {
  const s = el("div", { class: "secao" });
  if (!S.item) return el("div", { class: "secao dica" }, "Abra uma imagem para aprovar ou reprovar.");
  const com = el("textarea", { placeholder: "Suas palavras (vão para a régua e para o revisor)" });
  const v = async (veredito) => {
    try {
      await api("/api/veredito", { caminho: S.item.caminho, veredito, comentario: com.value });
      toast(veredito === "aprovado" ? "Aprovado e copiado para os aprovados" : "Reprovação registrada");
      S.item.estado = veredito; await abrirPasta(S.pasta);
    } catch (e) { toast(e.message, true); }
  };
  s.append(el("h3", {}, S.item.nome), el("div", { class: "dica" }, "Estado: " + (S.item.estado || "sem veredito")), com,
    el("div", { class: "linha-ctl" }, el("button", { class: "ok", onclick: () => v("aprovado") }, "Aprovar"),
      el("button", { class: "ruim", onclick: () => v("reprovado") }, "Reprovar")),
    el("div", { class: "dica" }, S.item.tipo === "modelo"
      ? "Aprovar o 3D libera a pixel art: o render em pixel recusa modelo não aprovado. Se o modelo mudar, a aprovação cai."
      : "Aprovar grava a trava (sha256) e copia para a pasta de aprovados. Se o arquivo mudar, a aprovação cai."));
  return s;
}
function abaPaleta() {
  const s = el("div", { class: "secao" });
  const pal = JSON.parse(JSON.stringify(S.info.paleta.dados));
  s.append(el("h3", {}, "Paleta do render"), el("div", { class: "dica" }, "Troque as cores e aplique: refaz folhas, GIFs e .aseprite sem rodar o Blender."));
  for (const [nome, f] of Object.entries(pal.familias)) {
    const linha = el("div", { class: "fam" }, el("div", { class: "nm" }, nome + (f.tipo === "emissivo" ? " (emissivo)" : "")));
    f.rampa.forEach((h, i) => {
      const inp = el("input", { type: "color", value: h }); inp.oninput = (e) => (f.rampa[i] = e.target.value);
      linha.append(el("label", { class: "sw" }, inp, el("span", {}, h)));
    });
    s.append(linha);
  }
  const tinta = el("input", { type: "color", value: pal.tinta }); tinta.oninput = (e) => (pal.tinta = e.target.value);
  s.append(el("div", { class: "fam" }, el("div", { class: "nm" }, "tinta (contorno)"), el("label", { class: "sw" }, tinta, el("span", {}, pal.tinta))));
  s.append(el("div", { class: "linha-ctl" }, el("button", { class: "prim", onclick: async () => {
    try { const j = await api("/api/recolor", { saida: S.info.saida_blender, paleta: pal, config: S.info.config_blender }); toast("Recolor rodando (" + j.job + ")"); atualizarJobs(); }
    catch (e) { toast(e.message, true); }
  } }, "Aplicar recolor")));
  return s;
}
function abaPraticas() {
  const s = el("div", { class: "secao" });
  if (!S.item) return el("div", { class: "secao dica" }, "Abra uma imagem ou folha para checar as boas práticas (docs/boas-praticas.md).");
  s.append(el("h3", {}, "Boas práticas"), el("button", { class: "prim", onclick: async () => {
    try { const j = await api("/api/praticas", { caminho: S.item.caminho }); toast("Checando (" + j.job + ")"); S.praticasJob = j.job; atualizarJobs(); }
    catch (e) { toast(e.message, true); }
  } }, "Checar esta imagem"));
  const job = S.jobs.find((j) => j.id === S.praticasJob);
  if (job && job.estado === "ok") {
    const res = job.resultado.resultados;
    const lista = Array.isArray(res) ? res : (res && res.resultados) || Object.values(res || {});
    for (const r of lista) {
      const c = r.passa === false ? "falha" : r.passa ? "passa" : "";
      const med = typeof r.medida === "object" ? JSON.stringify(r.medida) : (r.medida ?? "");
      s.append(el("div", { class: "res " + c }, `${r.passa === false ? "✗" : r.passa ? "✓" : "·"} ${r.id} ${r.titulo || ""} — ${med}${r.limite !== undefined && r.limite !== null ? " (limite " + JSON.stringify(r.limite) + ")" : ""}`));
    }
    if (job.resultado.overlay) s.append(el("img", { src: arq(job.resultado.overlay, Date.now()), style: "max-width:100%;image-rendering:pixelated;margin-top:8px" }));
  } else if (job && job.estado === "erro") s.append(el("div", { class: "res falha" }, job.erro));
  return s;
}
function abaPedidos() {
  const s = el("div", { class: "secao" }, el("h3", {}, "Pedidos ao chat"));
  if (!S.pedidos.length) s.append(el("div", { class: "dica" }, "Nenhum pedido ainda."));
  for (const p of S.pedidos.slice(0, 40)) {
    const caixa = el("div", { class: "pedido" },
      el("div", { class: "meta" }, `${p.id} · `, el("span", { class: "e-" + p.estado }, p.estado), ` · ${(p.asset || "").split(/[\\/]/).slice(-2).join("/")}`),
      el("div", {}, p.nota || "(só riscos)"),
      p.anotado ? el("img", { src: arq(p.anotado), loading: "lazy" }) : null,
      ...(p.vistas || []).map((v) => el("img", { src: arq(v), loading: "lazy" })),
      ...(p.respostas || []).map((r) => el("div", { class: "resp" }, `${r.quando} · ${r.estado}\n${r.texto}`,
        r.imagem ? el("img", { src: arq(r.imagem), loading: "lazy" }) : null)));
    if (p.estado === "pendente") caixa.append(el("div", { class: "linha-ctl" }, el("button", { onclick: async () => {
      await api("/api/pedido/estado", { id: p.id, estado: "descartado", texto: "descartado no Estúdio" }); atualizarPedidos();
    } }, "descartar")));
    s.append(caixa);
  }
  return s;
}
function abaTarefas() {
  const s = el("div", { class: "secao" }, el("h3", {}, "Tarefas"));
  if (!S.jobs.length) s.append(el("div", { class: "dica" }, "Nada rodando."));
  for (const j of S.jobs) s.append(el("div", { class: "job" }, `${j.nome} · ${j.estado}`,
    j.erro ? el("div", { class: "res falha" }, j.erro) : null,
    j.resultado && j.resultado.prancha ? el("div", { class: "dica" }, j.resultado.prancha) : null));
  return s;
}

// ------------------------------------------------------------------ ações
async function blender(previa) {
  const info = S.info;
  const saida = previa ? info.caminho.replace(/[\\/][^\\/]+$/, "") + "/previa" : info.caminho;
  if (!previa && !confirm("Render completo em " + saida + "? (a paleta precisa estar aprovada)")) return;
  try { const j = await api("/api/blender", { config: info.config_blender, saida, previa }); toast("Blender rodando (" + j.job + ")"); atualizarJobs(); }
  catch (e) { toast(e.message, true); }
}
async function atualizarPedidos() {
  try {
    const j = await api("/api/pedidos");
    S.pedidos = j.pedidos;
    const n = S.pedidos.filter((p) => p.estado === "pendente" || p.estado === "em_andamento").length;
    const b = $("#n-pedidos"); b.textContent = n; b.classList.toggle("quente", n > 0);
    if (S.aba === "pedidos") desenharPainel();
  } catch (e) { $("#status").textContent = "desconectado"; }
}
async function atualizarJobs() {
  try {
    const j = await api("/api/jobs");
    S.jobs = j.jobs;
    $("#n-jobs").textContent = S.jobs.filter((x) => x.estado === "rodando").length;
    for (const x of S.jobs) if (x.estado !== "rodando" && !S.jobsVistos.has(x.id)) {
      S.jobsVistos.add(x.id);
      if (Date.now() / 1000 - (x.fim || 0) < 10) {
        toast(`${x.nome}: ${x.estado}` + (x.erro ? " — " + x.erro : ""), x.estado === "erro");
        if (S.pasta && !S.item) abrirPasta(S.pasta);
        if (S.aba === "praticas" || S.aba === "tarefas") desenharPainel();
      }
    }
  } catch (e) { /* tenta de novo */ }
}

// ------------------------------------------------------------------ início
$("#busca").addEventListener("input", () => { desenharArvore(); if (S.info && !S.item) desenharGrade(); });
$("#bt-atualizar").onclick = carregarArvore;
$("#bt-pedidos").onclick = () => { S.aba = "pedidos"; desenharPainel(); };
$("#bt-jobs").onclick = () => { S.aba = "tarefas"; desenharPainel(); };
$("#bt-aprovados").onclick = async () => { const j = await api("/api/aprovados"); abrirPasta(j.pasta); };
document.addEventListener("keydown", (ev) => {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
  if (ev.key === " ") { ev.preventDefault(); alternarPlay(); }
  else if (ev.key === "ArrowLeft") passo(-1);
  else if (ev.key === "ArrowRight") passo(1);
  else if (ev.key === "Escape" && S.apontando) { S.apontando = false; if (S.item && S.item.tipo === "modelo") abrirModelo(S.item); }
  else if (ev.key === "Escape" && S.item) { pararPlay(); S.item = null; desenharGrade(); desenharPainel(); }
  else if (ev.key === "+" || ev.key === "=") { S.zoom = Math.min(16, S.zoom + 1); const z = $("[data-ctl=zoom]"); if (z) z.value = String(S.zoom); render(); }
  else if (ev.key === "-") { S.zoom = Math.max(1, S.zoom - 1); render(); }
  else if (ev.key.toLowerCase() === "z" && (ev.ctrlKey || ev.metaKey)) { S.marcas.pop(); render(); }
});
carregarArvore().catch((e) => { $("#status").textContent = "erro: " + e.message; });
atualizarPedidos(); atualizarJobs();
setInterval(() => { atualizarPedidos(); atualizarJobs(); }, 3000);
