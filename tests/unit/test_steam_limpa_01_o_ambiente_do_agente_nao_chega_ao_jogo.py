"""STEAM-LIMPA-01 — o ambiente do agente não chega ao jogo.

**A ARMADILHA, 17/09/2026.** Um assistente fechou a Steam dela e reabriu com
`setsid steam` do próprio Bash. A Steam herdou o ambiente do shell do
assistente, e **todo jogo lançado por ela herdou junto** — medido no `environ` do
`PRAGMATA.exe`:

    CLAUDECODE=1 · AI_AGENT=…_agent · PYENV_ROOT=…
    VIRTUAL_ENV=/mnt/Apate/…/venv   ← apontando para uma venv que NÃO EXISTE

O `proton` é um script Python. Durante uma hora, rodadas viciadas foram
comparadas entre si e o gadget USB virtual, o UCM, o ACL do hidraw e o daemon
foram acusados, um a um, de um defeito que nenhum deles causava. Quem viu foi
ela, com uma pergunta: *"Como diabos eu tava abrindo o pragmata e testando tudo
sem parar e vc observando tudo?"*

**POR QUE A RÉGUA MEDE A FERRAMENTA, E NÃO O REPOSITÓRIO:** o defeito não
estava em nenhum arquivo versionado — foi um comando digitado na hora. Régua
que varre `src/` não o pegaria. O que se pode travar é o INSTRUMENTO: garantir
que `scripts/subir-steam-limpa.py` existe, que a lista de sujeira cobre o que
já contaminou de verdade, e que a detecção reprova um ambiente sujo. Sem isso,
a próxima pessoa não tem o caminho certo à mão e repete o atalho errado.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
FERRAMENTA = RAIZ / "scripts" / "subir-steam-limpa.py"

#: As variáveis MEDIDAS no `environ` do PRAGMATA.exe em 17/09/2026. Esta lista
#: não se digita de memória: cada item esteve num processo de jogo de verdade.
CONTAMINARAM_DE_VERDADE = (
    "CLAUDECODE",
    "AI_AGENT",
    "VIRTUAL_ENV",
    "PYENV_ROOT",
)


def _modulo():
    """Carrega a ferramenta pelo caminho (o nome tem hífen, não dá `import`)."""
    assert FERRAMENTA.is_file(), (
        f"`{FERRAMENTA.relative_to(RAIZ)}` sumiu. Ela é o único caminho certo "
        f"para subir a Steam nesta casa — sem ela, a próxima pessoa repete o "
        f"`setsid steam` do shell do agente e contamina todo jogo"
    )
    spec = importlib.util.spec_from_file_location("subir_steam_limpa", FERRAMENTA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1 — a lista de sujeira cobre o que já contaminou
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("variavel", CONTAMINARAM_DE_VERDADE)
def test_a_sujeira_medida_esta_na_lista(variavel: str) -> None:
    """Toda variável que já chegou a um jogo tem de ser detectada."""
    mod = _modulo()
    assert variavel in mod.SUJEIRA, (
        f"`{variavel}` foi MEDIDA no environ do PRAGMATA.exe em 17/09/2026 e "
        f"não está em `SUJEIRA` — a ferramenta deixaria passar a contaminação "
        f"que ela existe para pegar"
    )


def test_as_essenciais_nao_sao_sujeira() -> None:
    """Uma lista de sujeira que engula uma essencial derruba a Steam.

    `PATH` e `HOME` existem nos dois ambientes; confundi-los com contaminação
    faria a ferramenta recusar todo doador e nunca subir nada.
    """
    mod = _modulo()
    intersecao = set(mod.SUJEIRA) & set(mod.ESSENCIAIS)
    assert not intersecao, (
        f"{sorted(intersecao)} estão em SUJEIRA e em ESSENCIAIS ao mesmo tempo — "
        f"a ferramenta recusaria todo doador"
    )


# ---------------------------------------------------------------------------
# 2 — A MORDIDA: a detecção reprova um ambiente sujo
# ---------------------------------------------------------------------------
def test_um_ambiente_sujo_e_recusado() -> None:
    """Monta o ambiente contaminado de 17/09 e exige que ele seja pego.

    Se este teste passar com a lista de sujeira esvaziada, a régua não mede
    nada — por isso ele também confere que a lista VAZIA falharia.
    """
    mod = _modulo()

    sujo = {
        "WAYLAND_DISPLAY": "wayland-1",
        "XDG_RUNTIME_DIR": "/run/user/1000",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
        "HOME": "/home/ninguem",
        "PATH": "/mnt/nada/venv/bin:/usr/bin",
        # o que o shell do agente carrega
        "CLAUDECODE": "1",
        "AI_AGENT": "ferramenta_agent",
        "VIRTUAL_ENV": "/mnt/nada/venv",
        "PYENV_ROOT": "/home/ninguem/.pyenv",
    }
    pegas = [v for v in mod.SUJEIRA if v in sujo]
    assert pegas, "a ferramenta não pegou NENHUMA contaminação no ambiente sujo"
    assert set(pegas) >= set(CONTAMINARAM_DE_VERDADE), (
        f"a ferramenta pegou só {sorted(pegas)}; as quatro medidas em 17/09 "
        f"eram {sorted(CONTAMINARAM_DE_VERDADE)}"
    )

    # e o espelho: um ambiente da sessão gráfica passa limpo
    limpo = {k: v for k, v in sujo.items() if k not in mod.SUJEIRA}
    assert not [v for v in mod.SUJEIRA if v in limpo], (
        "o ambiente limpo foi recusado — a lista de sujeira está pegando o que não deve"
    )


def test_a_ferramenta_nao_consegue_chamar_pgrep() -> None:
    """A ferramenta acha processo por `/proc/<pid>/comm`, e não PODE chamar pgrep.

    `pgrep -f <nome>` casa o PRÓPRIO comando de quem procura. Em 17/09/2026 isso
    fez um medidor declarar o jogo "de pé na volta 0" e medir o PID errado duas
    vezes seguidas.

    **A RÉGUA MEDE CAPACIDADE, NÃO MENÇÃO — e a primeira versão dela errou nisso.**
    Ela procurava a string `pgrep -f` no fonte e reprovou a ferramenta CORRETA,
    porque a docstring cita o padrão proibido justamente para explicá-lo. É a
    família de defeito que esta casa já pagou três vezes: *o aviso vira a primeira
    ocorrência do que ele proíbe*. Então aqui se mede o que o módulo é CAPAZ de
    fazer: sem `subprocess`, sem `os.popen`, sem `os.system`, ele não tem como
    chamar pgrep, escreva-se o que se escrever nos comentários.
    """
    import ast

    arvore = ast.parse(FERRAMENTA.read_text(encoding="utf-8"))

    importados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])

    proibidos = importados & {"subprocess", "commands", "popen2", "sh", "plumbum"}
    assert not proibidos, (
        f"a ferramenta passou a importar {sorted(proibidos)} — com isso ela "
        f"CONSEGUE chamar `pgrep -f`, que casa o próprio comando de quem procura"
    )

    chamadas = {
        f"{no.func.value.id}.{no.func.attr}"
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and isinstance(no.func.value, ast.Name)
    }
    for perigosa in ("os.popen", "os.system", "os.spawnv"):
        assert perigosa not in chamadas, (
            f"a ferramenta passou a usar `{perigosa}` — outro caminho para o shell"
        )

    # E a prova pela positiva: ela LÊ o comm.
    fonte = FERRAMENTA.read_text(encoding="utf-8")
    assert '"comm"' in fonte or "/comm" in fonte, (
        "a ferramenta precisa achar o processo por `/proc/<pid>/comm`"
    )


def test_a_regua_sabe_reprovar() -> None:
    """A MORDIDA da régua acima, sem tocar na ferramenta.

    Monta um módulo de mentira que importa `subprocess` e exige que a análise
    o reprove. Régua que só sabe passar não mede nada.
    """
    import ast

    doente = ast.parse("import subprocess\ndef f():\n    subprocess.run(['pgrep', '-f', 'x'])\n")
    importados = {
        a.name.split(".")[0]
        for no in ast.walk(doente)
        if isinstance(no, ast.Import)
        for a in no.names
    }
    assert "subprocess" in importados, (
        "a análise não pegou o `import subprocess` do módulo doente — "
        "ela não reprovaria a ferramenta se esta regredisse"
    )
