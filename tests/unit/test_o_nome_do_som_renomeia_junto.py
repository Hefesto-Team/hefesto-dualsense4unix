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

_SONY = " (DualSense Wireless Controller)"

_P2 = "aabbcc000001"
_P4 = "aabbcc000002"
_P3 = "aabbcc000003"
_P1 = "aabbcc000004"

_ASSENTOS_DE_AGORA = {_P2: 2, _P4: 4, _P3: 3, _P1: 1}

_ASSENTOS_DO_NOME = {_P2: 2, _P4: 4, _P3: 1, _P1: 3}


@pytest.fixture
def numerador() -> Any:
    """Instala um numerador de assento editável e o devolve ao fim."""
    assentos = dict(_ASSENTOS_DE_AGORA)
    anterior = mic.registrar_numerador_de_assento(lambda u: assentos.get(u))
    try:
        yield assentos
    finally:
        mic.registrar_numerador_de_assento(anterior)


def test_o_numero_sai_do_rotulo_nas_duas_familias() -> None:
    """A leitura é a INVERSA das duas funções que escrevem o rótulo."""
    assert mic.numero_do_rotulo("Alto-falante do Controle 3") == 3
    assert mic.numero_do_rotulo("Microfone do Controle 1") == 1
    assert mic.numero_do_rotulo("Alto-falante do Controle") is None
    assert mic.numero_do_rotulo("") is None
    assert mic.numero_do_rotulo("Microfone do Controle 0") is None
    assert mic.numero_do_rotulo(f"Microfone do Controle {chr(0x0661)}") is None


def test_perder_o_numero_nunca_conta_como_envelhecer() -> None:
    """É esta metade que impede a cura de virar um nó piscando."""
    assert not mic.rotulo_envelheceu(
        "Alto-falante do Controle 3" + _SONY, "Alto-falante do Controle" + _SONY
    )
    assert mic.rotulo_envelheceu(
        "Microfone do Controle" + _SONY, "Microfone do Controle 2" + _SONY
    )


def test_a_troca_entre_dois_rotulos_e_envelhecimento() -> None:
    """O defeito de 20/09 visto pela função: os dois lados acusam."""
    assert mic.rotulo_envelheceu(
        "Alto-falante do Controle 1" + _SONY, "Alto-falante do Controle 3" + _SONY
    )
    assert mic.rotulo_envelheceu(
        "Alto-falante do Controle 3" + _SONY, "Alto-falante do Controle 1" + _SONY
    )
    assert not mic.rotulo_envelheceu(
        "Alto-falante do Controle 2" + _SONY, "Alto-falante do Controle 2" + _SONY
    )


def test_a_regua_fraca_da_verde_sobre_a_troca() -> None:
    """O estado REAL da mesa dela passaria por uma régua de «tem número»."""
    no_ar = {
        uniq: f"Alto-falante do Controle {n}" + _SONY
        for uniq, n in _ASSENTOS_DO_NOME.items()
    }
    assert all(mic.numero_do_rotulo(r) is not None for r in no_ar.values())
    assert sorted(mic.numero_do_rotulo(r) or 0 for r in no_ar.values()) == [1, 2, 3, 4]

    de_agora = {
        uniq: f"Alto-falante do Controle {n}" + _SONY
        for uniq, n in _ASSENTOS_DE_AGORA.items()
    }
    velhos = [u for u in no_ar if mic.rotulo_envelheceu(no_ar[u], de_agora[u])]
    assert sorted(velhos) == sorted([_P3, _P1])


class _SinkEspiao:
    """Um `SinkVirtualPipeWire` de mentira que guarda o rótulo com que nasceu."""

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


def _mesa(
    monkeypatch: pytest.MonkeyPatch,
    sink: Any = _SinkEspiao,
    *,
    rota: Any = None,
) -> None:
    """Põe a fábrica de nós e a rota sob dublê. Nenhum `pactl` sai daqui."""
    monkeypatch.setattr(som, "SinkVirtualPipeWire", sink)
    monkeypatch.setattr(
        som,
        "rota_do_no",
        rota or (lambda u, t, mesa, **kw: som.RotaDoNo(True, sink=f"alsa_output.{u}")),
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
        uniq: f"Alto-falante do Controle {n}" + _SONY
        for uniq, n in _ASSENTOS_DE_AGORA.items()
    }


def test_a_renumeracao_chega_ao_rotulo_do_no_vivo(
    monkeypatch: pytest.MonkeyPatch, numerador: dict[str, int]
) -> None:
    """A MORDIDA DA SPRINT: força a troca de 20/09 e o nome vai junto."""
    _mesa(monkeypatch)
    ger = GerenciadorDeNosDeSom()
    ger.reconciliar(_controles())
    antes = dict(ger.nos)

    numerador[_P3], numerador[_P1] = 1, 3
    ger.reconciliar(_controles())

    assert _rotulos(ger) == {
        _P2: "Alto-falante do Controle 2" + _SONY,
        _P4: "Alto-falante do Controle 4" + _SONY,
        _P3: "Alto-falante do Controle 1" + _SONY,
        _P1: "Alto-falante do Controle 3" + _SONY,
    }
    assert ger.nos[_P2] is antes[_P2]
    assert ger.nos[_P4] is antes[_P4]
    assert ger.nos[_P3] is not antes[_P3]
    assert antes[_P3].parado is True
    assert antes[_P1].parado is True


def test_rotulo_igual_nao_encosta_no_no(
    monkeypatch: pytest.MonkeyPatch, numerador: dict[str, int]
) -> None:
    """Varredura sem novidade não derruba nada — ela roda de 5 em 5 segundos."""
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
    """Renomear é republicar, e republicar tira o dispositivo debaixo do jogo."""

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
    """`estado()` devolve `None` com o servidor em recuo — e "não sei" recusa."""

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
    """Com o numerador mudo o rótulo de agora perde o número — e nada acontece."""
    _mesa(monkeypatch)
    ger = GerenciadorDeNosDeSom()
    ger.reconciliar(_controles())
    antes = dict(ger.nos)
    numerador.clear()
    ger.reconciliar(_controles())
    assert all(ger.nos[u] is antes[u] for u in antes)
    assert _rotulos(ger) == {
        uniq: f"Alto-falante do Controle {n}" + _SONY
        for uniq, n in _ASSENTOS_DE_AGORA.items()
    }


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
    """O gêmeo, e o caso REAL dele: três de quatro errados, um sem número."""
    _abrir(_P2, "Microfone do Controle" + _SONY)
    _abrir(_P4, "Microfone do Controle 2" + _SONY)
    _abrir(_P3, "Microfone do Controle 1" + _SONY)
    _abrir(_P1, "Microfone do Controle 3" + _SONY)

    novos = {
        uniq: canal.renomear(uniq, mic.descricao_do_microfone(uniq))
        for uniq in _ASSENTOS_DE_AGORA
    }

    assert {u: s.descricao for u, s in canal._DE_PE.items()} == {
        _P2: "Microfone do Controle 2" + _SONY,
        _P4: "Microfone do Controle 4" + _SONY,
        _P3: "Microfone do Controle 3" + _SONY,
        _P1: "Microfone do Controle 1" + _SONY,
    }
    assert all(novo is not None for novo in novos.values())


def test_o_canal_certo_nao_e_republicado(
    canal_limpo: None, numerador: dict[str, int]
) -> None:
    """Republicar sem motivo tira o microfone de quem estiver gravando."""
    antes = _abrir(_P2, "Microfone do Controle 2" + _SONY)
    assert canal.renomear(_P2, mic.descricao_do_microfone(_P2)) is antes
    assert canal._DE_PE[_P2] is antes
    assert antes.parada is False


def test_a_fonte_do_cabo_volta_com_o_canal(
    canal_limpo: None, numerador: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """O canal do cabo renasce LENDO O MESMO nó ALSA — ou renasce mudo."""
    _abrir(_P3, "Microfone do Controle 1" + _SONY, fonte="alsa_input.usb-DualSense")
    assert _P3 not in canal._ALIMENTANDO

    argvs: list[list[str]] = []

    def _espiar(argv: list[str]) -> Any:
        argvs.append(argv)
        return None

    monkeypatch.setattr(canal, "_lancar_processo", _espiar)
    canal.renomear(_P3, mic.descricao_do_microfone(_P3))
    assert canal._FONTE_PEDIDA[_P3] == "alsa_input.usb-DualSense"
    assert any("--device=alsa_input.usb-DualSense" in argv for argv in argvs)


class _PonteFalsa:
    """Uma ponte de rádio de mentira — só o que o supervisor pergunta a ela."""

    def __init__(self, uniq: str) -> None:
        self.no = mic.NoDualSenseBT(caminho="/dev/hidraw9", uniq=uniq, produto=0x0CE6)
        self.chamada = 0

    @property
    def uniq_do_canal_proprio(self) -> str:
        return str(self.no.uniq)

    def renomear_a_source(self) -> bool:
        self.chamada += 1
        return True


def test_o_supervisor_delega_o_canal_do_radio_a_ponte(
    canal_limpo: None, numerador: dict[str, int]
) -> None:
    """A ponte guarda a referência viva; republicar por fora a deixa escrevendo"""
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    class _GerenciadorFalso:
        def __init__(self, ponte: _PonteFalsa) -> None:
            self.pontes = {"/dev/hidraw9": ponte}

    do_radio = _PonteFalsa(_P1)
    sub = BtMicSubsystem()
    sub._gerenciador = _GerenciadorFalso(do_radio)
    _abrir(_P3, "Microfone do Controle 1" + _SONY)
    sub._canais_do_cabo[_P3] = canal.nome_do_canal(_P3)
    da_ponte = _abrir(_P1, "Microfone do Controle 3" + _SONY)

    renomeados = sub._renomear_os_canais_velhos()

    assert do_radio.chamada == 1
    assert _P3 in renomeados
    assert canal._DE_PE[_P3].descricao == "Microfone do Controle 3" + _SONY
    assert canal.canal_de_pe(_P1) is da_ponte
    assert da_ponte.descricao == "Microfone do Controle 3" + _SONY
    assert da_ponte.parada is False


def test_a_ponte_so_renomeia_o_canal_que_ela_abriu(
    canal_limpo: None, numerador: dict[str, int]
) -> None:
    """Um canal que já estava no ar tem outro dono — e é ele quem o renomeia."""
    do_outro = _abrir(_P1, "Microfone do Controle 3" + _SONY)
    no = mic.NoDualSenseBT(caminho="/dev/hidraw9", uniq=_P1, produto=0x0CE6)
    ponte = mic.PonteMicBluetooth(no)
    ponte._source = ponte._abrir_o_canal_por_controle("Microfone do Controle 3" + _SONY)
    assert ponte._source is do_outro
    assert ponte.uniq_do_canal_proprio == ""

    assert ponte.renomear_a_source() is False
    assert canal.canal_de_pe(_P1) is do_outro
    assert do_outro.descricao == "Microfone do Controle 3" + _SONY
    assert do_outro.parada is False


def _sink_que_recusa(pares: set[tuple[str, Any]]) -> Any:
    """Um `_SinkEspiao` que se recusa a subir com certos `(uniq, rótulo)`."""

    class _Recusa(_SinkEspiao):
        def iniciar(self) -> bool:
            return (self.uniq, self.descricao) not in pares

    return _Recusa


def test_o_no_nao_some_quando_a_rota_nao_resolve(
    monkeypatch: pytest.MonkeyPatch, numerador: dict[str, int]
) -> None:
    """A rota some por uma varredura e o nó FICA — com o nome velho."""
    _mesa(monkeypatch)
    ger = GerenciadorDeNosDeSom()
    ger.reconciliar(_controles())
    antes = dict(ger.nos)

    _mesa(
        monkeypatch,
        rota=lambda u, t, mesa, **kw: som.RotaDoNo(False, motivo="sem placa"),
    )
    numerador[_P3], numerador[_P1] = 1, 3
    ger.reconciliar(_controles())

    assert set(ger.nos) == set(_ASSENTOS_DE_AGORA), (
        "um nó SUMIU da mesa dela para trocar de nome"
    )
    assert all(ger.nos[u] is antes[u] for u in antes)
    assert all(not no.parado for no in antes.values())
    assert _rotulos(ger)[_P3] == "Alto-falante do Controle 3" + _SONY
    assert _rotulos(ger)[_P1] == "Alto-falante do Controle 1" + _SONY


def test_o_no_volta_com_o_rotulo_velho_quando_o_renascimento_nao_sobe(
    monkeypatch: pytest.MonkeyPatch, numerador: dict[str, int]
) -> None:
    """O nó novo não sobe — e a VOLTA reergue o nó com o rótulo que estava no ar."""
    _mesa(monkeypatch)
    ger = GerenciadorDeNosDeSom()
    ger.reconciliar(_controles())
    antes = dict(ger.nos)

    _mesa(
        monkeypatch,
        sink=_sink_que_recusa(
            {
                (_P3, "Alto-falante do Controle 1" + _SONY),
                (_P1, "Alto-falante do Controle 3" + _SONY),
            }
        ),
    )
    numerador[_P3], numerador[_P1] = 1, 3
    ger.reconciliar(_controles())

    assert set(ger.nos) == set(_ASSENTOS_DE_AGORA), (
        "um nó SUMIU da mesa dela para trocar de nome"
    )
    assert ger.nos[_P3] is not antes[_P3]
    assert antes[_P3].parado is True
    assert _rotulos(ger)[_P3] == "Alto-falante do Controle 3" + _SONY
    assert _rotulos(ger)[_P1] == "Alto-falante do Controle 1" + _SONY
    assert ger.nos[_P2] is antes[_P2]


def test_o_canal_volta_com_o_rotulo_velho_quando_o_renascimento_nao_sobe(
    canal_limpo: None, numerador: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """O gêmeo do teste acima: `fechar` e o `abrir` seguinte recusa."""
    _abrir(_P3, "Microfone do Controle 1" + _SONY)

    class _RecusaONomeNovo(_SourceEspia):
        def iniciar(self) -> bool:
            return self.descricao != "Microfone do Controle 3" + _SONY

    monkeypatch.setattr(canal, "SourceVirtualPipeWire", _RecusaONomeNovo)
    de_pe = canal.renomear(_P3, mic.descricao_do_microfone(_P3))

    assert de_pe is not None, "o microfone dela SUMIU para trocar de nome"
    assert de_pe.descricao == "Microfone do Controle 1" + _SONY
    assert canal.canal_de_pe(_P3) is de_pe


def test_o_canal_que_nem_a_volta_ergue_devolve_none(
    canal_limpo: None, numerador: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nem a volta sobe — e o retorno diz isso, em vez do objeto morto."""
    velha = _abrir(_P3, "Microfone do Controle 1" + _SONY)

    class _NuncaSobe(_SourceEspia):
        def iniciar(self) -> bool:
            return False

    monkeypatch.setattr(canal, "SourceVirtualPipeWire", _NuncaSobe)
    assert canal.renomear(_P3, mic.descricao_do_microfone(_P3)) is None
    assert canal.canal_de_pe(_P3) is None
    assert velha.parada is True


def _ponte_com_canal_proprio(uniq: str, descricao: str) -> Any:
    """Uma `PonteMicBluetooth` de verdade com o canal aberto por ELA."""
    no = mic.NoDualSenseBT(caminho="/dev/hidraw9", uniq=uniq, produto=0x0CE6)
    ponte = mic.PonteMicBluetooth(no)
    ponte._source = ponte._abrir_o_canal_por_controle(descricao)
    return ponte


def test_a_ponte_troca_a_referencia_para_o_canal_que_renasceu(
    canal_limpo: None, numerador: dict[str, int]
) -> None:
    """O CAMINHO FELIZ DA PONTE, e ele estava sem régua nenhuma."""
    ponte = _ponte_com_canal_proprio(_P1, "Microfone do Controle 3" + _SONY)
    velha = ponte._source
    assert velha is not None
    assert ponte.uniq_do_canal_proprio == _P1

    assert ponte.renomear_a_source() is True

    novo = canal.canal_de_pe(_P1)
    assert novo is not None
    assert novo is not velha
    assert novo.descricao == "Microfone do Controle 1" + _SONY
    assert velha.parada is True
    assert ponte._source is novo


def test_a_ponte_solta_a_referencia_quando_o_canal_some(
    canal_limpo: None, numerador: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nem a volta subiu: a ponte não pode continuar anunciando um objeto morto."""
    ponte = _ponte_com_canal_proprio(_P1, "Microfone do Controle 3" + _SONY)
    velha = ponte._source

    class _NuncaSobe(_SourceEspia):
        def iniciar(self) -> bool:
            return False

    monkeypatch.setattr(canal, "SourceVirtualPipeWire", _NuncaSobe)
    assert ponte.renomear_a_source() is False
    assert ponte._source is None
    assert ponte.uniq_do_canal_proprio == ""
    assert velha.parada is True


def test_a_ponte_fica_com_o_canal_que_voltou_com_o_rotulo_velho(
    canal_limpo: None, numerador: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A volta trocou o OBJETO sem trocar o nome — e a ponte tem de saber disso."""
    ponte = _ponte_com_canal_proprio(_P1, "Microfone do Controle 3" + _SONY)
    velha = ponte._source

    class _RecusaONomeNovo(_SourceEspia):
        def iniciar(self) -> bool:
            return self.descricao != "Microfone do Controle 1" + _SONY

    monkeypatch.setattr(canal, "SourceVirtualPipeWire", _RecusaONomeNovo)
    assert ponte.renomear_a_source() is False
    assert ponte._source is not None
    assert ponte._source is not velha
    assert ponte._source.descricao == "Microfone do Controle 3" + _SONY
    assert ponte._source is canal.canal_de_pe(_P1)


class _BackendDeMesa:
    """O `describe_controllers()` do backend, com os controles que a tela mostra."""

    def __init__(self, *uniqs: str) -> None:
        self._uniqs = uniqs

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": u, "connected": True} for u in self._uniqs]


class _GerenciadorSemPonte:
    """O gerenciador de pontes do rádio, vazio: esta régua mede o CABO."""

    def __init__(self) -> None:
        self.pontes: dict[str, Any] = {}

    def reconciliar(self, alvos: list[Any]) -> None:
        del alvos

    def dormir(self, segundos: float) -> bool:
        del segundos
        return True

    def parar(self) -> None:
        return None


def _uma_volta_do_laco(
    sub: Any, monkeypatch: pytest.MonkeyPatch, supervisor: Any
) -> list[str]:
    """Roda UMA volta de `BtMicSubsystem._loop` e devolve o que ele engoliu."""
    engolidas: list[str] = []
    debug_de_verdade = supervisor.logger.debug

    def _espiar(evento: str, **campos: Any) -> Any:
        if evento == "bt_mic_reconciliacao_falhou":
            engolidas.append(str(campos))
        return debug_de_verdade(evento, **campos)

    monkeypatch.setattr(supervisor.logger, "debug", _espiar)
    monkeypatch.setattr(sub, "_dormir", lambda gerenciador: True)
    sub._loop()
    return engolidas


def test_o_laco_do_daemon_renomeia_os_canais_velhos(
    canal_limpo: None, numerador: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A FIAÇÃO, e é o que o conferente arrancou sem a régua piscar."""
    from hefesto_dualsense4unix.daemon.subsystems import bt_mic as supervisor

    sub = supervisor.BtMicSubsystem(registro=supervisor.RegistroDePedidosDeCanal())
    sub._gerenciador = _GerenciadorSemPonte()
    sub._backend = _BackendDeMesa(_P3)
    monkeypatch.setattr(mic, "nos_dualsense_bluetooth", lambda: [])
    assert sub._registro.pedir(_P3) is True

    _abrir(_P3, "Microfone do Controle 1" + _SONY)
    sub._canais_do_cabo[_P3] = canal.nome_do_canal(_P3)

    engolidas = _uma_volta_do_laco(sub, monkeypatch, supervisor)

    assert engolidas == [], f"o laço engoliu uma exceção: {engolidas}"
    de_pe = canal.canal_de_pe(_P3)
    assert de_pe is not None
    assert de_pe.descricao == "Microfone do Controle 3" + _SONY


def test_o_canal_sem_dono_ainda_tem_quem_o_renomeie(
    canal_limpo: None, numerador: dict[str, int]
) -> None:
    """O canal que NENHUMA ponte reclama — e que não tinha renomeador nenhum."""
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    sub = BtMicSubsystem()
    sub._gerenciador = _GerenciadorSemPonte()
    _abrir(_P2, "Microfone do Controle" + _SONY)
    assert sub._canais_do_cabo == {}

    assert sub._renomear_os_canais_velhos() == [_P2]
    de_pe = canal.canal_de_pe(_P2)
    assert de_pe is not None
    assert de_pe.descricao == "Microfone do Controle 2" + _SONY


def test_o_supervisor_solta_o_canal_do_cabo_que_sumiu(
    canal_limpo: None, numerador: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nem a volta subiu: a tabela do supervisor não pode dizer que ele está de pé."""
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import BtMicSubsystem

    sub = BtMicSubsystem()
    sub._gerenciador = _GerenciadorSemPonte()
    _abrir(_P3, "Microfone do Controle 1" + _SONY)
    sub._canais_do_cabo[_P3] = canal.nome_do_canal(_P3)

    class _NuncaSobe(_SourceEspia):
        def iniciar(self) -> bool:
            return False

    monkeypatch.setattr(canal, "SourceVirtualPipeWire", _NuncaSobe)
    assert sub._renomear_os_canais_velhos() == []
    assert canal.canal_de_pe(_P3) is None
    assert _P3 not in sub._canais_do_cabo
