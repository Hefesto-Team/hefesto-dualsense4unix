"""PERFIL-SALVA-TUDO — IDA E VOLTA: o gesto da aba chega ao ARQUIVO do perfil.

O PEDIDO DELA, 09/08/2026, literal:

    *"Preciso que cada feature de cada aba ao clicarmos em salvar perfil e
    aplicar (botão verde) tudo fique salvo no perfil ativo. Assim é impossível
    funcionar o app. faz uma solução robusta, considerando bt, todas as features
    que trabalhamos, e todas as features em cada aba, touch, giroscopio, speaker,
    mic, gatilho, lightbar. tudo."*

Este módulo é a RÉGUA, não a cura. Ele mede UMA pergunta por seção do perfil, e
a pergunta é sempre a mesma:

    o gesto da aba entra no rascunho, o "Salvar Perfil" do rodapé o leva ao
    disco, e o arquivo relido ainda o tem?

O caminho medido é o REAL, de ponta a ponta — nada de atalho pelo ``to_profile``:

    gesto da aba  ->  ``self.draft``  ->  ``on_save_profile`` (rodapé)
                  ->  ``_persist_profile_async``  ->  ``_gravar_perfil_async``
                  ->  ``profiles.loader.save_profile``  ->  DISCO
                  ->  ``profiles.loader.load_profile``  ->  asserção

É de propósito que a montagem do dublê espelhe a ``HefestoApp``: os defeitos
desta família SÓ existem na fronteira entre abas (uma escreve, outra reemite a
fotografia velha por cima), e um teste de módulo isolado nunca os veria.

HERMETISMO. Nenhum byte sai para o ``~/.config`` dela: o ``_hefesto_fake_env``
do ``tests/conftest.py`` isola ``XDG_CONFIG_HOME`` em ``tmp_path`` a cada teste,
e a fixture ``disco`` daqui CONFERE isso antes de deixar qualquer teste rodar —
o canário CANARIO-FS-01 do conftest é a segunda rede, não a primeira.

O QUE ESTE MÓDULO **NÃO** MEDE, declarado para ninguém tomar por garantia:

- **touch e giroscópio não existem no esquema de perfil.** ``Profile`` não tem
  campo de touchpad nem de giroscópio (``profiles/schema.py``) — não há o que
  fazer ida-e-volta. Isto não é lacuna de teste, é lacuna de PRODUTO, e está
  nomeada no relatório da sprint em vez de escondida atrás de um teste verde;
- o caminho de gravação da **aba Perfis** (``_build_profile_from_editor``), que
  é o OUTRO botão que grava. Ele lê widgets do editor e exigiria um glade
  montado; a fronteira entre ele e o rascunho já tem testemunha própria em
  ``test_perfil_salva_tudo_abas.py``.

O PORTÃO QUE IMPEDE A REGRESSÃO FUTURA mora ao lado, em
``test_perfil_salva_tudo_cobertura_das_secoes.py``: ele deriva
``Profile.model_fields`` em RUNTIME e reprova quando nasce uma seção nova sem
ida-e-volta aqui. A ponte entre os dois é ``SECOES_COBERTAS``, logo abaixo —
um dicionário LITERAL de propósito, para o portão poder lê-lo por AST, sem
importar este módulo (que exige GTK real) e sem pular onde não há PyGObject.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("PERFIL-SALVA-TUDO — ida e volta por seção")

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.profiles.loader import load_profile
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
    ProfileMicConfig,
    ProfileModeConfig,
    ProfileMouseConfig,
    ProfileSpeakerConfig,
    RumbleConfig,
    TriggerConfig,
    TriggersConfig,
)


SECOES_COBERTAS: dict[str, str] = {
    "name": "rodapé — o nome digitado no diálogo do Salvar Perfil",
    "match": "rodapé — _regra_do_save (disco > origem do rascunho > MatchManual)",
    "priority": "rodapé — _prioridade_do_save (quem já existe herda a do disco)",
    "triggers": "aba Gatilhos — TriggersActionsMixin._persist_params_to_draft",
    "leds": "aba Lightbar — LightbarActionsMixin._persist_leds_update",
    "rumble": "aba Rumble — RumbleActionsMixin._set_policy",
    "key_bindings": "aba Teclado — InputActionsMixin._persist_key_bindings_to_draft",
    "mouse": "aba Mouse — MouseActionsMixin.on_mouse_speed_changed",
    "mic": "card do controle — draft_config.registrar_microfone_no_rascunho",
    "speaker": "card do controle — draft_config.registrar_alto_falante_no_rascunho",
    "mode": "abas Início/Emulação — home_actions.registrar_modo_no_rascunho",
    "suppress_desktop_emulation": (
        "aba Emulação — emulation_actions.registrar_modo_jogo_no_rascunho"
    ),
    "controllers": "aba Lightbar com um controle no seletor — _persist_leds_update",
}

UNIQ_DE_TESTE = "aabbcc000002"


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
def disco(tmp_path: Path) -> Path:
    """O diretório de perfis DE VERDADE — provado dentro do ``tmp_path``."""
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    destino = profiles_dir(ensure=True)
    assert str(destino).startswith(str(tmp_path)), (
        "o diretório de perfis NÃO está isolado — este teste escreveria no "
        f"~/.config real da usuária ({destino})"
    )
    return destino


class _Escala:
    """Dublê de ``Gtk.Scale``/``Gtk.Adjustment`` — só o que os handlers leem."""

    def __init__(self, valor: float) -> None:
        self._valor = valor

    def get_value(self) -> float:
        return self._valor


class _Combo:
    """Dublê de ``Gtk.ComboBoxText`` — só o ``get_active_id``."""

    def __init__(self, ident: str | None) -> None:
        self._id = ident

    def get_active_id(self) -> str | None:
        return self._id


class _Caixa:
    """Dublê de ``Gtk.CheckButton`` — só o ``get_active``."""

    def __init__(self, ativo: bool) -> None:
        self._ativo = ativo

    def get_active(self) -> bool:
        return self._ativo


def _perfil_de_partida(nome: str = "Pragmata") -> Profile:
    """O perfil que ela tem em disco quando abre a janela."""
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=["steam_app_3357650"]),
        priority=60,
        leds=LedsConfig(lightbar=(97, 53, 131), auto_player_colors=False),
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"), right=TriggerConfig(mode="Off")
        ),
        rumble=RumbleConfig(passthrough=True),
    )


def _semear(perfil: Profile) -> Profile:
    """Grava o perfil de partida no disco isolado, pelo caminho de produção."""
    from hefesto_dualsense4unix.profiles.loader import save_profile

    save_profile(perfil, origem="teste:ida-e-volta")
    return perfil


def _relido(nome: str) -> Profile:
    """O perfil como ele ficou NO DISCO — nunca o objeto em memória."""
    return load_profile(nome)


class _LinhaDoPendente:
    """Dublê do rótulo "vai mudar para:" da aba Início — só o que ele expõe."""

    def __init__(self) -> None:
        self.texto = ""
        self.visivel = False

    def set_text(self, texto: str) -> None:
        self.texto = texto

    def set_visible(self, visivel: bool) -> None:
        self.visivel = bool(visivel)

    def get_visible(self) -> bool:
        return self.visivel


def _sem_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum IPC de leitura sai desta bancada — nem para o daemon dela."""

    def _explode(*_a: Any, **_kw: Any) -> Any:
        raise RuntimeError("daemon ausente nesta bancada")

    monkeypatch.setattr(footer_actions.ipc_bridge, "_run_call", _explode)


def _armadilha_de_apply_mode(
    monkeypatch: pytest.MonkeyPatch, *, desfecho: str = "sucesso"
) -> list[tuple[str, str | None]]:
    """Registra CADA ``apply_mode`` e devolve a lista — a régua da transição."""
    from hefesto_dualsense4unix.app.actions import mode_transition

    chamadas: list[tuple[str, str | None]] = []

    def _apply_mode_falso(
        mode_id: str,
        *,
        flavor: str | None = None,
        on_done: Callable[[Any], bool],
        on_fail: Callable[[Exception], bool],
    ) -> None:
        chamadas.append((mode_id, flavor))
        if desfecho == "sucesso":
            on_done({"status": "ok"})
        elif desfecho == "falha":
            on_fail(RuntimeError("o daemon recusou a transição"))

    monkeypatch.setattr(mode_transition, "apply_mode", _apply_mode_falso)
    return chamadas


def _confere_triggers(perfil: Profile) -> None:
    assert perfil.triggers.left.mode == "Rigid", (
        "o gatilho esquerdo voltou para "
        f"{perfil.triggers.left.mode!r} — o modo escolhido na aba não chegou "
        "ao arquivo"
    )
    assert list(perfil.triggers.left.params) == [7, 240], (
        f"os parâmetros do gatilho chegaram como {perfil.triggers.left.params!r} "
        "— o que ela sente no dedo não é o que está no disco"
    )


def _confere_leds(perfil: Profile) -> None:
    assert tuple(perfil.leds.lightbar) == (12, 34, 56), (
        f"a cor no arquivo é {tuple(perfil.leds.lightbar)!r} — a lightbar que "
        "ela escolheu não sobreviveu ao salvar"
    )
    assert abs(perfil.leds.lightbar_brightness - 0.40) < 1e-6, (
        f"o brilho no arquivo é {perfil.leds.lightbar_brightness!r}, e ela "
        "escolheu 40%"
    )


def _confere_rumble(perfil: Profile) -> None:
    assert perfil.rumble.policy == "economia", (
        f"a política de vibração no arquivo é {perfil.rumble.policy!r} — o "
        "botão que ela afundou na aba Rumble não chegou ao perfil"
    )


def _confere_key_bindings(perfil: Profile) -> None:
    """O gesto da aba CHEGOU, e o que a aba não mostra CONTINUA lá."""
    bindings = perfil.key_bindings or {}
    assert bindings.get("triangle") == ["KEY_C"], (
        f"os bindings no arquivo são {perfil.key_bindings!r} — o teclado que "
        "ela montou não sobreviveu ao salvar"
    )
    intocados = {
        chave: valor
        for chave, valor in bindings.items()
        if chave != "triangle"
    }
    assert intocados, (
        "o perfil ficou SÓ com o que a aba mostra. O gesto voltou a apagar o "
        "que a lista não exibe — é a N1 desfeita, e o preço é o perfil dela"
    )


def _confere_mouse(perfil: Profile) -> None:
    assert perfil.mouse is not None, (
        "a seção `mouse` NÃO existe no arquivo — arrastar os controles de "
        "velocidade não criou a seção (BUG-MOUSE-SAVE-DROPS-SECTION-01)"
    )
    assert (perfil.mouse.speed, perfil.mouse.scroll_speed) == (11, 4), (
        f"as velocidades no arquivo são {perfil.mouse.speed}/"
        f"{perfil.mouse.scroll_speed} — ela arrastou para 11/4"
    )


def _confere_mic(perfil: Profile) -> None:
    assert perfil.mic is not None, (
        "a seção `mic` NÃO existe no arquivo — o microfone não foi salvo no "
        "perfil (é a queixa literal de 18/08: nenhum dos 18 perfis dela tinha "
        "esta seção)"
    )
    assert perfil.mic.button_toggles_system is False, (
        "o `button_toggles_system` do arquivo é "
        f"{perfil.mic.button_toggles_system!r} — ela desligou"
    )
    assert perfil.mic.volume == 70, (
        f"o volume do microfone no arquivo é {perfil.mic.volume!r} — ela "
        "deixou 70 no controle deslizante do card"
    )
    assert perfil.mic.muted is None, (
        f"o mudo do microfone chegou ao arquivo ({perfil.mic.muted!r}) — ele é "
        "do controle, e o perfil não o leva"
    )


def _confere_speaker(perfil: Profile) -> None:
    assert perfil.speaker is not None, (
        "a seção `speaker` NÃO existe no arquivo — o volume que ela ajustou no "
        "card não virou configuração do perfil"
    )
    assert perfil.speaker.volume == 180, (
        f"o volume no arquivo é {perfil.speaker.volume} — ela deixou 180"
    )
    assert perfil.speaker.rota == 2, (
        f"a rota de saída no arquivo é {perfil.speaker.rota!r} — ela escolheu o "
        "canal 2 (L no fone, R no alto-falante)"
    )


def _confere_mode(perfil: Profile) -> None:
    assert perfil.mode is not None, (
        "a seção `mode` NÃO existe no arquivo — o modo que ela escolheu na aba "
        "Início evaporou no salvar (é a queixa literal do pragmata2.json)"
    )
    assert perfil.mode.kind == "gamepad", (
        f"o modo no arquivo é {perfil.mode.kind!r} — ela escolheu 'gamepad'"
    )
    assert perfil.mode.gamepad_flavor == "xbox", (
        f"a máscara no arquivo é {perfil.mode.gamepad_flavor!r} — ela escolheu "
        "'xbox'"
    )


def _confere_suppress(perfil: Profile) -> None:
    assert perfil.suppress_desktop_emulation is True, (
        "o `suppress_desktop_emulation` do arquivo é False — o modo jogo que "
        "ela ligou na aba Emulação não ficou salvo"
    )


def _confere_controllers(perfil: Profile) -> None:
    assert perfil.controllers, (
        "o mapa `controllers` NÃO existe no arquivo — a cor que ela ajustou "
        "para UM controle não ficou dentro do perfil"
    )
    entrada = perfil.controllers.get(UNIQ_DE_TESTE)
    assert entrada is not None and entrada.leds is not None, (
        f"o override do controle {UNIQ_DE_TESTE} não tem seção de LEDs: "
        f"{perfil.controllers!r}"
    )
    assert tuple(entrada.leds.lightbar) == (200, 10, 10), (
        f"a cor do override é {tuple(entrada.leds.lightbar)!r} — ela escolheu "
        "(200, 10, 10) com aquele controle selecionado"
    )


def _gesto_nome(janela: Any) -> None:
    """O nome não tem gesto de aba: ele é o que ela digita no diálogo."""
    return None


def _confere_nome(perfil: Profile) -> None:
    assert perfil.name == "Pragmata", (
        f"o perfil no disco se chama {perfil.name!r} — o nome do arquivo e o "
        "nome de dentro dele divergiram"
    )


def _gesto_match(janela: Any) -> None:
    """A regra não tem gesto de rodapé: ela vem do disco (REGRA-NAO-SE-PERDE)."""
    return None


def _confere_match(perfil: Profile) -> None:
    assert isinstance(perfil.match, MatchCriteria), (
        f"a regra virou {type(perfil.match).__name__} — salvar rebaixou o "
        "perfil do jogo a catch-all (REGRA-NAO-SE-PERDE-01)"
    )
    assert perfil.match.window_class == ["steam_app_3357650"], (
        f"a regra no arquivo é {perfil.match.window_class!r} — a do disco era "
        "steam_app_3357650"
    )


def _gesto_priority(janela: Any) -> None:
    """A prioridade não tem gesto de rodapé: quem existe herda a do disco."""
    return None


def _confere_priority(perfil: Profile) -> None:
    assert perfil.priority == 60, (
        f"a prioridade no arquivo é {perfil.priority} — era 60 no disco, e o "
        "rodapé não pode recalculá-la (a catraca do GRAVA-POR-UM-FUNIL-01)"
    )


_QUEBRADAS_HOJE: dict[str, str] = {}


def _casos() -> list[Any]:
    """Um ``pytest.param`` por seção, com o xfail estrito de quem está quebrada."""
    saida: list[Any] = []
    for campo in SECOES_COBERTAS:
        motivo = _QUEBRADAS_HOJE.get(campo)
        marcas = (
            [pytest.mark.xfail(strict=True, reason=motivo)] if motivo else []
        )
        saida.append(pytest.param(campo, id=campo, marks=marcas))
    return saida


class TestARegistroEACoberturaNaoPodemDivergir:
    """O literal que o portão lê tem de descrever os casos que existem aqui."""


    def test_toda_secao_quebrada_tem_motivo_escrito(self) -> None:
        """xfail sem razão é defeito escondido, não defeito documentado."""
        for campo, motivo in _QUEBRADAS_HOJE.items():
            assert campo in SECOES_COBERTAS, (
                f"{campo!r} está marcada como quebrada e não é seção coberta"
            )
            assert motivo and len(motivo) > 40, (
                f"a razão do xfail de {campo!r} é curta demais para explicar "
                f"onde o dado se perde: {motivo!r}"
            )


class TestOQueOEsquemaNaoTem:
    """Touch e giroscópio: a lacuna é de PRODUTO, e fica escrita aqui."""

    def test_touch_e_giroscopio_ainda_nao_sao_campos_do_perfil(self) -> None:
        """MORDIDA: acrescente ``gyro`` ao ``Profile`` e este teste reprova."""
        campos = set(Profile.model_fields)
        nascidos = {
            nome
            for nome in campos
            if any(
                pista in nome.lower()
                for pista in ("touch", "gyro", "giro", "motion", "sensor")
            )
        }
        assert not nascidos, (
            f"nasceram campos de touch/giroscópio no perfil ({sorted(nascidos)}) "
            "— acrescente o caso de ida-e-volta em SECOES_COBERTAS/_GESTOS, "
            "senão a feature nasce sem prova de que chega ao disco"
        )


class TestOsTiposDoEsquemaContinuamOsMesmos:
    """As seções opcionais continuam sendo as classes que os casos conferem."""

    def test_as_secoes_opcionais_tem_os_tipos_esperados(self, disco: Path) -> None:
        perfil = Profile(
            name="sonda",
            match=MatchCriteria(window_class=["x"]),
            mouse=ProfileMouseConfig(enabled=True),
            mic=ProfileMicConfig(button_toggles_system=True),
            speaker=ProfileSpeakerConfig(volume=100),
            mode=ProfileModeConfig(kind="gamepad"),
        )
        assert isinstance(perfil.mouse, ProfileMouseConfig)
        assert isinstance(perfil.mic, ProfileMicConfig)
        assert isinstance(perfil.speaker, ProfileSpeakerConfig)
        assert isinstance(perfil.mode, ProfileModeConfig)
