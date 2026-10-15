#!/usr/bin/env python3
"""Os ESTILOS DE JOGO: um atalho que ajusta gatilho, vibração e luz de uma vez.

A DECISÃO DE CONSTRUIR É DO USUÁRIO, 03/09/2026: o `<select>` de quinze opções estava
desenhado na aba Perfis — *o campo mais aceso do painel* — e não tinha nada
atrás. Perguntada se o motor devia existir, ela respondeu **"Construir o
motor"**, e escolheu o alcance: **gatilho + vibração + luz**.

A REGRA QUE MANDA NA COR, e é do usuário, verbatim
=================================================

    *"nenhuma cor dos controles nunca pode ser a mesma, mesmo no mesmo perfil e
    estilo de jogo. Dentro da paleta de fps tem que ter variações pra cada
    unidade de controle."*

**Isso não é preferência estética — é ENDEREÇO.** A barra de luz é a única
maneira de saber, olhando para a mesa, qual controle é qual. Duas unidades com a
mesma cor apagam essa informação, e apagam-na justamente quando ela mais importa:
com quatro controles ligados.

E A REGRA PEGA UM DEFEITO VIVO. Medido no perfil do usuário em 03/09/2026: a seção
GLOBAL do perfil guarda **uma** cor (`leds.lightbar`), e com
``auto_player_colors`` desligado os quatro controles a recebem — os quatro
iguais. O `auto_player_colors` é o que a impede hoje, e ele é um interruptor que
alguém pode desligar sem perceber o que perde.

**Então o estilo nunca escolhe UMA cor: escolhe uma FAMÍLIA**, e cada unidade
recebe uma variação dela. É a leitura literal do que o usuário pediu — *"dentro da
paleta de fps tem que ter variações pra cada unidade"*.

COMO AS QUATRO VARIAÇÕES NASCEM, e por que não são digitadas
--------------------------------------------------------------
Quatro cores por estilo, escritas à mão, seriam dezenas de lugares
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
os quatro ficam iguais — o que a regra de produto proíbe. A leitura que fica: brilho
MÍNIMO com as quatro cores distintas. Gasta quase nada e a mesa continua
legível. **Se ela preferir apagada mesmo, é uma palavra e uma linha.**

O «CO-OP LOCAL» SAIU — 25/09/2026, O-CO-OP-LOCAL-SAI-01
--------------------------------------------------------
O pedido é de produto (`D-2409-O-CO-OP-LOCAL-SAI`): *"Temos que remover o perfil
coop ou modo de jogo coop que não faz sentido inclusive."* O Hefesto dá um
controle virtual a cada jogador SEMPRE, do P1 ao P4, e o co-op não é um modo
que se escolhe — um Estilo com esse nome prometia ligar o que nunca desliga.
O que ele fazia (gatilho `SimpleRigid`,
vibração `balanceado`, a família azul da paleta de jogador) não some de perfil
nenhum: até 09/10 o estilo não se guardava, e o perfil que o recebeu guarda
os três ajustes como valores. A régua que impede a volta é
`tests/unit/test_o_co_op_local_saiu.py`.

A RECEITA INVISÍVEL — 08/10/2026, O-ESTILO-DO-JOGO-LIGA-A-IMERSAO-INTEIRA-EM-TODO-MODO-01
------------------------------------------------------------------------------------------
A escolha do usuário (ESCOLHAS de 08/10): nenhum cartão novo, o «Estilo de Jogo» é o
veículo, e cada estilo leva as variáveis que a tela não mostra. Exemplo dela:
*«É terror. (...) A cor do lightbar fica piscando a vibrção fina funciona se
apertar o botão da arma de fogo (...) o dualsense vibra mais alto por default e
por tempo x.»* <!-- noqa-acento: citação literal -->
Duas variáveis o gesto aplica no perfil (:data:`APLICADAS`): o ritmo e a
frequência do gatilho (os parâmetros de `trigger_specs.PRESETS`) e o modo (o
Point-and-click liga a Navegação, pela seção `mode` do perfil). As outras
(:data:`SO_DADO`) não se escrevem no perfil: desde 09/10
(O-ESTILO-DO-PERFIL-LIGA-O-MOTOR-DO-TATO-01) o perfil guarda a CHAVE do estilo
(`Profile.estilo`), e o motor do tato vivo lê o toque, o lado e a luz daqui,
pela tradução `daemon/subsystems/tato_vivo.receita_do_estilo`. Todo número vem
de fonte pública, citada na linha; o que é escolha de produto diz «escolha»,
e é valor de partida.
"""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from typing import Literal

RGB = tuple[int, int, int]

DISTANCIA_MINIMA = 90

GIRO_DE_MATIZ = 0.055

PASSO_DE_LUZ = 0.13


#: Fontes das receitas (públicas; nada descompilado):
#: [SONY] as faixas do header da Sony redistribuído no Steamworks SDK ≥ 1.55
#:        (`docs/protocol/dualsense-referencia-canonica.md` §1.1);
#: [NIELK1] o gist do Nielk1 sobre os gatilhos (mesma página, «Fontes»);
#: [WCAG] WCAG 2.1, critério 2.3.1: no máximo três clarões por segundo;
#: [RESPIRO] a patente pública US 6,658,577 (luz que «respira» a 12 por minuto);
#: [MDN] o exemplo do `GamepadHapticActuator.playEffect("dual-rumble")` na MDN:
#:       `duration: 200` ms.
RESPIRA_POR_SEGUNDO = 0.2  # [RESPIRO] 12 por minuto
TETO_DO_PISCAR = 3.0  # [WCAG] 2.3.1
DURACAO_DE_SEMPRE_MS = 200  # [MDN]

LuzQueReage = Literal["parada", "respira", "pisca"]


@dataclass(frozen=True)
class Receita:
    """As variáveis que a tela não mostra: o que cada canal faz no estilo."""

    #: o ritmo e a frequência do gatilho: `{parâmetro: valor}` do modo do estilo
    ajustes_do_gatilho: tuple[tuple[str, int], ...] = ()
    #: como a luz reage, e quantas vezes por segundo
    luz: LuzQueReage = "parada"
    luz_por_segundo: float = 0.0
    #: quanto dura a vibração de um evento (a força é o degrau `Estilo.vibracao`)
    duracao_da_vibracao_ms: int = DURACAO_DE_SEMPRE_MS
    #: a vibração fina bate a cada tiro (a borda do R2/L2 no leitor físico)
    toque_por_tiro: bool = True
    #: os motores esquerdo e direito seguem o lado do estouro no som do jogo
    lado_do_som: bool = True
    #: o modo que o estilo liga (`ProfileModeConfig.kind`); `None` tira só o `desktop`
    #: do perfil e deixa os outros modos como estão
    modo: Literal["desktop"] | None = None
    #: a tabela de botões que o estilo grava no perfil (`MOLDES`); `None` não toca na tabela
    molde: Literal["visual_novel", "so_mouse", "teclado_e_mouse"] | None = None


#: Os MOLDES da tabela de botões, para jogo de clicar: `{botão: ação}` do `Profile.button_actions`,
#: com a ação na língua de `core/acoes_de_botao.ACOES`. Só nomeiam o que sai do de fábrica; o
#: cursor, os cliques (Cruz e L2 = esquerdo, Triângulo e R2 = direito, R3 = meio) e a rolagem
#: já são o de fábrica. Os ombros e o Options saem de Alt+Tab e Super, que tiram o jogo da frente.
#: As teclas do Ren'Py: renpy.org/doc/html/keymap.html (PageUp volta o texto, Ctrl pula
#: enquanto segura, Esc abre o menu, H esconde a caixa).
MOLDES: dict[str, dict[str, str]] = {
    "visual_novel": {
        "l1": "KEY_PAGEUP",
        "r1": "KEY_LEFTCTRL",
        "options": "KEY_ESC",
        "create": "KEY_H",
    },
    "so_mouse": {
        "l1": "__NADA__",
        "r1": "__NADA__",
        "options": "__NADA__",
        "create": "__NADA__",
    },
    # o analógico esquerdo anda o personagem (o cursor sai), os gatilhos clicam e interagem
    "teclado_e_mouse": {
        "l1": "__NADA__",
        "r1": "__NADA__",
        "options": "KEY_ESC",
        "create": "__NADA__",
        "l3_direcao": "__WASD__",
        "r2": "KEY_E",
        "square": "BTN_RIGHT",
    },
}


#: as variáveis que o gesto do estilo aplica no perfil, por motor que já existe
APLICADAS = ("ajustes_do_gatilho", "modo", "molde")
#: as que ficam aqui, como dado: o motor do tato lê pelo estilo guardado no perfil
SO_DADO = ("luz", "luz_por_segundo", "duracao_da_vibracao_ms", "toque_por_tiro",
           "lado_do_som")


def _respira(ajustes: tuple[tuple[str, int], ...] = ()) -> Receita:
    """A luz que respira no tiro [RESPIRO]; o resto, o de sempre."""
    return Receita(ajustes, luz="respira", luz_por_segundo=RESPIRA_POR_SEGUNDO)


@dataclass(frozen=True)
class Estilo:
    """Uma receita: o que o estilo faz no gatilho, na vibração e na luz."""

    chave: str
    rotulo: str
    gatilho: str | None
    vibracao: str
    familia: RGB
    brilho: float
    porque: str
    receita_invisivel: Receita | None = None


ESTILOS: tuple[Estilo, ...] = (
    Estilo("fps", "FPS", "AutoGun", "max", (255, 40, 40), 1.0,
           "o gatilho estala em rajada, que é o gesto do gênero",
           # frequência: o padrão do produto, na faixa de 0 a 255 Hz [SONY]
           _respira((("frequency", 60),))),
    Estilo("corrida", "Corrida", "Resistance", "balanceado", (255, 140, 0), 1.0,
           "o acelerador tem peso constante; o freio também",
           Receita()),
    Estilo("acao", "Ação", "Weapon", "max", (170, 60, 255), 1.0,  # noqa-acento: chave
           "trava, solta no estalo e fica leve — o golpe",
           _respira()),
    # o «Arco» era um jeito da Ação no desenho e virou estilo (ESCOLHAS de 08/10)
    Estilo("arco", "Arco", "Bow", "balanceado", (200, 160, 80), 1.0,
           "a corda tensiona com o curso e solta no disparo",
           # tensão e disparo: o padrão do produto, nas faixas de 0 a 8 [NIELK1]
           _respira((("force", 6), ("snap", 7)))),
    Estilo("aventura", "Aventura", "Feedback", "balanceado", (40, 200, 90), 1.0,
           "um ponto de resistência que marca a ação, sem cansar",
           Receita()),
    Estilo("esportes", "Esportes", "SimpleRigid", "balanceado", (40, 120, 255), 1.0,
           "curso curto e previsível; o gatilho não conta história",
           Receita()),
    Estilo("point_and_click", "Point-and-click", "Off", "economia", (0, 200, 210), 1.0,
           "o gatilho não é usado; vibração baixa não distrai a leitura",
           # a Navegação é escolha do usuário (ESCOLHAS de 08/10); o toque e o lado também
           Receita(modo="desktop", molde="so_mouse")),
    Estilo("visual_novel", "Visual novel", "Off", "economia", (0, 200, 210), 0.5,
           "o texto é longo e a luz não disputa a leitura; os ombros voltam, pulam e abrem o menu",
           # a família do Point-and-click, parada e a meia luz; o gatilho é clique, sem efeito
           Receita(modo="desktop", molde="visual_novel")),
    Estilo("terror", "Terror", "PulseB", "max", (215, 30, 55), 0.7,
           "o pulso irregular é o susto no dedo; a luz baixa não denuncia",
           # pisca abaixo do teto [WCAG]; a vibração dura o dobro [MDN] (escolha)
           Receita(luz="pisca", luz_por_segundo=2.0,
                   duracao_da_vibracao_ms=2 * DURACAO_DE_SEMPRE_MS)),
    Estilo("luta", "Luta", "SemiAutoGun", "max", (255, 40, 180), 1.0,
           "um estalo por golpe, com volta rápida",
           _respira()),
    Estilo("maratona", "Maratona", "Off", "economia", (120, 120, 140), 0.25,
           "a sessão é longa: tudo que gasta bateria cai ao mínimo — mas a luz "
           "NÃO apaga, porque apagada os quatro ficariam iguais",
           Receita()),
    Estilo("plataforma", "Plataforma", "Off", "balanceado", (255, 210, 40), 1.0,
           "o pulo é botão, não gatilho; a vibração marca o impacto",
           Receita()),
    Estilo("retro", "Retrô/Emulador", "Off", "economia", (60, 230, 90), 1.0,
           "o console original não tinha nada disso; o verde é o do tubo",
           Receita()),
    Estilo("ritmo", "Ritmo/Música", "Off", "max", (255, 0, 220), 1.0,
           "a vibração É o instrumento; o gatilho atrapalha o tempo",
           # a luz no compasso, até o teto [WCAG]
           Receita(luz="respira", luz_por_segundo=TETO_DO_PISCAR)),
    Estilo("simulacao", "Simulação/Voo", "SlopeFeedback", "economia", (90, 180, 255), 1.0,
           "o manche endurece com o curso, e o voo é longo",
           Receita()),
    Estilo("personalizado", "Personalizado", None, "", (0, 0, 0), 0.0,
           "é o estilo que diz 'eu ajusto na mão' — não mexe em nada"),
)

POR_CHAVE = {e.chave: e for e in ESTILOS}
POR_ROTULO = {e.rotulo: e for e in ESTILOS}

DE_FABRICA: tuple[Estilo, ...] = tuple(e for e in ESTILOS if e.chave != "personalizado")


def _distancia(a: RGB, b: RGB) -> int:
    """|ΔR| + |ΔG| + |ΔB| — a conta grosseira, e ela é a honesta aqui."""
    return sum(abs(x - y) for x, y in zip(a, b, strict=True))


def _variar(base: RGB, passo: int, escala: float) -> RGB:
    """A cor da unidade `passo` (0..3) dentro da família de `base`."""
    r, g, b = (c / 255 for c in base)
    h, luz, s = colorsys.rgb_to_hls(r, g, b)
    lado = (passo - 1.5)
    h = (h + GIRO_DE_MATIZ * lado * escala) % 1.0
    luz = min(0.92, max(0.18, luz + PASSO_DE_LUZ * lado * escala))
    s = min(1.0, max(0.25, s))
    return tuple(round(c * 255) for c in colorsys.hls_to_rgb(h, luz, s))  # type: ignore[return-value]


ESCALA_MAXIMA = 2.6


def as_quatro(estilo: str | Estilo) -> tuple[RGB, RGB, RGB, RGB]:
    """As quatro cores daquele estilo, uma por unidade — e nunca duas iguais."""
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
