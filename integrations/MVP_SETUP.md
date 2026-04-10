# MVP setup: Space API + studio key + Blender + smoke test

This guide assumes you are new to this stack. The **goal** is one working HTTPS endpoint that runs MeshAnything V2, and your machine calling it with a **single shared studio key**.

---

## Q1 — What is “best” for you?

| Approach | When it wins |
|----------|----------------|
| **Docker on Hugging Face Spaces (recommended MVP)** | You want a GPU in the cloud without renting a VM yourself. HF builds your `Dockerfile`, serves HTTPS, and you only push git. |
| **Docker on a VPS (RunPod, Lambda, AWS GPU)** | You need custom queues, long jobs, or fixed IP. More ops work. |
| **Run Python directly on your PC** | Only if you have enough **VRAM** (upstream notes ~8 GB; **6 GB is often too tight**). You also fight Windows + CUDA + `flash-attn` builds. |

**For your situation (6 GB laptop, no infra experience): use HF Spaces + Docker** for inference, and run the **client** (Blender / `test_mvp.py`) on your machine.

---

## Part A — Hugging Face Space (Docker)

### A1. Prerequisites

- A [Hugging Face](https://huggingface.co) account.
- This repo pushed to **your** GitHub (or HF Git). The repo root must contain the **`Dockerfile`** we added.
- A **paid GPU** on Space (or CPU-only will **not** run this model in practice). Pick at least a small GPU (e.g. T4 class) for testing; larger is faster.

### A2. Step 2 — Create a Docker Space (pick one path)

You need: **Docker SDK**, **GPU hardware**, and **this repo’s code** on the Space (via Git push or GitHub sync).

#### Can the AI “run HF CLI for you”?

**Not with your account.** Creating a Space needs a **write token** tied to **your** Hugging Face login. Anyone helping you can only give commands; **you** run them in your own terminal (or add your token to an environment you control). Never paste a full `hf_…` token into chat.

---

#### Path W — Web UI (good if you dislike the terminal)

1. Log in at [huggingface.co](https://huggingface.co).
2. **[Spaces](https://huggingface.co/spaces)** → **Create new Space**.
3. **Owner / name**: e.g. `Mansur333` / `ma2-api` (name must be unique in your namespace).
4. **License** / **Visibility**: set **Private** if you want.
5. **SDK**: **Docker** (not Gradio).
6. **Hardware**: choose a **GPU** (e.g. **T4 small** is a common entry tier for tests). CPU-only will not run this model.
7. **Repo**: either **(a)** create an **empty** Space and push git later (step A2c), or **(b)** if the UI offers **“Import from GitHub”**, pick [github.com/mansvr/MA2](https://github.com/mansvr/MA2) and branch `main`.

Reference: [Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker), [Spaces overview](https://huggingface.co/docs/hub/spaces-overview).

---

#### Path C — Python script (same result as the UI; good for repeatability)

Requires **`huggingface_hub`** (already pulled in with many ML installs; upgrade if needed):

```powershell
pip install -U "huggingface_hub>=0.20"
$env:HF_TOKEN = "hf_..."   # create at https://huggingface.co/settings/tokens — use “write” for repo creation
cd o:\MeshanythingV2
python integrations\scripts\create_hf_space.py --repo-id YourHFUsername/ma2-api --hardware t4-small --private
```

Replace `YourHFUsername/ma2-api` with your real Hub namespace and Space name.  
`--hardware` accepts values like `cpu-basic`, `t4-small`, `t4-medium`, `l4x1`, `a10g-small` (see script error message for the full list).

If the Space **already exists**, add `--exist-ok` or delete/rename the Space on the Hub first.

---

#### Path L — Classic `huggingface-cli` (older installs)

If you have the legacy CLI (no `hf` command):

```powershell
huggingface-cli login
huggingface-cli repo create ma2-api --type space --space_sdk docker -y
```

That creates `YourUsername/ma2-api` on the Hub. **Hardware tier** is not always exposed here — set GPU in the Space **Settings → Hardware** on the website, or use **Path C** instead.

---

#### A2c. Push this repo to the Space (if the Space is not auto-synced from GitHub)

From your clone (with `main` containing `Dockerfile` + YAML in `README.md`):

```powershell
cd o:\MeshanythingV2
git remote add hf https://huggingface.co/spaces/YourHFUsername/ma2-api
git push hf main
```

Use the **exact** Space URL from the Hub (`https://huggingface.co/spaces/USER/NAME` → git remote is `https://huggingface.co/spaces/USER/NAME`). If `git push` asks for credentials, use your **HF username** and **token** as the password.

**Newer CLI:** after `pip install -U huggingface_hub`, you may get the `hf` command. Then you can also use `hf upload` / sync patterns; the git remote above is the most straightforward for a full repo.

This repo’s root **`README.md` now starts with YAML** (`sdk: docker`, `app_port: 7860`) so the Space is recognized as a **Docker** Space when the files are on the Hub.

### A3. Space settings (secrets)

In the Space → **Settings** → **Repository secrets** (or **Variables** depending on UI):

- **`MESHANYTHING_SERVER_API_KEY`**  
  - Value: a long random string (your **one shared studio key**).  
  - Example generation (run locally):  
    `[Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))`  
    or use a password manager.

Clients send the studio secret as **`Authorization: Bearer …`** when the Space is **public** and you are not using an HF user token.

If the Space is **private**, Hugging Face expects your **HF user token** in `Authorization` instead. In that case clients send the studio secret in **`X-MeshAnything-Key`** (the addon and `meshanything_client` do this automatically when you set `MESHANYTHING_HF_TOKEN`).

### A3b. Your Space (example)

| | |
|--|--|
| **Space page** | [huggingface.co/spaces/Mansur333/meshanythingv2-fromlocal](https://huggingface.co/spaces/Mansur333/meshanythingv2-fromlocal) |
| **API base URL** | `https://mansur333-meshanythingv2-fromlocal.hf.space` |

Use that **`.hf.space`** URL as `MESHANYTHING_API_BASE` (no trailing slash). It is different from the `huggingface.co/spaces/...` browser link.

**Sleeping:** Spaces **pause** when idle. The first request after sleep can take **1–3+ minutes** (cold start + model load). Open the Space page in a browser and wait until the app shows “Running,” or upgrade the Space for shorter sleeps / always-on if your plan allows.

**Private Space:** Create a **read** token under [Settings → Access Tokens](https://huggingface.co/settings/tokens) and set `MESHANYTHING_HF_TOKEN` (or `HF_TOKEN`) to `hf_...`. Keep your studio secret in `MESHANYTHING_API_KEY` and/or Space secret `MESHANYTHING_SERVER_API_KEY` as before.

### A4. Build

- First build can take **20–60+ minutes** (PyTorch + `flash-attn` compile).
- If the build times out, upgrade HF build resources or retry; check **Build logs** in the Space.

### A5. URL

Your API base is:

`https://<your-username>-<space-name>.hf.space`

(lowercase; no trailing slash). Example: `https://mansur333-meshanythingv2-fromlocal.hf.space`. Use this as **`MESHANYTHING_API_BASE`** everywhere—not the `huggingface.co/spaces/...` URL.

### A6. README / Space card

The **YAML frontmatter** at the top of `README.md` in this fork configures the Space card (`sdk: docker`, etc.). Adjust `title` / `emoji` there if you like (see [HF Spaces docs](https://huggingface.co/docs/hub/spaces-sdks-landing)).

---

## Part B — Smoke test from your PC (before Blender)

### B1. Install client dependencies

From repo root:

```powershell
cd o:\MeshanythingV2\integrations\meshanything_client
pip install -e .
pip install requests
```

### B2. Point env at your Space

```powershell
$env:MESHANYTHING_API_BASE = "https://mansur333-meshanythingv2-fromlocal.hf.space"
$env:MESHANYTHING_API_KEY = "your-studio-shared-secret"
# Private Space only — read token from https://huggingface.co/settings/tokens
$env:MESHANYTHING_HF_TOKEN = "hf_..."
```

If the Space is **public** and you did **not** set `MESHANYTHING_SERVER_API_KEY` on the server, you can omit both `MESHANYTHING_API_KEY` and `MESHANYTHING_HF_TOKEN` for a quick test (not for production).

### B3. Run the test script

From repo root:

```powershell
cd o:\MeshanythingV2
python integrations\scripts\test_mvp.py
```

Expect:

1. `GET /v1/health` → `200` and `"model_loaded": true`.
2. A file `integrations\scripts\mvp_test_output.obj` written.

**Optional knobs (CLI via env for `test_mvp.py`):** `MESHANYTHING_TARGET_FACE_COUNT`, `MESHANYTHING_OPTIMIZATION_STRENGTH` (`conservative` \| `moderate` \| `aggressive`), `MESHANYTHING_ENABLE_AI_STYLE=1`. Same fields exist on **POST `/v1/optimize`** and in the **Blender addon** preferences.

### B3b — “Old Gradio” Space vs this Docker API

Some Spaces show a **slider “target face count”** and text like **“standard Trimesh methods”**. That pattern is **classic mesh decimation** (trimesh / quadric), not the neural MeshAnything V2 forward pass. This repo’s **neural** path is controlled by **`mc` / `mc_level` / `sampling` / `seed`** (see `main.py`). To get **similar UX** to a target face count, the v1 API now applies **optional trimesh quadric decimation** *after* inference when you set **`target_face_count`** or **`optimization_strength`**. That does not change the model; it only caps polygon count on the reconstructed mesh.

**Trimesh-only endpoint (matches [meshanythingv2-fromlocal](https://huggingface.co/spaces/Mansur333/meshanythingv2-fromlocal)):** **`POST /v1/decimate`** — upload **`.obj` / `.ply` / `.stl`**, no GPU weights required. Same idea as the Streamlit app: quadric decimation, cleaning, optional orange vertex colors. Client: `MeshAnythingClient.decimate_file(...)`. Smoke test: `python integrations/scripts/test_decimate.py` (same `MESHANYTHING_API_BASE` env as `test_mvp.py`).

**If the OBJ looks wrong** (e.g. one triangle or extreme loss of detail): try **`MESHANYTHING_ENABLE_AI_STYLE=1`** and/or a different **`seed`**; enable **marching cubes** preprocess for difficult geometry (`mc=true`, `mc_level` 7–8). Degenerate outputs are usually model / conditioning issues, not the decimation step.

If you get **401**, check: (1) studio key matches `MESHANYTHING_SERVER_API_KEY` if you use one; (2) for **private** Spaces, `MESHANYTHING_HF_TOKEN` must be a valid `hf_...` token.  
If **403** from HF, the Space is private and you forgot the HF token.  
If **502/503**, the Space is still building, **sleeping** (wait and retry), or the model crashed on startup — open **Space logs**.

---

## Part C — Blender addon

1. Zip the folder **`integrations\blender_meshanything`** so the zip contains `blender_meshanything\__init__.py` at the top level (not an extra parent folder).
2. Blender → **Edit → Preferences → Add-ons → Install** → pick the zip → enable **MeshAnything Space API**.
3. In addon preferences set **API base URL** to your `https://....hf.space`.
4. Set **Hugging Face token** if the Space is **private** (`hf_...`).
5. Set **Studio API key** if your server uses `MESHANYTHING_SERVER_API_KEY`.
6. In the 3D View sidebar (**MeshAnything** tab), select a mesh, run **MeshAnything optimize**.

Optional env vars (same as client):

- `MESHANYTHING_API_BASE`
- `MESHANYTHING_API_KEY`
- `MESHANYTHING_HF_TOKEN` (or `HF_TOKEN`)

---

## Part D — Local API on your machine (optional, advanced)

Only if you have a **suitable GPU** and a full conda env matching the upstream README (torch 2.1 + CUDA 11.8 + `flash-attn` + `pip install -r requirements.txt`).

```powershell
cd o:\MeshanythingV2
$env:PYTHONPATH = "o:\MeshanythingV2"
$env:MESHANYTHING_SERVER_API_KEY = "local-test-secret"
cd integrations\space_api
python -m uvicorn app:app --host 127.0.0.1 --port 7860
```

Then:

```powershell
$env:MESHANYTHING_API_BASE = "http://127.0.0.1:7860"
$env:MESHANYTHING_API_KEY = "local-test-secret"
python integrations\scripts\test_mvp.py
```

---

## Troubleshooting

| Symptom | Likely cause |
|--------|----------------|
| Build fails on `flash-attn` | CUDA/torch mismatch; check **Build logs**. May need a larger HF builder. |
| Health OK but optimize 500 | Model OOM on small GPU; try a larger Space GPU or reduce batch (already 1). |
| 401 | Key mismatch; unset server secret to disable auth (dev only) or align Bearer token. |
| Cold start slow | HF free/paused Spaces; upgrade or keep “always on” if available. |
| **404 on `POST /v1/decimate`** | The Space is running an **old Docker image** from before that route existed. Push the current repo (with `integrations/space_api/trimesh_decimate.py` + `app.py` route) and let HF **rebuild**. `GET /` should mention `decimate` in JSON when the new image is live. |

---

## Q2 — One shared key per studio

Implemented as: **`MESHANYTHING_SERVER_API_KEY`** on the server, **`MESHANYTHING_API_KEY`** on clients. Same key for all seats until you add a gateway later.

---

## Q3 — Tier 3

Skipped per your choice; v1 stays **mesh → optimized OBJ** via REST.
