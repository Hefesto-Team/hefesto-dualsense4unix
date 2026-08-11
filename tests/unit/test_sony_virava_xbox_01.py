"""SONY-VIRAVA-XBOX-01 — a palavra dela entregava a máscara OPOSTA, calada.

Defeito medido em runtime (10/08/2026): ``normalize_flavor`` mapeava "sony",
"ps5", "nintendo", "switch" e "pro" para ``DEFAULT_FLAVOR`` == ``"xbox"``. Pedir
a máscara de PlayStation pelo nome que ela usa produzia a máscara de Xbox — sem
erro, sem log, e com o daemon respondendo ``status: "ok"`` e ``flavor: "xbox"``
como se o pedido tivesse sido atendido.

A cura tem duas metades, e este arquivo morde as duas:

1. **O sinônimo** — "sony"/"ps5" entram no ramo dualsense
   (``uinput_gamepad.FLAVOR_SINONIMOS``), e a máscara resultante é mesmo a da
   Sony (VID 054c + PID do Edge), não só a string certa.
2. **O portão** — ``gamepad.emulation.set`` RECUSA nome desconhecido em vez de
   cair no xbox calado. Nome que ninguém reconhece é erro, não default.

O que este arquivo NÃO pede: que "nintendo"/"switch"/"pro" virem dualsense. Não
existe máscara de Switch no catálogo; mapeá-las repetiria o defeito (entregar
calada uma máscara que ninguém pediu). Elas são nome desconhecido — e nome
desconhecido agora reprova.

E a terceira classe guarda o que JÁ funcionava: o ``normalize_flavor`` continua
TOLERANTE porque três chamadores internos dependem disso (ver docstrings lá).
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.integrations import uinput_gamepad as ug
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense


class _FakeConfig:
    gamepad_flavor = "xbox"


class _FakeDaemon:
    """Daemon dublado que ANOTA o que lhe pediram (o portão não pode chamá-lo)."""

    def __init__(self) -> None:
        self.calls: list[tuple[bool, str | None]] = []
        self.config = _FakeConfig()

    def set_gamepad_emulation(
        self, enabled: bool, flavor: str | None = None, **_kw: object
    ) -> bool:
        self.calls.append((enabled, flavor))
        if flavor:
            self.config.gamepad_flavor = ug.normalize_flavor(flavor)
        return True


class _Handlers(IpcHandlersMixin):
    def __init__(self, daemon: object) -> None:
        self.daemon = daemon


class TestAPalavraDelaChegaComoMascaraDeSony:
    """Metade 1: "sony" pede PlayStation e recebe PlayStation."""

    @pytest.mark.parametrize(
        "pedido", ["sony", "SONY", " Sony ", "ps5", "PS5", " ps5 "]
    )
    def test_sinonimo_resolve_para_dualsense(self, pedido: str) -> None:
        assert ug.normalize_flavor(pedido) == "dualsense"
        assert ug.resolver_flavor(pedido) == "dualsense"

    def test_a_mascara_de_verdade_e_a_da_sony_e_nao_so_a_string(self) -> None:
        """O que importa é o VID/PID que o jogo vê — antes vinha 045e:028e."""
        gp = ug.UinputGamepad.for_flavor("sony")

        assert gp.flavor == "dualsense"
        assert (gp.vendor, gp.product) == (0x054C, 0x0DF2)
        assert (gp.vendor, gp.product) != (ug.XBOX360_VENDOR, ug.XBOX360_PRODUCT)

    def test_sony_chega_no_backend_uhid_e_nao_no_fallback_xbox(self) -> None:
        """`uhid` só aceita máscara dualsense: com "sony" caindo em xbox, o
        pedido dela ia parar no uinput Xbox — o backend errado, calado."""
        assert UhidDualSense.for_flavor("sony") is not None
        assert UhidDualSense.for_flavor("ps5") is not None


class TestOPortaoRecusaNomeDesconhecido:
    """Metade 2 — a que importa: desconhecido REPROVA, não vira xbox."""

    @pytest.mark.parametrize(
        "pedido", ["nintendo", "switch", "pro", "xboks", "dualshock", "", "   "]
    )
    @pytest.mark.asyncio
    async def test_desconhecido_reprova_e_nao_toca_no_daemon(
        self, pedido: str
    ) -> None:
        d = _FakeDaemon()

        with pytest.raises(ValueError, match="desconhecida"):
            await _Handlers(d)._handle_gamepad_emulation_set(
                {"enabled": True, "flavor": pedido}
            )

        # O pior desfecho do defeito não era o erro ausente: era o vpad SUBIR
        # com a máscara errada e a resposta dizer "ok".
        assert d.calls == []
        assert d.config.gamepad_flavor == "xbox"

    @pytest.mark.asyncio
    async def test_a_recusa_diz_o_que_vale(self) -> None:
        """Recusar sem listar a alternativa é trocar um default calado por um
        erro calado."""
        with pytest.raises(ValueError) as exc:
            await _Handlers(_FakeDaemon())._handle_gamepad_emulation_set(
                {"enabled": True, "flavor": "nintendo"}
            )

        msg = str(exc.value)
        assert "nintendo" in msg
        for nome in ("dualsense", "xbox", "sony"):
            assert nome in msg

    @pytest.mark.parametrize(
        "pedido,canonico",
        [
            ("sony", "dualsense"),
            ("ps5", "dualsense"),
            ("dualsense", "dualsense"),
            (" PlayStation ", "dualsense"),
            ("xbox", "xbox"),
            ("  XBOX  ", "xbox"),
            ("xinput", "xbox"),
        ],
    )
    @pytest.mark.asyncio
    async def test_o_portao_nao_e_um_muro(self, pedido: str, canonico: str) -> None:
        """Todo nome do vocabulário atravessa — inclusive os que a CLI documenta."""
        d = _FakeDaemon()

        res = await _Handlers(d)._handle_gamepad_emulation_set(
            {"enabled": True, "flavor": pedido}
        )

        assert res["status"] == "ok"
        assert d.calls == [(True, pedido)]
        assert res["flavor"] == canonico

    @pytest.mark.asyncio
    async def test_sem_flavor_continua_mantendo_a_mascara_atual(self) -> None:
        """HARM-08: `gamepad on` sem `--flavor` não manda o campo, e não pode
        virar erro nenhum."""
        d = _FakeDaemon()

        res = await _Handlers(d)._handle_gamepad_emulation_set({"enabled": True})

        assert res["status"] == "ok"
        assert d.calls == [(True, None)]


class TestOQueJaFuncionavaContinua:
    """O portão endureceu; o normalizador NÃO — e é de propósito."""

    def test_normalize_flavor_segue_tolerante_para_os_caminhos_internos(self) -> None:
        """`uhid_gamepad.for_flavor` lê "não é dualsense, logo não é meu" do
        default xbox, e coop/gamepad/virtual_pad precisam de máscara SEMPRE (até
        com config de disco corrompida). Fazer o normalizador estourar quebraria
        esses três; por isso a recusa mora no portão de entrada de gente."""
        assert ug.normalize_flavor("nintendo") == ug.DEFAULT_FLAVOR == "xbox"
        assert ug.normalize_flavor(None) == "xbox"
        assert UhidDualSense.for_flavor("nintendo") is None

    def test_os_sinonimos_antigos_seguem_valendo(self) -> None:
        for pedido in ("ps", "playstation", "ds", "DualSense"):
            assert ug.normalize_flavor(pedido) == "dualsense"
        for pedido in ("xbox360", "x360", "xinput", "XBOX"):
            assert ug.normalize_flavor(pedido) == "xbox"

    def test_o_catalogo_e_fonte_unica_do_que_o_portao_aceita(self) -> None:
        """Um terceiro sabor em FLAVORS vale no portão sem editar tabela nenhuma
        — a mesma regra do `external_mask.mascaras_validas`."""
        assert set(ug.FLAVORS) <= set(ug.nomes_de_flavor_aceitos())
        assert set(ug.FLAVOR_SINONIMOS) <= set(ug.nomes_de_flavor_aceitos())
        assert set(ug.FLAVOR_SINONIMOS.values()) <= set(ug.FLAVORS)
