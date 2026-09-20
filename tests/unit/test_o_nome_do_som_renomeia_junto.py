"""O-NOME-DO-SOM-RENOMEIA-JUNTO-01 — o rótulo do nó segue o assento.

O DEFEITO, ACHADO DE OUVIDO POR ELA EM TESTE CEGO — 20/09/2026, 04:24
---------------------------------------------------------------------
Dois gabaritos lacrados antes de qualquer som tocar, três rodadas de seis
segundos, e ela sem saber o alvo nem o timbre de nenhuma. Acertou 3 de 3::

    mandei para «Alto-falante do Controle 3» → ela ouviu no Player 1, verde
    mandei para nada                          → «nada»
    mandei para «Alto-falante do Controle 1» → ela ouviu no Player 3, azul

**Os nomes do Player 1 e do Player 3 estavam trocados ENTRE SI**, e o
«Microfone do Controle N» mentia junto — pior: três dos quatro, e um deles sem
número nenhum.

A CAUSA, MEDIDA DE DENTRO DO DAEMON — e o numerador está CERTO
---------------------------------------------------------------
No mesmo instante em que os rótulos diziam ``2, 4, 1, 3``, o ``controller.list``
do daemon dela respondia ``player_slot`` ``2, 4, 3, 1`` para os mesmos quatro
``uniq``. O cálculo do assento nunca esteve errado: **o rótulo é a fotografia
do assento de quando o nó nasceu**, e quando um controle entra na mesa e
empurra o assento de OUTRO, o nó do outro não renasce.

E NÃO HÁ RENOMEAR NO LUGAR — medido nesta máquina no mesmo dia: o ``pactl`` do
``pipewire-pulse`` não tem ``update-sink-proplist`` nem
``update-source-proplist``, e o ``pacmd``, que os teria, responde *"No
PulseAudio daemon running"* sob o PipeWire. **Renomear é republicar** — o mesmo
ato que o daemon já faz por rotina quando o controle pisca.

A ORDEM DELA, 20/09/2026: *"corrige tudo que contenha a info incorreta
sobrescrevendo-a"*.

POR QUE UMA RÉGUA DE «TEM NÚMERO» NÃO SERVE
--------------------------------------------
No estado de 20/09 os quatro rótulos tinham número, e o CONJUNTO dos números
era ``{1, 2, 3, 4}`` — completo, sem repetição. Uma régua que contasse número,
ou que exigisse quatro números distintos, daria **verde sobre o defeito vivo**.
O que morde é a BIJEÇÃO: para cada ``uniq``, o rótulo tem de dizer o assento
DAQUELE ``uniq``. Ver :func:`test_a_regua_fraca_da_verde_sobre_a_troca`.

O QUE ESTE ARQUIVO NÃO MEDE
----------------------------
Som. Nenhum ``pactl`` de verdade sai daqui — o servidor de som dela tem quatro
DualSense em cima. Que o alto-falante do Player 3 toque o que entrou no nó do
Player 3 é a orelha dela, e já está medido na sprint.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
    ControleNaLista,
    GerenciadorDeNosDeSom,
)
from hefesto_dualsense4unix.integrations import alto_falante_bt as som
from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as mic

# A MESA DELA DE 20/09/2026, com endereços SINTÉTICOS: a faixa `aa:bb:cc` é a
# desta casa para fixture, e nunca se deriva um endereço de teste do real —
# nem mascarado. O que é fiel aqui são os ASSENTOS e a troca entre eles.
_P2 = "aabbcc000001"  # assento 2 — o rótulo sempre acertou
_P4 = "aabbcc000002"  # assento 4 — o rótulo sempre acertou
_P3 = "aabbcc000003"  # assento 3 — o rótulo dizia «Controle 1»
_P1 = "aabbcc000004"  # assento 1 — o rótulo dizia «Controle 3»

#: Os assentos que o daemon dela respondia às 04:24 de 20/09/2026.
_ASSENTOS_DE_AGORA = {_P2: 2, _P4: 4, _P3: 3, _P1: 1}

#: E os assentos que os nós tinham GRAVADO no nome, nascidos antes da troca.
_ASSENTOS_DO_NOME = {_P2: 2, _P4: 4, _P3: 1, _P1: 3}


@pytest.fixture
def numerador() -> Any:
    """Instala um numerador de assento editável e o devolve ao fim.

    O numerador é um gancho global (`registrar_numerador_de_assento`): deixá-lo
    instalado envenenaria os testes seguintes por ORDEM DE ARQUIVO, que é um
    defeito que esta casa já pagou.
    """
    assentos = dict(_ASSENTOS_DE_AGORA)
    anterior = mic.registrar_numerador_de_assento(lambda u: assentos.get(u))
    try:
        yield assentos
    finally:
        mic.registrar_numerador_de_assento(anterior)


# ---------------------------------------------------------------------------
# 1. A PERGUNTA, e ela tem UM dono para os dois rótulos
# ---------------------------------------------------------------------------


def test_o_numero_sai_do_rotulo_nas_duas_familias() -> None:
    """A leitura é a INVERSA das duas funções que escrevem o rótulo.

    MORDIDA: faça `numero_do_rotulo` partir por `" "` e pegar o primeiro campo
    e as quatro primeiras asserções caem.
    """
    assert mic.numero_do_rotulo("Alto-falante do Controle 3") == 3
    assert mic.numero_do_rotulo("Microfone do Controle 1") == 1
    assert mic.numero_do_rotulo("Alto-falante do Controle") is None
    assert mic.numero_do_rotulo("") is None
    # `bool` é `int` em Python e «Controle 0» não é assento de ninguém.
    assert mic.numero_do_rotulo("Microfone do Controle 0") is None
    # Dígito que não é ASCII vem de outro escritor, nunca desta casa. O
    # arábico-índico é escrito por `chr` e não literal: ele é ambíguo com o
    # `l` latino a olho nu, e o `ruff` reprova o literal por isso.
    assert mic.numero_do_rotulo(f"Microfone do Controle {chr(0x0661)}") is None


def test_perder_o_numero_nunca_conta_como_envelhecer() -> None:
    """É esta metade que impede a cura de virar um nó piscando.

    O numerador responde `None` sempre que ninguém o está atendendo — o
    subsystem descendo, a mesa vazia por uma varredura. Sem esta recusa o nó
    seria derrubado e republicado a cada cinco segundos, e o jogo perderia o
    dispositivo debaixo de si em laço.

    MORDIDA: tire o `if numero_do_rotulo(de_agora) is None: return False` de
    `rotulo_envelheceu` e a primeira asserção vira `True`.
    """
    assert not mic.rotulo_envelheceu(
        "Alto-falante do Controle 3", "Alto-falante do Controle"
    )
    # E o caminho inverso CONTA: o nó que nasceu sem assento sabido ganha nome
    # assim que a mesa souber dizer — é o `hefesto_mic_…` dela de 20/09, que
    # estava no ar como «Microfone do Controle», sem número.
    assert mic.rotulo_envelheceu(
        "Microfone do Controle", "Microfone do Controle 2"
    )


def test_a_troca_entre_dois_rotulos_e_envelhecimento() -> None:
    """O defeito de 20/09 visto pela função: os dois lados acusam.

    MORDIDA: compare só o NÚMERO (`numero_do_rotulo(no_ar) is None`) em vez do
    texto inteiro e as duas asserções caem — que é exatamente o instrumento
    falso que esta sprint proibiu.
    """
    assert mic.rotulo_envelheceu(
        "Alto-falante do Controle 1", "Alto-falante do Controle 3"
    )
    assert mic.rotulo_envelheceu(
        "Alto-falante do Controle 3", "Alto-falante do Controle 1"
    )
    assert not mic.rotulo_envelheceu(
        "Alto-falante do Controle 2", "Alto-falante do Controle 2"
    )


def test_a_regua_fraca_da_verde_sobre_a_troca() -> None:
    """O estado REAL da mesa dela passaria por uma régua de «tem número».

    Este teste não mede o produto: ele mede a RÉGUA, e existe para que ninguém
    substitua a bijeção por uma contagem achando que é a mesma coisa.
    """
    no_ar = {
        uniq: f"Alto-falante do Controle {n}"
        for uniq, n in _ASSENTOS_DO_NOME.items()
    }
    # A régua fraca: todo rótulo tem número...
    assert all(mic.numero_do_rotulo(r) is not None for r in no_ar.values())
    # ...e os quatro números são distintos e completos. Verde sobre o defeito.
    assert sorted(mic.numero_do_rotulo(r) or 0 for r in no_ar.values()) == [1, 2, 3, 4]

    # A régua que MORDE: para cada `uniq`, o rótulo diz o assento DAQUELE uniq.
    de_agora = {
        uniq: f"Alto-falante do Controle {n}"
        for uniq, n in _ASSENTOS_DE_AGORA.items()
    }
    velhos = [u for u in no_ar if mic.rotulo_envelheceu(no_ar[u], de_agora[u])]
    assert sorted(velhos) == sorted([_P3, _P1])


# ---------------------------------------------------------------------------
# 2. O ALTO-FALANTE — o nó renasce com o nome de agora, pelo caminho de sempre
# ---------------------------------------------------------------------------


class _SinkEspiao:
    """Um `SinkVirtualPipeWire` de mentira que guarda o rótulo com que nasceu.

    `estado` responde `IDLE` porque o caso normal é ninguém tocando; os testes
    que medem a recusa o trocam de propósito.
    """

    def __init__(self, **kw: Any) -> None:
        self.uniq = str(kw.get("uniq", ""))
        self.descricao = kw.get("descricao")  # (noqa-acento) nome de atributo
        self.rota = kw.get("rota")
        self.parado = False

    def iniciar(self) -> bool:
        return True

    def parar(self) -> None:
        self.parado = True

    def religar(self, rota: Any) -> bool:
        return False

    def estado(self) -> str | None:
        return "IDLE"


def _mesa(monkeypatch: pytest.MonkeyPatch, sink: Any = _SinkEspiao) -> None:
    """Põe a fábrica de nós e a rota sob dublê. Nenhum `pactl` sai daqui."""
    monkeypatch.setattr(som, "SinkVirtualPipeWire", sink)
    monkeypatch.setattr(
        som,
        "rota_do_no",
        lambda u, t, mesa, **kw: som.RotaDoNo(True, sink=f"alsa_output.{u}"),
    )


def _controles() -> list[ControleNaLista]:
    return [
        ControleNaLista(uniq, f"/dev/hidraw{i}", "bt")
        for i, uniq in enumerate(_ASSENTOS_DE_AGORA)
    ]


def _rotulos(ger: GerenciadorDeNosDeSom) -> dict[str, Any]:
    return {uniq: no.descricao for uniq, no in ger.nos.items()}


def test_o_no_nasce_dizendo_o_assento(
    monkeypatch: pytest.MonkeyPatch, numerador: dict[str, int]
) -> None:
    """A partida: os quatro nós dizem o assento dos quatro controles."""
    _mesa(monkeypatch)
    ger = GerenciadorDeNosDeSom()
    ger.reconciliar(_controles())
    assert _rotulos(ger) == {
        uniq: f"Alto-falante do Controle {n}"
        for uniq, n in _ASSENTOS_DE_AGORA.items()
    }


def test_a_renumeracao_chega_ao_rotulo_do_no_vivo(
    monkeypatch: pytest.MonkeyPatch, numerador: dict[str, int]
) -> None:
    """A MORDIDA DA SPRINT: força a troca de 20/09 e o nome vai junto.

    A renumeração acontece pelo caminho que o daemon já usa — o numerador
    responde outro número porque um controle entrou na mesa e empurrou o
    assento de outro —, e a varredura seguinte é a `reconciliar` de sempre.

    MORDIDA: tire o `if uniq in self._nos and self._o_rotulo_envelheceu(...)`
    de `GerenciadorDeNosDeSom.reconciliar` e os dois rótulos trocados ficam
    para trás — que é o estado que ela ouviu.
    """
    _mesa(monkeypatch)
    ger = GerenciadorDeNosDeSom()
    ger.reconciliar(_controles())
    antes = dict(ger.nos)

    # A TROCA, exatamente a que a mesa dela fez: o assento 1 e o 3 mudam de dono.
    numerador[_P3], numerador[_P1] = 1, 3
    ger.reconciliar(_controles())

    assert _rotulos(ger) == {
        _P2: "Alto-falante do Controle 2",
        _P4: "Alto-falante do Controle 4",
        _P3: "Alto-falante do Controle 1",
        _P1: "Alto-falante do Controle 3",
    }
    # E SÓ OS DOIS RENASCERAM: quem não mudou de assento não perde o nó.
    assert ger.nos[_P2] is antes[_P2]
    assert ger.nos[_P4] is antes[_P4]
    assert ger.nos[_P3] is not antes[_P3]
    assert antes[_P3].parado is True
    assert antes[_P1].parado is True


def test_rotulo_igual_nao_encosta_no_no(
    monkeypatch: pytest.MonkeyPatch, numerador: dict[str, int]
) -> None:
    """Varredura sem novidade não derruba nada — ela roda de 5 em 5 segundos.

    MORDIDA: faça `_o_rotulo_envelheceu` devolver `True` sem comparar e os
    quatro nós renascem a cada volta, que é o nó piscando debaixo do jogo.
    """
    _mesa(monkeypatch)
    ger = GerenciadorDeNosDeSom()
    ger.reconciliar(_controles())
    antes = dict(ger.nos)
    for _ in range(3):
        ger.reconciliar(_controles())
    assert all(ger.nos[u] is antes[u] for u in antes)


def test_o_no_que_esta_tocando_espera_o_silencio(
    monkeypatch: pytest.MonkeyPatch, numerador: dict[str, int]
) -> None:
    """Renomear é republicar, e republicar tira o dispositivo debaixo do jogo.

    MORDIDA: tire a consulta a `_esta_tocando` e o nó `RUNNING` é derrubado no
    meio da partida dela.
    """

    class _Tocando(_SinkEspiao):
        def estado(self) -> str | None:
            return "RUNNING"

    _mesa(monkeypatch, sink=_Tocando)
    ger = GerenciadorDeNosDeSom()
    ger.reconciliar(_controles())
    antes = dict(ger.nos)
    numerador[_P3], numerador[_P1] = 1, 3
    ger.reconciliar(_controles())
    assert ger.nos[_P3] is antes[_P3]
    assert ger.nos[_P1] is antes[_P1]


def test_nao_sei_se_esta_tocando_vale_como_tocando(
    monkeypatch: pytest.MonkeyPatch, numerador: dict[str, int]
) -> None:
    """`estado()` devolve `None` com o servidor em recuo — e "não sei" recusa.

    É a regra já escrita em `SinkVirtualPipeWire.estado`: *"não sei" não é
    "ninguém está tocando"*.

    MORDIDA: trate `None` como IDLE e o nó é derrubado justamente quando o
    servidor de som não está respondendo.
    """

    class _Mudo(_SinkEspiao):
        def estado(self) -> str | None:
            return None

    _mesa(monkeypatch, sink=_Mudo)
    ger = GerenciadorDeNosDeSom()
    ger.reconciliar(_controles())
    antes = dict(ger.nos)
    numerador[_P3], numerador[_P1] = 1, 3
    ger.reconciliar(_controles())
    assert ger.nos[_P3] is antes[_P3]


def test_o_numerador_calado_nao_derruba_nada(
    monkeypatch: pytest.MonkeyPatch, numerador: dict[str, int]
) -> None:
    """Com o numerador mudo o rótulo de agora perde o número — e nada acontece.

    MORDIDA: aceite o rótulo sem número como "de agora" e os quatro nós
    renascem sem número na primeira volta em que o gancho piscar.
    """
    _mesa(monkeypatch)
    ger = GerenciadorDeNosDeSom()
    ger.reconciliar(_controles())
    antes = dict(ger.nos)
    numerador.clear()
    ger.reconciliar(_controles())
    assert all(ger.nos[u] is antes[u] for u in antes)
    assert _rotulos(ger) == {
        uniq: f"Alto-falante do Controle {n}"
        for uniq, n in _ASSENTOS_DE_AGORA.items()
    }


# ---------------------------------------------------------------------------
# 3. O GÊMEO — o «Microfone do Controle N» mentia junto, e pior
# ---------------------------------------------------------------------------


class _SourceEspia:
    """Um `SourceVirtualPipeWire` de mentira, com o mesmo contrato de `abrir`."""

    def __init__(self, *, nome: str, descricao: str) -> None:
        self.nome = nome
        self.descricao = descricao
        self.taxa_hz = mic.MIC_TAXA_HZ
        self.canais = mic.MIC_CANAIS
        self.parada = False

    def iniciar(self) -> bool:
        return True

    def parar(self) -> None:
        self.parada = True


@pytest.fixture(autouse=True)
def sem_pactl(monkeypatch: pytest.MonkeyPatch) -> None:
    """NENHUM `pactl` e NENHUM processo saem deste arquivo.

    Ela tem quatro DualSense de pé e o som da máquina inteira passa pelo mesmo
    servidor. Os dublês entram nos TRÊS pontos de saída do módulo — a fábrica
    do nó, o `pactl` do `desmutar` e o `Popen` do alimentador — e não nos
    argumentos de cada chamada, porque o caminho que esta sprint acrescenta
    (`BtMicSubsystem._renomear_os_canais_velhos`) chama `renomear` com os
    padrões de PRODUÇÃO, como o daemon chama.
    """
    monkeypatch.setattr(canal, "SourceVirtualPipeWire", _SourceEspia)
    monkeypatch.setattr(canal, "_rodar_pactl", lambda argv: True)
    monkeypatch.setattr(canal, "_lancar_processo", lambda argv: None)


@pytest.fixture
def canal_limpo() -> Any:
    """Esvazia as tabelas do dono antes e depois."""
    for tabela in (canal._DE_PE, canal._ALIMENTANDO, canal._FONTE_PEDIDA):
        tabela.clear()
    try:
        yield
    finally:
        for tabela in (canal._DE_PE, canal._ALIMENTANDO, canal._FONTE_PEDIDA):
            tabela.clear()


def _abrir(uniq: str, descricao: str, fonte: str | None = None) -> Any:
    return canal.abrir(uniq, descricao, fonte=fonte)


def test_o_canal_do_microfone_renasce_com_o_assento_de_agora(
    canal_limpo: None, numerador: dict[str, int]
) -> None:
    """O gêmeo, e o caso REAL dele: três de quatro errados, um sem número.

    MORDIDA: faça `canal_do_microfone.renomear` devolver `None` sempre e os
    quatro rótulos ficam onde estavam — inclusive o que nunca teve número.
    """
    # O estado de 20/09: um sem número, um com o número de outro, dois certos.
    _abrir(_P2, "Microfone do Controle")
    _abrir(_P4, "Microfone do Controle 2")
    _abrir(_P3, "Microfone do Controle 1")
    _abrir(_P1, "Microfone do Controle 3")

    novos = {
        uniq: canal.renomear(uniq, mic.descricao_do_microfone(uniq))
        for uniq in _ASSENTOS_DE_AGORA
    }

    assert {u: s.descricao for u, s in canal._DE_PE.items()} == {
        _P2: "Microfone do Controle 2",
        _P4: "Microfone do Controle 4",
        _P3: "Microfone do Controle 3",
        _P1: "Microfone do Controle 1",
    }
    # Os quatro estavam errados de algum jeito, então os quatro renasceram.
    assert all(novo is not None for novo in novos.values())


def test_o_canal_certo_nao_e_republicado(
    canal_limpo: None, numerador: dict[str, int]
) -> None:
    """Republicar sem motivo tira o microfone de quem estiver gravando.

    MORDIDA: chame `fechar`/`abrir` sem consultar `rotulo_envelheceu` e o nó
    do controle que não mudou de assento cai na varredura seguinte.
    """
    antes = _abrir(_P2, "Microfone do Controle 2")
    assert canal.renomear(_P2, mic.descricao_do_microfone(_P2)) is None
    assert canal._DE_PE[_P2] is antes
    assert antes.parada is False


def test_a_fonte_do_cabo_volta_com_o_canal(
    canal_limpo: None, numerador: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """O canal do cabo renasce LENDO O MESMO nó ALSA — ou renasce mudo.

    A fonte vem de `_FONTE_PEDIDA` e não da tabela do alimentador: aqui o
    `parec` NÃO sobe (o `lancar` devolve `None`), que é o caso medido em que
    ler a fonte do alimentador devolveria `None`.

    MORDIDA: leia a fonte de `_ALIMENTANDO` e esta asserção cai — e na mesa
    dela o microfone do cabo fica mudo depois de uma renumeração.
    """
    _abrir(_P3, "Microfone do Controle 1", fonte="alsa_input.usb-DualSense")
    assert _P3 not in canal._ALIMENTANDO  # o alimentador não subiu, de propósito

    argvs: list[list[str]] = []

    def _espiar(argv: list[str]) -> Any:
        argvs.append(argv)
        return None

    monkeypatch.setattr(canal, "_lancar_processo", _espiar)
    canal.renomear(_P3, mic.descricao_do_microfone(_P3))
    assert canal._FONTE_PEDIDA[_P3] == "alsa_input.usb-DualSense"
    assert any("--device=alsa_input.usb-DualSense" in argv for argv in argvs)


# ---------------------------------------------------------------------------
# 4. CADA DONO RENOMEIA O QUE É DELE
# ---------------------------------------------------------------------------


class _PonteFalsa:
    """Uma ponte de rádio de mentira — só o que o supervisor pergunta a ela."""

    def __init__(self, uniq: str) -> None:
        self.no = mic.NoDualSenseBT(caminho="/dev/hidraw9", uniq=uniq, produto=0x0CE6)
        self.chamada = 0

    def renomear_a_source(self) -> bool:
        self.chamada += 1
        return True


def test_o_supervisor_delega_o_canal_do_radio_a_ponte(
    canal_limpo: None, numerador: dict[str, int]
) -> None:
    """A ponte guarda a referência viva; republicar por fora a deixa escrevendo
    num nó morto — o microfone mudo com tudo aparentemente de pé.

    MORDIDA: faça `_renomear_os_canais_velhos` chamar
    `canal_do_microfone.renomear` para TODO `uniq` de pé, inclusive os das
    pontes, e a chamada à ponte some — junto com a troca de referência dela.
    """
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    class _GerenciadorFalso:
        def __init__(self, ponte: _PonteFalsa) -> None:
            self.pontes = {"/dev/hidraw9": ponte}

    do_radio = _PonteFalsa(_P1)
    sub = BtMicSubsystem()
    sub._gerenciador = _GerenciadorFalso(do_radio)
    _abrir(_P3, "Microfone do Controle 1")
    sub._canais_do_cabo[_P3] = canal.nome_do_canal(_P3)

    renomeados = sub._renomear_os_canais_velhos()

    assert do_radio.chamada == 1
    assert _P3 in renomeados
    assert canal._DE_PE[_P3].descricao == "Microfone do Controle 3"


def test_a_ponte_so_renomeia_o_canal_que_ela_abriu(numerador: dict[str, int]) -> None:
    """Um canal que já estava no ar tem outro dono — e é ele quem o renomeia.

    MORDIDA: tire o `not self._canal_e_nosso` da recusa e a ponte republica o
    canal do cabo pelas costas do supervisor, que continua anunciando de pé um
    objeto morto.
    """
    no = mic.NoDualSenseBT(caminho="/dev/hidraw9", uniq=_P1, produto=0x0CE6)
    source = _SourceEspia(nome=canal.nome_do_canal(_P1), descricao="Microfone do Controle 3")
    ponte = mic.PonteMicBluetooth(no, source=source)
    assert ponte.renomear_a_source() is False
    assert source.descricao == "Microfone do Controle 3"
