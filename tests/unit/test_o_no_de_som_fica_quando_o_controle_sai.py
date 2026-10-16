"""O-NO-DE-SOM-FICA-QUANDO-O-CONTROLE-SAI-01 — o nó fica, a rota vai e volta.

**A decisão é de produto** (`D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE`, 08/09/2026,
«concordo com as 5»; a resposta de 13/10/2026: «só os que já entraram»): o nó de
som de cada controle nasce quando o controle entra pela primeira vez na sessão e
fica até o daemon parar. Nó que some quebra o jogo que o escolheu: o servidor
move o fluxo para a saída padrão, e quando o nó volta (o mesmo nome, outro id) o
jogo já não está nele.

O gerenciador derrubava o nó de todo `uniq` que saía da lista do sysfs, e a
troca do cabo pelo rádio (e a queda do rádio) passa por «fora da lista» por uma
volta de 5 s. A cura: o nó que nasceu fica; o que sai é a ROTA.

O servidor de som é de mentira, mas com ESTADO e mais fiel que o do vizinho: ele
responde `pactl list short modules` de verdade, guarda o fluxo de um jogo preso a
um nó e o MOVE para a saída padrão quando o `module-null-sink` desce, que é o que
o PipeWire faz. Nenhum módulo entra no servidor de ninguém. Os endereços são da
faixa forjada (`02fe00`).
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
    ControleNaLista,
    GerenciadorDeNosDeSom,
)
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as mic
from tests.unit.test_o_alto_falante_virtual_esconde_o_transporte import (
    _HDMI,
    _SINK_P1,
    _SINK_P2,
    _UNIQ_NUNCA_VISTO,
    _UNIQ_P1,
    _UNIQ_P2,
    _UNIQ_P3,
    _UNIQ_P4,
    _USB_P1,
    _USB_P2,
    ServidorDeSomDeMentira,
)


class ServidorComFluxos(ServidorDeSomDeMentira):
    """O servidor de mentira que lista os módulos e carrega o fluxo de um jogo."""

    def __init__(self) -> None:
        super().__init__()
        self.padrao = _HDMI
        self.fluxos: dict[str, str] = {}
        self.trocas_do_padrao: list[list[str]] = []
        self.chamadas: list[list[str]] = []

    def abrir_o_jogo(self, nome: str, no: str) -> None:
        """Um jogo escolheu o nó `no` como saída."""
        self.fluxos[nome] = no

    def __call__(self, argv: list[str]) -> str | None:
        self.chamadas.append(list(argv))
        if argv[:2] == ["pactl", "unload-module"]:
            args = self.modulos.get(argv[2], ())
            if args and args[0] == "module-null-sink":
                nome = next(a for a in args if a.startswith("sink_name=")).split("=", 1)[1]
                for jogo, destino in list(self.fluxos.items()):
                    if destino == nome:
                        self.fluxos[jogo] = self.padrao
            return super().__call__(argv)
        if argv[:4] == ["pactl", "list", "short", "modules"]:
            linhas = ["1\tmodule-native-protocol-unix\t"]
            linhas += [
                f"{ident}\t{args[0]}\t{' '.join(args[1:])}"
                for ident, args in self.modulos.items()
            ]
            return "\n".join(linhas) + "\n"
        if argv[:2] == ["pactl", "set-default-sink"]:
            self.trocas_do_padrao.append(argv)
            self.padrao = argv[2]
            return ""
        if "get-default-sink" in argv:
            return f"{self.padrao}\n"
        return super().__call__(argv)

    def no_do(self, jogo: str) -> str:
        return self.fluxos[jogo]

    def laco_para(self, no: str) -> list[tuple[str, str]]:
        """Os `module-loopback` que levam o que sai de `no` (ou entra nele)."""
        return [
            (s, d) for s, d in self.lacos() if s == f"{no}.monitor" or d == no
        ]


_ASSENTO = {_UNIQ_P1: 1, _UNIQ_P2: 2, _UNIQ_P3: 3, _UNIQ_P4: 4}


@pytest.fixture
def servidor(monkeypatch: pytest.MonkeyPatch) -> ServidorComFluxos:
    falso = ServidorComFluxos()
    monkeypatch.setattr(af, "_rodar", falso)
    anterior = mic.registrar_numerador_de_assento(lambda u: _ASSENTO.get(u))
    yield falso
    mic.registrar_numerador_de_assento(anterior)


@pytest.fixture(autouse=True)
def usb_da_bancada(monkeypatch: pytest.MonkeyPatch) -> None:
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


def _cabo(uniq: str) -> ControleNaLista:
    return ControleNaLista(uniq=uniq, caminho="/dev/hidraw-de-mentira", transporte="cabo")


def _radio(uniq: str) -> ControleNaLista:
    return ControleNaLista(uniq=uniq, caminho="/dev/hidraw-de-mentira", transporte="rádio")


def _ponte_de_pe(_uniq: str) -> Any:
    return lambda: True


def _gerenciador(fonte: str = af.FONTE_SFX) -> GerenciadorDeNosDeSom:
    return GerenciadorDeNosDeSom(
        ponte_do_radio_por_controle=_ponte_de_pe,
        fonte_por_controle=lambda _u: fonte,
    )


def _id_do_no(servidor: ServidorComFluxos, uniq: str) -> str:
    achados = [i for i, n in servidor.nos().items() if n == af.nome_do_sink(uniq)]
    assert len(achados) == 1, f"esperava um nó de {uniq}, o servidor tem {servidor.nos()}"
    return achados[0]


def test_o_controle_sai_e_volta_pelo_radio_e_o_no_e_o_mesmo(
    servidor: ServidorComFluxos,
) -> None:
    # D-0809-O-NO-DE-SOM-POR-CONTROLE-VIVE-SEMPRE
    """A troca do cabo pelo rádio passa por «fora da lista»: o id do nó não muda."""
    ger = _gerenciador()
    ger.reconciliar([_cabo(_UNIQ_P1)])
    nome = af.nome_do_sink(_UNIQ_P1)
    id_x = _id_do_no(servidor, _UNIQ_P1)
    servidor.abrir_o_jogo("jogo", nome)
    assert servidor.laco_para(nome) == [(f"{nome}.monitor", _SINK_P1)]

    ger.reconciliar([])
    assert _id_do_no(servidor, _UNIQ_P1) == id_x
    assert servidor.no_do("jogo") == nome, "o fluxo do jogo foi movido para a saída padrão"
    assert servidor.laco_para(nome) == [], "o nó ausente segue ligado a uma placa que saiu"

    ger.reconciliar([_radio(_UNIQ_P1)])
    assert _id_do_no(servidor, _UNIQ_P1) == id_x
    assert servidor.no_do("jogo") == nome
    rota = ger.nos[_UNIQ_P1].rota
    assert rota.tem_rota and rota.por_onde == af.POR_RADIO
    assert servidor.trocas_do_padrao == [], "entrar e sair mexeu na saída padrão do sistema"
    assert servidor.padrao == _HDMI


def test_o_controle_sai_e_volta_pelo_cabo_e_a_rota_volta_no_mesmo_no(
    servidor: ServidorComFluxos,
) -> None:
    ger = _gerenciador()
    ger.reconciliar([_cabo(_UNIQ_P1)])
    nome = af.nome_do_sink(_UNIQ_P1)
    id_x = _id_do_no(servidor, _UNIQ_P1)
    servidor.abrir_o_jogo("jogo", nome)

    ger.reconciliar([])
    ger.reconciliar([])
    assert servidor.laco_para(nome) == []
    ger.reconciliar([_cabo(_UNIQ_P1)])

    assert _id_do_no(servidor, _UNIQ_P1) == id_x
    assert servidor.no_do("jogo") == nome
    assert servidor.laco_para(nome) == [(f"{nome}.monitor", _SINK_P1)]
    assert servidor.trocas_do_padrao == []


def test_o_no_ausente_diz_que_nao_tem_para_onde_ir(servidor: ServidorComFluxos) -> None:
    """«Sem controle, o nó diz que não tem para onde ir»: a rota carrega o motivo."""
    ger = _gerenciador()
    ger.reconciliar([_cabo(_UNIQ_P1), _radio(_UNIQ_P2)])
    ger.reconciliar([])

    no_cabo, no_radio = ger.nos[_UNIQ_P1], ger.nos[_UNIQ_P2]
    assert not no_cabo.rota.tem_rota
    assert no_cabo.rota.motivo == af.MOTIVO_NO_SEM_PLACA_NO_CABO
    assert not no_radio.rota.tem_rota
    assert no_radio.rota.motivo in (af.MOTIVO_NO_SEM_PONTE_NO_RADIO, af.MOTIVO_NO_SEM_SABER_MONTAR)


def test_o_mix_do_pc_tambem_desce_com_o_controle_e_o_no_fica(
    servidor: ServidorComFluxos,
) -> None:
    """Em «mix» há um segundo fio (a saída padrão até o nó): ele também vai com a rota."""
    ger = _gerenciador(af.FONTE_MIX)
    ger.reconciliar([_cabo(_UNIQ_P1)])
    nome = af.nome_do_sink(_UNIQ_P1)
    id_x = _id_do_no(servidor, _UNIQ_P1)
    assert (f"{_HDMI}.monitor", nome) in servidor.laco_para(nome)

    ger.reconciliar([])
    assert servidor.laco_para(nome) == []
    assert _id_do_no(servidor, _UNIQ_P1) == id_x

    ger.reconciliar([_cabo(_UNIQ_P1)])
    assert _id_do_no(servidor, _UNIQ_P1) == id_x
    assert (f"{_HDMI}.monitor", nome) in servidor.laco_para(nome)
    assert servidor.trocas_do_padrao == []


def test_os_quatro_de_pe_um_sai_e_volta_e_os_outros_tres_ficam_intactos(
    servidor: ServidorComFluxos,
) -> None:
    ger = _gerenciador()
    todos = [_UNIQ_P1, _UNIQ_P2, _UNIQ_P3, _UNIQ_P4]
    ger.reconciliar([_cabo(_UNIQ_P1), _cabo(_UNIQ_P2), _radio(_UNIQ_P3), _radio(_UNIQ_P4)])
    antes = {u: _id_do_no(servidor, u) for u in todos}
    lacos_antes = {u: servidor.laco_para(af.nome_do_sink(u)) for u in todos}

    ger.reconciliar([_cabo(_UNIQ_P1), _radio(_UNIQ_P3), _radio(_UNIQ_P4)])
    assert {u: _id_do_no(servidor, u) for u in todos} == antes
    for u in (_UNIQ_P1, _UNIQ_P3, _UNIQ_P4):
        assert servidor.laco_para(af.nome_do_sink(u)) == lacos_antes[u]
    assert servidor.laco_para(af.nome_do_sink(_UNIQ_P2)) == []
    assert ger.nos[_UNIQ_P3].rota.tem_rota and ger.nos[_UNIQ_P1].rota.tem_rota

    ger.reconciliar([_cabo(_UNIQ_P1), _cabo(_UNIQ_P2), _radio(_UNIQ_P3), _radio(_UNIQ_P4)])
    assert {u: _id_do_no(servidor, u) for u in todos} == antes
    assert {u: servidor.laco_para(af.nome_do_sink(u)) for u in todos} == lacos_antes


def test_controle_que_nunca_entrou_nao_ganha_no(servidor: ServidorComFluxos) -> None:
    """A resposta de 13/10: «só os que já entraram»; nenhum nó nasce para quem nunca veio."""
    ger = _gerenciador()
    ger.reconciliar([_cabo(_UNIQ_P1)])
    ger.reconciliar([])
    ger.reconciliar([_cabo(_UNIQ_P1)])
    assert set(servidor.nos().values()) == {af.nome_do_sink(_UNIQ_P1)}
    assert _UNIQ_NUNCA_VISTO not in ger.nos


def test_so_o_parar_derruba_o_no_ausente(servidor: ServidorComFluxos) -> None:
    ger = _gerenciador()
    ger.reconciliar([_cabo(_UNIQ_P1), _radio(_UNIQ_P2)])
    ger.reconciliar([_radio(_UNIQ_P2)])
    assert len(servidor.nos()) == 2

    ger.parar()

    assert servidor.nos() == {}
    assert [m for m in servidor.modulos.values() if m[0] in ("module-null-sink",
                                                            "module-loopback")] == []
    assert ger.nos == {}


def test_no_que_o_servidor_perdeu_com_o_controle_fora_nao_volta_sozinho(
    servidor: ServidorComFluxos,
) -> None:
    """Módulo tirado por fora: sai da memória; o controle que volta o ergue de novo."""
    ger = _gerenciador()
    ger.reconciliar([_cabo(_UNIQ_P1)])
    servidor.modulos.pop(_id_do_no(servidor, _UNIQ_P1))
    ger.reconciliar([])
    assert ger.nos == {}
    ger.reconciliar([_cabo(_UNIQ_P1)])
    assert set(servidor.nos().values()) == {af.nome_do_sink(_UNIQ_P1)}
    assert _UNIQ_P1 in ger.nos


def test_a_volta_sem_controle_nao_escreve_nada_no_servidor(
    servidor: ServidorComFluxos,
) -> None:
    """Nó ausente já sem rota: as voltas seguintes só leem, nenhum `load` nem `unload`."""
    ger = _gerenciador()
    ger.reconciliar([_cabo(_UNIQ_P1)])
    ger.reconciliar([])
    servidor.chamadas.clear()

    ger.reconciliar([])
    ger.reconciliar([])

    escritas = [c for c in servidor.chamadas if c[1] in ("load-module", "unload-module")]
    assert escritas == []
    assert servidor.chamadas, "a volta nem perguntou ao servidor: a régua não mede nada"


def test_o_controle_cai_do_radio_e_volta_pelo_radio_no_mesmo_no(
    servidor: ServidorComFluxos,
) -> None:
    """O gesto da bancada: desligar pelo PS e religar, só no rádio, em «mix»."""
    ger = _gerenciador(af.FONTE_MIX)
    ger.reconciliar([_radio(_UNIQ_P3)])
    nome = af.nome_do_sink(_UNIQ_P3)
    id_x = _id_do_no(servidor, _UNIQ_P3)
    servidor.abrir_o_jogo("jogo", nome)
    assert servidor.laco_para(nome) == [(f"{_HDMI}.monitor", nome)]

    ger.reconciliar([])
    assert _id_do_no(servidor, _UNIQ_P3) == id_x
    assert servidor.laco_para(nome) == []
    assert servidor.no_do("jogo") == nome

    ger.reconciliar([_radio(_UNIQ_P3)])
    assert _id_do_no(servidor, _UNIQ_P3) == id_x
    assert servidor.laco_para(nome) == [(f"{_HDMI}.monitor", nome)]
    assert servidor.no_do("jogo") == nome
    assert servidor.trocas_do_padrao == []


def test_com_a_porta_fechada_no_meio_da_volta_o_ausente_nao_se_mexe(
    servidor: ServidorComFluxos, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O stop fecha a porta enquanto a volta lê o servidor: o ausente fica para o ``parar``."""
    ger = _gerenciador()
    ger.reconciliar([_cabo(_UNIQ_P1)])
    nome = af.nome_do_sink(_UNIQ_P1)
    lendo = ServidorComFluxos.__call__

    def fecha_ao_ler(self: ServidorComFluxos, argv: list[str]) -> str | None:
        if argv[:4] == ["pactl", "list", "short", "modules"]:
            ger.fechar()
        return lendo(self, argv)

    monkeypatch.setattr(ServidorComFluxos, "__call__", fecha_ao_ler)
    servidor.chamadas.clear()
    ger.reconciliar([])

    assert [c for c in servidor.chamadas if c[1] == "unload-module"] == []
    assert servidor.laco_para(nome) == [(f"{nome}.monitor", _SINK_P1)]
