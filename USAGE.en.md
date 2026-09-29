# Usage Guide

Day-to-day reference once the bot is already installed and running. See [INSTALL.en.md](INSTALL.en.md) if you haven't installed it yet.

*[Leer en español (USO.es.md)](USO.es.md)*

## How to read the alerts

Each message looks like this:

```
📻🚨 Apertura en 6 m (50 MHz) relacionada con Costa Rica (TI):

• 📥 [PSKReporter] TI2XYZ (EJ89au) recibió a LU5FF (FF99pd, Argentina) en 50.3146 MHz FT8 (SNR -8)
• 📤 [Cluster (Spothole)] TI2OY fue escuchado por PY1XYZ (GG87, Brazil) en 50.1150 MHz SSB (SNR -)
```

(The message text itself stays in Spanish by default — see [HOW_IT_WORKS.en.md](HOW_IT_WORKS.en.md) if you want to translate it.)

- **📥** = a TI station **received/heard** someone from abroad.
- **📤** = a TI station **was heard** by someone abroad.
- **`[PSKReporter]`** = detected via automatic digital modes (FT8, FT4, WSPR, JS8Call).
- **`[Cluster (Spothole)]`** = detected via a manual report to a DX cluster (SSB, CW, or manually announced digital).
- If nothing new happens in a cycle (every 5 minutes by default), no message is sent — there's no "all quiet" filler message.

## Testing that everything works, without waiting for a real opening

```bash
python3 alertas_6m_ti.py --test
```

Sends a short test message through the real channel (WhatsApp/email, whichever you have enabled). This is the fastest way to confirm the delivery channel still works after any change or restart.

## Checking the bot's status

```bash
sudo systemctl status alertas-6m-python alertas-6m-whatsapp --no-pager
```

Both should say `active (running)`. To watch what's happening live:

```bash
journalctl -u alertas-6m-python -f      # PSKReporter/Spothole monitoring
journalctl -u alertas-6m-whatsapp -f    # WhatsApp connection
```

## Status / QR page

While the WhatsApp bot is running, this page always reflects its current state — open it from any browser on the same network:

```
http://YOUR-SERVER-IP:3002/
```

- If it says "✅ Conectado a WhatsApp" ("Connected"): everything's fine, nothing to do.
- If it shows a QR code: you need to re-link (see below). It auto-refreshes every 10 seconds.

## If WhatsApp asks you to scan the QR again

WhatsApp can, on its own, close the session of an unofficial client like this one (see the warning in the README for more detail). When it happens:

```bash
sudo systemctl stop alertas-6m-whatsapp
cd whatsapp_bot
node index.js
```

Open `http://YOUR-PI-IP:3002/` from your phone, scan it, wait to see `✅ Conectado a WhatsApp.` in the terminal, stop it with **`Ctrl+C`** (never `Ctrl+Z` — that only pauses the process without closing it, leaving the port occupied) and hand control back to systemd:

```bash
sudo systemctl start alertas-6m-whatsapp
```

### How to minimize this happening often

- Don't run `node index.js` by hand while the `systemd` service is still active — an internal lock blocks the second instance to protect you, but stop the service first (`systemctl stop`) before any manual test anyway.
- Keep the phone with the SIM connected to the internet regularly (WhatsApp logs out linked devices that go **14 days** without connecting).
- Don't pile up old linked devices from past tests — occasionally check WhatsApp → Settings → Linked Devices and remove ones you no longer use (the limit is 4).
- Update Baileys from time to time, especially if disconnections become frequent: `cd whatsapp_bot && npm install @whiskeysockets/baileys@latest`.

## If PSKReporter stops responding

It's a free, community-run service; it sometimes has hours-long outages. The bot handles it on its own:

- It keeps working with Spothole (SSB/CW/manual digital) in the meantime.
- After ~10 minutes of consecutive failures, it sends a single warning to the group.
- After ~20 minutes, a second "check ASAP" warning — and it won't repeat again until it recovers.
- When PSKReporter comes back, it sends a recovery notice.

There's nothing you need to do on your end; it's an issue with their infrastructure, not your install. You can confirm by visiting `https://pskreporter.info/pskmap.html` — if that doesn't load either, it's a general outage, not something on your side.

## Errors you might see in the logs, and what they mean

| Log message | What it is | Action |
|---|---|---|
| `Error consultando PSKReporter: 526 Server Error` | Outage on PSKReporter's side (their server's SSL certificate) | None — the bot keeps going with Spothole and warns if it drags on |
| `❌ Ya hay otra instancia de este bot corriendo` | The lock detected two runs at once | Stop the extra one with `sudo systemctl stop alertas-6m-whatsapp` or by closing the correct manual process |
| `Error publicando en el grupo: No sessions` | WhatsApp hasn't finished syncing the group participants' encryption keys yet (normal right after reconnecting) | The bot retries on its own after 5s; if it persists, wait a minute and try `--test` again |
| `EADDRINUSE: address already in use 127.0.0.1:3001` | Two Node processes fighting over the same port | `sudo pkill -9 -f "node index.js"`, delete `.whatsapp_bot.lock`, and let systemd start it alone |
| "Esperando el mensaje. Esto puede demorar un poco" in WhatsApp | Encryption sync in progress after a reconnect | Resolves itself in 1-2 minutes, no need to resend |

## Settings you can change

All at the top of `alertas_6m_ti.py`, with comments explaining each one:

- `CHECK_INTERVAL_SECONDS` — how often it queries (300 = 5 min by default; don't go below 300 out of courtesy to the free services).
- `TI_PREFIX_REGEX` — which callsign prefixes count as "from Costa Rica" (TI/TE by default).
- `WHATSAPP_MODE` / `EMAIL_ENABLED` — where alerts go.
- `AVISO_INICIAL_TRAS_FALLOS` / `AVISO_ESCALACION_TRAS_FALLOS` — when it warns that PSKReporter is down.

After any change to this file:

```bash
python3 -m py_compile alertas_6m_ti.py && echo "syntax OK"   # validate before restarting
sudo systemctl restart alertas-6m-python
```

For changes to `whatsapp_bot/index.js`, the equivalent is `node --check index.js`, then `sudo systemctl restart alertas-6m-whatsapp`.
