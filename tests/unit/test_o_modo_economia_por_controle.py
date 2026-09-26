"""O-MODO-ECONOMIA-POR-CONTROLE-01 (25/09/2026) — gastar menos sem perder feature.

Pedido dela: *«Modo Economia de Bateria (se clica tá setado na economia Low
Iluminação Fraca, Vibraçao Economia, Gatilho (algum de economia pra mantermos
as features funcionando mas gastando menos, entende?)»*
<!-- noqa-acento: citação literal dela -->

O que este arquivo vigia, e a régua que manda sobre todas as outras: **a
economia que desliga uma feature reprova.** A luz fica mais fraca e não apaga,
a vibração ganha teto e não some, o gatilho gasta menos motor e mantém o efeito.

1. CADA PEÇA, sozinha: o gatilho de todo modo que a casa conhece (a lista é a
   das fábricas, nos dois sentidos), a luz e a vibração.
2. O APARELHO: o backend de verdade com quatro controles (P1 a P4, cabo e
   rádio), o que cada um recebe com e sem a economia.
3. A REGRA entre o global e o do controle, e a mesa em «Bateria longa» ligando
   em todos sem cortar a vibração duas vezes.
4. ONDE MORA: na declaração da mesa, ao lado do global — a economia do
   controle atravessa a troca de perfil, e o escritor que a tela manda pelo
   ``machine.declare`` não apaga o resto do controle.

MORDIDAS (o que arrancar para ver reprovar) — cada teste diz a sua no corpo.
MAC só da faixa forjada (aa:bb:cc).
"""
from __future__ import annotations

import importlib
from collections.abc import Iterator
from typing import Any

import pytest

from hefesto_dualsense4unix.core.trigger_effects import PRESET_FACTORIES, build_from_name
from hefesto_dualsense4unix.profiles import schema
from hefesto_dualsense4unix.profiles.manager import (
    ProfileManager,
    _controllers_na_economia,
    _controllers_to_rumble_scales,
    _controllers_to_specs,
    _perfil_na_economia,
)
from hefesto_dualsense4unix.profiles.schema import (
    A_ECONOMIA_EM_CADA_PECA,
    BRILHO_DA_BARRA_NA_ECONOMIA,
    FORCAS_DO_GATILHO,
    MODOS_DE_GATILHO_SEM_FORCA,
    ControllerOverrides,
    ControllerRumbleOverride,
    LedsConfig,
    MatchAny,
    Profile,
    RumbleConfig,
    TriggerConfig,
    controles_em_economia,
    declaracao_da_economia,
    economia_vale,
    gatilho_na_economia,
    leds_na_economia,
    origem_da_economia,
    registrar_declaracao_da_mesa,
    vibracao_na_economia,
)
from hefesto_dualsense4unix.utils.maquina import (
    ControleDeclarado,
    MaquinaConfig,
    OrcamentoDeclarado,
    fundir_declaracao,
)
from tests.unit.test_backend_multi_controller import _FakeHandle, _null_evdev

#: As quatro peças da mesa, na faixa forjada. A chave do backend tem os
#: dois-pontos; a do perfil é o `uniq` normalizado.
CHAVES = ("AA:BB:CC:00:00:01", "AA:BB:CC:00:00:02", "AA:BB:CC:00:00:03", "AA:BB:CC:00:00:04")
UNIQS = tuple(c.replace(":", "").lower() for c in CHAVES)

#: Parâmetros válidos de cada modo — todo modo que tem força tem a força ACESA
#: aqui, para que "a economia apagou" seja visível.
AMOSTRAS: dict[str, list[Any]] = {
    "Off": [],
    "Rigid": [5, 200],
    "SimpleRigid": [8],
    "Pulse": [],
    "PulseA": [2, 7, 200],
    "PulseB": [2, 7, 200],
    "Resistance": [3, 8],
    "Bow": [1, 6, 8, 8],
    "Galloping": [1, 6, 3, 5, 20],
    "SemiAutoGun": [2, 6, 8],
    "AutoGun": [3, 8, 20],
    "Machine": [1, 8, 200, 150, 20, 10],
    "Feedback": [2, 8],
    "Weapon": [2, 7, 200],
    "Vibration": [2, 8, 30],
    "SlopeFeedback": [1, 8, 2, 8],
    "MultiPositionFeedback": [0, 1, 2, 3, 4, 5, 6, 7, 8, 8],
    "MultiPositionVibration": [30, 0, 1, 2, 3, 4, 5, 6, 7, 8, 8],
    "Custom": [0x21, 1, 2, 3, 4, 5, 6, 7],
}


@pytest.fixture(autouse=True)
def _mesa_sem_registro() -> Iterator[None]:
    """A fonte da mesa é estado de módulo: cada teste começa e termina sem ela."""
    registrar_declaracao_da_mesa(None)
    yield
    registrar_declaracao_da_mesa(None)


def _declarar(teto: str | None = None, economia: tuple[str, ...] = ()) -> MaquinaConfig:
    """A declaração da mesa que o daemon teria — e registrada como a viva."""
    maquina = MaquinaConfig(
        orcamento=OrcamentoDeclarado(teto=teto),  # type: ignore[arg-type]
        controles={u: ControleDeclarado(economia=True) for u in economia},
    )
    registrar_declaracao_da_mesa(lambda: maquina)
    return maquina


# ---------------------------------------------------------------------------
# 1. CADA PEÇA — a economia não desliga nada
# ---------------------------------------------------------------------------


def test_todo_modo_de_gatilho_esta_classificado_nos_dois_sentidos() -> None:
    """Modo novo nas fábricas sem linha aqui reprova; linha sem modo também.

    MORDIDA: tire o ``"Vibration"`` de ``FORCAS_DO_GATILHO`` e veja reprovar
    nomeando o modo — ele passaria a ir ao aparelho com a força inteira.
    """
    classificados = set(FORCAS_DO_GATILHO) | set(MODOS_DE_GATILHO_SEM_FORCA)
    assert sorted(set(PRESET_FACTORIES) - classificados) == []
    assert sorted(classificados - set(PRESET_FACTORIES)) == []
    assert set(AMOSTRAS) == set(PRESET_FACTORIES)


@pytest.mark.parametrize("modo", sorted(PRESET_FACTORIES))
def test_o_gatilho_na_economia_mantem_o_efeito_e_gasta_menos(modo: str) -> None:
    """O mesmo modo no aparelho, as mesmas zonas acesas, e força menor ou igual.

    É a régua do pedido dela: *«pra mantermos as features funcionando mas
    gastando menos»*. Força que era maior que zero continua maior que zero —
    a zona que resistia continua resistindo.

    MORDIDA: faça ``schema._forca_na_economia`` devolver ``0`` e todo modo com
    força reprova no «apagou»; faça devolver ``valor`` e reprova no «gasta
    menos».
    """
    antes = TriggerConfig(mode=modo, params=list(AMOSTRAS[modo]))
    depois = gatilho_na_economia(antes)
    assert depois.mode == antes.mode
    efeito_antes = build_from_name(antes.mode, antes.params)
    efeito_depois = build_from_name(depois.mode, depois.params)
    assert efeito_depois.mode == efeito_antes.mode, "a economia trocou o efeito"
    forcas = FORCAS_DO_GATILHO.get(modo, ())
    params_antes = list(antes.params)
    params_depois = list(depois.params)
    for i, (a, d) in enumerate(zip(params_antes, params_depois, strict=True)):
        if i in forcas:
            assert (a > 0) == (d > 0), f"{modo}[{i}]: a economia apagou a força {a}"
            assert d <= a
        else:
            assert d == a, f"{modo}[{i}]: a economia mexeu em posição/tempo"
    if forcas and any(params_antes[i] > 1 for i in forcas if i < len(params_antes)):
        assert params_depois != params_antes, f"{modo}: a economia não gastou menos"


def test_o_gatilho_aninhado_tambem_entra_na_economia() -> None:
    """O formato de zonas (`list[list[int]]`) é todo força, e nenhuma zona apaga."""
    antes = TriggerConfig(
        mode="MultiPositionFeedback", params=[[0], [1], [2], [3], [4], [5], [6], [7], [8], [8]]
    )
    depois = gatilho_na_economia(antes)
    pares = zip(antes.params, depois.params, strict=True)
    planos = [(sub_a[0], sub_d[0]) for sub_a, sub_d in pares]  # type: ignore[index]
    assert all((a > 0) == (d > 0) and d <= a for a, d in planos)
    assert planos[-1] == (8, 4)
    build_from_name(depois.mode, depois.params)


def test_a_luz_fica_mais_fraca_e_nao_apaga() -> None:
    """Barra no teto e acesa; luzes de número no Fraco; a cor não é escrita.

    MORDIDA: ponha ``BRILHO_DA_BARRA_NA_ECONOMIA = 0.0`` e o «apagou» reprova.
    """
    assert 0.0 < BRILHO_DA_BARRA_NA_ECONOMIA < 1.0
    do_perfil = LedsConfig(lightbar=(0, 0, 255), lightbar_brightness=1.0,
                           player_led_brightness="forte")
    dele = leds_na_economia(None, do_perfil)
    assert dele is not None
    assert dele.lightbar_brightness == BRILHO_DA_BARRA_NA_ECONOMIA
    assert dele.lightbar_brightness > 0.0, "a economia apagou a barra"
    assert dele.player_led_brightness == "fraco"
    assert "lightbar" not in dele.model_fields_set, "a economia escreveu a cor"
    assert "player_leds" not in dele.model_fields_set

    # TETO, nunca troca: quem escolheu menos continua no que escolheu, e o
    # apagado por escolha dela continua apagado.
    fraca = leds_na_economia(LedsConfig.model_validate({"lightbar_brightness": 0.1}), do_perfil)
    assert fraca is not None and fraca.lightbar_brightness == 0.1
    apagada = leds_na_economia(LedsConfig.model_validate({"lightbar_brightness": 0.0}), do_perfil)
    assert apagada is not None and apagada.lightbar_brightness == 0.0


def _mult(policy: str | None, custom: float | None = None) -> float:
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    if policy == "custom":
        assert custom is not None
        return custom
    return RUMBLE_POLICY_MULT[policy or "balanceado"]


@pytest.mark.parametrize("da_peca", [None, "balanceado", "max", "economia", "custom"])
@pytest.mark.parametrize("do_perfil", [None, "economia", "balanceado", "max"])
def test_a_vibracao_tem_teto_e_nao_some(da_peca: str | None, do_perfil: str | None) -> None:
    """O que chega ao motor fica no degrau Economia ou abaixo, e nunca em zero.

    A conta é a do produto: o fator por peça é ``mult_da_peca / mult_do_perfil``
    (``_controllers_to_rumble_scales``), sobre o que a política do perfil já
    deixou passar.

    MORDIDA: em ``vibracao_na_economia``, devolva ``dela`` sempre — a peça em
    «Máximo» chega a 150% e reprova no teto.
    """
    custom = 0.2 if da_peca == "custom" else None
    dela = (
        None
        if da_peca is None
        else ControllerRumbleOverride(policy=da_peca, custom_mult=custom)  # type: ignore[arg-type]
    )
    nova = vibracao_na_economia(dela, do_perfil, mesa=False)
    fator = _controllers_to_rumble_scales(
        {UNIQS[0]: ControllerOverrides(rumble=nova)} if nova is not None else {},
        RumbleConfig(policy=do_perfil),  # type: ignore[arg-type]
    ).get(UNIQS[0], 1.0)
    no_motor = _mult(do_perfil) * fator
    economia = _mult("economia")
    antes = _mult(do_perfil) if dela is None else _mult(da_peca, custom)
    assert no_motor > 0.0, "a economia calou o motor"
    assert no_motor <= economia + 1e-9, f"passou do teto: {no_motor}"
    assert no_motor == pytest.approx(min(antes, economia)), (
        "a economia puxou para baixo do escolhido")


def test_as_barras_de_motor_sobrevivem_a_economia() -> None:
    """As barras só reduzem, e são escolha dela: a economia não as apaga."""
    dela = ControllerRumbleOverride(policy="max", motor_fraco_pct=50)
    nova = vibracao_na_economia(dela, "balanceado")
    assert nova is not None
    assert nova.policy == "economia"
    assert nova.motor_fraco_pct == 50
    assert "motor_forte_pct" not in nova.model_fields_set


def test_toda_peca_da_tabela_tem_ponto_de_aplicacao_ou_razao() -> None:
    """A tabela é o dono do que a economia faz: ponto importável, ou a razão.

    MORDIDA: troque o ponto do «Gatilhos» por ``schema:gatilho_que_nao_existe``.
    """
    nomes = [p.nome for p in A_ECONOMIA_EM_CADA_PECA]
    assert {"Barra de luz", "Luzes de número", "Vibração", "Gatilhos"} <= set(nomes)
    for peca in A_ECONOMIA_EM_CADA_PECA:
        assert peca.o_que_faz.strip(), peca.nome
        if peca.ponto_de_aplicacao is None:
            continue
        modulo, atributo = peca.ponto_de_aplicacao.split(":")
        assert callable(getattr(importlib.import_module(modulo), atributo)), peca.nome


# ---------------------------------------------------------------------------
# 2. O APARELHO — P1 a P4, cabo e rádio
# ---------------------------------------------------------------------------


def _mesa_de_quatro(transporte_do_alvo: str, alvo: int) -> tuple[Any, list[_FakeHandle]]:
    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    inst = PyDualSenseController(evdev_reader=_null_evdev())
    transportes = ["USB", "BT", "USB", "BT"]
    transportes[alvo] = transporte_do_alvo
    handles = [_FakeHandle(transport_name=t) for t in transportes]
    inst._handles = dict(zip(CHAVES, handles, strict=True))
    inst._primary_key = CHAVES[0]
    return inst, handles


def _perfil(controllers: dict[str, ControllerOverrides] | None = None) -> Profile:
    return Profile(
        name="economia",
        match=MatchAny(),
        leds=LedsConfig(lightbar=(0, 0, 255), lightbar_brightness=1.0),
        rumble=RumbleConfig(policy="balanceado"),
        controllers=controllers or {},
    )


def _o_que_cada_um_recebe(inst: Any, handles: list[_FakeHandle], perfil: Profile) -> list[tuple]:
    ProfileManager(controller=inst).apply(perfil)
    inst.set_rumble(weak=200, strong=200)
    return [
        (h.light.colors[-1], h.triggerL.mode, list(h.triggerL.forces),
         list(h.triggerR.forces), h.left_motor[-1], h.right_motor[-1])
        for h in handles
    ]


@pytest.mark.parametrize("transporte", ["USB", "BT"])
@pytest.mark.parametrize("alvo", [0, 1, 2, 3], ids=["P1", "P2", "P3", "P4"])
def test_so_o_controle_que_ligou_gasta_menos_e_continua_com_tudo(
    alvo: int, transporte: str
) -> None:
    """O backend de verdade, quatro peças: só a que ligou muda, e nada apaga.

    O perfil NÃO cita a peça: a economia é do controle (declaração da mesa), e
    vale no perfil que estiver ativo.

    MORDIDA: em ``ProfileManager.apply``, apague a linha
    ``profile = _perfil_na_economia(...)`` — o alvo recebe o mesmo que os
    outros e o «gasta menos» reprova.
    """
    inst, handles = _mesa_de_quatro(transporte, alvo)
    sem = _o_que_cada_um_recebe(inst, handles, _perfil())
    _declarar(economia=(UNIQS[alvo],))
    inst, handles = _mesa_de_quatro(transporte, alvo)
    com = _o_que_cada_um_recebe(inst, handles, _perfil())
    for i in range(4):
        if i != alvo:
            assert com[i] == sem[i], f"P{i + 1} mudou sem ter ligado a economia"
    cor_sem, modo_sem, l_sem, r_sem, forte_sem, fraco_sem = sem[alvo]
    cor_com, modo_com, l_com, r_com, forte_com, fraco_com = com[alvo]
    # A LUZ: mais fraca, acesa, e na mesma cor.
    assert 0 < max(cor_com) < max(cor_sem)
    assert [c > 0 for c in cor_com] == [c > 0 for c in cor_sem]
    # O GATILHO: o mesmo efeito, com menos força.
    assert modo_com == modo_sem
    assert l_com != l_sem and r_com != r_sem
    # A VIBRAÇÃO: no degrau Economia, e viva.
    assert 0 < forte_com < forte_sem and 0 < fraco_com < fraco_sem
    assert forte_com == round(forte_sem * _mult("economia"))


def test_as_luzes_de_numero_do_controle_vao_ao_fraco() -> None:
    """O degrau das luzes de número sai no `OutputSpec` da peça, e só dela."""
    perfil = _perfil()
    perfil = perfil.model_copy(
        update={"leds": perfil.leds.model_copy(update={"player_led_brightness": "forte"})}
    )
    vista = _perfil_na_economia(perfil, mesa=False, em_economia=frozenset({UNIQS[1]}))
    specs = _controllers_to_specs(vista.controllers, vista.leds)
    from hefesto_dualsense4unix.core.led_control import degrau_do_brilho_das_luzes

    assert specs[UNIQS[1]].player_led_brightness == degrau_do_brilho_das_luzes("fraco")
    assert UNIQS[0] not in specs


# ---------------------------------------------------------------------------
# 3. A REGRA — a mesa e o controle
# ---------------------------------------------------------------------------


def test_a_regra_entre_a_mesa_e_o_controle() -> None:
    """Vale se a mesa pedir OU o controle ligar; o controle não desliga a mesa.

    MORDIDA: troque o ``or`` de ``economia_vale`` por ``and``.
    """
    assert economia_vale(None, False) is False
    assert economia_vale(False, False) is False
    assert economia_vale(True, False) is True
    assert economia_vale(None, True) is True
    assert economia_vale(False, True) is True
    assert origem_da_economia(True, True) == "mesa"
    assert origem_da_economia(True, False) == "controle"
    assert origem_da_economia(None, False) is None


def test_a_mesa_em_bateria_longa_liga_a_economia_em_todos() -> None:
    """«Bateria longa» na aba Sistema: os quatro gastam menos, e nenhum apaga.

    A chave é a do disco (``economia``), lida pela fonte que o daemon registra
    — a MESMA do teto de vibração. E a vibração NÃO é cortada de novo aqui: o
    funil (``core.rumble._effective_mult``) já a corta para a mesa inteira.

    MORDIDA: em ``_perfil_na_economia``, apague o ramo ``if mesa:`` — a luz
    dos quatro volta inteira e reprova.
    """
    inst, handles = _mesa_de_quatro("BT", 1)
    sem = _o_que_cada_um_recebe(inst, handles, _perfil())
    _declarar(teto="economia")
    inst, handles = _mesa_de_quatro("BT", 1)
    com = _o_que_cada_um_recebe(inst, handles, _perfil())
    for i in range(4):
        assert 0 < max(com[i][0]) < max(sem[i][0]), f"P{i + 1}: a luz não caiu"
        assert com[i][1] == sem[i][1], f"P{i + 1}: o gatilho trocou de efeito"
        assert com[i][2] != sem[i][2], f"P{i + 1}: o gatilho não gastou menos"
        assert com[i][4] == sem[i][4], f"P{i + 1}: a vibração foi cortada duas vezes"


def test_sob_a_mesa_a_peca_nao_fura_o_teto_nem_corta_duas_vezes() -> None:
    """A peça em «Máximo» perde o que amplifica; a em «Economia» fica.

    Sob a mesa o funil já corta no degrau Economia, então a peça só não pode
    ter fator acima de 1 — e não pode ganhar um fator a mais abaixo disso.
    """
    perfil = _perfil({
        UNIQS[0]: ControllerOverrides(rumble=ControllerRumbleOverride(policy="max")),
        UNIQS[1]: ControllerOverrides(rumble=ControllerRumbleOverride(policy="economia")),
    })
    vista = _controllers_na_economia(
        perfil.controllers, perfil, mesa=True, em_economia=frozenset({UNIQS[2]})
    )
    escalas = _controllers_to_rumble_scales(vista, perfil.rumble)
    assert escalas.get(UNIQS[0], 1.0) == 1.0
    assert escalas[UNIQS[1]] == pytest.approx(_mult("economia"))
    assert UNIQS[2] not in escalas


def test_perfil_sem_economia_sai_identico() -> None:
    """Quem não ligou nada tem a ativação de antes desta sprint, o MESMO objeto."""
    perfil = _perfil({UNIQS[0]: ControllerOverrides(rumble=ControllerRumbleOverride(policy="max"))})
    assert _perfil_na_economia(perfil, mesa=False) is perfil


def test_fonte_da_mesa_que_levanta_nao_derruba_a_ativacao() -> None:
    """Declaração ilegível é mesa sem economia — nunca exceção na ativação."""

    def quebra() -> str:
        raise OSError("maquina.json ilegível")

    registrar_declaracao_da_mesa(quebra)
    assert schema.economia_da_mesa() is False
    assert controles_em_economia() == frozenset()
    _declarar(teto="balanceado")
    assert schema.economia_da_mesa() is False
    _declarar(teto="economia", economia=(UNIQS[2],))
    assert schema.economia_da_mesa() is True
    assert controles_em_economia() == frozenset({UNIQS[2]})


# ---------------------------------------------------------------------------
# 4. ONDE MORA — a declaração da mesa, ao lado do global
# ---------------------------------------------------------------------------


def test_a_economia_do_controle_atravessa_a_troca_de_perfil() -> None:
    """Ligada no P2, ela vale no perfil do jogo que abrir depois.

    É a razão de ela morar na declaração da mesa e não no perfil: a bateria é
    do controle. No perfil, a troca automática para o perfil de um jogo a
    apagaria, e ela teria de ligar de novo em cada jogo.

    MORDIDA: em ``ProfileManager.apply``, passe ``frozenset()`` no lugar de
    ``controles_em_economia()`` — o P2 volta a gastar tudo e reprova.
    """
    _declarar(economia=(UNIQS[1],))
    outro = Profile(name="um_jogo", match=MatchAny(),
                    leds=LedsConfig(lightbar=(255, 0, 0), lightbar_brightness=1.0))
    for perfil in (_perfil(), outro):
        inst, handles = _mesa_de_quatro("BT", 1)
        recebido = _o_que_cada_um_recebe(inst, handles, perfil)
        assert max(recebido[1][0]) < max(recebido[0][0]), perfil.name
        assert recebido[1][4] < recebido[0][4], perfil.name


def test_o_escritor_liga_desliga_e_nao_apaga_o_resto_do_controle() -> None:
    """O corpo do ``machine.declare``: liga com ``true``, desliga com ``null``.

    A fusão desce no dicionário, então o microfone e a cor do mesmo controle
    ficam. E desligar é ``null`` presente (sobrescreve), nunca a chave ausente.

    MORDIDA: faça o desligar omitir a chave — a economia fica ligada no disco
    e o «desligado» reprova.
    """
    disco = MaquinaConfig(
        controles={UNIQS[1]: ControleDeclarado(microfone=False, cor="Cobalt Blue")}
    ).model_dump()
    ligado = fundir_declaracao(disco, declaracao_da_economia("AA:BB:CC:00:00:02", True))
    maquina = MaquinaConfig.model_validate(ligado)
    assert maquina.controles[UNIQS[1]].economia is True
    assert maquina.controles[UNIQS[1]].microfone is False
    assert maquina.controles[UNIQS[1]].cor == "Cobalt Blue"
    registrar_declaracao_da_mesa(lambda: maquina)
    assert controles_em_economia() == frozenset({UNIQS[1]})

    desligado = MaquinaConfig.model_validate(
        fundir_declaracao(ligado, declaracao_da_economia(UNIQS[1], False))
    )
    assert desligado.controles[UNIQS[1]].economia is None
    assert desligado.controles[UNIQS[1]].microfone is False
    registrar_declaracao_da_mesa(lambda: desligado)
    assert controles_em_economia() == frozenset()

    with pytest.raises(ValueError):
        declaracao_da_economia("nao-e-endereco", True)


def test_a_economia_atravessa_o_disco() -> None:
    """``gravar_maquina_com_descartes`` grava a chave e ``carregar_maquina`` a lê."""
    from pathlib import Path

    from hefesto_dualsense4unix.utils import maquina as maquina_mod

    assert not str(maquina_mod.caminho_da_maquina()).startswith(
        str(Path("/home/vitoriamaria/.config"))
    ), "a suíte ia escrever no maquina.json dela"
    resultado = maquina_mod.gravar_maquina_com_descartes(
        declaracao_da_economia(UNIQS[3], True)
    )
    assert resultado.gravou
    lida = maquina_mod.carregar_maquina()
    registrar_declaracao_da_mesa(lambda: lida)
    assert controles_em_economia() == frozenset({UNIQS[3]})


def test_a_tabela_do_teto_diz_de_cada_peca_o_que_a_economia_faz() -> None:
    """A «Bateria longa» na tabela do teto: cada linha com ponto diz a SUA frase.

    A luz e os gatilhos ganharam ponto com esta sprint; a célula deles não pode
    herdar o percentual da vibração (o gatilho vai a metade, não a 30%).

    MORDIDA: em ``secao_orcamento.celula_do_perfil``, devolva
    ``celula_do_teto(chave)`` para toda linha — o «Gatilhos» passa a dizer
    «30% da força» e reprova.
    """
    pytest.importorskip("gi")
    from hefesto_dualsense4unix.app.actions.config import secao_orcamento as orc

    pecas = {p.nome: p for p in A_ECONOMIA_EM_CADA_PECA}
    for linha in orc.LINHAS_DO_TETO:
        if not linha.tem_ponto or linha.nome == "Vibração":
            continue
        assert linha.nome in pecas and pecas[linha.nome].ponto_de_aplicacao, linha.nome
        longa = orc.celula_do_perfil(orc.PERFIL_BATERIA_LONGA, linha)
        assert longa == pecas[linha.nome].o_que_faz, (linha.nome, longa)
        assert orc.celula_do_perfil(orc.PERFIL_TUDO_LIGADO, linha) == orc.SEM_TETO
        assert orc.celula_do_perfil(orc.PERFIL_EU_ESCOLHO, linha) == orc.CADA_ABA_MANDA


@pytest.mark.asyncio
async def test_o_daemon_registra_a_declaracao_no_boot_e_solta_ao_parar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O daemon vivo responde pela mesa; parado, deixa de responder.

    A medição é DURANTE o laço (capturada antes do ``stop``) e DEPOIS dele —
    um teste que só olhasse depois do ``stop`` daria verde sobre tudo.

    MORDIDA: em ``Daemon.run``, apague o ``registrar_declaracao_da_mesa(...)``
    do boot — o «durante» reprova; apague o ``_soltar_a_mesa(None)`` do
    ``finally`` — o «depois» reprova.
    """
    import asyncio

    from hefesto_dualsense4unix.core.controller import ControllerState
    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController
    from hefesto_dualsense4unix.utils import maquina as maquina_mod

    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
    )
    maquina_mod.gravar_maquina_com_descartes({
        "orcamento": {"teto": "economia"},
        "controles": {UNIQS[1]: {"economia": True}},
    })
    estado = ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )
    store = StateStore()
    daemon = Daemon(
        controller=FakeController(transport="usb", states=[estado]),
        bus=EventBus(), store=store,
        config=DaemonConfig(
            poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
            autoswitch_enabled=False, mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False, ps_button_action="none",
            mic_button_toggles_system=False,
        ),
    )
    tarefa = asyncio.create_task(daemon.run())
    for _ in range(500):
        if store.counter("poll.tick") >= 1:
            break
        await asyncio.sleep(0.01)
    durante = (schema.economia_da_mesa(), controles_em_economia())
    daemon.stop()
    await tarefa
    depois = (schema.economia_da_mesa(), controles_em_economia())
    assert durante == (True, frozenset({UNIQS[1]})), durante
    assert depois == (False, frozenset()), depois


def test_o_daemon_reaplica_o_perfil_so_quando_a_economia_muda(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O clique no botão chega ao aparelho na hora — e só o clique da economia.

    ``machine.declare`` rebinda ``_maquina``; quem rebinda chama
    ``reaplicar_se_a_economia_mudou`` com a declaração de antes. Mudou a
    economia (a da mesa OU a de um controle): o perfil corrente é reaplicado.
    Mudou outra coisa (a cor do plástico): nada. Em Modo Nativo: nada — a
    saída do nativo reaplica.

    MORDIDA: faça o método devolver ``False`` sem comparar — o «ligou no P2»
    reprova; tire a guarda do nativo — o último reprova.
    """
    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing import FakeController

    daemon = Daemon(
        controller=FakeController(transport="usb", states=[]),
        bus=EventBus(), store=StateStore(), config=DaemonConfig(),
    )
    chamadas: list[int] = []
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: chamadas.append(1))

    antes = MaquinaConfig()
    daemon._maquina = MaquinaConfig(controles={UNIQS[1]: ControleDeclarado(economia=True)})
    assert daemon.reaplicar_se_a_economia_mudou(antes) is True
    assert chamadas == [1], "ligou no P2 e o perfil não foi reaplicado"

    mesma = daemon._maquina
    daemon._maquina = mesma.model_copy(
        update={"controles": {UNIQS[1]: ControleDeclarado(economia=True, cor="Cobalt Blue")}}
    )
    assert daemon.reaplicar_se_a_economia_mudou(mesma) is False
    assert chamadas == [1], "a cor mudou e o perfil foi reaplicado à toa"

    daemon._maquina = MaquinaConfig(orcamento=OrcamentoDeclarado(teto="economia"))
    daemon._native_mode = True
    assert daemon.reaplicar_se_a_economia_mudou(antes) is False
    assert chamadas == [1], "em Modo Nativo o controle está com o jogo"
