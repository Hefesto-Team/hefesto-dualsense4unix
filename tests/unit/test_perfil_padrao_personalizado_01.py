"""PERFIL-PADRAO-PERSONALIZADO-01 — o padrão deixa de se chamar `meu_perfil`."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles.loader import (
    ARQUIVO_ANTIGO_DO_PADRAO,
    ARQUIVO_DO_PADRAO,
    BACKUP_DO_PADRAO,
    NOME_DO_PADRAO,
    SEED_MARKER_NAME,
    migrate_default_profile_name,
    seed_default_presets,
)

PERFIL_DELA: dict = {
    "name": "meu_perfil",
    "version": 1,
    "match": {"type": "any"},
    "priority": 1,
    "triggers": {
        "left": {"mode": "Off", "params": []},
        "right": {"mode": "Off", "params": []},
    },
    "leds": {
        "lightbar": [40, 80, 180],
        "player_leds": [False, False, True, False, False],
        "lightbar_brightness": 1.0,
        "auto_player_colors": True,
    },
    "rumble": {"passthrough": True, "policy": None, "custom_mult": None},
    "suppress_desktop_emulation": False,
    "controllers": {
        "d42f4b000000": {
            "leds": {"lightbar": [255, 0, 0]},
            "rumble": {"policy": "balanceado"},
        },
        "444648000000": {
            "leds": {"lightbar": [0, 0, 255]},
            "rumble": {"policy": "max"},
        },
    },
}


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    """Um diretório de perfis vazio, isolado do disco de qualquer pessoa."""
    d = tmp_path / "profiles"
    d.mkdir()
    return d


def _grava(directory: Path, nome: str, dados: dict) -> Path:
    caminho = directory / nome
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return caminho


def _fonte_de_fabrica(tmp_path: Path) -> Path:
    """O `assets/profiles_default/` de fábrica, com o preset novo dentro."""
    fonte = tmp_path / "fabrica"
    fonte.mkdir()
    _grava(
        fonte,
        ARQUIVO_DO_PADRAO,
        {
            "name": NOME_DO_PADRAO,
            "version": 1,
            "match": {"type": "any"},
            "priority": 1,
        },
    )
    return fonte


def test_o_perfil_dela_muda_de_nome_sem_perder_uma_linha(disco: Path) -> None:
    """O caso dela, fim a fim: renomeia e o conteúdo sai idêntico."""
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)

    assert migrate_default_profile_name(disco) == NOME_DO_PADRAO

    novo = json.loads((disco / ARQUIVO_DO_PADRAO).read_text(encoding="utf-8"))
    assert novo["name"] == NOME_DO_PADRAO
    esperado = {k: v for k, v in PERFIL_DELA.items() if k != "name"}
    assert {k: v for k, v in novo.items() if k != "name"} == esperado


def test_o_arquivo_antigo_fica_no_disco_e_some_da_lista(disco: Path) -> None:
    """"Guardando o antigo" — e guardado onde leitor nenhum tropece nele."""
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)

    migrate_default_profile_name(disco)

    backup = disco / BACKUP_DO_PADRAO
    assert backup.is_file(), "o perfil antigo dela não pode simplesmente sumir"
    assert json.loads(backup.read_text(encoding="utf-8")) == PERFIL_DELA
    assert not (disco / ARQUIVO_ANTIGO_DO_PADRAO).exists()
    assert sorted(p.name for p in disco.glob("*.json")) == [ARQUIVO_DO_PADRAO]


def test_a_sessao_segue_o_nome_novo(
    disco: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A metade A não pode quebrar a metade B."""
    from hefesto_dualsense4unix.utils import session, xdg_paths

    lar = tmp_path / "config"
    lar.mkdir()
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: lar)
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: lar)

    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    session.save_last_profile("meu_perfil")
    session.save_active_marker("meu_perfil")

    migrate_default_profile_name(disco)

    assert session.load_last_profile() == NOME_DO_PADRAO
    assert session.read_active_marker() == NOME_DO_PADRAO
    from hefesto_dualsense4unix.profiles import loader as _loader

    monkeypatch.setattr(_loader, "profiles_dir", lambda ensure=False: disco)
    assert session.resolve_boot_profile() is None
    session.save_freestyle_ligado(True)
    assert session.resolve_boot_profile() == NOME_DO_PADRAO


def test_a_sessao_que_aponta_outro_perfil_nao_e_tocada(
    disco: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Repontar é só para quem apontava o nome antigo — nada além disso."""
    from hefesto_dualsense4unix.utils import session, xdg_paths

    lar = tmp_path / "config"
    lar.mkdir()
    monkeypatch.setattr(xdg_paths, "config_dir", lambda ensure=False: lar)
    monkeypatch.setattr(session, "config_dir", lambda ensure=False: lar)

    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    session.save_last_profile("Black Myth: Wukong")
    session.save_active_marker("Black Myth: Wukong")

    migrate_default_profile_name(disco)

    assert session.load_last_profile() == "Black Myth: Wukong"
    assert session.read_active_marker() == "Black Myth: Wukong"


def test_recusa_quando_ela_ja_tem_um_perfil_personalizado(disco: Path) -> None:
    """Ela mesma criou um perfil com o nome do padrão. Sobrescrever destruiria dado."""
    dela = {"name": NOME_DO_PADRAO, "version": 1, "match": {"type": "any"},
            "priority": 42}
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    _grava(disco, ARQUIVO_DO_PADRAO, dela)

    assert migrate_default_profile_name(disco) is None

    assert json.loads(
        (disco / ARQUIVO_DO_PADRAO).read_text(encoding="utf-8")
    ) == dela
    assert (disco / ARQUIVO_ANTIGO_DO_PADRAO).is_file()


def test_recusa_quando_ela_ja_renomeou_o_perfil_na_mao(disco: Path) -> None:
    """O arquivo é `meu_perfil.json` mas o NOME lá dentro é do usuário."""
    dela = dict(PERFIL_DELA, name="Meu jeito")
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, dela)

    assert migrate_default_profile_name(disco) is None

    assert json.loads(
        (disco / ARQUIVO_ANTIGO_DO_PADRAO).read_text(encoding="utf-8")
    ) == dela
    assert not (disco / ARQUIVO_DO_PADRAO).exists()


def test_recusa_em_json_ilegivel_sem_explodir(disco: Path) -> None:
    """Perfil corrompido não pode derrubar a carga de perfil de ninguém."""
    (disco / ARQUIVO_ANTIGO_DO_PADRAO).write_text("{ não é json", encoding="utf-8")

    assert migrate_default_profile_name(disco) is None
    assert (disco / ARQUIVO_ANTIGO_DO_PADRAO).is_file()


def test_e_one_shot(disco: Path) -> None:
    """Rodou uma vez, não roda de novo — nem se o nome antigo reaparecer."""
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    assert migrate_default_profile_name(disco) == NOME_DO_PADRAO

    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    assert migrate_default_profile_name(disco) is None
    assert (disco / ARQUIVO_ANTIGO_DO_PADRAO).is_file()


def test_maquina_nova_nao_tem_o_que_migrar(disco: Path) -> None:
    """Sem `meu_perfil.json`, a migração é no-op e o semeador faz o trabalho."""
    assert migrate_default_profile_name(disco) is None
    assert not (disco / ARQUIVO_DO_PADRAO).exists()


def test_o_semeador_nao_entrega_o_segundo_catch_all(
    disco: Path, tmp_path: Path
) -> None:
    """A rede: `install.sh` semeia ANTES de qualquer Python carregar perfil."""
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)

    copiados = seed_default_presets(
        dest_dir=disco, source_dirs=(_fonte_de_fabrica(tmp_path),)
    )

    assert copiados == []
    assert sorted(p.name for p in disco.glob("*.json")) == [
        ARQUIVO_ANTIGO_DO_PADRAO
    ]
    marker = (disco / SEED_MARKER_NAME).read_text(encoding="utf-8").splitlines()
    assert ARQUIVO_DO_PADRAO in marker


def test_maquina_nova_recebe_o_preset_de_fabrica(disco: Path, tmp_path: Path) -> None:
    """Par da recusa acima: sem o arquivo antigo, o preset novo É semeado."""
    copiados = seed_default_presets(
        dest_dir=disco, source_dirs=(_fonte_de_fabrica(tmp_path),)
    )

    assert copiados == [ARQUIVO_DO_PADRAO]
    semeado = json.loads(
        (disco / ARQUIVO_DO_PADRAO).read_text(encoding="utf-8")
    )
    assert semeado["name"] == NOME_DO_PADRAO


def test_depois_da_migracao_o_semeador_nao_sobrescreve_o_dela(
    disco: Path, tmp_path: Path
) -> None:
    """A ordem de `_maybe_seed_presets`: migra e SÓ ENTÃO semeia."""
    _grava(disco, ARQUIVO_ANTIGO_DO_PADRAO, PERFIL_DELA)
    migrate_default_profile_name(disco)

    copiados = seed_default_presets(
        dest_dir=disco, source_dirs=(_fonte_de_fabrica(tmp_path),)
    )

    assert copiados == []
    depois = json.loads((disco / ARQUIVO_DO_PADRAO).read_text(encoding="utf-8"))
    assert depois["controllers"] == PERFIL_DELA["controllers"]


def test_o_asset_versionado_nao_carrega_mais_o_slug() -> None:
    """O que uma instalação nova entrega: nome de gente, não slug."""
    raiz = Path(__file__).resolve().parents[2]
    fabrica = raiz / "assets" / "profiles_default"

    assert not (fabrica / ARQUIVO_ANTIGO_DO_PADRAO).exists()
    dados = json.loads(
        (fabrica / ARQUIVO_DO_PADRAO).read_text(encoding="utf-8")
    )
    assert dados["name"] == NOME_DO_PADRAO

    catch_all = []
    for caminho in sorted(fabrica.glob("*.json")):
        dado = json.loads(caminho.read_text(encoding="utf-8"))
        if dado.get("match", {}).get("type") == "any":
            catch_all.append((caminho.name, dado.get("priority")))
    assert catch_all == [(ARQUIVO_DO_PADRAO, 1)]
