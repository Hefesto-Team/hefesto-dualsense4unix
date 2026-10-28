"""A aba Vibração do todo: os padrões (dado), o Modo automático e o padrão tocado num controle.

MORDIDAS: voltar o `?` (`class="ajuda`), pôr «Meus toques», tirar o `data-governa` do Modo
automático ou deixá-lo governar o Testar, tocar o padrão sem devolver a mão ao jogo, trocar a ordem
dos motores, deixar o padrão passar do teto e dar altura fixa à grade reprovam.
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
UNIQ = "aa:bb:cc:00:00:01"
CHROME = pathlib.Path("/usr/bin/google-chrome")


def _doc() -> str:
    """O desenho sem o estilo e sem o script: o que a pessoa vê e o que ela aciona."""
    bruto = MOCKUP.read_text(encoding="utf-8")
    return re.sub(r"<(style|script)>.*?</\1>", "", bruto, flags=re.S)


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
        padroes.sequencia("onda", "tres")  # (noqa-acento)


def test_tocar_percorre_os_passos_na_ordem_com_o_tempo_de_cada_um_e_reduz_pela_barra() -> None:
    enviados: list[tuple[int, int]] = []
    esperas: list[float] = []
    padroes.tocar("tranco", "ambos", lambda e, d: enviados.append((e, d)), esperas.append,
                  pontos_esquerdo=50, pontos_direito=100)
    passos = padroes.PADROES["tranco"]
    assert esperas == [ms / 1000 for ms, _, _ in passos]
    assert enviados == [(round(e / 2), d) for _, e, d in passos]


def test_a_tela_nao_tem_interrogacao_nem_meus_toques_nem_texto_de_dica_na_linha() -> None:
    doc = _doc()
    assert 'class="ajuda' not in doc, "o `?` voltou: a dica mora no `data-dica`"
    for fora in ("Meus toques", "Meus efeitos", "mesa", "Criar efeitos novos", "Sentir"):
        assert fora not in doc, f"o desenho trouxe «{fora}»"
    for dito in ("Modo automático", "Força da vibração", "Sensor háptico",
                 "Motor esquerdo", "Motor direito", "Testar agora", "Batida", "Onda", "Tranco"):
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
    assert "acoes" not in cl and "btn" not in cl, (  # (noqa-acento)
        "o Testar e o Parar não são escolha do jogo: o automático não os trava")


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


def test_o_padrao_toca_no_controle_dele_e_devolve_a_mao_ao_jogo(a05) -> None:
    ponte = _Ponte()
    a05._padrao_neste_controle(_ctx(), ponte, UNIQ, "batida", padroes.AMBOS)
    sets = [c for c in ponte.chamadas if c[0] == "rumble_set_checked"]
    assert len(sets) == len(padroes.PADROES["batida"])
    assert all(k.get("uniq") == UNIQ for _, _, k in sets), "o padrão toca no controle dele"
    assert sets[0][1][:2] == (255, 255)
    assert ponte.nomes[-2:] == ["rumble_stop", "rumble_passthrough"], (
        "sem devolver a mão ao jogo o controle fica mudo depois do efeito")
    assert a05.em_teste() == frozenset(), "o efeito não é o Testar: não deixa teste ligado"


def test_o_motor_esquerdo_e_o_pesado_e_vai_no_segundo_argumento(a05) -> None:
    """`rumble_set_checked(direito, esquerdo)`: o esquerdo é o `strong`."""
    ponte = _Ponte()
    a05._padrao_neste_controle(_ctx(), ponte, UNIQ, "tranco", padroes.ESQUERDO)
    for _, (fraco, *_), _k in [c for c in ponte.chamadas if c[0] == "rumble_set_checked"]:
        assert fraco == 0, "o direito tem de ficar calado"
    assert any(c[1][1] for c in ponte.chamadas if c[0] == "rumble_set_checked")


def test_o_efeito_que_a_ponte_recusa_para_e_devolve_a_mao_ao_jogo(a05) -> None:
    class Recusa(_Ponte):
        def rumble_set_checked(self, *a: Any, **k: Any) -> Any:
            self.chamadas.append(("rumble_set_checked", a, k))
            return (False, "O controle escolhido não está na mesa.")

    ponte = Recusa()
    with pytest.raises(RuntimeError, match="não está na mesa"):
        a05._padrao_neste_controle(_ctx(), ponte, UNIQ, "onda", padroes.AMBOS)
    assert len([c for c in ponte.chamadas if c[0] == "rumble_set_checked"]) == 1
    assert ponte.nomes[-2:] == ["rumble_stop", "rumble_passthrough"]


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
