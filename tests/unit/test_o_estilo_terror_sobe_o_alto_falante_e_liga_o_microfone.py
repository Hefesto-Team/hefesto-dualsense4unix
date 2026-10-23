"""O Terror duplica o som do PC no controle e abre o microfone, no Modo automático da aba Controles.

O-ESTILO-TERROR-SOBE-O-ALTO-FALANTE-E-LIGA-O-MICROFONE-NO-AUTOMATICO-01. Dublê do backend e das
pontes do daemon; o fone, o áudio do jogo e a abertura do microfone são o que o daemon responderia.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.ds_output_report import SAIDA_SO_NO_ALTO_FALANTE
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import estilos_de_jogo
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE, Receita
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import (
    VOLUME_DO_PADRAO,
    PontesDoSom,
    ProfileManager,
    gerente_do_daemon,
    pontes_do_som_do_daemon,
)
from hefesto_dualsense4unix.profiles.schema import MODO_AUTOMATICO, MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController

# a faixa forjada das fixtures (nunca endereço real mascarado)
QUATRO = ["aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04"]


class Mesa:
    """As pontes do daemon, com o que cada uma responderia e o que cada uma recebeu."""

    def __init__(
        self,
        conectados: list[str] | None = None,
        *,
        fones: set[str] | None = None,
        jogo: set[str] | None = None,
    ) -> None:
        self.conectados = list(QUATRO if conectados is None else conectados)
        self.fones = fones or set()
        self.jogo = jogo or set()
        self.fontes: list[tuple[str, str]] = []
        self.abertos: list[str] = []
        self.memoria: dict[str, str] = {}

    def pontes(self) -> PontesDoSom:
        def escolher(uniq: str, fonte: str) -> bool:
            self.fontes.append((uniq, fonte))
            return True

        def abrir(uniq: str) -> bool:
            self.abertos.append(uniq)
            return True

        return PontesDoSom(
            conectados=lambda: list(self.conectados),
            fone=lambda uniq: uniq in self.fones,
            jogo_no_alto_falante=lambda uniq: uniq in self.jogo,
            escolher_a_fonte=escolher,
            abrir_o_microfone=abrir,
            do_estilo=self.memoria,
        )


class Gerente:
    """O gerente com o backend de mentira e os appliers que CONTAM o que recebem."""

    def __init__(self, mesa: Mesa) -> None:
        self.mesa = mesa
        self.controle = FakeController()
        self.som: list[dict[str, Any]] = []
        self.mic: list[dict[str, Any]] = []
        self.manager = ProfileManager(
            controller=self.controle,
            store=StateStore(),
            speaker_applier=self._speaker,
            mic_applier=self._mic,
            som_do_estilo=mesa.pontes(),
        )

    def _speaker(
        self, volume: int, muted: bool, *, uniq: str | None = None,
        origin: str = "manual", rota: int | None = None,
    ) -> bool:
        self.som.append({"volume": volume, "muted": muted, "uniq": uniq, "rota": rota})
        return True

    def _mic(self, volume: int | None, muted: bool | None, *, uniq: str | None = None,
             origin: str = "manual") -> bool:
        self.mic.append({"volume": volume, "muted": muted, "uniq": uniq})
        return True

    def aplicar(self, perfil: Profile, **kw: Any) -> dict[str, str]:
        return self.manager.apply_som_do_estilo(perfil, **kw)


def _perfil(estilo: str | None, modo: str | None = MODO_AUTOMATICO, **kw: Any) -> Profile:
    return Profile(name="terror-de-teste", match=MatchAny(), estilo=estilo,
                   controles_modo=modo, **kw)  # type: ignore[arg-type]


@pytest.fixture
def perfis_no_disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / "profiles"
    pasta.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: pasta)
    return pasta


def test_a_receita_do_terror_usa_o_padrao_da_aba_audio_sem_numero_novo() -> None:
    af = POR_CHAVE["terror"].receita_invisivel.alto_falante  # type: ignore[union-attr]
    assert af is not None
    assert (af.fonte, af.rota, af.nivel_padrao) == ("mix", SAIDA_SO_NO_ALTO_FALANTE, True)
    assert POR_CHAVE["terror"].receita_invisivel.microfone_ligado is True  # type: ignore[union-attr]


def test_terror_no_automatico_duplica_e_abre_nos_quatro_controles() -> None:
    mesa = Mesa()
    g = Gerente(mesa)
    relatorio = g.aplicar(_perfil("terror"))
    assert [e["uniq"] for e in g.som] == QUATRO
    assert all(
        e["volume"] == VOLUME_DO_PADRAO and e["rota"] == SAIDA_SO_NO_ALTO_FALANTE
        and e["muted"] is False for e in g.som
    )
    assert mesa.fontes == [(u, "mix") for u in QUATRO]
    assert mesa.abertos == QUATRO
    assert all(relatorio[f"som_estilo:{u}"] == "aplicado" for u in QUATRO)
    assert all(relatorio[f"mic_estilo:{u}"] == "pedido" for u in QUATRO)


def test_com_fone_o_microfone_abre_igual_e_a_rota_que_duplica_nao_e_escrita() -> None:
    mesa = Mesa(fones={QUATRO[1]})
    g = Gerente(mesa)
    relatorio = g.aplicar(_perfil("terror"))
    assert mesa.abertos == QUATRO
    assert [e["uniq"] for e in g.som] == [QUATRO[0], QUATRO[2], QUATRO[3]]
    assert (QUATRO[1], "mix") not in mesa.fontes
    assert relatorio[f"som_estilo:{QUATRO[1]}"] == "ignorado_com_fone"


def test_o_fone_sozinho_nao_decide_se_o_microfone_abre() -> None:
    mesa = Mesa(fones=set(QUATRO))
    g = Gerente(mesa)
    g.aplicar(_perfil("terror"))
    assert g.som == []
    assert mesa.abertos == QUATRO


def test_o_jogo_que_ja_fala_no_alto_falante_nao_leva_a_duplicacao_por_cima() -> None:
    mesa = Mesa(jogo={QUATRO[0]})
    g = Gerente(mesa)
    relatorio = g.aplicar(_perfil("terror"))
    assert QUATRO[0] not in [e["uniq"] for e in g.som]
    assert (QUATRO[0], "mix") not in mesa.fontes
    assert relatorio[f"som_estilo:{QUATRO[0]}"] == "ignorado_o_jogo_manda"
    assert mesa.abertos == QUATRO


@pytest.mark.parametrize("modo", ["personalizado", None])
def test_fora_do_automatico_vale_a_aba_e_nada_se_escreve(modo: str | None) -> None:
    mesa = Mesa()
    g = Gerente(mesa)
    assert g.aplicar(_perfil("terror", modo)) == {}
    assert g.som == [] and g.mic == [] and mesa.fontes == [] and mesa.abertos == []


def test_sem_as_pontes_do_daemon_o_estilo_nao_escreve_som() -> None:
    g = Gerente(Mesa())
    g.manager.som_do_estilo = None
    assert g.aplicar(_perfil("terror")) == {}
    assert g.som == []


def test_os_outros_estilos_com_receita_nao_opinam_no_microfone() -> None:
    com_receita = [e for e in estilos_de_jogo.ESTILOS if e.receita_invisivel is not None]
    outros = [e for e in com_receita if e.chave != "terror"]
    assert len(outros) == 16
    for e in outros:
        assert e.receita_invisivel.microfone_ligado is None, e.chave  # type: ignore[union-attr]
        mesa = Mesa()
        g = Gerente(mesa)
        g.aplicar(_perfil(e.chave))
        assert mesa.abertos == [] and g.mic == [], e.chave


def test_o_terror_nao_enfraquece_a_vibracao_nem_o_gatilho_com_o_microfone_aberto() -> None:
    terror = POR_CHAVE["terror"]
    assert terror.vibracao == "max"
    mesa = Mesa()
    g = Gerente(mesa)
    g.aplicar(_perfil("terror"))
    assert mesa.abertos == QUATRO
    assert g.controle.commands == []
    assert terror.vibracao == "max"
    assert terror.receita_invisivel.duracao_da_vibracao_ms == (  # type: ignore[union-attr]
        2 * estilos_de_jogo.DURACAO_DE_SEMPRE_MS)


def test_o_mudo_do_controle_segue_dele() -> None:
    from hefesto_dualsense4unix.profiles.schema import ProfileSpeakerConfig

    g = Gerente(Mesa())
    g.aplicar(_perfil("terror", speaker=ProfileSpeakerConfig(volume=10, muted=True)))
    assert g.som and all(e["muted"] is True for e in g.som)


def test_a_trava_manual_de_audio_nao_existe_mais_e_o_estilo_entra() -> None:
    """D-1409: não há mais categoria `audio` que vete o perfil; o automático liga o estilo."""
    assert not hasattr(StateStore, "mark_manual_trigger_active")
    mesa = Mesa()
    g = Gerente(mesa)
    g.aplicar(_perfil("terror"))
    assert [e["uniq"] for e in g.som] == QUATRO


def test_ao_trocar_para_outro_estilo_a_fonte_do_terror_volta_ao_padrao_da_casa() -> None:
    mesa = Mesa()
    g = Gerente(mesa)
    g.aplicar(_perfil("terror"))
    assert mesa.memoria == {u: "mix" for u in QUATRO}
    mesa.fontes.clear()
    relatorio = g.aplicar(_perfil("fps"))
    assert mesa.fontes == [(u, "sfx") for u in QUATRO]
    assert mesa.memoria == {}
    assert relatorio[f"som_estilo:{QUATRO[0]}"] == "devolvido"
    mesa.fontes.clear()
    g.aplicar(_perfil("fps"))
    assert mesa.fontes == []


def test_ao_voltar_ao_personalizado_a_fonte_do_terror_tambem_volta() -> None:
    mesa = Mesa()
    g = Gerente(mesa)
    g.aplicar(_perfil("terror"))
    mesa.fontes.clear()
    g.aplicar(_perfil("terror", "personalizado"))
    assert mesa.fontes == [(u, "sfx") for u in QUATRO]


def test_o_replug_devolve_o_som_do_estilo_so_ao_controle_que_voltou(
    perfis_no_disco: Path,
) -> None:
    save_profile(_perfil("terror"))
    mesa = Mesa()
    g = Gerente(mesa)
    g.manager.store.set_active_profile("terror-de-teste")
    estado = g.manager.reapply_speaker_on_connect(QUATRO[2])
    assert estado == "aplicado"
    assert [e["uniq"] for e in g.som] == [QUATRO[2]]
    assert mesa.fontes == [(QUATRO[2], "mix")]
    assert mesa.abertos == []  # o microfone nasce no (re)connect, que já roda ali


def test_perfil_sem_estilo_e_sem_secao_nao_escreve_no_replug(perfis_no_disco: Path) -> None:
    save_profile(_perfil(None))
    g = Gerente(Mesa())
    g.manager.store.set_active_profile("terror-de-teste")
    assert g.manager.reapply_speaker_on_connect(QUATRO[0]) is None
    assert g.som == []


def test_a_ativacao_inteira_leva_o_som_do_estilo(perfis_no_disco: Path) -> None:
    save_profile(_perfil("terror"))
    mesa = Mesa()
    g = Gerente(mesa)
    relatorio: dict[str, str] = {}
    g.manager.activate("terror-de-teste", relatorio=relatorio)
    assert [e["uniq"] for e in g.som] == QUATRO
    assert mesa.abertos == QUATRO
    assert relatorio[f"som_estilo:{QUATRO[3]}"] == "aplicado"


# --- as pontes de verdade, sobre um daemon de mentira ---------------------


class _PadVirtual:
    def __init__(self, fone: bool, ha_s: float | None) -> None:
        self.jack = {"fone": fone, "microfone": False, "mudo": False}
        self.visto_ha_s = {} if ha_s is None else {"audio_do_jogo": ha_s}
        self.game_open = False


def _daemon(pad: _PadVirtual | None, uniq: str = QUATRO[0]) -> Any:
    sub = SimpleNamespace(vivas={})
    sub.escolher_a_fonte = lambda u, f: sub.vivas.__setitem__(u, f) is None
    controller = SimpleNamespace(
        primary_uniq=uniq, alvos_conectados=lambda: {"k0": uniq, "k1": None})
    return SimpleNamespace(
        controller=controller, _gamepad_device=pad, _last_state=None,
        _coop_manager=None, _alto_falante_subsystem=sub, bus=SimpleNamespace(_loop=None))


def test_a_ponte_le_o_fone_e_o_audio_do_jogo_no_pad_virtual() -> None:
    pontes = pontes_do_som_do_daemon(_daemon(_PadVirtual(True, 1.0)))
    assert pontes is not None
    assert pontes.conectados() == [QUATRO[0]]
    assert pontes.fone(QUATRO[0]) is True
    assert pontes.jogo_no_alto_falante(QUATRO[0]) is True


def test_a_ponte_sem_pad_virtual_diz_que_nao_sabe_e_o_jogo_calado() -> None:
    pontes = pontes_do_som_do_daemon(_daemon(None))
    assert pontes is not None
    assert pontes.fone(QUATRO[0]) is None
    assert pontes.jogo_no_alto_falante(QUATRO[0]) is False
    assert pontes_do_som_do_daemon(_daemon(_PadVirtual(False, 30.0))).jogo_no_alto_falante(  # type: ignore[union-attr]
        QUATRO[0]) is False
    assert pontes_do_som_do_daemon(None) is None


def test_a_ponte_escreve_a_fonte_viva_no_subsistema_do_daemon() -> None:
    daemon = _daemon(None)
    pontes = pontes_do_som_do_daemon(daemon)
    assert pontes is not None and pontes.escolher_a_fonte(QUATRO[0], "mix") is True
    assert daemon._alto_falante_subsystem.vivas == {QUATRO[0]: "mix"}
    assert pontes_do_som_do_daemon(daemon).do_estilo is pontes.do_estilo  # type: ignore[union-attr]


def test_o_gerente_do_daemon_leva_as_pontes_do_som() -> None:
    daemon = _daemon(None)
    daemon.store = StateStore()
    gerente = gerente_do_daemon(daemon, store=daemon.store, controller=FakeController())
    assert isinstance(gerente.som_do_estilo, PontesDoSom)


def test_a_ponte_abre_o_microfone_pelo_nascimento_do_controle_do_fio_de_fora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chamado = threading.Event()
    visto: dict[str, Any] = {}

    def agendar(daemon: Any, *, uniq: str | None) -> Any:
        visto["uniq"] = uniq
        visto["no_laco"] = asyncio.get_running_loop()
        chamado.set()
        return object()

    from hefesto_dualsense4unix.daemon.subsystems import hotkey

    monkeypatch.setattr(hotkey, "agendar_o_nascimento_do_microfone", agendar)
    laco = asyncio.new_event_loop()
    fio = threading.Thread(target=laco.run_forever, daemon=True)
    fio.start()
    try:
        daemon = _daemon(None)
        daemon.bus._loop = laco
        pontes = pontes_do_som_do_daemon(daemon)
        assert pontes is not None and pontes.abrir_o_microfone(QUATRO[0]) is True
        assert chamado.wait(2.0)
        assert visto["uniq"] == QUATRO[0] and visto["no_laco"] is laco
    finally:
        laco.call_soon_threadsafe(laco.stop)
        fio.join(2.0)
        laco.close()


def test_a_ponte_sem_laco_nao_finge_que_abriu() -> None:
    pontes = pontes_do_som_do_daemon(_daemon(None))
    assert pontes is not None and pontes.abrir_o_microfone(QUATRO[0]) is False


def test_a_receita_nova_so_pede_dado() -> None:
    assert {"alto_falante", "microfone_ligado"} <= set(estilos_de_jogo.SO_DADO)
    assert {"alto_falante", "microfone_ligado"}.isdisjoint(estilos_de_jogo.APLICADAS)
    assert Receita().alto_falante is None and Receita().microfone_ligado is None
