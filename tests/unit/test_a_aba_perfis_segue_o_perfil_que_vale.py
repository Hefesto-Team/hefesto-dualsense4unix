"""O CHIP «PERFIL ATIVO» NASCE SEM NOME, e só o pintor o nomeia.

O DEFEITO, na tela dela em 13/09/2026 (PERFIS-TIRA-BUSCA-ATIVO-01, §4.1,
absorvido pela VAO-DO-ESQUELETO-01): com o perfil que valia ativado pela aba
Perfis, o chip do topo dizia o nome de OUTRO perfil — o do exemplo do desenho.
O literal morava no ``topo.html``, que entra inteiro nas dez páginas, e ficava
na tela até o primeiro tique de cada aba e sempre que a pintura falhava.

A CURA É O QUE O PINTOR JÁ ESCREVE QUANDO NÃO HÁ PERFIL ATIVO. A régua não
digita esse valor: ela pergunta a ``pacotes.topo()`` o que ele escreve sem
perfil, e cobra que as vinte páginas (a bancada e o publicado) nasçam com isso.
Pintura que falha passa a mostrar ausência, nunca um perfil falso.

A MORDIDA: devolva ao ``topo.html`` um nome de perfil no chip, regere e
publique — :func:`test_as_dez_paginas_nascem_sem_nome_de_perfil` reprova nas
vinte. Tire ``perfil`` de ``pacotes.topo()`` e
:func:`test_o_pintor_nomeia_o_perfil_que_vale` reprova: o chip ficaria no
travessão para sempre, que é a outra metade do mesmo defeito.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import onde, pacotes

#: O CHIP E O ENDEREÇO DELE. Sem o endereço o pintor não tem onde escrever, e
#: a página nascer neutra deixaria de ser a metade de uma cura para ser a cura
#: inteira de um chip que nunca muda.
CHIP = re.compile(r'<span class="pa-nome"([^>]*)>([^<]*)</span>')

ABAS = tuple(f"{n:02d}-" for n in range(1, 11))


class _Ctx:
    """O mínimo de ``Contexto`` que ``topo`` lê (o mesmo molde da régua do rodapé)."""

    def __init__(self, ativo: str) -> None:
        self.state: dict[str, Any] = {"active_profile": ativo}
        self.mesa: list[dict[str, Any]] = []


def _sem_perfil() -> str:
    """O que o pintor escreve no chip quando nenhum perfil está valendo."""
    return str(pacotes.topo(_Ctx(""))["perfil"])


def _paginas() -> list[Any]:
    """As vinte páginas: o publicado e a bancada, cada um com as dez abas.

    **RÉGUA QUE ACHA ZERO NÃO É RÉGUA VERDE**: uma aba que falte em qualquer das
    duas pastas reprova na coleta, em vez de sair da conta calada.
    """
    fora = []
    for pasta, rotulo in ((onde.PUBLICADO, "publicado"), (onde.BANCADA, "bancada")):
        for prefixo in ABAS:
            achadas = sorted(pasta.glob(f"{prefixo}*.html"))
            assert achadas, f"não há página {prefixo}* em {pasta} ({rotulo})"
            nome = f"{rotulo}/{achadas[0].name}"
            fora.append(pytest.param(nome, achadas[0], id=nome))
    return fora


def test_o_pintor_nomeia_o_perfil_que_vale() -> None:
    """A metade positiva: com um perfil valendo, o chip recebe o nome dele."""
    assert pacotes.topo(_Ctx("meu_perfil"))["perfil"] == "meu_perfil"
    sem = _sem_perfil()
    assert sem and sem != "meu_perfil", (
        f"sem perfil ativo o pintor escreve {sem!r} — a régua abaixo compararia "
        f"as páginas com um valor que não distingue nada")


@pytest.mark.parametrize("rotulo,caminho", _paginas(), ids=lambda v: str(v))
def test_as_dez_paginas_nascem_sem_nome_de_perfil(rotulo: str, caminho: Any) -> None:
    """Toda página nasce com o chip que o pintor escreveria sem perfil ativo."""
    texto = caminho.read_text(encoding="utf-8")
    chips = CHIP.findall(texto)
    assert len(chips) == 1, (
        f"{rotulo}: esperava UM chip «Perfil ativo», achei {len(chips)}")
    atributos, nome = chips[0]
    assert 'data-campo="perfil"' in atributos, (
        f"{rotulo}: o chip perdeu o endereço da pintura ({atributos!r})")
    assert nome.strip() == _sem_perfil(), (
        f"{rotulo}: o chip nasce dizendo {nome.strip()!r} — um perfil que o "
        f"produto não afirmou. Sem pintura ele tem de dizer {_sem_perfil()!r}, "
        f"que é o que `pacotes.topo()` escreve quando nada está valendo.")
