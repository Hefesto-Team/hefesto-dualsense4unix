"""O Proton que sobra conta o uso de todo lançador.

O-PROTON-QUE-SOBRA-CONTA-O-USO-DE-TODO-LANCADOR-01, 16/10/2026.

O duplo clique que desinstala as versões de `compatibilitytools.d` que «sobram» só contava a Steam
(`config.vdf`). Um GE-Proton usado só pelo Lutris ou pelo Heroic saía, e o jogo daquele lançador
ficava sem Proton. O dono do saber de onde cada um guarda a versão é o
`censo_dos_lancadores.proton_em_uso`; `proton_pin.versoes_que_sobram` soma o que ele devolve.

O formato do Heroic foi medido num Heroic de verdade (16/10/2026): `GamesConfig/<jogo>.json` traz
`{<jogo>: {wineVersion: {bin, name, type}}}` e `config.json` traz o padrão em
`defaultSettings.wineVersion`. O do Lutris é o `wine.version` de cada `games/*.yml` e do
`runners/wine.yml`.

TUDO É DE MENTIRA: casa, Steam, Lutris e Heroic são pastas em `tmp_path`; nada é desinstalado.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): tirar a soma de
`versoes_que_sobram` faz os casos do Lutris e do Heroic reprovarem; o `.yml` ou o JSON ilegível
tratado como «vazio» (em vez de «não sei») faz os casos da dúvida reprovarem; o censo que deixa de
olhar o Heroic faz os casos dele reprovarem.
"""
from __future__ import annotations

import json
from pathlib import Path

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import proton_pin as pp
from tests.unit.test_o_fixar_proton_desinstala_as_que_sobram import (
    PINO,
    _mapa,
    _nomes,
)
from tests.unit.test_o_fixar_proton_desinstala_as_que_sobram import steam as _casa_com_steam

steam = _casa_com_steam

DO_LUTRIS = ".config/lutris"
FLATPAK_DO_LUTRIS = ".var/app/net.lutris.Lutris/config/lutris"
DO_HEROIC = ".config/heroic"
FLATPAK_DO_HEROIC = ".var/app/com.heroicgameslauncher.hgl/config/heroic"
TODAS = {"GE-Proton10-34", "GE-Proton11-1", "GE-Proton11-3", "GE-Proton11-6-x86_64"}


def _yml(casa: Path, onde: str, relativo: str, texto: str) -> None:
    alvo = casa / onde / relativo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(texto, encoding="utf-8")


def _jogo_do_lutris(casa: Path, versao: str, *, nome: str = "jogo", onde: str = DO_LUTRIS) -> None:
    _yml(casa, onde, f"games/{nome}.yml", f"game:\n  exe: /x\nwine:\n  version: {versao}\n")


def _jogo_do_heroic(casa: Path, versao: str, *, app: str = "abc123", onde: str = DO_HEROIC,
                    com_bin: bool = True) -> None:
    ferramenta = {"bin": (f"{casa}/.steam/steam/compatibilitytools.d/{versao}/proton"
                          if com_bin else ""), "name": versao, "type": "proton"}
    _yml(casa, onde, f"GamesConfig/{app}.json", json.dumps(
        {app: {"wineVersion": ferramenta, "winePrefix": "/p"}, "version": "v0", "explicit": True}))


def _sobras(casa: Path) -> set[str]:
    _mapa(casa, {"1": PINO})
    return _nomes(pp.versoes_que_sobram(casa, pino=PINO))


def test_so_a_steam_sobram_as_quatro(steam: Path) -> None:
    """Sem Lutris nem Heroic a conta é a de hoje."""
    assert _sobras(steam) == TODAS


def test_o_proton_de_um_jogo_do_lutris_fica(steam: Path) -> None:
    _jogo_do_lutris(steam, "GE-Proton11-1")
    assert _sobras(steam) == TODAS - {"GE-Proton11-1"}


def test_o_proton_padrao_do_runner_do_lutris_fica(steam: Path) -> None:
    _yml(steam, DO_LUTRIS, "runners/wine.yml", "wine:\n  version: GE-Proton11-3\n")
    assert _sobras(steam) == TODAS - {"GE-Proton11-3"}


def test_o_proton_de_um_jogo_do_heroic_fica(steam: Path) -> None:
    _jogo_do_heroic(steam, "GE-Proton10-34")
    assert _sobras(steam) == TODAS - {"GE-Proton10-34"}


def test_o_proton_padrao_do_heroic_fica(steam: Path) -> None:
    """`config.json` → `defaultSettings.wineVersion`: o que todo jogo sem escolha própria usa."""
    _yml(steam, DO_HEROIC, "config.json", json.dumps({"defaultSettings": {"wineVersion": {
        "bin": "", "name": "GE-Proton11-3", "type": "proton"}}}))
    assert _sobras(steam) == TODAS - {"GE-Proton11-3"}


def test_o_heroic_que_so_grava_o_bin_conta_pela_pasta(steam: Path) -> None:
    """O nome que o Heroic mostra pode não ser o da pasta: a pasta do `bin` também vale."""
    ferramenta = {"bin": f"{steam}/.steam/steam/compatibilitytools.d/GE-Proton11-1/proton",
                  "name": "Proton - GE-Proton 11-1", "type": "proton"}
    _yml(steam, DO_HEROIC, "GamesConfig/x.json", json.dumps({"x": {"wineVersion": ferramenta}}))
    assert _sobras(steam) == TODAS - {"GE-Proton11-1"}


def test_o_flatpak_dos_dois_conta_como_o_nativo(steam: Path) -> None:
    _jogo_do_lutris(steam, "GE-Proton11-1", onde=FLATPAK_DO_LUTRIS)
    _jogo_do_heroic(steam, "GE-Proton10-34", onde=FLATPAK_DO_HEROIC)
    assert _sobras(steam) == TODAS - {"GE-Proton11-1", "GE-Proton10-34"}


def test_a_caixa_da_letra_nao_decide(steam: Path) -> None:
    """O Lutris escreve a versão como a pessoa a escolheu; maiúscula a mais não derruba o jogo."""
    _jogo_do_lutris(steam, "ge-proton11-1")
    assert _sobras(steam) == TODAS - {"GE-Proton11-1"}


def test_os_tres_lancadores_juntos_so_um_sai(steam: Path) -> None:
    """Um usado só pelo Lutris, outro só pelo Heroic, um pela Steam: o sem uso nenhum é o único."""
    _jogo_do_lutris(steam, "GE-Proton11-1")
    _jogo_do_heroic(steam, "GE-Proton10-34")
    _mapa(steam, {"1": PINO, "2": "GE-Proton11-3"})
    assert _nomes(pp.versoes_que_sobram(steam, pino=PINO)) == {"GE-Proton11-6-x86_64"}


def test_o_censo_responde_o_que_cada_lancador_usa(steam: Path) -> None:
    _jogo_do_lutris(steam, "GE-Proton11-1")
    _jogo_do_heroic(steam, "GE-Proton10-34")
    uso = censo.proton_em_uso(steam)
    assert {"GE-Proton11-1", "GE-Proton10-34"} <= uso.versoes
    assert uso.duvida == ()


# --- na dúvida a pasta fica ---------------------------------------------------------------------

def test_o_yml_do_lutris_ilegivel_mantem_tudo(steam: Path) -> None:
    """MORDIDA: troque «não sei» por «ilegível = vazio» e as quatro saem."""
    _yml(steam, DO_LUTRIS, "games/quebrado.yml", "wine: [isto: não: fecha\n  - {")
    assert _sobras(steam) == set()
    assert censo.proton_em_uso(steam).duvida


def test_o_json_do_heroic_ilegivel_mantem_tudo(steam: Path) -> None:
    _yml(steam, DO_HEROIC, "GamesConfig/quebrado.json", '{"x": {"wineVersion": ')
    assert _sobras(steam) == set()


def test_o_config_do_heroic_ilegivel_mantem_tudo(steam: Path) -> None:
    _yml(steam, DO_HEROIC, "config.json", "{ isto não é json")
    assert _sobras(steam) == set()


def test_o_runner_do_lutris_ilegivel_mantem_tudo(steam: Path) -> None:
    _yml(steam, DO_LUTRIS, "runners/wine.yml", "- isto\n- e uma lista\n")
    assert _sobras(steam) == set()


def test_um_arquivo_bom_nao_apaga_a_duvida_do_outro(steam: Path) -> None:
    """O jogo legível diz que o 11-1 fica; o ilegível impede o resto de sair."""
    _jogo_do_lutris(steam, "GE-Proton11-1", nome="bom")
    _yml(steam, DO_LUTRIS, "games/ruim.yml", "wine: {version: [")
    assert _sobras(steam) == set()


def test_arquivo_vazio_nao_e_duvida(steam: Path) -> None:
    """Um `.yml` vazio não usa Proton nenhum: não trava a conta nem esconde as sobras."""
    _yml(steam, DO_LUTRIS, "games/vazio.yml", "")
    assert _sobras(steam) == TODAS
