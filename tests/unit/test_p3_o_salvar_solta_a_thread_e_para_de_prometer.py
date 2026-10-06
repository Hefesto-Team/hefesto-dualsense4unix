"""P3 + P3b — o Salvar segurava a janela, e comemorava o que não aconteceu.

PERFIS-ABRE-O-QUE-GUARDA-01/§2.2/2 e §2.2/3 (24/08/2026). Dois defeitos na
mesma linha de código, e o botão VIZINHO já tinha os dois curados:

**A thread.** `on_profile_save` chamava `profile_switch()` — síncrono — na
thread do GTK. O handler `profile.switch` levou **~1,2 s MEDIDOS no journal
da bancada**, número escrito no comentário de `on_profile_activate`, e foi por ele
que o **Ativar** virou `call_async` na ATIVAR-NAO-MENTE-01. O Salvar ficou.

**A promessa.** `profile_switch()` devolve um booleano cujo significado a
própria docstring declara: *"o daemon não confirmou"*. Nunca *"as seções
entraram"*. O Salvar lia o `True` como a segunda coisa e escrevia **"Perfil
salvo e reaplicado no controle"**. Com o jogo aberto, o gate R-04 recusa
seções: o daemon responde, o booleano é `True`, nada chega ao controle, e a
janela comemora. Cem linhas acima, no mesmo arquivo, o Ativar já sabia dizer
o que ficou de fora.

**Por que as duas curas são uma só costura**, e este arquivo trava isso: a
peça que devolve o CORPO do daemon numa chamada síncrona (`_corpo_do_daemon`)
sai com o teto de LEITURA de 250 ms, e o `profile.switch` não cabe nele.
Trocar só o texto, mantendo a chamada síncrona, ressuscitaria a
ATIVAR-NAO-MENTE-01 pelo avesso — todo Salvar cairia no caminho de falha por
timeout, com a ativação acontecendo.

**O que este arquivo NÃO afirma.** Que o Salvar inteiro saiu da thread do GTK.
`save_profile` continua lá (e continua sendo a exceção datada ao
`ProfileWriterMixin`). O que saiu é a perna de ~1,2 s, que é a que a medição
nomeia.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("p3: o Salvar solta a thread")

from typing import Any


from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

RECUSA_DO_R04: dict[str, Any] = {
    "secoes": {"mode": "aplicado", "rumble_policy": "adiado_lock_manual"}
}
RECUSA_TOTAL: dict[str, Any] = {"secoes": {"rumble_policy": "adiado_lock_manual"}}
TUDO_ENTROU: dict[str, Any] = {"secoes": {"rumble_policy": "aplicado"}}


class TestAFraseDoSalvar:
    def test_sem_reaplicar_nao_diz_uma_palavra_sobre_o_controle(self) -> None:
        """O perfil salvo não era o ativo: o disco mudou, o controle não."""
        assert pa.mensagem_do_salvar("Sackboy") == "Perfil salvo: Sackboy"

    def test_reaplicado_sem_relatorio_mantem_a_frase_que_ela_aprovou(self) -> None:
        """Daemon antigo, ou resposta sem `secoes`: sem informação, sem alarme."""
        assert pa.mensagem_do_salvar("Sackboy", reaplicou=True) == (
            "Perfil salvo e reaplicado no controle: Sackboy"
        )

    def test_reaplicado_com_tudo_dentro_mantem_a_frase_de_sempre(self) -> None:
        assert pa.mensagem_do_salvar(
            "Sackboy", reaplicou=True, result=TUDO_ENTROU
        ) == "Perfil salvo e reaplicado no controle: Sackboy"

    def test_secao_recusada_e_nomeada_em_vez_de_comemorada(self) -> None:
        """MORDE o P3b: com a cura arrancada sai o texto plano de hoje."""
        frase = pa.mensagem_do_salvar(
            "Sackboy", reaplicou=True, result=RECUSA_DO_R04
        )
        assert "reaplicado no controle" not in frase, (
            "o gate R-04 recusou a seção e a janela disse que aplicou"
        )
        assert "vibração" in frase, "o toast não nomeia o que ficou de fora"

    def test_a_frase_do_que_ficou_de_fora_e_a_mesma_do_botao_ativar(self) -> None:
        """Igualdade, não semelhança: dois donos da mesma frase derivam."""
        do_salvar = pa.mensagem_do_salvar(
            "Sackboy", reaplicou=True, result=RECUSA_DO_R04
        )
        do_ativar = pa.mensagem_de_ativacao("Sackboy", RECUSA_DO_R04)
        cauda_salvar = do_salvar.split(" — ", 1)[1]
        cauda_ativar = do_ativar.split(" — ", 1)[1]
        assert cauda_salvar == cauda_ativar

    def test_o_rename_diz_os_dois_nomes_nos_tres_estados(self) -> None:
        assert pa.mensagem_do_salvar("Sackboy", "sackboy_nativo") == (
            "Perfil renomeado: sackboy_nativo → Sackboy"
        )
        assert pa.mensagem_do_salvar(
            "Sackboy", "sackboy_nativo", reaplicou=True
        ) == "Perfil renomeado: sackboy_nativo → Sackboy (reaplicado no controle)"
        com_recusa = pa.mensagem_do_salvar(
            "Sackboy", "sackboy_nativo", reaplicou=True, result=RECUSA_DO_R04
        )
        assert "sackboy_nativo → Sackboy" in com_recusa
        assert "reaplicado no controle" not in com_recusa
        assert "vibração" in com_recusa

    def test_com_tudo_recusado_a_frase_diz_que_nada_chegou(self) -> None:
        """O caso mais caro: o lock manual dela recusa a troca inteira."""
        frase = pa.mensagem_do_salvar(
            "Sackboy", reaplicou=True, result=RECUSA_TOTAL
        )
        assert frase == "Perfil salvo: Sackboy — Nada foi aplicado ao controle."


class _Entry:
    def __init__(self, texto: str = "") -> None:
        self._t = texto

    def get_text(self) -> str:
        return self._t

    def set_text(self, texto: str) -> None:
        self._t = texto


class _Escala:
    def get_value(self) -> float:
        return 0.0

    def set_value(self, _v: float) -> None: ...


class _Editor(pa.ProfilesActionsMixin):  # type: ignore[misc]
    """Só o que a decisão de gravar consulta — mesmo molde do R-10."""

    def __init__(self, nome: str = "Sackboy", ativo: str | None = "Sackboy") -> None:
        self._profiles_cache: list[Profile] = []
        self._duplicate_source = None
        self._new_profile = True
        self._widgets: dict[str, Any] = {
            "profile_name_entry": _Entry(nome),
            "profile_priority_scale": _Escala(),
            "main_window": object(),
        }
        self.ativo = ativo
        self.toasts: list[str] = []
        self.salvos: list[Profile] = []

    def _get(self, wid: str) -> Any:
        return self._widgets.get(wid)

    def _selected_profile_name(self, _selection: Any = None) -> str | None:
        return None

    def _build_profile_from_editor(self) -> Profile:
        return Profile(
            name=self._widgets["profile_name_entry"].get_text(),
            match=MatchAny(),
            priority=0,
        )

    def _reload_profiles_store(self, **_kw: Any) -> None: ...

    def _notify_launch_env_refresh(self) -> None: ...

    def _reconciliar_rascunho_com_perfil_salvo(self, *_a: Any) -> None: ...

    def pegar_carona_no_gesto(self, _gesto: str = "") -> None: ...

    def _toast_profile(self, msg: str) -> None:
        self.toasts.append(msg)


