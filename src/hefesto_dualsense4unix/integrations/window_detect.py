"""Detecção de janela ativa com seleção automática de backend.

`detect_window_backend()` escolhe o backend adequado conforme as variáveis
de ambiente do compositor:

  WAYLAND_DISPLAY + DISPLAY  → _XlibComCosmicBackend (XWayland + Wayland nativo)
  WAYLAND_DISPLAY sem DISPLAY → _WaylandCascadeBackend (cosmic → portal → wlrctl)
  DISPLAY sem WAYLAND_DISPLAY → XlibBackend
  Nenhum                      → NullBackend    (loga autoswitch_compositor_unsupported)

Função `get_active_window_info()` mantém compatibilidade com a API legada de
`xlib_window.py`: retorna `dict[str, Any]` com chaves `wm_class`, `wm_name`,
`pid`, `exe_basename`.

BUG-COSMIC-WLR-BACKEND-REGRESSION-01 (v3.1.0): re-introduz o cascade
portal → wlrctl perdido no rebrand Hefesto → Hefesto - Dualsense4Unix.
O portal XDG é canônico onde existe (GNOME 46+); o `WlrctlBackend` cobre o
bloco wlroots (Sway, Hyprland, niri, river) via
`wlr-foreign-toplevel-management-unstable-v1`.

FATO SUBSTITUÍDO — 02/09/2026, e ele estava escrito aqui e no `wlr_toplevel.py`:
este cabeçalho dizia que o `wlrctl` *"funciona em COSMIC"*, e mais abaixo que a
cascata Wayland *"funciona no COSMIC via wlrctl"*. **É falso, e a medição é
direta:** dos 58 globais que o cosmic-comp 0.1 desta máquina publica, o
`zwlr_foreign_toplevel_manager_v1` **não está entre eles** — por isso o wlrctl
instalado responde *"Foreign Toplevel Management interface not found"*. O que
está entre eles é o `zcosmic_toplevel_info_v1` (versão 3), e é dele que fala o
`CosmicToplevelBackend`, primeiro da cascata.

JANELA-WAYLAND-CEGA-01 (02/09/2026): em XWayland, o backend deixa de ser só o
`xlib`. Ele continua PREFERIDO — é o único que resolve `exe_basename` —, mas
quando ele não enxerga (um app Wayland nativo em foco: `sem_foco_x`), a leitura
passa para o `cosmic`, em vez de virar `unknown`. Medido na sessão dela: com o
Chrome/Wayland em foco, o produto lia `wm_class="unknown"` e o
`zcosmic_toplevel_info_v1` lia `google-chrome`, no mesmo instante.
"""
from __future__ import annotations

import os
from typing import Any

from hefesto_dualsense4unix.integrations.window_backends.base import WindowBackend, WindowInfo
from hefesto_dualsense4unix.integrations.window_backends.null import NullBackend
from hefesto_dualsense4unix.integrations.window_backends.xlib import XlibBackend
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# AUTOSWITCH-FLOOD-FIX-01: once-guard p/ não floodar o journal com
# 'autoswitch_compositor_unsupported' quando não há display (ver detect_window_backend).
_unsupported_warned: bool = False

#: JANELA-CEGA-01 (28/07): motivos de leitura cega que nascem AQUI (os do
#: backend X11 moram em `window_backends/xlib.py`).
#: - cascata: portal e wlrctl desistiram no mesmo tick;
#: - janela sem classe: o backend DEVOLVEU janela, mas sem `wm_class` — a
#:   leitura não é útil e o motivo não pode virar "não sei por quê".
#: - backend sem motivo: devolveu None e não expõe `last_failure_reason`
#:   (dublê de teste, backend de terceiro) — "não sei por quê" DITO, que já é
#:   melhor do que um None mudo.
MOTIVO_CASCATA_SEM_LEITURA = "cascata_wayland_sem_leitura"
MOTIVO_JANELA_SEM_CLASSE = "janela_sem_classe"
MOTIVO_BACKEND_SEM_MOTIVO = "backend_sem_motivo"

#: PROCESSO-CEGO-01 (12/08/2026): quais backends entregam `exe_basename` — o
#: ÚNICO campo que o matcher `process_name` consulta
#: (`MatchCriteria.matches`, ramo `process_name`).
#:
#: Isto não é opinião sobre ambiente: é o que os arquivos DIZEM, e o teste
#: `test_o_nome_do_processo_que_nao_casa` confere linha a linha contra eles.
#: Só `window_backends/xlib.py` resolve o executável, em
#: `_exe_basename_from_pid` (`os.readlink("/proc/<pid>/exe")`).
#: `wayland_portal.py`, `wlr_toplevel.py` e `cosmic_toplevel.py` constroem o
#: `WindowInfo` com `exe_basename=""` LITERAL — o portal até recebe o `pid`, e
#: mesmo assim não resolve o executável; o `zcosmic_toplevel_info_v1` não manda
#: PID nenhum, nem na versão 3 —, e `null.py` não devolve janela nenhuma.
BACKENDS_QUE_VEEM_O_PROCESSO = frozenset({"xlib"})
BACKENDS_CEGOS_AO_PROCESSO = frozenset({"portal", "wlrctl", "cosmic", "null"})


def backend_ve_nome_do_processo(backend: str | None) -> bool | None:
    """O backend entrega ``exe_basename``? ``None`` = **não dá para saber**.

    PROCESSO-CEGO-01. A pergunta existe porque o preço de errar é alto e
    silencioso: `MatchCriteria` é um **E** entre os campos preenchidos, então
    um perfil com `process_name` num backend cego não deixa de casar só por
    aquele campo — ele **não entra nunca**, nem com a `window_class` certa.
    Foi a causa medida de cinco perfis dela (`FPS`, `Ação`, `Aventura`,
    `Corrida`, `Esportes`) jamais aparecerem no autoswitch em 30 dias de
    journal (PERFIL-MUDO-01, 10/08/2026).

    Os três valores, e o ``None`` é tão resposta quanto os outros dois:

    * ``True``  — backend que resolve o executável (hoje só o ``xlib``);
    * ``False`` — backend que devolve ``exe_basename`` vazio por construção;
    * ``None``  — nome vazio/ausente (o detector ainda não foi semeado, ou o
      daemon vivo é mais velho que esta versão), ou um nome que este módulo
      não conhece (backend de terceiro, dublê de teste).

    O ``None`` é o que impede a tela de inventar defeito: *"não sei"* e *"não
    casa"* mandam caçar em lugares opostos, e nesta casa "o daemon vivo é mais
    velho que o código" é rotina.

    Nome desconhecido responde ``None`` de propósito, e não ``False``: um
    backend que apareça depois desta linha ser escrita não pode herdar uma
    acusação que ninguém mediu sobre ele.
    """
    if not isinstance(backend, str) or not backend:
        return None
    if backend in BACKENDS_QUE_VEEM_O_PROCESSO:
        return True
    if backend in BACKENDS_CEGOS_AO_PROCESSO:
        return False
    return None


class _WaylandCascadeBackend:
    """Cascade: cosmic → portal XDG → wlrctl → None.

    **A ordem mudou em 02/09/2026, e a razão é medida.** O portal era o
    primeiro por ser o caminho oficial; na máquina dela ele não tem
    `GetActiveWindow` e o wlrctl não acha o protocolo do wlroots, então a
    cascata inteira era cega numa sessão COSMIC. O `CosmicToplevelBackend`
    passa à frente porque é o que responde ali — e onde ele não serve, ele se
    desliga sozinho depois de UM aperto de mão: num compositor que não publica
    `zcosmic_toplevel_info_v1`, o custo de tê-lo primeiro é uma ida ao soquete,
    uma vez na vida do processo.

    Esta classe vive em `window_detect.py` em vez de `window_backends/`
    porque é puramente composicional (escolhe entre backends existentes).
    """

    def __init__(self) -> None:
        from hefesto_dualsense4unix.integrations.window_backends.cosmic_toplevel import (
            CosmicToplevelBackend,
        )
        from hefesto_dualsense4unix.integrations.window_backends.wayland_portal import (
            WaylandPortalBackend,
        )
        from hefesto_dualsense4unix.integrations.window_backends.wlr_toplevel import (
            WlrctlBackend,
        )

        self._cosmic = CosmicToplevelBackend()
        self._portal = WaylandPortalBackend()
        self._wlrctl = WlrctlBackend()
        self._fallback_announced: bool = False
        # JANELA-CEGA-01: motivo da última leitura cega da cascata. Um só,
        # porque a cascata só falha de um jeito — os backends já desistiram;
        # qual deles desistiu está em `backend_name`.
        self.last_failure_reason: str | None = None
        # FEAT-WINDOW-DETECT-DIAG-01: fonte da última leitura ÚTIL da cascata
        # ("cosmic" | "portal" | "wlrctl" | None). Alimenta `backend_name`.
        self._last_source: str | None = None

    @property
    def backend_name(self) -> str:
        """Backend ativo na cascata: "cosmic" | "portal" | "wlrctl" | "null".

        FEAT-WINDOW-DETECT-DIAG-01. Dinâmico de propósito: a cascata pode
        migrar em runtime (o cosmic descobre que o compositor não é COSMIC; o
        portal desiste após o threshold de falhas; o wlrctl descobre que o
        compositor não expõe o protocolo do wlroots). Prioridade: fonte da
        última leitura útil, se ainda viável; senão o primeiro backend da fila
        que ainda se declara disponível; senão "null" (cascata cega — o
        autoswitch fica no fallback).
        """
        if self._last_source == "cosmic" and self._cosmic.available:
            return "cosmic"
        if self._last_source == "portal" and not self._portal.unsupported:
            return "portal"
        if self._last_source == "wlrctl" and self._wlrctl.available:
            return "wlrctl"
        if self._cosmic.available:
            return "cosmic"
        if not self._portal.unsupported:
            return "portal"
        if self._wlrctl.available:
            return "wlrctl"
        return "null"

    def get_active_window_info(self) -> WindowInfo | None:
        info = self._cosmic.get_active_window_info()
        if info is not None:
            self._last_source = "cosmic"
            self.last_failure_reason = None
            return info

        info = self._portal.get_active_window_info()
        if info is not None:
            self._last_source = "portal"
            self.last_failure_reason = None
            return info

        info = self._wlrctl.get_active_window_info()
        if info is not None:
            self._last_source = "wlrctl"
            self.last_failure_reason = None
            if not self._fallback_announced:
                logger.info(
                    "wayland_backend_fallback_wlrctl",
                    hint=(
                        "portal XDG não respondeu; wlrctl ativo "
                        "(wlr-foreign-toplevel-management)."
                    ),
                )
                self._fallback_announced = True
            return info

        self.last_failure_reason = MOTIVO_CASCATA_SEM_LEITURA
        return None


class _XlibComCosmicBackend:
    """XWayland: o `xlib` na frente, e o Wayland nativo atrás dele.

    JANELA-WAYLAND-CEGA-01 (02/09/2026). Numa sessão COSMIC o `DISPLAY` existe
    (XWayland), então `detect_window_backend` escolhia `xlib` e pronto — a
    cascata Wayland, com o único backend que enxerga app nativo, ficava do lado
    de fora e nunca era tentada. O resultado, medido ao vivo na sessão dela às
    23h02 de 02/09: com o Chrome/Wayland em foco, o produto lia
    `wm_class="unknown"` (motivo `sem_foco_x`) enquanto o
    `zcosmic_toplevel_info_v1` lia `google-chrome` no mesmo instante. Perfil
    por jogo não casa com `unknown`.

    **O xlib continua PREFERIDO, e não é hierarquia: é o que ele entrega a
    mais.** Só ele resolve o `exe_basename` (`BACKENDS_QUE_VEEM_O_PROCESSO`) e
    só ele traz o PID; um jogo Proton lido pelo `cosmic` perderia o
    `process_name` do perfil. Então o segundo backend só é consultado quando o
    primeiro NÃO devolveu janela — o caminho de quem joga por XWayland fica
    byte-por-byte o de antes.

    **Isto não substitui o resgate do `WindowReaderDiag`, e sim o torna
    desnecessário nesta configuração.** `maybe_recover` trocava o backend de
    uma vez por todas quando o XWayland morria; aqui a queda é por leitura, e
    volta sozinha se o XWayland voltar.

    **O CUSTO, dito em vez de escondido.** O `AutoSwitcher` lê a 2 Hz, e agora
    toda leitura cega do X consulta a cascata. No COSMIC isso é barato — o
    `CosmicToplevelBackend` mantém a conexão aberta e uma leitura sem novidade
    é um `recv` que devolve `EAGAIN`. Em compositor **wlroots com XWayland**,
    porém, quem responde é o `WlrctlBackend`, que gasta um `subprocess` por
    leitura: com um app Wayland nativo em foco, isso vira duas execuções de
    `wlrctl` por segundo. Não é custo novo em espécie — é exatamente o que a
    cascata já fazia nesses compositors em sessão Wayland pura, desde a
    v3.1.0 —, mas é custo novo de LUGAR, e quem for medir consumo de CPU do
    daemon numa dessas máquinas precisa saber onde olhar.
    """

    def __init__(self, xlib: WindowBackend, wayland: WindowBackend) -> None:
        self._xlib = xlib
        self._wayland = wayland
        self.last_failure_reason: str | None = None
        self._ultima_fonte: str | None = None
        self._anunciado: bool = False

    @property
    def backend_name(self) -> str:
        """De onde veio a última leitura ÚTIL — "xlib" ou o nome da cascata.

        Enquanto ninguém leu nada, responde "xlib": é o backend que vai ser
        tentado primeiro, e mentir "cosmic" antes da primeira leitura faria a
        tela prometer um nome de processo que este caminho nunca dá
        (`backend_ve_nome_do_processo` lê exatamente este campo).
        """
        if self._ultima_fonte == "wayland":
            nome = getattr(self._wayland, "backend_name", None)
            if isinstance(nome, str) and nome:
                return nome
            return "null"
        return getattr(self._xlib, "backend_name", "xlib")

    @property
    def xlib(self) -> WindowBackend:
        """O backend X11 de dentro — o `WindowReaderDiag` pergunta a saúde a ele."""
        return self._xlib

    def conexao_provada(self) -> bool | None:
        """Delega ao `xlib`: é dele que a pergunta fala (T-01, ONDA0-Z7)."""
        fn = getattr(self._xlib, "conexao_provada", None)
        return fn() if callable(fn) else None

    def get_active_window_info(self) -> WindowInfo | None:
        info = self._xlib.get_active_window_info()
        if info is not None:
            self._ultima_fonte = "xlib"
            self.last_failure_reason = None
            return info

        motivo_do_x = getattr(self._xlib, "last_failure_reason", None)
        info = self._wayland.get_active_window_info()
        if info is not None:
            self._ultima_fonte = "wayland"
            self.last_failure_reason = None
            if not self._anunciado:
                logger.info(
                    "janela_lida_pelo_wayland_nativo",
                    motivo_do_x=motivo_do_x,
                    hint=(
                        "o X não enxergou a janela em foco (app Wayland "
                        "nativo) e a leitura veio do compositor; o nome do "
                        "processo não vem por este caminho."
                    ),
                )
                self._anunciado = True
            return info

        self._ultima_fonte = None
        # JANELA-CEGA-01: os dois calaram. O motivo do X é o mais informativo
        # (ele distingue "XWayland morto" de "app nativo em foco"); o da
        # cascata entra quando o X não soube dizer.
        self.last_failure_reason = (
            motivo_do_x
            or getattr(self._wayland, "last_failure_reason", None)
            or MOTIVO_CASCATA_SEM_LEITURA
        )
        return None


def detect_window_backend() -> WindowBackend:
    """Detecta e retorna o backend mais adequado para o ambiente atual.

    Lógica de seleção:
    - XWayland (ambas variáveis presentes): `_XlibComCosmicBackend` — o xlib na
      frente (é quem vê o processo), a cascata Wayland atrás, para o app nativo
      que o X não enxerga (JANELA-WAYLAND-CEGA-01).
    - Wayland puro (apenas WAYLAND_DISPLAY): cascade cosmic → portal → wlrctl.
    - X11 puro (apenas DISPLAY): XlibBackend — não há Wayland atrás para cair.
    - Sem display: NullBackend (com log de advertência).
    """
    has_wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    has_x11 = bool(os.environ.get("DISPLAY"))

    if has_x11 and has_wayland:
        logger.debug("window_backend_selected", backend="xlib+wayland", xwayland=True)
        return _XlibComCosmicBackend(XlibBackend(), _WaylandCascadeBackend())

    if has_x11:
        logger.debug("window_backend_selected", backend="xlib", xwayland=False)
        return XlibBackend()

    if has_wayland:
        logger.debug("window_backend_selected", backend="wayland_cascade")
        return _WaylandCascadeBackend()

    # AUTOSWITCH-FLOOD-FIX-01: once-guard. Sem display, esta função era chamada
    # a cada tick do AutoSwitcher (0,5s) via get_active_window_info legado e
    # logava WARNING toda vez — 1800+ linhas em 10min no journal. Agora o
    # subsystem usa build_window_reader() (backend instanciado 1x), mas o
    # guard protege qualquer caller repetido (CLI/doctor) de floodar: avisa
    # uma vez, depois rebaixa para debug.
    global _unsupported_warned
    if not _unsupported_warned:
        logger.warning("autoswitch_compositor_unsupported")
        _unsupported_warned = True
    else:
        logger.debug("autoswitch_compositor_unsupported")
    return NullBackend()


_UNKNOWN_WINDOW: dict[str, Any] = {
    "wm_class": "unknown",
    "wm_name": "",
    "pid": 0,
    "exe_basename": "",
}


def get_active_window_info() -> dict[str, Any]:
    """Retorna dict com informações da janela ativa.

    Mantém compatibilidade com a assinatura original de
    `hefesto_dualsense4unix.integrations.xlib_window.get_active_window_info`.
    """
    backend = detect_window_backend()
    info: WindowInfo | None = backend.get_active_window_info()
    if info is None:
        return dict(_UNKNOWN_WINDOW)
    return info.as_dict()


class WindowReaderDiag:
    """Leitor de janela com diagnóstico de primeira classe.

    FEAT-WINDOW-DETECT-DIAG-01: além de callable (API legada — retorna o dict
    wm_class/wm_name/pid/exe_basename, com `_UNKNOWN_WINDOW` quando o backend
    não acha janela), expõe metadados para o autoswitch gravar no StateStore:

      backend_name       -- backend efetivamente ativo ("xlib" | "portal" |
                            "wlrctl" | "null"); dinâmico na cascata Wayland.
      last_read_useful   -- a última leitura retornou wm_class útil
                            (!= "unknown" e não-vazia)?
      useful_reads       -- total de leituras úteis desde a construção.
      last_useful_class  -- última wm_class útil vista (permite capturar o
                            wm_class de um jogo sem ler o journal).
      last_reason        -- JANELA-CEGA-01: POR QUE a última leitura não foi
                            útil ("sem_conexao_x", "sem_foco_x",
                            "foco_discorda_do_net_active", ...); None quando a
                            leitura foi útil. Sem ele, as seis causas de
                            cegueira do backend X11 colapsavam num `None` só
                            e ninguém conseguia distinguir "app Wayland
                            nativo em foco" (normal) de "o XWayland caiu"
                            (grave).
    """

    def __init__(self, backend: WindowBackend) -> None:
        self._backend = backend
        self.last_read_useful: bool = False
        self.useful_reads: int = 0
        self.last_useful_class: str | None = None
        self.last_reason: str | None = None

    @property
    def backend_name(self) -> str:
        """Nome do backend ativo; cai no nome da classe se não declarado."""
        name = getattr(self._backend, "backend_name", None)
        if isinstance(name, str) and name:
            return name
        return type(self._backend).__name__.lower()

    def __call__(self) -> dict[str, Any]:
        info: WindowInfo | None = self._backend.get_active_window_info()
        result: dict[str, Any] = (
            dict(_UNKNOWN_WINDOW) if info is None else info.as_dict()
        )
        wm_class = str(result.get("wm_class") or "")
        self.last_read_useful = wm_class not in ("", "unknown")
        if self.last_read_useful:
            self.useful_reads += 1
            self.last_useful_class = wm_class
            self.last_reason = None
        else:
            self.last_reason = self._motivo_da_cegueira(info)
        return result

    def _motivo_da_cegueira(self, info: WindowInfo | None) -> str:
        """Motivo desta leitura não-útil (JANELA-CEGA-01).

        Vem do backend quando ele soube dizer (`last_failure_reason`); backend
        que devolveu janela SEM `wm_class` não falhou — a janela é que não se
        identifica, e isso tem nome próprio. `getattr` porque o `Protocol`
        `WindowBackend` continua exigindo só `get_active_window_info`: backend
        de terceiro (ou dublê de teste) segue válido sem o campo, e aí o motivo
        honesto é o genérico.
        """
        motivo = getattr(self._backend, "last_failure_reason", None)
        if isinstance(motivo, str) and motivo:
            return motivo
        if info is not None:
            return MOTIVO_JANELA_SEM_CLASSE
        return MOTIVO_BACKEND_SEM_MOTIVO

    def conexao_provada(self) -> bool | None:
        """Delega a `XlibBackend.conexao_provada` (T-01, ONDA0-Z7).

        Backends sem o conceito de conexão (portal/wlrctl/null/dublê de
        teste) devolvem `None` — "não sei provar" é honesto, e o chamador
        (`autoswitch._build_diag_window_reader`) já trata `None` como
        "ainda sem prova de saúde".
        """
        fn = getattr(self._backend, "conexao_provada", None)
        return fn() if callable(fn) else None

    def _xwayland_morto_com_wayland_vivo(self) -> bool:
        """O backend é `xlib` PURO, a conexão está PROVADA morta, e há Wayland?

        D-TROCA-DE-PERFIL-CEGA (25/08/2026). As três condições juntas, e só
        elas, descrevem a máquina dela na medição de 23/08 às 22h21: 60
        `x11_connect_failed` em 30 min, `err=Can't connect to display :1`,
        sessão COSMIC/Wayland. O produto ficava preso a um backend cego tendo
        a cascata Wayland ao lado, nunca tentada.

        **O QUE MUDOU EM 02/09/2026, e por que este ramo quase não roda mais:**
        com `DISPLAY` E `WAYLAND_DISPLAY` no ambiente,
        `detect_window_backend()` já devolve o `_XlibComCosmicBackend`, que
        tenta a cascata Wayland a CADA leitura em que o X não enxergou —
        inclusive quando ele não enxergou por estar morto. O resgate deixa de
        ser necessário nessa configuração, e deixa de disparar: o `isinstance`
        abaixo é `XlibBackend`, não o composto. Isso é escolha, não descuido —
        a queda por leitura é reversível (o XWayland volta e o `exe_basename`
        volta com ele) e o resgate era de mão única dentro do episódio.

        O ramo continua vivo para o `xlib` PURO, que é o que
        `detect_window_backend()` devolve quando só há `DISPLAY`: aí um
        `WAYLAND_DISPLAY` que apareça DEPOIS (o `_ensure_display_env()`
        importa o ambiente do systemd `--user` no meio da vida do daemon) é
        exatamente o caso que este método existe para pegar.

        `conexao_provada() is False` é PROVA, não presunção: só devolve False
        depois de uma tentativa de conexão real que o servidor recusou
        (`None` = ainda não tentou; `True` = conectado agora). É a mesma régua
        que a T-01 da ONDA0-Z7 usou para semear `window_detect_healthy`.
        """
        if not isinstance(self._backend, XlibBackend):
            return False
        if not os.environ.get("WAYLAND_DISPLAY"):
            return False
        return self._backend.conexao_provada() is False

    def precisa_de_resgate(self) -> bool:
        """O backend atual está cego de um jeito que a re-detecção cura?

        Dois casos, e só dois — quem os conserta é `maybe_recover`:

        * **backend Null** (AUTOSWITCH-HEAL-01): o daemon nasceu antes do env
          gráfico e o env pode ter aparecido desde então;
        * **xlib com a conexão provada morta numa sessão Wayland**
          (D-TROCA-DE-PERFIL-CEGA): existe outro backend viável e ninguém o
          tentou.

        Existe separado de `maybe_recover` porque o chamador precisa saber se
        vale gastar o `systemctl --user show-environment` do
        `_ensure_display_env()` ANTES de tentar — o poll roda a 2 Hz.
        """
        if isinstance(self._backend, NullBackend):
            return True
        return self._xwayland_morto_com_wayland_vivo()

    def maybe_recover(self) -> bool:
        """Troca o backend em-place quando o atual está cego e há alternativa.

        AUTOSWITCH-HEAL-01 (22/07): no login o daemon pode nascer ANTES de o
        compositor exportar WAYLAND_DISPLAY/DISPLAY para o systemd --user —
        o backend era fixado em Null UMA vez e o perfil-por-jogo ficava morto
        a sessão inteira (medido: `window_detect_diag_seeded backend=null` no
        boot com o env presente minutos depois). O poll chama este método
        (rate-limitado no chamador) DEPOIS de re-importar o env; quando a
        re-detecção sai do Null, o backend é trocado em-place e o autoswitch
        volta à vida sem restart. Retorna True quando recuperou.

        D-TROCA-DE-PERFIL-CEGA (25/08/2026): o segundo caso é o XWayland
        MORTO numa sessão Wayland (ver `_xwayland_morto_com_wayland_vivo`).
        Aqui NÃO se chama `detect_window_backend()` — ela devolveria `xlib` de
        novo se o env ainda não tiver o `WAYLAND_DISPLAY` que este método
        acabou de ver; o resgate monta o composto direto.

        **A troca DEIXOU de ser de mão única — 02/09/2026.** Ela trocava o
        `xlib` pela cascata Wayland e pronto: quem casava perfil por
        `process_name` perdia o casamento até o próximo start do daemon, mesmo
        que o XWayland ressuscitasse no minuto seguinte. Agora o resgate
        monta o `_XlibComCosmicBackend` com o MESMO `xlib` dentro — ele volta a
        ser o preferido no instante em que voltar a responder, e o
        `exe_basename` volta junto. O que se perde enquanto o X está morto é o
        mesmo de antes (a cascata é cega ao processo), e o
        `window_detect_backend` publicado no `state_full` continua dizendo por
        onde a leitura veio — é o que `backend_ve_nome_do_processo` lê para a
        tela.
        """
        if isinstance(self._backend, NullBackend):
            novo = detect_window_backend()
            if isinstance(novo, NullBackend):
                return False
            self._backend = novo
            return True
        if self._xwayland_morto_com_wayland_vivo():
            self._backend = _XlibComCosmicBackend(self._backend, _WaylandCascadeBackend())
            logger.warning(
                "window_backend_xwayland_morto_resgate_wayland",
                hint=(
                    "o servidor X recusou conexão e a sessão é Wayland; "
                    "a detecção de janela passa a cair para a cascata "
                    "cosmic/portal/wlrctl a cada leitura que o X perder. O "
                    "nome do processo não vem por esse caminho (perfis que "
                    "casam por process_name não entram enquanto durar); "
                    "wm_class e título continuam, e o xlib volta a ser o "
                    "preferido assim que voltar a responder."
                ),
            )
            return True
        return False


def build_window_reader() -> WindowReaderDiag:
    """Cria um leitor de janela com o backend instanciado UMA vez.

    AUTOSWITCH-FLOOD-FIX-01. Diferente de `get_active_window_info()` (stateless,
    recria o backend a cada chamada — adequado p/ CLI/doctor pontual), este
    mantém o backend vivo para o poll do AutoSwitcher (2Hz). Ganhos:
    - não loga `autoswitch_compositor_unsupported` por tick (flood no journal);
    - preserva o estado anti-flood/anti-D-Bus dos backends
      (`_consecutive_failures`, `_unsupported_warned`, cache do `which`,
      `_fallback_announced`) em vez de resetá-lo a cada 0,5s;
    - evita gastar o timeout de 2s do portal jeepney a cada tick numa sessão
      Wayland real onde o portal não tem GetActiveWindow.

    FEAT-WINDOW-DETECT-DIAG-01: retorna `WindowReaderDiag` — callable
    retrocompatível com a API legada (mesmo dict wm_class/wm_name/pid/
    exe_basename) que também expõe `backend_name`/`last_read_useful`/
    `last_useful_class` para diagnóstico. O backend é fixado no momento da
    chamada — chame após o ambiente gráfico estar disponível (o subsystem
    importa o env antes).
    """
    return WindowReaderDiag(detect_window_backend())


__all__ = [
    "BACKENDS_CEGOS_AO_PROCESSO",
    "BACKENDS_QUE_VEEM_O_PROCESSO",
    "MOTIVO_BACKEND_SEM_MOTIVO",
    "MOTIVO_CASCATA_SEM_LEITURA",
    "MOTIVO_JANELA_SEM_CLASSE",
    "WindowReaderDiag",
    "backend_ve_nome_do_processo",
    "build_window_reader",
    "detect_window_backend",
    "get_active_window_info",
]
