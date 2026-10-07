"""Quais controles o evdev diz que o JOGO lê — a PISTA da linha do portão fechado.

**DESDE 26/09/2026 ESTE SINAL NÃO VOTA** (A-HAPTICA-QUEM-JOGA-02, decisão
``D-2609-QUEM-JOGA-E-QUEM-MEXE``). Quem joga, para o portão da háptica pelo
rádio, é quem MEXEU desde que o jogo abriu (``daemon/subsystems/quem_mexe.py``).

**E DESDE 28/09/2026 A PARTIDA NÃO SAI DAQUI** (A-HAPTICA-DO-RADIO-OBEDECE-AO-
SINAL-DO-JOGO-01). Quem abre e fecha a partida é o dono do fluxo no endpoint
de háptica, perguntado ao servidor de som; :func:`pids_de_jogo`, que lê o
``environ`` de todo processo, deixou de rodar a cada volta — um ``run``
auxiliar do GE-Proton, com ``STEAM_COMPAT_DATA_PATH`` e sem jogo nenhum,
abria e fechava a partida. O :class:`RetratoDoJogo` e o conjunto de
:func:`quem_o_jogo_le` vão só à linha ``haptica_portao_fechado`` como pista
(``evdev_le_este``), e só quando ela sai. A guarda do rótulo da háptica, que
também perguntava a :func:`pids_de_jogo` (``_ha_jogo_aberto``), saiu em
28/09/2026 com o endpoint por lugar, cujo rótulo não muda. O texto abaixo é o
registro de 20 e 25/09, quando o evdev votava.

**A CORREÇÃO É DO USUÁRIO, 20/09/2026, e derrubou a premissa de uma sprint inteira:**

    "na real o certo não era somente o controle do player 1 receber a vibração?
     pq é um jogo de um player e o erro era que o player 3 tava recebendo a
     vibração de forma espelhada"

A `O-ROTULO-QUE-COLIDE-01` leu a queixa como *"dois controles não vibram"* e
curou a colisão de nomes dos gravadores. A colisão era real e a cura fica — mas
ela não era a causa. A causa é que **o modo háptica entrava em todo controle
cujo endpoint tivesse stream**, e num jogo de um jogador isso não é ninguém
além de quem segura o controle.

E a colisão era, por acidente, o que segurava os outros dois: medido no journal
da bancada, 1 controle entrou em háptica e 270 tentativas de cada um dos outros dois
foram recusadas. *Curar a colisão sem este gate faria os três vibrarem.*

A REGRA, decidida pelo usuário entre três opções:

    Só o controle que o JOGO está usando entra em modo háptica.

Ela recusou «só o jogador 1» pensando no jogo de quatro do amigo dela: uma
regra fixa no índice 1 quebraria o co-op. *A regra é uma só, e serve às duas
mesas.*

O SINAL, e ele é universal
==========================

**Quem o jogo tem ABERTO.** Os descritores de um processo são legíveis em
``/proc/<pid>/fd``, e cada ``eventN`` carrega o ``uniq`` do controle no sysfs.
Não depende de saber o nome do jogo, nem de lista de jogos, nem de lançador —
o que atende a ordem de 16/09: *o app é de acessibilidade e não se cura
por caso*.

A DOBRA QUE NENHUMA LEITURA INGÊNUA ATRAVESSA
=============================================

**Com máscara, o jogo não lê o controle físico — lê o VIRTUAL.** Quando um
processo de jogo segura o ``eventN`` de um vpad, o ``uniq`` do nó é o MAC que
o vpad veste, e casar por ``uniq`` físico devolveria "ninguém está jogando" —
o tipo de resposta plausível e falsa que esta casa persegue. Por isso a
tradução virtual→físico entra aqui, e quem responde é o dono da ligação.

**E O GE-PROTON NÃO SEGURA EVDEV DE DUALSENSE NENHUM** (conferência de
26/09/2026, A-HAPTICA-QUEM-JOGA-01). O winebus fecha todo evdev de DualSense —
o físico por estar na lista de ignorados do SDL, o vpad ``0df2`` por
«deferring … to a different backend» — e fica só com o ``hidraw`` (o fonte
``bus_udev.c``, o rastro ``+hid`` do PRAGMATA de 17/09, e os ``fd`` medidos em
26/09: nenhum ``eventN``, o ``hidraw`` dos vpads). Com máscara DualSense este
sinal sai VAZIO por construção. E o ``hidraw`` não o substitui: o
``winedevice`` segura o de TODOS os vpads, e contá-lo devolveria o espelhado
de 20/09. Quem diz quem joga é a entrada do físico desde que o jogo abriu
(``daemon/subsystems/quem_mexe.py``), e este sinal não vota nem quando existe:
em 21/09, com o PRAGMATA de um jogador, o evdev deixou os QUATRO entrarem em
háptica (A-HAPTICA-QUEM-JOGA-02). Um fd diz o que o processo abriu, não quem
está jogando.

FATO SUBSTITUÍDO: aqui estava *"Medido na bancada em 20/09 … event21,
event264, event265 uniq=02:fe:f0:… Um jogo com máscara DualSense abre esse"*.
A lista era de nós que o DAEMON via (a sprint de 20/09: «83 descritores
visíveis»), sem nomear quem os segurava; e no ``d472e03f7`` a mesma frase dizia
«máscara Xbox».

QUEM ALIMENTA O VPAD, E NÃO DE QUEM ELE NASCEU
==============================================

A-HAPTICA-SEGUE-QUEM-ALIMENTA-O-VPAD-01, 25/09/2026. A tradução derivava o
MAC do vpad de cada físico (``vpad_mac``) e comparava — e isso responde de
quem o vpad NASCEU. O posto nasce sem identidade no boot (o piso
``02:fe:00:00:00:01``, que não deriva de ninguém) ou com a do primário de
quando renasceu, e o primário muda embaixo dele sem ele renascer. Medido na
bancada de queda com os vpads reais, 174 casos (2, 3 e 4 controles; USB, BT
e mista; o posto com o P1, o P2 e o P3; um jogador e todos): a forja errava
138, e em 15 fazia vibrar a mão do P1 que voltou tarde enquanto o P2 ou o P3
dirigia o posto. Quem sabe quem alimenta cada vpad AGORA é o co-op
(``CoopManager.quem_alimenta_cada_vpad``), e a mesma resposta é a que o
rumble do jogo já segue.

**Nada muda sem vpad nem com o vpad ``uinput``.** No Modo Nativo, o jogo que
segura o evdev do físico casa pelo próprio ``uniq``, e o tradutor não decide
nada. Com a máscara Xbox o vpad é ``uinput`` e não carrega ``uniq``: o jogo
que o lê não entra no conjunto, antes e depois desta cura.

AUSÊNCIA É RESPOSTA, E AQUI ELA TEM LADO
========================================

Sem ``/proc`` legível, sem jogo identificável ou sem vpad mapeável, a resposta
é o conjunto VAZIO — ninguém entra em háptica. O lado seguro é o silêncio: um
controle que não vibra é uma falta; um controle que vibra sozinho na mão de
alguém é o defeito que ela reportou.
"""

from __future__ import annotations

import os
import pathlib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

__all__ = [
    "ENV_DO_JOGO",
    "RAIZ_CLASS_HIDRAW",
    "RetratoDoJogo",
    "dono_do_vpad_pelo_coop",
    "hidraws_de_vpad",
    "nos_abertos_por",
    "pids_de_jogo",
    "quem_o_jogo_le",
    "uniq_por_evdev",
]

ENV_DO_JOGO = "STEAM_COMPAT_DATA_PATH"

_EVENTO = re.compile(r"/(event\d+)$")
_HIDRAW = re.compile(r"/(hidraw\d+)$")

RAIZ_CLASS_HIDRAW = "/sys/class/hidraw"


@dataclass(frozen=True)
class RetratoDoJogo:
    """O que a volta viu do jogo, numa passada só de ``/proc``."""

    pids: frozenset[int] = frozenset()
    eventos: frozenset[str] = frozenset()
    hidraws: frozenset[str] = frozenset()


def uniq_por_evdev(raiz: pathlib.Path | str = "/sys/class/input") -> dict[str, str]:
    """``{"event22": "d4:2f:4b:…"}`` — o dono de cada nó de entrada."""
    mapa: dict[str, str] = {}
    base = pathlib.Path(raiz)
    try:
        nos = sorted(base.glob("event*"))
    except OSError:
        return mapa
    for no in nos:
        try:
            uniq = (no / "device" / "uniq").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if uniq:
            mapa[no.name] = uniq.lower()
    return mapa


def _ambiente(pid: int, raiz_proc: pathlib.Path) -> str:
    try:
        return (raiz_proc / str(pid) / "environ").read_bytes().decode(
            "utf-8", "replace"
        )
    except OSError:
        return ""


def pids_de_jogo(raiz_proc: pathlib.Path | str = "/proc") -> set[int]:
    """Os processos que são JOGO, pelo ambiente e não pelo nome."""
    raiz = pathlib.Path(raiz_proc)
    achados: set[int] = set()
    try:
        entradas = list(raiz.iterdir())
    except OSError:
        return achados
    for entrada in entradas:
        if not entrada.name.isdigit():
            continue
        pid = int(entrada.name)
        if f"{ENV_DO_JOGO}=" in _ambiente(pid, raiz):
            achados.add(pid)
    return achados


def nos_abertos_por(
    pids: Iterable[int], raiz_proc: pathlib.Path | str = "/proc"
) -> tuple[frozenset[str], frozenset[str]]:
    """Os ``(eventN, hidrawN)`` que aqueles processos têm abertos AGORA."""
    raiz = pathlib.Path(raiz_proc)
    eventos: set[str] = set()
    hidraws: set[str] = set()
    for pid in pids:
        fd = raiz / str(pid) / "fd"
        try:
            descritores = list(fd.iterdir())
        except OSError:
            continue
        for d in descritores:
            try:
                alvo = os.readlink(d)
            except OSError:
                continue
            achado = _EVENTO.search(alvo)
            if achado:
                eventos.add(achado.group(1))
                continue
            achado = _HIDRAW.search(alvo)
            if achado:
                hidraws.add(achado.group(1))
    return frozenset(eventos), frozenset(hidraws)


def hidraws_de_vpad(nomes: Iterable[str]) -> frozenset[str]:
    """Dos ``hidrawN`` dados, os que são do NOSSO vpad — pelo ``uevent`` do pai HID.

    Quem responde é o ``pad_usb.e_pad_nosso``, o dono único da pergunta: o uhid
    (``HID_PHYS`` ``hefesto-vpad``) e, desde 07/10/2026, o pad em USB (o
    gadget sob o ``vhci_hcd``, com o serial do Hefesto). Morar sob
    ``/devices/virtual/misc/uhid/`` não separa nada: com o BlueZ de hoje, o
    DualSense FÍSICO pelo rádio também nasce por ``uhid``. Nó ilegível não
    conta. Só a linha do portão fechado pergunta, e só quando ela muda.
    """
    from hefesto_dualsense4unix.integrations import pad_usb

    return frozenset(
        nome
        for nome in nomes
        if pad_usb.e_hidraw_de_pad_nosso(nome, raiz_class_hidraw=RAIZ_CLASS_HIDRAW)
    )


def quem_o_jogo_le(
    *,
    fisicos: Iterable[str],
    dono_do_vpad: Callable[[str], str | None] | None = None,
    raiz_proc: pathlib.Path | str = "/proc",
    raiz_input: pathlib.Path | str = "/sys/class/input",
    ao_ver_o_jogo: Callable[[RetratoDoJogo], None] | None = None,
) -> set[str]:
    """Os ``uniq`` FÍSICOS que algum jogo está lendo agora."""
    conhecidos = {str(u).lower() for u in fisicos if u}
    pids = pids_de_jogo(raiz_proc)
    abertos, hidraws = nos_abertos_por(pids, raiz_proc) if pids else (frozenset(), frozenset())
    if ao_ver_o_jogo is not None:
        ao_ver_o_jogo(RetratoDoJogo(pids=frozenset(pids), eventos=abertos, hidraws=hidraws))
    if not pids or not abertos:
        return set()

    donos = uniq_por_evdev(raiz_input)
    jogando: set[str] = set()
    for evento in abertos:
        uniq = donos.get(evento)
        if not uniq:
            continue
        if uniq in conhecidos:
            jogando.add(uniq)
            continue
        if dono_do_vpad is None:
            continue
        fisico = dono_do_vpad(uniq)
        if fisico and str(fisico).lower() in conhecidos:
            jogando.add(str(fisico).lower())
    return jogando


_DIGITOS_DE_MAC = 12


def _digitos(endereco: object) -> str:
    """Os doze dígitos de um endereço, em minúsculas — ou ``""``."""
    baixo = str(endereco or "").strip().lower()
    if any(ch not in "0123456789abcdef:" for ch in baixo):
        return ""
    digitos = baixo.replace(":", "")
    return digitos if len(digitos) == _DIGITOS_DE_MAC else ""


def dono_do_vpad_pelo_coop(
    coop: Any, fisicos: Iterable[str]
) -> Callable[[str], str | None]:
    """O tradutor vpad→físico de :func:`quem_o_jogo_le`, PERGUNTANDO AO CO-OP."""
    perguntar = getattr(coop, "quem_alimenta_cada_vpad", None)
    if not callable(perguntar):
        return lambda _vpad: None
    resposta = perguntar()
    alimenta = {
        _digitos(vpad): _digitos(fisico)
        for vpad, fisico in dict(resposta).items()
        if _digitos(vpad) and _digitos(fisico)
    }
    na_mesa = {_digitos(f): str(f) for f in fisicos if _digitos(f)}

    def _dono(vpad_uniq: str) -> str | None:
        return na_mesa.get(alimenta.get(_digitos(vpad_uniq), ""))

    return _dono
