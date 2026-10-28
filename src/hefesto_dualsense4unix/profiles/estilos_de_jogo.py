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
Point and click liga a Navegação, pela seção `mode` do perfil). As outras
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

from hefesto_dualsense4unix.core.ds_output_report import SAIDA_L_FONE_R_ALTO_FALANTE

RGB = tuple[int, int, int]

DISTANCIA_MINIMA = 90

GIRO_DE_MATIZ = 0.055

PASSO_DE_LUZ = 0.13


RESPIRA_POR_SEGUNDO = 0.2
TETO_DO_PISCAR = 3.0
DURACAO_DE_SEMPRE_MS = 200

LuzQueReage = Literal["parada", "respira", "pisca", "batida", "acende", "bateria"]


@dataclass(frozen=True)
class AltoFalanteDoEstilo:
    """O que o estilo diz do alto-falante do controle: a camada que duplica o som do PC.

    ``Receita.alto_falante`` é ``None`` quando o estilo não opina (o alto-falante fica com o jogo
    e com o perfil). Quem escreve é ``ProfileManager.apply_som_do_estilo``, só com o Modo
    automático da aba Controles ligado.
    """

    fonte: Literal["mix", "sfx"]
    rota: int | None = None


@dataclass(frozen=True)
class Receita:
    """As variáveis que a tela não mostra: o que cada canal faz no estilo."""

    ajustes_do_gatilho: tuple[tuple[str, int], ...] = ()
    luz: LuzQueReage = "parada"
    luz_por_segundo: float = 0.0
    duracao_da_vibracao_ms: int = DURACAO_DE_SEMPRE_MS
    toque_por_tiro: bool = True
    lado_do_som: bool = True
    som_quando_o_jogo_cala: bool = True
    rumble_no_dedo: bool = False
    modo: Literal["desktop"] | None = None
    arranjo: Literal["navegacao", "point_and_click"] | None = None
    molde: Literal["visual_novel", "teclado_e_mouse"] | None = None
    luz_base: str | None = None
    luz_ritmo: int = 0
    alto_falante: AltoFalanteDoEstilo | None = None
    microfone_ligado: bool | None = None


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


SOM_DO_PC_TAMBEM_NO_CONTROLE = AltoFalanteDoEstilo("mix", rota=SAIDA_L_FONE_R_ALTO_FALANTE)
MUSICA_SO_NO_PC = AltoFalanteDoEstilo("sfx")

MOLDE_QUE_O_ESTILO_GRAVAVA: dict[str, str] = {"point_and_click": "so_mouse"}

APLICADAS = ("ajustes_do_gatilho", "modo", "arranjo", "molde", "luz_base", "luz_ritmo")
SO_DADO = ("luz", "luz_por_segundo", "duracao_da_vibracao_ms", "toque_por_tiro",
           "lado_do_som", "som_quando_o_jogo_cala", "rumble_no_dedo", "alto_falante",
           "microfone_ligado")


def _respira(
    ajustes: tuple[tuple[str, int], ...] = (), *, rumble_no_dedo: bool = False
) -> Receita:
    """A luz que respira [RESPIRO] e pulsa no tiro; o resto, o de sempre.

    A base «respirar» a ritmo 3 dura 3,3 s (`efeitos_de_luz.periodo_do_respirar_s`): é o mais
    perto dos 3 a 4 s da página que o ritmo inteiro alcança (escolha).
    """
    return Receita(ajustes, luz="respira", luz_por_segundo=RESPIRA_POR_SEGUNDO,
                   luz_base="respirar", luz_ritmo=3, rumble_no_dedo=rumble_no_dedo)


@dataclass(frozen=True)
class Lado:
    """O que um gatilho faz no estilo: o acionamento e a imersão dele (ou `None`).

    A imersão é uma chave de `efeitos_de_imersao.IMERSOES`; sem ela valem os padrões do acionamento
    mais os `ajustes_do_gatilho` da receita. Os números que o perfil guarda são os de
    `ajustes_da_imersao(imersao, modo, estilo)`, os mesmos que a aba Gatilhos reconhece.
    """

    modo: str
    imersao: str | None = None


@dataclass(frozen=True)
class Estilo:
    """Uma receita: o que o estilo faz nos gatilhos, na vibração e na luz.

    `gatilho` é o acionamento do R2. `r2` e `l2` são os dois lados; omitidos, o lado direito é o
    acionamento sozinho e o esquerdo repete o direito (o estilo que não separa os gatilhos).
    """

    chave: str
    rotulo: str
    gatilho: str | None
    vibracao: str
    familia: RGB
    brilho: float
    porque: str
    receita_invisivel: Receita | None = None
    r2: Lado | None = None
    l2: Lado | None = None

    def __post_init__(self) -> None:
        if self.r2 is not None and self.r2.modo != self.gatilho:
            raise ValueError(
                f"o estilo {self.rotulo!r}: o R2 é {self.r2.modo!r} e o gatilho {self.gatilho!r}; "
                "`gatilho` é o acionamento do R2")
        if self.gatilho and self.r2 is None:
            object.__setattr__(self, "r2", Lado(self.gatilho))
        if self.l2 is None and self.r2 is not None:
            object.__setattr__(self, "l2", self.r2)


ESTILOS: tuple[Estilo, ...] = (
    Estilo("nativo", "Nativo", None, "", (0, 0, 0), 0.0,
           "o jogo decide o gatilho, a vibração, a luz e o toque; o Hefesto não escolhe nada"),
    Estilo("fps", "FPS", "Machine", "max", (255, 40, 40), 1.0,
           "o R2 estala em rajada, que é o gesto do gênero, e o L2 tem o peso da mira",
           _respira((("start", 2), ("end", 9), ("strength", 4), ("frequency", 40))),
           Lado("Machine"), Lado("Resistance", "mira-firme")),
    Estilo("corrida", "Corrida", "MultiPositionVibration", "balanceado", (255, 140, 0), 1.0,
           "o acelerador ronca e o freio pulsa como o ABS; o corpo do controle sente o motor",
           Receita(toque_por_tiro=False, lado_do_som=False, luz="acende",
                   som_quando_o_jogo_cala=False),
           Lado("MultiPositionVibration", "motor-no-acelerador"),
           Lado("Resistance", "freio-abs-que-pulsa")),
    Estilo("acao", "Ação", "Weapon", "max", (170, 60, 255), 1.0,  # (noqa-acento)
           "o golpe pesa no R2 e chega ao braço; o arco é uma escolha daqui",
           _respira(rumble_no_dedo=True),
           Lado("Weapon", "golpe-pesado"), Lado("Resistance", "mira-firme")),
    Estilo("aventura", "Aventura", "Bow", "balanceado", (40, 200, 90), 1.0,
           "o arco é o gesto da aventura e a chama é a tocha; escalar e a porta ficam a um clique",
           Receita(luz_base="chama", luz_ritmo=5, rumble_no_dedo=True),
           Lado("Bow", "corda-que-estica"), Lado("Resistance", "mira-firme")),
    Estilo("esportes", "Esportes", "Resistance", "balanceado", (40, 120, 255), 1.0,
           "o chute carrega e correr muito pesa no dedo",
           Receita(rumble_no_dedo=True),
           Lado("Resistance", "golpe-carregado"), Lado("Resistance", "pique-que-cansa")),
    Estilo("point_and_click", "Point and click", "Weapon", "economia", (0, 200, 210), 0.4,
           "os gatilhos são os botões do mouse e respondem como um; vibração baixa não distrai",
           Receita(modo="desktop", arranjo="point_and_click", som_quando_o_jogo_cala=False),
           Lado("Weapon", "clique-mouse"), Lado("Weapon", "clique-mouse")),
    Estilo("visual_novel", "Visual novel", "Off", "economia", (0, 200, 210), 0.5,
           "o texto é longo e a luz não disputa a leitura; os ombros voltam, pulam e abrem o menu",
           Receita(modo="desktop", arranjo="navegacao", molde="visual_novel", luz_base="mare",
                   luz_ritmo=1, som_quando_o_jogo_cala=False)),
    Estilo("adulto", "Adulto", "Off", "max", (250, 128, 114), 1.0,
           "o gatilho é do jogo; a vibração sobe e a luz fica parada, sem reação a tiro",
           Receita()),
    Estilo("terror", "Terror", "Weapon", "max", (215, 30, 55), 0.7,
           "a arma não é confiável e o coração bate na luz e nos motores; a luz baixa não denuncia",
           Receita(duracao_da_vibracao_ms=2 * DURACAO_DE_SEMPRE_MS,
                   luz_base="batimento", luz_ritmo=10, rumble_no_dedo=True,
                   alto_falante=SOM_DO_PC_TAMBEM_NO_CONTROLE, microfone_ligado=True),
           Lado("Weapon", "pino-que-falha"), Lado("Resistance", "mira-firme")),
    Estilo("luta", "Luta", "Weapon", "max", (255, 40, 180), 1.0,
           "forte num gatilho, fraco no outro, e a pancada vem do lado do golpe",
           _respira(rumble_no_dedo=True),
           Lado("Weapon", "golpe-pesado"), Lado("Weapon", "golpe-leve")),
    Estilo("souls", "Souls/RPG", "Weapon", "max", (200, 120, 30), 0.6,
           "cada golpe pesado custa e ecoa, e segurar o escudo cansa o dedo",
           Receita(luz="respira", luz_por_segundo=RESPIRA_POR_SEGUNDO,
                   luz_base="chama", luz_ritmo=5, rumble_no_dedo=True),
           Lado("Weapon", "golpe-pesado"), Lado("MultiPositionFeedback", "escudo-que-aguenta")),
    Estilo("furtivo", "Furtivo", "Weapon", "economia", (70, 90, 160), 0.3,
           "tudo é baixo e preciso; o clique é discreto e prender a mira tem respiração",
           Receita(),
           Lado("Weapon", "golpe-leve"), Lado("Resistance", "carga-folego")),
    Estilo("maratona", "Maratona", "Off", "economia", (120, 120, 140), 0.25,
           "a sessão é longa: tudo que gasta bateria cai ao mínimo — mas a luz "
           "NÃO apaga, porque apagada os quatro ficariam iguais",
           Receita(luz="bateria", luz_por_segundo=RESPIRA_POR_SEGUNDO,
                   som_quando_o_jogo_cala=False)),
    Estilo("plataforma", "Plataforma", "SlopeFeedback", "balanceado", (255, 210, 40), 1.0,
           "agarrar e carregar ganham corpo no gatilho; a vibração marca o impacto",
           Receita(luz_base="arco-iris", luz_ritmo=7),
           Lado("SlopeFeedback", "agarrar"), Lado("MultiPositionVibration", "energia-que-cresce")),
    Estilo("retro", "Retrô/Emulador", "Off", "economia", (60, 230, 90), 1.0,
           "o console original não tinha nada disso; o verde é o do tubo",
           Receita(som_quando_o_jogo_cala=False)),
    Estilo("ritmo", "Ritmo/Música", "Weapon", "max", (255, 0, 220), 1.0,
           "a vibração É o instrumento; cada nota tem um clique que volta livre",
           Receita(luz="batida", luz_por_segundo=TETO_DO_PISCAR, lado_do_som=False,
                   alto_falante=MUSICA_SO_NO_PC),
           Lado("Weapon", "golpe-leve"), Lado("Weapon", "golpe-leve")),
    Estilo("simulacao", "Simulação/Voo", "SlopeFeedback", "economia", (90, 180, 255), 0.6,
           "o manche endurece com o curso e a pista ou a turbulência passam pelo L2 e pelo corpo",
           Receita(toque_por_tiro=False, lado_do_som=False, luz_base="mare", luz_ritmo=10,
                   som_quando_o_jogo_cala=False),
           Lado("SlopeFeedback"), Lado("Galloping", "terreno-que-muda")),
    Estilo("personalizado", "Personalizado", None, "", (0, 0, 0), 0.0,
           "é o estilo que diz 'eu ajusto na mão' — não mexe em nada"),
)

SAIU_DO_CATALOGO: dict[str, str] = {"arco": "acao"}  # (noqa-acento)

POR_ROTULO = {e.rotulo: e for e in ESTILOS}
POR_CHAVE = {e.chave: e for e in ESTILOS}
POR_CHAVE.update({velha: POR_CHAVE[nova] for velha, nova in SAIU_DO_CATALOGO.items()})


def chave_do_catalogo(chave: object) -> object:
    """A chave de hoje do estilo: a que saiu do catálogo vira a do estilo que a recebeu."""
    return SAIU_DO_CATALOGO.get(chave, chave) if isinstance(chave, str) else chave


SEM_COR = frozenset({"personalizado", "nativo"})

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
    if e.chave in SEM_COR:
        raise ValueError(
            f"o estilo {e.rotulo!r} não escolhe cor: o Personalizado diz 'eu ajusto na mão' e o "
            "Nativo deixa a luz com o jogo. Perguntar a cor dele é perguntar o que não delegou.")
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


def estilo_que_pinta(chave: object) -> Estilo | None:
    """O estilo do perfil que escolhe a cor da luz, ou ``None``.

    ``None`` sem estilo, com chave desconhecida e nos estilos de ``SEM_COR`` (o Nativo deixa a luz
    com o jogo e o Personalizado com a mão do usuário). A chave que saiu do catálogo vale como a
    do estilo que a recebeu.
    """
    estilo = POR_CHAVE.get(chave) if isinstance(chave, str) else None
    if estilo is None or estilo.chave in SEM_COR:
        return None
    return estilo


def luz_automatica(estilo: object, jogador: int | None,
                   tom_do_plastico: RGB | None) -> tuple[RGB, float]:
    """A cor automática de um controle e o fator de brilho dela: ``(cor, fator)``.

    É a resposta única a «que cor acende o controle sem cor escolhida à mão», para o daemon e
    para a tela. Com um estilo que pinta e o controle num lugar de 1 a 4, a cor da unidade dele
    na família do estilo (:func:`cor_da_unidade`) e o brilho do estilo; sem isso, a do plástico,
    e a do número sem ela (``led_control.cor_automatica``), com fator 1,0. Assim o controle que
    chega depois do gesto da aba Perfis, e o Modo automático da Iluminação, acendem o estilo.
    """
    from hefesto_dualsense4unix.core.led_control import cor_automatica

    dono = estilo_que_pinta(estilo)
    if dono is not None and jogador is not None and 1 <= int(jogador) <= 4:
        return cor_da_unidade(dono, int(jogador)), float(dono.brilho)
    return cor_automatica(jogador, tom_do_plastico), 1.0
