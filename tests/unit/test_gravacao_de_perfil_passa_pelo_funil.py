"""GRAVA-POR-UM-FUNIL-01 — o rodapé grava e o rascunho não fica sabendo (04/08)."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("funil de gravação de perfil")

import ast
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.loader import load_all_profiles
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
)

_SRC = Path(__file__).resolve().parents[2] / "src"
_APP = _SRC / "hefesto_dualsense4unix" / "app"

_PRIORIDADE_DO_PRIMEIRO_SAVE = 10
_PRIORIDADE_DA_CATRACA = 20


@pytest.fixture(autouse=True)
def _sync_run_in_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Roda ``ipc_bridge.run_in_thread`` de forma síncrona (sem loop GTK)."""

    def _sync(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        try:
            resultado = fn()
        except Exception as exc:
            if on_failure is not None:
                on_failure(exc)
            return
        on_success(resultado)

    monkeypatch.setattr(footer_actions.ipc_bridge, "run_in_thread", _sync)


@pytest.fixture
def disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o disco de verdade, num tmp."""
    import hefesto_dualsense4unix.profiles.loader as loader_mod

    destino = tmp_path / "profiles"
    destino.mkdir()
    monkeypatch.setattr(loader_mod, "profiles_dir", lambda ensure=False: destino)
    return destino


def _janela_fake(draft: DraftConfig, ativo: str = "") -> Any:
    """Dublê com os DOIS mixins que o ``HefestoApp`` compõe de verdade."""
    from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
    from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin

    class _Janela(ProfilesActionsMixin, FooterActionsMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self.draft = draft
            self._active_profile_name = ativo
            self._draft_baseline: Any = draft
            self._profiles_cache: list[Profile] = list(load_all_profiles())
            self._toasted: list[str] = []
            self._avisos_ao_daemon = 0
            builder = MagicMock()
            builder.get_object.return_value = MagicMock()
            self.builder = builder

        def _reload_profiles_store(
            self, select_name: str | None = None, on_done: Any | None = None
        ) -> None:
            self._profiles_cache = list(load_all_profiles())
            if on_done is not None:
                on_done()

        def _footer_toast(self, msg: str, context: str = "footer") -> None:
            self._toasted.append(msg)

        def _toast_profile(self, msg: str) -> None:
            self._toasted.append(msg)

        def _notify_launch_env_refresh(self) -> None:
            self._avisos_ao_daemon += 1

    return _Janela()


def _perfil_do_jogo(nome: str = "Pragmata") -> Profile:
    """Perfil com REGRA de janela e prioridade alta — o que ela tem em disco."""
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=["steam_app_3357650"]),
        priority=60,
        leds=LedsConfig(lightbar=(97, 53, 131)),
    )


def _salvar_pelo_rodape(janela: Any, nome: str) -> None:
    """O gesto dela: botão "Salvar Perfil", digita ``nome``, confirma."""
    dialogos = MagicMock()
    dialogos.prompt_profile_name.return_value = nome
    dialogos.prompt_overwrite_existing.return_value = True
    with patch(
        "hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", dialogos
    ):
        janela.on_save_profile()


def _perfil_em_disco(disco: Path, slug: str) -> dict[str, Any]:
    return json.loads((disco / f"{slug}.json").read_text(encoding="utf-8"))


class TestDoisSavesSeguidos:
    """O segundo "Salvar Perfil" não pode reescrever o perfil do primeiro."""

    def test_a_prioridade_e_a_regra_do_primeiro_save_sobrevivem(
        self, disco: Path
    ) -> None:
        """Dois "Salvar Perfil" seguidos com o mesmo nome, o gesto medido."""
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "MadJack")
        primeiro = _perfil_em_disco(disco, "madjack")

        _salvar_pelo_rodape(janela, "MadJack")
        segundo = _perfil_em_disco(disco, "madjack")

        assert primeiro["priority"] == _PRIORIDADE_DO_PRIMEIRO_SAVE, (
            "o perfil novo tem de nascer acima dos catch-all dela "
            "(PERFIL-NASCE-CERTO-01)"
        )
        assert segundo["priority"] == _PRIORIDADE_DO_PRIMEIRO_SAVE, (
            f"o segundo save subiu a prioridade para {segundo['priority']} — a "
            f"catraca medida ({_PRIORIDADE_DA_CATRACA}) está de volta e o "
            "perfil dela caminha para atropelar as regras de jogo"
        )
        assert segundo["priority"] != _PRIORIDADE_DA_CATRACA
        assert segundo["match"] == primeiro["match"]

    def test_a_configuracao_dela_continua_indo_junto(self, disco: Path) -> None:
        """A guarda não pode virar "o segundo save não grava nada"."""
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "MadJack")
        novos_leds = janela.draft.leds.model_copy(update={"lightbar_rgb": (10, 20, 30)})
        janela.draft = janela.draft.model_copy(update={"leds": novos_leds})
        _salvar_pelo_rodape(janela, "MadJack")

        assert _perfil_em_disco(disco, "madjack")["leds"]["lightbar"] == [10, 20, 30]


class TestRascunhoApontaParaODisco:
    def test_salvar_com_nome_novo_reaponta_o_rascunho(self, disco: Path) -> None:
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "MadJack")

        assert janela.draft.source_name == "MadJack", (
            "o rascunho continuou apontando para o perfil anterior — o gate "
            "`mesmo_perfil` do `to_profile` responderá False para sempre"
        )
        assert janela._active_profile_name == "MadJack"
        assert janela._draft_baseline is janela.draft

    def test_os_source_batem_com_o_perfil_gravado(self, disco: Path) -> None:
        """A invariante inteira, campo a campo, e não só o nome."""
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "MadJack")
        gravado = Profile.model_validate(_perfil_em_disco(disco, "madjack"))

        assert janela.draft.source_name == gravado.name
        assert janela.draft.source_priority == gravado.priority
        assert janela.draft.source_match == gravado.match
        assert janela.draft.source_mode == gravado.mode
        assert janela.draft.source_suppress == gravado.suppress_desktop_emulation

    def test_salvar_por_cima_de_perfil_que_ja_existe_herda_a_prioridade(
        self, disco: Path
    ) -> None:
        """Prioridade é CALCULADA só para quem não existe em disco."""
        from hefesto_dualsense4unix.profiles.loader import save_profile

        save_profile(
            Profile(
                name="Navegação",
                match=MatchCriteria(window_class=["firefox"]),
                priority=50,
            )
        )
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "Navegação")

        assert _perfil_em_disco(disco, "navegacao")["priority"] == 50

    def test_salvar_por_cima_de_perfil_que_ja_existe_herda_a_regra(
        self, disco: Path
    ) -> None:
        """REGRA-NAO-SE-PERDE-01 — o caso REAL dela, de 05/08/2026."""
        from hefesto_dualsense4unix.profiles.loader import save_profile

        save_profile(
            Profile(
                name="sackboy_nativo",
                match=MatchCriteria(window_class=["steam_app_1599660"]),
                priority=80,
            )
        )
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "sackboy_nativo")

        gravado = _perfil_em_disco(disco, "sackboy_nativo")
        assert gravado["match"]["type"] == "criteria", (
            "o rodapé apagou a regra de um perfil que JÁ EXISTIA — é o defeito "
            "que tirou o perfil do jogo dela de dentro do próprio jogo"
        )
        assert gravado["match"]["window_class"] == ["steam_app_1599660"]

    def test_perfil_novo_pelo_rodape_herda_a_regra_da_origem(
        self, disco: Path
    ) -> None:
        """Nome NOVO herda a regra do perfil de ORIGEM — e nunca nasce catch-all."""
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "um_nome_que_nao_existe")

        gravado = _perfil_em_disco(disco, "um_nome_que_nao_existe")
        assert gravado["match"]["type"] == "criteria", (
            "o perfil novo nasceu catch-all — é o que o tira de dentro do jogo "
            "dela e o põe por cima do desktop inteiro"
        )
        assert gravado["match"]["window_class"] == ["steam_app_3357650"]
        assert Profile.model_validate(gravado).e_catch_all is False


class TestImportarERestaurar:
    def test_importar_por_cima_do_perfil_ativo_atualiza_a_fotografia(
        self, disco: Path
    ) -> None:
        """O import muda o disco debaixo do rascunho — e ele tem de saber."""
        from hefesto_dualsense4unix.profiles.loader import save_profile

        ativo = Profile(name="Pragmata", match=MatchAny(), priority=5)
        save_profile(ativo)
        janela = _janela_fake(DraftConfig.from_profile(ativo), "Pragmata")

        janela._import_save_async(_perfil_do_jogo())

        assert janela.draft.source_match == _perfil_do_jogo().match, (
            "o rascunho ficou com a fotografia anterior ao import"
        )

        _salvar_pelo_rodape(janela, "Pragmata")
        salvo = _perfil_em_disco(disco, "pragmata")
        assert salvo["match"]["window_class"] == ["steam_app_3357650"], (
            "o save seguinte apagou a regra que ela acabou de importar"
        )
        assert salvo["priority"] == 60

    def test_importar_outro_perfil_nao_rouba_o_rascunho(self, disco: Path) -> None:
        """Importar um arquivo NÃO é dizer "passei a editar este perfil"."""
        ativo = _perfil_do_jogo("Pragmata")
        janela = _janela_fake(DraftConfig.from_profile(ativo), "Pragmata")

        janela._import_save_async(Profile(name="Corrida", match=MatchAny(), priority=7))

        assert janela.draft.source_name == "Pragmata"
        assert janela._active_profile_name == "Pragmata"

    def test_restaurar_padrao_deixa_o_rascunho_no_perfil_padrao(
        self, disco: Path
    ) -> None:
        """R-08/C9: rascunho e NOME trocam como unidade, também no restauro."""
        asset = footer_actions._meu_perfil_asset()
        if asset is None:
            pytest.skip("preset do perfil padrão ausente em todos os candidatos")
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        dialogos = MagicMock()
        dialogos.confirm_restore_default.return_value = True
        with patch(
            "hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", dialogos
        ):
            janela.on_restore_default()

        from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO

        assert janela._active_profile_name == NOME_DO_PADRAO
        assert janela.draft.source_name == NOME_DO_PADRAO


#: ``_reconciliar_rascunho_com_perfil_salvo``. Convertê-la é trabalho de outra
_AUTORIZADOS_A_GRAVAR = {
    "actions/profile_writer.py",
    "actions/profiles_actions.py",
}


def _chamadas_a_save_profile(caminho: Path) -> list[int]:
    """Linhas em que ``caminho`` CHAMA ``save_profile`` (AST, não texto)."""
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    linhas: list[int] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        if isinstance(alvo, ast.Name):
            nome = alvo.id
        elif isinstance(alvo, ast.Attribute):
            nome = alvo.attr
        else:
            continue
        if nome == "save_profile":
            linhas.append(no.lineno)
    return linhas


def test_nenhuma_gravacao_de_perfil_fora_do_funil() -> None:
    """O pedido central da mantenedora, em forma de portão."""
    ofensores: dict[str, list[int]] = {}
    for caminho in sorted(_APP.rglob("*.py")):
        relativo = caminho.relative_to(_APP).as_posix()
        if relativo in _AUTORIZADOS_A_GRAVAR:
            continue
        linhas = _chamadas_a_save_profile(caminho)
        if linhas:
            ofensores[relativo] = linhas

    assert ofensores == {}, (
        "gravação de perfil fora do funil (GRAVA-POR-UM-FUNIL-01): "
        f"{ofensores} — use `self._gravar_perfil_async(...)` de "
        "`app/actions/profile_writer.py`, que grava E reaponta o rascunho"
    )


def test_a_lista_de_autorizados_nao_cresce_em_silencio() -> None:
    """A exceção da aba Perfis é datada; a lista só pode encolher."""
    assert sorted(_AUTORIZADOS_A_GRAVAR) == [
        "actions/profile_writer.py",
        "actions/profiles_actions.py",
    ]


def test_quem_esta_autorizado_cumpre_a_invariante_por_conta_propria() -> None:
    """Autorizado a gravar não é autorizado a esquecer o rascunho."""
    for relativo in sorted(_AUTORIZADOS_A_GRAVAR):
        texto = (_APP / relativo).read_text(encoding="utf-8")
        assert "with_profile_identity" in texto, (
            f"{relativo} grava perfil e não reaponta o rascunho — a fotografia "
            "dos `source_*` envelhece e o `to_profile` volta a zerar regra e "
            "prioridade a cada save"
        )


def test_o_funil_carimba_a_origem_da_gravacao() -> None:
    """Toda gravação da janela diz de ONDE veio, no journal."""
    texto = (_APP / "actions/profile_writer.py").read_text(encoding="utf-8")
    assert "save_profile(profile, origem=" in texto, (
        "o funil grava sem dizer de onde veio — o `profile_salvo` do journal "
        "perde o único campo que distingue um botão do outro"
    )
    assert "janela:" in texto, (
        "a origem precisa identificar a JANELA, não só o processo: o basename "
        "do argv[0] é igual para todos os botões"
    )
