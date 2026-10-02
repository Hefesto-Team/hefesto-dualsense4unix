"""A lista suspensa com os jogos DESTA máquina — PERFIL-MODO-01, Passo 3."""
from __future__ import annotations

import re
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations.jogos_locais import JogoLocal
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import a10_perfis

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo

CATALOGO = [
    JogoLocal(appid="851100", nome="Sea of Stars", fonte="steam"),
    JogoLocal(appid="1245620", nome="ELDEN RING", fonte="steam"),
    JogoLocal(appid="999001", nome='A & B <b>"C"</b>', fonte="desktop"),
]


@pytest.fixture(autouse=True)
def _catalogo(monkeypatch: pytest.MonkeyPatch) -> None:
    """A biblioteca DELA nunca é lida por uma régua."""
    from hefesto_dualsense4unix.integrations import jogos_locais

    monkeypatch.setattr(
        a10_perfis, "_nomes_dos_jogos",
        lambda: {j.appid: j.nome for j in CATALOGO})
    monkeypatch.setattr(jogos_locais, "jogos_de_janela", lambda *a, **k: [])


def test_o_campo_do_jogo_consulta_a_lista_e_continua_livre() -> None:
    """As duas metades, e cada uma sozinha não faz nada."""
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
    assert '<option value="851100" label="Sea of Stars · 851100">' in html
    assert '<option value="1245620" label="ELDEN RING · 1245620">' in html
    assert html.index("1245620") < html.index("851100"), (
        "a lista saiu na ordem do appid — ela procura pelo NOME do jogo")


def test_o_nome_do_jogo_dela_nunca_vira_marcacao() -> None:
    """`perfis_web` inteiro existe por causa disto: o Python manda DADO."""
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
        assert por_appid[jogo.appid] == f"{jogo.nome} · {jogo.appid}", (
            f"o rótulo de `{jogo.appid}` chegou cortado: "
            f"{por_appid[jogo.appid]!r}")


def test_o_bloco_da_lista_sai_no_pacote() -> None:
    """E ele chega à página pelo `blocos`, com o seletor do `<datalist>`."""
    assert a10_perfis.SELETOR_DOS_JOGOS == \
        'datalist[data-hef="editor.jogo.lista"]'
    html = onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")
    assert 'data-hef="editor.jogo.lista"' in html, (
        "o seletor do `blocos` aponta para um endereço que a bancada não tem — "
        "o `document.querySelector` não acha, e a lista some sem erro")


def test_com_a_biblioteca_vazia_a_lista_fica_vazia_e_o_campo_segue_livre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem Steam, sem `.acf`, sem permissão: a lista é vazia e nada quebra."""
    monkeypatch.setattr(a10_perfis, "_nomes_dos_jogos", dict)
    assert a10_perfis._html_dos_jogos() == ""


def test_a_leitura_da_biblioteca_nunca_derruba_a_aba(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isto é PINTURA, duas vezes por segundo, sobre o disco dela."""
    def _explode() -> dict[str, str]:
        raise OSError("um `.desktop` ilegível")

    monkeypatch.setattr(a10_perfis, "_nomes_dos_jogos", _explode)
    assert a10_perfis._html_dos_jogos() == ""


def test_a_lista_tem_teto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Teto de segurança, e não de gosto — ver `TETO_DA_LISTA_DE_JOGOS`."""
    enorme = {str(n): f"Jogo {n:05d}" for n in range(a10_perfis.TETO_DA_LISTA_DE_JOGOS + 50)}
    monkeypatch.setattr(a10_perfis, "_nomes_dos_jogos", lambda: enorme)
    html = a10_perfis._html_dos_jogos()
    assert html.count("<option") == a10_perfis.TETO_DA_LISTA_DE_JOGOS, (
        "a lista passou do teto — e quem tem mais jogos que o teto continua "
        "com o campo LIVRE, que é o que ele sempre foi")


def test_o_teto_e_folgado_para_a_maquina_dela() -> None:
    """Um teto apertado seria a lista RECUSANDO o que ela tem."""
    assert a10_perfis.TETO_DA_LISTA_DE_JOGOS >= 500
