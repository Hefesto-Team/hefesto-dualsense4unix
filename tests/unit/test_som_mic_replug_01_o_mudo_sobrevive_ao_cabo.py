"""SOM-MIC-REPLUG-01 — o silêncio que o usuário pediu não pode morrer com o cabo."""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import manager as mgr
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.utils import maquina


class _Store:
    def __init__(self, ativo: str | None = "o-perfil-dela") -> None:
        self.active_profile = ativo


class _Applier:
    """Guarda cada chamada do `mic_applier` — é o fio que chega ao aparelho."""

    def __init__(self) -> None:
        self.chamadas: list[dict[str, Any]] = []

    def __call__(
        self,
        volume: int | None,
        muted: bool | None,
        *,
        uniq: str | None = None,
        origin: str = "manual",
    ) -> str:
        self.chamadas.append(
            {"volume": volume, "muted": muted, "uniq": uniq, "origin": origin}
        )
        return "aplicado"


def _perfil(mic: dict | None = None, por_peca: dict | None = None):
    """Um perfil de mentira com só o que estes casos leem."""
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    dados: dict[str, Any] = {"name": "o-perfil-dela", "match": MatchManual()}
    if mic is not None:
        dados["mic"] = {"button_toggles_system": False, **mic}
    if por_peca is not None:
        dados["controllers"] = por_peca
    return Profile(**dados)


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch):
    """O manager com o applier espião e o perfil que o `load_profile` devolve."""
    applier = _Applier()

    class Mesa:
        def __init__(self) -> None:
            self.applier = applier

        def com(self, profile) -> ProfileManager:
            monkeypatch.setattr(mgr, "load_profile", lambda nome: profile)
            return ProfileManager(
                controller=object(), store=_Store(), mic_applier=applier
            )

    return Mesa()


def _dono(uniq: str, mudo: bool) -> None:
    """O mudo que ela deu ao controle, no dono (o `maquina.json` do lar da suíte)."""
    assert maquina.gravar_o_mudo_do_microfone(uniq, mudo)


class TestOMudoVoltaNoReplug:
    def test_o_mudo_dela_atravessa_o_replug(self, mesa) -> None:
        """**O CASO QUE ORIGINOU ESTA RÉGUA.**"""
        _dono("aabbcc000003", True)
        m = mesa.com(_perfil())
        estado = m.reapply_mic_on_connect(uniq="aabbcc000003")
        assert estado == "aplicado"
        assert mesa.applier.chamadas, "nada chegou ao aparelho"
        assert mesa.applier.chamadas[-1]["muted"] is True, (
            "o mudo dela não atravessou o replug — ela volta a ser ouvida sem saber"
        )

    def test_o_mudo_desligado_nao_e_escrito_no_replug(self, mesa) -> None:
        """A outra metade da assimetria, e ela protege o LED."""
        _dono("aabbcc000003", False)
        m = mesa.com(_perfil(mic={"volume": 70}))
        m.reapply_mic_on_connect(uniq="aabbcc000003")
        assert mesa.applier.chamadas, "o volume do perfil não chegou ao aparelho"
        assert [c["muted"] for c in mesa.applier.chamadas] == [None], (
            "o replug apagou o LED vermelho do microfone"
        )

    def test_o_volume_atravessa_dos_dois_jeitos(self, mesa) -> None:
        """O ganho de captura nunca esteve em disputa — ele não toca no LED."""
        m = mesa.com(_perfil(mic={"volume": 70}))
        m.reapply_mic_on_connect(uniq="aabbcc000003")
        assert mesa.applier.chamadas[-1]["volume"] == 70


class TestOPerfilEmprestaOVolumeEODonoDizOMudo:
    def test_o_global_escreve_e_o_mudo_do_dono_vem_por_ultimo(self, mesa) -> None:
        """A MESMA ordem do `apply`, e a mesma da SOM-ROTA-03."""
        _dono("aabbcc000003", True)
        m = mesa.com(_perfil(mic={"volume": 50}))
        m.reapply_mic_on_connect(uniq="aabbcc000003")
        assert len(mesa.applier.chamadas) == 2, "global e peça, nesta ordem"
        assert mesa.applier.chamadas[0]["volume"] == 50, "o global não escreveu"
        assert mesa.applier.chamadas[0]["muted"] is None, "o global levou o mudo"
        assert mesa.applier.chamadas[-1]["muted"] is True, (
            "o mudo do dono não chegou à peça"
        )

    def test_o_mudo_de_um_perfil_nao_fala_no_replug(self, mesa) -> None:
        """O `muted` que um perfil ainda carregue não é o mudo do controle."""
        m = mesa.com(
            _perfil(
                mic={"muted": True, "volume": 50},
                por_peca={"aabbcc000003": {"mic": {"muted": True}}},
            )
        )
        m.reapply_mic_on_connect(uniq="aabbcc000003")
        assert [c["muted"] for c in mesa.applier.chamadas if c["muted"]] == [], (
            "o replug calou o controle pelo mudo de um perfil"
        )

    def test_a_chave_e_procurada_ja_canonizada(self, mesa) -> None:
        """A tela manda `aa:bb:…`; o dono guarda 12 hex. MORDIDA: ler cru."""
        _dono("aabbcc000003", True)
        m = mesa.com(_perfil())
        m.reapply_mic_on_connect(uniq="aa:bb:cc:00:00:03")
        assert mesa.applier.chamadas, "a chave com dois-pontos não achou o controle"
        assert mesa.applier.chamadas[-1]["muted"] is True

    def test_sem_opiniao_nenhuma_nao_escreve_nada(self, mesa) -> None:
        """Nem o perfil nem o dono pediram: nada se impõe."""
        m = mesa.com(_perfil())
        assert m.reapply_mic_on_connect(uniq="aabbcc000003") is None
        assert mesa.applier.chamadas == []


class TestATrocaDePerfilNaoLevaOMudo:
    @pytest.mark.parametrize("origem", ["autoswitch", "system", "manual"])
    def test_nenhuma_ativacao_leva_o_mudo(self, mesa, origem: str) -> None:
        """Nem o autoswitch, nem o restore de boot, nem a troca explícita."""
        m = mesa.com(_perfil(mic={"muted": True}))
        m.apply_mic(_perfil(mic={"muted": True}), origin=origem)
        assert mesa.applier.chamadas == [], (
            f"a ativação {origem} mexeu no mudo do microfone"
        )


class TestACuraEstaLIGADA:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""

    def test_o_daemon_chama_o_gancho_nos_dois_caminhos_de_replug(self) -> None:
        """Os DOIS pontos: o laço por alvo e a borda de alvo novo."""
        from pathlib import Path

        fonte = Path(
            "src/hefesto_dualsense4unix/daemon/connection.py"
        ).read_text(encoding="utf-8")
        assert fonte.count("await reapply_mic_after_connect") == 2, (
            "o gancho do microfone não cobre os dois caminhos de replug"
        )
        assert fonte.count("await reapply_speaker_after_connect") == 2

    def test_cada_um_tem_o_proprio_suppress(self) -> None:
        """O alto-falante falhar não pode custar o mudo do microfone do usuário."""
        from pathlib import Path

        fonte = Path(
            "src/hefesto_dualsense4unix/daemon/connection.py"
        ).read_text(encoding="utf-8")
        pedacos = fonte.split("await reapply_mic_after_connect")
        for antes in pedacos[:-1]:
            cauda = antes[-120:]
            assert "contextlib.suppress" in cauda, (
                "uma chamada do microfone não tem `suppress` próprio"
            )

    def test_o_gancho_esta_no_all(self) -> None:
        from hefesto_dualsense4unix.daemon import connection

        assert "reapply_mic_after_connect" in connection.__all__
