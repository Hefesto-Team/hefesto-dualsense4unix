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
  controles, o cabo e o BT. Quem monta é :func:`com_o_nome_da_sony`, e os
  campos que acompanham o nome no nó do alto-falante são :func:`campos_do_nome`;
* **a IDENTIDADE** — ``device.bus``, VID, PID e ``sysfs.path``: o que o
  ``winepulse.drv`` usa para classificar o aparelho e calcular o
  ``ContainerId`` (``fill_device_info`` e ``get_container_id``). Quem a veste
  é o endpoint de háptica (:mod:`integrations.endpoint_de_haptica`), desde
  18/09, e ele a lê daqui (:func:`campos_da_identidade`).

**POR QUE O NÓ DO ALTO-FALANTE VESTE SÓ O NOME** (decisão desta frente, pelo
padrão dela — o caminho mais reversível): o GE-Proton pinado dela chama de
«aparelho de áudio DualSense» todo nó com ``usb`` + ``054c`` + ``0ce6`` no
proplist (``proton-ds5-haptic``, patch 0013, ``is_dualsense_audio_device``), e
cada nó assim que entra ou sai soma um ``g_haptic_hotplug_generation`` (patch
0015) — o gatilho que remira a háptica do jogo aberto. O nó do alto-falante é
republicado quando o assento anda e quando o controle pisca. E o endpoint de
háptica existe justamente para ser O nó que o jogo acha sozinho — *"só este
casa com o teste, então o jogo não se confunde entre os dois"*
(``EndpointDeHaptica``). Dois nós com a identidade da Sony para o mesmo
controle, um de dois canais, é a porta para a háptica que já vibra abrir no nó
errado. Nada disso se mede sem um jogo aberto, então a identidade fica com o
endpoint de háptica, e o nó do alto-falante só veste o nome — até que um jogo
prove que os dois podem ser um só (a pergunta do §8 da sprint).
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
#: ``get_device_name`` troca a descrição inteira pelo ``device.product.name`` —
#: e o jogo perderia «Controle N», que é o que diz qual dos quatro é qual.
TETO_DO_NOME_NO_WINE = 62

_SUFIXO = f" ({NOME_USB_DA_SONY})"


def com_o_nome_da_sony(rotulo: str) -> str:
    """A forma A: «<rótulo> (DualSense Wireless Controller)». Idempotente.

    **O número vale mais que o sufixo.** Se o rótulo com o sufixo passar do
    :data:`TETO_DO_NOME_NO_WINE`, o Wine jogaria fora a frase inteira e o jogo
    mostraria só «DualSense Wireless Controller» — quatro controles com o mesmo
    nome. Nesse caso o rótulo dela sai sem o sufixo. Os rótulos desta casa
    («Alto-falante do Controle 4», «Microfone do Controle 4») cabem com folga;
    a guarda é para quem mudar a frase depois.
    """
    base = sem_o_nome_da_sony(rotulo)
    if not base:
        return ""
    vestido = f"{base}{_SUFIXO}"
    return vestido if len(vestido) <= TETO_DO_NOME_NO_WINE else base


def sem_o_nome_da_sony(rotulo: str) -> str:
    """O rótulo dela, sem o sufixo da Sony — a leitura inversa da forma A.

    Existe porque o número do assento é a ÚLTIMA palavra do rótulo dela, e é
    dele que ``dualsense_bt_audio.numero_do_rotulo`` depende: com o sufixo no
    fim, a última palavra seria ``Controller)`` e todo nó perderia o número.
    """
    texto = str(rotulo or "").strip()
    if texto.endswith(_SUFIXO):
        return texto[: -len(_SUFIXO)].rstrip()
    return texto


def campos_do_nome() -> tuple[str, ...]:
    """A metade do NOME, em ``chave=valor`` para o ``sink_properties=``.

    Os três são os da placa de verdade, medidos em 21/09/2026 no nó do cabo, e
    nenhum leva o endereço do controle: um pedaço do MAC na lista de som da
    máquina é o defeito que a descrição do microfone já pagou em 09/09.

    O que o Wine faz com eles: o ``device.product.name`` é o nome de RESERVA do
    ``get_device_name`` quando a descrição passa do teto — e o monitor do nó
    («Monitor of Alto-falante do Controle 1 (…)», 69 caracteres) passa. Sem ele
    o nome do monitor chegaria ao jogo com 69, que é o comprimento que derruba
    os aplicativos que o teto existe para proteger.
    """
    return (
        f"device.vendor.name='{FABRICANTE_USB}'",
        f"device.product.name='{NOME_USB_DA_SONY}'",
        f"node.nick='{NOME_USB_DA_SONY}'",
    )


def campos_da_identidade(sysfs_declarado: str) -> tuple[str, ...]:
    """A metade da IDENTIDADE: barramento, VID, PID e a âncora do ``ContainerId``.

    ``()`` sem âncora: sem ``sysfs.path`` o Wine zera o ``ContainerId`` — e
    zerado é o valor de toda saída que não é USB, então um nó que diz «sou USB
    da Sony» sem dizer de qual aparelho é pior que um nó que não diz nada.
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


__all__ = [
    "FABRICANTE_USB",
    "NOME_USB_DA_SONY",
    "PID_DUALSENSE",
    "TETO_DO_NOME_NO_WINE",
    "VID_SONY",
    "campos_da_identidade",
    "campos_do_nome",
    "com_o_nome_da_sony",
    "sem_o_nome_da_sony",
]
