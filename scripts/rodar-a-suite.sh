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
#     A_SECO=1 bash scripts/rodar-a-suite.sh     # só diz as partes e o tempo previsto de cada uma
#
# AS PARTES SÃO DE MESMO TEMPO, NÃO DE MESMO NÚMERO DE ARQUIVOS (08/10/2026). O
# `split -n l/24` repartia por linha, e as partes iam de 41 s a 241 s com o mesmo
# número de arquivos. O tempo de cada arquivo mora em `docs/data/tempos-da-suite.csv`
# (versionado: o CI roda este mesmo script, e a regra «a ordem é a mesma em toda
# máquina» vale para a partição); o maior arquivo vai para a parte mais leve, e o
# arquivo sem linha no CSV pesa a mediana dos medidos (com o CSV vazio, todos pesam
# igual, e a partição cai no número de arquivos). O fecho reescreve o CSV
# (`docs/process/ferramentas-da-leva/tempos-da-suite.py`).
#
# PARTES_EM_PARALELO=N (desligada por padrão): as partes sem arquivo que toque a
# máquina rodam N a N, nas vagas do semáforo `VEZ_DO_PYTEST=<vez-do-pytest.sh>`
# (`nenhum` roda sem semáforo); as que tocam continuam em série, depois. A
# partição muda com a chave (as que tocam ficam juntas nas últimas partes). Só
# se liga depois de uma corrida inteira, na máquina livre, sem morte do vigia de
# memória do harness (a de 08/09).
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
# `PARTIDO=1` é do filho da chave PARTES_EM_PARALELO: as partes já estão em $SAIDA.
[ -n "${PARTIDO:-}" ] || ls tests/unit/test_*.py | LC_ALL=C sort > "$SAIDA/todos.txt"
total=$(wc -l < "$SAIDA/todos.txt")
[ "$total" -gt 0 ] || { echo "ERRO: nenhum arquivo de teste em tests/unit/."; exit 2; }

# QUEM TOCA A MÁQUINA (só para a chave PARTES_EM_PARALELO): o arquivo que cita o
# que mexe no aparelho, no som, no BlueZ ou no systemd. Errar para mais custa
# paralelismo; errar para menos põe um teste que toca o aparelho ao lado de outro.
PARTES_EM_PARALELO="${PARTES_EM_PARALELO:-0}"
PADRAO_QUE_TOCA="uinput|UInput|hidraw|uhid|UHID|/dev/input|evdev|usbip|vudc|configfs|udevadm|systemctl|bluetoothctl|pactl|wpctl|pw-cli"
CSV_DOS_TEMPOS="${CSV_DOS_TEMPOS:-$RAIZ/docs/data/tempos-da-suite.csv}"
[ -n "${PARTIDO:-}" ] || : > "$SAIDA/toca-a-maquina.txt"
if [ -z "${PARTIDO:-}" ] && [ "$PARTES_EM_PARALELO" -gt 0 ] 2> /dev/null; then
  [ -n "${VEZ_DO_PYTEST:-}" ] || { echo "ERRO: PARTES_EM_PARALELO pede VEZ_DO_PYTEST=<vez-do-pytest.sh> (ou «nenhum»): sem as vagas do semáforo, pytest solto chama o earlyoom."; exit 2; }
  xargs grep -lE "$PADRAO_QUE_TOCA" < "$SAIDA/todos.txt" > "$SAIDA/toca-a-maquina.txt" 2> /dev/null || true
fi

# A PARTIÇÃO PELO TEMPO. Entra a lista (na ordem do LC_ALL=C), o CSV e quem toca a
# máquina; sai `parte-NN` com os arquivos de cada parte em ordem de nome, e
# `pesos.tsv` (pool, peso em ms, posição, arquivo) para quem quiser conferir.
# Inteiros em milissegundos e desempate por nome: a mesma saída em toda máquina.
partir_pelo_tempo() {  # $1 lista · $2 csv · $3 partes · $4 prefixo · $5 toca · $6 pesos
  local lista="$1" csv="$2" partes="$3" prefixo="$4" toca="$5" pesos="$6" k
  [ -f "$csv" ] || csv=/dev/null
  for ((k = 0; k < partes; k++)); do : > "$(printf '%s%02d' "$prefixo" "$k")"; done
  LC_ALL=C awk -F, -v toca="$toca" '
    FILENAME == ARGV[1] { if ($0 !~ /^#/ && $1 != "arquivo" && $2 ~ /^[0-9]+$/) ms[$1] = $2 + 0; next }
    FILENAME == toca { maq[$0] = 1; next }
    { n++; nome[n] = $0; if (($0 in ms) && ms[$0] > 0) { m++; v[m] = ms[$0] } }
    END {
      for (i = 2; i <= m; i++) { x = v[i]; j = i - 1; while (j >= 1 && v[j] > x) { v[j + 1] = v[j]; j-- } v[j + 1] = x }
      med = (m > 0) ? v[int((m + 1) / 2)] : 1000
      for (i = 1; i <= n; i++) {
        w = (nome[i] in ms && ms[nome[i]] > 0) ? ms[nome[i]] : med
        printf "%d\t%d\t%d\t%s\n", (nome[i] in maq) ? 1 : 0, w, i, nome[i]
      }
    }' "$csv" "$toca" "$lista" > "$pesos"
  LC_ALL=C sort -t "$(printf '\t')" -k2,2nr -k3,3n "$pesos" |
    LC_ALL=C awk -F'\t' -v P="$partes" '
      { pool[NR] = $1; w[NR] = $2; pos[NR] = $3; nome[NR] = $4; tot[$1] += $2; cnt[$1]++ }
      END {
        if (cnt[1] == 0) { np[0] = P; ini[0] = 0 }
        else if (cnt[0] == 0) { np[1] = P; ini[1] = 0 }
        else {
          np[1] = int(P * tot[1] / (tot[0] + tot[1]) + 0.5)
          if (np[1] < 1) np[1] = 1
          if (np[1] > P - 1) np[1] = P - 1
          np[0] = P - np[1]; ini[0] = 0; ini[1] = np[0]
        }
        for (r = 1; r <= NR; r++) {
          pl = pool[r]; melhor = ini[pl]
          for (q = ini[pl]; q < ini[pl] + np[pl]; q++)
            if (carga[q] + 0 < carga[melhor] + 0 || (carga[q] + 0 == carga[melhor] + 0 && quant[q] + 0 < quant[melhor] + 0)) melhor = q
          carga[melhor] += w[r]; quant[melhor]++
          printf "%d\t%d\t%s\n", melhor, pos[r], nome[r]
        }
      }' |
    LC_ALL=C sort -t "$(printf '\t')" -k1,1n -k2,2n |
    LC_ALL=C awk -F'\t' -v prefixo="$prefixo" '{ print $3 >> sprintf("%s%02d", prefixo, $1) }'
}
[ -n "${PARTIDO:-}" ] || partir_pelo_tempo "$SAIDA/todos.txt" "$CSV_DOS_TEMPOS" "$PARTES" "$SAIDA/parte-" \
  "$SAIDA/toca-a-maquina.txt" "$SAIDA/pesos.tsv"

# QUEM CARREGA O WEBKIT: os módulos de `src/` e `scripts/` que o pedem no
# código e, até o fecho, quem importa um deles (a `aba09` o carrega pela
# `ponte_da_tela`), lidos agora. O arquivo de teste é do WebKit se diz
# `WebKit2` ou importa um deles; errar para mais custa um processo, errar para
# menos põe o WebKit de volta no processo da parte. O nome do pacote tem
# dígito (`hefesto_dualsense4unix`), e a classe de caracteres o aceita.
# OS AJUDANTES DE `tests/unit/` (os `.py` sem prefixo `test_`: `janela_aberta_comum.py`,
# `mesa_do_mockup.py`…) entram na varredura como os de `src/`: o arquivo de teste que
# pede o `_gtk` a um ajudante não diz `WebKit2` e, sem isso, voltaria ao processo da
# parte, onde o WebKit morre com `rc=139` (A-JANELA-ABERTA-CABE-NA-PARTE-01).
importa_um_de() {  # $1 = os nomes, separados por `|`
  printf '%s' "^[[:space:]]*(import[[:space:]]+([A-Za-z0-9_]+\.)*($1)\b|from[[:space:]]+([A-Za-z0-9_]+\.)*($1)[[:space:]]+import|from[[:space:]]+[A-Za-z0-9_.]+[[:space:]]+import[[:space:]][^#]*\b($1)\b)"
}
nomes_de_modulo() { sed -E 's|/__init__\.py$|.py|; s|.*/||; s|\.py$||' | LC_ALL=C sort -u; }
mapfile -t _ajudantes < <(find tests/unit -maxdepth 1 -name '*.py' ! -name 'test_*' \
    ! -name '__init__.py' ! -name 'conftest.py' 2> /dev/null | LC_ALL=C sort)
_onde_se_importa=(src scripts ${_ajudantes[@]+"${_ajudantes[@]}"})
mapfile -t _modulos < <(grep -rlE --include='*.py' \
    "^[[:space:]]*(gi\.require_version\([\"']WebKit2|from gi\.repository import .*\bWebKit2\b)" \
    "${_onde_se_importa[@]}" 2> /dev/null | nomes_de_modulo)
while [ ${#_modulos[@]} -gt 0 ]; do
  mapfile -t _fecho < <({ printf '%s\n' "${_modulos[@]}"
    grep -rlE --include='*.py' "$(importa_um_de "$(IFS='|'; printf '%s' "${_modulos[*]}")")" \
      "${_onde_se_importa[@]}" 2> /dev/null | nomes_de_modulo; } | LC_ALL=C sort -u)
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

# A SECO: as partes e o tempo previsto de cada uma (a soma dos pesos), sem rodar
# nada e sem recibo. É o que o fecho e a régua conferem antes de gastar uma hora.
if [ -n "${A_SECO:-}" ]; then
  LC_ALL=C awk -F'\t' -v prefixo="$SAIDA/parte-" -v P="$PARTES" '
    FILENAME == ARGV[1] { peso[$4] = $2; next }
    FILENAME == ARGV[2] { maq[$0] = 1; next }
    { arq[FILENAME]++; t[FILENAME] += peso[$0]; if ($0 in maq) m[FILENAME]++ }
    END {
      for (k = 0; k < P; k++) {
        f = sprintf("%s%02d", prefixo, k); marca = (m[f] > 0) ? "  toca a máquina" : ""
        printf "  parte-%02d (%d arq): previsto %.1f s%s\n", k, arq[f], t[f] / 1000, marca
        soma += t[f]; if (k == 0 || t[f] > maior) maior = t[f]; if (k == 0 || t[f] < menor) menor = t[f]
      }
      printf "\ntotal previsto %.1f s · maior parte %.1f s · menor %.1f s · diferença %.1f s\n", soma / 1000, maior / 1000, menor / 1000, (maior - menor) / 1000
    }' "$SAIDA/pesos.tsv" "$SAIDA/toca-a-maquina.txt" "$SAIDA"/parte-[0-9][0-9]
  exit 0
fi

so_esta="${1:-}"
# Argumentos a mais para cada parte; o CI passa a cobertura por aqui.
read -r -a extra <<< "${SUITE_PYTEST_ARGS:-}"
vermelhos=0
verdes=0
passaram=0
pulados=0
# OS LOGS DESTA EXECUÇÃO, e só eles: o resumo (`falhas.txt`) lê esta lista, nunca o
# glob do diretório. O `SAIDA` guarda o que corridas anteriores deixaram (o
# `fecho-suite.sh` chama este script uma vez por parte no mesmo `SAIDA`, e o log da
# parte vermelha de uma chamada anterior é o que se tria), e `parte-*.log` lia tudo:
# o resumo da parte 05 trazia o vermelho da 02 (6 vermelhos numa corrida de 1, no
# fecho da 1.6.5). Nada se apaga; o log velho só não entra na conta.
logs_desta_corrida=()
# Os `parte-NN` que esta divisão fez são 00..PARTES-1; os de uma corrida de mais
# partes (`parte-12..23` depois de um `PARTES=12`) ficam no disco e não correm.
partes_desta_divisao=()
for ((k = 0; k < PARTES; k++)); do partes_desta_divisao+=("$(printf '%02d' "$k")"); done
if [ -n "$so_esta" ]; then
  case " ${partes_desta_divisao[*]} " in
    *" $so_esta "*) ;;
    *) echo "ERRO: a parte «$so_esta» não existe nesta divisão (00 a $(printf '%02d' $((PARTES - 1))))."; exit 2;;
  esac
fi

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
if [ -n "${PARTIDO:-}" ] && [ -f "$SAIDA/pilha-nativa.so" ]; then
  pilha="$SAIDA/pilha-nativa.so"  # o pai compilou; recompilar sob o filho em voo é corrida
elif [ -f "$RAIZ/scripts/pilha_nativa.c" ] && command -v cc > /dev/null 2>&1; then
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
  logs_desta_corrida+=("$log")
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
feitas=" "
# A CHAVE (desligada por padrão): as partes sem arquivo que toque a máquina, N a N,
# cada uma num filho que pega uma vaga do semáforo. O filho é este mesmo script
# com a parte pedida (e por isso sem recibo); a saída de cada um fica em
# `paralelo-NN.*` e sai aqui, na ordem das partes, quando todos voltam.
if [ "$PARTES_EM_PARALELO" -gt 0 ] 2> /dev/null && [ -z "$so_esta" ]; then
  em_voo=0
  marca=$(mktemp "$SAIDA/marca.XXXXXX")
  for n in "${partes_desta_divisao[@]}"; do
    f="$SAIDA/parte-$n"
    [ -s "$f" ] || continue
    ! grep -qxFf "$SAIDA/toca-a-maquina.txt" "$f" || continue
    feitas="$feitas$n "
    while [ "$em_voo" -ge "$PARTES_EM_PARALELO" ]; do wait -n || true; em_voo=$((em_voo - 1)); done
    (
      export PARTIDO=1 PARTES_EM_PARALELO=0 SAIDA PY
      if [ "$VEZ_DO_PYTEST" = nenhum ]; then bash "$0" "$n"; else bash "$VEZ_DO_PYTEST" bash "$0" "$n"; fi \
        > "$SAIDA/paralelo-$n.saida" 2>&1
      echo $? > "$SAIDA/paralelo-$n.rc"
    ) &
    em_voo=$((em_voo + 1))
  done
  wait
  for n in $feitas; do
    # os logs que o filho escreveu agora: o que não é mais novo que a marca é de corrida
    # velha (o filho morreu antes de abrir o log), e não conta
    for l in "$SAIDA/parte-$n.log" "$SAIDA/parte-$n"-*.log; do
      [ "$l" -nt "$marca" ] && logs_desta_corrida+=("$l")
    done
    grep -E '^  parte-|^    ' "$SAIDA/paralelo-$n.saida" 2> /dev/null
    read -r _ok _pulo < "$SAIDA/paralelo-$n.contagem" 2> /dev/null || { _ok=0; _pulo=0; }
    passaram=$((passaram + _ok)); pulados=$((pulados + _pulo))
    sozinhos=$((sozinhos + $(grep -c 'em processo próprio' "$SAIDA/paralelo-$n.saida" 2> /dev/null || true)))
    if [ "$(cat "$SAIDA/paralelo-$n.rc" 2> /dev/null || echo 1)" = 0 ]; then verdes=$((verdes + 1)); else vermelhos=$((vermelhos + 1)); fi
  done
  rm -f "$marca"
fi
for n in "${partes_desta_divisao[@]}"; do
  f="$SAIDA/parte-$n"
  [ -z "$so_esta" ] || [ "$n" = "$so_esta" ] || continue
  case "$feitas" in *" $n "*) continue;; esac
  [ -e "$f" ] || { echo "  parte-$n: SEM ARQUIVO — a divisão quebrou"; vermelhos=$((vermelhos+1)); continue; }

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

# o filho da chave diz ao pai quantos passaram e quantos pularam
[ -z "$so_esta" ] || echo "$passaram $pulados" > "$SAIDA/paralelo-$so_esta.contagem"
echo
# SÓ os logs desta execução (ver `logs_desta_corrida`): sem arquivo, `grep` leria o stdin.
if [ ${#logs_desta_corrida[@]} -gt 0 ]; then
  grep -ho "^FAILED [^ ]*\|^ERROR [^ ]*" "${logs_desta_corrida[@]}" 2>/dev/null | sort -u > "$SAIDA/falhas.txt"
else
  : > "$SAIDA/falhas.txt"
fi
quantas=$(wc -l < "$SAIDA/falhas.txt")
echo "testes que passaram: $passaram · pulados: $pulados"
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
