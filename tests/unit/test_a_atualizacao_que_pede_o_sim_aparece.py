"""A atualização que pede o «sim» aparece na tela (16/11/2026).

A-ATUALIZACAO-QUE-PEDE-O-SIM-APARECE-01, decisão D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO.

Medido: a extensão ligada que se atualiza para uma versão que pede uma permissão nova troca o
código e fica desligada, à espera do «sim», e a linha da extensão dizia só «Desligada». Agora a
linha e a janela da extensão dizem «Atualização esperando o seu sim», com o botão que mostra a
permissão nova; o «sim» dado (ligar) apaga o aviso.

MORDIDAS: o instalador sem a marca ``espera_o_sim`` reprova a linha e a janela; a marca que o
``ligar`` não apaga reprova o aviso depois do «sim».
"""
from __future__ import annotations

import json
import pathlib
import re
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.mods.instalador import instalar, ler_registro, ligar
from hefesto_dualsense4unix.mods.manifesto import pedidos_do_sim
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    _a07,
    _fonte,
    ctx,
    lar,
)

_o_pacote: Callable[[], Any] = _a07
ESTADO = "publicar:acessorios.estado"
ESTILO = "ler:jogo.estilo"
LIGAR = {"id": "ligada", "rotulo": "Ligada", "tipo": "ligado", "padrao": True}  # (noqa-acento)


def _versao(pasta: pathlib.Path, versao: str, permissoes: list[str]) -> None:
    arquivo = pasta / "hefesto-mod.json"
    manifesto = json.loads(arquivo.read_text(encoding="utf-8"))
    manifesto.update(versao=versao, permissoes=permissoes)  # (noqa-acento)
    arquivo.write_text(json.dumps(manifesto), encoding="utf-8")


def _ligada_e_atualizada(lar: Any, tmp_path: pathlib.Path) -> pathlib.Path:  # noqa: F811
    pasta = _fonte(tmp_path, permissoes=(ESTADO,), opcoes=[LIGAR], extra={"chave": "ligada"})
    feito = instalar(str(pasta), lugares=lar)
    ligar("toque", permissoes_vistas=pedidos_do_sim(feito.manifesto), lugares=lar)
    _versao(pasta, "0.2", [ESTADO, ESTILO])
    instalar(str(pasta), lugares=lar)
    return pasta


def _linha(ctx: Any) -> str:  # noqa: F811
    a07 = _o_pacote()
    a07.REGISTRO.esquecer()
    return str(a07.pacote(ctx)["blocos"][".ext-lista"])


def test_a_atualizacao_que_pede_permissao_nova_marca_a_espera_e_o_sim_a_apaga(
        lar: Any, tmp_path: pathlib.Path) -> None:  # noqa: F811
    _ligada_e_atualizada(lar, tmp_path)
    entrada = ler_registro(lar.registro)["toque"]
    assert (entrada.versao, entrada.ligada, entrada.espera_o_sim) == ("0.2", False, True)
    ligar("toque", permissoes_vistas=[ESTADO, ESTILO], lugares=lar)
    entrada = ler_registro(lar.registro)["toque"]
    assert entrada.ligada and not entrada.espera_o_sim


def test_a_extensao_nunca_ligada_nao_diz_que_a_atualizacao_espera(
        lar: Any, tmp_path: pathlib.Path, ctx: Any) -> None:  # noqa: F811
    pasta = _fonte(tmp_path, permissoes=(ESTADO,))
    instalar(str(pasta), lugares=lar)
    _versao(pasta, "0.2", [ESTADO, ESTILO])
    instalar(str(pasta), lugares=lar)
    assert not ler_registro(lar.registro)["toque"].espera_o_sim
    assert exp.ATUALIZACAO_ESPERANDO not in _linha(ctx)


def test_a_linha_diz_que_a_atualizacao_espera_o_sim_e_o_botao_mostra_a_permissao(
        lar: Any, tmp_path: pathlib.Path, ctx: Any) -> None:  # noqa: F811
    """D-1611-O-MODO-IMERSAO-TOCA-EM-TODO-JOGO: a linha diz a espera, e o botão abre o ⋮ com a
    permissão nova escrita por extenso."""
    _ligada_e_atualizada(lar, tmp_path)
    linha = _linha(ctx)
    assert exp.ATUALIZACAO_ESPERANDO in linha
    botao = re.search(r'<button class="btn mini ext-ver-sim" data-gesto="mais-da-modificacao" '
                      r'data-v="toque:permissoes">([^<]+)</button>', linha)  # (noqa-acento)
    assert botao and botao.group(1) == exp.ROTULO_DA_PERMISSAO_NOVA
    a07 = _o_pacote()
    carga = a07.mais_da_modificacao(ctx, {"v": "toque:permissoes"}, None)  # (noqa-acento)
    assert "estilo" in carga["blocos"][".ext-lista"].split('class="ext-perm"')[1].casefold()
    ligar("toque", permissoes_vistas=[ESTADO, ESTILO], lugares=lar)
    assert exp.ATUALIZACAO_ESPERANDO not in _linha(ctx)


def test_a_janela_da_extensao_diz_a_espera_com_a_permissao_nova(
        lar: Any, tmp_path: pathlib.Path, ctx: Any) -> None:  # noqa: F811
    _ligada_e_atualizada(lar, tmp_path)
    a07 = _o_pacote()
    carga = a07.configurar_modificacao(ctx, {"v": "toque"}, None)
    janela = exp.janela_pintada(carga["blocos"])
    espera = re.search(r'<div class="ja-espera-sim">(.*?)</details></div>', janela, re.S)
    assert espera and exp.ATUALIZACAO_ESPERANDO in espera.group(1)
    assert f"<summary>{exp.ROTULO_DA_PERMISSAO_NOVA}</summary>" in espera.group(1)
    assert "estilo" in espera.group(1).split("</summary>")[1].casefold()
    ligar("toque", permissoes_vistas=[ESTADO, ESTILO], lugares=lar)
    a07.REGISTRO.esquecer()
    carga = a07.configurar_modificacao(ctx, {"v": "toque"}, None)
    assert "ja-espera-sim" not in exp.janela_pintada(carga["blocos"])
