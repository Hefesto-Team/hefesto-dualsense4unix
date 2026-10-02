"""CONFIG-01 — a décima primeira aba existe, nasce vazia e não custa largura."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

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

ROTULO_DA_ABA = "Configurações"


class _HospedeiroDaFita(ConfigActionsMixin):
    """Hospedeiro mínimo: só a fita do cabeçalho, dentro de um pai de verdade."""

    def __init__(self) -> None:
        self.cabecalho = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        faixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.cabecalho.pack_end(faixa, False, False, 0)
        self._target_strip = faixa


def test_a_fita_esmaece_na_aba_e_volta_fora_dela() -> None:
    """Ida E volta, no mesmo teste — esmaecer sem devolver é o defeito."""
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
    """O cabeçalho tem de sair da troca de aba com o mesmo tamanho que entrou."""
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
    """Saída cedo tolerante: hospedeiro sem fita não pode levantar."""

    class _SemFita(ConfigActionsMixin):
        pass

    _SemFita().set_alvo_inativo(True, MOTIVO_ALVO_NAO_SE_APLICA)


def test_inativar_sem_motivo_levanta() -> None:
    """Z2-5: esmaecer sem dizer por quê é a mesma omissão que o P3 mediu."""
    host = _HospedeiroDaFita()
    with pytest.raises(ValueError):
        host.set_alvo_inativo(True)


def test_reativar_nao_exige_motivo() -> None:
    """A2: o lado que ACEITA — sair da aba não precisa de explicação nenhuma."""
    host = _HospedeiroDaFita()
    host.set_alvo_inativo(True, MOTIVO_ALVO_NAO_SE_APLICA)
    host.set_alvo_inativo(False)


def _montar_a_aba() -> tuple[Any, Gtk.Widget]:
    """Monta a aba em código e a assenta — é a aba de VERDADE que se mede aqui."""
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
    """Cada seção é uma moldura — como nas outras dez abas — e a ordem é a do"""
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
    """Chamar duas vezes não duplica seção."""

    host = HospedeiroDaAbaConfig()
    host.install_config_tab()
    host.install_config_tab()

    assert len(host.builder.get_object(ABA_CONFIG).get_children()) == len(SECOES)


def test_nenhum_titulo_promete_numero() -> None:
    """Rótulo estático é honesto; valor inventado não é."""
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
    """A folga vertical é da PÁGINA, que rola — nenhuma seção cresce nela."""
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


def test_secao_sem_widget_nao_tem_dica() -> None:
    """Item 8 dos oito de 22/08: a dica não pode chegar antes do conteúdo."""
    sem_conteudo_com_dica = []
    for secao in SECOES_DA_ABA:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
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
    """Hospedeiro mínimo: sem builder, sem mesa, sem daemon."""

    def __init__(self) -> None:
        self.builder = None
