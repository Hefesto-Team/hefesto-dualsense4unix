#!/usr/bin/env python3
"""Falha se uma faixa de MAC SINTÉTICA de teste aparecer no `config_dir()` real.

T-06 (ONDA0-Z7 · O AMBIENTE PRESUMIDO 01, 24/08/2026). Medido na bancada dela
em 23/08/2026: quatro registros com endereços da faixa `aabbcc` vazaram para
`~/.config/hefesto-dualsense4unix/controllers.json` — a mesa de produção dela,
não um fixture — empurrando os quatro DualSense REAIS dela das posições 1-4
para 1, 6, 7 e 8. `grep -rl aabbcc tests/ | wc -l` achou 91 arquivos de teste
usando a faixa; algum deles escreveu no disco dela em vez de num diretório
isolado (T-06 também rastreia a CAUSA — ver `docs/process/agentes/` da leva).

As faixas sintéticas da casa (CLAUDE.md, `scripts/check_test_data.sh`),
verificadas nas duas grafias — com `:` e sem:

  aabbcc  / aa:bb:cc
  02fe00  / 02:fe:00
  e8473a  / e8:47:3a

OS CHAMADORES, e por que são TRÊS lugares diferentes (LUZ-CEGA-01/E8,
25/08/2026 — até aqui este portão não tinha chamador NENHUM: nem CI, nem
gancho, nem lista do ``CLAUDE.md``. Portão que ninguém chama é o defeito
`A-CASA-SABE-E-O-PRODUTO-NÃO-FAZ`):

* ``--arvore`` (o DEFAULT, e o que roda no CI) varre a **árvore versionada**
  atrás dos arquivos que só o ``config_dir()`` deveria ter — um
  ``controllers.json`` commitado é artefato de tempo de execução no lugar
  errado, e se ele trouxer faixa de fixture o defeito atravessou outra porta.
  É determinístico, não depende de ``$HOME`` e por isso vale no CI, onde o
  ``~/.config`` está vazio e a varredura dele seria verde por vacuidade;
* ``--casa`` varre o ``config_dir()`` REAL. **Não roda sozinho em lugar
  nenhum**, de propósito: na máquina de quem já tem a poluição gravada ele
  fica vermelho todo dia até alguém decidir limpar — e a decisão sobre o que
  já está no disco é de quem é dono da máquina. Quem quer a resposta pede;
* a suíte chama a função :func:`enderecos` no ``tests/conftest.py``
  (FAIXA-NO-BERCO-01): ali a régua é o DELTA — reprova só se apareceu um
  endereço sintético que não estava lá no começo da sessão. Assim ela é verde
  numa máquina já poluída e vermelha no dia em que um teste polui.

Uso:
    python3 scripts/check_faixa_sintetica.py             # --arvore (default)
    python3 scripts/check_faixa_sintetica.py --casa      # o config_dir() real
    python3 scripts/check_faixa_sintetica.py --config-dir /algum/lugar
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# As três faixas sintéticas da casa. Cada uma casa nas DUAS grafias: com ':'
# entre os três primeiros octetos (aa:bb:cc...) e sem (aabbcc...) — o
# `controllers.json` medido em 23/08 usava a grafia sem ':'.
FAIXAS_SINTETICAS = ("aabbcc", "02fe00", "e8473a")


def _padrao_para(faixa: str) -> re.Pattern[str]:
    """Um regex por faixa, casando as duas grafias, sem diferenciar maiúscula."""
    a, b, c = faixa[0:2], faixa[2:4], faixa[4:6]
    return re.compile(rf"(?i){a}:?{b}:?{c}(?::?[0-9a-f]{{2}}){{0,3}}")


_PADROES = {faixa: _padrao_para(faixa) for faixa in FAIXAS_SINTETICAS}

#: Extensões que fazem sentido varrer — o `config_dir()` do Hefesto só guarda
#: JSON, texto e (raramente) log; nada binário mora lá por contrato.
_EXTENSOES_VARRIDAS = {".json", ".txt", ".log", ".conf", ".ini", ""}


def _vale_varrer(caminho: Path) -> bool:
    """Basta UM sufixo conhecido, em qualquer posição, e não só o último.

    PONTO CEGO MEDIDO — 25/08/2026, e quem o achou foi quem coordena, ao ver a
    própria régua ficar VERDE sobre um arquivo que ele mesmo acabara de criar:
    ``controllers.json.antes-de-tirar-fixtures-20260825``, com quatro endereços
    de fixture dentro, na config viva dela.

    ``Path.suffix`` devolve só o ÚLTIMO sufixo. Todo backup carrega um sufixo
    próprio — ``.bak``, ``.old``, ``.orig``, ``.2026-08-25``, ``.antes-de-X`` —,
    e por isso **backup era exatamente a classe de arquivo que esta régua não
    enxergava**. É a pior forma de ponto cego: some justamente onde alguém
    guardou uma cópia do estado que a régua existe para vigiar.

    ``Path.suffixes`` parte o nome em todos os pontos, então
    ``controllers.json.antes-de-X`` traz ``['.json', '.antes-de-X']`` e o
    ``.json`` basta. Um arquivo sem ponto nenhum continua varrido (o ``""`` da
    lista), e binário sem sufixo conhecido continua de fora.
    """
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
    """``{"<arquivo>::<endereço colado, minúsculo>"}`` — a forma COMPARÁVEL.

    Irmã de :func:`achados`, que devolve texto para pessoa ler. Esta devolve
    conjunto, para o ``tests/conftest.py`` (FAIXA-NO-BERCO-01) comparar o
    começo da sessão com o fim: o que interessa lá não é "existe faixa
    sintética" — numa máquina já poluída existe desde ontem — e sim "apareceu
    uma que não estava aqui quando a suíte começou".

    A chave inclui o ARQUIVO de propósito: o mesmo endereço migrando para um
    arquivo onde não estava é escrita nova, e escrita nova é o que se vigia.
    O número da linha fica de fora — uma linha a mais no arquivo empurraria
    todas as outras e produziria alarme sem escrita nenhuma.
    """
    vistos: set[str] = set()
    for linha in achados(diretorio):
        # "  <caminho>:<linha>: faixa sintética 'x' -> 'valor'"
        cabeca, _, cauda = linha.rpartition(" -> ")
        caminho = cabeca.strip().split(":")[0]
        valor = cauda.strip().strip("'\"").replace(":", "").lower()
        vistos.add(f"{caminho}::{valor}")
    return vistos


#: Os arquivos que o produto escreve DENTRO do ``config_dir()``. Um deles na
#: árvore versionada é artefato de tempo de execução no lugar errado — e é
#: exatamente o que o ``--arvore`` procura. A lista sai dos donos de cada um:
#: ``daemon/subsystems/identity.py``, ``external_mask.py``, ``utils/maquina.py``,
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

#: Onde a faixa sintética é LEGÍTIMA e não se procura nada: fixture de teste é
#: para isso, e documento de sprint cita o achado para não o perder.
_ARVORE_IGNORADA = ("tests", "docs", ".git", "captures", "examples")


def achados_na_arvore(raiz: Path) -> list[str]:
    """Artefatos de tempo de execução COMMITADOS que trazem faixa sintética."""
    linhas: list[str] = []
    for nome in NOMES_DE_TEMPO_DE_EXECUCAO:
        for caminho in sorted(raiz.rglob(nome)):
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
    args = parser.parse_args(argv)

    if args.config_dir is None and not args.casa:
        raiz = Path(__file__).resolve().parents[1]
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
