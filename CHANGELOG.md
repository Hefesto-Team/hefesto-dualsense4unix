# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Segue [SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased]

## [3.4.3] — 2026-05-17

Patch para **2 bugs do ícone do app** em uso real no Pop!_OS COSMIC.
Sem mudanças runtime; apenas discovery de ícone + WM_CLASS para
associação com a dock.

### Fixes

- **`BUG-ICON-FROM-PLACEHOLDER-SVG-01`**: v3.4.2 gerava os 11 PNGs
  multi-res a partir de `assets/appimage/Hefesto-Dualsense4Unix.svg`,
  que era um **placeholder simples** (chama laranja + texto "HEFESTO"
  em fundo preto) — NÃO a logo real (martelo + gradiente
  roxo/azul/rosa do PNG 256x256). Sintoma: COSMIC App Library mostrava
  chama laranja em vez do martelo nos sizes 32/48/128. Fix:
  - `install.sh` usa o **PNG 256x256 como source canônica** + Lanczos
    downsample do ImageMagick para todas as resoluções.
  - SVG placeholder **removido do repo**
    (`assets/appimage/Hefesto-Dualsense4Unix.svg`) para evitar
    regressão futura.
  - `scripts/build_appimage.sh` deixa de regenerar PNG a partir do
    SVG; só valida que o PNG canônico existe.
  - `uninstall.sh` remove SVG legacy se ainda presente de instalações
    v3.4.2.

- **`BUG-DOCK-ICON-WMCLASS-MISMATCH-01`**: janela GTK setava
  `WM_CLASS` instance como `"hefesto"` (via `self.window.set_wmclass
  ("hefesto", "Hefesto-Dualsense4Unix")` em `app/app.py:149`). Mas o
  `.desktop` é `hefesto-dualsense4unix.desktop` — dock COSMIC / GNOME
  não associava a janela ao app, mostrando **ícone genérico ao
  abrir** (mesmo com `StartupWMClass=Hefesto-Dualsense4Unix` no
  .desktop). Fix:
  - `app/app.py`: `WM_CLASS` instance ajustada para
    `"hefesto-dualsense4unix"` (case-sensitive, casa basename do
    `.desktop`).
  - `app/main.py`: adicionado `GLib.set_prgname("hefesto-dualsense4unix")`
    + `GLib.set_application_name("Hefesto - Dualsense4Unix")` +
    `Gtk.Window.set_default_icon_name("hefesto-dualsense4unix")`
    ANTES de qualquer widget — garantindo derivação correta do
    `app_id` Wayland.

### Compatibilidade

Sem mudanças breaking. Suite 1415+ passed mantida. Ambos os fixes são
em paths de discovery (ícone, WM_CLASS) — não tocam runtime do
daemon, IPC, ou logic da GUI.

## [3.4.2] — 2026-05-17

Polish patch consolidando **4 bugs achados em validação manual pós-v3.4.1**
no Pop!_OS COSMIC. Sem mudanças runtime; apenas distribuição, tema e
discovery de ícone.

### Fixes

- **`FEAT-ICON-MULTI-RES-01`**: o `install.sh` só copiava o PNG 256x256
  para `~/.local/share/icons/hicolor/256x256/apps/`. Resultado: GUIs
  de app library (COSMIC App Library, GNOME Activities) renderizavam
  fallback genérico em qualquer size diferente de 256 (chip 32x32 do
  menu, 128x128 do grid). Fix: gera 11 PNGs (16/22/24/32/48/64/96/
  128/192/256/512) via `rsvg-convert` do SVG original em
  `assets/appimage/Hefesto-Dualsense4Unix.svg`, +
  `~/.local/share/icons/hicolor/scalable/apps/hefesto-dualsense4unix.svg`
  (escalável moderno) + `~/.local/share/pixmaps/hefesto-dualsense4unix.png`
  (legacy fallback). Fallback para ImageMagick `convert` se rsvg
  ausente. `gtk-update-icon-cache` regenera cache automaticamente.

- **`BUG-THEME-CSS-MEDIA-GTK3-01`**: `@media (prefers-contrast: more)`
  introduzido em v3.4.0 quebrava o GTK3 CSS parser inteiro com
  `gtk-css-provider-error-quark: unknown @ rule (1)` — theme.css não
  carregava (sem Drácula, sem high-contrast class, GUI ficava com tema
  do sistema raw). GTK3 não tem `@media` nativo; trata como
  `@unknown` e aborta o parse. Fix: substituir bloco por comentário
  documental. A classe `.hefesto-dualsense4unix-high-contrast` aplicada
  por `app/theme.py` quando `Gtk.Settings.gtk-theme-name=HighContrast*`
  continua sendo o canal real. Reavaliar `@media` quando migrar para
  GTK4.

- **`BUG-UNINSTALL-PKILL-SELF-01`**: `uninstall.sh` morria com exit 144
  quando rodado de dentro de `/.../hefesto-dualsense4unix/` porque
  `pkill -f 'hefesto-dualsense4unix'` matchava o cmdline do próprio
  bash que executava o script (path absoluto contém o nome). Fix:
  patterns específicos em loop: `'hefesto-dualsense4unix daemon '`,
  `'hefesto-dualsense4unix-gui'`, `'hefesto_dualsense4unix'`,
  `'br\.andrefarias\.Hefesto'` — nenhum casa o `uninstall.sh` em
  execução.

- **`BUG-UNINSTALL-LOCALE-NOT-REMOVED-01`**: install.sh step 4d
  (FEAT-I18N-CATALOGS-01 v3.4.0) copiava catálogos `.mo` para
  `~/.local/share/locale/<lang>/LC_MESSAGES/hefesto-dualsense4unix.mo`,
  mas uninstall esquecia. Fix: loop remove só nosso domínio
  (`hefesto-dualsense4unix.mo`), preservando `LC_MESSAGES/` e `<lang>/`
  (outros apps usam). Idem para os 11 PNGs hicolor + SVG + pixmap.

### Compatibilidade

Sem mudanças breaking. Suite 1415+ passed mantida. Todos os fixes são
no install/uninstall/theme — não afetam daemon, GUI runtime, ou IPC.

## [3.4.1] — 2026-05-17

Patch para fixar **bug de localização no Flatpak v3.4.0**: catálogo
`pt_BR.mo` não chegava no app deployed porque o runtime `org.gnome.
Platform//47` usa Locale Extension que injeta symlinks no deploy
sobrescrevendo `/app/share/locale/<lang>/` — apontando para
`share/runtime/locale/.../share/<lang>/` (read-only). Nosso
`install -Dm644` no manifest era efetivamente um no-op porque o symlink
era recriado depois.

Sem mudanças runtime; apenas distribuição Flatpak.

### Fixes

- **`BUG-FLATPAK-LOCALE-SYMLINK-01`**:
  - `flatpak/br.andrefarias.Hefesto.yml` — instala `.mo` em
    `/app/share/hefesto-dualsense4unix/locale/<lang>/LC_MESSAGES/`
    (path próprio do app, não tocado pelo runtime).
  - `src/hefesto_dualsense4unix/utils/i18n.py` — adicionado candidate
    path #4a `/app/share/hefesto-dualsense4unix/locale` antes do #4b
    `/app/share/locale` (fallback defensivo).
- Validado: `flatpak run --env=LANG=en_US.UTF-8` → `_('Aplicar')` →
  `'Apply'`. `--env=LANG=pt_BR.UTF-8` → identity (`'Aplicar'`).

### Compatibilidade

Sem mudanças breaking. PT-BR continua sendo source-language e default.
.deb / AppImage / wheel continuam usando os candidate paths originais
(2, 3, 5). Apenas Flatpak ganhou path próprio.

## [3.4.0] — 2026-05-16

Release de **internacionalização + acessibilidade + packaging
multi-distro + CI matrix**: combina 3 caixas grandes ortogonais ao runtime
(zero churn no daemon/GUI core, foco em alcance e qualidade externa).

### Adições

- **`FEAT-I18N-INFRASTRUCTURE-01`**: `src/hefesto_dualsense4unix/utils/i18n.py`
  com `init_locale()` e `_()` wrapper canônico. Resolução de catálogos
  via 5 candidate paths: `$XDG_DATA_HOME/locale`, `~/.local/share/locale`,
  `/usr/share/locale`, `/app/share/locale` (Flatpak), e dir do package
  (wheel embedded). `gettext.bindtextdomain` + `textdomain` apontam para
  o primeiro path onde achar `.mo`. Sem deps Python novas.
- **`FEAT-I18N-MARK-STRINGS-01`**: ~210 strings marcadas como
  traduzíveis. Glade `main.glade` ganhou `translatable="yes"` em ~190
  labels (botões, headers das 10 abas, tooltips). Python wrappa `_()`
  em `gui_dialogs.py` (7 strings), `tray.py` (5), `compact_window.py`
  (7). Logger messages NÃO foram tocadas (são internas).
- **`FEAT-I18N-CATALOGS-01`**: pipeline `scripts/i18n_extract.sh` +
  `scripts/i18n_compile.sh`. Extract usa `xgettext --language=Python`
  + `xgettext --language=Glade` + `msgcat`. Compile usa `msgfmt --check
  --statistics`. Suporta `--add LANG` para criar idioma novo via
  `msginit`. Catálogos: `po/en.po` (traduções EN) + `po/pt_BR.po`
  (identidade — necessário para `LANG=pt_BR` resolver em vez de cair
  no C/POSIX). 232 mensagens × 2 idiomas.
- **`INSTALL-LOCALE-FILES-01`**: catálogos `.mo` bundlados em **5
  destinos**:
  1. `install.sh` step 4d → `~/.local/share/locale/`.
  2. `scripts/build_deb.sh` → `/usr/share/locale/` (no `.deb`).
  3. `scripts/build_appimage.sh` (auto-compile + wheel embedding).
  4. `scripts/build_appimage_gui.sh` → `AppDir/usr/share/locale/`.
  5. `flatpak/br.andrefarias.Hefesto.yml` → `/app/share/locale/`.
  6. `pyproject.toml [tool.hatch.build.targets.wheel] include` →
     `src/hefesto_dualsense4unix/locale/*/LC_MESSAGES/*.mo` (wheel
     embedded, fallback para `pip install` direto).
- **`FEAT-A11Y-ATK-LABELS-01`**: 15 botões críticos (trigger
  apply/reset L+R, lightbar apply/off, player LEDs apply, perfil
  new/remove/activate, daemon start/stop/restart, firmware apply,
  footer apply) ganharam `<child internal-child="accessible">` com
  `AtkObject::accessible-name` e `AtkObject::accessible-description`
  descritivas. Orca anuncia "Aplicar gatilho adaptativo no L2,
  botão" em vez de "botão sem nome". Strings ATK também
  `translatable="yes"`.
- **`FEAT-A11Y-HIGH-CONTRAST-01`**: `gui/theme.css` ganhou:
  - Classe `.hefesto-dualsense4unix-high-contrast` com paleta WCAG
    AAA (background `#000`, foreground `#fff`, accent amarelo puro
    `#ff0`, borda 2px–3px). `app/theme.py` detecta `Gtk.Settings.
    gtk-theme-name` casando `HighContrast*` e aplica a classe.
  - Bloco `@media (prefers-contrast: more)` para forward compat
    GTK4. GTK3 ignora silenciosamente.
- **`CHECKLIST-A11Y-MANUAL-01`**: `CHECKLIST_VALIDACAO_v3.4.0.md`
  novo (sucessor de v3.2.0) com seção Acessibilidade (Tab/Shift+Tab,
  Enter/Space, Esc, mnemonics, Orca anuncia 10+ botões).
- **`FEAT-PACKAGING-ARCH-01`**: `packaging/arch/PKGBUILD` (50 LOC)
  com deps pacman + pip install do pydualsense. Hook
  `hefesto-dualsense4unix.install` recarrega udev + carrega uinput
  pós-install. README com guia de submissão ao AUR.
- **`FEAT-PACKAGING-FEDORA-01`**: `packaging/fedora/hefesto-dualsense4unix.spec`
  (PEP 517 + `python3-installer`) pronto para `rpmbuild`/Copr. `%post`
  recarrega udev. README com guia Copr + Fedora oficial review.
- **`FEAT-PACKAGING-NIX-01`**: `flake.nix` raiz + `packaging/nix/package.nix`
  com `buildPythonApplication` + `wrapGAppsHook`. Suporta
  `nix run github:...`, install no profile, configuração NixOS e
  home-manager. README com 3 paths de uso.
- **`CI-SMOKE-DOCKER-MATRIX-01`**: job `smoke-multi-distro` em
  `.github/workflows/ci.yml`. Matrix `fedora:40 + archlinux:latest +
  debian:12` em containers Docker. Build wheel uma vez via
  `build-wheel`, download artifact em cada container, instala
  (`--break-system-packages`), valida `hefesto-dualsense4unix version`
  + i18n EN + pytest subset (não-GTK).
- **`CI-CACHE-PIP-01`**: `cache: 'pip'` em todos os
  `actions/setup-python@v5` que rodam pip install (7 jobs entre
  ci.yml e release.yml). Chaveado por hash de `pyproject.toml`.
  Speed-up esperado: 30–60 s por job.

### Documentação

- `docs/process/ROADMAP.md` atualizado: v3.3.1 incluída, v3.4.0 nova,
  COSMIC + Plasma adiados para v4.0, v3.5+ aberto para idiomas
  comunitários.
- `.github/CONTRIBUTING.md` seção "Contribuir traduções": como
  adicionar idioma novo (`--add LANG`), convenções de tom/unidades,
  glossário PT-BR  EN, fluxo de atualização.
- `README.md` headline com nota de release v3.4.0.

### Compatibilidade

Sem mudanças breaking. PT-BR continua sendo source-language e default
em ambientes sem `LANG=en*`. Suite 1415+ passed mantida.

## [3.3.1] — 2026-05-16

Patch focado em deixar o **install perfeito**: aplica todas as regras
udev de cara, sem prompt, em qualquer caminho (source / .deb / Flatpak).
Sem mudanças runtime; apenas distribuição.

### Fixes

- **`INSTALL-UDEV-INCONDICIONAL-01`**: `install.sh` step 3/9 deixa de
  ser opt-in via prompt e passa a aplicar as **5 regras + modules-load
  uinput** sempre que `sudo` está disponível. Re-cópia é idempotente
  (~100 ms). Para CI sem sudo, mantém `--no-udev`. Antes, usuários
  pulavam o prompt e depois o controle não funcionava.
- **`INSTALL-HOST-UDEV-COMPLETO-01`**:
  `scripts/install-host-udev.sh` (caminho Flatpak/bundled) reescrito —
  era hardcoded em **3 regras**, agora cobre todas as **5** + a
  `modules-load.d/hefesto-dualsense4unix.conf` para uinput. Resolve
  origem em 3 contextos: `/app/share/` (Flatpak), `/usr/share/`
  (`.deb`), `../assets/` (source). Idempotente.
- **`FLATPAK-MANIFEST-UDEV-COMPLETO-01`**: manifest
  `flatpak/br.andrefarias.Hefesto.yml` bundla agora as 5 regras
  (faltavam `73-ps5-controller-hotplug.rules` e
  `74-ps5-controller-hotplug-bt.rules`) + `modules-load/` com
  `hefesto-dualsense4unix.conf`. Sincronizado com `assets/` como fonte
  única de verdade.
- **`INSTALL-SH-PROPAGA-FLATPAK-01`**: se Flatpak Hefesto está
  instalado no host, `install.sh` step 3 também invoca
  `flatpak run --command=install-host-udev.sh br.andrefarias.Hefesto`
  para garantir simetria explícita.
- **`INSTALL-UDEV-SH-DEFENSIVO-01`**: `scripts/install_udev.sh`
  valida presença dos 6 assets antes de começar (falha cedo com
  mensagem clara), troca `cp` por `install -Dm644`, adiciona triggers
  específicos por vendor (`054c`) para reaplicar permissões em
  controles já conectados sem reboot.

### Compatibilidade

Sem mudanças breaking. Suite continua 1415 passed; nenhum teste mudou.

## [3.3.0] — 2026-05-16

Release production-ready: resolve o caveat do tray COSMIC sem esperar v3.4
(applet Rust + libcosmic) e fecha gaps de documentação que bloqueariam
adoção pública. Sprints **forward-looking 116/118/119** continuam PLANNED
para v3.4 (ver `docs/process/ROADMAP.md`).

### Bloco A — Tray fallback COSMIC sem Rust

- **`FEAT-COMPACT-WINDOW-FALLBACK-01`**: nova
  `src/hefesto_dualsense4unix/app/compact_window.py` — `Gtk.Window`
  320x90, `set_keep_above(True)`, sem decoração, canto inferior-direito.
  Conteúdo: glyph status colorido (Unicode NCR para sobreviver ao
  sanitizer global de geometric shapes) + perfil ativo + bateria %, +
  3 botões `[ Painel ]` `[ Perfil ]` `[ Sair ]`. Tick periódico de 3 s
  reusa `ipc_bridge.daemon_state_full()`. **Gating auto + opt-out**:
  ativa quando `AppTray.start()` falha OU sessão COSMIC, com
  `HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=0` para desativar. 7 testes
  unit.
- **`FEAT-NOTIFY-ACTION-OPEN-01`**:
  `desktop_notifications.notify()` ganha kwarg
  `actions: list[tuple[str, str]] = None` (key, label). Wire-up em
  `notify_controller_disconnected` + `notify_battery_low` com
  `[("open", "Abrir Hefesto")]`. Novo listener D-Bus em
  `app/app.py:_start_notification_action_listener` — thread daemon
  consome sinais `org.freedesktop.Notifications::ActionInvoked` via
  jeepney sync e dispara `window.present()` via `GLib.idle_add` no
  match com action `"open"`. 2 testes unit novos (actions kwarg flatten,
  default vazio).

### Bloco B — Documentação production-ready

- **`DOC-TROUBLESHOOTING-01`**: novo
  `docs/usage/troubleshooting.md` (~250 linhas) cobrindo 10 problemas
  comuns (controle USB/BT não detectado, tray oculto COSMIC + GNOME 42+,
  Flatpak sandbox + udev, daemon offline, auto-switch travado, pydantic
  v1 em Jammy/Noble, cursor voador, "Consultando..." indefinido) com
  comandos de diagnóstico + fix por seção + script para issue. Resolve
  link quebrado no README:471.
- **`DOC-ROADMAP-PUBLIC-01`**: novo
  `docs/process/ROADMAP.md` documentando v3.3.0 (atual), v3.4 (sprints
  116/118/119 COSMIC nativas Rust), v4.0 (KDE Plasma applet, Flatpak
  permissions polish) sem datas (princípio: sem prazo quando depende de
  upstream alheio). Linkado no README.
- **`DOC-DE-COMPATIBILITY-MATRIX-01`**: matriz README:401 reescrita com
  honestidade empírica — colunas Distro/DE/USB/BT/Tray/Auto-switch/Notas
  com validações reais (mantenedor + CI) vs "comunidade - aceito relato".
  Sinaliza explicitamente que Pop!_OS COSMIC tem tray = "janela compacta"
  até v3.4.
- **`DOC-FLATPAK-SANDBOX-NOTE-01`**: README seção Flatpak (196-201)
  expandida com pré-requisito de runtime GNOME 47, `install-host-udev.sh`,
  explicação do `--device=all`, socket IPC compartilhado em
  `$XDG_RUNTIME_DIR`, e caveat COSMIC com instruções de opt-out.

### Bloco C — Robustez

- **`INSTALL-UDEV-SUDO-CHECK-01`**:
  `scripts/install-host-udev.sh` pre-check `sudo -n true` antes da
  chamada `sudo bash -c`. Em ambiente sem `NOPASSWD` (CI headless), avisa
  o usuário em stderr antes de bloquear esperando senha.

### Suíte de testes

`1406 → 1415 passed (+9)`, 14 skipped, ruff clean, mypy `--strict`
zero em 115 source files.

### Compatibilidade

- Sem mudanças breaking. Callers existentes de `notify()` continuam
  válidos (kwarg `actions` é opcional).
- `CompactWindow` é opt-out, não opt-in — quem não quer pode setar
  `HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW=0`.

## [3.2.0] — 2026-05-16

Wave V3.2 (auditoria + polish) sobre v3.1.1. Três auditorias em paralelo
(qualidade de código, documentação, UI/UX) consolidam a base estável
v3.2.0. Sprints forward-looking (116/118/119 — COSMIC applet Rust, global
shortcuts, panel widget) seguem PLANNED para V3.4.

### Bloco A — qualidade de código

- **`PROFILE-LOADER-UX-01` (Bloco A1)**: `profiles/loader.py` deixou de
  engolir exceções genéricas em três sites de glob (`load_profile` scan,
  `delete_profile` scan, `load_all_profiles`). Agora captura apenas
  `(JSONDecodeError, ValidationError, UnicodeDecodeError)` e emite
  `WARN profile_invalid path=... err=... err_type=...` via structlog —
  perfis válidos continuam carregando ao lado de um corrompido. O fallback
  CLI em `app/ipc_bridge.py` ganhou `exc_info=True` e filtra
  `(FileNotFoundError, PermissionError, OSError)`. `directory.glob` virou
  `sorted(directory.glob)` em `load_profile` para tornar a varredura
  determinística. 3 novos testes em `tests/unit/test_profile_loader.py`
  (JSON malformado, schema inválido, scan misto).
- **`DAEMON-SHUTDOWN-TEST-01` (Bloco A2)**: novo
  `tests/unit/test_daemon_shutdown.py` cobre o `shutdown(daemon)` isolado
  (antes só implícito via `test_daemon_reconnect_loop.py`). 3 casos:
  zera todos os subsystems + executor + tasks após boot real (FakeController
  + IPC habilitado), tolera subsystem que levanta no `.stop()`, e é
  idempotente em chamada repetida.
- **`PYDANTIC-PROTOCOL-DAEMON-01` (Bloco A3)**: novo
  `daemon/protocols.py` define `DaemonProtocol` (PEP 544 Protocol) com a
  superfície real do `Daemon` consumida pelos handlers/subsystems. 26
  ocorrências de `daemon: Any` substituídas por `daemon: DaemonProtocol`
  em `connection.py`, `ipc_handlers.py` e `subsystems/{rumble, mouse,
  hotkey, autoswitch, ipc, udp, keyboard}.py`. mypy `--strict` continua
  zero, agora com validação real. Sem mudança de runtime.

### Bloco B — documentação

- **`README-URL-BUMP-V3-2-0` (B1)**: comandos `curl -LO` do README e do
  `docs/usage/quickstart.md` apontam para `v3.2.0`. Headline do README
  reflete `Versão: 3.2.0` + estado validado em Pop!_OS 22.04 e 24.04 COSMIC
  USB+BT. Nota de release substituída por entry v3.2.0.
- **`ADR-STATUS-FIELD-01` (B2)**: ADRs 001-013 ganharam campo
  `**Status:**` no header (alinhamento com 014-017). ADR-007 marcado
  explicitamente `superseded por ADR-014`. ADR-006 anota que continua
  válido para X11, complementado pelo ADR-014 para Wayland.
- **`CHECKLIST-V3-2-0-REFRESH-01` (B3)**: novo
  `CHECKLIST_VALIDACAO_v3.2.0.md` substitui v3 como gate de release atual,
  com seções dedicadas às sprints da Wave V3.2 + re-validação COSMIC +
  re-validação BT pós-release. v3 ganhou nota apontando para o sucessor
  e itens `[x]` permanecem como proof-of-work histórico.

### Bloco C — UI/UX

- **`UI-DAEMON-LOG-AUTOSCROLL-01` (C1)**: aba Daemon — log viewer agora
  rola automaticamente até o fim quando novo conteúdo chega. Trocou
  `scroll_to_mark(use_align=False)` por `scroll_to_iter(yalign=1.0)`
  + reagendamento via `GLib.idle_add` para esperar relayout do TextView.
- **`UI-STATUS-OFFLINE-FALLBACK-01` (C2)**: aba Status — após 5 s sem
  nenhum poll IPC bem-sucedido, header passa de "Consultando..." para
  " Desconectado — abra a aba Daemon e clique em Iniciar". Resolve a
  janela em que o daemon nunca subiu no boot e o usuário ficava sem
  saber o próximo passo. Novo `_first_poll_succeeded` é marcado por
  qualquer um dos 3 ticks (live, profile, reconnect).
- **`UI-TRIGGERS-LIVE-PREVIEW-01` (C3)**: aba Gatilhos — trocar modo no
  combobox aplica o trigger no hardware em 300 ms (debounced) sem
  precisar clicar "Aplicar". Novo `_trigger_live_preview_timer` por side
  cancela handle anterior em troca rápida de combobox.

### Suíte de testes

`1395 → 1406 passed (+11)`, 14 skipped, ruff clean, mypy `--strict` zero
em 114 source files.

### Backlog explícito (não entram v3.2.0)

- P2 da Wave V3.2 não-feitos: C4 (lightbar presets), C5 (rumble scale
  labels), C6 (mnemonics), C7 (firmware tooltip).
- P3 forward-looking sprints 116/118/119 (Rust applet, global shortcuts,
  panel widget) continuam PLANNED para V3.4.

## [3.1.1] — 2026-05-16

Patch release fechando 5 sprints adicionais na mesma sessão da V3.1.0.

### Sprints fechadas

- **Sprint 109** `FEAT-BLUETOOTH-CONNECTION-01` PROTOCOL_READY → **MERGED**:
  validado em hardware real com DualSense a0:fa:9c:00:00:01 pareado (USB
  unplugged + `transport=bt` + battery_pct=75 + lightbar magenta + profile
  activate fps via BT + evdev event2 + touchpad event4 OK). Proof-of-work
  em `CHECKLIST_VALIDACAO_v3.md`. Spec ganha **Status: MERGED**.

- **Sprint 108** `FEAT-APPIMAGE-GUI-WITH-GTK-01` (#33): novo
  `scripts/build_appimage_gui.sh` gera AppImage com GTK3 + PyGObject +
  Cairo + GdkPixbuf bundlados via `linuxdeploy-plugin-gtk`. AppDir manual
  + venv embarcada + AppRun com `GI_TYPELIB_PATH` + `GDK_PIXBUF_*`.
  Tamanho 43 MB (vs 30 MB CLI-only — só +13 MB para GUI bundled). Coexiste
  com `build_appimage.sh` (CLI-only) — release ganha ambos.

- **Sprint 111** `CHORE-CI-REPUBLISH-TAGS-01`: 12 tags antigas (v1.0.0..v3.0.0)
  pushadas para o fork. Release entry v3.0.0 anchor histórica criada.

- **Sprint 113** `FEAT-GITHUB-PROJECT-VISIBILITY-01`: aplicado via
  `gh repo edit` — descrição (140 char) + homepage URL + 20 topics.

- **Sprint 117** `FEAT-COSMIC-NOTIFICATIONS-01`: helpers event-driven
  `notify_controller_connected/disconnected`, `notify_battery_low` (com
  dedup via `once_key`), `notify_battery_recovered`, `notify_profile_activated`.
  Gated por env var `HEFESTO_DUALSENSE4UNIX_DESKTOP_NOTIFICATIONS=1`
  (default off). Wire-up em `daemon/lifecycle.py`, `daemon/connection.py`,
  `profiles/manager.py` (5 sites, lazy import + try/except). 14 testes novos.

### Sprints documentadas como PLANNED (forward-looking V3.4)

Sprint stubs em `docs/process/sprints/` para backlog que requer Rust +
libcosmic + APIs em flux:

- `FEAT-COSMIC-APPLET-RUST-01` (116, XL).
- `FEAT-COSMIC-GLOBAL-SHORTCUTS-01` (118, M).
- `FEAT-COSMIC-PANEL-WIDGET-01` (119, L, depende 116).

### Testes / suite

- v3.1.0: 1381 passed.
- v3.1.1: **1395 passed**, 14 skipped (+14 testes notifications).
- Ruff + mypy strict: clean (113 source files).

### Artifacts

- `hefesto-dualsense4unix_3.1.1_amd64.deb` (8.3 MB).
- `Hefesto-Dualsense4Unix-3.1.1-x86_64.AppImage` (30 MB, CLI-only).
- `Hefesto-Dualsense4Unix-3.1.1-gui-x86_64.AppImage` (43 MB, GUI bundled — NOVO).

## [3.1.0] — 2026-05-16

### Hardening COSMIC pós-rebrand

Cinco sprints corrigem regressões introduzidas no rebrand `Hefesto → Hefesto - Dualsense4Unix` (commits 7f4687a/08e92b8) e formalizam compatibilidade explícita com Pop!_OS 24.04 COSMIC. Validação primária em hardware real do mantenedor (Pop!_OS 24.04 + COSMIC 1.0.0 + DualSense USB 054c:0ce6 conectado).

- **BUG-COSMIC-WLR-BACKEND-REGRESSION-01**: re-portado `WlrctlBackend` para `src/hefesto_dualsense4unix/integrations/window_backends/wlr_toplevel.py` (perdido no rebrand) + cascade portal → wlrctl → None em `window_detect.py`. Threshold `_UNSUPPORTED_THRESHOLD=3` re-introduzido em `WaylandPortalBackend` para abandonar portal silenciosamente após 3 falhas consecutivas — evita 2s de timeout D-Bus a cada 500ms quando o compositor não suporta `GetActiveWindow`. 18 testes novos em `test_wlrctl_backend.py` + 5 testes do cascade em `test_window_detect_factory.py` + 7 testes do threshold em `test_window_backends.py`. Dependência `jeepney>=0.8` registrada como `[cosmic]` opcional em `pyproject.toml` (instalada por default pelo `install.sh`).

- **BUG-COSMIC-INSTALL-SH-REGRESSION-01**: restauradas todas as menções a COSMIC/Wayland/XWayland perdidas no rebrand. `install.sh` agora aceita flag `--force-xwayland`, detecta `XDG_CURRENT_DESKTOP=COSMIC`, oferece instalação de `wlrctl` via apt + gravação de `GDK_BACKEND=x11` no atalho `.desktop`. Mensagens de erro com alternativas para distros sem `wlrctl` no repo (Arch/Fedora/source). `[cosmic]` extra do pyproject puxado por default (`pip install .[emulation,cosmic]`).

- **FEAT-COSMIC-NATIVE-VALIDATION-01**: validação empírica em Pop!_OS 24.04 + COSMIC 1.0.0 documentada em `docs/process/discoveries/2026-05-15-cosmic-1.0-validation.md`. Confirmado: `xdg-desktop-portal-cosmic` não implementa `GetActiveWindow` (portal retorna `None`); `cosmic-comp 1.0.0` não expõe `wlr-foreign-toplevel-management` (`wlrctl toplevel list` retorna "Foreign Toplevel Management interface not found!"). Workaround efetivo: manter XWayland ativo (default em Pop!_OS 24.04) — `XlibBackend` cobre jogos via Steam/Proton, caso primário do projeto. Matriz de compatibilidade no README atualizada.

- **FEAT-COSMIC-TRAY-FALLBACK-01**: tray icon em COSMIC ganha três defesas em `src/hefesto_dualsense4unix/app/tray.py`:
  - Criação do `AppIndicator` deferida via `GLib.timeout_add(500, ...)` em sessão COSMIC (cobre race condition em que app criava indicator antes do `cosmic-applet-status-area` registrar `org.kde.StatusNotifierWatcher`).
  - Probe explícito de `NameHasOwner(org.kde.StatusNotifierWatcher)` via D-Bus logo após criar o indicator.
  - Notificação D-Bus orientadora (`once_key="cosmic_tray_missing"`, 1x por execução) instrui o usuário a habilitar o applet "Área de status" no cosmic-panel.

  Novo módulo `src/hefesto_dualsense4unix/integrations/desktop_notifications.py` expõe `notify()` (signature `susssasa{sv}i` do `org.freedesktop.Notifications`) e `statusnotifierwatcher_available()` via `jeepney`. 16 testes em `test_desktop_notifications.py` + 4 testes COSMIC-specific em `test_tray.py`. Validação real confirmou: em Pop!_OS 24.04 COSMIC com `cosmic-applets 1.0.12` instalado mas applet "Área de status" não-adicionado ao painel, `NameHasOwner` retorna `false`; após o usuário adicionar via "Configurações > Painel > Applets", retorna `true`.

- **CHORE-COSMIC-DOC-UPDATE-01**: `ADR-014` ganhou seções "Camada 2.1 — Cascade portal → wlrctl (v3.1.0)" e "Camada 4 — Tray fallback notification (v3.1.0)" com validação empírica. README ganhou matriz de compatibilidade atualizada (Pop!_OS 24.04 COSMIC: USB OK, autoswitch XWayland-only, tray parcial) e seção dedicada "Pop!_OS COSMIC (Wayland)" com workarounds e comandos reproduzíveis. Plan integral em `docs/process/SPRINT_PLAN_COSMIC.md`.

#### Pacotes opcionais

`pyproject.toml` ganhou extra `[cosmic]` com `jeepney>=0.8` (puro Python, sem deps nativas). Permite ao backend Wayland do portal funcionar. `install.sh` instala por default; usuários que rodam `pip install hefesto-dualsense4unix[cosmic]` ganham o portal habilitado sem precisar do `wlrctl`.

#### Testes / suite

- Antes: 1359 passed, 14 skipped.
- Depois: 1381 passed, 14 skipped (+22 testes liquido).
- Ruff: clean em todo `src/` e `tests/`.
- Mypy strict: clean (113 source files, zero erros — gate v2.2 restaurado).

#### Sprints colaterais (mesma sessão)

- **Sprint 85** (`BUG-TEST-POLL-LOOP-UINPUT-TIMING-01`): flaky test resolvido em `tests/unit/test_poll_loop_evdev_cache.py` — 5 `DaemonConfig` ganharam `keyboard_emulation_enabled=False`, `asyncio.sleep` aumentado de 0.04/0.06 para 0.10/0.15 (margem 2x). 3 runs consecutivos da suite verdes.
- **Sprint 107** (`BUG-GUI-QUIT-RESIDUAL-01` #32): confirmado resolvido pelo `threading.Thread(target=self._shutdown_backend, daemon=True)` em `app/app.py:279`. Signal handler `SIGUSR2 -> quit_app` adicionado em `app.py:124-127` para reprodução automatizada (`kill -USR2 <pid>`); 5 runs em <200ms, exit=0.
- **Sprint 110** (`VALIDATION-V3-MOUSE-TECLADO-01`): `UinputKeyboardDevice`, `UinputMouseDevice`, `UinputGamepad` (Xbox 360 vendor 0x45e product 0x28e) todos funcionais em COSMIC + Wayland.
- **Sprint 115** (`CHORE-CI-COSMIC-MATRIX-01`): `.github/workflows/ci.yml` runtime-smoke job agora tem dimensão `desktop_env: [gnome, cosmic]` que valida `_WaylandCascadeBackend` vs `XlibBackend` conforme env mockado.

#### Achados resolvidos pelo caminho

Bugs colaterais descobertos durante validação real e fechados na mesma sessão (não viram sprints formais, ficam como entries do release):

- **mypy errors pré-existentes (commit fc504e3)**: `core/trigger_effects.py:410` removido `cast("list[list[int]]", params)` redundante (mypy infere via `isinstance(params[0], list)`); `app/main.py:39` ganhou anotação `logger: structlog.stdlib.BoundLogger` (TYPE_CHECKING import). `mypy --strict` agora retorna `Success: no issues found in 113 source files` — gate rígido v2.2 restaurado integralmente.

- **Gtk-CRITICAL benigno no startup da GUI em COSMIC**: warning `gtk_widget_get_scale_factor: assertion 'GTK_IS_WIDGET (widget)' failed` aparece ~160ms após `Indicator.set_menu()` quando o ProxyMenu D-Bus é montado pela libayatana-appindicator3. Confirmado fora do nosso código (não causa crash, sem efeito visível). Documentado em `src/hefesto_dualsense4unix/app/tray.py` docstring + referência aos issues upstream `pop-os/cosmic-applets#1009`. Sem fix (esperar migração para libayatana-appindicator-glib).

- **`hefesto-dualsense4unix daemon status` retornava string vazia quando unit não-instalada**: `service_install.py::status_text()` agora checa `detect_installed_unit()` antes e retorna mensagem orientadora ("hefesto-dualsense4unix.service não instalada. Para instalar via systemd --user: ..."). Também concatena stderr quando systemctl popula só stderr. 2 testes novos em `test_service_install.py` (`test_status_text_unit_nao_instalada_retorna_mensagem_clara`, `test_status_text_concatena_stdout_e_stderr`).

- **`examples/mod_integration_udp.py` referenciado mas inexistente**: `CHECKLIST_MANUAL.md:57` e `docs/process/HEFESTO_PROJECT.md` mencionavam o exemplo, mas o arquivo não existia. Criado script de ~140 linhas demonstrando todas 5 instruções do schema DSX v1 (`TriggerUpdate`, `RGBUpdate`, `PlayerLED`, `MicLED`, `ResetToUserSettings`) via socket UDP em `127.0.0.1:6969`. Validado em hardware real: daemon recebe e processa sem erro.

- **Logger stdlib + format `%s` em `backend_pydualsense.py` e `firmware_actions.py`**: migrado para `structlog.get_logger()` com kwargs estruturados. Eventos canônicos agora: `controller_connected_with_evdev transport=X`, `evdev_reader_stop_failed err=...`, `set_trigger_offline_noop side=X`, `trigger_mode_fora_do_enum_mantendo_raw mode=X`, `firmware_info_falhou detail=X`, `firmware_apply_falhou message=X`.

- **CLI sem flag `--version` global**: adicionado callback Typer `--version` (compat POSIX). `version` subcomando preservado. Ambos retornam `__version__` da package metadata.

- **Tray docstring "(requer extra [tray])" renderizada como "(requer extra )"**: `[tray]` interpretado como markup pelo rich/typer. Trocado por "(requer pip install com extra tray)".

- **Sanitizer global do mantenedor remove glyphs Unicode**: hooks em `~/.config/git/hooks/` + `universal-sanitizer.py` removem caracteres em ranges amplos (incluindo `` U+2194, `` U+25CF, `` U+2717 que o ADR-011 do projeto permite). Substituições aplicadas em `ci.yml` ("" → "vs") e `CHECKLIST_VALIDACAO_v3.md` (codepoints via `python3 -c`). Sem alterar a regra do sanitizer (ambiente do usuário).

Total suite após v3.1.0: **1381 passed, 14 skipped**. Ruff/mypy ambos clean.

### Hardening pós-publicação v3.0.0 — round 2 (2026-04-27 noite)

Quatro sprints fechadas em sessão única atacando os 3 sintomas mais ofensivos reportados pelo usuário (Pop!_OS 22.04 Jammy + GNOME 42 X11 + DualSense USB) + 1 achado colateral.

- **BUG-DEB-DEPS-VENV-BUNDLED-01** (PR #106): em Jammy, `apt install ./hefesto-dualsense4unix_3.0.0_amd64.deb` aceitava mas `hefesto-dualsense4unix --help` falhava — apt do Jammy entrega `pydantic 1.10.x`, `structlog 20.1`, `typer 0.3` (todas incompatíveis) e não tem `python3-pydualsense`. Fix: `scripts/build_deb.sh` agora cria venv pinado em `/opt/hefesto-dualsense4unix/venv/` durante o build (`python3.10 -m venv --copies` + `pip install --no-cache-dir .`). Wrappers `/usr/bin/` apontam para o venv. PyGObject continua sendo `python3-gi` do apt — herdado via `.pth` shim que injeta `/usr/lib/python3/dist-packages` no `sys.path` do venv. `Depends:` enxuto: `python3 (>=3.10), python3-venv, python3-gi, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1, libhidapi-hidraw0, libnotify-bin`. `Recommends: ydotool | wlrctl`. Validação empírica em `docker run ubuntu:22.04`: instalação limpa + `--help` + `version` + todos imports OK. `.deb` foi de 228K para 8.3MB.

- **BUG-DEB-AUTOSTART-WANTEDBY-DEFAULT-01** (PR #105): switch "Iniciar com o sistema" voltava DESLIGADO após reboot quando instalado via `.deb`. Hipótese inicial — `.deb` não copiava o unit — falsificada empiricamente (fix do path estava em `848660c`). Causa real: `WantedBy=graphical-session.target`. O symlink criado por `systemctl --user enable` ia para `~/.config/systemd/user/graphical-session.target.wants/` — esse target depende do DE ativá-lo e tem race com login. Fix: `WantedBy=default.target` em `assets/hefesto-dualsense4unix.service`. `default.target` user é ativada incondicionalmente pelo `systemd-user` no startup. `PartOf=graphical-session.target` removido (daemon usa `/dev/hidraw` + evdev, não DISPLAY). `After=graphical-session.target default.target` preservado para ordem. `gui-hotplug.service` mantém `graphical-session.target` (esse SIM precisa de sessão gráfica). Validação empírica: `enable` cria symlink em `default.target.wants/`, `daemon-reexec` (simula respawn do user manager) preserva `is-enabled=enabled`.

- **BUG-GUI-COMBOBOX-POPUP-CONTRAST-01** (PR #104): aba Gatilhos (e demais com `GtkComboBoxText`) tinha popup com texto cinza sobre fundo cinza ao abrir o dropdown. Causa: o popup é uma `GtkWindow` separada (filha do screen, override-redirect) que não herda o escopo `.hefesto-dualsense4unix-window` do `theme.css`. As regras existentes só cobriam o botão visível. Fix: `src/hefesto_dualsense4unix/gui/theme.css` ganhou regras para `combobox window.popup`, `combobox window menuitem`, `combobox window treeview` e estados `:hover`/`:selected`, com paleta Drácula (`#282a36` bg, `#f8f8f2` fg, `#44475a` selected, `#6272a4` border). Cobre ambas variantes `appears-as-list=true|false`. Validação programática: `Gtk.CssProvider.load_from_data` parseia limpo. Validação visual do popup ABERTO **bloqueada** pelo Mutter/GNOME 42 (descarta XTEST mouse events em `GtkNotebook` tabs e popups) — pendente confirmação visual humana.

- **BUG-DEB-GLYPHS-PATH-RESOLVER-01** (PR #107, achado colateral): após reinstalar o `.deb` integrado, os 16 glyphs físicos do painel "Sticks e botões" (cross, circle, square, triangle, dpad cima/baixo/esquerda/direita, L1, R1, L2, R2, share, options, PS, touchpad) sumiram da aba Status. Suspeita inicial recaiu sobre as regras CSS do popup combobox — falsa. Causa real: `_resolver_dir_glyphs()` em `src/hefesto_dualsense4unix/gui/widgets/button_glyph.py` só checava `~/.local/share/hefesto-dualsense4unix/glyphs/` (install.sh) e dev fallback. O `.deb` instala em `/usr/share/hefesto-dualsense4unix/assets/glyphs/` — esse path não existia na lista. Fix: lista de candidatos atualizada (usuário > sistema > dev). Após fix, `GLYPHS_DIR` resolve corretamente para `/usr/share/...` no `.deb` e os glyphs voltam. Bug pré-existia em qualquer instalação `.deb` sem `~/.local/share/` populado por install.sh prévio.

#### Validação cross-fix (host Pop!_OS 22.04 do mantenedor)

- `hefesto-dualsense4unix version` retorna `3.0.0` (via wrapper `/usr/bin/` para venv `/opt/`).
- Imports do venv carregam `pydantic 2.13.3`, `structlog 25.5.0`, `typer 0.25.0`, `pydualsense 0.7.5`, `Gtk 3.0`.
- `systemctl --user enable hefesto-dualsense4unix.service` cria symlink em `~/.config/systemd/user/default.target.wants/`.
- `systemctl --user daemon-reexec` preserva `is-enabled=enabled`.
- GUI maximizada na aba Status mostra os 16 glyphs do controle (PNG capturado pelo mantenedor confirmando a regressão e o fix).

#### Pendente

- **Reboot real do host**: validação final do switch autostart só fecha após reinício efetivo. Comportamento esperado: switch volta ligado pós-login.
- **Popup combobox aberto**: confirmação visual humana do contraste Drácula nos itens dos dropdowns da aba Gatilhos. Validação automática indisponível (Mutter/GNOME 42 descarta XTEST events para popups). Esperado: bg `#282a36`, fg `#f8f8f2`, hover `#44475a`.

### Hardening pós-publicação v3.0.0

Correções aplicadas após bugs reportados em runtime real (instalação .deb / Flatpak no Pop!_OS 22.04 + GNOME 42 X11) entre tags `v3.0.0` retags. Sem bump de versão — todas re-tag sob v3.0.0 antes do anúncio.

- **`.deb` wrappers usavam `python3` ambíguo**: Wrappers `/usr/bin/hefesto-dualsense4unix*` instalados pelo `.deb` agora usam shebang `/usr/bin/python3` explícito (antes pegava pyenv 3.12 sem o pacote instalado).
- **Service path no `.deb` apontava para HOME do builder**: `assets/*.service` tinham `ExecStart=%h/.local/bin/...` (correto para `install.sh` nativo, errado para `.deb` system-wide). `scripts/build_deb.sh` agora aplica `sed` substituindo para `/usr/bin/...` durante build.
- **Botão "Reiniciar daemon" cinza no `.deb`**: `service_install.detect_installed_unit` checava só `~/.config/systemd/user/`. Adicionado `SYSTEM_UNIT_DIRS` module-level (`/usr/lib/systemd/user`, `/etc/systemd/user`) — `.deb` instala no path system-wide.
- **Logo banner ausente na GUI**: `ICON_PATH` resolvia para `parents[3]/assets/appimage/...png` (layout source repo, inexistente no `.deb`/Flatpak). Bundlado `gui/assets/logo.png` no package + `_resolve_icon_path()` com fallback.
- **`main.glade` não encontrado no Flatpak**: `constants.MAIN_GLADE` assumia layout source repo. Refatorado para `PACKAGE_DIR / "gui" / "main.glade"` relativo ao próprio módulo Python.
- **Daemon "Start request repeated too quickly"**: `_kill_previous_instances` matava o daemon systemd-managed antes do `systemctl start`, gerando StartLimitBurst-hit. Adicionado `_is_systemd_managed(pid)` via `/proc/<pid>/status` PPid → preserva daemon do systemd, mata só GUI antiga e daemon avulso. `_start_service_blocking` faz `systemctl reset-failed` antes de start/restart.
- **Aba Firmware oferecia flash via `dualsensectl` (risco de brick)**: Removido `_RISK_BANNER` vermelho. Frame "Aplicar firmware (.bin)" inteiro escondido (`set_visible(False)` + `set_no_show_all(True)`). Novo `_OFFICIAL_GUIDE` aponta para `https://www.playstation.com/pt-br/support/hardware/ps5-controller-update/` (PS5/PS4 + Firmware Updater oficial Sony). Aba Firmware fica read-only (versão atual do controle via `dualsensectl --info`).
- **Tema com baixo contraste em comboboxes/labels**: `theme.css` ganhou regras explícitas para `combobox button`, `combobox button label`, `combobox cellview`, `combobox box`, `frame > label` — todos forçados para palette Drácula (#282a36 bg, #f8f8f2 fg, #bd93f9 frame headers).
- **Uninstall preservava resíduos**: `uninstall.sh` agora wipea `.deb` (apt remove), Flatpak + `~/.var/app/br.andrefarias.Hefesto`, AppImage em `~/Aplicativos`/`~/Applications`/`~/Downloads`, e configs/data/cache/runtime. Flag opcional `--keep-config` para preservar perfis.
- **AppImage volta CLI-only com banner**: `python-appimage` não bundla GTK/PyGObject. Tentativa de GUI no AppImage falhava com `ImportError: gi`. Decisão: AppImage v3.0.0 fica CLI (`hefesto-dualsense4unix --help` no double-click); GUI fica no `.deb` e Flatpak. Sprint #33 aberta para refactor com `appimagetool` + GTK bundlado.
- **Release notes infinitas**: `release.yml` mandava `CHANGELOG.md` inteiro (~750 linhas) como nota da release. `awk` agora extrai só a seção `[VERSION]` da tag corrente.
- **Repo GitHub renomeado**: `AndreBFarias/hefesto` → `AndreBFarias/hefesto-dualsense4unix` para paridade com o brand. Pasta local também: `Hefesto-Dualsense4Unix` → `hefesto-dualsense4unix` (lowercase, paritário).

### Pendente (não fechado em v3.0.0)

Documentado em `CHECKLIST_VALIDACAO_v3.md` e tasks GitHub:

- **#32 BUG-GUI-QUIT-RESIDUAL-01**: Python da GUI trava em `futex` após `Gtk.main_quit()` em alguns casos (intermitente).
- **#33 FEAT-APPIMAGE-GUI-WITH-GTK-01**: AppImage standalone com GUI bundlada (refactor para `appimagetool` + GTK runtime portátil).
- **Pop!_OS 22.04 (Jammy) deps Python antigas no apt**: pydantic 1.x e structlog 20.x do apt Jammy não satisfazem `>=2.0` / `>=23.0`. Workaround: `pip install --user 'pydantic>=2' 'structlog>=23' 'typer>=0.12' rich pydualsense` após instalar `.deb`.
- **Bluetooth runtime end-to-end**: PROTOCOL_READY mas não validado em hardware BT pareado.
- **Aba Mouse e Teclado**: end-to-end com hardware real ainda não validado fora do daemon CLI.
- **state_full IPC**: alguns campos podem estar incompletos (verificar paridade com snapshot canônico).

## [3.0.0] — 2026-04-27

Major release de **rebrand + hardening**: rebrand `Hefesto` → `Hefesto - Dualsense4Unix` + 6 sprints de fix runtime real validadas no dia da release.

### Sprints fechadas pós-rebrand (acumulam no v3.0.0)

- **BUG-DAEMON-NO-DEVICE-FATAL-01**: daemon agora sobe mesmo sem DualSense conectado. `pydualsense.Exception("No device detected")` deixa de ser fatal — vira estado offline-OK com setters virando no-op silencioso. IPC/UDP/poll loop sobem antes de tentar conectar; reconnect_loop em background com probe a cada 5s detecta plug. systemd `StartLimitBurst=3` deixa de ser acionado (era consequência, não causa).
- **CLUSTER-IPC-STATE-PROFILE-01**: `daemon.state_full` IPC agora reflete o tick atual do `_poll_loop` (era snapshot stale), com telemetria diagnóstica `state_full.stale_neutral` para detectar evdev_reader desconectado. `profile.switch` IPC ganhou paridade com CLI `profile activate` (escreve `active_profile.txt` além do canônico `session.json`). Novo `MANUAL_PROFILE_LOCK_SEC=30s` no StateStore: autoswitch faz no-op enquanto lock manual ativo, evitando que troca via tray seja sobrescrita em <1s.
- **CLUSTER-INSTALL-DEPS-01**: `install.sh` ganhou passos 8/9 — detecta GNOME via `XDG_CURRENT_DESKTOP` e habilita `ubuntu-appindicators@ubuntu.com` automaticamente (Pop!_OS/Ubuntu vêm com extension instalada mas desabilitada). Detecta `dualsensectl` ausente e oferece flatpak install (`com.github.nowrep.dualsensectl`); install nunca bloqueia se opcional. Aba Firmware na GUI mostra mensagem clara com URL Flathub quando binário ausente.
- **CLUSTER-TRAY-POLISH-01**: "Sair" do tray agora mata daemon avulso via PID file (defesa anti-recycle via `is_hefesto_dualsense4unix_process`), não só systemctl stop. Item `(carregando)` zumbi removido do submenu Perfis. Mnemonic GTK underscore corrigido (`use_underline=False` explícito).
- **FEAT-BLUETOOTH-CONNECTION-01** (PROTOCOL_READY): código de runtime já era transport-agnostic (USB+BT). Sprint adicionou gate da regra udev `74-ps5-controller-hotplug-bt.rules` no `install.sh`, seção "Conexão via Bluetooth" no README com fluxo `bluetoothctl` em PT-BR, e CHECKLIST_HARDWARE_V2 item 8 expandido (5 sub-itens). Promoção a MERGED requer execução em hardware BT pareado.
- **BUG-VALIDAR-ACENTUACAO-FIX-GLYPHS-03**: `scripts/validar-acentuacao.py` ganhou defesa em profundidade (pre/post-pass) contra strip silencioso de glyphs ADR-011 (□). Pre-pass: linha contendo glyph protegido não é corrigida (conservador). Post-pass: revert se algum codepoint sumiu após substituição.

### Quebrando compatibilidade

### Quebrando compatibilidade

- **Pacote PyPI:** `hefesto` → `hefesto-dualsense4unix`. Não há migração automática; usuários precisam reinstalar via `pip install hefesto-dualsense4unix` (ou rodar `./install.sh` no clone).
- **Comando CLI:** `hefesto` → `hefesto-dualsense4unix` (e `hefesto-gui` → `hefesto-dualsense4unix-gui`). Quem rodava `./uninstall.sh && ./install.sh` re-instala o binário com nome novo.
- **Módulo Python:** `import hefesto` → `import hefesto_dualsense4unix`. Plugins externos precisam atualizar imports.
- **Service systemd:** `hefesto.service` → `hefesto-dualsense4unix.service`. `./uninstall.sh` (versão 2.x) seguido de `./install.sh` (versão 3.0) cuida da migração — ou manualmente `systemctl --user disable hefesto.service` antes do upgrade.
- **Env vars:** `HEFESTO_FAKE`, `HEFESTO_LOG_FORMAT`, `HEFESTO_PLUGINS_DIR`, etc → `HEFESTO_DUALSENSE4UNIX_*` (mesmo sufixo, prefixo expandido).
- **Paths runtime:** `~/.config/hefesto/` → `~/.config/hefesto-dualsense4unix/`; `~/.local/share/hefesto/glyphs/` → `~/.local/share/hefesto-dualsense4unix/glyphs/`; `$XDG_RUNTIME_DIR/hefesto/` → `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/`. Configs e perfis pré-existentes precisam ser movidos manualmente (`mv ~/.config/hefesto ~/.config/hefesto-dualsense4unix`).
- **Window class X11:** `Hefesto` → `Hefesto-Dualsense4Unix`. Perfis de auto-switch que matchavam `window_class="Hefesto"` precisam atualizar.
- **Ícones e .desktop:** todos os assets `Hefesto.{png,svg,desktop}` viraram `Hefesto-Dualsense4Unix.{png,svg,desktop}`.

### Preservado (sem mudança)

- **App-id Flatpak:** `br.andrefarias.Hefesto` permanece (já é composite com qualificador `br.andrefarias.`); o Flatpak instalado continua sendo o mesmo, só o `command:` interno aponta pra `hefesto-dualsense4unix-gui`.
- **Repositório GitHub:** `AndreBFarias/hefesto` mantém URL atual; `git clone` segue funcionando com o nome antigo.
- **Documentação histórica:** sprints (`docs/process/sprints/`), ADRs (`docs/adr/`), audits, discoveries e o `HEFESTO_PROJECT.md` original (`docs/process/`) ficaram intactos — registro do que foi decidido quando ainda se chamava só "Hefesto".

### Mudou

- Display brand em todos os pontos vivos: título da janela GTK, banner da TUI Textual, headers do README, descrição em `pyproject.toml`, mensagens de instalação/desinstalação, comentários e docstrings em código novo.
- Pasta de desenvolvimento: `Hefesto-DualSense_Unix` → `Hefesto-Dualsense4Unix` (sem espaços, hífen único).
- Validação programática verde: 1286 unit tests pass, mypy strict zero, ruff zero issues.
- Validação visual: GUI sobe com título correto `Hefesto - Dualsense4Unix`, screenshot capturado em `/tmp/hefesto-dualsense4unix_gui_main_*.png`.
- README ganha seção **"Layout das abas (GUI GTK3)"** descrevendo cada uma das 10 abas (Status, Gatilhos, Lightbar, Rumble, Perfis, Daemon, Emulação, Mouse, Teclado, Firmware) e seus controles.

### Como migrar (TL;DR)

```bash
# 1. parar e desinstalar a versão antiga
cd ~/Desenvolvimento/Hefesto-DualSense_Unix  # nome antigo
./uninstall.sh

# 2. (se você usa essa estrutura local) renomeie a pasta
cd ..
mv Hefesto-DualSense_Unix Hefesto-Dualsense4Unix

# 3. fazer pull e reinstalar
cd Hefesto-Dualsense4Unix
git pull origin main
./install.sh

# 4. mover config e dados (uma vez)
mv ~/.config/hefesto ~/.config/hefesto-dualsense4unix 2>/dev/null || true
mv ~/.local/share/hefesto ~/.local/share/hefesto-dualsense4unix 2>/dev/null || true
```

## [2.3.0] — 2026-04-24

Minor release com o marco **keyboard feature** completo para DualSense no
Linux. 3 sprints entregues em sequência (80 + 59.2 + 59.3) fechando o
tripé planejado desde a v2.2.0: persistência por perfil, UI de edição,
tokens virtuais para teclado virtual do sistema, consumo do touchpad
como botões (left/middle/right → backspace/enter/delete) e correção do
CI `acentuacao` travado desde v2.2.1. Pipeline de release 100% automático
(herdado da v2.2.2) gera .deb Noble + .AppImage + .flatpak + .whl + sdist
via workflow `release.yml` no push da tag.

### Adicionado
- **Aba "Mouse e Teclado" com editor de key bindings**
  (FEAT-KEYBOARD-UI-01, sprint 59.3): nova classe `InputActionsMixin`
  (subclasse de `MouseActionsMixin`) em `src/hefesto_dualsense4unix/app/actions/input_actions.py`
  entrega TreeView CRUD (Adicionar/Remover/Restaurar defaults) para
  `key_bindings` do perfil ativo, com legenda documentando formato
  `KEY_*` e tokens virtuais `__*__`. Tab no `main.glade` renomeada de
  "Mouse" para "Mouse e Teclado"; handlers `on_key_binding_*`
  registrados em `_signal_handlers()` (lição 77.1). `DraftConfig` ganha
  campo `key_bindings` com round-trip via `from_profile`/`to_profile`.
  Decisão documentada em
  `docs/process/discoveries/2026-04-24-r2-l2-inversion-decision.md`:
  inversão R2/L2 **não** aplicada (quebraria simetria com X/Triângulo
  + convenção de mouse destro); usuário pode customizar via UI por
  perfil. Validação visual em
  `docs/process/screenshots/FEAT-KEYBOARD-UI-01-depois.png`.

- **Tokens virtuais OSK + touchpad regions como bindings**
  (FEAT-KEYBOARD-UI-01 Fase B+D): `UinputKeyboardDevice` aceita tokens
  `__OPEN_OSK__` / `__CLOSE_OSK__` (em `core/keyboard_mappings.py`) e
  delega ao `virtual_token_callback` em vez de emitir via uinput;
  binding misto `KEY_*+__*__` é rejeitado com warning. `_OSKController`
  (em `daemon/subsystems/keyboard.py`) resolve `onboard`/`wvkbd-mobintl`
  via `shutil.which` com cache 1x + warning único se ausente, e faz
  subprocess.Popen idempotente em open/close. `DEFAULT_BUTTON_BINDINGS`
  ganha 5 entradas novas: L3→`__OPEN_OSK__`, R3→`__CLOSE_OSK__`, e as 3
  regiões `touchpad_{left,middle,right}_press` → `KEY_BACKSPACE/ENTER/DELETE`.
  `dispatch_keyboard` mescla `TouchpadReader.regions_pressed()` (infra
  da sprint 83) ao frozenset de botões antes do device dispatch.
  `_start_touchpad_reader` pula em `HEFESTO_DUALSENSE4UNIX_FAKE=1` (evita probing lento
  de evdev em testes); conftest autouse garante flag nos unit tests.
  17 testes novos cobrem: tokens + OSK spawn + fallback wvkbd + touchpad
  merge + exception safety.

- **Persistência de key bindings por perfil**
  (FEAT-KEYBOARD-PERSISTENCE-01, sprint 59.2): novo campo
  `Profile.key_bindings: dict[str, list[str]] | None = None` com validator
  que aceita tokens `KEY_*` (verificados contra `evdev.ecodes` quando
  disponível) e tokens virtuais `__*__` reservados para a sub-sprint UI
  (59.3). Semântica: `None` herda `DEFAULT_BUTTON_BINDINGS`; `{}` desativa
  todos os bindings; dict parcial é override explícito sem merge. Helper
  puro `_to_key_bindings(profile)` converte schema em `tuple[str, ...]`
  (KeyBinding). Método novo `ProfileManager.apply_keyboard(profile)`
  propaga ao `UinputKeyboardDevice` via `set_bindings` (armadilha A-06
  resolvida). `ProfileManager` ganha campo opcional `keyboard_device`;
  3 callsites do daemon (`connection.restore_last_profile`,
  `subsystems/ipc`, `subsystems/autoswitch`) passam
  `daemon._keyboard_device` no constructor, propagando o override a cada
  `activate()`. 9 perfis default em `assets/profiles_default/*.json`
  ganharam `"key_bindings": null` explícito. 10 testes novos em
  `tests/unit/test_profile_key_bindings.py` e
  `tests/unit/test_ipc_profile_switch_propaga_teclado.py` cobrindo
  helper + validator + mapper A-06 + caminho IPC real.

### Corrigido
- **Job `acentuacao` do `ci.yml` vermelho em `main` desde v2.2.1**
  (BUG-CI-ACENTUACAO-REGRESSION-01): 6 violações pré-existentes
  travavam o gate de acentuação PT-BR. 2 em comentário do
  `release.yml:116` (`Historico`/`iteracoes` → `Histórico`/`iterações`),
  2 em string literals de `tests/unit/test_firmware_updater.py:66,119`
  (`tambem` → `também`, `generico`/`binario` → `genérico`/`binário`),
  2 em identifier Python `conteudo` em
  `tests/unit/test_validar_acentuacao_glyphs.py:145-146` (renomeado
  para `texto_final` para evitar falso positivo — o validador não
  ignora identifiers, o que seria over-engineering para 2
  ocorrências). `python3 scripts/validar-acentuacao.py --all` passa
  com exit 0. Nota: a spec original dizia 10 violações, mas o
  release.yml foi parcialmente reescrito pelos fixes da v2.2.2 e a
  contagem real baixou para 6 — spec atualizada.

## [2.2.2] — 2026-04-24

Patch release pós-v2.2.1. Corrige o bug que obrigou upload manual na
release anterior (`deb-install-smoke` falhando por pydantic v1 no apt
de Jammy/Noble) e blinda o pipeline com um gate que detecta drift
entre o fallback hardcoded de `src/hefesto_dualsense4unix/__init__.py` e a versão
canônica em `pyproject.toml`. Objetivo substantivo: v2.2.2 é o
**primeiro release totalmente automático desde v0.1.0** — zero
intervenção humana após `git push --tags`.

### Corrigido
- **`structlog.typing` ausente no Jammy apt quebrava `deb-install-smoke`**
  (BUG-DEB-SMOKE-STRUCTLOG-TYPING-02): o fix 79.1 (pydantic) passou, mas
  o workflow run `24866299294` sobre a tag `v2.2.2` expôs um segundo
  modo de falha — `structlog.typing` só existe em `structlog >= 22.1`,
  enquanto Ubuntu 22.04 apt entrega `python3-structlog 21.x` (só
  `structlog.types`). Fix em 2 camadas: compat layer `try: from
  structlog.typing import Processor / except ImportError: from
  structlog.types import Processor` em `src/hefesto_dualsense4unix/utils/logging_config.py`
  (usa `TYPE_CHECKING` para satisfazer mypy) e version constraint
  `python3-structlog (>= 21.5)` em `packaging/debian/control`. Teste
  novo `tests/unit/test_logging_compat_import.py` cobre os dois
  caminhos via `monkeypatch.setitem(sys.modules, ...)`. L-21-7 reforçada:
  toda dep Python do `.deb` precisa `apt-cache policy` empírico
  individual — já saiu uma sub-diretriz para o BRIEF.
- **Smoke install do `.deb` passa em Ubuntu 22.04 e 24.04**
  (BUG-DEB-SMOKE-PYDANTIC-V2-NOBLE-01): validação empírica em
  2026-04-24 confirmou que Noble (24.04) entrega `python3-pydantic
  1.10.14`, não v2 como a sprint 74 havia assumido. O `.deb` da v2.2.1
  declarava `python3-pydantic (>= 2.0)` e rejeitava instalação em
  ambos releases LTS atuais, bloqueando o job `deb-install-smoke` e
  exigindo upload manual do release. Fix em 3 camadas:
  - `packaging/debian/control` declara `python3-pydantic` sem constraint
    de versão (apt resolve com a 1.x do sistema, sem erro).
  - `src/hefesto_dualsense4unix/__init__.py` detecta pydantic < 2 no import e emite
    `ImportWarning` com instrução acionável (`pip install --user
    'pydantic>=2'`).
  - `.github/workflows/release.yml` `deb-install-smoke` volta para
    `ubuntu-22.04` (mesmo runner do build) e adiciona passo `pip
    install --user 'pydantic>=2.0'` antes do `apt install`; o
    `hefesto-dualsense4unix --version` roda com `PYTHONPATH` apontando para o user
    site primeiro, garantindo que `import pydantic` resolva a v2.
  README atualizado com o novo caminho canônico (2 comandos:
  `pip install --user pydantic>=2` + `apt install ./hefesto_*.deb`).

### Infraestrutura
- **Gate `version-sync` no CI** (CHORE-VERSION-SYNC-GATE-01): novo job
  em `.github/workflows/ci.yml` que falha se o fallback `__version__`
  de `src/hefesto_dualsense4unix/__init__.py` divergir de `pyproject.toml
  [project].version`. Regex inline (tomllib + re.search) — YAGNI parser
  AST. Motivação: BUG-APPIMAGE-VERSION-NAME-01 revelou que o fallback
  ficou hardcoded em "1.0.0" por 3 releases enquanto `pyproject`
  avançava até 2.2.0; como o `.deb` via `cp -r` não tem METADATA
  importlib, o fallback é a última linha de defesa — se divergir,
  usuários vêem versão errada silenciosamente. Proof-of-work validou
  baseline (2.2.2 == 2.2.2 passa) e drift simulado (9.9.9 != 2.2.2
  detectado e rejeitado).

### Processo
- **L-21-7 consolidada no VALIDATOR_BRIEF.md** (seção `[PROCESS]
  Lições`): toda premissa sobre ambiente externo — "distro X tem lib
  Y versão N", "runner Z tem binário W" — exige validação empírica
  (`apt-cache policy`, `docker run`, consulta a `packages.ubuntu.com`)
  antes de virar spec. Sprint 74 violou essa regra e custou 1 release
  manual; agora é regra explícita no BRIEF.

## [2.2.1] — 2026-04-23

Patch release pós-v2.2.0. Corrige bugs críticos de packaging
descobertos durante a própria release v2.2.0 (nome do AppImage e
.deb incompatível com Ubuntu 22.04), introduz aba Firmware na GUI
(destravada pelo merge upstream de `dualsensectl` PR#53), blinda o
validador de acentuação contra remoção silenciosa de glyphs Unicode
(bug reproduzido 2x), melhora o layout da aba Perfis com combo +
preview JSON ao vivo, e aprimora o dev-setup com detecção de
PyGObject. 9 commits desde v2.2.0, 6 sprints principais + 3
colaterais, zero regressão.

### Alterado
- **Aba Perfis — preview JSON ao vivo** (UI-PROFILES-RIGHT-PANEL-REBALANCE-01):
  a coluna direita do editor ganha um frame "Preview do perfil (JSON)"
  com `GtkScrolledWindow` e label monoespaçada (tema Drácula) que mostra
  o objeto `Profile` resultante em tempo real. Atualiza a cada mudança
  em nome/prioridade/combo "Aplica a:"/nomes customizados/critérios
  avançados. Reutiliza `_build_profile_from_editor` como fonte única de
  verdade; falha graciosamente com `<perfil inválido: msg>` em caso de
  `ValidationError`. Ocupa o espaço vazio antes desbalanceado
  (~450 px → ~280 px) que resultou da sprint 77.
- **Aba Perfis, grupo "Aplica a:" — 6 radios substituídos por combo**
  (UI-PROFILES-RADIO-GROUP-REDESIGN-01): o campo "Aplica a:" no modo
  simples do editor de perfil trocou 6 `GtkRadioButton` empilhados
  verticalmente (~180 px de altura) por um único `GtkComboBoxText`
  (~40 px). Entries permanecem: Qualquer janela / Jogos da Steam /
  Navegador / Terminal / Editor de código / Jogo específico. Helpers
  `_selected_simple_choice` e `_select_radio` refatorados para
  `get_active_id`/`set_active_id`; handler novo `_on_aplica_a_changed`
  mostra/esconde o entry "Nome do jogo" quando id == "game".
  Liberação de ~140 px verticais na coluna direita — premissa para
  UI-PROFILES-RIGHT-PANEL-REBALANCE-01.

### Corrigido
- **Handlers da aba Firmware não respondiam a clicks**
  (BUG-FIRMWARE-SIGNAL-HANDLERS-01, colateral descoberto durante
  validação visual da UI-PROFILES-RADIO-GROUP-REDESIGN-01): os 3
  botões da aba Firmware (Verificar versão / Selecionar .bin /
  Aplicar firmware) estavam definidos no glade e no mixin, mas
  nunca conectados — o método `_signal_handlers()` em
  `src/hefesto_dualsense4unix/app/app.py` é declarativo e não foi estendido junto
  com a 70.2. Ao rodar `./run.sh --gui`, `Gtk.Builder` emitia
  `AttributeError: Handler on_firmware_* not found` e os botões
  ficavam mortos. Entradas adicionadas ao dict.

### Segurança
- **Blindagem contra remoção silenciosa de glyphs Unicode ADR-011**
  (BUG-VALIDAR-ACENTUACAO-FIX-GLYPHS-02): `scripts/validar-acentuacao.py`
  agora reconhece whitelist explícita `UNICODE_ALLOWED_RANGES` cobrindo
  Arrows, Box Drawing, Block Elements e Geometric Shapes. Em modo
  `--fix`, qualquer substituição cuja faixa original contenha caractere
  protegido é rejeitada e emite warning em stderr citando o glyph e a
  linha. Mesmo que alguém adicione par errado em `_PARES` (ex:
  `("", "")`), o filtro bloqueia a remoção. 23 testes regressão
  parametrizados em `tests/unit/test_validar_acentuacao_glyphs.py`
  cobrem codepoints canônicos (U+25AE/AF/CB/CF/D0, U+2192, U+2500,
  U+2588), boundaries dos ranges e cenário de par malicioso injetado.
  Bloqueia formalmente a 3ª reprodução da regressão documentada em
  `BUG-VALIDAR-ACENTUACAO-FIX-GLYPHS-01` (reproduzida 2x em V2.1 e V2.2).

### Melhorado
- **Developer experience — detecção de PyGObject no `.venv`** (INFRA-VENV-PYGOBJECT-01):
  `scripts/dev-setup.sh` agora valida `import gi; Gtk.require_version('3.0')`
  pelo `.venv/bin/python` após o collect-only do pytest. Quando ausente,
  imprime instrução acionável em 2 linhas (apt install + `dev_bootstrap.sh
  --with-tray`). Não bloqueia o fluxo (GUI é opt-in); apenas avisa para
  evitar a armadilha A-12 (`ModuleNotFoundError: No module named 'gi'`
  ao invocar `./run.sh --gui` ou coletar `tests/unit/test_status_actions_reconnect.py`).
  README marca `--with-tray` como pré-req de GUI. VALIDATOR_BRIEF.md
  armadilha A-12 promovida de "conhecida" para "PARCIALMENTE RESOLVIDA".

### Corrigido
- **`.deb` falhava ao instalar em Ubuntu 22.04** (BUG-DEB-PYDANTIC-V2-UBUNTU-22-01):
  o `python3-pydantic` do apt em Jammy é versão **1.9.x**, incompatível
  com o código do Hefesto - Dualsense4Unix (usa API pydantic v2 — `ConfigDict`). O
  `apt install ./hefesto_*.deb` falhava silenciosamente em cadeia com
  `ImportError: cannot import name 'ConfigDict' from 'pydantic'`.
  Fix: `packaging/debian/control` declara `python3-pydantic (>= 2.0)`
  (apt passa a rejeitar instalação com mensagem clara); CI smoke job
  `deb-install-smoke` migrado de `ubuntu-22.04` para `ubuntu-24.04`
  (valida no cenário que funciona out-of-the-box). README ganha seção
  **Ubuntu 22.04 (Jammy) e derivados** explicando 3 workarounds
  alternativos (migrar para 24.04, pip install manual, AppImage/Flatpak).
  `.deb` continua buildado em `ubuntu-22.04` para compat máxima de libs.

- **Versão reportada errada em CLI/TUI/AppImage** (BUG-APPIMAGE-VERSION-NAME-01):
  `src/hefesto_dualsense4unix/__init__.py` tinha `__version__ = "1.0.0"` hardcoded por
  ~3 releases, afetando `hefesto-dualsense4unix version`, título/subtítulo da TUI,
  nome do asset AppImage no GitHub Release (v2.2.0 saiu como
  `Hefesto-Dualsense4Unix-1.0.0-x86_64.AppImage`) e validação do teste `test_cli`.
  Fix: `__version__` passa a ser lido dinamicamente via
  `importlib.metadata.version("hefesto-dualsense4unix")` com fallback hardcoded
  sincronizado ao `pyproject.toml`. `scripts/build_appimage.sh`
  alinhado ao padrão de `build_deb.sh` (lê `pyproject.toml` direto,
  sem depender do pacote estar importável). Regressão futura coberta
  por `CHORE-VERSION-SYNC-GATE-01` (enfileirada).

### Adicionado
- **Aba Firmware na GUI** (FEAT-FIRMWARE-UPDATE-GUI-01):
  nova aba permite consultar versão atual do firmware do DualSense e
  aplicar blob oficial da Sony via wrapper `dualsensectl`. Backend em
  `src/hefesto_dualsense4unix/integrations/firmware_updater.py` invoca `dualsensectl
  info`/`update` em thread worker com callbacks `GLib.idle_add`; UI
  mostra banner de risco, versão atual, seletor de `.bin`, barra de
  progresso e diálogo de confirmação modal. 17 testes unit com mocks
  cobrem os fluxos (is_available, parse, get_info, apply + erros).
  Requer `dualsensectl` >= branch main 2026-02-19 instalado no sistema.
  Desbloqueio viabilizado por achado upstream em 2026-04-23: PR#53 do
  `nowrep/dualsensectl` expôs o protocolo DFU (feature reports
  0x20/0xF4/0xF5, blob 950272 bytes, CDN
  `fwupdater.dl.playstation.net`). Research completo em
  `docs/research/firmware-dualsense-2026-04-survey.md`.

## [2.2.0] — 2026-04-23

Release de polish pós-v2.1.0. Foco em destravar CI (`mypy` gate rígido
volta a valer), fechar débito técnico da auditoria V2 e polir a GUI
com prints reais + 5 bugs reportados pelo usuário após v2.1.0. Primeira
tag que publica `.deb`, `.AppImage` e `.flatpak` no GitHub Release
(dispatch v2.0.0/v2.1.0 falhou por incompatibilidade com commits antigos).

### Destravado
- **CI release gate** (BUG-CI-RELEASE-MYPY-GATE-01 + CHORE-MYPY-CLEANUP-V22-01):
  `release.yml` deixou de abortar em `mypy`; 41 errors pré-existentes
  fechados; `ci.yml` ganha job `typecheck` como gate rígido. A partir
  desta versão, qualquer PR/push que regride `mypy src/hefesto_dualsense4unix` quebra
  o workflow.
- **Flatpak bundle no GitHub release** (FEAT-CI-RELEASE-FLATPAK-ATTACH-01):
  `release.yml` ganha job `flatpak` e `github-release` passa a anexar
  `.whl`, `.tar.gz`, `.AppImage`, `.deb` e `.flatpak` a cada tag.
- **Re-publicação de tags via dispatch** (CHORE-CI-REPUBLISH-TAGS-01,
  PROTOCOL_READY): `release.yml` ganha `workflow_dispatch` com input
  `tag` — dono executa `gh workflow run release.yml -f tag=v2.1.0`
  para re-publicar releases que haviam abortado.

### Adicionado
- **dev-setup.sh idempotente** (CHORE-VENV-BOOTSTRAP-CHECK-01):
  wrapper que detecta `.venv` ausente ou pytest quebrado e invoca
  `dev_bootstrap.sh`; sempre termina com `pytest --collect-only`.
  Operacionaliza lição L-21-4 (sessão nova precisa de `.venv` viva).
- **Status PROTOCOL_READY** (DOCS-STATUS-PROTOCOL-READY-01):
  sprints só-doc (checklist/research) não podem mais virar MERGED
  sem ≥1 execução humana registrada em "Execuções registradas".
- **Seleção do perfil ativo ao abrir GUI** (FEAT-GUI-LOAD-LAST-PROFILE-01):
  aba Perfis sincroniza com `daemon.status` e destaca o perfil em
  execução (antes abria sempre no primeiro da lista ordenada).
- **Aba Emulação + Daemon + Status polidas**
  (UI-POLISH-EMULACAO-DAEMON-STATUS-01): `halign=start` nos cards,
  `uinput` → `UINPUT`, padding uniforme, fundo do log systemctl mais
  claro, título "Gatilhos (ao vivo)" → "Gatilhos".
- **Cores diferenciadas no footer** (UI-FOOTER-BUTTON-COLORS-01):
  Aplicar/Salvar/Importar/Restaurar ganham bordas coloridas (verde,
  ciano, laranja, cinza Drácula) sem poluir — gradientes com alpha
  baixo respondem a hover/active.
- **Botão Aplicar LEDs de jogador** (BUG-PLAYER-LEDS-APPLY-01):
  aba Lightbar ganha botão dedicado; `apply_led_settings` agora
  propaga `player_leds` ao controller (armadilha A-06 fechada para
  este campo — perfil JSON agora reaplica LEDs ao dar `profile.switch`).
- **Polish aba Perfis** (UI-PROFILES-LAYOUT-POLISH-01): headers
  TreeView em Drácula purple bold, slider de Prioridade ganha marks
  visuais (0/50/100). Achados H1 e H5 viraram sprints-filhas.
- **Infraestrutura de emulação de teclado** (FEAT-KEYBOARD-EMULATOR-01):
  `UinputKeyboardDevice`, bindings default hardcoded (Options→Super,
  Share→PrintScreen, L1→Alt+Shift+Tab, R1→Alt+Tab, touchpad
  middle/left/right→Enter/Backspace/Delete), subsystem novo
  `keyboard.py` com wire-up A-07 (4 pontos + teste dedicado) e
  A-09 (snapshot evdev único por tick compartilhado com mouse e
  hotkey). Persistência por perfil e UI editável ficam para
  FEAT-KEYBOARD-PERSISTENCE-01 e FEAT-KEYBOARD-UI-01.
- **Hardening do IPC** (HARDEN-IPC-PAYLOAD-LIMIT-01, reescopado de
  HARDEN-IPC-RUMBLE-CUSTOM-01 após L-21-3): `MAX_PAYLOAD_BYTES =
  32_768` no `_dispatch`; requests maiores rejeitados com JSON-RPC
  `-32600`. Cobertura via 5 testes.
- **Governança e descoberta open-source**
  (FEAT-GITHUB-PROJECT-VISIBILITY-01, PROTOCOL_READY): `.github/`
  ganha CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, PR
  template e ISSUE_TEMPLATE/question.md (todos PT-BR). Social
  preview 1280×640 em `docs/usage/assets/social-preview.png`.
  Comandos `gh repo edit` para descrição + 20 topics documentados
  em `docs/history/gh-repo-config.md` (execução humana pendente).
- **README renovado** (DOCS-README-RENOVATE-01): layout espelha
  `Conversor-Video-Para-ASCII`, 7 screenshots em
  `docs/usage/assets/readme_*.png`, badges de release/downloads/
  CI/license/Python, zero acentuação faltando.

### Corrigido
- **GUI abria com Daemon Offline apesar do daemon ativo**
  (BUG-GUI-DAEMON-STATUS-INITIAL-01): primeira leitura de
  `daemon.status` dispara via `GLib.idle_add` antes do primeiro
  frame; placeholder "Consultando..." substitui o "Offline" falso
  anterior; refresh do painel Daemon em thread worker para não
  bloquear GTK.
- **Ruff false-positives em specs novos**
  (BUG-VALIDAR-ACENTUACAO-FALSE-POS-01): par `facilmente →
  fácilmente` removido (sufixo `-mente` perde acento do radical);
  spec PHASE3 reescrito para evitar ambiguidade verbo/substantivo
  com "referencia".
- **`.deb` sem rich/evdev/xlib/filelock**
  (BUG-DEB-MISSING-DEPS-01): `packaging/debian/control` ganha 4
  deps Python que faltavam; `apt install ./hefesto_*.deb`
  agora produz CLI funcional no primeiro comando.
- **Flatpak build quebrado offline**
  (BUG-FLATPAK-PIP-OFFLINE-01): módulos `python-uinput` e
  `pydualsense` ganham `build-options.build-args: --share=network`
  para pip acessar PyPI durante o build.
- **`connection.py` fora de convenção**
  (REFACTOR-CONNECTION-FUNCTIONS-01, P2-02): movido de
  `daemon/subsystems/` para `daemon/` (eram funções soltas, não
  classe com start/stop).

### Governança do processo
- **6 lições V2.1 no BRIEF** (META-LESSONS-V21-BRIEF-01): seção
  `[PROCESS] Lições acumuladas por ciclo` com L-21-1..L-21-6.
  Planejador/executor/validador leem como trilho permanente.
- **Armadilha A-12** (do ciclo BUG-GUI-DAEMON-STATUS-INITIAL-01):
  `.venv` sem PyGObject sem `--with-tray` quebra validação visual
  via `.venv/bin/python`. Fix canônico: sprint
  `INFRA-VENV-PYGOBJECT-01` (PENDING).
- **Script `scripts/mark-sprint-merged.sh`**: automação de
  atualização de status em `SPRINT_ORDER.md` (evita edit manual
  propenso a erro; usa awk cirúrgico no campo Status da linha do ID).

### Sprints consolidadas (V2.2 — 17 MERGED + 2 PROTOCOL_READY + 1 SUPERSEDED)

**MERGED** (código/config executado):
BUG-CI-RELEASE-MYPY-GATE-01 · BUG-VALIDAR-ACENTUACAO-FALSE-POS-01 ·
META-LESSONS-V21-BRIEF-01 · CHORE-VENV-BOOTSTRAP-CHECK-01 ·
DOCS-STATUS-PROTOCOL-READY-01 · UI-POLISH-EMULACAO-DAEMON-STATUS-01 ·
BUG-GUI-DAEMON-STATUS-INITIAL-01 · FEAT-GUI-LOAD-LAST-PROFILE-01 ·
UI-FOOTER-BUTTON-COLORS-01 · BUG-PLAYER-LEDS-APPLY-01 ·
REFACTOR-CONNECTION-FUNCTIONS-01 · HARDEN-IPC-PAYLOAD-LIMIT-01 ·
FEAT-CI-RELEASE-FLATPAK-ATTACH-01 · CHORE-MYPY-CLEANUP-V22-01 ·
UI-PROFILES-LAYOUT-POLISH-01 · DOCS-README-RENOVATE-01 ·
FEAT-KEYBOARD-EMULATOR-01 · BUG-DEB-MISSING-DEPS-01 ·
BUG-FLATPAK-PIP-OFFLINE-01.

**PROTOCOL_READY** (infra pronta, execução humana do dono pendente):
CHORE-CI-REPUBLISH-TAGS-01 · FEAT-GITHUB-PROJECT-VISIBILITY-01.

**SUPERSEDED** (spec invalidado após leitura do código):
HARDEN-IPC-RUMBLE-CUSTOM-01 (→ HARDEN-IPC-PAYLOAD-LIMIT-01,
reescopado via L-21-3).

**PENDING para próximo ciclo**: INFRA-VENV-PYGOBJECT-01 ·
UI-PROFILES-RADIO-GROUP-REDESIGN-01 ·
UI-PROFILES-RIGHT-PANEL-REBALANCE-01 · FEAT-KEYBOARD-PERSISTENCE-01 ·
FEAT-KEYBOARD-UI-01 · FEAT-FIRMWARE-UPDATE-PHASE2-01 ·
FEAT-FIRMWARE-UPDATE-PHASE3-01.

### Known issues
- `gh workflow run release.yml -f tag=v2.0.0` falha em `ruff check`
  porque o código da tag v2.0.0 tem 6 violações ruff corrigidas
  depois. Re-publicar v2.0.0 exigiria re-tag (destrutivo). Decisão:
  v2.0.0 fica sem release no GitHub; v2.1.0 e v2.2.0+ ganham pacotes.

## [2.1.0] — 2026-04-23

Release de polish pós-v2.0.0. Oito sprints aditivas + auditoria manual.
Sem quebras; tudo retrocompatível com v2.0.0.

### Adicionado
- **Hook strict de acentuação PT-BR** (CHORE-ACENTUACAO-STRICT-HOOK-01):
  `scripts/validar-acentuacao.py` (809 linhas, 315 pares de palavras),
  `.pre-commit-config.yaml` com framework pre-commit, job
  `acentuacao` em `.github/workflows/ci.yml`. Whitelist robusta
  preserva `docs/history`, `docs/research`, `LICENSE`, fixtures
  ASCII intencionais. Bloqueia commits com PT-BR sem acento.
- **Separação slug × display em perfis** (PROFILE-SLUG-SEPARATION-01):
  novo módulo `src/hefesto_dualsense4unix/profiles/slug.py` com `slugify()`
  (normalização NFKD). `save_profile` grava filename ASCII derivado
  do `name` acentuado; `load_profile` faz busca adaptativa em 3
  camadas (direto → slug → scan). Corrige bug latente onde perfis
  acentuados (ex.: "Ação") criariam filenames acentuados colidindo
  com defaults ASCII.
- **Schema multi-position em triggers** (SCHEMA-MULTI-POSITION-PARAMS-01):
  `TriggerConfig.params: list[int] | list[list[int]]` com validator
  pydantic + property `is_nested`. Helper `_flatten_multi_position`
  em `trigger_effects.py` suporta formatos 2, 5 e 10 posições.
  Perfis `aventura` e `corrida` migrados para MultiPositionFeedback
  e MultiPositionVibration (0-8 scale). Outros 6 perfis mantidos
  sem mudança (fallback intocado por estabilidade).
- **Smoke test de .deb no CI** (SMOKE-DEB-INSTALL-CI-01): job
  `deb-install-smoke` em `release.yml` instala `.deb` real via
  `apt install`, valida `hefesto-dualsense4unix --version` e `hefesto-dualsense4unix-gui --help`,
  desinstala para validar postrm. Bloqueia release em tag push se
  instalação falhar.
- **Smoke test de Flatpak no CI** (SMOKE-FLATPAK-BUILD-CI-01):
  3 steps no `build-flatpak` em `flatpak.yml`:
  `flatpak install --user --noninteractive --bundle`,
  `flatpak info --user` para validar registro, upload do log de
  build como artifact (retention 7d, `if: always()`).
- **Screenshot da aba Perfis no quickstart**
  (QUICKSTART-PROFILES-SCREENSHOT-01):
  `docs/usage/assets/quickstart_07_perfis.png`. Quickstart seção
  "6. Trocar de perfil" referencia a imagem.
- **Research de firmware update do DualSense**
  (FEAT-FIRMWARE-UPDATE-PHASE1-01):
  `docs/research/firmware-update-protocol.md` (292 linhas).
  Estado da arte (dualsensectl, DS4Windows, pydualsense,
  hid-playstation), mapa de HID reports, hipóteses de DFU
  (feature report 0xA3 candidato), metodologia reprodutível
  (usbmon + Wireshark + VM Win11), riscos (brick), base legal
  (BR / UE / USA). Zero código executável; fase 1 é só research.
- **Checklist reprodutível de validação em hardware**
  (HARDWARE-VALIDATION-PROTOCOL-01):
  `docs/process/CHECKLIST_HARDWARE_V2.md` com 21 itens cobrindo
  features V1.1/V1.2/V2.0 que hoje só têm cobertura via
  FakeController (Player LEDs, Rumble policies, Mic button,
  Hotkey Steam, Hotplug USB/BT, Lightbar brightness,
  Multi-position triggers, Autoswitch, `daemon.reload`,
  Single-instance daemon+GUI, Plugins+watchdog, Metrics,
  emulação de Mouse, UDP compat, USB autosuspend).
- **Auditoria manual v1.0.0..HEAD** (AUDIT-V2-COMPLETE-01):
  `docs/process/discoveries/2026-04-23-auditoria-v2.md`. 79
  arquivos, +9286/-705 linhas. Zero P0/P1. Três P2
  documentais/polish: débito de BRIEF fechado inline,
  `connection.py` fora de convenção (candidato a
  REFACTOR-CONNECTION-FUNCTIONS-01), `rumble.policy_custom`
  sem limite de tamanho (candidato a HARDEN-IPC-RUMBLE-CUSTOM-01).

### Corrigido
- Armadilhas A-01 (IpcServer unlink cego), A-02 (udp_server assert
  ruidoso) e A-03 (smoke compartilha socket path) estavam listadas
  como abertas mas já RESOLVIDAS em código. `VALIDATOR_BRIEF.md`
  atualizado para refletir estado real (débito documental fechado).

### Notas de migração
- **Perfis aventura e corrida migrados para multi-position**:
  validação tátil pendente (exige hardware físico, impossível via
  FakeController). Se a sensação regredir, reverter individualmente
  via
  `git checkout v2.0.0 -- assets/profiles_default/aventura.json assets/profiles_default/corrida.json`.
- **Hook pre-commit obrigatório**: contribuições novas precisam
  passar por `validar-acentuacao.py`, `check_anonymity.sh` e
  `ruff`. Rodar `.venv/bin/pre-commit install` em clones novos.

### Sprints consolidadas (7 MERGED + 2 PROTOCOL_READY)

**MERGED** (código/config executado e validado):
CHORE-ACENTUACAO-STRICT-HOOK-01 · PROFILE-SLUG-SEPARATION-01 ·
SCHEMA-MULTI-POSITION-PARAMS-01 · SMOKE-DEB-INSTALL-CI-01 ·
SMOKE-FLATPAK-BUILD-CI-01 · QUICKSTART-PROFILES-SCREENSHOT-01 ·
AUDIT-V2-COMPLETE-01.

**PROTOCOL_READY** (documento entregue, execução humana pendente — lição L-21-6):
FEAT-FIRMWARE-UPDATE-PHASE1-01 (pesquisa de DFU) ·
HARDWARE-VALIDATION-PROTOCOL-01 (checklist de 21 itens).

Os 2 docs ganham seção `## Execuções registradas` (vazia) em `docs/research/firmware-update-protocol.md` e `docs/process/CHECKLIST_HARDWARE_V2.md`. Virar MERGED requer ≥1 execução humana registrada nessas tabelas.

### Known issues
Nenhum. Três P2 documentais/polish registrados em
`docs/process/discoveries/2026-04-23-auditoria-v2.md` viram sprints
futuras V2.2+.

## [2.0.0] — 2026-04-23

Release de infra + arquitetura + extensibilidade. 9 sprints V2.0
consolidadas sobre v1.2.0: cadeia completa de botões (inclusive Mic
físico muta o sistema), daemon refatorado em subsystems modulares,
endpoint Prometheus opt-in, sistema de plugins Python.

### Adicionado
- **Cadeia MIC completa** (INFRA-BUTTON-EVENTS-01, INFRA-MIC-HID-01,
  INFRA-SET-MIC-LED-01 + FEAT-AUDIO-CONTROL-01 + FEAT-HOTKEY-MIC-01):
  - `ControllerState.buttons_pressed: frozenset[str]` propagado do evdev
    snapshot pro poll loop; diff gera `EventTopic.BUTTON_DOWN/UP`.
  - Botão Mic exposto via HID-raw (`ds.state.micBtn`) em ambos ramos
    (evdev + fallback).
  - `IController.set_mic_led(muted)` abstrato; backend usa
    `ds.audio.setMicrophoneLED`. `apply_led_settings` propaga
    `settings.mic_led` (resolve débito documentado em led_control.py).
  - `src/hefesto_dualsense4unix/integrations/audio_control.py`: `AudioControl`
    auto-detecta wpctl → pactl → none; debounce 200ms; nunca
    `shell=True`; toggle retorna novo estado.
  - `Daemon._start_mic_hotkey` subscribe em BUTTON_DOWN, filtra mic_btn,
    chama `AudioControl.toggle` + `controller.set_mic_led(muted)`.
    Dupla sincronização: LED do controle espelha mute do sistema.
  - Opt-out via `DaemonConfig.mic_button_toggles_system: bool = True`.
- **Daemon refatorado em subsystems modulares** (REFACTOR-LIFECYCLE-01):
  - `src/hefesto_dualsense4unix/daemon/subsystems/`: 10 módulos temáticos
    (poll, ipc, udp, autoswitch, mouse, rumble, hotkey, metrics,
    plugins, connection).
  - `src/hefesto_dualsense4unix/daemon/context.py`: `DaemonContext` dataclass
    compartilhado (controller, bus, store, config, executor).
  - `base.py`: Protocol `Subsystem(name, start, stop, is_enabled)`.
  - `lifecycle.py`: 677L → 365L. Backcompat total — 820 testes antigos
    passam sem modificação.
  - ADR-015 documenta padrão e ordem canônica de start.
  - 55 testes novos testando subsystems em isolamento.
- **Endpoint de métricas Prometheus opt-in** (FEAT-METRICS-01):
  - `MetricsSubsystem` expõe `/metrics` em text exposition format,
    bind 127.0.0.1 only, porta 9090 default (configurável).
  - 8 métricas canônicas: poll_ticks, controller_connected, battery_pct,
    ipc_requests, udp_packets, events_dispatched, button_down/up.
  - Sem dep obrigatória de `prometheus_client` — texto manual. Extra
    `[metrics]` em pyproject.toml pra dashboards avançados.
  - `DaemonConfig.metrics_enabled/port`. ADR-016 + `docs/usage/metrics.md`
    com scrape config Prometheus + exemplo Grafana.
- **Sistema de plugins Python** (FEAT-PLUGIN-01):
  - `src/hefesto_dualsense4unix/plugin_api/`: ABC `Plugin` com hooks on_load/on_tick/
    on_button_down/on_battery_change/on_profile_change/on_unload
    (defaults no-op). `PluginContext` expõe controller + bus.subscribe
    + store.counter + log prefixado.
  - `load_plugins_from_dir` via `importlib.util` — skip ImportError.
  - `PluginsSubsystem` carrega de `~/.config/hefesto-dualsense4unix/plugins/*.py`.
  - Watchdog: hook >5ms loga warning; >3 violações seguidas desativa.
  - CLI `hefesto-dualsense4unix plugin list/reload`. IPC handlers `plugin.list` e
    `plugin.reload`.
  - Opt-in via `DaemonConfig.plugins_enabled`. Plugins user-owned —
    documentação deixa explícito que usuário é responsável (sem sandbox).
  - Exemplo `examples/plugins/lightbar_rainbow.py` cicla HSV.
  - ADR-017 documenta API, limitações, anti-patterns.

### Testes
- Suíte cresceu de 795 (v1.2.0) para **917 passed, 5 skipped**. +122
  testes novos cobrindo cadeia MIC (10), subsystems (55), metrics (22),
  plugin API (20), audio control (10) e wire hotkey mic (4).

---

## [1.2.0] — 2026-04-22

Release de plataforma: `.deb` nativo, bundle Flatpak para COSMIC,
hotplug Bluetooth, suporte a Wayland via portal XDG, hot-reload do
daemon sem restart, quickstart visual com screenshots. 6 sprints
consolidadas sobre v1.1.0.

### Adicionado
- **Pacote .deb** (FEAT-DEB-PACKAGE-01): `scripts/build_deb.sh` usa
  `dpkg-deb --build` direto (sem dh_python3/debhelper). Dependências
  declaradas: python3-gi, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1,
  libhidapi-hidraw0 + libs pydantic/structlog/typer/platformdirs.
  pydualsense/python-uinput via pip (documentado). Job CI `deb` em
  `release.yml`. Validado local: 179KB, estrutura conferida com
  `dpkg-deb -I/c`.
- **Bundle Flatpak** (FEAT-FLATPAK-BUNDLE-01): `br.andrefarias.Hefesto`
  com runtime org.gnome.Platform//45, finish-args para hidraw+uinput+
  XDG portal. Manifest YAML + AppStream validado. Scripts
  `build_flatpak.sh` + `install-host-udev.sh` (pkexec copia rules).
  Doc `docs/usage/flatpak.md` com arquitetura do sandbox e caminhos
  isolados (`~/.var/app/br.andrefarias.Hefesto/config/`).
- **Auto-abertura da GUI ao parear via Bluetooth**
  (FEAT-HOTPLUG-BT-01): regra udev `74-ps5-controller-hotplug-bt.rules`
  observa `SUBSYSTEM=="hidraw" KERNELS=="0005:054C:0CE6.*"` (BUS_BLUETOOTH
  + DualSense/Edge). Reusa `hefesto-dualsense4unix-gui-hotplug.service` — idempotência
  garantida pelo single-instance da GUI.
- **Backends de detecção de janela** (FEAT-COSMIC-WAYLAND-01):
  `window_backends/xlib.py`, `wayland_portal.py` (D-Bus
  org.freedesktop.portal.Window.GetActiveWindow, lazy import jeepney/
  dbus-fast), `null.py`. Factory `window_detect.py` escolhe conforme
  env (DISPLAY → Xlib, WAYLAND_DISPLAY puro → Portal, nenhum → Null).
  `xlib_window.py` mantido como shim. ADR-014 complementa ADR-007.
  `docs/usage/cosmic.md` novo. 13 testes de factory.
- **Quickstart visual** (DOCS-QUICKSTART-01): `docs/usage/quickstart.md`
  reescrito com 6 screenshots passo-a-passo cobrindo Status, Daemon,
  Mouse, Rodapé, Trigger presets, Rumble policy + solução de problemas.
  README.md com pointer "Começar em 2 minutos".

### Corrigido / Refatorado
- **Hot-reload do daemon** (REFACTOR-DAEMON-RELOAD-01, resolve A-08):
  `_on_ps_solo` lê `self.config.ps_button_action` em runtime, não em
  closure — imune a troca de config via reload. Método
  `Daemon.reload_config(new_config)` rebuilda hotkey manager e
  reage a mudanças de `mouse_emulation_enabled`. Handler IPC
  `daemon.reload` com `dataclasses.replace(**overrides)`, rejeita
  keys inválidas. 10 testes novos.

### Testes
- Suíte cresceu para **795 passed, 5 skipped** (+13 do factory Wayland,
  +10 do daemon reload).

---

## [1.1.0] — 2026-04-22

Release de estabilidade + polish UX. 17 sprints integradas sobre a 1.0.0
cobrindo correção de bugs P0 reportados pelo usuário, redesign da interface
com tema Drácula e ButtonGlyphs originais, estado central de configuração
(DraftConfig), 6 perfis pré-configurados + "Meu Perfil", presets de gatilho
por posição e política global de rumble com modo Auto dinâmico por bateria.

### Adicionado
- **Tema Drácula global** via `Gtk.CssProvider` (UI-THEME-BORDERS-PURPLE-01):
  bordas roxas `#bd93f9` nos widgets interativos, hover pink, focus cyan,
  cards `.hefesto-dualsense4unix-card` com fundo `#21222c`.
- **19 ButtonGlyph SVGs originais** (FEAT-BUTTON-SVG-01) em `assets/glyphs/`:
  4 face + 4 dpad + 4 triggers + 4 system (sem logo Sony) + 2 sticks + mic.
  Widget `ButtonGlyph(GtkDrawingArea)` + mapa `BUTTON_GLYPH_LABELS` PT-BR.
- **Bloco Status redesenhado** (UI-STATUS-STICKS-REDESIGN-01) em 3 colunas
  homogêneas: StickPreviewGtk + grid 4×4 de glyphs com feedback visual
  ao vivo. L2/R2 iluminam quando raw > 30; L3/R3 muda cor do título.
- **Player LEDs reais** (FEAT-PLAYER-LEDS-APPLY-01): bitmask arbitrário
  via `ds.light.playerNumber = PlayerID(bitmask)`, handler IPC
  `led.player_set`.
- **Brightness end-to-end** (FEAT-LED-BRIGHTNESS-02/03): `_to_led_settings`
  propaga → `LedSettings.brightness_level` → RGB escalado antes do
  hardware. Persist no JSON via `_build_profile_from_editor`. Resolve A-06.
- **Editor de perfil dual** (UI-PROFILES-EDITOR-SIMPLE-01): modo simples
  (radios) + modo avançado. Preferência em `gui_preferences.json`.
  `simple_match.py` com `SIMPLE_MATCH_PRESETS` + `detect_simple_preset`.
- **DraftConfig central** (FEAT-PROFILE-STATE-01): pydantic v2 frozen
  compartilhado. `switch-page` + `_refresh_widgets_from_draft` preserva
  edições. Handler IPC `profile.apply_draft` (ordem leds→triggers→rumble→mouse).
- **Rodapé global** (UI-GLOBAL-FOOTER-ACTIONS-01): Aplicar, Salvar Perfil,
  Importar JSON validado, Restaurar Default. Helpers em `gui_dialogs.py`.
- **6 perfis + Meu Perfil** (FEAT-PROFILES-PRESET-06): navegacao/fps/
  aventura/acao/corrida/esportes com identidade cromática e mecânica
  própria. `meu_perfil.json` como slot editável (MatchAny, priority 0).
  `scripts/install_profiles.sh` copia defaults sem sobrescrever.
- **Presets de trigger por posição** (FEAT-TRIGGER-PRESETS-POSITION-01):
  6 presets Feedback + 5 Vibração + Custom em dropdown. Popula os 10
  sliders em 1 clique.
- **Política global de rumble** (FEAT-RUMBLE-POLICY-01): Economia (0.3×)/
  Balanceado (0.7×)/Máximo (1.0×)/Auto. Auto dinâmico por bateria com
  debounce 5s. Slider Custom 0-100%.
- **Matriz 3-fontes do status do daemon** (BUG-DAEMON-STATUS-MISMATCH-01):
  Literal `online_systemd/online_avulso/iniciando/offline` + label PT-BR
  colorido + tooltip + botão "Migrar para systemd".
- **Refactor evdev snapshot único** (REFACTOR-HOTKEY-EVDEV-01): resolve A-09.
- **Script CI version-check** (DOCS-VERSION-SYNC-01).

### Corrigido
- **GUI abre e fecha ao plugar** (BUG-TRAY-SINGLE-FLASH-01): GUI vira
  "primeira vence" via `acquire_or_bring_to_front`; daemon mantém "última
  vence". Handler SIGUSR1 reabre janela. Guard `pgrep` removido da unit.
- **Rumble "Aplicar" não persiste** (BUG-RUMBLE-APPLY-IGNORED-01):
  `DaemonConfig.rumble_active` + `_reassert_rumble()` a 200ms no poll loop
  re-aplica valores sobrepondo writes HID. Handlers `rumble.stop` e
  `rumble.passthrough`.
- **Layout Status** ajustado ao feedback 2026-04-22: sticks lado-a-lado
  em 3 colunas homogêneas, glyphs 40px.
- **Aba Daemon log em card com wrap** (UI-DAEMON-LOG-WRAP-01): filtro ANSI.
- **Aba Emulação alinhada** (UI-EMULATION-ALIGN-01): Gtk.Grid 2-col,
  BUTTON_GLYPH_LABELS PT-BR em "D-pad Cima/Baixo".
- **Aba Mouse limpa** (UI-MOUSE-CLEANUP-01): removido "(fixo nesta versão)".
- **Handler `on_player_led_toggled` conectado** em `app.py`.

### Testes
- Suíte cresceu de 412 (v1.0.0) para **772 passed, 5 skipped**. +360
  testes novos cobrindo single-instance, rumble policy, draft config,
  IPC apply_draft, footer actions, profile presets, trigger presets,
  daemon status matrix, theme CSS, button glyphs, lightbar persist,
  status buttons glyphs, poll loop evdev cache, profile editor roundtrip,
  simple match, entre outros.

---

## [Pre-1.1.0 incremental — 2026-04-22]

### Adicionado (2026-04-22)
- **Módulo `single_instance`**: `acquire_or_takeover(name)` via `fcntl.flock` + SIGTERM(2s)→SIGKILL. Daemon e GUI passam a ser mutuamente exclusivos (modelo "última vence" no daemon). Previne 2+ instâncias criando `UinputMouseDevice` concorrentes (causa do bug "cursor voando" reportado pelo usuário).
- `install.sh`: flags `--enable-autostart` e `--enable-hotplug-gui`. Prompts interativos com default **NÃO** para ambos. Opt-in explícito elimina comportamento invasivo padrão.
- `uninstall.sh`: `pkill -TERM` → `pkill -KILL` residual após `systemctl stop` — zero processo órfão.
- `assets/hefesto-dualsense4unix.service`: `SuccessExitStatus=143 SIGTERM` (takeover não dispara respawn), `StartLimitIntervalSec=30 StartLimitBurst=3` (teto anti-loop).
- `HefestoApp.quit_app`: menu "Sair" do tray agora encerra daemon junto (`systemctl --user stop hefesto-dualsense4unix.service`).

### Corrigido (2026-04-22)
- **Cursor "voando" ao ativar aba Mouse**: causado por 2 daemons concorrentes criando 2 `UinputMouseDevice` separados que disputavam stick do DualSense via evdev e emitiam REL_X/REL_Y em paralelo. Fix via single-instance takeover.
- **PIDs renascendo ao matar processo**: cadeia de 5 fontes de spawn sem mutex (install.sh restart + hotplug unit + udev ADD + launcher GUI + ensure_daemon_running da GUI). Takeover + StartLimit corrige.
- `ensure_daemon_running` consulta pid file via `is_alive()` — não duplica `systemctl start` se o daemon já está vivo fora do systemd.
- Memória Claude (não faz parte do repo) atualizada refletindo HEAD real.

### Adicionado em docs (2026-04-22)
- **23 novas specs de sprint** em `docs/process/sprints/`, incluindo: BUG-TRAY-SINGLE-FLASH-01, BUG-DAEMON-STATUS-MISMATCH-01, BUG-RUMBLE-APPLY-IGNORED-01, FEAT-PLAYER-LEDS-APPLY-01, FEAT-BUTTON-SVG-01, UI-STATUS-STICKS-REDESIGN-01, UI-THEME-BORDERS-PURPLE-01, UI-PROFILES-EDITOR-SIMPLE-01, UI-GLOBAL-FOOTER-ACTIONS-01, UI-DAEMON-LOG-WRAP-01, UI-EMULATION-ALIGN-01, UI-MOUSE-CLEANUP-01, FEAT-TRIGGER-PRESETS-POSITION-01, FEAT-RUMBLE-POLICY-01, FEAT-DEB-PACKAGE-01, FEAT-FIRMWARE-UPDATE-01 (experimental, 3 fases), REFACTOR-HOTKEY-EVDEV-01, REFACTOR-DAEMON-RELOAD-01, FEAT-LED-BRIGHTNESS-02, FEAT-LED-BRIGHTNESS-03, DOCS-VERSION-SYNC-01. Especificações com critérios de aceite executáveis por dev jr.
- `docs/process/SPRINT_ORDER.md`: roadmap atualizado com 42 sprints em 3 waves + ordem paralelizável.
- `docs/process/HISTORICO_V1.md`: apêndice da onda pós-v1.0.0.
- `VALIDATOR_BRIEF.md`: armadilhas A-10 (múltiplas instâncias) e A-11 (race de udev ADD).

### Testes (2026-04-22)
- `test_single_instance.py` (6 testes): acquire, is_alive, pid órfão, takeover via fork com SIGTERM, release.
- `test_quit_app_stops_daemon.py` (4 testes): mock systemctl, FileNotFoundError, TimeoutExpired, tray.stop().
- `test_service_install.py`: atualizado para default `enable=False`, novo `test_install_enable_opt_in`.
- Total da suíte: **412 passed, 4 skipped** (skipped = quit_app no venv sem GdkPixbuf).

---

## [1.0.0] — 2026-04-21

Primeira release estável. Daemon + CLI + TUI + GUI GTK3 inteiros, falando com DualSense real via HID híbrido (pydualsense + evdev). 10 sprints de endurecimento e polimento sobre a 0.1.0.

### Adicionado
- **GUI GTK3 com banner visual**: logo circular (martelo + circuito tech) no canto superior-esquerdo, wordmark "Hefesto - Dualsense4Unix" em xx-large bold, subtitle "daemon de gatilhos adaptativos para DualSense". Janela com título `Hefesto - Dualsense4Unix`.
- **Reconnect automático na GUI**: máquina de 3 estados (`Online` / `Reconectando` / `Offline`) com polling IPC em thread worker, absorvendo restarts curtos do daemon sem flicker. Botão "Reiniciar Daemon" na aba Daemon dispara `systemctl --user restart hefesto-dualsense4unix.service` via subprocess assíncrono. Ver ADR-012.
- **Aba Mouse**: emulação mouse+teclado opt-in via `uinput` — Cross/L2 → BTN_LEFT, Triangle/R2 → BTN_RIGHT, D-pad → KEY_UP/DOWN/LEFT/RIGHT, analógico esquerdo → movimento com deadzone 20/128 e escala configurável, analógico direito → REL_WHEEL/REL_HWHEEL com rate-limit 50ms, R3 → BTN_MIDDLE. Toggle default OFF, sliders de velocidade na GUI.
- **Regra udev USB autosuspend**: `assets/72-ps5-controller-autosuspend.rules` força `power/control=on` e `autosuspend_delay_ms=-1` para `054c:0ce6` e `054c:0df2`. Elimina desconexão transiente do DualSense no Pop!_OS / Ubuntu / Fedora. Ver ADR-013.
- **`install.sh` orquestrado**: instalação completa em passada única — deps do sistema, venv, pacote editável, udev rules (com prompt interativo de sudo), `.desktop` + ícone + launcher desanexado, symlink `~/.local/bin/hefesto-dualsense4unix`, unit systemd `--user`, start automático do daemon. Flags `--no-udev`, `--no-systemd`, `--yes`, `--help`.
- **4 ADRs novos** (010–013) cobrindo socket IPC liveness probe, distinção glyphs vs emojis, máquina de reconnect, USB autosuspend.
- **Polish consistente de UI PT-BR**: Title Case em status (`Conectado Via USB`, `Tentando Reconectar...`, `Daemon Offline`, `Controle Desconectado`). Botões em português (`Iniciar`, `Parar`, `Reiniciar`, `Atualizar`, `Ver Logs`). Acentuação completa em labels visíveis. Siglas USB/BT/IPC/UDP preservadas em maiúsculas.

### Corrigido
- **Socket IPC com unlink cego** (crítico): `IpcServer.start()` agora faz liveness probe com timeout 0.1s antes de deletar o socket; `stop()` respeita `st_ino` registrado no start (soberania de subsistema, meta-regra 9.3). Smoke isolado via env var `HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME=hefesto-dualsense4unix-smoke.sock`. Ver ADR-010.
- **AssertionError ruidoso em `udp_server.connection_made`**: assert gratuito contra `asyncio.DatagramTransport` removido (Python 3.10 entrega `_SelectorDatagramTransport` que não passa isinstance público). Journal limpo em cada startup.
- **GUI congelava com daemon lento ou offline**: `asyncio.run()` síncrono a 20 Hz na thread GTK bloqueava a janela. Migração para `ThreadPoolExecutor` com callbacks via `GLib.idle_add`; `LIVE_POLL_INTERVAL_MS = 100` (10 Hz); timeout de 250ms no `open_unix_connection`. Janela permanece responsiva mesmo com IPC morto.
- **Dualidade `hefesto-dualsense4unix.service` / `hefesto-dualsense4unix-headless.service` removida**: unit única. Dropdown da aba Daemon virou label estática `Unit: hefesto-dualsense4unix.service`. API singular `detect_installed_unit()`.
- **Glyphs Unicode de estado preservados**: `` (U+25CF), `` (U+25CB), ``/`` (U+25AE/U+25AF), `` (U+25D0) são UI textual funcional, não emojis. Distinção formalizada em ADR-011.

### Modificado
- **Novo ícone canônico** (`assets/appimage/Hefesto-Dualsense4Unix.png`): martelo + placa de circuito, gradiente teal→magenta. Cache GTK `hicolor` populado em 9 tamanhos (16 a 512 px) pelo `install.sh`.
- **`VALIDATOR_BRIEF.md`** criado na raiz com invariantes, contratos de runtime e registro das armadilhas A-01 a A-06 descobertas durante esta onda.

### Diagnósticos

- `pytest tests/unit` → **335 passed**, zero failures.
- `ruff check src/ tests/` limpo.
- `./scripts/check_anonymity.sh` OK.
- Smoke USB + BT completos sem traceback, socket de produção preservado.

---

## [0.1.0] — 2026-04-20

### Adicionado
- **Core HID**: `IController` síncrona, backend híbrido `PyDualSenseController` (output HID via pydualsense, input via evdev para contornar conflito com `hid_playstation`), `FakeController` determinístico com replay de capture.
- **Trigger effects**: 19 factories nomeadas (`Off`, `Rigid`, `Pulse`, `PulseA/B`, `Resistance`, `Bow`, `Galloping`, `SemiAutoGun`, `AutoGun`, `Machine`, `Feedback`, `Weapon`, `Vibration`, `SlopeFeedback`, `MultiPositionFeedback`, `MultiPositionVibration`, `SimpleRigid`, `Custom`), todas validadas em ranges com clamp em 255.
- **LED e rumble**: `LedSettings` imutável, `RumbleEngine` com throttle de 20ms e stop imediato.
- **Daemon**: `Daemon.run()` com poll 60Hz, signal handlers SIGINT/SIGTERM, BatteryDebouncer (V2-17), integração com IpcServer, UdpServer e AutoSwitcher.
- **EventBus pubsub** com `asyncio.Queue` por subscriber, drop-oldest em overflow, thread-safe via `call_soon_threadsafe`.
- **StateStore** thread-safe com `RLock`, snapshot imutável, contadores.
- **Profile schema v1** com pydantic v2 (`MatchCriteria` AND/OR, `MatchAny` sentinel), loader atômico com `filelock`, `ProfileManager` com activate/apply/select_for_window.
- **AutoSwitcher** com poll 2Hz e debounce 500ms, respeita `HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT`.
- **Window detection X11** via `python-xlib`, `wm_class` segundo elemento (V3-6), `exe_basename` via `/proc/PID/exe`.
- **IPC JSON-RPC 2.0** sobre Unix socket 0600 com 8 métodos v1 e `IpcClient` async.
- **UDP server compat DSX** em `127.0.0.1:6969` com `RateLimiter` global 2000/s + per-IP 1000/s + `_sweep` periódico (V3-1), 6 tipos de instrução.
- **Gamepad virtual** Xbox 360 via `python-uinput` (VID `045e:028e`), forward analog + botões + d-pad com diff de estado.
- **HotkeyManager** com combo sagrado (PS+D-pad) e buffer 150ms, passthrough bloqueado em modo emulação (V2-4).
- **Systemd --user service** com unit única `hefesto-dualsense4unix.service` (SIMPLIFY-UNIT-01 revogou a dualidade normal/headless original da V2-12), `ServiceInstaller` com install/uninstall/start/stop/restart/status.
- **CLI completo**: `version`, `status`, `battery`, `led`, `tui`, `daemon start/install-service/uninstall-service/stop/restart/status`, `profile list/show/activate/create/delete`, `test trigger/led/rumble`, `emulate xbox360`.
- **TUI Textual**: `HefestoApp` com `MainScreen` mostrando info do daemon, lista de perfis, preview widgets (`TriggerBar`, `BatteryMeter`, `StickPreview`) com poll 10Hz via IPC.
- **Captures HID**: `record_hid_capture.py` grava estado em JSONL gzip (`.bin`), `FakeController.from_capture()` reproduz cronologicamente; gate de 5MB no CI.
- **9 ADRs** cobrindo escolhas de arquitetura.
- **Documentação completa**: protocolo UDP, IPC, trigger modes, quickstart.
- **Diário de descobertas** em `docs/process/discoveries/` (5 jornadas documentadas).

### Runtime validado
- 279 testes unit verdes em Python 3.10, 3.11 e 3.12.
- Smoke runtime real contra DualSense USB conectado em Pop!_OS 22.04, kernel 6.17.
- Proof visual (SVG) da TUI commitado em `docs/process/discoveries/assets/`.

### Pendente para v0.2+
- Captures HID com input ativo (#54).
- Matriz de distros testadas (`DOCS.2`).
- Guia de criação de perfis com `xprop` (`DOCS.1`).
- Benchmark de polling 60/120/1000 Hz (`INFRA.1`).
- Tray GTK3 AppIndicator (`W5.4`, opcional).
- Release PyPI (`W7.1`).
- AppImage bundle (`W7.2`, opcional).

### Não-escopo confirmado
- Windows, macOS, Wayland nativo, Bluetooth Audio.
- HidHide — superado pelo backend híbrido evdev+pydualsense (jornada em `docs/process/discoveries/2026-04-20-hotfix-2-hid-playstation-kernel-conflict.md`).

[0.1.0]: https://github.com/AndreBFarias/hefesto-dualsense4unix/releases/tag/v0.1.0
