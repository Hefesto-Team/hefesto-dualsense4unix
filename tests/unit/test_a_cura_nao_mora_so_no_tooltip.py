"""A cura sai do tooltip e vira card — com as três linhas e o selo de cada uma.

O QUE ESTE ARQUIVO TRAVA
-------------------------

O produto sabe achar cinco problemas na mesa, tem a cura escrita de quatro
deles, e até 25/08/2026 a cura só chegava à tela dentro de um
``set_tooltip_text`` (`secao_exame._dica_do_item`, e não havia um segundo
caminho). Quem não passasse o mouse por cima da palavra certa **nunca descobria
o que fazer**. Ao lado disso, `integrations/ordens_da_mesa.py` — 1261 linhas,
seis regras, bateria verde — não tinha um único consumidor.

Este arquivo é a régua de que os dois defeitos fecharam juntos:

1. o imperativo de uma ordem e as **três** linhas de porquê aparecem no texto de
   um ``Gtk.Label``, **fora de qualquer tooltip**;
2. a **terceira** linha aparece inclusive quando ela confessa que o ganho não
   foi medido. É ela que impede raciocínio de se vestir de medição: uma ordem
   que manda mover sem dizer quanto se ganha é honesta; a mesma com o ganho
   escondido é palpite com cara de laudo;
3. cada linha carrega o **selo de procedência** na tela — sem ele, "USB 3.0
   emite ruído em 2,4 GHz" (especificação de terceiro) e "não medi o ganho nesta
   máquina" (conta) leem igual;
4. a cura de uma conferência SEM ordem também sai do tooltip;
5. **nenhum serial chega ao markup.** A exigência nasceu quando a tela desta
   aba virava PNG versionado pelo retratista da janela GTK — que saiu com ela
   em 06/09/2026 (`D-0609-GTK-LEVA-INTEIRA`), e o retratista de hoje
   (`src/hefesto_dualsense4unix/interface/olhar.py`) fotografa as páginas HTML,
   não este painel. **A exigência fica**, e não depende de quem fotografa:
   nenhum portão de anonimato varre imagem, e `scripts/check_anonymity.sh` diz
   por escrito que o serial identifica a unidade dela tão bem quanto o MAC.

POR QUE ``Gtk.OffscreenWindow``, E NUNCA ``Gtk.Window``
--------------------------------------------------------

Sob Xvfb não há gerenciador de janelas, e uma ``Gtk.Window`` fica 1x1 para
sempre: os filhos nunca ganham tamanho e o teste passa a medir o servidor X em
vez do produto. É a armadilha nº 2 de `docs/process/COMO-OLHAR-A-TELA.md`.

A BANCADA NÃO É ESTA MÁQUINA
------------------------------

`bancada_das_ordens.py` monta o `Censo` e os `NoDeEntrada` à mão, com caminhos
``/mentira`` e seriais sintéticos, e os cinco caminhos do exame apontam para uma
raiz que não existe. Nada aqui abre ``/sys``, ``/proc`` ou o rádio.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi`. `importorskip("gi")`
# aceita o stub que outro arquivo planta em `sys.modules`; esta guarda não.
exigir_gi_real("a cura fora do tooltip")

import re
import time
from pathlib import Path
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_exame as secao
from hefesto_dualsense4unix.integrations import exame_da_mesa as exame_mod
from hefesto_dualsense4unix.integrations import ordens_da_mesa as ordens
from tests.unit import bancada_das_ordens as bancada

#: Doze hex seguidos, que é a FORMA em que um serial USB carrega endereço. A
#: régua é a mesma de `scripts/check_endereco_de_radio.py:103`, e o comprimento
#: sai da constante do módulo em vez de ser recopiado — se um dia o produto
#: mudar de ideia sobre o que é serial, esta régua muda junto.
SERIAL = re.compile(
    "(?<![0-9A-Fa-f])[0-9A-Fa-f]{"
    f"{ordens._TAMANHO_DO_SERIAL_DE_ENDERECO}"
    "}(?![0-9A-Fa-f])"
)

#: Uma raiz que não existe: força cada uma das cinco conferências ao ramo
#: pessimista sem tocar em arquivo nenhum da máquina.
SEM_BANCADA = Path("/bancada/nao-existe")


def _leitura() -> ordens.Leitura:
    """A bancada de 24/08 como `Leitura` — sem desenho de gabinete nenhum.

    Sem desenho é o caso mais comum e é uma resposta: R1 e R3 mandam mover, e
    dizem que só ela pode dizer para onde.
    """
    return ordens.Leitura(censo=bancada.censo(), entradas=bancada.entradas())


def _itens(**extra: Any) -> list[exame_mod.Item]:
    """As cinco conferências no pior caso, mais o que o teste pedir por cima.

    Os cinco caminhos apontam para uma raiz inexistente de propósito: é o que
    põe cada conferência no ramo pessimista — o que tem cura — sem tocar em
    arquivo nenhum desta máquina.
    """
    argumentos: dict[str, Any] = {
        "parametro_do_radio": SEM_BANCADA,
        "conf_do_radio": SEM_BANCADA,
        "raiz_usb": SEM_BANCADA,
        "modulos": SEM_BANCADA,  # (noqa-acento): nome de argumento
        "diretorio_do_modulo": SEM_BANCADA,
        "executar_busctl": lambda _argumentos: None,
        "leitura_da_vizinhanca": list,
        "leitura_das_ordens": _leitura,
    }
    argumentos.update(extra)
    return exame_mod.exame(**argumentos)


def _montar() -> tuple[Gtk.OffscreenWindow, secao.PainelDoExame]:
    """O painel de PRODUÇÃO, montado numa janela que existe de verdade."""
    janela = Gtk.OffscreenWindow()
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    janela.add(caixa)
    painel = secao.PainelDoExame()
    painel.montar(caixa)
    janela.show_all()
    return janela, painel


def _textos_visiveis(raiz: Any) -> list[str]:
    """O texto de todo ``Gtk.Label`` da árvore — e **nenhum tooltip**.

    A omissão é o ponto do arquivo: `get_tooltip_text()` não é lido em lugar
    nenhum daqui, então tudo que estas asserções encontrarem chegou à tela por
    um caminho que a pessoa vê sem passar o mouse por cima de nada.
    """
    achados: list[str] = []
    for widget in _arvore(raiz):
        if isinstance(widget, Gtk.Label) and widget.get_text():
            achados.append(widget.get_text())
    return achados


def _markups(raiz: Any) -> list[str]:
    """O markup Pango cru de cada rótulo — é o que vira pixel e vira PNG."""
    achados: list[str] = []
    for widget in _arvore(raiz):
        if isinstance(widget, Gtk.Label):
            bruto = widget.get_label()
            if bruto:
                achados.append(bruto)
    return achados


def _arvore(raiz: Any) -> list[Any]:
    achados: list[Any] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        achados.append(widget)
        filhos = getattr(widget, "get_children", None)
        if filhos is not None:
            pilha.extend(filhos())
    return achados


def _aplicar(painel: secao.PainelDoExame, itens: list[exame_mod.Item]) -> None:
    painel.aplicar(itens, exame_mod.veredito(itens), time.time())


# ---------------------------------------------------------------------------
# 1. A ordem chega à tela inteira — o imperativo e as três linhas.
# ---------------------------------------------------------------------------


def test_a_ordem_sai_do_tooltip_e_vira_texto_na_tela() -> None:
    """A MORDIDA deste arquivo, e ela é a frente inteira em uma asserção.

    Mordida verificada em 25/08/2026: comentei a chamada a
    `_desenhar_o_que_fazer` em `PainelDoExame.aplicar` — que é exatamente
    "devolver a cura só ao `set_tooltip_text`" — e este teste reprovou com
    `o imperativo da ordem 'radio_largo_no_mesmo_hub' não está em nenhum
    Gtk.Label`, nomeando a ordem que sumiu.
    """
    janela, painel = _montar()
    itens = _itens()
    com_ordem = [item for item in itens if item.ordem is not None]
    assert com_ordem, "a bancada de 24/08 tinha de disparar ordem; não disparou"

    _aplicar(painel, itens)

    textos = _textos_visiveis(janela)
    for item in com_ordem:
        ordem = item.ordem
        assert ordem is not None
        assert any(ordem.acao in texto for texto in textos), (
            f"o imperativo da ordem {ordem.chave!r} não está em nenhum "
            f"Gtk.Label — ele continua morando só no tooltip.\n"
            f"esperado: {ordem.acao!r}"
        )


def test_as_tres_linhas_aparecem_com_o_rotulo_e_o_selo() -> None:
    """As TRÊS, com o rótulo e o selo na mesma linha — nenhuma é opcional."""
    janela, painel = _montar()
    itens = _itens()

    _aplicar(painel, itens)

    textos = _textos_visiveis(janela)
    faltando: list[str] = []
    for item in itens:
        if item.ordem is None:
            continue
        for rotulo, linha in zip(
            exame_mod.ROTULOS_DA_ORDEM, item.ordem.linhas, strict=True
        ):
            selo = ordens.TEXTO_DO_SELO[linha.selo]
            casou = [
                texto
                for texto in textos
                if rotulo in texto and linha.texto in texto and selo in texto
            ]
            if not casou:
                faltando.append(f"{item.ordem.chave}/{rotulo}: {linha.texto!r}")
    assert not faltando, (
        "linhas de ordem que não chegaram à tela com rótulo E selo:\n  "
        + "\n  ".join(faltando)
    )


def test_a_terceira_linha_confessa_o_ganho_nao_medido_na_tela() -> None:
    """A regra que não tem exceção: o ganho não medido é DITO, nunca escondido.

    Uma ordem que manda mover um aparelho sem dizer quanto se ganha é honesta; a
    mesma ordem com o ganho escondido é palpite com cara de laudo. Esta é a
    linha que custa uma linha de tela e paga a confiança inteira.
    """
    janela, painel = _montar()
    itens = _itens()

    _aplicar(painel, itens)

    textos = _textos_visiveis(janela)
    confessadas = [
        texto
        for texto in textos
        if exame_mod.ROTULOS_DA_ORDEM[2] in texto and ordens.NAO_MEDI in texto
    ]
    assert confessadas, (
        "nenhuma linha de tela diz que o ganho não foi medido, e as ordens "
        f"desta bancada dizem: {[i.ordem.ganho_esperado.texto for i in itens if i.ordem]}"
    )


def test_a_ordem_sem_desenho_nao_inventa_nome_nem_numero_de_entrada() -> None:
    """Sem declaração dela, a ordem MANDA e diz o que falta para apontar.

    "Wi-Fi" é o nome que o `product` sugere e que a classe `ff` não sustenta;
    `usb1-port5` é um lugar que ninguém acha atrás do gabinete. Os dois são a
    tela afirmando além do que a máquina sabe.
    """
    janela, painel = _montar()

    _aplicar(painel, _itens())

    juntos = "\n".join(_textos_visiveis(janela))
    assert "Wi-Fi" not in juntos, "a tela nomeou como Wi-Fi o que ela não declarou"
    assert "port5" not in juntos and "usb1-" not in juntos, (
        "a tela publicou nome de nó do kernel como se fosse endereço de gente"
    )
    assert ordens.NAO_DECLARADO in juntos, (
        "sem desenho, a ordem tem de DIZER que só ela sabe para onde mandar — "
        "calar seria o estado vazio se disfarçando de resposta"
    )


def test_sem_entrada_livre_o_card_nao_manda_e_diz_por_que() -> None:
    """Ordem sem destino nasce sem imperativo — e as três linhas ficam.

    Um imperativo que manda mover para lugar nenhum é pior que silêncio; um
    card que some por não ter para onde mandar é o F7 de novo, porque a medição
    continua valendo. O que a tela perde é a ordem, não o fato.
    """
    janela, painel = _montar()

    def _sem_buraco() -> ordens.Leitura:
        return ordens.Leitura(
            censo=bancada.censo(),
            entradas=bancada.entradas(sem=bancada.NOS_LIVRES),
        )

    itens = _itens(leitura_das_ordens=_sem_buraco)
    assert [item.ordem.tem_acao for item in itens if item.ordem] == [False] * 3

    _aplicar(painel, itens)

    juntos = "\n".join(_textos_visiveis(janela))
    assert ordens.SEM_DESTINO in juntos, (
        "sem entrada livre, a tela tem de DIZER que não achou para onde mandar"
    )
    assert ordens.NAO_DECLARADO not in juntos, (
        "sem buraco livre nenhum, pedir o desenho do gabinete é mandar a "
        "pessoa trabalhar por um destino que não existe"
    )
    for rotulo in exame_mod.ROTULOS_DA_ORDEM:
        assert rotulo in juntos, f"a linha {rotulo!r} sumiu junto com o imperativo"


# ---------------------------------------------------------------------------
# 2. A cura de uma conferência sem ordem também sai do tooltip.
# ---------------------------------------------------------------------------


def test_a_cura_de_uma_conferencia_sem_ordem_tambem_vira_card() -> None:
    """Quatro das cinco conferências escrevem cura, e nem toda uma vira ordem.

    `energia_do_radio` e `suporte_ao_controle` disparam por arquivo de sistema,
    não por topologia de barramento: nenhuma regra do catálogo as cobre. Se o
    card só falasse de ordem, a cura delas continuaria no tooltip — o defeito
    curado pela metade, que é o mais caro desta casa.
    """
    janela, painel = _montar()
    itens = _itens()
    sem_ordem = [
        item
        for item in itens
        if item.ordem is None
        and item.cura
        and item.estado != exame_mod.ESTADO_CERTO
    ]
    assert sem_ordem, "a bancada tinha de ter conferência com cura e sem ordem"

    _aplicar(painel, itens)

    textos = _textos_visiveis(janela)
    for item in sem_ordem:
        assert any(item.cura in texto for texto in textos), (
            f"a cura de {item.chave!r} não saiu do tooltip: {item.cura!r}"
        )


def test_a_montagem_nao_desenha_card_nenhum() -> None:
    """O estado que o retrato das abas fotografa: montado e ainda sem exame.

    A montagem não examina (cabeçalho de `secao_exame.py`), então não há ordem
    para desenhar — e uma zona de cards que nascesse cheia estaria mostrando o
    resultado de leitura nenhuma.
    """
    janela, painel = _montar()

    assert painel.cards is not None
    assert painel.cards.get_children() == []
    assert not [t for t in _textos_visiveis(janela) if ordens.NAO_MEDI in t]


def test_a_zona_de_cards_nao_acumula_entre_dois_exames() -> None:
    """Dois exames seguidos não podem deixar a recomendação de ontem na tela.

    Zona que só acrescenta parece tela cheia de informação e é tela mentindo:
    ela mostraria junto o que a máquina dizia antes e depois de ela mexer nos
    cabos.
    """
    _janela, painel = _montar()
    itens = _itens()

    _aplicar(painel, itens)
    quantos = len(painel.cards.get_children())
    _aplicar(painel, itens)

    assert len(painel.cards.get_children()) == quantos
    assert quantos > 0


def test_um_exame_sem_ordem_nenhuma_limpa_a_zona() -> None:
    """Ela mexeu nos cabos e o problema saiu: o card tem de sair junto."""
    _janela, painel = _montar()

    _aplicar(painel, _itens())
    assert painel.cards.get_children()

    _aplicar(painel, _itens(leitura_das_ordens=ordens.Leitura))

    restantes = [
        markup
        for markup in _markups(painel.cards)
        if exame_mod.ROTULOS_DA_ORDEM[0] in markup
    ]
    assert not restantes, f"card de ordem sobreviveu a um exame sem ordens: {restantes}"


# ---------------------------------------------------------------------------
# 3. O serial não chega ao PNG.
# ---------------------------------------------------------------------------


def test_a_tela_nao_publica_serial_nem_endereco() -> None:
    """Doze hex no markup reprova — e o markup é o que vira pixel e vira PNG.

    `Identidade` não carrega serial por construção (`ordens_da_mesa` o lê dentro
    de `identidades`, compara e descarta), mas construção não é portão: um campo
    novo, um `f"{aparelho}"` distraído, e o serial da unidade dela entra num
    arquivo versionado que nenhum portão de anonimato varre, porque nenhum deles
    varre imagem.
    """
    janela, painel = _montar()

    _aplicar(painel, _itens())

    achados = [
        (markup, SERIAL.search(markup).group(0))  # type: ignore[union-attr]
        for markup in _markups(janela)
        if SERIAL.search(markup)
    ]
    assert not achados, (
        "há doze hexadecimais seguidos no texto da seção — é a forma de um "
        f"serial, e esta tela vira PNG versionado:\n  {achados}"
    )


def test_a_regua_do_serial_de_fato_pega_um_serial() -> None:
    """A régua contra si mesma: um dublê que só sabe passar não é régua.

    Esta casa pagou por três instrumentos falsos num dia só. Aqui o custo seria
    silencioso: uma regex quebrada daria verde para sempre sobre uma tela
    publicando a unidade dela.
    """
    janela, painel = _montar()
    vazada = ordens.Ordem(
        chave="regua_da_regua",
        acao=f"Mova o aparelho {bancada.SERIAL_DO_DONGLE_INTERNO}",
        o_que_eu_vi=ordens.Linha(texto="uma frase", selo=ordens.MEDIDO_AQUI),
        por_que_importa=ordens.Linha(texto="outra", selo=ordens.MEDIDO_AQUI),
        ganho_esperado=ordens.Linha(
            texto=ordens.NAO_MEDI, selo=ordens.DERIVADO_DA_CONTA
        ),
    )
    itens = [
        exame_mod.Item(
            chave=vazada.chave,
            rotulo=exame_mod.ROTULO_DA_ORDEM,
            estado=exame_mod.ESTADO_ATENCAO,
            porque=vazada.o_que_eu_vi.texto,
            cura=vazada.acao,
            ordem=vazada,
        )
    ]

    _aplicar(painel, itens)

    assert any(SERIAL.search(markup) for markup in _markups(janela)), (
        "a régua não achou um serial que está na tela — ela estava medindo nada"
    )


# ---------------------------------------------------------------------------
# 4. As duas famílias de chave não podem colidir.
# ---------------------------------------------------------------------------


def test_as_chaves_das_regras_nao_colidem_com_as_da_tira() -> None:
    """Colisão aqui seria MUDA, e é por isso que ela tem portão.

    `PainelDoExame.aplicar` pinta a tira procurando a linha PELA CHAVE. Uma
    regra chamada `vizinhanca_das_portas` faria a ordem sobrescrever a linha da
    conferência: a tira mostraria "Mudança recomendada" no lugar de
    "Vizinhança das portas", sem erro e sem log — o mesmo defeito que a foto de
    22/08 sofreu com uma chave digitada errada.
    """
    da_tira = {chave for chave, _rotulo in secao.PainelDoExame._linhas_do_desenho()}
    das_regras = {
        ordens.R1_RADIO_LARGO_NO_MESMO_HUB,
        ordens.R2_DOIS_RADIOS_COLADOS,
        ordens.R3_DONGLE_ATRAS_DE_HUB,
        ordens.R4_TECLADO_SO_NO_HUB,
        ordens.R5_DONGLE_DORME,
        ordens.R6_ENTRADA_RECLAMOU_DE_CORRENTE,
    }

    assert not (da_tira & das_regras), (
        "slug de regra igual a chave de conferência: a ordem sobrescreveria a "
        f"linha da tira em silêncio — {sorted(da_tira & das_regras)}"
    )
    assert exame_mod.CHAVE_DAS_ORDENS not in da_tira


# ---------------------------------------------------------------------------
# 5. O exame só lê o barramento quando pedem — a proteção da foto.
# ---------------------------------------------------------------------------


def test_sem_pedir_o_exame_nao_traz_ordem_nenhuma() -> None:
    """O default de `leitura_das_ordens` é desligado, e isso é a foto.

    A régua nasceu do retratista da janela GTK, que montava uma bancada para os
    cinco caminhos do exame e fotografava o resultado para `docs/usage/assets/`;
    ele saiu com a janela em 06/09/2026. **O motivo dela não saiu junto**, e é
    este: se o catálogo de ordens ligasse sozinho, ele varreria o barramento
    REAL da máquina dela por dentro de uma chamada que quem monta a bancada
    acredita ter injetado inteira — e o
    `test_com_as_raizes_injetadas_nada_do_sistema_real_e_lido` não veria, porque
    ele vigia `pathlib` e as duas varreduras usam `os.listdir` e `open`.
    """
    itens = _itens(leitura_das_ordens=None)

    assert [item.ordem for item in itens] == [None] * 5


def test_leitura_que_explode_vira_nao_sei_e_nunca_silencio() -> None:
    """Falha de leitura não pode virar "não recomendei nada".

    "Não achei o que mudar" e "não consegui olhar" são afirmações opostas, e a
    tela que as colapsa é a tela que mente de cinza.
    """

    def _quebrada() -> ordens.Leitura:
        raise OSError("o barramento sumiu no meio da leitura")

    itens = _itens(leitura_das_ordens=_quebrada)

    das_ordens = [item for item in itens if item.chave == exame_mod.CHAVE_DAS_ORDENS]
    assert len(das_ordens) == 1
    assert das_ordens[0].estado == exame_mod.ESTADO_NAO_SEI
    assert exame_mod.veredito(itens) != exame_mod.ESTADO_CERTO
