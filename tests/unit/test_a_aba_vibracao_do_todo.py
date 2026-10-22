"""A aba Vibração do todo: os padrões (dado), o Modo automático, os chips e o quadro de criar.

MORDIDAS: voltar o `?` (`class="ajuda`), pôr «Meus toques», tirar o `data-governa` do Modo
automático ou deixá-lo governar o Testar, devolver o Sentir sem a mão ao jogo, trocar a ordem dos
motores, deixar o padrão passar do teto, não guardar o efeito criado e dar altura fixa à grade
reprovam.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as padroes

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

MOCKUP = RAIZ / "mockup" / "05-vibracao.html"
PADRAO = "padrao"  # (noqa-acento) chave do contrato do clique
UNIQ = "aa:bb:cc:00:00:01"
CHROME = pathlib.Path("/usr/bin/google-chrome")


def _doc() -> str:
    """O desenho sem o estilo e sem o script: o que a pessoa vê e o que ela aciona."""
    bruto = MOCKUP.read_text(encoding="utf-8")
    return re.sub(r"<(style|script)>.*?</\1>", "", bruto, flags=re.S)


# ---------------------------------------------------------------- os padrões, como dado


def test_cada_padrao_tem_passos_de_ate_255_e_dura_menos_que_o_teto() -> None:
    assert set(padroes.PADROES) == {"batida", "onda", "tranco", "coice", "pancada_do_lado",
                                    "ressoar", "ricochete"}
    for nome, passos in padroes.PADROES.items():
        assert passos, nome
        for ms, esq, dir_ in passos:
            assert ms > 0 and 0 <= esq <= 255 and 0 <= dir_ <= 255, (nome, ms, esq, dir_)
        assert sum(ms for ms, _, _ in passos) <= padroes.TETO_MS, nome
        assert padroes.ROTULOS[nome], nome
        assert passos[-1][1:] == (0, 0), f"{nome} acaba com o motor ligado"


@pytest.mark.parametrize("motores,esq_zera,dir_zera", [
    ("esquerdo", False, True), ("direito", True, False), ("ambos", False, False)])
def test_o_motor_que_nao_toca_fica_em_zero(motores: str, esq_zera: bool, dir_zera: bool) -> None:
    passos = padroes.sequencia("batida", motores)
    assert len(passos) == len(padroes.PADROES["batida"])
    assert not esq_zera or all(esq == 0 for _, esq, _ in passos)
    assert not dir_zera or all(dir_ == 0 for _, _, dir_ in passos)
    assert any(esq for _, esq, _ in passos) or esq_zera
    assert any(dir_ for _, _, dir_ in passos) or dir_zera


def test_padrao_ou_motor_desconhecido_recusa_dizendo_os_que_existem() -> None:
    with pytest.raises(ValueError, match="batida, onda, tranco"):
        padroes.sequencia("inventado", "ambos")
    with pytest.raises(ValueError, match="esquerdo, direito, ambos"):
        padroes.sequencia("onda", "tres")  # (noqa-acento) motor que não existe


def test_tocar_percorre_os_passos_na_ordem_com_o_tempo_de_cada_um_e_reduz_pela_barra() -> None:
    enviados: list[tuple[int, int]] = []
    esperas: list[float] = []
    padroes.tocar("tranco", "ambos", lambda e, d: enviados.append((e, d)), esperas.append,
                  pontos_esquerdo=50, pontos_direito=100)
    passos = padroes.PADROES["tranco"]
    assert esperas == [ms / 1000 for ms, _, _ in passos]
    assert enviados == [(round(e / 2), d) for _, e, d in passos]


# ---------------------------------------------------------------- o desenho


def test_a_tela_nao_tem_interrogacao_nem_meus_toques_nem_texto_de_dica_na_linha() -> None:
    doc = _doc()
    assert 'class="ajuda' not in doc, "o `?` voltou: a dica mora no `data-dica`"
    for fora in ("Meus toques", "Meus efeitos", "mesa"):
        assert fora not in doc, f"o desenho trouxe «{fora}»"
    for dito in ("Criar efeitos novos", "Modo automático", "Força da vibração", "Sensor háptico",
                 "Motor esquerdo", "Motor direito", "Testar agora", "Batida", "Onda", "Tranco",
                 "Esquerdo", "Direito", "Sentir", "Criar"):
        assert dito in doc, f"o desenho perdeu «{dito}»"


def test_o_automatico_governa_a_forca_e_os_motores_e_nao_o_testar() -> None:
    bruto = MOCKUP.read_text(encoding="utf-8")
    chave = re.search(r'<[^>]*class="[^"]*modo-auto[^"]*"[^>]*>', bruto)
    assert chave, "o Modo automático sumiu"
    assert "data-governa" in chave.group(0)
    governa = re.search(r'data-governa="([^"]*)"', chave.group(0))
    assert governa
    assert ".forca" in governa.group(1) and ".motor" in governa.group(1)
    cl = governa.group(1)
    assert "acoes" not in cl and "btn" not in cl, (  # (noqa-acento) classe
        "o Testar e o Parar não são escolha do jogo: o automático não os trava")


def test_o_criar_e_o_sentir_apontam_para_o_quadro_que_eles_leem() -> None:
    doc = _doc()
    assert doc.count('id="criar-vibracao"') == 1
    for gesto in ("criar-efeito", "testar"):
        botoes = [b for b in re.findall(r"<button[^>]*>", doc)
                  if f'data-gesto="{gesto}"' in b and "data-hef-forma" in b]
        assert botoes, gesto
        assert all('data-hef-forma="criar-vibracao"' in b for b in botoes), (gesto, botoes)
    assert doc.count('data-linha="padrao"') == len(padroes.FORMAS_DE_CRIAR), "uma linha por forma"
    assert doc.count('data-linha="motores"') == 3, "são três escolhas de motor"


# ---------------------------------------------------------------- o pacote


class _Ponte:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    @property
    def nomes(self) -> list[str]:
        return [n for n, _a, _k in self.chamadas]

    def __getattr__(self, nome: str) -> Any:
        def registrar(*a: Any, **k: Any) -> Any:
            self.chamadas.append((nome, a, k))
            return (True, None) if nome.endswith("_checked") else True
        return registrar


@pytest.fixture
def a05(monkeypatch):
    import pacotes  # noqa: F401
    from pacotes import a05_vibracao

    monkeypatch.setattr(a05_vibracao, "_segurar", lambda _s: None)
    a05_vibracao.parar_o_teste()
    yield a05_vibracao
    a05_vibracao.parar_o_teste()


def _ctx() -> Any:
    import pacotes

    return pacotes.Contexto(
        state={"active_profile": "", "rumble_policy": "balanceado", "rumble_ff": {}},
        mesa=[{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua", "via": "USB",
               "cor": "starlight-blue"}],
        conectados=[{"uniq": UNIQ, "connected": True, "transport": "usb", "index": 0,
                     "player": 1}],
        estados={})


def test_o_chip_toca_o_padrao_dele_no_controle_dele_e_devolve_a_mao_ao_jogo(a05) -> None:
    import pacotes

    ponte = _Ponte()
    pacotes.gesto_da_pagina("05-vibracao.html", "testar")(
        _ctx(), {"uniq": UNIQ, PADRAO: "batida", "motores": "ambos"}, ponte)
    sets = [c for c in ponte.chamadas if c[0] == "rumble_set_checked"]
    assert len(sets) == len(padroes.PADROES["batida"])
    assert all(k.get("uniq") == UNIQ for _, _, k in sets), "o padrão toca no controle do chip"
    assert sets[0][1][:2] == (255, 255)
    assert ponte.nomes[-2:] == ["rumble_stop", "rumble_passthrough"], (
        "sem devolver a mão ao jogo o controle fica mudo depois do efeito")
    assert a05.em_teste() == frozenset(), "o efeito não é o Testar: não deixa teste ligado"


def test_o_motor_esquerdo_e_o_pesado_e_vai_no_segundo_argumento(a05) -> None:
    """`rumble_set_checked(direito, esquerdo)`: o esquerdo é o `strong`."""
    import pacotes

    ponte = _Ponte()
    pacotes.gesto_da_pagina("05-vibracao.html", "testar")(
        _ctx(), {"uniq": UNIQ, PADRAO: "tranco", "motores": "esquerdo"}, ponte)
    for _, (fraco, *_), _k in [c for c in ponte.chamadas if c[0] == "rumble_set_checked"]:
        assert fraco == 0, "o direito tem de ficar calado"
    assert any(c[1][1] for c in ponte.chamadas if c[0] == "rumble_set_checked")


def test_o_sentir_da_area_de_criar_le_a_forma_e_o_que_falta_recusa_dizendo(a05) -> None:
    import pacotes

    gesto = pacotes.gesto_da_pagina("05-vibracao.html", "testar")
    ponte = _Ponte()
    gesto(_ctx(), {"uniq": UNIQ, "forma": {PADRAO: "onda", "motores": "direito"}}, ponte)
    assert "rumble_set_checked" in ponte.nomes
    with pytest.raises(RuntimeError, match="Escolha a forma"):
        gesto(_ctx(), {"uniq": UNIQ, "forma": {PADRAO: "", "motores": "direito"}}, _Ponte())


def test_o_efeito_que_a_ponte_recusa_para_e_devolve_a_mao_ao_jogo(a05) -> None:
    import pacotes

    class Recusa(_Ponte):
        def rumble_set_checked(self, *a: Any, **k: Any) -> Any:
            self.chamadas.append(("rumble_set_checked", a, k))
            return (False, "O controle escolhido não está na mesa.")

    ponte = Recusa()
    with pytest.raises(RuntimeError, match="não está na mesa"):
        pacotes.gesto_da_pagina("05-vibracao.html", "testar")(
            _ctx(), {"uniq": UNIQ, PADRAO: "onda", "motores": "ambos"}, ponte)
    assert len([c for c in ponte.chamadas if c[0] == "rumble_set_checked"]) == 1
    assert ponte.nomes[-2:] == ["rumble_stop", "rumble_passthrough"]


def test_o_efeito_criado_entra_na_biblioteca_da_vibracao_e_vira_chip(a05) -> None:
    import pacotes

    criar = pacotes.gesto_da_pagina("05-vibracao.html", "criar-efeito")
    assert a05.meus_efeitos("vibracao") == {}
    criar(_ctx(), {"forma": {PADRAO: "onda", "motores": "esquerdo", "nome": "Maré"}}, _Ponte())
    guardado = a05.meus_efeitos("vibracao")
    assert guardado["Maré"]["base"] == "onda"
    assert guardado["Maré"]["parametros"] == {"motores": "esquerdo"}
    chip = a05.html_dos_toques(UNIQ)
    assert 'data-padrao="onda"' in chip and 'data-motores="esquerdo"' in chip
    assert f'data-uniq="{UNIQ}"' in chip and ">Maré<" in chip
    assert a05.meus_efeitos("gatilhos") == {} and a05.meus_efeitos("imersao") == {}, (
        "o efeito de vibração não entra nas bibliotecas dos gatilhos")


@pytest.mark.parametrize("forma,frase", [
    ({PADRAO: "onda", "motores": "ambos", "nome": ""}, "Dê um nome"),
    ({PADRAO: "", "motores": "ambos", "nome": "x"}, "Escolha a forma"),
    ({PADRAO: "onda", "motores": "", "nome": "x"}, "Escolha em qual motor"),
    ({PADRAO: "onda", "motores": "ambos", "nome": "n" * 200}, "no máximo"),
])
def test_criar_sem_o_que_falta_recusa_dizendo_e_nao_guarda(a05, forma, frase) -> None:
    import pacotes

    with pytest.raises(RuntimeError, match=frase):
        pacotes.gesto_da_pagina("05-vibracao.html", "criar-efeito")(
            _ctx(), {"forma": forma}, _Ponte())
    assert a05.meus_efeitos("vibracao") == {}


def test_o_pacote_manda_o_gesto_do_modo_e_o_bloco_dos_chips(a05) -> None:
    import pacotes

    pac = pacotes.pacote_da_pagina("05-vibracao.html", _ctx()) or {}
    assert a05.SELETOR_DOS_TOQUES in (pac.get("blocos") or {})


def test_o_chip_toca_no_controle_escolhido_na_fita_e_sem_escolha_no_primeiro(a05) -> None:
    """De um a quatro: o chip não fica preso ao primeiro controle quando outro está escolhido."""
    import pacotes

    outro = "aa:bb:cc:00:00:02"
    pacotes.gesto_da_pagina("05-vibracao.html", "criar-efeito")(
        _ctx(), {"forma": {PADRAO: "batida", "motores": "ambos", "nome": "Pulso"}}, _Ponte())
    ctx = _ctx()
    ctx.mesa.append({"pref": "p2", "jogador": 2, "uniq": outro, "nome": "Outro", "via": "BT",
                     "cor": "cosmic-red"})
    ctx.conectados.append({"uniq": outro, "connected": True, "transport": "bt", "index": 1,
                           "player": 2})
    for escolhido, uniq in (("p2", outro), ("", UNIQ)):
        ctx.escolhido = escolhido
        bloco = (pacotes.pacote_da_pagina("05-vibracao.html", ctx) or {})["blocos"][
            a05.SELETOR_DOS_TOQUES]
        assert f'data-uniq="{uniq}"' in bloco, (escolhido, bloco)


# ---------------------------------------------------------------- a medida, num Chrome headless


def test_a_aba_cabe_sem_rolar_sem_vao_e_o_nome_tem_a_largura_da_coluna() -> None:
    from playwright.sync_api import sync_playwright

    medir = """() => {
      const d = document.documentElement;
      const m = document.querySelector('.janela > .miolo') || d;
      const col = [...document.querySelectorAll('.vib > div')];
      const fundos = col.map(c => {
        const f = [...c.children].filter(e => getComputedStyle(e).position !== 'absolute');
        return Math.round(f[f.length - 1].getBoundingClientRect().bottom);
      });
      const nome = [...document.querySelectorAll('.vib .rot-ctrl')]
        .map(e => e.getBoundingClientRect().width);
      const des = [...document.querySelectorAll('.vib .moldura')]
        .map(e => e.getBoundingClientRect().width);
      return {rola: m.scrollHeight > m.clientHeight + 1, lateral: d.scrollWidth > d.clientWidth + 1,
              fundos, nome, des};
    }"""
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        pg = nav.new_page(viewport={"width": 1600, "height": 809})
        pg.goto(MOCKUP.as_uri())
        m = pg.evaluate(medir)
        nav.close()
    assert not m["rola"] and not m["lateral"], m
    assert len(set(m["fundos"])) == 1, f"as colunas acabam em alturas diferentes: {m['fundos']}"
    for nome, desenho in zip(m["nome"], m["des"], strict=True):
        if desenho:
            assert abs(nome - desenho) < 2, (nome, desenho)
