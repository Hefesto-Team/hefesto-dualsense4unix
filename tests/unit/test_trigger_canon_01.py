"""TRIGGER-CANON-01 — os modos de gatilho contra a enum oficial da Sony.

**Sete dos dezenove presets não faziam absolutamente nada**, e ela conviveu
com isso sem saber. A medição é dela, pelo tato, em 01/08/2026, pela aba
Gatilhos (que passa pelo daemon — o caminho `--raw` da CLI briga pelo hidraw
e imprime "aplicado" sem aplicar):

    "rígido e desligado sem diferença"
    "resistência nada também"
    "arco, galope e pulso e metralhadora funcionam"

E a correção dela, que INVERTEU metade da sprint. Perguntada se Arco, Galope e
Metralhadora eram iguais entre si — todos mandam `0x26` —, ela respondeu
*"eles são bem diferentes viu"*, e depois:

    "cara, as duas temos nomes perfeitos, pq essa é a sensação de usar ambas —
     e ambas são diferentes em si e diferentes do desligar"

**Isso é aceite de produto.** Os parâmetros "acidentais" dos cinco que
funcionam produzem sensações que casam com o nome. Eles deixaram de ser
implementação e viraram DADO — e este arquivo é a prova de regressão que a
sprint pediu para que a refatoração não os mude.
"""

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
    """O preset como a tela dela o aplica: com os defaults dos controles.

    É esta a combinação que ela sentiu — os defaults do `trigger_specs` são o
    que a aba Gatilhos mostra ao escolher o preset, e ela aplicou sem mexer
    nos controles deslizantes.
    """
    spec = _SPEC_POR_NOME[nome]
    return build_from_name(nome, [p.default for p in spec.params])


# ---------------------------------------------------------------------------
# E0-bis — a sensação aprovada por ela, travada byte a byte
# ---------------------------------------------------------------------------

#: Os bytes EXATOS que os seis presets aprovados produzem, capturados em
#: 01/08/2026 ANTES de qualquer refatoração desta sprint.
#:
#: **Estes números são dado, não implementação.** Eles são o que a mão dela
#: aprovou, e o que ela sente quando escolhe "Arco" ou "Galope" na tela. O
#: mecanismo por trás deles é acidental — os cinco mandam o modo `0x26`
#: (Vibration oficial), e `forces[0]`/`forces[1]` caem em cima do bitmask de
#: zonas ativas, então cada preset produz um bitmask diferente e o firmware
#: responde a cada um de um jeito. Acidental ou não, o resultado passou no
#: único teste que importa aqui, que é o tato dela.
#:
#: Qualquer mudança nestes bytes muda o que ela sente. Se uma refatoração
#: reprovar aqui, **a refatoração está errada, não a sensação**.
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
    """A prova de regressão da E0-bis, e a mais importante do arquivo.

    Ela testou estes seis na aba Gatilhos e disse que os nomes estão certos
    porque a SENSAÇÃO está certa. A sprint tinha como objetivo original "fazer
    os nomes corresponderem à enum da Sony", e o aceite dela inverteu isso: o
    nome do preset descreve a sensação, não o modo do fio.

    Mordida: mudar um único byte de qualquer um dos seis.
    """
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


# ---------------------------------------------------------------------------
# E1 — a enum passa a nomear o que a Sony nomeia
# ---------------------------------------------------------------------------


def test_a_enum_carrega_os_nomes_da_sony_sobre_os_mesmos_valores() -> None:
    """`RIGID_B` é OFF, e o nome escondia isso.

    A nomenclatura opaca (`Rigid_A/B/AB`, `Pulse_A/B/AB`) veio de uma
    engenharia reversa de 2020 e não é da Sony. Decodificada contra a enum
    oficial (que a Valve redistribui no Steamworks SDK, com o cabeçalho de
    copyright da Sony verbatim) e contra três engenharias reversas
    independentes que concordam entre si, `RIGID_B` vale `0x05`, que é
    literalmente **OFF**.

    Os nomes antigos ficam como ALIAS, e isso não é indecisão: eles estão em
    perfis no disco dela e no `docs/protocol/trigger-modes.md`. Um `IntEnum`
    resolve os dois nomes para o mesmo membro, então nada quebra e o código
    novo lê o nome honesto.

    Mordida: apagar `FEEDBACK`/`WEAPON`/`VIBRATION` da enum.
    """
    assert TriggerMode.RIGID_B == 0x05
    assert TriggerMode.DESLIGADO_OFICIAL == 0x05
    assert TriggerMode.RIGID_B is TriggerMode.DESLIGADO_OFICIAL

    assert TriggerMode.FEEDBACK == 0x21
    assert TriggerMode.WEAPON == 0x25
    assert TriggerMode.VIBRATION == 0x26
    assert TriggerMode.BOW == 0x22
    assert TriggerMode.GALLOPING == 0x23
    assert TriggerMode.MACHINE == 0x27

    # E os aliases antigos continuam resolvendo para o mesmo membro.
    assert TriggerMode.RIGID_A is TriggerMode.FEEDBACK
    assert TriggerMode.RIGID_AB is TriggerMode.WEAPON
    assert TriggerMode.PULSE_AB is TriggerMode.VIBRATION
    assert TriggerMode.PULSE_A is TriggerMode.BOW


def test_os_modos_de_depuracao_sao_recusados() -> None:
    """`0xFC`-`0xFE` CORROMPEM o estado do gatilho, e estavam expostos.

    O `CALIBRATION = 0xFC` era um membro público da enum, alcançável pelo
    preset `Custom` — que é o escape hatch documentado como "útil para
    experimentação". Experimentar com ele deixa o gatilho num estado que só
    sai desligando o controle.

    A recusa é um `ValueError`, e não um clamp silencioso: quem pediu `0xFC`
    pediu de propósito, e trocar por outro valor sem avisar seria mentir
    sobre o que foi enviado.

    Mordida: apagar o guarda do `custom()`.
    """
    assert frozenset({0xFC, 0xFD, 0xFE}) == MODOS_DE_DEPURACAO
    assert not hasattr(TriggerMode, "CALIBRATION")

    for modo in sorted(MODOS_DE_DEPURACAO):
        with pytest.raises(ValueError, match="depuração"):
            custom(modo, (0, 0, 0, 0, 0, 0, 0))

    # E um modo normal continua passando — o guarda não é um muro genérico.
    assert int(custom(0x26, (1, 2, 3, 4, 5, 6, 7)).mode) == 0x26


# ---------------------------------------------------------------------------
# E2 — os sete que não faziam nada passam a fazer
# ---------------------------------------------------------------------------

#: Os sete presets que ela mediu (ou que compartilham a causa dos medidos)
#: como sem efeito nenhum, e o modo OFICIAL que cada um passa a mandar.
#:
#: Por que só os OFICIAIS somem quando o empacotamento está errado: os modos
#: oficiais VALIDAM os parâmetros; os legados e os não oficiais não validam.
#: É por isso que os cinco de `0x26` funcionavam com parâmetros acidentais e
#: os de `0x25` não funcionavam com nenhum.
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
    """O segundo erro, ORTOGONAL ao modo — e o que a medição dela provou.

    Os modos oficiais **não recebem posições cruas**: recebem um bitmask de
    zonas ativas (u16 LE, bytes 1-2 do bloco) e forças de 3 bits com valor
    `força - 1` (u32 LE, bytes 3-6). Sem o bitmask, o firmware vê **nenhuma
    zona ativa** e não faz nada — o que explica por que o `0x25`, que é o
    Weapon OFICIAL, não fez nada nas mãos dela.

    Este teste é o que separa "trocou o número do modo" de "arrumou o
    empacotamento": um bitmask zerado com o modo certo continua sendo nada.

    Mordida: zerar o bitmask (`forces[0] = forces[1] = 0`) em qualquer
    factory.
    """
    efeito = _efeito_com_os_padroes(nome)
    zonas = int(efeito.forces[0]) | (int(efeito.forces[1]) << 8)

    assert zonas != 0, (
        f"{nome}: o bitmask de zonas ativas saiu ZERADO. Com o modo oficial e "
        "nenhuma zona ativa, o firmware não faz nada — que é exatamente o que "
        "ela sentiu"
    )


def test_a_forca_e_codificada_como_forca_menos_um_em_tres_bits() -> None:
    """E os 8 níveis SÃO expressáveis — o que refuta o `FORCA8-01`.

    O `BUG-TRIGGER-MULTIPOS-FORCA8-01` foi registrado como MEDIDO e concluiu
    *"o campo tem 3 bits, logo o máximo real é 7 e a força 8 satura"*. A
    conclusão está errada na causa: a codificação real é `(força - 1) & 0x07`
    com `força` em 1..8, e `força == 0` significa **zona inativa** — o que se
    expressa no bitmask, não no campo de força.

    Ou seja: `força 8` cabe (vira `7` nos três bits) e `força 1` cabe (vira
    `0`), e as duas são distinguíveis porque a zona está marcada no bitmask.

    Mordida: voltar a saturar 8 em 7 antes de subtrair 1.
    """
    from hefesto_dualsense4unix.core.trigger_effects import multi_position_feedback

    # Uma zona só, na posição 0, com a força MÁXIMA.
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

    # E a força 1 — o mínimo ATIVO — vira 0, sem se confundir com zona
    # inativa: quem diz que a zona existe é o bitmask.
    efeito_min = multi_position_feedback([1] + [0] * 9)
    zonas_min = int(efeito_min.forces[0]) | (int(efeito_min.forces[1]) << 8)
    forcas_min = int(efeito_min.forces[2])

    assert zonas_min == 0b1, "a zona continua ATIVA com força 1"
    assert forcas_min & 0x07 == 0, "força 1 vira 0 (1 - 1)"


def test_a_frequencia_da_vibracao_vai_para_o_byte_9() -> None:
    """`forces[6]` é o byte 9 do bloco, que é onde mora a frequência.

    Boa notícia de fiação registrada na sprint: o caminho já alcançava tudo. O
    backend escreve `forces[0..5]` em `common[11..16]` (bytes 1-6 do bloco) e
    `forces[6]` em `common[19]` (byte 9). Nenhuma mudança de protocolo foi
    necessária, só de empacotamento.

    Mordida: pôr a frequência em `forces[5]`.
    """
    from hefesto_dualsense4unix.core.trigger_effects import multi_position_vibration

    efeito = multi_position_vibration(97, [4] + [0] * 9)

    assert int(efeito.mode) == 0x26
    assert int(efeito.forces[6]) == 97, (
        "a frequência do Vibration oficial mora no byte 9 do bloco, que é "
        "`forces[6]` — e é o único slot que chega lá"
    )


# ---------------------------------------------------------------------------
# Achado desta leva — o AutoGun quebrava pelo caminho nomeado
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("nome", sorted(_SPEC_POR_NOME))
def test_todo_preset_aceita_os_proprios_parametros_pelo_nome(nome: str) -> None:
    """Os nomes de `trigger_specs` têm de ser os kwargs das factories.

    **Medido em 01/08/2026:** o `AutoGun` declarava o primeiro parâmetro como
    `position` no `trigger_specs` e a factory `auto_gun` o recebe como
    `start`. Pelo caminho POSICIONAL (uma lista) ninguém notava, porque a
    posição batia; pelo caminho NOMEADO — que é o do `build_from_name` com
    `dict`, usado por quem serializa parâmetros com nome — ele levantava
    `TypeError: auto_gun() got an unexpected keyword argument 'position'`.

    Este teste varre TODOS os presets porque o defeito é de uma classe que se
    repete: dois arquivos descrevendo a mesma assinatura, sem nada os
    amarrando.

    Mordida: renomear qualquer `TriggerParamSpec` sem renomear o kwarg da
    factory.
    """
    spec = _SPEC_POR_NOME[nome]
    if not spec.params:
        return
    params = {p.name: p.default for p in spec.params}
    build_from_name(nome, params)


# ---------------------------------------------------------------------------
# E4 — o `--raw` da CLI para de mentir
# ---------------------------------------------------------------------------


def test_o_raw_recusa_quando_o_daemon_esta_vivo(monkeypatch, capsys) -> None:
    """*"o instrumento pode estar brigando com o produto"* — em código.

    **Medido em 01/08/2026**, e custou uma tentativa inteira de medição: com o
    daemon no ar, o `--raw` abre um SEGUNDO controlador e disputa o mesmo
    `/dev/hidraw`. O `report_thread` do daemon sobrescreve o efeito em menos
    de meio segundo (é o keepalive dele) — e o comando imprimia
    "trigger aplicado" mesmo assim.

    Um erro honesto vale mais que um sucesso falso, e é por isso que a saída
    escolhida foi a RECUSA e não o clamp: uma bancada de depuração que só
    funciona com o produto parado é uma bancada honesta; a que anuncia
    sucesso sem aplicar é uma armadilha.

    Mordida: apagar a chamada a `_recusar_raw_com_daemon_vivo`.
    """
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
    """E a bancada continua existindo — é para isso que ela serve.

    Mordida: recusar sempre, independente do daemon.
    """
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
