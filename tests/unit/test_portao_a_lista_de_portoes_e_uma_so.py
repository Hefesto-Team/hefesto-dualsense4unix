"""O PORTÃO DO PORTÃO — a lista de portões desta casa é UMA SÓ.

Desde 10/10/2026 (O-CI-CHAMA-OS-PORTOES-PELO-NOME-01) o comando de cada portão mora num
lugar só, a tabela do `scripts/portoes.sh`, e o CI o chama pelo nome:
`bash scripts/portoes.sh --so <ids>`. Esta régua cobra as três metades disso:

- todo id de um `--so` existe na tabela;
- todo id da tabela aparece num `--so` do CI, ou está declarado `FORA-DO-CI` com o motivo,
  ou é de um script declarado `ARGUMENTO-DO-EVENTO` (o CI o chama direto, com o argumento
  que só o evento sabe);
- nenhum `run:` chama direto um comando que a tabela já tem, salvo o `ARGUMENTO-DO-EVENTO`
  com argumento diferente do da tabela. Comando relistado no `ci.yml` é a cópia que já
  divergiu calada duas vezes (o `validar-caducos.py` e o
  `portao_a_casa_sabe_e_o_produto_nao_faz`).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTOES_SH = RAIZ / "scripts" / "portoes.sh"
CI_YML = RAIZ / ".github" / "workflows" / "ci.yml"
# O CI tem dois arquivos que rodam portão da lista: o `ci.yml` e o `autoria.yml`, que
# carrega a régua única de autoria (`scripts/check_autoria.py`).
AUTORIA_YML = RAIZ / ".github" / "workflows" / "autoria.yml"

_FERRAMENTAS = ("ruff", "mypy", "shellcheck", "pytest", "pre-commit")

_O_MOTOR = "scripts/portoes.sh"

_RE_SCRIPT = re.compile(r"scripts/[A-Za-z0-9_./-]+\.(?:py|sh)")

#: o `portoes.sh --so <ids>` num comando de shell; os ids vão até a próxima opção ou operador
_RE_SO = re.compile(
    r"(?:^|[\s;&|(])(?:bash\s+)?(?:\./)?scripts/portoes\.sh\s+--so((?:\s+[a-z0-9][a-z0-9-]*)+)"
)


def _sem_comentario(linha: str) -> str:
    """Corta o comentário de shell/YAML, preservando `#` colado (cor, âncora)."""
    if linha.lstrip().startswith("#"):
        return ""
    return re.sub(r"\s#.*$", "", linha)


def _fichas(texto: str) -> set[str]:
    """As fichas de portão de um pedaço de linha de comando."""
    achadas = set(_RE_SCRIPT.findall(texto))
    for ferramenta in _FERRAMENTAS:
        if re.search(rf"(?<![\w-]){re.escape(ferramenta)}(?![\w-])", texto):
            achadas.add(ferramenta)
    return achadas


def comandos_do_ci(texto_ci: str) -> list[str]:
    """Cada comando que o CI EXECUTA, um por linha lógica do ``run:`` (o dobrado vira uma)."""
    saida: list[str] = []
    linhas = texto_ci.splitlines()
    i = 0
    while i < len(linhas):
        m = re.match(r"^(\s*)(?:-\s*)?run:\s*(.*)$", linhas[i])
        if not m:
            i += 1
            continue
        recuo = len(m.group(1))
        resto = m.group(2).strip()
        if resto in {"|", ">", "|-", ">-", "|+", ">+"} or resto == "":
            dobrado = resto.startswith(">")
            corpo: list[str] = []
            i += 1
            while i < len(linhas):
                bruta = linhas[i]
                if bruta.strip() and (len(bruta) - len(bruta.lstrip())) <= recuo:
                    break
                corpo.append(_sem_comentario(bruta))
                i += 1
            if dobrado:
                saida.append(" ".join(" ".join(corpo).split()))
            else:
                juntas = "\n".join(corpo).replace("\\\n", " ")
                saida.extend(" ".join(x.split()) for x in juntas.splitlines() if x.strip())
        else:
            saida.append(" ".join(_sem_comentario(resto).split()))
            i += 1
    return saida


def fichas_do_ci(texto_ci: str) -> set[str]:
    """O que o CI de fato RODA pelo próprio comando -- só o conteúdo dos blocos ``run:``."""
    fichas: set[str] = set()
    for comando in comandos_do_ci(texto_ci):
        fichas |= _fichas(comando)
    return fichas


def ids_do_so(comando: str) -> list[str]:
    """Os ids que um comando pede ao ``portoes.sh --so``, na ordem."""
    ids: list[str] = []
    for m in _RE_SO.finditer(comando):
        ids.extend(m.group(1).split())
    return ids


def _linhas_declaradas(texto_sh: str) -> list[str]:
    """A tabela crua de ``portoes.sh --listar``, sem rodar o script."""
    saida: list[str] = []
    dentro = None
    for linha in texto_sh.splitlines():
        if re.match(r"^\s*cat <<'TABELA'\s*$", linha):
            dentro = "PORTAO"
            continue
        if re.match(r"^\s*cat <<'DIV'\s*$", linha):
            dentro = "DIV"
            continue
        if linha.strip() in {"TABELA", "DIV"}:
            dentro = None
            continue
        if dentro == "PORTAO" and linha.strip():
            saida.append("PORTAO|" + linha.strip())
        elif dentro == "DIV" and linha.strip():
            saida.append(linha.strip())
    return saida


def tabela(texto_sh: str) -> dict[str, tuple[str, str, str]]:
    """``id -> (camada, runner, argv)`` das linhas de portão da tabela."""
    saida: dict[str, tuple[str, str, str]] = {}
    for linha in _linhas_declaradas(texto_sh):
        campos = linha.split("|")
        if campos[0] != "PORTAO" or len(campos) < 5 or campos[1].startswith("#"):
            continue
        saida[campos[2]] = (campos[1], campos[3], " ".join(campos[4].split()))
    return saida


def declaracoes(texto_sh: str, tipo: str) -> dict[str, str]:
    """``chave -> motivo`` das linhas ``<tipo>|chave|motivo`` de ``_DIVERGENCIAS``."""
    saida: dict[str, str] = {}
    for linha in _linhas_declaradas(texto_sh):
        campos = linha.split("|", 2)
        if campos[0] == tipo and len(campos) == 3:
            assert campos[2].strip(), f"{tipo} sem motivo escrito: {campos[1]}"
            saida[campos[1]] = campos[2]
    return saida


def _alvo(runner: str, argv: str) -> str:
    """O que identifica o portão num comando: o script, o teste ou o binário."""
    return argv.split()[0] if argv else ""


def _chama_direto(comando: str, runner: str, argv: str) -> bool:
    """Este comando executa o portão sem passar pelo ``--so``?"""
    if _RE_SO.search(comando):
        return False
    if runner == "bin":
        return argv in comando
    tokens = comando.split()
    return _alvo(runner, argv) in tokens


def _mesmo_argv(comando: str, argv: str) -> bool:
    """Do script em diante, o comando é EXATAMENTE o argv da tabela (o ``-q`` não conta)?"""
    tokens = comando.split()
    alvo = argv.split()[0]
    if alvo not in tokens:
        return False
    resto = [t for t in tokens[tokens.index(alvo):] if t != "-q"]
    return resto == argv.split()


def _ids_do_comando(alvo: str, texto_sh: str | None) -> set[str]:
    if texto_sh is None:
        texto_sh = PORTOES_SH.read_text(encoding="utf-8")
    return {
        id_ for id_, (_, _, argv) in tabela(texto_sh).items()
        if argv == alvo or argv.split()[0] == alvo
    }


def _chama(alvo: str, ids: set[str], comando: str) -> bool:
    if alvo in comando and not _RE_SO.search(comando):
        return True
    return bool(ids & set(ids_do_so(comando)))


def o_ci_chama(comando_da_tabela: str, texto_ci: str, texto_sh: str | None = None) -> bool:
    """O CI executa este comando, direto ou pelo nome? Para a régua que cobra UM portão no CI.

    ``comando_da_tabela`` é o argv da linha (``scripts/gerar-mapa.py --check``) ou só o
    script; ele conta como chamado quando um ``run:`` o escreve, ou quando um
    ``portoes.sh --so`` nomeia um id cujo argv é este (ou começa por este script).
    """
    alvo = " ".join(comando_da_tabela.split())
    ids = _ids_do_comando(alvo, texto_sh)
    return any(_chama(alvo, ids, comando) for comando in comandos_do_ci(texto_ci))


def o_passo_chama(comando_da_tabela: str, run: object, texto_sh: str | None = None) -> bool:
    """O mesmo, sobre o ``run`` de UM passo já lido pelo YAML (o dobrado já vem numa linha)."""
    alvo = " ".join(comando_da_tabela.split())
    ids = _ids_do_comando(alvo, texto_sh)
    texto = str(run or "").replace("\\\n", " ")
    linhas = [" ".join(_sem_comentario(x).split()) for x in texto.splitlines()]
    return any(_chama(alvo, ids, linha) for linha in linhas if linha) or _chama(
        alvo, set(), " ".join(str(run or "").split()))


def confere(texto_sh: str, texto_ci: str) -> list[str]:
    """As queixas. Lista vazia significa uma lista só."""
    portoes = tabela(texto_sh)
    fora_do_ci = declaracoes(texto_sh, "FORA-DO-CI")
    fora_do_local = declaracoes(texto_sh, "FORA-DO-LOCAL")
    do_evento = declaracoes(texto_sh, "ARGUMENTO-DO-EVENTO")
    comandos = comandos_do_ci(texto_ci)
    pedidos = [id_ for comando in comandos for id_ in ids_do_so(comando)]

    queixas: list[str] = []
    # 1. todo id de `--so` existe na tabela (o script recusa com rc 2, mas só na hora de rodar)
    for id_ in sorted(set(pedidos) - set(portoes)):
        queixas.append(
            f"{id_}: o CI pede `portoes.sh --so {id_}` e a tabela não tem esse id. "
            "Ou o id voltou à tabela, ou sai do `--so`."
        )
    # 2. todo id da tabela roda no CI pelo nome, ou está declarado
    for id_, (camada, runner, argv) in portoes.items():
        if camada == "suite" or id_ in pedidos:
            continue
        alvo = _alvo(runner, argv)
        if id_ in fora_do_ci or alvo in fora_do_ci:
            continue
        if alvo in do_evento and any(alvo in c.split() for c in comandos):
            continue
        queixas.append(
            f"{id_}: está na tabela de portoes.sh e nenhum `portoes.sh --so` do CI o nomeia. "
            "Ou entra no `--so` de um job, ou vira uma linha FORA-DO-CI com o motivo."
        )
    # 3. nenhum `run:` relista um comando da tabela
    for comando in comandos:
        for id_, (camada, runner, argv) in portoes.items():
            if camada == "suite" or not _chama_direto(comando, runner, argv):
                continue
            alvo = _alvo(runner, argv)
            if alvo in do_evento and not _mesmo_argv(comando, argv):
                continue
            queixas.append(
                f"{id_}: o CI chama direto `{comando}`, e esse comando já mora na tabela. "
                f"Troque por `bash scripts/portoes.sh --so {id_}`; se o CI precisa de um "
                "argumento que só o evento sabe, declare o script ARGUMENTO-DO-EVENTO."
            )
    # 4. o que o CI roda pelo próprio comando e a tabela não tem é FORA-DO-LOCAL declarado
    locais: set[str] = set()
    for _, _, argv in portoes.values():
        locais |= _fichas(argv)
    # o próprio `portoes.sh` é o motor do `--so`, não um portão
    so_no_ci = fichas_do_ci(texto_ci) - locais - set(fora_do_local) - set(do_evento) - {_O_MOTOR}
    for ficha in sorted(so_no_ci):
        queixas.append(
            f"{ficha}: RODA NO CI e NÃO está na tabela de portoes.sh. "
            "Ou entra na tabela, ou vira uma linha FORA-DO-LOCAL com o motivo. "
            "Foi assim que o validar-caducos.py atravessou uma leva inteira."
        )
    for ficha in sorted(set(fora_do_local) & locais):
        queixas.append(
            f"{ficha}: declarado FORA-DO-LOCAL e mesmo assim presente na tabela. "
            "A declaração e a tabela se contradizem."
        )
    return queixas


def _texto_do_ci() -> str:
    return CI_YML.read_text(encoding="utf-8") + "\n" + AUTORIA_YML.read_text(encoding="utf-8")


def test_a_lista_local_e_a_do_ci_sao_a_mesma() -> None:
    queixas = confere(PORTOES_SH.read_text(encoding="utf-8"), _texto_do_ci())
    assert not queixas, (
        f"A lista de portões divergiu em {len(queixas)} ponto(s):\n"
        + "\n".join("  - " + q for q in queixas)
    )


def test_o_ci_chama_os_portoes_pelo_nome() -> None:
    """A âncora: sem `--so` no CI, a regra 2 reprovaria tudo, mas a 3 passaria calada."""
    comandos = comandos_do_ci(CI_YML.read_text(encoding="utf-8"))
    pedidos = [id_ for c in comandos for id_ in ids_do_so(c)]
    assert len(set(pedidos)) >= 60, f"só {len(set(pedidos))} ids pedidos por `--so` no ci.yml"


def test_todo_portao_declarado_existe_no_disco() -> None:
    """Portão declarado e ausente é portão cego, e portão cego é pior que nenhum."""
    portoes = tabela(PORTOES_SH.read_text(encoding="utf-8"))
    ausentes = sorted(
        argv.split()[0] for _, runner, argv in portoes.values()
        if runner in {"py", "bash", "pytest"} and not (RAIZ / argv.split()[0]).exists()
    )
    assert not ausentes, (
        "portões declarados em portoes.sh e ausentes da árvore: " + ", ".join(ausentes))


def test_toda_declaracao_do_evento_tem_chamador_direto_no_ci() -> None:
    """A isenção da regra 3 só vale enquanto o CI chama o script com o argumento do evento."""
    texto_sh = PORTOES_SH.read_text(encoding="utf-8")
    comandos = comandos_do_ci(_texto_do_ci())
    for script, motivo in declaracoes(texto_sh, "ARGUMENTO-DO-EVENTO").items():
        assert any(script in c.split() for c in comandos), (
            f"{script} está declarado ARGUMENTO-DO-EVENTO e nenhum `run:` o chama: "
            "APAGUE a declaração."
        )
        assert re.search(r"\d{2}/\d{2}/\d{4}", motivo), f"a declaração de {script} não tem data"


def test_listar_imprime_a_mesma_tabela_que_o_script_roda() -> None:
    """`--listar` é a superfície que este teste lê; se ela mentir, o teste mente."""
    saida = subprocess.run(
        ["bash", str(PORTOES_SH), "--listar"],
        check=True,
        capture_output=True,
        text=True,
        cwd=RAIZ,
    ).stdout.splitlines()
    assert [linha for linha in saida if linha.strip()] == _linhas_declaradas(
        PORTOES_SH.read_text(encoding="utf-8")
    )


_SH_DUBLE = """#!/usr/bin/env bash
_LISTA() {
  cat <<'TABELA'
{tabela}
TABELA
}
_DIVERGENCIAS() {
  cat <<'DIV'
{div}
DIV
}
"""

_CI_DUBLE = """jobs:
  falso:
    steps:
{passos}
"""


def _duble(tabela_: list[str], div: list[str], passos: list[str]) -> tuple[str, str]:
    sh = _SH_DUBLE.replace("{tabela}", "\n".join(tabela_)).replace("{div}", "\n".join(div))
    ci = _CI_DUBLE.replace("{passos}", "\n".join(f"      - run: {p}" for p in passos))
    return sh, ci


_DUAS = ["rapido|um|py|scripts/validar-um.py --all", "rapido|dois|bash|scripts/check_dois.sh"]
_PELO_NOME = "bash scripts/portoes.sh --so um dois"


def test_a_regua_sabe_passar_quando_o_ci_chama_pelo_nome() -> None:
    sh, ci = _duble(_DUAS, [], [_PELO_NOME])
    assert confere(sh, ci) == []


def test_a_linha_nova_da_tabela_sem_so_nem_declaracao_reprova() -> None:
    """O primeiro caso da sprint: a tabela ganhou um portão e nenhum job o pede."""
    sh, ci = _duble([*_DUAS, "rapido|terceiro|py|scripts/check_terceiro.py"], [], [_PELO_NOME])
    queixas = confere(sh, ci)
    assert len(queixas) == 1 and queixas[0].startswith("terceiro:"), queixas


def test_o_run_que_relista_um_portao_da_tabela_reprova() -> None:
    """O segundo caso da sprint: um `run: python3 scripts/<portão>.py` plantado no CI."""
    sh, ci = _duble(_DUAS, [], [_PELO_NOME, "python3 scripts/validar-um.py --all"])
    queixas = confere(sh, ci)
    assert len(queixas) == 1 and "chama direto" in queixas[0], queixas


def test_o_run_direto_reprova_mesmo_com_o_id_no_so() -> None:
    """Rodar duas vezes não é desculpa: a cópia do comando é o defeito, não a falta dele."""
    sh, ci = _duble(_DUAS, [], [_PELO_NOME, "bash scripts/check_dois.sh"])
    assert any(q.startswith("dois:") and "chama direto" in q for q in confere(sh, ci))


def test_o_id_que_a_tabela_nao_tem_reprova() -> None:
    sh, ci = _duble(_DUAS, [], ["bash scripts/portoes.sh --so um dois sumiu"])
    queixas = confere(sh, ci)
    assert len(queixas) == 1 and queixas[0].startswith("sumiu:"), queixas


def test_a_declaracao_fora_do_ci_passa() -> None:
    sh, ci = _duble(
        _DUAS, ["FORA-DO-CI|scripts/check_dois.sh|pergunta à máquina, e no runner não há o quê"],
        ["bash scripts/portoes.sh --so um"],
    )
    assert confere(sh, ci) == []


def test_o_argumento_do_evento_passa_so_com_argumento_diferente() -> None:
    div = ["ARGUMENTO-DO-EVENTO|scripts/validar-um.py|10/10/2026: o ref vem do evento"]
    so_dois = "bash scripts/portoes.sh --so dois"
    sh, ci = _duble(_DUAS, div, [so_dois, 'python3 scripts/validar-um.py --contra "$REF"'])
    assert confere(sh, ci) == []
    sh, ci = _duble(_DUAS, div, [so_dois, "python3 scripts/validar-um.py --all"])
    assert any("chama direto" in q for q in confere(sh, ci))


def test_o_que_so_roda_no_ci_ainda_reprova_sem_fora_do_local() -> None:
    """O caso literal de 24/08: o validar-caducos.py só existia num dos lados."""
    caducos = "python3 scripts/validar-caducos.py --all"
    sh, ci = _duble(_DUAS, [], [_PELO_NOME, caducos])
    queixas = confere(sh, ci)
    assert len(queixas) == 1
    assert "scripts/validar-caducos.py" in queixas[0] and "RODA NO CI" in queixas[0]
    sh, ci = _duble(
        _DUAS, ["FORA-DO-LOCAL|scripts/validar-caducos.py|mexe no sistema vivo da máquina dela"],
        [_PELO_NOME, caducos],
    )
    assert confere(sh, ci) == []


def test_o_comentario_e_o_bloco_dobrado() -> None:
    """Comentário não roda; o `run: >-` em várias linhas é UM comando."""
    ci = (
        "jobs:\n  x:\n    steps:\n"
        "      # veja scripts/check_dois.sh\n"
        "      - run: >-\n"
        "          bash scripts/portoes.sh --so\n"
        "          um dois\n"
    )
    sh, _ = _duble(_DUAS, [], [])
    assert confere(sh, ci) == []


def test_a_ferramenta_conta_dos_dois_lados() -> None:
    sh, ci = _duble(["rapido|ruff|bin|ruff check src/ tests/"], [], ["ruff check src/ tests/"])
    assert any(q.startswith("ruff:") and "chama direto" in q for q in confere(sh, ci))
    sh_sem, ci_com = _duble([], [], ["mypy src/hefesto_dualsense4unix"])
    queixas = confere(sh_sem, ci_com)
    assert len(queixas) == 1 and queixas[0].startswith("mypy:")


def test_o_ci_chama_ve_o_comando_direto_e_pelo_nome() -> None:
    sh, _ = _duble(_DUAS, [], [])
    _, pelo_nome = _duble([], [], ["bash scripts/portoes.sh --so um"])
    _, direto = _duble([], [], ["python3 scripts/validar-um.py --all"])
    _, nada = _duble([], [], ["bash scripts/portoes.sh --so dois"])
    assert o_ci_chama("scripts/validar-um.py --all", pelo_nome, sh)
    assert o_ci_chama("scripts/validar-um.py", pelo_nome, sh)
    assert o_ci_chama("scripts/validar-um.py --all", direto, sh)
    assert not o_ci_chama("scripts/validar-um.py --all", nada, sh)


def test_a_regua_de_autoria_roda_nos_dois_lados_e_o_portao_velho_saiu() -> None:
    """O `autoria-historia` e o `autoria-arvore` estão na lista; o `historia-sem-ia` saiu."""
    ids = tabela(PORTOES_SH.read_text(encoding="utf-8"))
    assert "autoria-historia" in ids and "autoria-arvore" in ids
    assert "historia-sem-ia" not in ids
    do_ci = fichas_do_ci(_texto_do_ci())
    assert "scripts/check_autoria.py" in do_ci
    assert "scripts/check_a_historia_nao_tem_ia.py" not in do_ci


# --- o `--so` do próprio script, numa cópia com três portões de mentira ----------------------


@pytest.fixture
def portoes_de_mentira(tmp_path: Path) -> Path:
    texto = PORTOES_SH.read_text(encoding="utf-8")
    inicio = texto.index("_LISTA() {\n  cat <<'TABELA'\n")
    fim = texto.index("\nTABELA\n", inicio)
    linhas = "\n".join(
        f"{camada}|{id_}|bash|scripts/{id_}.sh"
        for camada, id_ in (("rapido", "um"), ("completo", "dois"), ("rapido", "terceiro"))
    )
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "portoes.sh").write_text(
        texto[:inicio] + "_LISTA() {\n  cat <<'TABELA'\n" + linhas + texto[fim:], encoding="utf-8"
    )
    for id_ in ("um", "dois", "terceiro"):
        (tmp_path / "scripts" / f"{id_}.sh").write_text(f"echo rodou-{id_} >> \"$0.marca\"\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def _rodar(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    import os

    ambiente = {**os.environ, "CI": "1"}
    return subprocess.run(
        ["bash", str(raiz / "scripts" / "portoes.sh"), *args],
        cwd=raiz, capture_output=True, text=True, env=ambiente, timeout=120,
    )


def test_o_so_roda_os_nomeados_e_so_eles(portoes_de_mentira: Path) -> None:
    saida = _rodar(portoes_de_mentira, "--so", "dois", "um")
    assert saida.returncode == 0, saida.stdout + saida.stderr
    rodaram = sorted(p.name for p in (portoes_de_mentira / "scripts").glob("*.marca"))
    assert rodaram == ["dois.sh.marca", "um.sh.marca"]


def test_o_so_com_id_fora_da_tabela_sai_rc_2_nomeando(portoes_de_mentira: Path) -> None:
    saida = _rodar(portoes_de_mentira, "--so", "um", "nao-existe")
    assert saida.returncode == 2
    assert "nao-existe" in saida.stderr
    assert not list((portoes_de_mentira / "scripts").glob("*.marca")), "rodou antes de recusar"


def test_o_so_sem_id_sai_rc_2(portoes_de_mentira: Path) -> None:
    assert _rodar(portoes_de_mentira, "--so").returncode == 2


def test_o_so_nunca_abre_o_recibo_da_camada_completa(portoes_de_mentira: Path) -> None:
    """O recibo certifica a camada completa INTEIRA; um `--so` roda uma parte dela."""
    import shutil

    shutil.copy2(RAIZ / "scripts" / "recibo_da_medida.py", portoes_de_mentira / "scripts")
    saida = _rodar(portoes_de_mentira, "--so", "dois")
    assert saida.returncode == 0, saida.stdout + saida.stderr
    assert "portoes-completo" not in saida.stdout + saida.stderr, "o --so abriu o recibo"
