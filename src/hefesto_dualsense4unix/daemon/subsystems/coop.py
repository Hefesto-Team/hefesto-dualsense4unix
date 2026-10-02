"""Subsystem Co-op local — N controles = N jogadores (FEAT-DSX-COOP-LOCAL-01)."""
from __future__ import annotations

import contextlib
import threading
import time
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.led_control import player_led_pattern
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader, EvdevSnapshot
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.integrations.virtual_pad import VirtualPad

logger = get_logger(__name__)

_CALIB_PRAZO_S = 2.0

ESPERA_PELA_ORDEM_S = 4.0


def secundarios_fora_da_mesa(
    sentados: Iterable[str], presentes: Iterable[str]
) -> int:
    """Quantos dos secundários DERRUBADOS perderam também o controle físico."""
    vivos = {str(mac) for mac in presentes}
    return sum(
        1
        for mac in sentados
        if isinstance(mac, str) and not mac.startswith("path:") and mac not in vivos
    )


def _texto_ou_none(valor: Any) -> str | None:
    """`str` não-vazia, ou None — blindagem de serialização do `state_full`.

    O payload roda a 10 Hz e termina em `json.dumps`; um vpad dublado por
    `MagicMock` devolveria um mock em `backend`/`mac`/`name` e derrubaria o
    servidor IPC. A mesma disciplina que o resto do `state_full` já aplica.
    """
    return valor if isinstance(valor, str) and valor else None


def _inteiro_ou_none(valor: Any) -> int | None:
    """`int` estrito (rejeita `bool` e mocks) — a mesma disciplina do texto."""
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def identidade_do_vpad(vpad: Any) -> dict[str, Any]:
    """O que um gamepad virtual sabe sobre si e nunca publicava (E2 do QUEM-É-QUEM-01).

    `{vpad_backend, vpad_uniq, vpad_nome, vpad_indice}`. Todas as leituras por
    `getattr` tipado: nada aqui exige um backend específico, e um vpad dublado
    por mock devolve `None` em vez de derrubar o `json.dumps` do `state_full`.

    - ``vpad_uniq`` é o MAC FORJADO que o vpad uhid VESTE (`UhidDualSense.mac`:
      o do aparelho, ou o do número quando não há identidade, e o seguinte deles
      quando outro vpad vivo já veste aquele — O-VPAD-DO-P1-NAO-REPETE-O-MAC-01)
      e que sai no `HID_UNIQ` do sysfs. É o único "nó" de um vpad uhid: nasce por
      `/dev/uhid`, sem ponteiro para /dev nem /sys. ``None`` no uinput, sem `uniq`.
    - ``vpad_indice`` é o inteiro que está DENTRO do nome do vpad, congelado
      quando aquele vpad nasceu.

      **FATO SUBSTITUÍDO — A-MESMA-LINGUA-01, 07/09/2026.** Esta linha dizia
      que ele era *"o `player_index` de ALOCAÇÃO"*, e era verdade até hoje: o
      nome nascia do índice do co-op enquanto o número publicado saía da fila
      de chegada, e os dois divergiam em 4 de 4 na bancada dela. Agora o nome
      nasce da MESMA fila (:meth:`CoopManager.numero_para_o_nome`), então este
      campo é *o número da carta no instante do nascimento do vpad*.

      Ele continua existindo, e por um motivo que a cura não apaga: o nome não
      se corrige vivo (não há renomear em uhid nem em uinput), então a fila
      pode andar depois. Sem este campo, quem casasse `player == N` com
      `Hefesto P{N}` leria o dispositivo de OUTRO jogador.
    """
    return {
        "vpad_backend": _texto_ou_none(getattr(vpad, "backend", None)),
        "vpad_uniq": _texto_ou_none(getattr(vpad, "mac", None)),
        "vpad_nome": _texto_ou_none(getattr(vpad, "name", None)),
        "vpad_indice": _inteiro_ou_none(getattr(vpad, "player", None)),
    }


def _item_da_mesa(
    *,
    player: Any,
    uniq: str | None,
    is_primary: bool,
    vpad: Any,
    aguardando_grab: bool,
) -> dict[str, Any]:
    """Um item de `CoopManager.mesa` — o contrato num lugar só."""
    numero = _inteiro_ou_none(player) or 0
    identidade = identidade_do_vpad(vpad)
    indice = identidade["vpad_indice"]
    return {
        "uniq": _texto_ou_none(uniq),
        "player": numero,
        "is_primary": bool(is_primary),
        **identidade,
        "aguardando_grab": bool(aguardando_grab),
        "nome_divergente": bool(indice is not None and numero and indice != numero),
    }


def calibration_cache(daemon: Any) -> dict[str, bytes]:
    """Cache de calibração 0x05 POR MAC, vivo no daemon (R-22)."""
    cache = getattr(daemon, "_calibration_by_uniq", None)
    if isinstance(cache, dict):
        return cache
    cache = {}
    with contextlib.suppress(Exception):
        daemon._calibration_by_uniq = cache
    return cache


@dataclass
class _SecondaryPlayer:
    """Um jogador secundário: o evdev de um controle físico + seu gamepad virtual."""

    identity: str
    evdev_path: str
    reader: EvdevReader
    player_index: int
    vpad: VirtualPad | None = None
    cedido_ao_primario: bool = False
    # vpad é uhid E o backend resolve hidraw por-uniq (DualSense); None para
    motion_reader: Any = None


class CoopManager:
    """Gerencia os jogadores secundários (P2+) do co-op local."""

    _fio_do_laco: int | None = None
    _ordem_pendente: bool = False

    def __init__(self, daemon: DaemonProtocol) -> None:
        self._daemon = daemon
        self._players: dict[str, _SecondaryPlayer] = {}
        from hefesto_dualsense4unix.core.evdev_reader import InputDirWatch

        self._watch = InputDirWatch()
        self._was_active = False
        self._leds_overridden = False
        self._camada_coop: dict[str, tuple[bool, bool, bool, bool, bool]] = {}
        self._retry_spawn = False
        self._calib_prazo: dict[str, float] = {}
        self._calib_sem_leitura: set[str] = set()
        self._backend_avisado: Any = None
        self._pronto_desde: dict[str, float] = {}
        self._mesa_do_jogo: dict[int, str] = {}
        self._nascido_em: dict[str, int] = {}
        self._nascimentos = 0
        self._vpad_do_p1_visto: Any = None
        self._fio_do_laco: int | None = None
        self._ordem_pendente = False
        self._ultima_recriacao: tuple[Any, ...] | None = None
        self._ordem_travada = False
        self._p1_espera_o_jogo = False


    def should_be_active(self) -> bool:
        """True se o co-op deve estar ativo agora (flag + gamepad + 2+ controles)."""
        cfg = getattr(self._daemon, "config", None)
        if not bool(getattr(cfg, "coop_enabled", False)):
            return False
        # co-op exige o caminho de gamepad virtual ligado (o P1 já é um vpad).
        return getattr(self._daemon, "_gamepad_device", None) is not None

    def player_count(self) -> int:
        """Total de jogadores ativos (P1 + secundários, incluindo pendentes)."""
        return 1 + len(self._players)

    def player_indexes(self) -> dict[str, int]:
        """MAC -> número do jogador que o JOGO vê (P1 no primário, P2+ nos demais)."""
        numeros = self.numeros_de_jogador()
        out: dict[str, int] = {}
        primary = self._primary_identity()
        if primary is not None and not primary.startswith("path:"):
            out[primary] = numeros.get(primary, 1)
        for mac, player in self._players.items():
            if player.vpad is not None and not mac.startswith("path:"):
                out[mac] = numeros.get(mac, player.player_index)
        return out

    def live_snapshots(self) -> dict[str, EvdevSnapshot]:
        """MAC -> snapshot de input AO VIVO de cada jogador secundário promovido.

        STATUS-01: é a fonte dos `inputs` por controle no `state_full` (o
        primário sai de `daemon._last_state`, a MESMA fonte do topo do payload
        — nunca daqui). Leitura pura e não-destrutiva: `EvdevReader.snapshot()`
        já devolve uma CÓPIA sob lock, sem consumir nada do reader.

        Ficam FORA (o card mostra "—", nunca um valor congelado fingindo vida):
          - jogador pendente (`vpad is None` — aguardando o grab confirmar; o
            jogo também não o vê);
          - identidade sem MAC (`path:...` — não casa com o `uniq` de nenhuma
            entrada de `controllers`);
          - reader cujo snapshot falhou (defensivo — nunca derruba o handler).
        """
        out: dict[str, EvdevSnapshot] = {}
        for mac, player in list(self._players.items()):
            if player.vpad is None or mac.startswith("path:"):
                continue
            try:
                out[mac] = player.reader.snapshot()
            except Exception as exc:
                logger.debug("coop_live_snapshot_falhou", identity=mac, err=str(exc))
        return out

    def mesa(self) -> list[dict[str, Any]]:
        """Um item por JOGADOR: QUAL controle físico alimenta QUAL vpad.

        QUEM-É-QUEM-01, entrega **E1** (sprint
        `docs/process/sprints/arquivados/2026-08-15-QUEM-E-QUEM-01-o-estado-publicado-nao-diz-qual-vpad-e-de-qual-controle.md`).
        Até aqui o estado publicado dizia `coop.players: 4` — um NÚMERO. A
        pergunta dela às 04:05 de 15/08/2026 — *"o vpad e o físico correspondem
        ao mesmo?"* — **não pôde ser lida do estado publicado**: foi paga
        apertando X em cada controle, quatro vezes, à mão (é o buraco que
        `scripts/ensaios/quem_e_quem.py` declara em voz alta: *"Nenhum arquivo
        de /sys carrega essa ligação"*).

        **A informação nunca precisou ser medida: ela existe aqui dentro por
        construção.** É este manager que cria o vpad de cada secundário a
        partir de um físico (`_spawn_player` → `_promote_player`), e o par
        `identity ↔ vpad` fica guardado em `_SecondaryPlayer`. O que faltava
        era publicá-lo — o defeito mais caro desta casa, "a casa sabe e o
        produto não faz", na sua forma mais barata de curar.

        **Isto é IDENTIFICAÇÃO INTERNA E DIAGNÓSTICO, não vocabulário de
        interface e não seleção de alvo — a distinção é DELIBERADA.** O alvo
        por MAC foi derrubado por ela em 13/08/2026 como estratégia de produto
        (nenhuma aba escolhe controle por endereço, e nenhuma passa a
        escolher). O que esta lista responde é outra pergunta, a de quem
        depura: *o produto está mesmo ligando cada físico ao vpad que ele
        pensa?* A tela consome isto como DICA (tooltip) do card que ela já lê,
        nunca como rótulo nem como seletor.

        O item, por jogador. Os dois primeiros campos repetem de propósito o
        NOME que ``controllers[]`` já usa para o mesmo fato — fato igual, nome
        igual, e quem lê casa as duas listas sem tabela de tradução:

        - ``uniq`` — o MAC do físico que alimenta este vpad, ou ``None`` quando
          a identidade é um fallback por path (não há como casar).
        - ``player`` — o número ÚNICO da mesa, de `numeros_de_jogador()`, a
          MESMA função que decide o desenho da lâmpada e o rótulo do card
          (MESA-CHEIA-12). Ler `player_index` cru aqui cruzaria os fios: ele é
          o índice de ALOCAÇÃO do vpad, e as duas ordens só coincidem por sorte.
        - ``is_primary`` — este é o P1 (vpad `daemon._gamepad_device`). Mesmo
          fato, mesmo nome que ``controllers[].is_primary``.
        - ``vpad_backend`` / ``vpad_uniq`` / ``vpad_nome`` / ``vpad_indice`` —
          a identidade do gamepad virtual, de `identidade_do_vpad` (a mesma
          função que a E2 usa no ``per_vpad``, para que as duas listas nunca
          descrevam o mesmo vpad de dois jeitos).
        - ``aguardando_grab`` — jogador registrado SEM vpad, esperando o
          EVIOCGRAB confirmar (BUG-COOP-GRAB-PENDING-VPAD-01). Sai na lista de
          propósito: o físico já está na mesa, e o desequilíbrio é o fato.
        - ``nome_divergente`` — a **E3**: `True` quando o ``player`` publicado
          e o ``vpad_indice`` que está DENTRO do nome do vpad diferem.

          **O QUE ELE SIGNIFICA MUDOU EM 07/09/2026 (A-MESMA-LINGUA-01), e a
          diferença é o ponto inteiro.** Até hoje ele dizia *"estes dois
          inteiros vêm de espaços de numeração diferentes"* — e por isso ficava
          `True` para sempre, nos quatro controles da mesa dela, sem que nada
          jamais o apagasse. Agora o nome NASCE do número da carta
          (:meth:`CoopManager.numero_para_o_nome`), então o normal é `False` e
          o alarme passa a dizer uma coisa só, verificável e temporária: *a
          fila andou depois que este vpad nasceu.*

          O aviso continua sendo obrigatório porque a cura não alcança o
          depois: o nome vai no `UHID_CREATE2`/`UI_DEV_SETUP` e o kernel não
          tem operação de renomear — corrigi-lo ao vivo seria derrubar e
          recriar o nó, e o jogo veria um gamepad desconectando no meio da
          partida. Sem o aviso, casar ``player == N`` com ``Hefesto P{N}``
          leria o dispositivo de outro jogador — medição confiante e errada, a
          armadilha nº 1 daqui.

        PRIVACIDADE — o MAC do físico vai INTEIRO, e o porquê está escrito
        aqui para não ser reaberto. (1) Não é exposição nova: o mesmo endereço
        já viaja no `state_full` desde a FEAT-STATE-PER-CONTROLLER-01, em
        ``controllers[].uniq``; publicar um MAC mascarado AQUI criaria um
        segundo endereço, incapaz de casar com o primeiro, e a GUI (que casa
        card↔vpad por `uniq`) não teria como usar a lista — a cura nasceria
        morta. (2) O `state_full` só trafega no socket LOCAL dela
        (`ipc_server`), sob permissão de usuário. (3) A regra dura da casa é
        *"nada de MAC real em ARQUIVO VERSIONADO"*, e nenhum caminho leva
        daqui a um: o que o repositório guarda são os ensaios e os testes, e
        os dois só conhecem as faixas forjadas (`02:fe`, `aa:bb:cc`,
        `e8:47:3a`) — `scripts/check_anonymity.sh` é o portão que reprova o
        contrário. O ``vpad_uniq``, esse, é forjado por construção e não
        identifica hardware nenhum.

        Com o co-op DESLIGADO a lista tem um item só, e isso é a verdade e não
        uma amputação: fora do co-op o INPUT vem só do primário (ver o
        cabeçalho deste módulo), então nenhum outro físico alimenta vpad
        nenhum. Um item por físico ali diria o contrário.
        """
        numeros = self.numeros_de_jogador()
        itens: list[dict[str, Any]] = []
        primary = self._primary_identity()
        if primary is not None:
            itens.append(
                _item_da_mesa(
                    player=numeros.get(primary, 1),
                    uniq=None if primary.startswith("path:") else primary,
                    is_primary=True,
                    vpad=getattr(self._daemon, "_gamepad_device", None),
                    aguardando_grab=False,
                )
            )
        for mac, jogador in self._players.items():
            itens.append(
                _item_da_mesa(
                    player=numeros.get(mac, jogador.player_index),
                    uniq=None if mac.startswith("path:") else mac,
                    is_primary=False,
                    vpad=jogador.vpad,
                    aguardando_grab=jogador.vpad is None,
                )
            )
        return itens

    def _primary_evdev_path(self) -> str | None:
        ev = getattr(getattr(self._daemon, "controller", None), "_evdev", None)
        path = getattr(ev, "_device_path", None)
        return str(path) if path is not None else None

    def _primary_identity(self) -> str | None:
        """Identidade (MAC) do primário; fallback por path do reader."""
        ctrl = getattr(self._daemon, "controller", None)
        uniq = getattr(ctrl, "primary_uniq", None)
        if uniq:
            return str(uniq)
        path = self._primary_evdev_path()
        return f"path:{path}" if path else None


    def _garantir_aviso_de_primario(self) -> None:
        """Pendura o aviso de troca de primário no backend. Idempotente."""
        ctrl = getattr(self._daemon, "controller", None)
        if ctrl is None or ctrl is self._backend_avisado:
            return
        fn = getattr(ctrl, "set_primary_change_observer", None)
        if not callable(fn):
            self._backend_avisado = ctrl
            logger.debug("coop_aviso_de_primario_indisponivel")
            return
        fn(self.ceder_ao_primario)
        self._backend_avisado = ctrl
        self._pendurar_a_espera_do_posto(ctrl)

    def ceder_ao_primario(self, anterior: str | None, novo: str | None) -> None:
        """O controle `novo` virou o primário — solte-o AGORA, antes do retarget."""
        if novo is None:
            return
        player = self._players.get(novo)
        if player is None or player.cedido_ao_primario:
            return
        player.cedido_ao_primario = True
        with contextlib.suppress(Exception):
            player.reader.set_grab(False)
        self._retry_spawn = True
        logger.info(
            "coop_player_cedido_ao_primario",
            identity=novo,
            anterior=anterior,
            **self._numero_e_indice(player),
        )

    def _recolher_os_cedidos(self) -> None:
        """Desmonta, no poll loop, os jogadores que cederam o controle ao P1."""
        for identity in [
            mac for mac, p in self._players.items() if p.cedido_ao_primario
        ]:
            self._teardown_player(identity)


    def sync(self, *, force: bool = False, origem: str | None = None) -> None:
        """Reconcilia os secundários com os controles plugados. Idempotente."""
        self._garantir_aviso_de_primario()
        if not self.should_be_active():
            self._was_active = False
            if self._players or self._leds_overridden:
                self.disable()
            self._reavaliar_a_mesa_suspensa()
            return

        from hefesto_dualsense4unix.daemon.subsystems.gamepad import vpad_vivo

        activated = not self._was_active
        self._was_active = True
        self._recolher_os_cedidos()
        self._promote_pending()
        self._corrigir_a_ordem()
        retry_needed = self._retry_spawn
        self._retry_spawn = False
        grab_degraded = any(
            p.reader.grab_state == "failed" for p in self._players.values()
        )
        vpad_morto = any(
            p.vpad is not None and not vpad_vivo(p.vpad)
            for p in self._players.values()
        )
        if not (
            self._watch.poll()
            or activated
            or grab_degraded
            or vpad_morto
            or retry_needed
            or force
        ):
            self._repintar_se_o_numero_mudou()
            return
        from hefesto_dualsense4unix.core.evdev_reader import discover_dualsense_evdevs
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            mascara_efetiva,
            vpad_ficou_para_tras,
        )

        primary = self._primary_identity()
        # primário ainda não resolveu o MAC (`primary_uniq` None no boot/restart
        # com controles já plugados → fallback "path:"), não há como excluí-lo de
        # `want` e um secundário nasceria para o PRÓPRIO controle do P1 (input
        # DOBRADO até o próximo sync ~2s). Adia enquanto não há MAC do primário;
        # `_retry_spawn` garante o re-teste no tick seguinte, sem depender do
        if primary is None or primary.startswith("path:"):
            logger.debug("coop_sync_defer_primary_sem_mac", primary=primary)
            self._retry_spawn = True
            return
        want = {
            mac: str(path)
            for mac, path in discover_dualsense_evdevs().items()
            if mac != primary
        }
        desired_flavor = self._flavor()
        desired_caminho = self._caminho()

        for mac in list(self._players):
            player = self._players[mac]
            if self._segura_na_troca_de_transporte(player, want.get(mac)):
                continue
            if mac not in want:
                self._teardown_player(mac)
            elif player.evdev_path != want[mac]:
                logger.info(
                    "coop_player_node_changed",
                    identity=mac,
                    old=player.evdev_path,
                    new=want[mac],
                )
                self._teardown_player(mac)
            elif player.reader.grab_state == "failed":
                logger.warning("coop_player_grab_failed_retry", identity=mac)
                self._teardown_player(mac)
            elif player.vpad is not None and not vpad_vivo(player.vpad):
                logger.warning("coop_player_vpad_morto_respawn", identity=mac)
                self._teardown_player(mac)
            elif player.vpad is not None and vpad_ficou_para_tras(
                getattr(player.vpad, "flavor", None),
                mac,
                desired_flavor,
                vpad=player.vpad,
                caminho=desired_caminho,
            ):
                if self._a_mascara_espera_o_jogo(mac, origem if force else "coop_tique"):
                    continue
                logger.info(
                    "coop_player_flavor_changed",
                    identity=mac,
                    old=getattr(player.vpad, "flavor", None),
                    new=mascara_efetiva(mac, desired_flavor),
                )
                self._teardown_player(mac)

        for mac in self._na_ordem_da_carta(want):
            if mac not in self._players:
                self._spawn_player(mac, want[mac])

        # todo ciclo cheio — cobre ativação, spawn, node novo e o replug (o
        # backend re-afirma o padrão broadcast do perfil no nó que reaparece;
        # como o replug também dispara o watch, este reassert devolve o padrão
        # do jogador logo em seguida).
        self._apply_coop_player_leds()

    def _a_mascara_espera_o_jogo(self, mac: str, origem: str | None) -> bool:
        """O pad deste secundário, que ficou para trás da máscara, espera o jogo?

        Pergunta ao dono da trava (`gamepad._recriacao_bloqueada_por_jogo`).
        ``origem`` ``None`` é o ciclo forçado por quem já perguntou: não espera.
        """
        if origem is None:
            return False
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            _recriacao_bloqueada_por_jogo,
        )

        return _recriacao_bloqueada_por_jogo(
            self._daemon, origin=origem, motivo=f"mascara_do_secundario:{_rotulo(mac)}"
        )

    def _segura_na_troca_de_transporte(
        self, player: _SecondaryPlayer, no_de_agora: str | None
    ) -> bool:
        """O jogador que está TROCANDO de transporte fica com o vpad. Devolve se segurou."""
        if no_de_agora is not None and no_de_agora == player.evdev_path:
            return False
        pergunta = getattr(
            getattr(self._daemon, "controller", None), "em_troca_de_transporte", None
        )
        if not callable(pergunta):
            return False
        try:
            em_troca = bool(pergunta(player.identity))
        except Exception as exc:
            logger.debug("coop_troca_de_transporte_pergunta_falhou", err=str(exc))
            return False
        if not em_troca:
            return False
        if no_de_agora is None:
            logger.debug("coop_player_segura_na_troca", identity=player.identity)
            self._retry_spawn = True
            return True
        logger.info(
            "coop_player_reapontado_na_troca",
            identity=player.identity,
            old=player.evdev_path,
            new=no_de_agora,
        )
        player.evdev_path = no_de_agora
        with contextlib.suppress(Exception):
            player.reader.request_reopen("troca_de_transporte")
        self._broker_hide_player(player)
        return True

    def _reavaliar_a_mesa_suspensa(self) -> None:
        """Reabre a conta do aviso enquanto os vpads estão suspensos."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            coop_sentados_na_suspensao,
            reavaliar_coop_fora_da_mesa,
        )

        if not coop_sentados_na_suspensao(self._daemon):
            return
        if not self._watch.poll():
            return
        from hefesto_dualsense4unix.core.evdev_reader import discover_dualsense_evdevs

        try:
            presentes = set(discover_dualsense_evdevs())
        except Exception as exc:
            logger.debug("coop_reavaliacao_da_mesa_falhou", err=str(exc))
            return
        reavaliar_coop_fora_da_mesa(self._daemon, presentes)

    def algum_boneco_ficou_para_tras(self) -> bool:
        """Algum secundário veste máscara ou canal diferente do efetivo de agora?"""
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            vpad_ficou_para_tras,
        )

        flavor = self._flavor()
        caminho = self._caminho()
        return any(
            player.vpad is not None
            and vpad_ficou_para_tras(
                getattr(player.vpad, "flavor", None),
                mac,
                flavor,
                vpad=player.vpad,
                caminho=caminho,
            )
            for mac, player in list(self._players.items())
        )

    def _flavor(self) -> str:
        from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor

        cfg = getattr(self._daemon, "config", None)
        return normalize_flavor(getattr(cfg, "gamepad_flavor", None))

    def _caminho(self) -> str | None:
        """O caminho escolhido (MODO-DE-CONEXAO-01), ou ``None`` = ninguém escolheu.

        O-CAMINHO-NAO-VAZA-01 (17/09/2026) — ESTA LINHA NÃO MUDOU, e a razão
        está aqui porque a leva chegou querendo mudá-la. O vazamento que levava
        a mesa inteira para o `xbox` do jogo anterior era o SLOT que ela lê
        ficar rançoso: `gamepad._guardar_o_caminho` nunca o limpava, então o
        jogo sem opinião herdava o canal do anterior e os três secundários
        nasciam em uinput atrás de um P1 já em uhid — sem
        `_start_player_motion_reader`, isto é, sem giroscópio para ninguém além
        do jogador 1, e sem uma linha de log dizendo por quê. Com o slot
        acompanhando a sessão, ler daqui voltou a ser correto.

        E NÃO se pergunta o canal ao vpad do P1 (`caminho_do_vpad`): a resposta
        dele é DERIVADA da máscara quando ninguém escolheu, e um P1 com cartão
        `xbox` passaria a derrubar todo secundário `dualsense` a cada tique — a
        MÁSCARA-POR-JOGADOR-01 virada do avesso. Medido: foi o que aconteceu ao
        tentar, e `test_a_mascara_do_cartao_vale_com_o_vpad_de_pe` reprovou.
        """
        from hefesto_dualsense4unix.integrations.virtual_pad import normalizar_caminho

        cfg = getattr(self._daemon, "config", None)
        return normalizar_caminho(getattr(cfg, "gamepad_caminho", None))

    def _next_player_index(self) -> int:
        """Menor índice de jogador livre (≥2).

        Estável para quem já está vivo (ninguém é renumerado) e sem duplicata:
        o índice de um jogador que saiu é reusado pelo próximo que entrar.
        """
        used = {p.player_index for p in self._players.values()}
        index = 2
        while index in used:
            index += 1
        return index

    def numero_para_o_nome(self, identity: str, fallback: int) -> int:
        """O número que vai DENTRO do nome do vpad deste controle.

        A-MESMA-LINGUA-01 (07/09/2026). Decisão dela, em cinco palavras:
        *"precisamos que falem a mesma língua."*

        **A pergunta é feita ao DONO, e o dono é um só.** O número que a carta
        mostra sai de :meth:`numeros_de_jogador` — a fila de chegada
        (`identity_registry`), a MESMA função que escolhe o desenho aceso na
        barra de player e o rótulo do card desde a MESA-CHEIA-12. O nome do
        vpad passa a sair dela também, em vez de guardar cópia do
        `player_index`. É a regra desta casa: *quando um valor tem dono, a
        régua PERGUNTA ao dono.*

        O QUE ESTAVA ERRADO, medido na bancada dela em 07/09/2026 com os
        QUATRO na mesa — e era **4 de 4**, nenhum acerto por sorte:

        | aparelho                | carta | nome do vpad |
        |-------------------------|-------|--------------|
        | Cosmic Red (cabo, P1)   | 2     | `Hefesto P1` |
        | Starlight Blue (rádio)  | 4     | `Hefesto P3` |
        | Galactic Purple (rádio) | 1     | `Hefesto P4` |
        | White (cabo)            | 3     | `Hefesto P2` |

        O `state_full` publicava `nome_divergente: true` nos quatro itens da
        mesa desde a QUEM-É-QUEM-01/E3 — a casa SABIA e o produto não fazia,
        o defeito mais caro daqui, na sua forma mais barata de curar.

        `fallback` é o `player_index` (índice de ALOCAÇÃO do vpad). Ele
        continua sendo a resposta quando não há registro de identidade
        (FakeController, backend legado, dublê de teste): sem fila, o
        histórico segue intacto.

        **O NOME SÓ PODE NASCER CERTO — ele não se corrige vivo.** O nó uhid
        recebe o nome em `UHID_CREATE2` e o ABI do kernel não tem operação de
        renomear (`/usr/include/linux/uhid.h`: `CREATE2`, `DESTROY`, `START`,
        `STOP`, `OPEN`, `CLOSE`, `OUTPUT`, `GET_REPORT*`, `SET_REPORT*`,
        `INPUT2` — e nada mais); o uinput é igual, o nome vai no `UI_DEV_SETUP`
        antes do `UI_DEV_CREATE`. Renomear é DERRUBAR e RECRIAR.

        **O PREÇO DE RECRIAR, medido no journal da bancada dela, 07/09/2026**
        (um replug real do controle branco, `uhid_device_created` →
        `vpad_uhid_ativo` → sinks de volta → `launch_env` reassentado):

        | marco                       | atraso desde o `CREATE2` |
        |-----------------------------|--------------------------|
        | `uhid_bind_ok`              | 10,1 ms                  |
        | `vpad_uhid_ativo`           | 60,6 ms                  |
        | motion reader de volta      | 561 ms                   |
        | réplicas (lightbar/LED)     | 658 ms                   |
        | `launch_env` reassentado    | 3,1 s                    |

        E o custo que os milissegundos não contam: o jogo recebe um
        `REMOVED`+`ADDED` de gamepad — controle arrancado da mão no meio da
        partida (é a mesma R-04 que o `start_gamepad_emulation` já se recusa a
        pagar quando o jogo está com a autoridade).

        **E O PIOR NÃO É O PREÇO UNITÁRIO, É QUANTOS PAGAM.** O número da
        carta é uma COLOCAÇÃO entre os PRESENTES (`identity_registry.slot_for`:
        *"um controle cujo lugar na fila é o terceiro exibe 1 quando é o único
        ligado"*). Uma bateria que acaba no jogador 1 muda o número de TODOS os
        que vêm atrás — renomear ao vivo derrubaria os outros três vpads por
        causa de um controle que nem era deles.

        Por isso esta função é chamada na PROMOÇÃO, e o `nome_divergente` de
        :func:`_item_da_mesa` passa a significar exatamente *"a fila andou
        depois que este vpad nasceu"* — que é a única coisa que ele pode
        significar de honesto.

        **ATÉ ONDE ESTE NÚMERO CHEGA — medido em 07/09/2026, e a fronteira é
        real.** Ele chega ao nome do nó evdev, ao `/proc/bus/input/devices` e
        à API **Joystick** da SDL (`SDL_JoystickNameForIndex` devolve o nome
        certo de cada um dos quatro). Ele **NÃO chega** à API
        **GameController**, que é a que a maioria dos jogos usa:

            idx  SDL_JoystickNameForIndex   SDL_GameControllerNameForIndex
             1   ...(Hefesto P1)            ...(Hefesto P1)
             3   ...(Hefesto P2)            ...(Hefesto P1)
             5   ...(Hefesto P3)            ...(Hefesto P1)
             7   ...(Hefesto P4)            ...(Hefesto P1)

        A CAUSA, medida e não deduzida: os bytes 2-3 do GUID da SDL são o
        CRC16 do NOME, então os quatro vpads têm GUIDs diferentes; a busca de
        mapping cai de volta para o GUID com o CRC zerado, os quatro colapsam
        em `030000004c050000f20d000000810000`, e UM mapping só — o primeiro
        registrado, que carrega o nome do P1 — responde pelos quatro. O
        `SDL_GameControllerName` devolve o nome do MAPPING, não o do nó. Ver
        a medição inteira em `integrations.uinput_gamepad.NINTENDO_PROCON_NAME`.

        E `SDL_JoystickGetDevicePlayerIndex` não é saída: ele devolve a ordem
        de ENUMERAÇÃO (0..7 nesta bancada), nunca a carta.

        **O QUE ISSO NÃO DERRUBA:** a cura continua certa e continua valendo.
        O defeito que ela fechou era a casa falar duas línguas sobre si mesma
        — a carta dizendo 2 e o nó dizendo `Hefesto P1`, em 4 de 4. O que a
        medição acrescenta é que fazer o JOGO ler esse número é outro
        trabalho, e não se ganha trocando o nome: pede mapping por GUID
        (`SDL_GAMECONTROLLERCONFIG`) ou o `player_index` da própria SDL.
        """
        numeros = self.numeros_de_jogador()
        numero = numeros.get(identity)
        if isinstance(numero, int) and not isinstance(numero, bool) and numero >= 1:
            return numero
        return fallback

    def _spawn_player(self, identity: str, path: str) -> None:
        """Cria um jogador secundário para o controle `identity` no node `path`.

        BUG-COOP-GRAB-PENDING-VPAD-01: o vpad SÓ nasce com grab CONFIRMADO
        ("held"). Recusa imediata de EVIOCGRAB → nada é criado (retry natural
        no próximo sync, BUG-COOP-GRAB-SILENT-FAIL-01). Grab "pending" (a
        thread do reader ainda não abriu o device) → o jogador é registrado
        SEM vpad — o jogo não vê nada — e `_promote_pending` (todo tick) cria
        o vpad quando o grab confirmar.
        """
        from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

        # target_uniq: reconexões do loop re-localizam ESTE controle pelo MAC,
        # nunca "o primeiro node da lista" (identidade estável por jogador).
        target = None if identity.startswith("path:") else identity
        reader = EvdevReader(device_path=Path(path), target_uniq=target)
        if not reader.start():
            logger.debug("coop_player_reader_unavailable", identity=identity, evdev=path)
            return
        # Grab: o jogo deve ver SÓ o gamepad virtual deste jogador, não o cru.
        if not reader.set_grab(True):
            logger.warning("coop_player_grab_refused", identity=identity, evdev=path)
            reader.stop()
            return
        player = _SecondaryPlayer(
            identity=identity,
            evdev_path=path,
            reader=reader,
            player_index=self._next_player_index(),
        )
        self._players[identity] = player
        # R-22: esquenta o cache do 0x05 assim que o jogador é registrado —
        # normalmente o grab só confirma um tick depois, então a leitura (que
        # roda fora do loop) já terminou quando a promoção precisar dela e o
        self._prefetch_calibration(identity)
        if reader.grab_state == "held" and self._pode_nascer_na_ordem(player):
            self._nascer_na_ordem(player)
        elif reader.grab_state == "held":
            logger.info(
                "coop_player_espera_a_ordem",
                identity=identity,
                carta=self._numero_da_carta(identity),
            )
            self._armar_sossego_do_launch_env("jogador de co-op esperando a ordem")
        else:
            logger.info(
                "coop_player_grab_pending",
                identity=identity,
                evdev=path,
                **self._numero_e_indice(player),
            )
            self._armar_sossego_do_launch_env("jogador de co-op aguardando grab")

    def _promote_pending(self) -> None:
        """Promove jogadores "aguardando grab": cria o vpad quando "held"."""
        pendentes = [i for i, p in self._players.items() if p.vpad is None]
        for identity in self._na_ordem_da_carta(pendentes):
            player = self._players.get(identity)
            if player is None or player.vpad is not None:
                continue
            state = player.reader.grab_state
            if state == "held":
                if self._pode_nascer_na_ordem(player):
                    self._nascer_na_ordem(player)
            elif state == "failed":
                logger.warning(
                    "coop_player_grab_failed_drop",
                    identity=identity,
                    evdev=player.evdev_path,
                )
                self._teardown_player(identity)
                self._retry_spawn = True

    def _make_player_rumble_sink(self, identity: str) -> Callable[[int, int], None]:
        """Sink de FF do vpad de UM jogador → rumble no controle DELE (por MAC).

        FEAT-VPAD-FF-PASSTHROUGH-01: delega em `apply_game_rumble` com
        `target_uniq=MAC` — targeting via a API por-uniq do backend
        (`set_rumble_for`, PERFIL-01, sem flip do seletor global), com a
        política global de intensidade e o respeito ao rumble fixado já
        embutidos lá. Identidade sem MAC ("path:...") não tem como casar o
        handle → broadcast (limitação documentada; não acontece com DualSense
        real).
        """
        daemon = self._daemon

        def _sink(weak: int, strong: int) -> None:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                anotar_rumble_no_vpad,
                apply_game_rumble,
            )

            target = None if identity.startswith("path:") else identity
            # MOTOR-QUE-NAO-SE-VE-01: o vpad é procurado AQUI, na hora do rumble
            # (o sink nasce antes dele, e o `_players[identity]` é recriado a
            # cada respawn), e vai junto: o pad `uinput` deste jogador leva a
            # háptica fina ao lugar DELE (NO-MODO-XBOX-TUDO-FUNCIONA-01).
            vpad = getattr(self._players.get(identity), "vpad", None)
            efetivo = apply_game_rumble(daemon, weak, strong, target_uniq=target, vpad=vpad)
            anotar_rumble_no_vpad(vpad, efetivo)

        return _sink

    def _make_player_replica_sinks(self, identity: str) -> dict[str, Any]:
        """Sinks de replicação (REPLICA-03) do vpad de UM jogador → físico DELE.

        Espelho por-jogador do `make_primary_replica_sinks` do P1: gatilhos
        adaptativos, lightbar e player-LEDs que o JOGO escrever no vpad deste
        jogador vão para o controle da identidade dele (por MAC), e o fim da
        sessão uhid devolve perfil/paleta/co-op. Identidade sem MAC
        ("path:...") não tem alvo estável — os appliers descartam com log
        (sem broadcast: réplica no controle errado é o bug P1-lightbar).
        """
        daemon = self._daemon
        target = None if identity.startswith("path:") else identity

        def _trigger(side: str, block: bytes) -> None:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                apply_game_trigger,
            )

            apply_game_trigger(daemon, side, block, target_uniq=target)

        def _lightbar(r: int, g: int, b: int) -> None:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                apply_game_lightbar,
            )

            apply_game_lightbar(daemon, (r, g, b), target_uniq=target)

        def _player_leds(bits: tuple[bool, bool, bool, bool, bool]) -> None:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                apply_game_player_leds,
            )

            apply_game_player_leds(daemon, bits, target_uniq=target)

        def _session_end() -> None:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import end_game_output_session

            end_game_output_session(daemon, target_uniq=target)

        return {
            "trigger_sink": _trigger,
            "lightbar_sink": _lightbar,
            "player_led_sink": _player_leds,
            "session_end_sink": _session_end,
            # A luz e o mudo do microfone que o jogo pede, ao controle DESTE jogador.
            **ralos_do_mic(daemon, lambda: target),
        }

    def _promote_player(self, player: _SecondaryPlayer) -> None:
        """Cria o vpad de um jogador com grab CONFIRMADO. Falha derruba o jogador."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import controller_allows_uhid
        from hefesto_dualsense4unix.integrations.virtual_pad import make_virtual_pad

        calib_pronta, calib = self._calibration_pronta(player.identity)
        if not calib_pronta:
            logger.debug(
                "coop_player_calibracao_pendente",
                identity=player.identity,
                **self._numero_e_indice(player),
            )
            return

        # controle não-DualSense (8BitDo, Pro Controller) também ganha vpad uhid
        vpad = make_virtual_pad(
            self._flavor(),
            identity=player.identity,
            rumble_sink=self._make_player_rumble_sink(player.identity),
            player=self.numero_para_o_nome(player.identity, player.player_index),
            allow_uhid=controller_allows_uhid(self._daemon),
            calibration_0x05=calib,
            caminho=self._caminho(),
            **self._make_player_replica_sinks(player.identity),
        )
        if vpad is None:
            logger.warning(
                "coop_player_vpad_failed",
                identity=player.identity,
                evdev=player.evdev_path,
            )
            self._teardown_player(player.identity)
            self._retry_spawn = True
            return
        player.vpad = vpad
        self._assentar(player.identity)
        self._start_player_motion_reader(player)
        logger.info(
            "coop_player_added",
            identity=player.identity,
            evdev=player.evdev_path,
            **self._numero_e_indice(player),
            players=self.player_count(),
        )
        from hefesto_dualsense4unix.integrations.virtual_pad import motivo_da_degradacao

        motivo = motivo_da_degradacao(vpad)
        if motivo is not None:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                notify_vpad_degradado,
            )

            with contextlib.suppress(Exception):
                notify_vpad_degradado(
                    self._daemon, motivo=motivo, **self._numero_e_indice(player)
                )
        self._materialize_launch_env()
        self._broker_hide_player(player)

    def _read_player_calibration(self, identity: str) -> bytes | None:
        """Feature 0x05 do físico de UM jogador (GYRO-01), ou None = canônico.

        Vista fail-safe de `_calibration_pronta`: "ainda não resolveu" vira
        None (o 0x05 canônico que o contrato do vpad já prevê). Quem PODE
        adiar — só a promoção — chama `_calibration_pronta` direto.
        """
        return self._calibration_pronta(identity)[1]

    def _calibration_pronta(self, identity: str) -> tuple[bool, bytes | None]:
        """`(resolvida?, calibração)` do jogador pelo CACHE — R-22."""
        if identity.startswith("path:"):
            return True, None
        cache = calibration_cache(self._daemon)
        hit = cache.get(identity)
        if hit is not None:
            return True, hit
        if identity in self._calib_sem_leitura:
            return True, None
        prazo = self._calib_prazo.get(identity)
        if prazo is None:
            self._schedule_calibration(identity)
            hit = cache.get(identity)
            if hit is not None or identity in self._calib_sem_leitura:
                self._calib_prazo.pop(identity, None)
                return True, hit
            return False, None
        if time.monotonic() < prazo:
            return False, None
        self._calib_prazo.pop(identity, None)
        self._calib_sem_leitura.add(identity)
        logger.warning("coop_calibracao_prazo_estourado", identity=identity)
        return True, None

    def _prefetch_calibration(self, identity: str) -> None:
        """Esquenta o cache do 0x05 de um jogador recém-registrado (R-22)."""
        if identity.startswith("path:"):
            return
        if identity in self._calib_sem_leitura or identity in self._calib_prazo:
            return
        if calibration_cache(self._daemon).get(identity) is not None:
            return
        self._schedule_calibration(identity)

    def _schedule_calibration(self, identity: str) -> None:
        """Agenda (fora do event loop) a leitura do 0x05 deste MAC — R-22."""
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            broker_call_nonblocking,
        )

        self._calib_prazo[identity] = time.monotonic() + _CALIB_PRAZO_S
        broker_call_nonblocking(self._daemon, lambda: self._fill_calibration(identity))

    def _fill_calibration(self, identity: str) -> None:
        """Lê o 0x05 e preenche o cache. Roda NA THREAD DO EXECUTOR (R-22)."""
        data: Any = None
        fn = getattr(self._daemon.controller, "read_calibration", None)
        if callable(fn):
            try:
                data = fn(identity)
            except Exception as exc:
                logger.warning(
                    "coop_calibration_read_failed", identity=identity, err=str(exc)
                )
                data = None
        if isinstance(data, bytes) and data:
            calibration_cache(self._daemon)[identity] = data
        else:
            self._calib_sem_leitura.add(identity)

    def _start_player_motion_reader(self, player: _SecondaryPlayer) -> None:
        """Espelho de motion por jogador (GYRO-01 co-op): hidraw dele → vpad dele.

        Gates — todos ESTRUTURAIS, isto é, verdades que não mudam enquanto este
        jogador existir (fail-safe: sem reader o vpad segue com a IMU neutra):
        - vpad em uhid (o uinput é evdev puro, sem `forward_motion`);
        - identidade com MAC (o hidraw por-uniq vem do backend pydualsense);
        - backend que expõe `hidraw_path` (o `FakeController` não tem físico).

        ESPELHO-QUE-NAO-NASCEU-01 (15/08/2026) — POR QUE NÃO SE OLHA O HANDLE
        AQUI. Havia um quarto gate: `hidraw_path(identity) is None` reprovava na
        hora, com a justificativa de que controle externo (8BitDo/Nintendo) não
        tem handle no backend e fica sem espelho por design (8BIT-02, estudo
        2026-07-19). **A decisão continua valendo; o gate é que olhava a coisa
        errada.** Ele lia uma AMOSTRA INSTANTÂNEA de um valor que muda, e a lia
        no pior instante possível: a promoção roda no tick do hotplug, enquanto
        o `_open_one` do backend ainda está no ar para aquele MAC (até
        `INIT_TIMEOUT_SEC` = 5 s por probe, e o BT chega a estourar esse teto).
        Quem perdesse essa corrida ficava sem espelho PARA SEMPRE — este método
        só é chamado uma vez, na promoção, e nada o reexecuta. Medido na mesa de
        quatro em 15/08/2026: o vpad do jogador sem espelho entregava ~0,4 Hz ao
        jogo (o poll loop de 60 Hz só emite no delta, e a janela 15..39 fica
        congelada em `_MOTION_NEUTRAL`) contra 165-196 Hz dos outros três.

        A garantia do 8BIT-02 não dependia deste gate e segue de pé sem ele: os
        secundários saem de `discover_dualsense_evdevs()`, que é fechada em
        `DUALSENSE_VENDOR`/`DUALSENSE_PIDS` — 8BitDo e Nintendo nunca chegam a
        `_players`, e um DualSense sem MAC legível cai no gate `path:` acima.

        O handle que ainda não abriu deixa de ser motivo de recusa porque o
        `PhysicalReportReader` já sabe esperar: `_run` re-resolve o
        `path_provider` a cada volta e faz backoff de 0,5 s a 5 s enquanto ele
        devolve None, na thread dele, fora do event loop. É exatamente o que o
        espelho do P1 (`subsystems/gamepad.start_motion_reader`) sempre fez — e
        é por isso que o P1 nunca sofreu deste defeito.
        """
        vpad = player.vpad
        if getattr(vpad, "backend", None) != "uhid":
            return
        identity = player.identity
        if identity.startswith("path:"):
            return
        hidraw_fn = getattr(self._daemon.controller, "hidraw_path", None)
        if not callable(hidraw_fn):
            return
        from hefesto_dualsense4unix.core.physical_report_reader import (
            PhysicalReportReader,
        )

        def _player_hidraw() -> str | None:
            try:
                path = hidraw_fn(identity)
            except Exception:
                return None
            return path if isinstance(path, str) else None

        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            make_broker_opener,
        )

        # BROKER-01 §6.3: o reader deste jogador nasce com o opener
        # broker-aware — reabre o hidraw via fd do broker root mesmo com o nó
        # escondido; sem broker, os.open por caminho (comportamento de hoje).
        reader = PhysicalReportReader(
            path_provider=_player_hidraw,
            vpad=vpad,
            opener=make_broker_opener(self._daemon),
        )
        reader.start()
        player.motion_reader = reader
        logger.info(
            "coop_motion_reader_spawned",
            identity=identity,
            **self._numero_e_indice(player),
        )


    def _player_hidraw_node(self, identity: str) -> str | None:
        """`/dev/hidrawN` do físico DESTE jogador via `hidraw_path(uniq)`, ou None."""
        if identity.startswith("path:"):
            return None
        hidraw_fn = getattr(self._daemon.controller, "hidraw_path", None)
        if not callable(hidraw_fn):
            return None
        with contextlib.suppress(Exception):
            node = hidraw_fn(identity)
            return node if isinstance(node, str) and node else None
        return None

    def _broker_hide_player(self, player: _SecondaryPlayer) -> None:
        """Hide do físico do jogador — SÓ com vpad confirmado E VIVO (BROKER-01)."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import vpad_vivo

        if not vpad_vivo(player.vpad):
            return
        with contextlib.suppress(Exception):
            if self._daemon.is_native_mode():
                return
            node = self._player_hidraw_node(player.identity)
            if node is None:
                return
            from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
                broker_call_nonblocking,
                broker_client_for,
            )

            client = broker_client_for(self._daemon)
            broker_call_nonblocking(self._daemon, lambda: client.hide(node))

    def _broker_restore_player(self, identity: str) -> None:
        """Restore do físico do jogador no `_teardown_player` (best-effort)."""
        with contextlib.suppress(Exception):
            node = self._player_hidraw_node(identity)
            if node is None:
                return
            from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
                broker_call_nonblocking,
                broker_client_for,
            )

            client = broker_client_for(self._daemon)
            broker_call_nonblocking(self._daemon, lambda: client.restore(node))

    def _materialize_launch_env(self) -> None:
        """Regrava as envs do wrapper hefesto-launch (best-effort, DEDUP-04)."""
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import (
                armar_rematerializacao,
                materialize_launch_env,
            )

            materialize_launch_env(self._daemon)
            armar_rematerializacao(self._daemon, motivo="borda de jogador de co-op")

    def _armar_sossego_do_launch_env(self, motivo: str) -> None:
        """Arma o sossego SEM escrever — para a borda que não materializa."""
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import (
                armar_rematerializacao,
            )

            armar_rematerializacao(self._daemon, motivo=motivo)

    def _teardown_player(self, identity: str) -> None:
        player = self._players.pop(identity, None)
        if player is None:
            return
        self._calib_prazo.pop(identity, None)
        self._calib_sem_leitura.discard(identity)
        self._pronto_desde.pop(identity, None)
        self._broker_restore_player(identity)
        with contextlib.suppress(Exception):
            player.reader.set_grab(False)
        with contextlib.suppress(Exception):
            player.reader.stop()
        if player.motion_reader is not None:
            with contextlib.suppress(Exception):
                player.motion_reader.stop()
            player.motion_reader = None
        self._zerar_rumble_do_jogador(identity)
        if player.vpad is not None:
            with contextlib.suppress(Exception):
                player.vpad.stop()
        self._levantar(identity)
        self._revert_single_player_led(identity)
        self._materialize_launch_env()
        logger.info("coop_player_removed", identity=identity, players=self.player_count())

    def _zerar_rumble_do_jogador(self, identity: str) -> None:
        """Manda UM report de stop ao controle que está saindo da mesa."""
        if identity.startswith("path:"):
            return
        force = getattr(self._daemon.controller, "force_rumble_stop", None)
        if not callable(force):
            return
        try:
            force(identity)
        except Exception as exc:
            logger.warning(
                "coop_rumble_stop_na_borda_falhou", identity=identity, err=str(exc)
            )


    def _apply_coop_player_leds(self) -> None:
        """Acende em cada controle o padrão canônico do SEU jogador."""
        # "2+ controles" que nunca existiu. Resultado: com um único DualSense,
        # slot 1 no registry de externos e o DualSense primário recebia 1 do
        if not self._players:
            logger.debug("coop_sem_secundario_nao_escreve_player_led")
            if self._camada_coop:
                self._publicar_camada_coop({})
            return
        padroes = {
            mac: player_led_pattern(numero)
            for mac, numero in self.numeros_de_jogador().items()
        }
        if self._publicar_camada_coop(padroes):
            return
        from hefesto_dualsense4unix.core import sysfs_leds

        try:
            nodes = sysfs_leds.discover()
        except Exception as exc:
            logger.warning("coop_player_led_discover_falhou", err=str(exc))
            return
        for mac, bits in padroes.items():
            node = nodes.get(mac)
            if node is None or not node.set_players(bits):
                logger.warning("coop_player_led_indisponivel", identity=mac)
                continue
            self._leds_overridden = True

    def _alvos_de_numeracao(self) -> list[tuple[str, int]]:
        """Quem recebe número nesta mesa, e o `fallback` de cada um.

        Ordem fixa e declarada — primário primeiro, depois os secundários na
        ordem em que entraram —, porque é ela que decide quem fica com o
        número em caso de empate dentro de `_numero_exibido`. Identidade sem
        MAC (`path:`) fica de fora: não há como casar o controle.
        """
        alvos: list[tuple[str, int]] = []
        primary = self._primary_identity()
        if primary is not None and not primary.startswith("path:"):
            alvos.append((primary, 1))
        for mac, player in self._players.items():
            if mac.startswith("path:"):
                # Sem MAC não há como casar o controle — segue com o padrão
                # broadcast (não deveria acontecer com DualSense real).
                logger.debug(
                    "coop_player_led_sem_mac",
                    identity=mac,
                    player=player.player_index,
                )
                continue
            alvos.append((mac, player.player_index))
        return alvos

    def numeros_de_jogador(self) -> dict[str, int]:
        """MAC -> número ÚNICO deste controle na mesa. FONTE ÚNICA (MESA-CHEIA-12).

        Medição de 15/08/2026, 01h00, com os QUATRO DualSense dela no rádio: o
        desenho aceso na barra de player NÃO era o número que o daemon
        publicava. Do `state_full` e do `/sys/class/leds` ao mesmo tempo:

        (os controles vão pelo LUGAR NA FILA; nenhum endereço real aqui)

        | controle       | `player` publicado | `player_slot` | desenho aceso |
        |----------------|--------------------|---------------|---------------|
        | 1º da fila     | 1                  | 1             | 1             |
        | 4º da fila     | 2                  | 4             | **4**         |
        | 2º da fila     | 3                  | 2             | **2**         |
        | 3º da fila     | 4                  | 3             | **3**         |

        A lâmpada acertava 4 de 4 contra o `player_slot` e 1 de 4 contra o
        `player` — porque eram DOIS espaços de numeração, cada um com o seu
        dono, e nenhum dos dois errado no seu domínio:

        - a lâmpada saía de `_numero_exibido` → `identity_registry.slot_for`,
          a FILA DE CHEGADA (`controllers.json`), colocação entre os
          presentes;
        - o `player` publicado saía de `player_indexes()` → `player_index`,
          o índice de ALOCAÇÃO do vpad do co-op (`_next_player_index`: menor
          livre ≥2, na ordem em que o co-op promoveu cada secundário).

        As duas ordens só coincidem por sorte: a do co-op é a ordem em que o
        grab confirmou nesta sessão, a da fila é a do registro de identidade.
        Um replug basta para separá-las — e nesta mesa elas estavam separadas
        nos três secundários.

        A verdade única é a FILA DE CHEGADA, por decisão dela (sprint
        `2026-08-14-INDICE-a-cor-do-controle-e-o-som-de-cada-jogador`: *"a
        ordem deve ser por ordem de conexão daquele momento"*, e essa ordem
        prevalece). Ela já governava a lâmpada e a cor automática
        (`identity.make_identity_output_provider`); a partir daqui governa
        também o número PUBLICADO — a lâmpada e o rótulo passam a ser a mesma
        função do mesmo MAC, sempre, por construção.

        D-30 / ORDEM-DE-CHEGADA-01 (15/08, 03:54) respondeu QUAL fila é essa,
        e a resposta mudou o dono do inteiro sem mudar uma linha daqui: o
        `slot_for` do registro passou a ordenar pela ordem de conexão DAQUELE
        MOMENTO (o gravado desempata quem chegou junto). A união que a
        MESA-CHEIA-12 fez continua intacta e é o que torna isso barato —
        lâmpada e rótulo são a MESMA função, então trocar a fonte de um
        trocou a do outro, sem chance de voltarem a divergir.

        Sem registro (FakeController, backend legado, dublê de teste) cada um
        cai no seu `fallback` histórico — primário 1, secundários pelo
        `player_index` —, então nada muda para quem não tem fila.
        """
        # G6 (27/09, a troca de cabo do branco: um 5 no azul, um 4 no branco).
        # A passada única deixava o `fallback` de quem estava FORA da mesa (na
        # troca de transporte, sem lâmpada) tomar a carta de quem estava nela.
        # Agora são duas: quem tem carta fica com ela, e só depois quem não tem
        # — O-MODO-XBOX-NAO-E-QUEDA-02, item 6, em `_numeros_em_duas_passadas`
        # (no fim da classe: o mapa de canais cita esta por linha).
        return self._numeros_em_duas_passadas()

    def _numero_exibido(self, identity: str, fallback: int, usados: set[int]) -> int:
        """Número que este controle ACENDE na barra de player (R-24).

        A lâmpada tinha DOIS espaços de numeração disputando-a e essa era a
        queixa literal ("os dois controles aparecem como player 1"):

        - o registro de identidade (`identity_registry`) dá o "Controle N" que
          a GUI, a CLI e a cor automática exibem — keyed por MAC, reservado no
          disconnect, agora estável entre boots (R-23);
        - o co-op tem o `player_index`, o índice de ALOCAÇÃO do vpad (1..N
          contíguo e REUSADO quando alguém sai — VPAD-03); o MAC e o nome do vpad
          saíram dele (E3 e A-MESMA-LINGUA-01), e ele ficou como o `fallback` dos dois.

        São coisas diferentes e as duas estão certas no seu domínio; o erro
        era acender o SEGUNDO na lâmpada. Com o primário cravado em 1 e o Pro
        Nintendo segurando o slot 1 no registro de externos, dois controles
        acendiam "player 1" ao mesmo tempo. E o `player_index` reusa o índice
        de quem saiu: P2 sai, P4 entra e herda o 2 — se P2 volta, dois "player
        2". Aqui a lâmpada passa a falar SÓ o espaço único.

        `fallback` = o `player_index` do co-op, usado quando não há registro
        (FakeController, backend legado, dublê de teste) — sem registro, nada
        muda em relação ao histórico. `usados` garante a última linha de
        defesa: número já tomado NESTA passada nunca acende duas vezes.
        """
        numero = self._numero_da_carta(identity)
        if numero is None or numero in usados:
            numero = fallback
        while numero in usados:
            numero += 1
        return numero

    def _numero_da_carta(self, identity: str) -> int | None:
        """O número da carta deste controle, perguntado ao registro — ou None."""
        registry = getattr(self._daemon, "identity_registry", None)
        lampada = (
            getattr(registry, "numero_da_lampada", None) if registry is not None else None
        )
        slot_for = getattr(registry, "slot_for", None) if registry is not None else None
        consulta = lampada if callable(lampada) else slot_for
        if callable(consulta):
            with contextlib.suppress(Exception):
                bruto = consulta(identity, assign=False)
                if isinstance(bruto, int) and not isinstance(bruto, bool) and bruto >= 1:
                    return bruto
        return None

    def _na_ordem_da_carta(self, identidades: Iterable[str]) -> list[str]:
        """As identidades na ordem do número da carta; sem número, no fim."""
        lista = list(identidades)
        sem_numero = float("inf")
        return sorted(
            lista,
            key=lambda mac: (
                n if (n := self._numero_da_carta(mac)) is not None else sem_numero
            ),
        )

    def _pode_nascer_na_ordem(self, player: _SecondaryPlayer) -> bool:
        """Este jogador PRONTO pode ganhar o vpad agora sem furar a fila?"""
        carta = self._numero_da_carta(player.identity)
        agora = time.monotonic()
        desde = self._pronto_desde.setdefault(player.identity, agora)
        if carta is None:
            return True
        na_frente = [
            outro.identity
            for outro in self._players.values()
            if outro.identity != player.identity
            and outro.vpad is None
            and not outro.cedido_ao_primario
            and outro.reader.grab_state != "failed"
            and (n := self._numero_da_carta(outro.identity)) is not None
            and n < carta
        ]
        if not na_frente:
            self._pronto_desde.pop(player.identity, None)
            return True
        if agora - desde >= ESPERA_PELA_ORDEM_S:
            logger.info(
                "coop_ordem_nao_esperou",
                identity=player.identity,
                carta=carta,
                na_frente=sorted(na_frente),
                esperou_s=round(agora - desde, 2),
            )
            self._pronto_desde.pop(player.identity, None)
            return True
        return False

    def _publicar_camada_coop(
        self, padroes: dict[str, tuple[bool, bool, bool, bool, bool]], *, escrever: bool = True
    ) -> bool:
        """Publica (ou revoga, com `{}`) a camada do co-op no backend (R-13)."""
        ctrl = getattr(self._daemon, "controller", None)
        publicar = getattr(ctrl, "set_coop_outputs", None)
        if not callable(publicar):
            return False
        if padroes == self._camada_coop:
            return True
        from hefesto_dualsense4unix.core.controller import OutputSpec

        try:
            publicar(
                {mac: OutputSpec(player_leds=bits) for mac, bits in padroes.items()}
                or None,
                **({} if escrever else {"escrever": False}),
            )
        except Exception as exc:
            logger.warning("coop_publicar_camada_falhou", err=str(exc))
            return True
        self._camada_coop = dict(padroes)
        self._leds_overridden = bool(padroes)
        return True

    def _profile_player_leds(self) -> tuple[bool, bool, bool, bool, bool] | None:
        """Último padrão de player-LED aplicado pelo perfil/GUI (broadcast)."""
        ctrl = getattr(self._daemon, "controller", None)
        bits = getattr(getattr(ctrl, "_desired", None), "player_leds", None)
        if bits is None or len(bits) != 5:
            return None
        return (bool(bits[0]), bool(bits[1]), bool(bits[2]), bool(bits[3]), bool(bits[4]))

    def _resolved_player_leds(
        self, mac: str
    ) -> tuple[bool, bool, bool, bool, bool] | None:
        """Padrão de player-LED do perfil para `mac`, resolvido POR-UNIQ."""
        ctrl = getattr(self._daemon, "controller", None)
        reader = getattr(ctrl, "resolved_player_leds_for", None)
        if not callable(reader):
            return self._profile_player_leds()
        try:
            bits = reader(mac)
        except Exception as exc:
            logger.warning(
                "coop_player_led_resolucao_falhou", identity=mac, err=str(exc)
            )
            return None
        if bits is None or len(bits) != 5:
            return None
        return (bool(bits[0]), bool(bits[1]), bool(bits[2]), bool(bits[3]), bool(bits[4]))

    def _revert_single_player_led(self, mac: str) -> None:
        """Devolve UM controle (por MAC) ao padrão do perfil. Best-effort."""
        if callable(getattr(getattr(self._daemon, "controller", None),
                            "set_coop_outputs", None)):
            return
        if not self._leds_overridden or mac.startswith("path:"):
            return
        bits = self._resolved_player_leds(mac)
        if bits is None:
            return
        from hefesto_dualsense4unix.core import sysfs_leds

        try:
            node = sysfs_leds.discover().get(mac)
        except Exception:
            node = None
        if node is None or not node.set_players(bits):
            logger.debug("coop_player_led_revert_indisponivel", identity=mac)

    def _revert_player_leds(self) -> None:
        """Restaura o padrão do perfil em TODOS os controles (co-op desligado)."""
        if not self._leds_overridden:
            return
        self._leds_overridden = False
        ctrl = getattr(self._daemon, "controller", None)
        if ctrl is None:
            logger.debug("coop_player_led_revert_sem_padrao")
            return
        if self._camada_coop and self._publicar_camada_coop({}):
            return
        bits = self._profile_player_leds()
        if not callable(getattr(ctrl, "resolved_player_leds_for", None)):
            if bits is None:
                logger.debug("coop_player_led_revert_sem_padrao")
                return
            try:
                ctrl.set_player_leds(bits)
            except Exception as exc:
                logger.warning("coop_player_led_revert_falhou", err=str(exc))
            return
        if bits is not None:
            from hefesto_dualsense4unix.core.controller import OutputSpec

            try:
                ctrl.apply_output_defaults(OutputSpec(player_leds=bits))
            except Exception as exc:
                logger.warning("coop_player_led_revert_falhou", err=str(exc))
        self._reassert_overridden_player_leds(default=bits)

    def _reassert_overridden_player_leds(
        self, default: tuple[bool, bool, bool, bool, bool] | None
    ) -> None:
        """Re-escreve por-uniq (sysfs por MAC) os conectados com override efetivo."""
        ctrl = getattr(self._daemon, "controller", None)
        describe = getattr(ctrl, "describe_controllers", None)
        if not callable(describe):
            return
        try:
            infos = describe()
        except Exception as exc:
            logger.warning("coop_player_led_revert_describe_falhou", err=str(exc))
            return
        pending: list[tuple[str, tuple[bool, bool, bool, bool, bool]]] = []
        for info in infos:
            if not info.get("connected"):
                continue
            uniq = info.get("uniq")
            if not isinstance(uniq, str) or not uniq:
                continue
            bits = self._resolved_player_leds(uniq)
            if bits is None or bits == default:
                continue
            pending.append((uniq, bits))
        if not pending:
            return
        from hefesto_dualsense4unix.core import sysfs_leds

        try:
            nodes = sysfs_leds.discover()
        except Exception as exc:
            logger.warning("coop_player_led_discover_falhou", err=str(exc))
            return
        for mac, bits in pending:
            node = nodes.get(mac)
            if node is None or not node.set_players(bits):
                logger.debug("coop_player_led_revert_indisponivel", identity=mac)


    def forward_all(self) -> None:
        """Repassa cada secundário ao seu gamepad virtual. Chamado por tick."""
        self._fio_do_laco = threading.get_ident()
        if self._ordem_pendente:
            self._ordem_pendente = False
            if self.should_be_active():
                self._corrigir_a_ordem()
        self._recolher_os_cedidos()
        self._promote_pending()
        troca = remapeamento_ativo(getattr(self._daemon, "store", None))
        arranjo_de_movimento = roteador_ativo(getattr(self._daemon, "store", None))
        marcas = marcas_da_partida(self._daemon)
        for player in list(self._players.values()):
            if player.vpad is None:
                continue
            if player.cedido_ao_primario:
                # do `_recolher_os_cedidos` acima — este `continue` é o que
                continue
            try:
                snap = player.reader.snapshot()
                botoes, l2, r2 = snap.buttons_pressed, snap.l2_raw, snap.r2_raw
                lx, ly, rx, ry = snap.lx, snap.ly, snap.rx, snap.ry
                soltos = self._apertos_vistos_de(player.identity).soltos(
                    leitor=player.reader,
                    pad=player.vpad,
                    pronto_em=getattr(self._daemon, "_input_ready_at", None),
                    apertos=getattr(snap, "apertos", None),
                    apertados=botoes,
                )
                if marcas is not None:
                    marcas.anotar(
                        player.identity, botoes=botoes, lx=lx, ly=ly, rx=rx, ry=ry, l2=l2, r2=r2
                    )
                if arranjo_de_movimento is not None:
                    botoes, l2 = aplicar_o_toque(
                        self._daemon,
                        arranjo_de_movimento,
                        uniq=player.identity,
                        botoes=botoes,
                        l2=l2,
                    )
                    lx, ly, rx, ry = aplicar_o_movimento(
                        self._daemon,
                        arranjo_de_movimento,
                        uniq=player.identity,
                        lx=lx,
                        ly=ly,
                        rx=rx,
                        ry=ry,
                        botoes=botoes,
                    )
                da_mao = botoes
                if troca:
                    botoes, l2, r2 = traduzir_remapeamento(botoes, l2, r2, troca)
                player.vpad.forward_analog(
                    lx=lx,
                    ly=ly,
                    rx=rx,
                    ry=ry,
                    l2=l2,
                    r2=r2,
                )
                if soltos:
                    com_soltos = da_mao | soltos
                    if troca:
                        com_soltos = traduzir_remapeamento(com_soltos, l2, r2, troca)[0]
                    player.vpad.forward_buttons(com_soltos)
                player.vpad.forward_buttons(botoes)
                pump = getattr(player.vpad, "pump_ff", None)
                if pump is not None:
                    pump()
            except Exception as exc:
                logger.warning("coop_forward_failed", evdev=player.evdev_path, err=str(exc))


    def _jogo_com_a_autoridade(self) -> bool:
        """O jogo está com a autoridade (o mesmo sinal STICKY da R-04)."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            _autoridade_do_jogo,
        )

        return _autoridade_do_jogo(self._daemon)

    def _no_fio_do_laco(self) -> bool:
        """Estamos na thread do poll loop (ou ele ainda não rodou: dublês)?"""
        fio = self._fio_do_laco
        return fio is None or fio == threading.get_ident()

    def _assentar(self, chave: str) -> None:
        """Um vpad nasceu: ele toma um lugar no jogo."""
        if chave != _CHAVE_DO_P1:
            self._acompanhar_o_p1()
        self._levantar(chave)
        self._nascimentos += 1
        self._nascido_em[chave] = self._nascimentos
        if self._jogo_com_a_autoridade():
            lugar = 0
            while lugar in self._mesa_do_jogo:
                lugar += 1
        else:
            self._compactar()
            lugar = len(self._mesa_do_jogo)
        self._mesa_do_jogo[lugar] = chave

    def _levantar(self, chave: str) -> None:
        """O vpad de `chave` morreu: o lugar dele fica livre. Idempotente."""
        for lugar, quem in list(self._mesa_do_jogo.items()):
            if quem == chave:
                del self._mesa_do_jogo[lugar]
        self._nascido_em.pop(chave, None)

    def _compactar(self) -> None:
        """Sem jogo aberto, o lugar de cada vpad é a ordem em que ele nasceu."""
        ordem = sorted(
            self._mesa_do_jogo.values(), key=lambda c: self._nascido_em.get(c, 0)
        )
        self._mesa_do_jogo = dict(enumerate(ordem))

    def _acompanhar_o_p1(self) -> None:
        """Senta, levanta ou re-senta o vpad do P1 conforme o objeto vivo hoje."""
        atual = getattr(self._daemon, "_gamepad_device", None)
        if atual is self._vpad_do_p1_visto:
            return
        self._vpad_do_p1_visto = atual
        if atual is None:
            self._levantar(_CHAVE_DO_P1)
        else:
            self._assentar(_CHAVE_DO_P1)

    def _carta_da_chave(self, chave: str) -> int | None:
        """A carta de quem está (ou vai estar) no lugar: o P1 é o primário."""
        if chave != _CHAVE_DO_P1:
            return self._numero_da_carta(chave)
        primario = self._primary_identity()
        if primario is None or primario.startswith("path:"):
            return None
        return self._numero_da_carta(primario)

    def _posto_vago(self, chave: str, autoridade: bool) -> bool:
        """`chave` é o vpad do P1 parado à espera do primário que caiu?"""
        if chave != _CHAVE_DO_P1 or not autoridade:
            return False
        primario = self._primary_identity()
        if primario is None or primario.startswith("path:"):
            return False
        return self.o_posto_do_p1_espera(primario)

    def _nascer_na_ordem(self, player: _SecondaryPlayer) -> None:
        """Dá o vpad a `player` — recriando ANTES quem ficaria fora de ordem."""
        if not self._no_fio_do_laco():
            self._promote_player(player)
            self._ordem_pendente = True
            return
        if not self._calibration_pronta(player.identity)[0]:
            self._promote_player(player)
            return
        self._corrigir_a_ordem(nascer=player)

    def _corrigir_a_ordem(self, nascer: _SecondaryPlayer | None = None) -> None:
        """Faz o jogo ver a carta: recria quem ficou fora de ordem, e nasce `nascer`."""
        if not self._no_fio_do_laco():
            self._ordem_pendente = True
            return
        try:
            self._ordenar(nascer)
        except Exception as exc:
            logger.warning("coop_ordem_falhou", err=str(exc))
            if nascer is not None and nascer.vpad is None and (
                self._players.get(nascer.identity) is nascer
            ):
                self._promote_player(nascer)

    def _ordenar(self, nascer: _SecondaryPlayer | None) -> None:
        """O corpo de `_corrigir_a_ordem`, já na thread do laço."""
        self._acompanhar_o_p1()
        autoridade = self._jogo_com_a_autoridade()
        if not autoridade:
            self._compactar()
        chaves_novas = [nascer.identity] if nascer is not None else []
        cartas: dict[str, int] = {}
        vago = False
        for lugar, chave in [
            *self._mesa_do_jogo.items(),
            *((None, c) for c in chaves_novas),
        ]:
            carta = self._carta_da_chave(chave)
            if carta is None and lugar is not None and self._posto_vago(chave, autoridade):
                vago = True
                carta = lugar + 1
            elif carta is None:
                if nascer is not None:
                    self._promote_player(nascer)
                return
            cartas[chave] = carta
        recriar, inteira = planejar_a_ordem(
            self._mesa_do_jogo,
            cartas,
            chaves_novas,
            fixos=frozenset({_CHAVE_DO_P1}) if autoridade else frozenset(),
            compacta=not autoridade,
        )
        if not autoridade:
            recriar = self._com_os_nomes_velhos(recriar, cartas)
        if vago:
            cartas_no_diario = {_rotulo(c): n for c, n in cartas.items() if c != _CHAVE_DO_P1}
        else:
            cartas_no_diario = {_rotulo(c): n for c, n in cartas.items()}
        if not vago and inteira != (not self._p1_espera_o_jogo):
            self._p1_espera_o_jogo = not inteira
            logger.info(
                "coop_ordem_do_p1_espera_o_jogo"
                if not inteira
                else "coop_ordem_do_p1_voltou",
                cartas=cartas_no_diario,
            )
        if recriar:
            assinatura = (tuple(sorted(cartas.items())), tuple(recriar))
            if assinatura == self._ultima_recriacao:
                if not self._ordem_travada:
                    self._ordem_travada = True
                    logger.warning(
                        "coop_ordem_nao_convergiu",
                        recriar=[_rotulo(c) for c in recriar],
                    )
                recriar = []
            else:
                self._ultima_recriacao = assinatura
                logger.info(
                    "coop_ordem_recriada",
                    recriar=[_rotulo(c) for c in recriar],
                    cartas=cartas_no_diario,
                    jogo=autoridade,
                )
                from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                    _recriacao_bloqueada_por_jogo,
                )

                _recriacao_bloqueada_por_jogo(
                    self._daemon,
                    origin="ordem_do_coop",
                    motivo="ordem:" + ",".join(_rotulo(c) for c in recriar),
                )
        elif not chaves_novas:
            self._ultima_recriacao = None
            self._ordem_travada = False
        for chave in recriar:
            self._derrubar_para_renascer(chave)
        for chave in sorted([*recriar, *chaves_novas], key=cartas.__getitem__):
            if chave == _CHAVE_DO_P1:
                self._reerguer_o_p1()
                continue
            jogador = self._players.get(chave)
            if jogador is not None and jogador.vpad is None:
                self._promote_player(jogador)

    def _derrubar_para_renascer(self, chave: str) -> None:
        """Derruba SÓ o vpad de `chave`: o físico segue preso e escondido."""
        if chave == _CHAVE_DO_P1:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                stop_gamepad_emulation,
            )

            stop_gamepad_emulation(self._daemon, persist=False, release_grab=False)
            self._acompanhar_o_p1()
            return
        jogador = self._players.get(chave)
        if jogador is None or jogador.vpad is None:
            return
        if jogador.motion_reader is not None:
            with contextlib.suppress(Exception):
                jogador.motion_reader.stop()
            jogador.motion_reader = None
        self._zerar_rumble_do_jogador(chave)
        with contextlib.suppress(Exception):
            jogador.vpad.stop()
        jogador.vpad = None
        self._levantar(chave)

    def _reerguer_o_p1(self) -> None:
        """O vpad do P1 nasce de novo, com a máscara e o caminho de antes."""
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            DESFECHOS_EMULACAO_ATIVA,
            reerguer_o_p1,
        )

        # sem o dono, a mesa no Modo Xbox via o P1 voltar DualSense e a tela e
        desfecho = reerguer_o_p1(self._daemon, motivo="ordem_do_coop")
        if desfecho not in DESFECHOS_EMULACAO_ATIVA:
            logger.warning("coop_ordem_o_p1_nao_voltou", desfecho=desfecho)
        self._acompanhar_o_p1()


    def disable(self) -> None:
        """Desmonta todos os secundários (solta grab, fecha uinput) e restaura"""
        for key in list(self._players):
            self._teardown_player(key)
        self._revert_player_leds()

    stop_all = disable


    def _pendurar_a_espera_do_posto(self, ctrl: Any) -> None:
        """A segunda metade do `_garantir_aviso_de_primario`: a pergunta da vaga."""
        pendurar = getattr(ctrl, "set_espera_do_posto", None)
        if callable(pendurar):
            pendurar(self.o_posto_do_p1_espera)
        logger.debug("coop_aviso_de_primario_ligado")

    def o_posto_do_p1_espera(self, uniq: str) -> bool:
        """O posto do P1 que caiu ESPERA por ele? — a decisão de 24/09/2026.

        `D-2409-O-JOGO-ESPERA-O-LUGAR-GUARDADO`, por delegação dela: com o P1
        fora dentro do prazo, o vpad do jogador 1 fica parado à espera dele e o
        P2 continua no vpad 2. São três as decisões dela que já diziam isso —
        *o primário espera a carta 1* e *o Hefesto manda no número, sempre*
        (23/09), e a linha 17, *os outros três não trocam de número*.

        O backend pergunta sob o `_io_lock` (`_quem_senta_no_posto`), então as
        três perguntas são de memória:

        1. **o co-op está de pé** (`should_be_active`): cada controle tem o
           próprio vpad. Fora do co-op o outro controle é a RESERVA e assume na
           hora — é o gesto dela de desligar um e seguir jogando com o outro;
        2. **o jogo está com a autoridade** (o sinal pegajoso da R-04): sem
           jogo, o dono do posto de P1 também navega o PC (a aba Navegação), e
           parar o posto tiraria o mouse de quem ficou por até 30 s sem nenhum
           jogo do outro lado para seguir o número;
        3. **o lugar dele espera na mesa**
           (`ControllerIdentityRegistry.o_lugar_espera`): o prazo, a gente nova
           que refaz a mesa e o «Renumerar agora» são do registro, o mesmo dono
           do número que a tela e a lâmpada mostram.
        """
        if not self.should_be_active() or not self._jogo_com_a_autoridade():
            return False
        registry = getattr(self._daemon, "identity_registry", None)
        pergunta = getattr(registry, "o_lugar_espera", None)
        return callable(pergunta) and bool(pergunta(uniq))


    def quem_alimenta_cada_vpad(self) -> dict[str, str]:
        """``{MAC que o vpad veste: identidade do físico que o alimenta}``. Só leitura."""
        alimenta: dict[str, str] = {}
        primario = self._primary_identity()
        posto = getattr(self._daemon, "_gamepad_device", None)
        mac = _texto_ou_none(getattr(posto, "mac", None))
        if mac and primario is not None and not primario.startswith("path:"):
            alimenta[mac.lower()] = primario
        for identidade, jogador in list(self._players.items()):
            if jogador.vpad is None or jogador.cedido_ao_primario:
                continue
            mac = _texto_ou_none(getattr(jogador.vpad, "mac", None))
            if mac and not identidade.startswith("path:"):
                alimenta[mac.lower()] = identidade
        return alimenta


    def _numeros_em_duas_passadas(self) -> dict[str, int]:
        """O corpo de `numeros_de_jogador`: quem tem carta fica com ela, os outros depois."""
        alvos = self._alvos_de_numeracao()
        cartas = {mac: self._numero_da_carta(mac) for mac, _fallback in alvos}
        numeros: dict[str, int] = {}
        usados: set[int] = set()
        for mac, _fallback in alvos:
            carta = cartas[mac]
            if carta is not None and carta not in usados:
                numeros[mac] = carta
                usados.add(carta)
        for mac, fallback in alvos:
            if mac in numeros:
                continue
            numero = self._assento_guardado(mac)
            if numero is None or numero in usados:
                numero = fallback
            while numero in usados:
                numero += 1
            numeros[mac] = numero
            usados.add(numero)
        return {mac: numeros[mac] for mac, _fallback in alvos}

    def _assento_guardado(self, identity: str) -> int | None:
        """O número do assento de `identity` na mesa do registro — ou None."""
        registry = getattr(self._daemon, "identity_registry", None)
        slot_for = getattr(registry, "slot_for", None) if registry is not None else None
        if not callable(slot_for):
            return None
        bruto: Any = None
        with contextlib.suppress(Exception):
            bruto = slot_for(identity, assign=False)
        if isinstance(bruto, int) and not isinstance(bruto, bool) and bruto >= 1:
            return bruto
        return None

    def _repintar_se_o_numero_mudou(self) -> None:
        """A barra de jogador segue o número mesmo sem hotplug (G6)."""
        self.publicar_os_numeros(escrever=True)


    _nomes_velhos_ditos: list[tuple[int, int]] | None = None

    def _nomes_que_ficaram_para_tras(self, cartas: Mapping[str, int]) -> dict[str, tuple[int, int]]:
        """Chave da mesa do jogo -> (o número no nome do vpad, o número de agora).

        O nome vai no `UHID_CREATE2` e não se troca vivo
        (:meth:`numero_para_o_nome`): um vpad que nasceu antes de a fila andar
        guarda o número de quando nasceu. Medido na bancada de queda em
        28/09/2026, nas 24 ordens de chegada dos quatro e sem jogo: a carta 1
        sai além do prazo, a NUM-01 renumera, e os vpads do roxo e do azul
        seguem «Hefesto P3» e «Hefesto P4» com a carta dizendo 2 e 3 — a
        ordem está certa, então o co-op não os recriava. Com o jogo aberto a
        ordem já os recria (o boneco anda junto), e com o `-02` o posto do P1
        é a carta 1.

        O número de agora é o do dono do nome (:meth:`numeros_de_jogador`, o
        mesmo que :meth:`numero_para_o_nome` e o `nome_divergente` leem). O do
        nome é o `vpad_indice` de :func:`identidade_do_vpad`: o `uinput` não
        carrega número no nome e fica de fora.
        """
        numeros = self.numeros_de_jogador()
        primario = self._primary_identity()
        velhos: dict[str, tuple[int, int]] = {}
        for chave in self._mesa_do_jogo.values():
            if chave not in cartas:
                continue
            if chave == _CHAVE_DO_P1:
                vpad = getattr(self._daemon, "_gamepad_device", None)
                dono = primario
            else:
                jogador = self._players.get(chave)
                if jogador is None or jogador.cedido_ao_primario:
                    continue
                vpad, dono = jogador.vpad, chave
            if vpad is None or dono is None or dono.startswith("path:"):
                continue
            no_nome = identidade_do_vpad(vpad)["vpad_indice"]
            agora = numeros.get(dono)
            if no_nome is not None and agora is not None and no_nome != agora:
                velhos[chave] = (no_nome, agora)
        return velhos

    def _a_mesa_esta_assentada(self) -> bool:
        """Nenhum lugar guardado, e todo controle da mesa com o virtual dele."""
        registro = getattr(self._daemon, "identity_registry", None)
        guardados = getattr(registro, "guardados", None)
        conectados = getattr(registro, "snapshot_connected", None)
        if not callable(guardados) or not callable(conectados):
            return True
        try:
            if guardados():
                return False
            na_mesa = len(conectados())
        except Exception:
            return False
        com_virtual = sum(
            1
            for jogador in self._players.values()
            if jogador.vpad is not None and not jogador.cedido_ao_primario
        )
        if (
            getattr(self._daemon, "_gamepad_device", None) is not None
            and self._primary_identity() is not None
        ):
            com_virtual += 1
        return com_virtual >= na_mesa

    def _com_os_nomes_velhos(self, recriar: list[str], cartas: Mapping[str, int]) -> list[str]:
        """`recriar` mais quem tem o nome velho, na ordem do jogo. Só com o jogo SOLTO."""
        if not self._a_mesa_esta_assentada():
            return recriar
        velhos = self._nomes_que_ficaram_para_tras(cartas)
        if not velhos:
            self._nomes_velhos_ditos = None
            return recriar
        piso = min(cartas[chave] for chave in velhos)
        sentados = [chave for _lugar, chave in sorted(self._mesa_do_jogo.items())]
        juntos = [c for c in sentados if c in recriar or cartas.get(c, 0) >= piso]
        nomes = sorted(velhos.values())
        if nomes != self._nomes_velhos_ditos:
            self._nomes_velhos_ditos = nomes
            logger.info("coop_nome_do_virtual_renasce", nomes=nomes, recriados=len(juntos))
        return juntos


    def numero_do_diario(self, identity: str | None, indice: int) -> int:
        """O número que o diário diz para este jogador: o da CARTA."""
        if not identity or identity.startswith("path:"):
            return indice
        return self.numero_para_o_nome(identity, indice)

    def numero_do_primario_no_diario(self) -> int:
        """O número do controle que alimenta o pad do P1, para o diário (1 sem carta)."""
        return self.numero_do_diario(self._primary_identity(), 1)

    def _numero_e_indice(self, player: _SecondaryPlayer) -> dict[str, int]:
        """Os dois campos do diário de um secundário: ``player`` (a carta) e ``indice``."""
        return {
            "player": self.numero_do_diario(player.identity, player.player_index),
            "indice": player.player_index,
        }


    def publicar_os_numeros(self, *, escrever: bool) -> bool:
        """Republica a camada do co-op com os números de agora. Devolve se mudou."""
        if not self._players:
            return False
        ctrl = getattr(self._daemon, "controller", None)
        if not callable(getattr(ctrl, "set_coop_outputs", None)):
            return False
        numeros = self.numeros_de_jogador()
        padroes = {mac: player_led_pattern(numero) for mac, numero in numeros.items()}
        if padroes == self._camada_coop:
            return False
        from hefesto_dualsense4unix.daemon.battery_journal import mascarar_endereco

        diario = logger.info if escrever else logger.debug
        diario(
            "coop_numero_repintado" if escrever else "coop_numero_republicado",
            numeros={mascarar_endereco(m): n for m, n in numeros.items()},
        )
        return self._publicar_camada_coop(padroes, escrever=escrever)


    _apertos_vistos: dict[str, Any] | None = None

    def _apertos_vistos_de(self, identity: str) -> Any:
        """O `gamepad.ApertosVistos` deste jogador, criado na primeira entrega."""
        if self._apertos_vistos is None:
            self._apertos_vistos = {}
        vistos = self._apertos_vistos.get(identity)
        if vistos is None:
            vistos = self._apertos_vistos[identity] = ApertosVistos()
        return vistos


from hefesto_dualsense4unix.core.remapeamento_de_botao import (  # noqa: E402
    ativo as remapeamento_ativo,
)
from hefesto_dualsense4unix.core.remapeamento_de_botao import (  # noqa: E402
    traduzir as traduzir_remapeamento,
)
from hefesto_dualsense4unix.core.roteador_de_movimento import (  # noqa: E402
    ativo as roteador_ativo,
)
from hefesto_dualsense4unix.daemon.subsystems.gamepad import (  # noqa: E402
    ApertosVistos,
    aplicar_o_movimento,
    aplicar_o_toque,
    ralos_do_mic,
)
from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import (  # noqa: E402
    marcas_da_partida,
)


def _numeros_sem_vpad(
    daemon: DaemonProtocol, controllers: Sequence[Mapping[str, object]]
) -> list[int | None]:
    """O número de cada controle quando NÃO há gamepad virtual de pé.

    COOP-NA-CONEXAO-NATIVA-01 (06/09/2026), Caminho B. Sem vpad há DOIS estados
    diferentes, e até hoje os dois devolviam ``None``:

    - **Controlar o PC** (desktop): o controle mexe no PC, não há jogo do outro
      lado e não há jogador nenhum — ``None`` continua sendo a resposta certa;
    - **Conexão Nativa (Sony)**: o jogo abre o controle FÍSICO e fala direto com
      ele. Não há intermediário, mas há controle na mão de alguém, e o número
      dele **já está calculado** — o ``identity_registry`` é chaveado pelo MAC e
      não consulta modo nenhum (``daemon/lifecycle.py:2849-2851`` roda o
      ``_sync_identity_registry`` antes do gate de conexão, a cada 2 s). Era
      dado pronto que a tela não publicava.

    **A PREMISSA QUE CAIU, e ela estava escrita:** o docstring de
    :func:`resolve_player_numbers` dizia *"sem gamepad virtual (modo
    desktop/nativo): não existe jogador"*. Isso é verdade do desktop e falso da
    Conexão Nativa — o modo mais fiel ao aparelho era o único em que a tela
    dizia que ninguém era jogador.

    **LEITURA PURA, e o ``assign=False`` é o que a mantém assim:** perguntar o
    número não pode dar lugar na fila a ninguém. É o mesmo contrato do
    ``ipc_handlers._player_slot_for``, e é por ele que o ``player`` e o
    ``player_slot`` do payload passam a concordar neste modo, em vez de
    discordarem sem que a tela saiba por quê.

    **O ``is not True`` é literal de propósito:** com o daemon dublado por
    ``MagicMock``, ``is_native_mode()`` devolve um mock TRUTHY, e um ``if`` solto
    numeraria a mesa inteira num teste que nunca falou de modo nenhum. Mesma
    blindagem do ``isinstance(number, int)`` do irmão abaixo.

    **E O GATE DO CO-OP CONTINUA FECHADO NESTE MODO — §9 da sprint, e é decisão,
    não a metade que faltou.** Se você veio até aqui para *"ligar o co-op na
    Conexão Nativa"* abrindo o :meth:`CoopManager.should_be_active`, esse
    caminho não existe: o mecanismo do co-op desta casa é *grab do físico + um
    vpad por jogador* (``_spawn_player``), e pôr-se no meio é exatamente o que a
    Conexão Nativa dispensa — abrir aquele gate **desfaria o modo que ela
    pediu**, pela mesma razão que já mantém a exceção de
    ``lifecycle.py:1611-1612``. Ou o jogo conta os dois físicos sozinho, ou
    alguém tem de estar no meio (o Caminho D, que é oferta e continua sem a
    palavra dela). A régua que trava isto é
    ``tests/unit/test_o_coop_vive_na_conexao_nativa.py``.

    **POR QUE ESTE PARÁGRAFO MORA AQUI e não lá em cima**, que é onde ele
    seria lido primeiro: ``docs/data/mapa-controles.csv`` cita
    ``coop.py:486-496``, ``:865`` e ``:880`` por FAIXA, e uma linha
    acrescentada antes delas apodrece as seis citações no portão
    ``citacoes-de-linha``. O mapa é da SPECS-A-PROCEDENCIA-01 e não se edita
    daqui — logo o topo deste arquivo está congelado para quem não o possui.
    Medido nesta leva, com o portão vermelho na mão.
    """
    vazio: list[int | None] = [None] * len(controllers)
    nativo = getattr(daemon, "is_native_mode", None)
    if not callable(nativo):
        return vazio
    ligado: Any = None
    with contextlib.suppress(Exception):
        ligado = nativo()
    if ligado is not True:
        return vazio
    registro = getattr(daemon, "identity_registry", None)
    slot_for = getattr(registro, "slot_for", None) if registro is not None else None
    if not callable(slot_for):
        return vazio
    fora: list[int | None] = []
    for ctrl in controllers:
        uniq = ctrl.get("uniq")
        if not bool(ctrl.get("connected")) or not isinstance(uniq, str):
            fora.append(None)
            continue
        bruto: Any = None
        with contextlib.suppress(Exception):
            bruto = slot_for(uniq, assign=False)
        certo = isinstance(bruto, int) and not isinstance(bruto, bool) and bruto > 0
        fora.append(bruto if certo else None)
    return fora


def resolve_player_numbers(
    daemon: DaemonProtocol, controllers: Sequence[Mapping[str, object]]
) -> list[int | None]:
    """Número do jogador que o JOGO vê, para cada controle de `controllers`."""
    if getattr(daemon, "_gamepad_device", None) is None:
        return _numeros_sem_vpad(daemon, controllers)
    connected = [bool(c.get("connected")) for c in controllers]
    coop_on = bool(getattr(getattr(daemon, "config", None), "coop_enabled", False))
    manager = getattr(daemon, "_coop_manager", None)
    if not coop_on or manager is None:
        return [1 if ok else None for ok in connected]
    index_by_mac = manager.player_indexes()
    out: list[int | None] = []
    for ctrl, ok in zip(controllers, connected, strict=True):
        uniq = ctrl.get("uniq")
        number = index_by_mac.get(uniq) if ok and isinstance(uniq, str) else None
        # Blindagem de serialização (mesma do `_as_str_or_none` do state_full):
        out.append(
            number if isinstance(number, int) and not isinstance(number, bool) else None
        )
    return out


def get_coop_manager(daemon: DaemonProtocol) -> CoopManager:
    """Retorna o `CoopManager` do daemon, criando-o sob demanda (lazy)."""
    manager = getattr(daemon, "_coop_manager", None)
    if manager is None:
        manager = CoopManager(daemon)
        daemon._coop_manager = manager
    return manager


def numero_do_nome_do_primario(daemon: Any, fallback: int = 1) -> int:
    """O número que vai DENTRO do nome do vpad do P1. A-MESMA-LINGUA-01."""
    manager = getattr(daemon, "_coop_manager", None)
    if not isinstance(manager, CoopManager):
        return fallback
    try:
        identity = manager._primary_identity()
        if identity is None or identity.startswith("path:"):
            return fallback
        return manager.numero_para_o_nome(identity, fallback)
    except Exception as exc:
        logger.debug("numero_do_nome_do_primario_falhou", err=str(exc))
        return fallback


_CHAVE_DO_P1 = "<p1>"


def _rotulo(chave: str) -> str:
    return "p1" if chave == _CHAVE_DO_P1 else chave


def _a_mesa_depois(
    mesa: Mapping[int, str],
    recriar: Sequence[str],
    nascer: Sequence[str],
    cartas: Mapping[str, int],
    *,
    compacta: bool,
) -> dict[int, str]:
    """Lugar do jogo -> chave depois de derrubar `recriar` e nascer o resto."""
    restam = {lugar: c for lugar, c in mesa.items() if c not in recriar}
    if compacta:
        restam = dict(enumerate(c for _lugar, c in sorted(restam.items())))
    livre = 0
    for chave in sorted([*recriar, *nascer], key=cartas.__getitem__):
        while livre in restam:
            livre += 1
        restam[livre] = chave
    return dict(sorted(restam.items()))


def _em_ordem(numeros: Sequence[int]) -> bool:
    return all(a <= b for a, b in pairwise(numeros))


def _fora_do_boneco(depois: Mapping[int, str], cartas: Mapping[str, int]) -> int:
    """Quantos o jogo mexe num boneco que não é o número da carta deles."""
    return sum(1 for lugar, chave in depois.items() if lugar != cartas[chave] - 1)


def _a_faixa(
    mesa: Mapping[int, str],
    cartas: Mapping[str, int],
    nascer: Sequence[str],
    fixos: frozenset[str],
    melhor: tuple[int, list[str], bool],
) -> tuple[int, list[str], bool]:
    """O plano por FAIXA de cartas, para quando o sufixo deixa gente fora do boneco."""
    parada = _a_mesa_depois(mesa, [], nascer, cartas, compacta=False)
    if not _em_ordem([cartas[c] for c in parada.values() if c not in fixos]):
        return melhor
    sentados = [c for _lugar, c in sorted(mesa.items())]
    limites = sorted({*(cartas[c] for c in sentados), *(cartas[c] for c in nascer)})
    for i, piso in enumerate(limites):
        for teto in limites[i:]:
            faixa = [c for c in sentados if piso <= cartas[c] <= teto and c not in fixos]
            depois = _a_mesa_depois(mesa, faixa, nascer, cartas, compacta=False)
            if any(lugar != cartas[c] - 1 for lugar, c in depois.items() if c in faixa):
                continue
            if not _em_ordem([cartas[c] for c in depois.values() if c not in fixos]):
                continue
            fora = _fora_do_boneco(depois, cartas)
            if (fora, len(faixa)) < (melhor[0], len(melhor[1])):
                melhor = (fora, faixa, _em_ordem([cartas[c] for c in depois.values()]))
    return melhor


def planejar_a_ordem(
    mesa: Mapping[int, str],
    cartas: Mapping[str, int],
    nascer: Sequence[str] = (),
    *,
    fixos: frozenset[str] = frozenset(),
    compacta: bool = False,
) -> tuple[list[str], bool]:
    """Quem recriar para o jogo ver as cartas em ordem — e se a ordem fecha inteira."""
    sentados = [c for _lugar, c in sorted(mesa.items())]
    lugar_de = {c: lugar for lugar, c in mesa.items()}
    limites = sorted({*(cartas[c] for c in sentados), *(cartas[c] for c in nascer)})
    candidatos = [max(limites, default=0) + 1, *reversed(limites)]
    melhor: tuple[int, list[str], bool] | None = None
    for t in candidatos:
        recriar = [c for c in sentados if cartas[c] >= t and c not in fixos]
        if melhor is not None and any(
            lugar_de[c] == cartas[c] - 1 for c in recriar if c not in melhor[1]
        ):
            break
        depois = _a_mesa_depois(mesa, recriar, nascer, cartas, compacta=compacta)
        if not _em_ordem([cartas[c] for c in depois.values() if c not in fixos]):
            continue
        fora = _fora_do_boneco(depois, cartas)
        if melhor is None or fora < melhor[0]:
            melhor = (fora, recriar, _em_ordem([cartas[c] for c in depois.values()]))
    if melhor is None:
        return [], False
    if melhor[0] and not compacta:
        melhor = _a_faixa(mesa, cartas, nascer, fixos, melhor)
    return melhor[1], melhor[2]


__all__ = [
    "CoopManager",
    "calibration_cache",
    "get_coop_manager",
    "numero_do_nome_do_primario",
    "planejar_a_ordem",
    "player_led_pattern",
    "resolve_player_numbers",
    "secundarios_fora_da_mesa",
]
