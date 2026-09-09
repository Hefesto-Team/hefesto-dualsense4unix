"""Os QUATRO microfones: um nó por controle, com o nome DELA — MIC-OS-QUATRO-01.

A palavra dela, 08/09/2026 à noite: *"o lance dos 4 mic virtuais via bt pra cada
controle e cavbo"*.  <!-- noqa-acento: citação literal dela, palavra por palavra -->

E o NOME é decisão dela de 09/09/2026 (`D-0909-OS-NOS-SE-CHAMAM-ALTO-FALANTE-E-
MICROFONE-DO-CONTROLE-N`, palavra dela: *"4a"*): **«Microfone do Controle N»**,
com o número do ASSENTO, como na tela.

O QUE ESTE ARQUIVO MORDE, e os três são defeitos MEDIDOS nesta árvore
---------------------------------------------------------------------

1. **O rótulo dizia o TRANSPORTE e publicava o ENDEREÇO dela.** A ponte
   batizava o nó de ``Microfone DualSense BT (aa:bb:cc:…)`` — o MAC do
   controle dela na lista de dispositivos de áudio de toda aplicação que abre
   um seletor de microfone.
2. **A palavra dela sobre o microfone de um controle no CABO evaporava.** O
   supervisor lia só o rádio e tratava *"não está no rádio"* como *"saiu da
   mesa"*. Medido, com o registro em mãos: a palavra dura até a varredura
   seguinte — e `dizer_no_ar` acorda o laço, então "seguinte" é imediato.
3. **No CABO ninguém erguia o canal com nome de controle.** `canal_do_microfone
   .abrir` tinha UM chamador em `src/`, e era a ponte de rádio. Sem o canal do
   cabo a mesa nunca chega a QUATRO, e trocar o fio pelo rádio continua
   trocando o microfone de nome.

**NADA AQUI FALA COM O PIPEWIRE DELA.** Nenhum `pactl` de verdade, nenhum
módulo carregado, nenhum `parec`: os dois donos (`canal_do_microfone.abrir` e
`fechar`) entram dublados, e o que se mede é quem chamou o quê, com que nome.

OS ENDEREÇOS SÃO SINTÉTICOS E MASCARADOS — octetos 4 e 5 zerados, a máscara da
casa.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import bt_mic
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt

#: Quatro controles, quatro endereços — sintéticos, com a máscara da casa.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"
P4 = "aa:bb:cc:00:00:04"
OS_QUATRO = (P1, P2, P3, P4)


def _hex(uniq: str) -> str:
    """A chave do registro: doze hex minúsculos, sem separador."""
    return uniq.replace(":", "").lower()


class _BackendDaMesa:
    """O backend do daemon, do jeito que este subsystem o consulta.

    Fiel no que importa: `describe_controllers()` devolve UMA entrada por
    handle, com `index` (a posição em `list(self._handles)`, 0 = primário),
    `connected` e `uniq`. É a MESMA lista que o `state_full` publica como
    `controllers` e que desenha os cards — por isso o assento sai daqui.
    """

    def __init__(self, uniqs: tuple[str, ...], desconectado: str | None = None) -> None:
        self.itens = [
            {
                "index": i,
                "connected": u != desconectado,
                "uniq": u,
                "transport": "usb",
                "is_primary": i == 0,
            }
            for i, u in enumerate(uniqs)
        ]

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self.itens]


class _Contexto:
    """O `DaemonContext` reduzido ao que o `start` deste subsystem lê."""

    def __init__(self, controller: Any) -> None:
        self.controller = controller
        self.config = None


@pytest.fixture()
def numerador_limpo():  # type: ignore[no-untyped-def]
    """Devolve o numerador global ao que era — ele é estado de PROCESSO.

    Sem isto uma régua que instala o gancho envenena a próxima pela ordem dos
    testes, que é o defeito `duble-que-nao-muda-resultado-so-esconde` visto do
    outro lado.
    """
    anterior = bt.registrar_numerador_de_assento(None)
    yield
    bt.registrar_numerador_de_assento(anterior)


# ---------------------------------------------------------------------------
# MORDIDA 1 — o rótulo é o dela, e ele NÃO carrega o endereço do controle
# ---------------------------------------------------------------------------


def test_o_rotulo_do_no_e_microfone_do_controle_n(numerador_limpo) -> None:  # type: ignore[no-untyped-def]
    """Com o assento sabido, o nó nasce «Microfone do Controle N»."""
    bt.registrar_numerador_de_assento(lambda u: {P1: 1, P2: 2, P3: 3, P4: 4}.get(u))

    rotulos = [bt.descricao_do_microfone(u) for u in OS_QUATRO]

    assert rotulos == [
        "Microfone do Controle 1",
        "Microfone do Controle 2",
        "Microfone do Controle 3",
        "Microfone do Controle 4",
    ], f"os quatro nós não têm o nome que ela decidiu: {rotulos}"
    assert len(set(rotulos)) == 4, (
        "dois controles com o MESMO rótulo na lista de entrada dela — o nome "
        "deixa de dizer qual é qual"
    )


def test_o_rotulo_nunca_carrega_o_endereco_do_controle(numerador_limpo) -> None:  # type: ignore[no-untyped-def]
    """O MAC dela não entra na lista de dispositivos de áudio da máquina.

    **A MORDIDA:** devolva a f-string de antes de 09/09 —
    ``f"Microfone DualSense BT ({uniq})"`` — e esta régua reprova nomeando os
    dois defeitos que ela carregava: o endereço à mostra e a palavra do
    transporte no lugar da palavra dela.

    A varredura é por PEDAÇO do endereço, e não pelo endereço inteiro: um
    rótulo com ``aabbcc000001`` (sem os dois-pontos) ou com só o rabo
    ``000001`` vaza a mesma identidade. É a mesma forma de régua do
    `check_endereco_de_radio.py`, que pega por FORMA e não por lista.
    """
    for numero, uniq in enumerate(OS_QUATRO, start=1):
        bt.registrar_numerador_de_assento(lambda _u, n=numero: n)
        rotulo = bt.descricao_do_microfone(uniq)
        sem_pontuacao = _hex(uniq)
        for pedaco in (uniq, sem_pontuacao, sem_pontuacao[-6:]):
            assert pedaco not in rotulo.lower(), (
                f"o rótulo do nó publica o endereço do controle: {rotulo!r} "
                f"carrega {pedaco!r}"
            )
        assert "bt" not in rotulo.lower() and "usb" not in rotulo.lower(), (
            f"o rótulo diz o TRANSPORTE: {rotulo!r} — trocar o fio pelo rádio "
            "voltaria a trocar o nome do microfone daquele controle"
        )


def test_sem_assento_sabido_nao_se_inventa_numero(numerador_limpo) -> None:  # type: ignore[no-untyped-def]
    """Ninguém atendendo = rótulo sem número, nunca um número chutado.

    Uma lista com dois «Microfone do Controle 1» é pior que uma com dois
    «Microfone do Controle»: o número repetido MENTE sobre qual é qual.
    """
    assert bt.descricao_do_microfone(P1) == "Microfone do Controle"

    # E um numerador que responde bobagem vale como "não sei" — `True` é `int`
    # em Python e viraria o assento 1 calado.
    for resposta in (0, -3, True, "2", None):
        bt.registrar_numerador_de_assento(lambda _u, r=resposta: r)
        assert bt.descricao_do_microfone(P1) == "Microfone do Controle", (
            f"o numerador respondeu {resposta!r} e virou assento"
        )

    # E um numerador que EXPLODE não pode derrubar a ponte subindo.
    def _explode(_u: str) -> int:
        raise RuntimeError("o daemon caiu no meio")

    bt.registrar_numerador_de_assento(_explode)
    assert bt.descricao_do_microfone(P1) == "Microfone do Controle"


def test_a_ponte_do_radio_batiza_o_no_com_o_nome_dela(  # type: ignore[no-untyped-def]
    monkeypatch, numerador_limpo
) -> None:
    """O rótulo chega ao NÓ pela ponte — e não só à função que o compõe.

    Régua de PRODUTO e não de texto: sobe a `PonteMicBluetooth` de verdade, com
    o dono do canal dublado, e lê a descrição com que ela pediu o nó.
    """
    from hefesto_dualsense4unix.integrations import canal_do_microfone

    bt.registrar_numerador_de_assento(lambda _u: 2)
    pedidos: list[tuple[str, str]] = []
    leitura, escrita = os.pipe()
    os.close(escrita)

    class _CanalDeMentira:
        nome = "hefesto_mic_000002"

        def iniciar(self) -> bool:
            # False de propósito: a régua quer a DESCRIÇÃO com que o canal foi
            # pedido, não uma thread de áudio de mentira girando na suíte.
            return False

    monkeypatch.setattr(
        canal_do_microfone,
        "abrir",
        lambda uniq, descricao, **_kw: pedidos.append((uniq, descricao))
        or _CanalDeMentira(),
    )
    no = bt.NoDualSenseBT(caminho="/dev/hidraw9", uniq=P2, produto=0x0CE6)
    ponte = bt.PonteMicBluetooth(
        no, opener=lambda _c: leitura, decodificador=object()
    )

    assert ponte.iniciar() is False  # o canal dublado recusa; é o combinado
    assert pedidos, "a ponte não pediu o canal por controle"
    assert pedidos[0][1] == "Microfone do Controle 2", (
        f"a ponte batizou o nó de {pedidos[0][1]!r} — o nome dela não chegou "
        "ao produto"
    )


# ---------------------------------------------------------------------------
# MORDIDA 2 — a palavra dela sobre o microfone do CABO sobrevive à varredura
# ---------------------------------------------------------------------------


class _NoDeRadio:
    def __init__(self, uniq: str) -> None:
        self.uniq = uniq


def test_a_palavra_dela_sobre_o_mic_do_cabo_sobrevive_a_varredura() -> None:
    """Ela aperta o botão do microfone de um controle NO FIO. A palavra fica.

    **O DEFEITO, MEDIDO NESTA ÁRVORE** (`_esquecer_quem_saiu_da_mesa` lendo só
    o rádio)::

        sub.no_ar(<controle do cabo>, True)   -> palavra: {…: True}
        sub._esquecer_quem_saiu_da_mesa([<só o do rádio>])
                                              -> palavra: {}

    **A MORDIDA:** troque `do_radio | self.uniqs_na_mesa()` por `do_radio` em
    `_esquecer_quem_saiu_da_mesa` e esta régua reprova.
    """
    registro = bt_mic.RegistroDePedidosDeCanal()
    sub = bt_mic.BtMicSubsystem(registro=registro)
    sub._backend = _BackendDaMesa((P1, P2))

    sub.no_ar(P1, True)
    assert registro.no_ar() == {_hex(P1): True}

    # Uma varredura: o rádio só mostra o P2. O P1 está no CABO, na mesa dela.
    sub._esquecer_quem_saiu_da_mesa([_NoDeRadio(P2)])

    assert registro.no_ar() == {_hex(P1): True}, (
        "a palavra dela sobre o microfone do controle do CABO foi apagada na "
        "primeira varredura"
    )
    assert _hex(P1) in registro.abertos(), (
        "o pedido de canal do controle do cabo foi esquecido junto"
    )


def test_quem_sai_da_mesa_de_verdade_continua_sendo_esquecido() -> None:
    """A cura não pode virar *"o pedido nunca morre"* — isso é o "liga sozinho".

    O controle que sai do rádio E do backend perde o pedido, como sempre. Sem
    esta metade, a reconexão dele subiria a ponte sozinha.
    """
    registro = bt_mic.RegistroDePedidosDeCanal()
    sub = bt_mic.BtMicSubsystem(registro=registro)
    sub._backend = _BackendDaMesa((P1, P2), desconectado=P1)

    sub.no_ar(P1, True)
    sub._esquecer_quem_saiu_da_mesa([_NoDeRadio(P2)])

    assert registro.no_ar() == {}, (
        "o controle saiu da mesa e a palavra dela sobre ele ficou de pé"
    )
    assert registro.abertos() == frozenset()


# ---------------------------------------------------------------------------
# MORDIDA 3 — o supervisor ergue o canal do CABO, e só de quem PEDIU
# ---------------------------------------------------------------------------


@pytest.fixture()
def dono_dublado(monkeypatch):  # type: ignore[no-untyped-def]
    """`canal_do_microfone` sem PipeWire: guarda quem subiu e quem caiu."""
    from hefesto_dualsense4unix.integrations import canal_do_microfone
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as el

    abertos: dict[str, str] = {}
    registro = {"abriu": [], "fechou": []}  # type: dict[str, list[Any]]

    def _abrir(uniq: str, descricao: str, **kw: Any) -> Any:
        registro["abriu"].append((uniq, descricao, kw.get("fonte")))
        nome = canal_do_microfone.nome_do_canal(uniq)
        abertos[uniq] = nome
        return type("Canal", (), {"nome": nome})()

    def _fechar(uniq: str) -> bool:
        registro["fechou"].append(uniq)
        return abertos.pop(uniq, None) is not None

    monkeypatch.setattr(canal_do_microfone, "abrir", _abrir)
    monkeypatch.setattr(canal_do_microfone, "fechar", _fechar)
    monkeypatch.setattr(canal_do_microfone, "de_pe", lambda: dict(abertos))
    monkeypatch.setattr(el, "casamento_usb_agora", lambda _m: None)
    return registro


#: O nó ALSA do cabo de UM controle. Nome real desta máquina, sem serial.
FONTE_DO_CABO = "alsa_input.usb-Sony_DualSense_Wireless_Controller-00.iec958-stereo"


def _com_uma_fonte(monkeypatch, fontes: list[str]) -> None:
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as el

    monkeypatch.setattr(el, "fontes_de_captura_agora", lambda: list(fontes))


def test_sem_toque_dela_nenhum_canal_do_cabo_sobe(  # type: ignore[no-untyped-def]
    monkeypatch, dono_dublado
) -> None:
    """Nada pedido = nada carregado. A privacidade é a mesma do rádio.

    Um canal do cabo carrega um `module-pipe-source` no servidor e um `parec`
    lendo o microfone dela. Ele não pode nascer por o daemon ter subido.
    """
    _com_uma_fonte(monkeypatch, [FONTE_DO_CABO])
    sub = bt_mic.BtMicSubsystem(registro=bt_mic.RegistroDePedidosDeCanal())
    sub._backend = _BackendDaMesa((P1,))

    sub._reconciliar_o_cabo([])

    assert dono_dublado["abriu"] == [], (
        "o supervisor ergueu canal sem ninguém ter apertado o botão do microfone"
    )


def test_o_toque_dela_ergue_o_canal_do_cabo_com_o_no_alsa(  # type: ignore[no-untyped-def]
    monkeypatch, dono_dublado, numerador_limpo
) -> None:
    """Ela liga o microfone de um controle no FIO: o canal com nome dele sobe.

    **A MORDIDA:** apague a chamada a `_reconciliar_o_cabo` no laço, ou o corpo
    de `_abrir_os_canais_do_cabo`, e esta régua reprova nomeando o controle.

    E ele sobe alimentado pelo nó ALSA — a resposta de `escolher_fonte` para
    *"de onde eu leio"*, não a do próprio canal.
    """
    bt.registrar_numerador_de_assento(lambda _u: 1)
    _com_uma_fonte(monkeypatch, [FONTE_DO_CABO])
    sub = bt_mic.BtMicSubsystem(registro=bt_mic.RegistroDePedidosDeCanal())
    sub._backend = _BackendDaMesa((P1,))

    sub.no_ar(P1, True)
    sub._reconciliar_o_cabo([])

    assert dono_dublado["abriu"] == [
        (_hex(P1), "Microfone do Controle 1", FONTE_DO_CABO)
    ], f"o canal do cabo do P1 não subiu como devia: {dono_dublado['abriu']}"
    assert sub._canais_do_cabo == {_hex(P1): "hefesto_mic_000001"}


def test_o_supervisor_do_cabo_nao_encosta_em_quem_esta_no_radio(  # type: ignore[no-untyped-def]
    monkeypatch, dono_dublado
) -> None:
    """Quem está no rádio é da PONTE — o supervisor não sobe nem derruba.

    Os dois transportes publicam o MESMO nó, e quem carrega um
    `module-pipe-source` com nome que já existe derruba o de pé como órfão
    (`SourceVirtualPipeWire.iniciar`). Um supervisor que não respeitasse a
    posse faria o microfone dela entregar zeros perfeitos — o defeito
    MIC-RADIO-ORFAO-01, de volta por outra porta.
    """
    _com_uma_fonte(monkeypatch, [FONTE_DO_CABO])
    sub = bt_mic.BtMicSubsystem(registro=bt_mic.RegistroDePedidosDeCanal())
    sub._backend = _BackendDaMesa((P1,))

    sub.no_ar(P1, True)
    sub._reconciliar_o_cabo([_NoDeRadio(P1)])

    assert dono_dublado["abriu"] == [], (
        "o supervisor do cabo ergueu o canal de um controle que está no rádio "
        "— os dois disputariam o mesmo nome de nó"
    )
    assert dono_dublado["fechou"] == []


def test_o_canal_do_cabo_cai_quando_ela_desliga(  # type: ignore[no-untyped-def]
    monkeypatch, dono_dublado, numerador_limpo
) -> None:
    """Soltar o pedido derruba o canal — e o `parec` que lia o microfone dela."""
    bt.registrar_numerador_de_assento(lambda _u: 1)
    _com_uma_fonte(monkeypatch, [FONTE_DO_CABO])
    registro = bt_mic.RegistroDePedidosDeCanal()
    sub = bt_mic.BtMicSubsystem(registro=registro)
    sub._backend = _BackendDaMesa((P1,))

    sub.no_ar(P1, True)
    sub._reconciliar_o_cabo([])
    assert sub._canais_do_cabo

    registro.soltar(P1)
    sub._reconciliar_o_cabo([])

    assert dono_dublado["fechou"] == [_hex(P1)], (
        "ela desligou o microfone e o canal do cabo ficou de pé, com o "
        f"alimentador lendo: {dono_dublado['fechou']}"
    )
    assert sub._canais_do_cabo == {}


def test_o_canal_do_cabo_passa_de_mao_quando_o_controle_vai_para_o_radio(  # type: ignore[no-untyped-def]
    monkeypatch, dono_dublado, numerador_limpo
) -> None:
    """Fio -> rádio: o supervisor SOLTA o nó antes de a ponte nascer.

    A ordem no laço é o que faz a troca ser uma passagem de mão, e não uma
    disputa: `_reconciliar_o_cabo` roda ANTES do `reconciliar` do gerenciador,
    então o nó do cabo já saiu quando a ponte tenta subir o dela.
    """
    bt.registrar_numerador_de_assento(lambda _u: 1)
    _com_uma_fonte(monkeypatch, [FONTE_DO_CABO])
    sub = bt_mic.BtMicSubsystem(registro=bt_mic.RegistroDePedidosDeCanal())
    sub._backend = _BackendDaMesa((P1,))

    sub.no_ar(P1, True)
    sub._reconciliar_o_cabo([])
    assert sub._canais_do_cabo

    # O mesmo controle aparece no rádio: o pedido continua aberto, mas o dono
    # do canal passa a ser a ponte.
    sub._reconciliar_o_cabo([_NoDeRadio(P1)])

    assert dono_dublado["fechou"] == [_hex(P1)]
    assert sub._canais_do_cabo == {}


# ---------------------------------------------------------------------------
# O ASSENTO — e por que ele NÃO é o número que o jogo vê
# ---------------------------------------------------------------------------


def test_o_assento_e_a_posicao_na_mesa_e_nao_o_numero_do_coop() -> None:
    """Quatro controles, quatro assentos — e o co-op não entra nesta conta.

    `coop.resolve_player_numbers` responde `1` para TODOS os controles quando o
    co-op está desligado. Batizar os nós por ele poria quatro «Microfone do
    Controle 1» na lista dela.
    """
    sub = bt_mic.BtMicSubsystem(registro=bt_mic.RegistroDePedidosDeCanal())
    sub._backend = _BackendDaMesa(OS_QUATRO)

    assentos = [sub.numero_do_assento(u) for u in OS_QUATRO]

    assert assentos == [1, 2, 3, 4], f"os assentos não saem da mesa: {assentos}"
    assert sub.numero_do_assento("aa:bb:cc:00:00:09") is None, (
        "um controle que não está na mesa ganhou assento"
    )


def test_o_gancho_do_assento_sobe_e_desce_com_o_subsystem(  # type: ignore[no-untyped-def]
    numerador_limpo,
) -> None:
    """Instalado no `start`, devolvido no `stop` — como os outros três ganchos.

    Um gancho que ficasse de pé com o subsystem parado responderia sobre uma
    mesa que ninguém está lendo mais.
    """
    import asyncio

    sub = bt_mic.BtMicSubsystem(gerenciador=_GerenciadorDeMentira())
    ctx = _Contexto(_BackendDaMesa((P1, P2)))

    asyncio.run(sub.start(ctx))  # type: ignore[arg-type]
    try:
        assert bt.descricao_do_microfone(P2) == "Microfone do Controle 2", (
            "o subsystem subiu e o nó continuou sem assento"
        )
    finally:
        asyncio.run(sub.stop())

    assert bt.descricao_do_microfone(P2) == "Microfone do Controle", (
        "o subsystem parou e o numerador dele continuou respondendo"
    )


class _GerenciadorDeMentira:
    """O gerenciador de pontes, reduzido ao que o laço deste subsystem chama."""

    def __init__(self) -> None:
        self.pontes: dict[str, Any] = {}

    def reconciliar(self, _alvos: list[Any]) -> None:
        return None

    def dormir(self, _s: float) -> bool:
        return True

    def parar(self) -> None:
        return None
