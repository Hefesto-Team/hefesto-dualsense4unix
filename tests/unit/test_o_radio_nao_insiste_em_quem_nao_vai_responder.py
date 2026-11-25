"""O rádio não insiste em quem não vai responder.

D-2511-O-RADIO-NAO-INSISTE-EM-QUEM-NAO-VAI-RESPONDER (25/11/2026). Num BlueZ sem o sinal
``Device1.Disconnected`` toda saída chega sem razão; o religador só chama de volta a saída sem
razão se o BlueZ entrega a razão (o dono viu o sinal) ou se o controle estava em uso (botão
mexido há pouco e o PS solto). A faxina pergunta à ponte privilegiada pelo impedimento do
``esquecer`` e só pergunta de novo quando a firma da ponte muda. TUDO É DE MENTIRA: o BlueZ, o
relógio e a ponte são dublês, e a suíte nunca chega ao sudo.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, SALA, VERMELHO

VOLTAS_DE_UMA_JANELA = 700


class _Ponte:
    """A ponte privilegiada de mentira: responde o impedimento e conta as perguntas."""

    def __init__(self, motivos: list[str]) -> None:
        self.motivos = motivos
        self.perguntas = 0
        self.a_firma = 1

    def firma(self) -> int:
        return self.a_firma

    def impedimentos_do_pedido(self, *_pedidos: Any) -> list[str]:
        self.perguntas += 1
        return list(self.motivos)


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


@pytest.fixture()
def mundo() -> rm.RadioDeMentira:
    return rm.RadioDeMentira()


@pytest.fixture()
def relogio() -> rm.Relogio:
    return rm.Relogio()


@pytest.fixture()
def dono(mundo: rm.RadioDeMentira, relogio: rm.Relogio) -> Iterator[bd.DonoVivo]:
    vivo = bd.DonoVivo(mundo, vaga=bd.VigiaDaVaga(relogio))
    yield vivo
    vivo.fechar()


def _central(
    dono: bd.DonoVivo, mundo: rm.RadioDeMentira, relogio: rm.Relogio, **extra: Any
) -> cr.CentralDoRadio:
    assert dono.ligar()
    return cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        no_kernel=lambda _aparelho: False, relogio=relogio, dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"}, **extra)


def _connects(mundo: rm.RadioDeMentira) -> list[tuple[str, str]]:
    return [(onde, quem) for tipo, onde, quem in mundo.linha_do_tempo if tipo == "Connect"]


def _andar(central: cr.CentralDoRadio, relogio: rm.Relogio, segundos: int) -> None:
    for _ in range(segundos):
        relogio.dormir(1.0)
        central.religar()


def _ler(dono: bd.DonoVivo, botoes: set[str], aparelho: str = VERMELHO) -> None:
    dono._vaga.observar({aparelho: frozenset(botoes)})


def test_a_saida_sem_razao_de_controle_parado_nao_e_chamada_de_volta(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """D-2511-O-RADIO-NAO-INSISTE-EM-QUEM-NAO-VAI-RESPONDER: o controle parado não é chamado."""
    mundo.pareado(SALA, VERMELHO, conectado=True)
    central = _central(dono, mundo, relogio)
    _ler(dono, set())
    mundo.desligar(VERMELHO)

    _andar(central, relogio, VOLTAS_DE_UMA_JANELA)

    assert _connects(mundo) == []


def test_a_saida_sem_razao_de_controle_em_uso_e_chamada_de_volta(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=True)
    central = _central(dono, mundo, relogio)
    _ler(dono, {"cross"})
    mundo.desligar(VERMELHO)

    _andar(central, relogio, 6)

    assert _connects(mundo) == [(SALA, VERMELHO)]


def test_o_controle_desligado_segurando_o_ps_nao_e_chamado_de_volta(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=True)
    central = _central(dono, mundo, relogio)
    _ler(dono, {"cross"})
    _ler(dono, {"cross", "ps"})
    mundo.desligar(VERMELHO)

    _andar(central, relogio, VOLTAS_DE_UMA_JANELA)

    assert _connects(mundo) == []


def test_o_botao_mexido_ha_muito_tempo_nao_conta_como_em_uso(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=True)
    central = _central(dono, mundo, relogio)
    _ler(dono, {"cross"})
    relogio.agora += bd.MEXIA_ATE_CAIR_S + 1.0
    _ler(dono, {"cross"})
    mundo.desligar(VERMELHO)

    _andar(central, relogio, VOLTAS_DE_UMA_JANELA)

    assert _connects(mundo) == []


def test_o_ultimo_tique_velho_nao_diz_que_o_controle_estava_em_uso(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=True)
    central = _central(dono, mundo, relogio)
    _ler(dono, {"cross"})
    relogio.agora += bd.TIQUE_LIDO_VALE_ATE_S + 1.0
    mundo.desligar(VERMELHO)

    _andar(central, relogio, VOLTAS_DE_UMA_JANELA)

    assert _connects(mundo) == []


def test_a_saida_com_razao_de_queda_segue_chamando_o_controle_parado(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    mundo.pareado(SALA, VERMELHO, conectado=True)
    central = _central(dono, mundo, relogio)
    _ler(dono, set())
    mundo._emitir(bd.Sinal("desconectou", caminho=rm.no_de(SALA, VERMELHO),
                           razao=bd.RAZAO_TIMEOUT))
    mundo.desligar(VERMELHO)

    _andar(central, relogio, 6)

    assert _connects(mundo) == [(SALA, VERMELHO)]


def test_o_bluez_que_ja_mandou_a_razao_a_entrega_a_cada_saida(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """Visto o sinal numa saída, a saída sem razão de outro controle volta a ser queda."""
    mundo.pareado(SALA, VERMELHO, conectado=True)
    mundo.pareado(SALA, AZUL, conectado=True)
    central = _central(dono, mundo, relogio)
    mundo._emitir(bd.Sinal("desconectou", caminho=rm.no_de(SALA, AZUL),
                           razao=bd.RAZAO_DO_CONTROLE))
    mundo.desligar(AZUL)
    _ler(dono, set())
    mundo.desligar(VERMELHO)

    _andar(central, relogio, 6)

    assert (SALA, VERMELHO) in _connects(mundo)


def test_a_faxina_pergunta_a_ponte_uma_vez_e_nao_tenta_o_esquecer_sem_a_regra(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dez voltas da faxina sem a regra do sudo: uma pergunta à ponte e nenhum ``esquecer``."""
    esquecidos: list[tuple[str, str]] = []

    def esquecer(adaptador: str, aparelho: str) -> tuple[bool, str]:
        esquecidos.append((adaptador, aparelho))
        return mundo.esquecer_na_ponte(adaptador, aparelho)

    monkeypatch.setattr(cr, "esquecer_pela_ponte", esquecer)
    mundo.pareado(SALA, VERMELHO, conectado=True)
    mundo.pareado(QUARTO, VERMELHO, host=False)
    ponte = _Ponte(["o sudo sem senha para a ponte não está no lugar"])
    central = _central(dono, mundo, relogio, ponte=ponte)  # type: ignore[arg-type]

    for _ in range(10):
        assert central.esquecer_as_sobras() is None

    assert ponte.perguntas == 1
    assert esquecidos == []

    ponte.motivos = []
    ponte.a_firma = 2
    assert central.esquecer_as_sobras() == (QUARTO, VERMELHO)
    assert ponte.perguntas == 2
    assert esquecidos == [(QUARTO, VERMELHO)]
