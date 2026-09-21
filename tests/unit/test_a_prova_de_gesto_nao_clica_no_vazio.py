"""A `--prova-gesto` não pode clicar num botão que não existe mais.

O ACHADO, medido em 08/09/2026: dois dos sete passos do roteiro clicavam
``[data-mudo="mic-liberar"]`` — botão que ela mandou tirar em 30/08 e que
aparece **zero vez** na página publicada e no
``mockup/``. ``querySelector`` devolve ``null``, o ``.click()`` levanta
``TypeError`` dentro do WebKit, e ``_js`` não lê retorno nem erro. **Dois dos
sete passos batiam em nada e ninguém ficava sabendo, durante nove dias** — e
esta é a régua que a casa usa para dizer que os botões de mudo estão clicados.

É a mesma família que o próprio arquivo já nomeia, ao contrário: lá a régua
NÃO COBRIA um botão que existe (o ♪, até 29/08); aqui ela COBRIA um botão que
não existe mais. Nos dois casos o sintoma é idêntico — verde sobre nada.

**ESTA RÉGUA NÃO ABRE JANELA NENHUMA.** Ela lê o roteiro por AST e a página por
texto. Abrir a janela para conferir seria pôr um `Gtk.Window` na sessão viva
dela (TELA-DELA-01/02) e, pior, CLICAR nos controles que ela está usando.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "controles_vivos.py"
#: A página que o `WebKit2.WebView` do produto lê.
PAGINAS = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas"  # (noqa-acento) pasta
PUBLICADO = PAGINAS / "02-controles.html"
BANCADA = RAIZ / "mockup" / "02-controles.html"


def _roteiro() -> tuple[tuple[int, str], ...]:
    """O roteiro lido do fonte por AST — sem importar `gi`, sem abrir janela.

    Importar o módulo puxaria GTK e WebKit2; é a mesma razão pela qual
    `check_a_tela_nao_confessa` lê as falas por AST.
    """
    arvore = ast.parse(FONTE.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.AnnAssign)
            and isinstance(no.target, ast.Name)
            and no.target.id == "ROTEIRO_DA_PROVA_DE_GESTO"
            and no.value is not None
        ):
            # NORMALIZA PARA `(ms, seletor)`. Desde 20/09 um passo pode trazer
            # um TERCEIRO item — `"so-existe"`, o passo que confere o alvo sem
            # puxar o gatilho, porque o 🎙 deixou de calar e passou a GRAVAR o
            # microfone de quem estiver na frente da máquina. A régua mede a
            # mesma coisa nos dois: *o alvo existe na página*.
            passos = ast.literal_eval(no.value)
            return tuple((p[0], p[1]) for p in passos)
    raise AssertionError(
        "o `ROTEIRO_DA_PROVA_DE_GESTO` sumiu do fonte — se ele voltou a ser uma "
        "lista embutida no meio do método, esta régua deixou de alcançá-lo, e "
        "com ela o portão que impede a prova de clicar no vazio"
    )


def _alvos_do_seletor(seletor: str) -> list[str]:
    """Os pedaços do seletor que TÊM de aparecer na página, um a um.

    Um seletor composto (``.rota button[data-rota="pc"]``) casa por partes: a
    classe, e cada par ``[chave="valor"]``. Conferir a string inteira contra o
    HTML não funcionaria — no HTML os atributos vêm em outra ordem, e com
    outros no meio.
    """
    partes: list[str] = []
    for atributo, valor in re.findall(r'\[([\w-]+)="([^"]*)"\]', seletor):
        partes.append(f'{atributo}="{valor}"')
    for classe in re.findall(r"\.([\w-]+)", seletor):
        partes.append(f"{classe}")
    return partes


@pytest.mark.parametrize("alvo", [PUBLICADO, BANCADA], ids=["publicado", "mockup"])
def test_todo_passo_do_roteiro_acha_alvo_na_tela(alvo: Path) -> None:
    """MORDIDA 1: cada seletor do roteiro existe na página. Nos DOIS lugares.

    **O PUBLICADO É O QUE DECIDE**, porque é o que o `WebKit2.WebView` do
    produto lê — curar o mockup não cura o produto. O mockup entra junto porque
    um seletor vivo só ali seria a mesma mentira, adiada até a publicação.

    ARRANQUE A CURA (ponha `[data-mudo="mic-liberar"]` de volta no
    `ROTEIRO_DA_PROVA_DE_GESTO`) e esta régua REPROVA dizendo o alvo e a
    página — o que ninguém disse durante nove dias.
    """
    html = alvo.read_text(encoding="utf-8")
    mortos: list[str] = []
    for _ms, seletor in _roteiro():
        for pedaco in _alvos_do_seletor(seletor):
            if pedaco not in html:
                mortos.append(f"{seletor}  (falta {pedaco!r})")
    assert not mortos, (
        f"a `--prova-gesto` clica em alvo que não existe em {alvo.name}:\n  "
        + "\n  ".join(mortos)
        + "\n\nUm passo que bate em `null` levanta dentro do WebKit e o `_js` "
        "não lê o erro: a prova dá VERDE sobre um botão morto."
    )


def test_o_roteiro_cobre_o_microfone_e_o_alto_falante() -> None:
    """MORDIDA 2: os DOIS botões da coluna do som continuam no roteiro.

    O defeito de origem (29/08) foi o contrário deste: a prova nunca clicava o
    🎙 nem o ♪ e dava verde sobre dois botões mortos. Tirar um deles do roteiro
    para fazer a régua de cima passar seria trocar um defeito pelo outro — e
    esta régua é o que impede a cura preguiçosa.

    **O ENDEREÇO DO 🎙 MUDOU EM 20/09 E O ALVO NÃO AFROUXOU.** Ele deixou de
    calar (`data-mudo="microfone"`) e passou a testar (`data-gesto="mic-testar"`)
    por ordem dela — *"esse botão segue desativando o microfone, não precisamos
    dele mais na interface pq o botão do próprio controle já o faz"*. O que
    esta régua cobra continua sendo o mesmo: que o roteiro VISITE os dois
    botões da coluna. Deixar o seletor velho aqui faria a régua vigiar um
    elemento que não existe mais — e uma régua que procura o que não há
    reprova para sempre, ou, pior, é apagada por incômodo.
    """
    seletores = [s for _ms, s in _roteiro()]
    for botao in ('[data-gesto="mic-retorno"]', '[data-mudo="alto-falante"]'):
        assert any(botao in s for s in seletores), (
            f"o roteiro deixou de clicar {botao} — é o defeito de 29/08 "
            f"voltando: {seletores}"
        )


def test_todo_botao_de_rota_tem_dono_na_tabela() -> None:
    """MORDIDA 4: a tabela de donos não pode ficar para trás da fileira.

    MEDIDO em 21/09/2026, rodando `--prova-gesto` na máquina dela: dos três
    botões do alto-falante, DOIS voltavam com *"SEM LINHA na tabela de donos —
    este gesto chegou de um endereço que o gerador não escreve. Nada foi
    aplicado."* A tabela conhecia `rota:jogo` e `rota:pc`, e o `pc` tinha saído
    da fileira no dia anterior, quando ela trocou o ato do terceiro botão.

    **E os dois tinham dono**: `pacotes/a02_controles.py` registra
    `@gesto("02-controles.html", "rota")` e aceita `jogo`, `junto`, `nada` e
    `pc`. O instrumento é que estava velho.

    POR QUE ISSO PRECISA DE RÉGUA, e não de atenção: a pergunta que a
    `--prova-gesto` existe para responder é *"este botão funciona?"*, e a
    queixa dela de 20/09 foi exatamente essa — *"os 3 botões do auto falante
    (…) não estão funcionando"*. Uma tabela de donos desatualizada faz a régua
    ACUSAR O PRODUTO de não fazer o que ele faz. Instrumento que erra a favor
    do alarme custa uma investigação inteira.

    A régua lê a PÁGINA (quais rotas existem) e o FONTE (quais têm dono), e
    nunca uma lista digitada aqui — digitar seria medir a própria saída.
    """
    fonte = FONTE.read_text(encoding="utf-8")
    inicio = fonte.index("DONOS_DOS_GESTOS = {")
    tabela = fonte[inicio : fonte.index("\n}\n", inicio)]
    declarados = set(re.findall(r'"rota:([a-z]+)"', tabela))
    for alvo in (PUBLICADO, BANCADA):
        if not alvo.is_file():
            continue
        na_pagina = set(re.findall(r'data-rota="([a-z]+)"', alvo.read_text(encoding="utf-8")))
        assert na_pagina, f"{alvo.name} não tem botão de rota nenhum — a fileira sumiu?"
        sem_dono = sorted(na_pagina - declarados)
        assert not sem_dono, (
            f"{alvo.name} tem botão de rota sem linha em `DONOS_DOS_GESTOS`: "
            f"{sem_dono}. A `--prova-gesto` vai dizer «nada foi aplicado» sobre "
            f"um botão que tem dono em `pacotes/a02_controles.rota`, e quem ler "
            f"o relatório vai concluir que o produto está quebrado."
        )


def test_o_passo_confessa_quando_nao_acha_o_alvo() -> None:
    """MORDIDA 3: o clique sintético reporta `achou`, em vez de estourar calado.

    O portão de cima pega o alvo que morreu no HTML. Este pega o caso que ele
    NÃO alcança: a página que existe no disco mas não está pintada na hora do
    clique (mesa vazia, card ainda não montado). O `_js` não lê retorno nem
    erro — sem o recado de volta, o passo some.

    ARRANQUE A CURA (volte o `.click()` cru) e esta régua REPROVA.
    """
    fonte = FONTE.read_text(encoding="utf-8")
    assert "def _clique_que_confessa(" in fonte
    arvore = ast.parse(fonte)
    corpo = next(
        (n for n in ast.walk(arvore)
         if isinstance(n, ast.FunctionDef) and n.name == "_clique_que_confessa"),
        None,
    )
    assert corpo is not None
    texto = ast.get_source_segment(fonte, corpo) or ""
    assert "postMessage" in texto, (
        "o clique sintético não manda nada de volta — um alvo ausente volta a "
        "sumir sem uma linha vermelha"
    )
    assert "achou" in texto, "o recado não diz SE o alvo foi achado"
    assert "if(e){e.click();}" in texto, (
        "o clique deixou de ser condicional: com o alvo ausente ele volta a "
        "levantar `TypeError` dentro do WebKit, calado"
    )


def test_o_relato_final_mostra_os_alvos_mortos() -> None:
    """MORDIDA 4: o número aparece no relato, senão ninguém o lê.

    *Aviso no cabeçalho de um comando que termina verde ninguém lê* — a regra
    de 04/09. O contador só vale se sair no relato do fim, junto dos outros.
    """
    fonte = FONTE.read_text(encoding="utf-8")
    assert "alvos_mortos_do_roteiro" in fonte
    assert "ALVOS MORTOS" in fonte, (
        "o relato final não nomeia os alvos mortos — o contador existe e "
        "ninguém o vê"
    )
