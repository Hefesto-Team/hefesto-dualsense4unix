# CHECKLIST_MANUAL — Smoke tests com hardware físico

Sprints cujos DoDs exigem DualSense conectado. Revisor com hardware marca `[x]` antes de cada release. Substitui runtime no CI quando validação de hardware é necessária (meta-regra 9.8 do arquivo global do CLI de IA).

---

## W1.3 — Daemon loop básico

- [ ] `hefesto daemon start --foreground` conecta ao DualSense USB, mostra bateria e stick L.
- [ ] `hefesto daemon start --foreground` conecta ao DualSense BT, mostra bateria e stick L.
- [ ] `Ctrl+C` desliga limpo (sem resetar LED ou travar o controle).
- [ ] Desconectar cabo durante execução → daemon loga evento `disconnected` e volta a aceitar nova conexão.

## W2.2 — Trigger effects e rumble

- [ ] Cada um dos 19 modos produz vibração correta em `L2` e `R2` via `hefesto test trigger --mode <X> --side <lado>`.
- [ ] `hefesto led --color FF0080` acende lightbar na cor esperada.
- [ ] Rumble weak/strong independentes; throttle anti-spam não bloqueia comandos legítimos.

## W3.2 — Perfis

- [ ] `hefesto profile activate <nome>` muda efeito no controle em menos de 100ms.
- [ ] `hefesto profile show <nome>` reflete o que está aplicado.

## W4.3 — UDP compat DSX

- [ ] `python examples/mod_integration_udp.py` muda trigger em tempo real.
- [ ] Rate limit dropa com log `warn` quando cliente ultrapassa 1000 pkt/s.
- [ ] `version != 1` no payload gera log `warn` e drop silencioso.

## W5.x — TUI

Cada PR que toca `src/hefesto/tui/**` inclui no body:

- [ ] `scrot /tmp/hefesto_tui_<area>_<ts>.png` anexado.
- [ ] `sha256sum` do PNG registrado.
- [ ] Descrição multimodal de 3–5 linhas cobrindo: elementos visíveis, acentuação PT-BR correta, contraste, layout.

Áreas a cobrir:
- [ ] Screen principal (status do daemon, perfil ativo).
- [ ] Screen de perfis (lista, ativação).
- [ ] Screen de teste de trigger (preview animado).
- [ ] Screen de settings.
- [ ] Status bar com bateria + conexão.

## W6.1 — Window detection X11

- [ ] `hefesto daemon logs` mostra mudança de `wm_class` ao trocar de janela ativa.
- [ ] Lançar Cyberpunk via Steam → log reporta `exe_basename=Cyberpunk2077.exe`.
- [ ] Alt-tab rápido entre 3 janelas não dispara auto-switch (debounce 500ms).

## W6.3 — Gamepad virtual

- [ ] `hefesto emulate xbox360 --on` cria `/dev/input/js*` visível para jogos.
- [ ] Jogo que só reconhece Xbox360 recebe input correto.
- [ ] Combo PS + D-pad troca perfil sem vazar para o uinput (buffer 150ms).
- [ ] `hefesto emulate xbox360 --off` remove o device virtual sem crash.

## W8.1 — Hotkeys

- [ ] Combo configurado em `daemon.toml` troca perfil com janela de jogo em foco.
- [ ] Modo `--unsafe-keyboard-hotkeys` exibe aviso de risco antes de ativar.

---

## Matriz de distros testadas

| Distro          | Versão | USB | BT  | Tray | Observações |
|-----------------|--------|-----|-----|------|-------------|
| Pop!\_OS        | 22.04  | [ ] | [ ] | [ ]  |             |
| Ubuntu          | 22.04  | [ ] | [ ] | [ ]  |             |
| Fedora          | 39     | [ ] | [ ] | [ ]  |             |
| Arch            | rolling| [ ] | [ ] | [ ]  |             |
