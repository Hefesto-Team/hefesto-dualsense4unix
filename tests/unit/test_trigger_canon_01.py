"""TRIGGER-CANON-01 — os modos de gatilho contra a enum oficial da Sony."""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS
from hefesto_dualsense4unix.core.trigger_effects import (
    MODOS_DE_DEPURACAO,
    TriggerMode,
    build_from_name,
    custom,
)

_SPEC_POR_NOME = {p.name: p for p in PRESETS}


def _efeito_com_os_padroes(nome: str):
    """O preset como a tela dela o aplica: com os defaults dos controles."""
    spec = _SPEC_POR_NOME[nome]
    return build_from_name(nome, [p.default for p in spec.params])


SENSACAO_APROVADA: dict[str, tuple[int, tuple[int, ...]]] = {
    "Bow": (0x26, (1, 7, 192, 224, 0, 0, 0)),
    "Galloping": (0x26, (0, 9, 7, 7, 10, 0, 0)),
    "Machine": (0x26, (0, 9, 3, 3, 50, 8, 0)),
    "SemiAutoGun": (0x26, (3, 6, 160, 0, 0, 0, 0)),
    "AutoGun": (0x26, (2, 192, 60, 0, 0, 0, 0)),
    "Pulse": (0x02, (0, 0, 0, 0, 0, 0, 0)),
}


@pytest.mark.parametrize("nome", sorted(SENSACAO_APROVADA))
def test_a_sensacao_que_ela_aprovou_nao_muda_um_byte(nome: str) -> None:
    """A prova de regressão da E0-bis, e a mais importante do arquivo."""
    esperado_modo, esperado_forces = SENSACAO_APROVADA[nome]
    efeito = _efeito_com_os_padroes(nome)

    assert int(efeito.mode) == esperado_modo, (
        f"{nome}: o modo mudou de 0x{esperado_modo:02X} para "
        f"0x{int(efeito.mode):02X} — a sensação que ela aprovou mudou junto"
    )
    assert tuple(int(f) for f in efeito.forces) == esperado_forces, (
        f"{nome}: os parâmetros mudaram. Estes bytes são o que a mão dela "
        "aprovou em 01/08 — se a refatoração precisa mudá-los, é a "
        "refatoração que está errada"
    )


def test_a_enum_carrega_os_nomes_da_sony_sobre_os_mesmos_valores() -> None:
    """`RIGID_B` é OFF, e o nome escondia isso."""
    assert TriggerMode.RIGID_B == 0x05
    assert TriggerMode.DESLIGADO_OFICIAL == 0x05
    assert TriggerMode.RIGID_B is TriggerMode.DESLIGADO_OFICIAL

    assert TriggerMode.FEEDBACK == 0x21
    assert TriggerMode.WEAPON == 0x25
    assert TriggerMode.VIBRATION == 0x26
    assert TriggerMode.BOW == 0x22
    assert TriggerMode.GALLOPING == 0x23
    assert TriggerMode.MACHINE == 0x27

    assert TriggerMode.RIGID_A is TriggerMode.FEEDBACK
    assert TriggerMode.RIGID_AB is TriggerMode.WEAPON
    assert TriggerMode.PULSE_AB is TriggerMode.VIBRATION
    assert TriggerMode.PULSE_A is TriggerMode.BOW


def test_os_modos_de_depuracao_sao_recusados() -> None:
    """`0xFC`-`0xFE` CORROMPEM o estado do gatilho, e estavam expostos."""
    assert frozenset({0xFC, 0xFD, 0xFE}) == MODOS_DE_DEPURACAO
    assert not hasattr(TriggerMode, "CALIBRATION")

    for modo in sorted(MODOS_DE_DEPURACAO):
        with pytest.raises(ValueError, match="depuração"):
            custom(modo, (0, 0, 0, 0, 0, 0, 0))

    assert int(custom(0x26, (1, 2, 3, 4, 5, 6, 7)).mode) == 0x26


MODO_ESPERADO_DOS_MORTOS: dict[str, int] = {
    "Rigid": 0x21,
    "SimpleRigid": 0x21,
    "Feedback": 0x21,
    "Resistance": 0x21,
    "SlopeFeedback": 0x21,
    "MultiPositionFeedback": 0x21,
    "MultiPositionVibration": 0x26,
}


@pytest.mark.parametrize("nome", sorted(MODO_ESPERADO_DOS_MORTOS))
def test_os_sete_mortos_deixam_de_mandar_off_ou_lixo(nome: str) -> None:
    """Nenhum dos sete pode continuar mandando `0x05` (OFF) nem `0x22` (Bow).

    O quadro que ela mediu:

    * `Rigid`, `SimpleRigid`, `Feedback` mandavam **`0x05`, que É o OFF**;
    * `Resistance`, `SlopeFeedback`, `MultiPositionFeedback` mandavam `0x25`
      (Weapon oficial) com parâmetros que o firmware recusa — o Weapon espera
      `(1<<início)|(1<<fim)` e uma força `-1`, e o que chegava não formava
      nada válido;
    * `MultiPositionVibration` mandava `0x22` (Bow) com o mesmo problema.

    Todos os sete são, semanticamente, **feedback** — resistência posicional —
    menos o último, que é vibração. É esse o modo oficial que cada um passa a
    mandar.

    Mordida: devolver `TriggerMode.RIGID_B` a qualquer uma das três primeiras
    factories.
    """
    efeito = _efeito_com_os_padroes(nome)
    modo = int(efeito.mode)

    assert modo != 0x05, f"{nome} continua mandando OFF"
    assert modo == MODO_ESPERADO_DOS_MORTOS[nome], (
        f"{nome} manda 0x{modo:02X}, esperado "
        f"0x{MODO_ESPERADO_DOS_MORTOS[nome]:02X}"
    )


@pytest.mark.parametrize("nome", sorted(MODO_ESPERADO_DOS_MORTOS))
def test_os_modos_oficiais_recebem_bitmask_de_zonas_nao_vazio(nome: str) -> None:
    """O segundo erro, ORTOGONAL ao modo — e o que a medição dela provou."""
    efeito = _efeito_com_os_padroes(nome)
    zonas = int(efeito.forces[0]) | (int(efeito.forces[1]) << 8)

    assert zonas != 0, (
        f"{nome}: o bitmask de zonas ativas saiu ZERADO. Com o modo oficial e "
        "nenhuma zona ativa, o firmware não faz nada — que é exatamente o que "
        "ela sentiu"
    )


def test_a_forca_e_codificada_como_forca_menos_um_em_tres_bits() -> None:
    """E os 8 níveis SÃO expressáveis — o que refuta o `FORCA8-01`."""
    from hefesto_dualsense4unix.core.trigger_effects import multi_position_feedback

    efeito = multi_position_feedback([8] + [0] * 9)
    zonas = int(efeito.forces[0]) | (int(efeito.forces[1]) << 8)
    forcas = (
        int(efeito.forces[2])
        | (int(efeito.forces[3]) << 8)
        | (int(efeito.forces[4]) << 16)
        | (int(efeito.forces[5]) << 24)
    )

    assert zonas == 0b1, "só a posição 0 está ativa"
    assert forcas & 0x07 == 7, "força 8 vira 7 nos três bits (8 - 1)"

    efeito_min = multi_position_feedback([1] + [0] * 9)
    zonas_min = int(efeito_min.forces[0]) | (int(efeito_min.forces[1]) << 8)
    forcas_min = int(efeito_min.forces[2])

    assert zonas_min == 0b1, "a zona continua ATIVA com força 1"
    assert forcas_min & 0x07 == 0, "força 1 vira 0 (1 - 1)"


def test_a_frequencia_da_vibracao_vai_para_o_byte_9() -> None:
    """`forces[6]` é o byte 9 do bloco, que é onde mora a frequência."""
    from hefesto_dualsense4unix.core.trigger_effects import multi_position_vibration

    efeito = multi_position_vibration(97, [4] + [0] * 9)

    assert int(efeito.mode) == 0x26
    assert int(efeito.forces[6]) == 97, (
        "a frequência do Vibration oficial mora no byte 9 do bloco, que é "
        "`forces[6]` — e é o único slot que chega lá"
    )


@pytest.mark.parametrize("nome", sorted(_SPEC_POR_NOME))
def test_todo_preset_aceita_os_proprios_parametros_pelo_nome(nome: str) -> None:
    """Os nomes de `trigger_specs` têm de ser os kwargs das factories."""
    spec = _SPEC_POR_NOME[nome]
    if not spec.params:
        return
    params = {p.name: p.default for p in spec.params}
    build_from_name(nome, params)


def test_o_raw_recusa_quando_o_daemon_esta_vivo(monkeypatch, capsys) -> None:
    """*"o instrumento pode estar brigando com o produto"* — em código."""
    import typer

    from hefesto_dualsense4unix.cli import cmd_test

    monkeypatch.setattr(
        "hefesto_dualsense4unix.app.ipc_bridge.daemon_status_basic",
        lambda: {"connected": True},
    )
    tocou_o_hardware: list[object] = []
    monkeypatch.setattr(
        cmd_test, "_apply_on_hardware", lambda acao: tocou_o_hardware.append(acao)
    )

    with pytest.raises(typer.Exit) as saida:
        cmd_test.cmd_trigger(
            side="right", mode="38", params="1,2,3,4,5,6,7", raw=True
        )

    assert saida.value.exit_code == 1
    assert tocou_o_hardware == [], (
        "o --raw NÃO pode chegar ao hardware com o daemon vivo — é a disputa "
        "pelo hidraw que invalida toda medição feita assim"
    )
    impresso = capsys.readouterr().out
    assert "recusado" in impresso
    assert "hidraw" in impresso, "a recusa tem de dizer POR QUÊ"


def test_o_raw_funciona_com_o_daemon_parado(monkeypatch) -> None:
    """E a bancada continua existindo — é para isso que ela serve."""
    from hefesto_dualsense4unix.cli import cmd_test

    monkeypatch.setattr(
        "hefesto_dualsense4unix.app.ipc_bridge.daemon_status_basic", lambda: None
    )
    aplicados: list[object] = []
    monkeypatch.setattr(
        cmd_test, "_apply_on_hardware", lambda acao: aplicados.append(acao)
    )

    cmd_test.cmd_trigger(side="right", mode="38", params="1,2,3,4,5,6,7", raw=True)

    assert len(aplicados) == 1, "com o daemon parado o --raw chega ao hardware"
