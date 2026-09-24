#!/usr/bin/env bash
# storm_watch.sh — kernel-watch: vigia do ecossistema USB/BT/xHCI do hefesto.
#
# Evolução do FEAT-DSX-STORM-WATCH-01 (PLAT-06 item 4, estudo
# 2026-07-18-estudo-kernel-hardening.md §6). O NOME do arquivo não mudou de
# propósito: a unit de usuário `hefesto-dualsense4unix-storm-watch.service`
# aponta para ele — compat preservada, nenhuma mudança de wiring obrigatória.
#
# O que vigia (journal do kernel + bluetoothd), com TAG por linha:
#   [USB-71]  o storm clássico (-71/enum) — mesmos padrões do doctor.sh;
#   [JOYCON]  joycon_enforce_subcmd_rate — o rate-limit do hid-nintendo que
#             derruba o 8BitDo/Pro Controller em BT (provado ao vivo 2026-07-18);
#   [JOYCON-PROBE]  Onda T (2026-07-20, desenho: docs/process/estudos/2026-07-
#             20-desenho-onda-t-patch-dkms.md) — a morte "invisível" por
#             PROBE (joycon_read_info -110, ANTES do device registrar; a
#             cascata [JOYCON] acima não vê nada porque o subcmd rate nem
#             chega a rodar) + o retry do patch DKMS agindo ("init over
#             bluetooth failed; retrying"). Tag NOVA, [JOYCON] fica intacto —
#             a string "exceeded max attempts" não mudou no patch;
#   [BT-HCI]  timeout/erro do hci no kernel — PREVENTIVO (zero histórico local:
#             silencioso até a 1ª ocorrência real, nada de alarmar o leigo);
#   [XHCI]    reset/morte do host USB — PREVENTIVO (idem);
#   [BT-ERR]  delta dos contadores RX/TX errors do adaptador (hciconfig), lido a
#             cada HEFESTO_KERNELWATCH_BT_INTERVAL s (default 300) — só loga
#             quando o contador PIOROU (pega rádio sujo sem btmon intrusivo);
#   [BT-SEM-CONTADOR]  uma linha só, no arranque, quando o `hciconfig` não
#             existe nesta máquina: aí [BT-ERR] NUNCA nasce, e sem esta marca
#             "zero [BT-ERR]" se leria como rádio limpo (MIGRACAO-BLUEZ-
#             DEPRECIADOS-01, 19/08/2026 — os contadores só saem do ioctl
#             HCIGETDEVINFO, e btmgmt/bluetoothctl não os expõem).
#
# AS QUATRO FAMÍLIAS DO RÁDIO (O-DIARIO-DO-RADIO-01, 23/09/2026). A palavra
# «storm» cobre pelo menos quatro físicas diferentes (dossiê de 23/09, em
# docs/process/estudos/2026-09-23-radio/dossies.md), e esta vigia era cega a
# três delas — 0 dos 4.019 «Output queue is full» de 22/09 chegaram ao log:
#   [USB-71]         família 1, o -71 de porta. O do ARRANQUE (a enumeração
#                    que acontece antes de a vigia subir) passou a entrar: a
#                    primeira volta de cada boot relê o boot inteiro;
#   [BT-SOCKET]      família 2A, o «BT socket write error» do bluetoothd — o
#                    EAGAIN que derrubou os quatro controles em 22/09;
#   [FILA-CHEIA]     família 2B, o «Output queue is full» do uhid — a fila
#                    presa com o bluetoothd sem drenar;
#   [ENLACE-PARADO]  família 2, «link tx timeout» e «killing stalled
#                    connection»: o kernel desistindo de um enlace;
#   [BT-TRAVADO]     família 3, o controlador travado em laço («command
#                    0x.... tx timeout» do Realtek, 24.998 vezes em 13/09);
#   [CRC]            família 4, a entrada descartada por CRC.
# Essas famílias chegam em RAJADA (no 2B são 100 linhas/s), então o log
# registra só a BORDA: a primeira linha sai inteira, as iguais são contadas, e
# um resumo sai a cada HEFESTO_KERNELWATCH_RESUMO_S (60) enquanto a rajada dura
# e outro quando ela acaba (HEFESTO_KERNELWATCH_JANELA_S, 10, sem repetir).
#
#   [PROBE-PERDIDA]  (STORM-USB-02, 24/09/2026) o controle do RÁDIO que perdeu
#                    a probe: `playstation 0005:054C:…: probe with driver
#                    playstation failed`. Pareado, conectado, com a luz acesa
#                    pelo próprio firmware — e sem existir para o sistema. É a
#                    contenção medida em 25/07 (dois subindo no mesmo
#                    adaptador), e é o que o -71 de um adaptador provoca: ele
#                    derruba todos os controles dele, e eles voltam juntos. Só o
#                    barramento 0005: no 0003 mora o vpad do próprio Hefesto
#                    (o `-17` do vpad que repete o MAC), que não se religa.
#
# O LUGAR E O RELIGAR NA HORA (STORM-USB-02). Duas coisas acontecem no instante
# do aviso, num estágio DEPOIS do `classify` (`anotar`) — o `classify` segue
# puro:
#   1. a linha [USB-71] ganha o LUGAR da porta (` · lugar pci-…-usb-0:4.4`), lido
#      do /sys DESTE boot na hora. Até aqui um -71 de outro boot era traduzido
#      pelos barramentos de hoje, e numa máquina em que a ordem dos xHCI mude o
#      nome da entrada sairia errado. Quem lê é o `exame_da_mesa`;
#   2. a linha da probe perdida — a HID do cabo no -71 (`usbhid …: can't add
#      hid device`) ou o [PROBE-PERDIDA] do rádio — chama o religar pela ponte
#      privilegiada (`sudo -n <ponte> religar-orfaos`), três vezes, com esperas
#      que cabem no lugar guardado de quem saiu (30 s): o controle volta com o
#      número dele. O tique do watchdog passa de 2 em 2 min (medido no journal
#      dela: mediana 120 s), e religado só ali ele voltava fora do prazo em ~3
#      de cada 4 quedas. Sem a regra do sudo (o install sem senha, o Flatpak),
#      nada muda: o tique continua religando, como antes.
#
# Log: ~/.local/state/hefesto-dualsense4unix/kernel.log (novo nome). O antigo
# storm.log é PRESERVADO se existir (histórico); se não existir, vira symlink
# para kernel.log (compat para humanos e scripts antigos).
#
# Não precisa de sudo se o usuário puder ler o journal do kernel (grupo
# systemd-journal/adm — padrão no Pop!_OS). Se não puder, registra a orientação
# e sai com erro (o serviço re-tenta com backoff, RestartSec=300).
#
# Hooks de teste (PUROS: stdin/args → stdout; não tocam journal nem estado):
#   --classify                              lê linhas short-iso do stdin e as
#                                           escreve com a TAG classificada
#   --test-desde MARCA BOOT_ID              diz de onde o journal começa (o boot
#                                           inteiro na primeira volta do boot,
#                                           o agora nas outras) e grava a marca
#   --test-bt-delta P_RX P_TX C_RX C_TX DEV emite a linha [BT-ERR] se delta > 0
#   --test-bt-sem-contador                  emite a linha [BT-SEM-CONTADOR]
#   --test-lugar                            lê mensagens do kernel (o que vem
#                                           depois da tag) e escreve «porta TAB
#                                           lugar» de cada uma
# E UM QUE NÃO É PURO, dito na cara: o estágio `anotar` inteiro.
#   --test-anotar TRAVA                     o `anotar` sobre o stdin. O religar
#                                           segura TRAVA (um arquivo) e chama o
#                                           sudo de HEFESTO_KERNELWATCH_SUDO —
#                                           sem esse gancho o hook sai com 2
#                                           ANTES da primeira linha: uma régua
#                                           nunca chama o sudo de verdade
#
# Uso manual: bash scripts/storm_watch.sh   (Ctrl+C encerra)
set -uo pipefail

# União dos padrões vigiados (case-insensitive; `can.t` cobre o apóstrofo).
# [USB-71] = regexes já provadas do doctor.sh (batalha de maio) + can't add hid.
# [JOYCON-PROBE] (Onda T) = "probe - fail = -" (nintendo_hid_probe do driver,
# QUALQUER retorno negativo — não hardcoda -110) + "failed to get joycon
# info" (joycon_read_info, a causa medida) + "init over bluetooth failed" (só
# existe no patch — o retry agindo). [JOYCON] intacto (exceeded max attempts).
# As quatro famílias do rádio (O-DIARIO-DO-RADIO-01): «output queue is full»
# (2B, do uhid), «bt socket write error» (2A, do bluetoothd), «link tx timeout»
# e «killing stalled connection» (o enlace parado), «command 0x.... tx timeout»,
# «read reg16 failed» e «failed to generate devcoredump» (3, o controlador
# travado — as três linhas de cada volta do laço) e «crc.s check failed» (4, a
# entrada). As do hci também casam o padrão genérico `bluetooth: hci…`; ficam
# escritas por extenso para que tirar o genérico não as cegue — e a régua
# (`test_o_vigia_ve_as_quatro_familias.py`) mede cada família SEM o genérico.
# [PROBE-PERDIDA] (STORM-USB-02): a probe do hid-playstation que abortou num
# controle do rádio (barramento 0005, e só ele).
GREP_UNION="error -71|can.t add hid device|device descriptor read/64, error|not accepting address|unable to enumerate usb device|joycon_enforce_subcmd_rate|probe - fail = -|failed to get joycon info|init over bluetooth failed|output queue is full|bt socket write error|link tx timeout|killing stalled connection|command 0x[0-9a-f]{4} tx timeout|read reg16 failed|failed to generate devcoredump|crc.s check failed|bluetooth: hci[0-9].*(timeout|failed|error)|xhci_hcd.*(reset|died|timeout|halt)|playstation 0005:[0-9a-f:.]+: probe with driver playstation failed"

# CADERNO-QUE-NÃO-ESCREVE-01: o `awk` desta casa lê de um cano que NUNCA fecha
# (`journalctl -f`), e o mawk bufferiza a ENTRADA — ver o comentário do
# `classify()`. O `-W interactive` é o que o destrava, e só o mawk o entende: o
# gawk o recusa como opção desconhecida e sai com erro, o que deixaria a vigia
# muda de um jeito ainda pior. Por isso a escolha é medida, não assumida.
_escolher_awk() {
    if awk -W interactive 'BEGIN { exit 0 }' </dev/null >/dev/null 2>&1; then
        echo "awk -W interactive"
    else
        echo "awk"
    fi
}
_AWK_CMD="$(_escolher_awk)"

# Classificador: linha short-iso do journal → "TIMESTAMP [TAG] mensagem".
# Ordem: do mais específico para o mais genérico (JOYCON/JOYCON-PROBE antes
# de USB-71 etc.). mawk-compatível (sem IGNORECASE): casa sobre tolower($0).
#
# CADERNO-QUE-NÃO-ESCREVE-01 (08/08/2026). O caderno dela estava VAZIO: 120
# linhas, todas banners do próprio shell, a última de 20/07 — contra 723 eventos
# de storm no journal do mesmo período, com a vigia `enabled` e `active` o tempo
# todo. Ela pediu a explicação da queda dos controles, e o arquivo que a guardaria
# não tinha nada.
#
# A CURA É O `-W interactive`, E NÃO O `fflush()`. Esta distinção custou duas
# medições e uma afirmação errada, então está escrita por extenso. O gargalo é a
# ENTRADA do mawk, não a saída: ele lê com buffer PRÓPRIO, fora do stdio, e nem
# chega a executar o bloco — então não há o que um `fflush()` de saída descarregue,
# e o `stdbuf` também não alcança (o `LD_PRELOAD` dele só mexe no stdio).
#
# MEDIDO nesta bancada, com produtor vivo e 3-4 s de espera:
#     mawk '{print; fflush()}'                -> 0 bytes
#     stdbuf -oL -i0 mawk '{print; fflush()}' -> 0 bytes
#     mawk -W interactive '{print}'           -> escreve na hora
#
# O `fflush()` FICA junto, e não é redundante: ele é o que garante a escrita por
# linha quando o `awk` desta máquina não for o mawk (o gawk ignora `-W
# interactive` como opção desconhecida mas honra o `fflush()`). Os dois juntos
# cobrem os dois interpretadores.
#
# A BORDA (O-DIARIO-DO-RADIO-01). As famílias do rádio chegam em rajada — no 2B
# de 22/09 foram 100 linhas por segundo durante 81 s —, e uma vigia que copia
# cada linha enche o log e esconde o que importa: QUANDO começou, QUANTO durou.
# Para as tags de rajada, a primeira linha de cada aparelho sai inteira (a
# borda), as seguintes só somam, e o total sai em duas linhas de resumo: uma a
# cada `resumo` segundos enquanto a rajada dura («segue»), outra quando ela
# acaba («repetiu»). Acabou = `janela` segundos sem repetir. O relógio é o da
# própria linha, não o da máquina: a releitura do arranque passa horas em
# segundos, e o awk não tem timer — por isso o fim de uma rajada só é escrito
# quando chega a linha seguinte (ou no fim da entrada).
#
# A chave da rajada é a TAG mais o aparelho (os dois primeiros campos da
# mensagem: `playstation 0005:054C:0CE6.000C:`, `Bluetooth: hci0:`). As três
# linhas de cada volta do laço do Realtek caem na mesma chave, e os três
# controles que levam EAGAIN no mesmo segundo também.
classify() {
    ${_AWK_CMD:-awk} \
        -v janela="${HEFESTO_KERNELWATCH_JANELA_S:-10}" \
        -v resumo="${HEFESTO_KERNELWATCH_RESUMO_S:-60}" '
    # "2026-09-22T16:46:32-03:00" -> segundos. O fuso é ignorado de propósito:
    # só se compara hora com hora do MESMO fluxo. Aritmética de calendário
    # (dias desde 1970) em vez de mktime(), que nem todo awk tem.
    function segundos(ts,   y, mo, d, yy, era, yoe, mm, doy, doe) {
        y = substr(ts, 1, 4) + 0; mo = substr(ts, 6, 2) + 0; d = substr(ts, 9, 2) + 0
        if (y < 1970 || mo < 1 || mo > 12 || d < 1) return -1
        yy = (mo <= 2) ? y - 1 : y
        era = int(yy / 400); yoe = yy - era * 400
        mm = (mo > 2) ? mo - 3 : mo + 9
        doy = int((153 * mm + 2) / 5) + d - 1
        doe = yoe * 365 + int(yoe / 4) - int(yoe / 100) + doy
        return (era * 146097 + doe - 719468) * 86400 \
            + substr(ts, 12, 2) * 3600 + substr(ts, 15, 2) * 60 + substr(ts, 18, 2)
    }
    function fechar(k) {
        if (extra[k] > 0)
            print ultts[k] " " tagk[k] " repetiu +" extra[k] " (" total[k] " desde " inits[k] ", " (ult[k] - ini[k]) " s): " texto[k]
        delete ult[k]; delete ini[k]; delete extra[k]; delete total[k]
        delete ultts[k]; delete inits[k]; delete tagk[k]; delete texto[k]; delete rep[k]
    }
    {
        low = tolower($0)
        tag = "[KERNEL]"
        borda = 0
        if (low ~ /joycon_enforce_subcmd_rate/) tag = "[JOYCON]"
        else if (low ~ /probe - fail = -|failed to get joycon info|init over bluetooth failed/) tag = "[JOYCON-PROBE]"
        else if (low ~ /playstation 0005:[0-9a-f:.]+: probe with driver playstation failed/) tag = "[PROBE-PERDIDA]"
        else if (low ~ /error -71|can.t add hid device|device descriptor read\/64, error|not accepting address|unable to enumerate usb device/) tag = "[USB-71]"
        else if (low ~ /output queue is full/) { tag = "[FILA-CHEIA]"; borda = 1 }
        else if (low ~ /bt socket write error/) { tag = "[BT-SOCKET]"; borda = 1 }
        else if (low ~ /link tx timeout|killing stalled connection/) { tag = "[ENLACE-PARADO]"; borda = 1 }
        else if (low ~ /command 0x[0-9a-f][0-9a-f][0-9a-f][0-9a-f] tx timeout|read reg16 failed|failed to generate devcoredump/) { tag = "[BT-TRAVADO]"; borda = 1 }
        else if (low ~ /crc.s check failed/) { tag = "[CRC]"; borda = 1 }
        else if (low ~ /xhci_hcd.*(reset|died|timeout|halt)/) { tag = "[XHCI]"; borda = 1 }
        else if (low ~ /bluetooth: hci[0-9].*(timeout|failed|error)/) { tag = "[BT-HCI]"; borda = 1 }
        # short-iso: "TS host identificador: msg" → "TS [TAG] msg"
        ts = $1
        rest = $0
        sub(/^[^ ]+ +/, "", rest)     # remove o timestamp
        sub(/^[^ ]+ +/, "", rest)     # remove o hostname
        sub(/^[^ ]+: +/, "", rest)    # remove "kernel:" / "bluetoothd[pid]:"
        t = segundos(ts)
        # Rajadas de OUTRA chave que esfriaram também fecham aqui: sem timer,
        # a chegada de qualquer linha é o relógio. A distância é em módulo: o
        # journal intercala kernel e bluetoothd, e um salto para trás também é
        # outra rajada.
        if (t >= 0) {
            for (j in ult) {
                dist = t - ult[j]
                if (dist < 0) dist = -dist
                if (dist > janela) fechar(j)
            }
        }
        if (!borda || t < 0) {
            print ts " " tag " " rest
            fflush()
            next
        }
        split(rest, campo, " ")
        k = tag " " campo[1] " " campo[2]
        if (k in ult) {
            extra[k]++; total[k]++; ult[k] = t; ultts[k] = ts
            if (t - rep[k] >= resumo) {
                print ts " " tag " segue +" extra[k] " (" total[k] " desde " inits[k] ", " (t - ini[k]) " s): " texto[k]
                extra[k] = 0; rep[k] = t
                fflush()
            }
            next
        }
        ini[k] = t; ult[k] = t; rep[k] = t; extra[k] = 0; total[k] = 1
        inits[k] = ts; ultts[k] = ts; tagk[k] = tag; texto[k] = rest
        print ts " " tag " " rest
        fflush()
    }
    END {
        for (j in ult) fechar(j)
        fflush()
    }'
}

# Contadores de erro do adaptador BT: imprime "RX TX" (0 0 se ilegível).
bt_read_errors() {
    local dev="$1"
    hciconfig "${dev}" 2>/dev/null | awk '
        /RX bytes/ { for (i = 1; i <= NF; i++) if ($i ~ /^errors:/) { split($i, a, ":"); rx = a[2] } }
        /TX bytes/ { for (i = 1; i <= NF; i++) if ($i ~ /^errors:/) { split($i, a, ":"); tx = a[2] } }
        END { if (rx == "") rx = 0; if (tx == "") tx = 0; print rx, tx }'
}

# Linha [BT-ERR] SÓ quando o delta é positivo (silencioso enquanto saudável).
bt_emit_delta() {
    local prev_rx="$1" prev_tx="$2" cur_rx="$3" cur_tx="$4" dev="$5"
    local d_rx=$((cur_rx - prev_rx)) d_tx=$((cur_tx - prev_tx))
    if (( d_rx > 0 || d_tx > 0 )); then
        printf '%s [BT-ERR] %s delta rx_errors=+%d tx_errors=+%d (acumulado %d/%d)\n' \
            "$(date '+%Y-%m-%dT%H:%M:%S%z')" "${dev}" "${d_rx}" "${d_tx}" \
            "${cur_rx}" "${cur_tx}"
    fi
}

# Linha única quando a medida de [BT-ERR] não existe nesta máquina.
#
# LEITURA SEM SUCESSOR VIVO (MIGRACAO-BLUEZ-DEPRECIADOS-01, 19/08/2026): os
# contadores RX/TX errors são o `hci_dev_stats` do kernel, entregue só pelo
# ioctl HCIGETDEVINFO — que só o `hciconfig` chama. Nem `btmgmt` nem
# `bluetoothctl` do 5.86 têm comando equivalente (conferido nos dois `--help` em
# 19/08/2026). Sem a ferramenta depreciada esta vigia não tem o que ler.
#
# Antes ela voltava CALADA, e o kernel.log ficava sem [BT-ERR] para sempre —
# indistinguível de "rádio limpo", que é a mentira por omissão que o doctor
# repetia adiante. A marca [BT-SEM-CONTADOR] existe para o doctor poder dizer
# "isto não foi medido" em vez de "isto está bem".
bt_sem_contador() {
    printf '%s [BT-SEM-CONTADOR] contadores de erro do rádio não medidos: o hciconfig (única fonte do ioctl HCIGETDEVINFO) foi depreciado pelo BlueZ e não está nesta máquina; btmgmt/bluetoothctl não o substituem. Sem [BT-ERR] neste log = medida ausente, NÃO rádio limpo\n' \
        "$(date '+%Y-%m-%dT%H:%M:%S%z')"
}

# Loop lateral: snapshot dos contadores por adaptador; emite só o delta.
bt_delta_loop() {
    if ! command -v hciconfig >/dev/null 2>&1; then
        bt_sem_contador >>"${LOG}"
        return 0
    fi
    local interval="${HEFESTO_KERNELWATCH_BT_INTERVAL:-300}"
    declare -A prev_rx prev_tx
    local path dev rx tx
    while :; do
        for path in /sys/class/bluetooth/hci*; do
            [[ -e "${path}" ]] || continue
            dev="$(basename "${path}")"
            # /sys/class/bluetooth também abriga as CONEXÕES ("hci0:256"), que
            # não são adaptador e fariam o hciconfig devolver vazio.
            [[ "${dev}" =~ ^hci[0-9]+$ ]] || continue
            read -r rx tx <<<"$(bt_read_errors "${dev}")"
            if [[ -n "${prev_rx[${dev}]:-}" ]]; then
                bt_emit_delta "${prev_rx[${dev}]}" "${prev_tx[${dev}]}" \
                    "${rx}" "${tx}" "${dev}" >>"${LOG}"
            fi
            prev_rx[${dev}]="${rx}"
            prev_tx[${dev}]="${tx}"
        done
        sleep "${interval}"
    done
}

# De onde o `journalctl -f` começa. A PRIMEIRA volta de cada boot relê o boot
# inteiro (`-b --lines=all`): o -71 da enumeração acontece no segundo do boot,
# antes de a vigia subir, e sem esta releitura ele nunca entrava no log —
# medido em 23/09, quatro boots da semana com -71 no arranque e nenhum no
# kernel.log. As voltas SEGUINTES do mesmo boot (a unit re-tenta com
# RestartSec) começam do agora (`-n0`), para não duplicar o que já foi escrito.
# A marca é o boot_id, gravado num arquivo do estado.
#   $1 = arquivo da marca · $2 = boot_id atual · imprime os argumentos, um por linha
desde_do_journal() {
    local marca="$1" boot="$2"
    if [[ -n "${boot}" && "$(cat "${marca}" 2>/dev/null || true)" != "${boot}" ]]; then
        printf '%s\n' "${boot}" >"${marca}" 2>/dev/null || true
        printf '%s\n' -b --lines=all
    else
        printf '%s\n' -n0
    fi
}

# ---- o LUGAR e o RELIGAR NA HORA (STORM-USB-02, 24/09/2026) ------------------
# Ver o cabeçalho. Tudo aqui roda como ela: nada escreve no /sys (o lugar é um
# `readlink`), e o religar é da ponte privilegiada, pelo sudo sem senha que o
# install grava para o verbo — e SÓ para ele.

#: Onde o /sys lista os nós USB. Gancho da régua: o /sys de mentira.
SYSFS_USB="${HEFESTO_KERNELWATCH_SYSFS_USB:-/sys/bus/usb/devices}"

#: A ponte instalada e quem a chama. Os dois ganchos existem para a régua, cujo
#: sudo de mentira aceita só o que a regra do sudoers aceita.
PONTE="${HEFESTO_KERNELWATCH_PONTE:-/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh}"
SUDO="${HEFESTO_KERNELWATCH_SUDO:-sudo}"

#: As esperas do religar, em segundos, contadas do aviso do kernel. A primeira
#: deixa a porta — ou o rádio, com os outros controles subindo juntos —
#: assentar; a soma (20 s), mais a probe e o hotplug do daemon (2 s), cabe no
#: lugar guardado de quem saiu (30 s, `identity.prazo_do_lugar_guardado`). São
#: três porque o teto do `bt_rebind_orphans.sh --evento` é três.
RELIGAR_ESPERAS="${HEFESTO_KERNELWATCH_RELIGAR_ESPERAS:-3 7 10}"

#: A porta USB de uma mensagem do kernel, no nome do /sys (`3-4.1.3`) — ou nada.
#: DUAS CÓPIAS, UMA FORMA: a outra é `exame_da_mesa.porta_do_evento`, que relê
#: o log depois; a régua (`test_o_cabo_que_cai_volta_com_o_numero.py`) passa as
#: cinco formas da linha pelas duas. O alvo é o que vem antes do primeiro `: `.
porta_da_mensagem() {
    local alvo
    [[ "$1" =~ ^[[:space:]]*[^[:space:]]+[[:space:]]+([^[:space:]]+):[[:space:]] ]] || return 0
    alvo="${BASH_REMATCH[1]}"
    if [[ "${alvo}" =~ ^usb([0-9]+)-port([0-9]+)$ ]]; then
        printf '%s-%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    elif [[ "${alvo}" =~ ^([0-9]+-[0-9]+(\.[0-9]+)*)-port([0-9]+)$ ]]; then
        printf '%s.%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[3]}"
    elif [[ "${alvo}" =~ ^([0-9]+-[0-9]+(\.[0-9]+)*):[0-9]+\.[0-9]+$ ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
    elif [[ "${alvo}" =~ ^[0-9]+-[0-9]+(\.[0-9]+)*$ ]]; then
        printf '%s\n' "${alvo}"
    fi
}

#: O LUGAR de uma porta pelos barramentos DESTE boot: `3-4.4` vira
#: `pci-0000:0c:00.3-usb-0:4.4` — o controlador PCI do hub-raiz `usb3` e a cadeia
#: de portas. DUAS CÓPIAS, UMA FORMA: a grafia é a do `ID_PATH` do udev, o dono
#: dela é `utils/lugar.lugar_do_caminho` e a leitura do controlador é
#: `mesa_de_radio.controladores_dos_barramentos` (o ÚLTIMO `0000:xx:xx.x` do
#: caminho real); a mesma régua confere as duas. Nada quando não se sabe.
lugar_da_porta() {
    local porta="$1" real parte pci=""
    local -a partes
    [[ "${porta}" =~ ^[0-9]+-[0-9]+(\.[0-9]+)*$ ]] || return 0
    real="$(readlink -f -- "${SYSFS_USB}/usb${porta%%-*}" 2>/dev/null)" || return 0
    IFS=/ read -ra partes <<<"${real}"
    for parte in "${partes[@]}"; do
        [[ "${parte}" =~ ^0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9a-f]$ ]] && pci="${parte}"
    done
    [[ -n "${pci}" ]] && printf 'pci-%s-usb-0:%s\n' "${pci}" "${porta#*-}"
    return 0
}

#: A linha pede o religar? As duas formas que o `bt_rebind_orphans.sh` cura, e
#: só elas: a HID do cabo que perdeu a probe no -71, e o controle do rádio que
#: perdeu a probe. Um -71 que o kernel ainda está tentando não pede nada.
_RELIGA_O_CABO='\[usb-71\] usbhid [0-9.:-]+: (can.t add hid device|probe with driver usbhid failed)'
pede_religar() {
    local baixa="${1,,}"
    [[ "${baixa}" =~ ${_RELIGA_O_CABO} ]] && return 0
    [[ "${baixa}" == *" [probe-perdida] "* ]]
}

#: O religar, EM FUNDO, para não segurar o log. Uma rajada, um trabalho: quem
#: chega com um de pé é absorvido por ele (o `flock`), e cada passada da ponte
#: religa o que houver de órfão naquela hora. Sem a regra do sudo, sai calado.
religar_em_fundo() {
    local trava="$1"
    (
        if command -v flock >/dev/null 2>&1; then
            flock -n 9 || exit 0
        fi
        [[ -x "${PONTE}" ]] || exit 0
        "${SUDO}" -n -l "${PONTE}" religar-orfaos >/dev/null 2>&1 || exit 0
        for espera in ${RELIGAR_ESPERAS}; do
            sleep "${espera}"
            timeout 60 "${SUDO}" -n "${PONTE}" religar-orfaos >/dev/null 2>&1 || true
        done
    ) 9>>"${trava}" </dev/null >/dev/null 2>&1 &
}

#: O estágio depois do `classify`: o lugar na linha do -71 e o religar da probe
#: perdida. `$1` é a trava do religar; vazio, só anota.
anotar() {
    local trava="${1:-}" linha porta lugar
    while IFS= read -r linha || [[ -n "${linha}" ]]; do
        if [[ "${linha}" == *" [USB-71] "* && "${linha}" != *" · lugar "* ]]; then
            porta="$(porta_da_mensagem "${linha#* \[USB-71\] }")"
            lugar=""
            [[ -n "${porta}" ]] && lugar="$(lugar_da_porta "${porta}")"
            [[ -n "${lugar}" ]] && linha="${linha} · lugar ${lugar}"
        fi
        printf '%s\n' "${linha}"
        if [[ -n "${trava}" ]] && pede_religar "${linha}"; then
            religar_em_fundo "${trava}"
        fi
    done
}

# ---- hooks de teste (puros, saem antes de tocar estado/journal) --------------
case "${1:-}" in
    --classify)
        classify
        exit 0
        ;;
    --test-lugar)
        while IFS= read -r mensagem || [[ -n "${mensagem}" ]]; do
            porta="$(porta_da_mensagem "${mensagem}")"
            lugar=""
            [[ -n "${porta}" ]] && lugar="$(lugar_da_porta "${porta}")"
            printf '%s\t%s\n' "${porta}" "${lugar}"
        done
        exit 0
        ;;
    --test-anotar)
        # A GUARDA QUE SAI: sem o sudo de mentira, este hook chamaria o sudo de
        # verdade — e a ponte instalada dela.
        if [[ -z "${HEFESTO_KERNELWATCH_SUDO:-}" || -z "${2:-}" ]]; then
            echo "storm_watch.sh --test-anotar: precisa de HEFESTO_KERNELWATCH_SUDO e da trava" >&2
            exit 2
        fi
        anotar "$2"
        wait
        exit 0
        ;;
    --test-bt-delta)
        shift
        bt_emit_delta "$@"
        exit 0
        ;;
    --test-bt-sem-contador)
        bt_sem_contador
        exit 0
        ;;
    --test-desde)
        desde_do_journal "${2:-}" "${3:-}"
        exit 0
        ;;
esac

# ---- serviço de verdade ------------------------------------------------------
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix"
mkdir -p "${STATE_DIR}"
LOG="${STATE_DIR}/kernel.log"
LEGACY_LOG="${STATE_DIR}/storm.log"

# Compat: storm.log preservado se for arquivo real; symlink se não existir.
if [[ ! -e "${LEGACY_LOG}" && ! -L "${LEGACY_LOG}" ]]; then
    ln -s "kernel.log" "${LEGACY_LOG}" 2>/dev/null || true
fi

if ! command -v journalctl >/dev/null 2>&1; then
    echo "# $(date '+%F %T') kernel-watch: journalctl ausente — abortando" >>"${LOG}"
    exit 1
fi

# Probe de permissão: lê 1 linha do kernel. Se falhar, o usuário não tem acesso
# ao journal do kernel — orienta e sai (serviço re-tenta com RestartSec).
if ! journalctl -k -n1 >/dev/null 2>&1; then
    {
        echo "# $(date '+%F %T') kernel-watch: sem permissão p/ 'journalctl -k'."
        echo "#   Adicione seu usuário ao grupo: sudo usermod -aG systemd-journal \"\$USER\""
        echo "#   (relogin necessário). Re-tentando em background."
    } >>"${LOG}"
    exit 1
fi

mapfile -t DESDE < <(desde_do_journal "${STATE_DIR}/kernel-watch.boot" \
    "$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)")
if [[ "${DESDE[0]:-}" == "-b" ]]; then
    echo "# $(date '+%F %T') kernel-watch: primeira volta deste boot — relendo o arranque (o -71 da enumeração nasce antes da vigia)" >>"${LOG}"
fi
echo "# $(date '+%F %T') kernel-watch iniciado (padrões: USB-71 JOYCON JOYCON-PROBE PROBE-PERDIDA FILA-CHEIA BT-SOCKET ENLACE-PARADO BT-TRAVADO CRC BT-HCI XHCI + contadores hci; preventivos ficam silenciosos até a 1ª ocorrência; rajada vira borda + resumo; o -71 leva o lugar; a probe perdida chama o religar)" >>"${LOG}"

bt_delta_loop &
BT_LOOP_PID=$!
trap 'kill "${BT_LOOP_PID}" 2>/dev/null' EXIT INT TERM

# -f follow; o começo sai de `desde_do_journal` (o boot inteiro na primeira
# volta do boot, `-n0` — o agora — nas outras); short-iso p/ timestamp estável.
# Fontes: kernel (+ = OU lógico) e o bluetoothd (unit), que é de onde vem o
# «BT socket write error» da família 2A.
# --case-sensitive=false: sem smartcase surpresa ("Bluetooth: hci" tem maiúscula).
# O `anotar` vem DEPOIS do `classify` (STORM-USB-02): põe o lugar na linha do -71
# e chama o religar na probe perdida, com a trava do religar no estado dela.
journalctl -f "${DESDE[@]}" -o short-iso --case-sensitive=false --grep="${GREP_UNION}" \
    _TRANSPORT=kernel + _SYSTEMD_UNIT=bluetooth.service \
    2>>"${LOG}" | classify | anotar "${STATE_DIR}/kernel-watch.religar" >>"${LOG}"

echo "# $(date '+%F %T') kernel-watch terminou inesperadamente (journalctl caiu?) — a unit re-tenta" >>"${LOG}"
exit 1
