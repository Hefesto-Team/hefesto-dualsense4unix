"""SINAL-NO-NASCIMENTO-01/E2 — o veredito atravessa o IPC, e o que ele não pode dizer."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.integrations import sinal_da_barra as sb

UNIQ_SYSFS = "02:fe:00:11:22:01"
UNIQ_IPC = "02fe00112201"

_ADAPTADOR = "02:fe:00:99:88:77"


class _Handler(IpcHandlersMixin):
    """O mixin com o mínimo que `_nascimento_para` toca."""

    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon  # type: ignore[assignment]


def _instancia(instancia: str = "0028", *, hidraw: str = "/dev/hidraw6") -> sb.Instancia:
    return sb.Instancia(
        instancia=instancia,
        uniq=UNIQ_SYSFS,
        adaptador=_ADAPTADOR,
        hw_version="0x00000811",
        input_n=None,
        hidraw=hidraw,
        transporte="bt",
    )


def _cartorio_com(*, sujo: bool) -> sb.CartorioDoNascimento:
    """Um cartório com UMA conexão já carimbada, condenada ou sã."""
    alvo = _instancia()
    cartorio = sb.CartorioDoNascimento()
    cartorio.observar([alvo], agora=100.0)
    nascimentos = {
        alvo.instancia: sb.Nascimento(
            instancia=alvo.instancia,
            quando=64_740.852,
            no=alvo.hidraw or "",
            transporte="bt",
            escritor=(600105,) if sujo else (),
            sujo=sujo,
        )
    }
    cartorio.carimbar(
        sb.veredito_do_nascimento(instancias=[alvo], nascimentos=nascimentos), agora=100.0
    )
    return cartorio


def _daemon_com(cartorio: Any) -> SimpleNamespace:
    return SimpleNamespace(_cartorio_do_nascimento=cartorio)


class TestOVereditoAtravessaOIpc:
    def test_a_conexao_condenada_leva_a_razao_ao_card(self) -> None:
        handler = _Handler(_daemon_com(_cartorio_com(sujo=True)))
        veredito = handler._nascimento_para(UNIQ_IPC)

        assert veredito is not None, (
            "a porta devolveu None para uma conexão carimbada — o card volta a "
            "oferecer a cura sem dizer por quê"
        )
        assert veredito["confianca"] == sb.CONFIANCA_SUSPEITA
        assert veredito["pede_reconexao"] is True
        assert veredito["instancia"] == "0028"
        assert veredito["porque"]

    def test_a_conexao_sa_nao_pede_reconexao(self) -> None:
        veredito = _Handler(_daemon_com(_cartorio_com(sujo=False)))._nascimento_para(
            UNIQ_IPC
        )
        assert veredito is not None
        assert veredito["confianca"] == sb.CONFIANCA_LIMPA
        assert veredito["pede_reconexao"] is False

    def test_a_frase_nunca_diz_acesa_nem_apagada(self) -> None:
        """Ninguém nesta casa consegue LER a lâmpada — três medições dizem isso."""
        for sujo in (True, False):
            veredito = _Handler(_daemon_com(_cartorio_com(sujo=sujo)))._nascimento_para(
                UNIQ_IPC
            )
            assert veredito is not None
            frase = veredito["porque"].lower()
            assert "acesa" not in frase and "apagada" not in frase, frase


class TestAusenciaNaoEInocencia:
    def test_sem_carimbo_a_porta_nao_afirma_nada(self) -> None:
        handler = _Handler(_daemon_com(sb.CartorioDoNascimento()))
        assert handler._nascimento_para(UNIQ_IPC) is None

    def test_o_daemon_recem_subido_nao_afirma_nada(self) -> None:
        """`_cartorio_do_nascimento` nasce `None` no `lifecycle`."""
        assert _Handler(_daemon_com(None))._nascimento_para(UNIQ_IPC) is None
        assert _Handler(None)._nascimento_para(UNIQ_IPC) is None
        assert (
            _Handler(_daemon_com(_cartorio_com(sujo=True)))._nascimento_para(None)
            is None
        )

    def test_o_vizinho_carimbado_nao_respinga_neste_card(self) -> None:
        handler = _Handler(_daemon_com(_cartorio_com(sujo=True)))
        assert handler._nascimento_para("02fe00112299") is None

    def test_um_dible_de_teste_nao_vira_acusacao_na_tela(self) -> None:
        """A mesma regra dura do `_lightbar_disputada`: `isinstance`, não pato."""
        from unittest.mock import MagicMock

        assert _Handler(MagicMock())._nascimento_para(UNIQ_IPC) is None


class TestPerguntarNaoCustaDiario:
    def test_a_porta_nao_le_o_diario_nem_roda_subprocesso(self, monkeypatch) -> None:
        """CONTADOR, e não bomba: `_enrich_controllers_per_controller` roda"""
        chamadas: list[str] = []
        handler = _Handler(_daemon_com(_cartorio_com(sujo=True)))

        monkeypatch.setattr(
            sb, "veredito_do_nascimento", lambda **_k: chamadas.append("diario") or []
        )
        monkeypatch.setattr(
            sb.subprocess,
            "run",
            lambda *_a, **_k: chamadas.append("subprocesso"),
        )

        for _ in range(60):
            assert handler._nascimento_para(UNIQ_IPC) is not None
        assert chamadas == [], (
            f"a pergunta da tela voltou a custar leitura: {chamadas}. O carimbo "
            "deixou de ser memória e virou consulta por segundo"
        )


class TestAPortaEstaLigadaNoPayload:
    """A mordida da FIAÇÃO. Sem esta linha o cartório volta a ser enfeite —"""

    def test_o_enrich_carimba_o_campo_em_cada_entrada(self) -> None:
        import inspect

        fonte = inspect.getsource(
            IpcHandlersMixin._enrich_controllers_per_controller
        )
        assert 'entry["nascimento"] = self._nascimento_para(uniq)' in fonte, (
            "o payload por controle parou de levar o veredito do nascimento. O "
            "daemon continua carimbando e a tela volta a não ter a razão — a "
            "`A-CASA-SABE-E-O-PRODUTO-NÃO-FAZ` de novo, no mesmo módulo"
        )
