"""VPAD-NO-ESPELHO-01/B — a imunidade por coincidência dos outros dois ensaios.

O QUE ESTES TESTES DESARMAM
---------------------------
`scripts/ensaio_rumble_um_bit_por_vez.py` (`achar_fisico`) e
`scripts/ensaio_o_keepalive_mata_o_rumble.py` (`inventario`) **nunca** miraram
no vpad do próprio produto. Mas não por régua: por acidente aritmético.

Os dois só aceitam o PID `0CE6`::

    ensaio_rumble_um_bit_por_vez.py:110   PID_DUALSENSE = "00000CE6"
    ensaio_o_keepalive_mata_o_rumble.py   DUALSENSE = (0x054C, 0x0CE6)

e o vpad se apresenta como `0DF2` — DualSense **Edge** — porque é assim que ele
some do `IGNORE_DEVICES` do SDL sem levar o físico junto
(`integrations/uhid_gamepad.py`, `VPAD_PRODUCT`).

O pino já está frouxo: **o Edge REAL existe**, o terceiro instrumento da mesma
bancada já aceita os dois PIDs (`ensaio_rumble_em_par.DUALSENSE_PIDS =
(0x0CE6, 0x0DF2)`), e "fazer os três concordarem" é uma limpeza que qualquer um
faria de boa-fé numa tarde. No dia em que alguém acrescentar `0x0DF2` aqui, sem
a régua os dois passam a aceitar o vpad — que tem força-feedback e engole o
efeito calado, sem que motor nenhum gire. A medição sairia **falsa sem avisar**,
que é a pior categoria de defeito de instrumento desta casa.

Por isso o desenho destes testes: eles abrem o filtro de PID de propósito
(`monkeypatch` no PID, exatamente a mudança que a pessoa faria) e exigem que a
recusa continue de pé. É a rede que desarma a bomba antes de ela ser armada — e
o teste continua valendo mesmo depois de alguém armá-la.

E DOS DOIS LADOS
----------------
A cura errada e óbvia seria recusar tudo que mora sob `/devices/virtual/`. Ela
reintroduz a armadilha paga em 11/08/2026: com BlueZ ≥ 5.73 o bluetoothd cria o
HID dos controles Bluetooth FÍSICOS por `/dev/uhid`, no mesmíssimo lugar do
nosso vpad. Por isso cada arquivo tem também o teste do controle de rádio
continuando ACEITO.

PROVA DE QUE MORDE (arrancar, ver reprovar, devolver) — 12/08/2026
-------------------------------------------------------------------
Arrancada a linha `if identidade_do_vpad.e_vpad_do_hefesto(...): continue` de
`achar_fisico` e de `inventario`, os quatro testes de recusa reprovaram e os de
regressão (rádio e cabo aceitos) seguiram verdes. A saída literal está no
relatório da leva.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
UM_BIT = RAIZ / "scripts" / "ensaio_rumble_um_bit_por_vez.py"
KEEPALIVE = RAIZ / "scripts" / "ensaio_o_keepalive_mata_o_rumble.py"

#: `capabilities/ff` de um nó COM força-feedback, como o sysfs a escreve.
FF_PRESENTE = "107030000 0"


def _carrega(caminho: Path, apelido: str):
    spec = importlib.util.spec_from_file_location(apelido, caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[apelido] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def um_bit():
    return _carrega(UM_BIT, "ensaio_rumble_um_bit_por_vez")


@pytest.fixture(scope="module")
def keepalive():
    return _carrega(KEEPALIVE, "ensaio_o_keepalive_mata_o_rumble")


# ---------------------------------------------------------------------------
# As mesas de mentira. Nada aqui toca hardware: monta-se em `tmp_path` a MESMA
# forma que cada instrumento percorre no sysfs, para que a régua sob teste seja
# a do instrumento e não a do mock.
#
# Os MACs são sintéticos e obedecem ao `scripts/check_test_data.sh`: os físicos
# na faixa de documentação `aa:bb:cc:…` com os octetos 4 e 5 zerados, e os do
# vpad no `02:fe:…` que o próprio produto forja.
# ---------------------------------------------------------------------------


def _uevent(*, barramento: str, pid: str, nome: str, phys: str, uniq: str) -> str:
    return (
        "DRIVER=playstation\n"
        f"HID_ID={barramento}:0000054C:{pid.upper():0>8}\n"
        f"HID_NAME={nome}\n"
        f"HID_PHYS={phys}\n"
        f"HID_UNIQ={uniq}\n"
    )


def _mesa_hidraw(base: Path, *, indice: int, uevent: str) -> Path:
    """A forma que o `achar_fisico` percorre: `<raiz>/hidrawN/device/uevent`."""
    dir_device = base / f"hidraw{indice}" / "device"
    dir_device.mkdir(parents=True, exist_ok=True)
    (dir_device / "uevent").write_text(uevent, encoding="utf-8")
    return base / f"hidraw{indice}"


def _mesa_hid(base: Path, *, indice: int, uevent: str, ff: str = FF_PRESENTE) -> Path:
    """A forma que o `inventario` percorre: `<raiz>/<hid>/{uevent,hidraw,input}`."""
    dir_hid = base / f"0003:054C:0DF2.{indice:04d}"
    (dir_hid / "hidraw").mkdir(parents=True, exist_ok=True)
    (dir_hid / "hidraw" / f"hidraw{indice}").mkdir(exist_ok=True)
    (dir_hid / "uevent").write_text(uevent, encoding="utf-8")
    dir_input = dir_hid / "input" / f"input{indice}"
    (dir_input / "capabilities").mkdir(parents=True, exist_ok=True)
    (dir_input / "capabilities" / "ff").write_text(f"{ff}\n", encoding="utf-8")
    (dir_input / f"event{indice}").mkdir(exist_ok=True)
    return dir_hid


UEVENT_VPAD = _uevent(
    barramento="0003",
    pid="0df2",
    nome="DualSense Wireless Controller (Hefesto P1)",
    phys="hefesto-vpad",
    uniq="02:fe:00:00:00:01",
)
UEVENT_RADIO = _uevent(
    barramento="0005",
    pid="0ce6",
    nome="DualSense Wireless Controller",
    phys="aa:bb:cc:00:00:11",  # MAC do adaptador
    uniq="aa:bb:cc:00:00:65",  # MAC do controle
)
UEVENT_CABO = _uevent(
    barramento="0003",
    pid="0ce6",
    nome="Sony Interactive Entertainment DualSense Wireless Controller",
    phys="usb-0000:0c:00.3-3/input3",
    uniq="aa:bb:cc:00:00:29",
)


# === ensaio_rumble_um_bit_por_vez.achar_fisico =============================


def test_um_bit_recusa_o_vpad_quando_alguem_acrescenta_o_pid_do_edge(
    um_bit, tmp_path, monkeypatch
):
    """A BOMBA, armada de propósito: o filtro de PID passa a aceitar `0DF2`.

    É literalmente a mudança que alguém faria para "fazer os três instrumentos
    concordarem" — e é ela que transformaria o vpad em alvo. Com a régua no
    lugar, o instrumento devolve None: nenhum aparelho para medir, que é a
    resposta CERTA quando só há vpad na mesa.
    """
    monkeypatch.setattr(um_bit, "PID_DUALSENSE", "00000DF2")
    _mesa_hidraw(tmp_path, indice=7, uevent=UEVENT_VPAD)

    assert um_bit.achar_fisico(raiz=str(tmp_path)) is None, (
        "com o PID do Edge aceito, o vpad do próprio produto virou alvo — ele "
        "engole o efeito calado e a medição sai falsa sem avisar"
    )


def test_um_bit_nao_pega_o_vpad_nem_quando_ele_vem_antes_do_fisico(
    um_bit, tmp_path, monkeypatch
):
    """O instrumento pega o PRIMEIRO que encontra, em ordem alfabética de nó.

    Este é o caso que o "pega o primeiro" torna venenoso: `hidraw2` (o vpad)
    vem antes de `hidraw9` (o controle de verdade). Sem a régua, o ensaio
    inteiro mediria o vpad e imprimiria `cabo` com toda a confiança.
    """
    monkeypatch.setattr(um_bit, "PID_DUALSENSE", "00000DF2")
    _mesa_hidraw(tmp_path, indice=2, uevent=UEVENT_VPAD)
    _mesa_hidraw(
        tmp_path,
        indice=9,
        uevent=_uevent(
            barramento="0005",
            pid="0df2",
            nome="Sony Interactive Entertainment DualSense Edge Wireless Controller",
            phys="aa:bb:cc:00:00:11",
            uniq="aa:bb:cc:00:00:99",
        ),
    )

    achado = um_bit.achar_fisico(raiz=str(tmp_path))

    assert achado is not None
    assert achado.hidraw == "/dev/hidraw9", (
        "o vpad estava na frente na ordem dos nós e foi escolhido"
    )
    assert achado.transporte == "bluetooth"


def test_um_bit_continua_achando_o_controle_do_radio(um_bit, tmp_path):
    """A armadilha de 11/08 virada teste: a cura não pode ser "recusa uhid"."""
    _mesa_hidraw(tmp_path, indice=3, uevent=UEVENT_RADIO)

    achado = um_bit.achar_fisico(raiz=str(tmp_path))

    assert achado is not None, "recusar o rádio é recusar metade da mesa"
    assert achado.hidraw == "/dev/hidraw3"
    assert achado.transporte == "bluetooth"


def test_um_bit_continua_achando_o_controle_do_cabo(um_bit, tmp_path):
    _mesa_hidraw(tmp_path, indice=4, uevent=UEVENT_CABO)

    achado = um_bit.achar_fisico(raiz=str(tmp_path))

    assert achado is not None
    assert achado.transporte == "cabo"


# === ensaio_o_keepalive_mata_o_rumble.inventario ===========================


def test_keepalive_recusa_o_vpad_quando_alguem_acrescenta_o_pid_do_edge(
    keepalive, tmp_path, monkeypatch
):
    """A MESMA bomba, no segundo instrumento: `DUALSENSE` passa a ser o Edge."""
    monkeypatch.setattr(keepalive, "DUALSENSE", (0x054C, 0x0DF2))
    _mesa_hid(tmp_path, indice=5, uevent=UEVENT_VPAD)

    assert keepalive.inventario(raiz=str(tmp_path)) == [], (
        "o vpad entrou no inventário como se fosse aparelho — o ensaio mediria "
        "um motor que não existe"
    )


def test_keepalive_nao_lista_o_vpad_junto_dos_aparelhos_de_verdade(
    keepalive, tmp_path, monkeypatch
):
    """Com PID do Edge aceito e mesa mista, sobra exatamente o aparelho."""
    monkeypatch.setattr(keepalive, "DUALSENSE", (0x054C, 0x0DF2))
    _mesa_hid(tmp_path, indice=1, uevent=UEVENT_VPAD)
    _mesa_hid(
        tmp_path,
        indice=8,
        uevent=_uevent(
            barramento="0005",
            pid="0df2",
            nome="Sony Interactive Entertainment DualSense Edge Wireless Controller",
            phys="aa:bb:cc:00:00:11",
            uniq="aa:bb:cc:00:00:88",
        ),
    )

    achados = keepalive.inventario(raiz=str(tmp_path))

    assert [item["hidraw"] for item in achados] == ["/dev/hidraw8"]
    assert [item["transporte"] for item in achados] == ["radio"]


def test_keepalive_continua_listando_o_controle_do_radio(keepalive, tmp_path):
    """Dos dois lados: a cura do vpad não pode derrubar o controle de rádio."""
    _mesa_hid(tmp_path, indice=6, uevent=UEVENT_RADIO)

    achados = keepalive.inventario(raiz=str(tmp_path))

    assert len(achados) == 1, "recusar o rádio reintroduz a armadilha de 11/08"
    assert achados[0]["transporte"] == "radio"
    assert achados[0]["evdev"] == "/dev/input/event6"


def test_keepalive_continua_listando_o_controle_do_cabo(keepalive, tmp_path):
    _mesa_hid(tmp_path, indice=2, uevent=UEVENT_CABO)

    achados = keepalive.inventario(raiz=str(tmp_path))

    assert len(achados) == 1
    assert achados[0]["transporte"] == "cabo"


# === a régua é UMA, e é a mesma nos três ===================================


def test_os_tres_instrumentos_usam_a_mesma_regua_e_nao_copias_dela():
    """O defeito de origem era a régua escrita três vezes, com três respostas.

    Este teste não olha comportamento: olha a IDENTIDADE do objeto. Duas
    leituras do mesmo dado são duas réguas, e uma delas envelhece calada — se
    alguém recopiar a função para dentro de um instrumento "para não depender
    do módulo", é aqui que se descobre, e não numa medição falsa daqui a meses.
    """
    import identidade_do_vpad

    em_par = _carrega(
        RAIZ / "scripts" / "ensaio_rumble_em_par.py", "ensaio_rumble_em_par_regua"
    )
    um_bit = _carrega(UM_BIT, "um_bit_regua")
    keepalive = _carrega(KEEPALIVE, "keepalive_regua")

    for instrumento in (em_par, um_bit, keepalive):
        assert (
            instrumento.identidade_do_vpad.e_vpad_do_hefesto
            is identidade_do_vpad.e_vpad_do_hefesto
        ), f"{instrumento.__name__} não usa a régua comum"

    # E o `em_par`, que reexporta as constantes, reexporta as DE VERDADE.
    assert em_par.VPAD_HID_PHYS is identidade_do_vpad.VPAD_HID_PHYS
    assert em_par.VPAD_UNIQ_PREFIXO is identidade_do_vpad.VPAD_UNIQ_PREFIXO
    assert em_par.VPAD_MARCA_NO_NOME is identidade_do_vpad.VPAD_MARCA_NO_NOME


def test_a_regua_comum_casa_com_o_que_o_produto_de_fato_carimba():
    """Contrato de fio travado nas DUAS pontas, agora num lugar só.

    Se o `uhid_gamepad` mudar o `phys` ou o MAC forjado, este teste cai — e
    ninguém descobre pelos três instrumentos voltando a mirar no vpad ao mesmo
    tempo.
    """
    import identidade_do_vpad
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        UhidDualSense,
        player_mac,
    )

    for jogador in (1, 2, 3, 4):
        assert player_mac(jogador).startswith(identidade_do_vpad.VPAD_UNIQ_PREFIXO)

    evento = UhidDualSense(player=1)._create2_event(b"\x00")
    assert identidade_do_vpad.VPAD_HID_PHYS.encode("ascii") in evento
    assert player_mac(1).encode("ascii") in evento
    assert identidade_do_vpad.VPAD_MARCA_NO_NOME in UhidDualSense(player=1).name


def test_a_regua_nao_olha_vid_pid_nem_barramento():
    """O ponto todo: os três são exatamente o que o vpad forja BEM.

    Um `uevent` com o VID/PID/barramento de um DualSense de cabo perfeitamente
    legítimo, e as marcas do vpad, tem de ser vpad. E o contrário: as marcas de
    um aparelho de verdade com o PID do vpad tem de ser aparelho.
    """
    import identidade_do_vpad

    disfarce_perfeito = identidade_do_vpad.campos_do_uevent(
        _uevent(
            barramento="0003",
            pid="0ce6",  # o PID do DualSense comum, não o do Edge
            nome="Sony Interactive Entertainment DualSense Wireless Controller",
            phys="hefesto-vpad",
            uniq="02:fe:00:00:00:02",
        )
    )
    assert identidade_do_vpad.e_vpad_do_hefesto(disfarce_perfeito) is True

    edge_de_verdade = identidade_do_vpad.campos_do_uevent(
        _uevent(
            barramento="0003",
            pid="0df2",  # o PID que o vpad usa — e o Edge REAL também
            nome="Sony Interactive Entertainment DualSense Edge Wireless Controller",
            phys="usb-0000:0c:00.3-3/input3",
            uniq="aa:bb:cc:00:00:42",
        )
    )
    assert identidade_do_vpad.e_vpad_do_hefesto(edge_de_verdade) is False, (
        "o Edge de verdade existe e é alvo legítimo — recusá-lo seria trocar "
        "um defeito por outro"
    )


def test_sem_dado_nenhum_a_regua_nao_acusa_ninguem():
    """Conservadora ao contrário do `_is_virtual_evdev`, e de propósito.

    Lá, "na dúvida é virtual" protege o daemon de adotar a própria saída. Aqui,
    "na dúvida é vpad" recusaria mirar num aparelho de verdade e o ensaio não
    aconteceria — quem fecha o outro lado é o filtro de VID/PID/barramento de
    quem chama.
    """
    import identidade_do_vpad

    assert identidade_do_vpad.e_vpad_do_hefesto({}) is False
    assert identidade_do_vpad.ler_uevent("/nao/existe/uevent") == {}
    assert identidade_do_vpad.uniq_do_no_de_entrada("/nao/existe") == ""
