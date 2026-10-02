"""O portão do mapa de canais está LIGADO — ou este teste reprova."""
from __future__ import annotations

from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"
PRE_COMMIT = RAIZ / ".pre-commit-config.yaml"

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
    """Os passos cujo `run` contém o comando. Comentário do YAML não conta."""
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
    """O `--check` também vive no pre-commit, e ali ele pega a divergência cedo."""
    dados = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    entradas = [
        hook.get("entry", "")
        for repositorio in dados.get("repos") or []
        for hook in repositorio.get("hooks") or []
    ]
    assert any(CHECK_DO_MAPA in entrada for entrada in entradas), (
        f"nenhum hook do pre-commit roda `{CHECK_DO_MAPA}`"
    )
