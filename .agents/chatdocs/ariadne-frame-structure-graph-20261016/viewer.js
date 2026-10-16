(function () {
  "use strict";

  const data = window.ARIADNE_GRAPH;
  const svgNS = "http://www.w3.org/2000/svg";
  const MAX_NODES = 64;
  const MAX_EDGES = 160;
  if (!data || !data.nodes || !Array.isArray(data.edges)) return;

  function canonical(value) {
    const raw = String(value || "").trim().toLowerCase().replace(/^0x/, "");
    return /^[0-9a-f]{1,16}$/.test(raw) ? "0x" + raw.padStart(16, "0") : null;
  }

  const nodes = new Map();
  Object.keys(data.nodes).forEach(function (id) {
    const original = data.nodes[id];
    nodes.set(id, Object.assign({}, original, {
      id: id,
      va: canonical(original.va) || String(original.va || id),
      gaps: Array.isArray(original.gaps) ? original.gaps.map(String) : []
    }));
  });
  const edges = data.edges.map(function (edge, index) {
    return { src: String(edge.src), dst: String(edge.dst), kind: String(edge.kind || "Unknown"), index: index };
  });
  // An edge may name an unrecovered target. Preserve that target without
  // representing it as a decoded instruction.
  edges.forEach(function (edge) {
    [edge.src, edge.dst].forEach(function (id) {
      if (nodes.has(id)) return;
      const match = /^f(\d+)_a([0-9a-f]+)$/i.exec(id);
      nodes.set(id, { id: id, frame: match ? Number(match[1]) : "?", va: match ? canonical(match[2]) : id, status: "unrecovered target", gaps: [] });
    });
  });
  const adjacency = new Map();
  nodes.forEach(function (_, id) { adjacency.set(id, []); });
  edges.forEach(function (edge) {
    adjacency.get(edge.src).push({ id: edge.dst, direction: 1, edge: edge });
    if (edge.src !== edge.dst) adjacency.get(edge.dst).push({ id: edge.src, direction: -1, edge: edge });
  });

  function findFocus(value, frame) {
    const address = canonical(value);
    if (!address) return { error: "Invalid address: enter one to sixteen hexadecimal digits, optionally prefixed by 0x." };
    const candidates = Array.from(nodes.values()).filter(function (node) { return frame === "any" || String(node.frame) === String(frame); });
    let matches = candidates.filter(function (node) { return node.va === address; });
    if (matches.length === 0) {
      const suffix = String(value).trim().toLowerCase().replace(/^0x/, "");
      matches = candidates.filter(function (node) { return String(node.va).replace(/^0x/, "").endsWith(suffix); });
    }
    if (matches.length === 0) return { error: "No graph node matches this address in the selected frame." };
    if (matches.length > 1) return { error: "Ambiguous address: " + matches.length + " nodes match. Select a frame or enter more address digits." };
    return { id: matches[0].id };
  }

  function neighborhood(focus, radius) {
    const selected = new Map([[focus, { distance: 0, level: 0 }]]);
    const queue = [focus];
    const omitted = new Set();
    let deeperUnknown = false;
    for (let head = 0; head < queue.length; head += 1) {
      const id = queue[head];
      const state = selected.get(id);
      if (state.distance >= radius) continue;
      adjacency.get(id).forEach(function (neighbor) {
        if (selected.has(neighbor.id)) return;
        if (selected.size >= MAX_NODES) {
          omitted.add(neighbor.id);
          if (state.distance + 1 < radius) deeperUnknown = true;
          return;
        }
        selected.set(neighbor.id, { distance: state.distance + 1, level: state.level + neighbor.direction });
        omitted.delete(neighbor.id);
        queue.push(neighbor.id);
      });
    }
    const internal = edges.filter(function (edge) { return selected.has(edge.src) && selected.has(edge.dst); });
    return { selected: selected, edges: internal.slice(0, MAX_EDGES), omittedNodes: omitted.size, deeperUnknown: deeperUnknown, omittedEdges: Math.max(0, internal.length - MAX_EDGES) };
  }

  function init() {
    const frameSelect = document.getElementById("frame-select");
    const addressInput = document.getElementById("address-input");
    const radiusSelect = document.getElementById("radius-select");
    const exploreButton = document.getElementById("explorebutton");
    const status = document.getElementById("viewer-status");
    const container = document.getElementById("neighborhood");
    const details = document.getElementById("selection-details");
    if (![frameSelect, addressInput, radiusSelect, exploreButton, status, container, details].every(Boolean)) return;
    container.style.overflowX = "auto";
    container.setAttribute("aria-label", "Bounded control-flow neighborhood");
    let currentFocus = null;

    function element(tag, attributes, text) {
      const result = document.createElementNS(svgNS, tag);
      Object.keys(attributes || {}).forEach(function (key) { result.setAttribute(key, attributes[key]); });
      if (text !== undefined) result.textContent = text;
      return result;
    }

    function edgeStyle(edge) {
      if (/captured.*e8|cross.?frame/i.test(edge.kind)) return { color: "#18845a", dash: "", marker: "cross" };
      if (/summary/i.test(edge.kind)) return { color: "#64748b", dash: "6 4", marker: "summary" };
      if (/call/i.test(edge.kind)) return { color: "#8b5cb5", dash: "3 4", marker: "call" };
      return { color: "#336fa5", dash: "", marker: "normal" };
    }

    function focusNode(id) {
      if (!nodes.has(id)) return;
      currentFocus = id;
      addressInput.value = nodes.get(id).va;
      // A selected node may be in the other frame, reached through the captured
      // CALL link. Keep the form consistent with the node the user selected.
      if (frameSelect.value !== "any" && String(nodes.get(id).frame) !== frameSelect.value) frameSelect.value = String(nodes.get(id).frame);
      addressInput.removeAttribute("aria-invalid");
      render();
    }

    function render() {
      if (!currentFocus) return;
      const radius = Math.max(1, Math.min(3, Number(radiusSelect.value) || 1));
      const local = neighborhood(currentFocus, radius);
      const columns = new Map();
      local.selected.forEach(function (position, id) {
        if (!columns.has(position.level)) columns.set(position.level, []);
        columns.get(position.level).push(id);
      });
      const levels = Array.from(columns.keys()).sort(function (a, b) { return a - b; });
      const width = Math.max(720, levels.length * 330 + 60);
      const rows = Math.max.apply(null, Array.from(columns.values()).map(function (column) { return column.length; }));
      const height = Math.max(220, rows * 140 + 80);
      const positions = new Map();
      levels.forEach(function (level, columnIndex) {
        columns.get(level).forEach(function (id, row) {
          positions.set(id, { x: 40 + columnIndex * 330, y: 40 + row * 140 + (height - 80 - columns.get(level).length * 140) / 2 });
        });
      });
      const svg = element("svg", { viewBox: "0 0 " + width + " " + height, width: width, height: height, role: "group", "aria-labelledby": "graph-title graph-description" });
      svg.style.maxWidth = "none";
      svg.appendChild(element("title", { id: "graph-title" }, "Recovered control-flow neighborhood"));
      svg.appendChild(element("desc", { id: "graph-description" }, "Actual typed control-flow edges within radius " + radius + ". Columns organize neighbors of the selected node; columns do not establish execution order. Boundary facts are node annotations, not invented destinations."));
      const defs = element("defs");
      [{ id: "cross", color: "#18845a" }, { id: "summary", color: "#64748b" }, { id: "call", color: "#8b5cb5" }, { id: "normal", color: "#336fa5" }].forEach(function (style) {
        const marker = element("marker", { id: "arrow-" + style.id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" });
        marker.appendChild(element("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: style.color }));
        defs.appendChild(marker);
      });
      svg.appendChild(defs);
      const edgeGroup = element("g", { "aria-label": "Actual graph edges" });
      local.edges.forEach(function (edge) {
        const source = positions.get(edge.src);
        const target = positions.get(edge.dst);
        const style = edgeStyle(edge);
        let sx = source.x + 250, sy = source.y + 48, tx = target.x, ty = target.y + 48;
        let path;
        if (edge.src === edge.dst) {
          path = "M " + (source.x + 185) + " " + source.y + " C " + (source.x + 300) + " " + (source.y - 35) + " " + (source.x + 300) + " " + (source.y + 115) + " " + (source.x + 250) + " " + (source.y + 80);
        } else if (target.x === source.x) {
          tx = target.x + 250;
          path = "M " + sx + " " + sy + " C " + (sx + 55) + " " + sy + " " + (tx + 55) + " " + ty + " " + tx + " " + ty;
        } else {
          if (target.x < source.x) { sx = source.x; tx = target.x + 250; }
          const mx = (sx + tx) / 2;
          path = "M " + sx + " " + sy + " C " + mx + " " + sy + " " + mx + " " + ty + " " + tx + " " + ty;
        }
        const group = element("g", { "data-edge-kind": edge.kind, "data-edge-src": edge.src, "data-edge-dst": edge.dst });
        group.appendChild(element("title", {}, edge.kind + ": " + nodes.get(edge.src).va + " → " + nodes.get(edge.dst).va));
        group.appendChild(element("path", { d: path, fill: "none", stroke: style.color, "stroke-width": 2, "stroke-dasharray": style.dash, "marker-end": "url(#arrow-" + style.marker + ")" }));
        const label = edge.kind.length > 28 ? edge.kind.slice(0, 25) + "…" : edge.kind;
        group.appendChild(element("text", { x: (sx + tx) / 2, y: (sy + ty) / 2 - 7, fill: style.color, "font-size": 11, "text-anchor": "middle", "paint-order": "stroke", stroke: "#ffffff", "stroke-width": 4, "stroke-linejoin": "round" }, label));
        edgeGroup.appendChild(group);
      });
      svg.appendChild(edgeGroup);
      local.selected.forEach(function (_, id) {
        const node = nodes.get(id);
        const position = positions.get(id);
        const unknown = /unknown|unrecover|unvisit|pending|failed|unavailable|opaque/i.test(String(node.status || ""));
        const group = element("g", { transform: "translate(" + position.x + " " + position.y + ")", tabindex: 0, role: "button", "data-node-id": id, "aria-label": "Focus frame " + node.frame + ", " + node.va + ", " + (node.status || "status unavailable") });
        group.style.cursor = "pointer";
        group.appendChild(element("title", {}, "Frame " + node.frame + " " + node.va + "\n" + (node.status || "status unavailable") + (node.gaps.length ? "\nBoundary facts:\n" + node.gaps.join("\n") : "")));
        group.appendChild(element("rect", { width: 250, height: 100, rx: 9, fill: id === currentFocus ? "#e9f2ff" : unknown ? "#fff4dc" : "#ffffff", stroke: id === currentFocus ? "#1c5c9b" : unknown ? "#aa741d" : "#94a3b8", "stroke-width": id === currentFocus ? 3 : 1.5 }));
        group.appendChild(element("text", { x: 12, y: 21, fill: "#475569", "font-size": 12 }, "FRAME " + node.frame + (id === currentFocus ? " · SELECTED" : "")));
        group.appendChild(element("text", { x: 12, y: 44, fill: "#10243a", "font-size": 15, "font-family": "monospace" }, node.va));
        group.appendChild(element("text", { x: 12, y: 65, fill: unknown ? "#865c17" : "#475569", "font-size": 12 }, String(node.status || "status unavailable").slice(0, 34)));
        const badge = node.gaps.length ? "Boundary facts: " + node.gaps.length + " · " + node.gaps[0] : "No recorded boundary fact";
        group.appendChild(element("text", { x: 12, y: 85, fill: node.gaps.length ? "#865c17" : "#64748b", "font-size": 10 }, badge.length > 43 ? badge.slice(0, 40) + "…" : badge));
        group.addEventListener("click", function () { focusNode(id); });
        group.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); focusNode(id); }
        });
        svg.appendChild(group);
      });
      container.replaceChildren(svg);
      const omissions = [];
      if (local.omittedNodes) omissions.push((local.deeperUnknown ? "at least " : "") + local.omittedNodes + " neighboring nodes omitted by the " + MAX_NODES + "-node cap");
      if (local.omittedEdges) omissions.push(local.omittedEdges + " edges between displayed nodes omitted by the " + MAX_EDGES + "-edge cap");
      status.textContent = "Showing " + local.selected.size + " nodes and " + local.edges.length + " actual edges, radius " + radius + ". " + (omissions.length ? omissions.join("; ") + ". " : "") + "This neighborhood omits other graph nodes. Columns are a browsing layout, not an execution sequence.";
      const chosen = nodes.get(currentFocus);
      const incident = adjacency.get(currentFocus);
      const lines = ["Frame " + chosen.frame + " · " + chosen.va, "Status: " + (chosen.status || "unavailable"), "", "Boundary facts (annotations, not CFG destinations):"];
      lines.push.apply(lines, chosen.gaps.length ? chosen.gaps.map(function (gap) { return "  " + gap; }) : ["  None recorded."]);
      lines.push("", "Incident edges in the retained graph:");
      incident.forEach(function (neighbor) {
        const edge = neighbor.edge;
        lines.push("  frame " + nodes.get(edge.src).frame + " " + nodes.get(edge.src).va + " --[" + edge.kind + "]--> frame " + nodes.get(edge.dst).frame + " " + nodes.get(edge.dst).va);
      });
      if (!incident.length) lines.push("  None recorded.");
      details.textContent = lines.join("\n");
    }

    function explore() {
      const result = findFocus(addressInput.value, frameSelect.value || "any");
      if (result.error) {
        addressInput.setAttribute("aria-invalid", "true");
        status.textContent = result.error + " The previous neighborhood is unchanged.";
        return;
      }
      focusNode(result.id);
    }
    exploreButton.addEventListener("click", explore);
    addressInput.addEventListener("keydown", function (event) { if (event.key === "Enter") { event.preventDefault(); explore(); } });
    frameSelect.addEventListener("change", explore);
    radiusSelect.addEventListener("change", render);
    document.querySelectorAll("[data-focus]").forEach(function (button) {
      button.addEventListener("click", function () { focusNode(button.getAttribute("data-focus")); });
    });
    if (!addressInput.value) addressInput.value = "0x00007ff774404108";
    explore();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
}());
