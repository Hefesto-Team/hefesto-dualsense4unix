#!/usr/bin/env bash
# Responde UMA pergunta: QUAIS controles entraram em modo háptica enquanto o
# jogo rodava — e por quanto tempo cada um ficou.
#
# Nasceu em 20/09/2026, depois de ela corrigir a premissa de uma sprint inteira:
# "na real o certo não era somente o controle do player 1 receber a vibração?
#  pq é um jogo de um player e o erro era que o player 3 tava recebendo a
#  vibração de forma espelhada".
#
# O instrumento anterior mediu se A CORRENTE fechava. Este mede QUEM RECEBE, e
# é a pergunta que a queixa de uso faz.
#
# Só lê o journal do daemon. Não toca em nada.
#
#   bash scripts/quem_vibra_no_jogo.sh [desde]      # padrão: "today"
set -uo pipefail
export LC_ALL=C
DESDE="${1:-today}"

J=$(journalctl --user -u hefesto-dualsense4unix.service --since "$DESDE" --no-pager 2>/dev/null)
if [ -z "$J" ]; then
  echo "SEM JOURNAL do daemon desde «$DESDE» — não sei dizer quem vibrou."
  echo "Ausência é resposta: não afirmo nada."
  exit 2
fi

echo "── quem ENTROU em modo háptica (som_radio_ponte_de_pe arranjo=0x32) ──"
printf '%s\n' "$J" | grep "som_radio_ponte_de_pe" | grep "0x32" \
  | grep -oE "uniq=[0-9a-f:]+" | sort | uniq -c | sort -rn \
  | sed 's/^/  /' || echo "  (nenhum)"

echo
echo "── quem TENTOU e foi recusado (haptica_sem_fonte) ──"
printf '%s\n' "$J" | grep "haptica_sem_fonte" \
  | grep -oE "uniq=[0-9a-f:]+" | sort | uniq -c | sort -rn \
  | sed 's/^/  /' || echo "  (nenhum)"

echo
echo "── quem ficou no SOM (arranjo=0x35), que é o certo para quem não joga ──"
printf '%s\n' "$J" | grep "som_radio_ponte_de_pe" | grep "0x35" \
  | grep -oE "uniq=[0-9a-f:]+" | sort | uniq -c | sort -rn \
  | sed 's/^/  /' || echo "  (nenhum)"

echo
echo "════════════════════════════════════════════════════════════════"
n=$(printf '%s\n' "$J" | grep "som_radio_ponte_de_pe" | grep -c "0x32" || true)
q=$(printf '%s\n' "$J" | grep "som_radio_ponte_de_pe" | grep "0x32" \
    | grep -oE "uniq=[0-9a-f:]+" | sort -u | wc -l)
echo "  entradas em háptica pelo rádio: $n"
echo "  controles DO RÁDIO que entraram em háptica: $q"
echo "  (o controle do CABO não passa por aqui — ele usa o endpoint REAL)"
# 28/09/2026 (O-BASICO-MEDIDO-01): as frases de veredito que moravam aqui
# liam a mesa de 20/09 (um jogo de um jogador, quem joga no cabo) e diziam
# «certo» ou «defeito» só pela contagem. Numa mesa de quatro no rádio, ou num
# jogo de quatro jogadores, a mesma contagem é o certo. O script fica com as
# contagens; quem casa a contagem com o jogo e os jogadores é o
# `o_basico.py saidas`.
