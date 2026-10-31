"""O portão do texto sem pessoa MORDE: uma palavra de cada classe, no texto ou no nome, reprova."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_texto_sem_pessoa.py"

_P = "e" + "la"
_POSTO = "ban" + "cada"
_NOME = "Vit" + "ória"
_CONTA = "vit" + "oria" + "maria"


def _carregar():
    spec = importlib.util.spec_from_file_location("_texto_sem_pessoa_sob_teste", PORTAO)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def portao():
    return _carregar()


def _repo(tmp_path: Path, arquivos: dict[str, str]) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for rel, texto in arquivos.items():
        caminho = tmp_path / rel
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


LIMPO = (
    "A janela abre a tabela; a estrela, a panela, a célula e a cautela ficam.\n"
    "A vitória do time não é nome de ninguém. A querela e a sequela também passam.\n"
    "«Fica sem perfil» é o rótulo do botão (29/09).\n"
)


@pytest.mark.parametrize(
    ("linha", "classe"),
    [
        (f"A aba mostra o que {_P} sabe.", "pronome"),
        (f"o perfil d{_P} volta", "pronome"),
        (f"o perfil d{_P}s volta", "pronome"),
        (f"pensou n{_P}", "pronome"),
        (f"{_P.upper()} decide", "pronome"),
        (f"def o_servico_d{_P}():", "pronome"),
        (f"servicoD{_P} = 1", "pronome"),
        (f"o ensaio na {_POSTO}", "posto"),
        (f"from x import {_POSTO}_do_mapa", "posto"),
        (f"as {_POSTO.upper()}S de BT", "posto"),
        (f"o controle da {_NOME}", "nome"),
        (f"com.{_CONTA}.App", "nome"),
        ("o texto  <!-- noqa-acento: " + "cita" + "ção literal -->", "citacao"),
        ("as palavras do " + "usuário: «isso fica assim»", "citacao"),
        ("ordem de " + "produto, *\"setar o jogo\"*", "citacao"),
        ("«v" + "c toma a decisão»", "citacao"),
    ],
)
def test_cada_classe_morde_no_conteudo(portao, linha, classe):
    assert classe in portao.classes_da_linha(linha)


def test_as_palavras_que_so_contem_as_letras_nao_casam(portao):
    for linha in LIMPO.splitlines():
        assert portao.classes_da_linha(linha) == [], linha


@pytest.mark.parametrize(
    ("rel", "classe"),
    [
        (f"tests/unit/test_o_mapa_que_{_P}_corrige.py", "pronome"),
        (f"scripts/{_POSTO}_do_radio.py", "posto"),
        (f"data/com.{_CONTA}.App.desktop", "nome"),
    ],
)
def test_o_nome_do_caminho_morde(portao, tmp_path, rel, classe):
    raiz = _repo(tmp_path, {rel: "conteúdo neutro\n"})
    achadas = portao.varrer(raiz)
    assert [(o.rel, o.linha, o.classe) for o in achadas] == [(rel, 0, classe)]


def test_a_arvore_limpa_passa_e_a_suja_reprova(portao, tmp_path, monkeypatch, capsys):
    raiz = _repo(tmp_path, {"README.md": LIMPO, "janela.py": "JANELA = 1\n"})
    monkeypatch.setattr(portao, "RAIZ", raiz)
    monkeypatch.setattr(portao, "ISENTOS", {})
    assert portao.main([]) == 0
    (raiz / "src").mkdir()
    (raiz / "src" / "a.py").write_text(f"# o ensaio na {_POSTO}\n", encoding="utf-8")
    assert portao.main([]) == 1
    assert "src/a.py:1: posto" in capsys.readouterr().out


def test_o_gancho_do_commit_mede_so_os_caminhos_dados(portao, tmp_path, monkeypatch, capsys):
    raiz = _repo(tmp_path, {"limpo.md": LIMPO, "sujo.md": f"a {_POSTO} de antes\n"})
    monkeypatch.setattr(portao, "RAIZ", raiz)
    monkeypatch.setattr(portao, "ISENTOS", {})
    assert portao.main(["limpo.md"]) == 0
    assert portao.main(["limpo.md", "sujo.md"]) == 1
    assert "sujo.md:1: posto" in capsys.readouterr().out
    (raiz / f"{_POSTO}.md").write_text(LIMPO, encoding="utf-8")
    assert portao.main([f"{_POSTO}.md"]) == 1


def test_a_autoria_legal_passa_so_na_linha_de_identidade(portao, tmp_path):
    raiz = _repo(
        tmp_path,
        {
            "po/pt_BR.po": (
                f'"Last-Translator: {_NOME[:3]}oria Maria <x@y>\\n"\n#. o controle da {_NOME}\n'
            ),
            "docs/x.md": f"{_NOME[:3]}oria Maria <x@y>\n",
        },
    )
    achadas = {(o.rel, o.linha) for o in portao.varrer(raiz)}
    assert achadas == {("po/pt_BR.po", 2), ("docs/x.md", 1)}


def test_o_relatorio_conta_por_area(portao):
    ocorre = portao.Ocorrencia
    achadas = [
        ocorre("src/a.py", 1, "posto", ""),
        ocorre("README.md", 1, "pronome", ""),
        ocorre("docs/a.md", 1, "posto", ""),
        ocorre("scripts/a.py", 1, "posto", ""),
        ocorre("tests/unit/test_a_x.py", 1, "posto", ""),
        ocorre("tests/unit/test_o_x.py", 1, "posto", ""),
        ocorre("tests/unit/test_bateria.py", 1, "posto", ""),
        ocorre("tests/conftest.py", 1, "posto", ""),
    ]
    assert [portao.area(o.rel) for o in achadas] == [
        "produto", "produto", "docs", "scripts", "tests-a", "tests-o", "tests-resto", "tests-resto",
    ]
    linhas = portao.relatorio(achadas)
    assert linhas[1].split()[:3] == ["produto", "2", "2"]
    assert linhas[-2].split()[:2] == ["total", "8"]


def test_a_regua_nao_se_isenta(portao):
    assert "scripts/check_texto_sem_pessoa.py" not in portao.ISENTOS
    assert "tests/unit/test_o_texto_nao_fala_de_pessoa.py" not in portao.ISENTOS
    texto = PORTAO.read_text(encoding="utf-8") + Path(__file__).read_text(encoding="utf-8")
    assert all(portao.classes_da_linha(linha) == [] for linha in texto.splitlines())


_D = "d" + _P


@pytest.mark.parametrize(
    "linha",
    [
        f'POR_ESCOLHA_DO_USUARIO = "escolha_{_D}"',
        f"o escritor carimba a ponte `por=escolha_{_D}` quando o perfil grava",
        f'novas["declarado_por_{_P}"] = _fato(x, y)',
        f'DECLARADO_PELO_USUARIO = "declarado-por-{_P}"',
        f'_MARCA_DA_ESCOLHA = ".a_escolha_{_D}_migrada"',
        f"    recebe: espera-{_P}",
    ],
)
def test_o_nome_gravado_de_antes_nao_tem_isencao(portao, linha):
    assert "pronome" in portao.classes_da_linha(linha)


def test_o_nome_gravado_de_antes_reprova_no_varrer(portao, tmp_path):
    texto = f'VALOR = "escolha_{_D}"\nPARTES = "escolha_d" + "e" + "la"\n'
    raiz = _repo(tmp_path, {"src/a.py": texto})
    assert [(o.linha, o.classe) for o in portao.varrer(raiz)] == [(1, "pronome")]
