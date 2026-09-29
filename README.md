# Alertas de 6 metros para Costa Rica (TI) / 6-Meter Alerts for Costa Rica (TI)

🇬🇧 *English first* — 🇪🇸 *Español más abajo*

---

## 🇬🇧 English

Bot that monitors the 6-meter band (50 MHz) and sends WhatsApp (and optionally email) alerts when:

- A **TI/TE** callsign (Costa Rica) receives a foreign station, or
- A **TI/TE** station is heard by someone outside Costa Rica,

using two public sources in parallel:

- **[PSKReporter](https://pskreporter.info)** — automatic digital modes (FT8, FT4, WSPR, JS8Call, etc.)
- **[Spothole](https://spothole.app)** — SSB, CW, and manually-reported digital via traditional DX clusters

Alerts are posted to a real WhatsApp group, using [Baileys](https://github.com/WhiskeySockets/Baileys) (unofficial) as the bridge.

### Documentation

| | |
|---|---|
| 📥 **[INSTALL.en.md](INSTALL.en.md)** | Full step-by-step installation guide |
| 📻 **[USAGE.en.md](USAGE.en.md)** | Day-to-day usage, troubleshooting, common errors |
| 🧠 **[HOW_IT_WORKS.en.md](HOW_IT_WORKS.en.md)** | Technical walkthrough of the code, for anyone extending it |

### Quick start

```bash
git clone <this-repo>
cd <this-repo>
chmod +x install.sh
./install.sh
```

### ⚠️ About WhatsApp

This project uses Baileys, an **unofficial** library that connects as a "linked device" of a real WhatsApp account. This goes outside WhatsApp's Terms of Service, and WhatsApp can disconnect it at any time through its own automation-detection mechanisms — there's no 100% stability guarantee. Use it with a WhatsApp number you wouldn't mind losing. The project includes several mitigations (anti-double-run lock, automatic session backup/restore, legitimate browser profile, retries) that reduce — but don't eliminate — the frequency of disconnections.

### Credits

[PSKReporter](https://pskreporter.info) (Philip Gladstone, N1DQ) · [Spothole](https://spothole.app) (Ian Renton) · [Baileys](https://github.com/WhiskeySockets/Baileys)

### License

MIT — see [LICENSE](LICENSE).

---

## 🇪🇸 Español

Bot que monitorea la banda de 6 metros (50 MHz) y avisa por WhatsApp (y opcionalmente correo) cuando:

- Una estación con indicativo **TI/TE** (Costa Rica) recibe a una estación extranjera, o
- Una estación **TI/TE** es escuchada por alguien fuera de Costa Rica,

usando dos fuentes públicas en paralelo:

- **[PSKReporter](https://pskreporter.info)** — modos digitales automáticos (FT8, FT4, WSPR, JS8Call, etc.)
- **[Spothole](https://spothole.app)** — SSB, CW y digital reportado a mano a DX clusters tradicionales

Las alertas se publican en un grupo de WhatsApp real, usando [Baileys](https://github.com/WhiskeySockets/Baileys) (no oficial) como puente.

### Documentación

| | |
|---|---|
| 📥 **[INSTALL.es.md](INSTALL.es.md)** | Manual completo de instalación paso a paso |
| 📻 **[USO.es.md](USO.es.md)** | Uso diario, solución de problemas, errores comunes |
| 🧠 **[COMO_FUNCIONA.es.md](COMO_FUNCIONA.es.md)** | Explicación técnica del código, para quien quiera extenderlo |

### Arranque rápido

```bash
git clone <este-repo>
cd <este-repo>
chmod +x install.sh
./install.sh
```

### ⚠️ Sobre WhatsApp

Este proyecto usa Baileys, una librería **no oficial** que se conecta como un "dispositivo vinculado" de una cuenta real de WhatsApp. Esto va por fuera de los Términos de Servicio de WhatsApp, y WhatsApp puede desconectarlo en cualquier momento por sus propios mecanismos de detección de automatización — no hay garantía de estabilidad al 100%. Úsalo con un número de WhatsApp que no te importe perder. El proyecto incluye varias mitigaciones (candado anti-doble-ejecución, respaldo/restauración automática de sesión, perfil de navegador legítimo, reintentos) que reducen —pero no eliminan— la frecuencia de desconexiones.

### Créditos

[PSKReporter](https://pskreporter.info) (Philip Gladstone, N1DQ) · [Spothole](https://spothole.app) (Ian Renton) · [Baileys](https://github.com/WhiskeySockets/Baileys)

### Licencia

MIT — ver [LICENSE](LICENSE).
