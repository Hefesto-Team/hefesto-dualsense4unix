"""A seção "A mesa" leva a declaração dela ao disco — e a relê ao voltar.

O DEFEITO QUE ESTE PORTÃO EXISTE PARA IMPEDIR (22/08/2026). A aba Configurações
nasceu com CONFIG-02 (a seção que lê o barramento) e CONFIG-03 (a camada
`maquina.json`, mais o `machine.declare` do IPC) **no mesmo dia**. As duas
frentes eram de agentes diferentes, e o `_ao_declarar` da seção ficou com o
`TODO(CONFIG-03)` intacto: *"enquanto a camada de persistência de mesa não
existe, o valor morre com a janela"*.

A camada existia. A frase que dizia que não sobreviveu a ela.

É a classe de defeito mais cara desta casa — a cura escrita e nunca ligada
(`A-CASA-SABE-E-O-PRODUTO-NAO-FAZ-01`) — acontecendo dentro da leva que a
documentou. O sintoma para quem usa: escolher "Acima" na altura da antena,
fechar a janela, reabrir, e a escolha não está lá. Nada avisa, e o exame da
mesa continua sem ter como explicar um alcance ruim.

O QUE O PORTÃO COBRA, e por que cada coisa:

1. **O gesto acumula em `_maquina_pendente`**, não grava sozinho. `D-A4`: quem
   grava é o "Aplicar" do rodapé. Dois donos do gesto de gravar é a classe de
   defeito que a `ABAS-01` curou.
2. **`"nao_sei"` vira `None`.** O esquema é `Literal["acima", "abaixo"] | None`
   com `extra="forbid"`: a string `"nao_sei"` faria o pydantic recusar o
   DOCUMENTO INTEIRO, e o sintoma na tela seria "não consegui gravar" — nunca
   "valor inválido".
3. **A fusão é parcial.** As cinco seções escrevem no MESMO rascunho pelo mesmo
   gesto. Substituir em vez de fundir faria a última a clicar apagar as outras
   quatro.
4. **Montar não suja o rascunho.** `set_active_id` emite `changed`; com o sinal
   já ligado, abrir a aba marcaria o rascunho como pendente sem ninguém ter
   clicado em nada, e o rodapé teria o que "Aplicar" do nada.
5. **O `tipo` de cada rádio tem tela.** `RadioDeclarado.tipo` nasceu em
   CONFIG-03 e ficou sem widget nenhum — a outra metade do mesmo defeito.
"""
from __future__ import annotations

from typing import Any

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("declaração da mesa")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador, Mesa, RadioUsb
from hefesto_dualsense4unix.utils.maquina import MaquinaConfig


class _Hospedeiro:
    """O mínimo que a seção toca: o rascunho da máquina, e nada mais."""

    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None


def _mesa_de_bancada() -> Mesa:
    """Um adaptador e um rádio vizinho — o bastante para as duas tabelas."""
    return Mesa(
        adaptadores=[
            Adaptador(
                interface="hci0",
                no="1-1",
                vid="0a12",
                pid="0001",
                busnum=1,
                devpath="1",
                painel="rear",
            )
        ],
        radios=[
            RadioUsb(no="1-2", vid="046d", pid="c52b", busnum=1, devpath="2")
        ],
    )


def _montar(host: Any, mesa: Mesa | None = None) -> Gtk.Box:
    """Monta a seção com uma mesa de bancada, sem tocar no `/sys` desta máquina."""
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    painel = secao_mesa._PainelDaMesa(host)
    painel._ler = lambda: _mesa_de_bancada() if mesa is None else mesa  # type: ignore[method-assign]
    painel._pedir_o_estado = lambda: None  # type: ignore[method-assign]
    painel.montar(caixa)
    host._painel_da_mesa = painel
    return caixa


def _seletores(raiz: Any) -> list[Any]:
    """Todo `SegmentedSelector` da árvore, na ordem em que aparecem."""
    from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector

    achados: list[Any] = []

    def _andar(widget: Any) -> None:
        if isinstance(widget, SegmentedSelector):
            achados.append(widget)
        if hasattr(widget, "get_children"):
            for filho in widget.get_children():
                _andar(filho)

    _andar(raiz)
    return achados


# --- 1. O gesto acumula, e não grava ---------------------------------------


def test_declarar_a_altura_acumula_no_rascunho_da_maquina() -> None:
    """Escolher "Acima" põe o valor em `_maquina_pendente`, sob `mesa`.

    Mordida: devolver o `_ao_declarar` ao corpo antigo
    (`self.declarado[chave] = seletor.get_active_id()`, e nada mais) — o
    rascunho fica `None` e este teste reprova.
    """
    host = _Hospedeiro()
    _montar(host)

    painel = host._painel_da_mesa
    painel._ao_declarar(_SeletorFalso("acima"), "altura_da_antena")

    assert host._maquina_pendente == {"mesa": {"altura_da_antena": "acima"}}, (
        "a escolha não chegou ao rascunho da máquina — sem isso o 'Aplicar' do "
        f"rodapé não tem o que gravar. Rascunho: {host._maquina_pendente!r}"
    )


def test_nao_sei_vira_ausencia_de_opiniao_e_nao_a_palavra() -> None:
    """`"nao_sei"` grava `None`, que é o que o esquema aceita.

    Mordida: passar o id cru adiante — o `MaquinaConfig` abaixo levanta, porque
    `Literal["acima", "abaixo"] | None` não conhece a palavra.
    """
    host = _Hospedeiro()
    _montar(host)

    host._painel_da_mesa._ao_declarar(_SeletorFalso("nao_sei"), "linha_de_visada")

    assert host._maquina_pendente == {"mesa": {"linha_de_visada": None}}
    # A régua independente: o esquema de verdade tem de aceitar o que saiu daqui.
    MaquinaConfig.model_validate(host._maquina_pendente)


def test_a_segunda_escolha_nao_apaga_a_primeira() -> None:
    """Fusão parcial: as cinco seções escrevem no MESMO rascunho.

    Mordida: trocar `fundir_declaracao` por atribuição direta em `_acumular`.
    """
    host = _Hospedeiro()
    _montar(host)
    painel = host._painel_da_mesa

    painel._ao_declarar(_SeletorFalso("acima"), "altura_da_antena")
    painel._ao_declarar(_SeletorFalso("livre"), "linha_de_visada")

    assert host._maquina_pendente == {
        "mesa": {"altura_da_antena": "acima", "linha_de_visada": "livre"}
    }


def test_declarar_nao_manda_ipc_nem_grava_em_disco() -> None:
    """Quem grava é o rodapé. A seção só marca o rascunho.

    Mordida: chamar `machine.declare` (ou `gravar_maquina`) de dentro do gesto —
    o dublê abaixo registra a chamada e este teste reprova.
    """
    gravou: list[Any] = []
    host = _Hospedeiro()
    _montar(host)

    original = secao_mesa.carregar_maquina
    secao_mesa.carregar_maquina = lambda: (gravou.append("leu"), MaquinaConfig())[1]  # type: ignore[assignment]
    try:
        host._painel_da_mesa._ao_declarar(_SeletorFalso("abaixo"), "altura_da_antena")
    finally:
        secao_mesa.carregar_maquina = original  # type: ignore[assignment]

    assert not gravou, (
        "o gesto foi ao disco. Ele só pode marcar o rascunho — o 'Aplicar' do "
        "rodapé é o dono único da gravação (D-A4)."
    )


# --- 2. Montar relê, e não suja -------------------------------------------


def test_montar_repoe_a_escolha_que_estava_gravada() -> None:
    """Abrir a aba mostra o que ela já tinha escolhido.

    Mordida: apagar o bloco de pré-seleção de `_linha_declarada` — o seletor
    volta sem nada marcado e este teste reprova.
    """
    host = _Hospedeiro()
    original = secao_mesa.carregar_maquina
    secao_mesa.carregar_maquina = lambda: MaquinaConfig.model_validate(  # type: ignore[assignment]
        {"mesa": {"altura_da_antena": "abaixo"}}
    )
    try:
        _montar(host)
    finally:
        secao_mesa.carregar_maquina = original  # type: ignore[assignment]

    assert host._painel_da_mesa.declarado["altura_da_antena"] == "abaixo", (
        "a seção não releu o que estava gravado; a escolha dela some ao "
        "reabrir a janela"
    )


def test_montar_nao_marca_o_rascunho_como_pendente() -> None:
    """Abrir a aba não pode dar ao rodapé o que "Aplicar".

    `set_active_id` emite `changed`. Se a pré-seleção viesse DEPOIS do
    `connect`, o simples ato de desenhar a tela escreveria no rascunho.

    Mordida: mover o `connect` para antes do bloco de pré-seleção.
    """
    host = _Hospedeiro()
    original = secao_mesa.carregar_maquina
    secao_mesa.carregar_maquina = lambda: MaquinaConfig.model_validate(  # type: ignore[assignment]
        {"mesa": {"altura_da_antena": "acima", "linha_de_visada": "livre"}}
    )
    try:
        _montar(host)
    finally:
        secao_mesa.carregar_maquina = original  # type: ignore[assignment]

    assert host._maquina_pendente is None, (
        "desenhar a tela sujou o rascunho: o rodapé passaria a ter algo a "
        f"aplicar sem ninguém ter clicado. Rascunho: {host._maquina_pendente!r}"
    )


# --- 3. O tipo de cada rádio tem tela --------------------------------------


def test_cada_radio_vizinho_ganha_o_seletor_de_tipo() -> None:
    """A coluna "O que é" existe, com os sete botões do desenho.

    `RadioDeclarado.tipo` nasceu em CONFIG-03 e ficou sem widget nenhum.

    Mordida: não anexar o `_seletor_do_tipo` na grade dos rádios.
    """
    host = _Hospedeiro()
    caixa = _montar(host)

    # A régua é a CONTAGEM, contra uma fonte independente do widget: a seção
    # tem dois seletores de declaração (altura e visada) mais um por rádio
    # vizinho. Bastasse "existe algum seletor", o teste passaria com a coluna
    # inteira ausente — e passava, medido em 22/08 antes desta linha.
    esperados = 2 + len(_mesa_de_bancada().radios)
    achados = _seletores(caixa)
    assert len(achados) == esperados, (
        f"a seção tem {len(achados)} seletores e devia ter {esperados}: dois de "
        "declaração mais um 'O que é' por rádio vizinho"
    )

    # Os sete ids do módulo são exatamente os `Literal` do esquema mais o
    # "não sei" — régua independente, contra o esquema e não contra a tela.
    do_esquema = {
        "wifi",
        "teclado",
        "mouse",
        "webcam",
        "caixa_de_som",
        "outro",
    }
    do_modulo = {ident for ident, _ in secao_mesa._TIPOS_DE_RADIO}
    assert do_modulo == do_esquema | {"nao_sei"}, (
        f"a tela oferece {sorted(do_modulo)} e o esquema aceita "
        f"{sorted(do_esquema)}; um botão que o esquema não conhece faz o "
        "pydantic recusar o documento inteiro no 'Aplicar'"
    )


def test_declarar_o_tipo_de_um_radio_acumula_por_vid_pid() -> None:
    """A chave é `vid:pid`, e não o nó do sysfs.

    O nó muda quando o aparelho troca de porta; a resposta "isto é um teclado"
    não muda com a porta. O esquema valida a chave por regex.

    Mordida: usar `radio.no` como chave — o `MaquinaConfig` abaixo levanta.
    """
    host = _Hospedeiro()
    _montar(host)

    host._painel_da_mesa._ao_declarar_o_radio(_SeletorFalso("webcam"), "046d:c52b")

    assert host._maquina_pendente == {
        "mesa": {"radios": {"046d:c52b": {"tipo": "webcam"}}}
    }
    MaquinaConfig.model_validate(host._maquina_pendente)


def test_montar_repoe_o_tipo_gravado_de_cada_radio() -> None:
    """O tipo declarado sobrevive a fechar a janela.

    Mordida: apagar o bloco de pré-seleção de `_seletor_do_tipo`.
    """
    host = _Hospedeiro()
    original = secao_mesa.carregar_maquina
    secao_mesa.carregar_maquina = lambda: MaquinaConfig.model_validate(  # type: ignore[assignment]
        {"mesa": {"radios": {"046d:c52b": {"tipo": "teclado"}}}}
    )
    try:
        _montar(host)
    finally:
        secao_mesa.carregar_maquina = original  # type: ignore[assignment]

    assert host._painel_da_mesa.radios_declarados.get("046d:c52b") == "teclado"


# --- 4. Nenhum TODO sobrevive à camada que ele esperava ---------------------


def test_a_secao_nao_diz_mais_que_a_camada_de_persistencia_nao_existe() -> None:
    """O comentário caduco é o defeito, não o enfeite dele.

    A frase *"enquanto a camada de persistência de mesa não existe"* ficou no
    código depois de a camada nascer, no mesmo dia. Quem lesse o módulo
    concluiria que o buraco era conhecido e aceito — foi o que aconteceu.

    Mordida: escrever `TODO(CONFIG-03)` de volta em `secao_mesa.py`.
    """
    from pathlib import Path

    fonte = Path(secao_mesa.__file__).read_text(encoding="utf-8")
    assert "TODO(CONFIG-03)" not in fonte, (
        "o módulo ainda diz que espera CONFIG-03. A camada existe desde "
        "22/08/2026 (`utils/maquina.py` e o `machine.declare` do IPC) — um TODO "
        "que sobrevive à própria cura ensina a próxima pessoa a não ligá-la."
    )


class _SeletorFalso:
    """Só o `get_active_id`, que é tudo o que o gesto lê do widget."""

    def __init__(self, ativo: str | None) -> None:
        self._ativo = ativo

    def get_active_id(self) -> str | None:
        return self._ativo
