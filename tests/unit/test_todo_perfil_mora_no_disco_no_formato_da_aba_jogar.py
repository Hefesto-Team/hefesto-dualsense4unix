"""TODO-PERFIL-MORA-NO-DISCO-NO-FORMATO-DA-ABA-JOGAR-01 — o modo de todo perfil num formato só.

Medido em 31/10/2026 em 59 perfis de uma máquina real: 22 com o par (caminho, máscara), 10 com
o ``mode`` sem o caminho, 4 sem ``mode`` e com a ponte carimbada, 23 sem os dois, e 16 com a
``controllers.<uniq>.mascara`` de antes da D-2710. A migração da máscara morava só na leitura, e
a escada carimbava a ponte sem o ``mode`` (``ponte_confirmada … modo_alinhado=False``): o
lançamento lia a ponte e a aba Jogar, o ``mode``.

O ENSAIO: os perfis moram no ``XDG_CONFIG_HOME`` do teste (o ``conftest`` isola), escritos crus
no disco como uma versão antiga os deixou, e o disco é lido de novo depois de cada passo. A
escada é a real (``launch_env.tique_da_escada``); só a borda do daemon é dublada.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.integrations import ponte_escada, ponte_tentativa
from hefesto_dualsense4unix.integrations.virtual_pad import MODOS, par_do_modo
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import secao_do_modo_com_o_caminho
from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

APPID = 9931107
MODIFICADO_EM = "2026-10-01T12:00:00-03:00"
P1, P2, P3 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03"


def _cru(nome: str, appid: int, **resto: Any) -> dict[str, Any]:
    return {
        "name": nome,
        "match": {"type": "criteria", "window_class": [f"steam_app_{appid}"]},
        "priority": 80,
        "modificado_em": MODIFICADO_EM,
        **resto,
    }


OS_FORMATOS: dict[str, dict[str, Any]] = {
    "sem_caminho": _cru("Sem Caminho", 9931001, mode={"kind": "gamepad", "gamepad_flavor": "xbox"}),
    "caminho_sem_mascara": _cru(
        "Caminho Sem Mascara", 9931002, mode={"kind": "gamepad", "gamepad_flavor": None,
                                              "caminho": "dualsense"}),
    "mascara_por_controle": _cru(
        "Mascara Por Controle", 9931003,
        mode={"kind": "gamepad", "gamepad_flavor": None, "caminho": "xbox"},
        controllers={P1: {"mascara": "dualsense"}, P2: {"mascara": "xbox"},
                     P3: {"mascara": "dualsense", "leds": {"lightbar": [1, 2, 3]}}}),
    "mascara_sem_mode": _cru(
        "Mascara Sem Mode", 9931004, controllers={P1: {"mascara": "nintendo"}}),
    "desktop_com_mascara": _cru(
        "Desktop Com Mascara", 9931005, mode={"kind": "desktop", "gamepad_flavor": None},
        controllers={P1: {"mascara": "xbox"}}),
    "ponte_sem_mode": _cru(
        "Ponte Sem Mode", 9931006,
        ponte={"kind": "gamepad", "gamepad_flavor": "dualsense", "steam_input": False,
               "confirmada_por": "silencio", "confirmada_em": "2026-10-31T05:29:05-03:00"}),
    "ponte_nativa_sem_mode": _cru(
        "Ponte Nativa Sem Mode", 9931007,
        ponte={"kind": "native", "gamepad_flavor": None, "steam_input": False,
               "confirmada_por": "silencio"}),
    "gamepad_sem_par": _cru(
        "Gamepad Sem Par", 9931013, mode={"kind": "gamepad", "gamepad_flavor": None}),
}

OS_QUE_FICAM: dict[str, dict[str, Any]] = {
    "sem_mode_sem_ponte": _cru("Sem Mode Sem Ponte", 9931011),
    "ponte_desktop_sem_mode": _cru(
        "Ponte Desktop Sem Mode", 9931012,
        ponte={"kind": "desktop", "gamepad_flavor": None, "steam_input": False,
               "confirmada_por": "escolha_do_usuario"}),
    "ja_no_formato": _cru(
        "Ja No Formato", 9931014, mode={"kind": "gamepad", "gamepad_flavor": "xbox",
                                        "caminho": "xbox"}),
}

O_MODO_ESPERADO: dict[str, dict[str, Any]] = {
    "sem_caminho": {"kind": "gamepad", "gamepad_flavor": "xbox", "caminho": "xbox"},
    "caminho_sem_mascara": {"kind": "gamepad", "gamepad_flavor": "dualsense",
                            "caminho": "dualsense"},
    "mascara_por_controle": {"kind": "gamepad", "gamepad_flavor": "xbox", "caminho": "xbox"},
    "mascara_sem_mode": {"kind": "gamepad", "gamepad_flavor": "nintendo"},
    "desktop_com_mascara": {"kind": "desktop", "gamepad_flavor": "xbox"},
    "ponte_sem_mode": {"kind": "gamepad", "gamepad_flavor": "dualsense", "caminho": "dualsense"},
    "ponte_nativa_sem_mode": {"kind": "native", "gamepad_flavor": None},
    "gamepad_sem_par": {"kind": "gamepad", "gamepad_flavor": "dualsense", "caminho": "dualsense"},
}


def _escrever(pasta: Path, chave: str, dados: dict[str, Any]) -> Path:
    alvo = pasta / f"{chave}.json"
    alvo.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return alvo


def _md5(pasta: Path) -> dict[str, str]:
    return {p.name: hashlib.md5(p.read_bytes()).hexdigest() for p in sorted(pasta.glob("*.json"))}


def _versoes(pasta: Path) -> list[Path]:
    return sorted((pasta / loader.HISTORICO_DIR_NAME).rglob("*.json"))


def _no_formato_da_aba_jogar(mode: dict[str, Any]) -> bool:
    """O ``mode`` é o que o escritor único deixa: reescrito por ele, não muda."""
    atual = ProfileModeConfig.model_validate(mode)
    secao = secao_do_modo_com_o_caminho(
        atual, kind=atual.kind, caminho=atual.caminho, mascara=atual.gamepad_flavor)
    if secao.model_dump() != atual.model_dump():
        return False
    if atual.kind != "gamepad":
        return atual.caminho is None
    return (atual.caminho, atual.gamepad_flavor) in {par_do_modo(m) for m in MODOS}


@pytest.fixture
def pasta() -> Path:
    destino = profiles_dir(ensure=True)
    for chave, dados in {**OS_FORMATOS, **OS_QUE_FICAM}.items():
        _escrever(destino, chave, dados)
    return destino


def test_cada_formato_antigo_vai_ao_formato_da_aba_jogar(pasta: Path) -> None:
    """Prova da D-3110-O-PERFIL-MORA-NO-DISCO-NO-FORMATO-DA-ABA-JOGAR.

    **A MORDIDA.** Sem a gravação da migração (o ``_atomic_write_json`` arrancado), o disco
    segue nos quatro formatos e esta régua reprova em cada um."""
    convertidos = loader.todo_perfil_no_formato_da_aba_jogar()

    assert sorted(convertidos) == sorted(f"{c}.json" for c in OS_FORMATOS)
    for chave, esperado in O_MODO_ESPERADO.items():
        dados = json.loads((pasta / f"{chave}.json").read_text(encoding="utf-8"))
        assert dados["mode"] == esperado, chave
        assert _no_formato_da_aba_jogar(dados["mode"]), chave
        controles = dados.get("controllers") or {}
        assert not any("mascara" in c for c in controles.values()), chave
        assert dados["modificado_em"] == MODIFICADO_EM, chave
        original = OS_FORMATOS[chave]
        assert {k: v for k, v in dados.items() if k not in ("mode", "controllers")} == {
            k: v for k, v in original.items() if k not in ("mode", "controllers")}, chave
    misturado = json.loads((pasta / "mascara_por_controle.json").read_text(encoding="utf-8"))
    assert misturado["controllers"][P3] == {"leds": {"lightbar": [1, 2, 3]}}


def test_o_perfil_sem_decisao_e_o_ja_convertido_ficam_byte_a_byte(pasta: Path) -> None:
    """Sem ``mode`` e sem ponte (a escada decide), com a ponte do ``desktop`` (o lançamento não
    a arma) e o já convertido: nenhum byte muda."""
    antes = {c: h for c, h in _md5(pasta).items() if c.removesuffix(".json") in OS_QUE_FICAM}

    loader.todo_perfil_no_formato_da_aba_jogar()

    depois = _md5(pasta)
    assert {c: depois[c] for c in antes} == antes
    sem = json.loads((pasta / "sem_mode_sem_ponte.json").read_text(encoding="utf-8"))
    assert "mode" not in sem


def test_a_segunda_rodada_nao_escreve_nada(pasta: Path) -> None:
    """Idempotente: a segunda passada não converte, não muda byte e não guarda versão."""
    loader.todo_perfil_no_formato_da_aba_jogar()
    bytes_da_primeira = _md5(pasta)
    versoes_da_primeira = _versoes(pasta)

    assert loader.todo_perfil_no_formato_da_aba_jogar() == []
    assert _md5(pasta) == bytes_da_primeira
    assert _versoes(pasta) == versoes_da_primeira


def test_a_versao_de_antes_vai_ao_historico(pasta: Path) -> None:
    """Cada perfil convertido guarda, no ``.historico``, os bytes de antes; o que fica, nada."""
    antes = {c: (pasta / f"{c}.json").read_bytes() for c in OS_FORMATOS}

    loader.todo_perfil_no_formato_da_aba_jogar()

    for chave, bruto in antes.items():
        versoes = loader.listar_historico(chave)
        assert [v.read_bytes() for v in versoes] == [bruto], chave
    for chave in OS_QUE_FICAM:
        assert loader.listar_historico(chave) == [], chave


def test_a_leitura_e_o_disco_dao_o_mesmo_modo(pasta: Path) -> None:
    """A máscara por controle: a leitura de antes da migração e o disco de depois concordam."""
    lidos_antes = {
        c: loader.load_profile(OS_FORMATOS[c]["name"]).mode
        for c in ("mascara_por_controle", "mascara_sem_mode", "desktop_com_mascara")
    }

    loader.todo_perfil_no_formato_da_aba_jogar()

    for chave, modo in lidos_antes.items():
        assert modo is not None
        assert loader.load_profile(OS_FORMATOS[chave]["name"]).mode == modo, chave


def test_a_primeira_carga_dos_perfis_roda_a_migracao(
    pasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """**A MORDIDA.** Quem converte é a semeadura da primeira carga; sem a chamada em
    ``_maybe_seed_presets``, o disco segue no formato antigo."""
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "seed_default_presets", lambda *_a, **_kw: [])
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)

    loader._maybe_seed_presets()

    dados = json.loads((pasta / "ponte_sem_mode.json").read_text(encoding="utf-8"))
    assert dados.get("mode") == O_MODO_ESPERADO["ponte_sem_mode"]


class _Daemon:
    """A borda do daemon que a escada lê: jogo na frente, sem controle de verdade."""

    def __init__(self) -> None:
        self.controller = SimpleNamespace()
        self.display_authority = "game"


def _escada_confirma_por_silencio(degrau: ponte_escada.Degrau) -> dict[str, bool]:
    """Confirma por silêncio e devolve o ``modo_alinhado`` de cada linha do diário do carimbo."""
    daemon = _Daemon()
    daemon._ponte_tentativa = ponte_tentativa.Tentativa(  # type: ignore[attr-defined]
        appid=APPID, epoch=1000, degrau=degrau, ultimo_gesto=0.0, viu_o_jogo=True)
    with structlog.testing.capture_logs() as registros:
        fim = launch_env.tique_da_escada(daemon, agora=ponte_escada.SILENCIO_CONFIRMA_SEC + 1.0)  # type: ignore[arg-type]
    assert fim == ponte_tentativa.FIM_CONFIRMADA
    return {
        r["event"]: r["modo_alinhado"] for r in registros
        if r["event"] in ("ponte_confirmada", "ponte_escada_carimbada")
    }


def test_o_carimbo_por_silencio_grava_a_ponte_e_o_modo_iguais() -> None:
    """**A MORDIDA.** O perfil sem ``mode`` (Mina the Hollower, 05:29:05): o carimbo por
    silêncio grava a ponte e o ``mode`` da mesma ponte, e as duas linhas do diário dizem
    ``modo_alinhado=True``. Com o ``o_carimbo_leva_o_modo`` arrancado (o ``alinhar_o_modo=False``
    de antes decidindo sozinho), o ``mode`` fica de fora e reprova; com o diário do carimbo de
    volta a ``resultado.alinhar``, ele diz ``False`` sobre o modo gravado e reprova."""
    pasta = profiles_dir(ensure=True)
    _escrever(pasta, "jogo_sem_modo", _cru("Jogo Sem Modo", APPID))

    diario = _escada_confirma_por_silencio(ponte_escada.ESCADA[0])

    assert diario == {"ponte_confirmada": True, "ponte_escada_carimbada": True}
    dados = json.loads((pasta / "jogo_sem_modo.json").read_text(encoding="utf-8"))
    assert dados["ponte"]["confirmada_por"] == "silencio"
    assert (dados["ponte"]["kind"], dados["ponte"]["gamepad_flavor"]) == ("gamepad", "dualsense")
    assert dados.get("mode") == {"kind": "gamepad", "gamepad_flavor": "dualsense",
                                 "caminho": "dualsense"}


def test_o_carimbo_por_silencio_nao_mexe_no_modo_escolhido() -> None:
    """O perfil que já tem ``mode`` (escolhido à mão ou já convertido) guarda o dele: o
    silêncio não pediu troca nenhuma, e o carimbo vai sozinho."""
    pasta = profiles_dir(ensure=True)
    escolhido = {"kind": "gamepad", "gamepad_flavor": "xbox", "caminho": "xbox"}
    _escrever(pasta, "jogo_com_modo", _cru("Jogo Com Modo", APPID, mode=escolhido))

    diario = _escada_confirma_por_silencio(ponte_escada.ESCADA[0])

    assert diario == {"ponte_confirmada": False, "ponte_escada_carimbada": False}
    dados = json.loads((pasta / "jogo_com_modo.json").read_text(encoding="utf-8"))
    assert dados["ponte"]["confirmada_por"] == "silencio"
    assert dados["mode"] == escolhido
