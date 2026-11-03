"""A lista sem escolha segue o estilo do perfil; o gatilho do perfil novo nasce no «—» (03/11).

D-0311-A-LISTA-SEM-ESCOLHA-SEGUE-O-ESTILO-DO-PERFIL: num perfil com estilo, a lista de efeito que
ninguém escolheu vale «Do estilo» nas três listas (Efeito do gatilho, Efeito háptico e Padrão dos
motores), na tela e no daemon, de um a quatro controles, inclusive o que liga depois do clique; num
perfil sem estilo (e no Nativo e no Personalizado) vale «—»; o «—» guardado vale. O gatilho de um
perfil novo nasce `Off`, e a lista dele mostra «—».
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.core.trigger_effects import build_from_name, off
from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as pv
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.interface.pacotes import a03_gatilhos, a05_vibracao, a10_perfis
from hefesto_dualsense4unix.profiles import formas_de_haptica as formas
from hefesto_dualsense4unix.profiles import schema
from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

DECISAO = "D-0311-A-LISTA-SEM-ESCOLHA-SEGUE-O-ESTILO-DO-PERFIL"
CAMPOS = (("efeito_haptico", formas.ESCOLHAS), ("efeito_imersao", pv.ESCOLHAS))
LADOS = ("left", "right")
ESTILOS_COM_EFEITO = ("fps", "souls", "terror")
SEM_ESTILO = (None, "", "nativo", "personalizado", "estilo-que-nao-existe")


def _uniqs(jogadores: int) -> list[str]:
    return [f"aabbcc0000{n:02x}" for n in range(1, jogadores + 1)]


def _as_tres_listas(perfil: dict[str, Any], uniq: str) -> list[str]:
    """O que as três listas mostram para `uniq`, como a 03 e a 05 pintam."""
    controles = perfil.get("controllers") or {}
    vistas = [a05_vibracao._escolha_da_lista(controles, uniq, campo, lista, perfil.get("estilo"))
              for campo, lista in CAMPOS]
    specs = a03_gatilhos._specs()
    for disco in LADOS:
        cfg = a03_gatilhos._o_que_o_controle_recebe(perfil, uniq, disco)
        d = a03_gatilhos._do_lado(cfg, specs)
        feita = a03_gatilhos._efeito_da_lista(
            str(d["modo-chave"]), list(d["params"]), d["cru"], disco, cfg)
        vistas.append(a03_gatilhos.DO_ESTILO
                      if a03_gatilhos._a_escolha_e_do_estilo(perfil, uniq, disco) else feita)
    return vistas


def _toques(uniqs: list[str], escolhas: dict[str, str | None], estilo: str | None) -> list[str]:
    """Os controles em que o tiro toca a forma, pelo atuador do daemon."""
    feitos: list[str] = []
    motor = tv.TatoVivo([tv.AtuadorDaHaptica(
        lambda uniq, *_a, **_k: feitos.append(uniq) or True,
        escolha_de=lambda u: escolhas.get(u), estilo_de=lambda: estilo)])
    borda = tv.BordaDoRumble()
    for uniq in uniqs:
        for instante, forte in ((0.0, 0), (0.008, 200)):
            for evento in borda.ver(uniq, 0, forte, instante):
                motor.anotar(evento)
    motor.tique(0.01, lambda _u: tv.EstadoDoCanal(modo=tv.MODO_XBOX, ha_jogo=True),
                tv.Receita(vibracao_por_tiro=True))
    return sorted(feitos)


@pytest.mark.parametrize("estilo", ESTILOS_COM_EFEITO)
@pytest.mark.parametrize("jogadores", [1, 2, 3, 4])
def test_com_estilo_a_lista_sem_escolha_e_do_estilo_e_toca_o_do_estilo(
    estilo: str, jogadores: int,
) -> None:
    """D-0311-A-LISTA-SEM-ESCOLHA-SEGUE-O-ESTILO-DO-PERFIL, de um a quatro controles."""
    uniqs = _uniqs(jogadores)
    perfil = {"name": "Com estilo", "estilo": estilo, "controllers": {u: {} for u in uniqs}}
    for uniq in uniqs:
        assert _as_tres_listas(perfil, uniq) == ["do_estilo"] * 4, DECISAO
    assert formas.forma_que_vale(None, estilo) == formas.forma_do_estilo(estilo)
    assert pv.padrao_que_vale(None, estilo) == pv.padrao_que_vale(pv.DO_ESTILO, estilo)
    assert pv.padrao_que_vale(None, estilo) is not None
    assert _toques(uniqs, {}, estilo) == sorted(uniqs)


@pytest.mark.parametrize("estilo", SEM_ESTILO)
@pytest.mark.parametrize("jogadores", [1, 4])
def test_sem_estilo_a_lista_sem_escolha_e_o_traco_e_nada_toca(
    estilo: str | None, jogadores: int,
) -> None:
    uniqs = _uniqs(jogadores)
    perfil = {"name": "Sem estilo", "estilo": estilo, "controllers": {}}
    for uniq in uniqs:
        assert _as_tres_listas(perfil, uniq) == ["sem_efeito"] * 4, DECISAO
    assert formas.forma_que_vale(None, estilo) is None
    assert pv.padrao_que_vale(None, estilo) is None
    assert _toques(uniqs, {}, estilo) == []


@pytest.mark.parametrize("jogadores", [1, 2, 3, 4])
def test_o_traco_guardado_num_perfil_com_estilo_vale(jogadores: int) -> None:
    uniqs = _uniqs(jogadores)
    traco = {"rumble": {"efeito_haptico": "sem_efeito", "efeito_imersao": "sem_efeito"},
             "triggers": {d: {"mode": "Off", "params": []} for d in LADOS}}
    perfil = {"name": "Traço", "estilo": "fps", "controllers": {u: traco for u in uniqs}}
    for uniq in uniqs:
        assert _as_tres_listas(perfil, uniq) == ["sem_efeito"] * 4
    assert formas.forma_que_vale(formas.SEM_EFEITO, "fps") is None
    assert pv.padrao_que_vale(pv.SEM_EFEITO, "fps") is None
    assert _toques(uniqs, dict.fromkeys(uniqs, formas.SEM_EFEITO), "fps") == []


def test_o_controle_que_liga_depois_do_estilo_tambem_segue_o_estilo() -> None:
    presente, depois = _uniqs(2)
    novo, _ = a10_perfis._com_o_estilo(
        Profile(name="Depois", match=MatchAny()), POR_CHAVE["fps"],
        [{"uniq": presente, "jogador": 1}])
    perfil = novo.model_dump(mode="json")
    assert depois not in perfil["controllers"]
    for uniq in (presente, depois):
        assert _as_tres_listas(perfil, uniq)[:2] == ["do_estilo", "do_estilo"]
    assert _toques([presente, depois], {}, novo.estilo) == sorted((presente, depois))


def test_o_gatilho_de_perfil_novo_nasce_no_traco() -> None:
    nascido = schema.TriggersConfig()
    for disco in LADOS:
        lado = getattr(nascido, disco)
        assert (lado.mode, lado.params) == ("Off", []), DECISAO
        assert build_from_name(lado.mode, lado.params) == off()
    novo = Profile(name="Perfil novo", match=MatchAny()).model_dump(mode="json")
    for uniq in _uniqs(4):
        assert _as_tres_listas(novo, uniq)[2:] == ["sem_efeito", "sem_efeito"]


def test_o_perfil_com_gatilho_gravado_nao_muda() -> None:
    rigido = {"mode": "Rigid", "params": [5, 200]}
    antigo = Profile.model_validate(
        {"name": "Antigo", "match": {"type": "any"}, "triggers": dict.fromkeys(LADOS, rigido)})
    assert (antigo.triggers.left.mode, antigo.triggers.left.params) == ("Rigid", [5, 200])
    lista = _as_tres_listas(antigo.model_dump(mode="json"), _uniqs(1)[0])
    assert lista[2:] != ["sem_efeito", "sem_efeito"]
