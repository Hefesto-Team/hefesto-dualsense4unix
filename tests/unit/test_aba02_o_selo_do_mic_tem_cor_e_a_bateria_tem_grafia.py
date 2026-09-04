#!/usr/bin/env python3
"""AS DUAS DECISÕES DELA DE 03/09/2026 na aba Controles.

**1. O SELO DO MICROFONE GANHA COR + ÍCONE.** *"Cor + ícone. Redundante de
propósito — quem lê rápido pega pela cor, quem não distingue cor pega pelo
risco."*

O DEFEITO, medido no DOM VIVO com o daemon ligado
(`scripts/ensaios/o_selo_do_mic_muda_de_cor.py`, na página PUBLICADA): a palavra
mudava e a cor não. Injetando os três valores do selo, o fundo de cada card
ficava congelado no que o gerador desenhou —

    P1  MUDO -> rgb(80, 250, 123)   ATIVO -> rgb(80, 250, 123)   — -> rgb(80, 250, 123)
    P2  MUDO -> rgb(68, 71, 90)     ATIVO -> rgb(68, 71, 90)     — -> rgb(68, 71, 90)

— o P1 dizia MUDO em VERDE e o P2 dizia ATIVO em CINZA. A causa é estrutural:
`escrever()` do piloto tem **UM alvo por elemento**, o padrão é o texto, e o
`<span>` carregava a palavra e a classe ao mesmo tempo.

**2. A BATERIA DESCONHECIDA VOLTA A `— %`.** *"— %, como a janela antiga"* —
paridade literal com a GTK, contra a harmonia interna do card. É dela.

AS MORDIDAS que estas réguas pegam, e as três foram feitas:

* junte os três `<span>` do selo num só — `test_o_selo_tem_tres_alvos` reprova;
* troque `data-hef-quando` por um literal digitado que divirja do dono —
  `test_o_quando_do_selo_vem_do_dono` reprova;
* faça `texto_da_bateria` redigitar a `f-string` da GTK —
  `test_a_bateria_pergunta_a_grafia_a_gtk` reprova.

O QUE ESTAS RÉGUAS **NÃO** MEDEM, de propósito: a cor em pixel e o risco
desenhado. Isso é `getComputedStyle` num motor de verdade, e quem faz é o ensaio
acima — este arquivo lê o HTML no disco, e HTML no disco não tem cor computada.
"""
from __future__ import annotations

import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

import pytest

from hefesto_dualsense4unix.interface import mesa_viva, onde

PAGINA = "02-controles.html"  # (noqa-acento) nome de arquivo

UNIQ = "aa:bb:cc:00:00:02"
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "cosmic-red", "mascara": "DualSense"}]


def _card(mod, contexto, entrada: dict) -> dict:
    """O ÚNICO card que o pacote monta para esta entrada.

    A chave de `cards` é o `uniq`, e não a posição — quem traduz para `p1` é o
    piloto. A régua tira o único valor em vez de digitar a chave: normalizar o
    `uniq` é do produto, e uma régua que digite a forma dele reprova no dia em
    que a normalização mudar.
    """
    cards = mod.pacote(contexto(state={"controllers": [entrada]},
                                mesa=MESA, conectados=[entrada]))["cards"]
    assert len(cards) == 1, f"esperava um card, vieram {len(cards)}"
    return next(iter(cards.values()))


def _bancada() -> str:
    return onde.pagina(PAGINA).read_text(encoding="utf-8")


def _selos(doc: str) -> list[str]:
    """Cada `<span class="selo-ativo…">` inteiro, até o `</span>` que o fecha.

    Conta profundidade em vez de casar um `</span>` qualquer: o selo tem dois
    filhos `<span>`, e uma expressão preguiçosa pararia no primeiro fecho.
    """
    fora = []
    for abre in re.finditer(r'<span class="selo-ativo[^"]*"', doc):
        i, nivel = abre.start(), 0
        for marca in re.finditer(r"<span\b|</span>", doc[abre.start():]):
            nivel += 1 if marca.group(0) == "<span" else -1
            if nivel == 0:
                fora.append(doc[i:abre.start() + marca.end()])
                break
    return fora


# ---------------------------------------------------------------------------
# 1. O selo — três elementos, um endereço, três alvos
# ---------------------------------------------------------------------------


def test_o_selo_tem_tres_alvos() -> None:
    """A cor, o risco e a palavra são TRÊS alvos, e um elemento aceita UM.

    A régua não conta elementos: ela cobra os três ALVOS que o
    `hefesto_vivo.escrever` sabe distinguir, todos sob o mesmo `data-campo`.
    `achar()` visita todos os elementos de mesmo endereço com o mesmo valor e
    cada um decide por si — é o mecanismo que o próprio `escrever` documenta.

    MORDE: junte os três `<span>` num só (que é como o produto está publicado
    hoje) e o selo volta a ter um alvo — a palavra —, com a cor congelada no que
    o gerador desenhou.
    """
    selos = _selos(_bancada())
    assert selos, "não achei um `.selo-ativo` na bancada da aba Controles"

    for selo in selos:
        enderecos = selo.count('data-campo="mic-selo"')
        assert enderecos == 3, (
            f"o selo tem {enderecos} endereço(s) e precisa de 3 — a cor, o "
            f"risco e a palavra. Achado: {selo[:160]}"
        )
        # A COR: o próprio selo acende a classe `on`.
        assert 'data-hef-alvo="classe" data-hef-classe="on"' in selo, (
            "o selo perdeu o alvo da COR. Sem ele o tique só troca a palavra, "
            "e o fundo fica no que o gerador desenhou — o defeito de 03/09."
        )
        # O RISCO: o glifo acende a classe `cortado`.
        assert 'data-hef-alvo="classe" data-hef-classe="cortado"' in selo, (
            "o selo perdeu o alvo do RISCO. Ela escolheu 'Cor + ícone' de "
            "propósito, para quem não distingue cor."
        )
        # A PALAVRA: o alvo PADRÃO, que é o texto — logo, sem `data-hef-alvo`.
        palavra = re.search(r'<span class="selo-palavra"([^>]*)>', selo)
        assert palavra is not None, "o selo perdeu o `<span>` da palavra"
        assert "data-hef-alvo" not in palavra.group(1), (
            "o `<span>` da palavra ganhou um alvo — ele tem de ficar no alvo "
            "PADRÃO (o texto), senão a palavra para de ser escrita."
        )


def test_o_quando_do_selo_vem_do_dono() -> None:
    """O valor que acende cada classe é o que `mesa_viva.selo_do_mic` devolve.

    RÉGUA PERGUNTA, NUNCA DIGITA — a lição que esta casa pagou seis vezes em
    03/09. Se o `data-hef-quando` fosse um literal digitado no gerador, o dia em
    que a palavra mudasse no dono ele deixaria de casar e a cor congelaria de
    novo, **calada**. É a mesma armadilha da rota por CSS
    (`.selo-ativo[data-mic="MUDO"]`), e a razão de ela ter sido recusada.

    MORDE: troque o `data-hef-quando` de qualquer um dos dois por outra palavra.
    """
    doc = _bancada()
    for selo in _selos(doc):
        for classe, esperado in (("on", mesa_viva.selo_do_mic(False, True)),
                                 ("cortado", mesa_viva.selo_do_mic(True, True))):
            achado = re.search(
                rf'data-hef-classe="{classe}" data-hef-quando="([^"]*)"', selo)
            assert achado is not None, f"o selo não declara quando `{classe}` acende"
            assert achado.group(1) == esperado, (
                f"`{classe}` acende em {achado.group(1)!r} e o dono do selo diz "
                f"{esperado!r} — a régua e o produto discordam, e quem pinta é o "
                "produto"
            )


def test_o_verde_quer_dizer_uma_coisa_so() -> None:
    """Só ATIVO acende. MUDO e o travessão ficam apagados.

    POR QUE A INVERSÃO IMPORTA: com a classe acesa no MUDO, o TERCEIRO estado —
    o travessão de `selo_do_mic(_, sabemos=False)` — cairia no ramo de baixo e
    ficaria VERDE. Um microfone que ninguém leu anunciando que captura é
    exatamente o defeito que aquela função existe para matar
    (`test_o_selo_do_mic_tem_tres_estados_e_um_dono_so`).

    MORDE: volte a acender no MUDO (`data-hef-quando` do `on` = MUDO). O
    travessão passa a pintar verde, e esta régua reprova pelo lado do desenho —
    o ensaio reprova pelo lado do pixel.
    """
    import aba02

    aceso = aba02.selo_do_microfone(False)
    apagado = aba02.selo_do_microfone(True)

    assert 'class="selo-ativo on"' in aceso, "o selo ATIVO não acende"
    assert 'class="selo-ativo"' in apagado and ' on"' not in apagado, (
        "o selo MUDO ficou aceso — verde tem de querer dizer UMA coisa só"
    )
    assert "cortado" in apagado, "o MUDO perdeu o risco sobre o microfone"
    assert "cortado" not in aceso.split("data-hef-classe")[1], (
        "o ATIVO nasceu com o risco aceso"
    )
    # E O QUE NÃO É ATIVO NÃO ACENDE, incluindo o travessão: o único valor no
    # `data-hef-quando` do `on` é o ATIVO, então qualquer outro apaga.
    assert f'data-hef-classe="on" data-hef-quando="{mesa_viva.selo_do_mic(False, True)}"' \
        in aceso


def test_a_folha_pinta_as_duas_classes() -> None:
    """As classes que o produto acende existem no CSS da página.

    Um alvo `classe` sem regra de CSS é uma pintura que ninguém vê: o piloto
    escreveria a classe a cada tique e o pixel não mudaria. É o gêmeo do
    endereço órfão, do outro lado.

    MORDE: apague `.selo-ativo.on` ou `.mic-glifo.cortado::after` do gerador.
    """
    doc = _bancada()
    assert ".selo-ativo.on{" in doc, (
        "a regra que ACENDE o selo sumiu — a classe seria escrita e o fundo "
        "ficaria apagado nos três estados"
    )
    assert ".mic-glifo.cortado::after{" in doc, (
        "a regra do RISCO sumiu — o glifo ganharia a classe e nada cruzaria o "
        "microfone, que é a metade da escolha dela para quem não distingue cor"
    )
    assert ".mic-glifo{" in doc and "position:relative" in doc, (
        "o glifo perdeu o `position:relative` — o `::after` do risco é absoluto "
        "e passaria a se posicionar contra outro ancestral"
    )


def test_o_selo_nao_e_escrito_a_mao_em_dois_lugares() -> None:
    """Um dono só para o selo no gerador — `aba02.selo_do_microfone`.

    O selo aparece DUAS vezes por controle: a linha fechada e o card aberto. Foi
    escrito à mão nos dois, e foi assim que a cor congelou — curar um lugar
    deixaria a outra metade viva, que é o defeito que a regra da casa mata.

    A régua lê o BYTECODE, não o texto: o comentário do gerador cita "ATIVO" com
    todas as letras para explicar o defeito, e uma régua de substring reprovaria
    justamente porque alguém escreveu bem.

    MORDE: reescreva o `<span class="selo-ativo…">` dentro de `resumo_fechado`
    ou de `bloco`.
    """
    import aba02

    for alvo, nome in ((aba02.resumo_fechado, "resumo_fechado"),
                       (aba02.bloco, "bloco")):
        codigo = alvo.__code__
        assert "selo_do_microfone" in codigo.co_names, (
            f"`{nome}` não chama o dono do selo"
        )
        literais = {c for c in codigo.co_consts if isinstance(c, str)}
        literais.discard(alvo.__doc__)
        assert not any("selo-ativo" in c for c in literais), (
            f"`{nome}` voltou a montar o selo por conta própria — duas versões "
            "vivas do mesmo desenho é como a cor congelou"
        )


# ---------------------------------------------------------------------------
# 2. A bateria desconhecida — `— %`, e a grafia é PERGUNTADA
# ---------------------------------------------------------------------------


def test_a_bateria_pergunta_a_grafia_a_gtk() -> None:
    """As duas frases da carga saem da GTK, não de uma cópia daqui.

    O comentário que morava nesta linha afirmava *"NÃO HÁ FUNÇÃO DONA PARA
    IMPORTAR"*. É falso, e o fato foi substituído:
    `StatusActionsMixin._bateria_da_mesa` é `@staticmethod`, devolve
    `(fração, texto)` e não toca em widget nenhum.

    MORDE: faça `texto_da_bateria` redigitar a `f-string` em vez de chamar o
    dono — esta régua reprova no dia em que a GTK mudar a grafia, que é
    exatamente quando ela tem de reprovar.
    """
    from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
    from pacotes.a02_controles import texto_da_bateria

    assert texto_da_bateria(None) == StatusActionsMixin._bateria_da_mesa({})[1]
    for pct in (0, 1, 42, 85, 100):
        assert texto_da_bateria(pct) == StatusActionsMixin._bateria_da_mesa(
            {"battery_pct": pct})[1], f"a carga {pct} saiu fora da grafia da GTK"


def test_a_bateria_desconhecida_e_travessao_com_porcento() -> None:
    """Decisão dela: `— %`, como a janela antiga. Paridade literal.

    O QUE CADUCOU: em 02/09 esta linha passou a devolver o travessão SECO, pela
    regra de *campo sem informação não mostra nada*. Ela decidiu o contrário em
    03/09 — a paridade com a janela que ela usa vence a harmonia interna do
    card —, e a decisão é dela.

    MORDE: volte a `mesa_viva.SEM_LEITOR` e esta régua reprova; o `%` some da
    tela dela e o card deixa de casar com a janela antiga.
    """
    from pacotes.a02_controles import texto_da_bateria

    seco = str(mesa_viva.SEM_LEITOR)
    assert texto_da_bateria(None) != seco, (
        "a bateria desconhecida voltou ao travessão seco — ela pediu `— %`"
    )
    assert texto_da_bateria(None).startswith(seco), (
        "a frase do desconhecido deixou de começar pelo travessão"
    )
    assert texto_da_bateria(None).endswith("%")


def test_o_card_emite_a_carga_desconhecida_com_porcento() -> None:
    """E ela chega ao CARD, não só à função — o valor que o tique pinta.

    MORDE: desligue a chamada em `pacote()` (volte o literal). O campo `bateria`
    do card volta ao travessão seco e esta régua reprova.
    """
    from pacotes import Contexto
    from pacotes import a02_controles as mod

    sem_carga = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
                 "battery_pct": None, "is_primary": True, "inputs": {},
                 "audio": {}, "speaker": {}}
    com_carga = dict(sem_carga, battery_pct=85)

    for entrada, esperado in ((sem_carga, "— %"), (com_carga, "85 %")):
        assert _card(mod, Contexto, entrada)["bateria"] == esperado, (
            f"o card emitiu {_card(mod, Contexto, entrada)['bateria']!r} e a "
            f"janela antiga escreve {esperado!r}"
        )


@pytest.mark.parametrize("mudo", [True, False])
def test_o_selo_do_card_continua_saindo_do_dono(mudo: bool) -> None:
    """A palavra que o tique pinta é a do dono — a cura não mexeu nisso.

    Esta régua existe porque a frente do selo tocou o GERADOR e o PACOTE no
    mesmo dia: sem ela, um erro no pacote passaria escondido atrás do desenho
    novo, que é bonito e não pinta nada sozinho.
    """
    from pacotes import Contexto
    from pacotes import a02_controles as mod

    entrada = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
               "battery_pct": 50, "is_primary": True, "inputs": {},
               "audio": {"mic_mudo": mudo}, "speaker": {}}
    assert _card(mod, Contexto, entrada)["mic-selo"] == mesa_viva.selo_do_mic(
        mudo, True)
