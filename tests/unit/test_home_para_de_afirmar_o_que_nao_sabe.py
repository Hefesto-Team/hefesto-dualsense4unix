"""A primeira tela para de afirmar o que não apurou — I4, I6, I11 e I3.

INÍCIO NÃO MENTE-01. Quatro afirmações que a aba Início fazia sem lastro, e o
que cada uma passou a dizer no lugar:

* **I4 — a pausa.** O ``_render_home`` tinha DOIS estados (daemon vivo, daemon
  morto). Com o Hefesto em pausa o payload continua ``connected: true`` e a aba
  pintava o caminho feliz inteiro — *"o Hefesto acende as luzes, faz o controle
  vibrar e dá um jogador para cada controle"* — enquanto nada disso acontecia.
  A aba Emulação, com o MESMO campo, já dizia "O Hefesto está em pausa";
* **I6 — a ponte sobre mesa vazia.** MEDIDO na bancada de 23/08/2026 com ZERO
  DualSense na casa: o frame dizia "Nenhum controle conectado." e a linha logo
  acima dizia, em VERDE, *"pelo Hefesto — o jogo recebe o controle"*. A função
  respondia sobre o **vpad**; a pessoa lê como resposta sobre o **jogo**;
* **I11 — o cadeado cego.** Na máquina dela, agora, a troca automática de
  perfil por janela está cega (``window_detect_seeing=False``,
  ``reason='sem_conexao_x'``) e o produto se declara são
  (``window_detect_healthy=True``). Com a caixa desmarcada — o padrão — a linha
  ao lado era **vazia**: nem que o mecanismo existe, nem que ele parou;
* **I3 — "você escolheu".** Com a fonte 1 morta, a divergência era sempre
  medida contra a máscara do PERFIL, que entra sozinho pelo autoswitch. A frase
  acusava a pessoa de um gesto que ela não deu.

O TEXTO de todas elas é **estrutural** e espera o olho dela
(PROVA-DE-TELA-01). Este arquivo mede o que a tela não pode dizer, e o que ela
tem de deixar de calar — nunca a redação.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MEDIDA = RAIZ / "tests" / "fixtures" / "state_full_mesa_vazia_medida.json"


def _payload_medido() -> dict[str, Any]:
    """O `state_full` de 23/08/2026, com o daemon vivo e a mesa vazia."""
    return json.loads(FIXTURE_MEDIDA.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------
# O dublê da aba — o mesmo desenho do `_HomeStub` dos vizinhos
# ----------------------------------------------------------------------


class _Widget:
    def __init__(self, label: str | None = None, **_kw: Any) -> None:
        # O `label=` do construtor é guardado: `Gtk.Label(label=...)` é como
        # o `_render_home_controllers` escreve o subtítulo do card, e um
        # dublê que o jogasse fora mediria uma fileira de cards mudos.
        self.texto = label or ""
        self.visivel = True
        self.active_id: str | None = None
        self.filhos: list[Any] = []
        self.classes: list[str] = []

    def set_text(self, valor: str) -> None:
        self.texto = valor

    def get_text(self) -> str:
        return self.texto

    def set_markup(self, valor: str) -> None:
        self.texto = valor

    def set_label(self, valor: str) -> None:
        self.texto = valor

    def set_visible(self, valor: bool) -> None:
        self.visivel = bool(valor)

    def get_visible(self) -> bool:
        return self.visivel

    def set_sensitive(self, _v: bool) -> None:
        pass

    def set_no_show_all(self, _v: bool) -> None:
        pass

    def set_active(self, _v: bool) -> None:
        pass

    def set_active_id(self, valor: str) -> None:
        self.active_id = valor

    def set_xalign(self, _v: float) -> None:
        pass

    def set_margin_end(self, _v: int) -> None:
        pass

    def get_style_context(self) -> Any:
        return SimpleNamespace(
            add_class=self.classes.append,
            remove_class=lambda n: None,
        )

    def pack_start(self, filho: Any, *_a: object) -> None:
        self.filhos.append(filho)

    def get_children(self) -> list[Any]:
        return list(self.filhos)

    def remove(self, filho: Any) -> None:
        self.filhos.remove(filho)

    def show_all(self) -> None:
        pass


class _HomeStub:
    _render_home = HomeActionsMixin._render_home
    _render_home_controllers = HomeActionsMixin._render_home_controllers
    _render_ponte_e_divergencia = HomeActionsMixin._render_ponte_e_divergencia
    _mascara_escolhida_por_ela = HomeActionsMixin._mascara_escolhida_por_ela
    _mascara_escolhida_com_fonte = HomeActionsMixin._mascara_escolhida_com_fonte

    def __init__(self) -> None:
        self._home_installed = True
        self._home_guard = False
        self._home_inflight = False
        self._home_flavor_pedido: str | None = None
        self._escolha_pendente: dict[str, str] | None = None
        self._modo_vigente_do_daemon: str | None = None
        self._mascara_vigente_do_daemon: str | None = None
        for nome in (
            "_home_mode_selector",
            "_home_flavor_selector",
            "_home_mode_desc",
            "_home_origin_label",
            "_home_session_label",
            "_home_players_hint",
            "_home_gamepad_opts",
            "_home_controllers_box",
            "_home_vpad_banner",
            "_home_wrapper_banner",
            "_home_shutdown_btn",
            "_home_reconciliar_btn",
            "_home_reconciliar_hint",
            "_home_ponte_label",
            "_home_divergencia_banner",
            "_home_autoswitch_lock",
            "_home_autoswitch_lock_hint",
        ):
            setattr(self, nome, _Widget())
        self._home_offline = False

    def _status_toast(self, _contexto: str, _msg: str) -> None:
        pass


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_Widget,
        Box=_Widget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


# ----------------------------------------------------------------------
# I4 — a pausa chega à primeira aba
# ----------------------------------------------------------------------


class TestAPausaChegaNaPrimeiraAba:
    def test_a_funcao_pura_so_acende_com_o_true_literal(self) -> None:
        """Chave ausente ou de outro tipo é "não sei", nunca "está parado".

        Mesma disciplina do `wrapper_used`: um daemon mais velho não afirma que
        o produto está em pausa, só não sabe dizer.
        """
        assert home_actions.texto_da_pausa({"paused": True})
        assert home_actions.texto_da_pausa({"paused": False}) is None
        assert home_actions.texto_da_pausa({}) is None
        assert home_actions.texto_da_pausa({"paused": 1}) is None
        assert home_actions.texto_da_pausa(None) is None

    def test_em_pausa_a_descricao_nao_promete_luz_nem_vibracao(
        self, fake_gtk: None
    ) -> None:
        """A MORDIDA da I4, literal do §5 da sprint.

        Arranque a consulta a `paused` no `_render_home` (volte a linha para
        `_MODE_DESCRIPTIONS.get(modo_exibido, "")` seco) e este teste reprova.
        """
        host = _HomeStub()
        estado = {
            "connected": True,
            "paused": True,
            "native_mode": False,
            "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
            "controllers": [
                {"index": 0, "connected": True, "transport": "usb",
                 "is_primary": True}
            ],
        }

        host._render_home(estado)

        descricao = host._home_mode_desc.get_text()
        assert "acende as luzes" not in descricao, (
            f"com o Hefesto em pausa a aba continua prometendo o caminho "
            f"feliz: {descricao!r}"
        )
        assert "pausa" in descricao.lower(), (
            "a aba calou sobre a pausa em vez de dizê-la — calar é o estado "
            "anterior, não a cura"
        )

    def test_sem_pausa_a_descricao_do_modo_volta_inteira(
        self, fake_gtk: None
    ) -> None:
        """A régua sabe dizer NÃO: sem pausa, a promessa do modo continua."""
        host = _HomeStub()
        estado = {
            "connected": True,
            "paused": False,
            "native_mode": False,
            "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
            "controllers": [
                {"index": 0, "connected": True, "transport": "usb",
                 "is_primary": True}
            ],
        }

        host._render_home(estado)

        assert "acende as luzes" in host._home_mode_desc.get_text()

    def test_a_pausa_do_produto_e_lida_do_mesmo_campo_da_aba_emulacao(
        self,
    ) -> None:
        """Uma fonte só. Duas leituras do mesmo fato não podem discordar.

        A aba Emulação lê `state["paused"]` para escrever "O Hefesto está em
        pausa"; esta aba tem de ler a MESMA chave, não uma derivada.
        """
        fonte = (
            RAIZ / "src/hefesto_dualsense4unix/app/actions/emulation_actions.py"
        ).read_text(encoding="utf-8")
        assert 'state.get("paused")' in fonte
        assert home_actions.texto_da_pausa({"paused": True}) is not None


# ----------------------------------------------------------------------
# I6 — a ponte não acende sobre mesa vazia
# ----------------------------------------------------------------------


class TestAPonteNaoAcendeSobreMesaVazia:
    def test_o_payload_medido_nao_produz_verde(self) -> None:
        """A MORDIDA da I6, literal do §5: o payload do §2.1 não pode sair verde.

        Arranque o ramo da mesa vazia em `texto_da_ponte` e este teste reprova
        — a frase volta a ser `#50fa7b` "pelo Hefesto" com zero controle na
        casa, que é o que a bancada mediu.
        """
        frase = home_actions.texto_da_ponte(_payload_medido())

        assert "#50fa7b" not in frase, (
            f"a ponte acendeu VERDE sobre a mesa vazia: {frase!r}. É o estado "
            "vazio pintado com a cor do estado bom (defeito de forma F7)."
        )
        assert frase.startswith(home_actions.PONTE_PREFIXO)

    def test_a_mesa_vazia_nao_e_a_mesma_frase_de_nenhuma_ponte(self) -> None:
        """Quarto veredito, e não o terceiro reaproveitado.

        "Nenhuma ponte" é o desktop — não há gamepad de pé. "De pé e vazia" é o
        gamepad montado sem quem o alimente. Dizer as duas com a mesma frase
        mandaria a pessoa clicar num botão que já está clicado.
        """
        vazia = home_actions.texto_da_ponte(_payload_medido())
        desktop = home_actions.texto_da_ponte(
            {
                "gamepad_emulation": {"enabled": False},
                "native_mode": False,
                "controllers": [],
            }
        )

        assert vazia != desktop
        assert 'Jogar pelo Hefesto"' in desktop
        assert 'Jogar pelo Hefesto"' not in vazia

    def test_com_controle_na_mesa_a_ponte_volta_a_ser_verde(self) -> None:
        """A régua sabe dizer SIM — senão "nunca verde" passaria por severo."""
        estado = _payload_medido()
        estado["controllers"] = [
            {"index": 0, "connected": True, "transport": "usb", "is_primary": True}
        ]

        frase = home_actions.texto_da_ponte(estado)

        assert "#50fa7b" in frase
        assert "pelo Hefesto" in frase

    def test_a_contagem_da_ponte_usa_o_mesmo_filtro_do_frame(self) -> None:
        """`connected=False` é o card fantasma — e não conta como mesa.

        `describe_controllers` devolve UMA entrada desconectada quando não há
        controle nenhum. Contar sem filtrar traria o fantasma de volta por
        outra porta, e a ponte acenderia verde com a mesa vazia de novo.
        """
        assert home_actions.controles_na_mesa(_payload_medido()) == 0
        assert (
            home_actions.controles_na_mesa(
                {"controllers": [{"connected": True}, {"connected": False}]}
            )
            == 1
        )
        assert home_actions.controles_na_mesa(None) == 0

    def test_a_ordem_das_cinco_perguntas_nao_mudou(self) -> None:
        """Steam Input e Nativo continuam vencendo o gamepad, com mesa vazia.

        A bifurcação da I6 mora DENTRO da quarta pergunta. Se ela tivesse
        subido, a exceção de Steam Input com mesa vazia passaria a dizer "de pé
        e vazia" — apagando o único veredito que explica por que o jogo está
        jogando sem o vpad.
        """
        vazio: list[dict[str, Any]] = []
        steam = home_actions.texto_da_ponte(
            {
                "gamepad_emulation": {"enabled": False},
                "steam_input": {"excecao_ativa": True, "vpad_suspenso": True},
                "controllers": vazio,
            }
        )
        nativo = home_actions.texto_da_ponte(
            {"native_mode": True, "gamepad_emulation": {"enabled": True},
             "controllers": vazio}
        )

        assert "Steam Input" in steam
        assert "direto (Sony)" in nativo


# ----------------------------------------------------------------------
# I11 — o cadeado diz quando o mecanismo que ele governa está cego
# ----------------------------------------------------------------------


class TestOCadeadoDizQuandoEstaCego:
    def test_a_funcao_pura_cala_sem_a_chave(self) -> None:
        """Ausência de chave é "não sei" — nunca "está cego".

        Um daemon mais velho não publica `window_detect_seeing`, e acender o
        aviso a partir disso seria alarme falso sobre um mecanismo que pode
        estar perfeito.
        """
        assert home_actions.texto_do_cadeado_cego({}) == ""
        assert home_actions.texto_do_cadeado_cego(None) == ""
        assert home_actions.texto_do_cadeado_cego({"window_detect_seeing": True}) == ""
        assert home_actions.texto_do_cadeado_cego({"window_detect_seeing": False})

    def test_o_payload_medido_faz_a_linha_falar(self, fake_gtk: None) -> None:
        """A MORDIDA da I11, literal do §5: com o payload do §2.1 a linha fala.

        Arranque a consulta a `window_detect_seeing` (faça
        `texto_do_cadeado_cego` devolver `""` sempre) e este teste reprova — a
        linha volta a ser vazia, que é o estado de hoje na máquina dela.
        """
        host = _HomeStub()

        host._render_home(_payload_medido())

        linha = host._home_autoswitch_lock_hint
        assert linha.get_visible() is True
        assert linha.get_text().strip(), (
            "a linha do cadeado continua vazia com o detector cego — a aba não "
            "diz nem que o mecanismo existe, nem que ele parou"
        )

    def test_com_o_detector_enxergando_e_o_cadeado_solto_a_linha_cala(
        self, fake_gtk: None
    ) -> None:
        """Sem nada a dizer, a linha some — é o comportamento normal."""
        host = _HomeStub()
        estado = _payload_medido()
        estado["window_detect_seeing"] = True

        host._render_home(estado)

        assert host._home_autoswitch_lock_hint.get_visible() is False

    def test_o_cadeado_ligado_continua_dizendo_o_que_dizia(self) -> None:
        """A frase antiga não foi substituída: as duas metades convivem.

        `autoswitch_lock_text` é a voz do que ELA escolheu; a nova é a do que
        não vai acontecer de qualquer jeito. Perder a primeira trocaria um
        silêncio por outro.
        """
        texto = home_actions.autoswitch_lock_text(
            {"autoswitch_locked": True, "active_profile": "pragmata"}
        )
        assert "Cadeado ligado" in texto
        assert "pragmata" in texto

    def test_a_frase_do_cadeado_nao_vai_para_o_rodape(self, fake_gtk: None) -> None:
        """O toast do rodapé segue falando SÓ do cadeado (AVISO-VIVO-01).

        Enfiar a cegueira do detector em `autoswitch_lock_text` faria o rodapé
        anunciá-la por BORDA toda vez que ela piscasse — ruído sobre um fato que
        já está escrito na tela, duas linhas acima.
        """
        toasts: list[str] = []
        host = _HomeStub()
        host._status_toast = lambda _c, msg: toasts.append(msg)  # type: ignore[method-assign]
        host._home_lock_toast = None

        host._render_home(_payload_medido())

        assert all(
            home_actions.TEXTO_DETECTOR_CEGO not in msg for msg in toasts
        ), f"a cegueira do detector vazou para o rodapé: {toasts}"


# ----------------------------------------------------------------------
# I3 — "você escolheu" para de acusar sobre gesto que ela não deu
# ----------------------------------------------------------------------


class _Rascunho:
    """Um `draft` com a seção `mode` do perfil, e nada mais."""

    def __init__(self, flavor: str) -> None:
        self.source_mode = {"kind": "gamepad", "gamepad_flavor": flavor}


class TestNinguemEAcusadoDeGestoQueNaoDeu:
    def test_mascara_vinda_do_perfil_nao_diz_voce_escolheu(
        self, fake_gtk: None
    ) -> None:
        """A MORDIDA da I3, segunda metade do §5.

        `draft` com `xbox` e SEM gesto dela: a frase não pode conter "você
        escolheu". Arranque a fonte do `_mascara_escolhida_com_fonte` (devolva
        sempre `FONTE_GESTO_DELA`) e este teste reprova.
        """
        host = _HomeStub()
        host.draft = _Rascunho("xbox")  # type: ignore[attr-defined]

        host._render_home(
            {
                "connected": True,
                "native_mode": False,
                "gamepad_emulation": {
                    "enabled": True,
                    "flavor": "dualsense",
                    "backend": "uhid",
                },
                "controllers": [
                    {"index": 0, "connected": True, "transport": "usb",
                     "is_primary": True}
                ],
            }
        )

        banner = host._home_divergencia_banner
        assert banner.get_visible() is True
        assert "você escolheu" not in banner.get_text(), (
            f"a aba acusou um gesto que ela não deu: {banner.get_text()!r}. O "
            "perfil entra sozinho pelo autoswitch — quatro dos perfis desta "
            "casa pedem xbox."
        )
        assert "perfil" in banner.get_text().lower()

    def test_gesto_dela_continua_dizendo_voce_escolheu(
        self, fake_gtk: None
    ) -> None:
        """A régua sabe dizer SIM. O gesto dela é gesto dela."""
        host = _HomeStub()
        host._home_flavor_pedido = "xbox"

        host._render_home(
            {
                "connected": True,
                "native_mode": False,
                "gamepad_emulation": {
                    "enabled": True,
                    "flavor": "dualsense",
                    "backend": "uhid",
                },
                "controllers": [
                    {"index": 0, "connected": True, "transport": "usb",
                     "is_primary": True}
                ],
            }
        )

        assert "você escolheu" in host._home_divergencia_banner.get_text()

    def test_o_alarme_do_daemon_ganha_leitor_e_nomeia_o_perfil(
        self, fake_gtk: None
    ) -> None:
        """A MORDIDA da I3, primeira metade do §5.

        `gamepad_emulation.mascara_divergente` é publicado pelo daemon desde a
        MASCARA-01 e `grep -rn "mascara_divergente" src/` só achava o ESCRITOR.
        Com o alarme populado, a frase nomeia o perfil do jogo em cena em vez de
        falar em abstrato. Arranque a leitura (`mascara_divergente_do_daemon`)
        e a frase volta ao texto genérico.
        """
        host = _HomeStub()

        host._render_home(
            {
                "connected": True,
                "native_mode": False,
                "gamepad_emulation": {
                    "enabled": True,
                    "flavor": "dualsense",
                    "backend": "uhid",
                    "mascara_divergente": {
                        "appid": 1234560,
                        "profile": "Pragmata",
                        "mascara_perfil": "xbox",
                        "mascara_viva": "dualsense",
                        "motivo": "mascara_diferente",
                        "em_cena": True,
                    },
                },
                "controllers": [
                    {"index": 0, "connected": True, "transport": "usb",
                     "is_primary": True}
                ],
                "game_signal": {"authority": "game"},
            }
        )

        frase = host._home_divergencia_banner.get_text()
        assert "Pragmata" in frase, (
            f"o alarme do daemon nomeava o perfil em cena e a frase saiu "
            f"genérica: {frase!r}"
        )
        assert "você escolheu" not in frase

    def test_o_leitor_do_alarme_recusa_payload_que_nao_e_o_contrato(self) -> None:
        """Régua que só sabe aceitar não é régua."""
        assert home_actions.mascara_divergente_do_daemon(None) is None
        assert home_actions.mascara_divergente_do_daemon({}) is None
        assert (
            home_actions.mascara_divergente_do_daemon(
                {"gamepad_emulation": {"mascara_divergente": None}}
            )
            is None
        )
        assert (
            home_actions.mascara_divergente_do_daemon(
                {"gamepad_emulation": {"mascara_divergente": "xbox"}}
            )
            is None
        )
        assert home_actions.mascara_divergente_do_daemon(
            {"gamepad_emulation": {"mascara_divergente": {"mascara_perfil": "xbox"}}}
        ) == {"mascara_perfil": "xbox"}

    def test_a_frase_do_perfil_sem_nome_nao_inventa_um(self) -> None:
        """Sem o nome do perfil, a frase diz "o perfil ativo" — nunca um nome."""
        frase = home_actions.texto_da_divergencia(
            "xbox",
            "dualsense",
            jogo_aberto=False,
            fonte=home_actions.FONTE_PERFIL,
        )
        assert frase is not None
        assert "o perfil ativo pede" in frase
        assert "você escolheu" not in frase
