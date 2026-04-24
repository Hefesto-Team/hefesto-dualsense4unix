# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Segue [SemVer](https://semver.org/lang/pt-BR/).

## [Unreleased]

### Adicionado
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
entre o fallback hardcoded de `src/hefesto/__init__.py` e a versão
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
  structlog.types import Processor` em `src/hefesto/utils/logging_config.py`
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
  - `src/hefesto/__init__.py` detecta pydantic < 2 no import e emite
    `ImportWarning` com instrução acionável (`pip install --user
    'pydantic>=2'`).
  - `.github/workflows/release.yml` `deb-install-smoke` volta para
    `ubuntu-22.04` (mesmo runner do build) e adiciona passo `pip
    install --user 'pydantic>=2.0'` antes do `apt install`; o
    `hefesto --version` roda com `PYTHONPATH` apontando para o user
    site primeiro, garantindo que `import pydantic` resolva a v2.
  README atualizado com o novo caminho canônico (2 comandos:
  `pip install --user pydantic>=2` + `apt install ./hefesto_*.deb`).

### Infraestrutura
- **Gate `version-sync` no CI** (CHORE-VERSION-SYNC-GATE-01): novo job
  em `.github/workflows/ci.yml` que falha se o fallback `__version__`
  de `src/hefesto/__init__.py` divergir de `pyproject.toml
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
  `src/hefesto/app/app.py` é declarativo e não foi estendido junto
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
  `("●", "")`), o filtro bloqueia a remoção. 23 testes regressão
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
  com o código do Hefesto (usa API pydantic v2 — `ConfigDict`). O
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
  `src/hefesto/__init__.py` tinha `__version__ = "1.0.0"` hardcoded por
  ~3 releases, afetando `hefesto version`, título/subtítulo da TUI,
  nome do asset AppImage no GitHub Release (v2.2.0 saiu como
  `Hefesto-1.0.0-x86_64.AppImage`) e validação do teste `test_cli`.
  Fix: `__version__` passa a ser lido dinamicamente via
  `importlib.metadata.version("hefesto")` com fallback hardcoded
  sincronizado ao `pyproject.toml`. `scripts/build_appimage.sh`
  alinhado ao padrão de `build_deb.sh` (lê `pyproject.toml` direto,
  sem depender do pacote estar importável). Regressão futura coberta
  por `CHORE-VERSION-SYNC-GATE-01` (enfileirada).

### Adicionado
- **Aba Firmware na GUI** (FEAT-FIRMWARE-UPDATE-GUI-01):
  nova aba permite consultar versão atual do firmware do DualSense e
  aplicar blob oficial da Sony via wrapper `dualsensectl`. Backend em
  `src/hefesto/integrations/firmware_updater.py` invoca `dualsensectl
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
  desta versão, qualquer PR/push que regride `mypy src/hefesto` quebra
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
  novo módulo `src/hefesto/profiles/slug.py` com `slugify()`
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
  `apt install`, valida `hefesto --version` e `hefesto-gui --help`,
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
  - `src/hefesto/integrations/audio_control.py`: `AudioControl`
    auto-detecta wpctl → pactl → none; debounce 200ms; nunca
    `shell=True`; toggle retorna novo estado.
  - `Daemon._start_mic_hotkey` subscribe em BUTTON_DOWN, filtra mic_btn,
    chama `AudioControl.toggle` + `controller.set_mic_led(muted)`.
    Dupla sincronização: LED do controle espelha mute do sistema.
  - Opt-out via `DaemonConfig.mic_button_toggles_system: bool = True`.
- **Daemon refatorado em subsystems modulares** (REFACTOR-LIFECYCLE-01):
  - `src/hefesto/daemon/subsystems/`: 10 módulos temáticos
    (poll, ipc, udp, autoswitch, mouse, rumble, hotkey, metrics,
    plugins, connection).
  - `src/hefesto/daemon/context.py`: `DaemonContext` dataclass
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
  - `src/hefesto/plugin_api/`: ABC `Plugin` com hooks on_load/on_tick/
    on_button_down/on_battery_change/on_profile_change/on_unload
    (defaults no-op). `PluginContext` expõe controller + bus.subscribe
    + store.counter + log prefixado.
  - `load_plugins_from_dir` via `importlib.util` — skip ImportError.
  - `PluginsSubsystem` carrega de `~/.config/hefesto/plugins/*.py`.
  - Watchdog: hook >5ms loga warning; >3 violações seguidas desativa.
  - CLI `hefesto plugin list/reload`. IPC handlers `plugin.list` e
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
  + DualSense/Edge). Reusa `hefesto-gui-hotplug.service` — idempotência
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
  cards `.hefesto-card` com fundo `#21222c`.
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
- `assets/hefesto.service`: `SuccessExitStatus=143 SIGTERM` (takeover não dispara respawn), `StartLimitIntervalSec=30 StartLimitBurst=3` (teto anti-loop).
- `HefestoApp.quit_app`: menu "Sair" do tray agora encerra daemon junto (`systemctl --user stop hefesto.service`).

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
- **GUI GTK3 com banner visual**: logo circular (martelo + circuito tech) no canto superior-esquerdo, wordmark "Hefesto" em xx-large bold, subtitle "daemon de gatilhos adaptativos para DualSense". Janela com título `Hefesto - DSX para Unix`.
- **Reconnect automático na GUI**: máquina de 3 estados (`Online` / `Reconectando` / `Offline`) com polling IPC em thread worker, absorvendo restarts curtos do daemon sem flicker. Botão "Reiniciar Daemon" na aba Daemon dispara `systemctl --user restart hefesto.service` via subprocess assíncrono. Ver ADR-012.
- **Aba Mouse**: emulação mouse+teclado opt-in via `uinput` — Cross/L2 → BTN_LEFT, Triangle/R2 → BTN_RIGHT, D-pad → KEY_UP/DOWN/LEFT/RIGHT, analógico esquerdo → movimento com deadzone 20/128 e escala configurável, analógico direito → REL_WHEEL/REL_HWHEEL com rate-limit 50ms, R3 → BTN_MIDDLE. Toggle default OFF, sliders de velocidade na GUI.
- **Regra udev USB autosuspend**: `assets/72-ps5-controller-autosuspend.rules` força `power/control=on` e `autosuspend_delay_ms=-1` para `054c:0ce6` e `054c:0df2`. Elimina desconexão transiente do DualSense no Pop!_OS / Ubuntu / Fedora. Ver ADR-013.
- **`install.sh` orquestrado**: instalação completa em passada única — deps do sistema, venv, pacote editável, udev rules (com prompt interativo de sudo), `.desktop` + ícone + launcher desanexado, symlink `~/.local/bin/hefesto`, unit systemd `--user`, start automático do daemon. Flags `--no-udev`, `--no-systemd`, `--yes`, `--help`.
- **4 ADRs novos** (010–013) cobrindo socket IPC liveness probe, distinção glyphs vs emojis, máquina de reconnect, USB autosuspend.
- **Polish consistente de UI PT-BR**: Title Case em status (`Conectado Via USB`, `Tentando Reconectar...`, `Daemon Offline`, `Controle Desconectado`). Botões em português (`Iniciar`, `Parar`, `Reiniciar`, `Atualizar`, `Ver Logs`). Acentuação completa em labels visíveis. Siglas USB/BT/IPC/UDP preservadas em maiúsculas.

### Corrigido
- **Socket IPC com unlink cego** (crítico): `IpcServer.start()` agora faz liveness probe com timeout 0.1s antes de deletar o socket; `stop()` respeita `st_ino` registrado no start (soberania de subsistema, meta-regra 9.3). Smoke isolado via env var `HEFESTO_IPC_SOCKET_NAME=hefesto-smoke.sock`. Ver ADR-010.
- **AssertionError ruidoso em `udp_server.connection_made`**: assert gratuito contra `asyncio.DatagramTransport` removido (Python 3.10 entrega `_SelectorDatagramTransport` que não passa isinstance público). Journal limpo em cada startup.
- **GUI congelava com daemon lento ou offline**: `asyncio.run()` síncrono a 20 Hz na thread GTK bloqueava a janela. Migração para `ThreadPoolExecutor` com callbacks via `GLib.idle_add`; `LIVE_POLL_INTERVAL_MS = 100` (10 Hz); timeout de 250ms no `open_unix_connection`. Janela permanece responsiva mesmo com IPC morto.
- **Dualidade `hefesto.service` / `hefesto-headless.service` removida**: unit única. Dropdown da aba Daemon virou label estática `Unit: hefesto.service`. API singular `detect_installed_unit()`.
- **Glyphs Unicode de estado preservados**: `●` (U+25CF), `○` (U+25CB), `▮`/`▯` (U+25AE/U+25AF), `◐` (U+25D0) são UI textual funcional, não emojis. Distinção formalizada em ADR-011.

### Modificado
- **Novo ícone canônico** (`assets/appimage/Hefesto.png`): martelo + placa de circuito, gradiente teal→magenta. Cache GTK `hicolor` populado em 9 tamanhos (16 a 512 px) pelo `install.sh`.
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
- **AutoSwitcher** com poll 2Hz e debounce 500ms, respeita `HEFESTO_NO_WINDOW_DETECT`.
- **Window detection X11** via `python-xlib`, `wm_class` segundo elemento (V3-6), `exe_basename` via `/proc/PID/exe`.
- **IPC JSON-RPC 2.0** sobre Unix socket 0600 com 8 métodos v1 e `IpcClient` async.
- **UDP server compat DSX** em `127.0.0.1:6969` com `RateLimiter` global 2000/s + per-IP 1000/s + `_sweep` periódico (V3-1), 6 tipos de instrução.
- **Gamepad virtual** Xbox 360 via `python-uinput` (VID `045e:028e`), forward analog + botões + d-pad com diff de estado.
- **HotkeyManager** com combo sagrado (PS+D-pad) e buffer 150ms, passthrough bloqueado em modo emulação (V2-4).
- **Systemd --user service** com unit única `hefesto.service` (SIMPLIFY-UNIT-01 revogou a dualidade normal/headless original da V2-12), `ServiceInstaller` com install/uninstall/start/stop/restart/status.
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

[0.1.0]: https://github.com/AndreBFarias/hefesto/releases/tag/v0.1.0
