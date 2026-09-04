"""O DESENHO GRANDE da `04-iluminacao` acende a luz do APARELHO, não a do mockup.

O QUE ESTAVA NA TELA DELA, medido no DOM VIVO em 03/09/2026 com o produto
instalado e UM controle no cabo
(``scripts/ensaios/a_luz_do_desenho_e_a_luz_do_aparelho.py``)::

    p1   o aparelho em (0, 0, 255)     e o desenho acendendo (126, 184, 212)
    p1   o número 1, que pede a lâmpada 3, e o desenho acendendo NENHUMA

O `#7EB8D4` é o `--luz` que o gerador CRAVA no `<g id="il-p1-lightbar">`: a cor
do MOCKUP, parada na tela dela debaixo de uma caixa que já dizia `#0000FF`. A
mesma célula afirmando duas cores — e quem olha lê o desenho antes do número.

AS CINCO LÂMPADAS ERAM PIOR: elas não acendiam **nenhuma**. `--led-apagado` e
`--led-aceso` são declarados em `.luzinhas` (`monta.CSS_LUZINHAS`), que é o
indicador PEQUENO da célula LEDs; as regras do desenho pintam `<rect>` dentro do
SVG, e `.luzinhas` é uma FOLHA da árvore, não um ancestral. As duas variáveis
chegavam vazias, o `fill:var(--led-aceso)` ficava inválido no tempo de computar
e as cinco herdavam o cinza do casco — com o `title` da própria moldura
prometendo que *"as cinco lâmpadas dizem qual é [o número]"*.

É O DEFEITO QUE O `CSS_LUZINHAS` JÁ TINHA PAGADO um andar acima, e está escrito
lá: *"Um bloco reusável que depende de um seletor da aba que o pariu não é
reusável"*. A aba 04 o repetiu ao usar os tokens fora do seletor deles.

POR QUE A CURA VIAJA NUMA FOLHA DE ESTILO, e não num campo: o pintor escreve
texto, largura, fundo, valor, `innerHTML`, classe, cor, atributo e `--plastico`
— **nenhum deles escreve um `--luz`**. É a mesma razão da `folha_do_plastico`,
e o `<style id="plastico-vivo">` que a carrega **já está publicado**, que é o
que faz esta cura chegar à tela dela HOJE.

O QUE ESTES TESTES COBREM, cada um com a mordida escrita:

1. o par das lâmpadas é LIDO do dono, e no escopo que o desenho alcança;
2. a barra acende a cor que o MOTOR afirma, e vence o `--luz` cravado;
3. sem cor a afirmar a barra APAGA, e o apagado é `initial` — o que faz a folha
   cair no `var(--luz-apagada)` em vez de deixar um halo aceso;
4. as lâmpadas seguem `player_led_pattern` do número VIVO, e a ordem das regras
   é o que decide qual fica acesa;
5. um lugar SEM controle apaga — o `--luz` do mockup não sobrevive num "P3
   Desconectado";
6. a folha viva sai no `blocos:` do `#plastico-vivo`, que é o seletor que a
   página PUBLICADA tem.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _p in (str(RAIZ / "src"),
           str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: A MESA DELA DE 03/09/2026 — um White no cabo e um por rádio sem cor lida.
#: MAC da faixa sintética da casa: há dois portões de anonimato nesta árvore.
MESA_DELA = [
    {"pref": "p1", "uniq": "aa:bb:cc:00:00:01", "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB", "transporte": "usb"},
    {"pref": "p2", "uniq": "aa:bb:cc:00:00:02", "jogador": 2, "cor": "",
     "nome": "Não sei", "via": "BT", "transporte": "bt"},
]

#: A COR CONHECIDA E ACESA — o único ramo em que `rotulo_lightbar` não tem
#: ressalva, e por isso o único em que o desenho PODE afirmar uma cor.
NO_CABO = {"uniq": "aa:bb:cc:00:00:01", "transport": "usb", "connected": True,
           "player": 1, "player_slot": 1, "is_primary": True,
           "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
           "lightbar_source": "sysfs", "battery_pct": 95}

#: A STEAM SEGURANDO O `fd` — a ressalva que estava viva na mesa dela quando
#: este trabalho foi medido. O motor devolve a última cor NOSSA e um recado, e a
#: regra dela manda o desenho calar: *"se não tá mostrando agora, não tem info
#: pra mostrar no produto"*.
NO_RADIO_DISPUTADO = {"uniq": "aa:bb:cc:00:00:02", "transport": "bt",
                      "connected": True, "player": 2, "player_slot": 2,
                      "is_primary": False, "lightbar_rgb": [255, 0, 0],
                      "lightbar_on": True, "lightbar_source": "sysfs",
                      "lightbar_disputada": True, "battery_pct": 85}


@pytest.fixture
def pacote04():
    from pacotes import a04_iluminacao

    return a04_iluminacao


@pytest.fixture
def carga():
    """O pacote da `04`, com a mesa DELA e os conectados que se pedir."""
    import pacotes

    def montar(conectados=None):
        ctx = pacotes.Contexto(
            state={"active_profile": ""},
            mesa=list(MESA_DELA),
            conectados=list(conectados if conectados is not None
                            else [NO_CABO, NO_RADIO_DISPUTADO]),
            estados={})
        return pacotes.pacote_da_pagina("04-iluminacao.html", ctx)

    return montar


def _regra(folha: str, seletor: str) -> str:
    """O corpo da regra daquele seletor, ou `""`. A ÚLTIMA, que é a que vale."""
    achadas = re.findall(re.escape(seletor) + r"\{([^}]*)\}", folha)
    return achadas[-1] if achadas else ""


# ---------------------------------------------------------------------------
# 1. as duas cores das lâmpadas, no escopo do desenho e LIDAS do dono
# ---------------------------------------------------------------------------
def test_o_par_das_lampadas_e_lido_do_dono_e_nao_digitado(pacote04):
    """`--led-apagado` e `--led-aceso` saem do `monta.CSS_LUZINHAS`.

    Duas cópias divergem no primeiro ajuste, e a lâmpada PEQUENA e a GRANDE da
    mesma célula passariam a ter dois brancos.

    A MORDIDA: troque `token_das_luzinhas('--led-aceso')` por um `"#fff"`
    escrito à mão em `tokens_da_luz` e este teste reprova — ele compara com o
    que o dono declara, não com um valor que alguém digitou aqui.
    """
    import monta

    dono = dict(re.findall(r"(--led-[a-z]+)\s*:\s*([^;}]+)", monta.CSS_LUZINHAS))
    assert dono, ("`monta.CSS_LUZINHAS` deixou de declarar o par de cores das "
                  "lâmpadas — o desenho grande lê de lá.")
    corpo = _regra(pacote04.tokens_da_luz(), pacote04.ESCOPO_DO_DESENHO)
    for nome, valor in dono.items():
        assert f"{nome}:{valor.strip()}" in corpo, (
            f"o token {nome} da folha do desenho ({corpo!r}) não é o que o dono "
            f"declara ({valor.strip()!r}).")


def test_o_par_nao_e_declarado_so_em_luzinhas(pacote04):
    """O escopo é `.luz-grade`, e não `.luzinhas` — é isso que estava errado.

    `.luzinhas` é o indicador PEQUENO; um `<rect>` dentro do SVG não desce dele.

    A MORDIDA: ponha `ESCOPO_DO_DESENHO = ".luzinhas"` e este teste reprova —
    foi exatamente esse escopo que deixou as cinco lâmpadas do desenho grande
    apagadas na tela dela.
    """
    assert pacote04.ESCOPO_DO_DESENHO == ".luz-grade", (
        f"o escopo da folha do desenho virou {pacote04.ESCOPO_DO_DESENHO!r}; a "
        f"grade é quem envolve os SVGs, e é ela que tem de declarar o par.")
    assert ".luzinhas" not in pacote04.tokens_da_luz(), (
        "a folha voltou a declarar o par em `.luzinhas`, que é o indicador "
        "pequeno — as lâmpadas do desenho grande não descem dele.")


# ---------------------------------------------------------------------------
# 2. e 3. a barra — a cor que o motor afirma, e o silêncio quando ele não afirma
# ---------------------------------------------------------------------------
def test_a_barra_acende_a_cor_do_aparelho_e_vence_a_cravada(pacote04):
    """A cor da barra vem do dado, e a regra é `!important`.

    O `!important` NÃO é força bruta: o `--luz` do mockup mora no atributo
    `style` do `<g>`, e declaração de linha vence folha. Sem ele a cura monta o
    mecanismo inteiro e a tela continua com `#7EB8D4`.

    A MORDIDA: tire o `!important` da regra da barra em `folha_da_luz` e este
    teste reprova; tire-o e rode o ensaio no produto, e a barra volta ao azul do
    mockup com a folha viva escrita e sem efeito nenhum.
    """
    folha = pacote04.folha_da_luz({"p1": ("#0000FF", 1)})
    corpo = _regra(folha, f'.ctrl[data-controle="p1"] {pacote04.ALVO_DA_BARRA}')
    assert "--luz:#0000FF" in corpo, (
        f"a barra do p1 não recebeu a cor do aparelho: {corpo!r}")
    assert "!important" in corpo, (
        "a regra da barra perdeu o `!important` — o `--luz` cravado no `style` "
        "do `<g>` volta a vencer, e a tela fica com a cor do mockup.")


def test_sem_cor_a_afirmar_a_barra_apaga_com_initial(pacote04):
    """Apagar é `initial`, e não um cinza escrito na folha viva.

    Uma propriedade personalizada em `initial` fica *guaranteed-invalid*, e é
    isso que faz o `fill:var(--luz,var(--luz-apagada))` da página cair no
    SEGUNDO argumento — o mesmo caminho de uma coluna que nasce sem `--luz`. Com
    um hexadecimal no lugar haveria um segundo "apagado" ao lado do que a aba já
    declara, e o `drop-shadow(… var(--luz))` continuaria ACESO em volta de uma
    barra apagada.

    A MORDIDA: troque `BARRA_APAGADA` por `LUZ_APAGADA` e este teste reprova.
    """
    assert pacote04.BARRA_APAGADA == "initial"
    folha = pacote04.folha_da_luz({"p1": ("", 1)})
    corpo = _regra(folha, f'.ctrl[data-controle="p1"] {pacote04.ALVO_DA_BARRA}')
    assert corpo == "--luz:initial !important", (
        f"a barra sem cor a afirmar não apagou pelo caminho da folha: {corpo!r}")


def test_o_travessao_tambem_apaga(pacote04):
    """`—` é o que o molde escreve num lugar sem dono, e ele NÃO é uma cor.

    A MORDIDA: tire o `TRAVESSAO` da comparação em `folha_da_luz` e este teste
    reprova com `--luz:—`, que é uma declaração inválida — a barra ficaria na
    cor do mockup, que é o defeito de partida.
    """
    from pacotes import TRAVESSAO

    folha = pacote04.folha_da_luz({"p1": (TRAVESSAO, 1)})
    corpo = _regra(folha, f'.ctrl[data-controle="p1"] {pacote04.ALVO_DA_BARRA}')
    assert corpo == "--luz:initial !important", (
        f"o travessão virou cor de barra: {corpo!r}")


# ---------------------------------------------------------------------------
# 4. as cinco lâmpadas — o padrão do DAEMON, e a ordem que decide
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("numero", [1, 2, 3, 4, 5, 6, 7, 8, 9])
def test_as_lampadas_seguem_o_padrao_do_daemon(pacote04, numero):
    """Quem diz quais acendem é `core/led_control.player_led_pattern`.

    Nunca a classe `led-on` do arquivo, que é o desenho perguntando a si mesmo —
    e nunca `monta.PADRAO_JOGADOR`, que só precomputa 1..8 e levanta `KeyError`
    fora disso (medido em 02/09/2026). O 9 está na lista por isso.

    A MORDIDA: inverta o `if acesa` em `folha_da_luz` e os nove casos reprovam.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    folha = pacote04.folha_da_luz({"p1": ("#0000FF", numero)})
    acesas = {int(n) for n in
              re.findall(r'\[id\$="-led-jogador-(\d)"\]\{fill:var\(--led-aceso\)',
                         folha)}
    quero = {i + 1 for i, b in enumerate(player_led_pattern(numero)) if b}
    assert acesas == quero, (
        f"o número {numero} pede as lâmpadas {sorted(quero)} e a folha acende "
        f"{sorted(acesas)}.")


def test_apaga_as_cinco_antes_de_acender_as_do_padrao(pacote04):
    """A ordem é o que decide: as duas regras valem (0,3,0) e as duas são
    `!important`, então quem vem por último ganha.

    Escrever na ordem inversa apagaria a lâmpada que acabou de acender — e a
    tela ficaria como estava antes desta cura, com as cinco iguais.

    A MORDIDA: mova o laço do padrão para ANTES da regra que apaga as cinco e
    este teste reprova.
    """
    folha = pacote04.folha_da_luz({"p1": ("#0000FF", 1)})
    apaga = folha.index(f'.ctrl[data-controle="p1"] {pacote04.ALVO_DAS_LAMPADAS}')
    acende = folha.index('.ctrl[data-controle="p1"] [id$="-led-jogador-3"]')
    assert apaga < acende, (
        "a regra que apaga as cinco lâmpadas veio DEPOIS da que acende a do "
        "padrão — com igual especificidade e as duas `!important`, a última "
        "vence e nenhuma lâmpada fica acesa.")


def test_sem_numero_nenhuma_lampada_acende(pacote04):
    """`None` quer dizer "não sei o número", e não "player 1".

    A MORDIDA: troque o guarda por um `numero or 1` e este teste reprova — a
    tela passaria a afirmar um número que ninguém leu.
    """
    folha = pacote04.folha_da_luz({"p1": ("#0000FF", None)})
    assert "--led-aceso" not in folha.split("led-jogador-\"]", 1)[-1], (
        "sem número a folha acendeu lâmpada — o desenho estaria dizendo um "
        "número que a mesa não deu.")


# ---------------------------------------------------------------------------
# 5. o lugar sem controle — o `--luz` do mockup não sobrevive a ele
# ---------------------------------------------------------------------------
def test_um_lugar_sem_controle_apaga(pacote04):
    """Os quatro lugares recebem regra, e não só os que têm dono.

    O `il-p2-lightbar` do desenho nasce com `--luz:#FF5555`; sem uma regra que o
    apague, um "P2 Desconectado" fica com a barra vermelha do mockup acesa.

    A MORDIDA: troque `TODOS_OS_LUGARES | set(luzes)` por `set(luzes)` e este
    teste reprova — foi assim que a coluna vazia guardou a luz do mockup.
    """
    from pacotes import TODOS_OS_LUGARES

    folha = pacote04.folha_da_luz({"p1": ("#0000FF", 1)})
    for pref in TODOS_OS_LUGARES:
        corpo = _regra(folha, f'.ctrl[data-controle="{pref}"] '
                              f'{pacote04.ALVO_DA_BARRA}')
        assert corpo, f"o lugar {pref} ficou sem regra de barra."
        if pref != "p1":
            assert corpo == "--luz:initial !important", (
                f"o lugar {pref} não tem controle e a barra dele não apagou: "
                f"{corpo!r}")


# ---------------------------------------------------------------------------
# 6. a folha chega à página — pelo seletor que o PUBLICADO tem
# ---------------------------------------------------------------------------
def test_o_pacote_manda_a_folha_da_luz_no_bloco_publicado(carga, pacote04):
    """A folha viva sai no `blocos:` do `#plastico-vivo`.

    O `id` diz "plastico" porque foi o casco que o pariu — e ele fica, porque
    **já está publicado**. Um `<style id="luz-viva">` novo só chegaria à tela
    dela no dia em que ela mandasse publicar a 04, e até lá a barra continuaria
    com a cor do mockup.

    A MORDIDA: tire o `+ folha_da_luz(...)` do `blocos` e este teste reprova; e
    o ensaio no produto volta a acusar as cinco lâmpadas apagadas.
    """
    p = carga()
    folha = (p.get("blocos") or {}).get("#plastico-vivo") or ""
    assert pacote04.ALVO_DA_BARRA in folha, (
        "a folha viva não leva a regra da barra do desenho grande.")
    assert pacote04.ALVO_DAS_LAMPADAS in folha, (
        "a folha viva não leva a regra das cinco lâmpadas.")


def test_a_pagina_publicada_tem_a_ancora_da_folha_viva():
    """`<style id="plastico-vivo">` existe no PUBLICADO, e é o que faz a cura
    chegar hoje. Sem ele o `blocos:` não acha onde pousar e some calado.

    A MORDIDA: aponte o `blocos` para um `#luz-viva` que a página não tem e este
    teste continua verde — por isso ele mede a PÁGINA, e o de cima mede o
    pacote. Os dois juntos é que dizem "o valor sai e tem onde chegar".
    """
    import onde

    publicado = onde.pagina("04-iluminacao.html",
                            publicado=True).read_text(encoding="utf-8")
    assert 'id="plastico-vivo"' in publicado, (
        "a página publicada perdeu o `<style id=\"plastico-vivo\">` — a folha "
        "viva do casco E da luz pousa nele.")


def test_a_cor_da_barra_e_a_que_o_motor_afirma(carga):
    """Ponta a ponta: com cor conhecida e acesa, a barra do p1 acende `#0000FF`;
    com a Steam segurando o `fd`, a do p2 apaga.

    QUEM DECIDE É `controller_card.rotulo_lightbar`, o dono da pergunta *"há cor
    a afirmar?"* — o mesmo que os cards da GUI estável usam. O pacote não tem
    opinião própria sobre isso, e é o que impede a tela de afirmar uma cor que
    ninguém mediu.

    A MORDIDA: troque o `_hex(acesa) if acesa else ""` por `_hex(crua)` no
    `pacote()` e este teste reprova no p2 — a barra passaria a pintar a última
    cor NOSSA com a Steam segurando o hidraw, que é exatamente o que a
    LUZ-CEGA-01 mediu como afirmação sem medida.
    """
    p = carga()
    folha = (p.get("blocos") or {}).get("#plastico-vivo") or ""
    from pacotes import a04_iluminacao as a04

    assert (_regra(folha, f'.ctrl[data-controle="p1"] {a04.ALVO_DA_BARRA}')
            == "--luz:#0000FF !important")
    assert (_regra(folha, f'.ctrl[data-controle="p2"] {a04.ALVO_DA_BARRA}')
            == "--luz:initial !important"), (
        "com a Steam segurando o controle o desenho continuou afirmando uma cor.")


def test_a_bancada_declara_o_par_no_escopo_do_desenho():
    """O HTML da bancada — o que ELA olha — traz a declaração na folha da página.

    A folha VIVA só existe com o daemon; a bancada é um arquivo que ela abre no
    navegador, e lá as cinco lâmpadas têm de acender do mesmo jeito.

    A MORDIDA: tire o `CSS_DA_LUZ_NO_DESENHO` do `CSS` do gerador, rode
    `aba04.py`, e este teste reprova.
    """
    import onde
    from pacotes import a04_iluminacao as a04

    bancada = onde.pagina("04-iluminacao.html").read_text(encoding="utf-8")
    assert a04.tokens_da_luz() in bancada.replace("\n", ""), (
        "a folha da bancada não declara o par das lâmpadas no escopo do "
        "desenho — as cinco saem iguais no arquivo que ela abre.")
