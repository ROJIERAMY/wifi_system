# WiFi café cards (simple)

One screen: pick **time** → **how many cards** → **Create**. Optional: send codes to a MikroTik router.

## Run

```powershell
cd c:\wifisystem
pip install -r requirements.txt
$env:HOTSPOT_ADMIN_PASSWORD = "your-password"
python run.py
```

Open **http://127.0.0.1:8000** — default password **`changeme`** if unset.

## Router (optional)

**Router** menu → enter MikroTik IP and login → **Test** → turn on **Allow sending cards** → **Save**. On the router, enable **API** (port 8728). Then use **Send new cards to router** on the main page.

Data file: `data/hotspot.db`.

## Public URL (online)

GitHub does **not** run the app. Use a host such as [Render](https://render.com):

1. Push this repo to GitHub (already done for `wifi_system`).
2. Sign in at [render.com](https://render.com) (use **Sign in with GitHub**).
3. **New** → **Web Service** → connect **`ROJIERAMY/wifi_system`**.
4. **Build:** `pip install -r requirements.txt`  
   **Start:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. **Environment** (important):
   - `HOTSPOT_ADMIN_PASSWORD` = your staff password  
   - `SESSION_SECRET` = long random string (or use Render’s **Generate**)
6. **Deploy Web Service**. When the build finishes, Render shows your live link, e.g. `https://wifi-system.onrender.com` (the exact name is whatever you choose in step 3).

Free instances **sleep after ~15 minutes** of no traffic; the first visit may take ~30–60s to wake up.

Optional: use the included `render.yaml` via **New** → **Blueprint** → select this repo (you may need to fill in `HOTSPOT_ADMIN_PASSWORD` when prompted).
