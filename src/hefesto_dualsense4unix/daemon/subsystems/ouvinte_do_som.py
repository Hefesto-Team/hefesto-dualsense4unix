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
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Quanto se espera antes de tentar de novo quando o `pactl` morre. O servidor
#: de som reinicia (o `systemctl --user restart pipewire` do doctor faz isso), e
#: um ouvinte que desistisse na primeira queda ficaria mudo pelo resto da
#: sessão — que é exatamente o defeito que ele vem curar.
ESPERA_PARA_RELIGAR_S: float = 3.0

#: O teto de uma leitura do estado (`pactl info`). Curto de propósito: o laço
#: roda no daemon, e uma leitura pendurada seguraria o `stop()`.
TETO_DA_LEITURA_S: float = 4.0

#: As linhas do `subscribe` que interessam. O `subscribe` fala de tudo —
#: clientes que abrem e fecham, streams de cada app — e reagir a tudo faria uma
#: leitura de `pactl info` por frame de áudio de qualquer programa.
#:
#: `server` é a que carrega a troca de padrão; `sink`/`source` são o nó que
#: nasce e morre, que é a outra metade da queixa dela (o nó do controle some e
#: a tela fica acesa no que estava).
EVENTOS_QUE_IMPORTAM = ("server", "sink", "source")


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
    """`pactl get-default-sink` + `get-default-source`, sem levantar.

    DUAS PERGUNTAS CURTAS em vez de um `pactl info` inteiro: o `info` traz
    dezenove campos e muda de forma entre versões, e estas duas respondem
    exatamente o que a tela mostra.

    Erro de qualquer natureza devolve o que se conseguiu ler — um campo vazio é
    *"não sei"*, e é o que a tela já sabe pintar. Levantar aqui derrubaria o
    laço por causa de um `pactl` que saiu do PATH.
    """
    valores = [await _pactl("get-default-sink"), await _pactl("get-default-source")]
    descricoes = await _descricoes()
    return SomDoSistema(
        saida=valores[0], entrada=valores[1],
        saida_nome=descricoes.get(valores[0], ""),
        entrada_nome=descricoes.get(valores[1], ""))


async def _pactl(*args: str) -> str:
    """Um `pactl` de LEITURA. Saída limpa, ou `""` — nunca levanta."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pactl", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=_ambiente())
    except (OSError, ValueError):
        return ""
    try:
        bruto, _ = await asyncio.wait_for(
            proc.communicate(), timeout=TETO_DA_LEITURA_S)
    except (TimeoutError, asyncio.TimeoutError):
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        return ""
    if proc.returncode != 0:
        return ""
    return bruto.decode("utf-8", "replace").strip()


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
    fora: dict[str, str] = {}
    nome = ""
    for linha in bruto.splitlines():
        limpa = linha.strip()
        if limpa.startswith("Name:"):
            nome = limpa[len("Name:"):].strip()
        elif limpa.startswith("Description:") and nome:
            fora[nome] = limpa[len("Description:"):].strip()
            nome = ""
    return fora


async def _descricoes() -> dict[str, str]:
    """Os nomes de gente de todas as saídas e entradas, num mapa só.

    DUAS CHAMADAS, e elas custam o que custam porque só acontecem quando o
    servidor AVISA que algo mudou — nunca por tique da janela.
    """
    fora: dict[str, str] = {}
    for alvo in ("sinks", "sources"):
        fora.update(descricoes_da_lista(await _pactl("list", alvo)))
    return fora


def interessa(linha: str) -> bool:
    """Esta linha do `subscribe` pede uma releitura?

    A forma é `Event 'change' on server #0`. Casar pela PALAVRA do alvo, e não
    por substring solta, é o que impede um `sink-input` (o stream de um app
    qualquer) de acordar o laço a cada frame de áudio — `sink-input` contém
    `sink`.
    """
    partes = linha.split()
    if len(partes) < 4 or partes[0] != "Event":
        return False
    return partes[3] in EVENTOS_QUE_IMPORTAM


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
    """Segue o `pactl subscribe` e publica toda mudança de padrão.

    **O ESTADO VIVE NO DAEMON, não aqui**: `daemon.som_do_sistema` é lido pelo
    `state_full` a cada tique da janela, e guardar uma cópia neste módulo daria
    dois donos do mesmo fato.

    **A PRIMEIRA LEITURA É ANTES DO `subscribe`**, e a ordem é a entrega: sem
    ela a tela ficaria sem resposta até a primeira mudança acontecer — que pode
    ser nunca.
    """
    while True:
        try:
            await _uma_volta(daemon)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("ouvinte_do_som_caiu", exc_info=True)
        await asyncio.sleep(ESPERA_PARA_RELIGAR_S)


async def _uma_volta(daemon: Any) -> None:
    """Uma sessão de `subscribe`, do início até o `pactl` morrer."""
    anterior = await ler_o_padrao()
    _guardar(daemon, anterior)
    await _publicar(daemon, anterior)

    proc = await asyncio.create_subprocess_exec(
        "pactl", "subscribe",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=_ambiente())
    logger.info("ouvinte_do_som_ligado", saida=anterior.saida,
                entrada=anterior.entrada)
    try:
        assert proc.stdout is not None
        async for bruto in proc.stdout:
            if not interessa(bruto.decode("utf-8", "replace").strip()):
                continue
            agora = await ler_o_padrao()
            if agora == anterior:
                # O SERVIDOR FALA MAIS DO QUE MUDA: um nó que nasce emite
                # evento e não troca padrão nenhum. Publicar aqui faria a tela
                # repintar por nada, que é o defeito medido em 05/09/2026 (80
                # repinturas em 80 tiques).
                continue
            anterior = agora
            _guardar(daemon, agora)
            await _publicar(daemon, agora)
            logger.info("som_do_sistema_mudou", saida=agora.saida,
                        entrada=agora.entrada)
    finally:
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
    "SomDoSistema",
    "descricoes_da_lista",
    "interessa",
    "ler_o_padrao",
    "ouvinte_do_som_loop",
    "som_do_sistema_payload",
    "start_ouvinte_do_som",
]
