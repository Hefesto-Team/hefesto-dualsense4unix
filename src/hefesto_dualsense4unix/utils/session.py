"""Persistência de sessão — salva e carrega o último perfil ativo do usuário.

O arquivo `~/.config/hefesto-dualsense4unix/session.json` guarda apenas o nome do
último perfil explicitamente ativado. O daemon lê esse arquivo no
startup e re-ativa o perfil automaticamente.

CLUSTER-IPC-STATE-PROFILE-01 (Bug B): adicional `active_profile.txt` é marker
secundário para a CLI legada (`hefesto-dualsense4unix profile current`).
`session.json` continua sendo o canônico para o daemon restaurar no boot.
Ambos são escritos em paridade pelo handler IPC `profile.switch`.

Nunca propaga exceção: falha silenciosa em ambos os sentidos.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import config_dir

logger = get_logger(__name__)

_SESSION_FILE = "session.json"
_PROFILE_KEY = "last_profile"
_ACTIVE_MARKER_FILE = "active_profile.txt"


def _session_path() -> Path:
    return config_dir(ensure=True) / _SESSION_FILE


def save_last_profile(name: str) -> None:
    """Persiste o nome do último perfil ativado em session.json."""
    path = _session_path()
    try:
        data = json.dumps({_PROFILE_KEY: name}, ensure_ascii=False)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".session_")
        try:
            os.write(fd, data.encode())
        finally:
            os.close(fd)
        os.replace(tmp, path)
        logger.debug("session_saved", last_profile=name)
    except Exception as exc:
        logger.debug("session_save_failed", err=str(exc))


def load_last_profile() -> str | None:
    """Retorna o nome do último perfil salvo, ou None se não houver."""
    path = _session_path()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        name = data.get(_PROFILE_KEY)
        if isinstance(name, str) and name.strip():
            logger.debug("session_loaded", last_profile=name)
            return name.strip()
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    except Exception as exc:
        logger.debug("session_load_failed", err=str(exc))
    return None


def save_active_marker(name: str) -> None:
    """Escreve `active_profile.txt` (marker da CLI legada).

    Best-effort: falha silenciosa para não quebrar o IPC chamador.
    `session.json` segue sendo o canônico para o daemon.

    Import lazy de `config_dir` para preservar o ponto de monkeypatch nos
    testes (`monkeypatch.setattr(xdg_paths, "config_dir", ...)`).
    """
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir as _config_dir

    try:
        marker = _config_dir(ensure=True) / _ACTIVE_MARKER_FILE
        marker.write_text(name + "\n", encoding="utf-8")
        logger.debug("active_marker_saved", profile=name)
    except Exception as exc:
        logger.warning("active_marker_write_failed", profile=name, err=str(exc))


def read_active_marker() -> str | None:
    """Lê `active_profile.txt`, ou None se ausente/vazio.

    Marker secundário usado pela CLI (`hefesto-dualsense4unix profile current`).
    Daemon usa `load_last_profile` (session.json) no restore.

    Import lazy de `config_dir` (mesma justificativa de `save_active_marker`).
    """
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir as _config_dir

    try:
        marker = _config_dir() / _ACTIVE_MARKER_FILE
        if not marker.exists():
            return None
        content = marker.read_text(encoding="utf-8").strip()
        return content or None
    except Exception:
        return None


_PAUSED_FLAG_FILE = "paused.flag"


def save_paused_state(paused: bool) -> None:
    """Persiste se o daemon está pausado (FEAT-DAEMON-PAUSE-RESUME-01).

    Usa um arquivo-flag em config_dir (existe = pausado) para o daemon retomar
    pausado após restart. Best-effort: nunca propaga exceção.
    """
    try:
        flag = config_dir(ensure=True) / _PAUSED_FLAG_FILE
        if paused:
            flag.write_text("1\n", encoding="utf-8")
        else:
            flag.unlink(missing_ok=True)
        logger.debug("paused_state_saved", paused=paused)
    except Exception as exc:
        logger.debug("paused_state_save_failed", err=str(exc))


def load_paused_state() -> bool:
    """Retorna True se o daemon foi deixado pausado na sessão anterior."""
    try:
        return (config_dir() / _PAUSED_FLAG_FILE).exists()
    except Exception:
        return False


_NATIVE_MODE_FLAG_FILE = "native_mode.flag"


def save_native_mode(active: bool, *, emu_stash: dict[str, Any] | None = None) -> None:
    """Persiste o Modo Nativo (FEAT-NATIVE-MODE-01) — existe = ativo.

    O conteúdo é JSON com o STASH da emulação PRÉ-nativo (`emu_stash`) para
    restaurar mouse/gamepad ao desligar (o release apaga os flags próprios).
    Conteúdo legado `"1\n"` é tolerado no load. Best-effort: nunca propaga.
    """
    try:
        flag = config_dir(ensure=True) / _NATIVE_MODE_FLAG_FILE
        if active:
            flag.write_text(
                json.dumps(emu_stash or {}), encoding="utf-8"
            )
        else:
            flag.unlink(missing_ok=True)
        logger.debug("native_mode_saved", active=active)
    except Exception as exc:
        logger.debug("native_mode_save_failed", err=str(exc))


def load_native_mode() -> tuple[bool, dict[str, Any]]:
    """Retorna (ativo, emu_stash) da sessão anterior.

    `emu_stash`: {"mouse": [enabled, speed, scroll], "gamepad": [enabled, flavor]}
    ou {} (ausente/legado). Tolerante a conteúdo legado `"1"` e a JSON inválido.
    """
    try:
        path = config_dir() / _NATIVE_MODE_FLAG_FILE
        if not path.exists():
            return False, {}
        raw = path.read_text(encoding="utf-8").strip()
        try:
            stash = json.loads(raw) if raw else {}
            if not isinstance(stash, dict):
                stash = {}
        except (json.JSONDecodeError, ValueError):
            stash = {}  # legado "1\n"
        return True, stash
    except Exception:
        return False, {}


_MOUSE_EMULATION_FLAG_FILE = "mouse_emulation.flag"


def _read_mouse_flag() -> dict[str, Any] | None:
    """Lê o flag de mouse cru: ``None`` = arquivo ausente (nunca configurada).

    Tolerante ao conteúdo legado ``"1\\n"`` (pré-JSON), a JSON malformado e a
    tipos errados: devolve ``{}`` (= o arquivo existe, sem dados aproveitáveis),
    nunca levanta. Valores não-inteiros de velocidade são descartados aqui, no
    ponto único de parse.
    """
    try:
        flag = config_dir() / _MOUSE_EMULATION_FLAG_FILE
        if not flag.exists():
            return None
        content = flag.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not content:
        return {}
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}  # conteúdo legado "1\n" → arquivo existe, sem dados
    if not isinstance(data, dict):
        return {}
    out: dict[str, Any] = {}
    raw_enabled = data.get("enabled")
    if isinstance(raw_enabled, bool):
        out["enabled"] = raw_enabled
    for key in ("speed", "scroll_speed"):
        raw = data.get(key)
        if isinstance(raw, int) and not isinstance(raw, bool):
            out[key] = raw
    return out


def save_mouse_emulation(
    enabled: bool,
    speed: int | None = None,
    scroll_speed: int | None = None,
) -> None:
    """Persiste a PREFERÊNCIA de emulação de mouse: toggle + velocidades.

    FEAT-MOUSE-CURSOR-FEEL-01 + HARM-06 (SPRINT-HARMONIA-01). O arquivo carrega
    JSON ``{"enabled": bool, "speed": N, "scroll_speed": M}`` e agora existe
    também quando a emulação está DESLIGADA: antes o "off" era gravado apagando
    o arquivo, o que confundia "a usuária desligou" com "nunca foi configurada".
    O modo "Controlar o PC" precisa distinguir os dois — ele liga o mouse por
    default no segundo caso e respeita o "off" no primeiro.

    ``speed``/``scroll_speed`` omitidos PRESERVAM o que já estava gravado (o
    desligar não passa velocidades e não pode zerar a escolha da usuária).
    Arquivo ausente segue significando "nunca configurada"; conteúdo legado sem
    a chave ``enabled`` (inclusive o ``"1\\n"`` pré-JSON) segue contando como
    ligada — era o que existir-o-arquivo queria dizer.

    NÃO usa session.json: `save_last_profile` reescreve aquele arquivo inteiro
    e apagaria as velocidades. Best-effort: nunca propaga exceção.
    """
    try:
        anterior = _read_mouse_flag() or {}
        payload: dict[str, Any] = {"enabled": bool(enabled)}
        for key, valor in (("speed", speed), ("scroll_speed", scroll_speed)):
            if valor is not None:
                payload[key] = int(valor)
            elif key in anterior:
                payload[key] = anterior[key]
        flag = config_dir(ensure=True) / _MOUSE_EMULATION_FLAG_FILE
        flag.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        logger.debug(
            "mouse_emulation_state_saved",
            enabled=enabled,
            speed=payload.get("speed"),
            scroll_speed=payload.get("scroll_speed"),
        )
    except Exception as exc:
        logger.debug("mouse_emulation_state_save_failed", err=str(exc))


def load_mouse_preference() -> tuple[bool | None, int | None, int | None]:
    """Preferência de mouse persistida: ``(ligada|None, speed, scroll_speed)``.

    HARM-06: ``None`` no primeiro campo = **nunca configurada** (arquivo
    ausente) — quem entra em "Controlar o PC" liga o mouse por default nesse
    caso, em vez de deixar o controle sem função nenhuma. ``False`` = a usuária
    desligou de propósito, e sair-e-voltar do modo tem que respeitar isso.

    Velocidades ``None`` (flag legado sem elas) = usar os defaults da config.
    """
    data = _read_mouse_flag()
    if data is None:
        return None, None, None
    # Sem a chave `enabled` o arquivo é de uma versão antiga, quando existir
    # JÁ significava ligada.
    return bool(data.get("enabled", True)), data.get("speed"), data.get("scroll_speed")


def load_mouse_emulation() -> tuple[bool, int | None, int | None]:
    """Retorna ``(ligada, speed, scroll_speed)`` da sessão anterior.

    ``(False, None, None)`` se a flag não existir (nunca configurada = não
    ligar sozinha no boot). Quem precisa distinguir "desligada" de "nunca
    configurada" usa `load_mouse_preference`.
    """
    enabled, speed, scroll_speed = load_mouse_preference()
    return bool(enabled), speed, scroll_speed


def save_mouse_emulation_enabled(enabled: bool) -> None:
    """Wrapper legado (FEAT-MOUSE-PERSIST-01) — persiste só o toggle.

    Delega para `save_mouse_emulation` sem velocidades (quando ligada, o JSON
    sai vazio e o load devolve speeds ``None`` → defaults). Preferir a função
    nova, que grava as velocidades junto.
    """
    save_mouse_emulation(enabled)


def load_mouse_emulation_enabled() -> bool:
    """Wrapper legado — retorna só se a emulação foi deixada ligada."""
    return load_mouse_emulation()[0]


_GAMEPAD_EMULATION_FLAG_FILE = "gamepad_emulation.flag"


def save_gamepad_emulation(enabled: bool, flavor: str | None = None) -> None:
    """Persiste o estado do gamepad virtual (FEAT-DSX-GAMEPAD-FLAVOR-01).

    Flag-file em config_dir cujo conteúdo é o flavor (`dualsense`/`xbox`) quando
    ligado; o arquivo é removido quando desligado. Assim o daemon restaura tanto
    o liga/desliga quanto a máscara após restart/reboot. Best-effort.
    """
    try:
        flag = config_dir(ensure=True) / _GAMEPAD_EMULATION_FLAG_FILE
        if enabled:
            flag.write_text(f"{(flavor or 'dualsense').strip()}\n", encoding="utf-8")
        else:
            flag.unlink(missing_ok=True)
        logger.debug("gamepad_emulation_state_saved", enabled=enabled, flavor=flavor)
    except Exception as exc:
        logger.debug("gamepad_emulation_state_save_failed", err=str(exc))


def load_gamepad_emulation() -> tuple[bool, str | None]:
    """Retorna (ligado, flavor) do gamepad virtual da sessão anterior.

    `(False, None)` se a flag não existir. Se existir mas vazia, assume ligado
    com flavor None (o caller normaliza para o default).
    """
    try:
        flag = config_dir() / _GAMEPAD_EMULATION_FLAG_FILE
        if not flag.exists():
            return False, None
        flavor = flag.read_text(encoding="utf-8").strip() or None
        return True, flavor
    except Exception:
        return False, None


#: FEAT-COOP-DEFAULT-ON-01: co-op local é o PADRÃO (cada controle = um
#: jogador). O que se persiste é o OPT-OUT: flag presente = usuária desligou.
_COOP_DISABLED_FLAG_FILE = "coop_disabled.flag"
#: Semântica antiga (presente = ligado) — removido na primeira escrita nova.
_COOP_ENABLED_FLAG_FILE_LEGACY = "coop_enabled.flag"


def save_coop_enabled(enabled: bool) -> None:
    """Persiste a escolha da usuária sobre o co-op local.

    FEAT-COOP-DEFAULT-ON-01: com 2+ controles, "cada controle = um jogador" é
    o comportamento esperado por padrão; grava-se apenas o opt-out
    (`coop_disabled.flag` existe = desligado de propósito). Migra o flag
    legado `coop_enabled.flag` apagando-o. Best-effort: nunca propaga exceção.
    """
    try:
        cfg = config_dir(ensure=True)
        (cfg / _COOP_ENABLED_FLAG_FILE_LEGACY).unlink(missing_ok=True)
        flag = cfg / _COOP_DISABLED_FLAG_FILE
        if enabled:
            flag.unlink(missing_ok=True)
        else:
            flag.write_text("1\n", encoding="utf-8")
        logger.debug("coop_enabled_state_saved", enabled=enabled)
    except Exception as exc:
        logger.debug("coop_enabled_state_save_failed", err=str(exc))


#: Marker da migração do opt-out de co-op (LEIGO-01). Ao lado do flag.
_COOP_OPTOUT_MIGRATION_MARKER = ".coop_optout_migrated"


def migrate_coop_optout() -> bool:
    """One-shot: apaga o `coop_disabled.flag` das versões antigas. True = migrou.

    LEIGO-01: o checkbox "Cada controle é um jogador" saiu da tela — cada
    controle é um jogador, sempre. Quem o desmarcou numa versão JÁ LANÇADA tem o
    opt-out gravado em disco, e ele sobrevive ao upgrade: o co-op ficaria
    desligado **sem nenhum caminho de volta na interface**.

    Apagar é a leitura certa da decisão de produto ("ninguém conecta dois
    controles no PC esperando que os dois controlem a mesma pessoa"), e espelha o
    que o `save_coop_enabled` já fazia com o flag legado. Idempotente via marker
    próprio: se alguém desligar o co-op pela CLI depois da migração, a escolha
    fica de pé.

    Best-effort: nunca propaga exceção — o daemon sobe de qualquer jeito.
    """
    try:
        cfg = config_dir(ensure=True)
        marker = cfg / _COOP_OPTOUT_MIGRATION_MARKER
        if marker.exists():
            return False
        flag = cfg / _COOP_DISABLED_FLAG_FILE
        migrou = flag.exists()
        flag.unlink(missing_ok=True)
        marker.write_text("1\n", encoding="utf-8")
        if migrou:
            logger.info("coop_optout_migrado", motivo="o checkbox saiu da UI (LEIGO-01)")
        return migrou
    except Exception as exc:
        logger.debug("coop_optout_migracao_falhou", err=str(exc))
        return False


def load_coop_enabled() -> bool:
    """True (padrão) salvo se a usuária desligou o co-op (opt-out persistido)."""
    try:
        return not (config_dir() / _COOP_DISABLED_FLAG_FILE).exists()
    except Exception:
        return True


__all__ = [
    "load_coop_enabled",
    "load_gamepad_emulation",
    "load_last_profile",
    "load_mouse_emulation",
    "load_mouse_emulation_enabled",
    "load_mouse_preference",
    "load_paused_state",
    "read_active_marker",
    "save_active_marker",
    "save_coop_enabled",
    "save_gamepad_emulation",
    "save_last_profile",
    "save_mouse_emulation",
    "save_mouse_emulation_enabled",
    "save_paused_state",
]
