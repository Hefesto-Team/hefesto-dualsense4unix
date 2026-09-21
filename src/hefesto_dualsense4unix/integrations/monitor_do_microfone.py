"""O 🎙 ligado — você se ouve enquanto ele está verde.

**A ORDEM É DELA, 21/09/2026**, depois de usar o botão que gravava três
segundos:

    "O FUNCIONAMENTO DO BOTÃO MIC TÁ ZUADO. SE EU ATIVAR COM UM CLICK E ELE
     FICAR VERDE ELE TÁ ATIVADO E SEGUE ASSIM ATÉ EU DESATIVAR CLICANDO
     NOVAMENTE E ELE FICANDO CINZA. POR DEFAULT SEGUE DESLIGADO, ATÉ ALGUEM
     CLICAR E VER ISSO REFLETINDO LÁ."

O ato de 20/09 gravava três segundos e devolvia — uma resposta, e depois
silêncio. O que ela descreve é o **«Let's Check» do Discord**: enquanto ligado,
a voz volta continuamente, e ela ajusta os dois deslizantes OUVINDO o efeito.
Com três segundos por clique não há como ajustar nada: o som some antes de a
mão chegar ao trilho.

O MECANISMO, e por que não é `parec | paplay`
=============================================

`pw-loopback` liga a fonte ao destino **dentro do PipeWire**, sem copiar
amostra nenhuma por um cano de shell. Um par `parec | paplay` custa dois
processos, dois buffers e a soma das duas latências; o loopback custa um
processo e a latência que se pede. E ele é o mesmo mecanismo que o produto já
usa para a rota «no controle e na TV» — um vocabulário só para "ligar um nó a
outro".

O QUE ELE NÃO É
===============

**Não é o mudo.** O mudo do microfone é do PLÁSTICO (o botão do controle), e a
tela o reflete no selo «ATIVO»/«DESLIGADO» — decisão dela de 20/09. Este é o
RETORNO: com o microfone mudo não há o que ouvir, e quem recusa antes é o
gesto.

**Não é o volume nem o ganho.** Os dois deslizantes agem no NÓ, e o loopback lê
o nó depois deles — é justamente por isso que ela consegue ajustar ouvindo.
"""

from __future__ import annotations

import atexit
import shutil
import subprocess
import threading

import structlog

logger = structlog.get_logger(__name__)

__all__ = [
    "LATENCIA_MS",
    "alternar",
    "desligar",
    "desligar_todos",
    "esta_ligado",
    "ligados",
    "ligar",
]

#: A latência do retorno, em milissegundos.
#:
#: **50 ms é o mesmo número dos gravadores desta casa**, e ele não é gosto: sem
#: latência explícita o PipeWire escolhe um buffer generoso e a voz volta com
#: quase dois segundos de atraso — mordeu o microfone e a ponte do rádio, as
#: duas vezes com o mesmo sintoma ("o som sai, mas atrasado"). Aqui o atraso é
#: pior que em qualquer outro lugar: quem se ouve com meio segundo de atraso
#: não consegue falar.
LATENCIA_MS = 50

#: `{uniq: Popen}` dos retornos de pé. O dicionário é o DONO do estado, e é
#: por isso que ele é privado: quem pergunta usa :func:`esta_ligado`, que
#: confere se o processo ainda vive antes de responder. Um `bool` guardado à
#: parte mentiria no instante em que o `pw-loopback` morresse sozinho.
_VIVOS: dict[str, subprocess.Popen[bytes]] = {}
_TRAVA = threading.Lock()


def esta_ligado(uniq: str) -> bool:
    """O retorno deste controle está de pé AGORA?

    Pergunta ao PROCESSO, não a uma lembrança: `poll()` devolve `None` só
    enquanto ele vive. Se o `pw-loopback` morreu (o controle saiu, o servidor
    de som reiniciou), a resposta é `False` e a entrada sai do dicionário —
    senão o botão ficaria verde sobre um retorno que não existe mais, que é a
    família de defeito que esta casa persegue.
    """
    if not uniq:
        return False
    with _TRAVA:
        proc = _VIVOS.get(uniq)
        if proc is None:
            return False
        if proc.poll() is None:
            return True
        _VIVOS.pop(uniq, None)
        return False


def ligados() -> tuple[str, ...]:
    """Os `uniq` com retorno de pé, em ordem estável.

    Ordem alfabética porque a lista vai para a tela: uma que mudasse de ordem
    a cada tique faria dois estados iguais parecerem diferentes.
    """
    with _TRAVA:
        vivos = [u for u, p in _VIVOS.items() if p.poll() is None]
        mortos = [u for u in _VIVOS if u not in vivos]
        for u in mortos:
            _VIVOS.pop(u, None)
    return tuple(sorted(vivos))


def ligar(uniq: str, fonte: str, *, destino: str = "") -> bool:
    """Liga o retorno deste controle. `True` = de pé.

    :param fonte: o nó de captura daquele controle (`hefesto_mic_<hex6>`).
    :param destino: o sink de saída; vazio manda para a saída padrão, que é
        onde ela ouve o jogo — e é a única resposta útil a *"como eu soo"*.

    **LIGAR DUAS VEZES NÃO ABRE DOIS**: o segundo pedido responde `True` sobre
    o que já está de pé. Sem esta linha, dois cliques rápidos deixariam um
    `pw-loopback` órfão segurando o microfone dela — e foi assim que um `parec`
    ficou 39 minutos com o microfone aberto em 03/09.
    """
    if not uniq or not fonte:
        return False
    if esta_ligado(uniq):
        return True
    if shutil.which("pw-loopback") is None:
        logger.info("monitor_do_mic_sem_pw_loopback", uniq=uniq)
        return False
    argv = [
        "pw-loopback",
        "--capture", fonte,
        "--latency", str(LATENCIA_MS),
        "--channels", "1",
        "--channel-map", "[ MONO ]",
        "--name", f"hefesto-retorno-do-mic-{uniq}",
    ]
    if destino:
        argv += ["--playback", destino]
    try:
        proc = subprocess.Popen(  # argv fixo, sem shell
            argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.info("monitor_do_mic_nao_subiu", uniq=uniq, err=str(exc))
        return False
    with _TRAVA:
        _VIVOS[uniq] = proc
    logger.info("monitor_do_mic_ligado", uniq=uniq, fonte=fonte)
    return True


def desligar(uniq: str) -> bool:
    """Desliga o retorno deste controle. `True` = havia um e ele morreu.

    `kill` e não `terminate` com espera longa: é um loopback de áudio, não há
    estado a salvar, e um segundo de espera entre o clique e o silêncio é um
    segundo em que o botão mente.
    """
    with _TRAVA:
        proc = _VIVOS.pop(uniq, None)
    if proc is None:
        return False
    try:
        proc.kill()
        proc.wait(timeout=2)
    except (OSError, subprocess.SubprocessError):
        pass
    logger.info("monitor_do_mic_desligado", uniq=uniq)
    return True


def alternar(uniq: str, fonte: str, *, destino: str = "") -> bool:
    """Liga se estava desligado, desliga se estava ligado. Devolve o estado NOVO.

    **É O CONTRATO DO BOTÃO DELA**, e o retorno é o estado novo de propósito:
    quem chama pinta a luz com o que recebe, sem uma segunda consulta que
    poderia responder diferente no meio.
    """
    if esta_ligado(uniq):
        desligar(uniq)
        return False
    return ligar(uniq, fonte, destino=destino)


def desligar_todos() -> int:
    """Desliga todos os retornos e devolve quantos eram.

    **REGISTRADO NO `atexit` LOGO ABAIXO**, e isso não é zelo: um
    `pw-loopback` órfão continua lendo o microfone dela depois de a janela
    fechar, sem nada na tela que o diga. A interface morre; o processo, não.
    """
    quantos = 0
    for uniq in list(_VIVOS):
        if desligar(uniq):
            quantos += 1
    return quantos


atexit.register(desligar_todos)
