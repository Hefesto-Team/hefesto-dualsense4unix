"""**MASCARA-CONTAGIO-01, 21/09/2026 — o latch que se realimentava pelo gesto.**

A queixa de uso, em caixa alta:

    *"POR EXEMPLO O PERFIL PRAGMATA ALGUMAS VEZES ALTEREI O MODO DE CONEXÃO DOS
    CONTROLES E MÁSCARAS MAS ALGO O MUDA NOVAMENTE PRA XBOX SEMPRE QUE EU O
    INICIO. OU O PERFIL NAO TA SALVANDO OU TEMOS ALGUM TESTE OU ALGO ALÉM QUE
    TÁ ZUANDO ISSO."*

O perfil ESTAVA salvando. Medido na bancada naquele dia, com os arquivos
na mão:

    gamepad_emulation.flag ......... xbox   (o padrão da MÁQUINA)
    controller_masks.json .......... os quatro em dualsense
    future_knight.json ............. mode.gamepad_flavor: "xbox"
    pragmata.json .................. mode.gamepad_flavor: null

`future_knight.json` é o ÚNICO dos 29 perfis do usuário com máscara declarada, e ao
ativá-lo o daemon promovia a escolha de UM JOGO a padrão da máquina. **A volta
não existia**: perfil com `gamepad_flavor: null` saía na primeira linha sem
desfazer nada. E o gesto que existia para desfazer — o chip «Sony DualSense» —
**re-carimbava o `xbox` da memória a cada clique**, porque ele não manda
`flavor` desde MODO-DE-CONEXAO-01 e o daemon caía em `config.gamepad_flavor`.

É a mesma classe do CAMINHO-CONTAGIO-01 (19/09), no outro eixo — e a ordem de produto
daquele dia nomeava os dois: *"sim tudo dualsense, tudo ligado mascara dualsense
por default mas esse vazamento me preocupa"*.
"""

from __future__ import annotations

import ast
import pathlib

LIFECYCLE = pathlib.Path("src/hefesto_dualsense4unix/daemon/lifecycle.py")
GAMEPAD = pathlib.Path("src/hefesto_dualsense4unix/daemon/subsystems/gamepad.py")


class TestPonto1AMascaraDeUmJogoNaoViraPadraoDaMaquina:
    def test_o_pedido_do_perfil_nao_chama_mais_o_gravador(self):
        """MORDIDA: devolva `self._gravar_mascara_do_perfil(flavor)` ao"""
        fonte = LIFECYCLE.read_text(encoding="utf-8")
        i = fonte.index("    def _pedir_mascara_do_perfil(")
        corpo = fonte[i : fonte.index("\n    def ", i + 10)]
        assert "self._gravar_mascara_do_perfil(" not in corpo, (
            "o perfil voltou a promover a própria máscara a padrão da máquina")

    def test_o_gravador_fica_como_nota_datada_e_nao_escreve(self, monkeypatch):
        """A decisão de 22/08 virou nota datada: o gravador existe e não grava nada."""
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon
        from hefesto_dualsense4unix.utils import session

        def _escreveu(*a, **k):
            raise AssertionError("o gravador voltou a escrever o padrão da máquina")

        monkeypatch.setattr(session, "save_gamepad_emulation", _escreveu)
        for flavor in ("xbox", "dualsense", None):
            assert Daemon._gravar_mascara_do_perfil(object(), flavor) is None


class TestPonto2OGestoQueNaoFalaDeMascaraNaoEscreveMascara:
    def _desfecho(self) -> str:
        fonte = GAMEPAD.read_text(encoding="utf-8")
        i = fonte.index("def start_gamepad_emulation_desfecho(")
        return fonte[i : fonte.index("\ndef ", i + 10)]

    def test_a_escrita_do_flag_depende_do_flavor_ter_vindo(self):
        """O ponto exato do latch: sem esta guarda, `key` vem da MEMÓRIA e o
        clique do usuário em «Sony DualSense» regrava o `xbox` que ele deveria
        desfazer.

        MORDIDA: troque o `if flavor is not None` por `if True`.
        """
        corpo = self._desfecho()
        i = corpo.index('if origin == "manual":')
        bloco = corpo[i : i + 2200]
        assert "if flavor is not None:" in bloco, (
            "o gesto sem máscara voltou a escrever máscara")
        assert "save_gamepad_emulation(True, key)" in bloco

    def test_o_liga_desliga_continua_gravando(self):
        """**O EIXO DO LIGA/DESLIGA NÃO PODE CAIR JUNTO** (AUTO-01.1)."""
        corpo = self._desfecho()
        i = corpo.index('if origin == "manual":')
        bloco = corpo[i : i + 2200]
        assert "load_gamepad_preference" in bloco, (
            "o ramo sem máscara não relê o disco — ou inventa, ou perde o "
            "ligado dela")
        assert "save_gamepad_emulation(True, gravada)" in bloco


class TestPonto3ODevolvedorDoXboxDoVazamento:
    def test_o_xbox_volta_ao_default_uma_vez(self, tmp_path, monkeypatch):
        """MORDIDA: faça a função devolver `lido` sempre. O flag dela continua"""
        from hefesto_dualsense4unix.daemon import lifecycle

        escritos: list[tuple[bool, str | None]] = []
        import hefesto_dualsense4unix.utils.session as sessao

        monkeypatch.setattr(
            sessao, "save_gamepad_emulation",
            lambda enabled, flavor=None: escritos.append((enabled, flavor)))

        assert lifecycle._a_mascara_dela_sem_o_vazamento("xbox") == "dualsense"
        assert escritos == [(True, "dualsense")], (
            "a devolução não chegou ao disco — o próximo boot lê `xbox` de novo")

    def test_o_dualsense_nao_e_tocado(self, monkeypatch):
        """**A ASSIMETRIA É DE PROPÓSITO.** Só o valor que o vazamento escrevia"""
        from hefesto_dualsense4unix.daemon import lifecycle
        import hefesto_dualsense4unix.utils.session as sessao

        escritos: list[object] = []
        monkeypatch.setattr(
            sessao, "save_gamepad_emulation",
            lambda *a, **k: escritos.append((a, k)))

        assert lifecycle._a_mascara_dela_sem_o_vazamento("dualsense") == "dualsense"
        assert escritos == []

    def test_o_boot_passa_a_flag_pela_devolucao(self):
        """**A CURA ESCRITA E NUNCA LIGADA** é o defeito mais caro desta casa."""
        fonte = LIFECYCLE.read_text(encoding="utf-8")
        i = fonte.index("gp_enabled, gp_flavor = load_gamepad_emulation()")
        bloco = fonte[i : i + 900]
        assert "_a_mascara_dela_sem_o_vazamento(gp_flavor)" in bloco, (
            "o boot não passa a flag pela devolução — a função existe e "
            "ninguém a chama")
        assert bloco.index("_a_mascara_dela_sem_o_vazamento") < bloco.index(
            "self.config.gamepad_flavor = gp_flavor"
        ), "a devolução vem DEPOIS de o slot da sessão já ter o xbox"


class TestOsDoisEixosTemAMesmaForma:
    def test_a_irma_do_caminho_continua_la(self):
        """As duas funções são irmãs e a segunda foi escrita olhando a"""
        arvore = ast.parse(LIFECYCLE.read_text(encoding="utf-8"))
        definidas = {n.name for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef)}
        chamadas = {
            getattr(c.func, "id", getattr(c.func, "attr", ""))
            for c in ast.walk(arvore) if isinstance(c, ast.Call)}
        for irma in ("_a_escolha_dela_sem_o_vazamento", "_a_mascara_dela_sem_o_vazamento"):
            assert irma in definidas, f"{irma} sumiu"
            assert irma in chamadas, f"{irma} existe e ninguém a chama"
