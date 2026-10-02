"""CONTAGEM-E-COOP-01 (a) — a janela inteira com UM denominador só.

O defeito medido em 29/07: a MESMA tela dizia números diferentes para "quantos
controles". Cinco lugares respondiam à pergunta, cada um com a conta feita
inline:

1. a fita de chips do topo — ``len(conectados) + len(externals)``;
2. a faixa "Número deste controle" — o mesmo total;
3. o cabeçalho — ``len(conectados)``, com o texto "N controles";
4. a linha "Conectado (N controles)" do frame Estado — ``len(conectados)``;
5. os cards da aba Status — ``len(conectados)`` (via ``_status_card_keys_for``),
   mais a base da numeração dos externos (``_dualsense_count``) e a linha de
   bateria, todos derivando do mesmo ``len(conectados)`` repetido.

Com dois DualSense e dois externos vivos, o cabeçalho dizia "2 controles" ao
lado de quatro chips e de uma faixa oferecendo os números 1, 2, 3 e 4.

A cura NÃO foi somar tudo: os dois espaços são reais e têm razão registrada
(externo não tem card nem bateria — EXT-COUNT-01; mas divide o espaço de
numeração — R-24/NUM-01). A cura foi (i) fazer todos derivarem de UMA função,
``_contagem_de_controles``, e (ii) NOMEAR o número na tela, porque "2" e "4"
estão os dois certos quando se diz de qual dos dois se trata.

Cada teste aqui MORDE: as asserções de texto reprovam exatamente o texto ANTIGO
("2 controles" com quatro controles na mesa), e as de derivação reprovam quem
voltar a fazer a conta inline.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("contagem: um numero so na janela")

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.status_actions import (
    ContagemDeControles,
    StatusActionsMixin,
    texto_de_contagem,
)

UNIQ_A = "aabbcc000001"
UNIQ_B = "aabbcc000002"


class _Rotulo:
    def __init__(self) -> None:
        self.markup: str | None = None
        self.texto: str | None = None
        self.visivel: bool | None = None

    def set_markup(self, markup: str) -> None:
        self.markup = markup

    def set_text(self, texto: str) -> None:
        self.texto = texto

    def set_visible(self, valor: bool) -> None:
        self.visivel = bool(valor)

    def show(self) -> None:
        self.visivel = True

    def hide(self) -> None:
        self.visivel = False

    def set_show_text(self, _valor: bool) -> None:
        pass

    def set_fraction(self, _valor: float) -> None:
        pass

    def get_children(self) -> list[Any]:
        return []


class _Builder:
    def __init__(self) -> None:
        self._widgets: dict[str, Any] = {}

    def get_object(self, wid: str) -> Any:
        return self._widgets.setdefault(wid, _Rotulo())


class _Janela(StatusActionsMixin):
    """Host mínimo: builder dublado + os colaboradores de widget anotados."""

    def __init__(self, externos: int = 0) -> None:
        self.builder = _Builder()
        self._reconnect_state = "online"
        self._consecutive_failures = 0
        self._externals = [
            {"key": f"ext{i}", "player_slot": None} for i in range(externos)
        ]
        self._target_combo = _Rotulo()
        self._target_combo_rows = []
        self._target_combo_active = 0
        self._target_combo_visible = False
        self._target_combo_updating = False
        self._externals_sig = None
        self._target_uniq_by_index = {}
        self._target_label_by_index = {}
        self._target_slot_by_index = {}
        self._totais_da_faixa: list[int] = []
        self._linhas_construidas: list[list[tuple[str, int | None]]] = []

    def _maybe_fetch_externals(self) -> None:
        """No-op: o inventário de externos é IPC (`controller.list`) e este"""


    def _rebuild_target_buttons(
        self, _box: Any, rows: list[tuple[str, int | None]]
    ) -> None:
        self._linhas_construidas.append(list(rows))

    def _set_target_active(self, _pos: int) -> None:
        pass

    def _set_target_strip_visible(self, _visivel: bool) -> None:
        pass

    def _refresh_numero_selector(self, total: int) -> None:
        self._totais_da_faixa.append(total)


def _dualsense(
    index: int, transporte: str, slot: int | None, uniq: str
) -> dict[str, Any]:
    return {
        "index": index,
        "transport": transporte,
        "connected": True,
        "is_primary": index == 0,
        "player_slot": slot,
        "uniq": uniq,
    }


def _estado(conectados: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "connected": bool(conectados),
        "transport": (conectados[0]["transport"] if conectados else "—"),
        "controllers": conectados,
        "battery_pct": 80,
        "active_profile": "vitoria",
    }


@pytest.fixture()
def mesa_2x2() -> tuple[_Janela, dict[str, Any]]:
    """Dois DualSense adotados + dois externos — a mesa em que a tela divergia."""
    janela = _Janela(externos=2)
    estado = _estado(
        [
            _dualsense(0, "usb", 1, UNIQ_A),
            _dualsense(1, "bt", 2, UNIQ_B),
        ]
    )
    return janela, estado


def test_a_mesa_e_a_soma_e_os_dois_espacos_seguem_separados() -> None:
    contagem = ContagemDeControles(adotados=2, externos=2)
    assert contagem.na_mesa == 4
    assert contagem.adotados == 2, "card e bateria contam só os adotados"
    assert contagem.externos == 2


@pytest.mark.parametrize(
    ("adotados", "externos", "esperado"),
    [
        (0, 0, ""),
        (1, 0, ""),
        (0, 1, ""),
        (2, 0, "2 controles"),
        (4, 0, "4 controles"),
        (2, 2, "2 do Hefesto + 2 externos"),
        (1, 1, "1 do Hefesto + 1 externo"),
        (1, 2, "1 do Hefesto + 2 externos"),
        (0, 2, "2 externos (nenhum do Hefesto)"),
    ],
)
def test_o_texto_diz_de_qual_numero_se_trata(
    adotados: int, externos: int, esperado: str
) -> None:
    """Sem externos o número é único e o texto não muda (a largura da CI agradece);"""
    assert texto_de_contagem(ContagemDeControles(adotados, externos)) == esperado


def test_a_contagem_da_janela_le_os_dois_espacos_de_uma_vez(
    mesa_2x2: tuple[_Janela, dict[str, Any]],
) -> None:
    janela, estado = mesa_2x2
    contagem = janela._contagem_de_controles(estado)
    assert (contagem.adotados, contagem.externos, contagem.na_mesa) == (2, 2, 4)


def test_placeholder_offline_nao_entra_na_conta() -> None:
    """HARM-CARD-FANTASMA-01: `describe_controllers` devolve UMA entrada com"""
    janela = _Janela()
    fantasma = _dualsense(0, "usb", None, UNIQ_A) | {"connected": False}
    contagem = janela._contagem_de_controles({"controllers": [fantasma]})
    assert contagem.na_mesa == 0


def test_cabecalho_e_frame_estado_nomeiam_os_externos(
    mesa_2x2: tuple[_Janela, dict[str, Any]],
) -> None:
    """O defeito, no ponto exato: "2 controles" com QUATRO na mesa."""
    janela, estado = mesa_2x2

    janela._render_online(estado)
    janela._render_slow_state(estado)

    cabecalho = janela.builder.get_object("header_connection").markup or ""
    assert "2 do Hefesto + 2 externos" in cabecalho
    assert "2 controles" not in cabecalho, (
        "o texto antigo dizia 2 com quatro controles na mesa"
    )
    assert "<b>USB</b>" in cabecalho and "BT" in cabecalho

    linha = janela.builder.get_object("status_connection").texto
    assert linha == "Conectado (2 do Hefesto + 2 externos)"


def test_um_dualsense_com_externos_para_de_calar_o_cabecalho() -> None:
    """A pior forma da divergência: o cabeçalho antigo entrava no caminho"""
    janela = _Janela(externos=2)
    estado = _estado([_dualsense(0, "usb", 1, UNIQ_A)])

    janela._render_online(estado)
    janela._render_slow_state(estado)

    cabecalho = janela.builder.get_object("header_connection").markup or ""
    assert "1 do Hefesto + 2 externos" in cabecalho
    assert "Conectado Via" not in cabecalho, (
        "o caminho single escondia os externos da mesa"
    )
    assert janela.builder.get_object("status_connection").texto == (
        "Conectado (1 do Hefesto + 2 externos)"
    )


def test_um_dualsense_sozinho_mantem_o_texto_de_sempre() -> None:
    """Cura exagerada também reprova: sem externos, nada na tela muda."""
    janela = _Janela()
    estado = _estado([_dualsense(0, "usb", 1, UNIQ_A)])

    janela._render_online(estado)
    janela._render_slow_state(estado)

    assert "Conectado Via USB" in (
        janela.builder.get_object("header_connection").markup or ""
    )
    assert janela.builder.get_object("status_connection").texto == "Conectado"


def test_dois_dualsense_sem_externos_mantem_o_texto_de_sempre() -> None:
    """Idem para 2+: "2 controles" é o texto histórico e não há ambiguidade —"""
    janela = _Janela()
    estado = _estado(
        [_dualsense(0, "usb", 1, UNIQ_A), _dualsense(1, "bt", 2, UNIQ_B)]
    )

    janela._render_online(estado)
    janela._render_slow_state(estado)

    assert "2 controles: <b>USB</b> + BT" in (
        janela.builder.get_object("header_connection").markup or ""
    )
    assert janela.builder.get_object("status_connection").texto == (
        "Conectado (2 controles)"
    )


def test_a_fita_e_a_faixa_de_numeros_seguem_a_mesa_inteira(
    mesa_2x2: tuple[_Janela, dict[str, Any]],
) -> None:
    """Os denominadores 1 e 2, agora derivados da MESMA função."""
    janela, estado = mesa_2x2

    janela._refresh_controller_target_combo(estado)

    assert janela._totais_da_faixa[-1] == 4
    assert janela._dualsense_count == 2
    # A fita continua com "Todos" + um chip por DualSense; os externos entram
    assert [rotulo for rotulo, _idx in janela._linhas_construidas[-1]] == [
        "Todos os controles",
        "Controle 1 — USB",
        "Controle 2 — BT",
    ]


def test_a_linha_de_bateria_conta_adotados_e_nao_a_mesa() -> None:
    """Um externo na mesa NÃO pode fazer a bateria do único DualSense sumir:
    externo é read-only e o Hefesto não lê bateria dele (EXT-COUNT-01)."""
    janela = _Janela(externos=3)
    estado = _estado([_dualsense(0, "usb", 1, UNIQ_A)])

    janela._render_slow_state(estado)

    assert janela.builder.get_object("status_battery_bar").visivel is True
    assert janela.builder.get_object("status_battery_caption").visivel is True


def test_cards_contam_adotados_e_nunca_a_mesa(
    mesa_2x2: tuple[_Janela, dict[str, Any]],
) -> None:
    """O denominador nº 5: dois cards para dois DualSense, com dois externos na
    mesa. Card de externo não existe — não há o que preencher nele."""
    _janela, estado = mesa_2x2
    chaves = StatusActionsMixin._status_card_keys_for(
        StatusActionsMixin._connected_controllers(estado)
    )
    assert len(chaves) == 2
