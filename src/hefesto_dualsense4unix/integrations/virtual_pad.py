"""Contrato comum dos gamepads virtuais + escolha do backend (SPRINT-UHID-VPAD-01).

Existem dois backends de vpad, e os call sites (`subsystems/gamepad.py` para o P1,
`subsystems/coop.py` para os secundários) não devem saber em qual estão:

  - `UinputGamepad` (/dev/uinput): só evdev. É o que faz a máscara **Xbox 360**,
    e é o caminho histórico — intacto.
  - `UhidDualSense` (/dev/uhid): device **HID** de verdade. O `hid_playstation`
    faz bind nele e o vpad ganha hidraw + lightbar + player-LED + motion sensors
    + touchpad. É o que faz a máscara **DualSense finalmente vibrar** no jogo (com
    uinput ela é evdev-only, o SDL usa o driver PS5, procura o hidraw, não acha, e
    o rumble morre — a razão de a máscara Xbox ter virado obrigatória).

`VirtualPad` é a interface que os dois cumprem; `make_virtual_pad` decide qual usar
e **já devolve o pad startado** — é ali que mora o fallback, num lugar só.

Por que o fallback vive na factory
----------------------------------
O caminho uhid tem três pontos de falha (nó ausente/sem regra udev, CREATE2
recusado, `hid_playstation` que não faz bind) e todos significam a mesma coisa
para o chamador: **use o uinput**. Espalhar isso pelos call sites daria uma
versão diferente do fallback em cada um. Cada motivo é logado (não silenciado):
"caiu no uinput" sem dizer por quê é um bug que a usuária sente no jogo e
ninguém consegue diagnosticar.

Blueprint canônico embutido (VPAD-03 / BT-01)
---------------------------------------------
O vpad uhid usa SEMPRE o blueprint sintético de `uhid_blueprint.py` — nenhuma
leitura do controle físico no caminho de criação. O modo de falha "controle
físico sem hidraw legível" morreu por construção: era ele que, em BT com o
controle ocioso (GET_REPORT estourando o timeout de 5 s do hidp com EIO),
derrubava o vpad para uinput `054c:0ce6` — indistinguível do físico e alvo da
launch option `IGNORE_DEVICES` persistida na Steam (jogo com zero controles).
O vpad sobe uhid Edge até sem controle conectado (boot antes do connect).

`allow_uhid=False` é o veto explícito do chamador (VPAD-08): o daemon FAKE
(`run.sh --fake`, usado em smoke na máquina da usuária) não pode registrar um
DualSense Edge REAL no kernel — a Steam enxergaria um controle fantasma.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

UHID_BIND_TIMEOUT_S = 0.5

# controle chega — o `uhid` (o relatório do DualSense, por onde voltam
# O `uhid` só se constrói com máscara DualSense: *"o `hid_playstation` só faz
# PRAGMATA segurou só o mouse e o teclado com quatro Edge `uinput`, e o Future
CAMINHO_DUALSENSE = "dualsense"
CAMINHO_XBOX = "xbox"
CAMINHOS: tuple[str, ...] = (CAMINHO_DUALSENSE, CAMINHO_XBOX)

MASCARA_DO_CANAL_COMUM = "xbox"


def normalizar_caminho(valor: object) -> str | None:
    """O caminho reconhecido, ou ``None`` — e ``None`` é *"ninguém escolheu"*."""
    if isinstance(valor, str):
        limpo = valor.strip().lower()
        if limpo in CAMINHOS:
            return limpo
    return None


def caminho_resolvido(caminho: object, mascara: object) -> str:
    """O caminho que vale: o escolhido, ou — sem escolha — o que sai da máscara."""
    escolhido = normalizar_caminho(caminho)
    if escolhido is not None:
        return escolhido
    return CAMINHO_DUALSENSE if mascara == "dualsense" else CAMINHO_XBOX


def quer_uhid(caminho: object, mascara: object) -> bool:
    """Este par (caminho, máscara) pede o vpad `uhid`?

    As duas metades, juntas: o caminho DualSense E a máscara DualSense. É a
    única pergunta que decide o backend, e mora aqui para o P1
    (`gamepad.start_gamepad_emulation_desfecho`) e os secundários
    (`external_mask.vpad_ficou_para_tras`) não a responderem cada um do seu jeito.
    """
    return mascara == "dualsense" and caminho_resolvido(caminho, mascara) == CAMINHO_DUALSENSE


def mascara_no_jogo(caminho: object, mascara: str) -> str:
    """O aparelho que o JOGO vê para este par (caminho, máscara).

    A regra de NO-MODO-XBOX-TUDO-FUNCIONA-01, e o dono dela é este: com o modo
    Xbox ESCOLHIDO, o jogo vê o Xbox 360 em qualquer máscara; nos outros casos,
    vê a máscara. A combinação «modo Xbox + máscara DualSense ou Nintendo no
    `uinput`, sem hidraw» não nasce, porque o jogo sob o Proton não a usa.

    SÓ O CAMINHO ESCOLHIDO, nunca o resolvido: sem escolha, a máscara Nintendo
    resolve para o caminho Xbox (:func:`caminho_resolvido`, o produto de antes
    de 13/09) e continua sendo o Pro, que é o que a tela mostra com o modo de
    fábrica aceso.
    """
    if normalizar_caminho(caminho) == CAMINHO_XBOX:
        return MASCARA_DO_CANAL_COMUM
    return mascara


def caminho_do_vpad(vpad: object) -> str | None:
    """O caminho em que ESTE vpad nasceu — ``None`` quando ele não sabe dizer.

    A factory pendura o caminho no pad que devolve. Um vpad sem o atributo
    (dublê de régua, ou um pad de antes desta cura) só responde pelo backend:
    `uhid` é o caminho DualSense; `uinput` sozinho não diz se foi escolhido ou
    degradado, e aí a resposta honesta é ``None`` — o chamador resolve pela
    máscara, que é o produto de antes.
    """
    escolhido = normalizar_caminho(getattr(vpad, "caminho", None))
    if escolhido is not None:
        return escolhido
    if getattr(vpad, "backend", None) == "uhid":
        return CAMINHO_DUALSENSE
    return None


def motivo_da_degradacao(vpad: object) -> str | None:
    """Por que ESTE vpad caiu do canal que pediu — ``None`` quando não caiu.

    Degradado é uma coisa só: a máscara DualSense no ``uinput`` quando o caminho
    é o do DualSense. O caminho Xbox no ``uinput`` é escolha dela (PS-L3-MASCARA-01),
    e a máscara que o ``uhid`` não veste também não é queda. O modo, a máscara e
    a forma de conexão são três eixos, e esta é a única pergunta que junta os
    dois primeiros para dizer «degradou»: o diário (``vpad_degradado``), o
    estado (``vpad_motivo``, ``degraded``) e o ``dedup_status`` a fazem aqui.

    O motivo é o que a fábrica pendurou (``fallback_motivo``), com ``sem_uhid``
    de piso para o pad que não sabe dizer. Pad sem caminho resolve pela máscara,
    como :func:`caminho_do_vpad` manda.
    """
    mascara = getattr(vpad, "flavor", None)
    if mascara != "dualsense" or getattr(vpad, "backend", None) != "uinput":
        return None
    if caminho_resolvido(caminho_do_vpad(vpad), mascara) == CAMINHO_XBOX:
        return None
    motivo = getattr(vpad, "fallback_motivo", None)
    return motivo if isinstance(motivo, str) and motivo else "sem_uhid"


def _pendurar_o_caminho(pad: object, caminho: str) -> None:
    """Grava no pad o caminho em que ele nasceu. Best-effort: nunca derruba."""
    try:
        pad.caminho = caminho  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        logger.debug("vpad_sem_lugar_para_o_caminho", caminho=caminho)


def _vestir_o_aparelho(pad: object, aparelho: str, *, mascara: str, player: int) -> None:
    """Veste o pad ainda não criado com o aparelho que o jogo usa."""
    vestir = getattr(pad, "vestir", None)
    if not callable(vestir):
        logger.debug("vpad_sem_como_vestir", aparelho=aparelho, player=player)
        return
    vestir(aparelho)
    logger.info("vpad_vestido_pelo_modo", mascara=mascara, no_jogo=aparelho,
                player=player)


@runtime_checkable
class VirtualPad(Protocol):
    """O que o daemon usa de um gamepad virtual, seja ele uinput ou uhid."""

    @property
    def flavor(self) -> str:
        """A máscara deste pad: "dualsense", "xbox" ou "nintendo"."""
        ...

    @property
    def backend(self) -> str:
        """"uinput" (evdev, máscara Xbox / fallback) ou "uhid" (DualSense HID real,
        Edge 0x0DF2). O botão de Launch Options escolhe a variante por aqui: só o
        "uhid" tem PID próprio e pode ser desduplicado por IGNORE_DEVICES."""
        ...

    @property
    def ff_supported(self) -> bool:
        """True quando o rumble do jogo tem por onde chegar até nós."""
        ...

    @property
    def ff_play_count(self) -> int:
        """Nº de pedidos de rumble que o JOGO fez neste vpad (diagnóstico)."""
        ...

    @property
    def ff_nao_nulo_count(self) -> int:
        """Nº de pedidos com FORÇA — os que fariam o motor mexer."""
        ...

    @property
    def ff_maior_pedido(self) -> tuple[int, int]:
        """Maior par (weak, strong) que o jogo pediu — "dava para SENTIR?"."""
        ...

    @property
    def ff_descartado_count(self) -> int:
        """Nº de pedidos do jogo que NÃO viraram vibração por falha nossa."""
        ...

    @property
    def ff_last_sent(self) -> tuple[int, int]:
        """Último par (weak, strong) 0-255 entregue ao `rumble_sink`."""
        ...

    def start(self) -> bool: ...

    def stop(self) -> None: ...

    def is_active(self) -> bool: ...

    def forward_analog(
        self, *, lx: int, ly: int, rx: int, ry: int, l2: int, r2: int
    ) -> None: ...

    def forward_buttons(self, pressed: frozenset[str]) -> None: ...

    def pump_ff(self) -> None: ...


def make_virtual_pad(
    flavor: str | None,
    *,
    identity: str | None = None,
    rumble_sink: Callable[[int, int], None] | None = None,
    trigger_sink: Callable[[str, bytes], None] | None = None,
    lightbar_sink: Callable[[int, int, int], None] | None = None,
    player_led_sink: Callable[[tuple[bool, bool, bool, bool, bool]], None]
    | None = None,
    session_end_sink: Callable[[], None] | None = None,
    player: int = 1,
    allow_uhid: bool = True,
    calibration_0x05: bytes | None = None,
    caminho: str | None = None,
    mic_led_sink: Callable[[int | None], bool | None] | None = None,
    mic_mute_sink: Callable[[bool], bool | None] | None = None,
) -> VirtualPad | None:
    """Cria e **starta** o vpad do jogador `player`. None = nenhum backend subiu.

    MODO-DE-CONEXAO-01 (13/09/2026): `caminho` é o MODO que ela escolheu
    (`CAMINHO_DUALSENSE` · `CAMINHO_XBOX`, ou ``None`` = ninguém escolheu). O
    uhid só é tentado com o caminho DualSense **e** a máscara efetiva DualSense
    (:func:`quer_uhid`); o caminho Xbox vai direto ao uinput, e isso não é
    degradação — é a escolha dela. O pad devolvido carrega o caminho em que
    nasceu (`pad.caminho`), que é o que o laço do co-op compara.

    NO-MODO-XBOX-TUDO-FUNCIONA-01 (28/09/2026): no caminho Xbox escolhido o
    pad nasce Xbox 360 em toda máscara (:func:`mascara_no_jogo`), para o P1 e
    para os secundários, no cabo e no rádio — esta fábrica não tem ramo de
    jogador nem de transporte. O `flavor` do pad continua sendo a máscara do
    cartão, que é o que os juízes de recriação comparam; como o aparelho é
    função do par (caminho, máscara) e os dois já são comparados, nenhum juiz
    recria em laço.

    Prefere o uhid quando tudo se alinha (máscara DualSense + /dev/uhid usável +
    permissão do chamador em `allow_uhid`); qualquer tropeço cai no
    `UinputGamepad`, que continua sendo o backend do Xbox 360 e o piso de
    compatibilidade. O blueprint é SEMPRE o canônico embutido
    (`uhid_blueprint.canonical_blueprint`) — o vpad não depende de controle
    físico conectado, nem de hidraw legível (VPAD-03/BT-01).

    REPLICA-03: os sinks de gatilho/lightbar/player-LED/fim-de-sessão replicam
    o output do JOGO ao controle físico — são exclusivos do backend uhid (o
    uinput é evdev-only: FF é o único output que chega até ele), então no
    fallback eles são deliberadamente descartados. O mesmo vale para os dois
    do microfone (A-LUZ-E-O-MUDO-DO-MICROFONE-OBEDECEM-AO-JOGO-01): o pad Xbox
    360 não tem luz nem mudo de microfone no protocolo.

    `allow_uhid=False` (VPAD-08): o chamador declara "sem uhid" quando o backend
    do controle é o fake (`run.sh --fake`) — um vpad uhid é um DualSense Edge
    REAL no kernel, visível pela Steam, e o smoke não pode plantar um.

    GYRO-01: `calibration_0x05` é o feature 0x05 lido do controle FÍSICO deste
    jogador (`backend.read_calibration`) — quando presente e íntegro, o vpad o
    carimba no blueprint no lugar do canônico, para o motion espelhado ser
    calibrado com a unidade certa. None/inválido = canônico (fallback fail-safe;
    o vpad nasce do mesmo jeito). Exclusivo do backend uhid, como os sinks.

    MÁSCARA-POR-JOGADOR-01 (o degrau que faltava desde 15/08, ligado em
    29/08/2026): `identity` é o MAC canônico do controle FÍSICO deste jogador —
    o mesmo que `core.evdev_reader.discover_dualsense_evdevs` devolve e que
    `backend.primary_uniq` dá para o P1. Quando ele vem, `flavor` deixa de ser a
    resposta e passa a ser o **padrão herdado**: a máscara que ESTE aparelho
    escolheu vence (`external_mask.mascara_efetiva`), e sem escolha registrada
    nada muda. `None` = o chamador não sabe de quem é o vpad, e aí a máscara é a
    do jogo, como sempre foi — o contrato histórico, intacto.

    A RESOLUÇÃO É AQUI, E ANTES DO BACKEND — a armadilha que
    `external_mask.py:68-77` descreveu para quem escrevesse este degrau: o gate
    do `_try_uhid` (*"não é dualsense, logo não é meu"*) decide pela máscara que
    RECEBE. Se ele continuasse recebendo a do JOGO, um jogador que escolheu
    `dualsense` numa sessão `xbox` teria o uhid vetado e cairia no uinput com
    máscara DualSense — o par degradado em que a vibração do jogo morre
    (VPAD-05/SPRINT-GAME-RUMBLE-01). Por isso `key` já é a máscara EFETIVA daqui
    para baixo, e os backends recebem só ela: uma leitura do registro por vpad,
    e nenhuma janela entre a decisão da factory e a do backend em que o registro
    possa mudar e os dois discordarem sobre quem é este controle
    (`mascara_efetiva` é idempotente — de uma máscara já efetiva devolve ela
    mesma).

    **E `identity` PASSA adiante desde COOP-QUE-NÃO-DESMONTA-01/E3
    (06/09/2026).** O parágrafo acima terminava dizendo que não passá-la não
    perdia nada, e era verdade enquanto ela só decidia máscara. Deixou de ser:
    o MAC do vpad uhid agora é ancorado nela (`uhid_gamepad.vpad_mac`), para o
    controle físico não trocar de MAC quando o número do jogador é reciclado.
    Sem o repasse, a cura parava aqui — na factory — e não chegava ao produto.
    """
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva
    from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad

    key = mascara_efetiva(identity, flavor)
    resolvido = caminho_resolvido(caminho, key)
    motivo: str | None = None
    if not quer_uhid(caminho, key):
        # escolha, sem `motivo` — o `state_full` não o chama de degradado.
        pass
    elif allow_uhid:
        uhid, motivo = _try_uhid(
            key,
            rumble_sink=rumble_sink,
            trigger_sink=trigger_sink,
            lightbar_sink=lightbar_sink,
            player_led_sink=player_led_sink,
            session_end_sink=session_end_sink,
            player=player,
            identity=identity,
            calibration_0x05=calibration_0x05,
            mic_led_sink=mic_led_sink,
            mic_mute_sink=mic_mute_sink,
        )
        if uhid is not None:
            _pendurar_o_caminho(uhid, resolvido)
            return uhid
    else:
        motivo = "uhid_vetado_pelo_chamador"
        logger.info("vpad_uhid_vetado_pelo_chamador_usando_uinput", player=player)
    pad = UinputGamepad.for_flavor(key, rumble_sink=rumble_sink)
    aparelho = mascara_no_jogo(caminho, key)
    if aparelho != key:
        _vestir_o_aparelho(pad, aparelho, mascara=key, player=player)
    if motivo is not None:
        # `state_full` o expõe (`gamepad_emulation.degraded_motivo`) para a
        pad.fallback_motivo = motivo
    if not pad.start():
        return None
    _pendurar_o_caminho(pad, resolvido)
    return pad


def _try_uhid(
    flavor: str,
    *,
    rumble_sink: Callable[[int, int], None] | None,
    trigger_sink: Callable[[str, bytes], None] | None = None,
    lightbar_sink: Callable[[int, int, int], None] | None = None,
    player_led_sink: Callable[[tuple[bool, bool, bool, bool, bool]], None]
    | None = None,
    session_end_sink: Callable[[], None] | None = None,
    player: int,
    identity: str | None = None,
    calibration_0x05: bytes | None = None,
    mic_led_sink: Callable[[int | None], bool | None] | None = None,
    mic_mute_sink: Callable[[bool], bool | None] | None = None,
) -> tuple[VirtualPad | None, str | None]:
    """Tenta o backend uhid; ``(None, motivo)`` = "use o uinput".

    O motivo vai ao log (como sempre foi) E volta ao chamador (VPAD-05): a
    factory o pendura no vpad uinput degradado para o `state_full` expor.
    ``(None, None)`` só no flavor xbox — uinput por design, não degradação.

    `identity` (E3) chega já resolvida em máscara pelo chamador, então aqui ela
    tem UM papel só: ancorar o MAC do vpad no controle físico. `None` = o
    chamador não sabe de quem é o vpad, e o MAC cai no número do jogador.
    """
    from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        UHID_NODE,
        UhidDualSense,
        uhid_available,
    )

    if flavor != "dualsense":
        return None, None
    if not uhid_available():
        logger.info("vpad_uhid_indisponivel_usando_uinput", node=UHID_NODE, player=player)
        return None, "uhid_indisponivel"
    pad = UhidDualSense.for_flavor(
        flavor,
        rumble_sink=rumble_sink,
        trigger_sink=trigger_sink,
        lightbar_sink=lightbar_sink,
        player_led_sink=player_led_sink,
        session_end_sink=session_end_sink,
        player=player,
        blueprint=canonical_blueprint(),
        calibration_0x05=calibration_0x05,
        mic_led_sink=mic_led_sink,
        mic_mute_sink=mic_mute_sink,
    )
    if pad is None:  # pragma: no cover - o gate de flavor acima já garante
        return None, "uhid_indisponivel"
    pad.identity = identity
    if not pad.start():
        logger.warning("vpad_uhid_start_falhou_usando_uinput", player=player)
        return None, "uhid_start_falhou"
    if not pad.wait_for_bind(UHID_BIND_TIMEOUT_S):
        logger.warning("vpad_uhid_bind_falhou_usando_uinput", player=player)
        pad.stop()
        return None, "uhid_bind_falhou"
    logger.info("vpad_uhid_ativo", player=player, name=pad.name, mac=pad.mac)
    return pad, None


def o_aparelho_mudou(vpad: object, caminho: object, mascara: str) -> bool:
    """O aparelho que ESTE vpad mostra ao jogo não é o que o par pede?

    O JUIZ PELO APARELHO — NO-MODO-XBOX-TUDO-FUNCIONA-01, onda 3 (28/09/2026).
    Os dois juízes de recriação (o `ja_estava` de
    `gamepad.start_gamepad_emulation_desfecho` e
    `external_mask.vpad_ficou_para_tras`) comparavam a máscara e o CANAL
    (:func:`quer_uhid`), e o canal da máscara Nintendo é o `uinput` nos dois
    modos: a troca para o modo Xbox com o Pro de pé não o recriava, e o Pro
    seguia no `uinput`, sem hidraw — a combinação que o jogo sob o Proton abre e
    não entende (o P4 azul do G3, 27/09). Os dois juízes perguntam AQUI, e a
    mesma pergunta nos dois é o que impede o laço: um só curado faria o P1 pedir
    o start a cada compasso.

    A PERGUNTA É AO PAD (`UinputGamepad.mascara_no_jogo`), e não à conta pelo
    caminho pendurado: a fábrica pendura o caminho RESOLVIDO, e o Pro sem modo
    escolhido nasce com o caminho Xbox pendurado e continua sendo o Pro. Um pad
    que não sabe dizer o que veste (o `uhid`, que só nasce DualSense no modo
    DualSense, e os dublês das réguas) não tem aparelho a comparar: fica o juízo
    do canal, que é o de antes.
    """
    vestido = getattr(vpad, "mascara_no_jogo", None)
    if not isinstance(vestido, str) or not vestido:
        return False
    return vestido != mascara_no_jogo(caminho, mascara)


__all__ = [
    "CAMINHOS",
    "CAMINHO_DUALSENSE",
    "CAMINHO_XBOX",
    "MASCARA_DO_CANAL_COMUM",
    "UHID_BIND_TIMEOUT_S",
    "VirtualPad",
    "caminho_do_vpad",
    "caminho_resolvido",
    "make_virtual_pad",
    "mascara_no_jogo",
    "motivo_da_degradacao",
    "normalizar_caminho",
    "o_aparelho_mudou",
    "quer_uhid",
]
