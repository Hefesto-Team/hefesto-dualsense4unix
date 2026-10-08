"""O-NO-DE-SOM-ACOMPANHA-O-CICLO-DO-DAEMON-01 — o servidor de som é a verdade, a memória é cache.

O QUE SE VIU (rodadas do engasgo de 06/10/2026, com o daemon do usuário no ar):
um `stop`/`start` deixou os alto-falantes «Controle N» duplicados, e com os nós
tirados por `pactl unload-module` o subsistema seguiu com o módulo velho na
memória (o vigia acusou `laco_voltou parado_s=330.8`).

A CAUSA, no código: o `iniciar()` do nó devolvia `True` só porque
`_module_id is not None`, a volta só chamava `iniciar()` de nó novo, e o `start`
só adotava os endpoints da háptica; do nó de som que um daemon anterior deixou
ninguém sabia.

O QUE ESTE ARQUIVO MEDE: o nó DO PRODUTO (`SinkVirtualPipeWire`,
`EndpointDeHaptica`) e o gerenciador DO PRODUTO, contra um servidor de mentira
COM ESTADO (`load-module`/`unload-module`/`list short modules`), com os quatro
controles, dois no cabo e dois no rádio. Nada aqui fala com o servidor de som
de ninguém.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as som
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

_P1, _P2, _P3, _P4 = (f"aa:bb:cc:5e:a3:c{n}" for n in (1, 2, 3, 4))
_QUINTO = "aa:bb:cc:5e:a3:c5"
_MESA = (_P1, _P2, _P3, _P4)
_TRANSPORTE = {_P1: "usb", _P2: "usb", _P3: "bt", _P4: "bt"}


class _Controle:
    def __init__(self, uniq: str) -> None:
        self.uniq = uniq
        self.transporte = _TRANSPORTE.get(uniq, "usb")


class _Servidor:
    """O `pactl` de mentira: módulos com estado, e só o que o nó pergunta."""

    def __init__(self) -> None:
        # o servidor de pé sempre tem módulo seu: lista vazia é `pactl` mudo, não resposta
        self.modulos: dict[str, tuple[str, str]] = {"1": ("libpipewire-module-rt", "")}
        self._proximo = 40
        self.mudo = False
        self.teimoso: set[str] = set()  # `unload-module` destes ids falha uma vez
        self.pedidos: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str | None:
        self.pedidos.append(list(argv))
        if argv[:4] == ["pactl", "list", "short", "modules"]:
            if self.mudo:
                return None
            return "\n".join(f"{i}\t{m}\t{a}\t" for i, (m, a) in self.modulos.items())
        if self.mudo:
            return None
        if argv[:2] == ["pactl", "load-module"]:
            return self.carregar(argv[2], " ".join(argv[3:]))
        if argv[:2] == ["pactl", "unload-module"]:
            if argv[2] in self.teimoso:
                self.teimoso.discard(argv[2])
                return None
            return "" if self.modulos.pop(argv[2], None) is not None else None
        return ""

    def carregar(self, modulo: str, argumentos: str) -> str:
        """Como o PipeWire: dois `load-module` com o mesmo nome dão DOIS módulos."""
        self._proximo += 1
        self.modulos[str(self._proximo)] = (modulo, argumentos)
        return f"{self._proximo}\n"

    def sinks_do_som(self) -> list[str]:
        return sorted(
            a.split("sink_name=")[1].split()[0]
            for m, a in self.modulos.values()
            if m == "module-null-sink" and "sink_name=hefesto_som_" in a
        )

    def loopbacks(self) -> list[str]:
        return sorted(a for m, a in self.modulos.values() if m == "module-loopback")

    def dos_outros(self) -> int:
        return sum(1 for m, a in self.modulos.values() if "hefesto" not in a.lower())

    def do_hefesto(self) -> list[str]:
        """Todo módulo desta casa de pé: sinks do som, rotas e endpoints da háptica."""
        return sorted(
            i for i, (m, a) in self.modulos.items()
            if "hefesto_som_" in a or "HEFESTO" in a
        )

    def id_do_sink(self, nome: str) -> str:
        (achado,) = [
            i for i, (m, a) in self.modulos.items()
            if m == "module-null-sink" and f"sink_name={nome} " in a + " "
        ]
        return achado

    def por_fora(self, module_id: str) -> None:
        """`pactl unload-module` na mão de alguém."""
        del self.modulos[module_id]


@pytest.fixture
def servidor(monkeypatch: pytest.MonkeyPatch) -> _Servidor:
    srv = _Servidor()
    monkeypatch.setattr(som, "_o_servidor_atende", lambda *_a, **_k: True)
    monkeypatch.setattr(som, "rodar_pactl", srv)
    monkeypatch.setattr(eh, "rodar_pactl", srv)
    return srv


def _rota(uniq: str) -> som.RotaDoNo:
    """Cabo: o nó entrega na placa do controle. Rádio: o mix do PC cai no nó."""
    if _TRANSPORTE.get(uniq, "usb") == "usb":
        return som.RotaDoNo(tem_rota=True, sink=f"alsa_output.placa-{uniq[-1]}",
                            por_onde="cabo", fonte=som.FONTE_PADRAO)
    return som.RotaDoNo(tem_rota=True, sink="", por_onde="radio", fonte=som.FONTE_MIX,
                        monitor_do_mix="alsa_output.pci-0000_0c_00.4.analog-stereo.monitor")


def _no(servidor: _Servidor, uniq: str) -> som.SinkVirtualPipeWire:
    return som.SinkVirtualPipeWire(uniq=uniq, runner=servidor, rota=_rota(uniq))


def _gerenciador(servidor: _Servidor) -> mod.GerenciadorDeNosDeSom:
    return mod.GerenciadorDeNosDeSom(fabrica=lambda uniq: _no(servidor, uniq), runner=servidor)


def _mesa() -> list[Any]:
    return [_Controle(u) for u in _MESA]


def _nomes(*uniqs: str) -> list[str]:
    return sorted(som.nome_do_sink(u) for u in uniqs)


# ---------------------------------------------------------------------------
# (1) o módulo some por fora e a volta seguinte o sobe de novo


def test_o_no_que_sumiu_por_fora_sobe_de_novo_no_iniciar(servidor: _Servidor) -> None:
    no = _no(servidor, _P1)
    assert no.iniciar()
    velho = no.module_id
    servidor.por_fora(servidor.id_do_sink(no.nome))
    assert no.iniciar(), "o nó não subiu de novo"
    assert no.module_id != velho, "o nó seguiu com o id de um módulo que o servidor não tem"
    assert servidor.sinks_do_som() == _nomes(_P1), "o servidor ficou sem o nó ou com dois"
    assert len(servidor.loopbacks()) == 1, "a rota velha ficou, ou a nova não subiu"


def test_a_volta_do_daemon_ergue_os_quatro_que_foram_tirados_por_fora(
    servidor: _Servidor,
) -> None:
    ger = _gerenciador(servidor)
    ger.reconciliar(_mesa())
    assert servidor.sinks_do_som() == _nomes(*_MESA)
    for uniq in (_P1, _P3):
        servidor.por_fora(servidor.id_do_sink(som.nome_do_sink(uniq)))
    ger.reconciliar(_mesa())
    assert servidor.sinks_do_som() == _nomes(*_MESA), "o nó tirado por fora nunca voltou"
    assert sorted(ger.nos) == sorted(_MESA)
    assert len(servidor.loopbacks()) == 4, "uma rota ficou de fora, ou sobrou uma velha"


def test_servidor_que_nao_responde_nao_derruba_nenhum_no(servidor: _Servidor) -> None:
    # A decisão D-0810-O-NO-DE-SOM-ORFAO-SE-DERRUBA.
    """«Não sei» não é «sumiu»: o `pactl` em recuo não pode esvaziar a mesa."""
    ger = _gerenciador(servidor)
    ger.reconciliar(_mesa())
    antes = sorted(servidor.modulos)
    servidor.mudo = True
    servidor.pedidos.clear()
    ger.reconciliar(_mesa())
    assert sorted(ger.nos) == sorted(_MESA)
    assert not [p for p in servidor.pedidos if p[1:2] == ["unload-module"]]
    servidor.mudo = False
    assert sorted(servidor.modulos) == antes


def test_resposta_sem_nenhum_modulo_tambem_e_nao_sei(servidor: _Servidor) -> None:
    """Servidor de pé sempre tem módulo seu: texto vazio é `pactl` calado, não «sumiu tudo»."""
    ger = _gerenciador(servidor)
    ger.reconciliar(_mesa())
    antes = sorted(servidor.modulos)
    ger_runner = ger._runner

    def calado(argv: list[str]) -> str | None:
        return "" if argv[:4] == ["pactl", "list", "short", "modules"] else servidor(argv)

    ger._runner = calado
    ger.reconciliar(_mesa())
    assert sorted(servidor.modulos) == antes, "a lista vazia derrubou ou recriou nós"
    ger._runner = ger_runner


def test_o_endpoint_da_haptica_que_sumiu_por_fora_sobe_de_novo(servidor: _Servidor) -> None:
    ancora = eh.Ancora(syspath="/devices/pci0000:00/usb3/3-1",
                       declarado="/devices/pci0000:00/usb3/3-1/3-1:1.0")
    endpoint = eh.EndpointDeHaptica(uniq=_P1, ancora=ancora, runner=servidor)
    assert endpoint.iniciar()
    velho = endpoint.module_id
    assert endpoint.no_ar() is True
    servidor.por_fora(velho or "")
    assert endpoint.no_ar() is False
    assert endpoint.iniciar(), "o endpoint não subiu de novo"
    assert endpoint.module_id != velho
    de_pe = eh.endpoints_de_pe(servidor)
    assert [len(v) for v in de_pe.values()] == [1], f"endpoint duplicado ou ausente: {de_pe}"


def test_o_endpoint_com_o_servidor_mudo_segue_de_pe(servidor: _Servidor) -> None:
    ancora = eh.Ancora(syspath="/devices/pci0000:00/usb3/3-1",
                       declarado="/devices/pci0000:00/usb3/3-1/3-1:1.0")
    endpoint = eh.EndpointDeHaptica(uniq=_P1, ancora=ancora, runner=servidor)
    assert endpoint.iniciar()
    servidor.mudo = True
    assert endpoint.no_ar() is None
    assert endpoint.iniciar(), "«não sei» virou «caiu»"


# ---------------------------------------------------------------------------
# (2) o `start` com módulos do daemon anterior não duplica


def test_o_start_derruba_o_que_o_daemon_anterior_deixou_e_nao_duplica(
    servidor: _Servidor,
) -> None:
    # A decisão D-0810-O-NO-DE-SOM-ORFAO-SE-DERRUBA.
    velho = mod.GerenciadorDeNosDeSom(fabrica=lambda u: _no(servidor, u), runner=servidor)
    velho.reconciliar([*_mesa(), _Controle(_QUINTO)])
    assert len(servidor.sinks_do_som()) == 5
    antes = set(servidor.do_hefesto())
    # o daemon velho morre SEM `stop`: a memória some, o servidor guarda tudo

    novo = _gerenciador(servidor)
    novo.reconciliar(_mesa())

    assert servidor.sinks_do_som() == _nomes(*_MESA), (
        f"nó duplicado ou nó de controle que saiu: {servidor.sinks_do_som()}")
    assert len(servidor.loopbacks()) == 4, "rota duplicada, ou rota do quinto ficou"
    assert not (antes & set(servidor.modulos)), "um módulo do daemon velho foi adotado às cegas"


def test_o_no_novo_nao_carrega_ao_lado_do_que_o_daemon_velho_deixou(
    servidor: _Servidor,
) -> None:
    primeiro = _no(servidor, _P2)
    assert primeiro.iniciar()
    segundo = _no(servidor, _P2)  # outro processo, mesma identidade
    assert segundo.iniciar()
    assert servidor.sinks_do_som() == _nomes(_P2)
    assert len(servidor.loopbacks()) == 1


def test_o_endpoint_do_daemon_anterior_e_adotado_e_nao_duplicado(servidor: _Servidor) -> None:
    # A decisão D-0810-O-NO-DE-SOM-ORFAO-SE-DERRUBA.
    ancora = eh.Ancora(syspath="/devices/pci0000:00/usb3/3-2",
                       declarado="/devices/pci0000:00/usb3/3-2/3-2:1.0")
    assert eh.EndpointDeHaptica(uniq=_P2, ancora=ancora, runner=servidor).iniciar()
    depois = eh.EndpointDeHaptica(uniq=_P2, ancora=ancora, runner=servidor)
    assert depois.iniciar()
    assert [len(v) for v in eh.endpoints_de_pe(servidor).values()] == [1]


# ---------------------------------------------------------------------------
# (3) o `stop` deixa o servidor sem nenhum nó de som do Hefesto


def test_o_stop_deixa_o_servidor_sem_no_de_som_nem_rota(servidor: _Servidor) -> None:
    ger = _gerenciador(servidor)
    ger.reconciliar(_mesa())
    assert servidor.sinks_do_som() and servidor.loopbacks()
    ger.parar()
    assert servidor.sinks_do_som() == []
    assert servidor.loopbacks() == []
    assert servidor.do_hefesto() == []


def test_o_stop_confere_e_derruba_o_que_o_primeiro_unload_nao_levou(
    servidor: _Servidor,
) -> None:
    """O `unload-module` falha calado (o runner devolve `None`): o `stop` pergunta de novo."""
    ger = _gerenciador(servidor)
    ger.reconciliar(_mesa())
    servidor.teimoso.update({servidor.id_do_sink(som.nome_do_sink(u)) for u in _MESA[:2]})
    servidor.teimoso.update(
        i for i, (m, a) in servidor.modulos.items() if m == "module-loopback")
    ger.parar()
    assert servidor.do_hefesto() == [], f"sobrou módulo depois do stop: {servidor.do_hefesto()}"


def test_o_parar_do_no_confere_que_o_modulo_saiu(servidor: _Servidor) -> None:
    """Um `unload-module` que falha calado não deixa o nó para trás: o `parar` pergunta de novo."""
    no = _no(servidor, _P3)
    assert no.iniciar()
    servidor.teimoso.add(servidor.id_do_sink(no.nome))
    servidor.teimoso.update(i for i, (m, _a) in servidor.modulos.items() if m == "module-loopback")
    no.parar()
    assert servidor.do_hefesto() == [], f"o nó ficou no servidor: {servidor.do_hefesto()}"


def test_o_stop_derruba_o_no_que_so_o_servidor_conhece(servidor: _Servidor) -> None:
    """Uma exceção engolida no meio do `stop` não deixa o nó no servidor."""
    ger = _gerenciador(servidor)
    ger.reconciliar(_mesa())
    por_estourar = ger.nos[_P1]

    def estoura() -> None:
        raise RuntimeError("parar() estourou")

    por_estourar.parar = estoura  # type: ignore[method-assign]
    ger.parar()
    assert servidor.sinks_do_som() == [], "o nó que estourou no parar() ficou no servidor"
    assert servidor.loopbacks() == []


def test_o_stop_nao_toca_modulo_de_outro_dono(servidor: _Servidor) -> None:
    # A decisão D-0810-O-NO-DE-SOM-ORFAO-SE-DERRUBA.
    servidor.carregar("module-null-sink", "sink_name=sink_de_outra_gente format=s16le")
    servidor.carregar("module-loopback", "source=outra.monitor sink=outra_saida")
    ger = _gerenciador(servidor)
    ger.reconciliar(_mesa())
    ger.parar()
    assert servidor.dos_outros() == 3, "o stop derrubou módulo que não é do Hefesto"
