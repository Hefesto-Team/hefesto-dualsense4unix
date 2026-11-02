"""A extensão que se atualiza segue ligada na troca.

A sprint é a A-EXTENSAO-QUE-SE-ATUALIZA-NAO-APARECE-DESLIGADA-NA-TROCA-01. O supervisor é o de
verdade, com o processo de verdade da extensão; o registro e o estado vivo moram num lar de
mentira (HOME e XDG desviados), e nada toca o ``~/.config`` de quem roda.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_mod
from hefesto_dualsense4unix.interface.desenho_da_experimental import processo_de
from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import (
    Lugares,
    gravar_registro,
    instalar,
    ler_estado,
    ler_registro,
)
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

_ate, _ligar_vendo, _pasta_do_mod, _supervisor = (
    _base._ate, _base._ligar_vendo, _base._pasta_do_mod, _base._supervisor)
curto, lar = _base.curto, _base.lar


def _o_que_se_le(lugares: Lugares) -> tuple[str, str]:
    """A palavra do ``mod listar`` e a chave da tela, do registro e do estado de agora."""
    entrada = ler_registro(lugares.registro)["exemplo"]
    vivo = ler_estado(lugares.estado).get("exemplo", {})
    estado = str(vivo.get("estado") or "")
    return estado or ("ligada" if entrada.ligada else "desligada"), processo_de(
        entrada.ligada, estado)


def _nova_versao(pasta: Path, versao: str, permissoes: list[str] | None = None) -> None:
    corpo = json.loads((pasta / "hefesto-mod.json").read_text(encoding="utf-8"))
    corpo["versao"] = versao  # (noqa-acento)
    if permissoes is not None:
        corpo["permissoes"] = permissoes  # (noqa-acento)
    (pasta / "hefesto-mod.json").write_text(json.dumps(corpo), encoding="utf-8")


def _atualizar_e_listar(saidas: list[Any]) -> None:
    """O gesto da linha de comando: ``mod atualizar`` e o ``mod listar`` logo em seguida."""
    runner = CliRunner()
    saidas.append(runner.invoke(cmd_mod.app, ["atualizar", "exemplo"]))
    saidas.append(runner.invoke(cmd_mod.app, ["listar"]))


class _Troca:
    """O que se leu e o que o supervisor gravou, do pedido de atualizar até a volta."""

    def __init__(self) -> None:
        self.vistos: list[tuple[str, str]] = []
        self.gravados: list[str] = []
        self.saidas: list[Any] = []
        self.pids: tuple[int | None, int | None] = (None, None)


def _trocar_vendo(lugares: Lugares, pasta: Path, **mais: Any) -> _Troca:
    """Atualiza a extensão viva; lê o estado a cada 10 ms e guarda cada estado gravado."""
    troca = _Troca()

    async def corrida() -> None:
        sup = _supervisor(lugares, procurar_bwrap=False, intervalo_s=0.3)
        gravar = sup._gravar_estado

        def gravar_vendo() -> None:
            estado = sup.estado_de("exemplo")
            troca.gravados.append(estado.estado if estado else "")
            gravar()

        await sup.iniciar()
        try:
            await _ate(lambda: _o_que_se_le(lugares)[0] == "rodando")
            troca.pids = (sup.pid_de("exemplo"), None)
            sup._gravar_estado = gravar_vendo  # type: ignore[method-assign]
            _nova_versao(pasta, "0.1.1", **mais)
            gesto = threading.Thread(target=_atualizar_e_listar, args=(troca.saidas,))
            gesto.start()
            while gesto.is_alive():
                troca.vistos.append(_o_que_se_le(lugares))
                await asyncio.sleep(0.01)
            gesto.join()
            assert ler_registro(lugares.registro)["exemplo"].versao == "0.1.1"
            final = "rodando" if ler_registro(lugares.registro)["exemplo"].ligada else "desligada"
            while troca.vistos[-1][0] != final:
                assert len(troca.vistos) < 2000, troca.vistos[-20:]
                await asyncio.sleep(0.01)
                troca.vistos.append(_o_que_se_le(lugares))
            troca.pids = (troca.pids[0], sup.pid_de("exemplo"))
        finally:
            sup._gravar_estado = gravar  # type: ignore[method-assign]
            await sup.parar()

    asyncio.run(corrida())
    return troca


def test_a_ligada_que_se_atualiza_nunca_aparece_desligada_e_volta_a_rodar(
    lar: Lugares, curto: Path
) -> None:
    pasta = _pasta_do_mod(curto / "fontes")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)

    troca = _trocar_vendo(lar, pasta)

    atualizou, listou = troca.saidas
    assert atualizou.exit_code == 0, atualizou.output
    assert listou.exit_code == 0, listou.output
    assert "desligada" not in listou.output, listou.output
    na_lista = [lista for lista, _ in troca.vistos]
    na_tela = [tela for _, tela in troca.vistos]
    assert "desligada" not in na_lista, na_lista
    assert "desligada" not in na_tela, na_tela
    assert "desligada" not in troca.gravados, troca.gravados
    assert "atualizando" in troca.gravados, "a troca do código é um estado próprio"
    assert na_lista[-1] == "rodando" and troca.gravados[-1] == "rodando"
    pid_velho, pid_novo = troca.pids
    assert pid_novo is not None and pid_novo != pid_velho, "o serviço reabriu a versão nova"
    assert ler_registro(lar.registro)["exemplo"].ligada


def test_a_versao_que_pede_permissao_nova_termina_desligada_com_o_motivo(
    lar: Lugares, curto: Path
) -> None:
    pasta = _pasta_do_mod(curto / "fontes")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)

    troca = _trocar_vendo(lar, pasta, permissoes=["ler:estado", "escrever:luz", "ler:bateria"])

    atualizou = troca.saidas[0]
    assert atualizou.exit_code == 0, atualizou.output
    assert "ler:bateria" in atualizou.output and "mod ligar exemplo" in atualizou.output
    assert troca.vistos[-1] == ("desligada", "desligada")
    primeira = troca.gravados.index("desligada")
    assert "atualizando" in troca.gravados[:primeira], troca.gravados
    assert set(troca.gravados[primeira:]) == {"desligada"}, troca.gravados
    assert troca.pids[1] is None
    assert not ler_registro(lar.registro)["exemplo"].ligada


def _marcar_com(lugares: Lugares, marca: str) -> None:
    registro = ler_registro(lugares.registro)
    registro["exemplo"].em_troca = marca
    gravar_registro(lugares.registro, registro)


def test_a_marca_de_quem_morreu_no_meio_nao_segura_a_extensao(lar: Lugares, curto: Path) -> None:
    """O instalar morto no meio da troca deixa a marca: o serviço volta a rodar a ligada."""
    instalar(str(_pasta_do_mod(curto / "fontes")), lugares=lar)
    _ligar_vendo("exemplo", lar)
    quem_troca = subprocess.Popen(["sleep", "30"])
    try:
        _marcar_com(lar, f"{quem_troca.pid}:{instalador._inicio_do_processo(quem_troca.pid)}")

        async def corrida() -> None:
            sup = _supervisor(lar, procurar_bwrap=False, intervalo_s=0.05)
            await sup.iniciar()
            try:
                assert _o_que_se_le(lar) == ("atualizando", "")
                assert sup.pid_de("exemplo") is None
                antes = lar.registro.stat().st_mtime_ns
                quem_troca.kill()
                quem_troca.wait()
                await _ate(lambda: _o_que_se_le(lar)[0] == "rodando")
                assert lar.registro.stat().st_mtime_ns == antes, "o registro não mudou"
            finally:
                await sup.parar()

        asyncio.run(corrida())
    finally:
        if quem_troca.poll() is None:
            quem_troca.kill()
            quem_troca.wait()
    _marcar_com(lar, "1:0")
    assert not instalador.troca_viva(ler_registro(lar.registro)["exemplo"])


def test_a_troca_que_falha_antes_do_codigo_tira_a_marca_e_segue_ligada(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = _pasta_do_mod(curto / "fontes")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)
    _nova_versao(pasta, "0.1.1")

    def quebra(nova: Path, final: Path) -> None:
        raise OSError("o disco recusou")

    monkeypatch.setattr(instalador, "_trocar_o_codigo", quebra)
    with pytest.raises(OSError):
        instalar(str(pasta), lugares=lar)
    entrada = ler_registro(lar.registro)["exemplo"]
    assert entrada.em_troca == "" and entrada.ligada and entrada.versao == "0.1.0"
