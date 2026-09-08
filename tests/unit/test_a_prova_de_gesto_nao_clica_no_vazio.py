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
            return ast.literal_eval(no.value)  # type: ignore[no-any-return]
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
    """MORDIDA 2: os DOIS botões de mudo continuam no roteiro.

    O defeito de origem (29/08) foi o contrário deste: a prova nunca clicava o
    🎙 nem o ♪ e dava verde sobre dois botões mortos. Tirar um deles do roteiro
    para fazer a régua de cima passar seria trocar um defeito pelo outro — e
    esta régua é o que impede a cura preguiçosa.
    """
    seletores = [s for _ms, s in _roteiro()]
    for botao in ('[data-mudo="microfone"]', '[data-mudo="alto-falante"]'):
        assert any(botao in s for s in seletores), (
            f"o roteiro deixou de clicar {botao} — é o defeito de 29/08 "
            f"voltando: {seletores}"
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
