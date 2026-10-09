#!/usr/bin/env python3
"""O-ESTILO-DO-PERFIL-LIGA-O-MOTOR-DO-TATO-01 — o estilo guardado liga o motor.

O motor do tato só age com receita, e a receita só existia em dicionários de
teste: o `Profile` real não guardava o estilo, e o vocabulário do estilo
(`toque_por_tiro`, luz `respira`/`pisca`) não era o do motor. Estas réguas usam o
`Profile` DE VERDADE. Vale para P1 a P4, cabo e rádio: o perfil é um só.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.profiles import estilos_de_jogo as ej
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

_RAIZ = Path(__file__).resolve().parents[2]


def _perfil(**campos: Any) -> Profile:
    return Profile(name="Pragmata", match=MatchAny(), **campos)


def test_o_fps_guardado_liga_o_motor_com_as_quatro_reacoes() -> None:
    receita = tv.receita_do_perfil(_perfil(estilo="fps"))
    assert receita.ligada
    assert receita.vibracao_por_tiro
    assert receita.lado_do_som
    assert receita.reacao_ao_tiro == "pulsa"
    assert receita.gatilho_no_ritmo
    assert receita.forca_do_toque == tv.FORCA_DO_DEGRAU["max"]
    assert receita.som_no_controle is False


def test_sem_estilo_o_motor_fica_desligado() -> None:
    assert tv.receita_do_perfil(_perfil()) == tv.DESLIGADA
    assert tv.receita_do_perfil(_perfil(estilo="personalizado")) == tv.DESLIGADA


def test_o_desvio_da_bancada_sobrepoe_so_o_seu_campo() -> None:
    do_estilo = tv.receita_do_perfil(_perfil(estilo="fps"))
    com_desvio = tv.receita_do_perfil(
        _perfil(estilo="fps", receita_do_tato={"som_no_controle": True}))
    assert com_desvio.som_no_controle is True
    assert com_desvio == tv.Receita(**{**do_estilo.__dict__, "som_no_controle": True})


def test_o_desvio_respeita_os_limites_do_motor() -> None:
    receita = tv.receita_do_perfil(
        _perfil(estilo="fps", receita_do_tato={"duracao_do_toque_ms": 900}))
    assert receita.duracao_do_toque_ms == 60


@pytest.mark.parametrize("estilo", ej.ESTILOS, ids=lambda e: e.chave)
def test_todo_estilo_se_traduz_numa_receita(estilo: ej.Estilo) -> None:
    receita = tv.receita_do_estilo(estilo)
    assert isinstance(receita, tv.Receita)
    assert receita.reacao_ao_tiro in tv.REACOES_DA_LUZ
    assert receita.gatilho_no_ritmo == (estilo.chave in tv.ESTILOS_DE_RAJADA)
    assert tv.receita_do_perfil(_perfil(estilo=estilo.chave)) == receita


def test_o_gatilho_no_ritmo_e_so_da_arma_de_rajada() -> None:
    assert tv.receita_do_perfil(_perfil(estilo="corrida")).gatilho_no_ritmo is False


def test_estilo_que_saiu_do_produto_nao_quebra_o_perfil() -> None:
    """O «Co-op local» saiu em 25/09: a chave que sobra carrega, e o motor fica desligado."""
    relido = Profile.model_validate(
        loader._payload_do_perfil(_perfil(estilo="coop",
                                          receita_do_tato={"toque_por_tiro": True})))
    assert tv.receita_do_perfil(relido) == tv.DESLIGADA


def test_perfil_sem_estilo_sai_do_disco_como_era() -> None:
    payload = loader._payload_do_perfil(_perfil())
    assert "estilo" not in payload
    assert tv.CAMPO_DA_RECEITA not in payload
    assert "estilo" not in _perfil().model_dump()


def test_o_perfil_ativo_com_estilo_liga_o_passo_do_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mordida: sem a tradução, o perfil com `estilo="fps"` deixa o motor desligado."""
    monkeypatch.setattr(loader, "load_profile", lambda nome: _perfil(estilo="fps"))
    daemon = SimpleNamespace(store=SimpleNamespace(active_profile="Pragmata"))
    motor = tv.TatoVivo()
    tv.Passo(daemon, motor)(0.0)
    assert motor.ligado is True


def _ensaio() -> Any:
    caminho = _RAIZ / "scripts" / "ensaios" / "o_tato_vivo_x_ou_y.py"
    spec = importlib.util.spec_from_file_location("o_tato_vivo_x_ou_y", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_o_ensaio_recusa_sem_medir_e_grava_com_ele(capsys: pytest.CaptureFixture[str]) -> None:
    ensaio = _ensaio()
    loader.save_profile(_perfil(estilo="fps"))
    argv = ["--perfil", "Pragmata", "--campo", "gatilho_no_ritmo", "--valor", "false"]
    assert ensaio.main(argv) == ensaio.RC_RECUSA
    assert loader.load_profile("Pragmata").receita_do_tato is None

    assert ensaio.main([*argv, "--medir"]) == ensaio.RC_OK
    relido = loader.load_profile("Pragmata")
    assert relido.receita_do_tato == {"gatilho_no_ritmo": False}
    assert tv.receita_do_perfil(relido).gatilho_no_ritmo is False

    assert ensaio.main(["--perfil", "Pragmata", "--campo", "gatilho_no_ritmo",
                        "--tirar", "--medir"]) == ensaio.RC_OK
    assert loader.load_profile("Pragmata").receita_do_tato is None
    capsys.readouterr()
    assert ensaio.main(["--perfil", "Pragmata", "--mostrar"]) == ensaio.RC_OK
    linhas = capsys.readouterr().out.splitlines()
    for campo in tv.CAMPOS_DA_RECEITA:
        assert any(linha.startswith(f"{campo} = ") for linha in linhas), campo


def test_o_gesto_da_aba_perfis_grava_o_estilo(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis

    guardado: dict[str, Profile] = {"perfil": _perfil()}

    def _save(prof: Profile, *a: Any, **kw: Any) -> None:
        guardado["perfil"] = prof

    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [guardado["perfil"]])
    monkeypatch.setattr(loader, "load_profile", lambda nome, *a, **k: guardado["perfil"])
    monkeypatch.setattr(loader, "save_profile", _save)
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "Pragmata", raising=False)
    monkeypatch.setattr(a10_perfis, "_DESFECHO", None, raising=False)

    class _Ponte:
        def profile_switch(self, nome: str) -> bool:
            return True

        def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
            return True

        def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
            return {}

    ctx = Contexto(state={"active_profile": None}, mesa=[], conectados=[], estados={})
    a10_perfis.editor_estilo(ctx, {"valor": "FPS"}, _Ponte())
    gravado = guardado["perfil"]
    assert gravado.estilo == "fps"
    relido = Profile.model_validate(loader._payload_do_perfil(gravado))
    assert relido.estilo == "fps"
    assert tv.receita_do_perfil(relido).ligada
