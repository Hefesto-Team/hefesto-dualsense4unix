"""O-P1-PEDIDO-DE-NOVO-NASCE-NA-FRENTE-DOS-OUTROS-CONTROLES-01 (22/11/2026).

O P1 pedido duas vezes no mesmo lançamento, com o secundário entrando na fila entre os dois
pedidos: o pedido igual (o mesmo pad, motivos diferentes) se junta ao que nasce, e o pedido de
outro pad entra na frente da fila, de modo que a entrega é P1, P2, P3, na ordem das cartas.

O `start_gamepad_emulation_desfecho` e o `CoopManager` são os reais; o fio de nascimento é de
mentira e a entrega é solta à mão, um pad por vez. Nenhum endereço real: faixa forjada
``aa:bb:cc`` com os octetos 4 e 5 zerados.

MORDIDAS: `mesmo_pedido` voltando a comparar os motivos reprova o primeiro caso (dois pads de
P1); o `(*fila, _CHAVE_DO_P1)` de volta reprova o segundo (P2, P3, P1).
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.integrations import virtual_pad

MASCARAS = ["dualsense", "xbox", "nintendo"]
CAMINHOS = {"dualsense": "dualsense", "xbox": "xbox", "nintendo": "xbox"}


class _Pedido:
    def __init__(self, identity: str | None, key: Any) -> None:
        self.identity = identity
        self.key = key
        self.pronto = False
        self.pad: Any = None
        self.ms: float | None = None
        self.descartado = False

    def descartar(self) -> None:
        self.descartado = True


class _Fio:
    def __init__(self) -> None:
        self.pedidos: list[_Pedido] = []

    def pedir(self, flavor: Any, *, identity: Any = None, **_kw: Any) -> _Pedido:
        pedido = _Pedido(identity, flavor)
        self.pedidos.append(pedido)
        return pedido

    def do_p1(self) -> list[_Pedido]:
        return [p for p in self.pedidos if p.identity is None]


def _jogador(i: int) -> SimpleNamespace:
    return SimpleNamespace(
        identity=f"aa:bb:cc:00:00:0{i}", evdev_path=f"/dev/input/event{i}", reader=None,
        player_index=i, vpad=None, cedido_ao_primario=False, externo=False, no_p1=False,
        a_espera=False, motion_reader=None, ralo_do_p1=None,
    )


class _Mesa:
    def __init__(self, daemon: Any, gerente: CoopManager, fio: _Fio, ordem: list[str]) -> None:
        self.daemon = daemon
        self.gerente = gerente
        self.fio = fio
        self.ordem = ordem

    def pedir_o_p1(self, flavor: str | None, **kw: Any) -> str:
        kw.setdefault("origin", "profile")
        return gp.start_gamepad_emulation_desfecho(self.daemon, flavor, **kw)

    def sentar(self, i: int) -> SimpleNamespace:
        jogador = _jogador(i)
        self.gerente._players[jogador.identity] = jogador  # type: ignore[assignment]
        self.gerente._promote_player(jogador)  # type: ignore[arg-type]
        return jogador

    def entregar_tudo(self) -> list[str]:
        for _ in range(20):
            nascendo = self.gerente._nascendo
            if nascendo is None:
                break
            nascendo[2].pad = SimpleNamespace(backend="uhid", flavor="dualsense")
            nascendo[2].pronto = True
            self.gerente._andar_a_fila()
        return self.ordem


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> _Mesa:
    fio = _Fio()
    ordem: list[str] = []
    daemon = SimpleNamespace(
        config=SimpleNamespace(
            gamepad_emulation_enabled=False, gamepad_flavor="dualsense", gamepad_caminho=None,
            gamepad_caminho_global=None, coop_enabled=True,
        ),
        _gamepad_device=None, controller=SimpleNamespace(), roupa_do_pad=None,
        store=SimpleNamespace(window_detect_current_class=None),
    )
    gerente = CoopManager(daemon)
    daemon._coop_manager = gerente
    monkeypatch.setattr(virtual_pad, "o_fio_de_nascimento", lambda d: fio)
    monkeypatch.setattr(gp, "o_p1_nasce_pelo_fio", lambda d, no_tique=False: True)
    monkeypatch.setattr(gp, "controller_allows_uhid", lambda d: True)
    monkeypatch.setattr(gp, "a_identidade_do_p1_que_nasce", lambda d: None)
    monkeypatch.setattr(gp, "numero_do_nome_do_primario", lambda d: 1, raising=False)
    monkeypatch.setattr(gp, "make_primary_rumble_sink", lambda d: None)
    monkeypatch.setattr(gp, "make_primary_replica_sinks", lambda d: {})
    monkeypatch.setattr(gp, "read_primary_calibration", lambda d: None)
    monkeypatch.setattr(gp, "_ha_jogo_em_foco", lambda d: False)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.coop.numero_do_nome_do_primario", lambda d: 1
    )

    def _instalar_p1(d: Any, device: Any, contexto: Any, ms: Any) -> str:
        ordem.append("P1")
        contexto.desfecho = gp.EMU_APLICADO
        for passo in contexto.depois:
            passo(contexto.desfecho)
        return gp.EMU_APLICADO

    def _instalar_pad(self: CoopManager, jogador: Any, vpad: Any, ms: Any) -> None:
        ordem.append(jogador.identity[-2:])
        jogador.vpad = vpad

    monkeypatch.setattr(gp, "instalar_o_p1", _instalar_p1)
    monkeypatch.setattr(CoopManager, "_instalar_o_pad", _instalar_pad)
    monkeypatch.setattr(CoopManager, "_acompanhar_o_p1", lambda self: None)
    monkeypatch.setattr(CoopManager, "_calibration_pronta", lambda self, chave: (True, None))
    monkeypatch.setattr(
        CoopManager, "_pedido_do_pad", lambda self, jogador, calib: ("dualsense", {})
    )
    return _Mesa(daemon, gerente, fio, ordem)


@pytest.mark.parametrize("secundarios", [1, 2, 3])
@pytest.mark.parametrize("mascara", MASCARAS)
def test_o_pedido_igual_com_outros_motivos_se_junta_e_a_ordem_e_a_das_cartas(
    mesa: _Mesa, mascara: str, secundarios: int
) -> None:
    """O pedido da troca de roupa (sem máscara) e o do applier (com máscara): um pad de P1 só."""
    mesa.daemon.config.gamepad_flavor = mascara
    mesa.pedir_o_p1(None, caminho=None, caminho_e_escolha=False)
    for i in range(2, secundarios + 2):
        mesa.sentar(i)
    resposta = mesa.pedir_o_p1(mascara, caminho=CAMINHOS[mascara], caminho_e_escolha=True)

    assert resposta == gp.EMU_APLICADO
    assert len(mesa.fio.do_p1()) == 1, [p.descartado for p in mesa.fio.do_p1()]
    assert not mesa.fio.do_p1()[0].descartado
    assert mesa.entregar_tudo() == ["P1", *(f"0{i}" for i in range(2, secundarios + 2))]


@pytest.mark.parametrize("secundarios", [1, 2, 3])
@pytest.mark.parametrize(("antes", "depois"), [("xbox", "dualsense"), ("dualsense", "xbox")])
def test_o_pedido_de_outro_pad_entra_na_frente_dos_secundarios(
    mesa: _Mesa, antes: str, depois: str, secundarios: int
) -> None:
    """D-2211-O-P1-PEDIDO-DE-NOVO-SE-JUNTA-PELO-PAD-E-NASCE-NA-FRENTE.

    O primeiro P1 é descartado, o P2 a P4 esperam, e o P1 novo nasce antes deles."""
    mesa.daemon.config.gamepad_flavor = antes
    mesa.pedir_o_p1(None, caminho=None, caminho_e_escolha=False)
    for i in range(2, secundarios + 2):
        mesa.sentar(i)
    mesa.pedir_o_p1(depois, caminho=CAMINHOS[depois], caminho_e_escolha=True)

    primeiro, novo = mesa.fio.do_p1()
    assert primeiro.descartado and not novo.descartado
    assert mesa.entregar_tudo() == ["P1", *(f"0{i}" for i in range(2, secundarios + 2))]


@pytest.mark.parametrize("muda", ["roupa", "identidade"])
def test_a_mesma_mascara_com_outra_roupa_ou_outro_dono_nao_se_junta(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch, muda: str
) -> None:
    """O arme das 18h07: `dualsense` com a roupa `0df2` e depois com a `0ce6` são dois pads."""
    agora = {"roupa": 0x0DF2, "identidade": None}
    monkeypatch.setattr(gp, "a_roupa_que_o_pad_veste", lambda d: agora["roupa"])
    monkeypatch.setattr(gp, "a_identidade_do_p1_que_nasce", lambda d: agora["identidade"])
    mesa.pedir_o_p1("dualsense", caminho="dualsense", caminho_e_escolha=True)
    mesa.sentar(2)
    if muda == "roupa":
        agora["roupa"] = 0x0CE6
    else:
        agora["identidade"] = "aa:bb:cc:00:00:01"
    mesa.pedir_o_p1("dualsense", caminho="dualsense", caminho_e_escolha=True)

    do_p1 = [p for p in mesa.fio.pedidos if p.identity in (None, "aa:bb:cc:00:00:01")]
    primeiro, novo = do_p1
    assert primeiro.descartado and not novo.descartado
    assert mesa.entregar_tudo() == ["P1", "02"]


def test_o_gesto_manual_que_se_junta_ao_pedido_do_perfil_grava_uma_vez(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    gravados: list[Any] = []
    from hefesto_dualsense4unix.utils import session

    monkeypatch.setattr(session, "save_gamepad_emulation", lambda *a, **k: gravados.append(a))
    mesa.pedir_o_p1(None, origin="profile", caminho=None, caminho_e_escolha=False)
    mesa.sentar(2)
    mesa.pedir_o_p1("dualsense", origin="manual", caminho="dualsense", caminho_e_escolha=True)

    contexto = gp.o_p1_que_nasce(mesa.daemon)
    assert contexto is not None
    assert contexto.caminho_e_escolha and contexto.origin == "manual"
    assert len(mesa.fio.do_p1()) == 1 and not mesa.fio.do_p1()[0].descartado
    mesa.entregar_tudo()
    assert gravados == [(True, "dualsense")]


def test_o_gesto_manual_repetido_nao_grava_duas_vezes(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch
) -> None:
    gravados: list[Any] = []
    from hefesto_dualsense4unix.utils import session

    monkeypatch.setattr(session, "save_gamepad_emulation", lambda *a, **k: gravados.append(a))
    mesa.pedir_o_p1("dualsense", origin="manual", caminho="dualsense", caminho_e_escolha=True)
    mesa.pedir_o_p1("dualsense", origin="manual", caminho="dualsense", caminho_e_escolha=True)
    mesa.entregar_tudo()
    assert gravados == [(True, "dualsense")]


@pytest.mark.parametrize("secundarios", [1, 2, 3])
def test_com_o_p1_entregue_o_pedido_novo_recria_so_o_p1(
    mesa: _Mesa, monkeypatch: pytest.MonkeyPatch, secundarios: int
) -> None:
    """P2 a P4 já têm o `vpad`: nenhum entra na fila, ninguém passa para trás."""
    pads = {}
    for i in range(2, secundarios + 2):
        jogador = _jogador(i)
        jogador.vpad = SimpleNamespace(backend="uhid", flavor="dualsense")
        mesa.gerente._players[jogador.identity] = jogador  # type: ignore[assignment]
        pads[jogador.identity] = jogador.vpad
    mesa.daemon._gamepad_device = SimpleNamespace(backend="uhid", flavor="dualsense")
    mesa.daemon.config.gamepad_emulation_enabled = True

    def _parar(d: Any, *, persist: bool = True, release_grab: bool = True) -> None:
        gp._largar_o_p1_que_nasce(d)
        d._gamepad_device = None

    monkeypatch.setattr(gp, "stop_gamepad_emulation", _parar)
    monkeypatch.setattr(gp, "vpad_vivo", lambda pad: True)
    monkeypatch.setattr(gp, "_recriacao_bloqueada_por_jogo", lambda *a, **k: False)
    monkeypatch.setattr(gp, "a_roupa_que_o_pad_veste", lambda d: 0)
    mesa.pedir_o_p1("xbox", caminho="xbox", caminho_e_escolha=True)

    assert mesa.gerente._fila_do_nascimento == ()
    assert [p.identity for p in mesa.fio.pedidos] == [None]
    assert {j.identity: j.vpad for j in mesa.gerente._players.values()} == pads
    assert mesa.entregar_tudo() == ["P1"]


def test_o_secundario_que_ja_nasce_termina_e_o_p1_novo_vem_antes_dos_que_esperam(
    mesa: _Mesa,
) -> None:
    """O pad que o fio já constrói não se tira; o P1 novo passa à frente de quem ainda espera."""
    mesa.daemon.config.gamepad_flavor = "xbox"
    mesa.sentar(2)
    mesa.sentar(3)
    mesa.sentar(4)
    assert mesa.gerente._nascendo is not None
    mesa.pedir_o_p1("dualsense", caminho="dualsense", caminho_e_escolha=True)

    assert mesa.entregar_tudo() == ["02", "P1", "03", "04"]
