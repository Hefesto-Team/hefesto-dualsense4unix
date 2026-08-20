"""usb_pai.py — qual placa de som é de QUAL controle, pelo dispositivo USB.

O PROBLEMA QUE ESTE MÓDULO RESOLVE
-----------------------------------

O PipeWire publica o áudio do DualSense com um nome que **não carrega
identidade**. Medido nesta bancada em 15/08/2026, com dois controles no cabo::

    alsa_output.usb-Sony_..._DualSense_Wireless_Controller-00.analog-surround-40
    alsa_output.usb-Sony_..._DualSense_Wireless_Controller-00.2.analog-surround-40

O ``-00`` e o ``-00.2`` são desempate do PipeWire — a string USB de serial é a
mesma em todo DualSense —, e o próprio ``/dev/snd/by-id`` só consegue guardar
UM link para os dois (colisão de nome no udev). Por isso a janela recusava
atribuir sink a qualquer controle assim que havia mais de um: exibir a saída do
controle errado é pior que não exibir nenhuma.

Mas existe um casamento que não depende de nome nenhum: **a placa de som e o
HID do mesmo controle penduram no MESMO dispositivo USB**. No cabo, a interface
``:1.0`` é o áudio e a ``:1.3`` é o HID, e as duas são filhas do nó que tem
``busnum``/``devnum``. Medido na mesma bancada::

    hidraw8  -> .../usb3/3-2/3-2:1.3/...   card3 -> .../usb3/3-2/3-2:1.0
    hidraw10 -> .../usb3/3-3/3-3:1.3/...   card2 -> .../usb3/3-3/3-3:1.0

Repare que a ordem do NOME é o inverso da ordem do CARD (``-00`` é o card 3),
que é exatamente por que adivinhar por posição erraria — e erraria de forma
convincente, com metade dos casos certos.

A lógica vem do ``scripts/ensaios/audio_por_transporte.py`` (``_dispositivo_usb_pai``),
que a mediu primeiro. Aqui ela é PORTADA para o produto, não importada: o
``scripts/`` não é pacote instalado, e a janela não pode depender de um
instrumento de bancada.

O QUE ELE NÃO É
----------------

Não é um casamento universal de áudio: **pelo rádio o DualSense não publica
placa ALSA nenhuma** (medido 15/08/2026 — a placa segue o transporte). Para
esses controles a resposta honesta deste módulo é a ausência, e quem chama tem
de dizer isso na tela em vez de emprestar a placa do vizinho.

UNIVERSALIDADE (o que ela pediu em 15/08/2026)
-----------------------------------------------

Nada aqui olha MAC, ordem de conexão, número de controles ou nome de máquina.
A pergunta é sempre a mesma para 1, 2, 4 ou 7 controles: *este nó de áudio e
este HID penduram no mesmo dispositivo USB?* — e ela se responde igual em
qualquer PC, porque quem responde é o sysfs do kernel.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping

#: Onde o sysfs está montado. O ``pactl`` publica ``sysfs.path`` como caminho
#: RELATIVO a esta raiz (``/devices/...``), e é aqui que ele vira absoluto.
RAIZ_SYSFS = "/sys"

#: Onde o kernel lista os nós hidraw. Cada um tem ``device/uevent`` com o
#: ``HID_UNIQ`` — o mesmo identificador que a janela usa por controle.
RAIZ_HIDRAW = "/sys/class/hidraw"

_MARCA_UNIQ = "HID_UNIQ="


def dispositivo_usb_pai(
    caminho: str,
    *,
    existe: Callable[[str], bool] = os.path.exists,
    real: Callable[[str], str] = os.path.realpath,
) -> str:
    """Sobe o sysfs até o nó do DISPOSITIVO USB — "" se não houver nenhum.

    O nó procurado é o que tem ``busnum`` E ``devnum``: é ele o dispositivo, e
    não a interface. Parar na interface (``3-2:1.3``) casaria o HID só consigo
    mesmo; parar no barramento (``usb3``) casaria TODOS os controles daquela
    controladora entre si — os dois erros dão resposta, e resposta errada.

    ``""`` é resposta legítima e comum: um DualSense por rádio pendura em
    ``/sys/devices/virtual/misc/uhid/...`` e nunca chega a um nó USB.

    ``existe`` e ``real`` são injetáveis para o teste montar um sysfs de
    mentira sem precisar de controle plugado.
    """
    if not caminho:
        return ""
    atual = real(caminho)
    while atual and atual != "/":
        if existe(os.path.join(atual, "busnum")) and existe(
            os.path.join(atual, "devnum")
        ):
            return atual
        pai = os.path.dirname(atual)
        if pai == atual:
            break
        atual = pai
    return ""


def nos_e_sysfs(saida_pactl: str) -> dict[str, str]:
    """``{nome do nó: sysfs.path}`` da saída LONGA do ``pactl list sinks|sources``.

    Por que a saída longa e não a curta: a curta traz o nome e mais nada, e o
    nome é justamente o que não distingue dois DualSense. O ``sysfs.path`` da
    seção ``Properties`` é o fio que leva ao dispositivo USB.

    O corte de registro é a linha SEM recuo (``Sink #N`` / ``Source #N``), não
    o texto dela: o ``pactl`` traduz rótulos, e ancorar em palavra traduzida é
    defeito esperando idioma. Dentro do registro só interessam a PRIMEIRA linha
    ``Name:`` (as seguintes são de portas e formatos) e o ``sysfs.path``.

    Nó sem ``sysfs.path`` entra com ``""`` — é o caso de todo nó virtual, como
    a ponte de mic por Bluetooth deste projeto. Ele PRECISA entrar: "não tem
    dispositivo USB" é um fato usado para decidir, não uma ausência de dado.
    """
    mapa: dict[str, str] = {}
    nome = ""
    caminho = ""

    def _fechar() -> None:
        nonlocal nome, caminho
        if nome:
            mapa[nome] = caminho
        nome = ""
        caminho = ""

    for linha in saida_pactl.splitlines():
        if linha and not linha[0].isspace():
            _fechar()
            continue
        despida = linha.strip()
        if not nome and despida.startswith("Name:"):
            nome = despida[len("Name:") :].strip()
        elif despida.startswith("sysfs.path"):
            _, _, valor = despida.partition("=")
            caminho = valor.strip().strip('"')
    _fechar()
    return mapa


def usb_pai_por_no(
    sysfs_por_no: Mapping[str, str],
    *,
    raiz: str = RAIZ_SYSFS,
    existe: Callable[[str], bool] = os.path.exists,
    real: Callable[[str], str] = os.path.realpath,
) -> dict[str, str]:
    """``{nome do nó: dispositivo USB pai}``, "" para o que não pendura em USB."""
    saida: dict[str, str] = {}
    for nome, relativo in sysfs_por_no.items():
        if not relativo:
            saida[nome] = ""
            continue
        absoluto = os.path.join(raiz, relativo.lstrip("/"))
        saida[nome] = dispositivo_usb_pai(absoluto, existe=existe, real=real)
    return saida


def usb_pai_por_uniq(
    uniqs: Iterable[str],
    *,
    raiz: str = RAIZ_HIDRAW,
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
    existe: Callable[[str], bool] = os.path.exists,
    real: Callable[[str], str] = os.path.realpath,
) -> dict[str, str]:
    """``{uniq: dispositivo USB pai}`` para os controles pedidos.

    A chave devolvida é o ``uniq`` COMO VEIO — quem chama procura pela mesma
    string que já tem —, mas a comparação com o ``HID_UNIQ`` do kernel é feita
    só pelos dígitos hex: a janela e o sysfs não combinam maiúsculas.

    Controle sem nó USB (rádio, ou vpad virtual) entra com ``""``, pelo mesmo
    motivo de :func:`nos_e_sysfs`: a ausência é o dado que impede emprestar a
    placa do vizinho.

    Uma varredura de ``/sys`` por ciclo, sem subprocesso nenhum e sem abrir
    ``/dev`` — nada aqui disputa o hidraw com o daemon.
    """
    procurados = {_so_hex(u): u for u in uniqs if u}
    saida: dict[str, str] = {alvo: "" for alvo in procurados.values()}
    if not procurados:
        return saida
    try:
        nos = sorted(listar(raiz))
    except OSError:
        return saida
    leitor = ler if ler is not None else _ler_texto
    for no in nos:
        dispositivo = os.path.join(raiz, no, "device")
        hex_uniq = _so_hex(_uniq_do_uevent(leitor(os.path.join(dispositivo, "uevent"))))
        if not hex_uniq:
            continue
        original = procurados.get(hex_uniq)
        if original is None or saida[original]:
            continue
        saida[original] = dispositivo_usb_pai(dispositivo, existe=existe, real=real)
    return saida


def _uniq_do_uevent(texto: str) -> str:
    """O valor de ``HID_UNIQ=`` no uevent — "" quando o nó não declara um."""
    for linha in texto.splitlines():
        if linha.startswith(_MARCA_UNIQ):
            return linha[len(_MARCA_UNIQ) :].strip()
    return ""


def _ler_texto(caminho: str) -> str:
    """Lê um arquivo de ``/sys``; "" em qualquer erro — sysfs some sob a mão."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return arquivo.read()
    except OSError:
        return ""


def _so_hex(valor: str) -> str:
    """Só os dígitos hex minúsculos — a normalização de MAC do projeto."""
    return "".join(ch for ch in valor.lower() if ch in "0123456789abcdef")


__all__ = [
    "RAIZ_HIDRAW",
    "RAIZ_SYSFS",
    "dispositivo_usb_pai",
    "nos_e_sysfs",
    "usb_pai_por_no",
    "usb_pai_por_uniq",
]
