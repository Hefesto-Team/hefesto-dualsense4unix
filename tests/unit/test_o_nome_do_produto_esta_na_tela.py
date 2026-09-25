"""O nome do produto está na tela das dez abas — O-NOME-DO-PRODUTO-NA-TELA-01.

**O pedido dela, 21/09/2026:** *"sumiu o Hefesto Dualsense4Linux (o 4 era verde
se não me engano) do banner. ao menos tinha no gtk em nenhum momento da tela
temos o nosso produto a disposição do user"*. <!-- noqa-acento: citação literal dela -->

**A escolha dela, 22/09/2026, sobre os mockups:** a opção A2 (o nome em duas
linhas ao lado da logo), com três ajustes:

1. *"o card dos controles ali do selecionar deixa em uma linha como os do B"* —
   o chip da fita não quebra de linha;
2. *"Esse x controles cai fora pra ganharmos espaçço Lateral"*  (noqa-acento: dela)
   — o cabeçalho diz só `x USB · y BT`, e `Nenhum controle` com a mesa vazia;
3. *"aumentar um pouco a fonte do Selecionar no banner tambem pq ele tá  (noqa-acento: dela)
   meio invisível"*.

A RÉGUA LÊ A PÁGINA PUBLICADA, que é o que o produto renderiza. O esqueleto das
dez é um só (`topo.html`), mas uma página que não foi regerada ou publicada
seria a cura que não chegou à tela.

AS MORDIDAS estão em cada docstring.
"""

from __future__ import annotations

import re

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import onde, pacotes

#: As dez abas, pelo nome do arquivo, da pasta que o produto renderiza.
ABAS = sorted(p.name for p in onde.paginas(publicado=True) if p.name[:2].isdigit())


def _pagina(nome: str) -> str:
    return onde.pagina(nome, publicado=True).read_text(encoding="utf-8")


def _linha_da_fita(doc: str) -> str:
    """O bloco `.fita-linha` do corpo — a marcação, não a folha de estilo."""
    i = doc.index('<div class="fita-linha">')
    return doc[i:doc.index('<div class="tira">', i)]


def test_sao_as_dez() -> None:
    """A parametrização abaixo não passa por vacuidade."""
    assert len(ABAS) == 10, ABAS


@pytest.mark.parametrize("arquivo", ABAS)
def test_o_nome_esta_ao_lado_da_logo_com_o_4_verde(arquivo: str) -> None:
    """Uma vez por aba, depois da logo e antes da fita, com o `4` à parte.

    A MORDIDA: tire o `marca-nome` do `topo.html`, regere e publique — as dez
    reprovam. Tire só o `<span class="m-4">` e a segunda asserção diz que o
    verde sumiu.
    """
    linha = _linha_da_fita(_pagina(arquivo))
    assert linha.count('class="marca-nome"') == 1, f"{arquivo}: o nome não está no banner"
    assert '<span class="m-hef">Hefesto</span>' in linha, arquivo
    assert 'DualSense<span class="m-4">4</span>Unix' in linha, (
        f"{arquivo}: o 4 de DualSense4Unix perdeu o elemento próprio — o verde sumiu")
    # `fita` como classe inteira: `fita-linha` contém a palavra, e sete abas
    # levam `fita inerte`.
    fita = re.search(r'<div class="fita[ "]', linha)
    assert fita, f"{arquivo}: a fita sumiu da linha"
    assert linha.index('class="logo"') < linha.index('class="marca-nome"') < fita.start(), (
        f"{arquivo}: o nome saiu do lugar do A2 (entre a logo e a fita)")


@pytest.mark.parametrize("arquivo", ABAS)
def test_as_cores_do_nome_sao_as_da_gtk(arquivo: str) -> None:
    """Rosa na marca e verde no `4`, por token — como o `app_wordmark` da GTK."""
    doc = _pagina(arquivo)
    assert re.search(r"\.marca-nome \.m-hef\{color:var\(--pink\)\}", doc), arquivo
    assert re.search(r"\.marca-nome \.m-4\{color:var\(--green\)\}", doc), arquivo


@pytest.mark.parametrize("arquivo", ABAS)
def test_o_chip_da_fita_nao_quebra_de_linha(arquivo: str) -> None:
    """Com quatro controles numa janela estreita o chip partia em duas linhas.

    A MORDIDA: tire o `white-space:nowrap` da regra `.fita .chip` do
    `topo.html` e esta régua reprova nas dez.
    """
    regra = re.search(r"\.fita \.chip\{[^}]*\}", _pagina(arquivo))
    assert regra and "white-space:nowrap" in regra.group(0), (
        f"{arquivo}: o chip da fita voltou a poder quebrar de linha")


@pytest.mark.parametrize("arquivo", ABAS)
def test_o_cabecalho_nao_diz_mais_n_controles(arquivo: str) -> None:
    """O `x USB · y BT` fica; o «N controles:» e o endereço dele saem."""
    linha = _linha_da_fita(_pagina(arquivo))
    conectado = re.search(r'<div class="conectado">.*?</div>', linha, re.S).group(0)
    assert "controles:" not in conectado and 'data-campo="conta"' not in conectado, (
        f"{arquivo}: o «N controles:» voltou — {conectado}")
    assert 'data-campo="conta-b"' in conectado, f"{arquivo}: a conta por transporte sumiu"


@pytest.mark.parametrize("arquivo", ABAS)
def test_o_selecionar_se_le(arquivo: str) -> None:
    """O rótulo passou dos 12 px na cor muda para 13,5 px no texto suave."""
    regra = re.search(r"\.fita > span:first-child\{([^}]*)\}", _pagina(arquivo))
    assert regra, f"{arquivo}: o rótulo «Selecionar:» perdeu a regra própria"
    tamanho = re.search(r"font-size:([\d.]+)px", regra.group(1))
    assert tamanho and float(tamanho.group(1)) > 12, (
        f"{arquivo}: o «Selecionar:» voltou ao tamanho em que ele sumia")


def test_o_pintor_nao_emite_mais_a_primeira_metade() -> None:
    """Ao vivo: `conta-b` e nada de `conta`, com a mesa vazia e com controle.

    A MORDIDA: devolva `"conta": …` ao `pacotes.topo()` e a primeira asserção
    reprova; tire o `or SEM_CONTROLE_NA_MESA` e a mesa vazia volta ao
    travessão solto ao lado da bolinha.
    """
    vazio = pacotes.topo(pacotes.Contexto(state={}, mesa=[], conectados=[], estados={}))
    assert "conta" not in vazio, vazio.get("conta")
    assert vazio["conta-b"] == pacotes.SEM_CONTROLE_NA_MESA

    um = [{"pref": "p1", "jogador": 1, "uniq": "aa:bb:cc:00:00:01", "transporte": "usb"}]
    cheio = pacotes.topo(pacotes.Contexto(state={}, mesa=um, conectados=[], estados={}))
    assert cheio["conta-b"] == "1 USB", cheio["conta-b"]
