# Installation Guide

Complete step-by-step guide to get the bot running from scratch, on a Raspberry Pi (or any Linux machine) that stays on 24/7.

*[Leer en español (INSTALL.es.md)](INSTALL.es.md)*

## 0. What you need before starting

- A Raspberry Pi (or Linux server) running **64-bit Raspberry Pi OS**, with SSH or terminal access.
  - If unsure of the architecture, run `dpkg --print-architecture` — it should say `arm64`, not `armhf`. If it says `armhf`, reinstall the OS choosing the 64-bit version in Raspberry Pi Imager before continuing (recent Node.js versions don't support 32-bit).
- A WhatsApp number that is already a **member of the group** where you want alerts to arrive (can be your own number, or a dedicated secondary one — recommended, since this method is unofficial and that number carries a low-but-real risk of friction with WhatsApp).
- Your email (optional, only if you also want email alerts) and, if using Gmail, an [app password](https://myaccount.google.com/apppasswords) (not your regular password).
- Your amateur radio callsign and a contact email, to identify yourself to PSKReporter (see section 4).

## 1. Download the project to the Raspberry Pi

If you have internet access on both ends:

```bash
git clone <this-repo-URL>
cd <repo-folder>
```

If you don't have a direct way to clone (for example, if you manage the Pi only via email or manual transfer), download the repo `.zip` from GitHub ("Code" → "Download ZIP"), transfer it to the Pi however you can (USB, email, `scp`, etc.) and unzip it:

```bash
unzip zip-file-name.zip -d alertas-6m-ti
cd alertas-6m-ti
```

## 2. Run the automatic installer

```bash
chmod +x install.sh
./install.sh
```

The installer does the following for you:

1. Installs Node.js 20 and Python 3 (if you don't have them).
2. Installs both projects' dependencies (`npm install`, `pip install requests`).
3. Asks whether you want to enable email, and if so, asks for the details.
4. Asks how you want WhatsApp (none / individual number via CallMeBot / group via Baileys).
5. **If you choose "group"**: it shows a QR code in the terminal to link the WhatsApp account. This is the only step that truly requires manual action — nothing here can be automated away, it's a WhatsApp security measure.
6. Builds and enables the two `systemd` services so everything runs on its own, forever, even after a Pi reboot.

### If the terminal QR doesn't scan well

The QR font over SSH sometimes renders distorted. Better:

1. Let the installer keep running (or if it already failed there, run `cd whatsapp_bot && node index.js` manually).
2. From your phone's browser, on the same WiFi network as the Pi, open `http://YOUR-PI-IP:3002/` (get the IP with `hostname -I`).
3. You'll see the QR as a crisp image, ready to scan with the camera.

## 3. Verify it worked

```bash
sudo systemctl status alertas-6m-python alertas-6m-whatsapp --no-pager
```

Both should say `active (running)` in green. Then test a real send without waiting for a real band opening:

```bash
python3 alertas_6m_ti.py --test
```

If the test message arrives wherever you configured (WhatsApp and/or email), the installation is complete.

## 4. Identify yourself to PSKReporter (important, don't skip this)

Edit the top of `alertas_6m_ti.py`:

```python
APPCONTACT = "your-email@example.com"
CALLSIGN_OPERADOR = "YOUR_CALLSIGN"
```

PSKReporter is a free, community-run service. Its developer (Philip Gladstone, N1DQ) [explicitly asks](https://groups.google.com/g/psk-reporter/c/gkQ3lcwzc6c) that anyone querying it programmatically identify themselves, so he can reach out instead of blocking if something looks off from your connection. After editing, restart:

```bash
sudo systemctl restart alertas-6m-python
```

## 5. Test it on your computer first (optional, recommended if you've never used it)

The whole project runs equally well on Windows/Mac/regular Linux — there's just no `systemd` there, so you run both processes manually in two terminals:

```bash
# Terminal 1
cd whatsapp_bot
npm install
node index.js

# Terminal 2 (in the main folder)
pip install requests
python3 alertas_6m_ti.py --test
```

Once you've confirmed it works, move to the Raspberry Pi to leave it running 24/7 with `install.sh`.

## Common installation issues

| Symptom | Likely cause | Fix |
|---|---|---|
| `Unsupported architecture armhf` installing Node.js | 32-bit operating system | Reinstall Raspberry Pi OS in the 64-bit version (see section 0) |
| `Could not get lock /var/lib/dpkg/lock-frontend` | `PackageKit` running in the background | `sudo systemctl stop packagekit`, then retry |
| `sed: -e expression #1, char N: unknown option to 's'` running `install.sh` | Old installer version with a quoting bug | Download the latest version of this repository |
| The terminal QR won't scan | Font distortion over SSH | Use the web page `http://YOUR-PI-IP:3002/` (see section 2) |

For day-to-day use once installed, and troubleshooting after it's running, see [USAGE.en.md](USAGE.en.md). For a technical walkthrough of how the code works, see [HOW_IT_WORKS.en.md](HOW_IT_WORKS.en.md).
