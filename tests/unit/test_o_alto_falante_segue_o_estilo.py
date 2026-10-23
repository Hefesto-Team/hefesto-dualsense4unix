"""O alto-falante de cada estilo segue o jogo, e o Ritmo nunca duplica o som.

Sprint O-ALTO-FALANTE-SEGUE-O-ESTILO-E-O-RITMO-NUNCA-DUPLICA-01. Só o Terror e o Ritmo têm
opinião sobre o alto-falante; os outros estilos deixam o nó com o jogo. O Ritmo escreve só a
``fonte`` ``sfx`` (pelo gancho do daemon), sem tocar no volume nem na rota.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.estilos_de_jogo import ESTILOS, POR_CHAVE
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import PontesDoSom, ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MODO_AUTOMATICO,
    MatchAny,
    Profile,
    ProfileSpeakerConfig,
)
from hefesto_dualsense4unix.testing import FakeController

# a faixa forjada das fixtures (nunca endereço real mascarado)
QUATRO = ["aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04"]


class Mesa:
    """As pontes do daemon, com o que cada uma recebeu."""

    def __init__(self, *, jogo: set[str] | None = None) -> None:
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
            conectados=lambda: list(QUATRO),
            fone=lambda uniq: False,
            jogo_no_alto_falante=lambda uniq: uniq in self.jogo,
            escolher_a_fonte=escolher,
            abrir_o_microfone=abrir,
            do_estilo=self.memoria,
        )


class Gerente:
    """O gerente com o backend de mentira e o applier de som que CONTA o que recebe."""

    def __init__(self, mesa: Mesa) -> None:
        self.mesa = mesa
        self.som: list[dict[str, Any]] = []
        self.manager = ProfileManager(
            controller=FakeController(),
            store=StateStore(),
            speaker_applier=self._speaker,
            som_do_estilo=mesa.pontes(),
        )

    def _speaker(
        self, volume: int, muted: bool, *, uniq: str | None = None,
        origin: str = "manual", rota: int | None = None,
    ) -> bool:
        self.som.append({"volume": volume, "muted": muted, "uniq": uniq, "rota": rota})
        return True


def _perfil(estilo: str | None, modo: str | None = MODO_AUTOMATICO, **kw: Any) -> Profile:
    return Profile(name="ritmo-de-teste", match=MatchAny(), estilo=estilo,
                   controles_modo=modo, **kw)


@pytest.fixture
def perfis_no_disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / "profiles"
    pasta.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: pasta)
    return pasta


def _com_receita() -> list[str]:
    return [e.chave for e in ESTILOS if e.receita_invisivel is not None]


def test_so_o_terror_e_o_ritmo_tem_opiniao_sobre_o_alto_falante() -> None:
    com_opiniao = {
        chave for chave in (e.chave for e in ESTILOS)
        if getattr(POR_CHAVE[chave].receita_invisivel, "alto_falante", None) is not None
    }
    assert com_opiniao == {"terror", "ritmo"}


def test_o_ritmo_nunca_duplica_a_receita_e_sfx_sem_volume_nem_rota() -> None:
    af = POR_CHAVE["ritmo"].receita_invisivel.alto_falante
    assert af is not None
    assert (af.fonte, af.rota, af.nivel_padrao) == ("sfx", None, False)


def test_ritmo_no_automatico_escreve_sfx_nos_quatro_e_nao_toca_no_volume() -> None:
    mesa = Mesa()
    g = Gerente(mesa)
    relatorio = g.manager.apply_som_do_estilo(_perfil("ritmo"))
    assert mesa.fontes == [(u, "sfx") for u in QUATRO]
    assert g.som == []  # nem volume, nem mudo, nem rota: o controle fica com o que já tem
    assert mesa.abertos == []  # o Ritmo não opina no microfone
    assert all(relatorio[f"som_estilo:{u}"] == "aplicado" for u in QUATRO)


def test_ritmo_partindo_de_um_perfil_com_fonte_mix_escreve_sfx_do_mesmo_jeito() -> None:
    mesa = Mesa()
    g = Gerente(mesa)
    perfil = _perfil("ritmo", speaker=ProfileSpeakerConfig(volume=120, muted=False, fonte="mix"))
    g.manager.apply_som_do_estilo(perfil)
    assert mesa.fontes == [(u, "sfx") for u in QUATRO]
    assert g.som == []


def test_terror_seguido_de_ritmo_tira_o_mix_do_terror() -> None:
    mesa = Mesa()
    g = Gerente(mesa)
    g.manager.apply_som_do_estilo(_perfil("terror"))
    assert mesa.memoria == {u: "mix" for u in QUATRO}
    mesa.fontes.clear()
    g.som.clear()
    g.manager.apply_som_do_estilo(_perfil("ritmo"))
    assert mesa.fontes == [(u, "sfx") for u in QUATRO]
    assert g.som == []
    assert mesa.memoria == {u: "sfx" for u in QUATRO}


@pytest.mark.parametrize("chave", [c for c in _com_receita() if c not in ("terror", "ritmo")])
def test_os_outros_estilos_deixam_o_alto_falante_com_o_jogo(chave: str) -> None:
    mesa = Mesa()
    g = Gerente(mesa)
    relatorio = g.manager.apply_som_do_estilo(_perfil(chave))
    assert POR_CHAVE[chave].receita_invisivel.alto_falante is None
    assert g.som == [] and mesa.fontes == [] and mesa.abertos == []
    assert not any(k.startswith("som_estilo:") for k in relatorio)


@pytest.mark.parametrize("modo", ["personalizado", None])
def test_ritmo_fora_do_automatico_vale_a_aba_e_nada_se_escreve(modo: str | None) -> None:
    mesa = Mesa()
    g = Gerente(mesa)
    g.manager.apply_som_do_estilo(_perfil("ritmo", modo))
    assert mesa.fontes == [] and g.som == []


def test_ritmo_sem_estilo_nem_pontes_nao_escreve() -> None:
    mesa = Mesa()
    g = Gerente(mesa)
    g.manager.apply_som_do_estilo(_perfil(None))
    assert mesa.fontes == []
    sem_pontes = ProfileManager(controller=FakeController(), store=StateStore())
    assert sem_pontes.apply_som_do_estilo(_perfil("ritmo")) == {}


def test_o_jogo_que_ja_fala_no_alto_falante_nao_leva_nada_por_cima_do_ritmo() -> None:
    mesa = Mesa(jogo={QUATRO[1]})
    g = Gerente(mesa)
    relatorio = g.manager.apply_som_do_estilo(_perfil("ritmo"))
    assert QUATRO[1] not in [u for u, _ in mesa.fontes]
    assert relatorio[f"som_estilo:{QUATRO[1]}"] == "ignorado_o_jogo_manda"
    assert [u for u, _ in mesa.fontes] == [QUATRO[0], QUATRO[2], QUATRO[3]]


def test_a_ativacao_inteira_do_ritmo_escreve_so_a_fonte(perfis_no_disco: Path) -> None:
    save_profile(_perfil("ritmo"))
    mesa = Mesa()
    g = Gerente(mesa)
    relatorio: dict[str, str] = {}
    g.manager.activate("ritmo-de-teste", relatorio=relatorio)
    assert mesa.fontes == [(u, "sfx") for u in QUATRO]
    assert g.som == []
    assert relatorio[f"som_estilo:{QUATRO[0]}"] == "aplicado"


def test_o_replug_devolve_a_fonte_do_ritmo_so_ao_controle_que_voltou(
    perfis_no_disco: Path,
) -> None:
    save_profile(_perfil("ritmo"))
    mesa = Mesa()
    g = Gerente(mesa)
    g.manager.store.set_active_profile("ritmo-de-teste")
    g.manager.reapply_speaker_on_connect(QUATRO[2])
    assert mesa.fontes == [(QUATRO[2], "sfx")]
    assert g.som == []


def test_nenhum_estilo_liga_o_estalo_do_tiro_no_alto_falante() -> None:
    assert tato_vivo.SOM_NO_CONTROLE_DO_ESTILO is False
