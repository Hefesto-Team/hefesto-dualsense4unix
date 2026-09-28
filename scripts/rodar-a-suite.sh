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
# shellcheck disable=SC2012  # os nomes desta casa são ASCII; `ls|sort` é a
# forma que o GUIA.md documenta há semanas, e trocá-la por `find` mudaria a
# ORDEM — que é o que decide a divisão em partes.
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
for f in "$SAIDA"/parte-*; do
  case "$f" in *.log|*.txt) continue;; esac
  n="${f##*parte-}"
  [ -z "$so_esta" ] || [ "$n" = "$so_esta" ] || continue

  quantos=$(wc -l < "$f")
  # TRAVA DE LOTE VAZIO: um lote sem arquivo passa como "0 testes" e some.
  [ "$quantos" -gt 0 ] || { echo "  parte-$n: VAZIA — a divisão quebrou"; vermelhos=$((vermelhos+1)); continue; }

  # Um arquivo por linha vira um argumento por arquivo — é o ponto do array.
  mapfile -t arquivos < "$f"
  PYTHONPATH="$RAIZ/src" "$PY" -m pytest "${arquivos[@]}" "${extra[@]}" \
      -q -p no:cacheprovider > "$SAIDA/parte-$n.log" 2>&1
  linha=$(tail -1 "$SAIDA/parte-$n.log")

  # SILÊNCIO DE PYTEST NÃO É VERDE. Sem linha de sumário, o processo morreu.
  case "$linha" in
    *passed*|*failed*|*error*|*"no tests ran"*) ;;
    *) linha="SEM SUMÁRIO — o processo morreu no meio (ver o log)"; ;;
  esac
  # `xfailed` e `xpassed` CONTÊM "failed" e "passed" — casar por substring aqui
  # conta reprovação onde não há. Medido no primeiro uso deste script: uma parte
  # com `750 passed, 4 xfailed` foi contada como vermelha.
  semx="${linha//xfailed/}"; semx="${semx//xpassed/}"
  case "$semx" in
    *failed*|*error*|*SEM\ SUMÁRIO*|*"no tests ran"*) vermelhos=$((vermelhos+1));;
    *) verdes=$((verdes+1));;
  esac
  echo "  parte-$n ($quantos arq): $linha"
  # A contagem do recibo: `N passed` não casa `N xpassed` (há um `x` antes).
  n_ok=$(printf '%s\n' "$linha" | grep -o '[0-9]\+ passed' | grep -o '[0-9]\+' || true)
  n_pulo=$(printf '%s\n' "$linha" | grep -o '[0-9]\+ skipped' | grep -o '[0-9]\+' || true)
  passaram=$((passaram + ${n_ok:-0}))
  pulados=$((pulados + ${n_pulo:-0}))
done

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
