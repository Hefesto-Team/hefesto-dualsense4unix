"""D-33 (05/08/2026) — as três mensagens do Steam Input nomeiam o JOGO."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_steam_input_d33_nomeia_o_jogo: importa código da janela GTK")

from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions.daemon_actions import (
    _frase_steam_input,
    format_fix_safe_result,
)
from hefesto_dualsense4unix.integrations import storm_doctor as sd
from hefesto_dualsense4unix.integrations.steam_launch_options import (
    nome_do_appid,
    rotulo_do_jogo,
)

_SACKBOY = "1599660"
#: Mullet Mad Jack: o caso legítimo de allowlist (a via oficial de DualSense
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
    """HOME de bancada com Steam nativa e a allowlist isolada."""
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
        """É o número que ela confere na Steam, e o único identificador comum"""
        _instalar(casa, _SACKBOY, "Sackboy: A Big Adventure")
        assert rotulo_do_jogo(_SACKBOY, casa) == "Sackboy: A Big Adventure (appid 1599660)"


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


class TestMensagemDoDoctor:
    def test_nomeia_o_jogo_e_nao_conta_arquivos(self, casa: Path) -> None:
        _instalar(casa, _SACKBOY, "Sackboy: A Big Adventure")
        _localconfig(casa, _vdf([_SACKBOY]))

        tag, msg = sd.check_steam_input(casa)

        assert tag == sd.WARN
        assert "Sackboy: A Big Adventure" in msg
        assert _SACKBOY in msg
        assert "perfil" not in msg
        assert "conflit" not in msg.lower()

    def test_diz_o_que_vai_acontecer_e_por_que(self, casa: Path) -> None:
        """"Vai desligar" ANTES de desligar — a bomba da D-31 era silenciosa."""
        _localconfig(casa, _vdf([_SACKBOY]))

        _, msg = sd.check_steam_input(casa)

        assert "vai desligá-lo no próximo ciclo" in msg
        assert "lista de exceções" in msg

    def test_aponta_o_botao_que_preserva_a_escolha_dela(self, casa: Path) -> None:
        """O ponteiro antigo mandava clicar no botão que APAGA a escolha dela."""
        _localconfig(casa, _vdf([_SACKBOY]))

        _, msg = sd.check_steam_input(casa)

        assert "'Este jogo não funciona'" in msg
        assert f"'{sd.rotulo_do_botao('btn_storm_fix_safe', '?')}'" not in msg

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
        """O ajuste GERAL da Steam não é escolha por jogo — desligá-lo não"""
        _localconfig(casa, _vdf([], global_ligado=True))

        tag, msg = sd.check_steam_input(casa)

        assert tag == sd.WARN
        assert f"'{sd.rotulo_do_botao('btn_storm_fix_safe', '?')}'" in msg
        assert "aba Sistema" in msg

    def test_jogo_da_allowlist_nao_e_acusado(self, casa: Path) -> None:
        (casa / "allowlist.txt").write_text(f"{_MMJ}\n", encoding="utf-8")
        _localconfig(casa, _vdf([_MMJ]))

        tag, _ = sd.check_steam_input(casa)

        assert tag == sd.OK


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
        """FEAT-STEAM-SIMPLES-01: o botão "Deixar tudo pronto" não pronuncia"""
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
