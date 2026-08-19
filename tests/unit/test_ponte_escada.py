"""PONTE-ESCADA-01 — a escada tenta em ordem e para de perguntar.

Os testes que MORDEM, um por decisão que a leva tomou:

1. **a ordem** é conferida contra `docs/data/mapa-controles.csv`, não contra o
   gosto de quem escreveu — a assimetria que põe a DualSense no primeiro degrau
   é uma CONTAGEM de linhas do mapa;
2. **a escada não roda em jogo com ponte confirmada.** Um defeito aqui é
   regressão pura: a escada trocando a máscara de um jogo que já funcionava;
3. **nada é confirmado sem alguém confirmar.** Jogo fechado no meio da escada
   não grava "funciona" — a mesma disciplina do balde
   `sem_impedimento_conhecido` do prontuário;
4. **nenhum degrau sobe sozinho com o jogo aberto**, porque cada um recria o
   vpad e paga o R-04.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import ponte_escada as pe

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"


def _linhas_uhid_do_dualsense() -> list[str]:
    """As chaves do mapa que só chegam ao JOGO pela máscara DualSense (`uhid`).

    `plataforma.vpad` fica de fora: é o mecanismo (o gamepad virtual em si),
    não uma feature que o jogo perca ao trocar de máscara.
    """
    with MAPA.open(encoding="utf-8") as fh:
        linhas = list(csv.DictReader(fh))
    return sorted(
        r["chave"]
        for r in linhas
        if r["controle"] == "dualsense"
        and r["chave"] != "plataforma.vpad"
        and "uhid" in (r["cabo_canal"], r["radio_canal"])
    )


class TestAOrdemVemDoMapa:
    def test_a_assimetria_esta_no_mapa_e_nao_na_opiniao(self) -> None:
        """O dado que justifica a ordem existe, e é contável."""
        chaves = _linhas_uhid_do_dualsense()
        assert len(chaves) >= 5, (
            "a ordem da escada se apoia na assimetria 'a máscara DualSense "
            f"carrega o que a Xbox não carrega'; o mapa hoje lista {chaves}"
        )
        # Nomeia, nunca só conta (WRAPPER-EM-TODOS-01).
        for esperada in (
            "movimento.giroscopio.jogo",
            "toque.touchpad",
            "vibracao.rumble.passthrough",
            "luz.replica_output_jogo",
        ):
            assert esperada in chaves

    def test_a_dualsense_vem_antes_da_xbox(self) -> None:
        """Errar para Xbox custa as linhas acima, e custa em silêncio."""
        posicoes = {d.ponte.chave: i for i, d in enumerate(pe.ESCADA)}
        assert posicoes["gamepad/dualsense"] < posicoes["gamepad/xbox"], (
            "a máscara Xbox é uinput 045e:028e e não tem onde pôr nenhuma das "
            f"{len(_linhas_uhid_do_dualsense())} linhas `uhid` do mapa"
        )

    def test_o_primeiro_degrau_e_o_estado_que_ja_funciona(self) -> None:
        assert pe.ESCADA[0].ponte == pe.Ponte(pe.KIND_GAMEPAD, pe.MASCARA_DUALSENSE)
        assert not pe.ESCADA[0].ponte.steam_input


class TestOPrecoDeCadaDegrau:
    def test_o_tramo_ao_vivo_sao_so_as_duas_mascaras(self) -> None:
        """As duas máscaras alcançam um jogo aberto; nativo e Steam Input não."""
        ao_vivo = [d.ponte.chave for d in pe.ESCADA if d.ao_vivo]
        assert ao_vivo == ["gamepad/dualsense", "gamepad/xbox"]

    def test_o_nativo_exige_reabrir_o_jogo(self) -> None:
        """A env congelou no `exec`: com o jogo aberto, nativo = ZERO controles."""
        nativo = next(d for d in pe.ESCADA if d.ponte.kind == pe.KIND_NATIVE)
        assert nativo.exige_reabrir_jogo
        assert pe.como_subir(nativo, jogo_vivo=True) == pe.SUBIR_REABRINDO_O_JOGO

    def test_o_steam_input_exige_fechar_a_steam(self) -> None:
        """`UseSteamControllerConfig` só sobrevive com a Steam fechada."""
        degrau = next(d for d in pe.ESCADA if d.ponte.steam_input)
        assert degrau.exige_fechar_steam
        assert degrau is pe.ESCADA[-1], "o mais caro de tentar fica por último"
        for vivo in (True, False):
            assert pe.como_subir(degrau, jogo_vivo=vivo) == pe.SUBIR_FECHANDO_A_STEAM

    @pytest.mark.parametrize("degrau", pe.ESCADA, ids=lambda d: d.ponte.chave)
    def test_nenhum_degrau_sobe_sozinho_com_o_jogo_aberto(self, degrau) -> None:
        """R-04: recriar o vpad com o jogo aberto arranca o controle da mão dela."""
        assert pe.como_subir(degrau, jogo_vivo=True) != pe.SUBIR_AGORA

    def test_com_o_jogo_fechado_as_mascaras_saem_de_graca(self) -> None:
        assert pe.como_subir(pe.ESCADA[0], jogo_vivo=False) == pe.SUBIR_AGORA
        assert pe.como_subir(pe.ESCADA[1], jogo_vivo=False) == pe.SUBIR_AGORA


class TestAEscadaSoRodaQuandoOProdutoNaoSabe:
    """O ponto que transforma 'achar rápido' em 'nunca mais procurar'."""

    def test_sem_nada_de_pe_comeca_no_primeiro_degrau(self) -> None:
        assert pe.proximo_degrau(ponte_atual=None) is pe.ESCADA[0]

    def test_ponte_confirmada_nao_tem_proximo_degrau(self) -> None:
        assert (
            pe.proximo_degrau(
                ponte_atual=pe.ESCADA[0].ponte, confirmada=pe.ESCADA[0].ponte
            )
            is None
        ), "a escada rodando em jogo com ponte confirmada é regressão pura"

    def test_confirmada_para_a_escada_mesmo_divergindo_do_que_esta_de_pe(self) -> None:
        """Divergir do carimbo é assunto do prontuário, não licença para
        recomeçar a escada num jogo que já foi resolvido."""
        assert (
            pe.proximo_degrau(
                ponte_atual=pe.ESCADA[0].ponte, confirmada=pe.ESCADA[2].ponte
            )
            is None
        )

    def test_a_ponte_de_pe_e_a_posicao_na_escada(self) -> None:
        assert pe.proximo_degrau(ponte_atual=pe.ESCADA[0].ponte) is pe.ESCADA[1]
        assert pe.proximo_degrau(ponte_atual=pe.ESCADA[1].ponte) is pe.ESCADA[2]
        assert pe.proximo_degrau(ponte_atual=pe.ESCADA[2].ponte) is pe.ESCADA[3]

    def test_a_escada_acaba_e_nao_da_a_volta(self) -> None:
        """Voltar ao primeiro degrau é o laço destrói-e-recria com outro nome."""
        assert pe.proximo_degrau(ponte_atual=pe.ESCADA[-1].ponte) is None

    def test_ponte_que_nao_e_degrau_nao_e_corrigida(self) -> None:
        """Ela escolheu na mão uma tupla que a escada não conhece."""
        fora = pe.Ponte(pe.KIND_GAMEPAD, pe.MASCARA_XBOX, steam_input=True)
        assert pe.indice_do_degrau(fora) == -1
        assert pe.proximo_degrau(ponte_atual=fora) is None


class TestOQueConfirmaEOQueNao:
    def test_o_silencio_com_o_jogo_vivo_confirma_a_ponte_de_pe(self) -> None:
        assert (
            pe.confirmacao_por_silencio(
                ponte_atual=pe.ESCADA[1].ponte,
                ultimo_gesto=1000.0,
                agora=1000.0 + pe.SILENCIO_CONFIRMA_SEC,
                jogo_vivo=True,
            )
            is pe.ESCADA[1].ponte
        )

    def test_silencio_curto_nao_confirma(self) -> None:
        assert (
            pe.confirmacao_por_silencio(
                ponte_atual=pe.ESCADA[1].ponte,
                ultimo_gesto=1000.0,
                agora=1000.0 + pe.SILENCIO_CONFIRMA_SEC - 0.01,
                jogo_vivo=True,
            )
            is None
        )

    def test_jogo_fechado_no_meio_da_escada_nao_confirma_nada(self) -> None:
        """Ela foi embora — isso não é ela aprovando a ponte."""
        assert (
            pe.confirmacao_por_silencio(
                ponte_atual=pe.ESCADA[1].ponte,
                ultimo_gesto=1000.0,
                agora=1000.0 + 10 * 3600,
                jogo_vivo=False,
            )
            is None
        )
        # ... e a ponte de pé continua sendo a posição na escada, então o
        # próximo lançamento retoma de onde parou.
        assert pe.proximo_degrau(ponte_atual=pe.ESCADA[1].ponte) is pe.ESCADA[2]

    def test_o_silencio_nao_recarimba_o_que_ja_foi_confirmado(self) -> None:
        """Recarimbar a cada volta apagaria a data, que é o que o carimbo tem."""
        assert (
            pe.confirmacao_por_silencio(
                ponte_atual=pe.ESCADA[0].ponte,
                ultimo_gesto=0.0,
                agora=1e9,
                jogo_vivo=True,
                confirmada=pe.ESCADA[0].ponte,
            )
            is None
        )

    def test_sem_ponte_de_pe_nao_ha_o_que_confirmar(self) -> None:
        assert (
            pe.confirmacao_por_silencio(
                ponte_atual=None, ultimo_gesto=0.0, agora=1e9, jogo_vivo=True
            )
            is None
        )


class TestUmaGavetaSO:
    """A confirmação mora no perfil. Este módulo não abre uma segunda."""

    def test_os_nomes_de_origem_sao_os_do_esquema(self) -> None:
        from hefesto_dualsense4unix.profiles import schema

        assert pe.POR_GESTO == schema.CONFIRMADA_POR_GESTO
        assert pe.POR_SILENCIO == schema.CONFIRMADA_POR_SILENCIO
        assert pe.POR_ESCOLHA_DELA == schema.CONFIRMADA_POR_ESCOLHA
        assert set(pe.CONFIRMACOES) == {
            schema.CONFIRMADA_POR_GESTO,
            schema.CONFIRMADA_POR_SILENCIO,
            schema.CONFIRMADA_POR_ESCOLHA,
        }

    def test_a_escada_nao_grava_em_disco(self) -> None:
        """Nenhuma porta de escrita: a gaveta é o perfil, e ela tem dono."""
        publicado = set(pe.__all__)
        assert not {n for n in publicado if "livro" in n or "gravar" in n}
        assert not hasattr(pe, "gravar_livro")

    def test_o_carimbo_do_perfil_vira_ponte_sem_traducao_espalhada(self) -> None:
        from hefesto_dualsense4unix.profiles.schema import PonteConfirmada

        carimbo = PonteConfirmada(kind="gamepad", gamepad_flavor="xbox")
        assert pe.ponte_do_carimbo(carimbo) == pe.ESCADA[1].ponte

        nativo = PonteConfirmada(kind="native")
        assert pe.ponte_do_carimbo(nativo) == pe.ESCADA[2].ponte

        com_steam = PonteConfirmada(
            kind="gamepad", gamepad_flavor="dualsense", steam_input=True
        )
        assert pe.ponte_do_carimbo(com_steam) == pe.ESCADA[3].ponte

    def test_sem_carimbo_nao_ha_ponte(self) -> None:
        assert pe.ponte_do_carimbo(None) is None


class TestAPonteSaiDoPerfilSemVocabularioNovo:
    def test_a_ponte_e_a_tupla_que_o_disco_ja_guardava(self) -> None:
        from hefesto_dualsense4unix.profiles.schema import (
            MatchCriteria,
            Profile,
            ProfileModeConfig,
        )

        perfil = Profile(
            name="sackboy",
            match=MatchCriteria(window_class=["steam_app_1599660"]),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
        )
        assert pe.ponte_do_perfil(perfil, na_allowlist=False) == pe.ESCADA[0].ponte
        assert pe.ponte_do_perfil(perfil, na_allowlist=True) == pe.ESCADA[-1].ponte

    def test_perfil_sem_modo_nao_opina(self) -> None:
        class Falso:
            mode = None

        assert pe.ponte_do_perfil(Falso(), na_allowlist=False) is None
