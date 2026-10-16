"""O-ESTILO-NATIVO-DEIXA-O-JOGO-DECIDIR-01 — o «Nativo» da lista de estilos.

Medido antes de curar (15/10/2026): a lista de estilos não tinha o «Nativo»; quem queria que o jogo
decidisse gatilho, vibração e luz tinha de pôr as três abas em Automático na mão, e a receita do
estilo anterior seguia tocando por baixo. Os esperados são escritos à mão, e a prova olha a VISTA
que vai ao aparelho (`perfil_no_modo`) e a receita do tato, não só o que ficou no arquivo.

MORDIDAS (cada uma foi feita e viu reprovar):

* dar ao Nativo o gatilho do Aventura -> `test_o_nativo_nao_tem_receita_nenhuma`;
* tirar o `modo` Automático dos gatilhos em `_com_o_nativo` -> o gatilho do Ação chega ao aparelho;
* deixar a `receita_do_tato` no Nativo -> o tato do Terror segue tocando;
* tirar o `_sai_do_nativo` -> o Personalizado fica neutralizado para sempre.
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import estilos_de_jogo, loader
from hefesto_dualsense4unix.profiles.schema import (
    MODO_AUTOMATICO,
    MODO_PERSONALIZADO,
    MatchAny,
    Profile,
    perfil_no_modo,
)

MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2, "cor": "white",
     "nome": "White", "via": "BT", "transporte": "bt", "alvo": False},
]


class Ponte:
    def profile_switch(self, nome: str) -> bool:
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return {}


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    guardado: dict[str, Any] = {
        "perfil": Profile(name="Pragmata", match=MatchAny(), priority=40)}

    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [guardado["perfil"]])
    monkeypatch.setattr(loader, "load_profile", lambda nome, *a, **k: guardado["perfil"])

    def _save(prof: Profile, *a: Any, **kw: Any) -> None:
        guardado["perfil"] = prof

    monkeypatch.setattr(loader, "save_profile", _save)
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "Pragmata", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    return guardado


def _aplicar(rotulo: str) -> None:
    ctx = Contexto(state={"active_profile": None}, mesa=list(MESA),
                   conectados=list(MESA), estados={})
    a10_perfis.editor_estilo(ctx, {"valor": rotulo}, Ponte())


def test_o_nativo_nao_tem_receita_nenhuma() -> None:
    """MORDIDA: dar ao Nativo o gatilho do Aventura reprova aqui."""
    nativo = estilos_de_jogo.POR_CHAVE["nativo"]
    assert nativo.rotulo == "Nativo"
    assert nativo.gatilho is None and nativo.vibracao == ""
    assert nativo.receita_invisivel is None
    assert estilos_de_jogo.ESTILOS[0] is nativo, "o Nativo abre a lista"


def test_aplicar_o_nativo_poe_o_gatilho_a_luz_e_a_vibracao_no_automatico(
    disco: dict[str, Any],
) -> None:
    _aplicar("Ação")
    com_gatilho = disco["perfil"]
    assert com_gatilho.triggers.left.mode != "Off", "o Ação traz gatilho; sem isso a prova é vazia"
    _aplicar("Nativo")
    perfil = disco["perfil"]
    assert perfil.estilo == "nativo"
    assert perfil.triggers.modo == perfil.leds.modo == perfil.rumble.modo == MODO_AUTOMATICO
    assert perfil.controles_modo == MODO_AUTOMATICO
    assert perfil.rumble.policy is None


def test_o_que_vai_ao_aparelho_no_nativo_e_sem_efeito_e_sem_cor(disco: dict[str, Any]) -> None:
    """MORDIDA: tirar o `modo` Automático em `_com_o_nativo` deixa o gatilho do Ação chegar."""
    _aplicar("Ação")
    _aplicar("Nativo")
    vista = perfil_no_modo(disco["perfil"])
    assert vista.triggers.left.mode == "Off" and vista.triggers.right.mode == "Off"
    assert tuple(vista.leds.lightbar) == (0, 0, 0)
    assert vista.leds.auto_player_colors is True


def test_o_tato_do_estilo_anterior_para_de_tocar(disco: dict[str, Any]) -> None:
    """MORDIDA: deixar a `receita_do_tato`/o `estilo` antigo faz o tato do Terror seguir."""
    _aplicar("Terror")
    disco["perfil"] = disco["perfil"].model_copy(
        update={"receita_do_tato": {"vibracao_por_tiro": True}})
    assert tato_vivo.receita_do_perfil(disco["perfil"]) != tato_vivo.DESLIGADA
    _aplicar("Nativo")
    assert disco["perfil"].receita_do_tato is None
    assert tato_vivo.receita_do_perfil(disco["perfil"]) == tato_vivo.DESLIGADA


def test_o_nativo_nao_pinta_nem_pergunta_cor_de_controle(disco: dict[str, Any]) -> None:
    _aplicar("Nativo")
    assert not (disco["perfil"].controllers or {}), "o Nativo não escreve cor por controle"
    with pytest.raises(ValueError, match="não escolhe cor"):
        estilos_de_jogo.as_quatro("nativo")


def test_sair_do_nativo_devolve_o_personalizado(disco: dict[str, Any]) -> None:
    """MORDIDA: sem `_sai_do_nativo` o Personalizado herda o Automático e o gatilho segue mudo."""
    _aplicar("Nativo")
    _aplicar("Personalizado")
    perfil = disco["perfil"]
    assert perfil.estilo == "personalizado"
    assert perfil.triggers.modo == perfil.leds.modo == perfil.rumble.modo == MODO_PERSONALIZADO
    assert perfil.controles_modo == MODO_PERSONALIZADO


def test_trocar_do_nativo_para_um_estilo_de_receita_tambem_volta_os_modos(
    disco: dict[str, Any],
) -> None:
    _aplicar("Nativo")
    _aplicar("Terror")
    perfil = disco["perfil"]
    assert perfil.triggers.modo == MODO_PERSONALIZADO
    assert perfil_no_modo(perfil).triggers.left.mode == perfil.triggers.left.mode != "Off"
