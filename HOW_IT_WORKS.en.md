# How It Works

Technical explanation of the internals, for anyone who wants to understand, modify, or adapt the project — you don't need to be an expert programmer, but some familiarity with Python and basic JavaScript helps.

*[Leer en español (COMO_FUNCIONA.es.md)](COMO_FUNCIONA.es.md)*

## Big picture

The project is **two independent programs** that talk to each other over local HTTP, each running as its own `systemd` service:

```
PSKReporter ─┐
             ├─▶ alertas_6m_ti.py (Python) ─▶ HTTP (127.0.0.1:3001) ─▶ whatsapp_bot/index.js (Node) ─▶ WhatsApp group
Spothole ────┘                                                                   │
                                                                                  └─▶ Status/QR web page (127.0.0.1:3002)
```

**Why two programs instead of one?** Because talking to WhatsApp unofficially (via Baileys) only exists as a **Node.js/JavaScript** library, while the rest of the logic (querying APIs, filtering, deciding) was written in **Python** for being simpler to read and maintain for that kind of task. Rather than forcing everything into one language, each part uses whichever tool fits best, and they talk over a simple HTTP bridge.

## `alertas_6m_ti.py` — the detection brain

### Configuration (top of the file)

Everything adjustable lives as constants at the top: the 6m frequency range in Hz, query interval, Costa Rica callsign prefixes (regex `^(TI|TE)\d`), Spothole parameters, outage-warning thresholds, and email/WhatsApp settings. Changing the bot's behavior almost always means editing a value here, not touching the logic below.

### `consultar_pskreporter(lookback_seconds)`

Builds a GET URL to `retrieve.pskreporter.info/query` with:
- `flowStartSeconds` — negative, meaning "the last N seconds".
- `frange` — frequency range in Hz (narrows to 6 meters server-side).
- `rptlimit` — result cap (2000; see the code comment for why that's not excessive).
- `appcontact` — your email, to identify yourself to the service (see `INSTALL.en.md` section 4).

The response is XML; it's parsed with `xml.etree.ElementTree` looking for `receptionReport` elements, and each one becomes a dictionary with uniform keys (`sender`, `receiver`, `freq_hz`, `mode`, etc.) — the same "shape" the Spothole function uses, so the rest of the code doesn't need to know which source a given piece of data came from.

### `consultar_spothole(max_age_seconds)`

Same idea, but against `spothole.app/api/v2/spots`, requesting the `6m` band and `mode_type=CW,PHONE,DATA` (CW, SSB, and manually-reported digital). The response is plain JSON (a list), documented in its [OpenAPI spec](https://spothole.app/apidocs) — field names (`dx_call`, `de_call`, `freq`, etc.) are confirmed against that official spec, not guessed.

### `clasificar(reportes)`

Walks the combined list of reports (from both sources) and splits each into one of two categories, using `es_ti()` (which applies the prefix regex) on each report's sender and receiver:

- `TI_ESCUCHA_DX` — the receiver is TI, the sender isn't.
- `TI_ES_ESCUCHADO` — the sender is TI, the receiver isn't.

If both are TI (a contact between two Costa Rican stations), it's skipped — it's not new information about international reach.

### `clave_unica(tipo, r)` — avoiding duplicate alerts

Each event is identified by **type + station pair + a 10-minute time window** (not by source or exact timestamp). This is intentional: if the same real contact arrives via both PSKReporter and Spothole (for example, if PSKReporter recovers from an outage right when Spothole had already reported something), it counts as a single event, not two. The record of what's already been alerted is kept in `estado_alertas_6m.json`, with automatic cleanup of entries older than 24 hours.

### `formatear_mensaje(eventos)`

Builds the final text: a fixed header, one line per event with a direction arrow (📥/📤), the source in brackets, and the contact's details. The `_lugar()` helper avoids dangling commas when a field is missing (like the receiver's country, which PSKReporter doesn't always report).

### `enviar_email()` / `enviar_whatsapp()`

`enviar_email` uses `smtplib` directly (no external libraries). `enviar_whatsapp` is a dispatcher based on `WHATSAPP_MODE`: if it's `"grupo"`, it POSTs to `http://127.0.0.1:3001/send-group` — meaning it talks to the Node program over local HTTP, not directly to WhatsApp.

### `ciclo()` — the heartbeat

Runs once per interval (`CHECK_INTERVAL_SECONDS`, 5 minutes by default):

1. Queries PSKReporter (with error handling: on failure, it counts the failure and moves on).
2. If the consecutive-failure count crosses `AVISO_INICIAL_TRAS_FALLOS` or `AVISO_ESCALACION_TRAS_FALLOS`, it sends a single (non-repeating) warning to the group/email.
3. Queries Spothole (independent of PSKReporter's result).
4. Classifies all combined reports.
5. Filters out ones already alerted (`clave_unica`).
6. If there are new events, builds the message and sends it.
7. Saves the updated state.

### `prueba()` / `--test`

Sends a short, fixed message through the real delivery path (`enviar_email`, `enviar_whatsapp`), without touching PSKReporter or Spothole — useful for testing the delivery channel in seconds, without waiting for real traffic.

## `whatsapp_bot/index.js` — the WhatsApp bridge

### Connecting with Baileys

`makeWASocket()` creates the connection, using `useMultiFileAuthState()` to save/read session credentials in `auth_info/` (files that should **never** be shared or committed to a repository — they're the keys that let something act as your account). The browser profile (`Browsers.macOS('Desktop')`) makes WhatsApp see the connection as a legitimate WhatsApp Desktop-type client, instead of a made-up name.

### The lock (`adquirirLock()` / `liberarLock()`)

Before connecting, it writes its own PID to a `.whatsapp_bot.lock` file. If that file already exists and the owning process is still alive, it refuses to start — this prevents two instances (say, one manual and one from `systemd`) from fighting over the same WhatsApp session and tearing it down.

### Session backup and auto-restore

Every time it connects successfully (`respaldarSesion()`), it copies `auth_info/` to `auth_info_backup/`. If, on startup, the main folder is empty or corrupted but the backup exists, it restores it automatically (`restaurarSesionSiHaceFalta()`) — meant to survive a power outage that corrupts files mid-write.

### Status/QR page (port 3002)

A second HTTP server, separate from the sending one, running from process startup (not only once connected). It serves a page that auto-refreshes every 10 seconds, showing the current QR code as an image (using the `qrcode` library, distinct from `qrcode-terminal`) or a "connected" message, depending on state.

### Sending server (port 3001)

Exposes `POST /send-group`, which receives `{"text": "..."}` and calls `enviarConReintento()` — which tries `sock.sendMessage()`, and if it fails (for example with the `"No sessions"` error, typical right after reconnecting), waits 5 seconds and retries once more before giving up.

### Group warm-up

Right after connecting, it calls `sock.groupMetadata(GROUP_JID)` once — this forces Baileys to sync the group participants' encryption keys before accepting sends, avoiding the `"No sessions"` error on the first message after a reconnect.

## `install.sh` — the installer

A bash script that automates all of the above: installs Node/Python, asks for configuration (email, WhatsApp mode), and if you choose "group", runs `node index.js --list-groups` so you can scan the QR and pick the group. At the end, it patches the `systemd` `.service` files with your installation's real paths (user, folder) and enables them.

## `systemd/*.service`

Two config files that tell Linux "keep this running forever, and if it dies, restart it" (`Restart=on-failure`). `alertas-6m-python.service` runs `python3 alertas_6m_ti.py`; `alertas-6m-whatsapp.service` runs `node index.js`. Neither depends on a terminal session staying open.

## Ideas for extending the project

- **A different country/prefix**: change `TI_PREFIX_REGEX` and the message text.
- **A different band**: change `BAND_FREQ_MIN_HZ`/`BAND_FREQ_MAX_HZ` and `SPOTHOLE_BAND`.
- **A different output channel** (Telegram, Discord): you'd add a `enviar_telegram()` function alongside the existing ones, and call it from `ciclo()` the same way `enviar_whatsapp()` is called. Telegram in particular is simpler, since it has an official bot API without any of the session-management overhead WhatsApp requires.
- **More data sources**: any service exposing radio spots over HTTP/JSON can be added with the same pattern as `consultar_spothole()` — return a list of dictionaries with the same keys, and append it to `reportes` inside `ciclo()`.
