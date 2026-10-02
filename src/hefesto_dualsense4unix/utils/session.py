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
    """Escreve `active_profile.txt`, o espelho da escolha (ver o cabeçalho).

    Best-effort: falha silenciosa para não quebrar o IPC chamador. Quem chama
    para decidir é só :func:`espelhar_a_escolha`; os chamadores de fora que
    sobram escrevem o mesmo nome que ela escreveria.

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

    O espelho lido pelo `profile save --from-active` da CLI. Ninguém o lê para
    decidir: a escolha é de :func:`a_escolha_dela`.

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


def _e_o_freestyle(nome: object) -> bool:
    """O nome aponta o Freestyle? Pelo slug, como `profiles.manager.e_o_freestyle`.

    Cópia de UMA linha, e de propósito: este módulo é o mais baixo da casa, e
    importar o `manager` daqui puxaria o produto inteiro para ler um flag.
    """
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
    """A escolha dela: o Freestyle ligado, ou o último perfil que ela ativou.

    `D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`, item 1. Ligado (e com o arquivo),
    é o Freestyle; desligado, é o `last_profile`, se ele carrega e não é o
    Freestyle; senão, `None` — «sem escolha» (item 10): o chip diz «—» e os
    gestos que gravam recusam. O Freestyle desligado nunca é a escolha (item 6).

    `freestyle_ligado`: o botão segundo quem pergunta. O daemon passa a
    memória dele (`profiles.manager.o_freestyle_manda`), que é quem a ativação
    obedece; sem ele, vale o flag do disco. Medido em 01/10/2026: o botão que
    apaga pergunta ANTES de o flag virar, e o disco ainda dizia «aceso» — a
    escolha voltava o próprio Freestyle, com o modo desligado.

    Quem pergunta: o boot e a reconexão, a volta do jogo (o autoswitch numa
    janela que não é jogo), o botão desligado, a saída do Modo Nativo, o
    rodapé e a perna do disco do chip. Nunca levanta.
    """
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
    """O nome que o boot restaura — a escolha dela (:func:`a_escolha_dela`).

    O nome fica porque réguas de outras sprints o trocam por dublê para dizer
    «a escolha dela é X»; o corpo pergunta ao dono na hora da chamada, então
    um dublê em qualquer um dos dois nomes vale para quem chama este. Até
    01/10/2026 o marcador `active_profile.txt` vencia o `session.json` na
    divergência (o seed de julho, PERFIL-03); o marcador virou espelho.
    """
    return a_escolha_dela()


def _apagar_o_espelho() -> None:
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir as _config_dir

    with contextlib.suppress(Exception):
        (_config_dir() / _ACTIVE_MARKER_FILE).unlink(missing_ok=True)


def espelhar_a_escolha() -> None:
    """O `active_profile.txt` passa a dizer a escolha de agora; sem ela, sai.

    Chamado pelo escritor da escolha e pelo dono do Modo Freestyle
    (`profiles.manager.ligar_o_freestyle`): ligar e desligar o botão muda a
    resposta sem mudar o `session.json`.
    """
    nome = a_escolha_dela()
    if nome:
        save_active_marker(nome)
    else:
        _apagar_o_espelho()


def gravar_a_escolha(nome: str) -> None:
    """O escritor único da escolha dela: o `session.json` e o espelho.

    O Freestyle não se grava no `session.json` (item 3: ligar o Freestyle não
    toca o último perfil, e desligá-lo devolve esse perfil); para ele, só o
    espelho muda — quem diz que ele manda é o flag, que o dono do modo grava.
    """
    if not _e_o_freestyle(nome):
        save_last_profile(nome)
    espelhar_a_escolha()


def esquecer_a_escolha(nome: str | None = None) -> None:
    """Zera o `last_profile` — todo, ou só se ele aponta `nome` (pelo slug).

    Item 9: apagar o perfil escolhido leva a «sem escolha», e não a um nome que
    o boot não acharia. Grava `{}` em vez de apagar o arquivo: o arquivo
    ausente é o sinal da máquina nova (:func:`migrar_a_escolha_dela`).
    """
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


#: A marca da migração da escolha (itens 7 e 8 da decisão). Existe = já rodou.
_MARCA_DA_ESCOLHA = ".a_escolha_dela_migrada"
#: A cópia do `session.json` antes de a migração o esvaziar.
_COPIA_DA_SESSAO = "session-antes-da-escolha.json"


def _so_o_freestyle_na_pasta() -> bool:
    """A pasta dos perfis não tem perfil além do Freestyle? Nunca levanta.

    É a outra metade do «máquina nova» do item 7: o Freestyle é o único perfil
    do install. Lê os nomes dos arquivos, e não os perfis, porque quem pergunta
    roda dentro da semeadura (`load_all_profiles` a chamaria de novo). Na dúvida
    (pasta ilegível), `False`: o botão não acende, que é o lado reversível.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    try:
        return all(_e_o_freestyle(arq.stem) for arq in profiles_dir().glob("*.json"))
    except OSError:
        return False


def migrar_a_escolha_dela() -> str | None:
    """Uma vez só, com marca: a máquina nova e a sessão que apontava o Freestyle.

    Itens 7 e 8 da `D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`:

    - **a máquina nova** (sem `session.json`, sem nunca ter gravado o flag e
      sem perfil além do Freestyle na pasta) nasce com o botão aceso: o
      Freestyle é o único perfil do install, e o chip diz o que o botão diz.
      Decidido por ela em 29/09, ~20h35 («Nasce aceso»). O preço, escrito: o
      primeiro perfil de jogo que a pessoa criar não entra sozinho enquanto o
      botão estiver aceso;
    - **a sessão apontando o Freestyle com o modo desligado** vira «sem
      escolha», com o arquivo copiado antes (`_COPIA_DA_SESSAO`). Acender o
      botão calaria os perfis de jogo dessa pessoa, que hoje entram sozinhos.

    A PASTA ENTRA NA CONTA DA MÁQUINA NOVA (conferência final de 02/10/2026).
    Sem `session.json` também está quem atualiza sem nunca ter ativado um
    perfil à mão: os perfis de jogo dessa pessoa entram sozinhos pela janela, e
    acender o botão os calaria todos, pela mesma razão do segundo caso. Com
    perfil próprio na pasta, a máquina não é nova, e nada muda: fora do jogo
    fica «sem escolha» (item 10), e o jogo continua entrando.

    Quem chama é a semeadura (`profiles.loader._maybe_seed_presets`), DEPOIS das
    duas renomeações do perfil padrão, que podem ter acabado de escrever o
    Freestyle na sessão. Devolve o desfecho, ou `None` quando a marca já
    estava. Nunca levanta.
    """
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


_FREESTYLE_LIGADO_FLAG_FILE = "freestyle_ligado.flag"
#: O arquivo do cadeado de 23/07 (FEAT-AUTOSWITCH-LOCK-01). Só a migração o lê.
_FLAG_DO_CADEADO_ANTIGO = "autoswitch_locked.flag"


def save_freestyle_ligado(ligado: bool) -> None:
    """Persiste o Modo Freestyle (O-FREESTYLE-E-UMA-CAMADA-SO-01, 28/09/2026).

    Arquivo-flag em config_dir (existe = ligado), no mesmo idioma do
    `paused.flag`. Best-effort: nunca propaga exceção. Quem chama é o dono
    único, `profiles.manager.ligar_o_freestyle`, que grava a memória junto.
    """
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
    """One-shot: o `autoswitch_locked.flag` LIGADO vira `freestyle_ligado.flag`.

    Item 5 da O-FREESTYLE-E-UMA-CAMADA-SO-01: o botão «Modo Freestyle» era o
    cadeado de 23/07, e quem o deixou ligado continua com ele ligado. O
    arquivo novo nasce ANTES de o antigo sair — uma queda no meio deixa os dois,
    e a próxima leitura termina o serviço. Idempotente: sem o antigo, nada.
    """
    antigo = base / _FLAG_DO_CADEADO_ANTIGO
    if not antigo.exists():
        return
    novo = base / _FREESTYLE_LIGADO_FLAG_FILE
    if not novo.exists():
        novo.write_text("1\n", encoding="utf-8")
    antigo.unlink(missing_ok=True)
    logger.info("cadeado_antigo_virou_freestyle_ligado")


def load_freestyle_ligado() -> bool:
    """True se o Modo Freestyle foi deixado ligado na sessão anterior.

    Faz a migração do cadeado antigo na mesma leitura (ver
    `_o_cadeado_antigo_vira_freestyle`): quem lê é o boot do daemon, e é a
    primeira coisa que o produto novo faz no disco dela.
    """
    try:
        base = config_dir()
        with contextlib.suppress(OSError):
            _o_cadeado_antigo_vira_freestyle(base)
        return (base / _FREESTYLE_LIGADO_FLAG_FILE).exists()
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


# `save_mouse_emulation_enabled` e `load_mouse_emulation_enabled` MORAVAM AQUI,
# e foram PODADOS em 26/08/2026. Os dois eram invólucros legados
# (FEAT-MOUSE-PERSIST-01) que o próprio docstring mandava não usar: o de gravar
# delegava a `save_mouse_emulation` sem velocidades, o de ler devolvia
# `load_mouse_emulation()[0]`. Nenhum caminho de produção os chamava — só
# `tests/`, e as fixtures que neutralizavam disco patchando o invólucro
# neutralizavam o que a produção NÃO chama (a produção chama
# `save_mouse_emulation`), ou seja, não neutralizavam nada.
# A trava que segurava a poda era "o applet do COSMIC pode importar isto".
# MEDIDA e CAÍDA em 26/08/2026: o applet é RUST (`packaging/cosmic-applet/src/`
# — `main.rs`, `app.rs`, `ipc.rs`), fala com o daemon por JSON-RPC no socket, e
# não há um único `.py` sob `packaging/`. Ele não importa Python nenhum.


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
    hoje `True`) — ver a precedência em `daemon/lifecycle.py:839-844`.

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
        return True  # conteúdo legado "1\n" → arquivo existe = ligada
    if not isinstance(data, dict):
        return True
    raw = data.get("enabled")
    if isinstance(raw, bool):
        return raw
    return True


# `load_keyboard_emulation_enabled` MOROU AQUI, e foi PODADA em 26/08/2026.
# A ASSIMETRIA DELIBERADA que ela documentava NÃO se apagou junto — ela está
# viva e é DECISÃO MEDIDA: o teclado emulado nasce LIGADO (carrega os atalhos,
# o teclado virtual do sistema em L3/R3 e as três regiões do touchpad), ao
# contrário do mouse, que nasce desligado. Quem a aplica hoje é o piso
# `DaemonConfig.keyboard_emulation_enabled = True`, e o boot só o sobrescreve
# quando `load_keyboard_preference()` devolve uma opinião — ver a precedência
# escrita em `daemon/lifecycle.py:839-844`.
# A razão da poda: o invólucro somava um default PRÓPRIO a essa precedência, e
# ninguém em produção o chamava — o boot lê `load_keyboard_preference` direto.
# Duas fontes para o mesmo default é a forma cara do defeito desta casa.


_GAMEPAD_EMULATION_FLAG_FILE = "gamepad_emulation.flag"

#: AUTO-01.1: OPT-OUT explícito do gamepad virtual — "ela desligou de propósito".
#: Até aqui o desligar era gravado APAGANDO o `gamepad_emulation.flag`, o que
#: conflatava dois estados muito diferentes: *nunca configurado* (instalação
#: nova) e *desligado a pedido dela*. A automação que liga a emulação com dois
#: ou mais controles na mesa (`Daemon.aplicar_gamepad_para_multiplos_controles`)
#: precisa distinguir os dois, senão religaria em ~2 s o vpad que ela acabou de
#: desligar — a pior classe de bug possível (o produto brigando com a usuária).
#: Mesmo desenho do `coop_disabled.flag` (FEAT-COOP-DEFAULT-ON-01) e da chave
#: `enabled` do flag de mouse (HARM-06): grava-se a decisão, não a ausência.
_GAMEPAD_DISABLED_FLAG_FILE = "gamepad_disabled.flag"


def save_gamepad_emulation(enabled: bool, flavor: str | None = None) -> None:
    """Persiste o estado do gamepad virtual (FEAT-DSX-GAMEPAD-FLAVOR-01).

    Flag-file em config_dir cujo conteúdo é o flavor (`dualsense`/`xbox`/
    `nintendo`) quando
    ligado; o arquivo é removido quando desligado. Assim o daemon restaura tanto
    o liga/desliga quanto a máscara após restart/reboot. Best-effort.

    AUTO-01.1: o desligar passou a gravar TAMBÉM o opt-out
    (`gamepad_disabled.flag`), e o ligar a apagá-lo. O contrato de leitura
    antigo (`load_gamepad_emulation`) não muda em nada — quem quer saber se ela
    JÁ DECIDIU alguma coisa usa `load_gamepad_preference`. Só o gesto manual
    chega aqui (R-07: `stop_gamepad_emulation(persist=origin == "manual")`), que
    é exatamente a decisão que a automação tem de respeitar.
    """
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
    """Preferência PERSISTIDA do gamepad virtual: ``(ligado|None, flavor)``.

    AUTO-01.1 — o primeiro campo tem TRÊS valores, e é essa a razão de existir:

      - ``True``  — ela deixou ligado (flag presente; o flavor é o conteúdo);
      - ``False`` — ela DESLIGOU de propósito (opt-out gravado). Nada de
        automação pode religar por conta própria;
      - ``None``  — **nunca decidiu** (instalação nova, ou versão anterior a
        esta que apagava o flag ao desligar). Só neste caso o daemon pode ligar
        a emulação sozinho ao ver dois controles na mesa.

    Espelha `load_mouse_preference` (HARM-06), que resolveu o mesmo problema no
    eixo do mouse. Best-effort: erro de I/O vira "nunca decidiu" — o fail-safe
    aqui é deixar a automação agir, porque o efeito dela (dois controles = dois
    jogadores) é o que a usuária espera quando não disse nada.
    """
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


#: MODO-DE-CONEXAO-01 (13/09/2026): o CAMINHO que ela escolheu (o chip de modo
#: da aba Jogar, o PS + R3) mora num arquivo AO LADO do
#: `gamepad_emulation.flag`, e não dentro dele: o formato daquele é o que o boot
#: lê há semanas (`load_gamepad_emulation`), e um segundo campo ali seria um
#: boot antigo lendo `dualsense\nxbox` como máscara. Ausente = ninguém escolheu.
_GAMEPAD_CAMINHO_FLAG_FILE = "gamepad_caminho.flag"

#: O-MODO-XBOX-NAO-E-QUEDA-02 (28/09/2026): as origens que o arquivo guarda.
#: `gesto_fora_do_jogo` é o PS + R3 ou o chip de modo com o desktop na frente
#: (o único escritor da escolha dela); `migracao_unica` é a devolução do `xbox`
#: de 18/09, que roda uma vez. O arquivo antigo, só com o caminho, não tem
#: origem, e é só ele que a migração devolve.
ORIGEM_DO_GESTO_FORA_DO_JOGO = "gesto_fora_do_jogo"
ORIGEM_DA_MIGRACAO_UNICA = "migracao_unica"


def save_gamepad_caminho(caminho: str | None, *, origem: str | None = None) -> None:
    """Persiste o caminho escolhido, com a origem e a hora; vazio apaga. Best-effort.

    Só gesto manual chega aqui (`gamepad._guardar_o_caminho`, a mesma R-07 do
    liga/desliga): um perfil trocando de caminho não vira a escolha dela.

    O formato é `{caminho, origem, quando}` desde a O-MODO-XBOX-NAO-E-QUEDA-02
    (28/09/2026): o boot distingue o `xbox` que ela escolheu fora do jogo do
    `xbox` sem origem que o vazamento de 18/09 deixou no disco.
    """
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
    """``(caminho, origem)`` gravados, crus. O arquivo antigo tem origem ``None``.

    Cru de propósito: a lista dos caminhos tem dono
    (`integrations/virtual_pad.normalizar_caminho`), e este módulo de utilidades
    não importa o de integrações.
    """
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
    """Retorna (ligado, flavor) do gamepad virtual da sessão anterior.

    `(False, None)` se a flag não existir. Se existir mas vazia, assume ligado
    com flavor None (o caller normaliza para o default). Quem precisa
    distinguir "desligado de propósito" de "nunca configurado" usa
    `load_gamepad_preference` (AUTO-01.1).
    """
    enabled, flavor = load_gamepad_preference()
    return bool(enabled), flavor


#: FEAT-COOP-DEFAULT-ON-01: co-op local é o PADRÃO (cada controle = um
#: jogador). O que se persiste é o OPT-OUT: flag presente = usuária desligou.
_COOP_DISABLED_FLAG_FILE = "coop_disabled.flag"
#: Semântica antiga (presente = ligado) — removido na primeira escrita nova.
_COOP_ENABLED_FLAG_FILE_LEGACY = "coop_enabled.flag"


def save_coop_enabled(enabled: bool) -> None:
    """Faxina dos flags de co-op — NUNCA grava opt-out (lápide, 06/08/2026).

    FEAT-COOP-DEFAULT-ON-01 gravava o opt-out aqui: `coop_disabled.flag`
    presente = desligado de propósito.

    COOP-SEM-INTERRUPTOR-01 (06/08/2026) — NOTA DATADA: o opt-out deixou de
    existir por decisão dela (*"todos e tudo no Hefesto tem que tá com o
    permitir co-op ligado"*), então este escritor virou **lápide**, não
    borracha: continua APAGANDO o que versões antigas deixaram (o flag legado e
    o de opt-out), e não escreve mais nada — nem com ``enabled=False``. É de
    propósito que o parâmetro sobreviva: a assinatura é contrato público, e um
    chamador antigo pedindo "desliga" não pode virar `TypeError` no boot.

    Deliberadamente NÃO há varredura nova de disco: o arquivo não existe na
    máquina dela, e a única remoção que precisa acontecer já tem dono one-shot
    (`migrate_coop_optout`, chamada no boot). Best-effort: nunca propaga
    exceção.
    """
    try:
        cfg = config_dir(ensure=True)
        (cfg / _COOP_ENABLED_FLAG_FILE_LEGACY).unlink(missing_ok=True)
        (cfg / _COOP_DISABLED_FLAG_FILE).unlink(missing_ok=True)
        logger.debug("coop_enabled_state_saved", enabled=True, pedido=bool(enabled))
    except Exception as exc:
        logger.debug("coop_enabled_state_save_failed", err=str(exc))


#: Marker da migração do opt-out de co-op (LEIGO-01). Ao lado do flag.
_COOP_OPTOUT_MIGRATION_MARKER = ".coop_optout_migrated"


#: O-MODO-XBOX-NAO-E-QUEDA-02 (27/09/2026): as duas devoluções do boot
#: (`lifecycle._a_escolha_dela_sem_o_vazamento` e a irmã da máscara) rodam UMA
#: vez. Sem a marca elas rodavam em todo boot e desfaziam o Xbox que ela
#: escolhesse de propósito, contra a própria docstring.
MARCA_DO_CAMINHO_DEVOLVIDO = ".caminho_xbox_do_vazamento_devolvido"
MARCA_DA_MASCARA_DEVOLVIDA = ".mascara_xbox_do_vazamento_devolvida"


def migracao_ainda_nao_feita(marca: str) -> bool:
    """True só na primeira chamada: grava a marca e deixa a migração rodar.

    Sem disco (a marca não se lê nem se grava) responde False: na dúvida a
    migração não roda, porque ela mexe numa escolha dela.
    """
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


# `load_coop_enabled` MOROU AQUI, e foi PODADA em 26/08/2026.
#
# A DECISÃO MEDIDA que ela guardava CONTINUA VALENDO, e é esta: desde
# 06/08/2026 (COOP-SEM-INTERRUPTOR-01) o co-op local não tem mais opt-out. Até
# lá esta função lia `coop_disabled.flag`, e um `True` gravado por versão antiga
# podia deixar a máquina dela sem co-op. O disco deixou de governar: quem manda
# é o piso `DaemonConfig.coop_enabled`, e o flag órfão é apagado no boot por
# `migrate_coop_optout` (chamada em `daemon/lifecycle.py`). Nada disso muda com
# a poda — o corpo era `return True`, e o piso é quem responde.
#
# A RAZÃO ESCRITA PARA MANTÊ-LA ERA FALSA, e por isso foi substituída em vez de
# preservada: o docstring dizia que a assinatura era "contrato público (CLI,
# applet e testes a importam)". MEDIDO em 26/08/2026 — a CLI não a importa
# (nenhum `.py` de `src/` a cita), e o applet do COSMIC é RUST
# (`packaging/cosmic-applet/src/{main,app,ipc}.rs`), que fala com o daemon por
# JSON-RPC e não importa Python nenhum. Sobrava `tests/`, que nunca foi caminho.


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
    "load_mouse_emulation",
    "load_mouse_preference",
    "load_paused_state",
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
    "save_mouse_emulation",
    "save_paused_state",
]
