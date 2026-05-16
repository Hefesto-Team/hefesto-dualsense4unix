# Checklist de validação — release v3.2.0 (2026-05-16)

Itens que precisam **execução manual com hardware ou ambiente real do usuário**
para liberar a release v3.2.0 (wave de auditoria + polish sobre v3.1.1).
Marcar `[x]` quando passar; logar evidência quando falhar.

Para histórico das releases anteriores (v3.0.0 rebrand + v3.1.x hardening
COSMIC + BT validation), consultar `CHECKLIST_VALIDACAO_v3.md`.

---

## Setup obrigatório antes da validação

- [ ] `git pull` em `rebrand/dualsense4unix` no HEAD atual (≥ commit que carrega
      tag `v3.2.0`).
- [ ] `cd ~/Desenvolvimento/hefesto-dualsense4unix && ./install.sh --yes` rodou
      sem erros em Pop!_OS 22.04 (GNOME 42) **ou** Pop!_OS 24.04 (COSMIC alpha).
- [ ] No COSMIC: `apt list --installed wlrctl 2>/dev/null | grep wlrctl` confirma
      backend Wayland fallback presente.
- [ ] `gnome-extensions list --enabled | grep ubuntu-appindicator` (apenas em
      GNOME) retorna a extension.
- [ ] **Logout/login** após install para tray icons recém-habilitados
      renderizarem.

---

## Wave V3.2 — sprints novas

### Bloco A — qualidade de código

#### A1 — PROFILE-LOADER-UX-01 (mensagens de erro acionáveis)

- [ ] Criar perfil malformado:
      `echo '{ broken json' > ~/.config/hefesto-dualsense4unix/profiles/quebrado.json`
- [ ] `hefesto-dualsense4unix profile list` → log `WARN profile_invalid
      path=...quebrado.json err=...` em vez de silêncio.
- [ ] `hefesto-dualsense4unix profile activate quebrado` → erro claro
      `JSON inválido em quebrado.json: <mensagem>` (não `perfil não encontrado`).
- [ ] Criar perfil schema-inválido (campo obrigatório ausente). Mesma cobertura.
- [ ] Remover o `quebrado.json` ao fim do teste.

#### A2 — DAEMON-SHUTDOWN-TEST-01 (teste isolado de shutdown)

- [ ] `.venv/bin/pytest tests/unit/test_daemon_shutdown.py -v` → 3+ casos passam
      isoladamente.
- [ ] Após o teste, `ls /tmp/hefesto-shutdown-test-*` → vazio (sem leaks de
      socket).

#### A3 — PYDANTIC-PROTOCOL-DAEMON-01 (DaemonProtocol substitui Any)

- [ ] `grep -rn "daemon: Any" src/hefesto_dualsense4unix/daemon/` → vazio
      (substituição completa nos 6 arquivos).
- [ ] `.venv/bin/mypy --strict src/hefesto_dualsense4unix` → zero erros.
- [ ] Suite total continua verde (`.venv/bin/pytest tests/unit -q` ≥ 1400 passed).

### Bloco B — documentação

#### B1 — README-URL-BUMP-V3-2-0

- [ ] `grep -n "v3.0.0\|v3.1.0\|v3.1.1" README.md` retorna apenas referências
      históricas (CHANGELOG entries antigos), nenhum `curl -LO` apontando para
      release anterior.
- [ ] `docs/usage/quickstart.md` linha do `.deb` baixa
      `hefesto-dualsense4unix_3.2.0_amd64.deb`.

#### B2 — ADR-STATUS-FIELD-01

- [ ] Cada ADR de `docs/adr/001-*.md` até `013-*.md` tem `**Status:**` no
      header.
- [ ] ADR-007 marcado explicitamente `superseded por ADR-014`.

#### B3 — Este checklist existe e cobre Wave V3.2.

### Bloco C — UI/UX

#### C1 — UI-DAEMON-LOG-AUTOSCROLL-01

- [ ] Abrir GUI → aba **Daemon**.
- [ ] Forçar fluxo de logs: `journalctl --user -u hefesto-dualsense4unix.service
      -f` em outro terminal + `hefesto-dualsense4unix profile activate fps`
      repetido.
- [ ] Log da aba acompanha o final automaticamente (sem scroll manual).

#### C2 — UI-STATUS-OFFLINE-FALLBACK-01

- [ ] `systemctl --user stop hefesto-dualsense4unix.service && pkill -KILL -f
      hefesto-dualsense4unix daemon`.
- [ ] Abrir GUI sem daemon vivo → aba **Status**.
- [ ] Após 5 s (sem nenhum poll bem-sucedido), label exibe
      `Desconectado (clique em Daemon > Start)` em vez de `Consultando...`.

#### C3 — UI-TRIGGERS-LIVE-PREVIEW-01

- [ ] DualSense conectado (USB ou BT).
- [ ] Aba **Gatilhos** → mudar combobox L2 de modo (ex.: `Rigid` → `Pulse`).
- [ ] Sem clicar em **Aplicar**, dentro de ~300 ms o hardware responde (sentir o
      gatilho ao apertar L2) e toast `Trigger aplicado: pulse` aparece no rodapé.

---

## Re-validação COSMIC pós-release

Pop!_OS 24.04 COSMIC alpha (cosmic-comp 1.0+):

- [ ] Tray icon aparece dentro de 500 ms (defer COSMIC). Se não aparecer,
      notificação D-Bus opcional informa ausência de StatusNotifierWatcher.
- [ ] Cascade Wayland: derrubar portal (`pkill -KILL xdg-desktop-portal-cosmic`)
      → `WaylandCascadeBackend` cai limpo para `wlrctl`; auto-switch continua
      detectando janela ativa.
- [ ] `HEFESTO_DUALSENSE4UNIX_DESKTOP_NOTIFICATIONS=1` → ao conectar/desconectar
      controle e ao trocar perfil, notificações D-Bus aparecem na shell COSMIC.
- [ ] `bash scripts/check_wayland_backend.sh` (se existir; senão consultar log
      `wayland_backend=...`) reporta backend ativo coerente com sessão.

---

## Re-validação BT após release

DualSense pareado via Bluetooth (USB desplugado):

- [ ] `bluetoothctl info <MAC>` → `Connected: yes`.
- [ ] `hefesto-dualsense4unix status` → `connected: True transport: bt`.
- [ ] Aplicar perfil `fps` via tray → triggers respondem fisicamente via BT.
- [ ] Lightbar muda cor via CLI: `hefesto-dualsense4unix led --color "#00FFFF"`.
- [ ] Auto-switch por janela funciona com janela X11 e Wayland (testar pelo
      menos 1 cada).

---

## Validação automatizada (gate de release)

```bash
.venv/bin/pytest tests/unit -q              # >= 1400 passed, 14 skipped
.venv/bin/ruff check .                      # All checks passed
.venv/bin/mypy --strict src/hefesto_dualsense4unix
bash -n install.sh scripts/build_deb.sh scripts/build_appimage_gui.sh
.venv/bin/python scripts/validar-acentuacao.py --all
bash scripts/check_anonymity.sh             # exceções: workflow YAML legítimo
```

---

## Artifacts de release

- [ ] `dist/hefesto-dualsense4unix_3.2.0_amd64.deb` presente, instalável em
      `docker run ubuntu:22.04` puro.
- [ ] `dist/appimage/Hefesto-Dualsense4Unix-3.2.0-x86_64.AppImage` (CLI) executa
      `--help` sem erro.
- [ ] `dist/appimage/Hefesto-Dualsense4Unix-3.2.0-gui-x86_64.AppImage` abre a
      janela GTK em sessão real.

---

## Pendências herdadas (não bloqueiam v3.2.0)

- [ ] **#32 GUI quit futex residual** — RESOLVIDO em v3.1.0 (ver
      `CHECKLIST_VALIDACAO_v3.md`); manter monitorado.
- [ ] **Aba Mouse**: cursor/scroll com touchpad/giroscópio do DualSense end-to-end.
- [ ] **Aba Teclado**: macros e tokens virtuais validados em jogo real.
- [ ] **#33 AppImage GUI**: validada em v3.1.1 (43 MB) — repetir smoke em
      ambiente sem GTK do sistema.

---

## Backlog forward-looking (v3.3.0+)

- `FEAT-COSMIC-APPLET-RUST-01` (sprint 116, XL) — aguarda libcosmic estável.
- `FEAT-COSMIC-GLOBAL-SHORTCUTS-01` (sprint 118, M) — aguarda API
  cosmic-settings.
- `FEAT-COSMIC-PANEL-WIDGET-01` (sprint 119, L) — depende de 116.
- P2 da Wave V3.2 (lightbar presets, rumble labels, mnemonics, firmware
  tooltip) — empurrados para v3.3.0.

---

*Gerado durante a Wave V3.2 (auditoria + polish) — base estável v3.2.0.*
