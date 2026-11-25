"""O-PERFIL-IMPORTADO-DE-NOME-REPETIDO-GANHA-NOME-PROPRIO-01: o importado repetido ganha nome.

O «Importar» do rodapé gravava o repetido como `<slug>-2.json` com o MESMO `name`: o resto do
produto acha o perfil pelo slug do `name`, e a lista passava a ter dois «Corrida», um aberto no
editor e o outro gravado. Agora o `name` muda junto («Corrida 2»), a gravação é a do `save_profile`
e o importado vira o perfil aberto no editor. O gêmeo que já está no disco ganha nome próprio, uma
vez, na primeira leitura do processo. O disco é o de verdade, no lar isolado da suíte; o último
teste clica no «Importar» da aba publicada, no WebKit sob Xvfb, no relógio do piloto.

MORDIDAS: voltar o `-N` só no nome do arquivo reprova o primeiro, o segundo e o da tela; tirar o
aberto no editor reprova o primeiro e o da tela; tirar a renomeação do gêmeo da primeira leitura
(`_maybe_seed_presets`) reprova o quarto.
"""
from __future__ import annotations

import json
import pathlib
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("o Importar da aba Perfis")

from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis, rodape
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir
from tests.unit.janela_aberta_comum import _correr, publicar_as_de_hoje

ESPERA_S = 2.0
FOTOGRAFAR: Callable[[Any, str], None] | None = None
LISTA = 'tbody[data-hef="perfis.lista"]'

LE_A_LISTA = """
(function(){
  const linhas = Array.from(document.querySelectorAll('@LISTA@ tr[data-hef-perfil]'));
  return JSON.stringify({
    real: document.querySelector('@LISTA@').dataset.hefReal === '1',
    nomes: linhas.map(function(x){ return x.dataset.hefPerfil; }),
    abertos: linhas.filter(function(x){ return x.getAttribute('aria-selected') === 'true'; })
      .map(function(x){ return x.dataset.hefPerfil; })});
})()
"""

CLICA_NO_IMPORTAR = "(function(){ document.querySelector('.r-importar').click(); return 'ok'; })()"


class _Ponte:
    def __init__(self, escolhe: str) -> None:
        self.escolhe = escolhe
        self.chamadas: list[str] = []

    def escolher_arquivo(self, *_a: Any, **_k: Any) -> str:
        return self.escolhe

    def chamar(self, metodo: str, *_a: Any, **_k: Any) -> bool:
        self.chamadas.append(metodo)
        return True

    def resultado(self, metodo: str, *_a: Any, **_k: Any) -> dict[str, Any]:
        self.chamadas.append(metodo)
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": ""}, mesa=[], conectados=[], estados={})


def _de_fora(tmp_path: pathlib.Path, nome: str, prioridade: int) -> str:
    destino = tmp_path / "de-fora.json"
    perfil = Profile(name=nome, match=MatchAny(), priority=prioridade)
    destino.write_text(perfil.model_dump_json(), encoding="utf-8")
    return str(destino)


def _no_disco(nome: str, prioridade: int) -> None:
    loader.save_profile(Profile(name=nome, match=MatchAny(), priority=prioridade), origem="régua")


def test_o_importado_repetido_ganha_nome_proprio_e_abre_no_editor(tmp_path: pathlib.Path) -> None:
    """D-1911-O-IMPORTADO-DE-NOME-REPETIDO-GANHA-NOME-PROPRIO: dois nomes, e o novo aberto."""
    _no_disco("Corrida", 10)
    ctx, ponte = _ctx(), _Ponte(_de_fora(tmp_path, "Corrida", 77))
    rodape.importar(ctx, {}, ponte)

    nomes = sorted(p.name for p in loader.load_all_profiles() if p.name.startswith("Corrida"))
    assert nomes == ["Corrida", "Corrida 2"], nomes
    assert loader.load_profile("Corrida").priority == 10, "o importado sobrescreveu o original"
    assert loader.load_profile("Corrida 2").priority == 77
    assert not list(profiles_dir().glob("corrida-*.json")), "o gêmeo voltou a nascer no disco"

    editor = a10_perfis._alvo_do_editor(ctx)
    assert editor.name == "Corrida 2" and editor.priority == 77, "o editor não abriu o importado"


def test_o_remover_apaga_o_aberto_e_nao_o_original(tmp_path: pathlib.Path) -> None:
    """D-1911-O-IMPORTADO-DE-NOME-REPETIDO-GANHA-NOME-PROPRIO: o que se vê é o que se apaga."""
    _no_disco("Corrida", 10)
    ctx, ponte = _ctx(), _Ponte(_de_fora(tmp_path, "Corrida", 77))
    rodape.importar(ctx, {}, ponte)

    with pytest.raises(RuntimeError, match="Apagar “Corrida 2”"):
        a10_perfis.remover(ctx, {}, ponte)
    a10_perfis.remover(ctx, {}, ponte)
    assert loader.perfil_em_disco("Corrida 2") is None
    assert loader.load_profile("Corrida").priority == 10


def test_importar_o_freestyle_nao_cria_um_gemeo_escondido(tmp_path: pathlib.Path) -> None:
    """D-1911-O-IMPORTADO-DE-NOME-REPETIDO-GANHA-NOME-PROPRIO: o Freestyle de fora vira «2»."""
    _no_disco(loader.NOME_DO_PADRAO, 1)
    rodape.importar(_ctx(), {}, _Ponte(_de_fora(tmp_path, loader.NOME_DO_PADRAO, 99)))
    assert loader.load_profile(loader.NOME_DO_PADRAO).priority == 1
    assert loader.load_profile(f"{loader.NOME_DO_PADRAO} 2").priority == 99


def test_o_gemeo_que_ja_esta_no_disco_ganha_nome_proprio_uma_vez(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-O-IMPORTADO-DE-NOME-REPETIDO-GANHA-NOME-PROPRIO: o `-2` antigo vira «Corrida 2»."""
    _no_disco("Corrida", 10)
    pasta = profiles_dir()
    gemeo = json.loads((pasta / "corrida.json").read_text(encoding="utf-8"))
    gemeo["priority"] = 77
    (pasta / "corrida-2.json").write_text(json.dumps(gemeo), encoding="utf-8")

    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    loader._maybe_seed_presets()
    nomes = sorted(p.name for p in loader.load_all_profiles() if p.name.startswith("Corrida"))
    assert nomes == ["Corrida", "Corrida 2"], nomes
    assert not (pasta / "corrida-2.json").exists()
    assert loader.load_profile("Corrida 2").priority == 77
    assert loader.load_profile("Corrida").priority == 10
    assert loader.os_gemeos_ganham_nome_proprio() == [], "a renomeação não é de uma vez só"


@pytest.fixture(scope="module")
def corrida(tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    publicado = publicar_as_de_hoje(tmp_path_factory)
    raiz = tmp_path_factory.mktemp("lar-do-importar")
    marcos: dict[str, Any] = {"lido": {}, "no_ar": set()}

    def le(piloto: Any, chave: str) -> bool:
        if chave in marcos["lido"]:
            return True
        if chave not in marcos["no_ar"]:
            marcos["no_ar"].add(chave)

            def volta(valor: Any, erro: Any) -> None:
                marcos["lido"][chave] = None if erro else json.loads(valor)

            piloto.ponte.perguntar(LE_A_LISTA.replace("@LISTA@", LISTA), volta)
        return False

    def roteiro(fora: Any, piloto: Any, _t: float) -> bool:
        agora = time.monotonic()
        if "pronto" not in marcos:
            if not le(piloto, "antes") or not marcos["lido"]["antes"]["real"]:
                marcos["lido"].pop("antes", None)
                return True
            marcos["pronto"] = True
            if FOTOGRAFAR is not None:
                FOTOGRAFAR(piloto, "antes")
            fora.ponte.escolher_arquivo = lambda *_a, **_k: marcos["arquivo"]
            marcos["clicou"] = agora
            piloto.ponte.rodar(CLICA_NO_IMPORTAR)
            return True
        if agora - marcos["clicou"] < ESPERA_S or not le(piloto, "depois"):
            return True
        if FOTOGRAFAR is not None:
            FOTOGRAFAR(piloto, "depois")
        return False

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("XDG_CONFIG_HOME", str(raiz))
        _no_disco("Corrida", 10)
        marcos["arquivo"] = _de_fora(tmp_path_factory.mktemp("de-fora"), "Corrida", 77)
        fora = _correr(publicado, "10-perfis.html", 1, roteiro, teto_s=90.0, tempo_real=True)
        no_disco = sorted(p.name for p in loader.load_all_profiles()
                          if p.name.startswith("Corrida"))
    return SimpleNamespace(marcos=marcos, fora=fora, no_disco=no_disco)


def test_o_botao_importar_da_tela_traz_o_nome_proprio_marcado_como_aberto(
        corrida: SimpleNamespace) -> None:
    """D-1911-O-IMPORTADO-DE-NOME-REPETIDO-GANHA-NOME-PROPRIO: na tela, «Corrida 2» e aberto."""
    m = corrida.marcos
    assert "depois" in m["lido"], "o roteiro nunca leu a lista depois do clique"
    antes, depois = m["lido"]["antes"], m["lido"]["depois"]
    assert "Corrida" in antes["nomes"] and "Corrida 2" not in antes["nomes"], antes
    assert depois["nomes"].count("Corrida") == 1 and "Corrida 2" in depois["nomes"], depois
    assert depois["abertos"] == ["Corrida 2"], depois
    assert corrida.no_disco == ["Corrida", "Corrida 2"]
