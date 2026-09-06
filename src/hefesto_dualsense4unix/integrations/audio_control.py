"""Controle de mute do microfone padrão do sistema via wpctl ou pactl.

Auto-detecta o backend disponivel (wpctl para PipeWire/WirePlumber,
pactl para PulseAudio legado). Nunca levanta excecao: falhas de
subprocess viram warning + retorno do último estado conhecido.

Regras:
- Nunca usa shell=True (invariante do projeto).
- Debounce 200ms com clock injetavel para testes.
- Logging via structlog (get_logger).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from typing import Literal

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

DEBOUNCE_SEC = 0.2
SUBPROCESS_TIMEOUT_SEC = 2.0
Backend = Literal["wpctl", "pactl", "none"]


class AudioControl:
    """Controla mute do microfone padrão do sistema via wpctl ou pactl.

    Auto-detecta backend no primeiro uso. Não levanta: falhas viram
    warning + retorno do último estado conhecido.

    Args:
        clock: função que retorna tempo monotonic em segundos. Injetavel
               para testes. Default: time.monotonic.
    """

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock: Callable[[], float] = clock or time.monotonic
        self._backend: Backend | None = None
        # Inicializado suficientemente negativo para que a primeira chamada
        # nunca seja bloqueada pelo debounce, independente do clock injetado.
        self._last_call_at: float = -(DEBOUNCE_SEC + 1.0)
        self._last_known_muted: bool = False
        self._warned_no_backend: bool = False

    # ------------------------------------------------------------------
    # Deteccao de backend
    # ------------------------------------------------------------------

    def _detect_backend(self) -> Backend:
        """Detecta qual utilitario de audio esta disponivel no PATH."""
        if shutil.which("wpctl"):
            return "wpctl"
        if shutil.which("pactl"):
            return "pactl"
        return "none"

    def _ensure_backend(self) -> Backend:
        """Detecta e cacheia o backend na primeira chamada."""
        if self._backend is None:
            self._backend = self._detect_backend()
            logger.info("audio_backend_detectado", backend=self._backend)
        return self._backend

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------

    def fonte_padrao_e_o_controle(self) -> bool:
        """True quando o microfone padrão do sistema É o do DualSense.

        BT-E-VPAD-01, defeito 1. **Medido em 01/08/2026**: com o controle no
        Bluetooth, `pactl list short cards | grep -i dualsense` devolve ZERO —
        no BT o DualSense **não tem placa de som nenhuma**. O áudio vai dentro
        dos reports HID e depende da ponte deste projeto, que é opt-in.

        Sem esta pergunta, o botão do microfone do controle alternava o mudo
        da FONTE PADRÃO, que no Bluetooth é outra coisa: nesta máquina, o
        microfone da placa-mãe. O log de três toques dela mostra a assinatura
        do defeito — sempre o mesmo resultado, porque não era o microfone do
        controle que estava sendo alternado:

            20:15:54  mic_hotkey_toggle  muted=True
            20:16:31  mic_hotkey_toggle  muted=True
            20:16:43  mic_hotkey_toggle  muted=True

        A comparação é por SUBSTRING do nome da fonte padrão, e não por
        enumeração de placas: é uma pergunta só, na cadência de um toque de
        botão, e o nome do node do PipeWire para o controle carrega
        "DualSense" em qualquer um dos dois backends.

        Em caso de dúvida devolve **False** — e o chamador não mexe em nada.
        É a resposta segura: não fazer nada é sempre melhor que mutar o
        microfone errado.
        """
        backend = self._ensure_backend()
        try:
            if backend == "wpctl":
                # O `wpctl inspect` do source padrão traz `node.name` e
                # `node.description`; o do controle carrega "DualSense".
                saida = self._run(
                    ["wpctl", "inspect", "@DEFAULT_AUDIO_SOURCE@"]
                ).stdout
            elif backend == "pactl":
                saida = self._run(["pactl", "get-default-source"]).stdout
            else:
                return False
        except Exception as exc:
            logger.warning("audio_fonte_padrao_falhou", err=str(exc))
            return False
        return "dualsense" in (saida or "").lower()

    def toggle_default_source_mute(self) -> bool:
        """Alterna mute do microfone padrão do sistema.

        Aplica debounce de 200ms: chamadas consecutivas dentro desse
        intervalo ignoram o subprocess e retornam o último estado.

        Returns:
            True se o microfone agora esta mutado; False se esta ativo.
        """
        now = self._clock()
        if (now - self._last_call_at) < DEBOUNCE_SEC:
            logger.debug("audio_toggle_debounced")
            return self._last_known_muted
        self._last_call_at = now

        backend = self._ensure_backend()
        if backend == "none":
            if not self._warned_no_backend:
                logger.warning("audio_backend_indisponivel")
                self._warned_no_backend = True
            return False

        try:
            if backend == "wpctl":
                self._run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"])
                self._last_known_muted = self._query_wpctl_muted()
            else:
                self._run(["pactl", "set-source-mute", "@DEFAULT_SOURCE@", "toggle"])
                self._last_known_muted = self._query_pactl_muted()
        except Exception as exc:
            logger.warning("audio_toggle_falhou", backend=backend, err=str(exc))
        return self._last_known_muted

    # ------------------------------------------------------------------
    # Métodos internos de subprocess
    # ------------------------------------------------------------------

    def _run(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        """Executa comando como lista de args, sem shell=True — e em `LC_ALL=C`.

        **O `LC_ALL=C` NÃO É ZELO, e a ausência dele era um instrumento que
        mentia.** Medido na máquina dela em 06/09/2026, com o `LANG=pt_BR.UTF-8`
        que ela usa::

            pactl set-source-mute <nó> 1 ; pactl get-source-mute <nó>
                sem LC_ALL  ->  Mute: sim
                com LC_ALL=C ->  Mute: yes
            desmutado, sem LC_ALL                ->  Mute: não

        :meth:`_query_pactl_muted` responde ``"yes" in saida.lower()``. Nem
        ``sim`` nem ``não`` contêm ``yes``, então nesta máquina a leitura
        devolvia **False sempre** — e :meth:`toggle_default_source_mute`
        afirmava *"o microfone está no ar"* tivesse ele mutado ou não. O
        aparelho obedecia; quem mentia era a leitura de volta.

        **É a MESMA causa que este arquivo já registra duas vezes** —
        `fonte_de_captura_do_controle` (15/08/2026, *"já respondeu 'nenhum
        controle com placa de áudio' sobre um sistema que tinha um"*) e
        `_texto_do_pactl`. As duas ganharam o ambiente; esta ficou de fora, que
        é a forma desta casa de deixar meia cura viva: **quando a cura conhece a
        causa, ela cobre TODOS os chamadores.**

        DÍVIDA DECLARADA, e ela não é desculpa: hoje NENHUM caminho de `src/`
        chama `toggle_default_source_mute` — o botão do microfone deixou de
        passar por ele em 01/09/2026, e há régua que reprova se ele voltar
        (`test_bt_e_vpad_01.py`). O defeito era latente, não vivo; o que o torna
        digno de conserto é que a próxima pessoa a reabrir aquela porta herdaria
        uma leitura que responde sobre o idioma do shell, não sobre o aparelho.
        """
        return subprocess.run(
            argv,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )

    def _query_wpctl_muted(self) -> bool:
        """Consulta estado de mute via wpctl get-volume.

        O wpctl inclui '[MUTED]' na saida quando o source esta mutado.
        """
        result = self._run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"])
        return "[MUTED]" in (result.stdout or "")

    def _query_pactl_muted(self) -> bool:
        """Consulta estado de mute via pactl get-source-mute.

        A saida padrão e 'Mute: yes' ou 'Mute: no'.
        """
        result = self._run(["pactl", "get-source-mute", "@DEFAULT_SOURCE@"])
        return "yes" in (result.stdout or "").lower()


#: Como se reconhece a fonte de captura DO CONTROLE entre as do sistema.
#:
#: São várias marcas porque são dois caminhos E dois vocabulários, e é
#: justamente isso que o controle deslizante do microfone existe para esconder
#: dela (MIC-VOLUME-01):
#:
#: - no CABO o DualSense é uma placa de áudio USB de verdade, e o source se
#:   chama ``alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_
#:   Controller-00.analog-stereo`` — **medido em 17/08/2026, com o controle no
#:   cabo**. Ele TEM a palavra "DualSense";
#: - no RÁDIO ele **não expõe placa nenhuma** (medido no mesmo dia: `pactl
#:   list cards` traz só as duas placas da máquina). O áudio trafega como Opus
#:   tunelado em HID, e quem publica um source é a ponte de
#:   `integrations/dualsense_bt_audio.py`, com o prefixo `hefesto_dualsense`.
#:
#: **UMA marca basta, e chegar a essa conclusão custou duas correções.**
#:
#: A lista teve três nomes. Os outros dois saíram, e os motivos são a mesma
#: lição por dois caminhos:
#:
#: - `hefesto_dualsense` saiu quando o teste da mordida mostrou que arrancá-lo
#:   não reprovava nada: o source da ponte se chama `hefesto_dualsense_bt_<mac>`
#:   e já casa com `dualsense`;
#: - `sony_interactive_entertainment` saiu em 17/08, quando o source do cabo foi
#:   lido AO VIVO pela primeira vez. Eu o havia posto por INFERÊNCIA, escrevendo
#:   que o nome no cabo "não teria a palavra DualSense". **Tem.** A medição
#:   derrubou a inferência, e a marca que ela justificava caiu junto.
#:
#: Fica registrado porque é a regra que este dia produziu duas vezes: **marca
#: redundante é ruído que finge cobertura** — e uma marca posta por palpite,
#: mesmo prudente, é dívida até alguém medir.
_MARCAS_DA_FONTE_DO_CONTROLE: tuple[str, ...] = ("dualsense",)


def fonte_de_captura_do_controle() -> str | None:
    """Nome do source de captura do DualSense, ou `None` se não houver.

    `None` não é erro: por Bluetooth, sem a ponte de áudio de pé, **não existe
    fonte** — e é isso que a interface precisa saber para deixar o controle
    deslizante insensível em vez de aceitar um gesto que não faria nada.

    Read-only: só lista. Nunca escreve.
    """
    try:
        saida = subprocess.run(
            ["pactl", "list", "short", "sources"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False,
            # `pactl` TRADUZ a saída, e uma versão desta função em português
            # já respondeu "nenhum controle com placa de áudio" sobre um
            # sistema que tinha um — a afirmação era sobre o idioma do shell,
            # não sobre o aparelho (medido em 15/08/2026).
            env={**os.environ, "LC_ALL": "C"},
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("audio_fonte_do_controle_falhou", err=str(exc))
        return None
    for linha in (saida or "").splitlines():
        partes = linha.split("\t")
        if len(partes) < 2:
            continue
        nome = partes[1].strip()
        alvo = nome.lower()
        # O MONITOR não é microfone — e esta linha foi paga com um defeito
        # real. Medido em 16/08/2026 com o controle no cabo: a primeira versão
        # desta função devolveu
        # `alsa_output.usb-…DualSense…analog-surround-40.monitor`, que é o ECO
        # DA SAÍDA do controle, não a captura. Todo sink do PulseAudio ganha um
        # source `.monitor` de brinde, e ele casa com qualquer marca que o sink
        # casaria. Um controle deslizante de MICROFONE mexendo no monitor do
        # ALTO-FALANTE é a tela fazendo outra coisa do que promete.
        if alvo.endswith(".monitor") or alvo.startswith("alsa_output."):
            continue
        if any(marca in alvo for marca in _MARCAS_DA_FONTE_DO_CONTROLE):
            return nome
    return None


def _texto_do_pactl(argv: list[str]) -> str | None:
    """`pactl` com `LC_ALL=C`, sem shell. `None` em qualquer falha.

    O `LC_ALL=C` não é zelo: o `pactl` desta máquina TRADUZ a saída, e uma
    versão desta rotina em português já respondeu "nenhum controle com placa de
    áudio" sobre um sistema que tinha uma (medido em 15/08/2026).
    """
    try:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        ).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("audio_fonte_do_uniq_falhou", err=str(exc))
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
    Ela resolvia por UMA regra — o dispositivo USB em que a placa pendura — e
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
    defeito que ela chamou de bug.
    """
    from hefesto_dualsense4unix.integrations.fontes_de_captura import (
        CasamentoUSB,
        escolher_fonte,
        fontes_dualsense,
    )
    from hefesto_dualsense4unix.integrations.usb_pai import (
        nos_e_sysfs,
        usb_pai_por_no,
        usb_pai_por_uniq,
    )

    if not uniq:
        return None
    curta = _texto_do_pactl(["pactl", "list", "sources", "short"])
    if curta is None:
        return None
    # O dono do "quais destas são de DualSense" é o mesmo de sempre: ele
    # descarta o `.monitor` (o ECO DA SAÍDA, que já custou um defeito real em
    # 16/08) e reconhece tanto a placa do cabo quanto a source da ponte.
    fontes = fontes_dualsense(curta)
    if not fontes:
        return None
    # A saída LONGA só serve ao casamento por USB — e é o único passo que o
    # controle no rádio não tem. Sem ela, as regras de IDENTIDADE continuam
    # valendo, e são justamente as que respondem por rádio.
    # A MESA, COMO ELA CHEGOU. `None` é "não perguntei" e vira `[]` para o
    # `escolher_fonte`, que é o comportamento de antes desta data; uma mesa
    # conhecida entra inteira, e o `uniq` de quem pergunta entra junto mesmo
    # que o backend não o tenha listado — perguntar pelo microfone de um
    # controle e não pô-lo entre os candidatos seria a régua se contradizendo.
    candidatos = list(mesa) if mesa is not None else []
    if mesa is not None and uniq not in candidatos:
        candidatos.append(uniq)
    usb: CasamentoUSB | None = None
    longa = _texto_do_pactl(["pactl", "list", "sources"])
    if longa is not None:
        censo = usb_pai_por_uniq(candidatos or [uniq])
        usb = CasamentoUSB(
            por_uniq={u: pai for u, pai in censo.items() if pai},
            por_no=usb_pai_por_no(nos_e_sysfs(longa)),
        )
    return escolher_fonte(fontes, uniq, candidatos, usb)


def definir_volume_da_captura(volume_pct: int, *, fonte: str | None) -> bool:
    """Põe o volume da captura do controle em `volume_pct` (0-100).

    MIC-VOLUME-01, pedido dela: *"um slicer de microfone pra definir o volume
    do microfone real (independente de saber se tá via bt ou via cabo), o app
    deve ser inteligente pra saber qual caminho usar"*. A "inteligência" mora
    em quem RESOLVE a fonte — `fonte_de_captura_do_uniq` quando há endereço,
    `fonte_de_captura_do_controle` quando não há.

    **`fonte` NÃO TEM PADRÃO, e a porta se fechou em 06/09/2026 (ONDA5-02-01).**
    Ela tinha: sem `fonte`, esta função chamava `fonte_de_captura_do_controle()`
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
        r = subprocess.run(
            ["pactl", "set-source-volume", alvo, f"{pct}%"],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("audio_volume_captura_falhou", err=str(exc), fonte=alvo)
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
    """O volume ATUAL da captura do controle, em por cento, ou `None`.

    Lê em vez de lembrar: guardar o valor mandado como se fosse leitura é o
    hábito que já fez esta tela parecer mentirosa quando ela nunca mentiu.

    **`fonte` NÃO TEM PADRÃO** — a mesma porta que `definir_volume_da_captura`
    fechou em 06/09/2026, e pela mesma razão, com um agravante próprio: uma
    LEITURA que cai na primeira fonte da lista devolve o número do microfone do
    vizinho, e quem o recebe o pinta no card certo. Mentir na leitura é pior que
    errar na escrita, porque não deixa rastro no aparelho.
    """
    alvo = fonte
    if not alvo:
        return None
    try:
        saida = subprocess.run(
            ["pactl", "get-source-volume", alvo],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SEC,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    # "Volume: front-left: 32768 /  50% / -18,06 dB, ..." — o primeiro por
    # cento basta; os canais do nosso source são mono ou espelhados.
    achado = re.search(r"(\d+)%", saida or "")
    return int(achado.group(1)) if achado else None


__all__ = [
    "DEBOUNCE_SEC",
    "SUBPROCESS_TIMEOUT_SEC",
    "AudioControl",
    "Backend",
    "definir_volume_da_captura",
    "fonte_de_captura_do_controle",
    "fonte_de_captura_do_uniq",
    "volume_da_captura",
]
