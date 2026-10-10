"""As marcas do jogo: etiquetas que a pessoa põe no perfil, por cima do estilo.

O estilo (`profiles/estilos_de_jogo.py`) é receita: gatilho, vibração, luz e modo, um
por perfil. A marca é eixo à parte: um jogo pode ser visual novel E adulto, com
qualquer estilo. Este módulo é o dono do vocabulário (`Profile.marcas` guarda as
chaves) e da regra do que cada marca liga.

A marca é só da pessoa: nada a sugere pela rede, e ela não sai da máquina (escolha
dela de 09/10/2026, AS-MARCAS-VISUAL-NOVEL-E-ADULTO-SE-SOMAM-AO-ESTILO-01).
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Marca:
    """Uma marca: a chave gravada no perfil, o rótulo da tela e o que ela liga."""

    chave: str
    rotulo: str
    liga: str


VISUAL_NOVEL = Marca(
    "visual_novel",
    "Visual novel",
    "Com o estilo Point-and-click, os botões seguem o molde de visual novel "
    "(avançar, voltar o texto, pular, menu, esconder a caixa). Com outro estilo, "
    "nada muda no controle: o jogo que aceita controle fica com o jogo.",
)
ADULTO = Marca(
    "adulto",
    "Adulto",
    "Não muda nada no controle nem na tela. Só uma modificação com a permissão "
    "de ler as marcas do perfil a enxerga, e nenhuma liga acessório sozinha.",
)

MARCAS: tuple[Marca, ...] = (VISUAL_NOVEL, ADULTO)
POR_CHAVE: dict[str, Marca] = {m.chave: m for m in MARCAS}

#: O estilo em que a marca «Visual novel» troca a tabela dos botões.
ESTILO_DO_MOLDE = "point_and_click"


def rotulos(marcas: Iterable[str] | None) -> list[str]:
    """Os rótulos das marcas conhecidas, na ordem do vocabulário.

    A chave desconhecida (uma marca que saiu do produto) fica de fora sem recusar o
    perfil, como o estilo.
    """
    tem = set(marcas or ())
    return [m.rotulo for m in MARCAS if m.chave in tem]


def molde_dos_botoes(estilo: str | None, marcas: Iterable[str] | None) -> str | None:
    """A chave do molde da tabela de botões que as marcas pedem, ou ``None``.

    Só a «Visual novel» com o estilo Point-and-click escolhe molde; a «Adulto» nunca
    escolhe nada.
    """
    if estilo == ESTILO_DO_MOLDE and VISUAL_NOVEL.chave in set(marcas or ()):
        return VISUAL_NOVEL.chave
    return None
