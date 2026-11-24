"""O-TOQUE-LIGADO-VOLTA-A-SER-O-CURSOR-COM-JOGO-ABERTO-FORA-DA-MASCARA-DUALSENSE-01.

**A regra (decidida em 12/10/2026 e em 15/10/2026).** O que a aba Jogar diz é o que o
aparelho faz: touchpad Ligado é o cursor do sistema, com jogo aberto ou fechado. A exceção é
a de ``D-1510-O-JOGO-COM-TOQUE-PROPRIO-E-A-MASCARA-DUALSENSE``: na máscara DualSense, com jogo
aberto e fora da janela do cliente da Steam, o hub segura o nó «Touchpad» (``EVIOCGRAB``) e o
dedo vai ao jogo pelo controle virtual. Fora da DualSense (Xbox, Nintendo, mouse e teclado),
o Ligado não é seguro: o dedo chega ao sistema como cursor. O Desligado segura o nó em toda máscara
com jogo aberto (``D-1510-O-TOUCHPAD-E-POR-CONTROLE``), e a rota de cursor ou zonas do perfil
(``D-2809-O-TOQUE-E-A-INCLINACAO-NO-PERFIL``) e o dedo do servidor DSU têm demanda própria.

``D-2411-COM-JOGO-ABERTO-O-TOQUE-LIGADO-NUNCA-E-O-CURSOR-DO-SISTEMA`` (nó seguro em toda
máscara) foi recusada na validação de 24/11/2026 e caducou: este arquivo a segura fora do
código, para ninguém a «curar» de novo.

O instrumento é o do uso: o ``SensorHub`` de verdade, ligado ao daemon pelas MESMAS perguntas
que ``_garantir_sensor_hub`` do IPC faz (``_ha_jogo_para_o_toque`` e a pergunta do toque,
ambas do handler de verdade), com leitores de touchpad de mentira que guardam o estado do
grab. A máscara é única para todos os controles
(``D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES``). O mouse e o teclado não são máscara: com
eles o controle virtual não existe e a máscara cai no padrão, que não é a DualSense; a régua
tem o modo e o sinal de emulação ligado, que o hub não lê.

AS MORDIDAS (24/11/2026, cada uma devolvida com o md5 conferido):

- a pergunta do toque devolvendo ``not _na_steam(self)`` para toda máscara (a cura recusada)
  reprova :func:`test_o_ligado_com_jogo_so_agarra_na_mascara_dualsense` nas linhas fora da
  DualSense, a mesa misturada e a rota que para;
- a pergunta devolvendo sempre ``True`` reprova também
  :func:`test_a_janela_do_cliente_da_steam_solta_o_no`;
- a pergunta devolvendo sempre ``False`` reprova a linha da DualSense.
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
_MODOS = ("dualsense", "xbox", "nintendo", "mouse_e_teclado")
_JANELA = bytes(range(1, TAMANHO_DA_JANELA + 1))
_IDS_DE_PECA = [f"p{n + 1}" for n in range(4)]


def _com_toque_proprio(modo: str) -> bool:
    """Só a máscara DualSense leva o dedo ao jogo; o resto é o cursor do sistema."""
    return modo == "dualsense"


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

    def __init__(self, modo: str) -> None:
        flavor = modo if modo in ("dualsense", "xbox", "nintendo") else "xbox"
        self.store = SimpleNamespace(window_detect_current_class="steam_app_1")
        self.daemon = SimpleNamespace(
            display_authority="game",
            config=SimpleNamespace(
                gamepad_flavor=flavor,
                mouse_emulation_enabled=modo == "mouse_e_teclado",
            ),
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

    def __init__(self, monkeypatch: pytest.MonkeyPatch, modo: str) -> None:
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
        self.daemon = _Daemon(modo)
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

    def nenhum_grab_pedido(self) -> bool:
        return all(leitor.grabs == [] for _u, leitor in self.criados)


@pytest.fixture
def montar(monkeypatch: pytest.MonkeyPatch) -> Any:
    def _montar(modo: str) -> _Mesa:
        return _Mesa(monkeypatch, modo)

    return _montar


@pytest.mark.parametrize("modo", _MODOS)
@pytest.mark.parametrize(("uniq", "transporte"), _PECAS, ids=_IDS_DE_PECA)
def test_o_ligado_com_jogo_so_agarra_na_mascara_dualsense(
    montar: Any, modo: str, uniq: str, transporte: str
) -> None:
    """D-2411-COM-JOGO-ABERTO-O-TOQUE-LIGADO-NUNCA-E-O-CURSOR-DO-SISTEMA, recusada: cursor.

    Cada modo, cada peça (cabo e rádio): com jogo aberto e Ligado, o nó só é seguro quando a
    máscara é a DualSense (D-1510-O-JOGO-COM-TOQUE-PROPRIO-E-A-MASCARA-DUALSENSE).
    """
    mesa = montar(modo)
    mesa.conferir()
    if _com_toque_proprio(modo):
        assert mesa.leitor(uniq).grab_state == "held", f"o toque ({transporte}) não foi ao jogo"
        assert mesa.segurados() == set(_UNIQS)
    else:
        assert mesa.leitor(uniq).grabs == [], (
            f"o nó ({transporte}, modo {modo}) foi tomado do sistema: o Ligado não é mais o cursor"
        )
        assert mesa.segurados() == set()
        assert mesa.nenhum_grab_pedido()
    assert REGISTRO.filtrar(uniq, _JANELA) is _JANELA, "o dedo foi zerado antes do jogo"


@pytest.mark.parametrize("modo", _MODOS)
def test_sem_jogo_aberto_o_ligado_e_o_cursor_do_sistema(montar: Any, modo: str) -> None:
    mesa = montar(modo)
    mesa.daemon.fechar_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set()
    assert all(leitor.grabs in ([], [True, False]) for _u, leitor in mesa.criados)


@pytest.mark.parametrize("modo", _MODOS)
def test_o_jogo_que_abre_e_fecha_so_leva_o_no_na_dualsense(montar: Any, modo: str) -> None:
    mesa = montar(modo)
    esperado = set(_UNIQS) if _com_toque_proprio(modo) else set()
    mesa.conferir()
    assert mesa.segurados() == esperado
    mesa.daemon.fechar_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set(), "o jogo fechou e o nó seguiu longe do sistema"
    mesa.daemon.abrir_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == esperado


@pytest.mark.parametrize("modo", _MODOS)
def test_a_janela_do_cliente_da_steam_solta_o_no(montar: Any, modo: str) -> None:
    """D-1510-A-JANELA-DA-STEAM-NAO-TOMA-O-TOQUE: na loja e na biblioteca o cursor é do sistema."""
    mesa = montar(modo)
    mesa.conferir()
    mesa.daemon.focar_a_steam()
    mesa.conferir()
    assert mesa.segurados() == set(), "na loja e na biblioteca o cursor é do sistema"
    mesa.daemon.abrir_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == (set(_UNIQS) if _com_toque_proprio(modo) else set())


@pytest.mark.parametrize("modo", _MODOS)
@pytest.mark.parametrize("uniq", _UNIQS, ids=_IDS_DE_PECA)
def test_o_desligado_agarra_e_cala_em_toda_mascara(montar: Any, modo: str, uniq: str) -> None:
    """D-1510-O-TOUCHPAD-E-POR-CONTROLE: o Desligado é do jogo, em toda máscara, só na peça dele."""
    mesa = montar(modo)
    REGISTRO.definir_touchpad(uniq, ligado=False)
    mesa.conferir()
    assert mesa.leitor(uniq).grab_state == "held", f"o Desligado ficou com o sistema ({modo})"
    outros = set(_UNIQS) - {uniq}
    esperado = set(_UNIQS) if _com_toque_proprio(modo) else {uniq}
    assert mesa.segurados() == esperado
    assert all(REGISTRO.filtrar(u, _JANELA) is _JANELA for u in outros), "o Desligado vazou"
    mesa.daemon.focar_a_steam()
    mesa.conferir()
    assert mesa.segurados() == {uniq}, "o Desligado soltou o nó na janela da Steam"
    mesa.daemon.fechar_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set(), "sem jogo o cursor é do sistema, mesmo no Desligado"


@pytest.mark.parametrize("modo", _MODOS)
@pytest.mark.parametrize("uniq", _UNIQS, ids=_IDS_DE_PECA)
def test_religar_devolve_o_cursor_fora_da_dualsense(montar: Any, modo: str, uniq: str) -> None:
    mesa = montar(modo)
    REGISTRO.definir_touchpad(uniq, ligado=False)
    mesa.conferir()
    assert mesa.leitor(uniq).grab_state == "held"
    REGISTRO.definir_touchpad(uniq, ligado=True)
    mesa.conferir()
    esperado = "held" if _com_toque_proprio(modo) else "off"
    assert mesa.leitor(uniq).grab_state == esperado


@pytest.mark.parametrize("modo", _MODOS)
@pytest.mark.parametrize("uniq", _UNIQS, ids=_IDS_DE_PECA)
def test_com_a_rota_de_cursor_o_no_volta_ao_sistema_quando_a_rota_para(
    montar: Any, modo: str, uniq: str
) -> None:
    """A rota do perfil pede o nó; quando para, só o toque próprio do jogo o mantém."""
    mesa = montar(modo)
    mesa.hub.toque_da_peca(uniq)
    mesa.conferir()
    assert mesa.leitor(uniq).grab_state == "held"
    mesa.relogio.agora += 6.0
    mesa.conferir()
    esperado = "held" if _com_toque_proprio(modo) else "off"
    assert mesa.leitor(uniq).grab_state == esperado, (
        f"a rota parou e o nó ficou no estado errado (modo {modo})"
    )


@pytest.mark.parametrize("modo", _MODOS)
@pytest.mark.parametrize("uniq", _UNIQS, ids=_IDS_DE_PECA)
def test_o_dedo_do_dsu_segura_o_no_e_o_solta_quando_cala(
    montar: Any, modo: str, uniq: str
) -> None:
    mesa = montar(modo)
    mesa.daemon.focar_a_steam()
    mesa.conferir()
    assert mesa.segurados() == set()
    mesa.hub.segurar_o_dedo(uniq)
    mesa.conferir()
    assert mesa.leitor(uniq).grab_state == "held", "o DSU não segurou o nó"
    assert mesa.segurados() == {uniq}
    mesa.relogio.agora += 60.0
    mesa.conferir()
    assert mesa.segurados() == set(), "o DSU calou e o nó seguiu longe do sistema"


@pytest.mark.parametrize("modo", ("xbox", "nintendo", "mouse_e_teclado"))
def test_a_mesa_misturada_fora_da_dualsense_cada_peca_com_o_seu_desfecho(
    montar: Any, modo: str
) -> None:
    """P1 Ligado, P2 Desligado, P3 com rota, P4 Ligado: nenhuma decide pela outra."""
    mesa = montar(modo)
    REGISTRO.definir_touchpad(_UNIQS[1], ligado=False)
    mesa.hub.toque_da_peca(_UNIQS[2])
    mesa.conferir()
    assert mesa.segurados() == {_UNIQS[1], _UNIQS[2]}, (
        "o Ligado sem rota foi tomado do cursor, ou o Desligado e a rota não seguraram"
    )
    assert mesa.leitor(_UNIQS[0]).grabs == [] and mesa.leitor(_UNIQS[3]).grabs == []

    mesa.relogio.agora += 6.0
    mesa.conferir()
    assert mesa.segurados() == {_UNIQS[1]}, "a rota que parou devolve o nó da P3 ao cursor"

    mesa.daemon.focar_a_steam()
    mesa.conferir()
    assert mesa.segurados() == {_UNIQS[1]}

    mesa.daemon.fechar_o_jogo()
    mesa.conferir()
    assert mesa.segurados() == set(), "o Desligado é do jogo: sem jogo, o cursor é do sistema"


def test_a_mesa_misturada_na_dualsense_o_ligado_vai_ao_jogo(montar: Any) -> None:
    mesa = montar("dualsense")
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
    assert mesa.segurados() == set()


@pytest.mark.parametrize("modo", _MODOS)
@pytest.mark.parametrize("uniq", _UNIQS, ids=_IDS_DE_PECA)
def test_o_controle_que_sai_e_volta_segue_a_regra_da_mascara(
    montar: Any, modo: str, uniq: str
) -> None:
    mesa = montar(modo)
    mesa.conferir()
    esperado = set(_UNIQS) if _com_toque_proprio(modo) else set()
    mesa.sair(uniq)
    assert mesa.segurados() == esperado - {uniq}
    mesa.voltar(uniq)
    assert mesa.segurados() == esperado, "voltou e o nó ficou do lado errado"


@pytest.mark.parametrize("modo", _MODOS)
def test_a_pergunta_do_daemon_responde_pela_mascara_e_pela_janela(
    montar: Any, modo: str
) -> None:
    """A pergunta que o hub faz ao handler de verdade: a máscara efetiva e a janela da Steam."""
    mesa = montar(modo)
    perguntar = mesa.hub._toque_proprio_do_jogo
    assert perguntar is not None
    for uniq in _UNIQS:
        assert perguntar(uniq) is _com_toque_proprio(modo)
    mesa.daemon.focar_a_steam()
    assert all(perguntar(u) is False for u in _UNIQS), "a janela da Steam tomou o toque"
