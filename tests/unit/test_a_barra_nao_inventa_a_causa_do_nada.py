"""Duas listas vazias são CINCO causas, e a barra só pode nomear as que sabe.

O DEFEITO, E ELE ERA UMA REGRESSÃO
-----------------------------------

``_destinos_do_broadcast`` (``daemon/ipc_handlers.py:1158-1183``) devolve
``([], [])`` em **cinco** situações distintas:

===  ====================================================  ==================
 #   situação                                              a janela sabe?
===  ====================================================  ==================
 1   mesa vazia (``not alvos``, :1160)                     **sim**
 2   Modo Nativo ligado, COM controle na mesa (:1162)      **sim**
 3   ``get_output_target_index`` ausente (:1168)           não
 4   exceção ao ler o índice (:1173)                       não
 5   alvo sem ``uniq`` estável (:1183)                     não
===  ====================================================  ==================

Até 25/08/2026 a barra respondia a **todas as cinco** com a mesma frase:
*"nenhum controle recebeu — não há controle na mesa"*. Nas quatro últimas isso
é falso, e no caso 2 era **regressão**: o código anterior a ``41541a7`` dizia
*"guardado; em Modo Nativo quem manda no controle é o jogo"*, que é a verdade.

A ironia é o ponto: a frente que introduziu esta frase existia para tirar da
tela a palavra "aplicado" sem prova. Ela trocou uma afirmação sem prova por
outra, na direção oposta — e é o padrão A3 desta casa, *o conserto que
reintroduz o defeito que cura*.

POR QUE TRÊS FRASES E NÃO UMA
------------------------------

A janela enxerga dois dos cinco casos e **não tem como** enxergar os outros
três. Uma frase só obrigaria a escolher entre calar sobre o que se sabe (caso 1
e 2 viram genéricos) ou inventar sobre o que não se sabe (3, 4 e 5 viram
diagnóstico). As duas são piores que três frases.

A terceira — a genérica — é a que carrega o peso: *"olhei e não sei por quê"* é
uma resposta legítima, e disfarçá-la de diagnóstico é o defeito de forma que a
``frase_do_desfecho`` inteira existe para matar.

A MORDIDA
---------

Faça ``NADA_ACONTECEU`` voltar a ser ``"nenhum controle recebeu — não há
controle na mesa"``, **ou** apague o ramo ``if modo_nativo_manda_no_output`` de
``frase_do_desfecho``, e ``test_o_modo_nativo_nao_vira_mesa_vazia`` reprova.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.textos_de_aplicacao import (
    NADA_ACONTECEU,
    NADA_ACONTECEU_MESA_VAZIA,
    NADA_ACONTECEU_NATIVO,
    frase_do_desfecho,
    mesa_vazia,
)


class _Host:
    """Dublê de janela. Sabe RECUSAR — dublê que só aceita não é régua (A2)."""

    def __init__(
        self,
        *,
        nativo: bool = False,
        conectados: dict[int, str] | None = None,
        coop: bool = False,
    ) -> None:
        self._modo_nativo_ligado = nativo
        self._coop_ligado = coop
        if conectados is not None:
            self._target_uniq_by_index = conectados


#: O corpo que o daemon devolve nos CINCO caminhos: as duas listas vazias.
VAZIO = {"status": "ok", "aplicado_em": [], "guardado_em": []}

MESA_COM_UM = {0: "aabbcc000001"}


class TestABarraNaoInventaACausaDoNada:
    def test_o_modo_nativo_nao_vira_mesa_vazia(self) -> None:
        """O caso 2 — e é a regressão que este arquivo existe para impedir.

        Modo Nativo ligado **com um controle na mesa**. Dizer "não há controle
        na mesa" aqui é afirmar o oposto do que a própria janela enxerga.
        """
        host = _Host(nativo=True, conectados=MESA_COM_UM)
        frase = frase_do_desfecho("Gatilho esquerdo (L2): Rigid", VAZIO, host)

        assert "não há controle na mesa" not in frase, (
            f"a barra disse {frase!r} com o Modo Nativo LIGADO e um controle "
            "conectado. As duas listas vazias vieram do ramo `is_native_mode()` "
            "(daemon/ipc_handlers.py:1162), não de mesa vazia — e o código "
            "anterior a 41541a7 acertava esta frase. É regressão."
        )
        assert frase.endswith(NADA_ACONTECEU_NATIVO), (
            f"esperava a frase terminar em {NADA_ACONTECEU_NATIVO!r}; veio {frase!r}"
        )

    def test_a_mesa_vazia_continua_dizendo_que_esta_vazia(self) -> None:
        """O caso 1. A cura não pode ter custado a frase que era VERDADE.

        Sem esta guarda, "conserto" que apagasse o diagnóstico inteiro
        passaria — e a pessoa com a mesa vazia perderia a única frase que lhe
        dizia o que fazer.
        """
        host = _Host(nativo=False, conectados={})
        frase = frase_do_desfecho("Cor da barra", VAZIO, host)
        assert frase.endswith(NADA_ACONTECEU_MESA_VAZIA), (
            f"mesa comprovadamente vazia devia manter o diagnóstico; veio {frase!r}"
        )

    def test_o_que_a_janela_nao_sabe_ela_nao_afirma(self) -> None:
        """Os casos 3, 4 e 5 — invisíveis para a janela.

        Um controle na mesa, Modo Nativo desligado, e mesmo assim o daemon
        devolveu duas listas vazias. A causa está fora do alcance da janela; a
        frase honesta é a genérica.
        """
        host = _Host(nativo=False, conectados=MESA_COM_UM)
        frase = frase_do_desfecho("Vibração", VAZIO, host)

        assert frase.endswith(NADA_ACONTECEU), f"veio {frase!r}"
        assert "não há controle na mesa" not in frase, (
            f"a barra disse {frase!r} com um controle CONECTADO e o Modo "
            "Nativo desligado. Este é um dos três caminhos que a janela não "
            "enxerga (índice ausente, exceção na leitura, alvo sem uniq) — e "
            "sobre o que ela não sabe, ela não afirma."
        )
        assert "Modo Nativo" not in frase, (
            f"a barra disse {frase!r} com o Modo Nativo DESLIGADO — inventar "
            "a causa errada é o mesmo defeito na direção oposta."
        )

    def test_as_tres_frases_sao_distintas(self) -> None:
        """Se duas colapsarem, os testes acima viram tautologia."""
        assert len({NADA_ACONTECEU, NADA_ACONTECEU_MESA_VAZIA, NADA_ACONTECEU_NATIVO}) == 3, (
            "duas das três frases de 'nada aconteceu' ficaram iguais — as "
            "asserções acima param de distinguir o que prometem distinguir."
        )


class TestMesaVaziaNaoAdivinha:
    """A régua nova precisa saber RECUSAR, e o padrão inseguro é o pior erro."""

    @pytest.mark.parametrize(
        ("mapa", "esperado", "porque"),
        [
            ({}, True, "mapa vazio é mesa vazia — é o que a Status publica"),
            ({0: "aabbcc000001"}, False, "um controle conectado"),
            ({0: "", 1: None}, True, "só entradas vazias contam como vazia"),
            ({0: "", 1: "aabbcc000002"}, False, "uma entrada boa basta"),
        ],
    )
    def test_le_o_mapa_de_conectados(
        self, mapa: dict, esperado: bool, porque: str
    ) -> None:
        assert mesa_vazia(_Host(conectados=mapa)) is esperado, porque

    def test_sem_mapa_ela_nao_inventa(self) -> None:
        """Sem o mapa a resposta é ``False``, e é o padrão SEGURO.

        ``True`` aqui faria a barra afirmar "não há controle na mesa" toda vez
        que os mixins não estivessem compostos — que é justamente quando ela
        menos sabe. Mesmo critério do ``getattr`` defensivo de
        ``modo_nativo_manda_no_output``.
        """
        assert mesa_vazia(_Host()) is False
        assert mesa_vazia(object()) is False
