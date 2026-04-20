#!/usr/bin/env bash
# Abre as 26 issues iniciais do roadmap via gh CLI.
# Idempotente: verifica se issue com mesmo titulo ja existe antes de criar.
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
    echo "erro: gh CLI nao encontrado."
    exit 1
fi

# Formato: sprint_id|titulo|labels
issues=(
    "W1.1|Interface IController + backend pydualsense|P1-high,type:feature,ai-task,status:ready"
    "W1.2|Event bus + state store thread-safe|P1-high,type:feature,ai-task,status:ready"
    "W1.3|Daemon loop asyncio basico|P1-high,type:feature,ai-task,status:ready,needs-device"
    "W2.1|Trigger effects - 19 modos com factories|P1-high,type:feature,ai-task,status:ready"
    "W2.2|LED control + rumble com throttle|P2-medium,type:feature,ai-task,status:ready,needs-device"
    "W3.1|Schema de perfil + loader JSON|P1-high,type:feature,ai-task,status:ready"
    "W3.2|Profile manager + CLI profile subcommands|P1-high,type:feature,ai-task,status:ready"
    "W4.1|systemd user service (normal + headless)|P1-high,type:feature,ai-task,status:ready"
    "W4.2|IPC Unix socket (JSON-RPC 2.0)|P1-high,type:feature,ai-task,status:ready"
    "W4.3|UDP server compat DSX com rate limit|P1-high,type:feature,ai-task,status:ready"
    "W5.1|TUI base (Textual) com tema Dracula|P2-medium,type:feature,ai-task,status:ready"
    "W5.2|TUI preview widgets (trigger, battery)|P2-medium,type:feature,ai-task,status:ready"
    "W5.3|CLI completo (typer) com tab completion|P2-medium,type:feature,ai-task,status:ready"
    "W5.4|Tray GTK3 AppIndicator (opcional)|P3-low,type:feature,ai-task,status:ready"
    "W6.1|Window detection X11 (python-xlib)|P2-medium,type:feature,ai-task,status:ready"
    "W6.2|Autoswitch de perfil por janela ativa|P2-medium,type:feature,ai-task,status:ready"
    "W6.3|Gamepad virtual via uinput (Xbox360)|P2-medium,type:feature,ai-task,status:ready,needs-device"
    "W7.1|Release PyPI + pipx|P2-medium,type:infra,ai-task,status:ready"
    "W7.2|AppImage bundle (opcional)|P3-low,type:infra,ai-task,status:ready"
    "W8.1|Hotkeys globais via botoes do controle|P2-medium,type:feature,ai-task,status:ready"
    "W8.2|Docs + release 1.0|P2-medium,type:docs,ai-task,status:ready"
    "W9.1|Exploratorio: esconder HID real (HidHide-like)|P3-low,type:feature,ai-task,status:ready,needs-device"
    "INFRA.1|Benchmark de polling (USB 60Hz vs 120Hz vs 1000Hz)|P3-low,type:infra,ai-task,status:ready,needs-device"
    "INFRA.2|Captures HID determinísticos (USB e BT)|P2-medium,type:test,ai-task,status:ready,needs-device"
    "DOCS.1|Guia de criação de perfis com xprop|P2-medium,type:docs,ai-task,status:ready"
    "DOCS.2|Matriz de compatibilidade por distro|P3-low,type:docs,status:ready"
)

created=0
skipped=0
for entry in "${issues[@]}"; do
    IFS='|' read -r sprint_id title labels <<< "$entry"
    full_title="${sprint_id}: ${title}"

    if gh issue list --search "\"$full_title\" in:title" --state all --json title \
         | grep -q "\"$full_title\""; then
        echo "pulando (ja existe): $full_title"
        skipped=$((skipped+1))
        continue
    fi

    body="Referência: \`HEFESTO_PROJECT.md\` + \`docs/process/HEFESTO_DECISIONS_V2.md\` + \`V3.md\`, sprint **${sprint_id}**."
    gh issue create --title "$full_title" --label "$labels" --body "$body"
    created=$((created+1))
done

echo ""
echo "resumo: criadas=$created puladas=$skipped total=${#issues[@]}"

# "Quem planta no tempo colhe na estacao." — Sêneca
