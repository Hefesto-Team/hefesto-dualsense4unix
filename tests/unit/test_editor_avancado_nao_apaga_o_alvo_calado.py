"""O cinto: os três campos crus em branco não apagam o alvo do perfil calados.

Irmão de `test_editor_avancado_mostra_a_regra_de_verdade`, e a razão de existir
é a mesma foto dela de 10/08/2026 às 04:34 — mas aqui o assunto não é o que a
tela MOSTRA, e sim o que o Salvar GRAVA.

O QUE FOI MEDIDO (antes desta leva, com o editor dela em mãos):

    perfil "Pragmata", window_class ["steam_app_3357650"], prioridade 200
    → abrir na aba Perfis (página simples: "Jogo da Steam · 3357650")
    → trocar o número do jogo (gesto dela na regra)
    → ligar o "Modo avançado" (os três campos apareciam VAZIOS)
    → Salvar

    ... e o disco recebia ``{"type": "manual"}``. O perfil do jogo dela virava
    "Só manual (nunca ativa sozinho)" — deixava de entrar no jogo para sempre —
    com o toast dizendo "Perfil salvo" e nenhuma pergunta no caminho.

A cura irmã (a página avançada mostrar a regra de verdade) fecha ESSA porta.
O cinto é para a porta que sobra, e que é legítima: ela LER os três campos
cheios, apagá-los de propósito e clicar Salvar. Isso continua podendo — a
vontade dela na GUI prevalece sempre —, só não pode acontecer em silêncio.

Por que o aviso que a casa já tinha não cobria: `confirm_downgrade_match_to_any`
é guardado por ``isinstance(profile.match, MatchAny)``, e o editor avançado com
os três campos em branco grava ``MatchManual`` (R-12 item 3). Os dois são
"o perfil perdeu o alvo", mas por lados opostos — e o texto do diálogo antigo
("faz ele valer para TUDO") seria uma mentira exata aqui, porque o perfil passa
a valer para NADA.

Hermético: reusa os dublês de widget do arquivo irmão. Nenhum GTK real, nenhum
daemon, nenhuma escrita no ``~/.config`` dela.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
exigir_gi_real("O cinto do editor avançado (os três campos em branco)")

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions import profiles_actions as pa
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    MatchCriteria,
    MatchManual,
    Profile,
)
from tests.unit.test_editor_avancado_mostra_a_regra_de_verdade import (
    APPID,
    WM_JOGO,
    Editor,
    ligar_o_save,
    perfil_dela,
)

assert APPID  # o appid do Pragmata vem do arquivo irmão, e é o mesmo


@pytest.fixture(autouse=True)
def _sem_preferencia_no_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    """`on_profile_advanced_toggle` persiste a preferência — aqui não escreve."""
    monkeypatch.setattr(pa, "set_pref", lambda *_a, **_kw: None)


def _apagar_os_tres_campos(editor: Editor) -> None:
    """O gesto: ela seleciona o conteúdo dos três campos crus e apaga."""
    editor._get("profile_window_class_entry").set_text("")
    editor._get("profile_title_regex_entry").set_text("")
    editor._get("profile_process_name_entry").set_text("")


# ---------------------------------------------------------------------------
# 1. O predicado, sozinho (função pura, sem GTK)
# ---------------------------------------------------------------------------


class TestOPredicado:
    def test_perfil_de_jogo_virando_manual_pede_aviso(self) -> None:
        """O caso da foto: o perfil do jogo dela perdendo o alvo.

        MORDIDA: remover o predicado (ou deixá-lo devolver sempre False)
        reprova aqui.
        """
        antes = MatchCriteria(window_class=[WM_JOGO])
        assert pa.rebaixamento_para_so_manual(antes, MatchManual()) is True

    def test_perfil_sempre_virando_manual_pede_aviso(self) -> None:
        """"Sempre" → "nunca sozinho" é a mesma perda pelo outro lado.

        MORDIDA: guardar o predicado por `isinstance(antes, MatchCriteria)` —
        a tentação de copiar a forma do aviso antigo — reprova aqui.
        """
        assert pa.rebaixamento_para_so_manual(MatchAny(), MatchManual()) is True

    def test_quem_ja_era_so_manual_nao_pede_nada(self) -> None:
        """Round-trip do perfil manual: nada a perder, nada a perguntar.

        Um diálogo por Salvar vira o ruído que se aprende a clicar sem ler — e
        aí mata também o aviso que importa (a lição do
        `QUEDA_DE_PRIORIDADE_QUE_PEDE_AVISO`).

        MORDIDA: tirar o `and not _nunca_entra_sozinho(antes)` do predicado.
        """
        assert pa.rebaixamento_para_so_manual(MatchManual(), MatchManual()) is False

    def test_o_criteria_vazio_conta_como_so_manual_nos_dois_lados(self) -> None:
        """O acidente e a intenção têm a MESMA cara na tela — e o mesmo efeito.

        `_match_label` já trata os dois como "Só manual (nunca ativa sozinho)";
        o predicado não pode discordar da coluna "Quando usar".

        MORDIDA: trocar `_nunca_entra_sozinho` por um
        `isinstance(m, MatchManual)` reprova nas duas asserções.
        """
        vazio = MatchCriteria()
        assert pa.rebaixamento_para_so_manual(vazio, MatchManual()) is False
        assert (
            pa.rebaixamento_para_so_manual(
                MatchCriteria(process_name=["eldenring"]), vazio
            )
            is True
        )

    def test_continuar_com_alvo_nao_pede_nada(self) -> None:
        """Trocar de jogo não é perder o jogo — e não gera pergunta.

        MORDIDA: um predicado que respondesse "a regra mudou?" em vez de "o
        perfil perdeu o que o fazia entrar?" reprova aqui.
        """
        antes = MatchCriteria(window_class=[WM_JOGO])
        depois = MatchCriteria(window_class=["steam_app_1599660"])
        assert pa.rebaixamento_para_so_manual(antes, depois) is False


# ---------------------------------------------------------------------------
# 2. O Salvar pergunta — e obedece à resposta dela
# ---------------------------------------------------------------------------


class TestOSalvarPergunta:
    def _editor_aberto_no_jogo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> Editor:
        perfil = perfil_dela()
        editor = Editor(cache=[perfil])
        editor.selecionado = perfil.name
        editor._populate_editor(perfil)
        ligar_o_save(editor, monkeypatch)
        editor.ligar_o_avancado()
        return editor

    def test_apagar_os_tres_campos_e_salvar_pergunta_antes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O gesto legítimo que não pode ser silencioso.

        Ela vê os três campos (a cura irmã), apaga tudo, clica Salvar. O perfil
        do jogo passaria a nunca mais entrar sozinho — a janela pergunta, e o
        "não" dela não grava nada.

        MORDIDA: arranque o bloco `rebaixamento_para_so_manual` de
        `on_profile_save` e as duas asserções reprovam — `manual_perguntado`
        fica vazio e o `MatchManual` vai para o disco calado.
        """
        editor = self._editor_aberto_no_jogo(monkeypatch)
        editor.resposta_manual = False

        _apagar_os_tres_campos(editor)
        editor.on_profile_save(None)

        assert editor.manual_perguntado == [("Pragmata", "Só neste programa")]
        assert editor.salvos == []

    def test_o_aviso_cita_o_rotulo_da_coluna_quando_usar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O diálogo não pode chamar o perfil de uma coisa e a lista de outra.

        Mesma disciplina do `confirm_downgrade_match_to_any` desde a
        SALVAR-NAO-REBAIXA-02: o rótulo vem de `_match_label`, que é a fonte da
        coluna "Quando usar".

        MORDIDA: passar um literal no `regra_atual=` (ou omiti-lo) reprova
        aqui — o diálogo diria "Só neste programa" de um perfil que a lista
        chama de "Sempre".
        """
        perfil = Profile(name="vitoria", match=MatchAny(), priority=100)
        editor = Editor(cache=[perfil])
        editor.selecionado = perfil.name
        editor._populate_editor(perfil)
        ligar_o_save(editor, monkeypatch)
        editor.resposta_manual = False

        editor.ligar_o_avancado()
        # Um gesto dela na regra, para as guardas SALVAR-NAO-REBAIXA saírem da
        # frente: sem isso o Salvar preserva a regra do disco e não há o que
        # perguntar.
        editor._get("profile_window_class_entry").set_text("firefox")
        editor._get("profile_window_class_entry").set_text("")
        editor._regra_tocada = True
        editor.on_profile_save(None)

        assert editor.manual_perguntado == [("vitoria", "Sempre")]
        assert editor.salvos == []

    def test_ela_disse_sim_e_o_perfil_vira_so_manual(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NUNCA recusar o gesto dela: o cinto pergunta, não decide.

        MORDIDA: trocar a pergunta por uma recusa (um `return` seco quando os
        três campos estão vazios) reprova aqui — o perfil não seria salvo.
        """
        editor = self._editor_aberto_no_jogo(monkeypatch)
        editor.resposta_manual = True

        _apagar_os_tres_campos(editor)
        editor.on_profile_save(None)

        assert len(editor.manual_perguntado) == 1
        assert len(editor.salvos) == 1
        assert isinstance(editor.salvos[0].match, MatchManual)

    def test_o_perfil_que_ja_era_so_manual_salva_sem_perguntar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Round-trip do manual: abrir, mexer na prioridade, salvar — sem ruído.

        MORDIDA: um cinto guardado só por "os três campos estão vazios" (sem
        olhar o que o perfil ERA) pergunta aqui, e vira o diálogo que se
        aprende a clicar sem ler.
        """
        perfil = Profile(name="coop_local", match=MatchManual(), priority=45)
        editor = Editor(cache=[perfil])
        editor.selecionado = perfil.name
        editor._populate_editor(perfil)
        ligar_o_save(editor, monkeypatch)
        editor._regra_tocada = True

        editor.on_profile_save(None)

        assert editor.manual_perguntado == []
        assert len(editor.salvos) == 1
        assert isinstance(editor.salvos[0].match, MatchManual)

    def test_perfil_novo_com_os_tres_campos_vazios_nao_pergunta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Não há alvo a perder num arquivo que ainda não existe.

        MORDIDA: tirar o `original is not None` da guarda em `on_profile_save`
        faz o "Novo perfil" só-manual pedir confirmação do nada.
        """
        editor = Editor(cache=[])
        ligar_o_save(editor, monkeypatch)
        editor.on_profile_new(None)
        editor._get("profile_name_entry").set_text("Só na mão")
        editor.ligar_o_avancado()
        editor._regra_tocada = True

        editor.on_profile_save(None)

        assert editor.manual_perguntado == []
        assert len(editor.salvos) == 1
        assert isinstance(editor.salvos[0].match, MatchManual)

    def test_o_aviso_antigo_continua_sendo_o_dono_do_caminho_dele(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """COR-A intacta: virar "Sempre" segue perguntando pelo diálogo antigo.

        Os dois avisos são irmãos, não concorrentes — e o novo não pode ter
        roubado o caminho do velho.

        MORDIDA: fundir os dois avisos num diálogo só, ou trocar o `if` solto
        do cinto novo por um `elif` mal encaixado, reprova aqui.
        """
        perfil = perfil_dela()
        editor = Editor(cache=[perfil])
        editor.selecionado = perfil.name
        editor._populate_editor(perfil)
        ligar_o_save(editor, monkeypatch)
        editor.resposta_downgrade = False

        editor._aplica_a.set_active_id("any")
        editor.on_profile_save(None)

        assert editor.downgrade_perguntado == [("Pragmata", "Só neste programa")]
        assert editor.manual_perguntado == []
        assert editor.salvos == []


# ---------------------------------------------------------------------------
# 3. O diálogo novo obedece às duas doutrinas da casa
# ---------------------------------------------------------------------------


class TestODialogoNovo:
    def test_passa_pelo_envelope_da_casa(self) -> None:
        """DIÁLOGO-QUE-MATA-A-JANELA-01: nada de `dialog.run()` cru.

        MORDIDA: trocar `executar_dialogo(dialog, ...)` por `dialog.run()` no
        diálogo novo reprova aqui — e derrubaria a janela dela de verdade.
        """
        import inspect

        from hefesto_dualsense4unix.app import gui_dialogs

        src = inspect.getsource(gui_dialogs.confirm_downgrade_match_to_manual)
        assert "executar_dialogo(" in src
        assert ".run()" not in src

    def test_nasce_com_o_tema_do_app(self) -> None:
        """GUI-05/P5: diálogo sem a classe abre CLARO no COSMIC (XWayland).

        MORDIDA: apagar a linha `_apply_app_theme(dialog)` do diálogo novo.
        """
        import inspect

        from hefesto_dualsense4unix.app import gui_dialogs

        src = inspect.getsource(gui_dialogs.confirm_downgrade_match_to_manual)
        assert "_apply_app_theme(" in src

    def test_o_default_e_cancelar(self) -> None:
        """Um Enter distraído não pode custar a regra do perfil dela.

        Mesma escolha do `confirm_downgrade_match_to_any`, e pela mesma razão.

        MORDIDA: trocar o default para `Gtk.ResponseType.OK` (o que o
        `prompt_overwrite_existing` faz, porque lá o preço é outro).
        """
        import inspect

        from hefesto_dualsense4unix.app import gui_dialogs

        src = inspect.getsource(gui_dialogs.confirm_downgrade_match_to_manual)
        assert "set_default_response(Gtk.ResponseType.CANCEL)" in src

    def test_o_texto_nao_promete_o_contrario_do_que_acontece(self) -> None:
        """O diálogo antigo diz "vale para TUDO" — aqui é o oposto exato.

        Reusar aquela frase seria o aviso mentindo sobre o que ela vai perder.

        MORDIDA: copiar o texto secundário do `confirm_downgrade_match_to_any`
        para o diálogo novo reprova nas duas asserções.
        """
        import inspect

        from hefesto_dualsense4unix.app import gui_dialogs

        src = inspect.getsource(gui_dialogs.confirm_downgrade_match_to_manual)
        assert "para TUDO" not in src
        assert "sozinho" in src
