#!/usr/bin/env bash
set -uo pipefail
_ajuda() {
  cat <<'AJUDA'
bancada.sh — o semáforo do recurso FÍSICO: 1 daemon, 1 broker de hidraw,
1 controle na mesa, 3 adaptadores de rádio. Isolar árvore de git não divide
aparelho, e é por isso que o worktree não basta.

  Se a liberação depende de um `finally` do detentor, o desenho está errado.
AJUDA
}

ARQ="${HEFESTO_BANCADA_ARQ:-${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hefesto-bancada.json}"
AGORA="${HEFESTO_BANCADA_AGORA:-$(date +%s)}"

_json() {
  sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\{0,1\}\([^\",}]*\)\"\{0,1\}.*/\1/p" "$ARQ" \
    | head -1
}

_hhmm() { date -d "@$1" '+%d/%m %H:%M' 2>/dev/null || echo "$1"; }

_avaliar() {
  [ -r "$ARQ" ] || { echo "LIVRE — ninguém reservou a bancada."; return 1; }

  local pid quem motivo desde expira
  pid="$(_json pid)"; quem="$(_json quem)"; motivo="$(_json motivo)"
  desde="$(_json desde)"; expira="$(_json expira_em)"

  if [ -z "${pid:-}" ] || [ -z "${expira:-}" ]; then
    echo "LIVRE — ${ARQ} existe mas está ilegível (sem pid ou sem expira_em); trate como livre."
    return 1
  fi

  if ! kill -0 "$pid" 2>/dev/null; then
    echo "LIVRE — quem reservou (PID ${pid}, ${quem}) morreu sem liberar; o kernel respondeu por ele."
    return 1
  fi

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
  -h|--help) _ajuda ;;
  *) echo "ERRO: comando desconhecido '${1}'. Veja $0 --help" >&2; exit 2 ;;
esac
