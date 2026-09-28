"""O servidor de som AVISA, e até hoje ninguém escutava.

O-SOM-DO-SISTEMA-E-O-DA-TELA-01 (21/09/2026). Pedido dela, com o painel de som
do COSMIC aberto ao lado da janela do Hefesto:

    *"outra coisa que precisamos ter é sincronia com os canais de saida de som
    e entrada de som do sistema operacional. isso é importante."*
    <!-- noqa-acento: citação literal dela -->

**O QUE ESTAVA MEDIDO, e é o defeito inteiro:** o produto só ESCREVIA. Uma
varredura em `src/` não achava um `pactl subscribe` nem um `pw-mon`; havia
escrita (`set-default-sink`, `set-default-source`) e leitura SOB DEMANDA
(`get-default-sink`). Quando ela trocava a saída no painel do sistema, nada no
Hefesto ficava sabendo — a tela só descobria no tique que por acaso
perguntasse, e a fileira do som continuava acesa no que estava.

**O CANAL EXISTE E RESPONDE.** Provado em 21/09/2026 sem tocar no som dela: um
`pactl subscribe` aberto, um null-sink criado e removido, e as quatro linhas
chegaram na hora (`new`/`remove` de `module` e de `sink`).

**E UM FATO QUE DESENHA ESTE MÓDULO: reescrever o MESMO valor não emite
evento.** Medido: `pactl set-default-source <o que já era>` passou sem uma
linha no `subscribe`. Quem escuta não vê as próprias escritas idempotentes, e
por isso **não há eco a filtrar** — o ouvinte pode ser burro.

**ELE NÃO DECIDE NADA, E ISSO É CONTRATO.** Este laço lê, compara e PUBLICA.
Quem elege microfone continua sendo `integrations/eleicao_de_microfone`, que é
o dono, e escrever um `set-default-source` daqui criaria o segundo escritor que
a eleição existe para acabar.

**E ELE PASSOU A SER O ÚNICO OUVIDO DO RETRATO** —
O-SERVIDOR-DE-SOM-TEM-UM-LEITOR-SO-01 (28/09/2026). Até esta data ele só
publicava a saída e a entrada padrão, e o daemon perguntava todo o resto ao
servidor por conta própria, 22 a 23 vezes por segundo. Agora ele escuta todo
evento de nó, de fluxo, de módulo e de servidor, junta cada rajada em
:data:`RAJADA_S` e manda o `integrations/retrato_do_som` reler SÓ o tipo que
mudou. Sem evento, zero `pactl`. O padrão publicado sai do retrato, sem
pergunta própria.

**A LÍNGUA FICA PRESA EM C.** O `pactl` desta casa responde em português
(`LC_ALL` do sistema), e um leitor que dependa do idioma da máquina já
respondeu *"não há"* sobre aparelho de pé duas vezes.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.integrations import retrato_do_som
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Quanto se espera antes de tentar de novo quando o `pactl` morre. O servidor
#: de som reinicia (o `systemctl --user restart pipewire` do doctor faz isso), e
#: um ouvinte que desistisse na primeira queda ficaria mudo pelo resto da
#: sessão — que é exatamente o defeito que ele vem curar.
ESPERA_PARA_RELIGAR_S: float = 3.0

#: Quanto o ouvinte junta eventos antes de mandar reler. Um jogo que abre
#: emite uma rajada — o fluxo nasce, muda, o nó acorda — e reler a cada linha
#: faria da rajada a mesma chuva de `pactl` que esta sprint veio curar.
RAJADA_S: float = 0.05

#: As linhas do `subscribe` que interessam. O `subscribe` fala de tudo —
#: clientes que abrem e fecham, streams de cada app — e reagir a tudo faria uma
#: leitura de `pactl info` por frame de áudio de qualquer programa.
#:
#: `server` é a que carrega a troca de padrão; `sink`/`source` são o nó que
#: nasce e morre, que é a outra metade da queixa dela (o nó do controle some e
#: a tela fica acesa no que estava).
EVENTOS_QUE_IMPORTAM = ("server", "sink", "source")

#: Os tipos do retrato cuja releitura pode mudar o padrão publicado: o
#: `server` diz quem é o padrão, e as listas de nós dizem o nome de gente dele.
_TIPOS_DO_PADRAO = frozenset(
    retrato_do_som.TIPO_DO_EVENTO[e] for e in EVENTOS_QUE_IMPORTAM)


@dataclass(frozen=True)
class SomDoSistema:
    """A saída e a entrada padrão do sistema, como o servidor as diz.

    DOIS PARES, e o segundo é o que ela lê. `saida`/`entrada` são os nomes
    CRUS dos nós (`alsa_output.pci-…hdmi-stereo`), que é o que o produto usa
    para comparar; `saida_nome`/`entrada_nome` são as `Description` do próprio
    servidor — **as mesmas palavras que o painel de som do COSMIC mostra a
    ela**, e é isso que faz a tela do Hefesto e o painel do sistema falarem a
    mesma língua, que é o pedido inteiro.
    """

    saida: str = ""
    entrada: str = ""
    saida_nome: str = ""
    entrada_nome: str = ""

    def como_dicionario(self) -> dict[str, str]:
        return {"saida": self.saida, "entrada": self.entrada,
                "saida_nome": self.saida_nome, "entrada_nome": self.entrada_nome}


def _ambiente() -> dict[str, str]:
    """O ambiente das leituras, com o idioma preso em C. Ver o cabeçalho."""
    return {**os.environ, "LC_ALL": "C", "LANG": "C"}


async def ler_o_padrao() -> SomDoSistema:
    """A saída e a entrada padrão, com os nomes de gente — pelo RETRATO, sem `pactl`.

    Até 28/09/2026 esta função fazia quatro perguntas próprias ao servidor
    (`get-default-sink`, `get-default-source`, `list sinks`, `list sources`) a
    cada evento. O retrato já sabe as quatro respostas, relidas pelo mesmo
    evento que acordou quem pergunta.

    Retrato sem resposta devolve os campos vazios — *"não sei"*, que é o que a
    tela já sabe pintar.
    """
    retrato = retrato_do_som.RETRATO
    saida = retrato.padrao("sink") or ""
    entrada = retrato.padrao("source") or ""
    descricoes = retrato.descricoes()
    return SomDoSistema(
        saida=saida, entrada=entrada,
        saida_nome=descricoes.get(saida, ""),
        entrada_nome=descricoes.get(entrada, ""))


def descricoes_da_lista(bruto: str) -> dict[str, str]:
    """`{nome cru: Description}` de uma saída de `pactl list sinks|sources`.

    FUNÇÃO PURA, e por isso ela é o oráculo: a régua lhe dá a saída medida na
    máquina dela e confere o par, sem servidor de som nenhum.

    **O FORMATO LONGO É O ÚNICO QUE TRAZ A DESCRIÇÃO.** O `short` tem cinco
    colunas e nenhuma delas é o nome de gente — e ler o longo esperando o short
    devolve lixo, que é um defeito que esta casa já pagou
    (`fontes_dualsense`, 20/09/2026).

    Cada nó começa em `Name:` e a descrição vem depois; um `Name:` novo fecha o
    anterior. Nó sem `Description` simplesmente não entra — e aí a tela cai no
    nome cru, que é longo e feio mas é verdade.
    """
    return {no.nome: no.descricao
            for no in retrato_do_som.nos_do_texto(bruto) if no.descricao}


def interessa(linha: str) -> bool:
    """Esta linha do `subscribe` pede uma releitura?

    A forma é `Event 'change' on server #0`. Casar pela PALAVRA do alvo, e não
    por substring solta, é o que impede um `sink-input` (o stream de um app
    qualquer) de acordar o laço a cada frame de áudio — `sink-input` contém
    `sink`.

    Desde 28/09/2026 o `sink-input` acorda o laço, e com razão: ele relê o
    tipo DELE no retrato (:func:`tipo_do_evento`). O que ele continua sem
    fazer é reler o PADRÃO, e é esta a pergunta que esta função responde.
    """
    return tipo_do_evento(linha) in _TIPOS_DO_PADRAO


def tipo_do_evento(linha: str) -> str | None:
    """O tipo do retrato que esta linha do `subscribe` manda reler, ou `None`.

    Pela PALAVRA do alvo, como :func:`interessa`: `sink-input` é um tipo, e
    `sink` é outro. `client` não relê nada — cada `pactl` do próprio retrato é
    um cliente, e reler por eles faria o retrato perguntar por causa das
    próprias perguntas.
    """
    partes = linha.split()
    if len(partes) < 4 or partes[0] != "Event":
        return None
    return retrato_do_som.TIPO_DO_EVENTO.get(partes[3])


async def _publicar(daemon: Any, agora: SomDoSistema) -> None:
    bus = getattr(daemon, "bus", None)
    if bus is None:
        return
    publicar = getattr(bus, "publish", None)
    if publicar is None:
        return
    resultado = publicar(EventTopic.SOM_DO_SISTEMA, agora.como_dicionario())
    if asyncio.iscoroutine(resultado):
        await resultado


async def ouvinte_do_som_loop(daemon: Any) -> None:
    """Segue o `pactl subscribe`, mantém o retrato em dia e publica toda mudança de padrão.

    **O ESTADO VIVE NO DAEMON, não aqui**: `daemon.som_do_sistema` é lido pelo
    `state_full` a cada tique da janela, e guardar uma cópia neste módulo daria
    dois donos do mesmo fato.

    **A PRIMEIRA LEITURA É ANTES DE ESCUTAR QUALQUER EVENTO**, e a ordem é a
    entrega: sem ela a tela ficaria sem resposta até a primeira mudança
    acontecer — que pode ser nunca.

    **QUEM PARA O LAÇO SOLTA O RETRATO**: sem ouvinte não há evento, e uma
    foto que ninguém mantém responderia sobre o passado.
    """
    try:
        while True:
            try:
                await _uma_volta(daemon)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("ouvinte_do_som_caiu", exc_info=True)
            await asyncio.sleep(ESPERA_PARA_RELIGAR_S)
    finally:
        retrato_do_som.RETRATO.soltar()


async def _carregar_o_retrato(retrato: retrato_do_som.RetratoDoSom) -> bool:
    """A leitura inteira, fora do laço de eventos. True = o retrato assumiu."""
    completo = await asyncio.to_thread(retrato.carregar)
    if completo or (retrato.dono and retrato.algum_em_dia()):
        # DONO DE ANTES QUE RELIGOU volta a responder já, mesmo que um tipo
        # tenha falhado: o tipo em dúvida diz "não sei" sozinho, e os outros
        # não precisam esperar por ele. Se NADA respondeu, o servidor não
        # voltou, e o retrato continua sem servidor.
        retrato.assumir(asyncio.get_running_loop())
        return True
    return False


async def _uma_volta(daemon: Any) -> None:
    """Uma sessão de `subscribe`, do início até o `pactl` morrer."""
    retrato = retrato_do_som.RETRATO
    proc = await asyncio.create_subprocess_exec(
        "pactl", "subscribe",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=_ambiente())
    pendentes: set[str] = set()
    tarefas: list[asyncio.Task[None]] = []
    try:
        # O `subscribe` ABRE ANTES DA LEITURA INTEIRA: um evento que chegue no
        # meio dela fica na fila do pipe e relê o tipo depois — o contrário
        # perderia a mudança que acontecesse entre ler e escutar.
        await _carregar_o_retrato(retrato)
        anterior = await ler_o_padrao()
        _guardar(daemon, anterior)
        await _publicar(daemon, anterior)
        logger.info("ouvinte_do_som_ligado", saida=anterior.saida,
                    entrada=anterior.entrada, retrato=retrato.vivo)

        async def aplicar() -> None:
            nonlocal anterior
            tipos = set(pendentes)
            pendentes.clear()
            if not retrato.completo():
                tipos.update(retrato_do_som.TIPOS)
            await asyncio.to_thread(retrato.reler, tipos)
            if not retrato.vivo and retrato.completo():
                retrato.assumir(asyncio.get_running_loop())
            if not tipos & _TIPOS_DO_PADRAO:
                return
            agora = await ler_o_padrao()
            if agora == anterior:
                # O SERVIDOR FALA MAIS DO QUE MUDA: um nó que nasce emite
                # evento e não troca padrão nenhum. Publicar aqui faria a tela
                # repintar por nada, que é o defeito medido em 05/09/2026 (80
                # repinturas em 80 tiques).
                return
            anterior = agora
            _guardar(daemon, agora)
            await _publicar(daemon, agora)
            logger.info("som_do_sistema_mudou", saida=agora.saida,
                        entrada=agora.entrada)

        async def descarregar() -> None:
            while pendentes:
                await asyncio.sleep(RAJADA_S)
                await aplicar()

        async def insistir() -> None:
            # A LEITURA INTEIRA QUE FALHOU TENTA DE NOVO sem esperar evento: um
            # servidor parado não avisa nada, e o retrato ficaria "não sei"
            # até alguém mexer no som.
            while not retrato.completo():
                await asyncio.sleep(ESPERA_PARA_RELIGAR_S)
                pendentes.update(retrato_do_som.TIPOS)
                await aplicar()

        if not retrato.completo():
            tarefas.append(asyncio.create_task(insistir()))
        vez: asyncio.Task[None] | None = None
        assert proc.stdout is not None
        async for bruto in proc.stdout:
            tipo = tipo_do_evento(bruto.decode("utf-8", "replace").strip())
            if tipo is None:
                continue
            pendentes.add(tipo)
            if vez is None or vez.done():
                vez = asyncio.create_task(descarregar())
                tarefas.append(vez)
        # O CANAL FECHOU (o servidor caiu, ou o `pactl` morreu): a rajada que
        # esperava a vez é relida agora, antes de o retrato dizer "não sei".
        for tarefa in tarefas:
            tarefa.cancel()
        # `gather` e não um `await` por tarefa dentro de `suppress(CancelledError)`:
        # aquele engolia também o cancelamento DESTE laço, que chegasse bem
        # aqui, e o daemon não conseguia parar o ouvinte com o servidor caído
        # (achado pela mordida do «sem servidor», 28/09/2026).
        await asyncio.gather(*tarefas, return_exceptions=True)
        tarefas.clear()
        if pendentes:
            await aplicar()
    finally:
        for tarefa in tarefas:
            tarefa.cancel()
        retrato.perdeu_o_servidor()
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()


def _guardar(daemon: Any, agora: SomDoSistema) -> None:
    with contextlib.suppress(Exception):  # dublê sem atributo, daemon ausente
        daemon.som_do_sistema = agora


def som_do_sistema_payload(daemon: Any) -> dict[str, str]:
    """O bloco do `state_full` — `{"saida": …, "entrada": …}`.

    Sem ouvinte de pé (daemon velho, `pactl` fora do PATH), os dois campos
    voltam vazios — que é *"não sei"*, e não *"não há"*. A tela já sabe pintar
    a diferença, e afirmar o segundo faria a pessoa parar de procurar.
    """
    guardado = getattr(daemon, "som_do_sistema", None)
    if isinstance(guardado, SomDoSistema):
        return guardado.como_dicionario()
    return SomDoSistema().como_dicionario()


def start_ouvinte_do_som(daemon: Any) -> None:
    """Sobe o laço. Idempotente do ponto de vista de quem chama."""
    tarefa = asyncio.create_task(ouvinte_do_som_loop(daemon),
                                 name="ouvinte_do_som_loop")
    daemon._tasks.append(tarefa)
    logger.info("ouvinte_do_som_iniciado")


__all__ = [
    "ESPERA_PARA_RELIGAR_S",
    "EVENTOS_QUE_IMPORTAM",
    "RAJADA_S",
    "SomDoSistema",
    "descricoes_da_lista",
    "interessa",
    "ler_o_padrao",
    "ouvinte_do_som_loop",
    "som_do_sistema_payload",
    "start_ouvinte_do_som",
    "tipo_do_evento",
]
