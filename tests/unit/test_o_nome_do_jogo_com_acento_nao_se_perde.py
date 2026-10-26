"""O nome do jogo com ™, ® ou acento não se perde no pactl, e o ouvido do tato fica no jogo.

O-NOME-DO-JOGO-COM-ACENTO-NAO-SE-PERDE-NO-PACTL-01 (24/10/2026). Na bancada do Sackboy™ o
`pactl --format=json` entregou «(null)» no `node.name` do jogo, o grafo do PipeWire deu o nome
inteiro, e o ouvido calava o gravador a cada 10 s. Aqui o JSON de mentira do `pactl` tem a forma
medida (o texto perdido, o serial e o id inteiros) e o grafo de mentira tem o nome em UTF-8.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as afb
from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import haptica_do_cabo as hc
from hefesto_dualsense4unix.integrations import porta_do_som as ps
from hefesto_dualsense4unix.integrations import quem_ouve_o_microfone as qom
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj

NOMES = (
    "Sackboy™: A Big Adventure",
    "Ratchet & Clank® Rift Apart",
    "Pokémon Lendas: Arceus",
    "ゼルダの伝説",
)

PID_DO_JOGO = 66255
FLUXOS_DO_JOGO = ((171, 719, 78), (179, 739, 78), (184, 794, 78))
ID_DO_OUVIDO = 900


def _sink_input(ident: int, serial: int, sink: int, *, nome: str, pid: int) -> dict[str, Any]:
    """Um `sink-input` do `pactl --format=json`, com o texto fora do ASCII já perdido."""
    perdido = nome if nome.isascii() else ps.NULO_DO_PACTL
    return {
        "index": serial, "sink": sink, "client": 718, "corked": False, "mute": False,
        "properties": {
            "application.name": perdido,
            "node.name": perdido,
            "media.name": f"audio stream #{serial}",
            "application.process.id": str(pid),
            "application.process.binary": "wine64-preloader",
            "object.id": str(ident),
            "object.serial": str(serial),
        },
    }


def _pactl_do_jogo(nome: str, *, extra: tuple[dict[str, Any], ...] = ()) -> str:
    fluxos = [_sink_input(i, s, k, nome=nome, pid=PID_DO_JOGO) for i, s, k in FLUXOS_DO_JOGO]
    return json.dumps([*fluxos, *extra])


def _no(ident: int, serial: int, nome: str, classe: str = "Stream/Output/Audio") -> dict[str, Any]:
    return {"id": ident, "type": "PipeWire:Interface:Node",
            "info": {"props": {"node.name": nome, "object.serial": serial,
                               "media.class": classe}}}


def _link(saida: int, entrada: int) -> dict[str, Any]:
    return {"id": 5000 + saida, "type": "PipeWire:Interface:Link",
            "info": {"output-node-id": saida, "input-node-id": entrada, "props": {}}}


def _grafo(nome_do_jogo: str, *, origem_do_ouvido: int | None = 171) -> str:
    """O grafo do PipeWire: os fluxos do jogo com o nome inteiro, o microfone e o ouvido."""
    objetos: list[dict[str, Any]] = [
        _no(i, s, nome_do_jogo) for i, s, _k in FLUXOS_DO_JOGO
    ]
    objetos.append(_no(47, 77, "alsa_input.usb-Sony_DualSense-00.mic", "Audio/Source"))
    objetos.append(_no(ID_DO_OUVIDO, 2001, tj.ROTULO_DO_OUVIDO, "Stream/Input/Audio"))
    if origem_do_ouvido is not None:
        objetos.append(_link(origem_do_ouvido, ID_DO_OUVIDO))
    return json.dumps(objetos)


class _Gravador:
    def __init__(self) -> None:
        self.stdout = SimpleNamespace(read=lambda _n: b"")

    def poll(self) -> int | None:
        return None


class _Bancada:
    """O ouvido com o leitor de fluxos e a conferência do PRODUTO, sobre o som de mentira."""

    def __init__(self, nome: str, *, origem_do_ouvido: int | None = 171) -> None:
        self.pactl = _pactl_do_jogo(nome)
        self.grafo = _grafo(nome, origem_do_ouvido=origem_do_ouvido)
        self.abertos: list[list[str]] = []
        self.derrubados: list[Any] = []
        self.ouvido = tj.OuvidoDoJogo(
            lambda: True,
            achar_o_fluxo=self._achar,
            montar_argv=lambda f: ["pw-record", f"--target={f.serial}"],
            abrir=self._abrir,
            derrubar=lambda proc, **_k: self.derrubados.append(proc),
            conferir_o_alvo=lambda rotulo: afb.origem_do_gravador(
                rotulo, ler_o_grafo=lambda: self.grafo),
            relogio=lambda: 10.0,
        )

    def _achar(self) -> tj.FluxoDoJogo | None:
        fluxos = ps.ler_fluxos("sink-inputs", lambda _argv: self.pactl)
        return tj.fluxo_do_jogo(fluxos or (), {PID_DO_JOGO})

    def _abrir(self, argv: list[str]) -> _Gravador:
        self.abertos.append(argv)
        return _Gravador()

    def voltas(self, n: int) -> None:
        for _ in range(n):
            self.ouvido.uma_volta()


@pytest.mark.parametrize("nome", NOMES)
def test_o_ouvido_liga_uma_vez_e_fica_no_jogo_de_nome_perdido(nome: str) -> None:
    """**A régua do defeito**: 51 voltas de liga-cala em 8 min viram uma ligação só."""
    bancada = _Bancada(nome)
    bancada.voltas(12)
    assert bancada.abertos == [["pw-record", "--target=719"]], bancada.abertos
    assert bancada.ouvido.contadores["alvo_errado"] == 0, (
        "o ouvido calou o gravador que se ligou ao fluxo certo do jogo"
    )
    assert bancada.derrubados == []
    assert bancada.ouvido._conferido


@pytest.mark.parametrize("nome", NOMES)
def test_o_alvo_errado_de_verdade_continua_calando(nome: str) -> None:
    """Outro fluxo do MESMO jogo, com o MESMO nome: o serial diz que não é o pedido."""
    bancada = _Bancada(nome, origem_do_ouvido=179)
    bancada.voltas(2)
    assert bancada.ouvido.contadores["alvo_errado"] == 1
    assert len(bancada.derrubados) == 1


def test_o_gravador_no_microfone_cala() -> None:
    bancada = _Bancada(NOMES[0], origem_do_ouvido=47)
    bancada.voltas(2)
    assert bancada.ouvido.contadores["alvo_errado"] == 1
    assert len(bancada.derrubados) == 1


def test_sem_ligacao_no_grafo_e_nao_sei_e_nao_derruba() -> None:
    bancada = _Bancada(NOMES[0], origem_do_ouvido=None)
    bancada.voltas(5)
    assert bancada.derrubados == [] and bancada.ouvido.contadores["alvo_errado"] == 0
    assert not bancada.ouvido._conferido


def _fluxo(nome: str = "", *, serial: int | None = 719, ident: int | None = 171,
           perdido: bool = True) -> tj.FluxoDoJogo:
    return tj.FluxoDoJogo(78, serial, nome, PID_DO_JOGO, ident=ident, nome_perdido=perdido)


def test_o_serial_decide_antes_do_nome() -> None:
    certo = afb.OrigemDoGravador(171, 719, "Sackboy™: A Big Adventure")
    assert tj.e_o_fluxo_pedido(certo, _fluxo()) is True
    assert tj.e_o_fluxo_pedido(afb.OrigemDoGravador(179, 739, certo.nome), _fluxo()) is False


def test_sem_serial_o_id_do_grafo_decide() -> None:
    assert tj.e_o_fluxo_pedido(afb.OrigemDoGravador(171, None, ""), _fluxo()) is True
    assert tj.e_o_fluxo_pedido(afb.OrigemDoGravador(179, None, ""), _fluxo()) is False


def test_o_nome_perdido_nunca_decide() -> None:
    """Sem identidade nos dois lados e com o nome do fluxo perdido, a resposta é «não sei»."""
    sem_identidade = _fluxo(serial=None, ident=None)
    assert tj.e_o_fluxo_pedido("Sackboy™: A Big Adventure", sem_identidade) is None
    assert tj.e_o_fluxo_pedido(None, _fluxo()) is None


def test_o_nome_inteiro_decide_quando_e_o_que_se_tem() -> None:
    ascii_ = _fluxo("jogo", serial=None, ident=None, perdido=False)
    assert tj.e_o_fluxo_pedido("jogo", ascii_) is True
    assert tj.e_o_fluxo_pedido("microfone", ascii_) is False


@pytest.mark.parametrize("nome", NOMES)
def test_a_porta_anota_o_texto_perdido_e_guarda_a_identidade(nome: str) -> None:
    fluxos = ps.ler_fluxos("sink-inputs", lambda _argv: _pactl_do_jogo(nome))
    assert fluxos is not None and len(fluxos) == 3
    primeiro = fluxos[0]
    assert primeiro.propriedades["node.name"] == ""
    assert primeiro.perdeu("node.name") and primeiro.perdeu("application.name")
    assert not primeiro.perdeu("object.serial") and not primeiro.perdeu("ausente")
    assert primeiro.propriedades["object.serial"] == "719"
    assert primeiro.propriedades["object.id"] == "171"


def test_o_texto_ascii_nao_se_marca_perdido() -> None:
    fluxos = ps.fluxos_do_texto(_pactl_do_jogo("Celeste"))
    assert fluxos and not fluxos[0].perdidos and fluxos[0].propriedades["node.name"] == "Celeste"


def _sinks(*nomes: str) -> str:
    return json.dumps([
        {"index": 70 + i, "name": n if n.isascii() else ps.NULO_DO_PACTL,
         "description": "x", "volume": {"front-left": {"value": 32768,
                                                       "value_percent": "50%", "db": "-18"}},
         "properties": {"node.name": n if n.isascii() else ps.NULO_DO_PACTL,
                        "sysfs.path": f"/devices/x{i}"}}
        for i, n in enumerate(nomes)
    ])


def test_o_no_de_nome_perdido_nao_casa_com_o_pedido_vazio() -> None:
    def ler(_argv: list[str]) -> str | None:
        return _sinks("Saída Estéreo", "hefesto_som_x")

    nos = ps.ler_nos("sinks", ler)
    assert nos is not None and nos[0].nome == "" and nos[0].perdeu("node.name")
    assert ps.volumes_do_no("sinks", "", ler) is None, (
        "um nó cujo nome o pactl perdeu respondeu por um pedido sem nome"
    )
    assert ps.volumes_do_no("sinks", "hefesto_som_x", ler) == [50]
    assert set(ps.sysfs_por_no("sinks", ler) or {}) == {"hefesto_som_x"}


@pytest.mark.parametrize("nome", NOMES)
def test_o_fluxo_do_jogo_de_nome_perdido_e_achado_e_o_nosso_fica_fora(nome: str) -> None:
    nosso = _sink_input(300, 366, 76, nome="hefesto-tato-estalo-x", pid=PID_DO_JOGO)
    fluxos = ps.fluxos_do_texto(_pactl_do_jogo(nome, extra=(nosso,)))
    achado = tj.fluxo_do_jogo(reversed(fluxos), {PID_DO_JOGO})
    assert achado is not None and achado.serial in (719, 739, 794)
    assert achado.nome == "" and achado.nome_perdido and achado.ident is not None
    assert tj.fluxo_do_jogo(fluxos[3:], {PID_DO_JOGO}) is None, "o nosso nó virou o jogo"


@pytest.mark.parametrize("nome", NOMES)
def test_o_estalo_cala_quando_o_jogo_de_nome_perdido_toca_no_no(nome: str) -> None:
    nos = (ps.NoDeSom(78, "hefesto_som_x"),)
    fluxos = ps.fluxos_do_texto(_pactl_do_jogo(nome))
    rotulo = tj.rotulo_do_estalo("hefesto_som_x")
    assert tj.outro_fluxo_no_no(nos, fluxos, "hefesto_som_x", rotulo) is True


@pytest.mark.parametrize("nome", NOMES)
def test_o_endpoint_ve_o_jogo_de_nome_perdido_como_outro(nome: str) -> None:
    tocador = _sink_input(300, 366, 78, nome=f"{eh.MARCA_DO_TOCADOR}x", pid=1)
    tocador["client"] = 55
    texto = _pactl_do_jogo(nome, extra=(tocador,))

    def runner(argv: list[str]) -> str | None:
        if argv[-1] == "sinks":
            return "78\thefesto_haptica_x\tPipeWire\ts16le 4ch 48000Hz\tRUNNING\n"
        return texto

    resposta = eh.fluxos_nos_endpoints(["hefesto_haptica_x"], runner)
    assert resposta == (frozenset({"55"}), frozenset({"hefesto_haptica_x"}))


@pytest.mark.parametrize("nome", NOMES)
def test_o_laco_do_cabo_se_acha_entre_fluxos_de_nome_perdido(nome: str) -> None:
    laco = _sink_input(300, 366, 76, nome=f"output.{ks.MARCA_DO_LACO_DO_CABO}x", pid=1)
    texto = _pactl_do_jogo(nome, extra=(laco,))
    assert ks.indice_do_fluxo(f"{ks.MARCA_DO_LACO_DO_CABO}x", lambda _argv: texto) == "366"


@pytest.mark.parametrize("nome", NOMES)
def test_o_jogo_de_nome_perdido_que_ouve_o_microfone_nao_e_nosso(nome: str) -> None:
    fluxo = _sink_input(171, 719, 47, nome=nome, pid=PID_DO_JOGO)
    fluxo["source"] = fluxo.pop("sink")
    stream = qom.streams_de_captura(json.dumps([fluxo]))[0]
    assert not qom.e_stream_do_hefesto(stream, raiz_proc="/proc-vazio-de-mentira")


def _pw_dump(monkeypatch: pytest.MonkeyPatch, saida: str) -> None:
    """O grafo pelo dublê do DONO (``retrato_do_som.ler_o_pw_dump``), o único leitor."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.retrato_do_som.ler_o_pw_dump", lambda: saida
    )


@pytest.mark.parametrize("nome", NOMES)
def test_a_conferencia_por_nome_da_casa_le_o_nome_inteiro_do_grafo(
    nome: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O laço do cabo e a ponte conferem contra um nó DESTA casa; o vizinho com ™ não atrapalha."""
    captura = hc.no_de_captura("x")
    objetos = json.loads(_grafo(nome, origem_do_ouvido=None))
    objetos += [_no(60, 600, "hefesto_haptica_x", "Audio/Sink"),
                _no(61, 601, captura, "Stream/Input/Audio"), _link(60, 61)]
    _pw_dump(monkeypatch, json.dumps(objetos))
    assert afb.conferir_o_alvo_do_gravador(captura) == "hefesto_haptica_x"
    origem = afb.origem_do_gravador(captura)
    assert origem == afb.OrigemDoGravador(60, 600, "hefesto_haptica_x")

    objetos[-1] = _link(171, 61)
    _pw_dump(monkeypatch, json.dumps(objetos))
    assert afb.conferir_o_alvo_do_gravador(captura) == nome, "o grafo perdeu o nome com ™"

    class _Lacos:
        def __init__(self) -> None:
            self.desligados: list[str] = []

        def desligar(self, chave: str) -> None:
            self.desligados.append(chave)

    lacos = _Lacos()
    cabo = hc.HapticaDoCabo(lacos)
    rota = hc.RotaDoCabo(captura="600", destino="76", origem="hefesto_haptica_x")
    assert cabo._conferir("x", rota) is False, "o laço ligado ao jogo não caiu"
    assert lacos.desligados == ["x"]


def test_o_grafo_traz_o_serial_e_o_id_da_origem() -> None:
    grafo = json.loads(_grafo(NOMES[3]))
    esperada = afb.OrigemDoGravador(171, 719, NOMES[3])
    assert afb.origem_no_grafo(grafo, tj.ROTULO_DO_OUVIDO) == esperada
    assert afb.origem_no_grafo(grafo, "outro-rotulo") is None
    assert afb.origem_no_grafo({"objeto": "solto"}, tj.ROTULO_DO_OUVIDO) is None
    ilegivel = afb.origem_do_gravador(tj.ROTULO_DO_OUVIDO, ler_o_grafo=lambda: "não é json")
    assert ilegivel is None


def test_o_ouvido_do_produto_pede_a_identidade_ao_grafo(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cura LIGADA: o ouvido sem dublê confere pela origem com serial, não pelo nome."""
    _pw_dump(monkeypatch, _grafo(NOMES[0]))
    origem = tj.conferir_o_alvo_do_ouvido(tj.ROTULO_DO_OUVIDO)
    assert origem == afb.OrigemDoGravador(171, 719, NOMES[0])
    assert tj.OuvidoDoJogo(lambda: False)._conferir_o_alvo is tj.conferir_o_alvo_do_ouvido


MESA = (
    ("P1", "APARELHOGHJKMN", "cabo"),
    ("P2", "APARELHOPQRSTU", "radio"),
    ("P3", "APARELHOVWXYZG", "cabo"),
    ("P4", "APARELHOHJKMNP", "radio"),
)
ASSENTOS = tuple(range(len(MESA)))


def _som(marca: str) -> str:
    return f"{afb.PREFIXO_SINK_DO_SOM}{marca}"


def _sinks_da_mesa() -> str:
    return json.dumps([
        {"index": 70 + i, "name": _som(marca), "description": f"Som {assento}",
         "properties": {"node.name": _som(marca)}}
        for i, (assento, marca, _t) in enumerate(MESA)
    ])


def _jogo_no_assento(nome: str, assento: int) -> str:
    fluxos = [_sink_input(i, s, 70 + assento, nome=nome, pid=PID_DO_JOGO)
              for i, s, _k in FLUXOS_DO_JOGO]
    return json.dumps(fluxos)


@pytest.mark.parametrize("assento", ASSENTOS)
@pytest.mark.parametrize("nome", NOMES)
def test_a_mesa_mista_o_estalo_cala_so_no_no_onde_o_jogo_toca(nome: str, assento: int) -> None:
    nos = ps.nos_do_texto(_sinks_da_mesa())
    fluxos = ps.fluxos_do_texto(_jogo_no_assento(nome, assento))
    vistos = [
        tj.outro_fluxo_no_no(nos, fluxos, _som(marca), tj.rotulo_do_estalo(_som(marca)))
        for _a, marca, _t in MESA
    ]
    assert vistos == [i == assento for i in ASSENTOS], (MESA[assento], vistos)


@pytest.mark.parametrize("assento", ASSENTOS)
@pytest.mark.parametrize("nome", NOMES)
def test_a_mesa_mista_o_endpoint_ve_o_jogo_so_no_do_assento(nome: str, assento: int) -> None:
    endpoints = [eh.nome_da_marca(marca) for _a, marca, _t in MESA]
    curtos = "".join(f"{70 + i}\t{n}\tPipeWire\ts16le 4ch 48000Hz\tRUNNING\n"
                     for i, n in enumerate(endpoints))
    texto = _jogo_no_assento(nome, assento)

    def runner(argv: list[str]) -> str | None:
        return curtos if argv[-1] == "sinks" else texto

    resposta = eh.fluxos_nos_endpoints(endpoints, runner)
    assert resposta == (frozenset(), frozenset({endpoints[assento]}))


@pytest.mark.parametrize("assento", ASSENTOS)
@pytest.mark.parametrize("nome", NOMES)
def test_a_mesa_mista_cada_gravador_confere_o_proprio_no_com_o_jogo_no_grafo(
    nome: str, assento: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ponte do rádio (P2, P4), o laço do cabo (P1, P3) e o ouvido, num grafo só."""
    objetos = json.loads(_grafo(nome, origem_do_ouvido=171))
    rotulos: list[tuple[str, str]] = []
    for i, (_a, marca, transporte) in enumerate(MESA):
        no = _som(marca) if transporte == "radio" else eh.nome_da_marca(marca)
        rotulo = (f"hefesto-ponte-{marca}-som" if transporte == "radio"
                  else hc.no_de_captura(marca))
        objetos += [_no(60 + i, 600 + i, no, "Audio/Sink"),
                    _no(80 + i, 800 + i, rotulo, "Stream/Input/Audio"), _link(60 + i, 80 + i)]
        rotulos.append((rotulo, no))
    objetos += [_link(i, 60 + assento) for i, _s, _k in FLUXOS_DO_JOGO]
    _pw_dump(monkeypatch, json.dumps(objetos))
    for rotulo, no in rotulos:
        assert afb.conferir_o_alvo_do_gravador(rotulo) == no, rotulo
    origem = tj.conferir_o_alvo_do_ouvido(tj.ROTULO_DO_OUVIDO)
    assert origem == afb.OrigemDoGravador(171, 719, nome)
    fluxo = tj.FluxoDoJogo(719, 719, "", PID_DO_JOGO, ident=171, nome_perdido=True)
    assert tj.e_o_fluxo_pedido(origem, fluxo) is True


@pytest.mark.parametrize("assento", ASSENTOS)
def test_a_mesa_mista_o_ouvido_fica_no_jogo_de_qualquer_assento(assento: int) -> None:
    bancada = _Bancada(NOMES[0])
    bancada.pactl = _jogo_no_assento(NOMES[0], assento)
    bancada.voltas(12)
    assert bancada.abertos == [["pw-record", "--target=719"]]
    assert bancada.ouvido.contadores["alvo_errado"] == 0 and bancada.derrubados == []
