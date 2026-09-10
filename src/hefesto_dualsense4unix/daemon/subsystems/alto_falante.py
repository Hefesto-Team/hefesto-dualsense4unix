"""Subsystem: o nó de som de CADA DualSense — e ele não sabe o que é transporte.

SOM-QUE-SAI-01. Embrulha :mod:`integrations.alto_falante_bt` no contrato
``Subsystem`` do daemon (``start``/``stop``/``is_enabled``). É fino de
propósito: toda a lógica de PipeWire, Opus e protocolo mora no módulo de
integração, que roda igual pelo CLI, pela interface ou por aqui. Espelho de
``daemon/subsystems/bt_mic.py``, a metade de ENTRADA, que **não é tocada**.

O DEFEITO QUE ELE EXISTE PARA MATAR
------------------------------------
A placa ALSA do DualSense é do **TRANSPORTE**, não da unidade — medido por
INVERSÃO em 15/08/2026, com os quatro aparelhos trocados de braço: quem foi
para o fio ganhou placa, quem foi para o ar perdeu. A consequência para quem
joga é a que esta sprint ataca: **ela tira o cabo no meio da partida e o
dispositivo de saída que o jogo escolheu desaparece do sistema.** Não é o som
que fica ruim — é a rota que some debaixo do jogo.

Depois deste subsystem, o jogo aponta para **um nó que não sai do lugar**: o
nome vem do ``uniq`` do controle (``hefesto_som_<hex6>``), e o cabo, o rádio e
o "não tem para onde ir" acontecem por baixo dele. É o mesmo contrato do
gamepad virtual, que é o precedente que ela citou: *o jogo escolhe um
dispositivo, não um transporte* (``integrations/virtual_pad.py``).

AS TRÊS DECISÕES DELA, E ELAS SÃO CURTAS
-----------------------------------------
``D-0609-O-NO-DE-SOM-VIVE-COM-O-CONTROLE`` (06/09/2026, por delegação,
reversível numa frase — ``docs/data/decisoes-dela.csv:213``):

1. **REVERTIDA POR ELA EM 08/09/2026.** Dizia *"o nó vive só enquanto há
   controle"* — decisão por DELEGAÇÃO, e declarada reversível numa frase. Ela
   reverteu com todas as letras em `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-
   SEMPRE` (*"concordo com as 5"*): **nó que some quebra o jogo que o
   escolheu.** O que vai e volta é a ROTA, e o nó fica;
2. **no cabo ele não vira saída padrão.** ``priority.session`` baixa
   (``integrations.alto_falante_bt.PRIORIDADE_SESSAO_DO_SOM``). Publicar o nó
   é uma coisa; mandar o som do sistema para ele é outra, e a segunda é dela;
3. **a escolha entre ``0x32`` e ``0x39`` só depois do D5**, com o número de
   banda na mesa. Este subsystem **não escreve no rádio** e por isso não
   escolhe degrau nenhum.

O QUE ELE NÃO FAZ, E É METADE DO VALOR DE LER ISTO
---------------------------------------------------
* **não escreve um byte no aparelho.** Ele publica e derruba nós do PipeWire,
  e mais nada. Quem escreve no rádio é o ensaio de bancada
  (``scripts/ensaios/o_som_que_sai.py``), com a orelha dela do outro lado —
  e o mapa proíbe, com todas as letras, concluir daí que a ponte funciona —
  a forma de erro tem nome e é a **FALÁCIA DO CANAL QUE RESPONDE**: concluir
  que, porque um canal responde, ele FAZ o que a gente esperava dele. O
  honesto é o par: *o canal responde, e o conteúdo vai pelos dois arranjos
  candidatos*;
* **PASSOU A LIGAR — 09/09/2026, SOM-POR-CONTROLE-01.** Esta linha dizia *"não
  liga o monitor ao sink USB do controle no cabo"*, e era verdade: o
  ``module-loopback`` e o casamento por dispositivo USB estavam fora da posse
  daquela sprint. Estão dentro desta. Quem resolve a rota é
  ``integrations.alto_falante_bt.rota_do_no``, e ele é o MESMO que a janela
  chama por ``app/audio_saida`` — uma pergunta, um dono;
* **não é registrado no daemon.** ``daemon/subsystems/__init__.py``,
  ``daemon/lifecycle.py`` e ``daemon/connection.py`` — os TRÊS lugares que
  ligam um subsystem, e os três fora da posse. **Este subsystem nasce órfão de
  propósito e declarado**, que é o oposto do defeito que o ``__init__.py`` do
  registry nomeia (o ``BtMicSubsystem`` nasceu órfão em 25/07 sem ninguém
  saber).

O ÓRFÃO GANHOU A ROTA — E CONTINUA ÓRFÃO POR TRÊS LINHAS QUE NÃO SÃO DAQUI
----------------------------------------------------------------------------
**As duas razões de 07/09 para não o ligar caíram em 09/09**, e as duas eram
razões de verdade:

* *"sem o ``module-loopback``, o nó publicado é um sumidouro"* — agora
  :class:`~integrations.alto_falante_bt.SinkVirtualPipeWire` sobe o loopback
  junto, e a pergunta *"onde este nó entrega?"* passou a ter **um** dono
  (``integrations.alto_falante_bt.rota_do_no``), que é o mesmo que a janela
  chama por ``app/audio_saida``. Eram duas respostas escritas; ficou uma;
* *"os quatro nascem com o MESMO rótulo"* — agora cada um nasce «Alto-falante
  do Controle N», com o número do ASSENTO, pelo mesmo gancho do «Microfone do
  Controle N» (decisão dela de 09/09, *"4a"*).

**O QUE FALTA PARA ELE VIVER NA MESA DELA, e não está nesta árvore:** as três
linhas do registro — ``daemon/subsystems/__init__.py`` (a lista),
``daemon/lifecycle.py`` (o ``_safe_start`` no ``run()``) e
``daemon/connection.py`` (o ``_stop_*`` no ``shutdown()``). Os TRÊS estão fora
da posse da SOM-POR-CONTROLE-01, e a receita de duas metades é a armadilha que
o ``subsystems/__init__.py`` já nomeia: quem faz duas sobe o subsystem e nunca
o para, e o nó fica na lista de saída dela **depois de o daemon morrer**.

A régua que trava o par continua sendo
``tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py`` — e ela sempre permitiu
esta cura: *"ela NÃO proíbe ligar o subsystem; ela trava o PAR — se ele subir,
o nó tem de ter rota"*.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

logger = get_logger(__name__)

#: Cadência da varredura de hotplug (sysfs). Não é polling de áudio: é só
#: *"apareceu/sumiu controle?"*. O mesmo número da metade de entrada.
RECONCILIA_S = 5.0

#: Os doze dígitos hex de um MAC. Um ``uniq`` que não os tenha não é endereço,
#: e `norm_mac` só FILTRA hex — sem esta trava, `"a"` viraria uma chave válida
#: e casaria com qualquer coisa. Mesma régua da metade de entrada.
_UNIQ_HEX = 12

#: O transporte suposto quando quem chamou não disse qual é. É o CABO porque é
#: o único onde há rota hoje, e supor rádio faria o nó recusar antes de tentar.
TRANSPORTE_CABO = "usb"


@dataclass(frozen=True)
class ControleNaLista:
    """Um DualSense visto pelo sysfs, com o transporte AO LADO e nunca DENTRO.

    O ``transporte`` existe para o diagnóstico e para o relatório — **nunca
    para o nome do nó**. Se algum dia ele entrar na identidade, o defeito que
    este subsystem existe para matar volta com outra roupa.
    """

    uniq: str
    caminho: str
    transporte: str


class GerenciadorDeNosDeSom:
    """Sobe/derruba um :class:`SinkVirtualPipeWire` por controle na lista.

    ``reconciliar()`` é idempotente e barato: um controle que sai da lista tem
    o nó derrubado, e os outros ficam de pé.

    **O CICLO DE VIDA É O DE 08/09/2026, e é dela.** Este texto dizia *"é ele
    que faz o «vive só enquanto há controle»"* — a decisão de 06/09, por
    delegação. Ela a reverteu (`D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`):
    o nó que ela quer é FIXO, e é a ROTA que vai e volta. Enquanto o subsystem
    não estiver registrado, quem publica os quatro nós fixos não existe — este
    gerenciador segue a lista viva, e o que a decisão dela cobra dele é
    **não derrubar o que não saiu**, que é o que ele já faz.
    """

    def __init__(
        self,
        *,
        fabrica: Any = None,
        fonte_por_controle: Any = None,
        ponte_do_radio_por_controle: Any = None,
    ) -> None:
        self._fabrica = fabrica
        self._fonte_por_controle = fonte_por_controle
        #: UMA PONTE POR CONTROLE NO RÁDIO — 10/09/2026. Recebe o ``uniq`` e
        #: devolve um callable que responde *"a ponte deste controle está no
        #: ar?"*. `None` = ninguém injetou ponte, e :func:`rota_do_no` recusa o
        #: rádio com a frase honesta, que é o comportamento de sempre.
        #:
        #: **A INJEÇÃO É O PONTO.** Este gerenciador não abre hidraw nem sobe
        #: thread: ele sabe QUAIS controles existem e qual é a mesa, e nada
        #: mais. Quem constrói a ponte é quem tem o broker na mão.
        self._ponte_do_radio_por_controle = ponte_do_radio_por_controle
        self._nos: dict[str, Any] = {}
        self._acordar = threading.Event()

    @property
    def nos(self) -> dict[str, Any]:
        return dict(self._nos)

    def _construir(self, uniq: str, transporte: str, mesa: tuple[str, ...]) -> Any:
        """O nó daquele controle, JÁ com rótulo próprio e rota resolvida.

        O rótulo e a rota nascem aqui e não dentro do nó porque quem sabe a
        MESA é este gerenciador: ``sink_do_controle`` precisa da lista inteira
        de ``uniq`` para casar a placa USB certa. Com um só, dois DualSense no
        cabo entregam o som do P2 no alto-falante do P1.
        """
        if self._fabrica is not None:
            return self._fabrica(uniq)
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            SinkVirtualPipeWire,
            descricao_do_alto_falante,
            rota_do_no,
        )

        return SinkVirtualPipeWire(
            uniq=uniq,
            descricao=descricao_do_alto_falante(uniq),
            rota=rota_do_no(
                uniq,
                transporte,
                mesa,
                fonte=self._fonte_do_no(uniq),
                ponte_do_radio=self._ponte_do_radio(uniq),
            ),
        )

    def _ponte_do_radio(self, uniq: str) -> Any:
        """O callable que diz se a ponte DESTE controle está no ar — ou `None`.

        `None` não é falha: é *"ninguém me deu ponte"*, e :func:`rota_do_no`
        responde com a frase honesta. O que ele NÃO pode virar é um `lambda:
        True` otimista — isso publicaria a rota sobre uma ponte que não existe,
        e o nó voltaria a ser o sumidouro que
        `tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py` trava.
        """
        if self._ponte_do_radio_por_controle is None:
            return None
        try:
            return self._ponte_do_radio_por_controle(uniq)
        except Exception:  # pragma: no cover - defensivo
            logger.debug("som_ponte_do_radio_ilegivel", uniq=uniq, exc_info=True)
            return None

    def _fonte_do_no(self, uniq: str) -> str:
        """``mix`` ou ``sfx`` para este controle — o padrão dela quando ninguém disse.

        A escolha mora no PERFIL (``ControllerOverrides.speaker.fonte``) e
        chega aqui por injeção, nunca por leitura de disco no laço: ler o
        perfil a cada varredura é a tempestade de syscalls que o mapa de
        motores do ``gamepad.py`` já pagou uma vez.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import FONTE_PADRAO

        if self._fonte_por_controle is None:
            return FONTE_PADRAO
        try:
            return self._fonte_por_controle(uniq) or FONTE_PADRAO
        except Exception:  # pragma: no cover - defensivo
            logger.debug("som_fonte_ilegivel", uniq=uniq, exc_info=True)
            return FONTE_PADRAO

    def reconciliar(self, controles: list[Any] | None = None) -> None:
        """Casa os nós vivos com a lista de controles recebida.

        **Tirar um controle da lista DERRUBA o nó dele e deixa os outros de
        pé.** Sem isso, um controle sumir derrubaria o som dos quatro — que é
        exatamente o defeito de "a rota some debaixo do jogo", só que causado
        por nós.

        Aceita ``str`` (só o ``uniq``) e :class:`ControleNaLista` (o ``uniq``
        **e** o transporte). A segunda forma é a que resolve rota; a primeira
        sobrevive porque as réguas de ciclo de vida a usam, e trocá-las por
        objeto não mediria nada de novo.
        """
        vistos: dict[str, str] = {}
        for item in controles or []:
            uniq = item if isinstance(item, str) else str(getattr(item, "uniq", ""))
            if not uniq or uniq in vistos:
                continue
            transporte = (
                "" if isinstance(item, str) else str(getattr(item, "transporte", ""))
            )
            vistos[uniq] = transporte
        alvos = list(vistos)
        mesa = tuple(alvos)
        for uniq in list(self._nos):
            if uniq not in alvos:
                self._derrubar(uniq)
        for uniq in alvos:
            if uniq in self._nos:
                continue
            no = self._construir(uniq, vistos[uniq] or TRANSPORTE_CABO, mesa)
            # SEM ROTA, SEM NÓ — e a razão está na invariante 4 de
            # `app/audio_saida.py`: *"um `module-null-sink` sozinho seria
            # exatamente o sink que aceita o áudio e o joga fora"*. Publicar
            # aqui poria uma entrada MUDA por DualSense na lista de som dela;
            # ela escolhe uma das quatro e o som some.
            #
            # Isto NÃO contradiz `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`.
            # A decisão dela é sobre o nó não sumir debaixo do jogo quando o
            # controle troca de transporte ou pisca; esta guarda é sobre nunca
            # PUBLICAR um nó que não entrega em lugar nenhum. `rota.motivo`
            # carrega a frase honesta, e é ela que a tela mostra.
            rota = getattr(no, "rota", None)
            if rota is not None and not getattr(rota, "tem_rota", True):
                logger.info(
                    "som_no_sem_rota",
                    uniq=uniq,
                    motivo=str(getattr(rota, "motivo", "")),
                )
                continue
            try:
                subiu = bool(no.iniciar())
            except Exception as exc:  # nunca derruba a varredura
                logger.debug("som_no_falhou", uniq=uniq, err=str(exc))
                continue
            if subiu:
                self._nos[uniq] = no
            else:
                logger.info("som_no_nao_subiu", uniq=uniq)

    def _derrubar(self, uniq: str) -> None:
        no = self._nos.pop(uniq, None)
        if no is None:
            return
        with contextlib.suppress(Exception):
            no.parar()
        logger.info("som_no_derrubado", uniq=uniq)

    def dormir(self, segundos: float) -> bool:
        """True quando é para parar. Bloqueia num Event, nunca num sleep."""
        return self._acordar.wait(segundos)

    def parar(self) -> None:
        """Derruba todos os nós. Idempotente."""
        for uniq in list(self._nos):
            self._derrubar(uniq)
        self._acordar.set()


def _uniq_de_perfil(uniq: str) -> str:
    """O `uniq` na grafia que o PERFIL usa: doze hex minúsculos, sem separador.

    O sysfs entrega `aa:bb:cc:dd:ee:ff` e o `Profile.controllers` é chaveado
    por `aabbccddeeff` — o schema recusa a outra forma. Casar as duas grafias
    à mão em cada chamador é como esta casa já perdeu uma escolha dela: a
    chave não bate, `get` devolve `None`, e ninguém vê erro nenhum.
    """
    return "".join(c for c in uniq.lower() if c in "0123456789abcdef")[:12]


def _carimbo_do_perfil(nome: str) -> Any:
    """`mtime_ns` do arquivo daquele perfil — `None` quando não dá para saber.

    É o que invalida o cache das fontes. `None` (arquivo não encontrado, erro
    de `stat`) força a releitura na varredura seguinte, que é o lado seguro:
    ler demais custa uma syscall, ler de menos entrega a escolha de ontem.
    """
    try:
        # `_profile_path` é privado do loader, e usá-lo é deliberado: a
        # alternativa seria redigitar aqui `profiles_dir() / f"{slug}.json"`,
        # e uma segunda regra de "onde mora o perfil" é como esta casa já
        # perdeu escrita dela — o `slugify` e a recusa de travessia moram lá.
        from hefesto_dualsense4unix.profiles.loader import _profile_path

        return Path(_profile_path(nome)).stat().st_mtime_ns
    except Exception:
        return None


def _fontes_por_controle(nome: str) -> dict[str, str]:
    """`{uniq: "mix"|"sfx"}` dos overrides daquele perfil. `{}` é honesto.

    Só entra quem DECLAROU: `speaker.fonte is None` significa *"sem opinião"*
    em todo o esquema de perfil, e transformá-lo em `sfx` aqui apagaria a
    diferença entre «ela escolheu efeitos» e «ela não escolheu nada» — que é
    a distinção que faz o padrão poder mudar um dia sem reescrever perfil.
    """
    try:
        from hefesto_dualsense4unix.profiles.loader import load_profile

        perfil = load_profile(nome)
    except Exception:
        logger.debug("som_perfil_ilegivel", perfil=nome, exc_info=True)
        return {}

    fontes: dict[str, str] = {}
    for chave, override in (getattr(perfil, "controllers", None) or {}).items():
        alto_falante = getattr(override, "speaker", None)
        fonte = getattr(alto_falante, "fonte", None)
        if fonte:
            fontes[_uniq_de_perfil(str(chave))] = str(fonte)
    return fontes


def controles_na_lista(raiz: str | None = None) -> list[ControleNaLista]:
    """Todo DualSense que o sysfs mostra, **nos dois transportes**.

    A metade de entrada só precisa dos de Bluetooth (o microfone no cabo já
    funciona sozinho); aqui a pergunta é outra e a resposta tem de ser dos
    dois lados, porque o nó existe justamente para não mudar quando o controle
    troca de braço.

    Reusa a leitura de ``uevent`` e as constantes de identidade da ENTRADA em
    vez de reimplementá-las — três instrumentos respondendo *"isto é um
    DualSense?"* de três jeitos é como esta casa já fabricou uma resposta
    errada, e o precedente tem nome (``identidade_do_vpad.py``). Os nomes com
    ``_`` são privados daquele módulo: a alternativa seria redigitar o vendor,
    os dois produtos e o parser aqui, que é a duplicação que a regra proíbe.
    Import tardio para que importar o subsystem não arraste a libopus nem o
    ``pactl`` — mesma razão do import tardio da metade de entrada.
    """
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as entrada

    achados: list[ControleNaLista] = []
    try:
        entradas = sorted(Path(raiz or entrada._SYSFS_HIDRAW).iterdir())
    except OSError:
        return achados
    for item in entradas:
        info = entrada._uevent(item)
        partes = info.get("HID_ID", "").split(":")
        if len(partes) != 3:
            continue
        try:
            bus, vendor, produto = (int(p, 16) for p in partes)
        except ValueError:
            continue
        if vendor != entrada._VENDOR_SONY or produto not in entrada._PRODUTOS_DUALSENSE:
            continue
        # O vpad do próprio hefesto se apresenta como 0x0DF2 em BUS_USB. Sem o
        # filtro de bus da entrada, o `HID_PHYS` é a ÚNICA rede que sobra — e
        # publicar um nó de som para o nosso próprio gamepad virtual seria o
        # produto conversando consigo mesmo.
        if info.get("HID_PHYS", "") == entrada._PHYS_VPAD:
            continue
        achados.append(
            ControleNaLista(
                uniq=info.get("HID_UNIQ", ""),
                caminho=f"/dev/{item.name}",
                transporte="rádio" if bus == entrada._BUS_BLUETOOTH else "cabo",
            )
        )
    return achados


class AltoFalanteSubsystem:
    """Mantém um nó de som por DualSense presente, em qualquer transporte."""

    name = "alto_falante"

    def __init__(
        self,
        *,
        gerenciador: Any = None,
        fonte_de_controles: Any = None,
    ) -> None:
        self._gerenciador_injetado = gerenciador
        self._gerenciador: Any = None
        #: UMA ponte por controle no rádio, pelo `uniq`.
        self._pontes: dict[str, Any] = {}
        #: `({uniq: fonte}, (nome do perfil, carimbo))` — SFX-POR-CONTROLE-01.
        self._fontes_em_cache: tuple[dict[str, str], Any] = ({}, None)
        #: O `StateStore` do daemon, que sabe o perfil ATIVO agora.
        self._store: Any = None
        self._fonte = fonte_de_controles or controles_na_lista
        self._thread: threading.Thread | None = None
        self._parar = threading.Event()
        self._backend: Any = None
        #: O numerador de assento que estava instalado quando este subsystem
        #: subiu. `Ellipsis` = ele não instalou nada (já havia dono) e não tem
        #: nada a devolver no `stop` — ver :meth:`start`.
        self._numerador_anterior: Any = Ellipsis

    # -- contrato Subsystem ----------------------------------------------

    def is_enabled(self, config: DaemonConfig) -> bool:
        """Sempre. O nó tem de estar no ar antes de o jogo escolher a saída.

        **Ligado não quer dizer tocando.** Sem controle na lista, ``alvos()``
        devolve ``[]``, nenhum módulo é carregado, nenhum byte de áudio passa
        por lugar nenhum e o custo em repouso é uma varredura de sysfs a cada
        :data:`RECONCILIA_S`. A privacidade não entra nesta conta como entra na
        do microfone: um alto-falante não escuta.

        ``config`` fica na assinatura porque o contrato ``Subsystem`` é esse.
        """
        del config
        return True

    def alvos(self, controles: list[Any]) -> list[Any]:
        """Os controles que ganham nó — os que têm identidade legível.

        Um controle sem ``HID_UNIQ`` NUNCA entra: sem endereço não há de quem
        seja o nó, e dois anônimos disputariam o mesmo nome. Ausência é
        resposta.

        **Devolve o CONTROLE e não o ``uniq``**, como o ``bt_mic.alvos`` já
        fazia: quem resolve a rota precisa do TRANSPORTE ao lado, e voltar a
        pedi-lo depois seria uma segunda varredura de sysfs com a chance de
        discordar da primeira.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

        vistos: list[Any] = []
        conhecidos: set[str] = set()
        for controle in controles:
            uniq = str(getattr(controle, "uniq", "") or "")
            if not nome_do_sink(uniq) or uniq in conhecidos:
                continue
            conhecidos.add(uniq)
            vistos.append(controle)
        return vistos

    def _controles_da_mesa(self) -> list[dict[str, Any]]:
        """``describe_controllers()`` do backend, ou ``[]`` quando ele não sabe.

        ``getattr`` porque nem todo backend é o de produção: os dublês da suíte
        e o backend de um controle só não conhecem a pergunta, e um backend que
        não conhece a pergunta não pode virar portão silencioso.
        """
        descrever = getattr(self._backend, "describe_controllers", None)
        if not callable(descrever):
            return []
        try:
            itens = descrever()
        except Exception:  # pragma: no cover - defensivo
            logger.debug("som_mesa_ilegivel", exc_info=True)
            return []
        if not isinstance(itens, list):
            return []
        return [item for item in itens if isinstance(item, dict)]

    def numero_do_assento(self, uniq: str) -> int | None:
        """P1..P4 deste controle — o número que vai no rótulo do nó.

        **A MESMA REGRA do ``BtMicSubsystem.numero_do_assento``, palavra por
        palavra, e é obrigatório que seja:** os dois rótulos que ela lê —
        «Alto-falante do Controle N» e «Microfone do Controle N» — têm de dizer
        o MESMO número sobre o MESMO aparelho, lado a lado na mesma lista de
        som. A regra é *filtrar por ``connected`` e enumerar a partir de 1*, e
        as duas armadilhas que ela evita estão medidas em 09/09/2026:

        * **não é o ``index``** de ``describe_controllers()``: aquele é a
          posição em ``list(self._handles)``, que conta o controle DESLIGADO —
          dá assento a quem não está na mesa e rouba o assento 1 de quem está;
        * **não é ``coop.resolve_player_numbers``**: com o co-op desligado ele
          responde ``1`` para todos, e a lista dela ganharia quatro
          «Alto-falante do Controle 1».

        **DUAS IMPLEMENTAÇÕES DA MESMA REGRA É DÍVIDA, e ela está declarada:**
        a de lá vive em ``daemon/subsystems/bt_mic.py``, que não está na posse
        desta sprint, então não deu para as duas chamarem uma terceira. O que
        segura o par é régua, não boa vontade —
        ``tests/unit/test_o_som_por_controle_cai_em_cada_um.py`` alimenta as
        DUAS com a mesma mesa e reprova a divergência.

        Sem daemon vivo não há assento: ``None`` é *"não sei o número"*, e o
        rótulo nasce sem número — nunca com um inventado.
        """
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        chave = norm_mac(str(uniq)) or ""
        if len(chave) != _UNIQ_HEX:
            return None
        conectados = [i for i in self._controles_da_mesa() if i.get("connected")]
        for posicao, item in enumerate(conectados, start=1):
            if (norm_mac(str(item.get("uniq") or "")) or "") == chave:
                return posicao
        return None

    def uniqs_com_no(self) -> frozenset[str]:
        """Os ``uniq`` cujo nó está DE PÉ agora — o efeito, não o pedido."""
        gerenciador = self._gerenciador
        if gerenciador is None:
            return frozenset()
        try:
            return frozenset(gerenciador.nos)
        except Exception:  # best-effort: o relato nunca derruba o state_full
            logger.debug("som_nos_ilegiveis", exc_info=True)
            return frozenset()

    # -----------------------------------------------------------------
    # SFX-POR-CONTROLE-01 (10/09/2026) — a fonte de CADA controle
    # -----------------------------------------------------------------
    # `GerenciadorDeNosDeSom` aceita `fonte_por_controle` desde que nasceu, e
    # **ninguém o injetava** — exatamente a mesma família do
    # `ponte_do_radio_por_controle` que a A1 fiou. Consequência para quem joga:
    # o campo `speaker.fonte` do perfil dela existia, a aba o gravava, e todo
    # nó nascia com `FONTE_PADRAO`. A escolha morria no disco.
    #
    # A DIFERENÇA ENTRE AS DUAS FONTES É A CENA DELA:
    #
    # * `sfx` — o nó fica LIVRE para a corrente que o jogo mandar. É o tiro
    #   saindo no plástico DAQUELE jogador, e é o padrão;
    # * `mix` — o monitor da SAÍDA PADRÃO cai também neste nó. É o «HDMI
    #   completo» dela: o que a TV recebe, o controle recebe junto.
    #
    # Numa mesa de quatro isso é por pessoa: o P1 pode querer o mix inteiro no
    # ouvido e o P2 só os efeitos do jogo. Um nó que ignora a escolha entrega
    # a mesma coisa aos quatro.

    def _fonte_do_controle(self, uniq: str) -> str:
        """`mix` ou `sfx` para ESTE controle, lido do perfil ativo dela.

        **NÃO LÊ DISCO NO LAÇO.** A varredura roda a cada
        :data:`RECONCILIA_S`; reler o perfil ali seria a tempestade de syscalls
        que o mapa de motores do `gamepad.py` já pagou uma vez. O cache é por
        `(nome do perfil, mtime do arquivo)`, então a escolha dela vale na
        varredura seguinte ao "Salvar" e nem um instante depois.
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import FONTE_PADRAO

        fontes = self._fontes_do_perfil()
        return fontes.get(_uniq_de_perfil(uniq)) or FONTE_PADRAO

    def _fontes_do_perfil(self) -> dict[str, str]:
        """`{uniq: fonte}` do perfil ativo — e `{}` é resposta honesta.

        Sem perfil ativo, com o arquivo ilegível, ou sem a seção `speaker` em
        override nenhum, a resposta é vazia e cada nó fica com o padrão. O que
        ela NUNCA pode ser é um palpite: publicar `mix` em quem não pediu põe
        o áudio do sistema inteiro no ouvido daquele jogador.
        """
        from hefesto_dualsense4unix.utils.session import load_last_profile

        try:
            nome = (
                getattr(getattr(self, "_store", None), "active_profile", None)
                or load_last_profile()
            )
        except Exception:  # pragma: no cover - defensivo
            nome = None
        if not nome:
            self._fontes_em_cache = ({}, None)
            return {}

        carimbo = _carimbo_do_perfil(nome)
        cacheado, chave = self._fontes_em_cache
        if chave == (nome, carimbo):
            return cacheado

        fontes = _fontes_por_controle(nome)
        self._fontes_em_cache = (fontes, (nome, carimbo))
        logger.debug("som_fontes_relidas", perfil=nome, controles=len(fontes))
        return fontes

    # -----------------------------------------------------------------
    # SOM-FIADO-01 (10/09/2026) — a ponte por rádio sobe DE VERDADE
    # -----------------------------------------------------------------
    # `PonteDeSomPorRadio` nasceu em 10/09 com régua e com o report que TOCOU,
    # e **ninguém a construía**: o único lugar onde o nome aparecia fora do
    # módulo que a define era a assinatura de um construtor. O degrau era
    # MONTOU, e a conferência daquele dia pegou o mapa chamando isso de "existe
    # no produto".
    #
    # É AQUI QUE A FIAÇÃO ACONTECE, e ela é POR CONTROLE: uma ponte por `uniq`,
    # com o hidraw DAQUELE controle e o monitor do nó DAQUELE controle. Uma
    # ponte compartilhada mandaria o som do P2 pelo alto-falante do P1 — a
    # mesma família do `sink_do_controle` no cabo.

    def _ponte_do_radio_de(self, uniq: str) -> Any:
        """O callable que diz se a ponte DESTE controle está no ar.

        `None` é resposta honesta e o padrão: sem ponte, `rota_do_no` recusa o
        rádio com a frase certa. O que ele NUNCA pode ser é um `lambda: True`
        otimista — isso publicaria rota sobre uma ponte inexistente e o nó
        voltaria a ser o sumidouro que
        `tests/unit/test_o_no_de_som_nao_nasce_sumidouro.py` trava.
        """
        ponte = self._pontes.get(uniq)
        if ponte is None:
            return None
        return ponte.esta_de_pe

    def _casar_as_pontes(self, controles: list[Any]) -> None:
        """Sobe uma ponte por controle NO RÁDIO, e derruba a de quem saiu.

        Roda na thread de reconciliação, junto com os nós — as duas coisas
        respondem à mesma lista, e separá-las abriria a janela em que o nó
        existe e a ponte não (ou o contrário).
        """
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            PonteDeSomPorRadio,
            e_radio,
            fonte_do_monitor_do_no,
            nome_do_sink,
        )
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            o_microfone_esta_no_ar,
        )

        vivos: dict[str, str] = {}
        for c in controles:
            uniq = str(getattr(c, "uniq", "") or "")
            if uniq and e_radio(str(getattr(c, "transporte", "") or "")):
                vivos[uniq] = str(getattr(c, "caminho", "") or "")

        for uniq in [u for u in self._pontes if u not in vivos]:
            ponte = self._pontes.pop(uniq, None)
            if ponte is not None:
                ponte.descer()
                logger.info("som_ponte_derrubada", uniq=uniq)

        for uniq, caminho in vivos.items():
            if uniq in self._pontes:
                continue
            if not caminho:
                continue
            fonte, gravador, motivo = fonte_do_monitor_do_no(nome_do_sink(uniq))
            if fonte is None:
                logger.info("som_ponte_sem_fonte", uniq=uniq, motivo=motivo)
                continue
            # O CAMINHO VAI NO FECHO, e o `functools.partial` diz o tipo: um
            # `lambda c=caminho: …` amarra igual, mas o mypy não infere o tipo
            # do default e o portão reprova.
            # O BIT DO MICROFONE VAI JUNTO, E ELE É PERGUNTADO A CADA REPORT
            # — 10/09/2026, queixa dela com o som tocando pelo rádio. O `0x35`
            # carrega, no bit 0 dos enables, o mesmo microfone; a ponte nascia
            # com ele em ZERO e o repetia 93,75 vezes por segundo, desligando
            # o microfone dela enquanto o som saía. Quem responde é o
            # `BtMicSubsystem`, pelo gancho — nenhum subsystem importa o
            # outro. `functools.partial` e não `lambda` pela mesma razão do
            # `abrir_hidraw` acima: o mypy infere o tipo do primeiro.
            ponte = PonteDeSomPorRadio(
                uniq=uniq,
                abrir_hidraw=functools.partial(self._abrir_hidraw, caminho),
                fonte_de_pcm=fonte,
                com_microfone=functools.partial(o_microfone_esta_no_ar, uniq),
                gravador=gravador,
            )
            if ponte.subir():
                self._pontes[uniq] = ponte
            else:
                ponte.descer()
                logger.info("som_ponte_nao_subiu", uniq=uniq, motivo=ponte.motivo)

    def _abrir_hidraw(self, caminho: str) -> int | None:
        """O fd de escrita daquele nó, pelo BROKER — nunca por `os.open` cru.

        Com o co-op ligado os hidraw dos físicos estão escondidos, e só o
        broker os entrega. É a mesma porta que todo instrumento desta casa usa.
        """
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            abrir_hidraw,
        )

        try:
            return abrir_hidraw(caminho, escrita=True).fd
        except Exception:
            logger.debug("som_hidraw_nao_abriu", caminho=caminho, exc_info=True)
            return None

    async def start(self, ctx: DaemonContext) -> None:
        """Sobe a thread de reconciliação. Idempotente.

        Nada de bloquear o event loop: a varredura do sysfs e o ``pactl`` do
        ``load-module`` rodam na thread.
        """
        self._backend = getattr(ctx, "controller", None)
        if self._thread is not None and self._thread.is_alive():
            return
        self._instalar_o_numerador()
        self._store = getattr(ctx, "store", None)
        self._gerenciador = self._gerenciador_injetado or GerenciadorDeNosDeSom(
            ponte_do_radio_por_controle=self._ponte_do_radio_de,
            fonte_por_controle=self._fonte_do_controle,
        )
        self._parar.clear()
        self._thread = threading.Thread(
            target=self._loop, name="hefesto-som-sup", daemon=True
        )
        self._thread.start()
        logger.info("som_subsystem_iniciado")

    async def stop(self) -> None:
        """Derruba os nós. Idempotente.

        O ``join`` sai do event loop por ``to_thread``: segurar o loop do
        daemon por uma varredura em curso atrasaria o shutdown inteiro.
        """
        self._parar.set()
        gerenciador = self._gerenciador
        if gerenciador is not None:
            with contextlib.suppress(Exception):
                gerenciador.parar()
        thread = self._thread
        self._thread = None
        if thread is not None:
            with contextlib.suppress(Exception):
                await asyncio.to_thread(thread.join, 2.0)
        # As pontes MORREM COM O SUBSYSTEM. Cada uma segura um fd de hidraw e
        # um `pw-record`; deixá-las de pé depois do `stop()` é vazar os dois
        # por controle, e o próximo `start()` abriria um segundo par.
        for uniq, ponte in list(self._pontes.items()):
            with contextlib.suppress(Exception):
                ponte.descer()
            self._pontes.pop(uniq, None)
        self._gerenciador = None
        self._desinstalar_o_numerador()
        self._backend = None
        logger.info("som_subsystem_parado")

    # -- o número do assento, que é do rótulo e de mais nada --------------

    def _instalar_o_numerador(self) -> None:
        """Instala o numerador de assento **só se ninguém o estiver atendendo**.

        O registro é UM (``dualsense_bt_audio.registrar_numerador_de_assento``)
        e serve aos dois rótulos, porque a resposta tem de ser a mesma nos
        dois. Quem chega primeiro atende; quem chega depois não derruba o
        dono, e a prova de que havia dono é o valor devolvido pelo registro —
        não existe leitor, e inventar um seria API nova por conveniência.

        Sem isto, subir este subsystem depois do ``BtMicSubsystem`` trocaria o
        numerador dele pelo nosso no meio da sessão, com os dois respondendo o
        mesmo — troca sem efeito e com risco.
        """
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            registrar_numerador_de_assento,
        )

        anterior = registrar_numerador_de_assento(self.numero_do_assento)
        if anterior is not None:
            registrar_numerador_de_assento(anterior)
            self._numerador_anterior = Ellipsis
            return
        self._numerador_anterior = anterior

    def _desinstalar_o_numerador(self) -> None:
        """Devolve o numerador anterior — e só se tiver sido ELE a instalar."""
        if self._numerador_anterior is Ellipsis:
            return
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            registrar_numerador_de_assento,
        )

        with contextlib.suppress(Exception):
            registrar_numerador_de_assento(self._numerador_anterior)
        self._numerador_anterior = Ellipsis

    # -- laço -------------------------------------------------------------

    def _loop(self) -> None:
        gerenciador = self._gerenciador
        if gerenciador is None:
            return
        while not self._parar.is_set():
            try:
                self._reconciliar(gerenciador)
            except Exception as exc:  # nunca derruba a thread
                logger.debug("som_reconciliacao_falhou", err=str(exc))
            if self._parar.wait(RECONCILIA_S) or gerenciador.dormir(0.0):
                return

    def _reconciliar(self, gerenciador: Any) -> None:
        """Uma varredura: quem está na lista ganha nó, quem saiu perde.

        Passa os CONTROLES, não os ``uniq``: quem resolve a rota precisa do
        transporte ao lado, e ir buscá-lo depois seria uma segunda varredura de
        sysfs com a chance de discordar da primeira — que é o defeito que
        `bt_mic._conectados_da_mesa` já pagou.
        """
        alvos = self.alvos(list(self._fonte()))
        # A PONTE PRIMEIRO, O NÓ DEPOIS — e a ordem é medida, não estética.
        # `rota_do_no` pergunta à ponte se ela está de pé no momento em que o
        # nó nasce. Fiar na ordem inversa publicaria a rota do rádio como
        # recusada e só a corrigiria na varredura seguinte, 2 s depois: o jogo
        # que abrisse o nó nesse intervalo pegaria a rota errada.
        self._casar_as_pontes(alvos)
        gerenciador.reconciliar(alvos)


__all__ = [
    "RECONCILIA_S",
    "AltoFalanteSubsystem",
    "ControleNaLista",
    "GerenciadorDeNosDeSom",
    "controles_na_lista",
]
