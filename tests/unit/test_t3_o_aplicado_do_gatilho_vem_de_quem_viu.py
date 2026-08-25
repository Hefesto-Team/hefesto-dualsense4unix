"""GATILHOS-APLICADO-COM-PROVA/T3 — "aplicado" sai da boca de quem viu o byte.

O DEFEITO, MEDIDO NA BANCADA VIVA EM 23/08/2026
===============================================
Com a mesa VAZIA, o daemon respondeu ao ``trigger.set``::

    {"status": "ok", "aplicado_em": [], "guardado_em": []}

Zero destino: nenhum byte no fio, nada guardado. E a aba Gatilhos disse
*"SimpleRigid aplicado"*.

A causa tinha DOIS elos, e este arquivo prende os dois:

1. a ponte estreitava a resposta para ``bool`` (``trigger_set_checked``), então
   o corpo do daemon morria antes de chegar à janela — a ``ELO-MUDO-01``
   construiu ``trigger_set_detalhado``/``trigger_reset_detalhado`` em 23/08 e
   deixou a ligação pendurada, de propósito, porque os chamadores moravam em
   arquivo que outra frente editava;
2. o ``_toast_trigger`` **re-deduzia** o destino do estado da própria janela.
   Essa heurística cobre duas das três razões que o daemon conhece (alvo fora
   da mesa, Modo Nativo) e **não cobre a mesa vazia com o alvo em "Todos"** —
   que é exatamente a rota medida.

A INVERSÃO É A ENTREGA: antes a janela deduzia e o daemon era ignorado; agora o
daemon manda, e a janela só preenche o silêncio quando ele não respondeu. Quem
decide a palavra é ``app/textos_de_aplicacao.frase_do_desfecho`` — dona única do
vocabulário, e é por isso que este arquivo nunca escreve as frases à mão.

O QUE ESTE ARQUIVO **NÃO** PROVA, e não pode
============================================
Que o controle OBEDECEU. ``gatilho.leitura`` é ``não/não`` nos dois transportes
no mapa de canais: não existe leitura de estado de gatilho neste produto. O que
a T3 entrega é *"o daemon escreveu"* — "aplicado" nunca vira "confirmado".

AS DUAS MORDIDAS, e elas são independentes de propósito
========================================================
* **esta** — arranque a leitura do corpo (volte ``_toast_trigger`` a montar a
  frase pela heurística) e a mesa vazia volta a dizer "aplicado";
* **a do portão** — tire as entradas de ``trigger_set_detalhado``,
  ``trigger_reset_detalhado`` e ``frase_do_desfecho`` do registro de
  ``portao_a_casa_sabe_e_o_produto_nao_faz.py`` **sem** trocar os chamadores, e
  o portão reprova nomeando os três. É a regra das réguas em série: consertar
  um portão deixa o sintoma idêntico se o outro olhar para o mesmo lugar.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("o desfecho do gatilho vem do corpo do daemon")

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import triggers_actions
from hefesto_dualsense4unix.app.actions.triggers_actions import TriggersActionsMixin
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.app.textos_de_aplicacao import GUARDADO, NADA_ACONTECEU

#: Endereços sintéticos, FORA da faixa `aabbcc…` que outros arquivos usam.
NA_MESA = "02:fe:00:00:00:33"
FORA_DA_MESA = "e8:47:3a:00:00:66"
#: O rótulo que a aba Status guarda do alvo (a R-16 o preserva quando ele cai).
ROTULO_DO_AUSENTE = "Controle 2 (BT)"

#: A resposta que a bancada MEDIU em 23/08 com a mesa vazia. É o caso.
CORPO_MESA_VAZIA: dict[str, Any] = {
    "status": "ok",
    "aplicado_em": [],
    "guardado_em": [],
}


class _BarraDeStatus:
    def __init__(self) -> None:
        self.mensagens: list[str] = []

    def get_context_id(self, _k: str) -> int:
        return 1

    def push(self, _ctx: int, msg: str) -> None:
        self.mensagens.append(msg)


class _Slider:
    """O mínimo de `Gtk.Scale` que `_collect_values` toca."""

    def __init__(self, valor: int) -> None:
        self._valor = valor

    def get_value(self) -> float:
        return float(self._valor)


class _Caixa:
    """O mínimo de `Gtk.Box` que `_rebuild_params` toca (o "Desligar" o chama).

    O modo ``Off`` não tem parâmetro nenhum, então o laço que monta sliders não
    roda e nenhum widget de verdade é criado — é o que deixa este arquivo medir
    o caminho de produção sem servidor gráfico.
    """

    def __init__(self) -> None:
        self.filhos: list[Any] = []

    def get_children(self) -> list[Any]:
        return list(self.filhos)

    def remove(self, filho: Any) -> None:
        self.filhos.remove(filho)

    def pack_start(self, filho: Any, *_a: Any) -> None:
        self.filhos.append(filho)

    def show_all(self) -> None:
        return None


class _Rotulo:
    """O mínimo de `Gtk.Label` que `_rebuild_params` toca."""

    def __init__(self) -> None:
        self.texto = ""

    def set_text(self, texto: str) -> None:
        self.texto = texto

    def set_markup(self, texto: str) -> None:
        self.texto = texto


class _Modo:
    """O mínimo de `SegmentedSelector` que `_apply_trigger` toca."""

    def __init__(self, ativo: str) -> None:
        self._ativo = ativo

    def get_active_id(self) -> str | None:
        return self._ativo

    def set_active_id(self, the_id: str) -> None:
        self._ativo = the_id


class _Host(TriggersActionsMixin):
    """Host mínimo com o estado que a aba Status mantém do ``state_full``.

    Sem GTK montado: o que está em julgamento é a FRASE, e ela sai de função
    pura. Os dublês de widget existem só para o caminho de produção
    (`_apply_trigger` -> `_collect_values` -> a ponte) rodar inteiro — é ele que
    se mede, não uma cópia dele.
    """

    def __init__(
        self,
        *,
        modo: str = "Rigid",
        alvo: str | None = None,
        conectados: dict[int, str | None] | None = None,
        nativo: bool = False,
    ) -> None:
        self.draft = DraftConfig.default()
        self._edit_target_uniq = alvo
        self._edit_target_label = ROTULO_DO_AUSENTE
        self._target_uniq_by_index = {0: NA_MESA} if conectados is None else conectados
        self._modo_nativo_ligado = nativo
        self._trigger_mode = {"left": _Modo(modo), "right": _Modo("Off")}
        spec = triggers_actions.get_spec(modo)
        assert spec is not None
        self._trigger_param_widgets = {
            "left": {p.name: _Slider(p.default) for p in spec.params},
            "right": {},
        }
        self._trigger_live_preview_timer = {"left": 0, "right": 0}
        self.barra = _BarraDeStatus()
        self._widgets: dict[str, Any] = {"status_bar": self.barra}
        for lado in ("left", "right"):
            self._widgets[f"trigger_{lado}_params_box"] = _Caixa()
            self._widgets[f"trigger_{lado}_desc"] = _Rotulo()

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    @property
    def ultima(self) -> str:
        return self.barra.mensagens[-1]


@pytest.fixture
def daemon(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Dublê da ponte que sabe RECUSAR, e não só passar.

    Régua que só sabe passar não é régua: os testes abaixo exercitam as duas
    respostas — corpo com destino, corpo sem destino nenhum, recusa, e o
    silêncio do daemon morto (``corpo=None``).
    """

    class _Ponte:
        def __init__(self) -> None:
            self.resposta: tuple[bool, str | None, dict[str, Any] | None] = (
                True,
                None,
                CORPO_MESA_VAZIA,
            )
            self.pedidos: list[tuple[str, str, list[int], str | None]] = []
            self.resets: list[tuple[str | None, str | None]] = []

        def set(
            self, side: str, mode: str, params: list[int], uniq: str | None = None
        ) -> tuple[bool, str | None, dict[str, Any] | None]:
            self.pedidos.append((side, mode, list(params), uniq))
            return self.resposta

        def reset(
            self, side: str | None = None, uniq: str | None = None
        ) -> tuple[bool, str | None, dict[str, Any] | None]:
            self.resets.append((side, uniq))
            return self.resposta

    ponte = _Ponte()
    monkeypatch.setattr(triggers_actions, "trigger_set_detalhado", ponte.set)
    monkeypatch.setattr(triggers_actions, "trigger_reset_detalhado", ponte.reset)
    return ponte


class TestAMesaVaziaParaDeDizerAplicado:
    """O caso medido em 23/08 — e ele é o motivo de a T3 existir."""

    def test_zero_destino_nao_e_aplicado(self, daemon: Any) -> None:
        host = _Host(alvo=None, conectados={})
        host._apply_trigger("left")
        assert "aplicado" not in host.ultima, (
            "o daemon respondeu `aplicado_em: [], guardado_em: []` — zero "
            "destino, nenhum byte no fio — e a barra afirmou aplicação"
        )
        assert NADA_ACONTECEU in host.ultima
        assert host.ultima.startswith("Gatilho esquerdo (L2): Rigid")

    def test_o_desligar_tambem_para_de_mentir(self, daemon: Any) -> None:
        """O "Desligar" ia pelo mesmo buraco: `ok` sem saber onde pegou."""
        host = _Host(alvo=None, conectados={})
        host._reset_trigger("left")
        assert daemon.resets == [("left", None)]
        assert NADA_ACONTECEU in host.ultima
        assert "aplicado" not in host.ultima

    def test_o_modo_por_posicao_carrega_o_corpo_igual(self, daemon: Any) -> None:
        """A rota de `dict` (`_send_trigger_named`) é a dos perfis de fábrica.

        `aventura` e `corrida` usam `MultiPositionFeedback`/`Vibration`, que
        passam por `_send_trigger_named`. Deixar SÓ a rota posicional lendo o
        corpo curaria a aba pela metade — a metade que ela menos usa.
        """
        host = _Host(modo="MultiPositionFeedback", alvo=None, conectados={})
        host._apply_trigger("left")
        assert daemon.pedidos == [
            ("left", "MultiPositionFeedback", [0, 1, 2, 3, 4, 5, 6, 7, 8, 8], None)
        ]
        assert NADA_ACONTECEU in host.ultima


class TestOCorpoManda:
    def test_um_destino_diz_aplicado_sem_numero(self, daemon: Any) -> None:
        """A mordida gêmea: a cura não pode avançar longe demais."""
        daemon.resposta = (True, None, {"status": "ok", "aplicado_em": [NA_MESA]})
        host = _Host(alvo=NA_MESA)
        host._apply_trigger("left")
        assert host.ultima == "Gatilho esquerdo (L2): Rigid aplicado"

    def test_dois_destinos_dizem_quantos(self, daemon: Any) -> None:
        daemon.resposta = (
            True,
            None,
            {"status": "ok", "aplicado_em": [NA_MESA, FORA_DA_MESA]},
        )
        host = _Host(alvo=None)
        host._apply_trigger("left")
        assert host.ultima == "Gatilho esquerdo (L2): Rigid aplicado em 2 controles"

    def test_so_guardado_diz_guardado_e_por_que(self, daemon: Any) -> None:
        """O `guardado_em` do daemon decide; a janela entra como o PORQUÊ."""
        daemon.resposta = (
            True,
            None,
            {"status": "ok", "aplicado_em": [], "guardado_em": [FORA_DA_MESA]},
        )
        host = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA})
        host._apply_trigger("left")
        assert GUARDADO in host.ultima
        assert "vai valer quando o Controle 2 voltar" in host.ultima
        assert "aplicado" not in host.ultima

    def test_a_recusa_no_corpo_e_a_frase_dele(self, daemon: Any) -> None:
        """Quando o daemon manda uma frase, ela é para ela — não a nossa."""
        daemon.resposta = (
            True,
            None,
            {"status": "recusado", "motivo": "o jogo é o dono do bloco de gatilho"},
        )
        host = _Host(alvo=NA_MESA)
        host._apply_trigger("left")
        assert "recusado: o jogo é o dono do bloco de gatilho" in host.ultima
        assert "aplicado" not in host.ultima


class TestOQueJaFuncionavaContinua:
    """Hipótese tem de explicar o que JÁ funcionava — regra da casa."""

    def test_daemon_mudo_cai_na_heuristica_de_sempre(self, daemon: Any) -> None:
        """Corpo ausente = não há resposta a ler; só aí a janela decide."""
        daemon.resposta = (True, None, None)
        host = _Host(alvo=NA_MESA)
        host._apply_trigger("left")
        assert host.ultima == "Gatilho esquerdo (L2): Rigid aplicado"

    def test_daemon_mudo_com_alvo_fora_ainda_diz_guardado(self, daemon: Any) -> None:
        daemon.resposta = (True, None, None)
        host = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA})
        host._apply_trigger("left")
        assert GUARDADO in host.ultima
        assert "vai valer quando o Controle 2 voltar" in host.ultima

    def test_modo_nativo_continua_vencendo_com_o_daemon_mudo(
        self, daemon: Any
    ) -> None:
        daemon.resposta = (True, None, None)
        host = _Host(alvo=NA_MESA, nativo=True)
        host._apply_trigger("left")
        assert GUARDADO in host.ultima
        assert "Modo Nativo" in host.ultima

    def test_a_recusa_por_parametro_continua_humanizada(self, daemon: Any) -> None:
        """HARM-19: daemon VIVO que recusa não pode virar "offline?"."""
        daemon.resposta = (False, "end (3) deve ser > start (5)", None)
        host = _Host(alvo=NA_MESA)
        host._apply_trigger("left")
        assert "não aplicado" in host.ultima
        assert "precisa ser maior que" in host.ultima

    def test_daemon_morto_continua_mandando_para_a_aba_sistema(
        self, daemon: Any
    ) -> None:
        daemon.resposta = (False, None, None)
        host = _Host(alvo=NA_MESA)
        host._apply_trigger("left")
        assert "aba Sistema" in host.ultima

    def test_alvo_desconhecido_continua_recusando_antes_do_ipc(
        self, daemon: Any
    ) -> None:
        """Z2-2: sem saber o alvo, a aba não manda — e não é a T3 que muda isso."""
        host = _Host(alvo=NA_MESA)
        del host._edit_target_uniq
        host._apply_trigger("left")
        assert daemon.pedidos == []
        assert "não aplicado" in host.ultima
        assert "Nada foi alterado" in host.ultima


class TestAPonteEstreitaSaiuDaAba:
    """A ligação da ELO-MUDO-01 aconteceu — e o jeito de provar é a ausência.

    Um teste que só olhasse a frase passaria com a aba ainda chamando a ponte
    estreita e montando a mesma frase por acaso. O que fecha a dívida do
    registro de `portao_a_casa_sabe_e_o_produto_nao_faz.py` é o CHAMADOR.
    """

    def test_a_aba_nao_importa_mais_os_involucros_de_bool(self) -> None:
        from pathlib import Path

        fonte = Path(triggers_actions.__file__).read_text(encoding="utf-8")
        assert "trigger_set_detalhado" in fonte
        assert "trigger_reset_detalhado" in fonte
        assert "import trigger_set_checked" not in fonte
        for estreito in ("trigger_set_checked(", "trigger_reset("):
            assert estreito not in fonte, (
                f"`{estreito}` de volta na aba: o corpo do daemon morre de novo"
            )

    def test_o_vocabulario_continua_num_lugar_so(self) -> None:
        """A frase sai de `textos_de_aplicacao`, não de um literal daqui."""
        from pathlib import Path

        fonte = Path(triggers_actions.__file__).read_text(encoding="utf-8")
        assert "frase_do_desfecho" in fonte
        assert f'"{GUARDADO}' not in fonte, (
            "a aba escreveu a palavra em vez de importá-la"
        )
