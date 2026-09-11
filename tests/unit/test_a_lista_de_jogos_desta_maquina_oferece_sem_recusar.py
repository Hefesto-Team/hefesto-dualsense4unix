"""A lista suspensa com os jogos DESTA máquina — PERFIL-MODO-01, Passo 3.

A linha 378 do CSV da paridade, `FALTA_NO_HTML`, e a nota que diz o custo:

    *"JOGO-QUE-SE-DIZ-01 existe porque o campo pedia o número cru — o único
    dado que ninguém tem em mãos. Sem a completação, criar um perfil de jogo
    pelo HTML exige ela saber o appid de cor ou ir buscá-lo na loja. O botão
    «Detectar» cobre metade disso (só com o jogo em foco, e só da Steam); a
    completação cobre o resto, inclusive jogo fechado."*

O ENUNCIADO DA SPRINT É A REGRA DESTA RÉGUA, e as duas metades são igualmente
duras: *"o campo deixa de ser texto livre e passa a **oferecer** o que existe na
máquina — continuando a **aceitar** o que ela digitar: uma lista que recusa o
que ela sabe que existe é pior que campo livre."*

Por isso o desenho usa `<datalist>` e não `<select>`: o primeiro OFERECE, o
segundo FECHA.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations.jogos_locais import JogoLocal
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import a10_perfis

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

#: TRÊS JOGOS DE MENTIRA, e o terceiro é o que a régua existe para pegar: um
#: nome com `&`, `<` e aspas. Eles vêm dos `.acf` e dos `.desktop` DELA, e
#: `DON'T SCREAM` já está no catálogo desta casa.
CATALOGO = [
    JogoLocal(appid="851100", nome="Sea of Stars", fonte="steam"),
    JogoLocal(appid="1245620", nome="ELDEN RING", fonte="steam"),
    JogoLocal(appid="999001", nome='A & B <b>"C"</b>', fonte="desktop"),
]


@pytest.fixture(autouse=True)
def _catalogo(monkeypatch: pytest.MonkeyPatch) -> None:
    """A biblioteca DELA nunca é lida por uma régua.

    **E AS ORIGENS PASSARAM A SER DUAS — 11/09/2026, JOGOS-DOS-LANCADORES-01.**
    Calar só a da Steam deixou o `<datalist>` lendo o Heroic, o Lutris e os 221
    `.desktop` da máquina de quem roda a régua: nesta bancada o
    ``test_com_a_biblioteca_vazia…`` reprovou com três emuladores DELA na
    lista, e no CI teria passado — a mesma linha com dois resultados conforme
    a máquina. A segunda origem entra VAZIA, e quem precisa dela a enche.
    """
    from hefesto_dualsense4unix.integrations import jogos_locais

    monkeypatch.setattr(
        a10_perfis, "_nomes_dos_jogos",
        lambda: {j.appid: j.nome for j in CATALOGO})
    monkeypatch.setattr(jogos_locais, "jogos_de_janela", lambda *a, **k: [])


# --------------------------------------------------------------------------
# 1. O DESENHO OFERECE — e o campo continua ACEITANDO
# --------------------------------------------------------------------------

def test_o_campo_do_jogo_consulta_a_lista_e_continua_livre() -> None:
    """As duas metades, e cada uma sozinha não faz nada.

    MORDIDA: tire o `list="jogos-desta-maquina"` do `<input>` em `aba10.py` e a
    primeira asserção reprova — a lista fica no HTML e ninguém a consulta, que é
    o silêncio que esta casa lê como sucesso.
    """
    html = onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")
    campo = re.search(r'<input[^>]*data-hef="editor\.jogo"[^>]*>', html)
    assert campo is not None, "o campo do jogo sumiu do editor"
    assert 'list="jogos-desta-maquina"' in campo.group(0), (
        "o campo do jogo não consulta a lista — o `<datalist>` existe e "
        "ninguém o lê")
    assert 'type="text"' in campo.group(0), (
        "o campo do jogo deixou de ser texto livre — uma lista que RECUSA o que "
        "ela sabe que existe é pior que campo livre (o enunciado é dela)")
    assert '<datalist id="jogos-desta-maquina"' in html
    assert '<datalist id="jogos-desta-maquina" data-hef="editor.jogo.lista">' \
           '</datalist>' in html, (
        "a lista não nasce VAZIA no desenho — um exemplo cravado aqui é a tela "
        "afirmando um jogo que ela talvez não tenha")


# --------------------------------------------------------------------------
# 2. O PACOTE ENCHE A LISTA — com o appid no `value`, que é o que o campo grava
# --------------------------------------------------------------------------

def test_a_lista_traz_o_appid_no_value_e_o_nome_no_rotulo() -> None:
    """A MESMA divisão das duas colunas do `Gtk.EntryCompletion` da janela GTK.

    *"Coluna 0 = o rótulo que ela lê, Coluna 1 = o appid, que é o que o campo
    grava"* — e o comentário de lá diz o preço de trocar: o perfil nasceria com
    um `steam_app_Sea of Stars`, que nunca casa com janela nenhuma.

    MORDIDA: troque `value="{appid}"` por `value="{nome}"` em
    `a10_perfis._html_dos_jogos` e isto reprova — escolher um jogo passaria a
    escrever o NOME no campo, e `from_simple_choice("steam_game", …)` quer o
    número.
    """
    html = a10_perfis._html_dos_jogos()
    assert '<option value="851100" label="Sea of Stars (appid 851100)">' in html
    assert '<option value="1245620" label="ELDEN RING (appid 1245620)">' in html
    # A ORDEM É ALFABÉTICA pelo NOME, que é o que ela procura — não pelo appid.
    assert html.index("1245620") < html.index("851100"), (
        "a lista saiu na ordem do appid — ela procura pelo NOME do jogo")


def test_o_nome_do_jogo_dela_nunca_vira_marcacao() -> None:
    """`perfis_web` inteiro existe por causa disto: o Python manda DADO.

    Os nomes vêm dos `.acf` e dos `.desktop` DELA — texto que ninguém desta casa
    controla. Um `"` no meio de um nome fecharia o `label=` e o resto viraria
    marcação no `<datalist>`.

    A RÉGUA É UM PARSER, e não um `in` de string: o `_atr` escapa **menos** que
    o `html.escape` de propósito (a medição está na docstring dele — escapar o
    que o serializador do navegador não escapa faz o `blocos` reescrever o bloco
    a cada 500 ms para sempre), então procurar `&lt;` aqui reprovaria a cura
    certa. O que importa é o que o NAVEGADOR lê de volta: o nome inteiro, dentro
    do atributo, sem um elemento a mais no documento.

    MORDIDA (colhida em 06/09/2026): troque o `_atr(...)` por `str(...)` em
    `_html_dos_jogos` e isto reprova — o `"` do nome fecha o `label=`, o parser
    devolve `A & B <b>` como rótulo e um `<b>` extra aparece na árvore.
    """
    from html.parser import HTMLParser

    class Leitor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.opcoes: list[dict[str, str]] = []
            self.outros: list[str] = []

        def handle_starttag(self, tag: str, attrs: Any) -> None:
            if tag == "option":
                self.opcoes.append({k: (v or "") for k, v in attrs})
            else:
                self.outros.append(tag)

    leitor = Leitor()
    leitor.feed(a10_perfis._html_dos_jogos())
    assert not leitor.outros, (
        f"o nome de um jogo dela virou {leitor.outros} no `<datalist>` — o "
        f"atributo foi fechado por um caractere que veio do disco")
    por_appid = {o["value"]: o["label"] for o in leitor.opcoes}
    for jogo in CATALOGO:
        assert por_appid[jogo.appid] == f"{jogo.nome} (appid {jogo.appid})", (
            f"o rótulo de `{jogo.appid}` chegou cortado: "
            f"{por_appid[jogo.appid]!r}")


def test_o_bloco_da_lista_sai_no_pacote() -> None:
    """E ele chega à página pelo `blocos`, com o seletor do `<datalist>`.

    MORDIDA: tire o `SELETOR_DOS_JOGOS` do `fora["blocos"]` de `pacote()` e
    isto reprova — a lista continuaria montada em Python e nunca chegaria ao
    DOM, que é a forma clássica do órfão calado.
    """
    assert a10_perfis.SELETOR_DOS_JOGOS == \
        'datalist[data-hef="editor.jogo.lista"]'
    html = onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")
    assert 'data-hef="editor.jogo.lista"' in html, (
        "o seletor do `blocos` aponta para um endereço que a bancada não tem — "
        "o `document.querySelector` não acha, e a lista some sem erro")


# --------------------------------------------------------------------------
# 3. AS DUAS BORDAS — biblioteca vazia e biblioteca enorme
# --------------------------------------------------------------------------

def test_com_a_biblioteca_vazia_a_lista_fica_vazia_e_o_campo_segue_livre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem Steam, sem `.acf`, sem permissão: a lista é vazia e nada quebra.

    É o contrato que a janela GTK já declara — *"degradar em silêncio é
    requisito"* — e é a metade do enunciado dela que diz "continuando a aceitar
    o que ela digitar".
    """
    monkeypatch.setattr(a10_perfis, "_nomes_dos_jogos", dict)
    assert a10_perfis._html_dos_jogos() == ""


def test_a_leitura_da_biblioteca_nunca_derruba_a_aba(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isto é PINTURA, duas vezes por segundo, sobre o disco dela.

    MORDIDA: tire o `try/except` de `_html_dos_jogos` e isto reprova com o
    `OSError` subindo — que na janela viva é a aba inteira parando de pintar
    por causa de um `.desktop` estragado.
    """
    def _explode() -> dict[str, str]:
        raise OSError("um `.desktop` ilegível")

    monkeypatch.setattr(a10_perfis, "_nomes_dos_jogos", _explode)
    assert a10_perfis._html_dos_jogos() == ""


def test_a_lista_tem_teto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Teto de segurança, e não de gosto — ver `TETO_DA_LISTA_DE_JOGOS`.

    O `blocos` compara o `innerHTML` a cada tique; um catálogo de milhares de
    linhas passaria por essa comparação dez vezes por segundo.
    """
    enorme = {str(n): f"Jogo {n:05d}" for n in range(a10_perfis.TETO_DA_LISTA_DE_JOGOS + 50)}
    monkeypatch.setattr(a10_perfis, "_nomes_dos_jogos", lambda: enorme)
    html = a10_perfis._html_dos_jogos()
    assert html.count("<option") == a10_perfis.TETO_DA_LISTA_DE_JOGOS, (
        "a lista passou do teto — e quem tem mais jogos que o teto continua "
        "com o campo LIVRE, que é o que ele sempre foi")


def test_o_teto_e_folgado_para_a_maquina_dela() -> None:
    """Um teto apertado seria a lista RECUSANDO o que ela tem.

    O catálogo desta máquina em 06/09/2026: 33 `.acf` mais 150 `.desktop`.
    """
    assert a10_perfis.TETO_DA_LISTA_DE_JOGOS >= 500
