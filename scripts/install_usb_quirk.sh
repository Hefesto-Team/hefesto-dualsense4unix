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
#   - ESTE script: aplica o quirk usbcore.quirks=054c:0ce6:gn,054c:0df2:gn
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
# DIFERENTE, este script AVISA e NÃO adiciona um segundo às cegas (mescle à mão).
#
# Idempotente (rodar 2x = no-op na 2a; nunca duplica token). Reversível
# (--remove). Bootloaders cobertos: kernelstub (Pop!_OS/System76) e grub.
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
# docs/process/discoveries/2026-06-26-storm-audio-pesquisa-profunda-quirk-vs-audiooff.md.

set -euo pipefail

# Token completo de cmdline (o que entra no kernelstub/grub).
readonly QUIRK="usbcore.quirks=054c:0ce6:gn,054c:0df2:gn"
# Apenas o VALOR (sem o prefixo) — o que o sysfs runtime espera.
readonly QUIRK_VALUE="054c:0ce6:gn,054c:0df2:gn"
# Marcador estável para checagem de presença (idempotência).
readonly MARKER="054c:0ce6:gn"
# Caminhos de config dos bootloaders suportados.
readonly KERNELSTUB_CONF="/etc/kernelstub/configuration"
readonly GRUB_CONF="/etc/default/grub"
readonly SYSFS_QUIRKS="/sys/module/usbcore/parameters/quirks"

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

detect_bootloader() {
    if command -v kernelstub >/dev/null 2>&1; then
        echo kernelstub
    elif [[ -f "$GRUB_CONF" ]]; then
        echo grub
    else
        echo none
    fi
}

# Avisa que há um usbcore.quirks= DIFERENTE e instrui a mesclar à mão.
warn_other_quirk() {
    local where="$1"
    warn "já existe um 'usbcore.quirks=' DIFERENTE em ${where}."
    warn "o kernel respeita só UM token usbcore.quirks= — NÃO vou adicionar um segundo às cegas."
    warn "mescle manualmente num único token, ex.:"
    warn "  usbcore.quirks=<o_que_já_existe>,${QUIRK_VALUE}"
}

# ---------------------------------------------------------------------------
# APLICAR
# ---------------------------------------------------------------------------
apply_kernelstub() {
    if [[ -f "$KERNELSTUB_CONF" ]] && grep -q "$MARKER" "$KERNELSTUB_CONF" 2>/dev/null; then
        info "no-op: quirk já presente em ${KERNELSTUB_CONF} (kernelstub)"
        return 0
    fi
    if [[ -f "$KERNELSTUB_CONF" ]] && grep -q 'usbcore\.quirks=' "$KERNELSTUB_CONF" 2>/dev/null; then
        warn_other_quirk "$KERNELSTUB_CONF"
        return 0
    fi
    info "aplicando via kernelstub: ${QUIRK}"
    as_root kernelstub --add-options "$QUIRK"
    info "feito — vale no PRÓXIMO boot. (--runtime aplica agora, sem reboot, no próximo replug.)"
}

apply_grub() {
    if grep -q "$MARKER" "$GRUB_CONF" 2>/dev/null; then
        info "no-op: quirk já presente em ${GRUB_CONF} (grub)"
        return 0
    fi
    if grep -qE 'usbcore\.quirks=' "$GRUB_CONF" 2>/dev/null; then
        warn_other_quirk "$GRUB_CONF"
        return 0
    fi
    if grep -qE '^[[:space:]]*GRUB_CMDLINE_LINUX_DEFAULT=' "$GRUB_CONF" 2>/dev/null; then
        info "adicionando token a GRUB_CMDLINE_LINUX_DEFAULT em ${GRUB_CONF}"
        # Insere o token logo após a aspa de abertura (idempotente: protegido
        # pelos greps acima). Se o valor estava vazio sobra um espaço à esquerda,
        # inofensivo para o grub.
        as_root sed -i -E \
            "s/^([[:space:]]*GRUB_CMDLINE_LINUX_DEFAULT=\")(.*)(\")/\1${QUIRK} \2\3/" \
            "$GRUB_CONF"
    else
        info "GRUB_CMDLINE_LINUX_DEFAULT ausente — criando a linha em ${GRUB_CONF}"
        printf 'GRUB_CMDLINE_LINUX_DEFAULT="%s"\n' "$QUIRK" | as_root tee -a "$GRUB_CONF" >/dev/null
    fi
    regen_grub
    info "feito — vale no PRÓXIMO boot. (--runtime aplica agora, sem reboot, no próximo replug.)"
}

regen_grub() {
    if command -v update-grub >/dev/null 2>&1; then
        as_root update-grub
    elif command -v grub-mkconfig >/dev/null 2>&1; then
        as_root grub-mkconfig -o /boot/grub/grub.cfg
    else
        warn "nem update-grub nem grub-mkconfig encontrados — regenere o grub.cfg manualmente"
    fi
}

apply_manual() {
    info "bootloader não reconhecido (sem kernelstub e sem ${GRUB_CONF})."
    info "adicione MANUALMENTE este token ao cmdline do seu bootloader (systemd-boot/outro):"
    info "  ${QUIRK}"
    info "ele PRESERVA o áudio do DualSense e mitiga o storm -71. Não é uma regra udev — é cmdline."
    return 0
}

do_apply() {
    case "$(detect_bootloader)" in
        kernelstub) apply_kernelstub ;;
        grub)       apply_grub ;;
        none)       apply_manual ;;
    esac
}

# ---------------------------------------------------------------------------
# REMOVER
# ---------------------------------------------------------------------------
remove_kernelstub() {
    if [[ ! -f "$KERNELSTUB_CONF" ]] || ! grep -q "$MARKER" "$KERNELSTUB_CONF" 2>/dev/null; then
        info "no-op: quirk ausente em ${KERNELSTUB_CONF} (kernelstub)"
        return 0
    fi
    info "removendo via kernelstub: ${QUIRK}"
    as_root kernelstub --delete-options "$QUIRK"
}

remove_grub() {
    if ! grep -q "$MARKER" "$GRUB_CONF" 2>/dev/null; then
        info "no-op: quirk ausente em ${GRUB_CONF} (grub)"
        return 0
    fi
    info "removendo token de ${GRUB_CONF}"
    # Remove só o NOSSO token e normaliza os espaços DENTRO da linha
    # GRUB_CMDLINE_LINUX_DEFAULT (sem tocar em outras linhas nem em outro
    # usbcore.quirks=): tira o token, colapsa espaço duplo e apara as bordas
    # internas das aspas — round-trip limpo (sem espaço órfão).
    as_root sed -i -E \
        "/^[[:space:]]*GRUB_CMDLINE_LINUX_DEFAULT=/{
            s/usbcore\.quirks=054c:0ce6:gn,054c:0df2:gn//g
            s/=\"[[:space:]]+/=\"/
            s/[[:space:]]+\"/\"/
            s/[[:space:]]{2,}/ /g
        }" \
        "$GRUB_CONF"
    regen_grub
}

do_remove() {
    # Limpa AMBOS os backends se seus configs existirem (não confia só no
    # detect_bootloader): se o bootloader mudou depois do apply, evita deixar um
    # token órfão no backend antigo. Cada remove_* é no-op quando o token está
    # ausente, então rodar os dois é seguro e idempotente.
    local did=0
    if [[ -f "$KERNELSTUB_CONF" ]]; then remove_kernelstub; did=1; fi
    if [[ -f "$GRUB_CONF" ]]; then remove_grub; did=1; fi
    if [[ "$did" -eq 0 ]]; then
        info "bootloader não reconhecido — remova MANUALMENTE o token do cmdline:"
        info "  ${QUIRK}"
    fi
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
    [[ "$scheduled" -eq 0 ]] && info "[agendado p/ próximo boot]  não — ausente no config do bootloader"

    # Runtime (sysfs) — vale só na próxima reenumeração/replug.
    if [[ -r "$SYSFS_QUIRKS" ]] && grep -q "$MARKER" "$SYSFS_QUIRKS" 2>/dev/null; then
        info "[runtime sysfs]             sim — em ${SYSFS_QUIRKS} (aplica no próximo replug)"
    else
        info "[runtime sysfs]             não — ${SYSFS_QUIRKS} sem o quirk"
    fi

    info "lembrete: quirk (este) PRESERVA o áudio; é ALTERNATIVA à regra 75 (áudio-off). Use uma OU outra."
    info "caveat: preserva o áudio no nível do KERNEL (sem storm); com os WP 52/53 o nó segue suprimido no PipeWire até removê-los ou definir DUALSENSE_MIC_INTENDED=1"
}

# ---------------------------------------------------------------------------
# RUNTIME (best-effort; não substitui o cmdline)
# ---------------------------------------------------------------------------
do_runtime() {
    [[ -e "$SYSFS_QUIRKS" ]] || die "sysfs ausente: ${SYSFS_QUIRKS} (usbcore embutido sem param exposto?)"
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
        help)    sed -n '2,41p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

# "A paciência espaça o golpe; é assim que o ferro não trinca." — provérbio da forja
