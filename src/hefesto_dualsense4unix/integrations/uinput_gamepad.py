"""Gamepad virtual via python-evdev (W6.3 + FEAT-DSX-GAMEPAD-FLAVOR-01).

Cria `/dev/input/js*` que o kernel registra como um gamepad padrão,
permitindo que jogos recebam o input do DualSense já traduzido/filtrado
pelo daemon (combos sagrados removidos).

Dois **flavors** (a "máscara" que o jogo vê):
  - ``dualsense``: VID Sony + PID do DualSense **Edge** (054c:0df2) → prompts
    PlayStation. O PID é DE PROPÓSITO distinto do físico (0ce6) — invariante
    VPAD-04/VPAD-06: nenhum caminho de criação de vpad pode dividir VID/PID
    com o controle real, senão a launch option persistida na Steam
    (``IGNORE_DEVICES=0x054c/0x0ce6``) esconde físico E vpad juntos e o jogo
    fica com ZERO controles (o bug do estudo de 117 agentes).
  - ``xbox``: VID/PID Xbox 360 (045e:028e) → **prompts Xbox**. Fallback
    para jogos "XInput-only" (Windows-ports via Proton) que ignoram Sony.

Fluxo do daemon:
  - Controle físico lê input via `EvdevReader` (HOTFIX-2).
  - Daemon decide: combo sagrado (HotkeyManager) consome, resto repassa.
  - `UinputGamepad.forward_*()` aplica os eventos no device virtual.
  - Jogo lê o device virtual com a máscara escolhida.

O button mapping (evdev BTN_A/B/X/Y = south/east/north/west) é o mesmo nos
dois flavors — o que muda os prompts é o VID/PID, não os códigos de botão.

FEAT-VPAD-FF-PASSTHROUGH-01 — force-feedback (rumble do JOGO):
  O device virtual anuncia EV_FF (FF_RUMBLE + FF_PERIODIC), então jogos/SDL
  fazem upload de efeitos de vibração NELE. O handshake do kernel
  (UI_FF_UPLOAD/UI_FF_ERASE via EV_UINPUT) e os eventos de play/stop (EV_FF)
  chegam no fd do uinput; `pump_ff()` — chamado a cada tick do poll loop —
  drena tudo isso e entrega o rumble resultante ao `rumble_sink` injetado
  (que escreve nos motores do DualSense físico certo). Por isso o backend
  migrou de python-uinput para python-evdev: o python-uinput não expõe
  `ff_effects_max` nem o handshake de upload — sem eles o kernel recusa
  device com EV_FF, e era exatamente essa a razão de os jogos nunca
  vibrarem o DualSense em "Jogar pelo Hefesto". Ambos os flavors ganham FF
  (o Xbox 360 real também tem rumble; jogos esperam). Ambiente sem suporte
  a FF degrada para o vpad sem EV_FF, sem crash.
"""
from __future__ import annotations

import contextlib
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from hefesto_dualsense4unix.core.rumble import pedido_mais_forte
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Xbox 360 (fallback p/ jogos XInput-only).
XBOX360_VENDOR = 0x045E
XBOX360_PRODUCT = 0x028E
XBOX360_NAME = "Microsoft X-Box 360 pad (Hefesto - Dualsense4Unix virtual)"

# DualSense (Sony) FÍSICO (054c:0ce6). NÃO entra em máscara de vpad nenhuma:
# é o VID/PID que a launch option IGNORE_DEVICES manda o SDL esconder — um vpad
# com este PID some junto com o físico (VPAD-04). As constantes ficam porque
# identificam o controle REAL em outros módulos (espelham `evdev_reader` e
# `uhid_gamepad.DUALSENSE_PRODUCT`).
DUALSENSE_VENDOR = 0x054C
DUALSENSE_PRODUCT = 0x0CE6
DUALSENSE_NAME = "Sony Interactive Entertainment DualSense Wireless Controller"

# DualSense **Edge** — a máscara "dualsense" do vpad (VPAD-04). Espelha o
# `uhid_gamepad.VPAD_PRODUCT`: uhid E uinput apresentam o MESMO Edge 0x0df2,
# então o invariante VPAD-06 (vpad nunca divide VID/PID com o físico) vale em
# TODOS os caminhos de criação, inclusive neste fallback degradado. Ressalva
# honesta (refutação nº 2 do sprint doc): um vpad uinput 0df2 não tem hidraw —
# o SDL não usa o driver HIDAPI PS5 nele e cai no matching evdev com um GUID
# (version 0x3) ausente do gamecontrollerdb; esse mapeamento NUNCA foi validado
# ao vivo, e por isso as envs materializadas para o wrapper de launch omitem o
# IGNORE_DEVICES quando qualquer vpad está neste backend degradado (ver
# `daemon.launch_env.compose_env` — DEDUP-04).
DUALSENSE_EDGE_PRODUCT = 0x0DF2
DUALSENSE_EDGE_NAME = (
    "Sony Interactive Entertainment DualSense Edge Wireless Controller"
)

# Nintendo Switch Pro Controller — a TERCEIRA máscara (ordem dela, 07/09/2026).
#
# É EMULAÇÃO, não suporte a aparelho Nintendo físico: o Hefesto faz o DualSense
# DELA se apresentar ao jogo como um Pro. O foco do produto continua sendo os
# quatro DualSense (decisão dela, 06/09/2026).
#
# VID/PID lidos no fonte C em `assets/dkms/hid-nintendo/hid-ids.h:1068,1073`
# (`USB_VENDOR_ID_NINTENDO` / `USB_DEVICE_ID_NINTENDO_PROCON`) — o mesmo par que
# `core.linhagem_nintendo.VIDPID_PRO` já nomeia.
#
# O PID É 0x2009 E TEM DE SER, e isto DERRUBA a afirmação que estava escrita em
# `interface/aba02.py` (*"o PID forjado não pode ser 0x2009"*). MEDIDO em
# 07/09/2026 dirigindo a libSDL2 desta máquina por ctypes, com o nó de pé:
#
#     057e:2009 -> SDL_GameControllerGetType = 5 (NINTENDO_SWITCH_PRO)
#     057e:2017 -> a SDL responde outro aparelho (SNES), não o Pro
#
# A SDL decide o TIPO — e portanto os prompts — pelo par VID/PID, e 0x2009 é o
# único que devolve Switch Pro. Um PID "seguro" entrega uma máscara que não
# mostra prompt de Nintendo nenhum, que é a máscara inteira.
#
# O QUE A RESSALVA DAQUELE TEXTO ACERTAVA, E FICA DECLARADO: se um Pro
# Controller (ou o clone 8BitDo em modo Switch, que mente o mesmo par) estiver
# na mesa E a lista de `SDL_GAMECONTROLLER_IGNORE_DEVICES` contiver
# `0x057e/0x2009`, o jogo perde o físico E o vpad juntos — é o VPAD-04 com
# outro fabricante. O produto NUNCA emite esse par no IGNORE dele
# (`daemon.launch_env._IGNORE_VALUE` é 054c:0ce6 + 28de:11ff); o risco só nasce
# de uma lista que a pessoa escreveu à mão. Não há saída por outro PID: ou é
# 0x2009 e a máscara existe, ou não é e ela não faz o que promete.
NINTENDO_VENDOR = 0x057E
NINTENDO_PROCON_PRODUCT = 0x2009
#: O nome que o `hid-nintendo` escreve (`ctlr->input->name = hdev->name`,
#: `hid-nintendo.c:2415`) mais o sufixo da casa — o mesmo padrão da máscara
#: Xbox, e serve a quem lê `/proc/bus/input/devices` com quatro vpads na mesa.
#:
#: **FATO SUBSTITUÍDO — 07/09/2026.** Esta linha dizia *"o nome NÃO entra no
#: GUID da SDL, então o sufixo é de graça"*. **As duas metades são falsas**, e
#: a medição está abaixo. O nome ENTRA no GUID, e o sufixo NÃO é de graça.
#:
#: MEDIDO com a libSDL2 desta máquina (`libSDL2-2.0.so.0.3000.0`), enumerando
#: os quatro vpads dela sem abrir nenhum. Os bytes 2-3 do GUID são o **CRC16
#: do nome** (`SDL_crc16`, refletido, poly 0xA001) — conferido nos quatro,
#: 4 de 4:
#:
#:     nome ................................ crc16   bytes[2:4] do GUID
#:     DualSense ... (Hefesto P1) .......... 0x8076  7680
#:     DualSense ... (Hefesto P2) .......... 0x7076  7670
#:     DualSense ... (Hefesto P3) .......... 0xe077  77e0
#:     DualSense ... (Hefesto P4) .......... 0xd075  75d0
#:
#: O QUE ISSO CUSTA, e é a parte que importa para quem mexer no nome: trocar o
#: nome troca o GUID. A busca de mapping da SDL cai de volta para o GUID com
#: esse CRC ZERADO quando o primeiro não casa, então um mapping do
#: `gamecontrollerdb` continua sendo encontrado — mas os quatro vpads colapsam
#: no MESMO GUID (`030000004c050000f20d000000810000`) e passam a ser servidos
#: por UM mapping só, o primeiro registrado. Consequência medida:
#: `SDL_JoystickNameForIndex` devolve o nome certo de cada um, e
#: `SDL_GameControllerNameForIndex` devolve **"Hefesto P1" nos quatro**.
#:
#: Ou seja: **o número dentro do nome não chega a um jogo que use a API
#: GameController** — ele chega pelo evdev, pelo `/proc/bus/input/devices` e
#: pela API Joystick crua. Ver `CoopManager.numero_para_o_nome`, que é quem põe
#: o número ali, e a ressalva escrita na docstring dela.
NINTENDO_PROCON_NAME = (
    "Nintendo Co., Ltd. Pro Controller (Hefesto - Dualsense4Unix virtual)"
)

# Bus USB (0x03): apresentar como controle USB real ajuda o match da SDL no
# gamecontrollerdb (o GUID inclui bustype+vendor+product). O default do
# python-evdev é BUS_USB, mas mantemos explícito.
BUS_USB = 0x03

#: Versão do input_id do device virtual. O python-uinput usava 0x3 por default
#: e o GUID SDL inclui a versão — preservamos o valor para o match no
#: gamecontrollerdb não mudar entre releases (validado ao vivo em gameplay).
DEVICE_VERSION = 0x3

#: FEAT-VPAD-FF-PASSTHROUGH-01 — nº máximo de efeitos FF simultâneos que o
#: vpad anuncia ao kernel (`ff_effects_max`). O uinput exige > 0 quando EV_FF
#: está nas capabilities; SDL usa tipicamente 1-2 efeitos por jogo.
MAX_FF_EFFECTS = 16

#: Cap de eventos FF drenados por tick — proteção contra flood no fd (jogo
#: emitindo play/stop em rajada); o excedente fica para o próximo tick.
_FF_MAX_EVENTS_PER_PUMP = 64

#: Teto de segurança para efeito de duração 0 ("toca até mandar parar").
#:
#: Sem ele o deadline é infinito e SÓ o jogo pode parar o motor — se ele fecha
#: no meio de uma vibração, trava, ou o evento de stop se perde, o controle
#: vibra indefinidamente (relatado ao vivo: "não parava por nada", e a saída
#: foi o botão "Parar", que por sua vez trava o rumble em silêncio).
#:
#: 30 s é generoso de propósito: qualquer novo play do mesmo efeito RENOVA o
#: prazo, então uma cena que vibra continuamente segue vibrando enquanto o jogo
#: mantiver o pedido. O teto só age quando ninguém está mais pedindo nada.
FF_TETO_SEM_DURACAO_S = 30.0

# Catálogo de flavors. `name`/`vendor`/`product` definem a máscara.
# VPAD-04: a entrada dualsense usa o Edge (0x0df2) — NUNCA o 0x0ce6 do físico.
FLAVORS: dict[str, dict[str, Any]] = {
    "dualsense": {
        "name": DUALSENSE_EDGE_NAME,
        "vendor": DUALSENSE_VENDOR,
        "product": DUALSENSE_EDGE_PRODUCT,
    },
    "xbox": {
        "name": XBOX360_NAME,
        "vendor": XBOX360_VENDOR,
        "product": XBOX360_PRODUCT,
    },
    "nintendo": {
        "name": NINTENDO_PROCON_NAME,
        "vendor": NINTENDO_VENDOR,
        "product": NINTENDO_PROCON_PRODUCT,
    },
}
#: SPRINT-GAME-RUMBLE-01: o default é **xbox**, não dualsense. Na época da
#: decisão o vpad dualsense-uinput tinha o MESMO VID/PID do físico (054c:0ce6)
#: e SEM hidraw — o SDL/HIDAPI do jogo adotava o FÍSICO pelo hidraw e IGNORAVA
#: o vpad (rumble in-game MORTO + controle DUPLICADO). Com a máscara Xbox 360
#: (045e:028e) o jogo vê o vpad pelo caminho evdev/FF e a vibração funciona —
#: provado com SDL2 e validado em gameplay. Hoje a máscara DualSense vibra pelo
#: backend uhid (Edge 0x0df2 com hidraw de verdade) e o fallback uinput também
#: é Edge (VPAD-04), mas o default segue xbox: é o piso de compatibilidade que
#: funciona validado em QUALQUER backend. Quem prefere prompts de PlayStation
#: escolhe "dualsense" na GUI/perfil (documentado no README).
#:
#: NOTA DATADA — 22/08/2026 (MASCARA-QUE-GRUDA-01): a decisão dela — *"a máscara
#: deve vir da escolha do user"* — tirou a máscara dos PRESETS, e **não** daqui.
#: São duas perguntas, e confundi-las foi o que fez o `xbox` viajar do daemon
#: para dentro do arquivo dela:
#:
#: * o que um PERFIL shipa: nada. Os presets de jogo passam a `gamepad_flavor:
#:   null`, e um perfil novo nasce sem botão marcado no editor (`null` = "mantém
#:   a máscara que estiver valendo"). Nenhum arquivo ganha máscara sem gesto;
#: * o que o DAEMON usa quando ninguém nunca escolheu: **`dualsense`**, e NÃO
#:   este valor. Quem decide numa instalação nova é
#:   `DaemonConfig.gamepad_flavor` (HARMONIA-MASK-01, `lifecycle.py`), e
#:   `start_gamepad_emulation` faz `normalize_flavor(flavor or
#:   daemon.config.gamepad_flavor)` — o `DEFAULT_FLAVOR` só entra quando a
#:   config vem `None` ou com valor desconhecido. A primeira escolha dela na
#:   GUI substitui os dois e passa a grudar (`2b11172`).
#:
#: NOTA DATADA — 23/08/2026. Esta nota nasceu em 22/08 dizendo que este valor
#: era "o que o daemon usa quando ninguém nunca escolheu" e que "a H1 **não foi
#: remedida**". As duas afirmações são falsas, e a medição que as derruba já
#: estava no repositório:
#:
#: * MEDIDO num `XDG_CONFIG_HOME` vazio: `DaemonConfig.gamepad_flavor` de
#:   fábrica é `'dualsense'`; `DEFAULT_FLAVOR` aqui é `'xbox'`. Numa instalação
#:   nova o jogo recebe a máscara DualSense;
#: * a H1 FOI remedida, e a cronologia fecha: o portão que a citava nasceu em
#:   **14/07** (`56564de`), o vpad passou a subir em `uhid` em **16/07**
#:   (`b0596f0`/`389e429`), e em **22/07** a HARMONIA-MASK-01 — decisão dela —
#:   registrou a máscara dualsense *"validada em jogo real
#:   (Sackboy/Mad King/Pragmata)"* e a razão do xbox como *"de antes da máscara
#:   dualsense vibrar — **superado** pela validação da Onda Harmonia"*. É essa
#:   remedição que virou o default do daemon.
#:
#: Este piso continua `xbox` por um motivo mais estreito, e só ele: é o valor
#: que `normalize_flavor` devolve para entrada CORROMPIDA (config ausente ou
#: desconhecida), onde nenhuma das duas máscaras é a resposta certa e o que
#: importa é não estourar. Trocá-lo é decisão de produto separada, não a
#: consequência de uma H1 que ninguém remediu.
DEFAULT_FLAVOR = "xbox"

# Retrocompat: nome histórico apontando para o flavor Xbox.
DEVICE_NAME = XBOX360_NAME


#: Sinônimos tolerados na CLI/IPC → chave canônica de :data:`FLAVORS`. As
#: chaves canônicas NÃO entram aqui (o resolvedor consulta o `FLAVORS` antes,
#: para que um terceiro sabor no catálogo valha sem uma linha de edição nesta
#: tabela — a mesma regra de fonte única do `external_mask.mascaras_validas`).
#:
#: NOTA DATADA — 10/08/2026: **"sony"** e **"ps5"** entraram aqui porque eram a
#: palavra que ela usa para pedir a máscara de PlayStation, e caíam no `else`
#: junto com o lixo: `normalize_flavor("sony")` devolvia **"xbox"** — a máscara
#: OPOSTA à pedida, sem erro e sem log. Nome desconhecido é ERRO no portão do
#: IPC (`ipc_handlers._handle_gamepad_emulation_set`), não default.
#:
#: NOTA DATADA — 07/09/2026. Esta nota dizia, com todas as letras, que
#: "nintendo"/"switch"/"pro" NÃO entram aqui porque *"não existe máscara de
#: Switch neste catálogo"*. **A máscara passou a existir nesta leva**, e a
#: razão daquela recusa caiu junto com o fato que a sustentava. As três entram
#: agora, e a chave canônica `nintendo` NÃO precisou de linha nenhuma nesta
#: tabela — o `resolver_flavor` consulta o `FLAVORS` antes, exatamente como o
#: comentário acima prometia. Isso foi MEDIDO, não deduzido: com o sabor no
#: catálogo e esta tabela intocada, `resolver_flavor("nintendo")` já devolvia
#: `"nintendo"`.
FLAVOR_SINONIMOS: dict[str, str] = {
    "ps": "dualsense",
    "ps5": "dualsense",
    "playstation": "dualsense",
    "sony": "dualsense",
    "ds": "dualsense",
    "xbox360": "xbox",
    "x360": "xbox",
    "xinput": "xbox",
    "switch": "nintendo",
    "pro": "nintendo",
    "procon": "nintendo",
}


def resolver_flavor(flavor: object) -> str | None:
    """A máscara canônica de `flavor`, ou **None** quando ninguém a reconhece.

    A metade ESTRITA do par: aceita as chaves de :data:`FLAVORS` e os
    :data:`FLAVOR_SINONIMOS` (sem caixa e sem espaço em volta) e devolve `None`
    para qualquer outra coisa — inclusive `None`, número e `""`. Quem chama
    decide o que fazer com a recusa; o que esta função JAMAIS faz é escolher uma
    máscara por conta própria.

    É a função que o portão do IPC usa. O :func:`normalize_flavor` continua
    tolerante porque os caminhos internos (perfil em disco, config do daemon,
    co-op) precisam de um valor sempre — mas nenhum deles é a usuária digitando.
    """
    if not isinstance(flavor, str):
        return None
    key = flavor.strip().lower()
    if key in FLAVORS:
        return key
    return FLAVOR_SINONIMOS.get(key)


def nomes_de_flavor_aceitos() -> tuple[str, ...]:
    """Todo nome que :func:`resolver_flavor` reconhece, ordenado.

    Existe para a mensagem de recusa do portão poder DIZER o que vale — recusar
    sem listar a alternativa é trocar um default calado por um erro calado.
    """
    return tuple(sorted(set(FLAVORS) | set(FLAVOR_SINONIMOS)))


def normalize_flavor(flavor: str | None) -> str:
    """Resolve um flavor válido; cai no default se desconhecido/None.

    TOLERANTE de propósito, e por isso NÃO serve de portão: o desconhecido vira
    :data:`DEFAULT_FLAVOR` em silêncio. Quem valida entrada de gente (IPC, CLI)
    usa :func:`resolver_flavor`, que devolve `None` em vez de escolher.
    """
    if flavor is None:
        return DEFAULT_FLAVOR
    return resolver_flavor(flavor) or DEFAULT_FLAVOR

# Mapeamento canonico Hefesto - Dualsense4Unix (HOTFIX-2) -> evdev constant usado no uinput.
# Layout Xbox: cross=A, circle=B, square=X, triangle=Y.
BUTTON_TO_UINPUT: dict[str, str] = {
    "cross": "BTN_A",
    "circle": "BTN_B",
    "square": "BTN_X",
    "triangle": "BTN_Y",
    "l1": "BTN_TL",
    "r1": "BTN_TR",
    "create": "BTN_SELECT",
    "options": "BTN_START",
    "ps": "BTN_MODE",
    "l3": "BTN_THUMBL",
    "r3": "BTN_THUMBR",
}

#: O mesmo mapa para a máscara **nintendo**, e a diferença é o par X/Y.
#:
#: POR QUE ELE EXISTE, MEDIDO em 07/09/2026 (não lido). Com o nó de pé, a
#: libSDL2 desta máquina tem DUAS tabelas para o Switch Pro e escolhe entre
#: elas pelo `SDL_GAMECONTROLLER_USE_BUTTON_LABELS`:
#:
#:     =1 (default da SDL) -> a:b1,b:b0,x:b2,y:b3   (segue o RÓTULO impresso)
#:     =0                  -> a:b0,b:b1,x:b3,y:b2   (segue a POSIÇÃO)
#:
#: `bN` é o índice do botão na ORDEM DE CÓDIGO evdev do próprio nó, então
#: `b0`=BTN_SOUTH(0x130), `b1`=BTN_EAST(0x131), `b2`=BTN_NORTH(0x133) e
#: `b3`=BTN_WEST(0x134). Os dois pares viram juntos: o **A** de um Pro fica à
#: DIREITA e o **X** fica em CIMA, ao contrário do Xbox.
#:
#: ESTA CASA JÁ ESCOLHEU, E A ESCOLHA É `=0`. O `daemon.launch_env.compose_env`
#: crava `SDL_GAMECONTROLLER_USE_BUTTON_LABELS=0` em TODA variante desde a
#: 8BIT-03, para que os Nintendo FÍSICOS dela (o Pro e o 8BitDo em modo Switch)
#: sejam mapeados por posição, *"como o resto do ecossistema PC espera"*. Uma
#: máscara que decidisse ao contrário faria a casa ter duas regras para a mesma
#: pergunta.
#:
#: Logo esta tabela é POSICIONAL — e, sendo posicional, ela é a IDENTIDADE dos
#: códigos que o kernel já usa para o DualSense físico
#: (`core.evdev_reader.BUTTON_MAP`: cross=BTN_SOUTH, circle=BTN_EAST,
#: triangle=BTN_NORTH, square=BTN_WEST). O botão de baixo continua sendo
#: "confirmar"; o que muda é só o desenho na tela do jogo.
#:
#: O QUE ISSO CUSTA, DECLARADO: fora do wrapper do Hefesto o default da SDL é
#: `=1`, e aí os quatro botões da frente chegam trocados aos pares. MEDIDO
#: nesta bancada, com esta tabela: com `=0`, cross→`a`; com `=1`, cross→`b`.
#: **Não é limite novo desta máscara** — é o mesmo de todo Nintendo físico
#: nesta máquina desde a 8BIT-03, e a cura, se um dia for pedida, é a mesma
#: para os dois: cravar o mapeamento por `SDL_GAMECONTROLLERCONFIG` em vez de
#: depender do hint.
#:
#: `l2_btn`/`r2_btn` NÃO entram aqui de propósito: no Pro os gatilhos são
#: DIGITAIS (`BTN_TL2`/`BTN_TR2`, ver :func:`_capacidades_procon`) e quem os
#: escreve é o `forward_analog`, para haver **um escritor só** por código.
BOTOES_PROCON: dict[str, str] = {
    "cross": "BTN_SOUTH",    # b0 -> `a` da SDL  (confirmar)
    "circle": "BTN_EAST",    # b1 -> `b` da SDL  (voltar)
    "square": "BTN_WEST",    # b3 -> `x` da SDL  (0x134; é o BTN_Y do Xbox)
    "triangle": "BTN_NORTH", # b2 -> `y` da SDL  (0x133; é o BTN_X do Xbox)
    "l1": "BTN_TL",          # b5 -> leftshoulder
    "r1": "BTN_TR",          # b6 -> rightshoulder
    "create": "BTN_SELECT",  # b9 -> back
    "options": "BTN_START",  # b10 -> start
    "ps": "BTN_MODE",        # b11 -> guide
    "l3": "BTN_THUMBL",      # b12 -> leftstick
    "r3": "BTN_THUMBR",      # b13 -> rightstick
}

#: máscara -> tabela de botões. Fonte única: quem acrescentar um sabor ao
#: :data:`FLAVORS` sem entrada aqui é reprovado pelo portão
#: `tests/unit/test_a_mascara_nintendo_pro_atravessa_a_casa.py`.
BOTOES_POR_FLAVOR: dict[str, dict[str, str]] = {
    "dualsense": BUTTON_TO_UINPUT,
    "xbox": BUTTON_TO_UINPUT,
    "nintendo": BOTOES_PROCON,
}

#: Acima deste valor (0-255) o gatilho analógico do DualSense vira o botão
#: digital do Pro; abaixo de :data:`LIMIAR_GATILHO_SOLTO` ele solta. Os dois
#: valores são diferentes de propósito (histerese): com um limiar só, um dedo
#: parado em cima do ponto emitiria press/release a 60 Hz.
#:
#: O aparelho não decide isto por nós — é a consequência declarada de o Pro
#: **não ter gatilho analógico** (medido em `hid-nintendo.c`: o `procon` não
#: registra `ABS_Z`/`ABS_RZ`, e ZL/ZR são `BTN_TL2`/`BTN_TR2`).
LIMIAR_GATILHO_PRESSIONADO = 32
LIMIAR_GATILHO_SOLTO = 16


def _capacidades_ff(ecodes: Any) -> list[Any]:
    """Os bits de EV_FF, iguais nas três máscaras.

    FF_RUMBLE (motores weak/strong 0-65535), FF_PERIODIC + formas de onda (o
    kernel valida a waveform contra os bits do device; SDL usa efeito periódico
    como fallback de rumble em alguns jogos) e FF_GAIN (ganho global 0-65535
    que a SDL manda por padrão).

    RESSALVA DECLARADA na máscara nintendo: o Pro de verdade anuncia **só**
    `FF_RUMBLE` (`joycon_config_rumble`, `hid-nintendo.c:2321-2322`, um
    `input_ff_create_memless`). O nosso anuncia mais. É superconjunto — nenhum
    jogo perde caminho por isso, e um jogo que só sabe pedir periódico ganha um
    que o Pro real não teria.
    """
    return [
        ecodes.FF_RUMBLE,
        ecodes.FF_PERIODIC,
        ecodes.FF_SQUARE,
        ecodes.FF_TRIANGLE,
        ecodes.FF_SINE,
        ecodes.FF_GAIN,
    ]


def _capacidades_padrao(*, with_ff: bool) -> dict[int, Any]:
    """Capabilities das máscaras `dualsense` e `xbox` (formato python-evdev).

    Eixos 0-255 (igual ao evdev do DualSense) e HAT digital -1..1.

    Este conjunto é uma imitação byte a byte do `xpad`, e é por isso que a
    máscara Xbox funciona: MEDIDO em 07/09/2026, a libSDL2 aplica a este nó o
    mapeamento `a:b0,b:b1,x:b2,y:b3,leftshoulder:b4,rightshoulder:b5,back:b6,
    start:b7,guide:b8,leftstick:b9,rightstick:b10,lefttrigger:a2,leftx:a0,
    lefty:a1,rightx:a3,righty:a4,righttrigger:a5` — os onze botões e os seis
    eixos caem, na ordem de código, exatamente onde a tabela os espera.

    Import local — evita custo no import do módulo e permite ambientes sem a
    lib (o chamador trata ImportError).
    """
    from evdev import AbsInfo, ecodes

    axis = AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)
    hat = AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)
    caps: dict[int, list[Any]] = {
        ecodes.EV_ABS: [
            (ecodes.ABS_X, axis),
            (ecodes.ABS_Y, axis),
            (ecodes.ABS_RX, axis),
            (ecodes.ABS_RY, axis),
            (ecodes.ABS_Z, axis),   # LT
            (ecodes.ABS_RZ, axis),  # RT
            (ecodes.ABS_HAT0X, hat),
            (ecodes.ABS_HAT0Y, hat),
        ],
        ecodes.EV_KEY: [
            ecodes.BTN_A, ecodes.BTN_B, ecodes.BTN_X, ecodes.BTN_Y,
            ecodes.BTN_TL, ecodes.BTN_TR,
            ecodes.BTN_SELECT, ecodes.BTN_START, ecodes.BTN_MODE,
            ecodes.BTN_THUMBL, ecodes.BTN_THUMBR,
        ],
    }
    if with_ff:
        caps[ecodes.EV_FF] = _capacidades_ff(ecodes)
    return caps


def _capacidades_procon(*, with_ff: bool) -> dict[int, Any]:
    """Capabilities da máscara `nintendo` — e ela NÃO é a de cima.

    O TERCEIRO SABOR NÃO CABE NO CONJUNTO FIXO, e a prova é uma medição, não
    uma leitura. Com um nó `057e:2009` de pé usando as capabilities do
    `_capacidades_padrao`, a libSDL2 desta máquina aplicou (07/09/2026):

        a:b1,b:b0,back:b9,dpdown:h0.4,...,guide:b11,leftshoulder:b5,
        leftstick:b12,lefttrigger:b7,leftx:a0,lefty:a1,misc1:b4,
        rightshoulder:b6,rightstick:b13,righttrigger:b8,rightx:a2,righty:a3,
        start:b10,x:b2,y:b3

    A SDL casa a tabela dela pelo par VID/PID e **ignora os bytes de versão**
    do GUID — a hipótese de que a versão `0x3` do nosso nó nos deixaria fora do
    catálogo dela é FALSA, e foi medida como falsa. Com onze botões e seis
    eixos, aquela tabela lê o nó errado inteiro: `b11`, `b12` e `b13` não
    existem, `lefttrigger:b7` cai no `BTN_START`, e `rightx:a2` cai no
    **gatilho esquerdo**. O analógico direito ficaria colado no dedo do L2.

    O conjunto abaixo é o do aparelho de verdade, lido no fonte C em
    `assets/dkms/hid-nintendo/hid-nintendo.c` (`joycon_input_create:2432-2436`
    para o ramo `procon`):

    * **14 botões**, `procon_button_mappings:494-509` — e os 14 têm de ser
      DECLARADOS mesmo quando nunca são pressionados, porque `bN` é a POSIÇÃO
      na ordem de código: faltar um empurra todos os seguintes;
    * **`BTN_Z` (b4)** é o botão Capture, o `misc1` da tabela da SDL. Um
      DualSense não tem equivalente; ele nasce declarado e mudo, e é essa
      declaração que mantém `leftshoulder` em b5 e não em b4;
    * **sem `ABS_Z`/`ABS_RZ`** (`joycon_config_left_stick`/`_right_stick`
      registram só X/Y/RX/RY) — no Pro os gatilhos são digitais, e é por isso
      que a tabela da SDL diz `lefttrigger:b7`;
    * **HAT** (`joycon_config_dpad`), igual ao das outras duas máscaras.

    O PREÇO, DECLARADO E NÃO ESCONDIDO: **sob esta máscara o L2/R2 deixa de
    ser analógico.** O aparelho imitado não tem esse eixo; um jogo que leia
    aceleração progressiva do gatilho recebe ligado/desligado. Quem quer o
    gatilho adaptativo e a curva escolhe `dualsense` ou `xbox`.

    A ÚNICA divergência de propósito é o domínio dos eixos: 0-255 aqui, contra
    `-32767..32767` do Pro real (`JC_MAX_STICK_MAG`, `hid-nintendo.c:213`). A
    SDL normaliza pelo min/max que o próprio nó declara — foi assim que a
    máscara Xbox sempre funcionou com 0-255 contra o `xpad`, que usa signed —,
    e manter 0-255 evita mexer no domínio de valor do `forward_analog`, que é
    partilhado pelas três máscaras.
    """
    from evdev import AbsInfo, ecodes

    axis = AbsInfo(value=0, min=0, max=255, fuzz=0, flat=0, resolution=0)
    hat = AbsInfo(value=0, min=-1, max=1, fuzz=0, flat=0, resolution=0)
    caps: dict[int, list[Any]] = {
        ecodes.EV_ABS: [
            (ecodes.ABS_X, axis),
            (ecodes.ABS_Y, axis),
            (ecodes.ABS_RX, axis),
            (ecodes.ABS_RY, axis),
            (ecodes.ABS_HAT0X, hat),
            (ecodes.ABS_HAT0Y, hat),
        ],
        # Na ordem de CÓDIGO, que é a ordem em que a SDL os numera.
        ecodes.EV_KEY: [
            ecodes.BTN_SOUTH,    # 0x130  b0  <- B do Pro
            ecodes.BTN_EAST,     # 0x131  b1  <- A do Pro
            ecodes.BTN_NORTH,    # 0x133  b2  <- X do Pro
            ecodes.BTN_WEST,     # 0x134  b3  <- Y do Pro
            ecodes.BTN_Z,        # 0x135  b4  <- Capture (declarado e mudo)
            ecodes.BTN_TL,       # 0x136  b5  <- L
            ecodes.BTN_TR,       # 0x137  b6  <- R
            ecodes.BTN_TL2,      # 0x138  b7  <- ZL (gatilho DIGITAL)
            ecodes.BTN_TR2,      # 0x139  b8  <- ZR (gatilho DIGITAL)
            ecodes.BTN_SELECT,   # 0x13a  b9  <- Minus
            ecodes.BTN_START,    # 0x13b  b10 <- Plus
            ecodes.BTN_MODE,     # 0x13c  b11 <- Home
            ecodes.BTN_THUMBL,   # 0x13d  b12
            ecodes.BTN_THUMBR,   # 0x13e  b13
        ],
    }
    if with_ff:
        caps[ecodes.EV_FF] = _capacidades_ff(ecodes)
    return caps


class _FabricaDeCapacidades(Protocol):
    """A forma dos dois construtores de capabilities — `(*, with_ff)`.

    POR QUE UM PROTOCOL E NÃO `Callable[..., dict[int, Any]]`: as reticências
    dizem *"assinatura desconhecida"*, e sob `strict` o mypy trata chamar isso
    como chamar função sem tipo — `no-untyped-call` mais `no-any-return`, os
    dois no `construtor(with_ff=with_ff)` logo abaixo. `Callable` também não
    saberia escrever este par, porque os dois argumentos são SOMENTE-NOMEADOS e
    a forma `Callable[[bool], …]` é posicional.
    """

    def __call__(self, *, with_ff: bool) -> dict[int, Any]: ...


#: máscara -> construtor de capabilities. Fonte única, como o
#: :data:`BOTOES_POR_FLAVOR`.
CAPACIDADES_POR_FLAVOR: dict[str, _FabricaDeCapacidades] = {
    "dualsense": _capacidades_padrao,
    "xbox": _capacidades_padrao,
    "nintendo": _capacidades_procon,
}


def _build_capabilities(*, with_ff: bool, flavor: str = DEFAULT_FLAVOR) -> dict[int, Any]:
    """Capabilities da máscara `flavor`. Sabor desconhecido cai no padrão."""
    construtor = CAPACIDADES_POR_FLAVOR.get(flavor, _capacidades_padrao)
    return construtor(with_ff=with_ff)


@dataclass
class UinputGamepad:
    """Wrapper do device virtual. Lazy-creates no `start()`.

    O default mantém o flavor Xbox para retrocompatibilidade dos call-sites
    antigos; o daemon e a CLA usam `UinputGamepad.for_flavor("dualsense")`.
    """

    name: str = DEVICE_NAME
    vendor: int = XBOX360_VENDOR
    product: int = XBOX360_PRODUCT
    bustype: int = BUS_USB
    flavor: str = "xbox"
    #: FEAT-VPAD-FF-PASSTHROUGH-01: destino do rumble vindo do JOGO via FF.
    #: Recebe (weak, strong) já convertidos para 0-255; injetado por quem cria
    #: o vpad (gamepad.py → controle primário; coop.py → controle do jogador).
    #: None = FF aceito no handshake mas descartado (vpad "mudo").
    rumble_sink: Callable[[int, int], None] | None = None
    #: Relógio monotônico injetável (testes de expiração de duração).
    time_fn: Callable[[], float] = time.monotonic
    #: VPAD-05 — por que o flavor dualsense caiu NESTE backend (uinput), setado
    #: pela factory (`make_virtual_pad`): "uhid_indisponivel",
    #: "uhid_start_falhou", "uhid_bind_falhou" ou "uhid_vetado_pelo_chamador".
    #: None = uinput por design (máscara xbox), não é degradação. Exposto no
    #: `state_full` (`gamepad_emulation.degraded_motivo`) para GUI/doctor.
    fallback_motivo: str | None = None

    _device: Any = None
    #: Módulo `evdev.ecodes` (guardado no start p/ não reimportar por tick).
    _ecodes: Any = None
    _last_buttons: frozenset[str] = field(default_factory=frozenset)
    # PERF-MULTI-CONTROLLER-01: último sexteto analógico emitido — o forward
    # roda a cada tick (60Hz) por vpad; sem delta eram 7 writes/tick/vpad no
    # /dev/uinput mesmo com tudo parado.
    _last_axes: tuple[int, int, int, int, int, int] | None = None
    # -- estado FF (FEAT-VPAD-FF-PASSTHROUGH-01) -------------------------
    #: True quando o device nasceu com EV_FF (ambiente pode degradar sem FF).
    _ff_supported: bool = False
    #: id do efeito → (weak16, strong16, duração_ms) do último upload.
    _ff_effects: dict[int, tuple[int, int, int]] = field(default_factory=dict)
    #: id do efeito em reprodução → deadline monotônico. Efeito sem duração
    #: recebe `FF_TETO_SEM_DURACAO_S` em vez de infinito (ver a constante).
    _ff_playing: dict[int, float] = field(default_factory=dict)
    #: Ganho global (FF_GAIN, 0.0-1.0); SDL manda 0xFFFF (1.0) por padrão.
    _ff_gain: float = 1.0
    #: Último par (weak, strong) 0-255 entregue ao sink — o sink escreve HID,
    #: então só é chamado quando o par MUDOU (throttle por mudança).
    _ff_last_sent: tuple[int, int] = (0, 0)
    #: SPRINT-GAME-RUMBLE-01 — nº de "play" de FF que o JOGO pediu neste vpad
    #: desde a criação (diagnóstico: "o jogo mandou rumble? quantas vezes?").
    #: Incrementa em cada `_start_ff_effect` de efeito válido; exposto no
    #: state_full para a GUI/doctor confirmarem se o jogo enxerga o vpad.
    _ff_play_count: int = 0
    # --- MASCARA-XBOX-MUDA-01 (09/08/2026) ------------------------------
    #
    #: Nº de pares NÃO-NULOS que saíram para o `rumble_sink` — o irmão do
    #: `ff_nao_nulo_count` do caminho uhid.
    #:
    #: **Por que ele existe, e é defeito de verdade.** O painel da aba Rumble
    #: (`app/actions/rumble_actions.texto_dos_pedidos_de_vibracao`) pergunta
    #: `nao_nulos` ANTES de `plays`, e o `daemon/ipc_handlers` lê os dois com
    #: `getattr(vp, ..., 0)`. Como este backend nunca teve `ff_nao_nulo_count`,
    #: o zero do default virava afirmação: com a máscara **Xbox** funcionando
    #: perfeitamente, a tela dizia *"o jogo falou de vibração Nx, mas pediu
    #: força zero em todas"* — e a frase manda caçar no jogo/máscara, que é o
    #: lado oposto do código. Um modo inteiro do produto era, por construção,
    #: impossível de medir; e o número que ele mostrava acusava o inocente.
    #:
    #: A contagem é no `_refresh_ff`, no instante em que o par vai ao sink:
    #: é o mesmo ponto do caminho uhid (o PEDIDO do jogo em 0-255, antes do
    #: multiplicador da política) e, aqui, DEPOIS do ganho e do `>> 8` — que
    #: é honesto: um efeito de magnitude 200/65535 vira zero nos motores, e
    #: contá-lo como "pediu força" seria a mesma mentira ao contrário.
    _ff_nao_nulo_count: int = 0
    #: Maior par pedido (weak, strong) — "dava para SENTIR?". Comparado por
    #: intensidade (o maior motor, desempate pela soma) e nunca por ordem
    #: lexicográfica de tupla: `(0, 255)` é um pedido enorme e `(1, 0)` é
    #: imperceptível, mas `(1, 0) > (0, 255)` em Python.
    _ff_maior_pedido: tuple[int, int] = (0, 0)
    #: Play de efeito que nunca foi uploadado — pedido do jogo que NÃO virou
    #: vibração por falha nossa (catálogo perdido). Sem contá-lo, o descarte
    #: era invisível e a tela dizia "o jogo não pediu".
    _ff_descartado_count: int = 0

    @classmethod
    def for_flavor(
        cls,
        flavor: str | None = DEFAULT_FLAVOR,
        *,
        rumble_sink: Callable[[int, int], None] | None = None,
        identity: str | None = None,
    ) -> UinputGamepad:
        """Constrói o gamepad com a máscara (VID/PID/nome) do flavor dado.

        `rumble_sink` (FEAT-VPAD-FF-PASSTHROUGH-01) recebe o rumble do jogo
        já em 0-255 (weak, strong); ver docstring do campo.

        `identity` (MÁSCARA-POR-JOGADOR-01, 15/08/2026) é o MAC canônico do
        controle FÍSICO deste jogador — o mesmo que `discover_dualsense_evdevs`
        usa como chave. Quando ele vem, `flavor` deixa de ser a resposta e passa
        a ser o **padrão herdado**: a máscara que este aparelho escolheu vence
        (`external_mask.mascara_efetiva`), e sem escolha nada muda. `None` = o
        chamador não sabe de quem é o vpad, e aí a máscara é a do jogo, como
        sempre foi.
        """
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            mascara_efetiva,
        )

        key = mascara_efetiva(identity, flavor)
        spec = FLAVORS[key]
        return cls(
            name=spec["name"],
            vendor=spec["vendor"],
            product=spec["product"],
            flavor=key,
            rumble_sink=rumble_sink,
        )

    def start(self) -> bool:
        """Cria o device. Retorna False se /dev/uinput indisponível.

        FEAT-VPAD-FF-PASSTHROUGH-01: tenta criar COM force-feedback (EV_FF);
        em kernel/ambiente sem suporte, degrada para o vpad sem FF (o jogo
        não vibra, input segue funcionando) — nunca crasha.
        """
        if self._device is not None:
            return True
        try:
            from evdev import ecodes
        except ImportError:
            logger.warning("python-evdev não instalado — emulação de gamepad indisponível")
            return False
        device = self._create_device(with_ff=True)
        if device is not None:
            self._ff_supported = True
        else:
            device = self._create_device(with_ff=False)
            if device is None:
                return False
            self._ff_supported = False
            logger.warning("uinput_ff_indisponivel_vpad_sem_rumble", name=self.name)
        self._device = device
        self._ecodes = ecodes
        logger.info("uinput_device_created", name=self.name, flavor=self.flavor,
                    vendor=hex(self.vendor), product=hex(self.product),
                    ff=self._ff_supported)
        return True

    def _create_device(self, *, with_ff: bool) -> Any | None:
        """Cria o UInput do python-evdev; None em falha (o start decide o fallback)."""
        from evdev import UInput

        try:
            return UInput(
                _build_capabilities(with_ff=with_ff, flavor=self.flavor),
                name=self.name,
                vendor=self.vendor,
                product=self.product,
                version=DEVICE_VERSION,
                bustype=self.bustype,
                max_effects=MAX_FF_EFFECTS if with_ff else 0,
            )
        except Exception as exc:
            logger.warning("uinput_device_create_failed", err=str(exc), ff=with_ff)
            return None

    def stop(self) -> None:
        if self._device is None:
            return
        # FEAT-VPAD-FF-PASSTHROUGH-01: se o FF do jogo deixou motor ligado,
        # zera o rumble físico antes de fechar (o vpad some; ninguém mais
        # mandaria o stop e o DualSense ficaria vibrando).
        if self._ff_last_sent != (0, 0) and self.rumble_sink is not None:
            with contextlib.suppress(Exception):
                self.rumble_sink(0, 0)
        with contextlib.suppress(Exception):
            self._device.close()
        self._device = None
        self._ecodes = None
        self._last_buttons = frozenset()
        self._last_axes = None
        self._ff_supported = False
        self._ff_effects.clear()
        self._ff_playing.clear()
        self._ff_gain = 1.0
        self._ff_last_sent = (0, 0)
        self._ff_play_count = 0
        self._ff_nao_nulo_count = 0
        self._ff_maior_pedido = (0, 0)
        self._ff_descartado_count = 0

    def is_active(self) -> bool:
        return self._device is not None

    @property
    def ff_supported(self) -> bool:
        """True se o device virtual nasceu com EV_FF (rumble do jogo roteável)."""
        return self._ff_supported

    @property
    def ff_play_count(self) -> int:
        """Nº de play de FF que o JOGO pediu neste vpad (diagnóstico de rumble)."""
        return self._ff_play_count

    @property
    def ff_nao_nulo_count(self) -> int:
        """Nº de pedidos com FORÇA — os que fariam o motor mexer.

        MASCARA-XBOX-MUDA-01. Este é o número que a aba Rumble pergunta
        primeiro; sem ele a máscara Xbox respondia zero por ausência e a tela
        acusava o jogo de pedir silêncio. Ver o campo `_ff_nao_nulo_count`.
        """
        return self._ff_nao_nulo_count

    @property
    def ff_maior_pedido(self) -> tuple[int, int]:
        """Maior par (weak, strong) pedido pelo jogo — "dava para sentir?"."""
        return self._ff_maior_pedido

    @property
    def ff_descartado_count(self) -> int:
        """Nº de play de efeito que NÃO tínhamos no catálogo (perdido por nós)."""
        return self._ff_descartado_count

    @property
    def ff_last_sent(self) -> tuple[int, int]:
        """Último par (weak, strong) 0-255 entregue ao sink (rumble do jogo)."""
        return self._ff_last_sent

    @property
    def backend(self) -> str:
        """Sempre "uinput": device de evdev (sem hidraw). É o backend da máscara
        Xbox 360 e o fallback do flavor dualsense quando o uhid não sobe. Mesmo
        degradado o PID é o Edge 0x0df2 (invariante VPAD-06 — nunca o 0ce6 do
        físico), mas sem hidraw o mapeamento SDL desse GUID nunca foi validado:
        o botão de Launch Options usa isto para NÃO anunciar IGNORE_DEVICES no
        ramo degradado (plano B da refutação nº 2 do sprint doc)."""
        return "uinput"

    def forward_analog(
        self,
        *,
        lx: int,
        ly: int,
        rx: int,
        ry: int,
        l2: int,
        r2: int,
    ) -> None:
        """Aplica valores analógicos no device virtual (só o que MUDOU).

        PERF-MULTI-CONTROLLER-01: emite apenas os eixos com valor novo e o SYN
        só quando algo foi emitido. Sticks parados = zero writes (o kernel de
        qualquer forma descartaria ABS repetido, mas o write/syscall era pago).
        """
        if self._device is None or self._ecodes is None:
            return
        axes = (lx, ly, rx, ry, l2, r2)
        last = self._last_axes
        if axes == last:
            return
        ec = self._ecodes
        if self.flavor == "nintendo":
            self._forward_analog_procon(axes, last, ec)
            return
        codes = (ec.ABS_X, ec.ABS_Y, ec.ABS_RX, ec.ABS_RY, ec.ABS_Z, ec.ABS_RZ)
        emitted = False
        for idx, code in enumerate(codes):
            if last is None or axes[idx] != last[idx]:
                self._device.write(ec.EV_ABS, code, axes[idx])
                emitted = True
        if emitted:
            self._device.syn()
        self._last_axes = axes

    def _forward_analog_procon(
        self,
        axes: tuple[int, int, int, int, int, int],
        last: tuple[int, int, int, int, int, int] | None,
        ec: Any,
    ) -> None:
        """O mesmo trabalho sob a máscara `nintendo`: 4 eixos + 2 botões.

        O Pro não tem `ABS_Z`/`ABS_RZ` (ver :func:`_capacidades_procon`), então
        L2 e R2 saem por `BTN_TL2`/`BTN_TR2`. **Este é o único escritor desses
        dois códigos** — `BOTOES_PROCON` não os tem de propósito — porque um
        código com dois escritores é um código cujo estado ninguém sabe.

        A conversão é por histerese (:data:`LIMIAR_GATILHO_PRESSIONADO` /
        :data:`LIMIAR_GATILHO_SOLTO`): o valor anterior decide o limiar de
        agora, e um dedo parado em cima do ponto não emite nada.
        """
        emitido = False
        for idx, code in enumerate((ec.ABS_X, ec.ABS_Y, ec.ABS_RX, ec.ABS_RY)):
            if last is None or axes[idx] != last[idx]:
                self._device.write(ec.EV_ABS, code, axes[idx])
                emitido = True
        for idx, code in ((4, ec.BTN_TL2), (5, ec.BTN_TR2)):
            antes = self._gatilho_apertado(last[idx], False) if last else False
            agora = self._gatilho_apertado(axes[idx], antes)
            if agora != antes:
                self._device.write(ec.EV_KEY, code, 1 if agora else 0)
                emitido = True
        if emitido:
            self._device.syn()
        self._last_axes = axes

    @staticmethod
    def _gatilho_apertado(valor: int, antes: bool) -> bool:
        """O gatilho analógico (0-255) como bit, com histerese."""
        if antes:
            return valor > LIMIAR_GATILHO_SOLTO
        return valor >= LIMIAR_GATILHO_PRESSIONADO

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        """Aplica set de botões pressionados. Diff com último snapshot."""
        if self._device is None or self._ecodes is None:
            return

        newly_pressed = pressed - self._last_buttons
        newly_released = self._last_buttons - pressed

        dpad_x, dpad_y = self._dpad_vector(pressed)
        last_dpad_x, last_dpad_y = self._dpad_vector(self._last_buttons)

        ec = self._ecodes
        for name in newly_pressed:
            code = self._resolve_evdev(name, ec)
            if code is not None:
                self._device.write(ec.EV_KEY, code, 1)
        for name in newly_released:
            code = self._resolve_evdev(name, ec)
            if code is not None:
                self._device.write(ec.EV_KEY, code, 0)

        if dpad_x != last_dpad_x:
            self._device.write(ec.EV_ABS, ec.ABS_HAT0X, dpad_x)
        if dpad_y != last_dpad_y:
            self._device.write(ec.EV_ABS, ec.ABS_HAT0Y, dpad_y)

        self._device.syn()
        self._last_buttons = frozenset(pressed)

    def _resolve_evdev(self, hefesto_name: str, ecodes_mod: Any) -> int | None:
        tabela = BOTOES_POR_FLAVOR.get(self.flavor, BUTTON_TO_UINPUT)
        if hefesto_name in tabela:
            key = tabela[hefesto_name]
            code = getattr(ecodes_mod, key, None)
            return int(code) if isinstance(code, int) else None
        # l2_btn / r2_btn digital viram triggers (ABS nas máscaras dualsense e
        # xbox, BTN_TL2/BTN_TR2 na nintendo) — os dois casos no forward_analog.
        return None

    # -- force-feedback (FEAT-VPAD-FF-PASSTHROUGH-01) ---------------------

    def pump_ff(self) -> None:
        """Drena o protocolo de FF do vpad e repassa o rumble do jogo ao sink.

        Não-bloqueante; chamado a cada tick do poll loop. Três papéis:
          1. upload/erase (EV_UINPUT): responde o handshake obrigatório do
             kernel (begin/end) e mantém o catálogo local de efeitos
             (id → magnitudes + duração);
          2. play/stop (EV_FF): liga/desliga efeitos (value = nº de
             repetições; 0 = stop) e captura FF_GAIN;
          3. expiração: zera o rumble quando a duração venceu (jogos que dão
             play sem nunca mandar stop).
        Vpad sem FF (degradado) ou parado = no-op.
        """
        device = self._device
        if device is None or not self._ff_supported:
            return
        for _ in range(_FF_MAX_EVENTS_PER_PUMP):
            try:
                event = device.read_one()
            except (BlockingIOError, OSError):
                break  # sem eventos pendentes / fd em estado transitório
            if event is None:
                break
            try:
                self._handle_ff_event(event)
            except Exception as exc:
                logger.warning("vpad_ff_event_failed", err=str(exc))
        self._refresh_ff()

    def _handle_ff_event(self, event: Any) -> None:
        """Trata UM evento vindo do fd do uinput (handshake FF ou play/stop)."""
        ec = self._ecodes
        etype = int(event.type)
        code = int(event.code)
        value = int(event.value)
        if etype == ec.EV_UINPUT and code == ec.UI_FF_UPLOAD:
            upload = self._device.begin_upload(value)
            effect = upload.effect
            # Re-upload do mesmo id ATUALIZA o efeito (jogos "reprogramam" o
            # efeito em vez de criar outro); o deadline de um play em curso
            # não muda, só as magnitudes.
            self._ff_effects[int(effect.id)] = self._parse_ff_effect(effect)
            upload.retval = 0
            self._device.end_upload(upload)
        elif etype == ec.EV_UINPUT and code == ec.UI_FF_ERASE:
            erase = self._device.begin_erase(value)
            effect_id = int(erase.effect_id)
            self._ff_effects.pop(effect_id, None)
            self._ff_playing.pop(effect_id, None)
            erase.retval = 0
            self._device.end_erase(erase)
        elif etype == ec.EV_FF and code == ec.FF_GAIN:
            self._ff_gain = max(0, min(0xFFFF, value)) / 0xFFFF
        elif etype == ec.EV_FF:
            # code = id do efeito (< MAX_FF_EFFECTS, nunca colide com FF_GAIN).
            if value > 0:
                self._start_ff_effect(code, repeats=value)
            else:
                self._ff_playing.pop(code, None)
        # Demais eventos no fd (ex.: eco de EV_SYN) são ignorados.

    def _parse_ff_effect(self, effect: Any) -> tuple[int, int, int]:
        """Extrai (weak16, strong16, duração_ms) de um efeito FF do kernel.

        Conversões (documentadas):
          - FF_RUMBLE: magnitudes 0-65535 dos dois motores, direto do efeito.
          - FF_PERIODIC: UMA magnitude signed (pico da onda, 0-32767) —
            usamos ``|magnitude| * 2`` nos DOIS motores (aproximação padrão de
            quem só tem rumble; é o que a SDL espera).
          - Tipo não suportado: (0, 0) — aceito no handshake (retval 0) mas
            mudo, sem quebrar o jogo.
        A duração vem de `ff_replay.length` (ms; 0 = toca até o stop). O
        `ff_replay.delay` é ignorado (raro; SDL não usa).
        """
        ec = self._ecodes
        duration_ms = int(effect.ff_replay.length)
        etype = int(effect.type)
        if etype == ec.FF_RUMBLE:
            rumble = effect.u.ff_rumble_effect
            weak = int(rumble.weak_magnitude) & 0xFFFF
            strong = int(rumble.strong_magnitude) & 0xFFFF
            return (weak, strong, duration_ms)
        if etype == ec.FF_PERIODIC:
            magnitude = min(0xFFFF, abs(int(effect.u.ff_periodic_effect.magnitude)) * 2)
            return (magnitude, magnitude, duration_ms)
        return (0, 0, duration_ms)

    def _start_ff_effect(self, effect_id: int, *, repeats: int) -> None:
        """Marca o efeito como tocando, com deadline = duração x repetições."""
        params = self._ff_effects.get(effect_id)
        if params is None:
            # MASCARA-XBOX-MUDA-01: play de efeito nunca uploadado é um pedido
            # do jogo que NÃO vira vibração — descartar é certo (não há o que
            # tocar), descartar EM SILÊNCIO não é. Sem o contador, a tela
            # afirmava "o jogo não pediu" sem ter como saber.
            self._ff_descartado_count += 1
            return
        duration_ms = params[2]
        if duration_ms <= 0:
            # Duração 0 significa "toca até o jogo mandar parar" (semântica do
            # kernel). O deadline era `math.inf`, então o ÚNICO jeito de o motor
            # parar era o jogo enviar stop/erase — e se ele fecha no meio de uma
            # vibração, trava, ou o evento se perde, o controle fica vibrando
            # para sempre. Relatado ao vivo: "não parava por nada".
            #
            # O teto não corta vibração legítima: qualquer novo play do MESMO
            # efeito renova o prazo, e jogos que vibram continuamente ficam
            # remandando efeito enquanto a cena dura. Ele só age quando o jogo
            # PAROU de pedir sem dizer que parou.
            deadline = self.time_fn() + FF_TETO_SEM_DURACAO_S
        else:
            deadline = self.time_fn() + (duration_ms * max(1, repeats)) / 1000.0
        self._ff_playing[effect_id] = deadline
        # SPRINT-GAME-RUMBLE-01: instrumentação — um play de efeito válido = o
        # jogo pediu rumble neste vpad. Se o contador fica em 0 durante o jogo,
        # o jogo NÃO enxerga o vpad (ex.: máscara DualSense atraindo o hidraw
        # do físico); se sobe mas o controle não vibra, o elo é o sink/hardware.
        self._ff_play_count += 1

    def _refresh_ff(self) -> None:
        """Expira efeitos vencidos e entrega o rumble alvo ao sink (se mudou).

        Efeitos simultâneos SOMAM magnitude (clamp em 0xFFFF) — espelha o
        ff-memless do kernel. Conversão 0-65535 → 0-255 por `>> 8`.
        """
        now = self.time_fn()
        for effect_id in [i for i, deadline in self._ff_playing.items() if now >= deadline]:
            del self._ff_playing[effect_id]
        weak_total = 0
        strong_total = 0
        for effect_id in self._ff_playing:
            params = self._ff_effects.get(effect_id)
            if params is None:
                continue
            weak_total += params[0]
            strong_total += params[1]
        gain = self._ff_gain
        weak = min(0xFFFF, int(weak_total * gain)) >> 8
        strong = min(0xFFFF, int(strong_total * gain)) >> 8
        pair = (weak, strong)
        if pair == self._ff_last_sent:
            return
        # MASCARA-XBOX-MUDA-01: as duas perguntas que a aba Rumble faz — "o
        # jogo pediu FORÇA?" e "dava para sentir?" — respondidas no MESMO
        # ponto em que o par vai ao sink. Antes do dedup não serve: um jogo
        # que reafirma o mesmo valor 60x/s inflaria a contagem; depois dele,
        # cada número é uma mudança real de pedido, igual ao caminho uhid.
        if weak or strong:
            self._ff_nao_nulo_count += 1
            self._ff_maior_pedido = pedido_mais_forte(self._ff_maior_pedido, pair)
        self._ff_last_sent = pair
        sink = self.rumble_sink
        if sink is None:
            return
        try:
            sink(weak, strong)
        except Exception as exc:
            logger.warning("vpad_ff_sink_failed", err=str(exc))

    @staticmethod
    def _dpad_vector(pressed: frozenset[str]) -> tuple[int, int]:
        x = 0
        y = 0
        if "dpad_left" in pressed:
            x = -1
        elif "dpad_right" in pressed:
            x = 1
        if "dpad_up" in pressed:
            y = -1
        elif "dpad_down" in pressed:
            y = 1
        return x, y


__all__ = [
    "BOTOES_POR_FLAVOR",
    "BOTOES_PROCON",
    "BUS_USB",
    "BUTTON_TO_UINPUT",
    "CAPACIDADES_POR_FLAVOR",
    "DEFAULT_FLAVOR",
    "DEVICE_NAME",
    "DEVICE_VERSION",
    "DUALSENSE_EDGE_NAME",
    "DUALSENSE_EDGE_PRODUCT",
    "DUALSENSE_NAME",
    "DUALSENSE_PRODUCT",
    "DUALSENSE_VENDOR",
    "FLAVORS",
    "FLAVOR_SINONIMOS",
    "LIMIAR_GATILHO_PRESSIONADO",
    "LIMIAR_GATILHO_SOLTO",
    "MAX_FF_EFFECTS",
    "NINTENDO_PROCON_NAME",
    "NINTENDO_PROCON_PRODUCT",
    "NINTENDO_VENDOR",
    "XBOX360_NAME",
    "XBOX360_PRODUCT",
    "XBOX360_VENDOR",
    "UinputGamepad",
    "nomes_de_flavor_aceitos",
    "normalize_flavor",
    "resolver_flavor",
]
