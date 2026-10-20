"""O diário de uma modificação fica no teto ENQUANTO ela roda.

Sprint O-DIARIO-DA-MODIFICACAO-TEM-TETO-ENQUANTO-ELA-RODA-01. Lar de mentira (``HOME`` e
``XDG_*`` em pasta temporária), sem caixa, com um filho que só escreve na saída e fica de pé.
Nenhuma prova fala com o serviço dela.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import tempfile
import textwrap
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.mods import supervisor as supervisor_mod
from hefesto_dualsense4unix.mods.instalador import (
    Lugares,
    instalar,
    ler_estado,
    ligar,
    manifesto_instalado,
)
from hefesto_dualsense4unix.mods.supervisor import Supervisor

TETO = 64 * 1024

#: O filho falador: 512 KiB em linhas numeradas, a linha final e depois fica de pé (ou cai).
_O_FILHO = textwrap.dedent('''
    import os, sys, time
    modo = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modo")).read().strip()
    for n in range(8192):
        print(f"linha {n:06d} " + "x" * 50, flush=(n % 64 == 0))
    print("a linha final", flush=True)
    if modo == "cai":
        sys.exit(3)
    while True:
        time.sleep(1)
''')

_FORA_DO_TMP = "/var/tmp" if os.access("/var/tmp", os.W_OK) else None


@pytest.fixture
def curto() -> Iterator[Path]:
    pasta = Path(tempfile.mkdtemp(prefix="hd", dir=_FORA_DO_TMP))
    try:
        yield pasta
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


@pytest.fixture
def lar(curto: Path, monkeypatch: pytest.MonkeyPatch) -> Lugares:
    casa, execucao = curto / "casa", curto / "run"
    for pasta in (casa, execucao):
        pasta.mkdir(mode=0o700)
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(casa / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(casa / ".local/share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(casa / ".local/state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(casa / ".cache"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(execucao))
    monkeypatch.setattr(supervisor_mod, "TETO_DO_DIARIO_BYTES", TETO)
    lugares = Lugares.do_xdg()
    assert str(lugares.dados).startswith(str(curto))
    return lugares


def _instalar_e_ligar(lar: Lugares, curto: Path, modo: str) -> Path:
    pasta = curto / "fonte"
    pasta.mkdir()
    manifesto = {
        "id": "falador",
        "nome": "Falador",
        "versao": "0.1.0",  # (noqa-acento): contrato ASCII
        "api": ">=1,<3",
        "licenca": "MIT",
        "tipos": ["processo"],
        "processo": {"executar": ["python3", "mod.py"]},
        "permissoes": ["ler:estado"],  # (noqa-acento): contrato ASCII
    }
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    (pasta / "mod.py").write_text(_O_FILHO, encoding="utf-8")
    (pasta / "modo").write_text(modo, encoding="utf-8")
    instalar(str(pasta), lugares=lar)
    ligar("falador", permissoes_vistas=manifesto_instalado("falador", lugares=lar).permissoes,
          lugares=lar)
    return lar.dados / "falador" / "diario.log"


def _supervisor(lar: Lugares, **mais: Any) -> Supervisor:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        return {"status": "ok"}

    return Supervisor(
        EventBus(),
        escritor=escritor,
        o_jogo_escreve=lambda uniq, canal: False,
        uniq_do_posto=lambda: "aa:bb:cc:00:00:01",
        lugares=lar,
        procurar_bwrap=False,
        **mais,
    )


async def _ate(condicao: Any, prazo: float = 15.0) -> None:
    fim = time.monotonic() + prazo
    while time.monotonic() < fim:
        if condicao():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("o prazo passou sem a condição")


def _texto(diario: Path) -> str:
    try:
        return diario.read_text(encoding="utf-8")
    except OSError:
        return ""


def test_a_modificacao_que_fala_muito_nao_passa_do_teto_enquanto_roda(
    lar: Lugares, curto: Path
) -> None:
    """D-2010-O-DIARIO-DA-EXTENSAO-TEM-TETO-ENQUANTO-ELA-RODA."""
    diario = _instalar_e_ligar(lar, curto, "fica")

    async def corrida() -> None:
        supervisor = _supervisor(lar)
        await supervisor.iniciar()
        try:
            await _ate(lambda: "a linha final" in _texto(diario))
            assert supervisor.estado_de("falador").estado == "rodando"
            assert diario.stat().st_size <= TETO, diario.stat().st_size
            texto = _texto(diario)
            assert texto.splitlines()[-1] == "a linha final"
            assert texto.splitlines()[0].startswith("linha "), "a metade nova começa na linha"
            assert len(texto.splitlines()[0]) == len("linha 000000 ") + 50
        finally:
            await supervisor.parar()

    asyncio.run(corrida())


def test_a_que_cai_falando_muito_guarda_a_ultima_linha_e_o_teto(
    lar: Lugares, curto: Path
) -> None:
    diario = _instalar_e_ligar(lar, curto, "cai")

    async def corrida() -> None:
        supervisor = _supervisor(lar, esperas=(0.05,))
        await supervisor.iniciar()
        try:
            await _ate(lambda: getattr(supervisor.estado_de("falador"), "estado", "")
                       == "parou")
            estado = ler_estado(lar.estado)["falador"]
            assert estado["ultima_linha"] == "a linha final"
            assert estado["quedas"] == 2
            assert diario.stat().st_size <= TETO, diario.stat().st_size
        finally:
            await supervisor.parar()

    asyncio.run(corrida())


def test_aparar_guarda_a_metade_nova_de_linha_inteira(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(supervisor_mod, "TETO_DO_DIARIO_BYTES", TETO)
    diario = tmp_path / "diario.log"
    linhas = [f"linha {n:06d} " + "x" * 50 for n in range(2000)]
    diario.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    supervisor_mod._aparar_o_diario(diario, chegando=0)
    texto = diario.read_text(encoding="utf-8")
    assert TETO // 2 - 64 <= len(texto) <= TETO // 2, len(texto)
    assert texto.splitlines() == linhas[-len(texto.splitlines()):]

    curto = "cabe\n"
    diario.write_text(curto, encoding="utf-8")
    supervisor_mod._aparar_o_diario(diario, chegando=TETO - len(curto))
    assert diario.read_text(encoding="utf-8") == curto, "no teto exato nada sai"
    supervisor_mod._aparar_o_diario(diario, chegando=TETO)
    assert diario.read_text(encoding="utf-8") == curto, "o diário curto já é a metade nova"
