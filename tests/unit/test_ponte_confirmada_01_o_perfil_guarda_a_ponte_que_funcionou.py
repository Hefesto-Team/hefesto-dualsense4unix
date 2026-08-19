"""PONTE-CONFIRMADA-01 (19/08/2026) — o perfil guarda a ponte que FUNCIONOU.

O perfil já guardava a ponte: ela é a tupla ``(mode.kind, mode.gamepad_flavor,
está na allowlist do Steam Input)``. O que ele NÃO guardava é a resposta da
pergunta que decide tudo — *"esta combinação foi CONFIRMADA neste jogo, ou é só
o que estava no arquivo quando ninguém sabia?"*.

Sem essa distinção o produto não separa **"nunca tentei"** de **"tentei e
funciona"**, e a escada de pontes nunca para: ela rodaria de novo a cada
abertura de cada jogo, arrancando o controle da mão dela a cada degrau (R-04,
medido em 23/07 — recriar o vpad com o jogo aberto tira o controle do jogo).

Este arquivo trava as quatro metades da frente:

1. o carimbo existe, e a borda recusa carimbo incoerente;
2. **a migração não mente** — os 18 perfis do disco dela continuam dizendo
   "ainda não sei", e um perfil que já traz ``gamepad_flavor="dualsense"`` NÃO
   vira confirmado por existir. É o defeito mais silencioso possível: confundir
   os dois faria a escada nunca rodar em jogo nenhum;
3. o prontuário SABE a ponte e a devolve no veredito — sem afrouxar o
   ``sem_impedimento_conhecido``, que continua recusando dizer "funciona";
4. a leitura é ÚNICA: as duas réguas (o manager, com pydantic; o prontuário,
   stdlib puro) respondem a mesma coisa sobre a mesma pasta.

Hermético: a fixture ``_hefesto_fake_env`` do ``conftest`` isola
``XDG_CONFIG_HOME`` num tmp por teste, e é o MESMO diretório que o
``save_profile`` escreve e que o prontuário lê.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.integrations import prontuario_dos_jogos as pdj
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.manager import (
    carimbar_ponte,
    perfil_do_appid,
    ponte_confirmada_do_appid,
    pontes_confirmadas,
)
from hefesto_dualsense4unix.profiles.schema import (
    CONFIRMADA_POR_ESCOLHA,
    CONFIRMADA_POR_GESTO,
    CONFIRMADA_POR_SILENCIO,
    PonteConfirmada,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

_DONT_SCREAM = "2054970"
_SACKBOY = "1599660"


def _evidencia() -> object:
    """Um executável lido — sem isto o prontuário nomeia `SEM_EXECUTAVEL`.

    A ficha só chega ao veredito da ponte quando o disco deixou ler o jogo, e
    é assim de propósito: cegueira do instrumento vence carimbo.
    """
    from hefesto_dualsense4unix.integrations.api_de_entrada import Evidencia, Familia

    return Evidencia(
        executavel=Path("/jogos/x/X-Win64-Shipping.exe"),
        imports=("kernel32.dll",),
        familias=frozenset({Familia.XINPUT}),
    )


def _perfil_de_jogo(
    nome: str,
    appid: str,
    *,
    flavor: str | None = "dualsense",
    prioridade: int = 0,
) -> Profile:
    """Um perfil de jogo como a GUI o escreve: `match.window_class`."""
    return Profile(
        name=nome,
        match={"type": "criteria", "window_class": [f"steam_app_{appid}"]},
        priority=prioridade,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor=flavor),
    )


# ---------------------------------------------------------------------------
# 1. O carimbo, e a borda que recusa carimbo incoerente
# ---------------------------------------------------------------------------
class TestOCarimbo:
    def test_a_ponte_e_a_tupla_de_sempre_mais_o_quando(self) -> None:
        """Nenhuma palavra nova: os três termos têm os nomes que já tinham."""
        ponte = PonteConfirmada(
            kind="gamepad", gamepad_flavor="dualsense", steam_input=False
        )
        assert (ponte.kind, ponte.gamepad_flavor, ponte.steam_input) == (
            "gamepad",
            "dualsense",
            False,
        )
        # E o carimbo: quando, e como.
        assert ponte.confirmada_em.startswith("20")
        assert ponte.confirmada_por == CONFIRMADA_POR_GESTO

    def test_os_tres_modos_de_confirmar_sao_os_da_escada(self) -> None:
        """O esquema tem de saber guardar toda confirmação que o produto produz.

        Um campo que não soubesse representar o ``silencio`` obrigaria a escada
        a manter uma segunda gaveta para o mesmo fato — e duas gavetas para o
        mesmo fato é como se cria a discordância que ninguém vê.
        """
        for por in (
            CONFIRMADA_POR_GESTO,
            CONFIRMADA_POR_SILENCIO,
            CONFIRMADA_POR_ESCOLHA,
        ):
            assert PonteConfirmada(kind="native", confirmada_por=por).confirmada_por == por

    def test_mascara_sem_gamepad_e_recusada_na_borda(self) -> None:
        """"Modo nativo com máscara xbox" não é uma ponte: é ruído."""
        with pytest.raises(ValidationError) as erro:
            PonteConfirmada(kind="native", gamepad_flavor="xbox")
        assert "gamepad_flavor só vale com kind='gamepad'" in str(erro.value)

    def test_data_ilegivel_morre_no_load_em_vez_de_virar_tela(self) -> None:
        with pytest.raises(ValidationError) as erro:
            PonteConfirmada(kind="gamepad", confirmada_em="ontem")
        assert "não é uma data ISO-8601" in str(erro.value)

    def test_mesma_ponte_compara_os_tres_termos_de_uma_vez(self) -> None:
        ponte = PonteConfirmada(
            kind="gamepad", gamepad_flavor="dualsense", steam_input=True
        )
        mode = ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense")
        assert ponte.mesma_ponte(mode, na_allowlist=True)
        # O terceiro termo sozinho já muda a ponte.
        assert not ponte.mesma_ponte(mode, na_allowlist=False)
        # E máscara diferente também.
        assert not ponte.mesma_ponte(
            ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox"), na_allowlist=True
        )
        # Perfil sem opinião nunca é igual a uma ponte confirmada.
        assert not ponte.mesma_ponte(None, na_allowlist=True)


# ---------------------------------------------------------------------------
# 2. A MIGRAÇÃO NÃO MENTE — "ainda não sei" continua sendo "ainda não sei"
# ---------------------------------------------------------------------------
class TestMigracaoSemPerda:
    def test_perfil_antigo_carrega_e_vale(self) -> None:
        """Aditivo de verdade: o arquivo de ontem abre hoje, inteiro."""
        arquivo = profiles_dir(ensure=True) / "antigo.json"
        arquivo.write_text(
            json.dumps(
                {
                    "name": "Antigo",
                    "version": 1,
                    "match": {"type": "criteria", "window_class": ["steam_app_1"]},
                    "priority": 7,
                    "mode": {"kind": "gamepad", "gamepad_flavor": "dualsense"},
                }
            ),
            encoding="utf-8",
        )
        perfil = load_profile("antigo")
        assert perfil.priority == 7
        assert perfil.mode is not None and perfil.mode.gamepad_flavor == "dualsense"
        assert perfil.ponte is None

    def test_gamepad_flavor_no_arquivo_nao_e_ponte_confirmada(self) -> None:
        """A MORDIDA da frente: existir não é ter sido confirmado.

        Os 18 perfis do disco dela trazem `mode` preenchido. Se `mode` valesse
        como carimbo, a escada nunca rodaria em jogo NENHUM — todos já
        nasceriam "resolvidos", e o defeito seria invisível: nada quebra, nada
        aparece no journal, e a pergunta que ela pediu (*"tenta em ordem e
        confirma uma vez"*) simplesmente nunca seria feita.
        """
        save_profile(_perfil_de_jogo("Dont Scream", _DONT_SCREAM))
        assert ponte_confirmada_do_appid(_DONT_SCREAM) is None
        # E o prontuário concorda: sem carimbo, sem balde de ponte.
        ficha = pdj.Prontuario(appid=_DONT_SCREAM, nome="DON'T SCREAM")
        assert ficha.ponte_confirmada is False

    def test_o_save_de_um_perfil_sem_ponte_nao_acrescenta_a_chave(self) -> None:
        """Downgrade: `extra="forbid"` recusa o perfil INTEIRO por uma chave nova.

        Gravar `"ponte": null` em todo save transformaria "voltar uma versão"
        em "todos os perfis quebrados" — a mesma cura medida do `rota` e do
        `controllers`.
        """
        caminho = save_profile(_perfil_de_jogo("Sackboy", _SACKBOY))
        no_disco = json.loads(Path(caminho).read_text(encoding="utf-8"))
        assert "ponte" not in no_disco

    def test_o_carimbo_sobrevive_ao_ciclo_disco(self) -> None:
        carimbado = carimbar_ponte(
            _perfil_de_jogo("Dont Scream", _DONT_SCREAM),
            kind="gamepad",
            gamepad_flavor="dualsense",
            steam_input=True,
            por=CONFIRMADA_POR_ESCOLHA,
        )
        save_profile(carimbado)
        de_volta = load_profile("Dont Scream")
        assert de_volta.ponte is not None
        assert de_volta.ponte.steam_input is True
        assert de_volta.ponte.confirmada_por == CONFIRMADA_POR_ESCOLHA


# ---------------------------------------------------------------------------
# 3. A leitura ÚNICA, por appid — e o empate resolvido igual dos dois lados
# ---------------------------------------------------------------------------
class TestQualEAPonteDesteAppid:
    def test_pergunta_pelo_appid_em_qualquer_das_tres_formas(self) -> None:
        """`2054970`, `"2054970"` e `"steam_app_2054970"` são o mesmo jogo."""
        save_profile(
            carimbar_ponte(
                _perfil_de_jogo("Dont Scream", _DONT_SCREAM),
                kind="gamepad",
                gamepad_flavor="xbox",
                steam_input=True,
            )
        )
        for forma in (int(_DONT_SCREAM), _DONT_SCREAM, f"steam_app_{_DONT_SCREAM}"):
            ponte = ponte_confirmada_do_appid(forma)
            assert ponte is not None and ponte.gamepad_flavor == "xbox"

    def test_jogo_sem_perfil_e_ainda_nao_sei_nao_e_nao_funciona(self) -> None:
        assert perfil_do_appid("999999") is None
        assert ponte_confirmada_do_appid("999999") is None

    def test_no_empate_vence_quem_sabe_a_ponte(self) -> None:
        """Duas fichas do mesmo jogo é real no disco dela (pragmata/pragmata2).

        Entre um perfil que sabe a ponte e outro que não sabe, a resposta
        honesta é a de quem sabe — o contrário faria a escada rodar de novo num
        jogo já resolvido.
        """
        save_profile(_perfil_de_jogo("Pragmata", "3357650", prioridade=99))
        save_profile(
            carimbar_ponte(
                _perfil_de_jogo("Pragmata2", "3357650", prioridade=0),
                kind="native",
            )
        )
        vencedor = perfil_do_appid("3357650")
        assert vencedor is not None and vencedor.name == "Pragmata2"
        # E as TRÊS leituras têm de responder o mesmo empate. Uma varredura
        # própria em cada uma responderia pela ordem de carga dos arquivos, e a
        # janela mostraria uma ponte enquanto o launch armava outra.
        assert pontes_confirmadas()["3357650"]["kind"] == "native"
        assert pdj.pontes_confirmadas()["3357650"].kind == "native"

    def test_a_forma_publicada_so_traz_quem_tem_carimbo(self) -> None:
        """`{appid: ponte}` — quem monta o estado não abre perfil nenhum."""
        save_profile(_perfil_de_jogo("Sackboy", _SACKBOY))
        save_profile(
            carimbar_ponte(
                _perfil_de_jogo("Dont Scream", _DONT_SCREAM),
                kind="gamepad",
                gamepad_flavor="dualsense",
                steam_input=True,
            )
        )
        publicado = pontes_confirmadas()
        assert set(publicado) == {_DONT_SCREAM}
        assert publicado[_DONT_SCREAM]["gamepad_flavor"] == "dualsense"
        assert publicado[_DONT_SCREAM]["steam_input"] is True
        # JSON de verdade: o estado viaja pelo socket.
        json.dumps(publicado)

    def test_as_duas_reguas_leem_a_mesma_pasta_e_concordam(self) -> None:
        """PORTÃO das cópias: pydantic de um lado, stdlib do outro.

        O prontuário NÃO pode importar o esquema (ele roda como script solto no
        `python3` do sistema, sem venv e sem pydantic — o `doctor.sh` o chama
        assim), então a leitura do carimbo existe duas vezes. O que impede as
        duas de divergirem é este teste, e não a disciplina de quem edita.
        """
        save_profile(
            carimbar_ponte(
                _perfil_de_jogo("Dont Scream", _DONT_SCREAM),
                kind="gamepad",
                gamepad_flavor="dualsense",
                steam_input=True,
                por=CONFIRMADA_POR_SILENCIO,
            )
        )
        save_profile(_perfil_de_jogo("Sackboy", _SACKBOY))
        save_profile(
            carimbar_ponte(_perfil_de_jogo("Pragmata", "3357650"), kind="native")
        )

        pelo_manager = pontes_confirmadas()
        pelo_prontuario = {
            appid: ponte.como_dicionario()
            for appid, ponte in pdj.pontes_confirmadas().items()
        }
        assert set(pelo_manager) == set(pelo_prontuario)
        for appid, ponte in pelo_prontuario.items():
            assert ponte == pelo_manager[appid], appid

    def test_perfil_ilegivel_nao_derruba_a_leitura_dos_outros(self) -> None:
        save_profile(
            carimbar_ponte(
                _perfil_de_jogo("Dont Scream", _DONT_SCREAM), kind="native"
            )
        )
        torto = profiles_dir(ensure=True) / "torto.json"
        torto.write_text("{{{ isto aqui nunca foi JSON", encoding="utf-8")
        assert set(pdj.pontes_confirmadas()) == {_DONT_SCREAM}


# ---------------------------------------------------------------------------
# 4. O PRONTUÁRIO sabe a ponte — e continua recusando dizer "funciona"
# ---------------------------------------------------------------------------
class TestOProntuarioSabeAPonte:
    def test_o_carimbo_aparece_no_veredito_e_no_dicionario(self) -> None:
        ficha = pdj.Prontuario(
            appid=_DONT_SCREAM,
            nome="DON'T SCREAM",
            raiz=Path("/jogos/dont-scream"),
            linha=f"{pdj.WRAPPER_PREFIX}x %command%",
            na_allowlist=True,
            steam_input="1",
            evidencia=_evidencia(),  # type: ignore[arg-type]
            ponte=pdj.Ponte(kind="gamepad", gamepad_flavor="dualsense", steam_input=True),
        )
        assert ficha.ponte_confirmada is True
        assert ficha.veredito == pdj.PONTE_CONFIRMADA
        publicado = ficha.como_dicionario()
        assert publicado["ponte"] == {
            "kind": "gamepad",
            "gamepad_flavor": "dualsense",
            "steam_input": True,
            "confirmada_em": None,
            "confirmada_por": None,
        }

    def test_o_balde_bom_continua_recusando_dizer_que_funciona(self) -> None:
        """A recusa é decisão medida (Duskfade x DON'T SCREAM). Nada afrouxou."""
        assert pdj.SEM_IMPEDIMENTO == "sem_impedimento_conhecido"
        assert "funciona" not in pdj.PONTE_CONFIRMADA
        assert "pronto" not in pdj.PONTE_CONFIRMADA
        # Jogo sem carimbo e sem estorvo continua no balde da ausência-de-motivo.
        from hefesto_dualsense4unix.integrations.api_de_entrada import (
            Evidencia,
            Familia,
        )

        ficha = pdj.Prontuario(
            appid=_SACKBOY,
            nome="Sackboy",
            raiz=Path("/jogos/sackboy"),
            linha=f"{pdj.WRAPPER_PREFIX}x %command%",
            evidencia=Evidencia(
                executavel=Path("/jogos/sackboy/Sackboy.exe"),
                imports=("kernel32.dll",),
                familias=frozenset({Familia.XINPUT}),
            ),
        )
        assert ficha.veredito == pdj.SEM_IMPEDIMENTO

    def test_carimbo_nao_apaga_estorvo(self) -> None:
        """Ponte confirmada com o wrapper fora da linha continua IMPEDIDO.

        A ponte que funcionou não está de pé — dizer o contrário seria
        exatamente a promessa que este módulo existe para não fazer.
        """
        ficha = pdj.Prontuario(
            appid=_DONT_SCREAM,
            nome="DON'T SCREAM",
            raiz=Path("/jogos/dont-scream"),
            linha=None,
            evidencia=_evidencia(),  # type: ignore[arg-type]
            ponte=pdj.Ponte(kind="gamepad", gamepad_flavor="dualsense"),
        )
        assert ficha.veredito == pdj.IMPEDIDO
        assert [e.chave for e in ficha.estorvos] == [pdj.SEM_WRAPPER]

    def test_a_ponte_que_mudou_vira_estorvo_nomeado(self) -> None:
        """Ela tirou o jogo da lista de exceções; a ponte confirmada usava-a."""
        ficha = pdj.Prontuario(
            appid=_DONT_SCREAM,
            nome="DON'T SCREAM",
            raiz=Path("/jogos/dont-scream"),
            linha=f"{pdj.WRAPPER_PREFIX}x %command%",
            na_allowlist=False,
            evidencia=_evidencia(),  # type: ignore[arg-type]
            ponte=pdj.Ponte(kind="gamepad", gamepad_flavor="dualsense", steam_input=True),
        )
        assert ficha.ponte_divergente is True
        assert ficha.veredito == pdj.IMPEDIDO
        estorvo = next(e for e in ficha.estorvos if e.chave == pdj.PONTE_DIVERGENTE)
        assert estorvo.automatica is False, (
            "repor a lista de exceções é gesto DELA — o produto não desfaz"
        )
        assert "CONFIRMADA" in estorvo.o_que

    def test_divergencia_tambem_no_sentido_contrario(self) -> None:
        """Confirmada SEM Steam Input, e hoje o jogo está na lista."""
        ficha = pdj.Prontuario(
            appid=_SACKBOY,
            nome="Sackboy",
            raiz=Path("/jogos/sackboy"),
            linha=f"{pdj.WRAPPER_PREFIX}x %command%",
            na_allowlist=True,
            steam_input="1",
            ponte=pdj.Ponte(kind="gamepad", gamepad_flavor="dualsense", steam_input=False),
        )
        assert ficha.ponte_divergente is True

    def test_estorvo_automatico_sem_cura_nao_existe(self) -> None:
        """O `automatica=True` é AFIRMAÇÃO, não promessa — inclusive o novo."""
        automaticos = {
            chave for chave, (_o, _c, auto) in pdj._ESTORVOS.items() if auto
        }
        assert automaticos <= set(pdj._CURAS)

    def test_o_censo_leva_o_carimbo_ate_a_frase(self, tmp_path: Path) -> None:
        censo = pdj.Censo(
            jogos=[
                pdj.Prontuario(
                    appid=_DONT_SCREAM,
                    nome="DON'T SCREAM",
                    raiz=tmp_path,
                    linha=f"{pdj.WRAPPER_PREFIX}x %command%",
                    ponte=pdj.Ponte(kind="gamepad", gamepad_flavor="dualsense"),
                ),
                pdj.Prontuario(
                    appid=_SACKBOY,
                    nome="Sackboy",
                    raiz=tmp_path,
                    linha=f"{pdj.WRAPPER_PREFIX}x %command%",
                ),
            ]
        )
        assert [j.nome for j in censo.com_ponte_confirmada] == ["DON'T SCREAM"]
        assert "1 com ponte já confirmada" in censo.frase()
        resumo = censo.como_dicionario()["resumo"]
        assert isinstance(resumo, dict) and resumo["com_ponte_confirmada"] == 1

    def test_o_censo_de_verdade_junta_perfil_e_disco(self, tmp_path: Path) -> None:
        """Ponta a ponta: o carimbo sai do perfil e chega ao prontuário do jogo."""
        steamapps = tmp_path / ".steam/steam/steamapps"
        (steamapps / "common/DontScream").mkdir(parents=True)
        (steamapps / f"appmanifest_{_DONT_SCREAM}.acf").write_text(
            '"AppState"\n{\n\t"appid"\t"' + _DONT_SCREAM + '"\n'
            '\t"name"\t"DON\'T SCREAM"\n\t"installdir"\t"DontScream"\n}\n',
            encoding="utf-8",
        )
        save_profile(
            carimbar_ponte(
                _perfil_de_jogo("Dont Scream", _DONT_SCREAM),
                kind="gamepad",
                gamepad_flavor="dualsense",
                steam_input=False,
            )
        )
        censo = pdj.levantar_censo(tmp_path, allowlist=[], examinar=False)
        ficha = next(j for j in censo.jogos if j.appid == _DONT_SCREAM)
        assert ficha.ponte is not None
        assert ficha.ponte.gamepad_flavor == "dualsense"
        assert ficha.ponte_divergente is False
