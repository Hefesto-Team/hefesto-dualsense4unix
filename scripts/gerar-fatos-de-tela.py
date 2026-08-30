#!/usr/bin/env python3
"""gerar-fatos-de-tela.py — o CSV vira Python que viaja no pacote.

Executa Z6-02 (docs/process/sprints/2026-08-24-ONDA0-Z6-COMUNHAO-COM-O-SPECS-01…
.md), a Peça 1 do contrato desenhado na PAREAMENTO-01.

POR QUE GERADO, E NÃO LIDO EM RUNTIME
--------------------------------------
`docs/data/mapa-controles.csv` **não viaja no pacote** — medido em 24/08/2026:
`pyproject.toml:83` só empacota `src/hefesto_dualsense4unix`, e nenhum dos
scripts de empacotamento (`packaging/`, `flatpak/`, `scripts/build_*.sh`)
carrega `docs/data/`. Uma GUI que lesse o CSV em runtime funcionaria na máquina
de quem desenvolve e quebraria na de quem instalou. Por isso o CSV é convertido
para Python **em build time**, e o módulo gerado é commitado e viaja com o
pacote — o mesmo desenho de `scripts/gerar-mapa.py` para o `specs.html`.

O `--check` PERGUNTA PELO CONTEÚDO, NÃO PELO RELÓGIO
------------------------------------------------------
A mesma disciplina de `gerar-mapa.py`: regenera em memória e compara **texto**
com o arquivo em disco, nunca `mtime`. A MAPA-CONTEÚDO-01 (12/08/2026) já pagou
duas vezes por comparar relógio.

A FRONTEIRA QUE SALVA A PROPOSTA
---------------------------------
A PAREAMENTO-01 desenha a fronteira DERIVA x NAO DERIVA: colunas de fato
(domínio fechado, régua executável) viram Python; prosa de bancada (`rotulo`,
`*_detalhe`, `*_ressalva`, `nota`, `estado_hoje`, `*_feature_v1`, `*_evidencia`)
NUNCA vira frase de tela por geração automática — isso seria pôr palavra na
boca dela. `checar_fronteira()` é o guarda mecânico: se uma coluna de prosa
entrar na allowlist de emissão, ele reprova.

Uso:
    python3 scripts/gerar-fatos-de-tela.py            # escreve o módulo gerado
    python3 scripts/gerar-fatos-de-tela.py --check    # o publicado bate com o CSV?
"""
from __future__ import annotations

import argparse
import csv
import difflib
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.append(str(Path(__file__).resolve().parent))

# Vocabulário com um dono só (Z6-01): nada aqui redigita valor de domínio — os
# três nomes vêm do portão que já é dono deles, exatamente como
# `scripts/gerar-mapa.py` já faz para a legenda da ESCADA no `specs.html`.
from check_paridade_transporte import (  # noqa: E402
    DOMINIO_EXISTE,
    DOMINIO_POR_SUFIXO,
    LADOS,
    pares_de_transporte,
)

CSV_RELATIVO = "docs/data/mapa-controles.csv"
SAIDA_RELATIVO = "src/hefesto_dualsense4unix/app/fatos_do_mapa.py"
CSV_CAMINHO = RAIZ / CSV_RELATIVO
SAIDA_CAMINHO = RAIZ / SAIDA_RELATIVO

#: As colunas de FATO que o gerador emite — o lado DERIVA da fronteira da
#: PAREAMENTO-01. Cada sufixo aqui tem domínio fechado em `DOMINIO_POR_SUFIXO`
#: (ou é `existe`, com domínio próprio em `DOMINIO_EXISTE`).
COLUNAS_DERIVAVEIS: frozenset[str] = frozenset(
    {"aceita", "aciona", "de_onde_sei", "ate_onde_foi", "por_que_nao_aciona", "canal"}
)

#: As colunas de PROSA — o lado NÃO DERIVA. Escritas para quem depura rádio,
#: não para quem joga; virar dica de tela por geração automática é o erro que
#: a PAREAMENTO-01 manda evitar (o precedente é "alto-falante" → "placa de
#: som", que ela derrubou em 15/08/2026). Esta lista não precisa ser
#: exaustiva — só precisa cobrir o que `checar_fronteira` tem de recusar.
COLUNAS_PROSA: frozenset[str] = frozenset(
    {
        "rotulo",
        "detalhe",
        "ressalva",
        "nota",
        "estado_hoje",
        "feature_v1",
        "evidencia",
        "offset",
        "report_id",
        "comando",
        "codigo_ref",
        "mordida",
        "mordida_provada_em",
        "provado_em",
        "provado_por",
        # 29/08/2026, pedido dela: "se tal informação veio do git, qual repo
        # e se eu e vc validamos na mesa". A fonte externa é PROSA DE
        # BANCADA — ela diz de onde veio a pista, não o que a tela fala.
        "fonte_externa",
        "validade_dias",
        "assimetria_declarada",
        "id_v1",
    }
)


def checar_fronteira(colunas_permitidas: frozenset[str]) -> None:
    """Reprova se uma coluna de PROSA entrar na allowlist de emissão.

    É o guarda mecânico da fronteira DERIVA x NAO DERIVA (PAREAMENTO-01, "A
    FRONTEIRA QUE SALVA A PROPOSTA"). Sem ele, a proposta escorrega em três
    levas para "gerar a voz dela a partir de célula" — que já foi tentado e
    derrubado por ela uma vez.
    """
    intrusas = colunas_permitidas & COLUNAS_PROSA
    if intrusas:
        raise ValueError(
            "checar_fronteira: coluna(s) de PROSA na allowlist de emissão do "
            f"gerador de fatos de tela: {sorted(intrusas)}. Prosa de bancada "
            "não vira frase de tela por geração automática — ver PAREAMENTO-01, "
            "'A FRONTEIRA QUE SALVA A PROPOSTA'."
        )


def le_csv() -> list[dict[str, str]]:
    with CSV_CAMINHO.open(encoding="utf-8", newline="") as arquivo:
        return list(csv.DictReader(arquivo))


def _valor(linha: dict[str, str], coluna: str) -> str:
    return (linha.get(coluna) or "").strip()


def monta_fatos(linhas: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    """O dicionário `FATOS`, na forma que o módulo gerado publica.

    Cada `id` vira uma entrada com `existe` e um sub-dicionário por lado
    (`cabo`, `radio`), só com as colunas DERIVÁVEIS. `pares_de_transporte` é o
    mesmo leitor por sufixo que `check_paridade_transporte.py` usa — nunca uma
    lista de colunas escrita à mão aqui.
    """
    if not linhas:
        return {}
    checar_fronteira(COLUNAS_DERIVAVEIS)
    cabecalho = list(linhas[0].keys())
    pares = pares_de_transporte(cabecalho)
    sufixos_a_emitir = sorted(set(pares) & COLUNAS_DERIVAVEIS)

    fatos: dict[str, dict[str, object]] = {}
    for linha in linhas:
        identificador = _valor(linha, "id")
        if not identificador:
            continue
        existe = _valor(linha, "existe")
        if existe not in DOMINIO_EXISTE:
            raise ValueError(
                f"gerar-fatos-de-tela: {identificador!r} tem `existe={existe!r}`, "
                f"fora do domínio {sorted(DOMINIO_EXISTE)} — o vocabulário tem um "
                "dono só (check_paridade_transporte.DOMINIO_EXISTE) e este "
                "gerador não redigita valor."
            )
        entrada: dict[str, object] = {"existe": existe}
        for lado in LADOS:
            lado_dict: dict[str, str] = {}
            for sufixo in sufixos_a_emitir:
                coluna_cabo, coluna_radio = pares[sufixo]
                coluna = coluna_cabo if lado == LADOS[0] else coluna_radio
                valor = _valor(linha, coluna)
                dominio = DOMINIO_POR_SUFIXO.get(sufixo)
                if dominio is not None and valor not in dominio:
                    raise ValueError(
                        f"gerar-fatos-de-tela: {identificador!r}[{lado}] tem "
                        f"`{coluna}={valor!r}`, fora do domínio {sorted(dominio)}."
                    )
                lado_dict[sufixo] = valor
            entrada[lado] = lado_dict
        fatos[identificador] = entrada
    return fatos


def _repr_dict_ordenado(d: dict[str, object], indentacao: str) -> list[str]:
    linhas_saida: list[str] = []
    prox = indentacao + "    "
    for chave in sorted(d):
        valor = d[chave]
        if isinstance(valor, dict):
            linhas_saida.append(f"{prox}{chave!r}: {{")
            for sub_chave in sorted(valor):
                linhas_saida.append(f"{prox}    {sub_chave!r}: {valor[sub_chave]!r},")
            linhas_saida.append(f"{prox}}},")
        else:
            linhas_saida.append(f"{prox}{chave!r}: {valor!r},")
    return linhas_saida


def monta() -> str:
    linhas = le_csv()
    fatos = monta_fatos(linhas)

    corpo = ["FATOS: Final[dict[str, dict[str, object]]] = {"]
    for identificador in sorted(fatos):
        corpo.append(f"    {identificador!r}: {{")
        entrada = fatos[identificador]
        corpo.append(f"        'existe': {entrada['existe']!r},")
        for lado in LADOS:
            lado_dict = entrada[lado]
            assert isinstance(lado_dict, dict)
            corpo.append(f"        {lado!r}: {{")
            for sufixo in sorted(lado_dict):
                corpo.append(f"            {sufixo!r}: {lado_dict[sufixo]!r},")
            corpo.append("        },")
        corpo.append("    },")
    corpo.append("}")

    cabecalho = f'''"""fatos_do_mapa.py — GERADO por scripts/gerar-fatos-de-tela.py.
NÃO EDITE À MÃO.

Fonte: {CSV_RELATIVO}. Regenerar: python3 scripts/gerar-fatos-de-tela.py

Só as colunas DERIVÁVEIS entram aqui (existe, aceita, aciona, de_onde_sei,
ate_onde_foi, por_que_nao_aciona, canal) — a fronteira DERIVA x NAO DERIVA da
PAREAMENTO-01. Prosa de bancada (rotulo, *_detalhe, *_ressalva, nota,
estado_hoje, *_feature_v1, *_evidencia) fica no CSV, de propósito: NAO vira
frase de tela por geração automática.

`FATOS[id]["existe"]` e `FATOS[id][lado][sufixo]` são as únicas leituras
suportadas. `id` é `chave@controle` (o endereço estável do mapa, coluna `id`
do CSV — nunca `chave` sozinha).
"""
from __future__ import annotations

from typing import Final

'''
    return cabecalho + "\n".join(corpo) + "\n"


def normaliza(texto: str) -> list[str]:
    return [linha.rstrip() for linha in texto.split("\n")]


def divergencias(publicado: str, regerado: str) -> list[str]:
    return list(
        difflib.unified_diff(
            normaliza(publicado),
            normaliza(regerado),
            fromfile="fatos_do_mapa.py publicado",
            tofile="o que o CSV produz hoje",
            lineterm="",
            n=0,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="reprova se fatos_do_mapa.py não for o que o CSV produz",
    )
    args = parser.parse_args(argv)

    regerado = monta()

    if args.check:
        if not SAIDA_CAMINHO.exists():
            print(
                f"{SAIDA_RELATIVO}: NAO EXISTE — rode "
                "scripts/gerar-fatos-de-tela.py",
                file=sys.stderr,
            )
            return 1
        publicado = SAIDA_CAMINHO.read_text(encoding="utf-8")
        difs = divergencias(publicado, regerado)
        if difs:
            print(
                f"{SAIDA_RELATIVO}: DESATUALIZADO — não é o que "
                f"{CSV_RELATIVO} produz",
                file=sys.stderr,
            )
            for linha in difs[:80]:
                print(f"  {linha}", file=sys.stderr)
            if len(difs) > 80:
                print(f"  … e mais {len(difs) - 80} linha(s)", file=sys.stderr)
            print("rode: python3 scripts/gerar-fatos-de-tela.py", file=sys.stderr)
            return 1
        print(f"{SAIDA_RELATIVO}: atualizado (confere com {CSV_RELATIVO})")
        return 0

    SAIDA_CAMINHO.write_text(regerado, encoding="utf-8")
    print(f"{SAIDA_RELATIVO}: escrito ({len(monta_fatos(le_csv()))} chaves)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
