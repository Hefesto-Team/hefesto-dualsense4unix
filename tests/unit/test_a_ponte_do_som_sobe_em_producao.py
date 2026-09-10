"""A ponte de som por rádio é CONSTRUÍDA por linha de produção — SOM-FIADO-01.

O DEFEITO QUE ESTA RÉGUA MATA, e ele tem data
----------------------------------------------
Em 10/09/2026 o som saiu pelo rádio de verdade: report ``0x35``, 334 B, um
quadro Opus, 70 segundos com a orelha dela. `PonteDeSomPorRadio` nasceu no
mesmo dia, com teste, com o arranjo provado byte a byte — **e nenhuma linha de
produção a construía**. O único lugar do repositório onde o nome aparecia fora
do módulo que a define era a assinatura de um construtor que ninguém chamava.

A escada desta casa é ``MONTOU → SAIU NO FIO → O APARELHO OBEDECEU → O JOGO
RECEBEU → O JOGO REAGIU``, e o alto-falante passou meses em ``MONTOU`` sendo
lido como pronto. O portão `casa-sabe` acusava exatamente isto:

    'integrations/alto_falante_bt.py::PonteDeSomPorRadio'  ← sem chamador

**Uma peça verde que ninguém liga é o defeito que esta régua existe para não
deixar repetir.**

O QUE ELA TRAVA — e são cinco contratos, não um
------------------------------------------------
1. o subsystem constrói UMA ponte POR CONTROLE, e só para quem está no rádio;
2. cada ponte recebe o hidraw DAQUELE controle e o monitor do nó DAQUELE
   controle — uma ponte compartilhada mandaria o som do P2 pelo alto-falante
   do P1, que é a família de defeito que ``sink_do_controle`` já pagou no cabo;
3. a ponte sobe ANTES do nó, porque ``rota_do_no`` pergunta a ela no instante
   em que o nó nasce;
4. quem sai da lista perde a ponte (fd de hidraw e ``pw-record`` não vazam);
5. o ``start()`` de produção injeta o callable no gerenciador — sem isso o
   gerenciador nunca pergunta a ninguém e a rota do rádio nasce recusada.

A MORDIDA
----------
Apague ``self._casar_as_pontes(alvos)`` de ``_reconciliar`` e os quatro
primeiros reprovam. Tire ``ponte_do_radio_por_controle=`` do ``start()`` e o
quinto reprova.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod


@dataclass
class _Controle:
    uniq: str
    caminho: str
    transporte: str


class _PonteDeMentira:
    """Um dublê que responde como a ponte real — e GUARDA o que recebeu.

    O que ele NÃO faz é abrir hidraw, subir thread ou falar com o rádio. O que
    esta régua mede é a FIAÇÃO; o comportamento da ponte de verdade está em
    `test_a_ponte_do_som_e_de_cada_controle.py`, com a mordida dele.
    """

    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.abrir_hidraw = kw["abrir_hidraw"]
        self.fonte_de_pcm = kw["fonte_de_pcm"]
        self.gravador = kw.get("gravador")
        self.motivo = ""
        self.subiu = False
        self.desceu = False
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        self.subiu = True
        return True

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        return True

    def esta_de_pe(self) -> bool:
        return self.subiu and not self.desceu


class _GerenciadorDeMentira:
    def __init__(self) -> None:
        self.recebeu: list[list[Any]] = []

    def reconciliar(self, controles: list[Any] | None = None) -> None:
        self.recebeu.append(list(controles or []))

    def dormir(self, _s: float) -> bool:
        return False

    def parar(self) -> None:
        return None


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """A mesa de quatro: três no rádio, um no cabo. É a cena dela."""
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    _PonteDeMentira.criadas = []
    ordem: list[str] = []
    monitores: dict[str, str] = {}

    def _fonte_do_monitor(id_do_no: str, **_: Any) -> tuple[Any, Any, str]:
        monitores[id_do_no] = id_do_no
        return (lambda _n: b""), f"gravador:{id_do_no}", ""

    def _ponte(**kw: Any) -> _PonteDeMentira:
        ordem.append(f"ponte:{kw['uniq']}")
        return _PonteDeMentira(**kw)

    abertos: list[str] = []

    class _No:
        def __init__(self, caminho: str) -> None:
            abertos.append(caminho)
            self.fd = 100 + len(abertos)

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _fonte_do_monitor)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _ponte)
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: _No(no))

    controles = [
        _Controle("aa:bb:cc:00:00:01", "/dev/hidraw1", "bluetooth"),
        _Controle("aa:bb:cc:00:00:02", "/dev/hidraw2", "bluetooth"),
        _Controle("aa:bb:cc:00:00:03", "/dev/hidraw3", "bluetooth"),
        _Controle("aa:bb:cc:00:00:04", "/dev/hidraw4", "usb"),
    ]
    ger = _GerenciadorDeMentira()
    sub = mod.AltoFalanteSubsystem(
        gerenciador=ger, fonte_de_controles=lambda: list(controles)
    )
    sub._gerenciador = ger

    def _reconciliar_com_ordem(g: Any) -> None:
        ordem.append("no")
        ger.reconciliar(g)

    return {
        "sub": sub,
        "ger": ger,
        "controles": controles,
        "ordem": ordem,
        "monitores": monitores,
        "abertos": abertos,
        "af": af,
    }


def test_uma_ponte_por_controle_no_radio_e_nenhuma_no_cabo(bancada: dict) -> None:
    """Três pontes para os três do rádio. O do cabo não ganha — e não é falha.

    No cabo o som vai pela placa ALSA que o próprio transporte publica; subir
    uma ponte de rádio ali seria um segundo caminho para o mesmo alto-falante.
    """
    sub = bancada["sub"]
    sub._reconciliar(bancada["ger"])

    assert sorted(sub._pontes) == [
        "aa:bb:cc:00:00:01",
        "aa:bb:cc:00:00:02",
        "aa:bb:cc:00:00:03",
    ], (
        "o subsystem não construiu uma ponte por controle no rádio — "
        f"construiu {sorted(sub._pontes)}"
    )
    assert "aa:bb:cc:00:00:04" not in sub._pontes, (
        "o controle do CABO ganhou ponte de rádio"
    )
    assert all(p.subiu for p in sub._pontes.values()), "as pontes não subiram"


def test_cada_ponte_leva_o_hidraw_e_o_monitor_DAQUELE_controle(  # noqa: N802
    bancada: dict,
) -> None:
    """O elo que impede o som do P2 de sair no alto-falante do P1.

    Uma ponte só, ou três pontes com o mesmo fd, passariam no teste acima e
    entregariam a cena errada na mesa dela. É por isso que este contrato é
    separado.
    """
    sub = bancada["sub"]
    af = bancada["af"]
    sub._reconciliar(bancada["ger"])

    for controle in bancada["controles"][:3]:
        ponte = sub._pontes[controle.uniq]
        ponte.abrir_hidraw()
        assert controle.caminho in bancada["abertos"], (
            f"a ponte de {controle.uniq} não abriu {controle.caminho}"
        )
        esperado = af.nome_do_sink(controle.uniq)
        assert ponte.gravador == f"gravador:{esperado}", (
            f"a ponte de {controle.uniq} está lendo o monitor de outro nó: "
            f"{ponte.gravador}"
        )

    assert len(set(id(p) for p in sub._pontes.values())) == 3, (
        "as três pontes são o mesmo objeto"
    )


def test_a_ponte_sobe_antes_do_no(bancada: dict) -> None:
    """A ORDEM, e ela é medida.

    ``rota_do_no`` chama ``ponte.esta_de_pe()`` no instante em que o nó é
    construído. Fiar na ordem inversa publica a rota do rádio como recusada e
    só a corrige na varredura seguinte — 2 s em que o jogo pega a rota errada.
    """
    sub = bancada["sub"]
    ordem = bancada["ordem"]
    ger = bancada["ger"]
    reconciliar_real = ger.reconciliar

    def _marcado(controles: list[Any] | None = None) -> None:
        ordem.append("no")
        reconciliar_real(controles)

    ger.reconciliar = _marcado  # type: ignore[method-assign]
    sub._reconciliar(ger)

    assert "no" in ordem, "o gerenciador de nós nunca foi chamado"
    primeira_ponte = next(i for i, x in enumerate(ordem) if x.startswith("ponte:"))
    assert primeira_ponte < ordem.index("no"), (
        f"o nó nasceu antes da ponte: {ordem}"
    )


def test_quem_sai_da_lista_perde_a_ponte(bancada: dict) -> None:
    """Um fd de hidraw e um `pw-record` por controle — eles não vazam."""
    sub = bancada["sub"]
    controles = bancada["controles"]
    sub._reconciliar(bancada["ger"])
    saiu = sub._pontes["aa:bb:cc:00:00:02"]

    controles.pop(1)
    sub._reconciliar(bancada["ger"])

    assert "aa:bb:cc:00:00:02" not in sub._pontes, "a ponte do que saiu ficou"
    assert saiu.desceu, "a ponte do que saiu não foi derrubada"
    assert sorted(sub._pontes) == [
        "aa:bb:cc:00:00:01",
        "aa:bb:cc:00:00:03",
    ], "derrubar um vizinho derrubou os outros"


def test_a_ponte_nao_e_reconstruida_a_cada_varredura(bancada: dict) -> None:
    """A varredura roda a cada 2 s. Reconstruir ali cortaria o som toda vez."""
    sub = bancada["sub"]
    sub._reconciliar(bancada["ger"])
    antes = dict(sub._pontes)
    sub._reconciliar(bancada["ger"])
    sub._reconciliar(bancada["ger"])

    assert all(sub._pontes[u] is p for u, p in antes.items()), (
        "a ponte foi reconstruída numa varredura sem mudança na lista"
    )
    assert len(_PonteDeMentira.criadas) == 3, (
        f"{len(_PonteDeMentira.criadas)} pontes construídas em 3 varreduras "
        "sem mudança — o som cortaria a cada uma"
    )


def test_o_stop_derruba_todas_as_pontes(bancada: dict) -> None:
    """Sem isto, cada `start()` seguinte abriria um segundo par por controle."""
    sub = bancada["sub"]
    sub._reconciliar(bancada["ger"])
    pontes = list(sub._pontes.values())

    asyncio.run(sub.stop())

    assert sub._pontes == {}, "sobraram pontes depois do stop"
    assert all(p.desceu for p in pontes), "alguma ponte ficou de pé sem dono"


def test_o_gerenciador_de_producao_recebe_o_callable_da_ponte() -> None:
    """O ``start()`` real injeta a resposta — e ela é POR CONTROLE.

    Sem esta injeção o gerenciador não tem a quem perguntar, ``rota_do_no``
    recusa o rádio com a frase honesta, e a ponte fica de pé entregando som a
    um nó que ninguém aponta.
    """
    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])

    class _Ctx:
        controller = None

    try:
        asyncio.run(sub.start(_Ctx()))
        ger = sub._gerenciador
        assert isinstance(ger, mod.GerenciadorDeNosDeSom)
        assert ger._ponte_do_radio_por_controle is not None, (
            "o gerenciador de produção nasceu sem saber a quem perguntar pela "
            "ponte — a rota do rádio nunca sairá de «recusada»"
        )
        assert ger._ponte_do_radio("nao-existe") is None, (
            "o callable devolveu algo para um controle SEM ponte; um "
            "`lambda: True` otimista publicaria rota sobre nada"
        )
    finally:
        asyncio.run(sub.stop())
