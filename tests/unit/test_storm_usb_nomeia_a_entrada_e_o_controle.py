"""O -71 diz a ENTRADA, o CONTROLE e o que ficou PARADO — STORM-USB-01, 24/09/2026.

A palavra dela de 23/09 é «nomear e religar»: *o doctor diz a entrada e o
controle de cada -71 dos últimos 7 dias*, e *o nome da entrada é o da seção do
rádio — não se inventa outro*. O laudo de 20/09 dizia o caminho do kernel
(`3-4.1.3`); estas réguas medem o que a palavra dela acrescentou. A lógica de
endereçamento (as formas da linha, o hub em comum, a janela) continua em
`tests/unit/test_o_endereco_do_storm_usb.py`, e a costura com o terminal em
`tests/unit/test_o_doctor_diz_a_porta_do_storm.py`.

O ``/sys`` DE MENTIRA É UMA ÁRVORE DE VERDADE no ``tmp_path``, lida pelos
leitores de verdade (``aparelho_da_porta``, ``mesa_de_radio.controladores_dos_
barramentos``, ``entrada_a_entrada.nome_da_porta``): nenhum dublê responde por
eles, e nada aqui olha o barramento de quem roda a suíte. Faixa sintética da
casa: o controlador ``0000:0a:00.0``.

AS MORDIDAS, uma por régua (arranque a cura, veja reprovar, devolva):

* :func:`test_o_nome_da_entrada_vem_do_dono` — faça :func:`_nomeador` devolver
  ``_sem_nome`` e a frase volta ao caminho cru: o nome que ela deu não chega.
* :func:`test_o_retrato_de_outra_maquina_nao_usa_os_nomes_dela` — troque o
  ``raiz_usb == RAIZ_USB`` por ``True`` e o nome desta máquina aparece no
  retrato de outra.
* :func:`test_o_adaptador_que_so_se_declara_na_interface` — tire o ramo da
  interface 0 de ``_e_adaptador`` e o adaptador composto vira "nada".
* :func:`test_o_controle_sem_hid_fica_parado` — tire o ``driver`` da conta em
  ``_hid_sem_driver`` e o controle de pé passa a ser acusado.
* :func:`test_a_interface_desligada_de_proposito_nao_e_o_71` — tire a guarda do
  ``authorized`` e a interface que alguém desligou vira queda.
* :func:`test_a_desistencia_no_mesmo_segundo_ganha` — troque o ``>=`` do
  carimbo por ``>`` e a desistência escrita no mesmo segundo das tentativas se
  perde.
* :func:`test_o_log_fora_de_ordem_nao_engana_o_desfecho` — troque o carimbo por
  "a última linha manda" e a tentativa antiga, escrita depois, apaga a
  desistência.
* :func:`test_o_hub_em_comum_diz_as_entradas_pelo_dono` (conferência de 24/09)
  — dê ao ``HubEmComum`` o caminho do kernel em vez do ``onde`` do hub, ou
  deixe as ``entradas`` de baixo vazias, e ela reprova. As duas mordidas
  passavam verdes antes dela.
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import exame_da_mesa as em
from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    DESFECHO_ENTRADA_LARGADA,
    DESFECHO_SEM_HID,
    aparelho_da_porta,
    storm_por_porta,
)
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

HOJE = datetime.date(2026, 9, 24)
PCI = "0000:0a:00.0"


def _linha(mensagem: str, *, quando: str = "2026-09-24T12:55:51") -> str:
    """Uma linha do `kernel.log` no formato que o `storm_watch.sh` escreve."""
    return f"{quando}-03:00 [USB-71] {mensagem}"


def _no(
    raiz: Path,
    porta: str,
    *,
    vid: str,
    pid: str,
    nome: str,
    tripla: tuple[str, str, str] = ("00", "00", "00"),
) -> None:
    """Um nó USB de mentira, com os campos que o exame lê."""
    no = raiz / porta
    no.mkdir(parents=True)
    for campo, valor in (
        ("idVendor", vid),
        ("idProduct", pid),
        ("product", nome),
        ("bDeviceClass", tripla[0]),
        ("bDeviceSubClass", tripla[1]),
        ("bDeviceProtocol", tripla[2]),
    ):
        (no / campo).write_text(valor + "\n", encoding="utf-8")


def _interface(
    raiz: Path,
    nome: str,
    *,
    tripla: tuple[str, str, str],
    driver: Path | None = None,
    authorized: str | None = None,
) -> None:
    """Uma interface de mentira (``3-4.4:1.3``), com ou sem ``driver``."""
    no = raiz / nome
    no.mkdir(parents=True)
    for campo, valor in zip(
        ("bInterfaceClass", "bInterfaceSubClass", "bInterfaceProtocol"),
        tripla,
        strict=True,
    ):
        (no / campo).write_text(valor + "\n", encoding="utf-8")
    if driver is not None:
        os.symlink(driver, no / "driver")
    if authorized is not None:
        (no / "authorized").write_text(authorized + "\n", encoding="utf-8")


def _dualsense(raiz: Path, porta: str, *, hid: str) -> None:
    """Um DualSense no cabo: áudio com driver, e a HID como ``hid`` mandar.

    ``hid`` é ``"com-driver"``, ``"sem-driver"`` ou ``"desligada"`` (o
    ``authorized`` em 0, a escolha de alguém).
    """
    _no(raiz, porta, vid="054c", pid="0ce6", nome="DualSense Wireless Controller")
    driver = raiz.parent / "drivers" / "qualquer"
    driver.mkdir(parents=True, exist_ok=True)
    _interface(raiz, f"{porta}:1.0", tripla=("01", "01", "00"), driver=driver)
    _interface(
        raiz,
        f"{porta}:1.3",
        tripla=("03", "00", "00"),
        driver=driver if hid == "com-driver" else None,
        authorized="0" if hid == "desligada" else None,
    )


def _raiz_com_controlador(tmp_path: Path) -> Path:
    """A lista ``bus/usb/devices`` com o hub-raiz ``usb3`` pendurado no ``PCI``.

    É o que ``controladores_dos_barramentos`` lê: um ``realpath`` por ``usbN``.
    Sem isso o caminho não vira lugar, e o nome dela não tem onde se prender.
    """
    raiz = tmp_path / "sys" / "bus" / "usb" / "devices"
    raiz.mkdir(parents=True)
    alvo = tmp_path / "sys" / "devices" / "pci0000:00" / PCI / "usb3"
    alvo.mkdir(parents=True)
    os.symlink(alvo, raiz / "usb3")
    return raiz


# --- o nome da entrada: do dono, e só dele -----------------------------------


def test_o_nome_da_entrada_vem_do_dono(tmp_path: Path) -> None:
    """O nome que ela deu ao lugar chega à frase, com o caminho do kernel junto."""
    raiz = _raiz_com_controlador(tmp_path)
    _dualsense(raiz, "3-4.1.3", hid="com-driver")
    lugar = f"pci-{PCI}-usb-0:4.1.3"
    maquina = MaquinaConfig.model_validate({"lugares": {lugar: {"nome": "Frente, a de baixo"}}})
    laudo = storm_por_porta(
        linhas=[_linha("usb 3-4.1.3: device descriptor read/all, error -71")],
        hoje=HOJE,
        raiz_usb=raiz,
        nomear=em._nomeador(raiz, maquina=maquina),
    )
    porque = laudo.portas[0].porque
    assert porque.startswith("Frente, a de baixo (3-4.1.3) — 1 evento"), porque
    # O hub do caminho não tem nome dela: sai com o que o desenho dá a qualquer um.
    assert "Entrada 4 (3-4)" in porque, porque


def test_sem_o_dono_a_frase_fica_com_o_caminho_do_kernel(tmp_path: Path) -> None:
    """O ``python3`` do sistema não carrega o dono: sobra o caminho, sem nome inventado."""
    raiz = tmp_path / "sys"
    _dualsense(raiz, "3-4.1.3", hid="com-driver")
    laudo = storm_por_porta(
        linhas=[_linha("usb 3-4.1.3: device descriptor read/all, error -71")],
        hoje=HOJE,
        raiz_usb=raiz,
        nomear=em._sem_nome,
    )
    assert laudo.portas[0].porque.startswith("3-4.1.3 — 1 evento"), laudo.portas[0].porque
    assert "Entrada" not in laudo.portas[0].porque.split(";")[0]


def test_o_retrato_de_outra_maquina_nao_usa_os_nomes_dela(tmp_path: Path) -> None:
    """Com a raiz de outro ``/sys``, o ``maquina.json`` DESTA máquina não vale.

    O suporte lê o retrato de quem pediu ajuda; os nomes que ela deu são das
    entradas DELA, e pôr «Frente, a de baixo» na entrada de outra pessoa seria
    um endereço convincente e falso.
    """
    from hefesto_dualsense4unix.utils.maquina import caminho_da_maquina, gravar_maquina

    assert str(caminho_da_maquina()).startswith(str(Path(os.environ["XDG_CONFIG_HOME"]))), (
        "o maquina.json desta régua tem de morar no lar de mentira"
    )
    raiz = _raiz_com_controlador(tmp_path)
    _dualsense(raiz, "3-4.1.3", hid="com-driver")
    lugar = f"pci-{PCI}-usb-0:4.1.3"
    assert gravar_maquina({"lugares": {lugar: {"nome": "Frente, a de baixo"}}})
    laudo = storm_por_porta(
        linhas=[_linha("usb 3-4.1.3: device descriptor read/all, error -71")],
        hoje=HOJE,
        raiz_usb=raiz,
    )
    porque = laudo.portas[0].porque
    assert "Frente, a de baixo" not in porque, porque
    assert porque.startswith("Entrada 4.1.3 (3-4.1.3)"), porque


# --- o controle, e a matriz: o cabo e o adaptador -----------------------------


def test_o_controle_no_cabo_se_diz_controle(tmp_path: Path) -> None:
    """Um aparelho da Sony na entrada é «um controle, pelo USB»."""
    raiz = tmp_path / "sys"
    _dualsense(raiz, "1-4", hid="com-driver")
    laudo = storm_por_porta(
        linhas=[_linha("usb 1-4: device descriptor read/all, error -71")],
        hoje=HOJE,
        raiz_usb=raiz,
        nomear=em._sem_nome,
    )
    assert "DualSense Wireless Controller (054c:0ce6) — um controle, pelo USB" in (
        laudo.portas[0].porque
    )


def test_o_adaptador_que_se_declara_no_aparelho(tmp_path: Path) -> None:
    """A tripla ``e0/01/01`` no descritor do aparelho — o UB500 da mesa dela."""
    raiz = tmp_path / "sys"
    _no(raiz, "1-4", vid="2357", pid="0604", nome="TP-Link UB500 Adapter",
        tripla=("e0", "01", "01"))
    laudo = storm_por_porta(
        linhas=[_linha("usb 1-4: device descriptor read/all, error -71")],
        hoje=HOJE,
        raiz_usb=raiz,
        nomear=em._sem_nome,
    )
    assert "um adaptador BT: quando ele cai, caem todos os controles dele" in (
        laudo.portas[0].porque
    )


def test_o_adaptador_que_so_se_declara_na_interface(tmp_path: Path) -> None:
    """O adaptador composto (``ef`` no aparelho) só se diz na interface 0."""
    raiz = tmp_path / "sys"
    _no(raiz, "3-4.4", vid="0bda", pid="8771", nome="Bluetooth Radio",
        tripla=("ef", "02", "01"))
    _interface(raiz, "3-4.4:1.0", tripla=("e0", "01", "01"))
    aparelho = aparelho_da_porta("3-4.4", raiz_usb=raiz)
    assert aparelho.e_adaptador is True
    assert aparelho.papel.startswith("um adaptador BT")


def test_um_teclado_nao_ganha_papel(tmp_path: Path) -> None:
    """Quem não é controle nem adaptador sai só com a identidade."""
    raiz = tmp_path / "sys"
    _no(raiz, "3-4.1.2", vid="258a", pid="010c", nome="Gaming Keyboard")
    _interface(raiz, "3-4.1.2:1.0", tripla=("03", "01", "01"))
    aparelho = aparelho_da_porta("3-4.1.2", raiz_usb=raiz)
    assert aparelho.papel == ""
    assert aparelho.hid_sem_driver is False, "a HID sem driver só conta num controle"


def test_hub_de_uma_porta_nao_casa_as_interfaces_do_vizinho(tmp_path: Path) -> None:
    """``3-4:*`` não casa ``3-4.1:1.0`` — a interface do vizinho não é dele."""
    raiz = tmp_path / "sys"
    _no(raiz, "3-4", vid="054c", pid="0ce6", nome="DualSense")
    _interface(raiz, "3-4.1:1.3", tripla=("03", "00", "00"))
    assert aparelho_da_porta("3-4", raiz_usb=raiz).hid_sem_driver is False


def test_o_hub_em_comum_diz_as_entradas_pelo_dono(tmp_path: Path) -> None:
    """O fator comum sai com o nome do hub e o das entradas de baixo, pelo dono.

    A pergunta 1 da sprint é «é a porta, o cabo ou o hub?», e a resposta que a
    topologia dá — o hub no caminho de duas entradas — tem de falar a mesma
    língua das linhas de cima: quem leu «Frente (3-4.1.3)» numa linha não pode
    ler só «3-4.1.3» na outra.
    """
    nomes = {"3-4": "Entrada 4", "3-4.1.3": "Frente", "3-4.4": "Atrás"}
    laudo = storm_por_porta(
        linhas=[
            _linha("usb 3-4.1.3: device descriptor read/all, error -71"),
            _linha("usb 3-4.4: device descriptor read/64, error -71"),
        ],
        hoje=HOJE,
        raiz_usb=tmp_path / "sys",
        nomear=nomes.get,
    )
    assert len(laudo.hubs_em_comum) == 1, laudo.hubs_em_comum
    porque = laudo.hubs_em_comum[0].porque
    assert porque.startswith(
        "o hub em Entrada 4 (3-4) está no caminho de 2 entradas que deram -71 "
        "(Frente (3-4.1.3), Atrás (3-4.4))"
    ), porque


# --- o que ficou parado --------------------------------------------------------


def test_o_controle_sem_hid_fica_parado(tmp_path: Path) -> None:
    """O controle encaixado sem driver na HID: o jogo não o vê, e a linha diz."""
    raiz = tmp_path / "sys"
    _dualsense(raiz, "3-4.4", hid="sem-driver")
    laudo = storm_por_porta(
        linhas=[_linha("usbhid 3-4.4:1.3: can't add hid device: -71")],
        hoje=HOJE,
        raiz_usb=raiz,
        nomear=em._sem_nome,
    )
    porta = laudo.portas[0]
    assert porta.desfecho == DESFECHO_SEM_HID
    assert porta.parada == "o controle está nela sem o HID, e o jogo não o vê"


def test_o_controle_que_voltou_com_hid_nao_fica_parado(tmp_path: Path) -> None:
    """Mesmo log, mas a HID tem driver AGORA: voltou (ou ela repôs), e nada parou."""
    raiz = tmp_path / "sys"
    _dualsense(raiz, "3-4.4", hid="com-driver")
    laudo = storm_por_porta(
        linhas=[_linha("usbhid 3-4.4:1.3: can't add hid device: -71")],
        hoje=HOJE,
        raiz_usb=raiz,
        nomear=em._sem_nome,
    )
    assert laudo.portas[0].parada == ""


def test_a_interface_desligada_de_proposito_nao_e_o_71(tmp_path: Path) -> None:
    """``authorized`` em 0 é escolha de alguém — não é o kernel desistindo."""
    raiz = tmp_path / "sys"
    _dualsense(raiz, "3-4.4", hid="desligada")
    assert aparelho_da_porta("3-4.4", raiz_usb=raiz).hid_sem_driver is False


def test_a_entrada_largada_vazia_fica_parada(tmp_path: Path) -> None:
    """``unable to enumerate``: o kernel largou a entrada, e ela segue vazia."""
    laudo = storm_por_porta(
        linhas=[
            _linha("usb 3-4.4: device not accepting address 10, error -71"),
            _linha("usb 3-4-port4: unable to enumerate USB device"),
        ],
        hoje=HOJE,
        raiz_usb=tmp_path / "sys",
        nomear=em._sem_nome,
    )
    porta = laudo.portas[0]
    assert porta.porta == "3-4.4"
    assert porta.desfecho == DESFECHO_ENTRADA_LARGADA
    assert porta.parada == "o kernel desistiu dela no -71, e ela segue vazia"


def test_a_entrada_largada_que_voltou_a_ter_aparelho_nao_fica_parada(tmp_path: Path) -> None:
    """Largada no log, com aparelho AGORA: alguém encaixou de novo, e nada parou."""
    raiz = tmp_path / "sys"
    _dualsense(raiz, "3-4.4", hid="com-driver")
    laudo = storm_por_porta(
        linhas=[_linha("usb 3-4-port4: unable to enumerate USB device")],
        hoje=HOJE,
        raiz_usb=raiz,
        nomear=em._sem_nome,
    )
    assert laudo.portas[0].parada == ""


def test_entrada_vazia_sem_a_desistencia_nao_e_parada(tmp_path: Path) -> None:
    """Vazia depois de um -71 que o kernel seguiu tentando: pode ter sido a mão dela.

    Dizer "parou" aqui seria inventar a queda.
    """
    laudo = storm_por_porta(
        linhas=[_linha("usb 3-4.4: device descriptor read/64, error -71")],
        hoje=HOJE,
        raiz_usb=tmp_path / "sys",
        nomear=em._sem_nome,
    )
    assert laudo.portas[0].desfecho == ""
    assert laudo.portas[0].parada == ""


def test_a_desistencia_no_mesmo_segundo_ganha(tmp_path: Path) -> None:
    """A tentativa e a desistência no MESMO segundo: vale a ordem em que o kernel escreveu.

    Medido na mesa dela em 24/09: `not accepting address 10` e `unable to
    enumerate` saem no mesmo carimbo.
    """
    laudo = storm_por_porta(
        linhas=[
            _linha("usb 3-4.4: device not accepting address 9, error -71"),
            _linha("usb 3-4-port4: unable to enumerate USB device"),
        ],
        hoje=HOJE,
        raiz_usb=tmp_path / "sys",
        nomear=em._sem_nome,
    )
    assert laudo.portas[0].desfecho == DESFECHO_ENTRADA_LARGADA


def test_o_log_fora_de_ordem_nao_engana_o_desfecho(tmp_path: Path) -> None:
    """A desistência mais NOVA vale, mesmo escrita antes de uma tentativa mais velha.

    O `kernel.log` fica fora de ordem de verdade (dois escritores, a unit que
    recomeça o journal) — ver `test_o_ultimo_e_o_mais_recente_e_nao_a_ultima_linha`.
    """
    laudo = storm_por_porta(
        linhas=[
            _linha("usb 3-4-port4: unable to enumerate USB device", quando="2026-09-24T12:55:51"),
            _linha("usb 3-4.4: device descriptor read/64, error -71", quando="2026-09-23T08:00:00"),
        ],
        hoje=HOJE,
        raiz_usb=tmp_path / "sys",
        nomear=em._sem_nome,
    )
    assert laudo.portas[0].desfecho == DESFECHO_ENTRADA_LARGADA


@pytest.mark.parametrize(
    ("mensagem", "desfecho"),
    [
        ("usb 3-4-port4: unable to enumerate USB device", DESFECHO_ENTRADA_LARGADA),
        ("usb usb1-port4: unable to enumerate USB device", DESFECHO_ENTRADA_LARGADA),
        ("usbhid 3-4.4:1.3: can't add hid device: -71", DESFECHO_SEM_HID),
        ("usbhid 3-4.4:1.3: probe with driver usbhid failed with error -71", DESFECHO_SEM_HID),
        ("usb 3-4.4: device descriptor read/64, error -71", ""),
        ("usb 3-4: clear tt 1 (9092) error -71", ""),
    ],
)
def test_as_linhas_da_mesa_dela_e_o_desfecho(mensagem: str, desfecho: str) -> None:
    """As formas COPIADAS do `kernel.log` dela (24/09), e o desfecho de cada uma."""
    assert em._desfecho(mensagem) == desfecho


def test_o_json_leva_a_entrada_o_papel_e_a_parada(tmp_path: Path) -> None:
    """É por JSON que o doctor lê — os campos novos têm de atravessar."""
    import json

    raiz = tmp_path / "sys"
    _dualsense(raiz, "3-4.4", hid="sem-driver")
    laudo = storm_por_porta(
        linhas=[_linha("usbhid 3-4.4:1.3: can't add hid device: -71")],
        hoje=HOJE,
        raiz_usb=raiz,
        nomear=lambda porta: "Entrada 7" if porta == "3-4.4" else None,
    )
    forma = json.loads(json.dumps(laudo.como_dicionario(), ensure_ascii=False))
    porta = forma["portas"][0]
    assert porta["entrada"] == "Entrada 7 (3-4.4)"
    assert porta["desfecho"] == DESFECHO_SEM_HID
    assert porta["parada"].startswith("o controle está nela sem o HID")
    assert porta["aparelho"]["hid_sem_driver"] is True
    assert porta["aparelho"]["papel"] == "um controle, pelo USB"
