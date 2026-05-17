# Checklist de validação — release v3.4.0 (2026-05-16)

Itens que precisam **execução manual com hardware ou ambiente real do usuário**
para liberar a release v3.4.0 (i18n EN baseline + acessibilidade ATK +
packaging multi-distro + CI smoke Docker multi-distro).

Marcar `[x]` quando passar; logar evidência quando falhar.

Sucessor de `CHECKLIST_VALIDACAO_v3.2.0.md` (que cobriu a Wave V3.2 de
auditoria + polish). Para histórico antes de v3.2.0, ver
`CHECKLIST_VALIDACAO_v3.md`.

---

## Setup obrigatório antes da validação

- [ ] `git pull origin main` em HEAD que carrega tag `v3.4.0`.
- [ ] `cd ~/Desenvolvimento/hefesto-dualsense4unix && ./install.sh --yes`
      rodou sem erros em Pop!_OS 22.04 (GNOME 42) **ou** Pop!_OS 24.04
      (COSMIC alpha).
- [ ] `ls ~/.local/share/locale/{en,pt_BR}/LC_MESSAGES/hefesto-dualsense4unix.mo`
      mostra ambos os catálogos compilados (passo 4d do install.sh).
- [ ] No COSMIC: `apt list --installed wlrctl 2>/dev/null | grep wlrctl`
      confirma backend Wayland fallback presente.
- [ ] `gnome-extensions list --enabled | grep ubuntu-appindicator` (apenas
      em GNOME) retorna a extension.

---

## Bloco A — i18n EN baseline

### A1 — Catálogos compilados e carregados

- [ ] `msgfmt --statistics po/en.po` reporta `232 mensagens traduzidas, 0
      não traduzidas` (sincronizar contagem com o output real após
      mudanças).
- [ ] `msgfmt --statistics po/pt_BR.po` idem (catálogo de identidade).
- [ ] `LANG=en_US.UTF-8 LANGUAGE=en .venv/bin/python -c "from
      hefesto_dualsense4unix.utils.i18n import _, init_locale; init_locale();
      print(_('Aplicar'))"` imprime `Apply`.
- [ ] `LANG=pt_BR.UTF-8 .venv/bin/python -c "..."` mantém `Aplicar`.

### A2 — GUI roda em EN

- [ ] `LANG=en_US.UTF-8 LANGUAGE=en ./run.sh --gui` abre janela com
      labels EN ("Apply", "Save", "Profile", "Triggers", "Quit",
      "Daemon", "Firmware", "Mouse", "Keyboard").
- [ ] Aba **Triggers** → botões `Apply to L2`, `Disable (Off)` corretos.
- [ ] Aba **Profiles** → seção `Saved profiles` + botões `New`,
      `Duplicate`, `Remove`, `Activate`, `Reload`.
- [ ] Tray icon menu (clicar com botão direito) → entradas em EN
      (`Open panel`, `Profiles`, `Quit Hefesto - Dualsense4Unix`).

### A3 — GUI volta a PT-BR

- [ ] `LANG=pt_BR.UTF-8 ./run.sh --gui` retorna a labels PT-BR original
      (`Aplicar`, `Salvar`, `Perfil`, `Gatilhos`).

### A4 — Compact window (fallback)

- [ ] `HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=1 LANG=en_US.UTF-8
      LANGUAGE=en ./run.sh --gui` mostra labels EN (`Panel`, `Profile`,
      `Quit`) no widget 320x90.

---

## Bloco B — Acessibilidade ATK

### B1 — Screen reader (Orca)

Pré-requisito: `apt install orca` em sessão com a11y stack ativa.

- [ ] `orca --version` retorna `3.x`.
- [ ] Iniciar `orca` em segundo plano. Abrir GUI.
- [ ] Tab até o botão `Aplicar em L2` → Orca anuncia "Aplicar gatilho
      adaptativo no L2, botão" (não "botão sem nome").
- [ ] Idem para botões: `Aplicar em R2`, `Aplicar no controle`
      (lightbar), `Aplicar LEDs`, `Novo`, `Remover`, `Ativar` (perfil),
      `Iniciar`/`Parar`/`Reiniciar` (daemon), `Aplicar firmware`,
      `Aplicar` (footer global).
- [ ] Descrição secundária ("Envia configuração do gatilho esquerdo ao
      controle") é anunciada quando o foco demora >2 s no botão.

### B2 — Navegação por teclado

- [ ] **Tab**: navega entre TODOS os botões da aba ativa em ordem
      visualmente coerente (esquerda→direita, topo→base).
- [ ] **Shift+Tab**: navega reverso.
- [ ] **Enter** ou **Space**: ativa o botão com foco. Toast/ação
      esperada acontece.
- [ ] **Esc**: fecha o diálogo modal de "Salvar Perfil", "Sobrescrever",
      "Restaurar default".
- [ ] **Alt+S**, **Alt+C** etc (mnemonics): disparam botões com
      `_` no label se o tema renderiza mnemonics.

### B3 — High-contrast (palette aumentada)

- [ ] `gsettings set org.gnome.desktop.interface gtk-theme
      "HighContrast"` (GNOME) ou ativar "Contraste alto" em
      Configurações > Acessibilidade.
- [ ] Reabrir GUI. Fundo preto puro `#000`, texto branco `#fff`,
      bordas amarelas `#ff0` (paleta WCAG AAA).
- [ ] Log `theme_high_contrast_aplicado system_theme=HighContrast...`
      aparece em `journalctl --user -u hefesto-dualsense4unix.service`.
- [ ] `gsettings reset org.gnome.desktop.interface gtk-theme` volta ao
      tema Drácula default da v3.x.

---

## Bloco C — Packaging multi-distro

### C1 — PKGBUILD Arch (smoke local)

```bash
docker run --rm -v "$PWD:/src" -w /src archlinux:latest bash -c '
  pacman -Syu --noconfirm base-devel git python python-pip
  cd /src/packaging/arch
  useradd -m builder && chown -R builder:builder /src
  su builder -c "makepkg -si --noconfirm --skipinteg"
  hefesto-dualsense4unix version
'
```

- [ ] Container Arch builda sem erro.
- [ ] `pacman -Q hefesto-dualsense4unix` lista o pacote.
- [ ] `hefesto-dualsense4unix version` retorna `3.4.0`.

### C2 — RPM spec Fedora (smoke local)

```bash
docker run --rm -v "$PWD:/src" -w /src fedora:40 bash -c '
  dnf install -y rpm-build rpmdevtools python3-build python3-pip git
  rpmdev-setuptree
  cp packaging/fedora/hefesto-dualsense4unix.spec ~/rpmbuild/SPECS/
  rpmbuild --build-in-place -bb packaging/fedora/hefesto-dualsense4unix.spec
  rpm -i ~/rpmbuild/RPMS/noarch/hefesto-dualsense4unix-*.rpm
  hefesto-dualsense4unix version
'
```

- [ ] rpmbuild conclui sem erro.
- [ ] `rpm -qa | grep hefesto-dualsense4unix` lista o pacote.
- [ ] Smoke `version` OK.

### C3 — Nix flake (smoke local, opcional)

Só executar se `nix` está instalado no host.

```bash
nix flake check
nix run .#default -- version
```

- [ ] `flake check` passa sem erros.
- [ ] `nix run` retorna `3.4.0`.

---

## Bloco D — CI smoke multi-distro

- [ ] PR aberto com qualquer mudança trivia (ex: bump CHANGELOG)
      dispara workflow `ci.yml`.
- [ ] Job `smoke-multi-distro` aparece com 3 matrix entries:
      `fedora:40`, `archlinux:latest`, `debian:12`.
- [ ] Os 3 entries terminam verdes (instalam wheel + rodam
      `hefesto-dualsense4unix version`).
- [ ] Cache pip ativo (`actions/cache@v4` hit em jobs subsequentes).

---

## Re-validação COSMIC pós-release

Pop!_OS 24.04 COSMIC alpha (cosmic-comp 1.0+):

- [ ] Tray icon aparece dentro de 500 ms (defer COSMIC). Se não
      aparecer, notificação D-Bus opcional informa ausência de
      StatusNotifierWatcher.
- [ ] Cascade Wayland: derrubar portal (`pkill -KILL
      xdg-desktop-portal-cosmic`) → `WaylandCascadeBackend` cai limpo
      para `wlrctl`; auto-switch continua detectando janela ativa.
- [ ] `HEFESTO_DUALSENSE4UNIX_DESKTOP_NOTIFICATIONS=1` → ao
      conectar/desconectar controle e ao trocar perfil, notificações
      D-Bus aparecem na shell COSMIC (com strings traduzidas se
      `LANG=en`).
- [ ] CompactWindow (`HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=1`) usa
      labels EN/PT-BR conforme `LANG`.

---

## Re-validação BT após release

DualSense pareado via Bluetooth (USB desplugado):

- [ ] `bluetoothctl info <MAC>` → `Connected: yes`.
- [ ] `hefesto-dualsense4unix status` → `connected: True transport: bt`.
- [ ] Aplicar perfil `fps` via tray → triggers respondem fisicamente
      via BT.
- [ ] Lightbar muda cor via CLI: `hefesto-dualsense4unix led --color
      "#00FFFF"`.
- [ ] Auto-switch por janela funciona com janela X11 e Wayland (testar
      pelo menos 1 cada).

---

## Validação automatizada (gate de release)

```bash
.venv/bin/pytest tests/unit -q              # >= 1415 passed (baseline v3.4)
.venv/bin/ruff check .                      # All checks passed
.venv/bin/mypy --strict src/hefesto_dualsense4unix
bash -n install.sh scripts/build_deb.sh \
        scripts/build_appimage*.sh \
        scripts/i18n_extract.sh scripts/i18n_compile.sh
.venv/bin/python scripts/validar-acentuacao.py --all
bash scripts/check_anonymity.sh             # exceções: workflow YAML legítimo
bash scripts/i18n_compile.sh                # 232 mensagens × 2 idiomas
```

---

## Artifacts de release

- [ ] `dist/hefesto-dualsense4unix_3.4.0_amd64.deb` presente, instalável
      em `docker run ubuntu:22.04` puro, com `/usr/share/locale/en/...mo`
      bundlado.
- [ ] `dist/appimage/Hefesto-Dualsense4Unix-3.4.0-x86_64.AppImage` (CLI)
      executa `--help` em EN sob `LANG=en_US.UTF-8`.
- [ ] `dist/appimage/Hefesto-Dualsense4Unix-3.4.0-gui-x86_64.AppImage`
      abre janela GTK em sessão real, locale switch funciona.
- [ ] `dist/flatpak/hefesto-dualsense4unix-3.4.0.flatpak` instala via
      `flatpak install --user ...flatpak`; rodar
      `flatpak run br.andrefarias.Hefesto` abre GUI com locale do host.

---

## Pendências herdadas (não bloqueiam v3.4.0)

- [ ] **Aba Mouse**: cursor/scroll com touchpad/giroscópio do DualSense
      end-to-end.
- [ ] **Aba Teclado**: macros e tokens virtuais validados em jogo real.

---

## Backlog forward-looking (v3.5+ / v4.0)

- v3.5+ comunidade: adicionar idiomas (ES, FR, DE) via PRs da
  comunidade — pipeline `scripts/i18n_extract.sh --add LANG` já cobre.
- v3.5+ Wayland-only cleanup: avaliar deprecar XlibBackend agora que
  WaylandCascadeBackend é estável.
- v3.5+ Plasma applet QML: paralelo ao COSMIC applet (sprint 119).
- v4.0 `FEAT-COSMIC-APPLET-RUST-01` (sprint 116): applet Rust +
  libcosmic — aguarda libcosmic estável publicado pelo System76.
- v4.0 `FEAT-COSMIC-GLOBAL-SHORTCUTS-01` (sprint 118): atalhos globais
  via cosmic-settings keybindings.
- v4.0 `FEAT-COSMIC-PANEL-WIDGET-01` (sprint 119): widget rico no
  painel COSMIC.
- v4.0 Flatpak permissions polish: substituir `--device=all` por
  granularidade fina quando freedesktop-sdk publicar.

---

*Gerado durante a release v3.4.0 (i18n EN + a11y + packaging
multi-distro + CI matrix) — base v3.4.0.*
