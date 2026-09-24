"""O que faz um nó de som desta casa PARECER um DualSense para quem o procura.

A-FORJA-VALIDA-O-SOM-01, 24/09/2026. Um dono para as palavras que o JOGO lê
num nó de áudio — e são duas metades, com riscos diferentes:

* **o NOME** — o que um jogo mostra e casa por substring. Sob Proton, o nome
  do endpoint é a ``device.description`` do nó (``winepulse.drv/pulse.c``,
  ``get_device_name``); um jogo que procura o alto-falante do controle procura
  ``DualSense`` ou ``Wireless Controller``, as strings USB da Sony
  (``/sys/bus/usb/devices/*/product``, medido em 21/09/2026). A decisão dela de
  23/09/2026 é a FORMA A: *«Alto-falante do Controle N (DualSense Wireless
  Controller)»* — o nome dela na frente, igual para o microfone, os quatro
  controles, o cabo e o BT. Quem monta é :func:`com_o_nome_da_sony`;
* **a IDENTIDADE** — ``device.bus``, VID, PID e ``sysfs.path``: o que o
  ``winepulse.drv`` usa para classificar o aparelho e calcular o
  ``ContainerId`` (``fill_device_info`` e ``get_container_id``). É o que o
  endpoint de háptica veste desde 18/09 (:mod:`integrations.endpoint_de_haptica`).

**POR QUE O NÓ DO ALTO-FALANTE VESTE SÓ O NOME** (decisão desta frente, pelo
padrão dela — o caminho mais reversível): o GE-Proton pinado dela chama de
«aparelho de áudio DualSense» todo nó com ``usb`` + ``054c`` + ``0ce6`` no
proplist (``proton-ds5-haptic``, patch 0013, ``is_dualsense_audio_device``), e
cada nó assim que entra ou sai soma um ``g_haptic_hotplug_generation`` (patch
0015) — o gatilho que remira a háptica do jogo aberto. O nó do alto-falante é
republicado quando o assento anda e quando o controle pisca. E o PRAGMATA
escolhe o endpoint pelo ``ContainerId`` (a memória de 17/09): dois endpoints
no mesmo contêiner, um de dois canais, é a porta para a háptica que já vibra
abrir no nó errado. Nada disso se mede sem um jogo aberto, então a metade da
identidade fica pronta aqui (:func:`campos_do_vestido`) e não é vestida no nó
do som até que um jogo prove que ela não rouba a háptica.
"""

from __future__ import annotations

#: O VID/PID que o ``winepulse.drv`` lê NO PROPLIST — não no aparelho.
VID_SONY = "054c"
PID_DUALSENSE = "0ce6"

#: As strings USB da Sony, lidas no sysfs de um DualSense no cabo em
#: 21/09/2026 (``product`` e ``manufacturer``). O PipeWire monta o nome do nó
#: real a partir delas, e ``fontes_de_captura.MARCADORES_DUALSENSE`` casa por
#: substring das mesmas.
NOME_USB_DA_SONY = "DualSense Wireless Controller"
FABRICANTE_USB = "Sony Interactive Entertainment"

#: O teto do nome no Wine (``MAX_DEVICE_NAME_LEN``, ``pulse.c``). Acima dele o
#: ``get_device_name`` troca a descrição pelo ``device.product.name`` — e o jogo
#: perderia «Controle N», que é o que diz qual dos quatro é qual.
TETO_DO_NOME_NO_WINE = 62

_ABRE = " ("
_FECHA = ")"


def com_o_nome_da_sony(rotulo: str) -> str:
    """A forma A: «<rótulo> (DualSense Wireless Controller)». Idempotente."""
    base = sem_o_nome_da_sony(rotulo)
    return f"{base}{_ABRE}{NOME_USB_DA_SONY}{_FECHA}" if base else ""


def sem_o_nome_da_sony(rotulo: str) -> str:
    """O rótulo dela, sem o sufixo da Sony — a leitura inversa da forma A.

    Existe porque o número do assento é a ÚLTIMA palavra do rótulo dela, e é
    dele que ``dualsense_bt_audio.numero_do_rotulo`` depende: com o sufixo no
    fim, a última palavra seria ``Controller)`` e todo nó perderia o número.
    """
    texto = str(rotulo or "").strip()
    sufixo = f"{_ABRE}{NOME_USB_DA_SONY}{_FECHA}"
    if texto.endswith(sufixo):
        return texto[: -len(sufixo)].rstrip()
    return texto


def campos_do_nome() -> tuple[str, ...]:
    """A metade do NOME, em ``chave=valor`` para o ``sink_properties=``.

    O ``node.nick`` é o da placa de verdade (``DualSense Wireless Controller``,
    medido em 21/09/2026 no nó do cabo) e NÃO leva o endereço do controle: um
    pedaço do MAC na lista de som da máquina é o defeito que a descrição do
    microfone já pagou em 09/09.
    """
    return (
        f"device.vendor.name='{FABRICANTE_USB}'",
        f"device.product.name='{NOME_USB_DA_SONY}'",
        f"node.nick='{NOME_USB_DA_SONY}'",
    )


def campos_da_identidade(sysfs_declarado: str) -> tuple[str, ...]:
    """A metade da IDENTIDADE: barramento, VID, PID e a âncora do ``ContainerId``.

    ``()`` sem âncora: sem ``sysfs.path`` o Wine zera o ``ContainerId``, e um
    nó que diz «sou USB da Sony» sem dizer de qual aparelho é pior que um nó
    que não diz nada.
    """
    caminho = str(sysfs_declarado or "").strip()
    if not caminho:
        return ()
    return (
        "device.bus=usb",
        f"device.vendor.id={VID_SONY}",
        f"device.product.id={PID_DUALSENSE}",
        f"sysfs.path={caminho}",
    )


def campos_do_vestido(sysfs_declarado: str) -> tuple[str, ...]:
    """As duas metades juntas — ``()`` sem âncora, pela razão de :func:`campos_da_identidade`."""
    identidade = campos_da_identidade(sysfs_declarado)
    return (*identidade, *campos_do_nome()) if identidade else ()


__all__ = [
    "FABRICANTE_USB",
    "NOME_USB_DA_SONY",
    "PID_DUALSENSE",
    "TETO_DO_NOME_NO_WINE",
    "VID_SONY",
    "campos_da_identidade",
    "campos_do_nome",
    "campos_do_vestido",
    "com_o_nome_da_sony",
    "sem_o_nome_da_sony",
]
