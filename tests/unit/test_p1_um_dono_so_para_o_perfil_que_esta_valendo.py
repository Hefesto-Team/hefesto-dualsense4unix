"""P1 — quatro superfícies da mesma janela, duas respostas, o mesmo fato.

PERFIS-ABRE-O-QUE-GUARDA-01/§2.1/1 (24/08/2026), medido com o daemon VIVO,
nenhuma janela aberta, nenhum byte escrito:

    $ .venv/bin/python -c "…daemon_state_full().get('active_profile')"
    None
    $ cat ~/.config/hefesto-dualsense4unix/active_profile.txt   # Sackboy
    $ cat ~/.config/hefesto-dualsense4unix/session.json  # {"last_profile": "Sackboy"}

    aba Perfis   lê o DISCO   -> "Sackboy", em verde e no topo   (CERTO)
    aba Status   lê o daemon  -> "Nenhum"
    aba Início   lê o daemon  -> vazio
    aba No jogo  lê o daemon  -> vazio

A aba Perfis está certa e sozinha: a cura é da PERFIL-ATUAL-01 (10/08), e o
comentário dela já nomeava o caso — *"não é o `active_profile` do daemon
quando ele está vazio, que é o caso VIVO da máquina dela"*. As outras três
nunca receberam essa cura.

**A distinção que a tela precisa carregar**, e que não existia em lugar nenhum
antes desta entrega: *"nenhum perfil ativo"* e *"o daemon não sabe dizer"* são
fatos diferentes. O `or "Nenhum"` da aba Status funde os dois — é a tela
confundindo "não sei" com "não há", e é a mesma disciplina que
`secao_controles.py` já aplica ("um 'não sei' não pode virar aviso").

**O que este arquivo NÃO cobre, e é de propósito:** as abas Status
(`status_actions.py`) e "No jogo" (`widgets/painel_no_jogo.py`). Elas são de
outra frente nesta leva — a fiação delas ao dono está registrada no relatório
como tarefa aberta, com o endereço exato. Travá-las aqui pintaria de vermelho
o trabalho de quem ainda nem começou.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions as ha
from hefesto_dualsense4unix.app.actions import profiles_actions as pa

#: O estado que a máquina DELA reporta hoje: o daemon respondeu, e disse `null`.
DAEMON_SEM_NOME: dict[str, Any] = {"active_profile": None, "autoswitch_locked": True}


@pytest.fixture
def marcador_no_disco(monkeypatch: pytest.MonkeyPatch) -> str:
    """O `active_profile.txt` dela, sem tocar no disco dela.

    O dono lê o disco por `perfil_que_ela_ativou` → `resolve_boot_profile`, e é
    ESSE ponto que o dublê intercepta: assim o teste mede a decisão do dono, e
    não a montagem de dois arquivos de sessão.
    """
    monkeypatch.setattr(pa, "perfil_que_ela_ativou", lambda: "Sackboy")
    return "Sackboy"


@pytest.fixture
def disco_vazio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "perfil_que_ela_ativou", lambda: None)


class TestODonoResponde:
    def test_o_daemon_com_nome_vence_o_disco(
        self, marcador_no_disco: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O daemon é quem aplicou as seções — a resposta dele é a mais fresca."""
        vale = pa.perfil_que_esta_valendo({"active_profile": "Navegação"})
        assert vale == ("Navegação", "daemon")
        assert vale.rotulo == "Navegação"

    def test_o_daemon_sem_nome_cai_no_disco_e_o_disco_responde(
        self, marcador_no_disco: str
    ) -> None:
        """MORDE o P1: é o caso VIVO da máquina dela.

        Arranque a segunda perna do dono e este teste reprova com `None` —
        que é a aba Início ficando vazia ao lado da aba Perfis mostrando
        "Sackboy" em verde.
        """
        vale = pa.perfil_que_esta_valendo(DAEMON_SEM_NOME)
        assert vale.nome == "Sackboy"
        assert vale.fonte == "disco", (
            "a segunda perna tem de ser DECLARADA: sem saber que a resposta "
            "veio do disco, a tela não tem como escolher as palavras"
        )

    def test_daemon_que_respondeu_e_disco_vazio_e_nenhum(
        self, disco_vazio: None
    ) -> None:
        """Ninguém tem nome, e o daemon falou: não há perfil ativo. É um fato."""
        vale = pa.perfil_que_esta_valendo({"active_profile": None})
        assert vale.nome is None
        assert vale.fonte == "nenhum"
        assert vale.sabe is True
        assert vale.rotulo == pa.ROTULO_NENHUM

    def test_daemon_calado_e_disco_vazio_e_nao_sei(self, disco_vazio: None) -> None:
        """MORDE a distinção: "não sei" não pode virar "não há".

        Arranque o ramo e o rótulo vira "Nenhum" — a tela afirmando ausência
        de perfil quando o que houve foi ausência de resposta.
        """
        vale = pa.perfil_que_esta_valendo(None)
        assert vale.nome is None
        assert vale.fonte == "nao_sei"
        assert vale.sabe is False
        assert vale.rotulo == pa.ROTULO_NAO_SEI
        assert pa.ROTULO_NAO_SEI != pa.ROTULO_NENHUM, (
            "os dois rótulos existem para não serem o mesmo"
        )

    def test_resposta_que_nao_e_dicionario_e_nao_sei(self, disco_vazio: None) -> None:
        """Payload estranho é ausência de resposta, nunca ausência de perfil."""
        for lixo in ("Sackboy", 42, [], object()):
            assert pa.perfil_que_esta_valendo(lixo).fonte == "nao_sei"

    def test_nome_vazio_do_daemon_nao_conta_como_resposta(
        self, marcador_no_disco: str
    ) -> None:
        """String vazia é o mesmo `null` com outra roupa."""
        assert pa.perfil_que_esta_valendo({"active_profile": ""}).nome == "Sackboy"

    def test_o_disco_que_estoura_nao_derruba_a_thread_do_gtk(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Best-effort é requisito: o dono é chamado de dentro de repintura."""
        def _explode() -> str | None:
            raise OSError("disco cheio")

        monkeypatch.setattr(pa, "perfil_que_ela_ativou", _explode)
        with pytest.raises(OSError):
            pa.perfil_que_ela_ativou()
        # E o dono, que é quem a tela chama, degrada em "não sei".
        assert pa.perfil_que_esta_valendo(None).fonte == "nao_sei"


class TestAsSuperficiesConcordam:
    def test_a_aba_inicio_diz_o_mesmo_nome_que_a_aba_perfis(
        self, marcador_no_disco: str
    ) -> None:
        """MORDE a divergência, e NOMEIA a aba que discordou.

        Com o daemon respondendo `null` e o marcador dizendo "Sackboy", as
        duas superfícies do meu escopo têm de dizer a mesma coisa. Arranque a
        fiação de `autoswitch_lock_text` ao dono e a frase da Início volta a
        sair sem o nome — enquanto a aba Perfis, ao lado, mostra o verde.
        """
        da_aba_perfis = pa.perfil_que_esta_valendo(DAEMON_SEM_NOME).nome
        frase_da_inicio = ha.autoswitch_lock_text(DAEMON_SEM_NOME)

        divergiram: list[str] = []
        if da_aba_perfis != "Sackboy":
            divergiram.append("Perfis")
        if "Sackboy" not in frase_da_inicio:
            divergiram.append("Início")
        assert divergiram == [], (
            f"as abas {divergiram} discordam sobre qual perfil está valendo, "
            f"com o daemon dizendo null e o disco dizendo 'Sackboy'"
        )

    def test_sem_ninguem_saber_a_inicio_cala_o_nome(self, disco_vazio: None) -> None:
        """O silêncio é parte da cura: inventar nome seria pior que não dizer."""
        frase = ha.autoswitch_lock_text({"autoswitch_locked": True})
        assert "vale o perfil" not in frase
        assert "não troca sozinho" in frase, "o aviso do cadeado continua de pé"

    def test_o_cadeado_desligado_continua_sem_frase(
        self, marcador_no_disco: str
    ) -> None:
        """A cura não pode acender uma linha que não existia."""
        assert ha.autoswitch_lock_text({"autoswitch_locked": False}) == ""
        assert ha.autoswitch_lock_text(None) == ""
