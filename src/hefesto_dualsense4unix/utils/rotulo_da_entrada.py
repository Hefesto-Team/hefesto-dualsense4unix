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
como nome. Um nome igual ao número, ou igual a «Entrada N», é tratado como
ausente (:func:`nome_que_vale`) — senão a tela diria «Entrada: 2».
"""

from __future__ import annotations

#: A palavra do produto para o buraco no gabinete (``D-A-PALAVRA-ENTRADA``). É o
#: nome da entrada quando ela não deu outro: «Entrada 3». Ela morava no
#: ``entrada_a_entrada`` até 26/09/2026, que a reexporta.
PALAVRA_DA_ENTRADA = "Entrada"

#: A palavra no meio da frase, antes do nome que ela deu: «a entrada Meio».
_PALAVRA_NA_FRASE = PALAVRA_DA_ENTRADA.lower()

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


def _aparado(texto: str | None) -> str:
    return " ".join(str(texto or "").split())


def nome_que_vale(numero: str | None, nome: str | None) -> str | None:
    """O nome dela, ou ``None`` quando ele não é nome.

    Vazio não é nome; o próprio número («2») não é nome; «Entrada 2» não é
    nome. Os três são o rótulo de reserva escrito por extenso, e tratá-los como
    nome faria a tela dizer «Entrada: 2» e «O 13».
    """
    limpo = _aparado(nome)
    if not limpo:
        return None
    numero_limpo = _aparado(numero)
    if numero_limpo:
        dobrado = limpo.casefold()
        if dobrado in (numero_limpo.casefold(),
                       f"{_PALAVRA_NA_FRASE} {numero_limpo}".casefold()):
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
        return f"{_PALAVRA_NA_FRASE} {vale}"
    return rotulo(numero)


__all__ = [
    "FACE_DO_HUB_DECLARADO",
    "FRASE_DO_NOME_COMPRIDO",
    "MAXIMO_DO_NOME_DA_ENTRADA",
    "PALAVRA_DA_ENTRADA",
    "na_frase",
    "nome_que_vale",
    "rotulo",
]
