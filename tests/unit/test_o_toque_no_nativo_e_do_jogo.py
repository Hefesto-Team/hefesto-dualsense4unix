"""O-TOQUE-NO-NATIVO-E-DO-JOGO-QUALQUER-QUE-SEJA-A-MASCARA-GUARDADA-01.

D-2411-NO-NATIVO-COM-JOGO-O-TOQUE-E-DO-JOGO. No Modo Nativo não há controle virtual: o jogo fala
direto com o controle de verdade (``hidraw``; o winebus não mantém aberto o ``eventN`` de um
DualSense), e a máscara guardada não descreve nada do que ele vê. Com jogo aberto e touchpad
Ligado, o hub segura o nó «Touchpad» (``EVIOCGRAB``) e o dedo não move o cursor do sistema, seja
a máscara guardada DualSense, Xbox ou Nintendo, com a emulação de gamepad guardada ligada ou
não. Sem jogo, e na janela do cliente da Steam
(``D-1510-A-JANELA-DA-STEAM-NAO-TOMA-O-TOQUE``), o Ligado segue o cursor. O Desligado segue
seguro em toda máscara (``D-1510-O-TOUCHPAD-E-POR-CONTROLE``).

O agarre acontece uma vez por mudança de estado (jogo abre, jogo fecha, foco entra ou sai da
Steam, interruptor muda): as réguas contam os ``set_grab`` de cada leitor e reprovam rajada.

O instrumento é o do uso: o ``SensorHub`` de verdade e o handler de verdade, com leitores de
touchpad de mentira que guardam o estado do grab (os de
``test_o_toque_ligado_e_o_cursor_com_jogo_aberto_fora_da_dualsense``).

AS MORDIDAS (24/11/2026, cada uma devolvida com o md5 conferido):

- a pergunta do toque voltando a consultar a máscara guardada no Nativo reprova as linhas Xbox
  e Nintendo de :func:`test_no_nativo_o_ligado_com_jogo_agarra_em_toda_mascara_guardada` e as
  outras réguas de nó segurado;
- a pergunta devolvendo ``True`` também na janela do cliente da Steam reprova
  :func:`test_a_janela_do_cliente_da_steam_solta_o_no_no_nativo`;
- a pergunta devolvendo sempre ``False`` no Nativo reprova toda linha com nó segurado;
- um leitor cujo agarre não pega (o laço que agarra a cada tique) estoura a contagem em
  :func:`test_o_instrumento_ve_a_rajada`.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from tests.unit import (
    test_o_toque_ligado_e_o_cursor_com_jogo_aberto_fora_da_dualsense as base,
)

_PECAS = base._PECAS
_UNIQS = base._UNIQS
_JANELA = base._JANELA
_IDS_DE_PECA = base._IDS_DE_PECA
_GUARDADAS = ("dualsense", "xbox", "nintendo")


@pytest.fixture(autouse=True)
def _registro_limpo() -> Any:
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


class _DaemonNativo(base._Daemon):
    """O handler de verdade com o daemon no Modo Nativo: sem vpad e sem cursor emulado."""

    emulacao_guardada = False

    def __init__(self, modo: str, guardada: str = "dualsense") -> None:
        super().__init__("mouse_e_teclado", guardada)
        self.daemon.is_native_mode = lambda: True
        self.daemon.config.gamepad_emulation_enabled = self.emulacao_guardada
        self.daemon.config.mouse_emulation_enabled = False


@pytest.fixture
def montar(monkeypatch: pytest.MonkeyPatch) -> Any:
    def _montar(guardada: str, emulacao: bool = False) -> base._Mesa:
        classe = type("_N", (_DaemonNativo,), {"emulacao_guardada": emulacao})
        monkeypatch.setattr(base, "_Daemon", classe)
        return base._Mesa(monkeypatch, "mouse_e_teclado", guardada)

    return _montar


def _agarres(mesa: base._Mesa) -> int:
    return sum(len(leitor.grabs) for _u, leitor in mesa.criados)


@pytest.mark.parametrize("emulacao", (False, True))
@pytest.mark.parametrize("guardada", _GUARDADAS)
@pytest.mark.parametrize(("uniq", "transporte"), _PECAS, ids=_IDS_DE_PECA)
def test_no_nativo_o_ligado_com_jogo_agarra_em_toda_mascara_guardada(
    montar: Any, guardada: str, emulacao: bool, uniq: str, transporte: str
) -> None:
    mesa = montar(guardada, emulacao)
    mesa.conferir()
    assert mesa.leitor(uniq).grab_state == "held", (
        f"Nativo ({transporte}, máscara guardada {guardada}): o toque não ficou com o jogo"
    )
    assert mesa.leitor(uniq).grabs == [True], "o agarre veio em rajada"
    assert mesa.segurados() == set(_UNIQS)
    assert REGISTRO.filtrar(uniq, _JANELA) is _JANELA, "o dedo foi zerado antes do jogo"


@pytest.mark.parametrize("guardada", _GUARDADAS)
def test_o_agarre_e_um_por_mudanca_de_estado(montar: Any, guardada: str) -> None:
    mesa = montar(guardada)
    mesa.conferir()
    assert _agarres(mesa) == len(_UNIQS)
    for _ in range(25):
        mesa.conferir()
    assert _agarres(mesa) == len(_UNIQS), "o hub agarrou de novo sem mudança de estado"

    mesa.daemon.focar_a_steam()
    mesa.conferir()
    mesa.conferir()
    assert mesa.segurados() == set()
    assert _agarres(mesa) == 2 * len(_UNIQS), "entrar na Steam custou mais de um gesto por nó"

    mesa.daemon.abrir_o_jogo()
    mesa.conferir()
    mesa.conferir()
    assert mesa.segurados() == set(_UNIQS)
    assert _agarres(mesa) == 3 * len(_UNIQS)

    mesa.daemon.fechar_o_jogo()
    mesa.conferir()
    mesa.conferir()
    assert mesa.segurados() == set()
    assert _agarres(mesa) == 4 * len(_UNIQS)
    assert all(leitor.grabs == [True, False, True, False] for _u, leitor in mesa.criados)


@pytest.mark.parametrize("guardada", _GUARDADAS)
def test_a_janela_do_cliente_da_steam_solta_o_no_no_nativo(montar: Any, guardada: str) -> None:
    """D-1510-A-JANELA-DA-STEAM-NAO-TOMA-O-TOQUE vale no Nativo: a loja tem cursor."""
    mesa = montar(guardada)
    mesa.conferir()
    mesa.daemon.focar_a_steam()
    mesa.conferir()
    assert mesa.segurados() == set(), "na loja e na biblioteca o cursor é do sistema"
    mesa.daemon.abrir_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set(_UNIQS)


@pytest.mark.parametrize("guardada", _GUARDADAS)
def test_sem_jogo_o_ligado_e_o_cursor_no_nativo(montar: Any, guardada: str) -> None:
    mesa = montar(guardada)
    mesa.daemon.fechar_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set()
    assert all(leitor.grabs in ([], [True, False]) for _u, leitor in mesa.criados)


@pytest.mark.parametrize("guardada", _GUARDADAS)
@pytest.mark.parametrize("uniq", _UNIQS, ids=_IDS_DE_PECA)
def test_o_desligado_segue_seguro_e_o_ligado_dos_outros_tambem(
    montar: Any, guardada: str, uniq: str
) -> None:
    mesa = montar(guardada)
    REGISTRO.definir_touchpad(uniq, ligado=False)
    mesa.conferir()
    assert mesa.segurados() == set(_UNIQS)
    mesa.daemon.focar_a_steam()
    mesa.conferir()
    assert mesa.segurados() == {uniq}, "o Desligado soltou o nó na janela da Steam"
    mesa.daemon.fechar_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set()


@pytest.mark.parametrize("guardada", _GUARDADAS)
@pytest.mark.parametrize("uniq", _UNIQS, ids=_IDS_DE_PECA)
def test_religar_no_nativo_com_jogo_segue_ao_jogo(montar: Any, guardada: str, uniq: str) -> None:
    mesa = montar(guardada)
    REGISTRO.definir_touchpad(uniq, ligado=False)
    mesa.conferir()
    REGISTRO.definir_touchpad(uniq, ligado=True)
    mesa.conferir()
    assert mesa.leitor(uniq).grab_state == "held"
    assert mesa.leitor(uniq).grabs == [True], "religar soltou e agarrou o nó de novo"


@pytest.mark.parametrize("guardada", _GUARDADAS)
@pytest.mark.parametrize("uniq", _UNIQS, ids=_IDS_DE_PECA)
def test_o_controle_que_sai_e_volta_no_nativo_volta_ao_jogo(
    montar: Any, guardada: str, uniq: str
) -> None:
    mesa = montar(guardada)
    mesa.conferir()
    mesa.sair(uniq)
    assert mesa.segurados() == set(_UNIQS) - {uniq}
    mesa.voltar(uniq)
    assert mesa.segurados() == set(_UNIQS), "voltou e o nó ficou com o cursor"
    assert all(leitor.grabs == [True] for dono, leitor in mesa.criados if dono != uniq)


@pytest.mark.parametrize("guardada", _GUARDADAS)
def test_a_mesa_misturada_no_nativo_cada_peca_com_o_seu_desfecho(
    montar: Any, guardada: str
) -> None:
    """P1 Ligado, P2 Desligado, P3 com rota, P4 Ligado: no Nativo todas ficam com o jogo."""
    mesa = montar(guardada)
    REGISTRO.definir_touchpad(_UNIQS[1], ligado=False)
    mesa.hub.toque_da_peca(_UNIQS[2])
    mesa.conferir()
    assert mesa.segurados() == set(_UNIQS)
    mesa.relogio.agora += 6.0
    mesa.conferir()
    assert mesa.segurados() == set(_UNIQS), "a rota que parou soltou o nó da P3 com o jogo aberto"
    assert all(leitor.grabs == [True] for _u, leitor in mesa.criados)
    mesa.daemon.focar_a_steam()
    mesa.conferir()
    assert mesa.segurados() == {_UNIQS[1]}
    mesa.daemon.fechar_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set()


@pytest.mark.parametrize("guardada", _GUARDADAS)
def test_a_pergunta_do_daemon_no_nativo_nao_consulta_a_mascara(
    montar: Any, guardada: str
) -> None:
    mesa = montar(guardada)
    perguntar = mesa.hub._toque_proprio_do_jogo
    assert perguntar is not None
    assert all(perguntar(u) is True for u in _UNIQS)
    mesa.daemon.focar_a_steam()
    assert all(perguntar(u) is False for u in _UNIQS), "a janela da Steam tomou o toque"


def test_o_instrumento_ve_a_rajada(montar: Any) -> None:
    """Um agarre que não pega é refeito a cada tique: a contagem tem de acusar."""
    mesa = montar("xbox")
    for _uniq, leitor in mesa.criados:
        leitor.set_grab = lambda querido, _l=leitor: (_l.grabs.append(querido), False)[1]
        leitor.grab_state = "off"
    for _ in range(10):
        mesa.conferir()
    assert _agarres(mesa) >= 10 * len(_UNIQS), "o laço que agarra a cada tique passou sem ser visto"


def test_fora_do_nativo_a_mascara_guardada_segue_mandando(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O contraste: o mesmo daemon sem o Nativo, com a máscara Xbox, deixa o cursor ao sistema."""
    mesa = base._Mesa(monkeypatch, "xbox")
    mesa.conferir()
    assert mesa.segurados() == set()
    assert isinstance(mesa.daemon.daemon, SimpleNamespace)
