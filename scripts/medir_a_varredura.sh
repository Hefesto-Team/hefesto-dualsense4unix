#!/usr/bin/env bash
# medir_a_varredura.sh — BUSCA-DO-RADIO-02 (19/09/2026)
#
# A PERGUNTA: quando a tela de Bluetooth do COSMIC entra em modo de busca, ela
# varre UM adaptador ou TODOS?
#
# POR QUE ELA DECIDE TUDO. A ideia dela é a POSSE do rádio: os dongles são dos
# controles, o adaptador interno fica para o resto — e é lá que a tela varre à
# vontade, sem tocar em controle nenhum. Isso só funciona se ela varrer UM. Se
# varrer os três, a RESERVA-DO-RADIO-01 morre e não se escreve uma linha dela.
#
# O QUE JÁ ESTÁ MEDIDO, e não precisa remedir:
#   · a varredura é POR ADAPTADOR e não vaza — `scan on` no hci0 deixa hci1 e
#     hci2 em `false`;
#   · um terceiro NÃO consegue parar a busca de outro — o BlueZ conta discovery
#     por CLIENTE, e `StopDiscovery` de fora devolve «No discovery started».
#     (Foi isto que matou o caminho 2 da BUSCA-DO-RADIO-01.)
#
# O QUE NÃO DÁ PARA MEDIR SEM ELA, e a razão não é preguiça: os dois binários
# do COSMIC estão `stripped` (sem símbolo, e o `.debug` não está instalado), o
# `bluetoothd` não loga descoberta no nível atual, e a tela precisa estar
# VISÍVEL — uma janela parqueada fora do monitor ficou 185 s aberta sem iniciar
# busca nenhuma, e não há como saber se é porque a página não varre sozinha ou
# porque um app Wayland fora da tela é suspenso.
#
# SÃO DUAS CORRIDAS, e o achado que mais muda a conclusão está nisso: a tela de
# Configurações usa `bluez-zbus`, o applet da dock usa a crate `bluer`. São
# DOIS programas com implementações separadas, e o resultado de um NÃO vale
# para o outro.
#
# Este script só LÊ propriedades. Não pede sudo, não liga busca, não muda nada.
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

# O VEREDITO SAI AQUI, e não na cabeça de quem leu. Uma régua que despeja
# tabela e deixa a interpretação para depois é uma régua que não mediu nada:
# esta casa já pagou por isso mais de uma vez.
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
        # A MORDIDA ACHOU ESTE CASO, 19/09/2026: numa máquina com UM adaptador
        # só, "varreu um" é 100%% dos adaptadores — e não há PARA ONDE reservar.
        # O conselho anterior dizia «a reserva resolve» e estava errado; é o
        # mesmo defeito que `mesa_de_radio.py:44-52` existe para recusar, o de
        # presumir a bancada de quem escreveu.
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
