"""O dono da GRAFIA do nome de uma entrada — «Entrada 3», «Meio», «na Entrada 3».

O-MAPA-QUE-ELA-CORRIGE-01, 26/09/2026 (D-2609-O-NOME-E-DA-POSICAO). O pedido
dela, com o mapa aberto: *«me referi as portas renomear»*. O nome passa a ser da
POSIÇÃO — ``mapa.portas[N].nome``, até 24 caracteres —, e a tela inteira o
compõe por aqui.

UM DONO, EM DUAS METADES, UMA PARA CADA FATO
--------------------------------------------

* **Aqui mora a grafia**, e só a stdlib: a palavra, o nome que vale, o rótulo,
  a frase e o artigo. As ordens (``integrations/ordens_da_mesa``, stdlib por
  contrato) compõem daqui sem carregar o ``pydantic``.
* **A leitura do nome mora no** ``integrations/entrada_a_entrada``
  (``nome_da_entrada``, ``rotulo_do_numero``, ``rotulos_das_entradas``): é o
  único lugar que conhece onde o nome está no ``maquina.json``.

O ARTIGO É SEMPRE FEMININO, porque concorda com «entrada» e não com o nome. O
governador adivinhava o gênero pelo nome e dizia «O 13 já tem…» e «o Meio»;
aqui a frase é «a entrada Meio», «na Entrada 3».

O NOME QUE NÃO É NOME. Treze das quinze entradas da máquina em que isto
nasceu se chamavam pelo próprio número («2», «15»): o Mapear gravava o número
como nome. Um número de entrada (o dela ou o de outra), ou «Entrada N», é
tratado como ausente (:func:`nome_que_vale`) — senão a tela diria «Entrada: 2».
"""

from __future__ import annotations

import re

#: A palavra do produto para o buraco no gabinete (``D-A-PALAVRA-ENTRADA``). É o
#: nome da entrada quando ela não deu outro: «Entrada 3». Ela morava no
#: ``entrada_a_entrada`` até 26/09/2026, que a reexporta.
PALAVRA_DA_ENTRADA = "Entrada"

#: A palavra no meio da frase, antes do nome que ela deu: «a entrada Meio». A
#: página do mapa a recebe do gerador, como a :data:`PALAVRA_DA_ENTRADA`.
PALAVRA_NA_FRASE = PALAVRA_DA_ENTRADA.lower()

#: A FACE QUE UM HUB DECLARADO GANHA NO DISCO — O-MAPA-DAS-CONEXOES-NO-PRODUTO-01.
#: É a CHAVE da face (o nome gravado em ``mapa.faces``), e leva o número: a troca
#: de duas entradas renomeia a face pelo número (D-2609-TROCAR-MOVE-O-BURACO). O
#: que a tela escreve no cabeçalho é :func:`titulo_do_hub`, com o nome dela.
FACE_DO_HUB_DECLARADO = f"Hub na {PALAVRA_DA_ENTRADA} {{numero}}"

#: O teto do nome de uma entrada, em caracteres — o que cabe no plugue do mapa.
MAXIMO_DO_NOME_DA_ENTRADA = 24

#: A frase da recusa de um nome comprido demais — a mesma no gravador e na
#: régua de língua.
FRASE_DO_NOME_COMPRIDO = f"O nome da entrada tem até {MAXIMO_DO_NOME_DA_ENTRADA} letras."


#: Um número de entrada escrito como nome — «3», «15a», «Entrada 12» —, a forma
#: do ``utils/maquina._NUMERO_DE_ENTRADA`` com a palavra opcional na frente.
_SO_O_NUMERO = re.compile(
    rf"^(?:{re.escape(PALAVRA_NA_FRASE)}\s+)?[0-9]{{1,3}}[a-z]?$", re.IGNORECASE)


def _aparado(texto: str | None) -> str:
    return " ".join(str(texto or "").split())


def nome_que_vale(numero: str | None, nome: str | None) -> str | None:
    """O nome dela, ou ``None`` quando ele não é nome.

    Vazio não é nome; o próprio número («2») não é nome; «Entrada 2» não é
    nome. Os três são o rótulo de reserva escrito por extenso, e tratá-los como
    nome faria a tela dizer «Entrada: 2» e «O 13».

    E NENHUM NÚMERO DE ENTRADA É NOME, nem o de outra (a conferência da
    O-MAPA-QUE-ELA-CORRIGE-01, 26/09/2026). MEDIDO no disco em que isto nasceu:
    o ``mapa`` trocou o buraco da 3 com o da 4 sem mexer nos ``lugares``, e o
    «3» que o Mapear gravou no lugar do hub passou a ser lido como o nome da
    Entrada 4 — a tela dizia «3» sobre a 4. «3», «15a» e «Entrada 12» são
    sempre o número escrito à mão; «USB 3» e «Hub 2» continuam nome.
    """
    limpo = _aparado(nome)
    if not limpo:
        return None
    if _SO_O_NUMERO.match(limpo):
        return None
    numero_limpo = _aparado(numero)
    if numero_limpo:
        dobrado = limpo.casefold()
        if dobrado in (numero_limpo.casefold(),
                       f"{PALAVRA_NA_FRASE} {numero_limpo}".casefold()):
            return None
    return limpo


def rotulo(numero: str | None, nome: str | None = None) -> str:
    """«Meio» quando ela deu nome; «Entrada 3» quando não deu.

    ``numero`` pode ser o número do mapa (``"3"``, ``"15a"``) ou o rótulo de
    reserva de uma porta sem número (``"4.1.4"``, ``"1-4"``).
    """
    vale = nome_que_vale(numero, nome)
    if vale:
        return vale
    return f"{PALAVRA_DA_ENTRADA} {numero}" if numero else ""


def na_frase(numero: str | None, nome: str | None = None) -> str:
    """O sintagma sem artigo, para o meio da frase: «entrada Meio» ou «Entrada 3»."""
    vale = nome_que_vale(numero, nome)
    if vale:
        return f"{PALAVRA_NA_FRASE} {vale}"
    return rotulo(numero)


def na_frase_do_rotulo(rotulo_pronto: str) -> str:
    """O sintagma de um rótulo que já veio pronto do dono (``nome_da_porta``).

    Para quem recebe o rótulo e não o número: o governador pergunta o nome do
    adaptador pela porta e compõe a frase da recusa. «Entrada 3» (a reserva)
    fica como está; o nome que ela deu ganha a palavra na frente: «entrada
    Meio». Vazio fica vazio.
    """
    limpo = _aparado(rotulo_pronto)
    if not limpo or limpo.startswith(f"{PALAVRA_DA_ENTRADA} "):
        return limpo
    return f"{PALAVRA_NA_FRASE} {limpo}"


def com_artigo(
    frase: str, *, em: bool = False, de: bool = False, maiuscula: bool = False
) -> str:
    """«a Entrada 3», «na entrada Meio», «da Entrada 3» — sempre feminino.

    ``em`` contrai em «na»; ``de``, em «da». ``maiuscula`` é o começo de frase:
    «A Entrada 3 já tem…».
    """
    if em and de:
        raise ValueError("o artigo contrai com «em» ou com «de», não com os dois")
    artigo = "na" if em else ("da" if de else "a")
    if maiuscula:
        artigo = artigo[:1].upper() + artigo[1:]
    return f"{artigo} {frase}" if frase else ""


def titulo_do_hub(numero: str, nome: str | None = None) -> str:
    """O cabeçalho da face de um hub: «Hub na Entrada 3», «Hub na entrada Meio».

    D-2609-O-HUB-PENDE-DA-ENTRADA: a face diz de qual entrada ela pende. A
    CHAVE da face no disco continua :data:`FACE_DO_HUB_DECLARADO`, pelo
    número; o título é o que a tela escreve, com o nome dela.
    """
    return f"Hub {com_artigo(na_frase(numero, nome), em=True)}"


def frase_do_hub_lido(numero: str, nome: str | None = None) -> str:
    """A divergência, sem culpa: «O computador lê este hub na Entrada 5.»"""
    return f"O computador lê este hub {com_artigo(na_frase(numero, nome), em=True)}."


__all__ = [
    "FACE_DO_HUB_DECLARADO",
    "FRASE_DO_NOME_COMPRIDO",
    "MAXIMO_DO_NOME_DA_ENTRADA",
    "PALAVRA_DA_ENTRADA",
    "PALAVRA_NA_FRASE",
    "com_artigo",
    "frase_do_hub_lido",
    "na_frase",
    "na_frase_do_rotulo",
    "nome_que_vale",
    "rotulo",
    "titulo_do_hub",
]
