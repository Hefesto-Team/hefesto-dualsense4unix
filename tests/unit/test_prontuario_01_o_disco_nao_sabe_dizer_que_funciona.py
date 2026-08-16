"""PRONTUARIO-01 (16/08/2026) — o disco não sabe dizer que um jogo funciona.

O alvo dela, ao sair em 15/08: *"espero de fato que tenhamos tudo resolvido e
cada um dos jogos locais jogável via cabo ou bt"*. O prontuário é a régua desse
alvo, e a primeira coisa que ele precisa fazer é **recusar o número fácil**.

**A prova de que "funciona" não se lê no disco.** `Duskfade` e `DON'T SCREAM`
têm a MESMA assinatura: mesmo motor, mesmas famílias de API (`rawinput` e
`xinput` por `LoadLibrary`), mesmo wrapper na linha, mesmo Steam Input
desligado. Um funciona e o outro não — medido, com o jogo aberto, em
16/08/2026. Qualquer prontuário que pintasse os dois de verde estaria certo
sobre um e errado sobre o outro, sem meio de saber qual.

Por isso o veredito é **impedimento**, e o balde bom se chama
``sem_impedimento_conhecido`` — que é uma frase mais longa e mais honesta que
"pronto".

Este arquivo trava as duas metades: que o prontuário NOMEIA o que sabe (com a
cura junto), e que ele não promete o que não sabe.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations.api_de_entrada import Familia, Veredito
from hefesto_dualsense4unix.integrations.prontuario_dos_jogos import (
    EXCECAO_INERTE,
    IMPEDIDO,
    LINHA_INTOCAVEL,
    NAO_SEI,
    SEM_EXECUTAVEL,
    SEM_IMPEDIMENTO,
    SEM_WRAPPER,
    Censo,
    Prontuario,
    e_infraestrutura,
    levantar_censo,
)
from hefesto_dualsense4unix.integrations.steam_launch_options import (
    IGNORE_SIGNATURE,
    WRAPPER_LAUNCH,
    _vdf_escape,
)

_PRAGMATA, _DUSKFADE, _SACKBOY = "3357650", "2542020", "1599660"
#: A linha real do Pragmata quando a variável de crash dela comeu o wrapper.
_COMIDA = "VKD3D_CONFIG=no_upload_hvv %command%"


def _com_wrapper(extra: str = "") -> str:
    return f"{WRAPPER_LAUNCH}" if not extra else f"{WRAPPER_LAUNCH} {extra}"


# ---------------------------------------------------------------------------
# O que o prontuário NUNCA diz
# ---------------------------------------------------------------------------
class TestNaoPrometeOQueNaoSabe:
    def test_o_balde_bom_nao_se_chama_pronto(self) -> None:
        """O nome é a promessa. "sem impedimento conhecido" não é "funciona"."""
        assert SEM_IMPEDIMENTO == "sem_impedimento_conhecido"
        assert "funciona" not in SEM_IMPEDIMENTO
        assert "pronto" not in SEM_IMPEDIMENTO

    def test_duskfade_e_dont_scream_saem_iguais(self) -> None:
        """A MORDIDA conceitual: o disco não separa os dois, e o veredito diz isso.

        Um prontuário que os separasse estaria inventando — e é justamente o
        tipo de invenção convincente que já custou horas nesta casa.
        """
        from hefesto_dualsense4unix.integrations.api_de_entrada import Evidencia

        assinatura = Evidencia(
            executavel=Path("/jogo/X-Win64-Shipping.exe"),
            imports=("kernel32.dll",),
            familias=frozenset({Familia.XINPUT, Familia.RAWINPUT}),
            carrega_xinput_dinamicamente=True,
        )
        quebrado = Prontuario(
            appid=_DUSKFADE, nome="Duskfade", raiz=Path("/jogo"),
            linha=_com_wrapper(), evidencia=assinatura, steam_input="0",
        )
        funciona = Prontuario(
            appid="2497900", nome="DON'T SCREAM", raiz=Path("/jogo"),
            linha=_com_wrapper(), evidencia=assinatura, steam_input="0",
        )
        assert quebrado.veredito == funciona.veredito == SEM_IMPEDIMENTO
        assert quebrado.api is funciona.api is Veredito.INDECISO

    def test_pasta_ausente_e_nao_sei_nunca_verde(self) -> None:
        ficha = Prontuario(appid="1", nome="Sumiu", raiz=None, linha=_com_wrapper())
        assert ficha.veredito == NAO_SEI


# ---------------------------------------------------------------------------
# O que ele diz, com a cura ao lado
# ---------------------------------------------------------------------------
class TestNomeiaOQueSabe:
    def test_sem_wrapper_e_impedido_e_a_cura_e_automatica(self) -> None:
        ficha = Prontuario(
            appid=_PRAGMATA, nome="PRAGMATA", raiz=Path("/jogo"), linha=_COMIDA
        )
        assert ficha.veredito == IMPEDIDO
        (estorvo,) = [e for e in ficha.estorvos if e.chave == SEM_WRAPPER]
        assert estorvo.automatica
        assert "hefesto-launch" in estorvo.o_que
        assert estorvo.a_cura  # nunca um diagnóstico sem saída

    def test_linha_intocavel_nao_promete_conserto_automatico(self) -> None:
        """Mexer nela quebraria o launch — e prometer o contrário seria pior.

        "Estendida" é a assinatura NOSSA com mais dispositivos grudados: quem
        editou a linha à mão fica com um fragmento-comando pendurado se o
        produto reescrever por cima, e o jogo não abre.
        """
        ficha = Prontuario(
            appid="1",
            nome="Com IGNORE à mão",
            raiz=Path("/jogo"),
            linha=f"{IGNORE_SIGNATURE},0x057e/0x2009 %command%",
        )
        chaves = [e.chave for e in ficha.estorvos]
        assert LINHA_INTOCAVEL in chaves
        assert SEM_WRAPPER not in chaves
        assert not [e for e in ficha.estorvos if e.automatica]

    def test_excecao_inerte_o_caso_do_sackboy(self) -> None:
        """Ela pôs o jogo na lista, e a lista não estava fazendo nada.

        Medido em 16/08/2026: Sackboy na allowlist com
        `UseSteamControllerConfig = 0`. A lista só PRESERVA o que já estava
        ligado — nunca liga.
        """
        ficha = Prontuario(
            appid=_SACKBOY, nome="Sackboy", raiz=Path("/jogo"),
            linha=_com_wrapper(), steam_input="0", na_allowlist=True,
        )
        assert EXCECAO_INERTE in [e.chave for e in ficha.estorvos]

    def test_allowlist_com_steam_input_ligado_nao_e_estorvo(self) -> None:
        ficha = Prontuario(
            appid=_PRAGMATA, nome="PRAGMATA", raiz=Path("/jogo"),
            linha=_com_wrapper(), steam_input="2", na_allowlist=True,
        )
        assert EXCECAO_INERTE not in [e.chave for e in ficha.estorvos]

    def test_sem_executavel_e_cegueira_declarada(self) -> None:
        from hefesto_dualsense4unix.integrations.api_de_entrada import Evidencia

        ficha = Prontuario(
            appid="1", nome="Ilegível", raiz=Path("/jogo"),
            linha=_com_wrapper(), evidencia=Evidencia(executavel=None),
        )
        (estorvo,) = [e for e in ficha.estorvos if e.chave == SEM_EXECUTAVEL]
        assert not estorvo.automatica


class TestOEstadoDoSteamInput:
    @pytest.mark.parametrize(
        ("do_jogo", "global_", "esperado"),
        [
            ("2", "0", True),
            ("0", "2", False),
            (None, "2", True),
            (None, "0", False),
            (None, None, None),
        ],
    )
    def test_o_valor_do_jogo_vence_o_global(
        self, do_jogo: str | None, global_: str | None, esperado: bool | None
    ) -> None:
        ficha = Prontuario(
            appid="1", nome="X", steam_input=do_jogo, steam_input_global=global_
        )
        assert ficha.steam_input_ligado is esperado


class TestAFraseParaATela:
    def test_com_pendencia_o_nome_aparece(self) -> None:
        """A regra do WRAPPER-EM-TODOS-01: nomear, nunca só contar."""
        censo = Censo(jogos=[
            Prontuario(appid=_PRAGMATA, nome="PRAGMATA", raiz=Path("/j"), linha=_COMIDA),
            Prontuario(appid="2", nome="Outro", raiz=Path("/j"), linha=_com_wrapper()),
        ])
        frase = censo.frase()
        assert "PRAGMATA" in frase
        assert "2 jogos com pendência" not in frase

    def test_muitos_impedidos_ainda_nomeia_os_primeiros(self) -> None:
        censo = Censo(jogos=[
            Prontuario(appid=str(i), nome=f"Jogo {i}", raiz=Path("/j"), linha=_COMIDA)
            for i in range(6)
        ])
        frase = censo.frase()
        assert "Jogo 0" in frase
        assert "e mais 3" in frase

    def test_sem_pendencia_a_frase_conta_quem_depende_de_espelho(self) -> None:
        from hefesto_dualsense4unix.integrations.api_de_entrada import Evidencia

        so_xinput = Evidencia(
            executavel=Path("/j/x.exe"), familias=frozenset({Familia.XINPUT})
        )
        censo = Censo(jogos=[
            Prontuario(appid="1", nome="A", raiz=Path("/j"),
                       linha=_com_wrapper(), evidencia=so_xinput),
        ])
        assert "1 dependem do espelho XInput" in censo.frase()

    def test_biblioteca_vazia_nao_inventa_numero(self) -> None:
        assert "Nenhum jogo" in Censo().frase()


class TestOCensoDeVerdade:
    """Um HOME de bancada com o layout REAL: três árvores `apps` e um manifesto."""

    @pytest.fixture()
    def casa(self, tmp_path: Path) -> Path:
        steamapps = tmp_path / ".steam/steam/steamapps"
        (steamapps / "common/Pragmata").mkdir(parents=True)
        (steamapps / f"appmanifest_{_PRAGMATA}.acf").write_text(
            '"AppState"\n{\n'
            f'\t"appid"\t\t"{_PRAGMATA}"\n'
            '\t"name"\t\t"PRAGMATA"\n'
            '\t"installdir"\t\t"Pragmata"\n}\n',
            encoding="utf-8",
        )
        (steamapps / "appmanifest_1493710.acf").write_text(
            '"AppState"\n{\n\t"appid"\t\t"1493710"\n'
            '\t"name"\t\t"Proton Experimental"\n'
            '\t"installdir"\t\t"Proton"\n}\n',
            encoding="utf-8",
        )
        config = tmp_path / ".steam/steam/userdata/1/config"
        config.mkdir(parents=True)
        (config / "localconfig.vdf").write_text(
            '"UserLocalConfigStore"\n{\n'
            '\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n\t\t\t{\n'
            '\t\t\t\t"apps"\n\t\t\t\t{\n'
            f'\t\t\t\t\t"{_PRAGMATA}"\n\t\t\t\t\t{{\n'
            f'\t\t\t\t\t\t"LaunchOptions"\t\t"{_COMIDA}"\n'
            "\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n"
            # a árvore que a Steam NÃO lê para LaunchOptions, com o wrapper nela
            '\t"apps"\n\t{\n'
            f'\t\t"{_PRAGMATA}"\n\t\t{{\n'
            f'\t\t\t"LaunchOptions"\t\t"{_vdf_escape(WRAPPER_LAUNCH)}"\n'
            '\t\t\t"UseSteamControllerConfig"\t\t"2"\n'
            "\t\t}\n\t}\n}\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_a_infraestrutura_fica_de_fora(self, casa: Path) -> None:
        censo = levantar_censo(casa, allowlist=[], examinar=False)
        assert [j.nome for j in censo.jogos] == ["PRAGMATA"]

    def test_a_arvore_errada_nao_esconde_a_pendencia(self, casa: Path) -> None:
        """A MORDIDA que junta as duas curas de hoje.

        Sem a âncora de caminho do ARVORE-ERRADA-01, o wrapper da árvore errada
        vence e o Pragmata sai verde — exatamente o que aconteceu às 05h.
        """
        censo = levantar_censo(casa, allowlist=[], examinar=False)
        (ficha,) = censo.jogos
        assert not ficha.tem_wrapper
        assert ficha.veredito == IMPEDIDO
        assert "PRAGMATA" in censo.frase()

    def test_casa_sem_steam_devolve_censo_vazio_sem_levantar(self, tmp_path: Path) -> None:
        censo = levantar_censo(tmp_path, allowlist=[], examinar=False)
        assert censo.jogos == []
        assert censo.erros == []


class TestFiltroDeInfraestrutura:
    @pytest.mark.parametrize(
        "nome",
        ["Proton 10.0", "Proton Experimental", "Steam Linux Runtime 3.0 (sniper)",
         "Steamworks Common Redistributables"],
    )
    def test_ferramentas_da_steam(self, nome: str) -> None:
        assert e_infraestrutura(nome)

    @pytest.mark.parametrize("nome", ["PRAGMATA", "Duskfade", "Protonaut", "Stray"])
    def test_jogos_de_verdade(self, nome: str) -> None:
        """`Protonaut` começa com "Proton" e É um jogo — a borda importa."""
        assert not e_infraestrutura(nome)
