"""Os dados que o produto lê em tempo de execução viajam em todo pacote, e a falta se diz.

AS-RECEITAS-DE-AMBIENTE-VIAJAM-NOS-PACOTES-01. As receitas de ambiente, o pino da peça GDK, o mapa
de canais e a linha-base das curas eram achados por `Path(__file__).resolve().parents[3]`, o caminho
do clone: instalado por wheel, .deb, Flatpak ou Nix o módulo não os achava e nenhum jogo recebia a
variável da receita, calado.

A régua: todo caminho de `docs/data/` e `assets/` que o `src/` lê é um arquivo do shared-data do
`pyproject.toml` (ou está em `SO_DO_CLONE`, com o motivo). O ensaio: um prefixo de mentira com só o
shared-data, o pacote copiado para fora do clone, e a pergunta feita por um Python à parte.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PACOTE = RAIZ / "src" / "hefesto_dualsense4unix"
PREFIXO_DO_SHARE = "share/hefesto-dualsense4unix/"

SO_DO_CLONE: dict[str, str] = {
    "interface/aba": "gerador do mockup: roda do clone, as páginas prontas é que viajam",
    "interface/monta.py": "gerador do mockup: roda do clone, as páginas prontas é que viajam",
    "interface/olhar.py": "ferramenta de foto: escreve no clone",
    "interface/desenho_da_experimental.py": "gerador do mockup: roda do clone",
    "app/actions/pecas_do_atualizador.py": "reconstrói a peça da casa a partir das fontes do clone",
}

DADOS_LIDOS_PELOS_TRES = (
    "docs/data/receitas-de-ambiente.csv",
    "assets/gdk-runtime/pino.txt",
    "assets/bluez-backport/BASELINE",
    "assets/pipewire-backport/BASELINE",
    "assets/portal-cosmic-backport/BASELINE",
)


def _pyproject() -> dict:
    return tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))


def _shared_data() -> dict[str, str]:
    return _pyproject()["tool"]["hatch"]["build"]["targets"]["wheel"]["shared-data"]


def _so_do_sdist() -> set[str]:
    return set(_pyproject()["tool"]["hatch"]["build"]["targets"]["sdist"]["only-include"])


def _constantes_de_caminho(arvore: ast.AST) -> list[tuple[str, int]]:
    docstrings = {
        id(no.body[0].value)
        for no in ast.walk(arvore)
        if isinstance(no, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and no.body
        and isinstance(no.body[0], ast.Expr)
        and isinstance(no.body[0].value, ast.Constant)
    }
    internos = {
        id(no.left) for no in ast.walk(arvore)
        if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Div)
    }

    def achatar(no: ast.AST) -> list[object]:
        if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Div):
            return [*achatar(no.left), *achatar(no.right)]
        if isinstance(no, ast.Constant) and isinstance(no.value, str):
            return [no.value]
        if isinstance(no, ast.Attribute):
            return [("attr", no.attr)]
        return [None]

    achados: list[tuple[str, int]] = []
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and id(no) not in docstrings
            and re.fullmatch(r"(?:docs/data|assets)/[\w./-]+", no.value)
        ):
            achados.append((no.value, no.lineno))
        if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Div) and id(no) not in internos:
            partes = achatar(no)
            for i, parte in enumerate(partes):
                inicio = parte if isinstance(parte, str) and parte in ("docs", "assets") else (
                    "assets" if isinstance(parte, tuple) and parte[1] == "assets" else None)
                if inicio is None:
                    continue
                resto: list[str] = []
                for seguinte in partes[i + 1:]:
                    if not isinstance(seguinte, str):
                        break
                    resto.append(seguinte)
                if resto:
                    achados.append(("/".join([inicio, *resto]), no.lineno))
                break
    return achados


def _o_que_o_src_le() -> dict[str, list[str]]:
    lidos: dict[str, list[str]] = {}
    for arquivo in sorted(PACOTE.rglob("*.py")):
        relativo = arquivo.relative_to(PACOTE).as_posix()
        for caminho, linha in _constantes_de_caminho(ast.parse(arquivo.read_text("utf-8"))):
            lidos.setdefault(caminho, []).append(f"{relativo}:{linha}")
    return lidos


def _coberto(caminho: str, fontes: set[str]) -> bool:
    return caminho in fontes or any(f.startswith(caminho.rstrip("/") + "/") for f in fontes)


def _justificado(origem: str) -> bool:
    modulo = origem.rsplit(":", 1)[0]
    return any(modulo.startswith(prefixo) for prefixo in SO_DO_CLONE)


def test_todo_dado_lido_pelo_src_viaja_no_shared_data_do_pyproject():
    """Cada caminho de `docs/data/` e `assets/` que o `src/` abre está no shared-data."""
    fontes = set(_shared_data())
    sem_pacote = {
        caminho: [o for o in origens if not _justificado(o)]
        for caminho, origens in _o_que_o_src_le().items()
        if not _coberto(caminho, fontes) and (RAIZ / caminho).exists()
    }
    sem_pacote = {c: o for c, o in sem_pacote.items() if o}
    assert not sem_pacote, (
        "o `src/` lê e o wheel não leva (ponha no shared-data e no sdist do pyproject.toml, ou "
        f"justifique em SO_DO_CLONE): {json.dumps(sem_pacote, ensure_ascii=False, indent=1)}"
    )


def test_a_regua_enxerga_os_dados_que_estes_tres_modulos_leem():
    """A busca não é cega: as receitas, o pino e as linhas-base entram no que a busca encontra."""
    lidos = _o_que_o_src_le()
    for caminho in DADOS_LIDOS_PELOS_TRES:
        assert caminho in lidos, f"a régua não viu a leitura de {caminho}"
    assert "docs/data/mapa-controles.csv" in lidos


def test_o_que_o_pyproject_leva_existe_no_repositorio_e_vai_no_sdist():
    """Todo arquivo do shared-data existe e o sdist o leva, senão o wheel do sdist o perde."""
    fontes = set(_shared_data())
    ausentes = sorted(f for f in fontes if not (RAIZ / f).is_file())
    assert not ausentes, f"o shared-data cita arquivo que não existe: {ausentes}"
    assert fontes <= _so_do_sdist(), f"o sdist deixa para trás: {sorted(fontes - _so_do_sdist())}"


def test_as_receitas_e_as_linhas_base_estao_no_shared_data_com_o_destino_do_repositorio():
    """O destino sob `share/` espelha o caminho do repositório, onde `repo_files` o procura."""
    dados = _shared_data()
    for caminho in (*DADOS_LIDOS_PELOS_TRES, "docs/data/mapa-controles.csv"):
        assert dados.get(caminho) == PREFIXO_DO_SHARE + caminho


def _montar_prefixo(destino: Path, sem: tuple[str, ...] = ()) -> dict[str, str]:
    """Um prefixo de mentira: o pacote copiado para fora do clone e só o shared-data ao lado."""
    lib = destino / "lib"
    shutil.copytree(
        PACOTE, lib / "hefesto_dualsense4unix",
        ignore=shutil.ignore_patterns("__pycache__", "pagin*", "locale", "*.mo", "*.html"),
    )
    share = destino / "share" / "hefesto-dualsense4unix"
    for fonte, alvo in _shared_data().items():
        if fonte in sem:
            continue
        copia = destino / "share" / alvo.removeprefix("share/")
        copia.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(RAIZ / fonte, copia)
    (destino / "home").mkdir()
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(destino / "home"),
        "XDG_DATA_HOME": str(destino / "share"),
        "XDG_CONFIG_HOME": str(destino / "home" / "c"),
        "XDG_CACHE_HOME": str(destino / "home" / "k"),
        "LIB": str(lib),
        "SHARE": str(share),
    }


PERGUNTA = """
import json, os, sys
sys.path.insert(0, os.environ["LIB"])
from hefesto_dualsense4unix.integrations import (
    canal_sem_imu, curas_da_casa, receitas_de_ambiente as r)
print(json.dumps({
    "receitas": len(r.carregar_tabela()),
    "linhas_do_doctor": r.linhas_do_doctor(),
    "pino": r._sha256_do_pino(),
    "mapa": canal_sem_imu.MAPA.is_file(),
    "linhas_do_mapa": len(canal_sem_imu.linhas_do_mapa()),
    "baseline": all((curas_da_casa.MAQUINA.assets / d / "BASELINE").is_file()
                    for d in ("bluez-backport", "pipewire-backport", "portal-cosmic-backport")),
}))
"""


def _perguntar(destino: Path, sem: tuple[str, ...] = ()) -> dict:
    ambiente = _montar_prefixo(destino, sem)
    feito = subprocess.run(
        [sys.executable, "-I", "-c", PERGUNTA], env=ambiente, capture_output=True, text=True,
        timeout=120, check=False, cwd=destino / "home",
    )
    assert feito.returncode == 0, feito.stderr[-2000:]
    return json.loads(feito.stdout.strip().splitlines()[-1])


def test_instalado_so_com_o_shared_data_as_receitas_o_pino_o_mapa_e_as_linhas_base_se_acham(
    tmp_path,
):
    """Fora do clone, só com o `share/`, os quatro dados chegam ao produto."""
    resposta = _perguntar(tmp_path)
    assert resposta["receitas"] >= 1
    assert resposta["pino"] is not None
    assert resposta["mapa"] is True
    assert resposta["linhas_do_mapa"] >= 1
    assert resposta["baseline"] is True
    assert all(tag == "[ OK ]" for tag, _ in resposta["linhas_do_doctor"]), resposta


def test_instalado_sem_as_receitas_o_doctor_diz_que_nao_vieram_e_nao_cala(tmp_path):
    """Sem a tabela e sem o pino no `share/`, o doctor diz as duas faltas em vez do silêncio."""
    resposta = _perguntar(
        tmp_path, sem=("docs/data/receitas-de-ambiente.csv", "assets/gdk-runtime/pino.txt"))
    assert resposta["receitas"] == 0
    textos = [t for tag, t in resposta["linhas_do_doctor"] if tag == "[WARN]"]
    assert any("as receitas de ambiente não vieram nesta instalação" in t for t in textos)
    assert any("o pino da peça GDK não veio nesta instalação" in t for t in textos)


def test_o_doctor_traz_o_bloco_das_receitas_e_a_linha_diz_presente_no_clone():
    """No clone as receitas estão presentes e o doctor as chama pelo nome."""
    from hefesto_dualsense4unix.integrations import receitas_de_ambiente

    linhas = receitas_de_ambiente.linhas_do_doctor()
    assert linhas and linhas[0][0] == "[ OK ]"
    assert "receitas de ambiente" in linhas[0][1]
    texto = (PACOTE / "cli" / "cmd_doctor.py").read_text(encoding="utf-8")
    assert "rc = max(rc, _print_bloco_receitas())" in texto


@pytest.mark.parametrize("tabela_ruim", ["", "id,sinais\n"])
def test_tabela_presente_sem_receita_valida_nao_diz_que_veio_sem_nada(tmp_path, tabela_ruim):
    """Tabela que existe mas não lê não é «não veio»: a linha diz que não se lê."""
    from hefesto_dualsense4unix.integrations import receitas_de_ambiente

    tabela = tmp_path / "t.csv"
    tabela.write_text(tabela_ruim, encoding="utf-8")
    linhas = receitas_de_ambiente.linhas_do_doctor(tabela=tabela)
    assert linhas[0][0] == "[WARN]"
    assert "não se leem" in linhas[0][1]
