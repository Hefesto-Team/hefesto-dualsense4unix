"""Os acessórios seguem os jogos escolhidos, com a força no deslizante: o DESENHO da janela.

Na aba interna «O que seguem» da janela dos acessórios (Lovense), a moldura «Os jogos que os
acessórios seguem» tem uma caixa por jogo, e a lista NASCE DESMARCADA («nenhum marcado: os
acessórios ficam parados»); a moldura «Força de cada canal» tem, para cada aparelho, um deslizante
de 0 a 20 por canal (vibração, gatilho e háptica), com o número ao lado.

O desenho (`mockup/07-lancadores.html`) e o produto. Nenhum «P1» a «P4» e nenhum nome de controle
cravado na janela. No produto: o `perfil.trocou` diz QUAL jogo é (`jogo`), o perfil, o `estilo` e o
jogador de cada controle, e nunca leva marca; o manifesto declara o `deslizante` (faixa, passo e
a posição inicial obrigatória dentro dela) e os `jogos`; a janela da extensão desenha o
`input[type=range]` e uma caixa por jogo que tem perfil, e o gesto guarda o valor.

MORDIDAS (executadas aqui): um deslizante a menos, um limite de 0 a 30, uma caixa já marcada de
fábrica ou um «P1» na janela reprovam a régua; o deslizante que não muda o número reprova no Chrome.
O `perfil.trocou` sem `jogo` reprova `test_abrir_um_jogo_publica_jogo_perfil_estilo_e_jogador`; o
manifesto que aceita o `deslizante` sem posição inicial reprova `test_o_deslizante_sem_padrao_...`.
"""

from __future__ import annotations

import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "07-lancadores.html"
CHROME = pathlib.Path("/usr/bin/google-chrome")
APARELHOS = ["Lovense Nora", "Lovense Domi", "Lovense Ferri"]
CANAIS = ["Vibração", "Gatilho", "Háptica"]


def _janela(texto: str | None = None) -> str:
    bruto = texto if texto is not None else MOCKUP.read_text(encoding="utf-8")
    sem = re.sub(r"<style\b[^>]*>.*?</style>", "", bruto, flags=re.S)
    inicio = sem.index('id="acessorios"')
    return sem[inicio:sem.find('<div class="tela-nova"', inicio + 1) if sem.find(
        '<div class="tela-nova"', inicio + 1) > 0 else None]


def _problemas(janela: str) -> list[str]:
    falta: list[str] = []
    forca = re.search(r'<div class="moldura t2-forca">(.*?)</div>\s*</div>', janela, flags=re.S)
    if not forca:
        return ["sem a moldura «Força de cada canal»"]
    cabecas = re.findall(r'<span class="fz-cab"[^>]*>([^<]+)</span>', forca.group(1))
    if cabecas != CANAIS:
        falta.append(f"canais {cabecas}")
    aparelhos = re.findall(r'<span class="fz-ap">([^<]+)</span>', forca.group(1))
    if aparelhos != APARELHOS:
        falta.append(f"aparelhos {aparelhos}")
    deslizantes = re.findall(
        r'<input type="range" min="(\d+)" max="(\d+)"[^>]*aria-label="([^"]+)"', forca.group(1))
    esperados = {f"{c} de {a}" for a in APARELHOS for c in CANAIS}
    if {r for _, _, r in deslizantes} != esperados or len(deslizantes) != 9:
        falta.append(f"{len(deslizantes)} deslizantes, e são nove: três por aparelho")
    if any((lo, hi) != ("0", "20") for lo, hi, _ in deslizantes):
        falta.append("um deslizante não vai de 0 a 20")
    lista = re.search(r'<div class="jg-lista">(.*?)</div>\s*</div>', janela, flags=re.S)
    caixas = re.findall(r'<input type="checkbox"([^>]*)>', lista.group(1)) if lista else []
    if not caixas:
        falta.append("sem a lista de jogos com caixa")
    if any("checked" in c for c in caixas):
        falta.append("uma caixa nasce marcada; a lista nasce desmarcada")
    if re.search(r"\bP[1-4]\b", janela):
        falta.append("um P1 a P4 na janela; a cor do plástico é do produto")
    return falta


def test_nove_deslizantes_de_zero_a_vinte_e_a_lista_nasce_desmarcada() -> None:
    assert _problemas(_janela()) == []


def test_ha_uma_caixa_por_jogo_com_perfil_e_o_nome_dele() -> None:
    lista = re.search(r'<div class="jg-lista">(.*?)</div>\s*</div>', _janela(), flags=re.S).group(1)
    caixas = re.findall(
        r'<input type="checkbox" data-jogo="([^"]+)"><span class="jg-n">([^<]+)</span>', lista)
    assert len(caixas) >= 7 and all(a == b for a, b in caixas), caixas


def test_a_regua_morde_o_limite_a_caixa_marcada_o_deslizante_a_menos_e_o_p1() -> None:
    doc = MOCKUP.read_text(encoding="utf-8")
    assert any("0 a 20" in p for p in _problemas(_janela(doc.replace(
        'max="20" step="1" value="10" aria-label="Vibração de Lovense Nora"',
        'max="30" step="1" value="10" aria-label="Vibração de Lovense Nora"', 1))))
    assert any("marcada" in p for p in _problemas(_janela(doc.replace(
        '<input type="checkbox" data-jogo="Elden Ring">',
        '<input type="checkbox" checked data-jogo="Elden Ring">', 1))))
    assert any("deslizantes" in p for p in _problemas(_janela(doc.replace(
        'aria-label="Háptica de Lovense Ferri"', 'aria-label="x"', 1))))
    assert any("P1" in p for p in _problemas(_janela(doc.replace(
        "Força de cada canal</span>", "Força de cada canal P1</span>", 1))))


@pytest.fixture(scope="module")
def pagina():
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        pg = nav.new_page(viewport={"width": 1212, "height": 809})
        yield pg
        nav.close()


def test_o_deslizante_muda_o_numero_ao_lado_e_a_lista_abre_desmarcada(pagina) -> None:
    pagina.goto(f"{MOCKUP.as_uri()}?aba=t2#acessorios")
    assert pagina.evaluate("[...document.querySelectorAll('.jg-l input')].every(c => !c.checked)")
    pagina.evaluate("""() => {
      const r = document.querySelector('[aria-label="Gatilho de Lovense Domi"]');
      r.value = 17; r.dispatchEvent(new Event('input', {bubbles: true})); }""")
    assert pagina.evaluate("""document.querySelector(
      '[aria-label="Gatilho de Lovense Domi"]').nextElementSibling.textContent""") == "17"
    pagina.click(".jg-l:nth-child(2) input")
    assert pagina.evaluate("document.querySelectorAll('.jg-l input:checked').length") == 1


# -- O produto: o evento, o manifesto e a janela da extensão --------------------------------------

import ast
import json
import sys
from types import SimpleNamespace
from typing import Any

from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems.autoswitch import AnunciadorDoJogo
from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError
from hefesto_dualsense4unix.mods.manifesto import ManifestoRecusadoError, Opcao, ler_manifesto
from hefesto_dualsense4unix.mods.opcoes import ler, padrao_de, validar
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import MatchAny, MatchCriteria, Profile

INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
MAC_1, MAC_2 = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"


def _daemon(appid: int | None, bus: EventBus, *, dois: bool = True) -> SimpleNamespace:
    """Um serviço de mentira com o P1 e, se pedido, o P2 do co-op, cada um com o seu número."""
    jogadores = {MAC_2: SimpleNamespace(reader=None, vpad=None, motion_reader=None)} if dois else {}
    numeros = {MAC_1: 1, MAC_2: 2}
    return SimpleNamespace(
        bus=bus, appid_em_cena=appid, controller=SimpleNamespace(primary_uniq=MAC_1),
        _coop_manager=SimpleNamespace(_players=jogadores),
        identity_registry=SimpleNamespace(
            numero_da_lampada=lambda uniq, assign=True: numeros[uniq]),
    )


def _tudo(fila: Any) -> list[dict[str, Any]]:
    saida = []
    while not fila.empty():
        saida.append(fila.get_nowait())
    return saida


def _store(nome: str | None) -> SimpleNamespace:
    return SimpleNamespace(active_profile=nome)


def test_abrir_um_jogo_publica_jogo_perfil_estilo_e_jogador() -> None:
    save_profile(Profile(name="Elden Ring", priority=5, estilo="terror", marcas=["adulto"],
                         match=MatchCriteria(window_class=["steam_app_1245620"])))
    bus = EventBus()
    fila = bus.subscribe(EventTopic.PERFIL_TROCOU)
    AnunciadorDoJogo(bus, _store("Elden Ring"), _daemon(1245620, bus)).ver()

    (evento,) = _tudo(fila)
    assert (evento["perfil"], evento["jogo"], evento["estilo"]) == (
        "Elden Ring", "steam_app_1245620", "terror")
    assert [(c["jogador"], c["perfil"], c["jogo"], c["estilo"]) for c in evento["controles"]] == [
        (1, "Elden Ring", "steam_app_1245620", "terror"),
        (2, "Elden Ring", "steam_app_1245620", "terror"),
    ]
    assert "marcas" not in evento and all("marcas" not in c for c in evento["controles"])


def test_fora_de_jogo_o_jogo_e_nulo_e_o_controle_que_entra_e_troca() -> None:
    save_profile(Profile(name="padrao", match=MatchAny(), priority=0))  # noqa-acento: chave do contrato
    bus = EventBus()
    fila = bus.subscribe(EventTopic.PERFIL_TROCOU)
    sem_jogo = _daemon(None, bus, dois=False)
    anunciador = AnunciadorDoJogo(bus, _store("padrao"), sem_jogo)  # noqa-acento: chave do contrato
    anunciador.ver()
    anunciador.ver()
    sem_jogo._coop_manager._players[MAC_2] = SimpleNamespace(
        reader=None, vpad=None, motion_reader=None)
    anunciador.ver()

    primeiro, segundo = _tudo(fila)
    assert primeiro["jogo"] is None and [c["jogador"] for c in primeiro["controles"]] == [1]
    assert [c["jogador"] for c in segundo["controles"]] == [1, 2], "o P2 que entrou não foi dito"


def test_dois_controles_em_jogos_diferentes_publicam_cada_um_o_seu() -> None:
    save_profile(Profile(name="padrao", match=MatchAny(), priority=0))  # noqa-acento: chave do contrato
    bus = EventBus()
    fila = bus.subscribe(EventTopic.PERFIL_TROCOU)
    appids = {MAC_1: 1245620, MAC_2: 730}
    AnunciadorDoJogo(bus, _store("padrao"), _daemon(1245620, bus), appids.get).ver()  # noqa-acento: chave do contrato

    (evento,) = _tudo(fila)
    assert {c["jogador"]: c["jogo"] for c in evento["controles"]} == {
        1: "steam_app_1245620", 2: "steam_app_730"}


def test_a_conexao_tardia_recebe_o_jogo_de_agora() -> None:
    save_profile(Profile(name="padrao", match=MatchAny(), priority=0))  # noqa-acento: chave do contrato
    bus = EventBus()
    AnunciadorDoJogo(bus, _store("padrao"), _daemon(730, bus)).ver()  # noqa-acento: chave do contrato
    tardia = bus.subscribe(EventTopic.PERFIL_TROCOU)
    (evento,) = _tudo(tardia)
    assert evento["jogo"] == "steam_app_730"


def test_o_jogo_que_fecha_diz_fechou_e_depois_o_perfil_sem_jogo() -> None:
    save_profile(Profile(name="padrao", match=MatchAny(), priority=0))  # noqa-acento: chave do contrato
    bus = EventBus()
    ordem: list[str] = []
    publicar = bus.publish
    bus.publish = lambda t, c: (ordem.append(t), publicar(t, c))[1]  # type: ignore[method-assign]
    servico = _daemon(730, bus)
    anunciador = AnunciadorDoJogo(bus, _store("padrao"), servico)  # noqa-acento: chave do contrato
    anunciador.ver()
    servico.appid_em_cena = None
    anunciador.ver()
    assert ordem == [EventTopic.PERFIL_TROCOU, EventTopic.JOGO_FECHOU, EventTopic.PERFIL_TROCOU]


def test_nenhum_evento_do_src_publica_marcas() -> None:
    """Em toda chamada `publish(...)` do `src/`, a palavra «marcas» não aparece."""
    achados = []
    for arquivo in sorted((RAIZ / "src").rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            chamada = isinstance(no, ast.Call) and getattr(no.func, "attr", "") == "publish"
            if chamada and any(
                isinstance(x, ast.Constant) and x.value == "marcas" for x in ast.walk(no)
            ):
                achados.append(f"{arquivo.relative_to(RAIZ)}:{no.lineno}")
    assert achados == [], f"um evento leva a marca do perfil: {achados}"


def test_o_pulso_da_barra_le_a_marca_do_arquivo_e_nao_do_evento() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.volta_dos_acessorios import volta_de_producao

    save_profile(Profile(name="noite", match=MatchAny(), priority=5, marcas=["adulto"]))
    bus = EventBus()
    AnunciadorDoJogo(bus, _store("noite"), _daemon(None, bus)).ver()
    volta = volta_de_producao(SimpleNamespace(bus=bus, controller=None))
    assert volta._l.marcas() == frozenset({"adulto"})


# O manifesto.

def _opcao(**campos: Any) -> dict[str, Any]:
    return {"id": "forca", "rotulo": "Força", "tipo": "deslizante", "minimo": 0, "maximo": 20,  # noqa-acento: chave do contrato
            "passo": 1, "padrao": 10, **campos}  # noqa-acento: chave do contrato


def test_o_manifesto_aceita_o_deslizante_com_faixa_passo_e_padrao() -> None:
    o = Opcao(**_opcao())
    assert (o.minimo, o.maximo, o.passo, o.padrao) == (0, 20, 1, 10)
    assert Opcao(**_opcao(padrao=0)).padrao == 0 and Opcao(**_opcao(padrao=20)).padrao == 20


def test_o_deslizante_sem_padrao_o_fora_da_faixa_e_a_faixa_torta_sao_recusados() -> None:
    sem_padrao = _opcao()
    del sem_padrao["padrao"]  # noqa-acento: chave do contrato
    for ruim in (sem_padrao, _opcao(padrao=21), _opcao(padrao=-1), _opcao(padrao=True),
                 _opcao(maximo=0), _opcao(passo=0), _opcao(minimo=None)):
        with pytest.raises(ValueError):
            Opcao(**ruim)


def test_faixa_so_vale_no_deslizante_e_jogos_so_aceita_chave_de_jogo() -> None:
    with pytest.raises(ValueError, match="não é deslizante"):
        Opcao(id="x", rotulo="X", tipo="numero", minimo=0)
    with pytest.raises(ValueError, match="não é de jogos"):
        Opcao(id="x", rotulo="X", tipo="escolha", escolhas=["a"], padrao=["steam_app_1"])
    assert Opcao(id="j", rotulo="Jogos", tipo="jogos").padrao is None
    assert Opcao(id="j", rotulo="Jogos", tipo="jogos", padrao=["steam_app_7"]).padrao == [
        "steam_app_7"]
    with pytest.raises(ValueError, match="chaves de jogo"):
        Opcao(id="j", rotulo="Jogos", tipo="jogos", padrao=["Elden Ring"])


def test_o_manifesto_inteiro_lido_do_arquivo_traz_o_deslizante(tmp_path) -> None:
    pasta = tmp_path / "ext"
    pasta.mkdir()
    (pasta / "hefesto-mod.json").write_text(json.dumps({
        "id": "ext", "nome": "Ext", "versao": "0.1", "api": ">=1,<2", "licenca": "MIT",  # noqa-acento: chave do contrato
        "tipos": ["tema"], "tema": {}, "opcoes": [_opcao(), {"id": "j", "rotulo": "Jogos",  # noqa-acento: chave do contrato
                                                             "tipo": "jogos"}],
    }), encoding="utf-8")
    manifesto = ler_manifesto(pasta)
    assert [o.tipo for o in manifesto.opcoes] == ["deslizante", "jogos"]
    (pasta / "hefesto-mod.json").write_text(json.dumps({
        "id": "ext", "nome": "Ext", "versao": "0.1", "api": ">=1,<2", "licenca": "MIT",  # noqa-acento: chave do contrato
        "tipos": ["tema"], "tema": {}, "opcoes": [{**_opcao(), "padrao": None}],  # noqa-acento: chave do contrato
    }), encoding="utf-8")
    with pytest.raises(ManifestoRecusadoError):
        ler_manifesto(pasta)


def test_o_valor_do_deslizante_cai_no_degrau_e_o_de_fora_da_faixa_e_recusado() -> None:
    o = Opcao(**_opcao(minimo=0, maximo=1, passo=0.25, padrao=0.5))
    assert validar(o, "0,6") == 0.5 and validar(o, 0.9) == 1.0 and padrao_de(o) == 0.5
    for fora in (1.5, -0.1, "abc"):
        with pytest.raises(InstalacaoRecusadaError):
            validar(o, fora)


def test_o_valor_de_jogos_e_uma_lista_de_chaves_sem_repetir() -> None:
    o = Opcao(id="j", rotulo="Jogos", tipo="jogos")
    assert padrao_de(o) == []
    assert validar(o, ["steam_app_1", "steam_app_2", "steam_app_1"]) == [
        "steam_app_1", "steam_app_2"]
    for ruim in ("steam_app_1", ["Elden Ring"], [1]):
        with pytest.raises(InstalacaoRecusadaError):
            validar(o, ruim)


# A janela da extensão.

@pytest.fixture
def lar(tmp_path, monkeypatch):
    from hefesto_dualsense4unix.mods.instalador import Lugares

    lg = Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # noqa-acento: campo
                 registro=tmp_path / "config" / "mods.json",
                 estado=tmp_path / "run" / "mods-estado.json")
    monkeypatch.setattr(Lugares, "do_xdg", classmethod(lambda cls: lg))
    a07 = _a07()
    monkeypatch.setattr(a07.VIGIA, "_disparar", lambda: None)
    a07.REGISTRO.esquecer()
    a07._MEXIDA.limpar()
    yield lg
    a07.REGISTRO.esquecer()
    a07._MEXIDA.limpar()


@pytest.fixture
def ctx():
    sys.path.insert(0, str(INTERFACE))
    import pacotes

    return pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})


def _a07():
    sys.path.insert(0, str(INTERFACE))
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


class _Ponte:
    def escolher_arquivo(self, titulo: str, padrao: str = "", sugestao: str = "") -> str | None:
        return None


def _instalada(a07, ctx, tmp_path) -> None:
    pasta = tmp_path / "fonte" / "acess"
    pasta.mkdir(parents=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps({
        "id": "acess", "nome": "Acess", "versao": "0.1", "api": ">=1,<2", "licenca": "MIT",  # noqa-acento: chave do contrato
        "tipos": ["tema"], "tema": {}, "opcoes": [  # noqa-acento: chave do contrato
            _opcao(id="vibracao", rotulo="Vibração", maximo=20, passo=1, padrao=10),
            {"id": "jogos", "rotulo": "Jogos que seguem", "tipo": "jogos"},
        ],
    }), encoding="utf-8")
    a07.instalar_modificacao(ctx, {"forma": {"mod-endereco": str(pasta)}}, _Ponte())


def test_a_janela_desenha_o_range_do_manifesto_e_uma_caixa_por_jogo_com_perfil(
        lar, ctx, tmp_path) -> None:
    save_profile(Profile(name="Elden Ring", priority=5,
                         match=MatchCriteria(window_class=["steam_app_1245620"])))
    save_profile(Profile(name="Counter-Strike 2", priority=5,
                         match=MatchCriteria(window_class=["steam_app_730"])))
    save_profile(Profile(name="padrao", match=MatchAny(), priority=0))  # noqa-acento: chave do contrato
    a07 = _a07()
    _instalada(a07, ctx, tmp_path)
    carga = a07.configurar_modificacao(ctx, {"v": "acess"}, _Ponte())
    janela = carga["blocos"]["#mod-janela"]

    assert re.search(r'<input type="range" min="0" max="20" step="1" value="10"', janela)
    caixas = re.findall(r'<input type="checkbox"( checked)? data-gesto="guardar-opcao-da-'
                        r'modificacao" data-v="acess:jogos:(steam_app_\d+)">', janela)  # noqa-acento: chave do contrato
    assert caixas == [("", "steam_app_730"), ("", "steam_app_1245620")], (
        "uma caixa por jogo que tem perfil, na ordem dos nomes, e nenhuma marcada de fábrica")


def test_guardar_o_deslizante_e_marcar_o_jogo_gravam_e_a_janela_repinta(lar, ctx, tmp_path) -> None:
    save_profile(Profile(name="Elden Ring", priority=5,
                         match=MatchCriteria(window_class=["steam_app_1245620"])))
    a07 = _a07()
    _instalada(a07, ctx, tmp_path)
    a07.configurar_modificacao(ctx, {"v": "acess"}, _Ponte())

    carga = a07.guardar_opcao_da_modificacao(
        ctx, {"v": "acess:vibracao", "valor": "17", "evento": "change"}, _Ponte())
    assert 'value="17"' in carga["blocos"]["#mod-janela"]
    carga = a07.guardar_opcao_da_modificacao(
        ctx, {"v": "acess:jogos:steam_app_1245620", "valor": "on", "evento": "change"}, _Ponte())
    assert "checked" in carga["blocos"]["#mod-janela"]
    guardado = json.loads((lar.dados / "acess" / "opcoes.json").read_text(encoding="utf-8"))
    assert guardado == {"vibracao": 17.0, "jogos": ["steam_app_1245620"]}

    # o clique do mesmo gesto não grava de novo; desmarcar tira da lista
    assert a07.guardar_opcao_da_modificacao(
        ctx, {"v": "acess:jogos:steam_app_1245620", "evento": "click"}, _Ponte()) is None
    a07.guardar_opcao_da_modificacao(
        ctx, {"v": "acess:jogos:steam_app_1245620", "valor": "on", "evento": "change"}, _Ponte())
    assert ler(_manifesto_de(lar), lar)["jogos"] == []


def test_o_gesto_recusa_o_valor_fora_da_faixa_e_o_jogo_sem_perfil(lar, ctx, tmp_path) -> None:
    a07 = _a07()
    _instalada(a07, ctx, tmp_path)
    with pytest.raises(RuntimeError, match="vai de 0 a 20"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": "acess:vibracao", "valor": "99", "evento": "change"}, _Ponte())
    with pytest.raises(RuntimeError, match="não tem perfil"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": "acess:jogos:steam_app_5", "valor": "on", "evento": "change"}, _Ponte())
    with pytest.raises(RuntimeError, match="Qual jogo"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": "acess:jogos", "valor": "on", "evento": "change"}, _Ponte())
    assert not (lar.dados / "acess" / "opcoes.json").exists(), "a recusa gravou"


def _manifesto_de(lar):
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    return manifesto_instalado("acess", lugares=lar)
