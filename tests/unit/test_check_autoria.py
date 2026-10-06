"""A régua de autoria (`scripts/check_autoria.py`), contra repositórios de brinquedo.

A lista é sintética: um canário sem sentido e um fornecedor inventado. O canário se
monta em tempo de execução porque a régua mede o próprio repositório, e o arquivo que
o escreve inteiro seria a primeira ocorrência dele.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
REGUA = RAIZ / "scripts" / "check_autoria.py"

CANARIO = "zqcanario" + "autoria"
FORNECEDOR = "fornecedor" + "-x"
ZERO = "0" * 40
# O sanitizador de coautoria do pre-commit apaga a linha que traz o literal: monta-se por partes.
COAUTORIA = "Co-Authored" + "-By"

LISTA = "\n".join([
    "# lista sintética dos testes",
    f"1 {CANARIO}",
    f"1 {FORNECEDOR.replace('-', ' ')}",
    "1 re:(?<=[A-Z0-9])-zq\\b",
    "2 agente", "2 Agente", "2 agentes", "2 Agentes",
    "2 subagente", "2 Subagente", "2 subagentes", "2 Subagentes",
    "2 assistente", "2 Assistente",
    "2 SIGLAX",
]) + "\n"

MAILMAP = (
    "Pessoa Um <um@casa.test>\n"
    "Pessoa Dois <dois@casa.test>\n"
    "Pessoa Dois <dois@casa.test> <70702280+dois@users.noreply.casa.test>\n"
    "Pessoa Dois <dois@casa.test> <noreply@github.com>\n"
)

UM = ("Pessoa Um", "um@casa.test")
DOIS = ("Pessoa Dois", "dois@casa.test")
DOIS_PELO_SITE = ("Pessoa Dois", "70702280+dois@users.noreply.casa.test")
SERVIDOR = ("GitHub", "noreply@github.com")
DE_FORA = ("Fulana de Fora", "fulana@fora.test")


def _ambiente(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    for chave in list(env):
        if chave.startswith(("GIT_AUTHOR", "GIT_COMMITTER", "AUTORIA_")):
            del env[chave]
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    env.update(extra or {})
    return env


def git(repo: Path, *args: str, extra: dict[str, str] | None = None) -> str:
    r = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
         "-c", "tag.gpgsign=false", *args],
        cwd=repo, env=_ambiente(extra), capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def commitar(
    repo: Path,
    mensagem: str = "feat: mais um",
    autor: tuple[str, str] = UM,
    committer: tuple[str, str] | None = None,
    arquivos: dict[str, str] | None = None,
    apagar: tuple[str, ...] = (),
) -> str:
    committer = committer or autor
    for nome, texto in (arquivos or {"a.txt": mensagem}).items():
        alvo = repo / nome
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(texto, encoding="utf-8")
        git(repo, "add", nome)
    for nome in apagar:
        git(repo, "rm", "-q", nome)
    git(repo, "commit", "-q", "--allow-empty", "-m", mensagem, extra={
        "GIT_AUTHOR_NAME": autor[0], "GIT_AUTHOR_EMAIL": autor[1],
        "GIT_COMMITTER_NAME": committer[0], "GIT_COMMITTER_EMAIL": committer[1],
    })
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "r"
    r.mkdir()
    git(r, "init", "-q", "-b", "dev")
    (r / ".mailmap").write_text(MAILMAP, encoding="utf-8")
    commitar(r, "chore: nasce", arquivos={".mailmap": MAILMAP})
    return r


def rodar(
    repo: Path, *args: str, lista: str | None = LISTA, entrada: str | None = None,
) -> subprocess.CompletedProcess[str]:
    extra = {"AUTORIA_VEDADOS": lista} if lista is not None else {}
    return subprocess.run(
        [sys.executable, str(REGUA), *args],
        cwd=repo, env=_ambiente(extra), input=entrada, capture_output=True, text=True,
    )


def saida(p: subprocess.CompletedProcess[str]) -> str:
    return p.stdout + p.stderr


# ---------------------------------------------------------------------------
# Quem pode assinar
# ---------------------------------------------------------------------------


def test_commit_limpo_de_quem_esta_no_mailmap_passa(repo: Path) -> None:
    commitar(repo, "feat: uma coisa", autor=DOIS)
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 0, saida(p)
    assert "OK" in p.stdout


def test_committer_fora_do_mailmap_com_autor_da_casa_reprova_s7(repo: Path) -> None:
    commitar(repo, autor=UM, committer=DE_FORA)
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 1
    assert "committer" in p.stdout


def test_nome_fora_com_endereco_da_casa_reprova_s8(repo: Path) -> None:
    commitar(repo, autor=("Fulana de Fora", UM[1]))
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 1
    assert "nome fora do .mailmap" in p.stdout


def test_a_saida_nao_imprime_o_nome_nem_o_endereco_de_quem_reprovou(repo: Path) -> None:
    commitar(repo, autor=DE_FORA)
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 1
    assert "Fulana" not in saida(p) and "fora.test" not in saida(p)


def test_coautoria_de_ferramenta_reprova_pela_regra_estrutural(repo: Path) -> None:
    """Nem a lista precisa conhecer o fornecedor: a linha de atribuição é a regra."""
    commitar(repo, f"feat: x\n\n{COAUTORIA}: Fornecedor X <x@{FORNECEDOR}.test>")
    p = rodar(repo, "historia", "HEAD", lista=f"1 {CANARIO}\n")
    assert p.returncode == 1
    assert "linha de atribuição" in p.stdout
    assert FORNECEDOR not in saida(p)


@pytest.mark.parametrize("chave", ["Algo-session", "Fornecedor-with", "Reviewed-by"])
def test_chave_de_atribuicao_sem_o_endereco_da_casa_reprova(repo: Path, chave: str) -> None:
    commitar(repo, f"feat: x\n\n{chave}: alguém <alguem@fora.test>")
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 1, saida(p)


@pytest.mark.parametrize("valor", [
    "Fornecedor X <x@fora.test>, um@casa.test",
    "Fornecedor X <x+um@casa.test>",
    "Pessoa Um <um@casa.test> <x@fora.test>",
])
def test_atribuicao_com_endereco_de_fora_ao_lado_do_da_casa_reprova(repo: Path, valor: str) -> None:
    """TODO endereço da linha é da casa: o da casa ao lado (ou dentro) de outro não basta."""
    commitar(repo, f"feat: x\n\n{COAUTORIA}: {valor}")
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 1, saida(p)
    assert "linha de atribuição" in p.stdout


def test_signed_off_by_de_quem_esta_no_mailmap_passa(repo: Path) -> None:
    commitar(repo, "feat: x\n\nSigned-off-by: Pessoa Dois <dois@casa.test>", autor=DOIS)
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 0, saida(p)


def test_edicao_pela_interface_do_github_passa_o_alias_do_mailmap(repo: Path) -> None:
    """Autor com o alias `70702280+…` e committer `GitHub <noreply@github.com>`."""
    commitar(repo, "docs: pelo site", autor=DOIS_PELO_SITE, committer=SERVIDOR)
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 0, saida(p)


def test_o_committer_do_github_com_autor_de_fora_reprova(repo: Path) -> None:
    commitar(repo, "docs: pelo site", autor=DE_FORA, committer=SERVIDOR)
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 1
    assert "autor" in p.stdout


def test_o_nome_github_com_outro_endereco_nao_e_o_servidor(repo: Path) -> None:
    commitar(repo, "docs: x", autor=UM, committer=("GitHub", "outro@fora.test"))
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 1


def test_tag_anotada_com_o_canario_na_mensagem_reprova_s6(repo: Path) -> None:
    commitar(repo)
    git(repo, "tag", "-a", "v1", "-m", f"versão {CANARIO}", extra={
        "GIT_COMMITTER_NAME": UM[0], "GIT_COMMITTER_EMAIL": UM[1]})
    p = rodar(repo, "historia", "refs/tags/v1")
    assert p.returncode == 1
    assert "tag" in p.stdout and CANARIO not in saida(p)


def test_tagger_fora_do_mailmap_reprova(repo: Path) -> None:
    commitar(repo)
    git(repo, "tag", "-a", "v2", "-m", "versão", extra={
        "GIT_COMMITTER_NAME": DE_FORA[0], "GIT_COMMITTER_EMAIL": DE_FORA[1]})
    p = rodar(repo, "historia", "refs/tags/v2")
    assert p.returncode == 1
    assert "tagger" in p.stdout


def test_arquivo_com_o_canario_no_nome_que_entrou_e_saiu_reprova_s12(repo: Path) -> None:
    nome = f"docs/{CANARIO}.md"
    commitar(repo, "docs: entra", arquivos={nome: "texto limpo\n"})
    commitar(repo, "docs: sai", apagar=(nome,))
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 1
    assert "nome de arquivo da história" in p.stdout
    assert CANARIO not in saida(p)


def test_refs_replace_que_mascara_um_trailer_reprova_s4(repo: Path) -> None:
    """O `git log` obedece a `refs/replace`; o push não. A régua mede o que viaja."""
    limpo = commitar(repo, "feat: limpo")
    sujo = commitar(repo, f"feat: sujo\n\n{COAUTORIA}: Fornecedor X <x@fora.test>")
    git(repo, "replace", sujo, limpo)
    # o dublê é real: o log comum, com as substituições valendo, mente
    visto = git(repo, "log", "-1", "--format=%B", sujo)
    assert COAUTORIA not in visto, "o dublê não mascarou nada: o caso não prova S4"
    p = rodar(repo, "historia", sujo)
    assert p.returncode == 1, saida(p)
    assert "linha de atribuição" in p.stdout


def test_historia_de_clone_raso_reprova(repo: Path, tmp_path: Path) -> None:
    commitar(repo)
    commitar(repo)
    raso = tmp_path / "raso"
    r = subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(raso)],
                       env=_ambiente(), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    (raso / ".mailmap").write_text(MAILMAP, encoding="utf-8")
    p = rodar(raso, "historia", "HEAD")
    assert p.returncode == 1
    assert "clone raso" in p.stdout


# ---------------------------------------------------------------------------
# O vocabulário: a lista, os dois níveis, e o que nunca se imprime
# ---------------------------------------------------------------------------


def test_sem_a_lista_a_parte_de_vocabulario_sai_nao_medido(repo: Path) -> None:
    commitar(repo)
    p = rodar(repo, "historia", "HEAD", lista="")
    assert p.returncode == 1
    assert "NÃO MEDIDO" in p.stdout


def test_a_lista_pode_vir_do_arquivo_do_git_config(repo: Path, tmp_path: Path) -> None:
    arquivo = tmp_path / "vedados"
    arquivo.write_text(LISTA, encoding="utf-8")
    git(repo, "config", "autoria.vedados", str(arquivo))
    commitar(repo, f"feat: {CANARIO}")
    p = rodar(repo, "historia", "HEAD", lista="")
    assert p.returncode == 1
    assert "termo da lista na mensagem" in p.stdout


@pytest.mark.parametrize("ruim", ["3 outro", "1re:x", "1 re:(", "nivel termo"])
def test_linha_da_lista_que_nao_se_le_e_nao_medido_e_nao_verde(repo: Path, ruim: str) -> None:
    """Um termo da lista que não se lê é um termo que não se mede: não sai verde."""
    commitar(repo)
    p = rodar(repo, "historia", "HEAD", lista=LISTA + ruim + "\n")
    assert p.returncode == 1, saida(p)
    assert "NÃO MEDIDO" in p.stdout and "1 linha(s)" in p.stdout
    assert ruim not in saida(p)


def test_arquivo_da_lista_que_nao_existe_tambem_e_nao_medido(repo: Path) -> None:
    git(repo, "config", "autoria.vedados", "/nao/existe/vedados")
    p = rodar(repo, "historia", "HEAD", lista="")
    assert p.returncode == 1
    assert "NÃO MEDIDO" in p.stdout


@pytest.mark.parametrize("onde", ["mensagem", "tag", "nome", "arvore", "diff", "texto", "ramo"])
def test_a_saida_de_qualquer_reprovacao_nao_contem_o_canario(repo: Path, onde: str) -> None:
    """O log do CI é público: nem o termo, nem a linha que casou, nem o nome que o carrega."""
    base = git(repo, "rev-parse", "HEAD")
    if onde == "mensagem":
        commitar(repo, f"feat: {CANARIO} apareceu")
        p = rodar(repo, "historia", "HEAD")
    elif onde == "tag":
        commitar(repo)
        git(repo, "tag", "-a", "v3", "-m", CANARIO, extra={
            "GIT_COMMITTER_NAME": UM[0], "GIT_COMMITTER_EMAIL": UM[1]})
        p = rodar(repo, "historia", "refs/tags/v3")
    elif onde == "nome":
        commitar(repo, "docs: x", arquivos={f"{CANARIO}/{CANARIO}.md": "limpo\n"})
        p = rodar(repo, "arvore")
    elif onde == "arvore":
        commitar(repo, "docs: x", arquivos={"d/a.md": f"linha limpa\nlinha com {CANARIO} aqui\n"})
        p = rodar(repo, "arvore", "HEAD")
    elif onde == "diff":
        topo = commitar(repo, "docs: x", arquivos={f"{CANARIO}.md": f"entra {CANARIO}\n"})
        p = rodar(repo, "diff", base, topo)
    elif onde == "texto":
        p = rodar(repo, "texto", entrada=f"título\ncorpo com {CANARIO}\n")
    else:
        sha = commitar(repo)
        git(repo, "branch", f"x-{CANARIO}")
        ramo = f"refs/heads/x-{CANARIO}"
        p = empurrar(repo, ramo, sha, ramo)
    assert p.returncode == 1, saida(p)
    assert CANARIO not in saida(p), saida(p)


def test_a_arvore_aponta_arquivo_e_linha_sem_a_linha_que_casou(repo: Path) -> None:
    commitar(repo, "docs: x", arquivos={"d/a.md": f"limpa\nlimpa\nacha {CANARIO} aqui\n"})
    p = rodar(repo, "arvore", "HEAD")
    assert p.returncode == 1
    assert "d/a.md:3: termo da lista (nível 1)" in p.stdout
    assert "acha" not in p.stdout


def test_a_arvore_limpa_passa(repo: Path) -> None:
    commitar(repo, "docs: x", arquivos={"d/a.md": "só texto limpo\n"})
    p = rodar(repo, "arvore", "HEAD")
    assert p.returncode == 0, saida(p)


@pytest.mark.parametrize(
    "nome", ["src/m.py", "README.md", "pyproject.toml", "CHANGELOG.md", "LICENSE"])
def test_nivel_1_mede_toda_a_arvore_sem_isencao_de_arquivo(repo: Path, nome: str) -> None:
    commitar(repo, "docs: x", arquivos={nome: f"# {CANARIO}\n"})
    assert rodar(repo, "arvore", "HEAD").returncode == 1


def test_termo_de_duas_palavras_acha_com_caixa_e_acento_diferentes(repo: Path) -> None:
    commitar(repo, "docs: x", arquivos={"a.md": "o Fornecédor X chegou\n"})
    assert rodar(repo, "arvore", "HEAD").returncode == 1


@pytest.mark.parametrize("texto", [
    "o defeito porque o gancho chama o script",
    "model_name = 'DualSense'",
    "integra com llama-cpp-python se disponível",
    "frame do codec opus: 71 bytes",
    "um fornecedor qualquer, x depois",
    "codec-zq em minúsculo",
])
def test_o_nivel_1_nao_falsa_em_vocabulario_comum(repo: Path, texto: str) -> None:
    commitar(repo, "docs: x", arquivos={"a.md": texto + "\n"})
    p = rodar(repo, "arvore", "HEAD")
    assert p.returncode == 0, saida(p)


def test_a_linha_regex_pega_o_sufixo_colado_a_maiuscula_ou_digito(repo: Path) -> None:
    commitar(repo, "docs: x", arquivos={"a.md": "laudo-X1-zq\n"})
    assert rodar(repo, "arvore", "HEAD").returncode == 1


def test_arquivo_ignorado_pelo_gitignore_nao_e_medido_na_arvore_de_trabalho(repo: Path) -> None:
    (repo / ".gitignore").write_text("lixo/\n", encoding="utf-8")
    (repo / "lixo").mkdir()
    (repo / "lixo" / "g.md").write_text(f"{CANARIO}\n", encoding="utf-8")
    assert rodar(repo, "arvore").returncode == 0


def test_arquivo_novo_ainda_sem_git_add_e_medido_na_arvore_de_trabalho(repo: Path) -> None:
    (repo / "novo.md").write_text(f"{CANARIO}\n", encoding="utf-8")
    assert rodar(repo, "arvore").returncode == 1


def test_importar_agente_de_pareamento_passa_o_nivel_2_nao_mede_codigo(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    codigo = {"m.py": "from x.agente_de_pareamento import y\n"}
    topo = commitar(repo, "feat: o pareamento", arquivos=codigo)
    p = rodar(repo, "diff", base, topo)
    assert p.returncode == 0, saida(p)


def test_o_diff_mede_o_nivel_1_nas_linhas_acrescentadas_e_so_nelas(repo: Path) -> None:
    commitar(repo, "docs: antes", arquivos={"a.md": f"{CANARIO}\n"})
    base = git(repo, "rev-parse", "HEAD")
    topo = commitar(repo, "docs: depois", arquivos={"a.md": f"{CANARIO}\nlimpa\n"})
    assert rodar(repo, "diff", base, topo).returncode == 0
    topo2 = commitar(repo, "docs: pior", arquivos={"a.md": f"{CANARIO}\nlimpa\nmais {CANARIO}\n"})
    assert rodar(repo, "diff", topo, topo2).returncode == 1


def test_o_diff_com_arquivo_que_nao_e_utf8_mede_e_nao_cai(repo: Path) -> None:
    """Um arquivo em Latin-1 derrubava a régua com traceback, e o push ficava barrado sem medida."""
    base = git(repo, "rev-parse", "HEAD")
    (repo / "latin.txt").write_bytes(b"ol\xe1 mundo\n")
    git(repo, "add", "latin.txt")
    topo = commitar(repo, "feat: latin", arquivos={})
    p = rodar(repo, "diff", base, topo)
    assert p.returncode == 0, saida(p)
    (repo / "latin.txt").write_bytes(b"ol\xe1 " + CANARIO.encode() + b"\n")
    git(repo, "add", "latin.txt")
    topo = commitar(repo, "feat: latin de novo", arquivos={})
    p = rodar(repo, "diff", base, topo)
    assert p.returncode == 1 and "Traceback" not in saida(p), saida(p)
    assert "latin.txt: linha acrescentada com termo da lista (nível 1)" in p.stdout


def test_mensagem_nova_com_vocabulario_de_processo_reprova(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    topo = commitar(repo, "fix: o subagente refez")
    p = rodar(repo, "diff", base, topo)
    assert p.returncode == 1
    assert "(nível 2)" in p.stdout


def test_o_nivel_2_preserva_a_caixa(repo: Path) -> None:
    base = git(repo, "rev-parse", "HEAD")
    # `SIGLAX` está na lista em maiúscula: a forma minúscula é outra palavra
    assert rodar(repo, "diff", base, commitar(repo, "feat: o siglax")).returncode == 0
    base2 = git(repo, "rev-parse", "HEAD")
    assert rodar(repo, "diff", base2, commitar(repo, "feat: o SIGLAX")).returncode == 1


def test_o_nivel_2_nao_mede_a_historia_ja_publicada(repo: Path) -> None:
    commitar(repo, "fix: o subagente refez")
    p = rodar(repo, "historia", "HEAD")
    assert p.returncode == 0, saida(p)


def test_texto_do_pr_mede_os_dois_niveis(repo: Path) -> None:
    assert rodar(repo, "texto", entrada="título\ncorpo limpo\n").returncode == 0
    assert rodar(repo, "texto", entrada="o subagente refez\n").returncode == 1
    assert rodar(repo, "texto", entrada=f"{CANARIO}\n").returncode == 1


# ---------------------------------------------------------------------------
# O que pode sair num push, e o que o servidor guarda
# ---------------------------------------------------------------------------


def _linha_de_push(origem: str, sha: str, destino: str) -> str:
    return f"{origem} {sha} {destino} {ZERO}\n"


def empurrar(
    repo: Path, origem: str, sha: str, destino: str,
) -> subprocess.CompletedProcess[str]:
    return rodar(repo, "pre-push", "origin", entrada=_linha_de_push(origem, sha, destino))


def test_push_para_ramo_fora_da_lista_de_publicaveis_reprova_s9(repo: Path) -> None:
    sha = commitar(repo)
    p = empurrar(repo, "refs/heads/dev", sha, "refs/heads/voo/x")
    assert p.returncode == 1
    assert "fora da lista de publicáveis" in p.stdout


def test_push_de_referencia_que_nunca_sai_da_maquina_reprova(repo: Path) -> None:
    sha = commitar(repo)
    git(repo, "update-ref", "refs/interno/x", sha)
    p = empurrar(repo, "refs/interno/x", sha, "refs/heads/dev")
    assert p.returncode == 1
    assert "nunca sai da máquina" in p.stdout


def test_push_para_o_ramo_de_fecho_passa(repo: Path) -> None:
    sha = commitar(repo)
    p = empurrar(repo, "refs/heads/dev", sha, "refs/heads/fecho/2026-09-28")
    assert p.returncode == 0, saida(p)


def test_push_de_sha_cru_para_o_dev_passa_e_para_o_resto_reprova(repo: Path) -> None:
    sha = commitar(repo)
    assert empurrar(repo, sha, sha, "refs/heads/dev").returncode == 0
    assert empurrar(repo, sha, sha, "refs/heads/outro").returncode == 1


def test_apagar_no_remoto_e_permitido(repo: Path) -> None:
    apagar = f"(delete) {ZERO} refs/heads/qualquer {'1' * 40}\n"
    p = rodar(repo, "pre-push", "origin", entrada=apagar)
    assert p.returncode == 0, saida(p)


def test_o_destino_publicavel_vem_do_git_config(repo: Path) -> None:
    sha = commitar(repo)
    git(repo, "config", "autoria.publicavel", "refs/heads/voo/*")
    entrada = _linha_de_push("refs/heads/dev", sha, "refs/heads/voo/x")
    assert rodar(repo, "pre-push", "origin", entrada=entrada).returncode == 0
    entrada = _linha_de_push("refs/heads/dev", sha, "refs/heads/dev")
    assert rodar(repo, "pre-push", "origin", entrada=entrada).returncode == 1


def test_o_push_mede_o_nivel_1_na_historia_inteira_e_o_nivel_2_so_no_novo(repo: Path) -> None:
    antigo = commitar(repo, "fix: o subagente de antes")
    novo = commitar(repo, "fix: sem nada")
    git(repo, "update-ref", "refs/remotes/origin/dev", antigo)
    entrada = _linha_de_push("refs/heads/dev", novo, "refs/heads/dev")
    assert rodar(repo, "pre-push", "origin", entrada=entrada).returncode == 0
    pior = commitar(repo, "fix: o subagente de agora")
    entrada = _linha_de_push("refs/heads/dev", pior, "refs/heads/dev")
    assert rodar(repo, "pre-push", "origin", entrada=entrada).returncode == 1


def test_push_com_commit_de_fora_do_mailmap_reprova(repo: Path) -> None:
    sha = commitar(repo, autor=DE_FORA)
    p = empurrar(repo, "refs/heads/dev", sha, "refs/heads/dev")
    assert p.returncode == 1


@pytest.fixture()
def servidor(repo: Path, tmp_path: Path) -> Path:
    nu = tmp_path / "nu.git"
    subprocess.run(["git", "init", "-q", "--bare", str(nu)], check=True, env=_ambiente())
    git(repo, "remote", "add", "origin", str(nu))
    return nu


def test_o_servidor_so_com_heads_tags_e_pull_passa(repo: Path, servidor: Path) -> None:
    git(repo, "push", "-q", "origin", "dev:refs/heads/dev")
    git(repo, "push", "-q", "origin", "dev:refs/pull/1/head")
    p = rodar(repo, "remoto", "origin")
    assert p.returncode == 0, saida(p)


def test_referencia_estranha_no_servidor_reprova_sem_o_nome(repo: Path, servidor: Path) -> None:
    git(repo, "push", "-q", "origin", f"dev:refs/{CANARIO}/x")
    p = rodar(repo, "remoto", "origin")
    assert p.returncode == 1
    assert "fora de heads, tags e pull" in p.stdout
    assert CANARIO not in saida(p)


def test_ramo_do_servidor_com_o_canario_reprova_sem_o_nome(repo: Path, servidor: Path) -> None:
    git(repo, "push", "-q", "origin", f"dev:refs/heads/x-{CANARIO}")
    p = rodar(repo, "remoto", "origin")
    assert p.returncode == 1
    assert CANARIO not in saida(p)


def test_uso_errado_sai_2(repo: Path) -> None:
    assert rodar(repo).returncode == 2
    assert rodar(repo, "diff", "so-um").returncode == 2
    assert rodar(repo, "inexistente").returncode == 2


# ---------------------------------------------------------------------------
# O instalador e o gancho de pre-push, de ponta a ponta
# ---------------------------------------------------------------------------


@pytest.fixture()
def casa(repo: Path, tmp_path: Path) -> Path:
    """O repositório de brinquedo com a régua, os ganchos e o instalador copiados."""
    import shutil

    (repo / "scripts").mkdir()
    shutil.copy2(REGUA, repo / "scripts" / "check_autoria.py")
    shutil.copy2(RAIZ / "scripts" / "instalar-hooks.sh", repo / "scripts" / "instalar-hooks.sh")
    shutil.copytree(RAIZ / "scripts" / "hooks", repo / "scripts" / "hooks")
    git(repo, "add", "scripts")
    commitar(repo, "chore: a régua e os ganchos")
    return repo


def instalar(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = _ambiente({"HOME": str(repo.parent)})
    return subprocess.run(
        ["bash", "scripts/instalar-hooks.sh", *args],
        cwd=repo, env=env, capture_output=True, text=True,
    )


def git_vivo(repo: Path, *args: str, lista: str | None = LISTA) -> subprocess.CompletedProcess[str]:
    """git COM os ganchos do repositório ligados, como na máquina de quem empurra."""
    extra = {"AUTORIA_VEDADOS": lista} if lista is not None else {}
    return subprocess.run(
        ["git", *args], cwd=repo, env=_ambiente(extra), capture_output=True, text=True,
    )


def test_o_instalador_copia_o_pre_push_e_grava_a_politica(casa: Path) -> None:
    p = instalar(casa)
    assert p.returncode == 0, saida(p)
    gancho = casa / ".git" / "hooks" / "pre-push"
    assert gancho.is_file() and not gancho.is_symlink()
    assert os.access(gancho, os.X_OK)
    assert gancho.read_bytes() == (casa / "scripts" / "hooks" / "pre-push").read_bytes()
    assert git(casa, "config", "--get", "autoria.politica") == "scripts/check_autoria.py"


def test_o_instalador_e_idempotente_e_o_conferir_diz_o_que_faria(casa: Path) -> None:
    antes = instalar(casa, "--conferir")
    assert antes.returncode == 1 and "faria" in antes.stdout
    assert not (casa / ".git" / "hooks" / "pre-push").exists(), "o --conferir mexeu"
    assert instalar(casa).returncode == 0
    depois = instalar(casa, "--conferir")
    assert depois.returncode == 0, saida(depois)
    assert "nada a fazer" in depois.stdout
    assert instalar(casa).returncode == 0


def test_numa_worktree_o_gancho_vai_para_o_diretorio_comum(casa: Path, tmp_path: Path) -> None:
    arvore = tmp_path / "voo"
    git(casa, "worktree", "add", "-q", "-b", "voo/x", str(arvore))
    p = instalar(arvore)
    assert p.returncode == 0, saida(p)
    assert (casa / ".git" / "hooks" / "pre-push").is_file()
    assert git(arvore, "config", "--get", "autoria.politica") == "scripts/check_autoria.py"


def test_com_core_hooks_path_so_grava_a_politica_e_nao_escreve_no_caminho_global(
    casa: Path, tmp_path: Path,
) -> None:
    global_ = tmp_path / "ganchos-globais"
    global_.mkdir()
    git(casa, "config", "core.hooksPath", str(global_))
    p = instalar(casa)
    assert p.returncode == 0, saida(p)
    assert list(global_.iterdir()) == [], "o instalador escreveu no caminho global"
    assert not (casa / ".git" / "hooks" / "pre-push").exists()
    assert git(casa, "config", "--get", "autoria.politica") == "scripts/check_autoria.py"


def test_gancho_de_outra_autoria_nao_e_sobrescrito(casa: Path) -> None:
    alheio = casa / ".git" / "hooks" / "pre-push"
    alheio.write_text("#!/bin/sh\necho meu\n", encoding="utf-8")
    p = instalar(casa)
    assert p.returncode == 1 and "RECUSADO" in p.stderr
    assert alheio.read_text(encoding="utf-8") == "#!/bin/sh\necho meu\n"


def test_link_morto_no_lugar_do_gancho_e_trocado_por_copia(casa: Path) -> None:
    gancho = casa / ".git" / "hooks" / "pre-push"
    gancho.symlink_to("/nao/existe/mais/pre-push")
    assert instalar(casa).returncode == 0
    assert gancho.is_file() and not gancho.is_symlink()


def _com_servidor(casa: Path, tmp_path: Path) -> Path:
    nu = tmp_path / "nu.git"
    subprocess.run(["git", "init", "-q", "--bare", str(nu)], check=True, env=_ambiente())
    git(casa, "remote", "add", "origin", str(nu))
    return nu


def test_o_gancho_instalado_barra_e_libera_o_push_de_verdade(casa: Path, tmp_path: Path) -> None:
    _com_servidor(casa, tmp_path)
    assert instalar(casa).returncode == 0
    commitar(casa, "feat: limpo")
    liberado = git_vivo(casa, "push", "origin", "dev:refs/heads/fecho/2026-09-28")
    assert liberado.returncode == 0, saida(liberado)
    fora = git_vivo(casa, "push", "origin", "dev:refs/heads/voo/x")
    assert fora.returncode != 0 and "fora da lista de publicáveis" in saida(fora)
    commitar(casa, f"feat: {CANARIO}")
    sujo = git_vivo(casa, "push", "origin", "dev:refs/heads/fecho/outro")
    assert sujo.returncode != 0 and CANARIO not in saida(sujo)


def test_o_gancho_copiado_sobrevive_ao_desaparecimento_da_arvore_que_o_instalou(
    casa: Path, tmp_path: Path,
) -> None:
    """Um link para `scripts/hooks/` desligaria a política calado; a cópia não."""
    import shutil

    _com_servidor(casa, tmp_path)
    assert instalar(casa).returncode == 0
    shutil.rmtree(casa / "scripts" / "hooks")
    commitar(casa, f"feat: {CANARIO}")
    p = git_vivo(casa, "push", "origin", "dev:refs/heads/fecho/x")
    assert p.returncode != 0, "a política se desligou calada sem a pasta de ganchos"


def test_o_gancho_sem_a_regua_na_arvore_reprova_e_nao_passa(casa: Path, tmp_path: Path) -> None:
    _com_servidor(casa, tmp_path)
    assert instalar(casa).returncode == 0
    (casa / "scripts" / "check_autoria.py").unlink()
    commitar(casa, "feat: limpo")
    p = git_vivo(casa, "push", "origin", "dev:refs/heads/fecho/x")
    assert p.returncode != 0
    assert "política não medida" in saida(p)


# ---------------------------------------------------------------------------
# O gancho de commit-msg: o vocabulário vem da mesma lista, nunca de um literal
# ---------------------------------------------------------------------------


def commit_msg(
    casa: Path, texto: str, lista: str | None = LISTA,
) -> tuple[subprocess.CompletedProcess[str], str]:
    arquivo = casa.parent / "MENSAGEM"
    arquivo.write_text(texto, encoding="utf-8")
    extra = {"AUTORIA_VEDADOS": lista} if lista is not None else {}
    p = subprocess.run(
        ["bash", "scripts/hooks/commit-msg", str(arquivo)],
        cwd=casa, env=_ambiente(extra), capture_output=True, text=True,
    )
    return p, arquivo.read_text(encoding="utf-8")


def test_o_commit_msg_barra_o_assunto_com_termo_da_lista(casa: Path) -> None:
    p, _ = commit_msg(casa, f"feat: {FORNECEDOR.replace('-', ' ')} entra\n")
    assert p.returncode == 1, saida(p)
    assert FORNECEDOR.replace("-", " ") not in saida(p)


def test_o_commit_msg_tira_do_corpo_a_linha_com_termo_e_a_atribuicao_de_fora(casa: Path) -> None:
    """O termo vem da LISTA: um fornecedor que nenhum literal do gancho conhece sai igual."""
    texto = (
        "feat: limpo\n\n"
        "linha que fica\n"
        f"linha com {CANARIO} sai\n"
        f"o {FORNECEDOR.replace('-', ' ')} também sai\n"
        f"{COAUTORIA}: Fulana <fulana@fora.test>\n"
        "o agente de pareamento fica"
    )
    p, depois = commit_msg(casa, texto)
    assert p.returncode == 0, saida(p)
    assert depois.splitlines() == [
        "feat: limpo", "", "linha que fica",
        "o agente de pareamento fica",
    ]


def test_o_commit_msg_sem_a_lista_nao_mexe_e_avisa(casa: Path) -> None:
    texto = f"feat: limpo\n\nlinha com {CANARIO}\n"
    p, depois = commit_msg(casa, texto, lista="")
    assert p.returncode == 0, saida(p)
    assert depois == texto
    assert "a lista de termos não chegou" in p.stderr


def test_o_commit_msg_nao_carrega_vocabulario_proprio() -> None:
    """Nenhuma lista de nomes no gancho: quem decide é a régua, pela lista de fora."""
    gancho = (RAIZ / "scripts" / "hooks" / "commit-msg").read_text(encoding="utf-8")
    assert "check_autoria.py" in gancho and " texto " in gancho
    assert "FERRAMENTA" not in gancho
