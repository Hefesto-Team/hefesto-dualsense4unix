"""O «nenhum efeito» de toda lista de efeito: um valor, um rótulo e uma opção só.

Gatilhos, Iluminação, Efeito háptico e Padrão dos motores mostram a mesma opção, gerada aqui:
o valor `sem_efeito`, o rótulo «—». Os nomes de antes (`nenhum` dos gatilhos, `sem-efeito` da luz,
o «—» escondido do lugar vazio e o rótulo antigo) chegam de página velha ou de perfil antigo e se
leem uma vez por `do_clique`, que devolve o valor de hoje.
"""
from __future__ import annotations

from html import escape

VALOR = "sem_efeito"
ROTULO = "—"
NOMES_VELHOS: frozenset[str] = frozenset({"nenhum", "sem-efeito", "—", "Sem efeito"})


def do_clique(valor: object) -> object:
    """O valor de hoje para o que veio do clique ou do disco; o resto passa como veio."""
    if isinstance(valor, str) and (valor.strip() in NOMES_VELHOS or valor.strip() == VALOR):
        return VALOR
    return valor


def e_sem_efeito(valor: object) -> bool:
    """`True` para o valor de hoje e para qualquer nome velho dele."""
    return do_clique(valor) == VALOR


def opcao(dica: str = "", escolhida: bool = False) -> str:
    """A `<option>` do nenhum efeito, igual em toda lista."""
    titulo = f' title="{escape(dica, quote=True)}"' if dica else ""
    marca = " selected" if escolhida else ""
    return f'<option value="{VALOR}"{titulo}{marca}>{ROTULO}</option>'
