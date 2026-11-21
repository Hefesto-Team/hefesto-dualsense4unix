"""A fonte de captura e o volume de cada controle, pelo `pactl` e pelo recuo do servidor de som.

Funções soltas: nenhuma muta o microfone padrão do sistema. Nunca usa `shell=True`; o logging
é por `get_logger`.
"""
from __future__ import annotations

import os
import re
import subprocess
from typing import Literal

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

SUBPROCESS_TIMEOUT_SEC = 2.0
_MARCAS_DA_FONTE_DO_CONTROLE: tuple[str, ...] = ("dualsense",)


def fonte_de_captura_do_controle() -> str | None:
    """Nome do source de captura do DualSense, ou `None` se não houver.

    `None` não é erro: por Bluetooth, sem a ponte de áudio de pé, **não existe
    fonte** — e é isso que a interface precisa saber para deixar o controle
    deslizante insensível em vez de aceitar um gesto que não faria nada.

    Read-only: só lista. Nunca escreve.
    """
    try:
        saida = _rodar_pelo_recuo(
            ["pactl", "list", "short", "sources"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        _avisar("audio_fonte_do_controle_falhou", exc)
        return None
    for linha in (saida or "").splitlines():
        partes = linha.split("\t")
        if len(partes) < 2:
            continue
        nome = partes[1].strip()
        alvo = nome.lower()
        if alvo.endswith(".monitor") or alvo.startswith("alsa_output."):
            continue
        if any(marca in alvo for marca in _MARCAS_DA_FONTE_DO_CONTROLE):
            return nome
    return None


def _texto_do_pactl(argv: list[str]) -> str | None:
    """`pactl` com `LC_ALL=C`, sem shell. `None` em qualquer falha."""
    try:
        return _rodar_pelo_recuo(
            argv,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        _avisar("audio_fonte_do_uniq_falhou", exc)
        return None


def fonte_de_captura_do_uniq(
    uniq: str, *, mesa: list[str] | None = None
) -> str | None:
    """A fonte de captura DAQUELE controle — pela régua que já é dona da pergunta.

    MIC-DA-MESA-CHEIA-01 (20/08/2026). A `fonte_de_captura_do_controle` acima
    devolve a PRIMEIRA fonte que casar com a marca — e isso estava certo enquanto
    a premissa escrita no handler fosse verdade: *"há uma fonte de captura por
    máquina para o controle, não uma por controle"*.

    **A premissa caducou, e a própria casa já a tinha derrubado.** Com dois
    DualSense no cabo há DUAS placas de som, cada uma pendurada no seu
    dispositivo USB — foi exatamente por isso que `usb_pai_por_uniq` nasceu em
    15/08, quando mic e botão de saída sumiram de todos os controles assim que
    havia dois.

    ESTA FUNÇÃO ERA UMA SEGUNDA RÉGUA, E SÓ ENXERGAVA O CABO (03/09/2026)
    ---------------------------------------------------------------------
    A função resolvia por UMA regra — o dispositivo USB em que a placa pendura — e
    saía com `None` logo na primeira linha quando o controle não tinha
    dispositivo USB nenhum. **Um controle no RÁDIO nunca tem** (medido em
    15/08/2026: a placa segue o transporte), então a resposta por rádio era
    `None` SEMPRE, inclusive com a ponte de microfone de pé publicando
    ``hefesto_dualsense_bt_<hex6>`` — um nome que carrega os três últimos
    octetos do MAC daquele controle e portanto o identifica melhor que o
    dispositivo USB identifica os do fio.

    O estrago não era o `None`: era o que vem depois dele. O
    `mic.volume.set` cai na rota GLOBAL quando esta função não resolve
    (`daemon/ipc_handlers.py`, o ramo `if fonte is None`), e a rota global
    devolve a PRIMEIRA fonte de DualSense da lista. Numa mesa com um controle
    no fio e um no ar, o controle deslizante do card de quem está no RÁDIO
    mexia no microfone de quem está no CABO — que é, palavra por palavra, o
    defeito que esta sprint fechou para o cabo em 20/08.

    **O aparelho aceitava; quem recusava era o filtro.** A casa já tinha a
    resposta certa e com dono único:
    :func:`~hefesto_dualsense4unix.integrations.fontes_de_captura.escolher_fonte`,
    com as quatro regras (MAC inteiro no nome · rabo do MAC da ponte BT · mesmo
    dispositivo USB · um-para-um). O medidor de cada card, a luz do microfone e
    a eleição já perguntavam por lá; só este caminho tinha régua própria — e
    duas verdades sobre a mesma pergunta é como esta casa fabrica divergência
    silenciosa.

    A REGRA 4 DEPENDE DA MESA, E A MESA AGORA ENTRA (ONDA5-02-01, 06/09/2026)
    ------------------------------------------------------------------------
    Aqui estava escrito que a regra 4 ficava DESLIGADA de propósito, com
    ``uniqs_com_audio=[]``, *"porque aqui só se conhece UM `uniq`"*. A razão era
    boa e a premissa é que caiu: **quem chama SABE a mesa** — o daemon a lê por
    :func:`~hefesto_dualsense4unix.daemon.subsystems.recado_do_microfone.mesa_de_agora`,
    que é a única leitura de "tem card na tela" desta casa.

    O parâmetro `mesa` é o que faltava para a pergunta ser respondível:

    ``None``   ninguém perguntou à mesa (é o padrão, e mantém o comportamento
               de antes desta data, palavra por palavra: a regra 4 fica
               desligada e a função responde só pelas regras de identidade e
               pelo USB).
    ``[]``     a mesa está vazia. Não inventa dono: a regra 4 exige um único
               candidato e zero não é um.
    ``[u]``    **o caso barato, e o que esta mudança destrava**: uma source, um
               controle — só pode ser ele, com o :meth:`CasamentoUSB.veta`
               ainda podendo desmentir.

    O CENSO DE USB PASSA A COBRIR A MESA INTEIRA, e custa o mesmo: uma
    varredura de ``/sys`` por chamada, independentemente de quantos `uniq`
    entram (:func:`~integrations.usb_pai.usb_pai_por_uniq`). **O que ele muda
    NÃO é o veredito deste `uniq`** — `casar` e `veta` leem só a entrada dele —,
    e sim o mapa ficar completo para quem o inspecionar: dizer que mapear a mesa
    "é o que dá ao `veta` o que vetar" seria escrever aqui uma segunda verdade
    sobre o mesmo código, que é como esta casa fabrica divergência silenciosa.

    Devolve `None` quando não dá para saber de quem é a fonte — e `None` aqui é
    a resposta CERTA, não uma falha: mexer no microfone do controle errado é
    pior que não mexer em nenhum. **E desde 06/09/2026 quem chama NÃO cai mais
    para a rota global quando há endereço** (`daemon/ipc_handlers.py`, o
    `mic.volume.set`): cair para a primeira da lista era, palavra por palavra, o
    defeito relatado como bug.
    """
    from hefesto_dualsense4unix.integrations import porta_do_som
    from hefesto_dualsense4unix.integrations.fontes_de_captura import (
        CasamentoUSB,
        escolher_fonte,
        fontes_dualsense,
    )
    from hefesto_dualsense4unix.integrations.usb_pai import (
        usb_pai_por_no,
        usb_pai_por_uniq,
    )

    if not uniq:
        return None
    curta = _texto_do_pactl(["pactl", "list", "sources", "short"])
    if curta is None:
        return None
    fontes = fontes_dualsense(curta)
    if not fontes:
        return None
    candidatos = list(mesa) if mesa is not None else []
    if mesa is not None and uniq not in candidatos:
        candidatos.append(uniq)
    usb: CasamentoUSB | None = None
    sysfs = porta_do_som.sysfs_por_no("sources", _texto_do_pactl)
    if sysfs is not None:
        censo = usb_pai_por_uniq(candidatos or [uniq])
        usb = CasamentoUSB(
            por_uniq={u: pai for u, pai in censo.items() if pai},
            por_no=usb_pai_por_no(sysfs),
        )
    return escolher_fonte(fontes, uniq, candidatos, usb)


def definir_volume_da_captura(volume_pct: int, *, fonte: str | None) -> bool:
    """Põe o volume da captura do controle em `volume_pct` (0-100).

    MIC-VOLUME-01, pedido: uma barra para o volume
    do microfone real, sem importar se pelo BT ou pelo cabo, e o app
    sabe sozinho qual caminho usar. A "inteligência" mora
    em quem RESOLVE a fonte — `fonte_de_captura_do_uniq` quando há endereço,
    `fonte_de_captura_do_controle` quando não há.

    **`fonte` NÃO TEM PADRÃO, e a porta se fechou em 06/09/2026 (ONDA5-02-01).**
    Havia: sem `fonte`, esta função chamava `fonte_de_captura_do_controle()`
    sozinha e escrevia na PRIMEIRA placa de DualSense da lista. Nenhum chamador
    de `src/` usava esse caminho — os cinco já passavam `fonte=` —, e era isso
    que o tornava perigoso: uma porta fechada com a chave na fechadura, que
    entregaria o microfone do vizinho ao próximo que a empurrasse sem ler. É a
    mesma disciplina do `muted` do `mic.set`, que também não tem padrão: **quem
    chama declara em qual aparelho está escrevendo.**

    `None` continua sendo valor legítimo — é "não há fonte para este controle" —
    e a resposta a ele é `False`. O que deixou de existir é a OMISSÃO.

    **Isto NÃO é o mudo do firmware.** Não apaga a luz vermelha do microfone e
    não tira o botão físico do controle — quem faz as duas coisas é o
    `mic.set`. São camadas diferentes e não se substituem.

    Devolve False quando não há fonte (o caso do rádio sem ponte) ou quando o
    `pactl` falha. Nunca levanta: volume de microfone não derruba daemon.
    """
    alvo = fonte
    if not alvo:
        return False
    pct = max(0, min(100, int(volume_pct)))
    try:
        r = _rodar_pelo_recuo(
            ["pactl", "set-source-volume", alvo, f"{pct}%"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _avisar("audio_volume_captura_falhou", exc, fonte=alvo)
        return False
    if r.returncode != 0:
        logger.warning(
            "audio_volume_captura_recusado",
            fonte=alvo,
            rc=r.returncode,
            err=(r.stderr or "").strip()[:120],
        )
        return False
    return True


def volume_da_captura(*, fonte: str | None) -> int | None:
    """O volume ATUAL da captura do controle, em por cento, ou `None`."""
    alvo = fonte
    if not alvo:
        return None
    try:
        saida = _rodar_pelo_recuo(
            ["pactl", "get-source-volume", alvo],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    achado = re.search(r"(\d+)%", saida or "")
    return int(achado.group(1)) if achado else None


class PactlEmRecuoError(subprocess.SubprocessError):
    """O servidor de som está em recuo: a pergunta NÃO saiu."""


def _rodar_pelo_recuo(
    argv: list[str],
    *,
    timeout: float,
    env: dict[str, str],
    capture_output: bool = True,
    text: Literal[True] = True,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """``subprocess.run`` com o recuo do SERVIDOR na frente de todo ``pactl``."""
    if argv[:1] != ["pactl"]:
        return subprocess.run(
            argv, capture_output=capture_output, text=text, timeout=timeout,
            check=check, env=env,
        )
    from hefesto_dualsense4unix.integrations import retrato_do_som

    resposta = retrato_do_som.responder(argv)
    if isinstance(resposta, str):
        return subprocess.CompletedProcess(list(argv), 0, stdout=resposta, stderr="")
    if resposta is not None:
        raise PactlEmRecuoError(
            f"o retrato do servidor de som não sabe: {' '.join(argv[1:3])} não saiu"
        )
    from hefesto_dualsense4unix.integrations.dualsense_bt_audio import PACTL

    if PACTL.mudo():
        raise PactlEmRecuoError(
            f"pactl em recuo por {PACTL.espera_s:.0f} s: {' '.join(argv[1:3])} não saiu"
        )
    try:
        proc = subprocess.run(
            argv, capture_output=capture_output, text=text, timeout=timeout,
            check=check, env=env,
        )
    except subprocess.TimeoutExpired:
        PACTL.estourou()
        raise
    finally:
        retrato_do_som.escreveu(argv)
    if getattr(proc, "returncode", 0) == 0:
        PACTL.respondeu()
    return proc


def _avisar(evento: str, exc: BaseException, **campos: object) -> None:
    """A falha de verdade vira ``warning``; a pergunta que o recuo segurou, ``debug``."""
    if isinstance(exc, PactlEmRecuoError):
        logger.debug(evento, err=str(exc), **campos)
    else:
        logger.warning(evento, err=str(exc), **campos)


__all__ = [
    "SUBPROCESS_TIMEOUT_SEC",
    "PactlEmRecuoError",
    "definir_volume_da_captura",
    "fonte_de_captura_do_controle",
    "fonte_de_captura_do_uniq",
    "volume_da_captura",
]
