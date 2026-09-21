"""MIC-NA-TELA-01 — o que sobrou quando o 🎙 trocou de ATO.

**ESTE ARQUIVO MEDIA UM BOTÃO QUE NÃO EXISTE MAIS — 21/09/2026.** Ele guardava
os três estados da LUZ DO PLÁSTICO no 🎙, pedido dela em 10/09. Em 21/09 ela
trocou o ato do mesmo botão:

    "SE EU ATIVAR COM UM CLICK E ELE FICAR VERDE ELE TÁ ATIVADO E SEGUE ASSIM
     ATÉ EU DESATIVAR CLICANDO NOVAMENTE E ELE FICANDO CINZA. POR DEFAULT
     SEGUE DESLIGADO"

Os dois não cabem num elemento só, e a aritmética é dela: o microfone nasce
ATIVO (ordem de 18/09), então a luz deixaria o botão verde **sem ela ter
clicado** — o contrário exato do que ela mandou. Saíram com o ato o campo
`mic-botao-estado`, o tradutor `mesa_viva.estado_do_botao_do_mic`, as duas
palavras de CSS e as réguas que os mediam.

**O QUE FICOU, e por isso este arquivo não morre:** a memória da luz no DAEMON
(o LED vermelho do plástico continua fazendo os quatro estados, e ele é
hardware) e o endereço vivo do 🎙 — a lição de 06/09, que a cor não pode vir
do gerador, vale para qualquer coisa que o botão venha a vestir.

Quem mede a trava nova é `test_o_mic_alterna_e_fica.py`.

O enunciado antigo, para quem for ler o histórico:

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

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

ABA02 = RAIZ / "src/hefesto_dualsense4unix/interface/aba02.py"


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
        assert 'data-campo="mic-retorno"' in fonte
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
