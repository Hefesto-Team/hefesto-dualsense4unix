"""As versões que rodam são as que a casa mediu no aparelho — B3 da O-PRODUTO.

``O-PRODUTO-EM-QUALQUER-MAQUINA-01`` (28/09/2026), a L4 do estudo
``2026-09-27-o-basico-e-os-jogos/03-qualquer-maquina.md``: o ``install.sh``
fazia ``pip install -e`` sem trava, e o ``pyproject.toml`` pede ``evdev>=1.6``.
Nesta casa o ``evdev`` é o 1.7.0 do apt; numa máquina nova o pip entregava o
2.0.0, que nenhum aparelho rodou — e a cura da queda da sessão sobrescreve o
``UInput._find_device``, que vale no 2.0.0 por coincidência.

O ``constraints.txt`` guarda as versões medidas; o install instala com ``-c``;
e esta régua lê o arquivo e o ``importlib.metadata`` do Python que roda a
suíte (a ``.venv`` do produto), e reprova divergência.

A MORDIDA, feita em 28/09/2026 sem tocar em ``.venv`` nenhuma: trocar a linha
``evdev==1.7.0`` do ``constraints.txt`` por ``evdev==2.0.0`` faz
``test_a_venv_roda_as_versoes_travadas`` reprovar, nomeando o ``evdev``; tirar
o ``"${_travas[@]}"`` de um dos dois ``pip install -e`` do ``install.sh`` faz
``test_o_install_instala_com_as_travas`` reprovar. Devolvidos, md5 conferido.
"""

from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
TRAVAS = RAIZ / "constraints.txt"
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")


def _travas() -> dict[str, str]:
    saida: dict[str, str] = {}
    for linha in TRAVAS.read_text(encoding="utf-8").splitlines():
        linha = linha.split("#", 1)[0].strip()
        if not linha:
            continue
        casou = re.fullmatch(r"([A-Za-z0-9_.-]+)==([0-9A-Za-z.+-]+)", linha)
        assert casou, f"linha do constraints.txt fora da forma nome==versão: {linha!r}"
        saida[casou.group(1)] = casou.group(2)
    return saida


def test_as_quatro_que_a_casa_mediu_estao_travadas() -> None:
    assert set(_travas()) >= {"evdev", "hidapi-usb", "pydantic", "pydualsense"}


def test_a_venv_roda_as_versoes_travadas() -> None:
    divergentes = []
    for nome, versao in _travas().items():
        try:
            instalada = importlib.metadata.version(nome)
        except importlib.metadata.PackageNotFoundError:
            instalada = "ausente"
        if instalada != versao:
            divergentes.append(f"{nome}: a .venv tem {instalada}, a casa mediu {versao}")
    assert divergentes == [], (
        "a .venv que roda o produto não é a que a casa mediu no aparelho — "
        "instale com `pip install -c constraints.txt`: " + "; ".join(divergentes)
    )


def test_o_install_instala_com_as_travas() -> None:
    """As duas linhas de `pip install -e` do install levam o `-c`."""
    linhas = [
        linha for linha in INSTALL.splitlines()
        if "--disable-pip-version-check" in linha and " -e " in linha
    ]
    assert len(linhas) == 2, linhas
    for linha in linhas:
        assert '"${_travas[@]}"' in linha, linha
    assert '_travas=(-c "${ROOT_DIR}/constraints.txt")' in INSTALL


def test_as_travas_cabem_no_que_o_pyproject_pede() -> None:
    """Uma trava fora do intervalo do `pyproject.toml` quebraria o pip."""
    from packaging.requirements import Requirement

    pyproject = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
    bloco = pyproject[pyproject.index("dependencies = [") :]
    bloco = bloco[: bloco.index("]")]
    pedidos = {
        Requirement(r).name: Requirement(r)
        for r in re.findall(r'"([^"]+)"', bloco)
    }
    for nome, versao in _travas().items():
        if nome in pedidos:
            assert pedidos[nome].specifier.contains(versao), (nome, versao)
