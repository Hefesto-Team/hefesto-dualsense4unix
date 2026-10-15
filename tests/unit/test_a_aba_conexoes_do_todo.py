"""A aba Conexões do desenho do todo: sem «?», sem «i», o X que ignora e o controle pela cor.

A-ABA-CONEXOES-DO-TODO-01 (13/10/2026). O que a régua prova, e a mordida que a derruba:

* nenhum ``span.ajuda`` (o «?») e nenhum ``.cd-info`` (o «i») na página: a dica mora no hover do
  título. MORDIDA: devolver um ``ajuda(...)`` ao gerador, ou um ``cd-info`` ao cartão;
* todo cartão leva ``data-dica-id``, e o que se pode ignorar leva o X (``.cd-x``) com o mesmo gesto
  do antigo «Ignorar». MORDIDA: tirar o ``data-gesto`` do ``.cd-x``;
* o pedido de pareamento e o movimento dizem a cor do plástico («Galactic Purple quer conectar»,
  «Starlight Blue · Meio»), e o botão do movimento é «Mover». MORDIDA: voltar ``P{n}`` ao título;
* o cartão do controle não tem os botões de perfil nem o giroscópio (mudanças 12, 17 e 18): o
  perfil mora na Sistema e o giroscópio na Controles, na Navegação e na Calibrar. MORDIDA:
  devolver o ``gc-perfil`` ou o ``est-mira`` ao cartão;
* a vaga sem controle diz «P3 • Desconectado».

A publicada acompanha o desenho no ``--publicar`` do fecho: a perna dela desta régua fica vermelha
até lá, por desenho.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "mockup" / "08-conexoes.html"
PUBLICADA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py"
CARTAO = RAIZ / "src/hefesto_dualsense4unix/interface/conexoes.py"

ARQUIVOS = [pytest.param(BANCADA, id="bancada"), pytest.param(PUBLICADA, id="publicada")]


def _doc(arquivo: pathlib.Path) -> str:
    """O desenho sem estilo e sem comentário: o que a pessoa vê e o que ela aciona."""
    bruto = arquivo.read_text(encoding="utf-8")
    sem_comentario = re.sub(r"<!--.*?-->", "", bruto, flags=re.S)
    return re.sub(r"<style\b[^>]*>.*?</style>", "", sem_comentario, flags=re.S)


def _cartoes(doc: str) -> list[str]:
    return re.findall(r'<section class="cartao-dica[^>]*>.*?</section>', doc, flags=re.S)


@pytest.mark.parametrize("arquivo", ARQUIVOS)
def test_nenhum_ponto_de_interrogacao_nem_o_i_nos_titulos_cartoes_e_janelas(
        arquivo: pathlib.Path) -> None:
    doc = _doc(arquivo)
    assert not re.search(r'class="ajuda[ "]', doc), "voltou um «?» (span.ajuda)"
    for velho in ("cd-info", "cd-porque", "cd-ignora"):
        assert velho not in doc, f"`{velho}` voltou ao cartão"


@pytest.mark.parametrize("arquivo", ARQUIVOS)
def test_os_titulos_levam_a_dica_no_hover(arquivo: pathlib.Path) -> None:
    doc = _doc(arquivo)
    assert re.search(
        r'<label class="quadro-titulo"[^>]*data-dica="[^"]+"[^>]*>Gestão de controles<', doc
    ), "a Gestão de controles perdeu a dica do título"
    assert re.search(r'data-dica="[^"]+"[^>]*>Dispositivos conectados<', doc), (
        "«Dispositivos conectados» perdeu a dica do título")
    janelas = re.findall(r'<span class="tn-tit"( data-dica="[^"]+")?[^>]*>', doc)
    assert len(janelas) == 5, f"as cinco janelas de mapear: {len(janelas)}"
    assert all(janelas), "uma janela de mapear ficou sem a dica no título"


@pytest.mark.parametrize("arquivo", ARQUIVOS)
def test_todo_cartao_tem_o_id_e_o_que_se_ignora_tem_o_x(arquivo: pathlib.Path) -> None:
    cartoes = _cartoes(_doc(arquivo))
    assert len(cartoes) >= 3, "a régua não achou os cartões — seletor cego é ERRO"
    com_x = 0
    for cartao in cartoes:
        assert re.search(r'data-dica-id="[^"]+"', cartao), f"sem data-dica-id: {cartao[:160]}"
        assert cartao.count('class="cd-x"') <= 1
        if 'class="cd-x"' in cartao:
            com_x += 1
            x = re.search(r'<button class="cd-x"[^>]*>', cartao)
            assert x and 'data-gesto="ignorar"' in x.group(0), x
            assert 'aria-label="Ignorar"' in x.group(0), "o X não se anuncia como «Ignorar»"
            assert 'data-dica="' in x.group(0), "o X não diz o que faz no hover"
    assert com_x >= 1, "nenhum cartão tem o X que ignora"
    assert any('class="cd-x"' not in c for c in cartoes), (
        "o pedido e o movimento não se ignoram: o X é só do conselho")


@pytest.mark.parametrize("arquivo", ARQUIVOS)
def test_o_pedido_e_o_movimento_dizem_a_cor_do_plastico(arquivo: pathlib.Path) -> None:
    doc = _doc(arquivo)
    assert "Galactic Purple quer conectar" in doc
    assert "Roxo quer conectar" not in doc
    mover = next(c for c in _cartoes(doc) if 'data-dica-id="mover:' in c)
    assert "Starlight Blue" in mover and not re.search(r"\bP\d\b", mover.split("<h4")[1]), mover
    assert re.search(r'data-gesto="aceitar-sugestao"[^>]*>Mover</button>', mover), mover


@pytest.mark.parametrize("arquivo", ARQUIVOS)
def test_o_cartao_do_controle_nao_tem_perfil_nem_giroscopio(arquivo: pathlib.Path) -> None:
    doc = _doc(arquivo)
    for saiu in ("gc-perfil", "perfil-do-controle", "est-mira", "Giroscópio como analógico",
                 "Analógico virtual"):
        assert saiu not in doc, f"`{saiu}` voltou à aba Conexões"
    assert "Perfil de desempenho" not in doc and "Perfil econômico" not in doc


@pytest.mark.parametrize("arquivo", ARQUIVOS)
def test_a_vaga_sem_controle_diz_p_n_desconectado(arquivo: pathlib.Path) -> None:
    doc = _doc(arquivo)
    certas = re.findall(r'<span class="gc-nome"[^>]*><b>P\d</b><span class="sep">•</span>'
                        r'Desconectado</span>', doc)
    assert len(certas) >= 2, "a régua não achou as vagas — seletor cego é ERRO"
    assert doc.count("Desconectado</span>") == len(certas), "vaga sem o «P N» no rótulo"


def test_o_gerador_nao_sabe_mais_fazer_um_ponto_de_interrogacao() -> None:
    """MORDIDA: devolver um ``def ajuda`` ou um ``cd-info`` ao gerador reprova."""
    gerador = GERADOR.read_text(encoding="utf-8")
    cartao = CARTAO.read_text(encoding="utf-8")
    assert "def ajuda(" not in gerador and 'class="ajuda' not in gerador
    assert "cd-info" not in gerador + cartao and "cd-ignora" not in gerador + cartao


def test_o_pedido_de_pareamento_se_nomeia_pela_cor_declarada(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem nome dado, o pedido diz a cor do plástico que a pessoa declarou; sem nada, «Controle»."""
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

    central = {"pedindo": [{"aparelho": "aa:bb:cc:00:00:01", "adaptador": "aa:bb:cc:00:00:11",
                            "nome": "Wireless Controller"}]}
    lugares = [{"id": "AABBCC000011"}]
    monkeypatch.setattr(a08, "_cor_declarada_de", lambda _aparelho: "Galactic Purple")
    assert a08._quem_pede_para_parear(central, lugares, ())[0]["nome"] == "Galactic Purple"
    monkeypatch.setattr(a08, "_cor_declarada_de", lambda _aparelho: "")
    assert a08._quem_pede_para_parear(central, lugares, ())[0]["nome"] == a08.CONTROLE_SEM_NOME
