# AREFA Workstation

### ▶ Use it now, no install: **https://gsmadoda.github.io/arefa-workstation-mac/**

Open that link in **desktop Chrome or Edge**. The model runs in your browser — no
sign-in, no key, nothing leaves your machine. (This page you are reading is just
the project's description. The link above is the actual app.)

A native-runnable build of the AREFA workstation — hosted (in-browser, above) or
fully local on macOS (below).

## What this is, and is not — read first

This is a **functional-equivalence build**, reconstructed from AREFA's described
architecture:

- the front door is **local AI conversation**, served against **Ollama
  `qwen2.5:7b`** on `127.0.0.1` — the same model identity the source proves
  (id `845dbda0ea48`);
- **VID3** provides governed **process mining** over an event log;
- runtime state lives under a single **state root**, honouring the launcher's
  `AREFA_STATE_ROOT` contract.

It is **not** the frozen qualified baseline and **not** the successor source. It
does not reproduce the fingerprints `f7e2317a…` (frozen) or `85c7f4e9…`
(successor), and it must never be represented as exact historical path identity.
Your own AREFA transfer contract names this the *separate functional-equivalence
mode* — same behaviour and model identity, different implementation, adapted to
macOS. That distinction is stated on the app's **System** tab too, so no one
mistakes it for the audited system.

Why a fresh implementation rather than the real bytes: the AREFA application
(`/usr/local/arefa`, and the successor `lib/arefa/`) was never transferred into
this session — only launchers, gate reports, and the Linux Ollama binary were.
This build is what can be made honestly from the architecture in hand. If you
send `/usr/local/arefa`, a byte-faithful port becomes possible; see the end.

## Two ways to use it

**Hosted, in your browser** — <https://gsmadoda.github.io/arefa-workstation-mac/>.
The model runs on WebGPU *inside the visitor's own browser tab* — the page is
static (GitHub Pages), there is no backend, no API key, and nothing typed leaves
the device. Pick a Qwen2.5 size and load it; the first load downloads the model
and caches it. Needs a recent **Chrome or Edge** (desktop) with WebGPU; the
process-mining tab works in any browser. This keeps AREFA's sovereign posture: it
is hosted on the internet, but every conversation stays local to whoever uses it.
The in-browser model is an MLC build of Qwen2.5 — the same family as the source
`qwen2.5:7b`, not its exact Ollama quantization/digest.

**Fully local** — clone and run (below). Runs the *exact* source model
(`qwen2.5:7b` via Ollama) on your machine, works offline, no browser-model
download. This is the strictest-posture option.

## Requirements

## Requirements

| Need | For | Install |
|---|---|---|
| **Python 3.8+** | the app itself | ships with macOS (or `xcode-select --install`) |
| **Ollama** + `qwen2.5:7b` | conversation | `brew install ollama`, then `ollama pull qwen2.5:7b` |

The UI and VID3 process mining work with **no model present**. Only the
conversation tab needs Ollama.

## Run it — three ways, easiest first

### 1. Double-click
Open the folder in Finder and double-click **`AREFA (double-click me).command`**.
A Terminal window runs AREFA and your browser opens to it. Close the window to stop.

> First time, macOS may say the file is from an unidentified developer. Right-click
> it → **Open** → **Open**. You only do this once.

### 2. As a real app (`AREFA.app`)
```bash
cd AREFA_Workstation_mac
./build_app.sh                       # or: ./build_app.sh /path/to/1024x1024.png  to set an icon
```
This refreshes the bundle, optionally builds an icon, and ad-hoc code-signs it so
Gatekeeper allows it. Then move **`AREFA.app`** to `/Applications` and double-click.

### 3. From the terminal
```bash
python3 arefa_workstation.py
```

## Check the machine first (optional)
```bash
./preflight.sh
```
Read-only. Reports whether Python and Ollama are present and whether the model
identity is **PASS** or **DIVERGENCE** against `845dbda0ea48` — the same check
the app runs live, and the same discipline as the intern install script: it never
substitutes a different model to make things pass.

## What it does

**Conversation** — talk to `qwen2.5:7b` running locally. Streamed token by token.
Nothing you type leaves the machine; the only outbound connection is to your local
Ollama.

**VID3 · Process mining** — drop a CSV event log with `case`, `activity`,
`timestamp` columns. It computes activity frequencies, the directly-follows graph,
start/end activities and distinct variants — all on your machine, from your rows.
There is a sample log at `sample_eventlog.csv`.

**System** — live status: Ollama reachability, the model-identity verdict, the
state root, and an explicit statement that this is the functional-equivalence
build. This is where the app tells the truth about what it is.

## Where it keeps things

`AREFA_STATE_ROOT`, or by default `~/Library/Application Support/AREFA` — the
macOS-native equivalent of the source's `~/.local/state/arefa`. Conversations are
saved there as JSON; `arefa.log` collects launch output.

## Security posture (matches the source contract)

- **Bound to `127.0.0.1` only.** AREFA never listens on a network interface,
  matching the source transfer state `network_exposed: false`. It is not reachable
  from other machines, and you should not put it behind a tunnel.
- **Local model only.** Conversation goes to `127.0.0.1:11434` and nowhere else.
- **No provenance claims.** This build asserts nothing about the audited system's
  fingerprints. It is clearly labelled, in the UI and here, as functional
  equivalence.

## If you want the byte-faithful port instead

Send the actual runtime and successor library — small, ~2.5 MB (run these on the
AREFA machine, substituting your own successor-tree path for `$SUCCESSOR`):
```bash
tar czf ~/arefa_runtime_for_mac.tar.gz -C / usr/local/arefa
tar czf ~/arefa_successor_lib.tar.gz -C "$SUCCESSOR" source/lib/arefa source/share/arefa
```
The single fact that decides the port's shape is which GUI toolkit `arefa-gui`
uses. Fastest way to tell me without uploading anything:
```bash
head -40 /usr/local/arefa/bin/arefa-gui
grep -rhoE '^[[:space:]]*(import|from)[[:space:]]+[A-Za-z_.]+' /usr/local/arefa | sort -u
```
