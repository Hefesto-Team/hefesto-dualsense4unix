"""O ÚNICO ponto por onde a janela grava perfil em disco (GRAVA-POR-UM-FUNIL-01)."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.carona_do_wrapper import (
    GESTO_SALVAR,
    CaronaDoWrapperMixin,
)
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import PonteConfirmada, Profile
from hefesto_dualsense4unix.profiles.slug import mesmo_slug
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def carimbo_que_o_save_leva(
    existente: Profile | None, do_rascunho: PonteConfirmada | None
) -> PonteConfirmada | None:
    """Carimbo de ponte que um perfil leva ao disco. UM dono, os dois botões."""
    if existente is not None and existente.ponte is not None:
        return existente.ponte
    return do_rascunho


class ProfileWriterMixin(CaronaDoWrapperMixin):
    """Funil de gravação de perfil compartilhado pelos mixins da janela."""

    draft: Any


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
        8. confere a invariante com um assert barato;
        9. **pega a carona do wrapper** (CARONA-DO-WRAPPER-01) — repõe, se
           precisar, a chamada do `hefesto-launch` que a Steam apagou das
           Opções de Inicialização. Silencioso quando não há o que repor.

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
            path = save_profile(profile, origem=f"janela:{evento}")
            extra: Any = None
            if depois_no_worker is not None:
                try:
                    extra = depois_no_worker(profile)
                except Exception as exc:
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
            logger.info(f"{evento}_ok", nome=profile.name, path=str(path))
            self._reapontar_rascunho(profile, adotar_como_ativo=adotar_como_ativo)
            recarregar = getattr(self, "_reload_profiles_store", None)
            if recarregar is not None:
                recarregar(select_name=profile.name)
            avisar = getattr(self, "_notify_launch_env_refresh", None)
            if avisar is not None:
                avisar()
            if depois_na_janela is not None:
                depois_na_janela(profile, path, extra)
            self._conferir_invariante_de_gravacao(profile)
            self.pegar_carona_no_gesto(GESTO_SALVAR)
            return False

        def _ao_falhar(exc: Exception) -> bool:
            self._toast_de_gravacao(mensagem_erro(exc))
            logger.warning(f"{evento}_falhou", erro=str(exc))
            return False

        ipc_bridge.run_in_thread(_trabalho, on_success=_ao_gravar, on_failure=_ao_falhar)


    def _reapontar_rascunho(
        self, profile: Profile, *, adotar_como_ativo: bool
    ) -> None:
        """Faz o rascunho descrever o perfil que ACABOU de ir para o disco."""
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        ativo = getattr(self, "_active_profile_name", "") or ""
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
        """Assert barato: o rascunho aponta para o que ficou em disco."""
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
        """Mensagem na statusbar pelo caminho que o mixin dono já usa."""
        toast = getattr(self, "_footer_toast", None)
        if callable(toast):
            toast(msg)
            return
        self._status_toast("footer", msg)


def tem_edicao_pendente(dono: object) -> bool:
    """O rascunho em memória diverge do que veio do disco? (R-08)

    **A GUARDA FICOU SEM DONO — 08/09/2026.** Esta pergunta é a que protege o
    trabalho não salvo dela: enquanto ela responder "sim", a aba Perfis não
    deixa uma seleção que não foi gesto dela repintar o editor nem mover o alvo
    do Salvar (``_ha_trabalho_no_editor``, ``_refazer_as_abas_apos_ativar``).

    Ela morava em ``HefestoApp._tem_edicao_pendente`` e saiu do disco junto com
    a janela GTK (``D-0609-GTK-LEVA-INTEIRA``, ``f5311616``). A decisão dela
    foi *"a ideia sempre foi reaproveitar o que fiz no gtk"* — **o motor fica**
    —, e isto é motor: duas linhas que comparam dois ``DraftConfig``, sem um
    ``Gtk`` e sem um ``self._get`` dentro. Foi levada por engano.

    O QUE MEDIU O ENGANO, e não é leitura de código: ``_draft_baseline`` tinha
    **três escritores vivos** (``footer_actions._aplicar_perfil_ao_rascunho``,
    ``ProfileWriterMixin._reapontar_rascunho``,
    ``profiles_actions._reconciliar_rascunho_com_perfil_salvo``) e **zero
    leitores**. Um valor que três caminhos mantêm em dia e ninguém consulta é a
    assinatura de um leitor que caiu — e os dois ``getattr(self,
    "_tem_edicao_pendente", None)`` de ``profiles_actions`` passavam direto,
    tomando o caminho do "não há nada a proteger" em silêncio.

    POR QUE FUNÇÃO DE MÓDULO, e não um método herdado: o leitor
    (``ProfilesActionsMixin``) e os escritores (``ProfileWriterMixin`` e o
    ``FooterActionsMixin`` que dele desce) **não se herdam** — só compartilham
    o ``CaronaDoWrapperMixin``, cuja única razão de existir é a carona do
    wrapper. Pendurar a pergunta lá daria a uma classe de um assunto só um
    segundo assunto. É o mesmo argumento, o mesmo arquivo e a mesma forma de
    :func:`carimbo_que_o_save_leva` (PONTE-SOBREVIVE-A-CORRIDA-01): quando os
    dois lados precisam da MESMA resposta e nenhum descende do outro, a
    resposta vira função importável — e a divergência não tem onde nascer.

    ``baseline is None`` responde ``False`` de propósito: sem nenhuma foto do
    disco na história não há divergência a declarar, e era o comportamento da
    janela.
    """
    baseline = getattr(dono, "_draft_baseline", None)
    if baseline is None:
        return False
    return bool(getattr(dono, "draft", None) != baseline)


__all__ = ["ProfileWriterMixin", "tem_edicao_pendente"]
