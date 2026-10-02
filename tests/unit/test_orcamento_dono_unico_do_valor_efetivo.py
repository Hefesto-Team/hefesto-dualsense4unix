"""O orçamento CALCULA; a aba de origem só EXIBE — e ninguém tem cópia do número.

CONFIG-05 (22/08/2026), a outra metade da D-A5. O arquivo irmão
(`test_orcamento_e_teto_nao_troca.py`) prende a CONTA no daemon; este prende o
que a tela pode dizer sobre ela, e são três invariantes:

1. **A linha "150% · limitado a 30% pelo orçamento" cala quando não sabe.**
   Sem declaração, com o orçamento em Auto (teto móvel) ou com o teto que não
   morde, a linha não aparece. Afirmar um limite que o daemon não impõe é o
   mesmo defeito que afirmar que ele não impõe um que impõe — só muda o lado
   para o qual manda caçar.
2. **Ninguém em `app/` recalcula a escada.** A única cópia autorizada é o
   `_POLICY_MULT` de `rumble_actions.py`, derivado do dono único; o percentual
   do teto sai de `core.rumble.teto_do_orcamento`. Duas contas divergem na
   primeira mudança de degrau — é o HARM-19, que já custou caro.
3. **A seção não grava nada.** O clique acumula em `_maquina_pendente` e ponto;
   o gesto de gravar tem UM dono, o "Aplicar" do rodapé. Um handler próprio
   aqui seria o segundo dono do mesmo valor, que é a `ABAS-01` de volta.

AS MORDIDAS, arrancadas e conferidas em 22/08/2026
--------------------------------------------------

1. **Fazer `teto_do_orcamento("auto")` devolver um número** (a escada de cima,
   1.0): reprova `test_em_auto_a_linha_cala_porque_o_teto_e_movel` — a tela
   passaria a prometer "limitado a 100%" para um teto que muda a cada tique.
2. **Trocar o `pedido <= teto` por `pedido < teto`**: reprova
   `test_a_linha_cala_quando_o_teto_nao_morde` — a aba diria "limitado a 30%"
   mostrando 30%, ou seja, anunciaria um corte que não houve.
3. **Fazer `_ao_escolher` chamar `machine_declare` na hora**: reprova
   `test_o_clique_nao_grava_nada` — e é a decisão D-A4 inteira, porque nesta
   aba nada vale antes do "Aplicar".
4. **Escrever "Economia" no lugar de "economia" em `CHAVES`**: reprova
   `test_o_clique_acumula_a_chave_e_nunca_o_rotulo` e
   `test_as_chaves_sao_as_do_schema` — e em produção o `extra="forbid"` do
   pydantic recusaria o DOCUMENTO INTEIRO na próxima carga.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a seção Orçamento da aba Configurações")

import ast
from pathlib import Path
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_orcamento
from hefesto_dualsense4unix.app.actions.rumble_actions import (
    texto_do_teto_do_orcamento,
)
from hefesto_dualsense4unix.core.rumble import teto_do_orcamento
from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "src" / "hefesto_dualsense4unix" / "app"

PCT_ECONOMIA = round(RUMBLE_POLICY_MULT["economia"] * 100)


class _Host:
    """O mínimo que a seção toca no hospedeiro."""

    def __init__(self, orcamento: str | None = None) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self._orcamento_lido = lambda: orcamento
        self._caixa: Any = None

    def _get(self, _ident: str) -> Any:
        return None


def _montar(host: _Host) -> Any:
    host._caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    secao_orcamento.montar(host, host._caixa)
    return host._caixa


def test_sem_declaracao_a_linha_nao_aparece() -> None:
    """"Não sei" não é "sem teto", e nenhum dos dois é "limitado"."""
    assert texto_do_teto_do_orcamento(RUMBLE_POLICY_MULT["max"], None) is None


@pytest.mark.parametrize("orcamento", ["balanceado", "max"])
def test_orcamento_sem_teto_nao_acende_a_linha(orcamento: str) -> None:
    """A dica dos dois promete "tudo como o jogo pedir, sem teto"."""
    assert texto_do_teto_do_orcamento(RUMBLE_POLICY_MULT["max"], orcamento) is None


def test_em_auto_a_linha_cala_porque_o_teto_e_movel() -> None:
    """MORDIDA 1. Em Auto o teto muda a cada tique com a bateria."""
    assert teto_do_orcamento("auto") is None
    assert texto_do_teto_do_orcamento(RUMBLE_POLICY_MULT["max"], "auto") is None


def test_a_linha_diz_o_pedido_e_o_teto_quando_o_teto_morde() -> None:
    """O formato aprovado: o que a aba pede, e a que ela chega limitada."""
    texto = texto_do_teto_do_orcamento(RUMBLE_POLICY_MULT["max"], "economia")
    assert texto is not None
    assert "150%" in texto
    assert f"{PCT_ECONOMIA}%" in texto
    assert "orçamento" in texto


def test_a_linha_cala_quando_o_teto_nao_morde() -> None:
    """MORDIDA 2. O que a aba mostra é o que chega: dizer "limitado" seria falso."""
    igual = texto_do_teto_do_orcamento(RUMBLE_POLICY_MULT["economia"], "economia")
    assert igual is None
    abaixo = texto_do_teto_do_orcamento(0.1, "economia")
    assert abaixo is None


def test_sem_saber_o_pedido_a_linha_cala() -> None:
    """Política fora dos degraus conhecidos, deslizador ainda não lido."""
    assert texto_do_teto_do_orcamento(None, "economia") is None


def test_o_percentual_da_linha_vem_do_dono_unico() -> None:
    """Nenhum número desta linha é digitado: todos derivam da tabela."""
    texto = texto_do_teto_do_orcamento(2.0, "economia")
    assert texto == f"200% · limitado a {PCT_ECONOMIA}% pelo orçamento"


def test_nenhum_modulo_de_app_recalcula_a_escada() -> None:
    """`RUMBLE_POLICY_MULT[...]` em `app/` só pode existir na cópia autorizada.

    A cópia autorizada é o `_POLICY_MULT` de `rumble_actions.py`, que deriva do
    dono único por desempacotamento (`{**RUMBLE_POLICY_MULT, "auto": 1.0}`) e
    não por índice. Qualquer indexação nova em `app/` é uma segunda conta.
    """
    achados = [
        f"{caminho.relative_to(RAIZ)}:{numero}"
        for caminho in sorted(APP.rglob("*.py"))
        for numero, linha in enumerate(
            caminho.read_text(encoding="utf-8").splitlines(), start=1
        )
        if "RUMBLE_POLICY_MULT[" in linha and not linha.lstrip().startswith("#")
    ]
    assert not achados, (
        "alguém passou a indexar a escada dentro de `app/` — a conta tem um "
        "dono, e ele mora no daemon:\n  " + "\n  ".join(achados)
    )


def test_a_dica_aprovada_diz_o_numero_que_o_produto_entrega() -> None:
    """A dica do botão Economia é texto aprovado, e por isso é literal."""
    assert (
        f"{PCT_ECONOMIA}%"
        in secao_orcamento.DICAS[secao_orcamento.PERFIL_BATERIA_LONGA]
    )


def test_o_clique_nao_grava_nada() -> None:
    """MORDIDA 3 (D-A4). Nada de IPC nem de disco no clique — só o rascunho."""
    fonte = Path(secao_orcamento.__file__).read_text(encoding="utf-8")
    codigo = "\n".join(
        linha for linha in fonte.splitlines() if not linha.lstrip().startswith("#")
    )
    for proibido in ("machine_declare", "gravar_maquina", "_safe_call"):
        assert proibido not in codigo, (
            f"a seção passou a chamar `{proibido}` — o gesto de gravar tem um "
            "dono, e é o 'Aplicar' do rodapé"
        )

    # `daemon.state_full`. Banir a palavra inteira empurraria essa leitura para
    # abaixo mede: toda chamada assíncrona desta seção nomeia `daemon.state_full`
    arvore = ast.parse(fonte)
    metodos = sorted(
        {
            no.args[0].value
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Name)
            and no.func.id == "call_async"
            and no.args
            and isinstance(no.args[0], ast.Constant)
            and isinstance(no.args[0].value, str)
        }
    )
    assert metodos == ["daemon.state_full"] or metodos == [], (
        "a seção passou a chamar um método IPC que não é a leitura do estado: "
        f"{metodos}. Ler é permitido e nomeado; escrever tem um dono, e é o "
        "'Aplicar' do rodapé"
    )
    chamadas = sum(
        1
        for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Name)
        and no.func.id == "call_async"
    )
    assert chamadas == len(metodos), (
        "há `call_async` cujo método não é literal — um método montado em "
        "tempo de execução escapa desta régua"
    )


def test_a_secao_le_o_gravado_e_nunca_o_pendente() -> None:
    """A aba de origem descreve o que o Hefesto aplica AGORA."""
    host = _Host("balanceado")
    host._maquina_pendente = {"orcamento": {"teto": "economia"}}
    assert secao_orcamento.orcamento_em_vigor(host) == "balanceado"


class TestOBotaoMostraOQueElaEscolheu:
    """Achado da conferência de 23/08/2026: a tela se contradizia."""

    def test_a_declaracao_pendente_vence_o_disco_no_botao(self) -> None:
        """MORDE: com `orcamento_em_vigor` no lugar, o botão mostra o disco."""
        host = _Host("economia")
        host._maquina_pendente = {"orcamento": {"teto": "max"}}

        assert secao_orcamento.orcamento_na_tela(host) == "max", (
            "o botão desta aba tem de mostrar o que ela acabou de escolher"
        )

    def test_o_nao_sei_pendente_apaga_o_botao_antigo(self) -> None:
        """MORDE: sem a função nova, o botão antigo volta afundado."""
        host = _Host("economia")
        host._maquina_pendente = {"orcamento": {"teto": None}}

        assert secao_orcamento.orcamento_na_tela(host) is None, (
            'escolher "Não sei" e remontar a aba trazia o botão antigo de volta'
        )

    def test_sem_pendencia_as_duas_concordam(self) -> None:
        """Sem declaração de pé, a tela e o vigor são a mesma coisa."""
        host = _Host("balanceado")
        host._maquina_pendente = None

        assert secao_orcamento.orcamento_na_tela(host) == "balanceado"
        assert secao_orcamento.orcamento_em_vigor(host) == "balanceado"

    def test_a_aba_rumble_continua_ignorando_o_pendente(self) -> None:
        """A razão de existirem DUAS funções, presa em teste."""
        host = _Host("balanceado")
        host._maquina_pendente = {"orcamento": {"teto": "max"}}

        assert secao_orcamento.orcamento_em_vigor(host) == "balanceado", (
            "a linha da aba Rumble descreve o que o daemon aplica AGORA"
        )
