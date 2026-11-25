"""D-1911-O-MODO-E-O-GATILHO-TEM-PADRAO-DO-COMPUTADOR: sem perfil ativo, o efeito do gatilho e o
«Modo automático» das abas Jogar, Gatilhos e Vibração se guardam no padrão do computador.

O lar é de mentira (o `conftest` desvia `HOME` e os `XDG_*`): sem perfil, sem computador declarado.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"), str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")
CHAVES = ("aabbcc000001", "aabbcc000002")
AUTOMATICO = "automatico"  # (noqa-acento)
PERSONALIZADO = "personalizado"
IMERSAO = {"left": "rajada-que-sobe-sozinha", "right": "nenhum"}


@pytest.fixture
def a03():
    import pacotes  # noqa: F401
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()


class Ponte:
    """Dublê do dono do aparelho: aceita tudo e diz que chegou aos controles."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def trigger_set_detalhado(self, *a: Any, **k: Any) -> tuple[bool, str, dict[str, Any]]:
        self.chamadas.append("set")
        return True, "", {"status": "ok", "aplicado_em": list(UNIQS), "guardado_em": []}

    def trigger_reset_detalhado(self, *a: Any, **k: Any) -> tuple[bool, str, dict[str, Any]]:
        self.chamadas.append("reset")
        return True, "", {"status": "ok", "aplicado_em": list(UNIQS), "guardado_em": []}

    def __getattr__(self, nome: str) -> Any:
        def registrar(*a: Any, **k: Any) -> bool:
            self.chamadas.append(nome)
            return True

        return registrar


def _ctx() -> Any:
    from pacotes import Contexto

    mesa = [{"pref": f"p{n}", "jogador": n, "uniq": u, "nome": f"Controle {n}", "via": "USB",
             "cor": "starlight-blue", "mascara": "DualSense"} for n, u in enumerate(UNIQS, 1)]
    vivos = [{"uniq": u, "player": n, "transport": "usb" if n == 1 else "bt",
              "is_primary": n == 1, "inputs": {"l2_raw": 0, "r2_raw": 0}}
             for n, u in enumerate(UNIQS, 1)]
    return Contexto(state={"active_profile": None}, mesa=mesa, conectados=vivos, estados={})


def _gesto(pagina: str, nome: str) -> Any:
    import pacotes

    funcao = pacotes.gesto_da_pagina(pagina, nome)
    assert funcao is not None, (pagina, nome)
    return funcao


def _computador() -> Any:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador

    return o_computador()


def _o_que_vale() -> Any:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_perfil_sem_perfil_ativo

    return o_perfil_sem_perfil_ativo()


def test_o_efeito_do_gatilho_de_cada_controle_fica_no_computador(a03) -> None:
    """D-1911-O-MODO-E-O-GATILHO-TEM-PADRAO-DO-COMPUTADOR: um efeito por controle, sem perfil."""
    from hefesto_dualsense4unix.profiles import efeitos_de_imersao as imersao

    escolhida = imersao.POR_CHAVE[IMERSAO["left"]]
    ponte = Ponte()
    a03.imersao_escolhida(_ctx(), {"uniq": UNIQS[0], "lado": "e", "valor": escolhida.chave}, ponte)
    a03.imersao_escolhida(_ctx(), {"uniq": UNIQS[1], "lado": "d", "valor": escolhida.chave}, ponte)

    do_computador = _computador().controles
    primeiro = do_computador[CHAVES[0]].triggers
    segundo = do_computador[CHAVES[1]].triggers
    assert primeiro.left.mode == "Machine" and "right" not in primeiro.model_fields_set
    assert segundo.right.mode == "Machine" and "left" not in segundo.model_fields_set

    a03.esquecer_o_rascunho()
    vista = _o_que_vale().controllers
    assert vista[CHAVES[0]].triggers.left.mode == "Machine"
    assert vista[CHAVES[1]].triggers.right.mode == "Machine"


def test_o_efeito_guardado_pinta_na_coluna_sem_rascunho(a03) -> None:
    """A aba reaberta (rascunho vazio) lê o efeito do computador, não o travessão."""
    from hefesto_dualsense4unix.profiles import efeitos_de_imersao as imersao
    from pacotes import perfil

    escolhida = imersao.POR_CHAVE[IMERSAO["left"]]
    pedido = {"uniq": UNIQS[0], "lado": "e", "valor": escolhida.chave}
    a03.imersao_escolhida(_ctx(), pedido, Ponte())
    a03.esquecer_o_rascunho()

    vale = perfil.ativo_que_vale(None)
    assert a03._o_que_o_controle_recebe(vale, UNIQS[0], "left")["mode"] == "Machine"
    assert a03._o_que_o_controle_recebe(vale, UNIQS[1], "left").get("mode") != "Machine"


@pytest.mark.parametrize("aba,gesto", [
    ("03-gatilhos.html", "modo-dos-gatilhos"),
    ("05-vibracao.html", "modo-da-vibracao"),
    ("01-jogar.html", "modo-dos-controles"),
])
def test_o_modo_automatico_sem_perfil_liga_e_volta(aba: str, gesto: str, a03) -> None:
    """D-1911-O-MODO-E-O-GATILHO-TEM-PADRAO-DO-COMPUTADOR: o modo liga e volta, sem perfil."""
    from pacotes import a02_controles, a05_vibracao, perfil

    leitor = {"modo-dos-gatilhos": a03.modo_dos_gatilhos_do_perfil,
              "modo-da-vibracao": a05_vibracao.modo_da_vibracao_do_perfil,
              "modo-dos-controles": a02_controles.modo_dos_controles_do_perfil}[gesto]
    assert leitor(perfil.ativo_que_vale(None)) == PERSONALIZADO

    _gesto(aba, gesto)(_ctx(), {"modo": AUTOMATICO}, Ponte())
    assert leitor(perfil.ativo_que_vale(None)) == AUTOMATICO
    vale = _o_que_vale()
    escrito = {"modo-dos-gatilhos": vale.triggers.modo, "modo-da-vibracao": vale.rumble.modo,
               "modo-dos-controles": vale.controles_modo}[gesto]
    assert escrito == AUTOMATICO

    _gesto(aba, gesto)(_ctx(), {"modo": PERSONALIZADO}, Ponte())
    assert leitor(perfil.ativo_que_vale(None)) == PERSONALIZADO


def test_o_modo_dos_gatilhos_guarda_so_o_modo_e_nao_o_efeito(a03) -> None:
    """Do gatilho global o computador guarda o modo: o efeito é de cada controle e de cada jogo."""
    _gesto("03-gatilhos.html", "modo-dos-gatilhos")(_ctx(), {"modo": AUTOMATICO}, Ponte())

    do_global = _computador().global_.triggers
    assert do_global is not None and do_global.model_fields_set == {"modo"}


def test_o_modo_automatico_guardado_recusa_o_efeito_sem_perfil(a03) -> None:
    """A guarda dos gestos de efeito vale sem perfil: o Automático escrito recusa e não grava."""
    _gesto("03-gatilhos.html", "modo-dos-gatilhos")(_ctx(), {"modo": AUTOMATICO}, Ponte())
    antes = _computador().model_dump(mode="json", exclude_unset=True)

    with pytest.raises(RuntimeError, match="modo automático"):
        a03.imersao_escolhida(
            _ctx(), {"uniq": UNIQS[0], "lado": "e", "valor": "rajada-que-sobe-sozinha"}, Ponte())
    assert _computador().model_dump(mode="json", exclude_unset=True) == antes


def test_o_perfil_do_jogo_sobrepoe_o_que_o_computador_guardou(a03) -> None:
    """Com perfil, o jogo manda: o que ele escreveu vence, o que não escreveu vem do computador."""
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
        gravar_pelo_gesto,
        perfil_que_vale,
    )
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        Profile,
        TriggerConfig,
        TriggersConfig,
    )

    _gesto("01-jogar.html", "modo-dos-controles")(_ctx(), {"modo": AUTOMATICO}, Ponte())
    _gesto("03-gatilhos.html", "modo-dos-gatilhos")(_ctx(), {"modo": AUTOMATICO}, Ponte())
    gravar_pelo_gesto(
        "gatilho", "",
        lambda v: v.model_copy(update={"controllers": {CHAVES[0]: ControllerOverrides(
            triggers=TriggersConfig(left=TriggerConfig(mode="Machine", params=[1, 9, 5, 5, 40]),
                                    right=TriggerConfig(mode="Rigid", params=[5, 200])))}}),
        uniq=CHAVES[0])

    jogo = Profile.model_validate({
        "name": "jogo", "match": {"type": "any"}, "controles_modo": PERSONALIZADO,
        "triggers": {"left": {"mode": "Galloping", "params": [0, 9, 7, 7, 10]}}})
    vale = perfil_que_vale(jogo, _computador())

    assert vale.controles_modo == PERSONALIZADO
    assert vale.triggers.modo == AUTOMATICO
    seus = vale.controllers[CHAVES[0]].triggers
    assert "left" not in seus.model_fields_set, "o gatilho que o jogo escolheu para todos vence"
    assert seus.right.mode == "Rigid", "o lado que o jogo não escolheu vem do computador"
