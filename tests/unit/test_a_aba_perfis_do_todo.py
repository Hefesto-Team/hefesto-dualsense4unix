"""A-ABA-PERFIS-DO-TODO-01 — a aba Perfis do todo: desenho, gestos novos e o clique que ativa.

Medido antes de curar (15/10/2026): o editor tinha Nome, Preferência (um slider), Funciona em,
Detectar e um rótulo de jogo; a lista não tinha data; o clique na linha só ABRIA o perfil, e o
cabeçalho dizia um perfil enquanto o editor mostrava outro; o Nativo, o Visual novel e o Adulto não
estavam na lista de estilos; a barra de baixo tinha botões de larguras diferentes; a coluna Nome
esticava as de data (104 px viravam 151). Os esperados são escritos à mão.

MORDIDAS (cada uma foi feita e viu reprovar):

* devolver o `.um-so` ao desenho -> `test_o_desenho_perde_o_que_a_tela_nova_nao_tem`;
* dar ao Adulto a família rosa da Luta -> `test_o_adulto_tem_uma_cor_que_nenhum_outro_estilo_tem`;
* trocar a grade da barra por `auto` -> `test_os_quatro_botoes_tem_a_mesma_largura`;
* devolver o `<col>` de 185 px do Nome -> `test_as_datas_medem_o_que_o_desenho_manda`;
* medir o rótulo da coluna uma vez só no `caber` ->
  `test_o_rotulo_cabe_com_todas_as_colunas_gravadas`;
* tirar o `_ativar_o` do `selecionar` ->
  `test_o_clique_deixa_o_cabecalho_e_o_editor_no_mesmo_perfil`;
* ler o `texto` no `editor_alvo` ou deixar o evento ao sair de «Eventos» -> os testes do alvo;
* arrastar sem regravar a `priority` do grupo -> `test_arrastar_regrava_a_ordem_do_mesmo_jogo`;
* tirar a guarda da `posNova` do `editor_ordem` ->
  `test_o_clique_solto_num_item_da_ordem_nao_e_arrasto` (a tela dizia «não entendi para onde»);
* devolver o seletor `[data-hef="editor.ordem"] ol` ->
  `test_todo_bloco_do_pacote_acha_um_lugar_na_pagina` (a lista do desenho ficava na tela);
* tirar o `:has` que revela a linha `.so-comando` ->
  `test_o_comando_tem_linha_propria_so_no_meu_comando` (19/10: o comando é só do «Meu comando»);
* esconder pelo `:has(ol:empty)` ou emitir `editor.ordem.ha` sempre cheio ->
  `test_qual_vale_primeiro_aparece_so_com_dois_perfis_do_jogo`;
* pintar o `editor.jogo` cru, ou gravar o nome como programa ->
  `test_o_nome_do_jogo_mostra_o_nome_e_grava_o_numero`.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest


from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import estilos_de_jogo, loader
from hefesto_dualsense4unix.profiles.schema import (
    PRIORIDADE_MAXIMA,
    MatchAny,
    MatchCriteria,
    Profile,
)

RAIZ = Path(__file__).resolve().parents[2]


def _desenho() -> str:
    """O mockup sem comentário, estilo e roteiro: o que o desenho de fato diz."""
    html = (RAIZ / "mockup" / "10-perfis.html").read_text(encoding="utf-8")
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    return re.sub(r"<(style|script)\b.*?</\1>", "", html, flags=re.S)


# --- o desenho ---------------------------------------------------------------------------------


def test_o_desenho_perde_o_que_a_tela_nova_nao_tem() -> None:
    """MORDIDA: devolver o `.um-so` (ou a ajuda, ou o botão de jogo de clicar) reprova aqui."""
    html = _desenho()
    assert "Criar perfil de point and click" not in html
    assert "um-so" not in html, "o botão «um só» saiu da tela nova"
    assert 'class="ajuda"' not in html and "<span class=\"ajuda" not in html
    assert 'class="conta"' not in html, "a contagem de perfis saiu"


def test_o_estilo_de_jogo_abre_em_traco_e_oferece_o_nativo_o_visual_novel_e_o_adulto() -> None:
    html = _desenho()
    bloco = html[html.index('data-hef="editor.estilo"'):]
    bloco = bloco[:bloco.index("</select>")]
    opcoes = re.findall(r"<option([^>]*)>([^<]*)</option>", bloco)
    rotulos = [texto.strip() for _atributos, texto in opcoes]
    assert rotulos[0] == "—" and "disabled" in opcoes[0][0] and "selected" in opcoes[0][0]
    assert rotulos[1] == "Nativo", "o Nativo abre a lista, logo depois do «—»"
    assert {"Visual novel", "Adulto", "Point and click", "Terror"} <= set(rotulos)
    do_produto = [e.rotulo for e in estilos_de_jogo.ESTILOS]
    assert rotulos[1:] == do_produto, "a lista do desenho é a do produto, na ordem"


def test_o_aplicar_em_tem_os_quatro_alvos_e_o_quando_so_aparece_nos_eventos() -> None:
    html = _desenho()
    for alvo in a10_perfis.ALVOS_DO_PERFIL:
        assert f'data-hef="editor.alvo.{alvo}"' in html and f'data-v="{alvo}"' in html
    quando = html[html.index('data-hef-gesto="editor.quando"') - 400:]
    assert "so-eventos" in quando[:600], "o «Quando» mora na linha que só aparece nos eventos"
    for momento in ("Cena", "Menu", "Pausa", "Controle conectado", "Programa aberto",
                    "Hora marcada", "Meu comando"):
        assert f">{momento}<" in html, f"falta o momento {momento!r}"


# --- a cor do Adulto ---------------------------------------------------------------------------


def test_o_adulto_tem_uma_cor_que_nenhum_outro_estilo_tem() -> None:
    """MORDIDA: dar ao Adulto a família rosa da Luta (255, 40, 180) reprova aqui."""
    adulto = estilos_de_jogo.POR_CHAVE["adulto"]
    assert adulto.familia == (250, 128, 114), "rosa-salmão: nem o rosa da Luta, nem o vermelho"
    for outro in estilos_de_jogo.ESTILOS:
        if outro.chave in estilos_de_jogo.SEM_COR or outro is adulto:
            continue
        longe = estilos_de_jogo._distancia(adulto.familia, outro.familia)
        assert longe > 90, f"o Adulto está a {longe} do {outro.rotulo}: a luz não separa os dois"
    assert len(set(estilos_de_jogo.as_quatro(adulto))) == 4


def test_o_adulto_traz_gatilho_desligado_e_vibracao_maxima() -> None:
    adulto = estilos_de_jogo.POR_CHAVE["adulto"]
    assert adulto.gatilho == "Off" and adulto.vibracao == "max"


# --- o clique que ativa ------------------------------------------------------------------------


class Ponte:
    """O daemon calado: quem manda o `profile.switch` muda o perfil que vale, como o de verdade."""

    def __init__(self, estado: dict[str, Any]) -> None:
        self.estado = estado
        self.trocas: list[str] = []

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        if metodo == "profile.switch":
            self.trocas.append(str(kw["name"]))
            self.estado["active_profile"] = str(kw["name"])
        return {}

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> bool:
        return True

    def profile_switch(self, nome: str) -> bool:
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _falso(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader, "profiles_dir", _falso)
    for atributo, valor in (("_ESCOLHIDO", ""), ("_ARMADO", None), ("_PROCURA", ""),
                            ("_PINTADO_PARA", ""), ("_ULTIMO_TIQUE", 0.0)):
        monkeypatch.setattr(a10_perfis, atributo, valor, raising=False)
    return alvo


def _ctx(ativo: str = "Elden Ring") -> Contexto:
    return Contexto(state={"active_profile": ativo}, mesa=[], conectados=[], estados={})


def _guardar(nome: str, prioridade: int = 10, classe: str | None = None) -> None:
    regra = MatchCriteria(window_class=[classe]) if classe else MatchAny()
    loader.save_profile(Profile(name=nome, match=regra, priority=prioridade), origem="régua")


def _linhas(ctx: Contexto) -> list[str]:
    html = a10_perfis.pacote(ctx)["blocos"][a10_perfis.SELETOR_DA_LISTA]
    return [x for x in html.splitlines() if "<tr" in x]


def test_o_clique_deixa_o_cabecalho_e_o_editor_no_mesmo_perfil(lar: Path) -> None:
    """MORDIDA: sem o `_ativar_o` no `selecionar`, o cabeçalho segue no perfil velho."""
    _guardar("Elden Ring", 40, "steam_app_1245620")
    _guardar("Pragmata", 30, "steam_app_3357650")
    ctx = _ctx("Elden Ring")
    ponte = Ponte(ctx.state)

    a10_perfis.selecionar(ctx, {"hefPerfil": "Pragmata"}, ponte)

    assert ctx.state["active_profile"] == "Pragmata" and ponte.trocas == ["Pragmata"]
    linhas = _linhas(ctx)
    abertas = [x for x in linhas if 'aria-selected="true"' in x]
    valendo = [x for x in linhas if 'class="ativo"' in x]
    assert len(abertas) == 1 and len(valendo) == 1
    assert abertas == valendo, "a linha aberta no editor é a linha do perfil que vale"
    assert 'data-hef-perfil="Pragmata"' in abertas[0]


# --- «Aplicar em» e «Quando» -------------------------------------------------------------------


def _aberto(nome: str) -> None:
    a10_perfis._ESCOLHIDO = nome


def test_o_aplicar_em_grava_o_alvo_e_o_pacote_acende_o_botao(lar: Path) -> None:
    """MORDIDA: ler o `texto` do botão no lugar de `v` não grava nada."""
    _guardar("Menu do PC")
    _aberto("Menu do PC")
    ctx = _ctx("Menu do PC")
    fora = a10_perfis.pacote(ctx)
    assert fora["editor.alvo.navegacao"] == "sim", "sem escolha, o perfil sem jogo é de Navegação"

    a10_perfis.editor_alvo(ctx, {"v": "programas", "texto": "Jogos"}, Ponte(ctx.state))

    assert loader.load_profile("Menu do PC").alvo == "programas"
    fora = a10_perfis.pacote(ctx)
    assert fora["editor.alvo.programas"] == "sim" and fora["editor.alvo.navegacao"] == ""


def test_um_alvo_que_nao_existe_recusa_sem_gravar(lar: Path) -> None:
    _guardar("Menu do PC")
    _aberto("Menu do PC")
    with pytest.raises(RuntimeError, match="não é um lugar onde o perfil vale"):
        a10_perfis.editor_alvo(_ctx("Menu do PC"), {"v": "lua"}, Ponte({}))
    assert loader.load_profile("Menu do PC").alvo is None


def test_sair_de_eventos_leva_o_momento_e_o_comando(lar: Path) -> None:
    # D-1510-O-APLICAR-EM-E-O-QUANDO-SO-GRAVAM
    """MORDIDA: deixar o `evento` ao sair de «Eventos» guarda um momento que ninguém vê."""
    _guardar("Ao pausar")
    _aberto("Ao pausar")
    ctx, ponte = _ctx("Ao pausar"), Ponte({})
    a10_perfis.editor_alvo(ctx, {"v": "eventos"}, ponte)
    a10_perfis.editor_quando(ctx, {"valor": "pausa", "evento": "change"}, ponte)
    a10_perfis.editor_quando(
        ctx, {"valor": "~/pausa.sh", "que": "comando", "evento": "change"}, ponte)
    perfil = loader.load_profile("Ao pausar")
    assert (perfil.alvo, perfil.evento, perfil.evento_comando) == ("eventos", "pausa", "~/pausa.sh")

    fora = a10_perfis.pacote(ctx)
    assert fora["editor.alvo.eventos"] == "sim"

    a10_perfis.editor_alvo(ctx, {"v": "jogos"}, ponte)
    perfil = loader.load_profile("Ao pausar")
    assert (perfil.alvo, perfil.evento, perfil.evento_comando) == ("jogos", None, None)


def test_o_quando_so_aceita_os_momentos_da_lista_e_o_clique_solto_nao_grava(lar: Path) -> None:
    _guardar("Ao pausar")
    _aberto("Ao pausar")
    ctx, ponte = _ctx("Ao pausar"), Ponte({})
    with pytest.raises(RuntimeError, match="não é um momento que o perfil conhece"):
        a10_perfis.editor_quando(ctx, {"valor": "sempre", "evento": "change"}, ponte)
    assert a10_perfis.editor_quando(ctx, {"valor": "menu", "evento": "click"}, ponte) is None
    assert loader.load_profile("Ao pausar").evento is None


def test_o_relato_do_alvo_e_do_momento_diz_o_rotulo_e_nao_o_valor_gravado(lar: Path) -> None:
    """O diário lê «Navegação» e «Controle conectado», nunca `navegacao` nem `controle_conectado`.

    MORDIDA: devolver `{novo}` ou `{momento}` cru à frase reprova aqui.
    """
    _guardar("Ao conectar")
    _aberto("Ao conectar")
    ctx, ponte = _ctx("Ao conectar"), Ponte({})
    relato = a10_perfis.editor_alvo(ctx, {"v": "navegacao"}, ponte)["relato"]
    assert relato.endswith("· aplica em Navegação")
    a10_perfis.editor_alvo(ctx, {"v": "eventos"}, ponte)
    relato = a10_perfis.editor_quando(
        ctx, {"valor": "controle_conectado", "evento": "change"}, ponte)["relato"]
    assert relato.endswith("· quando: Controle conectado")
    assert set(a10_perfis.ROTULO_DO_ALVO) == set(a10_perfis.ALVOS_DO_PERFIL)
    assert set(a10_perfis.ROTULO_DO_MOMENTO) == set(a10_perfis.EVENTOS_DO_PERFIL)


def test_todo_momento_do_desenho_existe_no_produto() -> None:
    """Os valores do `<select>` do «Quando» são os que o gesto aceita, nem um a mais."""
    html = _desenho()
    bloco = html[html.index('data-hef="editor.evento"'):]
    bloco = bloco[:bloco.index("</select>")]
    valores = re.findall(r'<option value="([^"]*)"', bloco)
    assert [v for v in valores if v not in ("", "—")] == list(a10_perfis.EVENTOS_DO_PERFIL)


def test_o_nome_do_jogo_mostra_o_nome_e_grava_o_numero(
        lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O rótulo do lado saiu: o campo diz «Pragmata», e escrever o nome grava o jogo da Steam.

    Medido na bancada (15/10/2026): o campo «Nome do jogo» mostrava `3357650` e mais nada.
    """
    from hefesto_dualsense4unix.profiles.simple_match import simple_extra

    monkeypatch.setattr(a10_perfis, "_nomes_dos_jogos", lambda: {"3357650": "Pragmata"})
    monkeypatch.setattr(a10_perfis, "_ofertas_de_jogos", lambda *a, **k: [])
    _guardar("Pragmata", 30, "steam_app_3357650")
    _guardar("Meu jogo", 20)
    _aberto("Pragmata")
    ctx = _ctx("Pragmata")
    assert a10_perfis.pacote(ctx)["editor.jogo"] == "Pragmata"

    _aberto("Meu jogo")
    resposta = a10_perfis.editor_jogo(
        _ctx("Meu jogo"), {"valor": "pragmata", "evento": "change"}, Ponte({}))
    assert simple_extra(loader.load_profile("Meu jogo").match) == "3357650"
    assert resposta["mesa"]["editor.jogo"] == "Pragmata"
    assert a10_perfis.pacote(_ctx("Meu jogo"))["editor.jogo"] == "Pragmata"


# --- «Qual vale primeiro» -------------------------------------------------------------------------


def test_qual_vale_primeiro_aparece_so_com_dois_perfis_do_jogo(lar: Path) -> None:
    """A classe `on` vem do pacote; o `:has(ol:empty)` não se recalcula no WebKitGTK.

    Medido na bancada (15/10/2026): com «Pragmata» e «Pragmata online», os dois `<li>` chegavam ao
    `<ol>` e o bloco seguia `display:none`, pois o `:has` ficou com a leitura do `<ol>` vazio.
    """
    _guardar("Pragmata", 30, "steam_app_3357650")
    _guardar("Navegar", 0)
    _aberto("Pragmata")
    ctx = _ctx("Pragmata")
    assert a10_perfis.pacote(ctx)["editor.ordem.ha"] == ""
    _guardar("Pragmata online", 20, "steam_app_3357650")
    fora = a10_perfis.pacote(ctx)
    assert fora["editor.ordem.ha"] == "sim"
    assert fora["blocos"][a10_perfis.SELETOR_DA_ORDEM].count("<li") == 2
    assert ":has(ol:empty)" not in _desenho()


def test_os_valores_da_nova_ordem_nunca_empatam_e_respeitam_o_teto() -> None:
    f = a10_perfis._valores_da_nova_ordem
    assert f([30, 20, 10], PRIORIDADE_MAXIMA) == [30, 20, 10], "reaproveita o que o grupo já tem"
    assert f([10, 10, 10], PRIORIDADE_MAXIMA) == [12, 11, 10], "o empate abre degraus"
    teto = PRIORIDADE_MAXIMA
    assert f([teto, teto, teto], teto) == [teto, teto - 1, teto - 2]
    assert f([0, 0], teto) == [1, 0]
    assert f([5], teto) == [5]


def test_arrastar_regrava_a_ordem_do_mesmo_jogo(lar: Path) -> None:
    # D-1510-A-ORDEM-DOS-PERFIS-SE-ARRASTA
    """MORDIDA: sem regravar a `priority` o arrasto só mexe na tela e o manager não muda."""
    for nome, prioridade in (("Souls A", 30), ("Souls B", 20), ("Souls C", 10)):
        _guardar(nome, prioridade, "steam_app_1245620")
    _guardar("Outro jogo", 99, "steam_app_3357650")
    _aberto("Souls A")
    ctx, ponte = _ctx("Souls A"), Ponte({})

    resposta = a10_perfis.editor_ordem(ctx, {"hefPerfil": "Souls C", "posNova": "1"}, ponte)

    assert resposta is not None and "Souls C vale primeiro" in str(resposta)
    prioridades = {p.name: p.priority for p in loader.load_all_profiles()}
    assert prioridades["Souls C"] == 30 and prioridades["Souls A"] == 20
    assert prioridades["Souls B"] == 10, "os valores do grupo são reaproveitados, não inventados"
    assert prioridades["Outro jogo"] == 99, "o perfil de OUTRO jogo não é tocado"
    html = a10_perfis.pacote(ctx)["blocos"][a10_perfis.SELETOR_DA_ORDEM]
    assert [m for m in re.findall(r'data-hef-perfil="([^"]+)"', html)] == [
        "Souls C", "Souls A", "Souls B"]


def test_arrastar_para_onde_ja_esta_nao_grava_nada(lar: Path) -> None:
    for nome, prioridade in (("Souls A", 30), ("Souls B", 20)):
        _guardar(nome, prioridade, "steam_app_1245620")
    _aberto("Souls A")
    antes = {p.name: p.model_dump_json() for p in loader.load_all_profiles()}
    resposta = a10_perfis.editor_ordem(
        _ctx("Souls A"), {"hefPerfil": "Souls A", "posNova": "1"}, Ponte({}))
    assert resposta is None
    assert {p.name: p.model_dump_json() for p in loader.load_all_profiles()} == antes


@pytest.mark.parametrize("pedido", [
    {"hefPerfil": "Souls B"},
    {"hefPerfil": "Souls B", "posNova": ""},
])
def test_o_clique_solto_num_item_da_ordem_nao_e_arrasto(lar: Path, pedido: dict[str, str]) -> None:
    """MORDIDA: sem a guarda da `posNova`, o clique solto num item dizia na tela «não entendi para
    onde o perfil foi arrastado» (medido no piloto em lar de mentira, 15/10/2026)."""
    for nome, prioridade in (("Souls A", 30), ("Souls B", 20)):
        _guardar(nome, prioridade, "steam_app_1245620")
    _aberto("Souls A")
    antes = {p.name: p.model_dump_json() for p in loader.load_all_profiles()}
    assert a10_perfis.editor_ordem(_ctx("Souls A"), pedido, Ponte({})) is None
    assert {p.name: p.model_dump_json() for p in loader.load_all_profiles()} == antes


@pytest.mark.parametrize("pedido", [
    {"hefPerfil": "Souls A", "posNova": "x"},
    {"hefPerfil": "Souls A", "posNova": "9"},
    {"hefPerfil": "Outro jogo", "posNova": "1"},
])
def test_arrastar_para_lugar_nenhum_recusa_sem_gravar(lar: Path, pedido: dict[str, str]) -> None:
    for nome, prioridade in (("Souls A", 30), ("Souls B", 20)):
        _guardar(nome, prioridade, "steam_app_1245620")
    _guardar("Outro jogo", 99, "steam_app_3357650")
    _aberto("Souls A")
    with pytest.raises(RuntimeError, match="Nada foi salvo"):
        a10_perfis.editor_ordem(_ctx("Souls A"), pedido, Ponte({}))
    assert {p.name: p.priority for p in loader.load_all_profiles()} == {
        "Souls A": 30, "Souls B": 20, "Outro jogo": 99}


# --- a tela no WebKit --------------------------------------------------------------------------


MEDIR = r"""
(function(){
  var larg = function(el){ return Math.round(el.getBoundingClientRect().width * 10) / 10; };
  var miolo = document.querySelector('.miolo');
  var raiz = document.documentElement;
  return JSON.stringify({
    botoes: [...document.querySelectorAll('.barra-quatro .btn')].map(
      function(b){ return [b.textContent.trim(), larg(b)]; }),
    miolo: [miolo.scrollHeight, miolo.clientHeight],
    folha: [raiz.scrollHeight, raiz.clientHeight, raiz.scrollWidth, raiz.clientWidth],
    colunas: [...document.querySelectorAll('table[data-tabela="10-perfis.lista"] th')].map(
      function(th){ return [th.dataset.coluna, larg(th)]; })
  });
})()
"""


@pytest.fixture(scope="module")
def tela() -> Any:
    """A página do gerador num WebView oculto de 1212 x 809, com a folha do produto."""
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a` (pulo não é verde)")
    sys.path.insert(0, str(RAIZ / "scripts"))
    import regua_de_tela

    from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA

    t = regua_de_tela.Tela(onde.BANCADA / "10-perfis.html", titulo_esperado="Hefesto",
                           largura=1212, altura=809)
    t.executar(
        "(function(){var s=document.createElement('style');"
        f"s.textContent={json.dumps(FOLHA_DA_CASA)};"
        "document.head.appendChild(s);return 'ok';})()")
    t.avancar(0.5)
    yield t
    t.fechar()


def test_os_quatro_botoes_tem_a_mesma_largura(tela: Any) -> None:
    """MORDIDA: trocar a grade da barra por `auto` deixa cada botão com a largura do texto."""
    medida = json.loads(tela.executar(MEDIR))
    nomes = [n for n, _w in medida["botoes"]]
    assert nomes == ["Duplicar", "Novo", "Remover", "Ativar"]
    larguras = {w for _n, w in medida["botoes"]}
    assert len(larguras) == 1 and min(larguras) > 150, medida["botoes"]


def test_a_aba_cabe_sem_rolagem_a_1212_por_809(tela: Any) -> None:
    medida = json.loads(tela.executar(MEDIR))
    assert medida["miolo"][0] <= medida["miolo"][1], f"o miolo rola: {medida['miolo']}"
    folha = medida["folha"]
    assert folha[0] <= folha[1] and folha[2] <= folha[3], f"a página rola: {folha}"


def test_as_datas_medem_o_que_o_desenho_manda(tela: Any) -> None:
    """MORDIDA: o `<col>` de 185 px do Nome estica as datas de 104 para 151 (medido)."""
    larguras = dict(json.loads(tela.executar(MEDIR))["colunas"])
    assert larguras["criado"] == 104 and larguras["modificado"] == 104, larguras
    assert larguras["nome"] > 300, f"o Nome é a coluna elástica: {larguras}"


MEDIR_O_ROTULO = r"""
(function(){
  var th = document.querySelector('th[data-coluna="criado"]');
  return JSON.stringify([th.scrollWidth, th.clientWidth]);
})()
"""


def test_o_rotulo_cabe_com_todas_as_colunas_gravadas(tela: Any) -> None:
    """Soma de colunas menor que a tela estica TODAS em proporção; o rótulo ainda cabe.

    MORDIDA: medir o `<th>` uma vez só (`i < 1` no `caber`) deixa «Criado em» 1 px curto.
    """
    tela.executar(
        "(function(){document.querySelector('table[data-tabela]')"
        ".setAttribute('data-larguras','nome:380·criado:48');return 'ok';})()")
    tela.avancar(0.4)
    scroll, client = json.loads(tela.executar(MEDIR_O_ROTULO))
    tela.executar(
        "(function(){document.querySelector('table[data-tabela]')"
        ".setAttribute('data-larguras','');return 'ok';})()")
    assert scroll <= client, f"o rótulo pede {scroll} px numa coluna de {client}"


def test_todo_bloco_do_pacote_acha_um_lugar_na_pagina(tela: Any) -> None:
    """Cada seletor de `blocos` casa UM elemento da página: sem casar, a pintura cai no vazio.

    Medido na bancada (15/10/2026): o «Qual vale primeiro» de um perfil sozinho no jogo seguia
    mostrando «Mortal Kombat» e «Mortal Kombat online», os dois do desenho.
    """
    seletores = (a10_perfis.SELETOR_DA_LISTA, a10_perfis.SELETOR_DOS_JOGOS,
                 a10_perfis.SELETOR_DA_ORDEM)
    contas = json.loads(tela.executar(
        "(function(){return JSON.stringify(" + json.dumps(list(seletores))
        + ".map(function(s){return document.querySelectorAll(s).length;}));})()"))
    assert contas == [1, 1, 1], dict(zip(seletores, contas, strict=True))


def test_o_comando_tem_linha_propria_so_no_meu_comando(tela: Any) -> None:
    """Com «Eventos», o comando só aparece no momento «Meu comando», numa linha própria e larga.

    Medido na bancada (15/10/2026): o comando dividia a linha com o momento e ficava com 22 px.
    Desde 19/10 ele mora em `.so-comando`, revelada pelo `:has` do `<option>` escolhido (o motor
    do produto, o WebKitGTK, entende o seletor): some em «Cena» e tem a linha toda em «Meu comando».
    """
    medida = json.loads(tela.executar(r"""
(function(){
  var c = document.querySelector('.campo.so-eventos'); c.classList.add('on');
  var s = c.querySelector('select'), i = document.querySelector('.ev-cmd'), v = s.value;
  s.value = 'cena'; var cena = i.getBoundingClientRect().width;
  s.value = 'meu_comando'; var meu = i.getBoundingClientRect().width;
  var sel = s.getBoundingClientRect().width;
  s.value = v; c.classList.remove('on');
  return JSON.stringify([sel, cena, meu]);
})()"""))
    largura_do_momento, sem_comando, largura_do_comando = medida
    assert sem_comando == 0, f"o comando aparece fora do «Meu comando»: {medida}"
    assert largura_do_momento > 250, f"o momento devia ter a linha toda: {medida}"
    assert largura_do_comando > 250, f"o campo do comando ficou com {largura_do_comando} px"
