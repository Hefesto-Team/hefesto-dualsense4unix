"""A-SUITE-NAO-PERGUNTA-AO-SOM-01 — a suíte não conversa com o servidor de som dela.

A PERGUNTA desta régua é a do enunciado: sob a suíte, um `pactl` sem dublê
chega ao servidor de som de quem roda? Ela responde pelo LADO DE FORA — o argv
que chegou ao dublê da sessão (`tests/conftest.py`, bloco SOM-DE-MENTIRA) —, e
não pelo texto do conftest.

O INVENTÁRIO QUE A MOTIVOU, medido em 13/09/2026 antes da cura, com espiões na
frente do `PATH` e montados por cima de `/usr/bin`: 87 argv chegaram a um
`pactl` de verdade, de 84 testes em 27 arquivos. Os 87 eram LEITURAS —
`list modules short` em todo boot de `Daemon`, `list sinks short` e
`get-default-sink` na aba Controles —, e um deles era a régua que existia para
provar que a leitura passava. O servidor de som dela travou duas vezes naquele
dia, e um `pactl` que lê trava junto.

CADA TESTE DESTE ARQUIVO DISPARA UM `pactl` QUE SÓ O DUBLÊ DA SESSÃO ATENDE, e
é isso que ele mede. Os argv carregam uma marca própria (`info <marca>`) para
não se confundirem com os de outro teste.

A MORDIDA — arrancar o desvio do `PATH` ou o `Popen` da suíte — faz estes
testes dispararem `pactl` de verdade. Por isso ela SÓ se roda com um espião
próprio na frente do `PATH` e montado por cima de `/usr/bin`, com os sockets de
som escondidos; a entrega da sprint traz o comando e as saídas.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from tests import conftest

RAIZ = Path(__file__).resolve().parents[2]

#: A família dos clientes do servidor de som, para o CENSO de baixo. Ela é mais
#: larga que a lista do conftest de propósito: o censo pergunta ao código quais
#: nomes ele usa, e a lista tem de conter todos.
FAMILIA = (
    r"pa(?:ctl|cmd|cat|rec(?:ord)?|play|mon|suspender)"
    r"|wpctl|pw-[a-z][a-z-]*[a-z]|arecord|aplay|speaker-test"
)


def _duble() -> Path:
    """O diretório dos dublês desta sessão — e ele TEM de existir."""
    if os.environ.get("HEFESTO_SOM_DE_VERDADE") == "1":
        pytest.skip("HEFESTO_SOM_DE_VERDADE=1: esta sessão pediu o servidor de verdade")
    duble = conftest.som_de_mentira()
    assert duble is not None, (
        "a sessão não armou o dublê do som: todo `pactl` da suíte chega ao "
        "servidor de som de quem a roda"
    )
    return duble


def _marca() -> str:
    return f"marca-{uuid.uuid4().hex[:12]}"


def _chegou_ao_duble(nome: str, marca: str) -> bool:
    return f"{nome} info {marca}" in conftest.chamadas_ao_som_de_mentira()


# ---------------------------------------------------------------------------
# 1. O PATH da sessão: quem herda o ambiente
# ---------------------------------------------------------------------------


def test_todo_binario_de_som_resolve_no_duble_da_sessao() -> None:
    """O `shutil.which` do produto é a primeira pergunta de todo `_rodar`.

    MORDIDA: tire o `os.environ["PATH"] = ...` de `_armar_som_de_mentira`.
    """
    duble = _duble()
    fora = {
        nome: shutil.which(nome)
        for nome in conftest.BINARIOS_DO_SERVIDOR_DE_SOM
        if shutil.which(nome) != str(duble / nome)
    }
    assert not fora, f"binário de som que não resolve no dublê da sessão: {fora}"


def test_um_pactl_que_herda_o_ambiente_cai_no_duble() -> None:
    """O caso dos 87 argv do inventário: todos herdavam o `PATH` da sessão."""
    _duble()
    marca = _marca()
    feito = subprocess.run(
        ["pactl", "info", marca], capture_output=True, text=True, timeout=30, check=False
    )
    assert feito.returncode != 0, "o dublê responde como um servidor que não atende"
    assert _chegou_ao_duble("pactl", marca), (
        "um `pactl` disparado pela suíte não chegou ao dublê da sessão — ele foi "
        f"a outro lugar: rc={feito.returncode} stderr={feito.stderr!r}"
    )


def test_os_dois_rodar_do_som_nao_chegam_ao_servidor() -> None:
    """A LEITURA pelos dois `_rodar` que a guarda de escrita embrulha.

    Até 13/09 a guarda deixava a leitura passar e ela chegava ao servidor dela
    — era a régua `test_a_guarda_recusa_a_escrita_e_deixa_a_leitura_passar`
    que o provava, lendo `list sinks short` de verdade.
    """
    _duble()
    from hefesto_dualsense4unix.integrations import alto_falante_bt, dualsense_bt_audio

    for modulo in (alto_falante_bt, dualsense_bt_audio):
        marca = _marca()
        assert modulo._rodar(["pactl", "info", marca]) is None, modulo.__name__
        assert _chegou_ao_duble("pactl", marca), (
            f"a leitura de `{modulo.__name__}._rodar` não chegou ao dublê da sessão"
        )


# ---------------------------------------------------------------------------
# 2. O Popen da sessão: quem NÃO herda o ambiente
# ---------------------------------------------------------------------------


def test_um_path_de_sistema_explicito_cai_no_duble() -> None:
    """Oito arquivos da suíte passam `env={"PATH": "/usr/bin:/bin"}` a um
    subprocesso — esse PATH não herda o desvio da sessão.

    MORDIDA: tire o `_instalar_popen_sem_som()` de `_armar_som_de_mentira`.
    """
    _duble()
    marca = _marca()
    subprocess.run(
        ["pactl", "info", marca],
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        capture_output=True, timeout=30, check=False,
    )
    assert _chegou_ao_duble("pactl", marca), (
        "um `pactl` com PATH de sistema explícito passou por cima do dublê"
    )


def test_o_caminho_absoluto_do_sistema_cai_no_duble() -> None:
    """`/usr/bin/pactl` escrito à mão não resolve pelo PATH de ninguém."""
    _duble()
    marca = _marca()
    subprocess.run(
        ["/usr/bin/pactl", "info", marca],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True, timeout=30, check=False,
    )
    assert _chegou_ao_duble("pactl", marca), "o caminho absoluto passou por cima do dublê"


def test_o_script_de_shell_com_path_de_sistema_cai_no_duble() -> None:
    """O `doctor.sh` e o `fix_wireplumber_default_source.sh` chamam `wpctl`
    e `pactl` por dentro, com o PATH que o teste lhes deu."""
    _duble()
    marca = _marca()
    subprocess.run(
        ["/bin/sh", "-c", f"wpctl info {marca}"],
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True, timeout=30, check=False,
    )
    assert _chegou_ao_duble("wpctl", marca), (
        "um script de shell com PATH de sistema achou o `wpctl` de verdade"
    )


def test_o_subprocesso_do_asyncio_cai_no_duble() -> None:
    """O daemon roda subprocesso pelo `asyncio`, que monta o `Popen` por baixo."""
    _duble()
    marca = _marca()

    async def _rodar() -> int:
        processo = await asyncio.create_subprocess_exec(
            "/usr/bin/pw-dump", "info", marca,
            env={"PATH": "/usr/bin:/bin"},
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        return await processo.wait()

    assert asyncio.run(_rodar()) != 0
    assert _chegou_ao_duble("pw-dump", marca), "o `asyncio` passou por cima do dublê"


def test_o_duble_do_proprio_teste_continua_vencendo(tmp_path: Path) -> None:
    """A metade que impede a cura de virar um SIM para tudo.

    Um teste que monta o PRÓPRIO `pactl` e o põe ANTES do sistema tem de
    continuar recebendo a chamada — é assim que `doctor.sh` e companhia são
    medidos. Um `Popen` que trocasse todo `pactl` pelo dublê da sessão
    quebraria esses testes e esconderia o que eles medem.

    MORDIDA: faça `_path_com_o_duble` inserir o dublê na FRENTE do PATH, e não
    antes do primeiro diretório de sistema.
    """
    _duble()
    marca = _marca()
    proprio = tmp_path / "bin"
    proprio.mkdir()
    registro = tmp_path / "chamadas-do-teste.txt"
    falso = proprio / "pactl"
    falso.write_text(
        f"#!/bin/sh\nprintf '%s\\n' \"pactl $*\" >> '{registro}'\nexit 0\n",
        encoding="utf-8",
    )
    falso.chmod(0o755)

    feito = subprocess.run(
        ["pactl", "info", marca],
        env={"PATH": f"{proprio}:/usr/bin:/bin"},
        capture_output=True, timeout=30, check=False,
    )

    assert feito.returncode == 0
    assert registro.read_text(encoding="utf-8").splitlines() == [f"pactl info {marca}"]
    assert not _chegou_ao_duble("pactl", marca), (
        "o dublê da sessão roubou a chamada do dublê que o teste montou"
    )


# ---------------------------------------------------------------------------
# 3. O CENSO: todo cliente de som que o produto e os scripts usam tem dublê
# ---------------------------------------------------------------------------


def _nomes_em_src() -> set[str]:
    achados: set[str] = set()
    for arquivo in (RAIZ / "src").rglob("*.py"):
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        achados.update(re.findall(rf"[\"']({FAMILIA})[\"']", texto))
    return achados


def _nomes_em_scripts() -> set[str]:
    achados: set[str] = set()
    arquivos = [RAIZ / "install.sh"]
    arquivos += [
        p for p in (RAIZ / "scripts").rglob("*")
        if p.is_file() and p.suffix in {".sh", ".py", ".bash", ""}
    ]
    for arquivo in arquivos:
        if not arquivo.is_file():
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="replace")
        achados.update(re.findall(rf"(?<![\w.-])({FAMILIA})(?![\w-])", texto))
    return achados


def test_o_censo_acha_os_clientes_de_som_que_ja_se_sabe_que_existem() -> None:
    """A régua do censo não pode virar um SIM para tudo.

    Medido em 13/09/2026: `src/` chama `pactl`, `wpctl`, `parec`, `paplay`,
    `pw-play` e `pw-record`. Um censo que não os achasse daria verde sobre
    qualquer lista.
    """
    assert {"pactl", "wpctl", "parec", "paplay", "pw-play", "pw-record"} <= _nomes_em_src()


def test_todo_cliente_de_som_do_produto_e_dos_scripts_tem_duble() -> None:
    """MORDIDA: tire `pw-link` de `BINARIOS_DO_SERVIDOR_DE_SOM` e este teste
    reprova nomeando o binário."""
    usados = _nomes_em_src() | _nomes_em_scripts()
    sem_duble = sorted(usados - set(conftest.BINARIOS_DO_SERVIDOR_DE_SOM))
    assert not sem_duble, (
        "cliente do servidor de som usado em `src/` ou `scripts/` sem dublê na "
        f"sessão da suíte: {sem_duble}. Acrescente-o a "
        "`BINARIOS_DO_SERVIDOR_DE_SOM` em `tests/conftest.py`."
    )
