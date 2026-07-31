# ADR-017 — Sistema de Plugins Python (FEAT-PLUGIN-01)

**Status:** aceito
**Data:** 2026-04-22
**Autor:** equipe Hefesto
**Contexto:** V2.0

---

## Contexto

Perfis hoje sao JSON estaticos: `triggers`, `leds`, `rumble` declarados em tempo de edicao.
Não ha como escrever um perfil que reaja ao jogo em tempo real — por exemplo,
"mudar lightbar para vermelho quando HP < 30%" ou "vibracao forte ao recarregar".

O UDP DSX (porta 6969) permite que jogos enviem comandos ao daemon, mas o caminho
inverso (leitura de estado do jogo) exige que o próprio jogo mande pacotes. Um sistema
de plugins abre alternativa: scripts Python lidos do disco que rodam no daemon com
acesso limitado ao `IController` + eventos + state.

---

## Decisão

Carregar plugins Python de `~/.config/hefesto-dualsense4unix/plugins/*.py` (cada
arquivo = 1 plugin). A API minima exposta e:

- `Plugin` ABC: hooks `on_load`, `on_tick`, `on_button_down`, `on_battery_change`,
  `on_profile_change`, `on_unload`. Todos com implementação no-op por padrao.
- `PluginContext`: container de dependências injetado em `on_load`. Expoe somente
  proxies sobre `IController` (subset de output + estado read-only), `EventBus.subscribe`,
  `StateStore.counter` e um logger prefixado.
- `load_plugins_from_dir(path)`: importa via `importlib.util`, instancia a primeira
  subclasse concreta de `Plugin` encontrada em cada arquivo. Erros de import sao
  ignorados com log warning.
- `PluginsSubsystem`: subsystem do daemon que carrega plugins no start, despacha
  hooks no poll loop e chama `on_unload` no shutdown.

---

## Convencoes da API

### Arquivo de plugin

```python
from hefesto_dualsense4unix.plugin_api import Plugin, PluginContext

class MeuPlugin(Plugin):
    name = "meu_plugin"          # slug unico, snake_case
    profile_match = ["eldenring"] # lista de perfis; [] = todos

    def on_load(self, ctx: PluginContext) -> None:
        self.ctx = ctx

    def on_tick(self, state) -> None:
        # chamado ~30-120 Hz; manter < 1 ms
        ...
```

### Diretório de instalação

```
~/.config/hefesto-dualsense4unix/plugins/
```

Arquivos com prefixo `_` sao ignorados (uso interno/desabilitado).

O diretório pode ser trocado por `HEFESTO_DUALSENSE4UNIX_PLUGINS_DIR` — a
variavel tem precedência sobre o caminho acima.

### Ativação

Por padrão, plugins sao desativados (`plugins_enabled = False` em `DaemonConfig`).
Ativar via:

- Variavel de ambiente: `HEFESTO_DUALSENSE4UNIX_PLUGINS_ENABLED=1`
- `plugins_enabled = True` no `DaemonConfig` (no código)

As duas so sao lidas na **subida** do daemon — ver a nota de verificação no
rodape antes de tentar ligar plugins num daemon já rodando.

---

## Limitações e seguranca

### Sem sandbox forte

Plugins rodam com os mesmos privilegios do processo daemon (usuário comum, sem root).
Não ha `RestrictedPython`, cgroups ou bubblewrap. O usuário e **inteiramente
responsavel** pelo código instalado em `~/.config/hefesto-dualsense4unix/plugins/`.

Mitigacao operacional: o diretório `~/.config/hefesto-dualsense4unix/plugins/` deve ser `owned by user`
(o próprio usuário quem instala os arquivos ali). Não instale plugins de fontes
desconhecidas.

Sandbox forte (bubblewrap, seccomp, Lua via `lupa`) e escopo de V3.

### Não versionar a API

A API `Plugin` / `PluginContext` e considerada instavel ate o primeiro release publico
de plugins. Mudancas breaking exigirao bump de versão da API e nota de migracao.

### Performance

- Cada hook tem watchdog de `time.monotonic`: se demorar > 5 ms, emite log warning.
- Três avisos consecutivos desativam o plugin automaticamente (flag `_PluginEntry.disabled`).
- `on_tick` e chamado no poll loop principal (~60 Hz por padrão). Plugins **não** devem
  fazer I/O bloqueante ou chamadas de rede diretamente em `on_tick`.

---

## Alternativas consideradas

| Alternativa | Descartada por |
|---|---|
| Lua via `lupa` | Menos bibliotecas disponiveis; V3 conforme roadmap |
| `RestrictedPython` | Falsa sensacao de seguranca; overhead de parse; sem vantagem real em relação a doc+responsabilidade do usuário |
| Subprocess isolado | Complexidade de IPC; latencia inaceitavel no poll loop |
| WASM/Wasmer | Ecossistema Python-WASM imaturo em 2026 |

---

## Impacto no código

Arquivos novos:
- `src/hefesto_dualsense4unix/plugin_api/__init__.py`
- `src/hefesto_dualsense4unix/plugin_api/plugin.py`
- `src/hefesto_dualsense4unix/plugin_api/context.py`
- `src/hefesto_dualsense4unix/plugin_api/loader.py`
- `src/hefesto_dualsense4unix/daemon/subsystems/plugins.py`
- `src/hefesto_dualsense4unix/cli/cmd_plugin.py`
- `examples/plugins/lightbar_rainbow.py`
- `tests/unit/test_plugin_api.py`

Arquivos modificados:
- `src/hefesto_dualsense4unix/daemon/lifecycle.py` — `DaemonConfig.plugins_enabled`, slot `_plugins_subsystem`, wire-up
- `src/hefesto_dualsense4unix/daemon/subsystems/__init__.py` — registro de `PluginsSubsystem`
- `src/hefesto_dualsense4unix/daemon/connection.py` — `shutdown()` chama `ps.stop()`. O arquivo nasceu em `daemon/subsystems/` e foi movido para `daemon/` no commit `560a0b2` (REFACTOR-CONNECTION-FUNCTIONS-01, auditoria P2-02): é uma coleção de funções soltas, não uma classe com `start()`/`stop()` como os outros módulos de `subsystems/`
- `src/hefesto_dualsense4unix/daemon/ipc_server.py` — handlers `plugin.list`, `plugin.reload`
- `src/hefesto_dualsense4unix/cli/app.py` — registro do `plugin_app`

---

## Nota de verificação — 2026-07-31

A decisão continua válida. **As receitas de ativação desta ADR nunca foram
verdade no código**, e quem seguisse a seção "Ativação" ao pé da letra não
ligava plugin nenhum. O que foi corrigido no corpo acima, item a item:

- Ativação por **arquivo de configuração** (`~/.config/hefesto/config.toml`,
  `plugins_enabled = true`): **removida**. O daemon não lê arquivo de
  configuração nenhum — nem esse, nem `daemon.toml`
  (BUG-DAEMON-TOML-DEAD-01). A receita era morta na origem.
- Variavel de ambiente: era `HEFESTO_PLUGINS_ENABLED`, que tem **zero**
  ocorrências em `src/`. A real é `HEFESTO_DUALSENSE4UNIX_PLUGINS_ENABLED=1`,
  lida em `daemon/subsystems/plugins.py` (`PluginsSubsystem.is_enabled`).
- Diretório de plugins: era `~/.config/hefesto/plugins/`, o layout curto
  legado. O real é `~/.config/hefesto-dualsense4unix/plugins/`
  (`_default_plugins_dir` em `daemon/subsystems/plugins.py`), com override por
  `HEFESTO_DUALSENSE4UNIX_PLUGINS_DIR` — variavel que a ADR não citava.
- Import do exemplo de plugin: era `from hefesto.plugin_api import ...`, pacote
  que não existe. O real é `from hefesto_dualsense4unix.plugin_api import
  Plugin, PluginContext`, exatamente como o `__init__.py` do pacote documenta.

Uma limitação a mais, medida agora e que a ADR não previa: **os dois switches
só valem na subida do daemon**. `_start_plugins` é chamado uma vez, na
sequência de start (`daemon/lifecycle.py`), e `reload_config` não reinicia
subsistemas — então `daemon.reload` com `plugins_enabled: true` troca o campo
do `DaemonConfig` e **não** carrega plugin num daemon já rodando. Mesma forma do
achado da ADR-016 sobre métricas. Como o daemon roda sob `systemd --user`,
exportar a variavel num terminal também não o alcança: ela precisa estar no
ambiente da unit.

`plugins_enabled` **existe** de fato em `DaemonConfig`
(`daemon/lifecycle.py`), e o `PluginsSubsystem` está registrado em
`daemon/subsystems/__init__.py` — nisso a ADR confere.

---

## Rodape

Decisão tomada com base em: seguranca prática (usuário responsavel), simplicidade de
implementação, maxima compatibilidade com ecossistema Python, alinhamento com o modelo
de extensão do projeto DualSenseX original.
