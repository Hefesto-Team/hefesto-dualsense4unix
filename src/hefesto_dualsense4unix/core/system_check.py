"""Checks de infra read-only para auto-diagnóstico no boot.

FEAT-SYSTEM-AUTOREPAIR-BOOT-01: espelha em Python parte do `scripts/doctor.sh`,
focado no que vale AVISAR ao usuário no boot do daemon (udev de hotplug
desatualizado, WirePlumber sequestrando o microfone do DualSense). NUNCA levanta
e NUNCA roda sudo/reparo — apenas detecta e devolve mensagens com o comando
sugerido. O reparo de fato fica a cargo do usuário (`doctor --fix`).
"""
from __future__ import annotations

import os
from pathlib import Path

# Nome de unit ERRADO que versões antigas das regras 73/74 instalaram
# (BUG-UDEV-HOTPLUG-UNIT-NAME-MISMATCH-01). A unit real tem o prefixo completo.
_WRONG_HOTPLUG_PATTERN = 'SYSTEMD_USER_WANTS}="hefesto-gui-hotplug.service"'
_UDEV_RULES = (
    "/etc/udev/rules.d/73-ps5-controller-hotplug.rules",
    "/etc/udev/rules.d/74-ps5-controller-hotplug-bt.rules",
)

# HAPTICA-NATIVA-01: onde o kernel lista as placas de som (o nome longo vem na
# segunda linha de cada uma) e onde mora a árvore UCM. Lidos NA CHAMADA, porque
# a suíte aponta os dois para o vazio.
_PROC_CARDS = "/proc/asound/cards"
_RAIZ_UCM = "/usr/share/alsa/ucm2"
_NOME_DO_DUALSENSE = "Sony Interactive Entertainment DualSense"


def _udev_hotplug_outdated() -> bool:
    """True se alguma regra 73/74 instalada cita a unit de hotplug ERRADA."""
    for rule in _UDEV_RULES:
        try:
            text = Path(rule).read_text(encoding="utf-8")
        except OSError:
            continue
        if _WRONG_HOTPLUG_PATTERN in text:
            return True
    return False


#: A chave EXATA do padrão de captura que alguém escolheu. As irmãs com sufixo
#: (`…source.0=`, `…source.1=`) são a PILHA do que foi escolhido antes
#: (`state-default-nodes.lua` do WirePlumber) — não são a escolha de agora.
_CHAVE_DA_FONTE_CONFIGURADA = "default.configured.audio.source"


def fonte_configurada_do_wireplumber() -> str | None:
    """O microfone padrão que alguém ESCOLHEU e o WirePlumber gravou, ou `None`.

    É o `default.configured.audio.source` do `default-nodes`: o que um
    `pactl set-default-source` (nosso ou de qualquer outro programa) ou a
    escolha nas configurações de som deixou gravado. O WirePlumber o devolve
    sozinho quando aquele nó reaparece — é por isso que ele é a escolha dela,
    e não o ativo de agora.

    **UM LEITOR SÓ DESTE ARQUIVO no lado Python.** O aviso de boot
    (`_wireplumber_hijacks_mic`) e o nascimento do microfone
    (`daemon/subsystems/hotkey._a_escolha_gravada_e_de_outro_controle`) fazem
    a mesma pergunta ao mesmo disco; duas leituras seriam duas réguas sobre o
    mesmo estado. O caminho é o mesmo dos donos do shell (`doctor.sh`,
    `fix_wireplumber_default_source.sh`: `${HOME}/.local/state/...`).

    `None` quando não há escolha gravada (a máquina nova, que nunca escolheu),
    ou quando o arquivo não se deixa ler. Nunca levanta.
    """
    estado = Path.home() / ".local/state/wireplumber/default-nodes"
    try:
        linhas = estado.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for linha in linhas:
        chave, igual, valor = linha.partition("=")
        if igual and chave.strip().lower() == _CHAVE_DA_FONTE_CONFIGURADA:
            return valor.strip() or None
    return None


def _wireplumber_hijacks_mic() -> bool:
    """True se o WirePlumber fixou o DualSense como fonte de áudio padrão."""
    fonte = fonte_configurada_do_wireplumber()
    return fonte is not None and "dualsense" in fonte.lower()


def _dir_dos_dropins() -> Path:
    """Onde o `fix_wireplumber_default_source.sh` põe os drop-ins 51/52/53/54."""
    return Path.home() / ".config/wireplumber/wireplumber.conf.d"


def _marca_do_gesto_do_mic() -> Path:
    """O arquivo em que quem PEDIU o mic do controle deixou o gesto gravado.

    O mesmo caminho do `_marca_do_gesto_do_mic()` do `doctor.sh` — e o
    `XDG_STATE_HOME` é lido NA HORA, porque a suíte o desvia para um lar de
    mentira e uma cópia no topo do módulo congelaria o de antes.
    """
    estado = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local/state")
    return Path(estado) / "hefesto-dualsense4unix" / "mic-do-dualsense-pedido.conf"


def _dualsense_mic_intended() -> bool:
    """True quando o mic do DualSense ser a fonte padrão é o que a pessoa PEDIU.

    **O DEFEITO, medido em 16/09/2026 na máquina dela.** Esta função perguntava
    a UMA variável de ambiente, e só a ela — enquanto o `doctor.sh` responde à
    MESMA pergunta com CINCO degraus (`_prefere_mic_do_dualsense`). Duas fontes
    de verdade para a mesma decisão, e esta lia a mais fraca: o daemon sobe pelo
    systemd com `Environment=PYTHONUNBUFFERED=1` e mais nada, então a variável
    **nunca chega aqui** por esse caminho.

    O estado em que os dois se contradizem não é hipotético — é o que o próprio
    instalador produz. Quem roda `install.sh --keep-dualsense-mic` sai com a
    marca do gesto gravada (`install.sh:3556`) e SEM o drop-in 51, e então:

        doctor.sh ....... [OK] microfone ativo é o DualSense (foi pedido)
        system_check .... WirePlumber fixou o DualSense — rode doctor.sh --fix

    O produto mandava desfazer a escolha que a pessoa acabara de fazer no
    instalador, a cada boot do daemon — e `--fix` instala o 51, que rebaixa
    justamente o microfone pedido. **Quem usa o mic do controle por
    acessibilidade seguiria a instrução do produto e perderia o microfone.**

    A cura é a regra da casa, sem novidade: *quando um valor tem dono, a régua
    PERGUNTA ao dono*. Os cinco degraus abaixo são os do `doctor.sh`, na mesma
    ordem e pela mesma razão — a ordem é a hierarquia de quem manda, e o último
    degrau é o que diz que **"não sei" nunca é "ela pediu"**.
    """
    conf = _dir_dos_dropins()
    # 1. Quem DESLIGOU de propósito vem antes de tudo: o 52 é a escolha
    #    explícita de "o controle é só-HID".
    if (conf / "52-hefesto-dualsense-disable-source.conf").exists():
        return False
    # 2. Opt-in explícito por ambiente. Continua valendo para quem roda o daemon
    #    à mão ou põe um drop-in de systemd — só deixou de ser o único sinal.
    if os.environ.get(
        "HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED", ""
    ).strip().lower() in ("1", "true", "yes"):
        return True
    # 3. O 51 é a política DEFAULT do install: rebaixar. Enquanto ele está no
    #    lugar, o controle é a ÚLTIMA opção — não a primeira.
    if (conf / "51-hefesto-dualsense-no-default-source.conf").exists():
        return False
    # 4. A MARCA DO GESTO. Sem o 51, é ELA quem diz que a promoção foi pedida.
    #
    # 5. E sem a marca: NÃO SEI — e "não sei" nunca é "ela pediu". A ausência
    #    tem duas origens que o disco não distingue (a promoção explícita e o
    #    `uninstall` que desarmou a cura), e ler as duas como uma já custou uma
    #    noite em 04/08/2026 (DROPIN-AMBIGUO-01). Os dois degraus cabem num
    #    `return` só porque o degrau 5 É a negação do 4 — não porque sejam a
    #    mesma pergunta.
    return _marca_do_gesto_do_mic().exists()


def _dualsenses_no_cabo_sem_ucm() -> list[str]:
    """Os nomes longos das placas de DualSense no cabo que o UCM não alcança.

    O mesmo teste do `check_ucm_do_dualsense` do `doctor.sh`: o
    `scripts/install_ucm_dualsense.sh` grava um gancho por controlador USB em
    `conf.d/USB-Audio/<nome longo>.conf`, e uma placa sem o gancho abre sem o
    sink `…HiFi__Speaker__sink` — o jogo da Sony pelo Proton não vibra. Uma
    distro sem `ucm.conf` não tem o que armar, e fica calada.
    """
    raiz = Path(_RAIZ_UCM)
    if not (raiz / "ucm.conf").is_file():
        return []
    try:
        linhas = Path(_PROC_CARDS).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    sem = []
    for linha in linhas:
        nome = linha.strip()
        if not nome.startswith(_NOME_DO_DUALSENSE):
            continue
        if not (raiz / "conf.d" / "USB-Audio" / f"{nome}.conf").is_file():
            sem.append(nome)
    return sem


def system_warnings() -> list[str]:
    """Avisos de infra para o boot. Read-only; nunca levanta, nunca usa sudo."""
    warnings: list[str] = []
    try:
        if _udev_hotplug_outdated():
            warnings.append(
                "regras udev de hotplug desatualizadas (nome de unit antigo) — "
                "rode: sudo bash scripts/install_udev.sh"
            )
        if not _dualsense_mic_intended() and _wireplumber_hijacks_mic():
            warnings.append(
                "WirePlumber fixou o DualSense como microfone padrão — "
                "rode: scripts/doctor.sh --fix"
            )
        if _dualsenses_no_cabo_sem_ucm():
            warnings.append(
                "DualSense no cabo sem o perfil UCM — a vibração dos jogos da "
                "Sony não chega pelo cabo; rode: bash scripts/install_ucm_dualsense.sh"
            )
    except Exception:
        return warnings
    return warnings


__all__ = ["fonte_configurada_do_wireplumber", "system_warnings"]
