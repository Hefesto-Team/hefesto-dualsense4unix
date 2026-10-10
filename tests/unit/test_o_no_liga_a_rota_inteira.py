"""O nó liga a rota inteira e segue a saída padrão.

Sprint O-NO-LIGA-A-ROTA-INTEIRA-E-SEGUE-A-SAIDA-PADRAO-01. A volta compara os
`module-loopback` que a rota PEDE com os que estão DE PÉ no servidor: desce o
que sobra, sobe o que falta, e o `module-null-sink` não muda de id (o jogo
que escolheu o nó não o perde). A saída padrão que o servidor não soube dizer
(`None`) deixa o mix de pé como está; com o servidor em recuo, nada se escreve.

Dois controles, P1 no cabo e P2 no rádio, os dois em `mix`, pela volta de
verdade (`GerenciadorDeNosDeSom.reconciliar`) contra um servidor de mentira
que guarda o que está carregado e responde `pactl list short modules`.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt

P1 = "aa:bb:cc:00:00:d1"
P2 = "aa:bb:cc:00:00:d2"
NO_P1 = af.nome_do_sink(P1)
NO_P2 = af.nome_do_sink(P2)
PLACA_P1 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)
HDMI = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"
FONE = "alsa_output.pci-0000_0a_00.3.analog-stereo"


class _Servidor:
    """O `pipewire-pulse` de mentira: carrega, descarrega, e diz o que está de pé."""

    def __init__(self) -> None:
        self.carregados: dict[str, list[str]] = {}
        self.argvs: list[list[str]] = []
        self.padrao: str | None = HDMI
        self.recusar_loopbacks = 0
        self._proximo = 500

    def __call__(self, argv: list[str]) -> str | None:
        self.argvs.append(list(argv))
        if argv[:2] == ["pactl", "load-module"]:
            if argv[2] == "module-loopback" and self.recusar_loopbacks > 0:
                self.recusar_loopbacks -= 1
                return None
            self._proximo += 1
            self.carregados[str(self._proximo)] = list(argv)
            return f"{self._proximo}\n"
        if argv[:2] == ["pactl", "unload-module"]:
            self.carregados.pop(argv[2], None)
            return ""
        if "get-default-sink" in argv:
            return None if self.padrao is None else f"{self.padrao}\n"
        if argv[:4] == ["pactl", "list", "short", "modules"]:
            linhas = ["1\tmodule-native-protocol-unix\t\t"]
            linhas += [f"{i}\t{a[2]}\t{' '.join(a[3:])}\t" for i, a in self.carregados.items()]
            return "\n".join(linhas) + "\n"
        return ""

    def fios(self) -> set[tuple[str, str]]:
        """``(source, sink)`` de cada `module-loopback` de pé."""
        achados: set[tuple[str, str]] = set()
        for argv in self.carregados.values():
            if argv[2] != "module-loopback":
                continue
            campos = dict(a.split("=", 1) for a in argv[3:] if "=" in a)
            achados.add((campos.get("source", ""), campos.get("sink", "")))
        return achados

    def id_do_fio(self, source: str, sink: str) -> str:
        for module_id, argv in self.carregados.items():
            if f"source={source}" in argv and f"sink={sink}" in argv:
                return module_id
        raise AssertionError(f"fio {source} -> {sink} não está de pé")

    def descarregados(self) -> list[str]:
        return [a[2] for a in self.argvs if a[:2] == ["pactl", "unload-module"]]

    def escritas(self) -> list[list[str]]:
        return [a for a in self.argvs if a[1:2] in (["load-module"], ["unload-module"])]


def _completo(monitor: str) -> set[tuple[str, str]]:
    """A rota inteira dos dois com o mix vindo de ``monitor``."""
    return {
        (f"{NO_P1}.monitor", PLACA_P1),
        (monitor, NO_P1),
        (monitor, NO_P2),
    }


@pytest.fixture
def servidor(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> _Servidor:
    servidor = _Servidor()
    monkeypatch.setattr(bt, "PACTL", bt.RecuoDoPactl(relogio=lambda: 1000.0))
    monkeypatch.setattr(bt.shutil, "which", lambda _nome: "/usr/bin/pactl")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(af, "_rodar", servidor)
    monkeypatch.setattr(af.SinkVirtualPipeWire, "_passar_a_escolha_dela", lambda _self: None)
    monkeypatch.setattr(
        af, "sink_do_controle", lambda uniq, *_a, **_k: PLACA_P1 if uniq == P1 else ""
    )
    return servidor


def _gerenciador(servidor: _Servidor) -> mod.GerenciadorDeNosDeSom:
    return mod.GerenciadorDeNosDeSom(
        fonte_por_controle=lambda _u: af.FONTE_MIX,
        ponte_do_radio_por_controle=lambda _u: (lambda: True),
        runner=servidor,
    )


def _volta(ger: mod.GerenciadorDeNosDeSom) -> None:
    ger.reconciliar([
        mod.ControleNaLista(uniq=P1, caminho="/dev/hidraw-de-mentira0", transporte="cabo"),
        mod.ControleNaLista(uniq=P2, caminho="/dev/hidraw-de-mentira1", transporte="rádio"),
    ])


def _ids(ger: mod.GerenciadorDeNosDeSom) -> dict[str, str | None]:
    return {u: no.module_id for u, no in ger.nos.items()}


def test_a_rota_que_nao_subiu_sobe_na_volta_seguinte(servidor: _Servidor) -> None:
    """(a) O servidor recusa o primeiro `module-loopback` (o do P1 até a placa).

    MORDIDA: religar só pela assinatura, sem olhar o que está de pé.
    """
    servidor.recusar_loopbacks = 1
    ger = _gerenciador(servidor)
    _volta(ger)
    assert (f"{NO_P1}.monitor", PLACA_P1) not in servidor.fios(), "a régua não recusou"
    ids = _ids(ger)

    _volta(ger)

    assert servidor.fios() == _completo(f"{HDMI}.monitor"), sorted(servidor.fios())
    assert _ids(ger) == ids, "o module-null-sink mudou de id"
    assert servidor.descarregados() == []


def test_o_loopback_descarregado_por_fora_volta(servidor: _Servidor) -> None:
    """(b) Os dois loopbacks tirados por fora voltam, e o nó fica o mesmo.

    MORDIDAS: religar só pela assinatura; `no_ar` que olha os loopbacks troca o id.
    """
    ger = _gerenciador(servidor)
    _volta(ger)
    ids = _ids(ger)
    servidor.carregados.pop(servidor.id_do_fio(f"{NO_P1}.monitor", PLACA_P1))
    servidor.carregados.pop(servidor.id_do_fio(f"{HDMI}.monitor", NO_P2))

    _volta(ger)

    assert servidor.fios() == _completo(f"{HDMI}.monitor"), sorted(servidor.fios())
    assert _ids(ger) == ids, "o nó saiu do lugar para religar a rota"


def test_o_mix_segue_a_saida_padrao_do_hdmi_ao_fone(servidor: _Servidor) -> None:
    """(c) A saída padrão sai do HDMI e vai ao fone: o mix dos dois vem do fone.

    MORDIDA: deixar o monitor fora da comparação.
    """
    ger = _gerenciador(servidor)
    _volta(ger)
    ids = _ids(ger)
    saida = servidor.id_do_fio(f"{NO_P1}.monitor", PLACA_P1)

    servidor.padrao = FONE
    _volta(ger)

    assert servidor.fios() == _completo(f"{FONE}.monitor"), sorted(servidor.fios())
    assert _ids(ger) == ids
    assert saida not in servidor.descarregados(), "a saída para o alto-falante caiu junto"


def test_o_mix_recusado_por_laco_sobe_quando_a_saida_volta_a_tv(servidor: _Servidor) -> None:
    """(d) Saída padrão no próprio nó do P1: o mix dele sai (laço); de volta à TV, sobe.

    O P2 segue com o mix vindo do nó do P1: o laço é só de quem toca em si mesmo.
    MORDIDA: deixar o monitor fora da comparação.
    """
    ger = _gerenciador(servidor)
    _volta(ger)
    ids = _ids(ger)

    servidor.padrao = NO_P1
    _volta(ger)
    assert servidor.fios() == {
        (f"{NO_P1}.monitor", PLACA_P1),
        (f"{NO_P1}.monitor", NO_P2),
    }, sorted(servidor.fios())

    servidor.padrao = HDMI
    _volta(ger)
    assert servidor.fios() == _completo(f"{HDMI}.monitor"), sorted(servidor.fios())
    assert _ids(ger) == ids


def test_a_saida_padrao_ilegivel_nao_derruba_o_mix(servidor: _Servidor) -> None:
    """(e) Uma volta em que o servidor não diz a saída padrão: nenhum `unload-module`.

    É o defeito de 17/09: «não sei» lido como «sem mix» derrubava um loopback
    bom por uma resposta vazia. MORDIDA: tratar `None` como `""`.
    """
    ger = _gerenciador(servidor)
    _volta(ger)
    antes = servidor.fios()

    servidor.padrao = None
    _volta(ger)

    assert servidor.descarregados() == []
    assert servidor.fios() == antes == _completo(f"{HDMI}.monitor")


def test_com_o_servidor_em_recuo_a_volta_nao_escreve(servidor: _Servidor) -> None:
    """(f) Servidor em recuo, rota faltando e saída padrão trocada: nada se escreve."""
    ger = _gerenciador(servidor)
    _volta(ger)
    servidor.carregados.pop(servidor.id_do_fio(f"{NO_P1}.monitor", PLACA_P1))
    servidor.carregados.pop(servidor.id_do_fio(f"{HDMI}.monitor", NO_P2))
    servidor.padrao = FONE
    escritas = len(servidor.escritas())

    bt.PACTL.estourou()
    _volta(ger)

    assert servidor.escritas()[escritas:] == []


def test_o_monitor_que_o_servidor_nao_diz_e_none() -> None:
    """«Não sei» tem forma própria: `None`, e `""` fica só para «sem mix»."""
    assert af.monitor_da_saida_padrao(runner=lambda _a: None) is None
    assert af.monitor_da_saida_padrao(runner=lambda _a: "\n") is None
    assert af.monitor_da_saida_padrao(runner=lambda _a: f"{HDMI}\n") == f"{HDMI}.monitor"
    rota = af.RotaDoNo(True, sink=PLACA_P1, por_onde=af.POR_CABO, fonte=af.FONTE_MIX,
                       monitor_do_mix=None)
    assert af.argv_das_rotas(NO_P1, rota) == (af.argv_para_ligar_o_no(NO_P1, PLACA_P1),)
