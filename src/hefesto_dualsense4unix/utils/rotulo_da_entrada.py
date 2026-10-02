"""O dono da GRAFIA do nome de uma entrada — «Entrada 3», «Meio», «na Entrada 3»."""

from __future__ import annotations

import re

PALAVRA_DA_ENTRADA = "Entrada"

PALAVRA_NA_FRASE = PALAVRA_DA_ENTRADA.lower()

FACE_DO_HUB_DECLARADO = f"Hub na {PALAVRA_DA_ENTRADA} {{numero}}"

MAXIMO_DO_NOME_DA_ENTRADA = 24

FRASE_DO_NOME_COMPRIDO = f"O nome da entrada tem até {MAXIMO_DO_NOME_DA_ENTRADA} letras."


_SO_O_NUMERO = re.compile(
    rf"^(?:{re.escape(PALAVRA_NA_FRASE)}\s+)?[0-9]{{1,3}}[a-z]?$", re.IGNORECASE)


def _aparado(texto: str | None) -> str:
    return " ".join(str(texto or "").split())


def nome_que_vale(numero: str | None, nome: str | None) -> str | None:
    """O nome dela, ou ``None`` quando ele não é nome."""
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
    """«Meio» quando ela deu nome; «Entrada 3» quando não deu."""
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
    """O sintagma de um rótulo que já veio pronto do dono (``nome_da_porta``)."""
    limpo = _aparado(rotulo_pronto)
    if not limpo or limpo.startswith(f"{PALAVRA_DA_ENTRADA} "):
        return limpo
    return f"{PALAVRA_NA_FRASE} {limpo}"


def com_artigo(
    frase: str, *, em: bool = False, de: bool = False, maiuscula: bool = False
) -> str:
    """«a Entrada 3», «na entrada Meio», «da Entrada 3» — sempre feminino."""
    if em and de:
        raise ValueError("o artigo contrai com «em» ou com «de», não com os dois")
    artigo = "na" if em else ("da" if de else "a")
    if maiuscula:
        artigo = artigo[:1].upper() + artigo[1:]
    return f"{artigo} {frase}" if frase else ""


def titulo_do_hub(numero: str, nome: str | None = None) -> str:
    """O cabeçalho da face de um hub: «Hub na Entrada 3», «Hub na entrada Meio»."""
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
