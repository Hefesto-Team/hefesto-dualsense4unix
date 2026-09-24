"""O daemon do Flatpak alcança o que o install cria em /run — O-FLATPAK-ALCANCA-O-BROKER-01.

No Flatpak o daemon roda DENTRO do sandbox, e o /run do sandbox é um tmpfs
próprio: um caminho de /run que o `finish-args` não monta responde ENOENT lá
dentro (medido em 24/09/2026, flatpak 1.18.1). Com a 70 e a 72 fechando o
hidraw e os nós de entrada do físico, o broker é a única porta para o
controle, e o daemon do Flatpak ficava sem ele.

Esta régua LÊ no código cada caminho de /run que o daemon abre (as constantes
de texto do pacote, fora as docstrings e fora o `broker/`, que roda como root
no host) e cobra, no manifesto, a linha que o monta — com o modo decidido. O
que o código cita e o sandbox NÃO deve ganhar está em :data:`NAO_SE_EXPOE`, com
o porquê. Um caminho novo de /run no código, sem linha e sem decisão, reprova.

A MORDIDA, medida: tirar a linha do broker reprova o teste da cobertura e o do
modo; pôr `:ro` na da trava reprova o do modo e o da escrita; tirar a do udev
reprova o da cobertura.
"""

from __future__ import annotations

import ast
import errno
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "src" / "hefesto_dualsense4unix"
MANIFESTO = RAIZ / "flatpak" / "io.github.hefesto_team.hefesto_dualsense4unix.yml"
PAGINA = RAIZ / "docs" / "usage" / "flatpak.md"

#: Subpacotes que NUNCA rodam no sandbox: o broker é um serviço root do host.
FORA_DO_SANDBOX = ("broker",)

#: O que o código cita em /run e o sandbox não ganha, de propósito.
NAO_SE_EXPOE: dict[str, str] = {
    "/run/systemd": (
        "é a sonda de «há systemd?» do `daemon_actions`; dentro do sandbox a "
        "resposta certa é não, e o FLATPAK_ID já decide antes dela"
    ),
    "/run/user": (
        "é o XDG_RUNTIME_DIR, e o que o produto usa dele vem pela linha "
        "`xdg-run/hefesto-dualsense4unix`"
    ),
}

#: Um caminho de /run dentro de um texto; `steam://rungameid/` fica de fora.
_RE_RUN = re.compile(r"(?<![\w:/])/run/[A-Za-z0-9_.@-]+(?:/[A-Za-z0-9_.@-]+)*")


def _docstrings(arvore: ast.AST) -> set[int]:
    ids: set[int] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant):
            ids.add(id(no.value))
    return ids


def caminhos_de_run_no_codigo() -> dict[str, list[str]]:
    """``{caminho: ["arquivo:linha", …]}`` de toda constante de texto com /run."""
    achados: dict[str, list[str]] = {}
    for arquivo in sorted(PACOTE.rglob("*.py")):
        relativo = arquivo.relative_to(PACOTE)
        if relativo.parts[0] in FORA_DO_SANDBOX:
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        docs = _docstrings(arvore)
        for no in ast.walk(arvore):
            if not (isinstance(no, ast.Constant) and isinstance(no.value, str)):
                continue
            if id(no) in docs:
                continue
            for casado in _RE_RUN.finditer(no.value):
                achados.setdefault(casado.group(0).rstrip("/"), []).append(
                    f"{relativo}:{no.lineno}"
                )
    return achados


def linhas_de_run_do_manifesto() -> dict[str, str]:
    """``{caminho: modo}`` de cada ``--filesystem=/run/…`` do ``finish-args``."""
    args = yaml.safe_load(MANIFESTO.read_text(encoding="utf-8"))["finish-args"]
    linhas: dict[str, str] = {}
    for arg in args:
        if not arg.startswith("--filesystem=/run/"):
            continue
        caminho, _, modo = arg.removeprefix("--filesystem=").partition(":")
        linhas[caminho.rstrip("/")] = modo or "rw"
    return linhas


def expostos() -> dict[str, str]:
    """O que o Flatpak monta, e com que modo — o caminho vem do DONO de cada um."""
    from hefesto_dualsense4unix.core.evdev_reader import UDEV_DB_DIR
    from hefesto_dualsense4unix.integrations.diario_do_radio import TRAVA_COMUM
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
        DEFAULT_SOCKET_PATH,
    )

    return {
        # A PASTA do socket: ele renasce a cada restart da socket unit, e uma
        # montagem do arquivo ficaria presa ao socket velho. `ro` basta para o
        # connect.
        str(PurePosixPath(DEFAULT_SOCKET_PATH).parent): "ro",
        # A pasta da trava, com escrita: o daemon escreve nela quem está com a
        # trava (o teste da escrita, abaixo, pergunta isso ao código).
        str(TRAVA_COMUM.parent): "rw",
        # A base do udev, só de leitura.
        str(UDEV_DB_DIR): "ro",
    }


def _debaixo_de(caminho: str, pasta: str) -> bool:
    return caminho == pasta or caminho.startswith(pasta + "/")


CAMINHOS = caminhos_de_run_no_codigo()


def test_a_leitura_do_codigo_enxerga_os_tres_donos() -> None:
    """Controle: o varredor acha o socket, a trava e a base do udev."""
    from hefesto_dualsense4unix.core.evdev_reader import UDEV_DB_DIR
    from hefesto_dualsense4unix.integrations.diario_do_radio import TRAVA_COMUM
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
        DEFAULT_SOCKET_PATH,
    )

    for dono in (DEFAULT_SOCKET_PATH, str(TRAVA_COMUM), str(UDEV_DB_DIR)):
        assert dono in CAMINHOS, f"o varredor não achou {dono}: a régua ficou cega"


@pytest.mark.parametrize("caminho", sorted(CAMINHOS))
def test_cada_caminho_de_run_do_daemon_tem_a_sua_linha(caminho: str) -> None:
    if any(_debaixo_de(caminho, pasta) for pasta in NAO_SE_EXPOE):
        return
    linhas = linhas_de_run_do_manifesto()
    cobre = [linha for linha in linhas if _debaixo_de(caminho, linha)]
    assert cobre, (
        f"o daemon abre {caminho} ({', '.join(CAMINHOS[caminho])}) e o finish-args "
        "não o monta: dentro do sandbox ele responde ENOENT. Acrescente a linha "
        "`--filesystem=` ao manifesto, ou a razão de não expor em NAO_SE_EXPOE"
    )


def test_cada_linha_de_run_do_manifesto_tem_o_modo_decidido() -> None:
    linhas = linhas_de_run_do_manifesto()
    decididos = expostos()
    assert linhas == decididos, (
        f"o manifesto monta {linhas} e o decidido é {decididos}. Um `:ro` na trava "
        "volta EROFS no O_RDWR; escrita no broker ou no udev é dar mais do que o "
        "código usa; a montagem do arquivo do socket fica presa ao socket velho"
    )
    for linha in linhas:
        assert any(_debaixo_de(caminho, linha) for caminho in CAMINHOS), (
            f"o manifesto monta {linha} e nenhum caminho do código mora ali"
        )


def test_o_que_nao_se_expoe_fica_fora_do_sandbox() -> None:
    linhas = linhas_de_run_do_manifesto()
    for pasta, porque in NAO_SE_EXPOE.items():
        assert not [linha for linha in linhas if _debaixo_de(linha, pasta)], (
            f"{pasta} não se monta no sandbox: {porque}"
        )
    args = yaml.safe_load(MANIFESTO.read_text(encoding="utf-8"))["finish-args"]
    assert any(a.startswith("--filesystem=xdg-run/hefesto-dualsense4unix") for a in args), (
        "sem a linha xdg-run, o /run/user que o código cita não chega ao sandbox"
    )


def test_a_trava_do_radio_escreve_e_por_isso_a_linha_nao_e_ro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pergunta ao código: ele escreve na trava? E o que faz numa montagem ro?"""
    from hefesto_dualsense4unix.integrations import diario_do_radio as dr

    alvo = tmp_path / "radio.lock"
    fd, escreve = dr._abrir_a_trava(alvo)
    os.close(fd)
    assert escreve, "controle: numa pasta gravável o daemon escreve o dono da trava"

    real = os.open

    def montagem_so_de_leitura(caminho: Any, bandeiras: int, *args: Any, **kwargs: Any) -> int:
        if bandeiras & (os.O_RDWR | os.O_WRONLY):
            raise OSError(errno.EROFS, "montagem só de leitura", str(caminho))
        return real(caminho, bandeiras, *args, **kwargs)

    monkeypatch.setattr(dr.os, "open", montagem_so_de_leitura)
    try:
        fd_ro, _escreve = dr._abrir_a_trava(alvo)
    except OSError as erro:
        assert erro.errno == errno.EROFS, f"controle: o erro simulado era EROFS, veio {erro}"
    else:
        os.close(fd_ro)
        pytest.fail(
            "o `_abrir_a_trava` passou a recuar no EROFS: o comentário do manifesto "
            "que diz o contrário ficou velho (a linha segue sem `:ro`, porque o "
            "daemon escreve o dono)"
        )
    monkeypatch.undo()

    modo = linhas_de_run_do_manifesto().get(str(dr.TRAVA_COMUM.parent))
    assert modo == "rw", (
        f"a trava está montada como {modo!r}: o daemon abre o radio.lock com O_RDWR, "
        "e numa montagem só de leitura o EROFS derruba a trava inteira"
    )


def test_a_pagina_do_flatpak_diz_cada_linha_de_run() -> None:
    pagina = PAGINA.read_text(encoding="utf-8")
    args = yaml.safe_load(MANIFESTO.read_text(encoding="utf-8"))["finish-args"]
    for arg in args:
        if arg.startswith("--filesystem=/run/"):
            assert f"`{arg}`" in pagina, (
                f"{arg} está no manifesto e não na tabela de permissões de "
                "docs/usage/flatpak.md"
            )
