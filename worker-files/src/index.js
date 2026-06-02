/**
 * Cloudflare Worker — kopten-de-files
 *
 * Routen:
 *   GET  /manifest.json       — aktuelle Übersicht aller PDFs im R2-Bucket
 *   POST /rebuild-manifest    — Manifest neu aus R2 lesen + zurück nach R2
 *                                schreiben + GH-Action rebuild triggern.
 *                                Geschützt mit `Authorization: Bearer <ADMIN_TOKEN>`.
 *   GET  /admin               — kleine HTML-UI für Redakteure, die nach
 *                                einem Upload das Manifest manuell triggern
 *
 * Bindings:
 *   FILES (R2)               — Bucket "kopten-de-files"
 *
 * Secrets:
 *   GITHUB_REPO              z.B. "StMarkus/kopten.de"
 *   GITHUB_DISPATCH_TOKEN    Fine-grained PAT mit `Contents: Read & write`
 *   ADMIN_TOKEN              Shared secret zum Aufruf von /rebuild-manifest
 */

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

const ADMIN_HTML = `<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>kopten.de — R2 Manifest-Refresh</title>
<style>
  :root { --burgundy:#7a1f1f; --gold:#c9a961; --bg:#faf7f2; --ink:#1c1c1c; --soft:#4a4a4a; --paper:#fff; --border:#e5e0d8; }
  * { box-sizing:border-box; }
  html,body { margin:0; padding:0; background:var(--bg); color:var(--ink); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,system-ui,sans-serif; min-height:100vh; }
  main { max-width:540px; margin:3rem auto; padding:0 1.2rem; }
  h1 { font-family:Georgia,'Cormorant Garamond',serif; font-size:1.9rem; margin:0 0 0.3rem; color:var(--burgundy); }
  .sub { color:var(--soft); margin:0 0 2rem; font-size:0.95rem; }
  .card { background:var(--paper); border:1px solid var(--border); border-radius:12px; padding:1.5rem; box-shadow:0 4px 16px rgba(28,28,28,0.04); }
  label { display:block; font-size:0.85rem; font-weight:600; margin-bottom:0.4rem; color:var(--soft); }
  input[type=password], input[type=text] { width:100%; padding:0.65rem 0.85rem; border:1px solid var(--border); border-radius:8px; font-size:0.95rem; font-family:inherit; background:var(--paper); }
  input:focus { outline:2px solid var(--gold); outline-offset:1px; border-color:var(--gold); }
  button { background:var(--burgundy); color:#fff; border:none; padding:0.8rem 1.4rem; border-radius:8px; font-size:1rem; font-weight:600; cursor:pointer; margin-top:1rem; width:100%; transition:opacity 0.15s; }
  button:hover:not(:disabled) { opacity:0.92; }
  button:disabled { opacity:0.55; cursor:wait; }
  .ghost { background:#fff; color:var(--burgundy); border:1px solid var(--burgundy); margin-top:0.6rem; }
  .row { display:flex; gap:0.6rem; align-items:center; margin-top:0.6rem; }
  .row label { margin:0; font-size:0.85rem; color:var(--soft); font-weight:400; }
  .status { margin-top:1.2rem; padding:0.9rem 1rem; border-radius:8px; font-size:0.95rem; line-height:1.5; display:none; }
  .status.ok { background:#eaf5ee; color:#1c5b35; display:block; }
  .status.err { background:#fce8e8; color:#7a1f1f; display:block; }
  .status.info { background:#fff9eb; color:#7a5a1c; display:block; }
  .small { color:var(--soft); font-size:0.85rem; margin-top:1.4rem; line-height:1.5; }
  code { background:var(--bg); padding:0.1rem 0.35rem; border-radius:4px; font-size:0.9em; }
  details { margin-top:1rem; }
  summary { cursor:pointer; font-size:0.9rem; color:var(--soft); }
  pre { background:#1c1c1c; color:#c9a961; padding:0.8rem; border-radius:6px; overflow:auto; font-size:0.78rem; line-height:1.45; }
</style>
</head>
<body>
<main>
  <h1>Manifest-Refresh</h1>
  <p class="sub">Nach dem Upload neuer PDFs hier klicken — dann erscheinen sie auf der Webseite.</p>

  <div class="card">
    <div id="setup">
      <label for="token">Admin-Token</label>
      <input id="token" type="password" placeholder="hex-Token…" autocomplete="off" />
      <div class="row"><input type="checkbox" id="remember" checked /> <label for="remember">In diesem Browser merken</label></div>
      <button id="save">Token speichern</button>
    </div>

    <div id="action" style="display:none">
      <p style="margin:0 0 1rem;color:var(--soft);font-size:0.92rem;">Token ist gespeichert.</p>
      <button id="refresh">↻ Manifest neu bauen + Webseite aktualisieren</button>
      <button id="reset" class="ghost">Token löschen</button>
    </div>

    <div id="status" class="status"></div>

    <details>
      <summary>Details / Logs</summary>
      <pre id="log">noch keine Aktion ausgeführt</pre>
    </details>
  </div>

  <p class="small">
    Workflow:<br>
    1. <a href="https://dash.cloudflare.com" target="_blank">Cloudflare-Dashboard</a> öffnen → R2 → <code>kopten-de-files</code> → PDFs hochladen<br>
    2. Hier <em>Refresh</em> klicken → nach ~1 Min ist die Webseite aktualisiert
  </p>
</main>

<script>
const $ = (id) => document.getElementById(id);
const setup = $('setup'), action = $('action');
const status = $('status'), log = $('log');

function show(msg, type='info') {
  status.className = 'status ' + type;
  status.textContent = msg;
}
function logLine(text) {
  log.textContent = (new Date().toLocaleTimeString() + ' ' + text + '\\n') + log.textContent;
}
function init() {
  const t = localStorage.getItem('admin_token');
  if (t) { setup.style.display='none'; action.style.display='block'; }
}
$('save').onclick = () => {
  const v = $('token').value.trim();
  if (!v) { show('Bitte Token eingeben', 'err'); return; }
  if ($('remember').checked) localStorage.setItem('admin_token', v);
  else sessionStorage.setItem('admin_token', v);
  init();
  show('Token gespeichert', 'ok');
};
$('reset').onclick = () => {
  localStorage.removeItem('admin_token');
  sessionStorage.removeItem('admin_token');
  setup.style.display='block';
  action.style.display='none';
  status.style.display='none';
  $('token').value = '';
};
$('refresh').onclick = async () => {
  const t = localStorage.getItem('admin_token') || sessionStorage.getItem('admin_token');
  if (!t) { show('Kein Token vorhanden', 'err'); return; }
  $('refresh').disabled = true;
  show('Wird ausgeführt …', 'info');
  logLine('POST /rebuild-manifest');
  try {
    const r = await fetch('/rebuild-manifest', { method:'POST', headers: { 'Authorization': 'Bearer ' + t } });
    const data = await r.json();
    logLine(JSON.stringify(data, null, 2));
    if (r.ok && data.ok && data.dispatch?.ok) {
      show('✓ ' + data.manifest_stats.slugs + ' Gemeinde(n), ' + data.manifest_stats.files + ' Datei(en). Webseite wird in ~1 Min aktualisiert.', 'ok');
    } else if (data.dispatch && !data.dispatch.ok) {
      show('Manifest gebaut, aber Webseiten-Rebuild fehlgeschlagen: ' + data.dispatch.error, 'err');
    } else {
      show('Fehler: ' + (data.error || r.status), 'err');
    }
  } catch (e) {
    logLine('Exception: ' + e.message);
    show('Netzwerkfehler: ' + e.message, 'err');
  } finally {
    $('refresh').disabled = false;
  }
};
init();
</script>
</body>
</html>`;

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...CORS },
  });
}

/** Liste alle Objekte im Bucket auf und baue ein verschachteltes Manifest:
 *  { slug: { category: [{ name, size }, ...], ... }, ... }
 */
async function buildManifest(bucket) {
  const tree = {};
  let cursor;
  do {
    const listing = await bucket.list({ cursor, limit: 1000 });
    for (const obj of listing.objects) {
      if (!obj.key.toLowerCase().endsWith(".pdf")) continue;
      const parts = obj.key.split("/");
      if (parts.length < 2) continue;

      const slug = parts[0];
      const fileName = parts[parts.length - 1];
      const categoryPath = parts.slice(1, -1); // alle Zwischen-Verzeichnisse

      let node = (tree[slug] = tree[slug] || {});
      // Letztes Zwischen-Verzeichnis bekommt das Array
      const lastDir =
        categoryPath.length === 0 ? "_files" : categoryPath[categoryPath.length - 1];
      for (let i = 0; i < categoryPath.length - 1; i++) {
        const seg = categoryPath[i];
        if (!node[seg] || Array.isArray(node[seg])) node[seg] = node[seg] || {};
        node = node[seg];
      }
      if (!Array.isArray(node[lastDir])) node[lastDir] = [];
      node[lastDir].push({ name: fileName, size: obj.size });
    }
    cursor = listing.truncated ? listing.cursor : null;
  } while (cursor);

  // Sortiere Dateien innerhalb jeder Kategorie
  function sortRec(n) {
    for (const key of Object.keys(n)) {
      if (Array.isArray(n[key])) {
        n[key].sort((a, b) => a.name.localeCompare(b.name, "de"));
      } else if (typeof n[key] === "object") {
        sortRec(n[key]);
      }
    }
  }
  sortRec(tree);
  return tree;
}

async function triggerGithubRebuild(env) {
  if (!env.GITHUB_REPO || !env.GITHUB_DISPATCH_TOKEN) {
    return { ok: false, error: "github_not_configured" };
  }
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "kopten-de-files-worker",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ event_type: "files-changed" }),
  });
  return res.ok
    ? { ok: true }
    : { ok: false, error: `github_${res.status}`, body: await res.text() };
}

async function handleRebuildManifest(request, env) {
  // Auth-Check
  const auth = request.headers.get("authorization") || "";
  if (!env.ADMIN_TOKEN || auth !== `Bearer ${env.ADMIN_TOKEN}`) {
    return json({ ok: false, error: "unauthorized" }, 401);
  }

  const manifest = await buildManifest(env.FILES);
  await env.FILES.put("manifest.json", JSON.stringify(manifest, null, 2), {
    httpMetadata: {
      contentType: "application/json",
      cacheControl: "public, max-age=60",
    },
  });

  const dispatch = await triggerGithubRebuild(env);
  return json({ ok: true, manifest_stats: countStats(manifest), dispatch });
}

function countStats(manifest) {
  let slugs = 0;
  let files = 0;
  function walk(node) {
    if (Array.isArray(node)) {
      files += node.length;
      return;
    }
    if (node && typeof node === "object") {
      for (const v of Object.values(node)) walk(v);
    }
  }
  for (const slug of Object.keys(manifest)) {
    slugs++;
    walk(manifest[slug]);
  }
  return { slugs, files };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }

    if (url.pathname === "/manifest.json" && request.method === "GET") {
      const obj = await env.FILES.get("manifest.json");
      if (!obj) return json({}, 200);
      return new Response(obj.body, {
        headers: {
          "Content-Type": "application/json",
          "Cache-Control": "public, max-age=60",
          ...CORS,
        },
      });
    }

    if (url.pathname === "/rebuild-manifest" && request.method === "POST") {
      return await handleRebuildManifest(request, env);
    }

    if (url.pathname === "/admin" && request.method === "GET") {
      return new Response(ADMIN_HTML, {
        headers: { "Content-Type": "text/html; charset=utf-8", ...CORS },
      });
    }

    return json({ ok: false, error: "not_found" }, 404);
  },

  // Optional: Queue consumer — sobald CF R2 Event Notifications eingerichtet
  // sind, landen Put/Delete-Events hier. Wir bauen das Manifest neu und
  // triggern den GH-Rebuild.
  async queue(batch, env) {
    await Promise.all(batch.messages.map((m) => m.ack()));
    const manifest = await buildManifest(env.FILES);
    await env.FILES.put("manifest.json", JSON.stringify(manifest, null, 2), {
      httpMetadata: { contentType: "application/json", cacheControl: "public, max-age=60" },
    });
    await triggerGithubRebuild(env);
  },
};
