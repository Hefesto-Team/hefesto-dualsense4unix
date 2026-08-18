"""Por RÁDIO, o único discriminador entre o clone e o genuíno é a OUI do MAC.

O QUE ESTE ARQUIVO GUARDA
-------------------------
A doutrina da casa, escrita em `docs/protocol/externos-referencia-canonica.md`
§5.3 e nas linhas `plataforma.distinguir_clone@pro` e
`plataforma.distinguir_clone@sn30` do mapa de canais: **pelo cabo** o
`bcdDevice` separa o Pro genuíno (`0210`) do clone 8BitDo (`0200`); **pelo
rádio** ele não existe — o Modalias sai `usb:v057Ep2009d0001` nos dois, com o
campo `d` fixo — e o que resta é a OUI do endereço.

E a OUI é a fonte da verdade justamente porque o firmware clone **mente o VID**
(por Bluetooth em modo DS4 ele se anuncia como Sony `054c`, nome "Wireless
Controller") e nunca mente o MAC. Três lugares independentes da árvore agem
sobre isso, e este arquivo cobra que os três continuem concordando:

- `daemon/subsystems/external_identity.py` — `NINTENDO_REAL_OUI`, o gatilho
  ESTRITO do enable-IMU (o clone não recebe o comando);
- `scripts/bt_active_mode.sh` — `OUI_NINTENDO_REAL`, o no-sniff POR-LINK (o
  genuíno cai sob carga COM sniff; o clone não completa a probe SEM sniff — A/B
  medido em 23/07/2026, requisitos OPOSTOS);
- `assets/82-nintendo-pro-nosniff.rules` — o mesmo escopo na borda do connect,
  por `ENV{HID_UNIQ}`.

O QUE ELE NÃO PROVA
-------------------
Nada sobre o fio: ele não pareia, não conecta e não lê endereço de aparelho
nenhum. Ele guarda a REGRA — se alguém trocar a OUI num dos três lugares, ou
fizer o VID voltar a vencer o MAC, o clone passa a receber o tratamento do
genuíno (ou o contrário) e a casa fica sem discriminador por rádio, calada.

ANONIMATO: nenhum endereço aparece escrito aqui. Os MACs de exemplo são
MONTADOS em tempo de execução a partir das constantes do próprio produto, com os
octetos 4 e 5 zerados — a máscara da casa.

MORDE? Tire a precedência do OUI sobre o VID em `brand_of`, ou troque a OUI de
um dos três lugares: cada um reprova um teste distinto deste arquivo.

MORDIDA PROVADA (15/08/2026, no espelho da árvore em `/tmp`, com a árvore de
trabalho intocada): ver `mordida_provada_em` nas duas linhas
`plataforma.distinguir_clone@*` do mapa de canais.
"""

from __future__ import annotations

import re
from pathlib import Path

from hefesto_dualsense4unix.app.actions.external_controllers import (
    _BRAND_BY_OUI,
    brand_of,
)
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    NINTENDO_REAL_OUI,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_MODO_ATIVO = REPO_ROOT / "scripts" / "bt_active_mode.sh"
REGRA_NOSNIFF = REPO_ROOT / "assets" / "82-nintendo-pro-nosniff.rules"

#: A OUI do clone, LIDA do produto — nunca escrita aqui (guarda de anonimato de
#: `tests/`: MAC-forma só nas faixas forjadas, e OUI real não é faixa forjada).
OUI_DO_CLONE = next(iter(_BRAND_BY_OUI))


def _mac_mascarado(oui: str, ultimo: int) -> str:
    """`OUI:00:00:NN` — a máscara da casa, montada a partir da OUI dada."""
    return ":".join((oui[0:2], oui[2:4], oui[4:6], "00", "00", f"{ultimo:02x}"))


def _oui_colada(texto: str) -> str:
    """Só os dígitos hex, minúsculos: `E0:F6:B5` e `e0f6b5` viram a mesma coisa."""
    return "".join(ch for ch in texto.lower() if ch in "0123456789abcdef")


def test_a_marca_do_clone_vence_o_vid_que_ele_mente() -> None:
    """Em modo DS4 o clone é Sony por VID e por nome; só o MAC o entrega.

    MORDIDA: tire o bloco do OUI de `brand_of` (deixando o `_VENDOR_BY_VID`
    responder primeiro) e este teste reprova com "Sony" — que é exatamente o que
    a interface dela mostraria para um 8BitDo.
    """
    clone_em_modo_ds4 = {
        "vid": "054c",
        "pid": "05c4",
        "name": "Wireless Controller",
        "uniq": _mac_mascarado(OUI_DO_CLONE, 1),
        "bus": "bluetooth",
    }
    assert brand_of(clone_em_modo_ds4) == _BRAND_BY_OUI[OUI_DO_CLONE], (
        "o clone voltou a passar por Sony: por rádio o VID é mentira do "
        "firmware e a OUI do MAC é o único sinal que separa os dois"
    )


def test_sem_oui_conhecida_a_marca_cai_no_vid_como_sempre() -> None:
    """Não-regressão: quem não é clone continua sendo lido pelo VID.

    É o caso do CABO, onde o `uniq` vem vazio — ali a distinção é outra (o
    `bcdDevice`), e forçar a OUI seria inventar dado que não existe.
    """
    pelo_cabo = {"vid": "057e", "pid": "2009", "name": "Pro Controller", "uniq": ""}
    assert brand_of(pelo_cabo) == "Nintendo"


def test_as_tres_reguas_da_casa_apontam_para_a_mesma_oui_do_genuino() -> None:
    """O código, o script do modo ativo e a regra udev 82 têm de concordar.

    MORDIDA: troque a OUI em QUALQUER um dos três e este teste reprova. Não é
    zelo tipográfico: o no-sniff é a cura do Pro genuíno e o VENENO do clone (a
    probe dele morre em `Failed to get joycon info; ret=-110` sem sniff), então
    um dos três apontando para o endereço errado troca o tratamento dos dois.
    """
    do_codigo = _oui_colada(NINTENDO_REAL_OUI)

    texto_script = SCRIPT_MODO_ATIVO.read_text(encoding="utf-8")
    achado = re.search(r'OUI_NINTENDO_REAL="([0-9A-Fa-f:]+)"', texto_script)
    assert achado, "o `bt_active_mode.sh` não declara mais `OUI_NINTENDO_REAL`"
    do_script = _oui_colada(achado.group(1))

    texto_regra = REGRA_NOSNIFF.read_text(encoding="utf-8")
    prefixos = {
        _oui_colada(m)
        for m in re.findall(r'ENV\{HID_UNIQ\}=="([0-9A-Fa-f:]+):\*"', texto_regra)
    }
    assert prefixos, "a regra 82 não escopa mais por `ENV{HID_UNIQ}`"

    assert do_script == do_codigo, (
        f"o script do modo ativo mira `{do_script}` e o produto mira "
        f"`{do_codigo}` — o no-sniff passaria a cair no aparelho errado"
    )
    assert prefixos == {do_codigo}, (
        f"a regra udev 82 escopa {sorted(prefixos)} e o produto mira "
        f"`{do_codigo}`: a regra e o script não podem discordar sobre quem "
        "recebe o tratamento"
    )


def test_o_tratamento_do_genuino_nunca_alcanca_a_oui_do_clone() -> None:
    """O clone PRECISA do sniff — receber o no-sniff quebra a probe dele.

    Este é o par que impede a "correção" mais tentadora: alargar o escopo para
    cobrir os dois controles da linhagem Nintendo.
    """
    do_codigo = _oui_colada(NINTENDO_REAL_OUI)
    assert do_codigo != OUI_DO_CLONE, (
        "a OUI do genuíno virou a do clone: o tratamento de no-sniff passaria a "
        "matar a probe do 8BitDo (4 falhas / 0 sucessos, A/B de 23/07)"
    )
    texto_regra = REGRA_NOSNIFF.read_text(encoding="utf-8")
    assert OUI_DO_CLONE not in _oui_colada(
        "\n".join(
            ln for ln in texto_regra.splitlines() if not ln.lstrip().startswith("#")
        )
    ), "a regra 82 passou a casar a OUI do clone — é o veneno dele, não a cura"
