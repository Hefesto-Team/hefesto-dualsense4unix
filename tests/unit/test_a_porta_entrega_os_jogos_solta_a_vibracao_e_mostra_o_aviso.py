"""A porta 2: os jogos da extensão de lançador, a vibração que se solta e o aviso do manifesto.

O contrato está em ``docs/protocol/porta-das-modificacoes.md``. Tudo roda num lar de mentira, com
porta e supervisor próprios: nenhuma prova fala com o serviço dela nem com um controle.

MORDIDAS (19/10/2026, executadas sobre a cura e devolvidas):

- o ``lancador.jogos`` tirado do ``_despachar`` da porta reprova
  ``test_a_extensao_de_lancador_entrega_os_jogos_e_a_interface_os_le`` e
  ``test_o_filho_de_lancador_entrega_os_jogos_pelo_supervisor``;
- o ``_soltar_a_vibracao`` tirado do ``finally`` da conexão reprova
  ``test_a_vibracao_que_a_extensao_deixou_ligada_se_solta_quando_ela_cai``;
- o ``AvisoParaVerError`` tirado do ``instalar`` reprova
  ``test_o_aviso_aparece_antes_de_instalar_e_nada_se_grava``;
- o ``manifesto.aviso != aviso_aceito`` tirado da recusa do ``instalar`` reprova
  ``test_reinstalar_pelo_terminal_com_o_aviso_ja_aceito_nao_pergunta_de_novo``.
"""
from __future__ import annotations

import asyncio
import json
import os
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import CODE_INVALID_PARAMS
from hefesto_dualsense4unix.mods import API_DAS_MODIFICACOES
from hefesto_dualsense4unix.mods.instalador import (
    AvisoParaVerError,
    instalar,
    ler_registro,
    ligar,
    manifesto_instalado,
)
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from hefesto_dualsense4unix.mods.porta import CODE_O_JOGO_ESCREVE, CODE_SEM_PERMISSAO, Porta
from hefesto_dualsense4unix.mods.supervisor import _comandos_do_lancador
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

_ate, _supervisor, _Cliente = _base._ate, _base._supervisor, _base._Cliente
#: O lar de mentira e a pasta curta são as mesmas fixtures das modificações.
curto, lar = _base.curto, _base.lar

P1, P2, P3 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03"
AVISO = "Não é afiliada à marca. Jogue só o que você comprou."
JOGOS = [
    {"chave": "lutris:12", "nome": "Celeste", "abrir": ["lutris", "lutris:rungameid/12"],
     "janela": "celeste"},
    {"chave": "lutris:13", "nome": "Hades", "abrir": ["lutris", "lutris:rungameid/13"]},
]


async def _porta(curto: Path, permissoes: list[str], *, comandos: tuple[str, ...] = ("lutris",),
                 escritas: list[Any] | None = None, o_jogo: Any = None) -> Porta:
    async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
        if escritas is not None:
            escritas.append((metodo, pedido))
        return {"status": "ok"}

    porta = Porta(curto / "mods.sock", EventBus(), escritor=escritor,
                  o_jogo_escreve=o_jogo or (lambda uniq, canal: False), uniq_do_posto=lambda: P1)
    await porta.iniciar()
    porta.registrar("ficha", "lanc", os.getpid(), permissoes, comandos=comandos)
    return porta


def _servico(supervisor: Any) -> Any:
    return SimpleNamespace(daemon=SimpleNamespace(_mods_supervisor=supervisor),
                           _mod_do_pedido=IpcHandlersMixin._mod_do_pedido)


# -- a extensão de lançador entrega os jogos --------------------------------------------


def test_a_extensao_de_lancador_entrega_os_jogos_e_a_interface_os_le(curto: Path) -> None:
    async def corrida() -> None:
        porta = await _porta(curto, ["lancador"])
        cliente = _Cliente(curto / "mods.sock")
        try:
            ola = await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
            assert ola["result"]["api"] == API_DAS_MODIFICACOES == 2
            feito = await asyncio.to_thread(cliente.pedir, "lancador.jogos", {"jogos": JOGOS})
            assert feito["result"] == {"recebidos": 2}
            esperado = [{**JOGOS[0]}, {**JOGOS[1], "janela": ""}]
            assert porta.jogos_de("lanc") == esperado
            corpo = await IpcHandlersMixin._handle_mods_jogos(
                _servico(SimpleNamespace(porta=porta)), {"mod": "lanc"})
            assert corpo == {"mod": "lanc", "jogos": esperado}
            # A lista inteira substitui a anterior.
            await asyncio.to_thread(cliente.pedir, "lancador.jogos", {"jogos": JOGOS[1:]})
            assert [j["chave"] for j in porta.jogos_de("lanc")] == ["lutris:13"]
        finally:
            cliente.fechar()
        await _ate(lambda: porta.jogos_de("lanc") == [])
        await porta.parar()

    asyncio.run(corrida())
    sem_servico = asyncio.run(IpcHandlersMixin._handle_mods_jogos(_servico(None), {"mod": "lanc"}))
    assert sem_servico == {"mod": "lanc", "jogos": []}


def test_o_jogo_que_abre_outro_comando_ou_vem_torto_e_recusado(curto: Path) -> None:
    async def corrida() -> None:
        porta = await _porta(curto, ["lancador"])
        porta.registrar("sem-palavra", "outra", os.getpid(), [], comandos=("lutris",))
        porta.registrar("sem-comandos", "terceira", os.getpid(), ["lancador"])
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
            await asyncio.to_thread(cliente.pedir, "lancador.jogos", {"jogos": JOGOS})
            casos = [
                ({"chave": "x", "nome": "X", "abrir": ["sh", "-c", "true"]}, CODE_SEM_PERMISSAO),
                ({"chave": "x", "nome": "X", "abrir": []}, CODE_INVALID_PARAMS),
                ({"chave": "x", "nome": "", "abrir": ["lutris"]}, CODE_INVALID_PARAMS),
                ({"chave": "", "nome": "X", "abrir": ["lutris"]}, CODE_INVALID_PARAMS),
                ("lutris", CODE_INVALID_PARAMS),
            ]
            for jogo, codigo in casos:
                recusa = await asyncio.to_thread(
                    cliente.pedir, "lancador.jogos", {"jogos": [jogo]})
                assert recusa["error"]["code"] == codigo, (jogo, recusa)
            repetida = await asyncio.to_thread(
                cliente.pedir, "lancador.jogos", {"jogos": [JOGOS[0], JOGOS[0]]})
            assert "repetida" in repetida["error"]["message"]
            assert len(porta.jogos_de("lanc")) == 2, "a recusa apagou a lista de antes"
        finally:
            cliente.fechar()
        for ficha, frase in (("sem-palavra", "falta a permissão lancador"),
                             ("sem-comandos", "lancador.comandos")):
            outro = _Cliente(curto / "mods.sock")
            try:
                await asyncio.to_thread(outro.pedir, "mod.ola", {"ficha": ficha})
                recusa = await asyncio.to_thread(outro.pedir, "lancador.jogos", {"jogos": JOGOS})
                assert frase in recusa["error"]["message"], recusa
            finally:
                outro.fechar()
        await porta.parar()

    asyncio.run(corrida())


def test_o_supervisor_passa_so_os_comandos_do_lancador() -> None:
    base: dict[str, Any] = {"id": "lanc", "nome": "Lanc", "api": ">=1,<3",
                            "versao": "1",  # (noqa-acento): contrato ASCII
                            "licenca": "MIT", "permissoes": ["lancador"]}  # (noqa-acento) chave
    lancador = Manifesto.model_validate({
        **base, "tipos": ["lancador", "processo"], "processo": {"executar": ["python3", "m.py"]},
        "lancador": {"rotulo": "Lanc", "comandos": ["lutris", "", 3, "flatpak"]}})
    assert _comandos_do_lancador(lancador) == ("lutris", "flatpak")
    tema = Manifesto.model_validate({**base, "tipos": ["tema"], "tema": {},
                                     "lancador": {"comandos": ["lutris"]}})
    assert _comandos_do_lancador(tema) == ()


_O_LANCADOR = textwrap.dedent('''
    import json, os, socket, time
    s = socket.socket(socket.AF_UNIX)
    s.connect(os.environ["HEFESTO_MOD_SOCKET"])
    f = s.makefile()
    def pedir(i, qual, params):
        linha = {"jsonrpc": "2.0", "id": i, "method": qual, "params": params}
        s.sendall((json.dumps(linha) + "\\n").encode())
        return json.loads(f.readline())
    pedir(1, "mod.ola", {"ficha": os.environ["HEFESTO_MOD_FICHA"]})
    pedir(2, "lancador.jogos", {"jogos": [
        {"chave": "lutris:12", "nome": "Celeste", "abrir": ["lutris", "lutris:rungameid/12"]}]})
    while True:
        time.sleep(1)
''')


def test_o_filho_de_lancador_entrega_os_jogos_pelo_supervisor(lar: Any, curto: Path) -> None:
    pasta = curto / "fonte-lanc"
    pasta.mkdir()
    (pasta / "mod.py").write_text(_O_LANCADOR, encoding="utf-8")
    (pasta / "hefesto-mod.json").write_text(json.dumps({
        "id": "lanc", "nome": "Lanc", "api": ">=2,<3", "licenca": "MIT",
        "versao": "0.1",  # (noqa-acento): contrato ASCII
        "tipos": ["lancador", "processo"], "processo": {"executar": ["python3", "mod.py"]},
        "permissoes": ["lancador"],  # (noqa-acento) chave do contrato
        "lancador": {"rotulo": "Lanc", "comandos": ["lutris"]},
    }), encoding="utf-8")
    instalar(str(pasta), lugares=lar)
    ligar("lanc", permissoes_vistas=["lancador"], lugares=lar)

    async def corrida() -> None:
        sup = _supervisor(lar, procurar_bwrap=False)
        await sup.iniciar()
        try:
            await _ate(lambda: bool(sup.porta.jogos_de("lanc")))
            assert sup.porta.jogos_de("lanc") == [{
                "chave": "lutris:12", "nome": "Celeste",
                "abrir": ["lutris", "lutris:rungameid/12"], "janela": ""}]
        finally:
            await sup.parar()

    asyncio.run(corrida())


# -- a vibração que a extensão deixou ligada se solta -----------------------------------


def test_a_vibracao_que_a_extensao_deixou_ligada_se_solta_quando_ela_cai(curto: Path) -> None:
    escritas: list[Any] = []
    do_jogo: set[str] = set()

    async def corrida() -> None:
        porta = await _porta(curto, ["escrever:vibracao"], escritas=escritas,
                             o_jogo=lambda uniq, canal: uniq in do_jogo)
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
            for uniq, fraco, forte in ((P1, 80, 0), (P2, 50, 50), (P2, 0, 0), (P3, 0, 40)):
                feito = await asyncio.to_thread(
                    cliente.pedir, "vibracao.set", {"uniq": uniq, "fraco": fraco, "forte": forte})
                assert feito["result"] == {"status": "ok"}, feito
            do_jogo.add(P3)
            recusa = await asyncio.to_thread(
                cliente.pedir, "vibracao.set", {"uniq": P3, "fraco": 9, "forte": 9})
            assert recusa["error"]["code"] == CODE_O_JOGO_ESCREVE
        finally:
            cliente.fechar()
        await _ate(lambda: len(escritas) > 4)
        await asyncio.sleep(0.05)
        await porta.parar()

    asyncio.run(corrida())
    # P1 ficou vibrando e se solta; P2 já tinha voltado a zero; P3 é do jogo agora.
    assert escritas[4:] == [("rumble.set", {"uniq": P1, "weak": 0, "strong": 0})]


# -- o aviso do manifesto ---------------------------------------------------------------


def _pasta_com_aviso(curto: Path, aviso: str = AVISO) -> Path:
    pasta = curto / "fonte-aviso"
    pasta.mkdir(exist_ok=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps({
        "id": "avisada", "nome": "Avisada", "api": ">=2,<3", "licenca": "MIT",
        "versao": "0.1",  # (noqa-acento): contrato ASCII
        "tipos": ["tema"], "tema": {}, "aviso": aviso,
        "permissoes": ["tema"],  # (noqa-acento) chave do contrato
    }), encoding="utf-8")
    return pasta


def test_o_aviso_aparece_antes_de_instalar_e_nada_se_grava(lar: Any, curto: Path) -> None:
    pasta = _pasta_com_aviso(curto)
    with pytest.raises(AvisoParaVerError) as aviso:
        instalar(str(pasta), lugares=lar, aviso_visto="")
    assert aviso.value.aviso == AVISO and aviso.value.frase == f"«Avisada» avisa: {AVISO}"
    assert ler_registro(lar.registro) == {} and not (lar.codigo / "avisada").exists()
    feito = instalar(str(pasta), lugares=lar, aviso_visto=AVISO)
    assert feito.entrada.aviso_aceito == AVISO and not feito.entrada.ligada
    # O aviso visto no instalar vale para o ligar: o «sim» pede só as permissões.
    assert ligar("avisada", permissoes_vistas=["tema"], lugares=lar).ligada


def test_o_aviso_nao_visto_pede_o_sim_do_ligar_e_segura_o_supervisor(
    lar: Any, curto: Path
) -> None:
    instalar(str(_pasta_com_aviso(curto)), lugares=lar)
    assert ler_registro(lar.registro)["avisada"].aviso_aceito == ""
    with pytest.raises(AvisoParaVerError):
        ligar("avisada", permissoes_vistas=["tema"], lugares=lar)
    sup = _supervisor(lar, procurar_bwrap=False)
    entrada = ler_registro(lar.registro)["avisada"]
    entrada.ligada, entrada.permissoes_aceitas = True, ["tema"]
    motivo, manifesto = sup._o_que_impede(entrada)
    assert manifesto is None and "aviso" in motivo
    feita = ligar("avisada", permissoes_vistas=["tema"], aviso_visto=AVISO, lugares=lar)
    assert feita.ligada and feita.aviso_aceito == AVISO
    assert sup._o_que_impede(ler_registro(lar.registro)["avisada"])[0] == ""


def test_a_versao_com_outro_aviso_espera_e_o_atualizar_volta_a_pedir_o_sim(
    lar: Any, curto: Path
) -> None:
    pasta = _pasta_com_aviso(curto)
    instalar(str(pasta), lugares=lar, aviso_visto=AVISO)
    ligar("avisada", permissoes_vistas=["tema"], lugares=lar)
    _pasta_com_aviso(curto, "Para maiores de 18 anos.")
    sozinha = instalar(str(pasta), lugares=lar, sozinha=True)
    assert not sozinha.trocou and "outro aviso" in sozinha.entrada.motivo_da_espera
    assert manifesto_instalado("avisada", lugares=lar).aviso == AVISO
    pedida = instalar(str(pasta), lugares=lar)
    assert pedida.trocou and not pedida.entrada.ligada, "o aviso novo ligou sem o «sim»"
    assert pedida.entrada.aviso_aceito == AVISO


def test_a_linha_de_comando_mostra_o_aviso_e_pergunta(lar: Any, curto: Path) -> None:
    from hefesto_dualsense4unix.cli.cmd_mod import app

    pasta = _pasta_com_aviso(curto)
    runner = CliRunner()
    nao = runner.invoke(app, ["instalar", str(pasta)], input="n\n")
    assert nao.exit_code == 1 and AVISO in nao.output and "Não instalei" in nao.output
    assert ler_registro(lar.registro) == {}
    sim = runner.invoke(app, ["instalar", str(pasta), "--sim"])
    assert sim.exit_code == 0, sim.output
    assert ler_registro(lar.registro)["avisada"].aviso_aceito == AVISO


def test_reinstalar_pelo_terminal_com_o_aviso_ja_aceito_nao_pergunta_de_novo(
    lar: Any, curto: Path
) -> None:
    """O aviso que já teve o «sim» não volta a perguntar, e a extensão segue ligada."""
    from hefesto_dualsense4unix.cli.cmd_mod import app

    pasta = _pasta_com_aviso(curto)
    instalar(str(pasta), lugares=lar, aviso_visto=AVISO)
    ligar("avisada", permissoes_vistas=["tema"], lugares=lar)
    de_novo = instalar(str(pasta), lugares=lar, aviso_visto="")
    assert de_novo.entrada.ligada and de_novo.entrada.aviso_aceito == AVISO
    pelo_terminal = CliRunner().invoke(app, ["instalar", str(pasta)], input="")
    assert pelo_terminal.exit_code == 0, pelo_terminal.output
    assert ler_registro(lar.registro)["avisada"].ligada
