"""O-PERFIL-QUE-VALE-SE-REMOVE-COM-A-PERGUNTA-01: o perfil que vale se remove, depois da pergunta.

O clique na linha ativa o perfil, então o do editor é quase sempre o que vale, e o «Remover» o
recusava sempre. Agora o primeiro clique pergunta (o rótulo vira «Remover o que vale?» e a dica diz
quem assume os controles) e o segundo passa o serviço ao perfil de fora do jogo, pelo
`profile.switch` do «Ativar», ANTES de apagar o arquivo. O disco é o de verdade, no lar isolado
da suíte.

No WebKit de verdade, sob Xvfb, no relógio do piloto: o clique no botão da aba publicada, com o
perfil que vale aberto no editor, mostra a pergunta (rótulo, dica e borda vermelha) e o segundo
clique tira o perfil da lista.

MORDIDAS: a recusa dura de volta no `remover` reprova o primeiro, o segundo e o da tela; tirar o
`_ativar_o` do `remover` reprova o segundo; trocar o `_ativar_o` para depois do `delete_profile`
reprova o segundo e o terceiro; tirar o campo da pergunta do `pacote` reprova o da tela.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("a pergunta do Remover da aba Perfis")

from hefesto_dualsense4unix.app.actions import profiles_actions
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader
from tests.unit.janela_aberta_comum import _correr, publicar_as_de_hoje

BOTAO = '[data-hef-gesto="remover"]'
LISTA = 'tbody[data-hef="perfis.lista"]'
ESPERA_S = 2.0
FOTOGRAFAR: Callable[[Any, str], None] | None = None

CLICA_NA_LINHA = """
(function(nome){
  const tr = Array.from(document.querySelectorAll('@LISTA@ tr[data-hef-perfil]'))
    .find(function(x){ return x.dataset.hefPerfil === nome; });
  if(!tr) return 'sem linha';
  tr.querySelector('td').click();
  return 'ok';
})("Sackboy")
"""

CLICA_NO_REMOVER = "(function(){ document.querySelector('@BOTAO@').click(); return 'ok'; })()"


def _js(texto: str) -> str:
    return texto.replace("@BOTAO@", BOTAO).replace("@LISTA@", LISTA)

LE_O_BOTAO = """
(function(){
  const b = document.querySelector('@BOTAO@');
  const sonda = document.createElement('i');
  sonda.style.color = 'var(--red)';
  document.body.appendChild(sonda);
  const vermelho = getComputedStyle(sonda).color;
  sonda.remove();
  return JSON.stringify({
    real: document.querySelector('@LISTA@').dataset.hefReal === '1',
    rotulo: b.textContent.trim(), dica: b.getAttribute('data-dica') || '',
    pergunta: b.classList.contains('pergunta'),
    borda_vermelha: getComputedStyle(b).borderTopColor === vermelho,
    nomes: Array.from(document.querySelectorAll('@LISTA@ tr[data-hef-perfil]'))
      .map(function(x){ return x.dataset.hefPerfil; })});
})()
"""


class _Ponte:
    """Anota o que foi pedido e vê, no `profile.switch`, se o perfil ainda está no disco."""

    def __init__(self, recusa: bool = False) -> None:
        self.chamadas: list[tuple[str, Any]] = []
        self.no_disco_na_troca: bool | None = None
        self.recusa = recusa

    def chamar(self, metodo: str, *_a: Any, **_k: Any) -> bool:
        self.chamadas.append((metodo, None))
        return True

    def resultado(self, metodo: str, *_a: Any, **kw: Any) -> dict[str, Any]:
        self.chamadas.append((metodo, kw.get("name")))
        if self.recusa:
            raise RuntimeError("o daemon recusou")
        self.no_disco_na_troca = loader.perfil_em_disco("Sackboy") is not None
        return {"active_profile": kw.get("name")}


@pytest.fixture(autouse=True)
def _disco_e_memoria(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "Sackboy", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    for i, nome in enumerate(("Pragmata", "Sackboy", loader.NOME_DO_PADRAO)):
        loader.save_profile(Profile(name=nome, match=MatchAny(), priority=100 - i), origem="régua")


def _ctx(valendo: str | None = "Sackboy") -> Contexto:
    return Contexto(state={"active_profile": valendo} if valendo else {},
                    mesa=[], conectados=[], estados={})


def test_o_primeiro_clique_pergunta_com_o_rotulo_e_a_dica_do_que_vale() -> None:
    """D-1911-O-PERFIL-QUE-VALE-SE-REMOVE-COM-A-PERGUNTA: pergunta antes, sem apagar nem trocar."""
    ctx, ponte = _ctx(), _Ponte()
    antes = a10_perfis.pacote(ctx)
    assert antes["perfis.remover"] == "Remover"
    assert antes[a10_perfis.CAMPO_DA_PERGUNTA_DO_REMOVER] == ""

    with pytest.raises(RuntimeError, match="Apagar “Sackboy”"):
        a10_perfis.remover(ctx, {}, ponte)

    depois = a10_perfis.pacote(ctx)
    assert depois["perfis.remover"] == a10_perfis.ROTULO_DO_QUE_VALE
    dica = depois[a10_perfis.CAMPO_DA_PERGUNTA_DO_REMOVER]
    assert "«Sackboy» está valendo" in dica and "perfil do computador" in dica
    assert loader.perfil_em_disco("Sackboy") is not None
    assert ponte.chamadas == []


def test_o_segundo_clique_passa_ao_perfil_do_computador_antes_de_apagar() -> None:
    """D-1911-O-PERFIL-QUE-VALE-SE-REMOVE-COM-A-PERGUNTA: o que vale sai e o Freestyle assume."""
    ctx, ponte = _ctx(), _Ponte()
    with pytest.raises(RuntimeError):
        a10_perfis.remover(ctx, {}, ponte)
    a10_perfis.remover(ctx, {}, ponte)

    assert ponte.chamadas == [("profile.switch", loader.NOME_DO_PADRAO),
                              ("launch_env.refresh", None)]
    assert ponte.no_disco_na_troca is True, "o arquivo saiu antes de o serviço trocar"
    assert loader.perfil_em_disco("Sackboy") is None
    assert loader.perfil_em_disco("Pragmata") is not None


def test_a_recusa_do_daemon_na_troca_deixa_o_perfil_no_disco() -> None:
    """D-1911-O-PERFIL-QUE-VALE-SE-REMOVE-COM-A-PERGUNTA: sem troca, nada é apagado."""
    ctx, ponte = _ctx(), _Ponte(recusa=True)
    with pytest.raises(RuntimeError):
        a10_perfis.remover(ctx, {}, ponte)
    with pytest.raises(RuntimeError, match="não confirmou"):
        a10_perfis.remover(ctx, {}, ponte)
    assert loader.perfil_em_disco("Sackboy") is not None


def test_com_o_servico_parado_o_marcador_vale_e_nada_se_troca(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-O-PERFIL-QUE-VALE-SE-REMOVE-COM-A-PERGUNTA: serviço calado, nada a trocar."""
    monkeypatch.setattr(profiles_actions, "perfil_que_o_usuario_ativou", lambda: "Sackboy")
    ctx, ponte = _ctx(None), _Ponte()
    with pytest.raises(RuntimeError):
        a10_perfis.remover(ctx, {}, ponte)
    a10_perfis.remover(ctx, {}, ponte)
    assert ponte.chamadas == [("launch_env.refresh", None)]
    assert loader.perfil_em_disco("Sackboy") is None


def test_outro_perfil_continua_sem_troca_nem_dica_de_quem_vale() -> None:
    """D-1911-O-PERFIL-QUE-VALE-SE-REMOVE-COM-A-PERGUNTA: o que não vale não troca o serviço."""
    ctx, ponte = _ctx("Pragmata"), _Ponte()
    with pytest.raises(RuntimeError):
        a10_perfis.remover(ctx, {}, ponte)
    pergunta = a10_perfis.pacote(ctx)
    assert pergunta["perfis.remover"] == "Remover “Sackboy”? Clique de novo"
    assert pergunta[a10_perfis.CAMPO_DA_PERGUNTA_DO_REMOVER] == ""
    a10_perfis.remover(ctx, {}, ponte)
    assert ponte.chamadas == [("launch_env.refresh", None)]


@pytest.fixture(scope="module")
def corrida(tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    publicado = publicar_as_de_hoje(tmp_path_factory)
    raiz = tmp_path_factory.mktemp("lar-do-remover")
    marcos: dict[str, Any] = {"lido": {}, "no_ar": set()}

    def le(piloto: Any, chave: str) -> bool:
        if chave in marcos["lido"]:
            return True
        if chave not in marcos["no_ar"]:
            marcos["no_ar"].add(chave)

            def volta(valor: Any, erro: Any) -> None:
                marcos["lido"][chave] = None if erro else json.loads(valor)

            piloto.ponte.perguntar(_js(LE_O_BOTAO), volta)
        return False

    def clicar(piloto: Any, js: str, etapa: str) -> None:
        marcos[etapa] = time.monotonic()
        piloto.ponte.rodar(_js(js))

    def fotografar(piloto: Any, nome: str) -> None:
        if FOTOGRAFAR is not None:
            FOTOGRAFAR(piloto, nome)

    def roteiro(fora: Any, piloto: Any, _t: float) -> bool:
        agora = time.monotonic()
        if "pronto" not in marcos:
            if not le(piloto, "inicio") or not marcos["lido"]["inicio"]["real"]:
                marcos["lido"].pop("inicio", None)
                return True
            marcos["pronto"] = True
            marcos["trocas"] = []

            def resultado(metodo: str, *_a: Any, **kw: Any) -> dict[str, Any]:
                fora.ponte.chamadas.append("resultado")
                if metodo != "profile.switch":
                    return {}
                if kw.get("name") == loader.NOME_DO_PADRAO:
                    marcos["trocas"].append(kw["name"])
                fora.estado.base["active_profile"] = kw.get("name")
                return {"active_profile": kw.get("name")}

            fora.ponte.resultado = resultado
            fora.estado.base["active_profile"] = "Sackboy"
            clicar(piloto, CLICA_NA_LINHA, "linha")
            return True
        if "antes" not in marcos["lido"] and agora - marcos["linha"] < ESPERA_S:
            return True
        if not le(piloto, "antes"):
            return True
        if "primeiro" not in marcos:
            fotografar(piloto, "antes")
            clicar(piloto, CLICA_NO_REMOVER, "primeiro")
            return True
        if agora - marcos["primeiro"] < ESPERA_S:
            return True
        if not le(piloto, "pergunta"):
            return True
        if "segundo" not in marcos:
            fotografar(piloto, "pergunta")
            marcos["trocas_na_pergunta"] = len(marcos["trocas"])
            clicar(piloto, CLICA_NO_REMOVER, "segundo")
            return True
        if agora - marcos["segundo"] < ESPERA_S:
            return True
        if not le(piloto, "depois"):
            return True
        fotografar(piloto, "depois")
        marcos["trocas_depois"] = len(marcos["trocas"])
        return False

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("XDG_CONFIG_HOME", str(raiz))
        for i, nome in enumerate(("Pragmata", "Sackboy", loader.NOME_DO_PADRAO)):
            from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

            loader.save_profile(Profile(name=nome, match=MatchAny(), priority=100 - i),
                                origem="régua")
        fora = _correr(publicado, "10-perfis.html", 1, roteiro, teto_s=90.0, tempo_real=True)
        no_disco = sorted(p.name for p in loader.load_all_profiles())
    return SimpleNamespace(marcos=marcos, fora=fora, no_disco=no_disco)


def test_o_botao_da_tela_pergunta_com_a_borda_vermelha_e_tira_o_perfil_que_vale(
        corrida: SimpleNamespace) -> None:
    """D-1911-O-PERFIL-QUE-VALE-SE-REMOVE-COM-A-PERGUNTA: o clique pergunta, o outro apaga."""
    m = corrida.marcos
    assert "trocas_depois" in m, "o roteiro nunca chegou ao segundo clique"
    antes, pergunta, depois = (m["lido"][k] for k in ("antes", "pergunta", "depois"))
    assert antes["rotulo"] == "Remover" and not antes["pergunta"], antes
    assert pergunta["rotulo"] == "Remover o que vale?", pergunta
    assert pergunta["pergunta"] and pergunta["borda_vermelha"], pergunta
    assert "«Sackboy» está valendo" in pergunta["dica"], pergunta
    assert "Sackboy" in pergunta["nomes"] and "Sackboy" not in depois["nomes"], (pergunta, depois)
    assert m["trocas_na_pergunta"] == 0, "a pergunta já trocou o perfil do serviço"
    assert m["trocas_depois"] == 1, "o segundo clique não passou ao perfil do computador"
    assert "Sackboy" not in corrida.no_disco and loader.NOME_DO_PADRAO in corrida.no_disco
