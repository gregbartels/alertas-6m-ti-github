# Manual de instalación

Guía completa para poner a correr el bot desde cero, en una Raspberry Pi (o cualquier Linux) que se quede prendida 24/7.

*[Read in English (INSTALL.en.md)](INSTALL.en.md)*


## 0. Lo que necesitas tener listo antes de empezar

- Una Raspberry Pi (o servidor Linux) con **Raspberry Pi OS de 64 bits** instalado y acceso por SSH o terminal.
  - Si no estás seguro de la arquitectura, corre `dpkg --print-architecture` — debe decir `arm64`, no `armhf`. Si dice `armhf`, reinstala el sistema operativo eligiendo la versión de 64 bits en Raspberry Pi Imager antes de continuar (las versiones recientes de Node.js no soportan 32 bits).
- Un número de WhatsApp que ya sea **miembro del grupo** donde quieres que lleguen las alertas (puede ser tu propio número, o uno secundario dedicado solo a esto — recomendado, porque este método no es oficial y ese número corre el riesgo, bajo pero real, de tener fricciones con WhatsApp).
- Tu correo (opcional, solo si además quieres alertas por email) y, si usas Gmail, una [contraseña de aplicación](https://myaccount.google.com/apppasswords) (no tu contraseña normal).
- Tu indicativo de radioaficionado y un correo de contacto, para identificarte ante PSKReporter (ver sección 4).

## 1. Descargar el proyecto a la Raspberry Pi

Si tienes acceso a internet en ambos lados:

```bash
git clone <URL-de-este-repositorio>
cd <carpeta-del-repositorio>
```

Si no tienes forma directa de clonar (por ejemplo, si administras la Pi solo por correo o transferencia manual), descarga el `.zip` del repositorio desde GitHub ("Code" → "Download ZIP"), pásalo a la Pi por el medio que tengas (USB, correo, `scp`, etc.) y descomprímelo:

```bash
unzip nombre-del-zip.zip -d alertas-6m-ti
cd alertas-6m-ti
```

## 2. Correr el instalador automático

```bash
chmod +x install.sh
./install.sh
```

El instalador hace lo siguiente por ti:

1. Instala Node.js 20 y Python 3 (si no los tienes).
2. Instala las dependencias de ambos proyectos (`npm install`, `pip install requests`).
3. Te pregunta si quieres activar el correo, y si sí, te pide los datos.
4. Te pregunta cómo quieres el WhatsApp (nada / número individual vía CallMeBot / grupo vía Baileys).
5. **Si eliges "grupo"**: te muestra un código QR en la terminal para vincular la cuenta de WhatsApp. Este es el único paso que de verdad requiere que tú hagas algo con las manos — nada se puede automatizar aquí, es una medida de seguridad de WhatsApp.
6. Arma y activa los dos servicios de `systemd` para que todo corra solo, para siempre, incluso si la Pi se reinicia.

### Si el QR de la terminal no escanea bien

La fuente del QR en una terminal SSH a veces sale distorsionada. Mejor:

1. Deja que el instalador siga corriendo (o si ya falló ahí, corre a mano `cd whatsapp_bot && node index.js`).
2. Desde el navegador de tu celular, en la misma red WiFi que la Pi, abre `http://IP-DE-TU-PI:3002/` (obtén la IP con `hostname -I`).
3. Ahí verás el QR como una imagen nítida, lista para escanear con la cámara.

## 3. Verificar que quedó bien

```bash
sudo systemctl status alertas-6m-python alertas-6m-whatsapp --no-pager
```

Ambos deben decir `active (running)` en verde. Luego, prueba el envío real sin esperar una apertura de la banda:

```bash
python3 alertas_6m_ti.py --test
```

Si te llega el mensaje de prueba a donde configuraste (WhatsApp y/o correo), la instalación quedó completa.

## 4. Identificarte ante PSKReporter (importante, no te lo saltes)

Edita el inicio de `alertas_6m_ti.py`:

```python
APPCONTACT = "tu-email@ejemplo.com"
CALLSIGN_OPERADOR = "TU_INDICATIVO"
```

PSKReporter es un servicio gratuito y comunitario. Su desarrollador (Philip Gladstone, N1DQ) [pide explícitamente](https://groups.google.com/g/psk-reporter/c/gkQ3lcwzc6c) que quien lo consulte de forma automática se identifique, para poder contactarte en vez de bloquearte si algo se ve raro desde tu conexión. Después de editar, reinicia:

```bash
sudo systemctl restart alertas-6m-python
```

## 5. Probarlo primero en tu computadora (opcional, recomendado si nunca lo has usado)

Todo el proyecto corre igual de bien en Windows/Mac/Linux normal — solo que ahí no hay `systemd`, así que corres los dos procesos a mano en dos terminales:

```bash
# Terminal 1
cd whatsapp_bot
npm install
node index.js

# Terminal 2 (en la carpeta principal)
pip install requests
python3 alertas_6m_ti.py --test
```

Cuando ya confirmes que funciona, muévete a la Raspberry Pi para dejarlo corriendo 24/7 con `install.sh`.

## Problemas comunes durante la instalación

| Síntoma | Causa probable | Solución |
|---|---|---|
| `Unsupported architecture armhf` al instalar Node.js | Sistema operativo de 32 bits | Reinstala Raspberry Pi OS en versión de 64 bits (ver sección 0) |
| `Could not get lock /var/lib/dpkg/lock-frontend` | `PackageKit` corriendo en segundo plano | `sudo systemctl stop packagekit`, luego reintenta |
| `sed: -e expression #1, char N: unknown option to 's'` al correr `install.sh` | Versión vieja del instalador con un bug de comillas | Descarga la versión más reciente de este repositorio |
| El QR en la terminal no escanea | Distorsión de la fuente en SSH | Usa la página web `http://IP-DE-TU-PI:3002/` (ver sección 2) |

Para el uso diario una vez instalado, y para solucionar problemas después de tenerlo corriendo, consulta [USO.es.md](USO.es.md). Para una explicación técnica de cómo funciona el código por dentro, consulta [COMO_FUNCIONA.es.md](COMO_FUNCIONA.es.md).
