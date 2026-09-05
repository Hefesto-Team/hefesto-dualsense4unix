#!/usr/bin/env python3
"""Os ESTILOS DE JOGO: um atalho que ajusta gatilho, vibração e luz de uma vez.

A DECISÃO DE CONSTRUIR É DELA, 03/09/2026: o `<select>` de quinze opções estava
desenhado na aba Perfis — *o campo mais aceso do painel* — e não tinha nada
atrás. Perguntada se o motor devia existir, ela respondeu **"Construir o
motor"**, e escolheu o alcance: **gatilho + vibração + luz**.

A REGRA QUE MANDA NA COR, e ela é dela, verbatim
=================================================

    *"nenhuma cor dos controles nunca pode ser a mesma, mesmo no mesmo perfil e
    estilo de jogo. Dentro da paleta de fps tem que ter variações pra cada
    unidade de controle."*

**Isso não é preferência estética — é ENDEREÇO.** A barra de luz é a única
maneira de saber, olhando para a mesa, qual controle é qual. Duas unidades com a
mesma cor apagam essa informação, e apagam-na justamente quando ela mais importa:
com quatro controles ligados.

E A REGRA PEGA UM DEFEITO VIVO. Medido no perfil dela em 03/09/2026: a seção
GLOBAL do perfil guarda **uma** cor (`leds.lightbar`), e com
``auto_player_colors`` desligado os quatro controles a recebem — os quatro
iguais. O `auto_player_colors` é o que a impede hoje, e ele é um interruptor que
alguém pode desligar sem perceber o que perde.

**Então o estilo nunca escolhe UMA cor: escolhe uma FAMÍLIA**, e cada unidade
recebe uma variação dela. É a leitura literal do que ela pediu — *"dentro da
paleta de fps tem que ter variações pra cada unidade"*.

COMO AS QUATRO VARIAÇÕES NASCEM, e por que não são digitadas
--------------------------------------------------------------
Sessenta cores escritas à mão (15 estilos x 4 unidades) seriam sessenta lugares
para envelhecer, e ninguém conferiria se duas colidem. Elas são DERIVADAS de uma
cor-família por rotação de matiz e passo de luminância — e :func:`as_quatro`
garante, medindo, que as quatro saem distinguíveis.

A distância mínima é em ``ΔRGB`` simples e não em CIELAB de propósito: o alvo é
um LED difuso atrás de plástico leitoso, não uma tela calibrada. O que se quer é
*"dá para dizer que são diferentes do outro lado do sofá"*, e para isso a conta
grosseira é a honesta — uma métrica fina prometeria uma precisão que o aparelho
não entrega.

A MARATONA É A ÚNICA EXCEÇÃO À COR, E NÃO À REGRA
--------------------------------------------------
Ela pede economia de bateria, e a proposta original era a luz APAGADA. Apagada,
os quatro ficam iguais — o que a regra dela proíbe. A leitura que fica: brilho
MÍNIMO com as quatro cores distintas. Gasta quase nada e a mesa continua
legível. **Se ela preferir apagada mesmo, é uma palavra e uma linha.**
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass

RGB = tuple[int, int, int]

#: A DISTÂNCIA MÍNIMA entre duas cores da mesma paleta, em soma de |ΔR|+|ΔG|+|ΔB|.
#: 90 foi medido contra a paleta canônica de jogador (`led_control`), cujas
#: vizinhas mais próximas — azul e roxo — distam 128. Um piso abaixo do que a
#: casa já considera distinguível seria inventar tolerância.
DISTANCIA_MINIMA = 90

#: QUANTO O MATIZ GIRA entre uma unidade e a seguinte, em voltas. 0.055 é ~20°:
#: o bastante para separar, pouco para a família continuar reconhecível como
#: "o vermelho do FPS".
GIRO_DE_MATIZ = 0.055

#: E O PASSO DE LUMINÂNCIA, que é a segunda dimensão. Só o matiz não bastaria
#: para as famílias quase acromáticas (o branco do Retrô, o cinza), onde girar
#: matiz não muda quase nada.
PASSO_DE_LUZ = 0.13


@dataclass(frozen=True)
class Estilo:
    """Uma receita: o que o estilo faz no gatilho, na vibração e na luz.

    `gatilho` é a CHAVE do modo (`AutoGun`, `Resistance`…), a mesma que a aba
    Gatilhos oferece — nunca o rótulo, que é texto de tela e muda.
    `vibracao` é o degrau (`economia`/`balanceado`/`max`), e `familia` é a cor
    de onde as quatro variações saem.
    """

    chave: str
    rotulo: str
    gatilho: str | None
    vibracao: str
    familia: RGB
    brilho: float
    porque: str


#: AS QUINZE RECEITAS, propostas por mim e APROVADAS por ela em 03/09/2026 —
#: *"o resto ta aprovado"* —, com a emenda da cor que esta docstring abre.
#:
#: A REGRA QUE GEROU A COLUNA DO GATILHO: o efeito descreve a RESISTÊNCIA que o
#: gênero pede no dedo, não o clima do jogo. `None` = não mexe no gatilho.
ESTILOS: tuple[Estilo, ...] = (
    Estilo("fps", "FPS", "AutoGun", "max", (255, 40, 40), 1.0,
           "o gatilho estala em rajada, que é o gesto do gênero"),
    Estilo("corrida", "Corrida", "Resistance", "balanceado", (255, 140, 0), 1.0,
           "o acelerador tem peso constante; o freio também"),
    # A CHAVE VAI SEM ACENTO de propósito — chave de contrato não leva; quem
    # carrega a palavra dela é o rótulo ao lado.
    Estilo("acao", "Ação", "Weapon", "max", (170, 60, 255), 1.0,  # noqa-acento: chave
           "trava, solta no estalo e fica leve — o golpe"),
    Estilo("aventura", "Aventura", "Feedback", "balanceado", (40, 200, 90), 1.0,
           "um ponto de resistência que marca a ação, sem cansar"),
    Estilo("esportes", "Esportes", "SimpleRigid", "balanceado", (40, 120, 255), 1.0,
           "curso curto e previsível; o gatilho não conta história"),
    Estilo("point_and_click", "Point-and-click", "Off", "economia", (0, 200, 210), 1.0,
           "o gatilho não é usado; vibração baixa não distrai a leitura"),
    # A FAMÍLIA DO TERROR MUDOU PORQUE A RÉGUA REPROVOU A PRIMEIRA. Era
    # `(150, 20, 30)`, um vinho escuro, e as quatro unidades saíam a 61 de
    # distância — abaixo do mínimo. Escuro não rende quatro: o espaço de
    # luminância abaixo do meio é estreito. O clima escuro continua, e vem do
    # `brilho` 0.7, que é o lugar certo dele.
    Estilo("terror", "Terror", "PulseB", "max", (215, 30, 55), 0.7,
           "o pulso irregular é o susto no dedo; a luz baixa não denuncia"),
    Estilo("luta", "Luta", "SemiAutoGun", "max", (255, 40, 180), 1.0,
           "um estalo por golpe, com volta rápida"),
    Estilo("coop", "Co-op local", "SimpleRigid", "balanceado", (0, 0, 255), 1.0,
           "quatro na mesa: a família é a paleta canônica de jogador, que é a "
           "que ela já conhece de olhar"),
    Estilo("maratona", "Maratona", "Off", "economia", (120, 120, 140), 0.25,
           "a sessão é longa: tudo que gasta bateria cai ao mínimo — mas a luz "
           "NÃO apaga, porque apagada os quatro ficariam iguais"),
    Estilo("plataforma", "Plataforma", "Off", "balanceado", (255, 210, 40), 1.0,
           "o pulo é botão, não gatilho; a vibração marca o impacto"),
    # E A DO RETRÔ FOI O CASO QUE MAIS ENSINOU: era `(230, 230, 235)`, quase
    # branco, e a régua devolveu as quatro a **9** de distância. Branco não tem
    # matiz para girar nem saturação para variar — ele não rende quatro cores
    # distintas por construção, e nenhuma abertura de família conserta isso.
    # O verde-fósforo do monitor de tubo é mais temático que o branco E rende.
    #
    # COLIDIR COM A FAMÍLIA DA AVENTURA É ACEITÁVEL, e vale dizer por quê: a
    # regra dela é sobre DUAS UNIDADES NA MESMA MESA ao mesmo tempo, não sobre
    # dois estilos que nunca convivem — um perfil tem um estilo só.
    Estilo("retro", "Retrô/Emulador", "Off", "economia", (60, 230, 90), 1.0,
           "o console original não tinha nada disso; o verde é o do tubo"),
    Estilo("ritmo", "Ritmo/Música", "Off", "max", (255, 0, 220), 1.0,
           "a vibração É o instrumento; o gatilho atrapalha o tempo"),
    Estilo("simulacao", "Simulação/Voo", "SlopeFeedback", "economia", (90, 180, 255), 1.0,
           "o manche endurece com o curso, e o voo é longo"),
    Estilo("personalizado", "Personalizado", None, "", (0, 0, 0), 0.0,
           "é o estilo que diz 'eu ajusto na mão' — não mexe em nada"),
)

POR_CHAVE = {e.chave: e for e in ESTILOS}
POR_ROTULO = {e.rotulo: e for e in ESTILOS}


def _distancia(a: RGB, b: RGB) -> int:
    """|ΔR| + |ΔG| + |ΔB| — a conta grosseira, e ela é a honesta aqui.

    Ver a docstring do módulo: o alvo é um LED difuso atrás de plástico, e uma
    métrica perceptual prometeria precisão que o aparelho não entrega.
    """
    return sum(abs(x - y) for x, y in zip(a, b, strict=True))


def _variar(base: RGB, passo: int, escala: float) -> RGB:
    """A cor da unidade `passo` (0..3) dentro da família de `base`.

    DOIS EIXOS, e os dois são precisos. O matiz gira em torno da família —
    SIMÉTRICO (`-1.5, -0.5, +0.5, +1.5` passos), para as quatro ficarem
    igualmente distantes do centro em vez de a última acabar longe da família; e
    a luminância anda em quatro degraus, porque nas famílias quase acromáticas
    (o branco do Retrô, o cinza da Maratona) girar matiz quase não muda nada.

    A PRIMEIRA VERSÃO GIRAVA SÓ PARA FRENTE e somava luz sempre, e as duas
    coisas quebraram no mesmo minuto: a quarta unidade do FPS saía
    `(255, 254, 173)` — um amarelo-claro que ninguém chamaria de "o vermelho do
    FPS" — e o Esportes colidia nas unidades 1 e 2 a 73 de distância. A régua
    pegou os dois, que é para isso que ela existe.
    """
    r, g, b = (c / 255 for c in base)
    h, luz, s = colorsys.rgb_to_hls(r, g, b)
    lado = (passo - 1.5)          # -1.5, -0.5, +0.5, +1.5
    h = (h + GIRO_DE_MATIZ * lado * escala) % 1.0
    # A LUZ RESPEITA O TETO E O PISO: acima de 0.92 tudo vira branco e as
    # famílias colidem entre si; abaixo de 0.18 o LED difuso não distingue.
    luz = min(0.92, max(0.18, luz + PASSO_DE_LUZ * lado * escala))
    # E A SATURAÇÃO ACOMPANHA, para a família não se dissolver quando a luz sobe.
    s = min(1.0, max(0.25, s))
    return tuple(round(c * 255) for c in colorsys.hls_to_rgb(h, luz, s))  # type: ignore[return-value]


#: ATÉ ONDE A BUSCA ABRE A FAMÍLIA. A escala 1.0 é o desenho; se duas unidades
#: colidirem, ela cresce até separar. O teto existe para a "família" não virar
#: uma volta inteira no círculo de cores — chegando aqui, é a `familia` que está
#: errada, e a régua diz isso em vez de devolver quatro cores de gêneros
#: diferentes.
ESCALA_MAXIMA = 2.6


def as_quatro(estilo: str | Estilo) -> tuple[RGB, RGB, RGB, RGB]:
    """As quatro cores daquele estilo, uma por unidade — e nunca duas iguais.

    A GARANTIA É MEDIDA, não prometida: a busca abre a família até as quatro
    ficarem a pelo menos :data:`DISTANCIA_MINIMA` umas das outras, e se nem no
    teto conseguir, LEVANTA. Devolver silenciosamente um par colidido seria a
    tela apagando a única informação que diz qual controle é qual — que é
    exatamente o que a regra dela existe para impedir.
    """
    e = estilo if isinstance(estilo, Estilo) else POR_CHAVE[str(estilo)]
    if e.chave == "personalizado":
        raise ValueError(
            "estilo 'Personalizado' não escolhe cor — ele existe para dizer "
            "'eu ajusto na mão'. Perguntar a cor dele é perguntar o que ela "
            "não delegou.")
    escala = 1.0
    while escala <= ESCALA_MAXIMA:
        cores = tuple(_variar(e.familia, i, escala) for i in range(4))
        pior = min(_distancia(cores[i], cores[j])
                   for i in range(4) for j in range(i + 1, 4))
        if pior >= DISTANCIA_MINIMA:
            return cores  # type: ignore[return-value]
        escala += 0.2
    raise ValueError(
        f"o estilo {e.rotulo!r} não separa quatro unidades nem abrindo a "
        f"família até {ESCALA_MAXIMA}x: a mais próxima fica a {pior}, e o "
        f"mínimo é {DISTANCIA_MINIMA}. A `familia` {e.familia} é escura ou "
        "dessaturada demais para render quatro — escolha outra.")


def cor_da_unidade(estilo: str | Estilo, jogador: int) -> RGB:
    """A cor daquele estilo para o jogador `1..4`."""
    if not 1 <= jogador <= 4:
        raise ValueError(f"jogador fora da mesa: {jogador} (a mesa é 1..4)")
    return as_quatro(estilo)[jogador - 1]
