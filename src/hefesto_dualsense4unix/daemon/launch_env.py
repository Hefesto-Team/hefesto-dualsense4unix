"""Materialização das envs de launch para o wrapper `hefesto-launch` (DEDUP-04).

A launch option persistida na Steam virou uma string CONSTANTE (o wrapper);
quem varia é ISTO aqui: arquivos `VAR=VAL` em
`~/.local/state/hefesto-dualsense4unix/launch_env/` que o daemon REGRAVA a
cada transição de estado e que o wrapper lê no momento do launch — depois de
passar no gate de vida (connect+ping IPC). Daemon morto/degradado => o
wrapper não exporta NADA e o jogo abre com o físico visível (pior caso:
controle duplicado, nunca zero controles).

Gatilhos de regravação (os três do sprint doc + o da revisão adversarial):
1. mudança de perfil/config (troca de máscara, liga/desliga emulação, Modo
   Nativo, `profile.switch`/`daemon.reload` via IPC);
2. transição de backend do vpad (uhid<->uinput — as promoções recriam o
   device via `start/stop_gamepad_emulation`, que chamam aqui; a falha TOTAL
   do start também regrava — daemon vivo sem vpad não pode deixar um IGNORE
   rançoso da sessão anterior no arquivo);
3. mudança do conjunto de jogadores do co-op (spawn/teardown de vpad);
4. mudança do CONJUNTO de perfis (save/delete/import pela GUI grava direto no
   disco — a GUI avisa via IPC `launch_env.refresh`, senão o
   `steam_app_<appid>.env` de um perfil novo ficaria ausente/rançoso na
   primeira sessão do jogo).

O conteúdo reflete o backend REAL agregado POR JOGADOR (espelha a
honestidade do `daemon_actions.compose_launch` histórico): QUALQUER vpad em
uinput/0ce6 => SEM `IGNORE_DEVICES` (esconder o físico com um vpad que a SDL
pode mapear errado deixaria um controle de botões trocados — ou nenhum —
como único; duplicado > zero controles).

Arquivos por appid: perfil com `steam_app_<appid>` no `window_class` ganha
`steam_app_<appid>.env` com a opinião DAQUELE perfil (o jogo é lançado ANTES
de a janela existir, então o autoswitch ainda não ativou o perfil — o
arquivo antecipa o modo que ele vai impor). Perfil sem opinião => sem
arquivo => o wrapper cai no `default.env` (máscara/backend globais atuais).
Resolução no MÍNIMO, sem UI de biblioteca de jogos.

JOGO-01 (25/07): o ramo da allowlist do Steam Input rotulava-se "sem dedup" e
era literalmente isso — omitia `SDL_GAMECONTROLLER_IGNORE_DEVICES` e
`PROTON_DISABLE_HIDRAW` e não fazia mais nada. Só que omitir o dedup COM o
gamepad virtual de pé é o próprio duplicado: medido ao vivo com UM DualSense
no cabo, o Mullet Mad Jack (2111190) enxergava js0=vpad e js2=físico (mais os
dois pads que o Steam Input cria), atribuía jogador 1 a um e jogador 2 ao
outro e metade dos comandos dela ia para o controle que o jogo não estava
lendo. O invariante que faltava, e que segue valendo nos dois lados desta
fronteira: **um controle físico produz exatamente UM dispositivo de jogo**.

NOTA DATADA — 09/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01, decisão dela): **a
allowlist do Steam Input não tem mais ramo nenhum neste arquivo de saída.** A
marca passou a significar "esconda o controle FÍSICO neste jogo", e não "entregue
o físico à Steam"; o jogo marcado recebe exatamente a mesma env de qualquer
outro jogo. O obituário do ramo, com o motivo de cada linha dele, está em
`materialize_launch_env`. O appid da allowlist continua vivo aqui para DUAS
outras coisas, e só elas: decidir a sessão da exceção
(`steam_input_exception_appid`) e pular o arming da máscara
(`arm_launch_profile`).
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as _dt
import itertools
import os
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core import o_dono_do_evento as _ode
from hefesto_dualsense4unix.integrations import ponte_escada, ponte_tentativa
from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class
from hefesto_dualsense4unix.utils.leitura_pela_assinatura import (
    Assinatura,
    LeituraPelaAssinatura,
    assinatura,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

#: Vars que o wrapper aceita exportar (allowlist ESPELHADA em
#: `assets/hefesto-launch.sh` — mudar aqui exige mudar lá). Qualquer outra
#: linha no arquivo é ignorada pelo wrapper (fail-safe contra arquivo
#: corrompido/adulterado exportando LD_PRELOAD e afins).
ENV_ALLOWLIST = (
    "SDL_GAMECONTROLLER_IGNORE_DEVICES",
    "SDL_JOYSTICK_HIDAPI",
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS",
    "PROTON_DISABLE_HIDRAW",
    "__GL_SHADER_DISK_CACHE",
    "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP",
    "SDL_ACCELEROMETER_AS_JOYSTICK",
    "PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE",
    "PROTON_ENABLE_MHWILDS_USB_AUDIO",
)

#: DualSense FÍSICO. Ele estava cravado DENTRO das duas strings abaixo; agora é
#: `054c:0df2`, é o MESMO do nosso vpad em toda máscara DualSense (uhid e
PAR_DUALSENSE_FISICO = (0x054C, 0x0CE6)

#:
#:     event2   Sony ... DualSense Wireless Controller       054c:0ce6  (físico)
#:     event6   DualSense Wireless Controller (Hefesto P1)   054c:0df2  (nosso)
PAR_STEAM_INPUT_VIRTUAL = (0x28DE, 0x11FF)

_MASCARAS_SO_EVDEV = frozenset({"xbox", "nintendo"})


def _par_vidpid(par: Any) -> tuple[int, int] | None:
    """`(vid, pid)` quando o par cabe em 16 bits cada; `None` quando não cabe.

    RECUSA em vez de corrigir. Um número fora da faixa formatado por `%04x`
    sai com CINCO dígitos, e o par seguinte gruda no anterior — o SDL leria um
    VID que ninguém pediu, e o winebus deixaria de casar a agulha certa.
    Descartar é o lado seguro da assimetria desta casa: um par A MENOS é o
    controle DUPLICADO (o pior caso aceito por escrito em
    `assets/hefesto-launch.sh` e `install.sh`); um par ERRADO a mais some com
    o controle de alguém.

    `bool` é `int` em Python e entraria aqui como 0/1 sem querer dizer isso —
    fica de fora de propósito.
    """
    try:
        vid, pid = par
    except (TypeError, ValueError):
        return None
    if isinstance(vid, bool) or isinstance(pid, bool):
        return None
    if not isinstance(vid, int) or not isinstance(pid, int):
        return None
    if not (0 <= vid <= 0xFFFF) or not (0 <= pid <= 0xFFFF):
        return None
    return vid, pid


def compor_lista_vidpid(pares: Iterable[tuple[int, int]], *, maiusculas: bool) -> str:
    """O VALOR de uma env de VID/PID, composto a partir de uma LISTA de pares."""
    molde = "0x%04X/0x%04X" if maiusculas else "0x%04x/0x%04x"
    vistos: set[tuple[int, int]] = set()
    saida: list[str] = []
    for par in pares:
        normal = _par_vidpid(par)
        if normal is None:
            logger.warning("launch_env_par_vidpid_descartado", par=str(par))
            continue
        if normal in vistos:
            continue
        vistos.add(normal)
        saida.append(molde % normal)
    return ",".join(saida)


def valor_ignore_devices(pares: Iterable[tuple[int, int]]) -> str:
    """Valor do `SDL_GAMECONTROLLER_IGNORE_DEVICES` para estes pares."""
    return compor_lista_vidpid(pares, maiusculas=False)


def valor_disable_hidraw(pares: Iterable[tuple[int, int]]) -> str:
    """Valor do `PROTON_DISABLE_HIDRAW` para estes pares."""
    return compor_lista_vidpid(pares, maiusculas=True)


#: O valor de HOJE, byte a byte: o DualSense físico E o espelho do Steam Input.
#:
_IGNORE_VALUE = valor_ignore_devices(
    (PAR_DUALSENSE_FISICO, PAR_STEAM_INPUT_VIRTUAL)
)

_DISABLE_HIDRAW_VALUE = valor_disable_hidraw((PAR_DUALSENSE_FISICO,))


WRAPPER_MARKER_WINDOW_SEC = 900.0

LAUNCH_ARM_WINDOW_SEC = 60.0

JANELA_DE_SOSSEGO_SEC = 0.6

ESTADO_ALLOWLIST_STEAM_INPUT = "allowlist Steam Input (físico é o único dispositivo)"

IGNORADO_DISPUTA_DA_ALLOWLIST = "ignorado_disputa_allowlist"


def _read_kv_int_fields(path: Path) -> dict[str, int]:
    """Lê um marker chave=valor (NUMÉRICO), best-effort — nunca levanta.

    Compartilhado por `read_last_run_marker`/`read_last_run_pid`/
    `read_last_exit_marker`: linhas desconhecidas ou com valor não-dígito
    são ignoradas silenciosamente (marker corrompido/adulterado não quebra
    o parse dos campos válidos). Arquivo ausente/ilegível devolve `{}`.

    O-REPOUSO-ESPERA-O-EVENTO-01, família 6 (29/09/2026): com o dono do evento
    armado, o marker é relido só quando a assinatura do `stat` muda
    (`utils/leitura_pela_assinatura.py`). Medido na sonda S.4: 291 `open` por
    minuto no `launch_env` com a mesa parada — o autoswitch a 2 Hz, a camada 1
    da varredura de `/proc` e o `state_full`. O ilegível não se guarda.
    """
    if _ode.armado():
        try:
            return _MARCADORES_PELA_ASSINATURA.ler(path)
        except OSError:
            return {}
        except Exception:
            logger.debug("wrapper_marker_read_falhou", exc_info=True)
            return {}
    return _read_kv_int_fields_do_disco(path)


def _read_kv_int_fields_do_disco(path: Path) -> dict[str, int]:
    """A leitura de sempre do marker; ausente é `{}`, ilegível também."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    except Exception:
        logger.debug("wrapper_marker_read_falhou", exc_info=True)
        return {}
    return _campos_do_marker(text)


def _decodificar_o_marker(path: Path) -> dict[str, int]:
    """A decodificação guardada pela assinatura: ausente é `{}`, ilegível sobe."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    return _campos_do_marker(text)


def _campos_do_marker(text: str) -> dict[str, int]:
    """Os campos `chave=<dígitos>` do texto; o resto se ignora."""
    out: dict[str, int] = {}
    for line in text.splitlines():
        key, _, value = line.partition("=")
        value = value.strip()
        if value.isdigit():
            out[key] = int(value)
    return out


_MARCADORES_PELA_ASSINATURA: LeituraPelaAssinatura[dict[str, int]] = LeituraPelaAssinatura(
    _decodificar_o_marker, copiar=dict
)
_ode.ao_desarmar(_MARCADORES_PELA_ASSINATURA.esquecer)


def assinatura_do_ultimo_lancamento(base_dir: Path | None = None) -> Assinatura | None:
    """A assinatura do `stat` do marker `last_run`, sem abri-lo; None = ausente."""
    return assinatura((base_dir if base_dir is not None else launch_env_dir()) / "last_run")


def read_last_run_marker(base_dir: Path | None = None) -> tuple[int, int] | None:
    """Lê o marker `last_run` do wrapper: ``(appid, epoch)`` ou None.

    Formato (gravado por `assets/hefesto-launch.sh`, chave=valor por linha):
    ``appid=<int>`` + ``epoch=<unix epoch s>`` (+ `pid=<int>` OPCIONAL desde
    NUMA-01 — ignorado aqui, ver `read_last_run_pid`; o contrato de retorno
    deste `read_last_run_marker` fica intacto para os chamadores existentes,
    `wrapper_used_state` incluso). Tolerante a lixo: linhas desconhecidas
    são ignoradas; faltando qualquer um dos dois campos (ou valores
    não-numéricos), devolve None — quem consome trata como "wrapper nunca
    rodou". Nunca levanta.
    """
    path = (base_dir if base_dir is not None else launch_env_dir()) / "last_run"
    fields = _read_kv_int_fields(path)
    appid = fields.get("appid")
    epoch = fields.get("epoch")
    if appid is None or epoch is None or appid <= 0:
        return None
    return appid, epoch


def read_last_run_pid(base_dir: Path | None = None) -> int | None:
    """Lê o campo `pid=` OPCIONAL do marker `last_run` (NUMA-01), ou None."""
    path = (base_dir if base_dir is not None else launch_env_dir()) / "last_run"
    return _read_kv_int_fields(path).get("pid")


def read_last_exit_marker(base_dir: Path | None = None) -> int | None:
    """Lê o marker `last_exit` do wrapper: epoch (int) ou None (NUMA-01)."""
    path = (base_dir if base_dir is not None else launch_env_dir()) / "last_exit"
    return _read_kv_int_fields(path).get("epoch")


def read_last_exit_pid(base_dir: Path | None = None) -> int | None:
    """Lê o campo `pid=` OPCIONAL do marker `last_exit`, ou None.

    Correção pós-auditoria da Onda N: `last_run`/`last_exit` são arquivos
    GLOBAIS (não por appid/sessão) — dois wrappers concorrentes (um cujo
    `exec` FALHA, outro que lança o jogo com sucesso) escrevem nos MESMOS
    dois arquivos sem qualquer lock entre si. `pid=$$` é o PID do PRÓPRIO
    wrapper que gravou aquele `last_exit` (o mesmo `$$` que ele também
    gravou no seu `last_run`, ANTES do `exec` falhar) — correlacionar este
    pid com o `pid=` do `last_run` CORRENTE (`read_last_run_pid`) é o que
    permite a `wrapper_game_running` distinguir "este `last_exit` é do
    MESMO launch que o `last_run` atual" (invalida de verdade) de "este
    `last_exit` é de um launch ANTERIOR/outro, que só perdeu a corrida de
    escrita" (não invalida — o jogo do launch mais novo segue rodando).
    Ausente (marker antigo, sem o campo) ou lixo (não-dígito) devolve None
    — quem consome trata como "sem correlação possível" e cai no critério
    anterior, só por epoch. Nunca levanta.
    """
    path = (base_dir if base_dir is not None else launch_env_dir()) / "last_exit"
    return _read_kv_int_fields(path).get("pid")


def pid_is_alive(pid: int | None) -> bool:
    """True quando `pid` é de um processo vivo agora (NUMA-01).

    `None`/`pid<=0` ⇒ False (sem pid, sem evidência). Usa `os.kill(pid, 0)`
    (não envia sinal nenhum, só sonda `/proc`): `ProcessLookupError` ⇒
    morto; `PermissionError` ⇒ vivo, mas de outro dono (ainda conta como
    vivo — o marker é do MESMO usuário do daemon na prática). Qualquer
    outro `OSError` degrada para False (fail-safe do lado do CHAMADOR:
    `wrapper_game_running` trata "não sei se vive" como "não conta" —
    quem quer o fail-safe do lado do JOGO é `classify`, via `unknown`
    explícito no gather, nunca aqui).
    """
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def wrapper_game_running(
    *,
    marker: tuple[int, int] | None,
    exit_marker: int | None,
    pid_alive: bool,
    marker_pid: int | None = None,
    exit_pid: int | None = None,
    now: float | None = None,
    window_sec: float = WRAPPER_MARKER_WINDOW_SEC,
) -> bool:
    """Decisão PURA: o marker do wrapper ainda atesta um jogo em execução?"""
    if marker is None:
        return False
    _, marker_epoch = marker
    moment = now if now is not None else time.time()
    if (moment - marker_epoch) > window_sec:
        return False
    if not pid_alive:
        return False
    if exit_marker is None or exit_marker < marker_epoch:
        return True
    if marker_pid is None or exit_pid is None:
        return False
    return exit_pid != marker_pid


def wrapper_used_state(
    *,
    appid: int,
    marker: tuple[int, int] | None,
    first_seen_epoch: float,
    window_sec: float = WRAPPER_MARKER_WINDOW_SEC,
) -> bool:
    """Decisão PURA do `wrapper_used` para um jogo detectado (GUI-05 item 3)."""
    if marker is None:
        return False
    marker_appid, marker_epoch = marker
    if marker_appid != appid:
        return False
    return (first_seen_epoch - marker_epoch) <= window_sec


def steam_input_appids(path: Path | None = None) -> set[int]:
    """AppIDs da allowlist do Steam Input (`steam_input_apps.txt`) — R-06.

    A allowlist é opt-in EXPLÍCITO da usuária: jogos cuja via oficial de
    DualSense é o Steam Input per-app (medido: Mullet Mad Jack, appid 2111190,
    chama `SetDualSenseTriggerEffect` da API Steamworks, que só funciona com o
    Steam Input DAQUELE jogo ligado). Até aqui o arquivo só era lido pelo guard
    de VDF (`disable_steam_input.sh`/`storm_doctor`) — o caminho de LANÇAMENTO
    e o broker o ignoravam por completo, então o Hefesto continuava escondendo
    o hidraw do controle físico e a exceção que ela configurou era inerte.

    A leitura reusa `storm_doctor.steam_input_allowlist` (fonte única do
    formato: uma linha por appid, `#` comenta) e converte para int — appid é
    número; token não-numérico no arquivo é ignorado em vez de virar erro.

    O caminho default sai de `steam_input_allowlist_path()` — a MESMA função
    do escritor (o botão "Este jogo não funciona") e, desde 23/08, também do
    `storm_doctor`.

    **Substitui o que estava escrito aqui.** Esta docstring dizia que o
    caminho vinha de `config_dir()` *"e não do `Path.home()` fixo do
    `storm_doctor`"*. O `Path.home()` fixo do `storm_doctor` deixou de existir
    na AMBIENTE-PRESUMIDO-01 (23/08): ele passou a delegar no escritor. A
    justificativa caducou, e o que restava era um **sexto resolvedor
    independente** do mesmo caminho — três linhas que ninguém precisava e que
    voltariam a divergir na primeira vez que o `STEAM_INPUT_ALLOWLIST_RELPATH`
    mudasse, em silêncio e sem erro, que é exatamente a forma do defeito que a
    DUPLO-REGISTRO-01 mediu. Régua em
    `tests/unit/test_t15_a_allowlist_tem_um_caminho_so.py` (T-15, 25/08/2026).
    """
    try:
        from hefesto_dualsense4unix.integrations.steam_launch_options import (
            steam_input_allowlist_path,
        )
        from hefesto_dualsense4unix.integrations.storm_doctor import (
            steam_input_allowlist,
        )

        tokens = steam_input_allowlist(
            path if path is not None else steam_input_allowlist_path()
        )
    except Exception:
        logger.debug("steam_input_allowlist_indisponivel", exc_info=True)
        return set()
    out: set[int] = set()
    for token in tokens:
        limpo = str(token).strip()
        if limpo.isdigit():
            out.add(int(limpo))
    return out


def launch_session_appid(
    *, base_dir: Path | None = None, now: float | None = None
) -> int | None:
    """Appid do jogo lançado PELO WRAPPER que ainda está rodando, ou None."""
    marker = read_last_run_marker(base_dir)
    if marker is None:
        return None
    marker_pid = read_last_run_pid(base_dir)
    vivo = wrapper_game_running(
        marker=marker,
        exit_marker=read_last_exit_marker(base_dir),
        pid_alive=pid_is_alive(marker_pid),
        marker_pid=marker_pid,
        exit_pid=read_last_exit_pid(base_dir),
        now=now,
    )
    return marker[0] if vivo else None


_CLASSES_CEGAS: frozenset[str] = frozenset({"", "unknown"})


def _leitura_cega(wm_class: str | None) -> bool:
    """True quando a leitura de janela não é evidência de app nenhum."""
    if wm_class is None:
        return True
    normalizada = wm_class.strip().casefold()
    if normalizada in _CLASSES_CEGAS:
        return True
    from hefesto_dualsense4unix.profiles.autoswitch import OWN_GUI_WM_CLASSES

    return normalizada in OWN_GUI_WM_CLASSES


def steam_input_exception_appid(
    daemon: Any | None = None,
    *,
    base_dir: Path | None = None,
    now: float | None = None,
    allowlist: set[int] | None = None,
) -> int | None:
    """Appid da allowlist com sessão ATIVA agora (R-06), ou None."""
    appids = allowlist if allowlist is not None else steam_input_appids()
    if not appids:
        return None
    sessao = launch_session_appid(base_dir=base_dir, now=now)
    if sessao is not None and sessao in appids:
        return sessao
    store = getattr(daemon, "store", None)
    wm_class = getattr(store, "window_detect_current_class", None)
    crua = wm_class if isinstance(wm_class, str) else None
    if _leitura_cega(crua):
        sticky = getattr(store, "window_detect_last_class", None)
        crua = sticky if isinstance(sticky, str) else None
    foco = steam_appid_from_wm_class(crua)
    if foco is not None and foco in appids:
        return foco
    return None


def _modo_da_ponte(ponte: ponte_escada.Ponte) -> Any:
    """Um `ProfileModeConfig` que materializa a ponte carimbada no perfil."""
    from hefesto_dualsense4unix.integrations.virtual_pad import normalizar_caminho
    from hefesto_dualsense4unix.profiles.schema import (
        ProfileModeConfig,
        normalizar_gamepad_flavor,
    )

    if ponte.kind == ponte_escada.KIND_GAMEPAD:
        # máscara DualSense no caminho DualSense é o uhid, a Xbox no caminho
        return ProfileModeConfig(
            kind="gamepad",
            gamepad_flavor=normalizar_gamepad_flavor(ponte.mascara),
            caminho=normalizar_caminho(ponte.mascara),  # type: ignore[arg-type]
        )
    return ProfileModeConfig(kind="native")


def ponte_do_lancamento(
    profile: Any, *, na_allowlist: bool
) -> ponte_escada.Ponte | None:
    """A ponte que ESTE lançamento entrega, ou None quando não há opinião."""
    return ponte_escada.ponte_do_perfil(profile, na_allowlist=na_allowlist)


def _jogo_na_autoridade(daemon: DaemonProtocol) -> bool:
    """Há jogo com o controle na mão dela AGORA? PONTE-ESCADA-LACO-01."""
    return getattr(daemon, "display_authority", "unknown") == "game"


def _mode_applier_so_a_mascara(daemon: DaemonProtocol) -> Callable[..., str]:
    """`apply_profile_mode` menos o `kind` — o applier do ramo da ALLOWLIST.

    ALLOWLIST-SO-A-MASCARA-01 (22/08/2026). A seção `mode` carrega DUAS coisas,
    e até esta data o ramo da allowlist tratava as duas como uma só:

    - **`kind`** (gamepad/native/desktop) é a DISPUTA PELO CONTROLE — ligar e
      desligar vpad, largar o físico, soltar o grab. É isto que a allowlist
      existe para pular, e continua pulado;
    - **`gamepad_flavor`** é O QUE O JOGO ENXERGA. Com o físico escondido
      (`ESCONDER-EM-VEZ-DE-SAIR-01`, 09/08) o vpad é o único dispositivo que o
      jogo marcado tem, e um vpad Xbox NÃO TEM campo de touchpad, giroscópio
      nem acelerômetro no descritor HID — dez linhas de `mapa-controles.csv`
      dizem `gamepad/dualsense` na coluna `ponte_alcanca`.

    Medido no daemon dela em 22/08/2026: perfil Sackboy pedindo
    `gamepad_flavor="dualsense"`, quatro vpads uinput com máscara `xbox` e
    `mode_from_profile=null`. Ou seja, marcar o jogo REMOVIA features em vez de
    preservá-las — o oposto exato da decisão dela (*"a allowlist do Steam Input
    NÃO tira o Hefesto da frente"*).

    **Não é um segundo escritor da máscara.** Quem escreve continua sendo
    `lifecycle.apply_profile_mode` -> `_pedir_mascara_do_perfil`, com o gate
    R-04 inteiro no caminho (jogo com a autoridade => `ADIADO_JOGO_ABERTO`, e
    nada é recriado na mão dela). O embrulho só decide se a chamada acontece,
    exatamente como o `_mode_applier_ao_sair_do_nativo` do `lifecycle.py`, que
    barra só o `native`.

    **A precondição é o que garante que SÓ a máscara passa**, e ela não é
    confiança no ramo do applier: a chamada só é feita quando o estado vivo JÁ
    é o `kind` que o perfil pede — emulação ligada, vpad de pé, nativo
    desligado. Nessa condição as duas linhas de disputa do ramo `gamepad`
    (`set_native_mode(False)` e o `set_gamepad_emulation` de ligar) são
    no-ops por construção, e a única coisa que sobra para mudar é o flavor.
    Fora dela o applier nem é chamado — ligar o vpad num jogo marcado seria a
    disputa que a allowlist pula.
    """

    def aplicar(
        mode: Any | None,
        *,
        profile: Any | None = None,
        origin: str = "launch",
    ) -> str:
        kind = getattr(mode, "kind", None) if mode is not None else None
        nome = getattr(profile, "name", None)
        if kind != "gamepad":
            logger.info(
                "launch_allowlist_mode_barrado",
                motivo="kind_e_disputa",
                kind=kind,
                profile=nome,
            )
            return IGNORADO_DISPUTA_DA_ALLOWLIST
        native, emulacao, flavor_vivo, _backends, _fisicos = _snapshot(daemon)
        tem_vpad = getattr(daemon, "_gamepad_device", None) is not None
        if native or not emulacao or not tem_vpad:
            logger.info(
                "launch_allowlist_mode_barrado",
                motivo="vpad_nao_esta_de_pe",
                native=native,
                emulacao=emulacao,
                tem_vpad=tem_vpad,
                profile=nome,
            )
            return IGNORADO_DISPUTA_DA_ALLOWLIST
        applier = getattr(daemon, "apply_profile_mode", None)
        if not callable(applier):
            return IGNORADO_DISPUTA_DA_ALLOWLIST
        logger.info(
            "launch_allowlist_so_a_mascara",
            profile=nome,
            mascara_do_perfil=getattr(mode, "gamepad_flavor", None),
            mascara_viva=flavor_vivo,
        )
        return str(applier(mode, profile=profile, origin=origin))

    return aplicar


def _ativar_o_perfil_do_lancamento(
    daemon: DaemonProtocol, profile: Any, *, appid: int, na_allowlist: bool = False
) -> dict[str, str]:
    """Ativa o perfil do jogo que ACABOU de subir, e devolve o relatório."""
    nome = getattr(profile, "name", None)
    if not nome:
        return {}
    relatorio: dict[str, str] = {}
    try:
        from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

        desvio: dict[str, Any] = (
            {"mode_applier": _mode_applier_so_a_mascara(daemon)}
            if na_allowlist
            else {}
        )
        gerente_do_daemon(
            daemon, store=getattr(daemon, "store", None), **desvio
        ).activate(str(nome), origin="launch", relatorio=relatorio)
    except Exception as exc:
        logger.warning(
            "launch_ativacao_do_perfil_falhou",
            appid=appid,
            profile=nome,
            err=str(exc),
        )
        return {}
    logger.info(
        "launch_perfil_ativado",
        appid=appid,
        profile=nome,
        secoes=relatorio,
    )
    return relatorio


def tique_da_escada(
    daemon: DaemonProtocol, *, agora: float | None = None
) -> str | None:
    """O relógio de 1 Hz da escada. Devolve o motivo do FIM, ou None."""
    resultado = ponte_tentativa.tique(
        daemon, jogo_vivo=_jogo_na_autoridade(daemon), agora=agora
    )
    ponte = resultado.carimbar if resultado.carimbar is not None else resultado.alinhar
    if ponte is None:
        return resultado.fim
    try:
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        gerente = ProfileManager(controller=daemon.controller)
        if resultado.carimbar is None:
            salvo = gerente.alinhar_o_modo_do_appid(
                resultado.appid, kind=ponte.kind, caminho=ponte.mascara
            )
        else:
            salvo = gerente.confirmar_ponte(
                resultado.appid,
                kind=ponte.kind,
                gamepad_flavor=ponte.mascara,
                steam_input=ponte.steam_input,
                por=resultado.por or ponte_escada.POR_SILENCIO,
                alinhar_o_modo=resultado.alinhar is not None,
            )
    except Exception as exc:
        logger.warning(
            "ponte_escada_carimbo_falhou",
            appid=resultado.appid,
            ponte=ponte.chave,
            err=str(exc),
        )
        return resultado.fim
    if salvo is None:
        logger.info("ponte_escada_sem_perfil_para_carimbar", appid=resultado.appid)
        return resultado.fim
    if resultado.carimbar is not None:
        logger.info(
            "ponte_escada_carimbada",
            appid=resultado.appid,
            ponte=ponte.chave,
            perfil=getattr(salvo, "name", None),
            por=resultado.por,
            modo_alinhado=resultado.alinhar is not None,
        )
    return resultado.fim


def _soltar_a_trava_do_lancamento(daemon: Any) -> None:
    """Um lançamento novo pode vestir o pad. A trava do anterior acaba aqui."""
    daemon._pad_travado_pelo_lancamento = None


def _travar_o_pad_que_o_jogo_vai_abrir(daemon: Any, appid: int, epoch: float) -> None:
    """O pad de pé ao `exec` é o que o jogo abre. Nada automático o recria."""
    daemon._pad_travado_pelo_lancamento = (int(appid), epoch)
    logger.info("pad_travado_pelo_lancamento", appid=appid, epoch=epoch)


def arm_launch_profile(
    daemon: DaemonProtocol,
    *,
    base_dir: Path | None = None,
    now: float | None = None,
) -> dict[str, Any] | None:
    """Aplica o modo do perfil do jogo NO LAUNCH, não quando a janela aparece.

    R-04 (auditoria 23/07). O modo do perfil só existia quando o autoswitch
    via a JANELA — ou seja, com o jogo JÁ RODANDO e com a env dele já congelada
    no `exec` do wrapper. Duas consequências medidas:

    - a troca de máscara chegava tarde e DESTRUÍA/RECRIAVA os vpads com o jogo
      aberto, invalidando os handles que ele abriu (a Steam nunca reabre o
      hidraw do vpad do P1) — "o modo de jogar nunca é respeitado";
    - com o gate destrutivo do R-04 em `subsystems/gamepad.py`, essa troca
      tardia passa a ser RECUSADA — logo o arming não é enfeite: é o que faz o
      perfil valer desde o primeiro frame em vez de não valer nunca.

    O gatilho é o marker `last_run`, que o wrapper grava ANTES de qualquer
    outra coisa (inclusive antes do gate de vida por IPC) e ANTES do `exec`.
    O arming é idempotente por `(appid, epoch)`: um mesmo launch arma UMA vez,
    por mais vezes que a reconciliação rode.

    Ordem deliberada: a `.env` por appid NÃO depende deste arming — ela já é
    materializada com a opinião do perfil (e, desde o R-05, com o backend
    PROGNOSTICADO). Por isso o arming pode ser assíncrono ao ping do wrapper
    sem risco: o que ele conserta é a MÁSCARA, que o jogo só consulta segundos
    depois, ao enumerar os controles.

    Appid da allowlist do Steam Input NÃO tem a MÁSCARA armada (contradição 11
    do plano): a allowlist é opt-in explícito de "quem entrega a ENTRADA deste
    jogo é a Steam", e impor a máscara de um perfil ali seria contradizer a
    própria exceção — a máscara é justamente uma opinião sobre o dispositivo
    de entrada.

    NOTA DATADA — 07/08/2026. O parágrafo acima dizia que a allowlist é opt-in
    de *"o Hefesto sai de cena neste jogo"*, e essa leitura está **refutada
    pela metade** pela medição dela de 06/08 (`CONTROLE-SONY-MEDIDO-01`, seção
    *A INVERSÃO*, grau MEDIDO): o Hefesto sai da ENTRADA e **fica inteiro na
    saída** — os gatilhos dela seguraram e a cor dela ficou, com o jogo da
    lista aberto. A decisão de código NÃO muda (a máscara continua fora, e por
    um motivo agora mais preciso); o que muda é a frase que a descreve, e ela
    é a mesma que o estudo
    o estudo «desenho-a-flag-do-jogo-e-o-perfil-a-partir-da-biblioteca» de 06/08/2026
    (seção 5.3, item 2) já cobrava desta função.

    NOTA DATADA — 09/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01). A refutação virou
    inteira: a marca deixou de entregar a entrada à Steam e passou a **esconder
    o controle físico**, com o Hefesto na frente do jogo marcado de ponta a
    ponta. Com isso, o motivo escrito acima — *"impor a máscara ali seria
    contradizer a própria exceção"* — deixou de existir: não há mais exceção a
    contradizer, e a máscara do perfil dela é uma opinião sobre o vpad que o
    jogo marcado agora enxerga. **O código NÃO foi mudado nesta leva, de
    propósito.** Ligar o arming num jogo marcado muda o que ela vê ao abrir o
    jogo, e trocar o modo de um jogo dela sem que ela peça é a regra mais velha
    desta casa ao contrário. Fica registrado como pergunta para ela, com o preço
    declarado: enquanto isto for assim, marcar um jogo continua desligando,
    calado, o modo do perfil daquele jogo NO LANÇAMENTO.

    ALLOWLIST-SUPRESSAO-01 (auditoria 24/07): "sair de cena" era largo demais e
    engolia o que NÃO disputa nada com o jogo. O `return` antecipado da
    allowlist vinha ANTES de olhar o perfil, então o
    `suppress_desktop_emulation` — o "modo jogo", que só PARA o mouse/teclado
    emulados do desktop — nunca era aplicado nesses appids. O que a allowlist
    existe para evitar é o Hefesto ROUBAR o controle (máscara/grab/vpad); parar
    de mexer o cursor enquanto ela joga não rouba nada de ninguém. Agora a
    allowlist pula SÓ a seção `mode`; a supressão do perfil é aplicada
    normalmente.

    PONTE-ESCADA-01 (19/08/2026) — o arming é onde a ponte GRAVADA passa a
    valer, e a divisão de poderes é declarada, não implícita:

    - **o perfil manda.** Perfil com `mode` continua sendo aplicado como
      sempre, mesmo que o carimbo diga outra coisa. A divergência é
      GRITADA (`ponte_confirmada_diverge_do_perfil`) e devolvida no dicionário,
      nunca resolvida às escondidas — trocar o modo de um jogo dela sem ela
      pedir é a regra mais velha desta casa ao contrário;
    - **o carimbo preenche o silêncio.** Perfil SEM `mode` é ausência de
      opinião (R-02), e era o ramo em que nada era armado. Com o
      `Profile.ponte` carimbado, é ele que arma — porque a confirmação veio de
      um gesto dela, e honrar o gesto dela não é atropelar ninguém;
    - **a ponte entregue é relatada**, e só quando a máscara CONVERGIU. Dizer
      "entreguei" sobre uma troca que o gate R-04 recusou é a mesma mentira
      que a MASCARA-01 tirou daqui em 19/08. E o arming NÃO carimba nada: quem
      confirma é o gesto dela, ou o silêncio dela com o jogo vivo
      (`ponte_escada.confirmacao_por_silencio`), e quem grava é
      `profiles/manager.confirmar_ponte`.
    """
    with contextlib.suppress(Exception):
        tique_da_escada(daemon)

    marker = read_last_run_marker(base_dir)
    if marker is None:
        return None
    appid, epoch = marker
    moment = now if now is not None else time.time()
    if (moment - epoch) > LAUNCH_ARM_WINDOW_SEC:
        return None
    if getattr(daemon, "_launch_armed_for", None) == (appid, epoch):
        return None
    daemon._launch_armed_for = (appid, epoch)  # type: ignore[attr-defined]
    _soltar_a_trava_do_lancamento(daemon)

    from hefesto_dualsense4unix.profiles.manager import o_freestyle_manda

    if o_freestyle_manda(getattr(daemon, "store", None)):
        logger.info("launch_arm_pulado_freestyle_ligado", appid=appid)
        return {"appid": appid, "armado": False, "motivo": "freestyle_ligado"}

    na_allowlist = appid in steam_input_appids()

    profile = None
    for candidato_appid, candidato in _steam_profiles(daemon):
        if candidato_appid == appid:
            profile = candidato
            break
    if profile is None:
        logger.info(
            "launch_arm_pulado_allowlist_steam_input"
            if na_allowlist
            else "launch_arm_sem_perfil",
            appid=appid,
        )
        _travar_o_pad_que_o_jogo_vai_abrir(daemon, appid, epoch)
        return {
            "appid": appid,
            "armado": False,
            "motivo": "allowlist_steam_input" if na_allowlist else "sem_perfil",
        }

    supressao: object | None = None
    aplicar_supressao = getattr(daemon, "apply_profile_suppression", None)
    if callable(aplicar_supressao):
        try:
            supressao = aplicar_supressao(
                bool(getattr(profile, "suppress_desktop_emulation", False)),
                profile=profile,
                origin="launch",
            )
        except Exception as exc:
            logger.warning(
                "launch_arm_supressao_falhou",
                appid=appid,
                profile=getattr(profile, "name", None),
                err=str(exc),
            )

    # faz o Hefesto CONTINUAR FUNCIONANDO, com a saída sendo xbox ou DualSense e
    # (`CONTROLE-SONY-MEDIDO-01`, seção A INVERSÃO): com o DualSense físico e
    ativacao = _ativar_o_perfil_do_lancamento(
        daemon, profile, appid=appid, na_allowlist=na_allowlist
    )

    if na_allowlist:
        logger.info(
            "launch_arm_pulado_allowlist_steam_input",
            appid=appid,
            profile=getattr(profile, "name", None),
            supressao=supressao,
            ativacao=ativacao,
        )
        _travar_o_pad_que_o_jogo_vai_abrir(daemon, appid, epoch)
        return {
            "appid": appid,
            "armado": False,
            "motivo": "allowlist_steam_input",
            "supressao": supressao,
            "ativacao": ativacao,  # chave de payload, como a `supressao` ao lado (noqa-acento)
        }

    mode = getattr(profile, "mode", None)
    ponte_perfil = ponte_do_lancamento(profile, na_allowlist=na_allowlist)
    # pragmata2), e aí o produto armaria um e leria o carimbo do outro.
    ponte_gravada = ponte_escada.ponte_do_carimbo(getattr(profile, "ponte", None))

    ponte_de_pe = ponte_perfil
    if ponte_de_pe is None and mode is not None:
        ponte_de_pe = ponte_escada.Ponte(kind=str(getattr(mode, "kind", "?")))
    comeco = ponte_tentativa.comecar(
        daemon,
        appid=appid,
        epoch=epoch,
        ponte_do_perfil=ponte_de_pe,
        confirmada=ponte_gravada,
        jogo_vivo=_jogo_na_autoridade(daemon),
    )

    veio_do_carimbo = False
    if (
        mode is None
        and ponte_gravada is not None
        and ponte_gravada.kind != ponte_escada.KIND_DESKTOP
    ):
        mode = _modo_da_ponte(ponte_gravada)
        veio_do_carimbo = True
        logger.info(
            "launch_arm_ponte_confirmada",
            appid=appid,
            profile=getattr(profile, "name", None),
            ponte=ponte_gravada.chave,
        )
    veio_da_escada = False
    if mode is None and comeco.armar is not None:
        mode = _modo_da_ponte(comeco.armar.ponte)
        veio_da_escada = True
        logger.info(
            "launch_arm_primeiro_degrau",
            appid=appid,
            profile=getattr(profile, "name", None),
            ponte=comeco.armar.ponte.chave,
        )

    if mode is None:
        logger.info(
            "launch_arm_perfil_sem_modo", appid=appid,
            profile=getattr(profile, "name", None),
            escada=comeco.motivo,
        )
        _travar_o_pad_que_o_jogo_vai_abrir(daemon, appid, epoch)
        return {
            "appid": appid,
            "armado": False,
            "motivo": "perfil_sem_modo",
            "escada": comeco.motivo,
        }

    if ponte_gravada is not None and not veio_do_carimbo:
        discordancia = ponte_escada.divergencia_com_o_carimbo(
            profile, ponte_gravada, na_allowlist=na_allowlist
        )
        if discordancia is not None:
            termo, do_perfil, gravado = discordancia
            logger.warning(
                "ponte_confirmada_diverge_do_perfil",
                appid=appid,
                profile=getattr(profile, "name", None),
                termo=termo,
                do_perfil=do_perfil,
                gravado=gravado,
            )

    applier = getattr(daemon, "apply_profile_mode", None)
    if not callable(applier):
        return {"appid": appid, "armado": False, "motivo": "daemon_sem_applier"}
    logger.info(
        "launch_arm_modo_do_perfil",
        appid=appid,
        profile=getattr(profile, "name", None),
        kind=getattr(mode, "kind", None),
    )
    resultado = applier(mode, profile=profile, origin="launch")
    native_pos, enabled_pos, flavor_pos, backends_pos, fisicos_pos = _snapshot(daemon)
    modo_antecipado = _modo_antecipado(
        profile,
        flavor_atual=flavor_pos,
        backends=backends_pos,
        identidade=_identidade_do_primario(daemon),
        permite_uhid=_permite_uhid(daemon),
        fisicos=fisicos_pos,
        vpads_previstos=_vpads_previstos(daemon, fisicos_pos),
    )
    divergencia = divergencia_de_mascara(
        modo_antecipado,
        native_vivo=native_pos,
        emulacao_viva=enabled_pos,
        flavor_vivo=flavor_pos,
    )
    if divergencia is not None:
        logger.warning(
            "launch_arm_mascara_nao_convergiu",
            appid=appid,
            profile=getattr(profile, "name", None),
            mascara_perfil=getattr(modo_antecipado, "mascara", None),
            mascara_viva=flavor_pos,
            motivo=divergencia,
        )
    # e para a divergência acima chegar ao `state_full` pelo mesmo caminho de
    with escrita_na_hora():
        materialize_launch_env(daemon)
    ponte_entregue = ponte_gravada if veio_do_carimbo else ponte_perfil
    if veio_da_escada and comeco.armar is not None:
        ponte_entregue = comeco.armar.ponte
    if divergencia is not None:
        ponte_entregue = None
        if veio_da_escada:
            ponte_tentativa.encerrar(daemon, motivo="degrau_nao_subiu")
    _travar_o_pad_que_o_jogo_vai_abrir(daemon, appid, epoch)
    return {
        "appid": appid,
        "armado": True,
        "profile": getattr(profile, "name", None),
        "resultado": resultado,
        "convergiu": divergencia is None,
        "divergente": divergencia,
        "ponte": ponte_entregue.chave if ponte_entregue is not None else None,
        "ponte_do_carimbo": veio_do_carimbo,
        "ponte_da_escada": veio_da_escada,
        "escada": comeco.motivo,
        "ponte_confirmada": (
            ponte_gravada.chave if ponte_gravada is not None else None
        ),
        "ativacao": ativacao,  # chave de payload, como a `supressao` ao lado (noqa-acento)
    }


def cobertura_total(*, backends: Sequence[str], fisicos: int) -> bool:
    """Existe um vpad vivo para CADA DualSense físico da mesa?

    WRAPPER-EM-TODOS-01 (03/08/2026) escreveu esta conta dentro do
    `compose_env`; a IGNORE-NO-FIM-DA-SEQUENCIA-01 (12/08/2026) a tirou para
    fora porque agora existe um segundo leitor dela — o vigia que compara a
    mesa de agora com a que foi materializada da última vez
    (`_assinatura_da_mesa`). Duas cópias da mesma conta é como esta casa
    reintroduz um defeito já pago; uma função com nome é o preço de não repetir.

    ``fisicos <= 0`` significa **"NÃO SEI"**, nunca "nenhum": o
    `_fisicos_na_mesa` devolve 0 quando o backend não expõe
    `describe_controllers` (`FakeController`, dublê de teste, backend legado).
    Nesse caso a resposta é True — o comportamento HISTÓRICO, decidir pelo TIPO
    do vpad. Apertar sem informação removeria o dedup de quem sempre o teve, que
    é regressão, não cura.
    """
    return fisicos <= 0 or len(backends) >= fisicos


def compose_env(
    *,
    native_mode: bool,
    emulation_enabled: bool,
    flavor: str,
    backends: Sequence[str],
    fisicos: int = 0,
) -> dict[str, str]:
    """Envs de launch para UM estado do daemon. Pura e testável.

    GUERRA-01 (estudo 2026-07-18): o IGNORE do SDL só filtra o caminho SDL —
    o winebus dos Protons 10/11 dá hidraw à família Sony inteira POR DEFAULT
    e é por ESSE canal que o jogo continuava escrevendo no físico (a guerra
    de escritores de lightbar/rumble). A env moderna é `PROTON_DISABLE_HIDRAW`
    (lista VID/PID); `PROTON_ENABLE_HIDRAW` morreu no Proton 10.

    - Modo Nativo: NENHUMA env de hidraw — a whitelist default do winebus já
      expõe o físico Sony (Protons 10/11); esconder o físico aqui é
      exatamente o "zero controles" relatado ao vivo.
    - Xbox **e Nintendo Pro**: `SDL_JOYSTICK_HIDAPI=0` (SDL lê o evdev, que o
      daemon graba) + IGNORE + DISABLE do físico (o vazamento winebus vale
      para qualquer máscara). O vpad é 045e ou 057e — nunca colide com o 0ce6.

      A máscara nintendo entrou neste ramo em 07/09/2026, e o ramo é o mesmo
      por medida, não por parecença: as duas sobem SEMPRE em uinput (o
      `_try_uhid` veta tudo o que não é `dualsense`), as duas são evdev puro
      sem hidraw, e as duas precisam que o SDL largue o HIDAPI para ler o nó
      que o daemon oferece. Antes disso o `nintendo` caía FORA dos dois `if` e
      saía sem IGNORE nenhum: o jogo veria o DualSense físico E o vpad, e o
      sintoma seria "controle dobrado" com a máscara nova no meio.
    - DualSense, em uhid ou em uinput: DISABLE do físico + IGNORE — dedup no
      layout PS. O vpad é o Edge 0df2 nos dois canais (VPAD-06), que o IGNORE
      do 0ce6 não alcança, e o uhid segue com hidraw pleno (NUNCA 0x0DF2 no
      DISABLE). NOTA DATADA — PS-L3-MASCARA-01, 14/09/2026, com a história
      corrigida na conferência do mesmo dia: o uinput ficava de fora por ser
      tratado como DEGRADAÇÃO (o `all(b == "uhid")` de 03/08, escrito quando o
      pior caso era mapeamento menos validado), e não por causa do PID. Desde o
      caminho Xbox (13/09) o uinput é ESCOLHA dela, e desde a
      TROCA-DENTRO-DO-JOGO-01 (14/09) a regra não depende mais de qual canal o
      vpad pegou: fora do Modo Nativo o jogo vê só o virtual.
    - Emulação desligada ou sem vpad vivo: SÓ o preload de shaders.

    O preload (`__GL_SHADER_*`) entra em toda variante: é inócuo e é a parte
    "carregamento completo" que o botão da GUI sempre prometeu.
    """
    env: dict[str, str] = {}
    # O `SDL_GAMECONTROLLER_IGNORE_DEVICES` esconde o DualSense físico do SDL
    # passava trivialmente sobre uma lista incompleta. Com 2 DualSense físicos
    tem_cobertura = cobertura_total(backends=backends, fisicos=fisicos)
    if not native_mode and emulation_enabled and backends:
        if flavor in _MASCARAS_SO_EVDEV:
            env["SDL_JOYSTICK_HIDAPI"] = "0"
            env["PROTON_DISABLE_HIDRAW"] = _DISABLE_HIDRAW_VALUE
            if tem_cobertura:
                env["SDL_GAMECONTROLLER_IGNORE_DEVICES"] = _IGNORE_VALUE
        elif flavor == "dualsense":
            env["PROTON_DISABLE_HIDRAW"] = _DISABLE_HIDRAW_VALUE
            if tem_cobertura:
                env["SDL_GAMECONTROLLER_IGNORE_DEVICES"] = _IGNORE_VALUE
        # PS-L3-MASCARA-01: o DualSense em uinput também esconde o físico.
        if not tem_cobertura:
            logger.info(
                "launch_env_ignore_omitido_sem_cobertura",
                fisicos=fisicos,
                vpads=len(backends),
                motivo="um vpad por DualSense físico é requisito do IGNORE",
            )
    env["__GL_SHADER_DISK_CACHE"] = "1"
    env["__GL_SHADER_DISK_CACHE_SKIP_CLEANUP"] = "1"
    # Inócua para DualSense/Xbox; entra em toda variante, como o preload.
    env["SDL_GAMECONTROLLER_USE_BUTTON_LABELS"] = "0"
    env["SDL_ACCELEROMETER_AS_JOYSTICK"] = "0"
    # HAPTICA-NATIVA-01 (17/09/2026): a vibração do DualSense viaja como ÁUDIO —
    #   a pergunta que a RE Engine faz para achar o alvo (0103). Sem DualSense
    env["PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE"] = "1"
    env["PROTON_ENABLE_MHWILDS_USB_AUDIO"] = "1"
    return env


def _fisicos_na_mesa(daemon: DaemonProtocol) -> int:
    """Quantos DualSense FÍSICOS estão conectados agora (0 se não der para saber).

    WRAPPER-EM-TODOS-01 (03/08/2026). O `_snapshot` abaixo sempre soube quantos
    VPADS existem e nunca soube quantos FÍSICOS há — e é a comparação entre os
    dois que decide se o `SDL_GAMECONTROLLER_IGNORE_DEVICES` pode sair.

    Zero na dúvida, e isso é deliberado: com zero, `compose_env` não emite o
    IGNORE, e o pior caso volta a ser o controle DUPLICADO, que é o que a
    doutrina desta casa aceita (`assets/hefesto-launch.sh`, `install.sh`).
    Nunca o contrário — um número otimista aqui esconde controle do jogo.
    """
    describe = getattr(getattr(daemon, "controller", None), "describe_controllers", None)
    if not callable(describe):
        return 0
    try:
        entradas = describe()
    except Exception:
        logger.debug("launch_env_fisicos_indisponiveis", exc_info=True)
        return 0
    if not isinstance(entradas, list):
        return 0
    return sum(
        1 for e in entradas if isinstance(e, dict) and e.get("connected")
    )


def _snapshot(daemon: DaemonProtocol) -> tuple[bool, bool, str, list[str], int]:
    """(native, emulation_enabled, flavor, backends dos vpads, físicos na mesa).

    WRAPPER-EM-TODOS-01: o quinto campo é novo. Sem ele, `compose_env` decidia
    pelo TIPO dos vpads (`all(b == "uhid")`) e nunca pela COBERTURA — e um
    jogador de co-op PENDENTE (aguardando o `EVIOCGRAB`, com `vpad is None`)
    simplesmente não entrava na lista, fazendo o `all(...)` passar
    trivialmente. Com 2 DualSense físicos e 1 vpad, o IGNORE escondia os DOIS
    por VID/PID e só UM voltava.
    """
    native = False
    with contextlib.suppress(Exception):
        native = bool(daemon.is_native_mode())
    cfg = getattr(daemon, "config", None)
    enabled = bool(getattr(cfg, "gamepad_emulation_enabled", False))
    flavor = _mascara_do_primario(daemon, cfg)

    backends: list[str] = []
    primary = getattr(daemon, "_gamepad_device", None)
    if primary is not None:
        backends.append(str(getattr(primary, "backend", "") or ""))
    coop = getattr(daemon, "_coop_manager", None)
    players = getattr(coop, "_players", None)
    if isinstance(players, dict):
        for player in players.values():
            vpad = getattr(player, "vpad", None)
            if vpad is not None:
                backends.append(str(getattr(vpad, "backend", "") or ""))
    return native, enabled, flavor, backends, _fisicos_na_mesa(daemon)


AssinaturaDaMesa = tuple[bool, bool, str, tuple[str, ...], int, bool]


def _o_freestyle_na_assinatura(daemon: Any) -> bool:
    """O Modo Freestyle ligado, pelo dono — o sexto campo da assinatura."""
    from hefesto_dualsense4unix.profiles.manager import o_freestyle_manda

    return o_freestyle_manda(getattr(daemon, "store", None))


def _assinatura_da_mesa(daemon: DaemonProtocol) -> AssinaturaDaMesa:
    """O estado que decide a env, em forma comparável (hashable)."""
    native, enabled, flavor, backends, fisicos = _snapshot(daemon)
    return (
        native, enabled, flavor, tuple(backends), fisicos,
        _o_freestyle_na_assinatura(daemon),
    )


def armar_rematerializacao(
    daemon: Any, *, motivo: str, agora: float | None = None
) -> None:
    """ARMA o relógio do sossego. Não escreve nada — só adia a decisão."""
    momento = agora if agora is not None else time.monotonic()
    with contextlib.suppress(Exception):
        daemon._launch_env_sossego_em = momento + JANELA_DE_SOSSEGO_SEC
        logger.debug("launch_env_sossego_armado", motivo=motivo)


def vigiar_a_mesa(daemon: Any, *, agora: float | None = None) -> None:
    """Arma o sossego quando a mesa mudou SEM borda que materializasse."""
    with contextlib.suppress(Exception):
        if getattr(daemon, "_launch_env_sossego_em", None) is not None:
            return
        if _assinatura_da_mesa(daemon) == getattr(
            daemon, "_launch_env_assinatura", None
        ):
            return
        armar_rematerializacao(daemon, motivo="a mesa mudou sem borda", agora=agora)


def rematerializar_se_sossegou(daemon: Any, *, agora: float | None = None) -> bool:
    """DISPARA quando a mesa sossegou: reavalia a cobertura e regrava se mudou."""
    try:
        prazo = getattr(daemon, "_launch_env_sossego_em", None)
        if prazo is None:
            return False
        momento = agora if agora is not None else time.monotonic()
        if momento < float(prazo):
            return False
        if _a_escrita_em_voo():
            return False
        daemon._launch_env_sossego_em = None
        assinatura = _assinatura_da_mesa(daemon)
        anterior = getattr(daemon, "_launch_env_assinatura", None)
        if assinatura == anterior:
            return False
    except Exception:
        logger.debug("launch_env_sossego_indisponivel", exc_info=True)
        return False
    logger.info(
        "launch_env_rematerializado_no_sossego",
        vpads=len(assinatura[3]),
        fisicos=assinatura[4],
        cobertura=cobertura_total(
            backends=list(assinatura[3]), fisicos=assinatura[4]
        ),
    )
    _avisar_se_o_jogo_ja_congelou(daemon, anterior, assinatura)
    materialize_launch_env(daemon)
    return True


def _avisar_se_o_jogo_ja_congelou(
    daemon: Any,
    anterior: AssinaturaDaMesa | None,
    atual: AssinaturaDaMesa,
) -> None:
    """Grita no journal quando a cobertura mudou com um jogo já de pé."""
    with contextlib.suppress(Exception):
        if anterior is None:
            return
        antes = cobertura_total(backends=list(anterior[3]), fisicos=anterior[4])
        agora_tem = cobertura_total(backends=list(atual[3]), fisicos=atual[4])
        if antes == agora_tem:
            return
        appid = launch_session_appid()
        if appid is None:
            return
        logger.warning(
            "launch_env_mudou_depois_do_exec",
            appid=appid,
            cobertura_no_arquivo_antigo=antes,
            cobertura_agora=agora_tem,
            vpads=len(atual[3]),
            fisicos=atual[4],
            motivo=(
                "o jogo congelou a env no exec do wrapper; a regravação vale "
                "para o PRÓXIMO lançamento, não para esta sessão"
            ),
        )


def _load_profiles(daemon: DaemonProtocol) -> list[Any]:
    """Perfis do disco, best-effort ([] quando indisponível)."""
    try:
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        return list(ProfileManager(controller=daemon.controller).list_profiles())
    except Exception:
        logger.debug("launch_env_perfis_indisponiveis", exc_info=True)
        return []


def _o_freestyle_que_manda(daemon: DaemonProtocol) -> Any | None:
    """O perfil Freestyle quando o Modo Freestyle está ligado; ``None`` quando não."""
    from hefesto_dualsense4unix.profiles.manager import e_o_freestyle, o_freestyle_manda

    if not o_freestyle_manda(getattr(daemon, "store", None)):
        return None
    for profile in _load_profiles(daemon):
        if e_o_freestyle(getattr(profile, "name", None)):
            return profile
    return None


def _steam_profiles(daemon: DaemonProtocol) -> list[tuple[int, Any]]:
    """(appid, Profile) para cada perfil com `steam_app_<appid>` no match."""
    out: list[tuple[int, Any]] = []
    for profile in _load_profiles(daemon):
        match = getattr(profile, "match", None)
        for wc in getattr(match, "window_class", None) or []:
            appid = steam_appid_from_wm_class(str(wc))
            if appid is not None:
                out.append((appid, profile))
    return out


def _nativos_fora_da_antecipacao(profiles: Sequence[Any]) -> list[str]:
    """Nomes dos perfis NATIVOS que a antecipação por-appid NÃO cobre."""
    out: list[str] = []
    for profile in profiles:
        kind = getattr(getattr(profile, "mode", None), "kind", None)
        if kind != "native":
            continue
        match = getattr(profile, "match", None)
        wcs = [str(wc) for wc in getattr(match, "window_class", None) or []]
        coberto = (
            bool(wcs)
            and all(steam_appid_from_wm_class(wc) is not None for wc in wcs)
            and not getattr(match, "window_title_regex", None)
            and not (getattr(match, "process_name", None) or [])
        )
        if not coberto:
            out.append(str(getattr(profile, "name", "?")))
    return out


def _permite_uhid(daemon: Any) -> bool:
    """Gate VPAD-08 da factory, tolerante a dublês (R-05)."""
    try:
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            controller_allows_uhid,
        )

        return bool(controller_allows_uhid(daemon))
    except Exception:
        return False


@dataclass(frozen=True)
class ModoAntecipado:
    """O modo que o perfil de um jogo IMPÕE quando ele estiver valendo."""

    native: bool
    emulacao: bool
    mascara: str
    backends: tuple[str, ...]
    motivo: str
    fisicos: int = 0
    pronto_para_troca: bool = False

    def como_estado(self) -> str:
        """A mesma gramática do `estado:` global, para os dois compararem."""
        pronto = " pronto_para_troca=True" if self.pronto_para_troca else ""
        return (
            f"native={self.native} emulacao={self.emulacao} "
            f"mascara={self.mascara} backends={list(self.backends) or '[]'}{pronto}"
        )


def divergencia_de_mascara(
    modo: ModoAntecipado | None,
    *,
    native_vivo: bool,
    emulacao_viva: bool,
    flavor_vivo: str,
) -> str | None:
    """Motivo curto da divergência perfil-vs-aparelho, ou None quando casam."""
    if modo is None or modo.native or not modo.emulacao:
        return None
    if native_vivo:
        return f"perfil_{modo.mascara}_vs_vivo_nativo"
    if not emulacao_viva:
        return f"perfil_{modo.mascara}_vs_vivo_sem_emulacao"
    if modo.mascara != flavor_vivo:
        return f"perfil_{modo.mascara}_vs_vivo_{flavor_vivo}"
    return None


def _modo_antecipado(
    profile: Any,
    *,
    flavor_atual: str,
    backends: list[str],
    permite_uhid: bool = False,
    fisicos: int = 0,
    identidade: str | None = None,
    vpads_previstos: int = 1,
) -> ModoAntecipado | None:
    """O `ModoAntecipado` do perfil, ou None quando ele não tem opinião."""
    mode = getattr(profile, "mode", None)
    if mode is None:
        return None
    kind = getattr(mode, "kind", None)
    if kind == "native":
        return ModoAntecipado(
            native=True, emulacao=False, mascara=flavor_atual,
            backends=(), motivo="perfil nativo",
        )
    mascara = _mascara_prevista(profile, mode, flavor_atual=flavor_atual, identidade=identidade)
    if kind == "desktop":
        # que abriu na Navegação fica com o DualSense de plástico (que o Hefesto
        # fora do Modo Nativo o jogo não vê o DualSense de plástico, com perfil ou
        return ModoAntecipado(
            native=False, emulacao=False, mascara=mascara,
            backends=_backends_da_troca(
                mascara, getattr(mode, "caminho", None), permite_uhid,
                quantos=vpads_previstos,
            ),
            motivo="perfil desktop (pronto para o PS + R3)",
            fisicos=fisicos, pronto_para_troca=True,
        )
    if kind == "gamepad":
        from hefesto_dualsense4unix.integrations.virtual_pad import normalizar_caminho

        flavor = mascara
        if flavor in _MASCARAS_SO_EVDEV:
            return ModoAntecipado(
                native=False, emulacao=True, mascara=flavor,
                backends=("uinput",), motivo=f"perfil gamepad {flavor}",
            )
        if normalizar_caminho(getattr(mode, "caminho", None)) == "xbox":
            # PS-L3-MASCARA-01: o caminho Xbox com a máscara DualSense é o Edge
            return ModoAntecipado(
                native=False, emulacao=True, mascara=flavor,
                backends=("uinput",), motivo="perfil gamepad dualsense (caminho xbox)",
            )
        # DualSense físico junto com o virtual (o controle duplicado).
        backends_efetivos = backends
        fisicos_efetivos = fisicos
        motivo = "perfil gamepad dualsense (backends reais)"
        if flavor != flavor_atual or not backends:
            from hefesto_dualsense4unix.integrations.uhid_gamepad import uhid_available

            prognostico_uhid = uhid_available() and permite_uhid
            backends_efetivos = ["uhid"] if prognostico_uhid else backends
            fisicos_efetivos = 0
            motivo = (
                "perfil gamepad dualsense (prognóstico uhid)"
                if prognostico_uhid
                else "perfil gamepad dualsense (prognóstico conservador)"
            )
        return ModoAntecipado(
            native=False, emulacao=True, mascara=flavor,
            backends=tuple(backends_efetivos), motivo=motivo,
            fisicos=fisicos_efetivos,
        )
    return None


def _env_for_profile(
    profile: Any,
    *,
    flavor_atual: str,
    backends: list[str],
    permite_uhid: bool = False,
    fisicos: int = 0,
) -> tuple[dict[str, str], str] | None:
    """(env, motivo) antecipando o modo que o perfil impõe; None = sem opinião."""
    modo = _modo_antecipado(
        profile,
        flavor_atual=flavor_atual,
        backends=backends,
        permite_uhid=permite_uhid,
        fisicos=fisicos,
    )
    if modo is None:
        return None
    return env_do_modo(modo), modo.motivo


def env_do_modo(modo: ModoAntecipado) -> dict[str, str]:
    """A `env` que materializa um `ModoAntecipado`."""
    return compose_env(
        native_mode=modo.native,
        emulation_enabled=modo.emulacao or modo.pronto_para_troca,
        flavor=modo.mascara,
        backends=list(modo.backends),
        fisicos=modo.fisicos,
    )


def appids_em_cena(
    daemon: Any, *, base_dir: Path | None = None, now: float | None = None
) -> set[int]:
    """Appids cujo perfil está (ou deveria estar) VALENDO agora."""
    out: set[int] = set()
    with contextlib.suppress(Exception):
        sessao = launch_session_appid(base_dir=base_dir, now=now)
        if sessao is not None:
            out.add(sessao)
    with contextlib.suppress(Exception):
        store = getattr(daemon, "store", None)
        wm_class = getattr(store, "window_detect_current_class", None)
        foco = steam_appid_from_wm_class(
            wm_class if isinstance(wm_class, str) else None
        )
        if foco is not None:
            out.add(foco)
    return out


def divergencias_publicadas(daemon: Any) -> list[dict[str, Any]]:
    """As divergências da ÚLTIMA materialização — leitura de memória, sem I/O.

    O `state_full` roda a 10-20 Hz e não pode ler perfis do disco; a mesma
    disciplina do `dedup_broken`, que se mede na borda de materialização e se
    publica daqui.
    """
    valor = getattr(daemon, "_mascara_divergencias", None)
    if not isinstance(valor, list):
        return []
    return [item for item in valor if isinstance(item, dict)]


def _publicar_divergencias(
    daemon: Any, divergencias: list[dict[str, Any]]
) -> None:
    """Grava as divergências no daemon e loga as TRANSIÇÕES no journal.

    MASCARA-01: a linha do arquivo por appid é diagnóstico para quem abre o
    arquivo; o journal e o `state_full` são o que faz a divergência agir. Só
    transições são logadas — a materialização roda em toda troca de estado e um
    log por passagem viraria ruído (e a mesma divergência ficaria "nova" para
    sempre).
    """
    anteriores = {
        (item.get("appid"), item.get("motivo"))
        for item in divergencias_publicadas(daemon)
    }
    atuais = {(item["appid"], item["motivo"]) for item in divergencias}
    with contextlib.suppress(Exception):
        daemon._mascara_divergencias = divergencias
    for item in divergencias:
        if (item["appid"], item["motivo"]) in anteriores:
            continue
        if item["em_cena"]:
            # DualSense com o jogo aberto. Warning porque é defeito visível
            logger.warning(
                "mascara_do_perfil_divergente",
                appid=item["appid"],
                profile=item["profile"],
                mascara_perfil=item["mascara_perfil"],
                mascara_viva=item["mascara_viva"],
                motivo=item["motivo"],
            )
        else:
            logger.info(
                "mascara_do_perfil_antecipada",
                appid=item["appid"],
                profile=item["profile"],
                mascara_perfil=item["mascara_perfil"],
                mascara_viva=item["mascara_viva"],
            )
    for appid, motivo in sorted(
        anteriores - atuais, key=lambda par: (par[0] or 0, par[1] or "")
    ):
        logger.info("mascara_do_perfil_convergiu", appid=appid, motivo=motivo)


def _render(env: dict[str, str], estado: str) -> str:
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    lines = [
        "# Materializado pelo daemon do Hefesto (DEDUP-04). Não edite:",
        "# é regravado a cada transição de estado do gamepad virtual.",
        f"# estado: {estado} | {ts}",
    ]
    lines.extend(f"{key}={value}" for key, value in env.items())
    return "\n".join(lines) + "\n"


def _write_atomic(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _jogadores_sem_imu(daemon: DaemonProtocol) -> list[str]:
    """Quem está com o par «máscara DualSense + caminho Xbox» AGORA.

    Nomeia, nunca só conta (WRAPPER-EM-TODOS-01), pelo número da CARTA — o
    do nome do pad, da lâmpada e do cartão (O-NUMERO-DO-JOGADOR-SE-REORGANIZA-
    NA-HORA-E-O-JOGO-VE-01, cura 2; era o `player_index` do co-op, o índice de
    alocação). O contágio leva os quatro jogadores juntos porque o caminho é
    da SESSÃO, e um evento que dissesse só «o P1» faria a mesa de quatro
    parecer um caso isolado.

    SÓ LEITURA, e nunca levanta: este é um diagnóstico dentro de uma
    materialização que não pode derrubar o start da emulação.
    """
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import _rotulo_do_jogador
    from hefesto_dualsense4unix.integrations.canal_sem_imu import canal_sem_imu_do_vpad

    fora: list[str] = []
    coop = getattr(daemon, "_coop_manager", None)
    if canal_sem_imu_do_vpad(getattr(daemon, "_gamepad_device", None)):
        primario = getattr(coop, "numero_do_primario_no_diario", None)
        numero = primario() if callable(primario) else 1
        valido = isinstance(numero, int) and not isinstance(numero, bool) and numero >= 1
        fora.append(str(numero) if valido else "1")
    jogadores = getattr(coop, "_players", None)
    if isinstance(jogadores, dict):
        for jogador in jogadores.values():
            if not canal_sem_imu_do_vpad(getattr(jogador, "vpad", None)):
                continue
            fora.append(_rotulo_do_jogador(coop, jogador))
    return fora


def _avisar_canal_sem_imu(
    daemon: DaemonProtocol, *, native: bool, enabled: bool
) -> None:
    """Registra `canal_sem_imu` no journal do launch. CANAL-SEM-VOZ-01.

    Os gates são os mesmos do `dedup_broken` ao lado, e pela mesma razão: em
    Modo Nativo o jogo fala com o DualSense físico (a IMU está no ar, e por
    outro fio), e com a emulação desligada não há vpad sobre o que falar. Fora
    esses dois, o evento sai sempre que o par estiver de pé — a borda de
    materialização já é a transição, e é por isso que ele mora aqui e não no
    `state_full` de 20 Hz, que viraria enxurrada.

    `linhas` sai com as chaves do mapa, em ordem estável, porque é por elas que
    se procura: `movimento.giroscopio.jogo` é greppável no mapa, na suíte e no
    journal, e uma frase bonita não é.
    """
    if native or not enabled:
        return
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.integrations import canal_sem_imu as sem_imu
        from hefesto_dualsense4unix.integrations.virtual_pad import CAMINHO_XBOX

        jogadores = _jogadores_sem_imu(daemon)
        if not jogadores:
            return
        linhas = sem_imu.chaves_fora_do_ar()
        logger.warning(
            sem_imu.EVENTO,
            jogadores=jogadores,
            mascara=sem_imu.MASCARA_QUE_PROMETE,
            caminho=CAMINHO_XBOX,
            backend="uinput",
            quantas=len(linhas),
            linhas=list(linhas),
        )


def _device_ks_nos_lancadores() -> dict[str, int]:
    """Grava o device KS nos prefixos dos LANÇADORES. Nunca levanta."""
    fora = {"escritos": 0, "ocupados": 0, "prefixos": 0}
    try:
        from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
        from hefesto_dualsense4unix.integrations.audio_ks_dualsense import (
            aplicar,
            controles_do_registro,
        )
        from hefesto_dualsense4unix.integrations.lista_de_exclusao import (
            prefixos_excluidos,
        )

        fora_da_exclusao = prefixos_excluidos()
        prefixos = [
            p for p in cv.prefixos_dos_lancadores()
            if (p / "pfx" / "system.reg").is_file()
            and p.resolve() not in fora_da_exclusao
        ]
        fora["prefixos"] = len(prefixos)
        if not prefixos:
            return fora
        controles = controles_do_registro()
        for prefixo in prefixos:
            try:
                r = aplicar(prefixo, controles=controles)
            except OSError:
                continue
            if r.motivo == "ocupado":
                fora["ocupados"] += 1
            elif r.escreveu:
                fora["escritos"] += 1
    except Exception:
        logger.debug("device_ks_nos_lancadores_falhou", exc_info=True)
    return fora


def materialize_launch_env(daemon: DaemonProtocol) -> None:
    """Regrava `default.env` + `steam_app_<appid>.env` com o estado REAL."""
    escrevente = _ESCREVENTE
    no_fio = (
        escrevente is not None
        and not getattr(_NA_HORA, "ligada", False)
        and escrevente.atende_aqui()
    )
    foto = _a_foto_ou_nada(daemon, no_fio=no_fio)
    if foto is None:
        return
    if no_fio and escrevente is not None:
        escrevente.pedir(foto)
        return
    _escrever_o_lancamento(foto)


def _a_parte_de_fora(
    foto: _FotoDoLancamento, devolver: Callable[[Callable[[], None]], None]
) -> None:
    """A materialização sobre a foto: os perfis, os modos, a escrita, as estradas."""
    t0 = time.perf_counter()
    target = launch_env_dir(ensure=True)
    native, enabled, flavor = foto.native, foto.enabled, foto.flavor
    backends = list(foto.backends)
    fisicos = foto.fisicos
    leitor = foto.leitor
    modo_vivo = foto.modo_vivo
    estado = modo_vivo.como_estado()
    # vivo e, sem vpad de pé, abria o jogo com o DualSense de plástico à
    default_env = env_do_modo(modo_vivo)
    if "SDL_GAMECONTROLLER_IGNORE_DEVICES" in default_env:
        arriscados = _nativos_fora_da_antecipacao(_load_profiles(leitor))
        if arriscados:
            del default_env["SDL_GAMECONTROLLER_IGNORE_DEVICES"]
            estado += " ignore_omitido=perfil_nativo_sem_appid"
            logger.info(
                "launch_env_ignore_omitido_por_perfil_nativo",
                perfis=arriscados,
            )
    _write_atomic(target / "default.env", _render(default_env, estado))
    desired = {"default.env"}
    em_cena = foto.em_cena
    divergencias: list[dict[str, Any]] = []
    freestyle = _o_freestyle_que_manda(leitor)
    for appid, do_jogo in _steam_profiles(leitor):
        profile = freestyle if freestyle is not None else do_jogo
        modo = _modo_antecipado(
            profile,
            flavor_atual=flavor,
            backends=backends,
            identidade=foto.identidade,
            permite_uhid=foto.permite_uhid,
            fisicos=fisicos,
            vpads_previstos=foto.vpads_previstos,
        )
        if modo is None:
            continue
        estado_do_perfil = f"{modo.motivo} | {modo.como_estado()}"
        motivo_divergencia = divergencia_de_mascara(
            modo,
            native_vivo=native,
            emulacao_viva=enabled,
            flavor_vivo=flavor,
        )
        if motivo_divergencia is not None:
            estado_do_perfil += f" divergente={motivo_divergencia}"
            divergencias.append(
                {
                    "appid": appid,
                    "profile": str(getattr(profile, "name", "?")),
                    "mascara_perfil": modo.mascara,
                    "mascara_viva": flavor,
                    "motivo": motivo_divergencia,
                    "em_cena": appid in em_cena,
                }
            )
        name = f"steam_app_{appid}.env"
        _write_atomic(
            target / name, _render(env_do_modo(modo), f"{estado_do_perfil} | vivo: {estado}")
        )
        desired.add(name)
    devolver(lambda: foto.publicar(divergencias))
    for stale in target.glob("steam_app_*.env"):
        if stale.name not in desired:
            with contextlib.suppress(OSError):
                stale.unlink()
    devolver(foto.carimbar)
    from hefesto_dualsense4unix.integrations.cura_por_estrada import (
        curar_todas_as_estradas,
    )

    estradas = curar_todas_as_estradas()
    ks = _device_ks_nos_lancadores()
    logger.info(
        "launch_env_materializado",
        native=native,
        emulacao=enabled,
        mascara=flavor,
        backends=backends,
        arquivos=len(desired),
        estradas=list(estradas),
        device_ks=ks,
        foto_ms=round(foto.foto_ms, 1),
        fora_ms=round((time.perf_counter() - t0) * 1000, 1),
    )


def _rodar_na_hora(acao: Callable[[], None]) -> None:
    """A devolução da escrita de sempre: na hora, no fio de quem chamou."""
    acao()


_TRAVA_DA_ESCRITA = threading.Lock()
_ULTIMA_ORDEM_ESCRITA = 0


def _escrever_o_lancamento(
    foto: _FotoDoLancamento,
    devolver: Callable[[Callable[[], None]], None] = _rodar_na_hora,
) -> bool:
    """A parte de fora, sob a trava da escrita. False = havia uma foto mais nova."""
    global _ULTIMA_ORDEM_ESCRITA
    with _TRAVA_DA_ESCRITA:
        if foto.ordem <= _ULTIMA_ORDEM_ESCRITA:
            return False
        try:
            _a_parte_de_fora(foto, devolver)
        except Exception:
            logger.warning("launch_env_materialize_falhou", exc_info=True)
        _ULTIMA_ORDEM_ESCRITA = foto.ordem
        return True


def _a_foto_ou_nada(daemon: DaemonProtocol, *, no_fio: bool) -> _FotoDoLancamento | None:
    """A foto do daemon vivo, ou None (com o aviso) — nunca levanta."""
    try:
        return _foto_do_lancamento(daemon, no_fio=no_fio)
    except Exception:
        logger.warning("launch_env_materialize_falhou", exc_info=True)
        return None


class _OQueOFioLe:
    """O que a parte de fora lê no lugar do daemon — O-APP-RESPONDE-NA-HORA-01."""

    def __init__(self, freestyle_ligado: bool) -> None:
        self.controller = None
        self.store = _StoreDaFoto(freestyle_ligado)


@dataclass(frozen=True)
class _StoreDaFoto:
    freestyle_ligado: bool


@dataclass(frozen=True)
class _FotoDoLancamento:
    """Tudo o que a materialização pergunta ao daemon VIVO, tirado no laço."""

    ordem: int
    native: bool
    enabled: bool
    flavor: str
    backends: tuple[str, ...]
    fisicos: int
    modo_vivo: ModoAntecipado
    em_cena: frozenset[int]
    identidade: str | None
    permite_uhid: bool
    vpads_previstos: int
    leitor: Any
    publicar: Callable[[list[dict[str, Any]]], None]
    carimbar: Callable[[], None]
    foto_ms: float


_ORDEM_DAS_FOTOS = itertools.count(1)


def _foto_do_lancamento(daemon: DaemonProtocol, *, no_fio: bool) -> _FotoDoLancamento:
    """A foto do daemon vivo, com as vozes do diagnóstico que leem dele."""
    t0 = time.perf_counter()
    native, enabled, flavor, backends, fisicos = _snapshot(daemon)
    modo_vivo = modo_do_estado_vivo(
        daemon, native=native, enabled=enabled, flavor=flavor,
        backends=backends, fisicos=fisicos,
    )
    # materialização (transição de estado) — nunca no state_full de 20 Hz.
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import dedup_status

    dedup_ok, dedup_motivos = dedup_status(daemon)
    if not dedup_ok and not native and enabled and backends:
        logger.warning("dedup_broken", motivos=dedup_motivos, backends=backends)
    # O QUE ELE DIZ QUE NINGUÉM DIZIA: com a máscara DualSense de pé, o
    # PRAGMATA com controle por movimento e o controle não respondeu.
    _avisar_canal_sem_imu(daemon, native=native, enabled=enabled)
    # O diário só acusa a FALHA do vpad (emulação ligada e nenhum vpad), com o
    # estado real da mesa; a Navegação não é defeito (D-2909).
    from hefesto_dualsense4unix.daemon.subsystems.rumble import (
        sem_dono_do_rumble,
    )

    if sem_dono_do_rumble(
        native=native, backends=backends, emulacao=enabled
    ):
        logger.warning(
            "rumble_sem_dono",
            motivo="sem_vpad_e_sem_modo_nativo",
            native=native,
            emulacao=enabled,
            backends=backends,
        )
    from hefesto_dualsense4unix.profiles.manager import o_freestyle_manda

    freestyle_ligado = o_freestyle_manda(getattr(daemon, "store", None))
    recibo = (
        native, enabled, flavor, tuple(backends), fisicos,
        _o_freestyle_na_assinatura(daemon),
    )

    ordem = next(_ORDEM_DAS_FOTOS)

    def carimbar() -> None:
        if ordem < _ULTIMA_ORDEM_ESCRITA:
            return
        with contextlib.suppress(Exception):
            daemon._launch_env_assinatura = recibo  # type: ignore[attr-defined]

    def publicar(divergencias: list[dict[str, Any]]) -> None:
        if ordem < _ULTIMA_ORDEM_ESCRITA:
            return
        _publicar_divergencias(daemon, divergencias)

    return _FotoDoLancamento(
        ordem=ordem,
        native=native,
        enabled=enabled,
        flavor=flavor,
        backends=tuple(backends),
        fisicos=fisicos,
        modo_vivo=modo_vivo,
        em_cena=frozenset(appids_em_cena(daemon)),
        identidade=_identidade_do_primario(daemon),
        permite_uhid=_permite_uhid(daemon),
        vpads_previstos=_vpads_previstos(daemon, fisicos),
        leitor=_OQueOFioLe(freestyle_ligado) if no_fio else daemon,
        publicar=publicar,
        carimbar=carimbar,
        foto_ms=(time.perf_counter() - t0) * 1000,
    )


class EscreventeDoLancamento:
    """O fio que escreve o lançamento fora do laço do serviço."""

    def __init__(
        self,
        devolver: Callable[[Callable[[], None]], None],
        laco: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._devolver = devolver
        self._laco_que_armou = laco
        self._trava = threading.Lock()
        self._pendente: _FotoDoLancamento | None = None
        self._tem_pedido = threading.Event()
        self._parar = False
        self.escritas = 0
        self._pedida = 0
        self._pousada = 0
        self._fio = threading.Thread(
            target=self._laco, name="hefesto-lancamento", daemon=True
        )
        self._fio.start()

    def atende_aqui(self) -> bool:
        """Quem pede está no laço que armou? (Sem laço, sempre.)"""
        if self._laco_que_armou is None:
            return True
        try:
            return asyncio.get_running_loop() is self._laco_que_armou
        except RuntimeError:
            return False

    def vivo(self) -> bool:
        """O laço que armou ainda existe? Um laço fechado não recebe devolução."""
        laco = self._laco_que_armou
        return laco is None or not laco.is_closed()

    def pedir(self, foto: _FotoDoLancamento) -> None:
        """Guarda a foto mais nova e acorda o fio. Não espera a escrita."""
        with self._trava:
            self._pendente = foto
            self._pedida = max(self._pedida, foto.ordem)
            self._tem_pedido.set()

    def em_voo(self) -> bool:
        """Há foto pedida cujo recibo ainda não voltou ao laço?"""
        with self._trava:
            return self._pedida > self._pousada

    def _pousou(self, ordem: int) -> None:
        with self._trava:
            self._pousada = max(self._pousada, ordem)

    def esvaziar_e_parar(self, teto_s: float = 5.0) -> None:
        """Escreve o que estiver pendente e para o fio (até `teto_s`)."""
        with self._trava:
            self._parar = True
            self._tem_pedido.set()
        self._fio.join(teto_s)

    def _laco(self) -> None:
        while True:
            self._tem_pedido.wait()
            with self._trava:
                foto, self._pendente = self._pendente, None
                self._tem_pedido.clear()
                parar = self._parar
            if foto is not None:
                try:
                    if _escrever_o_lancamento(foto, self._devolver):
                        self.escritas += 1
                finally:
                    def pousou(ordem: int = foto.ordem) -> None:
                        self._pousou(ordem)

                    with contextlib.suppress(Exception):
                        self._devolver(pousou)
            if not parar:
                continue
            with self._trava:
                if self._pendente is None:
                    return
                self._tem_pedido.set()


_ESCREVENTE: EscreventeDoLancamento | None = None


def _a_escrita_em_voo() -> bool:
    """O escrevente armado tem uma escrita cujo recibo ainda não voltou ao laço?"""
    escrevente = _ESCREVENTE
    return escrevente is not None and escrevente.vivo() and escrevente.em_voo()


_NA_HORA = threading.local()


def armar_o_escrevente(
    devolver: Callable[[Callable[[], None]], None],
    laco: asyncio.AbstractEventLoop | None = None,
) -> EscreventeDoLancamento | None:
    """Arma o escrevente do processo. Devolve-o, ou None se já havia um vivo."""
    global _ESCREVENTE
    velho = _ESCREVENTE
    if velho is not None and velho.vivo():
        return None
    _ESCREVENTE = EscreventeDoLancamento(devolver, laco)
    if velho is not None:
        velho.esvaziar_e_parar(teto_s=0.0)
    return _ESCREVENTE


def desarmar_o_escrevente(escrevente: EscreventeDoLancamento, teto_s: float = 5.0) -> None:
    """Desarma (as próximas são na hora) e escreve o que estiver pendente."""
    global _ESCREVENTE
    if _ESCREVENTE is escrevente:
        _ESCREVENTE = None
    escrevente.esvaziar_e_parar(teto_s)


@contextlib.contextmanager
def escrita_na_hora() -> Iterator[None]:
    """Dentro do bloco, `materialize_launch_env` escreve antes de voltar."""
    antes = getattr(_NA_HORA, "ligada", False)
    _NA_HORA.ligada = True
    try:
        yield
    finally:
        _NA_HORA.ligada = antes


def _identidade_do_primario(daemon: Any) -> str | None:
    """O MAC do jogador 1 (`gamepad.primary_identity`), ou None. Nunca levanta."""
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import primary_identity

        return primary_identity(daemon)
    return None


def _mascara_do_primario(daemon: Any, cfg: Any) -> str:
    """A máscara que o jogador 1 VESTE — a que o jogo vê.

    Esta env lia `config.gamepad_flavor`, a máscara da SESSÃO, e o jogo vê a do
    CARTÃO quando há uma (`external_mask.mascara_efetiva`). Medido na máquina
    dela em 14/09: sessão `xbox`, cartão `dualsense`, o journal dizendo
    `mascara_viva=xbox` com o vpad vestindo DualSense, e a env do Sony DualSense
    saindo com o `SDL_JOYSTICK_HIDAPI=0` do Xbox.

    Com o vpad de pé, a prova é o `flavor` dele; sem vpad, a máscara efetiva.
    """
    sessao = str(getattr(cfg, "gamepad_flavor", "dualsense") or "dualsense")
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            mascara_efetiva,
            mascara_vestida,
        )

        vivo = mascara_vestida(daemon)
        if isinstance(vivo, str) and vivo:
            return vivo
        return mascara_efetiva(_identidade_do_primario(daemon), sessao)
    return sessao


def _mascara_do_cartao(profile: Any, identidade: str | None) -> str | None:
    """A máscara que o PERFIL guarda no cartão do jogador 1, ou None."""
    if not identidade:
        return None
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import normalizar_mascara

    controles = getattr(profile, "controllers", None)
    if not isinstance(controles, dict):
        return None
    chave = norm_mac(identidade)
    dele = controles.get(chave) if chave else None
    return normalizar_mascara(getattr(dele, "mascara", None))


def _mascara_prevista(
    profile: Any, mode: Any, *, flavor_atual: str, identidade: str | None
) -> str:
    """A máscara que o jogo vai ver quando o perfil valer.

    A ordem é a de `external_mask.mascara_efetiva` (MASCARA-NO-PERFIL-01): o
    cartão do jogador 1 que o perfil guarda, a máscara padrão do perfil, a
    vigente. O prognóstico lia só a padrão, e o jogo com cartão DualSense e
    padrão `xbox` abria com a env do Xbox.
    """
    do_cartao = _mascara_do_cartao(profile, identidade)
    if do_cartao is not None:
        return do_cartao
    return str(getattr(mode, "gamepad_flavor", None) or flavor_atual)


def _backends_da_troca(
    mascara: str, caminho: Any, permite_uhid: bool, *, quantos: int = 1
) -> tuple[str, ...]:
    """Os canais que os vpads vão ter quando ela subir para um modo de jogo.

    `quantos` é a COBERTURA prometida — um vpad por DualSense físico quando o
    co-op está ligado, senão um só (TROCA-DENTRO-DO-JOGO-01, 14/09/2026). Sem
    ele a promessa era sempre de um vpad, e numa mesa de dois o IGNORE saía
    escondendo os dois físicos com um vpad prometido: o jogador 2 ficava sem
    controle até o co-op adotá-lo.
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import uhid_available
    from hefesto_dualsense4unix.integrations.virtual_pad import quer_uhid

    canal_proprio = quer_uhid(caminho, mascara)
    canal = "uhid" if (canal_proprio and permite_uhid and uhid_available()) else "uinput"
    return (canal,) * max(1, quantos)


def _vpads_previstos(daemon: Any, fisicos: int) -> int:
    """Quantos vpads existirão quando ela subir um modo de jogo.

    Com o co-op LIGADO, um por DualSense físico (é o que o `coop` faz ao subir);
    desligado, um só — todos os controles alimentam o mesmo vpad, e a mesa é de
    um jogador. TROCA-DENTRO-DO-JOGO-01 (14/09/2026).
    """
    cfg = getattr(daemon, "config", None)
    if fisicos > 1 and bool(getattr(cfg, "coop_enabled", False)):
        return fisicos
    return 1


def modo_do_estado_vivo(
    daemon: Any,
    *,
    native: bool,
    enabled: bool,
    flavor: str,
    backends: Sequence[str],
    fisicos: int,
) -> ModoAntecipado:
    """O modo que o `default.env` materializa — o de TODO jogo sem arquivo próprio.

    TROCA-DENTRO-DO-JOGO-01 (14/09/2026). O `default.env` copiava o estado VIVO:
    sem vpad de pé (a Navegação, ou a emulação caída) ele saía sem IGNORE e sem
    DISABLE, e o jogo aberto assim via o DualSense de plástico. Como a env é lida
    UMA vez no `exec`, o PS + R3 dentro do jogo não a alcança: o físico morre
    grabado e o vpad chega como segundo controle. Era o defeito medido no Future
    Knight — e o Future Knight só era o jogo com perfil próprio. Na máquina dela,
    em 14/09, 1 dos 30 perfis tinha `mode`: os outros 29 jogos liam este arquivo.

    DECISÃO DELA (D-1409-FORA-DO-NATIVO-O-JOGO-VE-SO-O-VIRTUAL): fora do Modo
    Nativo o jogo vê só o controle virtual, com perfil ou sem perfil. Aqui isso é
    uma regra só, do mesmo tipo que o arquivo por appid usa — o `ModoAntecipado`.

    O Modo Nativo continua entregando o físico, e é por isso que ele é a exceção:
    lá o vpad não existe de propósito.
    """
    fisicos = max(0, int(fisicos))
    if native:
        return ModoAntecipado(
            native=True, emulacao=False, mascara=flavor,
            backends=tuple(backends), motivo="modo nativo (o jogo vê o físico)",
            fisicos=fisicos,
        )
    if enabled and backends:
        return ModoAntecipado(
            native=False, emulacao=True, mascara=flavor,
            backends=tuple(backends), motivo="estado vivo",
            fisicos=fisicos,
        )
    if enabled:
        return ModoAntecipado(
            native=False, emulacao=False, mascara=flavor,
            backends=(), motivo="emulação ligada sem vpad (falha)",
            fisicos=fisicos,
        )
    cfg = getattr(daemon, "config", None)
    return ModoAntecipado(
        native=False, emulacao=False, mascara=flavor,
        backends=_backends_da_troca(
            flavor, getattr(cfg, "gamepad_caminho", None), _permite_uhid(daemon),
            quantos=_vpads_previstos(daemon, fisicos),
        ),
        motivo="pronto para o PS + R3 (sem vpad agora)",
        fisicos=fisicos, pronto_para_troca=True,
    )


__all__ = [
    "ENV_ALLOWLIST",
    "ESTADO_ALLOWLIST_STEAM_INPUT",
    "JANELA_DE_SOSSEGO_SEC",
    "LAUNCH_ARM_WINDOW_SEC",
    "PAR_DUALSENSE_FISICO",
    "WRAPPER_MARKER_WINDOW_SEC",
    "ModoAntecipado",
    "appids_em_cena",
    "arm_launch_profile",
    "armar_rematerializacao",
    "cobertura_total",
    "compor_lista_vidpid",
    "compose_env",
    "divergencia_de_mascara",
    "divergencias_publicadas",
    "env_do_modo",
    "launch_session_appid",
    "materialize_launch_env",
    "modo_do_estado_vivo",
    "pid_is_alive",
    "ponte_do_lancamento",
    "read_last_exit_marker",
    "read_last_exit_pid",
    "read_last_run_marker",
    "read_last_run_pid",
    "rematerializar_se_sossegou",
    "steam_appid_from_wm_class",
    "steam_input_appids",
    "steam_input_exception_appid",
    "tique_da_escada",
    "valor_disable_hidraw",
    "valor_ignore_devices",
    "vigiar_a_mesa",
    "wrapper_game_running",
    "wrapper_used_state",
]
