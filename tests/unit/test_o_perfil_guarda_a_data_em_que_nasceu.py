"""O-PERFIL-GUARDA-A-DATA-EM-QUE-NASCEU-E-A-DA-ULTIMA-MUDANCA-01 — as duas datas do perfil.

Medido antes de curar (15/10/2026): o `Profile` não tinha data nenhuma, e o `mtime` do `.json`
não serve porque a semeadura e o salvar automático reescrevem o arquivo. Os esperados abaixo são
escritos à mão, com o relógio do `loader` trocado por um que anda de dia em dia, e lidos do
ARQUIVO no disco.

MORDIDAS (cada uma foi feita e viu reprovar):

* gravar `criado_em` em todo salvar -> o salvar seguinte troca a data de nascimento;
* tirar o `gesto_de_agora` da condição -> o salvar automático muda `modificado_em`;
* tirar a comparação com o arquivo de antes -> o salvar sem mudança também carimba;
* semear sem `criado_em` -> o perfil semeado nasce sem data.
"""
from __future__ import annotations

import itertools
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations.jogos_locais import JogoLocal
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.loader import gesto_de_agora, load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile

DIA_1 = "2026-10-01T09:00:00-03:00"
DIA_2 = "2026-10-02T09:00:00-03:00"
DIA_3 = "2026-10-03T09:00:00-03:00"


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    dias = itertools.chain((DIA_1, DIA_2, DIA_3), itertools.repeat("2026-12-31T00:00:00-03:00"))
    monkeypatch.setattr(loader, "_agora_local", lambda: next(dias))
    yield


@pytest.fixture
def dir_perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _falso(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader, "profiles_dir", _falso)
    return alvo


def _lido(dir_perfis: Path, arquivo: str = "forja.json") -> dict[str, Any]:
    return json.loads((dir_perfis / arquivo).read_text(encoding="utf-8"))


def _perfil(prioridade: int = 10, **resto: Any) -> Profile:
    return Profile(name="Forja", match=MatchAny(), priority=prioridade, **resto)


def _por_gesto(perfil: Profile, **kw: Any) -> None:
    marca = gesto_de_agora.set("teste · gesto dela")
    try:
        save_profile(perfil, **kw)
    finally:
        gesto_de_agora.reset(marca)


def test_o_perfil_novo_nasce_com_criado_em_e_sem_modificado_em(
    relogio: None, dir_perfis: Path,
) -> None:
    save_profile(_perfil())
    arquivo = _lido(dir_perfis)
    assert arquivo["criado_em"] == DIA_1
    assert "modificado_em" not in arquivo


def test_o_gesto_dela_muda_so_o_modificado_em(relogio: None, dir_perfis: Path) -> None:
    """MORDIDA: gravar `criado_em` em todo salvar troca o DIA_1 pelo DIA_3."""
    save_profile(_perfil())
    _por_gesto(load_profile("Forja").model_copy(update={"priority": 77}))
    arquivo = _lido(dir_perfis)
    assert arquivo["priority"] == 77
    assert arquivo["criado_em"] == DIA_1
    assert arquivo["modificado_em"] == DIA_2


def test_o_salvar_automatico_nao_muda_nenhuma_data(relogio: None, dir_perfis: Path) -> None:
    """MORDIDA: tirar o `gesto_de_agora` da condição carimba o automático.

    Prova da D-1510-O-PERFIL-GUARDA-AS-DUAS-DATAS.
    """
    save_profile(_perfil())
    assert gesto_de_agora.get() is None
    save_profile(load_profile("Forja").model_copy(update={"priority": 55}))
    arquivo = _lido(dir_perfis)
    assert arquivo["priority"] == 55
    assert arquivo["criado_em"] == DIA_1
    assert "modificado_em" not in arquivo


def test_o_gesto_que_nao_muda_nada_deixa_o_arquivo_igual(relogio: None, dir_perfis: Path) -> None:
    """MORDIDA: tirar a comparação com o arquivo de antes carimba o salvar vazio."""
    save_profile(_perfil())
    antes = (dir_perfis / "forja.json").read_bytes()
    _por_gesto(load_profile("Forja"))
    assert (dir_perfis / "forja.json").read_bytes() == antes


def test_a_origem_automatica_nao_muda_a_data_nem_com_gesto_em_curso(
    relogio: None, dir_perfis: Path,
) -> None:
    save_profile(_perfil())
    _por_gesto(load_profile("Forja").model_copy(update={"priority": 31}),
               origem="lancador_agnostico")
    assert "modificado_em" not in _lido(dir_perfis)


def test_a_data_do_arquivo_vence_a_do_objeto_em_memoria(relogio: None, dir_perfis: Path) -> None:
    save_profile(_perfil())
    velho = load_profile("Forja").model_copy(update={"criado_em": "1999-01-01T00:00:00-03:00"})
    _por_gesto(velho.model_copy(update={"priority": 12}))
    assert _lido(dir_perfis)["criado_em"] == DIA_1


def test_a_copia_de_outro_perfil_nasce_com_a_data_de_hoje(relogio: None, dir_perfis: Path) -> None:
    save_profile(_perfil())
    _por_gesto(load_profile("Forja").model_copy(update={"name": "Forja 2"}))
    assert _lido(dir_perfis, "forja_2.json")["criado_em"] == DIA_2
    assert "modificado_em" not in _lido(dir_perfis, "forja_2.json")


def test_o_perfil_antigo_carrega_e_salva_sem_data_falsa(relogio: None, dir_perfis: Path) -> None:
    antigo = {"name": "Forja", "version": 1, "match": {"type": "any"}, "priority": 10}
    (dir_perfis / "forja.json").write_text(json.dumps(antigo), encoding="utf-8")
    perfil = load_profile("Forja")
    assert perfil.criado_em is None and perfil.modificado_em is None

    save_profile(perfil)
    assert "criado_em" not in _lido(dir_perfis) and "modificado_em" not in _lido(dir_perfis)

    _por_gesto(perfil.model_copy(update={"priority": 20}))
    arquivo = _lido(dir_perfis)
    assert "criado_em" not in arquivo, "o perfil antigo não nasceu hoje"
    assert arquivo["modificado_em"] == DIA_1


def test_a_data_estragada_no_arquivo_nao_derruba_o_perfil(dir_perfis: Path) -> None:
    bruto = {"name": "Forja", "version": 1, "match": {"type": "any"}, "priority": 10,
             "criado_em": "ontem de tarde", "modificado_em": 7}
    (dir_perfis / "forja.json").write_text(json.dumps(bruto), encoding="utf-8")
    perfil = load_profile("Forja")
    assert perfil.criado_em is None and perfil.modificado_em is None


def test_a_semeadura_grava_criado_em_e_o_gesto_em_curso_nao_a_carimba(
    relogio: None, tmp_path: Path,
) -> None:
    """MORDIDA: semear sem `criado_em` deixa o perfil do jogo sem data."""
    destino = tmp_path / "semeados"
    destino.mkdir()
    marca = gesto_de_agora.set("ipc:profile.list")
    try:
        loader.semear_perfis_dos_jogos(
            dest_dir=destino,
            jogos=[JogoLocal(appid="1245620", nome="Elden Ring", fonte="steam")])
    finally:
        gesto_de_agora.reset(marca)
    bruto = json.loads((destino / "elden_ring.json").read_text(encoding="utf-8"))
    assert bruto["criado_em"] == DIA_1
    assert "modificado_em" not in bruto
    assert set(bruto) == {"name", "match", "priority", "criado_em"}


def test_o_perfil_de_jogo_intocado_continua_intocado_com_a_data(relogio: None) -> None:
    """A data não conta como edição: o enxugar segue reconhecendo o perfil de jogo da semeadura."""
    gordo = loader._payload_do_perfil(Profile(
        name="Elden Ring", match=MatchCriteria(window_class=["steam_app_1245620"]),
        priority=loader.PRIORIDADE_DO_PERFIL_DE_JOGO, criado_em=DIA_1, modificado_em=DIA_2))
    assert loader._e_perfil_de_jogo_intocado(gordo) is True
    assert loader._e_perfil_de_jogo_intocado({**gordo, "mic": {"muted": True}}) is False


def test_o_criado_por_criterio_de_janela_tambem_ganha_a_data(
    relogio: None, dir_perfis: Path,
) -> None:
    perfil = Profile(name="Forja", match=MatchCriteria(window_class=["forja"]), priority=5)
    save_profile(perfil)
    assert _lido(dir_perfis)["criado_em"] == DIA_1
