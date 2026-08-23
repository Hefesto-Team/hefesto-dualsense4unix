"""A coluna "O que é" nasce preenchida pelo kernel, e ela só corrige.

O DEFEITO, medido em 22/08/2026: `integrations/censo_do_barramento.py` nasceu
naquele dia, lê `bInterfaceClass/SubClass/Protocol` da interface 0 e distingue
mouse (`03/01/02`) de teclado (`03/01/01`) sem perguntar nada a ninguém — e
tinha **zero consumidores em `app/`**. A tela ao lado, na mesma sessão, oferecia
SETE botões por linha perguntando à mão o que o kernel já respondia.

É a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` acontecendo dentro da sessão que a
documentou, pela segunda vez no mesmo dia (a primeira foi o `TODO(CONFIG-03)`
que sobreviveu à camada que esperava).

A decisão dela: *"classifica sozinho, você só corrige"*.

O QUE ESTE PORTÃO COBRA — os três degraus da precedência, e um quarto item que
é sobre a régua:

1. **o kernel vence o botão vazio.** Linha que o barramento classificou nasce
   com a palavra e o selo `(lido)`, e sem seletor nenhum;
2. **a correção dela vence o kernel.** `RadioDeclarado.tipo` gravado manda,
   mesmo quando o barramento respondeu outra coisa;
3. **onde ninguém sabe, o seletor abre sozinho** — a classe `ff`, em que o
   fabricante declinou de classificar. E "Corrigir" reabre o seletor numa linha
   já respondida, que é o outro meio-caminho do desenho dela;
4. **a junção é pelo `no`,** o caminho no sysfs, e nunca pelo `vid:pid`: duas
   unidades do mesmo aparelho têm o mesmo `vid:pid` e classes que podem
   divergir (um dongle de teclado e um de mouse do mesmo fabricante).

E o quinto, que é de privacidade: durante uma captura a seção **não varre o
barramento desta máquina**.
"""
from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("a coluna 'O que é' da seção A mesa")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    GRAU_DESCONHECIDO,
    GRAU_LIDO,
    Aparelho,
    Censo,
)
from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa, RadioUsb
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

#: Os dois nós da bancada. Aparelhos inventados: um teclado que o kernel sabe
#: nomear e um rádio de classe `ff`, que é o caso do Wi-Fi Realtek dela.
_NO_TECLADO = "/bancada/usb1/1-3"
_NO_MUDO = "/bancada/usb1/1-4"


class _Hospedeiro:
    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None


def _mesa() -> Mesa:
    return Mesa(
        radios=(
            RadioUsb(no=_NO_TECLADO, vid="1d57", pid="fa20", busnum=1, devpath="3"),
            RadioUsb(no=_NO_MUDO, vid="0bda", pid="b812", busnum=1, devpath="4"),
        )
    )


def _censo() -> Censo:
    """O kernel nomeia o primeiro e declina do segundo — os dois graus."""
    return Censo(
        aparelhos=(
            Aparelho(
                no=_NO_TECLADO,
                nome_do_kernel="1-3",
                vid="1d57",
                pid="fa20",
                classe="03",
                subclasse="01",
                protocolo="01",
                especie="Teclado",
                grau=GRAU_LIDO,
            ),
            Aparelho(
                no=_NO_MUDO,
                nome_do_kernel="1-4",
                vid="0bda",
                pid="b812",
                classe="ff",
                subclasse="ff",
                protocolo="ff",
                especie="Não identificado",
                grau=GRAU_DESCONHECIDO,
            ),
        )
    )


def _montar(
    host: Any,
    *,
    mesa: Mesa | None = None,
    censo: Censo | None = None,
    gravado: dict[str, Any] | None = None,
) -> tuple[Gtk.Box, Any]:
    """Monta a seção sobre a bancada, sem tocar no `/sys` desta máquina."""
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    painel = secao_mesa._PainelDaMesa(host)
    painel._ler = lambda: _mesa() if mesa is None else mesa  # type: ignore[method-assign]
    painel._ler_o_censo = lambda: _censo() if censo is None else censo  # type: ignore[method-assign]
    painel._pedir_o_estado = lambda: None  # type: ignore[method-assign]
    original = secao_mesa.carregar_maquina
    secao_mesa.carregar_maquina = lambda: MaquinaConfig.model_validate(gravado or {})  # type: ignore[assignment]
    try:
        painel.montar(caixa)
    finally:
        secao_mesa.carregar_maquina = original  # type: ignore[assignment]
    return caixa, painel


def _textos(raiz: Any) -> list[str]:
    """Todo texto da seção FORA dos botões segmentados.

    O seletor tem um botão escrito "Teclado" e outro "Mouse" — as mesmas
    palavras que a coluna usa para AFIRMAR. Sem esta exclusão, "a tela mostra
    Teclado" passaria com a tela só perguntando, que é exatamente o estado que
    esta leva veio tirar do produto.
    """
    achados: list[str] = []

    def _andar(widget: Any) -> None:
        if isinstance(widget, SegmentedSelector):
            return
        if isinstance(widget, Gtk.Label):
            achados.append(widget.get_text())
        obter = getattr(widget, "get_children", None)
        if obter is not None:
            for filho in obter():
                _andar(filho)

    _andar(raiz)
    return achados


def _seletores(raiz: Any) -> list[Any]:
    achados: list[Any] = []

    def _andar(widget: Any) -> None:
        if isinstance(widget, SegmentedSelector):
            achados.append(widget)
        obter = getattr(widget, "get_children", None)
        if obter is not None:
            for filho in obter():
                _andar(filho)

    _andar(raiz)
    return achados


# --- 1. O kernel vence o botão vazio ---------------------------------------


def test_a_linha_que_o_barramento_classificou_nasce_com_a_palavra() -> None:
    """"Teclado" e o selo `(lido)` na tela, sem ninguém ter respondido nada.

    Mordida: fazer `_celula_do_que_e` devolver sempre `_seletor_do_tipo` — a
    palavra some da tela e este teste reprova.
    """
    caixa, _ = _montar(_Hospedeiro())
    textos = _textos(caixa)

    assert "Teclado" in textos, (
        "a coluna 'O que é' não mostrou o que o barramento respondeu; a tela "
        f"continua perguntando o que a máquina já sabe. Textos: {textos}"
    )
    assert secao_mesa._SELO_LIDO in textos, (
        "a palavra apareceu sem o selo de procedência. Sem ele a tela afirma "
        "'Teclado' e não diz quem afirmou — é o mesmo defeito que o medidor "
        "desta seção já tinha pago com o 'derivado da especificação'."
    )


def test_a_linha_lida_nao_gasta_seletor_e_a_muda_gasta() -> None:
    """UM seletor de rádio na mesa de dois, e é o do aparelho que não se declara.

    A régua é a CONTAGEM contra fonte independente do widget: dois seletores de
    declaração (altura e visada) mais um por linha que ninguém classificou.
    Bastasse "existe algum seletor", o teste passaria com a coluna inteira do
    jeito velho — sete botões em toda linha.

    Mordida: apagar o degrau do `GRAU_LIDO` em `_celula_do_que_e`.
    """
    caixa, _ = _montar(_Hospedeiro())

    achados = _seletores(caixa)
    assert len(achados) == 3, (
        f"a seção tem {len(achados)} seletores e devia ter 3: dois de "
        "declaração mais UM 'O que é' — só a linha de classe `ff`. Uma linha "
        "que o barramento já classificou não pergunta nada."
    )
    ids = {ident for ident, _ in secao_mesa._TIPOS_DE_RADIO}
    assert ids.issubset(
        {botao for sel in achados[2:] for botao, _ in secao_mesa._TIPOS_DE_RADIO}
    )


def test_a_linha_muda_diz_que_ninguem_sabe() -> None:
    """O `▲` mora na linha de classe `ff`, e só nela.

    Mordida: tirar o `pack_start` do aviso em `_celula_do_que_e`.
    """
    caixa, _ = _montar(_Hospedeiro())
    textos = _textos(caixa)

    assert secao_mesa._AVISO_NAO_SABE in textos, (
        "a única linha que precisa dela não avisa que precisa. Sem o aviso, o "
        "seletor aberto parece defeito da tela em vez de pergunta."
    )
    assert textos.count(secao_mesa._AVISO_NAO_SABE) == 1, (
        "o aviso apareceu em mais de uma linha; ele é sobre a AUSÊNCIA de "
        f"resposta, e há uma só. Contagem: {textos.count(secao_mesa._AVISO_NAO_SABE)}"
    )


# --- 2. A correção dela vence o kernel -------------------------------------


def test_o_que_ela_declarou_vence_o_que_o_barramento_leu() -> None:
    """Ela disse "Caixa de som"; o kernel tinha dito "Teclado". Vale o dela.

    Mordida: consultar o censo ANTES do gravado em `_celula_do_que_e`.
    """
    caixa, _ = _montar(
        _Hospedeiro(),
        gravado={"mesa": {"radios": {"1d57:fa20": {"tipo": "caixa_de_som"}}}},
    )
    textos = _textos(caixa)

    assert "Caixa de som" in textos, (
        "a correção dela sumiu da tela. O kernel sabe a CLASSE do aparelho; "
        f"ela sabe o aparelho. Textos: {textos}"
    )
    assert "Teclado" not in textos, (
        "as duas respostas estão na tela ao mesmo tempo — quem lê tem de "
        "escolher entre duas afirmações sobre a mesma linha"
    )
    assert secao_mesa._SELO_DECLARADO in textos, (
        "a resposta dela apareceu com o selo de quem NÃO respondeu, ou sem "
        "selo. Os três degraus têm de ser distinguíveis na tela"
    )


def test_o_espelho_de_leitura_guarda_o_tipo_da_linha_sem_seletor() -> None:
    """`radios_declarados` não pode depender de QUAL widget foi desenhado.

    Este é o defeito que a leva de 22/08 criou e curou no mesmo passo: o
    espelho era preenchido dentro de `_seletor_do_tipo`, e a linha classificada
    pelo barramento não desenha seletor nenhum — o tipo gravado sumia.

    Mordida: devolver a linha `self.radios_declarados[...] = ...` para dentro
    de `_seletor_do_tipo`.
    """
    _, painel = _montar(
        _Hospedeiro(),
        gravado={"mesa": {"radios": {"1d57:fa20": {"tipo": "caixa_de_som"}}}},
    )

    assert painel.radios_declarados.get("1d57:fa20") == "caixa_de_som", (
        "o espelho de leitura da seção não conhece a declaração dela nesta "
        f"linha. Espelho: {painel.radios_declarados!r}"
    )


# --- 3. "Corrigir" reabre a pergunta ---------------------------------------


def test_corrigir_abre_o_seletor_na_linha_ja_respondida() -> None:
    """O outro meio do desenho: *"o seletor só aparece quando ela clicar".*

    Mordida: fazer `_ao_corrigir` não redesenhar (ou não guardar a chave).
    """
    host = _Hospedeiro()
    caixa, painel = _montar(host)
    antes = len(_seletores(caixa))

    painel._ao_corrigir(None, "1d57:fa20")

    depois = len(_seletores(caixa))
    assert depois == antes + 1, (
        f"clicar em '{secao_mesa._BOTAO_CORRIGIR}' não abriu o seletor: "
        f"{antes} seletores antes, {depois} depois"
    )
    assert "Teclado" not in _textos(caixa), (
        "a palavra do barramento continua na tela ao lado do seletor aberto — "
        "a linha passa a afirmar e a perguntar a mesma coisa"
    )


def test_corrigir_nao_grava_nada_por_si() -> None:
    """Abrir a pergunta não é responder.

    Mordida: chamar `_acumular` de dentro de `_ao_corrigir`.
    """
    host = _Hospedeiro()
    _, painel = _montar(host)

    painel._ao_corrigir(None, "1d57:fa20")

    assert host._maquina_pendente is None, (
        "só abrir o seletor já deu ao rodapé o que 'Aplicar'. Rascunho: "
        f"{host._maquina_pendente!r}"
    )


# --- 4. A junção é pelo nó, nunca pelo `vid:pid` ---------------------------


def test_duas_unidades_do_mesmo_vid_pid_nao_herdam_a_classe_uma_da_outra() -> None:
    """Mesmo `vid:pid`, nós diferentes, classes diferentes.

    É o caso real de qualquer casa com dois receptores do mesmo fabricante — e
    é o que separa uma junção certa de uma que "funciona na bancada". O
    `vid:pid` é a chave do que ELA declara (a resposta não muda com a porta);
    o `no` é a chave do que o kernel leu.

    Mordida: trocar `self._censo.aparelho(radio.no)` por uma busca por
    `vid`/`pid` — as duas linhas passam a dizer "Teclado".
    """
    outro = "/bancada/usb1/1-5"
    mesa = Mesa(
        radios=(
            RadioUsb(no=_NO_TECLADO, vid="1d57", pid="fa20", busnum=1, devpath="3"),
            RadioUsb(no=outro, vid="1d57", pid="fa20", busnum=1, devpath="5"),
        )
    )
    censo = Censo(
        aparelhos=(
            Aparelho(
                no=_NO_TECLADO,
                nome_do_kernel="1-3",
                vid="1d57",
                pid="fa20",
                especie="Teclado",
                grau=GRAU_LIDO,
            ),
            Aparelho(
                no=outro,
                nome_do_kernel="1-5",
                vid="1d57",
                pid="fa20",
                especie="Mouse",
                grau=GRAU_LIDO,
            ),
        )
    )
    caixa, _ = _montar(_Hospedeiro(), mesa=mesa, censo=censo)
    textos = _textos(caixa)

    assert "Teclado" in textos and "Mouse" in textos, (
        "duas unidades do mesmo `vid:pid` saíram com a mesma palavra: a junção "
        f"está sendo feita pela chave errada. Textos: {textos}"
    )


# --- 5. A foto não varre o barramento dela ---------------------------------


def test_durante_a_captura_a_secao_nao_le_o_barramento_desta_maquina(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem o dublê do censo, uma captura tem de sair com censo VAZIO.

    A foto entra em `docs/usage/assets/` sem revisão humana e nenhum portão
    desta casa varre imagem (F5). A espécie de cada aparelho dela é dado da
    máquina dela.

    A régua registra EFEITO, não construção: o espião substitui
    `ler_o_barramento` e conta chamadas.

    Mordida: apagar a guarda do `_mesa_leitor` em `_ler_o_censo`.
    """
    chamadas: list[int] = []
    monkeypatch.setattr(
        secao_mesa,
        "ler_o_barramento",
        lambda *a, **k: (chamadas.append(1), Censo())[1],
    )

    host = _Hospedeiro()
    host._mesa_leitor = _mesa  # type: ignore[attr-defined]
    painel = secao_mesa._PainelDaMesa(host)

    resultado = painel._ler_o_censo()

    assert not chamadas, (
        "a seção varreu o barramento USB desta máquina durante uma captura. "
        "A espécie de cada aparelho dela iria para um PNG versionado."
    )
    assert resultado.aparelhos == ()


def test_fora_da_captura_a_secao_le_o_barramento_de_verdade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A contraparte, e sem ela a guarda acima passaria com a leitura MORTA.

    Um portão que só prova a ausência da leitura aprova o módulo que nunca lê
    nada — e a coluna inteira cairia em "não sei" na máquina dela sem ninguém
    perceber.

    Mordida: fazer `_ler_o_censo` devolver `Censo()` sempre.
    """
    chamadas: list[int] = []
    monkeypatch.setattr(
        secao_mesa,
        "ler_o_barramento",
        lambda *a, **k: (chamadas.append(1), Censo())[1],
    )

    painel = secao_mesa._PainelDaMesa(_Hospedeiro())
    painel._ler_o_censo()

    assert chamadas, (
        "a seção não leu o barramento fora da captura; a coluna 'O que é' "
        "nasceria em 'não sei' em toda linha, na máquina de todo mundo"
    )
