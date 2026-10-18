"""TECLADO-NA-TELA-QUE-A-JANELA-NAO-LE-01 — o dado chega no fio e a linha o lê.

O daemon publica `keyboard_emulation.osk_disponivel` desde 10/08 (`ipc_handlers`), e é ele quem
enxerga o HOST: a janela não pode fazer o `shutil.which` por conta própria, porque num Flatpak
olharia dentro do sandbox. Nenhum atalho de fábrica digita letra, então o teclado na tela é o
único caminho do produto para ESCREVER TEXTO com o controle.

A aba Navegação do todo tirou a linha que dizia se a máquina tem o teclado. A frase voltou ao
desfecho da linha que o escolhe (O-QUE-A-NAVEGACAO-VELHA-DEIXOU-SEM-CHAMADOR-01): a escolha é
guardada e a resposta diz que, neste computador, ela não abre nada.

O que se mede:

1. a frase é de quem NÃO tem: `None` ("ainda não sei") e `True` devolvem `""`, porque trocar "não
   sei" por "não tem" mandaria instalar um pacote que talvez já esteja lá;
2. escolher o teclado na tela numa linha, com o daemon dizendo que não há, guarda e responde;
3. com ele instalado, ou sem resposta do daemon, a escolha não responde nada;
4. escolher outra ação, com o teclado ausente, não responde nada;
5. vale igual na linha do PS, que também aceita o teclado na tela.

MORDIDAS: tirar a chamada a `_avisar_se_sem_teclado_na_tela` reprova 2 e 5; devolver `""` nos três
estados reprova 1.
"""
from __future__ import annotations

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.input_actions`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions.input_actions import frase_do_teclado_na_tela
from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from tests.unit.test_a_06_o_perfil_lembra_do_mouse_e_do_teclado import (
    PonteDeMentira,
    _ctx,
    _semear,
)



class _PonteComMaquina(PonteDeMentira):
    """A ponte que também aceita o `machine.declare` da linha PS."""

    def machine_declare(self, maquina: dict) -> tuple[bool, str | None]:
        self.chamadas.append(("machine.declare", maquina))
        return True, None


ROTULOS = [acoes.rotulo(t) for t in ("__TOGGLE_OSK__", "__OPEN_OSK__", "__CLOSE_OSK__")]
SEM_TECLADO = {"enabled": True, "osk_disponivel": False}


def test_so_quem_nao_tem_recebe_a_frase() -> None:
    assert frase_do_teclado_na_tela(None) == "", (
        "a janela passou a afirmar sobre uma máquina que ninguém olhou")
    assert frase_do_teclado_na_tela(True) == "", "mandou instalar o que já está instalado"
    frase = frase_do_teclado_na_tela(False)
    assert "não há teclado na tela instalado" in frase
    assert "escrever texto" in frase, (
        "a frase avisa da falta e não diz a CONSEQUÊNCIA: sem ele não há como escrever texto")
    assert frase.index("wvkbd-mobintl") < frase.index("onboard"), (
        "o onboard digita por XTEST e não alcança cliente Wayland nativo: recomendá-lo "
        "primeiro faz o teclado ABRIR e não DIGITAR, que é pior que não abrir")


@pytest.fixture
def linha_e_pacotes():
    import pacotes

    pacotes._carregar_tudo()
    fn = pacotes.gesto_da_pagina("06-navegacao.html", "linha-de-botao")
    assert fn is not None
    return fn, pacotes


@pytest.mark.parametrize("rotulo", ROTULOS)
@pytest.mark.parametrize("botao", ["cross", "l1", "ps"])
def test_escolher_o_teclado_sem_ele_instalado_guarda_e_responde(
        linha_e_pacotes, botao: str, rotulo: str) -> None:
    # D-1710-O-TECLADO-NA-TELA-AUSENTE-RESPONDE-NA-LINHA
    fn, pacotes = linha_e_pacotes
    _semear("regua")
    ctx = _ctx(pacotes, keyboard_emulation=SEM_TECLADO)
    with pytest.raises(RuntimeError) as caiu:
        fn(ctx, {"linha": botao, "valor": rotulo}, _PonteComMaquina())
    assert str(caiu.value).startswith("guardei, e não há teclado na tela instalado"), caiu.value


@pytest.mark.parametrize("bloco", [
    {"enabled": True, "osk_disponivel": True},
    {"enabled": True},
    {"enabled": True, "osk_disponivel": None},
], ids=["instalado", "daemon-nao-disse", "daemon-sem-resposta"])
def test_instalado_ou_sem_resposta_a_escolha_nao_responde(linha_e_pacotes, bloco: dict) -> None:
    fn, pacotes = linha_e_pacotes
    _semear("regua")
    ctx = _ctx(pacotes, keyboard_emulation=bloco)
    fn(ctx, {"linha": "cross", "valor": ROTULOS[0]}, PonteDeMentira())


def test_outra_acao_sem_o_teclado_na_maquina_nao_responde(linha_e_pacotes) -> None:
    fn, pacotes = linha_e_pacotes
    _semear("regua")
    ctx = _ctx(pacotes, keyboard_emulation=SEM_TECLADO)
    fn(ctx, {"linha": "cross", "valor": acoes.rotulo(acoes.padrao()["cross"])}, PonteDeMentira())
