"""Os dois emblemas da capa: o de versão entrou no portão, o de testes parou de fingir contagem.

Item 1.15 da ONDA 1 (PUBLICAÇÃO-FIEL-01/E6), medido em 01/08 nesta árvore:

  - `README.md:12` anunciava `versão-0.4.0 alfa` com a 0.5.0 publicada, com a
    linha em prosa do MESMO arquivo já em 0.5.0 e com o `pyproject.toml` em
    0.5.0. O `scripts/check_version_consistency.py` casava só a prosa
    (`Versão:\\s*(\\S+)`), então o emblema — a primeira coisa que alguém vê —
    envelhecia por fora de todo portão. Cura: um segundo alvo no mesmo arquivo.
  - `README.md:13` anunciava `testes-6097`. A coleta desta máquina no mesmo dia
    devolvia 6408. O número já tinha sido repintado à mão sete vezes (1856,
    2022, 4867, 5256, 5529, 5783, 6089, 6097) e defasava de novo em dias.

DESENHO ESCOLHIDO PARA O EMBLEMA DE TESTES, E O PORQUÊ — o emblema deixou de
declarar contagem e passou a declarar um PISO ("mais de 5000"), conferido aqui
contra o número de funções `def test_` que existem em `tests/`.

Por que piso, e não o número exato derivado da coleta:

1. Não existe UM número. Medidos no mesmo dia, na mesma árvore: 6408 itens
   coletados por `pytest --collect-only`, 6307 passando na execução relatada, e
   5694 funções `def test_` no texto dos arquivos. Os três são verdadeiros e
   respondem a perguntas diferentes; um emblema com um deles mente sobre os
   outros dois.
2. A coleta depende do AMBIENTE. Nesta máquina, com GTK real, entram módulos de
   interface inteiros; no `lint-test` do CI eles saem — módulo com
   `pytest.importorskip` no topo não contribui teste NENHUM para a coleta. Um
   portão que comparasse o emblema com `--collect-only` reprovaria no runner
   exatamente por estar num runner. Contar `def test_` no texto é imune a isso:
   é leitura de arquivo, não importação.
3. Um portão que reprova a CI por um teste a mais vira ruído e alguém o
   desliga — e aí o emblema volta a mentir sem ninguém olhando. O piso só
   reprova quando a suíte ENCOLHE abaixo do que a capa promete, que é
   justamente o caso em que a capa passa a mentir. Suíte crescendo nunca
   derruba a CI: o emblema fica subestimado, e subestimar não é mentir.

O preço, dito: o piso envelhece para baixo (a capa diz "mais de 5000" com 5694
funções e 6408 itens coletados). Repintá-lo é opcional e vale uma vez por
milhar. O estado VIVO da suíte já é publicado ao lado, pelo emblema de CI, que
é derivado de verdade — o número exato mora onde é medido, não na capa.

Estes testes são o portão: o job `lint-test` do ci.yml roda `pytest tests/unit`,
então não foi preciso mexer no ci.yml.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
README = REPO / "README.md"
GATE_REL = "scripts/check_version_consistency.py"

#: O texto do emblema de testes fica entre `badge/testes-` e o `-` da cor.
_RE_EMBLEMA_TESTES = re.compile(r"img\.shields\.io/badge/testes-([^-\)]*)-")

#: O emblema de versão, com `versão` percent-encoded pelo shields.io.
_RE_EMBLEMA_VERSAO = re.compile(r"img\.shields\.io/badge/vers%C3%A3o-([0-9][^%-]*)")

#: Uma função `def test_` por linha, em qualquer indentação (classe inclusive).
_RE_FUNCAO_DE_TESTE = re.compile(r"^\s*(?:async\s+)?def test_\w*\(", re.MULTILINE)


def _versao_canonica() -> str:
    try:
        import tomllib
    except ImportError:  # pragma: no cover — 3.10
        import tomli as tomllib  # type: ignore[no-redef]
    dados = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    return str(dados["project"]["version"])


def _targets_do_portao() -> list[tuple[str, str, str]]:
    """Lê `_TARGETS` do portão real sem executá-lo (molde do
    tests/unit/test_versoes_rancosas_e_seed_flatpak.py)."""
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import check_version_consistency as gate
    finally:
        sys.path.pop(0)
    return list(gate._TARGETS)


def _texto_do_readme() -> str:
    return README.read_text(encoding="utf-8")


def _funcoes_de_teste_no_repo() -> int:
    """Contagem ESTÁTICA de funções de teste: lê o texto, não importa nada.

    É um piso da coleta real por construção — `parametrize` multiplica cada
    função em vários itens, e nenhuma função vira zero item num ambiente
    completo. Por não importar módulo nenhum, o número não muda entre a máquina
    com GTK e o runner sem GTK, que é o requisito deste portão.
    """
    total = 0
    for arquivo in sorted((REPO / "tests").rglob("test_*.py")):
        total += len(_RE_FUNCAO_DE_TESTE.findall(arquivo.read_text(encoding="utf-8")))
    return total


def _piso_declarado(texto_bruto: str) -> int | None:
    """Piso anunciado pelo emblema, ou None se ele finge contagem exata.

    Formas aceitas: "mais de 5000" e "5000+" (o `+` chega como `%2B`). Um
    número solto — "6097" — devolve None de propósito: é a forma que já
    defasou oito vezes.
    """
    legivel = texto_bruto.replace("%20", " ").replace("%2B", "+").strip()
    achado = re.fullmatch(r"mais de (\d+)|(\d+)\s*\+", legivel)
    if achado is None:
        return None
    return int(achado.group(1) or achado.group(2))


# --------------------------------------------------------------------------
# 1) O emblema de versão é alvo do portão — e está em dia.
# --------------------------------------------------------------------------


def test_emblema_de_versao_e_alvo_do_portao_de_versao() -> None:
    """Sem alvo próprio, o emblema passa por baixo da régua da prosa."""
    alvos_do_readme = [alvo for alvo in _targets_do_portao() if alvo[1] == "README.md"]
    assert len(alvos_do_readme) >= 2, (
        "o README voltou a ter um alvo só em "
        f"{GATE_REL}: a linha em prosa. O emblema da capa é um segundo literal "
        "no mesmo arquivo e precisa do próprio regex (item 1.15 da ONDA 1)."
    )
    texto = _texto_do_readme()
    casando = [
        alvo
        for alvo in alvos_do_readme
        if (achado := re.search(alvo[2], texto, re.MULTILINE)) is not None
        and "shields.io" in achado.group(0)
    ]
    assert casando, (
        "nenhum alvo do portão casa a URL do shields.io no README — o emblema "
        "de versão voltou a ser invisível ao portão"
    )


def test_emblema_de_versao_bate_com_o_pyproject() -> None:
    """A mordida no arquivo real: repintar o emblema para 0.4.0 derruba isto
    e derruba o `python scripts/check_version_consistency.py` junto."""
    achado = _RE_EMBLEMA_VERSAO.search(_texto_do_readme())
    assert achado is not None, "o emblema de versão sumiu da capa do README"
    assert achado.group(1) == _versao_canonica(), (
        f"a capa anuncia a versão {achado.group(1)!r} e o pyproject.toml diz "
        f"{_versao_canonica()!r}"
    )


def test_prosa_e_emblema_do_readme_dizem_a_mesma_versao() -> None:
    """Os dois literais do mesmo arquivo já divergiram: a prosa foi para a
    0.5.0 no bump e o emblema ficou na 0.4.0."""
    texto = _texto_do_readme()
    prosa = re.search(r"Versão:\s*(\S+)", texto)
    emblema = _RE_EMBLEMA_VERSAO.search(texto)
    assert prosa is not None and emblema is not None
    assert prosa.group(1) == emblema.group(1)


# --------------------------------------------------------------------------
# 2) O emblema de testes não pode voltar a fingir contagem exata.
# --------------------------------------------------------------------------


def test_emblema_de_testes_existe_e_aponta_para_a_suite() -> None:
    texto = _texto_do_readme()
    assert _RE_EMBLEMA_TESTES.search(texto) is not None, (
        "o emblema de testes sumiu da capa do README"
    )


def test_emblema_de_testes_nao_finge_contagem_exata() -> None:
    """A mordida do desenho: repintar `testes-6408` derruba isto.

    Número exato na capa é a forma que já defasou oito vezes, e defasa por
    construção — ele muda a cada leva e ninguém o repinta na hora certa.
    """
    achado = _RE_EMBLEMA_TESTES.search(_texto_do_readme())
    assert achado is not None
    bruto = achado.group(1)
    piso = _piso_declarado(bruto)
    assert piso is not None, (
        f"o emblema de testes voltou a declarar contagem: {bruto!r}. Ele tem de "
        "declarar um PISO — 'mais de N' ou 'N+' —, porque não existe UM número "
        "de testes: a coleta desta máquina, a execução e a contagem de funções "
        "dão três valores diferentes, e a coleta ainda muda de runner para "
        "runner conforme gi/cairo existam."
    )


def test_piso_do_emblema_de_testes_e_verdadeiro() -> None:
    """O piso só reprova quando a suíte ENCOLHE abaixo do que a capa promete.

    Suíte crescendo nunca derruba a CI aqui — é de propósito: portão que
    reprova por um teste a mais vira ruído e é desligado.
    """
    achado = _RE_EMBLEMA_TESTES.search(_texto_do_readme())
    assert achado is not None
    piso = _piso_declarado(achado.group(1))
    assert piso is not None, "coberto por test_emblema_de_testes_nao_finge_contagem_exata"
    funcoes = _funcoes_de_teste_no_repo()
    assert funcoes >= piso, (
        f"a capa promete mais de {piso} testes e há {funcoes} funções `def "
        "test_` em tests/. Ou a suíte encolheu, ou o piso foi pintado alto "
        "demais."
    )


def test_a_contagem_estatica_nao_ficou_muda() -> None:
    """Guarda do próprio medidor: um regex quebrado devolveria 0 e o piso
    passaria a ser conferido contra nada."""
    assert _funcoes_de_teste_no_repo() > 1000, (
        "o contador de funções `def test_` parou de achar testes — o portão do "
        "piso estaria medindo nada"
    )
