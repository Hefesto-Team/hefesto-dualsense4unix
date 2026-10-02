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

exigir_gi_real("o carimbo de ponte no Salvar Perfil")

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.loader import load_all_profiles
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    PonteConfirmada,
    Profile,
    ProfileModeConfig,
)

_APP = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix" / "app"

_APPID = "2054970"
_WM_DO_JOGO = f"steam_app_{_APPID}"


def _carimbo() -> PonteConfirmada:
    """Um carimbo com valores que NÃO são default nenhum."""
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


@pytest.fixture(autouse=True)
def _sync_run_in_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """``ipc_bridge.run_in_thread`` síncrono — sem loop GTK não há callback."""

    def _sync(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        try:
            resultado = fn()
        except Exception as exc:
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


def _arquivo(disco: Path, slug: str) -> dict[str, Any]:
    return json.loads((disco / f"{slug}.json").read_text(encoding="utf-8"))


class TestORascunhoTransportaOCarimbo:
    """A metade de baixo: o carimbo entra no rascunho e volta ao ``Profile``."""

    def test_o_rascunho_leva_o_carimbo_de_volta_ao_perfil(self) -> None:
        """Abrir o perfil na janela e emiti-lo de novo não pode perder o carimbo."""
        perfil = _perfil_do_jogo()
        rascunho = DraftConfig.from_profile(perfil)

        assert rascunho.source_ponte == perfil.ponte, (
            "o rascunho nasceu sem a fotografia do carimbo — nada abaixo dele "
            "tem como preservar o que ele não carrega"
        )
        assert rascunho.to_profile("DontScream").ponte == perfil.ponte

    def test_o_carimbo_nao_atravessa_para_um_nome_novo(self) -> None:
        """Nome NOVO nasce "ainda não sei", e é a resposta honesta."""
        rascunho = DraftConfig.from_profile(_perfil_do_jogo())

        assert rascunho.to_profile("MadJack").ponte is None


class TestOTransporteNaoEEscrita:
    """A ausência de escritor É a entrega, então ela tem portão."""

    def test_nenhuma_aba_escreve_o_carimbo_no_rascunho(self) -> None:
        """Nenhum arquivo de ``app/`` escreve ``source_ponte`` num ``model_copy``."""
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
        """Nenhum ``with_``/``registrar_`` do ``DraftConfig`` mexe na ponte."""
        escritores = [
            nome
            for nome in dir(DraftConfig)
            if nome.startswith(("with_", "without_", "registrar_"))
            and "ponte" in nome
        ]
        assert not escritores, (
            f"o rascunho ganhou escritor de carimbo: {escritores}"
        )


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


