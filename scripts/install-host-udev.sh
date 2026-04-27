#!/usr/bin/env bash
# install-host-udev.sh — Instala regras udev do Hefesto - Dualsense4Unix no sistema hospedeiro
#
# Executado UMA vez pelo usuário após instalar o bundle Flatpak:
#   flatpak run --command=install-host-udev.sh br.andrefarias.Hefesto
#
# Também pode ser executado diretamente no host (fora do Flatpak) se o Hefesto - Dualsense4Unix
# foi instalado via .deb ou pip:
#   sudo bash scripts/install-host-udev.sh
#
# As regras concedem acesso ao DualSense via hidraw sem necessidade de root
# a cada execução, e previnem autosuspend USB que derruba a conexão.
#
# Requer pkexec (polkit) ou execução com sudo.

set -euo pipefail

# Dentro do Flatpak, as rules ficam em /app/share/hefesto-dualsense4unix/udev-rules/
# Fora do Flatpak (instalação nativa), ficam em assets/ relativo ao script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -d "/app/share/hefesto-dualsense4unix/udev-rules" ]]; then
  # Executando dentro do bundle Flatpak
  RULES_SRC="/app/share/hefesto-dualsense4unix/udev-rules"
else
  # Executando fora do Flatpak (repositório local ou .deb)
  RULES_SRC="${SCRIPT_DIR}/../assets"
fi

RULES_DEST="/etc/udev/rules.d"

# Regras a instalar (pelo nome do arquivo)
RULES=(
  "70-ps5-controller.rules"
  "71-uinput.rules"
  "72-ps5-controller-autosuspend.rules"
)

# Verificar se as rules existem na origem
echo "Hefesto - Dualsense4Unix — instalação de regras udev"
echo ""
echo "Origem: ${RULES_SRC}"
echo "Destino: ${RULES_DEST}"
echo ""

for regra in "${RULES[@]}"; do
  if [[ ! -f "${RULES_SRC}/${regra}" ]]; then
    echo "ERRO: arquivo não encontrado: ${RULES_SRC}/${regra}"
    exit 1
  fi
done

echo "As seguintes regras serão copiadas para ${RULES_DEST}:"
for regra in "${RULES[@]}"; do
  echo "  - ${regra}"
done
echo ""
echo "Esta operação requer senha de administrador (pkexec/sudo)."
echo ""

# Função de instalação — executada com privilégios elevados
instalar_rules() {
  for regra in "${RULES[@]}"; do
    cp "${RULES_SRC}/${regra}" "${RULES_DEST}/${regra}"
    chmod 644 "${RULES_DEST}/${regra}"
    echo "  Instalado: ${RULES_DEST}/${regra}"
  done

  # Recarregar udev e re-disparar eventos para dispositivos PS5 já conectados
  udevadm control --reload-rules
  udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=054c 2>/dev/null || true
  udevadm trigger --subsystem-match=usb    --attr-match=idVendor=054c 2>/dev/null || true

  echo ""
  echo "Regras instaladas com sucesso."
  echo "Desconecte e reconecte o controle DualSense para aplicar as permissões."
}

# Decidir como elevar privilégios
if [[ "$(id -u)" -eq 0 ]]; then
  # Já rodando como root (ex: sudo bash install-host-udev.sh)
  instalar_rules
elif command -v pkexec &>/dev/null; then
  # Dentro do Flatpak ou sistema com polkit — pkexec é o caminho canônico
  pkexec bash -c "
    RULES_SRC='${RULES_SRC}'
    RULES_DEST='${RULES_DEST}'
    for regra in ${RULES[*]}; do
      cp \"\${RULES_SRC}/\${regra}\" \"\${RULES_DEST}/\${regra}\"
      chmod 644 \"\${RULES_DEST}/\${regra}\"
      echo \"  Instalado: \${RULES_DEST}/\${regra}\"
    done
    udevadm control --reload-rules
    udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=054c 2>/dev/null || true
    udevadm trigger --subsystem-match=usb    --attr-match=idVendor=054c 2>/dev/null || true
    echo 'Regras instaladas com sucesso.'
  "
elif command -v sudo &>/dev/null; then
  # Fallback para sudo (fora do Flatpak em sistemas sem polkit)
  sudo bash -c "
    for regra in ${RULES[*]}; do
      cp '${RULES_SRC}/'\${regra} '${RULES_DEST}/'\${regra}
      chmod 644 '${RULES_DEST}/'\${regra}
      echo \"  Instalado: ${RULES_DEST}/\${regra}\"
    done
    udevadm control --reload-rules
    udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=054c 2>/dev/null || true
    echo 'Regras instaladas com sucesso.'
  "
else
  echo "ERRO: nenhum método de elevação de privilégio encontrado (pkexec ou sudo)."
  echo "Execute manualmente como root:"
  for regra in "${RULES[@]}"; do
    echo "  sudo cp ${RULES_SRC}/${regra} ${RULES_DEST}/${regra}"
  done
  echo "  sudo udevadm control --reload-rules"
  exit 1
fi
