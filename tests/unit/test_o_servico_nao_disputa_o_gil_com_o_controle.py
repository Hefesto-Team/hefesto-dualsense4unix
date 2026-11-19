"""O-SERVICO-NAO-DISPUTA-O-GIL-COM-O-CONTROLE-01: o trabalho de vazão não prende o GIL por amostra.

O DSP do tato e do rumble passa o bloco inteiro de uma vez (o número de chamadas Python não
cresce com as amostras); a varredura do ``/proc`` só abre o ambiente do processo novo; a lista
dos perfis não copia fundo o perfil que não mudou.

AS MORDIDAS (executadas, uma a uma, com o md5 conferido na volta):

* o ``misturar_o_toque`` amostra por amostra → ``test_o_dsp_nao_anda_amostra_por_amostra``;
* o ``_Biquad.passar`` de uma amostra → ``test_o_dsp_nao_anda_amostra_por_amostra``;
* o ``pids_de_jogo`` sem a memória por programa → ``test_a_varredura_so_abre_o_processo_novo``;
* o ``list_profiles`` pelo ``load_all_profiles`` → ``test_a_lista_dos_perfis_nao_copia_fundo``.
"""
from __future__ import annotations

import math
import os
import random
import sys
from array import array
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import quem_o_jogo_le as q
from hefesto_dualsense4unix.profiles import formas_de_haptica as fh
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.testing import FakeController

AMOSTRAS = 4800


def _chamadas(f: Callable[[], object]) -> int:
    """Quantas chamadas, Python e C, a função faz: o laço por amostra faz uma por amostra."""
    contadas = [0]

    def contar(_quadro: Any, _evento: str, _arg: Any) -> None:
        contadas[0] += 1

    sys.setprofile(contar)
    try:
        f()
    finally:
        sys.setprofile(None)
    return contadas[0]


def test_o_dsp_nao_anda_amostra_por_amostra() -> None:
    """D-1911-O-TRABALHO-DE-VAZAO-NAO-PRENDE-O-GIL: menos de uma chamada a cada 4 amostras."""
    bloco = bytes(AMOSTRAS * 16)
    toque = array("f", [0.3 * math.sin(i / 7) for i in range(AMOSTRAS)])
    pcm = array("h", [int(8000 * math.sin(i / 30)) for i in range(2 * AMOSTRAS)]).tobytes()
    padrao = tv.padrao_de({"golpes": [[0, 120, 80, 0.8], [100, 200, 160, 0.6]], "repete": True})
    filtro, teto = fh.FiltroDoCorpo(), fh.TetoDoCorpo()
    casos: dict[str, Callable[[], object]] = {
        "misturar_o_toque": lambda: eh.misturar_o_toque(bloco, toque, 0, (2, 3)),
        "FiltroDoCorpo.processar": lambda: filtro.processar(pcm),
        "TetoDoCorpo.passar": lambda: teto.passar(toque),
        "amostras_de": lambda: tv.amostras_de(padrao, 50.0, AMOSTRAS, 0.8, 120.0),
    }
    caras = {nome: _chamadas(f) for nome, f in casos.items()}
    assert all(n < AMOSTRAS / 4 for n in caras.values()), caras


def _recursao(biquad: fh._Biquad, x: list[float]) -> list[float]:
    x1 = x2 = y1 = y2 = 0.0
    saida = []
    for v in x:
        y = biquad.b0 * v + biquad.b1 * x1 + biquad.b2 * x2 - biquad.a1 * y1 - biquad.a2 * y2
        x2, x1, y2, y1 = x1, v, y1, y
        saida.append(y)
    return saida


@pytest.mark.parametrize("tipo,corte", [("passa-alta", fh.CORTE_BAIXO_HZ),
                                        ("passa-baixa", fh.CORTE_ALTO_HZ)])
def test_o_filtro_em_bloco_e_a_recursao_de_sempre(tipo: str, corte: int) -> None:
    """D-1911-O-TRABALHO-DE-VAZAO-NAO-PRENDE-O-GIL: pedaços de todo tamanho, a mesma saída."""
    sorte = random.Random(19)
    x = [sorte.uniform(-1.0, 1.0) for _ in range(3000)]
    esperado = _recursao(fh._Biquad(tipo, corte, fh.TAXA), x)
    biquad, saida, de = fh._Biquad(tipo, corte, fh.TAXA), [], 0
    for tamanho in (1, 2, 255, 256, 257, 480, 1, 999, 749):
        saida.extend(biquad.passar(np.array(x[de:de + tamanho])).tolist())
        de += tamanho
    assert de == len(x)
    assert max(abs(a - b) for a, b in zip(esperado, saida, strict=True)) < 1e-9


def _proc(base: Path, processos: dict[int, tuple[str, bool]]) -> Path:
    for pid, (programa, jogo) in processos.items():
        pasta = base / str(pid)
        pasta.mkdir(parents=True, exist_ok=True)
        env = f"{q.ENV_DO_JOGO}=/prefixo\0HOME=/x\0" if jogo else "HOME=/x\0"
        (pasta / "environ").write_bytes(env.encode())
        exe = pasta / "exe"
        if exe.is_symlink():
            exe.unlink()
        exe.symlink_to(programa)
    return base


@pytest.fixture
def ambientes_abertos(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    abertos: list[str] = []
    bruto = q._bruto

    def contar(caminho: str) -> bytes:
        if caminho.endswith("/environ"):
            abertos.append(caminho)
        return bruto(caminho)

    monkeypatch.setattr(q, "_bruto", contar)
    yield abertos


def test_a_varredura_so_abre_o_processo_novo(
    tmp_path: Path, ambientes_abertos: list[str]
) -> None:
    """D-1911-O-TRABALHO-DE-VAZAO-NAO-PRENDE-O-GIL: o ambiente se lê no processo novo e no exec."""
    base = _proc(tmp_path / "proc", {11: ("/jogo", True), 22: ("/bash", False)})
    assert q.pids_de_jogo(base) == {11}
    assert len(ambientes_abertos) == 2
    ambientes_abertos.clear()
    assert q.pids_de_jogo(base) == {11}
    assert ambientes_abertos == [], "a varredura sem processo novo releu o ambiente de todos"
    _proc(base, {22: ("/wine64", True), 33: ("/outro", False)})
    assert q.pids_de_jogo(base) == {11, 22}, "o exec de um processo não se viu"
    assert sorted(ambientes_abertos) == [f"{base}/22/environ", f"{base}/33/environ"]


@pytest.fixture
def perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def pasta(ensure: bool = False) -> Path:
        return alvo

    monkeypatch.setattr(loader, "profiles_dir", pasta)
    loader.ligar_a_leitura_pela_assinatura()
    try:
        yield alvo
    finally:
        loader.desligar_a_leitura_pela_assinatura()


def test_a_lista_dos_perfis_nao_copia_fundo(perfis_isolados: Path) -> None:
    """D-1911-O-TRABALHO-DE-VAZAO-NAO-PRENDE-O-GIL: o perfil que não mudou volta o mesmo."""
    loader.save_profile(Profile(name="corrida", match=MatchCriteria(window_class=["corrida"])))
    for arquivo in perfis_isolados.glob("*.json"):
        os.utime(arquivo, (1_700_000_000, 1_700_000_000))
    gerente = ProfileManager(controller=FakeController())
    antes = {p.name: p for p in gerente.list_profiles()}
    depois = {p.name: p for p in gerente.list_profiles()}
    assert "corrida" in depois
    assert depois["corrida"] is antes["corrida"], "cada profile.list copiou fundo cada perfil"
