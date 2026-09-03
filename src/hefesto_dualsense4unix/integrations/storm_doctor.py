"""Diagnóstico do storm -71 do DualSense (FEAT-DSX-UNIFY-01).

Checks READ-ONLY do estado anti-storm, integrados ao hefesto (o launcher
standalone dsx.sh foi removido — teoria de HW refutada; a cura de raiz do storm
é o quirk do snd_usb_audio). NÃO muta nada; NÃO precisa de root. Cada função
recebe os paths por parâmetro (default = sistema real) para testes com fixtures.

Fronteira Aurora: o quirk `054c:0ce6:gn` do cmdline e as regras 99-usb são do
ritual-Aurora — aqui só REPORTAMOS o estado, não mexemos.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from hefesto_dualsense4unix.utils.repo_files import (
    FRASE_DE_ATUALIZAR,
    esta_instalacao_e_um_checkout,
)

# Tags no padrão do doctor.
OK = "[ OK ]"
WARN = "[WARN]"
INFO = "[INFO]"

#: O prefixo do gesto, palavra por palavra do molde já aprovado na aba
#: Configurações (`app/actions/config/secao_exame.PREFIXO_DA_CURA`, e a foto
#: `docs/usage/assets/readme_configuracoes.png`: *"O que fazer: Vale mudar um
#: deles de porta."*).
#:
#: **DUPLICAÇÃO DECLARADA, não descuido.** O dono do prefixo é o `secao_exame`,
#: que vive em `app/` — e `integrations/` não pode importar de `app/` sem
#: inverter a camada (é a mesma razão que mudou o conselho de atualizar de casa,
#: em `utils/repo_files.py:35-41`). A saída certa é o prefixo descer para
#: `utils/`, e isso está RELATADO na entrega desta frente.
PREFIXO_DA_CURA = "O que fazer: "


#: Os rótulos dos botões que as frases desta casa mandam clicar. LIDOS do
#: `main.glade`, nunca digitados — corrigido em 26/08/2026, e o defeito era
#: vivo: a leva daquele dia renomeou "Aplicar correções" para "Consertar
#: problemas conhecidos" (o rótulo velho não dizia o que o botão faz), e esta
#: frase continuou mandando a pessoa procurar um botão QUE NÃO EXISTE MAIS na
#: janela. Quem pegou foi `tests/unit/test_steam_input_ponteiros.py`, que
#: compara a frase com os rótulos vivos — e é por isso que ele existe.
_ROTULOS_EM_CACHE: dict[str, str] = {}


def rotulo_do_botao(widget_id: str, se_faltar: str) -> str:
    """O rótulo VIVO de um botão do `main.glade`, pelo id dele.

    `se_faltar` é o que sai quando o glade não está ao alcance (empacotamento
    parcial, teste sem recurso). Uma frase que some é pior que uma frase com um
    nome velho, então isto nunca levanta.
    """
    if widget_id in _ROTULOS_EM_CACHE:
        return _ROTULOS_EM_CACHE[widget_id]
    alvo = se_faltar
    try:
        import re as _re
        from pathlib import Path as _Path

        glade = (
            _Path(__file__).resolve().parents[1] / "gui" / "main.glade"
        ).read_text(encoding="utf-8")
        # A janela termina no PRÓXIMO `id=`, e não num número de caracteres:
        # o rótulo pode ser propriedade direta do botão OU, quando ele precisa
        # quebrar linha, um `<child><object class="GtkLabel">` alguns comentários
        # abaixo. Um teto fixo de caracteres achava o primeiro caso e perdia o
        # segundo — medido em 26/08, com o `btn_storm_fix_safe`, que é
        # exatamente o botão que virou filho naquele dia.
        bloco = glade.split(f'id="{widget_id}"', 1)[1]
        bloco = bloco.split(' id="', 1)[0]
        achado = _re.search(
            r'<property name="label" translatable="yes">([^<]+)</property>', bloco
        )
        if achado:
            alvo = achado.group(1)
    except (OSError, IndexError):
        pass
    _ROTULOS_EM_CACHE[widget_id] = alvo
    return alvo


# ---------------------------------------------------------------------------
# O GESTO DE ATUALIZAR, POR FORMATO DE INSTALAÇÃO (BG-06b)
#
# ESTE BLOCO MORA AQUI POR POSSE, NÃO POR DESENHO. A casa dele é
# `utils/repo_files.py`, ao lado de `FRASE_DE_ATUALIZAR` e de
# `esta_instalacao_e_um_checkout` — é a MESMA pergunta ("o que esta instalação
# tem ao lado do código?"), um grau mais fina. `repo_files.py` está fora da
# posse desta frente (LEVA-2-G, 26/08/2026), e a regra da leva é relatar em vez
# de escrever em arquivo alheio. Fica RELATADO: enquanto ele não descer,
# `app/actions/mouse_actions.py` e `app/actions/emulation_actions.py` — que
# chamam `repo_files.como_atualizar_esta_instalacao()` direto — continuam
# entregando a frase genérica, que é o último degrau desta escada e não uma
# contradição.
#
# O QUE ELE NÃO FAZ: adivinhar o formato pela distribuição. "Tem `apt`, logo é
# `.deb`" está errado para todo AppImage e todo `pip install --user` numa
# máquina Debian — e um gesto errado é pior que um gesto vago. A pergunta é
# sempre sobre ESTE código no disco: quem é o dono dele?
# ---------------------------------------------------------------------------

FORMATO_CHECKOUT = "checkout"
FORMATO_FLATPAK = "flatpak"
FORMATO_NIX = "nix"
FORMATO_ARCH = "arch"
FORMATO_DEBIAN = "debian"
FORMATO_FEDORA = "fedora"
FORMATO_DESCONHECIDO = "desconhecido"

#: O gesto de cada formato. **PROVISÓRIO — decisão dela**: os cinco nomeados
#: são texto novo de tela (o carimbo é herdado da T-03, que redigiu a genérica
#: e parou aqui de propósito).
#:
#: A forma é a mesma dos dois que já existiam, e não é estilo: a frase entra no
#: MESMO lugar de outras ("…, ou <isto>", "— <isto> e reconecte os controles"),
#: então ela é um GESTO ("rode X"), nunca uma oração inteira. Os dois extremos
#: da escada vêm de `repo_files.FRASE_DE_ATUALIZAR` por referência — redigi-los
#: de novo aqui é como duas verdades começam nesta casa.
GESTO_DE_ATUALIZAR: dict[str, str] = {
    FORMATO_CHECKOUT: FRASE_DE_ATUALIZAR[True],
    FORMATO_FLATPAK: "rode flatpak update",
    FORMATO_ARCH: "rode sudo pacman -Syu",
    FORMATO_FEDORA: "rode sudo dnf upgrade",
    FORMATO_DEBIAN: "rode sudo apt upgrade",
    FORMATO_NIX: "rode nix profile upgrade",
    FORMATO_DESCONHECIDO: FRASE_DE_ATUALIZAR[False],
}

#: Quem responde "este arquivo é meu", e o formato de cada um. A ordem não
#: importa: numa máquina só um deles reconhece o caminho.
_GERENCIADORES: tuple[tuple[str, str, str], ...] = (
    (FORMATO_ARCH, "pacman", "-Qo"),
    (FORMATO_DEBIAN, "dpkg", "-S"),
    (FORMATO_FEDORA, "rpm", "-qf"),
)


@lru_cache(maxsize=8)
def _dono_do_arquivo(caminho: str) -> str | None:
    """Qual gerenciador de pacotes diz ser dono deste caminho, ou ``None``.

    ``None`` é o degrau final da escada e significa *"ninguém assume"* —
    AppImage, `pip install --user`, `make install` à mão. É a resposta honesta,
    e é ela que devolve a frase genérica.

    Em cache porque a resposta não muda no meio de um processo (o pacote não é
    reinstalado por baixo da GUI aberta) e porque a frase é interpolada em
    muitas linhas do mesmo laudo — sem cache, o cartão "Saúde do sistema"
    pagaria um `dpkg -S` por linha. A chave é `str` e não `Path` de propósito:
    quem injeta o consultor nos testes não passa por aqui.
    """
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
    """Como este Hefesto foi instalado — em uma palavra.

    Os quatro parâmetros existem para a bancada e para quem já perguntou; em
    produção ninguém passa nenhum. Eles são o que dá mordida ao teste: um
    `/nix/store` de mentira é um `Path`, não uma variável de ambiente de
    fundo de gaveta.

    A escada, e cada degrau é uma MEDIÇÃO, não um palpite:

    1. **checkout** — há um `install.sh` ao lado do código (`repo_files`);
    2. **flatpak** — o `/.flatpak-info` que o próprio flatpak monta em todo
       sandbox, ou o `FLATPAK_ID` do ambiente;
    3. **nix** — o código está dentro do `/nix/store`;
    4. **arch/debian/fedora** — o gerenciador de pacotes ASSUME o arquivo;
    5. **desconhecido** — ninguém assume, e a frase volta a ser a genérica.
    """
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
    """O gesto de atualizar que serve para ESTA instalação, sem jargão.

    Substitui `repo_files.como_atualizar_esta_instalacao()` nos chamadores que
    esta frente possui. Os argumentos são os de :func:`formato_desta_instalacao`.
    """
    return GESTO_DE_ATUALIZAR[
        formato_desta_instalacao(
            e_checkout=e_checkout,
            marca_flatpak=marca_flatpak,
            raiz_do_codigo=raiz_do_codigo,
            consultar_dono=consultar_dono,
        )
    ]

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

    AMBIENTE-PRESUMIDO-01 (23/08/2026): o ``.config`` era CRAVADO aqui, e este
    era o único dos cinco leitores da allowlist que ignorava
    ``XDG_CONFIG_HOME`` — os outros quatro (o `disable_steam_input.sh`, o
    `doctor.sh`, o `daemon/launch_env` e o próprio ESCRITOR, o botão "Este jogo
    não funciona") o resolvem. Com a variável setada, o botão gravava num
    arquivo e o cartão da aba lia outro: a exceção era escrita e a tela seguia
    dizendo que o jogo estava fora da lista, sem erro nenhum. Agora o leitor
    chama a MESMA função do escritor — a divergência deixa de ser possível.
    """
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
    # BG-SAUDE-01 (26/08/2026) — **PROVISÓRIO — decisão dela**.
    # A frase dizia *"quirk anti-storm AUSENTE do usbcore (storm pode reincidir
    # sob carga)"*: o quê e o porquê em linguagem de kernel, e nenhum
    # o-que-fazer. Aqui o gesto honesto é NADA, e isso não é evasiva — este
    # quirk é o cinto extra (a alavanca A do `doctor.sh:837`), e a cura de raiz
    # é a linha de cima, do `check_snd_quirk`. Mandar mexer no cmdline do
    # kernel quem já está curado seria trabalho inventado; o público desta tela
    # não tem PS5 nem guia de USB.
    return WARN, (
        "o cinto extra do áudio USB não está posto (sob carga o travamento "
        f"pode voltar). {PREFIXO_DA_CURA}nada, enquanto a linha da cura do "
        "travamento do USB, logo acima, estiver verde — é ela que resolve na "
        "raiz."
    )


def find_localconfig_vdfs(home: Path) -> list[Path]:
    """localconfig.vdf per-user em layouts comuns de Steam no Linux (dedup).

    A lista de raízes é a de `steam_launch_options.RAIZES_STEAM_RELATIVAS` —
    uma só para o projeto inteiro (AMBIENTE-PRESUMIDO-01, 23/08/2026).
    """
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
        # BG-SAUDE-01 — **PROVISÓRIO — decisão dela**. Era *"Steam Input:
        # nenhum localconfig.vdf encontrado (Steam instalada?)"*: o nome de um
        # arquivo que a pessoa nunca vai abrir, e uma pergunta em vez de um
        # gesto. O nome do arquivo fica entre parênteses porque o `doctor.sh`
        # e o `disable_steam_input.sh` falam dele — mas ele deixou de ser a
        # frase.
        return INFO, (
            "Steam Input: não encontrei a Steam nesta máquina (nenhum "
            f"localconfig.vdf). {PREFIXO_DA_CURA}nada, se você não usa a "
            "Steam. Se usa, abra a Steam e faça login uma vez — depois volte "
            "a esta aba."
        )
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
                f"exceções. {PREFIXO_DA_CURA}para manter a sua escolha, abra o "
                "jogo e clique 'Este jogo não funciona' na aba Sistema."
            )
        if global_ligado:
            partes.append(
                "Steam Input LIGADO no ajuste GLOBAL da Steam (vale para todo "
                f"jogo, não é escolha por jogo). {PREFIXO_DA_CURA}clique "
                f"'{rotulo_do_botao('btn_storm_fix_safe', 'Consertar problemas conhecidos')}' "
                "na aba Sistema para desligar."
            )
        return WARN, " ".join(partes)
    excecoes = [
        v for v in vdfs if _STEAM_INPUT_RE.search(_safe_read(v))
    ]
    if excecoes:
        # T-07 (SISTEMA-O-VIGIA-VIVO-01, 25/08/2026). Esta linha É PINTADA NA
        # TELA, e dizia *"jogos cujo DualSense é entregue pela Steam"* — o
        # enquadramento que ela DERRUBOU em 09/08/2026
        # (ESCONDER-EM-VEZ-DE-SAIR-01). A marca inverteu de lado: em vez de
        # tirar o Hefesto da frente, ela ESCONDE o controle físico do jogo, e
        # os controles virtuais do Hefesto ficam de pé — que é justamente o
        # que o texto velho tinha de omitir.
        #
        # O `main.glade` recebeu o recado naquele dia (a nota datada em volta
        # do `btn_steam_game_broken`); o código que pinta, não. Fato errado
        # sai de TODOS os lugares onde aparece, e este era o último em `src/`
        # que ainda chegava aos olhos dela.
        #
        # A redação abaixo é a da caixinha da aba Perfis (`profiles_actions.
        # _frase_da_marca`), palavra por palavra, porque as duas marcam a
        # MESMA coisa — e duas maneiras de dizer o mesmo gesto obrigam quem lê
        # a descobrir que são o mesmo gesto.
        return OK, (
            "Steam Input desligado (com exceções por jogo, marcadas por "
            "você — nesses o controle físico fica escondido)"
        )
    return OK, "Steam Input desligado para o DualSense"


def check_wireplumber(dropin_dir: Path | None = None) -> tuple[str, str]:
    """Drop-in do WirePlumber (DualSense não-default / só-HID) instalado?"""
    if dropin_dir is None:
        # T-05 (ONDA0-Z7): dono único em xdg_paths — honra XDG_CONFIG_HOME.
        from hefesto_dualsense4unix.utils.xdg_paths import wireplumber_config_dir

        dropin_dir = wireplumber_config_dir()
    names = [
        "51-hefesto-dualsense-no-default-source.conf",
        "52-hefesto-dualsense-disable-source.conf",
    ]
    present = [n for n in names if (dropin_dir / n).is_file()]
    if present:
        return OK, f"WirePlumber configurado ({', '.join(present)})"
    # BG-SAUDE-01 — **PROVISÓRIO — decisão dela**. Esta era a pior das doze:
    # dizia *"WirePlumber sem drop-in do hefesto ('doctor --fix-safe'
    # instala)"* — mandava a pessoa a um comando de terminal enquanto o botão
    # que roda EXATAMENTE esse script está três linhas abaixo, na mesma tela
    # ("Aplicar correções" → `on_storm_fix_safe`, que chama o
    # `scripts/fix_wireplumber_default_source.sh --install`).
    return INFO, (
        "o ajuste de áudio do Hefesto não está instalado — sem ele o controle "
        "pode virar o microfone padrão do sistema sozinho. "
        f"{PREFIXO_DA_CURA}clique 'Aplicar correções' na aba Sistema."
    )


def check_authorized_rule(rules_dir: Path | None = None) -> tuple[str, str]:
    """Regra udev authorized=0 (rota áudio-off agressiva) instalada?

    Opt-in: presença = mic/fone do controle desligados. Só INFO.
    """
    rules_dir = rules_dir or Path("/etc/udev/rules.d")
    rule = rules_dir / "75-ps5-controller-disable-usb-audio.rules"
    if rule.is_file():
        # BG-SAUDE-01 — **PROVISÓRIO — decisão dela**. `authorized=0` é o nome
        # do gesto no kernel, não na tela. O estado é DELIBERADO (a regra 75 é
        # opt-in do instalador), então o gesto é "nada" — com a saída escrita
        # ao lado, que é o que faltava.
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
        # BG-SAUDE-01 — o gesto já estava aqui; o que faltava era estar no
        # molde, para a pessoa achá-lo sempre no mesmo lugar da frase.
        return INFO, (
            "a cura do travamento está agendada. "
            f"{PREFIXO_DA_CURA}desconecte e reconecte os controles para ela "
            "valer agora."
        )
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
    # BG-INSTALL-01 (26/08/2026): o "rode ./install.sh" era cravado, e este
    # laudo aparece em TODO formato de instalação — inclusive nos cinco que
    # não têm o arquivo.
    # BG-06b (26/08/2026): a frase deixou de parar no honesto-e-vago. O
    # `gesto_de_atualizar()` NOMEIA o gesto do formato desta máquina
    # (`flatpak update`, `pacman -Syu`, …) e só cai na genérica quando ninguém
    # assume o arquivo — ver o bloco no topo deste módulo.
    return (
        WARN,
        f"cura do travamento do USB AUSENTE — sem ela os controles podem "
        f"desconectar no meio do jogo. {PREFIXO_DA_CURA}{gesto_de_atualizar()} "
        f"e reconecte os controles (o botão "
        f"'{rotulo_do_botao('btn_storm_fix_safe', 'Consertar problemas conhecidos')}' "
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
    # Aqui `esperados >= 2` sempre (0 < placas < esperados), então o denominador
    # é plural de verdade; o que varia é quantos ficaram de fora.
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
    "GESTO_DE_ATUALIZAR",
    "PREFIXO_DA_CURA",
    "check_authorized_rule",
    "check_quirk",
    "check_snd_audio_healthy",
    "check_snd_quirk",
    "check_steam_input",
    "check_wireplumber",
    "contar_placas_dualsense",
    "controles_no_cabo",
    "find_localconfig_vdfs",
    "formato_desta_instalacao",
    "gesto_de_atualizar",
    "steam_input_allowlist",
    "steam_input_fora_da_allowlist",
    "steam_input_on_fora_da_allowlist",
    "storm_report",
]
