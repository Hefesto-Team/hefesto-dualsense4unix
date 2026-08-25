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
Controller") e nunca mente o MAC.

**A PERGUNTA MUDOU DE FORMA EM 25/08/2026, e a mudança é o assunto desta casa**
(UMA-FAIXA-NÃO-É-UM-FABRICANTE-01 / E1). Até então os três lugares comparavam o
endereço com UMA faixa — `e0:f6:b5`, a do Pro desta bancada — e este arquivo
cobrava que as três apontassem para ela. A Nintendo tem 82 faixas MA-L
registradas e a 8BitDo tem UMA (medido contra `/usr/share/ieee-data/oui.csv` em
22/08/2026): a lista fechada que funciona é a do CLONE, e a pergunta passou a ir
por NEGATIVA. A afirmação "a OUI do genuíno é a fonte da verdade" era um fato
errado, e fato errado se SUBSTITUI — ela saiu daqui junto com o código que a
escrevia.

O que continua verdade, e é o que este arquivo guarda: **a OUI do CLONE é o
único sinal honesto que ele emite**, e os lugares que decidem sobre no-sniff têm
de concordar sobre ela. Os três:

- `daemon/subsystems/external_identity.py` — `e_pro_genuino`, o gatilho do
  enable-IMU (o clone não recebe o comando);
- `scripts/bt_active_mode.sh` — o no-sniff POR-LINK a cada tick da vigia, e
  `scripts/bt_nosniff_now.sh`, o mesmo na BORDA do connect (o genuíno cai sob
  carga COM sniff; o clone não completa a probe SEM sniff — A/B medido em
  23/07/2026, requisitos OPOSTOS);
- `assets/82-nintendo-pro-nosniff.rules` — quem chama o segundo.

Quem cobra o resto — que a cura alcance um Pro de qualquer safra, e que as
cópias em shell não se separem do dono — é
`tests/unit/test_o_no_sniff_alcanca_todo_pro.py`.

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
from hefesto_dualsense4unix.core.linhagem_nintendo import OUIS_NINTENDO_VISTAS
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    NINTENDO_REAL_OUI,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_MODO_ATIVO = REPO_ROOT / "scripts" / "bt_active_mode.sh"
SCRIPT_BORDA = REPO_ROOT / "scripts" / "bt_nosniff_now.sh"
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
    """NOME HERDADO — o mapa de canais aponta para ESTE nó do pytest.

    A célula `teste_que_morde` da linha `plataforma.distinguir_clone@pro` em
    `docs/data/mapa-controles.csv` cita este id, e o
    `scripts/check_paridade_transporte.py` reprova quando ele some. O nome
    descreve a regra de ANTES de 25/08/2026 — "as três réguas apontam para a
    mesma OUI do genuíno" —, e essa regra caiu: uma faixa não é um fabricante, e
    a pergunta passou a ir por negativa, pela faixa do CLONE.

    **DÍVIDA DATADA (25/08/2026), e por que ela não fecha aqui.** O nome certo é
    `test_os_dois_scripts_de_no_sniff_concordam_sobre_quem_e_o_clone`. Trocá-lo
    exige mexer em `docs/data/mapa-controles.csv` no MESMO commit, e o mapa é
    território de outra frente — ninguém escreve nele de fora. Quem fechar:
    renomeie os dois juntos e apague este nó.

    O que ele guarda continua sendo o que a linha do mapa promete: por rádio, a
    OUI é o que separa o clone do genuíno.
    """
    test_os_dois_scripts_de_no_sniff_concordam_sobre_quem_e_o_clone()
    test_a_faixa_desta_bancada_nao_voltou_a_ser_a_definicao_de_pro()


def test_os_dois_scripts_de_no_sniff_concordam_sobre_quem_e_o_clone() -> None:
    """Quem recusa o no-sniff é a faixa do CLONE, e ela é a mesma nos dois.

    Os dois scripts decidem por NEGATIVA e carregam a lista do clone escrita em
    shell — eles rodam como root, pelo udev e pelo `ExecStartPost` do
    bluetoothd, antes de qualquer venv da casa existir.

    MORDIDA: troque a faixa do clone em QUALQUER um dos dois e este teste
    reprova. Não é zelo tipográfico: o no-sniff é a cura do Pro genuíno e o
    VENENO do clone (a probe dele morre em `Failed to get joycon info;
    ret=-110` sem sniff), então um dos dois com a faixa errada troca o
    tratamento dos dois controles.
    """
    for script in (SCRIPT_MODO_ATIVO, SCRIPT_BORDA):
        texto = script.read_text(encoding="utf-8")
        achado = re.search(r"^OUIS_CLONE=\(([^)]*)\)", texto, re.MULTILINE)
        assert achado, f"`{script.name}` não declara mais `OUIS_CLONE`"
        faixas = {_oui_colada(m) for m in re.findall(r'"([^"]*)"', achado.group(1))}
        assert faixas == {OUI_DO_CLONE}, (
            f"`{script.name}` conhece as faixas de clone {sorted(faixas)} e o "
            f"produto conhece {{'{OUI_DO_CLONE}'}}"
        )


def test_a_faixa_desta_bancada_nao_voltou_a_ser_a_definicao_de_pro() -> None:
    """O fato substituído não pode voltar por uma constante nova.

    Até 25/08/2026 os dois scripts comparavam o endereço com `OUI_NINTENDO_REAL`
    — a faixa do Pro DESTA casa — e um Pro de outra safra não recebia a cura,
    calado. Este teste é a lápide: se a constante reaparecer, ela reprova.

    O casamento é pela DECLARAÇÃO, não pela menção: os dois scripts citam o nome
    dela em comentário, de propósito, para dizer o que mudou e por quê.

    A ÂNCORA ACEITA INDENTAÇÃO, e isso foi medido: com `^OUI_NINTENDO_REAL=`
    puro, uma redeclaração DENTRO do laço — que é exatamente onde ela viveria —
    passava por baixo do portão, e a mordida saía verde (25/08/2026).
    """
    for script in (SCRIPT_MODO_ATIVO, SCRIPT_BORDA):
        texto = script.read_text(encoding="utf-8")
        assert not re.search(r"^[ \t]*OUI_NINTENDO_REAL=", texto, re.MULTILINE), (
            f"`{script.name}` voltou a decidir 'quem é um Pro' por UMA faixa. A "
            "Nintendo tem 82 faixas MA-L registradas: uma amostra de tamanho um "
            "vira a definição, e o Pro de quem não mora aqui perde a cura"
        )


def test_a_regra_82_so_escopa_por_endereco_as_faixas_ja_vistas() -> None:
    """A rota que dispensa o nome cobre exatamente o que a casa já viu.

    A outra rota da regra é por `HID_NAME`, e quem separa genuíno de clone ali é
    o helper. Cobrada em `tests/unit/test_o_no_sniff_alcanca_todo_pro.py`.
    """
    texto_regra = REGRA_NOSNIFF.read_text(encoding="utf-8")
    prefixos = {
        _oui_colada(m)
        for m in re.findall(r'ENV\{HID_UNIQ\}=="([0-9A-Fa-f:]+):\*"', texto_regra)
    }
    assert prefixos == set(OUIS_NINTENDO_VISTAS), (
        f"a regra udev 82 escopa {sorted(prefixos)} por endereço e o produto já "
        f"viu {sorted(OUIS_NINTENDO_VISTAS)} — a rota que não depende do nome "
        "tem de cobrir exatamente essas"
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
