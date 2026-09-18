"""O «No controle e na TV» não pode realimentar o próprio controle.

A LACUNA, e ela só não aparece na máquina dela
------------------------------------------------------------------------------
A SOM-JUNTO-01 (17/09/2026) fez a fonte ``mix`` chegar ao nó que já está de pé:
um ``module-loopback`` do monitor da SAÍDA PADRÃO do sistema para o nó do
controle. Na mesa dela a saída padrão é o HDMI e o fio é inofensivo. Numa
máquina em que a saída padrão é o PRÓPRIO controle, o fio fecha um laço:

* no rádio, ``hefesto_som_X.monitor → hefesto_som_X`` — a pessoa escolheu
  «Alto-falante do Controle N» nas configurações de som;
* no cabo, ``D.monitor → hefesto_som_X → D`` — a placa USB do DualSense tem
  ``priority.session`` 1109, acima do HDMI (696) e da placa-mãe (736), e
  nenhum drop-in do produto a rebaixa; com o fone plugado no controle ela é a
  saída de quem joga.

Não havia trava em lugar nenhum. A lacuna foi INFERIDA da leitura do código,
não medida na orelha: o que esta régua prova é o fio que o produto pede ao
``pactl``.

O QUE ELA TRAVA
------------------------------------------------------------------------------
1. ``argv_das_rotas`` — o dono PURO que os dois chamadores usam (o daemon e o
   plano da janela) — não sobe o mix que fecha laço, nos dois transportes;
2. ``rota_do_no`` entrega a rota com o monitor do mix VAZIO nesse caso, para o
   estado ficar legível — e sem frase nova para a tela (texto de tela é dela);
3. o monitor de OUTRO controle continua valendo: ele termina no alto-falante
   deste e não volta, e recusá-lo tiraria o mix de quem joga com a saída num
   controle e o som no outro;
4. a cena inteira, pelo gerenciador de produção, com o ``pactl`` de bancada.

A MORDIDA
------------------------------------------------------------------------------
Tire a condição ``o_mix_fecha_laco`` de ``argv_das_rotas`` e os casos de (1)
reprovam. Troque ``_mix_sem_laco(...)`` pelo ``monitor`` cru em ``rota_do_no``
e os de (2) reprovam. A cena (4) só reprova com as DUAS arrancadas — as duas
guardas cobrem o mesmo fio por portas diferentes, e é de propósito.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import fontes_de_captura
from tests.unit.bancada_do_som_junto import (
    HDMI,
    P1,
    P2,
    SINK_P1,
    Pactl,
    cabo,
    escrever_perfil,
    subsystem_e_gerenciador,
)

#: O nó deste controle, pelo dono único do nome.
NO_P1 = af.nome_do_sink(P1)

#: A placa USB de OUTRO controle — a saída padrão legítima de quem joga com o
#: som num controle e o mix no outro.
SINK_P2 = SINK_P1.replace("-00.", "-01.")


def _mixes(argvs: tuple[tuple[str, ...], ...], id_do_no: str) -> list[str]:
    """As origens dos ``module-loopback`` que TERMINAM no nó."""
    return [
        a[len("source="):]
        for argv in argvs
        if f"sink={id_do_no}" in argv
        for a in argv
        if a.startswith("source=")
    ]


# ---------------------------------------------------------------------------
# 1. O dono puro não sobe o laço
# ---------------------------------------------------------------------------


def test_no_radio_o_mix_do_proprio_no_nao_sobe() -> None:
    rota = af.RotaDoNo(
        True, por_onde=af.POR_RADIO, fonte=af.FONTE_MIX,
        monitor_do_mix=f"{NO_P1}.monitor",
    )

    assert _mixes(af.argv_das_rotas(NO_P1, rota), NO_P1) == [], (
        "o mix ligou o monitor do nó nele mesmo — o som do controle volta "
        "para o controle, em laço"
    )


def test_no_cabo_o_mix_da_propria_placa_nao_sobe_e_a_saida_fica() -> None:
    rota = af.RotaDoNo(
        True, sink=SINK_P1, por_onde=af.POR_CABO, fonte=af.FONTE_MIX,
        monitor_do_mix=f"{SINK_P1}.monitor",
    )

    argvs = af.argv_das_rotas(NO_P1, rota)

    assert _mixes(argvs, NO_P1) == [], (
        "o mix ligou a placa do controle ao nó que toca nela — "
        "D.monitor → nó → D, realimentação"
    )
    assert af.argv_para_ligar_o_no(NO_P1, SINK_P1) in argvs, (
        "recusar o laço derrubou a SAÍDA: o controle ficou sem som nenhum"
    )


def test_o_mix_da_tv_continua_subindo() -> None:
    """A trava não pode custar o caso de todo dia: a saída padrão é a TV."""
    rota = af.RotaDoNo(
        True, sink=SINK_P1, por_onde=af.POR_CABO, fonte=af.FONTE_MIX,
        monitor_do_mix=f"{HDMI}.monitor",
    )

    assert _mixes(af.argv_das_rotas(NO_P1, rota), NO_P1) == [f"{HDMI}.monitor"]


def test_o_monitor_de_outro_controle_nao_e_laco() -> None:
    """O som de P2 cai também em P1 e termina em P1: não volta a ninguém."""
    for monitor in (f"{af.nome_do_sink(P2)}.monitor", f"{SINK_P2}.monitor"):
        rota = af.RotaDoNo(
            True, sink=SINK_P1, por_onde=af.POR_CABO, fonte=af.FONTE_MIX,
            monitor_do_mix=monitor,
        )
        assert _mixes(af.argv_das_rotas(NO_P1, rota), NO_P1) == [monitor], (
            f"a trava recusou {monitor}, que não fecha ciclo — larga demais"
        )


# ---------------------------------------------------------------------------
# 2. A rota sai com o monitor vazio, e o resto dela intacto
# ---------------------------------------------------------------------------


@pytest.fixture()
def bancada(monkeypatch: pytest.MonkeyPatch) -> Pactl:
    """O `pactl` desviado no dono único dele: `alto_falante_bt._rodar`."""
    pactl = Pactl(placas=(SINK_P1,))
    monkeypatch.setattr(af, "_rodar", pactl)
    monkeypatch.setattr(
        fontes_de_captura,
        "escolher_sink",
        lambda sinks, uniq, conhecidos, usb: SINK_P1 if uniq == P1 else "",
    )
    return pactl


def test_a_rota_do_radio_recusa_o_monitor_do_proprio_no(bancada: Pactl) -> None:
    bancada.padrao = NO_P1

    rota = af.rota_do_no(
        P1, af.TRANSPORTE_RADIO, fonte=af.FONTE_MIX, ponte_do_radio=lambda: True
    )

    assert rota.tem_rota and rota.por_onde == af.POR_RADIO
    assert rota.monitor_do_mix == "", (
        f"a rota do rádio saiu com o mix {rota.monitor_do_mix!r} — o monitor "
        "do próprio nó"
    )
    assert rota.motivo == "", "a recusa inventou uma frase de tela"


def test_a_rota_do_cabo_recusa_o_monitor_da_propria_placa(bancada: Pactl) -> None:
    bancada.padrao = SINK_P1

    rota = af.rota_do_no(P1, af.TRANSPORTE_CABO, fonte=af.FONTE_MIX)

    assert rota.tem_rota and rota.sink == SINK_P1
    assert rota.monitor_do_mix == "", (
        f"a rota do cabo saiu com o mix {rota.monitor_do_mix!r} — a placa do "
        "próprio controle"
    )


def test_a_rota_com_a_tv_de_saida_segue_igual(bancada: Pactl) -> None:
    bancada.padrao = HDMI

    rota = af.rota_do_no(P1, af.TRANSPORTE_CABO, fonte=af.FONTE_MIX)

    assert rota.monitor_do_mix == f"{HDMI}.monitor"


# ---------------------------------------------------------------------------
# 4. A cena inteira, pela fiação de produção
# ---------------------------------------------------------------------------


def test_o_no_de_pe_no_cabo_nao_fecha_o_laco(bancada: Pactl) -> None:
    """O fone plugado no controle: a placa dele é a saída padrão do sistema."""
    bancada.padrao = SINK_P1
    nome = escrever_perfil({P1: af.FONTE_MIX})
    _sub, ger = subsystem_e_gerenciador(nome)

    ger.reconciliar([cabo(P1)])
    no = ger.nos[P1]

    assert (f"{SINK_P1}.monitor", no.nome) not in bancada.loopbacks, (
        f"o nó subiu com o laço de pé: {bancada.loopbacks}"
    )
    assert (f"{no.nome}.monitor", SINK_P1) in bancada.loopbacks, (
        "o controle ficou sem a saída para o alto-falante"
    )
