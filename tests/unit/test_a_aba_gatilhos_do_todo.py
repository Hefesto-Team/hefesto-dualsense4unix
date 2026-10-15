"""A aba Gatilhos do todo: os efeitos de imersão (dado) e a tela que os oferece.

MORDIDAS: pôr a pane com força 9, repetir os números de duas imersões, sobrar uma família sem as
três imersões, dar largura própria ao chip, trazer de volta o Guardar, perder o campo da imersão
numa célula, deixar o efeito criado fora das listas, a dica prometer o tempo onde o motor não o
toca em todo modo (ou calar o tempo onde toca) ou o «Sentir» devolver o que o perfil dizia ANTES
do toque reprova.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS, get_spec
from hefesto_dualsense4unix.daemon.subsystems.tato_vivo import TETO_POR_CONTROLE
from hefesto_dualsense4unix.profiles import efeitos_de_imersao as imersao
from hefesto_dualsense4unix.profiles.estilos_de_jogo import POR_CHAVE

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "03-gatilhos.html"
UNIQ = "aa:bb:cc:00:00:01"
CHROME = pathlib.Path("/usr/bin/google-chrome")

FAIXAS = {s.name: {p.name: (p.min_value, p.max_value) for p in s.params} for s in PRESETS}
PADROES = {s.name: {p.name: p.default for p in s.params} for s in PRESETS}


def _dentro_da_faixa(modo: str, ajustes: dict[str, int]) -> list[str]:
    erros = []
    for nome, valor in ajustes.items():
        if nome not in FAIXAS.get(modo, {}):
            erros.append(f"{modo}.{nome} não existe no PRESETS")
            continue
        lo, hi = FAIXAS[modo][nome]
        if not lo <= valor <= hi:
            erros.append(f"{modo}.{nome}={valor} fora de {lo}..{hi}")
    return erros


def test_cada_familia_tem_tres_imersoes_e_cada_modo_dela_as_tres() -> None:
    for familia, modos in imersao.FAMILIAS.items():
        delas = [i for i in imersao.IMERSOES if i.familia == familia]
        assert len(delas) == 3, (familia, [i.chave for i in delas])
        for modo in modos:
            assert get_spec(modo) is not None, f"{modo} não é modo do PRESETS"
            assert len(imersao.imersoes_do_acionamento(modo)) == 3, (familia, modo)


def test_todo_numero_esta_dentro_da_faixa_do_presets() -> None:
    erros: list[str] = []
    for i, modo, estilo, ajustes in imersao.todos_os_ajustes():
        erros += [f"{i.chave}/{estilo or 'base'}: {e}" for e in _dentro_da_faixa(modo, ajustes)]
        assert estilo == "" or estilo in POR_CHAVE, f"{i.chave}: estilo {estilo!r} não existe"
    for i in imersao.IMERSOES:
        for m in i.momentos:
            erros += [f"{i.chave} momento: {e}" for e in _dentro_da_faixa(m.modo, dict(m.ajustes))]
            assert not m.valem_em or set(m.valem_em) <= set(imersao.FAMILIAS[i.familia])
        for estilo in (*i.na_frente, *i.variantes):
            assert estilo in POR_CHAVE, f"{i.chave}: estilo {estilo!r} não existe"
    assert not erros, erros


def test_nenhum_momento_passa_do_teto_de_escritas_do_motor() -> None:
    for i in imersao.IMERSOES:
        for m in i.momentos:
            if m.a_cada_ms:
                assert 1000 / m.a_cada_ms <= TETO_POR_CONTROLE, (i.chave, m.a_cada_ms)
            assert m.apos_ms >= 0 and (m.dura_ms is None or m.dura_ms > 0), i.chave


#: o que só um `momento` faz (mudar com o tempo de aperto), e o `tato_vivo` os toca
_PROMESSA_DE_TEMPO = re.compile(
    r"depois de|de vez em quando|conforme|alterna|acelera|minuto|segundo|instante|\bHz\b"
    r"|\d+(?:,\d+)? ?s\b", re.I)


def test_a_dica_diz_o_tempo_so_onde_o_motor_o_toca_em_todo_modo() -> None:
    """A dica vai à tela: o tempo só se promete onde os momentos valem em todo modo dela."""
    erradas = {i.chave: i.dica for i in imersao.IMERSOES
               if bool(_PROMESSA_DE_TEMPO.search(i.dica)) != imersao.o_tempo_vale_em_todo_modo(i)}
    assert not erradas, erradas


def test_os_numeros_de_cada_imersao_so_se_repetem_nela_mesma() -> None:
    """A tela reconhece a imersão pelos números: dois iguais seriam a mesma opção."""
    vistos: dict[tuple[str, tuple[tuple[str, int], ...]], str] = {}
    for i, modo, estilo, ajustes in imersao.todos_os_ajustes():
        cheio = {**PADROES[modo], **ajustes}
        assert cheio != PADROES[modo], f"{i.chave}/{modo} é igual ao padrão do modo"
        chave = (modo, tuple(sorted(cheio.items())))
        dono = vistos.setdefault(chave, i.chave)
        assert dono == i.chave, f"{i.chave}/{modo}/{estilo or 'base'} repete {dono}"


def test_a_ordem_com_estilo_poe_as_dele_na_frente() -> None:
    sem = [i.chave for i in imersao.imersoes_do_acionamento("SemiAutoGun")]
    com = [i.chave for i in imersao.imersoes_do_acionamento("SemiAutoGun", "terror")]
    assert sem == ["ferrolho-que-volta", "trava-seca", "pino-que-falha"]
    assert com[0] == "pino-que-falha" and sorted(com) == sorted(sem)
    assert imersao.imersoes_do_acionamento("Off") == ()


# ---------------------------------------------------------------- a tela

def _desenho() -> str:
    """O desenho (`mockup/`), que é o que o gerador escreve e ela aprova."""
    return (RAIZ / "mockup" / PAGINA).read_text(encoding="utf-8")


def _o_que_se_le() -> str:
    """O desenho sem o estilo e sem o script: só o que a pessoa vê e o que ela aciona."""
    return re.sub(r"<(style|script)>.*?</\1>", "", _desenho(), flags=re.S)


@pytest.fixture
def a03():
    """O pacote da aba Gatilhos do todo, com o rascunho limpo."""
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    a03_gatilhos.esquecer_o_rascunho()
    yield a03_gatilhos
    a03_gatilhos.esquecer_o_rascunho()


def test_o_desenho_traz_as_palavras_da_decisao_e_nenhuma_das_que_sairam() -> None:
    doc = _o_que_se_le()
    for dito in ("Efeito de acionamento", "Efeito de imersão", "Criar efeitos novos", "Sentir",
                 "Estilo de jogo", "Controle"):
        assert dito in doc, f"o desenho perdeu «{dito}»"
    for fora in ("Guardar", "Em todos", "Efeito pronto", "Reenviar",
                 'class="ajuda', 'class="ajustes'):
        assert fora not in doc, f"o desenho trouxe de volta «{fora}»"
    assert 'data-gesto="guardar' not in doc and 'data-gesto="em-todos' not in doc
    assert doc.count('class="g2-barra"') == 4, "são quatro barras para criar o efeito"


def test_o_criar_e_o_sentir_apontam_para_o_quadro_que_eles_leem() -> None:
    """Sem `data-hef-forma` o gesto chega sem as barras e recusa («não consegui ler a área»).

    Achado na bancada de tela: o Sentir foi clicado e o daemon de mentira não recebeu nada.
    """
    doc = _o_que_se_le()
    assert doc.count('id="criar-gatilhos"') == 1
    for gesto in ("criar-efeito", "sentir"):
        botao = re.search(rf'<button[^>]*data-gesto="{gesto}"[^>]*>', doc)
        assert botao and 'data-hef-forma="criar-gatilhos"' in botao.group(0), (gesto, botao)


def test_cada_celula_conectada_tem_o_acionamento_e_a_imersao_e_a_vazia_nao() -> None:
    doc = _desenho()
    celulas = doc.split('<div class="g2-cel"')[1:]
    assert len(celulas) == 16, f"são 4 lugares x 2 gatilhos x 2 campos: {len(celulas)} células"
    for c in celulas:
        vazia = 'data-conectado="nao"' in c.split(">", 1)[0]
        assert "g2-acion" in c or "g2-imersao" in c, c[:200]
        if "g2-acion" in c:
            assert 'data-gesto="modo"' in c, c[:200]
        if "g2-imersao" in c:
            assert 'data-gesto="imersao"' in c, c[:200]
        assert ('<option value="—" selected' in c) == vazia, (
            "o lugar sem controle mostra o travessão e o conectado, não: " + c[:160])
    assert doc.count('data-gesto="imersao"') == 8 and doc.count('data-gesto="modo"') == 8


def test_cada_acionamento_com_imersao_oferece_as_tres_e_o_off_nenhuma(a03) -> None:
    for familia, modos in imersao.FAMILIAS.items():
        for modo in modos:
            html = a03.html_das_opcoes_de_imersao(modo)
            chaves = re.findall(r'value="([^"]+)"', html)
            delas = [c for c in chaves if c in imersao.POR_CHAVE]
            assert len(delas) == 3, (familia, modo, delas)
            assert all(imersao.POR_CHAVE[c].familia == familia for c in delas)
    sem = a03.html_das_opcoes_de_imersao("Off")
    assert "<optgroup label=\"Desligado" not in sem
    assert not [c for c in re.findall(r'value="([^"]+)"', sem) if c in imersao.POR_CHAVE]


def test_a_imersao_se_reconhece_pelos_numeros_e_o_que_ninguem_conhece_fica_em_branco(a03) -> None:
    uma = imersao.IMERSOES[0]
    modo = imersao.FAMILIAS[uma.familia][0]
    achada = next((m, a) for i, m, e, a in imersao.todos_os_ajustes() if i is uma and e == "")
    params = a03._params_da_imersao(uma, achada[0], "")
    assert params, "a imersão não deu números"
    assert a03._imersao_que_casa(achada[0], params) == uma.chave
    assert a03._imersao_que_casa(modo, a03._padroes(modo)) == a03.SEM_IMERSAO
    proprios = [(v + 1) % 9 for v in a03._padroes("Machine")]
    proprios[0] = 7
    assert a03._imersao_que_casa("Machine", proprios) == "", (
        "números próprios do perfil: dizer «Nenhum» seria mentir")


def test_o_efeito_criado_entra_na_lista_certa_e_so_nela(a03) -> None:
    forma = {"tipo": "acionamento", "partir": "Rigid", "nome": "Freio da régua",
             "inicio": "3", "fim": "9", "forca": "5", "freq": "40"}
    a03.criar_efeito_dos_gatilhos(None, {"forma": forma}, None)
    assert "meu:Freio da régua" in a03.html_das_opcoes_de_modo("left")
    assert "Freio da régua" not in a03.html_das_opcoes_de_imersao("Rigid")
    forma = {**forma, "tipo": "imersao", "nome": "Recuo da régua"}
    a03.criar_efeito_dos_gatilhos(None, {"forma": forma}, None)
    assert "meu:Recuo da régua" in a03.html_das_opcoes_de_imersao("Rigid")
    assert "Recuo da régua" not in a03.html_das_opcoes_de_modo("left")
    assert "Recuo da régua" in a03.html_dos_seus_efeitos()
    assert "Freio da régua" in a03.html_dos_seus_efeitos()


@pytest.mark.parametrize("forma,frase", [
    ({"tipo": "acionamento", "partir": "Rigid", "nome": ""}, "Dê um nome"),
    ({"tipo": "acionamento", "partir": "", "nome": "x"}, "partir"),
    ({"tipo": "", "partir": "Rigid", "nome": "x"}, "acionamento ou de imersão"),
    ({"tipo": "imersao", "partir": "Rigid", "nome": "n" * 200}, "no máximo"),
])
def test_criar_sem_o_que_falta_recusa_dizendo_e_nao_guarda(a03, forma, frase) -> None:
    with pytest.raises(RuntimeError, match=frase):
        a03.criar_efeito_dos_gatilhos(None, {"forma": forma}, None)
    assert a03.meus_efeitos() == {} and a03._meus_efeitos_da("imersao") == {}


class _Ponte:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def trigger_set_detalhado(self, *a: Any, **k: Any) -> tuple[bool, str, dict[str, Any]]:
        self.chamadas.append(("set", a))
        return True, "", {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}

    def trigger_reset_detalhado(self, *a: Any, **k: Any) -> tuple[bool, str, dict[str, Any]]:
        self.chamadas.append(("reset", a))
        return True, "", {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}


def _ctx() -> Any:
    from pacotes import Contexto

    mesa = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua", "via": "USB",
             "cor": "starlight-blue", "mascara": "DualSense"}]
    falso = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True,
             "inputs": {"l2_raw": 0, "r2_raw": 0}}
    return Contexto(state={"active_profile": ""}, mesa=mesa, conectados=[falso], estados={})


def test_escolher_a_imersao_manda_ao_controle_os_numeros_dela(a03, monkeypatch) -> None:
    uma = imersao.POR_CHAVE["rajada-que-sobe-sozinha"]
    ponte = _Ponte()
    o = {"uniq": UNIQ, "lado": "d", "valor": uma.chave,
         "forma": {"modo-chave-d": "Machine"}}
    a03.imersao_escolhida(_ctx(), o, ponte)
    (nome, args), = ponte.chamadas
    assert nome == "set" and "Machine" in args
    assert list(args[2]) == a03._params_da_imersao(uma, "Machine", "")
    ponte2 = _Ponte()
    a03.imersao_escolhida(_ctx(), {**o, "valor": "nenhum"}, ponte2)
    assert list(ponte2.chamadas[0][1][2]) == a03._padroes("Machine")
    with pytest.raises(ValueError, match="não é uma imersão"):
        a03.imersao_escolhida(_ctx(), {**o, "valor": "inventada"}, _Ponte())
    with pytest.raises(RuntimeError, match="não vale para"):
        a03.imersao_escolhida(_ctx(), {**o, "forma": {"modo-chave-d": "Bow"}}, _Ponte())


def test_sentir_toca_nos_dois_gatilhos_e_devolve_o_que_o_controle_recebia(a03, monkeypatch) -> None:
    monkeypatch.setattr(a03, "SENTIR_S", 0.0)
    ponte = _Ponte()
    forma = {"partir": "Rigid", "inicio": "2", "fim": "9", "forca": "4", "freq": "40"}
    a03.sentir(_ctx(), {"uniq": UNIQ, "forma": forma}, ponte)
    tocou, voltou = ponte.chamadas[:2], ponte.chamadas[2:]
    assert [c[0] for c in tocou] == ["set", "set"] and {c[1][0] for c in tocou} == {"left", "right"}
    assert [c[0] for c in voltou] == ["reset", "reset"], (
        "sem perfil o controle recebia Desligado: o que ele recebia volta como `trigger.reset`")
    assert a03.meus_efeitos() == {} and a03._meus_efeitos_da("imersao") == {}


def test_sentir_devolve_o_que_vale_depois_do_toque_e_nao_o_de_antes(a03, monkeypatch) -> None:
    """Uma escolha feita enquanto o efeito toca é a que fica no controle, não a de antes."""
    escolhido: dict[str, Any] = {}
    monkeypatch.setattr(a03.perfil, "ativo", lambda *_a, **_k: dict(escolhido))
    monkeypatch.setattr(a03, "_segurar_o_toque", lambda: escolhido.update(
        {"triggers": {"left": {"mode": "Rigid", "params": [5, 200]}}}))
    ponte = _Ponte()
    forma = {"partir": "Machine", "inicio": "2", "fim": "9", "forca": "4", "freq": "40"}
    a03.sentir(_ctx(), {"uniq": UNIQ, "forma": forma}, ponte)
    voltou = dict((c[1][0], c) for c in ponte.chamadas[2:])
    assert voltou["left"][0] == "set" and voltou["left"][1][1:3] == ("Rigid", [5, 200]), voltou


def test_as_barras_cobrem_so_o_que_o_modo_tem(a03) -> None:
    fora = a03._ajustes_da_criacao("Rigid", {"inicio": "9", "forca": "8", "freq": "255"})
    assert fora and all(n in FAIXAS["Rigid"] for n in fora), fora
    assert "frequency" not in fora, "o Rígido não tem frequência: a barra não faz nada nele"
    cheio = a03._ajustes_da_criacao("Machine", {"forca": "8", "freq": "255"})
    for nome, valor in cheio.items():
        assert valor <= FAIXAS["Machine"][nome][1], (nome, valor)


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema: a régua não tem motor")
def test_o_nome_do_controle_tem_a_largura_da_coluna_e_a_tela_nao_rola() -> None:
    from playwright.sync_api import sync_playwright

    medir = """() => {
      const chip = [...document.querySelectorAll('.g2-cab')].map(e => e.getBoundingClientRect());
      const sel = [...document.querySelectorAll('.g2-acion')].map(e => e.getBoundingClientRect());
      const imer = [...document.querySelectorAll('.g2-imersao')]
        .map(e => e.getBoundingClientRect());
      const vazios = [...document.querySelectorAll('.g2-cab[data-conectado="nao"] .chip')]
        .map(e => [e.innerText.trim(), getComputedStyle(e).visibility,
                   e.getBoundingClientRect().width]);
      const d = document.documentElement;
      return {chip: chip.map(r => [r.left, r.width]), vazios,
              acion: sel.map(r => [r.left, r.width]),
              imer: imer.map(r => [r.left, r.width]),
              rola: d.scrollHeight > d.clientHeight + 1,
              lateral: d.scrollWidth > d.clientWidth + 1};
    }"""
    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        pg = nav.new_page(viewport={"width": 1600, "height": 809})
        pg.goto((RAIZ / "mockup" / PAGINA).as_uri())
        m = pg.evaluate(medir)
        nav.close()
    assert len(m["chip"]) >= 2 and len(m["acion"]) >= 4
    for i, (esq, larg) in enumerate(m["chip"]):
        if m["acion"][i][1] == 0:
            continue  # o lugar sem controle não abre campo: só o nome tracejado
        assert abs(larg - m["acion"][i][1]) < 1.5 and abs(esq - m["acion"][i][0]) < 1.5, (
            f"o nome do controle {i} não tem a largura e o lugar da coluna: "
            f"{(esq, larg)} contra {m['acion'][i]}")
        assert abs(larg - m["imer"][i][1]) < 1.5, (i, larg, m["imer"][i])
    assert not m["rola"] and not m["lateral"], m
    # o lugar vazio diz que ali cabe um controle, como no desenho do todo
    assert m["vazios"] and all(
        v[0].endswith("Desconectado") and v[1] == "visible" and v[2] > 0 for v in m["vazios"]), (
        m["vazios"])
