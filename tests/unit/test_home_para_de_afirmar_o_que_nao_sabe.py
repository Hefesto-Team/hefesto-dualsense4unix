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

from tests.conftest import exigir_gi_real

exigir_gi_real("test_home_para_de_afirmar_o_que_nao_sabe: importa código da janela GTK")

import ast
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_MEDIDA = RAIZ / "tests" / "fixtures" / "state_full_mesa_vazia_medida.json"


def _payload_medido() -> dict[str, Any]:
    """O `state_full` de 23/08/2026, com o daemon vivo e a mesa vazia."""
    return json.loads(FIXTURE_MEDIDA.read_text(encoding="utf-8"))


class _Widget:
    def __init__(self, label: str | None = None, **_kw: Any) -> None:
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


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_Widget,
        Box=_Widget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


class TestAPausaChegaNaPrimeiraAba:
    def test_a_funcao_pura_so_acende_com_o_true_literal(self) -> None:
        """Chave ausente ou de outro tipo é "não sei", nunca "está parado"."""
        assert home_actions.texto_da_pausa({"paused": True})
        assert home_actions.texto_da_pausa({"paused": False}) is None
        assert home_actions.texto_da_pausa({}) is None
        assert home_actions.texto_da_pausa({"paused": 1}) is None
        assert home_actions.texto_da_pausa(None) is None


    def test_a_pausa_do_produto_e_lida_do_mesmo_campo_da_aba_emulacao(
        self,
    ) -> None:
        """Uma fonte só. Duas leituras do mesmo fato não podem discordar."""
        fonte = (
            RAIZ / "src/hefesto_dualsense4unix/app/actions/emulation_actions.py"
        ).read_text(encoding="utf-8")
        assert 'state.get("paused")' in fonte
        assert home_actions.texto_da_pausa({"paused": True}) is not None


class TestAPonteNaoAcendeSobreMesaVazia:
    def test_o_payload_medido_nao_produz_verde(self) -> None:
        """A MORDIDA da I6, literal do §5: o payload do §2.1 não pode sair verde."""
        frase = home_actions.texto_da_ponte(_payload_medido())

        assert "#50fa7b" not in frase, (
            f"a ponte acendeu VERDE sobre a mesa vazia: {frase!r}. É o estado "
            "vazio pintado com a cor do estado bom (defeito de forma F7)."
        )
        assert frase.startswith(home_actions.PONTE_PREFIXO)

    def test_a_mesa_vazia_nao_e_a_mesma_frase_de_nenhuma_ponte(self) -> None:
        """Quarto veredito, e não o terceiro reaproveitado."""
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
        """`connected=False` é o card fantasma — e não conta como mesa."""
        assert home_actions.controles_na_mesa(_payload_medido()) == 0
        assert (
            home_actions.controles_na_mesa(
                {"controllers": [{"connected": True}, {"connected": False}]}
            )
            == 1
        )
        assert home_actions.controles_na_mesa(None) == 0

    def test_a_ordem_das_perguntas_nao_mudou(self) -> None:
        """O Modo Nativo continua vencendo o gamepad, com mesa vazia.

        A bifurcação da I6 mora DENTRO da pergunta do gamepad. Se ela tivesse
        subido, o Modo Nativo com mesa vazia passaria a dizer "de pé e vazia" —
        apagando o veredito que explica que o jogo fala direto com o DualSense,
        sem o Hefesto no meio.
        """
        vazio: list[dict[str, Any]] = []
        nativo = home_actions.texto_da_ponte(
            {"native_mode": True, "gamepad_emulation": {"enabled": True},
             "controllers": vazio}
        )

        assert "direto (Sony)" in nativo


class TestAExcecaoDeSteamInputNaoInventaUmaPonte:
    """25/08/2026 — o ramo que a sprint mandou "registrar e seguir", fechado."""

    @staticmethod
    def _mesa_de_um(**delta: Any) -> dict[str, Any]:
        """Um controle no cabo, emulação de pé — o caminho feliz mínimo."""
        estado: dict[str, Any] = {
            "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
            "controllers": [
                {"index": 0, "connected": True, "transport": "usb", "is_primary": True}
            ],
        }
        estado.update(delta)
        return estado

    def test_com_a_excecao_ativa_a_ponte_continua_sendo_o_hefesto(self) -> None:
        """O payload de HOJE: exceção ligada, vpad de pé (o único possível)."""
        linha = home_actions.texto_da_ponte(
            self._mesa_de_um(
                steam_input={"excecao_ativa": True, "vpad_suspenso": False}
            )
        )

        assert "pelo Hefesto" in linha
        assert "Steam" not in linha

    def test_a_aba_nao_diz_que_a_steam_entrega_os_botoes(self) -> None:
        """Nem pelo payload impossível de ontem."""
        linha = home_actions.texto_da_ponte(
            self._mesa_de_um(
                steam_input={"excecao_ativa": True, "vpad_suspenso": True}
            )
        )

        assert "entrega os botões" not in linha
        assert "pelo Steam Input" not in linha

    def test_com_a_excecao_ativa_e_a_mesa_vazia_a_ponte_nao_acende(self) -> None:
        """A exceção não pode reacender o verde que a I6 apagou."""
        estado = _payload_medido()
        estado["steam_input"] = {"excecao_ativa": True, "vpad_suspenso": False}

        linha = home_actions.texto_da_ponte(estado)

        assert "#50fa7b" not in linha
        assert "de pé, e vazia" in linha

    def test_a_aba_nao_le_uma_flag_que_so_anda_para_um_lado(self) -> None:
        """O portão de forma, e ele é o que impede a volta silenciosa."""
        arvore = ast.parse(
            (
                RAIZ / "src/hefesto_dualsense4unix/app/actions/home_actions.py"
            ).read_text(encoding="utf-8")
        )
        prosa = {
            id(no.body[0].value)
            for no in ast.walk(arvore)
            if isinstance(
                no, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
            )
            and no.body
            and isinstance(no.body[0], ast.Expr)
            and isinstance(no.body[0].value, ast.Constant)
            and isinstance(no.body[0].value.value, str)
        }
        codigo: list[str] = []
        for no in ast.walk(arvore):
            if isinstance(no, ast.Constant) and isinstance(no.value, str):
                if id(no) not in prosa and "vpad_suspenso" in no.value:
                    codigo.append(f"linha {no.lineno}: literal {no.value!r}")
            elif isinstance(no, ast.Attribute) and "vpad_suspenso" in no.attr:
                codigo.append(f"linha {no.lineno}: atributo .{no.attr}")

        assert not codigo, (
            "a aba Início voltou a LER `vpad_suspenso`, e ela só anda para "
            f"False desde 09/08/2026 (VPAD-SUSPENSO-MORTO-01/E1): {codigo}"
        )


class TestOCadeadoDizQuandoEstaCego:
    def test_a_funcao_pura_cala_sem_a_chave(self) -> None:
        """Ausência de chave é "não sei" — nunca "está cego"."""
        assert home_actions.texto_do_cadeado_cego({}) == ""
        assert home_actions.texto_do_cadeado_cego(None) == ""
        assert home_actions.texto_do_cadeado_cego({"window_detect_seeing": True}) == ""
        assert home_actions.texto_do_cadeado_cego({"window_detect_seeing": False})


    def test_o_cadeado_ligado_continua_dizendo_o_que_dizia(self) -> None:
        """A frase antiga não foi substituída: as duas metades convivem."""
        texto = home_actions.autoswitch_lock_text(
            {"freestyle_ligado": True, "active_profile": "pragmata"}
        )
        assert "Modo Freestyle ligado" in texto
        assert "pragmata" in texto


class _Rascunho:
    """Um `draft` com a seção `mode` do perfil, e nada mais."""

    def __init__(self, flavor: str) -> None:
        self.source_mode = {"kind": "gamepad", "gamepad_flavor": flavor}


class TestNinguemEAcusadoDeGestoQueNaoDeu:


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
