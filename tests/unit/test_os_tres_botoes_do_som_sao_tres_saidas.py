"""**Os TRÊS botões da fileira do som fazem TRÊS coisas — 21/09/2026.**"""

from __future__ import annotations

import pathlib

PACOTE = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py")


def _ramo_do_gesto() -> str:
    fonte = PACOTE.read_text(encoding="utf-8")
    i = fonte.index("def rota(ctx: Contexto")
    return fonte[i : fonte.index("\n@gesto", i)]


class TestOTerceiroBotaoMandaoSomParaATV:
    def test_o_ramo_nada_liga_o_laco(self):
        """MORDIDA: tire a linha. O terceiro botão volta a calar o controle sem"""
        corpo = _ramo_do_gesto()
        i = corpo.index("if qual == ROTA_NADA_NO_CONTROLE:")
        ramo = corpo[i : corpo.index("if qual == ROTA_OUVIR_JUNTO:", i)]
        assert "som_do_controle_na_tv.ligar(uniq)" in ramo, (
            "«Tudo na TV» não manda o som do controle para a TV")

    def test_o_laco_sobe_depois_de_o_mix_cair(self):
        """**COM OS DOIS SENTIDOS DE PÉ O SOM DÁ A VOLTA:** o `mix` leva o PC ao"""
        corpo = _ramo_do_gesto()
        i = corpo.index("if qual == ROTA_NADA_NO_CONTROLE:")
        ramo = corpo[i : corpo.index("if qual == ROTA_OUVIR_JUNTO:", i)]
        assert ramo.index("devolver_o_som_do_pc(") < ramo.index(
            "som_do_controle_na_tv.ligar(uniq)"), (
            "o laço sobe antes de o caminho de volta cair — o som dá a volta")

    def test_os_outros_dois_botoes_fecham_o_laco(self):
        """**OS TRÊS BOTÕES SÃO UM ESTADO SÓ.** Um laço que sobrevivesse à troca"""
        corpo = _ramo_do_gesto()
        assert corpo.count("som_do_controle_na_tv.desligar(uniq)") == 2, (
            "algum dos outros dois botões não fecha o laço da TV")
        junto = corpo.index("if qual == ROTA_OUVIR_JUNTO:")
        assert "som_do_controle_na_tv.desligar(uniq)" in corpo[junto:junto + 900], (
            "«No controle e na TV» não fecha o laço do terceiro botão")


class TestOLacoLeOMonitorEEmEstereo:
    def test_a_captura_e_o_monitor_do_sink(self):
        """**UM SINK NÃO SE LÊ; LÊ-SE O MONITOR DELE.** Pedir o nome cru faz o"""
        from hefesto_dualsense4unix.integrations import laco_de_audio
        from hefesto_dualsense4unix.integrations import som_do_controle_na_tv

        pedidos: list[dict] = []
        original = laco_de_audio.Lacos.ligar
        try:
            laco_de_audio.Lacos.ligar = (
                lambda self, chave, **kw: pedidos.append(kw) or True)
            assert som_do_controle_na_tv.ligar("aa:bb:cc:00:00:01")
        finally:
            laco_de_audio.Lacos.ligar = original

        assert pedidos, "o módulo não chegou a pedir a laçada"
        assert pedidos[0]["captura"] == "hefesto_som_000001.monitor"
        assert pedidos[0]["canais"] == 2
        assert pedidos[0]["mapa"] == "[ FL FR ]"

    def test_uniq_ilegivel_nao_abre_laco_anonimo(self):
        """Sem endereço não há de quem seja o nó. Abrir um laço anônimo poria o"""
        from hefesto_dualsense4unix.integrations import som_do_controle_na_tv

        assert som_do_controle_na_tv.ligar("") is False
        assert som_do_controle_na_tv.ligar("xyz") is False


class TestOsDoisEixosDividemODono:
    def test_o_microfone_e_a_tv_usam_o_mesmo_dono(self):
        """Dois donos do mesmo estado divergem — um lembra de matar no fecho, o"""
        from hefesto_dualsense4unix.integrations import (
            monitor_do_microfone,
            som_do_controle_na_tv,
        )
        from hefesto_dualsense4unix.integrations.laco_de_audio import Lacos

        assert isinstance(monitor_do_microfone._LACOS, Lacos)
        assert isinstance(som_do_controle_na_tv._LACOS, Lacos)
        assert (monitor_do_microfone._LACOS.familia
                != som_do_controle_na_tv._LACOS.familia), (
            "as duas famílias têm o mesmo nome — os laços se confundiriam no "
            "grafo e no `desligar`")

    def test_o_fecho_alcanca_as_duas_familias(self):
        """MORDIDA: faça `fechar_tudo` varrer só a primeira família."""
        from hefesto_dualsense4unix.integrations import laco_de_audio

        fonte = pathlib.Path(laco_de_audio.__file__).read_text(encoding="utf-8")
        assert "for familia in _FAMILIAS" in fonte
        assert "atexit.register(fechar_tudo)" in fonte
