"""O nome que o pactl perde vem do grafo, num dono só, e nome vazio nunca casa com vazio.

O-NOME-QUE-O-PACTL-PERDE-VEM-DO-GRAFO-01 (24/10/2026). O JSON de mentira do `pactl` tem a forma
medida na bancada do Sackboy™ (`r1-cabo-2410b/si-C.json`): o índice é o serial, o `object.id` e o
`object.serial` chegam inteiros, e `application.name`, `node.name` e `module-stream-restore.id`
chegam «(null)». O grafo de mentira (`pw-dump`) tem o UTF-8 inteiro e o serial como número.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as afb
from hefesto_dualsense4unix.integrations import porta_do_som as ps
from hefesto_dualsense4unix.integrations import quem_ouve_o_microfone as qom
from hefesto_dualsense4unix.integrations import retrato_do_som as rs
from hefesto_dualsense4unix.integrations import transiente_do_jogo as tj
from tests.unit import pactl_json_de_mentira as pj

NULO = ps.NULO_DO_PACTL

NOMES = (
    "Sackboy™: A Big Adventure",
    "Ratchet & Clank® Rift Apart",
    "Pokémon Lendas: Arceus",
    "ゼルダの伝説",
    "Café 🎮 Party",
)

#: quatro controles, cabo e rádio: (id do grafo, serial, alvo, nome do jogo)
MESA_MISTA = (
    (171, 719, 76, NOMES[0]),
    (179, 739, 77, NOMES[1]),
    (184, 794, 78, NOMES[2]),
    (207, 846, 79, NOMES[3]),
)


def _perdido(texto: str) -> str:
    return texto if texto.isascii() else NULO


def _fluxo(ident: int, serial: int, alvo: int, nome: str, *, tipo: str = "sink") -> dict[str, Any]:
    """Um fluxo do `pactl --format=json`, com o texto fora do ASCII já perdido."""
    return {
        "index": serial, tipo: alvo, "client": 718, "corked": False, "mute": False,
        "properties": {
            "application.name": _perdido(nome),
            "node.name": _perdido(nome),
            "media.name": f"audio stream #{serial}",
            "module-stream-restore.id": _perdido(f"sink-input-by-application-name:{nome}"),
            "object.id": str(ident),
            "object.serial": str(serial),
        },
    }


def _no_do_grafo(ident: int, serial: int, nome: str, **props: str) -> dict[str, Any]:
    return {"id": ident, "type": "PipeWire:Interface:Node",
            "info": {"props": {"node.name": nome, "application.name": nome,
                               "object.serial": serial, **props}}}


def _grafo_de(*nos: dict[str, Any]) -> str:
    return json.dumps(list(nos), ensure_ascii=False)


class _Grafo:
    """O `pw-dump` de mentira, que conta quantas vezes foi lido."""

    def __init__(self, texto: str | None) -> None:
        self.texto = texto
        self.lidas = 0

    def __call__(self) -> str | None:
        self.lidas += 1
        return self.texto


def _leitor(respostas: dict[str, str]) -> Callable[[list[str]], str | None]:
    def ler(argv: list[str]) -> str | None:
        return respostas.get(" ".join(argv[1:]))
    return ler


def _mesa_mista() -> tuple[str, _Grafo]:
    pactl = json.dumps([_fluxo(i, s, a, n) for i, s, a, n in MESA_MISTA])
    grafo = _Grafo(_grafo_de(*(_no_do_grafo(i, s, n) for i, s, _a, n in MESA_MISTA)))
    return pactl, grafo


@pytest.mark.parametrize("nome", NOMES)
def test_ler_fluxos_devolve_o_nome_inteiro_pelo_grafo(nome: str) -> None:
    pactl = json.dumps([_fluxo(171, 719, 76, nome)])
    grafo = _Grafo(_grafo_de(_no_do_grafo(171, 719, nome)))
    fluxos = ps.ler_fluxos("sink-inputs", _leitor({"--format=json list sink-inputs": pactl}),
                           grafo)
    assert fluxos is not None
    (fluxo,) = fluxos
    assert fluxo.propriedades["node.name"] == nome
    assert fluxo.propriedades["application.name"] == nome
    assert fluxo.perdidos == frozenset({"module-stream-restore.id"}), (
        "o que o grafo não tem segue perdido, e só ele")
    assert grafo.lidas == 1


def test_a_mesa_mista_le_o_grafo_uma_vez_e_cada_fluxo_ganha_o_proprio_nome() -> None:
    """Quatro controles, cabo e rádio, quatro jogos de nome perdido: um `pw-dump` só."""
    pactl, grafo = _mesa_mista()
    fluxos = ps.ler_fluxos("sink-inputs", _leitor({"--format=json list sink-inputs": pactl}),
                           grafo)
    assert fluxos is not None
    assert [(f.alvo, f.propriedades["node.name"]) for f in fluxos] == [
        (str(a), n) for _i, _s, a, n in MESA_MISTA]
    assert grafo.lidas == 1


@pytest.mark.parametrize("grafo", [None, "", "pw-dump: não conectou"])
def test_sem_o_grafo_o_nome_fica_vazio_e_perdido(grafo: str | None) -> None:
    pactl = json.dumps([_fluxo(171, 719, 76, NOMES[0])])
    fluxos = ps.ler_fluxos("sink-inputs", _leitor({"--format=json list sink-inputs": pactl}),
                           _Grafo(grafo))
    assert fluxos is not None
    (fluxo,) = fluxos
    assert fluxo.propriedades["node.name"] == ""
    assert fluxo.perdeu("node.name") and fluxo.perdeu("application.name")


def test_ler_nos_devolve_o_nome_e_a_descricao_inteiros() -> None:
    nome, descricao = "alsa_output.Café™", "Saída digital (HDMI) Estéreo"
    pactl = pj.texto(pj.no(312, NULO, descricao=NULO,
                           props={"node.name": NULO, "object.id": "55", "object.serial": "312",
                                  "device.description": NULO}))
    grafo = _Grafo(_grafo_de(_no_do_grafo(55, 312, nome, **{"node.description": descricao})))
    nos = ps.ler_nos("sinks", _leitor({"--format=json list sinks": pactl}), grafo)
    assert nos is not None
    (no,) = nos
    assert (no.nome, no.descricao, no.descricao_nula) == (nome, descricao, False)
    assert no.perdidos == frozenset({"device.description"})


@pytest.mark.parametrize("nome_da_saida", ["alsa_output.pci-0000_0b_00.4.iec958-stereo",
                                           "alsa_output.Fone do João™"])
def test_o_monitor_da_saida_nao_ganha_o_nome_nem_a_descricao_dela(nome_da_saida: str) -> None:
    """O monitor tem o serial da saída: do nó vêm as propriedades, e o nome e a descrição não.

    A forma medida em 24/10/2026 nesta máquina: o monitor 74 tem `object.serial` 74, o
    `node.name` da saída e `device.class=monitor`, e a descrição «(null)» (era «Monitor of …
    Estéreo digital»); o grafo só tem o nó da saída, com a descrição DO USUÁRIO.
    """
    descricao = "Starship/Matisse HD Audio Controller Estéreo digital (IEC958)"
    perfil = "Estéreo digital (IEC958)"
    props = {"node.name": _perdido(nome_da_saida), "object.id": "61", "object.serial": "74",
             "device.class": "monitor", "device.profile.description": NULO}
    monitor = pj.no(74, _perdido(f"{nome_da_saida}.monitor"), descricao=NULO, props=props)
    saida = pj.no(74, _perdido(nome_da_saida), descricao=NULO,
                  props={**props, "device.class": "sound"})
    grafo = _Grafo(_grafo_de(_no_do_grafo(61, 74, nome_da_saida, **{
        "node.description": descricao, "device.profile.description": perfil,
        "device.class": "sound"})))
    (no_monitor,) = ps.nos_do_texto(ps.completar_o_json(pj.texto(monitor), grafo) or "")
    assert no_monitor.nome == (nome_da_saida + ".monitor" if nome_da_saida.isascii() else ""), (
        "o nome do monitor é dele, e o perdido segue perdido")
    assert no_monitor.descricao != descricao and no_monitor.descricao_nula
    assert no_monitor.propriedades["device.profile.description"] == perfil
    (no_saida,) = ps.nos_do_texto(ps.completar_o_json(pj.texto(saida), grafo) or "")
    assert (no_saida.nome, no_saida.descricao) == (nome_da_saida, descricao)


def test_sem_nada_perdido_o_grafo_nao_e_lido() -> None:
    pactl = json.dumps([_fluxo(171, 719, 76, "Celeste")])
    grafo = _Grafo(_grafo_de())
    texto = ps.completar_o_json(pactl, grafo)
    assert texto is pactl, "o texto inteiro volta o mesmo, sem cópia"
    assert grafo.lidas == 0


def test_o_completar_e_idempotente_e_nao_pede_o_grafo_de_novo() -> None:
    pactl, grafo = _mesa_mista()
    uma = ps.completar_o_json(pactl, grafo)
    duas = ps.completar_o_json(uma, grafo)
    assert duas == uma
    assert grafo.lidas == 1, "o que o grafo não tem (o module-stream-restore.id) não o pede de novo"


def test_a_identidade_decide_e_o_nome_do_vizinho_nao_entra() -> None:
    """Serial que o grafo não tem não cai no nome; serial do grafo com outro nome inteiro desfaz."""
    sumiu = _fluxo(171, 719, 76, NOMES[0])
    outro = _fluxo(179, 739, 77, NOMES[1])
    grafo = _Grafo(_grafo_de(_no_do_grafo(900, 9000, NOMES[0]),
                             _no_do_grafo(179, 739, NOMES[1])))
    fluxos = ps.fluxos_do_texto(ps.completar_o_json(json.dumps([sumiu, outro]), grafo) or "")
    assert [f.propriedades["node.name"] for f in fluxos] == ["", NOMES[1]]

    inteiro = pj.texto(pj.no(5, "alsa_output.hdmi", descricao=NULO,
                             props={"object.serial": "5"}))
    trocado = _Grafo(_grafo_de(_no_do_grafo(1, 5, "alsa_output.outro",
                                            **{"node.description": "Outro"})))
    (no,) = ps.nos_do_texto(ps.completar_o_json(inteiro, trocado) or "")
    assert no.descricao_nula, "o serial casou, o nome inteiro não: não é o mesmo nó"


def test_nome_vazio_nunca_casa_com_o_no_sem_nome_do_grafo() -> None:
    """Sem identidade e com o nome perdido, nada no grafo é o mesmo nó."""
    sem_identidade = {"index": 4, "name": NULO, "description": NULO,
                      "properties": {"node.name": NULO}}
    grafo = _Grafo(json.dumps([
        {"id": 7, "type": "PipeWire:Interface:Node",
         "info": {"props": {"node.name": "", "node.description": "Vizinho"}}}]))
    (no,) = ps.nos_do_texto(ps.completar_o_json(json.dumps([sem_identidade]), grafo) or "")
    assert (no.nome, no.descricao) == ("", "")


def test_com_o_nome_inteiro_o_alvo_errado_de_verdade_ainda_cala_o_ouvido() -> None:
    """O nome que o grafo devolve não decide: dois fluxos do MESMO jogo, e o serial manda.

    Medido em 24/10/2026: um jogo do Proton abre dois fluxos com o mesmo `node.name`. O nome
    inteiro de volta não pode fazer o gravador ligado ao fluxo vizinho passar por certo.
    """
    nome = NOMES[0]
    fluxos_crus = [_fluxo(171, 719, 76, nome), _fluxo(179, 739, 76, nome)]
    for f in fluxos_crus:
        f["properties"]["application.process.id"] = "4242"
    fluxos_crus[1]["corked"] = True
    grafo = _Grafo(_grafo_de(_no_do_grafo(171, 719, nome), _no_do_grafo(179, 739, nome)))
    fluxos = ps.ler_fluxos("sink-inputs",
                           _leitor({"--format=json list sink-inputs": json.dumps(fluxos_crus)}),
                           grafo)
    assert fluxos is not None
    jogo = tj.fluxo_do_jogo(fluxos, [4242])
    assert jogo is not None
    assert (jogo.serial, jogo.nome, jogo.nome_perdido) == (719, nome, False)
    assert tj.e_o_fluxo_pedido(afb.OrigemDoGravador(179, 739, nome), jogo) is False
    assert tj.e_o_fluxo_pedido(afb.OrigemDoGravador(171, 719, nome), jogo) is True
    assert tj.e_o_fluxo_pedido(afb.OrigemDoGravador(500, None, "Outro jogo"), jogo) is False


def _retrato(sinks: str, *, info: str, pw_dump: str = "",
             lidas: list[tuple[str, ...]] | None = None) -> rs.RetratoDoSom:
    respostas = {
        tuple(pj.argv_json("sinks")): sinks,
        **{tuple(pj.argv_json(t)): "[]" for t in ("sources", "sink-inputs", "source-outputs")},
        ("pactl", "info"): info,
        ("pw-dump",): pw_dump,
    }

    def ler(argv: list[str]) -> str:
        if lidas is not None:
            lidas.append(tuple(argv))
        return respostas.get(tuple(argv), "")

    retrato = rs.RetratoDoSom(ler=ler)
    retrato.carregar()
    retrato.assumir()
    return retrato


@pytest.mark.parametrize("alvo", ["@DEFAULT_SINK@", "@DEFAULT_MONITOR@"])
def test_o_padrao_sem_default_sink_nao_casa_com_o_no_de_nome_perdido(alvo: str) -> None:
    sinks = pj.texto(pj.no(76, NULO, porcentos=[40, 40], props={"node.name": NULO}),
                     pj.no(77, "alsa_output.hdmi", porcentos=[100, 100]))
    retrato = _retrato(sinks, info="Server Name: PulseAudio (on PipeWire 1.0.5)\n")
    assert retrato.responder(["pactl", "get-sink-volume", alvo]) is rs.NAO_SEI


def test_o_retrato_guarda_o_json_completo_e_le_o_grafo_uma_vez_por_releitura() -> None:
    nome = NOMES[0]
    sinks = pj.texto(pj.no(76, NULO, descricao=NULO, porcentos=[40, 40],
                           props={"node.name": NULO, "object.serial": "76"}))
    lidas: list[tuple[str, ...]] = []
    retrato = _retrato(sinks, info=f"Default Sink: {nome}\n",
                       pw_dump=_grafo_de(_no_do_grafo(40, 76, nome,
                                                      **{"node.description": "Jogo"})),
                       lidas=lidas)
    assert retrato.descricoes() == {nome: "Jogo"}
    assert retrato.responder(["pactl", "get-sink-volume", "@DEFAULT_SINK@"]) == (
        "Volume: front-left: 26214 / 40% / -23.88 dB,   front-right: 26214 / 40% / -23.88 dB\n")
    texto = retrato.responder(pj.argv_json("sinks"))
    assert isinstance(texto, str)
    grafo = _Grafo(None)
    nos = ps.ler_nos("sinks", lambda _argv: texto, grafo)
    assert nos is not None and nos[0].nome == nome
    assert grafo.lidas == 0, "quem pergunta ao retrato não lê o grafo de novo"
    assert lidas.count(("pw-dump",)) == 1


FONTE_DO_CABO = "hefesto_dualsense_bt_0000ab"
FONTE_DO_RADIO = "hefesto_dualsense_bt_0000f0"
UNIQ_CABO = "aa:bb:cc:00:00:ab"
UNIQ_RADIO = "aa:bb:cc:00:00:f0"
FONTES_CURTAS = (
    f"700\t{FONTE_DO_CABO}\tPipeWire\ts16le 1ch 48000Hz\tRUNNING\n"
    f"701\t{FONTE_DO_RADIO}\tPipeWire\ts16le 1ch 48000Hz\tRUNNING\n"
)


@pytest.mark.parametrize(("no_cabo", "no_radio"), [(NOMES[0], NOMES[3]), (NOMES[2], NOMES[4])])
def test_quem_ouve_o_microfone_nomeia_o_jogo_inteiro(
    no_cabo: str, no_radio: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cabo e rádio, um jogo de nome perdido em cada: a luz nomeia os dois pelo nome inteiro."""
    capturas = [_fluxo(171, 719, 700, no_cabo, tipo="source"),
                _fluxo(179, 739, 701, no_radio, tipo="source")]
    respostas = {
        "--format=json list source-outputs": (0, json.dumps(capturas)),
        "list sources short": (0, FONTES_CURTAS),
    }
    monkeypatch.setattr(qom, "_rodar", lambda argv: respostas.get(" ".join(argv[1:]), (127, "")))
    monkeypatch.setattr(qom, "casamento_usb_agora", lambda uniqs: None)
    grafo = _Grafo(_grafo_de(_no_do_grafo(171, 719, no_cabo), _no_do_grafo(179, 739, no_radio)))
    monkeypatch.setattr(rs, "ler_o_pw_dump", grafo)

    leitura = qom.ler_quem_ouve([UNIQ_CABO, UNIQ_RADIO])
    assert leitura.por_uniq == {UNIQ_CABO: [no_cabo], UNIQ_RADIO: [no_radio]}
    assert grafo.lidas == 1

    (stream, _) = qom.streams_de_captura(json.dumps(capturas))
    assert stream.nome_do_cliente == "audio stream #719", (
        "o texto cru, sem a porta, segue sem o nome: o leitor é que completa")
