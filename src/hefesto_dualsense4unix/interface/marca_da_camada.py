"""A marca da camada: de quem é o valor que um cartão mostra. Uma peça, um lugar."""
from __future__ import annotations

import html

COMPUTADOR = "PC"

SO_NESTE_JOGO = "so-neste-jogo"
VOLTAR_AO_DO_COMPUTADOR = "voltar-ao-do-computador"
TEXTO_SO_NESTE_JOGO = "Só neste jogo"
TEXTO_VOLTAR = "Voltar ao do PC"

DICA_SO_NESTE_JOGO = ("Guarda este cartão no perfil do jogo ativo. Daí em diante, "
                      "o que você mudar aqui vale só neste jogo.")
DICA_VOLTAR = "Tira a escolha deste jogo: volta a valer o do computador."


def campo(cartao: str) -> str:
    """O endereço da marca daquele cartão (``data-campo``)."""
    return f"camada-{cartao}"


def miolo(cartao: str, *, jogo: str = "", sobrepoe: bool = False) -> str:
    """O que vai dentro da marca: o dono do valor e o botão que muda o dono."""
    linha = html.escape(cartao, quote=True)
    if jogo and sobrepoe:
        dono = html.escape(jogo)
        botao = (f'<a class="camada-volta" data-gesto="{VOLTAR_AO_DO_COMPUTADOR}" '
                 f'data-linha="{linha}" title="{html.escape(DICA_VOLTAR, quote=True)}">'
                 f"{TEXTO_VOLTAR}</a>")
    elif jogo:
        dono = COMPUTADOR
        botao = (f'<a class="camada-so" data-gesto="{SO_NESTE_JOGO}" '
                 f'data-linha="{linha}" '
                 f'title="{html.escape(DICA_SO_NESTE_JOGO, quote=True)}">'
                 f"{TEXTO_SO_NESTE_JOGO}</a>")
    else:
        dono = COMPUTADOR
        botao = ""
    return (f'<span class="camada-dono" aria-label="{dono}">{dono}</span>'
            f"{botao}")


def bloco(cartao: str, *, jogo: str = "", sobrepoe: bool = False) -> str:
    """A marca inteira, com o endereço: o que os geradores põem no cabeçalho."""
    return (f'<span class="camada" data-campo="{campo(cartao)}" data-hef-alvo="html">'
            f"{miolo(cartao, jogo=jogo, sobrepoe=sobrepoe)}</span>")


def rotuladas(pares: tuple[tuple[str, str], ...]) -> str:
    """Mais de uma marca no mesmo cabeçalho, cada uma com o nome do cartão."""
    return ('<span class="camadas">' + "".join(
        f'<span class="camada-rot">{rotulo}</span>{bloco(cartao)}'
        for cartao, rotulo in pares) + "</span>")


#: NO LUGAR VAZIO A MARCA SOME: o piloto põe ``data-conectado="nao"`` no
CSS = """
.camadas{display:inline-flex;align-items:center;gap:6px;margin-left:auto;height:17px}
.camada-rot{font-size:11px;line-height:17px;color:var(--texto-mudo,#9aa0b4)}
.camada{display:inline-flex;gap:6px;align-items:center;height:17px;max-width:100%;
  font-size:11px;line-height:15px;color:var(--texto-mudo,#9aa0b4);white-space:nowrap}
.camada-dono{padding:0 6px;border:1px solid currentColor;border-radius:8px;
  flex:0 100 auto;min-width:0;max-width:120px;overflow:hidden;text-overflow:ellipsis}
.camada a{flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;
  cursor:pointer;color:var(--cyan,#8be9fd);text-decoration:none}
.camada a:hover{text-decoration:underline}
[data-conectado="nao"] .camada{visibility:hidden}
"""


__all__ = [
    "COMPUTADOR",
    "CSS",
    "DICA_SO_NESTE_JOGO",
    "DICA_VOLTAR",
    "SO_NESTE_JOGO",
    "TEXTO_SO_NESTE_JOGO",
    "TEXTO_VOLTAR",
    "VOLTAR_AO_DO_COMPUTADOR",
    "bloco",
    "campo",
    "miolo",
    "rotuladas",
]
