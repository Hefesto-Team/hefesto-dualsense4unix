# ADR-007: Wayland diferido para v1.x

**Status:** superseded por ADR-014 (Suporte ao COSMIC DE / Wayland no Pop!_OS, 2026-04-22)

## Contexto
Wayland não expõe janela ativa via API universal. Cada compositor tem seu próprio método: GNOME usa D-Bus extension, KDE usa KWin script, Sway usa IPC próprio. Implementar os três fura escopo da v0.x.

## Decisão
v0.x e v1.x oficialmente só suportam X11 para auto-switch. Sob Wayland, `get_active_window_info()` retorna `{wm_class: "unknown", ...}` e o matcher cai em `MatchAny` → perfil fallback.

## Workaround para usuários de Wayland
- CLI manual: `hefesto profile activate <nome>`.
- Hotkey via botões do controle (combo sagrado; V2-4).
- ~~Auto-switch por processo: matcher casa quando `process_name` aparecer em qualquer `/proc/*/comm` ativo.~~
  **Esta linha nunca foi verdade, e foi SUBSTITUÍDA em 12/08/2026** (PROCESSO-CEGO-01).
  Não existe, e nunca existiu, varredura de `/proc/*/comm` no código: `MatchCriteria.matches`
  compara `process_name` com o `exe_basename` da **janela em foco**, resolvido por
  `os.readlink("/proc/<pid>/exe")` — e isso só acontece no backend `xlib`
  (`window_backends/xlib.py`). Os dois backends de Wayland (`wayland_portal.py`,
  `wlr_toplevel.py`) devolvem `exe_basename=""` **literal**.
  Ou seja: o campo oferecido aqui como *o* workaround de Wayland é justamente o único
  dos três matchers que **não funciona** em Wayland puro — e, como o `matches` é um E
  entre os campos preenchidos, preenchê-lo derruba o perfil inteiro.
  Sob Wayland use `window_class` (vem do `app_id`) ou `window_title_regex`.
  Custo medido da linha errada: cinco perfis de gênero da mantenedora sem ativar
  nenhuma vez em 30 dias de journal (PERFIL-MUDO-01, 10/08/2026).

## Consequências
Pop!\_OS 22.04 (padrão X11) funciona 100%. Pop!\_OS COSMIC, GNOME Wayland, KDE Wayland degradam para fallback manual. Suporte Wayland completo é feature request com label `P3-low` até alguém escrever o plugin adequado.
