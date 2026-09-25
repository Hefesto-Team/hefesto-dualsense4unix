"""Quais controles o JOGO está lendo — a pergunta que decide quem vibra.

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

**Com máscara, o jogo não lê o controle físico — lê o VIRTUAL.** Medido na mesa
dela em 20/09, com os quatro ligados e o PRAGMATA aberto::

    event21, event264, event265   uniq=02:fe:f0:…   «DualSense (Hefesto P1)»
    event22, event27,  event28    uniq=d4:2f:4b:…   o P3 FÍSICO

O ``02:fe:f0:…`` é o vpad que o Hefesto publica. Um jogo com máscara DualSense
abre **esse**, e casar por ``uniq`` físico devolveria "ninguém está jogando" —
o tipo de resposta plausível e falsa que esta casa persegue. Por isso a
tradução virtual→físico entra aqui, e quem responde é o dono da ligação.

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

**Nada muda sem vpad nem com o vpad ``uinput``.** No Modo Nativo o jogo abre
o físico, que casa pelo próprio ``uniq``, e o tradutor nem é perguntado. Com
a máscara Xbox o vpad é ``uinput`` e não carrega ``uniq``: o jogo que o lê
não entra no conjunto, antes e depois desta cura.

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
from typing import Any

__all__ = [
    "ENV_DO_JOGO",
    "dono_do_vpad_pelo_coop",
    "evdevs_abertos_por",
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


def evdevs_abertos_por(
    pids: Iterable[int], raiz_proc: pathlib.Path | str = "/proc"
) -> set[str]:
    """Os ``eventN`` que aqueles processos têm abertos AGORA.

    Um descritor que não se consegue ler não é um "não": é um desconhecido, e
    ele simplesmente não entra no conjunto. Quem chama trata o vazio.
    """
    raiz = pathlib.Path(raiz_proc)
    abertos: set[str] = set()
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
                abertos.add(achado.group(1))
    return abertos


def quem_o_jogo_le(
    *,
    fisicos: Iterable[str],
    dono_do_vpad: Callable[[str], str | None] | None = None,
    raiz_proc: pathlib.Path | str = "/proc",
    raiz_input: pathlib.Path | str = "/sys/class/input",
) -> set[str]:
    """Os ``uniq`` FÍSICOS que algum jogo está lendo agora.

    :param fisicos: os ``uniq`` dos controles de verdade, para separar o que é
        aparelho do que é vpad. Sem esta lista não há como distinguir os dois,
        e inventar a distinção por forma do endereço seria adivinhar.
    :param dono_do_vpad: dado o ``uniq`` de um vpad, devolve o do controle
        físico que o ALIMENTA agora (:func:`dono_do_vpad_pelo_coop`). É
        injetável porque o dono dessa ligação é o co-op — perguntar a ele é a
        regra da casa.

    Devolve conjunto VAZIO quando não há jogo, quando ``/proc`` não se lê, ou
    quando o que o jogo abriu não se traduz em controle nenhum. O vazio aqui
    quer dizer "ninguém vibra", que é o lado seguro.
    """
    conhecidos = {str(u).lower() for u in fisicos if u}
    pids = pids_de_jogo(raiz_proc)
    if not pids:
        return set()

    abertos = evdevs_abertos_por(pids, raiz_proc)
    if not abertos:
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
        # máscara é EXATAMENTE ele que o jogo abre. Sem tradutor, a resposta
        # honesta é não contar — nunca chutar um físico.
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
