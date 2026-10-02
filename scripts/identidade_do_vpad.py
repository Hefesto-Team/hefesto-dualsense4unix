#!/usr/bin/env python3
"""identidade_do_vpad.py — a régua única que separa o vpad do Hefesto do aparelho.

POR QUE ESTE MÓDULO EXISTE (VPAD-NO-ESPELHO-01, 12/08/2026)
-----------------------------------------------------------
A pergunta *"este nó é um gamepad virtual do próprio produto?"* estava escrita
TRÊS vezes, uma por instrumento de bancada, e as três respondiam coisas
diferentes:

- `ensaio_rumble_em_par.py` respondia **errado**: aceitava mirar nos quatro
  vpads do co-op, rotulados como transporte `cabo`. Foi o defeito medido na
  mesa de 12/08 e curado ali;
- `ensaio_rumble_um_bit_por_vez.py` e `ensaio_o_keepalive_mata_o_rumble.py`
  respondiam **certo por acidente**: nenhum dos dois pergunta pelo vpad. Eles
  só aceitam o PID `0CE6`, e o vpad se apresenta como `0DF2` (DualSense Edge).
  A imunidade é do filtro de PID, não de régua nenhuma.

A segunda é uma bomba-relógio com pino já frouxo: **o DualSense Edge existe de
verdade**, e acrescentar `0x0DF2` à lista de PIDs é uma coisa razoável de se
querer fazer (o `ensaio_rumble_em_par.py` JÁ aceita os dois). No dia em que
alguém fizer isso, os dois instrumentos passam a aceitar mirar no vpad do
próprio produto — e a medição sai falsa **sem avisar**, porque o vpad tem
força-feedback e aceita o efeito calado, sem que motor nenhum gire.

Reusar em vez de reimplementar é regra desta casa, e a razão é esta: duas
leituras do mesmo dado são duas réguas, e uma delas envelhece calada. O
precedente de forma é `scripts/eliminacao.py`, importado pelo `gerar-mapa.py`
com `sys.path.insert(0, <dir deste arquivo>)`.

O QUE A RÉGUA OLHA, E O QUE ELA SE RECUSA A OLHAR
--------------------------------------------------
Ela pergunta **de quem é o device** antes de perguntar **o que ele diz ser**.

O critério é o que o PRODUTO carimba de propósito no `UHID_CREATE2`
(`src/hefesto_dualsense4unix/integrations/uhid_gamepad.py::_create2_event`) e
que o kernel republica no `uevent` do device HID pai::

    o vpad do Hefesto                    um DualSense de verdade (rádio)
    ---------------------------------    ---------------------------------
    DRIVER=playstation                   DRIVER=playstation
    HID_ID=0003:0000054C:00000DF2        HID_ID=0005:0000054C:00000CE6
    HID_NAME=DualSense … (Hefesto P1)    HID_NAME=DualSense Wireless Controller
    HID_PHYS=hefesto-vpad      <-- nós   HID_PHYS=<MAC do adaptador>
    HID_UNIQ=02:fe:00:00:00:01 <-- nós   HID_UNIQ=<MAC do controle>

O que ela **NÃO** olha, e é o ponto todo:

- **barramento, VID e PID** — os três são exatamente o que o vpad forja bem.
  Ele existe para se passar por um DualSense Edge no cabo, e consegue;
- **"mora sob `/devices/virtual/`"** — essa é a armadilha paga em 11/08/2026:
  com BlueZ ≥ 5.73 (UserspaceHID por padrão) o `bluetoothd` cria o HID dos
  controles Bluetooth **FÍSICOS** via `/dev/uhid`, no mesmíssimo lugar em que
  mora o nosso vpad. Recusar "virtual" recusaria metade da mesa — justo os do
  rádio, que costumam ser o ensaio.

MEDIDO na mesa de 12/08/2026, oito aparelhos (4 físicos + 4 vpads): os 16 nós
de vpad trazem `HID_PHYS=hefesto-vpad`; os 16 nós físicos trazem ali um MAC de
adaptador (rádio) ou um caminho USB (cabo). Nenhum físico traz `HID_UNIQ`
começando em `02:` — o primeiro octeto par é o bit *locally administered*, que
por definição não colide com endereço de fábrica.
"""
from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping

#: produto escreve. Num DualSense de verdade este campo é o MAC do adaptador
VPAD_HID_PHYS = "hefesto-vpad"

VPAD_UNIQ_PREFIXO = "02:fe:"

#: (`DualSense Wireless Controller (Hefesto P1)`). Nome é frágil por natureza —
#: este mesmo já mudou uma vez (BT-E-VPAD-01 trocou `Hefesto Virtual DualSense
VPAD_MARCA_NO_NOME = "(Hefesto P"

_PHYS_DO_NO_NAO_SERVE = True


def campos_do_uevent(texto: str) -> dict[str, str]:
    """As linhas `CHAVE=valor` de um `uevent` como dicionário."""
    return dict(
        linha.split("=", 1) for linha in texto.splitlines() if "=" in linha
    )


def ler_uevent(caminho: str) -> dict[str, str]:
    """`campos_do_uevent` do arquivo em `caminho` ({} se ilegível)."""
    try:
        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return campos_do_uevent(arquivo.read())
    except OSError:
        return {}


def e_vpad_do_hefesto(
    campos: Mapping[str, str],
    *,
    uniq_do_no: str = "",
    nome: str = "",
) -> bool:
    """True quando o aparelho descrito por `campos` é um vpad DESTE produto."""
    if campos.get("HID_PHYS", "").strip().lower().startswith(VPAD_HID_PHYS):
        return True
    if campos.get("HID_UNIQ", "").strip().lower().startswith(VPAD_UNIQ_PREFIXO):
        return True
    if uniq_do_no.strip().lower().startswith(VPAD_UNIQ_PREFIXO):
        return True
    return VPAD_MARCA_NO_NOME in (nome or campos.get("HID_NAME", ""))


#: máscara DualSense. Até a marca `phys` que a A-ENTRADA vai carimbar, a régua
#: DualSense Edge de verdade tem device HID pai — os dois ficam fora.
_MORADA_DO_UINPUT = re.compile(r"/devices/virtual/input/input\d+/?$")


def nomes_do_pad_uinput() -> frozenset[str]:
    """Os nomes que o produto pede ao kernel para o pad `uinput`, do FONTE dele."""
    try:
        from hefesto_dualsense4unix.integrations.uinput_gamepad import FLAVORS
    except Exception:
        return frozenset()
    return frozenset(str(dados["name"]) for dados in FLAVORS.values())


def e_pad_uinput_do_hefesto(
    nome: str, dir_device: str, nomes: Iterable[str] | None = None
) -> bool:
    """True quando o nó de entrada em `dir_device` é o pad `uinput` DESTE produto."""
    permitidos = nomes_do_pad_uinput() if nomes is None else frozenset(nomes)
    if not nome or nome not in permitidos:
        return False
    try:
        real = os.path.realpath(dir_device)
    except OSError:
        return False
    return bool(_MORADA_DO_UINPUT.search(real))


def uniq_do_no_de_entrada(dir_device: str) -> str:
    """O `uniq` do nó de entrada em `dir_device` ("" se ilegível)."""
    try:
        with open(
            os.path.join(dir_device, "uniq"), encoding="utf-8", errors="replace"
        ) as arquivo:
            return arquivo.read().strip()
    except OSError:
        return ""
