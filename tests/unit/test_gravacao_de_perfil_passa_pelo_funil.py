"""GRAVA-POR-UM-FUNIL-01 — o rodapé grava e o rascunho não fica sabendo (04/08).

O DEFEITO, medido antes de qualquer linha de código: o ``_on_saved`` do
``footer_actions.py`` atualizava ``_active_profile_name`` e ``_draft_baseline``
e NUNCA reapontava ``self.draft``. Como o ``to_profile`` decide pela fotografia
que o rascunho guarda do perfil de origem (os ``source_*``), o gate
``mesmo_perfil`` passava a responder ``False`` para sempre depois do primeiro
"Salvar Perfil" com nome novo — e todo save seguinte gravava ``MatchAny()`` com
prioridade ``max(catch-all) + 10``. A catraca medida no rodapé:

    1º "Salvar Perfil" como "MadJack" -> prioridade 10
    2º "Salvar Perfil" como "MadJack" -> prioridade 20
    3º                                -> prioridade 30

Cada gesto de preservar o trabalho dela empurrava o perfil um degrau para cima,
até passar por cima das regras de jogo. É a queixa crônica ("a config que eu
deixo nunca é respeitada") entrando por uma porta nova.

A cura tinha nome e endereço desde a ABAS-01 (25/07):
``DraftConfig.with_profile_identity``, cuja própria docstring descreve o
caminho do rodapé como o defeito que ele cura — e que tinha UM único chamador
em produção, a aba Perfis. Lembrar de chamar não é engenharia. Por isso a
gravação virou um FUNIL só (``app/actions/profile_writer.py``), e este módulo
guarda as duas coisas:

- os testes que MORDEM o comportamento (a catraca, o rascunho reapontado, a
  regra do perfil importado que sobrevive ao save seguinte);
- o PORTÃO que impede a recaída: nenhum ``save_profile(`` novo dentro de
  ``app/`` fora do funil. Quem escrever o quinto botão não precisa lembrar de
  nada — não consegue gravar por fora.

São DUAS curas, e cada uma tem a sua testemunha — anotado porque elas se
cobrem em parte, e quem arrancar só uma pode achar que a outra é enfeite:

- reapontar o rascunho (``with_profile_identity`` no funil). Arrancada, três
  testes de comportamento reprovam por conta própria
  (``test_salvar_com_nome_novo_reaponta_o_rascunho``,
  ``test_os_source_batem_com_o_perfil_gravado`` e
  ``test_importar_por_cima_do_perfil_ativo_atualiza_a_fotografia``) e outros
  quatro reprovam pelo assert de invariante do funil — sete no total, medido;
- herdar a prioridade de quem já existe em disco (``_prioridade_do_save``).
  Arrancada, ``test_salvar_por_cima_de_perfil_que_ja_existe_herda_a_prioridade``
  reprova com ``10 != 50``.

Arrancando AS DUAS, ``test_a_prioridade_e_a_regra_do_primeiro_save_sobrevivem``
reprova com a frase que dá nome à sprint: *"o segundo save subiu a prioridade
para 20"* — o estado histórico do disco dela, reproduzido. Tudo devolvido:
verdes.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira no CI
# headless, em vez de pular.
exigir_gi_real("funil de gravação de perfil")

import ast
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.loader import load_all_profiles
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
)

#: Raiz do pacote, para o portão e para os testes que leem o fonte.
_SRC = Path(__file__).resolve().parents[2] / "src"
_APP = _SRC / "hefesto_dualsense4unix" / "app"

#: A folga do cálculo de prioridade (`profiles_actions._FOLGA_ACIMA_DO_CATCH_ALL`)
#: repetida aqui de propósito: os números 10 e 20 desta suíte são os MEDIDOS no
#: rodapé, e importar a constante deixaria o teste concordar com o código mesmo
#: se a folga mudasse — que é justamente quando alguém precisa reler a sprint.
_PRIORIDADE_DO_PRIMEIRO_SAVE = 10
_PRIORIDADE_DA_CATRACA = 20


# ---------------------------------------------------------------------------
# Aparelhagem
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _sync_run_in_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """Roda ``ipc_bridge.run_in_thread`` de forma síncrona (sem loop GTK).

    PERF-FOOTER-ASYNC-IO-01 pôs o I/O de disco num worker; sem um loop GTK nos
    testes, os callbacks nunca executariam. Worker e callback na mesma thread
    preservam a semântica observável.
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

    O cálculo da prioridade mora na aba Perfis e o gesto mora no rodapé — são
    irmãos na MRO do aplicativo, e testar o rodapé sem o irmão mediria uma
    composição que não existe (o rodapé cairia no piso de fallback e a catraca
    não apareceria).
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
            self._avisos_ao_daemon = 0
            builder = MagicMock()
            builder.get_object.return_value = MagicMock()
            self.builder = builder

        def _reload_profiles_store(
            self, select_name: str | None = None, on_done: Any | None = None
        ) -> None:
            # A lista real relê o disco num worker; aqui basta o efeito que o
            # cálculo de prioridade enxerga — o cache em memória.
            self._profiles_cache = list(load_all_profiles())
            if on_done is not None:
                on_done()

        def _footer_toast(self, msg: str, context: str = "footer") -> None:
            self._toasted.append(msg)

        def _toast_profile(self, msg: str) -> None:
            self._toasted.append(msg)

        def _notify_launch_env_refresh(self) -> None:
            self._avisos_ao_daemon += 1

    return _Janela()


def _perfil_do_jogo(nome: str = "Pragmata") -> Profile:
    """Perfil com REGRA de janela e prioridade alta — o que ela tem em disco."""
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=["steam_app_3357650"]),
        priority=60,
        leds=LedsConfig(lightbar=(97, 53, 131)),
    )


def _salvar_pelo_rodape(janela: Any, nome: str) -> None:
    """O gesto dela: botão "Salvar Perfil", digita ``nome``, confirma."""
    dialogos = MagicMock()
    dialogos.prompt_profile_name.return_value = nome
    dialogos.prompt_overwrite_existing.return_value = True
    with patch(
        "hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", dialogos
    ):
        janela.on_save_profile()


def _perfil_em_disco(disco: Path, slug: str) -> dict[str, Any]:
    return json.loads((disco / f"{slug}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# A catraca: dois saves seguidos com o MESMO nome
# ---------------------------------------------------------------------------


class TestDoisSavesSeguidos:
    """O segundo "Salvar Perfil" não pode reescrever o perfil do primeiro.

    MORDIDA: com as DUAS curas arrancadas, o segundo save vê o ``source_name``
    do perfil ANTERIOR, cai no ramo "nome novo" do ``to_profile`` e grava
    ``MatchAny()`` com prioridade 20 — os números medidos e escritos no topo
    deste módulo. É o cenário histórico inteiro, e é por isso que esta classe
    existe mesmo com testemunhas mais específicas ao lado: ela guarda o que a
    usuária VIU, não a peça de código que o produzia.
    """

    def test_a_prioridade_e_a_regra_do_primeiro_save_sobrevivem(
        self, disco: Path
    ) -> None:
        """Dois "Salvar Perfil" seguidos com o mesmo nome, o gesto medido.

        O que o segundo save tem de fazer é REEMITIR o que está em disco, não
        recalcular tudo do zero — é isso que as duas asserções de prioridade e
        a de ``match`` medem aqui.

        NOTA DATADA — 05/08/2026: este parágrafo dizia *"o perfil nasce
        ``MatchAny`` no primeiro save de propósito"*, o que valeu de 23/07 a
        05/08 e caducou com a REGRA-NAO-SE-PERDE-02. Hoje o primeiro save
        herda a regra do perfil de origem (aqui, ``steam_app_3357650``), e o
        teste segue medindo a MESMA coisa que sempre mediu: o segundo save não
        pode mexer no que o primeiro gravou.
        """
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "MadJack")
        primeiro = _perfil_em_disco(disco, "madjack")

        _salvar_pelo_rodape(janela, "MadJack")
        segundo = _perfil_em_disco(disco, "madjack")

        assert primeiro["priority"] == _PRIORIDADE_DO_PRIMEIRO_SAVE, (
            "o perfil novo tem de nascer acima dos catch-all dela "
            "(PERFIL-NASCE-CERTO-01)"
        )
        assert segundo["priority"] == _PRIORIDADE_DO_PRIMEIRO_SAVE, (
            f"o segundo save subiu a prioridade para {segundo['priority']} — a "
            f"catraca medida ({_PRIORIDADE_DA_CATRACA}) está de volta e o "
            "perfil dela caminha para atropelar as regras de jogo"
        )
        assert segundo["priority"] != _PRIORIDADE_DA_CATRACA
        assert segundo["match"] == primeiro["match"]

    def test_a_configuracao_dela_continua_indo_junto(self, disco: Path) -> None:
        """A guarda não pode virar "o segundo save não grava nada"."""
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "MadJack")
        # O gesto da aba Lightbar entre um save e o outro.
        novos_leds = janela.draft.leds.model_copy(update={"lightbar_rgb": (10, 20, 30)})
        janela.draft = janela.draft.model_copy(update={"leds": novos_leds})
        _salvar_pelo_rodape(janela, "MadJack")

        assert _perfil_em_disco(disco, "madjack")["leds"]["lightbar"] == [10, 20, 30]


# ---------------------------------------------------------------------------
# A invariante: depois de gravar, o rascunho descreve o DISCO
# ---------------------------------------------------------------------------


class TestRascunhoApontaParaODisco:
    def test_salvar_com_nome_novo_reaponta_o_rascunho(self, disco: Path) -> None:
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "MadJack")

        assert janela.draft.source_name == "MadJack", (
            "o rascunho continuou apontando para o perfil anterior — o gate "
            "`mesmo_perfil` do `to_profile` responderá False para sempre"
        )
        assert janela._active_profile_name == "MadJack"
        assert janela._draft_baseline is janela.draft

    def test_os_source_batem_com_o_perfil_gravado(self, disco: Path) -> None:
        """A invariante inteira, campo a campo, e não só o nome."""
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "MadJack")
        gravado = Profile.model_validate(_perfil_em_disco(disco, "madjack"))

        assert janela.draft.source_name == gravado.name
        assert janela.draft.source_priority == gravado.priority
        assert janela.draft.source_match == gravado.match
        assert janela.draft.source_mode == gravado.mode
        assert janela.draft.source_suppress == gravado.suppress_desktop_emulation

    def test_salvar_por_cima_de_perfil_que_ja_existe_herda_a_prioridade(
        self, disco: Path
    ) -> None:
        """Prioridade é CALCULADA só para quem não existe em disco.

        Ela edita a cor com o "Pragmata" ativo e salva por cima da "Navegação"
        (prioridade 50, com regra de janela). Recalcular ali dava um número
        novo ao perfil DELA — o mesmo dente da catraca, por outra porta.
        """
        from hefesto_dualsense4unix.profiles.loader import save_profile

        save_profile(
            Profile(
                name="Navegação",
                match=MatchCriteria(window_class=["firefox"]),
                priority=50,
            )
        )
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "Navegação")

        assert _perfil_em_disco(disco, "navegacao")["priority"] == 50

    def test_salvar_por_cima_de_perfil_que_ja_existe_herda_a_regra(
        self, disco: Path
    ) -> None:
        """REGRA-NAO-SE-PERDE-01 — o caso REAL dela, de 05/08/2026.

        O ``sackboy_nativo`` dela tinha a regra ``steam_app_1599660``, e virou
        ``{"type": "any"}`` no meio da sessão de jogo. A consequência não é
        estética: a chave de seleção é ``(não é catch-all, prioridade)``, então
        **catch-all perde para qualquer regra** — o perfil do Sackboy passou a
        perder DENTRO do Sackboy (para o ``coop_local``, prioridade 75) e a
        ganhar em todo o resto do desktop, carregando
        ``suppress_desktop_emulation``. Foi por isso que subir a prioridade
        dele para 191 não resolveu nada.

        O que este teste mede é o degrau 1 da escada de ``_regra_do_save``: o
        DISCO vence a fotografia do rascunho. Regra não se perde por um gesto
        que a tela nem sabe nomear.

        NOTA DATADA — 05/08/2026: este parágrafo dizia que *"a decisão de que
        nome NOVO nasce ``MatchAny()`` continua de pé"*. Ela caiu no mesmo dia
        (REGRA-NAO-SE-PERDE-02): nome novo passou a herdar a regra da origem, e
        o órfão nasce ``MatchManual()``. O teste não muda — o cenário dele é
        justamente aquele em que os DOIS lados têm regra, e a do disco é a que
        tem de vencer, senão a cura de cima vira defeito novo.

        MORDIDA: apague o ``model_copy(update={"match": ...})`` de
        ``_persist_profile_async`` e este teste fica vermelho com ``any``.
        """
        from hefesto_dualsense4unix.profiles.loader import save_profile

        save_profile(
            Profile(
                name="sackboy_nativo",
                match=MatchCriteria(window_class=["steam_app_1599660"]),
                priority=80,
            )
        )
        # O rascunho veio de OUTRO perfil — é o estado normal de quem estava
        # mexendo nas abas e resolveu guardar por cima do perfil do jogo.
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "sackboy_nativo")

        gravado = _perfil_em_disco(disco, "sackboy_nativo")
        assert gravado["match"]["type"] == "criteria", (
            "o rodapé apagou a regra de um perfil que JÁ EXISTIA — é o defeito "
            "que tirou o perfil do jogo dela de dentro do próprio jogo"
        )
        assert gravado["match"]["window_class"] == ["steam_app_1599660"]

    def test_perfil_novo_pelo_rodape_herda_a_regra_da_origem(
        self, disco: Path
    ) -> None:
        """Nome NOVO herda a regra do perfil de ORIGEM — e nunca nasce catch-all.

        NOTA DATADA — este teste ocupava o lugar de
        ``test_perfil_novo_pelo_rodape_continua_nascendo_sempre``, testemunha
        da frase oposta (*"nome novo nasce ``MatchAny()``"*), que valeu de
        **23/07 a 05/08/2026**. A premissa caducou por medição, não por gosto:
        REGRA-NAO-SE-PERDE-02 mostrou que ``MatchAny`` não é neutro. Catch-all
        perde para qualquer regra na chave de seleção, dispara o veto R-21
        dentro de janela ``steam_app_*`` — logo o perfil recém-salvo NUNCA
        ativa no jogo — e ainda assim nasce com ``max(catch-all) + folga`` e
        ganha o desktop inteiro. O perfil não nascia "sempre": nascia no lugar
        errado, que é a forma do ``sackboy_nativo`` de 05/08.

        O que continua de pé é a razão da decisão antiga: um perfil novo não
        pode nascer com a regra ERRADA. Ele não nasce — a regra herdada é a do
        perfil que ela estava editando, e o ramo sem origem nenhuma vai para
        ``MatchManual()``, não para o catch-all. A escada inteira está em
        ``footer_actions._regra_do_save`` e nas testemunhas de
        ``test_regra_nao_se_perde_02_o_nome_novo_nascia_sem_regra.py``.

        MORDIDA: devolva o degrau 3 para ``MatchAny()`` (ou apague o degrau 2)
        e este teste reprova com ``any``.
        """
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        _salvar_pelo_rodape(janela, "um_nome_que_nao_existe")

        gravado = _perfil_em_disco(disco, "um_nome_que_nao_existe")
        assert gravado["match"]["type"] == "criteria", (
            "o perfil novo nasceu catch-all — é o que o tira de dentro do jogo "
            "dela e o põe por cima do desktop inteiro"
        )
        assert gravado["match"]["window_class"] == ["steam_app_3357650"]
        assert Profile.model_validate(gravado).e_catch_all is False


# ---------------------------------------------------------------------------
# Os outros dois botões que gravam passam pelo mesmo funil
# ---------------------------------------------------------------------------


class TestImportarERestaurar:
    def test_importar_por_cima_do_perfil_ativo_atualiza_a_fotografia(
        self, disco: Path
    ) -> None:
        """O import muda o disco debaixo do rascunho — e ele tem de saber.

        MORDIDA de verdade no ``match``: ela importa um "Pragmata" com a regra
        do jogo por cima do "Pragmata" catch-all que está ativo e, em seguida,
        salva pelo rodapé. Sem o funil reapontar o rascunho, o "Salvar Perfil"
        seguinte reemite a fotografia VELHA e a regra recém-importada morre.
        """
        from hefesto_dualsense4unix.profiles.loader import save_profile

        ativo = Profile(name="Pragmata", match=MatchAny(), priority=5)
        save_profile(ativo)
        janela = _janela_fake(DraftConfig.from_profile(ativo), "Pragmata")

        # O ``on_import_profile`` inteiro exige o FileChooser do GTK (janela de
        # verdade); a gravação do importado — que é o que este teste mede —
        # começa aqui, no mesmo ponto em que o diálogo a entrega.
        janela._import_save_async(_perfil_do_jogo())

        assert janela.draft.source_match == _perfil_do_jogo().match, (
            "o rascunho ficou com a fotografia anterior ao import"
        )

        _salvar_pelo_rodape(janela, "Pragmata")
        salvo = _perfil_em_disco(disco, "pragmata")
        assert salvo["match"]["window_class"] == ["steam_app_3357650"], (
            "o save seguinte apagou a regra que ela acabou de importar"
        )
        assert salvo["priority"] == 60

    def test_importar_outro_perfil_nao_rouba_o_rascunho(self, disco: Path) -> None:
        """Importar um arquivo NÃO é dizer "passei a editar este perfil"."""
        ativo = _perfil_do_jogo("Pragmata")
        janela = _janela_fake(DraftConfig.from_profile(ativo), "Pragmata")

        janela._import_save_async(Profile(name="Corrida", match=MatchAny(), priority=7))

        assert janela.draft.source_name == "Pragmata"
        assert janela._active_profile_name == "Pragmata"

    def test_restaurar_padrao_deixa_o_rascunho_no_meu_perfil(
        self, disco: Path
    ) -> None:
        """R-08/C9: rascunho e NOME trocam como unidade, também no restauro."""
        asset = footer_actions._meu_perfil_asset()
        if asset is None:
            pytest.skip("preset meu_perfil.json ausente em todos os candidatos")
        janela = _janela_fake(DraftConfig.from_profile(_perfil_do_jogo()), "Pragmata")

        dialogos = MagicMock()
        dialogos.confirm_restore_default.return_value = True
        with patch(
            "hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", dialogos
        ):
            janela.on_restore_default()

        assert janela._active_profile_name == "meu_perfil"
        assert janela.draft.source_name == "meu_perfil"


# ---------------------------------------------------------------------------
# O PORTÃO: ninguém grava perfil na janela fora do funil
# ---------------------------------------------------------------------------

#: Módulos de ``app/`` autorizados a chamar ``save_profile``.
#:
#: ``actions/profile_writer.py`` é o funil. ``actions/profiles_actions.py`` é a
#: EXCEÇÃO datada (04/08/2026): a aba Perfis grava dentro de uma transação
#: própria — confirma sobrescrita, apaga o perfil antigo no rename, migra o
#: marker de ativo no daemon — e cumpre a invariante por conta própria, pelo
#: ``_reconciliar_rascunho_com_perfil_salvo``. Convertê-la é trabalho de outra
#: leva. Esta lista só pode ENCOLHER: o teste abaixo trava o conteúdo dela.
_AUTORIZADOS_A_GRAVAR = {
    "actions/profile_writer.py",
    "actions/profiles_actions.py",
}


def _chamadas_a_save_profile(caminho: Path) -> list[int]:
    """Linhas em que ``caminho`` CHAMA ``save_profile`` (AST, não texto).

    Por AST porque texto acusaria o import, a docstring e o nome do parâmetro —
    e portão com falso positivo em massa vira portão desligado.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    linhas: list[int] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        if isinstance(alvo, ast.Name):
            nome = alvo.id
        elif isinstance(alvo, ast.Attribute):
            nome = alvo.attr
        else:
            continue
        if nome == "save_profile":
            linhas.append(no.lineno)
    return linhas


def test_nenhuma_gravacao_de_perfil_fora_do_funil() -> None:
    """O pedido central da mantenedora, em forma de portão.

    Quem escrever o quinto botão do rodapé não precisa lembrar de reapontar o
    rascunho — não consegue gravar por fora. Se este teste reprovar, a resposta
    NÃO é acrescentar o arquivo à lista: é chamar ``_gravar_perfil_async``.
    """
    ofensores: dict[str, list[int]] = {}
    for caminho in sorted(_APP.rglob("*.py")):
        relativo = caminho.relative_to(_APP).as_posix()
        if relativo in _AUTORIZADOS_A_GRAVAR:
            continue
        linhas = _chamadas_a_save_profile(caminho)
        if linhas:
            ofensores[relativo] = linhas

    assert ofensores == {}, (
        "gravação de perfil fora do funil (GRAVA-POR-UM-FUNIL-01): "
        f"{ofensores} — use `self._gravar_perfil_async(...)` de "
        "`app/actions/profile_writer.py`, que grava E reaponta o rascunho"
    )


def test_a_lista_de_autorizados_nao_cresce_em_silencio() -> None:
    """A exceção da aba Perfis é datada; a lista só pode encolher.

    Sem esta trava, o portão acima se dissolveria por acréscimo — bastaria
    escrever o nome do arquivo novo na lista para gravar por fora de novo.
    """
    assert sorted(_AUTORIZADOS_A_GRAVAR) == [
        "actions/profile_writer.py",
        "actions/profiles_actions.py",
    ]


def test_quem_esta_autorizado_cumpre_a_invariante_por_conta_propria() -> None:
    """Autorizado a gravar não é autorizado a esquecer o rascunho.

    Quem grava fora do funil tem de reapontar o rascunho pelo mesmo método —
    ``with_profile_identity``. Se a aba Perfis perder a chamada dela, o defeito
    volta por ali com o mesmo formato.
    """
    for relativo in sorted(_AUTORIZADOS_A_GRAVAR):
        texto = (_APP / relativo).read_text(encoding="utf-8")
        assert "with_profile_identity" in texto, (
            f"{relativo} grava perfil e não reaponta o rascunho — a fotografia "
            "dos `source_*` envelhece e o `to_profile` volta a zerar regra e "
            "prioridade a cada save"
        )


def test_o_funil_carimba_a_origem_da_gravacao() -> None:
    """Toda gravação da janela diz de ONDE veio, no journal.

    A lacuna que isto fecha custou uma madrugada inteira: em 05/08 o disco dela
    tinha `sackboy_nativo` com prioridade 191, e não havia como decidir entre
    duas explicações igualmente plausíveis — a catraca do rodapé (`191 = 1 +
    10x19`, dezenove saves) ou o controle deslizante da aba Perfis, cuja faixa
    é 0-200. Cinco agentes leram código e journal e **nenhum** conseguiu
    provar, porque o produto não registrava gravação de perfil.

    `save_profile(..., origem=)` (loader.py:787) carimba o `profile_salvo` com
    `match_antes`/`match_depois` e `priority_antes`/`priority_depois`. Sem a
    `origem`, o campo cai no basename do processo — que para toda a janela é o
    mesmo, e a pergunta "qual botão fez isto?" continua sem resposta.

    MORDIDA: apague o `origem=` da chamada em `profile_writer.py` e este teste
    fica vermelho.
    """
    texto = (_APP / "actions/profile_writer.py").read_text(encoding="utf-8")
    assert "save_profile(profile, origem=" in texto, (
        "o funil grava sem dizer de onde veio — o `profile_salvo` do journal "
        "perde o único campo que distingue um botão do outro"
    )
    assert "janela:" in texto, (
        "a origem precisa identificar a JANELA, não só o processo: o basename "
        "do argv[0] é igual para todos os botões"
    )
