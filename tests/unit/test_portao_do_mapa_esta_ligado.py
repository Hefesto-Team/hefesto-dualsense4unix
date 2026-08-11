"""O portão do mapa de canais está LIGADO — ou este teste reprova.

Esta é a mordida contra o defeito que originou a PARIDADE-PORTAO-01, e ele é
específico: o commit que criou o mapa afirma na mensagem que "o mapa de canais
existe, e ele é portão — não documentação", e MEDIDO em 11/08/2026 o
`scripts/gerar-mapa.py --check` não era chamado por workflow nenhum, por hook
nenhum e por teste nenhum. Pela régua da PORTÃO-VIVO-01, um gate que ninguém
roda não é gate, é arquivo.

O que este arquivo cobra é só isso: que os dois comandos continuem sendo
INVOCADOS. Ele não policia `continue-on-error` do censo — esse sinalizador é
deliberado hoje (a coluna `teste_que_morde` está vazia porque quem a preenche é
a sprint seguinte) e vai sair sozinho quando a dívida for paga; um teste que o
exigisse impediria justamente o conserto. O que ele policia é o passo DURO: o
`gerar-mapa.py --check` não pode ganhar `continue-on-error` sem alguém mexer
aqui, porque aí ele voltaria a relatar em vez de proteger.

PROVA DE QUE MORDE (11/08/2026) — quatro arrancamentos, um por teste, cada um
derrubando EXATAMENTE o seu e mais nenhum:

  - trocado o `run: python3 scripts/gerar-mapa.py --check` do `ci.yml` por um
    `echo`  -> caiu `test_o_ci_chama_o_check_do_mapa`, com a mensagem "o CI não
    chama `scripts/gerar-mapa.py --check`";
  - o mesmo com o `run` do censo  -> caiu `test_o_ci_chama_o_censo_de_paridade`;
  - posto `continue-on-error: true` no passo do `--check`  -> caiu
    `test_o_check_do_mapa_e_passo_duro_nao_relatorio`;
  - trocado o `entry` do hook no `.pre-commit-config.yaml`  -> caiu
    `test_o_hook_de_pre_commit_confere_o_mapa_publicado`.

Tudo devolvido, e a rodada de controle voltou verde.
"""
from __future__ import annotations

from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"
PRE_COMMIT = RAIZ / ".pre-commit-config.yaml"

#: Os dois comandos que a sprint exige vivos. O primeiro confere que o mapa
#: publicado reflete as fontes; o segundo é o censo (a camada 0 do portão).
CHECK_DO_MAPA = "scripts/gerar-mapa.py --check"
CENSO = "scripts/check_paridade_transporte.py"


def passos_do_ci() -> list[dict]:
    """Todo passo de todo job do CI, já com o nome do job junto."""
    dados = yaml.safe_load(CI.read_text(encoding="utf-8"))
    passos: list[dict] = []
    for nome_do_job, job in (dados.get("jobs") or {}).items():
        for passo in job.get("steps") or []:
            passos.append({**passo, "__job__": nome_do_job})
    return passos


def passos_que_rodam(agulha: str) -> list[dict]:
    """Os passos cujo `run` contém o comando. Comentário do YAML não conta.

    O `yaml.safe_load` já descarta comentário, e é por isso que ele está aqui em
    vez de um `in` no texto cru: comentar o passo é a forma mais barata de
    desligar um portão sem parecer que desligou.
    """
    return [
        passo
        for passo in passos_do_ci()
        if agulha in " ".join(str(passo.get("run", "")).split())
    ]


def test_o_ci_chama_o_check_do_mapa() -> None:
    achados = passos_que_rodam(CHECK_DO_MAPA)
    assert achados, (
        f"o CI não chama `{CHECK_DO_MAPA}`. Foi exatamente assim que o mapa "
        "passou a existir como arquivo em vez de portão."
    )


def test_o_ci_chama_o_censo_de_paridade() -> None:
    achados = passos_que_rodam(CENSO)
    assert achados, (
        f"o CI não chama `{CENSO}` — o censo do mapa (camada 0 do portão) "
        "voltou a ser um script que ninguém roda."
    )


def test_o_check_do_mapa_e_passo_duro_nao_relatorio() -> None:
    """`continue-on-error` no passo duro o transformaria de portão em aviso."""
    for passo in passos_que_rodam(CHECK_DO_MAPA):
        assert not passo.get("continue-on-error"), (
            f"o passo '{passo.get('name', passo['__job__'])}' roda "
            f"`{CHECK_DO_MAPA}` com continue-on-error: ele relata, não protege."
        )


def test_os_dois_comandos_apontam_para_arquivos_que_existem() -> None:
    """Portão que chama script inexistente é portão que reprova por engano."""
    assert (RAIZ / "scripts" / "gerar-mapa.py").is_file()
    assert (RAIZ / CENSO).is_file()


def test_o_hook_de_pre_commit_confere_o_mapa_publicado() -> None:
    """O `--check` também vive no pre-commit — e é LÁ que ele vale mais.

    Ele compara mtime, e mtime só é informação na máquina de quem edita: no
    runner, o checkout reescreve a árvore inteira em ordem de caminho e o
    `specs.html` (raiz) sai depois de `docs/` e de `scripts/`, nascendo sempre
    "mais novo" que as fontes. Quem morde por conteúdo no CI é o censo.
    """
    dados = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    entradas = [
        hook.get("entry", "")
        for repositorio in dados.get("repos") or []
        for hook in repositorio.get("hooks") or []
    ]
    assert any(CHECK_DO_MAPA in entrada for entrada in entradas), (
        f"nenhum hook do pre-commit roda `{CHECK_DO_MAPA}`"
    )
