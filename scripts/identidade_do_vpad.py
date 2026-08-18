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
from collections.abc import Mapping

#: `phys` do `UHID_CREATE2`, republicado pelo kernel como `HID_PHYS`. É a marca
#: MAIS forte: não é endereço nem nome de aparelho, é uma palavra que só este
#: produto escreve. Num DualSense de verdade este campo é o MAC do adaptador
#: (rádio) ou o caminho USB (cabo).
VPAD_HID_PHYS = "hefesto-vpad"

#: Prefixo do MAC forjado por jogador (`uhid_gamepad.player_mac` →
#: `02:fe:00:00:00:0N`), que sai em `HID_UNIQ` e também no `uniq` do nó de
#: entrada — o `hid_playstation` copia `hdev->uniq` para o `input_dev` (fonte:
#: `assets/dkms/hid-playstation/hid-playstation.c:704`).
VPAD_UNIQ_PREFIXO = "02:fe:"

#: SEGUNDA REDE, nunca a régua: a marca humana no nome
#: (`DualSense Wireless Controller (Hefesto P1)`). Nome é frágil por natureza —
#: este mesmo já mudou uma vez (BT-E-VPAD-01 trocou `Hefesto Virtual DualSense
#: P1` pelo de hoje, e há código nesta casa que ainda procura o nome velho).
#: Entra só para o caso em que o `uevent` do pai não se deixa ler.
VPAD_MARCA_NO_NOME = "(Hefesto P"

#: O `phys` do NÓ DE ENTRADA não serve de régua nenhuma para esta classe de
#: aparelho, e isto é MEDIDO, não suposto: o `ps_allocate_input_dev` do
#: `hid_playstation` copia `bustype`, `vendor`, `product`, `version`, `uniq` e
#: `name` para o `input_dev`, e **não copia `phys`**
#: (`assets/dkms/hid-playstation/hid-playstation.c:691-718`; a cópia do `uniq`
#: está na linha 704, e não há linha equivalente para `phys`). Na mesa de
#: 12/08/2026, os 22 nós de entrada com pai `DRIVER=playstation` — vpads,
#: cabeados e de rádio — trazem `phys` VAZIO, enquanto os 10 nós de
#: `DRIVER=hid-generic` da mesma máquina trazem o `phys` preenchido. Por isso
#: esta régua lê `HID_PHYS` do **uevent do pai**, nunca o atributo do nó.
_PHYS_DO_NO_NAO_SERVE = True


def campos_do_uevent(texto: str) -> dict[str, str]:
    """As linhas `CHAVE=valor` de um `uevent` como dicionário.

    Aceita o texto já lido em vez do caminho de propósito: quem chama costuma
    precisar do MESMO texto para outra coisa (o barramento, o `HID_ID`), e ler
    o arquivo duas vezes abriria a porta para duas fontes discordarem sobre o
    mesmo device entre uma leitura e outra.
    """
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
    """True quando o aparelho descrito por `campos` é um vpad DESTE produto.

    `campos` são as linhas do `uevent` do device HID **pai** — o mesmo arquivo
    de que sai o `HID_ID`. `uniq_do_no` é o `uniq` do nó de entrada, quando
    quem chama já o tem em mãos (é a MESMA marca por outro caminho: o
    `hid_playstation` copia `hdev->uniq` para o `input_dev`). `nome` cai no
    `HID_NAME` do próprio `uevent` quando não é passado.

    Em ordem de força:

    1. `HID_PHYS == hefesto-vpad` — carimbo do produto, some junto com o vpad;
    2. `HID_UNIQ` (ou o `uniq` do nó) com o prefixo do MAC forjado;
    3. a marca no nome, SEGUNDA REDE, para o caso de o `uevent` não abrir.

    Conservadora por desenho: na ausência total de dado ela devolve **False**.
    Aqui isso é o certo, e é o oposto da escolha do `_is_virtual_evdev` do
    daemon — lá, "na dúvida é virtual" protege contra o daemon adotar a própria
    saída; aqui, "na dúvida é vpad" recusaria mirar num aparelho de verdade e
    o ensaio não aconteceria. Quem fecha o outro lado é o filtro de VID/PID e
    barramento de quem chama, que este módulo deliberadamente não substitui.
    """
    if campos.get("HID_PHYS", "").strip().lower().startswith(VPAD_HID_PHYS):
        return True
    if campos.get("HID_UNIQ", "").strip().lower().startswith(VPAD_UNIQ_PREFIXO):
        return True
    if uniq_do_no.strip().lower().startswith(VPAD_UNIQ_PREFIXO):
        return True
    return VPAD_MARCA_NO_NOME in (nome or campos.get("HID_NAME", ""))


def uniq_do_no_de_entrada(dir_device: str) -> str:
    """O `uniq` do nó de entrada em `dir_device` ("" se ilegível).

    Conveniência para quem tem o diretório do nó em mãos (o
    `/sys/class/input/eventN/device`) e quer alimentar `uniq_do_no`.
    """
    try:
        with open(
            os.path.join(dir_device, "uniq"), encoding="utf-8", errors="replace"
        ) as arquivo:
            return arquivo.read().strip()
    except OSError:
        return ""
