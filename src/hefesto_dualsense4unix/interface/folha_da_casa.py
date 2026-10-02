"""A FOLHA DE USUÁRIO DA CASA — o CSS que o produto põe por cima das dez abas."""

from __future__ import annotations

import re

#: (``daemon.reload``, medido em 01/09) e nenhuma das dez abas tinha estado "em
#: ``.hef-sem-item`` É O BLOCO DO DESENHO QUE HOJE NÃO TEM ITEM — 19/09/2026,
#:
CLASSE_DA_ESPERA = "hef-esperando"

FOLHA_DA_CASA = (
    ".nota{display:none !important}"
    ".hef-sem-item{display:none !important}"
    "select{appearance:none;-webkit-appearance:none}"
    ".hef-em-voo{opacity:.6 !important;cursor:progress !important}"
    ".hef-deu-certo{border-color:var(--green,#50fa7b) !important;"
    "outline:1px solid var(--green,#50fa7b) !important}"
    ".hef-recusou{border-color:var(--orange,#ffb86c) !important;"
    "outline:1px solid var(--orange,#ffb86c) !important}"
    ".hef-esperando div.miolo,.hef-esperando .fita,.hef-esperando .conectado,"
    ".hef-esperando .perfil-ativo{opacity:0 !important}"
)


_REGRA = re.compile(r"([^{}]+)\{([^{}]*)\}")

_SIMPLES = re.compile(r"^[.#]?[A-Za-z][A-Za-z0-9_-]*$")


def seletores_escondidos(folha: str | None = None) -> tuple[str, ...]:
    """Os seletores que esta folha APAGA da tela (`display:none`)."""
    achados: list[str] = []
    for regra in _REGRA.finditer(FOLHA_DA_CASA if folha is None else folha):
        esconde = False
        for declaracao in regra.group(2).split(";"):
            prop, _, valor = declaracao.partition(":")
            if prop.strip().lower() != "display":
                continue
            if valor.replace("!important", "").strip().lower() == "none":
                esconde = True
        if not esconde:
            continue
        for seletor in regra.group(1).split(","):
            limpo = seletor.strip()
            if limpo:
                achados.append(limpo)
    desconhecidos = [s for s in achados if not _SIMPLES.match(s)]
    if desconhecidos:
        raise ValueError(
            "a FOLHA_DA_CASA esconde "
            + ", ".join(repr(s) for s in desconhecidos)
            + " e quem lê esta lista só sabe honrar `.classe`, `#id` e `tag`. "
            "ENSINE A RÉGUA antes de publicar a regra: "
            "`interface/frases_que_ela_baniu.texto_visivel_no_produto` conta "
            "como VISÍVEL tudo o que não souber esconder, e foi assim que o "
            "`--palavra mesa --publicado` acusou 34 ocorrências que o produto "
            "nunca mostrou."
        )
    return tuple(achados)
