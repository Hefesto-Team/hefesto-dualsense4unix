"""**A CURA ESCRITA E NUNCA LIGADA — e esta ficou órfã por ONZE DIAS.**

`integrations/cura_por_estrada.py` é o único código desta casa que leva o
ambiente do Hefesto a um lançador que não é a Steam. Ele nasceu em 09/09/2026
com um chamador só — o botão «Consertar» do cartão do lançador — e a
LANCADOR-LOCALIZAR-01 (10/09) tirou o botão.

**A DÍVIDA FICOU DECLARADA, e declarar é honesto — mas não é entrega.** A
assimetria que sobrou é estrutural, e é exatamente a queixa dela de 21/09:

    *"O HEFESTO NÃO É IDENTIFICADO E NÃO FUNCIONA LÁ. (…) O PROJETO E SUAS
    FEATURES DEVEM FUNCIONAR INDEPENDENTE DO LANÇADOR SER STEAM."*

A Steam recebia o ambiente VIVO — o daemon rematerializa o `default.env` a cada
transição e o `hefesto-launch.sh` o lê no lançamento. Os outros lançadores
recebiam uma FOTOCÓPIA tirada no dia do clique: um ambiente de 10/09 num produto
que mudou todo dia desde então.
"""

from __future__ import annotations

import pathlib

from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe

LAUNCH_ENV = pathlib.Path("src/hefesto_dualsense4unix/daemon/launch_env.py")


class TestOModuloDeixouDeSerOrfao:
    def test_o_materializador_chama_a_cura(self):
        """**A RÉGUA QUE IMPEDE A ÓRFÃ DE VOLTAR.**

        MORDIDA: tire a chamada de `materialize_launch_env`. O módulo volta a
        existir sem ninguém para acioná-lo, e os outros lançadores voltam à
        fotocópia.
        """
        fonte = LAUNCH_ENV.read_text(encoding="utf-8")
        i = fonte.index("def materialize_launch_env(")
        corpo = fonte[i : fonte.index("\n# ---", i)]
        assert "curar_todas_as_estradas()" in corpo, (
            "o materializador não reescreve as estradas dos outros lançadores")

    def test_a_carona_vai_dentro_do_try(self):
        """A função já promete nunca levantar, e o `except` da borda é a
        segunda rede — *"a materialização quebrada não pode derrubar o start da
        emulação"*, que é o contrato escrito na docstring.

        MORDIDA: mova a chamada para depois do `except`.
        """
        fonte = LAUNCH_ENV.read_text(encoding="utf-8")
        i = fonte.index("def materialize_launch_env(")
        corpo = fonte[i : fonte.index("\n# ---", i)]
        assert corpo.index("curar_todas_as_estradas()") < corpo.index(
            'logger.warning("launch_env_materialize_falhou"'), (
            "a carona saiu de dentro da rede do `try`")


class TestACuraPercorreTodosOsCartoes:
    def test_os_cinco_cartoes_estao_na_lista(self):
        """A Steam NÃO entra — ela tem o atalho de inicialização, que é a
        estrada dela; um override por cima seria a segunda entrega do mesmo
        ambiente.

        MORDIDA: acrescente `steam` à lista. `estradas_do_cartao` já a recusa,
        mas a lista passaria a prometer o que não entrega.
        """
        chaves = [c for c, _ in cpe.cartoes_com_estrada()]
        assert "steam" not in chaves
        assert set(chaves) == {"heroic", "lutris", "retroarch", "dolphin", "mgba"}

    def test_a_lista_e_lida_do_censo_e_nao_digitada(self):
        """**UMA SEGUNDA CÓPIA DIVERGIRIA**, e o sintoma seria o pior desta
        casa: a cura escreveria no arquivo de ontem e a tela diria «pronto».

        MORDIDA: cole a tabela aqui dentro. Esta régua reprova no dia em que o
        censo mudar e a cópia não.
        """
        from hefesto_dualsense4unix.integrations.censo_dos_lancadores import _ONDE

        do_censo = {nome.casefold(): (a, s) for nome, (a, s) in _ONDE.items()}
        assert dict(cpe.cartoes_com_estrada()) == do_censo

    def test_nunca_levanta_com_disco_hostil(self, monkeypatch):
        """Quem chama é a borda de materialização do daemon.

        MORDIDA: tire o `try` do laço.
        """
        def _explode(*a, **k):
            raise OSError("disco hostil")

        monkeypatch.setattr(cpe, "planejar", _explode)
        assert cpe.curar_todas_as_estradas() == ()

    def test_o_cartao_sem_ambiente_e_pulado_sem_levantar(self, monkeypatch, tmp_path):
        """Daemon parado = sem `default.env` = nada a escrever. Não é falha:
        `escrever_a_estrada` LEVANTA nesse caso, de propósito (a frase da recusa
        é a que a tela mostra), e quem roda sem tela tem de pular.

        MORDIDA: chame `escrever_a_estrada` sem conferir o `plano.ambiente`.
        """
        escreveu = []
        monkeypatch.setattr(
            cpe, "escrever_a_estrada", lambda p: escreveu.append(p) or "ok")
        # `pasta_do_ambiente` vazia = a ponte não publicou nada.
        assert cpe.curar_todas_as_estradas(pasta_do_ambiente=tmp_path) == ()
        assert escreveu == []
