"""A luz do botão de microfone diz QUEM TE ESCUTA — o laço que decide e escreve.

LUZ-DO-MIC-01, PEÇA C (03/09/2026). Este módulo é o único que ESCREVE no
`common[8]` por decisão de estado; as peças A e B só respondem perguntas.

**O CONTRATO, e ele é decisão dela** (a sprint `LUZ-DO-MIC-01`, §1)::

    apagado (0)      = MUDO. É a ÚNICA coisa que apaga esta luz.
    aceso fixo (1)   = o microfone está LIGADO — haja ou não app ouvindo
    piscando (2)     = algum app de fora tem o microfone aberto E entra som AGORA
    pisca lento (3)  = idem, E a bateria deste controle < 30%

A precedência está em `decidir`, e ela é a §1.1 escrita em código.

**O `0` DEIXOU DE SER DUAS COISAS — 19/09/2026, decisão dela**
(a sprint `A-LUZ-DO-MIC-ESPELHA-O-BOTAO-01`). O
contrato de 02/09 dizia *"apagado = MUDO, ou ninguém ouvindo — OS DOIS SÃO A
MESMA LUZ"*, e foi isso que custou a noite dela: com o microfone LIGADO e
ninguém gravando, a luz apagada lhe disse *"desligado"*, ela apertou o botão
para ligar e **desligou** — o vigia mediu `mudo=False canal_ativo=True` antes
do primeiro clique.

Perguntada com quatro opções, ela escolheu *«Espelhar o botão E consertar a
tela»*: a luz passa a responder ao BOTÃO, na hora, sem depender de app nenhum
estar aberto, e o *"alguém te ouve"* não some — vira o PISCANDO, e ganha texto
na aba Controle (`interface/pacotes/a02_controles.py`, campo `mic-ressalva`).

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
* **não abre o hidraw** — escrever cru é a armadilha do instrumento que briga
  com o produto (`docs/method/COMO-OLHAR-A-TELA.md`): o daemon reafirma o
  report de saída e a escrita crua morre em milissegundos. Tudo passa pelo backend;
* **não rouba o botão físico dela** — o gesto continua sendo do
  `hid-playstation` (que alterna `ds->mic_muted`) e do `mic_da_mesa`/`hotkey`
  (que elege). Este laço só LÊ o mudo e pinta;
* **não reafirma o mesmo valor** — escreve só na MUDANÇA. Reafirmar a cada
  tique por cima do kernel é literalmente o defeito do commit `3d9bb7e` no
  byte vizinho, e é o requisito que o teste do tempo morde.

**POR QUE `set_microphone_led` E NÃO `set_mic_led`, e isto não é preferência.**
Medido nesta árvore em 03/09/2026: `set_mic_led` coage a `bool` DUAS VEZES em
série (`core/backend_pydualsense.py:3952`, `flag = bool(aceso)`, e `:480`,
`tomar(bool(aceso))`), então `2` e `3` viram `1` sem erro e sem log — luz acesa
fixa onde devia piscar, que se lê como *"a PEÇA B não está detectando som"*. O
único caminho de produção que carrega o nível é
`PyDualSenseController.set_microphone_led(aceso, *, uniq=)`
(`core/backend_pydualsense.py:4300`), medido: `0->0, 1->1, 2->2, 3->3`.

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
A sem B                      0 / 1 completos — acende com o microfone
                             ligado, sem distinguir o `2`
A e B                        os quatro estados
===========================  ===========================================

**AUSÊNCIA NÃO É NEGAÇÃO.** `audio_status_for` devolve `None` para o controle
que ainda não reportou, e `None` **não** é `False`: tratá-lo como *"não está
muda"* acenderia a luz de um controle que acabou de chegar e ainda não disse
nada — é o mesmo `bool(None)` que esta casa já publicou como ATIVO sobre um
controle que tinha acabado de cair. Por isso `decidir` devolve `None` (*"não
sei, não escreva"*), que é um valor de primeira classe aqui.

**A BORDA É SEGURADA, e isso existe porque há DOIS escritores.** A eleição
(`hotkey._eleger_ou_devolver`) também escreve neste byte, por
`set_mic_led(aceso, uniq=)`, na borda do botão. O laço assina
`EventTopic.MIC_DA_MESA` — a mesma borda que a eleição consome, já com sossego
e carência aplicados pelo `mic_da_mesa` — e, naquele `uniq`, NÃO escreve até o
ato tomar a posse do mudo (`microphone_mute_for` deixa de ser `None`) ou até
`SEGURA_A_BORDA_S`. Depois reescreve o que decidiu, uma vez, porque a eleição
pode ter pintado por cima.

Até 29/09/2026 o laço ESQUECIA o que escreveu e relia o bit de mudo no tique
seguinte — e esse bit ainda era o de antes do aperto: a volta do handle lia UM
report de uma fila de 63, e na bancada de 29/09 a luz repintou o estado velho
por cima da eleição por ~2,3 s, com os quatro no rádio
(O-BOTAO-DO-MIC-CHEGA-NA-HORA-01). A leitura fresca não basta sozinha: o
`mudo` da borda não é o que o ato faz (`hotkey._o_que_a_borda_pede` troca o
calar por LIGAR no primeiro aperto depois de conectar), então a luz espera o
ato e decide pelo que ele deixou (ver `_mudo`). No caso de sempre, os dois
escritores escrevem o mesmo valor na mesma borda. **A briga quando a eleição
RECUSA** (ela apaga, e o firmware livre acende) segue aberta, para quem
coordena.
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

APAGADA: int = 0
ACESA: int = 1
PISCANDO: int = 2
PISCANDO_LENTO: int = 3

_DECIDIDO: dict[str, int] = {}


def estado_da_luz_do_mic(uniq: str) -> int | None:
    """O estado decidido para este controle — `None` = ninguém decidiu ainda.

    Leitura barata (um `dict`), pensada para o `state_full`: quem chama é o
    laço do IPC, a cada tique.
    """
    return _DECIDIDO.get(str(uniq or ""))


def _lembrar_o_estado(uniq: str, alvo: int | None) -> None:
    """Guarda (ou esquece) o que foi decidido para este controle."""
    chave = str(uniq or "")
    if not chave:
        return
    if alvo is None:
        _DECIDIDO.pop(chave, None)
    else:
        _DECIDIDO[chave] = int(alvo)


_OUVINTES: dict[str, list[str]] = {}


def quem_ouve_este_mic(uniq: str) -> list[str] | None:
    """Os apps de FORA que têm o microfone deste controle aberto.

    `None` = ninguém perguntou ainda (ou a PEÇA A não respondeu); `[]` =
    perguntamos e não há ninguém. A distinção é a mesma de `decidir`, e ela é
    o que separa *"ninguém está te ouvindo"* de *"não sei dizer"* na tela.

    **APPS DE FORA, e o "de fora" é o contrato.** A lista é a que
    `quem_ouve_agora` devolve, já sem os gravadores do próprio Hefesto
    (`e_stream_do_hefesto`, regra 3): o medidor de nível da aba Controle grava
    o mesmo canal o tempo todo, e contá-lo faria a tela dizer que alguém a
    ouve porque ela está aberta.

    Leitura barata (um `dict`), pensada para o `state_full`.
    """
    return _OUVINTES.get(str(uniq or ""))


def _lembrar_quem_ouve(uniq: str, ouvintes: list[str] | None) -> None:
    """Guarda (ou esquece) quem ouve este controle."""
    chave = str(uniq or "")
    if not chave:
        return
    if ouvintes is None:
        _OUVINTES.pop(chave, None)
    else:
        _OUVINTES[chave] = [str(x) for x in ouvintes]

INTERVALO_S: float = 0.25

#: guardada entre uma pergunta e outra, então a decisão continua a 4 Hz.
INTERVALO_DE_QUEM_OUVE_S: float = 1.0

_O_QUE_A_LUZ_LE: tuple[str, ...] = ("source-outputs", "sources")

SEGURA_A_BORDA_S: float = 1.0

LIMIAR_DE_BATERIA_PCT: int = 30

ESPERA_DO_REPORT_S: float = 0.15

SEM_RESPOSTA_ATE_SOLTAR_S: float = 3.0

MODULO_DE_QUEM_OUVE: str = "hefesto_dualsense4unix.integrations.quem_ouve_o_microfone"
NOME_DE_QUEM_OUVE: str = "quem_ouve_agora"

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
        ninguém ouvindo, e o microfone ligado    -> 1
        resto                                    -> 1

    **A LINHA DE BAIXO MUDOU EM 19/09/2026, E É DECISÃO DELA.** Ela era
    `não ouvintes -> 0`, e a sprint
    `2026-09-19-A-LUZ-DO-MIC-ESPELHA-O-BOTAO-01` mediu o preço: com o
    microfone LIGADO e nenhum app gravando — o arranjo exato da mesa dela
    naquela noite —, o journal só tinha `luz_do_mic_escrita estado=0`, a luz
    apagada lhe disse *"desligado"*, e o primeiro clique dela **desligou** o
    microfone que já estava no ar.

    Hoje **quem apaga é só o `mudo is True`**. A luz espelha o BOTÃO: o *"tem
    alguém te ouvindo"* não se perdeu, ele é o `2` (e a aba Controle passou a
    dizer QUEM, por escrito, no campo `mic-ressalva`).

    **E O FILTRO ANTI-AUTO-REFERÊNCIA CONTINUA CERTO.** A regra 3 de
    `e_stream_do_hefesto` exclui de `ouvintes` todo gravador cujo
    `application.name` contenha `hefesto` — e é por isso que a lista vem vazia
    na mesa dela: o único gravador do canal é o `hefesto-canal-do-microfone`,
    o medidor de nível da própria aba Controle. Contá-lo faria a luz **acender
    sozinha porque a tela está aberta**, e o `2` passaria a dizer *"a aba está
    medindo"* em vez de *"alguém te ouve"*. A causa do defeito não era o
    filtro: era o `0` querer dizer duas coisas.

    **O `None` é um valor de primeira classe, e não um buraco.** Ele sai em
    duas situações, e as duas são honestas:

    * `mudo is None` — o controle ainda não reportou o byte de estado de áudio.
      Chutar `False` acenderia a luz de quem acabou de chegar; chutar `True`
      apagaria a de quem está falando. A resposta certa é não escrever;
    * `ouvintes is None` — a PEÇA A não existe, não achou o `pactl`, ou não
      conseguiu ler o grafo. *"Não perguntei a ninguém"* não é *"ninguém
      ouve"*: a lista VAZIA (`[]`) é que significa ninguém, e ela acende o
      `1` com todas as letras. **Os dois continuam separados**, e a mudança de
      19/09 não os junta: o que mudou foi o VALOR da lista vazia, de `0` para
      `1`; `None` continua sendo *"não escreva"*.

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
        return ACESA
    if captando is True:
        if bateria_pct is not None and bateria_pct < LIMIAR_DE_BATERIA_PCT:
            return PISCANDO_LENTO
        return PISCANDO
    return ACESA


def _posse_do_mudo(backend: Any, uniq: str) -> bool | None:
    """O mudo que o HEFESTO afirma no firmware, ou `None` quando o dono é o kernel."""
    ler = getattr(backend, "microphone_mute_for", None)
    if not callable(ler):
        return None
    try:
        valor = ler(uniq)
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("luz_do_mic_posse_falhou", uniq=uniq, err=str(exc))
        return None
    return valor if isinstance(valor, bool) else None


def _segura_a_borda(
    backend: Any, uniq: str, segura_desde: dict[str, float], agora: float
) -> bool:
    """A borda deste controle ainda é da ELEIÇÃO? `True` = não decida nem escreva."""
    desde = segura_desde.get(uniq)
    if desde is None:
        return False
    if _posse_do_mudo(backend, uniq) is None and (agora - desde) < SEGURA_A_BORDA_S:
        return True
    segura_desde.pop(uniq, None)
    return False


def _mudo(backend: Any, uniq: str) -> bool | None:
    """O mudo que vale naquele controle, ou `None` quando ninguém disse."""
    posse = _posse_do_mudo(backend, uniq)
    if posse is not None:
        return posse
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
    (`core/backend_pydualsense.py:5347`) e a leitura é `getattr` no objeto que
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
    """Resolve UM nome num módulo irmão, uma vez só, tolerando a ausência."""
    chave = f"{caminho}:{nome}"
    if chave in cache:
        return cache[chave]
    achado = None
    try:
        modulo = importlib.import_module(caminho)
    except Exception as exc:
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
    """Roda `fn` fora do event loop, caindo para a chamada direta se não der."""
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
    """A PEÇA A: `{uniq: [clientes]}`, ou `None` para *"não sei"*."""
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
    """Os `uniq` que a PEÇA A disse ter ouvinte — e só eles vão para o medidor."""
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
    """A PEÇA B, construída na PRIMEIRA vez que alguém ouve — e não antes."""
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
    """Mata os `parec` e a thread do medidor. **Não é opcional.**"""
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
    `core/backend_pydualsense.py:3952` e `:480`).

    `valor is None` é a DEVOLUÇÃO DA POSSE (o bit `0x01` do flag1 cai e o
    kernel volta a escrever a luz na borda do botão); `0` é uma ORDEM
    ("apaga"), com a posse mantida. Confundir os dois é o defeito do commit
    `3d9bb7e` no byte vizinho.

    A escrita **não é HID I/O**: `_PinnedPyDualSense.set_microphone_led` só
    guarda `_mic_led_desejado` (`core/backend_pydualsense.py:1316`), e quem
    manda o report é a thread do handle. É por isso que ela pode ser chamada
    direto no `finally` do desligamento, quando não há executor garantido.
    """
    escrever = getattr(backend, "set_microphone_led", None)
    if not callable(escrever):
        # `PyDualSenseController`. Sair calado daqui seria o log dizendo que a
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
    """REPINTA na língua do kernel, espera o report sair, e SOLTA a posse."""
    alvos = [uniq for uniq in uniqs if uniq in posse]
    if backend is None or not alvos:
        return 0
    for uniq in alvos:
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
    """Decide o estado de cada controle da mesa e escreve — só na MUDANÇA."""
    from hefesto_dualsense4unix.integrations.retrato_do_som import RETRATO

    relogio = asyncio.get_running_loop().time
    marca_vista: int | None = None
    escrito: dict[str, int] = {}
    posse: set[str] = set()
    segura_desde: dict[str, float] = {}
    sem_resposta_desde: dict[str, float] = {}
    cache_das_pecas: dict[str, Any] = {}
    ouvintes_por_uniq: dict[str, Any] | None = None
    perguntei_em = float("-inf")
    medidor: Any = None

    fila: Any = None
    fila_do_jogo: Any = None
    inscrever = getattr(getattr(daemon, "bus", None), "subscribe", None)
    if callable(inscrever):
        with contextlib.suppress(Exception):
            fila = inscrever(_TOPICO_DA_BORDA)
        with contextlib.suppress(Exception):
            fila_do_jogo = inscrever(_TOPICO_DO_JOGO)

    try:
        while not daemon._is_stopping():
            await asyncio.sleep(INTERVALO_S)
            backend = getattr(daemon, "controller", None)
            if backend is None:
                continue
            agora = relogio()

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
                        segura_desde[alvo] = agora
                        a_pessoa_mandou(alvo, evento.get("em"))
            for chave in _drenar_o_jogo(fila_do_jogo):
                for uniq in [u for u in escrito if chave_do_mic(u) == chave]:
                    escrito.pop(uniq, None)

            mesa = mesa_de_agora(daemon)
            if mesa is None:
                continue
            for uniq in [u for u in escrito if u not in mesa] + [
                u for u in posse if u not in mesa
            ]:
                escrito.pop(uniq, None)
                _lembrar_o_estado(uniq, None)
                _lembrar_quem_ouve(uniq, None)
                posse.discard(uniq)
                segura_desde.pop(uniq, None)
                sem_resposta_desde.pop(uniq, None)

            marca = RETRATO.marca(_O_QUE_A_LUZ_LE)
            if marca != marca_vista or (agora - perguntei_em) >= INTERVALO_DE_QUEM_OUVE_S:
                ouvintes_por_uniq = await _fora_do_laco(
                    daemon, _quem_ouve, mesa, cache_das_pecas
                )
                perguntei_em = agora
                marca_vista = marca
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
                _lembrar_quem_ouve(uniq, ouvintes)
                if _segura_a_borda(backend, uniq, segura_desde, agora):
                    continue
                captando = None
                if captando_por_uniq is not None:
                    bruto_b = captando_por_uniq.get(uniq)
                    captando = bruto_b if isinstance(bruto_b, bool) else None
                decidido = decidir(
                    mudo=_mudo(backend, uniq),
                    ouvintes=ouvintes,
                    captando=captando,
                    bateria_pct=baterias.get(uniq),
                )

                _lembrar_o_estado(uniq, decidido)
                do_jogo = luz_do_mic_do_jogo(uniq)
                alvo = do_jogo if do_jogo is not None else decidido
                if alvo is None:
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
                    continue
                if await _fora_do_laco(daemon, _escrever, backend, uniq, alvo):
                    escrito[uniq] = alvo
                    posse.add(uniq)
                    logger.info("luz_do_mic_escrita", uniq=uniq, estado=alvo)
    finally:
        try:
            desinscrever = getattr(getattr(daemon, "bus", None), "unsubscribe", None)
            if callable(desinscrever):
                for topico, aberta in ((_TOPICO_DA_BORDA, fila), (_TOPICO_DO_JOGO, fila_do_jogo)):
                    if aberta is not None:
                        with contextlib.suppress(Exception):
                            desinscrever(topico, aberta)
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


def _topico_do_jogo() -> str:
    from hefesto_dualsense4unix.core.events import EventTopic

    return str(EventTopic.MIC_DO_JOGO)


_TOPICO_DO_JOGO = _topico_do_jogo()


def mesa_de_agora(daemon: Any) -> list[str] | None:
    """Reexporta a ÚNICA leitura pública de *"tem card na tela"*."""
    from hefesto_dualsense4unix.daemon.subsystems.recado_do_microfone import (
        mesa_de_agora as _mesa,
    )

    return _mesa(daemon)


# Com pad virtual DualSense, o `common[8]` que o jogo pede vai ao plástico do

_LUZ_DO_JOGO: dict[str, tuple[int, float]] = {}

_A_PESSOA_MANDOU_EM: dict[str, float] = {}


def chave_do_mic(uniq: str | None) -> str | None:
    """O `uniq` na forma da mesa (`norm_mac`, doze hex), ou `None` se não é MAC."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    chave = norm_mac(uniq)
    if chave is None or len(chave) != 12:
        return None
    return chave


def luz_do_mic_do_jogo(uniq: str | None) -> int | None:
    """A luz que o jogo pediu e está de pé neste controle; `None` = nenhuma.

    Leitura barata (um `dict`), pensada para o `state_full`.
    """
    chave = chave_do_mic(uniq)
    pedido = _LUZ_DO_JOGO.get(chave) if chave else None
    return None if pedido is None else pedido[0]


def a_pessoa_mandou(uniq: str | None, em: float | None = None) -> None:
    """Ela mandou no microfone deste controle (o aperto, o 🎙). `None` = agora."""
    chave = chave_do_mic(uniq)
    if chave is None:
        return
    quando = _instante(em)
    if quando > _A_PESSOA_MANDOU_EM.get(chave, float("-inf")):
        _A_PESSOA_MANDOU_EM[chave] = quando
    pedido = _LUZ_DO_JOGO.get(chave)
    if pedido is not None and pedido[1] <= _A_PESSOA_MANDOU_EM[chave]:
        _LUZ_DO_JOGO.pop(chave, None)
        logger.info("luz_do_mic_volta_a_ela", uniq=chave)


def quando_a_pessoa_mandou(uniq: str | None) -> float | None:
    """O instante da última ordem dela neste controle; `None` = nenhuma."""
    chave = chave_do_mic(uniq)
    return _A_PESSOA_MANDOU_EM.get(chave) if chave else None


def _instante(em: Any) -> float:
    """O `em` de um evento, ou agora (`time.monotonic`, o relógio da borda)."""
    import time

    if isinstance(em, (int, float)) and not isinstance(em, bool):
        return float(em)
    return time.monotonic()


def _o_jogo_pede_a_luz(chave: str, valor: int, em: float) -> bool:
    """Guarda o pedido de luz do jogo se ele é mais novo que a ordem dela."""
    if em <= _A_PESSOA_MANDOU_EM.get(chave, float("-inf")):
        logger.info("luz_do_mic_pedido_velho_do_jogo", uniq=chave, luz=valor)
        return False
    _LUZ_DO_JOGO[chave] = (int(valor), em)
    return True


def _drenar_o_jogo(fila: Any) -> list[str]:
    """Aplica os eventos `MIC_DO_JOGO` da fila; devolve as chaves que mudaram."""
    mudaram: list[str] = []
    if fila is None:
        return mudaram
    while True:
        try:
            evento = fila.get_nowait()
        except asyncio.QueueEmpty:
            break
        except Exception:  # pragma: no cover - defensivo
            break
        if not isinstance(evento, dict):
            continue
        chave = chave_do_mic(evento.get("uniq"))
        if chave is None:
            continue
        if evento.get("solta"):
            if _LUZ_DO_JOGO.pop(chave, None) is not None:
                logger.info("luz_do_mic_o_jogo_soltou", uniq=chave)
                mudaram.append(chave)
            continue
        luz = evento.get("luz")
        if isinstance(luz, bool) or not isinstance(luz, int):
            continue
        if _o_jogo_pede_a_luz(chave, luz, _instante(evento.get("em"))):
            logger.info("luz_do_mic_do_jogo", uniq=chave, luz=luz)
            mudaram.append(chave)
    return mudaram


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
    "SEGURA_A_BORDA_S",
    "SEM_RESPOSTA_ATE_SOLTAR_S",
    "a_pessoa_mandou",
    "chave_do_mic",
    "decidir",
    "luz_do_mic_do_jogo",
    "luz_do_mic_loop",
    "quando_a_pessoa_mandou",
    "start_luz_do_mic",
]
