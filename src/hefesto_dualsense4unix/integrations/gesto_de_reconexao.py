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
fora."* <!-- noqa-acento: citação literal -->

E O DIA MEDIU POR QUÊ. A mesa dela caiu num estado que o botão PS **não**
resolve: o BlueZ dizendo ``Connected: true`` para quatro controles com o kernel
sem HID nenhum deles — elo de pé, sessão de entrada morta. Para o rádio já
estava tudo certo, então apertar PS não fazia nada; o que destrava é derrubar o
elo morto. :func:`reconectar` faz os dois passos e diz qual deles bastou.

**O ELO SÓ É MORTO QUANDO O KERNEL NÃO TEM O HID DELE (02/10/2026).** Às 19h07
de 01/10, com o serviço mudo e a lista de jogadores vazia, o «Reconectar
controles» derrubou dois DualSense que o kernel tinha registrado de volta um
minuto antes: o «morto» era «fora da lista de quem chama», e a lista era a do
serviço que não respondia. Desde a O-RECONECTAR-SO-DERRUBA-O-ELO-MORTO-01,
:func:`reconectar` pergunta ao dono do ``HID_UNIQ``
(``conexao_zumbi.quem_tem_hid``) antes de derrubar: com o HID vivo, o controle
está no ar e nada se mexe; sem leitura do kernel, na dúvida, ele fica.

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

from hefesto_dualsense4unix.core import formas_do_endereco as _formas
from hefesto_dualsense4unix.integrations import bluez_dbus, conexao_zumbi
from hefesto_dualsense4unix.integrations.bluez_dbus import RADIO_DE_VERDADE_NA_SUITE
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

QUEM = "reconectar"

ESTADO_DESCONECTOU = "desconectou"
ESTADO_JA_ESTAVA_FORA = "ja_estava_fora"  # (noqa-acento): chave de máquina
ESTADO_SEM_ALVO = "sem_alvo"
ESTADO_NAO_DEU = "nao_deu"  # (noqa-acento): chave de máquina
ESTADO_VOLTOU = "voltou"
#: O elo morto caiu, e o resto é dela: um DualSense dormindo não atende
ESTADO_SO_O_PS = "so_o_ps"  # (noqa-acento): chave de máquina
ESTADO_JA_NO_AR = "ja_no_ar"  # (noqa-acento): chave de máquina

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
FRASE_JA_NO_AR = "Este controle já está conectado."
FRASE_SEM_O_KERNEL = (
    "Não consegui ver se o sistema enxerga este controle, então ele ficou como estava."
)

Executar = Callable[[Sequence[str]], "str | None"]


@dataclass(frozen=True)
class Resultado:
    """O que aconteceu com UM controle. Imutável: é uma foto, não estado."""

    estado: str
    porque: str
    endereco: str = ""

    @property
    def caiu(self) -> bool:
        """O controle está fora do rádio AGORA?"""
        return self.estado in (ESTADO_DESCONECTOU, ESTADO_JA_ESTAVA_FORA)


def mascarar(mac: str) -> str:
    """Zera os octetos 4 e 5 — a máscara desta casa, e há portão que a cobra."""
    return _formas.mascarar_endereco(mac) or _formas.mascarar(mac)


def _normalizar(mac: str) -> str | None:
    """``aa:bb:cc:11:22:33`` → ``AA_BB_CC_11_22_33``, ou ``None`` se não é MAC."""
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
    """O caminho D-Bus deste endereço, em QUALQUER adaptador. ``None`` se não há."""
    return _caminho(_leitor(executar), mac)


def esta_conectado(mac: str, *, executar: Executar | None = None) -> bool | None:
    """O BlueZ diz que este endereço está conectado AGORA? ``None`` = não sei."""
    leitor = _leitor(executar)
    caminho = _caminho(leitor, mac)
    return None if caminho is None else _conectado(leitor, caminho)


def tem_hid_no_kernel(mac: str) -> bool | None:
    """O kernel tem um ``hidraw`` com este endereço? ``None`` = não deu para ler."""
    com_hid = conexao_zumbi.quem_tem_hid()
    if com_hid is None:
        return None
    alvo = _normalizar(mac)
    limpo = conexao_zumbi.mac_limpo(alvo.replace("_", ":")) if alvo else None
    return limpo is not None and limpo in com_hid


def desconectar(mac: str, *, executar: Executar | None = None) -> Resultado:
    """Derruba este controle do rádio. Best-effort, e nunca levanta."""
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


def _modalias_dos_dualsense() -> tuple[str, ...]:
    """Os pares dos DualSense FÍSICOS, escritos como o `Modalias` do BlueZ os entrega.

    Os números SÃO os do broker (`broker/hidraw_broker.PHYS_VENDOR` e
    `PHYS_PRODUCTS`), lidos de lá, e a pergunta é por PROPRIEDADE, nunca pelo
    `Alias`: o nome é editável e a mesa dela tem quatro aparelhos com o mesmo,
    que é a doença que esta casa já pagou casando nó de som por rótulo.

    **O EDGE ENTROU EM 25/09/2026** (O-CONTROLE-NUNCA-VISTO-TEM-NOME-E-COR-01).
    Aqui estava o par do DualSense digitado (`v054Cp0CE6`), e o «Reconectar
    controles» nunca chamava de volta um DualSense Edge pelo rádio — o controle
    que o daemon adota, numera e acende como qualquer outro. O `0DF2` do nosso
    vpad não é aparelho do BlueZ, então aqui ele não confunde ninguém.
    """
    from hefesto_dualsense4unix.broker.hidraw_broker import PHYS_PRODUCTS, PHYS_VENDOR

    return tuple(f"v{PHYS_VENDOR:04X}p{pid:04X}" for pid in sorted(PHYS_PRODUCTS))


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
        if not isinstance(modalias, str) or not any(
            par.upper() in modalias.upper() for par in _modalias_dos_dualsense()
        ):
            continue
        achados.append((mac, _conectado(leitor, caminho)))
    return achados


def reconectar(mac: str, *, executar: Executar | None = None) -> Resultado:
    """Devolve este controle ao rádio: derruba o elo morto e chama de volta."""
    from hefesto_dualsense4unix.integrations.diario_do_radio import TravaOcupadaError

    mascara = mascarar(mac)
    caminho = caminho_do_controle(mac, executar=executar)
    if caminho is None:
        logger.info("reconexao_sem_alvo_no_bluez", endereco=mascara)
        return Resultado(ESTADO_SEM_ALVO, FRASE_SEM_ALVO, mascara)

    leitor = _leitor(executar)
    try:
        with bluez_dbus.na_trava(QUEM):
            com_hid = tem_hid_no_kernel(mac)
            if com_hid:
                logger.info("reconexao_elo_vivo_preservado", endereco=mascara)
                return Resultado(ESTADO_JA_NO_AR, FRASE_JA_NO_AR, mascara)
            if esta_conectado(mac, executar=executar) is not False:
                if com_hid is None:
                    logger.info("reconexao_sem_o_kernel_elo_preservado", endereco=mascara)
                    return Resultado(ESTADO_NAO_DEU, FRASE_SEM_O_KERNEL, mascara)
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
    "ESTADO_JA_NO_AR",
    "ESTADO_NAO_DEU",
    "ESTADO_SEM_ALVO",
    "ESTADO_SO_O_PS",
    "ESTADO_VOLTOU",
    "FRASE_DESCONECTOU",
    "FRASE_JA_ESTAVA_FORA",
    "FRASE_JA_NO_AR",
    "FRASE_NAO_DEU",
    "FRASE_SEM_ALVO",
    "FRASE_SEM_O_KERNEL",
    "QUEM",
    "RADIO_DE_VERDADE_NA_SUITE",
    "Resultado",
    "caminho_do_controle",
    "desconectar",
    "dualsenses_do_radio",
    "esta_conectado",
    "mascarar",
    "tem_hid_no_kernel",
]
