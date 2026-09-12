"""MIC-NA-TELA-01 — o botão 🎙 aceso, e o piscando.

**O pedido dela, 10/09/2026:** *"vamos lá na interface invertemos o botão mic
ele aceso (vai indicar que agora tá gravando audio, ele captando audio vai
ficar no estado de piscando (guia visual pro leigo que pegar o controle de
primeira))"*.  <!-- noqa-acento: citação literal dela -->

## O QUE ESTA RÉGUA TRAVA, e o principal não é o CSS

**O contrato de três estados JÁ EXISTIA** — no byte que acende a luz do
PLÁSTICO (`daemon/subsystems/luz_do_mic.decidir`: apagada · acesa · piscando ·
piscando devagar). A tela passa a LER esse estado, e não a decidi-lo de novo:

1. o laço da luz LEMBRA o que decidiu, por controle, e esquece quem sai;
2. o `state_full` publica isso em `audio.luz_do_mic` — ausência é *"não sei"*;
3. um dono só traduz o número na palavra do seletor
   (`mesa_viva.estado_do_botao_do_mic`), e ele **não decide nada**;
4. o pacote da aba emite `mic-botao-estado` com essa palavra;
5. o gerador tem as duas regras de CSS, em `--green` e nunca em `--red`, com
   `prefers-reduced-motion` respeitado.

**Um segundo ternário do lado da tela** (mudo? canal? nível?) poria o botão e a
luz na mão dela discordando no primeiro dia em que um dos dois fosse corrigido
— e é por isso que o `.mudo-i.on` de 06/09 caiu: naquela versão a classe vinha
do GERADOR, não do aparelho.

**A MORDIDA de cada teste está na sua docstring.**
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

ABA02 = RAIZ / "src/hefesto_dualsense4unix/interface/aba02.py"


class TestAPalavraTemUmDono:
    """A tradução do byte, e ela não decide nada."""

    def test_os_tres_estados_e_o_nao_sei(self) -> None:
        """MORDIDA: faça o `0` (apagada) devolver "gravando".

        Apagada é MUDA — o contrato dela é *"aceso = estou sendo ouvido"*, e um
        botão verde sobre um microfone calado é a mentira exata que a inversão
        veio desfazer.
        """
        import mesa_viva

        assert mesa_viva.estado_do_botao_do_mic(0) == ""
        assert mesa_viva.estado_do_botao_do_mic(1) == "gravando"
        assert mesa_viva.estado_do_botao_do_mic(2) == "captando"

    def test_piscando_devagar_e_a_mesma_palavra(self) -> None:
        """MORDIDA: devolva uma terceira palavra para o `3`.

        O `3` é «piscando com bateria baixa»: a diferença entre ele e o `2` é
        um aviso de CARGA, e a carga já tem lugar próprio no cartão. Duas
        piscadas diferentes no mesmo botão seriam duas gramáticas para quem só
        quer saber se está sendo ouvido.
        """
        import mesa_viva

        assert mesa_viva.estado_do_botao_do_mic(3) == "captando"

    def test_o_que_nao_e_numero_vale_como_nao_sei(self) -> None:
        """MORDIDA: aceite `True` ou `"2"`.

        `bool` é `int` em Python: sem a guarda, um `True` vindo de um dublê
        acenderia o botão como se o daemon tivesse dito «acesa».
        """
        import mesa_viva

        for cru in (None, True, False, "2", 2.0, "", {}):
            assert mesa_viva.estado_do_botao_do_mic(cru) == "", cru


class TestODaemonLembraOQueDecidiu:
    """O laço da luz guarda o ALVO, não o escrito."""

    def test_lembra_e_esquece(self) -> None:
        """MORDIDA: guarde só quando a escrita der certo.

        Sem a posse do byte a luz do plástico não muda, e ainda assim a tela
        sabe dizer o estado — guardar apenas o escrito deixaria o botão cinza
        exatamente nos controles em que o Hefesto não tem a posse.
        """
        from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as luz

        luz._lembrar_o_estado("aa:bb:cc:00:00:01", luz.PISCANDO)
        assert luz.estado_da_luz_do_mic("aa:bb:cc:00:00:01") == luz.PISCANDO
        luz._lembrar_o_estado("aa:bb:cc:00:00:01", None)
        assert luz.estado_da_luz_do_mic("aa:bb:cc:00:00:01") is None

    def test_quem_nunca_foi_decidido_e_nao_sei(self) -> None:
        """MORDIDA: devolva `APAGADA` em vez de `None` para quem não está lá.

        `APAGADA` é uma afirmação — *"medi, e está mudo"*. Para um controle que
        acabou de chegar isso pinta o botão de cinza-mudo com a mesma cara de
        quem foi medido, e a tela perde o terceiro estado que ela tem hoje.
        """
        from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as luz

        assert luz.estado_da_luz_do_mic("ff:ff:ff:00:00:ff") is None
        assert luz.estado_da_luz_do_mic("") is None


class TestOPacoteEmite:
    """A aba lê do daemon, e não do seu próprio palpite."""

    def _campos(self, luz: Any) -> dict[str, Any]:
        import pacotes
        import pacotes.a02_controles as a02

        audio = {"mic_mudo": False, "canal_ativo": True}
        if luz is not None:
            audio["luz_do_mic"] = luz
        ctx = pacotes.Contexto(
            state={}, mesa=[], estados={},
            conectados=[{"uniq": "aa:bb:cc:00:00:01", "transport": "usb",
                         "connected": True, "inputs": {}, "audio": audio,
                         "speaker": {"volume": 100, "muted": False}}])
        saida = a02.pacote(ctx)
        cards = saida.get("cards") or {}
        for valores in cards.values():
            if "mic-botao-estado" in valores:
                return valores
        return {}

    def test_o_campo_sai_com_a_palavra_do_daemon(self) -> None:
        """MORDIDA: emita `mesa_viva.selo_do_mic(...)` no lugar.

        O selo responde outra pergunta — *mudo ou ativo* — e não conhece o
        terceiro estado. Trocar um pelo outro faria o botão nunca piscar, com
        a régua do selo continuando verde.
        """
        assert self._campos(2).get("mic-botao-estado") == "captando"
        assert self._campos(1).get("mic-botao-estado") == "gravando"

    def test_sem_leitura_o_campo_vai_vazio(self) -> None:
        """MORDIDA: omita a chave quando não há leitura.

        A chave tem de ir em TODO tique: o piloto REMOVE o atributo ao receber
        vazio, e é isso que apaga um botão que estava piscando. Omitir deixaria
        a última palavra pendurada na tela para sempre — o defeito que a
        ressalva do alto-falante já pagou nesta aba.
        """
        campos = self._campos(None)
        assert "mic-botao-estado" in campos
        assert campos["mic-botao-estado"] == ""


class TestOGeradorPinta:
    """O CSS existe, é verde, e respeita quem pediu menos movimento."""

    def _fonte(self) -> str:
        return ABA02.read_text(encoding="utf-8")

    def test_o_botao_tem_endereco(self) -> None:
        """MORDIDA: tire o `data-campo` do 🎙.

        Sem endereço o pacote escreve no vazio: o campo sai a cada tique e a
        tela não muda — um botão que promete três estados e tem um.
        """
        fonte = self._fonte()
        assert 'data-campo="mic-botao-estado"' in fonte
        assert 'data-hef-atributo="{ATRIBUTO_DA_LUZ_DO_MIC}"' in fonte

    def test_as_duas_regras_sao_verdes_e_nao_vermelhas(self) -> None:
        """MORDIDA: troque `--green` por `--red`.

        `--red` é a cor da FALHA nesta casa, e um microfone no ar não é falha.
        Foi por isso — entre outras — que o `.mudo-i.on` caiu em 06/09.
        """
        fonte = self._fonte()
        trecho = fonte[fonte.index("O 🎙 EM TRÊS ESTADOS"):]
        trecho = trecho[: trecho.index('"""')]
        assert "var(--green)" in trecho
        assert "var(--red)" not in trecho

    def test_o_terceiro_estado_nao_depende_de_movimento(self) -> None:
        """Os três se distinguem PARADOS — decisão dela, 12/09/2026, opção (c).

        **ESTA RÉGUA COBRAVA A ANIMAÇÃO, E TERIA REPROVADO A DECISÃO DELA.** Ela
        exigia `@keyframes mic-captando` e um ramo `prefers-reduced-motion` com
        `animation:none` — isto é, exigia a IMPLEMENTAÇÃO de ontem, não o que a
        tela precisa dizer. A piscada saiu porque *a barra de nível, a dois
        centímetros, já mostra o mesmo fato*, e duas animações para um fato só
        competem entre si.

        O QUE SE MEDE AGORA É O ATO, e ele não mudou: o «captando» continua
        distinto do «no ar» e do «mudo` sem depender de movimento nenhum — o
        fundo esverdeado é o que os separa, e ele está sempre lá. Quem pediu
        menos movimento no sistema vê exatamente a mesma tela que todo mundo,
        que era a metade boa do ramo que saiu.

        MORDIDA: tire o `background` da regra do «captando» e ele fica idêntico
        ao «no ar» — o terceiro estado some, que é o defeito que esta régua
        existe para pegar. Devolva a animação e ela reprova também: informação
        de estado não pode voltar a morar no movimento.
        """
        fonte = self._fonte()
        trecho = fonte[fonte.index("O 🎙 EM TRÊS ESTADOS"):]
        trecho = trecho[: trecho.index('"""')]
        assert "background:rgba(80,250,123,.14)" in trecho, (
            "o «captando» perdeu o fundo que o separa do «no ar» — os dois "
            "estados viraram um só")
        assert "animation:" not in trecho and "@keyframes" not in trecho, (
            "o estado do microfone voltou a depender de movimento; a decisão "
            "dela de 12/09 é verde FIXO, porque quem se move é a barra ao lado")
