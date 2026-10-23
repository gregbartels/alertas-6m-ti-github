# Alertas de 6 metros para Costa Rica (TI) / 6-Meter Alerts for Costa Rica (TI)

🇬🇧 *English first* — 🇪🇸 *Español más abajo*

---


### In Loving Memory of Carlos "Keko" Diez, TI5KD
**Silent Key — October 6, 2026**

This project was created in loving memory of **Carlos "Keko" Diez, TI5KD**, a passionate amateur radio operator, a true enthusiast of the Magic Band (50 MHz), and a mentor to generations of radio amateurs in Costa Rica.

Keko was more than an experienced operator. He was a teacher, a friend, and an inspiration to many who discovered the fascinating world of 6-meter propagation through his knowledge, dedication, and willingness to share his experience.

His passion for 50 MHz helped inspire a community of operators who continue exploring the mysteries of the Magic Band, chasing distant signals, and celebrating every unexpected band opening.

Although Keko became a Silent Key on October 6, 2026, his knowledge, friendship, and contributions to amateur radio will continue to resonate far beyond the airwaves.

**This application is dedicated to his memory and to the spirit of curiosity, friendship, and discovery that he inspired in so many of us.**

*The signals may fade, but the legacy of a great radio amateur lives on.*

**73, Keko. TI5KD SK. You will always be remembered.**

## 🇬🇧 English

Bot that monitors the 6-meter band (50 MHz) and sends WhatsApp (and optionally email) alerts when:

- A **TI/TE** callsign (Costa Rica) receives a foreign station, or
- A **TI/TE** station is heard by someone outside Costa Rica,
<img width="727" height="521" alt="image" src="https://github.com/user-attachments/assets/2fde9330-5ac3-4959-9ba3-e951f46ed112" />

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


### En memoria de Carlos "Keko" Diez, TI5KD
**Silent Key — 6 de octubre de 2026**

Este proyecto fue creado en memoria de **Carlos "Keko" Diez, TI5KD**, un apasionado radioaficionado, entusiasta de la Banda Mágica (50 MHz) y maestro de generaciones de radioaficionados en Costa Rica.

Keko fue mucho más que un operador experimentado. Fue un maestro, un amigo y una fuente de inspiración para muchos que descubrieron el fascinante mundo de la propagación en 6 metros gracias a sus conocimientos, dedicación y generosidad para compartir sus experiencias.

Su pasión por los 50 MHz ayudó a inspirar a una comunidad de operadores que continúa explorando los misterios de la Banda Mágica, buscando señales lejanas y celebrando cada inesperada apertura de propagación.

Aunque Keko nos dejó el 6 de octubre de 2026, sus enseñanzas, su amistad y sus contribuciones a la radioafición seguirán resonando mucho más allá de las ondas de radio.

**Esta aplicación está dedicada a su memoria y al espíritu de curiosidad, amistad y descubrimiento que despertó en tantos de nosotros.**

*Las señales pueden desvanecerse, pero el legado de un gran radioaficionado permanece para siempre.*

**73, Keko. TI5KD SK. Siempre estarás presente en nuestra memoria.**



Bot que monitorea la banda de 6 metros (50 MHz) y avisa por WhatsApp (y opcionalmente correo) cuando:

- Una estación con indicativo **TI/TE** (Costa Rica) recibe a una estación extranjera, o
- Una estación **TI/TE** es escuchada por alguien fuera de Costa Rica,

<img width="727" height="521" alt="image" src="https://github.com/user-attachments/assets/49d0ffa5-cd0f-47d0-8454-42bc99902077" />

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
