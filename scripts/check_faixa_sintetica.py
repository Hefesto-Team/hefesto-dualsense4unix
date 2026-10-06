#!/usr/bin/env python3
"""Falha se uma faixa de MAC SINTÉTICA de teste aparecer no `config_dir()` real.

T-06 (ONDA0-Z7 · O AMBIENTE PRESUMIDO 01, 24/08/2026). Medido na bancada
em 23/08/2026: quatro registros com endereços da faixa `aabbcc` vazaram para
`~/.config/hefesto-dualsense4unix/controllers.json` — a mesa de produção dela,
não um fixture — empurrando os quatro DualSense REAIS dela das posições 1-4
para 1, 6, 7 e 8. `grep -rl aabbcc tests/ | wc -l` achou 91 arquivos de teste
usando a faixa; algum deles escreveu no disco do usuário em vez de num diretório
isolado (T-06 também rastreia a CAUSA — ver `docs/process/agentes/` da leva).

As faixas sintéticas da casa (o dono é `core/faixa_sintetica.py`; o
`scripts/check_test_data.sh` repete duas), verificadas nas duas grafias — com
`:` e sem:

  aabbcc  / aa:bb:cc
  02fe00  / 02:fe:00
  e8473a  / e8:47:3a

OS CHAMADORES, e por que são TRÊS lugares diferentes (LUZ-CEGA-01/E8,
25/08/2026 — até aqui este portão não tinha chamador NENHUM: nem CI, nem
gancho, nem lista de portões. Portão que ninguém chama é o defeito
`A-CASA-SABE-E-O-PRODUTO-NÃO-FAZ`):

* ``--arvore`` (o DEFAULT, e o que roda no CI) varre a **árvore versionada**
  atrás dos arquivos que só o ``config_dir()`` deveria ter — um
  ``controllers.json`` commitado é artefato de tempo de execução no lugar
  errado, e se ele trouxer faixa de fixture o defeito atravessou outra porta.
  É determinístico, não depende de ``$HOME`` e por isso vale no CI, onde o
  ``~/.config`` está vazio e a varredura dele seria verde por vacuidade;
* ``--casa`` varre o ``config_dir()`` REAL. **Não REPROVA em lugar nenhum**,
  de propósito: na máquina de quem já tem a poluição gravada ele ficaria
  vermelho todo dia até alguém decidir limpar — e a decisão sobre o que já
  está no disco é de quem é dono da máquina;
* a suíte chama a função :func:`enderecos` no ``tests/conftest.py``
  (FAIXA-NO-BERCO-01): ali a régua é o DELTA — reprova só se apareceu um
  endereço sintético que não estava lá no começo da sessão. Assim ela é verde
  numa máquina já poluída e vermelha no dia em que um teste polui;
* e o CABEÇALHO da suíte (``pytest_report_header``, mesmo ``conftest.py``,
  25/08/2026) RELATA a contagem do ``--casa`` em toda execução. **Esta linha é
  a correção de um fato:** até 25/08 este cabeçalho dizia que o ``--casa`` não
  rodava sozinho em lugar nenhum, e a consequência foi medida — o estado
  PARADO do ``~/.config`` dela não era olhado por instrumento nenhum, e quatro
  endereços forjados moraram na fila dela de 22/08 a 25/08 sem ninguém ver. O
  delta é cego para a sujeira que já estava lá; o relato do cabeçalho não é.

Uso:
    python3 scripts/check_faixa_sintetica.py             # --arvore (default)
    python3 scripts/check_faixa_sintetica.py --casa      # o config_dir() real
    python3 scripts/check_faixa_sintetica.py --config-dir /algum/lugar
    python3 scripts/check_faixa_sintetica.py --arvore --raiz /outra/arvore
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hefesto_dualsense4unix.core.faixa_sintetica import (
    FAIXAS_SINTETICAS,
    e_endereco_sintetico,
)


def _padrao_para(faixa: str) -> re.Pattern[str]:
    """Um regex por faixa, casando as duas grafias, sem diferenciar maiúscula."""
    a, b, c = faixa[0:2], faixa[2:4], faixa[4:6]
    return re.compile(rf"(?i){a}:?{b}:?{c}(?::?[0-9a-f]{{2}}){{0,3}}")


_PADROES = {faixa: _padrao_para(faixa) for faixa in FAIXAS_SINTETICAS}

_EXTENSOES_VARRIDAS = {".json", ".txt", ".log", ".conf", ".ini", ""}


def _vale_varrer(caminho: Path) -> bool:
    """Basta UM sufixo conhecido, em qualquer posição, e não só o último."""
    if not caminho.suffixes:
        return "" in _EXTENSOES_VARRIDAS
    return any(s.lower() in _EXTENSOES_VARRIDAS for s in caminho.suffixes)


def _config_dir() -> Path:
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    return config_dir()


def achados(diretorio: Path) -> list[str]:
    """Varre o diretório e devolve uma linha por ocorrência: arquivo:linha: valor."""
    linhas: list[str] = []
    if not diretorio.is_dir():
        return linhas
    for caminho in sorted(diretorio.rglob("*")):
        if not caminho.is_file():
            continue
        if not _vale_varrer(caminho):
            continue
        try:
            texto = caminho.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for numero, linha_texto in enumerate(texto.splitlines(), start=1):
            for faixa, padrao in _PADROES.items():
                for m in padrao.finditer(linha_texto):
                    linhas.append(
                        f"  {caminho}:{numero}: faixa sintética '{faixa}' -> {m.group(0)!r}"
                    )
    return linhas


def enderecos(diretorio: Path) -> set[str]:
    """``{"<arquivo>::<endereço colado, minúsculo>"}`` — a forma COMPARÁVEL."""
    vistos: set[str] = set()
    for linha in achados(diretorio):
        cabeca, _, cauda = linha.rpartition(" -> ")
        caminho = cabeca.strip().split(":")[0]
        valor = cauda.strip().strip("'\"").replace(":", "").lower()
        vistos.add(f"{caminho}::{valor}")
    return vistos


#: ``app/gui_prefs.py``, ``utils/session.py`` e a aba Sistema.
NOMES_DE_TEMPO_DE_EXECUCAO = (
    "controllers.json",
    "controller_masks.json",
    "maquina.json",
    "gui_preferences.json",
    "session.json",
    "active_profile.txt",
    "steam_input_apps.txt",
)

_ARVORE_IGNORADA = ("tests", "docs", ".git", "captures", "examples")


def achados_na_arvore(raiz: Path) -> list[str]:
    """Artefatos de tempo de execução COMMITADOS que trazem faixa sintética."""
    linhas: list[str] = []
    for nome in NOMES_DE_TEMPO_DE_EXECUCAO:
        for caminho in sorted(raiz.rglob(nome + "*")):
            if not caminho.is_file():
                continue
            if not _vale_varrer(caminho):
                continue
            relativo = caminho.relative_to(raiz)
            if relativo.parts and relativo.parts[0] in _ARVORE_IGNORADA:
                continue
            try:
                texto = caminho.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for numero, linha_texto in enumerate(texto.splitlines(), start=1):
                for faixa, padrao in _PADROES.items():
                    for m in padrao.finditer(linha_texto):
                        linhas.append(
                            f"  {relativo}:{numero}: faixa sintética "
                            f"'{faixa}' -> {m.group(0)!r}"
                        )
    return linhas


def limpar(diretorio: Path) -> list[str]:
    """Tira a faixa sintética da FILA do ``controllers.json`` — gesto explícito.

    **O QUE ISTO CURA, medido na bancada em 18/09/2026:** quatro endereços
    ``aa:bb:cc:00:00:0{1..4}`` moravam na fila de numeração desde 22/08,
    ocupando os postos 4 a 7 e empurrando um DualSense real para o **oitavo**.
    A causa (a suíte escrevendo no ``~/.config`` real) foi fechada em 25/08
    pelo lar de mentira de sessão; o que ficou foi a sujeira, e ninguém a
    limpava. Este portão ACUSAVA desde 24/08 e não tinha como curar — que é o
    defeito `A-CASA-SABE-E-O-PRODUTO-NÃO-FAZ` na sua forma mais pura.

    **POR QUE AQUI, e não dentro do produto.** A primeira cura escrita
    descartava a faixa no ``identity.order_entries``, e foi recuada no mesmo
    dia: duas dezenas de réguas desta casa usam ``aa:bb:cc`` como endereço de
    controle de verdade, e 236 arquivos de teste a citam. Expurgá-la no
    produto é uma regra sobre a NOSSA suíte, não sobre o aparelho. Aqui é o
    lugar certo: um gesto EXPLÍCITO, com dono, que o ``doctor`` chama — e a
    própria mensagem do ``--casa`` já dizia que *"a decisão sobre o que já
    está gravado é de quem é dono da máquina"*.

    Mexe só na FILA (o campo ``order``), e só nas entradas cujo endereço é de
    faixa sintética. Preserva o resto do documento byte a byte — o ``version``,
    o ``boot_id`` e qualquer campo que uma versão futura tenha posto lá.

    Devolve as linhas do relato, vazio quando não havia o que limpar.
    """
    alvo = diretorio / "controllers.json"
    if not alvo.is_file():
        return []
    try:
        dados = json.loads(alvo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(dados, dict) or not isinstance(dados.get("order"), list):
        return []
    antes = dados["order"]
    depois = [
        e
        for e in antes
        if not (isinstance(e, dict) and e_endereco_sintetico(e.get("addr")))
    ]
    if len(depois) == len(antes):
        return []
    tirados = [
        e["addr"] for e in antes if e not in depois and isinstance(e, dict)
    ]
    dados["order"] = depois
    tmp = alvo.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(dados, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(alvo)
    return [f"  tirado da fila: {a}" for a in tirados]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=None,
        help="diretório a varrer (o modo explícito; usado pelos testes)",
    )
    parser.add_argument(
        "--casa",
        action="store_true",
        help="varre o config_dir() REAL desta máquina (opt-in — ver o cabeçalho)",
    )
    parser.add_argument(
        "--arvore",
        action="store_true",
        help="varre a árvore versionada (é o DEFAULT quando nada é pedido)",
    )
    parser.add_argument(
        "--limpar",
        action="store_true",
        help="TIRA a faixa sintética da fila do controllers.json (com --casa)",
    )
    parser.add_argument(
        "--raiz",
        type=Path,
        default=None,
        help="a raiz da árvore a varrer no modo --arvore (padrão: a deste script)",
    )
    args = parser.parse_args(argv)

    if args.config_dir is None and not args.casa:
        raiz = (
            args.raiz.resolve()
            if args.raiz is not None
            else Path(__file__).resolve().parents[1]
        )
        encontrados = achados_na_arvore(raiz)
        if encontrados:
            print(f"FAIL: artefato de tempo de execução versionado em '{raiz}':")
            print("\n".join(encontrados))
            print(
                "  Estes arquivos são do `config_dir()`, não da árvore. Um "
                "deles aqui, com faixa de fixture dentro, é o mesmo vazamento "
                "de T-06 atravessando outra porta. Apague o artefato do "
                "versionamento (e ponha o caminho no .gitignore)."
            )
            return 1
        print(f"OK: nenhum artefato de tempo de execução versionado em '{raiz}'.")
        return 0

    diretorio = args.config_dir if args.config_dir is not None else _config_dir()
    if args.limpar:
        tirados = limpar(diretorio)
        if tirados:
            print(f"LIMPO: faixa sintética tirada da fila em '{diretorio}':")
            print("\n".join(tirados))
        else:
            print(f"OK: nada a limpar em '{diretorio}'.")
        return 0
    encontrados = achados(diretorio)

    if encontrados:
        print(f"FAIL: faixa sintética de teste encontrada em '{diretorio}':")
        print("\n".join(encontrados))
        print(
            "  Isto é a mesa de produção, não um fixture de teste. Um teste que "
            "escreveu aqui não está isolado do ambiente real — corrija o teste "
            "para usar um config_dir() dublê (tmp_path + XDG_CONFIG_HOME), não "
            "apague o achado às cegas: a decisão sobre o que já está gravado é "
            "de quem é dono da máquina."
        )
        return 1

    print(f"OK: nenhuma faixa sintética em '{diretorio}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
