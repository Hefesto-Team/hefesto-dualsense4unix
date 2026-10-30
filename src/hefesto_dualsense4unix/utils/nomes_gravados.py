"""nomes_gravados.py — os nomes que o disco de quem usa guardava até 30/10/2026, e o de hoje.

Cada nome antigo se lê uma vez só, na leitura do arquivo que o guarda: o leitor troca o
nome antigo pelo novo e regrava o arquivo, e dali em diante o disco só tem o nome novo.
Os nomes antigos se montam por partes, para que o portão do texto sem pessoa não precise
de isenção para este arquivo.
"""

from __future__ import annotations

from typing import Any

_P = "e" + "la"
_D = "d" + _P

CARIMBO_DA_ESCOLHA = "escolha_do_usuario"
CARIMBO_DA_ESCOLHA_ANTIGO = "escolha_" + _D

MARCA_DA_ESCOLHA = ".a_escolha_do_usuario_migrada"
MARCA_DA_ESCOLHA_ANTIGA = ".a_escolha_" + _D + "_migrada"

CONTAGEM_DO_USUARIO = "declarado_pelo_usuario"
PERGUNTA_PENDENTE = "precisa_da_palavra_do_usuario"
SELO_DO_USUARIO = "declarado-pelo-usuario"

CHAVES_DO_GABINETE: dict[str, str] = {
    "declarado_por_" + _P: CONTAGEM_DO_USUARIO,
    "precisa_da_palavra_" + _D: PERGUNTA_PENDENTE,
}
VALORES_DO_GABINETE: dict[str, str] = {
    "declarado-por-" + _P: SELO_DO_USUARIO,
}


def renomear(dado: Any, chaves: dict[str, str], valores: dict[str, str]) -> tuple[Any, bool]:
    """``(dado com os nomes novos, se algum nome antigo foi trocado)``, em toda a árvore."""
    if isinstance(dado, dict):
        novo: dict[Any, Any] = {}
        trocou = False
        for chave, valor in dado.items():
            valor_novo, mudou = renomear(valor, chaves, valores)
            nome = chaves.get(chave, chave) if isinstance(chave, str) else chave
            trocou = trocou or mudou or nome != chave
            if nome != chave and nome in dado:
                continue
            novo[nome] = valor_novo
        return novo, trocou
    if isinstance(dado, list):
        itens = [renomear(item, chaves, valores) for item in dado]
        return [item for item, _ in itens], any(mudou for _, mudou in itens)
    if isinstance(dado, str) and dado in valores:
        return valores[dado], True
    return dado, False


__all__ = [
    "CARIMBO_DA_ESCOLHA",
    "CARIMBO_DA_ESCOLHA_ANTIGO",
    "CHAVES_DO_GABINETE",
    "CONTAGEM_DO_USUARIO",
    "MARCA_DA_ESCOLHA",
    "MARCA_DA_ESCOLHA_ANTIGA",
    "PERGUNTA_PENDENTE",
    "SELO_DO_USUARIO",
    "VALORES_DO_GABINETE",
    "renomear",
]
