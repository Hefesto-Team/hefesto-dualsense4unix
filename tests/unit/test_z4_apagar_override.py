"""Z4/T7+T8+T9 — o `None` que carregava duas coisas em `controllers`."""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import MagicMock

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
