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

from hefesto_dualsense4unix.core.ds_output_report import SAIDA_SO_NO_ALTO_FALANTE

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

#: «batida»: a luz sobe na borda do som do jogo, não no tiro (o Ritmo, CATALOGO §3 «Na batida»);
#: «acende»: o brilho segue o curso do gatilho (a Corrida); «bateria»: respira bem devagar quando a
#: carga acaba e nunca pisca (a Maratona). As duas últimas são do laço da luz (`luz_animada`).
LuzQueReage = Literal["parada", "respira", "pisca", "batida", "acende", "bateria"]


@dataclass(frozen=True)
class AltoFalanteDoEstilo:
    """O que o estilo diz do alto-falante do controle: a camada que duplica o som do PC.

    ``Receita.alto_falante`` é ``None`` quando o estilo não opina (o alto-falante fica com o jogo
    e com o perfil). Quem escreve é ``ProfileManager.apply_som_do_estilo``, só com o Modo
    automático da aba Controles ligado.
    """

    #: a ``fonte`` do nó de som do controle (``ProfileSpeakerConfig.fonte``): ``mix`` faz todo o
    #: som do PC cair também no controle; ``sfx`` deixa o nó livre para o que o jogo mandar
    fonte: Literal["mix", "sfx"]
    #: o byte de saída do alto-falante (``core.ds_output_report.SAIDA_*``); ``None`` não toca nele
    rota: int | None = None
    #: ``True`` escreve o nível «Padrão» (100% do registrador, ``manager.VOLUME_DO_PADRAO``);
    #: ``False`` não escreve nível nenhum: só a ``fonte`` vai, e o controle fica com o volume
    #: que já tem (escrever o volume tomaria a posse dos bytes de áudio sem pedido)
    nivel_padrao: bool = False


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
    #: o som do jogo vira háptica onde o jogo não manda rumble (o estalo, o toque na forma do
    #: estilo; o grave, um corpo discreto) e cede no primeiro rumble dele
    #: (O-JOGO-SEM-RUMBLE-SE-SENTE-PELO-SOM-DELE-01); desligado onde o silêncio é o desenho e
    #: onde o contínuo do estilo (a Corrida, a Simulação) já é o som do jogo
    som_quando_o_jogo_cala: bool = True
    #: o rumble do jogo chega ao dedo que aperta o gatilho, em vibração (o modo `0x26`)
    #: (O-RUMBLE-DO-JOGO-CHEGA-AO-DEDO-NO-GATILHO-01); ligado nos estilos de golpe
    rumble_no_dedo: bool = False
    #: o modo que o estilo liga (`ProfileModeConfig.kind`); `None` tira só o `desktop`
    #: do perfil e deixa os outros modos como estão
    modo: Literal["desktop"] | None = None
    #: a tabela de botões que o estilo grava no perfil (`MOLDES`); `None` não toca na tabela
    molde: Literal["visual_novel", "so_mouse", "teclado_e_mouse"] | None = None
    #: a base da luz que anda sozinha (`schema.BASES_DA_LUZ`), escrita no `leds.efeito` de cada
    #: controle com a cor da unidade; `None` é a luz fixa. O pulso no tiro é a `luz` de cima.
    luz_base: str | None = None
    #: o ritmo da base, de 1 a 10 (`schema.RITMO_MINIMO_DA_LUZ`..`RITMO_MAXIMO_DA_LUZ`)
    luz_ritmo: int = 0
    #: o alto-falante do controle (O-ESTILO-TERROR-SOBE-O-ALTO-FALANTE-E-LIGA-O-MICROFONE-NO-
    #: AUTOMATICO-01 e O-ALTO-FALANTE-SEGUE-O-ESTILO-E-O-RITMO-NUNCA-DUPLICA-01): ``None`` = sem
    #: opinião, a rota do jogo; só o Terror (duplica) e o Ritmo (nunca duplica) opinam
    alto_falante: AltoFalanteDoEstilo | None = None
    #: abrir o microfone do controle quando o estilo entra (o Terror); ``None`` = sem opinião.
    #: Nunca ``False``: nenhum estilo cala o microfone, e abrir sem pedir expõe a voz da pessoa
    microfone_ligado: bool | None = None


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


#: O Terror duplica o som do PC no controle com o PADRÃO DA ABA ÁUDIO e nenhum número novo
#: (decisão por delegação de 23/10/2026, a validar na L2): a ``fonte`` ``mix`` é o que a aba acende
#: como «Todo o som do PC» (``a02_controles.aceso_da_fileira``); a rota é a desse botão
#: (``a02_controles.ROTA_TUDO_NO_CONTROLE`` = ``cartao_do_controle.ROTA_DO_CANAL[CANAL_TODO_O_PC]``
#: = ``SAIDA_SO_NO_ALTO_FALANTE``); o nível é o «Padrão» (``manager.VOLUME_DO_PADRAO``, os 100% do
#: registrador, que já passam do PS5). A L2 confirma o número.
SOM_DO_PC_TAMBEM_NO_CONTROLE = AltoFalanteDoEstilo(
    "mix", rota=SAIDA_SO_NO_ALTO_FALANTE, nivel_padrao=True)
#: O Ritmo nunca duplica: a música em dois tempos (o PC e o alto-falante, pelo rádio com o
#: codificador e a fila no caminho) faz a batida escorregar. Só a ``fonte`` ``sfx`` vai, e o
#: controle fica com o volume que já tem. A L8 mede o atraso e confirma a trava.
MUSICA_SO_NO_PC = AltoFalanteDoEstilo("sfx")

#: as variáveis que o gesto do estilo aplica no perfil, por motor que já existe
APLICADAS = ("ajustes_do_gatilho", "modo", "molde", "luz_base", "luz_ritmo")
#: as que ficam aqui, como dado: o motor do tato lê pelo estilo guardado no perfil
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
    # O Nativo é o estilo em que o jogo decide: sem gatilho, vibração, luz nem toque do Hefesto
    # (receita invisível ausente = o motor do tato não age). Não é o Modo Nativo, que é outro eixo.
    Estilo("nativo", "Nativo", None, "", (0, 0, 0), 0.0,
           "o jogo decide o gatilho, a vibração, a luz e o toque; o Hefesto não escolhe nada"),
    # O R2 bate a cada tiro (Metralhadora); o L2 tem o peso da mira (Peso · leve). O Coice dos
    # motores fecha a rajada na soltura.
    Estilo("fps", "FPS", "Machine", "max", (255, 40, 40), 1.0,
           "o R2 estala em rajada, que é o gesto do gênero, e o L2 tem o peso da mira",
           # a Metralhadora a 40 Hz e força 4, do curso 2 ao 9 (CATALOGO §2.4: era a Arma
           # automática a 60 Hz), na faixa de 0 a 255 Hz [SONY]
           _respira((("start", 2), ("end", 9), ("strength", 4), ("frequency", 40))),
           Lado("Machine"), Lado("Resistance", "mira-firme")),
    # o corpo da Corrida e da Simulação é o motor e a pista, não o tiro (CATALOGO §4). O ronco do
    # motor está no acelerador e no corpo (o Som no corpo): decisão de 19/10/2026, que revoga
    # a regra «nenhum contínuo como padrão de estilo».
    # A luz acende com o curso do gatilho (o acelerador e o freio aparecem na barra).
    Estilo("corrida", "Corrida", "MultiPositionVibration", "balanceado", (255, 140, 0), 1.0,
           "o acelerador ronca e o freio pulsa como o ABS; o corpo do controle sente o motor",
           Receita(toque_por_tiro=False, lado_do_som=False, luz="acende",
                   som_quando_o_jogo_cala=False),
           Lado("MultiPositionVibration", "motor-no-acelerador"),
           Lado("Resistance", "freio-abs-que-pulsa")),
    # A Ação: golpe pesado no R2, peso de mira no L2. O arco, que era um estilo, é uma escolha
    # daqui (Carga · estica e Carga · solta seca vêm na frente da lista).
    Estilo("acao", "Ação", "Weapon", "max", (170, 60, 255), 1.0,  # (noqa-acento): chave
           "o golpe pesa no R2 e chega ao braço; o arco é uma escolha daqui",
           _respira(rumble_no_dedo=True),
           Lado("Weapon", "golpe-pesado"), Lado("Resistance", "mira-firme")),
    # A Aventura, os Esportes, o Terror e a Luta guardam a chave de hoje (CATALOGO §2.4), com os
    # números do dono dela (`trigger_specs.PRESETS`), como todo estilo.
    Estilo("aventura", "Aventura", "Bow", "balanceado", (40, 200, 90), 1.0,
           "o arco é o gesto da aventura e a chama é a tocha; escalar e a porta ficam a um clique",
           Receita(luz_base="chama", luz_ritmo=5, rumble_no_dedo=True),
           Lado("Bow", "corda-que-estica"), Lado("Resistance", "mira-firme")),
    Estilo("esportes", "Esportes", "Resistance", "balanceado", (40, 120, 255), 1.0,
           "o chute carrega e correr muito pesa no dedo",
           Receita(rumble_no_dedo=True),
           Lado("Resistance", "golpe-carregado"), Lado("Resistance", "pique-que-cansa")),
    # a luz fixa a 0,4 não disputa a leitura (CATALOGO §3)
    # Os dois gatilhos são o botão do mouse: o Clique · mouse, raso e seco, nos dois lados.
    Estilo("point_and_click", "Point and click", "Weapon", "economia", (0, 200, 210), 0.4,
           "os gatilhos são os botões do mouse e respondem como um; vibração baixa não distrai",
           # a Navegação é escolha do usuário (ESCOLHAS de 08/10); o toque e o lado também
           Receita(modo="desktop", molde="so_mouse", som_quando_o_jogo_cala=False),
           Lado("Weapon", "clique-mouse"), Lado("Weapon", "clique-mouse")),
    Estilo("visual_novel", "Visual novel", "Off", "economia", (0, 200, 210), 0.5,
           "o texto é longo e a luz não disputa a leitura; os ombros voltam, pulam e abrem o menu",
           # a família do Point and click, a meia luz e a maré lenta; o gatilho é clique, sem efeito
           Receita(modo="desktop", molde="visual_novel", luz_base="mare", luz_ritmo=1,
                   som_quando_o_jogo_cala=False)),
    # O Adulto não mexe no gatilho (o jogo decide) e sobe a vibração; a luz fica parada e sem reação
    # a tiro. A família é o rosa-salmão que o usuário aprovou em 13/10/2026, longe das outras.
    Estilo("adulto", "Adulto", "Off", "max", (250, 128, 114), 1.0,
           "o gatilho é do jogo; a vibração sobe e a luz fica parada, sem reação a tiro",
           Receita()),
    # O coração bate na luz (a base «batimento») e nos motores (a Batida), no lugar do piscar
    # 2/s, que é alarme e não medo; a vibração dura o dobro [MDN] (escolha).
    Estilo("terror", "Terror", "Weapon", "max", (215, 30, 55), 0.7,
           "a arma não é confiável e o coração bate na luz e nos motores; a luz baixa não denuncia",
           Receita(duracao_da_vibracao_ms=2 * DURACAO_DE_SEMPRE_MS,
                   luz_base="batimento", luz_ritmo=10, rumble_no_dedo=True,
                   alto_falante=SOM_DO_PC_TAMBEM_NO_CONTROLE, microfone_ligado=True),
           Lado("Weapon", "pino-que-falha"), Lado("Resistance", "mira-firme")),
    # A Luta separa o golpe forte (R2) do fraco (L2); a pancada vem do lado de onde veio o golpe.
    Estilo("luta", "Luta", "Weapon", "max", (255, 40, 180), 1.0,
           "forte num gatilho, fraco no outro, e a pancada vem do lado do golpe",
           _respira(rumble_no_dedo=True),
           Lado("Weapon", "golpe-pesado"), Lado("Weapon", "golpe-leve")),
    # O combate de estamina dos soulslike: golpe pesado que custa e ecoa, escudo que cansa o dedo.
    # O Eco (o Impacto com cauda grave) está na háptica do estilo (`formas_de_haptica.POR_ESTILO`).
    Estilo("souls", "Souls/RPG", "Weapon", "max", (200, 120, 30), 0.6,
           "cada golpe pesado custa e ecoa, e segurar o escudo cansa o dedo",
           Receita(luz="respira", luz_por_segundo=RESPIRA_POR_SEGUNDO,
                   luz_base="chama", luz_ritmo=5, rumble_no_dedo=True),
           Lado("Weapon", "golpe-pesado"), Lado("MultiPositionFeedback", "escudo-que-aguenta")),
    # Tudo é baixo e preciso: o clique é discreto e prender a mira tem respiração.
    # O L2 prende a respiração (Carga · fôlego preso) e, ao soltar, os motores dão a Onda.
    Estilo("furtivo", "Furtivo", "Weapon", "economia", (70, 90, 160), 0.3,
           "tudo é baixo e preciso; o clique é discreto e prender a mira tem respiração",
           Receita(),
           Lado("Weapon", "golpe-leve"), Lado("Resistance", "carga-folego")),
    # A luz fica fixa a 25% e, quando a carga acaba, respira bem devagar (nunca pisca).
    Estilo("maratona", "Maratona", "Off", "economia", (120, 120, 140), 0.25,
           "a sessão é longa: tudo que gasta bateria cai ao mínimo — mas a luz "
           "NÃO apaga, porque apagada os quatro ficariam iguais",
           Receita(luz="bateria", luz_por_segundo=RESPIRA_POR_SEGUNDO,
                   som_quando_o_jogo_cala=False)),
    # a luz que gira é a alegria do gênero (a base «arco-íris»)
    Estilo("plataforma", "Plataforma", "SlopeFeedback", "balanceado", (255, 210, 40), 1.0,
           "agarrar e carregar ganham corpo no gatilho; a vibração marca o impacto",
           Receita(luz_base="arco-iris", luz_ritmo=7),
           Lado("SlopeFeedback", "agarrar"), Lado("MultiPositionVibration", "energia-que-cresce")),
    Estilo("retro", "Retrô/Emulador", "Off", "economia", (60, 230, 90), 1.0,
           "o console original não tinha nada disso; o verde é o do tubo",
           Receita(som_quando_o_jogo_cala=False)),
    # Um clique que volta livre em cada nota, nos dois lados, sem atrasar o tempo.
    Estilo("ritmo", "Ritmo/Música", "Weapon", "max", (255, 0, 220), 1.0,
           "a vibração É o instrumento; cada nota tem um clique que volta livre",
           # a luz na batida da música, até o teto [WCAG]; o lado do estouro não serve à música
           Receita(luz="batida", luz_por_segundo=TETO_DO_PISCAR, lado_do_som=False,
                   alto_falante=MUSICA_SO_NO_PC),
           Lado("Weapon", "golpe-leve"), Lado("Weapon", "golpe-leve")),
    # O manche endurece com o curso (a Rampa de força) e o chão passa pelo L2 e pelo corpo
    # (decisão de 19/10/2026).
    # O Grão (grãos finos) está na háptica do estilo (`formas_de_haptica.POR_ESTILO`).
    Estilo("simulacao", "Simulação/Voo", "SlopeFeedback", "economia", (90, 180, 255), 0.6,
           "o manche endurece com o curso e a pista ou a turbulência passam pelo L2 e pelo corpo",
           Receita(toque_por_tiro=False, lado_do_som=False, luz_base="mare", luz_ritmo=10,
                   som_quando_o_jogo_cala=False),
           Lado("SlopeFeedback"), Lado("Galloping", "terreno-que-muda")),
    Estilo("personalizado", "Personalizado", None, "", (0, 0, 0), 0.0,
           "é o estilo que diz 'eu ajusto na mão' — não mexe em nada"),
)

#: As chaves que saíram do catálogo e carregam como outro estilo: um perfil salvo com a velha
#: segue funcionando (o `schema` não recusa chave de estilo de propósito). O Arco era um estilo
#: de gatilho só (`Bow`) e virou uma escolha dentro da Ação e da Aventura (19/10/2026).
SAIU_DO_CATALOGO: dict[str, str] = {"arco": "acao"}  # (noqa-acento): chave

POR_ROTULO = {e.rotulo: e for e in ESTILOS}
POR_CHAVE = {e.chave: e for e in ESTILOS}
POR_CHAVE.update({velha: POR_CHAVE[nova] for velha, nova in SAIU_DO_CATALOGO.items()})


def chave_do_catalogo(chave: object) -> object:
    """A chave de hoje do estilo: a que saiu do catálogo vira a do estilo que a recebeu."""
    return SAIU_DO_CATALOGO.get(chave, chave) if isinstance(chave, str) else chave


#: Os estilos que não pintam o controle: o Personalizado (a mão do usuário) e o Nativo (o jogo).
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
