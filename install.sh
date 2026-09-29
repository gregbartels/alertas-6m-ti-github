#!/usr/bin/env bash
#
# install.sh - instalador de un click para el bot de alertas de 6m (TI / PSKReporter)
#
# Qué hace automáticamente:
#   - Instala Node.js, Python y sus dependencias
#   - Te pregunta los datos de correo y de WhatsApp, y los escribe en la config
#   - Arma y activa los servicios systemd para que todo corra 24/7
#
# Lo único que NO puede automatizar (porque WhatsApp no lo permite de otra
# forma): escanear el código QR con el teléfono para vincular la cuenta.
# El script se detiene justo en ese paso y te espera.
#
# Uso:
#   chmod +x install.sh
#   ./install.sh
#
set -e

BOLD='\033[1m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
paso()  { echo -e "\n${BOLD}${GREEN}==> $1${NC}"; }
aviso() { echo -e "${YELLOW}$1${NC}"; }

# Escapa caracteres especiales de sed (/, &, \) en un valor antes de usarlo
# como reemplazo, para que contraseñas/correos con esos caracteres no rompan
# el comando.
escape_sed() { printf '%s' "$1" | sed -e 's/[\/&\\]/\\&/g'; }

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(whoami)"
cd "$INSTALL_DIR"

echo -e "${BOLD}Instalador del bot de alertas de 6m (TI / PSKReporter)${NC}"
echo "Carpeta de instalación: $INSTALL_DIR"
echo "Usuario: $CURRENT_USER"

# ----------------------------------------------------------------------------
paso "1/7 Actualizando paquetes del sistema"
sudo apt-get update -y

# ----------------------------------------------------------------------------
paso "2/7 Instalando Node.js (si hace falta)"
if ! command -v node >/dev/null 2>&1; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
else
    echo "Node.js ya está instalado: $(node -v)"
fi

# ----------------------------------------------------------------------------
paso "3/7 Instalando Python y pip (si hace falta)"
sudo apt-get install -y python3 python3-pip
pip3 install requests --break-system-packages 2>/dev/null || pip3 install requests

# ----------------------------------------------------------------------------
paso "4/7 Instalando dependencias del bot de WhatsApp (npm install)"
(cd whatsapp_bot && npm install)

# ----------------------------------------------------------------------------
paso "5/7 Configuración de correo"
read -rp "¿Quieres activar también alertas por correo? [s/N]: " QUIERE_CORREO
if [[ "$QUIERE_CORREO" =~ ^[sSyY] ]]; then
    read -rp "Correo SMTP para enviar alertas (ej: tuusuario@gmail.com): " SMTP_USER
    read -rsp "Contraseña de aplicación de ese correo: " SMTP_PASSWORD; echo
    read -rp "Correo de destino para las alertas [$SMTP_USER]: " EMAIL_TO
    EMAIL_TO=${EMAIL_TO:-$SMTP_USER}

    sed -i "s|^EMAIL_ENABLED = .*|EMAIL_ENABLED = True|" alertas_6m_ti.py
    sed -i "s|^SMTP_USER = .*|SMTP_USER = \"$(escape_sed "$SMTP_USER")\"|" alertas_6m_ti.py
    sed -i "s|^SMTP_PASSWORD = .*|SMTP_PASSWORD = \"$(escape_sed "$SMTP_PASSWORD")\"|" alertas_6m_ti.py
    sed -i "s|^EMAIL_TO = .*|EMAIL_TO = \"$(escape_sed "$EMAIL_TO")\"|" alertas_6m_ti.py
else
    sed -i "s|^EMAIL_ENABLED = .*|EMAIL_ENABLED = False|" alertas_6m_ti.py
    echo "Correo desactivado, solo se usará WhatsApp."
fi

# ----------------------------------------------------------------------------
paso "6/7 Configuración de WhatsApp"
echo "¿Cómo quieres recibir las alertas por WhatsApp?"
echo "  1) No usar WhatsApp (solo correo)"
echo "  2) A un número individual, vía CallMeBot"
echo "  3) Directo al grupo de WhatsApp (vía Baileys)"
read -rp "Elige una opción [1-3]: " OPCION_WA

GROUP_JID=""

case "$OPCION_WA" in
  2)
    sed -i 's/^WHATSAPP_MODE = .*/WHATSAPP_MODE = "callmebot"  # ninguno \/ callmebot \/ grupo/' alertas_6m_ti.py
    read -rp "Tu número con código de país, sin '+' (ej: 50688888888): " CB_PHONE
    read -rp "Tu apikey de CallMeBot: " CB_APIKEY
    sed -i "s|^CALLMEBOT_PHONE = .*|CALLMEBOT_PHONE = \"$(escape_sed "$CB_PHONE")\"|" alertas_6m_ti.py
    sed -i "s|^CALLMEBOT_APIKEY = .*|CALLMEBOT_APIKEY = \"$(escape_sed "$CB_APIKEY")\"|" alertas_6m_ti.py
    ;;
  3)
    sed -i 's/^WHATSAPP_MODE = .*/WHATSAPP_MODE = "grupo"  # ninguno \/ callmebot \/ grupo/' alertas_6m_ti.py
    aviso "\nAhora toca vincular la cuenta de WhatsApp que ya está en tu grupo."
    aviso "Va a aparecer un código QR: escanéalo desde WhatsApp > Dispositivos vinculados > Vincular un dispositivo,\ncon el número que ya agregaste al grupo de alertas.\n"
    read -rp "Presiona Enter cuando estés listo para ver el QR..." _
    (cd whatsapp_bot && node index.js --list-groups) || true
    echo ""
    read -rp "Pega aquí el ID del grupo que quieres usar (termina en @g.us): " GROUP_JID
    ;;
  *)
    sed -i 's/^WHATSAPP_MODE = .*/WHATSAPP_MODE = "ninguno"  # ninguno \/ callmebot \/ grupo/' alertas_6m_ti.py
    ;;
esac

# ----------------------------------------------------------------------------
paso "7/7 Armando y activando los servicios systemd"

PY_SERVICE="systemd/alertas-6m-python.service"
WA_SERVICE="systemd/alertas-6m-whatsapp.service"

# Ajusta usuario y rutas reales de esta instalación en ambos archivos
sed -i "s|^User=.*|User=$CURRENT_USER|" "$PY_SERVICE" "$WA_SERVICE"
sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|" "$PY_SERVICE"
sed -i "s|^WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR/whatsapp_bot|" "$WA_SERVICE"

if [ -n "$GROUP_JID" ]; then
    sed -i "s|^Environment=GROUP_JID=.*|Environment=GROUP_JID=$(escape_sed "$GROUP_JID")|" "$WA_SERVICE"
fi

sudo cp "$PY_SERVICE" "$WA_SERVICE" /etc/systemd/system/
sudo systemctl daemon-reload

if [ "$OPCION_WA" = "3" ]; then
    sudo systemctl enable --now alertas-6m-whatsapp.service
fi
sudo systemctl enable --now alertas-6m-python.service

# ----------------------------------------------------------------------------
paso "Listo"
echo "Servicios activos. Para revisar el estado y los logs:"
echo "  sudo systemctl status alertas-6m-python"
[ "$OPCION_WA" = "3" ] && echo "  sudo systemctl status alertas-6m-whatsapp"
echo "  journalctl -u alertas-6m-python -f"
echo ""
echo "El bot ya está monitoreando 6m para estaciones TI en PSKReporter."
