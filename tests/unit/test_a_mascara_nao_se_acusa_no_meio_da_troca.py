"""A máscara não se acusa divergente no meio da troca nem na parada do serviço.

A-MASCARA-NAO-SE-ACUSA-NO-MEIO-DA-TROCA-NEM-NA-PARADA-DO-SERVICO-01 (22/11/2026). Na troca de
modo pela mão o pad troca primeiro e o perfil só se grava na entrega, no fio do perfil; a parada do
serviço desliga a emulação e materializa. A foto tirada nesses instantes comparava o perfil com um
aparelho em trânsito e acusava `mascara_do_perfil_divergente` sem divergência nenhuma. A foto em
trânsito (serviço parando, ou a marca do escritor do modo acesa) não publica nem apaga a divergência
anterior, e a foto assentada que a segue é a que decide.

A primeira parte mede a foto sobre um daemon de mentira; a segunda, o setter do daemon de verdade
(SUBCLASSE do real, como em `test_o_modo_se_grava_onde_ele_muda`), com a foto tirada DENTRO da
derrubada do pad velho e antes da gravação do perfil.

MORDIDAS (cada uma com o md5 do arquivo conferido na volta):
* `em_transito` devolvendo sempre False reprova a parada, o escritor em curso e as duas fotos do
  setter, com `perfil_dualsense_vs_vivo_sem_emulacao` e `perfil_dualsense_vs_vivo_xbox`;
* acender a marca depois da derrubada (no fim do corpo do setter) reprova a foto da janela;
* tirar o `soltar` do corpo de `_gravar_o_modo_no_fio` reprova o escritor que falha;
* acender a marca de `aplicar_o_arranjo_do_desktop` depois do mouse reprova a Navegação.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.launch_env as le
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.profiles import manager
from hefesto_dualsense4unix.interface.pacotes.a01_jogar import _aviso_da_divergencia_de_mascara
from tests.unit import test_o_modo_se_grava_onde_ele_muda as casa
from tests.unit.test_o_modo_se_grava_onde_ele_muda import (
    JANELA_DO_JOGO,
    _chip,
    _daemon,
    _Ensaio,
    _gerente,
    _Handlers,
    _pad_de_pe,
    _perfil,
)

ensaio = casa.ensaio
APPID = 9900480
MATERIALIZAR = le.materialize_launch_env


class _Espiao:
    """O logger do módulo: registra (nível, evento, kwargs)."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, Any]]] = []

    def _r(self, evento: str, **kw: Any) -> None:
        self.eventos.append((evento, kw))

    debug = info = warning = _r

    def nomes(self) -> list[str]:
        return [evento for evento, _ in self.eventos]


def _perfil_de_mentira(mascara: str) -> SimpleNamespace:
    return SimpleNamespace(
        name="Jogo da Régua",
        mode=SimpleNamespace(kind="gamepad", gamepad_flavor=mascara),
        match=SimpleNamespace(
            window_class=[f"steam_app_{APPID}"], window_title_regex=None, process_name=[]
        ),
    )


def _mesa(mascara_viva: str, *, emulacao: bool = True, parando: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=emulacao, gamepad_flavor=mascara_viva),
        _gamepad_device=SimpleNamespace(backend="uhid") if emulacao else None,
        _coop_manager=None,
        controller=SimpleNamespace(),
        store=SimpleNamespace(window_detect_current_class=f"steam_app_{APPID}"),
        _is_stopping=lambda: parando,
    )


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_permite_uhid", lambda daemon: True)
    return tmp_path


def _com_perfil(monkeypatch: pytest.MonkeyPatch, mascara: str) -> None:
    perfis = [(APPID, _perfil_de_mentira(mascara))]
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: perfis)


def _motivos(daemon: Any) -> set[str]:
    return {item["motivo"] for item in le.divergencias_publicadas(daemon)}


def test_a_foto_com_o_servico_parando_nao_publica(
    lar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parando, a emulação desligada: nada publica nem loga; a divergência de antes fica."""
    espiao = _Espiao()
    monkeypatch.setattr(le, "logger", espiao)
    _com_perfil(monkeypatch, "dualsense")
    mesa = _mesa("dualsense", emulacao=False, parando=True)

    MATERIALIZAR(mesa)

    assert _motivos(mesa) == set()
    assert "mascara_do_perfil_divergente" not in espiao.nomes()

    anterior = _mesa("xbox")
    MATERIALIZAR(anterior)
    assert _motivos(anterior) == {"perfil_dualsense_vs_vivo_xbox"}
    anterior.config.gamepad_flavor = "dualsense"
    anterior._is_stopping = lambda: True
    MATERIALIZAR(anterior)
    assert _motivos(anterior) == {"perfil_dualsense_vs_vivo_xbox"}, (
        "a foto em trânsito apagou a divergência anterior"
    )


def test_a_foto_com_o_escritor_em_curso_nao_publica_e_a_assentada_decide(
    lar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O pad já em Xbox e o perfil ainda DualSense: em trânsito não acusa; assentado acusa."""
    espiao = _Espiao()
    monkeypatch.setattr(le, "logger", espiao)
    _com_perfil(monkeypatch, "dualsense")
    mesa = _mesa("xbox")
    marca = le.acender_o_escritor(mesa, "ipc")
    assert marca is not None

    MATERIALIZAR(mesa)
    assert _motivos(mesa) == set()
    assert "mascara_do_perfil_divergente" not in espiao.nomes()

    marca.soltar()
    MATERIALIZAR(mesa)
    assert _motivos(mesa) == {"perfil_dualsense_vs_vivo_xbox"}
    assert espiao.nomes().count("mascara_do_perfil_divergente") == 1
    aviso = _aviso_da_divergencia_de_mascara(
        {"gamepad_emulation": {"mascara_divergente": le.divergencias_publicadas(mesa)[0]}}
    )
    assert aviso is not None and aviso["selo"] == "GAMEPAD"


def test_a_foto_assentada_com_perfil_e_pad_em_xbox_nao_publica(
    lar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _com_perfil(monkeypatch, "xbox")
    mesa = _mesa("xbox")
    marca = le.acender_o_escritor(mesa, "controle")
    assert marca is not None
    MATERIALIZAR(mesa)
    marca.soltar()
    MATERIALIZAR(mesa)
    assert _motivos(mesa) == set()


def test_a_marca_esquece_no_prazo_e_sem_porta_nao_acende() -> None:
    mesa = _mesa("xbox")
    assert le.acender_o_escritor(mesa, False) is None
    marca = le.acender_o_escritor(mesa, "ipc")
    assert marca is not None
    assert le.em_transito(mesa) is True
    assert le.em_transito(mesa, marca.ate + 1.0) is False


def test_a_foto_em_transito_pede_a_assentada_mesmo_com_a_assinatura_igual(
    lar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O clique no chip que já era o do perfil: o pad volta a casar, e a divergência de antes sai.

    A assinatura da mesa do fim é a do carimbo da foto em trânsito; sem o pedido da foto assentada
    o sossego não rematerializaria e a divergência velha ficaria publicada.
    """
    _com_perfil(monkeypatch, "dualsense")
    mesa = _mesa("xbox")
    MATERIALIZAR(mesa)
    assert _motivos(mesa) == {"perfil_dualsense_vs_vivo_xbox"}
    marca = le.acender_o_escritor(mesa, "ipc")
    assert marca is not None
    mesa.config.gamepad_flavor = "dualsense"
    MATERIALIZAR(mesa)
    assert _motivos(mesa) == {"perfil_dualsense_vs_vivo_xbox"}
    prazo = mesa._launch_env_sossego_em
    assert le.rematerializar_se_sossegou(mesa, agora=prazo) is False, (
        "rematerializou com a troca ainda em curso"
    )
    marca.soltar()
    assert le.rematerializar_se_sossegou(mesa, agora=prazo + 1000.0) is True
    assert _motivos(mesa) == set()


def _perfil_do_jogo_ativo(d: Any, mascara: str) -> None:
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria

    _perfil(
        "Jogo da Régua",
        mode={"kind": "gamepad", "caminho": mascara, "gamepad_flavor": mascara},
        match=MatchCriteria(window_class=[JANELA_DO_JOGO]),
    )
    d.store.set_active_profile("Jogo da Régua")
    _pad_de_pe(d, mascara)


def _fotos_da_troca(
    ensaio: _Ensaio, monkeypatch: pytest.MonkeyPatch, lar: Path, d: Any
) -> list[set[str]]:
    """A foto dentro da derrubada do pad velho e dentro do corpo do escritor, antes de gravar."""
    monkeypatch.setattr(le, "materialize_launch_env", MATERIALIZAR)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: _perfis_do_disco(daemon))
    fotos: list[set[str]] = []
    parar = ensaio.parar

    def parar_e_fotografar(daemon: Any, **kw: Any) -> None:
        parar(daemon, **kw)
        MATERIALIZAR(daemon)
        fotos.append(_motivos(daemon))

    monkeypatch.setattr(gp, "stop_gamepad_emulation", parar_e_fotografar)
    corpo = lifecycle._gravar_o_modo_sob_a_trava

    def fotografar_e_gravar(*a: Any, **kw: Any) -> Any:
        MATERIALIZAR(d)
        fotos.append(_motivos(d))
        return corpo(*a, **kw)

    monkeypatch.setattr(lifecycle, "_gravar_o_modo_sob_a_trava", fotografar_e_gravar)
    return fotos


def _perfis_do_disco(daemon: Any) -> list[tuple[int, Any]]:
    from hefesto_dualsense4unix.profiles import loader

    perfil = loader.load_profile("Jogo da Régua")
    return [(APPID, perfil)]


def test_a_troca_pelo_chip_nao_acusa_nem_na_derrubada_nem_antes_da_gravacao(
    ensaio: _Ensaio, lar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O chip do Xbox sobre o perfil DualSense: as duas fotos de dentro da troca não publicam."""
    d = _daemon()
    _perfil_do_jogo_ativo(d, "dualsense")
    h = _Handlers(d, _gerente(d))
    fotos = _fotos_da_troca(ensaio, monkeypatch, lar, d)

    resposta = _chip(h, "xbox")

    assert resposta["status"] == "ok", resposta
    assert len(fotos) == 2, f"as fotos de dentro da troca foram {fotos}"
    assert fotos == [set(), set()], (
        f"a foto em trânsito acusou {fotos}: o pad trocou primeiro e o perfil só grava na entrega"
    )
    assert getattr(d, "_marcas_do_escritor", set()) == set()
    MATERIALIZAR(d)
    assert _motivos(d) == set()


def test_o_escritor_que_falha_apaga_a_marca_e_a_foto_seguinte_publica(
    ensaio: _Ensaio, lar: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A gravação falha: a marca sai, e a divergência que ficou (DualSense contra Xbox) vale."""
    d = _daemon()
    _perfil_do_jogo_ativo(d, "dualsense")
    h = _Handlers(d, _gerente(d))
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: _perfis_do_disco(daemon))

    def falha(*a: Any, **kw: Any) -> Any:
        raise OSError("disco cheio")

    monkeypatch.setattr(manager, "gravar_o_modo_no_perfil_ativo", falha)

    resposta = _chip(h, "xbox")

    assert resposta["status"] == "ok", resposta

    assert getattr(d, "_marcas_do_escritor", set()) == set(), "a marca ficou acesa depois da falha"
    MATERIALIZAR(d)
    assert _motivos(d) == {"perfil_dualsense_vs_vivo_xbox"}


def test_o_pedido_que_o_aparelho_recusou_nao_deixa_marca(
    ensaio: _Ensaio, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = _daemon()
    _perfil_do_jogo_ativo(d, "dualsense")
    h = _Handlers(d, _gerente(d))
    ensaio.fabrica_recusa = True

    resposta = _chip(h, "xbox")

    assert resposta["status"] == "failed", resposta
    assert getattr(d, "_marcas_do_escritor", set()) == set()


def test_o_nativo_com_a_porta_acende_e_solta_a_marca(
    ensaio: _Ensaio, monkeypatch: pytest.MonkeyPatch
) -> None:
    d = _daemon()
    _perfil_do_jogo_ativo(d, "dualsense")
    vistas: list[bool] = []
    corpo = lifecycle._gravar_o_modo_sob_a_trava

    def espiar(*a: Any, **kw: Any) -> Any:
        vistas.append(le.em_transito(d))
        return corpo(*a, **kw)

    monkeypatch.setattr(lifecycle, "_gravar_o_modo_sob_a_trava", espiar)

    d.set_native_mode(True, origin="manual", grava_o_modo="ipc")
    _pelo_ipc_vazio()

    assert vistas == [True]
    assert getattr(d, "_marcas_do_escritor", set()) == set()


def _pelo_ipc_vazio() -> None:
    import asyncio

    from hefesto_dualsense4unix.daemon.ipc_server import _o_perfil_em_dia

    asyncio.run(_o_perfil_em_dia())


def test_a_navegacao_com_a_porta_acende_a_marca_antes_do_mouse_e_a_solta_na_gravacao(
    ensaio: _Ensaio, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O terceiro modo: a Navegação pela mão derruba o pad pelo mouse, com a marca já acesa."""
    d = _daemon()
    _perfil_do_jogo_ativo(d, "dualsense")
    no_mouse: list[bool] = []
    na_gravacao: list[bool] = []
    mouse = d.set_mouse_emulation

    def espiar_o_mouse(*a: Any, **kw: Any) -> bool:
        no_mouse.append(le.em_transito(d))
        return mouse(*a, **kw)

    corpo = lifecycle._gravar_o_modo_sob_a_trava

    def espiar_a_gravacao(*a: Any, **kw: Any) -> Any:
        na_gravacao.append(le.em_transito(d))
        return corpo(*a, **kw)

    monkeypatch.setattr(d, "set_mouse_emulation", espiar_o_mouse)
    monkeypatch.setattr(lifecycle, "_gravar_o_modo_sob_a_trava", espiar_a_gravacao)
    h = _Handlers(d, _gerente(d))

    casa._pelo_ipc(h._handle_desktop_arranjo_apply({"origin": "manual"}))

    assert no_mouse == [True], "o pad caiu pelo mouse antes de a marca acender"
    assert na_gravacao == [True]
    assert getattr(d, "_marcas_do_escritor", set()) == set()


@pytest.mark.parametrize("fisicos", [2, 3, 4])
@pytest.mark.parametrize(
    "transportes", [("usb",), ("bt",), ("usb", "bt")], ids=["cabo", "rádio", "misturada"]
)
def test_a_mesa_de_varios_controles_em_transito_nao_publica_e_a_assentada_decide(
    lar: Path, monkeypatch: pytest.MonkeyPatch, fisicos: int, transportes: tuple[str, ...]
) -> None:
    """A foto é do modo único: com dois, três e quatro controles, no cabo e no rádio, vale igual."""
    _com_perfil(monkeypatch, "dualsense")
    mesa = _mesa("xbox")
    mesa._coop_manager = SimpleNamespace(_players={
        f"p{i}": SimpleNamespace(vpad=SimpleNamespace(backend="uhid"))
        for i in range(2, fisicos + 1)
    })
    mesa.controller = SimpleNamespace(describe_controllers=lambda: [
        {"connected": True, "transport": transportes[i % len(transportes)]} for i in range(fisicos)
    ])
    marca = le.acender_o_escritor(mesa, "controle")
    assert marca is not None

    MATERIALIZAR(mesa)
    assert _motivos(mesa) == set()
    mesa._is_stopping = lambda: True
    marca.soltar()
    mesa.config.gamepad_emulation_enabled = False
    mesa._gamepad_device = None
    MATERIALIZAR(mesa)
    assert _motivos(mesa) == set()

    mesa._is_stopping = lambda: False
    mesa.config.gamepad_emulation_enabled = True
    mesa._gamepad_device = SimpleNamespace(backend="uhid")
    MATERIALIZAR(mesa)
    assert _motivos(mesa) == {"perfil_dualsense_vs_vivo_xbox"}
