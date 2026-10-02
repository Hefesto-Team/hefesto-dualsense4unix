"""EMPATE-01 — o desempate entre perfis deixa de ser a ordem do alfabeto."""
from __future__ import annotations

import types
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    Profile,
)
from hefesto_dualsense4unix.testing import FakeController

WM_DESKTOP = "firefox"
_REGRA_DO_DESKTOP = MatchCriteria(window_class=[WM_DESKTOP])


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _manager(ativo: str | None) -> ProfileManager:
    controller = FakeController()
    controller.connect()
    store = StateStore()
    if ativo is not None:
        store.set_active_profile(ativo)
    return ProfileManager(controller=controller, store=store)


def _semear_o_disco_dela() -> None:
    """Os dois `Pragmata` como estão no disco: gêmeos, empatados em 5."""
    save_profile(Profile(name="Pragmata", match=_REGRA_DO_DESKTOP, priority=5))
    save_profile(Profile(name="Pragmata2", match=_REGRA_DO_DESKTOP, priority=5))


class TestOCasoRealDosDoisPragmata:
    def test_o_ativo_continua_valendo(self, isolated_profiles_dir: Path) -> None:
        """O caso medido, inteiro: ativo = Pragmata2, vencedor = Pragmata2."""
        _semear_o_disco_dela()
        escolhido = _manager("Pragmata2").select_for_window({"wm_class": WM_DESKTOP})

        assert escolhido is not None
        assert escolhido.name == "Pragmata2", (
            "o perfil que ela deixou ativo foi derrubado por um empate que "
            "ninguém escolheu: pragmata.json vem antes de pragmata2.json no "
            "glob, e era só isso que decidia"
        )

    def test_o_outro_lado_do_empate_tambem_vale(
        self, isolated_profiles_dir: Path
    ) -> None:
        """Com `Pragmata` ativo, é ele quem fica — o critério não tem lado."""
        _semear_o_disco_dela()
        escolhido = _manager("Pragmata").select_for_window({"wm_class": WM_DESKTOP})

        assert escolhido is not None
        assert escolhido.name == "Pragmata"

    def test_renomear_o_arquivo_nao_muda_o_vencedor(
        self, isolated_profiles_dir: Path
    ) -> None:
        """A mordida do E4 da sprint: o teste não pode estar travando o alfabeto."""
        save_profile(Profile(name="Pragmata", match=_REGRA_DO_DESKTOP, priority=5))
        save_profile(Profile(name="Aaa Pragmata2", match=_REGRA_DO_DESKTOP, priority=5))

        escolhido = _manager("Aaa Pragmata2").select_for_window(
            {"wm_class": WM_DESKTOP}
        )

        assert escolhido is not None
        assert escolhido.name == "Aaa Pragmata2"

    def test_sem_incumbente_o_comportamento_historico_fica(
        self, isolated_profiles_dir: Path
    ) -> None:
        """Nenhum perfil ativo: nada muda — segue o primeiro da ordem de carga."""
        _semear_o_disco_dela()
        escolhido = _manager(None).select_for_window({"wm_class": WM_DESKTOP})

        assert escolhido is not None
        assert escolhido.name == "Pragmata"

    def test_incumbente_fora_do_empate_nao_muda_nada(
        self, isolated_profiles_dir: Path
    ) -> None:
        """Ativo que não é candidato não desempata coisa nenhuma."""
        _semear_o_disco_dela()
        save_profile(
            Profile(
                name="Jogo",
                match=MatchCriteria(window_class=["outra_coisa"]),
                priority=90,
            )
        )
        escolhido = _manager("Jogo").select_for_window({"wm_class": WM_DESKTOP})

        assert escolhido is not None
        assert escolhido.name == "Pragmata"

    def test_o_incumbente_nao_fura_prioridade(
        self, isolated_profiles_dir: Path
    ) -> None:
        """O terceiro termo é TERCEIRO: só age quando os dois primeiros empatam."""
        save_profile(Profile(name="Baixo", match=_REGRA_DO_DESKTOP, priority=5))
        save_profile(Profile(name="Alto", match=_REGRA_DO_DESKTOP, priority=80))

        escolhido = _manager("Baixo").select_for_window({"wm_class": WM_DESKTOP})

        assert escolhido is not None
        assert escolhido.name == "Alto"

    def test_o_incumbente_nao_fura_especificidade(
        self, isolated_profiles_dir: Path
    ) -> None:
        """Nem contra a regra específica (R-01), que vem antes de tudo."""
        save_profile(Profile(name="Pragmata2", match=MatchAny(), priority=100))
        save_profile(
            Profile(
                name="Regra do jogo",
                match=MatchCriteria(window_class=[WM_DESKTOP]),
                priority=0,
            )
        )

        escolhido = _manager("Pragmata2").select_for_window({"wm_class": WM_DESKTOP})

        assert escolhido is not None
        assert escolhido.name == "Regra do jogo"

    def test_desempata_por_slug_e_nao_por_string_crua(
        self, isolated_profiles_dir: Path
    ) -> None:
        """R-10: a identidade do perfil em disco é o SLUG."""
        save_profile(Profile(name="Aaa", match=_REGRA_DO_DESKTOP, priority=5))
        save_profile(Profile(name="Navegação", match=_REGRA_DO_DESKTOP, priority=5))

        escolhido = _manager("Navegacao").select_for_window({"wm_class": WM_DESKTOP})

        assert escolhido is not None
        assert escolhido.name == "Navegação"


class TestOSegundoSeletorTambemSabeQuemEstaAtivo:
    """O sinal de jogo tem um seletor PRÓPRIO (`Daemon._manager_de_selecao`)."""

    def test_o_seletor_de_leitura_recebe_o_store_do_daemon(self) -> None:
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon

        store = StateStore()
        store.set_active_profile("Pragmata2")
        falso_daemon = types.SimpleNamespace(
            _profile_selector=None,
            controller=FakeController(),
            store=store,
        )

        manager = Daemon._manager_de_selecao(falso_daemon)

        assert manager.store is store
        assert manager._nome_do_incumbente() == "Pragmata2"


class TestOEmpateDeixaDeSerMudo:
    """E1 da sprint: hoje o empate não deixa rastro nenhum no journal."""

    def test_loga_uma_vez_e_diz_quem_ganhou(
        self, isolated_profiles_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.profiles import manager as manager_mod

        registros: list[tuple[str, dict[str, object]]] = []

        def fake_info(evento: str, **kw: object) -> None:
            registros.append((evento, kw))

        monkeypatch.setattr(manager_mod.logger, "info", fake_info)
        _semear_o_disco_dela()
        gerente = _manager("Pragmata2")

        for _ in range(5):
            gerente.select_for_window({"wm_class": WM_DESKTOP})

        empates = [kw for evento, kw in registros if evento == "profile_select_empate_resolvido"]
        assert len(empates) == 1, (
            "a seleção roda a 2 Hz e o empate dela é permanente — sem dedup "
            "isto viraria milhares de linhas por hora no journal"
        )
        assert empates[0]["vencedor"] == "Pragmata2"
        assert empates[0]["empatados"] == ["Pragmata", "Pragmata2"]
