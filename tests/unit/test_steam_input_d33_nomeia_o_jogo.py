"""D-33 (05/08/2026) — as três mensagens do Steam Input nomeiam o JOGO.

A queixa dela, literal: *"não faço ideia de quando é pra ativar os controles
Steam e quando não, nem se os botões lá prestam"*. A parte MEDIDA dessa queixa
são três frases que falavam do estado do Steam Input sem nunca dizer de qual
jogo falavam — e que chamavam de *conflito* uma escolha que ela tomou na janela
da própria Steam:

1. `integrations/storm_doctor.check_steam_input` — *"Steam Input LIGADO em 1
   perfil(is) fora da allowlist — clique 'Aplicar correções'"*. O "1" contava
   ARQUIVOS `localconfig.vdf`; dez jogos ligados no mesmo arquivo davam "1", e
   um jogo ligado em duas contas de Steam dava "2". E o botão apontado é o que
   APAGA a escolha dela.
2. `app/actions/emulation_actions` (linha da aba Emulação) — *"Ligado —
   conflita com o Hefesto"*.
3. `app/actions/daemon_actions._frase_steam_input` — *"a Steam não sequestra
   mais o seu controle"*.

O que este arquivo trava, nas três: o appid aparece SEMPRE, o nome do jogo
aparece quando a Steam tem o `appmanifest` em disco, nome nenhum é inventado
quando não tem, e a palavra "conflito" não volta.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions.daemon_actions import (
    _frase_steam_input,
    format_fix_safe_result,
    format_steam_ready_result,
)
from hefesto_dualsense4unix.integrations import storm_doctor as sd
from hefesto_dualsense4unix.integrations.steam_launch_options import (
    nome_do_appid,
    rotulo_do_jogo,
)

#: Sackboy (1599660) é o jogo REAL da D-31: ligado no `localconfig.vdf` dela e
#: AUSENTE do `steam_input_apps.txt`. Aqui ele é só bancada — o arquivo dela
#: não é lido nem tocado por teste nenhum deste módulo.
_SACKBOY = "1599660"
#: Mullet Mad Jack: o caso legítimo de allowlist (a via oficial de DualSense
#: dele é o Steam Input).
_MMJ = "2111190"


def _vdf(appids_ligados: list[str], *, global_ligado: bool = False) -> str:
    """`localconfig.vdf` de bancada no formato REAL (tabs literais)."""
    blocos = "".join(
        f'\t\t"{appid}"\n\t\t{{\n\t\t\t"UseSteamControllerConfig"\t\t"2"\n\t\t}}\n'
        for appid in appids_ligados
    )
    valor = "2" if global_ligado else "0"
    return (
        '"UserLocalConfigStore"\n{\n\t"apps"\n\t{\n'
        f"{blocos}"
        "\t}\n"
        '\t"system"\n\t{\n'
        f'\t\t"SteamController_PSSupport"\t\t"{valor}"\n'
        "\t}\n}\n"
    )


@pytest.fixture()
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """HOME de bancada com Steam nativa e a allowlist isolada.

    CANARIO-FS-01: sem prender a allowlist aqui, o resultado do teste passaria
    a depender do `steam_input_apps.txt` REAL da mantenedora.
    """
    (tmp_path / ".steam/steam/steamapps").mkdir(parents=True)
    (tmp_path / ".steam/steam/userdata/123/config").mkdir(parents=True)
    monkeypatch.setattr(sd, "_allowlist_path", lambda: tmp_path / "allowlist.txt")
    return tmp_path


def _instalar(casa: Path, appid: str, nome: str) -> None:
    """Escreve o `appmanifest_<appid>.acf` que a Steam manteria em disco."""
    (casa / ".steam/steam/steamapps" / f"appmanifest_{appid}.acf").write_text(
        '"AppState"\n{\n'
        f'\t"appid"\t\t"{appid}"\n'
        f'\t"name"\t\t"{nome}"\n'
        "}\n",
        encoding="utf-8",
    )


def _localconfig(casa: Path, texto: str) -> None:
    (casa / ".steam/steam/userdata/123/config/localconfig.vdf").write_text(
        texto, encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# A tradução appid -> nome (a peça que só a CLI tinha)
# ---------------------------------------------------------------------------
class TestTraducaoDoAppid:
    def test_nome_vem_do_appmanifest(self, casa: Path) -> None:
        _instalar(casa, _SACKBOY, "Sackboy: A Big Adventure")
        assert nome_do_appid(_SACKBOY, casa) == "Sackboy: A Big Adventure"

    def test_jogo_desinstalado_devolve_o_appid_cru_e_nao_inventa(
        self, casa: Path
    ) -> None:
        """Sem manifest não há nome. O appid cru é honesto; nome chutado não é."""
        assert nome_do_appid(_SACKBOY, casa) is None
        assert rotulo_do_jogo(_SACKBOY, casa) == f"appid {_SACKBOY}"

    def test_o_appid_nunca_some_da_frase(self, casa: Path) -> None:
        """É o número que ela confere na Steam, e o único identificador comum
        aos três cadastros (vdf, allowlist, env materializado)."""
        _instalar(casa, _SACKBOY, "Sackboy: A Big Adventure")
        assert rotulo_do_jogo(_SACKBOY, casa) == "Sackboy: A Big Adventure (appid 1599660)"


# ---------------------------------------------------------------------------
# O walker: quem é JOGO, quem é chave GLOBAL
# ---------------------------------------------------------------------------
class TestQuemEstaLigado:
    def test_devolve_appid_do_jogo_fora_da_allowlist(self) -> None:
        appids, glob_on = sd.steam_input_fora_da_allowlist(
            _vdf([_SACKBOY, _MMJ]), {_MMJ}
        )
        assert appids == [_SACKBOY]
        assert glob_on is False

    def test_chave_global_nao_vira_jogo(self) -> None:
        appids, glob_on = sd.steam_input_fora_da_allowlist(
            _vdf([], global_ligado=True), set()
        )
        assert appids == []
        assert glob_on is True

    def test_o_veredito_booleano_antigo_continua_valendo(self) -> None:
        assert sd.steam_input_on_fora_da_allowlist(_vdf([_MMJ]), {_MMJ}) is False
        assert sd.steam_input_on_fora_da_allowlist(_vdf([_SACKBOY]), {_MMJ}) is True


# ---------------------------------------------------------------------------
# Mensagem 1 — o doctor (storm_doctor.check_steam_input)
# ---------------------------------------------------------------------------
class TestMensagemDoDoctor:
    def test_nomeia_o_jogo_e_nao_conta_arquivos(self, casa: Path) -> None:
        _instalar(casa, _SACKBOY, "Sackboy: A Big Adventure")
        _localconfig(casa, _vdf([_SACKBOY]))

        tag, msg = sd.check_steam_input(casa)

        assert tag == sd.WARN
        assert "Sackboy: A Big Adventure" in msg
        assert _SACKBOY in msg
        # O defeito literal: contava ARQUIVOS vdf e chamava de "perfil".
        assert "perfil" not in msg
        assert "conflit" not in msg.lower()

    def test_diz_o_que_vai_acontecer_e_por_que(self, casa: Path) -> None:
        """"Vai desligar" ANTES de desligar — a bomba da D-31 era silenciosa."""
        _localconfig(casa, _vdf([_SACKBOY]))

        _, msg = sd.check_steam_input(casa)

        assert "vai desligá-lo no próximo ciclo" in msg
        assert "lista de exceções" in msg

    def test_aponta_o_botao_que_preserva_a_escolha_dela(self, casa: Path) -> None:
        """O ponteiro antigo mandava clicar no botão que APAGA a escolha dela.

        Para um jogo, o gesto certo é o inverso: pôr o jogo na lista de
        exceções ('Este jogo não funciona'), que é o que faz o Hefesto sair da
        frente em vez de desfazer o que ela escolheu.
        """
        _localconfig(casa, _vdf([_SACKBOY]))

        _, msg = sd.check_steam_input(casa)

        assert "'Este jogo não funciona'" in msg
        assert "'Aplicar correções'" not in msg

    def test_sem_manifest_mostra_o_appid_cru(self, casa: Path) -> None:
        _localconfig(casa, _vdf([_SACKBOY]))

        _, msg = sd.check_steam_input(casa)

        assert f"appid {_SACKBOY}" in msg

    def test_dois_jogos_no_mesmo_arquivo_aparecem_os_dois(self, casa: Path) -> None:
        """Era aqui que o "1 perfil(is)" mais mentia: dez jogos, um arquivo."""
        _instalar(casa, _SACKBOY, "Sackboy: A Big Adventure")
        _instalar(casa, "3357650", "Pragmata")
        _localconfig(casa, _vdf([_SACKBOY, "3357650"]))

        _, msg = sd.check_steam_input(casa)

        assert "Sackboy: A Big Adventure" in msg
        assert "Pragmata" in msg
        assert "esses jogos não estão" in msg

    def test_chave_global_continua_apontando_o_aplicar_correcoes(
        self, casa: Path
    ) -> None:
        """O ajuste GERAL da Steam não é escolha por jogo — desligá-lo não
        apaga decisão nenhuma dela, e o botão certo continua sendo aquele."""
        _localconfig(casa, _vdf([], global_ligado=True))

        tag, msg = sd.check_steam_input(casa)

        assert tag == sd.WARN
        assert "'Aplicar correções'" in msg
        assert "aba Sistema" in msg

    def test_jogo_da_allowlist_nao_e_acusado(self, casa: Path) -> None:
        (casa / "allowlist.txt").write_text(f"{_MMJ}\n", encoding="utf-8")
        _localconfig(casa, _vdf([_MMJ]))

        tag, _ = sd.check_steam_input(casa)

        assert tag == sd.OK


# ---------------------------------------------------------------------------
# Mensagem 2 — a linha da aba Emulação
# ---------------------------------------------------------------------------
class TestLinhaDaAbaEmulacao:
    @staticmethod
    def _markup(**kwargs: object) -> str:
        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            markup_status_steam_input,
        )

        base: dict[str, object] = {
            "on": True,
            "jogos": ["Sackboy: A Big Adventure (appid 1599660)"],
            "excecoes": [],
            "efetiva": None,
        }
        base.update(kwargs)
        return markup_status_steam_input(**base)  # type: ignore[arg-type]

    def test_nomeia_o_jogo_e_larga_a_palavra_conflito(self) -> None:
        markup = self._markup()
        assert "Sackboy: A Big Adventure (appid 1599660)" in markup
        assert "conflita" not in markup
        assert "próximo ciclo" in markup

    def test_chave_global_nao_finge_ter_jogo(self) -> None:
        markup = self._markup(jogos=[])
        assert "ajuste global da Steam" in markup
        assert "appid" not in markup

    def test_desligado_e_indeterminado_nao_mudaram(self) -> None:
        assert "Desligado — tudo certo" in self._markup(on=False, jogos=[])
        assert "Steam não encontrado" in self._markup(on=None, jogos=[])

    def test_nome_com_e_comercial_nao_quebra_o_markup(self) -> None:
        """Pango engasga com `&` cru — e um jogo chamado "Rick & Morty" existe."""
        markup = self._markup(jogos=["Sam & Max (appid 321)"])
        assert "&amp;" in markup
        assert "Sam & Max" not in markup

    def test_o_bloco_de_excecoes_do_r06_continua_no_lugar(self) -> None:
        markup = self._markup(on=False, jogos=[], excecoes=[2111190], efetiva=True)
        assert "Exceção por jogo: 1 jogo(s) — controle liberado agora" in markup


# ---------------------------------------------------------------------------
# Mensagem 3 — o toast dos botões da aba Sistema
# ---------------------------------------------------------------------------
class TestToastDosBotoes:
    _ROTULO = "Sackboy: A Big Adventure (appid 1599660)"

    def test_frase_nomeia_o_jogo_e_o_motivo(self) -> None:
        frase = _frase_steam_input(0, "aplicado", [self._ROTULO])
        assert self._ROTULO in frase
        assert "não está na sua lista de exceções" in frase
        assert "sequestra" not in frase

    def test_sem_medicao_nao_inventa_jogo(self) -> None:
        frase = _frase_steam_input(0, "aplicado", None)
        assert "appid" not in frase
        assert "sequestra" not in frase

    def test_medido_e_vazio_diz_que_foi_o_ajuste_geral(self) -> None:
        frase = _frase_steam_input(0, "aplicado", [])
        assert "ajuste geral da Steam" in frase
        assert "nenhum jogo da sua lista de exceções foi tocado" in frase

    def test_modo_simples_preservado_o_jargao_nao_volta(self) -> None:
        """FEAT-STEAM-SIMPLES-01: o botão "Deixar tudo pronto" não pronuncia
        "Steam Input" — nomear o jogo não podia trazer o jargão de volta."""
        for jogos in ([self._ROTULO], [], None):
            assert "Steam Input" not in _frase_steam_input(0, "aplicado", jogos)

    def test_aplicar_correcoes_leva_o_nome_do_jogo_ate_o_toast(self) -> None:
        msg = format_fix_safe_result(
            {
                "ran": 2,
                "missing": 0,
                "steam_input": (0, "[steam-input] resultado=aplicado\n"),
                "steam_input_jogos": [self._ROTULO],
            }
        )
        assert self._ROTULO in msg

    def test_deixar_tudo_pronto_leva_o_nome_do_jogo_ate_o_toast(self) -> None:
        msg = format_steam_ready_result(
            janela="ok",
            dados={
                "script": (0, "[steam-input] resultado=aplicado\n"),
                "wrapper": None,
                "steam_input_jogos": [self._ROTULO],
            },
            wrapper_ok=False,
        )
        assert self._ROTULO in msg

    def test_relatorio_torto_nao_derruba_nem_inventa(self) -> None:
        for torto in ("Sackboy", [1599660], 7, {"a": 1}):
            msg = format_fix_safe_result(
                {
                    "ran": 1,
                    "missing": 0,
                    "steam_input": (0, "[steam-input] resultado=aplicado\n"),
                    "steam_input_jogos": torto,
                }
            )
            assert "appid" not in msg
