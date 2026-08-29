"""PONTE-CONFIRMADA-01 — o carimbo sobrevive ao gesto mais banal dela: Salvar.

O DEFEITO, medido em 22/08/2026 (defeito 1 dos oito de código do
``docs/process/SPRINT_ORDER.md``): ``DraftConfig.to_profile`` reconstrói o
``Profile`` do zero e não conhecia o campo ``ponte``. Então TODO "Salvar Perfil"
pelo rodapé apagava o carimbo — e a aba Perfis junto, que usa
``to_profile(ativo)`` como base do que grava
(``profiles_actions._build_profile_from_editor``).

O que se perdia não é preferência dela: é o que o produto APRENDEU sozinho. Sem
o carimbo, o jogo cai do ``manager.pontes_confirmadas()``, a data e a origem da
confirmação morrem, e a escada de ``integrations/ponte_escada.py`` recomeça do
primeiro degrau no lançamento seguinte — que é recriar o vpad com o jogo aberto
e arrancar o controle da mão dela (R-04, medido em 23/07). Custo diário, num
gesto que a tela nem sabe nomear.

A CURA É PASSTHROUGH SOMENTE-LEITURA, no molde do ``source_match`` e irmãos, e a
ausência de escritor É a entrega — tem caso próprio aqui
(``TestOTransporteNaoEEscrita``). Se a janela ganhasse campo para este valor,
todo save carimbaria como confirmada uma ponte que ninguém confirmou, a escada
pararia em TODO jogo e o produto passaria a jurar que sabe o que não sabe. Quem
carimba é ``profiles.manager.confirmar_ponte``, depois de uma confirmação de
verdade (gesto no controle, silêncio de quem jogou, ou escolha direta dela).

O SEGUNDO DEFEITO, medido em 28/08/2026 (PONTE-SOBREVIVE-A-CORRIDA-01): o
passthrough acima é uma FOTOGRAFIA, e quem carimba é outro processo. Carimbo
nascido depois de a janela abrir morria no Salvar seguinte da aba Perfis — duas
vezes no histórico dela. A razão inteira está em
``TestOCarimboQueChegouDepoisDaFotografia``.

São SETE peças, e cada uma foi arrancada, medida e devolvida — as seis primeiras
em 22/08/2026 (``sha256`` conferido nos três arquivos), a sétima em 28/08. A
contagem está escrita porque portão em série engana (19/08): duas curas podem
responder pelo mesmo vermelho.

1. ``source_ponte=profile.ponte`` em ``from_profile``. Arrancada: **2 reprovam**
   — ``test_o_rascunho_leva_o_carimbo_de_volta_ao_perfil`` (no PRIMEIRO assert,
   "o rascunho nasceu sem a fotografia do carimbo") e o caso da aba Perfis;
2. ``ponte=self.source_ponte if mesmo_perfil else None`` em ``to_profile``.
   Arrancada: **os mesmos 2** — e a distinção entre esta peça e a de cima é o
   assert que cai: aqui o primeiro passa e reprova o SEGUNDO. O caso do rodapé
   por cima do mesmo perfil NÃO reprova, porque o degrau de disco da peça 4
   ainda o salva; é por isso que a testemunha do passthrough é sem disco;
3. o gate ``mesmo_perfil`` desse passthrough. Arrancado (passthrough
   incondicional): **4 reprovam** — os dois casos de nome novo do rodapé e os
   dois de nome novo do rascunho;
4. ``footer_actions._carimbo_do_save``, o degrau de DISCO. Arrancado (devolvendo
   só o carimbo do rascunho): **1 reprova** —
   ``test_salvar_por_cima_de_outro_perfil_nao_apaga_o_carimbo_dele``, com
   ``ponte`` ausente do arquivo do vizinho;
5. ``"source_ponte": profile.ponte`` em ``with_profile_identity``. Arrancada:
   **2 reprovam** — ``test_a_fotografia_do_carimbo_acompanha_o_perfil_gravado``
   e ``test_o_segundo_save_do_nome_novo_tambem_nasce_sem_carimbo``: o rascunho
   seguiria com o carimbo do perfil ANTERIOR e o segundo save, já com
   ``mesmo_perfil`` verdadeiro, o gravaria no perfil novo;
6. a guarda ``estreia`` de ``_build_profile_from_editor``, hoje reduzida ao
   corte do degrau 2 (ver a peça 7). Arrancada — passando ``source.ponte``
   também na estreia: **2 reprovam**, a cópia do "Duplicar" nascendo carimbada
   nos dois casos que a medem;
7. o degrau de DISCO da aba Perfis (``perfil_em_disco(name)`` alimentando
   ``carimbo_que_o_save_leva``), PONTE-SOBREVIVE-A-CORRIDA-01, 28/08/2026.
   Arrancado — a consulta de volta para dentro de ``if estreia:``: **3
   reprovam**, os três casos de ``TestOCarimboQueChegouDepoisDaFotografia``.
   Trocado pelo CACHE (``_perfil_que_o_salvar_sobrescreve``, que era a cura
   óbvia): **os mesmos 3 reprovam** — é a medição que prova que só o arquivo
   responde, porque o cache é a outra fotografia da janela.

E as peças 2 e 4 estão em SÉRIE no caminho do rodapé: arrancadas JUNTAS, **4
reprovam** — entre elas ``test_salvar_por_cima_do_mesmo_perfil_preserva_o_carimbo``,
que é o custo diário reproduzido. Nenhuma das duas sozinha o derruba, e é por
isso que o passthrough tem testemunha SEM disco.

A ORDEM dos degraus também é peça, e ganhou testemunha própria em 28/08:
invertida (rascunho antes do disco), **1 reprova** —
``test_o_disco_vence_a_fotografia_quando_os_dois_tem_carimbo``. Os casos de
disco das classes acima não a alcançam, porque neles o rascunho está vazio e os
dois degraus concordam.

Os dois casos de ``TestOTransporteNaoEEscrita`` também foram mordidos, um a um:
um ``model_copy(update={"source_ponte": ...})`` plantado em
``app/actions/emulation_actions.py`` e um ``with_ponte`` plantado no
``DraftConfig`` reprovam um caso cada, nomeando o arquivo e o método.

Hermético: o ``_hefesto_fake_env`` do ``conftest`` isola ``XDG_CONFIG_HOME`` num
tmp por teste, e a fixture ``disco`` aponta o ``profiles_dir`` do loader para
dentro dele. Nenhum byte sai para o ``~/.config`` dela.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer `import gi`, e no lugar do
# `pytest.importorskip("gi")` — que ACEITA o stub plantado por outro arquivo.
exigir_gi_real("o carimbo de ponte no Salvar Perfil")

import ast
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.loader import load_all_profiles, save_profile
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    MatchManual,
    PonteConfirmada,
    Profile,
    ProfileModeConfig,
)

#: A raiz da janela, para o caso que prova a AUSÊNCIA de escritor.
_APP = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix" / "app"

#: O DON'T SCREAM — o jogo da noite em que ela decidiu que o produto CONSTRÓI a
#: ponte (19/08/2026), e o appid que a frente inteira usa como caso.
_APPID = "2054970"
_WM_DO_JOGO = f"steam_app_{_APPID}"


def _carimbo() -> PonteConfirmada:
    """Um carimbo com valores que NÃO são default nenhum.

    Máscara ``xbox`` (o default do produto é dualsense), ``steam_input`` ligado,
    data fixa e confirmação por SILÊNCIO (o default do campo é ``gesto``). Um
    carimbo que sobrevivesse "por acaso" — recriado do zero pelo esquema — não
    traria nenhum destes valores de volta, e o teste ficaria verde sem medir.
    """
    return PonteConfirmada(
        kind="gamepad",
        gamepad_flavor="xbox",
        steam_input=True,
        confirmada_em="2026-08-19T21:30:00-03:00",
        confirmada_por="silencio",
    )


def _perfil_do_jogo(
    nome: str = "DontScream", *, carimbo: bool = True, prioridade: int = 60
) -> Profile:
    """Perfil com REGRA de jogo — a única forma que declara um appid."""
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=[_WM_DO_JOGO]),
        priority=prioridade,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox"),
        ponte=_carimbo() if carimbo else None,
    )


# ---------------------------------------------------------------------------
# Aparelhagem — a mesma do funil de gravação, pelo mesmo motivo
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _sync_run_in_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """``ipc_bridge.run_in_thread`` síncrono — sem loop GTK não há callback.

    PERF-FOOTER-ASYNC-IO-01 pôs o I/O de disco num worker; worker e callback na
    mesma thread preservam a semântica observável.
    """

    def _sync(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        try:
            resultado = fn()
        except Exception as exc:  # espelha o run_in_thread real
            if on_failure is not None:
                on_failure(exc)
            return
        on_success(resultado)

    monkeypatch.setattr(footer_actions.ipc_bridge, "run_in_thread", _sync)


@pytest.fixture
def disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o disco de verdade, num tmp."""
    import hefesto_dualsense4unix.profiles.loader as loader_mod

    destino = tmp_path / "profiles"
    destino.mkdir()
    monkeypatch.setattr(loader_mod, "profiles_dir", lambda ensure=False: destino)
    return destino


def _janela_fake(draft: DraftConfig, ativo: str = "") -> Any:
    """Dublê com os DOIS mixins que o ``HefestoApp`` compõe de verdade.

    O cálculo da prioridade mora na aba Perfis e o gesto de salvar mora no
    rodapé — são irmãos na MRO do aplicativo, e medir o rodapé sem o irmão
    mediria uma composição que não existe.
    """
    from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
    from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin

    class _Janela(ProfilesActionsMixin, FooterActionsMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self.draft = draft
            self._active_profile_name = ativo
            self._draft_baseline: Any = draft
            self._profiles_cache: list[Profile] = list(load_all_profiles())
            self._toasted: list[str] = []
            builder = MagicMock()
            builder.get_object.return_value = MagicMock()
            self.builder = builder

        def _reload_profiles_store(
            self, select_name: str | None = None, on_done: Any | None = None
        ) -> None:
            self._profiles_cache = list(load_all_profiles())
            if on_done is not None:
                on_done()

        def _footer_toast(self, msg: str, context: str = "footer") -> None:
            self._toasted.append(msg)

        def _toast_profile(self, msg: str) -> None:
            self._toasted.append(msg)

        def _notify_launch_env_refresh(self) -> None:
            return None

    return _Janela()


def _salvar_pelo_rodape(janela: Any, nome: str) -> None:
    """O gesto dela: botão "Salvar Perfil", digita ``nome``, confirma."""
    dialogos = MagicMock()
    dialogos.prompt_profile_name.return_value = nome
    dialogos.prompt_overwrite_existing.return_value = True
    with patch(
        "hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", dialogos
    ):
        janela.on_save_profile()


def _arquivo(disco: Path, slug: str) -> dict[str, Any]:
    return json.loads((disco / f"{slug}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# O transporte pelo rascunho
# ---------------------------------------------------------------------------


class TestORascunhoTransportaOCarimbo:
    """A metade de baixo: o carimbo entra no rascunho e volta ao ``Profile``."""

    def test_o_rascunho_leva_o_carimbo_de_volta_ao_perfil(self) -> None:
        """Abrir o perfil na janela e emiti-lo de novo não pode perder o carimbo.

        É o caminho que o "Salvar Perfil" percorre inteiro, sem disco: o
        ``from_profile`` do boot, o ``to_profile`` do save.

        MORDIDA: com ``ponte=`` fora do ``Profile(...)`` de ``to_profile``, o
        segundo assert reprova com ``None != PonteConfirmada(...)``.
        """
        perfil = _perfil_do_jogo()
        rascunho = DraftConfig.from_profile(perfil)

        assert rascunho.source_ponte == perfil.ponte, (
            "o rascunho nasceu sem a fotografia do carimbo — nada abaixo dele "
            "tem como preservar o que ele não carrega"
        )
        assert rascunho.to_profile("DontScream").ponte == perfil.ponte

    def test_o_carimbo_nao_atravessa_para_um_nome_novo(self) -> None:
        """Nome NOVO nasce "ainda não sei", e é a resposta honesta.

        O gate é o mesmo R-11 que governa ``match``/``mode``/``priority``: o
        carimbo é REGISTRO de uma confirmação feita NAQUELE perfil. O jogo não
        perde nada — ``manager.perfil_do_appid`` desempata por
        ``(ponte is not None, priority, name)`` e continua achando o original.

        MORDIDA: passthrough incondicional (sem o ``if mesmo_perfil``) e este
        caso reprova — o perfil recém-nascido sai carimbado sem ninguém ter
        confirmado nada nele.
        """
        rascunho = DraftConfig.from_profile(_perfil_do_jogo())

        assert rascunho.to_profile("MadJack").ponte is None

    def test_a_fotografia_do_carimbo_acompanha_o_perfil_gravado(self) -> None:
        """``with_profile_identity`` reaponta o carimbo para o que ficou em disco.

        Depois de gravar com nome novo (que nasce sem carimbo), o rascunho tem
        de dizer "sem carimbo" — senão o save SEGUINTE, já com ``mesmo_perfil``
        verdadeiro, gravaria no perfil novo a confirmação do perfil anterior.

        MORDIDA: sem a chave ``source_ponte`` no ``model_copy`` de
        ``with_profile_identity``, este caso reprova — e o
        ``test_o_segundo_save_do_nome_novo_tambem_nasce_sem_carimbo`` mostra o
        estrago pelo caminho de verdade, com disco.
        """
        rascunho = DraftConfig.from_profile(_perfil_do_jogo())
        recem_gravado = rascunho.to_profile("MadJack")

        assert rascunho.with_profile_identity(recem_gravado).source_ponte is None


class TestOTransporteNaoEEscrita:
    """A ausência de escritor É a entrega, então ela tem portão.

    Sem este caso, a cura de hoje (transportar) e a cura errada (dar às abas um
    campo para carimbar) ficariam indistinguíveis para quem chegar depois — e a
    errada faria o produto jurar que sabe o que não sabe em TODO jogo.
    """

    def test_nenhuma_aba_escreve_o_carimbo_no_rascunho(self) -> None:
        """Nenhum arquivo de ``app/`` escreve ``source_ponte`` num ``model_copy``.

        ``draft_config.py`` fica de fora pelo mesmo motivo do portão de
        cobertura das seções: ele é o LUGAR de guardar (é lá que mora o
        ``with_profile_identity``, que reaponta a fotografia), não a superfície
        que a usuária toca.

        MORDIDA: acrescente ``self.draft.model_copy(update={"source_ponte": x})``
        a qualquer arquivo de ``app/actions/`` e este caso reprova nomeando o
        arquivo.
        """
        culpados: list[str] = []
        for caminho in sorted(_APP.rglob("*.py")):
            if caminho.name == "draft_config.py":
                continue
            arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
            for no in ast.walk(arvore):
                if not isinstance(no, ast.Call):
                    continue
                alvo = no.func
                nome = alvo.attr if isinstance(alvo, ast.Attribute) else ""
                if nome != "model_copy":
                    continue
                for kw in no.keywords:
                    if kw.arg != "update" or not isinstance(kw.value, ast.Dict):
                        continue
                    for chave in kw.value.keys:
                        if (
                            isinstance(chave, ast.Constant)
                            and chave.value == "source_ponte"
                        ):
                            culpados.append(caminho.name)
        assert not culpados, (
            "a janela ganhou um ESCRITOR do carimbo de ponte em "
            f"{sorted(set(culpados))}. O campo é passthrough somente-leitura: "
            "quem carimba é `profiles.manager.confirmar_ponte`, depois de uma "
            "confirmação de verdade. Com escritor, todo save carimbaria como "
            "confirmada uma ponte que ninguém confirmou e a escada pararia em "
            "TODO jogo."
        )

    def test_o_rascunho_nao_tem_metodo_que_carimbe(self) -> None:
        """Nenhum ``with_``/``registrar_`` do ``DraftConfig`` mexe na ponte.

        A varredura acima olha as CHAVES; esta olha os escritores NOMEADOS, que
        são o outro idioma de escrita no rascunho congelado (é a mesma dupla de
        sinais do portão de cobertura das seções). Um só dos dois deixaria a
        porta aberta pela outra grafia.

        MORDIDA: acrescente um ``def with_ponte(self, ...)`` ao ``DraftConfig`` e
        este caso reprova.
        """
        escritores = [
            nome
            for nome in dir(DraftConfig)
            if nome.startswith(("with_", "without_", "registrar_"))
            and "ponte" in nome
        ]
        assert not escritores, (
            f"o rascunho ganhou escritor de carimbo: {escritores}"
        )


# ---------------------------------------------------------------------------
# O rodapé — o gesto banal que apagava tudo
# ---------------------------------------------------------------------------


class TestORodapeNaoApagaOCarimbo:
    def test_salvar_por_cima_do_mesmo_perfil_preserva_o_carimbo(
        self, disco: Path
    ) -> None:
        """O CUSTO MEDIDO do defeito, reproduzido no caminho de verdade.

        Ela está com o jogo aberto, mexe numa cor e clica em "Salvar Perfil"
        com o mesmo nome. Antes da cura, o arquivo voltava do disco sem a chave
        ``ponte``: o jogo caía do painel de pontes confirmadas e a escada
        recomeçava no lançamento seguinte.

        MORDIDA: são duas curas em série aqui (o passthrough do ``to_profile`` e
        o degrau de disco do ``_carimbo_do_save``), e por isso este caso NÃO
        reprova com só uma arrancada. A testemunha isolada do passthrough é
        ``test_o_rascunho_leva_o_carimbo_de_volta_ao_perfil``; a do degrau de
        disco é o caso do perfil vizinho, logo abaixo. Arrancadas as DUAS
        (medido em 22/08/2026: 4 reprovam), este reprova com *"o Salvar do
        rodapé apagou o carimbo"*.
        """
        perfil = _perfil_do_jogo()
        save_profile(perfil)
        janela = _janela_fake(DraftConfig.from_profile(perfil), ativo=perfil.name)

        _salvar_pelo_rodape(janela, "DontScream")

        arquivo = _arquivo(disco, "dontscream")
        assert "ponte" in arquivo, (
            "o Salvar do rodapé apagou o carimbo — o jogo acabou de cair do "
            "`pontes_confirmadas()` e a escada vai recomeçar do primeiro degrau"
        )
        assert arquivo["ponte"] == {
            "kind": "gamepad",
            "gamepad_flavor": "xbox",
            "steam_input": True,
            "confirmada_em": "2026-08-19T21:30:00-03:00",
            "confirmada_por": "silencio",
        }

    def test_salvar_por_cima_de_outro_perfil_nao_apaga_o_carimbo_dele(
        self, disco: Path
    ) -> None:
        """Quem já existe em disco mantém o próprio carimbo.

        O rascunho veio de "Navegacao" (sem carimbo) e ela salva por cima do
        "DontScream", que TEM. O gate ``mesmo_perfil`` do ``to_profile``
        responde ``False`` aqui — é o buraco que o degrau de DISCO do
        ``_carimbo_do_save`` fecha, pelo mesmo argumento medido da
        REGRA-NAO-SE-PERDE-01: carimbo não se perde por um gesto que a tela nem
        sabe nomear.

        MORDIDA: com ``_carimbo_do_save`` devolvendo só o carimbo do rascunho,
        este caso reprova com ``'ponte' not in arquivo``.
        """
        save_profile(_perfil_do_jogo())
        outro = Profile(name="Navegacao", match=MatchManual(), priority=1)
        save_profile(outro)
        janela = _janela_fake(DraftConfig.from_profile(outro), ativo=outro.name)

        _salvar_pelo_rodape(janela, "DontScream")

        arquivo = _arquivo(disco, "dontscream")
        assert "ponte" in arquivo, (
            "salvar por cima de um perfil que TEM carimbo o apagou — e o "
            "rascunho de onde o save veio nunca soube dele"
        )
        assert arquivo["ponte"]["confirmada_por"] == "silencio"

    def test_salvar_com_nome_novo_nasce_sem_carimbo(self, disco: Path) -> None:
        """A janela não fabrica confirmação — nem quando herda a regra do jogo.

        O rodapé herda a REGRA do perfil de origem quando ela não é catch-all
        (REGRA-NAO-SE-PERDE-02), então o perfil novo nasce valendo no mesmo
        jogo. O carimbo NÃO vai junto: ninguém confirmou nada nele.

        MORDIDA: passthrough sem o gate ``mesmo_perfil`` e este caso reprova —
        o arquivo recém-criado sai com a chave ``ponte``.
        """
        perfil = _perfil_do_jogo()
        save_profile(perfil)
        janela = _janela_fake(DraftConfig.from_profile(perfil), ativo=perfil.name)

        _salvar_pelo_rodape(janela, "MadJack")

        arquivo = _arquivo(disco, "madjack")
        assert "ponte" not in arquivo, (
            "um perfil recém-criado nasceu carimbado: o produto passou a jurar "
            "que sabe uma ponte que ninguém confirmou nele"
        )
        assert "ponte" in _arquivo(disco, "dontscream"), (
            "e o perfil de ORIGEM tinha de continuar com o dele — quem sabia, "
            "sabe"
        )

    def test_o_segundo_save_do_nome_novo_tambem_nasce_sem_carimbo(
        self, disco: Path
    ) -> None:
        """A fotografia do rascunho acompanha, senão o carimbo volta pela porta dos fundos.

        Dois "Salvar Perfil" seguidos com o mesmo nome NOVO. No segundo, o
        ``mesmo_perfil`` já responde ``True`` (o rascunho foi reapontado) — e é
        exatamente aí que um ``source_ponte`` velho carimbaria o perfil novo com
        a confirmação do anterior, sem ninguém notar.

        MORDIDA: sem ``"source_ponte": profile.ponte`` no
        ``with_profile_identity``, este caso reprova no segundo save.
        """
        perfil = _perfil_do_jogo()
        save_profile(perfil)
        janela = _janela_fake(DraftConfig.from_profile(perfil), ativo=perfil.name)

        _salvar_pelo_rodape(janela, "MadJack")
        _salvar_pelo_rodape(janela, "MadJack")

        assert "ponte" not in _arquivo(disco, "madjack"), (
            "o segundo save carimbou o perfil novo com a confirmação do perfil "
            "ANTERIOR — a fotografia do rascunho envelheceu"
        )


# ---------------------------------------------------------------------------
# A aba Perfis — o OUTRO botão que grava
# ---------------------------------------------------------------------------


class _FakeEntry:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def get_text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text


class _FakeScale:
    def __init__(self, value: float = 0.0) -> None:
        self._value = float(value)

    def get_value(self) -> float:
        return self._value


class _Editor:
    """Dublê da aba Perfis com o mínimo que ``_build_profile_from_editor`` lê.

    Modo AVANÇADO de propósito: é a página que lê os três campos de regra
    diretamente, sem passar pelo seletor simples — menos widget de mentira
    entre o gesto e a medição.
    """

    def __init__(
        self,
        *,
        nome: str,
        draft: DraftConfig,
        ativo: str,
        cache: list[Profile],
        duplicando: Profile | None = None,
    ) -> None:
        self._widgets: dict[str, Any] = {
            "profile_name_entry": _FakeEntry(nome),
            "profile_priority_scale": _FakeScale(60),
            "profile_window_class_entry": _FakeEntry(_WM_DO_JOGO),
            "profile_title_regex_entry": _FakeEntry(""),
            "profile_process_name_entry": _FakeEntry(""),
        }
        self.draft = draft
        self._active_profile_name = ativo
        self._profiles_cache = list(cache)
        self._mode_advanced = True
        self._mode_kind_selector = None
        self._duplicate_source = duplicando
        self._new_profile = False
        self._alvo_do_salvar = ativo
        self._regra_tocada = False
        self._prioridade_tocada = False
        self._modo_tocado = False
        self._regra_do_disco = None
        self._prioridade_do_disco = None
        self._assinatura_da_regra_ao_abrir = None
        self._prioridade_ao_abrir = None

        self._toasted: list[str] = []

    def _get(self, widget_id: str) -> Any:
        return self._widgets[widget_id]

    def _selected_profile_name(self, selection: Any = None) -> str | None:
        return None

    # --- o que `on_profile_save` chama DEPOIS de gravar -------------------
    # Todos aqui pelo mesmo motivo: falam com o daemon, com a Steam ou com o
    # `Gtk.ListStore`, e nada disso pertence a uma medição sobre o carimbo.
    # O `save_profile` NÃO está entre eles — é ele que a medição lê.

    def _toast_profile(self, msg: str) -> None:
        self._toasted.append(msg)

    def _reload_profiles_store(
        self, select_name: str | None = None, on_done: Any | None = None
    ) -> None:
        self._profiles_cache = list(load_all_profiles())
        if on_done is not None:
            on_done()

    def _reaplicar_e_dizer(
        self, nome: str, renomeando_de: str | None, reaplicar: bool
    ) -> None:
        return None

    def _notify_launch_env_refresh(self) -> None:
        return None

    def pegar_carona_no_gesto(self, gesto: str = "") -> None:
        return None


def _montar_editor(**kwargs: Any) -> Any:
    """``_Editor`` com o mixin de verdade na frente, como a janela compõe."""
    from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin

    class _Aba(_Editor, ProfilesActionsMixin):  # type: ignore[misc]
        pass

    return _Aba(**kwargs)


class TestAAbaPerfisNaoApagaOCarimbo:
    def test_salvar_o_perfil_do_rascunho_pela_aba_preserva_o_carimbo(self) -> None:
        """A aba Perfis grava a partir do rascunho — e apagava o carimbo junto.

        ``_build_profile_from_editor`` usa ``to_profile(ativo)`` como base
        quando o Salvar em curso é o do perfil que o rascunho representa. Sem o
        passthrough, o carimbo morria também por esta porta — a mesma classe de
        defeito, dois botões.

        MORDIDA: com ``ponte=`` fora do ``Profile(...)`` de ``to_profile``, este
        caso reprova com ``None``.
        """
        perfil = _perfil_do_jogo()
        aba = _montar_editor(
            nome="DontScream",
            draft=DraftConfig.from_profile(perfil),
            ativo="DontScream",
            cache=[perfil],
        )

        assert aba._build_profile_from_editor().ponte == perfil.ponte

    def test_duplicar_nao_leva_o_carimbo_para_a_copia(self) -> None:
        """A cópia estreia "ainda não sei" — a MESMA resposta que o nome novo do rodapé.

        O "Duplicar" parte do perfil-fonte (``_duplicate_source``), e o carimbo
        dele vinha junto no ``model_dump`` da base. A cópia sai com a mesma
        regra, mas o gesto seguinte é repontá-la para OUTRO jogo: aí o carimbo
        viajaria, ``pontes_confirmadas()`` publicaria uma ponte que ninguém
        provou naquele appid, e a escada pararia num jogo nunca testado.

        MORDIDA: sem a guarda ``estreia`` de ``_build_profile_from_editor``,
        este caso reprova — a cópia nasce carimbada.
        """
        fonte = _perfil_do_jogo()
        aba = _montar_editor(
            nome="DontScream copia",
            draft=DraftConfig.from_profile(fonte),
            ativo="DontScream",
            cache=[fonte],
            duplicando=fonte,
        )

        copia = aba._build_profile_from_editor()

        assert copia.name == "DontScream copia", "pré-condição: é a cópia"
        assert copia.ponte is None


# ---------------------------------------------------------------------------
# A CORRIDA — o carimbo que chegou DEPOIS da fotografia
# ---------------------------------------------------------------------------


def _salvar_pela_aba(janela: Any) -> None:
    """O gesto dela: aba Perfis, botão "Salvar este perfil".

    `active_profile_name` fala com o daemon por socket; num teste ela só
    atrasaria o caso (o `on_profile_save` já a tem dentro de um `try`).
    """
    with patch(
        "hefesto_dualsense4unix.app.actions.profiles_actions.active_profile_name",
        lambda: None,
    ):
        janela.on_profile_save(None)


class TestOCarimboQueChegouDepoisDaFotografia:
    """PONTE-SOBREVIVE-A-CORRIDA-01 (28/08/2026) — o buraco que a aba Perfis tinha.

    As DUAS memórias que a janela tem do perfil são fotografias, e as duas
    envelhecem pelo mesmo motivo: quem carimba a ponte é OUTRO processo, o
    daemon (``profiles.manager.confirmar_ponte``), e ele escreve direto no
    arquivo.

    - ``draft.source_ponte`` é tirada no ``from_profile`` do boot da janela;
    - ``_profiles_cache`` é recarregado no boot e depois de gravar/apagar —
      nunca por tique, nunca quando o disco muda por fora.

    Então, se ela deixa a janela aberta e o daemon carimba nesse meio-tempo, o
    "Salvar este perfil" seguinte grava ``ponte: null`` por cima do carimbo. Não
    é hipótese: aconteceu DUAS vezes no histórico dela, e o histórico de versões
    do próprio produto guarda as duas.

    - **Sackboy, 26/08/2026** — carimbo nasceu às 03:49:47 (``gamepad``, por
      silêncio) e morreu às 03:54:01. Quatro minutos e catorze segundos: os dois
      snapshots consecutivos são 1238 B **com** ``ponte`` e 1053 B **sem**.
    - **DON'T SCREAM, 19/08/2026** — o mesmo padrão, e esse carimbo era
      ``confirmada_por: escolha_dela``. A escolha DELA, apagada por um clique em
      Salvar.

    O rodapé nunca teve este buraco, e a assimetria é a prova de onde estava o
    defeito: lá o ``existente`` vem de um ``load_all_profiles()`` FRESCO,
    rodado no worker no instante do save (``footer_actions.on_save_profile``),
    e alimenta o degrau 1 de ``carimbo_que_o_save_leva``. A aba Perfis só
    perguntava ao disco quando ``estreia`` — e ``estreia`` é falso justamente no
    gesto mais comum, salvar por cima de si mesmo.

    A régua velha (as classes acima) não alcança nada disso: todas as
    fotografias dela nascem do MESMO perfil que está em disco, então cache,
    rascunho e arquivo concordam e a corrida nunca acontece.
    """

    def test_a_aba_perfis_nao_apaga_o_carimbo_que_o_daemon_pos_depois(
        self, disco: Path
    ) -> None:
        """A corrida encenada nos três tempos, medida onde a decisão é tomada.

        MORDIDA: com a guarda ``if estreia:`` de volta em
        ``profiles_actions._build_profile_from_editor`` (ou seja, sem o degrau
        de disco no caminho comum), este caso reprova com ``None`` — o carimbo
        que o daemon acabou de pôr some do perfil que vai ao disco.
        """
        # Tempo 1 — a janela abriu com o perfil SEM carimbo. As duas memórias
        # dela (a fotografia do rascunho e o cache da lista) nascem daqui.
        sem_carimbo = _perfil_do_jogo(carimbo=False)
        save_profile(sem_carimbo)
        aba = _montar_editor(
            nome="DontScream",
            draft=DraftConfig.from_profile(sem_carimbo),
            ativo="DontScream",
            cache=[sem_carimbo],
        )
        assert aba.draft.source_ponte is None, (
            "pré-condição da corrida: a fotografia do rascunho não tem carimbo"
        )
        alvo = aba._perfil_que_o_salvar_sobrescreve("DontScream")
        assert alvo is not None and alvo.ponte is None, (
            "pré-condição da corrida: o cache em memória também não tem — é o "
            "que impede curar isto lendo o cache"
        )

        # Tempo 2 — o daemon carimba NO DISCO, depois das duas fotografias.
        save_profile(_perfil_do_jogo(carimbo=True))
        assert "ponte" in _arquivo(disco, "dontscream"), (
            "pré-condição da corrida: o disco tem o carimbo"
        )

        # Tempo 3 — ela clica em "Salvar este perfil".
        gravado = aba._build_profile_from_editor()

        assert gravado.ponte is not None, (
            "o Salvar da aba Perfis apagou o carimbo que o daemon pôs no disco "
            "enquanto a janela estava aberta — é a perda do Sackboy de 26/08, "
            "que viveu 4 min 14 s"
        )
        assert gravado.ponte == _carimbo()

    def test_o_gesto_inteiro_da_aba_deixa_o_carimbo_no_arquivo(
        self, disco: Path
    ) -> None:
        """A mesma corrida, do clique até o byte no disco.

        O caso acima mede a DECISÃO (o ``Profile`` montado); este mede o
        ESTRAGO, que é o que ela viu: o arquivo voltando sem a chave ``ponte``.
        Vale a dupla porque entre os dois há um ``save_profile`` que poderia
        (não pode, e por isso está medido) reintroduzir o defeito.

        MORDIDA: idem — com a guarda ``estreia`` de volta, reprova com
        ``'ponte' not in arquivo``.
        """
        sem_carimbo = _perfil_do_jogo(carimbo=False)
        save_profile(sem_carimbo)
        aba = _montar_editor(
            nome="DontScream",
            draft=DraftConfig.from_profile(sem_carimbo),
            ativo="DontScream",
            cache=[sem_carimbo],
        )
        save_profile(_perfil_do_jogo(carimbo=True))

        _salvar_pela_aba(aba)

        arquivo = _arquivo(disco, "dontscream")
        assert "ponte" in arquivo, (
            "o gesto inteiro apagou o carimbo do arquivo — o jogo caiu do "
            "`pontes_confirmadas()` e a escada vai recomeçar do primeiro degrau"
        )
        assert arquivo["ponte"]["confirmada_por"] == "silencio"

    def test_o_disco_vence_a_fotografia_quando_os_dois_tem_carimbo(
        self, disco: Path
    ) -> None:
        """Degrau 1 é o DISCO, e não "o que estiver mais cheio".

        O caso que separa a cura certa da cura preguiçosa (*"se o rascunho não
        tem, olha o disco"*): aqui os DOIS têm carimbo, e são diferentes. Quem
        vale é o do arquivo — é o único que registra uma confirmação de
        verdade, e a fotografia do rascunho pode ser de horas atrás.

        MORDIDA: um degrau invertido (rascunho antes do disco) reprova aqui com
        ``confirmada_por == 'gesto'``.
        """
        antigo = _perfil_do_jogo().model_copy(
            update={
                "ponte": PonteConfirmada(
                    kind="gamepad",
                    gamepad_flavor="dualsense",
                    confirmada_em="2026-08-01T10:00:00-03:00",
                    confirmada_por="gesto",
                )
            }
        )
        save_profile(antigo)
        aba = _montar_editor(
            nome="DontScream",
            draft=DraftConfig.from_profile(antigo),
            ativo="DontScream",
            cache=[antigo],
        )
        save_profile(_perfil_do_jogo(carimbo=True))  # o daemon recarimbou

        gravado = aba._build_profile_from_editor()

        assert gravado.ponte == _carimbo(), (
            "a fotografia do rascunho venceu o disco — o carimbo mais NOVO, "
            "que o daemon acabou de escrever, foi rebaixado por um valor de "
            "quando a janela abriu"
        )

    def test_duplicar_continua_sem_levar_o_carimbo_com_o_disco_carimbado(
        self, disco: Path
    ) -> None:
        """O degrau de disco NÃO pode ressuscitar a herança que a estreia mata.

        A cópia do "Duplicar" nasce sem carimbo (caso acima, com a razão por
        extenso). Se o degrau de disco valesse para ela olhando o perfil-FONTE,
        a herança voltaria pela porta dos fundos. O disco que importa é o do
        SLUG que este Salvar vai sobrescrever — e o da cópia não existe.

        MORDIDA: consultar o disco pelo nome do perfil ATIVO (em vez do nome
        digitado) reprova aqui — a cópia sai carimbada com a ponte da fonte.
        """
        fonte = _perfil_do_jogo()
        save_profile(fonte)
        aba = _montar_editor(
            nome="DontScream copia",
            draft=DraftConfig.from_profile(fonte),
            ativo="DontScream",
            cache=[fonte],
            duplicando=fonte,
        )

        copia = aba._build_profile_from_editor()

        assert copia.name == "DontScream copia", "pré-condição: é a cópia"
        assert copia.ponte is None
