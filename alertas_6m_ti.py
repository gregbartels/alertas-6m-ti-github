#!/usr/bin/env python3
"""
alertas_6m_ti.py
=================

Monitor de apertura de banda de 6 metros (50 MHz) para Costa Rica (TI),
basado en dos fuentes públicas:
  - PSKReporter (https://pskreporter.info): modos digitales automáticos
    (FT8, FT4, WSPR, JS8Call, etc.)
  - Spothole (https://spothole.app): agrega spots de SSB y CW reportados
    manualmente en DX clusters tradicionales.

Qué hace
--------
Cada N minutos consulta ambas fuentes pidiendo la actividad reciente en el
rango de frecuencia de 6 m, y detecta dos situaciones:

  1. TI_ESCUCHA_DX : una estación TI (Costa Rica) reporta haber recibido
     (RX) una estación que NO es de Costa Rica.
  2. TI_ES_ESCUCHADO : una estación TI transmite y es escuchada por una
     estación fuera de Costa Rica, en cualquier parte del mundo.

Cuando aparece algo nuevo (que no se había alertado antes), envía un aviso
por correo y/o WhatsApp (vía CallMeBot).

Importante sobre PSKReporter
-----------------------------
- El endpoint de consulta (https://retrieve.pskreporter.info/query) es un
  servicio público, no oficial/documentado formalmente para este uso. Úsalo
  con cortesía: no bajes el intervalo de consulta por debajo de ~5 minutos.
- Solo detecta estaciones que usan modos digitales que reportan a
  PSKReporter (FT8, FT4, WSPR, etc. vía WSJT-X, JS8Call, etc.). No detecta
  SSB/CW a menos que alguien lo reporte manualmente.
- Los nombres exactos de los atributos XML pueden variar levemente; el
  parser es tolerante (usa valores por defecto si falta un campo) y deja
  un log de lo recibido para que sea fácil ajustar si PSKReporter cambia
  algo.

Requisitos
----------
    pip install requests

Configuración
--------------
Edita la sección "CONFIGURACIÓN" más abajo con tus datos de correo y/o
WhatsApp (CallMeBot). Todo lo demás son valores por defecto razonables.

Ejecución
---------
    python3 alertas_6m_ti.py

Se queda corriendo en un bucle infinito. Para dejarlo funcionando de forma
permanente, lo ideal es correrlo como servicio (systemd) o con `tmux`/
`screen`, o bien programarlo con cron para que se ejecute una vez y salga
(ver la variable RUN_ONCE más abajo).
"""

import json
import logging
import re
import smtplib
import sys
import time
import urllib.parse
from email.mime.text import MIMEText
from pathlib import Path
from xml.etree import ElementTree

import requests

# ============================== CONFIGURACIÓN ==============================

# --- Búsqueda en PSKReporter (modos digitales: FT8, FT4, WSPR, JS8, etc.) ---
BAND_FREQ_MIN_HZ = 50_000_000      # 50.000 MHz
BAND_FREQ_MAX_HZ = 54_000_000      # 54.000 MHz (cubre todo 6m, incluidas
                                    # las asignaciones más amplias de otros países)
CHECK_INTERVAL_SECONDS = 300       # cada cuánto consultar (recomendado: >= 300 = 5 min)

# Identificación del bot ante PSKReporter, tal como lo pide su desarrollador
# (Philip Gladstone) en https://groups.google.com/g/psk-reporter/c/gkQ3lcwzc6c
# - así, si alguna vez ve tráfico raro desde esta IP, puede contactarte en vez
# de simplemente bloquearla.
APPCONTACT = "tu-email@ejemplo.com"    # <-- pon aquí tu correo real
CALLSIGN_OPERADOR = "TU_INDICATIVO"    # <-- pon aquí tu indicativo real
LOOKBACK_SECONDS = 360             # ventana de "hace cuántos segundos" pedir
                                    # (un poco mayor al intervalo, para no perder reportes)

# --- Búsqueda en Spothole (SSB/CW vía DX clusters tradicionales, dxcluster.info) ---
# Spothole (https://spothole.app) agrega spots de varios DX clusters públicos
# y los expone en una API JSON simple, sin necesidad de mantener una conexión
# telnet abierta. Aquí solo pedimos SSB ("PHONE") y CW en 6m.
SPOTHOLE_ENABLED = True
SPOTHOLE_URL = "https://spothole.app/api/v2/spots"
SPOTHOLE_BAND = "6m"
SPOTHOLE_MODE_TYPES = "CW,PHONE,DATA"   # PHONE = SSB/voz; DATA = digital reportado a mano a un cluster
SPOTHOLE_MAX_AGE_SECONDS = 1800    # no traer spots más viejos que esto (30 min)
SPOTHOLE_LIMIT = 200

# Ventana (en segundos) para considerar que dos reportes -de la misma fuente
# o de fuentes distintas- son "el mismo contacto real": si PSKReporter y
# Spothole reportan el mismo par de estaciones dentro de esta ventana, se
# cuenta una sola vez. 600 = 10 minutos.
DEDUPE_VENTANA_SEGUNDOS = 600

# Prefijos de indicativo de Costa Rica (ITU): TI y TE
TI_PREFIX_REGEX = re.compile(r"^(TI|TE)\d", re.IGNORECASE)

# --- Aviso de caída de PSKReporter (en dos etapas, para no saturar el grupo) ---
# Etapa 1 ("caído"): tras este número de fallos SEGUIDOS, un único aviso.
# Etapa 2 ("escalación"): si sigue caído este número de fallos más, un único
# aviso de "revisar ASAP" - y de ahí no se manda nada más hasta que se
# recupere, sin importar cuánto dure la caída.
# Con el intervalo de 5 min por defecto: 2 fallos = 10 min, 4 fallos = 20 min.
AVISO_INICIAL_TRAS_FALLOS = 2
AVISO_ESCALACION_TRAS_FALLOS = 4

_psk_fallos_consecutivos = 0
_psk_caido_avisado = False
_psk_escalado_avisado = False

# --- Correo ---
EMAIL_ENABLED = False
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "tu_correo@gmail.com"
SMTP_PASSWORD = "tu_contraseña_de_aplicacion"   # usa una "app password", no tu clave normal
EMAIL_FROM = SMTP_USER
EMAIL_TO = "tu_correo@gmail.com"

# --- WhatsApp ---
# Modo "ninguno"   : no envía nada por WhatsApp.
# Modo "callmebot" : envía a UN número individual, vía CallMeBot (gratis, oficial-ish).
#                    1. Agrega el número que indica https://www.callmebot.com/blog/free-api-whatsapp-messages/
#                       a tus contactos de WhatsApp.
#                    2. Envíale el mensaje: "I allow callmebot to send me messages"
#                    3. Te va a responder con tu "apikey".
# Modo "grupo"      : envía directo al grupo de WhatsApp, a través del bot local
#                    (whatsapp_bot/index.js, con Baileys) que debe estar corriendo aparte.
WHATSAPP_MODE = "ninguno"  # "ninguno" | "callmebot" | "grupo"

CALLMEBOT_PHONE = "50688888888"   # tu número con código de país, sin "+"
CALLMEBOT_APIKEY = "123456"

GRUPO_BOT_URL = "http://127.0.0.1:3001/send-group"  # endpoint del bot Node/Baileys

# --- Estado / persistencia (para no repetir la misma alerta) ---
STATE_FILE = Path(__file__).with_name("estado_alertas_6m.json")
STATE_MAX_AGE_SECONDS = 24 * 3600   # cuánto tiempo guardar el historial de alertas ya enviadas

# --- Correr solo una vez y salir (útil si lo programas con cron) ---
RUN_ONCE = False

# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("alertas_6m_ti")

PSKREPORTER_URL = "https://retrieve.pskreporter.info/query"


def cargar_estado():
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            return data
        except Exception:
            log.warning("No se pudo leer el archivo de estado, se empieza de cero.")
    return {}


def guardar_estado(estado):
    ahora = time.time()
    # limpia entradas viejas para que el archivo no crezca indefinidamente
    estado = {k: v for k, v in estado.items() if ahora - v < STATE_MAX_AGE_SECONDS}
    STATE_FILE.write_text(json.dumps(estado))
    return estado


def consultar_pskreporter(lookback_seconds):
    """Consulta PSKReporter y devuelve una lista de reportes de recepción
    como diccionarios. Filtra por banda de 6m tanto en la consulta como
    (por seguridad) del lado del cliente."""
    params = {
        "flowStartSeconds": -abs(lookback_seconds),
        "frange": f"{BAND_FREQ_MIN_HZ}-{BAND_FREQ_MAX_HZ}",
        "rptlimit": 2000,
        "appcontact": APPCONTACT,
    }
    url = f"{PSKREPORTER_URL}?{urllib.parse.urlencode(params)}"
    log.debug("Consultando %s", url)

    user_agent = f"alertas-6m-ti/1.0 ({CALLSIGN_OPERADOR}; contact: {APPCONTACT})"
    resp = requests.get(url, timeout=30, headers={"User-Agent": user_agent})
    resp.raise_for_status()

    try:
        root = ElementTree.fromstring(resp.content)
    except ElementTree.ParseError:
        log.error("No se pudo interpretar la respuesta XML de PSKReporter.")
        log.debug("Respuesta cruda: %s", resp.text[:2000])
        return []

    reportes = []
    for el in root.iter():
        # el nombre del elemento puede venir con o sin espacio de nombres
        tag = el.tag.split("}")[-1]
        if tag != "receptionReport":
            continue
        attrs = el.attrib
        try:
            freq = int(attrs.get("frequency", "0"))
        except ValueError:
            freq = 0
        # filtro de banda por si el parámetro frange no lo hizo el servidor
        if not (BAND_FREQ_MIN_HZ <= freq <= BAND_FREQ_MAX_HZ):
            continue
        reportes.append(
            {
                "sender": attrs.get("senderCallsign", "").upper(),
                "sender_locator": attrs.get("senderLocator", ""),
                "sender_dxcc": attrs.get("senderDXCC", ""),
                "receiver": attrs.get("receiverCallsign", "").upper(),
                "receiver_locator": attrs.get("receiverLocator", ""),
                "receiver_dxcc": attrs.get("receiverDXCC", ""),
                "freq_hz": freq,
                "mode": attrs.get("mode", "?"),
                "snr": attrs.get("sNR", attrs.get("snr", "?")),
                "flow_start": attrs.get("flowStartSeconds", "0"),
                "fuente": "PSKReporter",
            }
        )
    return reportes


def consultar_spothole(max_age_seconds):
    """Consulta Spothole (agregador de DX clusters) pidiendo spots de SSB/CW
    en 6m, y los devuelve en el mismo formato que consultar_pskreporter(),
    para que el resto del programa los trate igual.

    Nombres de campo confirmados contra el openapi.yml oficial de Spothole
    (API v2): dx_call, dx_grid, dx_country, de_call, de_grid, de_country,
    freq (en Hz), mode, mode_type, time (epoch en segundos), band.
    """
    params = {
        "band": SPOTHOLE_BAND,
        "mode_type": SPOTHOLE_MODE_TYPES,
        "max_age": max_age_seconds,
        "limit": SPOTHOLE_LIMIT,
    }
    url = f"{SPOTHOLE_URL}?{urllib.parse.urlencode(params)}"
    log.debug("Consultando %s", url)

    resp = requests.get(
        url, timeout=30,
        headers={"User-Agent": f"alertas-6m-ti/1.0 ({CALLSIGN_OPERADOR}; contact: {APPCONTACT})"},
    )
    resp.raise_for_status()

    try:
        datos = resp.json()
    except ValueError:
        log.error("No se pudo interpretar la respuesta JSON de Spothole.")
        log.debug("Respuesta cruda: %s", resp.text[:2000])
        return []

    # /api/v2/spots devuelve directamente una lista (SpotList); se deja el
    # fallback por si algún día cambia a un objeto envolvente.
    if isinstance(datos, dict):
        spots = datos.get("spots") or datos.get("data") or []
    else:
        spots = datos

    reportes = []
    for s in spots:
        if not isinstance(s, dict):
            continue

        try:
            freq_hz = int(float(s.get("freq", 0)))
        except (TypeError, ValueError):
            freq_hz = 0

        if not (BAND_FREQ_MIN_HZ <= freq_hz <= BAND_FREQ_MAX_HZ):
            continue

        dx_call = (s.get("dx_call") or "").upper()
        de_call = (s.get("de_call") or "").upper()
        if not dx_call or not de_call:
            continue

        reportes.append(
            {
                # "dx_call" = la estación que fue escuchada/reportada (equivale
                # a "sender" de PSKReporter); "de_call" = quien hizo el spot
                # (equivale a "receiver").
                "sender": dx_call,
                "sender_locator": s.get("dx_grid", ""),
                "sender_dxcc": s.get("dx_country", ""),
                "receiver": de_call,
                "receiver_locator": s.get("de_grid", ""),
                "receiver_dxcc": s.get("de_country", ""),
                "freq_hz": freq_hz,
                "mode": s.get("mode", "SSB/CW"),
                "snr": "-",  # Spothole/clusters no suelen traer SNR
                "flow_start": s.get("time", time.time()),
                "fuente": "Cluster (Spothole)",
            }
        )
    return reportes


def es_ti(callsign):
    return bool(TI_PREFIX_REGEX.match(callsign or ""))


def clasificar(reportes):
    """Separa los reportes en los dos tipos de evento que interesan."""
    eventos = []
    for r in reportes:
        sender_ti = es_ti(r["sender"])
        receiver_ti = es_ti(r["receiver"])

        if receiver_ti and not sender_ti:
            eventos.append(("TI_ESCUCHA_DX", r))
        elif sender_ti and not receiver_ti:
            eventos.append(("TI_ES_ESCUCHADO", r))
        # si ambos son TI (contacto interno) no es de interés aquí
    return eventos


def clave_unica(tipo, r):
    """Identifica un evento por PAR DE ESTACIONES + ventana de tiempo,
    sin incluir la fuente. Así, si PSKReporter y Spothole reportan el mismo
    contacto real (por ejemplo, alguien lo reporta a mano justo cuando
    PSKReporter también lo capta automáticamente), se trata como un solo
    evento en vez de dos líneas duplicadas."""
    try:
        marca = float(r.get("flow_start", 0))
    except (TypeError, ValueError):
        marca = 0
    ventana = int(marca // DEDUPE_VENTANA_SEGUNDOS)
    return f"{tipo}:{r['sender']}:{r['receiver']}:{ventana}"


def _lugar(*partes):
    """Arma un '(locator, país)' sin comas colgando cuando algún dato falta."""
    partes = [p for p in partes if p]
    return f" ({', '.join(partes)})" if partes else ""


def formatear_mensaje(eventos):
    lineas = ["📻🚨 Apertura en 6 m (50 MHz) relacionada con Costa Rica (TI):", ""]
    for tipo, r in eventos:
        freq_mhz = r["freq_hz"] / 1_000_000
        etiqueta = f"[{r.get('fuente', '?')}] "
        if tipo == "TI_ESCUCHA_DX":
            lineas.append(
                f"• 📥 {etiqueta}{r['receiver']}{_lugar(r['receiver_locator'])} recibió a "
                f"{r['sender']}{_lugar(r['sender_locator'], r['sender_dxcc'])} "
                f"en {freq_mhz:.4f} MHz {r['mode']} (SNR {r['snr']})"
            )
        else:
            lineas.append(
                f"• 📤 {etiqueta}{r['sender']}{_lugar(r['sender_locator'])} fue escuchado por "
                f"{r['receiver']}{_lugar(r['receiver_locator'], r['receiver_dxcc'])} "
                f"en {freq_mhz:.4f} MHz {r['mode']} (SNR {r['snr']})"
            )
    return "\n".join(lineas)


def enviar_email(asunto, cuerpo):
    if not EMAIL_ENABLED:
        return
    try:
        msg = MIMEText(cuerpo, _charset="utf-8")
        msg["Subject"] = asunto
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        log.info("Correo enviado.")
    except Exception as e:
        log.error("Error enviando correo: %s", e)


def enviar_whatsapp(texto):
    if WHATSAPP_MODE == "ninguno":
        return
    elif WHATSAPP_MODE == "callmebot":
        _enviar_whatsapp_callmebot(texto)
    elif WHATSAPP_MODE == "grupo":
        _enviar_whatsapp_grupo(texto)
    else:
        log.warning("WHATSAPP_MODE desconocido: %s", WHATSAPP_MODE)


def _enviar_whatsapp_callmebot(texto):
    try:
        params = {
            "phone": CALLMEBOT_PHONE,
            "text": texto,
            "apikey": CALLMEBOT_APIKEY,
        }
        url = "https://api.callmebot.com/whatsapp.php?" + urllib.parse.urlencode(params)
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            log.info("WhatsApp (CallMeBot) enviado.")
        else:
            log.error("CallMeBot respondió %s: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        log.error("Error enviando WhatsApp por CallMeBot: %s", e)


def _enviar_whatsapp_grupo(texto):
    """Envía el mensaje al grupo de WhatsApp llamando al bot local de Node/Baileys
    (whatsapp_bot/index.js), que debe estar corriendo en la misma máquina."""
    try:
        resp = requests.post(GRUPO_BOT_URL, json={"text": texto}, timeout=40)
        if resp.status_code == 200:
            log.info("WhatsApp (grupo) enviado.")
        else:
            log.error("El bot de WhatsApp respondió %s: %s", resp.status_code, resp.text[:200])
    except requests.exceptions.ConnectionError:
        log.error(
            "No se pudo conectar con el bot de WhatsApp en %s. "
            "¿Está corriendo `node whatsapp_bot/index.js`?",
            GRUPO_BOT_URL,
        )
    except Exception as e:
        log.error("Error enviando WhatsApp al grupo: %s", e)


def ciclo():
    global _psk_fallos_consecutivos, _psk_caido_avisado, _psk_escalado_avisado

    estado = cargar_estado()
    reportes = []

    try:
        reportes_psk = consultar_pskreporter(LOOKBACK_SECONDS)
        log.info("PSKReporter: %d reportes en 6m", len(reportes_psk))
        reportes.extend(reportes_psk)

        if _psk_caido_avisado:
            minutos = _psk_fallos_consecutivos * CHECK_INTERVAL_SECONDS // 60
            log.info("PSKReporter se recuperó tras ~%d min caído.", minutos)
            texto = f"✅ PSKReporter volvió a responder (llevaba ~{minutos} min caído). Monitoreo completo (digital + SSB/CW) restablecido."
            enviar_email("PSKReporter recuperado", texto)
            enviar_whatsapp(texto)
            _psk_caido_avisado = False
            _psk_escalado_avisado = False
        _psk_fallos_consecutivos = 0

    except Exception as e:
        log.error("Error consultando PSKReporter: %s", e)
        _psk_fallos_consecutivos += 1

        if _psk_fallos_consecutivos == AVISO_INICIAL_TRAS_FALLOS and not _psk_caido_avisado:
            minutos = AVISO_INICIAL_TRAS_FALLOS * CHECK_INTERVAL_SECONDS // 60
            codigo = getattr(getattr(e, "response", None), "status_code", None)
            detalle = f" (código {codigo})" if codigo else ""
            texto = (
                f"⚠️ PSKReporter lleva unos {minutos} min sin responder{detalle}. "
                f"Seguimos monitoreando 6m solo con Spothole (SSB/CW/digital manual) mientras tanto."
            )
            enviar_email("PSKReporter caído", texto)
            enviar_whatsapp(texto)
            _psk_caido_avisado = True

        elif _psk_fallos_consecutivos == AVISO_ESCALACION_TRAS_FALLOS and not _psk_escalado_avisado:
            minutos = AVISO_ESCALACION_TRAS_FALLOS * CHECK_INTERVAL_SECONDS // 60
            texto = (
                f"🚨 PSKReporter sigue caído desde hace unos {minutos} min. Revisar ASAP si es posible "
                f"(https://pskreporter.info/pskmap.html). No se repetirá este aviso hasta que se recupere."
            )
            enviar_email("PSKReporter sigue caído - revisar", texto)
            enviar_whatsapp(texto)
            _psk_escalado_avisado = True

    if SPOTHOLE_ENABLED:
        try:
            reportes_cluster = consultar_spothole(SPOTHOLE_MAX_AGE_SECONDS)
            log.info("Spothole (cluster): %d spots SSB/CW en 6m", len(reportes_cluster))
            reportes.extend(reportes_cluster)
        except Exception as e:
            log.error("Error consultando Spothole: %s", e)

    eventos = clasificar(reportes)

    nuevos = []
    for tipo, r in eventos:
        k = clave_unica(tipo, r)
        if k not in estado:
            estado[k] = time.time()
            nuevos.append((tipo, r))

    if nuevos:
        log.info("Eventos nuevos: %d", len(nuevos))
        mensaje = formatear_mensaje(nuevos)
        print(mensaje)
        enviar_email("Apertura de 6m - TI", mensaje)
        # WhatsApp tiene límite de longitud razonable; si hay muchos eventos
        # los manda en un solo mensaje igual, CallMeBot lo admite bien.
        enviar_whatsapp(mensaje)
    else:
        log.info("Sin eventos nuevos en este ciclo.")

    guardar_estado(estado)


def prueba():
    """Envía un mensaje de prueba simple por el mismo camino que una alerta
    real (enviar_email, enviar_whatsapp), sin depender de PSKReporter ni
    Spothole. Sirve para confirmar que el canal de entrega funciona, sin
    tener que esperar una apertura real de 6m.
    Uso: python3 alertas_6m_ti.py --test
    """
    mensaje = "🤖 Únicamente prueba de bot. Beep boop. Reiniciando sistema."
    print("--- Mensaje de prueba que se va a enviar ---")
    print(mensaje)
    print("--------------------------------------------")
    enviar_email("Prueba - Bot 6m TI", mensaje)
    enviar_whatsapp(mensaje)
    print("Prueba enviada (revisa correo/WhatsApp según lo que tengas activado).")


def main():
    if "--test" in sys.argv:
        prueba()
        return
    log.info("Iniciando monitor de 6m para TI (Ctrl+C para salir).")
    while True:
        ciclo()
        if RUN_ONCE:
            break
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
