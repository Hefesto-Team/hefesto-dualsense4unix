# ADR-007: Wayland diferido para v1.x

**Status:** superseded por ADR-014 (Suporte ao COSMIC DE / Wayland no Pop!_OS, 2026-04-22)

## Contexto
Wayland não expõe janela ativa via API universal. Cada compositor tem seu próprio método: GNOME usa D-Bus extension, KDE usa KWin script, Sway usa IPC próprio. Implementar os três fura escopo da v0.x.

## Decisão
v0.x e v1.x oficialmente só suportam X11 para auto-switch. Sob Wayland, `get_active_window_info()` retorna `{wm_class: "unknown", ...}` e o matcher cai em `MatchAny` → perfil fallback.

## Workaround para usuários de Wayland
- CLI manual: `hefesto profile activate <nome>`.
- Hotkey via botões do controle (combo sagrado; V2-4).
- Auto-switch por processo: matcher casa quando `process_name` aparecer em qualquer `/proc/*/comm` ativo.

## Consequências
Pop!\_OS 22.04 (padrão X11) funciona 100%. Pop!\_OS COSMIC, GNOME Wayland, KDE Wayland degradam para fallback manual. Suporte Wayland completo é feature request com label `P3-low` até alguém escrever o plugin adequado.
