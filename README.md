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
