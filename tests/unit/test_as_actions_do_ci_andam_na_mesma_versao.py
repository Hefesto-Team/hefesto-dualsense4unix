"""As quatro actions do GitHub sobem juntas: `checkout`, `setup-python` e o par de artefatos.

Os PRs do Dependabot de 07/10/2026 traziam cada action num PR só, e os fluxos pinados por SHA
(`dependencias.yml`, `imagens-de-teste.yml`, `paginas.yml`, `rotulos.yml`, `wiki.yml`) ficam de fora
de quem troca o `@vN` à mão: um fluxo esquecido roda a action velha sem nenhum aviso. Esta régua lê
TODOS os fluxos e reprova a versão que destoa.

O `upload-artifact` e o `download-artifact` vão juntos porque o artefato que um grava o outro lê no
mesmo run, e o download tem de ser pelo menos tão novo quanto o upload: o `upload-artifact@v7` pode
gravar o arquivo sem zip (`archive: false`), que só o `download-artifact@v8` sabe ler.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FLUXOS = sorted((RAIZ / ".github" / "workflows").glob("*.yml"))
ACOES = ("checkout", "setup-python", "upload-artifact", "download-artifact")

_USO = re.compile(
    r"uses:\s*actions/(?P<ação>"
    + "|".join(ACOES)
    + r")@(?P<ref>\S+)(?:[ \t]+#[ \t]*(?P<nota>\S.*))?$"
)
_SHA = re.compile(r"[0-9a-f]{40}")
_VERSAO = re.compile(r"v(?P<maior>\d+)(?:\.\d+)*")


def _usos() -> list[tuple[str, str, str, str, str]]:
    """(arquivo, linha, ação, ref, nota) de cada `uses:` das quatro actions."""
    saida = []
    for fluxo in FLUXOS:
        for n, linha in enumerate(fluxo.read_text(encoding="utf-8").splitlines(), 1):
            achou = _USO.search(linha)
            if achou:
                saida.append(
                    (fluxo.name, str(n), achou["ação"], achou["ref"], achou["nota"] or "")
                )
    return saida


def _maior(ref: str, nota: str) -> int | None:
    """O número maior da versão: do `@vN`, ou do `# vN.x.y` quando o ref é um SHA."""
    texto = nota if _SHA.fullmatch(ref) else ref
    achou = _VERSAO.fullmatch(texto.split()[0]) if texto.split() else None
    return int(achou["maior"]) if achou else None


def _por_acao() -> dict[str, dict[int | None, list[str]]]:
    quadro: dict[str, dict[int | None, list[str]]] = defaultdict(lambda: defaultdict(list))
    for arquivo, linha, acao, ref, nota in _usos():
        quadro[acao][_maior(ref, nota)].append(f"{arquivo}:{linha}")
    return quadro


def test_a_leitura_enxerga_as_quatro_actions() -> None:
    quadro = _por_acao()
    assert set(quadro) == set(ACOES), f"a régua não achou todas as actions: {sorted(quadro)}"
    assert sum(len(v) for porMaior in quadro.values() for v in porMaior.values()) >= 20


def test_todo_uso_tem_versao_legivel() -> None:
    """`@main`, `@master` ou um SHA sem o comentário `# vN` não dizem a versão: reprova."""
    ilegiveis = [
        f"{arq}:{lin} actions/{acao}@{ref}"
        for arq, lin, acao, ref, nota in _usos()
        if _maior(ref, nota) is None
    ]
    assert ilegiveis == [], (
        "uso da action sem versão legível (`@vN`, ou SHA de 40 hexa seguido de `# vN.x.y`): "
        + "; ".join(ilegiveis)
    )


def test_cada_action_roda_numa_versao_so_em_todos_os_fluxos() -> None:
    desencontros = {
        acao: {str(maior): onde for maior, onde in versoes.items()}
        for acao, versoes in _por_acao().items()
        if len(versoes) > 1
    }
    assert desencontros == {}, (
        "a mesma action em mais de uma versão maior entre os fluxos "
        f"(sobe tudo junto, SHA incluído): {desencontros}"
    )


def test_o_mesmo_comentario_de_versao_aponta_o_mesmo_sha() -> None:
    """Um SHA trocado só no comentário (`@<sha da v4> # v7.0.1`) passaria pela leitura do `# vN`.

    Sem rede não se confere o SHA contra a tag, mas entre os fluxos se confere: a mesma action com
    o mesmo comentário tem de apontar o MESMO commit, e o mesmo commit não leva dois comentários.
    O fluxo esquecido na subida destoa dos outros, que é o caso que esta régua existe para pegar.
    """
    shas_por_nota: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    notas_por_sha: dict[str, set[str]] = defaultdict(set)
    for arquivo, linha, acao, ref, nota in _usos():
        if not _SHA.fullmatch(ref):
            continue
        versao = nota.split()[0] if nota.split() else ""
        shas_por_nota[(acao, versao)][ref].append(f"{arquivo}:{linha}")
        notas_por_sha[ref].add(versao)
    divergentes = {
        f"{acao} {versao}": {sha[:12]: onde for sha, onde in shas.items()}
        for (acao, versao), shas in shas_por_nota.items()
        if len(shas) > 1
    }
    assert divergentes == {}, (
        "o mesmo comentário de versão sobre SHAs diferentes (um fluxo ficou para trás): "
        f"{divergentes}"
    )
    ambiguos = {sha[:12]: sorted(notas) for sha, notas in notas_por_sha.items() if len(notas) > 1}
    assert ambiguos == {}, f"o mesmo SHA com comentários de versão diferentes: {ambiguos}"


def test_o_download_nunca_e_mais_velho_que_o_upload() -> None:
    quadro = _por_acao()
    (subida,) = quadro["upload-artifact"]
    (descida,) = quadro["download-artifact"]
    assert subida is not None and descida is not None
    assert subida >= 4 and descida >= 4, "antes da v4 o artefato era outro backend: não se misturam"
    assert descida >= subida, (
        f"download-artifact@v{descida} lendo o que o upload-artifact@v{subida} grava: "
        "o download tem de ser pelo menos tão novo quanto o upload"
    )
