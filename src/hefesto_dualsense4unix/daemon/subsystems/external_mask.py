"""O modo único de todos os controles, visto por quem monta e recria os vpads.

D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES: o modo mora no ``mode`` do perfil ativo
(``gamepad_flavor`` e ``caminho``), chega ao daemon pelo ``DaemonConfig.gamepad_flavor`` e
vale para os quatro jogadores. Não há máscara por aparelho: a escolha que cada controle
tinha virou o modo do perfil na migração do
:meth:`~hefesto_dualsense4unix.profiles.schema.Profile._a_mascara_de_cada_controle_vira_o_modo`,
e o ``controller_masks.json`` que sobrar no disco é levado ao perfil e apagado no boot
(:func:`o_arquivo_de_mascaras_vira_o_modo`).
O escritor é um só, :meth:`~hefesto_dualsense4unix.daemon.lifecycle.Daemon.escolher_o_modo_unico`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    FLAVORS,
    normalize_flavor,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

ARQUIVO_DE_MASCARAS_DE_ANTES = "controller_masks.json"


def mascaras_validas() -> frozenset[str]:
    """Os valores que uma máscara pode ter — o catálogo do vpad, não uma cópia."""
    return frozenset(FLAVORS)


def normalizar_mascara(valor: object) -> str | None:
    """A máscara canônica de ``valor``, ou ``None`` quando não há uma."""
    if not isinstance(valor, str):
        return None
    chave = valor.strip().lower()
    return chave if chave in mascaras_validas() else None


def mascara_efetiva(identity: str | None, flavor_do_jogo: object) -> str:
    """A máscara de QUALQUER aparelho: a do modo único (``flavor_do_jogo``).

    A ``identity`` não decide nada desde a D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES:
    a ordem de três degraus (MASCARA-NO-PERFIL-01, 08/09/2026) perdeu o degrau 1, a
    ``controllers[uniq].mascara``, e o que fica é o ``mode.gamepad_flavor`` do perfil
    (pela config do daemon) e o padrão. O parâmetro segue para os chamadores que
    perguntam por aparelho (o co-op, a fábrica do P1, o lançamento) receberem a mesma
    resposta para todos. ``normalize_flavor`` é TOLERANTE: este é caminho interno, e
    quem valida gesto de gente é o portão do IPC.
    """
    del identity
    if isinstance(flavor_do_jogo, str):
        return normalize_flavor(flavor_do_jogo)
    return normalize_flavor(None)


def mesma_identidade(a: str | None, b: str | None) -> bool:
    """Os dois endereços são o MESMO aparelho? Pela chave canônica do registro.

    Comparar as strings cruas faria `AA:BB:…` e `aabb…` serem dois controles: a
    canonização que numera os aparelhos (`ExternalIdentityRegistry._canonical`) responde.
    """
    chave_a = _chave(a)
    chave_b = _chave(b)
    return chave_a is not None and chave_a == chave_b


def _chave(identity: str | None) -> str | None:
    """A chave canônica da identidade, ou ``None``."""
    if not identity or not isinstance(identity, str):
        return None
    chave, _persistivel = ExternalIdentityRegistry._canonical(identity)
    return chave or None


def vpad_ficou_para_tras(
    flavor_do_vpad: object,
    identity: str | None,
    flavor_do_jogo: object,
    *,
    vpad: object = None,
    caminho: object = None,
) -> bool:
    """O gamepad virtual deste jogador está com a máscara ERRADA? (recriá-lo)

    O laço de ``daemon/subsystems/coop.py`` derruba e recria todo vpad cujo ``flavor``
    divirja do modo único: sem ele, os jogadores 2+ ficam **presos no flavor antigo**
    quando o modo muda em runtime, com rumble morto e prompts divergentes do P1
    (SPRINT-GAME-RUMBLE-01). Um vpad sem ``flavor`` legível conta como ficado para trás.

    E O CANAL TAMBÉM (MODO-DE-CONEXAO-01, 13/09/2026): com a mesma máscara, o caminho
    Xbox é o vpad `uinput` e o DualSense é o `uhid`. Quando o chamador passa o ``vpad`` e
    o ``caminho`` pedido, um vpad no canal errado também ficou para trás. A comparação é
    pelo CANAL (:func:`~hefesto_dualsense4unix.integrations.virtual_pad.quer_uhid`), e um
    vpad que caiu no `uinput` por falta de `uhid` nasceu com o caminho DualSense
    pendurado, e por isso não entra em laço de recriação.
    """
    mascara = mascara_efetiva(identity, flavor_do_jogo)
    if flavor_do_vpad != mascara:
        return True
    if vpad is None:
        return False
    from hefesto_dualsense4unix.integrations.virtual_pad import (
        caminho_do_vpad,
        o_aparelho_mudou,
        quer_uhid,
    )

    return quer_uhid(caminho_do_vpad(vpad), mascara) != quer_uhid(
        caminho, mascara
    ) or o_aparelho_mudou(vpad, caminho, mascara)


def mascara_vestida(daemon: Any, uniq: str | None = None) -> str | None:
    """A máscara que o vpad DAQUELE aparelho veste AGORA — `None` sem vpad."""
    primario = getattr(daemon, "_gamepad_device", None)
    if uniq is None or mesma_identidade(uniq, _identidade_do_primario(daemon)):
        flavor = getattr(primario, "flavor", None)
        return flavor if isinstance(flavor, str) and flavor else None
    players = getattr(getattr(daemon, "_coop_manager", None), "_players", None)
    if isinstance(players, dict):
        for chave, player in players.items():
            if not mesma_identidade(uniq, str(chave)):
                continue
            flavor = getattr(getattr(player, "vpad", None), "flavor", None)
            return flavor if isinstance(flavor, str) and flavor else None
    return None


def _identidade_do_primario(daemon: Any) -> str | None:
    """O endereço do jogador 1, sem arrastar o `gamepad` para o import."""
    return getattr(getattr(daemon, "controller", None), "primary_uniq", None)


def _o_arquivo_de_mascaras() -> Path:
    """Onde o ``controller_masks.json`` de antes morava (import LAZY, pelo dublê dos testes)."""
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    return config_dir() / ARQUIVO_DE_MASCARAS_DE_ANTES


def _as_mascaras_do_arquivo(caminho: Path) -> list[str] | None:
    """As máscaras válidas do arquivo de antes, na ordem dele; ``None`` se ele não se lê."""
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(bruto, dict) or not isinstance(bruto.get("masks"), list):
        return None
    achadas: list[str] = []
    for entrada in bruto["masks"]:
        if isinstance(entrada, dict):
            mascara = normalizar_mascara(entrada.get("flavor"))
            if mascara is not None:
                achadas.append(mascara)
    return achadas


def o_arquivo_de_mascaras_vira_o_modo(perfil_ativo: object) -> str | None:
    """O ``controller_masks.json`` que sobrou vira o modo único e sai do disco. Uma vez.

    O arquivo era o CACHE da máscara de cada controle: com perfil ativo, o que ele
    guardava é o que o perfil declarava, e a migração do perfil já o levou ao ``mode``.
    O que só o arquivo sabia é a escolha feita sem perfil nenhum: ela vai ao padrão do
    computador (``gamepad_emulation.flag``), pela regra de desempate da migração do
    perfil; com o pad desligado o padrão não tem onde guardá-la, e o arquivo espera o
    próximo boot. O arquivo que não se lê fica onde está, intocado. Devolve a máscara
    que foi ao computador, ou ``None``.
    """
    caminho = _o_arquivo_de_mascaras()
    if not caminho.exists():
        return None
    mascaras = _as_mascaras_do_arquivo(caminho)
    if mascaras is None:
        logger.warning("arquivo_de_mascaras_de_antes_ilegivel_fica", arquivo=str(caminho))
        return None
    levada: str | None = None
    if mascaras and not (isinstance(perfil_ativo, str) and perfil_ativo):
        from hefesto_dualsense4unix.profiles.schema import _a_mascara_que_fica
        from hefesto_dualsense4unix.utils.session import (
            load_gamepad_emulation,
            save_gamepad_emulation,
        )

        ligado, _antes = load_gamepad_emulation()
        if not ligado:
            logger.info("arquivo_de_mascaras_de_antes_espera_o_pad", mascaras=mascaras)
            return None
        levada = _a_mascara_que_fica(mascaras, None)
        save_gamepad_emulation(True, levada)
    caminho.unlink(missing_ok=True)
    logger.info(
        "arquivo_de_mascaras_de_antes_virou_o_modo",
        mascaras=mascaras, perfil=perfil_ativo, ao_computador=levada,
    )
    return levada


__all__ = [
    "ARQUIVO_DE_MASCARAS_DE_ANTES",
    "mascara_efetiva",
    "mascara_vestida",
    "mascaras_validas",
    "mesma_identidade",
    "normalizar_mascara",
    "o_arquivo_de_mascaras_vira_o_modo",
    "vpad_ficou_para_tras",
]
