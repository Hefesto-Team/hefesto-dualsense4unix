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
    "interface/olhar.py": "ferramenta de foto: escreve no clone",
    "interface/desenho_da_experimental.py": "gerador do mockup: roda do clone",
    "app/actions/pecas_do_atualizador.py": "reconstrói a peça da casa a partir das fontes do clone",
}

DO_PROPRIO_PACOTE: dict[tuple[str, str], str] = {
    ("interface/monta.py", "assets/hefesto-logo.svg"): (
        "a janela importa o `monta` em tempo de execução, e o logo que ele lê é o de "
        "`interface/assets/`, dentro do pacote Python, que o `include` do wheel leva"
    ),
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


def _justificado(origem: str, caminho: str) -> bool:
    modulo = origem.rsplit(":", 1)[0]
    if (modulo, caminho) in DO_PROPRIO_PACOTE:
        return True
    return any(modulo.startswith(prefixo) for prefixo in SO_DO_CLONE)


def test_o_que_se_le_do_proprio_pacote_mora_no_pacote_e_o_wheel_o_leva():
    """A isenção por arquivo do pacote vale só se o arquivo está ao lado do módulo e no wheel."""
    inclui = _pyproject()["tool"]["hatch"]["build"]["targets"]["wheel"]["include"]
    for modulo, caminho in DO_PROPRIO_PACOTE:
        arquivo = (PACOTE / modulo).parent / caminho
        assert arquivo.is_file(), f"{modulo} lê {caminho}, que não está no pacote"
        relativo = arquivo.relative_to(RAIZ).as_posix()
        assert any(Path(relativo).match(p) for p in inclui), f"o wheel não leva {relativo}"


def test_todo_dado_lido_pelo_src_viaja_no_shared_data_do_pyproject():
    """Cada caminho de `docs/data/` e `assets/` que o `src/` abre está no shared-data."""
    fontes = set(_shared_data())
    sem_pacote = {
        caminho: [o for o in origens if not _justificado(o, caminho)]
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


PERGUNTA_DO_PINO = """
import json, os, sys
sys.prefix = os.path.join(os.environ["LIB"], "sem-prefixo")
sys.path.insert(0, os.environ["LIB"])
from hefesto_dualsense4unix.integrations import proton_pin
conf = proton_pin.default_pin_conf_path()
print(json.dumps({"pino_conf": str(conf.resolve()) if conf is not None else None}))
"""


def _perguntar(destino: Path, sem: tuple[str, ...] = (), pergunta: str = PERGUNTA) -> dict:
    ambiente = _montar_prefixo(destino, sem)
    feito = subprocess.run(
        [sys.executable, "-I", "-c", pergunta], env=ambiente, capture_output=True, text=True,
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


def test_instalado_so_com_o_shared_data_o_pino_do_proton_se_acha_no_share(tmp_path):
    """D-2611-O-PINO-DO-PROTON-SE-ACHA-EM-TODA-INSTALACAO: fora do clone, o `proton-pin.conf` é o
    do `share/`, e sem ele a resposta é «não há», nunca um caminho de fora do prefixo."""
    achado = _perguntar(tmp_path / "com", pergunta=PERGUNTA_DO_PINO)["pino_conf"]
    esperado = tmp_path / "com" / "share" / "hefesto-dualsense4unix" / "assets" / "proton-pin.conf"
    assert achado == str(esperado.resolve()), achado
    sem = _perguntar(
        tmp_path / "sem", sem=("assets/proton-pin.conf",), pergunta=PERGUNTA_DO_PINO)["pino_conf"]
    assert sem is None, sem


EXCECOES_DOS_PAIS_DO_ARQUIVO: dict[str, str] = {
    "interface/": "ferramenta do mockup e das fotos: roda do clone",
    "utils/memoria_dos_controles.py": "acha a cópia do clone para listar rastros, não lê dado",
    "utils/repo_files.py": "o resolvedor único: a primeira base é o clone",
}


def _sobe_pelos_pais_do_proprio_arquivo(arvore: ast.AST) -> list[int]:
    """As linhas que sobem do `__file__` até a raiz do clone: `parents[3]` ou mais, ou um laço
    sobre `.parents`."""
    linhas: list[int] = []
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Subscript)
            and isinstance(no.value, ast.Attribute)
            and no.value.attr == "parents"
            and "__file__" in ast.unparse(no.value)
            and isinstance(no.slice, ast.Constant)
            and isinstance(no.slice.value, int)
            and no.slice.value >= 3
        ):
            linhas.append(no.lineno)
        if (
            isinstance(no, ast.For)
            and isinstance(no.iter, ast.Attribute)
            and no.iter.attr == "parents"
        ):
            linhas.append(no.lineno)
        if isinstance(no, ast.Assign) and any(
            isinstance(x, ast.Name) and x.id == "here" for x in no.targets
        ) and "__file__" in ast.unparse(no.value):
            linhas.append(no.lineno)
    return linhas


def test_nenhum_modulo_monta_caminho_de_dado_pelos_pais_do_proprio_arquivo():
    """D-2611-O-PINO-DO-PROTON-SE-ACHA-EM-TODA-INSTALACAO: subir os pais do `__file__` só acha o
    dado no clone. Fora do `utils/repo_files.py` só passa quem também pergunta ao `repo_files`
    (o clone vira o último recurso) ou está justificado em EXCECOES_DOS_PAIS_DO_ARQUIVO."""
    soltos: dict[str, list[int]] = {}
    for arquivo in sorted(PACOTE.rglob("*.py")):
        relativo = arquivo.relative_to(PACOTE).as_posix()
        texto = arquivo.read_text("utf-8")
        linhas = _sobe_pelos_pais_do_proprio_arquivo(ast.parse(texto))
        if not linhas:
            continue
        if any(relativo.startswith(p) for p in EXCECOES_DOS_PAIS_DO_ARQUIVO):
            continue
        if "encontrar_arquivo_do_repo" in texto:
            continue
        soltos[relativo] = linhas
    assert not soltos, (
        "monta caminho de dado pelos pais do `__file__`, que só o clone tem: pergunte ao "
        f"`utils/repo_files.py` ou justifique: {json.dumps(soltos, ensure_ascii=False)}"
    )


def test_a_regua_dos_pais_do_arquivo_enxerga_o_laco_que_o_pino_tinha():
    """D-2611-O-PINO-DO-PROTON-SE-ACHA-EM-TODA-INSTALACAO: a régua não é cega ao desenho antigo."""
    antigo = (
        "from pathlib import Path\n"
        "def f():\n"
        "    here = Path(__file__).resolve()\n"
        "    for parent in here.parents:\n"
        "        pass\n"
        "RAIZ = Path(__file__).resolve().parents[3]\n"
    )
    assert sorted(_sobe_pelos_pais_do_proprio_arquivo(ast.parse(antigo))) == [3, 4, 6]
    assert _sobe_pelos_pais_do_proprio_arquivo(ast.parse(
        "from pathlib import Path\nX = Path(__file__).resolve().parents[2]\n")) == []


def _sem_clone(tmp_path, monkeypatch):
    """O atualizador de uma instalação por pacote: nenhuma base tem o clone."""
    from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa

    vazio = tmp_path / "sem-clone"
    vazio.mkdir()
    monkeypatch.setattr(pa, "RAIZ_DO_REPOSITORIO", vazio)
    monkeypatch.setattr(pa.repo_files, "bases_de_instalacao", lambda: (vazio,))
    return pa


def test_o_atualizador_sem_clone_diz_que_a_compilacao_da_peca_e_do_clone(tmp_path, monkeypatch):
    """D-2611-O-PINO-DO-PROTON-SE-ACHA-EM-TODA-INSTALACAO: sem o `construir.sh` ao lado, o
    atualizador não roda caminho que não existe e diz de quem é a compilação."""
    pa = _sem_clone(tmp_path, monkeypatch)
    rodados = []
    monkeypatch.setattr(pa.shutil, "which", lambda _nome: "/usr/bin/compilador")
    monkeypatch.setattr(pa, "_comando", lambda *a, **k: rodados.append(a) or (0, ""))
    feita, porque = pa._compilar_a_gdk(tmp_path / "pasta", "xgameruntime.dll", "0" * 64)
    assert feita is None
    assert "é do clone do Hefesto" in porque, porque
    assert not rodados, rodados


def test_o_atualizador_sem_clone_baixa_a_peca_da_versao_do_pacote_instalado(tmp_path, monkeypatch):
    """D-2611-O-PINO-DO-PROTON-SE-ACHA-EM-TODA-INSTALACAO: sem o `pyproject.toml` do clone, a
    versão do endereço da peça é a do pacote instalado, não vazia."""
    from importlib import metadata

    from hefesto_dualsense4unix.integrations import receitas_de_ambiente as receitas

    pa = _sem_clone(tmp_path, monkeypatch)
    marca = pa.MARCA_DA_VERSAO_NO_PINO
    pino = tmp_path / "pino.txt"
    pino.write_text(
        f"url=https://x/v{marca}/xgameruntime.dll\nsha256={'a' * 64}\n"
        f"gameinput_url=https://x/v{marca}/gameinput.dll\ngameinput_sha256={'b' * 64}\n",
        encoding="utf-8")
    monkeypatch.setattr(receitas, "PINO_DA_PECA", pino)
    monkeypatch.setattr(receitas, "pasta_da_peca", lambda home=None: tmp_path / "casa")
    monkeypatch.setattr(pa, "_cache", lambda: tmp_path / "cache")
    monkeypatch.setattr(metadata, "version", lambda _nome: "7.7.7")
    baixados: list[str] = []

    def baixar(url, destino, passo, sha256=""):
        baixados.append(url)
        raise pa.EtapaFalhouError("sem rede no ensaio")

    monkeypatch.setattr(pa, "_baixar", baixar)
    monkeypatch.setattr(pa, "_da_release_com_a_soma", lambda *_a: "")
    monkeypatch.setattr(pa.shutil, "which", lambda _nome: None)
    with pytest.raises(pa.EtapaFalhouError):
        pa._baixar_a_gdk(pa.Passo(), {})
    assert baixados == ["https://x/v7.7.7/xgameruntime.dll"], baixados


def test_a_versao_da_peca_e_a_do_clone_quando_ha_clone(tmp_path, monkeypatch):
    """D-2611-O-PINO-DO-PROTON-SE-ACHA-EM-TODA-INSTALACAO: no clone, o `pyproject.toml` diz a
    versão (a do pacote editável pode estar atrás do `git pull`); sem o clone, a do pacote."""
    from importlib import metadata

    from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa

    clone = tmp_path / "clone"
    clone.mkdir()
    (clone / "pyproject.toml").write_text('[project]\nversion = "9.9.9"\n', encoding="utf-8")
    monkeypatch.setattr(pa, "RAIZ_DO_REPOSITORIO", clone)
    monkeypatch.setattr(metadata, "version", lambda _nome: "7.7.7")
    assert pa._versao_instalada() == "9.9.9"
    (clone / "pyproject.toml").unlink()
    assert pa._versao_instalada() == "7.7.7"
