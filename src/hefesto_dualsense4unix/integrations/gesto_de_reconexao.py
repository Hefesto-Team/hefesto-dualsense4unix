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

**Não reconectar é decisão dela, e é o contrato deste módulo.** O botão PS é
dela; :func:`reconectar` não existe aqui de propósito. Um ``Connect`` nosso
devolveria o controle sem o gesto físico — e a instância que voltaria seria
nossa, não dela, num caminho que ninguém mediu.

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

import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: Teto de espera de cada `busctl`, em segundos. O mesmo número de
#: `integrations/exame_da_mesa.py:73` e de `integrations/apelido_do_dongle.py`:
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


def _busctl(argumentos: Sequence[str]) -> str | None:
    """Roda um `busctl` de USUÁRIO no bus do sistema e devolve a saída.

    ``None`` para os três jeitos de não dar — ferramenta ausente, código de
    saída diferente de zero e teto de tempo estourado. O chamador transforma os
    três em :data:`ESTADO_NAO_DEU`, que é a única leitura honesta: nenhum deles
    prova que o controle caiu, e nenhum deles prova que não caiu.

    Sem ``sudo``, e isso é o ponto: medido em 22/08/2026, o ``Disconnect`` de
    ``org.bluez.Device1`` responde para o uid 1000. O helper privilegiado do
    install existe para o que PRECISA de raiz, e este gesto não precisa.
    """
    if shutil.which("busctl") is None:
        return None
    try:
        saida = subprocess.run(
            ["busctl", *argumentos],
            capture_output=True,
            text=True,
            timeout=ESPERA_DO_BUSCTL_S,
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
    "FRASE_DESCONECTOU",
    "FRASE_JA_ESTAVA_FORA",
    "FRASE_NAO_DEU",
    "FRASE_SEM_ALVO",
    "Resultado",
    "caminho_do_controle",
    "desconectar",
    "esta_conectado",
    "mascarar",
]
