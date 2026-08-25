#!/usr/bin/env bash
# bancada.sh — o semáforo do recurso FÍSICO: 1 daemon, 1 broker de hidraw,
# 1 controle na mesa, 3 adaptadores de rádio. Isolar árvore de git não divide
# aparelho, e é por isso que o worktree não basta.
#
# O GESTO QUE ELE TORNA SEGURO, e são as palavras dela:
#   "vamos fazer a medição do BT, enquanto isso manda agentes pra execução das
#    demais sprints"
# Quinze das vinte e duas sprints precisam do daemon vivo, onze abrem hidraw e
# duas colidem de frente com a medição de rádio. Sem semáforo, um agente para o
# daemon debaixo da mão dela no meio da medição -- e o pior caso não é o agente
# falhar: é ele MEDIR, e publicar um número colhido enquanto o aparelho mudava.
#
# DUAS PROVAS DE VIDA INDEPENDENTES, e nenhuma exige que alguém lembre de
# liberar:
#   1. o PID do detentor está vivo?   -- quem responde é o KERNEL;
#   2. já passou de `expira_em`?      -- quem responde é o RELÓGIO.
# Basta uma delas dizer "não" para a bancada estar LIVRE.
#
# POR QUE AS DUAS, e não só o PID: um processo pode virar zumbi e o PID
# continuar existindo. E por que não só o relógio: um teto de quatro horas
# deixaria a bancada travada quatro horas depois de a sessão dela morrer.
#
# O TETO NÃO É ZELO -- é a lição do `btmgmt` sem adaptador, que travava o
# `install.sh` PARA SEMPRE em quem não tem Bluetooth. O que não volta sozinho
# trava a casa, e só teto de tempo resolveu. A mesma regra vale aqui:
#
#   Se a liberação depende de um `finally` do detentor, o desenho está errado.
#
# O ESTADO NÃO É VERSIONADO, e é de propósito: ele mora em
# ${XDG_RUNTIME_DIR}/hefesto-bancada.json, que o kernel limpa no fim da sessão.
# Estado transitório dentro do git vira commit de carona -- o `painel.html`
# entrou de carona em 16 de 22 commits de 23/08 exatamente assim.
#
# Uso:
#   scripts/bancada.sh reservar "medição de BT" [--horas 4]
#   scripts/bancada.sh status      uma linha, e é a que o despachante imprime
#   scripts/bancada.sh exigir      rc=1 com motivo e hora -> quem chamou NÃO passa
#   scripts/bancada.sh liberar
#
# QUEM CHAMA `exigir`: todo caminho que pare o daemon, escreva no hidraw ou
# chame `systemctl`. rc=1 significa ESPERAR e DIZER que está esperando -- nunca
# contornar por outro caminho, que é como se inventa medição falsa.
set -uo pipefail

# As três variáveis de dublê. Elas existem para que o PORTÃO possa exercitar as
# duas provas de vida uma de cada vez, sem esperar quatro horas e sem matar
# processo de verdade. A cicatriz que as obriga está no cabeçalho do portão:
# as duas primeiras medições do `flock` foram FALSAS porque o dublê não
# declarava o próprio PID.
ARQ="${HEFESTO_BANCADA_ARQ:-${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hefesto-bancada.json}"
AGORA="${HEFESTO_BANCADA_AGORA:-$(date +%s)}"

_json() {  # _json <chave> -- lê uma chave do arquivo, sem depender de jq
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\{0,1\}\([^\",}]*\)\"\{0,1\}.*/\1/p" "$ARQ" \
    | head -1
}

_hhmm() { date -d "@$1" '+%d/%m %H:%M' 2>/dev/null || echo "$1"; }

# Devolve 0 (bancada OCUPADA) ou 1 (LIVRE), e imprime a linha de estado.
_avaliar() {
  [ -r "$ARQ" ] || { echo "LIVRE — ninguém reservou a bancada."; return 1; }

  local pid quem motivo desde expira
  pid="$(_json pid)"; quem="$(_json quem)"; motivo="$(_json motivo)"
  desde="$(_json desde)"; expira="$(_json expira_em)"

  if [ -z "${pid:-}" ] || [ -z "${expira:-}" ]; then
    echo "LIVRE — ${ARQ} existe mas está ilegível (sem pid ou sem expira_em); trate como livre."
    return 1
  fi

  # PROVA DE VIDA 1 — o kernel. `kill -0` não envia sinal nenhum: só pergunta
  # se o processo existe. Se o detentor morreu (Wi-Fi caiu, sessão fechou,
  # `kill -9`), a bancada está livre na PRÓXIMA LEITURA, sem ninguém liberar.
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "LIVRE — quem reservou (PID ${pid}, ${quem}) morreu sem liberar; o kernel respondeu por ele."
    return 1
  fi

  # PROVA DE VIDA 2 — o relógio. Um processo zumbi mantém o PID existindo, e o
  # teto responde por cima. É a lição do `btmgmt` sem adaptador.
  if [ "$AGORA" -ge "$expira" ]; then
    echo "LIVRE — a reserva de ${quem} venceu em $(_hhmm "$expira") (o teto de tempo respondeu; o PID ${pid} ainda vive)."
    return 1
  fi

  echo "OCUPADA por ${quem} (PID ${pid}) desde $(_hhmm "$desde") até $(_hhmm "$expira") — ${motivo}"
  return 0
}

_reservar() {
  local motivo="${1:?falta o motivo da reserva -- 'medição de BT', por exemplo}"
  shift || true
  local horas="1"
  while [ $# -gt 0 ]; do
    case "$1" in
      --horas) horas="${2:?--horas precisa de um número}"; shift 2 ;;
      *) echo "ERRO: opção desconhecida '$1' em reservar" >&2; exit 2 ;;
    esac
  done

  if _avaliar >/dev/null; then
    echo "RECUSADO — a bancada já está reservada:" >&2
    _avaliar >&2
    exit 1
  fi

  # O PID GRAVADO É O DO SHELL QUE CHAMOU, nunca o deste script: `$$` morre no
  # próximo instante e a prova de vida 1 diria "livre" sempre. `HEFESTO_BANCADA_PID`
  # existe para o dublê do portão declarar o próprio PID -- que é justamente o
  # que faltava nas duas medições falsas do `flock`.
  local pid="${HEFESTO_BANCADA_PID:-$PPID}"
  local expira
  expira="$(awk -v a="$AGORA" -v h="$horas" 'BEGIN{printf "%d", a + h*3600}')"

  mkdir -p "$(dirname "$ARQ")"
  cat > "$ARQ" <<JSON
{
  "pid": ${pid},
  "quem": "$(id -un)",
  "motivo": "${motivo//\"/\'}",
  "desde": ${AGORA},
  "expira_em": ${expira}
}
JSON
  echo "RESERVADA por $(id -un) (PID ${pid}) até $(_hhmm "$expira") — ${motivo}"
  echo "O teto é a rede, não o 'liberar': se você morrer, a bancada volta sozinha."
}

case "${1:-status}" in
  reservar) shift; _reservar "$@" ;;
  status)   _avaliar >/dev/null; _avaliar; exit 0 ;;
  exigir)
    if _avaliar >/dev/null; then
      echo "BANCADA OCUPADA — você NÃO passa daqui." >&2
      _avaliar >&2
      echo "Espere, e DIGA na entrega que está esperando. Não contorne por outro" >&2
      echo "caminho: é assim que se inventa medição falsa." >&2
      exit 1
    fi
    _avaliar
    exit 0 ;;
  liberar)
    if [ -e "$ARQ" ]; then rm -f "$ARQ"; echo "LIBERADA."; else echo "já estava livre."; fi ;;
  -h|--help) sed -n '2,45p' "$0" | sed 's/^# \?//' ;;
  *) echo "ERRO: comando desconhecido '${1}'. Veja $0 --help" >&2; exit 2 ;;
esac
