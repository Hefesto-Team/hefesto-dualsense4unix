# ADR-017 — Sistema de Plugins Python (FEAT-PLUGIN-01)

**Status:** aceito
**Data:** 2026-04-22
**Autor:** equipe Hefesto
**Contexto:** V2.0

---

## Contexto

Perfis hoje sao JSON estaticos: `triggers`, `leds`, `rumble` declarados em tempo de edicao.
Nao ha como escrever um perfil que reaja ao jogo em tempo real — por exemplo,
"mudar lightbar para vermelho quando HP < 30%" ou "vibracao forte ao recarregar".

O UDP DSX (porta 6969) permite que jogos enviem comandos ao daemon, mas o caminho
inverso (leitura de estado do jogo) exige que o proprio jogo mande pacotes. Um sistema
de plugins abre alternativa: scripts Python lidos do disco que rodam no daemon com
acesso limitado ao `IController` + eventos + state.

---

## Decisao

Carregar plugins Python de `~/.config/hefesto/plugins/*.py` (cada arquivo = 1 plugin).
A API minima exposta e:

- `Plugin` ABC: hooks `on_load`, `on_tick`, `on_button_down`, `on_battery_change`,
  `on_profile_change`, `on_unload`. Todos com implementacao no-op por padrao.
- `PluginContext`: container de dependencias injetado em `on_load`. Expoe somente
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
from hefesto.plugin_api import Plugin, PluginContext

class MeuPlugin(Plugin):
    name = "meu_plugin"          # slug unico, snake_case
    profile_match = ["eldenring"] # lista de perfis; [] = todos

    def on_load(self, ctx: PluginContext) -> None:
        self.ctx = ctx

    def on_tick(self, state) -> None:
        # chamado ~30-120 Hz; manter < 1 ms
        ...
```

### Diretorio de instalacao

```
~/.config/hefesto/plugins/
```

Arquivos com prefixo `_` sao ignorados (uso interno/desabilitado).

### Ativacao

Por padrao, plugins sao desativados (`plugins_enabled = False` em `DaemonConfig`).
Ativar via:

- Configuracao em `~/.config/hefesto/config.toml`: `plugins_enabled = true`
- Variavel de ambiente: `HEFESTO_PLUGINS_ENABLED=1`

---

## Limitacoes e seguranca

### Sem sandbox forte

Plugins rodam com os mesmos privilegios do processo daemon (usuario comum, sem root).
Nao ha `RestrictedPython`, cgroups ou bubblewrap. O usuario e **inteiramente
responsavel** pelo codigo instalado em `~/.config/hefesto/plugins/`.

Mitigacao operacional: o diretorio `~/.config/hefesto/plugins/` deve ser `owned by user`
(o proprio usuario quem instala os arquivos ali). Nao instale plugins de fontes
desconhecidas.

Sandbox forte (bubblewrap, seccomp, Lua via `lupa`) e escopo de V3.

### Nao versionar a API

A API `Plugin` / `PluginContext` e considerada instavel ate o primeiro release publico
de plugins. Mudancas breaking exigirao bump de versao da API e nota de migracao.

### Performance

- Cada hook tem watchdog de `time.monotonic`: se demorar > 5 ms, emite log warning.
- Tres avisos consecutivos desativam o plugin automaticamente (flag `_PluginEntry.disabled`).
- `on_tick` e chamado no poll loop principal (~60 Hz por padrao). Plugins **nao** devem
  fazer I/O bloqueante ou chamadas de rede diretamente em `on_tick`.

---

## Alternativas consideradas

| Alternativa | Descartada por |
|---|---|
| Lua via `lupa` | Menos bibliotecas disponiveis; V3 conforme roadmap |
| `RestrictedPython` | Falsa sensacao de seguranca; overhead de parse; sem vantagem real em relacao a doc+responsabilidade do usuario |
| Subprocess isolado | Complexidade de IPC; latencia inaceitavel no poll loop |
| WASM/Wasmer | Ecossistema Python-WASM imaturo em 2026 |

---

## Impacto no codigo

Arquivos novos:
- `src/hefesto/plugin_api/__init__.py`
- `src/hefesto/plugin_api/plugin.py`
- `src/hefesto/plugin_api/context.py`
- `src/hefesto/plugin_api/loader.py`
- `src/hefesto/daemon/subsystems/plugins.py`
- `src/hefesto/cli/cmd_plugin.py`
- `examples/plugins/lightbar_rainbow.py`
- `tests/unit/test_plugin_api.py`

Arquivos modificados:
- `src/hefesto/daemon/lifecycle.py` — `DaemonConfig.plugins_enabled`, slot `_plugins_subsystem`, wire-up
- `src/hefesto/daemon/subsystems/__init__.py` — registro de `PluginsSubsystem`
- `src/hefesto/daemon/subsystems/connection.py` — `shutdown()` chama `ps.stop()`
- `src/hefesto/daemon/ipc_server.py` — handlers `plugin.list`, `plugin.reload`
- `src/hefesto/cli/app.py` — registro do `plugin_app`

---

## Rodape

Decisao tomada com base em: seguranca pratica (usuario responsavel), simplicidade de
implementacao, maxima compatibilidade com ecossistema Python, alinhamento com o modelo
de extensao do projeto DualSenseX original.
