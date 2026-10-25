"""O sinal ``PRESENTE`` da paridade é código, e não comentário: a FORMA do sinal decide a pergunta.

O-SINAL-PRESENTE-DA-PARIDADE-E-CODIGO-E-NAO-COMENTARIO-01 (25/10/2026). Até ali o
``scripts/check_paridade_gtk_html.py`` conferia toda linha ``PRESENTE`` por presença (``ocorre``), e
44 linhas do CSV passavam verdes com o símbolo vivo só num comentário ou numa docstring. A cura tem
um dono, ``scripts/prosa_do_codigo.py``: a citação por desenho (caminho, nome de arquivo, ID de
decisão) basta aparecer; o símbolo de código tem de ser USADO.

E o ``sem_comentario`` passou a conhecer o CSS, o C e o shell: sem isso, o ``.css`` e o ``.sh`` do
lado HTML contavam o comentário como uso, e a régua de cima mentia nesses arquivos.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_paridade_gtk_html.py"
sys.path.insert(0, str(RAIZ / "scripts"))

import prosa_do_codigo


@pytest.fixture(scope="module")
def portao() -> ModuleType:
    """O portão como módulo, sem rodar o ``main``."""
    spec = importlib.util.spec_from_file_location("_paridade_gtk_html_presente", PORTAO)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_paridade_gtk_html_presente"] = mod
    spec.loader.exec_module(mod)
    return mod


def _arquivo(tmp_path: Path, nome: str, corpo: str) -> Path:
    p = tmp_path / nome
    p.write_text(corpo, encoding="utf-8")
    return p


# ── A forma ─────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("sinal", [
    "app/actions/mode_transition.plan_mode_transition",
    "core/ds_output_report.py:106",
    "test_os_donos_de_fato.py",
    "disable_steam_input.sh",
    "D-A-CONTAGEM-DO-EXAME-SAIU",
])
def test_a_citacao_por_desenho_se_reconhece_pela_forma(sinal: str) -> None:
    assert prosa_do_codigo.e_citacao(sinal), sinal


@pytest.mark.parametrize("sinal", [
    "GESTO_DO_STEAM_INPUT",
    "home_actions.aviso_do_wrapper",
    ".selo.grave",
    'data-gesto="lado"',
    "editor.prioridade.escolha",
    "trigger_reset_detalhado",
])
def test_o_simbolo_de_codigo_nao_e_citacao(sinal: str) -> None:
    assert not prosa_do_codigo.e_citacao(sinal), sinal


def test_o_simbolo_so_num_comentario_reprova_o_presente(portao: ModuleType, tmp_path: Path) -> None:
    """O defeito medido: o símbolo sobrava num comentário, e a linha ``PRESENTE`` passava verde."""
    alvo = _arquivo(tmp_path, "comentario.py",
                    "X = 1  # antes daqui se chamava GESTO_DO_STEAM_INPUT\n")
    assert prosa_do_codigo.presente(alvo, "GESTO_DO_STEAM_INPUT") is False
    assert portao.Arvore().presente("GESTO_DO_STEAM_INPUT", [alvo]) is None, (
        "símbolo citado só num comentário não é usado: o PRESENTE tem de reprovar")


def test_o_simbolo_so_numa_docstring_reprova_o_presente(portao: ModuleType, tmp_path: Path) -> None:
    alvo = _arquivo(tmp_path, "docstring.py",
                    'def f():\n    """O TIQUE_MS da janela antiga saiu."""\n    return 1\n')
    assert prosa_do_codigo.presente(alvo, "TIQUE_MS") is False
    assert portao.Arvore().presente("TIQUE_MS", [alvo]) is None


def test_o_simbolo_usado_passa_o_presente(portao: ModuleType, tmp_path: Path) -> None:
    alvo = _arquivo(tmp_path, "usado.py", "GESTO_DO_STEAM_INPUT = 'steam-input'\n")
    assert prosa_do_codigo.presente(alvo, "GESTO_DO_STEAM_INPUT") is True
    assert portao.Arvore().presente("GESTO_DO_STEAM_INPUT", [alvo]) == alvo


@pytest.mark.parametrize("caminho", [
    "app/actions/mode_transition.plan_mode_transition",
    "scripts/foo.sh",
    "test_os_donos_de_fato.py",
])
def test_o_caminho_so_num_comentario_continua_passando(
        portao: ModuleType, tmp_path: Path, caminho: str) -> None:
    """O outro lado: a citação só PODE viver na prosa, e sem ele as linhas que citam emudeceriam."""
    alvo = _arquivo(tmp_path, "cita.py", f"X = 1  # a prova mora em {caminho}\n")
    assert prosa_do_codigo.presente(alvo, caminho) is True
    assert portao.Arvore().presente(caminho, [alvo]) == alvo


def test_a_docstring_com_acento_nao_desloca_o_comentario(tmp_path: Path) -> None:
    """O ``col_offset`` do ``ast`` conta bytes: sem :func:`prosa_do_codigo._coluna`, a docstring
    acentuada apagava o começo da linha de baixo, o ``tokenize`` caía e o comentário voltava a
    contar (60 arquivos do ``src/``, 2.493 comentários, medido em 25/10/2026)."""
    corpo = (
        "def f():\n"
        '    """Ação — é só prosa."""\n'
        "    valor = 1  # cita o SIMBOLO_FANTASMA\n"
        "    return valor\n"
    )
    limpo = prosa_do_codigo.sem_prosa(corpo, ".py")
    assert "SIMBOLO_FANTASMA" not in limpo
    assert "valor = 1" in limpo and "return valor" in limpo
    assert limpo.count("\n") == corpo.count("\n")


# ── Os sufixos ──────────────────────────────────────────────────────────────────────────────────


CASOS_DE_SUFIXO = {
    ".css": (
        "/* .selo.grave era a quarta cor */\n.selo { color: red; }\n",
        ".selo.ok { color: green; }\n/* nada */\n",
        ".selo.grave", ".selo.ok",
    ),
    ".c": (
        "// hefesto_antigo() saiu\nint x = 1; /* hefesto_antigo */\n",
        "int main(void) { return hefesto_novo(); }\n",
        "hefesto_antigo", "hefesto_novo",
    ),
    ".h": (
        "/* HEFESTO_VELHO\n   em duas linhas */\n#define A 1\n",
        "#define HEFESTO_NOVO 2  // o novo\n",
        "HEFESTO_VELHO", "HEFESTO_NOVO",
    ),
    ".sh": (
        "#!/bin/bash\n# chama_o_velho saiu\necho ok  # chama_o_velho\n",
        "#!/bin/bash\nchama_o_novo \"$@\"\n",
        "chama_o_velho", "chama_o_novo",
    ),
}


@pytest.mark.parametrize("sufixo", sorted(CASOS_DE_SUFIXO))
def test_o_nome_no_comentario_nao_e_uso(sufixo: str, tmp_path: Path) -> None:
    so_comentario, _, nome, _ = CASOS_DE_SUFIXO[sufixo]
    assert sufixo in prosa_do_codigo.SUFIXOS_COM_COMENTARIO
    limpo = prosa_do_codigo.sem_comentario(so_comentario, sufixo)
    assert nome not in limpo, f"{sufixo}: o comentário sobrou em {limpo!r}"
    alvo = _arquivo(tmp_path, f"comentario{sufixo}", so_comentario)
    assert prosa_do_codigo.usa(alvo, nome) is False
    assert prosa_do_codigo.cita(alvo, nome) is True


@pytest.mark.parametrize("sufixo", sorted(CASOS_DE_SUFIXO))
def test_o_nome_no_codigo_e_uso(sufixo: str, tmp_path: Path) -> None:
    _, no_codigo, _, nome = CASOS_DE_SUFIXO[sufixo]
    alvo = _arquivo(tmp_path, f"uso{sufixo}", no_codigo)
    assert prosa_do_codigo.usa(alvo, nome) is True


@pytest.mark.parametrize("sufixo", sorted(CASOS_DE_SUFIXO))
def test_as_quebras_de_linha_ficam_no_lugar(sufixo: str) -> None:
    """A citação de linha depende disso: as mesmas linhas, cada uma do mesmo tamanho."""
    for corpo in CASOS_DE_SUFIXO[sufixo][:2]:
        limpo = prosa_do_codigo.sem_comentario(corpo, sufixo)
        tamanhos = [len(linha) for linha in corpo.split("\n")]
        assert [len(linha) for linha in limpo.split("\n")] == tamanhos


def test_o_shebang_fica() -> None:
    limpo = prosa_do_codigo.sem_comentario("#!/usr/bin/env bash\n# fora\nexit 0\n", ".sh")
    assert limpo.startswith("#!/usr/bin/env bash\n")
    assert "fora" not in limpo


@pytest.mark.parametrize("linha", [
    'echo "$#" ${#lista[@]}',
    'echo "a # b"',
    "echo 'a # b'",
    "url=a#b",
    r"echo \# literal",
])
def test_o_cerquilha_que_nao_abre_comentario_no_shell(linha: str) -> None:
    corpo = f"{linha}\n"
    assert prosa_do_codigo.sem_comentario(corpo, ".sh") == corpo


def test_o_corpo_do_heredoc_e_dado() -> None:
    corpo = "cat <<'FIM'\n# isto é texto do heredoc\nFIM\n# isto é comentário\n"
    limpo = prosa_do_codigo.sem_comentario(corpo, ".sh")
    assert "# isto é texto do heredoc" in limpo
    assert "comentário" not in limpo


def test_a_cadeia_do_c_fica_inteira() -> None:
    corpo = 'const char *s = "/* não é comentário */ // nem isto";\n'
    assert prosa_do_codigo.sem_comentario(corpo, ".c") == corpo


def test_o_url_do_css_nao_e_comentario() -> None:
    corpo = ".a { background: url(http://exemplo/x.png); }\n"
    assert prosa_do_codigo.sem_comentario(corpo, ".css") == corpo


def test_o_css_dentro_do_html_perde_o_comentario() -> None:
    corpo = "<style>\n/* .selo.grave */\n.selo { }\n</style>\n<p>x</p>\n"
    limpo = prosa_do_codigo.sem_comentario(corpo, ".html")
    assert ".selo.grave" not in limpo and ".selo { }" in limpo
    assert limpo.count("\n") == corpo.count("\n")
