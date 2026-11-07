"""O-PREPARO-DA-EXTENSAO-MORA-FORA-DA-CAIXA-01 — as réguas.

A caixa escreve em ``<dados>/<id>``, e o ``preparo.log`` morava ali: o instalador o abria seguindo
link e esperando FIFO. Os plantios vão de dentro de um ``bwrap`` de verdade, no lar de mentira, e
de novo direto no caminho novo, para a segunda barreira morder sozinha. Nada fala com o serviço
real.

MORDIDAS (07/11/2026, executadas sobre a cura e devolvidas):
- o diário de volta a ``<dados>/<id>``: ``test_o_plantio_de_dentro_da_caixa_nao_alcanca_a_pessoa``
  e ``test_o_preparo_mora_na_pasta_do_diario``;
- ``diario.open("wb")`` no lugar do abridor: ``test_a_segunda_barreira_recusa_o_plantio[fifo]``;
- ``Path.open``/``write_bytes`` na poda: ``test_a_segunda_barreira_recusa_o_plantio[link]``;
- sem a mudança do velho: ``test_o_velho_se_muda_uma_vez``;
- a mudança sem o ``suppress``: ``test_o_velho_plantado_nao_segura_o_preparo``;
- sem criar a pasta de dados: ``test_o_preparo_ainda_acha_a_pasta_de_dados``;
- a poda que não corta: ``test_o_preparo_que_fala_demais_fica_no_teto``.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import stat
import textwrap
from pathlib import Path

import pytest

from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import (
    DIARIO_DO_PREPARO,
    TETO_DO_DIARIO_DO_PREPARO_BYTES,
    Lugares,
    atualizar,
    conferir_remocao,
    instalar,
    ler_registro,
    ligar,
    manifesto_instalado,
    remover,
)
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit import test_o_diario_da_extensao_mora_fora_da_caixa as diario
from tests.unit import test_o_diario_da_modificacao_tem_teto_enquanto_roda as teto

curto = teto.curto
lar = teto.lar

_ID = "plantador"
_DA_PESSOA = b"da pessoa, fora da caixa\n" * 40_000

_A_CAIXA_PLANTA = textwrap.dedent('''
    import os, sys
    aqui = os.path.dirname(os.path.abspath(__file__))
    alvo = os.path.join(os.environ["HEFESTO_MOD_DADOS"], "preparo.log")
    plantio = open(os.path.join(aqui, "plantio")).read()
    if os.path.lexists(alvo):
        os.unlink(alvo)
    if plantio == "fifo":
        os.mkfifo(alvo)
    else:
        os.symlink(plantio, alvo)
    print("plantei", flush=True)
    sys.exit(3)
''')


def _fonte(curto: Path, versao: str, plantio: str = "", preparo: str = "echo preparando\n") -> Path:
    pasta = curto / "fonte"
    pasta.mkdir(exist_ok=True)
    manifesto = {
        "id": _ID,
        "nome": "Plantador",
        "versao": versao,  # (noqa-acento)
        "api": ">=1,<3",
        "licenca": "MIT",
        "tipos": ["processo"],
        "processo": {"executar": ["python3", "mod.py"]},
        "permissoes": ["ler:estado"],  # (noqa-acento)
        "preparar": ["sh", "prepara.sh"],
    }
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    (pasta / "mod.py").write_text(_A_CAIXA_PLANTA, encoding="utf-8")
    (pasta / "plantio").write_text(plantio, encoding="utf-8")
    (pasta / "prepara.sh").write_text(preparo, encoding="utf-8")
    return pasta


def _ligar(lar: Lugares) -> instalador.Entrada:
    return ligar(_ID, permissoes_vistas=manifesto_instalado(_ID, lugares=lar).permissoes,
                 lugares=lar)


def _instalada(lar: Lugares, curto: Path, plantio: str = "", preparo: str = "echo preparando\n"
               ) -> None:
    instalar(str(_fonte(curto, "0.1.0", plantio, preparo)), lugares=lar)
    _ligar(lar)


def _novo(lar: Lugares) -> Path:
    return lar.pasta_do_diario(_ID) / DIARIO_DO_PREPARO


def _velho(lar: Lugares) -> Path:
    return lar.dados / _ID / DIARIO_DO_PREPARO


def _a_caixa_plantar(lar: Lugares) -> str:
    """A extensão roda na caixa de verdade, planta e sai."""
    async def corrida() -> str:
        supervisor = teto._supervisor(lar, bwrap=shutil.which("bwrap"), esperas=(0.05,))
        assert supervisor.bwrap
        await supervisor.iniciar()
        try:
            await teto._ate(lambda: getattr(supervisor.estado_de(_ID), "estado", "") == "parou")
            estado = supervisor.estado_de(_ID)
            assert estado is not None
            return estado.ultima_linha
        finally:
            await supervisor.parar()

    return diario._em_fio(lambda: asyncio.run(corrida()))


@pytest.mark.parametrize("plantio", ["link", "fifo"])
def test_o_plantio_de_dentro_da_caixa_nao_alcanca_a_pessoa(
    lar: Lugares, curto: Path, plantio: str,
) -> None:
    exigir_caixa_do_bwrap()
    alvo = curto / "casa" / "da-pessoa.txt"
    alvo.write_bytes(_DA_PESSOA)
    _instalada(lar, curto, str(alvo) if plantio == "link" else "fifo")
    assert _a_caixa_plantar(lar) == "plantei"
    modo = os.lstat(_velho(lar)).st_mode
    assert stat.S_ISLNK(modo) if plantio == "link" else stat.S_ISFIFO(modo)

    _fonte(curto, "0.2.0", str(alvo) if plantio == "link" else "fifo")
    feito = diario._em_fio(lambda: atualizar(_ID, lugares=lar))

    entrada = ler_registro(lar.registro)[_ID]
    assert feito.entrada.versao == entrada.versao == "0.2.0"
    assert entrada.ligada and entrada.motivo_do_preparo == ""
    assert entrada.preparada_em == entrada.instalada_em
    assert alvo.read_bytes() == _DA_PESSOA
    assert b"preparando" in _novo(lar).read_bytes()


def test_o_preparo_mora_na_pasta_do_diario(lar: Lugares, curto: Path) -> None:
    _instalada(lar, curto)
    assert not _novo(lar).is_relative_to(lar.dados / _ID)
    assert _novo(lar).read_bytes() == b"preparando\n"
    assert not os.path.lexists(_velho(lar))
    assert stat.S_IMODE(_novo(lar).stat().st_mode) == 0o600
    assert stat.S_IMODE(_novo(lar).parent.stat().st_mode) == 0o700


def test_o_preparo_ainda_acha_a_pasta_de_dados(lar: Lugares, curto: Path) -> None:
    _instalada(lar, curto, preparo='echo pronto > "$HEFESTO_MOD_DADOS/copia"\n')
    assert (lar.dados / _ID / "copia").read_text(encoding="utf-8") == "pronto\n"


def test_o_velho_se_muda_uma_vez(lar: Lugares, curto: Path) -> None:
    instalar(str(_fonte(curto, "0.1.0")), lugares=lar)
    _velho(lar).parent.mkdir(parents=True)
    _velho(lar).write_bytes(b"a saida de antes\n")
    _ligar(lar)
    assert not os.path.lexists(_velho(lar))
    assert _novo(lar).read_bytes() == b"preparando\n"

    _velho(lar).write_bytes(b"replantado depois\n")
    _fonte(curto, "0.2.0")
    atualizar(_ID, lugares=lar)
    assert _velho(lar).read_bytes() == b"replantado depois\n", "a mudança vale uma vez só"


@pytest.mark.parametrize("plantio", ["link", "fifo"])
def test_o_velho_plantado_nao_segura_o_preparo(
    lar: Lugares, curto: Path, plantio: str,
) -> None:
    alvo = curto / "casa" / "da-pessoa.txt"
    alvo.write_bytes(_DA_PESSOA)
    instalar(str(_fonte(curto, "0.1.0")), lugares=lar)
    _velho(lar).parent.mkdir(parents=True)
    if plantio == "link":
        _velho(lar).symlink_to(alvo)
    else:
        os.mkfifo(_velho(lar))

    entrada = diario._em_fio(lambda: _ligar(lar))

    assert entrada.ligada and entrada.motivo_do_preparo == ""
    assert alvo.read_bytes() == _DA_PESSOA
    assert _novo(lar).read_bytes() == b"preparando\n"


@pytest.mark.parametrize("plantio", ["link", "fifo"])
def test_a_segunda_barreira_recusa_o_plantio(
    lar: Lugares, curto: Path, plantio: str,
) -> None:
    alvo = curto / "casa" / "da-pessoa.txt"
    alvo.write_bytes(_DA_PESSOA)
    assert len(_DA_PESSOA) > TETO_DO_DIARIO_DO_PREPARO_BYTES
    instalar(str(_fonte(curto, "0.1.0")), lugares=lar)
    _novo(lar).parent.mkdir(parents=True)
    if plantio == "link":
        _novo(lar).symlink_to(alvo)
    else:
        os.mkfifo(_novo(lar))

    with pytest.raises(instalador.InstalacaoRecusadaError, match="não abriu"):
        diario._em_fio(lambda: _ligar(lar))

    assert alvo.read_bytes() == _DA_PESSOA
    entrada = ler_registro(lar.registro)[_ID]
    assert not entrada.ligada and "não abriu" in entrada.motivo_do_preparo


def test_o_preparo_que_fala_demais_fica_no_teto(lar: Lugares, curto: Path) -> None:
    linhas = TETO_DO_DIARIO_DO_PREPARO_BYTES // 10
    _instalada(lar, curto, preparo=f'seq -f %09.0f 1 {linhas + 100}\n')
    guardado = _novo(lar).read_bytes()
    assert len(guardado) == TETO_DO_DIARIO_DO_PREPARO_BYTES
    assert guardado.endswith(f"{linhas + 100:09d}\n".encode())


def test_a_remocao_leva_o_preparo(lar: Lugares, curto: Path) -> None:
    _instalada(lar, curto)
    assert _novo(lar).is_file()
    instalador.desligar(_ID, lugares=lar)
    assert remover(_ID, lugares=lar) == []
    assert conferir_remocao(_ID, lugares=lar) == []
    assert not os.path.lexists(_novo(lar))
