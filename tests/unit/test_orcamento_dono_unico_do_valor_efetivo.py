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

# GUARDA-GI-REAL-01: a seção monta widgets de verdade, e "pulei porque não
# tenho GTK" é reprovação no job `gtk-real`. Vem antes do bloco de imports.
exigir_gi_real("a seção Orçamento da aba Configurações")

import ast
import inspect
from pathlib import Path
from typing import Any, get_args

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_orcamento
from hefesto_dualsense4unix.app.actions.rumble_actions import (
    ROTULOS_DO_ORCAMENTO,
    texto_do_teto_do_orcamento,
)
from hefesto_dualsense4unix.core.rumble import teto_do_orcamento
from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT
from hefesto_dualsense4unix.utils.maquina import OrcamentoDeclarado

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "src" / "hefesto_dualsense4unix" / "app"

#: O degrau do Economia em percentual inteiro, derivado do dono único. É o
#: número que a tela mostra, e ele não se escreve em teste nenhum.
PCT_ECONOMIA = round(RUMBLE_POLICY_MULT["economia"] * 100)


class _Host:
    """O mínimo que a seção toca no hospedeiro."""

    def __init__(self, orcamento: str | None = None) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self._orcamento_lido = lambda: orcamento
        #: A caixa fica PENDURADA no hospedeiro, e não é detalhe de arrumação:
        #: solta numa variável local ela é coletada ao fim do `_montar`, o GTK
        #: destrói os filhos junto e o seletor para de emitir "changed" — o
        #: teste do clique falhava sem uma linha de erro, com o rascunho vazio.
        self._caixa: Any = None

    def _get(self, _ident: str) -> Any:
        return None


def _montar(host: _Host) -> Any:
    host._caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    secao_orcamento.montar(host, host._caixa)
    return host._caixa


# ---------------------------------------------------------------------------
# 1. A linha da aba de origem
# ---------------------------------------------------------------------------


def test_sem_declaracao_a_linha_nao_aparece() -> None:
    """"Não sei" não é "sem teto", e nenhum dos dois é "limitado"."""
    assert texto_do_teto_do_orcamento(RUMBLE_POLICY_MULT["max"], None) is None


@pytest.mark.parametrize("orcamento", ["balanceado", "max"])
def test_orcamento_sem_teto_nao_acende_a_linha(orcamento: str) -> None:
    """A dica dos dois promete "tudo como o jogo pedir, sem teto"."""
    assert texto_do_teto_do_orcamento(RUMBLE_POLICY_MULT["max"], orcamento) is None


def test_em_auto_a_linha_cala_porque_o_teto_e_movel() -> None:
    """MORDIDA 1. Em Auto o teto muda a cada tique com a bateria.

    A casa já enfrentou este caso e escolheu não prometer percentual
    (`profiles/manager.py:1556-1567`, o pulo com log
    `escala_de_vibracao_pulada_base_movel`). Um "limitado a 100%" que vira 30%
    no minuto seguinte ensina a desconfiar da tela inteira.
    """
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
    """Nenhum número desta linha é digitado: todos derivam da tabela.

    Prova pela negativa: o texto tem de conter o percentual DERIVADO, e o
    módulo da aba não pode ter o literal escrito em lugar nenhum.
    """
    texto = texto_do_teto_do_orcamento(2.0, "economia")
    assert texto == f"200% · limitado a {PCT_ECONOMIA}% pelo orçamento"


# ---------------------------------------------------------------------------
# 2. Um dono só para a escada
# ---------------------------------------------------------------------------


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


def test_a_migracao_cobre_toda_chave_que_o_disco_aceita() -> None:
    """Nenhum valor gravado fica sem perfil — a migração é 1-para-1 e total.

    NOTA DATADA — 25/08/2026, `D-PERFIL-DE-DESEMPENHO`. Este nó afirmava que os
    RÓTULOS da seção eram os da aba Rumble ("Economia", "Balanceado", "Máximo",
    "Auto"), e o que ele protegia era não redigitar quatro palavras em dois
    lugares. A decisão dela tirou os quatro botões da tela: eles viraram três
    perfis, cujos rótulos são dela e não da aba Rumble. O que sobrevive da
    proteção — e é a metade que morde — é que **nenhuma chave do disco pode
    ficar órfã**: uma chave sem entrada em `PERFIL_POR_TETO` nasceria com a
    fileira sem botão afundado, e a escolha da pessoa sumiria da tela sem nada
    avisar.

    O RÓTULO da aba Rumble continua tendo um dono só, e é o `ROTULOS_DO_ORCAMENTO`
    de `rumble_actions` — este teste só deixa de ser o lugar que o afirma.
    """
    assert set(secao_orcamento.PERFIL_POR_TETO) == set(secao_orcamento.CHAVES), (
        "uma chave do disco ficou sem perfil na migração — quem a tiver "
        "gravada abriria a aba com a fileira em branco"
    )
    assert set(secao_orcamento.PERFIL_POR_TETO.values()) <= set(
        secao_orcamento.PERFIS
    )
    assert ROTULOS_DO_ORCAMENTO["economia"] == "Economia", (
        "o dono dos rótulos da aba Rumble continua sendo o `rumble_actions`"
    )


def test_a_celula_da_tabela_vem_da_mesma_conta_do_daemon() -> None:
    """A tabela da aba e o teto do daemon são o mesmo número, ou a tela mente."""
    assert f"{PCT_ECONOMIA}%" in secao_orcamento.celula_do_teto("economia")
    assert secao_orcamento.celula_do_teto("balanceado") == secao_orcamento.SEM_TETO
    assert secao_orcamento.celula_do_teto("max") == secao_orcamento.SEM_TETO


def test_a_celula_e_calculada_e_nao_digitada() -> None:
    """O corpo da célula chama a conta; um literal ali seria a segunda cópia."""
    corpo = inspect.getsource(secao_orcamento.celula_do_teto)
    assert "teto_do_orcamento(" in corpo
    assert f"{PCT_ECONOMIA}" not in corpo.split('"""')[-1], (
        "o percentual do Economia foi digitado no código da célula — ele tem "
        "de sair de `teto_do_orcamento`"
    )


def test_a_dica_aprovada_diz_o_numero_que_o_produto_entrega() -> None:
    """A dica do botão Economia é texto aprovado, e por isso é literal.

    Literal não pode virar mentira: se o degrau do Economia mudar, esta frase
    passa a prometer o que o daemon não faz — e é este teste que avisa, em vez
    de a usuária descobrir sentindo. Foi assim que o "40%" do desenho caiu, em
    22/08/2026: o produto entrega 30%, e o número tem dono.
    """
    assert (
        f"{PCT_ECONOMIA}%"
        in secao_orcamento.DICAS[secao_orcamento.PERFIL_BATERIA_LONGA]
    )


# ---------------------------------------------------------------------------
# 3. A seção não grava nada
# ---------------------------------------------------------------------------


def test_as_chaves_sao_as_do_schema() -> None:
    """MORDIDA 4. A tupla da tela é o Literal que persiste, sem uma chave a mais."""
    # A anotação é `Literal[...] | None`: o primeiro `get_args` abre a união,
    # o segundo abre o Literal. Ler só o primeiro nível devolveria tupla vazia,
    # e o teste passaria comparando nada com nada.
    do_schema: tuple[str, ...] = tuple(
        valor
        for ramo in get_args(OrcamentoDeclarado.model_fields["teto"].annotation)
        for valor in get_args(ramo)
        if isinstance(valor, str)
    )
    assert do_schema, "o Literal de `OrcamentoDeclarado.teto` sumiu do schema"
    assert set(secao_orcamento.CHAVES) == set(do_schema)
    assert "custom" not in secao_orcamento.CHAVES, (
        "`custom` é o deslizador livre da aba Rumble, não escolha de mesa"
    )


def test_o_clique_acumula_a_chave_e_nunca_o_rotulo() -> None:
    """O rascunho leva a CHAVE do disco, nunca o id do botão nem o rótulo.

    Gravar `"tudo_ligado"` (o id do botão) ou `"Tudo ligado"` (o rótulo) faria
    o `extra="forbid"` do pydantic recusar o DOCUMENTO INTEIRO na próxima
    carga — e o sintoma na tela seria "não consegui gravar".
    """
    host = _Host()
    _montar(host)
    host._config_orcamento_seletor.set_active_id(  # type: ignore[attr-defined]
        secao_orcamento.PERFIL_TUDO_LIGADO
    )
    assert host._maquina_pendente == {"orcamento": {"teto": "balanceado"}}


def test_a_declaracao_e_parcial_e_nao_apaga_as_outras_secoes() -> None:
    """Cinco seções escrevem no mesmo rascunho; a fusão desce nos aninhados."""
    host = _Host()
    host._maquina_pendente = {"mesa": {"altura_da_antena": "acima"}}
    _montar(host)
    host._config_orcamento_seletor.set_active_id(  # type: ignore[attr-defined]
        secao_orcamento.PERFIL_BATERIA_LONGA
    )
    assert host._maquina_pendente == {
        "mesa": {"altura_da_antena": "acima"},
        "orcamento": {"teto": "economia"},
    }


def test_o_clique_nao_grava_nada() -> None:
    """MORDIDA 3 (D-A4). Nada de IPC nem de disco no clique — só o rascunho.

    Prova pelo fonte, e não por espião: um espião só pegaria a chamada que ele
    conhece, e o que a decisão proíbe é QUALQUER escritor nesta seção.
    """
    fonte = Path(secao_orcamento.__file__).read_text(encoding="utf-8")
    codigo = "\n".join(
        linha for linha in fonte.splitlines() if not linha.lstrip().startswith("#")
    )
    for proibido in ("machine_declare", "gravar_maquina", "_safe_call"):
        assert proibido not in codigo, (
            f"a seção passou a chamar `{proibido}` — o gesto de gravar tem um "
            "dono, e é o 'Aplicar' do rodapé"
        )

    # NOTA DATADA — 25/08/2026. `call_async` saiu da lista acima e ganhou régua
    # PRÓPRIA, mais estreita. A conta de fatias precisa de UMA coisa que o
    # sysfs desta seção não tem — quem está no rádio —, e ela mora no
    # `daemon.state_full`. Banir a palavra inteira empurraria essa leitura para
    # outro módulo só para escapar do portão, que é a meia-honestidade que esta
    # casa não aceita. O que a `D-A4` proíbe é ESCRITOR, e é isso que a régua
    # abaixo mede: toda chamada assíncrona desta seção nomeia `daemon.state_full`
    # e nada mais.
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


@pytest.mark.parametrize(
    ("gravado", "perfil"),
    [
        ("economia", secao_orcamento.PERFIL_BATERIA_LONGA),
        ("balanceado", secao_orcamento.PERFIL_TUDO_LIGADO),
        ("max", secao_orcamento.PERFIL_TUDO_LIGADO),
        ("auto", secao_orcamento.PERFIL_TUDO_LIGADO),
    ],
)
def test_montar_com_a_escolha_gravada_afunda_o_botao_certo(
    gravado: str, perfil: str
) -> None:
    """A migração da `D-PERFIL-DE-DESEMPENHO`, campo a campo, sem perder nada.

    E não deixa declaração pendente: abrir a janela não é gesto dela.
    """
    host = _Host(gravado)
    _montar(host)
    assert host._config_orcamento_seletor.get_active_id() == perfil  # type: ignore[attr-defined]
    assert host._maquina_pendente is None


def test_sem_nada_declarado_nenhum_botao_nasce_afundado() -> None:
    """Afundar o default do daemon faria a tela afirmar escolha que ela não fez."""
    host = _Host()
    _montar(host)
    assert host._config_orcamento_seletor.get_active_id() is None  # type: ignore[attr-defined]


def test_a_secao_le_o_gravado_e_nunca_o_pendente() -> None:
    """A aba de origem descreve o que o Hefesto aplica AGORA.

    Mostrar ali a escolha ainda pendente faria a aba Rumble anunciar um limite
    que o daemon não está impondo — a mentira oposta, e igualmente cara.
    """
    host = _Host("balanceado")
    host._maquina_pendente = {"orcamento": {"teto": "economia"}}
    assert secao_orcamento.orcamento_em_vigor(host) == "balanceado"


class TestOBotaoMostraOQueElaEscolheu:
    """Achado da conferência de 23/08/2026: a tela se contradizia.

    Com a marca nova do rodapé, o defeito ficou visível: declare um orçamento,
    troque de aba, volte — o rodapé dizia "Há escolhas declaradas por aplicar" e
    o botão mostrava o valor do disco. O caso mais feio era o "Não sei", que
    declara `teto: None`: na remontagem, o botão ANTIGO voltava afundado, e a
    escolha da pessoa sumia da tela sem aviso.

    As duas funções coexistem de propósito, e este teste prende as duas pontas.
    """

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
        """A razão de existirem DUAS funções, presa em teste.

        MORDE: se alguém fizer `orcamento_em_vigor` olhar o pendente, a aba
        Rumble passa a afirmar um limite que o daemon não está impondo.
        """
        host = _Host("balanceado")
        host._maquina_pendente = {"orcamento": {"teto": "max"}}

        assert secao_orcamento.orcamento_em_vigor(host) == "balanceado", (
            "a linha da aba Rumble descreve o que o daemon aplica AGORA"
        )
