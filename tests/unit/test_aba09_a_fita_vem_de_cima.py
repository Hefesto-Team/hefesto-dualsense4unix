"""A fita da aba 09 diz o controle que está NA MESA, nunca o do mockup.

A LEI É DELA, 03/09/2026:

    "se no topo tá mostrando controle white player 1, então cada aba vai usar
    os controles lá de cima. Não mistura com a info dos mockups. Cada feature
    faz referencia ao controle conectado."   # noqa-acento: citação literal dela

O QUE ELA VIU, e é o que estes testes trancam. Medido nesta árvore em
03/09/2026 com os dois controles dela ligados — um `White` no cabo, um segundo
no rádio:

    a mesa viva        p1 White USB (cor lida)  ·  p2 — BT (cor VAZIA)
    o cabeçalho        `2 controles: 1 USB · 1 BT`        <- vivo, certo
    o perfil           `meu_perfil`                       <- vivo, certo
    a fita             `P1 · Cosmic Red · USB`
                       `P2 · Starlight Blue · BT`         <- OS DOIS DO MOCKUP

A CAUSA, medida no mesmo dia: `hefesto_vivo._fita` desiste com
`any(not c.get("cor") for c in mesa)`. No cabo isso é uma espera de poucos
tiques; **pelo rádio a cor NUNCA chega** — quem diz é o mapa de canais
(`identidade.cor_do_aparelho`, `radio_aciona = não`). Com um controle no rádio a
guarda é permanente e a fita das dez abas nunca repinta.

AS DUAS METADES QUE ESTES TESTES SEPARAM, e é onde uma frente honesta se
distingue de uma que só maquia:

* o ENDEREÇO existe na bancada (o que a régua da identidade mede);
* alguém ESCREVE nele com o que leu do daemon (o que a régua não vê).

Um `data-campo` sem escritor zera a régua e deixa a tela igualmente mentindo —
seria trocar um congelado por um vazio.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a09_sistema

RAIZ = pathlib.Path(onde.RAIZ)
BANCADA = onde.BANCADA / "09-sistema.html"
GERADOR = RAIZ / "src/hefesto_dualsense4unix/interface/aba09.py"

#: A MESA DELA DE 03/09/2026, e ela é o caso que importa: um controle com a cor
#: lida pelo cabo e um SEM cor, porque veio pelo rádio. Uma mesa em que os dois
#: têm cor não separa a cura do defeito — era justamente o controle sem cor que
#: derrubava a fita inteira.
MESA_DELA = [
    {"pref": "p1", "uniq": "aa11", "jogador": 1, "cor": "white", "nome": "White",
     "via": "USB", "transporte": "usb", "alvo": True, "mascara": "DualSense"},
    {"pref": "p2", "uniq": "bb22", "jogador": 2, "cor": "", "nome": "Não sei",
     "via": "BT", "transporte": "bt", "alvo": False, "mascara": "DualSense"},
]

#: OS DOIS NOMES DO DESENHO. Nenhum deles é controle dela, e é por eles que se
#: reconhece o mockup falando pela máquina.
DO_MOCKUP = ("Cosmic Red", "Starlight Blue", "#ae335a", "#7eb8d4")


def _regua():
    """A régua da identidade, carregada do script que é dona dela."""
    caminho = RAIZ / "scripts/check_identidade_vem_de_cima.py"
    if not caminho.exists():
        pytest.skip("`scripts/check_identidade_vem_de_cima.py` não está nesta árvore")
    spec = importlib.util.spec_from_file_location("_regua_identidade", caminho)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _fita_da_bancada() -> str:
    """Só o bloco `<div class="fita …">…</div>` da página gerada."""
    x = BANCADA.read_text(encoding="utf-8")
    # `fita` COMO CLASSE INTEIRA: `'<div class="fita'` cru casa primeiro com
    # `<div class="fita-linha">`, o invólucro que também guarda o Perfil ativo.
    m = re.search(r'<div class="fita[ "]', x)
    assert m, "a `.fita` sumiu da página gerada"
    return x[m.start():x.index("</div>", m.start()) + len("</div>")]


# ---------------------------------------------------------------------------
# 1. O ENDEREÇO — o que a régua da identidade mede
# ---------------------------------------------------------------------------
def test_a_fita_da_bancada_tem_endereco_de_conjunto() -> None:
    """A `.fita` leva `data-campo` + `data-hef-alvo="html"`.

    É o conjunto que muda, e não um chip: o número de chips é o número de
    controles na mesa, e não há `data-campo` para um chip que ainda não existe.
    """
    bloco = _fita_da_bancada()
    assert 'data-campo="fita-chips"' in bloco
    assert 'data-hef-alvo="html"' in bloco


def test_o_endereco_nao_pousou_no_involucro() -> None:
    """E ele NÃO está na `.fita-linha`, que guarda o Perfil ativo.

    Aconteceu na primeira execução do gerador, em 03/09/2026: a âncora
    `'<div class="fita'` casou com `<div class="fita-linha">`. Endereçar o
    invólucro com alvo `html` mandaria o produto reescrever o miolo dele a cada
    tique e APAGAR o `data-campo="perfil"` do cabeçalho, que é das dez abas.
    """
    x = BANCADA.read_text(encoding="utf-8")
    linha = x[x.index('<div class="fita-linha'):]
    linha = linha[:linha.index('<div class="fita ')]
    assert "data-campo" not in linha, (
        "o endereço do conjunto pousou na `.fita-linha` — o produto passaria a "
        "reescrever o miolo dela e o `data-campo=\"perfil\"` do cabeçalho morreria")
    assert 'data-campo="perfil"' in x, "o Perfil ativo perdeu o endereço"


def test_cada_chip_de_controle_tem_o_seu_endereco() -> None:
    """A régua julga o `--plastico` pelo endereço do PRÓPRIO elemento.

    E ela está certa em julgar assim: um pai endereçado para TEXTO não daria ao
    filho o direito de trazer cor congelada. Aqui o pai é endereçado para HTML —
    o produto reescreve o chip inteiro —, e o `data-campo` do chip é o que
    registra isso no arquivo.
    """
    bloco = _fita_da_bancada()
    com_cor = re.findall(r'<label class="chip plastico[^>]*>', bloco)
    assert com_cor, "nenhum chip de plástico na fita — a forma da página mudou"
    for chip in com_cor:
        assert 'data-campo="fita-chip"' in chip, f"chip sem endereço: {chip}"


def test_o_chip_todos_nao_ganhou_endereco() -> None:
    """O `Todos` não é aparelho nenhum.

    Ele não traz cor nem nome de plástico; endereçá-lo diria que o produto o
    reescreve por identidade, o que não é verdade. Endereço morto é o defeito que
    esta leva existe para não repetir.
    """
    bloco = _fita_da_bancada()
    todos = re.search(r'<label class="chip on"[^>]*>Todos</label>', bloco)
    assert todos, "o chip `Todos` sumiu da fita"
    assert "data-campo" not in todos.group(0)


def test_a_regua_da_identidade_nao_acha_nada_na_09() -> None:
    """Zero congelados de identidade na bancada da 09. É o `PRONTO É` da spec."""
    regua = _regua()
    achados = regua.congelados_de(BANCADA, regua.nomes_de_colorway())
    assert achados == [], "\n".join(f"{ln}: {oq} -> {tr}" for ln, oq, tr in achados)


def test_o_gerador_e_o_pacote_escrevem_o_mesmo_nome() -> None:
    """O endereço está escrito em DOIS arquivos, e eles têm de casar.

    Escrito duas vezes sem régua, os dois divergem no dia em que alguém mudar um
    — foi assim que a fita viva morreu em silêncio em 27/08, quando o texto do
    chip mudou e o remendo deixou de casar. Ler o gerador por IMPORT não serve:
    ele escreve a bancada no import.
    """
    fonte = GERADOR.read_text(encoding="utf-8")
    for nome, valor in (("CAMPO_DA_FITA", a09_sistema.CAMPO_DA_FITA),
                        ("CAMPO_DO_CHIP", a09_sistema.CAMPO_DO_CHIP)):
        m = re.search(rf'^{nome} = "([^"]+)"', fonte, re.M)
        assert m, f"`{nome}` sumiu de `aba09.py`"
        assert m.group(1) == valor, (
            f"`{nome}` é {m.group(1)!r} no gerador e {valor!r} no pacote")


# ---------------------------------------------------------------------------
# 2. QUEM ESCREVE — o que a régua da identidade NÃO vê
# ---------------------------------------------------------------------------
def test_a_fita_viva_nomeia_o_controle_da_mesa() -> None:
    """Com a mesa dela, o chip do cabo diz `White` e traz a cor do plástico."""
    saida = a09_sistema._html_da_fita(MESA_DELA)
    assert "White" in saida
    assert "--plastico:" in saida


def test_a_fita_viva_nao_traz_um_nome_do_mockup() -> None:
    """Nenhum dos dois controles do desenho aparece — nem por nome, nem por hex.

    É a mordida desta frente: um `_html_da_fita` que caísse de volta no mockup
    (ou que copiasse os chips do arquivo) reprova aqui.
    """
    saida = a09_sistema._html_da_fita(MESA_DELA)
    for agulha in DO_MOCKUP:
        assert agulha not in saida, f"o mockup falou pela máquina: {agulha}"


def test_o_controle_sem_cor_nao_ganha_cor_inventada() -> None:
    """Campo sem informação não mostra nada — regra dela.

    Pelo rádio a cor do plástico não chega. O chip perde a borda colorida e o
    `title` diz por quê; o que ele NÃO faz é escolher um tom para preencher.
    """
    saida = a09_sistema._html_da_fita(MESA_DELA)
    chips = re.findall(r'<label class="chip[^"]*" data-campo="fita-chip"[^>]*>', saida)
    assert len(chips) == 2, f"esperava dois chips de controle, achei {len(chips)}"
    assert "--plastico:" in chips[0], "o controle do cabo perdeu a cor que foi lida"
    assert "--plastico:" not in chips[1], (
        "o controle do rádio ganhou uma cor que ninguém leu")
    assert "plastico" not in chips[1].split("data-campo")[0], (
        "o chip sem cor manteve a classe `plastico` e continua com a borda colorida")
    assert "não foi lida" in chips[1]


def test_o_chip_sem_leitura_nao_diz_nao_sei_nem_travessao() -> None:
    """`Não sei` é a AUSÊNCIA de leitura, não um nome — e `—` também não.

    E o nome que só repete o transporte sai: o chip TERMINA no transporte, e
    `P2 • rádio • rádio` afirma o mesmo fato duas vezes.

    A PALAVRA É PERGUNTADA À DONA — ONDA4-S10, 06/09/2026. Esta linha contava
    `"BT"`, a sigla de máquina, e por isso reprovou a decisão dela (D-05) em vez
    do defeito: o dia em que a fita passou a dizer `rádio`, a contagem de `"BT"`
    virou ZERO e a régua leu isso como "o transporte sumiu do chip".
    """
    from hefesto_dualsense4unix.app.actions.home_actions import palavra_do_transporte

    saida = a09_sistema._html_da_fita(MESA_DELA)
    segundo = saida[saida.rindex("<label class=\"chip"):]
    assert "Não sei" not in segundo
    assert "—" not in segundo
    palavra = palavra_do_transporte("bt")
    assert segundo.count(palavra) == 1, f"o transporte saiu duas vezes: {segundo}"


def test_mesa_vazia_nao_apaga_a_fita() -> None:
    """Sem controle na mesa a fita não se mexe.

    `""` faz o piloto pular a pintura; escrever vazio no `innerHTML` apagaria a
    tira inteira entre uma reconexão e outra.
    """
    assert a09_sistema._html_da_fita([]) == ""


def test_o_pacote_emite_o_endereco_da_fita(monkeypatch: pytest.MonkeyPatch) -> None:
    """O `pacote()` da aba 09 devolve a chave, e ela não vem vazia.

    A camada do produto é dublada: o que se mede aqui é a EMISSÃO do endereço da
    fita, e não o resto do pacote — que já tem régua própria.
    """
    monkeypatch.setattr(a09_sistema, "_leitura", lambda ctx: None)
    monkeypatch.setattr(a09_sistema._tela, "pacote", lambda leitura: {"valores": {}})
    ctx = pacotes.Contexto(state={}, mesa=MESA_DELA, conectados=[], estados={})
    fora = a09_sistema.pacote(ctx)
    assert a09_sistema.CAMPO_DA_FITA in fora, (
        "o pacote parou de emitir a fita — a tela volta a mostrar o desenho")
    assert "White" in str(fora[a09_sistema.CAMPO_DA_FITA])


def test_o_endereco_atravessa_o_normalizar() -> None:
    """A chave chega ao JS como campo solto, e não é comida no caminho.

    `normalizar` descarta todo `dict` que não seja `blocos`; uma STRING atravessa
    e vira campo da `mesa`, que é o dicionário que o pintor percorre por
    `data-campo`. Sem esta régua, um pacote correto continuaria sem pintar nada —
    o defeito que custou dois dias calado ao `blocos` em 02/09.
    """
    fora = pacotes.normalizar({a09_sistema.CAMPO_DA_FITA: "<b>x</b>"})
    assert fora["mesa"][a09_sistema.CAMPO_DA_FITA] == "<b>x</b>"
