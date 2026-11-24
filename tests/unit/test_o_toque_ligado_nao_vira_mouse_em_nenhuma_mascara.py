"""O-TOQUE-LIGADO-NAO-VIRA-MOUSE-COM-JOGO-ABERTO-EM-NENHUMA-MASCARA-01: o nó fica seguro.

**A decisão (24/11/2026, ``D-2411-COM-JOGO-ABERTO-O-TOQUE-LIGADO-NUNCA-E-O-CURSOR-DO-SISTEMA``,
a validar pelo usuário).** Com um jogo aberto e o touchpad Ligado, o dedo nunca chega ao
sistema como ponteiro por omissão, em nenhuma máscara: o hub segura o nó «Touchpad» do
controle (``EVIOCGRAB``) enquanto o jogo estiver aberto e fora da janela do cliente da
Steam. O que o dedo faz depois de seguro é o que o perfil diz: a rota de cursor ou
zonas emite o cursor ou os botões (D-2809-O-TOQUE-E-A-INCLINACAO-NO-PERFIL, em que o
toque nasce em «nenhum»), a máscara DualSense leva o dedo ao jogo pelo pad virtual
(D-1510-O-JOGO-COM-TOQUE-PROPRIO-E-A-MASCARA-DUALSENSE) e as outras ficam mudas. A nota
datada da decisão de 12/10/2026: o «Ligado sem configuração própria é o cursor do
sistema» passa a valer só fora de jogo.

O instrumento é o do uso: o ``SensorHub`` de verdade, ligado ao daemon pelas MESMAS
perguntas que ``_garantir_sensor_hub`` do IPC faz (``_ha_jogo_para_o_toque`` e a
pergunta do toque, ambas do handler de verdade), com leitores de touchpad de mentira
que guardam o estado do grab. A máscara vem de ``config.gamepad_flavor`` e é única para
todos os controles (``D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES``); o mouse e o
teclado não são máscara, e sim o modo de navegação, que o hub não lê: a régua varre as
três máscaras que existem.

AS MORDIDAS (24/11/2026, cada uma devolvida com o md5 conferido):

- a pergunta do toque voltando a exigir a máscara DualSense reprova as linhas das
  máscaras Xbox e Nintendo de :func:`test_com_jogo_e_ligado_o_no_fica_seguro`, a mesa
  misturada e a rota que para;
- a pergunta devolvendo sempre ``True`` (a Steam deixa de soltar o nó) reprova
  :func:`test_a_janela_do_cliente_da_steam_solta_o_no`.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.virtual_motion import (
    REGISTRO,
    TAMANHO_DA_JANELA,
)
from hefesto_dualsense4unix.daemon import sensor_hub as sensor_hub_mod
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub

_PECAS = (
    ("aa:bb:cc:00:00:01", "usb"),
    ("aa:bb:cc:00:00:02", "bt"),
    ("aa:bb:cc:00:00:03", "usb"),
    ("aa:bb:cc:00:00:04", "bt"),
)
_UNIQS = tuple(u for u, _ in _PECAS)
_MASCARAS = ("dualsense", "xbox", "nintendo")
_JANELA = bytes(range(1, TAMANHO_DA_JANELA + 1))


@pytest.fixture(autouse=True)
def _registro_limpo() -> Any:
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _LeitorDoToque:
    def __init__(self) -> None:
        self.grab_state = "off"
        self.grabs: list[bool] = []

    def start(self) -> bool:
        return True

    def stop(self) -> None:
        self.grab_state = "off"

    def touch_state(self) -> Any:
        return SimpleNamespace(touching=False, fingers=())

    def regions_pressed(self) -> frozenset[str]:
        return frozenset()

    def set_grab(self, querido: bool) -> bool:
        self.grabs.append(querido)
        self.grab_state = "held" if querido else "off"
        return True


class _Daemon(IpcHandlersMixin):
    """O handler de verdade, com o daemon de mentira que o hub pergunta."""

    store: Any
    daemon: Any

    def __init__(self, mascara: str) -> None:
        self.store = SimpleNamespace(window_detect_current_class="steam_app_1")
        self.daemon = SimpleNamespace(
            display_authority="game",
            config=SimpleNamespace(gamepad_flavor=mascara),
            is_native_mode=lambda: False,
        )
        self._sensor_hub = None

    def abrir_o_jogo(self) -> None:
        self.daemon.display_authority = "game"
        self.store.window_detect_current_class = "steam_app_1"

    def fechar_o_jogo(self) -> None:
        self.daemon.display_authority = "desktop"
        self.store.window_detect_current_class = "firefox"

    def focar_a_steam(self) -> None:
        self.store.window_detect_current_class = "steam"


class _Mesa:
    """O hub real ligado ao handler real: o que o daemon monta no primeiro uso."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, mascara: str) -> None:
        self.relogio = _Relogio()
        self.presentes = set(_UNIQS)
        self.criados: list[tuple[str, _LeitorDoToque]] = []
        self.mudou = False
        mesa = self

        class _HubDaMesa(SensorHub):
            def __init__(self) -> None:
                super().__init__(
                    motion_factory=lambda uniq, node: SimpleNamespace(
                        start=lambda: True, stop=lambda: None
                    ),
                    touch_factory=mesa._novo_leitor,
                    gamepad_factory=lambda uniq, node: SimpleNamespace(
                        start=lambda: True, stop=lambda: None
                    ),
                    descobrir_motion=dict,
                    descobrir_touch=mesa._descobrir,
                    descobrir_gamepad=dict,
                    relogio=mesa.relogio,
                    auto_manutencao=False,
                )

        monkeypatch.setattr(sensor_hub_mod, "SensorHub", _HubDaMesa)
        self.daemon = _Daemon(mascara)
        self.hub = self.daemon._garantir_sensor_hub()
        self.hub._watch = SimpleNamespace(poll=self._poll)
        for uniq in _UNIQS:
            self.hub.leitura(uniq)
        self.hub.reconciliar()

    def _poll(self) -> bool:
        mudou, self.mudou = self.mudou, False
        return mudou

    def _novo_leitor(self, uniq: str, _node: Any) -> _LeitorDoToque:
        leitor = _LeitorDoToque()
        self.criados.append((uniq, leitor))
        return leitor

    def _descobrir(self) -> dict[str, Path]:
        return {u: Path(f"/dev/input/event-{u}") for u in sorted(self.presentes)}

    def leitor(self, uniq: str) -> _LeitorDoToque:
        return [leitor for dono, leitor in self.criados if dono == uniq][-1]

    def conferir(self) -> None:
        self.hub.reconciliar()

    def sair(self, uniq: str) -> None:
        self.presentes.discard(uniq)
        self.mudou = True
        self.hub.reconciliar()

    def voltar(self, uniq: str) -> None:
        self.presentes.add(uniq)
        self.mudou = True
        self.hub.reconciliar()
        self.hub.reconciliar()

    def segurados(self) -> set[str]:
        return {
            u for u in _UNIQS if u in self.presentes and self.leitor(u).grab_state == "held"
        }


@pytest.fixture
def montar(monkeypatch: pytest.MonkeyPatch) -> Any:
    def _montar(mascara: str) -> _Mesa:
        return _Mesa(monkeypatch, mascara)

    return _montar


@pytest.mark.parametrize("mascara", _MASCARAS)
@pytest.mark.parametrize(("uniq", "transporte"), _PECAS, ids=[f"p{n + 1}" for n in range(4)])
def test_com_jogo_e_ligado_o_no_fica_seguro(
    montar: Any, mascara: str, uniq: str, transporte: str
) -> None:
    """D-2411-COM-JOGO-ABERTO-O-TOQUE-LIGADO-NUNCA-E-O-CURSOR-DO-SISTEMA: o nó fica seguro.

    Cada máscara, cada peça (cabo e rádio): jogo aberto e Ligado seguram o nó da peça.
    """
    mesa = montar(mascara)
    mesa.conferir()
    assert mesa.leitor(uniq).grab_state == "held", (
        f"o nó ({transporte}, máscara {mascara}) ficou com o sistema: o dedo move o cursor"
    )
    assert mesa.segurados() == set(_UNIQS), "uma peça Ligada ficou com o sistema"
    assert REGISTRO.filtrar(uniq, _JANELA) is _JANELA, "o dedo foi zerado antes do jogo"


@pytest.mark.parametrize("mascara", _MASCARAS)
def test_sem_jogo_aberto_o_ligado_e_o_cursor_do_sistema(montar: Any, mascara: str) -> None:
    mesa = montar(mascara)
    mesa.daemon.fechar_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set()
    assert all(leitor.grabs in ([], [True, False]) for _u, leitor in mesa.criados)


@pytest.mark.parametrize("mascara", _MASCARAS)
def test_o_jogo_que_fecha_devolve_o_no_no_mesmo_tique(montar: Any, mascara: str) -> None:
    mesa = montar(mascara)
    mesa.conferir()
    assert mesa.segurados() == set(_UNIQS)
    mesa.daemon.fechar_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set(), "o jogo fechou e o nó seguiu longe do sistema"
    mesa.daemon.abrir_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set(_UNIQS)


@pytest.mark.parametrize("mascara", _MASCARAS)
def test_a_janela_do_cliente_da_steam_solta_o_no(montar: Any, mascara: str) -> None:
    mesa = montar(mascara)
    mesa.conferir()
    mesa.daemon.focar_a_steam()
    mesa.conferir()
    assert mesa.segurados() == set(), "na loja e na biblioteca o cursor é do sistema"
    mesa.daemon.abrir_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set(_UNIQS)


@pytest.mark.parametrize("mascara", _MASCARAS)
@pytest.mark.parametrize("uniq", _UNIQS, ids=[f"p{n + 1}" for n in range(4)])
def test_com_a_rota_de_cursor_o_no_segue_seguro_e_o_sistema_nao_ve_dois_ponteiros(
    montar: Any, mascara: str, uniq: str
) -> None:
    """A rota do perfil pede o nó; quando a rota para, o jogo aberto o mantém seguro."""
    mesa = montar(mascara)
    mesa.hub.toque_da_peca(uniq)
    mesa.conferir()
    assert mesa.leitor(uniq).grab_state == "held"
    mesa.relogio.agora += 6.0
    mesa.conferir()
    assert mesa.leitor(uniq).grab_state == "held", (
        "a rota parou e o nó voltou ao sistema com o jogo aberto"
    )
    assert mesa.leitor(uniq).grabs.count(False) == 0, "o nó foi solto e retomado no meio"


def test_a_mesa_misturada_cada_peca_com_o_seu_desfecho(montar: Any) -> None:
    """P1 Ligado, P2 Desligado, P3 com rota, P4 Ligado: nenhuma decide pela outra."""
    mesa = montar("xbox")
    REGISTRO.definir_touchpad(_UNIQS[1], ligado=False)
    mesa.hub.toque_da_peca(_UNIQS[2])
    mesa.conferir()
    assert mesa.segurados() == set(_UNIQS)

    mesa.relogio.agora += 6.0
    mesa.conferir()
    assert mesa.segurados() == set(_UNIQS), "a rota que parou soltou um nó com o jogo aberto"

    mesa.daemon.focar_a_steam()
    mesa.conferir()
    assert mesa.segurados() == {_UNIQS[1]}, (
        "na Steam só o Desligado segue seguro; os outros três voltam ao cursor do sistema"
    )

    mesa.daemon.fechar_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set(), "o Desligado é do jogo: sem jogo, o cursor é do sistema"


@pytest.mark.parametrize("mascara", _MASCARAS)
@pytest.mark.parametrize("uniq", _UNIQS, ids=[f"p{n + 1}" for n in range(4)])
def test_o_controle_que_sai_e_volta_e_seguro_de_novo(
    montar: Any, mascara: str, uniq: str
) -> None:
    mesa = montar(mascara)
    mesa.conferir()
    outros = set(_UNIQS) - {uniq}
    mesa.sair(uniq)
    assert mesa.segurados() == outros
    mesa.voltar(uniq)
    assert mesa.leitor(uniq).grab_state == "held", "voltou e o nó ficou com o sistema"
    assert mesa.segurados() == set(_UNIQS)
