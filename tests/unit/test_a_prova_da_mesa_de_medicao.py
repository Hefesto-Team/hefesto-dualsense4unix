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
        pg.fill("#o-que-eu-vi", "so o P3 endureceu")
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
