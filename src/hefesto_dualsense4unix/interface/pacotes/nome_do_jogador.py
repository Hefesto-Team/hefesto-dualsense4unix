"""O nome que ela deu ao controle, com UM leitor e o filtro dele junto.

A-LINHA-MODELO-DIZ-O-NOME-DO-JOGADOR-01 (06/10/2026, ela: *«em qualquer aba onde tivermos modelo
tem que aparecer o nome do jogador também.»*). O nome tem dono desde a 08: o ``Alias`` do BlueZ,
que ela escreve no campo «dono» da Conexões. As abas que dizem o modelo (a 04 e a 05) o leem
POR AQUI, e a 08 também: o filtro mora ao lado do leitor, porque sem ele o ``Alias`` de fábrica
(«DualSense Wireless Controller») ou o que é o próprio endereço viraria «nome do jogador» e o
endereço iria para a tela.

A leitura em fundo (``_em_fundo``, validade de 3 s) continua na 08, que a divide com a seção do
rádio e o sino; aqui só se pergunta a ela, com import tardio (a 08 importa este módulo).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

NOMES_DE_FABRICA = ("DualSense", "Wireless Controller")

#: um ``Alias`` que é o endereço (``AA-BB-CC-DD-EE-FF``) não é nome de ninguém
ALIAS_QUE_E_ENDERECO = re.compile(r"[0-9A-Fa-f]{2}([-:_][0-9A-Fa-f]{2}){5}")


def mac(valor: object) -> str:
    """O endereço na forma única da casa (``AA:BB:CC:DD:EE:FF``), ou vazio."""
    return str(norm_mac(str(valor or "")) or "").upper()


def nome_dado(nome: str) -> str:
    """O nome que ela deu (controle ou adaptador), com a primeira letra maiúscula.

    Ordem de 05/10/2026, 13h: *«Nome que o user colocar pra controle mesmo se ele colocar
    minúsculo o app corrige colocando a primeira letra maiúscula»*. Só a primeira letra; o resto
    fica como o usuário escreveu. Vale ao gravar e ao ler o que já estava gravado em minúscula.
    <!-- noqa-acento: citação literal -->
    """
    nome = str(nome or "").strip()
    return nome[:1].upper() + nome[1:]


def e_nome_de_fabrica(nome: str) -> bool:
    return any(nome.startswith(f) for f in NOMES_DE_FABRICA)


def e_nome_dela(nome: str) -> bool:
    """Um ``Alias`` que ela pode ter dado: nem o de fábrica, nem o endereço."""
    return bool(nome) and not e_nome_de_fabrica(nome) and not ALIAS_QUE_E_ENDERECO.fullmatch(nome)


def nomes_por_endereco(aparelhos_bz: tuple[Any, ...],
                       e_controle: Callable[[Any], bool] | None = None) -> dict[str, str]:
    """O nome que ela deu a cada controle, pelo ENDEREÇO — um só por aparelho.

    `e_controle` diz se o aparelho é um controle (o dono é a 08, que o divide com a central); só o
    controle ganha a primeira letra maiúscula, o adaptador fica como veio.
    """
    if e_controle is None:
        from . import a08_conexoes

        e_controle = a08_conexoes._e_controle_do_bluez
    nomes: dict[str, str] = {}
    for a in sorted(aparelhos_bz, key=lambda a: getattr(a, "conectado", None) is not True):
        nome = str(getattr(a, "nome", "") or "").strip()
        endereco = mac(getattr(a, "endereco", ""))
        if endereco and e_nome_dela(nome) and endereco not in nomes:
            nomes[endereco] = nome_dado(nome) if e_controle(a) else nome
    return nomes


def nomes_dos_donos() -> dict[str, str]:
    """``{endereço: nome}`` do ``Alias`` do BlueZ, lido em fundo pela 08; sem leitura, vazio."""
    from . import a08_conexoes

    return a08_conexoes._nomes_dos_donos()


def o_nome_de(nomes: dict[str, str], uniq: object) -> str:
    """O nome que ela deu ao controle `uniq`, ou vazio (o número «P N» é da linha)."""
    return nomes.get(mac(uniq), "")
