"""Testar o microfone como o Discord: fala três segundos e ouve de volta.

**A ORDEM É DELA, 20/09/2026, verbatim:**

    "deixa o slicer 2 dele na telka em contra partida aquele glifo antigo de mic
     que servia para ligar o microfone volta a tela mas ele passa a ter o efeito
     do testar microfone do discord, ele reflete os slicers que vão mostrar no
     jogo como o microfone é ouvido e após três segundos de fala capturada de
     audio ele reproduz na tela o seu som falado."

E ela esclareceu qual glifo, quando perguntei:

    "é esse mesmo que cala que eu tava falando"

E confirmou por que o botão de calar pode sair:

    "esse botão segue desativando o microfone, não precisamos dele mais na
     interface pq o botão do
     proprio  # noqa-acento: citação literal dela
     controle já o faz e ele reflete isso"

TRÊS SEGUNDOS DE FALA, NÃO DE RELÓGIO
=====================================

Ela escreveu *"três segundos de fala capturada"*, e a diferença é o ponto: um
contador de relógio devolveria três segundos de silêncio para quem demorou a
falar, e o teste responderia "seu microfone está mudo" sobre um microfone bom.

Então o contador anda só quando há voz — mas o que se GUARDA é o trecho
inteiro, com as pausas. É o que o Discord devolve, e é o que deixa a pessoa
reconhecer a própria fala.

O LIMIAR TEM DONO, e é o medidor de nível
=========================================

:mod:`~hefesto_dualsense4unix.integrations.nivel_do_microfone` já decide o que
é voz e o que é piso de ruído nesta casa, com histerese. Inventar um segundo
limiar aqui criaria a segunda grafia do mesmo fato — o defeito que esta casa
mata por regra. O que muda é só a unidade: lá o `parec` entrega o PICO em
float32; aqui ele entrega o PCM, e o pico de cada bloco sai do próprio PCM.

AS TRÊS TRAVAS QUE ESTA CASA JÁ PAGOU, e que este módulo herda
==============================================================

1. **`--latency-msec=50` explícito.** Sem ele o `parec` acumula e a voz chega
   dois segundos atrasada — mordeu o microfone e a ponte do rádio.
2. **`stdout=PIPE`, nunca `/dev/null`.** Medido em 03/09: com o cano o `parec`
   morre junto com o pai; com `/dev/null` ele sobrevive órfão segurando o
   microfone dela aberto, e um ficou 39 minutos de pé.
3. **`PR_SET_PDEATHSIG`.** Um daemon morto por SIGKILL não deixa gravador vivo.
"""

from __future__ import annotations

import array
import contextlib
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

__all__ = [
    "BLOCO_MS",
    "FALA_ALVO_S",
    "TAXA",
    "TETO_S",
    "Gravacao",
    "argv_do_gravador",
    "argv_do_reprodutor",
    "fonte_do_controle",
    "gravar_ate_falar",
    "pico_do_bloco",
    "testar_e_devolver",
]

#: 48 kHz mono, s16le — a taxa do microfone do DualSense nos dois transportes
#: (a ponte do rádio entrega Opus mono 48 kHz; o cabo, a placa USB do controle).
TAXA = 48_000
CANAIS = 1
BYTES_POR_AMOSTRA = 2

#: 40 ms por bloco: o mesmo passo do medidor de nível, para que a histerese
#: dele valha aqui sem reajuste.
BLOCO_MS = 40

#: Quanto de FALA basta. Ela pediu três segundos.
FALA_ALVO_S = 3.0

#: O TETO, e ele é de segurança e não de desenho: sem voz nenhuma o laço
#: pararia só quando o processo morresse, e um teste que nunca termina segura o
#: microfone dela aberto. Quinze segundos é o dobro do que uma pessoa leva para
#: dizer uma frase inteira.
TETO_S = 15.0


class Gravacao:
    """O que o teste ouviu, e por que parou.

    ``pcm`` vazio com ``motivo="sem-voz"`` é uma resposta legítima: o microfone
    abriu e ninguém falou. Não é erro, e a tela diz isso de outro jeito.
    """

    __slots__ = ("fala_s", "motivo", "pcm", "pico_maximo", "total_s")

    def __init__(
        self,
        *,
        pcm: bytes,
        fala_s: float,
        total_s: float,
        pico_maximo: float,
        motivo: str,
    ) -> None:
        self.pcm = pcm
        self.fala_s = fala_s
        self.total_s = total_s
        self.pico_maximo = pico_maximo
        self.motivo = motivo

    def __repr__(self) -> str:  # pragma: no cover - diagnóstico
        return (
            f"Gravacao({len(self.pcm)}B, fala={self.fala_s:.1f}s, "
            f"total={self.total_s:.1f}s, pico={self.pico_maximo:.3f}, "
            f"motivo={self.motivo!r})"
        )


def argv_do_gravador(fonte: str) -> list[str]:
    """O ``parec`` que entrega o PCM desta fonte.

    ``--latency-msec=50`` é EXPLÍCITO por regra da casa: sem ele o servidor
    escolhe um buffer grande e a voz chega dois segundos depois de dita.
    """
    return [
        "parec",
        f"--device={fonte}",
        f"--rate={TAXA}",
        f"--channels={CANAIS}",
        "--format=s16le",
        "--raw",
        "--latency-msec=50",
    ]


def argv_do_reprodutor(destino: str = "") -> list[str]:
    """O ``paplay`` que devolve o PCM.

    Sem ``--device``, toca na SAÍDA PADRÃO — que é onde ela ouve o jogo, e
    portanto onde a pergunta *"como eu sou ouvida?"* se responde. Mandar para o
    alto-falante do controle responderia outra pergunta.

    **E um ``--device`` inexistente sai com ZERO e toca no padrão mesmo assim**
    (medido nesta casa, `a02_controles.py`), então passar destino errado não dá
    erro: dá a ilusão de ter tocado onde não tocou.
    """
    argv = [
        "paplay",
        f"--rate={TAXA}",
        f"--channels={CANAIS}",
        "--format=s16le",
        "--raw",
        "--latency-msec=50",
    ]
    if destino:
        argv.append(f"--device={destino}")
    return argv


def pico_do_bloco(pcm: bytes) -> float:
    """O pico de um bloco s16le, de 0.0 a 1.0.

    Bloco vazio devolve 0.0 — não há pico em nada, e isso não é silêncio
    medido: é ausência de medição. Quem chama não distingue os dois aqui
    porque, para o contador de fala, os dois valem o mesmo: não conta.
    """
    if not pcm:
        return 0.0
    amostras = array.array("h")
    amostras.frombytes(pcm[: len(pcm) - (len(pcm) % 2)])
    if not amostras:
        return 0.0
    return max(abs(a) for a in amostras) / 32768.0


def _morrer_com_o_pai() -> None:  # pragma: no cover - só roda no filho
    with contextlib.suppress(Exception):
        import ctypes

        ctypes.CDLL("libc.so.6", use_errno=True).prctl(1, 9, 0, 0, 0)


def gravar_ate_falar(
    fonte: str,
    *,
    limiar: float = 0.02,
    fala_alvo_s: float = FALA_ALVO_S,
    teto_s: float = TETO_S,
    abrir: Callable[[str], Any] | None = None,
    relogio: Callable[[], float] | None = None,
) -> Gravacao | None:
    """Grava até juntar ``fala_alvo_s`` de VOZ, e devolve o trecho inteiro.

    Devolve ``None`` quando não há ``parec`` na máquina ou o processo não
    subiu. **``None`` é "não sei"**, e é diferente de uma ``Gravacao`` vazia,
    que é "ouvi, e não havia voz". A tela precisa dos dois para não dizer
    "microfone mudo" quando o que faltou foi o programa.

    ``abrir`` e ``relogio`` existem para a régua: sem eles esta função só se
    mede com um microfone de verdade na mesa dela, e a suíte não pode depender
    disso.
    """
    lancar = abrir or _abrir_parec
    agora = relogio or time.monotonic

    proc = lancar(fonte)
    if proc is None:
        return None

    saida = getattr(proc, "stdout", None)
    if saida is None:
        with contextlib.suppress(Exception):
            proc.kill()
        return None

    bloco_bytes = int(TAXA * CANAIS * BYTES_POR_AMOSTRA * BLOCO_MS / 1000)
    bloco_s = BLOCO_MS / 1000.0
    pedacos: list[bytes] = []
    fala_s = 0.0
    total_s = 0.0
    pico_maximo = 0.0
    motivo = "sem-voz"
    comeco = agora()

    try:
        while True:
            if agora() - comeco >= teto_s:
                motivo = "teto"
                break
            dado = saida.read(bloco_bytes)
            if not dado:
                motivo = "fonte-fechou"
                break
            pedacos.append(dado)
            total_s += bloco_s
            pico = pico_do_bloco(dado)
            pico_maximo = max(pico_maximo, pico)
            # SÓ A VOZ ANDA O CONTADOR, e é o que ela pediu: "três segundos de
            # fala capturada". O silêncio entre palavras fica na gravação, mas
            # não encurta a espera.
            if pico >= limiar:
                fala_s += bloco_s
            if fala_s >= fala_alvo_s:
                motivo = "falou"
                break
    finally:
        with contextlib.suppress(Exception):
            proc.kill()
        with contextlib.suppress(Exception):
            proc.wait(timeout=2)

    return Gravacao(
        pcm=b"".join(pedacos) if motivo == "falou" else b"",
        fala_s=fala_s,
        total_s=total_s,
        pico_maximo=pico_maximo,
        motivo=motivo,
    )


def _abrir_parec(fonte: str) -> subprocess.Popen[bytes] | None:
    if shutil.which("parec") is None:
        logger.debug("teste_do_mic_sem_parec", fonte=fonte)
        return None
    ambiente = dict(os.environ)
    # O `pactl` desta casa TRADUZ sem `LC_ALL=C`, e um leitor cego responde
    # "não há" sobre aparelho de pé. Já custou duas vezes.
    ambiente["LC_ALL"] = "C"
    try:
        return subprocess.Popen(  # argv fixo, sem shell
            argv_do_gravador(fonte),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=ambiente,
            bufsize=0,
            preexec_fn=_morrer_com_o_pai,
        )
    except (OSError, ValueError) as erro:
        logger.warning("teste_do_mic_nao_abriu", fonte=fonte, err=str(erro))
        return None


def fonte_do_controle(uniq: str, *, saida_pactl: str = "") -> str | None:
    """O nó de captura DAQUELE controle — ``None`` quando não dá para saber.

    Não reimplementa a escolha: delega a
    :func:`~hefesto_dualsense4unix.integrations.fontes_de_captura.escolher_fonte`,
    que é a dona das cinco regras e já sabe que o nó com identidade
    (``hefesto_mic_<hex6>``) vence quando existe. Uma segunda escolha aqui seria
    a segunda grafia do mesmo fato.

    ``None`` é "não sei", e quem chama não deve tratá-lo como "não há
    microfone": sem o servidor de som, sem `pactl` ou sem o controle no ar, a
    pergunta simplesmente não tem resposta.
    """
    from hefesto_dualsense4unix.integrations.fontes_de_captura import (
        escolher_fonte,
        fontes_dualsense,
    )

    saida = saida_pactl
    if not saida:
        if shutil.which("pactl") is None:
            return None
        ambiente = dict(os.environ)
        # SEM `LC_ALL=C` O `pactl` TRADUZ, e o leitor fica cego sobre aparelho
        # de pé. Já custou duas vezes nesta casa.
        ambiente["LC_ALL"] = "C"
        try:
            saida = subprocess.run(  # argv fixo, sem shell
                ["pactl", "list", "sources"],
                capture_output=True,
                text=True,
                timeout=5,
                env=ambiente,
                check=False,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return None
    if not saida:
        return None
    return escolher_fonte(fontes_dualsense(saida), str(uniq), [str(uniq)])


def testar_e_devolver(
    uniq: str,
    *,
    limiar: float = 0.02,
    destino: str = "",
) -> Gravacao | None:
    """O ato inteiro: acha a fonte, grava até três segundos de fala, devolve.

    **É O QUE ELA PEDIU, e o efeito é o do Discord:** a pessoa fala, e ouve de
    volta exatamente como o jogo a ouve — com o volume e o ganho dos dois
    deslizantes já aplicados, porque eles agem no NÓ e não neste código.

    Devolve ``None`` quando não se achou a fonte ou o gravador não subiu; uma
    ``Gravacao`` com ``pcm`` vazio quando ouviu e não havia voz. **Só reproduz
    quando há o que reproduzir** — tocar silêncio responderia "seu microfone
    está bom" sobre um microfone mudo.

    **ESTA FUNÇÃO DEMORA ATÉ 15 SEGUNDOS, e por isso NUNCA roda no fio do
    GTK.** Uma leitura síncrona no tique segura o laço inteiro da janela — é o
    defeito de 03/09 que fez a interface dar 19 voltas em 40 segundos onde devia
    dar 117. Quem a chama põe num fio próprio.
    """
    fonte = fonte_do_controle(uniq)
    if not fonte:
        return None
    gravado = gravar_ate_falar(fonte, limiar=limiar)
    if gravado is None or not gravado.pcm:
        return gravado
    if shutil.which("paplay") is None:
        logger.info("teste_do_mic_sem_paplay", uniq=uniq)
        return gravado
    ambiente = dict(os.environ)
    ambiente["LC_ALL"] = "C"
    try:
        subprocess.run(  # argv fixo, sem shell
            argv_do_reprodutor(destino),
            input=gravado.pcm,
            capture_output=True,
            timeout=30,
            env=ambiente,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as erro:
        logger.warning("teste_do_mic_nao_reproduziu", uniq=uniq, err=str(erro))
    return gravado
