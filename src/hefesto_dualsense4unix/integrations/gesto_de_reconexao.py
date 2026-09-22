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

TRÊS DISCIPLINAS, HERDADAS DE ``integrations/exame_da_mesa.py``
================================================================
* **Nunca levanta.** Toda saída é um :class:`Resultado`; ausência do ``busctl``,
  erro do bus e teto de tempo colapsam em :data:`ESTADO_NAO_DEU`, que é uma
  resposta e não uma exceção;
* **"não deu" nunca é "desconectou"** — o quarto estado é obrigatório, e é o
  remédio do ELO-MUDO-01 aplicado aqui: ausência de notícia não pode ser lida
  como sucesso;
* **Nenhum endereço inteiro sai numa frase.** :func:`mascarar` zera os octetos 4
  e 5 antes de o texto chegar à tela, porque o retrato das abas versiona PNG do
  que aparece nela e há portão que reprova MAC real em arquivo do repositório.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Teto de espera de cada `busctl`, em segundos. O mesmo número de
#: `integrations/exame_da_mesa.py:92` (`ESPERA_DO_BUSCTL_S`) e de
#: `integrations/apelido_do_dongle.py`:
#: um `busctl` pendurado seguraria o único worker da ponte da janela, e a aba
#: inteira pareceria travada.
ESPERA_DO_BUSCTL_S = 5.0

#: O serviço e a interface, escritos uma vez.
SERVICO = "org.bluez"
INTERFACE_DO_DISPOSITIVO = "org.bluez.Device1"

#: O caminho de UM dispositivo, e nada mais fundo. A âncora de fim importa: o
#: BlueZ pendura filhos sob cada dispositivo (`.../dev_XX/sep1`, os endpoints de
#: áudio do DualSense), e chamar `Disconnect` num endpoint não derruba nada. É o
#: mesmo recorte de `exame_da_mesa._CAMINHO_DE_DISPOSITIVO`.
_CAMINHO_DE_DISPOSITIVO = re.compile(r"^/org/bluez/hci[0-9]+/dev_[0-9A-Fa-f_]+$")

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


def caminho_do_controle(mac: str, *, executar: Executar | None = None) -> str | None:
    """O caminho D-Bus deste endereço, em QUALQUER adaptador. ``None`` se não há.

    Varre `busctl tree` e casa pelo sufixo ``dev_<MAC>``. Não recebe ``hciN`` e
    não o deduz: numa mesa de três adaptadores o índice é sorteio, e o mesmo
    controle já apareceu sob ``hci1`` e sob ``hci2`` no mesmo dia.
    """
    alvo = _normalizar(mac)
    if alvo is None:
        return None
    rodar = _busctl if executar is None else executar
    bruto = rodar(["tree", SERVICO, "--list"])
    if bruto is None:
        return None
    sufixo = f"/dev_{alvo}"
    for linha in bruto.splitlines():
        caminho = linha.strip()
        if not caminho.endswith(sufixo):
            continue
        if _CAMINHO_DE_DISPOSITIVO.match(caminho):
            return caminho
    return None


def esta_conectado(mac: str, *, executar: Executar | None = None) -> bool | None:
    """O BlueZ diz que este endereço está conectado AGORA? ``None`` = não sei.

    Três respostas e não duas, pelo mesmo motivo do resto do arquivo: sem
    ``busctl``, com o ``bluetoothd`` fora ou com o dispositivo ausente da
    árvore, a resposta honesta é ``None``. Quem espera o botão PS tem de tratar
    ``None`` como "continua esperando", nunca como "voltou".
    """
    caminho = caminho_do_controle(mac, executar=executar)
    if caminho is None:
        return None
    rodar = _busctl if executar is None else executar
    bruto = rodar(
        ["get-property", SERVICO, caminho, INTERFACE_DO_DISPOSITIVO, "Connected"]
    )
    if bruto is None:
        return None
    texto = bruto.strip()
    if not texto:
        return None
    # O `busctl` responde com o tipo na frente: `b true`. Mesmo desembrulho de
    # `exame_da_mesa._propriedade_do_dispositivo`.
    valor = texto.split()[-1].strip('"').lower()
    if valor in ("true", "yes", "1"):
        return True
    if valor in ("false", "no", "0"):
        return False
    return None


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

    if esta_conectado(mac, executar=executar) is False:
        logger.info("reconexao_ja_estava_fora", endereco=mascara)
        return Resultado(ESTADO_JA_ESTAVA_FORA, FRASE_JA_ESTAVA_FORA, mascara)

    rodar = _busctl if executar is None else executar
    bruto = rodar(["call", SERVICO, caminho, INTERFACE_DO_DISPOSITIVO, "Disconnect"])
    if bruto is None:
        logger.warning("reconexao_disconnect_nao_deu", endereco=mascara)
        return Resultado(ESTADO_NAO_DEU, FRASE_NAO_DEU, mascara)
    logger.info("reconexao_disconnect_pedido", endereco=mascara)
    return Resultado(ESTADO_DESCONECTOU, FRASE_DESCONECTOU, mascara)


#: Teto do `Connect`, em segundos. Ele é MAIOR que o do resto porque o
#: `Connect` CHAMA o aparelho: o BlueZ tenta alcançar um rádio que pode estar
#: dormindo, e desistir em 5 s chamaria de "não deu" o que só estava demorando.
#: Medido na mesa dela em 22/09/2026: a recusa de um controle dormindo volta em
#: menos de 2 s (`br-connection-create-socket`), e um controle acordado
#: responde em 3-4 s.
ESPERA_DO_CONNECT_S = 12.0


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
    rodar = _busctl if executar is None else executar
    bruto = rodar(["tree", SERVICO, "--list"])
    if bruto is None:
        return []
    achados: list[tuple[str, bool | None]] = []
    for linha in bruto.splitlines():
        caminho = linha.strip()
        if not _CAMINHO_DE_DISPOSITIVO.match(caminho):
            continue
        modalias = rodar(
            ["get-property", SERVICO, caminho, INTERFACE_DO_DISPOSITIVO, "Modalias"]
        )
        if not modalias or _MODALIAS_DO_DUALSENSE not in modalias:
            continue
        mac = caminho.rsplit("/dev_", 1)[-1].replace("_", ":").lower()
        achados.append((mac, esta_conectado(mac, executar=executar)))
    return achados


#: A PORTA DE FUGA, para quem precisar medir o bus de verdade num teste. Quem
#: a declara assume a responsabilidade pelo rádio dela — é o mesmo contrato do
#: `HEFESTO_NA_TELA` da `utils/tela_de_mentira`.
RADIO_DE_VERDADE_NA_SUITE = "HEFESTO_RADIO_DE_VERDADE"


def _a_suite_esta_rodando() -> bool:
    """A suíte está no ar? Então este módulo NÃO fala com o rádio dela.

    **ESTA GUARDA NASCEU DE UM ESTRAGO MEDIDO — 22/09/2026, e o estrago foi
    meu.** O passo do rádio do «Reconectar controles» nasceu sem ela, e a
    primeira corrida de 457 testes que o alcançou chamou `Disconnect` e
    `Connect` nos QUATRO DualSense da mesa dela, ao vivo, no meio do trabalho
    dela. O recado do gesto saiu no relatório do teste: *"Aperte PS em 4
    controle(s)"*.

    É a mesma família da TELA-DELA-01 (`tests/conftest.py`) e da TELA-DELA-02
    (`utils/tela_de_mentira`): a suíte alcançando o aparelho dela. A diferença
    é que ali dava para REDIRECIONAR (uma tela de mentira) e aqui não há bus de
    mentira para onde mandar — então a resposta é recusar, e recusar devolve
    exatamente o que este módulo já sabe dizer: `None`, o *"não deu"* que vira
    `ESTADO_NAO_DEU` sem mentir que caiu ou que voltou.

    Quem injeta `executar` (todas as réguas deste módulo) não passa por aqui: o
    dublê é chamado direto, e continua exercitando a lógica inteira.
    """
    if os.environ.get(RADIO_DE_VERDADE_NA_SUITE) == "1":
        return False
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or "pytest" in sys.modules


def _connect_com_folga(argumentos: Sequence[str]) -> str | None:
    """O `busctl` do `Connect`, com o teto maior. Ver `ESPERA_DO_CONNECT_S`."""
    return _busctl(argumentos, espera=ESPERA_DO_CONNECT_S)


def reconectar(mac: str, *, executar: Executar | None = None) -> Resultado:
    """Devolve este controle ao rádio: derruba o elo morto e chama de volta.

    OS DOIS PASSOS, e o primeiro é o que o botão PS não consegue fazer:

    1. ``Disconnect`` quando o BlueZ ainda diz ``Connected`` — é o elo morto do
       estado que ela viu, com o rádio de pé e o kernel sem HID. Sem derrubá-lo,
       o PS dela não tem efeito: para o rádio o controle já está aqui;
    2. ``Connect``. Funciona com o controle ACORDADO (o elo caiu e ele continua
       ligado); com ele dormindo, o BlueZ recusa e o desfecho é
       :data:`ESTADO_SO_O_PS` — a metade que continua sendo dela.

    Nunca levanta, como todo o resto do módulo, e não usa ``sudo``.
    """
    mascara = mascarar(mac)
    caminho = caminho_do_controle(mac, executar=executar)
    if caminho is None:
        logger.info("reconexao_sem_alvo_no_bluez", endereco=mascara)
        return Resultado(ESTADO_SEM_ALVO, FRASE_SEM_ALVO, mascara)

    rodar = _busctl if executar is None else executar
    if esta_conectado(mac, executar=executar) is not False:
        # O elo morto sai primeiro. Um `Connect` por cima dele responde "já
        # está conectado" e não levanta sessão de entrada nenhuma — medido na
        # mesa dela, quatro vezes, com o kernel sem HID o tempo todo.
        if rodar(["call", SERVICO, caminho, INTERFACE_DO_DISPOSITIVO, "Disconnect"]) is None:
            logger.warning("reconexao_disconnect_nao_deu", endereco=mascara)
            return Resultado(ESTADO_NAO_DEU, FRASE_NAO_DEU, mascara)
        logger.info("reconexao_elo_morto_derrubado", endereco=mascara)

    # O `Connect` CHAMA o aparelho e tem teto próprio — ver
    # `ESPERA_DO_CONNECT_S`. Quem injeta `executar` (a régua) fica com o dele:
    # dublê não espera nada.
    chamar = rodar if executar is not None else _connect_com_folga
    voltou = chamar(["call", SERVICO, caminho, INTERFACE_DO_DISPOSITIVO, "Connect"])
    if voltou is None:
        logger.info("reconexao_connect_recusado", endereco=mascara)
        return Resultado(ESTADO_SO_O_PS, FRASE_SO_O_PS, mascara)
    logger.info("reconexao_voltou_pelo_radio", endereco=mascara)
    return Resultado(ESTADO_VOLTOU, FRASE_VOLTOU, mascara)


def _busctl(
    argumentos: Sequence[str], *, espera: float = ESPERA_DO_BUSCTL_S
) -> str | None:
    """Roda um `busctl` de USUÁRIO no bus do sistema e devolve a saída.

    ``None`` para os três jeitos de não dar — ferramenta ausente, código de
    saída diferente de zero e teto de tempo estourado. O chamador transforma os
    três em :data:`ESTADO_NAO_DEU`, que é a única leitura honesta: nenhum deles
    prova que o controle caiu, e nenhum deles prova que não caiu.

    Sem ``sudo``, e isso é o ponto: medido em 22/08/2026, o ``Disconnect`` de
    ``org.bluez.Device1`` responde para o uid 1000. O helper privilegiado do
    install existe para o que PRECISA de raiz, e este gesto não precisa.
    """
    if _a_suite_esta_rodando():
        return None
    if shutil.which("busctl") is None:
        return None
    try:
        saida = subprocess.run(
            ["busctl", *argumentos],
            capture_output=True,
            text=True,
            timeout=espera,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return saida.stdout if saida.returncode == 0 else None


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
    "Resultado",
    "caminho_do_controle",
    "desconectar",
    "dualsenses_do_radio",
    "esta_conectado",
    "mascarar",
]
