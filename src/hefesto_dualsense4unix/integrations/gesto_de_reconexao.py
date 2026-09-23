"""O gesto que derruba UM controle do rádio — ``Disconnect`` pelo D-Bus do BlueZ.

Por que este arquivo existe: a cura foi MEDIDA em 12/08/2026 e nunca foi ligada.
O ``Disconnect`` do BlueZ tinha ZERO chamadores em ``src/`` até hoje, e ele é a
metade automatizável da única receita conhecida para uma barra que nasceu
travada — ``Disconnect`` pelo produto, botão PS pela pessoa. É o padrão que esta
casa chama de *a casa sabe e o produto não faz*.

O QUE ELE FAZ, E O QUE NÃO FAZ
==============================
Faz UMA coisa: pede ao ``bluetoothd`` que derrube a conexão de um endereço, e
diz o que aconteceu numa frase em português. Não reconecta, não sonda o
aparelho, não escreve em LED nenhum.

**A REGRA DE NÃO RECONECTAR FOI REVOGADA POR ELA — 22/09/2026.** Aqui estava
escrito: *"Não reconectar é decisão dela, e é o contrato deste módulo. O botão
PS é dela; `reconectar` não existe aqui de propósito."* A palavra dela, no dia:
*"pera o reconectar deveria sim tocar no radio. não faz sentido ele ficar de
fora."* <!-- noqa-acento: citação literal dela -->

E O DIA MEDIU POR QUÊ. A mesa dela caiu num estado que o botão PS **não**
resolve: o BlueZ dizendo ``Connected: true`` para quatro controles com o kernel
sem HID nenhum deles — elo de pé, sessão de entrada morta. Para o rádio já
estava tudo certo, então apertar PS não fazia nada; o que destrava é derrubar o
elo morto. :func:`reconectar` faz os dois passos e diz qual deles bastou.

**O ``Connect`` NÃO ACORDA CONTROLE DORMINDO, e isso foi medido no mesmo dia:**
depois do ``Disconnect`` os três responderam ``br-connection-create-socket``,
porque um DualSense desligado não atende chamado. Por isso o estado
:data:`ESTADO_SO_O_PS` existe: ele é a metade que continua sendo dela.

ENDEREÇAMENTO POR MAC, NUNCA POR ``hciN``
==========================================
O caminho de um dispositivo no BlueZ carrega o adaptador
(``/org/bluez/hci2/dev_D4_2F_4B_00_00_D8``), e o índice ``hciN`` **inverte entre
boots**: os três adaptadores desta mesa são o MESMO modelo atrás do mesmo hub, e
qual deles vira ``hci0`` é sorteio de enumeração. Por isso nada aqui recebe
``hciN``: :func:`caminho_do_controle` VARRE a árvore e casa pelo MAC, que é o
que não muda. É a mesma doença que o ``bt_active_mode.sh:86`` tem com o seu
``head -1``, e a que o caminho da luz não tem (LUZ-CEGA-01, achado negativo).

SEM SUDO, E ISSO É MEDIDO
=========================
``Disconnect`` em ``org.bluez.Device1`` responde para o uid 1000 nesta mesa
(medido em 22/08/2026, com o ``busctl introspect`` respondendo e a propriedade
``Connected`` legível). Este gesto **não** passa pelo helper privilegiado do
install — pedir senha para algo que não precisa dela ensina a pessoa a digitar
senha sem motivo.

PELO DONO DO BLUEZ, E NA TRAVA DO RÁDIO (BLUEZ-UM-DONO-01, 23/09/2026)
========================================================================
Ler e escrever passam por ``integrations/bluez_dbus.py``: a guarda contra a
suíte, que nasceu AQUI em 22/09, subiu para a borda de lá e vale para toda
escrita do produto. O ``Disconnect`` e o ``Connect`` de :func:`reconectar` vão
JUNTOS dentro da trava comum do rádio: sem ela, o watchdog podia dar o
``Connect`` dele no meio do nosso gesto.

TRÊS DISCIPLINAS, HERDADAS DE ``integrations/exame_da_mesa.py``
================================================================
* **Nunca levanta.** Toda saída é um :class:`Resultado`; barramento fora, erro
  do BlueZ, trava ocupada e teto de tempo colapsam em :data:`ESTADO_NAO_DEU`,
  que é uma resposta e não uma exceção;
* **"não deu" nunca é "desconectou"** — o quarto estado é obrigatório, e é o
  remédio do ELO-MUDO-01 aplicado aqui: ausência de notícia não pode ser lida
  como sucesso;
* **Nenhum endereço inteiro sai numa frase.** :func:`mascarar` zera os octetos 4
  e 5 antes de o texto chegar à tela, porque o retrato das abas versiona PNG do
  que aparece nela e há portão que reprova MAC real em arquivo do repositório.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.integrations.bluez_dbus import RADIO_DE_VERDADE_NA_SUITE
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Como este gesto assina na trava e no diário comuns do rádio.
QUEM = "reconectar"

#: Os quatro estados. Nenhum deles é acento — são chaves de máquina.
ESTADO_DESCONECTOU = "desconectou"
ESTADO_JA_ESTAVA_FORA = "ja_estava_fora"  # (noqa-acento): chave de máquina
ESTADO_SEM_ALVO = "sem_alvo"
ESTADO_NAO_DEU = "nao_deu"  # (noqa-acento): chave de máquina
#: O controle voltou pelo rádio, sem a mão dela.
ESTADO_VOLTOU = "voltou"
#: O elo morto caiu, e o resto é dela: um DualSense dormindo não atende
#: `Connect`. É o desfecho mais comum quando o controle ficou parado.
ESTADO_SO_O_PS = "so_o_ps"  # (noqa-acento): chave de máquina

#: As frases, uma por estado. Elas vão para a tela como estão — e nenhuma delas
#: diz "a barra vai acender": este módulo derruba uma conexão, e o que a luz faz
#: depois é coisa que ninguém aqui consegue ler (`multi_intensity` é a memória
#: da última escrita, nunca a lâmpada).
FRASE_DESCONECTOU = "Desconectei o controle. Aperte PS nele para ele voltar."
FRASE_JA_ESTAVA_FORA = (
    "Este controle já não estava conectado. Aperte PS nele para ele voltar."
)
FRASE_SEM_ALVO = (
    "Não achei este controle no Bluetooth do sistema. Se ele está no cabo, este "
    "gesto não se aplica."
)
FRASE_VOLTOU = "Este controle voltou pelo rádio."
FRASE_SO_O_PS = (
    "Derrubei o elo morto deste controle — o rádio dizia que ele estava aqui "
    "e o sistema não o via. Aperte PS nele para ele voltar."
)
FRASE_NAO_DEU = (
    "Não consegui falar com o Bluetooth do sistema, então não sei se o controle "
    "caiu. Ele continua pareado."
)

#: O que roda um `busctl`: recebe os argumentos e devolve a saída, ou ``None``
#: quando não deu. É por este tipo que o módulo inteiro fica exercitável sem
#: `bluetoothd`, sem adaptador e sem controle na mesa.
Executar = Callable[[Sequence[str]], "str | None"]


@dataclass(frozen=True)
class Resultado:
    """O que aconteceu com UM controle. Imutável: é uma foto, não estado."""

    #: Um dos quatro ``ESTADO_*``.
    estado: str
    #: A frase que a tela mostra, em português e escrita para ela.
    porque: str
    #: O endereço, JÁ MASCARADO. Nunca o de doze hexa inteiro.
    endereco: str = ""

    @property
    def caiu(self) -> bool:
        """O controle está fora do rádio AGORA?

        ``ja_estava_fora`` conta: para quem espera o botão PS, os dois estados
        pedem exatamente o mesmo gesto. O que NÃO conta é
        :data:`ESTADO_NAO_DEU` — e essa é a linha inteira deste módulo: um
        ``False`` aqui significa "não sei", e quem chama não pode fingir que
        significa "não caiu".
        """
        return self.estado in (ESTADO_DESCONECTOU, ESTADO_JA_ESTAVA_FORA)


def mascarar(mac: str) -> str:
    """Zera os octetos 4 e 5 — a máscara desta casa, e há portão que a cobra.

    Aceita as duas formas que circulam no produto: ``aa:bb:cc:11:22:33`` (o
    ``uniq`` do daemon) e ``aabbcc112233`` (a chave do ``maquina.json``). A
    saída sai sempre com dois-pontos, que é como a pessoa lê um MAC.
    """
    limpo = mac.replace(":", "").replace("-", "").strip().lower()
    if len(limpo) != 12 or any(c not in "0123456789abcdef" for c in limpo):
        return mac
    octetos = [limpo[i : i + 2] for i in range(0, 12, 2)]
    octetos[3] = octetos[4] = "00"
    return ":".join(octetos)


def _normalizar(mac: str) -> str | None:
    """``aa:bb:cc:11:22:33`` → ``AA_BB_CC_11_22_33``, ou ``None`` se não é MAC.

    É a forma que o BlueZ usa no caminho do objeto. Recusar em vez de tentar é
    deliberado: um endereço forjado (o que começa em ``02``, do nosso DKMS) não
    tem dispositivo no bus, e mandar buscá-lo gastaria um subprocesso para
    receber a mesma resposta.
    """
    limpo = mac.replace(":", "").replace("-", "").strip().lower()
    if len(limpo) != 12 or any(c not in "0123456789abcdef" for c in limpo):
        return None
    return "_".join(limpo[i : i + 2] for i in range(0, 12, 2)).upper()


def _leitor(executar: Executar | None) -> bluez_dbus.LeitorDoBluez:
    """O dono do BlueZ, ou um leitor sobre o dublê de quem injetou ``executar``."""
    return bluez_dbus.dono() if executar is None else bluez_dbus.pelo_executor(executar)


def _caminho(leitor: bluez_dbus.LeitorDoBluez, mac: str) -> str | None:
    alvo = _normalizar(mac)
    if alvo is None:
        return None
    return leitor.caminho_do_aparelho(alvo.replace("_", ":").lower())


def _conectado(leitor: bluez_dbus.LeitorDoBluez, caminho: str) -> bool | None:
    return bluez_dbus.como_booleano(
        leitor.propriedade(caminho, bluez_dbus.APARELHO, "Connected")
    )


def caminho_do_controle(mac: str, *, executar: Executar | None = None) -> str | None:
    """O caminho D-Bus deste endereço, em QUALQUER adaptador. ``None`` se não há.

    Casa pelo endereço, que é o que não muda. Não recebe ``hciN`` e não o
    deduz: numa mesa de três adaptadores o índice é sorteio, e o mesmo controle
    já apareceu sob ``hci1`` e sob ``hci2`` no mesmo dia.
    """
    return _caminho(_leitor(executar), mac)


def esta_conectado(mac: str, *, executar: Executar | None = None) -> bool | None:
    """O BlueZ diz que este endereço está conectado AGORA? ``None`` = não sei.

    Três respostas e não duas, pelo mesmo motivo do resto do arquivo: sem
    barramento, com o ``bluetoothd`` fora ou com o dispositivo ausente da
    árvore, a resposta honesta é ``None``. Quem espera o botão PS tem de tratar
    ``None`` como "continua esperando", nunca como "voltou".
    """
    leitor = _leitor(executar)
    caminho = _caminho(leitor, mac)
    return None if caminho is None else _conectado(leitor, caminho)


def desconectar(mac: str, *, executar: Executar | None = None) -> Resultado:
    """Derruba este controle do rádio. Best-effort, e nunca levanta.

    A ordem das perguntas é a que gasta menos: acha o caminho, confere se ainda
    está conectado, e só então chama. Um ``Disconnect`` num dispositivo já fora
    responde ``0`` e não faz nada — mas dizer *"já não estava conectado"* é o
    que impede a pessoa de esperar um controle que nunca vai cair.
    """
    mascara = mascarar(mac)
    caminho = caminho_do_controle(mac, executar=executar)
    if caminho is None:
        logger.info("reconexao_sem_alvo_no_bluez", endereco=mascara)
        return Resultado(ESTADO_SEM_ALVO, FRASE_SEM_ALVO, mascara)

    leitor = _leitor(executar)
    if esta_conectado(mac, executar=executar) is False:
        logger.info("reconexao_ja_estava_fora", endereco=mascara)
        return Resultado(ESTADO_JA_ESTAVA_FORA, FRASE_JA_ESTAVA_FORA, mascara)

    if not leitor.desconectar(caminho, quem=QUEM).feita:
        logger.warning("reconexao_disconnect_nao_deu", endereco=mascara)
        return Resultado(ESTADO_NAO_DEU, FRASE_NAO_DEU, mascara)
    logger.info("reconexao_disconnect_pedido", endereco=mascara)
    return Resultado(ESTADO_DESCONECTOU, FRASE_DESCONECTOU, mascara)


#: O par do DualSense FÍSICO, escrito como o `Modalias` do BlueZ o entrega.
#: Os números são os mesmos do broker (`broker/hidraw_broker.py:97`,
#: `PHYS_PRODUCT`), e a pergunta é por PROPRIEDADE, nunca pelo `Alias`: o nome
#: é editável e a mesa dela tem quatro aparelhos com o mesmo, que é a doença
#: que esta casa já pagou casando nó de som por rótulo.
_MODALIAS_DO_DUALSENSE = "v054Cp0CE6"


def dualsenses_do_radio(
    *, executar: Executar | None = None
) -> list[tuple[str, bool | None]]:
    """Os DualSense que o BlueZ conhece: ``[(mac, conectado)]``, pela árvore.

    ``conectado`` é a resposta de três valores de :func:`esta_conectado` —
    ``None`` quer dizer *"não deu para perguntar"*, e quem chama não pode lê-lo
    como *"está fora"*.

    A LISTA É DA ÁRVORE INTEIRA, de todos os adaptadores: o índice ``hciN``
    inverte entre boots, e é a mesma razão de :func:`caminho_do_controle` não
    receber adaptador nenhum.
    """
    leitor = _leitor(executar)
    achados: list[tuple[str, bool | None]] = []
    for caminho in leitor.caminhos() or ():
        mac = bluez_dbus.endereco_do_aparelho(caminho)
        if mac is None:
            continue
        modalias = leitor.propriedade(caminho, bluez_dbus.APARELHO, "Modalias")
        if not isinstance(modalias, str) or _MODALIAS_DO_DUALSENSE not in modalias:
            continue
        achados.append((mac, _conectado(leitor, caminho)))
    return achados


def reconectar(mac: str, *, executar: Executar | None = None) -> Resultado:
    """Devolve este controle ao rádio: derruba o elo morto e chama de volta.

    OS DOIS PASSOS, e o primeiro é o que o botão PS não consegue fazer:

    1. ``Disconnect`` quando o BlueZ ainda diz ``Connected`` — é o elo morto do
       estado que ela viu, com o rádio de pé e o kernel sem HID. Sem derrubá-lo,
       o PS dela não tem efeito: para o rádio o controle já está aqui;
    2. ``Connect``, com o teto maior do dono (``ESPERA_DO_CONNECT_S``: o
       ``Connect`` CHAMA o aparelho). Funciona com o controle ACORDADO; com ele
       dormindo, o BlueZ recusa e o desfecho é :data:`ESTADO_SO_O_PS` — a
       metade que continua sendo dela.

    Os dois passos vão na MESMA trava do rádio: ninguém entra entre eles.
    Nunca levanta, como todo o resto do módulo, e não usa ``sudo``.
    """
    from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

    mascara = mascarar(mac)
    caminho = caminho_do_controle(mac, executar=executar)
    if caminho is None:
        logger.info("reconexao_sem_alvo_no_bluez", endereco=mascara)
        return Resultado(ESTADO_SEM_ALVO, FRASE_SEM_ALVO, mascara)

    leitor = _leitor(executar)
    try:
        with bluez_dbus.na_trava(QUEM):
            if esta_conectado(mac, executar=executar) is not False:
                # O elo morto sai primeiro. Um `Connect` por cima dele responde
                # "já está conectado" e não levanta sessão de entrada nenhuma —
                # medido na mesa dela, quatro vezes, com o kernel sem HID.
                if not leitor.desconectar(caminho, quem=QUEM).feita:
                    logger.warning("reconexao_disconnect_nao_deu", endereco=mascara)
                    return Resultado(ESTADO_NAO_DEU, FRASE_NAO_DEU, mascara)
                logger.info("reconexao_elo_morto_derrubado", endereco=mascara)
            voltou = leitor.conectar(caminho, quem=QUEM)
    except TravaOcupadaError:
        logger.warning("reconexao_trava_ocupada", endereco=mascara)
        return Resultado(ESTADO_NAO_DEU, FRASE_NAO_DEU, mascara)
    if not voltou.feita:
        logger.info("reconexao_connect_recusado", endereco=mascara)
        return Resultado(ESTADO_SO_O_PS, FRASE_SO_O_PS, mascara)
    logger.info("reconexao_voltou_pelo_radio", endereco=mascara)
    return Resultado(ESTADO_VOLTOU, FRASE_VOLTOU, mascara)


__all__ = [
    "ESTADO_DESCONECTOU",
    "ESTADO_JA_ESTAVA_FORA",
    "ESTADO_NAO_DEU",
    "ESTADO_SEM_ALVO",
    "ESTADO_SO_O_PS",
    "ESTADO_VOLTOU",
    "FRASE_DESCONECTOU",
    "FRASE_JA_ESTAVA_FORA",
    "FRASE_NAO_DEU",
    "FRASE_SEM_ALVO",
    "QUEM",
    "RADIO_DE_VERDADE_NA_SUITE",
    "Resultado",
    "caminho_do_controle",
    "desconectar",
    "dualsenses_do_radio",
    "esta_conectado",
    "mascarar",
]
