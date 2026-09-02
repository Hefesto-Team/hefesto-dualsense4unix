"""A TRAVA DA TELA DELA — nenhuma janela nasce visível quando o ambiente proíbe.

**ESTE ARQUIVO NASCEU DE UMA FOTO.** Em 02/09/2026, com treze frentes de agente
em voo, oito cópias da MESMA janela nasceram empilhadas na tela dela, em cima do
que ela estava fazendo. Ela fotografou e perguntou: *"pq sempre abre essas
inúmeras abas da mmesma tela?"*.

**O `--oculta` já existia, e a regra da casa sempre foi usá-lo.** Não bastou, e a
razão é estrutural, não de disciplina: a regra vivia no PROMPT de quem abre. Todo
caminho novo — um teste, um script de ensaio, um visor antigo, uma frente com
pressa — nasce sem ela. E o custo não cai em quem esqueceu: cai na tela DELA, que
é uma só.

**Uma regra que depende de quem chama lembrar dela não é regra. É sorte.** Por
isso a trava mora no dono ÚNICO da criação de janela (`gui/ponte_da_tela`) e é do
AMBIENTE: quem exporta ``HEFESTO_SEM_JANELA`` não abre janela visível nem
querendo.

O que estas réguas cobram, e cada uma morde um pedaço diferente:

1. a trava existe e responde ao ambiente (`janela_proibida_na_tela`);
2. com a variável no ar, o construtor da janela escolhe ``Gtk.OffscreenWindow``
   mesmo quando o chamador pediu janela na tela — é o coração da cura;
3. SEM a variável, nada muda: o produto continua abrindo para quem o chamou.
   Uma trava que sequestra a janela do produto seria pior que o defeito;
4. o visor `ver.py`, que é visível de propósito, RECUSA em vez de esconder;
5. nenhum arquivo de teste desta casa cria janela visível na importação — que é
   como o pytest a abriria só por COLETAR o arquivo.

A quinta é a que pega a classe inteira do defeito sem depender de ninguém rodar
nada: ela lê o fonte dos testes e reprova quem chama ``show_all()``/``present()``
sobre uma ``Gtk.Window`` no corpo do módulo.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

_RAIZ = pathlib.Path(__file__).resolve().parents[2]
_TESTES = _RAIZ / "tests"


# ---------------------------------------------------------------------------
# 1 e 2 — a trava existe, e ela decide
# ---------------------------------------------------------------------------
def test_a_trava_le_o_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDE: sem ler o ambiente a cada chamada, a trava vira estado congelado.

    Lê-la uma vez na importação faria um teste que exporta a variável no meio da
    sessão ser ignorado — e é exatamente assim que uma leva de agente a usa.
    """
    from hefesto_dualsense4unix.gui.ponte_da_tela import (
        SEM_JANELA_NA_TELA,
        janela_proibida_na_tela,
    )

    monkeypatch.delenv(SEM_JANELA_NA_TELA, raising=False)
    assert janela_proibida_na_tela() is False

    monkeypatch.setenv(SEM_JANELA_NA_TELA, "1")
    assert janela_proibida_na_tela() is True, (
        "a trava não viu a variável — se ela lê o ambiente só na importação, "
        "toda leva de agente volta a abrir janela na tela dela"
    )

    # Vazio e só-espaço não travam: quem exporta a variável em branco não pediu
    # nada, e travar aí calaria a janela do produto por um `export` distraído.
    monkeypatch.setenv(SEM_JANELA_NA_TELA, "   ")
    assert janela_proibida_na_tela() is False


def test_o_construtor_escolhe_a_oculta_quando_o_ambiente_proibe() -> None:
    """O CORAÇÃO DA CURA, lido no fonte: a decisão vem ANTES do `if oculta`.

    Não abre janela nenhuma (nem oculta): ler o fonte é o que permite esta régua
    rodar no CI sem display, e é o mesmo caminho que o portão `casa-sabe` usa
    para cobrar cura escrita e nunca ligada.
    """
    caminho = _RAIZ / "src/hefesto_dualsense4unix/gui/ponte_da_tela.py"
    fonte = caminho.read_text(encoding="utf-8")

    # POR AST, E NÃO POR BUSCA DE TEXTO — a primeira versão desta régua procurava
    # `janela_proibida_na_tela()` no arquivo inteiro, e a DEFINIÇÃO da função já
    # satisfazia a busca. Arranquei a chamada do construtor e ela passou verde.
    # É o defeito clássico desta casa: a régua que mede a PALAVRA em vez do ATO.
    arvore = ast.parse(fonte)
    construtores = [
        no
        for classe in arvore.body
        if isinstance(classe, ast.ClassDef)
        for no in classe.body
        if isinstance(no, ast.FunctionDef) and no.name == "__init__"
    ]
    assert construtores, "não achei o construtor da janela para auditar"

    chama = any(
        isinstance(dentro, ast.Call)
        and isinstance(dentro.func, ast.Name)
        and dentro.func.id == "janela_proibida_na_tela"
        for init in construtores
        for dentro in ast.walk(init)
    )
    assert chama, (
        "o CONSTRUTOR da janela não chama a trava. Ela pode estar definida no "
        "módulo e não ser usada — que é a forma preferida desta casa de "
        "fabricar cura de mentira, e o portão `casa-sabe` existe por isso"
    )

    # A ordem importa: a trava tem de decidir ANTES de a janela na tela nascer.
    linha_da_trava = min(
        dentro.lineno
        for init in construtores
        for dentro in ast.walk(init)
        if isinstance(dentro, ast.Call)
        and isinstance(dentro.func, ast.Name)
        and dentro.func.id == "janela_proibida_na_tela"
    )
    linha_da_janela = fonte[: fonte.index("self.janela = Gtk.Window(")].count("\n") + 1
    assert linha_da_trava < linha_da_janela, (
        "a trava é consultada DEPOIS de a janela na tela já ter sido "
        "construída — nesse ponto ela não impede nada"
    )


# ---------------------------------------------------------------------------
# 3 — a trava não sequestra a janela do produto
# ---------------------------------------------------------------------------
def test_sem_a_variavel_o_produto_abre_como_sempre() -> None:
    """MORDE: uma trava que vale SEMPRE tira a janela de quem usa o produto.

    O defeito que ela cura é de quem TRABALHA na máquina dela, não de quem joga.
    Se esta régua cair, alguém trocou `if not oculta and proibida()` por algo
    que decide sozinho — e o lançador dela passa a abrir uma janela invisível.
    """
    fonte = (
        _RAIZ / "src/hefesto_dualsense4unix/gui/ponte_da_tela.py"
    ).read_text(encoding="utf-8")

    assert "if not oculta and janela_proibida_na_tela():" in fonte, (
        "a guarda deixou de exigir as DUAS condições. Sem o `not oculta` ela "
        "reescreve o pedido de quem já pediu oculta (inofensivo); sem a "
        "variável, ela cala a janela do produto (que é o oposto da cura)"
    )


# ---------------------------------------------------------------------------
# 4 — o visor que é visível de propósito recusa dizendo
# ---------------------------------------------------------------------------
def test_o_visor_recusa_em_vez_de_abrir_escondido() -> None:
    """`ver.py` existe para ela OLHAR. Escondê-lo devolveria sucesso que mente.

    Chama o `main()` do visor num subprocesso, com a variável no ar, e cobra a
    recusa. Não abre janela: a recusa acontece antes de qualquer `Gtk.Window`.

    POR QUE CHAMAR `main()` EM VEZ DE EXECUTAR O ARQUIVO, e o achado é de
    02/09/2026: **`ver.py` não tem guarda de `__main__`.** Executá-lo direto —
    que é o que o próprio docstring dele ensina, `ver.py 08` — importa o módulo,
    define as funções e sai com 0 sem abrir nada. O script está morto desde
    algum ponto e ninguém notou, porque quem queria olhar usava o piloto.

    Isso é defeito à parte e NÃO foi curado aqui: acrescentar a guarda faria o
    visor voltar a abrir janela, e essa é decisão dela, não consequência de uma
    régua. O que esta régua garante é que, no dia em que a guarda voltar, a
    trava já esteja de pé.
    """
    import os

    ambiente = dict(os.environ)
    ambiente["HEFESTO_SEM_JANELA"] = "1"
    ambiente["PYTHONPATH"] = str(_RAIZ / "src")

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys;"
            "from hefesto_dualsense4unix.interface import ver;"
            "sys.exit(ver.main())",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=ambiente,
    )

    assert proc.returncode == 2, (
        "o visor NÃO recusou com a variável no ar — ele abriu (ou morreu por "
        f"outro motivo). Saída: {proc.stderr[-400:]!r}"
    )
    assert "HEFESTO_SEM_JANELA" in proc.stderr, (
        "recusou calado, ou pela razão errada. Recusar DIZENDO é regra desta "
        "casa, e aqui a frase precisa ensinar o caminho do `--oculta --foto`"
    )
    assert "--oculta" in proc.stderr, (
        "a recusa não diz COMO olhar sem aparecer. Uma recusa que não ensina o "
        "caminho certo empurra a próxima pessoa a contornar a trava"
    )


# ---------------------------------------------------------------------------
# 5 — nenhum teste abre janela só por ser COLETADO
# ---------------------------------------------------------------------------
def _mostra_janela_no_corpo(arquivo: pathlib.Path) -> list[str]:
    """Chamadas de `show_all`/`show`/`present` no CORPO do módulo.

    O corpo é o que roda na IMPORTAÇÃO, e o pytest importa todo arquivo de
    teste só para COLETAR. Uma janela criada ali aparece antes de qualquer
    teste rodar — inclusive quando a seleção do `-k` não ia rodar nenhum.

    Dentro de função não conta: ali o teste decide, e as fixtures da casa já
    sabem desviar o display.
    """
    try:
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    # SÓ o corpo do módulo. Pular `def`/`class` é o ponto inteiro: dentro deles
    # o teste decide quando abrir, e as fixtures da casa já desviam o display.
    #
    # NOTA DE QUEM ESCREVEU, porque o erro foi meu e é fácil repetir: a primeira
    # versão fazia `ast.walk(no)` sobre cada nó do corpo — e `walk` DESCE nas
    # funções. Ela acusou 90 arquivos que estão certos. `walk` sobre um `body`
    # não é "só o corpo"; é o arquivo inteiro por outro caminho.
    corpo = [
        no
        for no in arvore.body
        if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    achados: list[str] = []
    for no in corpo:
        for dentro in ast.walk(no):
            if not isinstance(dentro, ast.Call):
                continue
            f = dentro.func
            if not isinstance(f, ast.Attribute):
                continue
            if f.attr in {"show_all", "show", "present"}:
                achados.append(f"{arquivo.name}:{dentro.lineno} .{f.attr}()")
    return achados


def test_nenhum_teste_mostra_janela_na_importacao() -> None:
    """MORDE a classe inteira, sem abrir nada e sem depender de quem roda.

    Esta é a régua que teria evitado a foto de 02/09: ela lê o fonte de todos os
    testes e reprova quem manda mostrar janela no corpo do módulo.

    Os dois arquivos que EXERCITAM fechar janela (`test_dialogo_nao_mata_a_
    janela` e `test_socorro_ao_fechar_...`) montam o cenário dentro de uma
    STRING que só roda em subprocesso sob `xvfb-run`, com `GDK_BACKEND=x11` e
    sem `WAYLAND_DISPLAY` — por isso o `ast` não os vê aqui, e por isso eles
    estão certos. Se alguém tirar o `xvfb-run`, é o `test_o_cenario_de_janela_
    roda_isolado` abaixo que reprova.
    """
    culpados: list[str] = []
    for arquivo in sorted(_TESTES.rglob("test_*.py")):
        culpados.extend(_mostra_janela_no_corpo(arquivo))

    assert not culpados, (
        "estes testes mandam MOSTRAR janela no corpo do módulo, e o pytest "
        "importa todo arquivo só para coletar — a janela aparece na tela dela "
        f"antes de um teste sequer rodar: {culpados}. "
        "Mova para dentro de uma função, ou use `Gtk.OffscreenWindow`."
    )


def test_o_cenario_de_janela_roda_isolado() -> None:
    """Quem PRECISA de janela de verdade roda em display próprio.

    Os dois testes de fechamento montam uma `Gtk.Window` com `show_all()` para
    exercitar o `delete-event` — isso é legítimo e não dá para fazer offscreen.
    O que os torna seguros é o isolamento, e é ele que esta régua guarda.
    """
    for nome in (
        "test_dialogo_nao_mata_a_janela.py",
        "test_socorro_ao_fechar_diz_por_que_a_janela_nao_fecha.py",
    ):
        arquivo = _TESTES / "unit" / nome
        if not arquivo.exists():
            continue
        fonte = arquivo.read_text(encoding="utf-8")
        assert '"xvfb-run"' in fonte, (
            f"{nome} abre janela de verdade e deixou de rodar sob `xvfb-run` — "
            "sem display próprio ela nasce NA TELA DELA"
        )
        assert 'ambiente.pop("WAYLAND_DISPLAY", None)' in fonte, (
            f"{nome} deixou de remover o WAYLAND_DISPLAY do subprocesso: com "
            "ele no ambiente o GTK fala com o compositor dela, e o `xvfb-run` "
            "vira enfeite"
        )
