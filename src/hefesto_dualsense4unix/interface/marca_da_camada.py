"""A marca da camada: de quem é o valor que um cartão mostra. Uma peça, um lugar.

O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01 (01/10/2026). O som, os sensores,
a luz, a vibração, o mouse e o teclado têm um padrão do computador, e o perfil
do jogo só sobrepõe (`profiles/o_padrao_do_computador.SECOES`). O cabeçalho de
cada um desses cartões diz onde o clique grava:

- «Computador», com «Só neste jogo» ao lado quando há um jogo ativo;
- o nome do jogo, com «Voltar ao do computador», quando o jogo o sobrepõe;
- só «Computador», com o Freestyle ou sem perfil: o Freestyle não sobrepõe nada.

A marca é estado, e nunca frase sobre o que acabou de acontecer. Os geradores
da 02, da 04, da 05 e da 06 a desenham com :func:`bloco`; o pacote
(`pacotes/camada.py`) reescreve o miolo a cada tique com :func:`miolo`. É a
mesma função dos dois lados, e por isso o desenho e o produto não divergem.
"""
from __future__ import annotations

import html

#: A palavra da marca quando o valor é do computador (a palavra dela; «mesa» é
#: palavra banida na tela).
COMPUTADOR = "Computador"

#: Os dois gestos da marca, e os textos dos dois botões.
SO_NESTE_JOGO = "so-neste-jogo"
VOLTAR_AO_DO_COMPUTADOR = "voltar-ao-do-computador"
TEXTO_SO_NESTE_JOGO = "Só neste jogo"
TEXTO_VOLTAR = "Voltar ao do computador"

#: As dicas dos dois botões (o `?` da casa é o `title`).
DICA_SO_NESTE_JOGO = ("Guarda este cartão no perfil do jogo ativo. Daí em diante, "
                      "o que você mudar aqui vale só neste jogo.")
DICA_VOLTAR = "Tira a escolha deste jogo: volta a valer o do computador."


def campo(cartao: str) -> str:
    """O endereço da marca daquele cartão (``data-campo``)."""
    return f"camada-{cartao}"


def miolo(cartao: str, *, jogo: str = "", sobrepoe: bool = False) -> str:
    """O que vai dentro da marca: o dono do valor e o botão que muda o dono.

    ``jogo`` é o nome do perfil ativo quando ele é um jogo (vazio com o
    Freestyle ou sem perfil); ``sobrepoe`` diz se ele escolheu este cartão.
    """
    linha = html.escape(cartao, quote=True)
    rotulo = ""
    if jogo and sobrepoe:
        dono = html.escape(jogo)
        # O nome do jogo pode ser cortado com reticências numa coluna estreita;
        # o `aria-label` guarda o nome inteiro (e não vira dica: seria a cópia
        # exata do texto ao lado).
        rotulo = f' aria-label="{html.escape(jogo, quote=True)}"'
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
    return f'<span class="camada-dono"{rotulo}>{dono}</span>{botao}'


def bloco(cartao: str, *, jogo: str = "", sobrepoe: bool = False) -> str:
    """A marca inteira, com o endereço: o que os geradores põem no cabeçalho."""
    return (f'<span class="camada" data-campo="{campo(cartao)}" data-hef-alvo="html">'
            f"{miolo(cartao, jogo=jogo, sobrepoe=sobrepoe)}</span>")


def rotuladas(pares: tuple[tuple[str, str], ...]) -> str:
    """Mais de uma marca no mesmo cabeçalho, cada uma com o nome do cartão.

    ``pares`` é ``((cartão, rótulo), …)``. O grupo leva o empurrão para a
    direita (``margin-left:auto``): com as marcas soltas, cada uma pediria o
    vão e o flex o partiria entre elas.
    """
    return ('<span class="camadas">' + "".join(
        f'<span class="camada-rot">{rotulo}</span>{bloco(cartao)}'
        for cartao, rotulo in pares) + "</span>")


#: A FOLHA DA MARCA, uma vez por página: discreta, no canto do cabeçalho.
#:
#: A ALTURA É 17px, a do `.quadro-titulo` e a da `.porta` da 06: o cabeçalho
#: é `align-items:center`, e um filho mais alto desceria o quadro inteiro (a
#: primeira porta da 06, com 19px, moveu 663 caixas por 2px). Por isso a borda
#: da palavra não tem preenchimento vertical.
#:
#: NUMA COLUNA ESTREITA QUEM ENCOLHE PRIMEIRO É O NOME, com reticências (o
#: `flex-shrink` dele é cem vezes o do botão), e o nome inteiro fica no
#: `aria-label`. O botão só encolhe quando o nome já não tem o que dar.
#:
#: NO LUGAR VAZIO A MARCA SOME: o piloto põe ``data-conectado="nao"`` no
#: bloco do lugar que esvazia, e um lugar sem controle não tem de quem ser.
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
