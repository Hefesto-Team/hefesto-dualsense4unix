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

#: Timeout do `wait_for_bind`. O probe do `hid_playstation` faz várias idas e
#: voltas (GET_REPORT 0x09/0x20/0x05) antes do UHID_START.
#:
#: Medido ao vivo (6 execuções): o START chega em **2,3 ms** (pior caso 2,4 ms) —
#: 0,5 s são 200x de folga. Importa porque o `wait_for_bind` roda DENTRO do poll
#: loop (o co-op promove jogador em `sync`/`forward_all`): no caminho de falha o
#: timeout inteiro vira input congelado do P1. Com os 2,0 s originais um uhid que
#: não subisse travava o controle por 2 segundos.
UHID_BIND_TIMEOUT_S = 0.5

# ---------------------------------------------------------------------------
# O CAMINHO — MODO-DE-CONEXAO-01, 13/09/2026
# ---------------------------------------------------------------------------
# A regra é dela, em três mensagens seguidas, e está citada com a digitação
# dela na sprint (`docs/process/sprints/2026-09-13-MODO-DE-CONEXAO-01-…`,
# § A regra dela): o MODO é a base, e o PS + R3 é o mesmo modo; a MÁSCARA vem
# por cima, é como o jogo vê a entrada, e independe do modo; os dois valem com
# o jogo aberto; e o que o PS + R3 escolhe fica gravado no perfil.
#
# SÃO DOIS EIXOS, e esta factory já decidia os dois sem nomear o primeiro: a
# MÁSCARA é o par VID/PID que o jogo vê; o CAMINHO é o canal por onde o
# controle chega — o `uhid` (o relatório do DualSense, por onde voltam
# gatilho, luz e LED de jogador) ou o `uinput` (o canal comum, o do controle de
# Xbox e o piso de compatibilidade). Até 13/09 o caminho saía da máscara, e por
# isso o chip «Xbox» só mudava alguma coisa quando ninguém tinha escolhido
# máscara no cartão.
#
# O `uhid` só se constrói com máscara DualSense: *"o `hid_playstation` só faz
# bind em VID/PID da Sony"* (`_try_uhid`). Com outra máscara os dois caminhos
# dão o mesmo aparelho, e o caminho escolhido fica guardado assim mesmo — a
# falta do canal é dívida no mapa, nunca frase na tela (§D.2 da sprint).
CAMINHO_DUALSENSE = "dualsense"
CAMINHO_XBOX = "xbox"
CAMINHOS: tuple[str, ...] = (CAMINHO_DUALSENSE, CAMINHO_XBOX)


def normalizar_caminho(valor: object) -> str | None:
    """O caminho reconhecido, ou ``None`` — e ``None`` é *"ninguém escolheu"*.

    ESTRITA, ao contrário do `normalize_flavor`: um valor desconhecido não vira
    caminho nenhum por default. Quem recusa em voz alta é o portão do IPC.
    """
    if isinstance(valor, str):
        limpo = valor.strip().lower()
        if limpo in CAMINHOS:
            return limpo
    return None


def caminho_resolvido(caminho: object, mascara: object) -> str:
    """O caminho que vale: o escolhido, ou — sem escolha — o que sai da máscara.

    O SEGUNDO RAMO É O PRODUTO DE ANTES DE 13/09, e é de propósito (§D.1 da
    sprint): *"perfil sem `caminho`: o caminho sai de onde sai hoje (a máscara
    dualsense dá uhid; as outras, uinput), para nenhum jogo mudar no dia da
    cura"*.
    """
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


def _pendurar_o_caminho(pad: object, caminho: str) -> None:
    """Grava no pad o caminho em que ele nasceu. Best-effort: nunca derruba."""
    try:
        pad.caminho = caminho  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        logger.debug("vpad_sem_lugar_para_o_caminho", caminho=caminho)


@runtime_checkable
class VirtualPad(Protocol):
    """O que o daemon usa de um gamepad virtual, seja ele uinput ou uhid.

    Membros só-leitura de propósito: o daemon lê `flavor`/`ff_*` para a GUI e o
    doctor, mas quem define a máscara é a factory, na criação.
    """

    @property
    def flavor(self) -> str:
        """Máscara que o jogo vê: "dualsense", "xbox" ou "nintendo".

        A terceira entrou em 07/09/2026 e NÃO pediu linha nova aqui nem na
        factory: o gate do `_try_uhid` é *"não é dualsense, logo não é meu"*,
        então ela cai no uinput por si, como o xbox sempre caiu.
        """
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
        """Nº de pedidos com FORÇA — os que fariam o motor mexer.

        MASCARA-XBOX-MUDA-01 (09/08/2026). Entra no Protocol junto com o
        `ff_maior_pedido` por um motivo medido: enquanto só o backend uhid os
        tinha, o `daemon/ipc_handlers` os lia com `getattr(vp, ..., 0)` e o
        zero do default virava AFIRMAÇÃO — com a máscara Xbox vibrando
        perfeitamente, a aba Rumble dizia *"o jogo falou de vibração Nx, mas
        pediu força zero em todas"*. Um backend que não responde a pergunta é
        indistinguível de um backend que responde "não" e, num painel de
        diagnóstico, essa é a mentira mais cara que existe.

        O Protocol é o lugar certo do conserto: aqui a pergunta passa a ser
        obrigatória, e um backend novo não tem como nascer mudo.
        """
        ...

    @property
    def ff_maior_pedido(self) -> tuple[int, int]:
        """Maior par (weak, strong) que o jogo pediu — "dava para SENTIR?".

        Comparado por INTENSIDADE (`core.rumble.pedido_mais_forte`), nunca
        pela ordem de tupla do Python.
        """
        ...

    @property
    def ff_descartado_count(self) -> int:
        """Nº de pedidos do jogo que NÃO viraram vibração por falha nossa.

        No uhid: report com motor não-nulo cujos bits de vibração não
        reconhecemos. No uinput: play de efeito que não está no catálogo. Nos
        dois é o mesmo significado para quem lê a tela — *o jogo pediu e nós
        perdemos* —, e é o único caso em que o painel pode acusar a si mesmo.
        """
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
) -> VirtualPad | None:
    """Cria e **starta** o vpad do jogador `player`. None = nenhum backend subiu.

    MODO-DE-CONEXAO-01 (13/09/2026): `caminho` é o MODO que ela escolheu
    (`CAMINHO_DUALSENSE` · `CAMINHO_XBOX`, ou ``None`` = ninguém escolheu). O
    uhid só é tentado com o caminho DualSense **e** a máscara efetiva DualSense
    (:func:`quer_uhid`); o caminho Xbox vai direto ao uinput, e isso não é
    degradação — é a escolha dela. O pad devolvido carrega o caminho em que
    nasceu (`pad.caminho`), que é o que o laço do co-op compara.

    Prefere o uhid quando tudo se alinha (máscara DualSense + /dev/uhid usável +
    permissão do chamador em `allow_uhid`); qualquer tropeço cai no
    `UinputGamepad`, que continua sendo o backend do Xbox 360 e o piso de
    compatibilidade. O blueprint é SEMPRE o canônico embutido
    (`uhid_blueprint.canonical_blueprint`) — o vpad não depende de controle
    físico conectado, nem de hidraw legível (VPAD-03/BT-01).

    REPLICA-03: os sinks de gatilho/lightbar/player-LED/fim-de-sessão replicam
    o output do JOGO ao controle físico — são exclusivos do backend uhid (o
    uinput é evdev-only: FF é o único output que chega até ele), então no
    fallback eles são deliberadamente descartados.

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
        # O caminho Xbox, ou uma máscara que o uhid não veste: uinput por
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
        )
        if uhid is not None:
            _pendurar_o_caminho(uhid, resolvido)
            return uhid
    else:
        motivo = "uhid_vetado_pelo_chamador"
        logger.info("vpad_uhid_vetado_pelo_chamador_usando_uinput", player=player)
    pad = UinputGamepad.for_flavor(key, rumble_sink=rumble_sink)
    if motivo is not None:
        # VPAD-05 — fallback nunca silencioso: o PORQUÊ viaja com o vpad e o
        # `state_full` o expõe (`gamepad_emulation.degraded_motivo`) para a
        # GUI/doctor, sem ninguém precisar garimpar o journal.
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
        # Xbox não é trabalho do uhid: o `hid_playstation` só faz bind em
        # VID/PID da Sony, e um device HID sem driver não vira gamepad nenhum.
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
    )
    if pad is None:  # pragma: no cover - o gate de flavor acima já garante
        return None, "uhid_indisponivel"
    # E3 — A IDENTIDADE ENTRA AQUI, E NÃO PELO `for_flavor`, DE PROPÓSITO.
    # `for_flavor(identity=...)` faz uma SEGUNDA leitura do registro de
    # máscaras, e o `make_virtual_pad` acima já resolveu a máscara efetiva
    # justamente para não existir janela em que os dois discordem sobre quem é
    # este controle (a armadilha que `external_mask.py:68-77` descreveu). O que
    # o MAC do vpad precisa da identidade não é o veredito da máscara — é a
    # âncora, e ela é o mesmo dado nas duas leituras. Atribuir antes do
    # `start()` é o que importa: é lá que o MAC vai para o feature 0x09.
    pad.identity = identity
    if not pad.start():
        logger.warning("vpad_uhid_start_falhou_usando_uinput", player=player)
        return None, "uhid_start_falhou"
    if not pad.wait_for_bind(UHID_BIND_TIMEOUT_S):
        # O CREATE2 foi aceito mas o driver não fez bind (kernel sem
        # hid_playstation, MAC duplicado). Sem o `stop()` o device HID ficaria de
        # pé, mudo, disputando o jogo com o vpad uinput que vem a seguir.
        logger.warning("vpad_uhid_bind_falhou_usando_uinput", player=player)
        pad.stop()
        return None, "uhid_bind_falhou"
    logger.info("vpad_uhid_ativo", player=player, name=pad.name, mac=pad.mac)
    return pad, None


__all__ = [
    "CAMINHOS",
    "CAMINHO_DUALSENSE",
    "CAMINHO_XBOX",
    "UHID_BIND_TIMEOUT_S",
    "VirtualPad",
    "caminho_do_vpad",
    "caminho_resolvido",
    "make_virtual_pad",
    "normalizar_caminho",
    "quer_uhid",
]
