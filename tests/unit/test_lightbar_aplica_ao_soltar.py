"""BOTÃO-QUE-NÃO-MENTE-01 entrega 1 — a cor acende ao SOLTAR, não no 2o clique.

Defeito medido na sprint: escolher uma cor não acendia nada. O handler do
seletor gravava só no rascunho, e o hardware só via a cor quando ela achava o
botão "Aplicar no controle", trinta linhas de layout abaixo. Nenhum dos três
controles envolvidos tinha tooltip. Ela clicava, o controle não mudava, e
concluía que a janela era maquete — "clico e não acontece nada".

Adiar a escrita é decisão CERTA e continua valendo: aplicar a cada pixel de
arraste saturaria a fila do rádio (por Bluetooth cada escrita disputa a mesma
fila dos relatórios de input, vezes quatro controles). O defeito era o
adiamento SILENCIOSO. A cura encurta a janela do adiamento para um gesto.

Os dois lados que este arquivo prende, porque quebrar qualquer um devolve uma
queixa dela:

1. **soltar escreve** — um gesto, UMA escrita no controle;
2. **arrastar não escreve** — nenhuma escrita por pixel; o movimento só mexe
   no rascunho e na prévia.

Como este teste morde: a fiação do soltar mora em ``install_lightbar_tab``
(``_fiar_aplicar_ao_soltar``), e os testes disparam os sinais REGISTRADOS ali,
nunca chamando o handler pelo nome. Arrancar o ``connect`` do
``button-release-event`` (ou o do ``color-set``) faz o disparo cair no vazio e
a contagem de escritas ir a zero — reprova.

GUI: precisa de ``gi`` (padrão de ``test_lightbar_todos_por_mac_r14.py``).
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("lightbar aplica ao soltar")

from typing import Any

import pytest

gi = pytest.importorskip("gi")

# BUG-TEST-GDK-VERSION-PIN-01: pina Gdk/Gtk 3.0 ANTES de importar módulos da
# GUI — sem isso o gi pode carregar Gdk 4.0 e envenenar o processo inteiro.
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.actions import lightbar_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile


#: MACs forjados (faixa aa:bb:cc — teste-guarda de anonimato).
UNIQ_1 = "aabbcc000001"
UNIQ_2 = "aabbcc000002"

ROXO = (129, 61, 156)
AZUL = (0, 0, 255)


def _gdk_rgba_ok() -> bool:
    """A CI headless de release tem um Gdk parcial sem RGBA.

    ``install_lightbar_tab`` constrói um ``Gdk.RGBA`` para semear a cor inicial
    quando o seletor existe — mesmo skip de ``test_lightbar_todos_por_mac_r14``.
    Os testes de BRILHO não precisam do seletor e rodam em qualquer ambiente.
    """
    try:
        from gi.repository import Gdk

        return hasattr(Gdk, "RGBA")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Widgets falsos que GRAVAM as conexões (é aqui que o teste morde)
# ---------------------------------------------------------------------------


class _WidgetEspiao:
    """Widget mínimo que guarda quem se conectou a cada sinal.

    ``disparar`` faz o que o GTK faria: chama os handlers registrados NAQUELE
    sinal, na ordem de conexão. Sinal sem handler é disparo no vazio — que é
    exatamente o que acontece quando a fiação é arrancada.
    """

    def __init__(self) -> None:
        self.handlers: dict[str, list[Any]] = {}

    def connect(self, sinal: str, handler: Any, *_a: Any, **_kw: Any) -> int:
        self.handlers.setdefault(sinal, []).append(handler)
        return len(self.handlers[sinal])

    def disparar(self, sinal: str, *args: Any) -> None:
        for handler in list(self.handlers.get(sinal, [])):
            handler(*args)

    def queue_draw(self) -> None:
        return None


class _RGBAFalso:
    def __init__(self, r: float, g: float, b: float) -> None:
        self.red = r
        self.green = g
        self.blue = b
        self.alpha = 1.0


class _SeletorDeCor(_WidgetEspiao):
    def __init__(self, rgb: tuple[int, int, int] = ROXO) -> None:
        super().__init__()
        self._rgba = _RGBAFalso(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)

    def get_rgba(self) -> _RGBAFalso:
        return self._rgba

    def set_rgba(self, rgba: Any) -> None:
        self._rgba = _RGBAFalso(rgba.red, rgba.green, rgba.blue)

    def escolher(self, rgb: tuple[int, int, int]) -> None:
        """O que o diálogo de cor faz antes de emitir ``color-set``."""
        self._rgba = _RGBAFalso(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)


class _ControleDeslizante(_WidgetEspiao):
    def __init__(self, valor: float = 100.0) -> None:
        super().__init__()
        self.valor = float(valor)

    def get_value(self) -> float:
        return self.valor


class _Host(LightbarActionsMixin):
    """Host mínimo: rascunho + mapa de conectados + widgets espiões."""

    def __init__(
        self,
        draft: draft_mod.DraftConfig,
        widgets: dict[str, Any],
        uniq: str | None = None,
        conectados: dict[int, str | None] | None = None,
    ) -> None:
        self.draft = draft
        self._edit_target_uniq = uniq
        self._target_uniq_by_index = conectados if conectados is not None else {}
        self._widgets = widgets
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


def _draft(auto: bool = True) -> draft_mod.DraftConfig:
    perfil = Profile(
        name="vitoria",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(
            lightbar=ROXO,
            player_leds=[True, False, False, False, False],
            lightbar_brightness=1.0,  # 0..1 no perfil; vira 0..100 no rascunho
            auto_player_colors=auto,
        ),
    )
    return draft_mod.DraftConfig.from_profile(perfil)


class _EspiaoDeEscrita:
    """Conta as escritas que chegariam ao controle."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[Any, Any, str | None]] = []
        self.resposta = True

    def led_set(
        self,
        rgb: tuple[int, int, int],
        brightness: float | None = None,
        uniq: str | None = None,
    ) -> bool:
        self.chamadas.append((rgb, brightness, uniq))
        return self.resposta


@pytest.fixture
def escritas(monkeypatch: pytest.MonkeyPatch) -> _EspiaoDeEscrita:
    """Sela TODA saída para o hardware — nenhum teste toca no daemon real."""
    espiao = _EspiaoDeEscrita()
    monkeypatch.setattr(lightbar_actions, "led_set", espiao.led_set)
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "apply_draft_detalhado",
        lambda *_a, **_kw: pytest.fail(
            "com controles conectados a rota é led.set por MAC (R-14)"
        ),
    )
    return espiao


def _host_com_brilho(
    uniq: str | None = None,
    conectados: dict[int, str | None] | None = None,
    valor: float = 100.0,
) -> tuple[_Host, _ControleDeslizante]:
    """Host com o controle deslizante de brilho JÁ instalado (fiação real)."""
    escala = _ControleDeslizante(valor)
    host = _Host(
        _draft(),
        {"lightbar_brightness_scale": escala, "lightbar_preview": _WidgetEspiao()},
        uniq=uniq,
        conectados=conectados if conectados is not None else {1: UNIQ_1},
    )
    host.install_lightbar_tab()
    # A cor QUE ESTÁ NA TELA — no app quem a semeia é o
    # `_refresh_lightbar_from_draft`, que exige a aba inteira montada. Cor e
    # brilho formam um campo só no backend: soltar o brilho manda os dois.
    host._current_rgb = ROXO
    return host, escala


def _arrastar(host: _Host, escala: _ControleDeslizante, de: int, ate: int) -> None:
    """Arrasto contínuo: um ``value-changed`` por pixel, como o GTK emite."""
    passo = -1 if ate < de else 1
    for valor in range(de, ate + passo, passo):
        escala.valor = float(valor)
        host.on_lightbar_brightness_changed(escala)


# ---------------------------------------------------------------------------
# Brilho: arrastar não escreve; soltar escreve UMA vez
# ---------------------------------------------------------------------------


def test_arrastar_o_brilho_nao_escreve_um_pedido_por_pixel(
    escritas: _EspiaoDeEscrita,
) -> None:
    """O motivo de existir o adiamento: 41 pixels de arraste, zero escritas."""
    host, escala = _host_com_brilho()
    _arrastar(host, escala, 100, 60)

    assert escritas.chamadas == [], (
        "arrastar escreveu no controle — é a saturação de fila que o "
        "adiamento existe para evitar"
    )
    # O movimento continua vivo onde deve: rascunho e prévia.
    assert host.draft.leds.lightbar_brightness == 60


def test_soltar_o_brilho_escreve_uma_vez_so(escritas: _EspiaoDeEscrita) -> None:
    """Um gesto, UMA escrita — e com o valor final, não com o do meio."""
    host, escala = _host_com_brilho()
    _arrastar(host, escala, 100, 60)
    escala.disparar("button-release-event", escala, None)

    assert len(escritas.chamadas) == 1, (
        "soltar tinha de acender o controle uma vez; "
        f"escritas={escritas.chamadas}"
    )
    rgb, brilho, uniq = escritas.chamadas[0]
    assert rgb == ROXO
    assert brilho == pytest.approx(0.60)
    assert uniq == UNIQ_1


def test_a_ligacao_do_soltar_existe_na_instalacao_da_aba() -> None:
    """Prova direta da fiação: sem ela, todo o resto deste arquivo é teatro."""
    _host, escala = _host_com_brilho()
    assert "button-release-event" in escala.handlers, (
        "install_lightbar_tab não ligou o button-release-event do brilho — "
        "arrastar e soltar volta a não acender nada"
    )


def test_soltar_pelo_teclado_tambem_acende(escritas: _EspiaoDeEscrita) -> None:
    """Quem move o controle pelas setas nunca solta botão de mouse nenhum."""
    host, escala = _host_com_brilho()
    _arrastar(host, escala, 100, 95)
    escala.disparar("key-release-event", escala, None)

    assert len(escritas.chamadas) == 1
    assert escritas.chamadas[0][1] == pytest.approx(0.95)


def test_soltar_sem_ter_mexido_nao_escreve(escritas: _EspiaoDeEscrita) -> None:
    """Clicar no controle sem mudar valor não é pedido de nada."""
    _host, escala = _host_com_brilho()
    escala.disparar("button-release-event", escala, None)

    assert escritas.chamadas == []


def test_dois_gestos_seguidos_sao_duas_escritas_e_nao_mais(
    escritas: _EspiaoDeEscrita,
) -> None:
    """Cada gesto se fecha: soltar duas vezes não reenvia a primeira."""
    host, escala = _host_com_brilho()
    _arrastar(host, escala, 100, 80)
    escala.disparar("button-release-event", escala, None)
    _arrastar(host, escala, 80, 40)
    escala.disparar("button-release-event", escala, None)
    escala.disparar("button-release-event", escala, None)  # solta de novo, parado

    assert [c[1] for c in escritas.chamadas] == [
        pytest.approx(0.80),
        pytest.approx(0.40),
    ]


def test_o_handler_do_soltar_nao_consome_o_evento(escritas: _EspiaoDeEscrita) -> None:
    """Devolver True roubaria o fim do arraste do próprio GtkRange."""
    host, escala = _host_com_brilho()
    _arrastar(host, escala, 100, 90)
    assert host._on_lightbar_brilho_solto(escala, None) is False


def test_repovoar_a_aba_nao_conta_como_gesto(escritas: _EspiaoDeEscrita) -> None:
    """``_refresh_guard`` ligado = a janela mexeu no widget, não ela."""
    host, escala = _host_com_brilho()
    host._refresh_guard = True
    _arrastar(host, escala, 100, 50)
    escala.disparar("button-release-event", escala, None)
    host._refresh_guard = False

    assert escritas.chamadas == []


def test_daemon_offline_nao_explode_e_conta_a_verdade(
    escritas: _EspiaoDeEscrita,
) -> None:
    """Controle desconectado falha em silêncio, como o resto do módulo."""
    escritas.resposta = False
    host, escala = _host_com_brilho()
    _arrastar(host, escala, 100, 70)
    escala.disparar("button-release-event", escala, None)

    assert len(escritas.chamadas) == 1
    assert any("Não consegui aplicar" in t for t in host._toasts)


def test_alvo_selecionado_recebe_sozinho(escritas: _EspiaoDeEscrita) -> None:
    """PERFIL-05/R-17: com um controle escolhido, o MAC dele viaja no pedido."""
    host, escala = _host_com_brilho(uniq=UNIQ_2, conectados={1: UNIQ_1, 2: UNIQ_2})
    _arrastar(host, escala, 100, 30)
    escala.disparar("button-release-event", escala, None)

    assert [c[2] for c in escritas.chamadas] == [UNIQ_2]


# ---------------------------------------------------------------------------
# Cor: confirmar a cor no diálogo acende AGORA
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _gdk_rgba_ok(), reason="Gdk.RGBA ausente (CI headless)")
def test_soltar_o_seletor_de_cor_acende_uma_vez(escritas: _EspiaoDeEscrita) -> None:
    """O caso mais defensável da queixa: escolher cor não acendia nada.

    Simula a cadeia real: o Builder liga ``color-set`` ao handler de rascunho
    (que roda primeiro) e ``install_lightbar_tab`` liga o de escrita.
    """
    seletor = _SeletorDeCor()
    host = _Host(
        _draft(),
        {"lightbar_color_button": seletor, "lightbar_preview": _WidgetEspiao()},
        conectados={1: UNIQ_1, 2: UNIQ_2},
    )
    host.install_lightbar_tab()
    assert "color-set" in seletor.handlers, (
        "install_lightbar_tab não ligou o color-set — escolher a cor volta a "
        "só mexer no rascunho"
    )

    seletor.escolher(AZUL)
    host.on_lightbar_color_set(seletor)  # o que o glade fia (rascunho + prévia)
    seletor.disparar("color-set", seletor)  # o que a entrega 1 fia (escrita)

    assert escritas.chamadas == [
        (AZUL, 1.0, UNIQ_1),
        (AZUL, 1.0, UNIQ_2),
    ], "um gesto = uma escrita por controle conectado (R-14), e nem uma a mais"


@pytest.mark.skipif(not _gdk_rgba_ok(), reason="Gdk.RGBA ausente (CI headless)")
def test_escolher_cor_nao_desliga_a_paleta_automatica(
    escritas: _EspiaoDeEscrita,
) -> None:
    """A entrega 1 não pode reabrir o R-14: acender agora não é matar o auto."""
    seletor = _SeletorDeCor()
    host = _Host(
        _draft(auto=True),
        {"lightbar_color_button": seletor, "lightbar_preview": _WidgetEspiao()},
        conectados={1: UNIQ_1},
    )
    host.install_lightbar_tab()
    seletor.escolher(AZUL)
    host.on_lightbar_color_set(seletor)
    seletor.disparar("color-set", seletor)

    assert host.draft.leds.auto_player_colors is True
    assert host.draft.effective_leds_for(UNIQ_1).lightbar_rgb == AZUL
