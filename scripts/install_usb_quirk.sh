#!/usr/bin/env bash
# install_usb_quirk.sh — alavanca de boot que PRESERVA o áudio do DualSense.
#
# CONTEXTO: o storm -71 (EPROTO) do DualSense é disparado pela ENUMERAÇÃO das
# interfaces de ÁUDIO USB (snd-usb-audio) — uma rajada de control-transfers no
# EP0 que, sob carga, derruba o link do controlador. Há DUAS alavancas para o
# storm, ALTERNATIVAS (use UMA OU OUTRA, nunca as duas):
#
#   - regra 75 (assets/75-ps5-controller-disable-usb-audio.rules): DESLIGA o
#     áudio USB inteiro do controle (sem mic E sem fone do jack). Opt-in via
#     install_udev.sh --disable-usb-audio.
#   - ESTE script: aplica o quirk usbcore.quirks=054c:0ce6:gn
#     (g=DELAY_INIT, n=DELAY_CTRL_MSG), que ESPAÇA a rajada do probe para ela
#     não tombar o link — o áudio AINDA enumera, só mais devagar. PRESERVA o
#     mic e o fone do jack do DualSense. Validado A/B + ao vivo 2026-06-26.
#     CAVEAT: preserva o áudio no nível do KERNEL (sem storm); com os WP 52/53
#     instalados o nó segue suprimido no PipeWire até removê-los ou definir
#     HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1.
#
# IMPORTANTE — ISTO NÃO É UMA REGRA UDEV: é um PARÂMETRO DE CMDLINE DO KERNEL.
# Uma regra udev não consegue alterar o próprio enumeramento do device (o quirk
# precisa estar ativo ANTES do probe), por isso vem empacotado como PASSO DE
# INSTALL, ciente do bootloader, e não como assets/*.rules.
#
# O kernel respeita SÓ UM token usbcore.quirks= no cmdline — se já existir um
# DIFERENTE, o nosso é FUNDIDO nele (o mesmo merge do passo 3e do install), e
# nunca entra um segundo.
#
# O 054c:0df2 SAIU em 14/10/2026 (ADR 018, nota datada): é o PID do pad virtual
# do Hefesto, e o n dele esperava 200 ms por pedido de controle — com quatro
# controles o jogo perdia os controles. Quem tem o token velho
# (usbcore.quirks=054c:0ce6:gn,054c:0df2:gn) é MIGRADO: o velho sai, o novo entra,
# no kernelstub e no grub, e o valor do sysfs perde a entrada (vale no próximo
# enumerar, e o pad se refaz a cada sessão).
#
# Idempotente (rodar 2x = no-op na 2a; nunca duplica token). Reversível
# (--remove). Quem lê e escreve o carregador de boot é o módulo
# src/hefesto_dualsense4unix/integrations/kernel_cmdline.py, o mesmo do passo 3e
# (O-CMDLINE-DO-DUALSENSE-SO-SE-ESCREVE-NO-KERNELSTUB-01): kernelstub
# (Pop!_OS/System76), grub (Debian, Ubuntu, Fedora, Arch) e systemd-boot pelo
# /etc/kernel/cmdline.
#
# Uso:
#   scripts/install_usb_quirk.sh            aplica o quirk (default; requer root)
#   scripts/install_usb_quirk.sh --remove   reverte o quirk (requer root)
#   scripts/install_usb_quirk.sh --status   read-only: ativo/agendado/runtime (sem sudo)
#   scripts/install_usb_quirk.sh --check     alias de --status
#   scripts/install_usb_quirk.sh --runtime  escreve no sysfs (best-effort; só vale
#                                            na próxima reenumeração/replug; NÃO
#                                            substitui o cmdline). Requer root.
#
# FEAT-DSX-DEFINITIVE-FIX-01 §7.5 (Opção D). Pesquisa e descritores reais em
# o registro «storm-audio-pesquisa-profunda-quirk-vs-audiooff» de 26/06/2026.

set -euo pipefail

# Token completo de cmdline (o que entra no kernelstub/grub).
readonly QUIRK="usbcore.quirks=054c:0ce6:gn"
# Apenas o VALOR (sem o prefixo) — o que o sysfs runtime espera.
readonly QUIRK_VALUE="054c:0ce6:gn"
# Marcador estável para checagem de presença (idempotência).
readonly MARKER="054c:0ce6:gn"
# A entrada que o Hefesto gravava até 14/10/2026 e que agora SAI (a migração).
readonly ENTRADA_VELHA="054c:0df2:gn"
# Caminhos de config dos bootloaders suportados. Os HEFESTO_QUIRK_* são o
# gancho dos testes (um /etc e um /sys de mentira); o sudo não os repassa.
readonly KERNELSTUB_CONF="${HEFESTO_QUIRK_KERNELSTUB_CONF:-/etc/kernelstub/configuration}"
readonly GRUB_CONF="${HEFESTO_QUIRK_GRUB_CONF:-/etc/default/grub}"
readonly KERNEL_CMDLINE_CONF="${HEFESTO_QUIRK_KERNEL_CMDLINE:-/etc/kernel/cmdline}"
_aqui="${BASH_SOURCE[0]%/*}"
if [[ "$_aqui" == "${BASH_SOURCE[0]}" ]]; then _aqui="."; fi
_raiz_do_repo="$(cd "${_aqui}/.." && pwd)"
readonly DONO_DO_CMDLINE="${_raiz_do_repo}/src/hefesto_dualsense4unix/integrations/kernel_cmdline.py"
readonly SYSFS_QUIRKS="${HEFESTO_QUIRK_SYSFS:-/sys/module/usbcore/parameters/quirks}"

info() { printf '[usb-quirk] %s\n' "$*"; }
warn() { printf '[usb-quirk] aviso: %s\n' "$*" >&2; }
die()  { printf '[usb-quirk] ERRO: %s\n' "$*" >&2; exit 1; }

# Roda "$@" como root: direto se já for root, via sudo caso contrário.
as_root() {
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        die "precisa de root e 'sudo' está ausente — rode como root"
    fi
}


# ---------------------------------------------------------------------------
# A MIGRAÇÃO DO TOKEN VELHO (14/10/2026)
# ---------------------------------------------------------------------------
# Uma lista "a,b,c" sem a ENTRADA_VELHA (exata: um 054c:0df2 com outras flags
# é de terceiro e fica). Imprime a lista que sobra (vazia se nada sobrar).
_sem_a_entrada_velha() {
    local entrada saida=()
    local -a entradas
    IFS=',' read -r -a entradas <<<"$1"
    for entrada in "${entradas[@]}"; do
        [[ -z "$entrada" || "$entrada" == "$ENTRADA_VELHA" ]] && continue
        saida+=("$entrada")
    done
    local IFS=','
    printf '%s' "${saida[*]}"
}

# Os tokens usbcore.quirks= de um arquivo que carregam a ENTRADA_VELHA.
_tokens_com_a_entrada_velha() {
    local arquivo="$1" token
    [[ -r "$arquivo" ]] || return 0
    while IFS= read -r token; do
        if [[ ",${token#usbcore.quirks=}," == *",${ENTRADA_VELHA},"* ]]; then
            printf '%s\n' "$token"
        fi
    done < <(grep -oE 'usbcore\.quirks=[^"[:space:]]*' "$arquivo" 2>/dev/null | sort -u)
    return 0
}

# O valor do sysfs sem a entrada velha. Best-effort: vale no próximo enumerar
# (o pad virtual se refaz a cada sessão); falhar aqui não derruba o apply.
migrate_runtime() {
    local atual novo
    [[ -r "$SYSFS_QUIRKS" ]] || return 0
    atual="$(cat "$SYSFS_QUIRKS" 2>/dev/null || true)"
    [[ ",${atual}," == *",${ENTRADA_VELHA},"* ]] || return 0
    novo="$(_sem_a_entrada_velha "$atual")"
    info "tirando ${ENTRADA_VELHA} de ${SYSFS_QUIRKS} (vale no próximo enumerar do pad virtual)"
    printf '%s' "$novo" | as_root tee "$SYSFS_QUIRKS" >/dev/null \
        || warn "não consegui reescrever ${SYSFS_QUIRKS} — vale no próximo boot, pelo cmdline"
    return 0
}

# ---------------------------------------------------------------------------
# APLICAR E REMOVER, pelo dono do carregador de boot
# ---------------------------------------------------------------------------
# O módulo roda como root com os caminhos deste script (os HEFESTO_QUIRK_* são
# o gancho dos testes) e diz, uma linha por carregador, o que fez.
_pelo_dono() {
    local pedido="$1" saida rc=0 tipo backend tira poe
    [[ -f "$DONO_DO_CMDLINE" ]] || die "o dono do cmdline não está em ${DONO_DO_CMDLINE}"
    saida="$(as_root python3 -I "$DONO_DO_CMDLINE" "$pedido" \
        --kernelstub-conf "$KERNELSTUB_CONF" --grub-conf "$GRUB_CONF" \
        --kernel-cmdline "$KERNEL_CMDLINE_CONF")" || rc=$?
    while IFS=$'\t' read -r tipo backend tira poe; do
        case "$tipo" in
            no-op)  info "no-op: nada a mudar em ${tira} (${backend})" ;;
            troca)
                if [[ ",${tira//usbcore.quirks=/}," == *",${ENTRADA_VELHA},"* ]]; then
                    info "migrando em ${backend}: ${tira} → ${poe} (o ${ENTRADA_VELHA} do pad virtual sai)"
                else
                    info "trocando em ${backend}: tira ${tira}, põe ${poe}"
                fi ;;
            escreveu) info "feito em ${backend} (${tira}) — vale no PRÓXIMO boot. (--runtime aplica agora, sem reboot, no próximo replug.)" ;;
            aviso)  warn "${backend}" ;;
            falhou) warn "falhou: ${backend}" ;;
            nenhum)
                info "bootloader não reconhecido (sem kernelstub, ${GRUB_CONF} e ${KERNEL_CMDLINE_CONF})."
                info "adicione MANUALMENTE este token ao cmdline do seu bootloader: ${QUIRK}"
                info "ele PRESERVA o áudio do DualSense e mitiga o storm -71. Não é uma regra udev — é cmdline." ;;
        esac
    done <<<"${saida}"
    [[ "$rc" -eq 0 ]] || die "a escrita no carregador de boot falhou (rc=${rc})"
}

do_apply() {
    _pelo_dono quirk-aplicar
    migrate_runtime
}

# Limpa TODO carregador legível (não só o que manda hoje): se o bootloader mudou
# depois do apply, não fica token órfão no antigo. No-op onde o token não está.
do_remove() {
    _pelo_dono quirk-remover
}

# ---------------------------------------------------------------------------
# STATUS (read-only, sem sudo)
# ---------------------------------------------------------------------------
do_status() {
    info "quirk alvo: ${QUIRK}"

    # Ativo NESTE boot (cmdline corrente).
    if grep -q "$MARKER" /proc/cmdline 2>/dev/null; then
        info "[ativo neste boot]          sim — presente em /proc/cmdline"
    else
        info "[ativo neste boot]          não — ausente em /proc/cmdline"
    fi

    # Agendado para o PRÓXIMO boot (config do bootloader).
    local scheduled=0
    if [[ -r "$KERNELSTUB_CONF" ]] && grep -q "$MARKER" "$KERNELSTUB_CONF" 2>/dev/null; then
        info "[agendado p/ próximo boot]  sim — em ${KERNELSTUB_CONF} (kernelstub)"
        scheduled=1
    fi
    if [[ -r "$GRUB_CONF" ]] && grep -q "$MARKER" "$GRUB_CONF" 2>/dev/null; then
        info "[agendado p/ próximo boot]  sim — em ${GRUB_CONF} (grub)"
        scheduled=1
    fi
    if [[ -r "$KERNEL_CMDLINE_CONF" ]] && grep -q "$MARKER" "$KERNEL_CMDLINE_CONF" 2>/dev/null; then
        info "[agendado p/ próximo boot]  sim — em ${KERNEL_CMDLINE_CONF} (systemd-boot)"
        scheduled=1
    fi
    [[ "$scheduled" -eq 0 ]] && info "[agendado p/ próximo boot]  não — ausente no config do bootloader"

    # Runtime (sysfs) — vale só na próxima reenumeração/replug.
    if [[ -r "$SYSFS_QUIRKS" ]] && grep -q "$MARKER" "$SYSFS_QUIRKS" 2>/dev/null; then
        info "[runtime sysfs]             sim — em ${SYSFS_QUIRKS} (aplica no próximo replug)"
    else
        info "[runtime sysfs]             não — ${SYSFS_QUIRKS} sem o quirk"
    fi

    local onde
    for onde in /proc/cmdline "$KERNELSTUB_CONF" "$GRUB_CONF" "$KERNEL_CMDLINE_CONF"; do
        if [[ -n "$(_tokens_com_a_entrada_velha "$onde")" ]]; then
            info "[DEFEITO] ${ENTRADA_VELHA} em ${onde}: o pad virtual espera 200 ms por pedido; com 4 controles o jogo perde os controles — rode este script sem argumento para migrar"
        fi
    done
    if [[ -r "$SYSFS_QUIRKS" && ",$(cat "$SYSFS_QUIRKS" 2>/dev/null)," == *",${ENTRADA_VELHA},"* ]]; then
        info "[DEFEITO] ${ENTRADA_VELHA} em ${SYSFS_QUIRKS}: o pad virtual espera 200 ms por pedido — rode este script sem argumento para migrar"
    fi

    info "lembrete: quirk (este) PRESERVA o áudio; é ALTERNATIVA à regra 75 (áudio-off). Use uma OU outra."
    info "caveat: preserva o áudio no nível do KERNEL (sem storm); com os WP 52/53 o nó segue suprimido no PipeWire até removê-los ou definir DUALSENSE_MIC_INTENDED=1"
}

# ---------------------------------------------------------------------------
# RUNTIME (best-effort; não substitui o cmdline)
# ---------------------------------------------------------------------------
do_runtime() {
    [[ -e "$SYSFS_QUIRKS" ]] || die "sysfs ausente: ${SYSFS_QUIRKS} (usbcore embutido sem param exposto?)"
    migrate_runtime
    if [[ -r "$SYSFS_QUIRKS" ]] && grep -q "$MARKER" "$SYSFS_QUIRKS" 2>/dev/null; then
        info "no-op: quirk já presente em ${SYSFS_QUIRKS}"
        return 0
    fi
    # O sysfs guarda a LISTA INTEIRA de quirks num único valor — escrever
    # SUBSTITUI tudo. Para não sobrescrever quirks pré-existentes de outros
    # devices, mesclamos o valor atual + o nosso. (Acima já retornamos se o nosso
    # marcador já estava presente, então aqui 'current' não contém o nosso.)
    local current new
    current="$(cat "$SYSFS_QUIRKS" 2>/dev/null || true)"
    if [[ -n "$current" ]]; then
        new="${current},${QUIRK_VALUE}"
        warn "já havia quirks em runtime (${current}); mesclando para não sobrescrever"
    else
        new="$QUIRK_VALUE"
    fi
    info "escrevendo o quirk em ${SYSFS_QUIRKS} (best-effort runtime)"
    if printf '%s' "$new" | as_root tee "$SYSFS_QUIRKS" >/dev/null; then
        info "OK — vale SÓ na PRÓXIMA reenumeração/replug do controle e NÃO substitui o cmdline."
        info "desconecte e reconecte o DualSense para o quirk pegar. Para persistir, rode sem --runtime."
    else
        die "falha ao escrever em ${SYSFS_QUIRKS}"
    fi
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
# SEGURANÇA: aborta em argumento DESCONHECIDO (um "--remove" digitado errado
# NUNCA pode cair no apply destrutivo) e em modos CONFLITANTES (ex.: --status
# --remove). Só roda em execução direta (main-guard) — sourcing não dispara nada.
main() {
    local mode="" arg want
    for arg in "$@"; do
        case "$arg" in
            --remove|--delete) want="remove" ;;
            --status|--check)  want="status" ;;
            --runtime)         want="runtime" ;;
            -h|--help)         want="help" ;;
            *) die "argumento desconhecido: ${arg} (use: --remove | --status | --runtime | --help; sem args = aplica)" ;;
        esac
        if [[ -n "$mode" && "$mode" != "$want" ]]; then
            die "modos conflitantes: --${mode} e --${want} (passe só um)"
        fi
        mode="$want"
    done
    mode="${mode:-apply}"

    case "$mode" in
        apply)   do_apply ;;
        remove)  do_remove ;;
        status)  do_status ;;
        runtime) do_runtime ;;
        help)    sed -n '2,53p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

# "A paciência espaça o golpe; é assim que o ferro não trinca." — provérbio da forja
