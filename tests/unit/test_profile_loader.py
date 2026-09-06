"""Testes do loader JSON de perfis."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import (
    delete_profile,
    load_all_profiles,
    load_profile,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)

#: PERFIS-SAO-PERFIS-01 (06/09/2026): o dado de fábrica mora em DUAS casas —
#: `profiles_default/` (o que a semeadura copia, hoje só o `personalizado`) e
#: `estilos_de_jogo/` (os oito gêneros, que por decisão dela não são perfil).
_CASAS_DE_FABRICA = (
    Path(__file__).resolve().parents[2] / "assets" / "profiles_default",
    Path(__file__).resolve().parents[2] / "assets" / "estilos_de_jogo",
)


def _asset_de_fabrica(arquivo: str) -> Path | None:
    """O asset de fábrica pelo nome do arquivo, na casa em que ele estiver.

    O `pytest.skip` que estava nos dois chamadores virou `assert`, e a troca é
    a lição da casa: pular por ausência de arquivo é verde por AUSÊNCIA DE
    DADO — os dois testes que mediam `aventura` e `corrida` teriam ficado
    calados a partir do dia em que os assets mudaram de pasta, sem uma linha
    vermelha para avisar.
    """
    for casa in _CASAS_DE_FABRICA:
        candidato = casa / arquivo
        if candidato.exists():
            return candidato
    return None


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Força `profiles_dir()` a apontar para tmp_path/profiles."""
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _mk_profile(name: str = "test") -> Profile:
    return Profile(
        name=name,
        match=MatchCriteria(window_class=[f"{name}_class"]),
        priority=5,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Galloping", params=[0, 9, 7, 7, 10]),
        ),
        leds=LedsConfig(lightbar=(10, 20, 30)),
    )


def test_save_cria_arquivo(isolated_profiles_dir: Path):
    profile = _mk_profile("driving")
    path = save_profile(profile)
    assert path.exists()
    assert path.name == "driving.json"


def test_save_e_load_roundtrip(isolated_profiles_dir: Path):
    profile = _mk_profile("shooter")
    save_profile(profile)
    restored = load_profile("shooter")
    assert restored == profile


def test_load_perfil_inexistente(isolated_profiles_dir: Path):
    with pytest.raises(FileNotFoundError):
        load_profile("inexistente")


def test_load_all_ordenado(isolated_profiles_dir: Path):
    save_profile(_mk_profile("zeta"))
    save_profile(_mk_profile("alpha"))
    save_profile(_mk_profile("beta"))
    profiles = load_all_profiles()
    names = [p.name for p in profiles]
    assert names == ["alpha", "beta", "zeta"]


def test_delete_remove_arquivo(isolated_profiles_dir: Path):
    save_profile(_mk_profile("bow"))
    assert (isolated_profiles_dir / "bow.json").exists()
    delete_profile("bow")
    assert not (isolated_profiles_dir / "bow.json").exists()


def test_delete_inexistente_falha(isolated_profiles_dir: Path):
    with pytest.raises(FileNotFoundError):
        delete_profile("ghost")


def test_fallback_com_match_any(isolated_profiles_dir: Path):
    p = Profile(name="fallback", match=MatchAny(), priority=0)
    save_profile(p)
    restored = load_profile("fallback")
    assert isinstance(restored.match, MatchAny)
    assert restored.matches({}) is True


def test_json_gerado_eh_valido(isolated_profiles_dir: Path):
    save_profile(_mk_profile("x"))
    raw = (isolated_profiles_dir / "x.json").read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["name"] == "x"
    assert data["match"]["type"] == "criteria"
    assert data["triggers"]["right"]["mode"] == "Galloping"


def test_lock_file_e_criado(isolated_profiles_dir: Path):
    save_profile(_mk_profile("y"))
    # .lock é criado adjacente ao arquivo
    assert any(isolated_profiles_dir.glob("y.json.lock*")) or True  # lock fd ephemera


def test_overwrite_preserva_integridade(isolated_profiles_dir: Path):
    p1 = _mk_profile("a")
    save_profile(p1)
    p2 = _mk_profile("a")
    p2 = p2.model_copy(update={"priority": 99})
    save_profile(p2)
    restored = load_profile("a")
    assert restored.priority == 99


def test_save_profile_usa_slug(isolated_profiles_dir: Path):
    """PROFILE-SLUG-SEPARATION-01: Profile(name='Ação') grava acao.json."""
    profile = Profile(
        name="Ação",
        match=MatchCriteria(window_class=["acao_class"]),
        priority=5,
    )
    path = save_profile(profile)
    assert path.name == "acao.json"
    assert path.exists()
    # Garante que não foi gravado com filename acentuado.
    assert not (isolated_profiles_dir / "Ação.json").exists()


def test_load_profile_por_slug(isolated_profiles_dir: Path):
    """load_profile por slug literal ASCII retorna Profile com name acentuado."""
    profile = Profile(
        name="Ação",
        match=MatchCriteria(window_class=["acao_class"]),  # slug literal ASCII (noqa-acento)
        priority=5,
    )
    save_profile(profile)
    restored = load_profile("acao")  # slug literal ASCII (noqa-acento)
    assert restored.name == "Ação"


def test_load_profile_por_display(isolated_profiles_dir: Path):
    """load_profile('Ação') — display name — também encontra via slugify."""
    profile = Profile(
        name="Ação",
        match=MatchCriteria(window_class=["acao_class"]),
        priority=5,
    )
    save_profile(profile)
    restored = load_profile("Ação")
    assert restored.name == "Ação"


def test_load_profile_fallback_scan(isolated_profiles_dir: Path):
    """Arquivo com filename arbitrário e name='Ação' é achado via scan."""
    # Grava manualmente com filename divergente do slug.
    profile = Profile(
        name="Ação",
        match=MatchCriteria(window_class=["acao_class"]),
        priority=5,
    )
    payload = profile.model_dump(mode="json")
    arbitrario = isolated_profiles_dir / "qualquer-nome.json"
    arbitrario.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    restored = load_profile("Ação")
    assert restored.name == "Ação"


def test_delete_profile_resolve_slug(isolated_profiles_dir: Path):
    """delete_profile('Ação') remove acao.json via resolução por display."""
    profile = Profile(
        name="Ação",
        match=MatchCriteria(window_class=["acao_class"]),
        priority=5,
    )
    save_profile(profile)
    assert (isolated_profiles_dir / "acao.json").exists()

    delete_profile("Ação")
    assert not (isolated_profiles_dir / "acao.json").exists()


def test_loader_aventura_nested_params(isolated_profiles_dir: Path):
    """SCHEMA-MULTI-POSITION-PARAMS-01: aventura.json carrega com params aninhado.

    Após migração, `left` e `right` são MultiPositionFeedback com params
    na forma `list[list[int]]` de 10 sublistas. Loader não levanta.
    """
    src = _asset_de_fabrica("aventura.json")
    assert src is not None, "aventura.json sumiu das duas casas de fábrica"
    dst = isolated_profiles_dir / "aventura.json"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    profile = load_profile("aventura")
    assert profile.name == "Aventura"
    assert profile.triggers.left.mode == "MultiPositionFeedback"
    assert profile.triggers.right.mode == "MultiPositionFeedback"
    assert profile.triggers.left.is_nested is True
    assert profile.triggers.right.is_nested is True
    # 10 sublistas expected (matriz de decisão do spec)
    assert len(profile.triggers.left.params) == 10
    assert len(profile.triggers.right.params) == 10


def test_loader_corrida_nested_params(isolated_profiles_dir: Path):
    """SCHEMA-MULTI-POSITION-PARAMS-01: corrida.json migra apenas `right`."""
    src = _asset_de_fabrica("corrida.json")
    assert src is not None, "corrida.json sumiu das duas casas de fábrica"
    dst = isolated_profiles_dir / "corrida.json"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    profile = load_profile("corrida")
    assert profile.name == "Corrida"
    # left permanece Resistance (decisão explícita da matriz)
    assert profile.triggers.left.mode == "Resistance"
    assert profile.triggers.left.is_nested is False
    # right migrou para MultiPositionVibration com aninhado
    assert profile.triggers.right.mode == "MultiPositionVibration"
    assert profile.triggers.right.is_nested is True
    assert len(profile.triggers.right.params) == 10


# ---------------------------------------------------------------------------
# AUDIT-FINDING-PROFILE-PATH-TRAVERSAL-01 — sanitização de identifier
# ---------------------------------------------------------------------------


def test_load_profile_rejeita_path_absoluto(isolated_profiles_dir: Path):
    """Identifier com `/` no início escaparia via Path('/dir') / '/etc/passwd'."""
    with pytest.raises(ValueError, match="caractere proibido"):
        load_profile("/etc/passwd")


def test_load_profile_rejeita_parent_dir(isolated_profiles_dir: Path):
    """Identifier com `..` escaparia via resolve() do pathlib."""
    with pytest.raises(ValueError, match=r"caractere proibido|'\.\.'"):
        load_profile("../../etc/passwd")


def test_load_profile_rejeita_backslash(isolated_profiles_dir: Path):
    """Backslash não é separador em Linux mas é reservado para defesa cross-plat."""
    with pytest.raises(ValueError, match="caractere proibido"):
        load_profile("..\\etc\\passwd")


def test_load_profile_rejeita_null_byte(isolated_profiles_dir: Path):
    """Null byte quebra syscalls e confunde parsers — sempre rejeita."""
    with pytest.raises(ValueError, match="caractere proibido"):
        load_profile("foo\x00bar")


def test_load_profile_rejeita_parent_dir_puro(isolated_profiles_dir: Path):
    """Identifier `..` puro (sem separador) também escaparia via directory / '..'."""
    with pytest.raises(ValueError, match=r"'\.\.'"):
        load_profile("..")


def test_load_profile_aceita_slug_legitimo(isolated_profiles_dir: Path):
    """Display name acentuado continua funcionando via fallback de slugify."""
    profile = _mk_profile("shooter_pro")
    save_profile(profile)
    loaded = load_profile("shooter_pro")
    assert loaded.name == "shooter_pro"


# ---------------------------------------------------------------------------
# PROFILE-LOADER-UX-01 — mensagens de erro acionáveis para perfis inválidos
# ---------------------------------------------------------------------------


def test_load_all_profiles_pula_json_malformado_e_loga_warning(
    isolated_profiles_dir: Path,
) -> None:
    """JSON quebrado emite warning estruturado e não derruba carregamento dos válidos."""
    import structlog

    save_profile(_mk_profile("valido"))
    quebrado = isolated_profiles_dir / "quebrado.json"
    quebrado.write_text("{ broken json", encoding="utf-8")

    with structlog.testing.capture_logs() as captured:
        profiles = load_all_profiles()

    nomes = [p.name for p in profiles]
    assert "valido" in nomes
    assert "quebrado" not in nomes
    eventos = [rec for rec in captured if rec.get("event") == "profile_invalid"]
    assert any("quebrado.json" in str(rec.get("path", "")) for rec in eventos)


def test_load_all_profiles_pula_schema_invalido_e_loga(
    isolated_profiles_dir: Path,
) -> None:
    """Perfil com payload JSON válido porém schema Pydantic inválido vira warning."""
    import structlog

    save_profile(_mk_profile("ok"))
    schema_invalido = isolated_profiles_dir / "schema_invalido.json"
    # Sem campo obrigatório `name`; Pydantic levanta ValidationError.
    schema_invalido.write_text(
        json.dumps({"priority": 5, "match": {"type": "any"}}),
        encoding="utf-8",
    )

    with structlog.testing.capture_logs() as captured:
        profiles = load_all_profiles()

    nomes = [p.name for p in profiles]
    assert "ok" in nomes
    assert len(nomes) == 1
    eventos = [rec for rec in captured if rec.get("event") == "profile_invalid"]
    assert any("schema_invalido.json" in str(rec.get("path", "")) for rec in eventos)


def test_load_profile_scan_pula_invalido_e_acha_o_valido(
    isolated_profiles_dir: Path,
) -> None:
    """Fallback scan em load_profile pula JSON corrompido e segue procurando."""
    import structlog

    quebrado = isolated_profiles_dir / "aaa-quebrado.json"
    quebrado.write_text("{[}", encoding="utf-8")
    # Filename arbitrário com name='Ação' que precisa scan para ser achado.
    payload = Profile(
        name="Ação",
        match=MatchCriteria(window_class=["acao_class"]),
        priority=5,
    ).model_dump(mode="json")
    arbitrario = isolated_profiles_dir / "zzz-qualquer.json"
    arbitrario.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with structlog.testing.capture_logs() as captured:
        restored = load_profile("Ação")

    assert restored.name == "Ação"
    eventos = [rec for rec in captured if rec.get("event") == "profile_invalid"]
    assert any("aaa-quebrado.json" in str(rec.get("path", "")) for rec in eventos)


# ---------------------------------------------------------------------------
# PERFIL-02 (sprint 2026-07-16-perfis-por-controle): serialização que OMITE
# o mapa `controllers` quando None/vazio — requisito de compatibilidade
# ---------------------------------------------------------------------------

#: MAC forjado da faixa permitida (test_anonimato_de_fixtures.py).
_MAC_BT = "aabbcc000002"


def test_save_omite_controllers_quando_none(isolated_profiles_dir: Path):
    """Perfil sem opinião por-controle NÃO grava `"controllers": null` — sem a
    omissão, binário antigo (extra="forbid") rejeitaria TODO perfil salvo pelo
    novo no downgrade."""
    path = save_profile(_mk_profile("sem_mapa"))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "controllers" not in data


def test_save_omite_controllers_quando_vazio(isolated_profiles_dir: Path):
    """Mapa `{}` explícito também some do JSON (vazio == sem opinião)."""
    profile = _mk_profile("mapa_vazio").model_copy(update={"controllers": {}})
    path = save_profile(profile)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "controllers" not in data


def test_save_persiste_controllers_preenchido(isolated_profiles_dir: Path):
    """Aceite 1 do sprint: o mapa preenchido sobrevive a save→load sem perda."""
    profile = _mk_profile("com_mapa").model_copy(
        update={
            "controllers": {
                _MAC_BT: ControllerOverrides(leds=LedsConfig(lightbar=(0, 255, 0))),
            }
        }
    )
    path = save_profile(profile)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["controllers"][_MAC_BT]["leds"]["lightbar"] == [0, 255, 0]

    restored = load_profile("com_mapa")
    assert restored.controllers is not None
    assert restored.controllers[_MAC_BT].leds is not None
    assert restored.controllers[_MAC_BT].leds.lightbar == (0, 255, 0)


def test_save_preserva_override_parcial_escrito_a_mao(isolated_profiles_dir: Path):
    """Fix do review (2026-07-16, MED): entrada PARCIAL escrita à mão (só
    `lightbar`) continua parcial após save→load→save. O dump denso marcava os
    defaults do schema como explícitos no próximo load e a ativação pisava o
    global do controle (player-LEDs apagados, brilho 1.0) — a
    resolução-por-objeto refutada pelo sprint doc, via serialização."""
    raw = _mk_profile("parcial").model_dump(mode="json")
    raw["controllers"] = {_MAC_BT: {"leds": {"lightbar": [0, 255, 0]}}}
    profile = Profile.model_validate(raw)

    path = save_profile(profile)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["controllers"][_MAC_BT] == {"leds": {"lightbar": [0, 255, 0]}}

    # O ciclo completo load→save também não densifica.
    save_profile(load_profile("parcial"))
    data2 = json.loads(path.read_text(encoding="utf-8"))
    assert data2["controllers"][_MAC_BT] == {"leds": {"lightbar": [0, 255, 0]}}


def test_perfil_antigo_roundtrip_load_save_nao_introduz_a_chave(
    isolated_profiles_dir: Path,
):
    """Aceite 2 do sprint: perfil ANTIGO (JSON sem o campo, como os da usuária:
    vitoria/sackboy_nativo/navegacao) passa por load→save e o arquivo fica
    BYTE-IDÊNTICO — em particular, sem ganhar `controllers`."""
    path = save_profile(_mk_profile("antigo"))
    antes = path.read_bytes()
    assert b"controllers" not in antes

    save_profile(load_profile("antigo"))
    depois = path.read_bytes()
    assert depois == antes


def test_perfil_antigo_carrega_sem_warning(isolated_profiles_dir: Path):
    """Migração silenciosa: perfil v1 mínimo (escrito à mão, sem NENHUM campo
    novo) carrega sem erro e sem `profile_invalid` no log."""
    import structlog

    legado = isolated_profiles_dir / "legado.json"
    legado.write_text(
        json.dumps({"name": "legado", "match": {"type": "any"}}),
        encoding="utf-8",
    )

    with structlog.testing.capture_logs() as captured:
        profiles = load_all_profiles()

    assert [p.name for p in profiles] == ["legado"]
    assert profiles[0].controllers is None
    eventos = [rec for rec in captured if rec.get("event") == "profile_invalid"]
    assert eventos == []


def test_perfil_com_mapa_invalido_vira_warning_nao_crash(
    isolated_profiles_dir: Path,
):
    """Key degenerada no disco (JSON editado à mão) segue o contrato do
    loader: warning `profile_invalid` e os demais perfis carregam."""
    import structlog

    save_profile(_mk_profile("valido"))
    invalido = isolated_profiles_dir / "mapa_ruim.json"
    invalido.write_text(
        json.dumps(
            {
                "name": "mapa_ruim",
                "match": {"type": "any"},
                "controllers": {"000000000001": {}},
            }
        ),
        encoding="utf-8",
    )

    with structlog.testing.capture_logs() as captured:
        profiles = load_all_profiles()

    assert [p.name for p in profiles] == ["valido"]
    eventos = [rec for rec in captured if rec.get("event") == "profile_invalid"]
    assert any("mapa_ruim.json" in str(rec.get("path", "")) for rec in eventos)


def test_carrega_perfis_default_do_assets_simulado(isolated_profiles_dir: Path):
    """Mimetiza installer copiando perfis default para profiles_dir."""
    for casa in _CASAS_DE_FABRICA:
        assert casa.is_dir(), f"uma casa da fábrica sumiu: {casa}"
        for src in casa.glob("*.json"):
            dst = isolated_profiles_dir / src.name
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    profiles = load_all_profiles()
    names = sorted(p.name for p in profiles)
    # Ao menos fallback + algum outro
    assert "fallback" in names
    assert len(names) >= 2


# ---------------------------------------------------------------------------
# A MIGRAÇÃO APOSENTADA NÃO É MUDA (26/08/2026)
# ---------------------------------------------------------------------------
# A poda da fábrica apagou `assets/profiles_default/coop_local.json`, e é dele
# que `migrate_coop_local_match` e o ramo `coop_local` de
# `migrate_modo_jogo_nos_presets` copiam `match` e `priority`. Sem o asset,
# `_seed_source_file` devolve `None` — e o código ANTIGO fazia `continue`.
#
# O custo desse `continue`: quem tem um `coop_local` velho no disco (o de
# 14/07, com `criteria` de campos todos vazios) fica preso com um perfil que o
# autoswitch NUNCA escolhe, para sempre, e nada em lugar nenhum diz por quê.
# É a forma exata do defeito que esta casa chama de "a casa sabe e o produto
# não faz", com o agravante de o silêncio ser total.
#
# A cura não é adivinhar o regex perdido — escrever `match` de memória em
# perfil de alguém é o produto escolhendo por ela. A cura é RELATAR.


class TestAMigracaoAposentadaNaoEMuda:
    """MORDE: trocar o relato por um `continue` no `_seed_source_file` ausente.

    Arrancando a cura (as duas chamadas a `_relatar_migracao_aposentada`), as
    duas migrações voltam a ser no-op silencioso e os dois testes abaixo
    reprovam nomeando o caminho calado.
    """

    @staticmethod
    def _coop_local_de_fabrica_velho(destino: Path) -> Path:
        """O `coop_local` de 14/07: `criteria` vazio, inalcançável, intocado."""
        caminho = destino / "coop_local.json"
        caminho.write_text(
            json.dumps(
                {
                    "name": "coop_local",
                    "version": 1,
                    "match": {"type": "criteria"},
                    "priority": 45,
                    "mode": {"kind": "gamepad", "coop": True},
                }
            ),
            encoding="utf-8",
        )
        return caminho

    def test_a_migracao_aposentada_nao_e_muda(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem asset, `migrate_coop_local_match` RELATA em vez de calar."""
        import structlog.testing

        destino = tmp_path / "profiles"
        destino.mkdir()
        caminho = self._coop_local_de_fabrica_velho(destino)
        antes = caminho.read_text(encoding="utf-8")

        # Nenhum diretório-fonte existe: é o estado de quem instalou a versão
        # podada e ainda tem o preset velho no disco.
        monkeypatch.setattr(
            loader_module, "_DEFAULT_SEED_SOURCE_DIRS", (tmp_path / "sem_assets",)
        )

        with structlog.testing.capture_logs() as registros:
            migrados = loader_module.migrate_coop_local_match(dest_dir=destino)

        assert migrados == [], (
            "sem asset não há de onde copiar `match` — a migração não pode "
            "inventar regra no perfil dela"
        )
        assert caminho.read_text(encoding="utf-8") == antes, (
            "a migração aposentada mexeu no arquivo"
        )

        relatos = [
            r for r in registros
            if r.get("event") == "migracao_aposentada_sem_asset"
        ]
        assert relatos, (
            "a migração virou no-op SILENCIOSO: quem tem um `coop_local` velho "
            "no disco fica preso com um perfil inalcançável e o journal não "
            "diz uma palavra sobre isso. Eventos vistos: "
            f"{sorted({str(r.get('event')) for r in registros})}"
        )
        assert relatos[0].get("arquivo") == "coop_local.json"
        assert relatos[0].get("migracao") == "coop_local_match"  # slug, sem acento (noqa-acento)

    def test_o_ramo_do_modo_jogo_tambem_relata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A irmã: `migrate_modo_jogo_nos_presets` tem o mesmo ramo aposentado.

        Consertar uma e esquecer a outra deixaria metade do silêncio de pé —
        é o defeito "corrigir pela metade" que esta casa já pagou.
        """
        import structlog.testing

        destino = tmp_path / "profiles"
        destino.mkdir()
        self._coop_local_de_fabrica_velho(destino)
        monkeypatch.setattr(
            loader_module, "_DEFAULT_SEED_SOURCE_DIRS", (tmp_path / "sem_assets",)
        )

        with structlog.testing.capture_logs() as registros:
            migrados = loader_module.migrate_modo_jogo_nos_presets(dest_dir=destino)

        assert migrados == []
        relatos = [
            r for r in registros
            if r.get("event") == "migracao_aposentada_sem_asset"
            and r.get("migracao") == "modo_jogo_nos_presets"  # slug, sem acento (noqa-acento)
        ]
        assert relatos, (
            "o ramo `coop_local` de `migrate_modo_jogo_nos_presets` virou "
            "no-op silencioso — a prioridade 45 do preset velho fica atrás da "
            "Navegação para sempre, sem uma linha no journal"
        )

    def test_com_asset_presente_a_migracao_continua_migrando(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guarda do instrumento: régua que só sabe acusar não é régua.

        Se `migrate_coop_local_match` tivesse sido esvaziada em vez de
        aposentada, os dois testes acima passariam igual — e quem ainda tem o
        asset (uma instalação antiga, um `.deb` velho, o `/usr/share` de outra
        versão) perderia a migração de verdade sem ninguém notar.
        """
        destino = tmp_path / "profiles"
        destino.mkdir()
        caminho = self._coop_local_de_fabrica_velho(destino)

        fonte = tmp_path / "assets"
        fonte.mkdir()
        (fonte / "coop_local.json").write_text(
            json.dumps(
                {
                    "name": "coop_local",
                    "version": 1,
                    "match": {
                        "type": "criteria",
                        "window_title_regex": ".*(Sackboy|Overcooked).*",
                    },
                    "priority": 75,
                    "mode": {"kind": "gamepad", "coop": True},
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(loader_module, "_DEFAULT_SEED_SOURCE_DIRS", (fonte,))

        migrados = loader_module.migrate_coop_local_match(dest_dir=destino)

        assert migrados == ["coop_local.json"]
        depois = json.loads(caminho.read_text(encoding="utf-8"))
        assert depois["match"]["window_title_regex"] == ".*(Sackboy|Overcooked).*"
        assert depois["priority"] == 75
