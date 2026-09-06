"""O canal de captura de UM controle, com o nome DELE — não o do transporte.

ONDA5-MIC-VIRTUAL-01, e a decisão é dela, 05/09/2026:

    *"Criamos mecanismos pra usarmos todas as feature. Exemplo controle do Xbox
    não tem microfone mas se o Mic do dualsense passa a ser lido a parte via Mic
    virtual. Usaríamos essa feature do controle mesmo no Xbox. Mesmo problema
    BT. Hj já funciona assim, sem a parte do Mic virtual."*
    <!-- as duas metades, e as duas são engenharia -->

O princípio que manda este módulo existir está em
`docs/process/2026-09-05-A-MASCARA-NAO-CUSTA-FEATURE-o-principio-e-o-que-ele-cobra.md`,
e a regra que ele deixa é uma linha: **o Hefesto não explica a própria falha —
ele a conserta.**

O DEFEITO MEDIDO, e ele é de NOME
----------------------------------

Hoje o microfone do mesmo controle se chama de dois jeitos:

===========  ==============================================  ================
transporte   como o microfone daquele controle se chama      tem identidade?
===========  ==============================================  ================
rádio        ``hefesto_dualsense_bt_<hex6>`` — os três        **sim**
             últimos octetos do MAC
cabo         um nó ALSA cujo ``-00``/``-00.2`` é desempate    **não**
             posicional do PipeWire
===========  ==============================================  ================

**Troque o transporte e o microfone daquele controle muda de nome.** Um app que
fixou o device perde o microfone: o nome que ele guardou deixou de existir.

O custo disso já está pago e dá para medi-lo — responder *"qual nó é o microfone
DESTE controle"* custa hoje `fontes_de_captura.escolher_fonte`, quatro regras
mais um censo do dispositivo USB pai, com quatro chamadores independentes. E a
regra do USB pai **não existe no rádio**, porque a placa de som segue o
transporte: para o controle no rádio a resposta certa daquela função é ``None``,
e a docstring dela o diz.

O QUE ESTE MÓDULO É, E O QUE ELE **NÃO** É
-------------------------------------------

Ele é o **dono único do NOME e do CICLO DE VIDA** do canal por controle. Ele não
é um mecanismo novo: o mecanismo — ``module-pipe-source``, um módulo, um fifo,
zero processo intermediário — já existe e está medido em
:class:`~hefesto_dualsense4unix.integrations.dualsense_bt_audio.SourceVirtualPipeWire`,
publicado pela ponte de rádio desde 25/07/2026. **Ele é reusado daqui, não
reescrito** — que é exatamente a ordem dela: *"ao invés de aproveitar o do gtk e
adaptar ele pra funcionar no html. estamos recriando um produto que estava
praticamente pronto"*.

Pela mesma razão a PRIORIDADE não é um literal novo:
``PRIORIDADE_SESSAO_DA_PONTE`` é lida do dono, com a medição de 03/09 na máquina
dela por trás. Um número inventado aqui repetiria o defeito que aquele
comentário registra — um literal catorze dias atrás da doutrina que ele
espelhava.

O QUE ESTA SPRINT **NÃO** FAZ, e o corte é por REVERSIBILIDADE
---------------------------------------------------------------

Ela constrói o nó com nome. **Ela não converte o rádio**, e a razão não é
tamanho:

* **no CABO existe rede embaixo** — o nó ALSA continua publicado enquanto o nó
  novo sobe ao lado. Se o novo não servir, ninguém fica sem microfone;
* **no RÁDIO não existe** — ``hefesto_dualsense_bt_<hex6>`` é o ÚNICO canal que
  o rádio tem hoje. Mexer nele antes de o novo estar provado tira dela o
  microfone por Bluetooth inteiro.

A ONDA5-MIC-VIRTUAL-02 faz o rádio alimentar este nó e converte os quatro
chamadores de ``escolher_fonte``. Ela só começa com este nó de pé e medido com
dois controles na bancada.

**E NADA AQUI CARREGA MÓDULO SOZINHO.** :func:`abrir` é chamada, não agendada; o
ponto de entrada dela é o ``pedir_canal`` da eleição
(`integrations/eleicao_de_microfone.py`), que já é o gesto DELA desde 01/09 — o
botão do microfone, que quer dizer *"eu falo por este controle"*.

COMO O CABO ENTRA NO NÓ — A MEDIÇÃO VEIO ANTES DO CÓDIGO
---------------------------------------------------------

A sprint manda medir, antes de escrever qualquer linha, **se um link do grafo do
PipeWire basta ou se é preciso um leitor**. Medido na máquina dela em
06/09/2026, com um ``module-pipe-source`` de mentira de pé e desmontado no fim
(``pw-link``, ``pw-dump``, PipeWire 1.6.8)::

    pw-link -i | grep <o nó>   →  (NENHUMA PORTA DE ENTRADA)
    pw-link -o | grep <o nó>   →  <o nó>:capture_FL
                                  <o nó>:capture_FR
    pw-dump                    →  media.class = Audio/Source
                                  PORT dir=output  capture_FL
                                  PORT dir=output  capture_FR

**Um ``module-pipe-source`` não tem porta de ENTRADA.** As duas portas dele
apontam para fora, para quem grava. Não existe no grafo nada a que ligar o nó do
cabo: ``pw-link`` não tem alvo. **A única entrada do nó é o fifo** — que é,
aliás, o desenho: o módulo é o dono da ponta de leitura e a ponta de escrita é
de quem alimenta.

**Logo: é preciso um LEITOR.** Ele é um :data:`_ALIMENTADOR` (``parec``) que
grava do nó do cabo e entrega o PCM a :meth:`SourceVirtualPipeWire.escrever` —
a MESMA porta pela qual a ponte de rádio entrega os quadros Opus decodificados
desde 25/07. Um só nó, uma só entrada, dois transportes: é o que faz o
microfone daquele controle ter um nome só.

**Por que ``parec`` e não ``pw-cat``**, e não é gosto:

* o nome que este módulo tem em mãos é um nome de ``pactl`` (quem lista é
  ``fontes_de_captura.fontes_dualsense``, que lê ``pactl list sources short``).
  ``parec --device=`` fala exatamente essa língua; ``pw-cat --target=`` fala a
  do ``node.name`` do PipeWire, e a igualdade entre os dois hoje é acidente,
  não contrato;
* ``--property=CHAVE=VALOR`` é **um argv por propriedade**. Medido no mesmo dia:
  o ``source_properties`` do ``load-module`` perde tudo depois do primeiro
  espaço quando não vem entre aspas duplas — ver :func:`propriedades_do_canal`.
  Um alimentador que perdesse as propriedades acenderia a luz vermelha do
  microfone dela para sempre;
* a casa já lança ``parec`` (``app/mic_monitor.py``), e
  ``quem_ouve_o_microfone.descende_do_hefesto`` foi escrita para esse caso.

**O QUE ISTO AINDA CUSTA, e está declarado:** enquanto o alimentador roda, o nó
ALSA do cabo fica em ``RUNNING`` mesmo sem ninguém gravando do canal — o
``escrever`` descarta, e o descarte é o comportamento certo, mas quem lê é o
``parec``, que não sabe disso. É o MESMO defeito que a CANAL-POR-CONTROLE-01
nomeou no rádio (*"a ponte captura mesmo sem ouvinte"*), e a cura é a mesma: o
alimentador seguir o SUSPENDED/RUNNING da source. **Isso é da
ONDA5-MIC-VIRTUAL-02**, junto com o ``0x32`` do rádio, porque é a mesma peça.
O que segura a conta hoje é o ciclo de vida: o canal só nasce sob
``pedir_canal``, que é o toque DELA no botão.

A ARMADILHA QUE ESTE MÓDULO HERDA, e ela já tem nome na árvore
---------------------------------------------------------------

``quem_ouve_o_microfone.e_stream_do_hefesto`` existe porque *"o medidor do
próprio Hefesto não pode contar como ouvinte. Se contar, a luz acende sozinha e
a peça inteira mente"*. **O que alimentar este nó cai na MESMA armadilha, com o
mesmo sintoma:** a luz vermelha do microfone dela acesa para sempre.

E o mesmo módulo já ensinou como NÃO combinar isso: *"a junta com a peça B não é
um nome combinado — é um espaço de nome"*. Então aqui também não se combina
nome: as propriedades do nó nascem no espaço ``hefesto.``
(:data:`~hefesto_dualsense4unix.integrations.quem_ouve_o_microfone.PREFIXO_PROPRIEDADE_HEFESTO`),
lido do dono, e quem reconhece continua sendo aquela peça.
"""

from __future__ import annotations

import contextlib
import logging
import subprocess
import threading
from typing import Any

from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    PRIORIDADE_SESSAO_DA_PONTE,
    SourceVirtualPipeWire,
)
from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    MIN_HEX_SUFIXO_BT,
    PREFIXO_SOURCE_CANAL_DO_MIC,
    so_hex,
)
from hefesto_dualsense4unix.integrations.quem_ouve_o_microfone import (
    PREFIXO_PROPRIEDADE_HEFESTO,
)

logger = logging.getLogger(__name__)

#: O PREFIXO DO NOME — ``hefesto_mic_<hex6>``, lido do dono.
#:
#: **Ele mora em `fontes_de_captura`, e não aqui**, porque quem LÊ o nome é o
#: resolvedor (`escolher_fonte`, `fontes_dualsense`) e este módulo já importa
#: de lá: pôr o nome aqui fecharia um ciclo de importação. A regra da casa
#: resolve sem ciclo — o nome mora com quem o lê, e quem o escreve LÊ de lá, que
#: é o mesmo movimento de `PREFIXO_SOURCE_PONTE_BT`.
PREFIXO_CANAL = PREFIXO_SOURCE_CANAL_DO_MIC


#: Quantos dígitos hex um endereço de aparelho tem, sem os separadores. Doze —
#: seis octetos. É o que separa um MAC de uma string qualquer.
_HEX_DE_UM_ENDERECO = 12

#: O que se tira de um `uniq` antes de perguntar se o resto é hex. Só
#: separadores de endereço; nada de letras.
_SEPARADORES = (":", "-", ".", " ")

#: O PAPEL que o alimentador declara em ``hefesto.papel``. É o que diz, do lado
#: de fora, o que aquele stream está fazendo ali: ele não é ouvinte, é a
#: mangueira. Uma constante e não um literal solto porque a régua do encontro
#: (`test_o_canal_do_microfone_tem_nome_de_controle`) o lê daqui.
PAPEL_DO_ALIMENTADOR = "canal-do-microfone"

#: O LEITOR. A medição do cabeçalho decidiu que ele é necessário — um
#: ``module-pipe-source`` não tem porta de entrada no grafo — e decidiu qual:
#: ``parec``, que fala nome de ``pactl`` e leva uma propriedade por argv.
_ALIMENTADOR = "parec"

#: Como o alimentador se apresenta em ``application.name``. Ele já seria
#: reconhecido pelo espaço de nome ``hefesto.``; o nome legível existe para
#: quando um humano olhar o ``pactl list source-outputs`` e precisar saber o que
#: é aquilo — foi o que custou uma hora em 25/07 do outro lado.
NOME_DO_CLIENTE_ALIMENTADOR = "hefesto-canal-do-microfone"

#: Quanto o bombeador lê por vez. 4 KiB a 48 kHz mono s16 é ~42 ms — menos que
#: o fifo de 8 KiB do outro lado, para nunca ser ele o gargalo, e grande o
#: bastante para o laço acordar ~24 vezes por segundo em vez de mil.
_PEDACO_BYTES = 4096

#: A LATÊNCIA QUE SE PEDE AO LEITOR, e ela não é afinação — é conserto.
#:
#: MEDIDO na máquina dela em 06/09/2026, com o tom sintético na origem::
#:
#:     parec sem --latency-msec       → primeiro byte aos 1,98 s
#:     parec com --latency-msec=40    → primeiro byte aos 0,088 s
#:
#: O ``parec`` nasce com ``pulse.attr.fragsize = 384000`` — quase QUATRO
#: SEGUNDOS de áudio a 48 kHz mono s16. Do lado dela isso são dois segundos de
#: silêncio depois de apertar o botão do microfone, que se lê como *"não
#: funcionou"*; e o fragmento gigante chegaria de uma vez a um fifo de 8 KiB,
#: onde quase tudo viraria descarte.
#:
#: 40 ms é menos que o fifo (8 KiB ≈ 85 ms mono) de propósito: um fragmento
#: sempre cabe inteiro, e nunca é o leitor quem estoura a mangueira.
_LATENCIA_DO_ALIMENTADOR_MS = 40

#: Quanto se espera o alimentador morrer antes de insistir. Ele é um `parec`
#: sem estado; não há o que ele precise fechar direito.
_ESPERA_PELO_FIM_S = 2.0

#: Teto do `pactl` que tira o mudo de fábrica. Um `pactl` pendurado num PipeWire
#: morto não pode segurar o toque dela no botão do microfone.
_TIMEOUT_PACTL_S = 5.0


def sufixo_do_controle(uniq: str) -> str:
    """Os seis últimos dígitos hex do `uniq` — "" se ele não for um endereço.

    É a MESMA regra de `NoDualSenseBT.nome_curto`, e a diferença é o que
    acontece quando não dá: aquela propriedade cai no nome do nó, o que só faz
    sentido para quem está lendo o sysfs do Bluetooth. Aqui a resposta certa é
    `""` — **sem identidade não se batiza um canal**, e um nome inventado
    colidiria com o do vizinho na mesa de quatro, que é pior que não ter nome.

    E ELE EXIGE UM ENDEREÇO INTEIRO, não "seis dígitos hex em algum lugar" —
    medido ao escrever este módulo, em 05/09/2026: ``so_hex`` sobre
    ``"sem-identidade"`` devolve ``"emdedade"``, porque **e**, **d** e **a** são
    dígitos hex, e o canal nasceria batizado ``hefesto_mic_dedade``. É a mesma
    armadilha de casamento por acaso que `fontes_de_captura.sufixo_da_ponte_bt`
    já paga com o ``so_hex(resto) != resto``, aqui na entrada em vez da saída.
    """
    limpo = uniq.lower()
    for separador in _SEPARADORES:
        limpo = limpo.replace(separador, "")
    if len(limpo) < _HEX_DE_UM_ENDERECO or so_hex(limpo) != limpo:
        return ""
    return limpo[-MIN_HEX_SUFIXO_BT:]


def nome_do_canal(uniq: str) -> str:
    """`hefesto_mic_<hex6>` para este controle — "" se ele não tem identidade."""
    sufixo = sufixo_do_controle(uniq)
    return f"{PREFIXO_CANAL}{sufixo}" if sufixo else ""


def propriedades_do_canal(uniq: str) -> dict[str, str]:
    """As propriedades do ALIMENTADOR — no ESPAÇO DE NOME, nunca combinadas.

    ``hefesto.papel`` e ``hefesto.uniq`` caem sob
    :data:`quem_ouve_o_microfone.PREFIXO_PROPRIEDADE_HEFESTO`, que é lido do
    dono. Quem reconhece o que é do Hefesto continua sendo aquela peça, e ela o
    faz pelo PREFIXO — nenhuma chave combinada entre os dois arquivos.

    **ELAS VÃO NO STREAM DO ALIMENTADOR, NÃO NO NÓ**, e a diferença é o que
    decide se a luz vermelha do microfone dela mente. Quem
    :func:`~hefesto_dualsense4unix.integrations.quem_ouve_o_microfone.ouvintes_por_fonte`
    conta são os blocos de ``pactl list source-outputs`` — STREAMS. O
    alimentador é um stream que lê o nó do cabo; se ele contar, o Hefesto vira
    ouvinte de si mesmo e a luz acende sozinha, para sempre.

    **E ELAS NÃO CABERIAM NO NÓ, medido em 06/09/2026 nesta máquina:** o
    ``source_properties`` do ``pactl load-module`` só sobrevive inteiro entre
    ASPAS DUPLAS. Sem elas, tudo depois do primeiro espaço é descartado em
    silêncio — e é o que acontece hoje com a source da ponte de rádio, que monta
    ``device.description='…' priority.session=1500 device.icon_name=…``::

        A) source_properties=priority.session=7                 → prio 7   ✓
        B) …description='canal medicao' priority.session=7 …    → prio 2000 ✗
        C) source_properties="…=7 hefesto.papel=… hefesto.uniq=…" → tudo ✓

    O ``--property=CHAVE=VALOR`` do ``parec`` é um argv por propriedade e não
    tem esse buraco. (O caso B é defeito vivo de
    ``integrations/dualsense_bt_audio.py``, que esta sprint não toca — está
    RELATADO, não curado.)
    """
    return {
        f"{PREFIXO_PROPRIEDADE_HEFESTO}papel": PAPEL_DO_ALIMENTADOR,
        f"{PREFIXO_PROPRIEDADE_HEFESTO}uniq": uniq,
    }


def argv_do_alimentador(uniq: str, fonte: str, *, taxa_hz: int, canais: int) -> list[str]:
    """A linha de comando do leitor que enche o fifo — nunca uma string de shell.

    ``shell=True`` é invariante proibido nesta casa, e aqui ele seria pior que
    de costume: o `uniq` e o nome da fonte vêm do PipeWire, não de nós.

    **A taxa e os canais vêm do NÓ, não de constante deste arquivo.** O
    `module-pipe-source` foi carregado com um formato; entregar-lhe outro
    encheria o fifo com bytes de outro tamanho e o áudio sairia em velocidade
    errada, sem erro nenhum. Quem sabe o formato é a source, e ela o publica em
    `taxa_hz`/`canais` — o alimentador PERGUNTA a ela.
    """
    argv = [
        _ALIMENTADOR,
        f"--device={fonte}",
        "--raw",
        "--format=s16le",
        f"--rate={taxa_hz}",
        f"--channels={canais}",
        f"--latency-msec={_LATENCIA_DO_ALIMENTADOR_MS}",
        f"--client-name={NOME_DO_CLIENTE_ALIMENTADOR}",
    ]
    props = sorted(propriedades_do_canal(uniq).items())
    argv += [f"--property={chave}={valor}" for chave, valor in props]
    return argv


class _Alimentador:
    """O leitor do cabo e o bombeador — as duas metades de "o cabo entra no nó".

    Ele não escreve no fifo direto: entrega o PCM a
    :meth:`SourceVirtualPipeWire.escrever`, que é a porta PÚBLICA do mecanismo e
    a mesma pela qual a ponte de rádio entrega os quadros dela. É o que faz o
    nó ter UMA entrada e dois transportes — e é o que permite que a
    ONDA5-MIC-VIRTUAL-02 ligue o rádio no mesmo nó sem reabrir esta peça.

    O descarte de `escrever` quando ninguém está gravando é comportamento
    CORRETO e está documentado no dono; aqui ele aparece como bytes que somem, e
    é por isso que este laço não trata `False` como falha.
    """

    def __init__(self, uniq: str, fonte: str, source: Any, *, lancar: Any = None) -> None:
        self.uniq = uniq
        self.fonte = fonte
        self.source = source
        self._lancar = lancar or _lancar_processo
        self._proc: Any = None
        self._bomba: threading.Thread | None = None
        self._parando = threading.Event()

    def iniciar(self) -> bool:
        argv = argv_do_alimentador(
            self.uniq,
            self.fonte,
            taxa_hz=getattr(self.source, "taxa_hz", 48000),
            canais=getattr(self.source, "canais", 1),
        )
        try:
            self._proc = self._lancar(argv)
        except (OSError, ValueError):
            # `parec` pode não estar instalado. O canal continua de pé e mudo —
            # que é melhor que derrubar o nó, porque a MIC-VIRTUAL-02 vai
            # alimentá-lo pelo rádio pela mesma porta.
            logger.warning("canal_do_mic_alimentador_nao_lancou", exc_info=True)
            return False
        if self._proc is None or self._proc.stdout is None:
            return False
        self._bomba = threading.Thread(
            target=self._bombear, name=f"canal-do-mic-{self.uniq}", daemon=True
        )
        self._bomba.start()
        return True

    def _bombear(self) -> None:
        fluxo = self._proc.stdout
        try:
            while not self._parando.is_set():
                pedaco = fluxo.read(_PEDACO_BYTES)
                if not pedaco:
                    break
                self.source.escrever(pedaco)
        except (OSError, ValueError):
            # O processo morreu por baixo, ou o fluxo foi fechado pelo `parar`.
            # Nenhuma das duas é erro: são o fim do canal, visto de dentro.
            logger.debug("canal_do_mic_bomba_terminou", exc_info=True)

    def parar(self) -> None:
        """Mata o alimentador PELO PROCESSO QUE NÓS LANÇAMOS, nunca por padrão.

        `Popen.terminate` age sobre o pid deste objeto. Um `pkill -f parec`
        mataria o `parec` da janela dela — e derrubar processo por padrão é
        como esta casa já derrubou o compositor uma vez.
        """
        self._parando.set()
        proc = self._proc
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=_ESPERA_PELO_FIM_S)
            except Exception:
                # O `terminate` não bastou (ou nem chegou). Insiste, e ESPERA de
                # novo: colher o processo é o que evita deixar um zumbi para
                # cada canal que ela abre e fecha.
                matar = getattr(proc, "kill", None)
                if matar is not None:
                    with contextlib.suppress(Exception):
                        matar()
                        proc.wait(timeout=_ESPERA_PELO_FIM_S)
            saida = getattr(proc, "stdout", None)
            if saida is not None:
                with contextlib.suppress(OSError):
                    saida.close()
        bomba = self._bomba
        if bomba is not None and bomba.is_alive():
            bomba.join(timeout=_ESPERA_PELO_FIM_S)
        self._proc = None
        self._bomba = None


def _lancar_processo(argv: list[str]) -> Any:
    """O `Popen` de verdade. Isolado para a régua trocá-lo por um dublê."""
    # argv fixo e sem shell: `shell=True` é invariante proibido nesta casa.
    return subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)


def _rodar_pactl(argv: list[str]) -> bool:
    """Um `pactl` curto, com teto. Isolado para a régua trocá-lo por um dublê:
    **nenhum teste desta casa pode falar com o PipeWire da máquina dela.**
    """
    # argv fixo e sem shell: `shell=True` é invariante proibido nesta casa.
    return (
        subprocess.run(
            argv, capture_output=True, timeout=_TIMEOUT_PACTL_S, check=False
        ).returncode
        == 0
    )


def desmutar(nome: str, *, rodar: Any = None) -> bool:
    """Tira o mudo DE FÁBRICA do nó que acabamos de criar.

    **MEDIDO NA MÁQUINA DELA EM 06/09/2026, e é o defeito que calava o canal
    inteiro** (PipeWire 1.6.8)::

        module-pipe-source recém-carregado, nome NUNCA visto  →  Mute: yes
        app gravando do canal, com o mudo de fábrica          →  192000 B, pico 0
        o MESMO canal, depois de `set-source-mute … 0`        →  192000 B, pico 20000

    Todo ``module-pipe-source`` nasce mudo nesta versão — não é estado
    restaurado: um nome sorteado, que nunca existiu, nasce mudo igual. E mudo
    ele entrega BYTES, não silêncio detectável por quem conta bytes: 192 KB de
    zeros, o que se lê como *"a ponte está decodificando e não sai áudio"* — o
    sintoma que a ponte de rádio documenta como sendo do WirePlumber parado.

    **NÃO É O MUDO DELA.** O nó nasceu neste instante, com um nome que só nós
    escrevemos; não há escolha de usuário para atropelar aqui. O mudo do
    microfone dela continua sendo o do firmware, que este módulo não toca.

    **O MESMO DEFEITO ESTÁ VIVO NA PONTE DE RÁDIO**
    (``integrations/dualsense_bt_audio.py``), que publica pelo mesmo mecanismo e
    não desmuta. Está RELATADO e não curado: aquele arquivo é do
    ``nao_toca`` desta sprint.

    ``False`` = não deu, e **nunca levanta**: o caminho até aqui é o toque dela
    no botão do microfone, e nem o `pactl` ausente nem um servidor de som morto
    podem virar traceback no laço do daemon.
    """
    try:
        return bool((rodar or _rodar_pactl)(["pactl", "set-source-mute", nome, "0"]))
    except Exception:
        logger.warning("canal_do_mic_nao_desmutou", exc_info=True)
        return False


#: Os canais de pé, por `uniq`. O módulo é o dono do ciclo de vida, e o dono
#: precisa saber o que já subiu: pedir duas vezes o mesmo canal é o caminho
#: normal (duas abas, dois cliques), e carregar dois `module-pipe-source` com o
#: mesmo `source_name` publicaria dois nós disputando um nome só.
_DE_PE: dict[str, SourceVirtualPipeWire] = {}

#: Os alimentadores de pé, pelo mesmo `uniq`. Tabela SEPARADA de propósito: um
#: canal pode existir sem alimentador (o do rádio, que a MIC-VIRTUAL-02 enche
#: por `escrever`), e um alimentador nunca existe sem canal.
_ALIMENTANDO: dict[str, _Alimentador] = {}
_TRANCA = threading.Lock()


def abrir(
    uniq: str,
    descricao: str,
    *,
    fonte: str | None = None,
    fabrica: Any = None,
    lancar: Any = None,
    rodar: Any = None,
) -> SourceVirtualPipeWire | None:
    """Sobe o canal deste controle, ou devolve o que já estava de pé.

    `None` = não deu, e **nada ficou pela metade** — o contrato é o do
    `SourceVirtualPipeWire.iniciar`, que desfaz o que subiu antes de devolver
    `False`. Nunca levanta: o caminho até aqui é o toque dela no botão do
    microfone, e um traceback no laço do daemon é pior que uma recusa.

    `fonte` é o nó de onde o áudio VEM — o nó ALSA do cabo daquele controle,
    resolvido por `fontes_de_captura.escolher_fonte` **antes** de o canal subir
    (depois dele a regra 0 responde o próprio canal, que é a resposta certa para
    quem pergunta "qual é o microfone dele" e a errada para quem pergunta "de
    onde eu leio"). `None` publica o nó e não o alimenta: é o caminho do rádio,
    que enche o mesmo nó por `escrever` — e é a MIC-VIRTUAL-02 que o liga.

    **O canal SOBE mesmo que o alimentador não suba.** Um nó publicado e mudo é
    recuperável — o rádio pode enchê-lo, e a próxima tentativa reabre o cabo;
    derrubar o nó tiraria dela o canal inteiro por causa de um `parec` ausente.

    **E O NÓ NASCE MUDO** — medido, e é o que calava o canal inteiro. Ver
    :func:`desmutar`: o ``set-source-mute`` vem logo depois do `iniciar`, antes
    de qualquer alimentação, porque um canal que entrega 192 KB de zeros é pior
    que um canal que não sobe.

    `fabrica`, `lancar` e `rodar` existem para a régua: trocam o mecanismo, o
    processo e o `pactl` por dublês sem tocar no PipeWire nem no áudio da
    máquina. Em produção são `None`.
    """
    nome = nome_do_canal(uniq)
    if not nome:
        logger.debug("canal_do_mic_sem_identidade", extra={"uniq": uniq})
        return None
    with _TRANCA:
        ja = _DE_PE.get(uniq)
        if ja is not None:
            return ja
        construir = fabrica or SourceVirtualPipeWire
        try:
            source = construir(nome=nome, descricao=descricao)
            if not source.iniciar():
                return None
        except Exception:  # o gesto dela não vira traceback
            logger.warning("canal_do_mic_nao_subiu", exc_info=True)
            return None
        _DE_PE[uniq] = source
        if not desmutar(nome, rodar=rodar):
            # Não derruba o canal: o nó existe e alguém pode desmutá-lo à mão.
            # Mas fica no log, porque o sintoma do mudo é indistinguível de
            # "a ponte não está entregando áudio".
            logger.warning("canal_do_mic_nasceu_mudo", extra={"source": nome})
        if fonte:
            alimentador = _Alimentador(uniq, fonte, source, lancar=lancar)
            if alimentador.iniciar():
                _ALIMENTANDO[uniq] = alimentador
        return source


def fechar(uniq: str) -> bool:
    """Derruba o canal deste controle. False = não havia nada de pé.

    O canal MORRE COM O ÚLTIMO PEDIDO, e não com a desconexão: um controle que
    pisca no cabo (o caso do hub sobrecarregado, medido nesta casa) derrubaria e
    subiria o nó a cada piscada, e todo app que estivesse gravando perderia a
    fonte no meio da frase.

    **O ALIMENTADOR MORRE PRIMEIRO, e a ordem não é detalhe:** parar a source
    antes fecharia a ponta de leitura do fifo com o `parec` ainda escrevendo, e
    o que sobra disso é um processo vivo gravando o microfone dela sem nó
    nenhum para onde mandar.
    """
    with _TRANCA:
        source = _DE_PE.pop(uniq, None)
        alimentador = _ALIMENTANDO.pop(uniq, None)
    if alimentador is not None:
        try:
            alimentador.parar()
        except Exception:
            logger.warning("canal_do_mic_alimentador_nao_parou", exc_info=True)
    if source is None:
        return False
    try:
        source.parar()
    except Exception:
        logger.warning("canal_do_mic_nao_parou", exc_info=True)
    return True


def de_pe() -> dict[str, str]:
    """`{uniq: nome do nó}` do que está publicado agora. Cópia, não a tabela."""
    with _TRANCA:
        return {uniq: source.nome for uniq, source in _DE_PE.items()}


def alimentando() -> dict[str, str]:
    """`{uniq: nó de onde o áudio vem}` — quem está sendo enchido, e por onde.

    Diferente de :func:`de_pe` de propósito: um canal publicado e MUDO é estado
    legítimo (o do rádio, e o do cabo cujo `parec` não subiu), e colapsar os
    dois faria "o nó existe" parecer "o microfone está entrando".
    """
    with _TRANCA:
        return {uniq: alim.fonte for uniq, alim in _ALIMENTANDO.items()}


def prioridade() -> int:
    """A `priority.session` do canal — a MESMA faixa do cabo, lida do dono.

    Não é um número deste arquivo. `PRIORIDADE_SESSAO_DA_PONTE` carrega a
    medição de 03/09/2026 na máquina dela e o invariante que ela materializa:
    *um microfone de verdade nunca pode perder para um monitor*. Um literal aqui
    repetiria, na íntegra, o defeito que aquele comentário registra.
    """
    return PRIORIDADE_SESSAO_DA_PONTE
