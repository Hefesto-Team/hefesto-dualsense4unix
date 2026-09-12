"""SOM-POR-CONTROLE-01 — o mix ou o SFX, caindo em CADA controle.

**O pedido dela, 08/09/2026, à noite:** *"o lance dos 4 mic virtuais via bt pra
cada controle e cavbo e os somns seja hdmi completo seja o canal do sfx caindo
pra cada controle. nao esquece disso."*  <!-- noqa-acento: citação dela -->

O QUE ESTE ARQUIVO MEDE, e o que ele NÃO mede
----------------------------------------------
Mede o NOSSO lado: o nome do nó, o `sink_name`, a rota, a fonte e o ciclo de
vida — tudo com dublê, sem um byte de PCM e sem um `pactl` de verdade. **Não
mede som**: que o alto-falante do P2 toque o que entrou no nó do P2 é a orelha
dela, na bancada, e está declarado na entrega.

A MEDIÇÃO QUE ORIGINOU A SPRINT, refeita em 09/09/2026 às 19h55 com os QUATRO
DualSense na mesa dela (dois no cabo, dois no rádio), por
`scripts/ensaios/os_nos_de_som_por_controle.py`, que é leitura pura::

    saída padrão .... alsa_output.pci-…hdmi-stereo
    controle    transp.  placa USB  alto-falante virtual  mic virtual
    …:f0        rádio    —          NÃO EXISTE            NÃO EXISTE
    …:ab        cabo     sim        NÃO EXISTE            NÃO EXISTE
    …:03        rádio    —          NÃO EXISTE            NÃO EXISTE
    …:d8        cabo     sim        NÃO EXISTE            NÃO EXISTE
    rc=1 · `pactl list short modules | grep -c loopback` = 0

**Zero nós, com DUAS sprints marcadas `feita`.** As duas causas foram medidas
nesta árvore, e nenhuma era "faltou código":

1. **o `AltoFalanteSubsystem` é órfão** — `grep` por `alto_falante` em
   `daemon/subsystems/__init__.py`, `daemon/lifecycle.py` e
   `daemon/connection.py` devolve zero. Ele era órfão *de propósito*: sem
   `module-loopback`, o nó publicado é um sumidouro, e há régua que trava esse
   par (`test_o_no_de_som_nao_nasce_sumidouro.py`);
2. **e o nome não era o dela.** Mesmo ligado, o nó nasceria
   `Alto-falante · P1` com `sink_name=hefesto_alto_falante_p1` — e o
   instrumento procura «Alto-falante do Controle N» e `hefesto_som_<hex6>`.
   Eram DOIS `sink_name` para o mesmo nó, e o produto publica o segundo.

Esta sprint mata a causa 1 (a rota existe) e a causa 2 (o nome é o dela). A
terceira — as três linhas do registro — está fora da posse e vai na entrega.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.audio_saida import (
    NoDeAltoFalante,
    no_do_controle,
    nome_do_alto_falante,
    plano_de_publicacao,
)
from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
    AltoFalanteSubsystem,
    ControleNaLista,
    GerenciadorDeNosDeSom,
)
from hefesto_dualsense4unix.integrations import alto_falante_bt as som
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as mic
from hefesto_dualsense4unix.profiles.schema import ProfileSpeakerConfig

#: Faixas sintéticas da casa. NENHUM destes é um controle desta bancada — uma
#: régua que só passa com os quatro DualSense dela mede a bancada, não a cura.
_UNIQ_P1 = "02fe0011a1b2"
_UNIQ_P2 = "02fe0011a1b3"

_SINK_P1 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)
_SINK_P2 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.2.analog-surround-40"
)
_HDMI = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"


class _Gravador:
    """Um `runner` de `pactl` que ACEITA e guarda — e sabe RECUSAR.

    Devolve um id de módulo crescente para todo `load-module`, `""` para o que
    ele não conhece, e `None` quando `recusa=True` — que é o mundo do PipeWire
    parado. Um dublê que só sabe aceitar nunca exercita o caminho de erro.
    """

    def __init__(self, *, recusa: bool = False) -> None:
        self.argvs: list[list[str]] = []
        self.recusa = recusa
        self._proximo = 100

    def __call__(self, argv: list[str]) -> str | None:
        self.argvs.append(list(argv))
        if self.recusa:
            return None
        if "load-module" in argv:
            self._proximo += 1
            return f"{self._proximo}\n"
        if "get-default-sink" in argv:
            return f"{_HDMI}\n"
        return ""

    @property
    def linhas(self) -> list[str]:
        return [" ".join(a) for a in self.argvs]


def _runner_de_leitura(*, com_placa: bool = True) -> Any:
    """O `pactl` de LEITURA da bancada de mentira: dois DualSense no cabo."""
    curto = (
        f"62\t{_HDMI}\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
        f"134584\t{_SINK_P1}\tPipeWire\ts16le 4ch 48000Hz\tIDLE\n"
        f"135079\t{_SINK_P2}\tPipeWire\ts16le 4ch 48000Hz\tIDLE\n"
    ) if com_placa else f"62\t{_HDMI}\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"

    def runner(argv: list[str]) -> str:
        if "get-default-sink" in argv:
            return f"{_HDMI}\n"
        if "short" in argv:
            return curto
        return ""

    return runner


@pytest.fixture()
def usb_da_bancada(monkeypatch: pytest.MonkeyPatch) -> None:
    """O casamento por dispositivo USB, dublado — é ele que separa P1 de P2."""
    from hefesto_dualsense4unix.integrations import fontes_de_captura

    def escolher(sinks: Any, uniq: str, conhecidos: Any, usb: Any) -> str:
        return {_UNIQ_P1: _SINK_P1, _UNIQ_P2: _SINK_P2}.get(uniq, "")

    monkeypatch.setattr(fontes_de_captura, "escolher_sink", escolher)


def _entry(uniq: str, slot: int) -> dict[str, Any]:
    return {"uniq": uniq, "player_slot": slot, "transport": "usb"}


# ---------------------------------------------------------------------------
# 1. O NOME É O DELA, e o par com o microfone é a MESMA gramática
# ---------------------------------------------------------------------------


def test_o_no_se_chama_alto_falante_do_controle_n() -> None:
    """Decisão dela, 09/09/2026 (*"4a"*). Era «Alto-falante · P1» até 08/09.

    MORDIDA: volte `nome_do_alto_falante` para `f"Alto-falante · {a.upper()}"`
    e as quatro comparações caem — e com elas cai o instrumento de bancada, que
    procura exatamente esta palavra na lista viva.
    """
    assert nome_do_alto_falante("p1") == "Alto-falante do Controle 1"
    assert nome_do_alto_falante("p4") == "Alto-falante do Controle 4"
    assert nome_do_alto_falante("p5") == ""
    assert som.NOME_DO_ALTO_FALANTE_DO_CONTROLE == "Alto-falante do Controle"


def test_o_par_com_o_microfone_e_a_mesma_gramatica() -> None:
    """«Alto-falante do Controle 2» e «Microfone do Controle 2», lado a lado.

    Os dois rótulos vivem na MESMA lista de som dela. Divergir em uma palavra
    — «Controle» contra «controle», o número num e não no outro — é a lista
    dizendo duas coisas sobre o mesmo aparelho.

    MORDIDA: troque o sufixo de um dos dois e a comparação de forma reprova.
    """
    anterior = mic.registrar_numerador_de_assento(lambda _u: 2)
    try:
        assert som.descricao_do_alto_falante(_UNIQ_P1) == "Alto-falante do Controle 2"
        assert mic.descricao_do_microfone(_UNIQ_P1) == "Microfone do Controle 2"
    finally:
        mic.registrar_numerador_de_assento(anterior)


def test_sem_assento_sabido_nao_se_inventa_numero() -> None:
    """Dois «Alto-falante do Controle 1» mentem sobre qual é qual.

    MORDIDA: devolva `1` quando o numerador diz `None` e a lista dela ganha
    quatro rótulos idênticos com número — pior que quatro sem número.
    """
    anterior = mic.registrar_numerador_de_assento(None)
    try:
        assert som.descricao_do_alto_falante(_UNIQ_P1) == "Alto-falante do Controle"
    finally:
        mic.registrar_numerador_de_assento(anterior)


def test_o_endereco_dela_nunca_entra_no_rotulo() -> None:
    """O MAC do controle na lista de áudio da máquina é o defeito que a metade
    de entrada pagou em 09/09. Esta metade não o repete.

    MORDIDA: monte o rótulo com `f"… ({uniq})"`, como a ponte de rádio fazia, e
    as duas asserções caem.
    """
    anterior = mic.registrar_numerador_de_assento(lambda _u: 1)
    try:
        rotulo = som.descricao_do_alto_falante(_UNIQ_P1)
    finally:
        mic.registrar_numerador_de_assento(anterior)
    assert _UNIQ_P1 not in rotulo
    assert "11a1b2" not in rotulo


# ---------------------------------------------------------------------------
# 2. UM `sink_name` SÓ, e ele é o do APARELHO
# ---------------------------------------------------------------------------


def test_o_sink_name_e_o_do_aparelho_e_nao_o_do_assento() -> None:
    """O jogo escolhe uma saída; trocar o controle de assento não pode trocá-la.

    MORDIDA: volte `NoDeAltoFalante.id_do_no` para
    `f"hefesto_alto_falante_{self.assento}"` e o mesmo aparelho passa a ter
    dois `sink_name` conforme o assento em que ela o pôs.
    """
    no_p1 = NoDeAltoFalante("p1", _UNIQ_P1, "usb")
    no_p3 = NoDeAltoFalante("p3", _UNIQ_P1, "bt")

    assert no_p1.id_do_no == no_p3.id_do_no == "hefesto_som_11a1b2"
    assert no_p1.id_do_no == som.nome_do_sink(_UNIQ_P1)
    assert NoDeAltoFalante("p1", "", "usb").id_do_no == ""


# ---------------------------------------------------------------------------
# 3. A FONTE — «mix» é o HDMI completo, «sfx» deixa o nó livre
# ---------------------------------------------------------------------------


def test_mix_liga_o_monitor_da_saida_padrao_ao_no(usb_da_bancada: None) -> None:
    """O *«HDMI completo»* dela: o que a TV recebe, o controle recebe junto.

    MORDIDA: apague o ramo `FONTE_MIX` de `argv_das_rotas` e o plano volta a
    ter só a saída — o nó do controle nunca recebe o som do sistema, que é
    metade do pedido dela.
    """
    no = no_do_controle(_entry(_UNIQ_P1, 1), fonte=som.FONTE_MIX)
    assert no is not None
    plano = plano_de_publicacao(no, [_UNIQ_P1, _UNIQ_P2], runner=_runner_de_leitura())

    linhas = [" ".join(a) for a in plano.argv]
    assert plano.fonte == som.FONTE_MIX
    assert len(plano.argv) == 3, linhas
    assert f"source={_HDMI}.monitor" in linhas[2]
    assert "sink=hefesto_som_11a1b2" in linhas[2]


def test_sfx_deixa_o_no_livre_para_o_jogo(usb_da_bancada: None) -> None:
    """Sem `mix`, nenhum loopback ENTRA no nó — ele espera a corrente do jogo.

    É o padrão dela (`D-0809-NO-CABO-O-PADRAO-DO-SOM-E-SFX`): com `mix` de
    fábrica o controle viraria a saída de todo o som do PC sozinho.

    MORDIDA: faça `FONTE_PADRAO = FONTE_MIX` e este teste reprova — e o produto
    passa a tomar uma decisão que ela recusou por escrito.
    """
    no = no_do_controle(_entry(_UNIQ_P1, 1))
    assert no is not None
    assert no.fonte == "sfx"
    plano = plano_de_publicacao(no, [_UNIQ_P1, _UNIQ_P2], runner=_runner_de_leitura())

    linhas = [" ".join(a) for a in plano.argv]
    assert len(plano.argv) == 2, linhas
    assert not any(f"source={_HDMI}" in linha for linha in linhas)
    assert f"sink={_SINK_P1}" in linhas[1]


def test_um_em_mix_e_outro_em_sfx_ao_mesmo_tempo(usb_da_bancada: None) -> None:
    """O critério de pronto da sprint: P1 em `mix` e P2 em `sfx`, juntos.

    E cada um entrega no SEU sink — quem separa os dois é o dispositivo USB,
    nunca o texto do nome, que é a invariante 2 desta seção.

    MORDIDA: leia a fonte de um lugar global (uma constante de módulo, o último
    valor visto) em vez do nó, e os dois passam a ter a mesma.
    """
    ler = _runner_de_leitura()
    p1 = plano_de_publicacao(
        no_do_controle(_entry(_UNIQ_P1, 1), fonte=som.FONTE_MIX),
        [_UNIQ_P1, _UNIQ_P2],
        runner=ler,
    )
    p2 = plano_de_publicacao(
        no_do_controle(_entry(_UNIQ_P2, 2), fonte=som.FONTE_SFX),
        [_UNIQ_P1, _UNIQ_P2],
        runner=ler,
    )

    assert p1.fonte == "mix" and p2.fonte == "sfx"
    assert len(p1.argv) == 3 and len(p2.argv) == 2
    assert p1.sink == _SINK_P1 and p2.sink == _SINK_P2
    assert p1.id_do_no != p2.id_do_no


def test_o_mix_nao_troca_a_origem_pelo_destino() -> None:
    """Trocar as duas pontas manda o som do controle para a televisão dela.

    MORDIDA: inverta `source=` e `sink=` em `argv_para_ligar_o_mix` e as duas
    asserções caem — e nenhuma outra régua deste arquivo notaria.
    """
    argv = " ".join(som.argv_para_ligar_o_mix("hefesto_som_11a1b2", f"{_HDMI}.monitor"))
    assert f"source={_HDMI}.monitor" in argv
    assert "sink=hefesto_som_11a1b2" in argv


def test_sem_saida_padrao_legivel_o_mix_nao_se_inventa() -> None:
    """`pactl` mudo é "não sei", e um `source=` vazio toca no sink PADRÃO.

    É a cicatriz do `paplay --device=` que este módulo já registra: o comando é
    ACEITO, sai com zero, e o som vai para outro lugar — a TV dela.

    MORDIDA: devolva `".monitor"` quando o `pactl` não responde e o produto
    carrega um loopback com origem vazia.
    """

    def mudo(argv: list[str]) -> str | None:
        return None

    assert som.monitor_da_saida_padrao(runner=mudo) == ""
    rota = som.RotaDoNo(True, sink=_SINK_P1, fonte=som.FONTE_MIX, monitor_do_mix="")
    assert len(som.argv_das_rotas("hefesto_som_11a1b2", rota)) == 1


# ---------------------------------------------------------------------------
# 4. O NÓ VIVE SEMPRE — e sem rota ele DIZ (decisão dela, 08/09/2026)
# ---------------------------------------------------------------------------


def test_sem_rota_o_no_existe_e_carrega_a_frase() -> None:
    """`D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`: *"nó que some quebra o
    jogo que o escolheu"*.

    As duas metades andam juntas: o nó é publicado E o motivo vem cheio. Um nó
    publicado com o motivo VAZIO é o sumidouro que a invariante 4 recusa.

    MORDIDA: volte `plano_de_publicacao` a devolver `PlanoDoNo(False, argv=())`
    sem rota, que é o que esta casa fazia até 07/09, e as três primeiras
    asserções caem.
    """
    no = NoDeAltoFalante("p2", _UNIQ_P2, "bt")
    plano = plano_de_publicacao(no)

    assert plano.vai_publicar is True
    assert len(plano.argv) == 1
    assert plano.motivo == som.MOTIVO_NO_SEM_PONTE_NO_RADIO
    assert plano.tem_rota is False
    assert not any("module-loopback" in a for argv in plano.argv for a in argv)


def test_publicar_e_ter_rota_sao_perguntas_diferentes(usb_da_bancada: None) -> None:
    """Confundir as duas é o defeito seguinte: nó que existe e não entrega.

    MORDIDA: faça `tem_rota` devolver `self.vai_publicar` e o par vira uma
    coisa só — a tela passa a dizer "está tocando" sobre um nó mudo.
    """
    com = plano_de_publicacao(
        no_do_controle(_entry(_UNIQ_P1, 1)), [_UNIQ_P1], runner=_runner_de_leitura()
    )
    sem = plano_de_publicacao(NoDeAltoFalante("p2", _UNIQ_P2, "bt"))

    assert (com.vai_publicar, com.tem_rota) == (True, True)
    assert (sem.vai_publicar, sem.tem_rota) == (True, False)


# ---------------------------------------------------------------------------
# 5. O NÓ VIVO — o `SinkVirtualPipeWire` sobe a rota junto, e a derruba antes
# ---------------------------------------------------------------------------


def test_o_no_sobe_o_loopback_junto_com_o_sink() -> None:
    """A causa 1 da medição: era ESTA falta que fazia a fiação ser regressão.

    MORDIDA: apague a chamada a `_ligar_a_rota` em `iniciar` e o nó volta a ser
    um `module-null-sink` sozinho — o sink que aceita o áudio e o joga fora.
    """
    gravador = _Gravador()
    no = som.SinkVirtualPipeWire(
        uniq=_UNIQ_P1,
        descricao="Alto-falante do Controle 1",
        runner=gravador,
        rota=som.RotaDoNo(True, sink=_SINK_P1, por_onde=som.POR_CABO),
    )

    assert no.iniciar() is True
    assert any("module-null-sink" in linha for linha in gravador.linhas)
    assert any("module-loopback" in linha for linha in gravador.linhas)
    assert any(f"sink={_SINK_P1}" in linha for linha in gravador.linhas)


def test_a_rota_cai_antes_do_no_e_so_a_que_ele_subiu() -> None:
    """Um loopback cuja ponta some é módulo órfão no PipeWire dela.

    MORDIDA: descarregue o `module-null-sink` primeiro (ou esqueça
    `self._rotas`) e a ordem das duas últimas asserções inverte — que é como os
    52 sinks fantasma de 07/09 entraram.
    """
    gravador = _Gravador()
    no = som.SinkVirtualPipeWire(
        uniq=_UNIQ_P1,
        runner=gravador,
        rota=som.RotaDoNo(True, sink=_SINK_P1, por_onde=som.POR_CABO),
    )
    no.iniciar()
    id_do_sink = no.module_id
    gravador.argvs.clear()
    no.parar()

    descarregados = [a[-1] for a in gravador.argvs if "unload-module" in a]
    assert len(descarregados) == 2, gravador.linhas
    assert descarregados[-1] == id_do_sink
    no.parar()  # idempotente: nada de novo
    assert len([a for a in gravador.argvs if "unload-module" in a]) == 2


def test_sem_rota_o_no_sobe_sozinho_e_nao_liga_nada() -> None:
    """A outra metade do par: o nó existe, e nenhum loopback é carregado.

    MORDIDA: carregue o loopback mesmo com `rota=None` e o produto liga o som a
    um sink que ninguém resolveu.
    """
    gravador = _Gravador()
    no = som.SinkVirtualPipeWire(uniq=_UNIQ_P1, runner=gravador, rota=None)

    assert no.iniciar() is True
    assert not any("module-loopback" in linha for linha in gravador.linhas)


def test_o_loopback_que_nao_sobe_nao_derruba_o_no() -> None:
    """O dublê tem de saber RECUSAR, e a recusa não pode custar o nó.

    Um `module-loopback` que falha deixa o controle mudo; derrubar o nó por
    causa dele tira do jogo a saída que ele escolheu — o defeito inteiro.
    """
    gravador = _Gravador()

    def meio_recusa(argv: list[str]) -> str | None:
        gravador.argvs.append(list(argv))
        if "module-loopback" in argv:
            return None
        return "777\n" if "load-module" in argv else ""

    no = som.SinkVirtualPipeWire(
        uniq=_UNIQ_P1,
        runner=meio_recusa,
        rota=som.RotaDoNo(True, sink=_SINK_P1, por_onde=som.POR_CABO),
    )

    assert no.iniciar() is True
    assert no.module_id == "777"


# ---------------------------------------------------------------------------
# 6. O GERENCIADOR — cada controle com o SEU nó, e a mesa inteira na conta
# ---------------------------------------------------------------------------


def test_o_gerenciador_batiza_e_roteia_cada_um(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quatro na mesa, quatro nós, cada um com o seu rótulo e a sua rota.

    MORDIDA: volte `_construir` a `SinkVirtualPipeWire(uniq=uniq)`, sem o
    rótulo e sem a rota, e os quatro nascem com o MESMO nome e sem destino —
    que é exatamente o que o `test_o_no_de_som_nao_nasce_sumidouro` nomeia
    como regressão.
    """
    construidos: list[dict[str, Any]] = []

    class _NoFalso:
        def __init__(self, **kw: Any) -> None:
            construidos.append(kw)

        def iniciar(self) -> bool:
            return True

        def parar(self) -> None:
            return None

    monkeypatch.setattr(som, "SinkVirtualPipeWire", _NoFalso)
    monkeypatch.setattr(som, "descricao_do_alto_falante", lambda u: f"rotulo:{u[-6:]}")
    monkeypatch.setattr(
        som, "rota_do_no", lambda u, t, mesa, **kw: som.RotaDoNo(True, sink=f"sink:{u}")
    )

    ger = GerenciadorDeNosDeSom()
    ger.reconciliar(
        [
            ControleNaLista(_UNIQ_P1, "/dev/hidraw0", "usb"),
            ControleNaLista(_UNIQ_P2, "/dev/hidraw1", "bt"),
        ]
    )

    assert len(construidos) == 2
    rotulos = [c["descricao"] for c in construidos]  # (noqa-acento) nome de parâmetro
    assert rotulos == ["rotulo:11a1b2", "rotulo:11a1b3"]
    assert [c["rota"].sink for c in construidos] == [
        f"sink:{_UNIQ_P1}",
        f"sink:{_UNIQ_P2}",
    ]


def test_a_mesa_inteira_vai_para_quem_resolve_o_sink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com UM `uniq` só, dois DualSense no cabo casam a mesma placa.

    `escolher_sink` desempata pelo dispositivo USB, e para isso precisa da
    lista inteira. MORDIDA: passe `(uniq,)` em vez da mesa e esta asserção cai
    — e na bancada dela o som do P2 sai no alto-falante do P1.
    """
    mesas: list[tuple[str, ...]] = []

    class _NoFalso:
        def __init__(self, **kw: Any) -> None:
            pass

        def iniciar(self) -> bool:
            return True

        def parar(self) -> None:
            return None

    monkeypatch.setattr(som, "SinkVirtualPipeWire", _NoFalso)
    monkeypatch.setattr(som, "descricao_do_alto_falante", lambda u: "x")

    def espiar(uniq: str, transporte: str, mesa: Any, **kw: Any) -> Any:
        mesas.append(tuple(mesa))
        return som.RotaDoNo(False, motivo="x")

    monkeypatch.setattr(som, "rota_do_no", espiar)

    GerenciadorDeNosDeSom().reconciliar(
        [
            ControleNaLista(_UNIQ_P1, "/dev/hidraw0", "usb"),
            ControleNaLista(_UNIQ_P2, "/dev/hidraw1", "usb"),
        ]
    )

    assert mesas == [(_UNIQ_P1, _UNIQ_P2), (_UNIQ_P1, _UNIQ_P2)]


def test_a_fonte_de_cada_controle_chega_ao_no(monkeypatch: pytest.MonkeyPatch) -> None:
    """A escolha dela, por controle, atravessa o gerenciador até a rota.

    MORDIDA: ignore `fonte_por_controle` em `_fonte_do_no` e os dois nós
    recebem o padrão — a escolha `mix` que ela gravou no perfil evapora.
    """
    fontes: list[str] = []

    class _NoFalso:
        def __init__(self, **kw: Any) -> None:
            pass

        def iniciar(self) -> bool:
            return True

        def parar(self) -> None:
            return None

    monkeypatch.setattr(som, "SinkVirtualPipeWire", _NoFalso)
    monkeypatch.setattr(som, "descricao_do_alto_falante", lambda u: "x")
    monkeypatch.setattr(
        som,
        "rota_do_no",
        lambda u, t, mesa, **kw: (
            fontes.append(kw.get("fonte", "?")) or som.RotaDoNo(False, motivo="x")
        ),
    )

    escolhas = {_UNIQ_P1: "mix"}
    GerenciadorDeNosDeSom(
        fonte_por_controle=lambda u: escolhas.get(u, "")
    ).reconciliar(
        [
            ControleNaLista(_UNIQ_P1, "/dev/hidraw0", "usb"),
            ControleNaLista(_UNIQ_P2, "/dev/hidraw1", "usb"),
        ]
    )

    assert fontes == ["mix", "sfx"]


# ---------------------------------------------------------------------------
# 7. O «CONTROLE N» DO NÓ — e as TRÊS contas que viraram UMA (12/09/2026)
# ---------------------------------------------------------------------------

#: Quatro endereços SEM o prefixo de vpad, porque o registro de identidade
#: recusa `02:fe:…` por decisão (D9: o vpad jamais é "Controle N") — e é o
#: registro de VERDADE que responde daqui para baixo. Máscara da casa nos
#: octetos 4 e 5.
_OS_QUATRO = ("aabbcc000011", "aabbcc000012", "aabbcc000013", "aabbcc000014")


def _mesa(*itens: tuple[str, bool]) -> list[dict[str, Any]]:
    return [
        {"uniq": uniq, "connected": ligado, "index": i}
        for i, (uniq, ligado) in enumerate(itens)
    ]


def _backend(mesa: list[dict[str, Any]]) -> Any:
    return type("B", (), {"describe_controllers": staticmethod(lambda: mesa)})()


def _registro_com_a_fila(chegada: tuple[str, ...]) -> Any:
    """O `identity_registry` DE VERDADE, com a fila de chegada dada.

    **Não é dublê, e é de propósito.** Um dublê de registro seria mais frouxo
    que o produto em três pontos que importam aqui: ele recusa `uniq` vazio,
    recusa MAC de vpad (D9) e devolve a COLOCAÇÃO entre os PRESENTES, não o
    lugar cru na fila. O de verdade não faz I/O de disco enquanto ninguém chama
    `load()`, então a régua continua hermética.

    `slot_for(uniq)` com `assign=True` é o que DÁ o lugar na fila — é assim que
    o tique do daemon o dá. A ordem das chamadas é a ordem de chegada.
    """
    from hefesto_dualsense4unix.daemon.subsystems.identity import (
        ControllerIdentityRegistry,
    )

    registro = ControllerIdentityRegistry()
    for uniq in chegada:
        registro.slot_for(uniq)
    return registro


def _payload_do_ipc(mesa: list[dict[str, Any]], daemon: Any) -> list[dict[str, Any]]:
    """As entradas de `controllers` como o IPC as publica — com `player_slot`.

    Quem carimba é o PRODUTO: `IpcHandlersMixin._player_slot_for`, chamado sem
    instância porque ele só lê `self.daemon`. Redigitar `slot_for(…,
    assign=False)` aqui faria a régua medir a minha cópia da leitura em vez da
    do daemon — a forma de instrumento falso que esta casa já nomeou.
    """
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    quem_le = SimpleNamespace(daemon=daemon)
    saida = []
    for item in mesa:
        entrada = dict(item)
        entrada["player_slot"] = IpcHandlersMixin._player_slot_for(
            quem_le,  # type: ignore[arg-type]
            entrada.get("uniq") or None,
        )
        saida.append(entrada)
    return saida


@pytest.mark.parametrize(
    "mesa",
    [
        _mesa((_UNIQ_P1, True), (_UNIQ_P2, True)),
        _mesa((_UNIQ_P1, False), (_UNIQ_P2, True)),
        _mesa((_UNIQ_P2, True), (_UNIQ_P1, True)),
        _mesa(("", True), (_UNIQ_P2, True)),
    ],
)
def test_o_assento_do_alto_falante_e_o_mesmo_do_microfone(mesa: Any) -> None:
    """Os dois rótulos aparecem na MESMA lista de som dela — e dizem o mesmo N.

    «Alto-falante do Controle N» e «Microfone do Controle N», lado a lado: um
    dizer 2 enquanto o outro diz 3 sobre o mesmo aparelho é a lista mentindo.

    **ISTO JÁ FOI DUAS IMPLEMENTAÇÕES DA MESMA REGRA**, uma em cada subsystem, e
    esta régua era o que as segurava. Desde 12/09/2026 as duas chamam
    `subsystems/base.numero_do_assento_na_mesa` — a régua fica porque o par tem
    de continuar amarrado se alguém reescrever um dos dois lados.

    MORDIDA: faça `AltoFalanteSubsystem.numero_do_assento` voltar a contar
    (`enumerate` dos conectados) e o segundo caso reprova.
    """
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    backend = _backend(mesa)
    saida = AltoFalanteSubsystem()
    saida._backend = backend
    entrada = BtMicSubsystem()
    entrada._backend = backend

    for uniq in (_UNIQ_P1, _UNIQ_P2, "aabbcc000099"):
        assert saida.numero_do_assento(uniq) == entrada.numero_do_assento(uniq), uniq


def test_um_uniq_que_nao_e_endereco_nao_ganha_assento() -> None:
    """`norm_mac` só FILTRA hex: sem a trava dos doze, `"a"` casaria com tudo.

    MORDIDA: tire o `len(chave) != _UNIQ_HEX` e um `uniq` de um caractere passa
    a receber assento.
    """
    saida = AltoFalanteSubsystem()
    saida._backend = type(
        "B", (), {"describe_controllers": staticmethod(lambda: _mesa((_UNIQ_P1, True)))}
    )()

    assert saida.numero_do_assento("a") is None
    assert saida.numero_do_assento("") is None
    assert saida.numero_do_assento(_UNIQ_P1) == 1


def test_o_gancho_do_assento_nao_derruba_quem_ja_atende() -> None:
    """Um registro, dois candidatos: quem chega primeiro atende.

    Se este subsystem trocasse o numerador do `BtMicSubsystem` no meio da
    sessão, a troca seria sem efeito e com risco — os dois respondem o mesmo.

    MORDIDA: instale sempre (sem olhar o valor devolvido pelo registro) e a
    primeira asserção cai.
    """
    dono = mic.registrar_numerador_de_assento(lambda _u: 4)
    try:
        sub = AltoFalanteSubsystem()
        sub._instalar_o_numerador()
        assert mic.numero_do_assento(_UNIQ_P1) == 4
        sub._desinstalar_o_numerador()
        assert mic.numero_do_assento(_UNIQ_P1) == 4
    finally:
        mic.registrar_numerador_de_assento(dono)

    anterior = mic.registrar_numerador_de_assento(None)
    try:
        sub = AltoFalanteSubsystem()
        sub._backend = type(
            "B",
            (),
            {"describe_controllers": staticmethod(lambda: _mesa((_UNIQ_P1, True)))},
        )()
        sub._instalar_o_numerador()
        assert mic.numero_do_assento(_UNIQ_P1) == 1
        sub._desinstalar_o_numerador()
        assert mic.numero_do_assento(_UNIQ_P1) is None
    finally:
        mic.registrar_numerador_de_assento(anterior)


# ---------------------------------------------------------------------------
# 8. O PERFIL — a fonte por controle, e o perfil velho que não muda de byte
# ---------------------------------------------------------------------------


def test_a_fonte_entra_no_perfil_por_controle() -> None:
    """`ControllerOverrides.speaker.fonte`, o campo novo desta sprint.

    MORDIDA: tire o campo do `ProfileSpeakerConfig` e o `extra="forbid"` recusa
    o perfil inteiro — a escolha dela não tem onde morar.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    over = ControllerOverrides(speaker=ProfileSpeakerConfig(volume=180, fonte="mix"))
    assert over.speaker is not None
    assert over.speaker.fonte == "mix"


def test_perfil_velho_sem_fonte_carrega_e_nao_muda_de_byte() -> None:
    """Sem opinião a chave nem aparece no arquivo — é a regra da `rota`.

    `extra="forbid"` faz um hefesto ANTIGO recusar o perfil inteiro ao ver uma
    chave que ele não conhece; gravar `"fonte": null` em todo perfil salvo
    transformaria "voltar uma versão" em "todos os perfis com som quebrados".

    MORDIDA: tire `"fonte"` do laço do serializer e a segunda asserção cai.
    """
    velho = ProfileSpeakerConfig(volume=180)
    assert velho.fonte is None
    assert "fonte" not in velho.model_dump()
    assert ProfileSpeakerConfig(volume=180, fonte="sfx").model_dump()["fonte"] == "sfx"


def test_a_fonte_do_perfil_e_a_do_codigo_sao_a_mesma_lista() -> None:
    """Duas listas de valores é como esta casa fabrica divergência silenciosa.

    MORDIDA: acrescente um `"hdmi"` ao `Literal` do schema e a comparação de
    conjunto reprova — um valor que `rota_do_no` não sabe tratar chegaria ao
    disco.
    """
    import typing

    campo = ProfileSpeakerConfig.model_fields["fonte"].annotation
    literais = {
        v
        for arg in typing.get_args(campo)
        for v in typing.get_args(arg)
        if isinstance(v, str)
    }
    assert literais == {som.FONTE_MIX, som.FONTE_SFX}
    assert som.FONTE_PADRAO == som.FONTE_SFX


def test_uma_fonte_que_o_codigo_nao_conhece_cai_no_padrao() -> None:
    """Nada que venha de fora vira comportamento novo por acidente.

    MORDIDA: passe o valor adiante sem a peneira e `argv_das_rotas` decide por
    um `elif` que não existe — silêncio, que é o pior desfecho.
    """
    rota = som.rota_do_no(_UNIQ_P1, "bt", (), fonte="hdmi-completo")
    assert rota.fonte == som.FONTE_PADRAO


# ---------------------------------------------------------------------------
# 9. A PALAVRA DO TRANSPORTE — quatro grafias, uma pergunta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("palavra", ["bt", "radio", "rádio", "BLUETOOTH"])
def test_a_palavra_do_transporte_nao_troca_a_frase(palavra: str) -> None:
    """As quatro grafias do rádio pedem a MESMA frase.

    **ACHADO NA PASSADA SECA de 09/09/2026, com os quatro DualSense dela na
    mesa.** `ControleNaLista.transporte` diz `"rádio"` (a palavra da tela) e
    `app/audio_saida` diz `"bt"` (a do `state_full`). Com a comparação de texto
    contra UMA delas, os dois controles do rádio caíam no ramo do CABO e ela
    lia *"Reconecte o cabo do controle"* — sobre um controle sem cabo nenhum.

    MORDIDA: volte `e_radio(transporte)` para `transporte == TRANSPORTE_RADIO` e
    três dos quatro casos reprovam com a frase do cabo.
    """
    rota = som.rota_do_no(_UNIQ_P1, palavra, (_UNIQ_P1,), runner=lambda a: "")

    assert rota.tem_rota is False
    assert rota.motivo == som.MOTIVO_NO_SEM_PONTE_NO_RADIO


def test_o_cabo_continua_sendo_cabo_nas_duas_grafias() -> None:
    """A peneira do rádio não pode engolir o cabo — o dublê sabe recusar.

    MORDIDA: ponha `"usb"` ou `"cabo"` em `_PALAVRAS_DE_RADIO` e o controle do
    fio passa a receber a frase do rádio, que é o defeito espelhado.
    """
    for palavra in ("usb", "cabo", ""):
        assert som.e_radio(palavra) is False
    rota = som.rota_do_no(_UNIQ_P1, "cabo", (_UNIQ_P1,), runner=lambda a: "")
    assert rota.motivo == som.MOTIVO_NO_SEM_PLACA_NO_CABO


def test_as_tres_contas_do_mesmo_rotulo_viraram_uma() -> None:
    """HAVIA TRÊS contas para o mesmo «Controle N». Sobrou uma — 12/09/2026.

    TRES-CONTAS-PARA-UM-NUMERO-01, e o defeito que a originou foi medido na mesa
    DELA em 09/09 às 22h, com os quatro DualSense ligados::

        pactl list sources → Description: Microfone do Controle 2  ← o daemon
        a tela             → P1 • White • cabo                     ← o cartão

    Dois números para o mesmo aparelho, em duas janelas ao mesmo tempo — o
    defeito que o `numero_do_controle` foi criado para matar (COR-01/D6).

    **A CAUSA NÃO ERA DESCONEXÃO DE NINGUÉM, e é isto que esta régua fixa:** o
    `player_slot` é a ordem da FILA DE CHEGADA e a conta velha era a ordem dos
    HANDLES. Com os quatro na mesa as duas listas são diferentes — `[4,1,3,2]`
    contra `[1,2,3,4]` —, e é o MESMO par de listas que o portão
    `test_mesa_cheia_11_a_janela_conta_quatro` mediu no payload real dela.

    AS TRÊS CONTAS, medidas aqui uma contra a outra sobre a MESMA mesa:

        `app/actions/base.numero_do_controle`         a da TELA (importa `gi`)
        `daemon/ipc_handlers._numero_de_exibicao`     a MESMA, do lado do daemon
        `*.numero_do_assento`                         a dos NÓS DE SOM

    A terceira deixou de ser uma conta: ela pergunta o `player_slot` ao dono —
    o `identity_registry` — e entrega a entrada à regra da casa.

    MORDIDA: tire o `daemon=self._daemon` de um dos dois `numero_do_assento` (ou
    faça `base.numero_do_assento_na_mesa` ignorar o registro) e os nós voltam a
    dizer `[1,2,3,4]` contra o `[4,1,3,2]` do cartão.
    """
    from hefesto_dualsense4unix.app.actions.base import numero_do_controle
    from hefesto_dualsense4unix.daemon.ipc_handlers import _numero_de_exibicao
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    p1, p2, p3, p4 = _OS_QUATRO
    # a fila de chegada NÃO é a ordem dos handles: é ela que dá o `[4,1,3,2]`.
    registro = _registro_com_a_fila((p2, p4, p3, p1))
    daemon = type("D", (), {"identity_registry": registro})()

    mesa = _mesa((p1, True), (p2, True), (p3, True), (p4, True))
    backend = _backend(mesa)
    saida = AltoFalanteSubsystem(daemon=daemon)
    saida._backend = backend
    entrada = BtMicSubsystem(daemon=daemon)
    entrada._backend = backend

    publicado = _payload_do_ipc(mesa, daemon)
    assert [e["player_slot"] for e in publicado] == [4, 1, 3, 2], (
        "a fila de chegada não chegou ao payload; sem ela esta régua não mede "
        f"divergência nenhuma: {[e['player_slot'] for e in publicado]}"
    )

    for entry in publicado:
        uniq = entry["uniq"]
        da_tela = numero_do_controle(entry)
        do_daemon = _numero_de_exibicao(entry)
        do_no_de_saida = saida.numero_do_assento(uniq)
        do_no_de_entrada = entrada.numero_do_assento(uniq)
        assert da_tela == do_daemon == do_no_de_saida == do_no_de_entrada, (
            f"as contas discordam sobre {uniq}: tela={da_tela} "
            f"daemon={do_daemon} alto-falante={do_no_de_saida} "
            f"microfone={do_no_de_entrada}"
        )


def test_a_entrada_que_ja_traz_o_slot_nao_e_perguntada_de_novo() -> None:
    """Quem já carimbou o `player_slot` na entrada é o dono; o nó respeita.

    O caminho de produção é o contrário — `describe_controllers()` NÃO devolve
    `player_slot`, e é por isso que `base.numero_do_assento_na_mesa` vai pedi-lo
    ao registro. Mas quem passar a esta função uma entrada JÁ publicada (a do
    payload do IPC) não pode ter o valor dela atropelado: um segundo caminho de
    leitura sobre o mesmo campo é como nasce a divergência que esta sprint
    fechou.

    MORDIDA: tire o `if not isinstance(entrada.get("player_slot"), int)` de
    `base.numero_do_assento_na_mesa` e o 7 abaixo volta a ser 1.
    """
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    p1 = _OS_QUATRO[0]

    class _RegistroQueMente:
        def slot_for(self, uniq: str, **_kw: Any) -> int:
            return 99

    daemon = type("D", (), {"identity_registry": _RegistroQueMente()})()
    mesa = [{"uniq": p1, "connected": True, "index": 0, "player_slot": 7}]
    sub = BtMicSubsystem(daemon=daemon)
    sub._backend = _backend(mesa)

    assert sub.numero_do_assento(p1) == 7


def test_o_controle_desligado_nao_ganha_nome_mesmo_com_lugar_na_fila() -> None:
    """A INVARIANTE que a cura não podia perder: número só para quem está na mesa.

    `slot_for(uniq, assign=False)` responde a COLOCAÇÃO que um AUSENTE teria se
    voltasse — é a promessa dele, e é o que faz o cartão nascer certo no tique de
    hotplug. Um nó de som publicado por essa resposta poria na lista dela um
    «Microfone do Controle N» de um controle que não está lá, e que ninguém
    consegue desligar.

    MORDIDA: faça `base.numero_do_assento_na_mesa` varrer `_controles_da_mesa()`
    em vez dos conectados (ou peça o slot antes de achar o item) e o P1 desligado
    ganha nome.
    """
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    p1, p2, p3, p4 = _OS_QUATRO
    registro = _registro_com_a_fila((p1, p2, p3, p4))
    daemon = type("D", (), {"identity_registry": registro})()
    assert registro.slot_for(p1, assign=False) is not None, (
        "o registro perdeu o lugar do P1; sem lugar não há o que esta régua morde"
    )

    mesa = _mesa((p1, False), (p2, True), (p3, True), (p4, True))
    sub = BtMicSubsystem(daemon=daemon)
    sub._backend = _backend(mesa)

    assert sub.numero_do_assento(p1) is None, (
        "um controle DESLIGADO ganhou nome de nó na lista de som dela"
    )
    for uniq in (p2, p3, p4):
        tem_nome = sub.numero_do_assento(uniq) is not None
        assert tem_nome == (uniq in sub.uniqs_na_mesa()), (
            f"as duas leituras discordam sobre {uniq}"
        )
