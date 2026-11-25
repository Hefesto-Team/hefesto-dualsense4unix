"""O-DUPLO-CLIQUE-RENOMEIA-SEM-ATIVAR-E-O-CAMPO-FICA-01: o duplo clique renomeia sem ativar.

O WebKit de verdade, sob Xvfb, no relógio do piloto: a aba Perfis publicada, dois perfis no
disco de um lar de mentira, «Pragmata» valendo. Duplo clique em «Sackboy»:

1. o campo `input.renome` abre e nenhum `selecionar` chega ao daemon (o clique do nome espera o
   intervalo do duplo clique, e o segundo clique cancela a espera);
2. o daemon passa a dizer «Sackboy» enquanto o campo está aberto (o que a troca de perfil faria):
   o piloto adia a reescrita do `<tbody>` que tem campo de texto em edição, e o campo fica com o
   foco e o texto;
3. digitar e Enter manda o `perfis.renomear` com o valor, e a lista traz o nome novo;
4. o clique simples no nome continua ativando, passado o intervalo do duplo clique DO SISTEMA
   (`gtk-double-click-time`, o que o WebKit usa para contar o segundo clique), e não antes.

MORDIDAS: tirar o `campo_em_edicao` do laço de `blocos` do `hefesto_vivo.py` reprova o 2; tirar o
ouvinte de `click` em captura do roteiro de `aba10.py` reprova o 1; a espera fixa de 400 ms no
lugar do intervalo do sistema reprova o 4.
"""
from __future__ import annotations

import json
import pathlib
import time
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("o duplo clique da aba Perfis")

from tests.unit.janela_aberta_comum import (
    _correr,
    _gtk,
    publicar_as_de_hoje,
)

PAGINA = "10-perfis.html"
LISTA = 'tbody[data-hef="perfis.lista"]'
DUPLO_CLIQUE_DO_SISTEMA_MS = 1000
AINDA_NO_INTERVALO_S = 0.7
ESPERA_S = 2.0

DISPARA_O_DUPLO_CLIQUE = """
(function(nome){
  const tr = Array.from(document.querySelectorAll('@LISTA@ tr[data-hef-perfil]'))
    .find(function(x){ return x.dataset.hefPerfil === nome; });
  if(!tr) return 'sem linha';
  const td = tr.querySelector('td[data-hef="perfis.linha.nome"]');
  const base = {bubbles: true, cancelable: true, view: window};
  td.dispatchEvent(new MouseEvent('mousedown', Object.assign({detail: 1}, base)));
  td.dispatchEvent(new MouseEvent('mouseup', Object.assign({detail: 1}, base)));
  td.dispatchEvent(new MouseEvent('click', Object.assign({detail: 1}, base)));
  td.dispatchEvent(new MouseEvent('mousedown', Object.assign({detail: 2}, base)));
  td.dispatchEvent(new MouseEvent('mouseup', Object.assign({detail: 2}, base)));
  td.dispatchEvent(new MouseEvent('click', Object.assign({detail: 2}, base)));
  td.dispatchEvent(new MouseEvent('dblclick', Object.assign({detail: 2}, base)));
  return 'ok';
})(@NOME@)
"""

DISPARA_O_CLIQUE = """
(function(nome){
  const tr = Array.from(document.querySelectorAll('@LISTA@ tr[data-hef-perfil]'))
    .find(function(x){ return x.dataset.hefPerfil === nome; });
  if(!tr) return 'sem linha';
  tr.querySelector('td[data-hef="perfis.linha.nome"]').dispatchEvent(
    new MouseEvent('click', {bubbles: true, cancelable: true, view: window, detail: 1}));
  return 'ok';
})(@NOME@)
"""

LE_O_CAMPO = """
(function(){
  const c = document.querySelector('@LISTA@ input.renome');
  return JSON.stringify({
    real: document.querySelector('@LISTA@').dataset.hefReal === '1',
    aberto: !!c, foco: !!c && document.activeElement === c,
    valor: c ? c.value : '',
    nomes: Array.from(document.querySelectorAll('@LISTA@ tr[data-hef-perfil]'))
      .map(function(x){ return x.dataset.hefPerfil; })});
})()
"""

DIGITA_E_APERTA_ENTER = """
(function(){
  const c = document.querySelector('@LISTA@ input.renome');
  if(!c) return 'sem campo';
  c.value = 'Sackboy remasterizado';
  c.dispatchEvent(new Event('change', {bubbles: true}));
  c.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}));
  return 'ok';
})()
"""


def _js(texto: str, nome: str = "") -> str:
    return texto.replace("@LISTA@", LISTA).replace("@NOME@", json.dumps(nome))


def o_clique_no_nome(nome: str) -> str:
    return _js(DISPARA_O_CLIQUE, nome)


def _perfis_no_disco() -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    for i, nome in enumerate(("Pragmata", "Sackboy")):
        loader.save_profile(Profile(name=nome, match=MatchAny(), priority=100 - i))


@pytest.fixture(scope="module")
def publicado_de_hoje(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    return publicar_as_de_hoje(tmp_path_factory)


@pytest.fixture(scope="module")
def corrida(publicado_de_hoje: pathlib.Path,
            tmp_path_factory: pytest.TempPathFactory) -> SimpleNamespace:
    raiz = tmp_path_factory.mktemp("lar-dos-perfis")
    marcos: dict[str, Any] = {"lido": {}}

    def pergunta(piloto: Any, chave: str, js: str) -> None:
        marcos.setdefault("no_ar", set())
        if chave in marcos["no_ar"]:
            return
        marcos["no_ar"].add(chave)

        def volta(valor: Any, erro: Any) -> None:
            marcos["no_ar"].discard(chave)
            marcos["lido"][chave] = None if erro else valor

        piloto.ponte.perguntar(js, volta)

    def roteiro(fora: Any, piloto: Any, _t: float) -> bool:
        agora = time.monotonic()
        lido = marcos["lido"]
        if "abriu" not in marcos:
            pergunta(piloto, "linhas", _js(LE_O_CAMPO))
            visto = lido.get("linhas")
            if not visto or not json.loads(visto)["real"]:
                lido.pop("linhas", None)
                return True
            marcos["abriu"] = agora
            marcos["resultados_antes"] = fora.ponte.chamadas.count("resultado")
            piloto.ponte.rodar(_js(DISPARA_O_DUPLO_CLIQUE, "Sackboy"))
            return True
        if "daemon_trocou" not in marcos:
            if agora - marcos["abriu"] < ESPERA_S:
                return True
            marcos["gestos_do_duplo"] = [g.get("gesto") for g in piloto.gestos]
            marcos["resultados_do_duplo"] = (
                fora.ponte.chamadas.count("resultado") - marcos["resultados_antes"])
            pergunta(piloto, "campo_aberto", _js(LE_O_CAMPO))
            if "campo_aberto" not in lido:
                return True
            fora.estado.base["active_profile"] = "Sackboy"
            marcos["daemon_trocou"] = agora
            return True
        if "digitou" not in marcos:
            if agora - marcos["daemon_trocou"] < ESPERA_S:
                return True
            pergunta(piloto, "campo_depois_do_tique", _js(LE_O_CAMPO))
            if "campo_depois_do_tique" not in lido:
                return True
            piloto.ponte.rodar(_js(DIGITA_E_APERTA_ENTER))
            marcos["digitou"] = agora
            return True
        if "renomeou" not in marcos:
            if agora - marcos["digitou"] < ESPERA_S:
                return True
            marcos["gestos_do_enter"] = [
                (g.get("gesto"), g.get("valor")) for g in piloto.gestos]
            pergunta(piloto, "lista_depois", _js(LE_O_CAMPO))
            if "lista_depois" not in lido:
                return True
            marcos["renomeou"] = agora
            fora.estado.base["active_profile"] = "Pragmata"
            piloto.gestos.clear()
            piloto.ponte.rodar(o_clique_no_nome("Sackboy remasterizado"))
            return True
        if "clicou" not in marcos:
            if agora - marcos["renomeou"] < AINDA_NO_INTERVALO_S:
                marcos["antes_do_intervalo"] = [g.get("gesto") for g in piloto.gestos]
                return True
            if agora - marcos["renomeou"] < ESPERA_S:
                return True
            marcos["depois_do_intervalo"] = [g.get("gesto") for g in piloto.gestos]
            marcos["clicou"] = agora
        return False

    ajustes = _gtk().Settings.get_default()
    do_sistema = ajustes.get_property("gtk-double-click-time")
    ajustes.set_property("gtk-double-click-time", DUPLO_CLIQUE_DO_SISTEMA_MS)
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("XDG_CONFIG_HOME", str(raiz))
            _perfis_no_disco()
            fora = _correr(publicado_de_hoje, PAGINA, 1, roteiro,
                           teto_s=90.0, tempo_real=True)
            from hefesto_dualsense4unix.profiles import loader

            no_disco = sorted(p.name for p in loader.load_all_profiles())
    finally:
        ajustes.set_property("gtk-double-click-time", do_sistema)
    return SimpleNamespace(marcos=marcos, fora=fora, no_disco=no_disco)


def test_o_duplo_clique_abre_o_campo_e_nao_ativa(corrida: SimpleNamespace) -> None:
    """D-1911-O-DUPLO-CLIQUE-RENOMEIA-SEM-ATIVAR: o duplo clique abre o campo, sem ativar."""
    m = corrida.marcos
    assert "gestos_do_duplo" in m, "o roteiro nunca chegou ao duplo clique"
    campo = json.loads(m["lido"]["campo_aberto"])
    assert campo["aberto"] and campo["foco"], f"o campo não abriu com o foco: {campo}"
    assert "selecionar" not in m["gestos_do_duplo"], (
        f"o duplo clique ativou o perfil antes de renomear: {m['gestos_do_duplo']}")
    assert m["resultados_do_duplo"] == 0, "um `profile.switch` saiu do duplo clique"


def test_o_campo_fica_quando_o_daemon_ja_diz_o_perfil_novo(corrida: SimpleNamespace) -> None:
    """D-1911-O-DUPLO-CLIQUE-RENOMEIA-SEM-ATIVAR: o campo aberto sobrevive à reescrita da lista."""
    campo = json.loads(corrida.marcos["lido"]["campo_depois_do_tique"])
    assert campo["aberto"], "a reescrita do `<tbody>` levou o campo embora"
    assert campo["foco"], "o campo perdeu o foco"
    assert campo["valor"] == "Sackboy", f"o campo perdeu o texto: {campo['valor']!r}"


def test_enter_grava_o_nome_novo_na_lista_e_no_disco(corrida: SimpleNamespace) -> None:
    """D-1911-O-DUPLO-CLIQUE-RENOMEIA-SEM-ATIVAR: Enter grava o nome novo, na lista e no disco."""
    gestos = corrida.marcos["gestos_do_enter"]
    assert ("perfis.renomear", "Sackboy remasterizado") in gestos, gestos
    lista = json.loads(corrida.marcos["lido"]["lista_depois"])
    assert "Sackboy remasterizado" in lista["nomes"], f"a lista não trouxe o nome novo: {lista}"
    assert "Sackboy remasterizado" in corrida.no_disco and "Sackboy" not in corrida.no_disco


def test_o_clique_simples_no_nome_continua_ativando_passado_o_intervalo(
    corrida: SimpleNamespace,
) -> None:
    """D-1911-O-DUPLO-CLIQUE-RENOMEIA-SEM-ATIVAR: o clique simples ativa, passado o intervalo."""
    m = corrida.marcos
    assert "depois_do_intervalo" in m, "o roteiro nunca chegou ao clique simples"
    assert "selecionar" not in m["antes_do_intervalo"], (
        "o clique no nome ativou antes do intervalo do duplo clique do sistema")
    assert "selecionar" in m["depois_do_intervalo"], (
        f"o clique simples no nome deixou de ativar: {m['depois_do_intervalo']}")
