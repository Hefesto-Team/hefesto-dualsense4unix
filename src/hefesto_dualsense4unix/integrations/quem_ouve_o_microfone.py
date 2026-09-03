"""Quem está com o microfone DESTE controle aberto — a PEÇA A da LUZ-DO-MIC-01.

A luz do botão de mudo deixou de ser espelho do mudo e passou a responder
*"alguém está me ouvindo agora?"* (decisão dela, 02/09/2026, em
``docs/process/sprints/2026-09-02-LUZ-DO-MIC-01-a-luz-diz-quem-te-escuta.md``).
O estado ``aceso fixo`` da §1 é literalmente a resposta deste módulo: **algum
app está com o microfone deste controle aberto**.

A casa já sabia listar as FONTES de DualSense
(:func:`~hefesto_dualsense4unix.integrations.eleicao_de_microfone.fontes_de_captura_agora`)
e já sabia casar controle com dispositivo USB (``casamento_usb_agora``). O que
ela nunca perguntou é **quem está lendo uma fonte** — medido em 03/09/2026,
``grep`` por ``source-outputs`` em ``src/`` devolvia zero. É o que nasce aqui.

O QUE ISTO NÃO FAZ, e cada linha é uma decisão:

* **Não mede nível.** "Está entrando som" é a PEÇA B
  (``integrations/nivel_do_microfone.py``). Aqui a pergunta é só "está aberto".
* **Não escreve no controle.** Quem decide e escreve é a PEÇA C
  (``daemon/subsystems/luz_do_mic.py``). Este módulo só LÊ.
* **Não abre stream de captura.** Ler a lista não prende a fonte; abrir um
  stream prenderia o nó em ``RUNNING`` e faria a própria régua mentir.

AS TRÊS ARMADILHAS QUE ESTE MÓDULO EXISTE PARA NÃO CAIR — as três medidas em
03/09/2026, nesta máquina, e nenhuma delas dá erro quando se cai nela:

1. **``target.object`` NÃO diz de que fonte o stream lê.** Ele só existe quando
   o cliente pediu um device explícito, e SOME quando o app grava da fonte
   padrão — que nesta máquina é justamente o microfone do DualSense. Um leitor
   escrito com ele fica verde no teste (onde alguém sempre passa um device) e
   CEGO para o app que mais importa. O único elo confiável é o campo
   ``Source: <índice>``, cruzado com a coluna 1 de ``pactl list sources short``
   (:func:`nomes_de_fonte_por_indice`).
2. **O ``pactl`` desta máquina responde em português** (``Saída da fonte #``,
   ``Fonte:``, ``Cork: não``). Um parser que ancore em ``Source Output #`` acha
   ZERO aqui e devolve lista vazia — e lista vazia se lê como "ninguém está
   ouvindo", que é uma resposta plausível e falsa. O antídoto já existia:
   ``_ambiente_c()`` (``LC_ALL=C``), reusado daqui de baixo.
3. **O medidor do próprio Hefesto não pode contar como ouvinte.** Se contar, a
   luz acende sozinha e a peça inteira mente — é o risco central que a §3 da
   sprint nomeia. Ver :func:`e_stream_do_hefesto`.

**A JUNTA COM A PEÇA B NÃO É UM NOME COMBINADO — É UM ESPAÇO DE NOME.** O
stream do medidor foi visto em DUAS formas no mesmo dia (``parec`` pulse, com
``application.process.id``; ``pw-cat`` nativo, sem PID nenhum), e a PEÇA B
nasceu na mesma leva que esta: o nome exato pelo qual ela se anuncia não estava
fixado quando este arquivo foi escrito. Combinar uma string literal com ela
criaria DOIS donos do mesmo nome, que é como esta casa fabrica divergência
silenciosa — e o sintoma aqui seria a luz acesa para sempre.

Então aqui não se combina nome: reconhece-se o **espaço de nome**
(:data:`PREFIXO_PROPRIEDADE_HEFESTO`, :data:`MARCA_HEFESTO`) e o **modo de
pico**, que são propriedades da forma do stream e não de um acordo. Quem
declara continua sendo a PEÇA B (``nivel_do_microfone.propriedades_do_medidor``,
que este módulo NÃO importa, para não morrer se ela faltar); quem reconhece é
esta. O teste ``test_quem_ouve_o_microfone.py`` faz o encontro das duas e é o
que reprova se elas se afastarem.

**A JUNTA COM A PEÇA C É O TIPO DE RETORNO.** O laço da luz aceita o retorno
só quando ele é um ``dict`` (``daemon/subsystems/luz_do_mic.py``, ``_perguntar``:
``return valor if isinstance(valor, dict) else None``) — devolver outra coisa
não dá erro, dá a luz apagada para sempre. Por isso :func:`quem_ouve_agora` é
literalmente o ``{uniq: [nomes]}`` da §3, e a leitura rica mora em
:func:`ler_quem_ouve`, com outro nome, de propósito.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
    _rodar,
    casamento_usb_agora,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    escolher_fonte,
    fontes_dualsense,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O cabeçalho de bloco de ``pactl list source-outputs`` com ``LC_ALL=C``.
#: Sem o ambiente C ele é ``Saída da fonte #`` nesta máquina — ver a armadilha 2
#: do cabeçalho.
_CABECALHO_DE_BLOCO = "Source Output #"

#: A marca que identifica um processo/stream como NOSSO, em nome de aplicativo,
#: nome de nó ou ``application.id``. Minúscula: todo casamento por nome aqui é
#: feito em ``lower()``.
MARCA_HEFESTO = "hefesto"

#: O ESPAÇO DE NOME das propriedades que o Hefesto planta no stream
#: (``hefesto.papel``, ``hefesto.uniq``, e o que a PEÇA B inventar depois).
#: Reconhecer o prefixo, e não uma chave combinada, é o que faz esta régua
#: continuar valendo quando o outro lado acrescenta uma chave sem avisar.
PREFIXO_PROPRIEDADE_HEFESTO = "hefesto."

#: A propriedade que LIGA o modo de pico do reamostrador do PipeWire — e que é,
#: ao mesmo tempo, o crivo INTRÍNSECO desta peça. Quem a declara recebe
#: ``max|x|`` por bloco, um envelope, não áudio.
CHAVE_DO_MODO_DE_PICO = "resample.peaks"

#: Quantos ancestrais subir em ``/proc`` antes de desistir. Seis alcança
#: ``parec`` → janela/daemon com folga e nunca chega ao ``systemd --user``, que
#: é ancestral de TODO processo da sessão dela e faria a regra pegar tudo.
_MAX_ANCESTRAIS = 6


@dataclass(frozen=True)
class StreamDeCaptura:
    """Um bloco de ``pactl list source-outputs`` — alguém lendo uma fonte.

    ``fonte`` é o ÍNDICE da fonte (o campo ``Source:``), não o nome: o bloco
    não traz nome nenhum, e o campo que pareceria trazer (``target.object``)
    é o que some quando o app grava da fonte padrão.
    """

    indice: int
    fonte: int
    corked: bool
    props: dict[str, str] = field(default_factory=dict)

    @property
    def nome_do_cliente(self) -> str:
        """Como este stream se apresenta — o que a luz vai poder nomear.

        ``application.name`` primeiro (é o que o usuário reconhece: ``Google
        Chrome input``), ``node.name`` como reserva — um cliente PipeWire
        nativo publica os dois, mas nem todo cliente publica o primeiro.
        """
        for chave in ("application.name", "node.name", "media.name"):
            valor = self.props.get(chave, "").strip()
            if valor:
                return valor
        return ""

    @property
    def pid(self) -> int | None:
        """O PID do processo dono, quando ele existe.

        **Não existe em cliente PipeWire nativo** — medido: um ``pw-cat``
        publica ``application.name`` e ``node.name`` e mais nada de processo.
        Por isso o PID é sinal auxiliar aqui, nunca o crivo principal.
        """
        bruto = self.props.get("application.process.id", "").strip()
        try:
            return int(bruto)
        except ValueError:
            return None


@dataclass(frozen=True)
class LeituraDeOuvintes:
    """A resposta inteira de um ciclo — e ela distingue três coisas.

    ``lida=False`` é **não sei**: não havia ``pactl``, ou ele não respondeu. A
    luz não deve mudar por causa disto.

    ``por_uniq[uniq] == []`` é **sei, e ninguém ouve** — a fonte daquele
    controle existe e não tem nenhum ouvinte de fora.

    ``uniq in sem_canal`` é **não há o que medir**: o PipeWire não publica
    canal de captura para aquele controle. Medido em 03/09/2026 com dois
    controles na mesa: o do RÁDIO não publica nenhum, e enquanto isso valer o
    estado ``aceso`` nunca acende para quem joga sem fio (a §1.2 da sprint tem
    a nota, e quem cura é a CANAL-POR-CONTROLE-01). Colapsar este caso em
    ``[]`` faria a ausência de canal parecer defeito da luz.
    """

    por_uniq: dict[str, list[str]] = field(default_factory=dict)
    pausados_por_uniq: dict[str, list[str]] = field(default_factory=dict)
    sem_canal: tuple[str, ...] = ()
    lida: bool = True

    def alguem_ouve(self, uniq: str) -> bool | None:
        """``True``/``False`` por controle — e ``None`` quando não dá para saber.

        ``None`` cobre os dois "não sei" de propósito: a leitura que não
        aconteceu e o controle sem canal. Quem consome (a PEÇA C) não pode
        acender nem apagar por causa de ``None``.
        """
        if not self.lida or uniq not in self.por_uniq:
            return None
        return bool(self.por_uniq[uniq])


def nomes_de_fonte_por_indice(saida_pactl: str) -> dict[int, str]:
    """``{índice: nome}`` a partir de ``pactl list sources short``.

    É o elo que faltava: o bloco do stream diz ``Source: 600``, um número, e o
    resto da casa fala por NOME. O formato é
    ``índice\\tnome\\tdriver\\tformato\\testado`` e não é traduzido — a mesma
    saída que
    :func:`~hefesto_dualsense4unix.integrations.fontes_de_captura.fontes_dualsense`
    já lê, para não pagar uma terceira chamada de ``pactl``.

    O índice MUDA quando o aparelho re-pluga, então este mapa é remontado a
    cada ciclo. Linha ilegível é pulada, nunca chutada.
    """
    mapa: dict[int, str] = {}
    for linha in saida_pactl.splitlines():
        partes = linha.split("\t")
        if len(partes) < 2:
            continue
        try:
            indice = int(partes[0].strip())
        except ValueError:
            continue
        nome = partes[1].strip()
        if nome:
            mapa[indice] = nome
    return mapa


def streams_de_captura(saida_pactl: str) -> list[StreamDeCaptura]:
    """Os blocos de ``pactl list source-outputs``, já em estrutura.

    Corpo VAZIO é resposta legítima e quer dizer "ninguém está capturando" —
    medido: com nada capturando o comando devolve ``rc=0`` e zero byte. Quem
    chama é que separa isso de "não deu para ler" (``rc != 0``), e é a razão de
    :class:`LeituraDeOuvintes` ter o campo ``lida``.

    Bloco sem ``Source:`` é descartado: sem o índice não há a que atribuir o
    ouvinte, e atribuir ao primeiro da lista seria inventar dado.
    """
    saidas: list[StreamDeCaptura] = []
    indice: int | None = None
    fonte: int | None = None
    corked = False
    props: dict[str, str] = {}
    em_propriedades = False

    def fechar() -> None:
        if indice is not None and fonte is not None:
            saidas.append(
                StreamDeCaptura(indice=indice, fonte=fonte, corked=corked, props=dict(props))
            )

    for linha in saida_pactl.splitlines():
        nu = linha.strip()
        if nu.startswith(_CABECALHO_DE_BLOCO):
            fechar()
            indice, fonte, corked, em_propriedades = None, None, False, False
            props = {}
            try:
                indice = int(nu[len(_CABECALHO_DE_BLOCO) :].strip())
            except ValueError:
                indice = None
            continue
        if indice is None:
            continue
        if nu == "Properties:":
            em_propriedades = True
            continue
        if em_propriedades:
            chave, sep, valor = nu.partition(" = ")
            if sep:
                props[chave.strip()] = valor.strip().strip('"')
            continue
        chave, sep, valor = nu.partition(":")
        if not sep:
            continue
        rotulo = chave.strip()
        if rotulo == "Source":
            try:
                fonte = int(valor.strip())
            except ValueError:
                fonte = None
        elif rotulo == "Corked":
            corked = valor.strip().lower() == "yes"
    fechar()
    return saidas


def _cmdline(pid: int, raiz_proc: Path) -> str:
    """A linha de comando do processo, em minúscula — ``""`` se não der."""
    try:
        bruto = (raiz_proc / str(pid) / "cmdline").read_bytes()
    except OSError:
        return ""
    return bruto.replace(b"\0", b" ").decode("utf-8", "replace").lower()


def _ppid(pid: int, raiz_proc: Path) -> int | None:
    """O pai do processo, lido do campo 4 de ``/proc/<pid>/stat``.

    O ``comm`` do campo 2 vem entre parênteses e pode conter espaço, então o
    corte é feito depois do ÚLTIMO ``)`` — cortar pelo primeiro espaço lê o
    campo errado para todo processo com espaço no nome.
    """
    try:
        stat = (raiz_proc / str(pid) / "stat").read_text(encoding="utf-8")
    except OSError:
        return None
    _, _, resto = stat.rpartition(")")
    campos = resto.split()
    if len(campos) < 2:
        return None
    try:
        return int(campos[1])
    except ValueError:
        return None


def descende_do_hefesto(pid: int | None, raiz_proc: Path | str = "/proc") -> bool:
    """O processo (ou algum ancestral próximo) é do Hefesto?

    Existe por um buraco que nenhuma das outras regras alcança: a JANELA já
    captura o microfone hoje (``app/mic_monitor.py``, ``_garantir_captura``) e
    o ``parec`` que ela lança sai **cru** — ``application.name = "parec"``,
    igual ao ``parec`` de qualquer outro programa. Excluir pelo nome ``parec``
    excluiria os alheios junto; não excluir faz a luz acender quando ela abre a
    aba Status, que se lê como *"a aba está me espionando"*.

    A árvore de processos responde sem ambiguidade: aquele ``parec`` desce da
    janela do Hefesto. A subida é limitada a :data:`_MAX_ANCESTRAIS` de
    propósito — o ``systemd --user`` é ancestral de tudo o que ela roda, e
    chegar até lá faria a regra excluir a máquina inteira.

    ``raiz_proc`` é injetável para o teste medir a REGRA sem depender da mesa.
    """
    if pid is None:
        return False
    raiz = Path(raiz_proc)
    atual: int | None = pid
    for _ in range(_MAX_ANCESTRAIS):
        if atual is None or atual <= 1:
            return False
        if MARCA_HEFESTO in _cmdline(atual, raiz):
            return True
        atual = _ppid(atual, raiz)
    return False


def e_stream_do_hefesto(stream: StreamDeCaptura, raiz_proc: Path | str = "/proc") -> bool:
    """Este stream é NOSSO? — o risco central da peça, em uma função.

    Se o medidor de nível da PEÇA B contar como ouvinte, a luz acende sozinha e
    a peça inteira mente. As regras são independentes de propósito, porque a
    forma do stream irmão ainda não está fixada — ele foi visto em duas formas
    no mesmo dia, ``parec`` pulse e ``pw-cat`` nativo, e a segunda não publica
    processo nenhum:

    1. **Qualquer propriedade em ``hefesto.``** — o espaço de nome, não uma
       chave combinada. Pega ``hefesto.papel``, ``hefesto.uniq`` e o que a
       PEÇA B acrescentar depois sem avisar ninguém.
    2. **``application.id``** — ``br.dev.hefesto.…``. Sobrevive a troca de nome
       de aplicativo, e é o que o servidor guarda no ``stream-restore``.
    3. **``application.name`` / ``node.name`` / ``media.name``** — o único crivo
       que existe nas DUAS formas do stream, e por isso o que não pode faltar.
    4. **``resample.peaks = "true"``** — e esta é INTRÍNSECA, não convencional:
       um stream em modo de pico recebe ``max|x|`` por bloco, um envelope, não
       áudio. Ele estruturalmente não consegue ouvir o que ela diz, seja de
       quem for. Vale para um medidor de terceiro pelo mesmo motivo.
    5. **A árvore de processos** (:func:`descende_do_hefesto`) — a rede que pega
       o ``parec`` cru da janela, que não tem marca nenhuma para pegar.

    A direção do erro é escolhida: excluir demais apaga uma luz que devia
    acender; excluir de menos acende uma luz sozinha, para sempre, e é este o
    defeito que a sprint nomeia.
    """
    props = stream.props
    for chave, valor in props.items():
        if chave.lower().startswith(PREFIXO_PROPRIEDADE_HEFESTO) and valor.strip():
            return True
    if MARCA_HEFESTO in props.get("application.id", "").lower():
        return True
    if MARCA_HEFESTO in stream.nome_do_cliente.lower():
        return True
    if MARCA_HEFESTO in props.get("node.name", "").lower():
        return True
    if props.get(CHAVE_DO_MODO_DE_PICO, "").strip().lower() == "true":
        return True
    return descende_do_hefesto(stream.pid, raiz_proc)


def ouvintes_por_fonte(
    saida_source_outputs: str,
    saida_sources_short: str,
    raiz_proc: Path | str = "/proc",
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """``({fonte: [ouvintes]}, {fonte: [pausados]})`` — os dois, por NOME de fonte.

    Streams do Hefesto saem fora dos dois mapas: eles não são ouvintes nem
    ouvintes pausados, são a régua se olhando no espelho.

    A separação entre ouvinte e PAUSADO é o campo ``Corked``, e a decisão de
    qual conta para a luz **não é deste módulo**: o primeiro mapa é o que
    responde "alguém está me ouvindo AGORA", o segundo é "alguém tem aberto,
    mas parado". A PEÇA C escolhe. Registrado porque o caso ``Corked: yes``
    NÃO foi medido no levantamento de 03/09 — só o ``no`` apareceu na mesa.

    Só entram fontes que existem no mapa de índices: um stream cujo índice não
    casa com fonte nenhuma é descartado, não atribuído por proximidade.
    """
    nomes = nomes_de_fonte_por_indice(saida_sources_short)
    ouvindo: dict[str, list[str]] = {}
    pausados: dict[str, list[str]] = {}
    for stream in streams_de_captura(saida_source_outputs):
        nome_da_fonte = nomes.get(stream.fonte)
        if not nome_da_fonte:
            continue
        if e_stream_do_hefesto(stream, raiz_proc):
            continue
        alvo = pausados if stream.corked else ouvindo
        alvo.setdefault(nome_da_fonte, []).append(stream.nome_do_cliente)
    return ouvindo, pausados


def quem_ouve_agora(
    uniqs: list[str], raiz_proc: Path | str = "/proc"
) -> dict[str, list[str]] | None:
    """``{uniq: [nomes dos clientes]}`` — o contrato da §3, e nada além dele.

    **É esta a função que a PEÇA C chama**, e o tipo é o contrato inteiro: o
    laço da luz aceita o retorno só quando ele é ``dict``
    (``daemon/subsystems/luz_do_mic.py``, ``_perguntar``). Devolver a leitura
    rica aqui não daria erro nenhum — daria a luz apagada para sempre, com o
    laço descartando toda resposta em silêncio. A leitura rica é
    :func:`ler_quem_ouve`, com outro nome, exatamente por isso.

    Três respostas, e são três coisas diferentes:

    * ``None`` — **não sei**. Não havia ``pactl``, ou ele não respondeu.
    * ``uniq`` ausente do dicionário — **não há o que medir**: o PipeWire não
      publica canal de captura para aquele controle (o do rádio, hoje).
    * ``[]`` — **sei, e ninguém ouve**.

    As duas primeiras chegam ao laço como o mesmo ``None`` por ``uniq``, e o
    laço não escreve; a terceira apaga a luz com todas as letras.
    """
    leitura = ler_quem_ouve(uniqs, raiz_proc)
    return leitura.por_uniq if leitura.lida else None


def ler_quem_ouve(
    uniqs: list[str], raiz_proc: Path | str = "/proc"
) -> LeituraDeOuvintes:
    """A leitura de um ciclo, inteira: quem ouve, quem pausou, quem não tem canal.

    Três chamadas de ``pactl`` no pior caso — ``source-outputs``,
    ``sources short`` e a longa que o casamento USB pede —, ~6,8 ms de CPU,
    0,68% de um núcleo a 1 Hz (medido em 03/09/2026). O custo é **O(1) no
    número de controles**: uma chamada lista os streams de todas as fontes de
    uma vez, então quatro controles custam a mesma leitura que um.

    Sem fonte de DualSense nenhuma a terceira chamada nem acontece: não há o
    que casar, e todo controle vai para ``sem_canal``.

    Toda não-resposta é resposta. ``rc != 0`` no ``source-outputs`` devolve
    ``lida=False`` — "não sei" —, e não a lista vazia, que diria "ninguém está
    ouvindo" com a mesma cara.
    """
    if not uniqs:
        return LeituraDeOuvintes(lida=True)

    rc_so, saida_so = _rodar(["pactl", "list", "source-outputs"])
    if rc_so != 0:
        logger.debug("pactl list source-outputs falhou (rc=%s): não sei quem ouve", rc_so)
        return LeituraDeOuvintes(lida=False)

    rc_short, saida_short = _rodar(["pactl", "list", "sources", "short"])
    if rc_short != 0:
        logger.debug("pactl list sources short falhou (rc=%s): não sei quem ouve", rc_short)
        return LeituraDeOuvintes(lida=False)

    fontes = fontes_dualsense(saida_short)
    if not fontes:
        return LeituraDeOuvintes(sem_canal=tuple(uniqs), lida=True)

    ouvindo, pausados = ouvintes_por_fonte(saida_so, saida_short, raiz_proc)
    usb = casamento_usb_agora(uniqs)

    por_uniq: dict[str, list[str]] = {}
    pausados_por_uniq: dict[str, list[str]] = {}
    sem_canal: list[str] = []
    for uniq in uniqs:
        fonte = escolher_fonte(fontes, uniq, uniqs, usb)
        if fonte is None:
            sem_canal.append(uniq)
            continue
        por_uniq[uniq] = list(ouvindo.get(fonte, ()))
        pausados_por_uniq[uniq] = list(pausados.get(fonte, ()))
    return LeituraDeOuvintes(
        por_uniq=por_uniq,
        pausados_por_uniq=pausados_por_uniq,
        sem_canal=tuple(sem_canal),
        lida=True,
    )


__all__ = [
    "CHAVE_DO_MODO_DE_PICO",
    "MARCA_HEFESTO",
    "PREFIXO_PROPRIEDADE_HEFESTO",
    "LeituraDeOuvintes",
    "StreamDeCaptura",
    "descende_do_hefesto",
    "e_stream_do_hefesto",
    "ler_quem_ouve",
    "nomes_de_fonte_por_indice",
    "ouvintes_por_fonte",
    "quem_ouve_agora",
    "streams_de_captura",
]
