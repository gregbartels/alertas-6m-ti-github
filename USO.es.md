# Manual de uso

Guía de referencia para el día a día, una vez que el bot ya está instalado y corriendo. Ver [INSTALL.es.md](INSTALL.es.md) si todavía no lo has instalado.

*[Read in English (USAGE.en.md)](USAGE.en.md)*

## Cómo leer las alertas

Cada mensaje tiene esta forma:

```
📻🚨 Apertura en 6 m (50 MHz) relacionada con Costa Rica (TI):

• 📥 [PSKReporter] TI2XYZ (EJ89au) recibió a LU5FF (FF99pd, Argentina) en 50.3146 MHz FT8 (SNR -8)
• 📤 [Cluster (Spothole)] TI2OY fue escuchado por PY1XYZ (GG87, Brazil) en 50.1150 MHz SSB (SNR -)
```

- **📥** = una estación TI **recibió/escuchó** a alguien de afuera.
- **📤** = una estación TI **fue escuchada** por alguien de afuera.
- **`[PSKReporter]`** = detectado por modos digitales automáticos (FT8, FT4, WSPR, JS8Call).
- **`[Cluster (Spothole)]`** = detectado por un reporte manual a un DX cluster (SSB, CW, o digital anunciado a mano).
- Si no hay nada nuevo en un ciclo (cada 5 minutos por defecto), simplemente no llega ningún mensaje — no hay un "todo tranquilo" de relleno.

## Probar que todo funciona, sin esperar una apertura real

```bash
python3 alertas_6m_ti.py --test
```

Manda un mensaje corto de prueba por el mismo canal real (WhatsApp/correo, según lo que tengas activado). Es la forma más rápida de confirmar que el canal de entrega sigue funcionando después de cualquier cambio o reinicio.

## Revisar el estado del bot

```bash
sudo systemctl status alertas-6m-python alertas-6m-whatsapp --no-pager
```

Ambos deben decir `active (running)`. Para ver qué está pasando en vivo:

```bash
journalctl -u alertas-6m-python -f      # el monitoreo de PSKReporter/Spothole
journalctl -u alertas-6m-whatsapp -f    # la conexión a WhatsApp
```

## Página de estado / QR

Mientras el bot de WhatsApp corre, esta página siempre refleja su estado actual — ábrela desde cualquier navegador en la misma red:

```
http://IP-DE-TU-SERVIDOR:3002/
```

- Si dice "✅ Conectado a WhatsApp": todo bien, no hay nada que hacer.
- Si muestra un código QR: hay que volver a vincular (ver más abajo). Se actualiza sola cada 10 segundos.

## Si WhatsApp pide escanear el QR de nuevo

WhatsApp puede, por su propia cuenta, cerrar la sesión de un cliente no oficial como este (más detalle en la advertencia del README). Cuando pase:

```bash
sudo systemctl stop alertas-6m-whatsapp
cd whatsapp_bot
node index.js
```

Abre `http://IP-DE-TU-PI:3002/` desde el celular, escanea, espera a ver `✅ Conectado a WhatsApp.` en la terminal, corta con **`Ctrl+C`** (nunca `Ctrl+Z` — eso solo pausa el proceso sin cerrarlo, y deja el puerto ocupado) y devuélveselo a systemd:

```bash
sudo systemctl start alertas-6m-whatsapp
```

### Cómo minimizar que esto pase seguido

- No corras `node index.js` a mano mientras el servicio de `systemd` sigue activo — un candado interno bloquea la segunda instancia para protegerte, pero igual detén el servicio primero (`systemctl stop`) antes de cualquier prueba manual.
- Mantén el teléfono con la SIM conectado a internet regularmente (WhatsApp cierra sesiones de dispositivos vinculados que llevan **14 días** sin conexión).
- No acumules dispositivos vinculados de pruebas viejas — revisa de vez en cuando WhatsApp → Configuración → Dispositivos vinculados y borra los que ya no uses (el límite es 4).
- Actualiza Baileys de vez en cuando, sobre todo si las desconexiones se vuelven frecuentes: `cd whatsapp_bot && npm install @whiskeysockets/baileys@latest`.

## Si PSKReporter deja de responder

Es un servicio gratuito y comunitario; a veces tiene caídas de horas. El bot lo maneja solo:

- Sigue funcionando con Spothole (SSB/CW/digital manual) mientras tanto.
- A los ~10 minutos de fallos seguidos, manda un aviso único al grupo.
- A los ~20 minutos, un segundo aviso de "revisar ASAP" — y no repite más hasta que se recupere.
- Cuando PSKReporter vuelve, manda un aviso de recuperación.

No hay nada que debas hacer del lado tuyo; es un problema de su infraestructura, no de tu instalación. Puedes confirmarlo entrando a `https://pskreporter.info/pskmap.html` — si tampoco carga ahí, es una caída general, no algo tuyo.

## Errores que puedes ver en los logs, y qué significan

| Mensaje en el log | Qué es | Acción |
|---|---|---|
| `Error consultando PSKReporter: 526 Server Error` | Caída del lado de PSKReporter (certificado SSL de su servidor) | Ninguna — el bot sigue con Spothole y avisa si se prolonga |
| `❌ Ya hay otra instancia de este bot corriendo` | El candado detectó dos ejecuciones a la vez | Detén la que sobra con `sudo systemctl stop alertas-6m-whatsapp` o cerrando el proceso manual correcto |
| `Error publicando en el grupo: No sessions` | WhatsApp aún no sincronizó las claves de los participantes del grupo (normal justo tras reconectar) | El bot reintenta solo en 5s; si persiste, espera un minuto y prueba `--test` de nuevo |
| `EADDRINUSE: address already in use 127.0.0.1:3001` | Dos procesos de Node peleando por el mismo puerto | `sudo pkill -9 -f "node index.js"`, borra `.whatsapp_bot.lock`, y arranca solo por systemd |
| "Esperando el mensaje. Esto puede demorar un poco" en WhatsApp | Sincronización de cifrado en curso tras una reconexión | Se resuelve solo en 1-2 minutos, no hace falta reenviar |

## Ajustes que puedes cambiar

Todo al inicio de `alertas_6m_ti.py`, con comentarios explicando cada uno:

- `CHECK_INTERVAL_SECONDS` — cada cuánto consulta (300 = 5 min por defecto; no bajarlo de 300 por cortesía con los servicios gratuitos).
- `TI_PREFIX_REGEX` — qué prefijos de indicativo cuentan como "de Costa Rica" (TI/TE por defecto).
- `WHATSAPP_MODE` / `EMAIL_ENABLED` — a dónde llegan las alertas.
- `AVISO_INICIAL_TRAS_FALLOS` / `AVISO_ESCALACION_TRAS_FALLOS` — cuándo avisa que PSKReporter está caído.

Después de cualquier cambio a este archivo:

```bash
python3 -m py_compile alertas_6m_ti.py && echo "sintaxis OK"   # valida antes de reiniciar
sudo systemctl restart alertas-6m-python
```

Para cambios en `whatsapp_bot/index.js`, el equivalente es `node --check index.js`, y reiniciar con `sudo systemctl restart alertas-6m-whatsapp`.

Para entender qué hace cada función del código por dentro, consulta [COMO_FUNCIONA.es.md](COMO_FUNCIONA.es.md).
