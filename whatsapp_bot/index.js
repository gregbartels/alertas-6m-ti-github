#!/usr/bin/env node
/**
 * whatsapp_bot/index.js
 * ======================
 *
 * Puente entre el script de alertas de 6m (alertas_6m_ti.py) y un grupo
 * de WhatsApp, usando la librería no oficial "Baileys".
 *
 * IMPORTANTE - léelo antes de usarlo
 * -----------------------------------
 * Esto NO es la API oficial de WhatsApp. Funciona conectándose como si
 * fuera "otro celular" de tu cuenta de WhatsApp (Dispositivos vinculados),
 * igual que WhatsApp Web. Eso significa:
 *   - Necesitas un número de WhatsApp que ya sea miembro del grupo donde
 *     quieres que lleguen las alertas (puede ser tu propio número, o un
 *     número secundario/SIM de datos dedicada solo para esto).
 *   - Automatizar una cuenta así va por fuera de los Términos de Servicio
 *     de WhatsApp. El riesgo real de bloqueo es bajo para un bot que manda
 *     pocos mensajes (unas pocas alertas de propagación al día), pero
 *     existe. No lo uses con un número que no puedas perder.
 *   - La sesión se guarda en la carpeta ./auth_info. Si la borras, hay que
 *     volver a escanear el código QR.
 *
 * Instalación
 * -----------
 *   cd whatsapp_bot
 *   npm install
 *
 * Paso 1: descubrir el ID del grupo
 * -----------------------------------
 *   node index.js --list-groups
 *
 * La primera vez va a mostrar un código QR en la terminal. Escanéalo desde
 * el celular con la cuenta de WhatsApp que ya está en el grupo de alertas
 * (WhatsApp > Configuración > Dispositivos vinculados > Vincular un
 * dispositivo). Una vez conectado, imprime la lista de grupos donde esa
 * cuenta participa, con su ID (termina en "@g.us"). Copia el ID del grupo
 * que te interesa.
 *
 * Paso 2: configurar y correr el bot
 * -------------------------------------
 * Pon el ID del grupo en la variable de entorno GROUP_JID, por ejemplo:
 *
 *   GROUP_JID="120363000000000000@g.us" node index.js
 *
 * (o edita directamente la constante GROUP_JID más abajo). El bot se queda
 * corriendo, conectado a WhatsApp, y expone un pequeño servidor HTTP local
 * en http://127.0.0.1:3001/send-group que el script de Python usa para
 * pedirle que publique un mensaje en el grupo.
 *
 * Deja este proceso corriendo (systemd, tmux, pm2, etc.) al mismo tiempo
 * que alertas_6m_ti.py.
 */

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  Browsers,
} = require('@whiskeysockets/baileys');
const { Boom } = require('@hapi/boom');
const qrcodeTerminal = require('qrcode-terminal');
const qrcodeImagen = require('qrcode');
const pino = require('pino');
const http = require('http');
const fs = require('fs');
const path = require('path');

// ============================== CONFIGURACIÓN ==============================
const GROUP_JID = process.env.GROUP_JID || 'PON_AQUI_EL_ID_DEL_GRUPO@g.us';
const HTTP_HOST = '127.0.0.1';
const HTTP_PORT = 3001;
const QR_HTTP_PORT = 3002;   // página web de estado/QR, disponible desde que arranca el proceso
const AUTH_FOLDER = path.join(__dirname, 'auth_info');
const AUTH_BACKUP_FOLDER = path.join(__dirname, 'auth_info_backup');
const LOCK_FILE = path.join(__dirname, '.whatsapp_bot.lock');
// ============================================================================

const LIST_GROUPS = process.argv.includes('--list-groups');

let sock;
let httpIniciado = false;
let ultimoQR = null;   // el QR pendiente de escanear, o null si no hace falta
let conectado = false;

// ---------------------------------------------------------------------------
// Seguro contra ejecuciones dobles: si el bot ya está corriendo (por systemd
// o a mano) y alguien intenta arrancarlo otra vez, esta segunda instancia se
// niega a seguir en vez de pelear por la misma sesión de WhatsApp y tumbarla.
// ---------------------------------------------------------------------------
function pidEstaVivo(pid) {
  try {
    process.kill(pid, 0); // señal 0 = no mata nada, solo pregunta si existe
    return true;
  } catch {
    return false;
  }
}

function adquirirLock() {
  if (fs.existsSync(LOCK_FILE)) {
    const pidPrevio = parseInt(fs.readFileSync(LOCK_FILE, 'utf8').trim(), 10);
    if (pidPrevio && pidEstaVivo(pidPrevio)) {
      console.error(
        `❌ Ya hay otra instancia de este bot corriendo (PID ${pidPrevio}). ` +
        `No se inicia una segunda para no tumbar la sesión de WhatsApp.\n` +
        `Si estás seguro de que no hay ninguna corriendo, borra el archivo ${LOCK_FILE} y vuelve a intentar.`
      );
      process.exit(1);
    }
    // el PID guardado ya no existe (proceso viejo que no se cerró bien): lo reemplazamos
  }
  fs.writeFileSync(LOCK_FILE, String(process.pid));
}

function liberarLock() {
  try {
    if (fs.existsSync(LOCK_FILE) && fs.readFileSync(LOCK_FILE, 'utf8').trim() === String(process.pid)) {
      fs.unlinkSync(LOCK_FILE);
    }
  } catch {
    /* no pasa nada si falla, no es crítico */
  }
}

process.on('exit', liberarLock);
process.on('SIGINT', () => { liberarLock(); process.exit(0); });
process.on('SIGTERM', () => { liberarLock(); process.exit(0); });

// ---------------------------------------------------------------------------
// Respaldo y auto-restauración de la sesión: si la carpeta de sesión aparece
// vacía o dañada (por ejemplo, por un corte de luz a mitad de una escritura),
// se restaura automáticamente desde la última copia buena conocida, en vez
// de forzar un nuevo escaneo de QR.
// ---------------------------------------------------------------------------
function sesionValida(carpeta) {
  return fs.existsSync(path.join(carpeta, 'creds.json'));
}

function restaurarSesionSiHaceFalta() {
  if (!sesionValida(AUTH_FOLDER) && sesionValida(AUTH_BACKUP_FOLDER)) {
    console.warn('⚠️  La sesión actual está ausente o incompleta. Restaurando desde el respaldo...');
    fs.rmSync(AUTH_FOLDER, { recursive: true, force: true });
    fs.cpSync(AUTH_BACKUP_FOLDER, AUTH_FOLDER, { recursive: true });
    console.log('✅ Sesión restaurada desde el respaldo.');
  }
}

function respaldarSesion() {
  try {
    fs.rmSync(AUTH_BACKUP_FOLDER, { recursive: true, force: true });
    fs.cpSync(AUTH_FOLDER, AUTH_BACKUP_FOLDER, { recursive: true });
  } catch (e) {
    console.error('No se pudo respaldar la sesión:', e.message);
  }
}

async function iniciar() {
  restaurarSesionSiHaceFalta();

  const { state, saveCreds } = await useMultiFileAuthState(AUTH_FOLDER);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    auth: state,
    version,
    logger: pino({ level: 'silent' }),
    browser: Browsers.macOS('Desktop'),   // perfil real de WhatsApp Desktop en vez de un nombre inventado
    markOnlineOnConnect: false,           // no forzar el estado "en línea" todo el tiempo
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log('\nEscanea este código QR desde WhatsApp > Dispositivos vinculados > Vincular un dispositivo:\n');
      qrcodeTerminal.generate(qr, { small: true });
      ultimoQR = qr;
      conectado = false;
    }

    if (connection === 'open') {
      ultimoQR = null;
      conectado = true;
      console.log('✅ Conectado a WhatsApp.');
      respaldarSesion();
      if (LIST_GROUPS) {
        await listarGrupos();
        process.exit(0);
      } else {
        if (GROUP_JID.includes('PON_AQUI')) {
          console.warn('⚠️  Todavía no configuraste GROUP_JID. Corre primero: node index.js --list-groups');
        } else {
          // Fuerza la sincronización de los participantes/claves del grupo
          // ANTES de aceptar envíos, para evitar el error "No sessions" que
          // aparece si se manda un mensaje demasiado pronto tras conectar.
          try {
            await sock.groupMetadata(GROUP_JID);
            console.log('Sesión del grupo sincronizada.');
          } catch (e) {
            console.warn('No se pudo precalentar el grupo (se reintentará al primer envío):', e.message);
          }
        }
        if (!httpIniciado) {
          iniciarServidorHttp();
          httpIniciado = true;
        }
      }
    }

    if (connection === 'close') {
      conectado = false;
      const motivo = new Boom(lastDisconnect?.error)?.output?.statusCode;
      const debeReconectar = motivo !== DisconnectReason.loggedOut;
      console.log(
        'Conexión cerrada.',
        debeReconectar ? 'Reintentando...' : 'Sesión cerrada. Borra la carpeta auth_info y vuelve a escanear el QR.'
      );
      if (debeReconectar) setTimeout(iniciar, 3000);
    }
  });
}

async function listarGrupos() {
  const grupos = await sock.groupFetchAllParticipating();
  console.log('\nGrupos donde participa esta cuenta:\n');
  for (const g of Object.values(grupos)) {
    console.log(`- ${g.subject}\n    ${g.id}`);
  }
  console.log('\nCopia el ID (termina en @g.us) del grupo que quieres usar y ponlo en GROUP_JID.\n');
}

function iniciarServidorEstado() {
  const server = http.createServer(async (req, res) => {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    let cuerpo;
    if (conectado) {
      cuerpo = `<h1>✅ Conectado a WhatsApp</h1><p>No hay nada que escanear en este momento.</p>`;
    } else if (ultimoQR) {
      try {
        const imagenQR = await qrcodeImagen.toDataURL(ultimoQR, { width: 320 });
        cuerpo = `
          <h1>Escanea este código QR</h1>
          <p>WhatsApp &gt; Configuración &gt; Dispositivos vinculados &gt; Vincular un dispositivo</p>
          <img src="${imagenQR}" alt="Código QR" style="width:320px;height:320px;" />
          <p><small>Esta página se actualiza sola cada 10 segundos.</small></p>`;
      } catch (e) {
        cuerpo = `<h1>Error generando el QR</h1><p>${e.message}</p>`;
      }
    } else {
      cuerpo = `<h1>Esperando conexión...</h1><p>Todavía no hay código QR disponible.</p>`;
    }
    res.end(`
      <!DOCTYPE html>
      <html lang="es">
      <head>
        <meta charset="utf-8" />
        <meta http-equiv="refresh" content="10" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Estado del bot de WhatsApp - 6m TI</title>
        <style>body{font-family:sans-serif;text-align:center;padding:2rem;}</style>
      </head>
      <body>${cuerpo}</body>
      </html>
    `);
  });
  server.on('error', (e) => {
    console.error('Error en el servidor de estado/QR:', e.message);
  });
  server.listen(QR_HTTP_PORT, '0.0.0.0', () => {
    console.log(`Página de estado/QR disponible en http://<IP-de-tu-Pi>:${QR_HTTP_PORT}/ (ábrela desde el navegador del celular)`);
  });
}

function esperar(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function enviarConReintento(text, intentos = 2) {
  for (let i = 1; i <= intentos; i++) {
    try {
      await sock.sendMessage(GROUP_JID, { text });
      return;
    } catch (e) {
      const esUltimoIntento = i === intentos;
      console.warn(`Intento ${i} de envío falló (${e.message}).`, esUltimoIntento ? 'Sin más reintentos.' : 'Reintentando en 5s...');
      if (esUltimoIntento) throw e;
      await esperar(5000);
    }
  }
}

function iniciarServidorHttp() {
  const server = http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/send-group') {
      let body = '';
      req.on('data', (chunk) => (body += chunk));
      req.on('end', async () => {
        try {
          const { text } = JSON.parse(body || '{}');
          if (!text) throw new Error('falta el campo "text" en el JSON');
          await enviarConReintento(text);
          console.log('Mensaje publicado en el grupo.');
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true }));
        } catch (e) {
          console.error('Error publicando en el grupo:', e.message);
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: false, error: e.message }));
        }
      });
    } else {
      res.writeHead(404);
      res.end();
    }
  });
  server.on('error', (e) => {
    console.error('Error en el servidor HTTP local:', e.message);
  });

  server.listen(HTTP_PORT, HTTP_HOST, () => {
    console.log(`Escuchando en http://${HTTP_HOST}:${HTTP_PORT}/send-group (esperando al script de Python)`);
  });
}

adquirirLock();
if (!LIST_GROUPS) {
  iniciarServidorEstado();
}
iniciar();
