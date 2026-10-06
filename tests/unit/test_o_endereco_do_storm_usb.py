"""O -71 tem endereço, e o endereço é a porta mais o aparelho — STORM-USB-01.

O DEFEITO, medido em 19/09/2026 e escrito na sprint: o doctor imprimia

    [WARN] storm USB (-71) registrado no kernel-watch [USB-71] — 33 vez(es)
    nos últimos 7 dias (a última em 18/09); 164 no log inteiro

e mais nada. **A porta estava gravada em cada uma das 33 linhas** desde que o
`storm_watch.sh` nasceu; ninguém a cruzava com a topologia do ``/sys``. Um
número sem endereço não manda ninguém a lugar nenhum — ``-71`` é ``EPROTO``, e
a porta é a única coisa que separa *"o cabo daquele controle"* de *"aquele
hub"*.

AS MORDIDAS DESTE ARQUIVO, uma por função, e as três primeiras são o arranjo
DIFÍCIL — um parser que só reconhecesse ``usb 3-4:`` daria verde sobre 40% do
`kernel.log` desta casa:

* :func:`test_a_porta_do_hub_vira_a_porta_do_aparelho` — arranque
  ``_PORTA_DE_HUB`` de `exame_da_mesa` e ela reprova: ``usb 3-1.1-port3``
  deixa de virar ``3-1.1.3`` e o evento cai em "sem endereço". É o caso em que
  o aparelho NUNCA enumerou, logo não tem endereço próprio — o kernel nomeia a
  porta física, e é dela que o degrau sai.
* :func:`test_a_porta_do_hub_raiz_vira_o_no` — arranque
  ``_PORTA_DE_HUB_RAIZ`` e ``usb usb3-port4`` deixa de virar ``3-4``.
* :func:`test_a_interface_vira_o_aparelho` — arranque ``_INTERFACE_USB`` e
  ``usbhid 3-4.1.3:1.3`` deixa de virar ``3-4.1.3``.
* :func:`test_o_que_nao_se_enderecou_e_contado` — faça
  :func:`storm_por_porta` descartar em silêncio o que não soube endereçar e
  ela reprova: a soma das portas ficaria menor que o total contado, sem
  ninguém ver. É o F3 desta casa (*ausência é resposta*).
* :func:`test_o_hub_em_comum_precisa_de_duas_portas` — baixe o piso para UMA
  porta e ela reprova: um hub com uma única porta ruim seria acusado, o que é
  trocar a causa pelo endereço.
* :func:`test_a_porta_vazia_nao_vira_aparelho_nenhum` — faça a porta ausente
  devolver ``presente=True`` e ela reprova: o doctor passaria a nomear um
  aparelho que não está lá.
* :func:`test_a_janela_corta_o_que_e_velho` — tire o corte e ela reprova.

CINCO MORDIDAS QUE NÃO MORDIAM, achadas pela conferência de 20/09 e curadas
aqui. Todas na mesma dobra: **a frase do laudo estava coberta em pedaços, e o
pedaço de fora era o que a bancada imprime mais**:

* :func:`test_a_porta_de_raiz_diz_que_nao_ha_hub_no_caminho` — a bancada das
  réguas só tinha o arranjo FUNDO (``3-4.1.3``, atrás de dois hubs). O ramo
  sem hub — 27 dos 33 eventos da janela de 20/09 — passava com o texto
  arrancado.
* :func:`test_a_frase_diz_o_dia_antes_do_mes` — as réguas conferiam o campo
  ISO de máquina e nunca a data DENTRO da frase; inverter dia e mês passava.
* :func:`test_o_ultimo_e_o_mais_recente_e_nao_a_ultima_linha` — todas as
  linhas de teste já vinham em ordem crescente, então a guarda do máximo
  passava com a cura arrancada.
* :func:`test_o_empate_se_desfaz_pelo_nome_da_porta` — a régua da ordem
  PROMETIA o desempate no docstring e cobria só o ramo da contagem.
* :func:`test_a_cadeia_recusa_o_que_nao_e_porta` — a guarda de
  :func:`cadeia_da_porta` não tinha chamador com entrada inválida.

A RAIZ DO ``/sys`` ENTRA POR ARGUMENTO em todos eles: nenhum teste aqui olha a
máquina de quem roda a suíte, e é por isso que o resultado não muda quando o
DualSense do usuário sai da mesa.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import exame_da_mesa as exame_mod
from hefesto_dualsense4unix.integrations.exame_da_mesa import (
    aparelho_da_porta,
    cadeia_da_porta,
    log_do_kernel_watch,
    porta_do_evento,
    storm_por_porta,
)

HOJE = datetime.date(2026, 9, 20)


def _linha(dia: str, mensagem: str) -> str:
    """Uma linha do `kernel.log` no formato que o `storm_watch.sh` escreve."""
    return f"{dia}T12:00:00-03:00 [USB-71] {mensagem}"


def _no(raiz: Path, porta: str, *, vid: str, pid: str, nome: str, classe: str) -> None:
    """Um nó USB de mentira, com os quatro campos que o exame lê."""
    no = raiz / porta
    no.mkdir(parents=True)
    (no / "idVendor").write_text(vid + "\n", encoding="utf-8")
    (no / "idProduct").write_text(pid + "\n", encoding="utf-8")
    (no / "product").write_text(nome + "\n", encoding="utf-8")
    (no / "bDeviceClass").write_text(classe + "\n", encoding="utf-8")


def test_o_no_simples_e_a_propria_porta() -> None:
    """`usb 3-4.1.3: ...` — a forma FÁCIL, e a única que um parser ingênuo pega."""
    assert porta_do_evento("usb 3-4.1.3: device descriptor read/all, error -71") == (
        "3-4.1.3"
    )


def test_a_interface_vira_o_aparelho() -> None:
    """`usbhid 3-4.1.3:1.3` endereça o APARELHO, não a interface."""
    assert porta_do_evento("usbhid 3-4.1.3:1.3: can't add hid device: -71") == "3-4.1.3"


def test_o_driver_nao_precisa_ser_o_usbhid() -> None:
    """`uvcvideo 1-6:1.0` é a webcam, e ela também mora numa porta."""
    assert porta_do_evento(
        "uvcvideo 1-6:1.0: UVC non compliance: permanently disabling control "
        "980900 (Brightness), due to error -71"
    ) == "1-6"


def test_a_porta_do_hub_raiz_vira_o_no() -> None:
    """`usb usb3-port4` é a porta 4 do hub-RAIZ do barramento 3 — o nó `3-4`."""
    assert porta_do_evento("usb usb3-port4: unable to enumerate USB device") == "3-4"


def test_a_porta_do_hub_vira_a_porta_do_aparelho() -> None:
    """`usb 3-1.1-port3` é a porta 3 do hub em `3-1.1` — o nó `3-1.1.3`."""
    assert porta_do_evento("usb 3-1.1-port3: unable to enumerate USB device") == (
        "3-1.1.3"
    )


def test_o_que_o_parser_nao_conhece_devolve_vazio() -> None:
    """Forma desconhecida devolve ``""`` — e nunca um endereço inventado."""
    assert porta_do_evento("alguma coisa completamente diferente aconteceu") == ""
    assert porta_do_evento("") == ""


def test_a_cadeia_sobe_degrau_por_degrau() -> None:
    """`3-4.1.3` passa por `3-4` e `3-4.1` antes de chegar em si mesmo."""
    assert cadeia_da_porta("3-4.1.3") == ("3-4", "3-4.1", "3-4.1.3")


def test_a_porta_de_raiz_nao_tem_hub_no_caminho() -> None:
    """`1-4` é uma entrada do próprio computador: a cadeia é ela sozinha."""
    assert cadeia_da_porta("1-4") == ("1-4",)


def test_a_cadeia_recusa_o_que_nao_e_porta() -> None:
    """Texto que não é endereço USB devolve ``()`` — nunca um caminho inventado."""
    assert cadeia_da_porta("") == ()
    assert cadeia_da_porta("usb3-port4") == ()
    assert cadeia_da_porta("0000:00:14.0") == ()


def test_a_cadeia_nao_le_o_sys() -> None:
    """Ela é texto puro, e é isso que a faz servir a porta que já não existe."""
    assert cadeia_da_porta("9-9.9.9") == ("9-9", "9-9.9", "9-9.9.9")


def test_o_aparelho_sai_do_sys_injetado(tmp_path: Path) -> None:
    """Com a raiz injetada, a identidade é a do nó — e nada da máquina real."""
    _no(tmp_path, "3-4.1.3", vid="054c", pid="0ce6", nome="DualSense", classe="00")
    aparelho = aparelho_da_porta("3-4.1.3", raiz_usb=tmp_path)
    assert aparelho.presente is True
    assert aparelho.vid == "054c"
    assert aparelho.e_hub is False
    assert "DualSense (054c:0ce6)" in aparelho.identidade


def test_o_hub_se_declara_hub(tmp_path: Path) -> None:
    """`bDeviceClass` 09 é hub — e é o que separa o meio do caminho do fim."""
    _no(tmp_path, "3-4", vid="05e3", pid="0610", nome="USB2.1 Hub", classe="09")
    assert aparelho_da_porta("3-4", raiz_usb=tmp_path).e_hub is True


def test_a_porta_vazia_nao_vira_aparelho_nenhum(tmp_path: Path) -> None:
    """Porta ausente é ``presente=False``, e a frase DIZ que não se sabe."""
    aparelho = aparelho_da_porta("3-1.1", raiz_usb=tmp_path)
    assert aparelho.presente is False
    assert aparelho.vid == ""
    assert "não guarda quem já esteve aqui" in aparelho.identidade


def test_a_porta_ilegivel_nao_e_chamada_de_vazia(tmp_path: Path) -> None:
    """Existe mas não deixa ler o VID: ainda é ``presente``, com identidade pobre."""
    (tmp_path / "3-4").mkdir(parents=True)
    aparelho = aparelho_da_porta("3-4", raiz_usb=tmp_path)
    assert aparelho.presente is True
    assert "não publica nome" in aparelho.identidade


def _bancada(tmp_path: Path) -> Path:
    """A topologia desta casa, medida em 20/09/2026 e reproduzida em `tmp_path`."""
    raiz = tmp_path / "sys"
    _no(raiz, "3-4", vid="05e3", pid="0610", nome="USB2.1 Hub", classe="09")
    _no(raiz, "3-4.1", vid="05e3", pid="0610", nome="USB2.1 Hub", classe="09")
    _no(raiz, "3-4.1.3", vid="054c", pid="0ce6", nome="DualSense", classe="00")
    _no(raiz, "3-4.4", vid="2357", pid="0604", nome="UB500", classe="e0")
    _no(raiz, "1-4", vid="2357", pid="0604", nome="TP-Link BT", classe="e0")
    return raiz


def test_o_laudo_diz_a_porta_e_o_aparelho(tmp_path: Path) -> None:
    """A entrega da sprint em uma asserção: porta + aparelho + hub, por evento."""
    laudo = storm_por_porta(
        linhas=[
            _linha("2026-09-16", "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
            _linha(
                "2026-09-16",
                "usbhid 3-4.1.3:1.3: probe with driver usbhid failed with error -71",
            ),
        ],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert len(laudo.portas) == 1
    porta = laudo.portas[0]
    assert porta.porta == "3-4.1.3"
    assert porta.quantos == 2
    assert porta.ultimo == "2026-09-16"
    assert "DualSense (054c:0ce6)" in porta.porque
    assert [h.porta for h in porta.hubs] == ["3-4", "3-4.1"]
    assert "atrás de 2 hubs" in porta.porque


def test_a_frase_diz_que_a_leitura_do_aparelho_e_de_agora(tmp_path: Path) -> None:
    """Dois tempos verbais na mesma linha, e eles não se misturam.

    A contagem e a data vêm do LOG (passado); quem está na porta vem do ``/sys``
    (presente). Sem o "AGORA" a frase afirmaria que o DualSense de hoje é o
    aparelho que deu -71 há quatro dias — e o ``/sys`` não sabe disso. É a
    mesma classe do defeito que ela pegou em 03/09, aqui em outra roupa.
    """
    laudo = storm_por_porta(
        linhas=[_linha("2026-09-16", "usb 3-4.1.3: can't read configurations, error -71")],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert "nela AGORA:" in laudo.portas[0].porque


def test_a_janela_corta_o_que_e_velho(tmp_path: Path) -> None:
    """Evento de 30 dias atrás não entra — a mesma janela do `check_kernel_watch`."""
    laudo = storm_por_porta(
        linhas=[
            _linha("2026-08-21", "usb 3-4.4: device descriptor read/64, error -71"),
            _linha("2026-09-16", "usb 3-4.1.3: can't read configurations, error -71"),
        ],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert [p.porta for p in laudo.portas] == ["3-4.1.3"]
    assert laudo.total == 1


def test_o_que_nao_e_usb71_nao_entra(tmp_path: Path) -> None:
    """Só a tag `[USB-71]`. As outras cinco tags do kernel-watch são de outro assunto."""
    laudo = storm_por_porta(
        linhas=[
            "2026-09-16T12:00:00-03:00 [JOYCON] usb 3-4.4: joycon_enforce_subcmd_rate",
            "2026-09-16T12:00:00-03:00 [XHCI] xhci_hcd 0000:00:14.0: reset",
        ],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert laudo.portas == ()
    assert laudo.sem_endereco == 0


def test_o_que_nao_se_enderecou_e_contado(tmp_path: Path) -> None:
    """A linha que o parser não soube ler é CONTADA, nunca descartada."""
    laudo = storm_por_porta(
        linhas=[
            _linha("2026-09-16", "usb 3-4.1.3: can't read configurations, error -71"),
            _linha("2026-09-17", "uma forma de linha que o kernel ainda não escreveu"),
            _linha("2026-09-17", "outra forma estranha sem dois-pontos nenhum"),
        ],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert laudo.sem_endereco == 2
    assert laudo.total == 3, "o total tem de fechar com o que o doctor conta"


def test_a_porta_de_raiz_diz_que_nao_ha_hub_no_caminho(tmp_path: Path) -> None:
    """O ramo SEM hub — 27 dos 33 eventos desta casa — também tem de sair certo."""
    laudo = storm_por_porta(
        linhas=[_linha("2026-09-16", "usb 1-4: device descriptor read/all, error -71")],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    porta = laudo.portas[0]
    assert porta.hubs == ()
    assert "direto numa entrada do próprio computador" in porta.porque
    assert "atrás de" not in porta.porque
    assert "TP-Link BT (2357:0604)" in porta.porque


def test_a_frase_diz_o_dia_antes_do_mes(tmp_path: Path) -> None:
    """``2026-09-07`` sai como ``07/09`` — dia/mês, a ordem desta casa."""
    laudo = storm_por_porta(
        linhas=[_linha("2026-09-07", "usb 1-4: device descriptor read/all, error -71")],
        dias=15,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert "o último em 07/09" in laudo.portas[0].porque


def test_um_evento_so_nao_vira_eventos(tmp_path: Path) -> None:
    """"1 evento" no singular, "2 eventos" no plural — e as duas medidas."""
    bancada = _bancada(tmp_path)
    uma = storm_por_porta(
        linhas=[_linha("2026-09-16", "usb 1-4: device descriptor read/all, error -71")],
        dias=7,
        hoje=HOJE,
        raiz_usb=bancada,
    )
    assert "1 evento," in uma.portas[0].porque
    duas = storm_por_porta(
        linhas=[
            _linha("2026-09-16", "usb 1-4: device descriptor read/all, error -71"),
            _linha("2026-09-16", "usb 1-4: device not accepting address 12, error -71"),
        ],
        dias=7,
        hoje=HOJE,
        raiz_usb=bancada,
    )
    assert "2 eventos," in duas.portas[0].porque


def test_o_ultimo_e_o_mais_recente_e_nao_a_ultima_linha(tmp_path: Path) -> None:
    """Com o log fora de ordem, o carimbo do evento mais NOVO não regride."""
    laudo = storm_por_porta(
        linhas=[
            _linha("2026-09-17", "usb 1-4: device descriptor read/all, error -71"),
            _linha("2026-09-14", "usb 1-4: device not accepting address 12, error -71"),
        ],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert laudo.portas[0].ultimo == "2026-09-17"
    assert "o último em 17/09" in laudo.portas[0].porque


def test_o_hub_em_comum_e_nomeado(tmp_path: Path) -> None:
    """Duas portas que deram -71 sob o MESMO hub: o hub é o fator comum."""
    laudo = storm_por_porta(
        linhas=[
            _linha("2026-09-16", "usbhid 3-4.1.3:1.3: can't add hid device: -71"),
            _linha("2026-09-16", "usbhid 3-4.4:1.3: can't add hid device: -71"),
        ],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert [h.hub.porta for h in laudo.hubs_em_comum] == ["3-4"]
    assert laudo.hubs_em_comum[0].portas == ("3-4.1.3", "3-4.4")
    assert "USB2.1 Hub (05e3:0610)" in laudo.hubs_em_comum[0].porque


def test_o_hub_em_comum_precisa_de_duas_portas(tmp_path: Path) -> None:
    """Uma porta só NÃO acusa o hub dela."""
    laudo = storm_por_porta(
        linhas=[_linha("2026-09-16", "usbhid 3-4.1.3:1.3: can't add hid device: -71")],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert laudo.hubs_em_comum == ()


def test_as_portas_saem_da_mais_ruidosa_para_a_menos(tmp_path: Path) -> None:
    """Ordem estável: mais eventos primeiro, empate pelo nome da porta."""
    laudo = storm_por_porta(
        linhas=[
            _linha("2026-09-16", "usb 3-4.4: device descriptor read/64, error -71"),
            _linha("2026-09-16", "usb 3-4.1.3: can't read configurations, error -71"),
            _linha("2026-09-17", "usb 3-4.1.3: can't read configurations, error -71"),
        ],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert [p.porta for p in laudo.portas] == ["3-4.1.3", "3-4.4"]


def test_o_empate_se_desfaz_pelo_nome_da_porta(tmp_path: Path) -> None:
    """Duas portas com a MESMA contagem saem em ordem alfabética, sempre."""
    laudo = storm_por_porta(
        linhas=[
            _linha("2026-09-16", "usb 3-4.4: device descriptor read/64, error -71"),
            _linha("2026-09-16", "usb 3-4.1.3: can't read configurations, error -71"),
        ],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert [p.porta for p in laudo.portas] == ["3-4.1.3", "3-4.4"]


def test_sem_log_o_laudo_diz_por_que_nao_mediu() -> None:
    """Ausência é resposta: lista vazia SEM explicação se leria como "nenhum -71"."""
    laudo = storm_por_porta(log=None, dias=7, hoje=HOJE)
    assert laudo.portas == ()
    assert laudo.porque_nao, "um laudo vazio calado mente por omissão"


def test_log_ilegivel_tambem_diz_por_que(tmp_path: Path) -> None:
    """O arquivo que não abre não vira "está tudo limpo"."""
    laudo = storm_por_porta(log=tmp_path / "nao-existe.log", dias=7, hoje=HOJE)
    assert laudo.portas == ()
    assert "não deu para ler" in laudo.porque_nao


def test_o_laudo_sobrevive_ao_json(tmp_path: Path) -> None:
    """É por JSON que o doctor consome — e o `porque` tem de atravessar."""
    import json

    laudo = storm_por_porta(
        linhas=[_linha("2026-09-16", "usbhid 3-4.1.3:1.3: can't add hid device: -71")],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    forma = json.loads(json.dumps(laudo.como_dicionario(), ensure_ascii=False))
    assert forma["total"] == 1
    assert forma["portas"][0]["porta"] == "3-4.1.3"
    assert "DualSense" in forma["portas"][0]["porque"]


def test_o_kernel_log_vem_antes_do_storm_log(tmp_path: Path) -> None:
    """A mesma escada do `doctor.sh:3881-3882` — o nome novo ganha do antigo."""
    estado = tmp_path / ".local/state/hefesto-dualsense4unix"
    estado.mkdir(parents=True)
    (estado / "storm.log").write_text("", encoding="utf-8")
    assert log_do_kernel_watch(tmp_path).name == "storm.log"
    (estado / "kernel.log").write_text("", encoding="utf-8")
    assert log_do_kernel_watch(tmp_path).name == "kernel.log"


def test_sem_nenhum_dos_dois_o_caminho_e_none(tmp_path: Path) -> None:
    """Sem log, ``None`` — e quem chama vira `porque_nao`, não lista vazia."""
    assert log_do_kernel_watch(tmp_path) is None


@pytest.mark.parametrize(
    ("mensagem", "porta"),
    [
        ("usb 1-4: device descriptor read/all, error -71", "1-4"),
        ("usb 3-1.1: clear tt 1 (9072) error -71", "3-1.1"),
        ("usbhid 3-4.4:1.3: can't add hid device: -71", "3-4.4"),
        ("usb usb1-port3: unable to enumerate USB device", "1-3"),
        ("usb 3-1.1-port3: unable to enumerate USB device", "3-1.1.3"),
        ("usb 3-4.1.3: can't set config #1, error -71", "3-4.1.3"),
        ("usb 3-4: device not accepting address 12, error -71", "3-4"),
    ],
)
def test_as_formas_do_kernel_log_desta_casa(mensagem: str, porta: str) -> None:
    """Sete linhas COPIADAS do `kernel.log` desta bancada, com o -71 mascarado."""
    assert porta_do_evento(mensagem) == porta


def test_o_modulo_nao_chama_o_storm_no_exame(tmp_path: Path) -> None:
    """O exame das cinco linhas NÃO ganhou uma sexta — a tela não mudou."""
    itens = exame_mod.exame(
        parametro_do_radio=tmp_path / "enable_autosuspend",
        conf_do_radio=tmp_path / "conf",
        raiz_usb=tmp_path / "usb",
        modulos=tmp_path / "modules",
        diretorio_do_modulo=tmp_path / "hid-playstation",
        executar_busctl=lambda _: None,
        leitura_da_vizinhanca=lambda: [],
    )
    assert len(itens) == 5
    assert "storm_usb" not in {item.chave for item in itens}
