"""A luz do botão de microfone diz QUEM TE ESCUTA — o laço que decide e escreve.

LUZ-DO-MIC-01, PEÇA C (03/09/2026). Este módulo é o único que ESCREVE no
`common[8]` por decisão de estado; as peças A e B só respondem perguntas.

**O CONTRATO, e ele é decisão dela** (`docs/process/sprints/
2026-09-02-LUZ-DO-MIC-01-a-luz-diz-quem-te-escuta.md` §1)::

    apagado (0)      = MUDO, ou ninguém ouvindo.  OS DOIS SÃO A MESMA LUZ.
    aceso fixo (1)   = algum app está com o microfone deste controle aberto
    piscando (2)     = e está entrando som AGORA
    pisca lento (3)  = está entrando som, E a bateria deste controle < 30%

A precedência está em `decidir`, e ela é a §1.1 escrita em código.

**A LUZ INVERTE O KERNEL, e isso é o ponto inteiro.** O `hid-playstation`
escreve `mute_button_led = ds->mic_muted` (`hid-playstation.c:1538-1540`): para
ele, luz ACESA quer dizer MUDO. Aqui é o contrário — palavra dela: *"confuso
mudo e apagado tem que ser sinonimos aqui"*. Enquanto a posse do byte for
nossa, o firmware obedece a nós e o kernel não pinta nada; por isso a devolução
da posse tem de REPINTAR na língua do KERNEL antes de soltar (ver
`_devolver`), senão a luz fica presa no nosso vocabulário sobre um byte que
voltou a ser dele.

**O QUE ESTE LAÇO NÃO FAZ, e cada linha é requisito da §3:**

* **não toca o `common[9]`** — o mudo é campo separado, com bit de autorização
  separado, e as três recusas medidas (BT-E-VPAD-01, MIC-BT-DONO-01,
  MIC-DOIS-DONOS-01) são todas sobre ele. Aqui só se chama
  `set_microphone_led`, que mexe em `common[8]` e no bit `0x01` do flag1;
* **não abre o hidraw** — escrever cru por fora é a armadilha nº 3 do
  `CLAUDE.md`: o daemon reafirma o report de saída e a escrita crua morre em
  milissegundos. Tudo passa pelo backend;
* **não rouba o botão físico dela** — o gesto continua sendo do
  `hid-playstation` (que alterna `ds->mic_muted`) e do `mic_da_mesa`/`hotkey`
  (que elege). Este laço só LÊ o mudo e pinta;
* **não reafirma o mesmo valor** — escreve só na MUDANÇA. Reafirmar a cada
  tique por cima do kernel é literalmente o defeito do commit `3d9bb7e` no
  byte vizinho, e é o requisito que o teste do tempo morde.

**POR QUE `set_microphone_led` E NÃO `set_mic_led`, e isto não é preferência.**
Medido nesta árvore em 03/09/2026: `set_mic_led` coage a `bool` DUAS VEZES em
série (`core/backend_pydualsense.py:3995`, `flag = bool(aceso)`, e `:372`,
`tomar(bool(aceso))`), então `2` e `3` viram `1` sem erro e sem log — luz acesa
fixa onde devia piscar, que se lê como *"a PEÇA B não está detectando som"*. O
único caminho de produção que carrega o nível é
`PyDualSenseController.set_microphone_led(aceso, *, uniq=)`
(`core/backend_pydualsense.py:4408`), medido: `0->0, 1->1, 2->2, 3->3`.

**DUAS CADÊNCIAS NUM LAÇO SÓ, e o número tem razão.** A decisão roda a
`INTERVALO_S` (4 Hz) porque o `2` é atividade de voz e a 1 Hz a luz acompanha o
parágrafo, não a fala. A PEÇA A é a cara — três `pactl` por leitura, 6,8 ms de
CPU medidos, e a própria sprint pede *"leitura de ~1 Hz"* — então ela é
perguntada a cada `INTERVALO_DE_QUEM_OUVE_S` e a resposta fica guardada entre
uma pergunta e outra. As leituras de mudo e bateria são `getattr` sobre o que a
thread de report já atualizou, sem HID I/O, e a da PEÇA B é um `dict` sob
`lock` — nenhuma das três paga processo por tique.

**TODO `pactl` SAI DO EVENT LOOP, e isto é requisito.** A PEÇA A dispara três
subprocessos com `timeout` de 3 s cada, e a resolução de fonte mais dois;
chamá-los de dentro da corrotina congelaria o mesmo loop que serve o IPC e
reafirma o report de saída — até 9 s no pior caso, com a máquina dela parecendo
travada. Tudo que fala com o mundo passa por `_fora_do_laco`, que é o
`daemon._run_blocking` com queda tolerante.

**COMO AS PEÇAS IRMÃS SÃO CHAMADAS, e as duas têm forma DIFERENTE.** Medido em
03/09/2026 contra os módulos de verdade — este laço já nasceu procurando quatro
nomes de função em cada uma, e para a PEÇA B nenhum dos quatro existia:

* a PEÇA A é uma FUNÇÃO — `quem_ouve_agora(uniqs) -> {uniq: [clientes]} | None`,
  e a docstring dela diz, com todas as letras, *"é esta a função que a PEÇA C
  chama"*;
* a PEÇA B é um OBJETO COM ESTADO — `NivelDoMicrofone`, dirigido por
  `seguir({uniq: fonte})` e lido por `captando() -> {uniq: bool|None}`. Ela
  segura processos `parec` VIVOS, e por isso o laço é dono dela: quem a cria é
  quem a PARA no `finally`. Um medidor que vaza prende a fonte de captura dela
  aberta indefinidamente — um `parec` órfão com o stdout em `/dev/null` nunca
  toma `SIGPIPE` e vive para sempre. Já aconteceu nesta bancada.

**O `seguir` precisa do NOME DA FONTE, e a PEÇA A não o devolve.** Ela responde
QUEM ouve, não POR ONDE. O nome sai das réguas que a casa já tem
(`fontes_de_captura_agora` + `casamento_usb_agora` + `escolher_fonte`), e só
para quem JÁ tem ouvinte: a §1.1 diz que o `2` só existe dentro do `1`, então
com a sala vazia não se resolve fonte, não se abre `parec`, e o medidor nem
chega a nascer — o custo é zero processo e zero por cento.

**AS PEÇAS PODEM NÃO EXISTIR, e a degradação é declarada.** O laço as procura
por `import` tolerante e, sem elas, entrega o que SABE decidir:

===========================  ===========================================
o que está no ar             o que a luz faz
===========================  ===========================================
nem A nem B                  apaga quando ela está MUDA; no resto,
                             devolve a posse ao kernel (não inventa)
A sem B                      0 / 1 completos — acende quando um app tem
                             o microfone aberto, sem distinguir o `2`
A e B                        os quatro estados
===========================  ===========================================

**AUSÊNCIA NÃO É NEGAÇÃO.** `audio_status_for` devolve `None` para o controle
que ainda não reportou, e `None` **não** é `False`: tratá-lo como *"não está
muda"* acenderia a luz de um controle que acabou de chegar e ainda não disse
nada — é o mesmo `bool(None)` que esta casa já publicou como ATIVO sobre um
controle que tinha acabado de cair. Por isso `decidir` devolve `None` (*"não
sei, não escreva"*), que é um valor de primeira classe aqui.

**A INVALIDAÇÃO PELA BORDA, e ela existe porque há DOIS escritores.** A
eleição (`hotkey._eleger_ou_devolver`) também escreve neste byte, por
`set_mic_led(aceso, uniq=)`, na borda do botão. Se este laço confiasse na
memória do que ELE escreveu, um valor posto pela eleição ficaria de pé para
sempre (nós não reescrevemos o que achamos já estar lá). Então o laço assina
`EventTopic.MIC_DA_MESA` — a mesma borda que a eleição consome, já com sossego
e carência aplicados pelo `mic_da_mesa` — e ESQUECE o que escreveu naquele
`uniq`, reescrevendo no tique seguinte. Isso limita a briga a um tique em vez
de deixá-la eterna. **A briga em si é decisão de quem coordena**, e está no
relatório: ou a eleição para de escrever a luz (arquivo alheio), ou os dois
alternam visivelmente.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:  # pragma: no cover - só para tipo
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

#: Os quatro estados do `common[8]`, medidos no aparelho com o olho dela
#: (sprint §0). A faixa é `0..3` e o produto **não** a filtra: quem valida é o
#: firmware (`255 & 0x03 = 3` e ele APAGA — logo ele valida a faixa, não
#: mascara bits), e um `clamp` aqui esconderia um pedido errado.
APAGADA: int = 0
ACESA: int = 1
PISCANDO: int = 2
PISCANDO_LENTO: int = 3

#: Cadência da DECISÃO. O `2` é atividade de voz, que muda em ~100 ms; a 1 Hz a
#: luz acompanharia o parágrafo e não a fala. A 4 Hz nada disto custa: as
#: leituras deste tique (mudo e bateria) são `getattr` sobre o que a thread de
#: report da pydualsense já atualizou, sem HID I/O.
INTERVALO_S: float = 0.25

#: Cadência de QUEM OUVE (PEÇA A). Ela é a leitura CARA — dois `pactl` por
#: pergunta, 6,8 ms de CPU medidos em 03/09/2026 —, e a sprint fixa o alvo:
#: *"Custo alvo: leitura de ~1 Hz, sem processo permanente"*. A resposta fica
#: guardada entre uma pergunta e outra, então a decisão continua a 4 Hz.
INTERVALO_DE_QUEM_OUVE_S: float = 1.0

#: O quarto estado é a bateria, e o número é dela: *"pisca lento, se a bateria
#: do controle tiver abaixo de 30%"*. Abaixo, não abaixo-ou-igual.
LIMIAR_DE_BATERIA_PCT: int = 30

#: Quanto esperar, depois de REPINTAR, antes de soltar o bit `0x01`. O report
#: de saída sai na thread do handle assim que o buffer MUDA
#: (`backend_pydualsense.sendReport`), com throttle de
#: `REPORT_THREAD_THROTTLE_SEC` (0,008 s) escalado por controle até
#: `REPORT_THREAD_THROTTLE_MAX_SEC` (0,032 s). 150 ms são ~5 ciclos do pior
#: caso: folga para a repintura chegar ao aparelho antes de a posse cair.
#: Soltar sem esperar é o §2 da sprint acontecendo de novo — *"ambos tão
#: ligados. e ficaram."*
ESPERA_DO_REPORT_S: float = 0.15

#: Quanto tempo o laço segura a posse quando parou de saber decidir, antes de
#: devolvê-la ao kernel. Devolver na PRIMEIRA não-resposta faria um `pactl`
#: que estourou o `timeout` uma vez virar um pisca-pisca de posse; nunca
#: devolver deixaria a luz travada no último valor (um `2` eterno) quando a
#: PEÇA A cai de vez. Três segundos são doze tiques: uma falha isolada passa
#: batida, uma falha real vira devolução.
SEM_RESPOSTA_ATE_SOLTAR_S: float = 3.0

#: A PEÇA A: uma FUNÇÃO, e o nome é fixo dos dois lados. Contrato:
#: `{uniq: [nomes dos clientes]}`, e `None` quando não dá para saber.
#:
#: **FATO SUBSTITUÍDO, 03/09/2026.** Isto já foi uma TUPLA de quatro nomes
#: candidatos, de quando as peças nasciam na mesma leva e o nome ainda não
#: estava fixado. Ele está — a docstring de `quem_ouve_agora` diz *"é esta a
#: função que a PEÇA C chama"* —, e a lista custou caro no vizinho: procurar
#: quatro nomes e não achar nenhum é uma junta MORTA que se lê como *"a peça
#: irmã respondeu que não há som"*. Um nome, e o laço loga se não o achou.
MODULO_DE_QUEM_OUVE: str = "hefesto_dualsense4unix.integrations.quem_ouve_o_microfone"
NOME_DE_QUEM_OUVE: str = "quem_ouve_agora"

#: A PEÇA B: uma CLASSE com estado, não uma função. Dirigida por
#: `seguir({uniq: fonte})` e lida por `captando() -> {uniq: bool|None}`, já com
#: histerese (sem ela o pisca vira estroboscópio em cada sílaba). `None`
#: naquele `uniq` é *"não medi"*, e não *"não há som"*.
#:
#: **A JUNTA ESTAVA MORTA e nenhum teste via.** Este laço procurava aqui as
#: funções `captando_agora`/`esta_captando_agora`/`nivel_agora`/
#: `captando_por_uniq`; a PEÇA B não publica nenhuma das quatro. Medido em
#: 03/09/2026: `captando` ficava `None` para sempre e os estados `2` e `3`
#: eram inalcançáveis — metade do contrato dela, morta em silêncio. A suíte
#: passava porque o dublê PLANTAVA `captando_agora`, que só existia no teste.
MODULO_DO_NIVEL: str = "hefesto_dualsense4unix.integrations.nivel_do_microfone"
NOME_DO_MEDIDOR: str = "NivelDoMicrofone"


def decidir(
    *,
    mudo: bool | None,
    ouvintes: list[str] | None,
    captando: bool | None,
    bateria_pct: int | None,
) -> int | None:
    """A §1.1 da sprint, em código. Devolve o estado, ou `None` para *"não sei"*.

    A precedência, na ordem::

        mudo no firmware                         -> 0
        captando + bateria < 30%                 -> 3
        captando                                 -> 2
        algum app com o microfone aberto         -> 1
        resto                                    -> 0

    **O `None` é um valor de primeira classe, e não um buraco.** Ele sai em
    duas situações, e as duas são honestas:

    * `mudo is None` — o controle ainda não reportou o byte de estado de áudio.
      Chutar `False` acenderia a luz de quem acabou de chegar; chutar `True`
      apagaria a de quem está falando. A resposta certa é não escrever;
    * `ouvintes is None` — a PEÇA A não existe, não achou o `pactl`, ou não
      conseguiu ler o grafo. *"Não perguntei a ninguém"* não é *"ninguém
      ouve"*: a lista VAZIA (`[]`) é que significa ninguém, e ela acende o
      `0` com todas as letras.

    **`mudo` vence tudo**, inclusive a ausência da PEÇA A — é por isso que a
    degradação sem A e sem B ainda entrega alguma coisa: a luz apaga quando ela
    aperta o botão, que é a metade do contrato que não depende de ninguém.

    **A bateria só modula um aviso que já existe.** `bateria_pct is None` é o
    firmware que ainda não reportou a carga, e ausência não vira `3`: o estado
    cai para `2`, que continua verdadeiro. E bateria baixa SEM captação não
    acende nada — a luz é sobre quem te escuta.
    """
    if mudo is True:
        return APAGADA
    if mudo is None:
        return None
    if ouvintes is None:
        return None
    if not ouvintes:
        return APAGADA
    if captando is True:
        if bateria_pct is not None and bateria_pct < LIMIAR_DE_BATERIA_PCT:
            return PISCANDO_LENTO
        return PISCANDO
    return ACESA


def _mudo(backend: Any, uniq: str) -> bool | None:
    """O mudo do FIRMWARE daquele controle, ou `None` quando ele não disse.

    `audio_status_for` é a leitura direta do byte de estado que veio no report
    de INPUT (`core/backend_pydualsense.py:4033`). **Não é `microphone_mute_for`
    de propósito**: aquele diz quem MANDA (o valor que o Hefesto afirma), não o
    que está valendo no aparelho, e a §1.1 fala do firmware.
    """
    ler = getattr(backend, "audio_status_for", None)
    if not callable(ler):
        return None
    try:
        estado = ler(uniq)
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("luz_do_mic_mudo_falhou", uniq=uniq, err=str(exc))
        return None
    if not isinstance(estado, dict):
        return None
    valor = estado.get("mic_mudo")
    return valor if isinstance(valor, bool) else None


def _baterias(backend: Any) -> dict[str, int]:
    """`{uniq: battery_pct}` dos controles conectados. Só quem reportou entra.

    `describe_controllers` já devolve a carga por controle
    (`core/backend_pydualsense.py:5413`) e a leitura é `getattr` no objeto que
    a thread de report atualiza — sem HID I/O, e já há três consumidores do
    daemon pagando esse preço por tique.

    Quem não reportou a carga NÃO entra no dicionário, em vez de entrar com
    `None`: assim `bateria_pct is None` em `decidir` significa uma coisa só —
    *"não sei a carga"* — venha ela da chave ausente ou do backend calado.
    """
    descrever = getattr(backend, "describe_controllers", None)
    if not callable(descrever):
        return {}
    try:
        itens = descrever()
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("luz_do_mic_bateria_falhou", err=str(exc))
        return {}
    if not isinstance(itens, list):
        return {}
    out: dict[str, int] = {}
    for item in itens:
        if not isinstance(item, dict):
            continue
        uniq = item.get("uniq")
        carga = item.get("battery_pct")
        if isinstance(uniq, str) and uniq and isinstance(carga, int):
            out[uniq] = carga
    return out


def _da_peca(caminho: str, nome: str, cache: dict[str, Any]) -> Any:
    """Resolve UM nome num módulo irmão, uma vez só, tolerando a ausência.

    **Isto é requisito, não contorno.** As peças A e B nascem na mesma leva que
    este laço e podem chegar depois; um `import` no topo faria a ausência de
    uma delas derrubar o subsistema inteiro no boot, e um subsistema derrubado
    no boot é a luz morta sem ninguém saber por quê.

    O `cache` guarda o que foi achado (ou o `None` de *"não achei"*) para não
    repetir a busca a cada tique, e para o aviso sair UMA vez em vez de a 4 Hz
    no journal dela.

    **Um nome, não uma lista de candidatos.** Procurar quatro e não achar
    nenhum devolve o mesmo `None` de *"a peça não existe"*, e foi assim que a
    junta com a PEÇA B ficou morta sem ninguém ver: o `luz_do_mic_peca_ligada`
    nunca saía no journal, e nada olhava para a ausência dele.
    """
    chave = f"{caminho}:{nome}"
    if chave in cache:
        return cache[chave]
    achado = None
    try:
        modulo = importlib.import_module(caminho)
    except Exception as exc:
        # `Exception` e não `ImportError`: uma peça irmã que existe mas quebra
        # ao importar (um `SyntaxError` no meio da leva, uma dependência que
        # faltou) não pode derrubar o subsistema da luz.
        logger.info("luz_do_mic_peca_ausente", modulo=caminho, err=str(exc))
        modulo = None
    if modulo is not None:
        candidata = getattr(modulo, nome, None)
        if callable(candidata):
            achado = candidata
            logger.info("luz_do_mic_peca_ligada", modulo=caminho, nome=nome)
        else:
            logger.warning("luz_do_mic_peca_sem_funcao", modulo=caminho, nome=nome)
    cache[chave] = achado
    return achado


async def _fora_do_laco(daemon: Any, fn: Any, *args: Any) -> Any:
    """Roda `fn` fora do event loop, caindo para a chamada direta se não der.

    O que passa por aqui fala com o mundo: a PEÇA A são três `pactl` com
    `timeout` de 3 s cada, e a resolução de fonte são mais dois. Congelar o
    event loop por isso pararia o IPC e a reafirmação do report de saída — e o
    pior caso, 9 s, se lê como a máquina dela travando.

    A queda para a chamada direta existe porque `_run_blocking` exige o
    executor montado (`daemon/lifecycle.py:4860` afirma isso), e um daemon
    dublado ou meio subido não o tem. Bloquear um teste é aceitável; derrubar
    a luz por causa dele não é.
    """
    correr = getattr(daemon, "_run_blocking", None)
    if callable(correr):
        try:
            return await correr(fn, *args)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("luz_do_mic_sem_executor", err=str(exc))
    return fn(*args)


def _quem_ouve(uniqs: list[str], cache: dict[str, Any]) -> dict[str, Any] | None:
    """A PEÇA A: `{uniq: [clientes]}`, ou `None` para *"não sei"*.

    **BLOQUEIA** — até três `pactl`. Só se chama por `_fora_do_laco`.

    O retorno é aceito só quando é `dict`, e a própria PEÇA A registra o porquê
    no lugar dela: devolver a leitura rica aqui não daria erro nenhum — daria a
    luz apagada para sempre, com o laço descartando toda resposta em silêncio.
    """
    funcao = _da_peca(MODULO_DE_QUEM_OUVE, NOME_DE_QUEM_OUVE, cache)
    if funcao is None:
        return None
    try:
        valor = funcao(uniqs)
    except Exception as exc:
        logger.warning(
            "luz_do_mic_peca_falhou", modulo=MODULO_DE_QUEM_OUVE, err=str(exc)
        )
        return None
    return valor if isinstance(valor, dict) else None


def _com_ouvinte(ouvintes_por_uniq: dict[str, Any] | None) -> list[str]:
    """Os `uniq` que a PEÇA A disse ter ouvinte — e só eles vão para o medidor.

    A §1.1 é a razão: o `2` (piscando) só existe DENTRO do `1` (algum app com o
    microfone aberto). Medir quem ninguém está ouvindo abriria um `parec` para
    responder uma pergunta que a precedência já respondeu.
    """
    if not ouvintes_por_uniq:
        return []
    return [
        uniq
        for uniq, clientes in ouvintes_por_uniq.items()
        if isinstance(uniq, str) and isinstance(clientes, (list, tuple)) and clientes
    ]


def _fontes_para(uniqs: list[str], mesa: list[str]) -> dict[str, str]:
    """`{uniq: nome da fonte}` para quem tem ouvinte — com as réguas da casa.

    **Reuso, não reimplementação.** `fontes_de_captura_agora` lista as sources
    de DualSense, `casamento_usb_agora` diz quem pendura em qual dispositivo, e
    `escolher_fonte` aplica as quatro regras de atribuição (MAC inteiro no nome
    bluez · rabo do MAC da ponte BT · mesmo dispositivo USB · um-para-um com
    veto). Escrever uma quinta régua sobre o mesmo estado é o defeito que esta
    casa já pagou onze vezes.

    Existe porque a PEÇA A responde QUEM ouve e não POR ONDE: `seguir` precisa
    do nome da fonte para passar o `--device=` ao `parec`.

    **BLOQUEIA** — dois `pactl`. Só se chama por `_fora_do_laco`, e só com
    `uniqs` não vazio: com a sala vazia sai `{}` sem gastar processo nenhum.
    """
    if not uniqs:
        return {}
    try:
        from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
            casamento_usb_agora,
            fontes_de_captura_agora,
        )
        from hefesto_dualsense4unix.integrations.fontes_de_captura import escolher_fonte
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("luz_do_mic_sem_reguas_de_fonte", err=str(exc))
        return {}
    try:
        fontes = fontes_de_captura_agora()
        if not fontes:
            return {}
        usb = casamento_usb_agora(mesa)
        achadas: dict[str, str] = {}
        for uniq in uniqs:
            fonte = escolher_fonte(fontes, uniq, mesa, usb)
            if fonte:
                achadas[uniq] = fonte
        return achadas
    except Exception as exc:
        logger.warning("luz_do_mic_fonte_falhou", err=str(exc))
        return {}


def _medidor(cache: dict[str, Any]) -> Any:
    """A PEÇA B, construída na PRIMEIRA vez que alguém ouve — e não antes.

    Ela sobe uma thread e passa a segurar processos `parec`; construí-la no
    boot faria uma máquina onde ninguém nunca abre o microfone pagar uma thread
    parada para sempre. **Quem a cria é quem a PARA** — ver o `finally` de
    `luz_do_mic_loop`.
    """
    if "medidor" in cache:
        return cache["medidor"]
    classe = _da_peca(MODULO_DO_NIVEL, NOME_DO_MEDIDOR, cache)
    instancia = None
    if classe is not None:
        try:
            instancia = classe()
        except Exception as exc:
            logger.warning("luz_do_mic_medidor_recusou", err=str(exc))
    cache["medidor"] = instancia
    return instancia


def _seguir(medidor: Any, alvos: dict[str, str]) -> None:
    """Diz ao medidor exatamente quem medir. Idempotente do lado dele."""
    if medidor is None:
        return
    seguir = getattr(medidor, "seguir", None)
    if not callable(seguir):
        return
    try:
        seguir(alvos)
    except Exception as exc:
        logger.warning("luz_do_mic_seguir_falhou", err=str(exc))


def _captando(medidor: Any) -> dict[str, Any] | None:
    """`{uniq: bool|None}` do medidor. Sem HID I/O e sem processo: é um `dict`."""
    if medidor is None:
        return None
    ler = getattr(medidor, "captando", None)
    if not callable(ler):
        return None
    try:
        valor = ler()
    except Exception as exc:
        logger.warning("luz_do_mic_nivel_falhou", err=str(exc))
        return None
    return valor if isinstance(valor, dict) else None


def _parar_medidor(medidor: Any) -> None:
    """Mata os `parec` e a thread do medidor. **Não é opcional.**

    Um `parec` órfão segura a fonte de captura DELA aberta para sempre: o
    stdout vai para `/dev/null`, então ele nunca toma `SIGPIPE`, e o cgroup em
    que nasce não é unit do Hefesto — um `systemctl --user stop` do daemon não
    o recolhe. Medido nesta bancada em 03/09/2026, com um vazado vivo há 25
    minutos.
    """
    if medidor is None:
        return
    parar = getattr(medidor, "parar", None)
    if not callable(parar):
        return
    try:
        parar()
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("luz_do_mic_medidor_nao_parou", err=str(exc))


def _escrever(backend: Any, uniq: str, valor: int | None) -> bool:
    """`set_microphone_led(valor, uniq=)`, tolerando backend sem endereço.

    **NÃO É `set_mic_led`.** Aquele esmaga em `bool` duas vezes em série e faz
    o `2` e o `3` virarem `1` sem erro e sem log (medido em 03/09/2026,
    `core/backend_pydualsense.py:3995` e `:372`).

    `valor is None` é a DEVOLUÇÃO DA POSSE (o bit `0x01` do flag1 cai e o
    kernel volta a escrever a luz na borda do botão); `0` é uma ORDEM
    ("apaga"), com a posse mantida. Confundir os dois é o defeito do commit
    `3d9bb7e` no byte vizinho.

    A escrita **não é HID I/O**: `_PinnedPyDualSense.set_microphone_led` só
    guarda `_mic_led_desejado` (`core/backend_pydualsense.py:1117`), e quem
    manda o report é a thread do handle. É por isso que ela pode ser chamada
    direto no `finally` do desligamento, quando não há executor garantido.
    """
    escrever = getattr(backend, "set_microphone_led", None)
    if not callable(escrever):
        # Medido em 02/09/2026: nem `core/controller.IController` nem o
        # `FakeController` da suíte declaram este método — só o
        # `PyDualSenseController`. Sair calado daqui seria o log dizendo que a
        # luz mudou quando ela não mudou.
        logger.warning("luz_do_mic_sem_backend", uniq=uniq)
        return False
    try:
        escrever(valor, uniq=uniq)
    except TypeError:
        logger.warning("luz_do_mic_sem_endereco", uniq=uniq)
        with contextlib.suppress(Exception):
            escrever(valor)
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("luz_do_mic_escrita_falhou", uniq=uniq, err=str(exc))
        return False
    return True


async def _devolver(
    backend: Any,
    uniqs: list[str],
    escrito: dict[str, int],
    posse: set[str],
) -> int:
    """REPINTA na língua do kernel, espera o report sair, e SOLTA a posse.

    Este é o §2 da sprint, e ele nasceu de uma medição com ela olhando os dois
    controles: *"ambos tão ligados. e ficaram."* A causa está no contrato do
    kernel — ele escreve `mute_button_led = ds->mic_muted` **na borda do botão
    físico**, não continuamente (`hid-playstation.c:1538-1540`). Então largar o
    byte com a luz no NOSSO vocabulário deixa a mentira no ar até ela apertar o
    botão.

    **A repintura é na língua do KERNEL, e essa inversão é o miolo da função.**
    Nosso contrato é *mudo = apagado*; o do kernel é *aceso = mudo*. Como o
    byte está voltando para ele, o valor a deixar é `ACESA` quando ela está
    muda e `APAGADA` quando não está — o contrário do que este laço pinta
    enquanto a posse é nossa. Repintar no nosso vocabulário deixaria a luz
    discordando do kernel até a próxima borda, que é o mesmo defeito com outra
    roupa.

    **A ORDEM É REPINTAR, ESPERAR, SOLTAR — e a espera não é decoração.** O
    report só sai quando o buffer MUDA, na thread do handle; repintar e soltar
    no mesmo instante faria as duas mudanças caberem no mesmo report, e o
    aparelho nunca veria a repintura.

    Se o `await` for cancelado (a task já está morrendo), a repintura JÁ foi
    aplicada e a posse fica nossa: é o desfecho seguro dos dois. A luz mostra a
    verdade, e a posse de um daemon morto não escreve mais nada — o kernel
    reassume na borda seguinte de qualquer jeito.
    """
    alvos = [uniq for uniq in uniqs if uniq in posse]
    if backend is None or not alvos:
        return 0
    for uniq in alvos:
        # `None` (o controle nunca reportou) vira APAGADA: uma luz apagada é a
        # entrega mais segura para o kernel, que a repinta na borda seguinte.
        _escrever(backend, uniq, ACESA if _mudo(backend, uniq) else APAGADA)
    try:
        await asyncio.sleep(ESPERA_DO_REPORT_S)
    except asyncio.CancelledError:
        logger.warning("luz_do_mic_posse_retida", controles=len(alvos))
        raise
    for uniq in alvos:
        _escrever(backend, uniq, None)
        escrito.pop(uniq, None)
        posse.discard(uniq)
    logger.info("luz_do_mic_posse_devolvida", controles=len(alvos))
    return len(alvos)


async def luz_do_mic_loop(daemon: DaemonProtocol) -> None:
    """Decide o estado de cada controle da mesa e escreve — só na MUDANÇA.

    A memória do laço é local e por `uniq`, como no `mic_da_mesa`:

    * ``escrito`` — o último valor que NÓS pusemos no byte daquele controle;
    * ``posse``   — de quem o bit `0x01` do flag1 é, no nosso entender.

    Os dois são separados porque a eleição também escreve neste byte: quando
    uma borda chega, esquecemos o VALOR (para reescrever o nosso no tique
    seguinte) mas continuamos sabendo que a POSSE é nossa (a eleição a tomou
    ao escrever).

    **Controle que sai da mesa perde a memória inteira**, e não é higiene: na
    reconexão o handle é NOVO e não tem lembrança do que escrevemos no velho.
    Guardar o valor antigo faria o laço achar que o byte já está certo e nunca
    reescrevê-lo — a luz nasceria errada e ficaria.
    """
    relogio = asyncio.get_running_loop().time
    escrito: dict[str, int] = {}
    posse: set[str] = set()
    sem_resposta_desde: dict[str, float] = {}
    cache_das_pecas: dict[str, Any] = {}
    ouvintes_por_uniq: dict[str, Any] | None = None
    perguntei_em = float("-inf")
    medidor: Any = None

    fila: Any = None
    inscrever = getattr(getattr(daemon, "bus", None), "subscribe", None)
    if callable(inscrever):
        with contextlib.suppress(Exception):
            fila = inscrever(_TOPICO_DA_BORDA)

    try:
        while not daemon._is_stopping():
            await asyncio.sleep(INTERVALO_S)
            backend = getattr(daemon, "controller", None)
            if backend is None:
                continue
            agora = relogio()

            # A BORDA INVALIDA O QUE ACHAMOS TER ESCRITO. A eleição acabou de
            # pôr um valor no byte por outro caminho; se guardássemos o nosso,
            # nunca o reescreveríamos e o valor dela ficaria de pé.
            if fila is not None:
                while True:
                    try:
                        evento = fila.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    except Exception:  # pragma: no cover - defensivo
                        break
                    alvo = evento.get("uniq") if isinstance(evento, dict) else None
                    if isinstance(alvo, str) and alvo:
                        escrito.pop(alvo, None)
                        posse.add(alvo)

            mesa = mesa_de_agora(daemon)
            if mesa is None:
                # "Não perguntei a ninguém" não é "a mesa esvaziou": um backend
                # que não sabe listar não pode fazer o laço soltar a posse de
                # todo mundo. Ficamos parados até ele saber responder.
                continue
            for uniq in [u for u in escrito if u not in mesa] + [
                u for u in posse if u not in mesa
            ]:
                escrito.pop(uniq, None)
                posse.discard(uniq)
                sem_resposta_desde.pop(uniq, None)

            if (agora - perguntei_em) >= INTERVALO_DE_QUEM_OUVE_S:
                ouvintes_por_uniq = await _fora_do_laco(
                    daemon, _quem_ouve, mesa, cache_das_pecas
                )
                perguntei_em = agora
                # O MEDIDOR SEGUE SÓ QUEM JÁ TEM OUVINTE (§1.1: o `2` vive
                # dentro do `1`). Com a sala vazia não se resolve fonte, não se
                # abre `parec`, e o medidor nem chega a nascer.
                com_ouvinte = _com_ouvinte(ouvintes_por_uniq)
                if com_ouvinte and medidor is None:
                    medidor = _medidor(cache_das_pecas)
                if medidor is not None:
                    _seguir(
                        medidor,
                        await _fora_do_laco(daemon, _fontes_para, com_ouvinte, mesa),
                    )
            captando_por_uniq = _captando(medidor)
            baterias = _baterias(backend)

            for uniq in mesa:
                ouvintes = None
                if ouvintes_por_uniq is not None:
                    bruto = ouvintes_por_uniq.get(uniq)
                    ouvintes = list(bruto) if isinstance(bruto, (list, tuple)) else None
                captando = None
                if captando_por_uniq is not None:
                    bruto_b = captando_por_uniq.get(uniq)
                    captando = bruto_b if isinstance(bruto_b, bool) else None
                alvo = decidir(
                    mudo=_mudo(backend, uniq),
                    ouvintes=ouvintes,
                    captando=captando,
                    bateria_pct=baterias.get(uniq),
                )

                if alvo is None:
                    # PAROU DE SABER. Segurar para sempre deixaria um `2`
                    # eterno quando a PEÇA A cai; soltar na primeira falha
                    # faria um `pactl` que estourou o timeout virar um
                    # pisca-pisca de posse. Segura, e devolve se durar.
                    if uniq not in posse:
                        sem_resposta_desde.pop(uniq, None)
                        continue
                    desde = sem_resposta_desde.setdefault(uniq, agora)
                    if (agora - desde) >= SEM_RESPOSTA_ATE_SOLTAR_S:
                        logger.info("luz_do_mic_sem_resposta", uniq=uniq)
                        await _devolver(backend, [uniq], escrito, posse)
                        sem_resposta_desde.pop(uniq, None)
                    continue

                sem_resposta_desde.pop(uniq, None)
                if escrito.get(uniq) == alvo and uniq in posse:
                    # ESCREVE SÓ NA MUDANÇA. Reafirmar o mesmo valor a cada
                    # tique por cima do kernel é o commit `3d9bb7e` no byte
                    # vizinho, e é isto que o teste do TEMPO morde.
                    continue
                if await _fora_do_laco(daemon, _escrever, backend, uniq, alvo):
                    escrito[uniq] = alvo
                    posse.add(uniq)
                    logger.info("luz_do_mic_escrita", uniq=uniq, estado=alvo)
    finally:
        # O MEDIDOR MORRE NUM `finally` PRÓPRIO, e o aninhamento é o ponto: a
        # devolução abaixo tem um `await`, e um `await` pode ser cancelado. Se
        # a parada do medidor viesse depois dela, um segundo cancelamento
        # deixaria os `parec` vivos — com a fonte de captura DELA aberta e
        # ninguém lendo. A luz errada é um defeito; o microfone preso é dela.
        try:
            if fila is not None:
                desinscrever = getattr(getattr(daemon, "bus", None), "unsubscribe", None)
                if callable(desinscrever):
                    with contextlib.suppress(Exception):
                        desinscrever(_TOPICO_DA_BORDA, fila)
            # A DEVOLUÇÃO NO DESLIGAMENTO mora aqui porque o
            # `connection.shutdown` só sabe CANCELAR tasks
            # (`daemon/connection.py:1383-1384`) — um laço cancelado não repinta e
            # não solta nada. O `finally` roda com a cancelação já entregue, e
            # como o `shutdown` chama `cancel()` UMA vez por task, o `await` de
            # dentro de `_devolver` sobrevive; se não sobreviver, a repintura já
            # foi aplicada (ver `_devolver`).
            with contextlib.suppress(Exception):
                await _devolver(
                    getattr(daemon, "controller", None), sorted(posse), escrito, posse
                )
        finally:
            _parar_medidor(medidor)


def start_luz_do_mic(daemon: DaemonProtocol) -> None:
    """Sobe o laço da luz do microfone. Idempotente do ponto de vista de quem chama."""
    task = asyncio.create_task(luz_do_mic_loop(daemon), name="luz_do_mic_loop")
    daemon._tasks.append(task)
    logger.info("luz_do_mic_iniciado")


def _topico_da_borda() -> str:
    from hefesto_dualsense4unix.core.events import EventTopic

    return str(EventTopic.MIC_DA_MESA)


_TOPICO_DA_BORDA = _topico_da_borda()


def mesa_de_agora(daemon: Any) -> list[str] | None:
    """Reexporta a ÚNICA leitura pública de *"tem card na tela"*.

    Não é uma régua nova: é a de `recado_do_microfone`, importada tarde para
    não criar ciclo. Escrever a quarta régua sobre o mesmo estado é o defeito
    que esta casa já pagou onze vezes.
    """
    from hefesto_dualsense4unix.daemon.subsystems.recado_do_microfone import (
        mesa_de_agora as _mesa,
    )

    return _mesa(daemon)


__all__ = [
    "ACESA",
    "APAGADA",
    "ESPERA_DO_REPORT_S",
    "INTERVALO_DE_QUEM_OUVE_S",
    "INTERVALO_S",
    "LIMIAR_DE_BATERIA_PCT",
    "MODULO_DE_QUEM_OUVE",
    "MODULO_DO_NIVEL",
    "NOME_DE_QUEM_OUVE",
    "NOME_DO_MEDIDOR",
    "PISCANDO",
    "PISCANDO_LENTO",
    "SEM_RESPOSTA_ATE_SOLTAR_S",
    "decidir",
    "luz_do_mic_loop",
    "start_luz_do_mic",
]
