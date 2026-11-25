"""O-NOME-QUE-NAO-SERVE-SE-RECUSA-ANTES-DE-RENOMEAR-01: o nome que não serve se recusa antes.

O `perfis_renomear` gravava `prof.model_copy(update={"name": novo})`, que não roda o validador do
nome, e apagava o arquivo antigo: «Jogo 1/2» deixava `jogo_12.json` inválido no disco, o perfil
sumia da lista com tudo o que guardava. Agora o dono de «este nome serve?» é o esquema
(`recusa_do_nome_do_perfil`), o gesto recusa antes de gravar e a faixa do alto da aba diz o motivo.
No WebKit de verdade, sob Xvfb, no relógio do piloto: o campo do nome fica aberto com a borda
laranja e a faixa diz o motivo; corrigido o nome, o perfil é renomeado.

MORDIDAS: tirar a pergunta do esquema do `perfis_renomear` reprova o primeiro e o da tela; voltar o
`model_copy` reprova o segundo (o perfil gravado não relê); tirar o observador do campo do
`ROTEIRO` de `aba10.py` reprova o da tela.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("a recusa do nome na aba Perfis")

from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader, schema
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir
from tests.unit.janela_aberta_comum import _correr, publicar_as_de_hoje

LISTA = 'tbody[data-hef="perfis.lista"]'
ESPERA_S = 2.0
FOTOGRAFAR: Callable[[Any, str], None] | None = None

DUPLO_CLIQUE = """
(function(nome){
  const tr = Array.from(document.querySelectorAll('@LISTA@ tr[data-hef-perfil]'))
    .find(function(x){ return x.dataset.hefPerfil === nome; });
  if(!tr) return 'sem linha';
  const td = tr.querySelector('td[data-hef="perfis.linha.nome"]');
  const base = {bubbles: true, cancelable: true, view: window};
  td.dispatchEvent(new MouseEvent('click', Object.assign({detail: 1}, base)));
  td.dispatchEvent(new MouseEvent('click', Object.assign({detail: 2}, base)));
  td.dispatchEvent(new MouseEvent('dblclick', Object.assign({detail: 2}, base)));
  return 'ok';
})("Sackboy")
"""

DIGITA_E_APERTA_ENTER = """
(function(valor){
  const c = document.querySelector('@LISTA@ input.renome');
  if(!c) return 'sem campo';
  c.value = valor;
  c.dispatchEvent(new Event('change', {bubbles: true}));
  c.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}));
  return 'ok';
})(@VALOR@)
"""

ROLA_ATE_O_CAMPO = (
    "(function(){ const c = document.querySelector('@LISTA@ input.renome');"
    " if(c) c.scrollIntoView({block: 'center'}); return 'ok'; })()")

LE_A_TELA = """
(function(){
  const c = document.querySelector('@LISTA@ input.renome');
  const faixa = document.querySelector('div.desfecho');
  const sonda = document.createElement('i');
  sonda.style.color = 'var(--orange)';
  document.body.appendChild(sonda);
  const laranja = getComputedStyle(sonda).color;
  sonda.remove();
  return JSON.stringify({
    real: document.querySelector('@LISTA@').dataset.hefReal === '1',
    aberto: !!c, foco: !!c && document.activeElement === c, valor: c ? c.value : '',
    recusado: !!c && c.classList.contains('recusado'),
    borda_laranja: !!c && getComputedStyle(c).borderTopColor === laranja,
    faixa: faixa.textContent.trim(), faixa_acesa: faixa.classList.contains('on'),
    faixa_laranja: getComputedStyle(faixa).color === laranja,
    nomes: Array.from(document.querySelectorAll('@LISTA@ tr[data-hef-perfil]'))
      .map(function(x){ return x.dataset.hefPerfil; })});
})()
"""


def _js(texto: str, valor: str = "") -> str:
    return texto.replace("@LISTA@", LISTA).replace("@VALOR@", json.dumps(valor))


def _no_disco(*nomes: str) -> None:
    for i, nome in enumerate(nomes):
        loader.save_profile(Profile(name=nome, match=MatchAny(), priority=100 - i), origem="régua")


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_DESFECHO", None, raising=False)


class _Ponte:
    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, *_a: Any, **_k: Any) -> bool:
        self.chamadas.append(metodo)
        return True

    def resultado(self, metodo: str, *_a: Any, **_k: Any) -> dict[str, Any]:
        self.chamadas.append(metodo)
        return {}


def _renomear(era: str, novo: str) -> Any:
    ctx = Contexto(state={"active_profile": "Pragmata"}, mesa=[], conectados=[], estados={})
    return ctx, a10_perfis.perfis_renomear(ctx, {"valor": novo, "hefPerfil": era}, _Ponte())


@pytest.mark.parametrize(("novo", "frase"), [
    ("Jogo 1/2", schema.FRASE_DO_NOME_COM_BARRA),
    ("Meu..jogo", schema.FRASE_DO_NOME_COM_BARRA),
    ("///", schema.FRASE_DO_NOME_COM_BARRA),
    ("!!!", schema.FRASE_DO_NOME_SEM_SLUG),
])
def test_o_nome_que_nao_serve_se_recusa_e_o_perfil_fica_como_estava(novo: str, frase: str) -> None:
    """D-1911-O-NOME-QUE-NAO-SERVE-SE-RECUSA-ANTES-DE-RENOMEAR: recusa com o motivo."""
    _no_disco("Pragmata", "Jogo")
    antes = (profiles_dir() / "jogo.json").read_bytes()
    with pytest.raises(RuntimeError) as erro:
        _renomear("Jogo", novo)
    assert str(erro.value) == frase
    assert (profiles_dir() / "jogo.json").read_bytes() == antes, "o arquivo do perfil mudou"
    assert sorted(p.stem for p in profiles_dir().glob("*.json")) == ["jogo", "pragmata"]
    ctx = Contexto(state={"active_profile": "Pragmata"}, mesa=[], conectados=[], estados={})
    assert a10_perfis.pacote(ctx)["perfis.desfecho"] == frase, "a faixa do alto não diz o motivo"


def test_o_nome_com_acento_e_espaco_renomeia() -> None:
    """D-1911-O-NOME-QUE-NAO-SERVE-SE-RECUSA-ANTES-DE-RENOMEAR: o nome que serve segue valendo."""
    _no_disco("Pragmata", "Jogo")
    _, resposta = _renomear("Jogo", "Ação é ótima")
    assert resposta is not None
    nomes = {p.name for p in loader.load_all_profiles()}
    assert {"Pragmata", "Ação é ótima"} <= nomes and "Jogo" not in nomes, nomes
    assert a10_perfis._desfecho_para_a_tela() == ""


def test_o_perfil_renomeado_volta_do_disco_igual_menos_o_nome() -> None:
    """D-1911-O-NOME-QUE-NAO-SERVE-SE-RECUSA-ANTES-DE-RENOMEAR: o `renomeado` não perde campo."""
    _no_disco("Jogo")
    perfil = loader.load_profile("Jogo")
    outro = perfil.renomeado("Jogo outro")
    assert outro.name == "Jogo outro"
    assert outro.model_dump() == {**perfil.model_dump(), "name": "Jogo outro"}
    with pytest.raises(ValueError, match="barra"):
        perfil.renomeado("Jogo 1/2")


def test_o_jogo_com_barra_no_nome_vira_perfil_com_espaco_no_lugar() -> None:
    """D-1911-O-NOME-QUE-NAO-SERVE-SE-RECUSA-ANTES-DE-RENOMEAR: a barra do jogo vira espaço."""
    ctx = Contexto(state={}, mesa=[], conectados=[], estados={})
    frase = a10_perfis.criar_para_o_jogo(ctx, _Ponte(), classes=("jogo.exe",),
                                         nome_do_jogo="Jogo 1/2")
    assert frase == "Perfil criado: Jogo 1 2", frase
    assert loader.load_profile("Jogo 1 2").nome_do_jogo == "Jogo 1/2"


@pytest.fixture(scope="module")
def corrida(tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    publicado = publicar_as_de_hoje(tmp_path_factory)
    raiz = tmp_path_factory.mktemp("lar-do-nome")
    marcos: dict[str, Any] = {"lido": {}, "no_ar": set()}

    def le(piloto: Any, chave: str) -> bool:
        if chave in marcos["lido"]:
            return True
        if chave not in marcos["no_ar"]:
            marcos["no_ar"].add(chave)

            def volta(valor: Any, erro: Any) -> None:
                marcos["lido"][chave] = None if erro else json.loads(valor)

            piloto.ponte.perguntar(_js(LE_A_TELA), volta)
        return False

    def foto(piloto: Any, nome: str) -> None:
        if FOTOGRAFAR is not None:
            FOTOGRAFAR(piloto, nome)

    def digita(piloto: Any, valor: str, etapa: str) -> None:
        marcos[etapa] = time.monotonic()
        piloto.ponte.rodar(_js(DIGITA_E_APERTA_ENTER, valor))

    def roteiro(fora: Any, piloto: Any, _t: float) -> bool:
        agora = time.monotonic()
        if "abriu" not in marcos:
            if not le(piloto, "inicio") or not marcos["lido"]["inicio"]["real"]:
                marcos["lido"].pop("inicio", None)
                return True
            marcos["abriu"] = agora
            foto(piloto, "antes")
            piloto.ponte.rodar(_js(DUPLO_CLIQUE))
            return True
        if "ruim" not in marcos:
            if agora - marcos["abriu"] < ESPERA_S:
                return True
            digita(piloto, "Jogo 1/2", "ruim")
            return True
        if agora - marcos["ruim"] < ESPERA_S or not le(piloto, "recusado"):
            return True
        if "bom" not in marcos:
            if "rolou" not in marcos:
                marcos["rolou"] = agora
                piloto.ponte.rodar(_js(ROLA_ATE_O_CAMPO))
                return True
            if agora - marcos["rolou"] < 0.5:
                return True
            foto(piloto, "recusado")
            digita(piloto, "Sackboy 2", "bom")
            return True
        if agora - marcos["bom"] < ESPERA_S or not le(piloto, "corrigido"):
            return True
        foto(piloto, "corrigido")
        return False

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("XDG_CONFIG_HOME", str(raiz))
        _no_disco("Pragmata", "Sackboy")
        fora = _correr(publicado, "10-perfis.html", 1, roteiro, teto_s=90.0, tempo_real=True)
        no_disco = sorted(p.stem for p in profiles_dir().glob("*.json"))
    return SimpleNamespace(marcos=marcos, fora=fora, no_disco=no_disco)


def test_o_campo_fica_aberto_com_a_borda_laranja_e_a_faixa_diz_o_motivo(
        corrida: SimpleNamespace) -> None:
    """D-1911-O-NOME-QUE-NAO-SERVE-SE-RECUSA-ANTES-DE-RENOMEAR: o campo espera a correção."""
    m = corrida.marcos["lido"]
    assert "corrigido" in m, "o roteiro nunca chegou à correção"
    tela = m["recusado"]
    assert tela["aberto"] and tela["foco"] and tela["valor"] == "Jogo 1/2", tela
    assert tela["recusado"] and tela["borda_laranja"], tela
    assert tela["faixa"] == schema.FRASE_DO_NOME_COM_BARRA, tela
    assert tela["faixa_acesa"] and tela["faixa_laranja"], tela
    assert "Sackboy" in tela["nomes"], "o perfil saiu da lista"


def test_corrigido_o_nome_o_perfil_e_renomeado_e_a_faixa_se_apaga(
        corrida: SimpleNamespace) -> None:
    """D-1911-O-NOME-QUE-NAO-SERVE-SE-RECUSA-ANTES-DE-RENOMEAR: o nome novo entra, sem sobra."""
    tela = corrida.marcos["lido"]["corrigido"]
    assert not tela["aberto"], "o campo seguiu aberto depois do nome que serve"
    assert "Sackboy 2" in tela["nomes"] and "Sackboy" not in tela["nomes"], tela
    assert not tela["faixa_acesa"], tela
    assert "sackboy_2" in corrida.no_disco and "sackboy" not in corrida.no_disco
    assert not [n for n in corrida.no_disco if "1" in n], corrida.no_disco
