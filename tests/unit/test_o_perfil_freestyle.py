"""O-MODO-FREESTYLE-02 — o perfil de fora do jogo fica, e se chama «Freestyle»."""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

RAIZ = Path(__file__).resolve().parents[2]
FABRICA = RAIZ / "assets" / "profiles_default"
JOGO = "steam_app_2111190"

QUATRO = {f"aabbcc00000{n}": {"leds": {"lightbar": [n * 40, 0, 255 - n * 40]}}
          for n in (1, 2, 3, 4)}

PERFIL_DELA: dict[str, Any] = {
    "name": "Personalizado",
    "version": 1,
    "match": {"type": "criteria", "window_class": ["Hefesto-Dualsense4Unix"]},
    "priority": 1,
    "leds": {"lightbar": [255, 0, 0], "lightbar_brightness": 1.0},
    "controllers": QUATRO,
}


def _grava_dela(pasta: Path, dados: dict[str, Any] | None = None) -> bytes:
    """Grava o arquivo dela com a formatação dela e devolve os bytes exatos."""
    pasta.mkdir(parents=True, exist_ok=True)
    bruto = (json.dumps(dados or PERFIL_DELA, ensure_ascii=False, indent=4)
             + "\n").encode()
    (pasta / loader.ARQUIVO_DO_PERSONALIZADO).write_bytes(bruto)
    return bruto


def _copias(pasta: Path) -> list[Path]:
    return sorted((pasta / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PERSONALIZADO)
                  .glob("*.json"))


def _freestyle(pasta: Path) -> dict[str, Any]:
    return dict(json.loads((pasta / loader.ARQUIVO_DO_PADRAO).read_text(encoding="utf-8")))


def test_o_nome_e_o_arquivo_sao_do_freestyle() -> None:
    """O dono diz «Freestyle», e o asset versionado também."""
    assert loader.NOME_DO_PADRAO == "Freestyle"
    assert loader.ARQUIVO_DO_PADRAO == "freestyle.json"
    assert _freestyle(FABRICA)["name"] == loader.NOME_DO_PADRAO
    assert not (FABRICA / loader.ARQUIVO_DO_PERSONALIZADO).exists(), (
        "o preset «Personalizado» voltou à fábrica: a semeadura entregaria dois "
        "catch-all numa máquina nova")


def test_a_sanidade_nao_acusa_o_freestyle() -> None:
    """O catch-all de fábrica tem nome de perfil genérico, não de jogo perdido."""
    from hefesto_dualsense4unix.profiles.sanidade import verificar_perfis

    fabrica = Profile.model_validate(_freestyle(FABRICA))
    assert verificar_perfis([fabrica]) == []


def test_o_personalizado_dela_vira_freestyle_com_a_copia_byte_a_byte() -> None:
    """O caso dela, fim a fim: o nome muda, o conteúdo fica, e os bytes guardam."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)

    copia = loader.o_personalizado_vira_freestyle()

    assert copia is not None and copia.read_bytes() == bruto
    assert copia.parent == pasta / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PERSONALIZADO
    assert not (pasta / loader.ARQUIVO_DO_PERSONALIZADO).exists()
    novo = _freestyle(pasta)
    assert novo["name"] == "Freestyle"
    assert novo["controllers"] == QUATRO
    assert novo["leds"] == PERFIL_DELA["leds"]
    assert novo["priority"] == PERFIL_DELA["priority"]
    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]


def test_a_volta_existe_e_devolve_o_arquivo_inteiro() -> None:
    """Reversível: `restaurar_do_historico` é a volta que a casa já tinha."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)
    loader.o_personalizado_vira_freestyle()

    alvo, _versao = loader.restaurar_do_historico(loader.SLUG_DO_PERSONALIZADO)

    assert alvo == pasta / loader.ARQUIVO_DO_PERSONALIZADO
    assert alvo.read_bytes() == bruto


def test_a_segunda_corrida_nao_faz_nada() -> None:
    """One-shot, pela marca: nem cópia nova, nem um byte do Freestyle mexido."""
    pasta = profiles_dir(ensure=True)
    _grava_dela(pasta)
    assert loader.o_personalizado_vira_freestyle() is not None
    antes = (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes()

    assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == antes
    assert len(_copias(pasta)) == 1

    loader.save_profile(Profile(name="Personalizado",
                                match=MatchCriteria(window_class=["firefox"])))
    assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).is_file()


def test_sem_copia_nada_muda_e_a_marca_nao_nasce(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apagar sem volta é o único desfecho que a migração não tem."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)
    with monkeypatch.context() as m:
        m.setattr(loader, "_arquivar_versao", lambda *a, **k: None)
        assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).read_bytes() == bruto
    assert not (pasta / loader.ARQUIVO_DO_PADRAO).exists()
    assert not (pasta / loader._PERSONALIZADO_VIROU_FREESTYLE_MARKER).exists()

    assert loader.o_personalizado_vira_freestyle() is not None
    assert _freestyle(pasta)["controllers"] == QUATRO


def test_a_escrita_que_falha_deixa_o_arquivo_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ordem: a cópia, o novo, e SÓ ENTÃO o antigo sai."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)

    def _disco_cheio(*_a: Any, **_k: Any) -> None:
        raise OSError(28, "No space left on device")

    with monkeypatch.context() as m:
        m.setattr(loader, "_atomic_write_json", _disco_cheio)
        with pytest.raises(OSError):
            loader.o_personalizado_vira_freestyle()
    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).read_bytes() == bruto
    assert [c.read_bytes() for c in _copias(pasta)] == [bruto]
    assert not (pasta / loader._PERSONALIZADO_VIROU_FREESTYLE_MARKER).exists()


def test_a_regra_da_nossa_janela_vira_any_e_a_dela_fica() -> None:
    """O Freestyle é o perfil de FORA do jogo: a regra que só mira o Hefesto sai."""
    pasta = profiles_dir(ensure=True)
    _grava_dela(pasta)
    loader.o_personalizado_vira_freestyle()
    assert _freestyle(pasta)["match"] == {"type": "any"}


def test_a_regra_dela_para_outro_programa_fica() -> None:
    pasta = profiles_dir(ensure=True)
    dela = dict(PERFIL_DELA, match={"type": "criteria", "window_class": ["firefox"]})
    _grava_dela(pasta, dela)
    loader.o_personalizado_vira_freestyle()
    assert _freestyle(pasta)["match"] == {"type": "criteria", "window_class": ["firefox"]}


def test_recusa_quando_ela_ja_tem_um_freestyle() -> None:
    """Um `freestyle.json` que não é o de fábrica é DELA: os dois ficam."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)
    dela = {"name": "Freestyle", "version": 1, "match": {"type": "any"}, "priority": 7}
    (pasta / loader.ARQUIVO_DO_PADRAO).write_text(json.dumps(dela), encoding="utf-8")

    assert loader.o_personalizado_vira_freestyle() is None

    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).read_bytes() == bruto
    assert _freestyle(pasta) == dela
    assert _copias(pasta) == []


def test_o_freestyle_de_fabrica_que_o_install_copiou_cede_o_lugar() -> None:
    """O `install_profiles.sh` roda ANTES de qualquer Python e copia a fábrica."""
    pasta = profiles_dir(ensure=True)
    _grava_dela(pasta)
    (pasta / loader.ARQUIVO_DO_PADRAO).write_bytes(
        (FABRICA / loader.ARQUIVO_DO_PADRAO).read_bytes())

    assert loader.o_personalizado_vira_freestyle() is not None
    assert _freestyle(pasta)["controllers"] == QUATRO


def test_recusa_quando_ela_renomeou_na_mao() -> None:
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta, dict(PERFIL_DELA, name="Sofá"))
    assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).read_bytes() == bruto
    assert not (pasta / loader.ARQUIVO_DO_PADRAO).exists()


@pytest.mark.parametrize("bruto", [b"{ quebrado", b"[1, 2]"], ids=["texto", "lista"])
def test_json_que_nao_e_perfil_fica_como_esta(bruto: bytes) -> None:
    pasta = profiles_dir(ensure=True)
    (pasta / loader.ARQUIVO_DO_PERSONALIZADO).write_bytes(bruto)
    assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader.ARQUIVO_DO_PERSONALIZADO).read_bytes() == bruto
    assert not (pasta / loader.ARQUIVO_DO_PADRAO).exists()


def test_sem_personalizado_nada_acontece_e_a_marca_nasce() -> None:
    pasta = profiles_dir(ensure=True)
    assert loader.o_personalizado_vira_freestyle() is None
    assert (pasta / loader._PERSONALIZADO_VIROU_FREESTYLE_MARKER).is_file()
    assert not (pasta / loader.HISTORICO_DIR_NAME).exists()


def test_a_copia_mora_na_pasta_que_a_migracao_recebeu(tmp_path: Path) -> None:
    """`dest_dir` injetado leva o histórico junto — nunca o `profiles_dir()`."""
    outra = tmp_path / "outra"
    bruto = _grava_dela(outra)

    copia = loader.o_personalizado_vira_freestyle(dest_dir=outra)

    assert copia is not None and copia.read_bytes() == bruto
    assert copia.parent == outra / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PERSONALIZADO
    assert not (profiles_dir() / loader.HISTORICO_DIR_NAME).exists()


def test_a_sessao_que_apontava_o_personalizado_aponta_o_freestyle() -> None:
    """Sem isto o boot procuraria um arquivo que virou outro, e ficaria sem perfil."""
    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")

    loader.o_personalizado_vira_freestyle()

    assert session.load_last_profile() == "Freestyle"
    assert session.read_active_marker() == "Freestyle"
    assert session.resolve_boot_profile() is None, "o botão apagado: sem escolha"
    session.save_freestyle_ligado(True)
    assert session.resolve_boot_profile() == "Freestyle"


def test_a_sessao_que_aponta_outro_perfil_nao_e_tocada() -> None:
    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Mullet Mad Jack")
    session.save_active_marker("Mullet Mad Jack")

    loader.o_personalizado_vira_freestyle()

    assert session.load_last_profile() == "Mullet Mad Jack"
    assert session.read_active_marker() == "Mullet Mad Jack"


@pytest.fixture
def semeadura_ligada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liga a semeadura (o conftest a desliga) contra a FÁBRICA versionada."""
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (FABRICA,))
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)


def _install_profiles(home: Path) -> subprocess.CompletedProcess[str]:
    """O `scripts/install_profiles.sh` de VERDADE, num HOME de mentira."""
    return subprocess.run(
        ["bash", str(RAIZ / "scripts" / "install_profiles.sh"), str(RAIZ)],
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True, check=False, timeout=60,
    )


def test_maquina_nova_abre_com_o_freestyle(semeadura_ligada: None) -> None:
    """A primeira carga de perfis do processo — o que o daemon e a janela fazem."""
    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]
    assert loader.o_perfil_de_fora_do_jogo() == "Freestyle"
    assert session.load_freestyle_ligado() is True, "a máquina nova nasce acesa"
    assert session.resolve_boot_profile() == "Freestyle"


def test_o_disco_de_23_09_vira_freestyle_numa_carga(semeadura_ligada: None) -> None:
    """O disco dela hoje: o Personalizado com os quatro controles, ativo na sessão."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava_dela(pasta)
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")

    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]

    assert _freestyle(pasta)["controllers"] == QUATRO
    assert [c.read_bytes() for c in _copias(pasta)] == [bruto]
    assert session.resolve_boot_profile() is None
    assert session.load_freestyle_ligado() is False
    assert (session.config_dir() / session._COPIA_DA_SESSAO).is_file()


def test_o_disco_de_antes_de_05_09_vai_direto_ao_freestyle(semeadura_ligada: None) -> None:
    """`meu_perfil.json` ativo: a renomeação de 05/09 já leva ao nome de hoje."""
    pasta = profiles_dir(ensure=True)
    velho = dict(PERFIL_DELA, name="meu_perfil", match={"type": "any"})
    (pasta / loader.ARQUIVO_ANTIGO_DO_PADRAO).write_text(
        json.dumps(velho, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    session.save_last_profile("meu_perfil")
    session.save_active_marker("meu_perfil")

    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]

    assert (pasta / loader.BACKUP_DO_PADRAO).is_file()
    assert _freestyle(pasta)["controllers"] == QUATRO
    assert session.resolve_boot_profile() is None
    assert (session.config_dir() / session._COPIA_DA_SESSAO).is_file()


def test_o_install_profiles_de_hoje_roda_antes_e_o_dela_vence(
    tmp_path: Path, semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MEDIDA DO ITEM 4: o `install.sh` chama o shell antes de qualquer Python."""
    home = tmp_path / "home"
    pasta = home / ".config" / "hefesto-dualsense4unix" / "profiles"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    assert profiles_dir() == pasta
    _grava_dela(pasta)

    feito = _install_profiles(home)

    assert feito.returncode == 0, feito.stderr
    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]
    assert _freestyle(pasta)["controllers"] == QUATRO
    assert not (pasta / loader.ARQUIVO_DO_PERSONALIZADO).exists()


def test_o_install_profiles_depois_do_python_nao_traz_um_segundo(
    tmp_path: Path, semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O marker é contrato dos dois semeadores: depois do Python, o shell não copia."""
    home = tmp_path / "home"
    pasta = home / ".config" / "hefesto-dualsense4unix" / "profiles"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    _grava_dela(pasta)
    loader.load_all_profiles()
    antes = (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes()

    feito = _install_profiles(home)

    assert feito.returncode == 0, feito.stderr
    assert sorted(p.name for p in pasta.glob("*.json")) == [loader.ARQUIVO_DO_PADRAO]
    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == antes


def _grava_meu_perfil(pasta: Path, match: dict[str, Any]) -> None:
    """O disco de antes de 05/09: o padrão dela ainda se chama `meu_perfil`."""
    pasta.mkdir(parents=True, exist_ok=True)
    velho = dict(PERFIL_DELA, name=loader.NOME_ANTIGO_DO_PADRAO, match=match)
    (pasta / loader.ARQUIVO_ANTIGO_DO_PADRAO).write_text(
        json.dumps(velho, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_o_meu_perfil_com_a_nossa_janela_tambem_vale_fora_do_jogo(
    semeadura_ligada: None,
) -> None:
    """A regra da própria janela sai também no disco de antes de 05/09."""
    pasta = profiles_dir(ensure=True)
    _grava_meu_perfil(pasta, PERFIL_DELA["match"])

    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]
    assert _freestyle(pasta)["match"] == {"type": "any"}


def test_o_install_profiles_de_hoje_no_disco_de_antes_de_05_09(
    tmp_path: Path, semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O shell de hoje copia a fábrica ao lado do `meu_perfil.json` também."""
    home = tmp_path / "home"
    pasta = home / ".config" / "hefesto-dualsense4unix" / "profiles"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    _grava_meu_perfil(pasta, {"type": "any"})

    feito = _install_profiles(home)

    assert feito.returncode == 0, feito.stderr
    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]
    assert _freestyle(pasta)["controllers"] == QUATRO
    assert (pasta / loader.BACKUP_DO_PADRAO).is_file()


@pytest.mark.parametrize("nome_antigo", ["meu_perfil.json", "personalizado.json"])
def test_o_shell_recusa_a_fabrica_ao_lado_do_nome_antigo(
    tmp_path: Path, nome_antigo: str,
) -> None:
    """O `install_profiles.sh` espelha o `loader._o_slot_dela_tem_nome_antigo`."""
    home = tmp_path / "home"
    pasta = home / ".config" / "hefesto-dualsense4unix" / "profiles"
    pasta.mkdir(parents=True)
    (pasta / nome_antigo).write_text(
        json.dumps(dict(PERFIL_DELA, name="Sofá"), ensure_ascii=False) + "\n",
        encoding="utf-8")

    feito = _install_profiles(home)

    assert feito.returncode == 0, feito.stderr
    assert not (pasta / loader.ARQUIVO_DO_PADRAO).exists(), feito.stdout
    assert loader.ARQUIVO_DO_PADRAO in (pasta / ".seeded_presets").read_text(
        encoding="utf-8").splitlines()


def test_o_personalizado_que_ela_renomeou_nao_ganha_um_freestyle_ao_lado(
    semeadura_ligada: None,
) -> None:
    """Ela deu outro nome ao padrão: esse é o perfil de fora do jogo DELA."""
    pasta = profiles_dir(ensure=True)
    _grava_dela(pasta, dict(PERFIL_DELA, name="Sofá", match={"type": "any"}))

    assert [p.name for p in loader.load_all_profiles()] == ["Sofá"]
    assert not (pasta / loader.ARQUIVO_DO_PADRAO).exists()


class _ControleQueGuarda(FakeController):
    """O `FakeController` que GUARDA o mapa por controle que o perfil manda."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)
        self.camada: dict[str, Any] = {}

    def reset_output_overrides(self, overrides: Any = None) -> None:
        self.camada = dict(overrides or {})


async def _bloqueante(fn: Any, *args: Any) -> Any:
    return fn(*args)


def _boot(controle: FakeController, store: StateStore) -> None:
    asyncio.run(connection.restore_last_profile(SimpleNamespace(  # type: ignore[arg-type]
        controller=controle, store=store, _run_blocking=_bloqueante,
        _native_mode=False)))


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_o_boot_restaura_o_freestyle_com_os_quatro_controles(
    semeadura_ligada: None, transporte: str,
) -> None:
    """O disco dela, uma carga, e o boot: o Freestyle vale, com os quatro."""
    pasta = profiles_dir(ensure=True)
    _grava_dela(pasta)
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")
    session.save_freestyle_ligado(True)
    loader.load_all_profiles()
    controle = _ControleQueGuarda(transport=transporte)
    controle.connect()
    store = StateStore()
    store.set_freestyle_ligado(session.load_freestyle_ligado())

    _boot(controle, store)

    assert store.active_profile == "Freestyle"
    assert len(controle.camada) == 4, controle.camada


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_sem_sessao_o_boot_cai_no_freestyle(semeadura_ligada: None, transporte: str) -> None:
    """Máquina nova, ninguém ativou nada na mão: o boot não fica sem perfil."""
    loader.load_all_profiles()
    controle = _ControleQueGuarda(transport=transporte)
    controle.connect()
    store = StateStore()
    store.set_freestyle_ligado(True)

    _boot(controle, store)

    assert store.active_profile == "Freestyle"
    assert session.load_last_profile() is None, (
        "o boot gravou a sessão: restauro de sistema não é gesto dela")


def test_sem_freestyle_no_disco_o_boot_nao_inventa(semeadura_ligada: None,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem o arquivo (ela o apagou), o boot fica como sempre ficou: sem perfil."""
    loader.load_all_profiles()
    (profiles_dir() / loader.ARQUIVO_DO_PADRAO).unlink()
    store = StateStore()
    controle = _ControleQueGuarda()
    controle.connect()

    _boot(controle, store)

    assert store.active_profile is None


def _cena(travado: bool, escolha: str | None = None) -> list[str | None]:
    """O boot, o desktop, um jogo com perfil próprio, e o desktop de novo."""
    loader.load_all_profiles()
    loader.save_profile(Profile(name="Mullet Mad Jack",
                                match=MatchCriteria(window_class=[JOGO]),
                                priority=80))
    if escolha is not None:
        loader.save_profile(Profile(name=escolha,
                                    match=MatchCriteria(window_class=["zathura"]),
                                    priority=60))
        session.save_last_profile(escolha)
    session.save_freestyle_ligado(travado)
    store = StateStore()
    store.set_freestyle_ligado(travado)
    controle = _ControleQueGuarda()
    controle.connect()
    _boot(controle, store)
    ativos: list[str | None] = [store.active_profile]
    sw = AutoSwitcher(manager=ProfileManager(controller=controle, store=store),
                      window_reader=lambda: {}, store=store)
    agora = 0.0
    for info, segundos in (({"wm_class": "firefox", "wm_name": "Mozilla"}, 20),
                           ({"wm_class": JOGO, "wm_name": "Mullet Mad Jack"}, 5),
                           ({"wm_class": "firefox", "wm_name": "Mozilla"}, 30)):
        fim = agora + segundos
        while agora <= fim:
            sw._tick(info, agora)
            agora += 0.5
        ativos.append(store.active_profile)
    return ativos


def test_com_o_modo_freestyle_ligado_o_jogo_nao_entra(
    semeadura_ligada: None,
) -> None:
    """Ligado, o Freestyle vale no desktop, no jogo e na volta."""
    assert _cena(travado=True) == ["Freestyle", "Freestyle", "Freestyle",
                                   "Freestyle"]


def test_com_o_modo_freestyle_desligado_a_volta_e_a_escolha_dela(
    semeadura_ligada: None,
) -> None:
    """Desligado, o boot abre na escolha dela, o jogo entra e a volta é a ela."""
    assert _cena(travado=False, escolha="Sofá") == ["Sofá", "Sofá",
                                                    "Mullet Mad Jack", "Sofá"]


def test_sem_escolha_o_desligado_nao_cai_no_freestyle(semeadura_ligada: None) -> None:
    """«Sem escolha» (item 10): nenhum perfil no boot, e a volta do jogo não inventa um."""
    assert _cena(travado=False) == [None, None, "Mullet Mad Jack", "Mullet Mad Jack"]


def _brilho_sem_daemon() -> str:
    """O brilho da aba 04 com o daemon calado: o que o gesto responde.

    É o caminho de toda aba que grava no perfil ativo (02 a 08): o alvo vem de
    `perfil.nome_do_ativo`, que pergunta ao daemon e depois ao disco.
    """
    from hefesto_dualsense4unix.interface.pacotes import Contexto
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao as a04

    try:
        a04.brilho(Contexto(state={"active_profile": None, "controllers": []}),
                   {"uniq": "aa:bb:cc:00:00:01", "valor": "50"}, None)
    except RuntimeError as recusa:
        return str(recusa)
    return ""


def test_com_o_freestyle_as_abas_tem_onde_guardar(semeadura_ligada: None) -> None:
    """A medição que derrubou o motor da 01, com o sinal que a decisão pediu."""
    from hefesto_dualsense4unix.interface.pacotes import perfil

    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")
    session.save_freestyle_ligado(True)
    loader.load_all_profiles()

    alvo = perfil.nome_do_ativo({"active_profile": None, "controllers": []})
    assert alvo == "Freestyle", f"as abas gravariam em {alvo!r}"
    assert loader.load_profile(alvo).model_dump()["controllers"].keys() == QUATRO.keys()
    assert "não há perfil ativo" not in _brilho_sem_daemon()


def test_o_topo_diz_freestyle(semeadura_ligada: None) -> None:
    """Com o botão aceso, o chip «Perfil ativo» diz «Freestyle» — nunca o nome que saiu."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto, topo

    _grava_dela(profiles_dir(ensure=True))
    session.save_last_profile("Personalizado")
    session.save_active_marker("Personalizado")
    session.save_freestyle_ligado(True)
    loader.load_all_profiles()

    ctx = Contexto(state={"active_profile": None, "controllers": []})
    assert topo(ctx)["perfil"] == "Freestyle"


class _PonteDoRodape:
    """O bastante para o «Salvar Perfil», e nada mais frouxo que a real."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def apply_draft_detalhado(self, payload: dict[str, Any]) -> tuple[bool, None]:
        self.chamadas.append(("apply_draft_detalhado", (payload,)))
        return True, None

    def profile_reaplicar(self, nome: str) -> dict[str, Any]:
        self.chamadas.append(("profile_reaplicar", (nome,)))
        return {"active_profile": nome, "mode_aplicado": True, "secoes": {}}

    def chamar(self, metodo: str, timeout: float | None = None, **params: Any) -> bool:
        self.chamadas.append(("chamar", (metodo,)))
        return True

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        self.chamadas.append(("resultado", (metodo,)))
        return {"status": "ok"}


def _ctx_sem_perfil() -> Any:
    """O daemon não diz quem está ativo, e a sessão está vazia."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    return Contexto(state={"connected": True, "active_profile": None},
                    mesa=[], conectados=[], estados={})


def test_o_salvar_sem_perfil_ativo_grava_no_freestyle(semeadura_ligada: None) -> None:
    """Sem perfil valendo, o Salvar grava onde o boot restauraria: o Freestyle."""
    from hefesto_dualsense4unix.interface.pacotes import rodape, topo

    loader.load_all_profiles()
    arquivo = profiles_dir() / loader.ARQUIVO_DO_PADRAO
    antes = arquivo.read_bytes()
    ctx = _ctx_sem_perfil()

    rodape.salvar(ctx, {}, _PonteDoRodape())

    assert json.loads(arquivo.read_text(encoding="utf-8"))["name"] == "Freestyle"
    assert [c.read_bytes() for c in sorted(
        (profiles_dir() / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PADRAO).glob("*.json")
    )] == [antes], "o Salvar não guardou a versão de antes no histórico"
    assert "no perfil Freestyle" in topo(ctx)["rodape.salvar"]


def test_sem_freestyle_no_disco_o_salvar_continua_recusando(semeadura_ligada: None) -> None:
    """Sem o arquivo (ela o apagou), o gesto não inventa perfil: recusa dizendo."""
    from hefesto_dualsense4unix.interface.pacotes import rodape, topo

    loader.load_all_profiles()
    (profiles_dir() / loader.ARQUIVO_DO_PADRAO).unlink()
    ctx = _ctx_sem_perfil()

    with pytest.raises(ValueError, match="não há perfil ativo"):
        rodape.salvar(ctx, {}, _PonteDoRodape())
    assert "no perfil ativo" in topo(ctx)["rodape.salvar"]
    assert list(profiles_dir().glob("*.json")) == []
