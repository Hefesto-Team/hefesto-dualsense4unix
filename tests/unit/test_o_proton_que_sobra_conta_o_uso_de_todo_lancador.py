"""O Proton que sobra conta o uso de todo lançador.

O-PROTON-QUE-SOBRA-CONTA-O-USO-DE-TODO-LANCADOR-01, 16/10/2026.

O duplo clique que desinstala as versões de `compatibilitytools.d` que «sobram» só contava a Steam
(`config.vdf`). Um GE-Proton usado só pelo Lutris ou pelo Heroic saía, e o jogo daquele lançador
ficava sem Proton. O dono do saber de onde cada um guarda a versão é o
`censo_dos_lancadores.proton_em_uso`; `proton_pin.versoes_que_sobram` soma o que ele devolve.

O formato do Heroic foi medido num Heroic de verdade (16/10/2026): `GamesConfig/<jogo>.json` traz
`{<jogo>: {wineVersion: {bin, name, type}}}` e `config.json` traz o padrão em
`defaultSettings.wineVersion`.

O Lutris virou extensão em 19/10/2026 (OS-LANCADORES-ALEM-DA-STEAM-E-DO-HEROIC-VIRAM-EXTENSOES-01):
a versão de cada jogo vem do leitor da extensão (o `proton` de cada jogo), e o Lutris que está no
disco SEM a extensão ligada é «não sei» — ninguém o lê, e nenhum Proton sai.

TUDO É DE MENTIRA: casa, Steam, Lutris e Heroic são pastas em `tmp_path`; a extensão é um leitor
de mentira; nada é desinstalado.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): tirar a soma de
`versoes_que_sobram` faz os casos da extensão e do Heroic reprovarem; o JSON ilegível tratado como
«vazio» (em vez de «não sei») faz os casos da dúvida reprovarem; o censo que deixa de olhar o
Heroic, ou o leitor da extensão, faz os casos dele reprovarem; o Lutris no disco sem a extensão
que não vira dúvida faz os dois casos dele reprovarem.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    """O Lutris no disco, como ele grava; sem a extensão ligada, ninguém o lê."""
    _yml(casa, onde, f"games/{nome}.yml", f"game:\n  exe: /x\nwine:\n  version: {versao}\n")


def _extensao_que_le(monkeypatch: pytest.MonkeyPatch, *versoes: str,
                     estado: str = censo.LIDO) -> None:
    """A extensão `lutris` ligada, cujo leitor devolve um jogo por versão."""
    bloco = censo.LancadorDaModificacao(
        chave="lutris", rotulo="Lutris",
        leitor=censo.LeitorPorProcesso("lutris", "Lutris", ("python3", "leitor.py"), Path("/x")))
    monkeypatch.setattr(censo, "lancadores_das_extensoes",
                        lambda lugares=None: (censo.LancadorDaExtensao(bloco),))
    jogos = [censo.JogoDoLancador(f"j{i}", f"Jogo {i}", proton=v) for i, v in enumerate(versoes)]
    monkeypatch.setattr(censo, "ler_por_processo",
                        lambda leitor, **_k: censo.BibliotecaDoLancador("Lutris", estado, None,
                                                                        jogos))


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


def test_o_proton_de_um_jogo_da_extensao_fica(steam: Path,
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: o censo que não pergunta ao leitor da extensão deixa o 11-1 sair."""
    _jogo_do_lutris(steam, "GE-Proton11-1")
    _extensao_que_le(monkeypatch, "GE-Proton11-1")
    assert _sobras(steam) == TODAS - {"GE-Proton11-1"}


def test_o_lutris_no_disco_sem_a_extensao_mantem_tudo(steam: Path) -> None:
    """MORDIDA: sem a dúvida do Lutris que ninguém lê, as quatro saem e o jogo fica sem Proton."""
    _jogo_do_lutris(steam, "GE-Proton11-1")
    assert _sobras(steam) == set()
    assert "lutris" in censo.proton_em_uso(steam).duvida


def test_a_extensao_que_nao_le_mantem_tudo(steam: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _jogo_do_lutris(steam, "GE-Proton11-1")
    _extensao_que_le(monkeypatch, estado=censo.ILEGIVEL)
    assert _sobras(steam) == set()


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


def test_o_flatpak_do_heroic_conta_como_o_nativo(steam: Path) -> None:
    _jogo_do_heroic(steam, "GE-Proton10-34", onde=FLATPAK_DO_HEROIC)
    assert _sobras(steam) == TODAS - {"GE-Proton10-34"}


def test_o_lutris_flatpak_sem_a_extensao_tambem_mantem_tudo(steam: Path) -> None:
    _jogo_do_lutris(steam, "GE-Proton11-1", onde=FLATPAK_DO_LUTRIS)
    assert _sobras(steam) == set()


def test_a_caixa_da_letra_nao_decide(steam: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O lançador escreve a versão como a pessoa a escolheu; maiúscula a mais não derruba o jogo."""
    _extensao_que_le(monkeypatch, "ge-proton11-1")
    assert _sobras(steam) == TODAS - {"GE-Proton11-1"}


def test_os_tres_lancadores_juntos_so_um_sai(steam: Path,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    """Um usado só pela extensão, outro só pelo Heroic, um pela Steam: o sem uso é o único.

    Prova da D-1610-O-PROTON-QUE-SOBRA-CONTA-O-USO-DE-TODO-LANCADOR.
    """
    _jogo_do_lutris(steam, "GE-Proton11-1")
    _extensao_que_le(monkeypatch, "GE-Proton11-1")
    _jogo_do_heroic(steam, "GE-Proton10-34")
    _mapa(steam, {"1": PINO, "2": "GE-Proton11-3"})
    assert _nomes(pp.versoes_que_sobram(steam, pino=PINO)) == {"GE-Proton11-6-x86_64"}


def test_o_censo_responde_o_que_cada_lancador_usa(steam: Path,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    _jogo_do_lutris(steam, "GE-Proton11-1")
    _extensao_que_le(monkeypatch, "GE-Proton11-1")
    _jogo_do_heroic(steam, "GE-Proton10-34")
    uso = censo.proton_em_uso(steam)
    assert {"GE-Proton11-1", "GE-Proton10-34"} <= uso.versoes
    assert uso.duvida == ()


def test_o_json_do_heroic_ilegivel_mantem_tudo(steam: Path) -> None:
    """MORDIDA: troque «não sei» por «ilegível = vazio» e as quatro saem."""
    _yml(steam, DO_HEROIC, "GamesConfig/quebrado.json", '{"x": {"wineVersion": ')
    assert _sobras(steam) == set()
    assert censo.proton_em_uso(steam).duvida


def test_o_config_do_heroic_ilegivel_mantem_tudo(steam: Path) -> None:
    _yml(steam, DO_HEROIC, "config.json", "{ isto não é json")
    assert _sobras(steam) == set()


def test_um_arquivo_bom_nao_apaga_a_duvida_do_outro(steam: Path) -> None:
    """O jogo legível diz que o 10-34 fica; o ilegível impede o resto de sair."""
    _jogo_do_heroic(steam, "GE-Proton10-34", app="bom")
    _yml(steam, DO_HEROIC, "GamesConfig/ruim.json", '{"ruim": {"wineVersion": [')
    assert _sobras(steam) == set()
