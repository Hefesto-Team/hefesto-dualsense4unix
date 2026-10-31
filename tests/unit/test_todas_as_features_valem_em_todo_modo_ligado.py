"""Todas as features valem em todo modo ligado (TODAS-AS-FEATURES-VALEM-EM-TODO-MODO-LIGADO-01).

A causa medida em 31/10/2026: desde 14/10 (``6ad94334c``) o nó de háptica só nascia na porta
do gadget do pad, e o gadget só existe no modo DualSense (``uhid``). No modo Xbox e no
Nintendo o pad vai ao ``uinput``, o aparelho ficava sem nó, e com ele caíam a vibração como
háptica fina, os efeitos do Hefesto, o laço do cabo e a ponte do rádio (alto-falante e
microfone). A cura: o aparelho sem porta própria ganha o nó sem porta, só do Hefesto, sem o
nome da Sony; o nó com o nome da Sony continua só na porta do próprio pad. O Modo Nativo fica
como estava.

A régua vale para os modos ligados, P1 a P4, dois no cabo e dois no rádio. MORDIDA: troque, em
``_casar_as_pontes``, a atribuição de ``SEM_PORTA`` por ``continue``.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import pad_usb
from hefesto_dualsense4unix.integrations.virtual_pad import MODOS, par_do_modo, quer_uhid
from tests.unit import porta_de_mentira as porta
from tests.unit import test_a_haptica_chega_a_quem_entra_depois as h
from tests.unit import test_todo_pad_tem_porta_propria as t

_TODOS = t._TODOS
_IDS = ["p1-cabo", "p2-radio", "p3-cabo", "p4-radio"]
_MODOS_SEM_GADGET = [m for m in MODOS if not quer_uhid(*par_do_modo(m))]


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> Any:
    return t.mesa.__wrapped__(monkeypatch, tmp_path)  # type: ignore[attr-defined]


def _no_modo(uniq: str, modo: str, n: int) -> None:
    """O pad do aparelho no ``modo``: só o par que pede o ``uhid`` nasce no gadget."""
    if quer_uhid(*par_do_modo(modo)):
        porta.dar_porta(uniq, n)


def _o_no(mesa: Any, uniq: str) -> dict[str, Any]:
    (no,) = mesa.servidor.do_nome(eh.nome_sem_porta(eh.marca_do_aparelho(uniq)))
    return no


def test_os_modos_ligados_sem_gadget_sao_o_xbox_e_o_nintendo() -> None:
    assert sorted(_MODOS_SEM_GADGET) == ["nintendo", "xbox"]


@pytest.mark.parametrize("modo", _MODOS_SEM_GADGET)
@pytest.mark.parametrize("uniq", _TODOS, ids=_IDS)
def test_vibracao_e_efeitos_vao_pela_haptica_fina_em_todo_modo(
    mesa: Any, modo: str, uniq: str
) -> None:
    """A vibração do jogo e os efeitos do Hefesto têm o nó do aparelho em todo modo ligado."""
    _no_modo(uniq, modo, 1)
    controle = t._chega(mesa, uniq)
    mesa.volta(controle)
    mesa.volta(controle)
    assert mesa.sub._quer_o_rumble_pelo_audio(uniq) is True
    assert mesa.sub._quer_a_haptica_fina(uniq) is True
    assert mesa.sub.por_onde_vai_o_rumble(uniq)["rota"] == "haptica_fina"
    assert mesa.servidor.quedas == []


@pytest.mark.parametrize("modo", _MODOS_SEM_GADGET)
@pytest.mark.parametrize("uniq", _TODOS, ids=_IDS)
def test_o_no_sem_porta_nao_tem_o_nome_nem_a_identidade_da_sony(
    mesa: Any, modo: str, uniq: str
) -> None:
    """Nenhum jogo acha o nó sem porta: o engasgo de 14/10 não volta."""
    _no_modo(uniq, modo, 1)
    mesa.volta(t._chega(mesa, uniq))
    no = _o_no(mesa, uniq)
    assert not any(agulha in no["nome"] for agulha in eh.AGULHAS[:1] + eh.AGULHAS[2:])
    assert "sysfs.path" not in no["props"]
    assert "device.vendor.id" not in no["props"]
    assert "device.product.name" not in no["props"]
    assert mesa.servidor.do_nome(eh.nome_do_endpoint(uniq)) == []


@pytest.mark.parametrize("modo", _MODOS_SEM_GADGET)
@pytest.mark.parametrize("uniq", [u for u in _TODOS if u in t._NO_CABO], ids=["p1", "p3"])
def test_no_cabo_o_laco_leva_o_no_a_placa_em_todo_modo(mesa: Any, modo: str, uniq: str) -> None:
    _no_modo(uniq, modo, 1)
    controle = t._chega(mesa, uniq)
    mesa.volta(controle)
    mesa.volta(controle)
    laco = mesa.lacos.vivos[h._chave(uniq)]
    assert laco["captura"] == str(mesa.servidor.indice(_o_no(mesa, uniq)["nome"]))


@pytest.mark.parametrize("modo", _MODOS_SEM_GADGET)
@pytest.mark.parametrize("uniq", [u for u in _TODOS if u not in t._NO_CABO], ids=["p2", "p4"])
def test_no_radio_a_ponte_do_som_e_do_microfone_tem_o_no_em_todo_modo(
    mesa: Any, modo: str, uniq: str
) -> None:
    _no_modo(uniq, modo, 1)
    controle = t._chega(mesa, uniq)
    mesa.volta(controle)
    mesa.servidor.jogo_em.add(_o_no(mesa, uniq)["nome"])
    mesa.volta(controle)
    assert mesa.sub._sem_ponte_porque.get(uniq) != "o controle ainda não tem endpoint de vibração"
    assert mesa.sub._endpoint_da_ponte.get(uniq) == _o_no(mesa, uniq)["nome"]


def test_os_quatro_juntos_cada_um_com_o_seu_no(mesa: Any) -> None:
    chegaram = [t._chega(mesa, u) for u in _TODOS]
    mesa.volta(*chegaram)
    mesa.volta(*chegaram)
    nomes = {_o_no(mesa, u)["nome"] for u in _TODOS}
    assert len(nomes) == len(_TODOS)
    assert all(mesa.sub._quer_o_rumble_pelo_audio(u) for u in _TODOS)
    assert mesa.servidor.quedas == []


def test_a_troca_de_modo_troca_o_no_e_e_idempotente(mesa: Any) -> None:
    """Xbox → DualSense → Xbox: o nó da Sony vive na porta, e o sem porta volta sem a porta."""
    controle = t._chega(mesa, h._P2)
    mesa.volta(controle)
    sem_porta = _o_no(mesa, h._P2)["nome"]
    interface = porta.dar_porta(h._P2, 5)
    mesa.volta(controle)
    mesa.volta(controle)
    assert mesa.servidor.do_nome(sem_porta) == []
    assert h._ancora_do_aparelho(mesa.servidor, h._P2) == interface
    porta.tirar_porta(h._P2)
    mesa.volta(controle)
    mesa.volta(controle)
    assert mesa.servidor.do_nome(eh.nome_do_endpoint(h._P2)) == []
    assert len(mesa.servidor.do_nome(sem_porta)) == 1
    cargas = list(mesa.servidor.cargas)
    mesa.volta(controle)
    assert mesa.servidor.cargas == cargas


def test_o_no_sem_porta_que_sobrou_cai_quando_a_porta_chega(mesa: Any) -> None:
    """O daemon de antes deixou o nó sem porta; o aparelho agora tem a porta dele."""
    nome = eh.nome_sem_porta(eh.marca_do_aparelho(h._P1))
    herdado = mesa.servidor.modulo_herdado(nome, "")
    porta.dar_porta(h._P1, 2)
    mesa.volta(t._chega(mesa, h._P1))
    assert herdado in mesa.servidor.quedas
    assert mesa.servidor.do_nome(nome) == []


@pytest.mark.parametrize("uniq", _TODOS, ids=_IDS)
def test_no_modo_nativo_nada_muda(mesa: Any, uniq: str) -> None:
    mesa.sub._daemon = type("D", (), {"is_native_mode": lambda self: True})()
    mesa.volta(t._chega(mesa, uniq))
    assert mesa.servidor.do_nome(eh.nome_sem_porta(eh.marca_do_aparelho(uniq))) == []
    assert mesa.servidor.do_nome(eh.nome_do_endpoint(uniq)) == []


def test_o_endpoint_sem_porta_nasce_mesmo_com_o_gadget_de_outro() -> None:
    """A guarda da porta alheia vale só para o nó da Sony."""
    assert eh.e_sem_porta(eh.SEM_PORTA)
    assert not eh.a_porta_e_dele("aa:bb:cc:00:00:01", eh.SEM_PORTA)
    assert pad_usb.interface_do_aparelho("aa:bb:cc:00:00:01") is None


@pytest.mark.parametrize("uniq", _TODOS, ids=_IDS)
def test_o_registro_reconhece_so_o_endpoint_da_sony(uniq: str) -> None:
    """O laço do nó sem porta não tira a placa do registro: o jogo segue achando a placa."""
    from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

    marca = eh.marca_do_aparelho(uniq)
    assert ks.e_o_endpoint_que_o_jogo_acha(eh.nome_da_marca(marca), marca)
    assert not ks.e_o_endpoint_que_o_jogo_acha(eh.nome_sem_porta(marca), marca)
