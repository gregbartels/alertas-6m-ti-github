# Cómo funciona el código

Explicación técnica del funcionamiento interno, pensada para quien quiera entender, modificar o adaptar el proyecto — no hace falta ser programador experto, pero sí ayuda tener algo de familiaridad con Python y JavaScript básico.

*[Read in English (HOW_IT_WORKS.en.md)](HOW_IT_WORKS.en.md)*

## Panorama general

El proyecto son **dos programas independientes** que se comunican entre sí por HTTP local, cada uno corriendo como su propio servicio de `systemd`:

```
PSKReporter ─┐
             ├─▶ alertas_6m_ti.py (Python) ─▶ HTTP (127.0.0.1:3001) ─▶ whatsapp_bot/index.js (Node) ─▶ Grupo de WhatsApp
Spothole ────┘                                                                    │
                                                                                   └─▶ Página web de estado/QR (127.0.0.1:3002)
```

**¿Por qué dos programas en vez de uno?** Porque hablar con WhatsApp de forma no oficial (vía Baileys) solo existe como librería de **Node.js/JavaScript**, mientras que el resto de la lógica (consultar APIs, filtrar, decidir) se escribió en **Python** por ser más simple de leer y mantener para ese tipo de tarea. En vez de forzar todo a un solo lenguaje, cada parte usa la herramienta que mejor le queda, y se comunican por un puente HTTP simple.

## `alertas_6m_ti.py` — el cerebro de la detección

### Configuración (arriba del archivo)

Todo lo ajustable vive como constantes al inicio: rango de frecuencia de 6m en Hz, intervalo de consulta, prefijos de indicativo de Costa Rica (expresión regular `^(TI|TE)\d`), parámetros de Spothole, umbrales de aviso de caída, y los datos de correo/WhatsApp. Cambiar el comportamiento del bot casi siempre es editar un valor aquí, no tocar la lógica de abajo.

### `consultar_pskreporter(lookback_seconds)`

Arma una URL GET hacia `retrieve.pskreporter.info/query` con:
- `flowStartSeconds` — negativo, significa "los últimos N segundos".
- `frange` — rango de frecuencia en Hz (acota a 6 metros del lado del servidor).
- `rptlimit` — tope de resultados (2000; ver la nota sobre por qué no es exagerado en el propio código).
- `appcontact` — tu correo, para identificarte ante el servicio (ver `INSTALL.es.md` sección 4).

La respuesta es XML; se parsea con `xml.etree.ElementTree` buscando elementos `receptionReport`, y cada uno se convierte a un diccionario con claves uniformes (`sender`, `receiver`, `freq_hz`, `mode`, etc.) — el mismo "molde" que usa la función de Spothole, para que el resto del código no tenga que saber de cuál fuente vino cada dato.

### `consultar_spothole(max_age_seconds)`

Igual que la anterior, pero hacia `spothole.app/api/v2/spots`, pidiendo banda `6m` y `mode_type=CW,PHONE,DATA` (CW, SSB, y digital reportado a mano). La respuesta es JSON directo (una lista), documentada en su [OpenAPI spec](https://spothole.app/apidocs) — los nombres de campo (`dx_call`, `de_call`, `freq`, etc.) están confirmados contra esa especificación oficial, no adivinados.

### `clasificar(reportes)`

Recorre la lista combinada de reportes (de ambas fuentes) y separa cada uno en dos categorías, usando `es_ti()` (que aplica la expresión regular de prefijo) sobre el emisor y el receptor de cada reporte:

- `TI_ESCUCHA_DX` — el receptor es TI, el emisor no.
- `TI_ES_ESCUCHADO` — el emisor es TI, el receptor no.

Si ambos son TI (contacto interno entre dos costarricenses), se ignora — no es información nueva sobre alcance internacional.

### `clave_unica(tipo, r)` — evitar alertas duplicadas

Cada evento se identifica por **tipo + par de estaciones + ventana de tiempo de 10 minutos** (no por fuente ni por marca de tiempo exacta). Esto es a propósito: si el mismo contacto real llega tanto por PSKReporter como por Spothole (por ejemplo, si PSKReporter se recupera de una caída justo cuando Spothole ya había reportado algo), cuenta como un solo evento, no dos. El estado de qué ya se avisó se guarda en `estado_alertas_6m.json`, con una limpieza automática de entradas de más de 24 horas.

### `formatear_mensaje(eventos)`

Arma el texto final: encabezado fijo, una línea por evento con flecha de dirección (📥/📤), fuente entre corchetes, y los datos del contacto. La función `_lugar()` evita comas colgando cuando falta un dato (como el país del receptor, que PSKReporter no siempre reporta).

### `enviar_email()` / `enviar_whatsapp()`

`enviar_email` usa `smtplib` directo (nada de librerías externas). `enviar_whatsapp` es un despachador según `WHATSAPP_MODE`: si es `"grupo"`, hace un POST a `http://127.0.0.1:3001/send-group` — es decir, le habla al programa de Node por HTTP local, no directamente a WhatsApp.

### `ciclo()` — el corazón del programa

Se ejecuta una vez por intervalo (`CHECK_INTERVAL_SECONDS`, 5 minutos por defecto):

1. Consulta PSKReporter (con manejo de errores: si falla, cuenta el fallo y sigue).
2. Si el número de fallos seguidos cruza `AVISO_INICIAL_TRAS_FALLOS` o `AVISO_ESCALACION_TRAS_FALLOS`, manda un aviso único (no repetido) al grupo/correo.
3. Consulta Spothole (independiente del resultado de PSKReporter).
4. Clasifica todos los reportes combinados.
5. Filtra los que ya se habían avisado (`clave_unica`).
6. Si hay eventos nuevos, arma el mensaje y lo envía.
7. Guarda el estado actualizado.

### `prueba()` / `--test`

Manda un mensaje corto fijo por el mismo camino real (`enviar_email`, `enviar_whatsapp`), sin tocar PSKReporter ni Spothole — sirve para probar el canal de entrega en segundos, sin esperar tráfico real.

## `whatsapp_bot/index.js` — el puente a WhatsApp

### Conexión con Baileys

`makeWASocket()` crea la conexión, usando `useMultiFileAuthState()` para guardar/leer las credenciales de sesión en `auth_info/` (archivos que **nunca** se deben compartir ni subir a un repositorio — son las llaves que permiten actuar como tu cuenta). El perfil de navegador (`Browsers.macOS('Desktop')`) hace que WhatsApp vea la conexión como un cliente legítimo tipo WhatsApp Desktop, en vez de un nombre inventado.

### El candado (`adquirirLock()` / `liberarLock()`)

Antes de conectar, escribe su propio PID en un archivo `.whatsapp_bot.lock`. Si ese archivo ya existe y el proceso dueño sigue vivo, se niega a arrancar — esto evita que dos instancias (por ejemplo, una manual y otra de `systemd`) peleen por la misma sesión de WhatsApp y la tumben.

### Respaldo y auto-restauración de sesión

Cada vez que conecta bien (`respaldarSesion()`), copia `auth_info/` a `auth_info_backup/`. Si al arrancar la carpeta principal está vacía o dañada pero el respaldo existe, la restaura sola (`restaurarSesionSiHaceFalta()`) — pensado para sobrevivir un corte de luz que corrompa archivos a medio escribir.

### Página de estado/QR (puerto 3002)

Un segundo servidor HTTP, separado del de envío, que corre desde el arranque del proceso (no solo cuando ya está conectado). Sirve una página con auto-refresco cada 10 segundos que muestra el código QR actual como imagen (usando la librería `qrcode`, distinta de `qrcode-terminal`) o un mensaje de "conectado", según el estado.

### Servidor de envío (puerto 3001)

Expone `POST /send-group`, que recibe `{"text": "..."}` y llama a `enviarConReintento()` — que intenta `sock.sendMessage()`, y si falla (por ejemplo con el error `"No sessions"`, típico justo después de reconectar), espera 5 segundos y reintenta una vez más antes de darse por vencido.

### Precalentamiento del grupo

Justo después de conectar, llama a `sock.groupMetadata(GROUP_JID)` una vez — esto fuerza a Baileys a sincronizar las claves de cifrado de los participantes del grupo antes de aceptar envíos, evitando el error `"No sessions"` en el primer mensaje tras una reconexión.

## `install.sh` — el instalador

Es un script de bash que automatiza todo lo anterior: instala Node/Python, pregunta la configuración (correo, modo de WhatsApp), y si eliges "grupo", corre `node index.js --list-groups` para que escanees el QR y elijas el grupo. Al final, ajusta los archivos `.service` de `systemd` con las rutas reales de tu instalación (usuario, carpeta) y los activa.

## `systemd/*.service`

Dos archivos de configuración que le dicen a Linux "mantén esto corriendo siempre, y si se cae, reinícialo" (`Restart=on-failure`). `alertas-6m-python.service` corre `python3 alertas_6m_ti.py`; `alertas-6m-whatsapp.service` corre `node index.js`. Ninguno depende de que haya una sesión de terminal abierta.

## Ideas para extender el proyecto

- **Otro país/prefijo**: cambia `TI_PREFIX_REGEX` y los textos del mensaje.
- **Otra banda**: cambia `BAND_FREQ_MIN_HZ`/`BAND_FREQ_MAX_HZ` y `SPOTHOLE_BAND`.
- **Otro canal de salida** (Telegram, Discord): agregarías una función `enviar_telegram()` junto a las existentes, y la llamarías desde `ciclo()` igual que `enviar_whatsapp()`. Telegram en particular es más simple porque tiene una API oficial de bots, sin nada del manejo de sesión que requiere WhatsApp.
- **Más fuentes de datos**: cualquier servicio que exponga spots de radio por HTTP/JSON puede sumarse con el mismo patrón que `consultar_spothole()` — devolver una lista de diccionarios con las mismas claves, y sumarla a `reportes` dentro de `ciclo()`.
