/*
 * Rectify overlay — a single, dependency-free drop-in.
 *
 *   <script src="/rectify.js" data-rectify-endpoint="ws://localhost:4242/ws"></script>
 *
 * Lets you toggle an edit mode, draw a rectangle (or click) over any region of the
 * page, then describe a change in a chat box. The selection + instruction are sent
 * over a WebSocket to the local agent, which edits the source. Works on any site
 * because it stamps nothing onto the page — the agent finds the source itself.
 */
(function () {
  "use strict";
  if (window.__rectifyLoaded) return;
  window.__rectifyLoaded = true;

  // ---- config -------------------------------------------------------------
  const script = document.currentScript;
  const endpoint =
    (script && script.getAttribute("data-rectify-endpoint")) ||
    window.RECTIFY_ENDPOINT ||
    "ws://" + (location.hostname || "localhost") + ":4242/ws";

  // Opt-in: hard-reload the page after a successful edit. Useful for static sites
  // with no HMR; leave off for frameworks (Vite/React) that hot-swap in place.
  const autoReload =
    (script && script.hasAttribute("data-rectify-reload")) ||
    !!window.RECTIFY_RELOAD;

  // HTTP base for upload/list/delete, derived from the ws endpoint: swap the
  // scheme and drop the trailing "/ws". Under the platform this is "/_rectify"
  // (same origin, owner cookie sent); in local dev it's the agent's http origin.
  const httpBase = endpoint
    .replace(/^ws/, "http")
    .replace(/\/ws$/, "");

  // ---- icons (inline Lucide SVGs, MIT licensed) ---------------------------
  const SVG_OPEN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 3a2 2 0 0 0-2 2"/><path d="M19 3a2 2 0 0 1 2 2"/><path d="M21 19a2 2 0 0 1-2 2"/><path d="M5 21a2 2 0 0 1-2-2"/><path d="M9 3h1"/><path d="M9 21h1"/><path d="M14 3h1"/><path d="M14 21h1"/><path d="M3 9v1"/><path d="M21 9v1"/><path d="M3 14v1"/><path d="M21 14v1"/></svg>'; // lucide: square-dashed
  const SVG_CLOSE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>'; // lucide: x
  const SVG_CLIP = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13.234 20.252 21 12.3"/><path d="m16 6-8.414 8.586a2 2 0 0 0 0 2.828 2 2 0 0 0 2.828 0l8.414-8.586a4 4 0 0 0 0-5.656 4 4 0 0 0-5.656 0l-8.415 8.585a6 6 0 1 0 8.486 8.486"/></svg>'; // lucide: paperclip

  // ---- shadow root (isolates our UI from the host page's CSS) --------------
  const host = document.createElement("div");
  host.id = "rectify-root";
  host.style.cssText = "position:fixed;inset:0;z-index:2147483647;pointer-events:none;";
  document.documentElement.appendChild(host);
  const root = host.attachShadow({ mode: "open" });

  root.innerHTML = `
    <style>
      :host { all: initial; }
      * { box-sizing: border-box; font-family: -apple-system, system-ui, sans-serif; }
      .toggle {
        position: fixed; right: 16px; bottom: 16px; pointer-events: auto; z-index: 40;
        width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
        background: #111; color: #fff; border: none; border-radius: 50%; cursor: pointer;
        box-shadow: 0 4px 16px rgba(0,0,0,.25);
      }
      .toggle svg { width: 20px; height: 20px; }
      .toggle.active { background: #2563eb; }
      .capture {
        position: fixed; inset: 0; pointer-events: auto; cursor: crosshair; z-index: 10;
        background: rgba(37,99,235,.04);
      }
      .hl {
        position: fixed; pointer-events: none; border: 2px solid #2563eb; z-index: 20;
        background: rgba(37,99,235,.12); border-radius: 2px;
      }
      .rect {
        position: fixed; pointer-events: none; border: 2px dashed #2563eb; z-index: 20;
        background: rgba(37,99,235,.10);
      }
      .panel {
        position: fixed; width: 340px; max-height: 70vh; pointer-events: auto; z-index: 30;
        background: #fff; color: #111; border-radius: 12px; display: flex;
        flex-direction: column; box-shadow: 0 8px 40px rgba(0,0,0,.3);
        border: 1px solid #e5e7eb; overflow: hidden;
      }
      .panel header {
        display: flex; align-items: center; gap: 8px; padding: 10px 12px;
        background: #f8fafc; border-bottom: 1px solid #e5e7eb; font-size: 13px; font-weight: 600;
      }
      .panel header .sel { color: #6b7280; font-weight: 400; font-size: 11px;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
      .panel header button { border: none; background: none; cursor: pointer; color: #6b7280; font-size: 16px; }
      .msgs { flex: 1; overflow-y: auto; padding: 10px 12px; font-size: 12px; }
      .msg { margin-bottom: 8px; line-height: 1.45; }
      .msg.user { color: #111; font-weight: 600; }
      .msg.step { color: #475569; }
      .msg.error { color: #b91c1c; white-space: pre-wrap; }
      .msg.done { color: #047857; }
      .msg pre { background: #0f172a; color: #e2e8f0; padding: 8px; border-radius: 6px;
        overflow-x: auto; font-size: 11px; margin: 4px 0 0; white-space: pre; }
      .msg code { background: #eef2ff; color: #3730a3; padding: 1px 4px; border-radius: 4px; font-size: 11px; }
      .msg pre code { background: none; color: inherit; padding: 0; }
      .msg ul, .msg ol { margin: 4px 0 4px 18px; padding: 0; }
      .msg li { margin: 2px 0; }
      .msg a { color: #2563eb; }
      .msg strong { font-weight: 700; }
      .think { margin-bottom: 8px; font-size: 11px; }
      .think > summary { cursor: pointer; color: #94a3b8; list-style: none; user-select: none; }
      .think > summary::-webkit-details-marker { display: none; }
      .think > summary::before { content: "▸  "; }
      .think[open] > summary::before { content: "▾  "; }
      .think-body { margin-top: 6px; padding-left: 8px; border-left: 2px solid #e5e7eb; }
      .think-body .msg:last-child { margin-bottom: 0; }
      .history { margin-bottom: 8px; font-size: 11px; }
      .history > summary { cursor: pointer; color: #94a3b8; list-style: none; user-select: none; }
      .history > summary::-webkit-details-marker { display: none; }
      .history > summary::before { content: "▸  "; }
      .history[open] > summary::before { content: "▾  "; }
      .history-body { margin-top: 6px; padding-left: 8px; border-left: 2px solid #e5e7eb; }
      .compose { display: flex; flex-direction: column; gap: 6px; padding: 10px 12px; border-top: 1px solid #e5e7eb; }
      .compose textarea { width: 100%; resize: vertical; min-height: 54px; padding: 8px;
        border: 1px solid #d1d5db; border-radius: 8px; font-size: 13px; }
      .chips { display: flex; flex-wrap: wrap; gap: 4px; }
      .chips:empty { display: none; }
      .chip { display: inline-flex; align-items: center; gap: 4px; max-width: 100%;
        background: #eef2ff; color: #3730a3; border-radius: 6px; padding: 2px 4px 2px 8px; font-size: 11px; }
      .chip .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 200px; }
      .chip button { border: none; background: none; cursor: pointer; color: #6366f1; font-size: 13px; line-height: 1; padding: 0 2px; }
      .row { display: flex; gap: 6px; align-items: stretch; }
      .row button { flex: 1; border: none; border-radius: 8px; padding: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }
      .send { background: #2563eb; color: #fff; }
      .send:disabled { opacity: .5; cursor: default; }
      .clip { background: #f1f5f9; color: #334155; flex: 0 0 40px; display: flex; align-items: center; justify-content: center; }
      .clip svg { width: 16px; height: 16px; }
      .uploads { margin-bottom: 8px; font-size: 11px; }
      .uploads > summary { cursor: pointer; color: #94a3b8; list-style: none; user-select: none; }
      .uploads > summary::-webkit-details-marker { display: none; }
      .uploads > summary::before { content: "▸  "; }
      .uploads[open] > summary::before { content: "▾  "; }
      .uploads-body { margin-top: 6px; padding-left: 8px; border-left: 2px solid #e5e7eb; }
      .upitem { display: flex; align-items: center; gap: 6px; margin: 2px 0; }
      .upitem a { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #2563eb; }
      .upitem button { border: none; background: none; cursor: pointer; color: #94a3b8; font-size: 13px; line-height: 1; padding: 0 2px; }
      .upitem .empty { color: #94a3b8; }
      .dot { width:8px;height:8px;border-radius:50%;background:#22c55e;flex:0 0 auto; }
      .dot.off { background:#ef4444; }
    </style>
    <button class="toggle" title="Select an element to edit">${SVG_OPEN}</button>
  `;

  const toggle = root.querySelector(".toggle");

  // ---- websocket ----------------------------------------------------------
  let ws = null;
  let wsReady = false;
  const listeners = new Set();

  // Per-tab id so the agent keeps its memory across a reload (sessionStorage
  // survives reloads and is cleared when the tab closes). Falls back to a fresh
  // id each load if storage is blocked (private mode), i.e. no cross-reload memory.
  function sessionId() {
    try {
      let id = sessionStorage.getItem("rectify-sid");
      if (!id) {
        id =
          (crypto.randomUUID && crypto.randomUUID()) ||
          Date.now().toString(36) + Math.random().toString(36).slice(2);
        sessionStorage.setItem("rectify-sid", id);
      }
      return id;
    } catch (e) {
      return null;
    }
  }

  function connect() {
    if (ws && (ws.readyState === 0 || ws.readyState === 1)) return;
    const sid = sessionId();
    const url = sid
      ? endpoint + (endpoint.indexOf("?") === -1 ? "?" : "&") + "sid=" + encodeURIComponent(sid)
      : endpoint;
    try {
      ws = new WebSocket(url);
    } catch (e) {
      console.warn("[rectify] bad endpoint", endpoint, e);
      return;
    }
    ws.onopen = () => { wsReady = true; updateDot(); };
    ws.onclose = () => { wsReady = false; updateDot(); };
    ws.onerror = () => { wsReady = false; updateDot(); };
    ws.onmessage = (ev) => {
      let data;
      try { data = JSON.parse(ev.data); } catch { return; }
      listeners.forEach((fn) => fn(data));
    };
  }
  function send(obj) {
    if (!ws || ws.readyState !== 1) { connect(); }
    const trySend = () => {
      if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
      else setTimeout(trySend, 120);
    };
    trySend();
  }
  function updateDot() {
    const dot = root.querySelector(".dot");
    if (dot) dot.classList.toggle("off", !wsReady);
  }
  connect();

  // ---- selection ----------------------------------------------------------
  let mode = false;
  let capture = null, rectEl = null, hlEl = null, start = null, selected = false;

  function setMode(on) {
    mode = on;
    toggle.classList.toggle("active", on);
    toggle.innerHTML = on ? SVG_CLOSE : SVG_OPEN;
    toggle.title = on ? "Close" : "Select an element to edit";
    if (on) enterCapture(); else exitCapture();
  }

  function enterCapture() {
    capture = document.createElement("div");
    capture.className = "capture";
    root.appendChild(capture);
    hlEl = document.createElement("div");
    hlEl.className = "hl";
    hlEl.style.display = "none";
    root.appendChild(hlEl);

    capture.addEventListener("mousemove", onHover);
    capture.addEventListener("mousedown", onDown);
  }
  function exitCapture() {
    [capture, hlEl, rectEl].forEach((el) => el && el.remove());
    capture = hlEl = rectEl = start = null;
    selected = false;
  }

  // Hover highlight: peek through our overlay to find the real element.
  function elementUnder(x, y) {
    if (capture) capture.style.pointerEvents = "none";
    const el = document.elementFromPoint(x, y);
    if (capture) capture.style.pointerEvents = "auto";
    return el;
  }
  function onHover(e) {
    if (selected || start) return; // frozen on a selection, or drawing
    const el = elementUnder(e.clientX, e.clientY);
    if (!el) { hlEl.style.display = "none"; return; }
    const r = el.getBoundingClientRect();
    Object.assign(hlEl.style, {
      display: "block", left: r.left + "px", top: r.top + "px",
      width: r.width + "px", height: r.height + "px",
    });
  }
  function onDown(e) {
    e.preventDefault();
    selected = false; // starting a fresh selection re-enables hover preview
    if (rectEl) { rectEl.remove(); rectEl = null; }
    start = { x: e.clientX, y: e.clientY };
    hlEl.style.display = "none";
    rectEl = document.createElement("div");
    rectEl.className = "rect";
    root.appendChild(rectEl);
    window.addEventListener("mousemove", onMove, true);
    window.addEventListener("mouseup", onUp, true);
  }
  function onMove(e) {
    if (!start) return;
    const x = Math.min(e.clientX, start.x), y = Math.min(e.clientY, start.y);
    const w = Math.abs(e.clientX - start.x), h = Math.abs(e.clientY - start.y);
    Object.assign(rectEl.style, { left: x + "px", top: y + "px", width: w + "px", height: h + "px" });
  }
  function onUp(e) {
    window.removeEventListener("mousemove", onMove, true);
    window.removeEventListener("mouseup", onUp, true);
    const x = Math.min(e.clientX, start.x), y = Math.min(e.clientY, start.y);
    const w = Math.abs(e.clientX - start.x), h = Math.abs(e.clientY - start.y);
    const cx = x + w / 2, cy = y + h / 2;
    const isClick = w < 6 && h < 6;
    start = null;
    const target = elementUnder(isClick ? e.clientX : cx, isClick ? e.clientY : cy);
    if (!target || target === document.body || target === document.documentElement) {
      if (rectEl) { rectEl.remove(); rectEl = null; }
      return;
    }
    if (isClick) {
      // Drop the zero-size rect; freeze the highlight on the clicked element.
      if (rectEl) { rectEl.remove(); rectEl = null; }
      const r = target.getBoundingClientRect();
      Object.assign(hlEl.style, {
        display: "block", left: r.left + "px", top: r.top + "px",
        width: r.width + "px", height: r.height + "px",
      });
    } else {
      hlEl.style.display = "none"; // keep rectEl as the selection box
    }
    selected = true; // stop the hover highlight from chasing other elements
    const ctx = captureContext(target);
    openPanel(ctx, { x, y, w, h });
  }

  // ---- context capture ----------------------------------------------------
  function cssSelector(el) {
    if (!el || el.nodeType !== 1) return "";
    if (el.id) return "#" + CSS.escape(el.id);
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && parts.length < 5 && node !== document.body) {
      let part = node.tagName.toLowerCase();
      if (node.classList.length) {
        part += "." + [...node.classList].slice(0, 2).map((c) => CSS.escape(c)).join(".");
      }
      const parent = node.parentElement;
      if (parent) {
        const sibs = [...parent.children].filter((c) => c.tagName === node.tagName);
        if (sibs.length > 1) part += `:nth-of-type(${sibs.indexOf(node) + 1})`;
      }
      parts.unshift(part);
      node = node.parentElement;
    }
    return parts.join(" > ");
  }
  function captureContext(el) {
    const text = (el.innerText || el.textContent || "").trim().slice(0, 600);
    return {
      url: location.href,
      tag: el.tagName.toLowerCase(),
      classes: el.getAttribute("class") || "",
      selector: cssSelector(el),
      text,
      outerHTML: (el.outerHTML || "").slice(0, 4000),
    };
  }

  // ---- chat panel ---------------------------------------------------------
  let panel = null, currentCtx = null, busy = false;

  function openPanel(ctx, rect) {
    currentCtx = ctx;
    if (panel) panel.remove();
    panel = document.createElement("div");
    panel.className = "panel";
    panel.innerHTML = `
      <header>
        <span class="dot${wsReady ? "" : " off"}"></span>
        <span class="sel">${ctx.tag}${ctx.classes ? "." + ctx.classes.split(/\s+/)[0] : ""}</span>
        <button class="close" title="Close">✕</button>
      </header>
      <div class="msgs"></div>
      <div class="compose">
        <details class="uploads">
          <summary>Uploaded files</summary>
          <div class="uploads-body"></div>
        </details>
        <div class="chips"></div>
        <textarea placeholder="Describe the change… (e.g. make this heading larger and blue)"></textarea>
        <input type="file" class="file" multiple hidden>
        <div class="row">
          <button class="clip" title="Attach files">${SVG_CLIP}</button>
          <button class="send">Send</button>
        </div>
      </div>`;
    root.appendChild(panel);

    // Position next to the selection, kept on-screen.
    const vw = window.innerWidth, vh = window.innerHeight;
    let left = rect.x + rect.w + 12;
    if (left + 340 > vw) left = Math.max(8, rect.x - 352);
    let top = Math.min(rect.y, vh - 360);
    if (top < 8) top = 8;
    panel.style.left = left + "px";
    panel.style.top = top + "px";

    const ta = panel.querySelector("textarea");
    const sendBtn = panel.querySelector(".send");
    const msgs = panel.querySelector(".msgs");
    ta.focus();

    // ---- attachments ------------------------------------------------------
    // Files chosen via the paperclip wait here until Send, which uploads them
    // first and then sends the instruction referencing them. Removing a chip
    // just drops the pending file — nothing is uploaded until Send.
    const chipsEl = panel.querySelector(".chips");
    const fileInput = panel.querySelector(".file");
    const uploadsEl = panel.querySelector(".uploads");
    const uploadsBody = panel.querySelector(".uploads-body");
    let pending = [];

    function renderChips() {
      chipsEl.innerHTML = "";
      pending.forEach((file, i) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.innerHTML = `<span class="name"></span><button title="Remove">✕</button>`;
        chip.querySelector(".name").textContent = file.name;
        chip.querySelector("button").onclick = () => { pending.splice(i, 1); renderChips(); };
        chipsEl.appendChild(chip);
      });
    }

    panel.querySelector(".clip").onclick = () => fileInput.click();
    fileInput.onchange = () => {
      pending.push(...fileInput.files);
      fileInput.value = ""; // allow re-picking the same file
      renderChips();
    };

    // Uploads manager: list saved files, each removable via DELETE.
    async function refreshUploads() {
      try {
        const res = await fetch(`${httpBase}/uploads`, { credentials: "same-origin" });
        if (!res.ok) return;
        const { files } = await res.json();
        uploadsBody.innerHTML = "";
        if (!files.length) {
          uploadsBody.innerHTML = `<div class="upitem"><span class="empty">No files uploaded yet.</span></div>`;
          return;
        }
        files.forEach((f) => {
          const item = document.createElement("div");
          item.className = "upitem";
          item.innerHTML = `<a target="_blank" rel="noopener"></a><button title="Delete">✕</button>`;
          const a = item.querySelector("a");
          a.href = f.url; a.textContent = f.name;
          item.querySelector("button").onclick = async () => {
            await fetch(`${httpBase}/upload?name=${encodeURIComponent(f.name)}`,
              { method: "DELETE", credentials: "same-origin" });
            refreshUploads();
          };
          uploadsBody.appendChild(item);
        });
      } catch { /* offline / local dev without the endpoint — leave list empty */ }
    }
    refreshUploads();

    // Only the latest success/error stays visible; everything else (instructions,
    // thinking, prior outcomes) is swept into a collapsed "Previous messages" block.
    let lastOutcome = null;
    let historyEl = null;
    function archive(el) {
      if (!el) return;
      if (!historyEl) {
        historyEl = document.createElement("details");
        historyEl.className = "history";
        historyEl.innerHTML = `<summary>Previous messages</summary><div class="history-body"></div>`;
        msgs.insertBefore(historyEl, msgs.firstChild);
      }
      historyEl.querySelector(".history-body").appendChild(el);
    }

    panel.querySelector(".close").onclick = () => {
      panel.remove(); panel = null;
      selected = false; // resume hover preview after dismissing the selection
      if (hlEl) hlEl.style.display = "none";
      if (rectEl) { rectEl.remove(); rectEl = null; }
    };
    sendBtn.onclick = doSend;
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); doSend(); }
    });

    async function doSend() {
      const instruction = ta.value.trim();
      if (!instruction || busy) return;
      busy = true; sendBtn.disabled = true;

      // Upload any attached files first, then reference them in the instruction.
      let attachments = [];
      if (pending.length) {
        try {
          attachments = await Promise.all(pending.map(async (file) => {
            const res = await fetch(
              `${httpBase}/upload?name=${encodeURIComponent(file.name)}`,
              { method: "POST", body: file, credentials: "same-origin" });
            if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `Upload failed (${res.status})`);
            return res.json();
          }));
        } catch (e) {
          addMsg(msgs, "error", "Upload failed: " + (e.message || e));
          busy = false; sendBtn.disabled = false;
          return;
        }
        pending = []; renderChips(); refreshUploads();
      }

      const userMsg = addMsg(msgs, "user", instruction);
      ta.value = "";

      // Collect the agent's streamed steps ("thinking") into a collapsible block,
      // collapsed by default — click "Thinking" to reveal the live updates;
      // only the final answer is shown prominently once the run completes.
      const think = document.createElement("details");
      think.className = "think";
      think.open = false;
      think.innerHTML = `<summary>Thinking…</summary><div class="think-body"></div>`;
      msgs.appendChild(think);
      const thinkBody = think.querySelector(".think-body");
      const collapseThink = () => {
        think.open = false;
        think.querySelector("summary").textContent = "Thinking";
        if (!thinkBody.children.length) think.remove();
      };

      const onData = (data) => {
        // step + done summaries are written by the agent in markdown; render them.
        if (data.type === "step") {
          addMsg(thinkBody, "step", md(data.message), true);
          msgs.scrollTop = msgs.scrollHeight;
        } else if (data.type === "error") {
          collapseThink();
          showOutcome("error", data.message, false);
          finish();
        } else if (data.type === "done") {
          collapseThink();
          let html = md(data.summary || "Done.");
          if (data.files && data.files.length) html += `<br><small>${escapeHtml(data.files.join(", "))}</small>`;
          // changed === false means no file actually changed; show it as a warning.
          showOutcome(data.changed === false ? "error" : "done", html, true);
          finish();
          // Brief delay so the success message paints before the page reloads.
          if (data.changed && autoReload) setTimeout(() => location.reload(), 400);
        }
      };
      // Sweep this run's instruction + thinking and any prior outcome into the
      // collapsed history, leaving only the newest success/error visible.
      function showOutcome(cls, text, isHtml) {
        archive(lastOutcome);
        archive(userMsg);
        archive(think);
        lastOutcome = addMsg(msgs, cls, text, isHtml);
      };
      function finish() { busy = false; sendBtn.disabled = false; listeners.delete(onData); }
      listeners.add(onData);
      send({ type: "instruction", instruction, context: currentCtx, attachments });
    }
  }

  function addMsg(container, cls, text, isHtml) {
    const div = document.createElement("div");
    div.className = "msg " + cls;
    if (isHtml) div.innerHTML = text; else div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  // Minimal, dependency-free markdown → HTML for agent-authored text. Code is
  // stashed BEFORE escaping (contents escaped as it's stashed) so the agent's
  // literal <code>…</code> action blocks — plus ``` fences and `inline` — render
  // as real code rather than escaped tag text. Everything stays XSS-safe.
  function md(src) {
    const NUL = String.fromCharCode(0);
    const stash = [];
    const keep = (html) => NUL + (stash.push(html) - 1) + NUL;
    let s = String(src || "");
    s = s.replace(/```[^\n]*\n([\s\S]*?)```/g, (_, c) => keep(`<pre><code>${escapeHtml(c.replace(/\n$/, ""))}</code></pre>`));
    s = s.replace(/<code>([\s\S]*?)<\/code>/gi, (_, c) => keep(`<pre><code>${escapeHtml(c.replace(/^\n+|\n+$/g, ""))}</code></pre>`));
    s = s.replace(/`([^`\n]+)`/g, (_, c) => keep(`<code>${escapeHtml(c)}</code>`));
    s = escapeHtml(s);
    s = s.replace(/^\s*#{1,6}\s+(.+)$/gm, "<strong>$1</strong>");
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    s = s.replace(/(^|[^_])_([^_\n]+)_/g, "$1<em>$2</em>");
    s = s.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    // Lists: group consecutive bullet / numbered lines into a single list.
    s = s.replace(/(?:^[ \t]*(?:[-*]|\d+\.)\s+.+(?:\n|$))+/gm, (block) => {
      const ordered = /^[ \t]*\d+\./.test(block);
      const tag = ordered ? "ol" : "ul";
      const items = block.replace(/\n+$/, "").split(/\n/).map((l) => l.replace(/^[ \t]*(?:[-*]|\d+\.)\s+/, ""));
      return keep(`<${tag}>${items.map((i) => `<li>${i}</li>`).join("")}</${tag}>`);
    });
    s = s.replace(/\n/g, "<br>");
    // Restore stashed blocks (loop handles blocks nested inside other blocks).
    const restore = new RegExp(NUL + "(\\d+)" + NUL, "g");
    while (s.indexOf(NUL) !== -1) s = s.replace(restore, (_, i) => stash[+i]);
    return s;
  }

  toggle.onclick = () => setMode(!mode);
})();
