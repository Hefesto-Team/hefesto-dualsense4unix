"""A dica do rodapé nomeia o perfil ATIVO, e nunca o exemplo do desenho.

O DEFEITO, medido em 03/09/2026 pela régua do mockup e nomeado pelo juiz da
leva: as DEZ abas diziam *"Grava no perfil **Mortal Kombat**"* no ``title`` do
botão "Salvar Perfil", com ``meu_perfil`` ativo.

**O nome veio do pedido dela, e era um EXEMPLO.** Ela escreveu *"'Aplicar vale
agora • Salvar Perfil grava no Mortal Kombat' isso deveria em formato de
tooltip"*, e o ``fim.html`` congelou o exemplo em vez do nome. O comentário do
próprio arquivo já dizia o que importava — *o NOME do perfil, "a informação que
faltava e lhe custou semanas"* — e era exatamente essa informação que a dica
estava errando.

**Por que isto é grave e não cosmético:** a dica aparece sobre o botão que
GRAVA NO DISCO, e nomeia com confiança um perfil que não é o dela. Quem lê a
dica antes de clicar decide com base numa afirmação falsa.

AS DUAS METADES SÃO UMA CURA SÓ:

* o texto CONGELADO do ``fim.html`` passa a ser honesto sozinho — *"no perfil
  ativo"* —, para quem vê a página antes de o produto pintar;
* o produto o troca pelo nome de verdade, pelo alvo ``atributo``, que nasceu em
  03/09/2026 e é o que sabe escrever num ``title``.

A MORDIDA: tire ``rodape.salvar`` de :func:`pacotes.topo` e
:func:`test_a_dica_sai_com_o_nome_do_perfil_ativo` reprova; devolva o nome
literal ao ``fim.html`` e :func:`test_o_desenho_congelado_nao_nomeia_perfil`
reprova.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde, pacotes

#: AS DEZ PÁGINAS que o produto renderiza. O rodapé é um só para todas —
#: `fim.html` — e é por isso que um literal ali custa dez vezes.
PAGINAS = tuple(f"{n:02d}-" for n in range(1, 11))


class _Ctx:
    """O mínimo de ``Contexto`` que ``topo`` lê."""

    def __init__(self, ativo: str, mesa: list[dict[str, Any]] | None = None) -> None:
        self.state = {"active_profile": ativo}
        self.mesa = mesa or []


def test_a_dica_sai_com_o_nome_do_perfil_ativo() -> None:
    """Com um perfil ativo, as duas dicas o nomeiam."""
    campos = pacotes.topo(_Ctx("meu_perfil"))
    assert "meu_perfil" in campos["rodape.salvar"], campos["rodape.salvar"]
    assert "meu_perfil" in campos["rodape.exportar"], campos["rodape.exportar"]


def test_sem_perfil_ativo_nao_se_inventa_nome() -> None:
    """Sem perfil ativo, a dica cai para a mesma palavra do desenho.

    Escrever *"Grava no perfil —"* seria pior do que não dizer: um travessão
    onde se espera um nome lê-se como nome. A frase tem de continuar uma frase.
    """
    campos = pacotes.topo(_Ctx(""))
    assert "no perfil ativo" in campos["rodape.salvar"]
    assert "—" not in campos["rodape.salvar"]
    assert "o perfil ativo" in campos["rodape.exportar"]
    assert "—" not in campos["rodape.exportar"]


def test_a_dica_continua_dizendo_o_que_o_botao_faz() -> None:
    """A cura não pode ter encurtado a frase até tirar o que ela ensina.

    A decisão que o rodapé protege é a diferença entre APLICAR (vale agora) e
    SALVAR (grava no perfil). Trocar o nome não pode ter levado isso junto.
    """
    campos = pacotes.topo(_Ctx("meu_perfil"))
    assert "volta sozinho toda vez que este jogo abrir" in campos["rodape.salvar"]
    assert ".json" in campos["rodape.exportar"]


def test_o_desenho_congelado_nao_nomeia_perfil() -> None:
    """O ``fim.html`` — o rodapé das dez — não pode trazer nome de perfil.

    Ele é o que a tela mostra ANTES de o produto pintar, e numa página que ela
    ainda não publicou é o que ela mostra SEMPRE. Um nome ali é uma afirmação
    que o produto não fez.
    """
    fim = (onde.AQUI / "fim.html").read_text(encoding="utf-8")
    # SÓ AS LINHAS DE MARCAÇÃO: os comentários citam o pedido dela, que traz o
    # exemplo, e censurar a citação apagaria a razão de a cura existir.
    marcacao = "\n".join(
        ln for ln in fim.splitlines() if "<button" in ln or "title=" in ln)
    assert "Mortal Kombat" not in marcacao, (
        "o rodapé congelado voltou a nomear um perfil de exemplo")
    assert "no perfil ativo" in marcacao


@pytest.mark.parametrize("pagina", PAGINAS)
def test_nenhuma_pagina_da_bancada_promete_o_perfil_errado(pagina: str) -> None:
    """A régua olha a BANCADA — o desenho de HOJE, que é o que tem dono aqui.

    NÃO O PUBLICADO, e a distinção é a armadilha mais cara do
    `COMO-OLHAR-A-TELA.md`: apontar para o publicado daria **verde sobre a
    página congelada**. Mas o inverso também vale — cobrar aqui a página que só
    ELA pode republicar seria pôr num teste desta suíte uma dívida que não é de
    quem a roda. **A lacuna de publicação já tem dono**, e ele a relata com
    nome e número: `scripts/check_o_desenho_aprovado.py`.
    """
    caminhos = sorted(onde.saida().glob(f"{pagina}*.html"))
    if not caminhos:
        pytest.skip(f"não há página na bancada para {pagina}")
    dicas = re.findall(r'title="([^"]*)"', caminhos[0].read_text(encoding="utf-8"))
    culpadas = [d for d in dicas if "perfil Mortal Kombat" in d]
    assert not culpadas, (
        f"{caminhos[0].name} promete gravar num perfil que não é o dela: "
        f"{culpadas}. Rode o gerador daquela aba.")
