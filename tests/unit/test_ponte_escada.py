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

import ast
import csv
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import ponte_escada as pe

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
PRODUTO = RAIZ / "src" / "hefesto_dualsense4unix"


def _chamadas_a(nome: str) -> dict[str, list[ast.Call]]:
    """Todo `…nome(…)` do produto, agrupado por arquivo (caminho da raiz).

    LÊ a árvore sintática, e é isso que separa esta régua das onze que esta
    casa já reprovou por *digitarem o que deviam ler*: `def nome(...)`, a
    palavra num comentário e a menção numa docstring NÃO contam — só a
    chamada conta.
    """
    achados: dict[str, list[ast.Call]] = {}
    for arquivo in sorted(PRODUTO.rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Call) and _nome_curto(no.func) == nome:
                achados.setdefault(str(arquivo.relative_to(RAIZ)), []).append(no)
    return achados


def _nome_curto(no: ast.expr | None) -> str | None:
    """O último nome de uma expressão: `a.b.c` -> `"c"`, `c` -> `"c"`.

    Serve para `confirmar_ponte` e `ProfileManager(...).confirmar_ponte`
    contarem como a MESMA chamada, sem depender do estilo do import.
    """
    if isinstance(no, ast.Attribute):
        return no.attr
    if isinstance(no, ast.Name):
        return no.id
    return None


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


class TestQuemRecarimbaOPerfil:
    """A cadeia que escreve o carimbo continua sendo um FIO SÓ — e agora o
    gesto dela alcança o carimbo errado.

    Até 29/08/2026 esta classe se chamava `TestNinguemRecarimbaOPerfil` e
    travava o contrário: *nada recarimba*, medido contra a afirmação que morava
    na nota do `SILENCIO_CONFIRMA_SEC`. Ela mesma dizia, por escrito, o que
    fazer no dia em que o recarimbo fosse implementado — reprovar, e exigir que
    a nota fosse reescrita no mesmo commit. Foi o que aconteceu; a nota está
    reescrita, e o que esta classe trava agora é o desenho novo.

    O preço que a mudança paga, no journal dela: o Mullet Mad Jack carimbado
    `dualsense` por silêncio às 03:23:13 com `gestos=0`, quatro `PS + R3` entre
    03:27:59 e 03:29:02 terminando em `xbox`, e o carimbo errado no lugar — com
    a aba Perfis contando que aquela ponte funcionou e ninguém precisou mexer.
    Em 7 dias, 24 apertos: 23 perfis de jogo dela pedem `dualsense` e ela joga
    em `xbox`.

    O que NÃO mudou, e é o que estas três réguas seguram: **uma gaveta, um
    escritor, e nenhum carimbo sem `por=` explícito.**
    """

    def test_um_so_escritor_monta_o_carimbo(self) -> None:
        """`PonteConfirmada` e `carimbar_ponte` só são chamados de um arquivo."""
        assert set(_chamadas_a("PonteConfirmada")) == {
            "src/hefesto_dualsense4unix/profiles/manager.py"
        }
        assert set(_chamadas_a("carimbar_ponte")) == {
            "src/hefesto_dualsense4unix/profiles/manager.py"
        }

    def test_um_so_chamador_grava_o_carimbo(self) -> None:
        """O tique de 1 Hz é o único, e vale para as DUAS gravações.

        `alinhar_o_modo_com_a_ponte` entrou junto do carimbo em 29/08 e é a
        outra metade da mesma pergunta — por isso ela sai pela mesma porta e
        tem o mesmo chamador. Duas portas para o mesmo fato é como esta casa
        fabrica duas verdades.
        """
        assert set(_chamadas_a("confirmar_ponte")) == {
            "src/hefesto_dualsense4unix/daemon/launch_env.py"
        }
        assert set(_chamadas_a("alinhar_o_modo_do_appid")) == {
            "src/hefesto_dualsense4unix/daemon/launch_env.py"
        }
        assert set(_chamadas_a("alinhar_o_modo_com_a_ponte")) == {
            "src/hefesto_dualsense4unix/profiles/manager.py"
        }

    def test_todo_carimbo_do_produto_diz_de_onde_veio(self) -> None:
        """Nenhum carimbo sai sem `por=`, e o valor é do vocabulário da escada.

        A leitura é do argumento `por=` de cada chamada, não da palavra no
        arquivo: um carimbo novo cai aqui. O valor deixou de ser a constante
        `POR_SILENCIO` digitada no callsite e passou a ser o que o tique
        decidiu (`por_que_confirmou`), porque agora há DOIS desfechos — e é o
        `ponte_escada` que escolhe entre eles, não o `launch_env`.
        """
        for chamadas in _chamadas_a("confirmar_ponte").values():
            for chamada in chamadas:
                por = next(
                    (kw.value for kw in chamada.keywords if kw.arg == "por"), None
                )
                assert por is not None, "carimbo gravado sem `por=` explícito"

        # E os dois desfechos possíveis são os do esquema, sem um sexto nome.
        assert pe.por_que_confirmou(0) == pe.POR_SILENCIO
        assert pe.por_que_confirmou(1) == pe.POR_GESTO
        assert {pe.por_que_confirmou(0), pe.por_que_confirmou(3)} <= pe.CONFIRMACOES


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
