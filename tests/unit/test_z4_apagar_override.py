"""Z4/T7+T8+T9 — o `None` que carregava duas coisas em `controllers`."""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import MagicMock

from hefesto_dualsense4unix.app.draft_config import DraftConfig, LedsDraft
from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
from hefesto_dualsense4unix.daemon.state_store import StateStore


_UNIQ = "02fe00112233"


def _applier() -> tuple[DraftApplier, MagicMock, StateStore]:
    controller = MagicMock()
    store = StateStore()
    return DraftApplier(controller, store, daemon=None), controller, store


class TestODaemonJaAceitaVazio:
    """T7 — medição, não cura. `{}` já limpa e já arma a trava, hoje."""

    def test_controllers_vazio_substitui_o_mapa_por_vazio_no_backend(self) -> None:
        applier, controller, _store = _applier()
        applier.apply(
            {"controllers": {_UNIQ: {"leds": {"lightbar_rgb": [10, 20, 30]}}}}
        )
        controller.reset_mock()

        applied = applier.apply({"controllers": {}})

        assert applied == ["controllers"], (
            f"a seção `controllers` não entrou em `applied` para o payload "
            f"vazio: {applied!r} — o daemon está pulando `{{}}` como se fosse "
            "`None`"
        )
        controller.reset_output_overrides.assert_called_once()
        (arg,) = controller.reset_output_overrides.call_args.args
        assert not arg, (
            "`reset_output_overrides` foi chamado com "
            f"{arg!r} — para limpar, o mapa novo tem de ser vazio/None"
        )


class TestAMordidaDoQueFazOZeroJaFuncionar:
    """A mordida de T7: arrancar o guarda que faz `{}` chegar até aqui."""

    def test_trocar_is_none_por_not_raw_quebra_o_contrato_de_vazio(self) -> None:
        import hefesto_dualsense4unix.daemon.ipc_draft_applier as mod

        original = mod.DraftApplier._apply_section

        def _guarda_ingenuo(
            self: Any, applied: list[str], raw: Any, section: str, fn: Any
        ) -> None:
            if not raw:
                return
            try:
                fn(raw)
                applied.append(section)
            except Exception:
                pass

        mod.DraftApplier._apply_section = _guarda_ingenuo  # type: ignore[method-assign]
        try:
            applier, controller, _store = _applier()
            applied = applier.apply({"controllers": {}})
            assert applied == [], (
                "com o guarda ingênuo, `{}` DEVERIA ser pulado (essa é a "
                f"regressão) — mas `applied` saiu {applied!r}"
            )
            controller.reset_output_overrides.assert_not_called()
        finally:
            mod.DraftApplier._apply_section = original  # type: ignore[method-assign]


class TestAJanelaEmiteVazioQuandoOUltimoOverrideCai:
    """T8 — `_controllers_to_ipc` e o gêmeo `with_override_fields_cleared`."""

    def test_draft_default_sem_overrides_emite_none(self) -> None:
        d = DraftConfig.default()
        assert d.to_ipc_dict().get("controllers") is None

    def test_apagar_o_unico_override_por_campo_emite_vazio(self) -> None:
        d = DraftConfig.default().with_controller_leds(
            _UNIQ, LedsDraft(lightbar_rgb=(10, 20, 30))
        )
        assert list((d.to_ipc_dict().get("controllers") or {}).keys()) == [_UNIQ]

        d2 = d.with_controller_fields_cleared(
            _UNIQ, "leds", {"lightbar", "lightbar_brightness"}
        )
        assert d2.source_controllers is None, (
            "o mapa some do MODELO (correto — sem chave fantasma no perfil "
            f"salvo), mas ficou {d2.source_controllers!r}"
        )
        assert d2.to_ipc_dict().get("controllers") == {}, (
            f"a chave `controllers` no IPC saiu {d2.to_ipc_dict().get('controllers')!r}"
            " — deveria ser `{}` (apague os overrides), não `None` "
            "(sem opinião) nem ausente"
        )

    def test_apagar_pela_variante_todos_tambem_emite_vazio(self) -> None:
        """O gêmeo `with_override_fields_cleared` — o MESMO defeito, ponto B."""
        d = DraftConfig.default().with_controller_leds(
            _UNIQ, LedsDraft(lightbar_rgb=(10, 20, 30))
        )
        d2 = d.with_override_fields_cleared("leds", {"lightbar", "lightbar_brightness"})
        assert d2.source_controllers is None
        assert d2.to_ipc_dict().get("controllers") == {}, (
            "with_override_fields_cleared (a variante 'Todos') não marcou o "
            "esvaziamento — a chave saiu "
            f"{d2.to_ipc_dict().get('controllers')!r}"
        )

    def test_gravar_um_override_novo_desarma_a_flag(self) -> None:
        """Depois de apagar, gravar de novo volta ao comportamento normal —"""
        d = DraftConfig.default().with_controller_leds(
            _UNIQ, LedsDraft(lightbar_rgb=(10, 20, 30))
        )
        d2 = d.with_controller_fields_cleared(
            _UNIQ, "leds", {"lightbar", "lightbar_brightness"}
        )
        assert d2.controllers_esvaziados_nesta_edicao is True

        d3 = d2.with_controller_leds(_UNIQ, LedsDraft(lightbar_rgb=(1, 2, 3)))
        assert d3.controllers_esvaziados_nesta_edicao is False
        assert list((d3.to_ipc_dict().get("controllers") or {}).keys()) == [_UNIQ]

    def test_ciclo_fim_a_fim_apagar_salvar_fechar_reabrir(self) -> None:
        """A mordida-âncora da sprint (aceite §9, item 3): grave, apague,"""
        d = DraftConfig.default().with_controller_leds(
            _UNIQ, LedsDraft(lightbar_rgb=(10, 20, 30))
        )
        perfil_com_override = d.to_profile("z4-t8", priority=1)
        assert perfil_com_override.controllers, "setup inválido: sem override"

        d2 = d.with_controller_fields_cleared(
            _UNIQ, "leds", {"lightbar", "lightbar_brightness"}
        )
        perfil_salvo = d2.to_profile("z4-t8", priority=1)
        assert perfil_salvo.controllers is None, (
            f"o override sobreviveu no ARQUIVO: {perfil_salvo.controllers!r}"
        )

        applier, controller, _store = _applier()
        applier.apply({"controllers": d2.to_ipc_dict()["controllers"]})
        controller.reset_output_overrides.assert_called_once()
        (arg,) = controller.reset_output_overrides.call_args.args
        assert not arg, f"o daemon recebeu {arg!r} — deveria limpar tudo"


class TestOCensoDasOutrasSecoes:
    """T9 — censo: quantas seções têm um gesto que ESVAZIA um mapa antes"""

    _CENSO: ClassVar[dict[str, tuple[bool, str]]] = {
        "leds": (False, "seção GLOBAL, sem mapa — não há 'vazio' possível"),
        "triggers": (False, "idem — global"),
        "controllers": (True, "with_override_fields_cleared / with_controller_fields_cleared"),
        "rumble": (False, "global; o override por-peça VIVE dentro de `controllers`"),
        "mouse": (False, "seção única do draft, não um mapa por-chave"),
        "keyboard": (False, "idem"),
        "mic": (False, "None=sem opinião por CONTRATO (schema.py) — nunca 'apagar'"),
        "speaker": (False, "idem, com a exceção nomeada de `mic.muted` (não aplica aqui)"),
    }

    def test_apenas_controllers_tem_mapa_que_esvazia(self) -> None:
        com_mapa = [nome for nome, (tem, _motivo) in self._CENSO.items() if tem]
        assert com_mapa == ["controllers"], (
            f"seções com mapa esvaziável: {com_mapa!r} — a sprint mediu só "
            "`controllers` em 24/08/2026; se uma seção nova ganhou mapa "
            "por-chave, ela precisa do MESMO tratamento de "
            "`controllers_esvaziados_nesta_edicao` antes de este censo mentir"
        )

    def test_o_censo_cobre_as_oito_secoes_do_payload(self) -> None:
        """As oito seções que `DraftApplier.apply` conhece (fonte única:"""
        oito = {
            "leds",
            "triggers",
            "controllers",
            "rumble",
            "mouse",
            "keyboard",
            "mic",
            "speaker",
        }
        assert set(self._CENSO) == oito
