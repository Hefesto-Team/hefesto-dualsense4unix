"""SINAL-NO-NASCIMENTO-01/E2 — o veredito atravessa o IPC, e o que ele não pode dizer.

O carimbo do nascimento é tirado no tique de hotplug desde 22/08/2026 e vivia só
dentro do daemon: o card tinha o botão da cura ("A luz não acende") e não tinha a
RAZÃO para oferecê-la. Este arquivo guarda a porta que faltava — e as três
mentiras que ela não pode contar:

1. **ausência não é inocência.** ``None`` quer dizer *não carimbei*. Quem ler
   isso como "nasceu limpa" refaz o defeito que a BARRA-MUDA-01 §5 nomeou;
2. **um dublê de teste não vira acusação na tela dela.** O daemon é ``MagicMock``
   em boa parte da suíte, e um ``getattr`` ingênuo devolveria outro mock —
   a acusação apareceria no card sem ninguém ter medido nada;
3. **perguntar não pode custar diário.** Tirar o veredito custa dois
   ``journalctl``; a GUI pergunta o estado a cada segundo. Se a porta relesse o
   diário, o carimbo deixaria de ser memória e viraria consulta por segundo —
   e é justamente essa diferença que a sprint existe para produzir.

FIXTURES: faixa sintética ``02:fe:00`` da casa. Nenhum endereço real entra em
arquivo versionado, e há dois portões que reprovam.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.integrations import sinal_da_barra as sb

#: O endereço na grafia do SYSFS — é assim que o carimbo é guardado.
UNIQ_SYSFS = "02:fe:00:11:22:01"
#: O MESMO endereço na grafia do BACKEND — é a que chega ao payload de IPC, e a
#: única que a tela conhece. As duas grafias são o defeito de 25/08/2026.
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
        sb.ler_a_mesa(instancias=[alvo], nascimentos=nascimentos), agora=100.0
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
        """Ninguém nesta casa consegue LER a lâmpada — três medições dizem isso.

        A régua está no módulo e vale de novo aqui, porque é nesta frase que a
        promessa chegaria à tela dela.
        """
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
        """CONTADOR, e não bomba: `_enrich_controllers_per_controller` roda
        dentro de um `suppress` no chamador, e um `raise` sairia verde — a
        armadilha que a própria sprint registrou."""
        chamadas: list[str] = []
        # O carimbo é tirado ANTES: é o que o tique de hotplug já fez. O que
        # este teste mede é o preço de PERGUNTAR depois.
        handler = _Handler(_daemon_com(_cartorio_com(sujo=True)))

        monkeypatch.setattr(
            sb, "ler_a_mesa", lambda **_k: chamadas.append("diario") or []
        )
        monkeypatch.setattr(
            sb.subprocess,
            "run",
            lambda *_a, **_k: chamadas.append("subprocesso"),
        )

        for _ in range(60):  # um minuto do tique de 1 s da GUI
            assert handler._nascimento_para(UNIQ_IPC) is not None
        assert chamadas == [], (
            f"a pergunta da tela voltou a custar leitura: {chamadas}. O carimbo "
            "deixou de ser memória e virou consulta por segundo"
        )


class TestAPortaEstaLigadaNoPayload:
    """A mordida da FIAÇÃO. Sem esta linha o cartório volta a ser enfeite —
    exatamente o estado em que a BARRA-MUDA-01 declarou o módulo."""

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
