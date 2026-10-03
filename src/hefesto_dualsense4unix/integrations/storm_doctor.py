"""Diagnóstico do storm -71 do DualSense (FEAT-DSX-UNIFY-01).

Checks READ-ONLY do estado anti-storm, integrados ao hefesto (o launcher
standalone dsx.sh foi removido — teoria de HW refutada; a cura de raiz do storm
é o quirk do snd_usb_audio). NÃO muta nada; NÃO precisa de root. Cada função
recebe os paths por parâmetro (default = sistema real) para testes com fixtures.

Fronteira Aurora: o quirk `054c:0ce6:gn` do cmdline e as regras 99-usb são do
ritual-Aurora — aqui só REPORTAMOS o estado, não mexemos.

A PALAVRA «STORM» TEM QUATRO FAMÍLIAS (O-DIARIO-DO-RADIO-01, 23/09/2026). A
frase acima — «a cura de raiz do storm é o quirk» — vale só para a família 1a
(o -71 do áudio USB no cabo). O rádio tem outras três físicas, e o
:func:`classificar_o_historico` separa as quatro a partir do ``kernel.log`` do
kernel-watch: 1 (porta USB), 2A e 2B (o rádio afogado: o bluetoothd que leva
EAGAIN, a fila do uhid parada), 3 (o controlador travado em laço) e 4 (a
entrada descartada por CRC). É essa separação que dá fonte ao sino da aba
Conexões: cada queda do rádio pode dizer o fato — «4 controles com som
(limite 2)» — com :func:`o_fato_da_queda`, que junta o histórico com o diário
comum (``integrations/diario_do_radio.py``).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import warnings
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.integrations.radio_da_mesa import N_MAX_PONTES
from hefesto_dualsense4unix.utils.repo_files import (
    FRASE_DE_ATUALIZAR,
    esta_instalacao_e_um_checkout,
)

OK = "[ OK ]"
WARN = "[WARN]"
INFO = "[INFO]"

#: deles de porta."*).
PREFIXO_DA_CURA = "O que fazer: "


_ROTULOS_EM_CACHE: dict[str, str] = {}

#: OS RÓTULOS QUE SAÍRAM DA RESERVA — `{id do widget: o rótulo que saiu}`.
_ROTULOS_DE_RESERVA: dict[str, str] = {}


def rotulos_de_reserva() -> dict[str, str]:
    """`{id do widget: rótulo}` de todo rótulo que a FONTE não soube dar."""
    return dict(_ROTULOS_DE_RESERVA)


_NA_TELA_VIVA: dict[str, tuple[str, str]] = {
    "btn_storm_fix_safe": ("09-sistema.html", "refazer-consertos"),
}


def _rotulo_na_tela_viva(widget_id: str) -> str | None:
    """O rótulo daquele botão NA PÁGINA QUE O PRODUTO RENDERIZA, ou `None`."""
    alvo = _NA_TELA_VIVA.get(widget_id)
    if alvo is None:
        return None
    pagina, gesto = alvo
    try:
        import re as _re

        from hefesto_dualsense4unix.interface import onde as _onde

        doc = _onde.pagina(pagina, publicado=True).read_text(encoding="utf-8")
    except Exception:  # pragma: no cover — empacotamento sem a interface nova
        return None
    achado = _re.search(
        rf'data-gesto="{_re.escape(gesto)}"[^>]*>([^<]*)</button>', doc)
    if not achado:
        return None
    import html as _html

    return _html.unescape(achado.group(1)).strip() or None


def rotulo_do_botao(widget_id: str, se_faltar: str) -> str:
    """O rótulo VIVO daquele botão — na TELA QUE ELA USA, pelo id dele."""
    if widget_id in _ROTULOS_EM_CACHE:
        return _ROTULOS_EM_CACHE[widget_id]
    da_tela = _rotulo_na_tela_viva(widget_id)
    if da_tela:
        _ROTULOS_EM_CACHE[widget_id] = da_tela
        return da_tela
    alvo = se_faltar
    lido_da_fonte = False
    try:
        import re as _re
        from pathlib import Path as _Path

        glade = (
            _Path(__file__).resolve().parents[1] / "gui" / "main.glade"
        ).read_text(encoding="utf-8")
        bloco = glade.split(f'id="{widget_id}"', 1)[1]
        bloco = bloco.split(' id="', 1)[0]
        achado = _re.search(
            r'<property name="label" translatable="yes">([^<]+)</property>', bloco
        )
        if achado:
            alvo = achado.group(1)
            lido_da_fonte = True
    except (OSError, IndexError):
        pass
    if not lido_da_fonte:
        _ROTULOS_DE_RESERVA[widget_id] = se_faltar
        warnings.warn(
            f"storm_doctor: o rótulo do botão {widget_id!r} não foi lido de "
            f"lugar nenhum e saiu da RESERVA ({se_faltar!r}). A frase de tela "
            "continua de pé, mas ela manda clicar num nome que ninguém "
            "conferiu — dê um dono ao rótulo (D-0609-GTK-LEVA-INTEIRA).",
            stacklevel=2,
        )
    _ROTULOS_EM_CACHE[widget_id] = alvo
    return alvo


# de escrever em arquivo alheio. Fica RELATADO: enquanto ele não descer,
# sempre sobre ESTE código no disco: quem é o dono dele?

FORMATO_CHECKOUT = "checkout"
FORMATO_FLATPAK = "flatpak"
FORMATO_NIX = "nix"
FORMATO_ARCH = "arch"
FORMATO_DEBIAN = "debian"
FORMATO_FEDORA = "fedora"
FORMATO_DESCONHECIDO = "desconhecido"

GESTO_DE_ATUALIZAR: dict[str, str] = {
    FORMATO_CHECKOUT: FRASE_DE_ATUALIZAR[True],
    FORMATO_FLATPAK: "rode flatpak update",
    FORMATO_ARCH: "rode sudo pacman -Syu",
    FORMATO_FEDORA: "rode sudo dnf upgrade",
    FORMATO_DEBIAN: "rode sudo apt upgrade",
    FORMATO_NIX: "rode nix profile upgrade",
    FORMATO_DESCONHECIDO: FRASE_DE_ATUALIZAR[False],
}

_GERENCIADORES: tuple[tuple[str, str, str], ...] = (
    (FORMATO_ARCH, "pacman", "-Qo"),
    (FORMATO_DEBIAN, "dpkg", "-S"),
    (FORMATO_FEDORA, "rpm", "-qf"),
)


@lru_cache(maxsize=8)
def _dono_do_arquivo(caminho: str) -> str | None:
    """Qual gerenciador de pacotes diz ser dono deste caminho, ou ``None``."""
    for formato, binario, flag in _GERENCIADORES:
        if shutil.which(binario) is None:
            continue
        try:
            proc = subprocess.run(
                [binario, flag, caminho],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode == 0 and proc.stdout.strip():
            return formato
    return None


def formato_desta_instalacao(
    *,
    e_checkout: bool | None = None,
    marca_flatpak: Path | None = None,
    raiz_do_codigo: Path | None = None,
    consultar_dono: Callable[[str], str | None] | None = None,
) -> str:
    """Como este Hefesto foi instalado — em uma palavra."""
    if e_checkout is None:
        e_checkout = esta_instalacao_e_um_checkout()
    if e_checkout:
        return FORMATO_CHECKOUT

    marca = marca_flatpak or Path("/.flatpak-info")
    if marca.is_file() or os.environ.get("FLATPAK_ID"):
        return FORMATO_FLATPAK

    raiz = raiz_do_codigo or Path(__file__).resolve()
    if str(raiz).startswith("/nix/store"):
        return FORMATO_NIX

    dono = (consultar_dono or _dono_do_arquivo)(str(raiz))
    return dono or FORMATO_DESCONHECIDO


def gesto_de_atualizar(
    *,
    e_checkout: bool | None = None,
    marca_flatpak: Path | None = None,
    raiz_do_codigo: Path | None = None,
    consultar_dono: Callable[[str], str | None] | None = None,
) -> str:
    """O gesto de atualizar que serve para ESTA instalação, sem jargão."""
    return GESTO_DE_ATUALIZAR[
        formato_desta_instalacao(
            e_checkout=e_checkout,
            marca_flatpak=marca_flatpak,
            raiz_do_codigo=raiz_do_codigo,
            consultar_dono=consultar_dono,
        )
    ]


PACOTE_POR_FORMATO: dict[str, dict[str, str]] = {
    "opus": {
        FORMATO_DEBIAN: "libopus0",
        FORMATO_FEDORA: "opus",
        FORMATO_ARCH: "opus",
    },
}

NOME_DA_DEPENDENCIA: dict[str, str] = {
    "opus": "a libopus",
}

GESTO_DE_INSTALAR: dict[str, str] = {
    FORMATO_ARCH: "rode sudo pacman -S {pacote}",
    FORMATO_FEDORA: "rode sudo dnf install {pacote}",
    FORMATO_DEBIAN: "rode sudo apt install {pacote}",
}

FRASE_DE_INSTALAR_GENERICA = (
    "instale {biblioteca} pelo gerenciador de pacotes da sua distribuição"
)


def gesto_de_instalar(
    chave: str,
    *,
    e_checkout: bool | None = None,
    marca_flatpak: Path | None = None,
    raiz_do_codigo: Path | None = None,
    consultar_dono: Callable[[str], str | None] | None = None,
) -> str:
    """O gesto de INSTALAR esta biblioteca, com o nome que ela tem AQUI."""
    formato = formato_desta_instalacao(
        e_checkout=e_checkout,
        marca_flatpak=marca_flatpak,
        raiz_do_codigo=raiz_do_codigo,
        consultar_dono=consultar_dono,
    )
    pacote = PACOTE_POR_FORMATO.get(chave, {}).get(formato)
    molde = GESTO_DE_INSTALAR.get(formato)
    if pacote and molde:
        return molde.format(pacote=pacote)
    return FRASE_DE_INSTALAR_GENERICA.format(biblioteca=NOME_DA_DEPENDENCIA[chave])


_QUIRK_RE = re.compile(r"054c:0ce6")
# DualSense COM ignore_ctl_error (o que ataca o mixer que martela o EP0).
_SND_QUIRK_RE = re.compile(r"054c:0ce6:.*ignore_ctl_error")
_CARD_HEADER_RE = re.compile(r"^\s*\d+\s*\[")
_STEAM_INPUT_RE = re.compile(
    r'"(SteamController_PSSupport|UseSteamControllerConfig)"\s+"[12]"'
)

# STEAM-INPUT-ALLOWLIST-01 (22/07): alguns jogos entregam o suporte a DualSense
# SetDualSenseTriggerEffect, que só funciona com o Steam Input do jogo LIGADO).
def _allowlist_path() -> Path:
    """Caminho da allowlist, resolvido A CADA CHAMADA."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        steam_input_allowlist_path,
    )

    return steam_input_allowlist_path()
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
            global_ligado = True
    return appids, global_ligado


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
    return WARN, (
        "o cinto extra do áudio USB não está posto (sob carga o travamento "
        f"pode voltar). {PREFIXO_DA_CURA}nada, enquanto a linha da cura do "
        "travamento do USB, logo acima, estiver verde — é ela que resolve na "
        "raiz."
    )


def find_localconfig_vdfs(home: Path) -> list[Path]:
    """localconfig.vdf per-user em layouts comuns de Steam no Linux (dedup)."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        RAIZES_STEAM_RELATIVAS,
    )

    globs = [f"{raiz}/userdata/*/config/localconfig.vdf" for raiz in RAIZES_STEAM_RELATIVAS]
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
        return INFO, (
            "Steam Input: não encontrei a Steam nesta máquina (nenhum "
            f"localconfig.vdf). {PREFIXO_DA_CURA}nada, se você não usa a "
            "Steam. Se usa, abra a Steam e faça login uma vez — depois volte "
            "a esta aba."
        )
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
        # handler `on_storm_fix_safe` em `app/actions/daemon_actions.py`).
        partes: list[str] = []
        if appids:
            jogos = lista_de_jogos(appids, home)
            sujeito = "esse jogo não está" if len(appids) == 1 else "esses jogos não estão"
            partes.append(
                f"Steam Input ligado para {jogos} — o Hefesto vai desligá-lo no "
                f"próximo ciclo do guarda, porque {sujeito} na sua lista de "
                f"exceções. {PREFIXO_DA_CURA}para manter a sua escolha, abra o "
                "jogo e clique 'Este jogo não funciona' na aba Sistema."
            )
        if global_ligado:
            partes.append(
                "Steam Input LIGADO no ajuste GLOBAL da Steam (vale para todo "
                f"jogo, não é escolha por jogo). {PREFIXO_DA_CURA}clique "
                f"'{rotulo_do_botao('btn_storm_fix_safe', 'Refazer os consertos automáticos')}' "
                "na aba Sistema para desligar."
            )
        return WARN, " ".join(partes)
    excecoes = [
        v for v in vdfs if _STEAM_INPUT_RE.search(_safe_read(v))
    ]
    if excecoes:
        # TELA, e dizia *"jogos cujo DualSense é entregue pela Steam"* — o
        return OK, (
            "Steam Input desligado (com exceções por jogo, marcadas por "
            "você — nesses o controle físico fica escondido)"
        )
    return OK, "Steam Input desligado para o DualSense"


def check_wireplumber(dropin_dir: Path | None = None) -> tuple[str, str]:
    """Drop-in do WirePlumber (DualSense não-default / só-HID) instalado?"""
    if dropin_dir is None:
        from hefesto_dualsense4unix.utils.xdg_paths import wireplumber_config_dir

        dropin_dir = wireplumber_config_dir()
    names = [
        "51-hefesto-dualsense-no-default-source.conf",
        "52-hefesto-dualsense-disable-source.conf",
    ]
    present = [n for n in names if (dropin_dir / n).is_file()]
    if present:
        return OK, f"WirePlumber configurado ({', '.join(present)})"
    # ("Aplicar correções" → `on_storm_fix_safe`, que chama o
    # `scripts/fix_wireplumber_default_source.sh --install`).
    return INFO, (
        "o ajuste de áudio do Hefesto não está instalado — sem ele o controle "
        "pode virar o microfone padrão do sistema sozinho. "
        f"{PREFIXO_DA_CURA}{gesto_de_atualizar()}."
    )


def check_authorized_rule(rules_dir: Path | None = None) -> tuple[str, str]:
    """Regra udev authorized=0 (rota áudio-off agressiva) instalada?"""
    rules_dir = rules_dir or Path("/etc/udev/rules.d")
    rule = rules_dir / "75-ps5-controller-disable-usb-audio.rules"
    if rule.is_file():
        return INFO, (
            "o mic e o fone do controle estão DESLIGADOS de propósito (regra "
            f"áudio-off ATIVA). {PREFIXO_DA_CURA}nada, se foi você que pediu. "
            "Para ter mic e fone de volta, reinstale o Hefesto sem a opção de "
            "desligar o áudio do controle."
        )
    return INFO, (
        "regra áudio-off inativa — o mic e o fone do controle estão "
        f"liberados. {PREFIXO_DA_CURA}nada."
    )


def check_snd_quirk(
    quirk_flags_text: str | None = None, conf_path: Path | None = None
) -> tuple[str, str]:
    """A CURA DE RAIZ do storm (snd_usb_audio quirk_flags) está ativa?"""
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
        return INFO, (
            "a cura do travamento está agendada. "
            f"{PREFIXO_DA_CURA}desconecte e reconecte os controles para ela "
            "valer agora."
        )
    # isso seria uma mentira NOVA. O "Aplicar correções" (`on_storm_fix_safe`,
    # `scripts/fix_wireplumber_default_source.sh` — e deixa o quirk de fora DE
    return (
        WARN,
        f"cura do travamento do USB AUSENTE — sem ela os controles podem "
        f"desconectar no meio do jogo. {PREFIXO_DA_CURA}{gesto_de_atualizar()} "
        f"e reconecte os controles (o botão "
        f"'{rotulo_do_botao('btn_storm_fix_safe', 'Refazer os consertos automáticos')}' "
        "não instala esta cura).",
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
    USB e dois BT): o `/proc/asound/cards` trazia DUAS placas DualSense. A
    PLACA de áudio USB do controle só existe no cabo — por rádio o aparelho não
    anuncia A2DP/HFP/HSP e não há placa ALSA nenhuma a contar. Cobrar quatro
    placas de uma mesa com dois no rádio seria alarme falso permanente.

    "SEM PLACA" NÃO É "SEM MICROFONE", e a diferença é a cura de 03/09/2026: o
    microfone por rádio chega por FORA do ALSA, tunelado em Opus dentro do
    relatório HID (`integrations/dualsense_bt_audio.py`, BT-MIC-01, medido ao
    vivo em 25/07/2026). O denominador continua CERTO — ele conta placas, e
    ponte não é placa —, mas o conselho que saía daqui mandava a pessoa pegar
    o cabo para ter um microfone que o rádio já lhe dava.

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
    """"no único controle no cabo" ou "nos N controles no cabo"."""
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
        return INFO, (
            "áudio do controle ausente (controle desconectado? — ou "
            f"áudio-off). {PREFIXO_DA_CURA}conecte o controle pelo cabo — no "
            "rádio não há placa de som; o microfone ainda chega pela ponte do "
            "Hefesto, o fone é que não."
        )
    if esperados == 0:
        if placas:
            return (
                OK,
                f"áudio presente em {_frase_das_placas(placas)} (nenhum no cabo)",
            )
        return (
            INFO,
            "nenhum controle no cabo — o áudio USB não se aplica (no rádio o "
            f"controle não publica placa de som). {PREFIXO_DA_CURA}"
            "nada; no rádio o microfone chega pela ponte do Hefesto — só o "
            "fone é que pede o cabo.",
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
            f"(áudio-off ligado? — ou a placa ainda subindo). {PREFIXO_DA_CURA}"
            "espere alguns segundos e olhe de novo; se não voltar, desconecte "
            "e reconecte o cabo.",
        )
    faltam = "o outro está" if esperados - placas == 1 else "os demais estão"
    return (
        WARN,
        f"áudio presente em {placas} de {esperados} controles no cabo — "
        f"{faltam} sem mic nem fone. {PREFIXO_DA_CURA}desconecte e reconecte "
        "no cabo quem ficou de fora.",
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

    **A LINHA DA RESERVA — 06/09/2026, GTK-2.** Se algum dos checks acima citou
    um botão cujo nome saiu da RESERVA (:func:`rotulos_de_reserva`), o laudo
    diz isso em vez de calar: as linhas acima estão mandando clicar num nome que
    o produto não conseguiu conferir. Ela é CONDICIONAL e hoje nunca aparece —
    e é assim que se pretende. Ela nasce no dia em que o XML da janela sair
    sem que ninguém tenha dado dono ao rótulo, e some no dia em que o dono
    aparecer.
    """
    home = home or Path.home()
    achados = [
        check_snd_quirk(snd_quirk_text, snd_conf_path),
        check_snd_audio_healthy(cards_text, controles_no_cabo=controles_no_cabo),
        check_quirk(quirks_text),
        check_steam_input(home),
        check_wireplumber(dropin_dir),
        check_authorized_rule(rules_dir),
    ]
    reserva = rotulos_de_reserva()
    if reserva:
        nomes = ", ".join(f"'{r}'" for r in sorted(set(reserva.values())))
        achados.append((
            INFO,
            f"o nome de botão que este exame cita ({nomes}) não pôde ser "
            "conferido no produto — o exame continua valendo, o NOME é que "
            f"pode estar velho. {PREFIXO_DA_CURA}nada agora; quem cuida do "
            "produto tem de dar um dono a esse rótulo.",
        ))
    return achados


FAMILIAS_DO_RADIO: dict[str, tuple[str, str]] = {
    "[USB-71]": ("1", "porta USB"),
    "[BT-SOCKET]": ("2A", "rádio afogado"),
    "[FILA-CHEIA]": ("2B", "fila parada"),
    "[ENLACE-PARADO]": ("2", "enlace parado"),
    "[BT-TRAVADO]": ("3", "adaptador travado"),
    "[CRC]": ("4", "entrada corrompida"),
}

FAMILIA_DA_QUEDA = "2A"

LIMITE_DE_PONTES_POR_ADAPTADOR = N_MAX_PONTES

_TAGS_GENERICAS = frozenset({"[BT-HCI]", "[KERNEL]"})
_RECLASSIFICAR: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"output queue is full", re.I), "[FILA-CHEIA]"),
    (re.compile(r"bt socket write error", re.I), "[BT-SOCKET]"),
    (re.compile(r"link tx timeout|killing stalled connection", re.I), "[ENLACE-PARADO]"),
    (
        re.compile(
            r"command 0x[0-9a-f]{4} tx timeout|read reg16 failed|"
            r"failed to generate devcoredump",
            re.I,
        ),
        "[BT-TRAVADO]",
    ),
    (re.compile(r"crc.s check failed", re.I), "[CRC]"),
)

JANELA_DA_RAJADA_S = 10.0

_LINHA_DO_VIGIA = re.compile(
    r"^(?P<ts>\S+) (?P<tag>\[[A-Z0-9-]+\]) "
    r"(?:(?P<resumo>repetiu|segue) \+(?P<n>\d+) \([^)]*\): )?(?P<texto>.*)$"
)


@dataclass(frozen=True)
class EventoDoRadio:
    """Uma linha do kernel-watch que é de uma das quatro famílias."""

    quando: str
    carimbo: float
    tag: str
    familia: str
    ocorrencias: int
    borda: bool
    texto: str


@dataclass
class ContagemDaFamilia:
    """Quantas vezes uma família apareceu, e quando."""

    familia: str
    nome: str
    rajadas: int = 0
    ocorrencias: int = 0
    primeira: str = ""
    ultima: str = ""
    medida_desde: str = ""


_BANNER_DO_VIGIA = re.compile(
    r"^# (?P<data>\d{4}-\d{2}-\d{2}) (?P<hora>\d{2}:\d{2}:\d{2}) "
    r"kernel-watch iniciado \(padrões: (?P<lista>[^+)]*)"
)

_VISTA_PELA_TAG_GENERICA = {"2": "BT-HCI", "3": "BT-HCI"}


def _desde_quando_se_mede(linhas: Iterable[str]) -> dict[str, str]:
    """``{família: primeiro banner do kernel-watch que a procurava}``."""
    desde: dict[str, str] = {}
    for linha in linhas:
        casou = _BANNER_DO_VIGIA.match(linha)
        if casou is None:
            continue
        procuradas = set(casou["lista"].split())
        quando = f"{casou['data']}T{casou['hora']}"
        for tag, (familia, _nome) in FAMILIAS_DO_RADIO.items():
            if tag.strip("[]") in procuradas or (
                _VISTA_PELA_TAG_GENERICA.get(familia) in procuradas
            ):
                desde.setdefault(familia, quando)
    return desde


def _carimbo(ts: str) -> float | None:
    try:
        return datetime.fromisoformat(ts).timestamp()
    except ValueError:
        return None


def ler_eventos_do_radio(linhas: Iterable[str]) -> list[EventoDoRadio]:
    """As linhas das quatro famílias, na ordem em que vieram."""
    eventos: list[EventoDoRadio] = []
    for linha in linhas:
        casou = _LINHA_DO_VIGIA.match(linha.rstrip("\n"))
        if casou is None:
            continue
        tag = casou["tag"]
        if tag in _TAGS_GENERICAS:
            tag = next(
                (nova for padrao, nova in _RECLASSIFICAR if padrao.search(casou["texto"])),
                tag,
            )
        familia = FAMILIAS_DO_RADIO.get(tag)
        if familia is None:
            continue
        carimbo = _carimbo(casou["ts"])
        if carimbo is None:
            continue
        resumo = casou["resumo"]
        eventos.append(
            EventoDoRadio(
                quando=casou["ts"],
                carimbo=carimbo,
                tag=tag,
                familia=familia[0],
                ocorrencias=int(casou["n"]) if resumo else 1,
                borda=resumo is None,
                texto=casou["texto"],
            )
        )
    return eventos


def classificar_o_historico(linhas: Iterable[str]) -> dict[str, ContagemDaFamilia]:
    """``{família: contagem}`` de tudo o que o kernel-watch viu."""
    linhas = list(linhas)
    medida_desde = _desde_quando_se_mede(linhas)
    contagens: dict[str, ContagemDaFamilia] = {}
    ultima_vista: dict[str, float] = {}
    for evento in ler_eventos_do_radio(linhas):
        nome = FAMILIAS_DO_RADIO[evento.tag][1]
        conta = contagens.setdefault(
            evento.familia, ContagemDaFamilia(familia=evento.familia, nome=nome)
        )
        conta.ocorrencias += evento.ocorrencias
        anterior = ultima_vista.get(evento.familia)
        if evento.borda and (
            anterior is None or abs(evento.carimbo - anterior) > JANELA_DA_RAJADA_S
        ):
            conta.rajadas += 1
        ultima_vista[evento.familia] = evento.carimbo
        if not conta.primeira:
            conta.primeira = evento.quando
        conta.ultima = evento.quando
    nomes = dict(FAMILIAS_DO_RADIO.values())
    for familia in medida_desde:
        contagens.setdefault(familia, ContagemDaFamilia(familia=familia, nome=nomes[familia]))
    for conta in contagens.values():
        candidatos = [c for c in (medida_desde.get(conta.familia), conta.primeira[:19]) if c]
        conta.medida_desde = min(candidatos) if candidatos else ""
    return contagens


def caminho_do_kernel_log() -> Path:
    """O ``kernel.log`` do kernel-watch desta conta."""
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return state_dir() / "kernel.log"


def historico_do_radio(caminho: Path | None = None) -> dict[str, ContagemDaFamilia]:
    """:func:`classificar_o_historico` sobre o ``kernel.log``. Nunca levanta."""
    texto = _safe_read(caminho or caminho_do_kernel_log())
    return classificar_o_historico(texto.splitlines())


def quedas(eventos: Iterable[EventoDoRadio]) -> list[EventoDoRadio]:
    """As bordas da família que derruba os controles (:data:`FAMILIA_DA_QUEDA`)."""
    return [e for e in eventos if e.familia == FAMILIA_DA_QUEDA and e.borda]


def o_fato_da_queda(
    queda: EventoDoRadio,
    entradas_do_diario: Iterable[dict[str, Any]],
    *,
    limite: int = LIMITE_DE_PONTES_POR_ADAPTADOR,
) -> str | None:
    """O fato de uma queda, dito do jeito que a tela diz. ``None`` = não sei."""
    from hefesto_dualsense4unix.integrations.diario_do_radio import pontes_de_pe

    por_adaptador = pontes_de_pe(list(entradas_do_diario), queda.carimbo)
    if not por_adaptador:
        return None
    pontes = max(por_adaptador.values(), key=len)
    controles = {controle for controle, _tipo in pontes}
    tipos = {tipo for _controle, tipo in pontes}
    if not controles:
        return None
    if tipos == {"som"}:
        o_que = "com som"
    elif tipos == {"vibracao"}:
        o_que = "com vibração"
    else:
        o_que = "com som ou vibração"
    quantos = len(controles)
    palavra = "controle" if quantos == 1 else "controles"
    return f"{quantos} {palavra} {o_que} (limite {limite})"


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


__all__ = [
    "FAMILIAS_DO_RADIO",
    "FAMILIA_DA_QUEDA",
    "FRASE_DE_INSTALAR_GENERICA",
    "GESTO_DE_ATUALIZAR",
    "GESTO_DE_INSTALAR",
    "JANELA_DA_RAJADA_S",
    "LIMITE_DE_PONTES_POR_ADAPTADOR",
    "NOME_DA_DEPENDENCIA",
    "PACOTE_POR_FORMATO",
    "PREFIXO_DA_CURA",
    "ContagemDaFamilia",
    "EventoDoRadio",
    "caminho_do_kernel_log",
    "check_authorized_rule",
    "check_quirk",
    "check_snd_audio_healthy",
    "check_snd_quirk",
    "check_steam_input",
    "check_wireplumber",
    "classificar_o_historico",
    "contar_placas_dualsense",
    "controles_no_cabo",
    "find_localconfig_vdfs",
    "formato_desta_instalacao",
    "gesto_de_atualizar",
    "gesto_de_instalar",
    "historico_do_radio",
    "ler_eventos_do_radio",
    "o_fato_da_queda",
    "quedas",
    "rotulo_do_botao",
    "rotulos_de_reserva",
    "steam_input_allowlist",
    "steam_input_fora_da_allowlist",
    "storm_report",
]
