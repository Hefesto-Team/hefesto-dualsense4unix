"""O runner `pytest` do `portoes.sh` roda num LAR DE MENTIRA — `PORTAO-LAR-01`.

O DEFEITO, MEDIDO em 21/09/2026 na máquina dela, com o daemon VIVO: `bash
scripts/portoes.sh` sem argumento fez o portão `casa-sabe` (42 testes) escrever
no `~/.config/hefesto-dualsense4unix` **real** — `controller_masks.json` zerado
(78 -> 27 B), o perfil do jogo regravado, e o autoswitch trocou o perfil ATIVO
dela no meio da corrida, de «Marvel's Guardians of the Galaxy» para
«Personalizado».

O `CANARIO-FS-01` do `conftest.py` viu e fez `session.exitstatus = 1`: o portão
saiu **VERMELHO com os 42 testes PASSANDO**. Vermelho de ambiente lê-se como
regressão — a armadilha nomeada na §6.1 do ONDE PARAMOS de 21/09 — e, pior,
quem estava usando o produto perdeu configuração.

POR QUE O `conftest.py` NÃO BASTAVA, e é o ponto que este arquivo guarda: ele
desvia `HOME` e os quatro `XDG_*` por fixture, e `Path.home()` avaliado no
IMPORT de um módulo do produto escapa do monkeypatch. É o próprio texto do
canário que manda procurar por isso. Desviar no AMBIENTE, antes de o processo
nascer, alcança os dois casos de uma vez.

A MORDIDA, e ela é em três camadas de propósito:

1. :func:`test_o_mecanismo_alcanca_o_import` prova a PREMISSA — que um `HOME`
   no ambiente realmente muda o que `Path.home()` devolve num processo novo.
   Sem esta, as outras duas medem um arranjo que ninguém provou funcionar.
2. :func:`test_o_lar_de_mentira_cobre_as_seis_variaveis` LÊ o array do próprio
   `portoes.sh` e o EXECUTA. Não digita o valor esperado: pede ao script o que
   ele define e confere onde o processo filho cai. Tirar uma variável do array
   reprova aqui.
3. :func:`test_o_runner_pytest_usa_o_lar` prova que o runner `pytest` — e não
   outro — carrega o desvio. Apagar o `env` da linha do runner reprova aqui.

As três juntas são o que a casa chama de teste que MORDE: arranque a cura em
qualquer uma das duas pontas (o array ou o uso) e uma delas fica vermelha.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTOES = RAIZ / "scripts" / "portoes.sh"

#: As seis que importam. `HOME` é a raiz de `Path.home()` e de `~`; os cinco
#: `XDG_*` são os que o produto lê para achar config, dado, cache, estado e o
#: diretório de runtime. Quem perder um deles reabre uma porta para a casa dela.
VARIAVEIS = (
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "XDG_STATE_HOME",
    "XDG_RUNTIME_DIR",
)


def _bloco_do_array() -> str:
    """O trecho do `portoes.sh` que cria o lar e monta o ambiente.

    Lido do arquivo, nunca digitado aqui: a régua tem de responder sobre o
    script de hoje, e não sobre o que alguém escreveu nesta docstring.
    """
    fonte = PORTOES.read_text(encoding="utf-8")
    inicio = fonte.find('LAR_DE_MENTIRA="$(mktemp')
    if inicio < 0:
        pytest.fail(
            "o `portoes.sh` não cria mais o LAR_DE_MENTIRA — a cura do "
            "PORTAO-LAR-01 foi arrancada, e o runner `pytest` voltou a rodar "
            "com o HOME real de quem chamou"
        )
    fim = fonte.find(")", fonte.find("_AMBIENTE_DE_MENTIRA=(", inicio))
    assert fim > inicio, "o array _AMBIENTE_DE_MENTIRA está sem fecho"
    return fonte[inicio : fim + 1]


def test_o_mecanismo_alcanca_o_import(tmp_path: Path) -> None:
    """`HOME` no ambiente muda `Path.home()` num processo novo — a premissa.

    É o degrau que sustenta os outros dois. Se um dia o Python passar a
    resolver a casa por outro caminho (passwd, por exemplo, que é o que
    `os.path.expanduser` usa quando `HOME` some), esta régua cai primeiro e
    nomeia a causa, em vez de deixar as outras duas darem verde sobre um
    desvio que não desvia.
    """
    lar = tmp_path / "lar"
    lar.mkdir()
    saida = subprocess.run(
        [sys.executable, "-c", "from pathlib import Path; print(Path.home())"],
        env={"HOME": str(lar), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert saida.stdout.strip() == str(lar)


def test_o_lar_de_mentira_cobre_as_seis_variaveis(tmp_path: Path) -> None:
    """Executa o bloco do script e confere onde o processo filho cai.

    O bloco é lido do `portoes.sh` e rodado por `bash` com `TMPDIR` apontado
    para o `tmp_path` do teste — então o lar que nasce aqui morre aqui, e a
    medição não depende de nada fora desta pasta.
    """
    bloco = _bloco_do_array()
    script = "\n".join(
        (
            "set -euo pipefail",
            bloco,
            # `${_AMBIENTE_DE_MENTIRA[*]}` é como o runner o usa; repetimos a
            # forma exata para medir o que o portão de verdade faz.
            'env ${_AMBIENTE_DE_MENTIRA[*]} ' + shlex.quote(sys.executable) + " -c "
            + shlex.quote(
                "import os;"
                "print('\\n'.join(f'{k}={os.environ.get(k, \"\")}' "
                "for k in " + repr(list(VARIAVEIS)) + "))"
            ),
            'printf "LAR=%s\\n" "$LAR_DE_MENTIRA"',
        )
    )
    saida = subprocess.run(
        ["bash", "-c", script],
        env={"PATH": "/usr/bin:/bin", "TMPDIR": str(tmp_path)},
        capture_output=True,
        text=True,
    )
    assert saida.returncode == 0, saida.stderr
    lidos = dict(
        linha.split("=", 1)
        for linha in saida.stdout.splitlines()
        if "=" in linha
    )
    lar = lidos.pop("LAR", "")
    assert lar.startswith(str(tmp_path)), (
        f"o lar nasceu fora do TMPDIR do teste: {lar!r}"
    )
    for nome in VARIAVEIS:
        valor = lidos.get(nome, "")
        assert valor.startswith(lar), (
            f"{nome} não caiu no lar de mentira: {valor!r} — o runner `pytest` "
            f"do portão escreveria em {valor!r} na máquina de quem chamar"
        )


def test_o_runner_pytest_usa_o_lar() -> None:
    """A linha do runner `pytest` carrega o ambiente de mentira.

    Os outros runners ficam de fora de propósito: `py`, `bash` e `bin` leem
    arquivo e não instanciam o daemon. Quem carrega o produto inteiro — e por
    isso alcança o disco dela — é este.
    """
    fonte = PORTOES.read_text(encoding="utf-8")
    linha = next(
        (ln for ln in fonte.splitlines() if re.match(r"\s*pytest\)\s*cmd=", ln)),
        None,
    )
    assert linha is not None, "o runner `pytest` sumiu da tabela do portoes.sh"
    assert "_AMBIENTE_DE_MENTIRA" in linha, (
        "o runner `pytest` voltou a rodar com o HOME de quem chamou — em "
        "21/09/2026 isso zerou o `controller_masks.json` dela e trocou o "
        "perfil ativo no meio de uma corrida. Ver PORTAO-LAR-01."
    )
