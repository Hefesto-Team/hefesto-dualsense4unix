"""O microfone desligado não abre a captura do cabo.

Decisão: D-2011-O-MICROFONE-DESLIGADO-NAO-ABRE-A-CAPTURA-DO-CABO. Medido em 20/11/2026 no
diário do serviço: em 77 de 77 conexões a palavra de quem usa era ``ligado=False`` e o canal
do cabo subiu 66 vezes com o ``parec`` lendo o microfone físico, o que deixa a captura do
controle aberta a sessão inteira. A fonte virtual («Microfone do Controle N») continua
publicada para quem a escolheu; o que segue a palavra é o alimentador que lê o aparelho.

O servidor de som é o de mentira, a source é a ``SourceVirtualPipeWire`` real e o alimentador é
processo de mentira. Nenhum ``pactl`` de verdade roda.

MORDIDAS: sem o ``if mudo`` de ``_ligar_o_canal`` o canal calado nasce com o ``parec``; sem a
chamada a ``_alimentador_segue_a_palavra`` em ``escrever_o_mudo`` o gesto de ligar não ergue o
alimentador e o de desligar não o derruba.
"""
from __future__ import annotations

import io
import os
import shutil
import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import bt_mic
from hefesto_dualsense4unix.integrations import (
    canal_do_microfone,
    dualsense_bt_audio,
    eleicao_de_microfone,
    microfone_filtrado,
)
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    SourceVirtualPipeWire,
    campo_do_controle,
)

P = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
CABO = "alsa_input.usb-Sony_DualSense_Wireless_Controller-00.HiFi__Mic__source"
EDGE = "alsa_input.usb-Sony_DualSense_Edge_Wireless_Controller-00.HiFi__Mic__source"


class _Servidor:
    """O pipewire-pulse de mentira: módulos com fifo de leitor aberto; o reinício leva tudo."""

    def __init__(self) -> None:
        self.modulos: dict[str, str] = {}
        self.carregados = 0
        self._proximo = 20
        self._leitores: list[int] = []

    def reiniciar(self) -> None:
        self.modulos.clear()
        for fd in self._leitores:
            os.close(fd)
        self._leitores.clear()

    def __call__(self, argv: list[str]) -> str | None:
        if argv[:4] == ["pactl", "list", "modules", "short"]:
            return "".join(f"{i}\tmodule-pipe-source\t{a}\n" for i, a in self.modulos.items())
        if argv[:4] == ["pactl", "list", "sources", "short"]:
            return ""
        if argv[:2] == ["pactl", "load-module"]:
            fifo = next(a[5:] for a in argv if a.startswith("file="))
            os.mkfifo(fifo)
            self._leitores.append(os.open(fifo, os.O_RDONLY | os.O_NONBLOCK))
            ident = str(self._proximo)
            self._proximo += 1
            self.modulos[ident] = " ".join(argv[3:])
            self.carregados += 1
            return ident + "\n"
        if argv[:2] == ["pactl", "unload-module"]:
            self.modulos.pop(argv[2], None)
            return ""
        return ""


class _Processo:
    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self.stdout = io.BytesIO(b"")
        self.codigo: int | None = None

    def poll(self) -> int | None:
        return self.codigo

    def terminate(self) -> None:
        self.codigo = 0

    def kill(self) -> None:
        self.codigo = -9

    def wait(self, timeout: float | None = None) -> int:
        if self.codigo is None:
            self.codigo = 0
        return self.codigo


class _Mundo:
    def __init__(self, servidor: _Servidor) -> None:
        self.servidor = servidor
        self.alimentadores: list[_Processo] = []
        self.mudos: list[list[str]] = []
        self.palavras: dict[str, bool | None] = {}

    def lancar(self, argv: list[str]) -> _Processo:
        proc = _Processo(argv)
        self.alimentadores.append(proc)
        return proc

    def rodar(self, argv: list[str]) -> bool:
        self.mudos.append(argv)
        return True

    def abrir(self, uniq: str, fonte: str | None = CABO) -> Any:
        return canal_do_microfone.abrir(
            uniq, "Microfone do Controle 1", fonte=fonte, lancar=self.lancar, rodar=self.rodar,
            filtrar=lambda argv: _Processo(argv),
            fabrica=lambda **kw: SourceVirtualPipeWire(runner=self.servidor, **kw))

    def vivos(self, uniq: str | None = None) -> list[_Processo]:
        return [
            p for p in self.alimentadores
            if p.codigo is None
            and (uniq is None or campo_do_controle(uniq)[0] in " ".join(p.argv))
        ]


@pytest.fixture
def mundo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Mundo]:
    servidor = _Servidor()
    pronto = _Mundo(servidor)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/pipewire")
    monkeypatch.setattr(canal_do_microfone, "_passar_a_escolha_do_usuario", lambda *_a: None)
    monkeypatch.setattr(canal_do_microfone, "_a_palavra_do_usuario", pronto.palavras.get)
    monkeypatch.setattr(canal_do_microfone, "_lancar_processo", pronto.lancar)
    monkeypatch.setattr(canal_do_microfone, "_rodar_pactl", pronto.rodar)
    monkeypatch.setattr(dualsense_bt_audio, "pactl_mudo", lambda: False)
    monkeypatch.setattr(microfone_filtrado, "_lancar_processo", lambda argv: _Processo(argv))
    microfone_filtrado.fechar_todos()
    for uniq in list(canal_do_microfone.de_pe()):
        canal_do_microfone.fechar(uniq)
    yield pronto
    for uniq in list(canal_do_microfone.de_pe()):
        canal_do_microfone.fechar(uniq)
    microfone_filtrado.fechar_todos()
    servidor.reiniciar()


def test_o_cabo_calado_publica_a_fonte_sem_abrir_a_captura(mundo: _Mundo) -> None:
    """D-2011-O-MICROFONE-DESLIGADO-NAO-ABRE-A-CAPTURA-DO-CABO: a fonte fica, o parec não nasce."""
    mundo.palavras[P[0]] = False
    canal = mundo.abrir(P[0])
    assert canal is not None and canal.no_ar() is True, "a fonte virtual sumiu da lista"
    assert canal_do_microfone.de_pe() == {P[0]: canal.nome}
    assert mundo.vivos() == [], "o microfone desligado abriu a captura do controle"
    assert mundo.mudos[-1][-2:] == [canal.nome, "1"], "o nó não nasceu calado"


def test_o_cabo_ligado_ou_sem_palavra_nasce_lendo_o_aparelho(mundo: _Mundo) -> None:
    """D-2011-O-MICROFONE-DESLIGADO-NAO-ABRE-A-CAPTURA-DO-CABO: só a palavra False fecha."""
    mundo.palavras[P[0]] = True
    mundo.abrir(P[0])
    mundo.abrir(P[1])
    assert len(mundo.vivos(P[0])) == 1 and len(mundo.vivos(P[1])) == 1


def test_ligar_ergue_o_alimentador_e_desligar_o_derruba(mundo: _Mundo) -> None:
    """D-2011-O-MICROFONE-DESLIGADO-NAO-ABRE-A-CAPTURA-DO-CABO: o gesto vale na hora."""
    mundo.palavras[P[0]] = False
    mundo.abrir(P[0])
    canal_do_microfone.escrever_o_mudo(P[0], False, rodar=mundo.rodar, lancar=mundo.lancar)
    assert len(mundo.vivos(P[0])) == 1, "ligar o microfone não ergueu o alimentador"
    assert mundo.vivos(P[0])[0].argv[1] == f"--device={CABO}", "o alimentador leu outra fonte"
    canal_do_microfone.escrever_o_mudo(P[0], False, rodar=mundo.rodar, lancar=mundo.lancar)
    assert len(mundo.alimentadores) == 1, "o gesto repetido abriu um segundo parec"
    canal_do_microfone.escrever_o_mudo(P[0], True, rodar=mundo.rodar, lancar=mundo.lancar)
    assert mundo.vivos(P[0]) == [], "desligar o microfone deixou a captura aberta"
    assert canal_do_microfone.canal_de_pe(P[0]) is not None, "desligar derrubou a fonte virtual"


def test_o_mudo_ja_escrito_nao_esconde_o_alimentador_fora_da_palavra(mundo: _Mundo) -> None:
    """D-2011-O-MICROFONE-DESLIGADO-NAO-ABRE-A-CAPTURA-DO-CABO: o mudo lembrado não decide."""
    mundo.palavras[P[0]] = True
    mundo.abrir(P[0])
    canal_do_microfone._MUDO_ESCRITO[P[0]] = True
    canal_do_microfone.escrever_o_mudo(P[0], True, rodar=mundo.rodar, lancar=mundo.lancar)
    assert mundo.vivos(P[0]) == [], "o mudo repetido deixou o parec de pé"


def test_a_volta_do_servidor_de_som_respeita_o_microfone_desligado(mundo: _Mundo) -> None:
    """D-2011-O-MICROFONE-DESLIGADO-NAO-ABRE-A-CAPTURA-DO-CABO: o canal volta; a captura não."""
    mundo.palavras[P[0]] = False
    mundo.palavras[P[1]] = True
    mundo.abrir(P[0])
    mundo.abrir(P[1])
    mundo.servidor.reiniciar()
    voltaram = canal_do_microfone.reerguer_o_que_sumiu(
        lancar=mundo.lancar, rodar=mundo.rodar, filtrar=lambda argv: _Processo(argv))
    assert sorted(voltaram) == sorted(P[:2]), "um canal ficou fora da volta"
    assert mundo.vivos(P[0]) == [], "a volta do servidor reabriu a captura do microfone desligado"
    assert len(mundo.vivos(P[1])) == 1, "a volta do servidor perdeu o microfone ligado"


def test_o_renomear_e_a_volta_do_controle_respeitam_a_palavra(mundo: _Mundo) -> None:
    """D-2011-O-MICROFONE-DESLIGADO-NAO-ABRE-A-CAPTURA-DO-CABO: renascer e voltar não reabrem."""
    mundo.palavras[P[0]] = False
    mundo.abrir(P[0])
    novo = canal_do_microfone.renomear(
        P[0], "Microfone do Controle 2", lancar=mundo.lancar, rodar=mundo.rodar,
        fabrica=lambda **kw: SourceVirtualPipeWire(runner=mundo.servidor, **kw))
    assert novo is not None and mundo.vivos() == [], "o renomear reabriu a captura"
    canal_do_microfone.fechar(P[0])
    mundo.abrir(P[0])
    assert mundo.vivos() == [], "o controle que voltou reabriu a captura"


def test_o_canal_do_radio_nao_ganha_alimentador_pela_palavra(mundo: _Mundo) -> None:
    """D-2011-O-MICROFONE-DESLIGADO-NAO-ABRE-A-CAPTURA-DO-CABO: no rádio quem enche é a ponte."""
    mundo.palavras[P[0]] = False
    mundo.abrir(P[0], fonte=None)
    canal_do_microfone.escrever_o_mudo(P[0], False, rodar=mundo.rodar, lancar=mundo.lancar)
    assert mundo.alimentadores == []


def test_os_quatro_na_mesa_misturada_cada_um_pela_propria_palavra(mundo: _Mundo) -> None:
    """D-2011-O-MICROFONE-DESLIGADO-NAO-ABRE-A-CAPTURA-DO-CABO: P1 a P4, cabo, rádio e o Edge."""
    mundo.palavras.update({P[0]: False, P[1]: True, P[2]: False, P[3]: False})
    for uniq, fonte in ((P[3], EDGE), (P[2], None), (P[1], CABO), (P[0], CABO)):
        mundo.abrir(uniq, fonte=fonte)
    assert [len(mundo.vivos(u)) for u in P] == [0, 1, 0, 0]
    canal_do_microfone.escrever_o_mudo(P[3], False, rodar=mundo.rodar, lancar=mundo.lancar)
    assert mundo.vivos(P[3])[0].argv[1] == f"--device={EDGE}", "o Edge não ergueu o próprio parec"
    canal_do_microfone.escrever_o_mudo(P[1], True, rodar=mundo.rodar, lancar=mundo.lancar)
    assert [len(mundo.vivos(u)) for u in P] == [0, 0, 0, 1], "o gesto de um controle mexeu em outro"


def test_o_gesto_pela_porta_da_palavra_ergue_e_derruba_na_hora(mundo: _Mundo) -> None:
    """D-2011-O-MICROFONE-DESLIGADO-NAO-ABRE-A-CAPTURA-DO-CABO: botão e tela, uma porta."""
    sub = bt_mic.BtMicSubsystem(gerenciador=SimpleNamespace(pontes={}, reconciliar=lambda _a: None))
    anteriores = eleicao_de_microfone.registrar_dizedor_do_no_ar(
        sub.no_ar, sub.esquecer_a_palavra, sub.palavra_no_ar)
    try:
        eleicao_de_microfone.dizer_no_ar(P[0], False)
        mundo.palavras[P[0]] = sub.palavra_no_ar(P[0])
        mundo.abrir(P[0])
        assert mundo.vivos() == []
        inicio = time.perf_counter()
        assert eleicao_de_microfone.dizer_no_ar(P[0], True) is True
        ligar_ms = (time.perf_counter() - inicio) * 1000
        assert len(mundo.vivos(P[0])) == 1, "o botão de ligar não ergueu o alimentador"
        inicio = time.perf_counter()
        eleicao_de_microfone.dizer_no_ar(P[0], False)
        desligar_ms = (time.perf_counter() - inicio) * 1000
        assert mundo.vivos(P[0]) == [], "o botão de desligar deixou a captura aberta"
        assert ligar_ms < 250 and desligar_ms < 250, (ligar_ms, desligar_ms)
    finally:
        eleicao_de_microfone.registrar_dizedor_do_no_ar(*anteriores)
