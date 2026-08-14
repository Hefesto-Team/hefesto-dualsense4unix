"""Diagnóstico do storm -71 do DualSense (FEAT-DSX-UNIFY-01).

Checks READ-ONLY do estado anti-storm, integrados ao hefesto (o launcher
standalone dsx.sh foi removido — teoria de HW refutada; a cura de raiz do storm
é o quirk do snd_usb_audio). NÃO muta nada; NÃO precisa de root. Cada função
recebe os paths por parâmetro (default = sistema real) para testes com fixtures.

Fronteira Aurora: o quirk `054c:0ce6:gn` do cmdline e as regras 99-usb são do
ritual-Aurora — aqui só REPORTAMOS o estado, não mexemos.
"""
from __future__ import annotations

import re
from pathlib import Path

# Tags no padrão do doctor.
OK = "[ OK ]"
WARN = "[WARN]"
INFO = "[INFO]"

_QUIRK_RE = re.compile(r"054c:0ce6")
# SPRINT-GAME-RUMBLE-01: a cura de raiz é o quirk_flags do snd_usb_audio para o
# DualSense COM ignore_ctl_error (o que ataca o mixer que martela o EP0).
_SND_QUIRK_RE = re.compile(r"054c:0ce6:.*ignore_ctl_error")
# MESA-CHEIA-11/E3: linha de CABEÇALHO de placa no /proc/asound/cards
# (" 1 [Controller     ]: USB-Audio - ..."). A segunda linha de cada placa é a
# descrição, e repete o nome — contar a palavra daria o dobro.
_CARD_HEADER_RE = re.compile(r"^\s*\d+\s*\[")
_STEAM_INPUT_RE = re.compile(
    r'"(SteamController_PSSupport|UseSteamControllerConfig)"\s+"[12]"'
)

# STEAM-INPUT-ALLOWLIST-01 (22/07): alguns jogos entregam o suporte a DualSense
# PELA Steam (API Steamworks — caso medido: Mullet Mad Jack chama
# SetDualSenseTriggerEffect, que só funciona com o Steam Input do jogo LIGADO).
# O opt-in per-app desses títulos é deliberado — os checks não devem acusá-lo
# de conflito. Mesma allowlist do disable_steam_input.sh.
def _allowlist_path() -> Path:
    """Caminho da allowlist, resolvido A CADA CHAMADA.

    CANARIO-FS-01 (05/08/2026, decisão dela): isto ERA uma constante de módulo
    — ``Path.home() / ...`` avaliada no IMPORT. Em produção funcionava; em
    teste, não: o valor congelava antes de qualquer ``monkeypatch`` de ``HOME``,
    e a suíte passava a LER o arquivo real da mantenedora. O resultado de três
    arquivos de teste dependia, sem ninguém saber, do conteúdo do disco dela.

    ``Path.home()`` lê ``HOME`` no momento da chamada. Dentro de uma função,
    portanto, o isolamento da suíte volta a valer — e o comportamento em
    produção não muda em nada, porque lá o ``HOME`` é o mesmo do começo ao fim.

    O irmão desta cura é ``EmulationActionsMixin._wp_dropin_dir``, que tinha a
    mesma forma e é DIRETÓRIO DE ESCRITA.
    """
    return Path.home() / ".config" / "hefesto-dualsense4unix" / "steam_input_apps.txt"
_SI_KEY_RE = re.compile(
    r'"(SteamController_PSSupport|SteamController_SwitchSupport|'
    r'UseSteamControllerConfig)"\s+"[12]"'
)
_VDF_BLOCK_NAME_RE = re.compile(r'^\s*"([^"]*)"\s*$')


def steam_input_allowlist(path: Path | None = None) -> set[str]:
    """AppIDs com Steam Input per-app deliberado (uma linha por id; # comenta)."""
    caminho = path or _allowlist_path()
    out: set[str] = set()
    try:
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            token = linha.split("#", 1)[0].strip()
            if token:
                out.add(token)
    except OSError:
        pass
    return out


def steam_input_fora_da_allowlist(text: str, allow: set[str]) -> tuple[list[str], bool]:
    """`(appids per-app ligados fora da allowlist, chave GLOBAL ligada?)`.

    Anda a pilha de blocos do VDF (linha `"nome"` seguida de `{` abre bloco):
    `UseSteamControllerConfig` dentro de `apps/<appid>` da allowlist é opt-in
    deliberado e não conta; qualquer outro `UseSteamControllerConfig` é um
    JOGO, e o appid dele volta na lista. As chaves GLOBAIS
    (PSSupport/SwitchSupport) não pertencem a jogo nenhum — elas voltam no
    segundo termo, e por isso a mensagem pode falar delas sem inventar jogo.

    D-33 (05/08/2026): quem chamava sabia só que "havia algo ligado"; a
    mensagem então contava ARQUIVOS `vdf`. Aqui nasce o dado que faltava para
    a tela poder dizer o NOME do jogo.
    """
    appids: list[str] = []
    global_ligado = False
    stack: list[str] = []
    pending = ""
    for line in text.splitlines():
        m = _VDF_BLOCK_NAME_RE.match(line)
        if m:
            pending = m.group(1)
            continue
        s = line.strip()
        if s == "{":
            stack.append(pending)
            pending = ""
            continue
        if s == "}":
            if stack:
                stack.pop()
            continue
        km = _SI_KEY_RE.search(line)
        if km is None:
            continue
        if km.group(1) != "UseSteamControllerConfig":
            global_ligado = True
            continue
        appid = stack[-1] if stack else ""
        if appid in allow:
            continue
        if appid and appid not in appids:
            appids.append(appid)
        elif not appid:
            # `UseSteamControllerConfig` fora de qualquer bloco `apps/<id>`:
            # não dá para atribuir a jogo nenhum — entra como global em vez de
            # virar um jogo de appid vazio.
            global_ligado = True
    return appids, global_ligado


def steam_input_on_fora_da_allowlist(text: str, allow: set[str]) -> bool:
    """True se alguma chave de Steam Input em "1"/"2" está FORA da allowlist."""
    appids, global_ligado = steam_input_fora_da_allowlist(text, allow)
    return bool(appids) or global_ligado


def check_quirk(quirks_text: str | None = None) -> tuple[str, str]:
    """O quirk anti-storm (DELAY_CTRL_MSG) está ativo? (preserva o áudio do controle)."""
    if quirks_text is None:
        try:
            quirks_text = Path(
                "/sys/module/usbcore/parameters/quirks"
            ).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            quirks_text = ""
    if _QUIRK_RE.search(quirks_text or ""):
        return OK, "quirk anti-storm ativo (054c:0ce6 — áudio USB espaçado)"
    return WARN, "quirk anti-storm AUSENTE do usbcore (storm pode reincidir sob carga)"


def find_localconfig_vdfs(home: Path) -> list[Path]:
    """localconfig.vdf per-user em layouts comuns de Steam no Linux (dedup)."""
    globs = [
        ".steam/steam/userdata/*/config/localconfig.vdf",
        ".local/share/Steam/userdata/*/config/localconfig.vdf",
        ".var/app/com.valvesoftware.Steam/.steam/steam/userdata/*/config/localconfig.vdf",
        "snap/steam/common/.steam/steam/userdata/*/config/localconfig.vdf",
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for pattern in globs:
        for path in home.glob(pattern):
            real = path.resolve()
            if real.is_file() and real not in seen:
                seen.add(real)
                out.append(real)
    return out


def check_steam_input(home: Path | None = None) -> tuple[str, str]:
    """Steam Input (PSSupport/UseSteamControllerConfig) ON para o DualSense?

    ON é RUIM neste contexto (incompatível no Linux p/ Grim; e o storm/duplo-input).
    """
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        lista_de_jogos,
    )

    home = home or Path.home()
    vdfs = find_localconfig_vdfs(home)
    if not vdfs:
        return INFO, "Steam Input: nenhum localconfig.vdf encontrado (Steam instalada?)"
    # STEAM-INPUT-ALLOWLIST-01: opt-in per-app deliberado (ex.: MMJ) não é
    # conflito — só acusa o que a transformação do guard corrigiria.
    allow = steam_input_allowlist()
    appids: list[str] = []
    global_ligado = False
    for v in vdfs:
        ids, glob_on = steam_input_fora_da_allowlist(_safe_read(v), allow)
        for appid in ids:
            if appid not in appids:
                appids.append(appid)
        global_ligado = global_ligado or glob_on
    if appids or global_ligado:
        # STEAM-INPUT-01 (entrega 9): o rótulo citado aqui era 'Reaplicar fixes
        # seguros', que não é o nome de widget nenhum. O botão que de fato roda
        # o `disable_steam_input.sh --apply-quiet` chama-se "Aplicar correções"
        # e mora na aba Sistema (`gui/main.glade`, id `btn_storm_fix_safe`,
        # handler `on_storm_fix_safe` em `app/actions/daemon_actions.py`).
        #
        # D-33 (05/08/2026): a frase era "Steam Input LIGADO em N perfil(is)
        # fora da allowlist — clique 'Aplicar correções'". Três defeitos num
        # fôlego: o N contava ARQUIVOS `vdf` e não JOGOS; ela não dizia DE QUAL
        # jogo falava; e mandava clicar no botão que APAGA exatamente a escolha
        # que a usuária tomou na janela da Steam. Agora o jogo é nomeado, o que
        # vai acontecer é dito antes de acontecer, e o botão apontado é o que
        # PRESERVA a escolha. O ajuste GLOBAL da Steam continua sendo caso do
        # 'Aplicar correções' — ele não é escolha por jogo, é chave geral.
        partes: list[str] = []
        if appids:
            jogos = lista_de_jogos(appids, home)
            sujeito = "esse jogo não está" if len(appids) == 1 else "esses jogos não estão"
            partes.append(
                f"Steam Input ligado para {jogos} — o Hefesto vai desligá-lo no "
                f"próximo ciclo do guarda, porque {sujeito} na sua lista de "
                "exceções. Para manter a sua escolha, abra o jogo e clique "
                "'Este jogo não funciona' na aba Sistema."
            )
        if global_ligado:
            partes.append(
                "Steam Input LIGADO no ajuste GLOBAL da Steam (vale para todo "
                "jogo, não é escolha por jogo) — clique 'Aplicar correções' na "
                "aba Sistema para desligar."
            )
        return WARN, " ".join(partes)
    excecoes = [
        v for v in vdfs if _STEAM_INPUT_RE.search(_safe_read(v))
    ]
    if excecoes:
        return OK, (
            "Steam Input desligado (exceções per-app da allowlist ativas — "
            "ex.: jogos cujo DualSense é entregue pela Steam)"
        )
    return OK, "Steam Input desligado para o DualSense"


def check_wireplumber(dropin_dir: Path | None = None) -> tuple[str, str]:
    """Drop-in do WirePlumber (DualSense não-default / só-HID) instalado?"""
    dropin_dir = dropin_dir or (
        Path.home() / ".config" / "wireplumber" / "wireplumber.conf.d"
    )
    names = [
        "51-hefesto-dualsense-no-default-source.conf",
        "52-hefesto-dualsense-disable-source.conf",
    ]
    present = [n for n in names if (dropin_dir / n).is_file()]
    if present:
        return OK, f"WirePlumber configurado ({', '.join(present)})"
    return INFO, "WirePlumber sem drop-in do hefesto ('doctor --fix-safe' instala)"


def check_authorized_rule(rules_dir: Path | None = None) -> tuple[str, str]:
    """Regra udev authorized=0 (rota áudio-off agressiva) instalada?

    Opt-in: presença = mic/fone do controle desligados. Só INFO.
    """
    rules_dir = rules_dir or Path("/etc/udev/rules.d")
    rule = rules_dir / "75-ps5-controller-disable-usb-audio.rules"
    if rule.is_file():
        return INFO, "regra áudio-off (authorized=0) ATIVA — mic/fone do controle off"
    return INFO, "regra áudio-off inativa (áudio do controle preservado)"


def check_snd_quirk(
    quirk_flags_text: str | None = None, conf_path: Path | None = None
) -> tuple[str, str]:
    """A CURA DE RAIZ do storm (snd_usb_audio quirk_flags) está ativa?

    SPRINT-GAME-RUMBLE-01: o quirk `054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m`
    torna o probe do mixer UAC tolerante e espaça o EP0 — mata o storm na origem
    PRESERVANDO mic+fone (ao contrário da regra 75). Reporta o sysfs (sessão) e o
    drop-in de /etc/modprobe.d (persistente).
    """
    if quirk_flags_text is None:
        try:
            quirk_flags_text = Path(
                "/sys/module/snd_usb_audio/parameters/quirk_flags"
            ).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            quirk_flags_text = ""
    active = bool(_SND_QUIRK_RE.search(quirk_flags_text or ""))
    conf = conf_path or Path("/etc/modprobe.d/hefesto-dualsense-storm.conf")
    persisted = bool(conf.is_file() and _SND_QUIRK_RE.search(_safe_read(conf)))
    if active:
        return OK, "cura do travamento do USB ATIVA (mic e fone do controle preservados)"
    if persisted:
        # MESA-CHEIA-11/E4: são os QUATRO a reconectar — o quirk pega no replug
        # de cada controle, não no primeiro que voltar.
        return INFO, "cura do travamento agendada (reconecte os controles p/ ativar)"
    # STEAM-INPUT-01 (entrega 9), com reenquadramento: a sprint mandou trocar o
    # rótulo morto ('Reaplicar fixes seguros') pelo nome do botão real, e aqui
    # isso seria uma mentira NOVA. O "Aplicar correções" (`on_storm_fix_safe`,
    # em `app/actions/daemon_actions.py`) roda dois scripts — o
    # `scripts/disable_steam_input.sh` e o
    # `scripts/fix_wireplumber_default_source.sh` — e deixa o quirk de fora DE
    # PROPÓSITO (BUG-C: escrevê-lo a quente era `sudo tee` no /sys, o único
    # sudo em runtime da GUI, e falhava calado num botão que promete "não pede
    # senha"). Quem instala esta cura é o `install.sh` (via
    # `scripts/install_snd_quirk.sh`, em /etc/modprobe.d), e ela pega no
    # próximo replug do controle. É esse o ponteiro honesto.
    return (
        WARN,
        "cura do travamento do USB AUSENTE — rode ./install.sh e reconecte os "
        "controles (o botão 'Aplicar correções' não instala esta cura; sem ela "
        "os controles podem desconectar no meio do jogo)",
    )


def contar_placas_dualsense(cards_text: str | None) -> int:
    """Quantas PLACAS de áudio DualSense o `/proc/asound/cards` traz — função pura.

    MESA-CHEIA-11/E3 (14/08/2026). A régua vem antes do veredito, e esta erra
    fácil: cada placa ocupa DUAS linhas no arquivo, e o nome "DualSense" aparece
    nas duas — contar ocorrências da palavra dá o DOBRO das placas. O que
    identifica uma placa é a linha de cabeçalho, que começa com o índice dela::

         1 [Controller     ]: USB-Audio - DualSense Wireless Controller
                              Sony ... DualSense Wireless Controller at usb-...

    Então só as linhas `^<n> [` contam.
    """
    total = 0
    for linha in (cards_text or "").splitlines():
        if _CARD_HEADER_RE.match(linha) and "dualsense" in linha.lower():
            total += 1
    return total


def controles_no_cabo(state: object) -> int | None:
    """Quantos controles do `state_full` estão no CABO; ``None`` = não dá pra saber.

    MESA-CHEIA-11/E3 — este é o denominador honesto, e ele NÃO é "quantos
    controles há". Medido na mesa dela em 14/08/2026 com quatro controles (dois
    USB e dois BT): o `/proc/asound/cards` trazia DUAS placas DualSense. O
    áudio USB do controle só existe no cabo — no rádio o mic e o fone não
    passam por placa ALSA. Cobrar quatro placas de uma mesa com dois no rádio
    seria alarme falso permanente.

    ``None`` (state ausente, daemon offline, payload sem `controllers`) é
    diferente de ``0``: sem denominador o check volta a responder só
    presente/ausente, em vez de inventar uma fração.
    """
    if not isinstance(state, dict):
        return None
    controles = state.get("controllers")
    if not isinstance(controles, list):
        return None
    total = 0
    for entrada in controles:
        if not isinstance(entrada, dict):
            continue
        if entrada.get("connected") is False:
            continue
        if str(entrada.get("transport", "")).lower() == "usb":
            total += 1
    return total


def _frase_do_cabo(quantos: int) -> str:
    """"no único controle no cabo" ou "nos N controles no cabo".

    MESA-CHEIA-11/E3 (conserto de 14/08/2026): a primeira versão interpolava
    sempre no plural e o caso MAIS COMUM do produto — UM controle no cabo —
    saía como "nos 1 controles no cabo", verbatim na tela (cartão anti-storm) e
    no `doctor`. O ramo vizinho desta mesma função já lembrava do plural; aqui
    ele tinha sido esquecido.
    """
    if quantos == 1:
        return "no único controle no cabo"
    return f"nos {quantos} controles no cabo"


def _frase_das_placas(quantas: int) -> str:
    """"1 placa DualSense" ou "N placas DualSense" — sem o "(s)" de formulário."""
    if quantas == 1:
        return "1 placa DualSense"
    return f"{quantas} placas DualSense"


def check_snd_audio_healthy(
    cards_text: str | None = None, *, controles_no_cabo: int | None = None
) -> tuple[str, str]:
    """O áudio do controle (mic+fone) está presente? Prova que a cura não o quebrou.

    MESA-CHEIA-11/E3: era um `re.search(r"DualSense")` no texto INTEIRO — com a
    mesa cheia, UM controle com áudio respondia "presente" pelos quatro, e o
    check existe justamente para provar que a cura do storm não comeu o áudio
    de alguém. Agora ele CONTA, e o veredito muda quando falta.

    ``controles_no_cabo`` é o denominador (ver a função de mesmo nome). Sem ele
    — daemon offline, chamada antiga — a resposta continua sendo presente/
    ausente, sem fração inventada.
    """
    if cards_text is None:
        cards_text = _safe_read(Path("/proc/asound/cards"))
    placas = contar_placas_dualsense(cards_text)
    esperados = controles_no_cabo
    if esperados is None:
        if placas:
            return OK, "áudio do controle presente (mic+fone do DualSense ativos)"
        return INFO, "áudio do controle ausente (controle desconectado? — ou áudio-off)"
    if esperados == 0:
        if placas:
            return (
                OK,
                f"áudio presente em {_frase_das_placas(placas)} (nenhum no cabo)",
            )
        return (
            INFO,
            "nenhum controle no cabo — o áudio USB não se aplica (no rádio o "
            "mic e o fone não passam por placa de som)",
        )
    if placas >= esperados:
        return (
            OK,
            f"áudio presente {_frase_do_cabo(esperados)} "
            "(mic+fone do DualSense ativos)",
        )
    if placas == 0:
        return (
            INFO,
            f"áudio ausente {_frase_do_cabo(esperados)} "
            "(áudio-off ligado? — ou a placa ainda subindo)",
        )
    # Aqui `esperados >= 2` sempre (0 < placas < esperados), então o denominador
    # é plural de verdade; o que varia é quantos ficaram de fora.
    faltam = "o outro está" if esperados - placas == 1 else "os demais estão"
    return (
        WARN,
        f"áudio presente em {placas} de {esperados} controles no cabo — "
        f"{faltam} sem mic nem fone",
    )


def storm_report(
    home: Path | None = None,
    *,
    quirks_text: str | None = None,
    dropin_dir: Path | None = None,
    rules_dir: Path | None = None,
    snd_quirk_text: str | None = None,
    snd_conf_path: Path | None = None,
    cards_text: str | None = None,
    controles_no_cabo: int | None = None,
) -> list[tuple[str, str]]:
    """Bloco de diagnóstico storm para o `doctor` (read-only).

    ``controles_no_cabo`` (MESA-CHEIA-11/E3) é o denominador do check de áudio;
    quem tem o `state_full` à mão o calcula com a função de mesmo nome. ``None``
    = sem daemon, e aí o check volta a responder só presente/ausente.
    """
    home = home or Path.home()
    return [
        check_snd_quirk(snd_quirk_text, snd_conf_path),
        check_snd_audio_healthy(cards_text, controles_no_cabo=controles_no_cabo),
        check_quirk(quirks_text),
        check_steam_input(home),
        check_wireplumber(dropin_dir),
        check_authorized_rule(rules_dir),
    ]


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


__all__ = [
    "check_authorized_rule",
    "check_quirk",
    "check_snd_audio_healthy",
    "check_snd_quirk",
    "check_steam_input",
    "check_wireplumber",
    "contar_placas_dualsense",
    "controles_no_cabo",
    "find_localconfig_vdfs",
    "steam_input_allowlist",
    "steam_input_fora_da_allowlist",
    "steam_input_on_fora_da_allowlist",
    "storm_report",
]
