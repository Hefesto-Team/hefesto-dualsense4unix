"""Handlers JSON-RPC do `IpcServer` (AUDIT-FINDING-IPC-SERVER-SPLIT-01), em mixin
`IpcHandlersMixin`.

Separado de `ipc_server.py` para manter o dispatcher de IO enxuto; o `IpcServer` herda e registra os
`self._handle_*` em `__post_init__`.
"""
from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import os
import time
from collections.abc import Callable
from dataclasses import asdict, replace
from typing import TYPE_CHECKING, Any, Literal, cast

from hefesto_dualsense4unix.core import escritor_cru as _escritor_cru
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.core.trigger_effects import off as trigger_off
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import (
    apply_rumble_policy,
    uniq_do_alvo_de_output,
)
from hefesto_dualsense4unix.daemon.subsystems import recado_do_microfone
from hefesto_dualsense4unix.integrations import sinal_da_barra as _sinal_da_barra
from hefesto_dualsense4unix.integrations.no_do_vpad import (
    NO_DESCONHECIDO,
    no_ainda_vale,
    resolver_no_do_vpad,
)
from hefesto_dualsense4unix.profiles.schema import (
    MOTOR_PCT_PADRAO,
    RUMBLE_CUSTOM_MULT_MAX,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger


def _config_que_viaja(cfg: object) -> dict[str, Any]:
    """`asdict(cfg)` sem os campos que não atravessam JSON.

    O `asdict` do `DaemonConfig` arrasta o `orcamento_da_mesa` (uma `lambda` injetada); sem esta
    função o `json.dumps` explode e o `daemon.reload` faz o trabalho SEM resposta (03/09/2026). Em
    vez de listar o campo a excluir, pergunta-se ao `json`: o que não serializa sai, com o nome do
    campo no lugar e a marca.
    """
    fora: dict[str, Any] = {}
    for chave, valor in asdict(cfg).items():  # type: ignore[call-overload]
        try:
            json.dumps(valor)
        except (TypeError, ValueError):
            fora[chave] = "<não viaja por IPC>"
            continue
        fora[chave] = valor
    return fora


def _caminho_publicado(daemon: object) -> str | None:
    """O MODO de pé, na forma que a tela lê (MODO-DE-CONEXAO-01).

    O escolhido (`config.gamepad_caminho`) ou, sem escolha, o de fábrica (`dualsense`,
    CAMINHO-CONTAGIO-01); ``None`` sem config legível. O-MODO-XBOX-NAO-E-QUEDA-02: modo, máscara e
    conexão são três eixos, e o modo não se deduz da máscara do P1 (a de todos sai em
    `por_aparelho`).
    """
    from hefesto_dualsense4unix.integrations.virtual_pad import (
        CAMINHO_DUALSENSE,
        normalizar_caminho,
    )

    cfg = getattr(daemon, "config", None)
    if cfg is None:
        return None
    return normalizar_caminho(getattr(cfg, "gamepad_caminho", None)) or CAMINHO_DUALSENSE


def _mascaras_por_aparelho(handlers: object) -> dict[str, str]:
    """`{uniq: máscara efetiva}` para cada controle conectado agora (MASCARA-NA-TELA-01).

    Desde a D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES é o modo único, igual para todos;
    quem decide é `external_mask.mascara_efetiva`, e repetir a regra faria duas verdades. NUNCA
    levanta: o que não abre não derruba o ``, a tela mostra a máscara da sessão.
    """
    fora: dict[str, str] = {}
    try:
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            mascara_efetiva,
        )

        daemon_cfg = getattr(getattr(handlers, "daemon", None), "config", None)
        da_sessao = str(getattr(daemon_cfg, "gamepad_flavor", "dualsense"))
        describe = getattr(getattr(handlers, "controller", None),
                           "describe_controllers", None)
        if not callable(describe):
            return fora
        for entrada in describe() or ():
            if not isinstance(entrada, dict) or not entrada.get("connected"):
                continue
            uniq = str(entrada.get("uniq") or "")
            if not uniq:
                continue
            fora[uniq] = str(mascara_efetiva(uniq, da_sessao))
    except Exception:  # pragma: no cover
        return fora
    return fora


if TYPE_CHECKING:
    from hefesto_dualsense4unix.core.controller import IController
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol, GravaOModo
    from hefesto_dualsense4unix.daemon.state_store import StateStore


def _porta_que_grava(origem: str) -> GravaOModo:
    """A porta que o setter do modo recebe: ``"ipc"`` para o pedido à mão."""
    return "ipc" if origem == "manual" else False


def origem_do_pedido(params: dict[str, Any] | None) -> Literal["manual", "profile"]:
    """A origem declarada pelo cliente. Silêncio = automático, nunca "manual"."""
    bruto = (params or {}).get("origin")
    if bruto is None:
        return "profile"
    if bruto not in ("manual", "profile"):
        raise ValueError("'origin' precisa ser 'manual' ou 'profile'")
    return cast('Literal["manual", "profile"]', bruto)


logger = get_logger(__name__)


def _as_str_or_none(value: Any) -> str | None:
    """Normaliza campos informativos do state_full para str | None; só string real passa (um
    MagicMock estoura o `json.dumps`)."""
    return value if isinstance(value, str) else None


_LIGHTBAR_READ_TTL_SEC = 1.0

_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC = 5.0

COOP_SEMPRE_LIGADO_MOTIVO = (
    "o co-op local é sempre ligado: cada controle conectado é um jogador. "
    "Para um controle de reserva, deixe-o desconectado."
)


def _pontes_confirmadas_seguro() -> dict[str, Any]:
    """As pontes confirmadas, e NUNCA uma exceção: perfil malformado devolve vazio e não apaga a aba
    a cada tique do `state_full`."""
    try:
        from hefesto_dualsense4unix.profiles import manager as _pm

        fn = getattr(_pm, "pontes_confirmadas", None)
        if fn is None:
            return {}
        return dict(fn() or {})
    except Exception:
        return {}


class _RenumberAuthorityChangedError(Exception):
    """F3: um jogo abriu enquanto o renumber esperava os locks — abortar."""


class _NumeroAlvoAusenteError(Exception):
    """PLAYER-01: pediram um número para um controle que não está na mesa."""


class _NumeroForaDaMesaError(Exception):
    """PLAYER-01: pediram um número maior do que a quantidade de presentes.

    Carrega o teto real; vira ``{"ok": False, "reason": "numero_fora_da_mesa", "max": N}``.
    """

    def __init__(self, maximo: int) -> None:
        super().__init__(f"numero fora da mesa (max={maximo})")
        self.maximo = maximo


_WRAPPER_MARKER_TTL_SEC = 2.0

_PONTES_CONFIRMADAS_TTL_SEC = 5.0


_HID_DEVICES_DIR = "/sys/bus/hid/devices"

_HID_ORFAO_BUS = "0005"

_HID_ORFAO_VID = "054C"

_HID_ORFAOS_TTL_SEC = 2.0

_NO_DO_VPAD_TTL_SEC = 2.0


def _e_dualsense_por_bluetooth(id_do_device: str) -> bool:
    """O nome do diretório é ``BUS:VID:PID.INSTANCIA`` — ex. ``0005:054C:0CE6.000F``."""
    partes = id_do_device.split(":")
    if len(partes) < 3:
        return False
    return partes[0] == _HID_ORFAO_BUS and partes[1].upper() == _HID_ORFAO_VID


def dualsense_sem_driver(devices_dir: str | None = None) -> list[str]:
    """Os DualSense presentes e SEM driver: a lista de ids do sysfs (critério do
    `bt_rebind_orphans.sh`).

    Órfão é o que NÃO tem o symlink `driver` (sem hidraw, input, LED nem bateria).
    ``devices_dir=None`` resolve `_HID_DEVICES_DIR` na hora da chamada, para a suíte trocá-lo. Vazio
    se o diretório não existe: roda no `state_full`.
    """
    alvo = devices_dir if devices_dir is not None else _HID_DEVICES_DIR
    try:
        entradas = sorted(os.listdir(alvo))
    except OSError:
        return []
    achados: list[str] = []
    for id_do_device in entradas:
        if os.path.exists(os.path.join(alvo, id_do_device, "driver")):
            continue
        if _e_dualsense_por_bluetooth(id_do_device):
            achados.append(id_do_device)
    return achados


def _visto_ha_s(vp: Any) -> dict[str, float]:
    """O ``visto_ha_s`` do vpad, saneado para o payload de IPC (PAINEL-DA-VERDADE-01/E1).

    O vpad pode ser `uinput` ou dublê: `getattr` com default, valor forçado a `float`, não numérico
    cai fora.
    """
    cru = getattr(vp, "visto_ha_s", None)
    if not isinstance(cru, dict):
        return {}
    return {
        str(k): float(v)
        for k, v in cru.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def _audio_do_jogo_amostra(vp: Any) -> dict[str, int] | None:
    """A amostra de áudio do vpad, saneada para o payload (PARIDADE-SONY-01): quais dos bytes
    `common[4..7]` o jogo escreveu.

    Mesmas defesas do `_visto_ha_s`; valor exótico cai fora antes do JSON.
    """
    cru = getattr(vp, "audio_do_jogo_amostra", None)
    if not isinstance(cru, dict):
        return None
    return {
        str(k): int(v)
        for k, v in cru.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def _par_de_motores(cru: Any) -> list[int] | None:
    """Um par (weak, strong) do vpad saneado para o payload, ou None (RUMBLE-QUE-NAO-SE-SENTE-01);
    sai como `list` (JSON não tem tupla)."""
    if not isinstance(cru, tuple) or len(cru) != 2:
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in cru):
        return None
    return [int(cru[0]), int(cru[1])]


def _contador_do_vpad(vp: Any, nome: str) -> int:
    """Um contador cumulativo do vpad, com tipagem ESTRITA; 0 quando não há (ORFAOS-QUE-VOLTAM-01).

    Não é `int(getattr(...) or 0)`: `motion_forwards` decide a frase do card e `int()` de um
    `MagicMock` dá 1 ("o giroscópio parou" num caminho que nunca existiu). Um MagicMock nunca vira
    dado.
    """
    valor = getattr(vp, nome, 0)
    if isinstance(valor, bool) or not isinstance(valor, int):
        return 0
    return valor


def _idade_ou_none(cru: Any) -> float | None:
    """Uma idade em segundos saneada para o payload, ou None."""
    if isinstance(cru, bool) or not isinstance(cru, (int, float)):
        return None
    return float(cru)


def _jack_do_vpad(vp: Any) -> dict[str, bool] | None:
    """O `jack` do vpad (fone/microfone/mudo) saneado para o payload, ou None
    (JACK-QUE-NAO-LIGOU-01); None = este vpad não fala de jack."""
    cru = getattr(vp, "jack", None)
    if not isinstance(cru, dict):
        return None
    return {
        str(k): bool(v) for k, v in cru.items() if isinstance(v, bool)
    }


def _bateria_do_vpad(vp: Any) -> dict[str, Any] | None:
    """A bateria que o vpad ANUNCIA ao jogo, saneada para o payload, ou None
    (BATERIA-QUE-NAO-CHEGOU-01).

    `pct` é `None` com `_STATUS_DESCONHECIDO`: "não sei" não vira zero (zero é bateria crítica e
    acenderia alerta).
    """
    cru = getattr(vp, "bateria_anunciada", None)
    if not isinstance(cru, tuple) or len(cru) != 2:
        return None
    pct, carregando = cru
    if pct is not None and (isinstance(pct, bool) or not isinstance(pct, int)):
        return None
    if not isinstance(carregando, bool):
        return None
    return {"pct": pct, "carregando": carregando}


def _amostra_de_descarte(cru: Any) -> dict[str, int] | None:
    """(flag0, flag1, flag2, weak, strong) do último descarte, nomeado."""
    if not isinstance(cru, tuple) or len(cru) != 5:
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in cru):
        return None
    nomes = ("flag0", "flag1", "flag2", "weak", "strong")
    return dict(zip(nomes, (int(v) for v in cru), strict=True))


def _anel_de_vibracao(cru: Any) -> list[dict[str, Any]] | None:
    """Os últimos reports de vibração do vpad, nomeados (QUEM ESCREVEU-01)."""
    if not isinstance(cru, list):
        return None
    nomes = ("ha_s", "flag0", "flag1", "flag2", "weak", "strong", "ramo")
    itens: list[dict[str, Any]] = []
    for entrada in cru:
        if not isinstance(entrada, tuple) or len(entrada) != 7:
            return None
        *numeros, ramo = entrada
        if not isinstance(ramo, str):
            return None
        if not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in numeros
        ):
            return None
        itens.append(dict(zip(nomes, (*numeros, ramo), strict=True)))
    return itens


def _report_estranho(cru: Any) -> dict[str, int] | None:
    """(report_id, tamanho) do último output com envelope que não lemos."""
    if not isinstance(cru, tuple) or len(cru) != 2:
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in cru):
        return None
    return {"report_id": int(cru[0]), "tamanho": int(cru[1])}


def _norm_uniq(value: Any) -> str | None:
    """MAC 12-hex normalizado de uma key/serial do backend, ou None."""
    if not isinstance(value, str):
        return None
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    normalized = norm_mac(value)
    if normalized is None or len(normalized) != 12:
        return None
    return normalized


def _rgb_or_none(value: Any) -> tuple[int, int, int] | None:
    """Coerção defensiva de um RGB vindo de backend/fake para tupla de ints."""
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        return None
    try:
        return (int(value[0]), int(value[1]), int(value[2]))
    except (TypeError, ValueError):
        return None


def _numero_de_exibicao(entry: dict[str, Any]) -> int:
    """Número "Controle N" de UMA entrada de ``controllers`` (MESA-CHEIA-11/E1).

    Mesma regra de `app/actions/base.numero_do_controle` (slot de sessão; sem slot, posição
    1-based), que a interface não deixa vir para cá (`base.py` importa `gi`). O portão
    `test_mesa_cheia_11_a_janela_conta_quatro.py` compara as duas cópias.
    """
    slot = entry.get("player_slot")
    if isinstance(slot, int) and not isinstance(slot, bool):
        return slot
    indice = entry.get("index")
    if isinstance(indice, int) and not isinstance(indice, bool):
        return indice + 1
    return 1


def controles_bt_frageis(controllers: Any, *, native_mode: bool) -> list[int]:
    """Números dos controles frágeis por BT no Modo Nativo, CRESCENTES — função pura
    (MESA-CHEIA-11/E1).

    Frágil é cada controle CONECTADO em ``transport == "bt"`` com o Modo Nativo ligado. Olhar só o
    primário calava o aviso justamente para os três do rádio com o Controle 1 no cabo. Devolve `[]`,
    sem levantar, para `controllers` ausente ou dublado.
    """
    if not native_mode or not isinstance(controllers, list):
        return []
    numeros: list[int] = []
    for entry in controllers:
        if not isinstance(entry, dict):
            continue
        if not entry.get("connected"):
            continue
        transporte = entry.get("transport")
        if not isinstance(transporte, str) or transporte.lower() != "bt":
            continue
        numero = _numero_de_exibicao(entry)
        if numero not in numeros:
            numeros.append(numero)
    return sorted(numeros)


_HOLDERS_PGREP_TIMEOUT_SEC = _escritor_cru.PGREP_TIMEOUT_S
_HOLDERS_SCAN_BUDGET_SEC = _escritor_cru.ORCAMENTO_DA_VARREDURA_S
_HOLDERS_MAX_STEAM_PIDS = _escritor_cru.MAX_PIDS_DA_STEAM


def _steam_pids() -> list[int]:
    """PIDs do processo Steam via pgrep — padrões do `steam_running` canônico."""
    from hefesto_dualsense4unix.core.escritor_cru import pids_da_steam

    return pids_da_steam()


def _steam_hidraw_holders() -> dict[str, list[int]]:
    """Mapa `/dev/hidrawN` -> PIDs do Steam que seguram o nó (8BIT-01).

    Sonda OPCIONAL e degradável, restrita aos PIDs do Steam (readlink em /proc/<pid>/fd, sem sudo).
    Estourou o orçamento ou a permissão: devolve o que tem, e quem consome trata como "não sondado",
    nunca "ninguém segura". O corpo mora em `core/escritor_cru.holders_de_hidraw` (ESCRITOR-CRU-01);
    aqui sem filtro de nós.
    """
    from hefesto_dualsense4unix.core.escritor_cru import holders_de_hidraw

    return holders_de_hidraw()


def _external_inventory(
    dualsense_count: int = 0,
    slot_resolver: Callable[[str | None], int | None] | None = None,
) -> list[dict[str, Any]]:
    """Inventário de externos + sonda de holders — roda FORA do event loop (`asyncio.to_thread` do
    `_handle_controller_list`; a enumeração evdev custa 10-40 ms, PERF-MULTI-CONTROLLER-01).

    `holders` só aparece quando a sonda RODOU e achou o Steam no hidraw (8BIT-01). CLONE-01:
    `identity` (:data:`EXTERNAL_IDENTITY_FIELD`) é SEMPRE carimbado, a identidade de APARELHO que
    distingue dois clones no cabo com o mesmo `uniq` sintético. EXT-04: leitura PURA, nunca escreve
    LED (a escrita a cada poll de 4 s bombardeava o clone 8BitDo até o hid-nintendo desregistrá-lo);
    quem acende é o tick lento do daemon (`ExternalLedSync`). NUMA-05/R-24: `player_slot` vem só do
    `slot_resolver` (`None` = nenhuma opinião ainda; null honesto > número errado).
    `dualsense_count` fica só pela assinatura.
    """
    from hefesto_dualsense4unix.core.evdev_reader import discover_external_gamepads
    from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
        EXTERNAL_IDENTITY_FIELD,
        identity_for_entry,
    )

    inventory = discover_external_gamepads()
    holders: dict[str, list[int]] = {}
    with contextlib.suppress(Exception):
        holders = _steam_hidraw_holders()
    for entry in inventory:
        hidraw = entry.get("hidraw")
        if holders and isinstance(hidraw, str) and hidraw in holders:
            entry["holders"] = {"steam_pids": holders[hidraw]}
        identity = identity_for_entry(entry)
        entry[EXTERNAL_IDENTITY_FIELD] = identity
        slot: int | None = None
        if slot_resolver is not None:
            with contextlib.suppress(Exception):
                raw = slot_resolver(identity)
                if isinstance(raw, int) and not isinstance(raw, bool):
                    slot = raw
        entry["player_slot"] = slot
    return inventory


def _alcance_do_toque(daemon: Any) -> str:
    """`vpad` quando o Hefesto está no caminho do toque; `hidraw` quando o jogo o lê direto.

    No Modo Nativo e com o Steam Input do jogo ligado o jogo lê o hidraw do controle físico,
    e o Hefesto só alcança o nó do sistema (o cursor), não o que o jogo recebe.
    """
    nativo = bool(daemon is not None and getattr(daemon, "is_native_mode", bool)())
    steam_input = bool(getattr(daemon, "_steam_input_excecao", False))
    return "hidraw" if nativo or steam_input else "vpad"


class IpcHandlersMixin:
    """Mixin com os 19 métodos `_handle_*` do IpcServer; não instanciável isolado (espera
    `controller`, `store`, `profile_manager`, `daemon`)."""

    controller: IController
    store: StateStore
    profile_manager: Any
    daemon: DaemonProtocol

    _lightbar_read_cache: (
        dict[str, tuple[float, tuple[int, int, int] | None, bool]] | None
    ) = None

    _wrapper_marker_cache: tuple[float, tuple[int, int] | None] | None = None
    _wrapper_first_seen: tuple[int, float] | None = None

    _pontes_confirmadas_cache: tuple[float, dict[str, Any]] | None = None

    _hid_orfaos_cache: tuple[float, list[str]] | None = None

    _no_do_vpad_cache: (
        dict[tuple[str, str], tuple[float, tuple[int, ...] | None, dict[str, Any]]] | None
    ) = None

    _launch_arm_task: Any = None

    _identidade_de_fabrica_cache: dict[str, dict[str, str | None]] | None = None
    _agenda_da_identidade: Any = None

    _sensor_hub: Any = None


    async def _handle_profile_switch(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica perfil escolhido pelo usuário (entrada manual via IPC)."""
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("profile.switch exige 'name' string")
        relatorio: dict[str, str] = {}
        import time as _time

        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )
        lock_antes = getattr(self.store, "_manual_profile_lock_until", 0.0)
        self.store.mark_manual_profile_lock(
            _time.monotonic() + MANUAL_PROFILE_LOCK_SEC
        )
        try:
            profile = self.profile_manager.activate(
                name, origin="manual", relatorio=relatorio
            )
        except Exception:
            self.store.mark_manual_profile_lock(lock_antes)
            raise
        if self.daemon is not None:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    materialize_launch_env,
                )

                materialize_launch_env(self.daemon)
        estado_modo = relatorio.get("mode", "aplicado")
        resposta: dict[str, Any] = {
            "active_profile": profile.name,
            "mode_aplicado": estado_modo == "aplicado",
            "secoes": dict(relatorio),
        }
        if estado_modo != "aplicado":
            resposta["motivo"] = estado_modo
            if estado_modo.startswith("adiado"):
                deadline = getattr(
                    getattr(self.daemon, "_mode_pendente", None), "nao_antes_de", None
                )
                if isinstance(deadline, int | float):
                    import time as _t

                    resposta["expira_em_sec"] = round(
                        max(0.0, float(deadline) - _t.monotonic()), 1
                    )
        return resposta

    async def _handle_profile_list(self, params: dict[str, Any]) -> dict[str, Any]:
        from hefesto_dualsense4unix.profiles.manager import os_perfis_de_escolher

        profiles = os_perfis_de_escolher(self.profile_manager.list_profiles())
        return {
            "profiles": [
                {
                    "name": p.name,
                    "priority": p.priority,
                    "match_type": getattr(p.match, "type", "criteria"),
                }
                for p in profiles
            ]
        }

    async def _handle_profile_reaplicar(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """O «Aplicar»: o perfil inteiro de novo aos controles, sem virar escolha
        (O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01).

        A cadeia do `profile.switch` sem a escolha (sessão, marcador, último jogo, Freestyle).
        Só o gesto prende: `prender: true` arma a trava da mão (D-1410-O-APLICAR-SEGURA).
        """
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("profile.reaplicar exige 'name' string")
        relatorio: dict[str, str] = {}
        prender = params.get("prender") is True
        profile = self.profile_manager.reaplicar(name, relatorio=relatorio, prender=prender)
        if self.daemon is not None:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    materialize_launch_env,
                )

                materialize_launch_env(self.daemon)
        estado_modo = relatorio.get("mode", "aplicado")
        resposta: dict[str, Any] = {
            "active_profile": profile.name,
            "mode_aplicado": estado_modo == "aplicado",
            "secoes": dict(relatorio),
        }
        if estado_modo != "aplicado":
            resposta["motivo"] = estado_modo
        return resposta


    def _apply_por_uniq(
        self,
        params: dict[str, Any],
        *,
        brilho_da_cor: float | None = None,
        **campos: Any,
    ) -> str | None:
        """Aplica ``campos`` SÓ no controle do MAC ``params["uniq"]``, se houver (PERFIL-05).

        Devolve **o que o backend fez** (uma palavra de ``core.controller.ResultadoDeSaida``,
        MESA-CHEIA-09). ``None`` = esta rota NÃO se aplica (sem ``uniq`` ou backend sem
        ``apply_output_for``) e o chamador segue o caminho clássico. Backend que devolve ``None``
        vira ``"escreveu"`` (a resposta histórica). `brilho_da_cor` viaja com a cor do `led.set` e
        vira o `brilho_da_barra` do `state_full` (A-04-PERGUNTA-AO-DAEMON-VIVO-01); backend sem o
        parâmetro recebe a cor igual.
        """
        alvo = params.get("uniq")
        if not isinstance(alvo, str) or not alvo:
            return None
        apply_for = getattr(self.controller, "apply_output_for", None)
        if not callable(apply_for):
            return None
        from hefesto_dualsense4unix.core.controller import OutputSpec

        spec = OutputSpec(**campos)
        if brilho_da_cor is None:
            resultado = apply_for(alvo, spec)
        else:
            try:
                resultado = apply_for(alvo, spec, brilho_da_cor=brilho_da_cor)
            except TypeError:
                resultado = apply_for(alvo, spec)
        return resultado if isinstance(resultado, str) and resultado else "escreveu"

    @staticmethod
    def _destinos_por_uniq(resultado: str | None, uniq: str) -> tuple[list[str], list[str]]:
        """``(aplicado_em, guardado_em)`` a partir do que o backend fez (MESA-CHEIA-09 E1/E2).

        ``aplicado_em`` = o byte SAIU. ``guardado_em`` existe porque "não escreveu" tem duas causas
        opostas na tela: o override guardado que pega no hotplug (D-9) e o pedido que não guardou
        nada (sem MAC estável). ``"registrado"`` cobre também o Modo Nativo; ``"falhou"`` entra nas
        duas listas VAZIAS (prometer "guardado" mandaria esperar um evento que pode não vir). O
        default NÃO é otimista (1.4): só ``"escreveu"`` afirma, e palavra desconhecida não afirma
        nem promete, e vai ao log.
        """
        if resultado == "escreveu":
            return [uniq], []
        if resultado == "registrado":
            return [], [uniq]
        if resultado in (None, "sem_alvo", "nada_a_fazer", "falhou"):
            return [], []
        logger.warning(
            "destino_por_uniq_palavra_desconhecida", resultado=resultado, uniq=uniq
        )
        return [], []

    def _uniqs_conectados(self) -> list[str]:
        """MACs dos controles CONECTADOS, na ordem do backend (``describe_controllers``, sem HID
        I/O).

        Vazia se o backend não sabe dizer quem está na mesa ou não há ninguém: o chamador segue pelo
        caminho clássico.
        """
        describe = getattr(self.controller, "describe_controllers", None)
        if not callable(describe):
            return []
        try:
            entradas = describe()
        except Exception as exc:
            logger.debug("uniqs_conectados_falhou", err=str(exc))
            return []
        if not isinstance(entradas, list):
            return []
        alvos: list[str] = []
        for entrada in entradas:
            if not isinstance(entrada, dict) or not entrada.get("connected"):
                continue
            uniq = entrada.get("uniq")
            if isinstance(uniq, str) and uniq and uniq not in alvos:
                alvos.append(uniq)
        return alvos

    def _registrar_em_todos(
        self, *, brilho_da_cor: float | None = None, **campos: Any
    ) -> list[str]:
        """Registra ``campos`` na camada da USUÁRIA de CADA controle conectado."""
        apply_for = getattr(self.controller, "apply_output_for", None)
        if not callable(apply_for):
            return []
        alvo_uniq_fn = getattr(self.controller, "get_output_target_uniq", None)
        alvo_presente = alvo_uniq_fn() if callable(alvo_uniq_fn) else None
        if isinstance(alvo_presente, str) and alvo_presente:
            return [alvo_presente]
        alvo_ausente_fn = getattr(self.controller, "alvo_de_output_ausente", None)
        alvo_ausente = alvo_ausente_fn() if callable(alvo_ausente_fn) else None
        if isinstance(alvo_ausente, str) and alvo_ausente:
            return []
        alvos = self._uniqs_conectados()
        if not alvos:
            return []
        from hefesto_dualsense4unix.core.controller import OutputSpec
        from hefesto_dualsense4unix.core.led_control import DO_BROADCAST

        spec = OutputSpec(**campos)
        aplicados: list[str] = []
        for alvo in alvos:
            try:
                if brilho_da_cor is None:
                    apply_for(alvo, spec, procedencia_da_cor=DO_BROADCAST)
                else:
                    apply_for(
                        alvo, spec, procedencia_da_cor=DO_BROADCAST,
                        brilho_da_cor=brilho_da_cor,
                    )
            except TypeError:
                apply_for(alvo, spec)
            except Exception as exc:
                logger.warning(
                    "registrar_em_todos_falhou", uniq=alvo, err=str(exc)
                )
                continue
            aplicados.append(alvo)
        return aplicados

    def _destinos_do_broadcast(self) -> tuple[list[str], list[str]]:
        """``(aplicado_em, guardado_em)`` da rota CLÁSSICA — o pedido SEM ``uniq`` (conserto 1.4).

        O ``trigger.set``/``trigger.reset`` sem ``uniq`` dizia as duas listas vazias mesmo
        escrevendo, enquanto o ``led.set`` irmão respondia a mesa inteira; aqui diz em QUEM pegou,
        com o mesmo teto de verdade do ramo por-``uniq``. O que NÃO faz (medido):

        * **Não** registra por controle: ``_record_desired_locked(None, ...)`` NIVELA (limpa o campo
        nos overrides e solta o dono), e re-registrar desfaria o nivelamento que "Todos" promete
        (14/08).
        * ``guardado_em`` só vem no alvo AUSENTE; para "Todos" o valor foi ao default, sem endereço.
        * **Não** afirma em **Modo Nativo** (``report_thread`` mudo, nenhum byte sai; CONSERTO 1.3).
        * **Não** afirma quando não sabe (mesa vazia, backend sem seletor, alvo sem MAC estável): as
          duas listas vazias.

        BROADCAST-PROIBIDO-01: antes de ler ``get_output_target_index`` (que MASCARA "Todos" e "alvo
        sumiu" no mesmo ``None``) pergunta ``alvo_de_output_ausente``; alvo FORA da mesa devolve
        ``([], [alvo])``. "Aplicado" = o desejado está armado e o fio não está mudo
        (``_apply_trigger`` só arma o handle; quem escreve é o ``report_thread``).
        """
        alvos = self._uniqs_conectados()
        if not alvos:
            return [], []
        if self.daemon is not None and self.daemon.is_native_mode():
            return [], []
        alvo_ausente_fn = getattr(self.controller, "alvo_de_output_ausente", None)
        alvo_ausente = alvo_ausente_fn() if callable(alvo_ausente_fn) else None
        if isinstance(alvo_ausente, str) and alvo_ausente:
            return [], [alvo_ausente]
        onde_mira = getattr(self.controller, "get_output_target_index", None)
        if not callable(onde_mira):
            return [], []
        try:
            indice = onde_mira()
        except Exception as exc:
            logger.debug("destinos_do_broadcast_falhou", err=str(exc))
            return [], []
        if indice is None:
            return alvos, []
        nomear = getattr(self.controller, "get_output_target_uniq", None)
        alvo = nomear() if callable(nomear) else None
        if not isinstance(alvo, str) or not alvo:
            return [], []
        return [alvo], []

    async def _handle_trigger_set(self, params: dict[str, Any]) -> dict[str, Any]:
        side = params.get("side")
        mode = params.get("mode")
        trigger_params = params.get("params", [])
        if side not in ("left", "right"):
            raise ValueError("trigger.set: side precisa ser 'left' ou 'right'")
        if not isinstance(mode, str):
            raise ValueError("trigger.set: mode precisa ser string")
        if not isinstance(trigger_params, list):
            raise ValueError("trigger.set: params precisa ser lista")
        effect = build_from_name(mode, trigger_params)
        if params.get("todos") is True:
            aplicado_em, guardado_em = self._gatilho_em_todos({side: effect})
            return {
                "status": "ok",
                "aplicado_em": aplicado_em,
                "guardado_em": guardado_em,
            }
        campos: dict[str, Any] = (
            {"trigger_left": effect} if side == "left" else {"trigger_right": effect}
        )
        resultado = self._apply_por_uniq(params, **campos)
        if resultado is None:
            self.controller.set_trigger(side, effect)
            aplicado_em, guardado_em = self._destinos_do_broadcast()
        else:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        return {
            "status": "ok",
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    async def _handle_trigger_reset(self, params: dict[str, Any]) -> dict[str, Any]:
        """Grava ``Off`` no gatilho: sem efeito do Hefesto, e o jogo decide (R-19).

        Mesma rota do ``trigger.set``, carimbado com a camada ``usuaria`` (por MAC): solta o que o
        jogo pintou naquele gatilho. ABAS-06: ``uniq`` presente = reset por-MAC
        (``apply_output_for``), não broadcast nos quatro.
        """
        target = params.get("side", "both")
        if target not in ("left", "right", "both"):
            raise ValueError("trigger.reset: side deve ser left|right|both")
        campos: dict[str, Any] = {}
        if target in ("left", "both"):
            campos["trigger_left"] = trigger_off()
        if target in ("right", "both"):
            campos["trigger_right"] = trigger_off()
        if params.get("todos") is True:
            aplicado_em, guardado_em = self._gatilho_em_todos(
                {campo.removeprefix("trigger_"): efeito for campo, efeito in campos.items()}
            )
            return {
                "status": "ok",
                "aplicado_em": aplicado_em,
                "guardado_em": guardado_em,
            }
        resultado = self._apply_por_uniq(params, **campos)
        if resultado is None:
            for lado in ("left", "right"):
                if f"trigger_{lado}" in campos:
                    self.controller.set_trigger(lado, campos[f"trigger_{lado}"])
            aplicado_em, guardado_em = self._destinos_do_broadcast()
        else:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        return {
            "status": "ok",
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    def _gatilho_em_todos(self, efeitos: dict[str, Any]) -> tuple[list[str], list[str]]:
        """``(aplicado_em, guardado_em)`` do «Em todos» da aba Gatilhos (``todos: true``;
        O-EM-TODOS-DO-GATILHO-CHEGA-A-CADA-CONTROLE-DA-MESA-01).

        Quem escreve é `set_trigger_em_todos` do backend, e as listas são a palavra dele por
        controle, lida pelo `_destinos_por_uniq`. Backend sem ele (dublê antigo): a rota clássica.
        """
        dono = getattr(self.controller, "set_trigger_em_todos", None)
        if not callable(dono):
            for lado, efeito in efeitos.items():
                self.controller.set_trigger("left" if lado == "left" else "right", efeito)
            return self._destinos_do_broadcast()
        palavras: dict[str, str] = {}
        for lado, efeito in efeitos.items():
            for uniq, palavra in dict(dono(lado, efeito)).items():
                if palavras.get(uniq) != "escreveu":
                    palavras[uniq] = palavra
        aplicado_em: list[str] = []
        guardado_em: list[str] = []
        for uniq, palavra in palavras.items():
            aplicado, guardado = self._destinos_por_uniq(palavra, uniq)
            aplicado_em.extend(aplicado)
            guardado_em.extend(guardado)
        return aplicado_em, guardado_em


    async def _handle_led_set(self, params: dict[str, Any]) -> dict[str, Any]:
        rgb = params.get("rgb")
        if not isinstance(rgb, list) or len(rgb) != 3:
            raise ValueError("led.set: rgb precisa ser lista com 3 inteiros")
        for idx, v in enumerate(rgb):
            if not isinstance(v, int) or not (0 <= v <= 255):
                raise ValueError(f"led.set: rgb[{idx}] fora de byte")
        brightness_raw = params.get("brightness", 1.0)
        try:
            brightness = float(brightness_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("led.set: brightness precisa ser numerico") from exc
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(
                f"led.set: brightness fora de [0.0, 1.0]: {brightness}"
            )
        from hefesto_dualsense4unix.core.led_control import LedSettings

        r, g, b = LedSettings(
            lightbar=(int(rgb[0]), int(rgb[1]), int(rgb[2]))
        ).apply_brightness(brightness).lightbar
        resultado = self._apply_por_uniq(params, brilho_da_cor=brightness, led=(r, g, b))
        guardado_em: list[str] = []
        if resultado is not None:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        else:
            self.controller.set_led((r, g, b))
            aplicado_em = self._registrar_em_todos(brilho_da_cor=brightness, led=(r, g, b))
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        return {
            "status": "ok",
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    async def _handle_led_player_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica bitmask de 5 LEDs de player no controle."""
        bits_raw = params.get("bits")
        if not isinstance(bits_raw, list) or len(bits_raw) != 5:
            raise ValueError("led.player_set: 'bits' precisa ser lista com exatamente 5 booleanos")
        for idx, v in enumerate(bits_raw):
            if not isinstance(v, bool):
                raise ValueError(f"led.player_set: bits[{idx}] precisa ser booleano")
        bits: tuple[bool, bool, bool, bool, bool] = (
            bits_raw[0], bits_raw[1], bits_raw[2], bits_raw[3], bits_raw[4]
        )
        resultado = self._apply_por_uniq(params, player_leds=bits)
        guardado_em: list[str] = []
        if resultado is not None:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        else:
            self.controller.set_player_leds(bits)
            aplicado_em = self._registrar_em_todos(player_leds=bits)
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        return {
            "status": "ok",
            "bits": list(bits),
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    async def _handle_led_player_brightness_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """O brilho das cinco luzes de número: Fraco, Médio ou Forte.

        Decisão de 24/09/2026: `D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`.

        Params:
            brilho: ``"fraco"``, ``"medio"`` ou ``"forte"`` (noqa-acento): a PALAVRA do perfil.
                A tradução é de ``core/led_control.degrau_do_brilho_das_luzes``, que recusa palavra
                desconhecida. uniq: o MAC do controle. Presente = SÓ nele (camada da usuária);
                ausente = «Todos»: o padrão de quem chegar depois E cada conectado, salvo se o
                seletor do backend mira UM controle (vale só nele) ou um fora da mesa (fica
                guardado).

        Sai pelos caminhos do número, nos dois transportes
        (``PyDualSenseController._levar_o_brilho_das_luzes``).
        """
        from hefesto_dualsense4unix.core.led_control import (
            BRILHOS_DAS_LUZES,
            degrau_do_brilho_das_luzes,
        )

        brilho = params.get("brilho")
        if not isinstance(brilho, str):
            palavras = ", ".join(BRILHOS_DAS_LUZES)
            raise ValueError(
                f"led.player_brightness_set: 'brilho' precisa ser um de: {palavras}"
            )
        degrau = degrau_do_brilho_das_luzes(brilho)
        pedido = params
        if not params.get("uniq"):
            alvo_fn = getattr(self.controller, "get_output_target_uniq", None)
            ausente_fn = getattr(self.controller, "alvo_de_output_ausente", None)
            escolhido = alvo_fn() if callable(alvo_fn) else None
            if not (isinstance(escolhido, str) and escolhido):
                escolhido = ausente_fn() if callable(ausente_fn) else None
            if isinstance(escolhido, str) and escolhido:
                pedido = {**params, "uniq": escolhido}
        resultado = self._apply_por_uniq(pedido, player_led_brightness=degrau)
        guardado_em: list[str] = []
        if resultado is not None:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(pedido["uniq"])
            )
        else:
            from hefesto_dualsense4unix.core.controller import OutputSpec

            spec = OutputSpec(player_led_brightness=degrau)
            padrao = getattr(self.controller, "apply_output_defaults", None)
            if callable(padrao):
                padrao(spec)
            aplicado_em = []
            apply_for = getattr(self.controller, "apply_output_for", None)
            if callable(apply_for):
                for alvo in self._uniqs_conectados():
                    try:
                        if apply_for(alvo, spec) == "escreveu":
                            aplicado_em.append(alvo)
                    except Exception as exc:
                        logger.warning(
                            "brilho_das_luzes_em_todos_falhou", uniq=alvo, err=str(exc)
                        )
        return {
            "status": "ok",
            "brilho": brilho,
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    async def _handle_led_auto_release(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Só registra no diário: a luz não tem trava a soltar.

        Fica no contrato do IPC para quem ainda o chama; nenhum byte. A cor do gesto é carimbada com
        a camada ``usuaria`` do controle e a ativação de um perfil aplica a luz em qualquer origem;
        `escopo` diz na resposta que nada aqui é por controle.
        """
        logger.info("led_auto_release", categoria="led")
        return {"status": "ok", "categoria": "led", "escopo": "o daemon inteiro"}


    async def _handle_identity_renumber(self, params: dict[str, Any]) -> dict[str, Any]:
        """Reordena a FILA de preferência (DualSense + externos) — ONDA-U/NUM-01.

        Recusa com uma sessão de jogo ABERTA (``display_authority == 'game'``): repintar o LED no
        meio da partida é o erro que o NUMA-03 já curou no tick. A fila é ÚNICA entre
        ``identity.py`` e ``external_identity.py`` (EXT-04), então a reordenação é GLOBAL: junta os
        dois ``snapshot()``, ordena pelo lugar ATUAL (a ordem relativa fica) e reescreve 1..N via
        ``compact()`` de cada registro, sob o ``CONTROLLERS_FILE_LOCK`` (NUMA-04). Sem controle
        registrado, ``renumbered`` vazio (no-op). NUM-01: o que se reescreve é o LUGAR NA FILA, não
        o número de cada controle; o ausente só perde a fila e o número volta a ser calculado quando
        ele voltar.

        Repintura: ``reassert_resolved_outputs`` para o DualSense já com o slot novo; os externos
        pelo próximo tick do ``ExternalLedSync``, com o agendamento adiantado por
        ``daemon._schedule_external_tick`` (getattr defensivo).

        Atomicidade plan→apply (TOCTOU, 2026-07-20): ``snapshot()`` → plano → ``compact()`` roda com
        os DOIS ``RLock`` de instância (``lock_for_renumber``) tomados, senão um
        ``slot_for(assign=True)`` concorrente reivindicava o slot-alvo (dois "Controle 1"). Deadlock
        evitado pela HIERARQUIA ``identity._lock`` → ``external_identity._lock`` →
        ``CONTROLLERS_FILE_LOCK``, não por exclusividade (o provider de reserva, EXT-04, e o de
        presença, NUM-01, já tomam os dois); o lado externo não consulta o DualSense segurando o
        próprio lock. Fakes sem o método seguem sem a trava.

        Isolamento (U x HANG-01, 2026-07-20): aquisição + plano + ``compact()`` rodam por
        ``asyncio.to_thread`` sob ``asyncio.wait_for`` no executor PADRÃO, nunca direto neste
        `async` (o único loop do daemon). O lock de ``external_registry`` também é tomado pelo
        ``ExternalLedSync.tick()`` no pool ``hefesto-ext`` (HANG-01); um ``acquire()`` sem teto
        penduraria o loop. O timeout devolve erro ao IPC.
        """
        authority = (
            getattr(self.daemon, "display_authority", "unknown")
            if self.daemon is not None
            else "unknown"
        )
        if authority == "game":
            return {"ok": False, "reason": "sessao_de_jogo_aberta"}

        identity_registry = (
            getattr(self.daemon, "identity_registry", None)
            if self.daemon is not None
            else None
        )
        external_registry = (
            getattr(self.daemon, "external_registry", None)
            if self.daemon is not None
            else None
        )

        daemon = self.daemon

        def _authority_now() -> str:
            return (
                getattr(daemon, "display_authority", "unknown")
                if daemon is not None
                else "unknown"
            )

        try:
            renumbered = await asyncio.wait_for(
                asyncio.to_thread(
                    self._renumber_locked,
                    identity_registry,
                    external_registry,
                    authority_check=_authority_now,
                ),
                timeout=_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "identity_renumber_lock_timeout",
                timeout_sec=_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC,
            )
            return {"ok": False, "reason": "lock_timeout"}
        except _RenumberAuthorityChangedError:
            logger.info("identity_renumber_abortado_por_jogo")
            return {"ok": False, "reason": "sessao_de_jogo_aberta"}

        if not renumbered:
            return {"ok": True, "renumbered": {}}

        self._despachar_repintura("identity.renumber")

        return {"ok": True, "renumbered": renumbered}

    def _despachar_repintura(self, de_onde: str) -> None:
        """Manda repintar SEM segurar a resposta (RESPOSTA-QUE-CHEGA-TARDE-01)."""
        try:
            laco = asyncio.get_running_loop()
        except RuntimeError:
            self._repintar_apos_renumeracao()
            return

        def _no_fio() -> None:
            try:
                self._repintar_apos_renumeracao(laco_do_daemon=laco)
            except Exception as exc:
                logger.warning("repintura_apos_renumeracao_falhou",
                               de_onde=de_onde, err=str(exc))

        tarefa = laco.create_task(asyncio.to_thread(_no_fio))
        em_voo = getattr(self, "_repinturas_em_voo", None)
        if em_voo is None:
            em_voo = set()
            self._repinturas_em_voo = em_voo
        em_voo.add(tarefa)
        tarefa.add_done_callback(em_voo.discard)

    def _repintar_apos_renumeracao(
        self, laco_do_daemon: asyncio.AbstractEventLoop | None = None
    ) -> None:
        """As TRÊS repinturas de quem mexeu na fila de números, nesta ordem (compartilhada por
        `identity.renumber` e `identity.number.set`).

        ``laco_do_daemon`` é OBRIGATÓRIO quando o corpo roda fora da thread do laço (o normal desde
        RESPOSTA-QUE-CHEGA-TARDE-01, `_despachar_repintura` usa `asyncio.to_thread`); só o passo 3 o
        usa. ``None`` = estou na thread do laço, ou não há laço (dublês).

        1. **`coop.sync(force=True)` PRIMEIRO, e a ordem é o conserto.** Com `coop_enabled=True` a
        camada do co-op fica acima do override por-uniq e só é republicada num ciclo CHEIO de
        `sync()` (`subsystems/coop.py`); renumerar não dispara nenhuma das condições dele. Sem o
        `force`, o passo 2 reafirmava a camada VELHA e a lâmpada só acertava no próximo hotplug
        (medido com dois DualSense e o daemon vivo, em `/sys/class/leds`). Mora aqui e não na aba
        porque a janela GTK antiga tinha o mesmo defeito. 2. `reassert_resolved_outputs`: o
        DualSense reafirma o output com o número novo, sobre a camada fresca do passo 1. 3.
        `_schedule_external_tick`: os externos são repintados pelo tick lento, adiantado.

        Custo: o `sync(force=True)` paga uma `discover_dualsense_evdevs()` (~10-40 ms,
        PERF-MULTI-CONTROLLER-01) no event loop, e renumerar é gesto manual e raro. Os três passos
        são defensivos: nada aqui derruba a renumeração, que já aconteceu.
        """
        if self.daemon is not None:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.subsystems.coop import (
                    get_coop_manager,
                )

                get_coop_manager(self.daemon).sync(force=True)

        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        schedule_external_tick = (
            getattr(self.daemon, "_schedule_external_tick", None)
            if self.daemon is not None
            else None
        )
        if not callable(schedule_external_tick):
            return
        if laco_do_daemon is None:
            schedule_external_tick()
            return
        try:
            laco_do_daemon.call_soon_threadsafe(schedule_external_tick)
        except RuntimeError as exc:
            logger.warning("tique_externo_nao_agendado", err=str(exc))

    async def _handle_identity_number_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Atribui o NÚMERO EXIBIDO de UM controle (PLAYER-01, 25/07).

        Fica em ``identity.`` porque escreve o mesmo estado do ``identity.renumber`` (a fila dos
        dois registros, mesma hierarquia de locks); é ``number`` e não ``player`` porque "jogador" é
        o número do co-op (``app/actions/base.py``).

        Params:
            uniq: MAC normalizado do controle (o ``uniq`` do ``state_full``).
            number: número desejado, 1..N entre os PRESENTES.

        Retorno ``{"ok": True, "number": N, "changed": {key: lugar}}`` (``changed`` só traz quem
        MUDOU de lugar, R-15) ou ``{"ok": False, "reason": ...}``. NUM-01: escreve a fila, nunca um
        "número absoluto": atribuir o 2 é PERMUTAR lugares de presentes (``_set_number_locked``); os
        lugares dos ausentes ficam intocados. Mesmos gate de jogo aberto, teto de lock,
        ``asyncio.to_thread`` e re-checagem de autoridade dentro dos locks do ``identity.renumber``
        (NUMA-03, HANG-01).
        """
        uniq_raw = params.get("uniq")
        if not isinstance(uniq_raw, str) or not uniq_raw.strip():
            raise ValueError("identity.number.set: 'uniq' precisa ser string não vazia")
        numero = params.get("number")
        if not isinstance(numero, int) or isinstance(numero, bool) or numero < 1:
            raise ValueError(
                "identity.number.set: 'number' precisa ser inteiro >= 1"
            )
        alvo = _norm_uniq(uniq_raw) or uniq_raw.strip()

        authority = (
            getattr(self.daemon, "display_authority", "unknown")
            if self.daemon is not None
            else "unknown"
        )
        if authority == "game":
            return {"ok": False, "reason": "sessao_de_jogo_aberta"}

        identity_registry = (
            getattr(self.daemon, "identity_registry", None)
            if self.daemon is not None
            else None
        )
        external_registry = (
            getattr(self.daemon, "external_registry", None)
            if self.daemon is not None
            else None
        )
        daemon = self.daemon

        def _authority_now() -> str:
            return (
                getattr(daemon, "display_authority", "unknown")
                if daemon is not None
                else "unknown"
            )

        try:
            changed = await asyncio.wait_for(
                asyncio.to_thread(
                    self._set_number_locked,
                    identity_registry,
                    external_registry,
                    alvo,
                    numero,
                    authority_check=_authority_now,
                ),
                timeout=_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "identity_number_set_lock_timeout",
                timeout_sec=_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC,
            )
            return {"ok": False, "reason": "lock_timeout"}
        except _RenumberAuthorityChangedError:
            logger.info("identity_number_set_abortado_por_jogo")
            return {"ok": False, "reason": "sessao_de_jogo_aberta"}
        except _NumeroAlvoAusenteError:
            logger.info("identity_number_set_alvo_ausente", uniq=alvo)
            return {"ok": False, "reason": "controle_ausente"}
        except _NumeroForaDaMesaError as exc:
            logger.info(
                "identity_number_set_numero_fora_da_mesa",
                uniq=alvo,
                pedido=numero,
                maximo=exc.maximo,
            )
            return {
                "ok": False,
                "reason": "numero_fora_da_mesa",
                "max": exc.maximo,
            }

        if changed:
            self._despachar_repintura("identity.number.set")

        return {"ok": True, "number": numero, "changed": changed}

    @staticmethod
    def _set_number_locked(
        identity_registry: Any,
        external_registry: Any,
        alvo: str,
        numero: int,
        authority_check: Callable[[], str] | None = None,
    ) -> dict[str, int]:
        """Corpo BLOQUEANTE do ``identity.number.set`` — só via ``to_thread``.

        A regra: **trocar de lugar o alvo e quem tem o número pedido**, e mais ninguém
        (TROCA-DE-PLAYER-01, 29/08/2026: *"Trocar é TROCA, não fila"*; o ``pop``+``insert`` antigo
        era um rodízio). Permuta em vez de reescrever 1..N para o conjunto de lugares dos presentes
        ficar exato e o gesto não rebaixar quem está guardado. A fila é ÚNICA entre DualSense e
        externos (EXT-04/NUM-01):

        1. junta os PRESENTES dos dois registros como ``(lugar, key, registro)`` por lugar; **as
        duas recusas saem daqui, antes de qualquer escrita**; 1a. o registro dos DualSense ALINHA o
        gravado com a tela (``alinhar_gravado_com_a_tela``) e a mesa é relida se algo mudou; 2.
        TROCA as posições ``indice_atual`` e ``numero - 1``; 3. redistribui os MESMOS lugares, em
        ordem crescente, para a lista reordenada; 4. cada registro recebe só a sua fatia: DualSense
        por ``escolha_da_mao`` (senão o congelamento a apaga em 4,0 s), externos por ``compact``;
        ambos persistem sob o ``CONTROLLERS_FILE_LOCK``.

        Empate de lugar (só por corrupção) vai ao DualSense, como no ``load``,
        ``merged_order_payload`` e ``_posicao_locked``. Erros, ANTES de escrever:
        :class:`_NumeroAlvoAusenteError` e :class:`_NumeroForaDaMesaError`. ``authority_check`` é a
        re-checagem F3 pós-acquire do ``_renumber_locked``.
        """
        with contextlib.ExitStack() as locks:
            for reg in (identity_registry, external_registry):
                acquire = getattr(reg, "lock_for_renumber", None)
                if callable(acquire):
                    locks.enter_context(acquire())

            if callable(authority_check) and authority_check() == "game":
                raise _RenumberAuthorityChangedError()

            def _mesa_presente() -> list[tuple[int, int, str, Any]]:
                """Os ASSENTOS dos dois registros (ligados e guardados), por lugar."""
                mesa: list[tuple[int, int, str, Any]] = []
                for ordem_kind, registry in enumerate(
                    (identity_registry, external_registry)
                ):
                    if registry is None:
                        continue
                    conectados = _chaves_dos_assentos(registry)
                    mesa.extend(
                        (lugar, ordem_kind, key, registry)
                        for key, lugar in registry.snapshot().items()
                        if key in conectados
                    )
                mesa.sort(key=lambda e: (e[0], e[1], e[2]))
                return mesa

            presentes = _mesa_presente()

            if not any(e[2] == alvo and _ligado(e) for e in presentes):
                raise _NumeroAlvoAusenteError()
            if _fora_da_mesa(presentes, numero):
                raise _NumeroForaDaMesaError(sum(1 for e in presentes if _ligado(e)))

            alinhar = getattr(identity_registry, "alinhar_gravado_com_a_tela", None)
            if callable(alinhar) and alinhar():
                presentes = _mesa_presente()

            indice_atual = next(
                pos for pos, e in enumerate(presentes) if e[2] == alvo
            )

            lugares = [e[0] for e in presentes]
            nova_ordem = list(presentes)
            indice_alvo = numero - 1
            nova_ordem[indice_atual], nova_ordem[indice_alvo] = (
                nova_ordem[indice_alvo],
                nova_ordem[indice_atual],
            )

            mudou: dict[str, int] = {}
            por_registro: dict[int, dict[str, int]] = {}
            for pos, (lugar_atual, ordem_kind, key, registry) in enumerate(
                nova_ordem
            ):
                novo_lugar = lugares[pos]
                if novo_lugar != lugar_atual:
                    mudou[key] = novo_lugar
                por_registro.setdefault(ordem_kind, {})[key] = novo_lugar
                del registry

            if identity_registry is not None and por_registro.get(0):
                aplicar = getattr(identity_registry, "escolha_da_mao", None)
                if not callable(aplicar):
                    aplicar = identity_registry.compact
                aplicar(por_registro[0])
            if external_registry is not None and por_registro.get(1):
                external_registry.compact(por_registro[1])

            return mudou

    @staticmethod
    def _connected_keys(registry: Any) -> set[str]:
        """Keys CONECTADAS de um registro de identidade (R-15), com fallback."""
        if registry is None:
            return set()
        fn = getattr(registry, "snapshot_connected", None)
        if callable(fn):
            with contextlib.suppress(Exception):
                return {str(key) for key in fn()}
        with contextlib.suppress(Exception):
            return {str(key) for key in registry.snapshot()}
        return set()

    @staticmethod
    def _renumber_locked(
        identity_registry: Any,
        external_registry: Any,
        authority_check: Callable[[], str] | None = None,
    ) -> dict[str, int]:
        """Corpo BLOQUEANTE de `identity.renumber` — só via `asyncio.to_thread`."""
        with contextlib.ExitStack() as locks:
            for reg in (identity_registry, external_registry):
                acquire = getattr(reg, "lock_for_renumber", None)
                if callable(acquire):
                    locks.enter_context(acquire())

            if callable(authority_check) and authority_check() == "game":
                raise _RenumberAuthorityChangedError()

            entries: list[tuple[bool, int, str, Any]] = []
            for registry in (identity_registry, external_registry):
                if registry is None:
                    continue
                conectados = IpcHandlersMixin._connected_keys(registry)
                entries.extend(
                    (key not in conectados, slot, key, registry)
                    for key, slot in registry.snapshot().items()
                )
            if not entries:
                return {}

            entries.sort(key=lambda entry: (entry[0], entry[1]))
            renumbered: dict[str, int] = {}
            identity_map: dict[str, int] = {}
            external_map: dict[str, int] = {}
            for novo_lugar, (_offline, lugar_atual, key, registry) in enumerate(
                entries, start=1
            ):
                if lugar_atual != novo_lugar:
                    renumbered[key] = novo_lugar
                if registry is identity_registry:
                    identity_map[key] = novo_lugar
                else:
                    external_map[key] = novo_lugar

            if identity_registry is not None and identity_map:
                identity_registry.compact(identity_map)
            if external_registry is not None and external_map:
                external_registry.compact(external_map)

            return renumbered


    async def _handle_daemon_status(self, params: dict[str, Any]) -> dict[str, Any]:
        self._agendar_arming_do_launch()
        snap = self.store.snapshot()
        controller = snap.controller
        return {
            "connected": bool(controller and controller.connected),
            "transport": controller.transport if controller else None,
            "active_profile": snap.active_profile,
            "pontes_confirmadas": _pontes_confirmadas_seguro(),
            "battery_pct": controller.battery_pct if controller else None,
            "paused": bool(self.daemon is not None and self.daemon.is_paused()),
            "freestyle_ligado": bool(self.store.freestyle_ligado),
            "native_mode": bool(
                self.daemon is not None and self.daemon.is_native_mode()
            ),
            "emulation_suppressed": bool(
                self.daemon is not None
                and getattr(self.daemon, "_emulation_suppressed", False)
            ),
            "keyboard_emulation": self._keyboard_emulation_payload(),
            **self._window_detect_payload(),
        }

    def _keyboard_emulation_payload(self) -> dict[str, Any]:
        """Bloco `keyboard_emulation` publicado por `state_full` e `daemon.status`
        (EMULACAO-NO-JOGO-01).

        - `enabled`: o interruptor (`config.keyboard_emulation_enabled`, `keyboard_emulation.flag`);
        - `device_ativo`: o teclado virtual existe agora (`_keyboard_device`);
        - `despachando`: ele emitiria tecla NESTE instante (a conjunção completa do gate do poll
          loop);
        - `bloqueio`: por que não emitiria: `"desligada"`, `"sem_device"`, `"modo_jogo"` ou `null`
          quando emite;
        - `osk_disponivel` (TECLADO-QUE-NAO-DIGITA-01): há teclado na tela instalado na MÁQUINA;
          decide se o L3 abre algo e se há caminho para ESCREVER TEXTO com o controle.

        Sai do daemon e não de um `shutil.which` na janela: num Flatpak a janela olharia o sandbox.
        `getattr` defensivo (roda a 10-20 Hz).
        """
        daemon = self.daemon
        cfg = getattr(daemon, "config", None) if daemon is not None else None
        enabled = bool(getattr(cfg, "keyboard_emulation_enabled", False))
        device_ativo = bool(getattr(daemon, "_keyboard_device", None) is not None)
        bloqueio = self._bloqueio_da_emulacao_de_desktop(
            enabled=enabled, device_ativo=device_ativo
        )
        osk_disponivel = False
        with contextlib.suppress(Exception):
            controlador = getattr(daemon, "_osk_controller", None)
            if controlador is not None:
                osk_disponivel = bool(controlador.disponivel())
            else:
                from hefesto_dualsense4unix.daemon.subsystems.keyboard import (
                    osk_disponivel_no_sistema,
                )

                osk_disponivel = bool(osk_disponivel_no_sistema())
        return {
            "enabled": enabled,
            "device_ativo": device_ativo,
            "despachando": bloqueio is None,
            "bloqueio": bloqueio,
            "osk_disponivel": osk_disponivel,
        }

    def _bloqueio_da_emulacao_de_desktop(
        self, *, enabled: bool, device_ativo: bool
    ) -> str | None:
        """Por que a emulação de DESKTOP não emitiria agora, ou `None` se emite: UM DONO SÓ, para
        mouse e teclado.

        Os dois são calados pela mesma conjunção (`lifecycle._poll_loop`: `emu_active = not
        self._emulation_suppressed`); escrevê-la duas vezes faria as respostas divergirem. Entram
        por parâmetro só `enabled` (flag de cada um) e `device_ativo`. Ordem: o interruptor, o
        device, o jogo. Vocabulário (traduzido em
        `app/actions/mouse_actions.BLOQUEIO_DO_MOUSE_EM_PORTUGUES`): `"desligada"`, `"sem_device"`,
        `"modo_jogo"`.
        """
        daemon = self.daemon
        if not enabled:
            return "desligada"
        if not device_ativo:
            return "sem_device"
        if bool(getattr(daemon, "_emulation_suppressed", False)):
            return "modo_jogo"
        return None

    def _bloqueio_do_mouse(self) -> str | None:
        """Por que o cursor NÃO andaria agora, ou `None` se ele anda (MOUSE-SEM-RAZÃO-01, BG-02).

        A permissão de `uinput` entra por `device_ativo`: `UinputMouseDevice.start()` falha sem
        acesso ao nó e `_mouse_device` fica `None` com o interruptor em pé. Uma sonda de `os.access`
        na janela responderia pelo processo dela (no Flatpak, pelo sandbox). `getattr` defensivo
        (caminho do `state_full`, 10-20 Hz).
        """
        daemon = self.daemon
        cfg = getattr(daemon, "config", None) if daemon is not None else None
        return self._bloqueio_da_emulacao_de_desktop(
            enabled=bool(getattr(cfg, "mouse_emulation_enabled", False)),
            device_ativo=getattr(daemon, "_mouse_device", None) is not None,
        )

    def _mouse_emulation_payload(self) -> dict[str, Any]:
        """Bloco `mouse_emulation` do `state_full` — o estado E a razão.

        As três chaves de sempre são FEAT-CLI-PARITY-01 (o `mouse status` da CLI); `device_ativo`,
        `despachando` e `bloqueio` (BG-02) seguem o molde de `_keyboard_emulation_payload`. Sem
        `daemon_cfg` o bloco é OMITIDO: ausência = "estado indisponível".
        """
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        bloqueio = self._bloqueio_do_mouse()
        return {
            "enabled": bool(getattr(daemon_cfg, "mouse_emulation_enabled", False)),
            "speed": int(getattr(daemon_cfg, "mouse_speed", 6)),
            "scroll_speed": int(getattr(daemon_cfg, "mouse_scroll_speed", 1)),
            "device_ativo": getattr(self.daemon, "_mouse_device", None) is not None,
            "despachando": bloqueio is None,
            "bloqueio": bloqueio,
        }

    def _steam_input_payload(self) -> dict[str, bool]:
        """A exceção do Steam Input ativa agora (JOGO-01): o jogo da allowlist aberto."""
        daemon = self.daemon
        return {
            "excecao_ativa": bool(getattr(daemon, "_steam_input_excecao", False)),
        }

    def _jogo_steam_payload(self) -> dict[str, Any]:
        """Bloco `jogo_steam` do `state_full` — o TRI-ESTADO inteiro (ABA-DO-JOGO-01).

        `lido` distingue "não há jogo" de "o daemon acabou de subir e ainda não perguntou"
        (`StateStore.set_steam_jogo_appid`); sem ele a aba "No jogo" piscaria a cada restart.
        Coerção defensiva nos dois campos: um mock no `result` estoura no JSON do cliente.
        """
        lido = getattr(self.store, "steam_jogo_lido", None) is True
        appid_raw = getattr(self.store, "steam_jogo_appid", None)
        appid = (
            int(appid_raw)
            if isinstance(appid_raw, int) and not isinstance(appid_raw, bool)
            else None
        )
        return {"lido": lido, "appid": appid if lido else None}

    def _window_detect_payload(self) -> dict[str, Any]:
        """Bloco `window_detect_*` publicado por `state_full` e `daemon.status`
        (FEAT-WINDOW-DETECT-DIAG-01 + JANELA-CEGA-01).

        Os três campos antigos (backend/healthy/last_class) MENTIAM: em 28/07 o daemon publicava a
        própria janela e `healthy=True` com o backend devolvendo `None` a 2 Hz (`last_class` é
        STICKY e `healthy` um trinco de mão única). Os quatro novos:

        - `current_class`: a leitura CRUA do último tick (inclusive "unknown"/None);
        - `useful_age_sec`: segundos desde a última leitura ÚTIL (None = nunca);
        - `seeing`: houve leitura útil dentro de `WINDOW_DETECT_BLIND_AFTER_SEC` (decai e volta);
        - `reason`: POR QUE a última leitura não foi útil.

        `getattr` defensivo em tudo (store dublado).
        """
        idade_fn = getattr(self.store, "window_detect_useful_age", None)
        idade = idade_fn() if callable(idade_fn) else None
        seeing_fn = getattr(self.store, "window_detect_seeing", None)
        return {
            "window_detect_backend": _as_str_or_none(
                getattr(self.store, "window_detect_backend", None)
            ),
            "window_detect_healthy": bool(
                getattr(self.store, "window_detect_healthy", False)
            ),
            "window_detect_last_class": _as_str_or_none(
                getattr(self.store, "window_detect_last_class", None)
            ),
            "window_detect_current_class": _as_str_or_none(
                getattr(self.store, "window_detect_current_class", None)
            ),
            "window_detect_useful_age_sec": (
                round(float(idade), 1) if isinstance(idade, (int, float)) else None
            ),
            "window_detect_seeing": (
                bool(seeing_fn()) if callable(seeing_fn) else False
            ),
            "window_detect_reason": _as_str_or_none(
                getattr(self.store, "window_detect_reason", None)
            ),
        }

    async def _handle_daemon_pause(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pausa o despacho de input sem matar o daemon (FEAT-DAEMON-PAUSE-RESUME-01)."""
        self.daemon.pause()
        return {"status": "ok", "paused": True}

    async def _handle_daemon_resume(self, params: dict[str, Any]) -> dict[str, Any]:
        """Retoma o despacho de input (FEAT-DAEMON-PAUSE-RESUME-01)."""
        self.daemon.resume()
        return {"status": "ok", "paused": False}

    async def _handle_freestyle_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liga/desliga o Modo Freestyle — o botão «Modo Freestyle» da aba Jogar.

        O-FREESTYLE-E-UMA-CAMADA-SO-01 (28/09/2026), no lugar do `autoswitch.lock`. A palavra de
        produto: *«Aperto o botão do freestyle e o jogo que eu tiver jogando vai ter essa config
        independente do perfil do jogo.»*  (noqa-acento: citação)

        `ligado` opcional: ausente → inverte. **LIGAR** é o «Ativar» do Freestyle na aba Perfis, o
        mesmo caminho (o `profile.switch` dele, com a ativação à mão, liga o modo SEMPRE:
        `D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`); ligado, nenhum caminho automático troca o perfil.
        **DESLIGAR** devolve a escolha do usuário na hora, sem o leitor de janela (no COSMIC sem
        portal o autoswitch nunca acha janela): com jogo vivo, o jogo volta por cima
        (`origin="launch"`); sem jogo, a escolha (`origin="system"`); sem escolha, nenhum perfil
        ativo («Fica sem perfil», 29/09). A trava da troca à mão solta junto, com a linha no diário.
        """
        from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO
        from hefesto_dualsense4unix.profiles.manager import (
            o_freestyle_manda,
            soltar_a_trava_da_mao,
        )

        pedido = params.get("ligado")
        if pedido is not None and not isinstance(pedido, bool):
            raise ValueError("freestyle.set: 'ligado' precisa ser boolean")
        novo = (not o_freestyle_manda(self.store)) if pedido is None else pedido
        if novo:
            resposta = await self._handle_profile_switch({"name": NOME_DO_PADRAO})
        else:
            soltar_a_trava_da_mao(self.store, "freestyle_desligado")
            resposta = await self._o_que_volta_sem_o_freestyle()
        resposta["status"] = "ok"
        resposta["freestyle_ligado"] = o_freestyle_manda(self.store)
        logger.info("freestyle_set", ligado=resposta["freestyle_ligado"])
        return resposta

    async def _o_que_volta_sem_o_freestyle(self) -> dict[str, Any]:
        """O botão apagado: o jogo vivo, ou a escolha do usuário, ou nenhum perfil."""
        from hefesto_dualsense4unix.profiles.autoswitch import jogo_do_wrapper_vivo
        from hefesto_dualsense4unix.profiles.manager import perfil_do_appid
        from hefesto_dualsense4unix.utils.session import a_escolha_dela

        perfil = None
        with contextlib.suppress(Exception):
            appid = jogo_do_wrapper_vivo()
            perfil = perfil_do_appid(appid) if appid is not None else None
        nome, origem = (perfil.name, "launch") if perfil is not None else (
            a_escolha_dela(freestyle_ligado=False), "system")
        relatorio: dict[str, str] = {}
        self.profile_manager.apagar_o_freestyle(nome, origin=origem, relatorio=relatorio)
        if self.daemon is not None:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    materialize_launch_env,
                )

                materialize_launch_env(self.daemon)
        return {"active_profile": self.store.active_profile, "secoes": dict(relatorio)}

    async def _handle_native_mode_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liga/desliga o Modo Nativo — "release total" do controle (FEAT-NATIVE-MODE-01)."""
        if self.daemon is None:
            raise RuntimeError("daemon indisponível")
        raw = params.get("enabled")
        if raw is None:
            enabled = not self.daemon.is_native_mode()
        elif isinstance(raw, bool):
            enabled = raw
        else:
            raise ValueError("native.mode.set exige 'enabled' boolean ou omitido")
        origem = origem_do_pedido(params)
        if enabled and origem == "manual":
            new_state = self.daemon.set_native_mode(
                enabled, origin=origem, grava_o_modo=_porta_que_grava(origem)
            )
        else:
            new_state = self.daemon.set_native_mode(enabled, origin=origem)
        return {"status": "ok", "native_mode": bool(new_state)}

    async def _handle_daemon_state_full(self, params: dict[str, Any]) -> dict[str, Any]:
        """Estado completo pra GUI consumir a 20Hz."""
        snap = self.store.snapshot()
        state = (
            getattr(self.daemon, "_last_state", None) if self.daemon else None
        ) or snap.controller

        stale_warn_threshold = 3
        if (
            state is not None
            and self.controller.is_connected()
            and state.raw_lx == 128
            and state.raw_ly == 128
            and state.raw_rx == 128
            and state.raw_ry == 128
            and state.l2_raw == 0
            and state.r2_raw == 0
            and not state.buttons_pressed
        ):
            stale_count = self.store.bump("state_full.stale_neutral")
            if stale_count == stale_warn_threshold:
                logger.warning(
                    "state_stale_neutral_warning",
                    state_full_calls=stale_count,
                    hint="evdev_reader pode não ter conectado; HID-raw fallback estagnado",
                )

        buttons: list[str] = sorted(state.buttons_pressed) if state else []
        result: dict[str, Any] = {
            "connected": bool(state and state.connected),
            "transport": state.transport if state else None,
            "active_profile": snap.active_profile,
            "battery_pct": state.battery_pct if state else None,
            "l2_raw": state.l2_raw if state else 0,
            "r2_raw": state.r2_raw if state else 0,
            "lx": state.raw_lx if state else 128,
            "ly": state.raw_ly if state else 128,
            "rx": state.raw_rx if state else 128,
            "ry": state.raw_ry if state else 128,
            "buttons": buttons,
            "counters": snap.counters,
            "paused": bool(self.daemon is not None and self.daemon.is_paused()),
            "freestyle_ligado": bool(self.store.freestyle_ligado),
            "native_mode": bool(
                self.daemon is not None and self.daemon.is_native_mode()
            ),
            "native_mode_origin": _as_str_or_none(
                getattr(self.store, "native_mode_origin", None)
            ),
            "mode_from_profile": _as_str_or_none(
                getattr(self.daemon, "_mode_from_profile", None)
            ),
            "desktop_arranjo": _as_str_or_none(getattr(self.daemon, "arranjo_do_desktop", None)),
            "primary_grab_state": _as_str_or_none(
                getattr(
                    getattr(self.controller, "_evdev", None), "grab_state", None
                )
            ),
            "emulation_suppressed": bool(
                self.daemon is not None
                and getattr(self.daemon, "_emulation_suppressed", False)
            ),
            "keyboard_emulation": self._keyboard_emulation_payload(),
            "steam_input": self._steam_input_payload(),
            **self._window_detect_payload(),
        }
        result["game_signal"] = self._game_signal_snapshot()

        result["jogo_steam"] = self._jogo_steam_payload()

        result["pontes_confirmadas"] = self._pontes_confirmadas_no_tique()

        describe = getattr(self.controller, "describe_controllers", None)
        if callable(describe):
            controllers = describe()
            result["controllers"] = controllers
            if self.daemon is not None and isinstance(controllers, list):
                from hefesto_dualsense4unix.daemon.subsystems.coop import (
                    resolve_player_numbers,
                )

                entries = [c for c in controllers if isinstance(c, dict)]
                with contextlib.suppress(Exception):
                    for entry, number in zip(
                        entries,
                        resolve_player_numbers(self.daemon, entries),
                        strict=True,
                    ):
                        entry["player"] = number
            if isinstance(controllers, list):
                with contextlib.suppress(Exception):
                    self._enriquecer_e_medir_o_ar(
                        result, [c for c in controllers if isinstance(c, dict)], state
                    )

        entradas_de_controle = result.get("controllers")
        frageis = controles_bt_frageis(
            entradas_de_controle, native_mode=result["native_mode"]
        )
        conhece_a_mesa = isinstance(entradas_de_controle, list) and any(
            isinstance(e, dict) and e.get("connected") for e in entradas_de_controle
        )
        result["native_bt_fragil_controles"] = frageis
        result["native_bt_fragil"] = bool(
            frageis
            if conhece_a_mesa
            else (result["native_mode"] and result["transport"] == "bt")
        )

        result["controles_sem_driver"] = self._controles_sem_driver_payload()

        get_target = getattr(self.controller, "get_output_target_index", None)
        target_index: int | None = None
        if callable(get_target):
            raw_target = get_target()
            if isinstance(raw_target, int) and not isinstance(raw_target, bool):
                target_index = raw_target
        result["output_target_index"] = target_index

        from hefesto_dualsense4unix.daemon.subsystems.ouvinte_do_som import (
            som_do_sistema_payload,
        )

        result["som_do_sistema"] = som_do_sistema_payload(self.daemon)

        from hefesto_dualsense4unix.daemon.subsystems.intensidade_da_cena import (
            estado_do_daemon,
        )

        result["intensidade_da_cena"] = estado_do_daemon(self.daemon)

        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            result["mouse_emulation"] = self._mouse_emulation_payload()
            _flavor_da_sessao = str(getattr(daemon_cfg, "gamepad_flavor", "dualsense"))
            result["gamepad_emulation"] = {
                "enabled": bool(getattr(daemon_cfg, "gamepad_emulation_enabled", False)),
                "flavor": _flavor_da_sessao,
                "por_aparelho": _mascaras_por_aparelho(self),
                "caminho": _caminho_publicado(self.daemon),
            }
            gp_dev = getattr(self.daemon, "_gamepad_device", None)
            if gp_dev is not None:
                with contextlib.suppress(Exception):
                    result["gamepad_emulation"]["backend"] = str(
                        getattr(gp_dev, "backend", "") or ""
                    )
                with contextlib.suppress(Exception):
                    result["gamepad_emulation"]["ff_supported"] = bool(
                        getattr(gp_dev, "ff_supported", False)
                    )
                with contextlib.suppress(Exception):
                    from hefesto_dualsense4unix.integrations.virtual_pad import (
                        motivo_da_degradacao,
                    )

                    motivo = motivo_da_degradacao(gp_dev)
                    result["gamepad_emulation"]["degraded"] = motivo is not None
                    if motivo is not None:
                        result["gamepad_emulation"]["degraded_motivo"] = motivo
                with contextlib.suppress(Exception):
                    from hefesto_dualsense4unix.integrations import (
                        canal_sem_imu as _sem_imu,
                    )

                    sem_imu = _sem_imu.canal_sem_imu_do_vpad(gp_dev)
                    result["gamepad_emulation"]["canal_sem_imu"] = sem_imu
                    if sem_imu:
                        result["gamepad_emulation"]["canal_sem_imu_linhas"] = list(
                            _sem_imu.chaves_fora_do_ar()
                        )
                result["gamepad_emulation"]["o_que_o_jogo_ve"] = self._o_que_o_jogo_ve_de(
                    gp_dev,
                    _as_str_or_none(getattr(self.controller, "primary_uniq", None)),
                    result.get("transport"),
                )
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                    dedup_status,
                )

                dedup_ok, motivos = dedup_status(self.daemon)
                result["gamepad_emulation"]["dedup_ok"] = dedup_ok
                if motivos:
                    result["gamepad_emulation"]["dedup_motivo"] = ", ".join(motivos)
            result["gamepad_emulation"]["wrapper_used"] = None
            with contextlib.suppress(Exception):
                wrapper_used = self._wrapper_used_now()
                result["gamepad_emulation"]["wrapper_used"] = wrapper_used
                if (
                    wrapper_used is False
                    and result["gamepad_emulation"].get("enabled")
                    and not result.get("native_mode")
                    and result["gamepad_emulation"].get("dedup_ok", False)
                ):
                    result["gamepad_emulation"]["dedup_ok"] = False
                    motivo_atual = result["gamepad_emulation"].get("dedup_motivo")
                    result["gamepad_emulation"]["dedup_motivo"] = (
                        f"{motivo_atual}, jogo_sem_wrapper"
                        if motivo_atual
                        else "jogo_sem_wrapper"
                    )
            result["gamepad_emulation"]["mascara_divergente"] = None
            result["gamepad_emulation"]["mascara_divergencias"] = []
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    divergencias_publicadas,
                )

                divergencias = divergencias_publicadas(self.daemon)
                result["gamepad_emulation"]["mascara_divergencias"] = divergencias
                em_cena = [d for d in divergencias if d.get("em_cena")]
                if em_cena:
                    result["gamepad_emulation"]["mascara_divergente"] = em_cena[0]
            result["perfil_do_jogo_que_nao_entrou"] = self._perfil_que_nao_entrou()
            coop_mgr = getattr(self.daemon, "_coop_manager", None)
            players_raw = coop_mgr.player_count() if coop_mgr is not None else 1
            result["coop"] = {
                "enabled": bool(getattr(daemon_cfg, "coop_enabled", False)),
                "players": players_raw if isinstance(players_raw, int) else 1,
            }
            result["coop"]["mesa"] = []
            if coop_mgr is not None:
                with contextlib.suppress(Exception):
                    mesa = coop_mgr.mesa()
                    if isinstance(mesa, list):
                        result["coop"]["mesa"] = [
                            item for item in mesa if isinstance(item, dict)
                        ]
            registro_ext = getattr(self.daemon, "external_registry", None)
            conectados = getattr(registro_ext, "snapshot_connected", None)
            if callable(conectados):
                with contextlib.suppress(Exception):
                    vistos = conectados()
                    if isinstance(vistos, (set, frozenset)):
                        result["coop"]["externals"] = len(vistos)
            rumble_mult_applied = float(getattr(self.daemon, "_last_auto_mult", 1.0))
            result["rumble_policy"] = str(getattr(daemon_cfg, "rumble_policy", "balanceado"))
            result["rumble_policy_custom_mult"] = float(
                getattr(daemon_cfg, "rumble_policy_custom_mult", 0.7)
            )
            result["rumble_mult_applied"] = rumble_mult_applied
            result["rumble_motores"] = {}
            result["rumble_motor_pct_padrao"] = MOTOR_PCT_PADRAO
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                    _motores_do_perfil_ativo,
                )

                result["rumble_motores"] = {
                    uniq: {"forte_pct": par[0], "fraco_pct": par[1]}
                    for uniq, par in _motores_do_perfil_ativo(self.daemon).items()
                }

            vpads: list[tuple[int, Any, Any, str | None]] = []
            coop_mgr = getattr(self.daemon, "_coop_manager", None)
            numeros_por_mac: dict[str, int] = {}
            if (
                bool(getattr(getattr(self.daemon, "config", None), "coop_enabled", False))
                and coop_mgr is not None
            ):
                with contextlib.suppress(Exception):
                    numeros_por_mac = dict(coop_mgr.player_indexes())
            gp_device = getattr(self.daemon, "_gamepad_device", None)
            if gp_device is not None:
                primario = _as_str_or_none(
                    getattr(self.controller, "primary_uniq", None)
                )
                vpads.append(
                    (
                        int(numeros_por_mac.get(primario or "", 1) or 1),
                        gp_device,
                        getattr(self.daemon, "_motion_reader", None),
                        primario,
                    )
                )
            if coop_mgr is not None:
                players = getattr(coop_mgr, "_players", {})
                if isinstance(players, dict):
                    vpads.extend(
                        (
                            int(
                                numeros_por_mac.get(
                                    mac, getattr(p, "player_index", 0) or 0
                                )
                                or 0
                            ),
                            p.vpad,
                            getattr(p, "motion_reader", None),
                            _as_str_or_none(mac),
                        )
                        for mac, p in players.items()
                        if getattr(p, "vpad", None) is not None
                    )
            ff_plays = 0
            ff_nao_nulos = 0
            ff_descartados = 0
            ff_v2 = 0
            ff_paradas = 0
            ff_estranhos = 0
            ff_last: tuple[int, int] = (0, 0)
            per_vpad: list[dict[str, Any]] = []
            from hefesto_dualsense4unix.daemon.subsystems.coop import (
                identidade_do_vpad,
            )

            for player_num, vp, motion_reader, uniq_do_fisico in vpads:
                with contextlib.suppress(Exception):
                    ff_plays += int(getattr(vp, "ff_play_count", 0) or 0)
                    ff_nao_nulos += int(getattr(vp, "ff_nao_nulo_count", 0) or 0)
                    ff_descartados += int(getattr(vp, "ff_descartado_count", 0) or 0)
                    ff_v2 += int(getattr(vp, "ff_v2_count", 0) or 0)
                    ff_paradas += int(getattr(vp, "ff_parada_sdl_count", 0) or 0)
                    ff_estranhos += int(
                        getattr(vp, "ff_report_estranho_count", 0) or 0
                    )
                    last = getattr(vp, "ff_last_sent", None)
                    if isinstance(last, tuple) and len(last) == 2 and last != (0, 0):
                        ff_last = (int(last[0]), int(last[1]))
                with contextlib.suppress(Exception):
                    backend = getattr(vp, "backend", None)
                    streaming = getattr(vp, "motion_streaming", False)
                    hz_raw = getattr(motion_reader, "emit_hz", 0.0)
                    identidade = identidade_do_vpad(vp)
                    no_do_vpad = self._no_do_vpad_cached(
                        identidade["vpad_uniq"], identidade["vpad_nome"]
                    )
                    per_vpad.append(
                        {
                            "player": player_num,
                            "uniq": uniq_do_fisico,
                            "vpad_uniq": identidade["vpad_uniq"],
                            "vpad_nome": identidade["vpad_nome"],
                            "vpad_indice": identidade["vpad_indice"],
                            "evdev": no_do_vpad["evdev"],
                            "hidraw": no_do_vpad["hidraw"],
                            "ino": no_do_vpad["ino"],
                            "hidraw_ino": no_do_vpad["hidraw_ino"],
                            "game_open": getattr(vp, "game_open", False) is True,
                            "backend": backend if isinstance(backend, str) else None,
                            "ff_play_count": int(getattr(vp, "ff_play_count", 0) or 0),
                            "ff_nao_nulo_count": int(
                                getattr(vp, "ff_nao_nulo_count", 0) or 0
                            ),
                            "ff_maior_pedido": _par_de_motores(
                                getattr(vp, "ff_maior_pedido", None)
                            ),
                            "ff_descartado_count": int(
                                getattr(vp, "ff_descartado_count", 0) or 0
                            ),
                            "ff_descartado_amostra": _amostra_de_descarte(
                                getattr(vp, "ff_descartado_amostra", None)
                            ),
                            "ff_v2_count": int(getattr(vp, "ff_v2_count", 0) or 0),
                            "ff_parada_sdl_count": int(
                                getattr(vp, "ff_parada_sdl_count", 0) or 0
                            ),
                            "ff_report_estranho_count": int(
                                getattr(vp, "ff_report_estranho_count", 0) or 0
                            ),
                            "ff_report_estranho_amostra": _report_estranho(
                                getattr(vp, "ff_report_estranho_amostra", None)
                            ),
                            "ff_ultimos_reports": _anel_de_vibracao(
                                getattr(vp, "ff_ultimos_reports", None)
                            ),
                            "ff_por_classe": (
                                {str(k): int(v) for k, v in classes.items()}
                                if isinstance(
                                    classes := getattr(vp, "ff_por_classe", None), dict
                                ) else None
                            ),
                            "ff_forma_do_periodico": (
                                dict(forma_p)
                                if isinstance(
                                    forma_p := getattr(vp, "ff_forma_do_periodico", None), dict
                                ) else None
                            ),
                            "ff_ultimos_trechos": (
                                [list(t) for t in trechos]
                                if isinstance(
                                    trechos := getattr(vp, "ff_ultimos_trechos", None), list
                                ) else None
                            ),
                            "ff_rota": self._rota_do_rumble(uniq_do_fisico, backend),
                            "output_count": int(getattr(vp, "output_count", 0) or 0),
                            "trigger_replicas": int(
                                getattr(vp, "trigger_replicas", 0) or 0
                            ),
                            "lightbar_replicas": int(
                                getattr(vp, "lightbar_replicas", 0) or 0
                            ),
                            "player_led_replicas": int(
                                getattr(vp, "player_led_replicas", 0) or 0
                            ),
                            "motion_streaming": (
                                streaming if isinstance(streaming, bool) else False
                            ),
                            "motion_hz": (
                                float(hz_raw)
                                if isinstance(hz_raw, (int, float))
                                and not isinstance(hz_raw, bool)
                                else 0.0
                            ),
                            "reports_perdidos": (
                                _contador_do_vpad(motion_reader, "reports_perdidos")
                                if motion_reader is not None
                                else None
                            ),
                            "reports_estragados": (
                                _contador_do_vpad(motion_reader, "reports_estragados")
                                if motion_reader is not None
                                else None
                            ),
                            "touchpad_clicks": int(
                                getattr(vp, "touchpad_click_count", 0) or 0
                            ),
                            "touchpad_pressionado": bool(
                                getattr(vp, "touchpad_click", False) is True
                            ),
                            "motion_forwards": _contador_do_vpad(
                                vp, "motion_forward_count"
                            ),
                            "jack": _jack_do_vpad(vp),
                            "jack_forwards": _contador_do_vpad(
                                vp, "jack_forward_count"
                            ),
                            "bateria_no_jogo": _bateria_do_vpad(vp),
                            "battery_forwards": _contador_do_vpad(
                                vp, "battery_forward_count"
                            ),
                            "mic_button_forwards": _contador_do_vpad(
                                vp, "mic_button_count"
                            ),
                            **_o_microfone_do_jogo_no_vpad(vp),
                            "rumble_no_fisico": _par_de_motores(
                                getattr(vp, "rumble_no_fisico", None)
                            ),
                            "rumble_no_fisico_ha_s": _idade_ou_none(
                                getattr(vp, "rumble_no_fisico_ha_s", None)
                            ),
                            "visto_ha_s": _visto_ha_s(vp),
                            "audio_do_jogo_amostra": _audio_do_jogo_amostra(vp),
                        }
                    )
            result["rumble_ff"] = {
                "plays": ff_plays,
                "nao_nulos": ff_nao_nulos,
                "descartados": ff_descartados,
                "v2": ff_v2,
                "paradas": ff_paradas,
                "estranhos": ff_estranhos,
                "last_weak": ff_last[0],
                "last_strong": ff_last[1],
                "vpads": len(vpads),
                "per_vpad": per_vpad,
            }
            hotkey_cfg = getattr(
                getattr(self.daemon, "_hotkey_manager", None), "config", None
            )
            if hotkey_cfg is not None:
                buffer_ms = getattr(hotkey_cfg, "buffer_ms", None)
                passthrough = getattr(hotkey_cfg, "passthrough_in_emulation", None)
                if isinstance(buffer_ms, int) and not isinstance(buffer_ms, bool):
                    result["hotkey"] = {
                        "buffer_ms": buffer_ms,
                        "passthrough_in_emulation": bool(passthrough),
                    }
            result["mic_button_toggles_system"] = bool(
                getattr(daemon_cfg, "mic_button_toggles_system", True)
            )
            from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
                habilitado_por_env,
                uniqs_pedidos,
            )

            bt_mic_sub = getattr(self.daemon, "_bt_mic_subsystem", None)
            com_ponte: list[str] = []
            motivo = ""
            if bt_mic_sub is not None:
                with contextlib.suppress(Exception):
                    com_ponte = sorted(bt_mic_sub.uniqs_com_ponte())
                with contextlib.suppress(Exception):
                    motivo = str(bt_mic_sub.motivo)
            result["bt_mic"] = {
                "enabled": bool(uniqs_pedidos(daemon_cfg)) or habilitado_por_env(),
                "running": bt_mic_sub is not None,
                "uniqs": com_ponte,
                "motivo": motivo,
            }
            rumble_active = getattr(daemon_cfg, "rumble_active", None)
            result["rumble_passthrough"] = rumble_active is None
            result["rumble_active"] = (
                [int(rumble_active[0]), int(rumble_active[1])]
                if rumble_active is not None
                else None
            )

        result["mic_da_mesa"] = recado_do_microfone.publicar(self.daemon)

        navegacao = self._navegacao_payload()
        if navegacao is not None:
            result["navegacao"] = navegacao

        _com_a_marca_do_f_hid(result)
        return result

    def _rota_do_rumble(self, uniq: Any, backend: Any) -> dict[str, Any] | None:
        """Por onde vai o rumble do pad ``uinput`` (``alto_falante.por_onde_vai_o_rumble``)."""
        alto_falante = getattr(self.daemon, "_alto_falante_subsystem", None)
        rota = getattr(alto_falante, "por_onde_vai_o_rumble", None)
        if backend != "uinput" or not isinstance(uniq, str) or not uniq or not callable(rota):
            return None
        resposta = rota(uniq)
        return dict(resposta) if isinstance(resposta, dict) else None

    def _enrich_controllers_per_controller(
        self, entries: list[dict[str, Any]], state: Any
    ) -> None:
        """Enriquece cada entrada de `controllers` com o estado POR CONTROLE (shape estável para
        GUI/CLI; campos antigos não mudam).

        - ``serial``/``modelo``/``nome_declarado`` (ROTA-A): QUEM é o aparelho, nunca a posição;
          nascem ``None`` e só saem do ``None`` com fonte (:meth:`_identidade_publicada`).
        - ``player_slot``: número de sessão (COR-01/D6) do `identity_registry`, com ``assign=False``
          (ler nunca aloca); ausente → None.
        - ``lightbar_rgb``/``lightbar_on``/``lightbar_source``: a cor efetiva CONHECIDA, decidida
          pelo DONO DA ESCRITA:
          * ``"sysfs"``: nó gravável E escrito por nós (`_sysfs_written`); a classe LED é a verdade,
            e SÓ aqui ``(0, 0, 0)`` é "apagada";
          * ``"desired"``: nó não gravável (a escrita foi por hidraw, classe stale) mas o backend
            conhece a última cor (`resolved_led_for`);
          * ``"desconhecida"``: rgb None, NUNCA rotulada "apagada" (o LED pode brilhar o azul do
            kernel). Modo Nativo: a barra é do Hefesto
            (`D-2309-NO-NATIVO-A-LUZ-E-O-NUMERO-SAO-DO-HEFESTO`,
            `D-2409-NO-NATIVO-A-TELA-MOSTRA-A-COR`). D8: expõe-se UMA cor, a efetiva pós-escala de
            brilho; o contraste do traço é da tela (`cor_do_plastico.tom_para_a_borda`).
        - ``lightbar_disputada`` (ESCRITOR-CRU-01): outro processo (hoje só a Steam) segura o
          ``hidraw`` deste controle, então ``lightbar_rgb`` é a cor PEDIDA e pode não ser a acesa
          (16/08: o mesmo ``[0 255 0]`` apagada e verde). Sai da foto do sentinela (tique de 30 s);
          não toca ``/proc``.
        - ``brilho_da_barra``/``brilho_das_luzes`` (A-04-PERGUNTA-AO-DAEMON-VIVO-01): o brilho
          acesso e o degrau das luzes de número, com a camada da usuária; ``None`` = não sei
          (:meth:`_brilhos_acesos`).
        - ``nascimento`` (SINAL-NO-NASCIMENTO-01/E2): como a CONEXÃO nasceu; ``None`` = **não
          carimbei** (nunca "limpa"); vem do cartório do tique de hotplug
          (:meth:`_nascimento_para`).
        - ``inputs``: ``{lx,ly,rx,ry,l2_raw,r2_raw,buttons}`` + opcionais ``gyro`` (``{x,y,z}`` em
          graus/s) e ``touchpad`` (``{touching,x,y,width,height}``) via `SensorHub` (S2), ou None.
          **TRÊS FONTES, nesta ordem (a ordem é o contrato):** 1. o PRIMÁRIO espelha o `state` do
          topo (`daemon._last_state`, mesma fonte; armadilha A-09); `state` None fica None e NÃO cai
          para a 3; 2. secundário promovido pelo co-op: `CoopManager.live_snapshots()`;
          3. **STATUS-04**: qualquer outro conectado, por um `EvdevReader` PASSIVO do `SensorHub`
            (:meth:`_inputs_passivos`), que cura a mesa pela metade com o co-op desmontado (Nativo,
            emulação off, suspensão por Steam Input). Sem nenhuma → None (o card mostra "—", nunca
            um valor congelado).
        - ``vpad_backend``/``vpad_motivo`` (BT-03): backend do vpad DO JOGADOR deste controle
          ("uhid" | "uinput") e o motivo da degradação (`fallback_motivo`: "uhid_indisponivel",
          "uhid_start_falhou", "uhid_bind_falhou", "uhid_vetado_pelo_chamador", "sem_uhid"). Por
          controle, ao contrário do `dedup_status` (DEDUP-06); não jogador → None; máscara xbox é
          uinput por desenho e nunca tem motivo.

        Custo: sysfs no MÁXIMO 1x/s por nó (`_lightbar_read_cached`); nada toca hardware.
        """
        sysfs_map = getattr(self.controller, "_sysfs", None)
        written_map = getattr(self.controller, "_sysfs_written", None)
        node_by_uniq: dict[str, Any] = {}
        written_by_uniq: dict[str, tuple[int, int, int]] = {}
        if isinstance(sysfs_map, dict):
            for key, node in sysfs_map.items():
                uniq = _norm_uniq(key)
                if uniq is not None and node is not None:
                    node_by_uniq[uniq] = node
        if isinstance(written_map, dict):
            for key, raw in written_map.items():
                uniq = _norm_uniq(key)
                rgb = _rgb_or_none(raw)
                if uniq is not None and rgb is not None:
                    written_by_uniq[uniq] = rgb

        nos_por_uniq: dict[str, str] = {}
        mapear = getattr(self.controller, "nos_hidraw_por_uniq", None)
        if callable(mapear):
            with contextlib.suppress(Exception):
                nos_por_uniq = dict(mapear() or {})

        snapshots = self._coop_live_snapshots()
        com_leitor_coop = self._coop_uniqs_com_leitor()
        vpad_by_uniq = self._coop_vpads_by_uniq()
        gp_dev = (
            getattr(self.daemon, "_gamepad_device", None)
            if self.daemon is not None
            else None
        )

        for entry in entries:
            uniq = entry.get("uniq")
            uniq = uniq if isinstance(uniq, str) and uniq else None

            entry["player_slot"] = self._player_slot_for(uniq)

            entry.update(self._identidade_publicada(entry, uniq))

            rgb, on, source = self._lightbar_for_uniq(
                uniq, node_by_uniq, written_by_uniq
            )
            entry["lightbar_rgb"] = list(rgb) if rgb is not None else None
            entry["lightbar_on"] = on
            entry["lightbar_source"] = source
            entry["lightbar_disputada"] = self._lightbar_disputada(uniq, nos_por_uniq)
            entry["nascimento"] = self._nascimento_para(uniq)
            entry.update(self._brilhos_acesos(uniq))

            if entry.get("is_primary") and state is not None:
                entry["inputs"] = self._inputs_from_state(state)
            elif uniq is not None and uniq in snapshots:
                entry["inputs"] = self._inputs_from_snapshot(snapshots[uniq])
            else:
                entry["inputs"] = self._inputs_passivos(entry, uniq, com_leitor_coop)
            self._merge_sensores(entry, uniq)
            self._merge_audio(entry, uniq)

            backend, motivo = (None, None)
            if entry.get("is_primary") and gp_dev is not None:
                backend, motivo = self._vpad_backend_motivo(gp_dev)
            elif uniq is not None and uniq in vpad_by_uniq:
                backend, motivo = vpad_by_uniq[uniq]
            entry["vpad_backend"] = backend
            entry["vpad_motivo"] = motivo
            entry["o_que_o_jogo_ve"] = self._o_que_o_jogo_ve_de(
                gp_dev
                if entry.get("is_primary") and gp_dev is not None
                else self._coop_vpad_de(uniq),
                uniq,
                entry.get("transport"),
            )

        self._agenda_de_identidade().esquecer_ausentes(
            {
                str(entry["uniq"])
                for entry in entries
                if entry.get("connected") and isinstance(entry.get("uniq"), str)
            }
        )

    def _identidade_publicada(
        self, entry: dict[str, Any], uniq: str | None
    ) -> dict[str, str | None]:
        """``{serial, modelo, nome_declarado}`` deste controle; ``None`` = não sei (ROTA-A).

        O nome vinha da POSIÇÃO na lista (com um controle "Starlight Blue", com dois o mesmo cabo
        virava "Cosmic Red"), porque o daemon não publicava nada que identificasse o aparelho. Cada
        chave tem uma fonte:

        * ``nome_declarado``: o que O usuário nomeou, de `maquina.json` (`controles[<uniq>].cor`,
        C2); zero I/O (o `_maquina` é REBINDADO no "Aplicar" do `machine.declare`);
        * ``modelo``: o nome de fábrica decodificado dos caracteres 5-6 do serial
          (`integrations/cor_do_plastico`);
        * ``serial``: o serial de fábrica de 17 caracteres, cru.

        **A disciplina é `None`**: um ``modelo=None`` vira travessão; um modelo inventado é o
        defeito. Sem default, sem queda para "DualSense", sem tabela por VID/PID. Ler o serial é um
        `SET_FEATURE` `0x80` e só o daemon, que tem o aparelho, o faz sem disputar o hidraw; a
        leitura sai numa thread (uma em voo por `uniq`), não nesta função (10 Hz), e enquanto não
        volta sai ``None``.
        """
        declarado: str | None = None
        maquina = getattr(self.daemon, "_maquina", None) if self.daemon else None
        controles = getattr(maquina, "controles", None)
        if uniq and isinstance(controles, dict):
            declaracao = controles.get(uniq)
            bruto = getattr(declaracao, "cor", None)
            declarado = bruto.strip() if isinstance(bruto, str) and bruto.strip() else None

        de_fabrica = self._identidade_de_fabrica(uniq, entry)
        return {
            "serial": de_fabrica["serial"],
            "modelo": de_fabrica["modelo"],
            "nome_declarado": declarado,
        }

    def _identidade_de_fabrica(
        self, uniq: str | None, entry: dict[str, Any]
    ) -> dict[str, str | None]:
        """``{serial, modelo}`` do cache de sessão, disparando a leitura se for a hora."""
        vazio: dict[str, str | None] = {"serial": None, "modelo": None}
        if not uniq or not entry.get("connected"):
            return dict(vazio)
        cache = self._identidade_de_fabrica_cache
        if cache is None:
            cache = {}
            self._identidade_de_fabrica_cache = cache
        pronto = cache.get(uniq)
        if pronto is not None:
            return dict(pronto)
        dono = getattr(self, "daemon", None)
        registro: Any = getattr(dono, "identity_registry", None) if dono else None
        if getattr(registro, "pergunta_de_fabrica_armada", False) is True:
            achado = registro.identidade_de_fabrica(uniq)
            if achado is None:
                registro.agendar_a_pergunta_de_fabrica(uniq)
                return dict(vazio)
            serial = getattr(achado, "serial", None)
            nome = getattr(getattr(achado, "cor", None), "nome", None)
            return {
                "serial": serial if isinstance(serial, str) else None,
                "modelo": nome if isinstance(nome, str) else None,
            }
        if self._agenda_de_identidade().reservar(uniq):
            try:
                import threading

                threading.Thread(
                    target=self._perguntar_identidade,
                    args=(uniq,),
                    name=f"identidade-{uniq[:6]}",
                    daemon=True,
                ).start()
            except Exception:
                with contextlib.suppress(Exception):
                    from hefesto_dualsense4unix.integrations.cor_do_plastico import (
                        IdentidadeDeFabrica,
                    )

                    self._agenda_de_identidade().registrar(
                        uniq, IdentidadeDeFabrica(motivo="a thread não nasceu")
                    )
        return dict(vazio)

    def _agenda_de_identidade(self) -> Any:
        """A `AgendaDaPergunta` desta instância, criada no primeiro uso."""
        agenda = getattr(self, "_agenda_da_identidade", None)
        if agenda is None:
            from hefesto_dualsense4unix.integrations.cor_do_plastico import (
                AgendaDaPergunta,
            )

            agenda = AgendaDaPergunta()
            self._agenda_da_identidade = agenda
        return agenda

    def _perguntar_identidade(self, uniq: str) -> None:
        """A leitura, fora do laço. Só a RESPOSTA entra no cache."""
        from hefesto_dualsense4unix.integrations.cor_do_plastico import (
            IdentidadeDeFabrica,
            ler_identidade_pelo_cabo,
        )

        achado = IdentidadeDeFabrica(motivo="a leitura não devolveu")
        try:
            achado = ler_identidade_pelo_cabo(uniq)
        except Exception as erro:
            achado = IdentidadeDeFabrica(motivo=f"a leitura levantou {type(erro).__name__}")
        finally:
            if achado.definitiva:
                cache = self._identidade_de_fabrica_cache
                if cache is None:
                    cache = {}
                    self._identidade_de_fabrica_cache = cache
                cache[uniq] = {
                    "serial": achado.serial,
                    "modelo": None if achado.cor is None else achado.cor.nome,
                }
            self._agenda_de_identidade().registrar(uniq, achado)

    def _merge_sensores(self, entry: dict[str, Any], uniq: str | None) -> None:
        """Acrescenta `gyro`/`touchpad` ao `inputs` deste controle (S2)."""
        inputs = entry.get("inputs")
        if uniq is None or not isinstance(inputs, dict):
            return
        hub = self._sensor_hub or self._garantir_sensor_hub()
        leitura: Any = None
        with contextlib.suppress(Exception):
            leitura = hub.leitura(uniq)
        if isinstance(leitura, dict):
            inputs.update(leitura)
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

            estado = REGISTRO.estado(uniq)
            entry["sensores"] = {
                "giroscopio_ligado": estado.giroscopio,
                "acelerometro_ligado": estado.acelerometro,
                "grab_do_movimento": self._grab_do_movimento(hub, uniq),
                "touchpad": "ligado" if REGISTRO.touchpad_ligado(uniq) else "desligado",
                "touchpad_alcance": _alcance_do_toque(getattr(self, "daemon", None)),
            }

    @staticmethod
    def _grab_do_movimento(hub: Any, uniq: str) -> str:
        """`off|pending|held|failed|sem_reader` do nó de movimento de `uniq`; hub sem o método
        (dublê) é "não sei", nunca exceção."""
        perguntar = getattr(hub, "grab_do_movimento", None)
        if not callable(perguntar):
            return "desconhecido"
        try:
            return str(perguntar(uniq))
        except Exception:
            return "desconhecido"

    def _garantir_sensor_hub(self) -> Any:
        """O `SensorHub` desta sessão, criado no primeiro uso (S2/STATUS-04)."""
        hub = self._sensor_hub
        if hub is None:
            from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub

            hub = SensorHub()
            hub.perguntar_ao_daemon(
                ha_jogo=self._ha_jogo_para_o_toque,
                toque_proprio_do_jogo=self._jogo_tem_toque_proprio,
            )
            self._sensor_hub = hub
        return hub

    def _ha_jogo_para_o_toque(self) -> bool:
        """O mesmo sinal de jogo do tato vivo: autoridade `game` ou janela de jogo em foco."""
        from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import ha_jogo

        return bool(self.daemon is not None and ha_jogo(self.daemon))

    def _jogo_tem_toque_proprio(self, uniq: str) -> bool:
        """O jogo em foco recebe o toque desta peça pelo vpad: a máscara dela é a DualSense.

        A ficha do jogo (``ficha_declarada``) ainda não chega ao daemon; enquanto isso vale a
        máscara. Perfil em cursor/zonas e cliente DSU têm demanda própria no hub.
        """
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva

        cfg = getattr(self.daemon, "config", None)
        da_sessao = str(getattr(cfg, "gamepad_flavor", "dualsense"))
        return str(mascara_efetiva(uniq, da_sessao)) == "dualsense" and not _na_steam(self)

    def _inputs_passivos(
        self, entry: dict[str, Any], uniq: str | None, com_leitor_coop: set[str]
    ) -> dict[str, Any] | None:
        """Entrega STATUS-04: `inputs` de quem não tem NENHUMA outra fonte.

        Com o co-op desmontado (Nativo, emulação off) metade da mesa ficava muda justo quando ela
        joga. As TRÊS recusas, cada uma evita uma mentira:

        - **primário**: seria um snapshot evdev paralelo ao `state` do topo (A-09); `state is None`
          = "o daemon não está lendo";
        - **desconectado**: abrir node de quem saiu;
        - **controle que o co-op já segura** (inclusive o pendente de grab): o node está sob
          `EVIOCGRAB` e o fd passivo não recebe evento; medido em 04/09/2026 ele publica a posição
          de repouso do `absinfo` (`lx=129 ly=130 …`) parada para sempre, um número plausível e
          congelado.

        Custo sem trabalho: um `set` de MACs e três `if`, sem I/O (a abertura mora na thread de
        manutenção do hub).
        """
        if uniq is None or entry.get("is_primary") or not entry.get("connected"):
            return None
        if uniq in com_leitor_coop:
            return None
        leitura: Any = None
        with contextlib.suppress(Exception):
            leitura = self._garantir_sensor_hub().entradas(uniq)
        return leitura if isinstance(leitura, dict) else None

    def _coop_uniqs_com_leitor(self) -> set[str]:
        """MACs cujo node de gamepad o co-op já abriu (promovido OU pendente)."""
        coop = (
            getattr(self.daemon, "_coop_manager", None)
            if self.daemon is not None
            else None
        )
        players = getattr(coop, "_players", None) if coop is not None else None
        if not isinstance(players, dict):
            return set()
        return {
            mac
            for mac in players
            if isinstance(mac, str) and mac and not mac.startswith("path:")
        }

    def _merge_audio(self, entry: dict[str, Any], uniq: str | None) -> None:
        """Acrescenta `audio` e `speaker` a ESTE controle (AUDIO-STATUS-01 / D4); ambas OPCIONAIS (a
        GUI esconde o bloco em vez de inventar).

        - ``audio`` = ``{fone_plugado, mic_externo, mic_mudo}``: LEITURA do byte de estado de todo
          report de INPUT; ausente até um report ser lido.
        - ``audio.mic_mudo_desejado`` (MIC-USB-01): QUEM MANDA no mudo. ``true``/``false`` = o
          hefesto é dono e afirma esse valor em todo report (veio de `mic.set`); ``null`` = a posse
          é do `hid-playstation`. Só entra se o backend responde (`microphone_mute_for`); sem ele a
          aba Status não distingue "aperte o botão" de "desmute pela janela".
        - ``speaker`` = ``{volume: 0-255, muted: bool}`` (+ chaves de ``audio``): **só quando o
          hefesto é dono do volume**, pois o DualSense NÃO devolve o volume e qualquer número antes
          do 1º `speaker.set` seria chute.

        Cada leitura é defensiva por conta própria (dublê, backend sem os métodos).
        """
        status: Any = None
        status_fn = getattr(self.controller, "audio_status_for", None)
        if callable(status_fn):
            with contextlib.suppress(Exception):
                status = status_fn(uniq)
        if isinstance(status, dict):
            dono_fn = getattr(self.controller, "microphone_mute_for", None)
            if callable(dono_fn):
                desejado: Any = None
                with contextlib.suppress(Exception):
                    desejado = dono_fn(uniq)
                status["mic_mudo_desejado"] = (
                    bool(desejado) if isinstance(desejado, bool) else None
                )
            from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
                canal_do_microfone,
            )

            lido = canal_do_microfone(uniq)
            if isinstance(lido, dict):
                status["canal_ativo"] = bool(lido.get("canal_ativo"))
                status["canal_mudo"] = lido.get("canal_mudo")
                status["volume_captura"] = lido.get("volume_captura")
                status["canal_fonte"] = lido.get("fonte")
            from hefesto_dualsense4unix.daemon.subsystems.luz_do_mic import (
                estado_da_luz_do_mic,
                quem_ouve_este_mic,
            )

            luz = estado_da_luz_do_mic(str(uniq or ""))
            if luz is not None:
                status["luz_do_mic"] = int(luz)
            _a_luz_do_jogo_no_controle(status, uniq)
            ouvintes = quem_ouve_este_mic(str(uniq or ""))
            if ouvintes is not None:
                status["ouvintes_do_mic"] = list(ouvintes)
            entry["audio"] = status

        speaker: Any = None
        speaker_fn = getattr(self.controller, "speaker_state_for", None)
        if callable(speaker_fn):
            with contextlib.suppress(Exception):
                speaker = speaker_fn(uniq)
        if not isinstance(speaker, dict):
            return
        volume = speaker.get("volume")
        if not isinstance(volume, int) or isinstance(volume, bool):
            return
        bloco: dict[str, Any] = {
            "volume": max(0, min(255, volume)),
            "muted": bool(speaker.get("muted")),
        }
        rota = speaker.get("rota")
        if isinstance(rota, int) and not isinstance(rota, bool):
            bloco["rota"] = rota
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            fonte_publicada,
        )

        fonte = fonte_publicada(str(uniq or ""))
        if fonte:
            bloco["fonte"] = fonte
        if isinstance(status, dict):
            bloco.update(status)
        entry["speaker"] = bloco
        inputs = entry.get("inputs")
        if isinstance(inputs, dict):
            inputs["speaker"] = dict(bloco)

    def _lightbar_for_uniq(
        self,
        uniq: str | None,
        node_by_uniq: dict[str, Any],
        written_by_uniq: dict[str, tuple[int, int, int]],
    ) -> tuple[tuple[int, int, int] | None, bool, str]:
        """(rgb, on, source) de UM controle, pelo dono da escrita (STATUS-01)."""
        if uniq is not None:
            node = node_by_uniq.get(uniq)
            if node is not None and uniq in written_by_uniq:
                rgb, node_on = self._lightbar_read_cached(node)
                if rgb is not None:
                    return rgb, bool(node_on and rgb != (0, 0, 0)), "sysfs"
            resolved = getattr(self.controller, "resolved_led_for", None)
            if callable(resolved):
                rgb = None
                with contextlib.suppress(Exception):
                    rgb = _rgb_or_none(resolved(uniq))
                if rgb is not None:
                    return rgb, rgb != (0, 0, 0), "desired"
        return None, False, "desconhecida"

    def _brilhos_acesos(self, uniq: str | None) -> dict[str, Any]:
        """Os dois brilhos que ESTE controle acende agora — sempre as duas chaves
        (A-04-PERGUNTA-AO-DAEMON-VIVO-01).

        Pergunte ao daemon vivo, não ao perfil: a camada da usuária (R-20) atravessa o autoswitch
        (medido na mesa de quatro: o P3 em Forte seguia Forte após o perfil dizer Fraco, e o trilho
        dizia 82% com o P1 a 60%).

        - ``brilho_da_barra``: ``0.0``-``1.0``, o brilho em que ``lightbar_rgb`` foi acesa
          (`brilho_da_barra_para`);
        - ``brilho_das_luzes``: ``"fraco"``, ``"medio"`` ou ``"forte"`` (noqa-acento):
          o degrau das luzes de número (`brilho_das_luzes_para`).

        Só lê; ``None`` = «não sei» (backend sem as leituras, controle sem MAC, perfil sem brilho) e
        quem lê cai no disco.
        """
        from hefesto_dualsense4unix.core.led_control import BRILHOS_DAS_LUZES

        saida: dict[str, Any] = {"brilho_da_barra": None, "brilho_das_luzes": None}
        if uniq is None:
            return saida
        barra = getattr(self.controller, "brilho_da_barra_para", None)
        if callable(barra):
            with contextlib.suppress(Exception):
                brilho = barra(uniq)
                if isinstance(brilho, (int, float)) and not isinstance(brilho, bool):
                    saida["brilho_da_barra"] = max(0.0, min(1.0, float(brilho)))
        luzes = getattr(self.controller, "brilho_das_luzes_para", None)
        if callable(luzes):
            with contextlib.suppress(Exception):
                degrau = luzes(uniq)
                if isinstance(degrau, int) and not isinstance(degrau, bool):
                    saida["brilho_das_luzes"] = next(
                        (p for p, d in BRILHOS_DAS_LUZES.items() if d == degrau), None
                    )
        return saida

    def _lightbar_disputada(
        self, uniq: str | None, nos_por_uniq: dict[str, str]
    ) -> bool:
        """True quando OUTRO processo segura o hidraw DESTE controle (ESCRITOR-CRU-01).

        O sysfs guarda o PEDIDO, nunca o aceso (16/08: o mesmo `[0 255 0]` com a barra apagada e com
        ela verde); com escritor cru a tela só pode afirmar "esta é a cor que o Hefesto pediu". Sai
        da foto do sentinela (tique de 30 s do `reconnect_loop`): sondar `/proc` seria um `pgrep`
        por segundo.

        **ESCRITOR-CRU-03 (19/09/2026): a foto é CONFERIDA, não repetida.** Crua, ela contava o
        passado (Steam com SIGTERM e o `state_full` dizendo ``True`` sete segundos depois; em Modo
        Nativo o vigia nem sonda). `segurado_de_fato` confere se os PIDs da foto ainda EXISTEM (um
        `stat` em `/proc/<pid>`): só pode apagar um aviso, nunca acender.

        ``False`` também é nada sondado ainda: ausência de sonda não prova que ninguém segura, e
        aviso sem dado treina a ignorá-lo.
        """
        if uniq is None:
            return False
        no = nos_por_uniq.get(uniq)
        if not no or self.daemon is None:
            return False
        sentinela = getattr(self.daemon, "_sentinela_de_escritor_cru", None)
        if not isinstance(sentinela, _escritor_cru.SentinelaDeEscritorCru):
            return False
        return bool(sentinela.veredito.segurado_de_fato(no))

    def _nascimento_para(self, uniq: str | None) -> dict[str, Any] | None:
        """Como a conexão DESTE controle nasceu; ``None`` = **não carimbei**."""
        if uniq is None or self.daemon is None:
            return None
        cartorio = getattr(self.daemon, "_cartorio_do_nascimento", None)
        if not isinstance(cartorio, _sinal_da_barra.CartorioDoNascimento):
            return None
        carimbo = cartorio.do_uniq(uniq)
        if carimbo is None:
            return None
        return {
            "confianca": str(carimbo.confianca),
            "porque": str(carimbo.porque),
            "pede_reconexao": bool(carimbo.pede_reconexao),
            "instancia": str(carimbo.instancia),
            "hw_version": str(carimbo.hw_version),
            "firme": bool(carimbo.firme),
        }

    def _lightbar_read_cached(
        self, node: Any
    ) -> tuple[tuple[int, int, int] | None, bool]:
        """Leitura (rgb, brightness>0) de um nó LED com cache TTL por nó (STATUS-01).

        No máximo 1 leitura/s por nó (`_LIGHTBAR_READ_TTL_SEC`; o `state_full` roda a 10 Hz). Keyed
        pelo `indicator_dir`, que muda quando o kernel recria o nó (invalidação natural no replug).
        """
        cache = self._lightbar_read_cache
        if cache is None:
            cache = {}
            self._lightbar_read_cache = cache
        cache_key = str(getattr(node, "indicator_dir", "") or f"id:{id(node)}")
        now = time.monotonic()
        hit = cache.get(cache_key)
        if hit is not None and (now - hit[0]) < _LIGHTBAR_READ_TTL_SEC:
            return hit[1], hit[2]
        rgb: tuple[int, int, int] | None = None
        on = False
        with contextlib.suppress(Exception):
            rgb = _rgb_or_none(node.get_rgb())
        with contextlib.suppress(Exception):
            on = bool(node.is_on())
        if len(cache) > 64:
            cache.clear()
        cache[cache_key] = (now, rgb, on)
        return rgb, on

    def _player_slot_for(self, uniq: str | None) -> int | None:
        """Slot de sessão do controle `uniq` via identity_registry (COR-01/D9)."""
        if uniq is None or self.daemon is None:
            return None
        registry = getattr(self.daemon, "identity_registry", None)
        slot_for = getattr(registry, "slot_for", None) if registry is not None else None
        if not callable(slot_for):
            return None
        raw: Any = None
        with contextlib.suppress(Exception):
            raw = slot_for(uniq, assign=False)
        if isinstance(raw, int) and not isinstance(raw, bool):
            return raw
        return None

    @staticmethod
    def _inputs_from_state(state: Any) -> dict[str, Any] | None:
        """Inputs do PRIMÁRIO a partir do `state` do topo (`daemon._last_state`)."""
        try:
            return {
                "lx": int(state.raw_lx),
                "ly": int(state.raw_ly),
                "rx": int(state.raw_rx),
                "ry": int(state.raw_ry),
                "l2_raw": int(state.l2_raw),
                "r2_raw": int(state.r2_raw),
                "buttons": sorted(state.buttons_pressed),
            }
        except (AttributeError, TypeError, ValueError):
            return None

    @staticmethod
    def _inputs_from_snapshot(snap: Any) -> dict[str, Any] | None:
        """Inputs de um secundário a partir do `EvdevSnapshot` do reader dele."""
        try:
            return {
                "lx": int(snap.lx),
                "ly": int(snap.ly),
                "rx": int(snap.rx),
                "ry": int(snap.ry),
                "l2_raw": int(snap.l2_raw),
                "r2_raw": int(snap.r2_raw),
                "buttons": sorted(snap.buttons_pressed),
            }
        except (AttributeError, TypeError, ValueError):
            return None

    def _coop_live_snapshots(self) -> dict[str, Any]:
        """`CoopManager.live_snapshots()` com blindagem de dublês de teste."""
        coop = (
            getattr(self.daemon, "_coop_manager", None)
            if self.daemon is not None
            else None
        )
        live = getattr(coop, "live_snapshots", None) if coop is not None else None
        if not callable(live):
            return {}
        out: Any = None
        with contextlib.suppress(Exception):
            out = live()
        return out if isinstance(out, dict) else {}

    def _coop_vpads_by_uniq(self) -> dict[str, tuple[str | None, str | None]]:
        """MAC -> (vpad_backend, vpad_motivo) dos jogadores secundários (BT-03)."""
        coop = (
            getattr(self.daemon, "_coop_manager", None)
            if self.daemon is not None
            else None
        )
        players = getattr(coop, "_players", None) if coop is not None else None
        if not isinstance(players, dict):
            return {}
        out: dict[str, tuple[str | None, str | None]] = {}
        for mac, player in players.items():
            if not isinstance(mac, str) or mac.startswith("path:"):
                continue
            vpad = getattr(player, "vpad", None)
            if vpad is None:
                continue
            out[mac] = self._vpad_backend_motivo(vpad)
        return out

    @staticmethod
    def _vpad_backend_motivo(vpad: Any) -> tuple[str | None, str | None]:
        """(backend, motivo) de UM vpad — motivo só quando degradado (BT-03).

        Quem diz é `virtual_pad.motivo_da_degradacao` (o dono do `dedup_status` e do diário):
        máscara DualSense no uinput. O Xbox em uinput é escolha do usuário.
        """
        from hefesto_dualsense4unix.integrations.virtual_pad import motivo_da_degradacao

        raw_backend = getattr(vpad, "backend", None)
        backend = raw_backend if isinstance(raw_backend, str) and raw_backend else None
        return backend, motivo_da_degradacao(vpad)

    def _coop_vpad_de(self, uniq: str | None) -> Any:
        """O vpad vivo do jogador secundário `uniq`, ou ``None``."""
        coop = getattr(self.daemon, "_coop_manager", None) if self.daemon is not None else None
        players = getattr(coop, "_players", None) if coop is not None else None
        if not uniq or not isinstance(players, dict):
            return None
        return getattr(players.get(uniq), "vpad", None)

    def _o_que_o_jogo_ve_de(
        self, vpad: Any, uniq: str | None, transporte: object
    ) -> dict[str, Any] | None:
        """O que o jogo vê de `vpad`, com o movimento e as chaves do controle `uniq`.

        Nada aqui levanta: o pad que não sabe dizer (ou `None`) sai `None`.
        """
        from hefesto_dualsense4unix.core import roteador_de_movimento as roteador
        from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
        from hefesto_dualsense4unix.integrations.o_que_o_jogo_ve import o_que_o_jogo_ve

        store, sensores = getattr(self, "store", None), REGISTRO.estado(uniq)
        return o_que_o_jogo_ve(
            vpad, roteador.da_peca(store, uniq, roteador.ativo(store)),
            transporte=transporte,
            giro_ligado=sensores.giroscopio,
            acel_ligado=sensores.acelerometro,
            toque_ligado=REGISTRO.touchpad_ligado(uniq),
        )


    _AUTHORITY_VALUES = ("game", "daemon", "unknown")

    def _game_signal_snapshot(self) -> dict[str, Any]:
        """`game_signal` do `state_full` — quem manda na exibição AGORA.

        `daemon.display_authority` ('game'|'daemon'|'unknown', NUMA-01) é a MESMA leitura do
        merge-gate (`_game_wins`) e do `ExternalLedSync.tick`, nunca uma segunda fonte.
        ``degradado`` deriva dela: ``"unknown"`` JÁ é o estado fail-safe (detector cego, marker
        ilegível, sinal não fiado). O diagnóstico rico (`daemon._game_signal.diagnostico()`) é
        best-effort: hoje ``evidencia``/``motivo``/``desde`` ficam ``None``, salvo
        `motivo="sinal_nao_wireado"` sem `display_authority`; exceção nele não derruba o
        `state_full`.
        """
        authority_raw = (
            getattr(self.daemon, "display_authority", None)
            if self.daemon is not None
            else None
        )
        wired = isinstance(authority_raw, str) and authority_raw in self._AUTHORITY_VALUES
        authority = authority_raw if wired else "unknown"

        evidencia: str | None = None
        motivo: str | None = None if wired else "sinal_nao_wireado"
        desde: float | None = None
        degradado = authority == "unknown"

        diag_source = (
            getattr(self.daemon, "_game_signal", None)
            if self.daemon is not None
            else None
        )
        diagnostico = getattr(diag_source, "diagnostico", None)
        if callable(diagnostico):
            with contextlib.suppress(Exception):
                raw_diag = diagnostico()
                if isinstance(raw_diag, dict):
                    evidencia = _as_str_or_none(raw_diag.get("evidencia"))
                    motivo = _as_str_or_none(raw_diag.get("motivo")) or motivo
                    desde_raw = raw_diag.get("desde")
                    if isinstance(desde_raw, (int, float)) and not isinstance(
                        desde_raw, bool
                    ):
                        desde = float(desde_raw)
                    degradado_raw = raw_diag.get("degradado")
                    if isinstance(degradado_raw, bool):
                        degradado = degradado_raw

        return {
            "authority": authority,
            "evidencia": evidencia,
            "motivo": motivo,
            "desde": desde,
            "degradado": degradado,
        }


    _perfil_mudo_cache: tuple[tuple[str, str, str], list[dict[str, str]]] | None = None

    def _perfil_que_nao_entrou(self) -> list[dict[str, str]]:
        """Perfis que são regra DESTE jogo e mesmo assim não entraram.

        Só as regras do jogo em foco (`e_regra_deste_jogo`): sem a poda, com 14 perfis doze "não
        entrariam" a cada janela de desktop, por funcionar como deveriam. Fora de janela de jogo
        devolve `[]` sem tocar em disco (pagar `load_all_profiles()` a 10 Hz no desktop seria o
        poller cego já pago uma vez).
        """
        from hefesto_dualsense4unix.daemon.launch_env import steam_appid_from_wm_class

        def _txt(nome: str) -> str:
            valor = getattr(self.store, nome, None)
            return valor if isinstance(valor, str) else ""

        wm_class = _txt("window_detect_current_class")
        if steam_appid_from_wm_class(wm_class) is None:
            self._perfil_mudo_cache = None
            return []
        chave = (wm_class, _txt("window_detect_current_name"), _txt("window_detect_current_exe"))
        cache = self._perfil_mudo_cache
        if cache is not None and cache[0] == chave:
            return cache[1]

        from hefesto_dualsense4unix.profiles.loader import load_all_profiles
        from hefesto_dualsense4unix.profiles.porque_nao_entrou import (
            frase_do_perfil_que_nao_entrou,
            perfis_que_nao_entraram,
        )

        info = {"wm_class": chave[0], "wm_name": chave[1], "exe_basename": chave[2]}
        achados = [
            {"nome": a.nome, "frase": frase_do_perfil_que_nao_entrou(a)}
            for a in perfis_que_nao_entraram(info, load_all_profiles())
            if a.e_regra_deste_jogo
        ]
        self._perfil_mudo_cache = (chave, achados)
        return achados

    def _wrapper_used_now(self) -> bool | None:
        """`wrapper_used` do momento: True/False com jogo em foco, None sem."""
        from hefesto_dualsense4unix.daemon.launch_env import (
            steam_appid_from_wm_class,
            wrapper_used_state,
        )

        wm_class = getattr(self.store, "window_detect_last_class", None)
        appid = steam_appid_from_wm_class(
            wm_class if isinstance(wm_class, str) else None
        )
        if appid is None:
            self._wrapper_first_seen = None
            return None
        first = self._wrapper_first_seen
        if first is None or first[0] != appid:
            first = (appid, time.time())
            self._wrapper_first_seen = first
        return wrapper_used_state(
            appid=appid,
            marker=self._wrapper_marker_cached(),
            first_seen_epoch=first[1],
        )

    def _agendar_arming_do_launch(self) -> None:
        """Arma o modo do perfil quando o ping veio de um launch em curso."""
        if self.daemon is None:
            return
        marker = self._wrapper_marker_cached()
        if marker is None:
            return
        from hefesto_dualsense4unix.daemon.launch_env import LAUNCH_ARM_WINDOW_SEC

        if (time.time() - marker[1]) > LAUNCH_ARM_WINDOW_SEC:
            return
        if getattr(self.daemon, "_launch_armed_for", None) == marker:
            return
        with contextlib.suppress(RuntimeError):
            tarefa = asyncio.get_running_loop().create_task(self._armar_launch())
            self._launch_arm_task = tarefa
            tarefa.add_done_callback(lambda _t: setattr(self, "_launch_arm_task", None))

    async def _armar_launch(self) -> None:
        """Corpo do arming agendado — best-effort, nunca derruba o loop."""
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import arm_launch_profile

            resultado = arm_launch_profile(self.daemon)
            if isinstance(resultado, dict) and resultado.get("armado"):
                logger.info(
                    "launch_arm_pelo_ping_do_wrapper",
                    appid=resultado.get("appid"),
                    profile=resultado.get("profile"),
                    convergiu=resultado.get("convergiu"),
                    divergente=resultado.get("divergente"),
                )

    def _pontes_confirmadas_no_tique(self) -> dict[str, Any]:
        """As pontes confirmadas para o `state_full`, com cache TTL (BG-02, 25/08/2026).

        Evita uma SEGUNDA ida ao daemon por gesto na aba de perfil
        (`profiles_actions._buscar_as_pontes_confirmadas`). A leitura crua é a de
        `_pontes_confirmadas_seguro`, a mesma do `daemon.status`; o que muda é o teto
        (`_PONTES_CONFIRMADAS_TTL_SEC`: o tique paga cache, o gesto paga o disco).
        """
        now = time.monotonic()
        hit = self._pontes_confirmadas_cache
        if hit is not None and (now - hit[0]) < _PONTES_CONFIRMADAS_TTL_SEC:
            return hit[1]
        pontes = _pontes_confirmadas_seguro()
        self._pontes_confirmadas_cache = (now, pontes)
        return pontes

    def _wrapper_marker_cached(self) -> tuple[int, int] | None:
        """Marker `last_run` com cache TTL — o state_full roda a 10-20 Hz."""
        now = time.monotonic()
        hit = self._wrapper_marker_cache
        if hit is not None and (now - hit[0]) < _WRAPPER_MARKER_TTL_SEC:
            return hit[1]
        from hefesto_dualsense4unix.daemon.launch_env import read_last_run_marker

        marker = read_last_run_marker()
        self._wrapper_marker_cache = (now, marker)
        return marker

    def _no_do_vpad_cached(
        self, uniq: str | None, nome: str | None
    ) -> dict[str, Any]:
        """`{evdev, hidraw, ino, hidraw_ino}` do vpad, preso ao evento + `stat`
        (QUEM-SEGURA-O-NOSSO-NO-01).

        Muda só quando um nó nasce ou some em `/dev/input` ou nos `hidraw*` de `/dev`. Com o dono do
        evento armado vale até uma das duas gerações mudar (O-REPOUSO-ESPERA-O-EVENTO-01, família
        1); sem ele, o TTL. A raiz desviada da suíte cai no TTL; o `no_ainda_vale` barra o nó que
        mudou de inode.
        """
        chave = ((uniq or "").strip().casefold(), (nome or "").strip())
        if chave == ("", ""):
            return dict(NO_DESCONHECIDO)
        from hefesto_dualsense4unix.core import o_dono_do_evento as _ode
        from hefesto_dualsense4unix.integrations import no_do_vpad as _ndv

        dono = _ode.dono_armado()
        ficha = None if dono is None else dono.ficha(
            (_ndv.RAIZ_DEV_INPUT, _ode.NOMES), (_ndv.RAIZ_DEV, _ode.NOMES)
        )
        cache = self._no_do_vpad_cache
        if cache is None:
            cache = self._no_do_vpad_cache = {}
        hit, now = cache.get(chave), time.monotonic()
        valido = hit is not None and (
            hit[1] == ficha if ficha is not None else now - hit[0] < _NO_DO_VPAD_TTL_SEC
        )
        if hit is not None and valido and no_ainda_vale(hit[2]):
            return dict(hit[2])
        no = resolver_no_do_vpad(uniq=uniq, nome=nome)
        cache[chave] = (now, ficha, no)
        return dict(no)


    def _controles_sem_driver_payload(self) -> dict[str, Any]:
        """Quantos DualSense estão ligados e o sistema NÃO conseguiu adotar.

        Derivado do SISTEMA a cada leitura (`dualsense_sem_driver`), nunca de um campo paralelo:
        ESTADO-QUE-MENTE-01 (03/08, aberta neste payload) é o topo do `state_full` mantido ao lado
        da lista e a aba afirmando "Conectado · USB · 85%" com a mesa vazia. `ids` são nomes de
        diretório do sysfs (``0005:054C:0CE6.000F``, sem MAC) para casar com o
        `bt_rebind_orphans.sh`; a janela usa só a quantidade.
        """
        now = time.monotonic()
        hit = self._hid_orfaos_cache
        if hit is not None and (now - hit[0]) < _HID_ORFAOS_TTL_SEC:
            ids = hit[1]
        else:
            ids = dualsense_sem_driver()
            self._hid_orfaos_cache = (now, ids)
        return {"quantidade": len(ids), "ids": list(ids)}

    async def _handle_controller_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Lista os controles do daemon; opt-in `external` soma o inventário 8BIT-01.

        `controllers` segue com UMA entrada por controle físico ADOTADO
        (FEAT-DSX-MULTI-CONTROLLER-01); backend sem `describe_controllers` (FakeController) cai no
        resumo single-entry. 8BIT-01: o inventário dos EXTERNOS entra SÓ sob `{"external": true}`,
        FORA do event loop por `asyncio.to_thread` (pool default; o `daemon._executor` de 2 workers
        "hefesto-hid" atrasaria rumble/led, e `self.daemon` pode ser None); nunca no `state_full`.
        Resposta: chave `external` = lista de `{name, vid, pid, bus, uniq, driver, evdev_path,
        hidraw[, holders]}`; sem opt-in, payload byte-idêntico ao legado.

        **O NÚMERO ENTRA (UM-NUMERO-SO-01, 18/09/2026).** O ``index`` é a ordem dos HANDLES, não um
        número de jogador, e discordava do ``state_full`` (medido com quatro DualSense: índices
        0=vermelho 1=azul 2=roxo 3=branco; lâmpadas 2=vermelho 1=azul 3=roxo 4=branco).
        ``player_slot`` e ``numero`` saem pelos MESMOS donos do ``state_full``
        (:meth:`_player_slot_for`, :func:`_numero_de_exibicao`), leitura pura (``assign=False``);
        sem registry, ``player_slot`` é ``None`` e ``numero`` cai no ``index + 1``.
        """
        external_raw = params.get("external", False)
        if not isinstance(external_raw, bool):
            raise ValueError("controller.list: 'external' precisa ser boolean")
        describe = getattr(self.controller, "describe_controllers", None)
        if callable(describe):
            result: dict[str, Any] = {"controllers": describe()}
            self._carimbar_o_numero(result["controllers"])
        else:
            connected = self.controller.is_connected()
            result = {
                "controllers": [
                    {
                        "connected": connected,
                        "transport": self.controller.get_transport() if connected else None,
                    }
                ]
            }
        if external_raw:
            ds_count = sum(
                1
                for c in result["controllers"]
                if isinstance(c, dict) and c.get("connected")
            )
            registry = (
                getattr(self.daemon, "external_registry", None)
                if self.daemon is not None
                else None
            )
            peek = getattr(registry, "peek", None) if registry is not None else None
            resolver = peek if callable(peek) else None
            result["external"] = await asyncio.to_thread(
                _external_inventory, ds_count, resolver
            )
        return result

    def _indice_do_alvo(self, *, jogador: int | None, uniq: str | None) -> int:
        """Traduz «jogador N» / endereço para o índice dos handles (UM-NUMERO-SO-01).

        Mora no DAEMON porque as duas listas são dele (handles e fila de identidade); ver
        :meth:`_handle_controller_target_set`. RECUSA com frase quando o alvo não está na mesa: cair
        no broadcast pintaria os quatro no gesto de UM.
        """
        describe = getattr(self.controller, "describe_controllers", None)
        entradas = describe() if callable(describe) else []
        if not isinstance(entradas, list):
            entradas = []
        entradas = [e for e in entradas if isinstance(e, dict)]
        self._carimbar_o_numero(entradas)
        if uniq is not None:
            from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

            procurado = (norm_mac(uniq) or "").lower()
            for entrada in entradas:
                if (norm_mac(str(entrada.get("uniq") or "")) or "").lower() == procurado:
                    indice = entrada.get("index")
                    if isinstance(indice, int) and not isinstance(indice, bool):
                        return indice
            raise ValueError(
                "controller.target.set: este controle não está na mesa"
            )
        for entrada in entradas:
            if entrada.get("numero") == jogador:
                indice = entrada.get("index")
                if isinstance(indice, int) and not isinstance(indice, bool):
                    return indice
        na_mesa = sorted(
            n for n in (e.get("numero") for e in entradas) if isinstance(n, int)
        )
        raise ValueError(
            f"controller.target.set: não há Controle {jogador} na mesa"
            + (f" — há {na_mesa}" if na_mesa else "")
        )

    def _carimbar_o_numero(self, entries: Any) -> None:
        """Põe ``player_slot`` e ``numero`` em cada entrada (UM-NUMERO-SO-01), pelos donos do
        ``state_full``, sem conta nenhuma.

        ``numero`` é o carimbo que faltava: ``player_slot`` pode ser ``None`` e quem lê repetiria a
        regra de queda (como nasceram as três contas que a MESA-CHEIA-11 matou). Defensivo por
        inteiro: um registry dublado que levante não pode deixar a GUI, a CLI ou o applet sem mesa.
        """
        if not isinstance(entries, list):
            return
        for entrada in entries:
            if not isinstance(entrada, dict):
                continue
            with contextlib.suppress(Exception):
                if not isinstance(entrada.get("player_slot"), int) or isinstance(
                    entrada.get("player_slot"), bool
                ):
                    entrada["player_slot"] = self._player_slot_for(
                        entrada.get("uniq")
                    )
                entrada["numero"] = _numero_de_exibicao(entrada)

    async def _handle_controller_target_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Define o ALVO das ações de output (FEAT-DSX-CONTROLLER-SELECTOR-01)."""
        index = params.get("index")
        jogador = params.get("jogador")
        uniq = params.get("uniq")
        if index is not None and (isinstance(index, bool) or not isinstance(index, int)):
            raise ValueError("controller.target.set: 'index' precisa ser int ou null")
        if jogador is not None and (
            isinstance(jogador, bool) or not isinstance(jogador, int)
        ):
            raise ValueError("controller.target.set: 'jogador' precisa ser int ou null")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("controller.target.set: 'uniq' precisa ser texto ou null")
        dados = [p for p in ("index", "jogador", "uniq") if params.get(p) is not None]
        if len(dados) > 1:
            raise ValueError(
                "controller.target.set: mande UM alvo só — "
                + ", ".join(dados)
                + " vieram juntos"
            )
        if jogador is not None or uniq is not None:
            index = self._indice_do_alvo(jogador=jogador, uniq=uniq)
        setter = getattr(self.controller, "set_output_target", None)
        if not callable(setter):
            return {"status": "ok", "target_index": None}
        effective = setter(index)
        target_index = (
            effective if isinstance(effective, int) and not isinstance(effective, bool) else None
        )
        return {"status": "ok", "target_index": target_index}


    async def _handle_lightbar_reset(self, params: dict[str, Any]) -> dict[str, Any]:
        """Manda o Reset LED state (0x08) sob demanda — INSTRUMENTO de medição."""
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("lightbar.reset: 'uniq' precisa ser texto")
        enviar = getattr(self.controller, "enviar_release_leds", None)
        if not callable(enviar):
            raise RuntimeError("backend sem suporte a lightbar.reset")
        enviados = enviar(uniq=uniq)
        return {"status": "ok", "enviados": enviados}

    async def _handle_debug_player_leds(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga a escrita do LED de JOGADOR — INSTRUMENTO de eliminação."""
        suprimir = params.get("suprimir")
        if not isinstance(suprimir, bool):
            raise ValueError("debug.player_leds exige 'suprimir' booleano")
        alternar = getattr(self.controller, "suprimir_player_leds", None)
        if not callable(alternar):
            raise RuntimeError("backend sem suporte a debug.player_leds")
        return {"status": "ok", "suprimir": bool(alternar(suprimir))}

    async def _handle_rumble_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Fixa a vibração; RECUSA no Modo Nativo (FEAT-RUMBLE-POLICY-01 + NATIVO-RUMBLE-01).

        Persiste (weak, strong) brutos em daemon.config.rumble_active para o poll loop re-afirmar
        (_reassert_rumble); o multiplicador de política é aplicado antes do hardware, aqui e lá.
        MESA-CHEIA-05 (E0): o par leva o DONO (`rumble_active_uniq`), congelado agora, senão trocar
        o seletor levava o valor de um controle para outro.

        NATIVO-RUMBLE-01 (19/08/2026): no Modo Nativo o pedido é RECUSADO, com motivo
        (`daemon.subsystems.rumble`); a forma da resposta é a mesma (`weak`/`strong` dizem o que
        FICOU valendo), muda o `status` ("recusado") e o `desfecho`. BROADCAST-PROIBIDO-01
        (24/08/2026): alvo do seletor FORA da mesa também RECUSA, no mesmo molde
        (`app/ipc_bridge.py::rumble_set_checked` já o lê); antes o handler armava o `rumble_active`,
        chamava `set_rumble` e respondia "ok" enquanto o reassert de 5 Hz insistia num par que nunca
        chegou.
        """
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            MOTIVO_ALVO_FORA_DA_MESA,
            MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES,
            RUMBLE_APLICADO,
            RUMBLE_RECUSADO_ALVO_AUSENTE,
            RUMBLE_RECUSADO_MODO_NATIVO,
            escrever_com_a_forca,
            escrever_rumble_no_dono,
            fixar_par,
            modo_nativo_manda_nos_motores,
        )

        weak = params.get("weak")
        strong = params.get("strong")
        if not isinstance(weak, int) or not isinstance(strong, int):
            raise ValueError("rumble.set exige 'weak' e 'strong' inteiros 0-255")
        weak = max(0, min(255, weak))
        strong = max(0, min(255, strong))
        uniq = _uniq_do_rumble(params, "rumble.set")
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if modo_nativo_manda_nos_motores(self.daemon):
            par_de_pe = getattr(daemon_cfg, "rumble_active", None)
            logger.warning(
                "rumble_set_recusado_modo_nativo",
                weak=weak,
                strong=strong,
                par_de_pe=par_de_pe,
            )
            return {
                "status": "recusado",
                "desfecho": RUMBLE_RECUSADO_MODO_NATIVO,
                "motivo": MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES,
                "weak": par_de_pe[0] if par_de_pe else 0,
                "strong": par_de_pe[1] if par_de_pe else 0,
                "passthrough": par_de_pe is None,
            }
        if uniq is not None:
            eff_weak, eff_strong = apply_rumble_policy(self.daemon, weak, strong, uniq)
            mirar = getattr(self.controller, "set_rumble_for", None)
            if not callable(mirar) or not mirar(uniq, eff_weak, eff_strong):
                logger.warning(
                    "rumble_set_recusado_alvo_ausente", weak=weak, strong=strong,
                    alvo=uniq, par_de_pe=None,
                )
                return {
                    "status": "recusado",
                    "desfecho": RUMBLE_RECUSADO_ALVO_AUSENTE,
                    "motivo": MOTIVO_ALVO_FORA_DA_MESA,
                    "weak": 0,
                    "strong": 0,
                    "passthrough": True,
                }
            if daemon_cfg is not None:
                fixar_par(
                    daemon_cfg, uniq, weak, strong, time.monotonic(), so_este=True
                )
            return {
                "status": "ok",
                "desfecho": RUMBLE_APLICADO,
                "weak": weak,
                "strong": strong,
            }
        alvo_ausente_fn = getattr(self.controller, "alvo_de_output_ausente", None)
        alvo_ausente = alvo_ausente_fn() if callable(alvo_ausente_fn) else None
        if isinstance(alvo_ausente, str) and alvo_ausente:
            par_de_pe = getattr(daemon_cfg, "rumble_active", None)
            logger.warning(
                "rumble_set_recusado_alvo_ausente",
                weak=weak,
                strong=strong,
                alvo=alvo_ausente,
                par_de_pe=par_de_pe,
            )
            return {
                "status": "recusado",
                "desfecho": RUMBLE_RECUSADO_ALVO_AUSENTE,
                "motivo": MOTIVO_ALVO_FORA_DA_MESA,
                "weak": par_de_pe[0] if par_de_pe else 0,
                "strong": par_de_pe[1] if par_de_pe else 0,
                "passthrough": par_de_pe is None,
            }
        if daemon_cfg is not None:
            dono = uniq_do_alvo_de_output(self.controller)
            for largado in fixar_par(
                daemon_cfg, dono, weak, strong, time.monotonic(), so_este=False
            ):
                escrever_rumble_no_dono(self.controller, largado, 0, 0)
        escrever_com_a_forca(self.daemon, None, weak, strong)
        return {
            "status": "ok",
            "desfecho": RUMBLE_APLICADO,
            "weak": weak,
            "strong": strong,
        }

    async def _handle_rumble_stop(self, params: dict[str, Any]) -> dict[str, Any]:
        """Para o rumble e fixa (0, 0); no Modo Nativo SOLTA o par (NATIVO-RUMBLE-01)."""
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            MOTIVO_MODO_NATIVO_SOLTOU_O_PAR,
            RUMBLE_PARADO,
            RUMBLE_SOLTO_NO_MODO_NATIVO,
            escrever_rumble_no_dono,
            fixar_par,
            modo_nativo_manda_nos_motores,
            silenciar_dono_abandonado,
            soltar_todos,
        )

        uniq = _uniq_do_rumble(params, "rumble.stop")
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        dono_de_agora = uniq if uniq is not None else uniq_do_alvo_de_output(self.controller)
        if modo_nativo_manda_nos_motores(self.daemon):
            par_solto = getattr(daemon_cfg, "rumble_active", None)
            if daemon_cfg is not None:
                soltar_todos(daemon_cfg)
                daemon_cfg.rumble_dono_vibrando = None
            with contextlib.suppress(Exception):
                self.controller.set_rumble(weak=0, strong=0)
            logger.warning(
                "rumble_stop_soltou_o_par_no_modo_nativo",
                par_solto=par_solto,
            )
            return {
                "status": "ok",
                "desfecho": RUMBLE_SOLTO_NO_MODO_NATIVO,
                "motivo": MOTIVO_MODO_NATIVO_SOLTOU_O_PAR,
                "passthrough": True,
            }
        if uniq is not None:
            if daemon_cfg is not None:
                fixar_par(daemon_cfg, uniq, 0, 0, time.monotonic(), so_este=True)
            escrever_rumble_no_dono(self.controller, uniq, 0, 0)
            return {"status": "ok", "desfecho": RUMBLE_PARADO}
        if daemon_cfg is not None:
            par_velho = getattr(daemon_cfg, "rumble_active", None)
            dono_velho = getattr(daemon_cfg, "rumble_active_uniq", None)
            for largado in fixar_par(
                daemon_cfg, dono_de_agora, 0, 0, time.monotonic(), so_este=False
            ):
                escrever_rumble_no_dono(self.controller, largado, 0, 0)
            if par_velho is not None and any(par_velho):
                silenciar_dono_abandonado(self.controller, dono_velho, dono_de_agora)
            daemon_cfg.rumble_dono_vibrando = None
        self.controller.set_rumble(weak=0, strong=0)
        return {"status": "ok", "desfecho": RUMBLE_PARADO}

    async def _handle_rumble_passthrough(self, params: dict[str, Any]) -> dict[str, Any]:
        """Libera controle de rumble para jogo/UDP (BUG-RUMBLE-APPLY-IGNORED-01).

        Zera daemon.config.rumble_active (desativa a re-asserção do poll loop); o jogo retoma via
        UDP ou emulação Xbox360 e `rumble.set` retoma o manual. Params: ``enabled`` — True =
        passthrough; False = sem efeito. Com ``uniq`` solta só o par daquele controle; sem, todos. É
        o gesto que devolve a vibração ao jogo na aba Vibração, inclusive ao fim do teste dos
        motores.
        """
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            soltar_par,
            soltar_todos,
        )

        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("rumble.passthrough exige 'enabled' boolean")
        uniq = _uniq_do_rumble(params, "rumble.passthrough")
        if enabled:
            daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
            if daemon_cfg is not None:
                if uniq is not None:
                    soltar_par(daemon_cfg, uniq)
                else:
                    soltar_todos(daemon_cfg)
        return {"status": "ok", "passthrough": enabled}

    async def _handle_rumble_policy_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Altera política global de intensidade de rumble (FEAT-RUMBLE-POLICY-01)."""
        policy = params.get("policy")
        valid_policies = ("economia", "balanceado", "max", "auto", "custom")
        if policy not in valid_policies:
            raise ValueError(
                f"rumble.policy_set: policy deve ser um de {valid_policies}"
            )
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is None:
            raise ValueError("daemon não disponível para alterar política de rumble")
        daemon_cfg.rumble_policy = policy
        self._mark_rumble_policy_manual()
        logger.info("rumble_policy_alterada", policy=policy)
        return {"status": "ok", "policy": policy}

    async def _handle_rumble_policy_custom(self, params: dict[str, Any]) -> dict[str, Any]:
        """Define política "custom" com multiplicador explícito (FEAT-RUMBLE-POLICY-01)."""
        mult_raw = params.get("mult")
        try:
            mult = float(mult_raw)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ValueError("rumble.policy_custom: 'mult' precisa ser float") from exc
        if not (0.0 <= mult <= RUMBLE_CUSTOM_MULT_MAX):
            raise ValueError(
                f"rumble.policy_custom: mult fora de [0.0, {RUMBLE_CUSTOM_MULT_MAX}]: {mult}"
            )
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is None:
            raise ValueError("daemon não disponível para alterar política de rumble")
        daemon_cfg.rumble_policy = "custom"
        daemon_cfg.rumble_policy_custom_mult = mult
        self._mark_rumble_policy_manual()
        logger.info("rumble_policy_custom_definida", mult=mult)
        return {"status": "ok", "mult": mult}

    @staticmethod
    def _chave_de_peca_que_grava(alvo: str) -> str | None:
        """A chave sob a qual é SEGURO gravar no perfil, ou `None`."""
        from hefesto_dualsense4unix.profiles.manager import chave_de_peca_que_grava

        return chave_de_peca_que_grava(alvo)

    def _perfil_que_grava(self) -> str | None:
        """Em que perfil uma escolha POR PEÇA vai ser gravada — `None` quando nenhum
        (A-PERNA-QUE-FALTA-01, 11/09/2026).

        DUAS PERNAS, a segunda é a do boot deste daemon. Cura o que a `O-SALVAR-DA-JOGAR-01` mediu:
        com `self.store.active_profile` em `None` e os marcadores em disco valendo
        (`profiles_actions.perfil_que_esta_valendo`), os três gravadores respondiam `sem_perfil` sem
        gravar byte; o `gamepad.mask.set` o fazia CALADO (a tela acendia o chip e o `.json` ficava
        idêntico). A segunda perna usa `utils/session.resolve_boot_profile`, o MESMO resolvedor de
        `daemon/connection.py` (simetria com o boot, sem tocar `session.py`).

        **O nome do disco só vale se carregar:** o resolvedor só resolve NOMES, e um marker órfão
        viraria `FileNotFoundError` no meio de um clique em vez do `sem_perfil` calado de hoje.
        NUNCA LEVANTA: é rota de escrita de um clique (como o `nome_do_ativo` da interface).
        """
        from hefesto_dualsense4unix.profiles.manager import nome_do_perfil_que_grava

        return nome_do_perfil_que_grava(getattr(self.store, "active_profile", None))

    async def _handle_rumble_motores_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`rumble.motores.set` — a barra de CADA motor, no perfil (VIBRACAO-POR-MOTOR-01)."""
        from hefesto_dualsense4unix.daemon.ganho_da_haptica import GANHO
        from hefesto_dualsense4unix.profiles.formas_de_haptica import (
            ESCOLHAS as FORMAS_DE_HAPTICA,
        )
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
            chave_no_perfil,
            gravar_pelo_gesto,
        )
        from hefesto_dualsense4unix.profiles.schema import (
            ESCOLHAS_DE_IMERSAO,
            HAPTICA_PCT_MAX,
            HAPTICA_PCT_PADRAO,
            MOTOR_PCT_MAX,
            ControllerOverrides,
            ControllerRumbleOverride,
            pct_da_haptica,
        )

        pedidos: dict[str, int] = {}
        for campo, chave_ipc, teto in (
            ("motor_forte_pct", "forte_pct", MOTOR_PCT_MAX),
            ("motor_fraco_pct", "fraco_pct", MOTOR_PCT_MAX),
            ("haptica_pct", "haptica_pct", HAPTICA_PCT_MAX),
        ):
            if chave_ipc not in params:
                continue
            valor = params.get(chave_ipc)
            if not isinstance(valor, int) or isinstance(valor, bool):
                raise ValueError(
                    f"rumble.motores.set: '{chave_ipc}' precisa ser inteiro 0-{teto}"
                )
            pedidos[campo] = valor
        escolhas: dict[str, str] = {}
        for campo, vocabulario in (
            ("efeito_haptico", FORMAS_DE_HAPTICA),
            ("efeito_imersao", ESCOLHAS_DE_IMERSAO),
        ):
            if campo not in params:
                continue
            valor = params.get(campo)
            if not isinstance(valor, str) or valor not in vocabulario:
                raise ValueError(
                    f"rumble.motores.set: '{campo}' precisa ser uma de {', '.join(vocabulario)}"
                )
            escolhas[campo] = valor
        if not pedidos and not escolhas:
            raise ValueError(
                "rumble.motores.set exige ao menos um de 'forte_pct', 'fraco_pct', "
                "'haptica_pct', 'efeito_haptico' ou 'efeito_imersao' — campo omitido NÃO mexe "
                "naquela barra"
            )
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("rumble.motores.set: 'uniq' precisa ser string ou omitido")
        ControllerRumbleOverride.model_validate({**pedidos, **escolhas})

        alvo = uniq or self._uniq_do_primario()
        if not alvo:
            return {
                "status": "sem_controle",
                "uniq": None,
                "motivo": (
                    "não há controle na mesa para guardar a barra de motor — a "
                    "barra é POR PEÇA, e cair no primeiro da lista é o que "
                    "faria a mesa cheia escrever sempre no mesmo"
                ),
            }
        chave = self._chave_de_peca_que_grava(alvo)
        if not chave:
            return {
                "status": "sem_endereco",
                "uniq": alvo,
                "motivo": (
                    f"{alvo!r} não é um endereço de rádio de uma peça de "
                    "plástico — sem MAC não há como mirar uma peça, e gravar "
                    "sob uma chave que o motor nunca casa faria a escolha "
                    "sumir calada"
                ),
            }
        nome = self._perfil_que_grava() or ""
        visto: dict[str, Any] = {}

        def _com_as_barras(perfil: Any) -> Any:
            atuais = dict(perfil.controllers or {})
            original = chave_no_perfil(perfil, chave)
            dele = atuais.get(original) or ControllerOverrides()
            antes = dele.rumble
            campos: dict[str, Any] = (
                dict(antes.model_dump(exclude_unset=True)) if antes is not None else {}
            )
            for campo, valor in pedidos.items():
                padrao = HAPTICA_PCT_PADRAO if campo == "haptica_pct" else MOTOR_PCT_PADRAO
                if valor == padrao:
                    campos.pop(campo, None)
                else:
                    campos[campo] = valor
            for campo, escolha in escolhas.items():
                if escolha == "do_estilo":
                    campos.pop(campo, None)
                else:
                    campos[campo] = escolha
            novo = ControllerRumbleOverride.model_validate(campos) if campos else None
            visto["novo"] = novo
            antes_campos = (
                dict(antes.model_dump(exclude_unset=True)) if antes is not None else None
            )
            if antes_campos == (dict(campos) if campos else None):
                return None
            visto["gravado"] = True
            atuais[original] = dele.model_copy(update={"rumble": novo})
            return perfil.model_copy(update={"controllers": atuais})

        onde, _ = gravar_pelo_gesto("vibracao", nome, _com_as_barras, uniq=chave,
                                    origem="rumble.motores.set")
        efetivos = self._pcts_efetivos(visto.get("novo"))
        haptica = pct_da_haptica(visto.get("novo"))
        efeitos = {
            campo: getattr(visto.get("novo"), campo, None) or "do_estilo"
            for campo in ("efeito_haptico", "efeito_imersao")
        }
        if not visto.get("gravado"):
            logger.info("rumble_motores_sem_mudanca", uniq=chave, perfil=nome, onde=onde)
            return {
                "status": "ok",
                "uniq": alvo,
                "perfil": nome or None,
                "onde": onde,
                "gravado": False,
                "forte_pct": efetivos[0],
                "fraco_pct": efetivos[1],
                "haptica_pct": haptica,
                **efeitos,
            }
        if self.daemon is not None:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                esquecer_motores_do_perfil,
            )

            esquecer_motores_do_perfil(self.daemon)
        GANHO.ler_do_daemon(self.daemon, forcar=True)
        logger.info(
            "rumble_motores_gravados",
            uniq=chave,
            perfil=nome,
            onde=onde,
            forte_pct=efetivos[0],
            fraco_pct=efetivos[1],
            haptica_pct=haptica,
        )
        return {
            "status": "ok",
            "uniq": alvo,
            "perfil": nome or None,
            "onde": onde,
            "gravado": True,
            "forte_pct": efetivos[0],
            "fraco_pct": efetivos[1],
            "haptica_pct": haptica,
            **efeitos,
        }

    async def _handle_sensor_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`sensor.set` — desliga giroscópio, acelerômetro e touchpad DE VERDADE, por controle.

        Params: ``{uniq?, giroscopio?, acelerometro?, touchpad?: "ligado"|"desligado"}``;
        campo omitido NÃO mexe naquele sensor. Três escritas, nesta ordem: o registro vivo, o perfil
        (``ControllerOverrides.sensores``) e o pedido de grab ao ``SensorHub``. A resposta diz o
        alcance (``alcance``, ``touchpad_alcance``): a história está em
        docs/research/o-porque-dos-modulos.md, seção «O sensor.set».
        """
        from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
        from hefesto_dualsense4unix.profiles.schema import (
            ControllerOverrides,
            ControllerSensoresOverride,
        )

        pedidos: dict[str, bool] = {}
        for campo in ("giroscopio", "acelerometro"):
            if campo not in params:
                continue
            valor = params.get(campo)
            if not isinstance(valor, bool):
                raise ValueError(
                    f"sensor.set: '{campo}' precisa ser boolean — true liga o "
                    "sensor para o jogo, false o desliga"
                )
            pedidos[campo] = valor
        toque = params.get("touchpad")
        if "touchpad" in params and toque not in ("ligado", "desligado"):
            raise ValueError("sensor.set: 'touchpad' precisa ser 'ligado' ou 'desligado'")
        if not pedidos and toque is None:
            raise ValueError(
                "sensor.set exige ao menos um de 'giroscopio', 'acelerometro' ou "
                "'touchpad' — campo omitido NÃO mexe naquele sensor"
            )
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("sensor.set: 'uniq' precisa ser string ou omitido")

        alvo = uniq or self._uniq_do_primario()
        if not alvo:
            return {
                "status": "sem_controle",
                "uniq": None,
                "motivo": (
                    "não há controle na mesa para desligar sensor — o "
                    "interruptor é POR PEÇA, e cair no primeiro da lista é o "
                    "que faria a mesa cheia desligar sempre o mesmo giro"
                ),
            }
        chave = self._chave_de_peca_que_grava(alvo)
        if not chave:
            return {
                "status": "sem_endereco",
                "uniq": alvo,
                "motivo": (
                    f"{alvo!r} não é um endereço de rádio de uma peça de "
                    "plástico — sem MAC não há como mirar um sensor, e "
                    "desligar sob uma chave que o report nunca casa faria a "
                    "escolha sumir calada"
                ),
            }

        estado = REGISTRO.definir(
            chave,
            giroscopio=pedidos.get("giroscopio"),
            acelerometro=pedidos.get("acelerometro"),
        )
        if toque is not None:
            REGISTRO.definir_touchpad(chave, ligado=toque == "ligado")

        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
            chave_no_perfil,
            gravar_pelo_gesto,
        )

        nome = self._perfil_que_grava() or ""
        visto: dict[str, Any] = {}

        def _com_os_sensores(perfil: Any) -> Any:
            atuais = dict(perfil.controllers or {})
            original = chave_no_perfil(perfil, chave)
            dele = atuais.get(original) or ControllerOverrides()
            antes = dele.sensores
            campos = dict(antes.model_dump(exclude_unset=True)) if antes else {}
            for campo, valor in pedidos.items():
                if valor:
                    campos.pop(campo, None)
                else:
                    campos[campo] = False
            if toque == "desligado":
                campos["touchpad"] = "desligado"
            elif toque is not None:
                campos.pop("touchpad", None)
            novo = ControllerSensoresOverride.model_validate(campos) if campos else None
            antes_campos = dict(antes.model_dump(exclude_unset=True)) if antes else None
            if antes_campos == (dict(campos) if campos else None):
                return None
            visto["gravado"] = True
            atuais[original] = dele.model_copy(update={"sensores": novo})
            return perfil.model_copy(update={"controllers": atuais})

        onde, _ = gravar_pelo_gesto("sensores", nome, _com_os_sensores, uniq=chave,
                                    origem="sensor.set")
        gravado = bool(visto.get("gravado"))

        hub = self._garantir_sensor_hub()
        with contextlib.suppress(Exception):
            hub.reconciliar()
        grab = self._grab_do_movimento(hub, chave)
        pergunta_do_toque = getattr(hub, "grab_do_toque", None)
        grab_do_toque = pergunta_do_toque(chave) if callable(pergunta_do_toque) else "desconhecido"

        nativo = bool(
            self.daemon is not None and getattr(self.daemon, "is_native_mode", bool)()
        )
        alcance = {
            "report": "nao_se_aplica" if nativo else "aplicado",
            "evdev": grab,
        }
        ressalva: str | None = None
        if nativo and not estado.tudo_ligado:
            ressalva = (
                "Modo Nativo: o jogo lê o movimento pelo hidraw do controle "
                "FÍSICO, e nesse caminho o daemon não escreve byte nenhum — o "
                "kernel entrega o report direto. O sensor fica escondido de "
                "quem lê o nó evdev, e continua chegando a quem lê pelo hidraw "
                "(o SDL lê por ali). Para desligar de verdade, o Modo Virtual."
            )
        elif not estado.tudo_ligado and grab not in ("held", "pending"):
            ressalva = (
                f"o nó de movimento não ficou exclusivo (grab={grab}): o jogo "
                "não recebe mais o sensor pelo vpad, mas quem ler o nó evdev "
                "do controle físico ainda o vê"
            )

        logger.info(
            "sensor_set",
            uniq=chave,
            perfil=nome,
            onde=onde,
            gravado=gravado,
            giroscopio=estado.giroscopio,
            acelerometro=estado.acelerometro,
            grab=grab,
            nativo=nativo,
        )
        return {
            "status": "ok",
            "uniq": alvo,
            "perfil": nome or None,
            "onde": onde,
            "gravado": gravado,
            "giroscopio": estado.giroscopio,
            "acelerometro": estado.acelerometro,
            "alcance": alcance,
            "ressalva": ressalva,
            "touchpad": "ligado" if REGISTRO.touchpad_ligado(chave) else "desligado",
            "touchpad_alcance": _alcance_do_toque(self.daemon),
            "touchpad_grab": grab_do_toque,
        }

    @staticmethod
    def _pcts_efetivos(rumble: Any) -> tuple[int, int]:
        """`(forte_pct, fraco_pct)` que passam a valer — 100 quando sem opinião."""
        from hefesto_dualsense4unix.profiles.schema import pcts_dos_motores

        return pcts_dos_motores(rumble)

    def _mark_rumble_policy_manual(self) -> None:
        """Propaga o gesto manual de política de rumble ao daemon."""
        mark_manual = getattr(self.daemon, "mark_rumble_policy_manual", None)
        if callable(mark_manual):
            mark_manual()


    async def _handle_daemon_reload(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica overrides parciais de config em runtime (REFACTOR-DAEMON-RELOAD-01)."""
        if self.daemon is None:
            raise ValueError("daemon não disponível para reload")

        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        overrides = _sem_os_campos_aposentados(params.get("config_overrides", {}))
        if not isinstance(overrides, dict):
            raise ValueError("daemon.reload: 'config_overrides' deve ser objeto")

        known_fields = set(DaemonConfig.__dataclass_fields__)
        unknown = set(overrides) - known_fields
        if unknown:
            raise ValueError(
                f"daemon.reload: campos desconhecidos em config_overrides: {sorted(unknown)}"
            )

        new_cfg = replace(self.daemon.config, **overrides)
        self.daemon.reload_config(new_cfg)
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import (
                materialize_launch_env,
            )

            materialize_launch_env(self.daemon)
        return {"status": "ok", "config": _config_que_viaja(new_cfg)}

    async def _handle_launch_env_refresh(
        self, _params: dict[str, Any]
    ) -> dict[str, Any]:
        """Rematerializa as envs de launch do wrapper (DEDUP-04) sob demanda.

        Cobre o que os hooks de transição NÃO cobrem: criar/editar/apagar perfil pela GUI grava
        DIRETO no disco e o `steam_app_<appid>.env` de antecipação ficaria ausente/rançoso na
        PRIMEIRA sessão do jogo novo (IGNORE congelado, zero controles). A GUI chama best-effort
        após save/delete/import; daemon dublado sem materialização responde `failed`.
        """
        if self.daemon is None:
            return {"status": "failed"}
        from hefesto_dualsense4unix.daemon.launch_env import materialize_launch_env

        materialize_launch_env(self.daemon)
        return {"status": "ok"}

    async def _handle_speaker_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`speaker.set` — volume/mudo/devolução do alto-falante (D4 + SOM-02).

        Params: ``{volume?: 0-255, muted?: bool, rota?: 0-3, fonte?: "mix"|"sfx", release?: bool,
        uniq?: str}``; `uniq` omitido = o primário, **menos para a `fonte`**, que é por controle e
        recusa o pedido sem endereço.

        DUAS CAMADAS: a ``rota`` é o byte do firmware (por onde o PLÁSTICO toca) e a ``fonte`` é o
        PipeWire (o que ENTRA no nó). Pedido só de ``fonte`` não toma a posse nem manda byte; a
        resposta traz ``fonte`` com o que ficou valendo, ausente se ninguém a executou.

        O controle não lê esse registrador, então escrever é o ÚNICO jeito de conhecer o volume: a
        primeira chamada toma a posse dos bytes (antes, o firmware é o dono; AUDIO-OWNER-01) e só
        então o `daemon.state_full` traz `speaker`. `release: true` (SOM-02/E3) DEVOLVE a posse: os
        bytes voltam a "sem dono", o flag0 sai zerado, `speaker` some; devolve o CONTROLE, não o
        valor (o firmware conserva o último). `release` é chave própria porque aqui `muted` é
        opcional (ausente = não mexer), e `muted: null` daria duas leituras ao `{}`. PRECEDÊNCIA
        (SOM-02, entrega 3): `release` junto de `volume`/`muted` é ERRO DE VALIDAÇÃO, não ordem com
        vencedor.
        """
        volume = params.get("volume")
        muted = params.get("muted")
        release = params.get("release")
        uniq = params.get("uniq")
        rota = params.get("rota")
        fonte = params.get("fonte")
        if rota is not None:
            if not isinstance(rota, int) or isinstance(rota, bool):
                raise ValueError("speaker.set: 'rota' precisa ser int 0-3")
            if not 0 <= rota <= 3:
                raise ValueError(
                    "speaker.set: 'rota' fora de 0-3 (0=estéreo no fone, "
                    "1=mono no fone, 2=L no fone e R no alto-falante, "
                    "3=só no alto-falante)"
                )
        if volume is not None:
            if not isinstance(volume, int) or isinstance(volume, bool):
                raise ValueError("speaker.set: 'volume' precisa ser int 0-255")
            if not 0 <= volume <= 255:
                raise ValueError("speaker.set: 'volume' fora de 0-255")
        if muted is not None and not isinstance(muted, bool):
            raise ValueError("speaker.set: 'muted' precisa ser boolean ou omitido")
        if release is not None and not isinstance(release, bool):
            raise ValueError("speaker.set: 'release' precisa ser boolean ou omitido")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("speaker.set: 'uniq' precisa ser string ou omitido")
        if fonte is not None:
            from hefesto_dualsense4unix.integrations.alto_falante_bt import (
                FONTE_MIX,
                FONTE_SFX,
            )

            if not isinstance(fonte, str) or fonte not in (FONTE_MIX, FONTE_SFX):
                raise ValueError(
                    f"speaker.set: 'fonte' precisa ser {FONTE_SFX!r} (só o que "
                    f"o jogo mandar para este controle) ou {FONTE_MIX!r} (todo "
                    f"o som da máquina cai nele também)"
                )
        if release and (
            volume is not None
            or muted is not None
            or rota is not None
            or fonte is not None
        ):
            raise ValueError(
                "speaker.set: 'release' não combina com 'volume'/'muted' — "
                "devolver a posse e mandar um valor na mesma chamada não tem "
                "significado honesto; mande dois pedidos"
            )

        if release:
            return await self._speaker_release(uniq)

        fonte_feita: str | None = None
        if fonte is not None:
            fonte_feita = self._speaker_fonte(uniq, str(fonte))

        if volume is None and muted is None and rota is None:
            corpo: dict[str, Any] = {
                "status": "ok" if fonte_feita else "sem_controle",
                "speaker": self._speaker_estado(uniq),
            }
            if fonte_feita:
                corpo["fonte"] = fonte_feita
            return corpo

        setter = getattr(self.controller, "set_speaker_volume", None)
        if not callable(setter):
            raise ValueError("backend sem suporte a volume de alto-falante")

        sem_volume_conhecido = self._speaker_estado(uniq) is None
        if muted is not None and volume is None and sem_volume_conhecido:
            raise ValueError(
                "speaker.set: 'muted' sem volume conhecido — mande um 'volume' "
                "antes (mudo como primeira escrita tranca o alto-falante em "
                "zero e o próprio mudo não o solta)"
            )
        extras: dict[str, Any] = {} if rota is None else {"rota": rota}
        ok = bool(setter(volume, muted=muted, uniq=uniq, **extras))
        corpo = {
            "status": "ok" if ok else "sem_controle",
            "speaker": self._speaker_estado(uniq),
        }
        if fonte_feita:
            corpo["fonte"] = fonte_feita
        return corpo

    def _speaker_fonte(self, uniq: str | None, fonte: str) -> str | None:
        """Entrega a `fonte` ao dono do nó, e devolve a que ficou valendo."""
        sub = getattr(self.daemon, "_alto_falante_subsystem", None)
        escolher = getattr(sub, "escolher_a_fonte", None)
        valendo = getattr(sub, "fonte_escolhida", None)
        if not uniq or not callable(escolher) or not callable(valendo):
            return None
        try:
            if not escolher(uniq, fonte):
                return None
            return str(valendo(uniq))
        except Exception:  # pragma: no cover
            logger.debug("som_fonte_nao_escolhida", uniq=uniq, exc_info=True)
            return None

    async def _speaker_release(self, uniq: str | None) -> dict[str, Any]:
        """Devolve a posse dos bytes de volume (SOM-02/E3) e relê o estado.

        A releitura sai `None` (`speaker_state_for` sem dono), e o `_merge_audio` só publica
        dicionário: a chave `speaker` SOME do `daemon.state_full` e a janela volta a "não ajustado"
        no tique seguinte.
        """
        soltar = getattr(self.controller, "release_speaker_volume", None)
        if not callable(soltar):
            raise ValueError("backend sem suporte a devolução do alto-falante")
        ok = bool(soltar(uniq=uniq))
        return {
            "status": "ok" if ok else "sem_controle",
            "speaker": self._speaker_estado(uniq),
        }

    def _speaker_estado(self, uniq: str | None) -> dict[str, Any] | None:
        """Leitura tolerante do `speaker_state_for` (None = sem volume conhecido); `getattr`
        defensivo (FakeController e daemon antigo não têm o método)."""
        leitor = getattr(self.controller, "speaker_state_for", None)
        if not callable(leitor):
            return None
        estado: Any = None
        with contextlib.suppress(Exception):
            estado = leitor(uniq)
        return estado if isinstance(estado, dict) else None


    async def _handle_mic_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`mic.set` — mudo do microfone no FIRMWARE do controle (MIC-USB-01).

        Params: ``{muted: bool|null, uniq?: str}``; `uniq` escolhe o controle (mesmo roteamento
        por-uniq de `led.set`/`rumble.set`), omitido = o primário. Expõe o `set_microphone_mute` do
        AUDIO-OWNER-01: em 25/07 o microfone estava mudo por TRÊS camadas (o `mute:true` do
        WirePlumber, o perfil da placa preso no iec958 — ambos no `doctor --fix` —, e o firmware) e
        o único jeito de desmutar era o botão físico.

        OS TRÊS ESTADOS (`False` não é "não mexer"):

          - ``muted: true``: MUTA, o bit `MIC_MUTE` ligado (com `POWER_SAVE_CONTROL_ENABLE`) em todo
            report;
          - ``muted: false``: DESMUTA, o mesmo campo com o bit apagado; é uma ORDEM e o botão físico
            deixa de mandar;
          - ``muted: null``: DEVOLVE A POSSE ao `hid-playstation` (o bit de validação sai apagado e
            o firmware conserva o que tinha).

        Confundir o segundo com o terceiro foi o defeito dos dois escritores do byte (commit
        `3d9bb7e`: o keepalive mandava `common[9]=0x00` a 60 Hz por cima do kernel). Por isso
        `muted` é OBRIGATÓRIA: omitir levanta erro, não vira `False` silencioso.

        A resposta traz o estado LIDO (`audio`, do report de INPUT, que pode estar um report atrás)
        e a posse (`mic_mudo_desejado`). Fiação da GUI (não feita nesta sprint): o botão da aba
        Status chama `app.ipc_bridge.mic_set(...)` em `app/actions/status_actions.py` e relê
        `daemon.state_full`, nunca guarda o valor mandado como leitura.
        """
        if "muted" not in params:
            raise ValueError(
                "mic.set: 'muted' é obrigatório — true muta, false desmuta, "
                "null devolve a posse ao kernel"
            )
        muted = params.get("muted")
        uniq = params.get("uniq")
        if muted is not None and not isinstance(muted, bool):
            raise ValueError("mic.set: 'muted' precisa ser boolean ou null")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("mic.set: 'uniq' precisa ser string ou omitido")
        setter = getattr(self.controller, "set_microphone_mute", None)
        if not callable(setter):
            raise ValueError("backend sem suporte a mudo de microfone")
        ok = bool(setter(muted, uniq=uniq))
        estado: Any = None
        leitor = getattr(self.controller, "audio_status_for", None)
        if callable(leitor):
            with contextlib.suppress(Exception):
                estado = leitor(uniq)
        return {
            "status": "ok" if ok else "sem_controle",
            "audio": estado if isinstance(estado, dict) else None,
            "mic_mudo_desejado": muted,
        }

    async def _handle_mic_canal_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`mic.canal.set` — O ATO INTEIRO do microfone (MICROFONE-UM-ATO-01)."""
        if "ligado" not in params:
            raise ValueError(
                "mic.canal.set: 'ligado' é obrigatório — true liga o microfone "
                "deste controle no canal dele, false o desliga"
            )
        ligado = params.get("ligado")
        if not isinstance(ligado, bool):
            raise ValueError("mic.canal.set: 'ligado' precisa ser boolean")
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("mic.canal.set: 'uniq' precisa ser string ou omitido")
        if self.daemon is None:
            raise RuntimeError("daemon indisponível")
        alvo = uniq or self._uniq_do_primario()
        if not alvo:
            return {
                "status": "sem_controle",
                "uniq": None,
                "ligado": ligado,
                "motivo": (
                    "não há controle na mesa para ligar o microfone — o ato "
                    "precisa de um endereço, e cair no primeiro da lista é o "
                    "que faria a mesa cheia eleger sempre o mesmo"
                ),
            }
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import ligar_o_microfone

        ato = await ligar_o_microfone(self.daemon, alvo, ligado=ligado)
        return ato.como_corpo()

    def _uniq_do_alvo_de_saida(self) -> str | None:
        """O endereço do alvo de `controller.target.set`, ou `None` para TODOS: o dono único de *"o
        usuário apontou para alguém?"*.

        Separado de :meth:`_uniq_do_primario` porque os chamadores querem quedas DIFERENTES: os atos
        por controle (`sensor.set`, `mic.canal.set`, `rumble.motores.set`) caem no primário; o
        `mic.volume.set` cai na ROTA GLOBAL do servidor de som (a fonte padrão do sistema), e
        trocá-la pelo primário mudaria o gesto de quem tem um controle só.
        """
        alvo = getattr(self.controller, "get_output_target_uniq", None)
        if not callable(alvo):
            return None
        with contextlib.suppress(Exception):
            escolhido = alvo()
            if isinstance(escolhido, str) and escolhido:
                return escolhido
        return None

    def _uniq_do_primario(self) -> str | None:
        """Em quem o ato cai quando ela não disse o endereço (UM-NUMERO-SO-01, 18/09/2026).

        Ordem do mais explícito ao menos: o `uniq` do próprio pedido (resolvido pelo chamador), o
        alvo de saída DESTA sessão, e só então o primário (a conveniência de quem tem um controle
        só). Antes havia DUAS línguas de alvo: `led.set`/`rumble.set`/`trigger.*`/ `speaker.set`
        obedeciam ao seletor, e `sensor.set`/`mic.canal.set`/`rumble.motores.set` iam SEMPRE ao
        primário (medido com quatro DualSense: o mesmo `uniq` quatro vezes). Resolver aqui mantém
        uma regra por ato e curou os três chamadores de uma vez.
        """
        escolhido = self._uniq_do_alvo_de_saida()
        if escolhido:
            return escolhido
        listar = getattr(self.controller, "describe_controllers", None)
        if not callable(listar):
            return None
        with contextlib.suppress(Exception):
            for entrada in listar() or []:
                if not isinstance(entrada, dict):
                    continue
                if not entrada.get("connected"):
                    continue
                endereco = entrada.get("uniq")
                if isinstance(endereco, str) and endereco:
                    return endereco
        return None

    async def _handle_mic_led_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`mic.led.set` — o LED do botão de mudo, e a DEVOLUÇÃO da posse dele.

        Params: ``{aceso: bool|null, uniq?: str}``, no molde do `mic.set`; `uniq` omitido = o
        primário. MIC-DA-MESA-ELEICAO-01 (01/09/2026).

        `common[8]` (LED) e `common[9]` (mudo) são campos SEPARADOS, com bits próprios
        (`MIC_MUTE_LED_CONTROL_ENABLE` 0x01, `POWER_SAVE_CONTROL_ENABLE` 0x02): acender o LED **não
        muta nada**, então a inversão pedida (*"aceso = o mic está funcionando"*) não escreve no
        byte do mudo, e as três recusas medidas (BT-E-VPAD-01, MIC-BT-DONO-01, MIC-DOIS-DONOS-01),
        todas sobre o `common[9]`, ficam inteiras.

        OS TRÊS ESTADOS (`false` NÃO é `null`):

          - ``aceso: true``: ACENDE e a posse do byte passa a ser nossa;
          - ``aceso: false``: APAGA, uma ORDEM; o kernel deixa de mandar na luz;
          - ``aceso: null``: DEVOLVE A POSSE ao `hid-playstation` (`mute_button_led = ds->mic_muted`
            a cada borda, `hid-playstation.c:1538-1540`); o bit `0x01` do flag1 sai apagado. **Antes
            de soltar, a luz é REPINTADA com o mudo de fato** (LUZ-DO-MIC-01 §2): o kernel só
            repinta na borda do botão e a luz ficava presa (*"ambos tão ligados. e ficaram."*). Quem
            repinta é o backend (`_repintar_antes_de_soltar`), para os três caminhos da devolução
            (este IPC, `mic led-release`, desligamento) ganharem por um lugar.

        `aceso` é OBRIGATÓRIA (omitir levanta erro, não vira `False` silencioso; o defeito do commit
        `3d9bb7e` no byte vizinho). É a PORTA DE EMERGÊNCIA da inversão: sem ela só desligar o
        controle devolvia a luz ao kernel.
        """
        if "aceso" not in params:
            raise ValueError(
                "mic.led.set: 'aceso' é obrigatório — true acende, false apaga, "
                "null devolve a posse ao kernel"
            )
        aceso = params.get("aceso")
        uniq = params.get("uniq")
        if aceso is not None and not isinstance(aceso, int):
            raise ValueError(
                "mic.led.set: 'aceso' precisa ser boolean, int 0-255 ou null"
            )
        if isinstance(aceso, int) and not isinstance(aceso, bool) and not 0 <= aceso <= 255:
            raise ValueError("mic.led.set: 'aceso' como nível vai de 0 a 255")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("mic.led.set: 'uniq' precisa ser string ou omitido")
        setter = getattr(self.controller, "set_microphone_led", None)
        if not callable(setter):
            raise ValueError("backend sem suporte a LED de microfone")
        ok = bool(setter(aceso, uniq=uniq))
        return {"status": "ok" if ok else "sem_controle", "aceso": aceso}

    async def _handle_mic_volume_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """`mic.volume.set` — volume da CAPTURA no sistema (MIC-VOLUME-01).

        Params: ``{volume: int 0-100, uniq?: str}``.

        **Camada diferente do `mic.set`.** Aquele mexe no MUDO do firmware (camada 3: apaga a luz e
        tira o botão físico); este mexe no ganho da FONTE no PipeWire (camada 1) e não toca no
        firmware, no botão nem na luz. **Universal** (*"independente de saber se tá via bt ou via
        cabo, o app deve ser inteligente pra saber qual caminho usar"*): a fonte de captura vale nos
        dois transportes e quem a acha é `integrations/audio_control.fonte_de_captura_do_controle`
        (no cabo, o source ALSA; no rádio, o da ponte de áudio).

        **FATO SUBSTITUÍDO EM 09/09/2026:** o registrador de ganho EXISTE, é o `common[6]`
        (`mic_volume`, `0x0 - 0x40`, nomeado pelo `hid-playstation`), e a bancada mediu a captura
        mudando no cabo (`docs/data/ensaios.csv`, `folha-mic-volume-o-byte-age-cabo-0909`). A fonte
        no sistema segue como o degrau universal e o byte do aparelho é medido só no cabo; por isso
        os dois, nesta ordem.

        **`sem_fonte` é resposta, não falha:** por Bluetooth sem a ponte não há fonte de captura
        (16/08/2026: `pactl list cards` traz só as duas placas); a interface deixa o controle
        INSENSÍVEL com a dica, em vez de aceitar um gesto que não faz nada.

        **O `uniq` ROTEIA (MIC-DA-MESA-CHEIA-01, 20/08/2026):** com dois DualSense no cabo há DUAS
        placas (`usb_pai_por_uniq`, 15/08), e o gesto ia para a primeira da lista, o microfone de
        outra pessoa. **A queda para a rota global acabou (ONDA5-02-01, 06/09/2026; 02-Q8: *"Deveria
        ser só pro controle em questao"*):** com endereço, fonte não resolvida = ``sem_fonte`` e
        ninguém escreve em placa nenhuma (como `lifecycle.py` desde 03/09). O `por_uniq` FICA na
        resposta como última trava contra um daemon INSTALADO mais velho que a janela (04/09,
        `mic.canal.set`).

        **Sem a mesa seria regressão:** a mesa de UM controle com `pactl list sources` ilegível
        passaria de rota global (certa por acaso) a ``sem_fonte``. A mesa entra por
        `recado_do_microfone.mesa_de_agora` e a regra 4 do `escolher_fonte` (um-para-um) responde
        por REGRA; `None` dali é "não perguntei" e mantém o comportamento de antes. Sem `uniq`, a
        rota global segue valendo (mesa de um).
        """
        if "volume" not in params:
            raise ValueError("mic.volume.set: 'volume' é obrigatório (0-100)")
        volume = params.get("volume")
        if isinstance(volume, bool) or not isinstance(volume, int):
            raise ValueError("mic.volume.set: 'volume' precisa ser inteiro")
        if not (0 <= volume <= 100):
            raise ValueError("mic.volume.set: 'volume' fora de 0-100")
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("mic.volume.set: 'uniq' precisa ser string ou omitido")
        if not uniq:
            uniq = self._uniq_do_alvo_de_saida()

        from hefesto_dualsense4unix.integrations.audio_control import (
            definir_volume_da_captura,
            fonte_de_captura_do_controle,
            fonte_de_captura_do_uniq,
            volume_da_captura,
        )

        if uniq:
            fonte = fonte_de_captura_do_uniq(
                uniq, mesa=recado_do_microfone.mesa_de_agora(self.daemon))
            if not fonte:
                return {"status": "sem_fonte", "fonte": None, "volume": None,
                        "por_uniq": True}
            por_uniq = True
        else:
            fonte = fonte_de_captura_do_controle()
            por_uniq = False
        if not fonte:
            return {"status": "sem_fonte", "fonte": None, "volume": None}
        ok = definir_volume_da_captura(volume, fonte=fonte)
        aparelho = None
        escritor = getattr(self.controller, "set_microphone_volume", None)
        if callable(escritor):
            try:
                aparelho = bool(escritor(volume, uniq=uniq))
            except Exception as exc:  # pragma: no cover
                aparelho = False
                logger.warning("mic_volume_aparelho_falhou", err=str(exc))
        return {
            "status": "ok" if ok else "erro",
            "fonte": fonte,
            "volume": volume_da_captura(fonte=fonte),
            "por_uniq": por_uniq,
            "aparelho": aparelho,
        }

    async def _handle_mouse_emulation_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga emulação de mouse+teclado (FEAT-MOUSE-01).

        Params: ``enabled`` bool (opcional — ausente ativa a rota speed-only), ``speed`` int 1-12,
        ``scroll_speed`` int 1-5.

        Sem ``enabled`` (BUG-MOUSE-GUI-SYNC-01 A4) atualiza SÓ as velocidades (config e device
        vivo), sem start/stop nem persistir o flag. BG-02 (25/08/2026): o `failed` leva também
        `bloqueio`, que `app/actions/mouse_actions.frase_da_recusa_do_mouse` traduz (sem ele caía em
        `RECUSA_SEM_MOTIVO`). Só viaja no `failed`: ali responde "por que NÃO"; o `bloqueio` de
        ESTADO (ligado e calado) é o do bloco `mouse_emulation` do `state_full`.
        """
        enabled = params.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("mouse.emulation.set: 'enabled' precisa ser boolean ou omitido")
        speed = params.get("speed")
        scroll_speed = params.get("scroll_speed")
        if speed is not None and not isinstance(speed, int):
            raise ValueError("mouse.emulation.set: 'speed' precisa ser int")
        if scroll_speed is not None and not isinstance(scroll_speed, int):
            raise ValueError("mouse.emulation.set: 'scroll_speed' precisa ser int")

        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar emulação de mouse")

        if enabled is None:
            ok = self.daemon.set_mouse_speed(speed=speed, scroll_speed=scroll_speed)
            resposta: dict[str, Any] = {
                "status": "ok" if ok else "failed",
                "enabled": bool(
                    getattr(self.daemon.config, "mouse_emulation_enabled", False)
                ),
            }
            if not ok:
                resposta["bloqueio"] = self._bloqueio_do_mouse()
            return resposta

        ok = self.daemon.set_mouse_emulation(
            enabled=enabled,
            speed=speed,
            scroll_speed=scroll_speed,
            origin=origem_do_pedido(params),
        )
        resposta = {"status": "ok" if ok else "failed", "enabled": enabled and ok}
        if not ok:
            resposta["bloqueio"] = self._bloqueio_da_recusa_do_mouse(enabled)
        return resposta

    def _bloqueio_da_recusa_do_mouse(self, pedia_ligar: bool) -> str | None:
        """POR QUE o daemon disse não ao liga/desliga do mouse, lido depois do fato: dono único de
        `mouse.emulation.set` e `desktop.status.set` (O-MOUSE-SEGUE-A-NAVEGACAO-01).
        """
        bloqueio = self._bloqueio_do_mouse()
        if pedia_ligar and bloqueio == "desligada":
            bloqueio = "sem_device"
        return bloqueio

    async def _handle_mouse_emulation_restore(
        self, _params: dict[str, Any]
    ) -> dict[str, Any]:
        """Restaura a emulação de mouse conforme a preferência persistida (HARM-06).

        Sem params: o daemon gravou a preferência. Faz "Controlar o PC" LIGAR o mouse; entra na
        transição de modo (`app/actions/mode_transition.py`), nunca num botão solto. Daemon dublado
        sem o método responde `failed` (o modo desktop segue).
        """
        if self.daemon is None:
            raise ValueError("daemon não disponível para restaurar emulação de mouse")
        restore = getattr(self.daemon, "restore_mouse_preference", None)
        if not callable(restore):
            return {"status": "failed", "enabled": False}
        enabled = bool(restore())
        return {"status": "ok", "enabled": enabled}

    async def _handle_desktop_arranjo_apply(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Carrega no aparelho o arranjo do `desktop`: a Navegação ou o Point and click.

        POINT-AND-CLICK-01 (17/09/2026): TERCEIRO passo da transição para o `MODE_DESKTOP`, no lugar
        do `mouse.emulation.restore`, que descartava as cinco coisas da aba. A política mora em
        `Daemon.aplicar_o_arranjo_do_desktop`.

        Params: ``origin``: "manual"|"profile", a origem da ATIVAÇÃO (fura o lock de 30 s do gesto
        manual); **o silêncio é "profile"** (ORIGEM-QUE-MENTE-01). ``arranjo``: "navegacao" ou
        "point_and_click"; sem ele (ou outro valor), o último guardado. Resposta: ``{"status":
        "ok", "arranjo": {seção: estado}}``, o relatório inteiro.

        A ENTRADA LIGA O MOUSE (O-MOUSE-SEGUE-A-NAVEGACAO-01, `D-2909-A-NAVEGACAO-LIGA-O-MOUSE`): o
        `forcar_mouse` do PS + R3 saiu e cliente antigo que o mande é ignorado. Daemon dublado sem o
        método responde `failed`.
        """
        if self.daemon is None:
            raise ValueError("daemon não disponível para aplicar o arranjo do desktop")
        aplicar = getattr(self.daemon, "aplicar_o_arranjo_do_desktop", None)
        if not callable(aplicar):
            return {"status": "failed", "arranjo": {}}
        origem = origem_do_pedido(params)
        modo: dict[str, Any] = (
            {"grava_o_modo": _porta_que_grava(origem)} if origem == "manual" else {}
        )
        arranjo = aplicar(origin=origem, **modo, **_o_arranjo_pedido(params))
        return {"status": "ok", "arranjo": dict(arranjo or {})}

    async def _handle_desktop_status_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """O «Status do Modo» da aba Navegação: mouse e teclado, e o perfil.

        O-MOUSE-SEGUE-A-NAVEGACAO-01 (29/09/2026), commit 3: uma chamada só (ato e gravação em
        `Daemon.definir_o_status_da_navegacao`).

        Params: ``enabled`` bool (obrigatório); ``origin`` "manual"|"profile" — só ``manual`` grava
        ``mouse.enabled`` e ``teclado_emulado`` no perfil ativo (o silêncio é reconciliação,
        ORIGEM-QUE-MENTE-01). Resposta: ``{"status", "enabled", "mouse_emulation",
        "keyboard_emulation", "perfil", "gravado"}``; os dois blocos são os do `state_full`, o do
        mouse com o `bloqueio` DA RECUSA e o do teclado com ``nao_tentado`` quando o mouse falhou
        antes.
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("desktop.status.set exige 'enabled' boolean")
        if self.daemon is None:
            raise ValueError("daemon não disponível para o Status do Modo")
        definir = getattr(self.daemon, "definir_o_status_da_navegacao", None)
        if not callable(definir):
            raise ValueError("daemon sem suporte ao Status do Modo")
        origem = origem_do_pedido(params)
        desfecho = definir(enabled, origin=origem, grava=_porta_que_grava(origem))

        mouse_ok = bool(desfecho.get("mouse"))
        bloco_do_mouse = {
            **self._mouse_emulation_payload(),
            "status": "ok" if mouse_ok else "failed",
        }
        if not mouse_ok:
            bloco_do_mouse["bloqueio"] = self._bloqueio_da_recusa_do_mouse(enabled)
        teclado = desfecho.get("teclado")
        bloco_do_teclado = {
            **self._keyboard_emulation_payload(),
            "status": "nao_tentado" if teclado is None else ("ok" if teclado else "failed"),
        }
        ok = mouse_ok and bool(teclado)
        return {
            "status": "ok" if ok else "failed",
            "enabled": bool(enabled and ok),
            "mouse_emulation": bloco_do_mouse,
            "keyboard_emulation": bloco_do_teclado,
            "perfil": desfecho.get("perfil"),
            "gravado": bool(desfecho.get("gravado")),
        }

    async def _handle_navegacao_interna_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga a Navegação Interna, ou troca o tipo («Interna» ou «Uso geral» da aba 06).

        A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01. Params: ``ligada`` bool
        (opcional; o interruptor «Status da navegação» no tipo Interna), ``tipo``
        "interna"|"computador" (opcional; só grava o tipo), ``origin`` "manual"|"profile". Resposta:
        ``{"status": "ok", "navegacao": {interna_ligada, tipo, foco}}``.
        """
        ligada = params.get("ligada")
        tipo = params.get("tipo")
        if ligada is not None and not isinstance(ligada, bool):
            raise ValueError("navegacao.interna.set: 'ligada' tem de ser boolean")
        if tipo is not None and not isinstance(tipo, str):
            raise ValueError("navegacao.interna.set: 'tipo' tem de ser texto")
        if ligada is None and tipo is None:
            raise ValueError("navegacao.interna.set exige 'ligada' ou 'tipo'")
        definir = getattr(self.daemon, "definir_a_navegacao_interna", None)
        if not callable(definir):
            raise ValueError("daemon sem suporte à Navegação Interna")
        bloco = definir(ligada=ligada, tipo=tipo, origin=origem_do_pedido(params))
        return {"status": "ok", "navegacao": dict(bloco)}

    async def _handle_navegacao_foco(self, params: dict[str, Any]) -> dict[str, Any]:
        """A janela diz se está na frente; a resposta traz os toques de cada controle.

        A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01. Um pulso ao ganhar/perder o
        foco e uma renovação a cada tique com a Interna ligada; sem renovação por
        ``PRAZO_DO_FOCO_S`` o daemon larga o foco. Os toques são contadores que só sobem, por
        controle (``r1``, ``l1``, ``x``, ``o``, ``quadrado``, ``triangulo``, ``cima``, ``baixo``,
        ``esquerda``, ``direita``, ``start``), contados só com a Interna agindo. Params: ``ativa:
        bool``. Resposta: ``{"status", "foco", "toques"}``.
        """
        ativa = params.get("ativa")
        if not isinstance(ativa, bool):
            raise ValueError("navegacao.foco exige 'ativa' boolean")
        from hefesto_dualsense4unix.daemon.subsystems.navegacao_interna import (
            da_navegacao,
        )

        nav = da_navegacao(self.daemon)
        if nav is None:
            raise ValueError("daemon sem suporte à Navegação Interna")
        apertos = self._apertos_de_cada_controle()
        nav.contar(apertos)
        nav.declarar_foco(ativa)
        return {"status": "ok", "foco": nav.foco_vivo(), "toques": nav.toques(apertos)}

    def _apertos_de_cada_controle(self) -> dict[str, dict[str, int] | None]:
        """``uniq → apertos`` do leitor de cada controle: o do posto, os do co-op e os passivos (as
        fontes do ``inputs`` do `state_full`).

        O contador é o ``EvdevSnapshot.apertos`` (a borda de cada aperto). O passivo só se lê se o
        hub já existe: quem o abre é o `state_full`.
        """
        describe = getattr(self.controller, "describe_controllers", None)
        entradas: list[Any] = []
        if callable(describe):
            with contextlib.suppress(Exception):
                entradas = list(describe() or [])
        coop = self._coop_live_snapshots()
        hub = self._sensor_hub
        out: dict[str, dict[str, int] | None] = {}
        for entrada in entradas:
            if not isinstance(entrada, dict) or not entrada.get("connected"):
                continue
            uniq = entrada.get("uniq")
            if not isinstance(uniq, str) or not uniq:
                continue
            snap: Any = None
            if entrada.get("is_primary"):
                leitor = getattr(self.controller, "_evdev", None)
                with contextlib.suppress(Exception):
                    snap = leitor.snapshot() if leitor is not None else None
            elif uniq in coop:
                snap = coop[uniq]
            elif hub is not None:
                with contextlib.suppress(Exception):
                    out[uniq] = hub.apertos(uniq)
                continue
            apertos = getattr(snap, "apertos", None)
            out[uniq] = dict(apertos) if isinstance(apertos, dict) else None
        return out

    def _navegacao_payload(self) -> dict[str, Any] | None:
        """O bloco ``navegacao`` do `state_full`: ``{interna_ligada, tipo, foco}``."""
        from hefesto_dualsense4unix.daemon.subsystems.navegacao_interna import (
            da_navegacao,
        )

        nav = da_navegacao(self.daemon)
        bloco = nav.bloco() if nav is not None else None
        if bloco is None:
            return None
        from hefesto_dualsense4unix.daemon.subsystems.big_picture import da_big_picture

        bp = da_big_picture(self.daemon)
        if bp is not None:
            bloco = {**bloco, "big_picture": bp.bloco(self.daemon)}
        return bloco

    async def _handle_navegacao_big_picture_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga ou desliga o Modo Big Picture na Steam.

        A-ABA-NAVEGACAO-FAZ-O-QUE-DIZ-E-O-MODO-STEAM-NAVEGA-O-BIG-PICTURE-01. Ligado e com a Steam
        na frente, onde o controle é do Hefesto (Sony DualSense, Xbox, Navegação), o direcional, a
        Cruz e o Círculo viram setas, Enter e Esc; no Nativo e no Steam Input a Steam lê o físico e
        o Hefesto não entra. É da máquina, não do perfil.

        Params: ``ligado`` bool (o valor da lista «Modo Big Picture na Steam»), ``origin``
        "manual"|"profile". Resposta: ``{"status": "ok", "big_picture": {ligado, agindo,
        quem_le}}``.
        """
        ligado = params.get("ligado")
        if not isinstance(ligado, bool):
            raise ValueError("navegacao.big_picture.set exige 'ligado' boolean")
        definir = getattr(self.daemon, "definir_o_big_picture", None)
        if not callable(definir):
            raise ValueError("daemon sem suporte ao Modo Big Picture")
        bloco = definir(ligado, origin=origem_do_pedido(params))
        return {"status": "ok", "big_picture": dict(bloco)}

    async def _handle_keyboard_emulation_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga a emulação de TECLADO (EMULACAO-NO-JOGO-01).

        Params: ``enabled`` bool (obrigatório). Molde do `mouse.emulation.set`; nasceu da queixa de
        29/07: ela desligou "o modo mouse teclado", o mouse obedeceu (flag em disco,
        FEAT-MOUSE-PERSIST-01) e o teclado seguiu emitindo Alt+Tab no R1 dentro da partida.

        Resposta: `{"status": "ok"|"failed", "enabled": bool, "keyboard_emulation": {...}}`, o bloco
        do `daemon.status`/`state_full` (`_keyboard_emulation_payload`). A interface deve avisar que
        desligar tira também o teclado virtual em L3/R3 e as três regiões do touchpad.
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("keyboard.emulation.set exige 'enabled' boolean")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o teclado emulado")
        setter = getattr(self.daemon, "set_keyboard_emulation", None)
        if not callable(setter):
            raise ValueError("daemon sem suporte a alternar o teclado emulado")
        ok = bool(setter(enabled))
        return {
            "status": "ok" if ok else "failed",
            "enabled": bool(enabled and ok),
            "keyboard_emulation": self._keyboard_emulation_payload(),
        }

    async def _handle_gamepad_mask_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """O MODO ÚNICO de todos os controles: `gamepad.mask.set {flavor}`.

        D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES (27/10/2026). Era a máscara de UM
        aparelho (MASCARA-NA-TELA-01, 03/09); agora o `flavor` (`dualsense`, `xbox`,
        `nintendo`) é o modo de todos, pelo escritor único
        (`Daemon.escolher_o_modo_unico`), o mesmo do PS + L3 e do chip de modo. O `uniq`
        fica opcional e não escolhe controle: a 01 publicada ainda o manda. Vazio ou
        desconhecido é recusado em voz alta. A resposta é a do `gamepad.emulation.set`; o modo
        que não subiu leva ``motivo: aparelho_nao_vestiu``, a palavra que a tela já traduz.
        """
        from hefesto_dualsense4unix.integrations.virtual_pad import MODOS, normalizar_modo

        flavor = params.get("flavor")
        if normalizar_modo(flavor) is None:
            raise ValueError(
                f"gamepad.mask.set: modo desconhecido {flavor!r} — o modo vale para "
                f"todos os controles; aceito: {', '.join(MODOS)}"
            )
        resposta = await self._handle_gamepad_emulation_set(
            {"enabled": True, "flavor": flavor, "origin": "manual"}
        )
        if resposta.get("status") != "ok":
            resposta["motivo"] = "aparelho_nao_vestiu"
        return resposta

    async def _handle_gamepad_emulation_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga o gamepad virtual e define a máscara (FEAT-DSX-GAMEPAD-FLAVOR-01)."""
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("gamepad.emulation.set exige 'enabled' boolean")
        flavor = params.get("flavor")
        if flavor is not None and not isinstance(flavor, str):
            raise ValueError("gamepad.emulation.set: 'flavor' precisa ser string")
        if flavor is not None:
            from hefesto_dualsense4unix.integrations.uinput_gamepad import (
                nomes_de_flavor_aceitos,
                resolver_flavor,
            )

            if resolver_flavor(flavor) is None:
                aceitos = ", ".join(nomes_de_flavor_aceitos())
                raise ValueError(
                    f"gamepad.emulation.set: máscara desconhecida {flavor!r} — "
                    f"aceito: {aceitos}"
                )
        caminho = params.get("caminho")
        if caminho is not None:
            from hefesto_dualsense4unix.integrations.virtual_pad import (
                CAMINHOS,
                normalizar_caminho,
            )

            if normalizar_caminho(caminho) is None:
                raise ValueError(
                    f"gamepad.emulation.set: caminho desconhecido {caminho!r} — "
                    f"aceito: {', '.join(CAMINHOS)}"
                )
            caminho = normalizar_caminho(caminho)
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o gamepad virtual")

        origem = origem_do_pedido(params)
        if enabled and origem == "manual" and (flavor is not None or caminho is not None):
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                DESFECHOS_EMULACAO_ATIVA,
            )
            from hefesto_dualsense4unix.integrations.uinput_gamepad import resolver_flavor
            from hefesto_dualsense4unix.integrations.virtual_pad import modo_do_par

            pedido = resolver_flavor(flavor) if flavor is not None else caminho
            ok = self.daemon.escolher_o_modo_unico(
                modo_do_par(caminho, pedido), porta=_porta_que_grava(origem)
            ) in DESFECHOS_EMULACAO_ATIVA
        else:
            modo: dict[str, Any] = {"caminho": caminho} if caminho is not None else {}
            if enabled and caminho is None:
                do_dono = self._caminho_do_perfil_ativo()
                if do_dono is not None:
                    modo = {"caminho": do_dono, "caminho_e_escolha": False}
            if enabled and origem == "manual":
                modo["grava_o_modo"] = _porta_que_grava(origem)
            ok = self.daemon.set_gamepad_emulation(
                enabled=enabled,
                flavor=flavor,
                origin=origem,
                **modo,
            )
        if enabled and ok:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                EMU_APLICADO,
                depois_do_p1,
                esperar_o_p1_que_nasce,
            )

            nasceu = await esperar_o_p1_que_nasce(self.daemon, depois_do_p1(self.daemon))
            ok = ok if nasceu is None else nasceu == EMU_APLICADO
        active_flavor = getattr(self.daemon.config, "gamepad_flavor", None)
        resposta: dict[str, Any] = {
            "status": "ok" if ok else "failed",
            "enabled": enabled and ok,
            "flavor": active_flavor,
        }
        if caminho is not None or (enabled and origem == "manual" and flavor is not None):
            resposta["caminho"] = _caminho_publicado(self.daemon)
        return resposta

    def _caminho_do_perfil_ativo(self) -> str | None:
        """O MODO que o perfil ativo declara (`dualsense`/`xbox`), ou ``None``."""
        from hefesto_dualsense4unix.integrations.virtual_pad import normalizar_caminho

        nome = getattr(getattr(self, "store", None), "active_profile", None)
        if not isinstance(nome, str) or not nome:
            return None
        try:
            mode = self.profile_manager.get(nome).mode
        except Exception:
            return None
        if getattr(mode, "kind", None) != "gamepad":
            return None
        return normalizar_caminho(getattr(mode, "caminho", None))

    async def _handle_coop_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liga o co-op local; RECUSA desligar (FEAT-DSX-COOP-LOCAL-01)."""
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("coop.set exige 'enabled' boolean")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o co-op")
        if not enabled:
            coop_recusa = getattr(self.daemon, "_coop_manager", None)
            players_recusa = (
                coop_recusa.player_count() if coop_recusa is not None else 1
            )
            logger.warning(
                "coop_set_desligar_recusado",
                motivo="coop_sempre_ligado",
                players=players_recusa,
            )
            return {
                "status": "recusado",
                "enabled": True,
                "players": players_recusa,
                "motivo": COOP_SEMPRE_LIGADO_MOTIVO,
            }
        effective = self.daemon.set_coop_enabled(
            enabled, origin=origem_do_pedido(params)
        )
        coop = getattr(self.daemon, "_coop_manager", None)
        players = coop.player_count() if coop is not None else 1
        return {"status": "ok", "enabled": bool(effective), "players": players}

    async def _handle_coop_sync(self, params: dict[str, Any]) -> dict[str, Any]:
        """Roda UM ciclo cheio de reconciliação do co-op (`sync(force=True)`)."""
        del params
        if self.daemon is None:
            raise ValueError("daemon não disponível para reconciliar o co-op")
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager

        coop = get_coop_manager(self.daemon)
        coop.sync(force=True)
        players = coop.player_count()
        return {
            "status": "ok",
            "players": players if isinstance(players, int) else 1,
            "active": bool(coop.should_be_active()),
        }

    async def _handle_emulation_suppress(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga o modo jogo (suprime emulação mouse/teclado)."""
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar modo jogo")
        suppressed = params.get("suppressed")
        if suppressed is not None and not isinstance(suppressed, bool):
            raise ValueError("emulation.suppress: 'suppressed' precisa ser bool")
        new_state = self.daemon.set_emulation_suppressed(suppressed)
        return {"status": "ok", "emulation_suppressed": new_state}

    async def _handle_machine_declare(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Grava no `maquina.json` o que o usuário declarou sobre a máquina (CONFIG-03).

        A aba Configurações guarda o que o Hefesto **não mede** (altura da antena, linha de visada,
        o rádio vizinho, o modo da chave física de um genérico, a cor do plástico quando a leitura
        do firmware falha); este é o único gesto que escreve aquele arquivo.

        Params: `{"maquina": {...}}`, declaração **parcial** no formato do `MaquinaConfig`
        (`utils/maquina.py`); a fusão é contra o disco sob o lock, para duas seções da janela não se
        apagarem. Retorno `{"ok": True}` ou `{"ok": False, "reason": ...}` com
        `declaracao_invalida`, `versao_desconhecida` ou `falha_ao_gravar`.

        **`descartados`** (CONFIG-06, 23/08/2026): no sucesso, lista os CAMPOS de topo do
        `maquina.json` em disco que o schema recusa e a gravação deixou para trás
        (`utils/maquina.py:_o_que_ainda_vale`), para a janela dizer o que se perdeu. Aditiva e só
        com algo a dizer; nomes CRUS do schema (a tradução é da ponte da GUI,
        `_rotulos_dos_campos`).

        **Toda recusa vem no CORPO, nunca como erro JSON-RPC:** o `_safe_call` da GUI colapsa erro
        de protocolo e daemon morto em `(False, None)` e a janela diria "daemon offline?" a um
        daemon vivo (doutrina do commit `daee934`; a frase de tela é da GUI, `_MOTIVOS_MAQUINA`).
        `versao_desconhecida` é a que importa: `maquina.json` de versão futura não é lido **nem
        sobrescrito**, os bytes ficam intactos. Fora do `daemon.state_full` (tique de 20 Hz): a
        declaração muda por gesto.
        """
        from hefesto_dualsense4unix.utils.maquina import (
            carregar_maquina,
            gravar_maquina_com_descartes,
        )

        declaracao = params.get("maquina")
        if not isinstance(declaracao, dict):
            return {"ok": False, "reason": "declaracao_invalida"}
        try:
            resultado = await asyncio.to_thread(
                gravar_maquina_com_descartes, declaracao
            )
        except ValueError as exc:
            logger.info("machine_declare_recusada_schema", err=str(exc))
            return {"ok": False, "reason": "declaracao_invalida"}
        except OSError as exc:
            logger.warning("machine_declare_falha_de_escrita", err=str(exc))
            return {"ok": False, "reason": "falha_ao_gravar"}
        if not resultado.gravou:
            return {"ok": False, "reason": "versao_desconhecida"}
        vivo: Any = self.daemon
        antes = getattr(vivo, "_maquina", None)
        vivo._maquina = await asyncio.to_thread(carregar_maquina)
        with contextlib.suppress(Exception):
            vivo.reaplicar_se_a_economia_mudou(antes)
        reconciliar = getattr(vivo, "reconciliar_bt_mic", None)
        if callable(reconciliar):
            try:
                _reconciliacao = reconciliar()
                if inspect.isawaitable(_reconciliacao):
                    await _reconciliacao
            except Exception as exc:
                logger.warning("machine_declare_bt_mic_nao_reconciliou", err=str(exc))
        if resultado.descartados:
            return {"ok": True, "descartados": list(resultado.descartados)}
        return {"ok": True}

    async def _handle_plugin_list(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Lista plugins carregados no daemon (FEAT-PLUGIN-01)."""
        ps = getattr(self.daemon, "_plugins_subsystem", None) if self.daemon else None
        if ps is None:
            return []
        result: list[dict[str, Any]] = ps.list_plugins()
        return result

    async def _handle_plugin_reload(self, params: dict[str, Any]) -> dict[str, Any]:
        """Recarrega plugins do disco (FEAT-PLUGIN-01)."""
        from hefesto_dualsense4unix.daemon.context import DaemonContext

        ps = getattr(self.daemon, "_plugins_subsystem", None) if self.daemon else None
        if ps is None:
            raise ValueError("plugins não habilitados neste daemon")

        ctx = DaemonContext(
            controller=self.controller,
            bus=getattr(self.daemon, "bus", None),  # type: ignore[arg-type]
            store=self.store,
            config=getattr(self.daemon, "config", None),
            executor=getattr(self.daemon, "_executor", None),
        )
        total = await ps.reload(ctx)
        return {"status": "ok", "total": total}

    async def _handle_mods_agora(self, params: dict[str, Any]) -> dict[str, Any]:
        """A coluna «Agora» da janela de uma extensão: o último ``acessorios.estado`` publicado.

        ``{mod}`` → ``{mod, ligado, nivel, perfil, aparelhos, ajustes}``; sem conexão viva, o
        estado vazio (``ligado: false``, nível 0, sem aparelho), e a tela mostra a coluna vazia.
        """
        from hefesto_dualsense4unix.mods.porta import estado_vazio_dos_acessorios

        mod = self._mod_do_pedido(params)
        supervisor = getattr(self.daemon, "_mods_supervisor", None) if self.daemon else None
        if supervisor is None:
            return estado_vazio_dos_acessorios(mod)
        agora: dict[str, Any] = supervisor.porta.agora_de(mod)
        return agora

    async def _handle_mods_parar_tudo(self, params: dict[str, Any]) -> dict[str, Any]:
        """O «Parar tudo» da janela: o gesto ``para`` vai só à extensão ``{mod}``.

        Só vale para a extensão cujo manifesto instalado declara ``parar_tudo``. ``{parado}`` é
        falso quando ela não está conectada à porta (nada a parar).
        """
        from hefesto_dualsense4unix.mods.instalador import (
            InstalacaoRecusadaError,
            manifesto_instalado,
        )

        mod = self._mod_do_pedido(params)
        supervisor = getattr(self.daemon, "_mods_supervisor", None) if self.daemon else None
        if supervisor is None:
            return {"parado": False}
        try:
            manifesto = await asyncio.to_thread(
                manifesto_instalado, mod, lugares=supervisor.lugares
            )
        except InstalacaoRecusadaError as exc:
            raise ValueError(exc.frase) from exc
        if not manifesto.parar_tudo:
            raise ValueError(f"«{manifesto.nome}» não declara o «Parar tudo».")
        return {"parado": bool(supervisor.porta.parar_tudo(mod))}

    async def _handle_mods_jogos(self, params: dict[str, Any]) -> dict[str, Any]:
        """Os jogos da extensão de lançador ``{mod}``: o último ``lancador.jogos`` publicado.

        ``{mod, jogos: [{chave, nome, abrir, janela}]}``; sem conexão viva, a lista vazia.
        """
        mod = self._mod_do_pedido(params)
        supervisor = getattr(self.daemon, "_mods_supervisor", None) if self.daemon else None
        jogos = supervisor.porta.jogos_de(mod) if supervisor is not None else []
        return {"mod": mod, "jogos": jogos}

    @staticmethod
    def _mod_do_pedido(params: dict[str, Any]) -> str:
        """O ``mod`` dos pedidos da janela da extensão: o ``id`` do manifesto, nunca vazio."""
        mod = params.get("mod")
        if not isinstance(mod, str) or not mod.strip():
            raise ValueError("o pedido não diz de qual extensão se trata (mod)")
        return mod.strip()

    _medidor_de_ar: Any = None
    _adaptadores_em_cache: tuple[float, frozenset[str], dict[str, str]] | None = None
    _afh_evitados: dict[str, tuple[int, ...] | None] | None = None
    _enlaces_lidos: dict[str, dict[str, Any]] | None = None
    _ler_qualidade: Any = None
    _afh_lido_em: float = float("-inf")
    _afh_em_voo: bool = False
    _ler_afh: Any = None
    _sinal_dos_enlaces: dict[str, int | None] | None = None
    _ler_sinal: Any = None
    _leitor_proprio_do_sinal: Any = None
    _monitor_de_receptores: Any = None
    _varrer_os_receptores: Any = None

    def _enriquecer_e_medir_o_ar(
        self, result: dict[str, Any], entries: list[dict[str, Any]], state: Any
    ) -> None:
        """O enriquecimento POR CONTROLE e, depois dele, o ar."""
        with contextlib.suppress(Exception):
            self._enrich_controllers_per_controller(entries, state)
        with contextlib.suppress(Exception):
            self._merge_radio(entries)
            result["radio_ar"] = self._ar_por_adaptador(entries)
        with contextlib.suppress(Exception):
            result["radio_receptores"] = self._os_receptores_publicam()
        from hefesto_dualsense4unix.profiles.schema import HAPTICA_PCT_PADRAO

        result["haptica_pct_padrao"] = HAPTICA_PCT_PADRAO
        with contextlib.suppress(Exception):
            result["radio_governador"] = self._o_governador_publica()
        with contextlib.suppress(Exception):
            result["radio_central"] = self._a_central_publica(entries)
        with contextlib.suppress(Exception):
            self._merge_mira(entries)
        self._merge_acessibilidade(entries)
        with contextlib.suppress(Exception):
            self._merge_no_jogo(entries)
        with contextlib.suppress(Exception):
            self._merge_zero(entries)

    def _os_receptores_publicam(self) -> dict[str, Any]:
        """``state_full["radio_receptores"]``: a saúde de cada receptor 2.4G (a última hora).

        Só números: teclas apertadas repetindo e buracos no movimento do mouse, por ``usb:vid:pid``,
        nunca o código de uma tecla (``integrations/receptor_sem_fio``). O monitor nasce na primeira
        pergunta e lê o evdev numa thread; sob a suíte e no modo falso a chave sai vazia, salvo a
        régua que injeta o dela.
        """
        monitor = self._monitor_de_receptores
        if monitor is None:
            from hefesto_dualsense4unix.integrations import bluez_dbus, receptor_sem_fio
            from hefesto_dualsense4unix.utils.xdg_paths import fake_mode_enabled

            varrer = self._varrer_os_receptores
            if varrer is None:
                if bluez_dbus.a_suite_esta_rodando() or fake_mode_enabled():
                    return {}
                varrer = self._receptores_do_censo
            monitor = receptor_sem_fio.MonitorDosReceptores(varrer)
            self._monitor_de_receptores = monitor
            monitor.iniciar()
        publicado: dict[str, Any] = monitor.publicar()
        return publicado

    @staticmethod
    def _receptores_do_censo() -> dict[str, tuple[str, ...]]:
        """``{usb:vid:pid: (/dev/input/eventN, …)}`` dos receptores que o censo reconheceu."""
        from hefesto_dualsense4unix.integrations import receptor_sem_fio
        from hefesto_dualsense4unix.integrations.censo_do_barramento import ler_o_barramento

        achados: dict[str, tuple[str, ...]] = {}
        for a in ler_o_barramento().conectados():
            if a.receptor and a.eventos:
                chave = receptor_sem_fio.chave_do_aparelho(a.vid, a.pid)
                achados[chave] = (*achados.get(chave, ()), *(f"/dev/input/{e}" for e in a.eventos))
        return achados

    @staticmethod
    def _hz_ou_none(valor: Any) -> float | None:
        """Um Hz publicável, ou ``None`` — bool e texto não são taxa."""
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return None
        return float(valor)

    _ADAPTADOR_TTL_S = 2.0
    _AFH_PERIODO_S = 10.0

    def _merge_radio(self, entries: list[dict[str, Any]]) -> None:
        """Quatro chaves por controle, SEMPRE presentes, ``None`` = não sei."""
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        def chave(valor: Any) -> str:
            return (norm_mac(str(valor)) or "") if isinstance(valor, str) else ""

        no_radio = [
            e["uniq"] for e in entries
            if e.get("transport") == "bt" and isinstance(e.get("uniq"), str) and e["uniq"]
        ]
        enderecos = self._adaptadores_do_radio(no_radio)
        hub = self._sensor_hub
        if hub is None:
            from hefesto_dualsense4unix.utils.xdg_paths import fake_mode_enabled

            if not fake_mode_enabled():
                hub = self._garantir_sensor_hub()
        voz = getattr(getattr(self.daemon, "_bt_mic_subsystem", None), "hz_de_voz", None)
        pontes: dict[str, str] = {}
        pontes_fn = getattr(
            getattr(self.daemon, "_alto_falante_subsystem", None), "pontes_de_pe", None
        )
        if callable(pontes_fn):
            with contextlib.suppress(Exception):
                pontes = {chave(u): m for u, m in dict(pontes_fn()).items() if chave(u)}
        perguntar_hz = getattr(hub, "hz_do_movimento", None)
        from hefesto_dualsense4unix.daemon.ganho_da_haptica import GANHO

        nativo = False
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.subsystems import rumble

            nativo = bool(rumble.modo_nativo_manda_nos_motores(self.daemon))
        no_ar_fn = getattr(
            getattr(self.daemon, "_alto_falante_subsystem", None), "haptica_no_ar", None
        )
        for entry in entries:
            uniq = entry.get("uniq") if isinstance(entry.get("uniq"), str) else None
            radio = entry.get("transport") == "bt"
            vivo = bool(uniq) and entry.get("connected", True) is not False
            entry["adaptador"] = (enderecos.get(uniq) or None) if radio and uniq else None
            hz: Any = None
            if vivo and callable(perguntar_hz):
                with contextlib.suppress(Exception):
                    hz = perguntar_hz(uniq)
            entry["hz_movimento"] = self._hz_ou_none(hz)
            hz_voz: Any = None
            if vivo and radio and callable(voz):
                with contextlib.suppress(Exception):
                    hz_voz = voz(uniq)
            entry["hz_voz"] = self._hz_ou_none(hz_voz)
            modo = pontes.get(chave(uniq)) if radio and uniq else None
            entry["ponte_do_radio"] = modo if modo in ("som", "haptica") else None
            entry["sinal_dbm"] = (
                (self._sinal_dos_enlaces or {}).get(chave(uniq)) if radio and uniq else None
            )
            entry["haptica_pct"] = GANHO.pct_guardado(uniq)
            entry["haptica_alcanca"] = not (radio and nativo and modo is None)
            entry["haptica_vale_pct"] = GANHO.pct_que_vale(uniq)
            no_ar = False
            if vivo and callable(no_ar_fn):
                with contextlib.suppress(Exception):
                    no_ar = no_ar_fn(uniq) is True
            entry["haptica_no_ar"] = no_ar

    def _adaptadores_do_radio(self, uniqs: list[str]) -> dict[str, str]:
        """``{uniq: endereço do adaptador | ""}``, relido no máximo a cada 2 s."""
        from hefesto_dualsense4unix.integrations import radio_da_mesa

        agora = time.monotonic()
        alvo = frozenset(uniqs)
        cache = self._adaptadores_em_cache
        if cache is not None and cache[1] == alvo and agora - cache[0] < self._ADAPTADOR_TTL_S:
            return cache[2]
        enderecos = radio_da_mesa.adaptador_por_uniq(sorted(alvo)) if alvo else {}
        self._adaptadores_em_cache = (agora, alvo, dict(enderecos))
        return dict(enderecos)

    def _ar_por_adaptador(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """``state_full["radio_ar"]``: o orçamento de ar por adaptador
        (``radio_da_mesa.orcamento_por_adaptador`` é o dono).

        Aqui só se junta o que o daemon mede: as chaves de :meth:`_merge_radio`, a amostra de ar e o
        AFH.

        **O AMOSTRADOR TEM UM DONO (GOVERNADOR-DO-RADIO-01, 23/09/2026):** um ``MedidorDeAr``
        próprio aqui daria DOIS medidores fotografando o mesmo contador. A amostra é a do governador
        (``AltoFalanteSubsystem.governador``, a cada 250 ms); sem ele, ou no modo falso, «não sei».
        ``_medidor_de_ar`` é a porta da régua, que injeta um dublê.
        """
        from hefesto_dualsense4unix.integrations import radio_da_mesa

        amostra: Any = None
        medidor = self._medidor_de_ar
        if medidor is not None:
            amostra = medidor.amostrar()
        else:
            governador = self._o_governador()
            if governador is not None:
                amostra = governador.ultima_amostra()
        ar: dict[str, Any] | None = None
        if amostra is not None:
            ar = {e: a for e, a in dict(amostra).items() if e}
            self._talvez_ler_o_afh(ar)
            self._talvez_ler_o_sinal(ar)
        orcamento = radio_da_mesa.orcamento_por_adaptador(
            entries,
            ar=ar,
            canais_evitados=dict(self._afh_evitados or {}),
            enlaces=dict(self._enlaces_lidos or {}),
            sinais=dict(self._sinal_dos_enlaces or {}),
        )
        return {endereco: o.publicar() for endereco, o in orcamento.items()}

    def _talvez_ler_o_afh(self, ar: dict[str, Any]) -> None:
        """Pergunta o AFH de cada enlace numa thread, no máximo a cada 10 s."""
        agora = time.monotonic()
        if self._afh_em_voo or agora - self._afh_lido_em < self._AFH_PERIODO_S:
            return
        ler = self._ler_afh
        if ler is None:
            from hefesto_dualsense4unix.utils.xdg_paths import fake_mode_enabled

            if fake_mode_enabled():
                return
            from hefesto_dualsense4unix.integrations.ar_do_adaptador import ler_mapa_afh

            ler = ler_mapa_afh
        self._afh_em_voo = True
        self._afh_lido_em = agora
        leituras = dict(ar)

        a_qualidade = self._ler_qualidade
        if a_qualidade is None and self._ler_afh is not None:
            def a_qualidade(_hci: int, _handle: int) -> int | None:
                return None
        elif a_qualidade is None:
            from hefesto_dualsense4unix.integrations.ar_do_adaptador import ler_qualidade

            a_qualidade = ler_qualidade

        def perguntar() -> None:
            from hefesto_dualsense4unix.integrations.ar_do_adaptador import (
                canais_evitados_pelo_adaptador,
                enlaces_do_adaptador,
            )

            evitados: dict[str, tuple[int, ...] | None] = {}
            enlaces: dict[str, dict[str, Any]] = {}
            try:
                for endereco, leitura in leituras.items():
                    lidos = enlaces_do_adaptador(leitura, ler_mapa=ler, ler_qual=a_qualidade)
                    enlaces[endereco] = lidos
                    evitados[endereco] = canais_evitados_pelo_adaptador(lidos)
                self._afh_evitados = evitados
                self._enlaces_lidos = enlaces
            except Exception:  # pragma: no cover
                logger.debug("radio_afh_nao_lido", exc_info=True)
            finally:
                self._afh_em_voo = False

        try:
            import threading

            threading.Thread(target=perguntar, name="radio-afh", daemon=True).start()
        except Exception:
            self._afh_em_voo = False


    def _talvez_ler_o_sinal(self, ar: dict[str, Any]) -> None:
        """O sinal (RSSI) de cada enlace: UM leitor, no máximo uma pergunta por segundo.

        Com o governador de pé o leitor é o dele (ele pausa a ponte do controle longe); sem
        governador, o daemon tem o seu.
        """
        from hefesto_dualsense4unix.integrations import radio_da_mesa

        leitor = getattr(self._o_governador(), "leitor_do_sinal", None)
        if not isinstance(leitor, radio_da_mesa.LeitorDoSinal) or self._ler_sinal is not None:
            if self._leitor_proprio_do_sinal is None:
                self._leitor_proprio_do_sinal = radio_da_mesa.LeitorDoSinal(self._ler_sinal)
            leitor = self._leitor_proprio_do_sinal
        leitor.talvez_ler(ar)
        self._sinal_dos_enlaces = leitor.sinais()

    def _o_governador(self) -> Any:
        """O governador do rádio, que mora no subsystem do som — ou ``None``."""
        subsystem = getattr(self.daemon, "_alto_falante_subsystem", None)
        return getattr(subsystem, "governador", None)

    def _o_governador_publica(self) -> dict[str, Any]:
        """``state_full["radio_governador"]``: as pontes com a marca «além do limite», quem está
        cedendo, e os pedidos que a tela tem de perguntar."""
        governador = self._o_governador()
        if governador is None:
            return {}
        publicado = governador.publicar()
        return dict(publicado) if isinstance(publicado, dict) else {}

    async def _handle_radio_ponte_ligar_aqui(self, params: dict[str, Any]) -> dict[str, Any]:
        """«Ligar aqui»: a ponte deste controle sobe além do limite do adaptador."""
        uniq = params.get("uniq")
        if not isinstance(uniq, str) or not uniq.strip():
            raise ValueError("radio.ponte.ligar_aqui pede `uniq` do controle")
        governador = self._o_governador()
        if governador is None:
            return {"status": "sem_governador", "uniq": uniq}
        ligou = await asyncio.to_thread(governador.ligar_aqui, uniq.strip())
        return {"status": "ok" if ligou else "sem_adaptador", "uniq": uniq}


    def _a_central(self) -> Any:
        """A central do rádio, que o daemon sobe no arranque — ou ``None``."""
        return getattr(self.daemon, "_central_do_radio", None)

    def _a_central_publica(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """``state_full["radio_central"]``: os movimentos (``esperando``, ``chegou``,
        ``nao_chegou``) e a proposta do «Equilibrar», UMA ou nenhuma.

        ``entries`` já passou pelo :meth:`_merge_radio` (``adaptador`` do ``HID_PHYS`` e
        ``ponte_do_radio``, o que a proposta pesa). Nunca abre o dono do BlueZ nem espera o rádio: o
        tique não pode.
        """
        central = self._a_central()
        if central is None:
            return {}
        publicado = central.publicar(entries)
        return dict(publicado) if isinstance(publicado, dict) else {}

    async def _handle_radio_mover(self, params: dict[str, Any]) -> dict[str, Any]:
        """«Mover» um aparelho para um adaptador, ou o «Conectar» (D8).

        ``aparelho``: o endereço (``aa:bb:…``) ou o ``uniq`` de 12 hex (o ``proposta.controle`` do
        «Equilibrar»). Sem ele é o «Conectar»: a janela abre no destino com mais vaga de ponte e
        chega o controle segurado em PS + Create. ``destino``: o adaptador; sem ele, a D8 escolhe.

        Volta quando a trava do rádio vem (no máximo 5 s, decisão registrada) com o movimento
        «esperando»; o resto segue num fio e chega por ``state_full["radio_central"]``. ``status:
        "ocupado"`` tem DUAS causas com a mesma resposta: a trava não veio no prazo, ou OUTRO
        MOVIMENTO ESTÁ EM CURSO (um por vez, ``central_do_radio.MOTIVO_OCUPADO``); nada mudou. A
        tela já apaga os botões enquanto um espera (``a08_conexoes._ocupado``) e esta recusa é a
        segunda trava, para o pedido entre dois tiques.
        """
        from hefesto_dualsense4unix.integrations.central_do_radio import MOTIVO_OCUPADO

        aparelho = params.get("aparelho")
        destino = params.get("destino")
        if aparelho is not None and not isinstance(aparelho, str):
            raise ValueError("radio.mover: `aparelho` é o endereço do aparelho")
        if destino is not None and not isinstance(destino, str):
            raise ValueError("radio.mover: `destino` é o endereço do adaptador")
        central = self._a_central()
        if central is None:
            return {"status": "sem_central"}
        if aparelho and aparelho.strip():
            movimento = await asyncio.to_thread(
                central.comecar_a_mover, aparelho.strip(), destino or None
            )
        else:
            movimento = await asyncio.to_thread(central.comecar_a_conectar, destino or None)
        status = "ocupado" if movimento.motivo == MOTIVO_OCUPADO else "ok"
        return {"status": status, "movimento": movimento.publicar()}


    _CAMPOS_DA_MIRA = ("ligada", "sensibilidade", "zona_morta_graus_s",
                       "gatilho", "inverter_horizontal", "inverter_vertical",
                       "inclinacao", "toque", "mesmo_parado", "lado")

    def _merge_acessibilidade(self, entries: list[dict[str, Any]]) -> None:
        """``entry["acessibilidade"]``: a ativação e a curva que valem AGORA neste controle."""
        from hefesto_dualsense4unix.core import (
            ativacao_de_botao,
            curva_do_analogico,
            filtro_de_botao,
        )

        store = getattr(self, "store", None)
        for entry in entries:
            uniq = entry.get("uniq")
            if not isinstance(uniq, str) or not uniq:
                continue
            tem_modo = (ativacao_de_botao.da_peca(store, uniq) is not None
                        or filtro_de_botao.da_peca(store, uniq) is not None)
            tem_curva = curva_do_analogico.da_peca(store, uniq) is not None
            entry["acessibilidade"] = {
                "ativacao": tem_modo,  # (noqa-acento)
                "analogicos": tem_curva,
            }

    def _merge_mira(self, entries: list[dict[str, Any]]) -> None:
        """``entry["mira"]`` de cada controle: o chip e o bloco da Calibrar."""
        from hefesto_dualsense4unix.core import roteador_de_movimento as rot

        store = getattr(self, "store", None)
        mesa = rot.ativo(store)
        agora = time.monotonic()
        for entry in entries:
            uniq = entry.get("uniq")
            if not isinstance(uniq, str) or not uniq:
                continue
            vale = rot.da_peca(store, uniq, mesa)
            numeros = rot.parametros_da_peca(store, uniq)
            mira = vale if vale is not None and vale.ligado else None
            entry["mira"] = {
                "ligada": mira is not None,
                "virtual": vale is not None and rot.virtual_aceso(vale),
                "lado": rot.lado_do_virtual(vale if vale is not None else numeros),
                "destino": mira.destino if mira is not None else rot.DESTINO_NENHUM,
                "toque": vale.toque if vale is not None else rot.DESTINO_NENHUM,
                "inclinacao": vale.acelerometro if vale is not None else rot.DESTINO_NENHUM,
                "sensibilidade": numeros.sensibilidade,
                "zona_morta_graus_s": numeros.zona_morta_graus_s,
                "gatilho": numeros.gatilho,
                "inverter_horizontal": numeros.inverter_horizontal,
                "inverter_vertical": numeros.inverter_vertical,
                "inclinacao_parada": (
                    vale is not None and vale.inclina and not vale.mesmo_parado
                    and rot.inclinacao_parada(store, uniq, agora)
                ),
                "mesmo_parado": numeros.mesmo_parado,
            }

    async def _handle_mira_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`mira.set` — o chip «Analógico Virtual» e os ajustes da Calibrar, POR CONTROLE."""
        from hefesto_dualsense4unix.core import roteador_de_movimento as rot
        from hefesto_dualsense4unix.profiles.schema import (
            ControllerOverrides,
            ProfileMovimentoConfig,
        )

        desconhecidos = sorted(set(params) - {"uniq", *self._CAMPOS_DA_MIRA})
        if desconhecidos:
            raise ValueError(
                f"mira.set não conhece {desconhecidos}: a tela oferece o chip "
                "(`ligada`), o lado dele (`lado`), os dois deslizantes (`sensibilidade`, "
                "`zona_morta_graus_s`), o `gatilho`, os dois `inverter_*`, a "
                "`inclinacao`, o `toque` e o `mesmo_parado`, e o resto do arranjo "
                "mora no perfil"
            )
        pedidos: dict[str, Any] = {}
        if "ligada" in params and not isinstance(params["ligada"], bool):
            raise ValueError(
                "mira.set: 'ligada' precisa ser boolean — true acende o Analógico "
                "Virtual no lado guardado, false o apaga"
            )
        if "lado" in params and params["lado"] not in rot.LADOS_DO_VIRTUAL:
            raise ValueError(
                f"mira.set: 'lado' é um de {', '.join(rot.LADOS_DO_VIRTUAL)} — o "
                "analógico que o giro e a inclinação movem"
            )
        o_virtual = "ligada" in params or "lado" in params
        if "sensibilidade" in params:
            valor = params["sensibilidade"]
            if isinstance(valor, bool) or not isinstance(valor, int):
                raise ValueError("mira.set: 'sensibilidade' é um inteiro de 1 a 12")
            pedidos["sensibilidade"] = valor
        if "zona_morta_graus_s" in params:
            valor = params["zona_morta_graus_s"]
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise ValueError(
                    "mira.set: 'zona_morta_graus_s' é o «Ignorar tremor até», "
                    "em graus por segundo"
                )
            pedidos["zona_morta_graus_s"] = float(valor)
        if "gatilho" in params:
            valor = params["gatilho"]
            if valor is not None and not isinstance(valor, str):
                raise ValueError(
                    "mira.set: 'gatilho' é o botão do «Só enquanto eu segurar», "
                    "ou null para a mira andar sempre"
                )
            pedidos["gatilho"] = valor or None
        for lado in ("inverter_horizontal", "inverter_vertical"):
            if lado in params:
                valor = params[lado]
                if not isinstance(valor, bool):
                    raise ValueError(f"mira.set: '{lado}' precisa ser boolean")
                pedidos[lado] = valor
        if "inclinacao" in params:
            valor = params["inclinacao"]
            if not isinstance(valor, str) or valor not in rot.DESTINOS_DA_INCLINACAO:
                raise ValueError(
                    "mira.set: 'inclinacao' é um de "
                    f"{', '.join(rot.DESTINOS_DA_INCLINACAO)} — o analógico que a "
                    "inclinação move, ou nenhum"
                )
            pedidos["acelerometro"] = valor
        if "toque" in params:
            valor = params["toque"]
            if valor not in rot.TOQUES:
                raise ValueError(
                    f"mira.set: 'toque' é um de {', '.join(rot.TOQUES)} — o "
                    "touchpad do computador, o cursor ou as zonas"
                )
            pedidos["toque"] = valor
        if "mesmo_parado" in params:
            valor = params["mesmo_parado"]
            if not isinstance(valor, bool):
                raise ValueError(
                    "mira.set: 'mesmo_parado' precisa ser boolean — o «Mesmo parado» "
                    "do «Só enquanto eu segurar»"
                )
            pedidos["mesmo_parado"] = valor
        if not pedidos and not o_virtual:
            raise ValueError(
                f"mira.set exige ao menos um de {', '.join(self._CAMPOS_DA_MIRA)} "
                "— campo omitido NÃO mexe na mira"
            )
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("mira.set: 'uniq' precisa ser string ou omitido")

        alvo = uniq or self._uniq_do_primario()
        if not alvo:
            return {
                "status": "sem_controle",
                "uniq": None,
                "motivo": (
                    "não há controle na mesa para mirar — a mira é POR PEÇA, e "
                    "cair no primeiro da lista faria a mesa cheia mirar sempre "
                    "com o mesmo controle"
                ),
            }
        chave = self._chave_de_peca_que_grava(alvo)
        if not chave:
            return {
                "status": "sem_endereco",
                "uniq": alvo,
                "motivo": (
                    f"{alvo!r} não é um endereço de rádio de uma peça de "
                    "plástico — sem MAC não há como mirar por um controle"
                ),
            }

        nativo = bool(
            self.daemon is not None and getattr(self.daemon, "is_native_mode", bool)()
        )
        if nativo and {"ligada", "lado", "inclinacao", "toque"} & set(params):
            logger.info("mira_set_recusado_no_nativo", uniq=chave)
            return {
                "status": "nativo",
                "uniq": alvo,
                "motivo": (
                    "Modo Nativo: o jogo lê o controle físico direto e não há "
                    "gamepad virtual onde a mira escreva — o chip não grava"
                ),
            }

        nome = self._perfil_que_grava()
        perfil: Any = None
        escritos: dict[str, Any] = {}
        if nome:
            from hefesto_dualsense4unix.profiles.loader import load_profile

            perfil = load_profile(nome)
            dele = (perfil.controllers or {}).get(chave)
            antes = getattr(dele, "movimento", None)
            escritos = dict(antes.model_dump(exclude_unset=True)) if antes else {}
        try:
            mesa = (perfil.movimento if perfil is not None
                    else rot.parametros_da_peca(self.store, chave))
            if o_virtual:
                atual = rot.arranjo_da_peca(
                    mesa, ProfileMovimentoConfig.model_validate(escritos))
                lado = params.get("lado") or rot.lado_do_virtual(atual)
                rota = lado if params.get("ligada", True) else rot.DESTINO_NENHUM
                pedidos = {"lado": lado, "destino": rota, "acelerometro": rota, **pedidos}
            campos = {**escritos, **pedidos}
            secao = ProfileMovimentoConfig.model_validate(campos)
            arranjo = rot.arranjo_da_peca(mesa, secao)
        except ValueError as exc:
            raise ValueError(f"mira.set recusado: {exc}") from exc

        gravado = False
        if perfil is not None and escritos != campos:
            from hefesto_dualsense4unix.profiles.loader import save_profile

            atuais = dict(perfil.controllers or {})
            dele = atuais.get(chave) or ControllerOverrides()
            atuais[chave] = dele.model_copy(update={"movimento": secao})
            save_profile(perfil.model_copy(update={"controllers": atuais}))
            gravado = True

        rot.definir_da_peca(self.store, chave, arranjo)
        rot.sincronizar_o_filtro(self.store)

        ressalva: str | None = None
        if nativo:
            ressalva = (
                "Modo Nativo: o jogo lê o controle FÍSICO direto e não há gamepad "
                "virtual onde a mira escreva. Os ajustes ficam guardados e valem "
                "quando o modo voltar a Virtual ou Xbox."
            )
        logger.info(
            "mira_set",
            uniq=chave,
            perfil=nome,
            gravado=gravado,
            ligada=arranjo.ligado,
            lado=arranjo.lado,
            sensibilidade=arranjo.sensibilidade,
            zona_morta_graus_s=arranjo.zona_morta_graus_s,
            gatilho=arranjo.gatilho,
            inverter_horizontal=arranjo.inverter_horizontal,
            inverter_vertical=arranjo.inverter_vertical,
            toque=arranjo.toque,
            acelerometro=arranjo.acelerometro,
            mesmo_parado=arranjo.mesmo_parado,
            nativo=nativo,
        )
        return {
            "status": "ok",
            "uniq": alvo,
            "perfil": nome if isinstance(nome, str) else None,
            "gravado": gravado,
            "ligada": arranjo.ligado,
            "virtual": rot.virtual_aceso(arranjo),
            "lado": rot.lado_do_virtual(arranjo),
            "sensibilidade": arranjo.sensibilidade,
            "zona_morta_graus_s": arranjo.zona_morta_graus_s,
            "gatilho": arranjo.gatilho,
            "inverter_horizontal": arranjo.inverter_horizontal,
            "inverter_vertical": arranjo.inverter_vertical,
            "toque": arranjo.toque,
            "inclinacao": arranjo.acelerometro,
            "mesmo_parado": arranjo.mesmo_parado,
            "alcance": {"tique": "nao_se_aplica" if nativo else "aplicado"},
            "ressalva": ressalva,
        }

    async def _handle_haptica_testar(self, params: dict[str, Any]) -> dict[str, Any]:
        """`haptica.testar` — o botão «Háptica» da aba Vibração, num controle.

        A-ABA-VIBRACAO-TEM-O-SENSOR-HAPTICO-E-DOIS-TESTES-01 (02/10/2026). Params: ``{uniq: str,
        ligado: bool}``. Ligado, o tocador do aparelho daquele controle toca a forma do «Efeito
        háptico» dele, a mesma do tiro (``alto_falante.testar_a_haptica``), com o ganho da linha
        «Sensor Háptico»; desligado, cala. A janela rebate o ligado a cada segundo e o teste que
        ninguém rebate solta sozinho. Mora no fim da classe para nenhuma citação ``arquivo:linha``
        deste arquivo andar.

        Responde ``{status, uniq, ligado, leva, forma}``, com ``par`` e ``motivo_da_forma`` quando
        a forma cede ao par de teste; ``sem_efeito`` na escolha «Sem efeito» e ``sem_som`` quando o
        subsystem do som não está no ar, os dois com ``motivo``.
        """
        uniq = params.get("uniq")
        if not isinstance(uniq, str) or not uniq.strip():
            raise ValueError("haptica.testar exige 'uniq': o teste é de um controle")
        ligado = params.get("ligado")
        if not isinstance(ligado, bool):
            raise ValueError("haptica.testar exige 'ligado' verdadeiro ou falso")
        sub = getattr(self.daemon, "_alto_falante_subsystem", None)
        testar = getattr(sub, "testar_a_haptica", None)
        if not callable(testar):
            return {
                "status": "sem_som",
                "motivo": "o som do Hefesto não está no ar; reinicie o serviço",
            }
        resposta = testar(uniq.strip(), ligado)
        return dict(resposta) if isinstance(resposta, dict) else {"status": "sem_som"}


    async def _handle_radio_busca_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """O «Procurar»: liga ou desliga a busca do rádio, com valor absoluto."""
        ligada = params.get("ligada")
        destino = params.get("destino")
        if not isinstance(ligada, bool):
            raise ValueError("radio.busca.set: `ligada` é true ou false")
        if destino is not None and not isinstance(destino, str):
            raise ValueError("radio.busca.set: `destino` é o endereço do adaptador")
        central = self._a_central()
        if central is None:
            return {"status": "sem_central", "busca": None}
        resposta = await asyncio.to_thread(
            central.ligar_a_busca, ligada, (destino or "").strip() or None)
        return dict(resposta)

    async def _handle_radio_dispensar(self, params: dict[str, Any]) -> dict[str, Any]:
        """O X do «Não Conectou»: o movimento acabado do aparelho sai da publicação."""
        aparelho = params.get("aparelho")
        if not isinstance(aparelho, str) or not aparelho.strip():
            raise ValueError("radio.dispensar: `aparelho` é o endereço do aparelho")
        central = self._a_central()
        if central is None:
            return {"status": "sem_central", "dispensado": False}
        feito = await asyncio.to_thread(central.dispensar, aparelho)
        atual = central.movimento_de(aparelho)
        if feito is None and atual is not None and atual.em_curso:
            return {"status": "ocupado", "dispensado": False}
        return {"status": "ok", "dispensado": feito is not None}

    def _merge_no_jogo(self, entries: list[dict[str, Any]]) -> None:
        """``entry["no_jogo"]``: os analógicos que o pad DAQUELE controle mandou ao jogo
        (O-CIRCULO-DO-ANALOGICO-MOSTRA-O-QUE-O-JOGO-VE-01).

        O cartão pintava só a mão (`inputs`); com Inclinação ou Mira num analógico o jogo recebe
        outra coisa. Vem do último envio do pad (`eixos_no_jogo`), o MESMO pad do `vpad_backend`,
        sem cópia no laço do jogo. `None` sem pad (Nativo, Navegação, pendente), com o jogador
        cedido ao primário (o `forward_all` o pula), sem endereço ou antes do primeiro envio. Nunca
        levanta.
        """
        primario = (
            getattr(self.daemon, "_gamepad_device", None) if self.daemon is not None else None
        )
        dos_outros = self._coop_pads_que_mandam()
        for entry in entries:
            uniq = entry.get("uniq")
            uniq = uniq if isinstance(uniq, str) and uniq else None
            if entry.get("is_primary"):
                pad = primario
            else:
                pad = dos_outros.get(uniq) if uniq is not None else None
            entry["no_jogo"] = self._eixos_do_pad(pad)

    def _coop_pads_que_mandam(self) -> dict[str, Any]:
        """MAC -> pad dos secundários que o `forward_all` alimenta agora: o critério do
        `_coop_vpads_by_uniq` (sem `path:` nem pendente sem `vpad`) e mais o cedido ao primário.
        """
        coop = getattr(self.daemon, "_coop_manager", None) if self.daemon is not None else None
        players = getattr(coop, "_players", None) if coop is not None else None
        if not isinstance(players, dict):
            return {}
        pads: dict[str, Any] = {}
        for mac, player in players.items():
            if not isinstance(mac, str) or mac.startswith("path:"):
                continue
            vpad = getattr(player, "vpad", None)
            if vpad is None or getattr(player, "cedido_ao_primario", False) is True:
                continue
            pads[mac] = vpad
        return pads

    @staticmethod
    def _eixos_do_pad(pad: Any) -> dict[str, int] | None:
        """`{lx, ly, rx, ry}` do último envio do `pad`, ou `None`."""
        if pad is None:
            return None
        eixos = getattr(pad, "eixos_no_jogo", None)
        if not isinstance(eixos, tuple) or len(eixos) != 4:
            return None
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in eixos):
            return None
        return dict(zip(("lx", "ly", "rx", "ry"), eixos, strict=True))

    _ZERO_PARADO = "parado"
    _ZERO_MEDINDO = "medindo"
    _ZERO_PRONTO = "pronto"
    _ZERO_MEXEU = "mexeu"
    _INTERVALO_DO_ZERO_S = 0.02

    def _estados_do_zero(self) -> dict[str, str]:
        """Chave de sensor -> o estado da última medida desta sessão."""
        estados = getattr(self, "_estados_do_zero_por_chave", None)
        if not isinstance(estados, dict):
            estados = {}
            self._estados_do_zero_por_chave = estados
        return estados

    async def _handle_motion_calibrate(self, params: dict[str, Any]) -> dict[str, Any]:
        """`motion.calibrate {uniq}` — mede o repouso de UM controle e guarda o zero dele.

        Responde na hora ``{status: "medindo", uniq, segundos}``; a medida corre por
        ``SEGUNDOS_DO_ZERO`` e o fim aparece em ``entry["zero"]`` do ``state_full``: ``pronto``
        (zero no disco), ``mexeu`` (nada guardado), ``parado`` (sem leitura, ou disco que não
        gravou: o zero anterior volta). Segundo pedido no meio responde a mesma medida. No Nativo
        mede e guarda igual: o zero vale quando o Hefesto volta a traduzir.
        """
        from hefesto_dualsense4unix.core import roteador_de_movimento as rot
        from hefesto_dualsense4unix.core.virtual_motion import chave_de_sensor

        uniq = params.get("uniq")
        if not isinstance(uniq, str) or not chave_de_sensor(uniq):
            raise ValueError("motion.calibrate exige 'uniq': o zero é de um controle")
        uniq = uniq.strip()
        chave = chave_de_sensor(uniq)
        estados = self._estados_do_zero()
        resposta = {
            "status": self._ZERO_MEDINDO, "uniq": uniq, "segundos": float(rot.SEGUNDOS_DO_ZERO),
        }
        if estados.get(chave) == self._ZERO_MEDINDO:
            return resposta
        estados[chave] = self._ZERO_MEDINDO
        tarefa = asyncio.get_running_loop().create_task(self._medir_o_zero(uniq, chave))
        em_voo = getattr(self, "_medidas_do_zero_em_voo", None)
        if not isinstance(em_voo, set):
            em_voo = set()
            self._medidas_do_zero_em_voo = em_voo
        em_voo.add(tarefa)
        tarefa.add_done_callback(em_voo.discard)
        return resposta

    async def _medir_o_zero(self, uniq: str, chave: str) -> None:
        """A medida: amostra o giro e o acelerômetro, decide e grava. Nunca levanta."""
        from hefesto_dualsense4unix.core import roteador_de_movimento as rot
        from hefesto_dualsense4unix.utils.session import gravar_os_zeros

        estados = self._estados_do_zero()
        try:
            hub = self._garantir_sensor_hub()
            laco = asyncio.get_running_loop()
            fim = laco.time() + float(rot.SEGUNDOS_DO_ZERO)
            amostras: list[tuple[Any, Any]] = []
            while laco.time() < fim:
                giro = hub.velocidade_do_movimento(uniq)
                acel = hub.aceleracao_do_movimento(uniq)
                if giro is not None and acel is not None:
                    amostras.append((giro, acel))
                await asyncio.sleep(self._INTERVALO_DO_ZERO_S)
            zero = rot.medir_o_zero(amostras)
            if zero is None:
                lidas = len(amostras) >= rot.MINIMO_DE_AMOSTRAS_DO_ZERO
                estados[chave] = self._ZERO_MEXEU if lidas else self._ZERO_PARADO
                logger.info("zero_nao_guardado", uniq=uniq, amostras=len(amostras))
                return
            anterior = rot.zero_de(self.store, uniq)
            rot.definir_o_zero(self.store, uniq, zero)
            gravou = await asyncio.to_thread(gravar_os_zeros, rot.zeros_para_gravar(self.store))
            if not gravou:
                rot.definir_o_zero(self.store, uniq, anterior)
                estados[chave] = self._ZERO_PARADO
                logger.warning("zero_nao_gravado", uniq=uniq)
                return
            estados[chave] = self._ZERO_PRONTO
            logger.info("zero_guardado", uniq=uniq, vies=[round(v, 3) for v in zero.giro])
        except asyncio.CancelledError:
            estados[chave] = self._ZERO_PARADO
            raise
        except Exception as exc:
            estados[chave] = self._ZERO_PARADO
            logger.warning("zero_falhou", uniq=uniq, err=str(exc))

    def _merge_zero(self, entries: list[dict[str, Any]]) -> None:
        """``entry["zero"]``: ``{estado, guardado}`` da medida do zero deste controle."""
        from hefesto_dualsense4unix.core import roteador_de_movimento as rot
        from hefesto_dualsense4unix.core.virtual_motion import chave_de_sensor

        estados = self._estados_do_zero()
        for entry in entries:
            uniq = entry.get("uniq")
            if not isinstance(uniq, str) or not chave_de_sensor(uniq):
                entry["zero"] = None
                continue
            guardado = rot.zero_de(self.store, uniq) is not None
            estado = estados.get(chave_de_sensor(uniq))
            if estado is None:
                estado = self._ZERO_PRONTO if guardado else self._ZERO_PARADO
            entry["zero"] = {"estado": estado, "guardado": guardado}

    async def _grava_a_acessibilidade(
        self, metodo: str, secao: str, params: dict[str, Any], *, por_peca: bool
    ) -> dict[str, Any]:
        """O miolo de `perfil.ativacao.set`, `perfil.analogicos.set` e `perfil.cursor.set`.

        Grava a seção no perfil que vale (campo omitido NÃO mexe no que já está), valida pelo
        mesmo modelo do arquivo e deposita o resultado no `store` ao vivo, sem reativar o perfil.
        Com `uniq` (só ativação e analógicos), a escrita é a da peça; sem, a do perfil.
        """
        from hefesto_dualsense4unix.profiles import schema

        modelo: Any = {
            "ativacao": schema.ProfileAtivacaoConfig,  # (noqa-acento)
            "analogicos": schema.ProfileAnalogicosConfig,
            "cursor": schema.ProfileCursorConfig,
        }[secao]
        campos_do_modelo = set(modelo.model_fields)
        desconhecidos = sorted(set(params) - {"uniq", *campos_do_modelo})
        if desconhecidos:
            raise ValueError(
                f"{metodo} não conhece {desconhecidos}: os campos são "
                f"{', '.join(sorted(campos_do_modelo))}"
            )
        pedidos = {k: v for k, v in params.items() if k != "uniq"}
        if not pedidos:
            raise ValueError(
                f"{metodo} exige ao menos um de {', '.join(sorted(campos_do_modelo))} "
                "— campo omitido NÃO mexe na seção"
            )
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError(f"{metodo}: 'uniq' precisa ser string ou omitido")
        if uniq is not None and not por_peca:
            raise ValueError(f"{metodo}: o cursor é do perfil, não de uma peça")

        nome = self._perfil_que_grava()
        if not nome:
            return {"status": "sem_perfil", "uniq": uniq,
                    "motivo": "não há perfil valendo onde gravar a seção"}
        chave: str | None = None
        if uniq is not None:
            chave = self._chave_de_peca_que_grava(uniq)
            if not chave:
                return {"status": "sem_endereco", "uniq": uniq,
                        "motivo": f"{uniq!r} não é o endereço de rádio de uma peça de plástico"}

        from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile

        perfil = load_profile(nome)
        dele = (perfil.controllers or {}).get(chave) if chave else None
        antes = getattr(dele, secao, None) if chave else getattr(perfil, secao, None)
        escritos = dict(antes.model_dump(exclude_unset=True)) if antes is not None else {}
        campos = {**escritos, **pedidos}
        try:
            nova = modelo.model_validate(campos)
        except ValueError as exc:
            raise ValueError(f"{metodo} recusado: {exc}") from exc

        gravado = escritos != campos
        if gravado:
            if chave:
                atuais = dict(perfil.controllers or {})
                da_peca = atuais.get(chave) or schema.ControllerOverrides()
                atuais[chave] = da_peca.model_copy(update={secao: nova})
                perfil = perfil.model_copy(update={"controllers": atuais})
            else:
                perfil = perfil.model_copy(update={secao: nova})
            save_profile(perfil)

        relatorio: dict[str, str] = {}
        aplicar = getattr(self.profile_manager, "apply_acessibilidade", None)
        if callable(aplicar):
            aplicar(perfil, relatorio=relatorio)
        logger.info("perfil_acessibilidade_set", metodo=metodo, perfil=nome, uniq=chave,
                    gravado=gravado)
        return {
            "status": "ok",
            "uniq": uniq,
            "perfil": nome,
            "gravado": gravado,
            secao: nova.model_dump(),
            "alcance": {"tique": relatorio.get("acessibilidade", "aplicado")},
        }

    async def _handle_perfil_ativacao_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`perfil.ativacao.set` — o modo e o filtro do botão, no perfil ou numa peça."""
        return await self._grava_a_acessibilidade(
            "perfil.ativacao.set", "ativacao", params, por_peca=True)  # (noqa-acento)

    async def _handle_perfil_analogicos_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`perfil.analogicos.set` — a zona morta, a curva e a mão, no perfil ou numa peça."""
        return await self._grava_a_acessibilidade(
            "perfil.analogicos.set", "analogicos", params, por_peca=True)

    async def _handle_perfil_cursor_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`perfil.cursor.set` — a precisão, a permanência e o clique travado do cursor."""
        return await self._grava_a_acessibilidade(
            "perfil.cursor.set", "cursor", params, por_peca=False)

    async def _handle_sequencia_gravar(self, params: dict[str, Any]) -> dict[str, Any]:
        """`sequencia.gravar` — ouve os botões de um controle e devolve os passos e os tempos."""
        import time

        from hefesto_dualsense4unix.core import ativacao_de_botao

        acao = str(params.get("acao") or "estado")  # (noqa-acento)
        if acao not in ("iniciar", "parar", "estado"):
            raise ValueError(
                "sequencia.gravar: 'acao' é iniciar, parar ou estado")
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("sequencia.gravar: 'uniq' precisa ser string ou omitido")
        if acao == "iniciar":
            ativacao_de_botao.gravar_iniciar(self.store, uniq, time.monotonic())
        if acao == "parar":
            passos = ativacao_de_botao.gravar_parar(self.store)
            return {"status": "ok", "gravando": False, "passos": passos}
        gravando, passos = ativacao_de_botao.gravar_estado(self.store)
        return {"status": "ok", "gravando": gravando, "passos": passos}

    async def _handle_sequencia_tocar(self, params: dict[str, Any]) -> dict[str, Any]:
        """`sequencia.tocar` — toca uma vez, no pad virtual, a sequência que a tela mostra."""
        import time

        from hefesto_dualsense4unix.core import ativacao_de_botao
        from hefesto_dualsense4unix.profiles import schema

        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("sequencia.tocar: 'uniq' precisa ser string ou omitido")
        desconhecidos = sorted(set(params) - {"uniq", "passos", "jeito", "ritmo"})
        if desconhecidos:
            raise ValueError(f"sequencia.tocar não conhece {desconhecidos}")
        try:
            seq = schema.SequenciaDeBotao.model_validate(
                {k: v for k, v in params.items() if k != "uniq"})
        except ValueError as exc:
            raise ValueError(f"sequencia.tocar recusado: {exc}") from exc
        motivo = ativacao_de_botao.recusar((), (), {}, {}, (), {seq.passos[0].botao: seq})
        if motivo:
            raise ValueError(f"sequencia.tocar recusado: {motivo}")
        ativacao_de_botao.tocar_agora(self.store, uniq, seq, time.monotonic())
        return {"status": "ok", "passos": len(seq.passos)}

    async def _handle_desktop_arranjo_repor(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Repõe a tabela do Point and click, se é o arranjo de agora: o serviço decide.

        A aba Navegação pede depois de trocar o «Perfil jogo - navegação»
        (O-POINT-AND-CLICK-SE-REPOE-EM-TODO-CAMINHO-01). Resposta: ``{"status", "reposto"}``;
        ``reposto`` falso fora do `desktop` ou na Navegação. Daemon sem o método: ``failed``.
        """
        repor = getattr(self.daemon, "_repor_o_point_and_click", None)
        if not callable(repor):
            return {"status": "failed", "reposto": False}
        return {"status": "ok", "reposto": bool(repor())}

    async def _manifesto_da_janela(self, mod: str) -> tuple[Any, Any] | None:
        """O manifesto instalado de ``mod`` (o da janela aberta) e a porta; ``None`` sem o
        supervisor."""
        from hefesto_dualsense4unix.mods.instalador import (
            InstalacaoRecusadaError,
            manifesto_instalado,
        )

        supervisor = getattr(self.daemon, "_mods_supervisor", None) if self.daemon else None
        if supervisor is None:
            return None
        try:
            manifesto = await asyncio.to_thread(
                manifesto_instalado, mod, lugares=supervisor.lugares)
        except InstalacaoRecusadaError as exc:
            raise ValueError(exc.frase) from exc
        return manifesto, supervisor.porta

    async def _handle_mods_acao(self, params: dict[str, Any]) -> dict[str, Any]:
        """O clique numa ação da janela: ``extensao.acao`` vai só à extensão ``{mod}``.

        Sem ``alvo``, a ação é uma das declaradas para a janela; com ele (o ``id``
        de um aparelho), uma das ``aparelhos_acoes``, e ``valor`` (verdadeiro ou falso) é a chave
        ``ligar``; ou um dos ``controles`` que o aparelho publicou (``_conferir_a_acao``).
        ``{enviada}`` é falso quando a extensão não está conectada à porta.
        """
        mod = self._mod_do_pedido(params)
        acao = params.get("acao")  # (noqa-acento)
        alvo, valor = params.get("alvo"), params.get("valor")
        if not isinstance(acao, str) or not acao:
            raise ValueError("o pedido não diz qual ação")
        if alvo is not None and (not isinstance(alvo, str) or not 1 <= len(alvo) <= 40):
            raise ValueError("o alvo é o id de um aparelho, de 1 a 40 letras")
        if valor is not None and not isinstance(valor, (bool, str)):
            raise ValueError("o valor da ação é verdadeiro, falso ou o id de uma opção")
        achado = await self._manifesto_da_janela(mod)
        if achado is None:
            return {"enviada": False}
        manifesto, porta = achado
        geridos = manifesto.aparelhos_acoes
        declaradas = (geridos.acoes if geridos else []) if alvo is not None else manifesto.acoes
        conhecida = any(a.id == acao for a in declaradas)
        _conferir_a_acao(manifesto, porta, mod, alvo, acao, valor, conhecida)
        return {"enviada": bool(porta.acao(mod, acao, alvo=alvo, valor=valor))}

    async def _handle_mods_livre(self, params: dict[str, Any]) -> dict[str, Any]:
        """O arrastar do controle livre: ``extensao.livre`` só à extensão ``{mod}``.

        ``{mod, id, valor (0 a 1), soltou, modo?}``; a porta solta no máximo 20 por segundo, e o
        soltar sai sempre. ``modo`` só vale no ``livre`` com ``modos`` (sem ele, ``soltar``).
        ``{enviado}`` é falso quando a extensão não está conectada à porta.
        """
        mod = self._mod_do_pedido(params)
        opcao_id, valor, soltou = params.get("id"), params.get("valor"), params.get("soltou", False)
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0 <= valor <= 1:
            raise ValueError("o valor do livre vai de 0 a 1")
        if not isinstance(soltou, bool):
            raise ValueError("o soltou é verdadeiro ou falso")
        achado = await self._manifesto_da_janela(mod)
        if achado is None:
            return {"enviado": False}
        manifesto, porta = achado
        livre = manifesto.opcao_livre
        if livre is None or livre.id != opcao_id:
            raise ValueError(f"«{manifesto.nome}» não declara o controle livre «{opcao_id}».")
        from hefesto_dualsense4unix.mods.manifesto import MODOS_DO_LIVRE

        modo = params.get("modo", MODOS_DO_LIVRE[0] if livre.modos else None)
        if not livre.modos and modo is not None:
            raise ValueError(f"«{manifesto.nome}» não declara os modos do controle livre.")
        if livre.modos and modo not in MODOS_DO_LIVRE:
            raise ValueError("o modo do livre é soltar, segurar ou repetir")
        com_modo = {"modo": modo} if livre.modos else {}
        return {"enviado": bool(porta.livre(mod, livre.id, float(valor), soltou=soltou,
                                            **com_modo))}


def _conferir_a_acao(manifesto: Any, porta: Any, mod: str, alvo: str | None, acao: str,
                     valor: Any, declarada: bool) -> None:
    """A ação declarada leva ``valor`` verdadeiro ou falso (a chave ``ligar``). A que o manifesto
    não declara só passa com ``aparelhos_controles``, se for um dos ``controles`` que o aparelho
    ``alvo`` publicou no último estado, e com o valor do tipo dele (a chave, verdadeiro ou falso; a
    paleta e a escolha, o ``id`` de uma das opções)."""
    if declarada:
        if valor is not None and not isinstance(valor, bool):
            raise ValueError("o valor da ação é verdadeiro ou falso")
        return
    controle = _controle_do_alvo(manifesto, porta, mod, alvo, acao)
    if controle is None:
        onde = "nos aparelhos" if alvo is not None else "na janela"
        raise ValueError(f"«{manifesto.nome}» não declara a ação «{acao}» {onde}.")
    _conferir_o_valor_do_controle(controle, valor)


def _controle_do_alvo(manifesto: Any, porta: Any, mod: str, alvo: str | None,
                      acao: str) -> dict[str, Any] | None:
    """O controle pedido do aparelho ``alvo`` no último ``acessorios.estado`` de ``mod``: só com
    ``aparelhos_controles`` no manifesto e com o aparelho que o publicou."""
    if alvo is None or manifesto.aparelhos_controles is None:
        return None
    estado = porta.agora_de(mod)
    aparelho = next((a for a in estado.get("aparelhos") or [] if a.get("id") == alvo), None)
    controles = (aparelho or {}).get("controles") or []
    return next((c for c in controles if c.get("id") == acao), None)


def _conferir_o_valor_do_controle(controle: dict[str, Any], valor: Any) -> None:
    """A chave pede verdadeiro ou falso; a paleta e a escolha, o ``id`` de uma das opções."""
    if controle["tipo"] == "chave":
        if not isinstance(valor, bool):
            raise ValueError("o valor da chave é verdadeiro ou falso")
        return
    ids = [o["id"] for o in controle.get("opcoes") or []]  # (noqa-acento)
    if valor not in ids:
        raise ValueError(f"o valor de «{controle['id']}» é uma de: {', '.join(ids)}")


def _uniq_do_rumble(params: dict[str, Any], metodo: str) -> str | None:
    """O ``uniq`` opcional do pedido de vibração: ausente é «o alvo de agora»."""
    uniq = params.get("uniq")
    if uniq is None:
        return None
    if not isinstance(uniq, str) or not uniq.strip():
        raise ValueError(f"{metodo}: 'uniq' precisa ser o endereço do controle")
    return uniq.strip()


def _chaves_dos_assentos(registry: Any) -> set[str]:
    """As chaves com ASSENTO na mesa de ``registry``: as ligadas e as guardadas."""
    ligados = IpcHandlersMixin._connected_keys(registry)
    lugares = getattr(registry, "lugares_da_mesa", None)
    if not callable(lugares):
        return ligados
    try:
        na_mesa = {int(r) for r in lugares()}
        postos = registry.snapshot().items()
    except Exception:
        return ligados
    return ligados | {str(k) for k, r in postos if r in na_mesa}


def _ligado(entrada: tuple[int, int, str, Any]) -> bool:
    """A entrada da mesa é de um controle LIGADO (e não de um lugar guardado)."""
    return entrada[2] in IpcHandlersMixin._connected_keys(entrada[3])


def _fora_da_mesa(mesa: list[tuple[int, int, str, Any]], numero: int) -> bool:
    """O número pedido não cabe — a MESMA conta do botão cinza da aba 04
    (``a04_iluminacao.um_botao_de_player``).

    Fora da mesa = passa da quantidade de ligados E ninguém ligado o tem. Acima da conta que um
    ligado tem é troca; o que só um lugar guardado tem, ou ninguém tem, é recusa: daemon e tela
    dizem a mesma coisa.
    """
    if numero <= sum(1 for e in mesa if _ligado(e)):
        return False
    return numero > len(mesa) or not _ligado(mesa[numero - 1])


def _amostra_da_luz_do_mic(cru: Any) -> int | None:
    """O `common[8]` do último pedido de luz do jogo, ou None (nunca um mock)."""
    if isinstance(cru, bool) or not isinstance(cru, int):
        return None
    return int(cru)


def _o_microfone_do_jogo_no_vpad(vp: Any) -> dict[str, Any]:
    """As chaves do microfone do jogo no bloco de um pad virtual."""
    mudo = getattr(vp, "mic_mudo_do_jogo_amostra", None)
    return {
        "mic_led_do_jogo": _contador_do_vpad(vp, "mic_led_do_jogo"),
        "mic_led_do_jogo_amostra": _amostra_da_luz_do_mic(
            getattr(vp, "mic_led_do_jogo_amostra", None)
        ),
        "mic_mudo_do_jogo": _contador_do_vpad(vp, "mic_mudo_do_jogo"),
        "mic_mudo_do_jogo_amostra": mudo if isinstance(mudo, bool) else None,
        "mic_eco_do_driver": _contador_do_vpad(vp, "mic_eco_do_driver"),
        "mic_do_jogo_retido": _contador_do_vpad(vp, "mic_do_jogo_retido"),
    }


def _a_luz_do_jogo_no_controle(status: dict[str, Any], uniq: Any) -> None:
    """`luz_do_mic_do_jogo` no `audio` do controle, só com o pedido de pé."""
    from hefesto_dualsense4unix.daemon.subsystems.luz_do_mic import luz_do_mic_do_jogo

    do_jogo = luz_do_mic_do_jogo(str(uniq or ""))
    if do_jogo is not None:
        status["luz_do_mic_do_jogo"] = int(do_jogo)


def _com_a_marca_do_f_hid(result: dict[str, Any]) -> None:
    """O ``usb_f_hid`` dos pads USB virtuais é o curado? Só da memória do pad.

    O pad anota a marca ``get_report_sized`` ao montar o gadget; o
    ``state_full`` não lê o sysfs. None = nenhum pad USB mediu ainda.
    """
    emulacao = result.get("gamepad_emulation")
    if isinstance(emulacao, dict):
        from hefesto_dualsense4unix.integrations import pad_usb

        emulacao["get_report_sized"] = pad_usb.marca_do_f_hid_medida()


def _na_steam(handlers: Any) -> bool:
    """A janela em foco é o cliente da Steam: ela conta como jogo, mas o toque fica no cursor.

    O ``ha_jogo`` vê a Steam como jogo; com a máscara DualSense e o Ligado, o hub agarraria o
    touchpad nela, e o cursor pararia na loja e na biblioteca.
    """
    from hefesto_dualsense4unix.profiles.steam_app import e_janela_do_cliente_steam

    store = getattr(handlers, "store", None)
    return bool(e_janela_do_cliente_steam(getattr(store, "window_detect_current_class", None)))


def _sem_os_campos_aposentados(overrides: Any) -> Any:
    """Tira do `config_overrides` as chaves de `CAMPOS_APOSENTADOS`, avisando uma vez por chave.

    Valor que não é objeto passa como veio: quem o recusa é o handler.
    """
    if not isinstance(overrides, dict):
        return overrides
    for aposentado in sorted(CAMPOS_APOSENTADOS & set(overrides)):
        if aposentado not in _APOSENTADOS_AVISADOS:
            _APOSENTADOS_AVISADOS.add(aposentado)
            logger.warning("daemon.reload.campo_aposentado", campo=aposentado)
    return {k: v for k, v in overrides.items() if k not in CAMPOS_APOSENTADOS}


CAMPOS_APOSENTADOS = frozenset({"auto_reconnect", "reconnect_backoff_sec"})
_APOSENTADOS_AVISADOS: set[str] = set()


def _o_arranjo_pedido(params: dict[str, Any]) -> dict[str, str]:
    """O ``arranjo`` do `desktop.arranjo.apply`, quando é um dos dois; ``{}`` deixa o guardado."""
    from hefesto_dualsense4unix.utils.session import ARRANJOS_DO_DESKTOP

    pedido = params.get("arranjo")
    return {"arranjo": pedido} if pedido in ARRANJOS_DO_DESKTOP else {}


__all__ = ["IpcHandlersMixin"]
