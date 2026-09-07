#!/usr/bin/env bash
# validar.sh — sobe A MESA DE MEDIÇÃO e a abre na tela dela.
#
# A encomenda é dela, 06/09/2026:
#
#     "a ideia é termos uma página pra medirmos o que falta no specs. (…) eu
#     registro lá que tal controle ficou x com o teste y clico em avançar, o
#     novo teste inicia eu relato o estado dos 4 controles"
#
# E a razão de a página existir, que é a que decide tudo: a sessão de quem estava na bancada
# acabava e levava embora não só o resultado como o MODO DE CHEGAR NELE. A frase
# dela, palavra por palavra, está em
# docs/process/agentes/2026-09-06/A-VALIDACAO-DOS-QUATRO-01-entrada/ESPEC-A-VALIDACAO.md
# — aqui ela é referida e não repetida, porque nomeia o assistente, e nome de
# assistente não entra em arquivo versionado fora de docs/process/.
#
# A JANELA É DELA E PARA ELA. Aqui **não** vale `--oculta`: esta é a única
# janela desta casa que nasce de propósito na tela dela, porque é ela que vai
# olhar os quatro controles e clicar. As réguas automáticas — o Playwright que
# prova esta página — essas sim rodam headless, e é o `--sem-abrir` que as serve.
#
# ELE LIGA O DAEMON SE ELE ESTIVER PARADO — e NUNCA o reinicia. Pedido dela,
# 07/09/2026: *"quando rodar o validar ele tem que acionar isso
# automaticamente"*, depois de atravessar meia bancada com o daemon morto. Sem
# daemon a página lê o kernel e o kernel devolve a LÂMPADA da sessão passada:
# ela plugou o controle que o roteiro chama de P1 e a página o pôs no P3.
#
# A DIFERENÇA ENTRE `start` E `restart` É A SESSÃO DELA. `start` num serviço já
# ativo não faz nada; `restart` derruba o daemon vivo, com os controles na mão
# dela, no meio de uma medição. Por isso aqui só se pergunta `is-active` e só
# se chama `start` — e se ele já estiver de pé, o script não toca em nada.
#
# A RÉGUA NÃO LIGA NADA: com `--sem-abrir` (que é o que o Playwright usa) o
# daemon não é acionado. Uma suíte que sobe serviço na máquina dela é uma
# suíte que mexe na mesa dela sem ela pedir.
#
# Uso:
#   ./validar.sh                 liga o daemon se preciso, sobe e abre na tela dela
#   ./validar.sh --sem-abrir     sobe e só imprime o endereço (é o que a régua usa)
#   ./validar.sh --sem-daemon    não liga o daemon, mesmo parado
#   ./validar.sh --porta 8765    escolhe a porta (0 = a primeira livre)
#   ./validar.sh --censo         o retrato dos testes, sem servir nada
set -uo pipefail

RAIZ="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
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
    -h|--help)   sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf 'validar.sh: não conheço "%s". Use --help.\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

# ---------------------------------------------------------------------------
# O INTERPRETADOR SE DECLARA, e a razão é a cicatriz do `portoes.sh`: numa
# árvore de voo, escolher o python pela POSIÇÃO imprimia a venv de OUTRA cópia
# do repositório e produzia quatro vermelhos falsos sobre código são. Aqui a
# regra é de CAPACIDADE: o primeiro python que importa o pacote DESTA árvore.
# ---------------------------------------------------------------------------
escolher_python() {
  local candidatos=(
    "$RAIZ/.venv/bin/python"
    "/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix/.venv/bin/python"
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
  echo "validar.sh: nenhum python desta máquina importa o pacote desta árvore." >&2
  echo "  tentei: $RAIZ/.venv/bin/python, a venv da árvore dela, e o python3 do PATH." >&2
  exit 1
}
export PYTHONPATH="$RAIZ/src${PYTHONPATH:+:$PYTHONPATH}"

RESOLVIDO="$("$PY" -c 'import hefesto_dualsense4unix as h; print(h.__file__)')"
case "$RESOLVIDO" in
  "$RAIZ"/*) : ;;
  *) echo "validar.sh: o python resolve para OUTRA árvore — $RESOLVIDO" >&2
     echo "  medir o src de outra árvore é a armadilha que já fez trabalho ENTREGUE" >&2
     echo "  ser diagnosticado como faltando. Pare aqui." >&2
     exit 1 ;;
esac

printf 'python:  %s\n' "$PY"
printf 'pacote:  %s\n' "$RESOLVIDO"

if [ "$CENSO" = 1 ]; then
  exec "$PY" "$RAIZ/scripts/mesa_de_medicao.py" --censo
fi

# ---------------------------------------------------------------------------
# O DAEMON — `start` se estiver parado, e nada se estiver de pé. Ver o
# cabeçalho: `restart` derrubaria o daemon vivo com os controles na mão dela.
# ---------------------------------------------------------------------------
if [ "$LIGAR_DAEMON" = 1 ] && command -v systemctl >/dev/null 2>&1; then
  ESTADO="$(systemctl --user is-active "$UNIT" 2>/dev/null || true)"
  if [ "$ESTADO" = "active" ]; then
    printf 'daemon:  já de pé\n'
  elif systemctl --user cat "$UNIT" >/dev/null 2>&1; then
    printf 'daemon:  %s — ligando (%s)\n' "${ESTADO:-desconhecido}" "$UNIT"
    if systemctl --user start "$UNIT" 2>/dev/null; then
      # ELE NÃO NASCE PRONTO: o socket aparece depois do processo. Sem esta
      # espera a página sobe, pergunta cedo demais, cai no kernel e mostra a
      # LÂMPADA velha — que é exatamente o defeito que ligar o daemon cura.
      for _ in $(seq 1 40); do
        [ "$(systemctl --user is-active "$UNIT" 2>/dev/null || true)" = "active" ] && break
        sleep 0.25
      done
      printf 'daemon:  %s\n' "$(systemctl --user is-active "$UNIT" 2>/dev/null || echo '?')"
    else
      printf 'daemon:  NÃO subiu. A página vai ler o kernel e dizer isso.\n' >&2
    fi
  else
    # A MENSAGEM NÃO NOMEIA O INSTALADOR de propósito: há régua que proíbe o
    # nome dele neste arquivo, e a razão é boa — ele reescreve os lançadores
    # dela e a unit, e um lançador que o CITA é um passo de virar um que o
    # chama.
    printf 'daemon:  a unit %s não existe nesta máquina — o produto não está instalado\n' "$UNIT" >&2
  fi
fi

# ---------------------------------------------------------------------------
# QUEM ESTÁ NA MESA — antes de servir, para quem sobe saber com o que conta.
# ---------------------------------------------------------------------------
"$PY" -c "
import sys; sys.path.insert(0, '$RAIZ/scripts')
import mesa_de_medicao as m
mesa = m.quem_esta_na_mesa()
print('na mesa:', mesa['daemon'])
for p in ('P1','P2','P3','P4'):
    v = mesa['postos'][p]
    print(f\"  {p}  {v['nome']:24} {v['transporte'] or '-':8} {v['modelo'] or '-'}\")
"

# ---------------------------------------------------------------------------
# O SERVIDOR. Biblioteca padrão, `127.0.0.1`, sem uma dependência nova — a
# dívida do `playwright`, que não está no `pyproject.toml` e deixa toda árvore
# de agente com dois portões vermelhos, já ensinou o preço de acrescentar uma.
# ---------------------------------------------------------------------------
TUBO="$(mktemp -d)/endereco"
mkfifo "$TUBO"
"$PY" "$RAIZ/scripts/mesa_de_medicao.py" --servir --porta "$PORTA" > "$TUBO" &
SERVIDOR=$!
# O PID é conferido, e é por ele que se mata. `pkill -f` já derrubou o
# compositor dela — nunca por padrão.
trap 'kill "$SERVIDOR" 2>/dev/null || true' EXIT INT TERM

read -r ENDERECO < "$TUBO"
rm -rf "$(dirname "$TUBO")"
printf 'a mesa está em: %s\n' "$ENDERECO"

if [ "$ABRIR" = 1 ]; then
  # A tela é DELA. Nada de `--oculta` aqui, e nada de escolher navegador por
  # conta própria: `xdg-open` respeita o padrão que ela configurou.
  (xdg-open "$ENDERECO" >/dev/null 2>&1 || true) &
  printf 'abri na tela dela. Ctrl-C para fechar o servidor.\n'
else
  printf 'sem abrir (--sem-abrir). Ctrl-C para fechar o servidor.\n'
fi

wait "$SERVIDOR"
