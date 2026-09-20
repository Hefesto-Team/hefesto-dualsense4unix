#!/usr/bin/env bash
# regra_do_no_aberta.sh — escreve a variante ABERTA do 70-ps5-controller.rules.
#
# Uso: bash scripts/regra_do_no_aberta.sh ORIGEM DESTINO
#
# POR QUE ESTE ARQUIVO NASCEU (20/09/2026)
# ========================================
# A cura O-NO-NASCE-FECHADO-01 tem DUAS METADES e elas não podem viajar
# separadas:
#
#   1. a regra udev que faz o `/dev/hidraw` do DualSense físico nascer
#      `0600 root` (`TAG-="uaccess"`);
#   2. o broker `hefesto-hidraw-broker`, que é quem o ABRE sob pedido.
#
# Quem instala só a metade 1 entrega um DualSense INUTILIZÁVEL: o nó nasce
# fechado e não existe ninguém para abri-lo. Foi o que a auditoria mediu nos
# pacotes de distro — `packaging/{arch,fedora,nix}` e o `build_deb.sh` gravam
# o asset (fechado) em `/usr/lib/udev/rules.d/` e disparam
# `udevadm control --reload-rules`, mas o broker é instalado FORA do pacote
# (pelo `install-host-udev.sh`, que precisa do uid da sessão e por isso não
# pode rodar no `postinst`). Num `.deb` ou `.rpm` o controle ficava morto até
# alguém rodar o helper à mão.
#
# Isso bate de frente com a ordem dela de 11/09/2026 — *o produto é para
# qualquer usuário; nada pode depender da bancada, do perfil ou dos jogos
# dela*.
#
# A REGRA QUE ISTO IMPLEMENTA: **quem não instala o broker instala a regra
# ABERTA.** O asset versionado continua sendo o FECHADO — ele é o default dela
# («isso deveria estar no install por default») e é o que os caminhos que
# levam o broker junto (`install.sh` → `install_udev.sh`, e o
# `install-host-udev.sh` quando consegue renderizar o broker) gravam em
# `/etc/udev/rules.d/`, que VENCE `/usr/lib/udev/rules.d/` no udev.
#
# O ESPELHO DO PACOTE CONTINUA FECHADO, e é de propósito: o
# `/usr/share/hefesto-dualsense4unix/udev-rules/` não é lido pelo udev — é a
# FONTE que o `install-host-udev.sh` consome depois, quando o broker entra.
#
# UM DONO SÓ PARA A TRANSFORMAÇÃO. O `install_udev.sh --no-fechar-o-no` tinha
# o `sed` escrito inline; com seis chamadores, seis cópias do `sed` seriam seis
# oportunidades de uma delas envelhecer sozinha — que é o defeito que o
# `novo-layout/` custou a esta casa.
set -euo pipefail

ORIGEM="${1:-}"
DESTINO="${2:-}"

if [[ -z "${ORIGEM}" || -z "${DESTINO}" ]]; then
    echo "uso: bash scripts/regra_do_no_aberta.sh ORIGEM DESTINO" >&2
    exit 2
fi

if [[ ! -f "${ORIGEM}" ]]; then
    echo "ERRO: origem ausente: ${ORIGEM}" >&2
    exit 1
fi

_tmp="$(mktemp)"
trap 'rm -f "${_tmp}"' EXIT

# Reabre SÓ as duas linhas do DualSense standard (0ce6). As do Edge (0df2) e a
# do vpad nunca fecharam — ver o cabeçalho do asset.
sed -e 's/MODE="0600", OWNER="root", GROUP="root", TAG-="uaccess"/MODE="0660", TAG+="uaccess"/' \
    "${ORIGEM}" > "${_tmp}"

# AS DUAS GUARDAS, e nenhuma é decorativa.
#
# O grep IGNORA comentário: o cabeçalho do asset CITA a forma fechada ao
# explicar como reverter, e uma guarda que lesse a prosa reprovaria sempre.
_regras() { grep -v '^[[:space:]]*#' "$1" || true; }

# 1. Sobrou alguma linha FECHADA? Então o `sed` não alcançou o asset de hoje.
if _regras "${_tmp}" | grep -q 'TAG-="uaccess"'; then
    echo "ERRO: não foi possível reabrir todas as linhas de ${ORIGEM}." >&2
    echo "      nada foi escrito em ${DESTINO}." >&2
    exit 1
fi

# 2. O resultado tem as DUAS linhas 0ce6 com `uaccess`? Um asset renomeado ou
#    um `sed` que casou zero vezes passaria pela guarda 1 calado — e o que sai
#    seria uma regra que não dá acesso a ninguém, que é o mesmo defeito com
#    outra roupa.
_abertas="$(_regras "${_tmp}" | grep -ci '0ce6.*TAG+="uaccess"' || true)"
if [[ "${_abertas}" -ne 2 ]]; then
    echo "ERRO: a variante aberta de ${ORIGEM} tem ${_abertas} linha(s) 0ce6 com uaccess; esperadas 2." >&2
    echo "      nada foi escrito em ${DESTINO}." >&2
    exit 1
fi

install -Dm644 "${_tmp}" "${DESTINO}"
