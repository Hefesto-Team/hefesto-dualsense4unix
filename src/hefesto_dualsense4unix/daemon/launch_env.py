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
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import os
import re
import time
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    "PROTON_DISABLE_HIDRAW",
    "__GL_SHADER_DISK_CACHE",
    "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP",
)

_IGNORE_VALUE = "0x054c/0x0ce6"

#: GUERRA-01: lista VID/PID que o winebus.sys dos Protons 10/11 lê para NEGAR
#: hidraw (a whitelist default dele dá hidraw à família Sony INTEIRA — físico
#: 0ce6 E vpad 0df2 — e ignora a env do SDL). SÓ o físico entra aqui: o vpad
#: Edge 0df2 PRECISA do hidraw (é por ele que rumble/triggers/lightbar do
#: jogo chegam) — NUNCA incluir 0x0DF2. `PROTON_ENABLE_HIDRAW` morreu no
#: Proton 10 e foi aposentada (só AMPLIAVA exposição).
_DISABLE_HIDRAW_VALUE = "0x054C/0x0CE6"

_STEAM_APP_WC_RE = re.compile(r"^steam_app_(\d+)$")

#: GUI-05 item 3 (honestidade do dedup): idade MÁXIMA, em segundos, do marker
#: `last_run` (gravado pelo wrapper no LAUNCH) em relação à PRIMEIRA detecção
#: da janela `steam_app_<appid>`. A janela serve para DESCARTAR markers de
#: sessões ANTIGAS (o jogo de ontem/horas atrás) — NÃO para limitar a latência
#: launch→janela: jogos pesados (Proton na 1ª execução, compilação de shaders,
#: RDR2 com o Rockstar Launcher) só abrem a janela `steam_app_N` minutos depois
#: do launch, e o marker legítimo desse launch ficaria fora de uma janela
#: curta, derrubando `wrapper_used` para false no MEIO do jogo (falso alarme
#: de "jogo sem wrapper"). Por isso 15 min: cobre o carregamento AAA mais lento
#: e ainda rejeita marker de uma sessão de verdade velha. Marker de outro
#: appid, ou ausente = o jogo NÃO passou pelo `hefesto-launch`.
WRAPPER_MARKER_WINDOW_SEC = 900.0


def steam_appid_from_wm_class(wm_class: str | None) -> int | None:
    """Appid do jogo a partir da wm_class (`steam_app_N`), ou None."""
    if not isinstance(wm_class, str):
        return None
    m = _STEAM_APP_WC_RE.match(wm_class)
    return int(m.group(1)) if m is not None else None


def _read_kv_int_fields(path: Path) -> dict[str, int]:
    """Lê um marker chave=valor (NUMÉRICO), best-effort — nunca levanta.

    Compartilhado por `read_last_run_marker`/`read_last_run_pid`/
    `read_last_exit_marker`: linhas desconhecidas ou com valor não-dígito
    são ignoradas silenciosamente (marker corrompido/adulterado não quebra
    o parse dos campos válidos). Arquivo ausente/ilegível devolve `{}`.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    except Exception:  # defensivo: leitura de marker jamais derruba o IPC
        logger.debug("wrapper_marker_read_falhou", exc_info=True)
        return {}
    out: dict[str, int] = {}
    for line in text.splitlines():
        key, _, value = line.partition("=")
        value = value.strip()
        if value.isdigit():
            out[key] = int(value)
    return out


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
    """Lê o campo `pid=` OPCIONAL do marker `last_run` (NUMA-01), ou None.

    `pid=$$` é gravado pelo wrapper no MOMENTO do launch — como `exec env
    "$@"` preserva o PID (o wrapper VIRA o jogo), este é o pid do próprio
    processo do jogo enquanto ele roda. Ausente (marker antigo, sem o
    campo) ou lixo (não-dígito) devolve None. Nunca levanta.
    """
    path = (base_dir if base_dir is not None else launch_env_dir()) / "last_run"
    return _read_kv_int_fields(path).get("pid")


def read_last_exit_marker(base_dir: Path | None = None) -> int | None:
    """Lê o marker `last_exit` do wrapper: epoch (int) ou None (NUMA-01).

    Formato: ``epoch=<unix epoch s>`` (+ ``pid=<int>`` OPCIONAL desde a
    correção pós-auditoria, ver `read_last_exit_pid`), gravado pelo trap de
    EXIT do wrapper — best-effort e só cobre as saídas SEM `exec`
    bem-sucedido (o exec substitui o processo do wrapper pelo jogo; o trap
    de um shell que virou outro programa não existe mais para disparar).
    Serve para encurtar na prática a janela de "pid reuse" do `last_run`
    (ver riscos da síntese): um marker de saída mais novo que o `last_run`
    é evidência de que aquele launch específico NUNCA chegou a rodar o
    jogo — MAS só quando os dois pertencem ao MESMO launch (ver
    `read_last_exit_pid`/`wrapper_game_running`: sem essa correlação por
    pid, o `last_exit` de um launch A que falhou o próprio `exec` invalida
    o `last_run` de um launch B posterior e bem-sucedido, sempre que o trap
    tardio de A grava DEPOIS de B já ter sobrescrito o marker global —
    achado da auditoria da Onda N). Arquivo ausente/ilegível ou sem campo
    válido devolve None. Nunca levanta.
    """
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
    """Decisão PURA: o marker do wrapper ainda atesta um jogo em execução?

    NUMA-01 — evidência #3 do sinal "jogo real ativo": marker `last_run`
    FRESCO (gravado até `window_sec` atrás de `now`) E `pid_alive` E sem
    `exit_marker` mais novo que o próprio marker (senão aquele launch já
    terminou/nunca decolou). Cobre a janela launch→janela (shaders/AAA,
    mesma constante generosa de `wrapper_used_state`), Wayland puro COM
    wrapper (não depende do detector de janela) e sobrevive a restart do
    daemon (o marker é do disco, não de memória). Nunca levanta.

    Correção pós-auditoria da Onda N (`last_run`/`last_exit` GLOBAIS, sem
    pid/sessão amarrando um ao outro): um `exit_marker` mais novo (ou
    igual) que `marker_epoch` só invalida o launch corrente quando
    `marker_pid`/`exit_pid` estão presentes E CASAM — ou seja, quando o
    `last_exit` pertence ao MESMO launch do `last_run` que está sendo
    avaliado. Sequência do achado: launch A grava `last_run` (epoch=E1,
    pid=P1) e o próprio `exec` FALHA; launch B (retry, ou outro jogo)
    grava `last_run` (epoch=E2>E1, pid=P2) com sucesso — P2 vivo rodando o
    jogo de verdade; o trap tardio de A só termina de gravar `last_exit`
    (epoch=E3>=E2) DEPOIS que B já sobrescreveu o marker. Sem a correlação
    por pid, `exit_marker(E3) >= marker_epoch(E2)` derrubava B mesmo com o
    jogo de B genuinamente vivo. Com `exit_pid=P1 != marker_pid=P2`, o
    `exit_marker` é reconhecido como de OUTRO launch e ignorado — o
    critério antigo (só por epoch) permanece como fallback quando qualquer
    um dos dois pids está ausente (markers gravados antes desta correção,
    ou leitura que falhou): fail-safe do lado conservador desta evidência
    específica (`classify` ainda tem os outros 2 ramos). Nunca levanta.
    """
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
    """Decisão PURA do `wrapper_used` para um jogo detectado (GUI-05 item 3).

    ``appid`` = jogo cuja janela `steam_app_N` o detector viu;
    ``first_seen_epoch`` = epoch da PRIMEIRA detecção desse appid;
    ``marker`` = `(appid, epoch)` do `last_run` (ou None).

    True quando o marker é do MESMO appid e foi gravado até ``window_sec``
    ANTES da primeira detecção — o wrapper roda no launch, antes de a janela
    existir. Marker mais NOVO que a primeira detecção também conta (relaunch
    pelo wrapper com a leitura do detector ainda quente). O caso "sem jogo"
    (wm_class não é steam_app) é decidido pelo chamador (devolve None lá).
    """
    if marker is None:
        return False
    marker_appid, marker_epoch = marker
    if marker_appid != appid:
        return False
    return (first_seen_epoch - marker_epoch) <= window_sec


def compose_env(
    *,
    native_mode: bool,
    emulation_enabled: bool,
    flavor: str,
    backends: Sequence[str],
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
    - Xbox: `SDL_JOYSTICK_HIDAPI=0` (SDL lê o evdev, que o daemon graba) +
      IGNORE + DISABLE do físico (o vazamento winebus vale para qualquer
      máscara). O vpad é 045e — nunca colide com o 0ce6.
    - DualSense com TODOS os vpads em uhid (Edge 0df2 com hidraw real):
      DISABLE do físico + IGNORE — dedup no layout PS; o vpad segue com
      hidraw pleno pela whitelist default (NUNCA 0x0DF2 no DISABLE).
    - DualSense com QUALQUER vpad em uinput (degradado), emulação desligada
      ou sem vpad vivo: SÓ o preload de shaders. Duplicado > zero controles.

    O preload (`__GL_SHADER_*`) entra em toda variante: é inócuo e é a parte
    "carregamento completo" que o botão da GUI sempre prometeu.
    """
    env: dict[str, str] = {}
    # Modo Nativo: expõe o físico — sem DISABLE, sem IGNORE (whitelist default).
    if not native_mode and emulation_enabled and backends:
        if flavor == "xbox":
            env["SDL_JOYSTICK_HIDAPI"] = "0"
            env["SDL_GAMECONTROLLER_IGNORE_DEVICES"] = _IGNORE_VALUE
            env["PROTON_DISABLE_HIDRAW"] = _DISABLE_HIDRAW_VALUE
        elif flavor == "dualsense" and all(b == "uhid" for b in backends):
            env["PROTON_DISABLE_HIDRAW"] = _DISABLE_HIDRAW_VALUE
            env["SDL_GAMECONTROLLER_IGNORE_DEVICES"] = _IGNORE_VALUE
        # dualsense degradado (algum uinput) => sem IGNORE, de propósito.
    env["__GL_SHADER_DISK_CACHE"] = "1"
    env["__GL_SHADER_DISK_CACHE_SKIP_CLEANUP"] = "1"
    return env


def _snapshot(daemon: DaemonProtocol) -> tuple[bool, bool, str, list[str]]:
    """(native, emulation_enabled, flavor, backends REAIS de todos os vpads)."""
    native = False
    with contextlib.suppress(Exception):
        native = bool(daemon.is_native_mode())
    cfg = getattr(daemon, "config", None)
    enabled = bool(getattr(cfg, "gamepad_emulation_enabled", False))
    flavor = str(getattr(cfg, "gamepad_flavor", "dualsense") or "dualsense")

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
    return native, enabled, flavor, backends


def _load_profiles(daemon: DaemonProtocol) -> list[Any]:
    """Perfis do disco, best-effort ([] quando indisponível)."""
    try:
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        return list(ProfileManager(controller=daemon.controller).list_profiles())
    except Exception:
        logger.debug("launch_env_perfis_indisponiveis", exc_info=True)
        return []


def _steam_profiles(daemon: DaemonProtocol) -> list[tuple[int, Any]]:
    """(appid, Profile) para cada perfil com `steam_app_<appid>` no match."""
    out: list[tuple[int, Any]] = []
    for profile in _load_profiles(daemon):
        match = getattr(profile, "match", None)
        for wc in getattr(match, "window_class", None) or []:
            m = _STEAM_APP_WC_RE.match(str(wc))
            if m is not None:
                out.append((int(m.group(1)), profile))
    return out


def _nativos_fora_da_antecipacao(profiles: Sequence[Any]) -> list[str]:
    """Nomes dos perfis nativo/desktop que a antecipação por-appid NÃO cobre.

    Achado MED da revisão adversarial da Fase 2: um perfil `kind=native|
    desktop` casado por `window_title_regex`/`process_name` (o próprio sprint
    UX recomenda "perfil para o launcher" por título) — ou por um
    `window_class` que não seja `steam_app_<id>` — não gera arquivo por appid,
    então o jogo lança pelo `default.env`. Se esse default carrega IGNORE, a
    sequência é determinística: a janela ganha foco → o autoswitch ativa o
    perfil nativo → a emulação cai → o vpad some e o físico continua escondido
    pelo IGNORE congelado na env do processo = ZERO controles. Quando existe
    ao menos um perfil assim, o `default.env` OMITE o IGNORE (conservador:
    duplicado > zero controles). Perfil coberto = só `steam_app_*` no
    window_class e nenhum outro critério (o arquivo por-appid antecipa o modo
    dele). `MatchAny` com modo nativo/desktop conta como arriscado.
    """
    out: list[str] = []
    for profile in profiles:
        kind = getattr(getattr(profile, "mode", None), "kind", None)
        if kind not in ("native", "desktop"):
            continue
        match = getattr(profile, "match", None)
        wcs = [str(wc) for wc in getattr(match, "window_class", None) or []]
        coberto = (
            bool(wcs)
            and all(_STEAM_APP_WC_RE.match(wc) is not None for wc in wcs)
            and not getattr(match, "window_title_regex", None)
            and not (getattr(match, "process_name", None) or [])
        )
        if not coberto:
            out.append(str(getattr(profile, "name", "?")))
    return out


def _env_for_profile(
    profile: Any,
    *,
    flavor_atual: str,
    backends: list[str],
) -> tuple[dict[str, str], str] | None:
    """(env, motivo) antecipando o modo que o perfil impõe; None = sem opinião.

    Perfil `mode=None` não materializa arquivo próprio — o wrapper cai no
    `default.env`. `kind=gamepad` com máscara dualsense usa os backends
    REAIS atuais (se a emulação está desligada agora, não dá para garantir
    uhid no futuro => conservador, sem IGNORE).
    """
    mode = getattr(profile, "mode", None)
    if mode is None:
        return None
    kind = getattr(mode, "kind", None)
    if kind == "native":
        return (
            compose_env(
                native_mode=True, emulation_enabled=False,
                flavor=flavor_atual, backends=[],
            ),
            "perfil nativo",
        )
    if kind == "desktop":
        return (
            compose_env(
                native_mode=False, emulation_enabled=False,
                flavor=flavor_atual, backends=[],
            ),
            "perfil desktop",
        )
    if kind == "gamepad":
        flavor = str(getattr(mode, "gamepad_flavor", None) or flavor_atual)
        if flavor == "xbox":
            # O vpad Xbox é uinput 045e POR DESIGN — o IGNORE é seguro
            # independente do estado atual (invariante VPAD-06).
            return (
                compose_env(
                    native_mode=False, emulation_enabled=True,
                    flavor="xbox", backends=["uinput"],
                ),
                "perfil gamepad xbox",
            )
        return (
            compose_env(
                native_mode=False, emulation_enabled=True,
                flavor=flavor, backends=backends,
            ),
            "perfil gamepad dualsense (backends reais)",
        )
    return None


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


def materialize_launch_env(daemon: DaemonProtocol) -> None:
    """Regrava `default.env` + `steam_app_<appid>.env` com o estado REAL.

    Best-effort e barata (arquivos de ~200 B): NUNCA propaga exceção — o
    wrapper degrada sozinho para "nenhuma env" quando o arquivo falta; a
    materialização quebrada não pode derrubar o start da emulação.
    """
    try:
        target = launch_env_dir(ensure=True)
        native, enabled, flavor, backends = _snapshot(daemon)
        estado = (
            f"native={native} emulacao={enabled} mascara={flavor} "
            f"backends={backends or '[]'}"
        )
        # DEDUP-06: o log de "dedup quebrada" mora AQUI, na borda de
        # materialização (transição de estado) — nunca no state_full de 20 Hz.
        # O `dedup_ok` por jogador que a GUI/doctor consomem sai do IPC.
        if (
            not native
            and enabled
            and flavor == "dualsense"
            and backends
            and any(b != "uhid" for b in backends)
        ):
            logger.warning("dedup_broken", motivo="vpad_uinput", backends=backends)
        default_env = compose_env(
            native_mode=native,
            emulation_enabled=enabled,
            flavor=flavor,
            backends=backends,
        )
        if "SDL_GAMECONTROLLER_IGNORE_DEVICES" in default_env:
            arriscados = _nativos_fora_da_antecipacao(_load_profiles(daemon))
            if arriscados:
                # Perfil nativo/desktop fora do alcance da antecipação por
                # appid: o IGNORE congelado no default.env viraria zero
                # controles quando o autoswitch ativasse esse perfil (ver
                # `_nativos_fora_da_antecipacao`). Duplicado > zero.
                del default_env["SDL_GAMECONTROLLER_IGNORE_DEVICES"]
                estado += " ignore_omitido=perfil_nativo_sem_appid"
                logger.info(
                    "launch_env_ignore_omitido_por_perfil_nativo",
                    perfis=arriscados,
                )
        _write_atomic(target / "default.env", _render(default_env, estado))
        desired = {"default.env"}
        for appid, profile in _steam_profiles(daemon):
            per_profile = _env_for_profile(
                profile, flavor_atual=flavor, backends=backends
            )
            if per_profile is None:
                continue
            env, motivo = per_profile
            name = f"steam_app_{appid}.env"
            _write_atomic(target / name, _render(env, f"{motivo} | {estado}"))
            desired.add(name)
        for stale in target.glob("steam_app_*.env"):
            if stale.name not in desired:
                with contextlib.suppress(OSError):
                    stale.unlink()
        logger.info(
            "launch_env_materializado",
            native=native,
            emulacao=enabled,
            mascara=flavor,
            backends=backends,
            arquivos=len(desired),
        )
    except Exception:
        logger.warning("launch_env_materialize_falhou", exc_info=True)


__all__ = [
    "ENV_ALLOWLIST",
    "WRAPPER_MARKER_WINDOW_SEC",
    "compose_env",
    "materialize_launch_env",
    "pid_is_alive",
    "read_last_exit_marker",
    "read_last_exit_pid",
    "read_last_run_marker",
    "read_last_run_pid",
    "steam_appid_from_wm_class",
    "wrapper_game_running",
    "wrapper_used_state",
]
