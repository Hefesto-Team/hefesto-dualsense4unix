"""O `--rapido` só repete o que mudou, e os dois portões mais caros ficam rápidos por dentro."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTOES = RAIZ / "scripts" / "portoes.sh"

DEZ = (
    "paridade-gtk-html", "portoes-lentos-rapidos", "pecas-do-dualsense", "so-a-primeira-letra",
    "paridade-transporte", "tela-nao-confessa", "cores-do-dualsense", "quatro-respostas-morde",
    "gesto-onde-deve-04", "gesto-em-lugar-vazio",
)


def _carregar(rel: str, nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, RAIZ / rel)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


RECIBO = _carregar("scripts/recibo_da_medida.py", "_recibo_do_rapido")
PROSA = _carregar("scripts/prosa_do_codigo.py", "_prosa_do_rapido")
DONO = _carregar("scripts/check_o_endereco_em_toda_forma.py", "_dono_do_rapido")


def _linhas_da_tabela() -> dict[str, list[str]]:
    texto = PORTOES.read_text(encoding="utf-8")
    corpo = texto[texto.index("cat <<'TABELA'"):texto.index("\nTABELA\n")]
    linhas: dict[str, list[str]] = {}
    for linha in corpo.splitlines()[1:]:
        if linha.startswith("#") or not linha.strip():
            continue
        campos = linha.split("|")
        linhas[campos[1]] = campos
    return linhas


TABELA = _linhas_da_tabela()


@pytest.mark.parametrize("ficha", DEZ)
def test_os_dez_mais_caros_declaram_o_que_leem(ficha: str) -> None:
    campos = TABELA[ficha]
    assert campos[0] == "rapido", f"{ficha} saiu da camada rápida"
    assert len(campos) == 5 and campos[4].strip(), (
        f"{ficha} perdeu a quinta coluna: a chave volta a ser a árvore inteira "
        "e qualquer byte o faz rodar")
    globs = [e for e in campos[4].split() if not e.startswith("@")]
    assert globs, f"{ficha} só declara sinal, nenhum glob"
    assert "@sempre" not in campos[4], f"{ficha} nunca seria lembrado"


def _git(raiz: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(raiz), *args], check=True, capture_output=True)


def _arquivo_que_casa(glob: str) -> str:
    """Um caminho que o glob declarado casa (o `**` vira uma pasta e um arquivo)."""
    return glob.replace("**", "dentro/arquivo.txt").replace("*", "x")


def _arvore_do_portao(tmp_path: Path, ficha: str) -> tuple[Path, list[str], list[str]]:
    """Uma árvore git com um arquivo por glob declarado, o script do portão e um arquivo de fora."""
    campos = TABELA[ficha]
    entradas = campos[4].split()
    raiz = tmp_path / "arvore"
    raiz.mkdir()
    _git(raiz, "init", "-q")
    dentro = [_arquivo_que_casa(g) for g in entradas if not g.startswith("@")]
    for rel in [*dentro, campos[3].split()[0], "docs/usage/fora.md", "README.md"]:
        alvo = raiz / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text("v1\n", encoding="utf-8")
    _git(raiz, "add", ".")
    return raiz, entradas, dentro


def _chave(raiz: Path, ficha: str, entradas: list[str]) -> str | None:
    campos = TABELA[ficha]
    ent = RECIBO.Entradas(raiz)
    chave: str | None = RECIBO.chave_do_portao(ent, "amb", ficha, campos[2], campos[3], entradas)
    return chave


@pytest.mark.parametrize("ficha", DEZ)
def test_tocar_fora_das_entradas_deixa_o_portao_lembrado(tmp_path: Path, ficha: str) -> None:
    raiz, entradas, _ = _arvore_do_portao(tmp_path, ficha)
    antes = _chave(raiz, ficha, entradas)
    assert antes is not None
    (raiz / "docs" / "usage" / "fora.md").write_text("v2\n", encoding="utf-8")
    (raiz / "README.md").write_text("v2\n", encoding="utf-8")
    assert _chave(raiz, ficha, entradas) == antes, (
        f"{ficha}: um arquivo que o portão não lê mudou e a memória esqueceu o verde")


@pytest.mark.parametrize("ficha", DEZ)
def test_tocar_uma_entrada_faz_o_portao_rodar(tmp_path: Path, ficha: str) -> None:
    raiz, entradas, dentro = _arvore_do_portao(tmp_path, ficha)
    for rel in dentro:
        antes = _chave(raiz, ficha, entradas)
        alvo = raiz / rel
        alvo.write_text(alvo.read_text(encoding="utf-8") + "mudou\n", encoding="utf-8")
        assert _chave(raiz, ficha, entradas) != antes, (
            f"{ficha}: {rel} mudou e o portão seria lembrado sobre bytes que ele lê")


def test_morde_o_glob_que_nao_casa_nada_faz_o_portao_rodar_sempre(tmp_path: Path) -> None:
    raiz, entradas, _ = _arvore_do_portao(tmp_path, "tela-nao-confessa")
    assert _chave(raiz, "tela-nao-confessa", entradas) is not None
    assert _chave(raiz, "tela-nao-confessa", ["pasta-que-nao-existe/**"]) is None


LIDO_DE_FORA = {
    "gesto-em-lugar-vazio": ("assets/glyphs/bateria.svg",),
    "portoes-lentos-rapidos": ("assets/glyphs/bateria.svg", "assets/glyphs/cross.svg"),
}


def _scripts_do_conftest() -> list[str]:
    texto = (RAIZ / "tests" / "conftest.py").read_text(encoding="utf-8")
    nomes = set(re.findall(r"^\s*import (\w+)\s*$", texto, re.M))
    nomes |= set(re.findall(r"^\s*from (\w+) import", texto, re.M))
    return sorted(f"scripts/{n}.py" for n in nomes if (RAIZ / "scripts" / f"{n}.py").is_file())


def _casados(ficha: str) -> set[str]:
    ent = RECIBO.Entradas(RAIZ)
    casados: set[str] = set()
    for padrao in TABELA[ficha][4].split():
        if not padrao.startswith("@"):
            casados |= ent.glob(padrao)
    return casados


def test_o_conftest_importa_um_script_e_a_lista_o_ve() -> None:
    assert "scripts/check_faixa_sintetica.py" in _scripts_do_conftest(), (
        "a leitura dos imports do conftest não acha mais o script que ele importa: a régua abaixo "
        "passaria sem medir nada")


@pytest.mark.parametrize("ficha", [f for f in DEZ if TABELA[f][2] == "pytest"])
def test_o_portao_pytest_leva_na_chave_o_que_o_conftest_importa(ficha: str) -> None:
    faltam = [s for s in _scripts_do_conftest() if s not in _casados(ficha)]
    assert not faltam, (
        f"{ficha}: o `tests/conftest.py` importa {faltam} em todo pytest, e a quinta coluna não o "
        "lê; mudá-lo deixaria o portão lembrado")


@pytest.mark.parametrize("ficha", sorted(LIDO_DE_FORA))
def test_o_que_o_gerador_le_fora_do_src_entra_na_chave(ficha: str) -> None:
    faltam = [rel for rel in LIDO_DE_FORA[ficha] if rel not in _casados(ficha)]
    assert not faltam, f"{ficha}: abre {faltam} e a quinta coluna não o lê"


_TEXTOS = (
    "player_slot_color = 1",
    "x = player_slot\n",
    "mesa_viva.VIA_DO_TRANSPORTE",
    "VIA_DO_TRANSPORTE_X",
    "_player_slot",
    "nada aqui",
    "a.player_slot(b)",
)


@pytest.mark.parametrize("texto", _TEXTOS)
@pytest.mark.parametrize(
    "simbolo", ("player_slot", "VIA_DO_TRANSPORTE", "data-volume=\"microfone\""))
def test_o_literal_primeiro_nao_muda_o_veredito_da_agulha(texto: str, simbolo: str) -> None:
    pela_agulha = PROSA.agulha(simbolo).search(texto) is not None
    assert PROSA.ocorre_no_texto(texto, simbolo) == pela_agulha


def test_morde_o_simbolo_dentro_de_outro_maior_continua_sem_casar(tmp_path: Path) -> None:
    arquivo = tmp_path / "x.py"
    arquivo.write_text("cor = player_slot_color\n# player_slot no comentário\n", encoding="utf-8")
    assert PROSA.cita(arquivo, "player_slot") is True
    assert PROSA.usa(arquivo, "player_slot") is False
    arquivo.write_text("cor = player_slot_color\n", encoding="utf-8")
    PROSA._CACHE.clear()
    assert PROSA.cita(arquivo, "player_slot") is False
    assert PROSA.usa(arquivo, "player_slot") is False


_OCTETOS = ("aa", "bb", "cc", "4c", "5d", "6e")


def _formas(o: tuple[str, ...]) -> dict[str, str]:
    virtuais = DONO.virtuais_da_maquina({o})
    virtual = next(iter(virtuais.values()))
    return {
        "separada": "uniq = " + ":".join(("aa", "bb", "cc", *o[3:])),
        "colada": "no=hefesto_som_" + "".join(o[3:]),
        "derivada": "vpad " + ":".join(virtual).upper(),
    }


def _varrer_linha_a_linha(arquivos: list[Path], padroes, coladas, virtuais) -> list[str]:  # type: ignore[no-untyped-def]
    """O `varrer` sem o filtro por arquivo: a referência que a cura tem de reproduzir."""
    original = DONO._tem_candidato
    try:
        vars(DONO)["_tem_candidato"] = lambda *_a, **_k: True
        return list(DONO.varrer(arquivos, padroes, coladas, virtuais))
    finally:
        vars(DONO)["_tem_candidato"] = original


@pytest.mark.parametrize("forma", ("separada", "colada", "derivada"))
def test_o_endereco_plantado_em_cada_forma_continua_reprovando(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forma: str) -> None:
    monkeypatch.setattr(DONO, "RAIZ", tmp_path)
    reais = {_OCTETOS}
    arquivo = tmp_path / "plantado.txt"
    arquivo.write_text("linha limpa\n" + _formas(_OCTETOS)[forma] + "\n", encoding="utf-8")
    args = (DONO.padrao_das_janelas(reais), DONO.janelas_coladas(reais),
            DONO.pedacos_dos_virtuais(DONO.virtuais_da_maquina(reais)))
    achados = DONO.varrer([arquivo], *args)
    assert achados and achados[0].startswith("plantado.txt:2:"), achados
    assert achados == _varrer_linha_a_linha([arquivo], *args)


def test_o_filtro_por_arquivo_da_o_mesmo_veredito_da_varredura_por_linha(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(DONO, "RAIZ", tmp_path)
    reais = {_OCTETOS, ("0a", "12", "34", "56", "78", "9a")}
    formas = _formas(_OCTETOS)
    casos = {
        "limpo.py": "def f():\n    return 'decada facada'\n",
        "borda.txt": "f" + "".join(_OCTETOS[3:]) + "f\n" + "4c-5d-6e-" + "\n",
        "isento.md": formas["separada"] + " <!-- endereco-de-mentira: fixture -->\n",
        "tudo.txt": "\n".join(formas.values()) + "\n" + formas["colada"].upper() + "\n",
        "espacado.txt": "aa bb cc 4c 5d 6e\n" + "0a.12.34.56.78.9a\n",
        "mascarado.txt": "aa:bb:cc:00:00:6e\n",
    }
    arquivos = []
    for nome, texto in casos.items():
        (tmp_path / nome).write_text(texto, encoding="utf-8")
        arquivos.append(tmp_path / nome)
    args = (DONO.padrao_das_janelas(reais), DONO.janelas_coladas(reais),
            DONO.pedacos_dos_virtuais(DONO.virtuais_da_maquina(reais)))
    achados = DONO.varrer(arquivos, *args)
    assert achados == _varrer_linha_a_linha(arquivos, *args)
    nomes = {a.split(":", 1)[0] for a in achados}
    assert {"tudo.txt", "espacado.txt"} <= nomes
    assert not nomes & {"limpo.py", "isento.md", "mascarado.txt"}, achados

