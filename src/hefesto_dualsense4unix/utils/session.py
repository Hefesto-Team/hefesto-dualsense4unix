"""Persistência de sessão — a escolha dela, e os flags que atravessam o reboot.

A ESCOLHA DELA TEM DOIS CAMPOS E UM DONO (`D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`,
O-HEFESTO-ABRE-NO-ULTIMO-PERFIL-E-O-FREESTYLE-DIZ-A-VERDADE-01, 01/10/2026). O
`freestyle_ligado.flag` diz se o Freestyle manda; o `session.json` guarda o
último perfil que ELA ativou, fora o Freestyle. Quem responde «qual é a escolha
dela» é :func:`a_escolha_dela`, e quem a grava é :func:`gravar_a_escolha` — só
o gesto dela (`ProfileManager.activate(origin="manual")`) chega lá; o
autoswitch, o lançamento, o restauro e o «Aplicar» não tocam em nenhum dos dois.

O `active_profile.txt` é ESPELHO da resposta (o Freestyle quando ligado),
escrito pelo mesmo escritor, para o `profile save --from-active` da CLI. Ninguém
o lê para decidir. Até 01/10 o boot o lia, e ele vencia o `session.json` na
divergência: era o seed de migração de julho, cuja convergência já aconteceu.

O `store.active_profile` do daemon (publicado por `daemon.status`/`state_full`)
é o perfil que VALE agora — outra pergunta: o jogo aberto entra por cima da
escolha, e sai devolvendo-a.

Nunca propaga exceção: falha silenciosa em ambos os sentidos.
"""
from __future__ import annotations

import contextlib
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
    """Escreve `active_profile.txt`, o espelho da escolha (ver o cabeçalho)."""
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir as _config_dir

    try:
        marker = _config_dir(ensure=True) / _ACTIVE_MARKER_FILE
        marker.write_text(name + "\n", encoding="utf-8")
        logger.debug("active_marker_saved", profile=name)
    except Exception as exc:
        logger.warning("active_marker_write_failed", profile=name, err=str(exc))


def read_active_marker() -> str | None:
    """Lê `active_profile.txt`, ou None se ausente/vazio."""
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir as _config_dir

    try:
        marker = _config_dir() / _ACTIVE_MARKER_FILE
        if not marker.exists():
            return None
        content = marker.read_text(encoding="utf-8").strip()
        return content or None
    except Exception:
        return None


def _e_o_freestyle(nome: object) -> bool:
    """O nome aponta o Freestyle? Pelo slug, como `profiles.manager.e_o_freestyle`."""
    from hefesto_dualsense4unix.profiles.loader import SLUG_DO_PADRAO
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    return isinstance(nome, str) and mesmo_slug(nome, SLUG_DO_PADRAO)


def _o_perfil_carrega(nome: str) -> bool:
    """Há arquivo para este nome? Pelo dono de «nome vira arquivo», sem semear."""
    from hefesto_dualsense4unix.profiles.loader import arquivo_do_perfil

    try:
        return arquivo_do_perfil(nome) is not None
    except Exception:
        return False


def a_escolha_dela(*, freestyle_ligado: bool | None = None) -> str | None:
    """A escolha dela: o Freestyle ligado, ou o último perfil que ela ativou."""
    from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO

    try:
        ligado = load_freestyle_ligado() if freestyle_ligado is None else freestyle_ligado
        if ligado and _o_perfil_carrega(NOME_DO_PADRAO):
            return NOME_DO_PADRAO
        nome = load_last_profile()
        if nome and not _e_o_freestyle(nome) and _o_perfil_carrega(nome):
            return nome
    except Exception as exc:
        logger.debug("a_escolha_dela_ilegivel", err=str(exc))
    return None


def resolve_boot_profile() -> str | None:
    """O nome que o boot restaura — a escolha dela (:func:`a_escolha_dela`)."""
    return a_escolha_dela()


def _apagar_o_espelho() -> None:
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir as _config_dir

    with contextlib.suppress(Exception):
        (_config_dir() / _ACTIVE_MARKER_FILE).unlink(missing_ok=True)


def espelhar_a_escolha() -> None:
    """O `active_profile.txt` passa a dizer a escolha de agora; sem ela, sai."""
    nome = a_escolha_dela()
    if nome:
        save_active_marker(nome)
    else:
        _apagar_o_espelho()


def gravar_a_escolha(nome: str) -> None:
    """O escritor único da escolha dela: o `session.json` e o espelho."""
    if not _e_o_freestyle(nome):
        save_last_profile(nome)
    espelhar_a_escolha()


def esquecer_a_escolha(nome: str | None = None) -> None:
    """Zera o `last_profile` — todo, ou só se ele aponta `nome` (pelo slug)."""
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    atual = load_last_profile()
    if atual is None:
        return
    if nome is not None and not mesmo_slug(atual, nome) and atual != nome:
        return
    path = _session_path()
    try:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".session_")
        try:
            os.write(fd, b"{}")
        finally:
            os.close(fd)
        os.replace(tmp, path)
        logger.info("a_escolha_dela_esquecida", nome=atual)
    except Exception as exc:
        logger.debug("session_save_failed", err=str(exc))
    espelhar_a_escolha()


_MARCA_DA_ESCOLHA = ".a_escolha_dela_migrada"
_COPIA_DA_SESSAO = "session-antes-da-escolha.json"


def _so_o_freestyle_na_pasta() -> bool:
    """A pasta dos perfis não tem perfil além do Freestyle? Nunca levanta."""
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    try:
        return all(_e_o_freestyle(arq.stem) for arq in profiles_dir().glob("*.json"))
    except OSError:
        return False


def migrar_a_escolha_dela() -> str | None:
    """Uma vez só, com marca: a máquina nova e a sessão que apontava o Freestyle."""
    import shutil

    from filelock import FileLock

    try:
        base = config_dir(ensure=True)
        marca = base / _MARCA_DA_ESCOLHA
        if marca.exists():
            return None
        with FileLock(str(base / f"{_MARCA_DA_ESCOLHA}.lock")):
            if marca.exists():
                return None
            with contextlib.suppress(OSError):
                _o_cadeado_antigo_vira_freestyle(base)
            sessao = base / _SESSION_FILE
            flag = base / _FREESTYLE_LIGADO_FLAG_FILE
            if not sessao.exists() and not flag.exists() and _so_o_freestyle_na_pasta():
                save_freestyle_ligado(True)
                desfecho = "maquina_nova_nasce_acesa"
            elif not flag.exists() and _e_o_freestyle(load_last_profile()):
                shutil.copy2(sessao, base / _COPIA_DA_SESSAO)
                esquecer_a_escolha()
                desfecho = "freestyle_desligado_vira_sem_escolha"
            else:
                desfecho = "nada_a_mudar"
            espelhar_a_escolha()
            marca.write_text("done\n", encoding="utf-8")
    except Exception as exc:
        logger.warning("a_escolha_dela_nao_migrou", err=str(exc))
        return None
    logger.info("a_escolha_dela_migrada", desfecho=desfecho)
    return desfecho


_PAUSED_FLAG_FILE = "paused.flag"


def save_paused_state(paused: bool) -> None:
    """Persiste se o daemon está pausado (FEAT-DAEMON-PAUSE-RESUME-01)."""
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


_FREESTYLE_LIGADO_FLAG_FILE = "freestyle_ligado.flag"
_FLAG_DO_CADEADO_ANTIGO = "autoswitch_locked.flag"


def save_freestyle_ligado(ligado: bool) -> None:
    """Persiste o Modo Freestyle (O-FREESTYLE-E-UMA-CAMADA-SO-01, 28/09/2026)."""
    try:
        flag = config_dir(ensure=True) / _FREESTYLE_LIGADO_FLAG_FILE
        if ligado:
            flag.write_text("1\n", encoding="utf-8")
        else:
            flag.unlink(missing_ok=True)
        logger.debug("freestyle_ligado_salvo", ligado=ligado)
    except Exception as exc:
        logger.debug("freestyle_ligado_nao_salvou", err=str(exc))


def _o_cadeado_antigo_vira_freestyle(base: Path) -> None:
    """One-shot: o `autoswitch_locked.flag` LIGADO vira `freestyle_ligado.flag`."""
    antigo = base / _FLAG_DO_CADEADO_ANTIGO
    if not antigo.exists():
        return
    novo = base / _FREESTYLE_LIGADO_FLAG_FILE
    if not novo.exists():
        novo.write_text("1\n", encoding="utf-8")
    antigo.unlink(missing_ok=True)
    logger.info("cadeado_antigo_virou_freestyle_ligado")


def load_freestyle_ligado() -> bool:
    """True se o Modo Freestyle foi deixado ligado na sessão anterior."""
    try:
        base = config_dir()
        with contextlib.suppress(OSError):
            _o_cadeado_antigo_vira_freestyle(base)
        return (base / _FREESTYLE_LIGADO_FLAG_FILE).exists()
    except Exception:
        return False


_NATIVE_MODE_FLAG_FILE = "native_mode.flag"


def save_native_mode(active: bool, *, emu_stash: dict[str, Any] | None = None) -> None:
    """Persiste o Modo Nativo (FEAT-NATIVE-MODE-01) — existe = ativo."""
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
    """Retorna (ativo, emu_stash) da sessão anterior."""
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
            stash = {}
        return True, stash
    except Exception:
        return False, {}


_MOUSE_EMULATION_FLAG_FILE = "mouse_emulation.flag"


def _read_mouse_flag() -> dict[str, Any] | None:
    """Lê o flag de mouse cru: ``None`` = arquivo ausente (nunca configurada)."""
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
        return {}
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
    """Persiste a PREFERÊNCIA de emulação de mouse: toggle + velocidades."""
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
    """Preferência de mouse persistida: ``(ligada|None, speed, scroll_speed)``."""
    data = _read_mouse_flag()
    if data is None:
        return None, None, None
    return bool(data.get("enabled", True)), data.get("speed"), data.get("scroll_speed")


def load_mouse_emulation() -> tuple[bool, int | None, int | None]:
    """Retorna ``(ligada, speed, scroll_speed)`` da sessão anterior."""
    enabled, speed, scroll_speed = load_mouse_preference()
    return bool(enabled), speed, scroll_speed


# `save_mouse_emulation`), ou seja, não neutralizavam nada.


_KEYBOARD_EMULATION_FLAG_FILE = "keyboard_emulation.flag"


def save_keyboard_emulation(enabled: bool) -> None:
    """Persiste a PREFERÊNCIA de emulação de teclado (EMULACAO-NO-JOGO-01).

    Molde exato do `save_mouse_emulation` (HARM-06): JSON com a chave
    ``enabled``, gravado nos DOIS sentidos — o "off" é uma decisão dela e tem de
    ficar escrito, não apagado. Até esta sprint o teclado emulado não tinha
    lugar nenhum onde ser desligado: o default `True` de
    `DaemonConfig.keyboard_emulation_enabled` vencia sempre, e o R1 (Alt+Tab no
    mapa default) trocava de aplicativo dentro do jogo dela.

    Não usa `session.json`: `save_last_profile` reescreve aquele arquivo inteiro.
    Best-effort: nunca propaga exceção (o IPC/boot não pode cair por I/O).
    """
    try:
        flag = config_dir(ensure=True) / _KEYBOARD_EMULATION_FLAG_FILE
        flag.write_text(json.dumps({"enabled": bool(enabled)}) + "\n", encoding="utf-8")
        logger.debug("keyboard_emulation_state_saved", enabled=enabled)
    except Exception as exc:
        logger.debug("keyboard_emulation_state_save_failed", err=str(exc))


def load_keyboard_preference() -> bool | None:
    """Preferência persistida do teclado emulado: ``True``/``False``/``None``.

    ``None`` = **nunca configurada** (arquivo ausente, que é o caso de toda
    instalação anterior a esta sprint). Quem lê no boot mantém, nesse caso, o
    default histórico da config (`DaemonConfig.keyboard_emulation_enabled`,
    hoje `True`) — ver a precedência em `daemon/lifecycle.py:481-486`.

    Tolerante a conteúdo legado/malformado do mesmo jeito que
    `_read_mouse_flag`: arquivo vazio ou JSON inválido conta como "ligada" (era
    o que existir-o-arquivo queria dizer), tipo errado em ``enabled`` também.
    Erro de I/O vira ``None`` (nunca decidiu) — fail-safe é não mudar nada.
    """
    try:
        flag = config_dir() / _KEYBOARD_EMULATION_FLAG_FILE
        if not flag.exists():
            return None
        content = flag.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not content:
        return True
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return True
    if not isinstance(data, dict):
        return True
    raw = data.get("enabled")
    if isinstance(raw, bool):
        return raw
    return True


# `load_keyboard_emulation_enabled` MOROU AQUI, e foi PODADA em 26/08/2026.
# `DaemonConfig.keyboard_emulation_enabled = True`, e o boot só o sobrescreve


_PLUGINS_FLAG_FILE = "plugins.flag"


def save_plugins_enabled(enabled: bool) -> bool:
    """Grava a escolha de ligar os plugins (``hefesto plugin ligar|desligar``).

    Plugin de terceiro roda com os privilégios do daemon: ligado só pela mão
    de quem o instalou, e desligado é o padrão (OS-INTERRUPTORES-QUE-NINGUEM-LIGA-01,
    02/10/2026). Vale na próxima subida do daemon. ``False`` = não gravou.
    """
    try:
        flag = config_dir(ensure=True) / _PLUGINS_FLAG_FILE
        flag.write_text(json.dumps({"enabled": bool(enabled)}) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.debug("plugins_flag_save_failed", err=str(exc))
        return False
    return True


def load_plugins_enabled() -> bool:
    """A escolha gravada por :func:`save_plugins_enabled`; sem arquivo, desligado."""
    try:
        flag = config_dir() / _PLUGINS_FLAG_FILE
        if not flag.exists():
            return False
        data = json.loads(flag.read_text(encoding="utf-8") or "{}")
    except Exception:
        return False
    return isinstance(data, dict) and data.get("enabled") is True


_METRICS_FLAG_FILE = "metrics.flag"


def save_metrics_enabled(enabled: bool) -> bool:
    """Grava a escolha de expor as métricas (``hefesto metrics ligar|desligar``).

    Ferramenta de diagnóstico, desligada por padrão: só a mão de quem quer
    medir a liga (OS-INTERRUPTORES-QUE-NINGUEM-LIGA-01, 03/10/2026). Vale na
    próxima subida do daemon. ``False`` = não gravou.
    """
    try:
        flag = config_dir(ensure=True) / _METRICS_FLAG_FILE
        flag.write_text(json.dumps({"enabled": bool(enabled)}) + "\n", encoding="utf-8")
    except Exception as exc:
        logger.debug("metrics_flag_save_failed", err=str(exc))
        return False
    return True


def load_metrics_enabled() -> bool:
    """A escolha gravada por :func:`save_metrics_enabled`; sem arquivo, desligada."""
    try:
        flag = config_dir() / _METRICS_FLAG_FILE
        if not flag.exists():
            return False
        data = json.loads(flag.read_text(encoding="utf-8") or "{}")
    except Exception:
        return False
    return isinstance(data, dict) and data.get("enabled") is True


_GAMEPAD_EMULATION_FLAG_FILE = "gamepad_emulation.flag"

_GAMEPAD_DISABLED_FLAG_FILE = "gamepad_disabled.flag"


def save_gamepad_emulation(enabled: bool, flavor: str | None = None) -> None:
    """Persiste o estado do gamepad virtual (FEAT-DSX-GAMEPAD-FLAVOR-01)."""
    try:
        cfg = config_dir(ensure=True)
        flag = cfg / _GAMEPAD_EMULATION_FLAG_FILE
        optout = cfg / _GAMEPAD_DISABLED_FLAG_FILE
        if enabled:
            flag.write_text(f"{(flavor or 'dualsense').strip()}\n", encoding="utf-8")
            optout.unlink(missing_ok=True)
        else:
            flag.unlink(missing_ok=True)
            optout.write_text("1\n", encoding="utf-8")
        logger.debug("gamepad_emulation_state_saved", enabled=enabled, flavor=flavor)
    except Exception as exc:
        logger.debug("gamepad_emulation_state_save_failed", err=str(exc))


def load_gamepad_preference() -> tuple[bool | None, str | None]:
    """Preferência PERSISTIDA do gamepad virtual: ``(ligado|None, flavor)``."""
    try:
        cfg = config_dir()
        flag = cfg / _GAMEPAD_EMULATION_FLAG_FILE
        if flag.exists():
            return True, (flag.read_text(encoding="utf-8").strip() or None)
        if (cfg / _GAMEPAD_DISABLED_FLAG_FILE).exists():
            return False, None
        return None, None
    except Exception:
        return None, None


_GAMEPAD_CAMINHO_FLAG_FILE = "gamepad_caminho.flag"

ORIGEM_DO_GESTO_FORA_DO_JOGO = "gesto_fora_do_jogo"
ORIGEM_DA_MIGRACAO_UNICA = "migracao_unica"


def save_gamepad_caminho(caminho: str | None, *, origem: str | None = None) -> None:
    """Persiste o caminho escolhido, com a origem e a hora; vazio apaga. Best-effort."""
    try:
        alvo = config_dir(ensure=True) / _GAMEPAD_CAMINHO_FLAG_FILE
        if caminho and caminho.strip():
            from datetime import datetime

            dado = {
                "caminho": caminho.strip(),
                "origem": origem,
                "quando": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            alvo.write_text(json.dumps(dado, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            alvo.unlink(missing_ok=True)
        logger.debug("gamepad_caminho_salvo", caminho=caminho, origem=origem)
    except Exception as exc:
        logger.debug("gamepad_caminho_save_failed", err=str(exc))


def load_gamepad_caminho_com_origem() -> tuple[str | None, str | None]:
    """``(caminho, origem)`` gravados, crus. O arquivo antigo tem origem ``None``."""
    try:
        alvo = config_dir() / _GAMEPAD_CAMINHO_FLAG_FILE
        if not alvo.exists():
            return None, None
        texto = alvo.read_text(encoding="utf-8").strip()
    except Exception:
        return None, None
    if not texto:
        return None, None
    if texto.startswith("{"):
        try:
            dado = json.loads(texto)
        except ValueError:
            return None, None
        if not isinstance(dado, dict):
            return None, None
        caminho = dado.get("caminho")
        origem = dado.get("origem")
        return (
            caminho if isinstance(caminho, str) and caminho else None,
            origem if isinstance(origem, str) and origem else None,
        )
    return texto, None


def load_gamepad_emulation() -> tuple[bool, str | None]:
    """Retorna (ligado, flavor) do gamepad virtual da sessão anterior."""
    enabled, flavor = load_gamepad_preference()
    return bool(enabled), flavor


_COOP_DISABLED_FLAG_FILE = "coop_disabled.flag"
_COOP_ENABLED_FLAG_FILE_LEGACY = "coop_enabled.flag"


def save_coop_enabled(enabled: bool) -> None:
    """Faxina dos flags de co-op — NUNCA grava opt-out (lápide, 06/08/2026)."""
    try:
        cfg = config_dir(ensure=True)
        (cfg / _COOP_ENABLED_FLAG_FILE_LEGACY).unlink(missing_ok=True)
        (cfg / _COOP_DISABLED_FLAG_FILE).unlink(missing_ok=True)
        logger.debug("coop_enabled_state_saved", enabled=True, pedido=bool(enabled))
    except Exception as exc:
        logger.debug("coop_enabled_state_save_failed", err=str(exc))


_COOP_OPTOUT_MIGRATION_MARKER = ".coop_optout_migrated"


MARCA_DO_CAMINHO_DEVOLVIDO = ".caminho_xbox_do_vazamento_devolvido"
MARCA_DA_MASCARA_DEVOLVIDA = ".mascara_xbox_do_vazamento_devolvida"


def migracao_ainda_nao_feita(marca: str) -> bool:
    """True só na primeira chamada: grava a marca e deixa a migração rodar."""
    try:
        alvo = config_dir(ensure=True) / marca
        if alvo.exists():
            return False
        alvo.write_text("1\n", encoding="utf-8")
        return True
    except Exception as exc:
        logger.debug("migracao_marca_falhou", marca=marca, err=str(exc))
        return False


def migrate_coop_optout() -> bool:
    """One-shot: apaga o `coop_disabled.flag` das versões antigas. True = migrou."""
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


__all__ = [
    "a_escolha_dela",
    "espelhar_a_escolha",
    "esquecer_a_escolha",
    "gravar_a_escolha",
    "load_freestyle_ligado",
    "load_gamepad_caminho_com_origem",
    "load_gamepad_emulation",
    "load_gamepad_preference",
    "load_keyboard_preference",
    "load_last_profile",
    "load_metrics_enabled",
    "load_mouse_emulation",
    "load_mouse_preference",
    "load_paused_state",
    "load_plugins_enabled",
    "migrar_a_escolha_dela",
    "read_active_marker",
    "resolve_boot_profile",
    "save_active_marker",
    "save_coop_enabled",
    "save_freestyle_ligado",
    "save_gamepad_caminho",
    "save_gamepad_emulation",
    "save_keyboard_emulation",
    "save_last_profile",
    "save_metrics_enabled",
    "save_mouse_emulation",
    "save_paused_state",
    "save_plugins_enabled",
]
