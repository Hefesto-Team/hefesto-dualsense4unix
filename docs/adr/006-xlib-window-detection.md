# ADR-006: Detecção de janela ativa via `python-xlib`

**Status:** aceito (continua válido para X11; complementado pelo ADR-014 para Wayland)

## Contexto
Duas alternativas: chamar `xdotool` via `subprocess` ou usar `python-xlib` direto. `subprocess` adiciona overhead e shell-out; `python-xlib` fala com o servidor X nativo, mais rápido e sem risco de command injection.

## Decisão
`python-xlib >= 0.33` com poll a 2Hz. Retorna `{wm_class, wm_name, pid, exe_basename}`. `wm_class` usa o segundo elemento da tupla Xlib (`(instance, class)` → `class`, V3-6), mais estável entre apps Qt/GTK. `exe_basename` via `os.readlink(/proc/PID/exe)` e `os.path.basename`.

## Consequências
Zero shell-out, latência sub-millisegundo. Funciona só em X11; Wayland cai no fallback (ADR-007). Debounce 500ms evita flicker em alt-tab. Apps com `wm_class` e `instance` diferentes obrigam o criador de perfil a escolher o valor correto — documentar `xprop WM_CLASS` no guia de criação de perfis.
