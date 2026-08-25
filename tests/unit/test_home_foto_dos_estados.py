"""A aba Início tinha UMA foto, e cinco estados que ninguém nunca viu — I10.

INÍCIO NÃO MENTE-01, §2.4, medido em 24/08/2026: a
`docs/usage/assets/readme_inicio.png` é de hoje, mas os dois controles nela são
dublê escrito à mão dentro do `scripts/gui-captura/retratar_abas.py`. Esse
dublê não traz `paused`, nem `primary_grab_state`, nem `external`, nem
`steam_input`, nem `draft` — então **o aviso de grab, a pausa, o card de
externo, a exceção de Steam Input e a divergência de máscara nunca foram
fotografados**. A aba tem uma foto do caminho feliz e mais nada.

Isso importa porque a regra desta casa é *"interface só fecha com o olho dela"*,
com foto antes e depois (PROVA-DE-TELA-01). Uma prova de tela tirada sobre a
única foto que existe é prova sobre o caso que já estava certo.

A ARMADILHA QUE ESTE ARQUIVO EXISTE PARA NÃO REPETIR
-----------------------------------------------------

Em **14/08/2026**, com a mesa cheia, **nove dos dez PNGs saíram byte a byte
idênticos** aos de quando havia um controle só — e o instrumento era cego por
construção, não por defeito. A régua daqui é a mesma daquele dia, virada para o
outro lado: **cada estado nomeado tem de produzir um PNG DIFERENTE do caminho
feliz, byte a byte.** Se dois estados saem iguais, ou o produto não os
distingue, ou o instrumento não os alcança — e nos dois casos a foto não serve
de prova.

A ÚNICA saída dessa régua é a DECLARADA (25/08/2026): um estado que a aba, por
decisão medida, não distingue entra em `ESTADOS_SEM_EFEITO_NA_ABA`, no próprio
instrumento, com a razão datada — e passa a ser cobrado pela régua contrária,
que reprova se um dia ele sair diferente. Sem essa segunda régua, a declaração
seria a porta por onde a foto volta a não provar nada.

E a régua sabe RECUSAR (A2, "o dublê que só sabe passar"): o
`test_a_regua_sabe_dizer_que_dois_estados_sao_iguais` fotografa o caminho feliz
DUAS vezes e exige as duas somas idênticas. Sem ele, uma régua que sempre
achasse diferença passaria por severa.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. Contra o stub, o
# `savev` não existiria e a comparação de bytes mediria o nada.
exigir_gi_real("a foto dos estados da aba Início")

import functools
import hashlib
import importlib.util
import re
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

# CI headless sem libcairo cai no stub do card (sem sub-widgets de desenho).
pytest.importorskip("cairo")

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gui-captura" / "retratar_abas.py"

#: Toda razão declarada carrega data — mesma régua do portão do par
#: assimétrico e do `portao_a_casa_sabe_e_o_produto_nao_faz`.
_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")

#: Os cinco estados que a sprint nomeia como NUNCA fotografados, mais a mesa
#: vazia do §2.1 (o payload medido com zero controle na casa). O caminho feliz
#: não entra: ele é a régua, não um dos medidos.
_ESTADOS_QUE_TEM_DE_DIFERIR = (
    "em_pausa",
    "grab_falhou",
    "externo_na_mesa",
    "mascara_divergente",
    "mesa_vazia",
)

#: O `steam_input` saiu da lista acima em 25/08/2026 e não sumiu: ele passou
#: para `ESTADOS_SEM_EFEITO_NA_ABA`, no próprio instrumento, com a razão datada
#: e a régua CONTRÁRIA (`test_os_estados_declarados_iguais_saem_iguais`). A
#: exceção de Steam Input não muda a linha da Ponte porque, desde a
#: ESCONDER-EM-VEZ-DE-SAIR-01, quem alimenta o jogo durante ela continua sendo
#: o gamepad do Hefesto — ver o ramo 2 de `texto_da_ponte`.


@functools.lru_cache(maxsize=1)
def _script() -> Any:
    """Importa o script de retrato como módulo, sem rodar o `main`. UMA vez.

    O cache não é economia: é CORREÇÃO. O `_aplicar_tema` guarda em
    `_tema_ja_aplicado` (variável de MÓDULO) que o tema já foi aplicado nesta
    execução, porque `apply_theme` NÃO é idempotente — ele lê `gtk-font-name`,
    soma o delta de acessibilidade e grava de volta, então a segunda chamada
    soma sobre o já somado e a tipografia da tela inteira cresce um degrau.
    Importar o script duas vezes cria dois módulos, cada um com o seu
    `_tema_ja_aplicado` em `False`, e a segunda foto sai com fonte maior que a
    primeira — medido aqui em 25/08/2026, e é a mesma armadilha que a docstring
    do `_aplicar_tema` documenta para o cabeçalho.
    """
    assert SCRIPT.is_file(), f"{SCRIPT} sumiu — o retrato das abas é rotina desta casa"
    spec = importlib.util.spec_from_file_location("_retratar_abas_estados", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _nao_inflar_a_fonte_da_sessao(modulo: Any) -> None:
    """Impede que ESTE arquivo mude a tipografia do resto da suíte.

    MEDIDO em 25/08/2026, e é a armadilha *"o instrumento pode estar brigando
    com o produto"*: `app.theme.apply_theme` NÃO é idempotente — ele lê
    `gtk-font-name` do `Gtk.Settings` (que é da TELA, não da janela), soma o
    delta de acessibilidade e grava de volta. Uma aplicação a mais no processo
    e a fonte da sessão inteira sobe um degrau.

    O preço apareceu longe daqui:
    `test_largura_a_mesma_em_todas_as_abas.py::test_no_tamanho_de_projeto_o_teto_nao_entra_em_acao[tab_home_box]`
    passou a reprovar com **1400 px contra 1646** — um teste de LARGURA
    quebrado por um teste de FOTO, dois arquivos adiante, sem nenhuma relação
    entre eles.

    A cura usa o mecanismo que o próprio script já tem: `_tema_ja_aplicado`
    ligado faz `_aplicar_tema` marcar só a classe da janela e não tocar no
    `Gtk.Settings`. As fotos daqui saem sem o CSS do produto — e isso não
    enfraquece nada, porque o que este arquivo mede é a DIFERENÇA entre elas, e
    todas recebem exatamente o mesmo tratamento. Quem grava as fotos que vão ao
    repositório é o script, rodado à parte, com o tema inteiro.
    """
    modulo._tema_ja_aplicado = True


def _soma(arquivo: Path) -> str:
    return hashlib.sha256(arquivo.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def _somas(tmp_path_factory: Any) -> dict[str, str]:
    """Fotografa TODOS os estados uma vez e devolve `{nome: sha256}`.

    Escopo de módulo porque cada estado custa uma janela offscreen e uma espera
    de relógio de 1 s (o resize da superfície só chega no tique do frame clock,
    e `Gtk.events_pending()` não o alcança) — refazer isso por teste levaria a
    suíte a minutos sem medir nada a mais.
    """
    modulo = _script()
    _nao_inflar_a_fonte_da_sessao(modulo)
    modulo._desligar_animacoes()
    saida = tmp_path_factory.mktemp("estados-do-inicio")
    somas: dict[str, str] = {}
    for nome in modulo.ESTADOS_DO_INICIO:
        arquivo, _recado = modulo._fotografar_um_estado_do_inicio(saida, nome)
        somas[nome] = _soma(arquivo)
    return somas


def test_os_cinco_estados_nunca_fotografados_estao_no_instrumento() -> None:
    """O instrumento CONHECE os cinco, e cada um diz o que passou a mostrar.

    Sem esta lista o modo `--estados-do-inicio` viraria um punhado de fotos sem
    contrato: quem rodasse não saberia o que estava olhando, e o próximo a
    mexer removeria um estado sem que nada acusasse.
    """
    modulo = _script()
    conhecidos = modulo.ESTADOS_DO_INICIO

    assert "caminho_feliz" in conhecidos, (
        "sem o caminho feliz não há régua: a prova destes estados é serem "
        "DIFERENTES dele"
    )
    faltando = [n for n in _ESTADOS_QUE_TEM_DE_DIFERIR if n not in conhecidos]
    assert not faltando, (
        f"o instrumento deixou de alcançar {faltando}. São estados que a sprint "
        "INÍCIO NÃO MENTE-01 nomeia como nunca fotografados (§2.4) — tirá-los "
        "devolve a aba à foto única do caminho feliz."
    )
    for nome, (_delta, _mascara, oque) in conhecidos.items():
        assert isinstance(oque, str) and len(oque) > 20, (
            f"o estado {nome!r} não diz o que passou a mostrar. A frase é o que "
            "o recibo imprime; sem ela a foto não se explica sozinha."
        )


def test_cada_estado_produz_uma_foto_diferente_do_caminho_feliz(
    _somas: dict[str, str],
) -> None:
    """A mordida. Em 14/08 nove de dez PNGs saíram idênticos e ninguém viu.

    Estado que sai igual ao caminho feliz é estado que a foto NÃO prova: ou o
    produto não o distingue (defeito de tela), ou o instrumento não o alcança
    (defeito de régua). Os dois valem vermelho aqui — a foto é a prova de tela
    desta onda, e prova que não distingue nada não é prova.
    """
    referencia = _somas["caminho_feliz"]
    iguais = [
        nome
        for nome in _ESTADOS_QUE_TEM_DE_DIFERIR
        if _somas.get(nome) == referencia
    ]
    assert not iguais, (
        f"estes estados da aba Início saíram byte a byte IGUAIS ao caminho "
        f"feliz: {iguais}. A tela não os distingue — é o defeito de 14/08/2026 "
        "de novo, com os papéis trocados: lá o instrumento era cego, aqui é a "
        "aba que não fala. Cada nome desta lista é uma tarefa da sprint INÍCIO "
        "NÃO MENTE-01 que ainda não entrou."
    )


def test_os_estados_declarados_iguais_saem_iguais(_somas: dict[str, str]) -> None:
    """A régua contrária — e ela é o que impede a declaração de virar desculpa.

    Um estado só sai da régua da diferença DECLARADO em
    `ESTADOS_SEM_EFEITO_NA_ABA`, com razão datada. Este teste cobra o outro
    lado: se a aba passar a distinguir o estado, a foto muda, este teste
    reprova, e quem mexeu é obrigado a devolver o nome à régua da diferença em
    vez de deixar uma declaração que virou mentira.

    É a mesma disciplina do `_PAR_ACEITO` do portão do par assimétrico
    (`test_nenhuma_declaracao_ficou_obsoleta`): declaração sem régua que a
    derrube envelhece em silêncio.
    """
    modulo = _script()
    declarados = modulo.ESTADOS_SEM_EFEITO_NA_ABA
    referencia = _somas["caminho_feliz"]

    desconhecidos = [n for n in declarados if n not in modulo.ESTADOS_DO_INICIO]
    assert not desconhecidos, (
        f"declarados como sem efeito e ausentes do instrumento: {desconhecidos}"
    )
    for nome, razao in declarados.items():
        assert _DATA.search(razao), (
            f"a razão de {nome!r} não tem data. Razão sem idade vira paisagem — "
            "é a régua que esta casa já escreveu duas vezes."
        )
    diferentes = [n for n in declarados if _somas.get(n) != referencia]
    assert not diferentes, (
        f"estes estados foram DECLARADOS sem efeito na aba e a foto mostra "
        f"outra coisa: {diferentes}. A aba passou a distingui-los — mova o nome "
        "para `_ESTADOS_QUE_TEM_DE_DIFERIR` e apague a declaração, senão a "
        "razão datada fica no disco afirmando o que a tela já desmente."
    )


def test_a_regua_sabe_dizer_que_dois_estados_sao_iguais(
    tmp_path: Path, _somas: dict[str, str]
) -> None:
    """Régua que só sabe achar diferença não é régua (A2, 23/08/2026).

    Fotografa o caminho feliz uma SEGUNDA vez, numa janela nova, e exige a
    mesma soma. Isso prova as duas coisas de que o teste acima depende: que a
    foto é determinística (as animações do GTK estão desligadas — ver o
    cabeçalho do script) e que somas iguais são alcançáveis.
    """
    modulo = _script()
    _nao_inflar_a_fonte_da_sessao(modulo)
    modulo._desligar_animacoes()
    arquivo, _recado = modulo._fotografar_um_estado_do_inicio(
        tmp_path, "caminho_feliz"
    )
    assert _soma(arquivo) == _somas["caminho_feliz"], (
        "duas fotos do MESMO estado saíram diferentes. Enquanto isso for "
        "verdade, o teste da diferença acima passa por acaso e não mede nada — "
        "é a armadilha das animações do GTK, documentada no cabeçalho do "
        "`retratar_abas.py`."
    )


def test_o_estado_do_externo_vem_do_fixture_versionado() -> None:
    """Nada de endereço digitado neste script: o externo sai de `tests/`.

    O portão de anonimato **não varre imagens**, e esta foto vai para o
    repositório. O único dado seguro é o que já passou pelos portões de
    `tests/`, que são allowlist de PREFIXO — mais severos que a máscara de
    `docs/`.
    """
    modulo = _script()
    externo = modulo._um_externo_versionado()

    assert externo, (
        "o inventário versionado de externos sumiu. Sem ele o estado "
        "`externo_na_mesa` teria de trazer um endereço escrito à mão aqui — e "
        "endereço escrito no script é endereço que portão nenhum confere."
    )
    endereco = str(externo.get("uniq") or "")
    assert endereco.startswith(("aa:bb:cc", "e8:47:3a", "02:fe:00")), (
        f"o `uniq` {endereco!r} não está numa das faixas forjadas desta casa. "
        "A foto o publicaria numa imagem que nenhum portão varre."
    )


def test_a_pasta_dos_estados_nao_e_a_da_documentacao() -> None:
    """As fotos de medição não podem cair em `docs/usage/assets/`.

    Mesma razão da mesa cheia: aquelas dez imagens são as do README e do guia
    da interface, e o portão da procedência
    (`test_as_fotos_acompanham_a_versao.py`) mede pelo último commit que tocou
    a pasta — uma foto de medição lá dentro daria as do README por conferidas
    sem ninguém as ter regerado.
    """
    modulo = _script()
    destino = modulo.DESTINO_ESTADOS_DO_INICIO

    assert destino != modulo.DESTINO_DOC
    assert not str(destino).startswith(str(modulo.DESTINO_DOC))
    assert destino.is_relative_to(RAIZ / "docs" / "process" / "estudos" / "assets"), (
        f"as fotos dos estados foram parar em {destino}. A convenção das "
        "medições desta casa é `docs/process/estudos/assets/`."
    )
