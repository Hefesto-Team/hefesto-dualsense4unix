"""A PROVA DA MESA DE MEDIÇÃO — o que a régua do construtor não alcançava.

`test_a_mesa_de_medicao.py` é do construtor e prova a montagem. Este arquivo é
da PROVA, e ele mede outra coisa: **o que uma página vazia também passaria**.

A cicatriz que o justifica é desta casa e é de hoje: uma régua que roda o tique
uma vez mede um INSTANTE; uma que confere presença mede a PALAVRA. Quatro das
provas da §7 da especificação — *nada acontece antes do INICIAR*, *o timer
conta antes de aplicar*, *a resposta sobrevive*, *o índice tem seções* —
passariam sobre uma página que não renderizasse coisa alguma, porque todas elas
conferem AUSÊNCIA ou um punhado de elementos. Por isso a primeira régua deste
arquivo é o PISO DE CONTEÚDO, e ela tem mordida própria.

O QUE ELE MEDE E O OUTRO NÃO:

* o piso de conteúdo, com a mordida (uma página vazia REPROVA);
* a inércia antes do INICIAR medida em TRÊS camadas — a tela, a REDE e o DISCO.
  O construtor conferia só a tela, e uma página que já tivesse gravado em disco
  passaria;
* o timer DESCENDO no relógio, e nenhum pedido de desenho durante a contagem.
  O construtor conferia que o relógio não estava vazio — um relógio parado
  passa nisso;
* a resposta sobrevivendo à MORTE DO SERVIDOR: processo morto por PID, processo
  novo, e o campo relido. O construtor recarregava a aba com o mesmo servidor de
  pé, o que não separa o disco da memória do processo;
* as lâmpadas do jogador conferidas contra o padrão canônico do produto
  (`1→3 · 2→24 · 3→135 · 4→1245`), e não só "alguma acesa";
* o veredito do índice, que dava VERDE SOBRE NADA — ver
  :func:`test_mordida_os_quatro_disseram_nada_e_o_indice_dizia_obedeceu`.

TODA JANELA É HEADLESS. O Chrome sobe sem tela, que é o padrão de `launch()`, e
é o mesmo caminho dos portões `pecas-do-dualsense` e `cores-do-dualsense`.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))
import mesa_de_medicao as med

CHROME = "/usr/bin/google-chrome"

PISO = {
    "elementos": 400,
    "testes": 140,
    "palavras": 200,
    "formas": 200,
    "regras_de_cor": 28,
    "linhas_do_indice": 140,
}

class _Servidor:
    """Sobe `mesa_de_medicao.py --servir` num processo próprio."""

    def __init__(self, lar: pathlib.Path, mentira: pathlib.Path | None = None):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(RAIZ / "src")
        env["XDG_STATE_HOME"] = str(lar)
        env["HOME"] = str(lar)
        env.pop("MESA_DE_MEDICAO_MESA_DE_MENTIRA", None)
        if mentira:
            env[med.PORTA_DA_REGUA] = str(mentira)
        self.proc = subprocess.Popen(
            [sys.executable, str(RAIZ / "scripts/mesa_de_medicao.py"),
             "--servir", "--porta", "0"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env=env, cwd=str(RAIZ))
        linha = (self.proc.stdout.readline() or "").strip()
        if not linha.startswith("http://127.0.0.1:"):
            self.morrer()
            raise AssertionError(f"o servidor não subiu: {linha!r}")
        self.url = linha
        self.registro = lar / "hefesto-dualsense4unix/mesa-de-medicao"

    def morrer(self) -> None:
        """Por PID CONFERIDO, nunca `pkill -f` — um `pkill -f` já derrubou o"""
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.morrer()


def _abre_o_como(pg) -> None:
    """Abre a gaveta do campo do COMO, CLICANDO — nunca pelo `.open`."""
    if not pg.evaluate("() => !!document.querySelector('#caixa-do-gesto')?.open"):
        pg.click("#caixa-do-gesto > summary")
    pg.wait_for_selector("#gesto", state="visible")

def _mentira_dos_quatro(alvo: pathlib.Path) -> pathlib.Path:
    """Quatro modelos DIFERENTES, pela porta declarada da régua."""
    modelos = [("P1", "cosmic-red", "Cosmic Red", "USB", 87, "charging"),
               ("P2", "starlight-blue", "Starlight Blue", "USB", 64, "discharging"),
               ("P3", "nova-pink", "Nova Pink", "BT", 41, "discharging"),
               ("P4", "midnight-black", "Midnight Black", "BT", 92, "full")]
    postos = {
        p: {"posto": p, "presente": True, "nome": nome, "modelo": nome,
            "colorway": slug, "transporte": t, "bateria": bat,
            "estado_da_bateria": est, "uniq": f"AA:BB:CC:D{i}:E{i}:0{i}",
            "lampada": i, "barra": "#00ff00"}
        for i, (p, slug, nome, t, bat, est) in enumerate(modelos, 1)}
    alvo.write_text(json.dumps({"daemon": "", "quando": "", "postos": postos}),
                    encoding="utf-8")
    return alvo


def _testes_da_pagina(url: str) -> list[dict]:
    corpo = urllib.request.urlopen(url, timeout=20).read().decode("utf-8")
    return json.loads(re.search(r"window\.__TESTES__ = (\[.*?\]);\n", corpo, re.S).group(1))


_MEDIR = """() => ({
  elementos: document.querySelectorAll('*').length,
  testes: (window.__TESTES__ || []).length,
  palavras: document.body.innerText.trim().split(/\\s+/).filter(Boolean).length,
  formas: document.querySelectorAll(
     '.ctl svg path, .ctl svg rect, .ctl svg circle, .ctl svg ellipse').length,
  regras_de_cor: Array.from(document.styleSheets).reduce((n, s) => {
     try { return n + Array.from(s.cssRules).filter(
        r => /data-colorway=/.test(r.selectorText || '')).length; }
     catch (e) { return n; } }, 0),
  linhas_do_indice: document.querySelectorAll('#indice-corpo tr').length,
})"""


@pytest.fixture()
def lar(tmp_path):
    p = tmp_path / "lar"
    p.mkdir()
    return p


@pytest.fixture()
def mentira(tmp_path):
    return _mentira_dos_quatro(tmp_path / "mentira.json")


@pytest.fixture()
def pw():
    sync_playwright = pytest.importorskip(
        "playwright.sync_api", reason="playwright não está no pyproject",
    ).sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=CHROME)
        try:
            yield nav
        finally:
            nav.close()


pytestmark = pytest.mark.skipif(
    not pathlib.Path(CHROME).exists(), reason="sem Chrome")


def test_a_pagina_tem_conteudo_real_e_a_regua_morde_a_pagina_vazia(
        pw, lar, mentira, tmp_path) -> None:
    """O PISO DE CONTEÚDO, com a mordida ao lado no MESMO teste."""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1000})
        alvo = next(t for t in _testes_da_pagina(s.url) if t["pecas"])
        pg.goto(s.url + "#" + alvo["id"])
        pg.wait_for_selector("#iniciar")
        pg.click("#iniciar")
        pg.click("#pular-timer")
        pg.wait_for_selector(".ctl svg")
        medido = pg.evaluate(_MEDIR)

        abaixo = {k: (medido[k], v) for k, v in PISO.items() if medido[k] < v}
        assert not abaixo, f"a página não tem conteúdo real: {abaixo}"

        vazia = tmp_path / "vazia.html"
        vazia.write_text("<!doctype html><html><body></body></html>",
                         encoding="utf-8")
        pg.goto(vazia.as_uri())
        nada = pg.evaluate(_MEDIR)
        reprovou = [k for k, v in PISO.items() if nada[k] < v]
        assert set(reprovou) == set(PISO), (
            "a régua do piso não morde a página vazia — ela passaria em "
            f"{sorted(set(PISO) - set(reprovou))}")
        pg.close()


def test_nada_acontece_antes_do_iniciar_nem_na_tela_nem_na_rede_nem_no_disco(
        pw, lar, mentira) -> None:
    """A inércia do TEMPO 1 — e o que ela alcança NÃO é o desenho."""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1000})
        pedidos: list[str] = []
        pg.on("request", lambda r: pedidos.append(f"{r.method} {r.url}"))
        todos = _testes_da_pagina(s.url)
        alvo = next(t for t in todos if t["pecas"])
        pg.goto(s.url + "#" + alvo["id"])
        pg.wait_for_selector("#iniciar")

        assert pg.is_visible("#antes")
        assert not pg.is_visible("#contagem"), "o timer correu sem ela clicar"
        assert not pg.is_visible("#depois"), "o TEMPO 3 apareceu sozinho"
        pg.wait_for_selector(".ctl svg")
        assert pg.eval_on_selector_all(".ctl svg", "e=>e.length") == 4, (
            "os quatro desenhos NÃO estão na tela antes do INICIAR — ela vai "
            "mexer no aparelho sem ter visto onde olhar")
        assert pg.eval_on_selector_all(".ctl g.marcada", "e=>e.length") > 0, (
            "nenhuma peça acesa no TEMPO 1: o desenho está lá e não diz nada")
        assert pg.eval_on_selector_all(
            "input[type=radio]", "e=>e.filter(x=>x.offsetParent!==null).length") == 0, (
            "as respostas por controle estão CLICÁVEIS antes do INICIAR")
        assert [p for p in pedidos if "/registro" in p] == []
        assert not s.registro.exists() or not list(s.registro.iterdir()), (
            "a página encostou no disco antes de ela clicar em INICIAR")

        for t in (todos[0], todos[len(todos) // 2], todos[-1]):
            pg.goto(s.url + "#" + t["id"])
            pg.wait_for_selector("#iniciar")
            assert pg.is_visible("#iniciar"), f"sem INICIAR em {t['id']}"
        pg.close()


def test_o_timer_desce_e_nada_e_aplicado_enquanto_ele_corre(
        pw, lar, mentira) -> None:
    """O relógio DESCENDO, não só presente."""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1000})
        alvo = next(t for t in _testes_da_pagina(s.url)
                    if t["pecas"] and t["segundos"] >= 5)
        pg.goto(s.url + "#" + alvo["id"])
        pg.wait_for_selector("#iniciar")
        assert int(pg.inner_text("#segundos-alvo")) == alvo["segundos"]

        pedidos: list[str] = []
        pg.on("request", lambda r: pedidos.append(r.url))
        pg.click("#iniciar")
        primeiro = int(pg.inner_text("#relogio").strip())
        assert pg.is_visible("#contagem") and not pg.is_visible("#depois")
        pg.wait_for_timeout(2400)
        segundo = int(pg.inner_text("#relogio").strip())

        assert primeiro - segundo >= 2, (
            f"o relógio não desceu: {primeiro} -> {segundo} em 2,4 s")
        assert [p for p in pedidos if "/desenhos" in p] == [], (
            "os desenhos foram REMONTADOS durante a contagem — a peça acesa "
            "pisca na cara dela no pior momento, que é justamente quando ela "
            "está olhando os controles. Eles já estavam na tela desde o TEMPO 1")
        assert pg.eval_on_selector_all(".ctl svg", "e=>e.length") == 4, (
            "os desenhos SUMIRAM quando o timer começou — é durante a contagem "
            "que ela mais precisa deles")
        pg.close()


def test_o_timer_longo_sai_do_arquivo_e_nao_de_um_numero_fixo(lar) -> None:
    """A linha 10 do roteiro diz *"volta neles aos 20 min"*, e o timer conta"""
    testes = med.todos_os_testes()
    tempos = sorted({t.segundos for t in testes})
    assert len(tempos) >= 3, f"todos os testes contam o mesmo tempo: {tempos}"
    assert max(tempos) >= 1200, (
        f"o tempo mais longo da mesa é {max(tempos)}s — a linha do roteiro que "
        f"pede vinte minutos não chegou até aqui")


def test_a_resposta_sobrevive_ao_servidor_morrer_e_o_endereco_sai_mascarado(
        pw, lar, mentira) -> None:
    """O disco, separado da memória do processo."""
    gesto = "prova: interface.sh > aba 03 > efeito Arma no P3 · report 0x02"
    s = _Servidor(lar, mentira)
    try:
        pg = pw.new_page(viewport={"width": 1280, "height": 1000})
        alvo = next(t for t in _testes_da_pagina(s.url) if t["pecas"])
        reage = next((p for p, v in alvo["papeis"].items() if v == "reage"), "P3")
        pg.goto(s.url + "#" + alvo["id"])
        pg.wait_for_selector("#iniciar")
        pg.click("#iniciar")
        pg.click("#pular-timer")
        pg.wait_for_selector(".ctl svg")
        pg.check(f'.ctl[data-posto="{reage}"] input[value="obedeceu"]')
        pg.fill('textarea[name="n-P3"]', "so o P3 endureceu")
        _abre_o_como(pg)
        pg.fill("#gesto", gesto)
        pg.click("#so-salvar")
        pg.wait_for_timeout(600)
        na_tela = pg.inner_text(".quatro")
        pg.close()
    finally:
        s.morrer()

    assert s.proc.poll() is not None, "o servidor não morreu"

    assert "AA:BB:CC:00:00:01" in na_tela
    assert not re.search(r"AA:BB:CC:D\d:E\d", na_tela), (
        "o endereço cru chegou à tela")
    fita = sorted(s.registro.glob("registro-*.jsonl"))
    assert fita, "nada foi para o disco"
    bruto = fita[0].read_text(encoding="utf-8")
    assert gesto in bruto
    assert not re.search(r"AA:BB:CC:D\d:E\d", bruto), (
        "o endereço cru chegou à fita")

    s2 = _Servidor(lar, mentira)
    try:
        pg = pw.new_page(viewport={"width": 1280, "height": 1000})
        pg.goto(s2.url + "#" + alvo["id"])
        pg.wait_for_selector("#iniciar")
        pg.click("#iniciar")
        pg.click("#pular-timer")
        pg.wait_for_selector(".ctl svg")
        assert pg.input_value("#gesto") == gesto, (
            "o COMO não sobreviveu à morte do servidor")
        assert pg.is_checked(f'.ctl[data-posto="{reage}"] input[value="obedeceu"]')
        pg.close()
    finally:
        s2.morrer()


def test_os_quatro_trazem_transporte_modelo_e_a_lampada_do_padrao_do_produto(
        pw, lar, mentira) -> None:
    """As lâmpadas conferidas contra o PADRÃO, e o padrão vem do produto."""
    sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))
    import monta

    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1000})
        alvo = next(t for t in _testes_da_pagina(s.url) if t["pecas"])
        pg.goto(s.url + "#" + alvo["id"])
        pg.wait_for_selector("#iniciar")
        pg.click("#iniciar")
        pg.click("#pular-timer")
        pg.wait_for_selector(".ctl svg")

        cores = pg.eval_on_selector_all(
            ".ctl svg", "es=>es.map(e=>e.getAttribute('data-colorway'))")
        assert cores == ["cosmic-red", "starlight-blue", "nova-pink",
                         "midnight-black"], cores

        cartoes = pg.eval_on_selector_all(".ctl", "es=>es.map(e=>e.innerText)")
        for esperado, cartao in zip(
                ["Cosmic Red", "Starlight Blue", "Nova Pink", "Midnight Black"],
                cartoes, strict=True):
            assert esperado in cartao, f"o modelo {esperado} sumiu do cartão"
        for esperado, cartao in zip(["USB", "USB", "BT", "BT"], cartoes, strict=True):
            assert esperado in cartao, f"o transporte {esperado} sumiu do cartão"

        acesas = pg.eval_on_selector_all(
            ".ctl", "es=>es.map(e=>Array.from("
                    "e.querySelectorAll('[id*=led-jogador-].led-on'))"
                    ".map(x=>x.id.slice(-1)).sort().join(''))")
        canonico = ["".join(sorted(monta.PADRAO_JOGADOR[n])) for n in (1, 2, 3, 4)]
        assert acesas == canonico, (
            f"as lâmpadas do jogador não seguem o padrão do produto: "
            f"{acesas} != {canonico}")
        pg.close()


def test_mordida_os_quatro_disseram_nada_e_o_indice_dizia_obedeceu() -> None:
    """DEFEITO MEDIDO E CURADO NESTA PROVA, e ele era um verde sobre nada."""
    assert med.veredito({p: "nada" for p in med.POSTOS}) == "falhou"
    assert med.veredito({"P1": "nada"}) == "falhou"
    assert med.veredito({}) == "não feito"
    assert med.veredito({"P1": "nao-vi", "P2": "nao-vi"}) == "não feito"
    assert med.veredito({"P1": "obedeceu", "P2": "nada"}) == "obedeceu"
    assert med.veredito({"P1": "outra-coisa"}) == "parcial"
    assert med.veredito({p: "obedeceu" for p in med.POSTOS}) == "obedeceu"


def test_todo_estado_que_o_indice_pinta_e_alcancavel() -> None:
    """A paleta e a função têm de falar dos MESMOS estados."""
    do_js = set(re.findall(r"v === '([^']+)'", med._JS))
    do_js.add("não feito")
    alcancaveis = {
        med.veredito(r) for r in (
            {}, {"P1": "nao-vi"}, {"P1": "nada"}, {"P1": "obedeceu"},
            {"P1": "outra-coisa"}, {"P1": "obedeceu", "P2": "nao-vi"})
    }
    assert do_js <= alcancaveis, (
        f"o índice pinta estados que a função nunca devolve: "
        f"{sorted(do_js - alcancaveis)}")


def test_a_recusa_do_como_nao_deixa_rastro_no_disco(lar) -> None:
    """400 é metade da prova; a outra metade é o disco continuar vazio."""
    with _Servidor(lar) as s:
        pedido = urllib.request.Request(
            s.url + "registro",
            data=json.dumps({"teste": "x", "respostas": {"P1": "obedeceu"},
                             "gesto": "   "}).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with pytest.raises(urllib.error.HTTPError) as erro:
            urllib.request.urlopen(pedido, timeout=10)
        assert erro.value.code == 400
        assert "COMO" in erro.value.read().decode("utf-8")
    assert not s.registro.exists() or not list(s.registro.glob("registro-*.jsonl")), (
        "a recusa deixou rastro em disco")


def test_o_tema_e_o_da_casa_e_nao_uma_paleta_desta_pagina(pw, lar, mentira) -> None:
    """*"mantém o mesmo tema que vemos aplicando"*."""
    assert med.paleta_da_casa.TOKENS in med._CSS, (
        "o CSS da mesa não contém os tokens da casa — alguém voltou a digitar "
        "a paleta aqui")
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 900})
        pg.goto(s.url)
        pg.wait_for_selector("#desenhos svg")
        fundo = pg.eval_on_selector("body", "e=>getComputedStyle(e).backgroundColor")
        tinta = pg.eval_on_selector("body", "e=>getComputedStyle(e).color")
        def luz(cor: str) -> float:
            r, g, b = (int(x) for x in re.findall(r"\d+", cor)[:3])
            return (r * 299 + g * 587 + b * 114) / 1000
        assert luz(fundo) < 60, f"o fundo não é escuro: {fundo}"
        assert luz(tinta) > 190, f"a tinta não é clara: {tinta}"
        pg.close()


def test_cada_controle_tem_as_opcoes_e_um_campo_so_dele(pw, lar, mentira) -> None:
    """*"coloca em baixo de cada controle as opções do que selecionar e um campo"""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1100})
        alvo = next(t for t in _testes_da_pagina(s.url) if t["pecas"])
        pg.goto(s.url + "#" + alvo["id"])
        pg.wait_for_selector("#iniciar")
        pg.click("#iniciar")
        pg.click("#pular-timer")
        pg.wait_for_selector(".ctl .extra")

        for posto in ("P1", "P2", "P3", "P4"):
            cartao = pg.query_selector(f'.ctl[data-posto="{posto}"]')
            assert cartao, f"sem cartão do {posto}"
            assert len(cartao.query_selector_all("input[type=radio]")) == len(med.RESPOSTAS)
            assert cartao.query_selector("textarea.extra"), (
                f"o {posto} não tem campo próprio")
            svg = cartao.query_selector("svg").bounding_box()
            resp = cartao.query_selector(".resp").bounding_box()
            extra = cartao.query_selector("textarea.extra").bounding_box()
            assert resp["y"] >= svg["y"] + svg["height"] - 2, (
                f"as opções do {posto} não estão abaixo do desenho")
            quatro = cartao.query_selector_all(".resp input[type=radio]")
            ultimo = quatro[-1].bounding_box()
            assert cartao.query_selector(".resp textarea.extra"), (
                f"o campo do {posto} não está dentro da lista das opções")
            assert extra["y"] >= ultimo["y"] - 2, (
                f"o campo do {posto} não vem depois da quarta opção")
            assert extra["y"] <= resp["y"] + resp["height"] + 2, (
                f"o campo do {posto} caiu fora da caixa das opções")

        pg.check('input[name="r-P1"][value="obedeceu"]')
        pg.fill('textarea[name="n-P1"]', "só o motor esquerdo")
        pg.fill('textarea[name="n-P3"]', "nada no direito")
        _abre_o_como(pg)
        pg.fill("#gesto", "hefesto test rumble --player 1")
        pg.click("#so-salvar")
        pg.wait_for_timeout(600)

        fita = [json.loads(x) for x in
                (s.registro / f"registro-{med._agora()[:10]}.jsonl")
                .read_text(encoding="utf-8").splitlines()]
        assert fita[-1]["notas"] == {"P1": "só o motor esquerdo",
                                     "P3": "nada no direito"}, fita[-1]["notas"]
        pg.close()


def test_o_verificar_diz_certo_ou_errado_por_controle(pw, lar, mentira) -> None:
    """*"após responder e clicar em verificar ele mostra se deu certo ou errado"""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1100})
        alvo = next(t for t in _testes_da_pagina(s.url)
                    if med.PAPEL_REAGE in t["papeis"].values()
                    and med.PAPEL_CALADO in t["papeis"].values())
        pg.goto(s.url + "#" + alvo["id"])
        pg.wait_for_selector("#iniciar")
        pg.click("#iniciar")
        pg.click("#pular-timer")
        pg.wait_for_selector(".ctl .resp")

        assert pg.eval_on_selector_all(
            ".laudo", "e=>e.filter(x=>x.offsetParent!==null).length") == 0, (
            "o laudo apareceu antes de ela clicar em verificar")

        reage = next(p for p, v in alvo["papeis"].items() if v == med.PAPEL_REAGE)
        calado = next(p for p, v in alvo["papeis"].items() if v == med.PAPEL_CALADO)
        pg.check(f'input[name="r-{reage}"][value="nada"]')
        pg.check(f'input[name="r-{calado}"][value="nada"]')
        pg.click("#verificar")
        pg.wait_for_timeout(300)

        def classe(p: str) -> str:
            return pg.eval_on_selector(f"#laudo-{p}", "e=>e.className")

        assert "v-nao-bate" in classe(reage), (
            f"{reage} devia reagir, respondeu 'nada', e o laudo não acusou")
        assert "v-bate" in classe(calado), (
            f"{calado} devia ficar calado, ficou, e o laudo não confirmou")
        assert pg.eval_on_selector_all(
            ".laudo", "e=>e.filter(x=>x.offsetParent!==null).length") == 4, (
            "o laudo não apareceu nos quatro")
        assert "NÃO bate" in pg.inner_text("#resumo-do-laudo")
        pg.close()


def test_a_capa_explica_o_teste_e_ela_sobrevive_aos_tres_tempos(
        pw, lar, mentira) -> None:
    """*"começa na parte superior explicando o que está sendo testado e afins"*."""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1100})
        alvo = next(t for t in _testes_da_pagina(s.url)
                    if t["pecas"] and t["passa_quando"])
        pg.goto(s.url + "#" + alvo["id"])
        pg.wait_for_selector("#desenhos svg")

        capa = pg.query_selector(".capa").bounding_box()
        desenhos = pg.query_selector("#desenhos").bounding_box()
        assert capa["y"] + capa["height"] <= desenhos["y"] + 2, (
            "a capa não vem antes dos quatro desenhos")

        for tempo, ir_ate in ((1, None), (3, "#iniciar")):
            if ir_ate:
                pg.click("#iniciar")
                pg.click("#pular-timer")
                pg.wait_for_selector(".ctl .resp")
            texto = pg.inner_text(".capa")
            assert alvo["titulo"][:24] in texto, f"sem o título no tempo {tempo}"
            assert alvo["passa_quando"][:24] in texto, (
                f"o 'passa quando' sumiu no tempo {tempo} — e o {tempo} é a "
                f"hora de julgar contra ele")
        pg.close()


# O QUE O USUÁRIO PEDIU EM 07/09/2026, com quatro DualSense na mesa e o daemon parado
def test_os_quatro_aparecem_sem_daemon_lidos_do_kernel() -> None:
    """**.

    A página só sabia perguntar ao daemon, e com ele parado punha travessão em
    tudo — como se não houvesse controle nenhum, tendo QUATRO. Tudo isto o
    `hid_playstation` publica de graça no `sysfs`, sem escrever um byte.

    A RÉGUA RODA NA MÁQUINA REAL e pula quando não há DualSense — ela mede o
    que o kernel publica, e um dublê de `sysfs` mediria o dublê.
    """
    # VIVO existe um segundo nó chamado "DualSense Wireless Controller
    def _e_dualsense(no: pathlib.Path) -> bool:
        texto = (no / "device" / "uevent").read_text(
            encoding="utf-8", errors="replace")
        vid, pid = med._VID_PID_DUALSENSE
        alvos = {f"HID_ID=0003:{vid}:{pid}", f"HID_ID=0005:{vid}:{pid}"}
        return any(linha.strip() in alvos for linha in texto.splitlines())

    todos = sorted(pathlib.Path("/sys/class/hidraw").glob("hidraw*"))
    nos = [n for n in todos if _e_dualsense(n)]
    if not nos:
        pytest.skip("nenhum DualSense nesta máquina agora")
    vistos = med.pelo_sysfs()
    assert len(vistos) == len(nos), (
        f"o kernel mostra {len(nos)} DualSense e a leitura devolveu "
        f"{len(vistos)} — a segunda fonte não está lendo")
    emulados = [n for n in todos
                if "Hefesto" in (n / "device" / "uevent").read_text(
                    encoding="utf-8", errors="replace")]
    enderecos = {v["uniq_cru"] for v in vistos}
    for e in emulados:
        cru = (e / "device" / "uevent").read_text(
            encoding="utf-8", errors="replace")
        campos = dict(linha.split("=", 1) for linha in cru.splitlines()
                      if "=" in linha)
        assert campos.get("HID_UNIQ", "?") not in enderecos, (
            "o controle virtual do daemon entrou na mesa como se fosse "
            "plástico")
    for v in vistos:
        assert v["transporte"] in ("cabo", "rádio"), v
        assert v["uniq"], "sem endereço"
        assert v["uniq"].split(":")[3] == "00", f"MAC sem máscara: {v['uniq']}"
        assert v["uniq"].split(":")[4] == "00", f"MAC sem máscara: {v['uniq']}"
    assert all("colorway" not in v for v in vistos)


def test_a_cor_que_ela_disse_fica_guardada_pelo_endereco(lar, monkeypatch) -> None:
    """A cor do plástico não se lê sem escrever no controle, e esta página não"""
    monkeypatch.setenv("XDG_STATE_HOME", str(lar))
    monkeypatch.setattr(med, "pasta_do_registro",
                        lambda: lar / "mesa-de-medicao")
    assert med.cores_que_ela_disse() == {}
    med.guardar_cor_dela("aa:bb:cc:00:00:01", "nova-pink")
    assert med.cores_que_ela_disse() == {"aa:bb:cc:00:00:01": "nova-pink"}
    assert med.nome_do_colorway("nova-pink") == "Nova Pink"
    med.guardar_cor_dela("aa:bb:cc:00:00:01", "")
    assert med.cores_que_ela_disse() == {}


def test_um_controle_de_cada_vez_quando_e_de_maos_e_ouvidos() -> None:
    """Teste de mãos e ouvidos roda um controle de cada vez."""
    ts = med.todos_os_testes()
    por_id = {t.id: t for t in ts}
    assert por_id["roteiro-06"].um_por_vez, "a vibração tem de ser um por vez"
    assert por_id["roteiro-09"].um_por_vez, "o microfone tem de ser um por vez"
    audio = [t for t in ts if "audio" in t.secao]
    assert audio and all(t.um_por_vez for t in audio), (
        [t.id for t in audio if not t.um_por_vez])
    luz = [t for t in ts if "luz" in t.secao]
    assert luz and not any(t.um_por_vez for t in luz), (
        "a luz virou um-por-vez, e ela se lê com os olhos nos quatro de uma vez")


def test_o_como_vem_pronto_e_nao_e_cobrado_dela(pw, lar, mentira) -> None:
    """O «como» de cada teste já vem pronto na página; ninguém o preenche."""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1100})
        alvo = next(t for t in _testes_da_pagina(s.url)
                    if t["como"] and not t["um_por_vez"])
        pg.goto(s.url + "#" + alvo["id"])
        pg.wait_for_selector("#iniciar")
        pg.click("#iniciar")
        pg.click("#pular-timer")
        pg.wait_for_selector(".ctl .resp")

        _abre_o_como(pg)
        gesto = pg.input_value("#gesto")
        assert gesto.strip(), "o COMO chegou vazio — ela teria de digitar"
        passos = dict(alvo["como"]).get("os passos", "")
        primeiro = next((x.strip() for x in passos.split("\n") if x.strip()), "")
        assert primeiro, f"o teste {alvo['id']} não publica passos"
        assert primeiro[:30] in gesto, (gesto[:160], primeiro[:60])

        pg.check('input[name="r-P1"][value="obedeceu"]')
        pg.click("#so-salvar")
        pg.wait_for_timeout(700)
        assert not pg.inner_text("#aviso").strip(), pg.inner_text("#aviso")
        fita = (s.registro / f"registro-{med._agora()[:10]}.jsonl")
        assert fita.exists(), "não gravou sem ela digitar o COMO"
        pg.close()


def test_a_pagina_abre_no_que_falta_e_o_medido_vem_pre_marcado(
        pw, lar, mentira) -> None:
    """*"a ideia é ficar fácil pra validarmos as teses, a grande maioria ali já"""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1100})
        pg.goto(s.url)
        pg.wait_for_selector("#desenhos svg")

        assert pg.eval_on_selector("#f-falta", "e=>e.classList.contains('ligado')")
        assert pg.evaluate("() => TESTES.every(t => !t.ja_medido)"), (
            "a página abriu mostrando testes já medidos")
        assert pg.evaluate("() => TODOS.some(t => t.ja_medido)"), (
            "nenhum teste tem selo de medido — o filtro não teria o que mostrar")

        pg.click("#f-medido")
        pg.wait_for_timeout(500)
        assert pg.evaluate("() => TESTES.every(t => t.ja_medido)")
        assert pg.is_visible("#selo"), "o selo do que já foi medido não aparece"
        assert "medido" in pg.inner_text("#selo").lower()

        i = pg.evaluate("() => TESTES.findIndex(t => t.resposta_do_mapa)")
        assert i >= 0, "nenhum medido traz a resposta que o mapa implica"
        pg.evaluate("(i) => ir(i, 3)", i)
        pg.wait_for_selector(".ctl .resp")
        pg.wait_for_timeout(400)
        assert pg.eval_on_selector_all(
            "input[type=radio]:checked", "e=>e.length") == 4, (
            "a resposta do mapa não foi pré-marcada nos quatro")
        assert pg.eval_on_selector_all(".vindo-do-mapa", "e=>e.length") == 4, (
            "a pré-marca não está declarada como vinda do mapa — ela "
            "confundiria o que o arquivo afirma com o que viu")
        pg.close()


def _so_o_codigo(fonte: str) -> str:
    """O fonte sem comentários e sem literais de texto."""
    import io
    import tokenize as _tk

    fora = []
    for tok in _tk.generate_tokens(io.StringIO(fonte).readline):
        if tok.type in (_tk.COMMENT, _tk.STRING):
            continue
        fora.append(tok.string)
    return " ".join(fora)


def test_as_21_estao_nas_seis_secoes_do_roteiro() -> None:
    """*"cadê as seções das 21?"* — 07/09/2026, ela olhando o seletor."""
    secoes = med.secoes_do_roteiro()
    assert len(secoes) == 21, secoes
    assert len(set(secoes.values())) == 6, sorted(set(secoes.values()))
    das_21 = [t for t in med.todos_os_testes() if t.id.startswith("roteiro-")]
    assert len({t.secao for t in das_21}) == 6, {t.secao for t in das_21}
    assert all(t.secao.startswith("O roteiro ·") for t in das_21), (
        [t.secao for t in das_21 if not t.secao.startswith("O roteiro ·")])
    for nome in set(secoes.values()):
        assert any(nome in t.secao for t in das_21), nome


def test_a_cor_se_le_do_aparelho_sob_o_comando_dela() -> None:
    """*"A cor exige escrita mesmo. Mas ler uma vez, sob seu comando, é o que o"""
    fonte = pathlib.Path(med.__file__).read_text(encoding="utf-8")
    assert "cor_do_plastico.ler_pelo_cabo" in fonte, (
        "a mesa deixou de perguntar ao dono da leitura")
    codigo = _so_o_codigo(fonte)
    for proibido in ("montar_pedido", "0x80", "SET_FEATURE", "ioctl",
                     "HIDIOCSFEATURE"):
        assert proibido not in codigo, (
            f"a mesa passou a montar o pedido ela mesma (`{proibido}`) — a "
            f"trava do byte tem UM dono, e não é esta página")
    corpo = fonte.split("def ler_a_cor_no_aparelho", 1)[1]
    chamadas = corpo.count("ler_a_cor_no_aparelho()")
    assert chamadas == 1, (
        f"`ler_a_cor_no_aparelho` é chamada {chamadas} vezes — ela escreve no "
        f"aparelho, e escrever tem de ser ato dela, uma vez por clique")
    assert 'caminho == "/ler-cor"' in fonte


def test_a_borda_do_cartao_e_a_cor_do_plastico(pw, lar, mentira) -> None:
    """*"a borda de cada controle deve ter a borda na cor do model"*."""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1000})
        alvo = next(t for t in _testes_da_pagina(s.url)
                    if med.PAPEL_REAGE in t["papeis"].values())
        pg.goto(s.url + "#" + alvo["id"])
        pg.wait_for_selector(".ctl svg")
        pg.wait_for_timeout(400)
        bordas = pg.eval_on_selector_all(
            ".ctl", "es=>es.map(e=>getComputedStyle(e).borderColor)")
        assert len(set(bordas)) == 4, (
            f"os quatro cartões têm a mesma borda: {bordas} — a cor do "
            f"plástico não chegou à moldura")
        import monta
        cores = pg.eval_on_selector_all(
            ".ctl svg", "es=>es.map(e=>e.getAttribute('data-colorway'))")
        for borda, colorway in zip(bordas, cores, strict=True):
            esperado = monta.cor_da_zona(colorway, "casca-solida")
            r, g, b = (int(x, 16) for x in
                       (esperado[1:3], esperado[3:5], esperado[5:7]))
            assert borda == f"rgb({r}, {g}, {b})", (colorway, borda, esperado)
        pg.close()


def test_a_peca_em_foco_acende_como_no_mapa_do_controle(pw, lar, mentira) -> None:
    """*"as bordas ou coisas a serem observadas ficam com o foco o mesmo que"""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1000})
        pg.goto(s.url)
        pg.wait_for_selector("#desenhos svg")
        rosa = pg.evaluate(
            "() => { const s = document.createElement('span');"
            " s.style.color = 'var(--color-pink)'; document.body.appendChild(s);"
            " const c = getComputedStyle(s).color; s.remove(); return c; }")
        for peca in ("touchpad", "lightbar", "l2", "feat-rumble-esquerdo",
                     "feat-giroscopio", "mic", "alto-falante"):
            i = pg.evaluate(
                "(p) => TESTES.findIndex(t => t.pecas.some(x => x[0] === p))", peca)
            assert i >= 0, f"nenhum teste acende `{peca}`"
            pg.evaluate("(i) => ir(i, 1)", i)
            pg.wait_for_timeout(700)
            medido = pg.evaluate("""(p) => {
              const g = document.querySelector(`#p1-${p}`);
              if (!g) return null;
              const f = g.querySelector('path,circle,rect,ellipse,polygon');
              return {op: getComputedStyle(g).opacity,
                      fill: f ? getComputedStyle(f).fill : null};
            }""", peca)
            assert medido, f"`{peca}` não está no desenho"
            assert medido["fill"] == rosa, (peca, medido)
            assert float(medido["op"]) == 1.0, (
                f"`{peca}` acende meio transparente ({medido['op']}) — meia "
                f"instrução")
        pg.close()


def test_a_folha_do_desenho_vem_do_mapa_do_controle() -> None:
    """*"e cara o contorno não tá pintado (…) abra o playwright e mude o tipo"""
    folha = med.folha_do_desenho(["p1", "p2"])
    assert "stroke:var(--z-casca-solida" in folha and "--sem-plastico:" in folha, (
        "a folha do desenho perdeu o contorno na cor do plástico")
    assert ".sem-tinta{fill:none !important" in folha.replace(" ", " "), (
        "sem a `sem-tinta` o círculo do PS volta — *\"o do PS não tem esse "
        "círculo no meio\"*")
    for var in ("--led-apagado", "--led-aceso", "--luz-apagada"):
        assert f"{var}:" in folha, (
            f"`{var}` é usada e não é declarada — um valor que não resolve não "
            f"herda o de trás, cai no preto")
    assert "#p1-corpo" in folha and "#p2-corpo" in folha, folha[:400]
    assert "mp-" not in folha, "sobrou endereço do mapa na folha da mesa"
    assert ":hover" not in folha, "veio o realce do mapa, e ele é do ponteiro"


def test_o_desenho_da_mesa_pinta_o_contorno_como_o_mapa(pw, lar, mentira) -> None:
    """O contorno, medido: cor do plástico e ESPESSURA que se enxerga."""
    import monta

    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1600, "height": 1100})
        pg.goto(s.url)
        pg.wait_for_selector(".ctl svg")
        pg.wait_for_timeout(600)
        medido = pg.evaluate("""() => [...document.querySelectorAll('.ctl')]
          .map(c => {
            const svg = c.querySelector('svg');
            const g = svg.querySelector('[id$="-corpo"]');
            const alvo = g && g.querySelector('.corpo,.peca');
            const s = alvo ? getComputedStyle(alvo) : null;
            return {colorway: svg.getAttribute('data-colorway'),
                    largura: Math.round(svg.getBoundingClientRect().width),
                    stroke: s && s.stroke, w: s && s.strokeWidth,
                    efeito: s && s.getPropertyValue('vector-effect')};
          })""")
        assert len(medido) == 4, medido
        for c in medido:
            if not c["colorway"]:
                continue
            esperado = monta.cor_da_zona(c["colorway"], "casca-solida")
            r, g, b = (int(esperado[i:i + 2], 16) for i in (1, 3, 5))
            assert c["stroke"] == f"rgb({r}, {g}, {b})", (
                f"o contorno de {c['colorway']} não é a cor do plástico: {c}")
            assert c["efeito"] == "non-scaling-stroke", (
                f"o traço voltou a escalar com o desenho: {c}")
            assert float(c["w"].rstrip("px")) >= 1.4, (
                f"o contorno é fino demais para se ver: {c}")
        pg.close()


def test_o_ps_nao_acende_o_circulo_que_ela_mandou_tirar(pw, lar, mentira) -> None:
    """*"o do PS não tem esse círculo no meio"* — 07/09/2026."""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1440, "height": 1000})
        pg.goto(s.url)
        pg.wait_for_selector(".ctl svg")
        pg.wait_for_timeout(600)
        medido = pg.evaluate("""() => {
          const g = document.querySelector('#p1-ps');
          if (!g) return null;
          g.classList.add('marcada');
          const f = g.querySelector('path,circle,rect,ellipse,polygon');
          const s = getComputedStyle(f);
          const fora = {fill: s.fill, stroke: s.stroke,
                        cor_do_grupo: getComputedStyle(g).color};
          g.classList.remove('marcada');
          return fora;
        }""")
        assert medido, "o PS sumiu do desenho"
        assert medido["fill"] == "none" and medido["stroke"] == "none", (
            f"o círculo do PS acendeu: {medido} — ela mandou tirá-lo em 27/08")
        assert medido["cor_do_grupo"] != "none", medido


def test_as_21_da_bancada_se_escolhem_num_corte_so(pw, lar, mentira) -> None:
    """*"quais desses são os mais importantes? não fez separação dos 21 mais?"*"""
    quantas = len(med.secoes_do_roteiro())
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1600, "height": 1100})
        pg.goto(s.url)
        pg.wait_for_selector(".ctl svg")
        pg.wait_for_timeout(500)
        visto = pg.evaluate("""() => {
          const sel = document.querySelector('#secao-filtro');
          return {grupos: [...sel.querySelectorAll('optgroup')].map(g => g.label),
                  primeiras: [...sel.options].slice(0, 2).map(o => o.text),
                  valor_do_corte: sel.options[1] && sel.options[1].value};
        }""")
        assert len(visto["grupos"]) == 2, (
            f"o seletor não separa a bancada do acervo: {visto}")
        assert any("BANCADA" in g for g in visto["grupos"]), visto["grupos"]
        assert any("ACERVO" in g for g in visto["grupos"]), visto["grupos"]
        assert str(quantas) in visto["primeiras"][1], (
            f"a linha do roteiro inteiro não diz quantas são: {visto}")

        pg.select_option("#secao-filtro", visto["valor_do_corte"])
        pg.wait_for_timeout(500)
        depois = pg.evaluate(
            "() => ({n: TESTES.length,"
            "        so_roteiro: TESTES.every(t => t.secao.startsWith('O roteiro'))})")
        assert depois["n"] == quantas, (
            f"o corte das {quantas} deixou {depois['n']} na tela")
        assert depois["so_roteiro"], "entrou célula do acervo no corte da bancada"
        assert f"1 de {quantas}" in pg.inner_text("header, main").replace(
            "\n", " ") or f"1 DE {quantas}" in pg.inner_text("body").upper(), (
            "a página não diz que agora são as do roteiro")
        pg.close()


def test_a_espera_longa_nao_prende_ela_na_tela(pw, lar, mentira) -> None:
    """** — 07/09/2026,"""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1400, "height": 1050})
        pg.goto(s.url)
        pg.wait_for_selector(".ctl svg")
        pg.wait_for_timeout(500)
        limiar = pg.evaluate("() => ESPERA_LONGA")
        assert limiar > 0, "o limiar da espera longa sumiu do módulo"

        def espera(qual: str) -> dict[str, object]:
            i = pg.evaluate(
                "(l) => TESTES.findIndex(t => l === 'longa'"
                "        ? t.segundos >= ESPERA_LONGA : t.segundos < ESPERA_LONGA)",
                qual)
            assert i >= 0, f"nenhum teste com espera {qual}"
            pg.evaluate("(i) => ir(i, 1)", i)
            pg.wait_for_timeout(400)
            pg.evaluate("() => iniciar()")
            pg.wait_for_timeout(700)
            return pg.evaluate("""() => ({
              titulo: document.querySelector('#titulo-da-espera').textContent,
              recado_escondido: document.querySelector('#recado-da-espera').hidden,
              relogio: parseFloat(getComputedStyle(
                  document.querySelector('#relogio')).fontSize),
              segundos: TESTES[atual].segundos,
            })""")

        longa, curta = espera("longa"), espera("curta")

        assert "volte" in longa["titulo"].lower(), longa
        assert str(round(longa["segundos"] / 60)) in longa["titulo"], longa
        assert not longa["recado_escondido"], (
            "a espera longa não explica que ela pode sair — e é justamente o "
            "que ela precisa saber")
        assert "olhos" in curta["titulo"].lower(), curta
        assert curta["recado_escondido"], (
            "a espera curta ganhou o recado da longa — mandar sair da tela por "
            "dez segundos é perder o gesto")
        assert longa["relogio"] < curta["relogio"] / 2, (
            f"o relógio da espera longa continua grande ({longa['relogio']}px "
            f"contra {curta['relogio']}px) — ele volta a ser a coisa que ela "
            f"olha por vinte minutos")
        pg.close()


def test_as_21_trazem_o_gesto_e_ele_vem_do_arquivo_dono() -> None:
    """*"O COMO é obrigatório: escreva o gesto exato que foi aplicado. isso aqui"""
    das_21 = [t for t in med.todos_os_testes() if t.id.startswith("roteiro-")]
    assert len(das_21) == 21, len(das_21)
    obrigatorios = {"o que isto prova", "onde olhar", "os passos",
                    "como saber que passou", "por controle"}
    sem_gesto = []
    for teste in das_21:
        rotulos = {r for r, _ in teste.como}
        if not obrigatorios <= rotulos:
            sem_gesto.append((teste.id, sorted(obrigatorios - rotulos)))
    assert not sem_gesto, (
        f"{len(sem_gesto)} das 21 não trazem o gesto inteiro: {sem_gesto}")

    for teste in das_21:
        passos = dict(teste.como)["os passos"]
        quantos = len([x for x in passos.split("\n") if x.strip()])
        assert quantos >= 3, (
            f"{teste.id} tem {quantos} passos — um teste de bancada "
            f"com menos de três passos é um título, não um gesto")

    fonte = pathlib.Path(med.__file__).read_text(encoding="utf-8")
    assert "como_das_21()" in fonte, "a mesa deixou de ler o dono do gesto"
    assert med._O_COMO_DAS_21.endswith(".md")
    assert med._o_dono_do_gesto(med._O_COMO_DAS_21) is not None, (
        f"o arquivo do gesto sumiu: {med._O_COMO_DAS_21}")


def test_o_gesto_e_o_corpo_do_teste_e_nao_uma_gaveta(pw, lar, mentira) -> None:
    """O gesto vivia dentro de um `details` FECHADO."""
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1500, "height": 1200})
        pg.goto(s.url)
        pg.wait_for_selector(".ctl svg")
        pg.wait_for_timeout(700)
        i = pg.evaluate("() => TESTES.findIndex(t => t.id === 'roteiro-10')")
        assert i >= 0, "a linha 10 sumiu da fatia aberta"
        pg.evaluate("(i) => ir(i, 1)", i)
        pg.wait_for_timeout(700)
        visto = pg.evaluate("""() => {
          const g = document.querySelector('#como-do-arquivo');
          if (!g) return null;
          const d = document.querySelector('#desenhos');
          return {
            visivel: g.offsetParent !== null,
            dentro_de_gaveta: !!g.closest('details'),
            antes_dos_desenhos: !!(d && (g.compareDocumentPosition(d)
                                   & Node.DOCUMENT_POSITION_FOLLOWING)),
            rotulos: [...g.querySelectorAll('b')].map((e) => e.textContent),
            itens_de_lista: g.querySelectorAll('li').length,
            texto: g.textContent.length,
          };
        }""")
        assert visto, "o bloco do gesto sumiu da página"
        assert visto["visivel"], "o gesto voltou a nascer escondido"
        assert not visto["dentro_de_gaveta"], (
            "o gesto voltou para dentro de um `details` — o que ela precisa "
            "para executar não pode custar um clique")
        assert visto["antes_dos_desenhos"], (
            "o gesto ficou DEPOIS dos desenhos; a instrução precede o ato")
        assert "onde olhar" in visto["rotulos"], visto["rotulos"]
        assert visto["itens_de_lista"] >= 5, (
            f"os passos não viraram lista ({visto['itens_de_lista']} itens) — "
            f"uma parede de texto é o que ela não conseguiu executar")
        assert visto["texto"] > 500, (
            f"o gesto tem {visto['texto']} caracteres; a linha 10 sozinha tem "
            f"mais que isso no arquivo — a leitura não chegou à tela")
        assert "---" not in pg.inner_text("#como-do-arquivo"), (
            "o `---` que divide as seções do arquivo vazou para a tela")
        pg.close()


def test_o_acervo_do_mapa_tambem_tem_gesto() -> None:
    """*"depois de melhorar os 21. quero que aí sim vc use o novo modelo pra"""
    do_arquivo = med.como_do_mapa()
    assert len(do_arquivo) > 150, (
        f"o arquivo do gesto do mapa publica {len(do_arquivo)} células — "
        f"alguém o encolheu, ou a leitura quebrou")
    do_mapa = [x for x in med.todos_os_testes()
               if not x.id.startswith("roteiro-")]
    sem = [x.id for x in do_mapa
           if not any(r == "os passos" for r, _ in x.como)]
    assert not sem, (
        f"{len(sem)} células do mapa chegaram sem gesto: {sem[:5]} — e sem ele "
        f"o COMO volta a ser a procedência repetida, que é o defeito que ela "
        f"apontou na linha 10 do roteiro")

    assert med._O_COMO_DAS_21 != med._O_COMO_DO_MAPA
    for caminho in (med._O_COMO_DAS_21, med._O_COMO_DO_MAPA):
        assert med._o_dono_do_gesto(caminho) is not None, caminho

    for x in do_mapa[:40]:
        onde = dict(x.como).get("onde olhar", "")
        assert onde, x.id
        lado = "cabo" if x.id.endswith("-cabo") else "rádio"
        outro = "rádio" if lado == "cabo" else "cabo"
        corpo = " ".join(v for _, v in x.como).lower()
        assert lado in corpo or outro not in corpo, (
            f"{x.id} fala só do {outro} — o gesto caiu na célula errada")


def test_todo_token_de_cor_sem_reserva_esta_definido() -> None:
    """`var(--x)` sem reserva tem de existir — senão a regra some calada."""
    css = med._CSS
    definidos = set(re.findall(r"(--[\w-]+)\s*:", css))
    secos = set(re.findall(r"var\(\s*(--[\w-]+)\s*\)", css))
    orfaos = sorted(secos - definidos)
    assert not orfaos, (
        f"{len(orfaos)} token(s) usados sem reserva e sem definição: {orfaos}. "
        f"O navegador descarta a propriedade inteira e ninguém vê.")


def test_a_mascara_pega_as_duas_formas_de_endereco() -> None:
    """Com dois-pontos e COLADO — o daemon publica a segunda."""
    assert med._mascarar("aa:bb:cc:dd:ee:ff") == "aa:bb:cc:00:00:ff"
    assert med._mascarar("aabbccddeeff") == "aabbcc0000ff"
    assert med._mascarar("AABBCCDDEEFF") == "AABBCC0000FF"
    assert med._mascarar("") == ""
    assert med._mascarar("sem endereço") == "sem endereço"


def test_o_daemon_vivo_nao_e_mais_pobre_que_o_kernel(monkeypatch) -> None:
    """Transporte e carga têm de sobreviver aos DOIS caminhos."""
    daemon = {"controllers": [{
        "index": 0, "connected": True, "transport": "usb", "player_slot": 1,
        "uniq": "aabbccddeeff", "battery_pct": 100, "modelo": "Galactic Purple",
    }]}
    monkeypatch.setattr(med, "_pergunta_ao_daemon", lambda *a, **k: daemon)
    monkeypatch.setattr(med, "pelo_sysfs", lambda: [{
        "uniq": "aa:bb:cc:00:00:ff", "uniq_cru": "aa:bb:cc:dd:ee:ff",
        "transporte": "cabo", "bateria": 100, "estado_da_bateria": "full",
        "lampada": 1, "barra": "", "no": "hidraw0", "nome_do_driver": "",
    }])
    p1 = med.quem_esta_na_mesa()["postos"]["P1"]
    assert p1["transporte"] == "cabo", (
        f"o daemon disse `usb` e o cartão mostrou {p1['transporte']!r}")
    assert p1["estado_da_bateria"] == "full", (
        "a carga sumiu — o daemon não a publica e o kernel publica")
    assert p1["uniq"] == "aabbcc0000ff", (
        f"o endereço saiu sem máscara: {p1['uniq']!r}")

    daemon["controllers"][0]["transport"] = "bt"
    assert med.quem_esta_na_mesa()["postos"]["P1"]["transporte"] == "rádio"


def test_os_dois_donos_do_gesto_sao_rastreados_pelo_git() -> None:
    """O gesto das 199 células viaja no clone, ou não é gesto de ninguém."""
    for relativo in (med._O_COMO_DAS_21, med._O_COMO_DO_MAPA):
        assert relativo.startswith("docs/method/"), (
            f"o dono do gesto voltou para uma pasta de processo: {relativo}")
        assert (med.RAIZ / relativo).is_file(), f"sumiu do disco: {relativo}"
        rastreado = subprocess.run(
            ["git", "-C", str(med.RAIZ), "ls-files", "--error-unmatch",
             relativo],
            capture_output=True, text=True, check=False)
        assert rastreado.returncode == 0, (
            f"`{relativo}` não é rastreado pelo git — o gesto de 199 testes "
            "morre no próximo clone limpo, calado, como morreu em 20/09")


def test_o_dono_que_some_grita_e_nao_devolve_vazio(tmp_path, monkeypatch) -> None:
    """A ausência virou defeito duro, e é a mudança de 20/09/2026."""
    monkeypatch.setattr(med, "RAIZ", tmp_path)
    relativo = "docs/method/UM-DONO.md"

    (tmp_path / "docs" / "method").mkdir(parents=True)
    dono = tmp_path / relativo
    dono.write_text("## um-id — título\n\n**O que isto prova.** algo\n",
                    encoding="utf-8")
    assert med._o_dono_do_gesto(relativo) == dono

    dono.unlink()
    assert med._o_dono_do_gesto(relativo) is None
    with pytest.raises(FileNotFoundError, match="o dono do gesto sumiu"):
        med._gesto_do_arquivo(relativo, r"##\s+(\S+)", lambda m: m.group(1))

    shutil.rmtree(tmp_path / "docs" / "method")
    with pytest.raises(FileNotFoundError, match="o dono do gesto sumiu"):
        med._gesto_do_arquivo(relativo, r"##\s+(\S+)", lambda m: m.group(1))
