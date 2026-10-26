#!/usr/bin/env bash
set -u
_ajuda() {
  cat <<'AJUDA'
ensaio-do-engasgo.sh — os ensaios do engasgo, jogados por quem joga
(O-ENGASGO-SE-CURA-PELO-QUE-CHEGA-AO-JOGO-01, §4).

  ensaio-do-engasgo.sh preparar <appid>     com a Steam FECHADA: põe o MangoHud
                                            por quadro, sem desenhar na tela, nas
                                            Opções de Inicialização do jogo
  ensaio-do-engasgo.sh volta <nome> <min>   abra o jogo, chegue à fase e rode
                                            isto; ao fim, feche o jogo
  ensaio-do-engasgo.sh resumo               uma linha por minuto de cada volta
  ensaio-do-engasgo.sh devolver             com a Steam FECHADA: devolve a opção
                                            de antes e confere
AJUDA
}

RAIZ=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
DONO=${HEFESTO_OPCOES_POR_JOGO:-$RAIZ/src/hefesto_dualsense4unix/integrations/opcoes_por_jogo.py}
PY=${HEFESTO_PY:-python3}
PASTA=${XDG_STATE_HOME:-$HOME/.local/state}/hefesto-dualsense4unix/ensaio-do-engasgo
ANTES=$PASTA/antes.json
QUADROS=$PASTA/mangohud

diz() { printf '%s %s\n' "$(date +%T)" "$*"; }
morre() { diz "RECUSO: $*" >&2; exit 2; }

py() {
    "$PY" - "$@" <<'PY'
import csv, json, re, sys, time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

NOME_DO_CSV = re.compile(r"_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.csv$")
HORA_DO_KERNEL = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})")
ato, args = sys.argv[1], sys.argv[2:]


def amostra() -> dict:
    vm = {}
    for linha in Path("/proc/vmstat").read_text().splitlines():
        k, v = linha.split()
        if k.startswith(("allocstall", "compact_stall", "compact_fail")):
            vm[k] = int(v)
    ordem = 0
    for linha in Path("/proc/buddyinfo").read_text().splitlines():
        ordem += sum(int(x) for x in linha.split()[4:][7:11])
    return {"ts": round(time.time(), 1), "vmstat": vm, "ordem_7_a_10": ordem}


def inicio(volta: Path) -> float:
    return datetime.strptime((volta / "inicio").read_text().strip(),
                             "%Y-%m-%d %H:%M:%S").timestamp()


def minuto(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def cabe(n: float, sim: bool) -> str:
    return str(int(n)) if sim else "-"


if ato == "amostrar":
    saida, fim = Path(args[0]), time.time() + float(args[1]) * 60
    with saida.open("a") as f:
        while True:
            f.write(json.dumps(amostra()) + "\n")
            f.flush()
            if time.time() >= fim:
                break
            time.sleep(min(10.0, max(0.0, fim - time.time())))

elif ato == "recolher":
    voltas = sorted((inicio(v), v) for v in Path(args[1]).glob("*") if (v / "inicio").exists())
    for c in sorted(Path(args[0]).glob("*.csv")):
        if c.name.endswith("_summary.csv"):
            continue
        antes = [v for t, v in voltas if t <= c.stat().st_mtime]
        if antes:
            c.rename(antes[-1] / c.name)

elif ato == "resumo":
    for volta in sorted(p for p in Path(args[0]).iterdir() if (p / "inicio").exists()):
        memoria = volta / "memoria.jsonl"
        amostras = [json.loads(x) for x in memoria.read_text().splitlines()
                    if x.strip()] if memoria.exists() else []
        comeco = inicio(volta)
        fim = amostras[-1]["ts"] if amostras else float("inf")
        linhas: dict = defaultdict(lambda: defaultdict(float))
        com_quadros: set = set()
        com_memoria: set = set()
        for c in sorted(volta.glob("*.csv")):
            achado = NOME_DO_CSV.search(c.name)
            if not achado:
                continue
            t0 = datetime.strptime(achado.group(1), "%Y-%m-%d_%H-%M-%S").timestamp()
            with c.open(newline="") as f:
                rows = list(csv.reader(f))
            cab = next((i for i, r in enumerate(rows) if r and r[0] == "fps"), None)
            if cab is None:
                continue
            col = {n: k for k, n in enumerate(rows[cab])}
            vistos: list = []
            for r in rows[cab + 2:]:
                try:
                    ms, ns = float(r[col["frametime"]]), float(r[col["elapsed"]])
                except (KeyError, ValueError, IndexError):
                    continue
                ts = t0 + ns / 1e9
                if not comeco <= ts <= fim:
                    continue
                vistos.append(ts)
                m = linhas[minuto(ts)]
                m["quadros"] += 1
                m[">33ms"] += ms > 33
                m[">50ms"] += ms > 50
            if vistos:
                passo = min(vistos)
                while passo <= max(vistos):
                    com_quadros.add(minuto(passo))
                    passo += 60
                com_quadros.add(minuto(max(vistos)))
        for a, b in zip(amostras, amostras[1:]):
            m = linhas[minuto(b["ts"])]
            com_memoria.add(minuto(b["ts"]))
            for chave in ("allocstall", "compact_stall"):
                m[chave] += sum(v - a["vmstat"].get(k, 0) for k, v in b["vmstat"].items()
                                if k.startswith(chave))
        for amostra_ in amostras:
            m = linhas[minuto(amostra_["ts"])]
            m["ordem"] = min(m.get("ordem", amostra_["ordem_7_a_10"]),
                             amostra_["ordem_7_a_10"])
        for chave_ in com_quadros:
            linhas[chave_]
        kernel = volta / "kernel.txt"
        sem_kernel = (volta / "kernel-sem-acesso").exists()
        for linha in kernel.read_text().splitlines() if kernel.exists() else []:
            achado = HORA_DO_KERNEL.match(linha)
            if achado:
                m = linhas[achado.group(1).replace("T", " ")]
                m["NVRM"] += "NVRM" in linha
                m["fila"] += "Output queue is full" in linha
        avisos = []
        if not com_quadros:
            avisos.append("sem quadros do MangoHud")
        if sem_kernel:
            avisos.append("sem acesso ao diário do kernel")
        print(f"== {volta.name}" + (f" ({'; '.join(avisos)})" if avisos else ""))
        for hora in sorted(linhas):
            m = linhas[hora]
            q, mem = hora in com_quadros, hora in com_memoria
            ordem = int(m["ordem"]) if "ordem" in m else "-"
            print(f"{hora[-5:]} quadros={cabe(m['quadros'], q)} "
                  f">33ms={cabe(m['>33ms'], q)} >50ms={cabe(m['>50ms'], q)} "
                  f"allocstall={cabe(m['allocstall'], mem)} "
                  f"compact_stall={cabe(m['compact_stall'], mem)} ordem7-10_min={ordem} "
                  f"NVRM={cabe(m['NVRM'], not sem_kernel)} "
                  f"fila_cheia={cabe(m['fila'], not sem_kernel)}")

elif ato == "guardar":
    Path(args[0]).write_text(json.dumps({"appid": args[1], "opção": args[2]}))

elif ato == "ler":
    print(json.loads(Path(args[0]).read_text())[args[1]])

elif ato == "opção":
    print(json.loads(args[1]).get(args[0], ""))
PY
}

opcao_de() {
    tabela=$("$PY" "$DONO" --json) || return 1
    py opção "$1" "$tabela"
}

aplicar() {
    "$PY" "$DONO" --aplicar
    rc=$?
    [ "$rc" = 3 ] && diz "a Steam está aberta: feche-a e rode de novo" >&2
    return "$rc"
}

devolver_a_tabela() {
    appid=$(py ler "$ANTES" appid)
    antes=$(py ler "$ANTES" opção)
    if [ -n "$antes" ]; then
        "$PY" "$DONO" --definir "$appid" "$antes" >/dev/null
    else
        "$PY" "$DONO" --tirar "$appid" >/dev/null
    fi
}

preparar() {
    appid=${1:-}
    case "$appid" in ''|*[!0-9]*) morre "diga o appid do jogo (só dígitos)" ;; esac
    [ ! -e "$ANTES" ] || morre "já há um ensaio preparado ($ANTES); rode o devolver antes"
    mkdir -p "$QUADROS" || morre "não consegui criar $QUADROS"
    antes=$(opcao_de "$appid") || morre "o dono das opções não respondeu"
    py guardar "$ANTES" "$appid" "$antes" || morre "não consegui guardar a opção de antes"
    miolo=${antes%%\%command\%*}
    miolo=${miolo%"${miolo##*[![:space:]]}"}
    mango="MANGOHUD=1 MANGOHUD_CONFIG=no_display=1,log_interval=0,autostart_log=1,log_duration=0,output_folder=$QUADROS"
    "$PY" "$DONO" --definir "$appid" "${miolo:+$miolo }$mango %command%" >/dev/null || {
        rm -f "$ANTES"; morre "o dono recusou a opção do ensaio"; }
    if ! aplicar; then
        devolver_a_tabela
        rm -f "$ANTES"
        morre "a opção do ensaio não chegou à Steam; a tabela voltou ao que era"
    fi
    diz "pronto: abra o jogo pela Steam; cada volta é um 'volta <nome> <minutos>'"
}

devolver() {
    [ -e "$ANTES" ] || morre "não há ensaio preparado"
    py recolher "$QUADROS" "$PASTA/voltas"
    devolver_a_tabela || morre "o dono não devolveu a opção"
    aplicar || morre "a opção de antes está na tabela, e a Steam ainda não a recebeu"
    appid=$(py ler "$ANTES" appid)
    antes=$(py ler "$ANTES" opção)
    agora=$(opcao_de "$appid")
    [ "$agora" = "$antes" ] || { diz "DIFERENTE: a opção do jogo é '$agora', e era '$antes'" >&2; exit 1; }
    rm -f "$ANTES"
    diz "devolvido e conferido: a opção do jogo $appid é a de antes"
}

volta() {
    nome=${1:-}
    minutos=${2:-10}
    case "$nome" in ''|*/*|.*) morre "diga o nome da volta (sem barra)" ;; esac
    case "$minutos" in ''|*[!0-9.]*) morre "diga os minutos da volta" ;; esac
    [ -e "$ANTES" ] || morre "rode o preparar antes"
    d=$PASTA/voltas/$nome
    [ ! -e "$d" ] || morre "a volta '$nome' já existe"
    py recolher "$QUADROS" "$PASTA/voltas"
    mkdir -p "$d" || morre "não consegui criar $d"
    inicio=$(date '+%Y-%m-%d %H:%M:%S')
    printf '%s\n' "$inicio" > "$d/inicio"
    diz "volta $nome: $minutos min, de 10 em 10 s"
    py amostrar "$d/memoria.jsonl" "$minutos"
    if [ -z "$(journalctl -k -n 5 -q --no-pager 2>/dev/null)" ]; then
        : > "$d/kernel-sem-acesso"
    fi
    journalctl -k -o short-iso --since "$inicio" --no-pager 2>/dev/null \
        | grep -E 'NVRM|Output queue is full' > "$d/kernel.txt"
    diz "volta $nome fechada: feche o jogo e reabra para a próxima"
}

resumo() {
    [ -d "$PASTA/voltas" ] || morre "não há volta gravada"
    py recolher "$QUADROS" "$PASTA/voltas"
    py resumo "$PASTA/voltas"
}

case "${1:-}" in
    preparar) shift; preparar "$@" ;;
    volta) shift; volta "$@" ;;
    resumo) resumo ;;
    devolver) devolver ;;
    *) _ajuda; exit 2 ;;
esac
