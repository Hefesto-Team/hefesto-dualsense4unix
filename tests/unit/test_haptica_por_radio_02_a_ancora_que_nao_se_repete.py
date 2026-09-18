"""HAPTICA-POR-RADIO — a âncora que não se repete e a ponte que volta ao som.

INSTALL-UNIVERSAL (18/09/2026). Dois defeitos do endpoint de háptica pelo
rádio que não dependem da máquina dela, e por isso chegariam a qualquer outra:

1. **A ÂNCORA REPETIDA.** A distribuição ordenava TODOS os controles vivos e
   dava a i-ésima âncora ao i-ésimo; quem já tinha endpoint era só pulado. B
   conecta sozinho e fica com a âncora 0; A chega depois, com A < B, e a
   ordenação dá a âncora 0 a A também. Dois nós com o mesmo ``ContainerId``: a
   háptica de um jogador vai para o outro. O mesmo com o adaptador que cai e
   devolve os controles em outra ordem — e, depois de cada restart do daemon, a
   ordenação desfazia as âncoras que o servidor tinha de pé e recarregava nós
   vivos.

2. **A PONTE QUE NÃO VOLTAVA AO SOM.** O modo háptica era decidido pelo
   ``RUNNING`` do sink, e no modo háptica a própria ponte lê o monitor do
   endpoint — um leitor segura o nó em ``RUNNING``. Fechado o jogo, a ponte
   seguia no arranjo da háptica, que não leva áudio, e o alto-falante do
   controle ficava mudo. Quem toca no sink é um sink-input; o nosso gravador
   não é um.

As réguas de subsystem usam o ``EndpointDeHaptica`` DE VERDADE contra um
servidor de som de mentira: é o ``sysfs.path`` que chega ao servidor que o jogo
lê, e é ele que se mede. Nada toca o PipeWire dela; os ``uniq`` são da faixa
sintética ``aa:bb:cc``.

LIMITE DECLARADO: é fiação e conta. A prova com o jogo aberto e o escritor
único é bancada, e está pendente.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

_A = "aa:bb:cc:00:00:01"
_B = "aa:bb:cc:00:00:02"
_C = "aa:bb:cc:00:00:03"
_D = "aa:bb:cc:00:00:04"


def _ancora(i: int) -> eh.Ancora:
    return eh.Ancora(
        syspath=f"/devices/pci0000:00/usb3/3-{i}",
        declarado=f"/devices/pci0000:00/usb3/3-{i}/3-{i}:1.0",
    )


_QUATRO = [_ancora(i) for i in range(4)]


def _no(uniq: str, ancora: eh.Ancora, module_id: str = "70") -> dict[str, list[tuple[str, str]]]:
    return {eh.nome_do_endpoint(uniq): [(module_id, ancora.declarado)]}


# ---------------------------------------------------------------------------
# 1. A CONTA — `distribuir_ancoras` é pura
# ---------------------------------------------------------------------------


def test_quem_ja_tem_ancora_fica_com_ela() -> None:
    """B chegou primeiro com a âncora 0; A, menor, chega depois e ganha outra."""
    postas = eh.distribuir_ancoras([_A, _B], _QUATRO, ja_postas={_B: _QUATRO[0]})
    assert postas[_B] == _QUATRO[0]
    assert postas[_A] != _QUATRO[0]


def test_o_servidor_semeia_quem_o_processo_esqueceu() -> None:
    """O restart: a memória nasce vazia, e o nó de pé diz qual era a âncora."""
    de_pe = {**_no(_A, _QUATRO[2], "71"), **_no(_B, _QUATRO[0], "72")}
    postas = eh.distribuir_ancoras([_A, _B], _QUATRO, de_pe)
    assert postas == {_A: _QUATRO[2], _B: _QUATRO[0]}


def test_o_no_que_declara_aparelho_que_saiu_nao_e_adotado() -> None:
    sumida = _ancora(9)
    postas = eh.distribuir_ancoras([_A], _QUATRO, _no(_A, sumida))
    assert postas[_A] in _QUATRO


def test_dois_nos_de_pe_com_a_mesma_ancora_se_separam() -> None:
    """O estado que o defeito deixou no servidor não sobrevive à distribuição."""
    de_pe = {**_no(_A, _QUATRO[0], "71"), **_no(_B, _QUATRO[0], "72")}
    postas = eh.distribuir_ancoras([_A, _B], _QUATRO, de_pe)
    assert postas[_A].syspath != postas[_B].syspath


def test_a_ancora_lembrada_que_saiu_do_barramento_e_trocada() -> None:
    postas = eh.distribuir_ancoras([_A], _QUATRO[1:], ja_postas={_A: _QUATRO[0]})
    assert postas[_A] == _QUATRO[1]


def test_a_memoria_vence_o_servidor_quando_discordam() -> None:
    """O nó deste processo está vivo; o do servidor é resto de outro."""
    de_pe = _no(_A, _QUATRO[0])
    postas = eh.distribuir_ancoras([_A, _B], _QUATRO, de_pe, ja_postas={_B: _QUATRO[0]})
    assert postas[_B] == _QUATRO[0]
    assert postas[_A] != _QUATRO[0]


def test_faltando_ancora_ninguem_recebe_a_de_outro() -> None:
    postas = eh.distribuir_ancoras([_A, _B, _C], _QUATRO[:2], ja_postas={_C: _QUATRO[0]})
    assert len(postas) == 2
    assert len({a.syspath for a in postas.values()}) == 2


@pytest.mark.parametrize("chegada", list(itertools.permutations([_A, _B, _C, _D])))
def test_nenhuma_ordem_de_chegada_repete_ancora(chegada: tuple[str, ...]) -> None:
    """Os quatro chegam um por um, em cada uma das 24 ordens, lembrando o de antes.

    MORDIDA: distribuir sem ``ja_postas`` (a ordenação pura de antes) reprova
    em 23 das 24 ordens.
    """
    lembradas: dict[str, eh.Ancora] = {}
    for n in range(1, len(chegada) + 1):
        presentes = list(chegada[:n])
        postas = eh.distribuir_ancoras(presentes, _QUATRO, ja_postas=lembradas)
        # quem já estava na mesa não troca de âncora
        assert all(postas[u] == a for u, a in lembradas.items()), (presentes, postas)
        lembradas = dict(postas)
    assert len({a.syspath for a in lembradas.values()}) == 4


# ---------------------------------------------------------------------------
# 2. A FIAÇÃO — o subsystem, o endpoint de verdade e um servidor de mentira
# ---------------------------------------------------------------------------


class _Servidor:
    """Um servidor de som de mentira, na forma das respostas do `pipewire-pulse`.

    Guarda os módulos que carregou com o `sysfs.path` declarado — é o que o
    jogo lê. Todo sink responde `RUNNING`: é o pior caso, o do leitor do
    monitor segurando o nó. O jogo é um sink-input, aberto pela régua em
    `jogo_em`.
    """

    def __init__(self) -> None:
        #: module_id -> (sink_name, sysfs.path)
        self.modulos: dict[str, tuple[str, str]] = {}
        self.cargas: list[str] = []
        self.quedas: list[str] = []
        self.jogo_em: set[str] = set()
        self._proximo = 500

    def por(self, uniq: str, ancora: eh.Ancora) -> str:
        """Um nó que um processo ANTERIOR deixou de pé."""
        self._proximo += 1
        self.modulos[str(self._proximo)] = (eh.nome_do_endpoint(uniq), ancora.declarado)
        return str(self._proximo)

    def caminho_de(self, uniq: str) -> list[str]:
        nome = eh.nome_do_endpoint(uniq)
        return [c for n, c in self.modulos.values() if n == nome]

    def __call__(self, argv: list[str]) -> str | None:
        if argv[:4] == ["pactl", "list", "short", "modules"]:
            return "\n".join(
                f"{mid}\tmodule-null-sink\tsink_name={nome} format=float32le "
                f'sink_properties="device.bus=usb sysfs.path={caminho} '
                f'priority.session=0"\t'
                for mid, (nome, caminho) in self.modulos.items()
            )
        if argv[:2] == ["pactl", "load-module"]:
            nome = next(a.split("=", 1)[1] for a in argv if a.startswith("sink_name="))
            props = next(a for a in argv if a.startswith("sink_properties="))
            caminho = next(
                p.split("=", 1)[1] for p in props.split() if p.startswith("sysfs.path=")
            )
            self._proximo += 1
            self.modulos[str(self._proximo)] = (nome, caminho)
            self.cargas.append(nome)
            return f"{self._proximo}\n"
        if argv[:2] == ["pactl", "unload-module"]:
            self.modulos.pop(argv[2], None)
            self.quedas.append(argv[2])
            return ""
        if argv[:4] == ["pactl", "list", "short", "sinks"]:
            return "\n".join(
                f"{mid}\t{nome}\tPipeWire\tfloat32le 4ch 48000Hz\tRUNNING"
                for mid, (nome, _c) in self.modulos.items()
            )
        if argv[:4] == ["pactl", "list", "short", "sink-inputs"]:
            return "\n".join(
                f"9{mid}\t{mid}\t12\tprotocol-native.c\tfloat32le 4ch 48000Hz"
                for mid, (nome, _c) in self.modulos.items()
                if nome in self.jogo_em
            )
        return None


class _PonteDeMentira:
    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.arranjo = kw.get("arranjo")
        self.desceu = False
        self.motivo = ""
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        return True

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        return True

    def esta_de_pe(self) -> bool:
        return not self.desceu


@dataclass
class _Controle:
    uniq: str
    caminho: str = "/dev/hidraw9"
    transporte: str = "bluetooth"


@dataclass
class _Mesa:
    sub: Any
    servidor: _Servidor
    ancoras: list[eh.Ancora]

    def casar(self, *uniqs: str) -> None:
        self.sub._casar_as_pontes([_Controle(u) for u in uniqs])


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> _Mesa:
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    _PonteDeMentira.criadas = []
    servidor = _Servidor()
    ancoras = list(_QUATRO)
    monkeypatch.setattr(eh, "rodar_pactl", servidor)
    monkeypatch.setattr(af, "rodar_pactl", servidor)
    monkeypatch.setattr(eh, "ancoras", lambda *a, **k: list(ancoras))
    monkeypatch.setattr(
        af, "fonte_do_monitor_do_no", lambda no, **kw: ((lambda _n: b""), f"gravador:{no}", "")
    )
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())

    class _Ger:
        def reconciliar(self, *_a: Any, **_k: Any) -> None:
            return None

        def dormir(self, _s: float) -> bool:
            return False

        def parar(self) -> None:
            return None

    sub = mod.AltoFalanteSubsystem(gerenciador=_Ger(), fonte_de_controles=list)
    return _Mesa(sub=sub, servidor=servidor, ancoras=ancoras)


def test_o_controle_que_chega_depois_com_uniq_menor_nao_herda_a_ancora(mesa: _Mesa) -> None:
    """O caso do auditor, no servidor: dois nós, dois `sysfs.path`.

    E o nó de B não se mexe: quem já estava na mesa, talvez com o jogo aberto
    no nó, não paga pela chegada do outro.

    MORDIDA: voltar a ``distribuir_ancoras(list(vivos), ancoras())`` em
    ``_casar_as_pontes``. A ordenação dá a âncora 0 de B a A, e o nó de B é
    derrubado e recarregado noutra âncora.
    """
    mesa.casar(_B)
    de_b = mesa.servidor.caminho_de(_B)
    mesa.casar(_A, _B)
    assert len(mesa.servidor.modulos) == 2
    caminhos = [c for _n, c in mesa.servidor.modulos.values()]
    assert len(set(caminhos)) == 2, f"dois nós com o mesmo ContainerId: {caminhos}"
    assert mesa.servidor.caminho_de(_B) == de_b, "o nó de quem já estava trocou de âncora"
    assert mesa.servidor.quedas == []


def test_a_queda_e_a_volta_em_outra_ordem_nao_repete(mesa: _Mesa) -> None:
    """O adaptador cai, leva os dois, e eles voltam na ordem inversa."""
    mesa.casar(_A, _B)
    mesa.casar()
    assert mesa.servidor.modulos == {}
    mesa.casar(_B)
    de_b = mesa.servidor.caminho_de(_B)
    quedas = len(mesa.servidor.quedas)
    mesa.casar(_A, _B)
    caminhos = [c for _n, c in mesa.servidor.modulos.values()]
    assert len(caminhos) == 2
    assert len(set(caminhos)) == 2, caminhos
    assert mesa.servidor.caminho_de(_B) == de_b
    assert len(mesa.servidor.quedas) == quedas, "a volta de A derrubou o nó de B"


def test_o_restart_com_os_nos_de_pe_nao_recarrega_nada(mesa: _Mesa) -> None:
    """O daemon novo nasce sem memória; o servidor ainda tem os nós do anterior.

    Recarregar derrubaria um nó vivo — com o jogo talvez aberto nele — para
    subir outro, e com a âncora trocada o device KS do prefixo deixaria de
    casar.

    MORDIDA: a distribuição sem ``de_pe`` dá A→0 e B→1 pela ordem, e os dois
    nós são derrubados e recarregados.
    """
    mesa.servidor.por(_A, _QUATRO[2])
    mesa.servidor.por(_B, _QUATRO[0])
    mesa.casar(_A, _B)
    assert mesa.servidor.cargas == [], "recarregou nó que estava de pé"
    assert mesa.servidor.quedas == []
    assert mesa.servidor.caminho_de(_A) == [_QUATRO[2].declarado]
    assert mesa.servidor.caminho_de(_B) == [_QUATRO[0].declarado]


def test_os_nos_que_o_defeito_deixou_repetidos_se_separam(mesa: _Mesa) -> None:
    """Quem atualiza o produto herda o servidor com os dois nós na âncora 0."""
    mesa.servidor.por(_A, _QUATRO[0])
    mesa.servidor.por(_B, _QUATRO[0])
    mesa.casar(_A, _B)
    assert mesa.servidor.caminho_de(_A) == [_QUATRO[0].declarado]
    assert mesa.servidor.caminho_de(_B) not in ([], [_QUATRO[0].declarado])


def test_a_ancora_cujo_aparelho_saiu_e_trocada_fora_do_jogo(mesa: _Mesa) -> None:
    mesa.casar(_A)
    antes = mesa.servidor.caminho_de(_A)
    mesa.ancoras.remove(next(a for a in _QUATRO if a.declarado == antes[0]))
    mesa.casar(_A)
    depois = mesa.servidor.caminho_de(_A)
    assert len(depois) == 1
    assert depois != antes


def test_com_o_jogo_tocando_a_ancora_nao_troca(mesa: _Mesa) -> None:
    """Trocar derrubaria o nó com o jogo tocando nele — a partida perde a háptica."""
    mesa.casar(_A)
    antes = mesa.servidor.caminho_de(_A)
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_A))
    mesa.casar(_A)  # a ponte vira a da háptica
    mesa.ancoras.remove(next(a for a in _QUATRO if a.declarado == antes[0]))
    mesa.casar(_A)
    assert mesa.servidor.caminho_de(_A) == antes


# ---------------------------------------------------------------------------
# 3. O MODO — quem toca é um sink-input
# ---------------------------------------------------------------------------


def test_o_leitor_do_monitor_nao_conta_como_jogo() -> None:
    """Sink em RUNNING sem sink-input é o NOSSO gravador segurando o nó.

    MORDIDA: devolver ``sink_esta_tocando`` ao estado ``RUNNING`` do sink.
    """
    servidor = _Servidor()
    servidor.por(_A, _QUATRO[0])
    assert af.sink_esta_tocando(eh.nome_do_endpoint(_A), servidor) is False
    servidor.jogo_em.add(eh.nome_do_endpoint(_A))
    assert af.sink_esta_tocando(eh.nome_do_endpoint(_A), servidor) is True


def test_o_stream_de_outro_sink_nao_e_deste() -> None:
    servidor = _Servidor()
    servidor.por(_A, _QUATRO[0])
    servidor.por(_B, _QUATRO[1])
    servidor.jogo_em.add(eh.nome_do_endpoint(_B))
    assert af.sink_esta_tocando(eh.nome_do_endpoint(_A), servidor) is False


def test_o_jogo_que_fecha_devolve_a_ponte_ao_som(mesa: _Mesa) -> None:
    """O defeito inteiro: fechado o jogo, o alto-falante do controle volta.

    O servidor de mentira responde `RUNNING` para todo sink, como o PipeWire
    com a ponte lendo o monitor do endpoint.

    MORDIDA: com o ``RUNNING`` decidindo, a última ponte continua a da háptica.
    """
    mesa.casar(_A)
    assert _PonteDeMentira.criadas[-1].arranjo is None
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_A))
    mesa.casar(_A)
    assert _PonteDeMentira.criadas[-1].arranjo is af.ARRANJO_HAPTICA_032
    mesa.servidor.jogo_em.clear()
    mesa.casar(_A)
    assert _PonteDeMentira.criadas[-1].arranjo is None, "a ponte ficou presa na háptica"
    assert len(_PonteDeMentira.criadas) == 3
