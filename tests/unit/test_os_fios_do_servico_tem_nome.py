"""Cada fio do serviço leva o nome Python dele ao kernel, e o doctor diz o custo de cada um.

OS-FIOS-DO-SERVICO-TEM-NOME-E-CUSTO-MEDIDO-01: medido em 25/11/2026, 58 dos 61 fios do serviço
saíam em ``/proc/<pid>/task/*/comm`` como ``hefesto-dualsen``. Os fios aqui são do próprio pytest;
nada fala com o serviço de verdade.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.daemon import main as daemon_main
from hefesto_dualsense4unix.utils import nome_do_fio


@pytest.fixture
def dono_instalado() -> Iterator[None]:
    assert nome_do_fio.instalar()
    try:
        yield
    finally:
        nome_do_fio.desinstalar()


def _nome_lido_pelo_fio(nome: str) -> str | None:
    lido: list[str | None] = []

    def _ler() -> None:
        lido.append(nome_do_fio.nome_no_kernel(threading.get_native_id()))

    fio = threading.Thread(target=_ler, name=nome)
    fio.start()
    fio.join(5)
    return lido[0]


def _nome_do_processo() -> str:
    return Path("/proc/self/comm").read_text(encoding="utf-8").strip()


def test_com_o_dono_o_fio_novo_le_o_proprio_nome_no_kernel(dono_instalado: None) -> None:
    """D-2611-CADA-FIO-LEVA-O-NOME-AO-KERNEL."""
    assert _nome_lido_pelo_fio("tato-do-p1") == "tato-do-p1"


def test_sem_o_dono_o_fio_fica_com_o_nome_do_processo() -> None:
    nome_do_fio.desinstalar()
    assert _nome_lido_pelo_fio("tato-do-p2") == _nome_do_processo()


def test_o_dono_instalado_duas_vezes_nao_embrulha_duas_vezes(dono_instalado: None) -> None:
    embrulhado = threading.Thread._bootstrap_inner  # type: ignore[attr-defined]
    assert nome_do_fio.instalar()
    assert threading.Thread._bootstrap_inner is embrulhado  # type: ignore[attr-defined]
    assert _nome_lido_pelo_fio("luz") == "luz"


def test_o_fio_principal_guarda_o_nome_do_processo(dono_instalado: None) -> None:
    antes = _nome_do_processo()
    _nome_lido_pelo_fio("outro")
    assert _nome_do_processo() == antes


def test_o_pool_ganha_o_prefixo_curto(dono_instalado: None) -> None:
    with ThreadPoolExecutor(max_workers=1) as pool:
        lido = pool.submit(lambda: nome_do_fio.nome_no_kernel(threading.get_native_id())).result(5)
    assert lido is not None
    assert lido.startswith("pool-")


@pytest.mark.parametrize(
    ("nome", "curto"),
    [
        ("Thread-7 (ler)", b"ler"),
        ("ThreadPoolExecutor-0_3", b"pool-0_3"),
        ("asyncio_0", b"asyncio_0"),
        ("governador-do-radio", b"governador-do-r"),
        ("ação-ação-ação-x", "ação-ação-a".encode()),
    ],
)
def test_o_nome_curto_cabe_nos_quinze_bytes_sem_cortar_letra(nome: str, curto: bytes) -> None:
    feito = nome_do_fio.nome_curto(nome)
    assert feito == curto
    assert len(feito) <= nome_do_fio.BYTES_DO_NOME
    feito.decode("utf-8")


class _InstalouError(Exception):
    pass


def test_o_servico_instala_o_dono_antes_de_qualquer_fio(monkeypatch: pytest.MonkeyPatch) -> None:
    """O ``run_daemon`` para no primeiro passo de mentira: nunca chega à instância única."""
    ordem: list[str] = []

    def _passo(nome: str) -> Any:
        def _registrar() -> bool:
            ordem.append(nome)
            raise _InstalouError

        return _registrar

    monkeypatch.setattr(nome_do_fio, "instalar", _passo("instalar"))
    monkeypatch.setattr(daemon_main, "ligar_a_pilha_da_queda_nativa", _passo("pilha"))
    monkeypatch.setattr(daemon_main, "ajustar_a_vez_do_gil", _passo("gil"))
    with pytest.raises(_InstalouError):
        daemon_main.run_daemon()
    assert ordem == ["instalar"]


def test_o_doctor_diz_o_custo_de_cada_fio_pelo_nome(dono_instalado: None) -> None:
    pare = threading.Event()

    def _girar() -> None:
        while not pare.is_set():
            sum(range(2000))
            time.sleep(0.001)

    fio = threading.Thread(target=_girar, name="fio-que-gira", daemon=True)
    fio.start()
    try:
        linhas = cmd_doctor._linhas_dos_fios(int(Path("/proc/self").resolve().name), 0.3)
    finally:
        pare.set()
        fio.join(5)
    assert linhas[0][0] == "[INFO]"
    assert " fios em " in linhas[0][1]
    assert any(m.startswith("fio fio-que-gira: ") and "acordadas/s" in m for _t, m in linhas[1:])
    assert all(tag == "[INFO]" for tag, _m in linhas)


def test_o_doctor_sem_servico_de_pe_so_informa() -> None:
    assert cmd_doctor._linhas_dos_fios(None) == [
        ("[INFO]", "fios do serviço: o serviço não está de pé")
    ]


def test_o_doctor_em_json_leva_o_bloco_dos_fios(monkeypatch: pytest.MonkeyPatch) -> None:
    """O bloco entra no doctor de verdade, não só na função que monta as linhas.

    MORDIDA: o ``_rodar_o_doctor`` sem o ``_print_bloco_fios`` deixa o bloco fora.
    """
    from typer.testing import CliRunner

    from hefesto_dualsense4unix.cli.app import app

    async def _sem_daemon() -> list[tuple[str, str]]:
        return []

    for bloco in (
        "_print_storm_block",
        "_print_bloco_contratos",
        "_print_bloco_proton_fixado",
        "_print_bloco_entrada",
        "_print_bloco_registro",
        "_print_bloco_install",
    ):
        monkeypatch.setattr(cmd_doctor, bloco, lambda: 0)
    monkeypatch.setattr(cmd_doctor, "_print_bloco_perfis", lambda: False)
    monkeypatch.setattr(cmd_doctor, "_daemon_checks", _sem_daemon)
    monkeypatch.setattr(cmd_doctor, "_pid_do_servico", lambda: None)
    r = CliRunner().invoke(app, ["doctor", "--json"])
    assert r.exit_code == 0, r.output
    assert "fios do serviço: o serviço não está de pé" in r.output
