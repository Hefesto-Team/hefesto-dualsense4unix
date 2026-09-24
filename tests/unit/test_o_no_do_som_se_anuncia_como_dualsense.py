"""A-FORJA-VALIDA-O-SOM-01 — o nó do som se anuncia como DualSense, para o JOGO.

Hoje a casa sabe que o alto-falante do controle obedece ao NOSSO comando, e não
sabe se obedece a um JOGO: sob Proton o nome do alto-falante que o jogo lista é
a ``device.description`` do nó (``winepulse.drv/pulse.c``, ``get_device_name``),
e um jogo que procura o alto-falante do controle procura ``DualSense`` ou
``Wireless Controller`` — as strings USB da Sony. O nosso nó dizia só
«Alto-falante do Controle 1».

A DECISÃO DELA, 23/09/2026, é a FORMA A: «Alto-falante do Controle N (DualSense
Wireless Controller)» — o nome dela na frente, igual para o microfone, os
quatro controles, o USB e o BT. A decisão está DIGITADA aqui de propósito: a
régua lê a decisão, não o dono (``vestido_de_dualsense.com_o_nome_da_sony``).
Mude o dono sem mudar a decisão e esta régua reprova.

AS MORDIDAS, uma por teste, e cada uma diz o que arrancar:

1. o sufixo da Sony sai de ``com_o_nome_da_sony`` → o jogo não acha o nó;
2. o nome da Sony (fabricante, produto, apelido) sai de
   ``propriedades_do_sink`` → o monitor do nó chega ao Wine acima do teto;
3. a identidade (barramento, VID, PID, âncora) entra no nó do alto-falante →
   o GE passa a ver DOIS aparelhos de áudio DualSense para o mesmo controle;
4. o ``sysfs.path`` sai de ``campos_da_identidade`` → o ``ContainerId`` do
   endpoint de háptica sai zerado, e o ``pactl`` continua respondendo ``ok``;
5. o nome de DENTRO ganha a palavra da Sony → o nó entra na lista das PLACAS
   de DualSense, e a E6 aconteceu por acidente;
6. o ``sem_o_nome_da_sony`` sai de ``numero_do_rotulo`` → todo nó perde o
   número e o rótulo nunca mais acompanha o assento.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable, Iterator

import pytest

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.integrations import alto_falante_bt as som
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as mic
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as haptica
from hefesto_dualsense4unix.integrations import fontes_de_captura as fontes
from hefesto_dualsense4unix.integrations import vestido_de_dualsense as vestido

#: A FORMA A, decisão dela de 23/09/2026 — digitada, não lida do dono.
_SONY = " (DualSense Wireless Controller)"

#: O teto do Wine, do fonte que roda nesta máquina: ``MAX_DEVICE_NAME_LEN`` em
#: ``proton-hefesto/fonte/wine/dlls/winepulse.drv/pulse.c``. Acima dele o
#: ``get_device_name`` troca a frase inteira pelo ``device.product.name``.
_TETO_DO_WINE = 62

#: O que o ``pipewire-pulse`` põe na frente do nome do monitor de um sink.
_MONITOR_DE = "Monitor of "

#: Faixa sintética da casa — nenhum controle desta bancada.
_UNIQ = "02:fe:00:11:a1:b2"


@pytest.fixture
def assento() -> Iterator[Callable[[int | None], None]]:
    """Põe o numerador de assento a responder um número, e devolve o de antes."""
    anterior = mic.registrar_numerador_de_assento(None)

    def _por(numero: int | None) -> None:
        mic.registrar_numerador_de_assento(None if numero is None else (lambda _u: numero))

    try:
        yield _por
    finally:
        mic.registrar_numerador_de_assento(anterior)


def _como_o_servidor_le(argumento: str, chave: str) -> dict[str, str]:
    """``chave="a='x y' b=1"`` → ``{"a": "x y", "b": "1"}``, como o ``pipewire-pulse``.

    O servidor tira as aspas DUPLAS de fora e parte o resto respeitando as
    SIMPLES — é o parser que cortava tudo depois do primeiro espaço quando as
    duplas faltavam (06/09/2026). Ler o ARGV cru deu verde sobre aquele defeito;
    esta função lê o que o NÓ recebe.
    """
    prefixo = f'{chave}="'
    assert argumento.startswith(prefixo) and argumento.endswith('"'), argumento
    miolo = argumento[len(prefixo) : -1]
    campos: dict[str, str] = {}
    for pedaco in shlex.split(miolo):
        nome, igual, valor = pedaco.partition("=")
        assert igual, f"campo sem valor no argumento: {pedaco!r}"
        campos[nome] = valor
    return campos


class _PactlFalso:
    """Dublê do ``pactl`` que ACEITA e RECUSA — as duas respostas são exercidas."""

    def __init__(self, *, aceita: bool = True) -> None:
        self.aceita = aceita
        self.chamadas: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str | None:
        self.chamadas.append(list(argv))
        if argv[:2] == ["pactl", "load-module"]:
            return "4242\n" if self.aceita else "Failure: Module initialization failed\n"
        return ""


def _props_do_no_publicado(descricao: str) -> dict[str, str]:
    """As propriedades do nó do alto-falante, lidas do ``load-module`` do DAEMON."""
    pactl = _PactlFalso()
    no = som.SinkVirtualPipeWire(uniq=_UNIQ, descricao=descricao, runner=pactl)
    assert no.iniciar() is True
    carga = [a for a in pactl.chamadas if a[:3] == ["pactl", "load-module", "module-null-sink"]]
    assert len(carga) == 1, pactl.chamadas
    argumento = next(a for a in carga[0] if a.startswith("sink_properties="))
    return _como_o_servidor_le(argumento, "sink_properties")


# ---------------------------------------------------------------------------
# 1. O NOME que o jogo lê — a forma A, nos quatro assentos e sem assento
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("numero", [1, 2, 3, 4, None])
def test_o_nome_que_o_jogo_le_e_a_forma_a(assento, numero: int | None) -> None:
    """Os dois nós de cada controle levam o nome da Sony atrás do nome dela.

    MORDIDA 1: faça ``com_o_nome_da_sony`` devolver o rótulo sem o sufixo e as
    duas igualdades caem — o nó continua de pé e jogo nenhum o reconhece.
    """
    assento(numero)
    sufixo = "" if numero is None else f" {numero}"

    assert som.descricao_do_alto_falante(_UNIQ) == f"Alto-falante do Controle{sufixo}{_SONY}"
    assert mic.descricao_do_microfone(_UNIQ) == f"Microfone do Controle{sufixo}{_SONY}"


@pytest.mark.parametrize("numero", [1, 2, 3, 4])
def test_um_jogo_que_casa_por_substring_acha_os_dois(assento, numero: int) -> None:
    """O teste que o JOGO faz: alguma das palavras da Sony no nome, sem caixa.

    As marcas são as da casa (``fontes_de_captura.MARCADORES_DUALSENSE``), que
    são as mesmas que um motor de jogo procura — e as que o nó NÃO tinha.
    """
    assento(numero)
    for rotulo in (som.descricao_do_alto_falante(_UNIQ), mic.descricao_do_microfone(_UNIQ)):
        baixa = rotulo.lower()
        assert any(marca in baixa for marca in fontes.MARCADORES_DUALSENSE), rotulo


@pytest.mark.parametrize("numero", [1, 2, 3, 4, None])
def test_o_nome_cabe_no_teto_do_wine(assento, numero: int | None) -> None:
    """Acima de 62 o Wine joga a frase fora — e com ela o «Controle N».

    Sem o número os quatro controles chegariam ao jogo com o MESMO nome, que é o
    defeito de dois «Alto-falante do Controle 1» com outra roupa.
    """
    assento(numero)
    for rotulo in (som.descricao_do_alto_falante(_UNIQ), mic.descricao_do_microfone(_UNIQ)):
        assert len(rotulo) <= _TETO_DO_WINE, (len(rotulo), rotulo)
    assert vestido.TETO_DO_NOME_NO_WINE == _TETO_DO_WINE


def test_o_sufixo_nunca_come_o_numero() -> None:
    """Rótulo que não cabe com o sufixo sai SEM o sufixo, nunca sem o número."""
    comprido = "Alto-falante do Controle de quem joga do lado esquerdo 4"
    assert len(comprido + _SONY) > _TETO_DO_WINE
    assert vestido.com_o_nome_da_sony(comprido) == comprido
    # E a forma é idempotente: vestir duas vezes não põe dois sufixos.
    uma = vestido.com_o_nome_da_sony("Microfone do Controle 2")
    assert vestido.com_o_nome_da_sony(uma) == uma == "Microfone do Controle 2" + _SONY


@pytest.mark.parametrize("assento_da_tela", ["p1", "p2", "p3", "p4"])
def test_a_janela_e_o_daemon_dizem_o_mesmo_nome(assento, assento_da_tela: str) -> None:
    """Os dois caminhos que nomeiam o nó — pelo ``uniq`` e pelo assento — concordam.

    MORDIDA: devolva a f-string antiga em ``audio_saida.nome_do_alto_falante``
    e a janela passa a publicar um nó com um nome e o daemon com outro.
    """
    numero = int(assento_da_tela[1:])
    assento(numero)
    assert audio_saida.nome_do_alto_falante(assento_da_tela) == som.descricao_do_alto_falante(_UNIQ)


# ---------------------------------------------------------------------------
# 2. O NÓ DO ALTO-FALANTE veste o nome da Sony, e só o nome
# ---------------------------------------------------------------------------


def test_o_no_do_alto_falante_veste_o_nome_da_sony() -> None:
    """Fabricante, produto e apelido chegam ao NÓ — lidos como o servidor os lê.

    MORDIDA 2: tire ``*campos_do_nome()`` de ``propriedades_do_sink`` e os três
    somem daqui.
    """
    props = _props_do_no_publicado("Alto-falante do Controle 1" + _SONY)

    assert props["device.description"] == "Alto-falante do Controle 1" + _SONY
    assert props["device.vendor.name"] == "Sony Interactive Entertainment"
    assert props["device.product.name"] == "DualSense Wireless Controller"
    assert props["node.nick"] == "DualSense Wireless Controller"
    # O que já estava lá não pode sair por causa do vestido.
    assert props["priority.session"] == str(som.PRIORIDADE_SESSAO_DO_SOM)
    assert props["device.icon_name"] == "audio-speakers"


def test_o_monitor_tem_nome_de_reserva_no_wine(assento) -> None:
    """O monitor do nó passa do teto, e é o ``device.product.name`` que o salva.

    O ``pipewire-pulse`` chama o monitor de «Monitor of <descrição>». Com a
    forma A isso dá 69 caracteres; acima do teto o Wine monta o nome a partir do
    ``device.product.name`` — sem ele, o nome comprido chega inteiro ao jogo, e
    é esse comprimento que derruba o aplicativo que o teto existe para proteger.
    """
    assento(1)
    rotulo = som.descricao_do_alto_falante(_UNIQ)
    assert len(_MONITOR_DE + rotulo) > _TETO_DO_WINE
    props = _props_do_no_publicado(rotulo)
    reserva = props.get("device.product.name", "")
    assert reserva, "o monitor do nó chega ao Wine sem nome de reserva"
    assert len(_MONITOR_DE + reserva) <= _TETO_DO_WINE


def test_o_no_do_alto_falante_nao_veste_a_identidade() -> None:
    """Barramento, VID, PID e âncora ficam com o endpoint de háptica.

    O GE-Proton pinado chama de aparelho de áudio DualSense todo nó com ``usb``
    + ``054c`` + ``0ce6`` no proplist (``proton-ds5-haptic``, patch 0013) — e o
    endpoint de háptica existe para ser o ÚNICO desse controle.

    MORDIDA 3: some ``campos_da_identidade`` ao ``propriedades_do_sink`` e
    esta régua reprova.
    """
    props = _props_do_no_publicado("Alto-falante do Controle 1" + _SONY)
    for chave in ("device.bus", "device.vendor.id", "device.product.id", "sysfs.path"):
        assert chave not in props, f"o nó do alto-falante declarou {chave}={props[chave]!r}"


def test_a_janela_publica_o_mesmo_no_que_o_daemon(assento) -> None:
    """O plano da janela (``argv_para_publicar_o_no``) leva as MESMAS propriedades.

    São dois os que publicam o nó; um vestido que só um deles levasse poria na
    lista dela dois nós diferentes com o mesmo nome.
    """
    assento(2)
    no = audio_saida.NoDeAltoFalante(assento="p2", uniq=_UNIQ)
    argv = audio_saida.argv_para_publicar_o_no(no)
    argumento = next(a for a in argv if a.startswith("sink_properties="))
    da_janela = _como_o_servidor_le(argumento, "sink_properties")
    do_daemon = _props_do_no_publicado(som.descricao_do_alto_falante(_UNIQ))
    assert da_janela == do_daemon


# ---------------------------------------------------------------------------
# 3. O ENDPOINT DE HÁPTICA lê a identidade do mesmo dono
# ---------------------------------------------------------------------------


def test_o_endpoint_de_haptica_declara_a_ancora() -> None:
    """A identidade do endpoint sai de ``campos_da_identidade``, com a âncora dele.

    MORDIDA 4: tire a linha do ``sysfs.path`` de ``campos_da_identidade`` e o
    ``ContainerId`` que o Wine calcula sai ZERADO — com o ``pactl`` dando ``ok``,
    que é a forma de instrumento falso que esta casa mais paga.
    """
    ancora = haptica.Ancora(
        syspath="/devices/pci0000:00/0000:00:14.0/usb3/3-4",
        declarado="/devices/pci0000:00/0000:00:14.0/usb3/3-4/3-4:1.0",
    )
    props = _como_o_servidor_le(
        haptica.propriedades_do_endpoint(_UNIQ, ancora), "sink_properties"
    )
    assert props["device.bus"] == "usb"
    assert props["device.vendor.id"] == "054c"
    assert props["device.product.id"] == "0ce6"
    assert props["sysfs.path"] == ancora.declarado
    assert props["device.vendor.name"] == "Sony Interactive Entertainment"


def test_sem_ancora_nao_ha_identidade() -> None:
    """«Sou USB da Sony» sem dizer de qual aparelho é pior que não dizer nada."""
    assert vestido.campos_da_identidade("") == ()
    assert vestido.campos_da_identidade("   ") == ()
    com = vestido.campos_da_identidade("/devices/x/3-4:1.0")
    assert "sysfs.path=/devices/x/3-4:1.0" in com


# ---------------------------------------------------------------------------
# 4. O NOME DE DENTRO não mudou — a regressão que a sprint mandou travar
# ---------------------------------------------------------------------------


def test_o_nome_de_dentro_nao_ganhou_a_palavra_da_sony() -> None:
    """O nó continua FORA da lista das placas de DualSense, que casa pelo NOME.

    ``sinks_dualsense`` responde *"que placas de DualSense há na máquina"*, e é
    por nome de dentro que ele casa. O vestido mexe no que o JOGO lê e não pode
    mexer nisto; se o nó entrar aqui, alguém mudou o nome de dentro sem
    declarar.

    MORDIDA 5: ponha ``dualsense`` no ``PREFIXO_SINK_DO_SOM`` e o nó entra.
    """
    nosso = som.nome_do_sink(_UNIQ)
    placa = (
        "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller"
        "-00.HiFi__Speaker__sink"
    )
    curta = (
        f"593\t{nosso}\tPipeWire\ts16le 2ch 48000Hz\tRUNNING\n"
        f"551\t{placa}\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED\n"
    )
    assert nosso and not any(m in nosso.lower() for m in fontes.MARCADORES_DUALSENSE)
    assert fontes.sinks_dualsense(curta) == [placa]


# ---------------------------------------------------------------------------
# 5. O RÓTULO continua acompanhando o assento, através do sufixo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("numero", [1, 2, 3, 4])
def test_o_numero_se_le_atraves_do_sufixo(numero: int) -> None:
    """``numero_do_rotulo`` acha o assento nas duas formas — a de antes e a A.

    MORDIDA 6: tire o ``sem_o_nome_da_sony`` de ``numero_do_rotulo`` e a forma
    A devolve ``None`` — o nó perde o número e ``rotulo_envelheceu`` nunca mais
    republica nada.
    """
    assert mic.numero_do_rotulo(f"Alto-falante do Controle {numero}{_SONY}") == numero
    assert mic.numero_do_rotulo(f"Microfone do Controle {numero}{_SONY}") == numero
    assert mic.numero_do_rotulo(f"Alto-falante do Controle {numero}") == numero


def test_o_no_no_ar_com_o_nome_de_antes_renasce_com_a_forma_a() -> None:
    """Depois do install, os nós que estão no ar com o nome velho mudam UMA vez.

    É a migração: o nó publicado antes da forma A tem o rótulo sem o sufixo, e
    ele envelheceu — o daemon o republica quando o nó ficar em silêncio. E a
    forma A igual a si mesma não envelhece, senão o nó renasceria em laço.
    """
    velho = "Alto-falante do Controle 1"
    novo = velho + _SONY
    assert mic.rotulo_envelheceu(velho, novo) is True
    assert mic.rotulo_envelheceu(novo, novo) is False
    # Perder o número continua nunca contando como envelhecer.
    assert mic.rotulo_envelheceu(novo, "Alto-falante do Controle" + _SONY) is False
