"""A atualização da extensão espera o jogo e volta se cair.

Os repositórios são ``git init`` locais, abertos por ``file://``, num lar de mentira: nenhuma
prova fala com a rede de fora, com o serviço nem com um jogo de verdade (a pergunta do jogo é
um dublê injetado no supervisor).

MORDIDAS (25/11/2026, executadas sobre a cura e devolvidas):

- a pergunta do jogo tirada do ``_talvez_atualizar`` reprova
  ``test_com_jogo_aberto_a_atualizacao_sozinha_espera_e_sem_jogo_abre``;
- a volta tirada do ``_cuidar`` reprova
  ``test_a_versao_nova_que_cai_ao_abrir_volta_para_a_anterior``;
- a prova tirada do ``dar_por_provada`` reprova
  ``test_a_versao_que_ficou_estavel_nao_volta_quando_cai_depois``.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import (
    Lugares,
    commit_novo,
    conferir_remocao,
    ler_registro,
    manifesto_instalado,
    remover,
)
from tests.unit import test_a_extensao_instalada_pelo_git_se_atualiza_sozinha as _vizinho

curto, lar, remoto = _vizinho.curto, _vizinho.lar, _vizinho.remoto
_ate, _instalar_ligada = _vizinho._ate, _vizinho._instalar_ligada
_publicar, _rodando = _vizinho._publicar, _vizinho._rodando
_supervisor_rapido = _vizinho._supervisor_rapido

_QUE_CAI = "import sys\nsys.exit(1)\n"
_ESTAVEL_UMA_VEZ = (
    "import os, sys, time\n"
    "if not os.path.exists('marca'):\n"
    "    open('marca', 'w').close()\n"
    "    time.sleep(1.0)\n"
    "sys.exit(1)\n"
)
_ESPERAS_CURTAS = (0.0, 0.0, 0.0)


def _publicar_com(origem: Path, versao: str, corpo: str) -> str:
    (origem / "mod.py").write_text(corpo, encoding="utf-8")
    return _publicar(origem, versao)


def test_com_jogo_aberto_a_atualizacao_sozinha_espera_e_sem_jogo_abre(
    lar: Lugares, remoto: Path
) -> None:
    """D-2511-A-ATUALIZACAO-DA-EXTENSAO-ESPERA-O-JOGO-E-VOLTA-SE-CAIR: com jogo, não abre."""
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=0.0)
    com_jogo = [True]
    sup = _supervisor_rapido(lar, jogo_aberto=lambda: com_jogo[0])

    async def corrida() -> None:
        await sup.reconciliar()
        try:
            await _ate(lambda: _rodando(sup))
            _publicar(remoto, "0.2.0")
            sup._talvez_atualizar()
            assert sup._atualizando is None, "a atualização abriu com jogo aberto"
            assert ler_registro(lar.registro)["exemplo"].versao == "0.1.0"
            com_jogo[0] = False
            sup._talvez_atualizar()
            assert sup._atualizando is not None, "sem jogo, a atualização não abriu"
            await sup._atualizando
            assert ler_registro(lar.registro)["exemplo"].versao == "0.2.0"
        finally:
            await sup.parar()

    asyncio.run(corrida())


def test_so_a_extensao_com_processo_espera_o_jogo(lar: Lugares, remoto: Path) -> None:
    """D-2511-A-ATUALIZACAO-DA-EXTENSAO-ESPERA-O-JOGO-E-VOLTA-SE-CAIR: a parada não espera."""
    _instalar_ligada(lar, remoto, ligada=False, intervalo_da_atualizacao_s=0.0)
    sup = _supervisor_rapido(lar, jogo_aberto=lambda: True)

    async def corrida() -> None:
        await sup.reconciliar()
        try:
            sup._talvez_atualizar()
            assert sup._atualizando is not None, "a extensão sem processo esperou o jogo"
            await sup._atualizando
        finally:
            await sup.parar()

    asyncio.run(corrida())


def test_a_versao_nova_que_cai_ao_abrir_volta_para_a_anterior(
    lar: Lugares, remoto: Path
) -> None:
    """D-2511-A-ATUALIZACAO-DA-EXTENSAO-ESPERA-O-JOGO-E-VOLTA-SE-CAIR: cai quatro, volta."""
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=0.2)
    antiga = ler_registro(lar.registro)["exemplo"].commit
    sup = _supervisor_rapido(lar, esperas=_ESPERAS_CURTAS, jogo_aberto=lambda: False)

    async def corrida() -> None:
        await sup.iniciar()
        try:
            await _ate(lambda: _rodando(sup))
            ruim = _publicar_com(remoto, "0.2.0", _QUE_CAI)
            await _ate(lambda: ler_registro(lar.registro)["exemplo"].commit_esperando == ruim)
            await _ate(lambda: _rodando(sup))
            entrada = ler_registro(lar.registro)["exemplo"]
            assert (entrada.versao, entrada.commit) == ("0.1.0", antiga)
            assert entrada.versao_esperando == "0.2.0" and entrada.ligada
            assert entrada.motivo_da_espera == (
                "A versão 0.2.0 caiu ao abrir; voltou para a 0.1.0.")
            assert not entrada.em_prova and not entrada.commit_anterior
            assert manifesto_instalado("exemplo", lugares=lar).versao == "0.1.0"
            assert "sys.exit" not in (lar.codigo / "exemplo" / "mod.py").read_text("utf-8")
            assert not (lar.codigo / ".exemplo.anterior").exists()
            assert commit_novo(entrada) is None, "o commit que caiu voltou a ser oferecido"
            await asyncio.sleep(0.6)
            assert ler_registro(lar.registro)["exemplo"].versao == "0.1.0"
        finally:
            await sup.parar()

    asyncio.run(corrida())


def test_a_versao_que_ficou_estavel_nao_volta_quando_cai_depois(
    lar: Lugares, remoto: Path
) -> None:
    """D-2511-A-ATUALIZACAO-DA-EXTENSAO-ESPERA-O-JOGO-E-VOLTA-SE-CAIR: a estável não volta."""
    _instalar_ligada(lar, remoto, intervalo_da_atualizacao_s=0.2)
    sup = _supervisor_rapido(
        lar, esperas=_ESPERAS_CURTAS, estavel_s=0.4, jogo_aberto=lambda: False)

    async def corrida() -> None:
        await sup.iniciar()
        try:
            await _ate(lambda: _rodando(sup))
            nova = _publicar_com(remoto, "0.2.0", _ESTAVEL_UMA_VEZ)
            await _ate(lambda: ler_registro(lar.registro)["exemplo"].commit == nova)
            await _ate(lambda: (e := sup.estado_de("exemplo")) is not None
                       and e.estado == "parou", prazo=20.0)
            entrada = ler_registro(lar.registro)["exemplo"]
            assert (entrada.versao, entrada.commit) == ("0.2.0", nova)
            assert not entrada.em_prova and entrada.versao_esperando == ""
        finally:
            await sup.parar()

    asyncio.run(corrida())


def test_a_guarda_e_uma_so_e_sai_com_a_remocao(lar: Lugares, remoto: Path) -> None:
    """D-2511-A-ATUALIZACAO-DA-EXTENSAO-ESPERA-O-JOGO-E-VOLTA-SE-CAIR: uma só, e some."""
    _instalar_ligada(lar, remoto, ligada=False)
    primeira = ler_registro(lar.registro)["exemplo"].commit
    segunda = _publicar(remoto, "0.2.0")
    instalador.atualizar("exemplo", lugares=lar)
    guarda = lar.codigo / ".exemplo.anterior"
    entrada = ler_registro(lar.registro)["exemplo"]
    assert (entrada.versao_anterior, entrada.commit_anterior) == ("0.1.0", primeira)
    assert entrada.em_prova and guarda.is_dir()
    _publicar(remoto, "0.3.0")
    instalador.atualizar("exemplo", lugares=lar)
    entrada = ler_registro(lar.registro)["exemplo"]
    assert (entrada.versao_anterior, entrada.commit_anterior) == ("0.2.0", segunda)
    assert "0.2.0" in (guarda / "hefesto-mod.json").read_text("utf-8")
    assert str(guarda) in conferir_remocao("exemplo", lugares=lar)
    assert remover("exemplo", lugares=lar) == []
    assert not guarda.exists()

