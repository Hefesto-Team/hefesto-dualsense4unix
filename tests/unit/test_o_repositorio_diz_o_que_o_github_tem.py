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
import re
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


def _modulo(nome: str) -> Any:
    """Um script de `scripts/github/` carregado como módulo (eles não são um pacote)."""
    spec = importlib.util.spec_from_file_location(
        f"{nome}_do_github", RAIZ / "scripts" / "github" / f"{nome}.py"
    )
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[f"{nome}_do_github"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


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


def test_tudo_o_que_o_github_oferece_esta_ligado() -> None:
    funcoes = _dados()["funções"]
    assert all(
        funcoes[n]["ligada"] is True
        for n in ("issues", "wiki", "pages", "projects", "discussions", "sponsor")
    )
    # O botão Sponsor ligado mostra o que o FUNDING.yml lista: sem chave ativa, nada a mostrar.
    assert _yaml(GH_DIR / "FUNDING.yml"), "o botão Sponsor pede ao menos uma chave no FUNDING.yml"


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
    return [
        r["nome"]
        for r in dados["rulesets"]
        if r.get("historico_linear") and r.get("excecao") is None
    ]


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
        lambda d: d["funções"]["wiki"].update(ligada=False),
        lambda d: d["funções"].pop("sponsor"),
        lambda d: d["seguranca"]["releases_imutaveis"].pop("depois"),
        lambda d: d["seguranca"].pop("linguagens_da_varredura"),
        lambda d: d["seguranca"].update(grafo_de_dependencias=False),
        lambda d: d["rotulos"]["lista"][0].update(cor="#d73a4a"),
        lambda d: d["rotulos"]["lista"].append(dict(d["rotulos"]["lista"][0])),
        lambda d: d["ações"].update(aprovacao_de_fork="ninguem"),
        lambda d: d["ambientes"][0].update(revisores=[f"conta{i}" for i in range(7)]),
        lambda d: d["ambientes"][0].update(revisores="[REDACTED]"),
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
        casou = [
            c for c in combos if dims and all(c[k] == v for k, v in extra.items() if k in dims)
        ]
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
        "lint-test (3.10)",
        "lint-test (3.12)",
    ]
    # com `name` e sem a matriz nele, o GitHub acrescenta os valores do mesmo jeito
    com_nome = {"strategy": {"matrix": {"os": ["a"]}}}
    assert [_nome_do_check("Smoke", v) for v in _combinacoes(com_nome)] == ["Smoke (a)"]
    so_include = {"strategy": {"matrix": {"include": [{"distro": "fedora"}, {"distro": "arch"}]}}}
    assert [_nome_do_check("Smoke ${{ matrix.distro }}", v) for v in _combinacoes(so_include)] == [
        "Smoke fedora",
        "Smoke arch",
    ]


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
    arq.write_text(texto[:inicio] + texto[inicio:].replace(antes, depois, 1), encoding="utf-8")


def test_mordida_trocar_o_nome_do_job_reprova(copia_dos_workflows: Path) -> None:
    wf = copia_dos_workflows / ".github" / "workflows"
    assert checks_sem_job(_dados(), copia_dos_workflows) == []
    _trocar(wf / "autoria.yml", "\n  autoria:\n", "\n  autoria-nova:\n")
    assert any(f.startswith("autoria:") for f in checks_sem_job(_dados(), copia_dos_workflows))


def test_mordida_tirar_uma_versao_da_matriz_reprova(copia_dos_workflows: Path) -> None:
    wf = copia_dos_workflows / ".github" / "workflows"
    _trocar(
        wf / "ci.yml",
        '["3.10", "3.11", "3.12"]',
        '["3.10", "3.11"]',
        a_partir_de="\n  lint-test:\n",
    )
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


_APLICADO: dict[str, Any] = {}


@pytest.fixture
def gh_aplicado(gh: Mentira) -> Mentira:
    """O repositório de mentira depois do `--aplicar` inteiro.

    A primeira aplicação da corrida é feita de verdade (e conferida); os testes de deriva partem
    de uma cópia dela em vez de repeti-la."""
    if not _APLICADO:
        assert rodar("--aplicar") == 0
        _APLICADO.update(gh.estado)
    gh.estado_arq.write_text(json.dumps(_APLICADO))
    gh.zerar_log()
    return gh


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
    assert (
        e["repo"]["has_issues"],
        e["repo"]["has_wiki"],
        e["repo"]["has_projects"],
        e["repo"]["has_discussions"],
        e["sponsor"],
    ) == (True, True, True, True, True)
    assert (e["alertas"], e["fixes"], e["relato"]) == (True, False, True), (
        "o Dependabot fica só no alerta"
    )
    assert set(e["análise"].values()) == {"enabled"}
    assert e["colaboradores"] == {aplicar.CONTA_DA_CASA: "admin", "AndreBFarias": "admin"}
    assert [r["name"] for r in e["rulesets"]] == [r["nome"] for r in d["rulesets"]]
    porta = next(r for r in e["rulesets"] if any(x["type"] == "pull_request" for x in r["rules"]))
    tipos = {x["type"] for x in porta["rules"]}
    assert tipos == {"pull_request", "required_status_checks", "required_linear_history"}
    contextos_ = [
        c["context"]
        for x in porta["rules"]
        if x["type"] == "required_status_checks"
        for c in x["parameters"]["required_status_checks"]
    ]
    assert "autoria" in contextos_
    # O `.mailmap` é lido do topo do PR, e o próprio PR pode acrescentar quem o fez: a aprovação
    # só vale depois do último push, e um push novo a derruba.
    revisao = next(x["parameters"] for x in porta["rules"] if x["type"] == "pull_request")
    assert revisao["require_last_push_approval"] is True
    assert revisao["dismiss_stale_reviews_on_push"] is True
    assert revisao["required_approving_review_count"] >= 1
    assert porta["bypass_actors"] == [
        {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
    ]
    historia = next(r for r in e["rulesets"] if r["name"].startswith("A história"))
    assert {x["type"] for x in historia["rules"]} == {
        "deletion",
        "non_fast_forward",
        "required_signatures",
    }
    assert historia["bypass_actors"] == []
    versoes = next(r for r in e["rulesets"] if r["target"] == "tag")
    assert {x["type"] for x in versoes["rules"]} == {"deletion", "non_fast_forward", "update"}
    assert versoes["conditions"]["ref_name"]["include"] == ["refs/tags/v*"]


def test_rodar_de_novo_nao_muda_nada(gh_aplicado: Mentira) -> None:
    antes = gh_aplicado.estado
    gh_aplicado.zerar_log()
    assert rodar("--conferir") == 0
    assert rodar("--aplicar") == 0
    assert gh_aplicado.escritas() == []
    assert gh_aplicado.estado == antes


def test_a_deriva_volta_ao_arquivo(gh_aplicado: Mentira) -> None:
    e = gh_aplicado.estado
    e["repo"]["description"] = "mudada na interface"
    e["rulesets"][1]["rules"] = [
        x for x in e["rulesets"][1]["rules"] if x["type"] != "required_status_checks"
    ]
    e["relato"] = False
    e["colaboradores"].pop("AndreBFarias")
    gh_aplicado.estado_arq.write_text(json.dumps(e))
    gh_aplicado.zerar_log()
    assert rodar("--conferir") == 1
    assert gh_aplicado.escritas() == []
    assert rodar("--aplicar") == 0
    assert rodar("--conferir") == 0
    depois = gh_aplicado.estado
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
def test_a_deriva_de_valor_do_ruleset_volta_ao_arquivo(gh_aplicado: Mentira, deriva: Any) -> None:
    e = gh_aplicado.estado
    deriva(e)
    gh_aplicado.estado_arq.write_text(json.dumps(e))
    assert rodar("--conferir") == 1
    assert rodar("--aplicar") == 0
    assert rodar("--conferir") == 0


def test_o_que_o_servidor_acrescenta_nao_e_deriva(gh_aplicado: Mentira) -> None:
    e = gh_aplicado.estado
    # o servidor devolve campos que nunca mandamos; e o campo mandado tem de ser lido de volta
    assert "allowed_merge_methods" in json.dumps(e["rulesets"])
    assert rodar("--conferir") == 0


def test_o_ruleset_homonimo_da_organizacao_nao_se_confunde_com_o_nosso(gh: Mentira) -> None:
    # A lista da API traz os da organização junto, por padrão; o id deles não se edita pelo
    # repositório. O aplicador lê só os do repositório.
    nome = _dados()["rulesets"][0]["nome"]
    gh.mudar(
        rulesets_da_org=[
            {
                "id": 900,
                "name": nome,
                "target": "branch",
                "enforcement": "active",
                "source_type": "Organization",
                "source": "Hefesto-Team",
            }
        ]
    )
    assert rodar("--aplicar") == 0
    assert [r["name"] for r in gh.estado["rulesets"]] == [r["nome"] for r in _dados()["rulesets"]]
    assert rodar("--conferir") == 0


def test_a_ordem_da_seguranca_no_arquivo_nao_muda_o_resultado(gh: Mentira, tmp_path: Path) -> None:
    # As atualizações de segurança só ligam depois dos alertas; o arquivo pode listar ao contrário.
    dados = _dados()
    dados["seguranca"]["atualizacoes_de_seguranca"] = True
    dados["seguranca"] = dict(reversed(list(dados["seguranca"].items())))
    invertido = tmp_path / "invertido.yml"
    invertido.write_text(
        yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
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
    dados["funções"]["wiki"]["ligada"] = False  # desligada sem `depois`
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
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    assert r.returncode == 1 and len(r.stdout.strip().splitlines()) == 1
    r = subprocess.run(
        [sys.executable, str(APLICAR), "--repo", REPO],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    assert r.returncode == 2  # argparse: falta --conferir ou --aplicar


# ---------------------------------------------------------------------------
# 4. Cada grupo que o arquivo declara, contra o `gh` de mentira
# ---------------------------------------------------------------------------


def _arquivo(tmp_path: Path, ajusta: Any) -> Path:
    """Uma variação do arquivo do repositório, para o cenário que o teste precisa."""
    dados = _dados()
    ajusta(dados)
    caminho = tmp_path / "variacao.yml"
    caminho.write_text(yaml.safe_dump(dados, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return caminho


def _gravar(gh: Mentira, estado: dict[str, Any]) -> None:
    gh.estado_arq.write_text(json.dumps(estado))


def _detalhe(tmp_path: Path, *args: str) -> tuple[int, str]:
    arq = tmp_path / "detalhe-lido.txt"
    codigo = rodar(*args, "--detalhe", str(arq))
    return codigo, arq.read_text(encoding="utf-8")


def test_a_mesclagem_chega_ao_repositorio_e_a_deriva_volta(gh: Mentira) -> None:
    assert rodar("--aplicar", "--so", "configuração") == 0
    r = gh.estado["repo"]
    assert (
        r["allow_merge_commit"],
        r.get("allow_squash_merge", True),
        r.get("allow_rebase_merge", True),
        r["delete_branch_on_merge"],
        r["allow_update_branch"],
    ) == (False, True, True, True, True)
    e = gh.estado
    e["repo"]["allow_merge_commit"] = True
    _gravar(gh, e)
    assert rodar("--conferir", "--so", "configuração") == 1
    assert (
        rodar("--aplicar", "--so", "configuração") == 0
        and rodar("--conferir", "--so", "configuração") == 0
    )
    assert gh.estado["repo"]["allow_merge_commit"] is False


def test_as_pages_saem_do_fluxo_e_a_deriva_volta(gh: Mentira) -> None:
    assert rodar("--aplicar", "--so", "funções") == 0
    assert gh.estado["pages"] is True and gh.estado["pages_tipo"] == "workflow"
    gh.mudar(pages_tipo="legacy")
    assert rodar("--conferir", "--so", "funções") == 1
    assert rodar("--aplicar", "--so", "funções") == 0 and gh.estado["pages_tipo"] == "workflow"


def test_o_fluxo_do_actions_so_le_e_o_pr_de_fora_espera_aprovacao(gh: Mentira) -> None:
    assert rodar("--aplicar", "--so", "ações") == 0
    e = gh.estado
    assert e["fluxo"] == {
        "default_workflow_permissions": "read",
        "can_approve_pull_request_reviews": False,
    }
    assert e["fork"] == "all_external_contributors"
    gh.mudar(
        fluxo={"default_workflow_permissions": "write", "can_approve_pull_request_reviews": True}
    )
    assert rodar("--conferir", "--so", "ações") == 1
    assert rodar("--aplicar", "--so", "ações") == 0
    assert gh.estado["fluxo"]["default_workflow_permissions"] == "read"


def test_a_varredura_de_codigo_liga_com_as_linguagens_e_a_deriva_volta(gh: Mentira) -> None:
    assert rodar("--aplicar", "--so", "seguranca") == 0
    v = gh.estado["varredura"]
    assert v["state"] == "configured" and sorted(v["languages"]) == ["actions", "python"]
    assert v["query_suite"] == "default"
    gh.mudar(varredura={"state": "configured", "languages": ["python"], "query_suite": "default"})
    assert rodar("--conferir", "--so", "seguranca") == 1
    assert rodar("--aplicar", "--so", "seguranca") == 0 and sorted(
        gh.estado["varredura"]["languages"]
    ) == ["actions", "python"]


def test_o_grafo_de_dependencias_que_o_github_nao_liga_por_api_so_se_mede(
    gh: Mentira, tmp_path: Path
) -> None:
    assert rodar("--aplicar") == 0
    gh.mudar(grafo=False)
    gh.zerar_log()
    assert rodar("--conferir") == 1
    codigo, detalhe = _detalhe(tmp_path, "--aplicar")
    assert codigo == 1 and "à mão" in detalhe and "grafo_de_dependencias" in detalhe
    assert "feito: seguranca.grafo" not in detalhe, "o que não se fez não vira «feito»"
    assert gh.escritas() == [], "o que só se mede não pode virar escrita"


def test_a_release_imutavel_liga_e_desliga_pelo_arquivo(gh: Mentira, tmp_path: Path) -> None:
    ligada = _arquivo(tmp_path, lambda d: d["seguranca"].update(releases_imutaveis=True))
    assert (
        rodar("--aplicar", "--so", "seguranca", arquivo=ligada) == 0
        and gh.estado["imutaveis"] is True
    )
    assert (
        rodar("--conferir", "--so", "seguranca") == 1
    )  # o arquivo do repositório a quer desligada
    assert rodar("--aplicar", "--so", "seguranca") == 0 and gh.estado["imutaveis"] is False


def test_os_rotulos_chegam_inteiros_e_a_deriva_volta(gh: Mentira) -> None:
    assert rodar("--aplicar", "--so", "rotulos") == 0
    quer = {r["nome"]: r for r in _dados()["rotulos"]["lista"]}
    reais = {x["name"]: x for x in gh.estado["labels"]}
    assert set(quer) == set(reais)
    tela = reais["área: tela"]
    assert (tela["color"], tela["description"]) == ("c5def5", quer["área: tela"]["descrição"])
    e = gh.estado
    for x in e["labels"]:
        if x["name"] == "área: tela":
            x["color"], x["description"] = "000000", "outra"
    _gravar(gh, e)
    assert rodar("--conferir", "--so", "rotulos") == 1
    assert (
        rodar("--aplicar", "--so", "rotulos") == 0 and rodar("--conferir", "--so", "rotulos") == 0
    )
    assert {x["name"]: x["color"] for x in gh.estado["labels"]}["área: tela"] == "c5def5"


def test_o_rotulo_com_outra_caixa_e_renomeado_e_o_que_nao_esta_no_arquivo_fica(gh: Mentira) -> None:
    gh.mudar(
        labels=[
            {"id": 1, "name": "Bug", "color": "D73A4A", "description": None},
            {"id": 2, "name": "estranho", "color": "ffffff", "description": None},
        ]
    )
    assert rodar("--aplicar", "--so", "rotulos") == 0
    nomes = [x["name"] for x in gh.estado["labels"]]
    assert "bug" in nomes and "Bug" not in nomes
    assert "estranho" in nomes, "apagar rótulo o solta das issues: só com `exclusivos: true`"


def test_o_rotulo_com_barra_e_interrogacao_no_nome_chega_inteiro_e_se_corrige(
    gh: Mentira, tmp_path: Path
) -> None:
    nomes = ["build / ci", "o que é isto?", "50% pronto #3"]
    arq = _arquivo(
        tmp_path,
        lambda d: d["rotulos"]["lista"].extend(
            {"nome": n, "cor": "ededed", "descrição": "um rótulo difícil"} for n in nomes
        ),
    )
    assert rodar("--aplicar", "--so", "rotulos", arquivo=arq) == 0
    assert set(nomes) <= {x["name"] for x in gh.estado["labels"]}
    e = gh.estado
    for x in e["labels"]:
        if x["name"] in nomes:
            x["description"] = "outra"
    _gravar(gh, e)
    assert rodar("--conferir", "--so", "rotulos", arquivo=arq) == 1
    assert rodar("--aplicar", "--so", "rotulos", arquivo=arq) == 0
    assert rodar("--conferir", "--so", "rotulos", arquivo=arq) == 0


def test_rotulos_exclusivos_apagam_o_que_nao_esta_no_arquivo(gh: Mentira, tmp_path: Path) -> None:
    arq = _arquivo(tmp_path, lambda d: d["rotulos"].update(exclusivos=True))
    gh.mudar(labels=[{"id": 2, "name": "estranho", "color": "ffffff", "description": None}])
    assert rodar("--conferir", "--so", "rotulos", arquivo=arq) == 1
    assert rodar("--aplicar", "--so", "rotulos", arquivo=arq) == 0
    assert "estranho" not in [x["name"] for x in gh.estado["labels"]]


def test_os_marcos_chegam_e_a_deriva_volta(gh: Mentira) -> None:
    assert rodar("--aplicar", "--so", "milestones") == 0
    quer = _dados()["milestones"]
    assert [m["title"] for m in gh.estado["milestones"]] == [m["titulo"] for m in quer]
    e = gh.estado
    e["milestones"][0]["description"] = "outra coisa"
    _gravar(gh, e)
    assert rodar("--conferir", "--so", "milestones") == 1
    assert (
        rodar("--aplicar", "--so", "milestones") == 0
        and rodar("--conferir", "--so", "milestones") == 0
    )


def test_a_data_do_marco_chega_ao_servidor(gh: Mentira, tmp_path: Path) -> None:
    arq = _arquivo(tmp_path, lambda d: d["milestones"][0].update(data="2026-12-31"))
    assert rodar("--aplicar", "--so", "milestones", arquivo=arq) == 0
    assert gh.estado["milestones"][0]["due_on"].startswith("2026-12-31")
    assert rodar("--conferir", "--so", "milestones", arquivo=arq) == 0


def test_os_tipos_de_issue_chegam_e_o_que_ja_existia_e_acertado(gh: Mentira) -> None:
    gh.mudar(
        tipos=[
            {"id": 1, "name": "Bug", "description": "velha", "color": "gray", "is_enabled": True}
        ]
    )
    assert rodar("--aplicar", "--so", "tipos_de_issue") == 0
    por = {t["name"]: t for t in gh.estado["tipos"]}
    assert set(por) == {t["nome"] for t in _dados()["tipos_de_issue"]}
    assert por["Bug"]["color"] == "red" and por["Bug"]["description"] != "velha"
    assert rodar("--conferir", "--so", "tipos_de_issue") == 0


@pytest.mark.parametrize("grupo", ["tipos_de_issue", "equipes", "projetos"])
def test_o_que_so_existe_em_organizacao_nao_se_mede_em_conta_pessoal(
    gh: Mentira, grupo: str, capsys: Capsys
) -> None:
    gh.mudar(organizacoes=[])
    assert rodar("--conferir", "--so", grupo) == 2
    assert "sem medida" in capsys.readouterr().out
    assert gh.escritas() == []


def test_a_equipe_nasce_com_os_membros_e_o_acesso(gh: Mentira) -> None:
    assert rodar("--aplicar", "--so", "equipes") == 0
    e = gh.estado["equipes"]["mantenedores"]
    assert {k: v["role"] for k, v in e["membros"].items()} == {
        aplicar.CONTA_DA_CASA: "maintainer",
        "AndreBFarias": "maintainer",
    }
    assert e["repos"] == {REPO: "maintain"}
    assert rodar("--conferir", "--so", "equipes") == 0


def test_o_convite_pendente_nao_conta_como_membro(gh: Mentira, tmp_path: Path) -> None:
    gh.mudar(membros_da_org=[aplicar.CONTA_DA_CASA])
    codigo, detalhe = _detalhe(tmp_path, "--aplicar", "--so", "equipes")
    assert codigo == 1, "quem ainda não aceitou o convite não é da equipe"
    assert "AndreBFarias" in detalhe


def test_os_ambientes_chegam_com_revisores_e_so_implantam_de_tag(gh: Mentira) -> None:
    assert rodar("--aplicar", "--so", "ambientes") == 0
    for nome in ("pypi", "release"):
        env = gh.estado["ambientes"][nome]
        assert sorted(env["revisores"]) == sorted([aplicar.CONTA_DA_CASA, "AndreBFarias"])
        assert [(p["name"], p["type"]) for p in env["políticas"]] == [("v*", "tag")]
        assert env["política"] == {"protected_branches": False, "custom_branch_policies": True}
    assert rodar("--conferir", "--so", "ambientes") == 0


def test_a_pagina_publica_do_main_e_a_regra_do_ramo_padrao_sai(gh: Mentira) -> None:
    # O GitHub cria o `github-pages` com a regra do ramo padrão (o `dev`) quando as Pages ligam
    # por fluxo; o `paginas.yml` publica do `main`, e com a regra de fábrica seria recusado.
    assert rodar("--aplicar", "--so", "funções") == 0
    criado = gh.estado["ambientes"]["github-pages"]
    assert [(p["name"], p["type"]) for p in criado["políticas"]] == [("dev", "branch")]
    assert rodar("--conferir", "--so", "ambientes") == 1
    assert rodar("--aplicar", "--so", "ambientes") == 0
    env = gh.estado["ambientes"]["github-pages"]
    assert [(p["name"], p["type"]) for p in env["políticas"]] == [("main", "branch")]
    assert env["revisores"] == [], "a página publica sem esperar aprovação"
    assert rodar("--conferir", "--so", "ambientes") == 0
    publicar = _workflow("paginas.yml")["jobs"]["publicar"]
    ramos = _gatilhos(_workflow("paginas.yml"))["push"]["branches"]
    quer = next(a for a in _dados()["ambientes"] if a["nome"] == publicar["environment"]["name"])
    assert quer["ramos"] == ramos, "o ambiente da página aceita o ramo de que o fluxo publica"


def _uma_regra_a_mais(e: dict[str, Any]) -> None:
    e["ambientes"]["pypi"]["políticas"].append({"id": 999, "name": "dev", "type": "branch"})


def _sem_um_revisor(e: dict[str, Any]) -> None:
    e["ambientes"]["pypi"]["revisores"].pop()


def _sem_a_regra_da_tag(e: dict[str, Any]) -> None:
    e["ambientes"]["release"]["políticas"] = []


def _qualquer_ramo(e: dict[str, Any]) -> None:
    e["ambientes"]["pypi"]["política"] = {
        "protected_branches": True,
        "custom_branch_policies": False,
    }


@pytest.mark.parametrize(
    "deriva", [_sem_um_revisor, _sem_a_regra_da_tag, _qualquer_ramo, _uma_regra_a_mais])
def test_a_deriva_do_ambiente_volta_ao_arquivo(gh: Mentira, deriva: Any) -> None:
    assert rodar("--aplicar", "--so", "ambientes") == 0
    e = gh.estado
    deriva(e)
    _gravar(gh, e)
    assert rodar("--conferir", "--so", "ambientes") == 1
    assert (
        rodar("--aplicar", "--so", "ambientes") == 0
        and rodar("--conferir", "--so", "ambientes") == 0
    )


def test_a_categoria_de_discussao_que_falta_so_se_mede(gh: Mentira, tmp_path: Path) -> None:
    assert rodar("--aplicar", "--so", "discussoes") == 0
    e = gh.estado
    e["categorias"] = [c for c in e["categorias"] if c["slug"] != "q-a"]
    _gravar(gh, e)
    gh.zerar_log()
    assert rodar("--conferir", "--so", "discussoes") == 1
    codigo, detalhe = _detalhe(tmp_path, "--aplicar", "--so", "discussoes")
    assert codigo == 1 and "q-a" in detalhe and "à mão" in detalhe
    assert "feito: discussoes" not in detalhe, "o que não se fez não vira «feito»"
    assert gh.escritas() == [], "a API do GitHub não cria categoria: nada a escrever"


def test_a_categoria_que_deixa_de_aceitar_resposta_aparece(gh: Mentira) -> None:
    assert rodar("--aplicar", "--so", "discussoes") == 0
    e = gh.estado
    for c in e["categorias"]:
        if c["slug"] == "q-a":
            c["isAnswerable"] = False
    _gravar(gh, e)
    assert rodar("--conferir", "--so", "discussoes") == 1


def _roteiro(gh: Mentira) -> dict[str, Any]:
    return gh.estado["projetos"][0]  # type: ignore[no-any-return]


def test_o_roteiro_nasce_inteiro_ligado_aos_dois_repositorios(gh: Mentira) -> None:
    assert rodar("--aplicar", "--so", "projetos") == 0
    p, quer = _roteiro(gh), _dados()["projetos"][0]
    assert (p["title"], p["public"], p["desc"]) == (quer["título"], True, quer["descrição"])
    assert sorted(p["repos"]) == sorted(quer["ligado_a"])
    status = next(c for c in p["campos"] if c["name"] == "Status")
    assert [(o["name"], o["color"]) for o in status["options"]] == [
        (e["nome"], e["cor"]) for e in quer["etapas"]
    ]
    assert [v["name"] for v in p["vistas"]] == [v["nome"] for v in quer["vistas"]]
    ids = {c["name"]: c["databaseId"] for c in p["campos"]}
    por_versao = next(v for v in p["vistas"] if v["name"] == "Por versão")
    assert por_versao["group_by"] == [ids["Milestone"]]
    bugs = next(v for v in p["vistas"] if v["name"] == "Bugs por área")
    assert (bugs["filter"], bugs["group_by"], bugs["layout"]) == (
        "label:bug",
        [ids["Labels"]],
        "TABLE_LAYOUT",
    )


def test_o_roteiro_aplicado_de_novo_nao_escreve(gh: Mentira) -> None:
    assert rodar("--aplicar", "--so", "projetos") == 0
    antes = gh.estado["projetos"]
    gh.zerar_log()
    assert rodar("--aplicar", "--so", "projetos") == 0
    assert gh.escritas() == [] and gh.estado["projetos"] == antes


def _repo_desligado(p: dict[str, Any]) -> None:
    p["repos"].remove("Hefesto-Team/Forja")


def _etapas_do_github(p: dict[str, Any]) -> None:
    next(c for c in p["campos"] if c["name"] == "Status")["options"] = [
        {"id": "a", "name": "Todo", "color": "GREEN", "description": ""}
    ]


def _vista_apagada(p: dict[str, Any]) -> None:
    p["vistas"] = [v for v in p["vistas"] if v["name"] != "Por versão"]


def _projeto_privado(p: dict[str, Any]) -> None:
    p["public"] = False


@pytest.mark.parametrize(
    "deriva", [_repo_desligado, _etapas_do_github, _vista_apagada, _projeto_privado]
)
def test_a_deriva_do_roteiro_volta_ao_arquivo(gh: Mentira, deriva: Any) -> None:
    assert rodar("--aplicar", "--so", "projetos") == 0
    e = gh.estado
    deriva(e["projetos"][0])
    _gravar(gh, e)
    assert rodar("--conferir", "--so", "projetos") == 1
    assert (
        rodar("--aplicar", "--so", "projetos") == 0 and rodar("--conferir", "--so", "projetos") == 0
    )


def test_a_vista_com_o_filtro_trocado_so_se_mede(gh: Mentira, tmp_path: Path) -> None:
    assert rodar("--aplicar", "--so", "projetos") == 0
    e = gh.estado
    next(v for v in e["projetos"][0]["vistas"] if v["name"] == "Bugs por área")["filter"] = (
        "is:closed"
    )
    _gravar(gh, e)
    gh.zerar_log()
    codigo, detalhe = _detalhe(tmp_path, "--aplicar", "--so", "projetos")
    assert codigo == 1 and "Bugs por área" in detalhe and "à mão" in detalhe
    assert gh.escritas() == [], "a API não edita vista: recriar apagando é decisão de quem mantém"


def test_a_saude_da_comunidade_se_mede_e_nao_se_aplica(gh: Mentira, tmp_path: Path) -> None:
    assert rodar("--aplicar", "--so", "about,comunidade") == 0
    e = gh.estado
    e["arquivos_da_comunidade"]["contributing"] = False
    _gravar(gh, e)
    gh.zerar_log()
    codigo, detalhe = _detalhe(tmp_path, "--aplicar", "--so", "comunidade")
    assert codigo == 1 and "contributing" in detalhe
    assert gh.escritas() == []


def test_o_arquivo_de_um_repositorio_so_com_o_minimo_continua_valendo() -> None:
    minimo = {
        k: v
        for k, v in _dados().items()
        if k in ("versão", "about", "funções", "seguranca", "mantenedores", "rulesets")
    }
    minimo["seguranca"].pop("linguagens_da_varredura", None)
    for n in aplicar.SEGURANCA_OPCIONAL:
        minimo["seguranca"].pop(n, None)
    assert aplicar.validar(minimo) == [], "cada grupo novo é opcional: o arquivo antigo não quebra"


# ---------------------------------------------------------------------------
# 5. Os rulesets que o arquivo ganhou: a assinatura e as tags
# ---------------------------------------------------------------------------


def assinatura_anulada_por_excecao(dados: dict[str, Any]) -> list[str]:
    """Os rulesets que exigem assinatura e deixam alguém de fora dela.

    A exceção de administrador anula a regra para quem mais empurra commit direto no `dev`: a
    assinatura exigida morreria no primeiro push de quem mantém.
    """
    return [r["nome"] for r in dados["rulesets"] if r.get("assinatura") and r.get("excecao")]


def test_a_assinatura_exigida_mora_na_regra_sem_excecao_e_cobre_o_dev_e_o_main() -> None:
    dados = _dados()
    assert assinatura_anulada_por_excecao(dados) == []
    exigem = [r for r in dados["rulesets"] if r.get("assinatura") == "exigida"]
    assert len(exigem) == 1 and sorted(exigem[0]["ramos"]) == ["dev", "main"]


def test_mordida_assinatura_na_regra_com_excecao_reprova() -> None:
    dados = _dados()
    porta = next(r for r in dados["rulesets"] if r.get("excecao"))
    porta["assinatura"] = "exigida"
    assert assinatura_anulada_por_excecao(dados) == [porta["nome"]]


def test_as_versoes_publicadas_nao_se_apagam_nem_se_movem() -> None:
    versoes = next(r for r in _dados()["rulesets"] if "tags" in r)
    assert versoes["tags"] == ["v*"] and "excecao" not in versoes
    tipos = {x["type"] for x in aplicar.corpo_do_ruleset(versoes)["rules"]}
    assert tipos == {"deletion", "non_fast_forward", "update"}
    assert aplicar.corpo_do_ruleset(versoes)["target"] == "tag"


def test_revisao_e_check_nao_valem_em_ruleset_de_tag() -> None:
    dados = _dados()
    versoes = next(r for r in dados["rulesets"] if "tags" in r)
    versoes["revisão"] = {"aprovacoes": 1}
    assert any("só vale para ramo" in e for e in aplicar.validar(dados))


def test_o_gh_de_mentira_recusa_o_que_o_servidor_recusa_no_ruleset_de_tag(
    gh: Mentira, tmp_path: Path
) -> None:
    corpo = aplicar.corpo_do_ruleset(next(r for r in _dados()["rulesets"] if "tags" in r))
    corpo["name"] = "x"
    corpo["rules"].append(
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [{"context": "a"}],
                "strict_required_status_checks_policy": False,
            },
        }
    )
    r = subprocess.run(
        ["gh", "api", "-i", "-X", "POST", f"repos/{REPO}/rulesets", "--input", "-"],
        input=json.dumps(corpo),
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    assert r.returncode != 0 and "422" in r.stdout
    assert "não vale num ruleset de tag" in json.loads(r.stdout.split("\n\n", 1)[1])["message"]
    corpo["rules"] = [{"type": "update"}]  # a regra `update` pede o parâmetro
    r = subprocess.run(
        ["gh", "api", "-i", "-X", "POST", f"repos/{REPO}/rulesets", "--input", "-"],
        input=json.dumps(corpo),
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    assert "422" in r.stdout and "update_allows_fetch_and_merge" in r.stdout


def test_o_de_fora_diz_o_motivo_de_cada_coisa_que_a_casa_nao_usa() -> None:
    de_fora = _dados()["de_fora"]
    assert set(de_fora) >= {
        "lfs",
        "merge_queue",
        "codespaces",
        "autolinks",
        "imagem_de_previa_social",
    }
    assert all(len(str(m)) >= 40 for m in de_fora.values()), "o motivo é medida, não uma palavra"
    dados = _dados()
    dados["de_fora"]["lfs"] = "  "
    assert any("de_fora.lfs" in e for e in aplicar.validar(dados))


# ---------------------------------------------------------------------------
# 6. Os arquivos do repositório e o que o arquivo declara
# ---------------------------------------------------------------------------

GH_DIR = RAIZ / ".github"
ISSUES = GH_DIR / "ISSUE_TEMPLATE"
TIPOS_DE_CAMPO = {"markdown", "textarea", "input", "dropdown", "checkboxes"}


def _yaml(caminho: Path) -> Any:
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))


def _formularios() -> list[Path]:
    return sorted(p for p in ISSUES.glob("*.yml") if p.name != "config.yml")


def _rotulos_declarados() -> set[str]:
    return {r["nome"] for r in _dados()["rotulos"]["lista"]}


def erros_do_formulario(f: dict[str, Any], rotulos: set[str], tipos: set[str]) -> list[str]:
    erros: list[str] = []
    for chave in ("name", "description", "body"):
        if not f.get(chave):
            erros.append(f"falta `{chave}`")
    erros += [
        f"rótulo «{r}» não está no repositorio.yml" for r in f.get("labels", []) if r not in rotulos
    ]
    if f.get("type") not in tipos:
        erros.append(f"tipo «{f.get('type')}» não está em tipos_de_issue")
    ids: list[str] = []
    for campo in f.get("body") or []:
        if campo.get("type") not in TIPOS_DE_CAMPO:
            erros.append(f"campo de tipo «{campo.get('type')}» não existe")
            continue
        if campo["type"] != "markdown":
            ids.append(str(campo.get("id")))
            if not (campo.get("attributes") or {}).get("label"):
                erros.append(f"o campo «{campo.get('id')}» não tem `label`")
        if campo["type"] == "dropdown" and not (campo.get("attributes") or {}).get("options"):
            erros.append(f"o dropdown «{campo.get('id')}» não tem opções")
    if len(ids) != len(set(ids)):
        erros.append("há `id` repetido")
    return erros


def test_ha_um_formulario_para_o_defeito_a_ideia_e_o_jogo() -> None:
    assert [p.name for p in _formularios()] == ["bug.yml", "ideia.yml", "jogo.yml"]
    assert not list(ISSUES.glob("*.md")), "formulário no lugar do modelo solto"


@pytest.mark.parametrize("arquivo", _formularios(), ids=lambda p: p.name)
def test_o_formulario_de_issue_vale_e_so_cita_rotulo_e_tipo_que_existem(arquivo: Path) -> None:
    tipos = {t["nome"] for t in _dados()["tipos_de_issue"]}
    assert erros_do_formulario(_yaml(arquivo), _rotulos_declarados(), tipos) == []


def test_mordida_formulario_com_rotulo_ou_tipo_que_nao_existe_reprova() -> None:
    f = _yaml(ISSUES / "bug.yml")
    f["labels"] = ["rotulo-que-ninguem-criou"]
    f["type"] = "Tipo Inventado"
    erros = erros_do_formulario(
        f, _rotulos_declarados(), {t["nome"] for t in _dados()["tipos_de_issue"]}
    )
    assert len(erros) == 2


def test_o_formulario_que_pede_o_doctor_o_chama_pelo_nome_que_a_triagem_procura() -> None:
    triagem = _modulo("triagem")
    for nome in ("bug.yml", "jogo.yml"):
        campos = [c for c in _yaml(ISSUES / nome)["body"] if c.get("id") == "doctor"]
        assert len(campos) == 1, nome
        assert campos[0]["attributes"]["label"] == triagem.CAMPO
        assert campos[0]["validations"]["required"] is True
    for r in (*triagem.ROTULOS_QUE_PEDEM, triagem.ROTULO):
        assert r in _rotulos_declarados()
    for nome in ("bug.yml", "jogo.yml"):
        assert set(_yaml(ISSUES / nome)["labels"]) & set(triagem.ROTULOS_QUE_PEDEM)


def test_a_configuracao_das_issues_manda_a_pergunta_para_as_discussoes() -> None:
    conf = _yaml(ISSUES / "config.yml")
    assert conf["blank_issues_enabled"] is False
    slugs = {c["slug"] for c in _dados()["discussoes"]["categorias"]}
    for link in conf["contact_links"]:
        assert link["name"] and link["about"]
        if "/discussions/categories/" in link["url"]:
            assert link["url"].rsplit("/", 1)[1] in slugs, link["url"]
    assert any("/security/advisories/new" in c["url"] for c in conf["contact_links"])


def test_cada_modelo_de_discussao_tem_o_nome_de_uma_categoria_que_o_arquivo_declara() -> None:
    slugs = {c["slug"] for c in _dados()["discussoes"]["categorias"]}
    modelos = sorted((GH_DIR / "DISCUSSION_TEMPLATE").glob("*.yml"))
    assert modelos
    for m in modelos:
        assert m.stem in slugs, f"{m.name}: não há categoria «{m.stem}» no repositorio.yml"
        corpo = _yaml(m)
        assert corpo["title"] and corpo["body"]
        assert all(c["type"] in TIPOS_DE_CAMPO for c in corpo["body"])
    assert "announcements" not in {m.stem for m in modelos}, (
        "anúncio é de quem mantém: sem formulário"
    )


def test_o_codeowners_chama_uma_equipe_que_o_arquivo_declara() -> None:
    linhas = [
        x
        for x in (GH_DIR / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
        if x.strip() and not x.startswith("#")
    ]
    assert linhas and linhas[0].split()[0] == "*", (
        "sem a regra geral, PR em arquivo novo não pede revisão"
    )
    equipes = {f"@Hefesto-Team/{e['nome']}" for e in _dados()["equipes"]}
    for linha in linhas:
        donos = linha.split()[1:]
        assert donos and set(donos) <= equipes, linha


def test_o_funding_so_usa_chaves_que_o_github_conhece() -> None:
    conhecidas = {
        "github",
        "patreon",
        "open_collective",
        "ko_fi",
        "tidelift",
        "community_bridge",
        "liberapay",
        "issuehunt",
        "lfx_crowdfunding",
        "polar",
        "buy_me_a_coffee",
        "thanks_dev",
        "custom",
    }
    funding = _yaml(GH_DIR / "FUNDING.yml")
    assert funding and set(funding) <= conhecidas
    assert all(isinstance(v, (str, list)) and v for v in funding.values()), "chave vazia não vale"


def _casa(glob: str, arquivo: str) -> bool:
    """O glob do rotulador contra um caminho (`**` atravessa pastas, `*` não)."""
    padrao = ""
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            padrao += "(?:.*/)?"
            i += 3
        elif glob.startswith("**", i):
            padrao += ".*"
            i += 2
        elif glob[i] == "*":
            padrao += "[^/]*"
            i += 1
        else:
            padrao += re.escape(glob[i])
            i += 1
    return re.fullmatch(padrao, arquivo) is not None


def _arquivos_versionados() -> list[str]:
    saida = subprocess.run(
        ["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True
    )
    return saida.stdout.splitlines()


def _globs_do_rotulador() -> list[tuple[str, str]]:
    achados: list[tuple[str, str]] = []
    for rotulo, regras in _yaml(GH_DIR / "labeler.yml").items():
        for regra in regras:
            for g in regra["changed-files"][0]["any-glob-to-any-file"]:
                achados.append((rotulo, g))
    return achados


def test_o_rotulador_so_poe_rotulo_que_existe() -> None:
    rotulos = _rotulos_declarados()
    assert {r for r, _ in _globs_do_rotulador()} <= rotulos
    areas = {r for r in rotulos if r.startswith("área: ")}
    assert areas <= {r for r, _ in _globs_do_rotulador()}, (
        "toda área tem de ser pelo menos um caminho"
    )


def test_cada_caminho_do_rotulador_acha_algum_arquivo_do_repositorio() -> None:
    arquivos = _arquivos_versionados()
    perdidos = [(r, g) for r, g in _globs_do_rotulador() if not any(_casa(g, a) for a in arquivos)]
    assert perdidos == [], f"o rótulo nunca seria posto por estes caminhos: {perdidos}"


def test_o_casador_de_caminho_distingue_estrela_de_estrela_estrela() -> None:
    assert _casa("src/**", "src/a/b/c.py") and not _casa("src/*", "src/a/b.py")
    assert _casa("docs/usage/bluetooth*.md", "docs/usage/bluetooth-varios.md")
    assert not _casa("docs/usage/bluetooth*.md", "docs/usage/x/bluetooth.md")


# --- os fluxos novos ---------------------------------------------------------------------------

WORKFLOWS_NOVOS = ("rotulos.yml", "paginas.yml", "imagens-de-teste.yml", "dependencias.yml")
SHA = re.compile(r"[0-9a-f]{40}")


def _workflow(nome: str) -> dict[Any, Any]:
    wf = _yaml(GH_DIR / "workflows" / nome)
    assert isinstance(wf, dict)
    return wf


def _gatilhos(wf: dict[Any, Any]) -> Any:
    """O `on:` do workflow (o PyYAML o lê como `True`)."""
    return wf.get(True, wf.get("on"))


def _usos(wf: dict[Any, Any]) -> list[str]:
    return [
        p["uses"]
        for j in (wf.get("jobs") or {}).values()
        for p in j.get("steps") or []
        if "uses" in p
    ]


def usos_mal_fixados(wf: dict[Any, Any]) -> list[str]:
    """Ação de fora do GitHub só vale presa a um commit; as `actions/` aceitam a versão maior."""
    ruins: list[str] = []
    for uso in _usos(wf):
        dono, _, ref = uso.partition("@")
        ref = ref.split()[0] if ref else ""
        if not ref:
            ruins.append(f"{uso}: sem versão")
        elif dono.startswith("actions/"):
            if not (SHA.fullmatch(ref) or re.fullmatch(r"v\d+", ref)):
                ruins.append(f"{uso}: use v<maior> ou um commit")
        elif not SHA.fullmatch(ref):
            ruins.append(f"{uso}: ação de fora presa a um commit, e não a «{ref}»")
    return ruins


@pytest.mark.parametrize("nome", WORKFLOWS_NOVOS)
def test_os_fluxos_novos_prendem_as_acoes_e_pedem_so_leitura_por_padrao(nome: str) -> None:
    wf = _workflow(nome)
    assert usos_mal_fixados(wf) == []
    assert wf["permissions"] == {"contents": "read"}, "a escrita é por job, nunca no topo"


def test_mordida_acao_de_fora_numa_versao_solta_reprova() -> None:
    wf = _workflow("imagens-de-teste.yml")
    wf["jobs"]["imagem"]["steps"][2]["uses"] = "docker/login-action@v3"
    assert any("docker/login-action" in e for e in usos_mal_fixados(wf))
    wf["jobs"]["imagem"]["steps"][2]["uses"] = "docker/login-action@main"
    assert usos_mal_fixados(wf)


def test_o_fluxo_que_roda_com_escrita_em_pr_de_fora_nunca_baixa_o_codigo_do_pr() -> None:
    wf = _workflow("rotulos.yml")
    gatilhos = _gatilhos(wf)
    assert "pull_request_target" in gatilhos
    area = wf["jobs"]["area"]
    assert not [p for p in area["steps"] if "checkout" in p.get("uses", "")]
    assert area["permissions"]["pull-requests"] == "write"
    assert wf["jobs"]["doctor"]["permissions"]["issues"] == "write"


def test_o_fluxo_de_rotulos_aponta_para_arquivos_que_existem() -> None:
    texto = (GH_DIR / "workflows" / "rotulos.yml").read_text(encoding="utf-8")
    for caminho in re.findall(r"(\.github/labeler\.yml|scripts/github/triagem\.py)", texto):
        assert (RAIZ / caminho).is_file(), caminho
    assert "scripts/github/triagem.py" in texto and ".github/labeler.yml" in texto


def test_a_revisao_de_dependencias_roda_em_todo_pr() -> None:
    gatilhos = _workflow("dependencias.yml").get(True, _workflow("dependencias.yml").get("on"))
    assert "pull_request" in (gatilhos if isinstance(gatilhos, (dict, list)) else [gatilhos])


def test_as_paginas_publicam_so_o_main_e_pelo_ambiente_do_github() -> None:
    wf = _workflow("paginas.yml")
    gatilhos = _gatilhos(wf)
    assert gatilhos["push"]["branches"] == ["main"]
    publicar = wf["jobs"]["publicar"]
    assert publicar["permissions"] == {"pages": "write", "id-token": "write"}
    assert publicar["environment"]["name"] == "github-pages"
    passos = " ".join(str(p.get("run", "")) for p in wf["jobs"]["montar"]["steps"])
    assert "scripts/github/montar_pagina.py" in passos
    assert _yaml(GH_DIR / "repositorio.yml")["funções"]["pages"]["ligada"] is True


def _matriz_do_smoke() -> list[dict[str, Any]]:
    ci = _yaml(GH_DIR / "workflows" / "ci.yml")
    return ci["jobs"]["smoke-multi-distro"]["strategy"]["matrix"]["include"]  # type: ignore[no-any-return]


def imagens_fora_da_matriz(matriz: list[dict[str, Any]], pasta: Path) -> list[str]:
    """Cada distro do `smoke-multi-distro` tem um Dockerfile com a mesma imagem e instalação."""
    faltas: list[str] = []
    for d in matriz:
        arq = pasta / f"{d['distro']}.Dockerfile"
        if not arq.is_file():
            faltas.append(f"{d['distro']}: sem Dockerfile")
            continue
        linhas = arq.read_text(encoding="utf-8").splitlines()
        if f"FROM {d['image']}" not in linhas:
            faltas.append(f"{d['distro']}: não parte de {d['image']}")
        if f"RUN {d['install_cmd']}" not in linhas:
            faltas.append(f"{d['distro']}: não instala o `install_cmd` do ci.yml")
        if d.get("fontes") and not any(f"--fontes {d['fontes']} --so-fontes" in x for x in linhas):
            faltas.append(f"{d['distro']}: falta o passo das fontes ({d['fontes']})")
    return faltas


def test_as_imagens_de_teste_instalam_o_que_o_smoke_do_ci_instala() -> None:
    assert imagens_fora_da_matriz(_matriz_do_smoke(), RAIZ / "scripts" / "github" / "imagens") == []
    wf = _workflow("imagens-de-teste.yml")
    distros = wf["jobs"]["imagem"]["strategy"]["matrix"]["distro"]
    assert sorted(distros) == sorted(d["distro"] for d in _matriz_do_smoke())
    passos = wf["jobs"]["imagem"]["steps"]
    imagem = next(p for p in passos if p.get("id") == "meta")["with"]["images"]
    assert imagem.startswith("ghcr.io/hefesto-team/") and imagem == imagem.lower().replace(
        "${{ matrix.distro }}", "${{ matrix.distro }}"
    ), "o nome da imagem no ghcr é todo minúsculo"
    assert wf["jobs"]["imagem"]["permissions"]["packages"] == "write"


def test_mordida_imagem_que_instala_outra_coisa_reprova(tmp_path: Path) -> None:
    copia = tmp_path / "imagens"
    shutil.copytree(RAIZ / "scripts" / "github" / "imagens", copia)
    assert imagens_fora_da_matriz(_matriz_do_smoke(), copia) == []
    arq = copia / "debian-12.Dockerfile"
    arq.write_text(
        arq.read_text(encoding="utf-8").replace("libnotify-bin", "libnotify-bin-velho"),
        encoding="utf-8",
    )
    (copia / "archlinux.Dockerfile").write_text("FROM archlinux:latest\n", encoding="utf-8")
    faltas = imagens_fora_da_matriz(_matriz_do_smoke(), copia)
    assert any(f.startswith("debian-12") for f in faltas) and any(
        f.startswith("archlinux") for f in faltas
    )
    (copia / "fedora-42.Dockerfile").unlink()
    assert any(
        "fedora-42: sem Dockerfile" in f for f in imagens_fora_da_matriz(_matriz_do_smoke(), copia)
    )


# ---------------------------------------------------------------------------
# 7. A triagem das issues e a página do produto
# ---------------------------------------------------------------------------


def _corpo_de_issue(doctor: str | None) -> str:
    base = "### O que aconteceu\n\nO gatilho trava.\n\n### Como repetir\n\n1. liga\n\n"
    if doctor is None:
        return base
    return base + f"### Saída do doctor\n\n{doctor}\n\n### Registro do serviço\n\n_No response_"


def test_a_issue_sem_a_saida_do_doctor_ganha_o_rotulo_e_o_comando() -> None:
    t = _modulo("triagem")
    for doctor in (None, "", "_No response_", "curto", "```shell\nok\n```"):
        d = t.decidir(_corpo_de_issue(doctor), ["bug"], "opened")
        assert d == {"adicionar": [t.ROTULO], "remover": [], "comentar": True}, doctor
    assert "hefesto-dualsense4unix doctor" in t.COMENTARIO
    # Só a issue editada passa pela triagem de novo (o fluxo não escuta comentário): o recado pede a
    # edição, no campo que a régua lê, e nunca promete que um comentário tira o rótulo.
    assert f"«{t.CAMPO}»" in t.COMENTARIO and "comentário" not in t.COMENTARIO
    gatilhos = _gatilhos(_workflow("rotulos.yml"))
    assert "issue_comment" not in gatilhos and gatilhos["issues"]["types"] == ["opened", "edited"]


def test_a_issue_editada_nao_comenta_de_novo_e_a_completa_perde_o_rotulo() -> None:
    t = _modulo("triagem")
    saida = "```shell\n" + "Controle: DualSense (cabo)\nServiço: ativo\n" + "```"
    d = t.decidir(_corpo_de_issue(None), ["bug"], "edited")
    assert d == {"adicionar": [t.ROTULO], "remover": [], "comentar": False}
    d = t.decidir(_corpo_de_issue(saida), ["bug", t.ROTULO], "edited")
    assert d == {"adicionar": [], "remover": [t.ROTULO], "comentar": False}
    assert t.decidir(_corpo_de_issue(saida), ["bug"], "opened") == {
        "adicionar": [],
        "remover": [],
        "comentar": False,
    }
    assert t.decidir(_corpo_de_issue(None), ["bug", t.ROTULO], "edited") == {
        "adicionar": [],
        "remover": [],
        "comentar": False,
    }, "o rótulo que já está não se põe de novo"


def test_a_ideia_nao_precisa_do_doctor() -> None:
    t = _modulo("triagem")
    d = t.decidir("### O que você quer fazer\n\nUma coisa.", ["enhancement"], "opened")
    assert d == {"adicionar": [], "remover": [], "comentar": False}


def test_a_triagem_le_o_evento_do_github_e_nao_escreve_sem_o_aplicar(tmp_path: Path) -> None:
    evento = tmp_path / "evento.json"
    evento.write_text(
        json.dumps(
            {
                "action": "opened",
                "issue": {"number": 7, "body": _corpo_de_issue(None), "labels": [{"name": "bug"}]},
            }
        ),
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            sys.executable,
            str(RAIZ / "scripts/github/triagem.py"),
            "--evento",
            str(evento),
            "--repo",
            REPO,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0
    assert json.loads(r.stdout)["adicionar"] == ["precisa do doctor"]
    evento.write_text(
        json.dumps(
            {
                "action": "opened",
                "issue": {"number": 8, "pull_request": {}, "body": "", "labels": []},
            }
        ),
        encoding="utf-8",
    )
    r = subprocess.run(
        [
            sys.executable,
            str(RAIZ / "scripts/github/triagem.py"),
            "--evento",
            str(evento),
            "--repo",
            REPO,
            "--aplicar",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0 and "é um PR" in r.stdout


def test_a_pagina_nasce_do_readme_com_todas_as_fotos_e_sem_link_relativo(tmp_path: Path) -> None:
    mp = _modulo("montar_pagina")
    faltam = mp.montar(RAIZ, tmp_path / "site")
    assert faltam == [], f"o README cita imagem que a página não leva: {faltam}"
    pagina = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "<h1>" in pagina and "<title>Hefesto" in pagina
    assert mp.links_relativos(pagina) == []
    fotos = [x for x in mp.imagens_citadas(pagina) if x.startswith("docs/usage/assets/aba-")]
    assert len(fotos) == 10, "as dez abas do README"
    assert all((tmp_path / "site" / f).is_file() for f in fotos)


def test_mordida_o_readme_que_cita_foto_que_nao_existe_reprova(tmp_path: Path) -> None:
    mp = _modulo("montar_pagina")
    raiz = tmp_path / "raiz"
    shutil.copytree(
        RAIZ / "docs" / "usage" / "assets",
        raiz / "docs" / "usage" / "assets",
        ignore=shutil.ignore_patterns("maximizada"),
    )
    (raiz / "README.md").write_text(
        "# Titulo\n\nTexto.\n\n![x](docs/usage/assets/nao-existe.png)\n\n[guia](docs/usage/x.md)\n",
        encoding="utf-8",
    )
    assert mp.montar(raiz, tmp_path / "site") == ["docs/usage/assets/nao-existe.png"]
    pagina = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "blob/main/docs/usage/x.md" in pagina and mp.links_relativos(pagina) == []
    assert mp.principal(["--raiz", str(raiz), "--saida", str(tmp_path / "s2")]) == 1


# ---------------------------------------------------------------------------
# 8. A máquina que assina commit, e o aviso do instalador de ganchos
# ---------------------------------------------------------------------------

ASSINAR = RAIZ / "scripts" / "github" / "assinar-commits.sh"
INSTALAR = RAIZ / "scripts" / "instalar-hooks.sh"


@pytest.fixture
def lar(tmp_path: Path) -> Path:
    """Um lar de mentira com uma chave SSH de brinquedo, gerada aqui (nunca a de quem roda)."""
    return _lar_com_chave(tmp_path / "lar")


def _lar_com_chave(casa: Path) -> Path:
    (casa / ".ssh").mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ssh-keygen",
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            "brinquedo",
            "-f",
            str(casa / ".ssh" / "id_ed25519"),
        ],
        check=True,
    )
    return casa


def _ambiente_do_lar(casa: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "SSH_"))}
    env.update(
        HOME=str(casa),
        XDG_CONFIG_HOME=str(casa / ".config"),
        GIT_CONFIG_GLOBAL=str(casa / ".gitconfig"),
        GIT_CONFIG_NOSYSTEM="1",
    )
    return env


def assinar(casa: Path, *args: str) -> subprocess.CompletedProcess[str]:
    assert casa.resolve() != Path.home().resolve(), "a assinatura só se prova em lar de mentira"
    return subprocess.run(
        ["bash", str(ASSINAR), *args],
        env=_ambiente_do_lar(casa),
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_maquina_que_nao_assina_reprova_o_conferir_e_diz_o_que_falta(lar: Path) -> None:
    r = assinar(lar, "--conferir")
    assert r.returncode == 1
    for item in ("gpg.format ssh", "user.signingkey", "commit.gpgsign true", "tag.gpgsign true"):
        assert item in r.stdout
    assert not (lar / ".gitconfig").exists(), "o --conferir não escreve"
    assert assinar(lar).returncode == 1, "sem argumento é o mesmo que --conferir"


def test_o_aplicar_configura_as_quatro_coisas_e_o_commit_sai_assinado(lar: Path) -> None:
    r = assinar(lar, "--aplicar", "--provar")
    assert r.returncode == 0, r.stdout + r.stderr
    cfg = {
        k: subprocess.run(
            ["git", "config", "--global", "--get", k],
            env=_ambiente_do_lar(lar),
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        for k in ("gpg.format", "user.signingkey", "commit.gpgsign", "tag.gpgsign")
    }
    assert cfg == {
        "gpg.format": "ssh",
        "user.signingkey": str(lar / ".ssh" / "id_ed25519.pub"),
        "commit.gpgsign": "true",
        "tag.gpgsign": "true",
    }
    assert "confere" in r.stdout
    assert assinar(lar, "--conferir", "--provar").returncode == 0


def test_o_aplicar_e_idempotente_e_o_conferir_depois_sai_zero(lar: Path) -> None:
    assert assinar(lar, "--aplicar").returncode == 0
    antes = (lar / ".gitconfig").read_text(encoding="utf-8")
    r = assinar(lar, "--aplicar")
    assert r.returncode == 0 and "nada a fazer" in r.stdout
    assert (lar / ".gitconfig").read_text(encoding="utf-8") == antes
    assert assinar(lar, "--conferir").returncode == 0


def test_a_chave_pedida_vale_e_a_que_nao_existe_ou_nao_e_publica_recusa(
    lar: Path, tmp_path: Path
) -> None:
    outra = tmp_path / "outra"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(outra)], check=True)
    assert assinar(lar, "--aplicar", "--chave", f"{outra}.pub").returncode == 0
    assert str(outra) in (lar / ".gitconfig").read_text(encoding="utf-8")
    assert (
        assinar(lar, "--conferir", "--chave", str(lar / ".ssh" / "id_ed25519.pub")).returncode == 1
    )
    vazio = tmp_path / "lar2"
    vazio.mkdir()
    r = assinar(vazio, "--aplicar")
    assert r.returncode == 2 and "chave pública" in r.stderr and not (vazio / ".gitconfig").exists()
    r = assinar(lar, "--aplicar", "--chave", str(lar / ".ssh" / "nao-existe.pub"))
    assert r.returncode == 2 and "não achei a chave pública" in r.stderr
    assert assinar(vazio, "--aplicar", "--chave", str(outra)).returncode == 2, "a privada não vale"


def test_a_chave_gravada_que_sumiu_do_disco_volta_a_reprovar(lar: Path) -> None:
    assert assinar(lar, "--aplicar").returncode == 0
    (lar / ".ssh" / "id_ed25519.pub").unlink()
    r = assinar(lar, "--conferir")
    assert r.returncode == 1 and "não existe" in r.stdout


def test_o_provar_reprova_quando_o_commit_nao_sai_assinado(lar: Path) -> None:
    assert assinar(lar, "--aplicar").returncode == 0
    (lar / ".ssh" / "id_ed25519").unlink()  # sobra a pública, e o git não tem com o que assinar
    r = assinar(lar, "--conferir", "--provar")
    assert r.returncode == 1 and "NÃO saiu assinado" in r.stdout


def test_o_assinar_nao_roda_com_sudo_nem_com_argumento_estranho(lar: Path) -> None:
    assert assinar(lar, "--tudo").returncode == 2
    assert assinar(lar, "--chave").returncode == 2


@pytest.fixture
def casa_dos_ganchos(tmp_path: Path) -> Path:
    """O repositório de brinquedo com o instalador, a régua, os ganchos e o conferidor copiados."""
    repo = tmp_path / "repo"
    (repo / "scripts" / "github").mkdir(parents=True)
    for origem, destino in (
        ("scripts/instalar-hooks.sh", "scripts/instalar-hooks.sh"),
        ("scripts/check_autoria.py", "scripts/check_autoria.py"),
        ("scripts/github/assinar-commits.sh", "scripts/github/assinar-commits.sh"),
    ):
        shutil.copy2(RAIZ / origem, repo / destino)
    shutil.copytree(RAIZ / "scripts" / "hooks", repo / "scripts" / "hooks")
    env = _ambiente_do_lar(tmp_path / "lar")
    (tmp_path / "lar").mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=env)
    return repo


def _instalar(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    lar = repo.parent / "lar"
    return subprocess.run(
        ["bash", "scripts/instalar-hooks.sh", *args],
        cwd=repo,
        env=_ambiente_do_lar(lar),
        capture_output=True,
        text=True,
        check=False,
    )


def test_o_conferir_do_instalador_avisa_da_maquina_que_nao_assina_e_nao_muda_a_saida(
    casa_dos_ganchos: Path,
) -> None:
    sem = _instalar(casa_dos_ganchos, "--conferir")
    assert "AVISO: esta máquina não assina commit" in sem.stdout
    assert "scripts/github/assinar-commits.sh --aplicar" in sem.stdout
    assert (
        sem.returncode == 1
    )  # o que o instalador faria (a política e o gancho) ainda não está feito
    assert _instalar(casa_dos_ganchos).returncode == 0
    depois = _instalar(casa_dos_ganchos, "--conferir")
    assert depois.returncode == 0 and "nada a fazer" in depois.stdout
    assert "AVISO: esta máquina não assina commit" in depois.stdout, (
        "o aviso vale também com tudo o mais em dia"
    )
    assert not (casa_dos_ganchos.parent / "lar" / ".gitconfig").exists(), (
        "o instalador nunca configura a assinatura"
    )


def test_o_instalador_sem_o_aviso_quando_a_maquina_assina(casa_dos_ganchos: Path) -> None:
    destino = _lar_com_chave(casa_dos_ganchos.parent / "lar")
    assert assinar(destino, "--aplicar").returncode == 0
    assert _instalar(casa_dos_ganchos).returncode == 0
    r = _instalar(casa_dos_ganchos, "--conferir")
    assert r.returncode == 0 and "AVISO" not in r.stdout


def test_o_instalador_so_avisa_no_conferir(casa_dos_ganchos: Path) -> None:
    r = _instalar(casa_dos_ganchos)
    assert r.returncode == 0 and "AVISO" not in r.stdout
