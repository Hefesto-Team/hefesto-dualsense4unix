#!/usr/bin/env bash
set -euo pipefail

SEGUNDOS="${1:-40}"
SAIDA="${2:-/tmp/varredura-$(date +%H%M%S).txt}"

_adaptadores() {
    busctl --system tree org.bluez 2>/dev/null \
        | grep -oE '/org/bluez/hci[0-9]+$' | sed 's|.*/||' | sort -u
}

_discovering() {
    busctl --system get-property org.bluez "/org/bluez/$1" \
        org.bluez.Adapter1 Discovering 2>/dev/null | awk '{print $2}'
}

mapfile -t ADPS < <(_adaptadores)
if [[ "${#ADPS[@]}" -eq 0 ]]; then
    printf 'nenhum adaptador Bluetooth nesta máquina — não há o que medir.\n' >&2
    exit 1
fi

printf '\n'
printf '  MEDINDO A VARREDURA — %s segundos, %s adaptador(es)\n' "${SEGUNDOS}" "${#ADPS[@]}"
printf '  saída: %s\n\n' "${SAIDA}"
printf '  AGORA, com o laço rodando:\n'
printf '    1. abra a tela de Bluetooth (Configurações -> Bluetooth)\n'
printf '    2. deixe aberta uns 15 s\n'
printf '    3. feche\n'
printf '  Depois repita ESTA MESMA corrida abrindo o popover do ícone de\n'
printf '  Bluetooth da barra, em vez da janela — são dois programas diferentes.\n\n'

: > "${SAIDA}"
for _ in $(seq 1 "${SEGUNDOS}"); do
    linha="$(date +%T)"
    for h in "${ADPS[@]}"; do
        linha="${linha}  ${h}=$(_discovering "${h}")"
    done
    printf '%s\n' "${linha}" | tee -a "${SAIDA}"
    sleep 1
done

printf '\n  ── O QUE ISTO DIZ ──────────────────────────────────────────\n'
quantos_varreram=0
quais=""
for h in "${ADPS[@]}"; do
    if grep -qF "${h}=true" "${SAIDA}"; then
        quantos_varreram=$((quantos_varreram + 1))
        quais="${quais} ${h}"
    fi
done

case "${quantos_varreram}" in
    0)
        printf '  NENHUM adaptador varreu durante a corrida.\n'
        printf '  A tela não chegou a abrir, ou ela só varre quando se pede\n'
        printf '  («Adicionar aparelho»). Repita clicando no botão de procurar.\n'
        ;;
    1)
        printf '  VARREU UM SÓ:%s\n\n' "${quais}"
        if [[ "${#ADPS[@]}" -eq 1 ]]; then
            printf '  MAS ESTA MÁQUINA TEM UM ADAPTADOR SÓ — não há para onde\n'
            printf '  reservar, e a varredura alcança todo controle que houver.\n'
            printf '  Aqui a RESERVA-DO-RADIO-01 não se aplica: o caminho é parear\n'
            printf '  pelo próprio Hefesto (PONTE-SEM-CHAMADOR-01), para que esta\n'
            printf '  tela nunca precise abrir.\n'
        else
            printf '  A RESERVA RESOLVE. Pôr os controles nos OUTROS adaptadores os\n'
            printf '  tira do alcance da tela de Bluetooth — a RESERVA-DO-RADIO-01\n'
            printf '  deixa de estar travada por esta medição.\n'
        fi
        ;;
    "${#ADPS[@]}")
        printf '  VARREU TODOS:%s\n\n' "${quais}"
        printf '  A RESERVA NÃO RESOLVE, e a RESERVA-DO-RADIO-01 morre aqui.\n'
        printf '  O controle sofre em qualquer adaptador, e o caminho passa a ser\n'
        printf '  outro: parear pelo próprio Hefesto, para que esta tela nunca\n'
        printf '  precise abrir (PONTE-SEM-CHAMADOR-01).\n'
        ;;
    *)
        printf '  VARREU %s DE %s:%s\n\n' "${quantos_varreram}" "${#ADPS[@]}" "${quais}"
        printf '  Há uma REGRA de escolha, e ela é o achado. Prováveis: só os\n'
        printf '  `Powered`, ou só os sem link ativo. Meça de novo com um\n'
        printf '  controle conectado e depois sem — a diferença nomeia a regra.\n'
        ;;
esac
printf '  ────────────────────────────────────────────────────────────\n\n'
