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


def _wireplumber_hijacks_mic() -> bool:
    """True se o WirePlumber fixou o DualSense como fonte de áudio padrão."""
    state = Path.home() / ".local/state/wireplumber/default-nodes"
    try:
        for line in state.read_text(encoding="utf-8").splitlines():
            low = line.lower()
            if low.startswith("default.configured.audio.source=") and "dualsense" in low:
                return True
    except OSError:
        pass
    return False


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
    except Exception:
        return warnings
    return warnings


__all__ = ["system_warnings"]
