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
4. O ESCRITOR que a tela chama, e o que ele deixa no disco.

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
    com_a_economia_do_controle,
    economia_vale,
    gatilho_na_economia,
    leds_na_economia,
    origem_da_economia,
    registrar_teto_da_mesa,
    vibracao_na_economia,
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
    registrar_teto_da_mesa(None)
    yield
    registrar_teto_da_mesa(None)


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
    planos = [(sub_a[0], sub_d[0]) for sub_a, sub_d in zip(antes.params, depois.params, strict=True)]  # type: ignore[index]
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
    assert no_motor == pytest.approx(min(antes, economia)), "a economia puxou para baixo do escolhido"


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
def test_so_o_controle_que_ligou_gasta_menos_e_continua_com_tudo(alvo: int, transporte: str) -> None:
    """O backend de verdade, quatro peças: só a que ligou muda, e nada apaga.

    MORDIDA: em ``ProfileManager.apply``, apague a linha
    ``profile = _perfil_na_economia(...)`` — o alvo recebe o mesmo que os
    outros e o «gasta menos» reprova.
    """
    inst, handles = _mesa_de_quatro(transporte, alvo)
    sem = _o_que_cada_um_recebe(inst, handles, _perfil())
    inst, handles = _mesa_de_quatro(transporte, alvo)
    com = _o_que_cada_um_recebe(
        inst, handles, _perfil({UNIQS[alvo]: ControllerOverrides(economia=True)})
    )
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
    perfil = _perfil({UNIQS[1]: ControllerOverrides(economia=True)})
    perfil = perfil.model_copy(
        update={"leds": perfil.leds.model_copy(update={"player_led_brightness": "forte"})}
    )
    vista = _perfil_na_economia(perfil, mesa=False)
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
    registrar_teto_da_mesa(lambda: "economia")
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
        UNIQS[2]: ControllerOverrides(economia=True),
    })
    vista = _controllers_na_economia(perfil.controllers, perfil, mesa=True)
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

    registrar_teto_da_mesa(quebra)
    assert schema.economia_da_mesa() is False
    registrar_teto_da_mesa(lambda: "balanceado")
    assert schema.economia_da_mesa() is False
    registrar_teto_da_mesa(lambda: "economia")
    assert schema.economia_da_mesa() is True


# ---------------------------------------------------------------------------
# 4. O ESCRITOR — o que a tela chama, e o que fica no disco
# ---------------------------------------------------------------------------


def test_o_escritor_liga_desliga_e_nao_deixa_rastro() -> None:
    """Ligar grava ``true``; desligar APAGA a chave, e a entrada vazia some.

    O resto do override da peça continua parcial: a luz que só falava do
    brilho não passa a falar da cor.

    MORDIDA: faça o escritor gravar ``economia=False`` ao desligar — o disco
    guarda uma chave que um Hefesto de antes recusaria, e reprova.
    """
    parcial = ControllerOverrides(leds=LedsConfig.model_validate({"lightbar_brightness": 0.5}))
    perfil = _perfil({UNIQS[0]: parcial})

    ligado = com_a_economia_do_controle(perfil, UNIQS[0], True)
    assert ligado is not None
    disco = ligado.controllers[UNIQS[0]].model_dump(exclude_unset=True)
    assert disco == {"leds": {"lightbar_brightness": 0.5}, "economia": True}
    assert com_a_economia_do_controle(ligado, UNIQS[0], True) is None

    desligado = com_a_economia_do_controle(ligado, UNIQS[0], False)
    assert desligado is not None
    assert desligado.controllers[UNIQS[0]].model_dump(exclude_unset=True) == {
        "leds": {"lightbar_brightness": 0.5}
    }

    so_ela = com_a_economia_do_controle(_perfil(), UNIQS[3], True)
    assert so_ela is not None
    volta = com_a_economia_do_controle(so_ela, UNIQS[3], False)
    assert volta is not None and UNIQS[3] not in volta.controllers


def test_o_perfil_com_a_economia_atravessa_o_disco(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """``save_profile`` grava a chave e ``load_profile`` a devolve."""
    from hefesto_dualsense4unix.profiles import loader as loader_module

    def fake_profiles_dir(ensure: bool = False) -> Any:
        tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    perfil = com_a_economia_do_controle(_perfil(), UNIQS[2], True)
    assert perfil is not None
    loader_module.save_profile(perfil)
    lido = loader_module.load_profile(perfil.name)
    assert lido.controllers[UNIQS[2]].economia is True
