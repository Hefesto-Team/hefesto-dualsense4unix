"""A-LUZ-DO-MIC-ESPELHA-O-BOTAO-01 — a aba Controle diz QUEM te ouve.

**A decisão dela, 19/09/2026.** Perguntada com quatro opções depois de a
medição mostrar o defeito, ela escolheu *«Espelhar o botão E consertar a
tela»* — as duas metades:

===========================  ==============================================
superfície                   o que passa a dizer
===========================  ==============================================
a luz do controle            o estado do MEU microfone: mudo apaga, ligado
                             ACENDE, ligado com alguém de fora gravando e
                             entrando som PISCA
a aba Controle               QUEM está ouvindo, por escrito
===========================  ==============================================

A primeira metade é do `daemon/subsystems/luz_do_mic.py`, e quem a guarda é o
`test_a_luz_do_mic_diz_quem_te_escuta.py`. **Esta régua é da SEGUNDA**, e ela
existe porque a primeira criou o buraco: com a luz acesa nos dois casos, ela
sozinha deixou de distinguir *"ligado"* de *"ligado e alguém te ouvindo"* —
alguém tem de dizer a diferença, por escrito.

A CADEIA INTEIRA, e cada degrau tem um teste aqui:

1. o laço da luz LEMBRA quem ouve cada controle, e esquece quem sai da mesa;
2. o `state_full` publica isso em `audio.ouvintes_do_mic` — ausência é
   *"não perguntei"*, e `[]` é *"perguntei, e não há ninguém"*;
3. um dono só vira a lista em frase (`mesa_viva.frase_de_quem_te_ouve`);
4. o pacote da aba emite `mic-ressalva` com essa frase, em TODO tique;
5. o gerador tem o endereço dentro da moldura do microfone.

**A MORDIDA de cada teste está na docstring dele.**
"""

from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

ABA02 = RAIZ / "src/hefesto_dualsense4unix/interface/aba02.py"
IPC = RAIZ / "src/hefesto_dualsense4unix/daemon/ipc_handlers.py"

UM = "aa:bb:cc:00:00:01"


def _moldura_do_microfone(fonte: str) -> str:
    """O pedaço do gerador que desenha a moldura do microfone, e só ele.

    A ÂNCORA É A TAG, E NÃO O ATRIBUTO SOZINHO: `data-bloco="microfone"`
    aparece ANTES no CSS (as regras do `data-apagado`), e fatiar por ele
    devolvia a folha de estilo — uma régua que mede o pedaço errado dá verde
    ou vermelho sobre outra coisa, que é a família de instrumento falso que
    esta casa mais paga.
    """
    inicio = fonte.index('class="moldura" data-bloco="microfone"')
    return fonte[inicio: fonte.index('data-bloco="alto-falante"', inicio)]


class TestODaemonLembraQuemOuve:
    """O laço da luz guarda a lista que ele JÁ perguntou."""

    def test_lembra_a_sala_vazia_e_esquece_quem_sai(self) -> None:
        """MORDIDA: guarde `None` no lugar da lista vazia.

        `[]` e `None` são respostas DIFERENTES, e a tela as escreve diferente:
        a vazia vira *"ninguém está te ouvindo ainda"*, a ausência não vira
        frase nenhuma. Colapsá-las devolveria o defeito de 19/09 à tela, no
        mesmo dia em que ele saiu da luz.
        """
        from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as luz

        luz._lembrar_quem_ouve(UM, [])
        assert luz.quem_ouve_este_mic(UM) == []
        luz._lembrar_quem_ouve(UM, ["Discord"])
        assert luz.quem_ouve_este_mic(UM) == ["Discord"]
        luz._lembrar_quem_ouve(UM, None)
        assert luz.quem_ouve_este_mic(UM) is None

    def test_quem_nunca_foi_perguntado_e_nao_sei(self) -> None:
        """MORDIDA: devolva `[]` para quem não está no dicionário.

        `[]` é uma AFIRMAÇÃO — *"medi, e ninguém te ouve"*. Para um controle
        que acabou de chegar isso põe a frase na tela sem ninguém ter
        perguntado ao servidor de som, que é a família de defeito que esta
        casa persegue por escrito: a ausência de dado virando afirmação.
        """
        from hefesto_dualsense4unix.daemon.subsystems import luz_do_mic as luz

        assert luz.quem_ouve_este_mic("ff:ff:ff:00:00:ff") is None
        assert luz.quem_ouve_este_mic("") is None


class TestOIpcPublica:
    """O que o laço sabe chega à tela pelo `state_full`."""

    def test_a_chave_sai_do_mesmo_lugar_que_a_luz(self) -> None:
        """MORDIDA: pergunte à PEÇA A de novo, aqui.

        Perguntar do lado do IPC seriam dois `pactl` por tique de TELA, dentro
        do laço que serve o IPC e reafirma o report de saída — e duas respostas
        que divergem no primeiro segundo em que uma delas chega atrasada. O
        laço da luz já perguntou a 1 Hz; publicar é ler um `dict`.
        """
        fonte = IPC.read_text(encoding="utf-8")
        assert "quem_ouve_este_mic" in fonte
        assert 'status["ouvintes_do_mic"]' in fonte
        # E a leitura é a do MÓDULO da luz, não uma chamada nova à PEÇA A.
        assert "quem_ouve_agora" not in fonte


class TestAPalavraTemUmDono:
    """Uma cópia só das palavras, e ela cabe numa linha."""

    def test_a_sala_vazia_vira_a_frase_que_faltava(self) -> None:
        """MORDIDA: devolva `""` para a lista vazia.

        É O CASO QUE ORGANIZOU O DIA: o microfone dela estava LIGADO e nenhum
        app gravava. A luz agora acende nesse estado — e sem esta frase a tela
        não tem como dizer que acesa não quer dizer *"alguém te escuta"*.
        """
        import mesa_viva

        assert mesa_viva.frase_de_quem_te_ouve([]) == mesa_viva.NINGUEM_TE_OUVE
        assert mesa_viva.NINGUEM_TE_OUVE

    def test_a_ausencia_nao_vira_frase(self) -> None:
        """MORDIDA: trate `None` como lista vazia.

        *"Não perguntei"* não é *"ninguém ouve"*. `""` faz a `.ressalva` sumir
        sem cobrar um pixel (D-02 dela, *"linha fixa só quando HÁ ressalva"*),
        que é o comportamento honesto de quem não sabe.
        """
        import mesa_viva

        for cru in (None, "", 0, False, {}, "Discord"):
            assert mesa_viva.frase_de_quem_te_ouve(cru) == "", cru

    def test_os_nomes_aparecem(self) -> None:
        """MORDIDA: devolva sempre a contagem, sem nomear ninguém.

        A decisão dela é *"QUEM está ouvindo"*, e um *"1 programa está te
        ouvindo"* sobre um Discord aberto responde outra pergunta — a de
        quantos, que ninguém fez.
        """
        import mesa_viva

        assert mesa_viva.frase_de_quem_te_ouve(["Discord"]) == (
            "Discord está te ouvindo.")
        assert mesa_viva.frase_de_quem_te_ouve(["Discord", "OBS"]) == (
            "Discord e OBS estão te ouvindo.")
        assert mesa_viva.frase_de_quem_te_ouve(("Chrome",)) == (
            "Chrome está te ouvindo.")

    def test_nenhuma_frase_dobra_a_linha(self) -> None:
        """MORDIDA: tire o recuo para a contagem e deixe os nomes crescerem.

        MEDIDO no Chrome headless sobre `mockup/02-controles.html`, na janela
        do produto (1180px), em 19/09/2026: a coluna do som tem 281px, uma
        linha da `.ressalva` custa 17,3px e o card vai de 329,6 a 351,9 com a
        linha escrita, **sem o quadro rolar**. A SEGUNDA linha é que não cabe:
        a coluna do som é uma das duas que mandam na altura, e um bloco que
        dobra já tirou o P4 da tela dela em 30/08.

        Esta régua varre os arranjos que a mesa de quatro produz — inclusive
        nomes longos de verdade, como os que o `pactl` devolve.
        """
        import mesa_viva

        nomes = ["Discord", "OBS Studio", "Google Chrome input",
                 "org.telegram.desktop", "speech-dispatcher-espeak-ng"]
        arranjos: list[list[str]] = [nomes[:n] for n in range(1, len(nomes) + 1)]
        arranjos.append([])
        arranjos.append(["um-nome-de-aplicativo-absurdamente-comprido-mesmo"])
        for arranjo in arranjos:
            frase = mesa_viva.frase_de_quem_te_ouve(arranjo)
            assert len(frase) <= mesa_viva.LIMITE_DA_LINHA_DE_QUEM_OUVE, (
                f"{arranjo} vira uma frase de {len(frase)} caracteres "
                f"({frase!r}) — acima do limite medido, a linha dobra e o "
                f"card cresce o dobro"
            )

    def test_acima_do_limite_a_contagem_continua_verdadeira(self) -> None:
        """MORDIDA: devolva a frase vazia quando os nomes não couberem.

        Recuar para *"não sei"* sobre um fato que o daemon MEDIU seria perder
        dado por causa de largura — e justamente no arranjo mais importante,
        o de muita gente ouvindo. A contagem cabe sempre e não mente.
        """
        import mesa_viva

        muitos = [f"aplicativo-numero-{n}" for n in range(7)]
        assert mesa_viva.frase_de_quem_te_ouve(muitos) == (
            "7 programas estão te ouvindo.")
        assert mesa_viva.frase_de_quem_te_ouve(
            ["um-nome-de-aplicativo-absurdamente-comprido-mesmo"]
        ) == "Um programa está te ouvindo."


class TestOPacoteEmite:
    """A aba lê do daemon, e não do seu próprio palpite.

    **A BANCADA ANDOU NA FRENTE, e por isso o campo é CONDICIONAL.** O
    endereço `mic-ressalva` existe em `mockup/02-controles.html` e a página
    publicada ainda não o tem — a aba 02 só recebe pelo `--publicar 02`, que é
    ato dela. Até lá o pacote **não** emite a chave, senão ela entra em
    `casamento.medir(...)["orfaos"]` e conta em `cobertura.pintados` uma
    pintura que não acontece.

    Estes testes FINGEM a publicação (é o que `com_a_pagina_publicada` faz no
    `test_a_aba_controles_reusa_o_motor.py`), e o teste logo abaixo guarda o
    outro lado: sem publicar, a chave não sai.
    """

    def _campos(self, audio: dict[str, Any], *,
                publicada: bool = True) -> dict[str, Any]:
        import pacotes
        import pacotes.a02_controles as a02

        ctx = pacotes.Contexto(
            state={}, mesa=[], estados={},
            conectados=[{"uniq": UM, "transport": "usb", "connected": True,
                         "inputs": {}, "audio": audio,
                         "speaker": {"volume": 100, "muted": False}}])
        antes = a02._ENDERECOS
        if publicada:
            a02._ENDERECOS = frozenset(
                a02._enderecos_da_pagina() or ()) | {"mic-ressalva"}
        try:
            cards = (a02.pacote(ctx).get("cards") or {}).values()
            for valores in cards:
                if "mic-selo" in valores:
                    return valores
        finally:
            a02._ENDERECOS = antes
        return {}

    def test_enquanto_ela_nao_publicar_a_chave_nao_sai(self) -> None:
        """MORDIDA: emita `mic-ressalva` fora do `_so_se_a_pagina_tiver`.

        A bancada é DELA. Emitir para um endereço que a página publicada não
        tem põe a chave nos órfãos do casamento e faz o pacote contar uma
        pintura que não acontece — e quem reprova é o
        `test_o_pacote_so_emite_endereco_que_a_pagina_tem`, medido nesta
        árvore em 19/09/2026 com a frase *"o pacote emitiu ['mic-ressalva'] e
        a página publicada não tem onde pô-los"*.

        NO DIA EM QUE ELA PUBLICAR, este teste morre sozinho junto com a
        condição — e é o desfecho certo: a régua some quando o motivo dela
        some.
        """
        import pacotes.a02_controles as a02

        if "mic-ressalva" in a02._enderecos_da_pagina():  # pragma: no cover
            import pytest

            pytest.skip("ela publicou a aba 02 — a condição já caiu")
        campos = self._campos(
            {"mic_mudo": False, "canal_ativo": True, "ouvintes_do_mic": []},
            publicada=False)
        assert campos, "o card nem saiu — a régua ficaria verde sobre nada"
        assert "mic-ressalva" not in campos

    def test_o_campo_sai_com_a_frase_do_dono(self) -> None:
        """MORDIDA: monte a frase aqui, em vez de chamar o dono.

        Uma segunda cópia das palavras diverge da primeira no dia em que uma
        delas for corrigida — e foi exatamente assim que o «Sem toque» desta
        aba já mentiu.
        """
        base = {"mic_mudo": False, "canal_ativo": True}
        vazia = self._campos({**base, "ouvintes_do_mic": []})
        assert vazia["mic-ressalva"] == "Ninguém está te ouvindo ainda."
        com_um = self._campos({**base, "ouvintes_do_mic": ["Discord"]})
        assert com_um["mic-ressalva"] == "Discord está te ouvindo."

    def test_sem_leitura_a_linha_some(self) -> None:
        """MORDIDA: omita a chave quando o daemon não publicou a lista.

        A chave tem de ir em TODO tique: sem ela a frase velha fica pendurada
        na tela para sempre — a tela diria *"Discord está te ouvindo"* com o
        Discord fechado, que é o defeito oposto e pior. `monta.NADA_A_DIZER`
        é o que faz a `.ressalva` sumir sem cobrar um pixel.
        """
        import monta

        campos = self._campos({"mic_mudo": False, "canal_ativo": True})
        assert "mic-ressalva" in campos
        assert campos["mic-ressalva"] == monta.NADA_A_DIZER


class TestOGeradorTemOEndereco:
    """Sem endereço, o pacote escreve no vazio e a tela não muda."""

    def _fonte(self) -> str:
        return ABA02.read_text(encoding="utf-8")

    def test_a_linha_existe_e_mora_no_bloco_do_microfone(self) -> None:
        """MORDIDA: tire o `monta_ressalva("mic-ressalva")` do gerador.

        O campo continuaria saindo a cada tique, e o pacote continuaria
        verde — escrevendo num endereço que a página não tem. É o defeito
        que esta casa já mediu como *"verde sobre dois botões mortos"*.

        E o LUGAR é requisito: a frase responde sobre o MICROFONE, e no bloco
        do alto-falante ela responderia sobre a coisa errada.
        """
        fonte = self._fonte()
        assert 'monta_ressalva("mic-ressalva")' in fonte
        bloco = _moldura_do_microfone(fonte)
        assert 'monta_ressalva("mic-ressalva")' in bloco, (
            "a linha de quem ouve saiu da moldura do microfone")

    def test_a_pagina_da_bancada_carrega_o_endereco(self) -> None:
        """MORDIDA: gere a página sem rodar `aba02.py` de novo.

        O gerador e a página são dois arquivos, e é entre eles que esta casa
        já perdeu cura: mudar o gerador sem regerar deixa a bancada com o
        desenho de ontem, e o `check_o_desenho_aprovado.py` compara a bancada
        com o PUBLICADO — não com o gerador.
        """
        pagina = RAIZ / "mockup" / "02-controles.html"
        if not pagina.exists():  # pragma: no cover - árvore sem a bancada
            import pytest

            pytest.skip("a bancada não está nesta árvore")
        html = pagina.read_text(encoding="utf-8")
        assert 'data-campo="mic-ressalva"' in html
        assert 'class="ressalva" data-campo="mic-ressalva"' in html

    def test_a_dica_diz_o_que_a_luz_acesa_quer_dizer(self) -> None:
        """MORDIDA: tire da dica a frase que separa acesa de ouvida.

        A luz acesa passou a querer dizer *"ligado"*, e não *"alguém te
        ouve"* — a inversão é a decisão dela, e uma dica que continue
        prometendo a leitura antiga ensina errado quem pega o controle pela
        primeira vez, que é justamente para quem ela escreveu esta dica.
        """
        fonte = self._fonte()
        bloco = _moldura_do_microfone(fonte)
        assert "não que alguém esteja ouvindo" in bloco
