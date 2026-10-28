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

import queue
import threading
import time
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

UHID_BIND_TIMEOUT_S = 0.5

CAMINHO_DUALSENSE = "dualsense"
CAMINHO_XBOX = "xbox"
CAMINHOS: tuple[str, ...] = (CAMINHO_DUALSENSE, CAMINHO_XBOX)

MASCARA_DO_CANAL_COMUM = "xbox"

MOTIVO_MODO_XBOX_ESCOLHIDO = "modo_xbox_escolhido"

MOTIVO_SEM_CANAL_PROPRIO = "sem_canal_proprio"

LINHA_DA_PRO_NO_UINPUT = (
    "a máscara Pro Controller vai ao jogo pelo uinput: os botões, os analógicos e a vibração, "
    "sem o giroscópio e as luzes de jogador, porque o Proton só dá hidraw ao DualSense e ao "
    "DualShock 4"
)


def o_jogo_ve_a_pro(caminho: object, mascaras: object) -> bool:
    """Algum controle mostra a Pro ao jogo? ``mascaras``: as de cada aparelho, ou a da sessão."""
    if isinstance(mascaras, str) or not isinstance(mascaras, (list, tuple, set, frozenset)):
        return False
    return any(
        isinstance(m, str) and mascara_no_jogo(caminho, m) == "nintendo" for m in mascaras
    )


def normalizar_caminho(valor: object) -> str | None:
    """O caminho reconhecido, ou ``None`` — e ``None`` é *"ninguém escolheu"*."""
    if isinstance(valor, str):
        limpo = valor.strip().lower()
        if limpo in CAMINHOS:
            return limpo
    return None


MODO_NINTENDO = "nintendo"
MODOS: tuple[str, ...] = (CAMINHO_DUALSENSE, CAMINHO_XBOX, MODO_NINTENDO)

_CAMINHO_DO_MODO: dict[str, str | None] = {
    CAMINHO_DUALSENSE: CAMINHO_DUALSENSE,
    CAMINHO_XBOX: CAMINHO_XBOX,
    MODO_NINTENDO: None,
}


def normalizar_modo(valor: object) -> str | None:
    """O modo único reconhecido (`dualsense`, `xbox`, `nintendo`), ou ``None``."""
    if isinstance(valor, str):
        limpo = valor.strip().lower()
        if limpo in MODOS:
            return limpo
    return None


def par_do_modo(modo: str) -> tuple[str | None, str]:
    """``(caminho, máscara)`` do modo único: o par que vale para todos os controles.

    DualSense é o caminho `dualsense` com a máscara `dualsense` (uhid); Xbox, o caminho `xbox`
    com a máscara `xbox`; Nintendo Pro, a máscara `nintendo` sem caminho (uinput).
    """
    return _CAMINHO_DO_MODO[modo], modo


def modo_do_par(caminho: object, mascara: object) -> str:
    """O modo único que o par ``(caminho, máscara)`` mostra ao jogo."""
    if not isinstance(mascara, str) or mascara not in MODOS:
        mascara = CAMINHO_DUALSENSE
    return mascara_no_jogo(caminho, mascara)


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


def mascara_no_jogo(caminho: object, mascara: str, *, sem_canal: bool = False) -> str:
    """O aparelho que o JOGO vê para este par (caminho, máscara); o dono da regra.

    Com o modo Xbox ESCOLHIDO (nunca o resolvido: sem escolha, a Nintendo segue
    o Pro), o jogo vê o Xbox 360 em qualquer máscara; com ``sem_canal`` (o par
    pedia o `uhid` e ele não subiu), também, até o canal voltar. Nos outros
    casos, vê a máscara. O Edge ou o Pro no `uinput`, sem hidraw, no lugar do
    Xbox 360, não nascem: o jogo sob o Proton não os usa.
    """
    if normalizar_caminho(caminho) == CAMINHO_XBOX:
        return MASCARA_DO_CANAL_COMUM
    if sem_canal and quer_uhid(caminho, mascara):
        return MASCARA_DO_CANAL_COMUM
    return mascara


def motivo_da_troca(caminho: object, mascara: str, *, sem_canal: bool = False) -> str | None:
    """Por que o aparelho do jogo não é a máscara do cartão — ``None`` quando é.

    A pergunta do :func:`mascara_no_jogo` com a resposta em palavras, para o
    diário e a tela dizerem a troca em vez de a calarem: o modo Xbox escolhido,
    ou o canal próprio que não subiu. Xbox em Xbox não é troca.
    """
    if mascara_no_jogo(caminho, mascara) != mascara:
        return MOTIVO_MODO_XBOX_ESCOLHIDO
    if mascara_no_jogo(caminho, mascara, sem_canal=sem_canal) != mascara:
        return MOTIVO_SEM_CANAL_PROPRIO
    return None


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
    é o do DualSense. O caminho Xbox no ``uinput`` é escolha do usuário (PS-L3-MASCARA-01),
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


def _vestir_o_aparelho(
    pad: object, aparelho: str, *, mascara: str, player: int, motivo: str | None = None
) -> None:
    """Veste o pad ainda não criado com o aparelho que o jogo usa.

    O `motivo` (:func:`motivo_da_troca`) vai ao diário e fica no pad
    (`troca_motivo`).
    """
    vestir = getattr(pad, "vestir", None)
    if not callable(vestir):
        logger.debug("vpad_sem_como_vestir", aparelho=aparelho, player=player)
        return
    vestir(aparelho)
    try:
        pad.troca_motivo = motivo  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        logger.debug("vpad_sem_lugar_para_o_motivo", motivo=motivo, player=player)
    logger.info("vpad_vestido_pelo_modo", mascara=mascara, no_jogo=aparelho,
                player=player, motivo=motivo)


def _o_pad_nasceu(pad: object, caminho: str, identity: str | None) -> None:
    """O pad do aparelho nasceu: o caminho fica nele, e a adoção decide o estacionado.

    O-P3-VOLTA-INTEIRO (14/10/2026): esta fábrica é o ponto por onde passa todo
    pad de aparelho, o do P1 e o do co-op, no cabo e no rádio. O uhid que
    retomou o gadget estacionado já o tirou de lá; o pad que nasce sem retomá-lo
    (outra máscara, o uinput, o uhid sem gadget) deixaria um DualSense fantasma
    ao lado dele, e o estacionado desce aqui, sem relógio.
    """
    _pendurar_o_caminho(pad, caminho)
    if identity:
        from hefesto_dualsense4unix.integrations.uhid_gamepad import o_pad_do_aparelho_nasceu

        o_pad_do_aparelho_nasceu(identity)


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
        na roupa do `product`). O botão de Launch Options escolhe a variante por
        aqui: só o "uhid" se separa do físico pela posse, e o físico pode sair da
        lista do jogo."""
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

    @property
    def eixos_no_jogo(self) -> tuple[int, int, int, int] | None:
        """Os quatro eixos dos analógicos (lx, ly, rx, ry) do último envio ao jogo.

        `None` enquanto o pad não tem nó (antes do `start`, depois do `stop`) ou
        ainda não mandou nada. É leitura do que o pad já guarda para só escrever
        o que mudou: nenhum custo no tique (O-CIRCULO-DO-ANALOGICO-…-01).
        """
        ...


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
    roupa: int | None = None,
) -> VirtualPad | None:
    """Cria e **starta** o vpad do jogador `player`. None = nenhum backend subiu.

    MODO-DE-CONEXAO-01 (13/09/2026): `caminho` é o MODO que o usuário escolheu
    (`CAMINHO_DUALSENSE` · `CAMINHO_XBOX`, ou ``None`` = ninguém escolheu). O
    uhid só é tentado com o caminho DualSense **e** a máscara efetiva DualSense
    (:func:`quer_uhid`); o caminho Xbox vai direto ao uinput, e isso não é
    degradação — é a escolha do usuário. O pad devolvido carrega o caminho em que
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
    `external_mask.py:67-76` descreveu para quem escrevesse este degrau: o gate
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
            roupa=roupa,
        )
        if uhid is not None:
            _o_pad_nasceu(uhid, resolvido, identity)
            return uhid
    else:
        motivo = "uhid_vetado_pelo_chamador"
        logger.info("vpad_uhid_vetado_pelo_chamador_usando_uinput", player=player)
    pad = UinputGamepad.for_flavor(key, rumble_sink=rumble_sink)
    sem_canal = motivo is not None
    aparelho = mascara_no_jogo(caminho, key, sem_canal=sem_canal)
    if aparelho != key:
        _vestir_o_aparelho(
            pad, aparelho, mascara=key, player=player,
            motivo=motivo_da_troca(caminho, key, sem_canal=sem_canal),
        )
    if motivo is not None:
        pad.fallback_motivo = motivo
    if not pad.start():
        return None
    _o_pad_nasceu(pad, resolvido, identity)
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
    roupa: int | None = None,
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
        roupa=roupa,
    )
    if pad is None:  # pragma: no cover
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


class PedidoDePad:
    """Um nascimento pedido ao fio: o laço pergunta `pronto` e leva o `pad`.

    `ms` é o tempo que a fábrica levou. `descartar` vale antes e depois da
    entrega: o pad que nasce para ninguém para no próprio fio, nunca no laço.
    """

    def __init__(self, fio: FioDeNascimento) -> None:
        self._fio = fio
        self._feito = threading.Event()
        self._trava = threading.Lock()
        self._descartado = False
        self.pad: VirtualPad | None = None
        self.ms: float | None = None

    @property
    def pronto(self) -> bool:
        return self._feito.is_set()

    @property
    def descartado(self) -> bool:
        return self._descartado

    def esperar(self, prazo_s: float | None = None) -> bool:
        """Espera a entrega. Só a borda que pede e precisa da resposta espera."""
        return self._feito.wait(prazo_s)

    def _entregar(self, pad: VirtualPad | None, ms: float) -> None:
        with self._trava:
            self.ms = ms
            sobra = pad if self._descartado else None
            if sobra is None:
                self.pad = pad
            self._feito.set()
        if sobra is not None:
            self._fio.parar_o_pad(sobra)

    def descartar(self) -> None:
        """Ninguém quer mais este pad: o que nasceu (ou nascer) para no fio."""
        with self._trava:
            if self._descartado:
                return
            self._descartado = True
            sobra, self.pad = self.pad, None
        if sobra is not None:
            self._fio.parar_o_pad(sobra)


class FioDeNascimento:
    """O dono único do nascimento do pad fora do laço do tique.

    O-PAD-QUE-NASCE-NAO-PARA-O-TIQUE-DOS-OUTROS-01 (16/10/2026): o
    `make_virtual_pad` espera o bind do `uhid` (até `UHID_BIND_TIMEOUT_S`, e o
    assentamento depois dele) e, no gadget USB, a ida e volta ao broker. No laço
    do tique isso parava a entrada de todos os jogadores. Aqui ele roda numa
    thread só, um pedido por vez, na ordem de chegada: a ordem dos nós que o
    jogo vê é a ordem dos pedidos, e quem pede decide essa ordem.
    """

    def __init__(self) -> None:
        self._fila: queue.Queue[tuple[str, Any, Any]] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._trava = threading.Lock()
        self._fechado = False

    def pedir(self, flavor: str | None, **kwargs: Any) -> PedidoDePad:
        """Pede um pad com os argumentos do `make_virtual_pad`. Volta na hora."""
        pedido = PedidoDePad(self)
        self._por("nascer", pedido, (flavor, kwargs))
        return pedido

    def parar_o_pad(self, pad: object) -> None:
        """O `stop` de um pad que ninguém instalou, na vez dele na fila."""
        self._por("parar", pad, None)

    def parar(self) -> None:
        """Fecha o fio depois do que já foi pedido; o que chega depois não abre fio novo."""
        with self._trava:
            self._fechado = True
            thread, self._thread = self._thread, None
        if thread is not None:
            self._fila.put(("fim", None, None))

    def _por(self, tipo: str, alvo: Any, kwargs: Any) -> None:
        with self._trava:
            fechado = self._fechado
            if not fechado:
                self._fila.put((tipo, alvo, kwargs))
                if self._thread is None:
                    self._thread = threading.Thread(
                        target=self._rodar, name="hefesto-nascimento-do-pad", daemon=True
                    )
                    self._thread.start()
        if not fechado:
            return
        if tipo == "parar":
            self._parar_agora(alvo)
        else:
            alvo._entregar(None, 0.0)

    @staticmethod
    def _parar_agora(pad: Any) -> None:
        try:
            pad.stop()
        except Exception as exc:
            logger.warning("vpad_descartado_nao_parou", err=str(exc))

    def _rodar(self) -> None:
        while True:
            tipo, alvo, argumentos = self._fila.get()
            if tipo == "fim":
                return
            if tipo == "parar":
                self._parar_agora(alvo)
                continue
            if alvo.descartado:
                alvo._entregar(None, 0.0)
                continue
            inicio = time.monotonic()
            pad: VirtualPad | None = None
            flavor, kwargs = argumentos
            try:
                pad = make_virtual_pad(flavor, **kwargs)
            except Exception as exc:
                logger.warning("vpad_nascimento_falhou", err=str(exc))
            alvo._entregar(pad, (time.monotonic() - inicio) * 1000.0)


def o_fio_de_nascimento(daemon: object) -> FioDeNascimento | None:
    """O fio do daemon que roda o laço do tique, ou `None` (a borda nasce na hora)."""
    fio = getattr(daemon, "_fio_de_nascimento", None)
    return fio if isinstance(fio, FioDeNascimento) else None


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
    sem_canal = motivo_da_degradacao(vpad) is not None
    return vestido != mascara_no_jogo(caminho, mascara, sem_canal=sem_canal)


def a_roupa_mudou(vpad: object, roupa: object) -> bool:
    """O pad uhid de pé veste outra roupa que a pedida (`numeros_da_sony.ROUPAS_DO_PAD`)?

    O terceiro termo dos juízes de recriação, ao lado do caminho e da máscara
    (D-2210-O-PAD-SE-RECONHECE-PELA-POSSE). Só o uhid veste roupa: o uinput, e
    o dublê sem ``product`` inteiro, não têm o que comparar, e um juiz que os
    comparasse recriaria em laço.
    """
    from hefesto_dualsense4unix.core.numeros_da_sony import roupa_normalizada

    if getattr(vpad, "backend", None) != "uhid":
        return False
    vestida = getattr(vpad, "product", None)
    if not isinstance(vestida, int) or isinstance(vestida, bool):
        return False
    return vestida != roupa_normalizada(roupa)


__all__ = [
    "CAMINHOS",
    "CAMINHO_DUALSENSE",
    "CAMINHO_XBOX",
    "LINHA_DA_PRO_NO_UINPUT",
    "MASCARA_DO_CANAL_COMUM",
    "MODOS",
    "MODO_NINTENDO",
    "MOTIVO_MODO_XBOX_ESCOLHIDO",
    "MOTIVO_SEM_CANAL_PROPRIO",
    "UHID_BIND_TIMEOUT_S",
    "FioDeNascimento",
    "PedidoDePad",
    "VirtualPad",
    "a_roupa_mudou",
    "caminho_do_vpad",
    "caminho_resolvido",
    "make_virtual_pad",
    "mascara_no_jogo",
    "modo_do_par",
    "motivo_da_degradacao",
    "motivo_da_troca",
    "normalizar_caminho",
    "normalizar_modo",
    "o_aparelho_mudou",
    "o_fio_de_nascimento",
    "o_jogo_ve_a_pro",
    "par_do_modo",
    "quer_uhid",
]
