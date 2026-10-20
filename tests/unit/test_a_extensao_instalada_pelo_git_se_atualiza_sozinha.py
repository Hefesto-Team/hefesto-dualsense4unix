"""A extensão instalada pelo link do git se atualiza sozinha.

A sprint é a A-EXTENSAO-INSTALADA-PELO-GIT-SE-ATUALIZA-SOZINHA-01.
Os repositórios são ``git init`` locais, abertos por ``file://``, num lar de mentira: nenhuma
prova fala com a rede de fora, com o GitHub nem com o serviço dela.

MORDIDAS (19/10/2026, executadas sobre a cura e devolvidas):

- a permissão nova tirada do ``_o_que_segura_a_atualizacao`` reprova
  ``test_a_versao_que_pede_permissao_nova_fica_esperando_o_atualizar``;
- a origem local e a chave desligada tiradas do ``_talvez_atualizar`` reprovam
  ``test_a_chave_desligada_no_registro_nao_pergunta_ao_git`` e
  ``test_a_origem_local_nunca_se_atualiza_sozinha``.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import (
    InstalacaoRecusadaError,
    Lugares,
    atualizar,
    commit_novo,
    commit_remoto,
    gravar_registro,
    instalar,
    ler_registro,
    ligar,
    manifesto_instalado,
)
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

_ate, _chave, _git, _supervisor = _base._ate, _base._chave, _base._git, _base._supervisor
#: O lar de mentira e a pasta curta são as mesmas fixtures das modificações.
curto, lar = _base.curto, _base.lar

#: O filho de mentira: só fica de pé; a prova é o PID que o supervisor grava.
_O_FILHO = "import time\nwhile True:\n    time.sleep(1)\n"


def _manifesto(versao: str = "0.1.0", permissoes: tuple[str, ...] = ("ler:estado",)) -> str:
    return json.dumps({
        "id": "exemplo", "nome": "Exemplo", "versao": versao,  # (noqa-acento): contrato ASCII
        "api": ">=1,<3", "licenca": "MIT", "tipos": ["processo"],
        "processo": {"executar": ["python3", "mod.py"]},
        "permissoes": list(permissoes),  # (noqa-acento): contrato ASCII
    })


def _publicar(origem: Path, versao: str, **mais: Any) -> str:
    """Um commit novo no repositório de mentira; devolve o commit."""
    (origem / "hefesto-mod.json").write_text(_manifesto(versao, **mais), encoding="utf-8")
    _git(origem, "add", ".")
    _git(origem, "commit", "-q", "-m", f"a {versao}")
    return _git(origem, "rev-parse", "HEAD")


@pytest.fixture
def remoto(curto: Path, lar: Lugares) -> Path:
    origem = curto / "remoto" / "hefesto-mod-exemplo"
    origem.mkdir(parents=True)
    (origem / "mod.py").write_text(_O_FILHO, encoding="utf-8")
    _git(origem, "init", "-q", "-b", "principal")
    _publicar(origem, "0.1.0")
    return origem


def _instalar_ligada(lar: Lugares, origem: Path, **ajuste: Any) -> None:
    instalar(f"file://{origem}", lugares=lar)
    ligar("exemplo", permissoes_vistas=manifesto_instalado("exemplo", lugares=lar).permissoes,
          lugares=lar)
    registro = ler_registro(lar.registro)
    for campo, valor in ajuste.items():
        setattr(registro["exemplo"], campo, valor)
    gravar_registro(lar.registro, registro)


def _supervisor_rapido(lar: Lugares, **mais: Any) -> Any:
    sup = _supervisor(lar, procurar_bwrap=False, intervalo_s=0.05, **mais)
    sup.piso_da_atualizacao_s = 0.0
    sup.espera_depois_da_falha_s = 0.0
    return sup


def _rodando(sup: Any) -> bool:
    estado = sup.estado_de("exemplo")
    return estado is not None and estado.estado == "rodando" and sup.pid_de("exemplo") is not None


# -- o commit novo instala sozinho ---------------------------------------------


def test_o_commit_novo_do_remoto_se_instala_sozinho_e_a_viva_volta(
    lar: Lugares, remoto: Path
) -> None:
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=0.2)

    async def corrida() -> None:
        sup = _supervisor_rapido(lar)
        await sup.iniciar()
        try:
            await _ate(lambda: _rodando(sup))
            pid_velho = sup.pid_de("exemplo")
            novo = _publicar(remoto, "0.2.0")
            await _ate(lambda: ler_registro(lar.registro)["exemplo"].commit == novo)
            await _ate(lambda: _rodando(sup) and sup.pid_de("exemplo") != pid_velho)
            entrada = ler_registro(lar.registro)["exemplo"]
            assert entrada.versao == "0.2.0" and entrada.ligada
            assert entrada.intervalo_da_atualizacao_s == 0.2, "o intervalo dela se perdeu"
            assert entrada.versao_esperando == ""
            assert manifesto_instalado("exemplo", lugares=lar).versao == "0.2.0"
        finally:
            await sup.parar()

    asyncio.run(corrida())


def test_a_chave_desligada_no_registro_nao_pergunta_ao_git(
    lar: Lugares, remoto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar_ligada(lar, remoto, atualiza_sozinha=False, intervalo_da_atualizacao_s=0.0)
    perguntas: list[str] = []
    monkeypatch.setattr(instalador, "commit_remoto", lambda e, r: perguntas.append(e) or None)

    async def corrida() -> None:
        sup = _supervisor_rapido(lar)
        await sup.iniciar()
        try:
            await _ate(lambda: _rodando(sup))
            _publicar(remoto, "0.2.0")
            await asyncio.sleep(0.5)
            assert perguntas == []
            assert ler_registro(lar.registro)["exemplo"].versao == "0.1.0"
        finally:
            await sup.parar()

    asyncio.run(corrida())


# -- o que não se instala sozinho ----------------------------------------------


def test_a_versao_que_pede_permissao_nova_fica_esperando_o_atualizar(
    lar: Lugares, remoto: Path
) -> None:
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=0.1)

    async def corrida() -> None:
        sup = _supervisor_rapido(lar)
        await sup.iniciar()
        try:
            await _ate(lambda: _rodando(sup))
            pid = sup.pid_de("exemplo")
            velho = ler_registro(lar.registro)["exemplo"].commit
            novo = _publicar(remoto, "0.2.0", permissoes=("ler:estado", "rede:internet"))
            await _ate(lambda: ler_registro(lar.registro)["exemplo"].commit_esperando == novo)
            entrada = ler_registro(lar.registro)["exemplo"]
            assert entrada.commit == velho and entrada.versao == "0.1.0"
            assert entrada.versao_esperando == "0.2.0" and entrada.ligada
            assert "rede:internet" in entrada.motivo_da_espera
            assert manifesto_instalado("exemplo", lugares=lar).permissoes == ["ler:estado"]
            assert sup.pid_de("exemplo") == pid, "a extensão viva foi parada sem trocar nada"
        finally:
            await sup.parar()

    asyncio.run(corrida())
    # A versão que espera não se baixa de novo a cada volta; o «Atualizar» a instala.
    assert commit_novo(ler_registro(lar.registro)["exemplo"]) is None
    feito = atualizar("exemplo", lugares=lar)
    assert feito.trocou and feito.permissoes_novas == ["rede:internet"]
    entrada = ler_registro(lar.registro)["exemplo"]
    assert entrada.versao == "0.2.0" and not entrada.ligada and entrada.versao_esperando == ""


def test_a_tag_oficial_que_deixa_de_conferir_com_a_chave_fica_esperando(
    lar: Lugares, curto: Path, remoto: Path
) -> None:
    if shutil.which("ssh-keygen") is None:
        pytest.skip("sem ssh-keygen")
    privada, chave_do_time = _chave(curto, "chave-do-time")
    outra, _linha = _chave(curto, "chave-de-outro")

    def assinar(com: Path) -> None:
        _git(remoto, "-c", "gpg.format=ssh", "-c", f"user.signingkey={com}",
             "tag", "-f", "-s", "v1", "-m", "assinada")

    assinar(privada)
    instalar(f"file://{remoto}", ref="v1", lugares=lar, chaves=(chave_do_time,))
    assert ler_registro(lar.registro)["exemplo"].origem == "oficial"

    novo = _publicar(remoto, "0.2.0")
    assinar(outra)
    assert commit_remoto(f"file://{remoto}", "v1") == novo
    feito = atualizar("exemplo", lugares=lar, chaves=(chave_do_time,), sozinha=True)
    assert not feito.trocou
    entrada = ler_registro(lar.registro)["exemplo"]
    assert entrada.origem == "oficial" and entrada.versao == "0.1.0"
    assert entrada.commit_esperando == novo and "chave oficial" in entrada.motivo_da_espera

    assinar(privada)
    feito = atualizar("exemplo", lugares=lar, chaves=(chave_do_time,), sozinha=True)
    assert feito.trocou and feito.entrada.origem == "oficial" and feito.entrada.versao == "0.2.0"


# -- a origem local e a falta de rede ------------------------------------------


def test_a_origem_local_nunca_se_atualiza_sozinha(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = curto / "pasta-do-mod"
    pasta.mkdir()
    (pasta / "mod.py").write_text(_O_FILHO, encoding="utf-8")
    (pasta / "hefesto-mod.json").write_text(_manifesto(), encoding="utf-8")
    instalar(str(pasta), lugares=lar)
    registro = ler_registro(lar.registro)
    registro["exemplo"].intervalo_da_atualizacao_s = 0.0
    gravar_registro(lar.registro, registro)

    def nunca(*_a: Any) -> None:
        raise AssertionError("a origem local perguntou ao git")

    monkeypatch.setattr(instalador, "commit_remoto", nunca)
    assert commit_novo(ler_registro(lar.registro)["exemplo"]) is None
    with pytest.raises(InstalacaoRecusadaError, match="não se atualiza sozinha"):
        atualizar("exemplo", lugares=lar, sozinha=True)
    sup = _supervisor_rapido(lar)

    async def uma_volta() -> None:
        # Sem o reconciliar, o registro lido está vazio e a volta não veria a extensão.
        await sup.reconciliar()
        assert "exemplo" in sup._registro_lido
        sup._talvez_atualizar()
        aberta = sup._atualizando is not None
        await sup.parar()
        assert not aberta, "a origem local abriu uma conferência"

    asyncio.run(uma_volta())


def test_sem_rede_a_extensao_viva_fica_e_o_supervisor_segue(
    lar: Lugares, remoto: Path
) -> None:
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=0.1)
    shutil.rmtree(remoto)
    entrada = ler_registro(lar.registro)["exemplo"]
    assert commit_remoto(entrada.endereco, entrada.ref) is None
    with pytest.raises(InstalacaoRecusadaError, match="não respondeu"):
        commit_novo(entrada)

    async def corrida() -> None:
        sup = _supervisor_rapido(lar)
        await sup.iniciar()
        try:
            await _ate(lambda: _rodando(sup))
            pid = sup.pid_de("exemplo")
            await asyncio.sleep(0.6)
            assert sup._laco is not None and not sup._laco.done(), "a vigia caiu sem rede"
            assert _rodando(sup) and sup.pid_de("exemplo") == pid
            assert ler_registro(lar.registro)["exemplo"] == entrada
        finally:
            await sup.parar()

    asyncio.run(corrida())


def test_a_linha_da_extensao_diz_a_versao_que_espera_o_atualizar() -> None:
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07
    from hefesto_dualsense4unix.mods.instalador import Entrada

    entrada = Entrada(id="exemplo", nome="Exemplo", versao="0.1.0", origem="comunidade",
                      endereco="file:///nada", versao_esperando="0.2.0",
                      motivo_da_espera="A versão 0.2.0 pede rede:internet.")
    linha = a07._extensao_de(a07._Instalada(entrada=entrada, manifesto=None))
    assert linha.versao == "0.1.0 · a 0.2.0 espera o «Atualizar»"
    assert "rede:internet" in linha.dica
    entrada.versao_esperando = ""
    assert a07._extensao_de(a07._Instalada(entrada=entrada, manifesto=None)).versao == "0.1.0"


def test_o_intervalo_de_fabrica_e_de_seis_horas_e_o_piso_de_um_minuto() -> None:
    """A extensão nova guarda as seis horas; o registro não desce abaixo do piso."""
    # D-1910-A-EXTENSAO-DO-GIT-CONFERE-A-CADA-SEIS-HORAS
    from hefesto_dualsense4unix.mods import supervisor
    from hefesto_dualsense4unix.mods.instalador import Entrada

    entrada = Entrada(id="exemplo", nome="Exemplo", versao="0.1.0", origem="comunidade",
                      endereco="file:///nada")
    assert entrada.intervalo_da_atualizacao_s == 6 * 3600.0
    assert supervisor.PISO_DA_ATUALIZACAO_S == 60.0
    assert supervisor.ESPERA_DEPOIS_DA_FALHA_S == 600.0



def test_o_git_que_nao_roda_e_recusa_com_o_motivo(
    lar: Lugares, remoto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _instalar_ligada(lar, remoto)

    def sem_git(*_a: Any, **_k: Any) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(instalador.subprocess, "run", sem_git)
    with pytest.raises(InstalacaoRecusadaError, match="não respondeu: git"):
        commit_remoto(f"file://{remoto}", None)
    with pytest.raises(InstalacaoRecusadaError, match="não respondeu"):
        commit_novo(ler_registro(lar.registro)["exemplo"])


def test_o_registro_ilegivel_nao_abre_conferencia(lar: Lugares, remoto: Path) -> None:
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=0.0)
    sup = _supervisor_rapido(lar)

    async def uma_volta() -> None:
        await sup.reconciliar()
        lar.registro.write_text("{ torto", encoding="utf-8")
        await sup.reconciliar()
        sup._talvez_atualizar()
        aberta = sup._atualizando is not None
        await sup.parar()
        assert not aberta, "o registro torto abriu uma conferência"

    asyncio.run(uma_volta())
