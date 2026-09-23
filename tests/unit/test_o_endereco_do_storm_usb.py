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
pedaço de fora era o que a mesa dela imprime mais**:

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
DualSense dela sai da mesa.
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

#: O dia de referência das réguas. Fixo de propósito: uma janela medida contra
#: `date.today()` faz o teste mudar de resposta à meia-noite.
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


# --- as cinco formas da linha do kernel --------------------------------------
#
# As cinco saíram do `kernel.log` desta casa (164 eventos, 08/08 a 18/09) e não
# de uma leitura do fonte do kernel: o que o parser precisa reconhecer é o que
# o kernel REALMENTE escreveu nesta bancada.


def test_o_no_simples_e_a_propria_porta() -> None:
    """`usb 3-4.1.3: ...` — a forma FÁCIL, e a única que um parser ingênuo pega."""
    assert porta_do_evento("usb 3-4.1.3: device descriptor read/all, error -71") == (
        "3-4.1.3"
    )


def test_a_interface_vira_o_aparelho() -> None:
    """`usbhid 3-4.1.3:1.3` endereça o APARELHO, não a interface.

    A MORDIDA: arranque `_INTERFACE_USB` e esta linha deixa de ter endereço —
    o `:1.3` a faz falhar em `_NO_USB`, e 14 dos 164 eventos deste log somem.
    """
    assert porta_do_evento("usbhid 3-4.1.3:1.3: can't add hid device: -71") == "3-4.1.3"


def test_o_driver_nao_precisa_ser_o_usbhid() -> None:
    """`uvcvideo 1-6:1.0` é a webcam, e ela também mora numa porta.

    O parser casa a FORMA da linha do kernel, não uma lista de drivers — que é
    o que impede o dia em que o `snd-usb-audio` aparecer aqui de virar um
    evento sem endereço.
    """
    assert porta_do_evento(
        "uvcvideo 1-6:1.0: UVC non compliance: permanently disabling control "
        "980900 (Brightness), due to error -71"
    ) == "1-6"


def test_a_porta_do_hub_raiz_vira_o_no() -> None:
    """`usb usb3-port4` é a porta 4 do hub-RAIZ do barramento 3 — o nó `3-4`.

    A MORDIDA: arranque `_PORTA_DE_HUB_RAIZ` e sobra vazio.

    PROVA CRUZADA nesta bancada, e ela não vem do meu parser: em 24/08 o log
    tem `usb usb1-port6: unable to enumerate USB device` e, no MESMO dia,
    `uvcvideo 1-6:1.0: ... error -71`. O kernel nomeou o mesmo aparelho pelos
    dois caminhos, e é o que sustenta a tradução.
    """
    assert porta_do_evento("usb usb3-port4: unable to enumerate USB device") == "3-4"


def test_a_porta_do_hub_vira_a_porta_do_aparelho() -> None:
    """`usb 3-1.1-port3` é a porta 3 do hub em `3-1.1` — o nó `3-1.1.3`.

    A MORDIDA: arranque `_PORTA_DE_HUB` e sobra vazio.

    É a forma MAIS informativa das cinco, e a que um parser ingênuo perde: o
    aparelho nunca enumerou, então ele não tem endereço próprio nenhum. Só
    existe a porta física, e é ela que diz onde encostar a mão.
    """
    assert porta_do_evento("usb 3-1.1-port3: unable to enumerate USB device") == (
        "3-1.1.3"
    )


def test_o_que_o_parser_nao_conhece_devolve_vazio() -> None:
    """Forma desconhecida devolve ``""`` — e nunca um endereço inventado."""
    assert porta_do_evento("alguma coisa completamente diferente aconteceu") == ""
    assert porta_do_evento("") == ""


# --- o caminho até a porta ---------------------------------------------------


def test_a_cadeia_sobe_degrau_por_degrau() -> None:
    """`3-4.1.3` passa por `3-4` e `3-4.1` antes de chegar em si mesmo."""
    assert cadeia_da_porta("3-4.1.3") == ("3-4", "3-4.1", "3-4.1.3")


def test_a_porta_de_raiz_nao_tem_hub_no_caminho() -> None:
    """`1-4` é uma entrada do próprio computador: a cadeia é ela sozinha."""
    assert cadeia_da_porta("1-4") == ("1-4",)


def test_a_cadeia_recusa_o_que_nao_e_porta() -> None:
    """Texto que não é endereço USB devolve ``()`` — nunca um caminho inventado.

    A MORDIDA: arranque a guarda ``_NO_USB`` de :func:`cadeia_da_porta` e esta
    régua reprova, com ``""`` virando o caminho ``("-",)``. Nenhuma régua a
    alcançava: todas chamavam a função com porta válida, e a guarda que impede
    o laudo de acusar um hub chamado ``-`` passava com a cura arrancada.
    """
    assert cadeia_da_porta("") == ()
    assert cadeia_da_porta("usb3-port4") == ()
    assert cadeia_da_porta("0000:00:14.0") == ()


def test_a_cadeia_nao_le_o_sys() -> None:
    """Ela é texto puro, e é isso que a faz servir a porta que já não existe.

    Um -71 de seis dias atrás costuma ser de uma porta VAZIA hoje. Se a cadeia
    dependesse do ``/sys``, o caminho do evento antigo seria inexprimível — e
    é justamente o evento antigo que ninguém consegue explicar.
    """
    assert cadeia_da_porta("9-9.9.9") == ("9-9", "9-9.9", "9-9.9.9")


# --- quem está na porta ------------------------------------------------------


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
    """Porta ausente é ``presente=False``, e a frase DIZ que não se sabe.

    A MORDIDA: faça `aparelho_da_porta` devolver ``presente=True`` para a porta
    que não existe e esta régua reprova — o doctor passaria a nomear um
    aparelho que não está lá, que é a mentira mais cara que este laudo pode
    contar.
    """
    aparelho = aparelho_da_porta("3-1.1", raiz_usb=tmp_path)
    assert aparelho.presente is False
    assert aparelho.vid == ""
    assert "não guarda quem já esteve aqui" in aparelho.identidade


def test_a_porta_ilegivel_nao_e_chamada_de_vazia(tmp_path: Path) -> None:
    """Existe mas não deixa ler o VID: ainda é ``presente``, com identidade pobre.

    "Não consegui ler" e "não tem ninguém" são afirmações OPOSTAS, e colapsá-las
    é o defeito que o quarto estado deste módulo existe para impedir. Aqui o nó
    existe e nenhum campo é legível — o caso do ``/sys`` sob contêiner.
    """
    (tmp_path / "3-4").mkdir(parents=True)
    aparelho = aparelho_da_porta("3-4", raiz_usb=tmp_path)
    assert aparelho.presente is True
    assert "não publica nome" in aparelho.identidade


# --- o laudo inteiro ---------------------------------------------------------


def _bancada(tmp_path: Path) -> Path:
    """A topologia desta casa, medida em 20/09/2026 e reproduzida em `tmp_path`."""
    raiz = tmp_path / "sys"
    _no(raiz, "3-4", vid="05e3", pid="0610", nome="USB2.1 Hub", classe="09")
    _no(raiz, "3-4.1", vid="05e3", pid="0610", nome="USB2.1 Hub", classe="09")
    _no(raiz, "3-4.1.3", vid="054c", pid="0ce6", nome="DualSense", classe="00")
    _no(raiz, "3-4.4", vid="2357", pid="0604", nome="UB500", classe="e0")
    # A PORTA DE RAIZ ESTAVA FALTANDO AQUI, e ela não é um caso de borda: no
    # `kernel.log` desta casa, 27 dos 33 eventos da janela de 20/09 são em
    # `1-4` — uma entrada do próprio computador, sem hub nenhum no caminho. A
    # bancada só tinha o arranjo FUNDO (3-4.1.3, atrás de dois hubs), e o ramo
    # que a máquina dela imprime vinte e sete vezes não tinha régua.
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
    assert "nesta porta AGORA:" in laudo.portas[0].porque


def test_a_janela_corta_o_que_e_velho(tmp_path: Path) -> None:
    """Evento de 30 dias atrás não entra — a mesma janela do `check_kernel_watch`.

    A MORDIDA: tire a comparação com o corte e esta régua reprova. Seria o
    defeito de 03/09 renascido dentro do laudo novo: um endereço de agosto
    impresso como se fosse de agora.
    """
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
    """A linha que o parser não soube ler é CONTADA, nunca descartada.

    A MORDIDA: troque o ``sem_endereco += 1`` por um ``continue`` mudo e esta
    régua reprova. Sem ela, o dia em que o kernel inventar uma sexta forma de
    linha o doctor mostraria três portas sobre trinta e três eventos, com a
    diferença invisível — um instrumento verde sobre a própria cegueira.
    """
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
    """O ramo SEM hub — 27 dos 33 eventos desta casa — também tem de sair certo.

    A MORDIDA: apague o texto do ``else`` de :attr:`PortaDoStorm.porque` (o
    *"direto numa entrada do próprio computador"*) e esta régua reprova.

    Ela nasceu de uma mordida que NÃO mordeu: a bancada das réguas só tinha o
    arranjo fundo (``3-4.1.3``, atrás de dois hubs), e o ramo que a mesa dela
    imprime vinte e sete vezes passava com o texto arrancado. *A régua cobria
    o arranjo difícil e deixava o comum de fora* — a forma inversa do defeito
    de sempre, e igualmente cega.
    """
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
    """``2026-09-07`` sai como ``07/09`` — dia/mês, a ordem desta casa.

    A MORDIDA: troque a fatia ``[8:10]`` pela ``[5:7]`` do carimbo ISO, na
    :attr:`PortaDoStorm.porque` e esta régua reprova. Nenhuma outra a pegava:
    as réguas conferiam o campo ISO de máquina e nunca a DATA DENTRO DA
    FRASE, que é a única coisa que uma pessoa lê.

    A data escolhida tem os dois números válidos como dia E como mês de
    propósito: invertida, ``07/09`` vira ``09/07`` e continua parecendo uma
    data — manda procurar a queda de 9 de julho, que não houve. Com ``16/09``
    a troca daria ``09/16``, visivelmente quebrado, e a régua morderia por
    sorte em vez de por desenho.
    """
    laudo = storm_por_porta(
        linhas=[_linha("2026-09-07", "usb 1-4: device descriptor read/all, error -71")],
        dias=15,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert "o último em 07/09" in laudo.portas[0].porque


def test_um_evento_so_nao_vira_eventos(tmp_path: Path) -> None:
    """"1 evento" no singular, "2 eventos" no plural — e as duas medidas.

    A MORDIDA: troque o condicional do plural por um texto fixo e esta régua
    reprova. Sozinha ela seria cosmética; junto com as outras deste bloco ela
    fecha a frase INTEIRA do laudo, que é a entrega da sprint e estava coberta
    só em pedaços.
    """
    # UMA bancada só: `_bancada` CRIA os nós, e chamá-la duas vezes na mesma
    # `tmp_path` estoura em `mkdir`. A régua mede a frase, não o /sys.
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
    """Com o log fora de ordem, o carimbo do evento mais NOVO não regride.

    A MORDIDA: troque o ``if data > ultimo.get(porta, "")`` por uma atribuição
    seca e esta régua reprova — a frase passaria a anunciar a queda de 14/09
    como a última, escondendo a de 17/09.

    E o log FICA fora de ordem de verdade: o `storm_watch.sh` escreve com dois
    produtores no mesmo arquivo (o `journalctl -f` e o `bt_delta_loop &`), a
    unit re-tenta e recomeça o `journalctl`, e o relógio da máquina pode andar
    para trás num acerto de NTP. A guarda existia e nenhuma régua a segurava:
    todas as linhas dos testes já vinham em ordem crescente.
    """
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
    """Duas portas que deram -71 sob o MESMO hub: o hub é o fator comum.

    É a resposta à pergunta 1 da sprint — *"é a porta, o cabo ou o hub?"*. Com
    duas portas independentes sob `3-4` em pane, a topologia aponta o hub, e
    nenhum dos dois aparelhos explica o outro.
    """
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
    """Uma porta só NÃO acusa o hub dela.

    A MORDIDA: baixe o piso de ``>= 2`` para ``>= 1`` e esta régua reprova.
    Com uma porta só, o aparelho daquela porta explica o evento igualmente bem
    e é o suspeito mais barato — acusar o hub seria trocar a causa pelo
    endereço, que é como um laudo manda trocar peça boa.
    """
    laudo = storm_por_porta(
        linhas=[_linha("2026-09-16", "usbhid 3-4.1.3:1.3: can't add hid device: -71")],
        dias=7,
        hoje=HOJE,
        raiz_usb=_bancada(tmp_path),
    )
    assert laudo.hubs_em_comum == ()


def test_as_portas_saem_da_mais_ruidosa_para_a_menos(tmp_path: Path) -> None:
    """Ordem estável: mais eventos primeiro, empate pelo nome da porta.

    Sem o desempate, duas execuções sobre o MESMO log dariam ordens diferentes
    e um `diff` entre dois laudos acusaria mudança onde não houve.
    """
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
    """Duas portas com a MESMA contagem saem em ordem alfabética, sempre.

    A MORDIDA: tire o ``p.porta`` da chave do ``sort`` e esta régua reprova.

    A régua irmã (:func:`test_as_portas_saem_da_mais_ruidosa_para_a_menos`)
    PROMETIA isto no docstring — *"empate pelo nome da porta"* — e cobria só o
    ramo do ``-quantos``: as duas portas dela tinham contagens diferentes, e
    arrancar o desempate a deixava verde. Aqui as duas empatam em 1, e entram
    no log na ordem CONTRÁRIA à alfabética, para que a ordem de inserção do
    dicionário não possa ser confundida com ordenação.
    """
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


# --- o caminho do log --------------------------------------------------------


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


# --- as cinco formas, medidas de uma vez -------------------------------------


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
    """Sete linhas COPIADAS do `kernel.log` desta bancada, com o -71 mascarado.

    Elas não foram inventadas a partir do regex — vieram do log, e é o que
    impede a tautologia de montar o esperado com a mesma constante que a
    função lê. Se o parser perder uma forma, esta tabela reprova por ela.
    """
    assert porta_do_evento(mensagem) == porta


def test_o_modulo_nao_chama_o_storm_no_exame(tmp_path: Path) -> None:
    """O exame das cinco linhas NÃO ganhou uma sexta — a tela não mudou.

    Interface só fecha com o olho dela, e o `--storm-usb` é leitura de
    terminal. A MORDIDA: acrescente o laudo a `exame()` e esta régua reprova,
    junto com `test_o_exame_devolve_as_cinco_linhas_na_ordem_da_tela`.
    """
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
