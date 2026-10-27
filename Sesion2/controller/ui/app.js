/*
 * Consola visual del SDN Controller (capa VISTA).
 * Regla de diseño: este archivo NO calcula rutas ni costos. Todo lo que decide
 * la red lo responde la API REST del Controller; aquí solo se dibuja.
 */
(() => {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const VIEW_W = 900, VIEW_H = 560, PAD = 70, NODE_R = 26;
  const METRIC_NAMES = { delay: "Retardo", bandwidth: "Ancho de banda", loss: "Pérdida" };
  const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const $ = (id) => document.getElementById(id);
  const ui = {
    graph: $("graph"), links: $("links"), nodes: $("nodes"), overlay: $("overlay"),
    empty: $("canvas-empty"), emptyMsg: $("canvas-empty-msg"), hint: $("hint"),
    ctrlHealth: $("ctrl-health"), routerHealth: $("router-health"), version: $("topo-version"),
    src: $("src"), dst: $("dst"), swap: $("swap"), calc: $("calc"), clear: $("clear"),
    routeResult: $("route-result"), routerUrl: $("router-url"), send: $("send"),
    packetResult: $("packet-result"), linkList: $("link-list"), log: $("log"), clearLog: $("clear-log"),
  };

  const state = {
    topology: null,          // respuesta de GET /topology
    positions: new Map(),    // nodo -> {x, y} (solo dibujo)
    layoutKey: "",
    metric: "delay",
    src: null,
    dst: null,
    route: null,             // última respuesta 200 de GET /route
    ghostPath: null,         // ruta anterior, cuando cambió por un fallo/restablecimiento
    unreachable: false,
    selectedLink: null,      // "A|B"
    activeHop: null,         // "A|B" mientras se anima el paquete
    packetCounter: 0,
    animating: false,
  };

  // ------------------------------------------------------------------ util
  const linkKey = (a, b) => [a, b].sort().join("|");
  const el = (tag, attrs = {}, parent) => {
    const node = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  };
  const h = (tag, props = {}, ...children) => {
    const node = document.createElement(tag);
    Object.assign(node, props);
    for (const child of children) node.append(child);
    return node;
  };
  const fmt = (n, digits = 4) => Number(n.toFixed(digits)).toString();

  async function api(base, path, options = {}) {
    try {
      const response = await fetch(base + path, {
        headers: { "content-type": "application/json" },
        ...options,
      });
      let body = null;
      try { body = await response.json(); } catch (_) { /* sin cuerpo JSON */ }
      return { ok: response.ok, status: response.status, body, network: false };
    } catch (error) {
      return { ok: false, status: 0, body: null, network: true, error };
    }
  }
  const errorCode = (res) => (res.body && res.body.error && res.body.error.code) || (res.network ? "SIN_CONEXION" : `HTTP_${res.status}`);
  const errorMessage = (res) => (res.body && res.body.error && res.body.error.message) || (res.network ? "No hubo respuesta" : "");

  // ------------------------------------------------------------- registro
  function log(kind, html) {
    const time = new Date().toLocaleTimeString("es-CO", { hour12: false });
    const item = h("li", {}, h("time", { textContent: time }));
    const text = h("span", { className: `e-${kind}` });
    text.innerHTML = html;
    item.append(text);
    ui.log.prepend(item);
    while (ui.log.children.length > 40) ui.log.lastChild.remove();
  }
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  // --------------------------------------------------------------- layout
  // Distribución por fuerzas (Fruchterman-Reingold) determinista: solo afecta al dibujo.
  function computeLayout(topology) {
    // Los routers aislados van en una fila abajo; el resto ocupa todo el lienzo.
    const connected = new Set();
    topology.links.forEach((l) => { connected.add(l.node_a); connected.add(l.node_b); });
    const isolated = topology.nodes.filter((id) => !connected.has(id));
    const main = topology.nodes.filter((id) => connected.has(id));
    const bottom = isolated.length ? 95 : 0;
    const pos = forceLayout(main, topology.links, VIEW_H - bottom);
    isolated.forEach((id, i) => {
      const step = Math.min(110, (VIEW_W - 2 * PAD) / Math.max(isolated.length, 1));
      pos.set(id, { x: PAD + step * (i + 0.5), y: VIEW_H - 48 });
    });
    return pos;
  }

  function forceLayout(nodes, links, height) {
    const n = nodes.length;
    const pos = new Map();
    const cx = VIEW_W / 2, cy = height / 2;
    nodes.forEach((id, i) => {
      const angle = (2 * Math.PI * i) / Math.max(n, 1) - Math.PI / 2;
      pos.set(id, { x: cx + 200 * Math.cos(angle), y: cy + 160 * Math.sin(angle) });
    });
    if (n <= 1) return fit(pos, height);
    const area = (VIEW_W - 2 * PAD) * (height - 2 * PAD);
    const k = 0.9 * Math.sqrt(area / n);
    let temperature = VIEW_W / 8;
    for (let iter = 0; iter < 400; iter++) {
      const disp = new Map(nodes.map((id) => [id, { x: 0, y: 0 }]));
      for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
          const a = pos.get(nodes[i]), b = pos.get(nodes[j]);
          let dx = a.x - b.x, dy = a.y - b.y;
          const dist = Math.max(Math.hypot(dx, dy), 0.01);
          const force = (k * k) / dist;
          dx /= dist; dy /= dist;
          disp.get(nodes[i]).x += dx * force; disp.get(nodes[i]).y += dy * force;
          disp.get(nodes[j]).x -= dx * force; disp.get(nodes[j]).y -= dy * force;
        }
      }
      for (const link of links) {
        const a = pos.get(link.node_a), b = pos.get(link.node_b);
        if (!a || !b) continue;
        let dx = a.x - b.x, dy = a.y - b.y;
        const dist = Math.max(Math.hypot(dx, dy), 0.01);
        const force = (dist * dist) / k;
        dx /= dist; dy /= dist;
        disp.get(link.node_a).x -= dx * force; disp.get(link.node_a).y -= dy * force;
        disp.get(link.node_b).x += dx * force; disp.get(link.node_b).y += dy * force;
      }
      for (const id of nodes) {
        const p = pos.get(id), d = disp.get(id);
        d.x += (cx - p.x) * 0.02 * k / 50; // gravedad suave hacia el centro
        d.y += (cy - p.y) * 0.02 * k / 50;
        const len = Math.max(Math.hypot(d.x, d.y), 0.01);
        p.x += (d.x / len) * Math.min(len, temperature);
        p.y += (d.y / len) * Math.min(len, temperature);
      }
      temperature *= 0.985;
    }
    return fit(pos, height);
  }

  function fit(pos, height) {
    if (!pos.size) return pos;
    const xs = [...pos.values()].map((p) => p.x), ys = [...pos.values()].map((p) => p.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const w = Math.max(maxX - minX, 1), hgt = Math.max(maxY - minY, 1);
    const scale = Math.min((VIEW_W - 2 * PAD) / w, (height - 2 * PAD) / hgt, 2.5);
    const offX = (VIEW_W - w * scale) / 2, offY = (height - hgt * scale) / 2 + 10;
    for (const p of pos.values()) {
      p.x = offX + (p.x - minX) * scale;
      p.y = offY + (p.y - minY) * scale;
    }
    return pos;
  }

  // ------------------------------------------------------------- dibujo
  function routeEdges(path) {
    const set = new Set();
    if (!path) return set;
    for (let i = 0; i + 1 < path.length; i++) set.add(linkKey(path[i], path[i + 1]));
    return set;
  }

  function linkLabel(link) {
    if (state.metric === "delay") return `${fmt(link.delay_ms, 2)} ms`;
    if (state.metric === "bandwidth") return `${fmt(link.bandwidth_mbps, 2)} Mbps`;
    return `${fmt(link.loss_prob * 100, 2)} %`;
  }

  function draw() {
    ui.links.replaceChildren();
    ui.nodes.replaceChildren();
    const topo = state.topology;
    if (!topo) return;

    const pathEdges = routeEdges(state.route && state.route.path);
    const ghostEdges = routeEdges(state.ghostPath);
    const pathIndex = new Map((state.route ? state.route.path : []).map((id, i) => [id, i]));
    const degree = new Map(topo.nodes.map((id) => [id, 0]));
    topo.links.forEach((l) => { degree.set(l.node_a, degree.get(l.node_a) + 1); degree.set(l.node_b, degree.get(l.node_b) + 1); });

    for (const link of topo.links) {
      const a = state.positions.get(link.node_a), b = state.positions.get(link.node_b);
      if (!a || !b) continue;
      const key = linkKey(link.node_a, link.node_b);
      const classes = ["link"];
      if (link.status === "failed") classes.push("failed");
      if (pathEdges.has(key)) classes.push("on-path");
      else if (ghostEdges.has(key)) classes.push("ghost");
      if (state.selectedLink === key) classes.push("selected");
      if (state.activeHop === key) classes.push("active-hop");
      const g = el("g", { class: classes.join(" "), "data-key": key }, ui.links);
      // dirección del dibujo: si es parte de la ruta, el flujo va de origen a destino
      let [p, q] = [a, b];
      if (pathEdges.has(key) && pathIndex.get(link.node_a) > pathIndex.get(link.node_b)) [p, q] = [b, a];
      el("line", { class: "wire", x1: p.x, y1: p.y, x2: q.x, y2: q.y }, g);
      el("line", { class: "hit", x1: a.x, y1: a.y, x2: b.x, y2: b.y }, g);
      const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      const label = el("g", { class: "label", transform: `translate(${mx},${my})` }, g);
      const text = link.status === "failed" ? "caído" : linkLabel(link);
      const width = 12 + text.length * 7.2;
      el("rect", { x: -width / 2, y: -11, width, height: 22, rx: 11 }, label);
      el("text", { "text-anchor": "middle", "dominant-baseline": "central" }, label).textContent = text;
      el("title", {}, g).textContent = `${link.node_a} — ${link.node_b}\nRetardo ${link.delay_ms} ms · Ancho de banda ${link.bandwidth_mbps} Mbps · Pérdida ${fmt(link.loss_prob * 100, 2)} %\nEstado: ${link.status === "failed" ? "caído" : "activo"}`;
      g.addEventListener("click", () => selectLink(key));
    }

    for (const id of topo.nodes) {
      const p = state.positions.get(id);
      const classes = ["node"];
      if (degree.get(id) === 0) classes.push("isolated");
      if (pathIndex.has(id)) classes.push("on-path");
      if (id === state.src) classes.push("origin");
      if (id === state.dst) classes.push(state.unreachable ? "unreachable" : "dest");
      const g = el("g", { class: classes.join(" "), transform: `translate(${p.x},${p.y})`, "data-id": id, tabindex: 0, role: "button", "aria-label": `Router ${id}` }, ui.nodes);
      if (id === state.src) el("circle", { class: "pulse", r: NODE_R }, g);
      el("circle", { class: "body", r: NODE_R }, g);
      el("text", { class: "name" }, g).textContent = id;
      if (degree.get(id) === 0) el("text", { class: "caption", y: NODE_R + 16 }, g).textContent = "aislado";
      if (pathIndex.has(id) && id !== state.src && id !== state.dst) {
        const badge = el("g", { class: "badge", transform: `translate(${NODE_R - 4},${-NODE_R + 4})` }, g);
        el("circle", { r: 10 }, badge);
        el("text", {}, badge).textContent = pathIndex.get(id);
      }
      if (id === state.src) drawMarker(g, "Tú", "var(--origin)");
      if (id === state.dst) drawMarker(g, state.unreachable ? "✕" : "Destino", state.unreachable ? "var(--danger)" : "var(--dest)");
      attachNodeEvents(g, id);
    }
  }

  function drawMarker(group, text, color) {
    const width = Math.max(30, 10 + text.length * 7);
    const m = el("g", { class: "marker", transform: `translate(0,${-NODE_R - 22})` }, group);
    el("path", { d: `M${-width / 2},-11 h${width} v20 h${-(width / 2 - 6)} l-6,7 l-6,-7 h${-(width / 2 - 6)} z`, fill: color }, m);
    el("text", { y: 0, "dominant-baseline": "central" }, m).textContent = text;
  }

  // ------------------------------------------------------- interacción
  function svgPoint(evt) {
    const pt = ui.graph.createSVGPoint();
    pt.x = evt.clientX; pt.y = evt.clientY;
    return pt.matrixTransform(ui.graph.getScreenCTM().inverse());
  }

  function attachNodeEvents(group, id) {
    let start = null, moved = false;
    group.addEventListener("pointerdown", (evt) => {
      start = svgPoint(evt); moved = false;
      group.setPointerCapture(evt.pointerId);
    });
    group.addEventListener("pointermove", (evt) => {
      if (!start) return;
      const p = svgPoint(evt);
      if (!moved && Math.hypot(p.x - start.x, p.y - start.y) < 4) return;
      moved = true;
      state.positions.set(id, { x: Math.min(Math.max(p.x, 30), VIEW_W - 30), y: Math.min(Math.max(p.y, 40), VIEW_H - 30) });
      draw();
    });
    group.addEventListener("pointerup", () => {
      if (start && !moved) onNodeClick(id);
      start = null;
    });
    group.addEventListener("keydown", (evt) => { if (evt.key === "Enter" || evt.key === " ") { evt.preventDefault(); onNodeClick(id); } });
  }

  function onNodeClick(id) {
    if (!state.src || (state.src && state.dst)) {
      setEndpoints(id, null);
      log("info", `Te ubicaste en el router <b>${esc(id)}</b> (origen).`);
    } else if (id === state.src) {
      setEndpoints(null, null);
    } else {
      setEndpoints(state.src, id);
      calculateRoute("selección");
    }
  }

  function setEndpoints(src, dst) {
    state.src = src; state.dst = dst;
    state.route = null; state.ghostPath = null; state.unreachable = false;
    ui.src.value = src || ""; ui.dst.value = dst || "";
    updateHint();
    if (!src || !dst) renderRouteIdle();
    draw();
  }

  function updateHint() {
    if (!state.src) ui.hint.textContent = "Haz clic en un router para ubicarte en él (origen). Luego haz clic en otro para elegir el destino.";
    else if (!state.dst) ui.hint.textContent = `Estás en ${state.src}. Haz clic en el router de destino.`;
    else ui.hint.textContent = `Ruta ${state.src} → ${state.dst} con métrica «${METRIC_NAMES[state.metric]}». Haz clic en un enlace para fallarlo o restablecerlo, o arrastra los routers para reacomodar el dibujo.`;
  }

  function selectLink(key) {
    state.selectedLink = state.selectedLink === key ? null : key;
    renderLinkList();
    draw();
    const item = ui.linkList.querySelector(`[data-key="${key}"]`);
    if (item && state.selectedLink) item.scrollIntoView({ block: "nearest", behavior: REDUCED_MOTION ? "auto" : "smooth" });
  }

  // ---------------------------------------------------------- topología
  async function loadTopology({ silent = false } = {}) {
    const res = await api("", "/topology");
    if (!res.ok) {
      state.topology = null;
      ui.empty.hidden = false;
      ui.emptyMsg.textContent = `${errorCode(res)}: ${errorMessage(res)}`;
      draw();
      if (!silent) log("err", `No se pudo leer la topología (<code>${esc(errorCode(res))}</code>).`);
      return false;
    }
    ui.empty.hidden = true;
    const previous = state.topology;
    state.topology = res.body;
    const key = state.topology.nodes.join(",") + "/" + state.topology.links.map((l) => linkKey(l.node_a, l.node_b)).join(",");
    if (key !== state.layoutKey) {
      state.positions = computeLayout(state.topology);
      state.layoutKey = key;
    }
    if (!previous || previous.topology_version !== state.topology.topology_version) bumpVersion(state.topology.topology_version);
    fillSelects();
    renderLinkList();
    draw();
    if (!silent) log("info", `Topología cargada: ${state.topology.nodes.length} routers, ${state.topology.links.length} enlaces (versión ${state.topology.topology_version}).`);
    return true;
  }

  function bumpVersion(version) {
    ui.version.textContent = `versión ${version}`;
    ui.version.classList.remove("bump");
    void ui.version.offsetWidth;
    ui.version.classList.add("bump");
  }

  function fillSelects() {
    for (const select of [ui.src, ui.dst]) {
      const current = select === ui.src ? state.src : state.dst;
      select.replaceChildren(h("option", { value: "", textContent: "—" }), ...state.topology.nodes.map((id) => h("option", { value: id, textContent: id })));
      select.value = current || "";
    }
  }

  function renderLinkList() {
    if (!state.topology) { ui.linkList.replaceChildren(); return; }
    const items = state.topology.links.map((link) => {
      const key = linkKey(link.node_a, link.node_b);
      const failed = link.status === "failed";
      const button = h("button", {
        type: "button",
        className: failed ? "restore" : "danger",
        textContent: failed ? "Restablecer" : "Fallar",
      });
      button.addEventListener("click", (evt) => { evt.stopPropagation(); changeLink(link, failed ? "restore" : "fail"); });
      const li = h("li", { className: [failed ? "failed" : "", state.selectedLink === key ? "selected" : ""].join(" ").trim() },
        h("span", { className: "name", textContent: `${link.node_a}–${link.node_b}` }),
        h("span", { className: "attrs", textContent: `${fmt(link.delay_ms, 2)}\u00a0ms · ${fmt(link.bandwidth_mbps, 2)}\u00a0Mbps · ${fmt(link.loss_prob * 100, 2)}\u00a0%` }),
        h("span", { className: "st", textContent: failed ? "caído" : "activo" }),
        button);
      li.dataset.key = key;
      li.addEventListener("click", () => selectLink(key));
      return li;
    });
    ui.linkList.replaceChildren(...items);
  }

  // --------------------------------------------------------------- rutas
  function renderRouteIdle() {
    ui.routeResult.className = "result";
    ui.routeResult.replaceChildren(h("p", { className: "muted", textContent: state.src ? `Origen: ${state.src}. Elige el destino.` : "Elige un origen y un destino." }));
  }

  function pathChips(path) {
    const box = h("div", { className: "path" });
    path.forEach((id, i) => {
      if (i > 0) box.append(h("span", { className: "arrow", textContent: "→" }));
      box.append(h("span", { className: "chip" + (i === 0 ? " o" : i === path.length - 1 ? " d" : ""), textContent: id }));
    });
    return box;
  }

  async function calculateRoute(reason) {
    if (!state.src || !state.dst) { renderRouteIdle(); return; }
    const params = new URLSearchParams({ src: state.src, dst: state.dst, metric: state.metric });
    const res = await api("", `/route?${params}`);
    const before = state.route;
    if (res.ok) {
      state.route = res.body;
      state.unreachable = false;
      const changed = before && reason === "enlace" && before.path.join() !== res.body.path.join();
      state.ghostPath = changed ? before.path : null;
      renderRouteOk(res.body, changed ? before : null);
      log("ok", `<code>GET /route</code> ${esc(state.src)}→${esc(state.dst)} (${METRIC_NAMES[state.metric]}): <b>${res.body.path.map(esc).join(" → ")}</b>, costo ${fmt(res.body.total_cost)}.`);
    } else {
      state.route = null;
      state.ghostPath = before && reason === "enlace" ? before.path : null;
      state.unreachable = errorCode(res) === "ROUTE_NOT_FOUND";
      renderRouteError(res, before && reason === "enlace" ? before : null);
      log("err", `<code>GET /route</code> ${esc(state.src)}→${esc(state.dst)}: <b>${esc(errorCode(res))}</b>.`);
    }
    updateHint();
    draw();
  }

  function routeDetails(route) {
    const dl = h("dl", { className: "kv" });
    const rows = [
      ["Métrica", METRIC_NAMES[route.metric]],
      ["Costo total", fmt(route.total_cost)],
      ["Costo por salto", route.hop_costs.length ? route.hop_costs.map((c) => fmt(c)).join(" + ") : "—"],
      ["Saltos", String(route.path.length - 1)],
      ["Versión topología", String(route.topology_version)],
    ];
    for (const [k, v] of rows) dl.append(h("dt", { textContent: k }), h("dd", { textContent: v }));
    return dl;
  }

  function renderRouteOk(route, previous) {
    ui.routeResult.className = "result ok";
    const children = [h("p", { className: "title", textContent: "Ruta seleccionada por el Controller" }), pathChips(route.path), routeDetails(route)];
    if (previous) {
      children.push(h("div", { className: "change", textContent: `La ruta cambió: antes ${previous.path.join(" → ")} (costo ${fmt(previous.total_cost)}), ahora ${route.path.join(" → ")} (costo ${fmt(route.total_cost)}). La ruta anterior se ve en naranja.` }));
    }
    ui.routeResult.replaceChildren(...children);
  }

  function renderRouteError(res, previous) {
    ui.routeResult.className = "result err";
    const code = errorCode(res);
    const explanations = {
      ROUTE_NOT_FOUND: `No hay ningún camino activo entre ${state.src} y ${state.dst}. Un paquete enviado por el Router quedaría UNREACHABLE.`,
      NODE_NOT_FOUND: "El router no existe en la topología.",
      TOPOLOGY_UNAVAILABLE: "El Controller no tiene topología cargada.",
      SIN_CONEXION: "El Controller no respondió.",
    };
    const children = [
      h("p", { className: "title err-title", textContent: `${res.status || ""} ${code}`.trim() }),
      h("p", { className: "muted", textContent: explanations[code] || errorMessage(res) }),
    ];
    if (previous) children.push(h("div", { className: "change", textContent: `Antes la ruta era ${previous.path.join(" → ")}; ese camino ya no está disponible (en naranja).` }));
    ui.routeResult.replaceChildren(...children);
  }

  // -------------------------------------------------------------- enlaces
  async function changeLink(link, action) {
    const res = await api("", `/links/${action}`, {
      method: "POST",
      body: JSON.stringify({ node_a: link.node_a, node_b: link.node_b }),
    });
    const name = `${link.node_a}–${link.node_b}`;
    if (res.ok) {
      log("ok", `<code>POST /links/${action}</code> ${esc(name)} → ${action === "fail" ? "caído" : "activo"}, versión ${res.body.topology_version}.`);
    } else {
      log("err", `<code>POST /links/${action}</code> ${esc(name)}: <b>${esc(errorCode(res))}</b> ${esc(errorMessage(res))}`);
    }
    state.selectedLink = linkKey(link.node_a, link.node_b);
    await loadTopology({ silent: true });
    if (state.src && state.dst) await calculateRoute("enlace");
  }

  // -------------------------------------------------------------- paquete
  function routerBase() {
    return ui.routerUrl.value.trim().replace(/\/+$/, "");
  }

  async function sendPacket() {
    if (state.animating) return;
    if (!state.src || !state.dst) {
      ui.packetResult.className = "result err";
      ui.packetResult.replaceChildren(h("p", { className: "muted", textContent: "Primero elige origen y destino en el dibujo." }));
      return;
    }
    const packetId = `ui-${Date.now().toString(36)}-${++state.packetCounter}`;
    const payload = { packet_id: packetId, src: state.src, dst: state.dst, metric: state.metric, payload: "consola" };
    ui.send.disabled = true;
    const res = await api(routerBase(), "/packets", { method: "POST", body: JSON.stringify(payload) });
    ui.send.disabled = false;

    if (res.network) {
      ui.packetResult.className = "result err";
      ui.packetResult.replaceChildren(
        h("p", { className: "title err-title", textContent: "El Router no respondió" }),
        h("p", { className: "muted", textContent: `Verifica que router/main.py esté corriendo en ${routerBase()}.` }));
      log("err", `<code>POST /packets</code>: el Router no respondió en ${esc(routerBase())}.`);
      refreshRouterHealth();
      return;
    }
    if (!res.ok) {
      ui.packetResult.className = "result err";
      ui.packetResult.replaceChildren(
        h("p", { className: "title err-title", textContent: `${res.status} ${errorCode(res)}` }),
        h("p", { className: "muted", textContent: errorMessage(res) }));
      log("err", `<code>POST /packets</code> ${esc(packetId)}: <b>${esc(errorCode(res))}</b>.`);
      return;
    }

    const result = res.body;
    if (result.status === "UNREACHABLE") {
      ui.packetResult.className = "result err";
      ui.packetResult.replaceChildren(
        h("p", { className: "title err-title", textContent: "UNREACHABLE" }),
        h("p", { className: "muted", textContent: `El Controller no encontró camino de ${result.src} a ${result.dst}. Registrado en el log: ${result.log_persisted ? "sí" : "no"}.` }));
      log("err", `Paquete <code>${esc(packetId)}</code> ${esc(result.src)}→${esc(result.dst)}: <b>UNREACHABLE</b>.`);
      return;
    }

    const hopsList = h("ol", { className: "hops" }, ...result.trace.map((hop) => h("li", { textContent: `Salto ${hop.hop}: ${hop.from_node} → ${hop.to_node}` })));
    ui.packetResult.className = "result ok";
    ui.packetResult.replaceChildren(
      h("p", { className: "title", textContent: `DELIVERED · ${result.packet_id}` }),
      pathChips(result.route.path),
      (() => {
        const dl = h("dl", { className: "kv" });
        for (const [k, v] of [["Costo", fmt(result.route.total_cost)], ["Versión topología", String(result.route.topology_version)], ["Registrado en el log", result.log_persisted ? "sí" : "no (aviso)"]]) dl.append(h("dt", { textContent: k }), h("dd", { textContent: v }));
        return dl;
      })(),
      hopsList);
    log("ok", `Paquete <code>${esc(packetId)}</code> entregado por el Router: ${result.route.path.map(esc).join(" → ")}.`);
    await animatePacket(result.trace, hopsList);
  }

  function animatePacket(trace, hopsList) {
    return new Promise((resolve) => {
      if (!trace.length || REDUCED_MOTION) { resolve(); return; }
      state.animating = true;
      const dot = el("circle", { class: "packet", r: 9 }, ui.overlay);
      let index = 0;
      const step = () => {
        if (index >= trace.length) {
          dot.remove();
          state.activeHop = null;
          state.animating = false;
          draw();
          resolve();
          return;
        }
        const hop = trace[index];
        const a = state.positions.get(hop.from_node), b = state.positions.get(hop.to_node);
        state.activeHop = linkKey(hop.from_node, hop.to_node);
        draw();
        [...hopsList.children].forEach((li, i) => li.classList.toggle("now", i === index));
        const start = performance.now(), duration = 750;
        const frame = (now) => {
          const t = Math.min((now - start) / duration, 1);
          const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
          dot.setAttribute("cx", a.x + (b.x - a.x) * e);
          dot.setAttribute("cy", a.y + (b.y - a.y) * e);
          if (t < 1) requestAnimationFrame(frame);
          else { index++; step(); }
        };
        requestAnimationFrame(frame);
      };
      step();
    });
  }

  // --------------------------------------------------------------- salud
  async function refreshHealth() {
    const res = await api("", "/health");
    const pill = ui.ctrlHealth;
    if (res.ok && res.body.status === "ok") {
      pill.className = "pill ok"; pill.lastChild.textContent = "Controller activo";
      if (!state.topology || state.topology.topology_version !== res.body.topology_version) {
        // la topología cambió desde otro lado (/docs, scripts/demo.py...): se sincroniza
        const hadTopology = Boolean(state.topology);
        await loadTopology({ silent: true });
        if (hadTopology) log("info", `La topología cambió fuera de la consola (versión ${res.body.topology_version}).`);
        if (state.src && state.dst) await calculateRoute("enlace");
      }
    } else if (res.ok) {
      pill.className = "pill warn"; pill.lastChild.textContent = "Controller degradado";
      if (state.topology) await loadTopology({ silent: true });
    } else {
      pill.className = "pill bad"; pill.lastChild.textContent = "Controller sin respuesta";
    }
  }

  async function refreshRouterHealth() {
    const res = await api(routerBase(), "/health");
    const pill = ui.routerHealth;
    if (res.ok) { pill.className = "pill ok"; pill.lastChild.textContent = "Router activo"; }
    else { pill.className = "pill bad"; pill.lastChild.textContent = "Router sin respuesta"; }
  }

  // ------------------------------------------------------------- eventos
  function bind() {
    document.querySelectorAll(".segmented button").forEach((button) => {
      button.addEventListener("click", () => {
        state.metric = button.dataset.metric;
        document.querySelectorAll(".segmented button").forEach((b) => {
          b.classList.toggle("active", b === button);
          b.setAttribute("aria-checked", String(b === button));
        });
        state.ghostPath = null;
        updateHint();
        draw();
        if (state.src && state.dst) calculateRoute("métrica");
      });
    });
    ui.src.addEventListener("change", () => { setEndpoints(ui.src.value || null, ui.dst.value && ui.dst.value !== ui.src.value ? ui.dst.value : null); if (state.src && state.dst) calculateRoute("selección"); });
    ui.dst.addEventListener("change", () => { if (!ui.src.value) { ui.dst.value = ""; return; } state.dst = ui.dst.value || null; state.route = null; state.ghostPath = null; state.unreachable = false; if (state.dst) calculateRoute("selección"); else { renderRouteIdle(); draw(); } });
    ui.swap.addEventListener("click", () => { if (state.src && state.dst) { setEndpoints(state.dst, state.src); calculateRoute("selección"); } });
    ui.calc.addEventListener("click", () => calculateRoute("botón"));
    ui.clear.addEventListener("click", () => { state.selectedLink = null; setEndpoints(null, null); renderLinkList(); });
    ui.send.addEventListener("click", sendPacket);
    ui.routerUrl.addEventListener("change", refreshRouterHealth);
    ui.clearLog.addEventListener("click", () => ui.log.replaceChildren());
  }

  async function start() {
    const params = new URLSearchParams(location.search);
    ui.routerUrl.value = params.get("router") || `${location.protocol}//${location.hostname}:8001`;
    bind();
    renderRouteIdle();
    await loadTopology();
    await Promise.all([refreshHealth(), refreshRouterHealth()]);
    setInterval(refreshHealth, 3000);
    setInterval(refreshRouterHealth, 5000);
  }

  start();
})();
