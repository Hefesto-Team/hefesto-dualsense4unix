"""A luz animada obedece à «Bateria longa» (A-LUZ-ANIMADA-OBEDECE-A-BATERIA-LONGA-01).

Na economia da mesa, ou na do controle, o efeito da barra para e a barra fica fixa na cor do perfil;
ao sair da economia, o efeito volta sem gesto. Um reassert de fora (o daemon repintando as saídas
resolvidas) é seguido do quadro corrente no tique seguinte, mesmo igual ao anterior. Sem perfil
ativo, a lista de efeitos da aba 04 mostra o que o computador guarda. Vale para P1 a P4, no cabo e
no Bluetooth: o plano não pergunta pelo transporte.
"""
from __future__ import annotations

import pathlib
import sys
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.profiles import schema
from hefesto_dualsense4unix.profiles.schema import (
    EfeitoDaLuz,
    LedsConfig,
    MatchAny,
    Profile,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Quatro jogadores: faixa forjada (`aa:bb:cc`), nunca endereço de aparelho de verdade.
JOGADORES = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
EFEITO = "piscar;FF0000;4"


def _perfil(efeito: str | None = EFEITO) -> Profile:
    return Profile(name="regua", match=MatchAny(), leds=LedsConfig(efeito=efeito))


def _declaracao(mesa: bool = False, controles: tuple[str, ...] = ()) -> Any:
    """A declaração viva do ``maquina.json``: o teto da mesa e os controles que ligaram a sua."""
    return SimpleNamespace(
        orcamento=SimpleNamespace(teto="economia" if mesa else None),
        controles={u.replace(":", ""): SimpleNamespace(economia=True) for u in controles},
    )


@pytest.fixture
def economia() -> Iterator[Any]:
    """Põe a declaração viva que o ``plano_do_perfil`` lê, e a tira no fim."""
    atual = {"declaracao": _declaracao()}
    schema.registrar_declaracao_da_mesa(lambda: atual["declaracao"])
    try:
        yield atual
    finally:
        schema.registrar_declaracao_da_mesa(None)


def test_sem_economia_os_quatro_controles_animam(economia: dict[str, Any]) -> None:
    assert set(luz.plano_do_perfil(_perfil(), JOGADORES)) == set(JOGADORES)


def test_na_bateria_longa_da_mesa_nenhum_controle_anima(economia: dict[str, Any]) -> None:
    """MORDIDA: devolver o perfil cru ao ``plano_do_perfil`` (sem a vista da economia)."""
    economia["declaracao"] = _declaracao(mesa=True)
    assert luz.plano_do_perfil(_perfil(), JOGADORES) == {}


@pytest.mark.parametrize("em_economia", JOGADORES)
def test_na_economia_de_um_controle_so_ele_sai_do_plano(
        economia: dict[str, Any], em_economia: str) -> None:
    economia["declaracao"] = _declaracao(controles=(em_economia,))
    plano = luz.plano_do_perfil(_perfil(), JOGADORES)
    assert set(plano) == set(JOGADORES) - {em_economia}


def test_o_endereco_do_controle_casa_em_qualquer_forma(economia: dict[str, Any]) -> None:
    economia["declaracao"] = _declaracao(controles=(JOGADORES[1],))
    assert JOGADORES[1] not in luz.plano_do_perfil(_perfil(), [JOGADORES[1].upper()])
    assert luz.plano_do_perfil(_perfil(), [JOGADORES[1].replace(":", "")]) == {}


def test_sair_da_economia_devolve_o_efeito(economia: dict[str, Any]) -> None:
    economia["declaracao"] = _declaracao(mesa=True)
    assert luz.plano_do_perfil(_perfil(), JOGADORES) == {}
    economia["declaracao"] = _declaracao()
    assert set(luz.plano_do_perfil(_perfil(), JOGADORES)) == set(JOGADORES)


def test_a_vista_injetada_vale_sem_declaracao_viva() -> None:
    """Quem já tem a economia na mão a passa: o plano não vai ao disco por ela."""
    assert luz.plano_do_perfil(_perfil(), JOGADORES, mesa_em_economia=True) == {}
    so_um = luz.plano_do_perfil(
        _perfil(), JOGADORES, em_economia=frozenset({JOGADORES[0].replace(":", "")}))
    assert JOGADORES[0] not in so_um and len(so_um) == 3


# ---------------------------------------------------------------- o laço inteiro


class _Barra:
    def __init__(self) -> None:
        self.escritos: list[tuple[str, tuple[int, int, int]]] = []
        self.soltos: list[str] = []

    def laco(self) -> luz.LuzAnimada:
        return luz.LuzAnimada(lambda u, c: self.escritos.append((u, c)), self.soltos.append)


def _daemon(repinturas: list[int]) -> Any:
    """Um daemon sem jogo, com a barra livre; ``repinturas[0]`` é o contador do backend."""
    pad = SimpleNamespace(backend="uhid", visto_ha_s={}, game_open=False)

    class _Controller:
        primary_uniq = JOGADORES[0]

        @property
        def repinturas_da_luz(self) -> int:
            return repinturas[0]

    return SimpleNamespace(
        controller=_Controller(), _last_state=None, _gamepad_device=pad,
        display_authority="unknown", _coop_manager=None,
        store=SimpleNamespace(active_profile="regua"))


def _passo(monkeypatch: pytest.MonkeyPatch, repinturas: list[int] | None = None,
           efeito: str = EFEITO) -> tuple[luz.Passo, _Barra]:
    barra = _Barra()
    monkeypatch.setattr(luz, "perfil_ativo", lambda _d: _perfil(efeito))
    return luz.Passo(_daemon(repinturas or [0]), barra.laco()), barra


def test_o_laco_para_na_bateria_longa_solta_a_barra_e_volta_ao_sair(
        monkeypatch: pytest.MonkeyPatch, economia: dict[str, Any]) -> None:
    """Entrar na economia solta a barra UMA vez (a cor do perfil); sair devolve o efeito."""
    passo, barra = _passo(monkeypatch)
    assert passo(10.0) == 1
    economia["declaracao"] = _declaracao(mesa=True)
    assert passo(10.6) == 0, "o plano é relido a cada meio segundo"
    assert barra.soltos == [JOGADORES[0]]
    assert passo(11.0) == 0 and barra.soltos == [JOGADORES[0]], "solta uma vez só"
    economia["declaracao"] = _declaracao()
    assert passo(11.05) == 0, "ainda dentro do meio segundo da releitura"
    assert passo(11.7) == 1, "saiu da economia: o efeito volta sem gesto"


# ---------------------------------------------------------------- o reassert de fora


def test_depois_de_um_reassert_de_fora_o_quadro_corrente_sai_mesmo_igual(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O piscar de ritmo 1 fica 1,67 s no mesmo quadro: sem o repinte, a cor base do reassert
    ficaria na barra até o quadro mudar. MORDIDA: ignorar o contador de repinturas."""
    repinturas = [0]
    passo, barra = _passo(monkeypatch, repinturas, "piscar;FF0000;1")
    assert passo(10.0) == 1
    assert passo(10.1) == 0, "quadro igual não sai"
    repinturas[0] += 1
    assert passo(10.2) == 1, "o reassert repintou a cor base: o quadro corrente volta"
    assert barra.escritos[-1] == barra.escritos[0]
    assert passo(10.3) == 0, "e uma vez só por reassert"


def test_o_reassert_que_o_proprio_laco_pede_nao_vira_quadro(
        monkeypatch: pytest.MonkeyPatch, economia: dict[str, Any]) -> None:
    """Ao parar, o ``soltar`` repinta pelo backend e o contador sobe: sem plano, nada a escrever."""
    repinturas = [0]
    passo, barra = _passo(monkeypatch, repinturas)
    assert passo(10.0) == 1
    economia["declaracao"] = _declaracao(mesa=True)
    repinturas[0] += 1
    assert passo(10.6) == 0 and barra.soltos == [JOGADORES[0]]
    assert len(barra.escritos) == 1


def test_o_backend_conta_cada_repintura_e_o_quadro_do_efeito_nao_conta(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O contador é do dono único das repinturas (``_repintar_a_luz_de_um``): reassert, vigia do
    sequestro e nó novo sobem; o quadro do efeito, não."""
    from hefesto_dualsense4unix.profiles import loader
    from tests.unit.test_r20_camadas_de_saida import _backend

    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: tmp_path)
    backend, _h1, _h2 = _backend()
    antes = backend.repinturas_da_luz
    backend.pintar_a_barra_sem_lembrar(next(iter(backend.alvos_conectados().values())) or "",
                                       (0, 200, 200))
    assert backend.repinturas_da_luz == antes, "o quadro do efeito não é repintura"
    backend.reassert_resolved_outputs()
    assert backend.repinturas_da_luz > antes
    meio = backend.repinturas_da_luz
    uniqs = [u for u in backend.alvos_conectados().values() if u]
    backend.reafirmar_barra_e_numero(uniqs)
    assert backend.repinturas_da_luz > meio


# ---------------------------------------------------------------- a aba 04 sem perfil ativo


def _ctx() -> Any:
    import pacotes

    return pacotes.Contexto(
        state={"active_profile": ""},
        mesa=[{"pref": "p1", "jogador": 1, "uniq": JOGADORES[0], "nome": "Régua", "via": "USB",
               "cor": "starlight-blue"}],
        conectados=[{"uniq": JOGADORES[0], "connected": True, "transport": "usb", "index": 0,
                     "player": 1}],
        estados={})


def test_sem_perfil_ativo_a_lista_mostra_o_efeito_que_o_computador_guarda() -> None:
    """O ``maquina.json`` guarda o respirar; sem perfil ativo a lista dizia «Luz fixa».
    MORDIDA: devolver o perfil vazio à lista."""
    import pacotes
    from pacotes import a04_iluminacao as a04

    pacotes.gesto_da_pagina("04-iluminacao.html", "efeito-da-luz")(
        _ctx(), {"uniq": JOGADORES[0], "valor": "respirar;00FFFF;2"}, None)
    colunas = a04.pacote(_ctx())["colunas"]
    assert colunas[JOGADORES[0]][a04.CAMPO_DO_EFEITO] == "respirar;00FFFF;2"


def test_sem_perfil_e_sem_efeito_guardado_a_lista_diz_luz_fixa() -> None:
    from pacotes import a04_iluminacao as a04

    colunas = a04.pacote(_ctx())["colunas"]
    assert colunas[JOGADORES[0]][a04.CAMPO_DO_EFEITO] == a04.LUZ_FIXA


def test_o_efeito_e_so_o_da_luz_animada() -> None:
    """Guarda do tipo: o plano devolve ``PlanoDoControle`` com o efeito lido, não texto."""
    plano = luz.plano_do_perfil(_perfil(), JOGADORES[:1], mesa_em_economia=False,
                                em_economia=frozenset())
    assert isinstance(plano[JOGADORES[0]].efeito, EfeitoDaLuz)
