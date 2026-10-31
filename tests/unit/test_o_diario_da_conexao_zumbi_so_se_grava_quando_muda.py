"""O-DIARIO-DA-CONEXAO-ZUMBI-SO-SE-GRAVA-QUANDO-MUDA-01.

O diário do vigia guarda o veredito, não o batimento: duas voltas iguais gravam uma vez só, e a
aba Conexões sabe se o diário vale pelo processo que o gravou, não por um carimbo regravado a cada
cinco segundos.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import conexoes
from hefesto_dualsense4unix.daemon.subsystems.conexoes import (
    ConexoesSubsystem,
    ler_o_diario,
    o_diario_e_fresco,
)
from hefesto_dualsense4unix.integrations.conexao_zumbi import LinkDeRadio, VigiaDeZumbis

DONGLE = "aa:bb:cc:00:00:33"
SAO = "aa:bb:cc:00:00:22"
ZUMBI = "aa:bb:cc:00:00:44"
LINK_ZUMBI = LinkDeRadio(hci="hci1", adaptador=DONGLE, controle=ZUMBI)


class _PonteSemCura:
    def __init__(self, impede: list[str] | None = None) -> None:
        self._impede = impede if impede is not None else ["a ponte não está instalada"]

    def impedimentos(self) -> list[str]:
        return list(self._impede)

    def desconectar(self, link: LinkDeRadio) -> tuple[bool, str]:
        return False, "sem ponte"


@pytest.fixture
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    caminho = tmp_path / "estado" / "conexao-zumbi.json"
    monkeypatch.setattr(conexoes, "caminho_do_diario", lambda: caminho)
    return caminho


def _subsystem(mesa: dict[str, Any]) -> ConexoesSubsystem:
    return ConexoesSubsystem(
        vigia=VigiaDeZumbis(ponte=_PonteSemCura(), segundos_para_zumbi=0.0),
        olhador=lambda: (list(mesa["links"]), {SAO}, {("hci0", SAO)}, []),
    )


def _gravacoes(caminho: Path, quantas_voltas: int, subsystem: ConexoesSubsystem,
               inicio: float) -> int:
    vistas: set[tuple[int, int]] = set()
    for volta in range(quantas_voltas):
        subsystem.uma_volta(inicio + volta * conexoes.INTERVALO_S)
        estado = caminho.stat()
        vistas.add((estado.st_ino, estado.st_mtime_ns))
    return len(vistas)


def test_cinco_minutos_de_voltas_iguais_gravam_uma_vez_so(diario: Path) -> None:
    mesa: dict[str, Any] = {"links": []}
    subsystem = _subsystem(mesa)
    voltas = int(300 / conexoes.INTERVALO_S)
    assert _gravacoes(diario, voltas, subsystem, 100.0) == 1


def test_o_veredito_novo_grava_de_novo_e_o_igual_nao(diario: Path) -> None:
    mesa: dict[str, Any] = {"links": []}
    subsystem = _subsystem(mesa)
    subsystem.uma_volta(10.0)
    antes = diario.stat()
    mesa["links"] = [LINK_ZUMBI]
    subsystem.uma_volta(15.0)
    depois = diario.stat()
    assert (antes.st_ino, antes.st_mtime_ns) != (depois.st_ino, depois.st_mtime_ns)
    assert [z["controle"] for z in ler_o_diario()["zumbis"]] == [ZUMBI]
    subsystem.uma_volta(20.0)
    subsystem.uma_volta(25.0)
    terceira = diario.stat()
    assert (terceira.st_ino, terceira.st_mtime_ns) == (depois.st_ino, depois.st_mtime_ns)


def test_o_diario_apagado_com_o_daemon_vivo_volta_na_volta_seguinte(diario: Path) -> None:
    subsystem = _subsystem({"links": [LINK_ZUMBI]})
    subsystem.uma_volta(10.0)
    diario.unlink()
    subsystem.uma_volta(15.0)
    assert [z["controle"] for z in ler_o_diario()["zumbis"]] == [ZUMBI]


def test_o_diario_nao_carrega_batimento(diario: Path) -> None:
    _subsystem({"links": []}).uma_volta(10.0)
    gravado = ler_o_diario()
    assert "carimbo" not in gravado
    assert gravado["pid"] == os.getpid()


def test_o_diario_do_processo_vivo_e_fresco_e_o_do_morto_nao(diario: Path) -> None:
    _subsystem({"links": []}).uma_volta(10.0)
    gravado = ler_o_diario()
    assert o_diario_e_fresco(gravado) is True
    morto = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"],
                           capture_output=True, text=True, check=True)
    assert o_diario_e_fresco({**gravado, "pid": int(morto.stdout)}) is False
    assert o_diario_e_fresco({**gravado, "partida": gravado["partida"] + 1}) is False
    assert o_diario_e_fresco({"carimbo": 1.0, "zumbis": []}) is False
    assert o_diario_e_fresco({}) is False
    assert o_diario_e_fresco(None) is False


def _linhas_da_aba(volta: dict[str, Any]) -> list[dict[str, Any]]:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
    from hefesto_dualsense4unix.interface.pacotes import nome_do_jogador

    a08._DISPENSADOS.clear()
    return a08._os_que_nao_viraram_controle(volta, [nome_do_jogador.mac(DONGLE)], [])


def test_a_aba_mostra_o_zumbi_do_diario_fresco_e_cala_o_velho(diario: Path) -> None:
    _subsystem({"links": [LINK_ZUMBI]}).uma_volta(10.0)
    gravado = ler_o_diario()
    [linha] = _linhas_da_aba(gravado)
    assert linha["nao_conectou"] is True
    assert linha["chave"].endswith("|" + ZUMBI.replace(":", ""))
    assert _linhas_da_aba({**gravado, "partida": gravado["partida"] + 1}) == []
