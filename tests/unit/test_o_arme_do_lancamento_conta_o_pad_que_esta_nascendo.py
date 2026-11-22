"""O-ARME-DO-LANCAMENTO-CONTA-O-PAD-QUE-ESTA-NASCENDO-01 (19/11/2026).

No diário de 12/11 a 19/11, seis `launch_arm_mascara_nao_convergiu` com
`perfil_dualsense_vs_vivo_sem_emulacao`: o arme lê o `_snapshot` logo depois do applier, e o
applier que troca a roupa para o pad do P1 e o pede ao fio do nascimento; até o fio entregar,
`gamepad_emulation_enabled` é falso e não há `_gamepad_device`. Agora o pad do P1 em voo conta
como emulação viva, com a máscara e o canal pedidos; o fio que falha o tira da conta.

MORDIDA: sem o ramo do `o_p1_que_nasce` no `_snapshot`, o primeiro caso reprova com
`perfil_xbox_vs_vivo_sem_emulacao`.

22/11/2026: a foto conta também o pad de cada secundário em voo (fila, `_nascendo`,
`_instalando`) e, enquanto a mesa sobe, a promessa `_vpads_previstos`; as três janelas do P1 que
nasce (fila para `_nascendo`, entrega para instalação, pedido velho para o novo) não saem da
conta. A prova cobre dois, três e quatro controles, cabo e rádio, os dois canais e as três
máscaras.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.launch_env as le
from hefesto_dualsense4unix.core.numeros_da_sony import ROUPA_COMUM as ROUPA_DO_COMUM
from hefesto_dualsense4unix.daemon.subsystems import gamepad
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.daemon.subsystems.gamepad import OP1QueNasce
from hefesto_dualsense4unix.integrations import uhid_gamepad, virtual_pad

APPID = 9949958


class _Pedido:
    def __init__(self) -> None:
        self.pronto = False
        self.pad: Any = None
        self.ms: float | None = None
        self.descartado = False

    def descartar(self) -> None:
        self.descartado = True


class _Fio:
    def __init__(self) -> None:
        self.pedidos: list[_Pedido] = []

    def pedir(self, _flavor: Any, **_kw: Any) -> _Pedido:
        pedido = _Pedido()
        self.pedidos.append(pedido)
        return pedido


def _perfil(mascara: str) -> SimpleNamespace:
    return SimpleNamespace(
        name="Jogo",
        mode=SimpleNamespace(kind="gamepad", gamepad_flavor=mascara),
        match=SimpleNamespace(
            window_class=[f"steam_app_{APPID}"], window_title_regex=None, process_name=[],
        ),
    )


def _o_p1_que_nasce(mascara: str) -> OP1QueNasce:
    return OP1QueNasce(
        key=mascara, flavor=mascara, identity=None, mascara_do_p1=mascara, caminho=None,
        caminho_pedido=None, caminho_e_escolha=True, origin="gesto_de_perfil", carta=1,
        kwargs={"allow_uhid": True},
    )


def _mesa(fio: _Fio) -> SimpleNamespace:
    """O P1 de pé em `dualsense`; o applier troca a roupa e pede o pad novo ao fio."""
    daemon = SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=SimpleNamespace(backend="uhid", flavor="dualsense"),
        controller=SimpleNamespace(),
        store=SimpleNamespace(window_detect_current_class=None),
    )
    coop = CoopManager(daemon)
    daemon._coop_manager = coop

    def _applier(mode: Any, *, profile: Any, origin: str) -> bool:
        daemon._gamepad_device = None
        daemon.config.gamepad_emulation_enabled = False
        coop.pedir_o_p1(_o_p1_que_nasce(str(mode.gamepad_flavor)))
        return True

    daemon.apply_profile_mode = _applier
    return daemon


@pytest.fixture
def mesa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[SimpleNamespace, _Fio]:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_permite_uhid", lambda daemon: True)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, _perfil("xbox"))])
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
    fio = _Fio()
    monkeypatch.setattr(virtual_pad, "o_fio_de_nascimento", lambda daemon: fio)
    (tmp_path / "last_run").write_text(f"appid={APPID}\nepoch=1000\npid=1\n", encoding="utf-8")
    return _mesa(fio), fio


def test_o_pad_em_voo_conta_como_emulacao_viva(mesa: tuple[SimpleNamespace, _Fio]) -> None:
    """D-1911-O-ARME-CONTA-O-PAD-QUE-NASCE: o pedido em voo não publica divergência."""
    daemon, fio = mesa
    resultado = le.arm_launch_profile(daemon, base_dir=Path(le.launch_env_dir()), now=1001.0)

    assert fio.pedidos and not fio.pedidos[0].pronto
    assert resultado is not None
    assert resultado["divergente"] is None, resultado
    assert resultado["convergiu"] is True
    assert le.divergencias_publicadas(daemon) == []


def test_o_fio_que_falha_devolve_a_divergencia(
    mesa: tuple[SimpleNamespace, _Fio], monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-1911-O-ARME-CONTA-O-PAD-QUE-NASCE: o pad que não nasce volta a divergir."""
    daemon, fio = mesa
    le.arm_launch_profile(daemon, base_dir=Path(le.launch_env_dir()), now=1001.0)
    instalados: list[Any] = []
    monkeypatch.setattr(
        gamepad, "instalar_o_p1", lambda d, pad, contexto, ms: instalados.append(pad) or "falhou"
    )

    fio.pedidos[0].pronto = True
    daemon._coop_manager._andar_a_fila()
    le.materialize_launch_env(daemon)

    assert instalados == [None]
    assert daemon._coop_manager.o_p1_que_nasce() is None
    motivos = {item["motivo"] for item in le.divergencias_publicadas(daemon)}
    assert motivos == {"perfil_xbox_vs_vivo_sem_emulacao"}


IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"
EDGE = "0x054c/0x0ce6,0x28de/0x11ff"
COMUM_0CE6 = "0x28de/0x11ff"
TRANSPORTES = {
    2: [("usb", "usb"), ("bt", "bt"), ("usb", "bt")],
    3: [("usb",) * 3, ("bt",) * 3, ("usb", "bt", "usb")],
    4: [("usb",) * 4, ("bt",) * 4, ("bt", "usb", "bt", "usb")],
}
CENARIOS = [(n, t) for n, lista in TRANSPORTES.items() for t in lista]
ESTAGIOS = ["p1_no_fio_demais_na_fila", "p1_de_pe_demais_na_fila", "p1_de_pe_um_nascendo"]


class _Controlador:
    def __init__(self, transportes: tuple[str, ...], *, uhid: bool = True) -> None:
        self._transportes = transportes
        if uhid:
            self.hidraw_path = lambda: None

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"connected": True, "transport": t} for t in self._transportes]


def _jogador(i: int) -> SimpleNamespace:
    return SimpleNamespace(
        identity=f"aa:bb:cc:00:00:0{i}", evdev_path=f"/dev/input/event{i}", reader=None,
        player_index=i, vpad=None, cedido_ao_primario=False, externo=False, no_p1=False,
        a_espera=False, motion_reader=None, ralo_do_p1=None,
    )


def _mesa_da_fila(
    transportes: tuple[str, ...], *, mascara: str, estagio: str, canal: str = "uhid",
    coop: bool = True, com_demais: bool = True,
) -> tuple[SimpleNamespace, _Fio]:
    fio = _Fio()
    p1_de_pe = estagio != "p1_no_fio_demais_na_fila"
    daemon = SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(
            gamepad_emulation_enabled=p1_de_pe, gamepad_flavor=mascara, coop_enabled=coop,
        ),
        _gamepad_device=SimpleNamespace(backend=canal, flavor=mascara) if p1_de_pe else None,
        controller=_Controlador(transportes, uhid=canal == "uhid"),
        store=SimpleNamespace(window_detect_current_class=None),
    )
    gerente = CoopManager(daemon)
    daemon._coop_manager = gerente
    if not p1_de_pe:
        gerente.pedir_o_p1(_o_p1_que_nasce(mascara))
    demais = [_jogador(i) for i in range(2, len(transportes) + 1)] if com_demais else []
    for jogador in demais:
        gerente._players[jogador.identity] = jogador  # type: ignore[assignment]
    chaves = tuple(j.identity for j in demais)
    if estagio == "p1_de_pe_um_nascendo" and demais:
        gerente._nascendo = (chaves[0], demais[0], _Pedido())  # type: ignore[assignment]
        chaves = chaves[1:]
    gerente._fila_do_nascimento = (*gerente._fila_do_nascimento, *chaves)
    return daemon, fio


@pytest.fixture
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Fio:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
    fio = _Fio()
    monkeypatch.setattr(virtual_pad, "o_fio_de_nascimento", lambda daemon: fio)
    return fio


def _foto(daemon: SimpleNamespace) -> Any:
    return le._foto_do_lancamento(daemon, no_fio=False, com_as_vozes=False)


def _env_do_padrao(daemon: SimpleNamespace) -> dict[str, str]:
    return le._o_ambiente_padrao(_foto(daemon))[0]


def _env_do_jogo_dualsense(daemon: SimpleNamespace, vestida: tuple[int, str] | None) -> Any:
    foto = _foto(daemon)
    return le.o_ambiente_do_jogo(
        foto, APPID, do_jogo=_perfil("dualsense"), freestyle=None,
        padrao=le._o_ambiente_padrao(foto), receita={}, roupa=lambda: vestida,
    )


@pytest.mark.parametrize("estagio", ESTAGIOS)
@pytest.mark.parametrize(("n", "transportes"), CENARIOS)
def test_o_secundario_em_voo_mantem_o_ignore_na_roupa_edge(
    casa: _Fio, n: int, transportes: tuple[str, ...], estagio: str
) -> None:
    """A foto conta o pad de cada secundário na fila: o IGNORE da roupa Edge fica."""
    daemon, _ = _mesa_da_fila(transportes, mascara="dualsense", estagio=estagio)
    ambiente = _env_do_jogo_dualsense(daemon, None)
    assert ambiente.divergencia is None, ambiente.estado
    assert ambiente.env[IGNORE] == EDGE, ambiente.estado


@pytest.mark.parametrize("estagio", ESTAGIOS)
@pytest.mark.parametrize(("n", "transportes"), CENARIOS)
def test_o_secundario_em_voo_mantem_o_ignore_na_roupa_0ce6(
    casa: _Fio, n: int, transportes: tuple[str, ...], estagio: str
) -> None:
    daemon, _ = _mesa_da_fila(transportes, mascara="dualsense", estagio=estagio)
    ambiente = _env_do_jogo_dualsense(daemon, (ROUPA_DO_COMUM, "arme"))
    assert ambiente.env[IGNORE] == COMUM_0CE6, ambiente.estado


@pytest.mark.parametrize("estagio", ESTAGIOS)
@pytest.mark.parametrize(("n", "transportes"), CENARIOS)
def test_o_secundario_em_voo_mantem_o_ignore_na_mascara_xbox(
    casa: _Fio, n: int, transportes: tuple[str, ...], estagio: str
) -> None:
    daemon, _ = _mesa_da_fila(transportes, mascara="xbox", estagio=estagio, canal="uinput")
    env = _env_do_padrao(daemon)
    assert env["SDL_JOYSTICK_HIDAPI"] == "0"
    assert IGNORE in env


@pytest.mark.parametrize("coop", [True, False])
@pytest.mark.parametrize("canal", ["uhid", "uinput"])
def test_o_canal_do_secundario_em_voo_e_o_pedido(casa: _Fio, canal: str, coop: bool) -> None:
    """Cada pad em voo conta por si, com o canal pedido, com ou sem a promessa da mesa."""
    daemon, _ = _mesa_da_fila(
        ("usb", "bt", "usb"), mascara="dualsense", estagio="p1_de_pe_demais_na_fila",
        canal=canal, coop=coop,
    )
    assert le._snapshot(daemon)[3] == [canal] * 3


@pytest.mark.parametrize("transportes", [("usb", "bt"), ("bt", "bt", "usb"), ("usb",) * 4])
def test_a_mesa_que_sobe_conta_a_promessa_quando_o_controle_ainda_nao_voltou(
    casa: _Fio, transportes: tuple[str, ...]
) -> None:
    """O caso das 21h31: o P1 nasce no fio e os outros físicos ainda não são candidatos."""
    daemon, _ = _mesa_da_fila(
        transportes, mascara="dualsense", estagio="p1_no_fio_demais_na_fila", com_demais=False
    )
    ambiente = _env_do_jogo_dualsense(daemon, None)
    assert ambiente.env[IGNORE] == EDGE, ambiente.estado


def test_com_o_coop_desligado_o_ignore_segue_fora(casa: _Fio) -> None:
    daemon, _ = _mesa_da_fila(
        ("usb", "bt", "usb"), mascara="dualsense", estagio="p1_no_fio_demais_na_fila",
        coop=False, com_demais=False,
    )
    assert IGNORE not in _env_do_jogo_dualsense(daemon, None).env


def test_o_pedido_que_o_fio_descartou_deixa_o_ignore_fora(casa: _Fio) -> None:
    daemon, _ = _mesa_da_fila(
        ("usb", "bt", "usb"), mascara="dualsense", estagio="p1_de_pe_demais_na_fila"
    )
    assert IGNORE in _env_do_jogo_dualsense(daemon, None).env
    daemon._coop_manager._fila_do_nascimento = ()
    assert IGNORE not in _env_do_jogo_dualsense(daemon, None).env


@pytest.mark.parametrize("transportes", [("usb",) * 3, ("bt", "usb", "bt", "usb")])
def test_a_mesa_parada_responde_como_antes(casa: _Fio, transportes: tuple[str, ...]) -> None:
    """Sem pad em voo a foto é a de sempre: nada é prometido, nada é acrescentado."""
    daemon, _ = _mesa_da_fila(transportes, mascara="dualsense", estagio="p1_de_pe_demais_na_fila")
    gerente = daemon._coop_manager
    gerente._fila_do_nascimento = ()
    for jogador in gerente._players.values():
        jogador.vpad = SimpleNamespace(backend="uhid", flavor="dualsense")
    _native, _enabled, _flavor, backends, fisicos = le._snapshot(daemon)
    assert backends == ["uhid"] * len(transportes)
    assert fisicos == len(transportes)
    assert le._o_ambiente_padrao(_foto(daemon))[0] == le.compose_env(
        native_mode=False, emulation_enabled=True, flavor="dualsense",
        backends=backends, fisicos=fisicos,
    )
    gerente._players.popitem()
    assert IGNORE not in le._o_ambiente_padrao(_foto(daemon))[0]


def test_o_arme_inteiro_entrega_o_ignore_com_o_secundario_na_fila(
    mesa: tuple[SimpleNamespace, _Fio], monkeypatch: pytest.MonkeyPatch
) -> None:
    """O `ambiente_do_lancamento` do arme com troca de roupa e dois secundários na fila."""
    daemon, _fio = mesa
    daemon.config.coop_enabled = True
    daemon.controller = _Controlador(("usb", "bt", "bt"))
    gerente = daemon._coop_manager
    for i in (2, 3):
        jogador = _jogador(i)
        gerente._players[jogador.identity] = jogador
        gerente._fila_do_nascimento = (*gerente._fila_do_nascimento, jogador.identity)
    monkeypatch.setattr(le, "_steam_profiles", lambda leitor: [(APPID, _perfil("dualsense"))])
    resposta = le.ambiente_do_lancamento(daemon, APPID)
    assert f"{IGNORE}={EDGE}" in resposta["linhas"], resposta
    assert le.divergencias_publicadas(daemon) == []


class _FioQueFotografa(_Fio):
    def __init__(self, tirar: Any) -> None:
        super().__init__()
        self.fotos: list[Any] = []
        self._tirar = tirar

    def pedir(self, _flavor: Any, **kw: Any) -> _Pedido:
        self.fotos.append(self._tirar())
        return super().pedir(_flavor, **kw)


def test_a_foto_no_meio_da_saida_da_fila_ainda_conta_o_secundario(
    casa: _Fio, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Janela 1: o item sai da fila e o `_nascendo` ainda não existe."""
    daemon, _ = _mesa_da_fila(
        ("usb", "bt", "usb"), mascara="dualsense", estagio="p1_de_pe_demais_na_fila", coop=False
    )
    fio = _FioQueFotografa(lambda: le._snapshot(daemon)[3])
    monkeypatch.setattr(virtual_pad, "o_fio_de_nascimento", lambda d: fio)
    monkeypatch.setattr(CoopManager, "_calibration_pronta", lambda self, chave: (True, None))
    monkeypatch.setattr(
        CoopManager, "_pedido_do_pad", lambda self, jogador, calib: ("dualsense", {})
    )
    daemon._coop_manager._andar_a_fila()
    assert fio.fotos == [["uhid"] * 3]


def test_a_foto_no_pedido_novo_do_p1_ainda_conta_o_p1(
    casa: _Fio, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Janela 3: o pedido velho sai e o novo ainda não entrou."""
    daemon, _ = _mesa_da_fila(
        ("usb", "bt"), mascara="dualsense", estagio="p1_no_fio_demais_na_fila",
        coop=False, com_demais=False,
    )
    gerente = daemon._coop_manager
    velho = gerente._nascendo[2]
    fotos: list[Any] = []
    antigo = type(velho).descartar

    def descartar(self: _Pedido) -> None:
        fotos.append(le._snapshot(daemon)[1:4])
        antigo(self)

    monkeypatch.setattr(type(velho), "descartar", descartar)
    gerente.pedir_o_p1(_o_p1_que_nasce("dualsense"))
    assert fotos
    assert all(foto == (True, "dualsense", ["uhid"]) for foto in fotos), fotos


def test_a_foto_no_meio_da_instalacao_do_p1_conta_o_p1(
    casa: _Fio, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Janela 2: a entrega zera o pedido, e o pad e a emulação ainda não estão postos."""
    daemon, _ = _mesa_da_fila(
        ("usb", "bt"), mascara="dualsense", estagio="p1_no_fio_demais_na_fila",
        coop=False, com_demais=False,
    )
    gerente = daemon._coop_manager
    fotos: list[tuple[bool, str, list[str]]] = []

    def tirar(*_a: Any, **_k: Any) -> None:
        fotos.append(le._snapshot(daemon)[1:4])

    monkeypatch.setattr("hefesto_dualsense4unix.daemon.subsystems.coop.anotar_o_nascimento", tirar)
    monkeypatch.setattr(gamepad, "start_motion_reader", tirar)
    monkeypatch.setattr(gamepad, "_set_controller_grab", lambda *a, **k: None)
    monkeypatch.setattr(gamepad, "_materialize_launch_env", lambda d: None)
    monkeypatch.setattr(gamepad, "_guardar_o_caminho", lambda *a, **k: None)
    pedido = gerente._nascendo[2]
    pedido.pad = SimpleNamespace(backend="uhid", flavor="dualsense")
    pedido.pronto = True
    gerente._andar_a_fila()
    assert fotos == [(True, "dualsense", ["uhid"])] * 2
    assert gerente._p1_que_nasce is None


def test_a_foto_no_meio_da_instalacao_do_secundario_conta_o_secundario(
    casa: _Fio, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Janela 2 do secundário: `_nascendo` já foi zerado e o `vpad` ainda não foi posto."""
    daemon, _ = _mesa_da_fila(
        ("usb", "bt", "usb"), mascara="dualsense", estagio="p1_de_pe_um_nascendo", coop=False
    )
    gerente = daemon._coop_manager
    fotos: list[list[str]] = []

    def instalar(self: CoopManager, jogador: Any, vpad: Any, ms: Any) -> None:
        fotos.append(le._snapshot(daemon)[3])
        jogador.vpad = vpad
        fotos.append(le._snapshot(daemon)[3])

    monkeypatch.setattr(CoopManager, "_instalar_o_pad", instalar)
    monkeypatch.setattr(CoopManager, "_calibration_pronta", lambda self, chave: (True, None))
    monkeypatch.setattr(
        CoopManager, "_pedido_do_pad", lambda self, jogador, calib: ("dualsense", {})
    )
    pedido = gerente._nascendo[2]
    pedido.pad = SimpleNamespace(backend="uhid", flavor="dualsense")
    pedido.pronto = True
    gerente._andar_a_fila()
    assert fotos == [["uhid"] * 3, ["uhid"] * 3]


def test_a_entrega_velha_nao_derruba_o_pedido_novo_do_p1(casa: _Fio) -> None:
    daemon, _ = _mesa_da_fila(
        ("usb",), mascara="dualsense", estagio="p1_no_fio_demais_na_fila"
    )
    gerente = daemon._coop_manager
    novo = gerente._p1_que_nasce
    velho = _Pedido()
    gerente._entregar("<p1>", None, velho)
    assert velho.descartado
    assert gerente._p1_que_nasce is novo
