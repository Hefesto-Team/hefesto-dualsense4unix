#!/usr/bin/env python3
"""A RÉGUA DO PORTÃO NOVO: nenhum texto de tela confessa dívida NOSSA.

ORDEM DELA, 07/09/2026:

    *"O app tem que funcionar e não mostrar na tela que o app não presta. Se
     não tem como, ok. Testamos e criamos o canal. até lá tudo bem, o layout
     não informa os nossos defeitos."*

**POR QUE ESTE ARQUIVO EXISTE, e não só o script.** O portão vive em
``scripts/check_a_tela_nao_confessa.py`` e roda no ``portoes.sh`` e no CI. Mas
esta casa acabou de pagar, nesta mesma aba e neste mesmo dia, o preço de uma
régua que só roda quando alguém a chama: o ``aba04._conferir`` tem quatorze
seções e mora dentro de ``if __name__ == "__main__"`` — *"roda quando alguém
digita `python aba04.py`; nunca no pytest"*. Um conferente escondeu os dois
botões que ela usa e **nenhuma régua reprovou**. Então o portão roda AQUI
também, no processo do pytest, e as peneiras dele são exercitadas por dublê.

**A MORDIDA, e ela é o teste — não uma nota de rodapé.** Cada `test_morde_*`
abaixo alimenta a peneira com uma frase que ela mandou tirar e cobra que ela
seja acusada; e com uma frase legítima, cobrando que passe. Régua que só sabe
passar não é régua.
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_a_tela_nao_confessa.py"


@pytest.fixture(scope="module")
def portao():
    """O script importado como módulo — sem `sys.path` global e sem subprocesso.

    `importlib.util.spec_from_file_location` porque `scripts/` não é pacote;
    é o mesmo caminho que outras réguas desta casa já usam para morder um
    script sem o instalar.
    """
    spec = importlib.util.spec_from_file_location("_portao_confissao", PORTAO)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. O PORTÃO PASSA NA ÁRVORE DE HOJE
# ---------------------------------------------------------------------------
def test_o_portao_passa_na_arvore_de_hoje() -> None:
    """Ele roda no `portoes.sh` e no CI; aqui ele roda também, e no pytest.

    O SUBPROCESSO É DE PROPÓSITO nesta linha: é exatamente o que o `portoes.sh`
    faz, e é o `rc` dele que decide a integração. As peneiras são mordidas
    abaixo, por dublê, sem tocar em disco.
    """
    r = subprocess.run([sys.executable, str(PORTAO)], capture_output=True,
                       text=True, cwd=RAIZ)
    assert r.returncode == 0, (
        f"o portão da confissão reprovou:\n{r.stdout}\n{r.stderr}")


# ---------------------------------------------------------------------------
# 2. AS TRÊS FRASES QUE ELA MARCOU SAÍRAM — dos DOIS lados
# ---------------------------------------------------------------------------
#: Ela marcou três cantos na foto e nomeou três frases. As duas metades andam
#: juntas: a bancada é o que ela olha, e `paginas/` é o que o
#: `WebKit2.WebView` renderiza. Um conserto que fica só num lado não chega à
#: tela dela — e foi assim que a régua nova pegou, nesta leva, uma cura que
#: existia no `mockup/` e não no publicado.
AS_QUE_SAIRAM = (
    ("06-navegacao.html", "o Hefesto ainda não faz"),
    ("02-controles.html", "não faz o som sair neste alto-falante"),
    ("01-jogar.html", "não sabe montar esta máscara"),
)


@pytest.mark.parametrize(("pagina", "frase"), AS_QUE_SAIRAM)  # noqa-acento: nome de parametro
def test_a_frase_que_ela_marcou_saiu_dos_dois_lados(pagina: str, frase: str) -> None:
    from hefesto_dualsense4unix.interface import onde

    for caminho in (onde.pagina(pagina), onde.PUBLICADO / pagina):
        texto = caminho.read_text(encoding="utf-8")
        assert frase not in texto, (
            f"{caminho.name} ainda diz {frase!r} — ela marcou esta frase em "
            f"07/09/2026, e a ordem é que o layout não informe os nossos "
            f"defeitos")


def test_a_divida_do_alto_falante_continua_no_mapa() -> None:
    """A tela calou; a dívida NÃO fechou — e virar a célula seria mentir.

    É a metade que separa *"tiramos da tela"* de *"fingimos que fechou"*, e ela
    é ordem dela por escrito: *"NÃO vire a célula — o canal continua fechado e
    virar seria mentir ao contrário."*
    """
    from hefesto_dualsense4unix.app.fatos_do_mapa import FATOS

    celula = FATOS["audio.alto_falante@dualsense"]["radio"]
    assert isinstance(celula, dict)
    assert celula["aciona"] != "sim", (
        "a célula do alto-falante no rádio virou para `sim`. Calar a tela é "
        "ordem dela; virar a célula não é — o canal continua fechado")


# ---------------------------------------------------------------------------
# 3. A MORDIDA DA PENEIRA — a régua sabe RECUSAR
# ---------------------------------------------------------------------------
#: O que a peneira TEM de acusar. As três primeiras são as que ela marcou; as
#: outras são a mesma família, escritas de outro jeito.
CONFISSOES = (
    "Rolar com dois dedos no touchpad é outra coisa, e o Hefesto ainda não faz.",
    "Pelo rádio o Hefesto ainda não faz o som sair neste alto-falante.",
    "O Hefesto não sabe montar esta máscara.",
    "Ainda não sei olhar este lançador.",
    "O perfil ainda não tem por onde limitar estes.",
    "Não conseguimos ler isto por aqui.",
)

#: O que a peneira NÃO pode acusar, e é a parte difícil: a MESMA forma, com o
#: sujeito do outro lado. As quatro primeiras estão na tela hoje e são
#: legítimas — foi medindo-as que a régua aprendeu a não decidir sozinha.
LEGITIMAS = (
    "Não sei onde fica",
    "Sem resposta não é o mesmo que “Não sei”.",
    "O perfil não guarda uma configuração: guarda uma por controle.",
)


@pytest.mark.parametrize("frase", CONFISSOES)
def test_morde_a_peneira_acusa_a_confissao(portao, frase: str) -> None:
    """MORDE: tire a alternativa do `ainda` da FORMA e estas seis passam calado."""
    assert portao._forma(frase), (
        f"a peneira deixou passar {frase!r} — é a família que a ordem dela de "
        f"07/09/2026 manda tirar da tela")


@pytest.mark.parametrize("frase", LEGITIMAS)
def test_a_peneira_nao_acusa_a_voz_da_pessoa_nem_a_afirmacao_positiva(
        portao, frase: str) -> None:
    """A voz DELA respondendo *"não sei"* não é o produto confessando.

    MEDIDO NESTA LEVA: a primeira peneira tinha `não sei` solto, e das 40
    acusações 18 eram a pessoa falando — a opção de uma lista, o botão do passo
    a passo, e a explicação de que *"sem resposta não é o mesmo que Não sei"*.
    Uma tabela com dezoito linhas dessas ninguém lê, e uma tabela que ninguém
    lê é a régua desligada por dentro.
    """
    assert not portao._forma(frase), (
        f"a peneira acusou {frase!r}, que é a voz da pessoa ou uma afirmação "
        f"positiva — obrigar a declarar isto esvazia a tabela de sentido")


def test_a_afirmacao_positiva_e_pega_pela_forma_e_so_a_tabela_a_absolve(portao) -> None:
    """*"O Hefesto não é só para a Steam"* é o oposto de uma confissão — e a
    peneira a pega assim mesmo, porque ela casa por FORMA e não por sentido.

    **ISSO NÃO É UM DEFEITO DA PENEIRA; é o desenho dela.** Nenhuma expressão
    regular lê sentido, e uma que tentasse erraria para o outro lado — deixando
    passar a confissão escrita com jeito. O que a régua faz é obrigar a
    DECLARAR, e declarar custa uma linha e ensina a quem vier: a pergunta a
    responder é *de quem é o sujeito*.

    **A FRASE SAIU DA TELA EM 11/09/2026** — A2-002, aprovada por ela: o `?` da
    aba Lançadores perdeu os dois parágrafos que definiam a aba por negação. E
    a linha que a declarava saiu no MESMO commit, porque o portão confere nos
    dois sentidos: declaração que sobrevive à frase envelhece calada, e a
    próxima pessoa a lê como se a confissão continuasse lá.

    O EXEMPLO FICA, e agora ensina a outra metade: no dia em que esta frase
    voltar à tela, a peneira a pega e a tabela não a absolve — que é
    exatamente a frição que a ordem dela pede.
    """
    frase = "O Hefesto não é só para a Steam."
    assert portao._forma(frase), "a peneira deixou de casar por forma"
    assert not any(k.lower() in frase.lower() for k in portao.FATOS), (
        "a frase saiu da tela em 11/09/2026 e a declaração dela tinha de sair "
        "junto — uma linha em FATOS sobre uma frase que a tela não tem mais é "
        "a declaração que envelhece calada, e o portão reprova por isso")


def test_morde_a_limpeza_vem_antes_do_casamento(portao) -> None:
    """**A ARMADILHA QUE ESTA CASA PAGOU QUATRO VEZES EM QUATRO DIAS.**

    *Um comentário que descreve o padrão proibido vira a primeira ocorrência
    dele.* O CSS do gerador entra INTEIRO na página, e o comentário que
    EXPLICAVA a remoção de um botão já deixou o `paridade-gtk-html` verde sobre
    um botão que não existia — nesta mesma aba, ontem.

    Medido quando esta régua nasceu: das dez frases que a primeira varredura
    achou, DUAS estavam dentro de comentários HTML — as duas eram a explicação,
    não o defeito.

    MORDE: tire o `re.sub` dos comentários de `_limpo` e esta linha reprova.
    """
    pagina = (
        '<!-- este comentário explica que a frase "o Hefesto ainda não faz" '
        'saiu daqui -->\n'
        '<style>/* e o CSS também fala: o Hefesto ainda não faz */</style>\n'
        '<script>// o Hefesto ainda não faz</script>\n'
        '<p>Rola com o analógico direito.</p>'
    )
    assert not portao._forma(portao._limpo(pagina)), (
        "a régua contou a EXPLICAÇÃO como se fosse o defeito — é a armadilha "
        "de prosa que esta casa pagou quatro vezes em quatro dias")
    # E SEM A LIMPEZA ELA CONTA — a segunda metade, que prova que a primeira
    # mede alguma coisa. Sem esta linha, um `_limpo` que apagasse a página
    # inteira passaria no teste acima.
    assert portao._forma(pagina), (
        "o dublê não tem a frase que a régua deveria achar sem a limpeza — a "
        "mordida não estaria medindo nada")


def test_morde_a_legenda_do_mockup_fica_de_fora_e_a_janela_nao(portao) -> None:
    """O recorte é a JANELA, e a `.nota` é a legenda — *"fora da janela"*.

    A folha da casa a declara assim com todas as letras. A legenda é o
    documento em que a casa conta a ELA o que mudou e por quê, e é lá que a
    dívida DEVE ser nomeada — obrigar a declarar cada linha dela transformaria
    a tabela num índice do CHANGELOG.

    **RELATADO em 07/09/2026:** essa legenda viaja para o publicado, então o
    produto instalado carrega o registro de obra do mockup. Se ela deve ou não
    ir junto é decisão de tela, e a tela é dela.
    """
    pagina = ('<p title="o Hefesto ainda não faz isto">um</p>'
              '<div class="nota">e aqui o Hefesto ainda não faz aquilo</div>')
    dentro = portao._dentro_da_janela(pagina)
    assert portao._forma(dentro), "a régua deixou de olhar dentro da janela"
    assert len(portao._forma(dentro)) == 1, (
        "a régua entrou na legenda do mockup — ali a dívida é para ser "
        "nomeada, e é o que ela lê para aprovar o desenho")


def test_morde_a_tabela_nao_pode_ficar_orfa(portao) -> None:
    """Declaração que sobrevive à frase envelhece calada — e mente ao contrário.

    É a mesma regra do portão da lista de portões: a checagem vale nos DOIS
    sentidos. Uma linha declarada que a tela não tem mais faz a próxima pessoa
    ler uma confissão que já saiu.
    """
    assert "orfas" in PORTAO.read_text(encoding="utf-8"), (
        "o portão perdeu a checagem do sentido inverso")


def test_toda_divida_declarada_diz_o_endereco_e_a_data(portao) -> None:
    """A tabela da dívida só encolhe, e cada linha tem de dizer ONDE e QUANDO.

    Sem endereço a linha é um lamento; com endereço ela é uma fila. As três de
    hoje estão fora dos arquivos desta leva, e é por isso que existem — a ordem
    dela chegou depois delas.
    """
    for frase, razao in portao.A_DIVIDA.items():
        assert "/" in razao or "aba" in razao, (
            f"a dívida {frase!r} não diz o endereço de quem a tira")
        assert "/2026" in razao, (
            f"a dívida {frase!r} não diz a data em que foi medida")
