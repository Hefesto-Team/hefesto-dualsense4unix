"""Os portões que o `scripts/portoes.sh` manda rodar continuam LIGADOS no CI."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"

PORTOES_SH = RAIZ / "scripts" / "portoes.sh"

CABECALHO = "_LISTA()"

PISO = 7

def so_na_maquina_dela() -> dict[str, str]:
    """Os portões da tabela que, por decisão registrada, NÃO rodam no CI."""
    texto = PORTOES_SH.read_text(encoding="utf-8")
    inicio = texto.find("_DIVERGENCIAS()")
    assert inicio != -1, "o portoes.sh perdeu o bloco `_DIVERGENCIAS()`"
    declarados: dict[str, str] = {}
    for linha in texto[inicio:].splitlines()[1:]:
        if linha.strip() == "}":
            break
        if linha.startswith("FORA-DO-CI|"):
            _, caminho, razao = linha.split("|", 2)
            declarados[caminho] = razao
    return declarados


def bloco_de_portoes() -> str:
    """A tabela `_LISTA` do `scripts/portoes.sh` — a fonte versionada."""
    if not PORTOES_SH.is_file():
        pytest.skip(
            "scripts/portoes.sh não existe nesta árvore — sem a lista "
            "versionada esta guarda não tem o que conferir."
        )
    texto = PORTOES_SH.read_text(encoding="utf-8")
    inicio = texto.find("_LISTA()")
    if inicio < 0:
        return ""
    fim = texto.find("\nTABELA\n", texto.find("<<'TABELA'", inicio))
    return texto[inicio:fim] if fim > 0 else ""


def portoes_da_casa() -> list[str]:
    """Os scripts de `scripts/` citados no bloco, na ordem em que aparecem."""
    vistos: list[str] = []
    linhas = [linha for linha in bloco_de_portoes().splitlines()
              if not linha.lstrip().startswith("#")]
    for achado in re.findall(r"scripts/[\w./-]+\.(?:sh|py)", "\n".join(linhas)):
        if achado not in vistos:
            vistos.append(achado)
    return vistos


def passos_do_ci() -> list[dict]:
    """Todo passo de todo job do CI, já com o nome do job e o job inteiro junto."""
    dados = yaml.safe_load(CI.read_text(encoding="utf-8"))
    passos: list[dict] = []
    for nome_do_job, job in (dados.get("jobs") or {}).items():
        for passo in job.get("steps") or []:
            passos.append({**passo, "__job__": nome_do_job, "__do_job__": job})
    return passos


INTERPRETADORES = frozenset(
    {
        "bash",
        "sh",
        "env",
        "sudo",
        "python",
        "python3",
        "python3.10",
        "python3.11",
        "python3.12",
        ".venv/bin/python",
        "./.venv/bin/python",
    }
)

_ATRIBUICAO = re.compile(r"[A-Za-z_][A-Za-z_0-9]*=.*")

_ENGOLIDOR = re.compile(r"\|\|\s*(true|:|/bin/true|exit\s+0)\b")

_IF_MORTO = re.compile(r"(?:\$\{\{\s*)?(?:false|0)(?:\s*\}\})?", re.IGNORECASE)


def linhas_de_comando(run: object) -> list[str]:
    """As linhas do `run` que o shell EXECUTA — comentário de shell fora."""
    limpas: list[str] = []
    for linha in str(run).splitlines():
        nua = linha.strip()
        if nua and not nua.startswith("#"):
            limpas.append(nua)
    return limpas


def comandos(linha: str) -> list[str]:
    """A linha quebrada nos operadores que começam um comando NOVO."""
    return [pedaco.strip() for pedaco in re.split(r"\|\||&&|[;|&]", linha) if pedaco.strip()]


def em_posicao_de_comando(comando: str, portao: str) -> bool:
    """O script é EXECUTADO neste comando, ou só aparece escrito nele?"""
    tokens = comando.split()
    if portao not in tokens:
        return False
    antes = tokens[: tokens.index(portao)]
    return all(t in INTERPRETADORES or _ATRIBUICAO.fullmatch(t) for t in antes)


def linhas_que_rodam(passo: dict, portao: str) -> list[str]:
    """As linhas do passo em que o portão é de fato executado."""
    return [
        linha
        for linha in linhas_de_comando(passo.get("run", ""))
        if any(em_posicao_de_comando(comando, portao) for comando in comandos(linha))
    ]


def desligado_por_if(valor: object) -> bool:
    """O `if:` deste passo (ou deste job) nunca é verdadeiro?"""
    if valor is None:
        return False
    if isinstance(valor, bool):
        return not valor
    return bool(_IF_MORTO.fullmatch(" ".join(str(valor).split())))


def passos_que_rodam(agulha: str) -> list[dict]:
    """Os passos que EXECUTAM o comando — não os que o mencionam."""
    return [passo for passo in passos_do_ci() if linhas_que_rodam(passo, agulha)]


def test_a_ancora_da_lista_de_portoes_continua_de_pe() -> None:
    """Sem esta trava, uma reformatação do `portoes.sh` desligaria tudo calada."""
    achados = portoes_da_casa()
    assert len(achados) >= PISO, (
        f"a tabela '{CABECALHO}' de scripts/portoes.sh rendeu "
        f"{len(achados)} scripts, "
        f"piso {PISO}: {achados}\n"
        "Se o bloco MUDOU DE LUGAR ou de formato, conserte a âncora deste "
        "arquivo (CABECALHO e `bloco_de_portoes`) — sem ela a lista derivada "
        "nasce vazia e todos os testes daqui passam sem olhar nada.\n"
        "Se um portão SAIU da tabela de propósito, baixe o PISO no mesmo "
        "commit, para que a queda fique escrita em vez de descoberta."
    )


def test_todo_portao_da_casa_e_invocado_no_ci() -> None:
    """O que a casa manda rodar antes da leva tem de rodar no CI também."""
    for portao in portoes_da_casa():
        if portao in so_na_maquina_dela():
            continue
        assert passos_que_rodam(portao), (
            f"nenhum passo do ci.yml INVOCA `{portao}`, e o portoes.sh manda "
            "rodá-lo antes de fechar qualquer leva.\n"
            "DEVOLVA o passo ao ci.yml, num `run:`. Comentário não conta: o "
            "portão tem de rodar, não de ser mencionado.\n"
            "Foi assim que o check_test_data.sh passou meses existindo, "
            "reprovando e não rodando (BUG-GATE-TEST-DATA-NAO-RODAVA-01).\n"
            "Se ele NÃO deve rodar no CI, declare-o `FORA-DO-CI` no `scripts/portoes.sh` "
            "com a razão e a data."
        )


def test_todo_gancho_do_pre_commit_e_portao_da_casa() -> None:
    """O pre-commit só roda no CI; o que ele confere tem de rodar em casa também."""
    config = yaml.safe_load((RAIZ / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    casa = set(portoes_da_casa())
    faltam = [
        f"{gancho['id']}: {script}"
        for repo in config["repos"]
        for gancho in repo["hooks"]
        for script in re.findall(r"scripts/[\w./-]+\.(?:sh|py)", gancho.get("entry", ""))
        if script not in casa
    ]
    assert not faltam, (
        f"estes ganchos do pre-commit não são portão da casa: {faltam}. O "
        "pre-commit não roda nesta máquina (FORA-DO-LOCAL), então o que ele "
        "confere só reprova no CI, depois do empurrão. Ponha o script na "
        "tabela do `scripts/portoes.sh`."
    )


def test_nenhum_portao_da_casa_virou_aviso() -> None:
    """`continue-on-error` transforma portão em decoração com nome de portão."""
    for portao in portoes_da_casa():
        for passo in passos_que_rodam(portao):
            onde = passo.get("name", passo["__job__"])
            assert not passo.get("continue-on-error"), (
                f"o passo '{onde}' roda `{portao}` com continue-on-error: ele "
                "relata, não protege.\n"
                "TIRE o `continue-on-error`. Um portão que não reprova é pior "
                "que portão nenhum, porque a casa passa a confiar num guarda "
                "que dorme."
            )
            assert not passo["__do_job__"].get("continue-on-error"), (
                f"o JOB '{passo['__job__']}' roda `{portao}` e é inteiro "
                "continue-on-error: o passo parece duro e o job o perdoa.\n"
                "TIRE o `continue-on-error` do job, ou mova este portão para "
                "um job duro. Desligar pelo nível do job é a rota mais barata "
                "de todas — não apaga linha nenhuma e não aparece no diff do "
                "passo."
            )


def test_nenhum_portao_da_casa_tem_a_reprovacao_engolida() -> None:
    """`|| true` roda o portão, ouve o "não", e responde "sim" mesmo assim."""
    for portao in portoes_da_casa():
        for passo in passos_que_rodam(portao):
            onde = passo.get("name", passo["__job__"])
            for linha in linhas_que_rodam(passo, portao):
                engolidor = _ENGOLIDOR.search(linha)
                assert not engolidor, (
                    f"o passo '{onde}' roda `{portao}` e engole a reprovação "
                    f"com `{engolidor.group(0)}`:\n    {linha}\n"
                    "TIRE o engolidor. O portão executa, reprova, e o passo "
                    "fica verde — é `continue-on-error` escrito em shell, e "
                    "sem a palavra `continue-on-error` para o diff denunciar."
                )


def test_nenhum_portao_da_casa_esta_desligado_por_if() -> None:
    """`if: false` desliga o portão sem apagar uma linha sequer do `run`."""
    for portao in portoes_da_casa():
        for passo in passos_que_rodam(portao):
            onde = passo.get("name", passo["__job__"])
            assert not desligado_por_if(passo.get("if")), (
                f"o passo '{onde}' roda `{portao}` sob `if: {passo.get('if')!r}`, "
                "que nunca é verdadeiro: o passo aparece PULADO no relatório e "
                "ninguém lê pulo.\n"
                "TIRE o `if`, ou mova o portão para um passo que sempre roda."
            )
            assert not desligado_por_if(passo["__do_job__"].get("if")), (
                f"o JOB '{passo['__job__']}' roda `{portao}` e o job inteiro "
                f"está sob `if: {passo['__do_job__'].get('if')!r}`, que nunca é "
                "verdadeiro.\n"
                "TIRE o `if` do job, ou mova este portão para um job que roda. "
                "Desligar pelo nível do job não aparece no diff do passo."
            )


def test_todo_portao_da_casa_aponta_para_arquivo_que_existe() -> None:
    """Portão que chama script inexistente é portão que reprova por engano."""
    for portao in portoes_da_casa():
        assert (RAIZ / portao).is_file(), (
            f"o portoes.sh manda rodar `{portao}` e esse arquivo não existe "
            "na árvore. APAGUE a linha da tabela, ou devolva o script."
        )


def test_a_lista_de_lacunas_nao_envelhece_calada() -> None:
    """Sem isto, o `FORA-DO-CI` vira o lugar onde se esconde o que incomoda."""
    derivados = portoes_da_casa()
    for chave, razao in so_na_maquina_dela().items():
        assert chave in derivados, (
            f"{chave!r} está declarado como portão de fora do CI e nem consta "
            "mais da tabela — APAGUE a entrada."
        )
        assert len(razao) > 120, (
            f"a razão de {chave!r} não diz por que o CI não é o lugar dele: {razao!r}"
        )
        assert re.search(r"\d{2}/\d{2}/\d{4}", razao), (
            f"a lacuna {chave!r} não tem data. Sem data ninguém sabe se ela "
            "envelheceu — e uma lacuna sem idade vira paisagem."
        )
