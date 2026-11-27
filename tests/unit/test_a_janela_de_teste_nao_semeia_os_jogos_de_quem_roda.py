"""A-JANELA-DE-TESTE-NAO-SEMEIA-OS-JOGOS-DE-QUEM-RODA-01: a janela de teste não cria perfil de jogo.

A conftest desliga a semeadura de perfis por teste, e a fixture de módulo roda antes desse
isolamento: a janela aberta por `_correr` numa fixture de módulo lia a biblioteca de jogos da
máquina e criava um perfil por jogo na pasta de mentira. Em 27/11/2026 a régua de renomear
reprovou quando um jogo com «1» no nome entrou na biblioteca de quem rodava a suíte. O `_correr`
desliga a semeadura na corrida inteira, para todo chamador.

A biblioteca aqui é de mentira (um manifesto num lar do teste), e a régua confere antes que o
produto enxerga o jogo: sem essa conferência, passaria por não haver jogo nenhum.

MORDIDA: tirar o `mp.setenv(SEED_SKIP_ENV_VAR, "1")` do `_correr` cria `jogo_1.json` e reprova.
"""
from __future__ import annotations

import pathlib
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("a janela de teste sem a semeadura dos jogos")

from hefesto_dualsense4unix.integrations.jogos_locais import jogos_da_biblioteca_steam
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir
from tests.unit.janela_aberta_comum import _correr, publicar_as_de_hoje

MANIFESTO = '"AppState"\n{\n\t"appid"\t\t"4242"\n\t"name"\t\t"Jogo 1"\n}\n'
A_LISTA_E_REAL = (
    "(function(){ const l = document.querySelector('tbody[data-hef=\"perfis.lista\"]');"
    " return JSON.stringify(!!l && l.dataset.hefReal === '1'); })()")


@pytest.fixture
def lar_com_um_jogo(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Um lar com um perfil guardado e um jogo instalado, com a semeadura religada."""
    lar = tmp_path / "lar-com-um-jogo"
    biblioteca = lar / ".steam/steam/steamapps"
    biblioteca.mkdir(parents=True)
    (biblioteca / "appmanifest_4242.acf").write_text(MANIFESTO, encoding="utf-8")
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(lar / ".local/share"))
    loader.save_profile(Profile(name="Pragmata", match=MatchAny(), priority=100), origem="régua")
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_ultima_varredura_de_jogos", None)
    monkeypatch.setattr(loader, "_assinatura_da_biblioteca_vista", None)
    return lar


def test_a_janela_de_teste_nao_cria_perfil_para_o_jogo_instalado(
        lar_com_um_jogo: pathlib.Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    """A corrida do `_correr` deixa a pasta de perfis como a régua a montou."""
    assert [j.nome for j in jogos_da_biblioteca_steam()] == ["Jogo 1"], "o produto não vê o jogo"
    lido: dict[str, Any] = {}

    def roteiro(_fora: Any, piloto: Any, _t: float) -> bool:
        if lido.get("real"):
            return False
        if not lido.get("no_ar"):
            lido["no_ar"] = True

            def volta(valor: Any, erro: Any) -> None:
                lido["no_ar"] = False
                lido["real"] = not erro and valor == "true"

            piloto.ponte.perguntar(A_LISTA_E_REAL, volta)
        return True

    _correr(publicar_as_de_hoje(tmp_path_factory), "10-perfis.html", 1, roteiro, teto_s=60.0)

    assert lido.get("real"), "a aba Perfis nunca pintou a lista de verdade"
    assert sorted(p.stem for p in profiles_dir().glob("*.json")) == ["pragmata"]
