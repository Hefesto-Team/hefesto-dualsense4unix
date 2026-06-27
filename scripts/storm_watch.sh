#!/usr/bin/env bash
# storm_watch.sh — registra o "storm" USB (-71) do DualSense num log dedicado.
#
# FEAT-DSX-STORM-WATCH-01. Diferente dos monitores ad-hoc (que viviam em /tmp,
# morriam no reboot e pediam sudo), este é replicável e roda pelo serviço de
# usuário `hefesto-dualsense4unix-storm-watch.service`:
#   - segue o log do kernel (journalctl -k -f) filtrando ' -71';
#   - anexa as linhas (já com timestamp) a um log dedicado, fácil de ler;
#   - sobrevive a reboot (o journald do sistema já persiste; este é só um
#     recorte legível só do storm).
#
# Não precisa de sudo se o usuário puder ler o journal do kernel (grupo
# systemd-journal/adm — padrão no Pop!_OS). Se não puder, registra a orientação
# e sai com erro (o serviço re-tenta com backoff).
#
# Uso manual: bash scripts/storm_watch.sh   (Ctrl+C encerra)
set -uo pipefail

STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix"
mkdir -p "${STATE_DIR}"
LOG="${STATE_DIR}/storm.log"

if ! command -v journalctl >/dev/null 2>&1; then
    echo "# $(date '+%F %T') storm-watch: journalctl ausente — abortando" >>"${LOG}"
    exit 1
fi

# Probe de permissão: lê 1 linha do kernel. Se falhar, o usuário não tem acesso
# ao journal do kernel — orienta e sai (serviço re-tenta com RestartSec).
if ! journalctl -k -n1 >/dev/null 2>&1; then
    {
        echo "# $(date '+%F %T') storm-watch: sem permissão p/ 'journalctl -k'."
        echo "#   Adicione seu usuário ao grupo: sudo usermod -aG systemd-journal \"\$USER\""
        echo "#   (relogin necessário). Re-tentando em background."
    } >>"${LOG}"
    exit 1
fi

echo "# $(date '+%F %T') storm-watch iniciado (segue journalctl -k por ' -71')" >>"${LOG}"

# -k kernel, -f follow, -n0 começa do agora (o journald já guarda o histórico),
# --grep filtra o erro USB do storm. Cada linha casada já vem com timestamp.
exec journalctl -k -f -n0 --grep=' -71' >>"${LOG}" 2>>"${LOG}"
