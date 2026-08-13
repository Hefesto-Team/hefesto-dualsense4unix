# ADR-014 — Suporte ao COSMIC DE (Wayland) no Pop!_OS

**Data:** 2026-04-22
**Status:** aceito
**Complementa/substitui:** ADR-007 (Wayland diferido)

---

## Contexto

O Pop!_OS 24.04 entregou o COSMIC DE em produção (System76, Wayland nativo).
Com isso, o deferimento de Wayland documentado no ADR-007 precisa ser revisado.
O principal ponto de ruptura é a detecção de janela ativa, que o Hefesto usa para
o autoswitch de perfis:

- `src/hefesto_dualsense4unix/integrations/xlib_window.py` depende de `python-xlib` + variável
  `DISPLAY`. Em Wayland puro (sem XWayland), não há servidor X; o módulo retornava
  `{"wm_class": "unknown"}` silenciosamente e o autoswitch ficava preso em
  `fallback.json`.
- Compositors como COSMIC 1.0+ e GNOME 46+ expõem o portal XDG D-Bus
  `org.freedesktop.portal.Window.GetActiveWindow`, que permite obter informações
  da janela ativa sem depender de X11.

## Decisão

Adotar arquitetura de backends intercambiáveis para detecção de janela ativa,
implementada em camadas:

### Camada 1 — Backends e factory (implementado nesta sprint)

1. Pacote `src/hefesto_dualsense4unix/integrations/window_backends/`:
   - `base.py` — `WindowInfo` (dataclass) e `WindowBackend` (Protocol).
   - `xlib.py` — `XlibBackend`: lógica X11 via `python-xlib`.
   - `wayland_portal.py` — `WaylandPortalBackend`: cliente D-Bus do portal XDG.
   - `null.py` — `NullBackend`: retorna sempre `None` (modo silencioso).

2. `src/hefesto_dualsense4unix/integrations/window_detect.py` — factory `detect_window_backend()`:
   - `WAYLAND_DISPLAY` + `DISPLAY` → `XlibBackend` (XWayland, preferido).
   - `WAYLAND_DISPLAY` sem `DISPLAY` → `WaylandPortalBackend`.
   - `DISPLAY` sem `WAYLAND_DISPLAY` → `XlibBackend`.
   - Nenhum → `NullBackend` (loga `autoswitch_compositor_unsupported`).

3. `xlib_window.py` convertido em shim de compatibilidade: re-exporta
   `get_active_window_info` de `window_detect`. Código legado não precisa de
   alteração.

   > **O shim não existe mais** — ver a nota de verificação no fim desta ADR.

### Camada 2 — Portal XDG (implementado nesta sprint)

`WaylandPortalBackend` tenta (em ordem):
1. `jeepney` (puro Python, sem dep nativa compilada).
2. `dbus-fast` (assíncrono, mais completo).

Se nenhuma biblioteca estiver disponível, retorna `None` sem erro. A dependência
é **opcional** — não incluída em `pyproject.toml` como dep obrigatória.

### Camada 3 — Applet nativo COSMIC

Crate Rust `cosmic-applet-hefesto-dualsense4unix` para integração nativa com o painel COSMIC.

> **Entregue.** Era "sprint futura em V3.4" quando esta ADR foi escrita; o applet
> existe em `packaging/cosmic-applet/` e o `install.sh` o compila e instala por
> **padrão em sessões COSMIC** (`--enable-cosmic-applet` força fora do COSMIC,
> `--no-cosmic-applet` desliga). Verificado em 25/07/2026.

### Camada 2.1 — Cascade portal → wlrctl (v3.1.0)

Re-introduzida em `v3.1.0` (sprint `BUG-COSMIC-WLR-BACKEND-REGRESSION-01`):

- `WlrctlBackend` (`src/hefesto_dualsense4unix/integrations/window_backends/wlr_toplevel.py`):
  cliente do `wlrctl` CLI usando o protocolo `wlr-foreign-toplevel-management-unstable-v1`.
- `_WaylandCascadeBackend` (em `window_detect.py`): tenta portal primeiro, cai para
  wlrctl se portal retorna None ou está no estado "unsupported" (threshold de 3
  falhas consecutivas no `WaylandPortalBackend`).

Validação empírica em Pop!_OS 24.04 + COSMIC 1.0.0 (2026-05-16):

- `xdg-desktop-portal-cosmic` em uso ainda **não implementa**
  `org.freedesktop.portal.Window::GetActiveWindow`. Portal sempre retorna None.
- `cosmic-comp 1.0.0` em uso **não expõe** `wlr-foreign-toplevel-management-unstable-v1`.
  `wlrctl toplevel list` retorna exit code 1 com `"Foreign Toplevel Management interface not found!"`.
- Resultado prático: autoswitch em Wayland puro recai em fallback. **Solução**:
  manter `DISPLAY=:1` (XWayland) ativo — Pop!_OS 24.04 vem com XWayland por
  padrão. `XlibBackend` cobre janelas XWayland (Steam, Proton, browsers Xorg)
  e o autoswitch funciona para esses (caso primário do projeto: jogos via Proton).
- Documentado em `arquivo/processo-pre-1.0:docs/process/discoveries/2026-05-15-cosmic-1.0-validation.md`.

### Camada 4 — Tray fallback notification (v3.1.0)

Sprint `FEAT-COSMIC-TRAY-FALLBACK-01` introduz três defesas em `src/hefesto_dualsense4unix/app/tray.py`:

1. **Defer da criação do `AppIndicator`** via `GLib.timeout_add(500, ...)` em
   sessão COSMIC. Empírico: cobre race condition em que o app criava o
   indicator antes do `cosmic-applet-status-area` registrar
   `org.kde.StatusNotifierWatcher`.
2. **Probe explícito** do `StatusNotifierWatcher` via D-Bus `NameHasOwner`
   logo após criar o indicator. Se ausente em sessão COSMIC, emite warning
   estruturado.
3. **Notification D-Bus** orientadora (`org.freedesktop.Notifications`) com
   `once_key="cosmic_tray_missing"` (1x por execução) instruindo o usuário a
   habilitar o applet "Área de status" no cosmic-panel via
   "Configurações > Painel > Applets".

Em Pop!_OS 24.04 + COSMIC 1.0.0 com `cosmic-applets 1.0.12`, o applet
status-area existe mas **não vem por padrão no painel** — precisa adicionar
manualmente. Validação real confirmou:

```
gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
    --method org.freedesktop.DBus.NameHasOwner org.kde.StatusNotifierWatcher
(false,)
```

Após o usuário adicionar o applet no painel via cosmic-settings, `NameHasOwner`
retorna `true` e o tray do Hefesto passa a renderizar normalmente.

## Consequencias

**Positivo:**
- Autoswitch de perfil funciona em XWayland (caso mais comum de COSMIC hoje).
- Cascade portal → wlrctl cobre 4 compositors wlroots-like (COSMIC futuro,
  Sway, Hyprland, niri, river) quando o portal não estiver disponível.
- Degradação silenciosa e documentada em Wayland puro sem portal disponível.
- API legada (`get_active_window_info` dict) preservada — zero breaking changes.
- Backends são isolados e testáveis via monkeypatch de `os.environ`.
- Em sessão COSMIC, tray usa defer + probe + notification orientadora — sem
  ícone "fantasma" silenciosamente faltando.

**Negativo:**
- `WaylandPortalBackend` depende de `jeepney` (extra opcional `[cosmic]` em
  pyproject.toml; `install.sh` instala por default desde v3.1.0).
- `WlrctlBackend` depende do binário `wlrctl` (Recommends do `.deb` desde
  v2.4.1; `install.sh` em sessão COSMIC oferece instalação automática via apt).
- Portal `GetActiveWindow` não existe em compositors Wayland antigos
  (GNOME < 46, Sway, Hyprland, e — confirmado empiricamente — COSMIC 1.0.0).
  Nesses ambientes o cascade tenta wlrctl em seguida.
- COSMIC 1.0.0 também não expõe `wlr-foreign-toplevel-management` ainda —
  ver `arquivo/processo-pre-1.0:docs/process/discoveries/2026-05-15-cosmic-1.0-validation.md`. Workaround
  efetivo é manter XWayland ativo.
- Validação manual em Pop!_OS 24.04 + COSMIC 1.0.0 real concluída em
  `arquivo/processo-pre-1.0:docs/process/discoveries/2026-05-15-cosmic-1.0-validation.md`.

## Alternativas consideradas

- **Manter fallback silencioso** (comportamento anterior de ADR-007): descartado
  porque COSMIC em produção invalida a hipótese de "Wayland é futuro distante".
- **Forçar XWayland sempre via `DISPLAY=:0`**: descartado porque invade o ambiente
  do usuário e exige dependência de um servidor X em paralelo.
- **Substituir toda a stack por `pydbus`**: descartado pela dep nativa (libdbus-1);
  `jeepney` puro Python é mais portável.

---

## Nota de verificação — 2026-07-31

A arquitetura de backends confere: `window_backends/` com `base`, `xlib`,
`wayland_portal`, `wlr_toplevel` e `null`, e a factory em `window_detect.py`.

**O item 3 da Camada 1 caducou.** O shim `integrations/xlib_window.py` foi
retirado em 29/07 (CODIGO-MORTO-01) e o arquivo hoje é uma **lápide**: o módulo
levanta `ImportError` já no import, com mensagem que aponta o substituto. Ele
não re-exporta nada, e a frase "código legado não precisa de alteração" virou o
oposto — código legado que importe `xlib_window` **quebra no import**, de
propósito.

O motivo não foi limpeza: a `XlibClient` que morava ali lia o
`_NET_ACTIVE_WINDOW` da raiz **sem gate de foco**, exatamente o defeito que o
UX-02 e o FOCO-01 curaram no backend vivo
(`window_backends/xlib.py`, que só aceita a leitura quando `get_input_focus()`
e `_NET_ACTIVE_WINDOW` concordam). Quem importasse o shim reintroduziria o
ping-pong de perfil com a suíte verde — daí o erro alto no import, e não uma
leitura errada e silenciosa a 2 Hz.

Substitutos, e é o que a lápide manda usar:

```python
from hefesto_dualsense4unix.integrations.window_detect import build_window_reader

ler_janela = build_window_reader()   # backend instanciado UMA vez
info = ler_janela()                  # wm_class / wm_name / pid / exe_basename
```

Para leitura pontual (CLI, `doctor`), `window_detect.get_active_window_info()`
mantém a assinatura do antigo `xlib_window.get_active_window_info`.

O resto da ADR não foi reconferido nesta passagem — a nota cobre só a lápide.

---

## Nota de verificação — 2026-08-12 (PROCESSO-CEGO-01)

Conferidos contra o código o item 1 da Camada 1, a Camada 2.1 e a frase "API
legada preservada". Um achado que a ADR não dizia, e que custou caro:

**"O mesmo dict" NÃO é o mesmo conteúdo.** A ADR promete que os backends
devolvem `wm_class`/`wm_name`/`pid`/`exe_basename` — e devolvem, com as MESMAS
chaves. Só que `exe_basename` chega **sempre vazio** fora do `xlib`:

| Backend | `exe_basename` | Onde, no fonte |
|---|---|---|
| `xlib` | resolvido | `window_backends/xlib.py`, `_exe_basename_from_pid` → `os.readlink("/proc/<pid>/exe")` |
| `portal` | `""` literal | `window_backends/wayland_portal.py`, `_parse_portal_result` — **mesmo tendo o `pid`** do portal em mãos |
| `wlrctl` | `""` literal | `window_backends/wlr_toplevel.py`, fim de `get_active_window_info` (o `wlrctl` não devolve pid) |
| `null` | não devolve janela | `window_backends/null.py` |

Isso importa porque `MatchCriteria.matches` é um **E** entre os campos
preenchidos e "alvo vazio nunca casa": um perfil com `process_name` num backend
de Wayland **não entra nunca**, e leva junto a `window_class` que casaria
sozinha. Foi a causa medida de cinco perfis de gênero da mantenedora jamais
ativarem em 30 dias de journal (PERFIL-MUDO-01, 10/08/2026) — o mesmo defeito
que o ADR-007 recomendava como *workaround* de Wayland (ver a correção lá).

O fato virou código verificável em
`integrations/window_detect.backend_ve_nome_do_processo`, com
`BACKENDS_QUE_VEEM_O_PROCESSO`/`BACKENDS_CEGOS_AO_PROCESSO` ao lado; o teste
`tests/unit/test_o_nome_do_processo_que_nao_casa.py` confere a tabela contra o
que cada backend REALMENTE devolve, para ela não envelhecer em silêncio.

Nada mais desta ADR foi contrariado pelo código nesta passagem: a factory de
`window_detect.py` decide pelos quatro ramos de ambiente descritos, e a cascata
`portal → wlrctl → null` está onde a Camada 2.1 diz.
