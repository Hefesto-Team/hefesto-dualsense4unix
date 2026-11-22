"""O botão do microfone não roda o `pactl` no laço, e o canal que sobe não segura a trava.

A palavra do microfone chega aos canais pelo `BtMicSubsystem` (`no_ar` e `esquecer_a_palavra`), e
cada escrita de mudo é um `pactl`. Quem a diz de dentro do laço do asyncio só pede: um fio próprio
escreve, lendo a palavra no instante da escrita. O `canal_do_microfone.abrir` guarda a `_TRANCA` só
para as tabelas: o `iniciar` do nó e o `pactl` do mudo correm longe das tabelas, e quem chega no
meio vê o canal ainda não publicado.

O `pactl` e o nó são de mentira e dormem; o tique do laço é o tempo que o chamador leva para voltar.

MORDIDAS: o `_escrever_o_mudo_nos_canais` de volta ao fio de quem diz a palavra reprova pela frase
«a palavra do microfone parou o laço»; a `_TRANCA` de volta em volta do `iniciar` reprova «o canal
que sobe parou o laço»; sem o `_seguir_a_palavra_que_mudou` a palavra dita na subida se perde.
"""
from __future__ import annotations

import asyncio
import io
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
    BtMicSubsystem,
    RegistroDePedidosDeCanal,
)
from hefesto_dualsense4unix.integrations import (
    canal_do_microfone,
    dualsense_bt_audio,
    microfone_filtrado,
)

MESA = ("aabbcc000011", "aabbcc000022", "aabbcc000033", "aabbcc000044")
CABO = "alsa_input.usb-fake-00.HiFi__Mic__source"
DORME_S = 0.3
TETO_DO_TIQUE_S = 0.02
FRASE_DA_PALAVRA = "a palavra do microfone parou o laço"
FRASE_DO_CANAL = "o canal que sobe parou o laço"


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


class _Source:
    construidas = 0
    dorme_ao_iniciar_s = 0.0
    iniciando = threading.Event()

    def __init__(self, *, nome: str, descricao: str, **_: object) -> None:
        type(self).construidas += 1
        self.nome = nome
        self.descricao = descricao

    def iniciar(self) -> bool:
        type(self).iniciando.set()
        time.sleep(type(self).dorme_ao_iniciar_s)
        return True

    def parar(self) -> None:
        return None


class _Pactl:
    """O `pactl` de mentira: guarda o mudo de cada nó, e dorme quando mandam."""

    def __init__(self) -> None:
        self.dorme_s = 0.0
        self.mudo_do_no: dict[str, str] = {}
        self.na_primeira_escrita: Any = None
        self._trava = threading.Lock()

    def __call__(self, argv: list[str]) -> bool:
        if argv[:2] == ["pactl", "set-source-mute"]:
            with self._trava:
                gancho, self.na_primeira_escrita = self.na_primeira_escrita, None
            if gancho is not None:
                gancho()
            time.sleep(self.dorme_s)
            self.mudo_do_no[argv[2]] = argv[3]
        return True


class _Mesa:
    def __init__(self, pactl: _Pactl) -> None:
        self.pactl = pactl
        self.sub = BtMicSubsystem(registro=RegistroDePedidosDeCanal())

    def abrir(self, uniq: str, *, cabo: bool = False) -> Any:
        return canal_do_microfone.abrir(
            uniq, "Microfone do Controle", fonte=CABO if cabo else None,
            fabrica=_Source, lancar=_Processo)

    def mudo(self, uniq: str) -> str | None:
        return self.pactl.mudo_do_no.get(canal_do_microfone.nome_do_canal(uniq))


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Mesa]:
    pactl = _Pactl()
    pronta = _Mesa(pactl)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(canal_do_microfone, "_rodar_pactl", pactl)
    monkeypatch.setattr(canal_do_microfone, "_lancar_processo", _Processo)
    monkeypatch.setattr(canal_do_microfone, "_passar_a_escolha_do_usuario", lambda *_a: None)
    monkeypatch.setattr(
        canal_do_microfone, "_a_palavra_do_usuario", pronta.sub.palavra_no_ar)
    monkeypatch.setattr(dualsense_bt_audio, "pactl_mudo", lambda: False)
    monkeypatch.setattr(microfone_filtrado, "abrir", lambda *_a, **_k: "")
    monkeypatch.setattr(_Source, "dorme_ao_iniciar_s", 0.0)
    monkeypatch.setattr(_Source, "construidas", 0)
    _Source.iniciando.clear()
    for uniq in list(canal_do_microfone.de_pe()):
        canal_do_microfone.fechar(uniq)
    yield pronta
    pronta.sub.esperar_o_mudo_dos_canais(10.0)
    for uniq in list(canal_do_microfone.de_pe()):
        canal_do_microfone.fechar(uniq)


def _sobe_a_mesa(mesa: _Mesa) -> None:
    for i, uniq in enumerate(MESA):
        mesa.abrir(uniq, cabo=i < 2)
    assert set(canal_do_microfone.de_pe()) == set(MESA)


class TestAPalavraNaoParaOLaco:
    def test_dois_apertos_voltam_na_hora_e_o_mudo_final_e_o_da_ultima_palavra(
        self, mesa: _Mesa
    ) -> None:
        """D-2211-A-PALAVRA-DO-MUDO-SAI-DO-FIO-DO-LACO."""
        _sobe_a_mesa(mesa)
        mesa.pactl.dorme_s = DORME_S
        a, b = MESA[0], MESA[3]

        async def apertos() -> float:
            inicio = time.perf_counter()
            mesa.sub.no_ar(a, False)
            mesa.sub.no_ar(a, True)
            mesa.sub.no_ar(b, False)
            return time.perf_counter() - inicio

        tique = asyncio.run(apertos())
        assert tique < TETO_DO_TIQUE_S, f"{FRASE_DA_PALAVRA}: {tique * 1000:.0f} ms"
        assert mesa.sub.esperar_o_mudo_dos_canais(15.0)
        assert mesa.mudo(b) == "1"
        assert mesa.mudo(a) == "0", "o mudo final de A não é o da última palavra dele"
        assert mesa.mudo(MESA[1]) == "0" and mesa.mudo(MESA[2]) == "0"

    def test_esquecer_a_palavra_tambem_volta_na_hora(self, mesa: _Mesa) -> None:
        _sobe_a_mesa(mesa)
        a = MESA[2]
        mesa.sub.no_ar(a, False)
        assert mesa.mudo(a) == "1"
        mesa.pactl.dorme_s = DORME_S

        async def esquece() -> float:
            inicio = time.perf_counter()
            mesa.sub.esquecer_a_palavra(a)
            return time.perf_counter() - inicio

        tique = asyncio.run(esquece())
        assert tique < TETO_DO_TIQUE_S, f"{FRASE_DA_PALAVRA}: {tique * 1000:.0f} ms"
        assert mesa.sub.esperar_o_mudo_dos_canais(15.0)
        assert mesa.mudo(a) == "0"

    def test_fora_do_laco_a_palavra_chega_ao_no_na_hora(self, mesa: _Mesa) -> None:
        _sobe_a_mesa(mesa)
        mesa.sub.no_ar(MESA[1], False)
        assert mesa.mudo(MESA[1]) == "1"


class TestOCanalQueSobeNaoSegura:
    def test_o_laco_chama_de_pe_no_meio_do_iniciar_e_nao_espera(self, mesa: _Mesa) -> None:
        _Source.dorme_ao_iniciar_s = 0.4
        subiu = threading.Thread(target=mesa.abrir, args=(MESA[0],), daemon=True)
        subiu.start()
        assert _Source.iniciando.wait(5.0)
        inicio = time.perf_counter()
        visto = canal_do_microfone.de_pe()
        tique = time.perf_counter() - inicio
        assert tique < TETO_DO_TIQUE_S, f"{FRASE_DO_CANAL}: {tique * 1000:.0f} ms"
        assert MESA[0] not in visto, "o canal apareceu publicado antes de subir"
        subiu.join(10.0)
        assert MESA[0] in canal_do_microfone.de_pe()

    def test_o_pactl_do_mudo_do_nascimento_tambem_corre_fora_da_trava(self, mesa: _Mesa) -> None:
        mesa.pactl.dorme_s = 0.4
        subiu = threading.Thread(target=mesa.abrir, args=(MESA[1],), daemon=True)
        subiu.start()
        time.sleep(0.1)
        inicio = time.perf_counter()
        canal_do_microfone.de_pe()
        tique = time.perf_counter() - inicio
        assert tique < TETO_DO_TIQUE_S, f"{FRASE_DO_CANAL}: {tique * 1000:.0f} ms"
        subiu.join(10.0)
        assert mesa.mudo(MESA[1]) == "0"

    def test_dois_abrir_do_mesmo_controle_sobem_um_canal_so(self, mesa: _Mesa) -> None:
        _Source.dorme_ao_iniciar_s = 0.3
        fontes: list[Any] = []
        fios = [
            threading.Thread(target=lambda: fontes.append(mesa.abrir(MESA[2])), daemon=True)
            for _ in range(2)
        ]
        for fio in fios:
            fio.start()
        for fio in fios:
            fio.join(10.0)
        assert _Source.construidas == 1, "o mesmo controle subiu dois canais"
        assert len(fontes) == 2 and fontes[0] is fontes[1]

    def test_a_palavra_dita_durante_a_subida_chega_ao_no_publicado(self, mesa: _Mesa) -> None:
        a = MESA[3]
        durante = threading.Event()

        def diz_calado_no_meio() -> None:
            mesa.sub.no_ar(a, False)
            durante.set()

        mesa.pactl.dorme_s = 0.3
        mesa.pactl.na_primeira_escrita = lambda: threading.Thread(
            target=diz_calado_no_meio, daemon=True).start()
        mesa.abrir(a)
        assert durante.wait(5.0)
        assert mesa.mudo(a) == "1", "a palavra dita enquanto o canal subia se perdeu"
