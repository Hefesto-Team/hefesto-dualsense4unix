"""central_do_radio.py — mover, parear, equilibrar e conferir (MOVER-UM-POR-VEZ-01).

A palavra, 23/09/2026, e é a especificação: *"moveriamos por exemplo 1
controle por vez. Apagaria esse um controle, o user, aperta os botões do
controle pra sincronizar aquele controle e ele estaria no novo dispositivo. E
não apagar tudo."* <!-- noqa-acento: citação literal -->

O QUE O ESTUDO DE 23/09 DERRUBOU, e por isso o mover é este
===========================================================
* Copiar a chave do bond entre adaptadores NÃO move: a chave é presa aos dois
  endereços, e o controle guarda UM host. Mover é re-parear (R1).
* O host não liga o controle (``ReconnectMode="device"``): o adaptador só se
  escolhe no PAREAR (D8). Por isso o «Conectar» também passa por aqui.

LER → DECIDIR → APLICAR → CONFERIR
==================================
* **LER** pelo dono do BlueZ (``bluez_dbus``): em que adaptadores o aparelho
  tem objeto e bond, e quais adaptadores a mesa tem. Onde o controle ESTÁ vem
  do kernel — o ``HID_PHYS`` do hidraw (``radio_da_mesa.adaptador_por_uniq``).
* **DECIDIR**: o destino pedido, ou o da D8 (``plano_de_radio.ordem_dos_destinos``
  — uma regra só para «onde parear» e para o «Equilibrar»).
* **APLICAR**, TUDO dentro da trava comum (``diario_do_radio.trava_do_radio``,
  pela borda do dono): a conexão velha que o aparelho tenha no DESTINO sai
  primeiro (é dele — a R6 revista permite); o aparelho é DESLIGADO e a conexão
  dele em cada ORIGEM é esquecida — pelo ``RemoveDevice`` do dono e pelo verbo
  ``esquecer`` da ponte root (bond em disco, cache SDP e a LÁPIDE que impede o
  autorestore de ressuscitá-lo); só então a janela de pareamento abre SÓ no
  destino, com ``Powered`` ligado se preciso e ``Pairable`` ligado SÓ durante a
  janela; o ``Pair`` é atendido pelo agente próprio (R5), e sem ele pelo piso;
  depois o nome dela (o ``Alias``) vai junto, e ``Connect``.
* **CONFERIR** — o coração: até :data:`CONFERIR_S` lendo o ``HID_PHYS`` no
  adaptador pretendido e o movimento chegando. Só com os dois o estado vira
  :data:`CHEGOU`.

A ORDEM É DESLIGAR → ESQUECER A ORIGEM → PAREAR → CONFERIR, e é a R1 dela ao pé
da letra: *«Apagar a conexão no adaptador antigo, pedir PS + Create, e parear
só no destino.»* FATO SUBSTITUÍDO (A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01,
25/09/2026): de 23/09 a 25/09 a ordem foi parear → conferir → esquecer, por
decisão registrada, para que um parear que falhasse não perdesse a
conexão velha. A lista dela de 25/09 mediu o preço (passos c1 e c2): com o
controle LIGADO na origem, o DualSense não entra em modo de parear — *«a
instrução "segure PS + Create" não faz sentido com ele ligado»* —, e o controle
que ainda tem a chave na origem volta para lá sozinho. O produto faz a parte
dele antes de pedir o gesto: desliga o controle e esquece a origem. Um parear
que falha deixa o controle sem casa, e o «Conectar» o traz de volta em qualquer
adaptador, com o mesmo PS + Create. <!-- noqa-acento: citação literal -->

OS TRÊS ESTADOS que a tela lê
=============================
:data:`ESPERANDO` (o gesto em curso, ou aplicado e ainda não conferido),
:data:`CHEGOU` e :data:`NAO_CHEGOU`. **Sem conferência o estado nunca é
«chegou»**: um aplicar que o BlueZ disse que deu, e que o ``HID_PHYS`` não
confirma, fica em «esperando» — e é vigiado, sem a trava, até
:data:`PRAZO_DO_PENDENTE_S`. Se o controle aparece no destino, vira «chegou»;
se o prazo acaba, «não chegou» — e a MEIA CHAVE que o ``Pair`` deixou no
destino sai antes do veredito (:meth:`CentralDoRadio._fechar_sem_chegar`), em
TODA saída sem chegada; sem a trava, ela fica devida e sai na primeira vez em
que a central a tem (:meth:`CentralDoRadio._pagar_as_meias_chaves`). O
prazo é UM, o da tela também, e o pedido seguinte não espera a vigia para
encontrá-lo vencido (:meth:`CentralDoRadio._vencer_os_prazos`).

O NOME DO USUÁRIO mora pelo endereço do controle, e não na chave
(:meth:`CentralDoRadio.cuidar_dos_nomes`, O-RADIO-CONECTA-ONDE-ELA-MANDA-02).

IDEMPOTÊNCIA É REQUISITO
========================
Rodar duas vezes não move nada duas vezes: o mover em curso devolve o mesmo
movimento, e o aparelho que já está no destino, sem bond em outro lugar, volta
«chegou» sem uma escrita no rádio. Nada aqui cria nó de som.

UM POR VEZ, TAMBÉM NO ARRASTAR (A-COSTURA-DA-ONDA-2-01)
======================================================
Com um movimento em curso — no gesto, ou aplicado e ainda «esperando» a
conferência, já sem a trava —, nenhum outro começa: o pedido volta
:data:`MOTIVO_OCUPADO`, e o botão treme. A conferida é feita duas vezes, antes
e DEPOIS de pegar a trava, porque o outro pode nascer enquanto este espera.

O DESTINO SEGUE A CAIXA QUE ELA ABRIU (O-CONECTAR-SEGUE-A-CAIXA-QUE-ELA-ABRIU-01):
o pedido para o MESMO movimento, ainda antes de o aparelho aparecer na janela
(:data:`PASSOS_EM_QUE_O_DESTINO_MUDA`), não é outro movimento — é o chip dela
levando a busca junto. A janela fecha onde estava e recomeça no destino novo
(:meth:`CentralDoRadio._mudar_o_destino`), e um «Mover» segue «Mover» do
mesmo controle.

O «CONECTAR» (D8) é o mesmo caminho sem alvo: a janela abre no destino com
mais vaga de ponte (:func:`plano_de_radio.ordem_dos_destinos`), e NADA PAREIA
SEM O CLIQUE DO USUÁRIO (O-PAREAR-ESPERA-O-CLIQUE-01, D-3009-O-PAREAR-E-O-CLIQUE-DELA,
30/09/2026, a validar pelo usuário): a janela pareia o aparelho que
o usuário escolheu no «Parear» da linha dele (:meth:`CentralDoRadio._a_escolha_dela`),
e só um que a janela viu (o «Parear de Novo» escolhe antes). Até 30/09 ela pareava o primeiro
controle que aparecesse, em meio segundo, antes de a tela o mostrar. E O CONTROLE QUE VOLTA PELO
PAREAMENTO ANTIGO também chega (a foto 2 da lista dela de 25/09: *«conectou com
algum mas não apareceu na lista»*): quem ela liga só com o PS reconecta no
adaptador que já tinha a chave dele, sem passar pela janela. O controle que se
conecta durante a janela e não estava conectado quando ela abriu é o dela; o
«Conectar» acaba «chegou» ONDE ele chegou (:data:`MOTIVO_PELO_PAREAMENTO_ANTIGO`),
e a tela o mostra chegando. <!-- noqa-acento: citação literal -->

O «EQUILIBRAR» (R12) é :func:`plano_de_radio.ordem_de_redistribuicao` — dona
desde 20/09. Esta central só a chama, e só quando nenhum movimento está
«esperando»: um de cada vez.

A FAXINA (A-SOBRA-DO-BOND-SAI-SOZINHA-01, 25/09/2026)
======================================================
O mover desta central esquece a origem no fim. Um mover feito à mão, ou antes
de ela existir, deixa a chave velha para trás: o controle fica com bond em dois
adaptadores, e na bancada o P2 ficou assim de 19/09 a 25/09, com o ``doctor``
acusando e ninguém arrumando. A pergunta, 25/09: *«A interface do app não
deveria corrigir isso automaticamente?»* Deveria, e a decisão é de quem
coordena: o controle guarda UM host, e quando o kernel o diz conectado num
adaptador (``HID_PHYS``) ele mesmo respondeu qual chave vale. A do outro
adaptador é sobra, e sai como sai a origem de um mover: ``RemoveDevice`` mais o
verbo ``esquecer`` da ponte, com lápide. :meth:`CentralDoRadio.esquecer_as_sobras`
faz UMA por volta, dentro da trava, e nunca com um movimento «esperando» (o mover
cuida da própria origem). Controle desligado, ou no cabo, não diz qual chave
vale, e aí nada sai: a sobra espera ele conectar pelo rádio.

O QUE ESTE MÓDULO NÃO FAZ
=========================
Não fala com a tela (nada de recado, R8), não move a webcam (não é do rádio)
e nunca apaga em lote. No «Conectar» pareia UM aparelho — o que o usuário escolheu
na lista —, e nenhum sem o clique do usuário.
"""

from __future__ import annotations

import contextlib
import re
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.integrations.conexao_zumbi import (
    PONTE_INSTALADA,
    PedidoAPonte,
    mac_limpo,
    pedido_a_ponte,
)
from hefesto_dualsense4unix.integrations.gesto_de_pareamento import (
    ESTADO_JA_PAREADO,
    ESTADO_PAREOU,
    SEGUNDOS_DA_JANELA,
    SEGUNDOS_MAX,
    JanelaDeBusca,
    Resultado,
    e_controle,
)
from hefesto_dualsense4unix.integrations.gesto_de_reconexao import mascarar
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

QUEM = "central"


ESPERANDO = "esperando"
CHEGOU = "chegou"
NAO_CHEGOU = "nao_chegou"  # (noqa-acento): chave de máquina
ESTADOS = (ESPERANDO, CHEGOU, NAO_CHEGOU)

CONECTANDO = ""


PASSO_PREPARANDO = "preparando"
PASSO_DESLIGANDO = "desligando"
PASSO_GESTO = "gesto"
PASSO_PAREANDO = "pareando"
PASSO_CONFERINDO = "conferindo"
PASSO_ESQUECENDO = "esquecendo"
PASSO_FIM = "fim"
PASSOS_EM_QUE_O_DESTINO_MUDA = frozenset({PASSO_PREPARANDO, PASSO_DESLIGANDO, PASSO_GESTO})


#: dela: *«moveriamos por exemplo 1 controle por vez»*). <!-- noqa-acento: citação literal -->
MOTIVO_OCUPADO = "ocupado"
MOTIVO_SEM_BLUEZ = "sem_bluez"
MOTIVO_FORA_DO_RADIO = "fora_do_radio"
MOTIVO_SEM_DESTINO = "sem_destino"
MOTIVO_JA_ESTAVA = "ja_estava"  # (noqa-acento): chave de máquina
MOTIVO_SEM_JANELA = "sem_janela"
MOTIVO_SEM_GESTO = "sem_gesto"
MOTIVO_NAO_PAREOU = "nao_pareou"  # (noqa-acento): chave de máquina
MOTIVO_SEM_CONFIRMACAO = "sem_confirmacao"
MOTIVO_VOLTOU = "voltou"
MOTIVO_PRAZO = "prazo"
MOTIVO_FALHOU = "falhou"
MOTIVO_PELO_PAREAMENTO_ANTIGO = "pelo_pareamento_antigo"
MOTIVO_DESLIGADA = "desligada"


MOVEU_O_APARELHO = "moveu um aparelho"
O_APARELHO_NAO_CHEGOU = "o aparelho não chegou"
ESQUECEU_A_SOBRA = "esqueceu a sobra de um bond"
ESQUECEU_A_MEIA_CHAVE = "esqueceu a meia chave de um pareamento que não chegou"
VOLTOU_PELO_PAREAMENTO_ANTIGO = "o controle voltou pelo pareamento antigo"
NAO_LIMPOU_SEM_LAPIDE = "não limpou: sem lápide"
ENTERROU_O_QUE_SAIU_POR_FORA = "gravou a lápide de um pareamento tirado por fora"


ICONE_DE_CONTROLE = "input-gaming"

#: O ``Modalias`` do controle cujo movimento o daemon lê: o DualSense (Sony
_MODALIAS_QUE_O_DAEMON_MEDE = re.compile(r"v054Cp(0CE6|0DF2)", re.IGNORECASE)


PRAZO_DA_TRAVA_DO_GESTO_S = 5.0

CONFERIR_S = 10.0

PASSO_S = 0.5

PRAZO_DO_PENDENTE_S = 60.0

#: A chave que o movimento acabou de fazer e que ainda não conectou recebe ``Trusted`` e
#: ``Connect`` de novo a cada tanto, até o prazo (O-CONTROLE-NOVO-SE-CONECTA-E-SE-TIRA-…-01).
REPROVOCAR_S = 5.0

ESPERA_DO_SUMICO_S = 2.0

ESPERA_DO_DESLIGAR_S = 3.0

#: cada ``state_full``, e pelo caminho de reserva (``busctl``) cada foto custa
VALIDADE_DOS_ADAPTADORES_S = 2.0

ESPERA_DA_PONTE_S = 20.0

INTERVALO_DA_FAXINA_S = 30.0

_FIO_DA_FAXINA = "faxina"

INTERVALO_DOS_NOMES_S = 2.0

LEMBRA_O_NAO_CONECTOU_S = 600.0

ESPERA_DA_LAPIDE_DE_FORA_S = 60.0

PARES_POR_LIMPEZA = 32

#: *«limpar com frequencia a cada troca <!-- noqa-acento: citação literal -->
DEPOIS_DE_UMA_TROCA = "depois de uma troca"
QUANDO_O_CONTROLE_DESLIGOU = "quando o controle desligou"
NA_VOLTA_DA_FAXINA = "na volta da faxina"


@dataclass(frozen=True)
class Movimento:
    """UM aparelho sendo movido para UM adaptador. Imutável: cada passo é outro."""

    aparelho: str
    destino: str
    estado: str
    passo: str
    motivo: str = ""
    origens: tuple[str, ...] = ()
    e_controle: bool = True
    pareou_no_destino: bool = False
    origens_esquecidas: bool = False
    classe: int | None = None
    modalias: str = ""
    icone: str = ""
    nome: str = ""
    comecou: float = 0.0
    quando: float = field(default_factory=time.time)
    #: o relógio da central e a hora de parede do ``Pair`` que deu; 0 = ainda não pareou
    pareou_em: float = 0.0
    pareou_quando: float = 0.0

    @property
    def em_curso(self) -> bool:
        return self.estado == ESPERANDO

    @property
    def prazo_desde(self) -> float:
        """O prazo da chave nova conta do ``Pair``, não da janela: no diário de 06/10 ela segurou
        PS + Create 16 s depois de a janela abrir, e a chave viveu só os 42 s que sobravam."""
        return self.pareou_em or self.comecou

    def publicar(self) -> dict[str, Any]:
        """O que viaja no ``state_full`` — só tipos de JSON."""
        return {
            "aparelho": self.aparelho,
            "destino": self.destino,
            "estado": self.estado,
            "passo": self.passo,
            "motivo": self.motivo,
            "origens": list(self.origens),
            "e_controle": self.e_controle,
            "classe": self.classe,
            "modalias": self.modalias,
            "icone": self.icone,
            "nome": self.nome,
            "quando": round(self.quando, 3),
            "prazo_desde": round(self.pareou_quando or self.quando, 3),
        }


OndeEsta = Callable[[str], str]

Movimentacao = Callable[[str], "float | None"]

EsquecerNaPonte = Callable[[str, str], "tuple[bool, str]"]


class GuardaDosNomes(Protocol):
    """Onde mora o nome que ela deu a cada controle, pelo ENDEREÇO dele."""

    def ler(self) -> Mapping[str, str] | None:
        """``{endereço aa:bb:…: nome}``; ``None`` = não deu para ler (não é «não há»)."""
        ...

    def gravar(self, aparelho: str, nome: str | None) -> bool:
        """Grava o nome (``None`` esquece). ``False`` = não gravou."""
        ...


class NomesNaMaquina:
    """O nome dela no ``maquina.json`` (``ControleDeclarado.nome``) — o dono é"""

    def __init__(self) -> None:
        self._lido: tuple[tuple[int, int] | None, dict[str, str]] | None = None

    def ler(self) -> Mapping[str, str] | None:
        from hefesto_dualsense4unix.utils import maquina

        try:
            estado = maquina.caminho_da_maquina().stat()
            marca: tuple[int, int] | None = (estado.st_mtime_ns, estado.st_size)
        except FileNotFoundError:
            marca = None
        except OSError:
            return None
        if self._lido is not None and self._lido[0] == marca:
            return dict(self._lido[1])
        nomes: dict[str, str] = {}
        for chave, nome in maquina.nomes_dos_controles(maquina.carregar_maquina()).items():
            endereco = endereco_de(chave)
            if endereco is not None:
                nomes[endereco] = nome
        self._lido = (marca, nomes)
        return dict(nomes)

    def gravar(self, aparelho: str, nome: str | None) -> bool:
        from hefesto_dualsense4unix.utils.maquina import gravar_o_nome_do_controle

        return gravar_o_nome_do_controle(aparelho, nome)


class Janela(Protocol):
    """O que a central usa de uma :class:`gesto_de_pareamento.JanelaDeBusca`."""

    @property
    def aberta(self) -> bool: ...

    def abrir_a_janela(self) -> str: ...

    def candidatos(self) -> tuple[Any, ...]: ...

    def parear(self, endereco: str) -> Resultado: ...

    def fechar(self) -> None: ...


AbrirJanela = Callable[[str, int, bluez_dbus.LeitorDoBluez], Janela]


def _hex12(endereco: str) -> str:
    """``aa:bb:…`` → ``aabb…`` — a forma do ``uniq`` do estado do daemon."""
    return endereco.replace(":", "").lower()


def _entrada(dono: bluez_dbus.LeitorDoBluez, objeto: bluez_dbus.AparelhoDoBluez) -> int:
    """Quantas vezes o objeto ENTROU no BlueZ desde a foto — o dono vivo conta"""
    contar = getattr(dono, "entrada", None)
    return int(contar(objeto.caminho)) if callable(contar) else 0


def endereco_de(valor: object) -> str | None:
    """O endereço do aparelho, pelas duas formas que circulam: com ``:`` ou 12 hex."""
    if not isinstance(valor, str):
        return None
    texto = valor.strip().lower()
    if len(texto) == 12 and all(c in "0123456789abcdef" for c in texto):
        texto = ":".join(texto[i : i + 2] for i in range(0, 12, 2))
    return mac_limpo(texto)


def _onde_esta_pelo_hid_phys(uniq: str) -> str:
    """O adaptador em que o kernel diz que o controle está — pelo dono do número."""
    from hefesto_dualsense4unix.integrations.radio_da_mesa import adaptador_por_uniq

    return adaptador_por_uniq([uniq]).get(uniq, "")


def esquecer_pela_ponte(
    adaptador: str,
    aparelho: str,
    *,
    caminho: str = PONTE_INSTALADA,
    correr: Callable[[PedidoAPonte], tuple[int, str]] | None = None,
) -> tuple[bool, str]:
    """O verbo ``esquecer`` da ponte root: bond em disco, cache SDP e a lápide."""
    try:
        pedido = pedido_a_ponte("esquecer", adaptador, aparelho, caminho=caminho)
    except ValueError:
        return False, "o endereço não tem forma de endereço"
    if correr is None:
        if bluez_dbus.a_suite_esta_rodando():
            return False, "a suíte está no ar e esta é a ponte de verdade"
        correr = _correr_a_ponte
    codigo, erro = correr(pedido)
    if codigo == 0:
        return True, ""
    return False, erro or f"a ponte saiu com {codigo}"


def _correr_a_ponte(pedido: PedidoAPonte) -> tuple[int, str]:
    """Roda o pedido até o fim, com os dados pelo stdin — nunca o de quem chamou."""
    try:
        feito = subprocess.run(
            list(pedido.argv),
            input=pedido.entrada,
            capture_output=True,
            text=True,
            timeout=ESPERA_DA_PONTE_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as erro:
        return 1, f"a ponte não respondeu: {erro}"
    return feito.returncode, (feito.stderr or "").strip()


def _janela_de_busca(
    destino: str, segundos: int, dono: bluez_dbus.LeitorDoBluez
) -> Janela:
    """A janela no destino: a do dono vivo, ou a da ponte root quando ele não há."""
    if not dono.atende_o_proprio_pareamento and bluez_dbus.a_suite_esta_rodando():
        return JanelaDeBusca(
            destino, segundos, abrir=_recusar_a_ponte_sob_a_suite, correr=_nao_correr_sob_a_suite
        )
    return JanelaDeBusca(destino, segundos, dono=dono)


def _recusar_a_ponte_sob_a_suite(_pedido: PedidoAPonte) -> subprocess.Popen[str]:
    raise OSError("a suíte está no ar e esta é a ponte de verdade")


def _nao_correr_sob_a_suite(_pedido: PedidoAPonte) -> tuple[int, str]:
    return 1, "a suíte está no ar e esta é a ponte de verdade"


def _o_bluez_diz_controle(objetos: Iterable[bluez_dbus.AparelhoDoBluez]) -> bool | None:
    """A CLASSE decide quando algum objeto a tem; sem ela, o ``Icon`` que o"""
    vistos = tuple(objetos)
    for objeto in vistos:
        if objeto.classe is not None:
            return e_controle(objeto.classe)
    icones = {objeto.icone for objeto in vistos if objeto.icone}
    if icones:
        return ICONE_DE_CONTROLE in icones
    return None


@dataclass(frozen=True)
class _Foto:
    adaptadores: Mapping[str, bluez_dbus.AdaptadorDoBluez]
    do_aparelho: Mapping[str, bluez_dbus.AparelhoDoBluez]


def _ler(dono: bluez_dbus.LeitorDoBluez, aparelho: str) -> _Foto | None:
    """A mesa pelo dono. ``None`` = não deu para perguntar — nunca «não há»."""
    adaptadores = dono.adaptadores()
    if adaptadores is None:
        return None
    aparelhos = dono.aparelhos()
    if aparelhos is None:
        return None
    por_caminho = {a.caminho: a for a in adaptadores}
    do_aparelho = {
        por_caminho[a.adaptador].endereco: a
        for a in aparelhos
        if a.endereco == aparelho and a.adaptador in por_caminho
    }
    return _Foto({a.endereco: a for a in adaptadores}, do_aparelho)


def _controles_pelo_endereco(
    aparelhos: Iterable[bluez_dbus.AparelhoDoBluez],
) -> dict[str, list[bluez_dbus.AparelhoDoBluez]]:
    """Os objetos de cada CONTROLE, pelo endereço — um por adaptador que o conhece."""
    grupos: dict[str, list[bluez_dbus.AparelhoDoBluez]] = {}
    for objeto in aparelhos:
        grupos.setdefault(objeto.endereco, []).append(objeto)
    return {e: objs for e, objs in sorted(grupos.items()) if _o_bluez_diz_controle(objs)}


def _o_nome_que_vale(
    objetos: Sequence[bluez_dbus.AparelhoDoBluez],
    dados: Mapping[str, str],
    vistos_antes: Mapping[str, str],
    guardado: str,
) -> tuple[str, bool]:
    """``(o nome que vale depois desta volta, ela apagou?)`` — ver"""
    conhecidos = [o for o in objetos if o.caminho in vistos_antes]
    renomeados = [o for o in conhecidos
                  if dados[o.caminho] and vistos_antes[o.caminho] != _alias_de(o)]
    if renomeados:
        renomeados.sort(key=lambda o: o.conectado is not True)
        return dados[renomeados[0].caminho], False
    if guardado and any(vistos_antes[o.caminho] == guardado and not dados[o.caminho]
                        and o.pareado is True for o in conhecidos):
        return "", True
    if not guardado and not conhecidos:
        com_nome = sorted((o for o in objetos if dados[o.caminho]),
                          key=lambda o: o.conectado is not True)
        if com_nome:
            return dados[com_nome[0].caminho], False
    return guardado, False


def _alias_de(objeto: bluez_dbus.AparelhoDoBluez) -> str:
    return str(objeto.nome or "").strip()


@dataclass(frozen=True)
class PedidoDePareamento:
    """Um controle CONHECIDO que pede um par novo (O-CONTROLE-QUE-PEDE-PARA-PAREAR-…-01).

    Medido em 05/10/2026: ela segurou PS + Create no «vermelho», e o BlueZ o tinha no ar no
    adaptador da Esquerda (RSSI de -56 a -62) com ``Paired``/``Bonded`` verdadeiros e
    ``Connected`` falso. O controle em modo de parear perdeu a chave; o BlueZ guarda a dele;
    nenhum dos dois conecta. O sinal é esse: conhecido + desconectado + ouvido na varredura.
    """

    aparelho: str
    #: o adaptador que o ouve mais forte, onde o par novo se faz
    adaptador: str
    rssi: int
    #: todos os adaptadores que o ouvem agora
    ouvido_por: tuple[str, ...]
    #: os adaptadores onde mora o par velho
    par_velho: tuple[str, ...]
    nome: str = ""

    def publicar(self) -> dict[str, Any]:
        return {"aparelho": self.aparelho, "adaptador": self.adaptador, "rssi": self.rssi,
                "ouvido_por": list(self.ouvido_por), "par_velho": list(self.par_velho),
                "nome": self.nome}


def pedidos_de_pareamento(
    adaptadores: Iterable[bluez_dbus.AdaptadorDoBluez],
    aparelhos: Iterable[bluez_dbus.AparelhoDoBluez],
    *,
    fora: Iterable[str] = (),
) -> tuple[PedidoDePareamento, ...]:
    """Os controles conhecidos que pedem para parear, pela foto do BlueZ.

    Conhecido = pareado em algum adaptador; desconectado em todos; e com ``RSSI`` em ao
    menos um (o BlueZ só o tem enquanto a varredura ouve o aparelho). Sem o ``RSSI`` é o
    controle desligado, e ele não aparece. ``fora`` são os que a central já está movendo.
    """
    por_caminho = {a.caminho: a.endereco for a in adaptadores}
    excluidos = {endereco_de(e) for e in fora}
    pedidos = []
    for endereco, objetos in _controles_pelo_endereco(aparelhos).items():
        daqui = [o for o in objetos if o.adaptador in por_caminho]
        if endereco_de(endereco) in excluidos or not daqui:
            continue
        if any(o.conectado is True for o in daqui):
            continue
        velhos = tuple(sorted(por_caminho[o.adaptador] for o in daqui if o.pareado is True))
        ouvidos = sorted((o for o in daqui if o.rssi is not None),
                         key=lambda o: -(o.rssi or 0))
        if not velhos or not ouvidos:
            continue
        nome = next((_alias_de(o) for o in daqui if _alias_de(o)), "")
        pedidos.append(PedidoDePareamento(
            aparelho=endereco, adaptador=por_caminho[ouvidos[0].adaptador],
            rssi=int(ouvidos[0].rssi or 0),
            ouvido_por=tuple(por_caminho[o.adaptador] for o in ouvidos),
            par_velho=velhos, nome=nome))
    return tuple(pedidos)


class CentralDoRadio:
    """O motor do mover, do parear e do «Equilibrar». Um por processo (o daemon)."""

    def __init__(
        self,
        *,
        dono: bluez_dbus.LeitorDoBluez | None = None,
        onde_esta: OndeEsta | None = None,
        movimento: Movimentacao | None = None,
        esquecer_na_ponte: EsquecerNaPonte | None = None,
        abrir_janela: AbrirJanela | None = None,
        nomes: GuardaDosNomes | None = None,
        sysfs: Mapping[str, Any] | None = None,
        relogio: Callable[[], float] = time.monotonic,
        dormir: Callable[[float], None] = time.sleep,
        segundos_da_janela: int = SEGUNDOS_DA_JANELA,
        segundos_da_busca: int = SEGUNDOS_MAX,
        conferir_s: float = CONFERIR_S,
        prazo_do_pendente_s: float = PRAZO_DO_PENDENTE_S,
        prazo_da_trava_s: float = PRAZO_DA_TRAVA_DO_GESTO_S,
    ) -> None:
        self._dono_fixo = dono
        self._onde_esta = onde_esta or _onde_esta_pelo_hid_phys
        self._movimento = movimento
        self._esquecer_na_ponte = esquecer_na_ponte or esquecer_pela_ponte
        self._abrir_janela = abrir_janela or _janela_de_busca
        self._nomes: GuardaDosNomes = nomes if nomes is not None else NomesNaMaquina()
        self._alias_vistos: dict[str, str] = {}
        self._geracao_dos_nomes = 0
        self._sysfs = dict(sysfs or {})
        self._relogio = relogio
        self._dormir = dormir
        self._segundos = int(segundos_da_janela)
        self._segundos_da_busca = int(segundos_da_busca)
        self._conferir_s = float(conferir_s)
        self._prazo_do_pendente_s = float(prazo_do_pendente_s)
        self._prazo_da_trava_s = float(prazo_da_trava_s)
        self._tranca = threading.Lock()
        self._movimentos: dict[str, Movimento] = {}
        self._destino_pedido: str | None = None
        self._escolha: str | None = None
        self._vistos_na_janela: frozenset[str] = frozenset()
        self._busca: dict[str, Any] | None = None
        self._janela_da_busca: Janela | None = None
        self._desligar = False
        self._aberturas = 0
        self._ultima_busca: dict[str, Any] | None = None
        self._meias_chaves: set[tuple[str, str]] = set()
        self._fios: dict[str, threading.Thread] = {}
        self._no_fio_atual = threading.local()
        self._parar = threading.Event()
        self._ultimos_controles: tuple[Mapping[str, Any], ...] = ()
        self._adaptadores_em_cache: tuple[float, tuple[bluez_dbus.AdaptadorDoBluez, ...]] | None = (
            None
        )
        self._refrescando = False
        #: O dono já foi aberto? Antes disso o ``state_full`` não o abre: o
        self._ligada = dono is not None
        self._dono_visto: bluez_dbus.LeitorDoBluez | None = dono
        self._tranca_da_limpeza = threading.Lock()
        self._limpeza_pedida = threading.Event()
        self._por_que_limpar = ""
        self._lembrancas: dict[str, tuple[str, frozenset[tuple[str, int]]]] = {}
        self._provocado_em: dict[str, float] = {}
        self._saidas_de_fora: list[tuple[str, str, float, str]] = []
        self._sem_lapide_dito: set[tuple[str, str]] = set()
        #: o controle que a janela escolheu sozinha por pedir para parear (o par se refaz)
        self._pedido_da_janela = ""
        self._ouvindo: object | None = None
        if dono is not None:
            self._ouvir(dono)


    def _dono(self) -> bluez_dbus.LeitorDoBluez:
        if self._dono_fixo is not None:
            return self._dono_fixo
        dono = bluez_dbus.dono()
        self._dono_visto = dono
        self._ouvir(dono)
        return dono

    def _ouvir(self, dono: bluez_dbus.LeitorDoBluez) -> None:
        """Assina os avisos do dono (o :class:`bluez_dbus.DonoVivo`): o controle"""
        with self._tranca_da_limpeza:
            if dono is self._ouvindo:
                return
            self._ouvindo = dono
        ouvir = getattr(dono, "ouvir", None)
        if callable(ouvir):
            ouvir(self._ao_aviso_do_dono)

    def _ao_aviso_do_dono(self, aviso: str, dados: Mapping[str, Any]) -> None:
        """Chega no fio do barramento: só anota e pede — nada de D-Bus aqui."""
        if aviso == bluez_dbus.AVISO_DESLIGOU:
            self._pedir_a_limpeza(QUANDO_O_CONTROLE_DESLIGOU)
        elif aviso == bluez_dbus.AVISO_SAIU_PAREADO:
            adaptador = endereco_de(dados.get("adaptador"))
            aparelho = endereco_de(dados.get("aparelho"))
            if dados.get("pela_trava") or adaptador is None or aparelho is None:
                return
            pendente = (adaptador, aparelho, self._relogio(), str(dados.get("dono") or ""))
            with self._tranca_da_limpeza:
                if not any(p[:2] == pendente[:2] for p in self._saidas_de_fora):
                    self._saidas_de_fora.append(pendente)

    def _pedir_a_limpeza(self, por_que: str) -> None:
        """Pede UMA volta da limpeza ao fio da faxina (:meth:`limpar`)."""
        with self._tranca_da_limpeza:
            if not self._por_que_limpar:
                self._por_que_limpar = por_que
        self._limpeza_pedida.set()

    def _dono_sem_abrir(self) -> bluez_dbus.LeitorDoBluez | None:
        """O último dono visto, se ainda pergunta — ``None`` sem abrir nada.

        É o do tique: sem dono vivo, ``bluez_dbus.dono()`` tenta o Gio de novo
        de forma síncrona (até ~5 s num barramento mudo), e o ``state_full``
        roda no laço do daemon.
        """
        visto = self._dono_visto
        return visto if visto is not None and visto.pode_perguntar() else None

    def ligar(self) -> bool:
        """Abre o dono do BlueZ — no arranque do daemon, fora de qualquer fio de tela."""
        dono = self._dono()
        vivo = dono.pode_perguntar()
        self._ligada = True
        logger.info("central_do_radio_ligada", vivo=vivo, pelo_dono=type(dono).__name__)
        return vivo

    def fechar(self, *, espera: float = 3.0) -> None:
        """Pede para os fios pararem e espera. Idempotente, nunca levanta."""
        self._parar.set()
        self._limpeza_pedida.set()
        with self._tranca:
            fios = list(self._fios.values())
        for fio in fios:
            if fio is not threading.current_thread():
                fio.join(timeout=espera)


    def movimentos(self) -> tuple[Movimento, ...]:
        with self._tranca:
            return tuple(self._movimentos.values())

    def movimento_de(self, aparelho: str) -> Movimento | None:
        alvo = endereco_de(aparelho)
        if alvo is None:
            return None
        with self._tranca:
            return self._movimentos.get(alvo)

    @property
    def em_curso(self) -> bool:
        """Algum movimento está «esperando»? Então o «Equilibrar» não propõe nada."""
        return any(m.em_curso for m in self.movimentos())

    def _guardar(self, movimento: Movimento) -> Movimento:
        with self._tranca:
            self._movimentos[movimento.aparelho] = movimento
            self._mudou_o_movimento(movimento)
        self._no_fio_atual.chave = movimento.aparelho
        return movimento

    def _mudou_o_movimento(self, movimento: Movimento) -> None:
        """COM A ``_tranca`` NA MÃO. O movimento que começa tira a lembrança de"""
        if movimento.em_curso:
            self._lembrancas.pop(movimento.aparelho, None)
        else:
            self._pedir_a_limpeza(DEPOIS_DE_UMA_TROCA)

    def _comecar(self, movimento: Movimento) -> Movimento:
        """O «esperando» de um movimento novo — e nenhum destino pedido para o de antes."""
        with self._tranca:
            self._destino_pedido = None
            self._escolha, self._vistos_na_janela = None, frozenset()
            self._desligar = False
        return self._guardar(movimento)

    def _sair_do_gesto(self, movimento: Movimento, **mudancas: Any) -> Movimento | None:
        """O movimento deixa a espera do gesto — para o ``Pair`` ou para o «não"""
        feito = replace(movimento, **mudancas)
        with self._tranca:
            if self._destino_pedido is not None and not self._parar.is_set():
                return None
            if feito.aparelho != movimento.aparelho:
                self._movimentos.pop(movimento.aparelho, None)
            self._movimentos[feito.aparelho] = feito
            self._mudou_o_movimento(feito)
        self._no_fio_atual.chave = feito.aparelho
        return feito

    def _falhou(self, chave: str) -> Movimento:
        """Um erro no meio do mover: o movimento deste fio acaba «não chegou»."""
        logger.warning("central_mover_levantou", aparelho=mascarar(chave), exc_info=True)
        atual = self._pela_chave(getattr(self._no_fio_atual, "chave", chave))
        if atual is None or not atual.em_curso:
            return atual or Movimento(chave, "", NAO_CHEGOU, PASSO_FIM, MOTIVO_FALHOU)
        if atual.pareou_no_destino:
            try:
                return self._fechar_sem_chegar(atual, MOTIVO_FALHOU, self._dono())
            except Exception:
                logger.warning("central_meia_chave_levantou", aparelho=mascarar(atual.aparelho),
                               exc_info=True)
        return self._acabou(atual, NAO_CHEGOU, MOTIVO_FALHOU)

    def publicar(
        self,
        controles: Iterable[Mapping[str, Any]] | None = None,
        *,
        ar: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """``state_full["radio_central"]``: os movimentos e a proposta do «Equilibrar».

        Nunca levanta: a tela lê isto a cada volta, e uma falha aqui não pode
        apagar o resto do estado.
        """
        proposta: dict[str, Any] | None = None
        if controles is not None:
            self.conhecer(controles)
        if self._ligada:
            with contextlib.suppress(Exception):
                ordem = self.propor(ar=ar, esperar=False)
                proposta = ordem.publicar() if ordem is not None else None
        return {
            "movimentos": [m.publicar() for m in self._movimentos_publicados()],
            "em_curso": self.em_curso,
            "proposta": proposta,
            "busca": self._busca_publicada(),
            "pedindo": [p.publicar() for p in self._pedidos_publicados()],
        }

    def _pedidos_publicados(self) -> tuple[PedidoDePareamento, ...]:
        """Os controles que pedem para parear, pela foto do dono vivo (memória, sem D-Bus).

        Pelo caminho de reserva a foto custaria subprocessos no tique: ali não há pedido.
        """
        vivo = self._dono_sem_abrir()
        if vivo is None or not vivo.atende_o_proprio_pareamento:
            return ()
        with contextlib.suppress(Exception):
            adaptadores, aparelhos = vivo.adaptadores(), vivo.aparelhos()
            if adaptadores is not None and aparelhos is not None:
                with self._tranca:
                    movendo = [m.aparelho for m in self._movimentos.values() if m.em_curso]
                return pedidos_de_pareamento(adaptadores, aparelhos, fora=movendo)
        return ()

    def _quem_pede_aqui(self, dono: bluez_dbus.LeitorDoBluez, destino: str) -> str:
        """O controle conhecido que pede para parear e que o ``destino`` ouve agora, ou ``""``."""
        adaptadores, aparelhos = dono.adaptadores(), dono.aparelhos()
        if adaptadores is None or aparelhos is None:
            return ""
        return next((p.aparelho for p in pedidos_de_pareamento(adaptadores, aparelhos)
                     if destino in p.ouvido_por), "")

    def _refazer_o_par_no_destino(
        self, dono: bluez_dbus.LeitorDoBluez, aparelho: str, destino: str
    ) -> None:
        """O par velho NO destino sai, e espera o controle voltar a aparecer na varredura.

        Sem isto o ``Pair`` responde «já pareado» sobre a chave que o controle perdeu.
        """
        foto = _ler(dono, aparelho)
        velho = foto.do_aparelho.get(destino) if foto is not None else None
        if velho is None or velho.pareado is not True:
            return
        self._tirar_o_velho_do_destino(dono, aparelho, destino, velho)
        fim = self._relogio() + CONFERIR_S
        while self._relogio() < fim and not self._parar.is_set():
            if dono.caminho_do_aparelho(aparelho, adaptador=destino) is not None:
                return
            self._dormir(PASSO_S)

    def _busca_publicada(self) -> dict[str, Any] | None:
        """A busca do «Procurar» como a tela a lê, ou ``None``: com o chip dela"""
        with self._tranca:
            conectando = self._movimentos.get(CONECTANDO)
            if self._busca is None or (conectando is not None and not conectando.em_curso):
                return None
            busca = dict(self._busca)
            if self._destino_pedido is not None:
                busca["adaptador"] = self._destino_pedido
            return busca

    def ligar_a_busca(self, ligada: bool, destino: str | None = None) -> dict[str, Any]:
        """O «Procurar»: liga ou desliga a busca, com valor absoluto."""
        if not ligada:
            with self._tranca:
                janela = self._janela_da_busca
                conectando = self._movimentos.get(CONECTANDO)
                if janela is None and (conectando is None or not conectando.em_curso):
                    return {"status": "ok", "busca": None}
                self._desligar = True
                self._destino_pedido = None
            if janela is not None:
                with contextlib.suppress(Exception):
                    janela.fechar()
            busca = self._esperar_a_busca(lambda b: b is None)
            return {"status": "ok" if busca is None else "ocupado", "busca": busca}
        pedido = endereco_de(destino) if destino else None
        agora = self._busca_publicada()
        if agora is not None and (pedido is None or agora["adaptador"] == pedido):
            return {"status": "ok", "busca": agora}
        with self._tranca:
            antes = self._aberturas
        self._vencer_os_prazos()
        with self._tranca:
            mover = any(m.em_curso and m.aparelho != CONECTANDO
                        for m in self._movimentos.values())
        if mover:
            return {"status": MOTIVO_OCUPADO, "busca": agora}
        feito = self.comecar_a_conectar(destino)
        if feito.motivo:
            return {"status": feito.motivo, "busca": self._busca_publicada()}

        def no_pedido(busca: dict[str, Any] | None) -> bool:
            return busca is not None and (pedido is None or busca["adaptador"] == pedido)

        fim = time.monotonic() + self._prazo_da_trava_s + 1.0
        espera = threading.Event()
        while True:
            agora = self._busca_publicada()
            with self._tranca:
                aberta = dict(self._ultima_busca) if (
                    self._aberturas > antes and self._ultima_busca is not None) else None
            for busca in (agora, aberta):
                if no_pedido(busca):
                    return {"status": "ok", "busca": busca}
            conectando = self._pela_chave(CONECTANDO)
            if conectando is None or not conectando.em_curso or time.monotonic() >= fim:
                motivo = conectando.motivo if conectando is not None else ""
                return {"status": motivo or MOTIVO_SEM_JANELA, "busca": agora}
            espera.wait(0.01)

    def _esperar_a_busca(
        self, pronta: Callable[[dict[str, Any] | None], bool]
    ) -> dict[str, Any] | None:
        """Espera, no relógio de verdade, a busca publicada ficar como pedida —"""
        fim = time.monotonic() + self._prazo_da_trava_s + 1.0
        espera = threading.Event()
        while True:
            busca = self._busca_publicada()
            conectando = self._pela_chave(CONECTANDO)
            if pronta(busca) or conectando is None or not conectando.em_curso:
                return busca
            if time.monotonic() >= fim:
                return busca
            espera.wait(0.01)

    def _movimentos_publicados(self) -> tuple[Movimento, ...]:
        """Os movimentos como a tela os lê: o destino que o usuário pediu, e que o fio"""
        with self._tranca:
            pedido = self._destino_pedido
            return tuple(self._com_o_destino_pedido(m, pedido) for m in self._movimentos.values())

    @staticmethod
    def _com_o_destino_pedido(movimento: Movimento, pedido: str | None) -> Movimento:
        """O movimento no destino pedido — se ainda é um que muda de destino, e"""
        if (pedido is None or not movimento.em_curso
                or movimento.passo not in PASSOS_EM_QUE_O_DESTINO_MUDA):
            return movimento
        return replace(movimento, destino=pedido,
                       origens=tuple(o for o in movimento.origens if o != pedido))


    def _adaptadores(
        self, *, esperar: bool = True
    ) -> tuple[bluez_dbus.AdaptadorDoBluez, ...] | None:
        """Os adaptadores do dono, numa foto que vale :data:`VALIDADE_DOS_ADAPTADORES_S`.

        ``esperar=False`` é o caminho do ``state_full``: com o dono vivo a foto
        é memória e sai na hora; pelo caminho de reserva (``busctl``) ela custa
        subprocessos, e sem dono vivo abri-lo custa o Gio — nos dois casos ela
        se refaz num fio e o tique leva a última que havia.
        """
        agora = self._relogio()
        cache = self._adaptadores_em_cache
        if cache is not None and agora - cache[0] < VALIDADE_DOS_ADAPTADORES_S:
            return cache[1]
        if esperar:
            dono = self._dono()
        else:
            vivo = self._dono_sem_abrir()
            if vivo is None or not vivo.atende_o_proprio_pareamento:
                self._refrescar_os_adaptadores()
                return cache[1] if cache is not None else None
            dono = vivo
        lidos = dono.adaptadores()
        if lidos is not None:
            self._adaptadores_em_cache = (agora, tuple(lidos))
        return lidos

    def _refrescar_os_adaptadores(self) -> None:
        with self._tranca:
            if self._refrescando:
                return
            self._refrescando = True

        def rodar() -> None:
            try:
                lidos = self._dono().adaptadores()
                if lidos is not None:
                    self._adaptadores_em_cache = (self._relogio(), tuple(lidos))
            except Exception:
                logger.warning("central_adaptadores_nao_leu", exc_info=True)
            finally:
                with self._tranca:
                    self._refrescando = False

        threading.Thread(target=rodar, name="hefesto-central-adaptadores", daemon=True).start()

    def _planos(
        self, ar: Mapping[str, Any] | None = None, *, esperar: bool = True
    ) -> tuple[Any, frozenset[str] | None]:
        """Os planos por adaptador (o dono é ``plano_de_radio``) e quem varre."""
        from hefesto_dualsense4unix.integrations import plano_de_radio

        adaptadores = self._adaptadores(esperar=esperar)
        busca = self._busca_publicada()
        propria = busca["adaptador"] if busca is not None else None
        varrendo = (
            frozenset(a.endereco for a in adaptadores if a.varrendo and a.endereco != propria)
            if adaptadores is not None
            else None
        )
        planos = plano_de_radio.plano_por_adaptador(
            self._ultimos_controles,
            ar=ar,
            adaptadores=[a.endereco for a in adaptadores or ()],
            **self._sysfs,
        )
        return planos, varrendo

    def propor(
        self,
        controles: Iterable[Mapping[str, Any]] | None = None,
        *,
        ar: Mapping[str, Any] | None = None,
        esperar: bool = True,
    ) -> Any:
        """O «Equilibrar» (R12): UM movimento, ou ``None``."""
        from hefesto_dualsense4unix.integrations import plano_de_radio

        if controles is not None:
            self.conhecer(controles)
        if self.em_curso:
            return None
        planos, varrendo = self._planos(ar, esperar=esperar)
        return plano_de_radio.ordem_de_redistribuicao(planos, varrendo=varrendo)

    def conhecer(self, controles: Iterable[Mapping[str, Any]]) -> None:
        """Guarda o ``state["controllers"]`` de agora — é dele que a D8 e o"""
        self._ultimos_controles = tuple(dict(c) for c in controles)

    def escolher_destino(
        self,
        aparelho: str | None = None,
        *,
        controles: Iterable[Mapping[str, Any]] | None = None,
    ) -> str | None:
        """A D8: onde parear. Mais vaga de ponte; no empate, menos controles; quem"""
        from hefesto_dualsense4unix.integrations import plano_de_radio

        if controles is not None:
            self.conhecer(controles)
        planos, varrendo = self._planos()
        alvo = endereco_de(aparelho) if aparelho else None
        agora = self._onde_esta(_hex12(alvo)) if alvo else ""
        for plano in plano_de_radio.ordem_dos_destinos(planos, varrendo=varrendo, exceto=agora):
            return str(plano.endereco)
        return None


    def comecar_a_mover(self, aparelho: str, destino: str | None = None) -> Movimento:
        """O gesto da tela: começa o mover num fio e volta assim que a trava vier."""
        alvo = endereco_de(aparelho)
        if alvo is None:
            return Movimento(str(aparelho), destino or "", NAO_CHEGOU, PASSO_FIM,
                             MOTIVO_FORA_DO_RADIO)
        self._vencer_os_prazos()
        mudou = self._mudar_o_destino(alvo, destino)
        if mudou is not None:
            return mudou
        escolhido = self._a_escolha_dela(alvo, destino)
        if escolhido is not None:
            return escolhido
        repetido = self._o_mesmo_em_curso(alvo, destino)
        if repetido is not None:
            return repetido
        if self._ocupada():
            return self._recusa_por_outro(alvo, destino)
        return self._no_fio(
            alvo, destino, lambda pronto: self.mover(alvo, destino, _ao_pegar_a_trava=pronto)
        )

    def comecar_a_conectar(self, destino: str | None = None) -> Movimento:
        """O «Conectar» da tela: o mesmo fio de :meth:`comecar_a_mover`, sem alvo."""
        self._vencer_os_prazos()
        mudou = self._mudar_o_destino(CONECTANDO, destino)
        if mudou is not None:
            return mudou
        repetido = self._o_mesmo_em_curso(CONECTANDO, destino)
        if repetido is not None:
            return repetido
        if self._ocupada():
            return self._recusa_por_outro(CONECTANDO, destino)
        return self._no_fio(
            CONECTANDO, destino, lambda pronto: self.conectar(destino, _ao_pegar_a_trava=pronto)
        )

    def _ocupada(self) -> bool:
        """Há movimento em curso, ou a central já fechou — então nada começa."""
        return self._parar.is_set() or self.em_curso

    def _vencer_os_prazos(self) -> None:
        """O «esperando» que já passou do prazo resolve AGORA, antes do pedido."""
        agora = self._relogio()
        for movimento in self.movimentos():
            if (movimento.em_curso and movimento.passo == PASSO_CONFERINDO
                    and agora - movimento.prazo_desde >= self._prazo_do_pendente_s):
                try:
                    self._vigiar_um(movimento)
                except Exception:
                    logger.warning("central_prazo_levantou",
                                   aparelho=mascarar(movimento.aparelho), exc_info=True)

    def _mudar_o_destino(self, chave: str, destino: str | None) -> Movimento | None:
        """O chip de outro adaptador com a busca de pé: a busca vai junto."""
        novo = endereco_de(destino) if destino else None
        if novo is None or self._parar.is_set():
            return None
        with self._tranca:
            atual = next((m for m in self._movimentos.values() if m.em_curso), None)
        if atual is None or atual.passo not in PASSOS_EM_QUE_O_DESTINO_MUDA:
            return None
        if chave not in (CONECTANDO, atual.aparelho):
            return None
        adaptadores = self._adaptadores()
        if adaptadores is None or novo not in {a.endereco for a in adaptadores}:
            return None
        with self._tranca:
            agora = self._movimentos.get(atual.aparelho)
            if (agora is None or not agora.em_curso
                    or agora.passo not in PASSOS_EM_QUE_O_DESTINO_MUDA):
                return None
            self._destino_pedido = None if novo == agora.destino else novo
        logger.info("central_o_destino_segue_a_caixa", aparelho=mascarar(agora.aparelho),
                    de=mascarar(agora.destino), para=mascarar(novo))
        return self._com_o_destino_pedido(agora, novo)

    def _a_escolha_dela(self, alvo: str, destino: str | None) -> Movimento | None:
        """O «Parear» dela na lista do «Conectar»: a escolha, e não outro movimento.

        O aparelho que a janela ainda não viu também se escolhe, para o «Parear de
        Novo» ser UM clique (esquece o par velho, abre a busca e escolhe o mesmo
        aparelho): com a janela aberta no destino dela e o aparelho fora do ar em
        TODO adaptador. O ``Pair`` continua esperando a janela ver o endereço
        escolhido, nenhum outro: o controle de outra pessoa, ou o que já está
        no ar noutro adaptador (esse é um «Mover», e segue recusado), não entra.
        """
        pedido = endereco_de(destino) if destino else None
        if pedido is None or self._parar.is_set():
            return None
        with self._tranca:
            atual = self._movimentos.get(CONECTANDO)
            if (atual is None or not atual.em_curso
                    or atual.passo not in PASSOS_EM_QUE_O_DESTINO_MUDA
                    or atual.destino != pedido):
                return None
            visto = alvo in self._vistos_na_janela
            janela_aberta = atual.passo == PASSO_GESTO and self._busca is not None
        if not visto and (not janela_aberta or self._onde_esta(_hex12(alvo))):
            return None
        with self._tranca:
            if self._movimentos.get(CONECTANDO) is not atual:
                return None
            self._escolha = alvo
        logger.info("central_ela_escolheu", aparelho=mascarar(alvo), adaptador=mascarar(pedido),
                    antes_de_ver=not visto)
        return atual

    def _tomar_o_destino_pedido(
        self, movimento: Movimento, *, recomecar: bool = False
    ) -> Movimento | None:
        """O fio atende o destino que o usuário pediu: o movimento vai para ele."""
        with self._tranca:
            novo, self._destino_pedido = self._destino_pedido, None
            if novo is None or novo == movimento.destino:
                if not recomecar:
                    return None
                novo = movimento.destino
            if self._busca is not None:
                self._busca = {**self._busca, "adaptador": novo}
            feito = replace(
                movimento, destino=novo, passo=PASSO_PREPARANDO,
                origens=tuple(o for o in movimento.origens if o != novo),
                comecou=self._relogio(), quando=time.time(),
            )
            self._movimentos[feito.aparelho] = feito
        self._no_fio_atual.chave = feito.aparelho
        logger.info("central_a_janela_foi_para_o_destino_pedido",
                    aparelho=mascarar(feito.aparelho), adaptador=mascarar(novo))
        return feito

    def _recusa_por_outro(self, chave: str, destino: str | None) -> Movimento:
        """A recusa do um por vez — a mesma forma da trava ocupada, e não guardada."""
        logger.info("central_um_por_vez", aparelho=mascarar(chave), fechada=self._parar.is_set())
        return Movimento(chave, destino or "", NAO_CHEGOU, PASSO_FIM, MOTIVO_OCUPADO)

    def _no_fio(
        self,
        chave: str,
        destino: str | None,
        trabalho: Callable[[Callable[[], None]], Movimento],
    ) -> Movimento:
        pronto = threading.Event()
        caixa: dict[str, Movimento] = {}

        def trabalhar() -> None:
            try:
                caixa["fim"] = trabalho(pronto.set)
            except Exception:
                logger.warning("central_mover_levantou", aparelho=mascarar(chave), exc_info=True)
            finally:
                pronto.set()
            fim = caixa.get("fim")
            if fim is not None and fim.motivo == MOTIVO_OCUPADO:
                return
            self._vigiar_ate_resolver(fim.aparelho if fim is not None else chave)

        fio = threading.Thread(target=trabalhar, name="hefesto-central-mover", daemon=True)
        self._guardar_o_fio(chave, fio)
        fio.start()
        pronto.wait(self._prazo_da_trava_s + 1.0)
        if "fim" in caixa and caixa["fim"].motivo == MOTIVO_OCUPADO:
            return caixa["fim"]
        return self._pela_chave(chave) or Movimento(
            chave, destino or "", ESPERANDO, PASSO_PREPARANDO, comecou=self._relogio()
        )

    def _guardar_o_fio(self, chave: str, fio: threading.Thread) -> None:
        """Guarda o fio para o :meth:`fechar` — sem tirar da lista um que ainda vive."""
        with self._tranca:
            rotulo, n = chave, 1
            while (vivo := self._fios.get(rotulo)) is not None and vivo.is_alive():
                n += 1
                rotulo = f"{chave}#{n}"
            self._fios[rotulo] = fio

    def _pela_chave(self, chave: str) -> Movimento | None:
        with self._tranca:
            return self._movimentos.get(chave)

    def _o_mesmo_em_curso(self, alvo: str, destino: str | None) -> Movimento | None:
        atual = self._pela_chave(alvo)
        if atual is None or not atual.em_curso:
            return None
        pedido = endereco_de(destino) if destino else None
        if pedido is None or pedido == atual.destino:
            return atual
        return None

    def mover(
        self,
        aparelho: str,
        destino: str | None = None,
        *,
        _ao_pegar_a_trava: Callable[[], None] | None = None,
    ) -> Movimento:
        """UM aparelho para UM adaptador — síncrono, e bloqueia pelo gesto do usuário."""
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        alvo = endereco_de(aparelho)
        if alvo is None:
            return Movimento(str(aparelho), destino or "", NAO_CHEGOU, PASSO_FIM,
                             MOTIVO_FORA_DO_RADIO)
        self._vencer_os_prazos()
        mudou = self._mudar_o_destino(alvo, destino)
        if mudou is not None:
            return mudou
        escolhido = self._a_escolha_dela(alvo, destino)
        if escolhido is not None:
            return escolhido
        repetido = self._o_mesmo_em_curso(alvo, destino)
        if repetido is not None:
            return repetido
        if self._ocupada():
            return self._recusa_por_outro(alvo, destino)
        try:
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                repetido = self._o_mesmo_em_curso(alvo, destino)
                if repetido is not None:
                    return repetido
                if self._ocupada():
                    return self._recusa_por_outro(alvo, destino)
                self._comecar(Movimento(alvo, destino or "", ESPERANDO, PASSO_PREPARANDO,
                                        comecou=self._relogio()))
                if _ao_pegar_a_trava is not None:
                    _ao_pegar_a_trava()
                try:
                    self._pagar_as_meias_chaves(self._dono())
                    return self._mover_na_trava(alvo, destino)
                except Exception:
                    return self._falhou(alvo)
        except TravaOcupadaError:
            logger.info("central_mover_trava_ocupada", aparelho=mascarar(alvo))
            return Movimento(alvo, destino or "", NAO_CHEGOU, PASSO_FIM, MOTIVO_OCUPADO)

    def conectar(
        self,
        destino: str | None = None,
        *,
        _ao_pegar_a_trava: Callable[[], None] | None = None,
    ) -> Movimento:
        """O «Conectar» (D8): um aparelho no destino com mais vaga de ponte."""
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        self._vencer_os_prazos()
        mudou = self._mudar_o_destino(CONECTANDO, destino)
        if mudou is not None:
            return mudou
        repetido = self._o_mesmo_em_curso(CONECTANDO, destino)
        if repetido is not None:
            return repetido
        if self._ocupada():
            return self._recusa_por_outro(CONECTANDO, destino)
        try:
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                repetido = self._o_mesmo_em_curso(CONECTANDO, destino)
                if repetido is not None:
                    return repetido
                if self._ocupada():
                    return self._recusa_por_outro(CONECTANDO, destino)
                self._comecar(Movimento(CONECTANDO, destino or "", ESPERANDO, PASSO_PREPARANDO,
                                        comecou=self._relogio()))
                if _ao_pegar_a_trava is not None:
                    _ao_pegar_a_trava()
                try:
                    self._pagar_as_meias_chaves(self._dono())
                    return self._conectar_na_trava(destino)
                except Exception:
                    return self._falhou(CONECTANDO)
        except TravaOcupadaError:
            logger.info("central_conectar_trava_ocupada")
            return Movimento(CONECTANDO, destino or "", NAO_CHEGOU, PASSO_FIM, MOTIVO_OCUPADO)

    def _conectar_na_trava(self, destino: str | None) -> Movimento:
        comeco = self._relogio()
        dono = self._dono()
        adaptadores = dono.adaptadores()
        movimento = Movimento(CONECTANDO, destino or "", ESPERANDO, PASSO_PREPARANDO,
                              comecou=comeco)
        if adaptadores is None:
            return self._acabou(movimento, NAO_CHEGOU, MOTIVO_SEM_BLUEZ)
        pedido = endereco_de(destino) if destino else self.escolher_destino()
        por_endereco = {a.endereco: a for a in adaptadores}
        movimento = replace(movimento, destino=pedido or "")
        if pedido is None or pedido not in por_endereco:
            return self._acabou(movimento, NAO_CHEGOU, MOTIVO_SEM_DESTINO)
        return self._parear_e_conferir(
            self._guardar(movimento), dono, por_endereco[pedido], conectar=True,
            ligados_antes=self._controles_conectados(dono),
        )

    def _mover_na_trava(self, alvo: str, destino: str | None) -> Movimento:
        comeco = self._relogio()
        dono = self._dono()
        foto = _ler(dono, alvo)
        if foto is None:
            return self._acabou(
                Movimento(alvo, destino or "", ESPERANDO, PASSO_PREPARANDO, comecou=comeco),
                NAO_CHEGOU, MOTIVO_SEM_BLUEZ,
            )
        if not foto.do_aparelho:
            return self._acabou(
                Movimento(alvo, destino or "", ESPERANDO, PASSO_PREPARANDO, comecou=comeco),
                NAO_CHEGOU, MOTIVO_FORA_DO_RADIO,
            )
        pedido = endereco_de(destino) if destino else self.escolher_destino(alvo)
        e_controle = self._e_controle(foto, alvo)
        origens = tuple(sorted(
            e for e, a in foto.do_aparelho.items() if e != pedido and a.pareado
        ))
        movimento = Movimento(
            alvo, pedido or "", ESPERANDO, PASSO_PREPARANDO,
            origens=origens, e_controle=e_controle, comecou=comeco,
            **self._quem_e(foto, dono, exceto=pedido or ""),
        )
        if pedido is None or pedido not in foto.adaptadores:
            return self._acabou(movimento, NAO_CHEGOU, MOTIVO_SEM_DESTINO)

        if self._chegou(movimento, dono):
            if not origens:
                return self._guardar(replace(
                    movimento, estado=CHEGOU, passo=PASSO_FIM, motivo=MOTIVO_JA_ESTAVA
                ))
            return self._esquecer_as_origens(movimento, dono)

        if e_controle and self._onde_esta(_hex12(alvo)) == pedido:
            conferindo = self._guardar(replace(movimento, passo=PASSO_CONFERINDO))
            if self._conferir(conferindo, dono):
                return self._esquecer_as_origens(conferindo, dono)
            return self._guardar(replace(conferindo, motivo=MOTIVO_SEM_CONFIRMACAO))

        movimento = self._guardar(movimento)
        self._tirar_o_velho_do_destino(dono, alvo, pedido, foto.do_aparelho.get(pedido))
        movimento = self._desligar_e_esquecer_a_origem(movimento, dono, foto)
        return self._parear_e_conferir(movimento, dono, foto.adaptadores[pedido])

    def _tirar_o_velho_do_destino(
        self,
        dono: bluez_dbus.LeitorDoBluez,
        alvo: str,
        destino: str,
        velho: bluez_dbus.AparelhoDoBluez | None,
    ) -> None:
        """O objeto velho do aparelho no DESTINO sai antes de a janela abrir (R6"""
        if velho is None:
            return
        if velho.pareado:
            self._esquecer(dono, destino, alvo)
        else:
            dono.remover_aparelho(velho.caminho, quem=QUEM)
        self._esperar_sumir(dono, alvo, destino)

    def _quem_e(
        self, foto: _Foto, dono: bluez_dbus.LeitorDoBluez, *, exceto: str = ""
    ) -> dict[str, Any]:
        """A classe, o ``Modalias``, o ``Icon`` e o nome dela, lidos ANTES de a origem sair."""
        pares = sorted(foto.do_aparelho.items(), key=lambda par: par[1].conectado is not True)
        objetos = [o for _e, o in pares]
        classe = next((o.classe for o in objetos if o.classe is not None), None)
        modalias = next((o.modalias for o in objetos if o.modalias), "")
        icone = next((o.icone for o in objetos if o.icone), "")
        dados = (self._nome_dado(dono, o) for e, o in pares if e != exceto)
        nome = next((dado for dado in dados if dado), "")
        if not nome and objetos:
            nome = self._nome_guardado(objetos[0].endereco)
        return {"classe": classe, "modalias": modalias, "icone": icone, "nome": nome}

    @staticmethod
    def _nome_dado(dono: bluez_dbus.LeitorDoBluez, objeto: bluez_dbus.AparelhoDoBluez) -> str:
        """O ``Alias`` DESTE objeto quando é um nome que ela deu; ``""`` quando é"""
        alias = str(objeto.nome or "").strip()
        if not alias:
            return ""
        fabrica = str(dono.propriedade(objeto.caminho, bluez_dbus.APARELHO, "Name") or "").strip()
        if alias == fabrica or alias.replace("-", ":").lower() == objeto.endereco:
            return ""
        return alias

    def _nome_guardado(self, aparelho: str) -> str:
        """O nome que ela deu a este aparelho, pelo endereço; ``""`` sem nome ou sem ler."""
        try:
            return str((self._nomes.ler() or {}).get(aparelho) or "")
        except Exception:
            logger.warning("central_nomes_nao_leu", exc_info=True)
            return ""

    def _desligar_e_esquecer_a_origem(
        self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez, foto: _Foto
    ) -> Movimento:
        """A PARTE DO PRODUTO, antes de pedir o gesto — a R1 dela ao pé da letra."""
        movimento = self._guardar(replace(movimento, passo=PASSO_DESLIGANDO))
        alvo = movimento.aparelho
        for endereco in sorted(foto.do_aparelho):
            if endereco == movimento.destino:
                continue
            caminho = foto.do_aparelho[endereco].caminho
            conectado = bluez_dbus.como_booleano(
                dono.propriedade(caminho, bluez_dbus.APARELHO, "Connected")
            )
            if conectado is True:
                dono.desconectar(caminho, quem=QUEM)
        self._esperar_desligar(movimento, dono)
        for origem in movimento.origens:
            self._esquecer(dono, origem, alvo)
            self._esperar_sumir(dono, alvo, origem)
        return self._guardar(replace(movimento, origens_esquecidas=True))

    def _esperar_desligar(self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez) -> None:
        """Até :data:`ESPERA_DO_DESLIGAR_S` pelo controle fora do ar: o"""
        fim = self._relogio() + ESPERA_DO_DESLIGAR_S
        while True:
            if movimento.e_controle:
                ainda = bool(self._onde_esta(_hex12(movimento.aparelho)))
            else:
                ainda = any(
                    bluez_dbus.como_booleano(
                        dono.propriedade(o.caminho, bluez_dbus.APARELHO, "Connected")
                    ) is True
                    for o in (dono.aparelhos() or ())
                    if o.endereco == movimento.aparelho
                )
            if not ainda or self._relogio() >= fim or self._parar.is_set():
                return
            self._dormir(PASSO_S)

    def _parear_e_conferir(
        self,
        movimento: Movimento,
        dono: bluez_dbus.LeitorDoBluez,
        adaptador: bluez_dbus.AdaptadorDoBluez,
        *,
        conectar: bool = False,
        ligados_antes: frozenset[str] = frozenset(),
    ) -> Movimento:
        """APLICAR e CONFERIR: a janela só no destino, o gesto, o ``Pair``, o"""
        fechou = False
        while True:
            pedido = self._tomar_o_destino_pedido(movimento, recomecar=fechou)
            if pedido is not None:
                ida = self._ir_para(pedido, dono, conectar=conectar)
                if isinstance(ida, Movimento):
                    return ida
                movimento, adaptador = ida
            desfecho = self._uma_janela(movimento, dono, adaptador, conectar=conectar,
                                        ligados_antes=ligados_antes)
            fechou = desfecho is None
            if desfecho is None:
                continue
            if not desfecho.em_curso:
                return desfecho
            movimento = desfecho
            break

        movimento = self._guardar(replace(movimento, passo=PASSO_CONFERINDO))
        if not self._conferir(movimento, dono):
            logger.info("central_mover_sem_confirmacao", aparelho=mascarar(movimento.aparelho))
            pendente = self._guardar(replace(movimento, motivo=MOTIVO_SEM_CONFIRMACAO))
            if self._relogio() - pendente.prazo_desde >= self._prazo_do_pendente_s:
                return self._fechar_sem_chegar(pendente, MOTIVO_PRAZO, dono)
            return pendente
        return self._esquecer_as_origens(movimento, dono)

    def _uma_janela(
        self,
        movimento: Movimento,
        dono: bluez_dbus.LeitorDoBluez,
        adaptador: bluez_dbus.AdaptadorDoBluez,
        *,
        conectar: bool,
        ligados_antes: frozenset[str],
    ) -> Movimento | None:
        """A janela num destino: o gesto, o ``Pair``, o nome dela e o ``Connect``."""
        restaurar = self._preparar_o_adaptador(dono, adaptador)
        with self._tranca:
            self._escolha, self._vistos_na_janela = None, frozenset()
        segundos = self._segundos_da_busca if conectar else self._segundos
        janela = self._abrir_janela(adaptador.endereco, segundos, dono)
        segue = False
        try:
            motivo = janela.abrir_a_janela()
            if motivo:
                logger.warning("central_janela_nao_abriu", motivo=motivo[:200])
                return self._sem_chegar_do_gesto(movimento, MOTIVO_SEM_JANELA)
            movimento = self._guardar(replace(movimento, passo=PASSO_GESTO))
            comeco = self._relogio()
            if conectar:
                desde = time.time()
                with self._tranca:
                    self._busca = {"adaptador": adaptador.endereco, "desde": round(desde, 3),
                                   "ate": round(desde + segundos, 3)}
                    self._janela_da_busca = janela
                    self._aberturas += 1
                    self._ultima_busca = dict(self._busca)
                achado = self._esperar_a_escolha_dela(janela, dono, ligados_antes,
                                                      comeco=comeco, segundos=segundos,
                                                      destino=adaptador.endereco)
                if achado is None:
                    fim = self._sem_gesto(movimento, janela, comeco, segundos)
                    segue = fim is None
                    return fim
                with self._tranca:
                    self._busca = None
                endereco, pelo_antigo = achado
                if pelo_antigo:
                    return self._voltou_pelo_antigo(movimento, endereco, dono)
                pareando = self._quem_chegou(movimento, endereco, dono)
            elif not self._esperar_o_gesto(janela, movimento.aparelho, comeco=comeco):
                return self._sem_gesto(movimento, janela, comeco, segundos)
            else:
                pareando = self._sair_do_gesto(movimento, passo=PASSO_PAREANDO)
            if pareando is None:
                return None
            movimento = pareando
            if conectar and self._pedido_da_janela == movimento.aparelho:
                # o controle conhecido que pediu um par novo: o velho no destino sai antes
                self._refazer_o_par_no_destino(dono, movimento.aparelho, movimento.destino)
            resultado = janela.parear(movimento.aparelho)
            if resultado.estado not in (ESTADO_PAREOU, ESTADO_JA_PAREADO):
                return self._acabou(movimento, NAO_CHEGOU, MOTIVO_NAO_PAREOU)
            # a busca sai do destino ANTES do ``Connect``: no diário de 06/10 o ``Connect`` correu
            # com a varredura de pé no mesmo adaptador e voltou ``Failed`` duas vezes
            janela.fechar()
            agora = self._relogio()
            movimento = self._guardar(replace(
                movimento, pareou_no_destino=True, pareou_em=agora,
                pareou_quando=movimento.quando + (agora - movimento.comecou)))
            with self._tranca:
                self._provocado_em[movimento.aparelho] = self._relogio()
            self._dar_o_nome(dono, movimento)
            self._lembrar_o_alias(dono, movimento.aparelho, movimento.destino)
            self._conectar(dono, movimento.aparelho, movimento.destino)
            return movimento
        finally:
            with self._tranca:
                self._escolha, self._vistos_na_janela = None, frozenset()
                self._janela_da_busca, self._desligar = None, False
                self._pedido_da_janela = ""
                if not segue:
                    self._busca = None
            janela.fechar()
            restaurar()

    def _sem_gesto(self, movimento: Movimento, janela: Janela, comeco: float,
                   segundos: float) -> Movimento | None:
        """A espera do gesto voltou sem o aparelho. Se a janela ainda estava de"""
        if self._desligar:
            return self._sem_chegar_do_gesto(movimento, MOTIVO_DESLIGADA)
        if not (self._parar.is_set() or not janela.aberta
                or self._relogio() >= comeco + segundos):
            return None
        return self._sem_chegar_do_gesto(movimento, MOTIVO_SEM_GESTO)

    def _sem_chegar_do_gesto(self, movimento: Movimento, motivo: str) -> Movimento | None:
        """O «não chegou» de uma janela sem gesto — ou ``None``, com o pedido de"""
        feito = self._sair_do_gesto(movimento, estado=NAO_CHEGOU, passo=PASSO_FIM, motivo=motivo)
        if feito is not None:
            self._no_diario_do_nao_chegou(feito)
        return feito

    def _ir_para(
        self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez, *, conectar: bool
    ) -> Movimento | tuple[Movimento, bluez_dbus.AdaptadorDoBluez]:
        """O destino que o usuário pediu (:meth:`_tomar_o_destino_pedido`), antes da janela de
        lá."""
        novo = movimento.destino
        adaptador = next((a for a in dono.adaptadores() or () if a.endereco == novo), None)
        if adaptador is None:
            return self._acabou(movimento, NAO_CHEGOU, MOTIVO_SEM_DESTINO)
        if conectar:
            return movimento, adaptador
        foto = _ler(dono, movimento.aparelho)
        if foto is not None:
            self._tirar_o_velho_do_destino(dono, movimento.aparelho, novo,
                                           foto.do_aparelho.get(novo))
        return movimento, adaptador

    def _quem_chegou(
        self, movimento: Movimento, achado: str, dono: bluez_dbus.LeitorDoBluez
    ) -> Movimento | None:
        """O «Conectar» ganha o endereço e vai para o ``Pair``: sai a chave"""
        foto = _ler(dono, achado)
        origens = tuple(sorted(
            e for e, a in (foto.do_aparelho.items() if foto is not None else ())
            if e != movimento.destino and a.pareado
        ))
        quem = self._quem_e(foto, dono, exceto=movimento.destino) if foto is not None else {}
        e_controle = self._e_controle(foto, achado) if foto is not None else True
        return self._sair_do_gesto(movimento, aparelho=achado, origens=origens,
                                   e_controle=e_controle, passo=PASSO_PAREANDO, **quem)

    def _voltou_pelo_antigo(
        self, movimento: Movimento, achado: str, dono: bluez_dbus.LeitorDoBluez
    ) -> Movimento:
        """O «Conectar» que acaba porque o controle voltou pelo pareamento antigo."""
        onde = self._onde_esta(_hex12(achado))
        foto = _ler(dono, achado)
        quem = self._quem_e(foto, dono) if foto is not None else {}
        with self._tranca:
            self._movimentos.pop(CONECTANDO, None)
        feito = self._guardar(replace(
            movimento, aparelho=achado, destino=onde or movimento.destino, e_controle=True,
            estado=CHEGOU, passo=PASSO_FIM, motivo=MOTIVO_PELO_PAREAMENTO_ANTIGO, **quem,
        ))
        logger.info("central_conectar_pelo_pareamento_antigo", aparelho=mascarar(achado),
                    adaptador=mascarar(feito.destino))
        self._no_diario(
            VOLTOU_PELO_PAREAMENTO_ANTIGO,
            "ela ligou o controle e ele voltou para o adaptador que tinha a chave dele",
            feito,
            depois={"adaptador": feito.destino},
        )
        return feito

    def _dar_o_nome(self, dono: bluez_dbus.LeitorDoBluez, movimento: Movimento) -> None:
        """O nome dela vai junto: o ``Alias`` do objeto NOVO no destino."""
        if not movimento.nome:
            return
        no = dono.caminho_do_aparelho(movimento.aparelho, adaptador=movimento.destino)
        if no is None:
            return
        dono.escrever_propriedade(no, bluez_dbus.APARELHO, "Alias", "s", movimento.nome,
                                  quem=QUEM)


    def _e_controle(self, foto: _Foto, alvo: str) -> bool:
        """Pergunta à CLASSE do aparelho, nunca ao nome. Sem classe, ao ``Icon``
        que o próprio BlueZ deriva (da ``Appearance``, no de baixo consumo); sem
        os dois, ao daemon — o controle que ele publica é controle.

        FATO SUBSTITUÍDO (o conferente da A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01,
        25/09/2026): sem classe, a pergunta ia ao kernel — *«o aparelho que tem
        hidraw no rádio é controle»*. Todo aparelho HID pelo rádio tem hidraw, e
        o ``HID_PHYS`` dele é o adaptador: o teclado de baixo consumo, que não
        publica ``Class`` (o «BT5.0 Keyboard» da lista dela, passos b7 e c3),
        virava controle. A tela o vestia de DualSense com «Segure PS + Create»,
        e o CONFERIR esperava um movimento que teclado não tem até o prazo — com
        a origem já esquecida e a central ocupada por dois minutos.
        """
        pelo_bluez = _o_bluez_diz_controle(foto.do_aparelho.values())
        if pelo_bluez is not None:
            return pelo_bluez
        alvo12 = _hex12(alvo)
        return any(_hex12(str(c.get("uniq") or "")) == alvo12 for c in self._ultimos_controles)

    def _o_daemon_mede(self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez) -> bool:
        """O daemon mede o movimento DESTE controle? Só o do DualSense (Sony
        ``054C``, produtos ``0CE6`` e ``0DF2``), que é o controle que ele lê.

        O ``Modalias`` é o lido antes de a origem sair ou, no «Conectar» (que
        acha o controle ANTES de parear, quando o BlueZ ainda não tem o
        ``Modalias`` dele), o do objeto no destino. Sem ``Modalias`` nenhum é
        «não sei», e «não sei» não afrouxa o CONFERIR: vale o movimento.
        """
        modalias = movimento.modalias
        if not modalias:
            no = dono.caminho_do_aparelho(movimento.aparelho, adaptador=movimento.destino)
            if no is not None:
                modalias = str(dono.propriedade(no, bluez_dbus.APARELHO, "Modalias") or "")
        if not modalias:
            return True
        return _MODALIAS_QUE_O_DAEMON_MEDE.search(modalias) is not None

    def _preparar_o_adaptador(
        self, dono: bluez_dbus.LeitorDoBluez, adaptador: bluez_dbus.AdaptadorDoBluez
    ) -> Callable[[], None]:
        """``Powered`` se preciso e ``Pairable`` SÓ durante a janela."""
        caminho = adaptador.caminho
        if adaptador.ligado is False:
            dono.escrever_propriedade(caminho, bluez_dbus.ADAPTADOR, "Powered", "b", True,
                                      quem=QUEM)
        antes = bluez_dbus.como_booleano(
            dono.propriedade(caminho, bluez_dbus.ADAPTADOR, "Pairable")
        )
        if antes is True:
            return lambda: None
        escrita = dono.escrever_propriedade(caminho, bluez_dbus.ADAPTADOR, "Pairable", "b",
                                            True, quem=QUEM)
        if not escrita.feita or antes is None:
            return lambda: None

        def devolver() -> None:
            dono.escrever_propriedade(caminho, bluez_dbus.ADAPTADOR, "Pairable", "b", False,
                                      quem=QUEM)

        return devolver

    def _esperar_o_gesto(self, janela: Janela, alvo: str, *, comeco: float) -> bool:
        """Espera o aparelho aparecer na janela — ela segurando PS + Create."""
        fim = comeco + self._segundos
        while True:
            if any(getattr(c, "endereco", "") == alvo for c in janela.candidatos()):
                return True
            if (self._parar.is_set() or self._relogio() >= fim or not janela.aberta
                    or self._destino_pedido is not None):
                return False
            self._dormir(PASSO_S)

    def _esperar_a_escolha_dela(
        self,
        janela: Janela,
        dono: bluez_dbus.LeitorDoBluez,
        ligados_antes: frozenset[str],
        *,
        comeco: float,
        segundos: float,
        destino: str = "",
    ) -> tuple[str, bool] | None:
        """O «Conectar»: ``(endereço, pelo_antigo)`` do aparelho do usuário, ou ``None``.

        Com a janela aberta pelo usuário, o controle CONHECIDO que pede para parear no destino é
        a escolha dele (O-CONTROLE-QUE-PEDE-PARA-PAREAR-…-01): ele já disse o que quer ao apertar
        PS + Create e abrir a janela, e outro clique seria custo para quem joga.
        """
        fim = comeco + segundos
        while True:
            vistos = frozenset(str(getattr(c, "endereco", "") or "")
                               for c in janela.candidatos()) - {""}
            with self._tranca:
                self._vistos_na_janela = vistos
                escolha = self._escolha
            if escolha is not None and escolha in vistos:
                return escolha, False
            pede = self._quem_pede_aqui(dono, destino) if destino and escolha is None else ""
            if pede:
                logger.info("central_conectar_quem_pede_para_parear", aparelho=mascarar(pede),
                            adaptador=mascarar(destino))
                with self._tranca:
                    self._pedido_da_janela = pede
                return pede, False
            voltou = self._quem_voltou_sozinho(dono, ligados_antes)
            if voltou:
                return voltou, True
            if (self._parar.is_set() or self._desligar or self._relogio() >= fim
                    or not janela.aberta or self._destino_pedido is not None):
                return None
            self._dormir(PASSO_S)

    def _controles_conectados(self, dono: bluez_dbus.LeitorDoBluez) -> frozenset[str]:
        """Os controles (pela classe) que o BlueZ diz conectados agora, em qualquer adaptador."""
        return frozenset(
            o.endereco for o in (dono.aparelhos() or ())
            if o.conectado is True and e_controle(o.classe)
        )

    def _quem_voltou_sozinho(
        self, dono: bluez_dbus.LeitorDoBluez, ligados_antes: frozenset[str]
    ) -> str:
        """O controle que se conectou depois de a janela abrir — com o kernel confirmando."""
        for endereco in sorted(self._controles_conectados(dono) - ligados_antes):
            if self._onde_esta(_hex12(endereco)):
                return endereco
        return ""

    def _conectar(self, dono: bluez_dbus.LeitorDoBluez, alvo: str, destino: str) -> None:
        """``Connect`` no destino se o BlueZ ainda não o diz conectado."""
        no = dono.caminho_do_aparelho(alvo, adaptador=destino)
        if no is None:
            return
        conectado = bluez_dbus.como_booleano(dono.propriedade(no, bluez_dbus.APARELHO, "Connected"))
        if conectado is not True:
            dono.conectar(no, quem=QUEM)

    def _provocar_a_chave_nova(
        self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez
    ) -> None:
        """A chave que ESTE movimento fez no destino e que ainda não conectou: ``Trusted`` e
        ``Connect`` de novo, a cada :data:`REPROVOCAR_S`, até o prazo. Quem está no ar noutro
        adaptador não é chamado: o ``Connect`` dele não é desta chave."""
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        if not movimento.pareou_no_destino or not movimento.destino:
            return
        agora = self._relogio()
        with self._tranca:
            if agora - self._provocado_em.get(movimento.aparelho, 0.0) < REPROVOCAR_S:
                return
            self._provocado_em[movimento.aparelho] = agora
        if self._onde_esta(_hex12(movimento.aparelho)):
            return
        with contextlib.suppress(TravaOcupadaError), bluez_dbus.na_trava(
            QUEM, prazo_s=self._prazo_da_trava_s
        ):
            if self.movimento_de(movimento.aparelho) != movimento:
                return
            no = dono.caminho_do_aparelho(movimento.aparelho, adaptador=movimento.destino)
            if no is None or bluez_dbus.como_booleano(
                    dono.propriedade(no, bluez_dbus.APARELHO, "Paired")) is not True:
                return
            if bluez_dbus.como_booleano(
                    dono.propriedade(no, bluez_dbus.APARELHO, "Trusted")) is not True:
                dono.confiar(no, quem=QUEM)
            # o ``Connect`` espera no máximo o que sobra do prazo: o veredito não passa do
            # instante em que a tela diz «Não conectou»
            resta = self._prazo_do_pendente_s - (self._relogio() - movimento.prazo_desde)
            if resta < 1.0 or bluez_dbus.como_booleano(
                    dono.propriedade(no, bluez_dbus.APARELHO, "Connected")) is True:
                return
            logger.info("central_chama_a_chave_nova", aparelho=mascarar(movimento.aparelho),
                        adaptador=mascarar(movimento.destino))
            dono.conectar(no, espera=min(bluez_dbus.ESPERA_DO_CONNECT_S, resta), quem=QUEM)

    def _chegou(self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez) -> bool:
        """A pergunta do CONFERIR, UMA vez. Controle: ``HID_PHYS`` no destino E o"""
        if movimento.e_controle:
            uniq = _hex12(movimento.aparelho)
            if self._onde_esta(uniq) != movimento.destino:
                return False
            if self._movimento is None:
                return True
            hz = self._movimento(uniq)
            if hz is not None:
                return hz > 0
            return not self._o_daemon_mede(movimento, dono)
        no = dono.caminho_do_aparelho(movimento.aparelho, adaptador=movimento.destino)
        if no is None:
            return False
        return bluez_dbus.como_booleano(
            dono.propriedade(no, bluez_dbus.APARELHO, "Connected")
        ) is True

    def _conferir(self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez) -> bool:
        """Até :data:`CONFERIR_S` perguntando — e nunca além do"""
        fim = min(self._relogio() + self._conferir_s,
                  movimento.prazo_desde + self._prazo_do_pendente_s)
        while True:
            if self._chegou(movimento, dono):
                return True
            if self._parar.is_set() or self._relogio() >= fim:
                return False
            self._dormir(PASSO_S)

    def _esquecer(self, dono: bluez_dbus.LeitorDoBluez, adaptador: str, aparelho: str) -> bool:
        """Esquece UM aparelho em UM adaptador: ``RemoveDevice`` do dono mais o"""
        no = dono.caminho_do_aparelho(aparelho, adaptador=adaptador)
        if no is not None:
            dono.remover_aparelho(no, quem=QUEM)
            self._lembrar_o_alias(dono, aparelho, adaptador, caminho=no, sumiu=True)
        fez, motivo = self._esquecer_na_ponte(adaptador, aparelho)
        if not fez:
            logger.warning(
                "central_esquecer_sem_lapide",
                adaptador=mascarar(adaptador),
                aparelho=mascarar(aparelho),
                motivo=motivo[:200],
            )
        return fez

    def _esperar_sumir(self, dono: bluez_dbus.LeitorDoBluez, aparelho: str, adaptador: str) -> None:
        fim = self._relogio() + ESPERA_DO_SUMICO_S
        while dono.caminho_do_aparelho(aparelho, adaptador=adaptador) is not None:
            if self._relogio() >= fim:
                return
            self._dormir(0.05)

    def _esquecer_as_origens(
        self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez
    ) -> Movimento:
        """O fim do mover: a conexão de cada ORIGEM sai, uma por uma, com lápide."""
        if not movimento.origens and not movimento.pareou_no_destino:
            return self._guardar(replace(
                movimento, estado=CHEGOU, passo=PASSO_FIM, motivo=MOTIVO_JA_ESTAVA
            ))
        movimento = self._guardar(replace(movimento, passo=PASSO_ESQUECENDO))
        sem_lapide = [] if movimento.origens_esquecidas else [
            origem for origem in movimento.origens
            if not self._esquecer(dono, origem, movimento.aparelho)
        ]
        feito = self._guardar(replace(movimento, estado=CHEGOU, passo=PASSO_FIM, motivo=""))
        self._no_diario(
            MOVEU_O_APARELHO,
            "ela moveu com PS + Create, e o HID_PHYS confirmou",
            feito,
            depois={"adaptador": feito.destino, "sem_lapide": sem_lapide or None},
        )
        return feito

    def _acabou(self, movimento: Movimento, estado: str, motivo: str) -> Movimento:
        """O fim do movimento. O «não chegou» que chega aqui depois do ``Pair``"""
        feito = self._guardar(replace(movimento, estado=estado, passo=PASSO_FIM, motivo=motivo))
        if estado == NAO_CHEGOU:
            self._dever_a_meia_chave(feito)
            self._no_diario_do_nao_chegou(feito)
        return feito

    def _dever_a_meia_chave(self, movimento: Movimento) -> None:
        """A chave que ESTE movimento pode ter deixado no destino entra na fila"""
        if movimento.pareou_no_destino and movimento.destino:
            with self._tranca:
                self._meias_chaves.add((movimento.destino, movimento.aparelho))

    def _pagar_as_meias_chaves(self, dono: bluez_dbus.LeitorDoBluez) -> tuple[tuple[str, str], ...]:
        """COM A TRAVA NA MÃO: cada meia chave devida sai — se ainda é meia chave."""
        with self._tranca:
            devidas = sorted(self._meias_chaves)
        pagas: list[tuple[str, str]] = []
        for adaptador, aparelho in devidas:
            try:
                saiu = self._esquecer_se_meia_chave(dono, adaptador, aparelho)
            except Exception:
                logger.warning("central_meia_chave_levantou", aparelho=mascarar(aparelho),
                               adaptador=mascarar(adaptador), exc_info=True)
                continue
            if saiu is None:
                continue
            if saiu:
                pagas.append((adaptador, aparelho))
            with self._tranca:
                self._meias_chaves.discard((adaptador, aparelho))
        if pagas:
            self._no_diario_das_meias_chaves(pagas)
        return tuple(pagas)

    def tirar_as_meias_chaves(self) -> tuple[tuple[str, str], ...]:
        """UMA volta da faxina sobre as meias chaves devidas: pega a trava e as tira."""
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        with self._tranca:
            devendo = bool(self._meias_chaves)
        if not devendo or self._ocupada():
            return ()
        try:
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                if self._ocupada():
                    return ()
                return self._pagar_as_meias_chaves(self._dono())
        except TravaOcupadaError:
            logger.info("central_meias_chaves_trava_ocupada")
        except Exception:
            logger.warning("central_meias_chaves_levantou", exc_info=True)
        return ()

    def _no_diario_das_meias_chaves(self, pagas: Sequence[tuple[str, str]]) -> None:
        try:
            from hefesto_dualsense4unix.integrations import diario_do_radio

            for adaptador, aparelho in pagas:
                diario_do_radio.registrar(
                    QUEM, ESQUECEU_A_MEIA_CHAVE,
                    "o pareamento não chegou, e a chave que ficou no destino saiu quando "
                    "a central teve a trava",
                    depois={"adaptador": adaptador}, controle=aparelho, adaptador=adaptador,
                )
        except Exception:
            logger.warning("central_diario_nao_gravou", exc_info=True)

    def _no_diario_do_nao_chegou(self, feito: Movimento, *, meia_chave: bool = False) -> None:
        self._no_diario(O_APARELHO_NAO_CHEGOU, feito.motivo, feito,
                        depois={"pareou_no_destino": feito.pareou_no_destino,
                                "origens_esquecidas": feito.origens_esquecidas,
                                "meia_chave_esquecida": meia_chave or None})

    def _fechar_sem_chegar(
        self, movimento: Movimento, motivo: str, dono: bluez_dbus.LeitorDoBluez
    ) -> Movimento:
        """O «não chegou» da vigia e do prazo — com a MEIA CHAVE saindo antes."""
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        try:
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                if self._pela_chave(movimento.aparelho) != movimento:
                    return self._pela_chave(movimento.aparelho) or movimento
                esquecida = self._esquecer_a_meia_chave(movimento, dono)
                movimento = self._esquecer_as_origens_mortas(movimento, dono)
                return self._acabou_se_ainda(movimento, motivo, meia_chave=esquecida is True,
                                             devida=esquecida is None)
        except TravaOcupadaError:
            logger.warning("central_meia_chave_sem_trava", aparelho=mascarar(movimento.aparelho))
            return self._acabou_se_ainda(movimento, motivo, meia_chave=False, devida=True)

    def _esquecer_as_origens_mortas(
        self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez
    ) -> Movimento:
        """O «Conectar» que PAREOU no destino e não conferiu: o ``Pair`` trocou o"""
        if (not movimento.pareou_no_destino or movimento.origens_esquecidas
                or not movimento.origens or self._onde_esta(_hex12(movimento.aparelho))):
            return movimento
        for origem in movimento.origens:
            self._esquecer(dono, origem, movimento.aparelho)
        return self._guardar(replace(movimento, origens_esquecidas=True))

    def _acabou_se_ainda(
        self, movimento: Movimento, motivo: str, *, meia_chave: bool, devida: bool = False
    ) -> Movimento:
        """«Não chegou» só se o movimento guardado ainda é ESTE — conferido e"""
        feito = replace(movimento, estado=NAO_CHEGOU, passo=PASSO_FIM, motivo=motivo)
        with self._tranca:
            atual = self._movimentos.get(movimento.aparelho)
            if atual != movimento:
                return atual or movimento
            self._movimentos[movimento.aparelho] = feito
            self._mudou_o_movimento(feito)
        if devida:
            self._dever_a_meia_chave(feito)
        self._no_diario_do_nao_chegou(feito, meia_chave=meia_chave)
        return feito

    def _esquecer_a_meia_chave(
        self, movimento: Movimento, dono: bluez_dbus.LeitorDoBluez
    ) -> bool | None:
        """A chave que ESTE movimento criou no destino e que nunca conectou sai"""
        if not movimento.pareou_no_destino or not movimento.destino:
            return False
        return self._esquecer_se_meia_chave(dono, movimento.destino, movimento.aparelho)

    def _esquecer_se_meia_chave(
        self, dono: bluez_dbus.LeitorDoBluez, adaptador: str, aparelho: str
    ) -> bool | None:
        """A meia chave de ``aparelho`` em ``adaptador`` sai — se ainda é meia chave."""
        adaptadores = dono.adaptadores()
        if adaptadores is None or adaptador not in {a.endereco for a in adaptadores}:
            return None
        no = dono.caminho_do_aparelho(aparelho, adaptador=adaptador)
        if no is None:
            return None if dono.caminhos() is None else False
        pareado = bluez_dbus.como_booleano(dono.propriedade(no, bluez_dbus.APARELHO, "Paired"))
        conectado = bluez_dbus.como_booleano(
            dono.propriedade(no, bluez_dbus.APARELHO, "Connected"))
        if pareado is None:
            return None
        if pareado is not True or conectado is True:
            return False
        if self._onde_esta(_hex12(aparelho)) == adaptador:
            return False
        logger.info("central_esquece_a_meia_chave", aparelho=mascarar(aparelho),
                    adaptador=mascarar(adaptador))
        self._esquecer(dono, adaptador, aparelho)
        self._esperar_sumir(dono, aparelho, adaptador)
        if (dono.caminho_do_aparelho(aparelho, adaptador=adaptador) is not None
                or dono.caminhos() is None):
            logger.warning("central_meia_chave_nao_sumiu", aparelho=mascarar(aparelho),
                           adaptador=mascarar(adaptador))
            return None
        return True

    def _no_diario(
        self, o_que: str, por_que: str, movimento: Movimento, *, depois: Mapping[str, Any]
    ) -> None:
        """Uma linha no diário comum. Nunca levanta: o gesto já aconteceu."""
        try:
            from hefesto_dualsense4unix.integrations import diario_do_radio

            diario_do_radio.registrar(
                QUEM,
                o_que,
                por_que,
                antes={"adaptadores": list(movimento.origens)},
                depois=dict(depois),
                controle=movimento.aparelho,
                adaptador=movimento.destino or None,
            )
        except Exception:
            logger.warning("central_diario_nao_gravou", exc_info=True)


    def vigiar(self) -> None:
        """UMA volta sobre os movimentos aplicados e ainda não confirmados."""
        pendentes = [
            m for m in self.movimentos()
            if m.em_curso and m.passo == PASSO_CONFERINDO
        ]
        for movimento in pendentes:
            try:
                self._vigiar_um(movimento)
            except Exception:
                logger.warning(
                    "central_vigia_levantou", aparelho=mascarar(movimento.aparelho), exc_info=True
                )
                if (
                    self._relogio() - movimento.prazo_desde >= self._prazo_do_pendente_s
                    and self.movimento_de(movimento.aparelho) == movimento
                ):
                    self._acabou(movimento, NAO_CHEGOU, MOTIVO_PRAZO)

    def _vigiar_um(self, movimento: Movimento) -> None:
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        dono = self._dono()
        if self._chegou(movimento, dono):
            with contextlib.suppress(TravaOcupadaError), bluez_dbus.na_trava(
                QUEM, prazo_s=self._prazo_da_trava_s
            ):
                if self.movimento_de(movimento.aparelho) == movimento:
                    self._esquecer_as_origens(movimento, dono)
            return
        if movimento.e_controle and movimento.origens:
            onde = self._onde_esta(_hex12(movimento.aparelho))
            if onde and onde in movimento.origens:
                self._fechar_sem_chegar(movimento, MOTIVO_VOLTOU, dono)
                return
        if self._relogio() - movimento.prazo_desde >= self._prazo_do_pendente_s:
            self._fechar_sem_chegar(movimento, MOTIVO_PRAZO, dono)
            return
        self._provocar_a_chave_nova(movimento, dono)

    def _vigiar_ate_resolver(self, alvo: str) -> None:
        """O fio do gesto, depois do mover: vigia o «esperando» até resolver."""
        while not self._parar.is_set():
            atual = self.movimento_de(alvo)
            if atual is None or not atual.em_curso or atual.passo != PASSO_CONFERINDO:
                return
            self._dormir(1.0)
            self.vigiar()


    def sobras(self, dono: bluez_dbus.LeitorDoBluez) -> tuple[tuple[str, str, str], ...] | None:
        """``(adaptador que sai, controle, adaptador em que ele está)``, em ordem."""
        chaves = self._chaves_dobradas(dono)
        if chaves is None:
            return None
        achadas: list[tuple[str, str, str]] = []
        for aparelho, onde_tem in sorted(chaves.items()):
            agora = self._onde_esta(_hex12(aparelho))
            if agora:
                if agora in onde_tem:
                    achadas.extend(
                        (sai, aparelho, agora) for sai in sorted(onde_tem) if sai != agora)
                continue
            lembrada = self._a_lembranca_que_vale(aparelho, onde_tem, dono)
            if lembrada is None:
                continue
            onde, eram = lembrada
            achadas.extend(
                (sai, aparelho, onde) for sai in sorted(onde_tem)
                if sai != onde and (sai, _entrada(dono, onde_tem[sai])) in eram)
        return tuple(achadas)

    def _chaves_dobradas(
        self, dono: bluez_dbus.LeitorDoBluez
    ) -> dict[str, dict[str, bluez_dbus.AparelhoDoBluez]] | None:
        """``{controle: {adaptador: objeto}}`` de quem tem CHAVE (``Paired``) em dois"""
        adaptadores = dono.adaptadores()
        aparelhos = dono.aparelhos()
        if adaptadores is None or aparelhos is None:
            return None
        por_caminho = {a.caminho: a.endereco for a in adaptadores}
        chaves: dict[str, dict[str, bluez_dbus.AparelhoDoBluez]] = {}
        for objeto in aparelhos:
            if objeto.pareado is not True or objeto.adaptador not in por_caminho:
                continue
            chaves.setdefault(objeto.endereco, {})[por_caminho[objeto.adaptador]] = objeto
        return {aparelho: onde_tem for aparelho, onde_tem in chaves.items()
                if len(onde_tem) >= 2 and any(e_controle(o.classe) for o in onde_tem.values())}

    def _lembrar_onde_estao(self) -> None:
        """Onde cada controle com a chave dobrada está no ar AGORA, e as chaves"""
        try:
            dono = self._dono_sem_abrir()
            if dono is None or not dono.atende_o_proprio_pareamento:
                return
            chaves = self._chaves_dobradas(dono)
            if chaves is None:
                return
            for aparelho, onde_tem in chaves.items():
                agora = self._onde_esta(_hex12(aparelho))
                if not agora:
                    continue
                with self._tranca:
                    if any(m.em_curso and m.aparelho == aparelho
                           for m in self._movimentos.values()):
                        continue
                    if agora in onde_tem:
                        self._lembrancas[aparelho] = (agora, frozenset(
                            (onde, _entrada(dono, objeto)) for onde, objeto in onde_tem.items()))
                    else:
                        self._lembrancas.pop(aparelho, None)
        except Exception:
            logger.warning("central_lembranca_levantou", exc_info=True)

    def _a_lembranca_que_vale(
        self,
        aparelho: str,
        onde_tem: Mapping[str, bluez_dbus.AparelhoDoBluez],
        dono: bluez_dbus.LeitorDoBluez,
    ) -> tuple[str, frozenset[tuple[str, int]]] | None:
        """A lembrança de onde ``aparelho`` estava no ar — se ela ainda vale."""
        with self._tranca:
            lembrada = self._lembrancas.get(aparelho)
        if lembrada is None:
            return None
        onde, eram = lembrada
        agora = {(ad, _entrada(dono, objeto)) for ad, objeto in onde_tem.items()}
        if onde not in onde_tem or not agora <= eram:
            with self._tranca:
                if self._lembrancas.get(aparelho) == lembrada:
                    del self._lembrancas[aparelho]
            return None
        return lembrada

    def esquecer_as_sobras(self, por_que: str = NA_VOLTA_DA_FAXINA) -> tuple[str, str] | None:
        """Esquece UMA sobra e devolve ``(adaptador, controle)``."""
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        if self._ocupada():
            return None
        try:
            dono = self._dono()
            if not self.sobras(dono):
                return None
            with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                if self._ocupada():
                    return None
                achadas = self.sobras(dono)
                if not achadas:
                    return None
                sai, aparelho, fica = achadas[0]
                no = dono.caminho_do_aparelho(aparelho, adaptador=sai)
                fez, motivo = self._esquecer_na_ponte(sai, aparelho)
                if not fez:
                    self._nao_limpou(sai, aparelho, fica, motivo)
                    return None
                resto = dono.caminho_do_aparelho(aparelho, adaptador=sai)
                if resto is not None:
                    dono.remover_aparelho(resto, quem=QUEM)
                self._lembrar_o_alias(dono, aparelho, sai, caminho=no, sumiu=True)
                self._esperar_sumir(dono, aparelho, sai)
        except TravaOcupadaError:
            logger.info("central_faxina_trava_ocupada")
            return None
        except Exception:
            logger.warning("central_faxina_levantou", exc_info=True)
            return None
        with self._tranca:
            self._sem_lapide_dito.discard((sai, aparelho))
        logger.info(
            "central_esqueceu_a_sobra",
            aparelho=mascarar(aparelho),
            adaptador=mascarar(sai),
            fica=mascarar(fica),
            por_que=por_que,
        )
        try:
            from hefesto_dualsense4unix.integrations import diario_do_radio

            diario_do_radio.registrar(
                QUEM,
                ESQUECEU_A_SOBRA,
                por_que,
                antes={"adaptadores": sorted({sai, fica})},
                depois={"adaptador": fica},
                controle=aparelho,
                adaptador=sai,
            )
        except Exception:
            logger.warning("central_diario_nao_gravou", exc_info=True)
        return sai, aparelho

    def _nao_limpou(self, sai: str, aparelho: str, fica: str, motivo: str) -> None:
        """A ponte não enterrou a sobra: nada sai, e o diário diz UMA vez por par."""
        logger.warning("central_sobra_sem_lapide", aparelho=mascarar(aparelho),
                       adaptador=mascarar(sai), motivo=str(motivo)[:200])
        with self._tranca:
            if (sai, aparelho) in self._sem_lapide_dito:
                return
            self._sem_lapide_dito.add((sai, aparelho))
        try:
            from hefesto_dualsense4unix.integrations import diario_do_radio

            diario_do_radio.registrar(
                QUEM, NAO_LIMPOU_SEM_LAPIDE, str(motivo)[:200] or "a ponte não respondeu",
                antes={"adaptadores": sorted({sai, fica})}, depois={"adaptador": fica},
                controle=aparelho, adaptador=sai,
            )
        except Exception:
            logger.warning("central_diario_nao_gravou", exc_info=True)

    def limpar(self, por_que: str = NA_VOLTA_DA_FAXINA) -> tuple[tuple[str, str], ...]:
        """UMA volta da limpeza: as sobras, um par por vez, até não haver"""
        feitas: list[tuple[str, str]] = []
        for _ in range(PARES_POR_LIMPEZA):
            feito = self.esquecer_as_sobras(por_que)
            if feito is None:
                break
            feitas.append(feito)
        self._tirar_os_acabados()
        return tuple(feitas)

    def _no_ar(self, aparelho: str, dono: bluez_dbus.LeitorDoBluez | None) -> bool:
        """``aparelho`` está no ar por algum transporte: o ``HID_PHYS`` no rádio,"""
        u = _hex12(aparelho)
        if self._onde_esta(u):
            return True
        if any(_hex12(str(c.get("uniq") or "")) == u and c.get("connected", True) is not False
               for c in self._ultimos_controles):
            return True
        if dono is not None:
            return any(o.conectado is True and _hex12(o.endereco) == u
                       for o in dono.aparelhos() or ())
        return False

    def _tirar_os_acabados(self) -> tuple[Movimento, ...]:
        """Os movimentos acabados que não dizem mais nada saem da publicação: o"""
        try:
            dono = self._dono_sem_abrir()
            agora = time.time()
            with self._tranca:
                acabados = [m for m in self._movimentos.values() if not m.em_curso]
            sair = [m for m in acabados
                    if agora - m.quando > LEMBRA_O_NAO_CONECTOU_S
                    or (m.estado == NAO_CHEGOU and m.aparelho and self._no_ar(m.aparelho, dono))]
            with self._tranca:
                for m in sair:
                    if self._movimentos.get(m.aparelho) == m:
                        del self._movimentos[m.aparelho]
            return tuple(sair)
        except Exception:
            logger.warning("central_acabados_levantou", exc_info=True)
            return ()

    def dispensar(self, aparelho: str) -> Movimento | None:
        """O X do «Não Conectou»: o movimento ACABADO de ``aparelho`` sai da"""
        alvo = endereco_de(aparelho)
        if alvo is None:
            return None
        vencido = self.movimento_de(alvo)
        if (vencido is not None and vencido.em_curso and vencido.passo == PASSO_CONFERINDO
                and self._relogio() - vencido.prazo_desde >= self._prazo_do_pendente_s):
            # a tela já diz «Não conectou» (o mesmo prazo) e a vigia ainda não falou: o clique
            # dela é o veredito, e o fecho é o da vigia (a meia chave sai antes)
            self._vigiar_um(vencido)
        with self._tranca:
            atual = self._movimentos.get(alvo)
            if atual is None or atual.em_curso:
                return None
            del self._movimentos[alvo]
        return atual

    def gravar_as_lapides_de_fora(self) -> tuple[tuple[str, str], ...]:
        """A LÁPIDE DE QUEM SAIU POR FORA (cura 5 da ESQUECER-E-LIMPAR-AS-CONEXOES-01)."""
        from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

        with self._tranca_da_limpeza:
            pendentes = list(self._saidas_de_fora)
        if not pendentes:
            return ()
        agora = self._relogio()
        dono = self._dono_sem_abrir()
        resolvidos: list[tuple[str, str, float, str]] = []
        enterrados: list[tuple[str, str]] = []
        for pendente in pendentes:
            adaptador, aparelho, quando, dono_de_entao = pendente
            if agora - quando < ESPERA_DA_LAPIDE_DE_FORA_S or dono is None:
                continue
            try:
                adaptadores = dono.adaptadores()
                if (dono.dono_do_bluez() != dono_de_entao or adaptadores is None
                        or adaptador not in {a.endereco for a in adaptadores}):
                    resolvidos.append(pendente)
                    continue
                with bluez_dbus.na_trava(QUEM, prazo_s=self._prazo_da_trava_s):
                    if dono.caminho_do_aparelho(aparelho, adaptador=adaptador) is not None:
                        resolvidos.append(pendente)
                        continue
                    fez, motivo = self._esquecer_na_ponte(adaptador, aparelho)
            except TravaOcupadaError:
                continue
            except Exception:
                logger.warning("central_lapide_de_fora_levantou", exc_info=True)
                continue
            if not fez:
                logger.warning("central_lapide_de_fora_sem_ponte", aparelho=mascarar(aparelho),
                               adaptador=mascarar(adaptador), motivo=str(motivo)[:200])
                continue
            resolvidos.append(pendente)
            enterrados.append((adaptador, aparelho))
            try:
                from hefesto_dualsense4unix.integrations import diario_do_radio

                diario_do_radio.registrar(
                    QUEM, ENTERROU_O_QUE_SAIU_POR_FORA,
                    "o pareamento saiu do BlueZ por fora do Hefesto, com o serviço vivo",
                    depois={"adaptador": adaptador}, controle=aparelho, adaptador=adaptador,
                )
            except Exception:
                logger.warning("central_diario_nao_gravou", exc_info=True)
        with self._tranca_da_limpeza:
            self._saidas_de_fora = [p for p in self._saidas_de_fora if p not in resolvidos]
        return tuple(enterrados)

    def comecar_a_faxina(
        self, intervalo_s: float = INTERVALO_DA_FAXINA_S, *, passo_s: float | None = None
    ) -> None:
        """Sobe o fio da faxina — uma volta a cada ``intervalo_s``. Idempotente."""
        with self._tranca:
            vivo = self._fios.get(_FIO_DA_FAXINA)
            if vivo is not None and vivo.is_alive():
                return
            fio = threading.Thread(
                target=self._faxinar_sempre,
                args=(float(intervalo_s), passo_s),
                name="hefesto-central-faxina",
                daemon=True,
            )
            self._fios[_FIO_DA_FAXINA] = fio
        fio.start()

    def _faxinar_sempre(self, intervalo_s: float, passo_s: float | None = None) -> None:
        passo = min(intervalo_s, INTERVALO_DOS_NOMES_S) if passo_s is None else float(passo_s)
        desde_a_faxina = 0.0
        while not self._parar.is_set():
            pedida = self._limpeza_pedida.wait(passo)
            if self._parar.is_set():
                return
            if pedida:
                with self._tranca_da_limpeza:
                    por_que, self._por_que_limpar = self._por_que_limpar, ""
                    self._limpeza_pedida.clear()
                self.limpar(por_que or NA_VOLTA_DA_FAXINA)
                continue
            desde_a_faxina += passo
            faxina = desde_a_faxina >= intervalo_s
            vivo = self._o_dono_e_a_foto_viva()
            if vivo:
                self._lembrar_onde_estao()
            self.gravar_as_lapides_de_fora()
            if faxina or vivo:
                self.tirar_as_meias_chaves()
                self.cuidar_dos_nomes()
            if faxina:
                desde_a_faxina = 0.0
                self.limpar(NA_VOLTA_DA_FAXINA)

    def _o_dono_e_a_foto_viva(self) -> bool:
        """O dono de agora lê da foto em memória (o Gio), e não de subprocessos."""
        visto = self._dono_sem_abrir()
        return visto is not None and visto.atende_o_proprio_pareamento


    def _lembrar_o_alias(
        self,
        dono: bluez_dbus.LeitorDoBluez,
        aparelho: str,
        adaptador: str,
        *,
        caminho: str | None = None,
        sumiu: bool = False,
    ) -> None:
        """A central tirou ou recriou o objeto: a volta dos nomes fica sabendo."""
        no = caminho or dono.caminho_do_aparelho(aparelho, adaptador=adaptador)
        if no is None:
            return
        with self._tranca:
            if sumiu:
                self._alias_vistos.pop(no, None)
            else:
                self._alias_vistos[no] = str(
                    dono.propriedade(no, bluez_dbus.APARELHO, "Alias") or "").strip()
            self._geracao_dos_nomes += 1

    def cuidar_dos_nomes(self) -> tuple[tuple[str, str], ...] | None:
        """UMA volta do NOME DO USUÁRIO: guarda o que ela deu, e o devolve a todo objeto."""
        if self._ocupada():
            return None
        try:
            with self._tranca:
                geracao = self._geracao_dos_nomes
                vistos_antes = dict(self._alias_vistos)
            dono = self._dono()
            aparelhos = dono.aparelhos()
            guardados = self._nomes.ler()
            if aparelhos is None or guardados is None:
                return None
            vistos: dict[str, str] = {}
            feitos: list[tuple[str, str]] = []
            for endereco, objetos in _controles_pelo_endereco(aparelhos).items():
                dados = {o.caminho: self._nome_dado(dono, o) for o in objetos}
                guardado = str(guardados.get(endereco) or "")
                vale, apagou = _o_nome_que_vale(objetos, dados, vistos_antes, guardado)
                gravou = vale == guardado or self._nomes.gravar(endereco, vale or None)
                if not gravou:
                    vistos.update({o.caminho: vistos_antes[o.caminho]
                                   for o in objetos if o.caminho in vistos_antes})
                    continue
                if vale != guardado:
                    logger.info("central_guardou_o_nome", aparelho=mascarar(endereco),
                                apagou=apagou)
                    feitos.append((endereco, vale))
                for objeto in objetos:
                    alias = _alias_de(objeto)
                    vistos[objeto.caminho] = alias
                    if objeto.pareado is not True:
                        continue
                    if vale and alias != vale:
                        novo = vale
                    elif apagou and dados[objeto.caminho] == guardado:
                        novo = ""
                    else:
                        continue
                    escrita = dono.escrever_propriedade(
                        objeto.caminho, bluez_dbus.APARELHO, "Alias", "s", novo, quem=QUEM)
                    if escrita.feita:
                        logger.info("central_devolveu_o_nome", aparelho=mascarar(endereco),
                                    fabrica=not novo)
                        feitos.append((endereco, novo))
            with self._tranca:
                if geracao == self._geracao_dos_nomes:
                    self._alias_vistos = vistos
            return tuple(feitos)
        except Exception:
            logger.warning("central_nomes_levantou", exc_info=True)
            return None


__all__ = [
    "CHEGOU",
    "CONECTANDO",
    "CONFERIR_S",
    "ESPERANDO",
    "ESPERA_DO_DESLIGAR_S",
    "ESQUECEU_A_MEIA_CHAVE",
    "ESQUECEU_A_SOBRA",
    "ESTADOS",
    "ICONE_DE_CONTROLE",
    "INTERVALO_DA_FAXINA_S",
    "INTERVALO_DOS_NOMES_S",
    "MOTIVO_FALHOU",
    "MOTIVO_FORA_DO_RADIO",
    "MOTIVO_JA_ESTAVA",
    "MOTIVO_NAO_PAREOU",
    "MOTIVO_OCUPADO",
    "MOTIVO_PELO_PAREAMENTO_ANTIGO",
    "MOTIVO_PRAZO",
    "MOTIVO_SEM_BLUEZ",
    "MOTIVO_SEM_CONFIRMACAO",
    "MOTIVO_SEM_DESTINO",
    "MOTIVO_SEM_GESTO",
    "MOTIVO_SEM_JANELA",
    "MOTIVO_VOLTOU",
    "MOVEU_O_APARELHO",
    "NAO_CHEGOU",
    "O_APARELHO_NAO_CHEGOU",
    "PASSOS_EM_QUE_O_DESTINO_MUDA",
    "PASSO_CONFERINDO",
    "PASSO_DESLIGANDO",
    "PASSO_ESQUECENDO",
    "PASSO_FIM",
    "PASSO_GESTO",
    "PASSO_PAREANDO",
    "PASSO_PREPARANDO",
    "PRAZO_DA_TRAVA_DO_GESTO_S",
    "PRAZO_DO_PENDENTE_S",
    "QUEM",
    "VOLTOU_PELO_PAREAMENTO_ANTIGO",
    "CentralDoRadio",
    "GuardaDosNomes",
    "Movimento",
    "NomesNaMaquina",
    "PedidoDePareamento",
    "endereco_de",
    "esquecer_pela_ponte",
    "pedidos_de_pareamento",
]
