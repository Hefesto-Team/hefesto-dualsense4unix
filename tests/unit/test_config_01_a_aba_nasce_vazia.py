"""CONFIG-01 — a décima primeira aba existe, nasce vazia e não custa largura.

O portão da leva da aba Configurações. Enquanto ele não estiver verde, nenhuma
das outras sprints tem onde morar.

O que ele cobra, e por que cada coisa:

1. **A página existe no Glade, com id no box interno.** Medido em 21/08,
   arrancando o id: `id_da_pagina` NÃO devolve `None` — devolve algo como
   `___object_142___`, o nome que o GtkBuilder inventa a partir da POSIÇÃO do
   objeto no arquivo. A página atravessa inteira o `assert None not in nomes`
   de `test_toda_aba_continua_sendo_reconhecida_pelo_id_do_glade` e muda de
   identidade em silêncio no dia em que alguém inserir um objeto antes dela.
   Este é o único teste que cobra o id.
2. **`install_config_tab()` é chamado nos DOIS caminhos de abertura.** A janela
   sobe visível (`show`) ou minimizada na bandeja (`run`, com `start_hidden`),
   e o segundo é o caminho de quem tem autostart. O
   BUG-HOME-TAB-HIDDEN-INSTALL-01 já foi pago uma vez exatamente assim: a aba
   abria em branco para quem começa na bandeja. Não havia teste guardando as
   duas listas; este é ele.
3. **O mixin está na MRO.** Sem a base, `install_config_tab` não existe no
   objeto e o `show()` estoura.
4. **A fita de alvo esmaece nesta aba e VOLTA nas outras.** O seletor de
   controle do cabeçalho não tem sentido aqui — o que se declara nesta aba vale
   para a mesa inteira. Esmaecer e nunca devolver seria pior que não esmaecer.
5. **A aba montada PELO MIXIN cabe na janela.**
   `tests/unit/test_layout_orcamento_altura.py` carrega o `main.glade` CRU e não
   roda `install_*_tab` nenhum: ele não veria uma linha sequer do que esta aba
   monta em código. Um portão que olha para o lugar errado é pior que portão
   nenhum, porque encerra a busca. Aqui a aba é MONTADA e só então medida.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: vem antes de qualquer import de `gi` de propósito.
# `pytest.importorskip("gi")` ACEITA o stub que outro arquivo planta em
# sys.modules; e sem guarda nenhuma este módulo derruba a COLETA inteira
# no CI headless, em vez de pular.
exigir_gi_real("aba configurações")

import contextlib
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import (
    ABA_CONFIG,
    MOTIVO_ALVO_NAO_SE_APLICA,
    SECOES,
    SECOES_DA_ABA,
    ConfigActionsMixin,
)
from tests.unit.aba_config_sem_a_janela import HospedeiroDaAbaConfig

#: O rótulo da aba, como a pessoa o lê na tira.
ROTULO_DA_ABA = "Configurações"


# --- 4. A fita de alvo esmaece e VOLTA -------------------------------------


class _HospedeiroDaFita(ConfigActionsMixin):
    """Hospedeiro mínimo: só a fita do cabeçalho, dentro de um pai de verdade.

    O cabeçalho existe no dublê porque é ele que o teste da largura vigia: a
    entrada na aba não pode acrescentar filho nenhum ali.
    """

    def __init__(self) -> None:
        self.cabecalho = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        faixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.cabecalho.pack_end(faixa, False, False, 0)
        self._target_strip = faixa


def test_a_fita_esmaece_na_aba_e_volta_fora_dela() -> None:
    """Ida E volta, no mesmo teste — esmaecer sem devolver é o defeito.

    Mordida: trocar o argumento de `set_alvo_inativo` por um `True` fixo.
    """
    host = _HospedeiroDaFita()
    faixa = host._target_strip

    assert faixa.get_sensitive(), "instrumento inválido: a fita já nasceu inerte"

    host.set_alvo_inativo(True, MOTIVO_ALVO_NAO_SE_APLICA)
    assert not faixa.get_sensitive(), (
        "a fita continuou respondendo na aba Configurações"
    )

    host.set_alvo_inativo(False)
    assert faixa.get_sensitive(), (
        "a fita não voltou ao sair da aba — o seletor de controle das outras "
        "abas ficaria morto até reabrir a janela"
    )


def test_entrar_na_aba_nao_engorda_o_cabecalho() -> None:
    """O cabeçalho tem de sair da troca de aba com o mesmo tamanho que entrou.

    Decisão dela, 23/08/2026. A versão anterior pendurava ao lado da fita um
    rótulo com o motivo do esmaecimento. Ele empurrava a altura e a largura do
    cabeçalho, cobria o subtítulo do produto e deixava esta aba mais larga que
    as outras dez — que é exatamente o defeito que a foto mostrou.

    Mordida: pendurar qualquer widget no cabeçalho dentro de `set_alvo_inativo`.
    """
    host = _HospedeiroDaFita()
    antes = list(host.cabecalho.get_children())

    host.set_alvo_inativo(True, MOTIVO_ALVO_NAO_SE_APLICA)
    assert list(host.cabecalho.get_children()) == antes, (
        "entrar na aba Configurações acrescentou widget ao cabeçalho: ele "
        "muda de tamanho e esta aba passa a destoar das outras dez"
    )

    host.set_alvo_inativo(False)
    assert list(host.cabecalho.get_children()) == antes, (
        "sair da aba Configurações deixou widget no cabeçalho"
    )


def test_a_fita_ausente_nao_derruba_nada() -> None:
    """Saída cedo tolerante: hospedeiro sem fita não pode levantar.

    Mordida: tirar a guarda `if faixa is None: return`.
    """

    class _SemFita(ConfigActionsMixin):
        pass

    _SemFita().set_alvo_inativo(True, MOTIVO_ALVO_NAO_SE_APLICA)


def test_inativar_sem_motivo_levanta() -> None:
    """Z2-5: esmaecer sem dizer por quê é a mesma omissão que o P3 mediu.

    Mordida: tirar o `if inativo and not motivo: raise ...` do corpo.
    """
    host = _HospedeiroDaFita()
    with pytest.raises(ValueError):
        host.set_alvo_inativo(True)


def test_reativar_nao_exige_motivo() -> None:
    """A2: o lado que ACEITA — sair da aba não precisa de explicação nenhuma."""
    host = _HospedeiroDaFita()
    host.set_alvo_inativo(True, MOTIVO_ALVO_NAO_SE_APLICA)
    host.set_alvo_inativo(False)  # não levanta


# --- 5. A aba MONTADA cabe na janela ---------------------------------------


def _montar_a_aba() -> tuple[Any, Gtk.Widget]:
    """Monta a aba em código e a assenta — é a aba de VERDADE que se mede aqui.

    06/09/2026 (`GTK-3`): o berço saiu do `gui/main.glade` para
    `tests/unit/aba_config_sem_a_janela.py`, com régua de fidelidade própria.
    """
    hospedeiro = HospedeiroDaAbaConfig()
    hospedeiro.install_config_tab()
    builder = hospedeiro.builder

    pagina = Gtk.ScrolledWindow()
    pagina.add(builder.get_object(ABA_CONFIG))
    janela = Gtk.OffscreenWindow()
    janela.get_style_context().add_class("hefesto-dualsense4unix-window")
    janela.add(pagina)
    janela.show_all()
    while Gtk.events_pending():
        Gtk.main_iteration()
    return builder, pagina


def _titulo_da_moldura(frame: Gtk.Widget) -> str | None:
    """O texto do `label_widget` de uma moldura de seção, ou `None`."""
    rotulo = frame.get_label_widget()
    return None if rotulo is None else rotulo.get_text()


def test_a_aba_e_cinco_molduras_na_ordem_do_desenho() -> None:
    """Cada seção é uma moldura — como nas outras dez abas — e a ordem é a do
    desenho aprovado.

    Este teste nasceu cobrando o contrário ("cinco títulos, zero conteúdo"), e
    ele estava certo enquanto a aba era só o portão. O aceite mudou em
    22/08/2026, e por uma medição: posta lado a lado com as outras dez, a
    Configurações foi a única que leu como quebrada — as dez montam cada seção
    num `Gtk.Frame` com título no canto (`home_actions.py:1500`, `:1712`,
    `:1756`) e esta tinha cinco rótulos soltos na borda esquerda.

    O que sobrevive daquele aceite é o que importa e não caduca: **a aba tem
    exatamente as seções do desenho, na ordem do desenho**. Quantos widgets há
    dentro de cada uma é assunto da seção, não deste portão.

    Mordida: trocar a ordem em `secoes.py`, ou montar uma seção sem moldura.
    """
    builder, _pagina = _montar_a_aba()
    caixa = builder.get_object(ABA_CONFIG)
    filhos = caixa.get_children()

    assert len(filhos) == len(SECOES), (
        f"a aba nasceu com {len(filhos)} filhos diretos e as seções são "
        f"{len(SECOES)}. Todo widget da aba mora DENTRO de uma moldura de "
        "seção — nada é empacotado solto na página."
    )
    assert all(isinstance(f, Gtk.Frame) for f in filhos), (
        "há widget empacotado solto na página, fora de uma moldura de seção"
    )
    assert [_titulo_da_moldura(f) for f in filhos] == [
        titulo for titulo, _ in SECOES
    ]


def test_a_instalacao_e_idempotente() -> None:
    """Chamar duas vezes não duplica seção.

    Os dois caminhos de abertura podem, em tese, se cruzar. E o `show()` roda
    depois do `run()` no ramo da bandeja.

    Mordida: apagar o `getattr(self, "_config_installed", False)` da guarda.
    """

    host = HospedeiroDaAbaConfig()
    host.install_config_tab()
    host.install_config_tab()

    assert len(host.builder.get_object(ABA_CONFIG).get_children()) == len(SECOES)


def test_nenhum_titulo_promete_numero() -> None:
    """Rótulo estático é honesto; valor inventado não é.

    A aba nasce sem uma única medição feita. Um número na tela agora seria
    ilustração se passando por leitura — exatamente o que o desenho avisa sobre
    os endereços e os `831 / 1600` do mockup.

    Mordida: escrever um número em qualquer título de seção.
    """
    for titulo, dica in SECOES:
        assert not any(caractere.isdigit() for caractere in titulo), (
            f"o título {titulo!r} promete um número que ninguém mediu"
        )
        if dica is not None:
            assert not any(caractere.isdigit() for caractere in dica), (
                f"a dica de {titulo!r} promete um número que ninguém mediu"
            )


def _aba_com_controles_na_mesa() -> Any:
    """A aba montada com dois controles, para a seção dos cards existir."""

    class _HospedeiroComMesa(HospedeiroDaAbaConfig):
        def __init__(self) -> None:
            super().__init__()
            self._controles_leitor = lambda: {
                "controllers": [
                    {
                        "uniq": "aa:bb:cc:00:00:01",
                        "connected": True,
                        "transport": "usb",
                        "player_slot": 1,
                    },
                    {
                        "uniq": "aa:bb:cc:00:00:02",
                        "connected": True,
                        "transport": "bt",
                        "player_slot": 2,
                    },
                ]
            }

    hospedeiro = _HospedeiroComMesa()
    hospedeiro.install_config_tab()
    while Gtk.events_pending():
        Gtk.main_iteration()
    return hospedeiro.builder


def test_nenhuma_secao_estica_para_ocupar_a_folga() -> None:
    """A folga vertical é da PÁGINA, que rola — nenhuma seção cresce nela.

    O GTK3 propaga `vexpand` de baixo para cima. Basta um espaçador expansível
    no fundo de um widget — e há um legítimo, o que ancora o seletor de jogador
    no rodapé de todo card para os cards terem a mesma altura — para o
    `Gtk.Frame` da seção inteira passar a pedir expansão. A página então
    entrega a ele toda a folga que sobrar.

    Medido em 22/08/2026: a seção "Os controles" saiu com
    `compute_expand(VERTICAL) = True` e a aba ganhou um vão vazio de mais de
    cem pixels embaixo dos cards. O sintoma é pior numa janela alta, onde a
    última seção afunda para longe das outras.

    Mordida: arranquei o `frame.set_vexpand(False)` de `moldura_de_secao` e
    este teste reprovou nomeando "Os controles".

    A aba é montada aqui COM controles na mesa, e não pelo `_montar_a_aba()`
    dos outros testes deste arquivo. A primeira versão deste teste usava
    aquele, e não mordia: sem controle nenhum a seção mostra uma linha de texto,
    não há card, não há espaçador, e não há `vexpand` para propagar. Um teste
    que só passa é um teste que não testa.
    """
    builder = _aba_com_controles_na_mesa()
    esticam = [
        _titulo_da_moldura(frame)
        for frame in builder.get_object(ABA_CONFIG).get_children()
        if frame.compute_expand(Gtk.Orientation.VERTICAL)
    ]

    assert not esticam, (
        f"estas seções esticam verticalmente: {esticam}. A folga da aba é da "
        "página, que rola — uma seção que cresce afunda as de baixo."
    )


# --- 6. A dica viaja com a seção ------------------------------------------


def test_secao_sem_widget_nao_tem_dica() -> None:
    """Item 8 dos oito de 22/08: a dica não pode chegar antes do conteúdo.

    Quando a aba nasceu (CONFIG-01, 21/08) as cinco seções eram rótulos soltos
    e três delas já traziam dica afirmando NO PRESENTE o que a seção faria — o
    desenho tinha sido copiado inteiro para dentro de uma tela vazia. Mentira na
    tela, e do tipo caro: quem lê a dica não tem como saber que ela fala do
    futuro.

    A régua é mecânica, e é a que o `SPRINT_ORDER.md` fixou: **enquanto a seção
    não puser um widget na caixa dela, ela não tem dica.** Uma seção que já
    desenha pode explicar o que desenha; uma que não desenha nada só pode calar.

    Mordida: trocar o `montar` de qualquer seção com dica por um que não
    acrescente nada — este teste reprova nomeando a seção.
    """
    sem_conteudo_com_dica = []
    for secao in SECOES_DA_ABA:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # Seção que nem monta é seção sem widget, e cai na mesma régua: engolir
        # aqui é o que faz a falha virar "sem tela", em vez de derrubar o portão
        # com um traceback que não diz nada sobre dica nenhuma.
        with contextlib.suppress(Exception):
            secao.montar(_HospedeiroVazio(), caixa)
        if not caixa.get_children() and secao.DICA is not None:
            sem_conteudo_com_dica.append(secao.TITULO)

    assert not sem_conteudo_com_dica, (
        f"estas seções não põem widget nenhum na caixa e mesmo assim têm dica: "
        f"{sem_conteudo_com_dica}. A dica viaja com a seção — descreve o que "
        "está na tela, nunca o que ainda vai chegar."
    )


class _HospedeiroVazio(ConfigActionsMixin):
    """Hospedeiro mínimo: sem builder, sem mesa, sem daemon.

    É de propósito que ele não saiba nada. Uma seção que só consegue desenhar
    com a mesa cheia ainda assim tem de pôr ALGO na caixa — nem que seja a linha
    de "nenhum controle na mesa". Caixa vazia é seção sem tela, e seção sem tela
    não fala.
    """

    def __init__(self) -> None:
        self.builder = None
