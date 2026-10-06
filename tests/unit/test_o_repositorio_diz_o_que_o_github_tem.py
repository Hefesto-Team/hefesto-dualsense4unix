"""O arquivo `.github/repositorio.yml` e o `scripts/github/aplicar.py`.

Três coisas se medem aqui:

1. o esquema do arquivo (e que cada função que ele declara tem quem a aplique);
2. o nome de cada check obrigatório existe como job num workflow, e o workflow roda em PR;
3. o aplicador contra um `gh` de mentira: um executável no PATH que guarda o estado de um
   repositório falso em JSON, grava as chamadas e recusa o que a API real recusaria.

Nada daqui fala com o GitHub.
"""
from __future__ import annotations

import importlib.util
import itertools
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
ARQUIVO = RAIZ / ".github" / "repositorio.yml"
APLICAR = RAIZ / "scripts" / "github" / "aplicar.py"

_spec = importlib.util.spec_from_file_location("aplicar_do_github", APLICAR)
assert _spec and _spec.loader
aplicar = importlib.util.module_from_spec(_spec)
sys.modules["aplicar_do_github"] = aplicar
_spec.loader.exec_module(aplicar)

Capsys = pytest.CaptureFixture[str]
REPO = "Hefesto-Team/ensaio"


def _dados() -> dict[str, Any]:
    d = yaml.safe_load(ARQUIVO.read_text(encoding="utf-8"))
    assert isinstance(d, dict)
    return d


# ---------------------------------------------------------------------------
# 1. O esquema e os aplicadores
# ---------------------------------------------------------------------------


def test_o_arquivo_do_repositorio_vale() -> None:
    assert aplicar.validar(_dados()) == []


def test_as_funcoes_desligadas_dizem_quando_voltam() -> None:
    funcoes = _dados()["funções"]
    desligadas = [n for n, v in funcoes.items() if not v["ligada"]]
    assert desligadas == ["sponsor"], "tudo o que o GitHub oferece está ligado, menos o que depende de quem recebe"
    assert str(funcoes["sponsor"]["depois"]).strip()
    assert all(funcoes[n]["ligada"] is True for n in ("issues", "wiki", "pages", "projects", "discussions"))


def test_o_ruleset_exige_o_check_de_autoria_e_o_lint_test() -> None:
    porta = [r for r in _dados()["rulesets"] if "checks" in r]
    assert len(porta) == 1
    assert "autoria" in porta[0]["checks"]
    assert any(c.startswith("lint-test") for c in porta[0]["checks"])
    assert {r["nome"] for r in _dados()["rulesets"] if r.get("sem_push_forcado")}


def regras_que_barram_a_historia(dados: dict[str, Any]) -> list[str]:
    """Os rulesets sem exceção que barram commit que a história já tem.

    O histórico linear olha cada commit que o push acrescenta ao ramo, inclusive os antigos: a
    história do `dev` tem centenas de merges que o `main` não tem (`git rev-list --merges`). Num
    ruleset sem exceção, a regra barraria o primeiro push do repositório recriado e o avanço do
    `main` na release, e nada a desligaria senão mudar o arquivo no meio da janela.
    """
    return [r["nome"] for r in dados["rulesets"]
            if r.get("historico_linear") and r.get("excecao") is None]


def test_a_regra_sem_excecao_nao_barra_a_historia_que_ja_existe() -> None:
    assert regras_que_barram_a_historia(_dados()) == []
    porta = next(r for r in _dados()["rulesets"] if "checks" in r)
    assert porta.get("historico_linear") is True, "o PR de quem não mantém entra em linha reta"


def test_mordida_historico_linear_sem_excecao_reprova() -> None:
    dados = _dados()
    historia = next(r for r in dados["rulesets"] if r.get("excecao") is None)
    historia["historico_linear"] = True
    assert regras_que_barram_a_historia(dados) == [historia["nome"]]


def funcoes_sem_aplicador(dados: dict[str, Any], aplicadores: dict[str, Any]) -> list[str]:
    return [f for f in aplicar.funções_declaradas(dados) if f not in aplicadores]


def test_toda_funcao_declarada_tem_quem_a_aplique() -> None:
    dados = _dados()
    assert funcoes_sem_aplicador(dados, aplicar.APLICADORES) == []
    # e o inverso: aplicador sem declaração é código morto
    assert sorted(set(aplicar.APLICADORES) - set(aplicar.funções_declaradas(dados))) == []


def test_toda_regra_de_ruleset_declarada_tem_quem_a_monte() -> None:
    assert set(aplicar.regras_declaradas(_dados())) <= set(aplicar.REGRAS_DE_RULESET)
    for chave, tipo in aplicar.REGRAS_DE_RULESET.items():
        r: dict[str, Any] = {"nome": "x", "ramos": ["dev"], chave: True}
        if chave == "revisão":
            r[chave] = {"aprovacoes": 1}
        if chave == "checks":
            r[chave] = ["autoria"]
        if chave == "assinatura":
            r[chave] = "exigida"
        tipos = [x["type"] for x in aplicar.corpo_do_ruleset(r)["rules"]]
        assert tipos == [tipo], chave


def test_mordida_funcao_sem_aplicador_reprova(monkeypatch: pytest.MonkeyPatch) -> None:
    dados = _dados()
    incompleto = dict(aplicar.APLICADORES)
    del incompleto["seguranca.relato_privado"]
    assert funcoes_sem_aplicador(dados, incompleto) == ["seguranca.relato_privado"]
    # uma função nova no arquivo, sem lugar no esquema, também reprova
    dados["seguranca"]["radar_novo"] = True
    assert any("radar_novo" in e for e in aplicar.validar(dados))
    assert "seguranca.radar_novo" in funcoes_sem_aplicador(dados, aplicar.APLICADORES)


@pytest.mark.parametrize(
    "estraga",
    [
        lambda d: d["funções"]["sponsor"].pop("depois"),
        lambda d: d["funções"].pop("sponsor"),
        lambda d: d["seguranca"]["releases_imutaveis"].pop("depois"),
        lambda d: d["seguranca"].pop("linguagens_da_varredura"),
        lambda d: d["seguranca"].update(grafo_de_dependencias=False),
        lambda d: d["rotulos"]["lista"][0].update(cor="#d73a4a"),
        lambda d: d["rotulos"]["lista"].append(dict(d["rotulos"]["lista"][0])),
        lambda d: d["acoes"].update(aprovacao_de_fork="ninguem"),
        lambda d: d["ambientes"][0].update(revisores=[]),
        lambda d: d["ambientes"][0].update(tags=[], ramos=[]),
        lambda d: d["equipes"][0].update(nome="Mantenedores Da Casa"),
        lambda d: d["projetos"][0]["etapas"][0].update(cor="VERDE"),
        lambda d: d["discussoes"]["categorias"][0].update(slug="Anúncios"),
        lambda d: d["rulesets"][0].update(assinatura="opcional"),
        lambda d: d["rulesets"][2].update(ramos=["dev"]),
        lambda d: d["de_fora"].pop("lfs"),
        lambda d: d["de_fora"].update(codespaces=""),
        lambda d: d["about"].update(topicos=["Linux Ruim"]),
        lambda d: d["about"].update(topicos=[f"t{i}" for i in range(21)]),
        lambda d: d["mantenedores"][0].update(função="dono"),
        lambda d: d["rulesets"][0].update(ramos=[]),
        lambda d: d["rulesets"][0].update(sem_apagar="sim"),
        lambda d: d["rulesets"][1]["revisão"].update(aprovacoes=0),
        lambda d: d["rulesets"][1].update(checks=[]),
        lambda d: d["rulesets"][1].update(excecao="todos"),
        lambda d: d["rulesets"][1].update(regra_inventada=True),
        lambda d: d["rulesets"][1].update(nome=d["rulesets"][0]["nome"]),
        lambda d: d.update(versão=2),
    ],
)
def test_mordida_o_esquema_reprova_o_arquivo_estragado(estraga: Any) -> None:
    dados = _dados()
    estraga(dados)
    assert aplicar.validar(dados), "o esquema aceitou um arquivo estragado"


# ---------------------------------------------------------------------------
# 2. O nome de cada check obrigatório é um job que existe
# ---------------------------------------------------------------------------


def _combinacoes(job: dict[str, Any]) -> list[dict[str, Any]]:
    """Cada combinação da matriz do job (as dimensões cruzadas, mais as do `include`)."""
    matriz = (job.get("strategy") or {}).get("matrix") or {}
    dims = {k: v for k, v in matriz.items() if k not in ("include", "exclude")}
    combos = [dict(zip(dims, c, strict=True)) for c in itertools.product(*dims.values())]
    if not dims:
        combos = []
    for extra in matriz.get("include") or []:
        # sem dimensões, cada `include` é uma combinação própria
        casou = [c for c in combos
                 if dims and all(c[k] == v for k, v in extra.items() if k in dims)]
        if casou:
            for c in casou:
                c.update({k: v for k, v in extra.items() if k not in dims})
        else:
            combos.append(dict(extra))
    return combos


def _nome_do_check(nome: str, valores: dict[str, Any]) -> str:
    """O nome que o GitHub mostra: o `name` com a matriz expandida; sem `${{ matrix.* }}` no
    nome, ele acrescenta os valores entre parênteses (com `name` ou sem)."""
    if "${{ matrix." in nome:
        for k, v in valores.items():
            nome = nome.replace("${{ matrix." + k + " }}", str(v))
        return nome
    return f"{nome} ({', '.join(str(v) for v in valores.values())})"


def test_o_nome_do_check_segue_a_regra_do_github() -> None:
    sem_nome = {"strategy": {"matrix": {"python": ["3.10", "3.12"]}}}
    assert [_nome_do_check("lint-test", v) for v in _combinacoes(sem_nome)] == [
        "lint-test (3.10)", "lint-test (3.12)"]
    # com `name` e sem a matriz nele, o GitHub acrescenta os valores do mesmo jeito
    com_nome = {"strategy": {"matrix": {"os": ["a"]}}}
    assert [_nome_do_check("Smoke", v) for v in _combinacoes(com_nome)] == ["Smoke (a)"]
    so_include = {"strategy": {"matrix": {"include": [{"distro": "fedora"}, {"distro": "arch"}]}}}
    assert [_nome_do_check("Smoke ${{ matrix.distro }}", v) for v in _combinacoes(so_include)] == [
        "Smoke fedora", "Smoke arch"]


def contextos(raiz: Path) -> dict[str, dict[str, Any]]:
    """Cada nome de check que os workflows de `raiz` produzem, e se o workflow roda em PR."""
    achados: dict[str, dict[str, Any]] = {}
    for arq in sorted((raiz / ".github" / "workflows").glob("*.y*ml")):
        wf = yaml.safe_load(arq.read_text(encoding="utf-8")) or {}
        gatilhos = wf.get(True, wf.get("on")) or {}  # o PyYAML lê `on:` como True
        em_pr = "pull_request" in (gatilhos if isinstance(gatilhos, (dict, list)) else [gatilhos])
        for ident, job in (wf.get("jobs") or {}).items():
            nome = str(job.get("name", ident))
            nomes = [_nome_do_check(nome, v) for v in _combinacoes(job)] or [nome]
            for n in nomes:
                achados[n] = {"arquivo": arq.name, "pr": em_pr}
    return achados


def checks_sem_job(dados: dict[str, Any], raiz: Path) -> list[str]:
    """Os checks exigidos que nenhum job produz, ou que o workflow não roda em PR."""
    existentes = contextos(raiz)
    faltam: list[str] = []
    for r in dados["rulesets"]:
        for check in r.get("checks", []):
            if check not in existentes:
                faltam.append(f"{check}: nenhum job com esse nome")
            elif not existentes[check]["pr"]:
                faltam.append(f"{check}: o workflow {existentes[check]['arquivo']} não roda em PR")
    return faltam


def test_cada_check_obrigatorio_existe_como_job_e_roda_em_pr() -> None:
    assert checks_sem_job(_dados(), RAIZ) == []


@pytest.fixture
def copia_dos_workflows(tmp_path: Path) -> Path:
    destino = tmp_path / "copia"
    shutil.copytree(RAIZ / ".github" / "workflows", destino / ".github" / "workflows")
    return destino


def _trocar(arq: Path, antes: str, depois: str, a_partir_de: str = "") -> None:
    """Troca a primeira ocorrência de `antes`, contada a partir de `a_partir_de`."""
    texto = arq.read_text(encoding="utf-8")
    inicio = texto.index(a_partir_de) if a_partir_de else 0
    assert antes in texto[inicio:], antes
    arq.write_text(
        texto[:inicio] + texto[inicio:].replace(antes, depois, 1), encoding="utf-8")


def test_mordida_trocar_o_nome_do_job_reprova(copia_dos_workflows: Path) -> None:
    wf = copia_dos_workflows / ".github" / "workflows"
    assert checks_sem_job(_dados(), copia_dos_workflows) == []
    _trocar(wf / "autoria.yml", "\n  autoria:\n", "\n  autoria-nova:\n")
    assert any(f.startswith("autoria:") for f in checks_sem_job(_dados(), copia_dos_workflows))


def test_mordida_tirar_uma_versao_da_matriz_reprova(copia_dos_workflows: Path) -> None:
    wf = copia_dos_workflows / ".github" / "workflows"
    _trocar(wf / "ci.yml", '["3.10", "3.11", "3.12"]', '["3.10", "3.11"]',
            a_partir_de="\n  lint-test:\n")
    achados = checks_sem_job(_dados(), copia_dos_workflows)
    assert any(f.startswith("lint-test (3.12)") for f in achados)


def test_mordida_workflow_que_nao_roda_em_pr_reprova(copia_dos_workflows: Path) -> None:
    wf = copia_dos_workflows / ".github" / "workflows"
    gatilho = "  pull_request:\n    types: [opened, edited, synchronize, reopened]\n"
    _trocar(wf / "autoria.yml", gatilho, "")
    assert any("não roda em PR" in f for f in checks_sem_job(_dados(), copia_dos_workflows))


# ---------------------------------------------------------------------------
# 3. O aplicador contra o `gh` de mentira
# ---------------------------------------------------------------------------

GH_DE_MENTIRA = RAIZ / "tests" / "fixtures" / "github" / "gh_de_mentira.py"

ESTADO_INICIAL: dict[str, Any] = {
    "user": aplicar.CONTA_DA_CASA,
    "slug": REPO,
    "privado": False,
    "repo": {
        "node_id": "R_kgDOabc",
        "description": None,
        "homepage": "https://patreon.com/exemplo",
        "has_issues": True,
        "has_wiki": True,
        "has_projects": True,
        "has_discussions": False,
    },
    "topics": [],
    "repos_extras": {"Hefesto-Team/hefesto-dualsense4unix": "R_h", "Hefesto-Team/Forja": "R_f"},
    "alertas": False,
    "fixes": False,
    "relato": False,
    "pages": False,
    "sponsor": True,
    "análise": {
        "secret_scanning": "disabled",
        "secret_scanning_push_protection": "disabled",
    },
    "colaboradores": {},
    "rulesets": [],
    "prox": 0,
    "negar": {},
}


class Mentira:
    def __init__(self, pasta: Path) -> None:
        self.estado_arq = pasta / "estado.json"
        self.log = pasta / "chamadas.jsonl"
        self.log.write_text("")
        self.estado_arq.write_text(json.dumps(ESTADO_INICIAL))

    @property
    def estado(self) -> dict[str, Any]:
        return json.loads(self.estado_arq.read_text())  # type: ignore[no-any-return]

    def mudar(self, **campos: Any) -> None:
        e = self.estado
        e.update(campos)
        self.estado_arq.write_text(json.dumps(e))

    def chamadas(self) -> list[dict[str, Any]]:
        return [json.loads(x) for x in self.log.read_text().splitlines()]

    def escritas(self) -> list[dict[str, Any]]:
        return [c for c in self.chamadas() if c["escrita"]]

    def zerar_log(self) -> None:
        self.log.write_text("")


@pytest.fixture
def gh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mentira:
    pasta = tmp_path / "mentira"
    (pasta / "bin").mkdir(parents=True)
    exe = pasta / "bin" / "gh"
    corpo = GH_DE_MENTIRA.read_text(encoding="utf-8").split("\n", 1)[1]
    exe.write_text(f"#!{sys.executable}\n{corpo}", encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    m = Mentira(pasta)
    monkeypatch.setenv("PATH", f"{pasta / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GH_MENTIRA_ESTADO", str(m.estado_arq))
    monkeypatch.setenv("GH_MENTIRA_LOG", str(m.log))
    return m


def rodar(*args: str, arquivo: Path = ARQUIVO) -> int:
    return int(aplicar.principal(["--repo", REPO, "--arquivo", str(arquivo), *args]))


def test_conferir_diz_a_diferenca_e_nao_escreve(gh: Mentira, capsys: Capsys) -> None:
    assert rodar("--conferir") == 1
    saida = capsys.readouterr().out.strip().splitlines()
    assert len(saida) == 1 and "diferença" in saida[0]
    assert gh.escritas() == []
    assert gh.estado["rulesets"] == [] and gh.estado["alertas"] is False


def test_aplicar_deixa_o_repositorio_como_o_arquivo_diz(gh: Mentira) -> None:
    assert rodar("--aplicar") == 0
    e, d = gh.estado, _dados()
    assert e["repo"]["description"] == d["about"]["descrição"]
    assert e["repo"]["homepage"] == d["about"]["site"]
    assert sorted(e["topics"]) == sorted(d["about"]["topicos"])
    assert (e["repo"]["has_issues"], e["repo"]["has_wiki"], e["repo"]["has_projects"],
            e["repo"]["has_discussions"], e["sponsor"]) == (True, True, True, True, False)
    assert (e["alertas"], e["fixes"], e["relato"]) == (True, False, True), "o Dependabot fica só no alerta"
    assert set(e["análise"].values()) == {"enabled"}
    assert e["colaboradores"] == {aplicar.CONTA_DA_CASA: "admin", "AndreBFarias": "admin"}
    assert [r["name"] for r in e["rulesets"]] == [r["nome"] for r in d["rulesets"]]
    porta = next(r for r in e["rulesets"] if any(x["type"] == "pull_request" for x in r["rules"]))
    tipos = {x["type"] for x in porta["rules"]}
    assert tipos == {"pull_request", "required_status_checks", "required_linear_history"}
    contextos_ = [c["context"] for x in porta["rules"] if x["type"] == "required_status_checks"
                  for c in x["parameters"]["required_status_checks"]]
    assert "autoria" in contextos_
    # O `.mailmap` é lido do topo do PR, e o próprio PR pode acrescentar quem o fez: a aprovação
    # só vale depois do último push, e um push novo a derruba.
    revisao = next(x["parameters"] for x in porta["rules"] if x["type"] == "pull_request")
    assert revisao["require_last_push_approval"] is True
    assert revisao["dismiss_stale_reviews_on_push"] is True
    assert revisao["required_approving_review_count"] >= 1
    assert porta["bypass_actors"] == [
        {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]
    historia = next(r for r in e["rulesets"] if r["name"].startswith("A história"))
    assert {x["type"] for x in historia["rules"]} == {
        "deletion", "non_fast_forward", "required_signatures"}
    assert historia["bypass_actors"] == []
    versoes = next(r for r in e["rulesets"] if r["target"] == "tag")
    assert {x["type"] for x in versoes["rules"]} == {"deletion", "non_fast_forward", "update"}
    assert versoes["conditions"]["ref_name"]["include"] == ["refs/tags/v*"]


def test_rodar_de_novo_nao_muda_nada(gh: Mentira) -> None:
    assert rodar("--aplicar") == 0
    antes = gh.estado
    gh.zerar_log()
    assert rodar("--conferir") == 0
    assert rodar("--aplicar") == 0
    assert gh.escritas() == []
    assert gh.estado == antes


def test_a_deriva_volta_ao_arquivo(gh: Mentira) -> None:
    assert rodar("--aplicar") == 0
    e = gh.estado
    e["repo"]["description"] = "mudada na interface"
    e["rulesets"][1]["rules"] = [
        x for x in e["rulesets"][1]["rules"] if x["type"] != "required_status_checks"]
    e["relato"] = False
    e["colaboradores"].pop("AndreBFarias")
    gh.estado_arq.write_text(json.dumps(e))
    gh.zerar_log()
    assert rodar("--conferir") == 1
    assert gh.escritas() == []
    assert rodar("--aplicar") == 0
    assert rodar("--conferir") == 0
    depois = gh.estado
    assert depois["repo"]["description"] == _dados()["about"]["descrição"]
    assert depois["relato"] is True and depois["colaboradores"]["AndreBFarias"] == "admin"
    assert any(x["type"] == "required_status_checks" for x in depois["rulesets"][1]["rules"])


def _porta(e: dict[str, Any]) -> dict[str, Any]:
    return next(r for r in e["rulesets"] if any(x["type"] == "pull_request" for x in r["rules"]))


def _aprovacoes_a_zero(e: dict[str, Any]) -> None:
    for x in _porta(e)["rules"]:
        if x["type"] == "pull_request":
            x["parameters"]["required_approving_review_count"] = 0


def _check_renomeado(e: dict[str, Any]) -> None:
    for x in _porta(e)["rules"]:
        if x["type"] == "required_status_checks":
            x["parameters"]["required_status_checks"][0]["context"] = "outro"


@pytest.mark.parametrize(
    "deriva",
    [
        _aprovacoes_a_zero,
        _check_renomeado,
        lambda e: _porta(e).update(bypass_actors=[]),
        lambda e: _porta(e).update(enforcement="evaluate"),
        lambda e: _porta(e)["conditions"]["ref_name"].update(include=["refs/heads/dev"]),
    ],
)
def test_a_deriva_de_valor_do_ruleset_volta_ao_arquivo(gh: Mentira, deriva: Any) -> None:
    assert rodar("--aplicar") == 0
    e = gh.estado
    deriva(e)
    gh.estado_arq.write_text(json.dumps(e))
    assert rodar("--conferir") == 1
    assert rodar("--aplicar") == 0
    assert rodar("--conferir") == 0


def test_o_que_o_servidor_acrescenta_nao_e_deriva(gh: Mentira) -> None:
    assert rodar("--aplicar") == 0
    e = gh.estado
    # o servidor devolve campos que nunca mandamos; e o campo mandado tem de ser lido de volta
    assert "allowed_merge_methods" in json.dumps(e["rulesets"])
    assert rodar("--conferir") == 0


def test_o_ruleset_homonimo_da_organizacao_nao_se_confunde_com_o_nosso(gh: Mentira) -> None:
    # A lista da API traz os da organização junto, por padrão; o id deles não se edita pelo
    # repositório. O aplicador lê só os do repositório.
    nome = _dados()["rulesets"][0]["nome"]
    gh.mudar(rulesets_da_org=[{"id": 900, "name": nome, "target": "branch", "enforcement": "active",
                               "source_type": "Organization", "source": "Hefesto-Team"}])
    assert rodar("--aplicar") == 0
    assert [r["name"] for r in gh.estado["rulesets"]] == [r["nome"] for r in _dados()["rulesets"]]
    assert rodar("--conferir") == 0


def test_a_ordem_da_seguranca_no_arquivo_nao_muda_o_resultado(
    gh: Mentira, tmp_path: Path
) -> None:
    # As atualizações de segurança só ligam depois dos alertas; o arquivo pode listar ao contrário.
    dados = _dados()
    dados["seguranca"]["atualizacoes_de_seguranca"] = True
    dados["seguranca"] = dict(reversed(list(dados["seguranca"].items())))
    invertido = tmp_path / "invertido.yml"
    invertido.write_text(
        yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8")
    primeira = next(iter(yaml.safe_load(invertido.read_text())["seguranca"]))
    assert primeira == "releases_imutaveis"
    assert rodar("--aplicar", arquivo=invertido) == 0
    assert (gh.estado["alertas"], gh.estado["fixes"]) == (True, True)


def test_a_guarda_recusa_conta_errada_e_nao_escreve(gh: Mentira, capsys: Capsys) -> None:
    gh.mudar(user="outra-conta")
    assert rodar("--aplicar") == 2
    assert "recusado" in capsys.readouterr().out
    assert gh.escritas() == []
    # o conferir só lê: não precisa da guarda
    assert rodar("--conferir") == 1


def test_a_guarda_recusa_dono_de_fora(gh: Mentira, capsys: Capsys) -> None:
    gh.mudar(slug="outra-organizacao/ensaio")
    codigo = aplicar.principal(["--repo", "outra-organizacao/ensaio", "--aplicar"])
    assert codigo == 2 and "recusado" in capsys.readouterr().out
    assert gh.escritas() == []


def test_o_que_nao_se_mediu_nao_sai_como_verde(gh: Mentira, capsys: Capsys) -> None:
    gh.mudar(privado=True)  # o plano gratuito devolve 403 para ruleset
    assert rodar("--conferir") == 2
    assert "sem medida" in capsys.readouterr().out
    assert gh.escritas() == []


def test_sem_rulesets_deixa_os_rulesets_para_depois_do_push(gh: Mentira) -> None:
    assert rodar("--aplicar", "--sem", "rulesets") == 0
    assert all("rulesets" not in c["p"] for c in gh.chamadas())
    assert gh.estado["rulesets"] == []
    assert rodar("--conferir") == 1  # o todo ainda tem diferença
    assert rodar("--aplicar") == 0
    assert len(gh.estado["rulesets"]) == 3


def test_falha_de_escrita_aparece_e_nao_vira_verde(gh: Mentira, capsys: Capsys) -> None:
    gh.mudar(negar={"PUT repos/Hefesto-Team/ensaio/private-vulnerability-reporting": 422})
    assert rodar("--aplicar") == 1
    assert "sobram" in capsys.readouterr().out
    assert gh.estado["relato"] is False and gh.estado["alertas"] is True


def test_o_arquivo_estragado_nao_chega_ao_servidor(gh: Mentira, tmp_path: Path) -> None:
    dados = _dados()
    del dados["funções"]["sponsor"]["depois"]
    ruim = tmp_path / "ruim.yml"
    ruim.write_text(yaml.safe_dump(dados, allow_unicode=True), encoding="utf-8")
    assert rodar("--aplicar", arquivo=ruim) == 2
    assert gh.chamadas() == []


def test_o_resumo_e_uma_linha_e_o_detalhe_vai_para_o_arquivo(
    gh: Mentira, tmp_path: Path, capsys: Capsys
) -> None:
    detalhe = tmp_path / "detalhe.txt"
    assert rodar("--conferir", "--detalhe", str(detalhe)) == 1
    resumo = capsys.readouterr()
    assert len(resumo.out.strip().splitlines()) == 1 and resumo.err == ""
    linhas = detalhe.read_text().splitlines()
    assert any(x.startswith("falta: rulesets") for x in linhas)
    assert any(x.startswith("falta: seguranca.") for x in linhas)


def test_o_script_roda_como_comando(gh: Mentira) -> None:
    r = subprocess.run(
        [sys.executable, str(APLICAR), "--repo", REPO, "--conferir"],
        capture_output=True, text=True, check=False, env=os.environ.copy())
    assert r.returncode == 1 and len(r.stdout.strip().splitlines()) == 1
    r = subprocess.run([sys.executable, str(APLICAR), "--repo", REPO],
                       capture_output=True, text=True, check=False, env=os.environ.copy())
    assert r.returncode == 2  # argparse: falta --conferir ou --aplicar
