"""A FOLHA DE USUÁRIO DA CASA — o CSS que o produto põe por cima das dez abas."""
# ruff: noqa: E501  (o CSS do piso é regra em f-string: uma regra por linha é o que o diff lê)

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


#: O PISO DOS ALVOS E DA LETRA (20/10/2026, OS-ALVOS-E-A-LETRA-CRESCEM-E-A-INTERFACE-GANHA-TAMANHO-01).
#: O usuário decidiu em 13/10: todo alvo com no mínimo 24 px (o piso do WCAG 2.2, critério 2.5.8) e nenhuma
#: letra abaixo de 12 px. Em 20/10 escolheu o arranjo A na Controles e na Sistema: tudo onde está,
#: só maior, com o respiro apertado. Os dois números moram AQUI, e a régua
#: (`tests/unit/test_os_alvos_e_a_letra_crescem.py`) mede contra eles.
ALVO_MINIMO_PX = 24
LETRA_MINIMA_PX = 12

_A = ALVO_MINIMO_PX
_L = LETRA_MINIMA_PX

#: O CSS do piso, por página: o gerador da aba o põe na cabeça (`com_o_piso`), e a página publicada
#: o leva ao produto. Uma folha só, nesta casa; nenhuma aba escreve a regra do piso por conta própria.
PISO_POR_PAGINA: dict[str, str] = {
    "02-controles": f"""
/* o piso: alvo de {_A} px e letra de {_L} px; só os tamanhos sobem e o respiro aperta onde precisa */
body.por-controle .pt{{font-size:{_L}px !important}}
body.por-controle .faixa,body.por-controle .faixa .div,body.por-controle .faixa .leia,body.por-controle .bat,body.por-controle .bat .n{{font-size:{_L}px !important}}
body.por-controle .faixa>span{{line-height:16px !important}}
body.por-controle .sensores-peca .sw,body.por-controle .moldura.touchp .todo-sw-toque{{height:{_A}px !important;font-size:{_L}px !important}}
body.por-controle .moldura.touchp .todo-sw-toque .t-lig,body.por-controle .moldura.touchp .todo-sw-toque .t-des{{font-size:{_L}px !important}}
body.por-controle .rot,body.por-controle .rot-vol,body.por-controle .vol .n,body.por-controle .de-quem,body.por-controle .xy,body.por-controle .stick-rot,body.por-controle .gat-linha,body.por-controle .gat-linha .n,body.por-controle .eixo{{font-size:{_L}px !important}}
body.por-controle .selo-ativo,body.por-controle .rot .selo-som,body.por-controle .selo-palavra{{font-size:{_L}px !important}}
body.por-controle .vol,body.por-controle .puxa-vol,body.por-controle .puxa-vol::-webkit-slider-runnable-track,body.por-controle .puxa-vol::-webkit-slider-thumb{{height:{_A}px !important}}
body.por-controle .mudo-i{{width:{_A}px !important;height:{_A}px !important;flex:0 0 {_A}px !important;font-size:14px !important;line-height:22px !important}}
body.por-controle .padrao-i{{height:{_A}px !important;font-size:{_L}px !important;line-height:22px !important}}
body.por-controle .rota button,body.por-controle .rota.trio button{{height:{_A}px !important;min-height:{_A}px !important;font-size:{_L}px !important}}
body.por-controle .quadro-titulo{{min-height:{_A}px !important;display:inline-flex !important;align-items:center !important}}
body.por-controle .moldura,body.por-controle .card-corpo>div:last-child>.moldura.leituras{{padding:4px 10px 5px !important}}
body.por-controle .rot{{margin-bottom:3px !important}}
body.por-controle .rota,body.por-controle .rota.trio{{gap:2px !important;margin-top:3px !important}}
body.por-controle .card-corpo{{padding-top:8px !important}}
body.por-controle .ctl:has(> input:checked),body.por-controle:has(#c-todos:checked) .ctl{{padding-bottom:8px !important}}
body.por-controle .gb svg text{{font-size:10.2px}}
body.por-controle .gat-linha .n{{top:-15px !important;line-height:14px !important}}
/* a vaga: «Player 3 • Desconectado», sem cor, máscara, microfone, sensores nem bateria */
body.por-controle .ctl.off,body.por-controle .ctl.off:has(> input:checked),body.por-controle:has(#c-todos:checked) .ctl.off{{height:26px !important;padding-bottom:0 !important}}
body.por-controle .ctl.off > .faixa{{height:{_A}px !important;display:flex !important;align-items:center !important;font-size:{_L}px !important}}
/* a dica também é alvo: o rótulo que só abre dica chega a {_A} px, pago pela margem de baixo dele */
body.por-controle .rot[data-dica]{{min-height:{_A}px !important;display:flex !important;align-items:center !important;margin-bottom:0 !important}}
""",
    "09-sistema": f"""
/* o piso: Copiar, Salvar e o que abre dica em {_A} px, nenhuma letra abaixo de {_L} px; o respiro entre os grupos aperta */
body .selo,body .selo .sg{{font-size:{_L}px !important}}
body .saude .selo{{flex:0 0 84px !important}}
body .pt{{font-size:{_L}px !important}}
body .sec-rot .btn.copiar{{height:{_A}px !important;font-size:{_L}px !important}}
body .sec-rot.sr-log{{height:35px !important}}
body .log{{font-size:{_L}px !important}}
/* a dica também é alvo: as linhas do Status e os títulos que só abrem dica chegam a {_A} px; paga a margem embaixo do título e entre os grupos */
body .saude .txt{{min-height:{_A}px !important}}
body .sec-rot{{height:{_A}px !important;margin-bottom:2px !important}}
body .sec-rot>span{{min-height:{_A}px !important}}
body .quadro-titulo{{min-height:{_A}px !important;display:inline-flex !important;align-items:center !important}}
body .sec-grupo,body .sec-alta{{margin-top:10px !important;padding-top:8px !important}}
""",
}

ID_DA_FOLHA_DO_PISO = "piso-dos-alvos"


def com_o_piso(aba: str, doc: str) -> str:
    """O documento com a folha do piso da `aba` (nome da página, sem `.html`) na cabeça, antes do `</head>`.

    Página sem piso declarado volta como veio. Chamar duas vezes não repete a folha.
    """
    folha = PISO_POR_PAGINA.get(aba)
    marca = f'<style id="{ID_DA_FOLHA_DO_PISO}">'
    if folha is None or marca in doc:
        return doc
    if doc.count("</head>") != 1:
        raise ValueError(f"{aba}: a cabeça da página não é uma só; o piso não tem onde pousar")
    return doc.replace("</head>", f"{marca}{folha}</style>\n</head>", 1)
