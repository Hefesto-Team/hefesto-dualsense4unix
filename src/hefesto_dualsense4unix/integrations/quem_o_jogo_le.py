"""Quais controles o evdev diz que o JOGO lê — e o retrato do jogo que a volta usa.

**DESDE 26/09/2026 ESTE SINAL NÃO VOTA** (A-HAPTICA-QUEM-JOGA-02, decisão
``D-2609-QUEM-JOGA-E-QUEM-MEXE``). Quem joga, para o portão da háptica pelo
rádio, é quem MEXEU desde que o jogo abriu (``daemon/subsystems/quem_mexe.py``).
Daqui a volta usa o :class:`RetratoDoJogo` (os pids que abrem e fecham a
partida, e o que o jogo segura), e o conjunto de :func:`quem_o_jogo_le` vai à
linha ``haptica_portao_fechado`` como pista (``evdev_le_este``). O texto abaixo
é o registro de 20 e 25/09, quando ele votava.

**A CORREÇÃO É DELA, 20/09/2026, e derrubou a premissa de uma sprint inteira:**

    "na real o certo não era somente o controle do player 1 receber a vibração?
     pq é um jogo de um player e o erro era que o player 3 tava recebendo a
     vibração de forma espelhada"

A `O-ROTULO-QUE-COLIDE-01` leu a queixa como *"dois controles não vibram"* e
curou a colisão de nomes dos gravadores. A colisão era real e a cura fica — mas
ela não era a causa. A causa é que **o modo háptica entrava em todo controle
cujo endpoint tivesse stream**, e num jogo de um jogador isso não é ninguém
além de quem segura o controle.

E a colisão era, por acidente, o que segurava os outros dois: medido no journal
dela, 1 controle entrou em háptica e 270 tentativas de cada um dos outros dois
foram recusadas. *Curar a colisão sem este gate faria os três vibrarem.*

A REGRA, decidida por ela entre três opções:

    Só o controle que o JOGO está usando entra em modo háptica.

Ela recusou «só o jogador 1» pensando no jogo de quatro do amigo dela: uma
regra fixa no índice 1 quebraria o co-op. *A regra é uma só, e serve às duas
mesas.*

O SINAL, e ele é universal
==========================

**Quem o jogo tem ABERTO.** Os descritores de um processo são legíveis em
``/proc/<pid>/fd``, e cada ``eventN`` carrega o ``uniq`` do controle no sysfs.
Não depende de saber o nome do jogo, nem de lista de jogos, nem de lançador —
o que atende a ordem dela de 16/09: *o app é de acessibilidade e não se cura
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

FATO SUBSTITUÍDO: aqui estava *"Medido na mesa dela em 20/09 … event21,
event264, event265 uniq=02:fe:f0:… Um jogo com máscara DualSense abre esse"*.
A lista era de nós que o DAEMON via (a sprint de 20/09: «83 descritores
visíveis»), sem nomear quem os segurava; e no ``017d72d1c`` a mesma frase dizia
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

#: A variável que marca um processo rodando sob Proton. Um jogo Steam a carrega
#: em toda a cadeia (medido em 20/09: seis dos sete processos do PRAGMATA,
#: inclusive o `.exe`); nenhum shell nosso a carrega, e é isso que a torna um
#: filtro e não um palpite.
ENV_DO_JOGO = "STEAM_COMPAT_DATA_PATH"

#: `eventN` no alvo de um link de `/proc/<pid>/fd`.
_EVENTO = re.compile(r"/(event\d+)$")
#: `hidrawN` no alvo de um link de `/proc/<pid>/fd`.
_HIDRAW = re.compile(r"/(hidraw\d+)$")

#: Onde o kernel lista os ``hidrawN``. Lida na CHAMADA, e não no padrão do
#: argumento: a suíte a aponta para uma pasta vazia (``tests/conftest.py``), e
#: nenhum teste lê o ``uevent`` de um aparelho dela.
RAIZ_CLASS_HIDRAW = "/sys/class/hidraw"


@dataclass(frozen=True)
class RetratoDoJogo:
    """O que a volta viu do jogo, numa passada só de ``/proc``.

    A-HAPTICA-QUEM-JOGA-01. Quem precisa saber se há jogo (a partida de
    ``quem_mexe``) e o que ele segura (a linha do portão fechado) recebe isto
    da MESMA varredura que :func:`quem_o_jogo_le` já fazia: medido em 26/09
    com o jogo aberto, ela custa 8 ms para achar os 18 processos e 15 ms para
    ler os descritores — uma segunda por volta dobraria a conta.
    """

    pids: frozenset[int] = frozenset()
    eventos: frozenset[str] = frozenset()
    hidraws: frozenset[str] = frozenset()


def uniq_por_evdev(raiz: pathlib.Path | str = "/sys/class/input") -> dict[str, str]:
    """``{"event22": "d4:2f:4b:…"}`` — o dono de cada nó de entrada.

    Um controle publica VÁRIOS ``eventN`` (botões, movimento, touchpad, o
    conector do fone), e todos carregam o mesmo ``uniq``. Ler qualquer um
    responde a mesma coisa, então não há escolha a fazer aqui.
    """
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
    """Os processos que são JOGO, pelo ambiente e não pelo nome.

    Casar por nome de processo seria uma lista de jogos — e a ordem dela de
    16/09 é que *o app é de acessibilidade e não se cura por caso*. O ambiente
    responde sobre qualquer jogo Steam, inclusive os que ela instalar amanhã.
    """
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
    """Os ``(eventN, hidrawN)`` que aqueles processos têm abertos AGORA.

    Um descritor que não se consegue ler não é um "não": é um desconhecido, e
    ele simplesmente não entra no conjunto. Quem chama trata o vazio.
    """
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

    A marca é a que só o produto escreve (``uhid_gamepad.VPAD_HID_PHYS``,
    ``hefesto-vpad``), a mesma que o backend e o broker usam. Morar sob
    ``/devices/virtual/misc/uhid/`` não separa nada: com o BlueZ de hoje, o
    DualSense FÍSICO pelo rádio também nasce por ``uhid``. Nó ilegível não
    conta. Só a linha do portão fechado pergunta, e só quando ela muda.
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import VPAD_HID_PHYS

    raiz = pathlib.Path(RAIZ_CLASS_HIDRAW)
    achados: set[str] = set()
    for nome in nomes:
        try:
            texto = (raiz / nome / "device" / "uevent").read_text(
                encoding="utf-8", errors="replace"
            )
        except OSError:
            continue
        for linha in texto.splitlines():
            chave, _, valor = linha.partition("=")
            if chave == "HID_PHYS" and valor.strip().startswith(VPAD_HID_PHYS):
                achados.add(nome)
                break
    return frozenset(achados)


def quem_o_jogo_le(
    *,
    fisicos: Iterable[str],
    dono_do_vpad: Callable[[str], str | None] | None = None,
    raiz_proc: pathlib.Path | str = "/proc",
    raiz_input: pathlib.Path | str = "/sys/class/input",
    ao_ver_o_jogo: Callable[[RetratoDoJogo], None] | None = None,
) -> set[str]:
    """Os ``uniq`` FÍSICOS que algum jogo está lendo agora.

    :param fisicos: os ``uniq`` dos controles de verdade, para separar o que é
        aparelho do que é vpad. Sem esta lista não há como distinguir os dois,
        e inventar a distinção por forma do endereço seria adivinhar.
    :param dono_do_vpad: dado o ``uniq`` de um vpad, devolve o do controle
        físico que o ALIMENTA agora (:func:`dono_do_vpad_pelo_coop`). É
        injetável porque o dono dessa ligação é o co-op — perguntar a ele é a
        regra da casa.
    :param ao_ver_o_jogo: recebe o :class:`RetratoDoJogo` desta passada, antes
        de qualquer resposta — também quando não há jogo, que é o retrato vazio.
        É por ele que a volta sabe se a partida abriu sem varrer ``/proc`` de
        novo.

    Devolve conjunto VAZIO quando não há jogo, quando ``/proc`` não se lê, ou
    quando o que o jogo abriu não se traduz em controle nenhum. O vazio aqui
    quer dizer "ninguém vibra", que é o lado seguro.
    """
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
        # NÃO É UM CONTROLE FÍSICO: é o vpad que o Hefesto publica, e com
        # máscara é ele que o jogo lê. Sem tradutor, a resposta honesta é não
        # contar — nunca chutar um físico.
        if dono_do_vpad is None:
            continue
        fisico = dono_do_vpad(uniq)
        if fisico and str(fisico).lower() in conhecidos:
            jogando.add(str(fisico).lower())
    return jogando


#: Um endereço de aparelho tem doze dígitos hexadecimais.
_DIGITOS_DE_MAC = 12


def _digitos(endereco: object) -> str:
    """Os doze dígitos de um endereço, em minúsculas — ou ``""``.

    O co-op guarda a identidade colada (``aabbcc000001``, a do ``norm_mac``) e
    o sysfs a imprime com ``:``; os dois lados são o mesmo aparelho. Descartar
    e não peneirar: um caractere fora de ``[0-9a-f:]`` invalida o valor (um
    ``path:`` tem ``d``, ``e`` e ``a`` no meio, e uma peneira faria dele um
    endereço).
    """
    baixo = str(endereco or "").strip().lower()
    if any(ch not in "0123456789abcdef:" for ch in baixo):
        return ""
    digitos = baixo.replace(":", "")
    return digitos if len(digitos) == _DIGITOS_DE_MAC else ""


def dono_do_vpad_pelo_coop(
    coop: Any, fisicos: Iterable[str]
) -> Callable[[str], str | None]:
    """O tradutor vpad→físico de :func:`quem_o_jogo_le`, PERGUNTANDO AO CO-OP.

    A-HAPTICA-SEGUE-QUEM-ALIMENTA-O-VPAD-01. O dono da ligação entre cada
    físico e o vpad dele é quem a faz: o ``CoopManager``
    (``quem_alimenta_cada_vpad``) — o posto é do primário de AGORA, e cada
    secundário é do físico dele. A pergunta é feita UMA vez, na montagem; o
    tradutor devolvido só consulta a resposta.

    O físico devolvido é o da lista ``fisicos``, na grafia em que ela veio:
    é com ela que :func:`quem_o_jogo_le` compara.

    **Nunca chuta.** Sem co-op (o daemon ainda não o criou), sem a pergunta
    (um dublê), com um vpad que ninguém alimenta ou com um dono que não está
    na mesa, a resposta é ``None``: ninguém vibra por aquele vpad. Uma
    exceção da pergunta SOBE — quem chama registra e responde o vazio.
    """
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
