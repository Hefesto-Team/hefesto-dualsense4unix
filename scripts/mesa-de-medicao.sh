#!/usr/bin/env bash
set -uo pipefail
_ajuda() {
  cat <<'AJUDA'
mesa-de-medicao.sh — sobe A MESA DE MEDIÇÃO e a abre na tela do usuário.

Uso:
  scripts/mesa-de-medicao.sh                 liga o daemon se preciso, sobe e abre na tela do usuário
  scripts/mesa-de-medicao.sh --sem-abrir     sobe e só imprime o endereço (é o que a régua usa)
  scripts/mesa-de-medicao.sh --sem-daemon    não liga o daemon, mesmo parado
  scripts/mesa-de-medicao.sh --porta 8765    escolhe a porta (0 = a primeira livre)
  scripts/mesa-de-medicao.sh --censo         o retrato dos testes, sem servir nada
AJUDA
}

RAIZ="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
ABRIR=1
PORTA=0
CENSO=0
LIGAR_DAEMON=1
UNIT="hefesto-dualsense4unix.service"

while [ $# -gt 0 ]; do
  case "$1" in
    --sem-abrir) ABRIR=0; LIGAR_DAEMON=0 ;;
    --sem-daemon) LIGAR_DAEMON=0 ;;
    --censo)     CENSO=1 ;;
    --porta)     PORTA="${2:-0}"; shift ;;
    -h|--help)   _ajuda; exit 0 ;;
    *) printf 'mesa-de-medicao.sh: não conheço "%s". Use --help.\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

escolher_python() {
  local candidatos=(
    "${PY:-}"
    "${HEFESTO_PY:-}"
    "$RAIZ/.venv/bin/python"
    "$(command -v python3 || true)"
  )
  local py
  for py in "${candidatos[@]}"; do
    [ -x "$py" ] || continue
    if PYTHONPATH="$RAIZ/src" "$py" -c 'import hefesto_dualsense4unix' >/dev/null 2>&1; then
      printf '%s\n' "$py"
      return 0
    fi
  done
  return 1
}

PY="$(escolher_python)" || {
  echo "mesa-de-medicao.sh: nenhum python desta máquina importa o pacote desta árvore." >&2
  echo "  tentei: o PY, o HEFESTO_PY, $RAIZ/.venv/bin/python e o python3 do PATH." >&2
  exit 1
}
export PYTHONPATH="$RAIZ/src${PYTHONPATH:+:$PYTHONPATH}"

RESOLVIDO="$("$PY" -c 'import hefesto_dualsense4unix as h; print(h.__file__)')"
case "$RESOLVIDO" in
  "$RAIZ"/*) : ;;
  *) echo "mesa-de-medicao.sh: o python resolve para OUTRA árvore — $RESOLVIDO" >&2
     echo "  medir o src de outra árvore é a armadilha que já fez trabalho ENTREGUE" >&2
     echo "  ser diagnosticado como faltando. Pare aqui." >&2
     exit 1 ;;
esac

printf 'python:  %s\n' "$PY"
printf 'pacote:  %s\n' "$RESOLVIDO"

if [ "$CENSO" = 1 ]; then
  exec "$PY" "$RAIZ/scripts/mesa_de_medicao.py" --censo
fi

if [ "$LIGAR_DAEMON" = 1 ] && command -v systemctl >/dev/null 2>&1; then
  ESTADO="$(systemctl --user is-active "$UNIT" 2>/dev/null || true)"
  if [ "$ESTADO" = "active" ]; then
    printf 'daemon:  já de pé\n'
  elif systemctl --user cat "$UNIT" >/dev/null 2>&1; then
    printf 'daemon:  %s — ligando (%s)\n' "${ESTADO:-desconhecido}" "$UNIT"
    if systemctl --user start "$UNIT" 2>/dev/null; then
      printf 'daemon:  %s\n' "$(systemctl --user is-active "$UNIT" 2>/dev/null || echo '?')"
    else
      printf 'daemon:  NÃO subiu. A página vai ler o kernel e dizer isso.\n' >&2
    fi
  else
    printf 'daemon:  a unit %s não existe nesta máquina — o produto não está instalado\n' "$UNIT" >&2
  fi
fi

"$PY" -c "
import sys; sys.path.insert(0, '$RAIZ/scripts')
import mesa_de_medicao as m
mesa = m.quem_esta_na_mesa()
print('na mesa:', mesa['daemon'])
for p in ('P1','P2','P3','P4'):
    v = mesa['postos'][p]
    print(f\"  {p}  {v['nome']:24} {v['transporte'] or '-':8} {v['modelo'] or '-'}\")
"

TUBO="$(mktemp -d)/endereco"
mkfifo "$TUBO"
"$PY" "$RAIZ/scripts/mesa_de_medicao.py" --servir --porta "$PORTA" > "$TUBO" &
SERVIDOR=$!
trap 'kill "$SERVIDOR" 2>/dev/null || true' EXIT INT TERM

read -r ENDERECO < "$TUBO"
rm -rf "$(dirname "$TUBO")"
printf 'a mesa está em: %s\n' "$ENDERECO"

if [ "$ABRIR" = 1 ]; then
  (xdg-open "$ENDERECO" >/dev/null 2>&1 || true) &
  printf 'abri na tela dela. Ctrl-C para fechar o servidor.\n'
else
  printf 'sem abrir (--sem-abrir). Ctrl-C para fechar o servidor.\n'
fi

wait "$SERVIDOR"
