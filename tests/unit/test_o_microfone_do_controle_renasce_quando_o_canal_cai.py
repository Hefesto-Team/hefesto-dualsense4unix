"""O microfone do controle renasce quando o canal cai (O-MICROFONE-DO-CONTROLE-RENASCE-...).

O servidor de som é o de mentira: guarda os módulos que o ``load-module`` criou, cria o fifo de
cada um com o leitor aberto, e ``reiniciar()`` leva tudo, como o ``systemctl --user restart
pipewire-pulse``. A source é a ``SourceVirtualPipeWire`` real, e o alimentador e o filtro são
processos de mentira. A pergunta é sempre ao servidor, e o servidor mudo é «não sei».

MORDIDAS: ``no_ar`` que responde ``True`` sem perguntar reprova a volta do módulo; ``voz_no_ar``
que olha só o processo reprova a voz que some com o canal de pé; sem ``terminou_sozinha`` e sem a
comparação do ``uniq`` a ponte morta fica na tabela; tirar o passo ``canais`` da volta do
``BtMicSubsystem`` reprova a volta do canal pelo laço.
"""
from __future__ import annotations

import io
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from structlog.testing import capture_logs

from hefesto_dualsense4unix.daemon.subsystems import bt_mic
from hefesto_dualsense4unix.integrations import (
    canal_do_microfone,
    dualsense_bt_audio,
    microfone_filtrado,
)
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    GerenciadorMicBluetooth,
    NoDualSenseBT,
    PonteMicBluetooth,
    SourceVirtualPipeWire,
)

P = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")
CABO = "alsa_input.usb-fake-00.HiFi__Mic__source"


class _Servidor:
    """O pipewire-pulse de mentira: módulos, fontes, e o mudo que não responde."""

    def __init__(self) -> None:
        self.modulos: dict[str, str] = {}
        self.fontes: set[str] = set()
        self.carregados = 0
        self.descarregados = 0
        self.mudo = False
        self._proximo = 20
        self._leitores: list[int] = []

    def reiniciar(self) -> None:
        self.modulos.clear()
        self.fontes.clear()
        self._proximo = 7
        for fd in self._leitores:
            os.close(fd)
        self._leitores.clear()

    def fechar(self) -> None:
        self.reiniciar()

    def __call__(self, argv: list[str]) -> str | None:
        if self.mudo:
            return None
        if argv[:4] == ["pactl", "list", "modules", "short"]:
            return "".join(
                f"{i}\tmodule-pipe-source\t{args}\n" for i, args in self.modulos.items())
        if argv[:4] == ["pactl", "list", "sources", "short"]:
            return "".join(f"{i}\t{n}\tPipeWire\ts16le\tIDLE\n" for i, n in enumerate(self.fontes))
        if argv[:2] == ["pactl", "load-module"]:
            args = " ".join(argv[3:])
            fifo = next(a[5:] for a in argv if a.startswith("file="))
            os.mkfifo(fifo)
            self._leitores.append(os.open(fifo, os.O_RDONLY | os.O_NONBLOCK))
            ident = str(self._proximo)
            self._proximo += 1
            self.modulos[ident] = args
            self.carregados += 1
            return ident + "\n"
        if argv[:2] == ["pactl", "unload-module"]:
            self.descarregados += 1
            self.modulos.pop(argv[2], None)
            return ""
        return ""


def _fonte_no_ar(nome: str) -> bool | None:
    canal = canal_do_microfone.canal_de_pe(P[0])
    return None if canal is None else canal.fonte_no_ar(nome)


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
        self.filtros: list[_Processo] = []

    def lancar_alimentador(self, argv: list[str]) -> _Processo:
        proc = _Processo(argv)
        self.alimentadores.append(proc)
        return proc

    def lancar_filtro(self, argv: list[str]) -> _Processo:
        proc = _Processo(argv)
        self.filtros.append(proc)
        return proc

    def abrir(self, uniq: str, fonte: str | None = CABO, *, voz: bool = True) -> Any:
        canal = canal_do_microfone.abrir(
            uniq, "Microfone do Controle 1", fonte=fonte, lancar=self.lancar_alimentador,
            rodar=lambda _a: True, filtrar=self.lancar_filtro,
            fabrica=lambda **kw: SourceVirtualPipeWire(runner=self.servidor, **kw))
        if voz:
            self.publicar_a_voz(uniq)
        return canal

    def publicar_a_voz(self, uniq: str) -> None:
        self.servidor.fontes.add(microfone_filtrado.nome_da_voz(canal_do_microfone.nome_do_canal(uniq)))

    def reerguer(self) -> list[str]:
        return canal_do_microfone.reerguer_o_que_sumiu(
            lancar=self.lancar_alimentador, rodar=lambda _a: True, filtrar=self.lancar_filtro)


@pytest.fixture
def mundo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Mundo]:
    servidor = _Servidor()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/pipewire")
    monkeypatch.setattr(canal_do_microfone, "_passar_a_escolha_do_usuario", lambda *_a: None)
    monkeypatch.setattr(canal_do_microfone, "_a_palavra_do_usuario", lambda _u: None)
    pronto = _Mundo(servidor)
    monkeypatch.setattr(microfone_filtrado, "_lancar_processo", pronto.lancar_filtro)
    microfone_filtrado.fechar_todos()
    for uniq in list(canal_do_microfone.de_pe()):
        canal_do_microfone.fechar(uniq)
    yield pronto
    for uniq in list(canal_do_microfone.de_pe()):
        canal_do_microfone.fechar(uniq)
    microfone_filtrado.fechar_todos()
    servidor.fechar()


def test_o_servidor_reiniciado_leva_o_modulo_e_a_volta_o_devolve(mundo: _Mundo) -> None:
    """D-1911-O-MICROFONE-RENASCE-QUANDO-O-CANAL-CAI: o canal perdido volta com a voz e o cabo."""
    canal: Any = mundo.abrir(P[0])
    assert canal.no_ar() is True and mundo.servidor.carregados == 1
    mundo.servidor.reiniciar()
    assert canal.no_ar() is False, "o canal seguiu de pé pela memória"
    assert mundo.reerguer() == [P[0]]
    assert mundo.servidor.carregados == 2, "a volta não pediu o load-module"
    assert canal.no_ar() is True
    assert canal.escrever(b"\x00\x00"), "o fifo novo não aceita a voz"
    assert canal_do_microfone.canal_de_pe(P[0]) is canal, "o canal renasceu em outro objeto"
    assert len(mundo.alimentadores) == 2, "o alimentador do cabo não voltou"
    assert len(mundo.filtros) == 2, "o filtro da voz não voltou"
    assert mundo.reerguer() == [], "o canal que já voltou não volta de novo"


def test_o_servidor_mudo_e_nao_sei_e_nada_se_refaz(mundo: _Mundo) -> None:
    """D-1911-O-MICROFONE-RENASCE-QUANDO-O-CANAL-CAI: sem resposta do servidor nada é pedido."""
    canal = mundo.abrir(P[0])
    mundo.servidor.reiniciar()
    mundo.servidor.mudo = True
    assert canal.no_ar() is None
    assert mundo.reerguer() == []
    assert (mundo.servidor.carregados, mundo.servidor.descarregados) == (1, 0)
    assert len(mundo.alimentadores) == 1 and len(mundo.filtros) == 1
    mundo.servidor.mudo = False
    assert mundo.reerguer() == [P[0]], "o servidor voltou e o canal não"


def test_o_canal_de_pe_no_servidor_nao_e_tocado(mundo: _Mundo) -> None:
    """D-1911-O-MICROFONE-RENASCE-QUANDO-O-CANAL-CAI: com o módulo no servidor nada se refaz."""
    mundo.abrir(P[0])
    mundo.abrir(P[1])
    assert mundo.reerguer() == []
    assert mundo.servidor.carregados == 2 and len(mundo.filtros) == 2


def test_a_voz_que_some_com_o_canal_de_pe_volta_so_a_voz(mundo: _Mundo) -> None:
    """D-1911-O-MICROFONE-RENASCE-QUANDO-O-CANAL-CAI: o filtro confere o nó, não só o processo."""
    mundo.abrir(P[0])
    assert microfone_filtrado.voz_no_ar(P[0], _fonte_no_ar) is True
    mundo.servidor.fontes.clear()
    voz = microfone_filtrado.voz_no_ar(P[0], _fonte_no_ar)
    assert voz is False, "o processo vivo escondeu o nó que sumiu"
    assert mundo.reerguer() == []
    assert len(mundo.filtros) == 2, "a voz não voltou"
    assert mundo.servidor.carregados == 1, "o canal que estava de pé foi refeito"
    mundo.publicar_a_voz(P[0])
    assert microfone_filtrado.voz_no_ar(P[0], _fonte_no_ar) is True
    mundo.filtros[1].codigo = 1
    assert microfone_filtrado.voz_no_ar(P[0], _fonte_no_ar) is False
    mundo.reerguer()
    assert len(mundo.filtros) == 3, "o processo morto não foi refeito"


def test_a_voz_que_ainda_nao_apareceu_nao_e_refeita(mundo: _Mundo) -> None:
    """D-1911-O-MICROFONE-RENASCE-QUANDO-O-CANAL-CAI: o filtro que sobe não é derrubado a meio."""
    mundo.abrir(P[0], voz=False)
    assert microfone_filtrado.voz_no_ar(P[0], _fonte_no_ar) is None
    mundo.reerguer()
    assert len(mundo.filtros) == 1


def _volta_do_laco(monkeypatch: pytest.MonkeyPatch) -> tuple[bt_mic.BtMicSubsystem, list[str]]:
    sub = bt_mic.BtMicSubsystem(gerenciador=SimpleNamespace(pontes={}, reconciliar=lambda _a: None))
    vistos: list[str] = []
    monkeypatch.setattr(dualsense_bt_audio, "nos_dualsense_bluetooth", lambda: [])
    for nome in ("_esquecer_quem_saiu_da_mesa", "_soltar_os_que_o_usuario_desmarcou",
                 "_reconciliar_o_cabo", "_refazer_quem_esperava_o_canal",
                 "_aplicar_a_palavra_do_usuario", "_varrer_os_orfaos",
                 "_renomear_os_canais_velhos", "_devolver_a_fonte_padrao"):
        monkeypatch.setattr(sub, nome, lambda *_a: None)

    def conferir() -> list[str]:
        vistos.append("a")
        return []

    monkeypatch.setattr(canal_do_microfone, "reerguer_o_que_sumiu", conferir)
    return sub, vistos


def test_a_volta_do_microfone_confere_os_canais_de_pe(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-O-MICROFONE-RENASCE-QUANDO-O-CANAL-CAI: cada volta confere os canais."""
    sub, vistos = _volta_do_laco(monkeypatch)
    sub._volta(sub._gerenciador)
    sub._volta(sub._gerenciador)
    assert vistos == ["a", "a"]


def _no(caminho: str, uniq: str) -> NoDualSenseBT:
    return NoDualSenseBT(caminho=caminho, uniq=uniq, produto=0x0CE6)


class _Decodificador:
    def decodificar(self, _quadro: bytes) -> None:
        return None


class _SourceDaPonte:
    nome = "hefesto_mic_ponte"
    descartes = 0

    def iniciar(self) -> bool:
        return True

    def estado(self) -> None:
        return None

    def escrever(self, _pcm: bytes) -> bool:
        return True

    def parar(self) -> None:
        return None


def _ponte_real(no: NoDualSenseBT, fechadas: list[int]) -> PonteMicBluetooth:
    """A ponte de verdade; o hidraw é um cano cuja ponta de escrita já fechou (leitura vazia)."""
    leitura, escrita = os.pipe()
    os.close(escrita)
    fechadas.append(leitura)
    return PonteMicBluetooth(
        no, opener=lambda _c: leitura, decodificador=_Decodificador(), source=_SourceDaPonte())


def _esperar_a_thread(ponte: PonteMicBluetooth) -> None:
    thread = ponte._thread
    assert thread is not None
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_a_ponte_do_radio_que_morre_sozinha_sai_e_outra_sobe_com_um_aviso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-O-MICROFONE-RENASCE-QUANDO-O-CANAL-CAI: a thread morta sem pedido vira ponte nova."""
    fds: list[int] = []
    criadas: list[PonteMicBluetooth] = []

    def fabrica(no: NoDualSenseBT) -> PonteMicBluetooth:
        ponte = _ponte_real(no, fds)
        criadas.append(ponte)
        return ponte

    gerenciador = GerenciadorMicBluetooth(fabrica=fabrica)
    nos = [_no("/dev/hidraw7", P[0])]
    with capture_logs() as diario:
        gerenciador.reconciliar(nos)
        primeira = criadas[0]
        _esperar_a_thread(primeira)
        assert primeira.terminou_sozinha()
        for _ in range(2):
            gerenciador.reconciliar(nos)
            _esperar_a_thread(criadas[-1])
    assert len(criadas) == 3, "a ponte morta ficou na tabela"
    assert criadas[0].terminou_sozinha() is False, "a ponte velha não foi parada"
    avisos = [e for e in diario if e.get("event") == "bt_mic_ponte_caiu"]
    assert len(avisos) == 2 and {a["motivo"] for a in avisos} == {"terminou"}
    gerenciador.parar()


def test_o_caminho_reaproveitado_por_outro_controle_troca_a_ponte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-1911-O-MICROFONE-RENASCE-QUANDO-O-CANAL-CAI: o uniq novo no mesmo hidraw nunca herda."""
    paradas: list[str] = []

    class _Ponte:
        def __init__(self, no: NoDualSenseBT) -> None:
            self.no = no

        def iniciar(self) -> bool:
            return True

        def terminou_sozinha(self) -> bool:
            return False

        def parar(self) -> None:
            paradas.append(self.no.uniq)

    gerenciador = GerenciadorMicBluetooth(fabrica=_Ponte)
    gerenciador.reconciliar([_no("/dev/hidraw7", P[0])])
    with capture_logs() as diario:
        gerenciador.reconciliar([_no("/dev/hidraw7", P[0].upper())])
        assert paradas == [], "o mesmo controle, escrito de outro jeito, foi derrubado"
        gerenciador.reconciliar([_no("/dev/hidraw7", P[1])])
    assert paradas == [P[0]]
    assert [p.no.uniq for p in gerenciador.pontes.values()] == [P[1]]
    avisos = [e for e in diario if e.get("event") == "bt_mic_ponte_caiu"]
    assert [a["motivo"] for a in avisos] == ["outro_controle"]
