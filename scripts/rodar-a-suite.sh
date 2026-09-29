#!/usr/bin/env bash
# A suíte inteira, em pedaços que sobrevivem — e sobreviver é o ponto.
#
# TRÊS COISAS MATAM UMA CORRIDA DA SUÍTE NESTA CASA, e as três estão curadas
# aqui. Nenhuma delas é teste reprovando, e as três se leem como se fossem:
#
#   1. UM PROCESSO SÓ MORRE NO MEIO, em ponto variável, sem traceback e sem
#      sumário. Medido em 25/08/2026 com a máquina OCIOSA — não é carga. O
#      `rc=1` que sobra não é reprovação.
#
#   2. O VIGIA DE MEMÓRIA DO HARNESS MATA TAREFA DE FUNDO. Medido em
#      08/09/2026: DUAS corridas morreram com **9,1 GB disponíveis** e a
#      máquina folgada. O vigia é de fora — não há `except` a escrever, e o
#      conserto é o pedaço menor rodando em PRIMEIRO PLANO.
#
#   3. LOTE MONTADO DA ÁRVORE ERRADA MORRE CALADO. Um arquivo que não existe
#      aborta o LOTE INTEIRO, e `no tests ran` lê-se como limpo. Por isso a
#      lista nasce de `ls` DESTA árvore, e há uma trava que recusa lote vazio.
#
# E O PROCESSO QUE MORRE POR SINAL DIZ ONDE. Em 26/09/2026 uma parte morreu
# com `rc=139` (o WebKit) e nenhum log tinha a pilha. Cada arquivo que carrega
# o WebKit roda em processo próprio (o sinal leva um arquivo, não a parte), e
# todo pytest leva a `scripts/pilha_nativa.c` por `LD_PRELOAD`: o log de quem
# morre tem a pilha Python (o `faulthandler`) e a nativa.
#
# USO:
#     bash scripts/rodar-a-suite.sh              # as 24 partes, em série
#     bash scripts/rodar-a-suite.sh 07           # só a parte 07
#     PARTES=12 bash scripts/rodar-a-suite.sh    # pedaços maiores (mais risco)
#
# A saída de cada parte vai para ARQUIVO — nunca crua no terminal dela, que é o
# mesmo em que a conversa acontece.
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ" || exit 2

PARTES="${PARTES:-24}"
SAIDA="${SAIDA:-/tmp/suite-$(date +%H%M%S)}"
PY="${PY:-$RAIZ/.venv/bin/python}"
[ -x "$PY" ] || PY="/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix/.venv/bin/python"
[ -x "$PY" ] || { echo "ERRO: não achei um python. Passe PY=<caminho>."; exit 2; }

mkdir -p "$SAIDA"
# A LISTA NASCE DESTA ÁRVORE. Ver a armadilha 3 no cabeçalho.
# shellcheck disable=SC2012  # os nomes desta casa são ASCII; a lista é
# `ls tests/unit/test_*.py | sort`, e trocá-la por `find` mudaria a ORDEM —
# que é o que decide a divisão em partes.
#
# E A ORDEM É A MESMA EM TODA MÁQUINA, pelo `LC_ALL=C` (27/09/2026). O `sort`
# segue o idioma de quem roda: em pt_BR ele ignora o `_` e a divisão sai outra
# que a do runner (C.UTF-8) — medido na corrida 36354426805, a
# `test_o_gesto_de_pareamento.py` rodava na parte 14 do CI e na 15 em casa, com
# outros vizinhos no mesmo processo. Vermelho de ordem só se reproduz com as
# mesmas partes.
ls tests/unit/test_*.py | LC_ALL=C sort > "$SAIDA/todos.txt"
total=$(wc -l < "$SAIDA/todos.txt")
[ "$total" -gt 0 ] || { echo "ERRO: nenhum arquivo de teste em tests/unit/."; exit 2; }
split -n "l/$PARTES" -d "$SAIDA/todos.txt" "$SAIDA/parte-"

# QUEM CARREGA O WEBKIT: os módulos de `src/` e `scripts/` que o pedem no
# código e, até o fecho, quem importa um deles (a `aba09` o carrega pela
# `ponte_da_tela`), lidos agora. O arquivo de teste é do WebKit se diz
# `WebKit2` ou importa um deles; errar para mais custa um processo, errar para
# menos põe o WebKit de volta no processo da parte. O nome do pacote tem
# dígito (`hefesto_dualsense4unix`), e a classe de caracteres o aceita.
importa_um_de() {  # $1 = os nomes, separados por `|`
  printf '%s' "^[[:space:]]*(import[[:space:]]+([A-Za-z0-9_]+\.)*($1)\b|from[[:space:]]+([A-Za-z0-9_]+\.)*($1)[[:space:]]+import|from[[:space:]]+[A-Za-z0-9_.]+[[:space:]]+import[[:space:]][^#]*\b($1)\b)"
}
nomes_de_modulo() { sed -E 's|/__init__\.py$|.py|; s|.*/||; s|\.py$||' | LC_ALL=C sort -u; }
mapfile -t _modulos < <(grep -rlE --include='*.py' \
    "^[[:space:]]*(gi\.require_version\([\"']WebKit2|from gi\.repository import .*\bWebKit2\b)" \
    src scripts 2> /dev/null | nomes_de_modulo)
while [ ${#_modulos[@]} -gt 0 ]; do
  mapfile -t _fecho < <({ printf '%s\n' "${_modulos[@]}"
    grep -rlE --include='*.py' "$(importa_um_de "$(IFS='|'; printf '%s' "${_modulos[*]}")")" \
      src scripts 2> /dev/null | nomes_de_modulo; } | LC_ALL=C sort -u)
  [ ${#_fecho[@]} -gt ${#_modulos[@]} ] || break
  _modulos=("${_fecho[@]}")
done
padrao_do_webkit=""
[ ${#_modulos[@]} -eq 0 ] || padrao_do_webkit=$(importa_um_de "$(IFS='|'; printf '%s' "${_modulos[*]}")")
e_do_webkit() {
  grep -qF 'WebKit2' "$1" && return 0
  [ -n "$padrao_do_webkit" ] || return 1
  grep -qE "$padrao_do_webkit" "$1"
}
# `LISTAR_O_WEBKIT=1` só diz quem roda em processo próprio, e sai: é a
# pergunta que a régua faz a este script sobre a árvore de verdade.
if [ -n "${LISTAR_O_WEBKIT:-}" ]; then
  while IFS= read -r a; do e_do_webkit "$a" && printf '%s\n' "$a"; done < "$SAIDA/todos.txt"
  exit 0
fi

echo "suíte — $total arquivos em $PARTES partes"
echo "        python $PY"
echo "        saída  $SAIDA"
echo

so_esta="${1:-}"
# Argumentos a mais para cada parte; o CI passa a cobertura por aqui.
read -r -a extra <<< "${SUITE_PYTEST_ARGS:-}"
vermelhos=0
verdes=0
passaram=0
pulados=0

# O RECIBO DA MEDIDA. A trava do push da máquina só deixa o `dev` subir com o
# recibo da suíte da MESMA árvore (`<git comum>/hefesto-recibos/<árvore>.suite`),
# e quem o escreve é `scripts/recibo_da_medida.py`: `abrir` antes da primeira
# parte e `fechar` no fim, com o rc desta corrida. Só a corrida INTEIRA deixa
# recibo: com uma parte só, ou com argumentos a mais (um `-k` ou um
# `--deselect` encolhem a suíte sem mudar o nome dela), não há recibo.
recibo_da_corrida=""
if [ -z "$so_esta" ] && [ ${#extra[@]} -eq 0 ]; then
  recibo_da_corrida="$SAIDA/recibo-da-corrida.json"
  "$PY" "$RAIZ/scripts/recibo_da_medida.py" abrir suite \
    --raiz "$RAIZ" --corrida "$recibo_da_corrida" || true
  echo
elif [ -z "$so_esta" ]; then
  echo "recibo: esta corrida não deixa recibo — ela leva argumentos a mais (SUITE_PYTEST_ARGS)"
  echo
fi
# A PILHA NATIVA, compilada a cada corrida para a máquina de quem roda. Sem
# compilador, o processo que morre por sinal sai só com a pilha Python.
pilha=""
if [ -f "$RAIZ/scripts/pilha_nativa.c" ] && command -v cc > /dev/null 2>&1; then
  if cc -shared -fPIC -O1 -o "$SAIDA/pilha-nativa.so" "$RAIZ/scripts/pilha_nativa.c" -ldl \
      > "$SAIDA/pilha-nativa.cc.log" 2>&1; then
    pilha="$SAIDA/pilha-nativa.so"
  fi
fi
[ -n "$pilha" ] || echo "pilha nativa: sem compilador ou sem a fonte; quem morrer por sinal sai só com a pilha Python"

# Um processo de pytest: o sumário em `linha`, e a parte fica vermelha se ele
# reprova, some sem sumário ou morre por sinal.
rodar_pytest() {  # $1 = o log; o resto, os arquivos
  local log="$1" rc_do_processo
  shift
  if [ -n "$pilha" ]; then
    LD_PRELOAD="$pilha${LD_PRELOAD:+ $LD_PRELOAD}" PYTHONPATH="$RAIZ/src" \
      "$PY" -m pytest "$@" "${extra[@]}" -q -p no:cacheprovider > "$log" 2>&1
  else
    PYTHONPATH="$RAIZ/src" "$PY" -m pytest "$@" "${extra[@]}" -q -p no:cacheprovider > "$log" 2>&1
  fi
  rc_do_processo=$?
  # O SUMÁRIO é a última linha com o tempo da sessão (`… in 1.23s`), e não a
  # última do log: quem morre ao sair escreve a pilha DEPOIS dele.
  linha=$(grep -E '(passed|failed|errors?|skipped|deselected|no tests ran).* in [0-9.]+s' "$log" | tail -1)
  # SILÊNCIO DE PYTEST NÃO É VERDE. Sem linha de sumário, o processo morreu.
  # O arquivo que pula inteiro (sem o GTK) diz só `N skipped`, com rc=5: é
  # sumário, e o pulo vai ao recibo como não medido.
  case "$linha" in
    *passed*|*failed*|*error*|*skipped*|*deselected*|*"no tests ran"*) ;;
    *) linha="SEM SUMÁRIO — o processo morreu no meio"; ;;
  esac
  # O WebKit também morre DEPOIS do sumário, ao sair: o rc diz o sinal.
  if [ "$rc_do_processo" -gt 128 ]; then
    linha="$linha · MORREU PELO SINAL $((rc_do_processo - 128)): a pilha está em $log"
  fi
  # `xfailed` e `xpassed` CONTÊM "failed" e "passed" — casar por substring aqui
  # conta reprovação onde não há. Medido no primeiro uso deste script: uma parte
  # com `750 passed, 4 xfailed` foi contada como vermelha.
  local semx="${linha//xfailed/}"
  semx="${semx//xpassed/}"
  case "$semx" in
    *failed*|*error*|*SEM\ SUMÁRIO*|*"no tests ran"*|*"MORREU PELO SINAL"*) vermelha=1;;
  esac
  # A contagem do recibo: `N passed` não casa `N xpassed` (há um `x` antes).
  local n_ok n_pulo
  n_ok=$(printf '%s\n' "$linha" | grep -o '[0-9]\+ passed' | grep -o '[0-9]\+' || true)
  n_pulo=$(printf '%s\n' "$linha" | grep -o '[0-9]\+ skipped' | grep -o '[0-9]\+' || true)
  passaram=$((passaram + ${n_ok:-0}))
  pulados=$((pulados + ${n_pulo:-0}))
}

sozinhos=0
for f in "$SAIDA"/parte-*; do
  case "$f" in *.log|*.txt|*.so) continue;; esac
  n="${f##*parte-}"
  [ -z "$so_esta" ] || [ "$n" = "$so_esta" ] || continue

  quantos=$(wc -l < "$f")
  # TRAVA DE LOTE VAZIO: um lote sem arquivo passa como "0 testes" e some.
  [ "$quantos" -gt 0 ] || { echo "  parte-$n: VAZIA — a divisão quebrou"; vermelhos=$((vermelhos+1)); continue; }

  # Um arquivo por linha vira um argumento por arquivo — é o ponto do array.
  mapfile -t arquivos < "$f"
  comuns=()
  do_webkit=()
  for a in "${arquivos[@]}"; do
    if e_do_webkit "$a"; then do_webkit+=("$a"); else comuns+=("$a"); fi
  done
  vermelha=0
  # A TRAVA DA LISTA VAZIA: pytest sem arquivo roda a suíte inteira.
  if [ ${#comuns[@]} -gt 0 ]; then
    rodar_pytest "$SAIDA/parte-$n.log" "${comuns[@]}"
    echo "  parte-$n ($quantos arq): $linha"
  else
    echo "  parte-$n ($quantos arq): todos do WebKit"
  fi
  for a in "${do_webkit[@]}"; do
    nome="${a##*/}"
    nome="${nome%.py}"
    rodar_pytest "$SAIDA/parte-$n-$nome.log" "$a"
    echo "    $nome, em processo próprio: $linha"
    sozinhos=$((sozinhos+1))
  done
  if [ "$vermelha" -eq 0 ]; then verdes=$((verdes+1)); else vermelhos=$((vermelhos+1)); fi
done
[ "$sozinhos" -eq 0 ] || echo "  (os $sozinhos arquivos do WebKit rodaram em processo próprio)"

echo
grep -ho "^FAILED [^ ]*\|^ERROR [^ ]*" "$SAIDA"/parte-*.log 2>/dev/null | sort -u > "$SAIDA/falhas.txt"
quantas=$(wc -l < "$SAIDA/falhas.txt")
echo "partes verdes: $verdes · partes com vermelho: $vermelhos · testes vermelhos: $quantas"
[ "$quantas" -eq 0 ] || { echo; cat "$SAIDA/falhas.txt"; }
echo
echo "os logs ficam em $SAIDA"
rc=1
[ "$vermelhos" -eq 0 ] && rc=0
if [ -n "$recibo_da_corrida" ]; then
  # Pulo não é verde: o teste pulado sai no recibo como NÃO MEDIDO.
  nao_medidos=()
  [ "$pulados" -eq 0 ] || nao_medidos=(--nao-medido "testes pulados: $pulados")
  echo
  "$PY" "$RAIZ/scripts/recibo_da_medida.py" fechar suite "$rc" \
    --raiz "$RAIZ" --corrida "$recibo_da_corrida" \
    --contagem "$total arquivos em $PARTES partes; $verdes partes verdes; $passaram testes passaram; $pulados pulados" \
    ${nao_medidos[@]+"${nao_medidos[@]}"} || true
fi
exit "$rc"
