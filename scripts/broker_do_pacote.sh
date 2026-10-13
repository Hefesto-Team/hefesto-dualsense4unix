#!/usr/bin/env bash
# broker_do_pacote.sh — escreve as units do broker root para um PACOTE de distro.
#
# Uso: bash scripts/broker_do_pacote.sh DIRETORIO_DAS_UNITS CAMINHO_DO_BINARIO
#
# O broker atende a conta que está na frente do computador (pergunta ao logind a
# cada pedido), então a unit não carrega uid nem grupo e nada nela depende da
# máquina que instala (O-BROKER-SERVE-QUEM-ESTA-NA-FRENTE-01). Por isso os
# quatro pacotes (.deb, Arch, Fedora, Nix) levam o broker como unit de sistema
# e a regra do nó FECHADA, como o install nativo. Sobra uma troca, e é do
# pacote, não da máquina: onde o binário mora.
#
# UM DONO SÓ PARA A TRANSFORMAÇÃO, como o `regra_do_no_aberta.sh` foi: quatro
# receitas com o `sed` escrito dentro seriam quatro cópias para envelhecer
# sozinhas. A mesma troca do install nativo mora em `_render_broker_units`
# (`scripts/lib/camada_de_maquina.sh`); um teste compara as duas saídas.
#
# Escreve `hefesto-hidraw-broker.service` e `.socket` em DIRETORIO_DAS_UNITS.
# Devolve 1, sem deixar unit utilizável, se sobrar placeholder ou se o
# ExecStart não apontar para o binário pedido.
set -euo pipefail

DESTINO="${1:-}"
BINARIO="${2:-}"

if [[ -z "${DESTINO}" || -z "${BINARIO}" ]]; then
    echo "uso: bash scripts/broker_do_pacote.sh DIRETORIO_DAS_UNITS CAMINHO_DO_BINARIO" >&2
    exit 2
fi
if [[ "${BINARIO}" != /* ]]; then
    echo "ERRO: o binário tem de ser um caminho absoluto: ${BINARIO}" >&2
    exit 2
fi

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICO_SRC="${RAIZ}/assets/systemd/hefesto-hidraw-broker.service"
SOCKET_SRC="${RAIZ}/assets/systemd/hefesto-hidraw-broker.socket"
BINARIO_DO_INSTALL="/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"

for _f in "${SERVICO_SRC}" "${SOCKET_SRC}"; do
    [[ -f "${_f}" ]] || { echo "ERRO: asset ausente: ${_f}" >&2; exit 1; }
done

mkdir -p "${DESTINO}"
_s="${DESTINO}/hefesto-hidraw-broker.service"
_k="${DESTINO}/hefesto-hidraw-broker.socket"

# `|` como separador: o caminho tem barras. O binário não tem `|` nem `&`.
sed -e "s/__NO_NASCE_FECHADO__/1/" \
    -e "s|${BINARIO_DO_INSTALL}|${BINARIO}|g" \
    "${SERVICO_SRC}" > "${_s}"
cat "${SOCKET_SRC}" > "${_k}"

if grep -q '__[A-Z_]*__' "${_s}" "${_k}"; then
    rm -f "${_s}" "${_k}"
    echo "ERRO: a unit do broker ficou com placeholder sobrando" >&2
    exit 1
fi
if grep -q "${BINARIO_DO_INSTALL}" "${_s}" && [[ "${BINARIO}" != "${BINARIO_DO_INSTALL}" ]]; then
    rm -f "${_s}" "${_k}"
    echo "ERRO: a unit do broker ainda aponta para o caminho do install nativo" >&2
    exit 1
fi
if ! grep -q "^ExecStart=${BINARIO}\$" "${_s}"; then
    rm -f "${_s}" "${_k}"
    echo "ERRO: o ExecStart da unit do broker não aponta para ${BINARIO}" >&2
    exit 1
fi
