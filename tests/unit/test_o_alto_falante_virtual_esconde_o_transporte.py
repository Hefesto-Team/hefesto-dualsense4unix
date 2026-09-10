"""O-ALTO-FALANTE-VIRTUAL-01 — o alto-falante virtual esconde o transporte.

**O pedido dela, 29/08/2026:** alto-falante virtual *"no estilo do gamepad
virtual"*, para o som do controle funcionar **independente da máscara e do
transporte**. O contrato é o mesmo do vpad: o jogo escolhe um gamepad, não um
transporte — aqui, quem escolhe a saída escolhe um CONTROLE, não um sink.

**As duas decisões que a sprint deixava para ela já estão tomadas**, por
delegação (`docs/data/decisoes-dela.csv`, `D-0609-UM-NO-DE-SOM-POR-CONTROLE`):
um nó por controle, com o número do assento.

**O NOME MUDOU EM 09/09/2026, E QUEM O MUDOU FOI ELA.** Este arquivo aferia
`Alto-falante · P1` … `P4` e escrevia, como MORDIDA de um dos testes, *"troque
o rótulo por «Alto-falante do Controle N»"*. Era a leitura certa do mundo de
06/09 — a decisão de então era por DELEGAÇÃO. Ela decidiu o contrário
(`D-0909-OS-NOS-SE-CHAMAM-ALTO-FALANTE-E-MICROFONE-DO-CONTROLE-N`, palavra
dela: *"4a"*), e o par com «Microfone do Controle N» está na LÍNGUA DESTA
CASA. **O que era a mordida virou o produto**, e o que este arquivo mede agora
é o nome dela.

E o `sink_name` também tinha DOIS donos — `hefesto_alto_falante_<assento>`
aqui e `hefesto_som_<hex6>` em `integrations/alto_falante_bt`, que é o que o
produto de fato publica. Ficou o segundo: ele segue o APARELHO, e por isso
sobrevive à troca de assento tanto quanto à troca de cabo.

Cada teste deste arquivo diz, na docstring, **o que arrancar para vê-lo
reprovar**. Nenhum áudio real, nenhum módulo carregado no PipeWire de ninguém:
o produto devolve o PLANO de comandos, e o plano é o que se mede.

**E esta régua não é a bancada desta casa.** Os endereços são das faixas
sintéticas (`02fe00`, `aabbcc`), o terceiro controle nunca esteve nesta mesa, e
nada aqui depende dos dois DualSense daqui: uma prova que só passa com eles
mede a bancada, não a cura.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.audio_saida import (
    ASSENTOS,
    MOTIVO_NO_SEM_ASSENTO,
    MOTIVO_NO_SEM_PLACA_NO_CABO,
    MOTIVO_NO_SEM_PONTE_NO_RADIO,
    POR_CABO,
    POR_RADIO,
    TRANSPORTE_CABO,
    TRANSPORTE_RADIO,
    NoDeAltoFalante,
    no_do_controle,
    nome_do_alto_falante,
    plano_de_publicacao,
    rota_do_no,
)

# ---------------------------------------------------------------------------
# A bancada de mentira: dois controles no cabo, cada um no seu dispositivo USB
# ---------------------------------------------------------------------------

#: Faixas sintéticas da casa. NENHUM destes é um controle desta bancada.
_UNIQ_P1 = "02fe0011a1b2"
_UNIQ_P2 = "02fe0011a1b3"
_UNIQ_NUNCA_VISTO = "aabbcc7f0e01"

_SINK_P1 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)
_SINK_P2 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.2.analog-surround-40"
)

#: `pactl list sinks short` com os DOIS controles e uma HDMI no meio. Os dois
#: nomes de DualSense diferem só por um `-00`/`-00.2` — desempate posicional do
#: PipeWire, e não identidade. É a armadilha inteira num texto só.
_SINKS_CURTO = (
    f"59\t{_SINK_P1}\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED\n"
    "61\talsa_output.pci-0000_0c_00.4.iec958-stereo\tPipeWire"
    "\ts32le 2ch 48000Hz\tSUSPENDED\n"
    f"73\t{_SINK_P2}\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED\n"
)

_SINKS_LONGO = (
    f"Sink #59\n\tName: {_SINK_P1}\n\tProperties:\n"
    '\t\tsysfs.path = "/devices/pci0000:00/usb3/3-1/3-1:1.0/sound/card3"\n'
    f"Sink #73\n\tName: {_SINK_P2}\n\tProperties:\n"
    '\t\tsysfs.path = "/devices/pci0000:00/usb3/3-2/3-2:1.0/sound/card4"\n'
)

_USB_P1 = "/sys/devices/pci0000:00/usb3/3-1"
_USB_P2 = "/sys/devices/pci0000:00/usb3/3-2"


def _runner(curto: str = _SINKS_CURTO, longo: str = _SINKS_LONGO) -> Any:
    """Dublê do `pactl`: um texto por pergunta, nenhum processo de verdade.

    Ele sabe RECUSAR: com `curto=""` responde a lista vazia, que é o caminho de
    erro que a régua exercita — dublê que só sabe passar não é dublê.
    """

    def roda(argv: list[str]) -> str:
        if argv[:4] == ["pactl", "list", "sinks", "short"]:
            return curto
        if argv[:3] == ["pactl", "list", "sinks"]:
            return longo
        return ""

    return roda


@pytest.fixture
def usb_da_bancada(monkeypatch: pytest.MonkeyPatch) -> None:
    """O censo de USB que o `sink_do_controle` consulta, dublado.

    `sink_do_controle` importa `usb_pai_*` DENTRO da função, então trocar o
    atributo do módulo alcança a chamada — e é o que evita esta régua ir ao
    `/sys` da máquina que roda a suíte.
    """
    from hefesto_dualsense4unix.integrations import usb_pai

    monkeypatch.setattr(
        usb_pai,
        "usb_pai_por_uniq",
        lambda uniqs, **_: {
            u: {_UNIQ_P1: _USB_P1, _UNIQ_P2: _USB_P2}.get(u, "") for u in uniqs
        },
    )
    monkeypatch.setattr(
        usb_pai,
        "usb_pai_por_no",
        lambda mapa, **_: {_SINK_P1: _USB_P1, _SINK_P2: _USB_P2},
    )


def _entry(
    uniq: str,
    *,
    slot: int = 1,
    transporte: str = TRANSPORTE_CABO,
    flavor: str = "dualsense",
) -> dict[str, Any]:
    """Uma entrada de ``state_full.controllers``, com a MÁSCARA dentro.

    A máscara entra de propósito: ela é o que a invariante 3 proíbe de olhar.
    """
    return {
        "index": slot - 1,
        "player_slot": slot,
        "uniq": uniq,
        "transport": transporte,
        "gamepad": {"flavor": flavor},
    }


# ---------------------------------------------------------------------------
# 1. O MESMO NÓ, OS DOIS TRANSPORTES
# ---------------------------------------------------------------------------


def test_o_mesmo_controle_no_cabo_e_no_radio_e_o_mesmo_no() -> None:
    """Trocar o cabo pelo rádio não pode trocar o nome nem o id da saída.

    MORDIDA: derive o nome ou o id do transporte — por exemplo, fazendo
    `NoDeAltoFalante.id_do_no` devolver `f"{nome_do_sink(self.uniq)}_"
    f"{self.transporte}"` — e este teste reprova nas duas comparações. É o
    defeito que o nó existe para não ter: quem escolheu esta saída uma vez
    continua com ela escolhida depois que o controle sai do cabo.
    """
    no_cabo = no_do_controle(_entry(_UNIQ_P1, slot=1, transporte=TRANSPORTE_CABO))
    no_radio = no_do_controle(_entry(_UNIQ_P1, slot=1, transporte=TRANSPORTE_RADIO))

    assert no_cabo is not None
    assert no_radio is not None
    assert no_cabo.nome == no_radio.nome == "Alto-falante do Controle 1"
    assert no_cabo.id_do_no == no_radio.id_do_no == "hefesto_som_11a1b2"


def test_o_nome_e_o_id_vem_do_assento_e_de_mais_nada() -> None:
    """Quatro assentos, quatro nomes, e o número é o do JOGADOR.

    A palavra é DELA (`D-0909-OS-NOS-SE-CHAMAM-…`, *"4a"*): «Alto-falante do
    Controle 1»… MORDIDA: volte o rótulo para `f"Alto-falante · {a.upper()}"`,
    que é o que esta casa escrevia até 08/09, e as quatro comparações caem.
    """
    assert [nome_do_alto_falante(a) for a in ASSENTOS] == [
        "Alto-falante do Controle 1",
        "Alto-falante do Controle 2",
        "Alto-falante do Controle 3",
        "Alto-falante do Controle 4",
    ]


def test_um_assento_que_o_desenho_nao_tem_nao_ganha_no() -> None:
    """Um `p5` na lista de saída seria um nó que a tela não desenha.

    MORDIDA: tire a guarda `if assento not in ASSENTOS` de
    `nome_do_alto_falante` e o produto passa a nomear assentos que não existem.
    """
    assert nome_do_alto_falante("p5") == ""
    assert no_do_controle({"player_slot": 5, "uniq": _UNIQ_NUNCA_VISTO}) is None
    assert rota_do_no(None).motivo == MOTIVO_NO_SEM_ASSENTO


def test_os_assentos_daqui_sao_os_mesmos_do_desenho() -> None:
    """Duas listas de assentos é como esta casa fabrica divergência silenciosa.

    MORDIDA: acrescente um `p5` a `ASSENTOS` e a comparação com o dono do lado
    da tela (`interface/pacotes.TODOS_OS_LUGARES`) reprova.
    """
    from hefesto_dualsense4unix.interface.pacotes import TODOS_OS_LUGARES

    assert set(ASSENTOS) == set(TODOS_OS_LUGARES)


# ---------------------------------------------------------------------------
# 2. O SINK É RESOLVIDO PELA IDENTIDADE, NÃO PELO TEXTO
# ---------------------------------------------------------------------------


def test_dois_controles_no_cabo_e_cada_no_entrega_no_sink_do_seu(
    usb_da_bancada: None,
) -> None:
    """Dois DualSense no cabo: cada nó entrega no sink DAQUELE controle.

    Os dois nomes de sink diferem só por um `-00`/`-00.2`, que é desempate
    posicional do PipeWire e não identidade. Quem separa os dois é o dispositivo
    USB em que a placa e o HID penduram juntos.

    MORDIDA: troque a chamada a `sink_do_controle` dentro de `rota_do_no` por um
    casamento de texto —

        alvos = [s for s in sinks if s.startswith("alsa_output.usb-")]
        alvo = alvos[0] if alvos else ""

    — e os DOIS nós passam a apontar para `_SINK_P1`: o som do P2 sai no
    alto-falante do P1. É o erro que `audio_saida.sink_do_controle` já existe
    para não cometer.
    """
    mesa = [_UNIQ_P1, _UNIQ_P2]

    plano_p1 = plano_de_publicacao(
        no_do_controle(_entry(_UNIQ_P1, slot=1)), mesa, runner=_runner()
    )
    plano_p2 = plano_de_publicacao(
        no_do_controle(_entry(_UNIQ_P2, slot=2)), mesa, runner=_runner()
    )

    assert plano_p1.sink == _SINK_P1
    assert plano_p2.sink == _SINK_P2
    assert plano_p1.sink != plano_p2.sink
    assert plano_p1.por_onde == plano_p2.por_onde == POR_CABO


def test_o_plano_do_cabo_liga_o_no_ao_sink_pelos_dois_canais_da_frente(
    usb_da_bancada: None,
) -> None:
    """Com rota, o plano tem as DUAS metades: criar o nó e ligá-lo ao aparelho.

    O mapa (`audio.alto_falante@dualsense`, `cabo_canal`) diz *canais 1-2 do
    sink `alsa_output.usb-...analog-surround-40`*; numa placa `surround-40` os
    canais 1 e 2 são `front-left` e `front-right`.

    MORDIDA: devolva só o `module-null-sink` e o nó nasce sem destino — um sink
    na lista de saída dela que aceita som e não o leva a lugar nenhum.
    """
    plano = plano_de_publicacao(
        no_do_controle(_entry(_UNIQ_P1, slot=1)), [_UNIQ_P1, _UNIQ_P2], runner=_runner()
    )

    assert plano.vai_publicar is True
    assert len(plano.argv) == 2
    criar, ligar = plano.argv
    assert "module-null-sink" in criar
    assert "sink_name=hefesto_som_11a1b2" in criar
    assert any(
        "device.description='Alto-falante do Controle 1'" in arg for arg in criar
    ), criar
    assert "module-loopback" in ligar
    assert "source=hefesto_som_11a1b2.monitor" in ligar
    assert f"sink={_SINK_P1}" in ligar
    assert "channel_map=front-left,front-right" in ligar


def test_sem_placa_de_som_no_cabo_o_no_diz_o_que_fazer() -> None:
    """O `pactl` sem nenhum sink de DualSense é "não sei", e "não sei" se diz.

    **O NÓ EXISTE MESMO ASSIM — decisão dela de 08/09/2026**
    (`D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`): *"nó que some quebra o
    jogo que o escolheu"*. O que falta sem placa é a ROTA, e é ela que o plano
    recusa — com a frase, e sem um único `module-loopback`.

    MORDIDA: devolva um `module-loopback` neste ramo e o produto liga o som a
    um sink que ele não resolveu.
    """
    plano = plano_de_publicacao(
        no_do_controle(_entry(_UNIQ_NUNCA_VISTO, slot=3)), runner=_runner(curto="")
    )

    assert plano.vai_publicar is True
    assert plano.tem_rota is False
    assert len(plano.argv) == 1
    assert "module-null-sink" in plano.argv[0]
    assert not any("module-loopback" in a for argv in plano.argv for a in argv)
    assert plano.motivo == MOTIVO_NO_SEM_PLACA_NO_CABO


# ---------------------------------------------------------------------------
# 3. SEM ROTA, ELE DIZ — e não engole o áudio
# ---------------------------------------------------------------------------


def test_no_radio_sem_ponte_o_no_recusa_com_a_frase() -> None:
    """A queixa histórica dela: *"na hora do vamos ver a versão de BT não funcionava"*.

    O nó EXISTE (tem nome e id, os mesmos do cabo) e reporta indisponível com a
    frase do quê/por quê/o que fazer.

    **O QUE MUDOU EM 08/09/2026, e foi ELA:** o nó por rádio é PUBLICADO —
    `D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`. Este teste aferia
    `vai_publicar is False`, que era o mundo da decisão por delegação de 06/09.
    O que ele mede agora é o par: o nó existe **e** a frase está lá.

    MORDIDA: apague o `motivo` deste ramo — devolva `PlanoDoNo(True,
    argv=(argv_para_publicar_o_no(no),))` e nada mais. O nó aparece na lista de
    saída dela, ela escolhe, e o som some **sem uma palavra**, que é a metade
    da invariante 4 que a decisão dela NÃO derrubou.
    """
    no = no_do_controle(_entry(_UNIQ_P1, slot=1, transporte=TRANSPORTE_RADIO))
    assert no is not None

    plano = plano_de_publicacao(no)

    assert plano.nome == "Alto-falante do Controle 1"
    assert plano.id_do_no == "hefesto_som_11a1b2"
    assert plano.vai_publicar is True
    assert plano.tem_rota is False
    assert len(plano.argv) == 1
    assert not any("module-loopback" in a for argv in plano.argv for a in argv)
    assert plano.motivo == MOTIVO_NO_SEM_PONTE_NO_RADIO


def test_a_frase_do_radio_diz_as_tres_coisas() -> None:
    """O quê, por quê, e o que fazer — e sem palavra de dentro da máquina.

    MORDIDA: troque a frase por *"indisponível"* e as três asserções caem;
    escreva `hidraw` nela e a última cai.
    """
    frase = MOTIVO_NO_SEM_PONTE_NO_RADIO

    assert "não chega a este controle pelo rádio" in frase
    assert "ainda não sabe montar o pacote de áudio" in frase
    assert "Ligue-o no cabo" in frase
    for proibida in ("hidraw", "uniq", "MAC", "sink", "mesa"):
        assert proibida not in frase


def test_quando_a_ponte_do_radio_existir_o_no_publica_por_ela() -> None:
    """A superfície já sabe receber a ponte da P5 — ela é que ainda não existe.

    MORDIDA: ignore o `ponte_do_radio` e recuse sempre. A sprint que trouxer a
    ponte teria de reabrir este módulo em vez de só passá-la aqui.
    """
    no = NoDeAltoFalante("p2", _UNIQ_P2, TRANSPORTE_RADIO)

    plano = plano_de_publicacao(no, ponte_do_radio=lambda: True)

    assert plano.vai_publicar is True
    assert plano.por_onde == POR_RADIO
    assert plano.sink == ""
    assert len(plano.argv) == 1
    assert "sink_name=hefesto_som_11a1b3" in plano.argv[0]


def test_ponte_do_radio_que_diz_nao_e_o_mesmo_que_ponte_nenhuma() -> None:
    """O dublê tem de saber RECUSAR, e a régua exercita as duas respostas."""
    no = NoDeAltoFalante("p2", _UNIQ_P2, TRANSPORTE_RADIO)

    assert plano_de_publicacao(no, ponte_do_radio=lambda: False).motivo == (
        MOTIVO_NO_SEM_PONTE_NO_RADIO
    )
    assert plano_de_publicacao(no, ponte_do_radio=None).motivo == (
        MOTIVO_NO_SEM_PONTE_NO_RADIO
    )


# ---------------------------------------------------------------------------
# 4. A MÁSCARA NÃO MUDA NADA
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("flavor", ["dualsense", "xbox", "nintendo"])
def test_a_mascara_nao_muda_o_no(flavor: str, usb_da_bancada: None) -> None:
    """Os três valores de máscara, o mesmo nó e o mesmo plano.

    Pedido dela, literal: o som funciona *independente da máscara*. Som não é
    entrada, e a máscara é do gamepad.

    MORDIDA: faça `no_do_controle` ler `entry["gamepad"]["flavor"]` e entrar com
    ele no nome (ou recusar fora de `dualsense`) — as três execuções divergem e
    duas reprovam.
    """
    plano = plano_de_publicacao(
        no_do_controle(_entry(_UNIQ_P1, slot=1, flavor=flavor)),
        [_UNIQ_P1, _UNIQ_P2],
        runner=_runner(),
    )

    assert plano.nome == "Alto-falante do Controle 1"
    assert plano.id_do_no == "hefesto_som_11a1b2"
    assert plano.sink == _SINK_P1
    assert plano.vai_publicar is True


def test_a_mascara_nao_entra_em_assinatura_nenhuma() -> None:
    """A invariante escrita como régua: `flavor` não é parâmetro desta seção.

    MORDIDA: acrescente `flavor: str = "dualsense"` a qualquer uma das cinco e
    este teste nomeia a que ganhou o parâmetro.
    """
    import inspect

    from hefesto_dualsense4unix.app import audio_saida

    for nome in (
        "nome_do_alto_falante",
        "no_do_controle",
        "assento_do_controle",
        "rota_do_no",
        "plano_de_publicacao",
    ):
        parametros = inspect.signature(getattr(audio_saida, nome)).parameters
        assert "flavor" not in parametros, nome
        assert "mascara" not in parametros, nome


# ---------------------------------------------------------------------------
# 5. A RÉGUA NÃO É A BANCADA DESTA CASA
# ---------------------------------------------------------------------------


def test_um_controle_que_nunca_esteve_aqui_ganha_o_mesmo_no() -> None:
    """Nenhum passo desta régua depende dos dois DualSense desta bancada.

    O `_UNIQ_NUNCA_VISTO` é de outra faixa sintética e não tem nó USB no dublê:
    ele cai no ramo honesto do "não sei", com nome e id normais.

    MORDIDA: amarre o nome ou o id ao endereço do controle e este teste passa a
    exigir um aparelho específico para dar verde.
    """
    no = no_do_controle(_entry(_UNIQ_NUNCA_VISTO, slot=4))
    assert no is not None
    assert no.nome == "Alto-falante do Controle 4"

    plano = plano_de_publicacao(no, [_UNIQ_NUNCA_VISTO], runner=_runner(curto=""))
    assert plano.vai_publicar is True
    assert plano.tem_rota is False
    assert plano.motivo == MOTIVO_NO_SEM_PLACA_NO_CABO
