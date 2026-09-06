#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AREFA Workstation — macOS functional-equivalence build
=======================================================

WHAT THIS IS
------------
A native-runnable macOS build of the AREFA workstation, reconstructed from the
system's *described architecture* rather than its source bytes:

  * the front door is local AI conversation, served against Ollama qwen2.5:7b
    on 127.0.0.1 — the same model identity the source proves (id 845dbda0ea48);
  * VID3 provides governed process mining over an event log;
  * runtime state lives under a single state root, honouring the launcher's
    AREFA_STATE_ROOT contract.

WHAT THIS IS NOT
----------------
This is NOT the frozen qualified baseline and NOT the successor source. It does
not reproduce the fingerprint f7e2317a… or 85c7f4e9…, and it must never be
represented as exact historical path identity. Per the AREFA transfer contract
this is the separate "functional-equivalence mode": same behaviour and model
identity, different implementation, adapted to macOS paths.

DISCIPLINE
----------
  * Binds 127.0.0.1 only. It never listens on a network interface, matching the
    source transfer state (network_exposed: false).
  * Nothing an operator types leaves the machine: the only outbound connection
    is to the local Ollama server.
  * The model-identity guard reports PASS / DIVERGENCE exactly as the source
    discipline requires; it warns, it does not silently substitute a model.

Requires only Python 3.8+ (ships with macOS) and, for conversation, a local
Ollama serving qwen2.5:7b. The process-mining and UI work with no model present.
"""

import datetime
import http.server
import json
import os
import socket
import sys
import threading
import urllib.error
import urllib.request
import webbrowser

# ── Identity, held to the source's proven values ───────────────────────────
APP_NAME = "AREFA Workstation"
BUILD_KIND = "macOS functional-equivalence build"
EXPECTED_MODEL = "qwen2.5:7b"
EXPECTED_MODEL_ID = "845dbda0ea48"          # T00/T01A short manifest id
OLLAMA = os.environ.get("AREFA_OLLAMA_HOST", "http://127.0.0.1:11434")

DEFAULT_PORT = int(os.environ.get("AREFA_PORT", "8973"))
SYSTEM_PROMPT = (
    "You are AREFA, a sovereign local workstation assistant running entirely on "
    "the operator's own machine. You are direct, specific, and unembarrassed by "
    "detail. When you do not know something you say so rather than inventing it."
)


def state_root():
    """The single runtime state root.

    Honours AREFA_STATE_ROOT if set (the launcher contract). Otherwise uses the
    macOS-native location, which is the functional equivalent of the source's
    ~/.local/state/arefa — the contract's portable mode, not a path claim.
    """
    env = os.environ.get("AREFA_STATE_ROOT")
    if env:
        return os.path.abspath(os.path.expanduser(env))
    return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "AREFA")


STATE = state_root()
CONV_DIR = os.path.join(STATE, "conversations")


def ensure_state():
    os.makedirs(CONV_DIR, exist_ok=True)


# ── Ollama bridge ──────────────────────────────────────────────────────────

def ollama_get(path, timeout=4):
    req = urllib.request.Request(OLLAMA + path, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def model_status():
    """Reachability + exact model-identity verdict, in the source's language."""
    out = {"reachable": False, "model_present": False, "model_id": None,
           "expected_model": EXPECTED_MODEL, "expected_model_id": EXPECTED_MODEL_ID,
           "identity": "UNVERIFIED", "models": []}
    try:
        tags = ollama_get("/api/tags")
    except Exception as exc:                                   # noqa: BLE001
        out["error"] = "%s" % (exc,)
        return out
    out["reachable"] = True
    for m in tags.get("models", []):
        name = m.get("name", "")
        digest = (m.get("digest") or "").replace("sha256:", "")
        out["models"].append({"name": name, "id": digest[:12]})
        if name == EXPECTED_MODEL or name.split(":")[0] == "qwen2.5":
            out["model_present"] = True
            out["model_id"] = digest[:12]
            out["identity"] = ("PASS" if digest.startswith(EXPECTED_MODEL_ID)
                               else "DIVERGENCE")
    return out


def chat_stream(messages, handler):
    """Proxy a streaming chat turn from Ollama to the browser as it arrives."""
    body = json.dumps({"model": EXPECTED_MODEL, "messages": messages,
                       "stream": True}).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/chat", data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        upstream = urllib.request.urlopen(req, timeout=600)
    except urllib.error.URLError as exc:
        handler.send_response(503)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps(
            {"error": "ollama_unreachable", "detail": "%s" % (exc,)}).encode())
        return

    handler.send_response(200)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("X-Accel-Buffering", "no")
    handler.end_headers()
    try:
        for raw in upstream:
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            piece = obj.get("message", {}).get("content", "")
            if piece:
                handler.wfile.write(piece.encode("utf-8"))
                handler.wfile.flush()
            if obj.get("done"):
                break
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        upstream.close()


# ── VID3: governed process mining over an event log ────────────────────────

def mine(rows):
    """Directly-follows process map from (case, activity, timestamp) events.

    Honest, self-contained process mining: it groups events by case, orders each
    case by timestamp, and reports the activity frequencies, the directly-follows
    edges, the start and end activities, and the distinct variants. No inference
    beyond what the event order states.
    """
    clean = []
    for r in rows:
        case = str(r.get("case", "")).strip()
        act = str(r.get("activity", "")).strip()
        ts = str(r.get("timestamp", "")).strip()
        if case and act:
            clean.append((case, act, ts))
    if not clean:
        return {"error": "no_events", "detail": "No (case, activity) rows found."}

    cases = {}
    for case, act, ts in clean:
        cases.setdefault(case, []).append((ts, act))

    act_count, edges, starts, ends, variants = {}, {}, {}, {}, {}
    for case, evs in cases.items():
        evs.sort(key=lambda e: e[0])          # order within the case by timestamp
        seq = [a for _, a in evs]
        for a in seq:
            act_count[a] = act_count.get(a, 0) + 1
        starts[seq[0]] = starts.get(seq[0], 0) + 1
        ends[seq[-1]] = ends.get(seq[-1], 0) + 1
        for a, b in zip(seq, seq[1:]):
            edges[(a, b)] = edges.get((a, b), 0) + 1
        v = " → ".join(seq)
        variants[v] = variants.get(v, 0) + 1

    return {
        "cases": len(cases),
        "events": len(clean),
        "activities": sorted(({"activity": a, "count": c}
                              for a, c in act_count.items()),
                             key=lambda x: -x["count"]),
        "edges": sorted(({"from": a, "to": b, "count": c}
                        for (a, b), c in edges.items()), key=lambda x: -x["count"]),
        "starts": sorted(({"activity": a, "count": c} for a, c in starts.items()),
                         key=lambda x: -x["count"]),
        "ends": sorted(({"activity": a, "count": c} for a, c in ends.items()),
                       key=lambda x: -x["count"]),
        "variants": sorted(({"variant": v, "count": c} for v, c in variants.items()),
                           key=lambda x: -x["count"]),
    }


# ── Conversation persistence, under the state root ─────────────────────────

def save_conversation(cid, data):
    ensure_state()
    safe = "".join(c for c in cid if c.isalnum() or c in "-_")[:64] or "conversation"
    path = os.path.join(CONV_DIR, safe + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    return safe


def list_conversations():
    ensure_state()
    out = []
    for name in sorted(os.listdir(CONV_DIR)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(CONV_DIR, name), encoding="utf-8") as fh:
                d = json.load(fh)
            out.append({"id": name[:-5], "title": d.get("title", name[:-5]),
                        "turns": len(d.get("messages", []))})
        except Exception:                                     # noqa: BLE001
            continue
    return out


def load_conversation(cid):
    safe = "".join(c for c in cid if c.isalnum() or c in "-_")[:64]
    path = os.path.join(CONV_DIR, safe + ".json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ── HTTP surface ───────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "AREFA/equiv"

    def log_message(self, *a):                                # quiet
        return

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", "0") or "0")
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            page = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
        elif self.path == "/api/status":
            ms = model_status()
            self._json({
                "app": APP_NAME, "build": BUILD_KIND,
                "state_root": STATE, "ollama_host": OLLAMA,
                "model": ms, "conversations": list_conversations(),
                "time": datetime.datetime.now().isoformat(timespec="seconds"),
            })
        elif self.path.startswith("/api/conversation/"):
            d = load_conversation(self.path.rsplit("/", 1)[-1])
            self._json(d or {"error": "not_found"}, 200 if d else 404)
        else:
            self._json({"error": "not_found"}, 404)

    def do_POST(self):
        try:
            if self.path == "/api/chat":
                data = self._body()
                msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
                msgs += data.get("messages", [])
                chat_stream(msgs, self)
            elif self.path == "/api/mine":
                self._json(mine(self._body().get("rows", [])))
            elif self.path == "/api/conversation":
                data = self._body()
                cid = save_conversation(data.get("id", "conversation"), data)
                self._json({"saved": cid})
            else:
                self._json({"error": "not_found"}, 404)
        except BrokenPipeError:
            pass
        except Exception as exc:                              # noqa: BLE001
            try:
                self._json({"error": "server", "detail": "%s" % (exc,)}, 500)
            except Exception:                                 # noqa: BLE001
                pass


def free_port(preferred):
    for port in (preferred, 0):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", port))
            p = s.getsockname()[1]
            s.close()
            return p
        except OSError:
            continue
    return preferred


def main():
    ensure_state()
    port = free_port(DEFAULT_PORT)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = "http://127.0.0.1:%d/" % port
    bar = "=" * 70
    print(bar)
    print("%s — %s" % (APP_NAME, BUILD_KIND))
    print(bar)
    print("  Front door      : %s" % url)
    print("  State root      : %s" % STATE)
    print("  Model expected  : %s (%s)" % (EXPECTED_MODEL, EXPECTED_MODEL_ID))
    print("  Ollama host     : %s" % OLLAMA)
    print("  Bound to        : 127.0.0.1 only — never a network interface")
    print(bar)
    print("  Close this window (or Ctrl-C) to stop AREFA.")
    print(bar)
    if "--no-browser" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nAREFA stopped.")
        httpd.shutdown()


# ── Embedded single-page front door ────────────────────────────────────────
PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AREFA Workstation</title>
<style>
  :root{
    --ink:#0b0f0c; --panel:#12181300; --card:#141a15; --line:#232a24;
    --fg:#e9ece8; --mute:#8b938b; --gold:#e0a53e; --green:#61b565; --ember:#e0843e;
    --mono:"SF Mono",ui-monospace,Menlo,monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  }
  *{box-sizing:border-box}
  html,body{margin:0;height:100%}
  body{background:var(--ink);color:var(--fg);font-family:var(--sans);
    display:grid;grid-template-rows:auto auto 1fr;overflow:hidden}
  header{display:flex;align-items:center;gap:16px;padding:12px 20px;
    border-bottom:1px solid var(--line);background:#0d120e}
  .mark{font-family:var(--sans);font-weight:800;letter-spacing:.06em;font-size:18px}
  .mark b{color:var(--gold)}
  .kind{font-family:var(--mono);font-size:10px;color:var(--mute);
    text-transform:uppercase;letter-spacing:.14em;border:1px solid var(--line);
    padding:4px 8px;border-radius:3px}
  .id{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--mute);
    display:flex;gap:14px;align-items:center}
  .dot{width:8px;height:8px;border-radius:2px;background:var(--mute);display:inline-block}
  .dot.ok{background:var(--green)} .dot.warn{background:var(--ember)} .dot.bad{background:#c0392b}
  .tabs{display:flex;gap:2px;padding:0 20px;border-bottom:1px solid var(--line);background:#0d120e}
  .tab{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.12em;
    color:var(--mute);background:none;border:0;padding:12px 14px;cursor:pointer;border-bottom:2px solid transparent}
  .tab[aria-selected=true]{color:var(--fg);border-bottom-color:var(--gold)}
  main{overflow:hidden;position:relative}
  section{position:absolute;inset:0;display:none;overflow:auto;padding:20px}
  section[data-on=true]{display:block}
  /* chat */
  #chat[data-on=true]{display:grid;grid-template-rows:1fr auto;padding:0}
  #log{overflow:auto;padding:20px;display:flex;flex-direction:column;gap:16px}
  .msg{max-width:760px;line-height:1.6;white-space:pre-wrap;word-wrap:break-word}
  .msg.user{align-self:flex-end;background:#1b2a1c;border:1px solid #274428;
    padding:10px 14px;border-radius:12px 12px 2px 12px}
  .msg.arefa{align-self:flex-start}
  .msg .who{font-family:var(--mono);font-size:10px;letter-spacing:.14em;
    text-transform:uppercase;color:var(--mute);margin-bottom:5px}
  .msg.arefa .who{color:var(--gold)}
  .composer{display:flex;gap:10px;padding:14px 20px;border-top:1px solid var(--line);background:#0d120e}
  textarea{flex:1;resize:none;background:var(--card);border:1px solid var(--line);color:var(--fg);
    border-radius:8px;padding:11px 13px;font-family:var(--sans);font-size:15px;min-height:46px;max-height:160px}
  textarea:focus{outline:2px solid var(--gold);outline-offset:-1px}
  button.send{background:var(--gold);color:#1a1206;border:0;border-radius:8px;padding:0 20px;
    font-weight:700;cursor:pointer;font-size:14px}
  button.send:disabled{opacity:.5;cursor:default}
  .hint{padding:26px;max-width:640px;color:var(--mute);line-height:1.7}
  .hint code{background:var(--card);border:1px solid var(--line);padding:2px 6px;border-radius:4px;
    font-family:var(--mono);color:var(--fg)}
  /* mining */
  .grid{display:grid;gap:16px;grid-template-columns:1fr 1fr;max-width:1100px}
  .box{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px}
  .box h3{margin:0 0 12px;font-size:13px;font-family:var(--mono);letter-spacing:.1em;
    text-transform:uppercase;color:var(--gold)}
  table{width:100%;border-collapse:collapse;font-size:13px}
  td,th{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
  th{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--mute)}
  td.n{text-align:right;font-family:var(--mono);color:var(--gold)}
  .drop{border:1px dashed var(--line);border-radius:8px;padding:22px;text-align:center;color:var(--mute);
    margin-bottom:16px;cursor:pointer}
  .drop.hot{border-color:var(--gold);color:var(--fg)}
  .lead{max-width:760px;color:var(--mute);line-height:1.65;margin:0 0 16px}
  .kv{font-family:var(--mono);font-size:12px;line-height:1.9}
  .kv b{color:var(--fg);font-weight:400} .kv .k{color:var(--mute);display:inline-block;min-width:190px}
  a{color:var(--gold)}
</style></head><body>
<header>
  <span class="mark">A<b>R</b>EFA</span>
  <span class="kind" id="buildKind">functional-equivalence build</span>
  <span class="id">
    <span><span class="dot" id="oDot"></span> Ollama</span>
    <span><span class="dot" id="mDot"></span> <span id="mLabel">model</span></span>
  </span>
</header>
<nav class="tabs" role="tablist">
  <button class="tab" role="tab" data-tab="chat" aria-selected="true">Conversation</button>
  <button class="tab" role="tab" data-tab="mine" aria-selected="false">VID3 · Process mining</button>
  <button class="tab" role="tab" data-tab="about" aria-selected="false">System</button>
</nav>
<main>
  <section id="chat" data-on="true">
    <div id="log"></div>
    <div class="composer">
      <textarea id="in" placeholder="Talk to AREFA — runs entirely on this machine"></textarea>
      <button class="send" id="send">Send</button>
    </div>
  </section>
  <section id="mine">
    <p class="lead">VID3 governed process mining. Drop a CSV event log with columns
      <code>case</code>, <code>activity</code>, <code>timestamp</code> (any order; extra columns ignored).
      Every figure below is computed here, on this machine, from the rows you provide.</p>
    <div class="drop" id="drop">Drop a CSV here, or click to choose a file</div>
    <input type="file" id="file" accept=".csv,text/csv" hidden>
    <div id="mineOut"></div>
  </section>
  <section id="about">
    <p class="lead">This is the <b id="k2">macOS functional-equivalence build</b> of the AREFA
      workstation — the system's described architecture, adapted to run on your Mac. It is
      <b>not</b> the frozen qualified baseline and not the successor source; it does not reproduce
      those fingerprints and must not be represented as exact historical identity.</p>
    <div class="kv" id="sys"></div>
  </section>
</main>
<script>
const $=s=>document.querySelector(s), log=$("#log");
let history=[], busy=false;

function tab(name){
  document.querySelectorAll('.tab').forEach(t=>t.setAttribute('aria-selected',String(t.dataset.tab===name)));
  document.querySelectorAll('main section').forEach(s=>s.dataset.on=String(s.id===name));
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>tab(t.dataset.tab));

function bubble(who,cls){
  const d=document.createElement('div'); d.className='msg '+cls;
  d.innerHTML='<div class="who">'+who+'</div><div class="body"></div>';
  log.appendChild(d); log.scrollTop=log.scrollHeight; return d.querySelector('.body');
}
async function send(){
  const t=$("#in").value.trim(); if(!t||busy) return;
  $("#in").value=''; busy=true; $("#send").disabled=true;
  bubble('You','user').textContent=t;
  history.push({role:'user',content:t});
  const out=bubble('AREFA','arefa'); out.textContent='…';
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({messages:history})});
    if(!r.ok){ const e=await r.json().catch(()=>({}));
      out.textContent='[ AREFA could not reach the local model. '+
        'Start Ollama and pull qwen2.5:7b — see the System tab. ]'+
        (e.detail?'\n\n'+e.detail:''); busy=false; $("#send").disabled=false; return; }
    const reader=r.body.getReader(), dec=new TextDecoder(); let acc='';
    out.textContent='';
    while(true){ const {done,value}=await reader.read(); if(done) break;
      acc+=dec.decode(value,{stream:true}); out.textContent=acc; log.scrollTop=log.scrollHeight; }
    history.push({role:'assistant',content:acc});
  }catch(err){ out.textContent='[ error: '+err+' ]'; }
  busy=false; $("#send").disabled=false; $("#in").focus();
}
$("#send").onclick=send;
$("#in").addEventListener('keydown',e=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}});

// mining
function parseCSV(text){
  const lines=text.replace(/\r/g,'').split('\n').filter(l=>l.trim().length);
  if(!lines.length) return [];
  const head=lines[0].split(',').map(h=>h.trim().toLowerCase());
  const ci=head.findIndex(h=>/case|trace|id/.test(h));
  const ai=head.findIndex(h=>/activity|action|event|step|task/.test(h));
  const ti=head.findIndex(h=>/time|date|ts|stamp/.test(h));
  return lines.slice(1).map(l=>{const c=l.split(',');
    return {case:(c[ci]||'').trim(),activity:(c[ai]||'').trim(),timestamp:(c[ti]||'').trim()};});
}
async function runMine(text){
  const rows=parseCSV(text);
  const r=await fetch('/api/mine',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({rows})});
  const d=await r.json(); const o=$("#mineOut");
  if(d.error){ o.innerHTML='<div class="box">No usable events found. Check that the CSV has case and activity columns.</div>'; return; }
  const tbl=(title,rows,cols)=>'<div class="box"><h3>'+title+'</h3><table><tr>'+
    cols.map(c=>'<th>'+c[0]+'</th>').join('')+'</tr>'+
    rows.slice(0,25).map(x=>'<tr>'+cols.map(c=>'<td'+(c[2]?' class="n"':'')+'>'+
      (c[2]?x[c[1]]:String(x[c[1]]))+'</td>').join('')+'</tr>').join('')+'</table></div>';
  o.innerHTML='<div class="kv" style="margin-bottom:16px">'+
      '<div><span class="k">Cases</span><b>'+d.cases+'</b></div>'+
      '<div><span class="k">Events</span><b>'+d.events+'</b></div>'+
      '<div><span class="k">Distinct variants</span><b>'+d.variants.length+'</b></div></div>'+
    '<div class="grid">'+
    tbl('Activity frequency',d.activities,[['Activity','activity'],['Count','count',1]])+
    tbl('Directly-follows edges',d.edges,[['From','from'],['To','to'],['Count','count',1]])+
    tbl('Start activities',d.starts,[['Activity','activity'],['Cases','count',1]])+
    tbl('End activities',d.ends,[['Activity','activity'],['Cases','count',1]])+
    '</div><div class="box" style="margin-top:16px"><h3>Variants</h3><table>'+
    '<tr><th>Path</th><th>Cases</th></tr>'+d.variants.slice(0,20).map(v=>'<tr><td>'+
      v.variant+'</td><td class="n">'+v.count+'</td></tr>').join('')+'</table></div>';
}
const drop=$("#drop"), file=$("#file");
drop.onclick=()=>file.click();
file.onchange=e=>{const f=e.target.files[0]; if(f) f.text().then(runMine);};
['dragover','dragenter'].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.add('hot');}));
['dragleave','drop'].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.remove('hot');}));
drop.addEventListener('drop',e=>{const f=e.dataTransfer.files[0]; if(f) f.text().then(runMine);});

// status
async function status(){
  try{
    const s=await fetch('/api/status').then(r=>r.json());
    $("#buildKind").textContent=s.build; $("#k2").textContent=s.build;
    const m=s.model;
    $("#oDot").className='dot '+(m.reachable?'ok':'bad');
    $("#mDot").className='dot '+(m.identity==='PASS'?'ok':(m.model_present?'warn':'bad'));
    $("#mLabel").textContent=m.model_present?(m.expected_model+' · '+(m.model_id||'?')+' · '+m.identity):'model missing';
    $("#sys").innerHTML=[
      ['Build',s.build],['State root',s.state_root],['Ollama host',s.ollama_host],
      ['Model expected',m.expected_model+'  ('+m.expected_model_id+')'],
      ['Model present',m.model_present?'yes':'no'],
      ['Measured id',m.model_id||'—'],
      ['Identity verdict',m.identity],
      ['Network exposure','none — bound to 127.0.0.1 only'],
      ['Conversations stored',String((s.conversations||[]).length)],
    ].map(r=>'<div><span class="k">'+r[0]+'</span><b>'+r[1]+'</b></div>').join('')+
    (m.reachable?'':'<div style="margin-top:16px;color:var(--ember)">Ollama is not running. Install it '+
      '(<b>brew install ollama</b> or the Ollama.app), then <b>ollama serve</b> and '+
      '<b>ollama pull qwen2.5:7b</b>. Conversation lights up once the model answers on 127.0.0.1:11434.</div>');
  }catch(e){}
}
status(); setInterval(status,4000);
bubble('AREFA','arefa').textContent=
  "AREFA workstation, running locally on your Mac. Ask me anything. "+
  "If this reply is the only thing I ever say, the local model isn't answering yet — open the System tab.";
$("#in").focus();
</script></body></html>"""


if __name__ == "__main__":
    main()
