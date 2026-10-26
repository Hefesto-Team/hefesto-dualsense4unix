"""O vigia de zumbi pergunta e avisa uma vez por episódio.

Um link de rádio que conecta e não vira controle fica de pé enquanto o
vigia roda, uma volta a cada 5 s. Antes desta régua, cada volta perguntava
de novo ao ``sudo`` (``impedimentos()``), mesmo sem nada ter mudado, e cada
volta repetia no journal o mesmo aviso: perto de 17 mil linhas por dia
com um zumbi de pé.

Aqui o relógio é de mentira, a ponte conta as perguntas e as derrubadas e
devolve uma firma que a régua controla, e o journal se lê por
``structlog.testing.capture_logs``. Nenhum ``sudo`` de verdade roda, e os
endereços são da faixa sintética da casa.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems import conexoes
from hefesto_dualsense4unix.daemon.subsystems.conexoes import ConexoesSubsystem, PonteComTrava
from hefesto_dualsense4unix.integrations.conexao_zumbi import (
    LinkDeRadio,
    PontePrivilegiada,
    VigiaDeZumbis,
)

DONGLE_A = "aa:bb:cc:00:00:11"
DONGLE_B = "aa:bb:cc:00:00:33"
SAO = "aa:bb:cc:00:00:22"
ZUMBI = "aa:bb:cc:00:00:44"

LINK_ZUMBI = LinkDeRadio(hci="hci1", adaptador=DONGLE_B, controle=ZUMBI)
CONHECIDOS = {("hci0", SAO)}

VOLTAS = 12
INTERVALO = 5.0


class PonteQueConta:
    """Ponte de mentira: conta perguntas e derrubadas, e a firma é da régua."""

    def __init__(self) -> None:
        self.impede: list[str] = []
        self.funciona = True
        self.motivo = "a ponte saiu com 1"
        self.firma_atual: object = (1, 100)
        self.perguntas = 0
        self.pedidos: list[LinkDeRadio] = []

    def impedimentos(self) -> list[str]:
        self.perguntas += 1
        return list(self.impede)

    def firma(self) -> object:
        return self.firma_atual

    def desconectar(self, link: LinkDeRadio) -> tuple[bool, str]:
        self.pedidos.append(link)
        return (True, "") if self.funciona else (False, self.motivo)


class Mesa:
    """O que o olhador devolve; a régua troca os links entre as voltas."""

    def __init__(self) -> None:
        self.links: list[LinkDeRadio] = [LINK_ZUMBI]

    def __call__(self) -> tuple[list[LinkDeRadio], set[str], set[tuple[str, str]], list[str]]:
        return list(self.links), {SAO}, set(CONHECIDOS), []


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    caminho = tmp_path / "conexao-zumbi.json"
    monkeypatch.setattr(conexoes, "caminho_do_diario", lambda: caminho)
    return caminho


def _subsystem(ponte: PonteQueConta, mesa: Mesa, **kwargs: Any) -> ConexoesSubsystem:
    vigia = VigiaDeZumbis(ponte=cast(PontePrivilegiada, ponte), segundos_para_zumbi=0.0,
                          **kwargs)
    return ConexoesSubsystem(vigia=vigia, olhador=mesa)


def _avisos(registros: Sequence[Mapping[str, Any]]) -> list[str]:
    return [
        str(r.get("recado"))
        for r in registros
        if r.get("event") == "conexao_zumbi" and r.get("log_level") == "warning"
    ]


def test_o_impedimento_se_pergunta_uma_vez_e_se_avisa_uma_vez(diario: Path) -> None:
    """Item 1: 60 s de zumbi com impedimento — uma pergunta, um aviso, o JSON em toda volta."""
    ponte = PonteQueConta()
    ponte.impede = ["o sudo sem senha para a ponte não está no lugar"]
    subsystem = _subsystem(ponte, Mesa())
    com_diario = 0
    with structlog.testing.capture_logs() as registros:
        for volta in range(VOLTAS):
            subsystem.uma_volta(100.0 + volta * INTERVALO)
            gravado = json.loads(diario.read_text(encoding="utf-8"))
            if gravado["diario"] and ZUMBI in gravado["diario"][0]:
                com_diario += 1
    assert ponte.perguntas == 1, f"o sudo foi perguntado {ponte.perguntas} vezes"
    assert len(_avisos(registros)) == 1, _avisos(registros)
    assert com_diario == VOLTAS, "a aba Conexões perdeu o diário numa volta"
    assert ponte.pedidos == []


def test_a_firma_nova_da_ponte_faz_perguntar_e_agir_na_mesma_volta(diario: Path) -> None:
    """Item 2: o install no meio do episódio troca a firma, e o vigia age na volta."""
    ponte = PonteQueConta()
    ponte.impede = ["a ponte privilegiada não está instalada"]
    subsystem = _subsystem(ponte, Mesa())
    for volta in range(5):
        subsystem.uma_volta(100.0 + volta * INTERVALO)
    assert ponte.perguntas == 1
    ponte.firma_atual = (2, 200)
    ponte.impede = []
    veredito = subsystem.uma_volta(100.0 + 5 * INTERVALO)
    assert ponte.perguntas == 2
    assert veredito.derrubados == (LINK_ZUMBI,)
    assert ponte.pedidos == [LINK_ZUMBI]


def test_o_episodio_novo_pergunta_de_novo_uma_vez(diario: Path) -> None:
    """Item 3: o link some e volta — uma pergunta a mais, não uma por volta."""
    ponte = PonteQueConta()
    ponte.impede = ["o sudo sem senha para a ponte não está no lugar"]
    mesa = Mesa()
    subsystem = _subsystem(ponte, mesa)
    agora = 100.0
    for _ in range(4):
        subsystem.uma_volta(agora)
        agora += INTERVALO
    mesa.links = []
    subsystem.uma_volta(agora)
    agora += INTERVALO
    mesa.links = [LINK_ZUMBI]
    with structlog.testing.capture_logs() as registros:
        for _ in range(4):
            subsystem.uma_volta(agora)
            agora += INTERVALO
    assert ponte.perguntas == 2
    assert len(_avisos(registros)) == 1, "o aviso que voltou depois do sumiço não saiu"


def test_o_segurado_pelo_teto_avisa_uma_vez(diario: Path) -> None:
    """Item 4: doze voltas seguradas pelo teto, um aviso.

    A derrubada fecha o episódio: o link que volta abre outro, e a ponte é
    perguntada uma vez a mais, não uma por volta.
    """
    ponte = PonteQueConta()
    subsystem = _subsystem(ponte, Mesa(), janela_do_teto_s=600.0)
    primeiro = subsystem.uma_volta(100.0)
    assert primeiro.derrubados
    with structlog.testing.capture_logs() as registros:
        for volta in range(1, VOLTAS + 1):
            veredito = subsystem.uma_volta(100.0 + volta * INTERVALO)
            assert veredito.segurados_pelo_teto == (LINK_ZUMBI,)
    assert len(ponte.pedidos) == 1
    assert ponte.perguntas == 2, f"o sudo foi perguntado {ponte.perguntas} vezes"
    assert len(_avisos(registros)) == 1, _avisos(registros)


def test_a_ponte_que_falha_tenta_toda_volta_e_avisa_por_motivo(diario: Path) -> None:
    """Item 5: a decisão de 20/09 continua (tenta toda volta); o aviso, só por motivo novo."""
    ponte = PonteQueConta()
    ponte.funciona = False
    subsystem = _subsystem(ponte, Mesa())
    agora = 100.0
    with structlog.testing.capture_logs() as registros:
        for _ in range(VOLTAS):
            subsystem.uma_volta(agora)
            agora += INTERVALO
    assert len(ponte.pedidos) == VOLTAS
    assert len(_avisos(registros)) == 1, _avisos(registros)
    ponte.motivo = "a ponte não respondeu: tempo esgotado"
    with structlog.testing.capture_logs() as registros:
        for _ in range(3):
            subsystem.uma_volta(agora)
            agora += INTERVALO
    avisos = _avisos(registros)
    assert len(avisos) == 1 and "tempo esgotado" in avisos[0], avisos


def test_a_firma_da_ponte_e_o_inode_e_o_ctime(tmp_path: Path) -> None:
    """A firma muda quando o instalador grava ou regrava a ponte."""
    alvo = tmp_path / "bt_ponte_privilegiada.sh"
    pasta = tmp_path / "sudoers.d"
    pasta.mkdir()
    ponte = PontePrivilegiada(caminho=str(alvo), pasta_da_regra=str(pasta))
    ausente = ponte.firma()
    alvo.write_text("#!/bin/bash\n", encoding="utf-8")
    primeira = ponte.firma()
    assert primeira != ausente
    novo = tmp_path / "novo.sh"
    novo.write_text("#!/bin/bash\n# regravada\n", encoding="utf-8")
    novo.replace(alvo)
    assert ponte.firma() not in (ausente, primeira)


class PonteDaMaquina(PontePrivilegiada):
    """Responde como a de verdade: sem a regra na pasta, o ``sudo -n`` pede senha."""

    perguntas = 0

    def impedimentos(self) -> list[str]:
        self.perguntas += 1
        motivos: list[str] = []
        if not Path(self.caminho).exists():
            motivos.append("a ponte privilegiada não está instalada")
        if not (Path(self.pasta_da_regra) / "49-hefesto-bt-ponte").exists():
            motivos.append("o sudo sem senha para a ponte não está no lugar")
        return motivos

    def desconectar(self, link: LinkDeRadio) -> tuple[bool, str]:
        return True, ""


def test_o_install_em_dois_passos_nao_prende_a_resposta_velha(
    tmp_path: Path, diario: Path
) -> None:
    """A volta que cai entre a ponte e a regra não prende o «sem a regra» no episódio.

    O instalador grava a ponte e só depois do ``visudo -c`` grava a regra
    (``install_bt_ponte_privilegiada_host``). A firma lê as duas pontas.
    """
    pasta = tmp_path / "sudoers.d"
    pasta.mkdir()
    alvo = tmp_path / "bt_ponte_privilegiada.sh"
    ponte = PonteDaMaquina(caminho=str(alvo), pasta_da_regra=str(pasta))
    vigia = VigiaDeZumbis(ponte=ponte, segundos_para_zumbi=0.0)
    subsystem = ConexoesSubsystem(vigia=vigia, olhador=Mesa())
    assert subsystem.uma_volta(100.0).impedimentos
    alvo.write_text("#!/bin/bash\n", encoding="utf-8")
    assert subsystem.uma_volta(105.0).impedimentos
    time.sleep(0.05)
    (pasta / "49-hefesto-bt-ponte").write_text("regra\n", encoding="utf-8")
    veredito = subsystem.uma_volta(110.0)
    assert veredito.derrubados == (LINK_ZUMBI,), (
        f"a regra entrou e o vigia seguiu com a resposta velha: {veredito.impedimentos}"
    )
    assert ponte.perguntas == 3


def test_a_ponte_com_trava_repassa_a_firma_da_interna(tmp_path: Path) -> None:
    alvo = tmp_path / "bt_ponte_privilegiada.sh"
    alvo.write_text("#!/bin/bash\n", encoding="utf-8")
    interna = PontePrivilegiada(caminho=str(alvo))
    assert PonteComTrava(interna=interna).firma() == interna.firma()
