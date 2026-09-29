"""Local web UI: python -m scriptbench.web  ->  http://127.0.0.1:8000

Standard library only. It binds to localhost, so the API key never leaves
this machine and nobody else can spend your quota.
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .generator import generate_detailed
from .llm import LLMError

MAX_BODY_BYTES = 10_000


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in ("/", "/index.html"):
            self._send(404, "text/plain", b"not found")
            return
        self._send(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))

    def do_POST(self) -> None:
        if self.path != "/api/generate":
            self._send(404, "text/plain", b"not found")
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self._json(413, {"error": "request too large"})
            return
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
            result = generate_detailed(
                str(data.get("niche", "")),
                str(data.get("topic", "")),
                int(data.get("seconds", 0)),
                offline=bool(data.get("offline")),
            )
        except (ValueError, TypeError) as err:
            self._json(400, {"error": str(err)})
            return
        except LLMError as err:
            message = ("Every AI model is busy right now (Google reports high demand)."
                       if err.transient else str(err).split("\n")[0])
            self._json(503, {"error": message, "transient": err.transient})
            return
        self._json(200, {**result.script, "meta": result.meta})

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, "application/json", json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # keep the console readable
        sys.stderr.write(f"{self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scriptbench.web")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Script Bench running at http://127.0.0.1:{args.port}  (Ctrl+C to stop)", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Script Bench</title>
<style>
  :root { --bg:#f7f7f5; --card:#fff; --ink:#1b1b1b; --muted:#6b6b6b; --line:#e3e3df;
          --accent:#2f5bea; --warn:#b54708; --bad:#b42318; --ok:#067647; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#141414; --card:#1e1e1e; --ink:#ececec; --muted:#9a9a9a; --line:#333;
            --accent:#7c9bff; --warn:#f5a524; --bad:#ff6b5e; --ok:#3ccf8e; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
  main { max-width:760px; margin:0 auto; padding:32px 16px 64px; }
  h1 { margin:0 0 4px; font-size:28px; }
  .sub { color:var(--muted); margin:0 0 24px; }
  form, .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:20px; }
  label { display:block; font-weight:600; font-size:14px; margin:0 0 6px; }
  input[type=text], select { width:100%; padding:10px 12px; font:inherit; color:inherit;
         background:var(--bg); border:1px solid var(--line); border-radius:8px; margin-bottom:16px; }
  .row { display:flex; gap:16px; align-items:end; flex-wrap:wrap; }
  .row > div { flex:1; min-width:140px; }
  .check { display:flex; gap:8px; align-items:center; font-weight:400; margin-bottom:16px; }
  button { background:var(--accent); color:#fff; border:0; border-radius:8px; padding:11px 20px;
           font:inherit; font-weight:600; cursor:pointer; }
  button:disabled { opacity:.6; cursor:wait; }
  #out { margin-top:24px; }
  .section { margin-bottom:20px; }
  .tag { font-size:12px; font-weight:700; letter-spacing:.06em; color:var(--muted); }
  .tag span { font-weight:400; letter-spacing:0; }
  .hook { font-size:22px; font-weight:650; line-height:1.35; }
  .body p { margin:0 0 10px; }
  .meta { border-top:1px solid var(--line); padding-top:14px; font-size:14px; color:var(--muted); }
  .meta ul { margin:6px 0 0; padding-left:20px; }
  .hard { color:var(--bad); } .soft { color:var(--warn); } .good { color:var(--ok); }
  .err { color:var(--bad); background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; }
  details { margin-top:10px; } summary { cursor:pointer; }
</style>
</head>
<body>
<main>
  <h1>Script Bench</h1>
  <p class="sub">Turn an idea into a short-form video script, timed to your runtime.</p>

  <form id="f">
    <label for="niche">Niche</label>
    <input id="niche" type="text" required value="fitness" placeholder="e.g. personal finance">
    <label for="topic">Topic (one sentence)</label>
    <input id="topic" type="text" required value="Why stretching before lifting is overrated">
    <div class="row">
      <div>
        <label for="seconds">Runtime</label>
        <select id="seconds"><option>30</option><option selected>45</option><option>60</option></select>
      </div>
      <div><label class="check"><input id="offline" type="checkbox"> Offline (templates only, no AI)</label></div>
    </div>
    <button id="go">Generate script</button>
  </form>

  <div id="out"></div>
</main>
<script>
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

$("f").addEventListener("submit", async e => {
  e.preventDefault();
  const btn = $("go");
  btn.disabled = true;
  btn.textContent = $("offline").checked ? "Generating..." : "Writing with AI (can take up to a minute)...";
  $("out").innerHTML = "";
  try {
    const res = await fetch("/api/generate", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ niche: $("niche").value, topic: $("topic").value,
                             seconds: +$("seconds").value, offline: $("offline").checked })
    });
    const d = await res.json();
    if (!res.ok) {
      const hint = d.transient ? "<br><br>The AI service is busy right now. Try again in a minute, or tick Offline." : "";
      $("out").innerHTML = `<div class="err">${esc(d.error)}${hint}</div>`;
      return;
    }
    render(d);
  } catch (err) {
    $("out").innerHTML = `<div class="err">Could not reach the local server: ${esc(err.message)}</div>`;
  } finally {
    btn.disabled = false; btn.textContent = "Generate script";
  }
});

function render(d) {
  const m = d.meta, s = m.section_seconds;
  const diff = Math.abs(m.estimated_seconds - m.target_seconds) / m.target_seconds;
  const issues = m.issues.map(i => `<li class="${i.severity}">[${i.severity}] ${esc(i.message)}</li>`).join("");
  const verify = (m.verify || []).map(v => `<li>${esc(v)}</li>`).join("");
  const hooks = (m.hook_candidates || []).map(h =>
    `<li><b>${esc(h.style)}</b> (score ${h.score}): ${esc(h.text)}</li>`).join("");
  $("out").innerHTML = `
    <div class="card">
      <div class="section"><div class="tag">HOOK <span>~${Math.round(s.hook)}s</span></div>
        <div class="hook">${esc(d.hook)}</div></div>
      <div class="section body"><div class="tag">BODY <span>~${Math.round(s.body)}s</span></div>
        ${d.body.split("\\n\\n").map(p => `<p>${esc(p)}</p>`).join("")}</div>
      <div class="section"><div class="tag">CTA <span>~${Math.round(s.cta)}s</span></div>
        <div>${esc(d.cta)}</div></div>
      <div class="meta">
        <span class="${diff <= 0.12 ? "good" : "hard"}">~${Math.round(m.estimated_seconds)}s spoken (target ${m.target_seconds}s)</span>
        &middot; engine: ${esc(m.engine)}
        ${m.revisions !== undefined ? `&middot; revisions: ${m.revisions}` : ""}
        &middot; score: ${m.score}/100
        ${m.hook_style ? `<br>hook style: ${esc(m.hook_style)}` : ""}
        ${issues ? `<ul>${issues}</ul>` : ""}
        ${verify ? `<div style="margin-top:10px"><b>Check before filming:</b><ul>${verify}</ul></div>` : ""}
        ${hooks ? `<details><summary>All hook candidates</summary><ul>${hooks}</ul></details>` : ""}
      </div>
    </div>`;
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
