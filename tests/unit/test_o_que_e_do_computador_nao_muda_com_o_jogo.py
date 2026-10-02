"""O que é do computador não muda com o jogo (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01).

Ela, 01/10, depois de uma noite com visitas: *«algumas features precisam ser por
computador e permanecerem salvas»*. O som, os sensores, a luz, a vibração, o
mouse e o teclado ganham um padrão do computador no ``maquina.json``
(``computador``), e o perfil do jogo só sobrepõe.

Tudo num lar de mentira (o ``conftest`` desvia os ``XDG_*``), com identidades da
faixa sintética da casa.
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import (
    A_ECONOMIA_EM_CADA_PECA,
    Profile,
)
from hefesto_dualsense4unix.utils import maquina as m

P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"


def _perfil(nome: str = "Jogo X", **campos: Any) -> Profile:
    return Profile.model_validate(
        {"name": nome, "match": {"type": "criteria", "window_class": [nome.lower()]},
         **campos})


def _computador(documento: dict[str, Any]) -> Any:
    assert m.gravar_o_computador(documento)
    return opc.o_computador()


# ---------------------------------------------------------------------------
# O dono: o campo `computador` do `maquina.json`
# ---------------------------------------------------------------------------
def test_o_computador_vai_ao_disco_so_com_o_que_foi_declarado() -> None:
    """O brilho de fábrica de UM controle não pode ir ao disco por extenso.

    MORDIDA: tirar o serializador de ``ComputadorDeclarado`` grava o ``LedsConfig``
    inteiro do P2, e o brilho 1.0 de fábrica passaria a vencer o do computador.
    """
    _computador({"controles": {P2: {"leds": {"lightbar": [0, 255, 0]}}}})
    bruto = json.loads(m.caminho_da_maquina().read_text(encoding="utf-8"))
    assert bruto["computador"] == {"controles": {P2: {"leds": {"lightbar": [0, 255, 0]}}}}
    relido = m.carregar_maquina().computador
    assert relido.controles[P2].leds.model_fields_set == {"lightbar"}


def test_o_computador_recusa_o_que_e_do_jogo() -> None:
    """A máscara, os gatilhos e a mira de um controle são do jogo (`DO_JOGO`)."""
    with pytest.raises(ValueError, match="do jogo"):
        m.gravar_o_computador({"controles": {P2: {"mascara": "xbox"}}})
    with pytest.raises(ValueError):
        m.gravar_o_computador({"global": {"mouse": {"speed": 99}}})


def test_o_resgate_salva_o_resto_do_computador() -> None:
    """Uma seção torta sai sozinha; a luz que ela ajustou continua."""
    _computador({"global": {"leds": {"lightbar": [1, 2, 3]}}})
    bruto = json.loads(m.caminho_da_maquina().read_text(encoding="utf-8"))
    bruto["computador"]["global"]["mouse"] = {"speed": 999}
    m.caminho_da_maquina().write_text(json.dumps(bruto), encoding="utf-8")
    relido = m.carregar_maquina().computador
    assert relido.global_.leds is not None and relido.global_.leds.lightbar == (1, 2, 3)
    assert relido.global_.mouse is None


# ---------------------------------------------------------------------------
# A vista
# ---------------------------------------------------------------------------
def test_sem_computador_a_vista_e_o_mesmo_objeto() -> None:
    """Quem nunca declarou nada aplica byte a byte o que aplicava."""
    jogo = _perfil(leds={"lightbar": [9, 9, 9]})
    assert opc.perfil_que_vale(jogo, m.MaquinaConfig().computador) is jogo


def test_a_precedencia_campo_a_campo() -> None:
    """O jogo neste controle > o jogo global > o computador neste controle > o todo controle.

    MORDIDA: deixar o computador do P2 vencer a escolha global do jogo põe o verde
    do computador no P2 de um jogo que escolheu vermelho para todos.
    """
    computador = _computador({
        "global": {"leds": {"lightbar": [10, 20, 200], "lightbar_brightness": 0.5},
                   "rumble": {"policy": "max"}},
        "controles": {P2: {"leds": {"lightbar": [0, 255, 0], "lightbar_brightness": 0.3},
                           "rumble": {"motor_forte_pct": 40}}},
    })
    jogo = _perfil(leds={"lightbar": [255, 0, 0]},
                   controllers={P2: {"rumble": {"motor_forte_pct": 80}}})
    vista = opc.perfil_que_vale(jogo, computador)
    assert vista.leds.lightbar == (255, 0, 0)  # o jogo, global
    assert vista.leds.lightbar_brightness == 0.5  # o computador, todo controle
    assert vista.rumble.policy == "max"
    p2 = vista.controllers[P2]
    assert p2.rumble.motor_forte_pct == 80  # o jogo, neste controle
    assert p2.leds.lightbar_brightness == 0.3  # o computador, neste controle
    assert "lightbar" not in p2.leds.model_fields_set  # o jogo global vence


def test_o_valor_de_fabrica_das_secoes_densas_segue_o_computador() -> None:
    """O `leds` que o «Salvar» antigo gravava por extenso não é escolha (a resposta 4)."""
    computador = _computador({"global": {"leds": {"lightbar": [10, 20, 200]}}})
    jogo = _perfil(leds={})  # denso, tudo de fábrica
    assert not opc.sobrepoe(jogo, "luz")
    assert opc.perfil_que_vale(jogo, computador).leds.lightbar == (10, 20, 200)


def test_o_par_da_politica_anda_junto() -> None:
    """O jogo que escolhe a política leva o `custom_mult` junto: nada de par torto."""
    computador = _computador({"global": {"rumble": {"policy": "custom", "custom_mult": 1.7}}})
    jogo = _perfil(rumble={"policy": "max"})
    vista = opc.perfil_que_vale(jogo, computador)
    assert (vista.rumble.policy, vista.rumble.custom_mult) == ("max", None)


def test_o_controle_nunca_visto_nasce_do_computador() -> None:
    """Uma identidade nova, sem linha no perfil nem no computador, recebe o global.

    MORDIDA: cair no de fábrica (a vista não pôr o global do computador no perfil)
    deixa a barra em preto.
    """
    computador = _computador({"global": {"leds": {"lightbar": [10, 20, 200]}}})
    vista = opc.perfil_que_vale(_perfil(), computador)
    assert P3 not in (vista.controllers or {})
    assert vista.leds.lightbar == (10, 20, 200)


def test_os_botoes_e_as_teclas_do_computador_por_baixo_do_jogo() -> None:
    computador = _computador({"global": {
        "button_actions": {"cross": "KEY_ENTER", "circle": "KEY_ESC"},
        "key_bindings": {"triangle": ["KEY_C"]},
        "teclado_emulado": True,
    }})
    jogo = _perfil(button_actions={"circle": "KEY_BACKSPACE"}, key_bindings={})
    vista = opc.perfil_que_vale(jogo, computador)
    assert vista.button_actions == {"cross": "KEY_ENTER", "circle": "KEY_BACKSPACE"}
    assert vista.key_bindings == {}  # o teclado silencioso do jogo vale
    assert vista.teclado_emulado is True


# ---------------------------------------------------------------------------
# O escritor
# ---------------------------------------------------------------------------
def test_o_clique_grava_no_computador_quando_o_jogo_nao_sobrepoe() -> None:
    """O perfil fica byte a byte; o `maquina.json` muda.

    MORDIDA: `onde_grava` devolver sempre o jogo grava no perfil.
    """
    caminho = save_profile(_perfil())
    antes = caminho.read_bytes()
    onde = opc.gravar("luz", {"leds": {"lightbar": [1, 2, 3]}}, uniq=P2,
                      perfil_ativo="Jogo X")
    assert onde == opc.COMPUTADOR
    assert caminho.read_bytes() == antes
    assert opc.o_computador().controles[P2].leds.lightbar == (1, 2, 3)


def test_o_clique_grava_no_jogo_quando_ele_ja_sobrepoe_o_cartao() -> None:
    save_profile(_perfil(controllers={P2: {"leds": {"lightbar": [9, 9, 9]}}}))
    onde = opc.gravar("luz", {"leds": {"lightbar": [1, 2, 3]}}, uniq=P2,
                      perfil_ativo="Jogo X")
    assert onde == opc.JOGO
    assert load_profile("Jogo X").controllers[P2].leds.lightbar == (1, 2, 3)
    assert P2 not in opc.o_computador().controles


def test_a_mudanca_do_gesto_vai_inteira_ao_computador() -> None:
    """`gravar_a_mudanca`: o gesto monta o perfil novo; só a diferença vai ao computador."""
    antes = _perfil(controllers={P1: {"triggers": {"left": {"mode": "Off"}}}})
    save_profile(antes)
    antes = load_profile("Jogo X")
    depois = Profile.model_validate({
        **antes.model_dump(mode="json", exclude_unset=True),
        "controllers": {P1: {"triggers": {"left": {"mode": "Off"}}},
                        P2: {"rumble": {"motor_forte_pct": 30}}},
    })
    assert opc.gravar_a_mudanca("vibracao", antes, depois, uniq=P2) == opc.COMPUTADOR
    assert opc.o_computador().controles[P2].rumble.motor_forte_pct == 30
    assert P2 not in (load_profile("Jogo X").controllers or {})


def test_so_neste_jogo_e_voltar_ao_do_computador() -> None:
    """O jogo copia o que vale e passa a mandar; voltar tira, e o computador volta."""
    _computador({"controles": {P2: {"leds": {"lightbar": [0, 255, 0]}}}})
    save_profile(_perfil())
    opc.so_neste_jogo("luz", P2, "Jogo X")
    jogo = load_profile("Jogo X")
    assert jogo.controllers[P2].leds.lightbar == (0, 255, 0)
    assert opc.marca("luz", jogo, P2) == "Jogo X"
    assert opc.gravar("luz", {"leds": {"lightbar": [255, 0, 0]}}, uniq=P2,
                      perfil_ativo="Jogo X") == opc.JOGO
    assert opc.o_computador().controles[P2].leds.lightbar == (0, 255, 0)
    opc.voltar_ao_do_computador("luz", P2, "Jogo X")
    jogo = load_profile("Jogo X")
    assert opc.marca("luz", jogo, P2) == "Computador"
    assert opc.perfil_que_vale(jogo, opc.o_computador()).controllers[P2].leds.lightbar == (
        0, 255, 0)


def test_o_freestyle_nao_sobrepoe_nada() -> None:
    """Com o Freestyle, o clique grava no computador e o «Só neste jogo» recusa."""
    save_profile(Profile.model_validate({"name": "Freestyle", "match": {"type": "any"},
                                         "leds": {"lightbar": [5, 5, 5]}}))
    assert opc.gravar("luz", {"leds": {"lightbar": [1, 2, 3]}},
                      perfil_ativo="Freestyle") == opc.COMPUTADOR
    with pytest.raises(opc.OFreestyleNaoSobrepoeError):
        opc.so_neste_jogo("luz", P2, "Freestyle")


def test_restaurar_esvazia_o_computador_e_guarda_a_marca_da_migracao() -> None:
    _computador({"global": {"leds": {"lightbar": [1, 2, 3]}}, "migrado": True})
    assert opc.restaurar_o_computador()
    computador = opc.o_computador()
    assert computador.migrado is True
    assert computador.global_.leds is None


# ---------------------------------------------------------------------------
# A peça «Vibração» da economia
# ---------------------------------------------------------------------------
def test_a_economia_diz_que_corta_tambem_a_haptica() -> None:
    """A economia corta a háptica desde 29/09 (``daemon/ganho_da_haptica``)."""
    vibracao = next(p for p in A_ECONOMIA_EM_CADA_PECA if p.nome == "Vibração")
    assert vibracao.o_que_faz == "O teto da Economia, nos dois motores e na háptica."
