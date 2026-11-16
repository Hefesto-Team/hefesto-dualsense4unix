#!/usr/bin/env python3
"""Gera o desenho da janela «Configurar · Modo imersão» (`mockup/janela-do-modo-imersao.html`).

A janela é a da 07, montada pelo mesmo `desenho_da_experimental.modificacao_miolo_html` que o
produto usa, do manifesto e da página do Estúdio da extensão (a cópia em `mockup/modo-imersao/`),
com uma mesa de exemplo de quatro controles. Nada da janela é HTML à mão.

    janela_do_imersao.py                 # gera do manifesto guardado
    janela_do_imersao.py --de <pasta>    # copia antes o manifesto e o Estúdio da extensão
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import desenho_da_experimental as exp
import onde

cv = exp.cv

NOME = "janela-do-modo-imersao.html"
ID_DO_MOD = "imersao"
DADOS = onde.RAIZ / "mockup" / "modo-imersao"
MANIFESTO = DADOS / "hefesto-mod.json"
ESTUDIO = DADOS / "estudio.html"
DO_ESTUDIO_NA_EXTENSAO = "estudio/pagina/estudio.html"

PLASTICOS = ("Starlight Blue", "Cosmic Red", "White", "Galactic Purple")
PRESENTES = (
    "coracao", "alivio", "golpe_com_lado", "lado_na_luz", "luz_do_dano",  # (noqa-acento)
    "cor_do_dano", "impacto_nos_gatilhos", "clima", "susto_no_alto_falante", "susto_no_tato",
    "intervalo_do_susto", "duracao_do_susto", "volume_do_susto", "forca_do_susto",
    "tipo_do_coracao", "tipo_do_alivio", "tipo_do_golpe", "tipo_do_susto", "tipo_do_l2",
    "tipo_do_r2", "canal.mira")
CLIMA = (2, 2, 3, 3, 4, 4, 5, 5, 6, 7, 7, 6, 6, 7, 8, 8, 7, 6, 6, 7)

GRAFO = {"tipo": "grafo", "erros": [], "nos": [
    {"id": "som", "nome": "Som do jogo", "tipo": "entrada", "coluna": 0},
    {"id": "vibracao", "nome": "Vibração do jogo", "tipo": "entrada", "coluna": 0},
    {"id": "microfone", "nome": "Microfone", "tipo": "entrada", "coluna": 0},
    {"id": "parado", "nome": "Controle parado", "tipo": "entrada", "coluna": 0},
    {"id": "tensao", "nome": "Tensão", "tipo": "derivado", "coluna": 1},  # (noqa-acento)
    {"id": "estalo", "nome": "Estalo com lado", "tipo": "derivado", "coluna": 1},
    {"id": "dano", "nome": "Dano", "tipo": "derivado", "coluna": 1},
    {"id": "coracao", "nome": "coração", "tipo": "regra", "coluna": 2},  # (noqa-acento)
    {"id": "alivio", "nome": "alívio", "tipo": "regra", "coluna": 2},
    {"id": "susto", "nome": "susto", "tipo": "regra", "coluna": 2},
    {"id": "golpe", "nome": "golpe com lado", "tipo": "regra", "coluna": 2},
    {"id": "luz", "nome": "luz do dano", "tipo": "regra", "coluna": 2},
    {"id": "tato", "nome": "Vibração fina", "tipo": "saida", "coluna": 3},
    {"id": "motores", "nome": "Motores", "tipo": "saida", "coluna": 3},
    {"id": "falante", "nome": "Alto-falante", "tipo": "saida", "coluna": 3},
    {"id": "barra", "nome": "Barra de luz", "tipo": "saida", "coluna": 3},
    {"id": "gatilhos", "nome": "Gatilhos", "tipo": "saida", "coluna": 3},
], "arestas": [
    ["som", "estalo"], ["som", "tensao"], ["microfone", "tensao"],  # (noqa-acento)
    ["parado", "tensao"], ["vibracao", "dano"], ["vibracao", "estalo"],  # (noqa-acento)
    ["tensao", "coracao"], ["tensao", "alivio"], ["tensao", "susto"],  # (noqa-acento)
    ["estalo", "golpe"], ["dano", "luz"], ["dano", "golpe"],
    ["coracao", "tato"], ["alivio", "tato"], ["susto", "tato"],  # (noqa-acento)
    ["susto", "falante"], ["golpe", "motores"], ["golpe", "gatilhos"], ["luz", "barra"],
]}


def copiar_da_extensao(pasta: pathlib.Path) -> None:
    """Guarda em `mockup/modo-imersao/` o manifesto e o Estúdio da extensão em `pasta`. O `aviso`
    fica fora da cópia: ele é o texto do «sim» da instalação, e a janela não o desenha."""
    DADOS.mkdir(parents=True, exist_ok=True)
    dados = json.loads((pasta / "hefesto-mod.json").read_text(encoding="utf-8"))
    dados.pop("aviso", None)
    MANIFESTO.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(pasta / DO_ESTUDIO_NA_EXTENSAO, ESTUDIO)


def manifesto() -> Any:
    from hefesto_dualsense4unix.mods.manifesto import Manifesto

    return Manifesto.model_validate(json.loads(MANIFESTO.read_text(encoding="utf-8")))


def mesa(n: int = 4) -> dict[str, Any]:
    """O estado de exemplo: a extensão ligada, com `n` controles e escritas de agora há pouco."""
    aparelhos = [{"id": f"jogador-{j}", "nome": PLASTICOS[j - 1], "ligado": j != 3,
                  "estado": "ligado", "controles": [
                      {"id": ident, "tipo": "escolha", "rotulo": rotulo, "dica": dica,
                       "valor": "100" if ident == "forca" else "75",
                       "opcoes": [{"id": str(v), "rotulo": f"{v}%"}  # (noqa-acento)
                                  for v in (0, 25, 50, 75, 100)]}
                      for ident, rotulo, dica in (
                          ("forca", "Força", "A força de tudo o que este controle sente"),
                          ("volume", "Volume", "O volume do alto-falante deste controle"))]}
                 for j in range(1, n + 1)]
    return {"mod": ID_DO_MOD, "ligado": True, "nivel": 7, "limiar": 6, "perfil": "Universal",
            "aparelhos": aparelhos, "conexoes": [], "presentes": list(PRESENTES),  # (noqa-acento)
            "linhas": [{"rotulo": "Estilo", "valor": "Terror"},
                       {"rotulo": "Lendo", "valor": "Som, vibração, microfone"}],
            "ao_vivo": {
                "controles": [{"jogador": j, "cor": PLASTICOS[j - 1]} for j in range(1, n + 1)],
                "escritas": [{"canal": "haptica", "controle": 0, "ha_ms": 200},
                             {"canal": "gatilho", "controle": 0, "ha_ms": 600},
                             {"canal": "luz", "controle": 1, "ha_ms": 300}]}}


def opcoes_da_janela(m: Any, estado: dict[str, Any]) -> list[exp.OpcaoDaJanela]:
    """As linhas do manifesto com o valor padrão, como o produto as monta."""
    from hefesto_dualsense4unix.mods import opcoes

    valores = {o.id: opcoes.padrao_de(o) for o in m.opcoes}
    valores = {k: int(v) if isinstance(v, float) and v == int(v) else v for k, v in valores.items()}
    aparecem = opcoes.aparecem(m, valores, estado.get("presentes"))
    return [exp.OpcaoDaJanela(
        mod=ID_DO_MOD, id=o.id, rotulo=o.rotulo, tipo=o.tipo, valor=valores[o.id],
        escolhas=opcoes.escolhas_de(m, o, valores), grupo=o.grupo or "", minimo=o.minimo or 0,
        maximo=o.maximo or 0, passo=o.passo or 1, dica=o.dica or "", unidade=o.unidade or "",
        zero=o.zero or "", degraus=o.degraus or 0, cartao=o.cartao or "", canal=o.canal or "")
        for o in m.opcoes if o.id in aparecem]


def miolo(aba: str = "", controles: int = 4) -> str:
    """O miolo da janela, aberto em `aba`, com `controles` controles na mesa."""
    m = manifesto()
    estado = mesa(controles)
    acoes = tuple(exp.AcaoDaJanela(a.id, a.rotulo, a.grupo or "", a.icone or "")
                  for a in m.acoes)
    geridos = m.aparelhos_acoes
    aparelhos = exp.AparelhosDaJanela(
        tuple(exp.AcaoDaJanela(a.id, a.rotulo, a.grupo or "", a.icone or "")
              for a in geridos.acoes), geridos.grupo or "") if geridos else None
    pagina = None
    if m.pagina is not None:
        estudio = ESTUDIO.read_text(encoding="utf-8").replace(
            "</body>", f"<script>receber({json.dumps(GRAFO, ensure_ascii=False)});</script>"
            "</body>", 1)
        pagina = exp.PaginaDaJanela(estudio, m.pagina.rotulo, m.pagina.altura_max)
    html: str = exp.modificacao_miolo_html(
        m.nome, opcoes_da_janela(m, estado), mod=ID_DO_MOD, agora=tuple(m.agora), estado=estado,
        parar_tudo=m.parar_tudo, aba=aba, acoes=acoes, aparelhos=aparelhos,
        controles=str(m.aparelhos_controles.grupo) if m.aparelhos_controles else "",
        pagina=pagina, vivo=cv.vivo_de(estado, 0, CLIMA), abas=tuple(m.abas))
    return html


def pagina(aba: str = "", controles: int = 4) -> str:
    """A 07 do desenho com a janela do Modo imersão aberta."""
    base = onde.pagina("07-lancadores.html").read_text(encoding="utf-8")
    velha = exp.janela_da_extensao(exp.miolo_do_desenho_da_extensao())
    if base.count(velha) != 1:
        raise SystemExit("ERRO: a janela de exemplo não está uma vez na 07 do desenho; rode o "
                         "aba07.py antes")
    doc = base.replace(velha, exp.janela_da_extensao(miolo(aba, controles)), 1)
    inicio = doc.index(f'<div class="tela-nova" id="{exp.JANELAS[0]}">')
    fim = doc.index('<div class="tela-nova" id="modificacao">')
    if any(f'id="{j}"' not in doc[inicio:fim] for j in exp.JANELAS[:-1]):
        raise SystemExit("ERRO: as outras janelas da 07 mudaram de ordem; a janela da extensão "
                         "tem de ser a última")
    aberta = "<style>.tela-nova#modificacao{display:flex}</style>\n</head>"
    doc = re.sub(r"<title>[^<]*</title>", "<title>Hefesto — a janela do Modo imersão</title>",
                 doc[:inicio] + doc[fim:], count=1)
    return doc.replace("</head>", aberta, 1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--de", type=pathlib.Path, help="a pasta da extensão Modo imersão")
    args = ap.parse_args(argv)
    if args.de:
        copiar_da_extensao(args.de)
    onde.gravar(NOME, pagina())
    print(f"{NOME}: OK, do manifesto {manifesto().versao} da extensão")
    return 0


if __name__ == "__main__":
    sys.exit(main())
