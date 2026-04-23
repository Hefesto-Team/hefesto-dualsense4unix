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

- `src/hefesto/integrations/xlib_window.py` depende de `python-xlib` + variável
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

1. Pacote `src/hefesto/integrations/window_backends/`:
   - `base.py` — `WindowInfo` (dataclass) e `WindowBackend` (Protocol).
   - `xlib.py` — `XlibBackend`: lógica X11 via `python-xlib`.
   - `wayland_portal.py` — `WaylandPortalBackend`: cliente D-Bus do portal XDG.
   - `null.py` — `NullBackend`: retorna sempre `None` (modo silencioso).

2. `src/hefesto/integrations/window_detect.py` — factory `detect_window_backend()`:
   - `WAYLAND_DISPLAY` + `DISPLAY` → `XlibBackend` (XWayland, preferido).
   - `WAYLAND_DISPLAY` sem `DISPLAY` → `WaylandPortalBackend`.
   - `DISPLAY` sem `WAYLAND_DISPLAY` → `XlibBackend`.
   - Nenhum → `NullBackend` (loga `autoswitch_compositor_unsupported`).

3. `xlib_window.py` convertido em shim de compatibilidade: re-exporta
   `get_active_window_info` de `window_detect`. Código legado não precisa de
   alteração.

### Camada 2 — Portal XDG (implementado nesta sprint)

`WaylandPortalBackend` tenta (em ordem):
1. `jeepney` (puro Python, sem dep nativa compilada).
2. `dbus-fast` (assíncrono, mais completo).

Se nenhuma biblioteca estiver disponível, retorna `None` sem erro. A dependência
é **opcional** — não incluída em `pyproject.toml` como dep obrigatória.

### Camada 3 — Applet nativo COSMIC (fora de escopo desta sprint)

Crate Rust `cosmic-applet-hefesto` para integração nativa com o painel COSMIC.
Sprint futura em V1.2.

## Consequencias

**Positivo:**
- Autoswitch de perfil funciona em XWayland (caso mais comum de COSMIC hoje).
- Degradação silenciosa e documentada em Wayland puro sem portal disponível.
- API legada (`get_active_window_info` dict) preservada — zero breaking changes.
- Backends são isolados e testáveis via monkeypatch de `os.environ`.

**Negativo:**
- `WaylandPortalBackend` depende de libs opcionais (`jeepney`/`dbus-fast`).
  Em ambientes minimais sem nenhuma, retorna `None` (mesmo comportamento do
  fallback anterior).
- Portal `GetActiveWindow` não existe em compositors Wayland antigos (GNOME < 46,
  Sway, Hyprland). Nesses ambientes o backend Null é ativado.
- Não testado diretamente no hardware COSMIC (Pop!_OS 24.04 real) nesta sprint —
  validação manual é responsabilidade do mantenedor antes de marcar Camada 2 como
  "produção ready".

## Alternativas consideradas

- **Manter fallback silencioso** (comportamento anterior de ADR-007): descartado
  porque COSMIC em produção invalida a hipótese de "Wayland é futuro distante".
- **Forçar XWayland sempre via `DISPLAY=:0`**: descartado porque invade o ambiente
  do usuário e exige dependência de um servidor X em paralelo.
- **Substituir toda a stack por `pydbus`**: descartado pela dep nativa (libdbus-1);
  `jeepney` puro Python é mais portável.
