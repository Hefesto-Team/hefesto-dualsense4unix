"""A-GUARDA-DO-EDITOR-ACHA-O-AJUSTE-DE-CADA-CONTROLE-01 — a guarda por controle.

Medido antes de curar (12/10/2026): o perfil guarda o ajuste de cada controle sob o serial
normalizado (`aabbcc000001`), e a mesa entrega o serial como o aparelho o diz (`aa:bb:cc:00:00:01`
pelo rádio). A guarda lia `controllers.get(uniq)` cru e a linha dizia «nada só dele» sobre um
controle que TEM ajuste próprio. Os esperados são escritos à mão (faixa forjada, nenhum endereço
real). Desde 15/10 a linha também não leva o `P1 •` no nome: fala pela cor do plástico.

MORDIDAS (cada uma foi feita e viu reprovar):

* voltar a `_linhas_da_guarda` ao `get(uniq)` cru -> o serial com «:» perde o ajuste;
* devolver o `P{n} •` ao rótulo curto -> `test_a_linha_fala_pela_cor_do_plastico`.
"""
from __future__ import annotations

import pytest


from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import ControllerOverrides, MatchAny, Profile

SERIAL = "aabbcc000001"

FORMAS_DO_MESMO_SERIAL = ["aabbcc000001", "aa:bb:cc:00:00:01", "AA:BB:CC:00:00:01", "AABBCC000001"]


def _perfil() -> Profile:
    return Profile(name="Bancada", match=MatchAny(),
                   controllers={SERIAL: ControllerOverrides(leds={})})


@pytest.mark.parametrize("uniq", FORMAS_DO_MESMO_SERIAL)
def test_o_serial_acha_o_ajuste_em_qualquer_forma(uniq: str) -> None:
    """MORDIDA: o `get` cru por `uniq` só acerta a forma que ficou gravada."""
    linhas = perfis_web._linhas_da_guarda([{"uniq": uniq, "nome": "Cosmic Red"}], _perfil())
    assert linhas[0]["secoes"]["leds"] is True, f"{uniq!r}: o ajuste da luz sumiu da guarda"
    total = len(perfis_web.SECOES_NA_TELA)
    assert f"1 de {total} ajustes só deste controle" in linhas[0]["dica"]


def test_o_controle_sem_ajuste_herda_e_diz() -> None:
    linhas = perfis_web._linhas_da_guarda(
        [{"uniq": "02fe00000009", "nome": "White"}], _perfil())
    assert not any(linhas[0]["secoes"].values())
    assert "nada só dele" in linhas[0]["dica"]


def test_a_linha_fala_pela_cor_do_plastico(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: devolver o `P1 •` ao rótulo curto reprova aqui."""
    mesa = [{"pref": "p1", "uniq": SERIAL, "jogador": 1, "cor": "cosmic-red",
             "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True}]
    perfil = _perfil()
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [perfil])
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    ctx = Contexto(state={"active_profile": "Bancada"}, mesa=list(mesa),
                   conectados=list(mesa), estados={})
    fora = a10_perfis.pacote(ctx)
    nomes = fora["guarda.nome"]
    assert nomes[0] == "Cosmic Red • USB"
    assert len(nomes) == a10_perfis.LUGARES_DA_TABELA
    for nome in nomes:
        assert not any(f"P{n}" in nome for n in range(1, 5)), f"número de jogador em {nome!r}"
    cores_dos_vazios = nomes[1:]
    assert len(set(cores_dos_vazios)) == len(cores_dos_vazios), "dois vazios com a mesma cor"
    assert "Cosmic Red" not in "".join(cores_dos_vazios), "o vazio repete a cor de quem está"
