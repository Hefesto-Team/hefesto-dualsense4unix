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
#     bash scripts/rodar-a-suite.sh --lote <lista>   # só os arquivos da lista (ou LOTE=<lista>)
#
# O LOTE (09/10/2026): uma lista avulsa de arquivos de teste, um por linha, roda
# com o MESMO isolamento da suíte — cada arquivo do WebKit num processo só dele, o
# resto junto, todos com a pilha nativa — numa parte só, sem recibo. É o lote de
# quem trabalha numa árvore de voo: `pytest $(cat lista)` sob `xvfb-run` punha
# vários arquivos do WebKit no mesmo processo, e a queda intermitente que a suíte
# já curou voltava ali. A lista que não existe, vazia, ou com um arquivo que não
# está nesta árvore (ou que não é `test_*.py`) falha ALTO, antes de rodar
# qualquer coisa: é a armadilha 3.
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
# PARTES_EM_PARALELO=N (desligada por padrão até uma corrida inteira provar, na máquina livre, a
# mesma contagem de testes da série e nenhuma parte morta: D-0810-AS-PARTES-EM-PARALELO-ESPERAM-A-PROVA).
# `PARTES_EM_PARALELO=auto` (21/10/2026) dá N=3 quando a árvore tem o semáforo da casa
# `docs/process/ferramentas-da-leva/vez-do-pytest.sh` e a máquina tem 8 núcleos ou mais, e 0 no
# clone, no runner do CI, no lote e com `SUITE_PYTEST_ARGS`; com a prova feita, o padrão passa a
# ser `auto`. As partes rodam em filhos, N a N, cada
# um numa vaga do semáforo `VEZ_DO_PYTEST=<vez-do-pytest.sh>` (`nenhum` roda sem semáforo). Cada
# filho de parte LEVE nasce com lar (HOME e XDG_*), TMPDIR, D-Bus e Xvfb próprios, como o
# `portoes.sh` faz com cada pytest: dois filhos nunca dividem pasta, bus nem display. Quem TOCA a
# máquina (o arquivo que cita um serviço do sistema ou do usuário, `PADRAO_QUE_TOCA`) vai nas
# últimas partes e corre UMA por vez, ao lado das leves: o tempo da suíte é o da maior das duas
# frentes, e não a soma. A partição muda com a chave (as que tocam ficam juntas): para triar a
# parte NN de uma corrida com a chave, `PARTES_EM_PARALELO=auto rodar-a-suite.sh NN` repete a
# MESMA divisão e roda só aquela parte, em série.
#
# O QUE NÃO TOCA MAIS A MÁQUINA (21/10/2026): `uinput`, `uhid`, `hidraw`, `/dev/input` e `evdev`
# saíram do padrão. O `conftest.py` recusa a abertura de `/dev/uinput` e `/dev/uhid` (e as
# fábricas `uinput.Device` e `evdev.UInput`) em TODO processo de teste (VIGIA-DE-APARELHO-01), e
# aponta o sysfs de hidraw, o configfs e o gadget para pastas vazias; ler `/dev/input` não escreve
# em nada. O padrão antigo punha 754 de 1921 arquivos na frente das que tocam (30 min de 64);
# `PADRAO_QUE_TOCA=<regex>` devolve o padrão que se quiser.
#
# A saída de cada parte vai para ARQUIVO — nunca crua no terminal dela, que é o
# mesmo em que a conversa acontece.
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ" || exit 2

# O D-BUS DA SUÍTE NÃO TEM PORTAL. O Chrome dos testes de tela pede o `org.freedesktop.portal.Desktop`
# ao D-Bus da sessão, e o `dbus-daemon` acordava o portal da máquina, cujo backend do COSMIC morre sem
# Wayland: 8 pânicos por parte, em 17 das 24 partes do fecho de 23/10/2026. O daemon procura o serviço
# primeiro no `$XDG_DATA_HOME/dbus-1/services`, e ali o portal é um `/bin/false` (a medida está no
# `_lar_sem_portal` do `portoes.sh`). Um dono só para os dois D-Bus da suíte: o do lar de cada parte
# leve (`lancar_filho`) e o de quem roda a suíte inteira (`SUITE_SOB_DBUS_PROPRIO=1`, o do fecho).
servicos_sem_portal() {  # $1 = a pasta que o `dbus-daemon` lê como `XDG_DATA_HOME`
  local servicos="$1/dbus-1/services" portal
  mkdir -p "$servicos"
  for portal in org.freedesktop.portal.Desktop org.freedesktop.portal.Documents; do
    printf '[D-BUS Service]\nName=%s\nExec=/bin/false\n' "$portal" > "$servicos/$portal.service"
  done
}
# `SUITE_SOB_DBUS_PROPRIO=1` põe a corrida sob D-Bus e Xvfb próprios. A pasta dos serviços vai SÓ ao
# `dbus-daemon`: o pytest recebe o `XDG_DATA_HOME` de quem chamou (a parte que toca a máquina roda no
# ambiente dele).
if [ -n "${SUITE_SOB_DBUS_PROPRIO:-}" ]; then
  for _b in dbus-run-session xvfb-run; do
    command -v "$_b" > /dev/null 2>&1 || { echo "ERRO: SUITE_SOB_DBUS_PROPRIO pede o $_b."; exit 2; }
  done
  _bus="$(mktemp -d "${TMPDIR:-/tmp}/suite-bus-XXXXXX")" || exit 2
  servicos_sem_portal "$_bus"
  if [ -n "${XDG_DATA_HOME+x}" ]; then _volta=(XDG_DATA_HOME="$XDG_DATA_HOME"); else _volta=(-u XDG_DATA_HOME); fi
  env XDG_DATA_HOME="$_bus" dbus-run-session -- env -u SUITE_SOB_DBUS_PROPRIO "${_volta[@]}" \
    xvfb-run -a bash "$RAIZ/scripts/${BASH_SOURCE[0]##*/}" "$@"
  _rc=$?
  rm -rf "$_bus"
  exit "$_rc"
fi

PARTES="${PARTES:-24}"
SAIDA="${SAIDA:-/tmp/suite-$(date +%H%M%S)}"
# O python: o `PY` de quem chama, o `HEFESTO_PY` da casa (o mesmo que o `portoes.sh` lê; é o que a árvore
# sem `.venv` recebe numa leva), a `.venv` desta árvore e o `python3` do sistema, nesta ordem. Nenhum
# caminho de máquina: em outro PC a suíte acha o python3 dele (10/10/2026).
PY="${PY:-}"
for _py in "${HEFESTO_PY:-}" "$RAIZ/.venv/bin/python" "$(command -v python3 || true)"; do
  [ -n "$PY" ] && [ -x "$PY" ] && break
  PY="$_py"
done
unset _py
[ -n "$PY" ] && [ -x "$PY" ] || { echo "ERRO: não achei um python. Passe PY=<caminho>."; exit 2; }

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
if [ "${1:-}" = "--lote" ]; then
  [ -n "${2:-}" ] || { echo "ERRO: --lote pede a lista: bash scripts/rodar-a-suite.sh --lote <lista>"; exit 2; }
  LOTE="$2"
  shift 2
fi
LOTE="${LOTE:-}"
if [ -n "$LOTE" ]; then
  # O LOTE: a lista é a de quem chama, conferida AQUI, e vira a única parte.
  [ -f "$LOTE" ] || { echo "ERRO: o lote «$LOTE» não existe."; exit 2; }
  PARTES=1
  PARTES_EM_PARALELO=0
  ruins=()
  : > "$SAIDA/todos.txt"
  while IFS= read -r a || [ -n "$a" ]; do
    a="${a#"${a%%[![:space:]]*}"}"
    a="${a%"${a##*[![:space:]]}"}"
    [ -n "$a" ] || continue
    a="${a#"$RAIZ"/}"
    case "${a##*/}" in
      test_*.py) [ -f "$a" ] || { ruins+=("$a (não existe nesta árvore)"); continue; } ;;
      *) ruins+=("$a (não é um arquivo test_*.py)"); continue ;;
    esac
    printf '%s\n' "$a" >> "$SAIDA/todos.txt"
  done < "$LOTE"
  if [ ${#ruins[@]} -gt 0 ]; then
    echo "ERRO: o lote «$LOTE» tem ${#ruins[@]} entrada(s) que não rodam — nada rodou:"
    printf '  %s\n' "${ruins[@]}"
    exit 2
  fi
  LC_ALL=C sort -u -o "$SAIDA/todos.txt" "$SAIDA/todos.txt"
  [ -s "$SAIDA/todos.txt" ] || { echo "ERRO: o lote «$LOTE» está vazio — pytest sem arquivo roda a suíte inteira."; exit 2; }
else
  [ -n "${PARTIDO:-}" ] || ls tests/unit/test_*.py | LC_ALL=C sort > "$SAIDA/todos.txt"
fi
total=$(wc -l < "$SAIDA/todos.txt")
[ "$total" -gt 0 ] || { echo "ERRO: nenhum arquivo de teste em tests/unit/."; exit 2; }

# QUEM TOCA A MÁQUINA (só para a chave PARTES_EM_PARALELO): o arquivo que cita o
# que mexe no aparelho, no som, no BlueZ ou no systemd. Errar para mais custa
# paralelismo; errar para menos põe um teste que toca o aparelho ao lado de outro.
PADRAO_QUE_TOCA="${PADRAO_QUE_TOCA:-usbip|vudc|configfs|udevadm|systemctl|bluetoothctl|pactl|wpctl|pw-cli}"
# `auto` liga a chave na árvore que tem o semáforo da casa (a máquina onde o `vez-do-pytest.sh`
# divide as vagas entre os agentes), fora do lote e sem argumento a mais. Com uma parte (`NN`) ela
# liga também, para a divisão ser a da corrida inteira; o agendador só corre sem `NN`. Numa árvore
# sem o semáforo (um clone, o runner do CI) fica desligada e a corrida é a de sempre.
PARTES_EM_PARALELO="${PARTES_EM_PARALELO:-0}"
if [ "$PARTES_EM_PARALELO" = auto ]; then
  PARTES_EM_PARALELO=0
  _vez_da_casa="$RAIZ/docs/process/ferramentas-da-leva/vez-do-pytest.sh"
  _nucleos=$(nproc 2> /dev/null || echo 1)
  if [ -z "$LOTE" ] && [ -z "${SUITE_PYTEST_ARGS:-}" ] && [ -z "${PARTIDO:-}" ] \
      && [ "$_nucleos" -ge 8 ] 2> /dev/null && { [ -n "${VEZ_DO_PYTEST:-}" ] || [ -f "$_vez_da_casa" ]; }; then
    PARTES_EM_PARALELO=3
    VEZ_DO_PYTEST="${VEZ_DO_PYTEST:-$_vez_da_casa}"
  fi
  unset _vez_da_casa _nucleos
fi
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

# QUEM CARREGA O WEBKIT. O arquivo de teste é do WebKit se diz `WebKit2` ou importa um
# módulo que o carrega; errar para mais custa um processo, errar para menos põe o WebKit de
# volta no processo da parte, onde ele morre com `rc=139`. A leitura é do `ast` do Python
# (o `FECHO_DO_WEBKIT` abaixo), rodada uma vez por corrida, e casa pelo CAMINHO PONTUADO
# INTEIRO (A-LISTA-DO-WEBKIT-DA-SUITE-VOLTA-AO-TAMANHO-REAL-01, 23/10/2026):
#
#   * o módulo se chama pelo caminho dele (`hefesto_dualsense4unix.cli.app`) e por cada
#     sufixo (`cli.app`, `app`), porque a casa põe pastas no `sys.path` (`import hefesto_vivo`,
#     `from pacotes import …`, `import regua_de_tela`); e o import casa INTEIRO com um deles.
#     O fecho textual de antes casava o nome nu em qualquer ponto do caminho, e o `app` de
#     `cli/app.py` casava todo `import hefesto_dualsense4unix.app.…`: 421 módulos e 1582
#     arquivos em processo próprio, 75 s só para listar (eram 38, 127 e 6 s em 17/10);
#   * em `src/` e `scripts/`, SÓ O IMPORT DE TOPO propaga (o corpo do módulo, os `if`, `try`
#     e corpos de classe, fora o `if TYPE_CHECKING:`): o import dentro de função só roda se a
#     função for chamada, e foi uma corrente deles (`a09_sistema` → `janela`, `abrir` →
#     `a09_sistema`, `tray` → `abrir`) que abriu a porta;
#   * no arquivo de teste e nos ajudantes de `tests/unit/` (os `.py` sem `test_`, como
#     `janela_aberta_comum.py`), TODO import conta, lido no texto (até o que está numa string,
#     para errar para mais), com o relativo (`from .x import y`, `from ..pasta.x import y`)
#     e o `__import__("…")`/`import_module("…")` de nome literal; o ajudante que pede o `_gtk`
#     dentro de função leva consigo quem o importa (A-JANELA-ABERTA-CABE-NA-PARTE-01).
#
# O módulo que pede o WebKit é o que diz `gi.require_version("WebKit2", …)` ou
# `from gi.repository import … WebKit2` (no topo, em `src/` e `scripts/`); o arquivo de teste
# ou ajudante que diz `WebKit2` em qualquer lugar também é do WebKit.
IFS= read -r -d '' FECHO_DO_WEBKIT << 'PY' || true
import ast
import os
import re
import sys

raiz, lista = sys.argv[1], sys.argv[2]
os.chdir(raiz)
LER = re.compile(r"^[ \t]*import[ \t]+([^\n#;]+)", re.M)
DE = re.compile(r"^[ \t]*from[ \t]+(\.*[\w.]*)[ \t]+import[ \t]+(\([^)]*\)|[^\n#;]*)", re.M)
DINAMICO = re.compile(r"(?:__import__|import_module)\(\s*[\"']([\w.]+)[\"']")


def arquivos(pasta, raso=False):
    if raso:
        return sorted(f"{pasta}/{n}" for n in os.listdir(pasta) if n.endswith(".py")) \
            if os.path.isdir(pasta) else []
    saida = []
    for base, dirs, nomes in os.walk(pasta):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        saida += [f"{base}/{n}" for n in sorted(nomes) if n.endswith(".py")]
    return saida


def nomes_e_pacote(rel):
    """Os nomes pelos quais o arquivo se importa (o caminho pontuado e cada sufixo) e o pacote."""
    partes = rel[:-3].split("/")
    init = partes[-1] == "__init__"
    if init:
        partes = partes[:-1]
    if partes[0] == "src":
        partes = partes[1:]
    nomes = {".".join(partes[i:]) for i in range(len(partes))}
    return nomes, ".".join(partes if init else partes[:-1])


def com_os_pais(nome):
    partes = nome.split(".")
    return {".".join(partes[: i + 1]) for i in range(len(partes))}


def absoluto(base, nivel, pacote):
    """O `from .x` resolvido contra o pacote de quem importa; vazio se sobe além da raiz."""
    if not nivel:
        return base
    p = pacote.split(".") if pacote else []
    if nivel - 1 > len(p):
        return ""
    p = p[: len(p) - (nivel - 1)]
    return ".".join([*p, base] if base else p)


def do_texto(texto, pacote):
    """Todo import do texto, em qualquer profundidade: o do arquivo de teste e do ajudante."""
    saida = set()
    for m in LER.finditer(texto):
        for pedaco in m.group(1).split(","):
            nome = pedaco.split(" as ")[0].strip(" \t\\")
            if re.fullmatch(r"[\w.]+", nome):
                saida |= com_os_pais(nome)
    for m in DE.finditer(texto):
        base = m.group(1)
        nivel = len(base) - len(base.lstrip("."))
        base = absoluto(base.lstrip("."), nivel, pacote)
        if not base:
            continue
        saida |= com_os_pais(base)
        for pedaco in re.split(r"[,\n]", m.group(2)):
            nome = pedaco.split("#")[0].split(" as ")[0].strip(" \t\\()")
            if re.fullmatch(r"\w+", nome):
                saida.add(f"{base}.{nome}")
    for m in DINAMICO.finditer(texto):
        saida |= com_os_pais(m.group(1))
    return saida


def pede_o_webkit(no):
    if isinstance(no, ast.Call):
        f, a = no.func, no.args
        return (isinstance(f, ast.Attribute) and f.attr == "require_version" and bool(a)
                and isinstance(a[0], ast.Constant) and a[0].value == "WebKit2")
    if isinstance(no, ast.ImportFrom):
        return no.module == "gi.repository" and any(x.name == "WebKit2" for x in no.names)
    return isinstance(no, ast.Import) and any("WebKit2" in x.name for x in no.names)


def do_topo(arvore, pacote):
    """Os imports que rodam ao importar o módulo (fora de função), e se ele pede o WebKit."""
    saida, pede = set(), False
    pilha = list(arvore.body)
    while pilha:
        no = pilha.pop()
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(no, ast.If) and "TYPE_CHECKING" in ast.dump(no.test):
            pilha += no.orelse
            continue
        for campo in ("body", "orelse", "finalbody", "handlers", "cases"):
            pilha += getattr(no, campo, None) or []
        pede = pede or pede_o_webkit(no) or (
            isinstance(no, ast.Expr) and pede_o_webkit(no.value))
        if isinstance(no, ast.Import):
            for a in no.names:
                saida |= com_os_pais(a.name)
        elif isinstance(no, ast.ImportFrom):
            base = absoluto(no.module or "", no.level, pacote)
            if base:
                saida |= com_os_pais(base)
                saida |= {f"{base}.{a.name}" for a in no.names if a.name != "*"}
    return saida, pede


def ler(rel):
    nomes, pacote = nomes_e_pacote(rel)
    try:
        with open(rel, encoding="utf-8") as fh:
            texto = fh.read()
    except (OSError, ValueError):
        return nomes, set(), rel.startswith("tests/")
    if rel.startswith("tests/"):
        return nomes, do_texto(texto, pacote), "WebKit2" in texto
    try:
        return (nomes, *do_topo(ast.parse(texto, rel), pacote))
    except (SyntaxError, ValueError):
        return nomes, set(), False


lidos = {rel: ler(rel) for rel in [*arquivos("src"), *arquivos("scripts"),
                                     *arquivos("tests/unit", raso=True)]
           if not rel.endswith("/conftest.py")}
with open(lista, encoding="utf-8") as fh:
    pedidos = [linha.strip() for linha in fh if linha.strip()]
for rel in pedidos:
    if rel not in lidos:
        lidos[rel] = ler(rel)
do_webkit, nomes_do_webkit = set(), set()
mudou = True
while mudou:
    mudou = False
    for rel, (nomes, importa, pede) in lidos.items():
        if rel not in do_webkit and (pede or importa & nomes_do_webkit):
            do_webkit.add(rel)
            nomes_do_webkit |= nomes
            mudou = True
print("\n".join(rel for rel in pedidos if rel in do_webkit))
PY
# A lista do WebKit é lida UMA vez por corrida; o filho da chave PARTES_EM_PARALELO lê a do pai.
# O fecho só usa a biblioteca padrão e roda no `python3` do sistema: o `PY` é o do pytest, e uma
# régua pode passar um de mentira, que não lê nada.
_py_do_fecho="$(command -v python3 || printf '%s' "$PY")"
if [ -z "${PARTIDO:-}" ] || [ ! -f "$SAIDA/do-webkit.txt" ]; then
  "$_py_do_fecho" -c "$FECHO_DO_WEBKIT" "$RAIZ" "$SAIDA/todos.txt" > "$SAIDA/do-webkit.txt" \
    || { echo "ERRO: não consegui ler quem carrega o WebKit ($_py_do_fecho rodou o FECHO_DO_WEBKIT com erro)."; exit 2; }
fi
declare -A _do_webkit=()
while IFS= read -r a; do [ -z "$a" ] || _do_webkit[$a]=1; done < "$SAIDA/do-webkit.txt"
e_do_webkit() { [ -n "${_do_webkit[$1]:-}" ]; }
# `LISTAR_O_WEBKIT=1` só diz quem roda em processo próprio, e sai: é a
# pergunta que a régua faz a este script sobre a árvore de verdade.
if [ -n "${LISTAR_O_WEBKIT:-}" ]; then
  while IFS= read -r a; do e_do_webkit "$a" && printf '%s\n' "$a"; done < "$SAIDA/todos.txt"
  exit 0
fi

if [ -n "$LOTE" ]; then
  echo "lote — $total arquivos de $LOTE (o WebKit em processo próprio, como na suíte)"
else
  echo "suíte — $total arquivos em $PARTES partes"
  # A MARCA DA CORRIDA (O-TEMPO-DA-SUITE-SO-SOMA-UMA-CORRIDA-01, 23/10/2026): a árvore do índice, o número
  # de arquivos e o hash da partição. O fecho roda cada parte numa chamada e guarda o recibo da verde, e a
  # pasta dele juntou partes de quatro corridas, com partições diferentes; o `o-tempo-da-casa.py` só soma
  # as partes se as marcas batem. Dez caracteres, não doze: doze hex a casa lê como endereço de rádio.
  _tree=""
  _idx=$(git -C "$RAIZ" rev-parse --path-format=absolute --git-path index 2> /dev/null || true)
  if [ -n "$_idx" ] && [ -f "$_idx" ]; then
    _copia=$(mktemp "${TMPDIR:-/tmp}/suite-idx-XXXXXX")
    cp "$_idx" "$_copia" && _tree=$(GIT_INDEX_FILE="$_copia" git -C "$RAIZ" write-tree 2> /dev/null || true)
    rm -f "$_copia"
  fi
  [ -n "$_tree" ] || _tree=$(git -C "$RAIZ" rev-parse 'HEAD^{tree}' 2> /dev/null || echo sem-git)
  _partes_md5=$(for ((k = 0; k < PARTES; k++)); do
    printf '== %02d\n' "$k"; cat "$(printf '%s/parte-%02d' "$SAIDA" "$k")" 2> /dev/null
  done | md5sum | cut -c1-10)
  echo "        corrida árvore=${_tree:0:10} arquivos=$total partição=$_partes_md5"
  unset _tree _idx _copia _partes_md5
fi
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
# recibo: com uma parte só, com um lote, ou com argumentos a mais (um `-k` ou um
# `--deselect` encolhem a suíte sem mudar o nome dela), não há recibo.
recibo_da_corrida=""
if [ -z "$LOTE" ] && [ -z "$so_esta" ] && [ ${#extra[@]} -eq 0 ]; then
  recibo_da_corrida="$SAIDA/recibo-da-corrida.json"
  "$PY" "$RAIZ/scripts/recibo_da_medida.py" abrir suite \
    --raiz "$RAIZ" --corrida "$recibo_da_corrida" || true
  echo
elif [ -n "$LOTE" ]; then
  echo "recibo: um lote não deixa recibo — ele não é a suíte"
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
# A CHAVE: as partes em filhos, N a N, cada um numa vaga do semáforo. O filho é este mesmo script com
# a parte pedida (e por isso sem recibo); a saída de cada um fica em `paralelo-NN.*` e sai aqui, na
# ordem das partes, quando todos voltam. DUAS FILAS, UMA FRENTE CADA: a das partes que tocam a máquina
# corre uma de cada vez (nunca duas ao mesmo tempo), e a das leves enche as vagas que sobram. Com as
# três vagas, a parede é a da fila das que tocam, ou a das leves dividida pelas vagas que restam,
# a maior das duas; a soma das duas seria a corrida em série.
if [ "$PARTES_EM_PARALELO" -gt 0 ] 2> /dev/null && [ -z "$so_esta" ]; then
  marca=$(mktemp "$SAIDA/marca.XXXXXX")
  fila_toca=()
  fila_leve=()
  for n in "${partes_desta_divisao[@]}"; do
    f="$SAIDA/parte-$n"
    [ -s "$f" ] || continue
    feitas="$feitas$n "
    if grep -qxFf "$SAIDA/toca-a-maquina.txt" "$f"; then fila_toca+=("$n"); else fila_leve+=("$n"); fi
  done
  declare -A pid_de=() toca_de=()
  em_voo=0
  toca_voando=0
  # O filho da parte LEVE nasce com lar, TMPDIR, D-Bus e Xvfb próprios (como cada pytest do
  # `portoes.sh`); o da parte que toca a máquina nasce no ambiente de quem chama.
  lancar_filho() {  # $1 = a parte, $2 = 1 se toca a máquina
    local n="$1" toca="$2" lar prefixo=()
    (
      export PARTIDO=1 PARTES_EM_PARALELO=0 SAIDA PY
      comando=(bash "$0" "$n")
      if [ "$toca" = 0 ]; then
        lar=$(mktemp -d "${TMPDIR:-/tmp}/suite-lar-XXXXXX")
        mkdir -p "$lar"/{config,data,cache,state,runtime,tmp}
        chmod 700 "$lar/runtime"
        # O lar não tem portal (o `servicos_sem_portal`, no alto) nem sessão gráfica.
        servicos_sem_portal "$lar/data"
        command -v xvfb-run > /dev/null 2>&1 && prefixo=(xvfb-run -a)
        command -v dbus-run-session > /dev/null 2>&1 && prefixo=(dbus-run-session -- ${prefixo[@]+"${prefixo[@]}"})
        comando=(env HOME="$lar" XDG_CONFIG_HOME="$lar/config" XDG_DATA_HOME="$lar/data"
          XDG_CACHE_HOME="$lar/cache" XDG_STATE_HOME="$lar/state" XDG_RUNTIME_DIR="$lar/runtime"
          TMPDIR="$lar/tmp" XDG_CURRENT_DESKTOP= WAYLAND_DISPLAY= GIO_USE_VFS=local
          ${prefixo[@]+"${prefixo[@]}"} "${comando[@]}")
      fi
      # a vaga é a mais de fora: o Xvfb e o lar só nascem com a vaga na mão
      if [ "$VEZ_DO_PYTEST" != nenhum ]; then comando=(bash "$VEZ_DO_PYTEST" "${comando[@]}"); fi
      "${comando[@]}" > "$SAIDA/paralelo-$n.saida" 2>&1
      echo $? > "$SAIDA/paralelo-$n.rc"
      [ -z "${lar:-}" ] || rm -rf "$lar"
    ) &
    pid_de[$n]=$!
    toca_de[$n]=$toca
    em_voo=$((em_voo + 1))
    [ "$toca" = 0 ] || toca_voando=1
  }
  while [ ${#fila_toca[@]} -gt 0 ] || [ ${#fila_leve[@]} -gt 0 ] || [ "$em_voo" -gt 0 ]; do
    while [ "$em_voo" -lt "$PARTES_EM_PARALELO" ]; do
      if [ "$toca_voando" -eq 0 ] && [ ${#fila_toca[@]} -gt 0 ]; then
        lancar_filho "${fila_toca[0]}" 1
        fila_toca=("${fila_toca[@]:1}")
      elif [ ${#fila_leve[@]} -gt 0 ]; then
        lancar_filho "${fila_leve[0]}" 0
        fila_leve=("${fila_leve[@]:1}")
      else
        break
      fi
    done
    [ "$em_voo" -gt 0 ] || break
    # Quem acabou se confere pelo PID de cada filho, e não pelo que o `wait -n` diz: o filho que
    # acaba enquanto o pai espera outro processo some da conta do `wait -n` (medido no bash 5.2:
    # ele volta 127 com um filho a menos), e o `-p` só existe do bash 5.1 em diante. Sem a
    # conferência, o laço gira para sempre com uma vaga que nunca volta.
    wait -n 2> /dev/null || true
    acabou=0
    for n in "${!pid_de[@]}"; do
      ! kill -0 "${pid_de[$n]}" 2> /dev/null || continue
      [ "${toca_de[$n]}" = 0 ] || toca_voando=0
      unset "pid_de[$n]"
      em_voo=$((em_voo - 1))
      acabou=1
    done
    [ "$acabou" = 1 ] || sleep 0.2
  done
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
