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

exigir_gi_real("o desfecho do gatilho vem do corpo do daemon")

from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import triggers_actions
from hefesto_dualsense4unix.app.textos_de_aplicacao import GUARDADO

NA_MESA = "02:fe:00:00:00:33"
FORA_DA_MESA = "e8:47:3a:00:00:66"
ROTULO_DO_AUSENTE = "Controle 2 (BT)"

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
    """O mínimo de `Gtk.Box` que `_rebuild_params` toca (o "Desligar" o chama)."""

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


@pytest.fixture
def daemon(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Dublê da ponte que sabe RECUSAR, e não só passar."""

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
