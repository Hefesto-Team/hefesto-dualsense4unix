#!/bin/sh
# hefesto-launch — wrapper de Opções de Inicialização da Steam (DEDUP-04).
#
# Instalado pelo passo de USUÁRIO do install.sh (sem sudo, sem flag) em:
#   ~/.local/share/hefesto-dualsense4unix/bin/hefesto-launch
#
# Na Steam a string é CONSTANTE (o botão "Copiar opções p/ jogos" gera):
#   sh -c '...' hefesto-launch %command%
# e ela mesma degrada quando este arquivo faltar. O wrapper roda no HOST,
# ANTES do container do Steam Linux Runtime (launch options embrulham o
# %command% inteiro — é assim que mangohud funciona), então:
#   - o env herdado carrega LD_LIBRARY_PATH/LD_PRELOAD do runtime scout:
#     os helpers do host (python3 do probe IPC) rodam com essas vars limpas,
#     preservando o env original no exec do jogo;
#   - o exec final é `exec env "$@"` (NUNCA `exec "$@"`): LaunchOptions
#     pré-existentes no formato `VAR=VAL %command%` viram $1 e o env(1) as
#     processa como assignment — `exec "$@"` tentaria EXECUTÁ-las (ENOENT).
#
# Decisão das envs (fail-safe por construção — o jogo SEMPRE abre; o controle,
# ver a nota do item 4):
#   1. $SteamAppId ausente/0 (atalho não-Steam) ................ nenhuma env
#   2. arquivo materializado ausente ........................... nenhuma env
#   3. gate de vida: connect()+ping JSON-RPC no socket de PRODUÇÃO por nome
#      EXATO (nunca glob — o socket FAKE mora no mesmo diretório; arquivo de
#      socket sobrevive a crash, então "o arquivo existe" NÃO é gate) —
#      daemon morto/stale/timeout ............................. nenhuma env
#   4. daemon vivo => exporta SÓ as envs da allowlist lidas do arquivo que o
#      daemon regrava a cada transição. NOTA DATADA — TROCA-DENTRO-DO-JOGO-01,
#      14/09/2026: aqui dizia "qualquer vpad degradado => o arquivo já vem SEM o
#      IGNORE". A regra agora é a decisão dela
#      (D-1409-FORA-DO-NATIVO-O-JOGO-VE-SO-O-VIRTUAL): fora do Modo Nativo o
#      arquivo esconde o DualSense de plástico, em qualquer canal, e o que ainda
#      derruba o IGNORE é a COBERTURA — um vpad por físico. O "nunca zero
#      controles" acima vale para o Modo Nativo e para a mesa sem cobertura; na
#      Navegação, o jogo fica sem gamepad até ela subir um modo, e isso é
#      escolha dela.
#
# Allowlist ESPELHADA em src/hefesto_dualsense4unix/daemon/launch_env.py.

set -u

decide_envs() {
    # Imprime no stdout uma linha VAR=VAL por env aprovada. Qualquer falha
    # (return sem imprimir) significa "nenhuma env nossa".
    appid="${SteamAppId:-}"
    case "$appid" in
        ''|0) return 0 ;;
        *[!0-9]*) return 0 ;;
    esac

    state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/hefesto-dualsense4unix/launch_env"
    envfile="$state_dir/steam_app_${appid}.env"
    [ -f "$envfile" ] || envfile="$state_dir/default.env"
    [ -f "$envfile" ] || return 0

    command -v python3 >/dev/null 2>&1 || return 0

    runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    sock="$runtime/hefesto-dualsense4unix/hefesto-dualsense4unix.sock"
    [ -S "$sock" ] || return 0

    # Gate de vida com timeout CURTO (1 s) para não atrasar o launch. As
    # vars do loader ficam limpas SÓ para o helper (o env do jogo não muda).
    LD_LIBRARY_PATH= LD_PRELOAD= PYTHONPATH= PYTHONHOME= \
        python3 - "$sock" <<'PYEOF' >/dev/null 2>&1 || return 0
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(1.0)
s.connect(sys.argv[1])
s.sendall(
    json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "daemon.status", "params": {}}
    ).encode("utf-8")
    + b"\n"
)
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(4096)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
data = json.loads(buf.decode("utf-8"))
raise SystemExit(0 if isinstance(data, dict) and "result" in data else 1)
PYEOF

    # Daemon vivo: só a allowlist passa (arquivo adulterado não exporta LD_PRELOAD e afins).
    while IFS= read -r line; do
        case "$line" in
            SDL_GAMECONTROLLER_IGNORE_DEVICES=*) printf '%s\n' "$line" ;;
            SDL_JOYSTICK_HIDAPI=*)               printf '%s\n' "$line" ;;
            SDL_GAMECONTROLLER_USE_BUTTON_LABELS=*) printf '%s\n' "$line" ;;
            SDL_ACCELEROMETER_AS_JOYSTICK=*)     printf '%s\n' "$line" ;;
            PROTON_DISABLE_HIDRAW=*)             printf '%s\n' "$line" ;;
            __GL_SHADER_DISK_CACHE=*)            printf '%s\n' "$line" ;;
            __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=*) printf '%s\n' "$line" ;;
            PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE=*) printf '%s\n' "$line" ;;
            PROTON_ENABLE_MHWILDS_USB_AUDIO=*)   printf '%s\n' "$line" ;;
        esac
    done < "$envfile"
    return 0
}

record_last_run() {
    # Marker de execução (GUERRA-01 / honestidade do dedup): prova que o jogo
    # PASSOU pelo wrapper — o daemon compara com a janela steam_app detectada
    # e expõe `wrapper_used` no state_full (o `dedup_ok` sozinho é
    # falso-tranquilizante: nunca checa se o jogo herdou a env).
    #
    # Arquivo: $XDG_STATE_HOME/hefesto-dualsense4unix/launch_env/last_run
    # Formato (chave=valor, uma por linha; consumido pelo daemon):
    #   appid=<SteamAppId numérico do launch>
    #   epoch=<unix epoch em segundos do launch>
    #   pid=<PID deste wrapper — NUMA-01>
    #
    # NUMA-01: `pid=$$` é o PID DESTE processo. Como o `exec env "$@"` final
    # PRESERVA o PID (o wrapper VIRA o jogo — mesmo truque do Game Mode
    # abaixo), este é o pid do próprio jogo enquanto ele roda; o daemon soma
    # `kill(pid, 0)` a este marker para saber se o launch ainda está vivo
    # (evidência "jogo real ativo" — game_signal.wrapper_game_running). Campo
    # NOVO e opcional: `read_last_run_marker` do daemon o ignora (compat com
    # markers antigos sem o campo).
    #
    # Best-effort de ponta a ponta: gravado ANTES do gate de vida (o marker
    # atesta o wrapper, não o daemon) e NENHUMA falha aqui pode atrasar ou
    # derrubar o launch. Escrita via tmp+mv para o daemon nunca ler metade.
    lr_appid="${SteamAppId:-}"
    case "$lr_appid" in
        ''|0) return 0 ;;
        *[!0-9]*) return 0 ;;
    esac
    lr_dir="${XDG_STATE_HOME:-$HOME/.local/state}/hefesto-dualsense4unix/launch_env"
    mkdir -p "$lr_dir" 2>/dev/null || return 0
    {
        printf 'appid=%s\n' "$lr_appid"
        printf 'epoch=%s\n' "$(date +%s)"
        printf 'pid=%s\n' "$$"
    } > "$lr_dir/last_run.tmp" 2>/dev/null || return 0
    mv -f "$lr_dir/last_run.tmp" "$lr_dir/last_run" 2>/dev/null || true
    return 0
}

record_last_exit() {
    # Marker de encerramento (NUMA-01): epoch de uma saída deste wrapper SEM
    # `exec` bem-sucedido — encurta na prática a janela de "pid reuse" do
    # `last_run` (um `last_exit` mais novo que o `last_run` do MESMO launch
    # prova que aquele processo nunca virou o jogo). Só dispara via o
    # handler de EXIT (`_hefesto_on_exit`, abaixo): o `exec` bem-sucedido
    # SUBSTITUI este processo pelo jogo — não há trap de shell para disparar
    # depois disso, e é exatamente por isso que a detecção de "jogo ainda
    # rodando" do NUMA-01 usa `pid_alive`, não este marker.
    #
    # Arquivo: $XDG_STATE_HOME/hefesto-dualsense4unix/launch_env/last_exit
    # Formato (chave=valor, uma por linha):
    #   epoch=<unix epoch em segundos>
    #   pid=<PID deste wrapper>
    #
    # Correção pós-auditoria da Onda N: `last_run`/`last_exit` são arquivos
    # GLOBAIS (não por appid/sessão) — sem o `pid=$$` aqui (o MESMO `$$` que
    # este processo já gravou no seu PRÓPRIO `last_run`, ANTES do `exec`
    # falhar), o daemon não tem como saber se um `last_exit` mais novo
    # pertence ao launch que está avaliando ou a outro concorrente que só
    # perdeu a corrida de escrita destes dois arquivos (o achado: launch A
    # falha o exec e grava `last_exit` tarde, DEPOIS de um launch B legítimo
    # já ter sobrescrito o `last_run` — sem correlação por pid, A invalidava
    # B com o jogo de B genuinamente rodando). `read_last_exit_pid` do
    # daemon ignora o campo em markers antigos sem ele (compat).
    #
    # Best-effort ABSOLUTO (mesma disciplina do `record_last_run`): nunca
    # atrasa nem derruba a saída, mesmo com o diretório ilegível.
    le_dir="${XDG_STATE_HOME:-$HOME/.local/state}/hefesto-dualsense4unix/launch_env"
    mkdir -p "$le_dir" 2>/dev/null || return 0
    {
        printf 'epoch=%s\n' "$(date +%s)"
        printf 'pid=%s\n' "$$"
    } > "$le_dir/last_exit.tmp" 2>/dev/null || return 0
    mv -f "$le_dir/last_exit.tmp" "$le_dir/last_exit" 2>/dev/null || true
    return 0
}

registrar_audio_ks() {
    # O rastro do curador do device KS (INSTALL-UNIVERSAL, 18/09/2026). A
    # saída do curador vai para /dev/null — é o jogo que está abrindo —, e sem
    # este arquivo a vibração que não chegou numa máquina de outra pessoa não
    # deixava sinal nenhum: nem o doctor nem o daemon olhavam o curador.
    #
    # Arquivo: $XDG_STATE_HOME/hefesto-dualsense4unix/launch_env/audio_ks_ultimo
    # Formato (chave=valor, uma por linha; lido pelo `doctor.sh`):
    #   appid=<SteamAppId, só dígitos>   epoch=<unix epoch do lançamento>
    #   rc=<saída do curador>            tentativas=<quantas vezes rodou>
    #   motivo=ok | ocupado | erro | sem-registro | desligado | sem-curador
    #
    # Mesma disciplina do `record_last_run`: best-effort ABSOLUTO, e tmp+mv
    # para o leitor nunca pegar metade. O tmp leva o PID porque dois jogos
    # abrindo juntos escreveriam o MESMO tmp.
    ra_appid="${SteamAppId:-}"
    case "$ra_appid" in
        *[!0-9]*) ra_appid="" ;;
    esac
    ra_dir="${XDG_STATE_HOME:-$HOME/.local/state}/hefesto-dualsense4unix/launch_env"
    mkdir -p "$ra_dir" 2>/dev/null || return 0
    {
        printf 'appid=%s\n' "$ra_appid"
        printf 'epoch=%s\n' "$(date +%s 2>/dev/null)"
        printf 'rc=%s\n' "$1"
        printf 'motivo=%s\n' "$2"
        printf 'tentativas=%s\n' "$3"
    } > "$ra_dir/audio_ks_ultimo.$$" 2>/dev/null || return 0
    mv -f "$ra_dir/audio_ks_ultimo.$$" "$ra_dir/audio_ks_ultimo" 2>/dev/null || true
    return 0
}

# NUMA-01: handler ÚNICO de trap EXIT deste wrapper. Combina o restaurador
# de Game Mode (só ativo se `enter_game_mode` alterou o perfil — guardado
# pela variável `hefesto_gm_prev`, setada ABAIXO em vez de `enter_game_mode`
# armar seu PRÓPRIO trap) com `record_last_exit`. Registrado UMA vez, cedo,
# para cobrir qualquer saída sem `exec` (binário `env` ausente, erro de
# shell) — o `exec env "$@"` bem-sucedido DESCARTA este trap por completo
# (o processo virou outro programa; é o comportamento documentado do Game
# Mode abaixo, preservado aqui).
hefesto_gm_prev=""

_hefesto_on_exit() {
    [ -n "$hefesto_gm_prev" ] && gm_set_profile "$hefesto_gm_prev" 2>/dev/null
    record_last_exit
    return 0
}
trap '_hefesto_on_exit' EXIT

# --- Game Mode COSMIC (PLAT-05) ---------------------------------------------
# Pede Performance ao system76-power na largada do jogo e devolve o perfil
# anterior quando ele terminar. Best-effort ABSOLUTO: sem system76-power =>
# no-op silencioso; qualquer falha (D-Bus mudo, timeout) NUNCA atrasa o launch
# além de ~2 s por chamada nem impede o jogo de abrir.
#
# Detecção (nesta ordem): binário system76-power (o cliente oficial — mesma
# package do daemon) > busctl > dbus-send. A interface D-Bus REAL
# (introspecção ao vivo 2026-07-18) NÃO tem SetProfile: os setters são os
# métodos Performance/Balanced/Battery (sem argumento) e o getter é
# GetProfile — codificado contra o que existe, não contra o esperado.
#
# Restauração: o `exec env` final PRESERVA o PID (o wrapper VIRA o jogo),
# então o trap de EXIT do sh morre no exec — quem restaura é um filho em
# background que espera este PID sumir. O handler único `_hefesto_on_exit`
# (topo do script, NUMA-01) fica mesmo assim: cobre a saída SEM exec (ex.:
# env(1) ausente). Restaurar duas vezes é inócuo.
# Se quem lança matar o grupo de processos inteiro no fim, a restauração se
# perde — best-effort documentado, nunca pior que não ter Game Mode.
#
# HEFESTO_GM_POLL_SECS: período do poll do restaurador (default 2 s);
# override existe para os testes não esperarem segundos reais.

GM_BUS_DEST="com.system76.PowerDaemon"
GM_BUS_PATH="/com/system76/PowerDaemon"

gm_have_transport() {
    # Alguém para conversar? Sem transporte, o Game Mode inteiro é no-op —
    # e nenhum sed/head roda à toa (ambientes mínimos não têm nem eles).
    command -v system76-power >/dev/null 2>&1 && return 0
    command -v busctl >/dev/null 2>&1 && return 0
    command -v dbus-send >/dev/null 2>&1
}

gm_run() {
    # Timeout curto (2 s) quando timeout(1) existir; sem ele, roda direto.
    if command -v timeout >/dev/null 2>&1; then
        timeout 2 "$@" 2>/dev/null
    else
        "$@" 2>/dev/null
    fi
}

gm_current_profile() {
    # Imprime o perfil atual em minúsculas (performance/balanced/battery)
    # ou nada quando não dá para perguntar.
    if command -v system76-power >/dev/null 2>&1; then
        gm_run system76-power profile \
            | sed -n 's/^Power Profile:[[:space:]]*//p'
    elif command -v busctl >/dev/null 2>&1; then
        gm_run busctl --system call \
            "$GM_BUS_DEST" "$GM_BUS_PATH" "$GM_BUS_DEST" GetProfile \
            | sed -n 's/^s[[:space:]]*"\(.*\)"$/\1/p'
    elif command -v dbus-send >/dev/null 2>&1; then
        gm_run dbus-send --system --print-reply --dest="$GM_BUS_DEST" \
            "$GM_BUS_PATH" "$GM_BUS_DEST.GetProfile" \
            | sed -n 's/.*string "\(.*\)".*/\1/p'
    fi | head -n 1 | tr '[:upper:]' '[:lower:]'
}

gm_set_profile() {
    # $1 SEMPRE validado antes: battery|balanced|performance (minúsculas).
    # Saída inesperada do daemon nunca vira comando (case fechado).
    case "$1" in
        battery) gm_method="Battery" ;;
        balanced) gm_method="Balanced" ;;
        performance) gm_method="Performance" ;;
        *) return 1 ;;
    esac
    if command -v system76-power >/dev/null 2>&1; then
        gm_run system76-power profile "$1" >/dev/null
    elif command -v busctl >/dev/null 2>&1; then
        gm_run busctl --system call \
            "$GM_BUS_DEST" "$GM_BUS_PATH" "$GM_BUS_DEST" "$gm_method" \
            >/dev/null
    elif command -v dbus-send >/dev/null 2>&1; then
        gm_run dbus-send --system --print-reply --dest="$GM_BUS_DEST" \
            "$GM_BUS_PATH" "$GM_BUS_DEST.$gm_method" >/dev/null
    else
        return 1
    fi
}

enter_game_mode() {
    gm_have_transport || return 0
    gm_prev="$(gm_current_profile)" || gm_prev=""
    case "$gm_prev" in
        battery|balanced) ;;
        *) return 0 ;;  # vazio, performance ou desconhecido: nada a fazer
    esac
    gm_set_profile performance || return 0
    # NUMA-01: em vez de armar o PRÓPRIO trap (que substituiria o handler
    # único `_hefesto_on_exit` registrado no topo do script, perdendo o
    # `record_last_exit`), só marca a variável que ele consulta. Cobre só a
    # saída SEM exec (exec bem-sucedido descarta o trap inteiro).
    hefesto_gm_prev="$gm_prev"
    gm_pid=$$
    (
        # Restaurador: espera o PID do jogo (o mesmo deste wrapper, via
        # exec) sumir e devolve o perfil anterior. FDs fechados para nunca
        # segurar o pipe de stdout do jogo aberto (Steam esperaria).
        gm_poll="${HEFESTO_GM_POLL_SECS:-2}"
        while kill -0 "$gm_pid" 2>/dev/null; do
            sleep "$gm_poll" || break
        done
        gm_set_profile "$gm_prev"
    ) </dev/null >/dev/null 2>&1 &
    return 0
}

# --- Camadas Vulkan que engasgam o jogo (ENGASGO-VULKAN-01) -----------------
# Uma camada Vulkan IMPLÍCITA registrada dentro do prefixo Wine embrulha a
# chamada de apresentação de cada quadro. Medido em 23/08/2026 no Sackboy dela:
# 60 fps de média perfeita e ~70 quadros longos por minuto (47 a 91 ms), num
# metrônomo de 1,021 s solto do relógio de parede — e de 27 prefixos, o único
# com camada a mais era o único que engasgava.
#
# Por que AQUI e não por variável de ambiente: camada Vulkan é lida de DENTRO do
# prefixo, e é lá que ela tem de ser desarmada. Medido nesta mesma madrugada —
# `MANGOHUD=1` exportado por este wrapper NÃO aparece no `environ` do processo
# do jogo; só funciona quando a Steam INTEIRA nasce com a variável.
#
# CORREÇÃO 23/08/2026: este comentário dizia que o pressure-vessel "FILTRA o
# ambiente" e que "cura por env não serve". Generalização falsa, tirada de UMA
# variável. As envs do dedup logo acima (SDL_GAMECONTROLLER_IGNORE_DEVICES,
# PROTON_DISABLE_HIDRAW) atravessam e funcionam — se não atravessassem, o jogo
# não leria os vpads. O defeito real continua sendo o que a linha 66 já declara:
# ninguém confere se o jogo HERDOU a env.
#
# Por que no gancho e não só num botão: regra dela de 14/08/2026 — *receita por
# appid deixa todo jogo novo desprotegido*. O botão conserta os prefixos de
# hoje; isto aqui pega o jogo que ela instalar amanhã, no primeiro lançamento.
#
# CUSTO MEDIDO (23/08/2026, na máquina dela, os 28 `system.reg` REAIS dos dois
# discos — três repetições por prefixo, não uma amostra):
#   - portão em TODO lançamento: média de 2,1 ms (2 ms no maior, de 5,4 MB;
#     1 ms num de 4,1 MB). 27 dos 28 param aqui e nunca chamam o python3;
#   - só quando há camada LIGADA para desligar, o curador em python3, UMA vez:
#     ~120 ms de trabalho no registro de 5,4 MB do Sackboy — 44 ms de leitura e
#     ~75 ms de escrita mais o backup —, e de 0,13 a 0,6 s de ponta a ponta
#     contando o interpretador e a variação do disco;
#   - DEPOIS de curado o portão passa batido (medido no mesmo registro): o
#     lançamento seguinte volta aos 2 ms.
#
# À PROVA DE FALHA, como o `enter_game_mode || true` logo abaixo: sem
# STEAM_COMPAT_DATA_PATH (jogo nativo, sem prefixo) não há nada a fazer; sem o
# curador instalado, sem python3, ou com qualquer erro, o jogo abre igual.
curar_camadas_vulkan() {
    prefixo="${STEAM_COMPAT_DATA_PATH:-}"
    [ -n "$prefixo" ] || return 0
    reg="$prefixo/pfx/system.reg"
    [ -f "$reg" ] || return 0

    # Portão barato E PRECISO, numa varredura só. `dword:00000000` significa
    # camada LIGADA (o número é a flag de DESABILITAR, zero = não desabilite),
    # então só há trabalho quando existe entrada em zero DENTRO da seção de
    # camadas implícitas. `-F` porque o alvo tem barras invertidas literais —
    # `Vulkan\\ImplicitLayers` é como o registro do Wine as escreve.
    #
    # Sem o portão preciso, todo lançamento de um prefixo JÁ CURADO pagava de
    # novo os 0,1 a 0,6 s do interpretador mais a leitura do registro inteiro
    # (medido). Com ele: 2 ms, e o python3 só roda quando há o que desligar.
    #
    # O resultado do grep entra numa VARIÁVEL, não num pipe para `grep -q`:
    # CORRIDA-DO-PIPEFAIL-01 (13/08/2026) — `grep -q` sai no primeiro
    # casamento, o produtor morre de SIGPIPE, e o status do pipe passa a
    # depender de quem ganhou a corrida.
    #
    # `-A 20` pode transbordar para a seção seguinte e disparar o python3 à
    # toa. É o lado seguro de errar: o curador refaz a conta direito e não
    # mexe em nada; um portão apertado demais é que perderia a cura.
    cv_secao="$(grep -FA 20 'Vulkan\\ImplicitLayers' "$reg" 2>/dev/null)" || cv_secao=""
    case "$cv_secao" in
        *"=dword:00000000"*) ;;
        *) return 0 ;;
    esac

    curador="$HOME/.local/share/hefesto-dualsense4unix/bin/hefesto-camadas"
    [ -x "$curador" ] || return 0
    command -v python3 >/dev/null 2>&1 || return 0

    # Teto de tempo: nem um prefixo patológico pode segurar o launch. Sem
    # timeout(1) roda direto — o curador é stdlib e só lê/escreve um arquivo.
    if command -v timeout >/dev/null 2>&1; then
        cv_run="timeout 10"
    else
        cv_run=""
    fi
    # As vars do loader ficam limpas SÓ para o helper (mesmo cuidado do gate de
    # vida em `decide_envs`): o env do jogo não muda.
    LD_LIBRARY_PATH= LD_PRELOAD= PYTHONPATH= PYTHONHOME= \
        $cv_run python3 "$curador" --prefixo "$prefixo" \
        --appid "${SteamAppId:-}" >/dev/null 2>&1
    return 0
}

# HAPTICA-NATIVA-01 (17/09/2026) — a vibração da Sony, que viaja como ÁUDIO.
#
# O PRAGMATA acha o alvo da vibração perguntando ao `setupapi` por um device
# `KSCATEGORY_AUDIO` com o mesmo ContainerId do alto-falante do controle. O
# GE-Proton não cria esse device para o DualSense; o curador
# `hefesto-audio-ks` o grava no `system.reg` do prefixo, antes do `wineserver`
# subir. Vibrou na mão dela, com o físico direto e em modo produto.
#
# Há DualSense no CABO, com placa de som? Por Bluetooth não há placa de áudio,
# e sem o controle a opção do MHWilds só expõe KS falso de headset USB — a
# classe de defeito que quebrou o Black Desert Online no GE. Raiz injetável
# (`HEFESTO_SYSFS`) para a suíte nunca ler o controle dela.
#
# SÓ SHELL PURO, sem `cat` nem `sed`: medido na suíte, com um PATH mínimo a
# troca por `sed` devolvia VAZIO e o jogo perdia TODAS as variáveis, não só
# esta. Um passo novo do wrapper nunca pode custar as envs que já funcionavam.
dualsense_no_cabo() {
    for d in "${HEFESTO_SYSFS:-/sys}"/bus/usb/devices/*; do
        [ -r "$d/idVendor" ] && [ -r "$d/idProduct" ] || continue
        IFS= read -r ks_vid 2>/dev/null <"$d/idVendor" || continue
        [ "$ks_vid" = "054c" ] || continue
        IFS= read -r ks_pid 2>/dev/null <"$d/idProduct" || continue
        case "$ks_pid" in
            0ce6|0df2) ;;
            *) continue ;;
        esac
        for s in "$d"/*/sound/card*; do
            [ -e "$s" ] && return 0
        done
    done
    return 1
}

# O device KS é refeito A CADA LANÇAMENTO: o DEVNUM muda a cada replug, e uma
# sessão sem a opção apaga os valores da chave. O curador só escreve quando algo
# mudou. Sem a opção ligada, só limpa o que for nosso (portão barato de 2 ms).
# À prova de falha, como a cura das camadas.
# O endpoint que o produto publica por controle NO RÁDIO (HAPTICA-POR-RADIO-01).
# Pelo rádio o controle não tem placa de som, e quem publica o alto-falante do
# DualSense é um nó nosso do PipeWire — o nome dele carrega as agulhas que o GE
# procura (`Sony_Interactive_Entertainment`, `Speaker__sink`) e o marcador da
# casa. Sem `pactl` a resposta é "não há", como em toda sondagem desta casa.
endpoint_de_mentira_vivo() {
    command -v pactl >/dev/null 2>&1 || return 1
    pactl list short sinks 2>/dev/null \
        | grep -q 'Sony_Interactive_Entertainment.*HEFESTO.*Speaker__sink'
}

# O jogo acha a háptica por um endpoint de áudio, e não pergunta como o
# CONTROLE está ligado: no cabo o endpoint é a placa de som do DualSense; no
# rádio é o nó que nós publicamos. Para a opção do MHWilds, os dois valem — e a
# razão de ela existir é o Black Desert, que quebra quando o KS falso aparece
# SEM nenhum endpoint de DualSense por trás.
dualsense_com_endpoint() {
    dualsense_no_cabo || endpoint_de_mentira_vivo
}

curar_audio_ks() {
    prefixo="${STEAM_COMPAT_DATA_PATH:-}"
    [ -n "$prefixo" ] || return 0
    reg="$prefixo/pfx/system.reg"
    case "$hefesto_envs" in
        *PROTON_ENABLE_MHWILDS_USB_AUDIO=1*) ks_modo="" ;;
        *)
            # Sem a opção só há trabalho se houver bloco nosso a limpar.
            if [ ! -f "$reg" ] || ! grep -qF 'HEFESTOKS' "$reg" 2>/dev/null; then
                registrar_audio_ks 0 desligado 0
                return 0
            fi
            ks_modo="--remover"
            ;;
    esac
    # A PRIMEIRA SESSÃO DE TODO JOGO NOVO cai aqui: o proton cria o prefixo
    # (copy_pfx, que traz o system.reg) DENTRO do %command%, depois deste
    # wrapper. Não há cura barata — criar o prefixo antes do jogo pede medição
    # —, e a sessão deixa o registro no disco: o lançamento seguinte grava. O
    # que não pode é ficar calado, e o doctor lê este rastro.
    if [ ! -f "$reg" ]; then
        registrar_audio_ks 0 sem-registro 0
        return 0
    fi
    curador="$HOME/.local/share/hefesto-dualsense4unix/bin/hefesto-audio-ks"
    if [ ! -x "$curador" ]; then
        registrar_audio_ks 0 sem-curador 0
        return 0
    fi
    command -v python3 >/dev/null 2>&1 || return 0
    if command -v timeout >/dev/null 2>&1; then
        ks_run="timeout 10"
    else
        ks_run=""
    fi
    # O `ocupado` (saída 3) é o wineserver DESTE prefixo ainda vivo — o do
    # install script da Steam (redistribuíveis, EOS), ou o da sessão que acabou
    # de fechar. Esperar custa zero: o `proton waitforexitandrun` roda
    # `wineserver -w` sobre o MESMO servidor antes de abrir o jogo. Até cinco
    # novas tentativas, com o mesmo `sleep` do restaurador do Game Mode; sem
    # `sleep` no PATH, desiste na primeira (shell puro, nada novo é exigido).
    # HEFESTO_KS_ESPERA_SECS existe para a suíte não esperar segundos reais.
    ks_tentativas=1
    while :; do
        LD_LIBRARY_PATH= LD_PRELOAD= PYTHONPATH= PYTHONHOME= \
            $ks_run python3 "$curador" --prefixo "$prefixo" \
            --sysfs "${HEFESTO_SYSFS:-/sys}" $ks_modo >/dev/null 2>&1
        ks_rc=$?
        [ "$ks_rc" -eq 3 ] || break
        [ "$ks_tentativas" -le 5 ] || break
        sleep "${HEFESTO_KS_ESPERA_SECS:-1}" 2>/dev/null || break
        ks_tentativas=$((ks_tentativas + 1))
    done
    case "$ks_rc" in
        0) ks_motivo="ok" ;;
        3) ks_motivo="ocupado" ;;
        *) ks_motivo="erro" ;;
    esac
    registrar_audio_ks "$ks_rc" "$ks_motivo" "$ks_tentativas"
    return 0
}

# AMBIENTE-DO-JOGO-01 (18/09/2026) — o interpretador de quem abriu a Steam.
#
# Uma Steam aberta de um terminal com venv, conda ou pyenv ativo passa esse
# ambiente a todo jogo: medido em 17/09 no `environ` do PRAGMATA, com a venv
# na frente do SYSTEM_PATH. O `proton` é script Python
# (`#!/usr/bin/env python3`), e quem o roda passa a ser o python3 que o
# terminal escolheu. O produto já reabre a Steam limpa; esta é a ponta que
# cobre a Steam que a PESSOA abriu de um terminal, porque todo jogo passa por
# aqui.
#
# Podar só o PATH não chega ao `proton`, e o portador medido diz por quê: o
# `steam.sh` guarda o PATH com que a Steam subiu (`export SYSTEM_PATH="$PATH"`),
# e o jogo Proton roda dentro da Steam Linux Runtime, cujo
# `pressure-vessel-unruntime` faz `export PATH="$SYSTEM_PATH"` DEPOIS deste
# gancho e antes do `proton`. As duas listas de busca saem podadas.
#
# A lista é a do dono, `integrations/ambiente_do_jogo.py`, e a régua
# `test_ambiente_do_jogo_01_o_terminal_nao_vai_junto.py` confere as duas: os
# nomes, e a borda caso a caso contra o dono. Só o ambiente do exec muda: os
# ajudantes acima já limpam o que lhes importa. O que a pessoa escreve na
# Opção de Inicialização vem em "$@", DEPOIS disto, e o env(1) o aplica por
# cima — uma PYTHONPATH escrita por ela sobrevive.
#
# SÓ SHELL PURO, pelo mesmo motivo de `dualsense_no_cabo`: sem `sed` nem `tr`,
# e a lista se parte por expansão de parâmetro, sem glob. A poda devolve em
# `la_novo`. Uma entrada vazia fica onde estava; e se tirar os `bin/` deixasse
# a lista vazia, ela fica como veio (sem PATH não se acha nem o `sh` do jogo).
podar_bins_do_interpretador() {
    la_novo=""
    [ -n "$1" ] || return 0
    la_resto="$1:"
    la_primeiro=1
    while [ -n "$la_resto" ]; do
        la_dir="${la_resto%%:*}"
        la_resto="${la_resto#*:}"
        la_cmp="${la_dir%/}"
        if [ -n "$la_cmp" ]; then
            [ "$la_cmp" = "$la_bin_venv" ] && continue
            [ "$la_cmp" = "$la_bin_conda" ] && continue
        fi
        if [ "$la_primeiro" = 1 ]; then
            la_novo="$la_dir"
            la_primeiro=0
        else
            la_novo="$la_novo:$la_dir"
        fi
    done
    return 0
}

limpar_ambiente_do_interpretador() {
    la_bin_venv=""
    la_bin_conda=""
    la_base="${VIRTUAL_ENV:-}"
    la_base="${la_base%/}"
    [ -n "$la_base" ] && la_bin_venv="$la_base/bin"
    la_base="${CONDA_PREFIX:-}"
    la_base="${la_base%/}"
    [ -n "$la_base" ] && la_bin_conda="$la_base/bin"
    unset VIRTUAL_ENV CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_SHLVL PYTHONHOME PYTHONPATH PYENV_VERSION
    [ -n "$la_bin_venv$la_bin_conda" ] || return 0
    podar_bins_do_interpretador "${PATH:-}"
    [ -n "$la_novo" ] && PATH="$la_novo"
    podar_bins_do_interpretador "${SYSTEM_PATH:-}"
    [ -n "$la_novo" ] && export SYSTEM_PATH="$la_novo"
    return 0
}

record_last_run || true

hefesto_envs="$(decide_envs)" || hefesto_envs=""

# Sem endpoint de DualSense NENHUM — nem a placa de som do cabo, nem o nó do
# rádio —, a opção do MHWilds sai como "0" ESCRITO: omitir não desliga, porque o
# `proton` preenche do `user_settings.py` toda chave ausente. E ela precisa
# mesmo estar ligada: sem ela o `setupapi` não publica interface
# KSCATEGORY_AUDIO nenhuma (patch 0103, `devinst.c`), e o jogo desiste antes de
# olhar o registro.
case "$hefesto_envs" in
    *PROTON_ENABLE_MHWILDS_USB_AUDIO=1*)
        if ! dualsense_com_endpoint; then
            ks_envs=""
            while IFS= read -r kv; do
                case "$kv" in
                    PROTON_ENABLE_MHWILDS_USB_AUDIO=1) kv="PROTON_ENABLE_MHWILDS_USB_AUDIO=0" ;;
                esac
                ks_envs="${ks_envs}${kv}
"
            done <<HEFESTO_KS_EOF
$hefesto_envs
HEFESTO_KS_EOF
            hefesto_envs="$ks_envs"
        fi
        ;;
esac

if [ -n "$hefesto_envs" ]; then
    # Prependa cada VAR=VAL como argumento do env(1) — assignments precisam
    # vir antes do comando; a ordem entre eles é irrelevante. O heredoc NÃO
    # cria subshell (pipe criaria), então o `set --` sobrevive ao loop.
    while IFS= read -r kv; do
        [ -n "$kv" ] && set -- "$kv" "$@"
    done <<HEFESTO_EOF
$hefesto_envs
HEFESTO_EOF
fi

# Camada Vulkan que engasga (ENGASGO-VULKAN-01): antes do exec, porque o
# `wineserver` deste prefixo só sobe DEPOIS — e é ele quem lê o registro. À
# prova de falha, mesma disciplina do Game Mode.
curar_camadas_vulkan || true

# O device de áudio KS do DualSense (HAPTICA-NATIVA-01): também antes do exec,
# pelo mesmo motivo — o `wineserver` deste prefixo ainda não subiu.
curar_audio_ks || true

# Game Mode COSMIC (PLAT-05): DEPOIS das envs decididas, ANTES do exec — e à
# prova de falha: o jogo abre mesmo se nada disso funcionar.
enter_game_mode || true

# O último passo antes do exec (AMBIENTE-DO-JOGO-01): o jogo nasce sem o
# interpretador do terminal que abriu a Steam.
limpar_ambiente_do_interpretador || true

exec env "$@"
