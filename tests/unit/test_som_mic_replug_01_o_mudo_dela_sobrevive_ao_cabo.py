"""SOM-MIC-REPLUG-01 — o silêncio que ela pediu não pode morrer com o cabo.

A PRIMEIRA DAS SETE DÍVIDAS que a régua das quatro pernas declarou, e a mais
cara delas porque o preço de errar é de PRIVACIDADE::

    campo         perna   estado em 16/09          o texto da dívida
    mic.muted     VOLTA   DÍVIDA                   "o LED do mudo volta (está
                                                    em `_OUTPUT_FIELDS`), mas o
                                                    MUDO em si não"

**O que acontecia:** ela deixa o microfone mudo, tira e repõe o cabo, e o
microfone volta ABERTO — o firmware nasce assim, e nenhum caminho de adoção ou
reconexão chamava `set_microphone_mute`. A pessoa continua achando que está em
silêncio. Num produto de acessibilidade, em que o microfone do controle é o
canal de fala de quem o usa, este é o defeito mais grave da família: **o
silêncio que o produto promete e não entrega.**

A CONCILIAÇÃO, e é ela que esta régua trava
-------------------------------------------
Havia DUAS decisões medidas em tensão, e as duas continuam de pé:

- o perfil do jogo não rouba o mudo dela no meio de uma gravação — desde
  28/09/2026 (O-MUDO-E-DO-CONTROLE-01) por uma razão mais forte que a
  ``MIC-GRAVACAO-01``: o mudo é do CONTROLE e mora no ``maquina.json``, e
  nenhuma troca de perfil o escreve, nem a explícita;
- ``AUDIT-FINDING-PROFILE-MIC-LED-RESET-01`` — o LED vermelho do mic jamais se
  apaga como colateral.

O replug lê o mudo do DONO (``utils.maquina.mudo_do_microfone``); o perfil
ativo só empresta o volume.

A passagem do replug é ASSIMÉTRICA, e é por isso que cabe entre as duas::

    muted=True   ESCREVE   o firmware voltou aberto; devolver o mudo desfaz uma
                           escolha que ninguém fez. E ACENDE o LED — o lado
                           seguro tem sinal visível, o inseguro não tem nenhum.
    muted=False  não       já é o default do firmware, e escrever APAGARIA o LED.

E a regra mora em UM lugar (`apply_mic`), porque a casa exige que a guarda do
mudo não tenha duas cópias que possam divergir.
"""
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
    """Um perfil de mentira com só o que estes casos leem.

    `match` e `mic.button_toggles_system` são OBRIGATÓRIOS no esquema e entram
    com valor neutro — o `Profile` real é quem valida, e usar o dublê do pydantic
    aqui esconderia um campo que o produto exige.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    dados: dict[str, Any] = {"name": "o-perfil-dela", "match": MatchManual()}
    if mic is not None:
        #: O interruptor é UM por máquina e não é desta cura — vai neutro.
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
        """**O CASO QUE ORIGINOU ESTA RÉGUA.**

        MORDIDA: trocar `origin="replug"` por `origin="system"` em
        `reapply_mic_on_connect` — a guarda do `apply_mic` zera o `muted` e o
        microfone dela volta aberto, calado, como antes da cura.
        """
        _dono("aabbcc000003", True)
        m = mesa.com(_perfil())
        estado = m.reapply_mic_on_connect(uniq="aabbcc000003")
        assert estado == "aplicado"
        assert mesa.applier.chamadas, "nada chegou ao aparelho"
        assert mesa.applier.chamadas[-1]["muted"] is True, (
            "o mudo dela não atravessou o replug — ela volta a ser ouvida sem saber"
        )

    def test_o_mudo_desligado_nao_e_escrito_no_replug(self, mesa) -> None:
        """A outra metade da assimetria, e ela protege o LED.

        `muted=False` já é o default do firmware: escrever não mudaria o som e
        APAGARIA o LED vermelho, que a AUDIT-FINDING-PROFILE-MIC-LED-RESET-01
        proíbe fora de pedido explícito dela.

        MORDIDA: deixar `muted` passar sem filtro no ramo `replug`.
        """
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
        """A MESMA ordem do `apply`, e a mesma da SOM-ROTA-03.

        O global do perfil leva o volume; o mudo vem do dono, na peça.
        """
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
        """O `muted` que um perfil ainda carregue não é o mudo do controle.

        O-MUDO-E-DO-CONTROLE-01: o dono não diz nada deste controle, e o perfil
        (de antes da migração) diz calado no global e na peça. Nada se cala.

        MORDIDA: deixar o `muted` do perfil na vista do replug.
        """
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
        """Nem o autoswitch, nem o restore de boot, nem a troca explícita.

        O-MUDO-E-DO-CONTROLE-01 (28/09/2026), resposta 9 dela: o mudo é do
        controle e vale em todo jogo. Até ali a troca explícita levava o
        `muted` do perfil (MIC-GRAVACAO-01).

        MORDIDA: o `apply_mic` voltar a deixar o `muted` passar em `manual`.
        """
        m = mesa.com(_perfil(mic={"muted": True}))
        m.apply_mic(_perfil(mic={"muted": True}), origin=origem)
        assert mesa.applier.chamadas == [], (
            f"a ativação {origem} mexeu no mudo do microfone"
        )


class TestACuraEstaLIGADA:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa.

    A `sentinela_do_wrapper` nasceu com 19 testes e `grep` nenhum a chamava.
    Esta classe existe para que isto não se repita aqui.
    """

    def test_o_daemon_chama_o_gancho_nos_dois_caminhos_de_replug(self) -> None:
        """Os DOIS pontos: o laço por alvo e a borda de alvo novo.

        MORDIDA: apagar uma das duas chamadas de `connection.py`.
        """
        from pathlib import Path

        fonte = Path(
            "src/hefesto_dualsense4unix/daemon/connection.py"
        ).read_text(encoding="utf-8")
        assert fonte.count("await reapply_mic_after_connect") == 2, (
            "o gancho do microfone não cobre os dois caminhos de replug"
        )
        # Onde o alto-falante é reaplicado, o microfone também tem de ser.
        assert fonte.count("await reapply_speaker_after_connect") == 2

    def test_cada_um_tem_o_proprio_suppress(self) -> None:
        """O alto-falante falhar não pode custar o mudo do microfone dela.

        MORDIDA: pôr os dois `await` dentro do mesmo `contextlib.suppress`.
        """
        from pathlib import Path

        fonte = Path(
            "src/hefesto_dualsense4unix/daemon/connection.py"
        ).read_text(encoding="utf-8")
        # Cada chamada do mic é precedida do SEU `with contextlib.suppress`.
        pedacos = fonte.split("await reapply_mic_after_connect")
        for antes in pedacos[:-1]:
            cauda = antes[-120:]
            assert "contextlib.suppress" in cauda, (
                "uma chamada do microfone não tem `suppress` próprio"
            )

    def test_o_gancho_esta_no_all(self) -> None:
        from hefesto_dualsense4unix.daemon import connection

        assert "reapply_mic_after_connect" in connection.__all__
