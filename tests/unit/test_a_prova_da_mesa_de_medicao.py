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
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))
import mesa_de_medicao as med

CHROME = "/usr/bin/google-chrome"

#: O piso de conteúdo. Cada número foi MEDIDO na página de 06/09/2026 e escrito
#: bem abaixo do medido, porque um piso colado no medido reprova no dia em que
#: alguém acrescenta um teste — e um piso longe do medido não morde. Os medidos,
#: para quem for mexer: 2036 elementos · 148 testes · 2635 palavras · 212 formas
#: nos quatro desenhos · 252 regras `data-colorway` · 148 linhas de índice.
PISO = {
    "elementos": 400,
    "testes": 140,
    "palavras": 200,
    "formas": 200,
    "regras_de_cor": 28,
    "linhas_do_indice": 140,
}

# ---------------------------------------------------------------------------
# O servidor de verdade, em processo à parte — é o que permite MATÁ-LO
# ---------------------------------------------------------------------------
class _Servidor:
    """Sobe `mesa_de_medicao.py --servir` num processo próprio.

    POR QUE UM PROCESSO E NÃO A `servir()` NA MESMA MEMÓRIA: a prova da §7.5 é
    que a resposta está **em disco, não só no navegador**. Com o servidor na
    mesma memória do teste, o `estado.json` relido poderia estar vindo de um
    cache do processo e ninguém veria a diferença. Matando o processo e subindo
    outro, o que sobrevive é só o que o disco guardou.
    """

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
        """Por PID CONFERIDO, nunca `pkill -f` — um `pkill -f` já derrubou o
        compositor dela."""
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


def _mentira_dos_quatro(alvo: pathlib.Path) -> pathlib.Path:
    """Quatro modelos DIFERENTES, pela porta declarada da régua.

    O endereço é FICTÍCIO (OUI `AA:BB:CC`, que não é de fabricante nenhum) e
    entra **sem máscara de propósito**: a prova é que ele sai com os octetos 4 e
    5 zerados nos dois lados — na tela e no disco.
    """
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


#: A MEDIDA DO CONTEÚDO, e ela é UMA função porque a mordida a chama também.
#: Duas cópias e a mordida mediria outra coisa que a régua.
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
        nav = p.chromium.launch(executable_path=CHROME)  # headless é o padrão
        try:
            yield nav
        finally:
            nav.close()


pytestmark = pytest.mark.skipif(
    not pathlib.Path(CHROME).exists(), reason="sem Chrome")


# ---------------------------------------------------------------------------
# 0. A RÉGUA CONTRA A CURA PREGUIÇOSA — e ela vem primeiro de propósito
# ---------------------------------------------------------------------------
def test_a_pagina_tem_conteudo_real_e_a_regua_morde_a_pagina_vazia(
        pw, lar, mentira, tmp_path) -> None:
    """O PISO DE CONTEÚDO, com a mordida ao lado no MESMO teste.

    Uma página que não renderiza nada passa em quase toda prova de ausência —
    e é assim que uma cura preguiçosa atravessa uma leva inteira. Esta régua
    exige NÚMERO: elementos, testes, palavras, formas de desenho, regras de cor
    e linhas de índice. A mordida é uma página vazia medida pela **mesma
    função** — duas cópias e a mordida mediria outra coisa que a régua.
    """
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

        # A MORDIDA: a mesma medida, numa página que não renderiza nada.
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


# ---------------------------------------------------------------------------
# §7.2 — NADA acontece antes do INICIAR, medido em TRÊS camadas
# ---------------------------------------------------------------------------
def test_nada_acontece_antes_do_iniciar_nem_na_tela_nem_na_rede_nem_no_disco(
        pw, lar, mentira) -> None:
    """A inércia do TEMPO 1 — e o que ela alcança NÃO é o desenho.

    O construtor conferia a TELA. Uma página que já tivesse gravado uma linha em
    disco passaria numa régua mais frouxa — e o registro dela nasceria com uma
    resposta que ela nunca deu. Aqui se conferem as três camadas: o que está na
    tela, o que saiu pela rede e o que encostou no disco.

    O QUE ESTA RÉGUA COBRAVA A MAIS, E DEIXOU DE COBRAR — 06/09/2026: ela exigia
    ZERO desenho antes do INICIAR, lendo *"botão de INICIAR antes de qualquer
    coisa acontecer"* como se alcançasse a ilustração. Não alcança, e a mesma
    encomenda diz o contrário duas frases depois: *"O botão mostra o que vai
    acontecer E O QUE OBSERVAR"*, e *"Faça os svgs brilharem mostrando o que
    observar de cada controle em cada rodada"*. O desenho com a peça acesa É o
    "o que observar" — ele é a INSTRUÇÃO, não o recibo. Com ele preso ao TEMPO 3
    ela lia o texto, apertava INICIAR e ia mexer no aparelho SEM NUNCA TER VISTO
    onde olhar; o desenho só chegava depois, quando a hora de observar já tinha
    passado. Agora o teste cobra o oposto: os quatro ESTÃO na tela no TEMPO 1.

    O que "nada acontece" alcança de verdade continua cobrado abaixo, inteiro: o
    timer não corre sozinho, as respostas por controle não aparecem antes de ela
    ter o que responder, e NADA encosta no disco.
    """
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
        # A RESPOSTA fica escondida no TEMPO 1, e o desenho não: as duas moram
        # no mesmo cartão, e o corte é por tempo (`body[data-tempo]`). Marcar
        # "obedeceu" antes de aplicar é gravar uma resposta sobre nada.
        assert pg.eval_on_selector_all(
            "input[type=radio]", "e=>e.filter(x=>x.offsetParent!==null).length") == 0, (
            "as respostas por controle estão CLICÁVEIS antes do INICIAR")
        assert [p for p in pedidos if "/registro" in p] == []
        assert not s.registro.exists() or not list(s.registro.iterdir()), (
            "a página encostou no disco antes de ela clicar em INICIAR")

        # E o INICIAR existe em TODO teste, não só neste: o primeiro, o do meio
        # e o último. Um botão que só nasce na primeira linha não é o contrato.
        for t in (todos[0], todos[len(todos) // 2], todos[-1]):
            pg.goto(s.url + "#" + t["id"])
            pg.wait_for_selector("#iniciar")
            assert pg.is_visible("#iniciar"), f"sem INICIAR em {t['id']}"
        pg.close()


# ---------------------------------------------------------------------------
# §7.3 — o timer CONTA, e conta ANTES
# ---------------------------------------------------------------------------
def test_o_timer_desce_e_nada_e_aplicado_enquanto_ele_corre(
        pw, lar, mentira) -> None:
    """O relógio DESCENDO, não só presente.

    Um relógio parado em "5" passa numa régua que pergunta se o texto não está
    vazio. Aqui se lê o número duas vezes, com 2,4 s entre elas, e se cobra a
    diferença — e, no mesmo intervalo, que nenhum desenho tenha sido pedido: é
    isso que faz o timer estar ANTES de aplicar, e não ao lado.
    """
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
    """A linha 10 do roteiro diz *"volta neles aos 20 min"*, e o timer conta
    1200 s por causa disso. Se o tempo fosse um literal desta página, os 148
    testes contariam o mesmo número."""
    testes = med.todos_os_testes()
    tempos = sorted({t.segundos for t in testes})
    assert len(tempos) >= 3, f"todos os testes contam o mesmo tempo: {tempos}"
    assert max(tempos) >= 1200, (
        f"o tempo mais longo da mesa é {max(tempos)}s — a linha do roteiro que "
        f"pede vinte minutos não chegou até aqui")


# ---------------------------------------------------------------------------
# §7.5 — a resposta sobrevive à MORTE DO SERVIDOR
# ---------------------------------------------------------------------------
def test_a_resposta_sobrevive_ao_servidor_morrer_e_o_endereco_sai_mascarado(
        pw, lar, mentira) -> None:
    """O disco, separado da memória do processo.

    Recarregar a aba com o mesmo servidor de pé não separa as duas coisas: o
    `estado.json` poderia estar vindo de um cache e a régua não veria. Aqui o
    processo é MORTO por PID, outro sobe no lugar, e o que aparece na tela é só
    o que o disco guardou.
    """
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
        # O CAMPO GERAL SAIU em 07/09/2026 — palavra dela: *"O que eu vi no
        # conjunto não deve existir assim, demos 4 opções pra cada controle
        # uma 5 deveria ser um campo pra eu descrever por controle o que
        # ocorreu"*. O que ela escreve mora no campo DO CONTROLE.
        pg.fill('textarea[name="n-P3"]', "so o P3 endureceu")
        pg.fill("#gesto", gesto)
        pg.click("#so-salvar")
        pg.wait_for_timeout(600)
        na_tela = pg.inner_text(".quatro")
        pg.close()
    finally:
        s.morrer()

    assert s.proc.poll() is not None, "o servidor não morreu"

    # O ENDEREÇO, mascarado nas duas camadas.
    assert "AA:BB:CC:00:00:01" in na_tela
    assert not re.search(r"AA:BB:CC:D\d:E\d", na_tela), (
        "o endereço cru chegou à tela")
    fita = sorted(s.registro.glob("registro-*.jsonl"))
    assert fita, "nada foi para o disco"
    bruto = fita[0].read_text(encoding="utf-8")
    assert gesto in bruto
    assert not re.search(r"AA:BB:CC:D\d:E\d", bruto), (
        "o endereço cru chegou à fita")

    # E AGORA UM PROCESSO NOVO. Só o disco atravessa daqui.
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


# ---------------------------------------------------------------------------
# §7.6 — os quatro desenhos, com a lâmpada CANÔNICA
# ---------------------------------------------------------------------------
def test_os_quatro_trazem_transporte_modelo_e_a_lampada_do_padrao_do_produto(
        pw, lar, mentira) -> None:
    """As lâmpadas conferidas contra o PADRÃO, e o padrão vem do produto.

    "Alguma lâmpada acesa" passa mesmo quando os quatro acendem a mesma. O
    padrão canônico é `1→3 · 2→24 · 3→135 · 4→1245` e quem o diz é
    `core/led_control.py::player_led_pattern` — ele é LIDO daqui, nunca
    digitado: a tabela já foi digitada uma vez nesta casa e o jogador 3 estava
    errado por um mês.
    """
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


# ---------------------------------------------------------------------------
# O VEREDITO — o verde sobre nada que o índice mostrava
# ---------------------------------------------------------------------------
def test_mordida_os_quatro_disseram_nada_e_o_indice_dizia_obedeceu() -> None:
    """DEFEITO MEDIDO E CURADO NESTA PROVA, e ele era um verde sobre nada.

    Medido em 06/09/2026, com a função como o construtor a entregou:

        veredito({P1..P4: "nada"})  ->  "obedeceu"

    Os quatro controles disseram *"não aconteceu nada"* e o índice — que é o
    instrumento que ela lê para saber o que ainda falta — pintava a linha de
    VERDE. A regra era `all(v in ("obedeceu", "nada"))`, e um conjunto só de
    `nada` a satisfaz.

    E `falhou` era INALCANÇÁVEL: a docstring nomeia quatro estados, o CSS tem a
    classe `.e-falhou` e o JS tem o ramo que a escolhe — e nenhum caminho da
    função jamais o devolvia. Uma paleta com quatro cores para três estados é o
    instrumento afirmando uma medida que ele não faz.

    A cura não julga papel, que é a decisão do construtor e continua de pé:
    `obedeceu` só exige que **ao menos um** controle tenha obedecido.
    """
    assert med.veredito({p: "nada" for p in med.POSTOS}) == "falhou"
    assert med.veredito({"P1": "nada"}) == "falhou"
    # e o que já valia continua valendo
    assert med.veredito({}) == "não feito"
    assert med.veredito({"P1": "nao-vi", "P2": "nao-vi"}) == "não feito"
    assert med.veredito({"P1": "obedeceu", "P2": "nada"}) == "obedeceu"
    assert med.veredito({"P1": "outra-coisa"}) == "parcial"
    # a resposta `obedeceu` num controle que devia ficar calado continua sendo
    # um ACHADO, não um "falhou" automático
    assert med.veredito({p: "obedeceu" for p in med.POSTOS}) == "obedeceu"


def test_todo_estado_que_o_indice_pinta_e_alcancavel() -> None:
    """A paleta e a função têm de falar dos MESMOS estados.

    O JS do índice escolhe entre quatro classes. Se um dos quatro estados não
    tem caminho em :func:`veredito`, a página declara uma medida que ela não
    faz — e foi exatamente o caso de `falhou` até esta prova.
    """
    do_js = set(re.findall(r"v === '([^']+)'", med._JS))
    do_js.add("não feito")  # o `else` do encadeado, que o `e-nao` pinta
    alcancaveis = {
        med.veredito(r) for r in (
            {}, {"P1": "nao-vi"}, {"P1": "nada"}, {"P1": "obedeceu"},
            {"P1": "outra-coisa"}, {"P1": "obedeceu", "P2": "nao-vi"})
    }
    assert do_js <= alcancaveis, (
        f"o índice pinta estados que a função nunca devolve: "
        f"{sorted(do_js - alcancaveis)}")


# ---------------------------------------------------------------------------
# O que o servidor recusa — o COMO, pela porta HTTP, com o disco conferido
# ---------------------------------------------------------------------------
def test_a_recusa_do_como_nao_deixa_rastro_no_disco(lar) -> None:
    """400 é metade da prova; a outra metade é o disco continuar vazio.

    Um servidor que devolvesse 400 DEPOIS de escrever a linha teria a régua
    verde e o defeito vivo — e o defeito é justamente uma resposta gravada sem
    o modo de chegar nela.
    """
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


# ---------------------------------------------------------------------------
# O QUE ELA PEDIU EM 06/09/2026, olhando a primeira versão da página:
#
#   *"tá péssimo o layout e usabilidade da página de testes. mantém o mesmo
#   tema que vemos aplicando. coloca em baixo de cada controle as opções do que
#   selecionar e um campo extra. após responder e clicar em verificar ele mostra
#   se deu certo ou errado pra cada controle. deixa mais clean o layout e começa
#   na parte superior explicando o que está sendo testado e afins."*
#
# Cada régua abaixo cobra UMA dessas frases, no navegador.
# ---------------------------------------------------------------------------
def test_o_tema_e_o_da_casa_e_nao_uma_paleta_desta_pagina(pw, lar, mentira) -> None:
    """*"mantém o mesmo tema que vemos aplicando"*.

    A mesa nasceu com nove hex CLAROS digitados nela — a quinta cópia da mesma
    decisão de paleta, e a única fora de dia. A régua não compara hex: ela cobra
    que o texto do CSS venha do DONO (`paleta_da_casa.TOKENS`, o mesmo de que o
    `specs.html`, o `painel.html`, o `frases-de-tela.html` e o `index.html`
    leem) e que a página renderize ESCURO de verdade.
    """
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
    """*"coloca em baixo de cada controle as opções do que selecionar e um campo
    extra"*.

    O campo geral continua existindo e é sobre o conjunto; este é sobre ESTE
    controle. A régua cobra os dois: quatro campos próprios, e o que ela digita
    em cada um chegando ao DISCO com o nome do controle — um campo que a tela
    mostra e o registro não guarda é pior que campo nenhum.
    """
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
            # E EMBAIXO, não em cima: a caixa das opções começa depois do
            # desenho terminar. Um cartão que empilhasse ao contrário passaria
            # numa régua que só conta elementos.
            svg = cartao.query_selector("svg").bounding_box()
            resp = cartao.query_selector(".resp").bounding_box()
            extra = cartao.query_selector("textarea.extra").bounding_box()
            assert resp["y"] >= svg["y"] + svg["height"] - 2, (
                f"as opções do {posto} não estão abaixo do desenho")
            # O CAMPO É A QUINTA OPÇÃO, e por isso mora DENTRO da lista das
            # quatro — dela: *"demos 4 opções pra cada controle uma 5 deveria
            # ser um campo pra eu descrever por controle o que ocorreu"*. A
            # régua cobrava o contrário (o campo DEPOIS da caixa) e passaria
            # com ele solto no fim do cartão, que é onde ele NÃO deve estar.
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
    """*"após responder e clicar em verificar ele mostra se deu certo ou errado
    pra cada controle"*.

    E o veredito NÃO PODE aparecer antes do clique: um laudo na tela antes de
    ela responder é um laudo sobre nada. A régua vai aos dois lados — o que
    não se vê antes, e o que se vê depois, por controle.
    """
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1100})
        # um teste com papéis DISTINTOS: sem isso o "certo ou errado" não se
        # distingue, e a régua passaria medindo quatro vereditos iguais.
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

        # Responde ERRADO em quem devia reagir e CERTO em quem devia calar.
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
    """*"começa na parte superior explicando o que está sendo testado e afins"*.

    E ela fica. O defeito que isto cura tinha DUAS metades: a explicação vinha
    DEPOIS dos quatro desenhos (ela via os controles antes de saber para quê) e
    era pintada só no TEMPO 1 — some justamente no TEMPO 3, que é a hora de
    julgar o que aconteceu.
    """
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


# ---------------------------------------------------------------------------
# O QUE ELA PEDIU EM 07/09/2026, com quatro DualSense na mesa e o daemon parado
# ---------------------------------------------------------------------------
def test_os_quatro_aparecem_sem_daemon_lidos_do_kernel() -> None:
    """*"não estamos usando o nosso mapa? pq até agora ele não entendeu qual
    player deveria aparecer, nem qual controle (…) nem o modo de conexão (qual
    é bt e qual é cabo) se tá ou não carregando"*.

    A página só sabia perguntar ao daemon, e com ele parado punha travessão em
    tudo — como se não houvesse controle nenhum, tendo QUATRO. Tudo isto o
    `hid_playstation` publica de graça no `sysfs`, sem escrever um byte.

    A RÉGUA RODA NA MÁQUINA REAL e pula quando não há DualSense — ela mede o
    que o kernel publica, e um dublê de `sysfs` mediria o dublê.
    """
    # A RÉGUA CONTA OS NÓS PRIMEIRO, e só pula se não houver nenhum. Sem esta
    # metade a mordida não mordia: arrancar a leitura fazia `pelo_sysfs()`
    # devolver vazio, e a régua PULAVA em vez de reprovar — verde sobre uma
    # cura arrancada, que é a família que esta casa caça.
    nos = [n for n in pathlib.Path("/sys/class/hidraw").glob("hidraw*")
           if "DualSense" in (n / "device" / "uevent").read_text(
               encoding="utf-8", errors="replace")]
    if not nos:
        pytest.skip("nenhum DualSense nesta máquina agora")
    vistos = med.pelo_sysfs()
    assert len(vistos) == len(nos), (
        f"o kernel mostra {len(nos)} DualSense e a leitura devolveu "
        f"{len(vistos)} — a segunda fonte não está lendo")
    for v in vistos:
        assert v["transporte"] in ("cabo", "rádio"), v
        assert v["uniq"], "sem endereço"
        assert v["uniq"].split(":")[3] == "00", f"MAC sem máscara: {v['uniq']}"
        assert v["uniq"].split(":")[4] == "00", f"MAC sem máscara: {v['uniq']}"
    # E A COR NÃO VEM DAQUI, de propósito: ela exige escrita no aparelho.
    assert all("colorway" not in v for v in vistos)


def test_a_cor_que_ela_disse_fica_guardada_pelo_endereco(lar, monkeypatch) -> None:
    """A cor do plástico não se lê sem escrever no controle, e esta página não
    escreve. Então ELA diz qual é, uma vez, e a mesa lembra pelo endereço."""
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
    """*"coisas que eu precisa fazer todos separados um por vez (…) afinal
    podemos ter 4 controles mas só tenho um par de mãos"*.

    Vibração se sente com a MÃO e som se ouve com a ORELHA: medir quatro ao
    mesmo tempo ali não é difícil, é impossível. Luz e bateria não entram,
    porque se leem com os olhos e os olhos pegam os quatro de uma vez.
    """
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
    """*"O COMO é obrigatório (…) isso aqui me quebra. isso eu espero que a
    página descreva"*.

    O COMO já existe nos arquivos — as colunas da própria célula do mapa —, e
    cobrar dela que o digitasse era pedir que redigitasse o que o repositório
    publica. A régua cobra que o campo chegue PREENCHIDO, e que salvar funcione
    sem ela tocar nele.
    """
    with _Servidor(lar, mentira) as s:
        pg = pw.new_page(viewport={"width": 1280, "height": 1100})
        alvo = next(t for t in _testes_da_pagina(s.url)
                    if t["como"] and not t["um_por_vez"])
        pg.goto(s.url + "#" + alvo["id"])
        pg.wait_for_selector("#iniciar")
        pg.click("#iniciar")
        pg.click("#pular-timer")
        pg.wait_for_selector(".ctl .resp")

        gesto = pg.input_value("#gesto")
        assert gesto.strip(), "o COMO chegou vazio — ela teria de digitar"
        assert alvo["como"][0][1][:20] in gesto, (gesto, alvo["como"][0])

        # E SALVA SEM ELA TOCAR NO CAMPO: era exatamente isto que a recusa
        # impedia, e é o que a fez dizer que a página a quebrava.
        pg.check('input[name="r-P1"][value="obedeceu"]')
        pg.click("#so-salvar")
        pg.wait_for_timeout(700)
        assert not pg.inner_text("#aviso").strip(), pg.inner_text("#aviso")
        fita = (s.registro / f"registro-{med._agora()[:10]}.jsonl")
        assert fita.exists(), "não gravou sem ela digitar o COMO"
        pg.close()


def test_a_pagina_abre_no_que_falta_e_o_medido_vem_pre_marcado(
        pw, lar, mentira) -> None:
    """*"a ideia é ficar fácil pra validarmos as teses, a grande maioria ali já
    foi validada uns 80%"*.

    A mesa listava só o que FALTAVA, então ela não tinha como CONFIRMAR nada.
    Agora as duas famílias estão na página: abre no que falta, e o já medido
    vem com o selo e a resposta do mapa pré-marcada.
    """
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
        # o CSS o põe em maiúsculas; a régua lê sem caso, senão mede a folha
        assert "medido" in pg.inner_text("#selo").lower()

        # A RESPOSTA DO MAPA VEM MARCADA, e marcada como VINDA DO MAPA.
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
    """O fonte sem comentários e sem literais de texto.

    Uma régua que varre o arquivo cru não distingue o que o código FAZ do que
    o comentário DESCREVE — e nesta casa os comentários descrevem exatamente o
    que não se pode fazer. `tokenize` faz a separação que a `str` não faz.
    """
    import io
    import tokenize as _tk

    fora = []
    for tok in _tk.generate_tokens(io.StringIO(fonte).readline):
        if tok.type in (_tk.COMMENT, _tk.STRING):
            continue
        fora.append(tok.string)
    return " ".join(fora)


def test_as_21_estao_nas_seis_secoes_do_roteiro() -> None:
    """*"cadê as seções das 21?"* — 07/09/2026, ela olhando o seletor.

    A especificação da mesa trazia seis seções desde 06/09 (§4) e a página as
    ignorava: jogava as 21 numa gaveta só. A tabela mora no ROTEIRO, e a régua
    cobra que ela seja lida de lá — não seis nomes digitados nesta página.
    """
    secoes = med.secoes_do_roteiro()
    assert len(secoes) == 21, secoes
    assert len(set(secoes.values())) == 6, sorted(set(secoes.values()))
    das_21 = [t for t in med.todos_os_testes() if t.id.startswith("roteiro-")]
    assert len({t.secao for t in das_21}) == 6, {t.secao for t in das_21}
    assert all(t.secao.startswith("O roteiro ·") for t in das_21), (
        [t.secao for t in das_21 if not t.secao.startswith("O roteiro ·")])
    # E CADA UMA DAS SEIS TEM LINHA: uma seção vazia no seletor é uma gaveta
    # que ela abre para nada.
    for nome in set(secoes.values()):
        assert any(nome in t.secao for t in das_21), nome


def test_a_cor_se_le_do_aparelho_sob_o_comando_dela() -> None:
    """*"A cor exige escrita mesmo. Mas ler uma vez, sob seu comando, é o que o
    daemon faz. então por favor faz isso. é o que eu venho pedindo."*

    A leitura é a ÚNICA escrita que esta página faz, e ela não se monta aqui:
    `integrations.cor_do_plastico` é o dono, com uma função sem parâmetro para
    o payload e outra que o confere byte a byte antes de sair — porque `0x80` é
    a família em que `[1, 1]` RESETA o controle.

    A RÉGUA NÃO ESCREVE NO APARELHO: ela prova que a página PERGUNTA AO DONO em
    vez de montar o pedido, e que a leitura não roda sozinha.
    """
    fonte = pathlib.Path(med.__file__).read_text(encoding="utf-8")
    assert "cor_do_plastico.ler_pelo_cabo" in fonte, (
        "a mesa deixou de perguntar ao dono da leitura")
    # A RÉGUA LÊ O CÓDIGO, NÃO A PROSA — e esta linha é a cicatriz de 07/09:
    # a primeira versão varria o arquivo inteiro e reprovou no COMENTÁRIO que
    # avisa para não montar o pedido, porque ele cita o byte que descreve. É a
    # mesma armadilha do `BOOTSTRAP` de 05/09, e ela não é de digitação: um
    # aviso escrito bem é indistinguível do defeito para quem varre texto cru.
    codigo = _so_o_codigo(fonte)
    for proibido in ("montar_pedido", "0x80", "SET_FEATURE", "ioctl",
                     "HIDIOCSFEATURE"):
        assert proibido not in codigo, (
            f"a mesa passou a montar o pedido ela mesma (`{proibido}`) — a "
            f"trava do byte tem UM dono, e não é esta página")
    # E NÃO RODA SOZINHA: a única chamada está atrás da rota do POST.
    corpo = fonte.split("def ler_a_cor_no_aparelho", 1)[1]
    chamadas = corpo.count("ler_a_cor_no_aparelho()")
    assert chamadas == 1, (
        f"`ler_a_cor_no_aparelho` é chamada {chamadas} vezes — ela escreve no "
        f"aparelho, e escrever tem de ser ato dela, uma vez por clique")
    assert 'caminho == "/ler-cor"' in fonte


def test_a_borda_do_cartao_e_a_cor_do_plastico(pw, lar, mentira) -> None:
    """*"a borda de cada controle deve ter a borda na cor do model"*.

    E o PAPEL não pode cobri-la: a primeira volta pôs um `outline` roxo em quem
    devia reagir, e os quatro cartões ficavam roxos — a cor do plástico, que é
    o que ela usa para casar a tela com o controle na mão, sumia da moldura.
    """
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
        # e ela é a COR DA CASCA daquele modelo, perguntada ao dono
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
    """*"as bordas ou coisas a serem observadas ficam com o foco o mesmo que
    temos no mapa dos controles (…) touchpad lightbar e afins tudo isso também,
    fora motor e gatilhos tal como é no mapa"*.

    O mapa acende a peça em foco em `--pink`, e é o rosa que ela já associa a
    "olhe aqui" em toda a casa. A régua vai a peça por peça — incluindo as
    OCULTAS (motores, sensores, bateria), que são as que somem quando alguém
    mexe na folha de realce sem saber que elas existem.
    """
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
    """*"e cara o contorno não tá pintado (…) abra o playwright e mude o tipo
    de controle no mapa dos controles e veja a diferença"* — 07/09/2026.

    Ela estava certa duas vezes. O desenho é DE LINHA, e quem dá cor à linha é
    o `stroke` — a folha dos 28 pinta as ZONAS, e o contorno vivia numa segunda
    folha que só existia dentro do `mapa-do-controle.html`. A mesa emitia o
    mesmo SVG e não pintava nada.

    A CURA NÃO É COPIAR, é LER: `folha_do_desenho` vai à página que é dona das
    regras e reescreve só o endereço. A régua cobra as duas metades — que as
    regras venham de lá, e que as VARIÁVEIS venham junto (a primeira volta
    trouxe `fill:var(--led-apagado)` sem o `--led-apagado`, e os cinco LEDs de
    jogador ficaram pretos).
    """
    folha = med.folha_do_desenho(["p1", "p2"])
    assert "stroke:var(--z-casca-solida)" in folha, (
        "a folha do desenho perdeu o contorno na cor do plástico")
    # AS DUAS QUEIXAS DELA, cada uma com a regra que a responde
    assert ".sem-tinta{fill:none !important" in folha.replace(" ", " "), (
        "sem a `sem-tinta` o círculo do PS volta — *\"o do PS não tem esse "
        "círculo no meio\"*")
    # AS VARIÁVEIS VIAJAM JUNTO
    for var in ("--led-apagado", "--led-aceso", "--luz-apagada"):
        assert f"{var}:" in folha, (
            f"`{var}` é usada e não é declarada — um valor que não resolve não "
            f"herda o de trás, cai no preto")
    # E O ENDEREÇO É O DESTA PÁGINA, não o do mapa: quatro desenhos na mesma
    # página só não colidem porque cada um leva o prefixo do seu posto.
    assert "#p1-corpo" in folha and "#p2-corpo" in folha, folha[:400]
    assert "mp-" not in folha, "sobrou endereço do mapa na folha da mesa"
    # O QUE NÃO PODE VIR: o realce de LÁ, cujo gatilho é o mouse. Aqui quem
    # manda acender é o roteiro.
    assert ":hover" not in folha, "veio o realce do mapa, e ele é do ponteiro"


def test_o_desenho_da_mesa_pinta_o_contorno_como_o_mapa(pw, lar, mentira) -> None:
    """O contorno, medido: cor do plástico e ESPESSURA que se enxerga.

    A cor sozinha não bastava, e a foto provou: o `stroke-width:.42` vem em
    unidades do `viewBox` (116,68 de largura). O mapa desenha o SVG com 1160 px
    e o traço sai com 4,2 px de tela; a mesa desenhava com 190 e o traço dava
    **0,68 px**. Abaixo de um pixel o navegador não desenha linha, desenha um
    cinza fraco — e a borda de cima do touchpad sumia inteira.

    Por isso a régua mede as DUAS coisas, e a espessura em pixels de TELA.
    """
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
            # A ESPESSURA É DE TELA, e não some quando o cartão encolhe
            assert c["efeito"] == "non-scaling-stroke", (
                f"o traço voltou a escalar com o desenho: {c}")
            assert float(c["w"].rstrip("px")) >= 1.4, (
                f"o contorno é fino demais para se ver: {c}")
        pg.close()


def test_o_ps_nao_acende_o_circulo_que_ela_mandou_tirar(pw, lar, mentira) -> None:
    """*"o do PS não tem esse círculo no meio"* — 07/09/2026.

    Decisão dela de 27/08: *"Remove o circulo e Deixa só o Glifo do PS pra ser
    o Botão"*. O desenho obedece com a classe `sem-tinta`, e o REALCE a
    atropelava: com o PS marcado nascia de volta o círculo que ela mandou
    tirar. Quem acende ali é o glifo, pelo `color`.

    A cura foi no DONO (`monta.folha_de_realce`), não nesta página — o produto
    inteiro usa `apertados=` e sofria do mesmo.
    """
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
        # E O GLIFO CONTINUA ACENDENDO: tirar o círculo não pode apagar o botão
        assert medido["cor_do_grupo"] != "none", medido


def test_as_21_da_bancada_se_escolhem_num_corte_so(pw, lar, mentira) -> None:
    """*"quais desses são os mais importantes? não fez separação dos 21 mais?"*
    — 07/09/2026, ela olhando o seletor aberto.

    A separação EXISTIA: as seis seções do roteiro já vinham antes das onze do
    mapa. Mas dezessete linhas seguidas não DIZEM qual bloco é a bancada e qual
    é o acervo — a ordem é uma informação que só quem a escreveu enxerga.

    Duas coisas curam, e as duas são de leitura: os `optgroup` nomeiam os
    blocos, e uma linha fecha as 21 num corte só — *"o prioritários são os 16
    (…) faço eles e na sequência vou fazendo os demais"*.

    A RÉGUA NÃO DIGITA 21: ela pergunta ao roteiro quantas são. No dia em que
    uma linha for acrescentada à sprint, a página muda junto e esta régua não
    reprova a mudança.
    """
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

        # E O CORTE CORTA: escolher a linha deixa exatamente as do roteiro.
        pg.select_option("#secao-filtro", visto["valor_do_corte"])
        pg.wait_for_timeout(500)
        depois = pg.evaluate(
            "() => ({n: TESTES.length,"
            "        so_roteiro: TESTES.every(t => t.secao.startsWith('O roteiro'))})")
        assert depois["n"] == quantas, (
            f"o corte das {quantas} deixou {depois['n']} na tela")
        assert depois["so_roteiro"], "entrou célula do acervo no corte da bancada"
        # E O CABEÇALHO CONTA O QUE SOBROU, senão ela procura teste que não está
        assert f"1 de {quantas}" in pg.inner_text("header, main").replace(
            "\n", " ") or f"1 DE {quantas}" in pg.inner_text("body").upper(), (
            "a página não diz que agora são as do roteiro")
        pg.close()

