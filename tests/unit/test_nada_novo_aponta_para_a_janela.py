"""A régua do portão `nada novo aponta para a janela` — sprint GTK-1, 06/09/2026.

O portão (`scripts/check_nada_aponta_para_a_janela.py`) tem DUAS METADES, e este
arquivo prova as duas com a MORDIDA: cada uma é exercitada com a cura arrancada,
para que se veja reprovar, e devolvida.

  METADE 1 — um import novo de `gui/` fora da lista reprova, nomeando arquivo e
             linha.
  METADE 2 — uma linha nova no inventário sem veredito reprova.

**Por que o portão existe**, decisão dela em 06/09/2026
(`D-0609-GTK-LEVA-INTEIRA`): *"a ideia sempre foi reaproveitar o que fiz no gtk
e não apontar nada mais pra lá mas pro html"*. A janela sai em três sprints; enquanto ela
sai, nada novo pode passar a apontar para lá — senão a `GTK-3` persegue um alvo
que cresce.

**ESTA RÉGUA NÃO MEDE A ÁRVORE, MEDE O PORTÃO.** Ela monta uma árvore de
mentira em `tmp_path` e aponta o módulo do portão para lá, trocando `RAIZ` e
`CSV_DO_INVENTARIO`. Medir a árvore de verdade faria a régua reprovar por
trabalho de outra sprint, que é o defeito que esta casa chama de *"a régua mede
o mundo de ontem"*.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

RAIZ_DE_VERDADE = Path(__file__).resolve().parents[2]
PORTAO = RAIZ_DE_VERDADE / "scripts" / "check_nada_aponta_para_a_janela.py"


def _carregar_portao():
    """Importa o portão como módulo próprio, sem poluir `sys.modules` de ninguém."""
    espec = importlib.util.spec_from_file_location(
        "portao_nada_aponta_para_a_janela", PORTAO
    )
    assert espec and espec.loader
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


_CABECALHO = "# inventário de mentira, só para a régua\n"
_COLUNAS = (
    "arquivo,linhas,alvo,natureza,ocorrencias,pergunta_respondida,veredito,razao\n"
)


@pytest.fixture
def casa(tmp_path, monkeypatch):
    """Uma árvore de mentira com UM arquivo que cita a janela, e o CSV que o declara."""
    modulo = _carregar_portao()

    pacote = tmp_path / "src" / "hefesto_dualsense4unix" / "interface"
    pacote.mkdir(parents=True)
    (pacote / "aba_qualquer.py").write_text(
        "from hefesto_dualsense4unix.gui import ponte_da_tela\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "scripts").mkdir()

    inventario = tmp_path / "docs" / "data" / "o-que-ainda-aponta-para-a-janela.csv"
    inventario.parent.mkdir(parents=True)
    inventario.write_text(
        _CABECALHO
        + _COLUNAS
        + "src/hefesto_dualsense4unix/interface/aba_qualquer.py,1,gui.ponte_da_tela,"
        "import,1,quem cita? a interface nova,MOTOR-MUDA-DE-CASA,"
        "o piloto HTML fica e muda de endereço\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(modulo, "RAIZ", tmp_path)
    monkeypatch.setattr(modulo, "CSV_DO_INVENTARIO", inventario)
    return modulo, tmp_path, inventario


def test_a_base_da_regua_esta_verde(casa, capsys):
    """Sem mordida nenhuma, a árvore de mentira passa. É o zero da régua."""
    modulo, _, _ = casa
    assert modulo.comando_portao() == 0
    assert "OK:" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# METADE 1 — um import NOVO de `gui/` reprova, nomeando arquivo e linha
# ---------------------------------------------------------------------------


def test_metade_1_import_novo_de_gui_reprova_nomeando_arquivo_e_linha(casa, capsys):
    modulo, raiz, _ = casa
    alvo = raiz / "src" / "hefesto_dualsense4unix" / "interface" / "aba_nova.py"
    alvo.write_text(
        "# uma aba nova da interface\n"
        "from hefesto_dualsense4unix.gui import app\n",
        encoding="utf-8",
    )

    assert modulo.comando_portao() == 1
    saida = capsys.readouterr().out
    assert "CITAÇÃO NOVA" in saida
    assert "src/hefesto_dualsense4unix/interface/aba_nova.py:2" in saida, saida
    assert "gui.app" in saida


def test_metade_1_a_lista_so_diminui_ocorrencia_a_mais_reprova(casa, capsys):
    """Um import a MAIS num arquivo já declarado também reprova: a lista só encolhe."""
    modulo, raiz, _ = casa
    alvo = raiz / "src" / "hefesto_dualsense4unix" / "interface" / "aba_qualquer.py"
    alvo.write_text(
        "from hefesto_dualsense4unix.gui import ponte_da_tela\n"
        "from hefesto_dualsense4unix.gui import ponte_da_tela as segunda\n",
        encoding="utf-8",
    )

    assert modulo.comando_portao() == 1
    saida = capsys.readouterr().out
    assert "CRESCEU" in saida
    assert "1 declarada(s), 2 viva(s)" in saida, saida


def test_metade_1_a_cura_devolvida_passa(casa, capsys):
    """Desfeita a mordida, o portão volta ao verde — senão ele só sabe reprovar."""
    modulo, raiz, _ = casa
    alvo = raiz / "src" / "hefesto_dualsense4unix" / "interface" / "aba_nova.py"
    alvo.write_text("from hefesto_dualsense4unix.gui import app\n", encoding="utf-8")
    assert modulo.comando_portao() == 1
    capsys.readouterr()

    alvo.unlink()
    assert modulo.comando_portao() == 0
    assert "OK:" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# METADE 2 — linha nova no CSV sem veredito reprova
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("coluna", "valor", "esperado"),
    [
        ("veredito", "", "não é um dos três"),
        ("veredito", "TALVEZ", "não é um dos três"),
        ("pergunta_respondida", "", "`pergunta_respondida` vazia"),
        ("razao", "", "`razao` vazia"),
        ("ocorrencias", "muitas", "`ocorrencias` não é número"),
    ],
)
def test_metade_2_linha_sem_veredito_reprova(casa, capsys, coluna, valor, esperado):
    modulo, raiz, inventario = casa
    (raiz / "scripts" / "instrumento.py").write_text(
        "CAMINHO = 'main.glade'\n", encoding="utf-8"
    )
    campos = {
        "arquivo": "scripts/instrumento.py",
        "linhas": "1",
        "alvo": "gui/main.glade",
        "natureza": "código",
        "ocorrencias": "1",
        "pergunta_respondida": "quem cita? um script",
        "veredito": "SAI-COM-A-JANELA",
        "razao": "some com a janela",
    }
    campos[coluna] = valor
    with inventario.open("a", encoding="utf-8") as destino:
        destino.write(",".join(campos[nome] for nome in modulo.COLUNAS) + "\n")

    assert modulo.comando_portao() == 1
    assert esperado in capsys.readouterr().out


def test_metade_2_linha_declarada_por_inteiro_passa(casa, capsys):
    """A mesma linha, com veredito, pergunta e razão, passa. A mordida se desfaz."""
    modulo, raiz, inventario = casa
    (raiz / "scripts" / "instrumento.py").write_text(
        "CAMINHO = 'main.glade'\n", encoding="utf-8"
    )
    with inventario.open("a", encoding="utf-8") as destino:
        destino.write(
            "scripts/instrumento.py,1,gui/main.glade,código,1,"
            "quem cita? um script da janela,SAI-COM-A-JANELA,some com a janela\n"
        )

    assert modulo.comando_portao() == 0
    assert "OK:" in capsys.readouterr().out


def test_metade_2_par_repetido_reprova(casa, capsys):
    """Duas linhas para o mesmo (arquivo, alvo) escondem uma das duas."""
    modulo, _, inventario = casa
    with inventario.open("a", encoding="utf-8") as destino:
        destino.write(
            "src/hefesto_dualsense4unix/interface/aba_qualquer.py,1,gui.ponte_da_tela,"
            "import,1,outra leitura,MOTOR-MUDA-DE-CASA,outra razão\n"
        )

    assert modulo.comando_portao() == 1
    assert "par repetido" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# O QUE NÃO REPROVA — e é decisão, não descuido
# ---------------------------------------------------------------------------


def test_a_lista_que_encolheu_avisa_mas_nao_reprova(casa, capsys):
    modulo, raiz, _ = casa
    (raiz / "src" / "hefesto_dualsense4unix" / "interface" / "aba_qualquer.py").unlink()

    assert modulo.comando_portao() == 0
    saida = capsys.readouterr().out
    assert "encolheu" in saida
    assert "--podar" in saida


def test_o_podar_so_encolhe(casa, capsys):
    """`--podar` apaga a linha cujo par sumiu, e NUNCA acrescenta uma nova.

    Se ele acrescentasse, bastaria rodá-lo para lavar uma citação nova — e o
    portão passaria a assinar embaixo do que devia barrar.
    """
    modulo, raiz, inventario = casa
    (raiz / "src" / "hefesto_dualsense4unix" / "interface" / "aba_qualquer.py").unlink()
    nova = raiz / "src" / "hefesto_dualsense4unix" / "interface" / "outra.py"
    nova.write_text("from hefesto_dualsense4unix.gui import app\n", encoding="utf-8")

    assert modulo.comando_podar() == 0
    capsys.readouterr()

    texto = inventario.read_text(encoding="utf-8")
    assert "aba_qualquer.py" not in texto, "a linha morta tinha de ter sido podada"
    assert "outra.py" not in texto, "o --podar NÃO pode acrescentar citação nova"
    assert modulo.comando_portao() == 1, "a citação nova continua reprovando"


# ---------------------------------------------------------------------------
# A RÉGUA NÃO SE MEDE
# ---------------------------------------------------------------------------


def test_o_portao_nao_se_varre_a_si_mesmo():
    """O script, o CSV e este arquivo citam os alvos porque SÃO o instrumento.

    Sem `_NAO_SE_VARRE` o portão nasceria acusando a si mesmo — e esta leva já
    achou três réguas que mediam a si mesmas.
    """
    modulo = _carregar_portao()
    assert "scripts/check_nada_aponta_para_a_janela.py" in modulo._NAO_SE_VARRE
    assert "tests/unit/test_nada_novo_aponta_para_a_janela.py" in modulo._NAO_SE_VARRE
    assert "docs/data/o-que-ainda-aponta-para-a-janela.csv" in modulo._NAO_SE_VARRE


def test_a_prosa_nao_e_chamada():
    """`tokenize`, não `grep`: a sprint avisa que a maioria das citações é comentário."""
    modulo = _carregar_portao()
    fonte = (
        "import os\n"
        "# o texto vem de main.glade, em prosa\n"
        'CAMINHO = "main.glade"\n'
        '"""docstring que cita main.glade também."""\n'
    )
    prosa = modulo._prosa_do_python(fonte)
    natureza = []
    for numero, linha in enumerate(fonte.splitlines(), start=1):
        for _, coluna in modulo._alvos_da_linha(linha):
            natureza.append(modulo._natureza(linha, coluna, numero, ".py", prosa))
    assert natureza == ["prosa", "código", "prosa"], natureza


def test_o_arquivo_nao_cita_a_si_mesmo(casa, capsys):
    """`app/app.py` falando de `app/app.py` não é apontar para a janela: é a janela."""
    modulo, raiz, _ = casa
    janela = raiz / "src" / "hefesto_dualsense4unix" / "app"
    janela.mkdir(parents=True)
    (janela / "app.py").write_text(
        "# ver app/app.py e hefesto_dualsense4unix.app.app\n", encoding="utf-8"
    )

    assert modulo.comando_portao() == 0
    assert "OK:" in capsys.readouterr().out


def test_a_peneira_nao_muda_a_conta():
    """A peneira barata tem de fazer a MESMA pergunta do filtro.

    **A cicatriz:** a primeira peneira era uma lista de cadeias escrita à mão, e
    ela perdeu 20 pares e 35 citações de uma vez — nenhuma das cadeias cobria
    `hefesto_dualsense4unix.app.app` na forma pontuada. Peneira que não é o
    filtro é portão que mede menos do que diz medir, em silêncio.

    Aqui a igualdade é exercitada linha a linha: tudo o que `_alvos_da_linha`
    acha, a peneira TEM de deixar passar.
    """
    modulo = _carregar_portao()
    amostras = [
        "from hefesto_dualsense4unix.app.app import HefestoApp",
        "import hefesto_dualsense4unix.app.app as app_mod",
        "from hefesto_dualsense4unix.app import main as app_main",
        'MAIN_GLADE = GUI_DIR / "main.glade"',
        "# a paleta vem do gui/theme.css",
        "from hefesto_dualsense4unix.gui import ponte_da_tela",
        "hefesto_dualsense4unix.gui.widgets.button_glyph",
        "# ver gui/aba_conexoes.py",
        "python3 -m hefesto_dualsense4unix.app.main",
    ]
    for amostra in amostras:
        assert modulo._alvos_da_linha(amostra), f"o filtro não achou: {amostra}"
        assert modulo._PENEIRA.search(amostra), f"a peneira barrou: {amostra}"


def test_os_tres_vereditos_sao_os_do_plano():
    modulo = _carregar_portao()
    assert {
        "SAI-COM-A-JANELA",
        "MOTOR-MUDA-DE-CASA",
        "NUNCA-DEVIA-CITAR",
    } == modulo.VEREDITOS


# ---------------------------------------------------------------------------
# O INVENTÁRIO DE VERDADE — o que a GTK-3 vai levar a zero
# ---------------------------------------------------------------------------


def test_o_inventario_de_verdade_existe_e_esta_declarado_por_inteiro():
    """A árvore de verdade passa no portão, e o inventário não está vazio."""
    modulo = _carregar_portao()
    inventario = modulo.ler_o_inventario()
    assert inventario, "o inventário da GTK-1 não pode nascer vazio"
    for linha in inventario:
        assert linha["veredito"] in modulo.VEREDITOS, linha
        assert linha["pergunta_respondida"].strip(), linha
        assert linha["razao"].strip(), linha
