"""O modo tem um dono, do boot à tela — O-MODO-XBOX-NAO-E-QUEDA-02.

A sessão dela de 27/09 mediu o mesmo defeito por quatro portas: o modo que o
perfil pôs de pé era desfeito por quem só devia RECRIAR o pad. Às 21h07 e às
23h28 o lançamento do PRAGMATA pôs o pad em DualSense, e segundos depois um
restart o devolveu ao Xbox sem que o diário dissesse quem pediu (L2,
`medidas/L2-pragmata/VEREDITO.md`). Cada restart tinha a sua fonte: a foto da
suspensão, o caminho do pad velho, ou nenhuma — e «nenhuma» LIMPAVA o slot, e
o Xbox da sessão voltava DualSense com um clique no cartão.

A cura consolidada (a sprint, «A cura, consolidada para quem implementa»):

1. o caminho vive num lugar só, o slot da sessão (`gamepad.caminho_da_sessao`),
   e todo restart lê dele e diz quem pediu (`p1_reerguido motivo=…`);
   (a) o arquivo da escolha dela guarda a origem, e a migração de 18/09 devolve
   só o valor sem origem.

As réguas fazem o pad nascer pelos métodos REAIS do daemon e do subsistema; só
a borda é dublada (a fábrica publica o que a real publica: a máscara efetiva, o
canal de `quer_uhid` e o caminho pendurado).
"""

from __future__ import annotations

import functools
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.subsystems import coop as coop_mod
from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.utils import session, xdg_paths

#: A faixa sintética da casa — nenhum endereço real em arquivo versionado.
P1 = "aabbcc000001"


class _Vpad:
    """O pad de mentira: publica o que a fábrica real publica."""

    def __init__(self, mascara: str, identity: str | None, caminho: str | None) -> None:
        self.flavor = mascara
        self.identity = identity
        self.backend = "uhid" if vp.quer_uhid(caminho, mascara) else "uinput"
        vp._pendurar_o_caminho(self, vp.caminho_resolvido(caminho, mascara))
        self.parado = False

    def stop(self) -> None:
        self.parado = True


def _fabrica(flavor: Any, *, identity: Any = None, caminho: Any = None, **_kw: Any) -> _Vpad:
    """A fábrica dublada veste a máscara EFETIVA, como a real."""
    return _Vpad(em.mascara_efetiva(identity, flavor), identity, caminho)


def _parar(daemon: Any, *, persist: bool = True, release_grab: bool = True) -> None:
    if daemon._gamepad_device is not None:
        daemon._gamepad_device.stop()
    daemon._gamepad_device = None
    daemon.config.gamepad_emulation_enabled = False


class _Store:
    native_mode_active = False

    def bump(self, *_a: Any, **_k: Any) -> None:
        return None


class _Daemon:
    """Os métodos REAIS do `lifecycle.Daemon`, amarrados a um objeto sem aparelho."""

    def __init__(self) -> None:
        self.config = SimpleNamespace(
            gamepad_flavor="dualsense",
            gamepad_emulation_enabled=False,
            gamepad_caminho=None,
            gamepad_caminho_global=None,
            coop_enabled=True,
            rumble_active=(0, 0),
        )
        self.controller = SimpleNamespace(
            primary_uniq=P1, hidraw_path=lambda uniq=None: None
        )
        self._gamepad_device: Any = None
        self._mouse_device = None
        self._coop_manager: Any = None
        self.store = _Store()
        self._emu_lock = threading.Lock()
        self._native_mode = False
        self._emu_manual_ts = 0.0
        self._mode_from_profile: Any = None
        self._mascara_adiada_por_jogo: Any = None
        self._gamepad_multi_log = ""
        self._last_rebackend_ts = float("-inf")
        self.display_authority = "unknown"
        for nome in (
            "set_gamepad_emulation",
            "set_gamepad_emulation_desfecho",
            "vestir_a_mascara_do_aparelho",
            "aplicar_gamepad_para_multiplos_controles",
            "_log_gamepad_multi",
            "_restore_emulation_from_stash",
            "_esquecer_mascara_adiada",
        ):
            setattr(self, nome, functools.partial(getattr(lifecycle.Daemon, nome), self))

    def set_native_mode(self, enabled: bool, **_kw: Any) -> bool:
        self._native_mode = bool(enabled)
        return True

    def is_native_mode(self) -> bool:
        return self._native_mode

    def contar_controles_fisicos(self) -> int:
        return 2


@pytest.fixture(autouse=True)
def _bancada(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A borda dublada; o registro de máscaras zerado."""
    monkeypatch.setattr(vp, "make_virtual_pad", _fabrica)
    monkeypatch.setattr(gp, "stop_gamepad_emulation", _parar)
    dubles: dict[str, Any] = {
        "_set_controller_grab": lambda d, g: None,
        "_materialize_launch_env": lambda d: None,
        "start_motion_reader": lambda d, dev: None,
        "read_primary_calibration": lambda d: None,
        "make_primary_rumble_sink": lambda d: None,
        "make_primary_replica_sinks": lambda d: {},
        "controller_allows_uhid": lambda d: True,
        "vpad_vivo": lambda dev: True,
        "_deve_promover_backend": lambda *a, **k: False,
    }
    for nome, valor in dubles.items():
        monkeypatch.setattr(gp, nome, valor)
    monkeypatch.setattr(coop_mod, "numero_do_nome_do_primario", lambda d, fallback=1: 1)
    monkeypatch.setattr(
        coop_mod, "get_coop_manager", lambda d: SimpleNamespace(sync=lambda force=False: None)
    )
    monkeypatch.setattr(session, "save_gamepad_emulation", lambda *a, **k: None)
    monkeypatch.setattr(session, "load_gamepad_preference", lambda: (None, None))
    em._zerar_registro_de_mascaras()
    (xdg_paths.config_dir(ensure=True) / "controller_masks.json").unlink(missing_ok=True)
    yield
    em._zerar_registro_de_mascaras()


def _mesa_no_modo_xbox(cartao: str | None = None) -> _Daemon:
    """O perfil pôs o modo Xbox de pé: o pad do P1 no caminho Xbox, o dono em Xbox.

    A máscara do P1 é a DualSense da sessão (ou a do `cartao`): é com ela que
    um start sem opinião volta ao DualSense, e é o caso que morde.
    """
    if cartao is not None:
        em.registro_de_mascaras().set_mask(P1, cartao)
    d = _Daemon()
    desfecho = gp.start_gamepad_emulation_desfecho(d, None, origin="profile", caminho="xbox")
    assert desfecho == gp.EMU_APLICADO, "premissa da bancada"
    assert vp.caminho_do_vpad(d._gamepad_device) == "xbox"
    assert gp.caminho_da_sessao(d) == "xbox"
    return d


# ---------------------------------------------------------------------------
# Item 1 — todo restart lê o dono, e diz quem pediu
# ---------------------------------------------------------------------------


def _pela_ordem_do_coop(d: _Daemon) -> None:
    coop = coop_mod.CoopManager(d)  # type: ignore[arg-type]
    coop._derrubar_para_renascer(coop_mod._CHAVE_DO_P1)
    coop._reerguer_o_p1()


def _pelo_revive(d: _Daemon) -> None:
    _parar(d)
    d.config.gamepad_emulation_enabled = True
    assert gp.upgrade_primary_vpad_to_uhid(d) is True  # type: ignore[arg-type]


def _pela_volta_do_steam_input(d: _Daemon) -> None:
    # A foto da suspensão é de ANTES: um perfil entrou no meio e pôs o Xbox.
    _parar(d)
    d._steam_input_vpad_suspenso = True  # type: ignore[attr-defined]
    d._steam_input_flavor_suspenso = "dualsense"  # type: ignore[attr-defined]
    d._steam_input_caminho_suspenso = "dualsense"  # type: ignore[attr-defined]
    assert gp.resume_vpads_after_steam_input(d) is True  # type: ignore[arg-type]


def _pelo_cartao(d: _Daemon) -> None:
    # O gesto do cartão escolhe MÁSCARA (do Pro de volta ao DualSense); o modo
    # é o do dono.
    em.registro_de_mascaras().set_mask(P1, "dualsense")
    assert d.vestir_a_mascara_do_aparelho(P1) == gp.EMU_APLICADO


def _pela_saida_do_modo_nativo(d: _Daemon) -> None:
    _parar(d)
    d._native_emu_stash = {"gamepad": [True, "dualsense"]}  # type: ignore[attr-defined]
    d._restore_emulation_from_stash()


def _por_dois_controles_na_mesa(d: _Daemon) -> None:
    _parar(d)
    assert d.aplicar_gamepad_para_multiplos_controles() == lifecycle.APLICADO


def _pelo_juiz_das_mascaras(d: _Daemon) -> None:
    em.registro_de_mascaras().set_mask(P1, "dualsense")
    assert gp.reconciliar_as_mascaras(d) == gp.EMU_APLICADO


#: motivo -> (o restart, o cartão do P1 antes dele). Os dois restarts de
#: máscara partem do Pro no cartão, para a troca ao DualSense ser o que recria.
RESTARTS: dict[str, tuple[Any, str | None]] = {
    "ordem_do_coop": (_pela_ordem_do_coop, None),
    "revive_pos_falha_total": (_pelo_revive, None),
    "volta_do_steam_input": (_pela_volta_do_steam_input, None),
    "mascara_do_cartao": (_pelo_cartao, "nintendo"),
    "saida_do_modo_nativo": (_pela_saida_do_modo_nativo, None),
    "dois_controles_na_mesa": (_por_dois_controles_na_mesa, None),
    "mascara_reconciliada": (_pelo_juiz_das_mascaras, "nintendo"),
}


@pytest.mark.parametrize("motivo", sorted(RESTARTS))
def test_todo_restart_renasce_no_modo_do_dono(motivo: str) -> None:
    """Com o modo Xbox de pé, nenhum restart devolve o pad ao DualSense.

    MORDE: tire o `caminho=` do cartão, da saída do Modo Nativo ou dos dois
    controles (o start sem opinião limpa o slot e o pad volta uhid); devolva à
    volta do Steam Input a foto da suspensão; ou à promoção o caminho do pad velho.
    """
    restart, cartao = RESTARTS[motivo]
    d = _mesa_no_modo_xbox(cartao)
    with structlog.testing.capture_logs() as diario:
        restart(d)

    assert d._gamepad_device is not None, "o restart não reergueu o pad"
    assert vp.caminho_do_vpad(d._gamepad_device) == "xbox", (
        f"o restart `{motivo}` escolheu o modo por conta própria: o pad voltou "
        f"{vp.caminho_do_vpad(d._gamepad_device)!r} com o dono em Xbox"
    )
    assert gp.caminho_da_sessao(d) == "xbox", "o restart mexeu no dono"
    assert {"event": "p1_reerguido", "motivo": motivo, "caminho": "xbox"} in [
        {k: r.get(k) for k in ("event", "motivo", "caminho")} for r in diario
    ], (
        "o restart não disse quem pediu: foi o buraco do diário de 27/09"
    )


def test_o_cartao_nao_vira_a_escolha_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    """O gesto do cartão é `manual`, e o modo que ele repassa não é escolha.

    MORDE: tire o `caminho_e_escolha=False` do cartão e o modo da sessão vira
    a escolha dela no arquivo, como se ela tivesse apertado o PS + R3.
    """
    escritos: list[Any] = []
    monkeypatch.setattr(session, "save_gamepad_caminho", lambda *a, **k: escritos.append(a))
    d = _mesa_no_modo_xbox("nintendo")
    _pelo_cartao(d)
    assert escritos == []
    assert d.config.gamepad_caminho_global is None


def test_a_promocao_segue_o_dono_e_nao_o_pad_velho() -> None:
    """O pad degradado renasce no modo do dono (a promoção é um restart)."""
    d = _Daemon()
    d.config.gamepad_emulation_enabled = True
    d.config.gamepad_caminho = "dualsense"
    velho = _Vpad("dualsense", P1, "dualsense")
    velho.backend = "uinput"
    d._gamepad_device = velho
    from hefesto_dualsense4unix.integrations import uhid_gamepad

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(uhid_gamepad, "uhid_available", lambda: True)
        assert gp.upgrade_primary_vpad_to_uhid(d) is True  # type: ignore[arg-type]
    assert d._gamepad_device.backend == "uhid"
    assert vp.caminho_do_vpad(d._gamepad_device) == "dualsense"


# ---------------------------------------------------------------------------
# Item (a) — o arquivo dela guarda a origem, e a migração devolve só o legado
# ---------------------------------------------------------------------------


@pytest.fixture
def _arquivo_do_caminho() -> Iterator[Any]:
    pasta = xdg_paths.config_dir(ensure=True)
    alvo = pasta / "gamepad_caminho.flag"
    marca = pasta / session.MARCA_DO_CAMINHO_DEVOLVIDO
    alvo.unlink(missing_ok=True)
    marca.unlink(missing_ok=True)
    yield alvo
    alvo.unlink(missing_ok=True)
    marca.unlink(missing_ok=True)


class _DaemonDoGesto:
    """O suficiente para o `_guardar_o_caminho` REAL gravar a escolha dela."""

    def __init__(self) -> None:
        self.config = SimpleNamespace(gamepad_caminho=None, gamepad_caminho_global=None)

    def _janela_de_jogo_em_foco(self) -> bool:
        return False


def test_o_gesto_fora_do_jogo_grava_com_a_origem(_arquivo_do_caminho: Any) -> None:
    gp._guardar_o_caminho(_DaemonDoGesto(), "xbox", origin="manual")  # type: ignore[arg-type]

    assert session.load_gamepad_caminho_com_origem() == ("xbox", "gesto_fora_do_jogo")
    assert session.load_gamepad_caminho() == "xbox"


def test_a_escolha_dela_com_origem_sobrevive_aos_boots(_arquivo_do_caminho: Any) -> None:
    """O `xbox` que ela escolheu fora do jogo NÃO é o vazamento de 18/09.

    MORDE: tire da migração a pergunta pela origem e o primeiro boot desfaz a
    escolha dela.
    """
    gp._guardar_o_caminho(_DaemonDoGesto(), "xbox", origin="manual")  # type: ignore[arg-type]

    for _boot in range(2):
        lido = lifecycle._a_escolha_dela_sem_o_vazamento(
            *session.load_gamepad_caminho_com_origem()
        )
        assert lido == "xbox", "o boot desfez o Xbox que ela escolheu"
    assert session.load_gamepad_caminho_com_origem() == ("xbox", "gesto_fora_do_jogo")


def test_o_legado_sem_origem_volta_uma_vez(_arquivo_do_caminho: Any) -> None:
    """O arquivo antigo (só o caminho) é o legado: devolvido uma vez, com a marca."""
    _arquivo_do_caminho.write_text("xbox\n", encoding="utf-8")

    primeiro = lifecycle._a_escolha_dela_sem_o_vazamento(
        *session.load_gamepad_caminho_com_origem()
    )
    assert primeiro == "dualsense"
    assert session.load_gamepad_caminho_com_origem() == ("dualsense", "migracao_unica")

    _arquivo_do_caminho.write_text("xbox\n", encoding="utf-8")
    segundo = lifecycle._a_escolha_dela_sem_o_vazamento(
        *session.load_gamepad_caminho_com_origem()
    )
    assert segundo == "xbox", "a migração rodou duas vezes"


def test_arquivo_ilegivel_e_ninguem_escolheu(_arquivo_do_caminho: Any) -> None:
    _arquivo_do_caminho.write_text("{quebrado", encoding="utf-8")
    assert session.load_gamepad_caminho_com_origem() == (None, None)
