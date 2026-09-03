#!/usr/bin/env python3
"""O LUGAR SEM CONTROLE NÃO VESTE O APARELHO DO MOCKUP — aba 06.

O DEFEITO, MEDIDO NO PRODUTO INSTALADO em 03/09/2026, com UM DualSense White no
cabo e a aba Navegação aberta no `WebKit2.WebView` (janela oculta). Os quatro
cartões, lidos do DOM VIVO por `getComputedStyle`::

    P1 • White         casco rgb(68, 71, 90)     lightbar rgb(0, 0, 255)
    P2 • —             casco rgb(126, 184, 212)  lightbar rgb(255, 0, 0)
    P3 • Desconectado  casco rgb(83, 87, 111)    lightbar rgb(83, 87, 111)
    P4 • Desconectado  casco rgb(83, 87, 111)    lightbar rgb(83, 87, 111)

`rgb(126, 184, 212)` é `#7eb8d4` — o **Starlight Blue do mockup** — e
`rgb(255, 0, 0)` é o `style="--luz:#ff0000"` que o `monta.svg()` cravou no
`<g id="p2-lightbar">` do desenho. O cartão do P2 estava VAZIO (o rótulo dizia
`P2 • —` e o `data-conectado` dizia `nao`) e era o  (noqa-acento: atributo)
 mais colorido e o
mais aceso da fileira: mais chamativo que o do único controle de verdade na
mesa. É a oitava aparição do defeito que esta casa já nomeou — *a tela
afirmando um controle que não está na mesa*.

POR QUE O P3 E O P4 ESCAPARAM, e é o que nomeia a causa: eles nascem
`class="nav-ctl vazia"` no HTML, e a folha do desenho **já sabe** desenhar um
lugar vazio. O P2 nasce OCUPADO e fica vazio em tempo de execução; quem o
esvazia escreve a classe `off`, que folha de estilo nenhuma menciona. Duas
palavras para o mesmo estado, e elas nunca se encontraram.

A CURA está em `a06_navegacao._apagar_os_lugares_sem_dono`: a folha viva do
plástico passa a emitir, para cada lugar do desenho que a mesa NÃO ocupa, o
mesmo neutro que o `.vazia` usa (`var(--linha)`) — nas zonas de identidade e na
`--luz`.

DEPOIS DA CURA, medido do mesmo jeito, na mesma máquina, no mesmo minuto::

    P2 • —             casco rgb(83, 87, 111)    lightbar rgb(83, 87, 111)

— idêntico ao P3 e ao P4, e o P1 intacto.

AS QUATRO MORDIDAS, e cada uma reprova um teste diferente:

* apague a chamada de `_apagar_os_lugares_sem_dono` em `folha_do_plastico`;
* troque o `var(--linha)` por um cinza digitado;
* tire o `!important` da regra da `--luz` (o valor chega em `style=` no próprio
  elemento, e estilo de linha vence folha que não o traga);
* faça a função emitir regra para um lugar que a mesa OCUPA — a cor do aparelho
  dela seria apagada pela regra seguinte.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import a06_navegacao as a06

PAGINA = "06-navegacao.html"
#: A CAIXA DA ABA 06. A 04 passa a sua (`.ctrl`) — o parâmetro existe para que
#: as duas leiam a MESMA função, e é por isso que os testes daqui o exercitam.
CAIXA = ".nav-ctl"


@pytest.fixture(scope="module")
def publicado() -> str:
    """A página que o produto RENDERIZA. É nela que o defeito aparece."""
    return onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")


def _regras(folha: str) -> dict[str, str]:
    """`{seletor: corpo}` — a folha viva partida em regras."""
    return {s.strip(): c for s, c in re.findall(r"([^{}]+)\{([^{}]*)\}", folha)}


# ---------------------------------------------------------------------------
# 1. O QUE A PÁGINA PUBLICADA REALMENTE TRAZ — o defeito não é hipótese
# ---------------------------------------------------------------------------

def test_o_desenho_crava_um_aparelho_no_lugar_do_p2(publicado: str) -> None:
    """Sem a cura não há o que apagar: o mockup crava o P2 vestido e aceso."""
    assert 'data-controle="p2"' in publicado, (
        "o cartão do P2 perdeu o `data-controle` — a folha viva não tem mais "
        "como endereçá-lo, e a cura inteira deixa de alcançar o lugar")
    assert 'id="p2-lightbar" style="--luz:#ff0000"' in publicado, (
        "o `--luz` cravado do P2 mudou de forma; a régua aferia o vermelho "
        "do mockup num lugar vazio e passou a medir outra coisa")
    # A ÂNCORA NÃO PODE EXIGIR A POSIÇÃO DO ATRIBUTO — corrigido em 03/09/2026,
    # e o defeito nasceu de um MERGE. Esta régua veio de uma frente que ancorava
    # em `<svg data-colorway="…"`; outra frente, no mesmo dia, endereçou o
    # desenho e inseriu três atributos ANTES dele
    # (`data-campo`, `data-hef-alvo`, `data-hef-atributo`). As duas verdes na
    # própria árvore, vermelhas juntas — o par de olhos que falta é sempre o do
    # merge. O que a régua quer saber é se o desenho do P2 CRAVA o Starlight
    # Blue, não em que ordem o gerador escreve os atributos.
    assert re.search(r'<svg [^>]*data-colorway="starlight-blue"[^>]*class="ds-svg"',
                     publicado), (
        "o `data-colorway` do desenho do P2 mudou — era o Starlight Blue do "
        "mockup, que é o que a cura existe para apagar")


def test_o_desenho_sabe_pintar_um_lugar_vazio(publicado: str) -> None:
    """O neutro NÃO é digitado na cura: é o que o `.vazia` do desenho já usa."""
    assert ".nav-ctl.vazia .ds-svg" in publicado, (
        "a folha do desenho não fala mais do lugar vazio — o `var(--linha)` da "
        "cura deixou de ter dono, e viraria a segunda verdade")
    assert re.search(r"--linha:\s*#", publicado), (
        "o `--linha` sumiu da página: a cura escreveria uma variável que não "
        "resolve, e o casco cairia nos `fill` crus do `ds_limpo.svg`")


# ---------------------------------------------------------------------------
# 2. A CURA — o que a folha viva passa a emitir
# ---------------------------------------------------------------------------

def test_o_lugar_sem_dono_ganha_o_neutro_do_desenho() -> None:
    """Com UM controle na mesa, os outros TRÊS lugares são apagados."""
    folha = a06.folha_do_plastico([{"pref": "p1", "cor": "white"}], CAIXA)
    regras = _regras(folha)
    for pref in ("p2", "p3", "p4"):
        alvo = f'{CAIXA}[data-controle="{pref}"] .ds-svg'
        assert alvo in regras, (
            f"o lugar vazio `{pref}` ficou sem regra — o desenho do mockup "
            f"continua vestido num lugar onde não há controle")
        assert "var(--linha)" in regras[alvo], (
            f"o neutro do `{pref}` não é o do desenho (`var(--linha)`)")
        assert "#" not in regras[alvo], (
            f"a regra do `{pref}` traz um hex digitado — a cor tem UM dono, e "
            f"é a folha do SVG")


def test_a_luz_do_lugar_sem_dono_apaga_com_important() -> None:
    """O `--luz` chega em `style=` no elemento; sem `!important` nada muda."""
    folha = a06.folha_do_plastico([{"pref": "p1", "cor": "white"}], CAIXA)
    regras = _regras(folha)
    alvo = f'{CAIXA}[data-controle="p2"] [id$="-lightbar"]'
    assert alvo in regras, (
        "a lightbar do lugar vazio ficou sem regra: o cartão do P2 volta a "
        "acender em `#ff0000` num lugar onde não há controle")
    assert "--luz" in regras[alvo] and "var(--linha)" in regras[alvo]
    assert "!important" in regras[alvo], (
        "sem o `!important` a regra perde para o `style=\"--luz:#ff0000\"` que "
        "o `monta.svg()` cravou no próprio elemento — a folha não muda nada")


def test_o_lugar_ocupado_nao_e_apagado() -> None:
    """Apagar um lugar COM dono mataria a cor do aparelho dela."""
    mesa = [{"pref": "p1", "cor": "white"}, {"pref": "p2", "cor": "cosmic-red"}]
    folha = a06.folha_do_plastico(mesa, CAIXA)
    regras = _regras(folha)
    for pref, hexa in (("p1", "#e4e0d8"), ("p2", "#ae335a")):
        alvo = f'{CAIXA}[data-controle="{pref}"] .ds-svg'
        assert hexa in regras[alvo].lower(), (
            f"o `{pref}` está na mesa e perdeu a cor do aparelho — a regra do "
            f"lugar vazio passou por cima do lugar ocupado")
        assert "var(--linha)" not in regras[alvo]
    assert f'{CAIXA}[data-controle="p2"] [id$="-lightbar"]' not in regras, (
        "o P2 está na mesa e mesmo assim teve a lightbar apagada")
    # os dois que sobram continuam apagados
    assert f'{CAIXA}[data-controle="p3"] .ds-svg' in regras


def test_a_mesa_vazia_apaga_os_quatro_lugares() -> None:
    """Sem controle nenhum, nenhum dos quatro lugares afirma um aparelho."""
    regras = _regras(a06.folha_do_plastico([], CAIXA))
    for pref in ("p1", "p2", "p3", "p4"):
        assert f'{CAIXA}[data-controle="{pref}"] .ds-svg' in regras
        assert f'{CAIXA}[data-controle="{pref}"] [id$="-lightbar"]' in regras


def test_a_caixa_da_aba_04_atravessa() -> None:
    """A 04 chama a MESMA função com a caixa dela. Duas cópias divergiriam."""
    folha = a06.folha_do_plastico([{"pref": "p1", "cor": "white"}], ".ctrl")
    assert '.ctrl[data-controle="p2"] .ds-svg' in _regras(folha)
    assert ".nav-ctl" not in folha


def test_o_seletor_vence_a_folha_de_dentro_do_svg() -> None:
    """(0,3,0) contra o (0,1,1) de `svg[data-colorway="…"]`, ou nada muda."""
    folha = a06.folha_do_plastico([{"pref": "p1", "cor": "white"}], CAIXA)
    escritos = [s for s in _regras(folha) if "p2" in s and "ds-svg" in s]
    assert len(escritos) == 1, "o lugar vazio ganhou mais de um seletor"
    alvo = escritos[0]
    assert (alvo.count("."), alvo.count("[")) == (2, 1), (
        f"o seletor do lugar vazio mudou de peso (`{alvo}`): ele precisa de "
        f"duas classes e um atributo para vencer o `svg[data-colorway=…]` "
        f"(0,1,1) que o `monta.svg()` embute no próprio SVG")
