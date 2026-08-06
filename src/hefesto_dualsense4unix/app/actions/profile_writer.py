"""O ÚNICO ponto por onde a janela grava perfil em disco (GRAVA-POR-UM-FUNIL-01).

A INVARIANTE desta casa, escrita uma vez para valer em todo botão:

    Toda gravação de perfil feita pela janela termina com o rascunho apontando
    para o que ficou em DISCO — ``draft.source_name == profile.name`` e os
    demais ``source_*`` iguais aos do perfil gravado.

Por que ela precisa de um funil, e não de disciplina:

O ``DraftConfig`` guarda uma FOTOGRAFIA do perfil de onde veio (os ``source_*``)
e o ``to_profile`` decide por ela — o gate ``mesmo_perfil``
(``draft_config.py``) pergunta se o nome que está sendo salvo é o mesmo da
fotografia. Enquanto a fotografia envelhece, o gate responde ``False`` para
sempre, e cada save seguinte grava ``MatchAny()`` com prioridade
``max(catch-all) + folga``. MEDIDO no caminho do rodapé em 04/08/2026: o
primeiro "Salvar Perfil" nasce com prioridade 10, o SEGUNDO com o mesmo nome
nasce com 20, o terceiro com 30 — uma catraca que empurra o perfil dela para
cima a cada gesto e apaga a regra de janela no caminho. É a queixa crônica
("a config que eu deixo nunca é respeitada") entrando por uma porta nova.

``DraftConfig.with_profile_identity`` existe desde a ABAS-01 (25/07) para curar
exatamente isto, e a docstring dele descreve o caminho do rodapé como o defeito
— mas tinha UM único chamador em produção (a aba Perfis). O rodapé, que grava
por três botões diferentes (Salvar, Importar, Restaurar Padrão), não chamava
nenhum. Lembrar de chamar não é engenharia: quem escrever o quarto botão vai
esquecer de novo.

Então o caminho de gravação passa a ser um só, e ele é quem se lembra. O portão
``tests/unit/test_gravacao_de_perfil_passa_pelo_funil.py`` reprova qualquer
``save_profile(`` novo dentro de ``app/`` fora daqui — quem escrever o quinto
botão não precisa lembrar de nada, porque não consegue gravar por fora.

Thread: o I/O de disco corre no worker de ``ipc_bridge.run_in_thread``
(PERF-FOOTER-ASYNC-IO-01) e todo o resto na thread GTK. Cada gancho declara em
qual das duas roda — a documentação disso é o motivo de os nomes serem longos.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.profiles.slug import mesmo_slug
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


class ProfileWriterMixin(WidgetAccessMixin):
    """Funil de gravação de perfil compartilhado pelos mixins da janela.

    Herdar daqui (em vez de importar uma função solta) é o que dá ao funil
    acesso ao ``self.draft``, ao ``_active_profile_name`` e aos irmãos de mixin
    — os mesmos que o defeito atravessava.
    """

    # Referência ao rascunho central (definida em HefestoApp.__init__).
    draft: Any  # DraftConfig — evita import circular; validado em runtime

    # ------------------------------------------------------------------
    # O funil
    # ------------------------------------------------------------------

    def _gravar_perfil_async(
        self,
        construir: Callable[[], Profile],
        *,
        adotar_como_ativo: bool,
        mensagem_ok: Callable[[Profile, Path], str],
        mensagem_erro: Callable[[Exception], str],
        evento: str,
        depois_no_worker: Callable[[Profile], Any] | None = None,
        depois_na_janela: Callable[[Profile, Path, Any], None] | None = None,
    ) -> None:
        """Grava um perfil e deixa a janela coerente com o disco.

        Faz, nesta ordem e sem exceção:

        1. ``construir()`` **no worker** — devolve o ``Profile`` a gravar;
        2. ``save_profile`` **no worker** — a única gravação de perfil da GUI;
        3. ``depois_no_worker(profile)`` **no worker**, opcional — I/O extra que
           o chamador precisa fazer com o disco já atualizado (o "Restaurar
           Padrão" relê o perfil para recarregar o rascunho inteiro);
        4. toast e log **na janela**;
        5. reaponta o rascunho (``with_profile_identity``) e zera a linha de
           base **na janela** — a INVARIANTE do módulo;
        6. recarrega a lista de perfis e avisa o daemon
           (``launch_env.refresh``) **na janela**;
        7. ``depois_na_janela(profile, path, extra)``, opcional;
        8. confere a invariante com um assert barato.

        ``adotar_como_ativo`` diz se ESTA gravação é a do rascunho:

        - ``True`` — "Salvar Perfil" e "Restaurar Padrão": o gesto dela É trocar
          o que a janela está editando, mesmo com nome novo;
        - ``False`` — "Importar": o perfil importado não é o que as abas estão
          editando. Ainda assim o rascunho é reapontado quando o arquivo
          gravado é o do perfil ATIVO (mesmo slug) — nesse caso o disco mudou
          debaixo dele, e não reapontar deixaria a fotografia velha, que é o
          defeito inteiro visto de outro ângulo.
        """

        def _trabalho() -> tuple[Profile, Path, Any]:
            profile = construir()
            # `origem` carimba o `profile_salvo` do journal com QUEM gravou.
            # Sem isto o registro cai no basename do processo, que para a GUI
            # é sempre o mesmo — e foi exatamente essa cegueira que impediu, na
            # madrugada de 05/08, decidir se a prioridade 191 do disco dela veio
            # da catraca do rodapé ou do controle deslizante. Aqui a resposta
            # passa a estar na linha, junto do `match_antes`/`match_depois`.
            path = save_profile(profile, origem=f"janela:{evento}")
            extra: Any = None
            if depois_no_worker is not None:
                try:
                    extra = depois_no_worker(profile)
                except Exception as exc:
                    # O arquivo JÁ está no disco: transformar isto em "falha ao
                    # salvar" seria mentir para ela sobre o que aconteceu.
                    logger.warning(
                        "gravar_perfil_pos_gravacao_falhou",
                        evento=evento,
                        nome=profile.name,
                        erro=str(exc),
                    )
            return profile, path, extra

        def _ao_gravar(resultado: tuple[Profile, Path, Any]) -> bool:
            profile, path, extra = resultado
            self._toast_de_gravacao(mensagem_ok(profile, path))
            # `evento` é a RAIZ do nome: os dois lados (`_ok`/`_falhou`) saem
            # dela, e os nomes que o journal já conhecia continuam iguais.
            logger.info(f"{evento}_ok", nome=profile.name, path=str(path))
            self._reapontar_rascunho(profile, adotar_como_ativo=adotar_como_ativo)
            recarregar = getattr(self, "_reload_profiles_store", None)
            if recarregar is not None:
                recarregar(select_name=profile.name)
            # DEDUP-04: o conjunto de perfis mudou — o daemon rematerializa o
            # `steam_app_<appid>.env` de antecipação AGORA, senão o primeiro
            # launch do jogo cai no `default.env` rançoso.
            avisar = getattr(self, "_notify_launch_env_refresh", None)
            if avisar is not None:
                avisar()
            if depois_na_janela is not None:
                depois_na_janela(profile, path, extra)
            self._conferir_invariante_de_gravacao(profile)
            return False  # GLib.idle_add não repete

        def _ao_falhar(exc: Exception) -> bool:
            self._toast_de_gravacao(mensagem_erro(exc))
            logger.warning(f"{evento}_falhou", erro=str(exc))
            return False

        ipc_bridge.run_in_thread(_trabalho, on_success=_ao_gravar, on_failure=_ao_falhar)

    # ------------------------------------------------------------------
    # Peças do funil (separadas para serem legíveis, não para serem chamadas
    # de fora — quem grava chama `_gravar_perfil_async` e mais nada)
    # ------------------------------------------------------------------

    def _reapontar_rascunho(
        self, profile: Profile, *, adotar_como_ativo: bool
    ) -> None:
        """Faz o rascunho descrever o perfil que ACABOU de ir para o disco.

        É a linha que faltava no rodapé. Sem ela o ``source_name`` continua
        apontando para o perfil anterior, o gate ``mesmo_perfil`` do
        ``to_profile`` responde ``False`` para sempre e o save seguinte grava
        ``MatchAny()`` com a prioridade recalculada — a catraca 10 → 20 → 30.

        ``_draft_baseline`` acompanha (R-08): o que estava em memória virou
        disco, então a edição deixa de ser "pendente" e a reconciliação com o
        perfil ativo volta a rodar pelo resto da sessão.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        ativo = getattr(self, "_active_profile_name", "") or ""
        # Gravar OUTRO perfil (importar um arquivo que não é o que as abas
        # editam) não pode mexer no rascunho dela — a mesma guarda que a aba
        # Perfis usa em `_reconciliar_rascunho_com_perfil_salvo`.
        e_do_rascunho = adotar_como_ativo or (
            bool(ativo) and mesmo_slug(profile.name, ativo)
        )
        if not e_do_rascunho:
            return
        self.draft = draft.with_profile_identity(profile)
        self._active_profile_name = profile.name
        self._draft_baseline = self.draft

    def _conferir_invariante_de_gravacao(self, profile: Profile) -> None:
        """Assert barato: o rascunho aponta para o que ficou em disco.

        Só cobra quando a gravação É a do rascunho (o import de OUTRO perfil
        deixa o rascunho onde estava, de propósito). Se disparar, o defeito é
        alguém ter trocado a ordem dos passos do funil — e o lugar de descobrir
        isso é a suíte, não o disco dela.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        ativo = getattr(self, "_active_profile_name", "") or ""
        if not ativo or not mesmo_slug(profile.name, ativo):
            return
        assert draft.source_name == profile.name, (
            "gravação sem reapontar o rascunho: source_name "
            f"{draft.source_name!r} != {profile.name!r}"
        )
        assert draft.source_priority == profile.priority, (
            "gravação sem reapontar o rascunho: source_priority "
            f"{draft.source_priority!r} != {profile.priority!r}"
        )

    def _toast_de_gravacao(self, msg: str) -> None:
        """Mensagem na statusbar pelo caminho que o mixin dono já usa.

        ``_footer_toast`` quando existe (é o que os dublês de teste substituem
        e o que o rodapé instrumenta); a statusbar crua quando o funil é usado
        por um mixin que não tem rodapé.
        """
        toast = getattr(self, "_footer_toast", None)
        if callable(toast):
            toast(msg)
            return
        self._status_toast("footer", msg)


__all__ = ["ProfileWriterMixin"]
