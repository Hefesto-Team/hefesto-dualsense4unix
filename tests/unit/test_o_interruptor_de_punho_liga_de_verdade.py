"""O interruptor de punho da aba Vibração acende com a barra, e o clique escreve.

ORDEM DELA, 14/09/2026, com os dois controles na mesa e a foto da aba na mão:

    *"ao abrir o vibração o motor esquerdo do controle azul não fica ativado e
     nem se eu clicar em máximo ele liga. ele deveria ligar se > 0 no slicer
     dele."*  (noqa-acento: citação literal dela)

O QUE ESTAVA QUEBRADO, e eram DUAS metades — as duas mentindo do mesmo jeito,
medidas no daemon dela no mesmo dia:

1. **não havia pintura.** A classe `on` dos oito botões era a da CENA do mockup:
   o P1 com os dois punhos acesos e o P2 com o esquerdo apagado, cravados no
   HTML. Medido no `state_full` dela às 23h: as DUAS barras do P2 em **100**, e a
   tela mostrando o punho esquerdo dele apagado. A tela afirmava o contrário do
   produto, e afirmava para sempre — nenhum tique a corrigia;
2. **não havia clique.** O botão trazia `data-hef="lado"`, e `data-hef` **não
   está na lista que o ouvinte do piloto varre** (`hefesto_vivo.manda_do_alvo`
   casa `data-gesto`, `data-papel`, `data-forca`, `data-modo`…). O clique morria
   no navegador. E, do outro lado, nenhum gesto `lado` estava registrado para
   atendê-lo: `pacotes.gesto_da_pagina("05-vibracao.html", "lado")` devolvia
   `None`. Um botão morto com cara de interruptor, oito vezes.

A CASA SABIA DOS DOIS, e por escrito: `a05_vibracao.SEM_DONO["lado:ligado"]` e
`app/telas/vibracao.SEM_FONTE["lado:ligado"]` declaravam a dívida desde 02/09,
com sprint (`MIGRA-VIBRACAO-06`) e com a razão certa — *não há campo de habilitar
motor por lado em `profiles/schema.py`*. **A cura de 14/09 não criou o campo.**
Ela leu o que já existia: a barra daquele motor.

A REGRA É DELA E TEM UMA FONTE SÓ: aceso = `barra(motor) > 0`. O clique é o par —
desligar escreve 0, ligar devolve 100 —, pelo mesmo `rumble.motores.set` que o
arraste usa. Um campo `ligado` separado do valor seria a segunda verdade desta
linha, e na primeira vez que os dois divergissem a tela diria "ligado" com a
barra em zero — que é, ao contrário, exatamente o defeito que ela relatou.

O QUE ESTA RÉGUA MORDE, e são as três pontas que faltavam:

* **o desenho** — o botão carrega o endereço de pintura E o do clique, e o do
  clique é um que o ouvinte enxerga;
* **o pacote** — emite `lado-{lado}` do valor da barra, nos dois sentidos;
* **o gesto** — existe, escreve o par certo e recusa dizendo.
"""
from __future__ import annotations

import pathlib
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/05-vibracao.html"
PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

#: Os dois lados, como a tela os chama. Vêm do dono da tradução
#: (`app/telas/vibracao.LADO_PARA_MOTOR`) e não de uma lista digitada: uma
#: terceira sigla que nascesse lá e não aqui passaria calada.
LADOS = tuple(a05._tela.LADO_PARA_MOTOR)

UNIQ = "aa:bb:cc:00:00:01"


def _ctx(barra_e: int, barra_d: int) -> pacotes.Contexto:
    """Uma mesa de um controle, com as duas barras onde o teste quiser.

    O `rumble_motores` é o mapa que `_barras_dos_motores` lê — o MESMO que o
    daemon publica e que `apply_game_rumble` multiplica.
    """
    controle = {"uniq": UNIQ, "connected": True, "player": 1, "transport": "usb"}
    state: dict[str, Any] = {
        "controllers": [controle],
        "rumble_motores": {UNIQ.replace(":", ""): {"forte_pct": barra_e,
                                           "fraco_pct": barra_d}},
        "rumble_policy": "balanceado",
    }
    # O ITEM DE MESA tem a forma que `mesa_viva.mesa_do_estado` monta — as nove
    # chaves, medidas contra o daemon vivo. Faltar uma faz o pacote levantar
    # `KeyError` no meio, que é uma régua medindo o dublê e não o produto.
    item = {"uniq": UNIQ, "pref": "p1", "jogador": 1, "nome": "Prova",
            "cor": "", "transporte": "usb", "via": "cabo",
            "alvo": True, "mascara": "dualsense"}
    return pacotes.Contexto(state=state, mesa=[item], conectados=[controle],
                            estados={}, externos=[])


def _coluna(barra_e: int, barra_d: int) -> dict[str, Any]:
    """A coluna daquele controle, pela chave que o PACOTE usou.

    A chave não se digita: o daemon publica o endereço normalizado e a mesa pode
    trazê-lo com dois-pontos, e escolher uma das duas aqui faria a régua medir a
    grafia em vez do valor.
    """
    colunas = a05.pacote(_ctx(barra_e, barra_d))["colunas"]
    assert len(colunas) == 1, f"a mesa de prova tem um controle; vieram {len(colunas)}"
    return next(iter(colunas.values()))


class _Ponte:
    """Uma ponte que anota o que lhe pedem e nunca fala com o daemon."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def __getattr__(self, nome: str) -> Any:
        def falso(*a: Any, **k: Any) -> tuple[bool, dict[str, str]]:
            self.chamadas.append((nome, k))
            return True, {"status": "ok"}
        return falso


# ---------------------------------------------------------------------------
# 1. O DESENHO — os dois endereços, e o do clique é um que o ouvinte enxerga
# ---------------------------------------------------------------------------

def test_o_botao_do_punho_tem_o_endereco_da_pintura() -> None:
    html = PAGINA.read_text(encoding="utf-8")
    botoes = re.findall(r"<button class=\"lado[^\"]*\"[^>]*>", html)
    assert len(botoes) == 8, (
        f"a aba tem {len(botoes)} interruptores de punho, e são 8 — dois por "
        f"controle, quatro colunas"
    )
    for botao in botoes:
        assert 'data-hef-alvo="classe"' in botao, (
            f"interruptor sem alvo de pintura: {botao}. Sem ele a classe `on` "
            f"volta a ser a da cena do mockup, cravada — que é o defeito que ela "
            f"relatou em 14/09"
        )
        assert re.search(r'data-campo="lado-[a-z]+"', botao), (
            f"interruptor sem `data-campo`: {botao}"
        )


def test_o_clique_do_punho_usa_um_endereco_que_o_ouvinte_enxerga() -> None:
    """A metade que faltava e que nenhuma régua via.

    `data-hef` não está no `closest` do `manda_do_alvo`, então um botão que só o
    tivesse nunca chegaria ao Python — e o teste de gesto passaria, porque ele
    chama a função direto. É a assinatura desta casa: *a régua responde sobre
    outra coisa que não o produto*.

    Ela lê a lista DO PILOTO, nunca uma cópia: o dia em que o ouvinte aprender um
    vocabulário novo, esta régua aprende junto.
    """
    piloto = PILOTO.read_text(encoding="utf-8")
    trecho = piloto[piloto.index("function manda_do_alvo"):][:600]
    vocabulario = set(re.findall(r"\[data-([a-z-]+)\]", trecho))
    assert vocabulario, "não achei a lista de endereços de clique no piloto"

    html = PAGINA.read_text(encoding="utf-8")
    for botao in re.findall(r"<button class=\"lado[^\"]*\"[^>]*>", html):
        atributos = set(re.findall(r"data-([a-z-]+)=", botao))
        assert atributos & vocabulario, (
            f"o interruptor não tem NENHUM endereço que o ouvinte do piloto "
            f"varre ({sorted(vocabulario)}): {botao}\n"
            f"O clique morre no navegador — foi assim que os oito botões ficaram "
            f"mortos com cara de interruptor até 14/09/2026"
        )


# ---------------------------------------------------------------------------
# 2. O PACOTE — acende pela barra, nos dois sentidos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("barra_e", "barra_d", "aceso_e", "aceso_d"),
    [
        (100, 100, "1", "1"),   # os dois cheios: os dois acesos
        (0, 100, "", "1"),      # o caso DELA, ao contrário: só o direito
        (100, 0, "1", ""),
        (0, 0, "", ""),         # nenhum
        (1, 1, "1", "1"),       # *"> 0"*, e não ">= 50": um ponto já acende
    ],
)
def test_o_punho_acende_pela_barra(
    barra_e: int, barra_d: int, aceso_e: str, aceso_d: str
) -> None:
    coluna = _coluna(barra_e, barra_d)
    assert coluna["lado-e"] == aceso_e, (
        f"com a barra esquerda em {barra_e}, o punho devia estar "
        f"{'aceso' if aceso_e else 'apagado'} — a regra dela é *«> 0 no slicer»*"
    )
    assert coluna["lado-d"] == aceso_d


def test_o_aceso_e_a_barra_nunca_discordam() -> None:
    """A razão de não haver campo próprio, medida em vez de afirmada.

    MORDIDA: dar ao interruptor uma fonte separada da barra reprova aqui na
    primeira vez que as duas divergirem — que é o dia em que a tela passa a poder
    dizer "ligado" com o trilho em zero.
    """
    for barra in (0, 1, 37, 100):
        coluna = _coluna(barra, barra)
        for lado in LADOS:
            aceso = bool(coluna[f"lado-{lado}"])
            valor = int(coluna[f"barra-{lado}"])
            assert aceso == (valor > 0), (
                f"o punho {lado} diz {'aceso' if aceso else 'apagado'} e a barra "
                f"dele diz {valor}"
            )


def test_a_divida_declarada_fechou() -> None:
    """A dívida some das DUAS listas, que é a regra da casa contra dívida fantasma."""
    from hefesto_dualsense4unix.app.telas import vibracao

    assert "lado:ligado" not in a05.SEM_DONO
    assert "lado:ligado" not in vibracao.SEM_FONTE


# ---------------------------------------------------------------------------
# 3. O GESTO — existe, escreve o par certo, e recusa dizendo
# ---------------------------------------------------------------------------

def test_o_gesto_existe() -> None:
    assert pacotes.gesto_da_pagina("05-vibracao.html", "lado") is not None, (
        "o gesto `lado` sumiu — os oito interruptores voltaram a ser desenho"
    )


@pytest.mark.parametrize(
    ("lado", "barra_antes", "campo", "valor"),
    [
        ("e", 100, "forte_pct", 0),    # aceso -> desliga
        ("e", 0, "forte_pct", 100),    # apagado -> liga cheio
        ("d", 100, "fraco_pct", 0),
        ("d", 0, "fraco_pct", 100),
    ],
)
def test_o_clique_escreve_o_par_certo(
    lado: str, barra_antes: int, campo: str, valor: int
) -> None:
    """O interruptor é o PAR da barra, e escreve pelo método dela.

    O campo importa: `forte_pct` é o motor ESQUERDO (`e` -> `strong`) e
    `fraco_pct` o direito, e a
    tradução tem um dono (`app/telas/vibracao.MOTOR_PARA_BARRA`). Trocá-los faria
    o punho esquerdo desligar o motor direito — com a tela certa e a mão dela
    sentindo o contrário.
    """
    ctx = _ctx(barra_antes if lado == "e" else 50,
               barra_antes if lado == "d" else 50)
    ponte = _Ponte()
    gesto = pacotes.gesto_da_pagina("05-vibracao.html", "lado")
    assert gesto is not None
    gesto(ctx, {"lado": lado, "uniq": UNIQ, "controle": "p1"}, ponte)

    escritas = [k for nome, k in ponte.chamadas if nome == "rumble_motores_set"]
    assert escritas, "o clique não escreveu nada"
    assert escritas[0].get(campo) == valor, (
        f"clicar o punho {lado!r} com a barra em {barra_antes} devia mandar "
        f"{campo}={valor}; mandou {escritas[0]!r}"
    )
    assert escritas[0].get("uniq") == UNIQ, (
        "o clique foi sem endereço — `rumble.motores.set` sem `uniq` alcança "
        "outro controle que não o da coluna que ela clicou"
    )


def test_o_estado_vem_do_daemon_e_nao_do_que_o_clique_afirma() -> None:
    """O botão pintado no tique anterior diria o estado de ontem.

    MORDIDA: fazer o gesto ler `o["ligado"]` (o `dataset` do botão) em vez do
    `ctx.state` reprova aqui — o clique chega com uma afirmação velha e o gesto
    tem de ignorá-la.
    """
    ctx = _ctx(100, 100)          # o daemon diz: os dois ligados
    ponte = _Ponte()
    gesto = pacotes.gesto_da_pagina("05-vibracao.html", "lado")
    assert gesto is not None
    # …e o clique chega afirmando o contrário, como um botão pintado há um tique
    gesto(ctx, {"lado": "e", "uniq": UNIQ, "controle": "p1", "ligado": "0"}, ponte)

    escritas = [k for nome, k in ponte.chamadas if nome == "rumble_motores_set"]
    assert escritas[0]["forte_pct"] == 0, (
        "o gesto acreditou no que o clique afirmou em vez de perguntar ao "
        "estado: com a barra em 100, clicar DESLIGA"
    )


@pytest.mark.parametrize(
    ("clique", "pedaco"),
    [
        ({"lado": "e"}, "dentro da coluna"),
        ({"lado": "x", "uniq": UNIQ}, "esquerdo ou"),
    ],
)
def test_a_recusa_fala_com_quem_tem_o_controle_na_mao(
    clique: dict[str, Any], pedaco: str
) -> None:
    """`RuntimeError` leva a frase ao cartão dela; `ValueError` fica no `stderr`.

    É o contrato do piloto (`hefesto_vivo._recusou_dizendo`), e as duas recusas
    deste gesto são sobre um gesto DELA — as duas têm de chegar aos olhos dela.
    """
    gesto = pacotes.gesto_da_pagina("05-vibracao.html", "lado")
    assert gesto is not None
    with pytest.raises(RuntimeError) as erro:
        gesto(_ctx(100, 100), clique, _Ponte())
    assert pedaco in str(erro.value)
