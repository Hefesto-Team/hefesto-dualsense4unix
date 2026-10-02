"""PLAT-01 (Proton pinado): conf, ensure com sha256, CompatToolMapping, gates."""
from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import proton_pin as pp

PIN_NAME = "GE-Proton10-34"

CONF_OK = f"""
# comentário
name={PIN_NAME}
url=https://example.invalid/{PIN_NAME}.tar.gz
sha256={"ab" * 32}
"""

_TAB = "\t"


def test_parse_conf_ignora_comentarios_e_normaliza_sha():
    conf = pp.parse_pin_conf(CONF_OK.replace("ab" * 32, "AB" * 32))
    assert conf["name"] == PIN_NAME
    assert conf["sha256"] == "ab" * 32


@pytest.mark.parametrize("faltando", ["name", "url", "sha256"])
def test_parse_conf_explode_sem_chave_obrigatoria(faltando):
    linhas = [
        linha
        for linha in CONF_OK.splitlines()
        if not linha.startswith(f"{faltando}=")
    ]
    with pytest.raises(ValueError, match=faltando):
        pp.parse_pin_conf("\n".join(linhas))


def test_parse_conf_explode_com_sha256_torto():
    """Seguir com sha inválido extrairia binário não verificado — explode."""
    with pytest.raises(ValueError, match="sha256"):
        pp.parse_pin_conf(CONF_OK.replace("ab" * 32, "deadbeef"))


def test_o_asset_real_do_repo_parseia_e_pina_a_versao_validada():
    """assets/proton-pin.conf é a fonte da verdade — o contrato do install.

    16/09/2026: o pino subiu de `GE-Proton10-34` para `GE-Proton11-6-x86_64`,
    pela feature que a versão nova traz — o áudio do alto-falante do controle e
    as haptics de voice-coil DENTRO do jogo (o 11-4 "finalized … haptics,
    controller-speaker audio, and hotplug handling"; o 11-6 "reworked …
    audio/haptic routing, endpoint identity"). A razão do pino não mudou: sem
    ele um upgrade automático de Proton pode reintroduzir o controle duplicado
    do winebus.

    CORREÇÃO DE FATO, 17/09/2026: esta docstring dizia que o 11-4 "fechou o
    casamento do ContainerId com o MMDevice" e que o 11-6 "refez o caminho pelo
    dsound". As notas de release do 11-4 ao 11-7 não dizem isso, e o dsound.dll
    do pino velho tem os mesmos símbolos — ver
    docs/protocol/proton-o-pino-desta-casa-e-a-subida-para-o-11-7.md, §7.1.

    O SUFIXO `-x86_64` FAZ PARTE DO NOME, e é a armadilha desta subida: a partir
    do 11-4 o release publica `GE-Proton11-N-x86_64.tar.gz`, a raiz do tarball é
    `GE-Proton11-6-x86_64/` e o nome INTERNO do `compatibilitytool.vdf` — o
    valor que vai ao `CompatToolMapping` — também tem o sufixo. Até o 11-3 não
    havia nenhum.
    """
    asset = Path(__file__).resolve().parents[2] / "assets" / "proton-pin.conf"
    conf = pp.parse_pin_conf(asset.read_text(encoding="utf-8"))
    assert conf["name"] == "GE-Proton11-7-x86_64"
    assert "GloriousEggroll/proton-ge-custom" in conf["url"]
    assert conf["url"].endswith(f"{conf['name']}.tar.gz")


def _make_tarball(tmp_path: Path, name: str = PIN_NAME) -> Path:
    """Tarball mínimo com a MESMA forma do release (topo = <name>/)."""
    src = tmp_path / "tar-src" / name
    src.mkdir(parents=True)
    (src / "proton").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (src / "version").write_text(f"1752000000 {name}\n", encoding="utf-8")
    (src / "files").mkdir()
    (src / "files" / "bin.txt").write_text("x", encoding="utf-8")
    tarball = tmp_path / f"{name}.tar.gz"
    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(src, arcname=name)
    return tarball


def _conf_para(tarball: Path) -> dict[str, str]:
    return {
        "name": PIN_NAME,
        "url": "https://example.invalid/pin.tar.gz",
        "sha256": pp.sha256_of_file(tarball),
    }


def test_ensure_extrai_do_cache_e_depois_vira_noop_offline(tmp_path):
    tarball = _make_tarball(tmp_path)
    conf = _conf_para(tarball)
    compat = tmp_path / "compat"
    cache = tmp_path / "cache"
    cache.mkdir()
    tarball.rename(cache / f"{PIN_NAME}.tar.gz")

    chamadas: list[str] = []

    def downloader(url: str, dest: Path) -> None:
        chamadas.append(url)

    r1 = pp.ensure_pinned_proton(
        conf, compat_dir=compat, cache_dir=cache, downloader=downloader
    )
    assert r1.state == "installed_from_cache"
    assert (compat / PIN_NAME / "proton").is_file()
    manifest = json.loads(
        (compat / PIN_NAME / pp.MANIFEST_BASENAME).read_text(encoding="utf-8")
    )
    assert manifest["sha256"] == conf["sha256"]

    r2 = pp.ensure_pinned_proton(
        conf, compat_dir=compat, cache_dir=cache, downloader=downloader
    )
    assert r2.state == "already"
    assert chamadas == []


def test_ensure_respeita_instalacao_preexistente_sem_manifesto(tmp_path):
    """Dir válido da usuária (ex.: via ProtonUp) é dado do usuário — mantido."""
    conf = {"name": PIN_NAME, "url": "https://x.invalid/t.tar.gz", "sha256": "ab" * 32}
    compat = tmp_path / "compat"
    (compat / PIN_NAME).mkdir(parents=True)
    (compat / PIN_NAME / "proton").write_text("#!", encoding="utf-8")
    (compat / PIN_NAME / "version").write_text("x", encoding="utf-8")
    r = pp.ensure_pinned_proton(
        conf, compat_dir=compat, cache_dir=tmp_path / "cache", downloader=None
    )
    assert r.state == "already"
    assert "pré-existente" in r.detail


def test_ensure_checksum_errado_no_cache_aborta_sem_extrair(tmp_path):
    """O invariante central: NUNCA extrair binário não verificado."""
    tarball = _make_tarball(tmp_path)
    conf = _conf_para(tarball)
    conf["sha256"] = "00" * 32
    compat = tmp_path / "compat"
    cache = tmp_path / "cache"
    cache.mkdir()
    tarball.rename(cache / f"{PIN_NAME}.tar.gz")
    r = pp.ensure_pinned_proton(
        conf, compat_dir=compat, cache_dir=cache, downloader=None
    )
    assert r.state == "checksum_mismatch"
    assert not (compat / PIN_NAME).exists()


def test_ensure_download_verificado_entra_e_alimenta_o_cache(tmp_path):
    tarball = _make_tarball(tmp_path)
    conf = _conf_para(tarball)
    compat = tmp_path / "compat"
    cache = tmp_path / "cache"

    def downloader(url: str, dest: Path) -> None:
        dest.write_bytes(tarball.read_bytes())

    r = pp.ensure_pinned_proton(
        conf, compat_dir=compat, cache_dir=cache, downloader=downloader
    )
    assert r.state == "downloaded"
    assert (compat / PIN_NAME / "proton").is_file()
    assert (cache / f"{PIN_NAME}.tar.gz").is_file()


def test_ensure_download_corrompido_nao_extrai_nem_envenena_o_cache(tmp_path):
    conf = {"name": PIN_NAME, "url": "https://x.invalid/t.tar.gz", "sha256": "ab" * 32}
    compat = tmp_path / "compat"
    cache = tmp_path / "cache"

    def downloader(url: str, dest: Path) -> None:
        dest.write_bytes(b"tarball corrompido (fixture)")

    r = pp.ensure_pinned_proton(
        conf, compat_dir=compat, cache_dir=cache, downloader=downloader
    )
    assert r.state == "checksum_mismatch"
    assert not (compat / PIN_NAME).exists()
    assert list(cache.glob("*.tar.gz")) == []


def test_ensure_sem_cache_e_sem_rede_e_pendencia_honesta(tmp_path):
    conf = {"name": PIN_NAME, "url": "https://x.invalid/t.tar.gz", "sha256": "ab" * 32}
    r = pp.ensure_pinned_proton(
        conf,
        compat_dir=tmp_path / "compat",
        cache_dir=tmp_path / "cache",
        downloader=None,
    )
    assert r.state == "unavailable"


def _config_vdf(ctm_entries: dict[str, str] | None) -> str:
    """config.vdf mínimo com a MESMA forma do real (visto ao vivo 2026-07-18)."""
    ctm = ""
    if ctm_entries is not None:
        blocos = "".join(
            f'{_TAB * 5}"{appid}"\n{_TAB * 5}{{\n'
            f'{_TAB * 6}"name"{_TAB * 2}"{nome}"\n'
            f'{_TAB * 6}"config"{_TAB * 2}""\n'
            f'{_TAB * 6}"priority"{_TAB * 2}"250"\n'
            f"{_TAB * 5}}}\n"
            for appid, nome in ctm_entries.items()
        )
        ctm = (
            f'{_TAB * 4}"CompatToolMapping"\n{_TAB * 4}{{\n'
            f"{blocos}{_TAB * 4}}}\n"
        )
    return (
        '"InstallConfigStore"\n{\n'
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f'{_TAB * 4}"ShaderCacheManager"\n{_TAB * 4}{{\n'
        f'{_TAB * 5}"HasCurrentBucket"{_TAB * 2}"1"\n'
        f"{_TAB * 4}}}\n"
        f"{ctm}"
        f'{_TAB * 4}"AutoUpdateWindowEnabled"{_TAB * 2}"1"\n'
        f"{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n"
    )


def test_build_cria_o_bloco_quando_ausente_com_global_e_appids():
    texto, changes = pp.build_compat_tool_mapping(
        _config_vdf(None), tool_name=PIN_NAME, appids=["1599660", "1971870"]
    )
    mapping = pp.extract_compat_tool_mapping(texto)
    assert mapping == {
        "0": PIN_NAME,
        "1599660": PIN_NAME,
        "1971870": PIN_NAME,
    }
    assert changes["0"]["action"] == "added"
    assert changes["0"]["previous_name"] == ""
    assert changes["0"]["ctm_created"] == "1"
    assert set(changes) == {"0", "1599660", "1971870"}
    assert '"priority"\t\t"75"' in texto
    assert '"priority"\t\t"250"' in texto
    assert '"HasCurrentBucket"\t\t"1"' in texto


def test_build_troca_entrada_existente_e_registra_o_nome_anterior():
    original = _config_vdf({"0": "proton_11", "1971870": PIN_NAME})
    texto, changes = pp.build_compat_tool_mapping(
        original, tool_name=PIN_NAME, appids=["1971870"]
    )
    assert pp.extract_compat_tool_mapping(texto)["0"] == PIN_NAME
    assert changes == {"0": {"action": "replaced", "previous_name": "proton_11"}}
    diferentes = [
        (a, b)
        for a, b in zip(original.splitlines(), texto.splitlines(), strict=True)
        if a != b
    ]
    assert len(diferentes) == 1
    assert '"name"' in diferentes[0][0]


def test_build_e_idempotente():
    original = _config_vdf({"0": PIN_NAME, "1971870": PIN_NAME})
    texto, changes = pp.build_compat_tool_mapping(
        original, tool_name=PIN_NAME, appids=["1971870"]
    )
    assert texto == original
    assert changes == {}


def test_build_explode_em_arquivo_que_nao_e_config_vdf():
    with pytest.raises(ValueError, match="Software/Valve/Steam"):
        pp.build_compat_tool_mapping(
            '"Outro"\n{\n}\n', tool_name=PIN_NAME, appids=[]
        )


def test_remove_do_que_foi_adicionado_e_roundtrip_byte_a_byte():
    """add → remove volta ao arquivo ORIGINAL (o uninstall simétrico da casa)."""
    original = _config_vdf({"1245620": "proton_11"})
    travado, changes = pp.build_compat_tool_mapping(
        original, tool_name=PIN_NAME, appids=["1599660"]
    )
    revertido, n = pp.remove_compat_tool_mapping(
        travado, tool_name=PIN_NAME, changes=changes
    )
    assert n == 2
    assert revertido == original


def test_remove_fecha_roundtrip_no_caso_sem_ctm_previo():
    """Achado #7: sem CompatToolMapping prévio o lock cria o bloco INTEIRO; o"""
    original = _config_vdf(None)
    travado, changes = pp.build_compat_tool_mapping(
        original, tool_name=PIN_NAME, appids=["1599660", "1971870"]
    )
    assert "CompatToolMapping" in travado
    revertido, n = pp.remove_compat_tool_mapping(
        travado, tool_name=PIN_NAME, changes=changes
    )
    assert n == 3
    assert "CompatToolMapping" not in revertido
    assert revertido == original


def test_remove_preserva_bloco_criado_por_nos_se_usuaria_assumiu_uma_entrada():
    """Achado #7 (contra-caso): se a usuária mudou UMA entrada do bloco que"""
    original = _config_vdf(None)
    travado, changes = pp.build_compat_tool_mapping(
        original, tool_name=PIN_NAME, appids=["1599660"]
    )
    mudado = travado.replace(
        f'"name"\t\t"{PIN_NAME}"', '"name"\t\t"proton_experimental"', 1
    )
    revertido, n = pp.remove_compat_tool_mapping(
        mudado, tool_name=PIN_NAME, changes=changes
    )
    assert "CompatToolMapping" in revertido
    assert "proton_experimental" in revertido
    assert n == 1


def test_remove_restaura_o_nome_anterior_de_entrada_trocada():
    original = _config_vdf({"0": "proton_11"})
    travado, changes = pp.build_compat_tool_mapping(
        original, tool_name=PIN_NAME, appids=[]
    )
    revertido, n = pp.remove_compat_tool_mapping(
        travado, tool_name=PIN_NAME, changes=changes
    )
    assert n == 1
    assert revertido == original


def test_remove_nao_toca_entrada_que_a_usuaria_mudou_depois_do_lock():
    """Ela trocou o tool depois do nosso lock = ela assumiu; é dela agora."""
    travado, changes = pp.build_compat_tool_mapping(
        _config_vdf(None), tool_name=PIN_NAME, appids=["1599660"]
    )
    mudado = travado.replace(
        f'"name"\t\t"{PIN_NAME}"', '"name"\t\t"proton_experimental"', 1
    )
    revertido, n = pp.remove_compat_tool_mapping(
        mudado, tool_name=PIN_NAME, changes=changes
    )
    mapping = pp.extract_compat_tool_mapping(revertido)
    assert "proton_experimental" in mapping.values()
    assert n < len(changes)


@pytest.fixture()
def steam_fechada(monkeypatch):
    monkeypatch.setattr(pp, "steam_running", lambda: False)
    monkeypatch.setattr(pp, "steam_game_running", lambda: False)


def test_lock_recusa_com_steam_aberta_sem_tocar_no_vdf(tmp_path, monkeypatch):
    monkeypatch.setattr(pp, "steam_running", lambda: True)
    monkeypatch.setattr(pp, "steam_game_running", lambda: False)
    vdf = tmp_path / "config.vdf"
    original = _config_vdf(None)
    vdf.write_text(original, encoding="utf-8")
    r = pp.lock_games_to_pinned_proton(
        tool_name=PIN_NAME,
        appids=["1599660"],
        config_vdf=vdf,
        state_path=tmp_path / "state.json",
    )
    assert r["status"] == "recusado"
    assert r["reason"] == "steam_aberta"
    assert vdf.read_text(encoding="utf-8") == original


def test_lock_recusa_jogo_aberto_com_precedencia(tmp_path, monkeypatch):
    """Jogo aberto vence: fechar a Steam agora MATARIA o jogo (DEDUP-05)."""
    monkeypatch.setattr(pp, "steam_running", lambda: True)
    monkeypatch.setattr(pp, "steam_game_running", lambda: True)
    vdf = tmp_path / "config.vdf"
    vdf.write_text(_config_vdf(None), encoding="utf-8")
    r = pp.lock_games_to_pinned_proton(
        tool_name=PIN_NAME,
        appids=[],
        config_vdf=vdf,
        state_path=tmp_path / "state.json",
    )
    assert r["reason"] == "jogo_da_steam_aberto"


def test_lock_escreve_backup_estado_e_unlock_reverte_tudo(
    tmp_path, steam_fechada
):
    vdf = tmp_path / "config.vdf"
    original = _config_vdf({"1245620": "proton_11"})
    vdf.write_text(original, encoding="utf-8")
    state = tmp_path / "state" / "proton-pin-lock.json"

    r = pp.lock_games_to_pinned_proton(
        tool_name=PIN_NAME,
        appids=["1599660"],
        config_vdf=vdf,
        state_path=state,
    )
    assert r["status"] == "locked"
    assert pp.extract_compat_tool_mapping(vdf.read_text(encoding="utf-8"))[
        "0"
    ] == PIN_NAME
    backups = list(tmp_path.glob("config.vdf.bak.hefesto-proton-*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == original
    registro = json.loads(state.read_text(encoding="utf-8"))
    assert registro["tool_name"] == PIN_NAME
    assert set(registro["changes"]) == {"0", "1599660"}

    u = pp.unlock_games_from_pinned_proton(config_vdf=vdf, state_path=state)
    assert u["status"] == "unlocked"
    assert u["reverted"] == 2
    assert vdf.read_text(encoding="utf-8") == original
    assert not state.exists()


def test_lock_repetido_e_noop_e_preserva_o_registro_original(
    tmp_path, steam_fechada
):
    vdf = tmp_path / "config.vdf"
    vdf.write_text(_config_vdf({"0": "proton_11"}), encoding="utf-8")
    state = tmp_path / "state.json"
    r1 = pp.lock_games_to_pinned_proton(
        tool_name=PIN_NAME, appids=[], config_vdf=vdf, state_path=state
    )
    assert r1["status"] == "locked"
    r2 = pp.lock_games_to_pinned_proton(
        tool_name=PIN_NAME, appids=[], config_vdf=vdf, state_path=state
    )
    assert r2["status"] == "noop"
    registro = json.loads(state.read_text(encoding="utf-8"))
    assert registro["changes"]["0"]["previous_name"] == "proton_11"


def test_unlock_sem_estado_e_noop_sem_tocar_no_vdf(tmp_path, steam_fechada):
    vdf = tmp_path / "config.vdf"
    original = _config_vdf({"0": PIN_NAME})
    vdf.write_text(original, encoding="utf-8")
    u = pp.unlock_games_from_pinned_proton(
        config_vdf=vdf, state_path=tmp_path / "inexistente.json"
    )
    assert u["status"] == "noop"
    assert u["reason"] == "sem_estado"
    assert vdf.read_text(encoding="utf-8") == original


def test_lock_falha_do_estado_nao_deixa_o_vdf_pinado_sem_reversao(
    tmp_path, steam_fechada, monkeypatch
):
    """Achado #5: se a persistência do registro falhar (OSError), o config.vdf"""
    vdf = tmp_path / "config.vdf"
    original = _config_vdf({"0": "proton_11"})
    vdf.write_text(original, encoding="utf-8")
    state = tmp_path / "state" / "proton-pin-lock.json"

    def boom(*_a, **_k):
        raise OSError("estado somente-leitura (fixture)")

    monkeypatch.setattr(pp, "_merge_lock_state", boom)
    r = pp.lock_games_to_pinned_proton(
        tool_name=PIN_NAME, appids=["1599660"], config_vdf=vdf, state_path=state
    )
    assert r["status"] == "erro"
    assert vdf.read_text(encoding="utf-8") == original
    assert not state.exists()


def test_lock_proton_for_all_games_zero_arg_traduz_o_contrato_da_gui(
    tmp_path, steam_fechada
):
    """Achado #4: o botão "Travar Proton validado" chama esta função ZERO-ARG."""
    steamapps = tmp_path / ".steam/steam/steamapps"
    steamapps.mkdir(parents=True)
    (steamapps / "appmanifest_1599660.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"1599660"\n\t"name"\t\t"Sackboy"\n}\n',
        encoding="utf-8",
    )
    (steamapps / "compatdata" / "1599660").mkdir(parents=True)
    pino = tmp_path / ".steam/steam/compatibilitytools.d" / PIN_NAME
    pino.mkdir(parents=True)
    (pino / "proton").write_text("#!/bin/sh\n", encoding="utf-8")
    (pino / "version").write_text(f"1 {PIN_NAME}\n", encoding="utf-8")
    vdf = tmp_path / "config.vdf"
    vdf.write_text(_config_vdf(None), encoding="utf-8")
    state = tmp_path / "state" / "proton-pin-lock.json"
    conf = {"name": PIN_NAME, "url": "https://x.invalid/t.tar.gz", "sha256": "ab" * 32}

    result = pp.lock_proton_for_all_games(
        conf=conf, home=tmp_path, config_vdf=vdf, state_path=state
    )
    assert set(result) >= {"locked", "skipped", "errors", "tool"}
    assert result["tool"] == PIN_NAME
    assert result["errors"] == 0
    assert result["locked"] == 2
    mapping = pp.extract_compat_tool_mapping(vdf.read_text(encoding="utf-8"))
    assert mapping["0"] == PIN_NAME
    assert mapping["1599660"] == PIN_NAME
    assert state.exists()


def test_lock_proton_for_all_games_e_chamavel_sem_argumentos():
    """A assinatura tem que aceitar `lock_proton_for_all_games()` (o worker da
    GUI chama zero-arg) — nenhum parâmetro posicional obrigatório."""
    import inspect

    assert callable(pp.lock_proton_for_all_games)
    for p in inspect.signature(pp.lock_proton_for_all_games).parameters.values():
        assert p.kind in (p.KEYWORD_ONLY, p.VAR_KEYWORD)
        assert p.kind == p.VAR_KEYWORD or p.default is not inspect.Parameter.empty


@pytest.mark.parametrize(
    ("nome", "major"),
    [
        ("GE-Proton10-34", 10),
        ("GE-Proton9-27", 9),
        ("proton_9", 9),
        ("proton_8", 8),
        ("proton_63", 6),
        ("proton_513", 5),
        ("proton_411", 4),
        ("proton_316", 3),
        ("proton_10", 10),
        ("proton_11", 11),
        ("proton_experimental", None),
        ("steamlinuxruntime", None),
        ("", None),
    ],
)
def test_proton_major(nome, major):
    assert pp.proton_major(nome) == major


def test_report_completo(tmp_path):
    conf = {"name": PIN_NAME, "url": "https://x.invalid/t.tar.gz", "sha256": "ab" * 32}
    compat = tmp_path / "compat"
    (compat / PIN_NAME).mkdir(parents=True)
    (compat / PIN_NAME / "proton").write_text("#!", encoding="utf-8")
    (compat / PIN_NAME / "version").write_text("x", encoding="utf-8")
    (compat / PIN_NAME / pp.MANIFEST_BASENAME).write_text(
        json.dumps({"sha256": "ab" * 32}), encoding="utf-8"
    )
    texto = _config_vdf({"0": PIN_NAME, "1245620": "proton_9", "2497900": "proton_11"})
    report = pp.proton_pin_report(
        conf,
        compat_dir=compat,
        config_vdf_text=texto,
        installed_appids=["1245620", "2497900", "1599660"],
    )
    assert report["pinned_present"] is True
    assert report["pinned_manifest_ok"] is True
    assert report["global_is_pinned"] is True
    assert report["games_off_pin"] == ["1245620", "2497900"]
    assert report["games_leaky_proton"] == [("1245620", "proton_9")]


def test_report_sem_pin_presente_e_global_alheio(tmp_path):
    conf = {"name": PIN_NAME, "url": "https://x.invalid/t.tar.gz", "sha256": "ab" * 32}
    texto = _config_vdf({"0": "proton_9"})
    report = pp.proton_pin_report(
        conf,
        compat_dir=tmp_path / "compat",
        config_vdf_text=texto,
        installed_appids=["42"],
    )
    assert report["pinned_present"] is False
    assert report["global_is_pinned"] is False
    assert report["games_off_pin"] == ["42"]
    assert report["games_leaky_proton"] == [("42", "proton_9")]


def test_list_installed_appids_filtra_ferramentas(tmp_path):
    steamapps = tmp_path / ".steam/steam/steamapps"
    steamapps.mkdir(parents=True)

    def manifest(appid: str, nome: str) -> None:
        (steamapps / f"appmanifest_{appid}.acf").write_text(
            f'"AppState"\n{{\n\t"appid"\t\t"{appid}"\n'
            f'\t"name"\t\t"{nome}"\n}}\n',
            encoding="utf-8",
        )

    manifest("1599660", "Sackboy: A Big Adventure")
    manifest("1245620", "ELDEN RING")
    manifest("2805730", "Proton 9.0 (Beta)")
    manifest("1628350", "Steam Linux Runtime 3.0 (sniper)")
    manifest("228980", "Steamworks Common Redistributables")
    assert pp.list_installed_appids(home=tmp_path) == ["1245620", "1599660"]


_VDF_COM_ESCOLHA_DELA = """"UserLocalConfigStore"
{
\t"Software"
\t{
\t\t"Valve"
\t\t{
\t\t\t"Steam"
\t\t\t{
\t\t\t\t"CompatToolMapping"
\t\t\t\t{
\t\t\t\t\t"2497900"
\t\t\t\t\t{
\t\t\t\t\t\t"name"\t\t"proton_11"
\t\t\t\t\t\t"config"\t\t""
\t\t\t\t\t\t"priority"\t\t"250"
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t}
}
"""


def test_o_lock_nao_atropela_o_proton_que_ela_escolheu() -> None:
    """A MORDIDA. Tire o `if not atropelar_escolha_dela` e isto fica vermelho."""
    texto, changes = pp.build_compat_tool_mapping(
        _VDF_COM_ESCOLHA_DELA,
        tool_name="GE-Proton10-34",
        appids=["2497900"],
    )

    assert changes["2497900"]["action"] == "preservado", (
        "o lock diz ter feito "
        f"{changes['2497900']['action']} num jogo em que ela JÁ tinha escolhido "
        "o Proton — foi assim que o DON'T SCREAM perdeu o microfone em 14/08"
    )
    assert changes["2497900"]["previous_name"] == "proton_11"
    assert '"name"\t\t"proton_11"' in texto, (
        "a linha do Proton DELA foi reescrita no config.vdf: o produto atropelou "
        "uma escolha deliberada, que é exatamente o defeito de 14/08"
    )
    corpo = texto.split('"2497900"', 1)[1].split("}", 1)[0]
    assert "GE-Proton10-34" not in corpo, (
        "o Proton do produto entrou no bloco do jogo dela"
    )


def test_quem_nao_tinha_escolha_continua_ganhando_o_proton_validado() -> None:
    """A cura não pode virar cadeado: jogo SEM escolha continua sendo travado."""
    _, changes = pp.build_compat_tool_mapping(
        _VDF_COM_ESCOLHA_DELA,
        tool_name="GE-Proton10-34",
        appids=["2497900", "851100"],
    )
    assert changes["851100"]["action"] == "added", (
        "jogo que não tinha escolha nenhuma deixou de receber o Proton validado — "
        "a cura foi longe demais"
    )
    assert changes["2497900"]["action"] == "preservado"


def test_a_contagem_nao_chama_de_travado_o_que_foi_preservado() -> None:
    """`locked` contava tudo, inclusive o que o produto respeitou."""
    changes = {
        "0": {"action": "added", "previous_name": ""},
        "851100": {"action": "added", "previous_name": ""},
        "2497900": {"action": "preservado", "previous_name": "proton_11"},
    }
    locked = sum(
        1 for c in changes.values()
        if isinstance(c, dict) and c.get("action") != "preservado"
    )
    preservados = sum(
        1 for c in changes.values()
        if isinstance(c, dict) and c.get("action") == "preservado"
    )
    assert (locked, preservados) == (2, 1), (
        "a contagem somaria 3 travados numa leva em que 1 foi respeitado"
    )
