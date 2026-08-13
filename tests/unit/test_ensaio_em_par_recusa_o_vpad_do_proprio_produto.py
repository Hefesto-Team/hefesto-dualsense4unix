"""VPAD-NO-ESPELHO-01 — o `ensaio_rumble_em_par.py` mirava no vpad do Hefesto.

O DEFEITO, MEDIDO NA MESA DE 12/08/2026 COM QUATRO CONTROLES
------------------------------------------------------------
O docstring do instrumento promete, desde que ele nasceu: *"Ele RECUSA mirar no
que não for DualSense físico: os espelhos `Microsoft X-Box 360 pad` (28de:11ff,
Valve) e os gamepads virtuais têm FF e aceitariam o efeito sem que aparelho
nenhum vibrasse."*

Ele não recusava os gamepads virtuais do PRÓPRIO produto. Saída literal do
`--listar`, com quatro DualSense na mesa (dois no cabo, dois no rádio) e os
quatro vpads do co-op de pé — a coluna do nome vem cortada em `…` só para caber
na largura desta casa, o resto é byte por byte o que a mesa imprimiu::

    no                  transporte jogador vid:pid    mirar?   nome
    /dev/input/event21  cabo       P1      054c:0df2  SIM      DualSense … (Hefesto P1)
    /dev/input/event29  cabo       P4      054c:0ce6  SIM      Sony Interactive … Controller
    /dev/input/event257 cabo       P3      054c:0ce6  SIM      Sony Interactive … Controller
    /dev/input/event261 cabo       P4      054c:0df2  SIM      DualSense … (Hefesto P2)
    /dev/input/event265 radio      P2      054c:0ce6  SIM      DualSense Wireless Controller
    /dev/input/event268 cabo       P1      054c:0df2  SIM      DualSense … (Hefesto P3)
    /dev/input/event272 radio      P1      054c:0ce6  SIM      DualSense Wireless Controller
    /dev/input/event275 cabo       P3      054c:0df2  SIM      DualSense … (Hefesto P4)
    /dev/input/event279 virtual    —       054c:0df2  NAO      Sony … Edge Wireless Controller

Nove nós marcados `SIM` para quatro aparelhos: os quatro `(Hefesto Pn)` são os
vpads, e ainda por cima rotulados como transporte `cabo`.

A CADEIA CAUSAL
---------------
A régua era::

    eh_fisico = (
        vid == DUALSENSE_VID
        and pid in DUALSENSE_PIDS
        and barramento in TRANSPORTE_POR_BARRAMENTO
    )

e o vpad passa nos três, porque ele foi construído para passar:

1. `vid == 054c` — o `_create2_event` manda `DUALSENSE_VENDOR`;
2. `pid == 0df2` — o vpad se apresenta como DualSense **Edge** de propósito
   (`VPAD_PRODUCT`), para o `IGNORE_DEVICES` do SDL esconder só o físico; e
   `0x0DF2` está em `DUALSENSE_PIDS` porque o Edge REAL existe;
3. `barramento == 0003` — o `_create2_event` declara `BUS_USB`.

Quem escapava era só o `event279`, gamepad de uinput puro, que não tem `HID_ID`
nenhum. Não foi a régua que o pegou: foi a ausência de dado.

O QUE ESTES TESTES PROTEGEM DOS DOIS LADOS
------------------------------------------
A cura óbvia e ERRADA seria recusar o que mora sob `/devices/virtual/`. Ela
reintroduz a armadilha paga em 11/08/2026: com BlueZ ≥ 5.73 o bluetoothd cria o
HID dos controles BLUETOOTH FÍSICOS via `/dev/uhid`, no mesmíssimo lugar em que
mora o nosso vpad — recusar "virtual" recusaria metade da mesa, justo os dois do
rádio, que são o ensaio. Por isso há teste dos DOIS lados: o vpad recusado E o
controle de rádio aceito.

A régua nova pergunta de quem é o device antes de perguntar o que ele diz ser, e
usa as marcas que o PRODUTO carimba de propósito no `UHID_CREATE2` — `HID_PHYS =
hefesto-vpad` e o MAC forjado `02:fe:…`, que o kernel republica no `uevent` do
device HID pai. Nome entra só como segunda rede (e este mesmo nome já mudou uma
vez, no BT-E-VPAD-01).

PROVA DE QUE MORDE (arrancar, ver reprovar, devolver) — 12/08/2026
------------------------------------------------------------------
Arrancada a cura do `scripts/ensaio_rumble_em_par.py` (o `not eh_vpad` do
`eh_fisico` e o ramo `vpad` do rótulo de transporte, isto é, a régua velha de
volta), os cinco testes de identidade reprovaram e os de regressão (rádio
aceito, cabo aceito, uinput/Steam recusados) seguiram verdes — que é
exatamente o desenho pedido. A saída literal está no relatório da leva.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INSTRUMENTO = RAIZ / "scripts" / "ensaio_rumble_em_par.py"


@pytest.fixture(scope="module")
def ensaio():
    """O instrumento carregado como módulo (ele não é pacote instalável)."""
    spec = importlib.util.spec_from_file_location("ensaio_rumble_em_par", INSTRUMENTO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["ensaio_rumble_em_par"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


# --- a mesa de mentira -----------------------------------------------------
#
# Nada aqui toca hardware: monta-se em `tmp_path` a MESMA forma que o sysfs
# tem, com os símbolos que o instrumento de fato segue —
#
#   class/input/eventN            -> devices/<...>/input/inputN/eventN
#   devices/<...>/input/inputN/eventN/device -> ..
#
# — para que `_hid_pai` suba os mesmos degraus que sobe na máquina viva. Um
# teste que só trocasse o retorno de `inventario` não mediria a régua: mediria
# o mock.
#
# Os MACs são sintéticos e obedecem ao `scripts/check_test_data.sh`: os físicos
# na faixa de documentação `aa:bb:cc:…`, e os do vpad no `02:fe:…` que o próprio
# produto forja.

FF_PRESENTE = "107030000 0"


def _monta_no(
    base: Path,
    *,
    evento: int,
    sob: str,
    nome: str,
    vid: str = "054c",
    pid: str = "0ce6",
    barramento: str = "0003",
    uniq: str = "",
    hid_phys: str | None = None,
    hid_uniq: str | None = None,
    com_hid: bool = True,
    ff: str = FF_PRESENTE,
) -> str:
    """Cria um nó de entrada de mentira; devolve o caminho `/dev/input/eventN`."""
    hid_id = f"{barramento}:{vid.upper():0>8}:{pid.upper():0>8}"
    if com_hid:
        dir_hid = base / "devices" / sob / f"{hid_id}.{evento:04d}"
        dir_input = dir_hid / "input" / f"input{evento}"
    else:
        dir_hid = None
        dir_input = base / "devices" / sob / f"input{evento}"

    (dir_input / "id").mkdir(parents=True, exist_ok=True)
    (dir_input / "capabilities").mkdir(parents=True, exist_ok=True)
    (dir_input / "name").write_text(f"{nome}\n", encoding="utf-8")
    (dir_input / "uniq").write_text(f"{uniq}\n", encoding="utf-8")
    (dir_input / "phys").write_text("\n", encoding="utf-8")
    (dir_input / "id" / "vendor").write_text(f"{vid}\n", encoding="utf-8")
    (dir_input / "id" / "product").write_text(f"{pid}\n", encoding="utf-8")
    (dir_input / "capabilities" / "ff").write_text(f"{ff}\n", encoding="utf-8")

    if dir_hid is not None:
        linhas = ["DRIVER=playstation", f"HID_ID={hid_id}", f"HID_NAME={nome}"]
        if hid_phys is not None:
            linhas.append(f"HID_PHYS={hid_phys}")
        if hid_uniq is not None:
            linhas.append(f"HID_UNIQ={hid_uniq}")
        (dir_hid / "uevent").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    dir_evento = dir_input / f"event{evento}"
    dir_evento.mkdir(parents=True, exist_ok=True)
    (dir_evento / "device").symlink_to("..")

    raiz = base / "class" / "input"
    raiz.mkdir(parents=True, exist_ok=True)
    (raiz / f"event{evento}").symlink_to(dir_evento)
    return f"/dev/input/event{evento}"


def _vpad(base: Path, *, evento: int, jogador: int) -> str:
    """Um vpad do Hefesto, como o `uhid_gamepad` de fato o cria."""
    return _monta_no(
        base,
        evento=evento,
        sob="virtual/misc/uhid",
        nome=f"DualSense Wireless Controller (Hefesto P{jogador})",
        pid="0df2",
        barramento="0003",
        uniq=f"02:fe:00:00:00:{jogador:02x}",
        hid_phys="hefesto-vpad",
        hid_uniq=f"02:fe:00:00:00:{jogador:02x}",
    )


def _fisico_no_radio(base: Path, *, evento: int, mac: str) -> str:
    """Um DualSense de rádio: mora sob `/devices/virtual/misc/uhid/` (BlueZ)."""
    return _monta_no(
        base,
        evento=evento,
        sob="virtual/misc/uhid",
        nome="DualSense Wireless Controller",
        pid="0ce6",
        barramento="0005",
        uniq=mac,
        hid_phys="aa:bb:cc:00:00:ad",
        hid_uniq=mac,
    )


def _fisico_no_cabo(base: Path, *, evento: int, mac: str) -> str:
    return _monta_no(
        base,
        evento=evento,
        sob="pci0000:00/0000:00:08.1/usb3/3-3/3-3:1.3",
        nome="Sony Interactive Entertainment DualSense Wireless Controller",
        pid="0ce6",
        barramento="0003",
        uniq=mac,
        hid_phys="usb-0000:0c:00.3-3/input3",
        hid_uniq=mac,
    )


def _por_no(itens: list[dict], caminho: str) -> dict:
    achado = next((i for i in itens if i["no"] == caminho), None)
    assert achado is not None, f"{caminho} sumiu do inventário: {itens}"
    return achado


# --- (a) o vpad é RECUSADO -------------------------------------------------


def test_o_vpad_do_hefesto_nao_e_alvo_mesmo_forjando_054c_0df2_no_cabo(
    ensaio, tmp_path
):
    """A régua velha dizia SIM aos quatro vpads da mesa. Este é o defeito."""
    no = _vpad(tmp_path, evento=21, jogador=1)
    itens = ensaio.inventario(raiz=str(tmp_path / "class" / "input"))

    item = _por_no(itens, no)
    assert item["vid_pid"] == "054c:0df2", "a mesa de mentira tem de forjar o Edge"
    assert item["vpad_do_hefesto"] is True
    assert item["dualsense_fisico"] is False, (
        "o vpad passa em vid/pid/barramento porque foi feito para passar — "
        "quem o separa é a marca que o produto carimba, não o que ele diz ser"
    )


def test_o_transporte_do_vpad_nao_e_cabo_porque_nao_ha_aparelho_do_outro_lado(
    ensaio, tmp_path
):
    """`cabo` responde "por onde o report viaja ATÉ o aparelho" — e não há um."""
    no = _vpad(tmp_path, evento=261, jogador=2)
    item = _por_no(ensaio.inventario(raiz=str(tmp_path / "class" / "input")), no)
    assert item["transporte"] == "vpad", (
        "o 0003 do vpad é parte do disfarce; imprimi-lo como `cabo` repete o "
        "disfarce para quem está lendo a mesa"
    )


def test_disparar_no_vpad_e_recusado_antes_de_qualquer_efeito_subir(ensaio, tmp_path):
    """A recusa tem de acontecer no `_abrir`, não só no rótulo do `--listar`."""
    no = _vpad(tmp_path, evento=268, jogador=3)
    itens = ensaio.inventario(raiz=str(tmp_path / "class" / "input"))

    with pytest.raises(SystemExit) as erro:
        ensaio._abrir(no, itens)
    assert "RECUSO mirar" in str(erro.value)
    assert "VIRTUAL do próprio Hefesto" in str(erro.value)


def test_o_vpad_e_pego_pelo_uniq_do_no_quando_o_uevent_do_pai_nao_traz_as_marcas(
    ensaio, tmp_path
):
    """Segunda via da MESMA marca: o `hid_playstation` copia `hdev->uniq` para o
    `input_dev` (hid-playstation.c:704), então o MAC forjado aparece também no
    `uniq` do nó de entrada. Um `uevent` de pai ilegível não pode devolver o
    vpad para a lista de alvos."""
    no = _monta_no(
        tmp_path,
        evento=275,
        sob="virtual/misc/uhid",
        nome="DualSense Wireless Controller",  # sem a marca humana no nome
        pid="0df2",
        barramento="0003",
        uniq="02:fe:00:00:00:04",
        hid_phys=None,
        hid_uniq=None,
    )
    item = _por_no(ensaio.inventario(raiz=str(tmp_path / "class" / "input")), no)
    assert item["vpad_do_hefesto"] is True
    assert item["dualsense_fisico"] is False


def test_o_nome_e_a_segunda_rede_e_nao_a_regua(ensaio, tmp_path):
    """Sem NENHUMA marca de endereço, o nome ainda salva. É rede, não régua:
    quem responde nos casos de cima é o `HID_PHYS`/`HID_UNIQ`."""
    no = _monta_no(
        tmp_path,
        evento=99,
        sob="virtual/misc/uhid",
        nome="DualSense Wireless Controller (Hefesto P1)",
        pid="0df2",
        barramento="0003",
        uniq="",
        hid_phys=None,
        hid_uniq=None,
    )
    item = _por_no(ensaio.inventario(raiz=str(tmp_path / "class" / "input")), no)
    assert item["vpad_do_hefesto"] is True
    assert item["dualsense_fisico"] is False


# --- (b) o rádio continua ACEITO: o que separa cura de contorno -------------


def test_o_dualsense_do_radio_continua_alvo_mesmo_morando_em_devices_virtual(
    ensaio, tmp_path
):
    """A ARMADILHA de 11/08/2026, virada teste.

    Com BlueZ ≥ 5.73 o bluetoothd cria o HID do controle FÍSICO por `/dev/uhid`,
    sob `/sys/devices/virtual/misc/uhid/` — o mesmo lugar do nosso vpad. Se a
    cura do vpad recusar este nó, ela virou "recusa tudo que é uhid" e derrubou
    metade da mesa, que é justamente o ensaio.
    """
    no = _fisico_no_radio(tmp_path, evento=265, mac="aa:bb:cc:00:00:65")
    item = _por_no(ensaio.inventario(raiz=str(tmp_path / "class" / "input")), no)

    assert item["vpad_do_hefesto"] is False
    assert item["dualsense_fisico"] is True, (
        "recusar o controle do rádio é reintroduzir a armadilha paga em 11/08"
    )
    assert item["transporte"] == "radio"


def test_o_dualsense_do_cabo_continua_alvo(ensaio, tmp_path):
    no = _fisico_no_cabo(tmp_path, evento=29, mac="aa:bb:cc:00:00:29")
    item = _por_no(ensaio.inventario(raiz=str(tmp_path / "class" / "input")), no)
    assert item["dualsense_fisico"] is True
    assert item["transporte"] == "cabo"


# --- as recusas que JÁ funcionavam continuam funcionando --------------------


def test_o_gamepad_de_uinput_puro_segue_recusado(ensaio, tmp_path):
    """O `event279` da mesa: sem `HID_ID`, e por isso nunca foi alvo."""
    no = _monta_no(
        tmp_path,
        evento=279,
        sob="virtual/input",
        nome="Sony Interactive Entertainment DualSense Edge Wireless Controller",
        pid="0df2",
        com_hid=False,
    )
    item = _por_no(ensaio.inventario(raiz=str(tmp_path / "class" / "input")), no)
    assert item["dualsense_fisico"] is False
    assert item["transporte"] == "virtual"


def test_o_espelho_da_steam_segue_recusado_e_com_o_rotulo_dele(ensaio, tmp_path):
    no = _monta_no(
        tmp_path,
        evento=300,
        sob="virtual/input",
        nome="Microsoft X-Box 360 pad 0",
        vid="28de",
        pid="11ff",
        com_hid=False,
    )
    item = _por_no(ensaio.inventario(raiz=str(tmp_path / "class" / "input")), no)
    assert item["espelho_da_steam"] is True
    assert item["dualsense_fisico"] is False


# --- a mesa inteira, como ela estava em 12/08 ------------------------------


def test_na_mesa_de_quatro_controles_so_os_quatro_fisicos_sao_alvo(ensaio, tmp_path):
    """A contagem é o resumo do defeito: eram NOVE `SIM` para quatro aparelhos."""
    vpads = [_vpad(tmp_path, evento=20 + n, jogador=n) for n in (1, 2, 3, 4)]
    fisicos = [
        _fisico_no_cabo(tmp_path, evento=29, mac="aa:bb:cc:00:00:29"),
        _fisico_no_cabo(tmp_path, evento=257, mac="aa:bb:cc:00:00:57"),
        _fisico_no_radio(tmp_path, evento=265, mac="aa:bb:cc:00:00:65"),
        _fisico_no_radio(tmp_path, evento=272, mac="aa:bb:cc:00:00:72"),
    ]
    outro = _monta_no(
        tmp_path,
        evento=279,
        sob="virtual/input",
        nome="Sony Interactive Entertainment DualSense Edge Wireless Controller",
        pid="0df2",
        com_hid=False,
    )

    itens = ensaio.inventario(raiz=str(tmp_path / "class" / "input"))
    alvos = {str(i["no"]) for i in itens if i["dualsense_fisico"]}

    assert alvos == set(fisicos), (
        "um alvo por APARELHO de verdade — nem um vpad a mais, nem um controle "
        "de rádio a menos"
    )
    assert not (alvos & set(vpads))
    assert outro not in alvos


def test_o_listar_carimba_nao_vpad_no_veredito(ensaio, tmp_path, capsys):
    """O rótulo tem de dizer POR QUE recusou — `NAO` seco mandaria caçar udev."""
    _vpad(tmp_path, evento=21, jogador=1)
    ensaio.imprimir_inventario(
        ensaio.inventario(raiz=str(tmp_path / "class" / "input"))
    )
    saida = capsys.readouterr().out
    assert "NAO/vpad" in saida
    assert " cabo " not in saida


# --- o contrato com o produto, travado nas DUAS pontas ---------------------


def test_as_marcas_do_instrumento_sao_as_que_o_produto_de_fato_carimba():
    """As constantes `VPAD_*` do instrumento são contrato de fio replicado — se
    o `uhid_gamepad` mudar o `phys` ou o MAC forjado, este teste cai junto e
    ninguém descobre pelo instrumento voltando a mirar no vpad."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        UhidDualSense,
        player_mac,
    )

    spec = importlib.util.spec_from_file_location(
        "ensaio_rumble_em_par_contrato", INSTRUMENTO
    )
    assert spec is not None and spec.loader is not None
    instrumento = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instrumento)

    for jogador in (1, 2, 3, 4):
        assert player_mac(jogador).startswith(instrumento.VPAD_UNIQ_PREFIXO)

    evento = UhidDualSense(player=1)._create2_event(b"\x00")
    assert instrumento.VPAD_HID_PHYS.encode("ascii") in evento, (
        "o `phys` do UHID_CREATE2 é a marca mais forte do vpad — mudou lá, "
        "tem de mudar aqui"
    )
    assert player_mac(1).encode("ascii") in evento
    assert instrumento.VPAD_MARCA_NO_NOME in UhidDualSense(player=1).name
