"""O lugar sem controle tem UMA leitura nos quatro lugares — e a mesa vazia não guarda o desenho.

**As três fotos dela, 21/09/2026**, com ZERO controles na mesa:

1. *"dois controles conectados quando não tem nenhum"* — a fita de cima dizia
   `P1 · Cosmic Red · USB` e `P2 · Starlight Blue · BT`, os dois do desenho,
   ao lado de `0 controles`. O piloto devolvia `""` com a mesa vazia e a fita
   ficava como o arquivo publicado a trouxe.
2. *"os leds na linha dos leds do p3,p4 tem que aparecerem mas não aparecerem
   ligados como o p1 e o p2"* — a linha LEDs da Iluminação ACESA em azul e
   vermelho no P1 e no P2 (o alvo `html` fica fora do travessão), e um `—`
   seco no P3 e no P4.
3. *"p1,p2 tão diferentes do p3 e p4"* — o cartão da Navegação dizendo
   `P1 • P1 • Desconectado` com `● USB • Navega o PC` em verde, e o P3 e o P4
   `P3 • Desconectado` com `—`. E o rótulo do lugar que NASCE vazio saía
   `P3•Desconectado`, espremido, ao lado de `P1 • Desconectado`.

**A FAMÍLIA É A QUE ESTA CASA MAIS PAGA:** o lugar que o desenho publica como
OCUPADO e que a mesa esvazia fica com o que o desenho escreveu, onde a pintura
não alcança. A cura tem três peças, e cada teste abaixo morde uma:

* `pacotes.LUGAR_VAZIO` — a aba declara o que o lugar vazio mostra onde o
  travessão não chega, e o despachante aplica nos quatro;
* `pacotes.MARCAS_DO_LUGAR` — a classe que é de UM lugar (o verde de quem
  navega) acende nele e apaga nos outros, pelo passo `1d` do piloto;
* o `escrever()` do piloto reescreve o texto IGUAL quando os filhos são só o
  separador `•`, para os quatro rótulos terem a mesma forma.

AS MORDIDAS, uma por teste, estão escritas em cada docstring.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
_INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
if str(_INTERFACE) not in sys.path:
    sys.path.insert(0, str(_INTERFACE))

import monta
import pacotes
from pacotes import a04_iluminacao, a06_navegacao

from hefesto_dualsense4unix.interface import hefesto_vivo

PILOTO = _INTERFACE / "hefesto_vivo.py"
LUGARES = sorted(pacotes.TODOS_OS_LUGARES)
#: AS DEZ ABAS, da tabela que diz quem pinta cada página — nunca digitadas.
ABAS = sorted(p for p in pacotes.PACOTES if p[:2].isdigit())

#: Um controle de mentira, da faixa sintética da casa — há dois portões de
#: anonimato e eles não perdoam.
UNIQ = "aa:bb:cc:00:00:01"
PRIMARIO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
            "battery_pct": 90, "is_primary": True, "inputs": {}, "audio": {},
            "speaker": {}}
MESA_DE_UM = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
               "via": "USB", "cor": "", "mascara": "DualSense"}]


def _mesa_vazia() -> pacotes.Contexto:
    return pacotes.Contexto(state={"connected": True}, mesa=[], conectados=[],
                            estados={})


def _o_que_chega_a_tela(pagina: str, ctx: pacotes.Contexto,
                        para_pref: dict[str, str] | None = None) -> dict:
    """O caminho do tique, na ordem do piloto: pacote → normalizar → apagar."""
    bruto = pacotes.pacote_da_pagina(pagina, ctx)
    assert bruto is not None, f"{pagina} não tem pacote"
    carga = pacotes.normalizar(bruto, para_pref or {})
    com_dono = sorted((para_pref or {}).values())
    return pacotes.apagar_os_lugares_sem_dono(carga, com_dono)


# ---------------------------------------------------------------------------
# 1. A FITA DA MESA VAZIA
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("arquivo", ABAS)
def test_a_fita_da_mesa_vazia_troca_o_desenho(arquivo: str) -> None:
    """Zero controles, zero chips, zero rótulo — e a fita É repintada.

    O RÓTULO SAIU EM 22/09/2026, pedido dela: *"quando não tiver controle Não
    Aparece o selecionar:"*. Ele sobrava sozinho, apontando para nada.

    A MORDIDA: devolva o `if not mesa: return ""` ao `hefesto_vivo._fita` e
    este teste reprova nas dez: `""` é o piloto pulando a pintura, e a tela
    fica com os dois chips do desenho. Tire o `if lista` do rótulo em
    `monta.fita` e a terceira asserção reprova nas dez.
    """
    fita = hefesto_vivo._fita([], arquivo)
    assert 'class="fita' in fita, (
        f"{arquivo}: com a mesa vazia a fita não foi emitida — o piloto pula a "
        "pintura e a tela fica com `P1 · Cosmic Red · USB` do desenho")
    assert 'class="chip' not in fita, f"{arquivo}: a fita vazia inventou chip:\n{fita}"
    assert "Selecionar" not in fita, (
        f"{arquivo}: sem controle nenhum o `Selecionar:` voltou a sobrar sozinho:\n{fita}")


def test_a_fita_da_mesa_vazia_cobre_as_dez() -> None:
    """A parametrização acima não pode passar por vacuidade."""
    assert len(ABAS) == 10, ABAS
    fita = hefesto_vivo._fita([], "01-jogar.html")
    assert fita and "Cosmic Red" not in fita and "Starlight Blue" not in fita


# ---------------------------------------------------------------------------
# 2. O CONTRATO DO LUGAR VAZIO, no despachante
# ---------------------------------------------------------------------------
def test_o_lugar_vazio_declarado_chega_aos_tres_vazios_e_nao_ao_ocupado() -> None:
    """O que a aba declara vale em TODO lugar sem dono, e só neles.

    A MORDIDA: apague o `colunas[pref].update(...)` de
    `pacotes.apagar_os_lugares_sem_dono` — os três lugares vazios voltam a
    receber só o travessão, e o desenho do mockup fica neles.
    """
    carga = {"colunas": {"p1": {"luz": "VIVO", "brilho": "80%"}},
             pacotes.LUGAR_VAZIO: {"luz": "APAGADO"}}
    fora = pacotes.apagar_os_lugares_sem_dono(carga, ["p1"])
    assert fora["colunas"]["p1"] == {"luz": "VIVO", "brilho": "80%"}
    for pref in ("p2", "p3", "p4"):
        assert fora["colunas"][pref]["luz"] == "APAGADO", pref
        assert fora["colunas"][pref]["brilho"] == pacotes.TRAVESSAO, pref
    assert pacotes.LUGAR_VAZIO not in fora, (
        "a chave do lugar vazio viajou até a página — ela é instrução para o "
        "despachante, não valor de tela")


def test_o_lugar_vazio_vence_a_frase_padrao_da_identidade() -> None:
    """A 06 escreve só o NOME no `identidade`; a frase-padrão traz o número.

    Sem a precedência o cartão dizia `P1 • P1 • Desconectado`.
    """
    carga = {"colunas": {"p1": {"identidade": "Régua"}},
             pacotes.LUGAR_VAZIO: {"identidade": pacotes.SEM_NINGUEM_AQUI}}
    fora = pacotes.apagar_os_lugares_sem_dono(carga, ["p1"])
    assert fora["colunas"]["p2"]["identidade"] == pacotes.SEM_NINGUEM_AQUI


def test_o_bloco_da_aba_ganha_do_lugar_vazio() -> None:
    """Não se escreve duas vezes no mesmo elemento — o bloco já disse."""
    seletor = '[data-controle="p3"] [data-campo="luz"]'
    carga = {"colunas": {"p1": {"luz": "VIVO"}}, "blocos": {seletor: "<b>x</b>"},
             pacotes.LUGAR_VAZIO: {"luz": "APAGADO"}}
    fora = pacotes.apagar_os_lugares_sem_dono(carga, ["p1"])
    assert "luz" not in fora["colunas"]["p3"]
    assert fora["colunas"]["p2"]["luz"] == "APAGADO"


def test_o_normalizar_leva_o_vazio_e_traduz_as_marcas() -> None:
    """As duas chaves são `dict` na raiz — e o laço do `normalizar` come `dict`.

    A MORDIDA: apague o bloco das duas chaves no fim do `normalizar` e este
    teste reprova; na tela, o lugar vazio volta ao desenho e o verde de quem
    navega volta a ficar cravado no P1.
    """
    bruto = {"colunas": {UNIQ: {"x": "1"}},
             pacotes.LUGAR_VAZIO: {"luz": "APAGADO", "estrutura": {"n": 1}},
             pacotes.MARCAS_DO_LUGAR: {"navega": [UNIQ], "outra": []}}
    fora = pacotes.normalizar(bruto, {UNIQ: "p2"})
    assert fora[pacotes.LUGAR_VAZIO] == {"luz": "APAGADO"}
    assert fora[pacotes.MARCAS_DO_LUGAR] == {"navega": ["p2"], "outra": []}
    assert "luz" not in fora["mesa"] and "navega" not in fora["mesa"]


def test_pacote_sem_as_chaves_nao_ganha_chave_nova() -> None:
    """As nove abas que não declaram nada saem do `normalizar` como antes."""
    fora = pacotes.normalizar({"colunas": {}, "mesa": {"a": 1}}, {})
    assert set(fora) == {"mesa", "colunas"}


# ---------------------------------------------------------------------------
# 3. A ILUMINAÇÃO — os LEDs aparecem, e não aparecem ligados
# ---------------------------------------------------------------------------
def test_as_cinco_lampadas_do_lugar_vazio_estao_todas_apagadas() -> None:
    """`monta.luzinhas(0)` desenha as cinco e não acende nenhuma.

    A MORDIDA: devolva `luzinhas` a `PADRAO_JOGADOR[jogador]` — o `0` levanta
    `KeyError`, o `desenho_da_luz` o engole e o lugar vazio fica SEM as cinco
    lâmpadas (o `.pad` vazio), que é a linha que ela pediu para aparecer.
    """
    html = monta.luzinhas(0)
    assert html.count("<i") == 5, html
    assert 'class="on"' not in html, html


def test_a_linha_leds_do_lugar_vazio_e_o_desenho_apagado() -> None:
    """As duas tiras apagadas e as cinco lâmpadas desenhadas."""
    luz = a04_iluminacao.o_lugar_vazio()["luz"]
    assert luz.count("tira-luz") == 2, luz
    assert luz.count(a04_iluminacao.TIRA_APAGADA) == 2, (
        "uma das tiras do lugar vazio saiu ACESA — é a queixa dela de volta")
    assert luz.count("<i") == 5 and 'class="on"' not in luz, luz


def test_os_quatro_lugares_vazios_da_04_mostram_a_mesma_coisa() -> None:
    """Zero controles: o P1 e o P2 (que o desenho publica ocupados) e o P3 e o
    P4 (que ele publica vazios) recebem a MESMA linha LEDs e a MESMA linha
    Jogador. A MORDIDA: tire o `LUGAR_VAZIO` do `pacote()` da 04 e o P1 volta
    a mostrar as tiras acesas do mockup — esta régua acusa o campo ausente.
    """
    carga = _o_que_chega_a_tela("04-iluminacao.html", _mesa_vazia())
    esperado = a04_iluminacao.o_lugar_vazio()
    for pref in LUGARES:
        coluna = carga["colunas"][pref]
        for campo, valor in esperado.items():
            assert coluna.get(campo) == valor, (
                f"{pref}·{campo} do lugar vazio não é o desenho apagado")


# ---------------------------------------------------------------------------
# 4. A NAVEGAÇÃO — o cartão vazio é um só, e o verde é de quem navega
# ---------------------------------------------------------------------------
def test_os_quatro_cartoes_vazios_da_06_sao_iguais() -> None:
    """`P{n} • Desconectado` e `—`, nos quatro — nem `P1 • P1 • …`, nem a
    bolinha verde de `Navega o PC`. A MORDIDA: tire o `LUGAR_VAZIO` do
    `pacote()` da 06 e o P1 volta a dizer o número duas vezes.
    """
    carga = _o_que_chega_a_tela("06-navegacao.html", _mesa_vazia())
    for pref in LUGARES:
        coluna = carga["colunas"][pref]
        assert coluna.get("identidade") == pacotes.SEM_NINGUEM_AQUI, (pref, coluna)
        assert coluna.get("navega") == pacotes.TRAVESSAO, (pref, coluna)
    assert carga[pacotes.MARCAS_DO_LUGAR] == {"navega": []}, (
        "com a mesa vazia algum cartão ficou com o verde de quem navega")


def test_o_verde_vai_para_o_primario() -> None:
    """Com um controle primário, a marca é dele — e o lugar dele é o do tique."""
    ctx = pacotes.Contexto(state={"connected": True}, mesa=MESA_DE_UM,
                           conectados=[dict(PRIMARIO)], estados={})
    carga = _o_que_chega_a_tela("06-navegacao.html", ctx, {UNIQ: "p1"})
    assert carga[pacotes.MARCAS_DO_LUGAR] == {"navega": ["p1"]}
    assert carga["colunas"]["p1"]["navega"] == a06_navegacao.linha_do_cartao("USB", True)
    assert a06_navegacao.BOLINHA in carga["colunas"]["p1"]["navega"], (
        "o primário voltou sem a bolinha — era o que a linha em texto fazia "
        "depois de o controle sair e voltar")


# ---------------------------------------------------------------------------
# 5. O PILOTO, rodado no `node` — a régua mede o ATO, não a palavra
# ---------------------------------------------------------------------------
def _trecho(abre: str, fecha: str) -> str:
    fonte = PILOTO.read_text(encoding="utf-8")
    i = fonte.index(abre)
    return fonte[i:fonte.index(fecha, i)]


def _node(roteiro: str, *args: str) -> dict:
    node = shutil.which("node") or shutil.which("nodejs")
    if not node:
        pytest.skip("sem `node` nesta máquina — a régua mede o JS rodando")
    r = subprocess.run([node, "-e", roteiro, "--", *args],
                       capture_output=True, text=True, cwd=str(RAIZ))
    assert r.returncode == 0, f"o trecho do piloto não roda:\n{r.stderr}"
    return json.loads(r.stdout)


_DOM_DAS_MARCAS = """
function Lugar(pref, classes){
  const cls = new Set(classes);
  this.classList = {
    contains: function(c){ return cls.has(c); },
    toggle: function(c, quer){ if(quer) cls.add(c); else cls.delete(c); },
  };
  this._cls = cls;
}
const inicial = JSON.parse(process.argv[1]);
const p = JSON.parse(process.argv[2]);
const todos = {};
for(const [pref, classes] of Object.entries(inicial)) todos[pref] = new Lugar(pref, classes);
const document = {
  querySelectorAll: function(sel){
    const m = /\\[data-controle="([^"]+)"\\]/.exec(sel);
    return m && todos[m[1]] ? [todos[m[1]]] : [];
  }
};
let n = 0;
__TRECHO__
const fora = {};
for(const [pref, el] of Object.entries(todos)) fora[pref] = Array.from(el._cls).sort();
console.log(JSON.stringify({lugares: fora, n: n}));
"""


def test_o_passo_1d_move_o_verde_para_quem_navega() -> None:
    """O desenho crava `navega` no P1; a marca diz P2 — o verde muda de lugar.

    A MORDIDA: apague o passo `1d` do piloto e o P1 continua verde, o P2 não.
    """
    roteiro = _DOM_DAS_MARCAS.replace("__TRECHO__", _trecho(
        "    // 1d. AS MARCAS DO LUGAR", "    // 2. OS CAMPOS POR CONTROLE"))
    inicial = {"p1": ["nav-ctl", "navega"], "p2": ["nav-ctl"],
               "p3": ["nav-ctl", "vazia"], "p4": ["nav-ctl", "vazia"]}
    fora = _node(roteiro, json.dumps(inicial),
                 json.dumps({"marcas": {"navega": ["p2"]}}))
    assert "navega" not in fora["lugares"]["p1"]
    assert "navega" in fora["lugares"]["p2"]
    assert fora["lugares"]["p3"] == ["nav-ctl", "vazia"], (
        "o passo tocou uma classe que o pacote não nomeou")
    assert fora["n"] == 2

    parado = _node(roteiro, json.dumps({"p1": ["navega"], "p2": [], "p3": [], "p4": []}),
                   json.dumps({"marcas": {"navega": ["p1"]}}))
    assert parado["n"] == 0, "a marca que já está certa foi reescrita — a tela samba"


_DOM_DO_ESCREVER = """
function Filho(classe, comFilho){
  const cls = new Set([classe]);
  this.classList = {contains: function(c){ return cls.has(c); }};
  this.firstElementChild = comFilho ? {} : null;
}
function Rotulo(texto, filhos){
  this.dataset = {};
  this._texto = texto;
  this.children = filhos;
  this.escrito = 0;
}
Object.defineProperty(Rotulo.prototype, 'textContent', {
  get: function(){ return this._texto; },
  set: function(v){ this._texto = v; this.children = []; this.escrito += 1; },
});
Object.defineProperty(Rotulo.prototype, 'firstElementChild', {
  get: function(){ return this.children[0] || null; },
});
const window = {__hef: {}};
const document = {activeElement: null};
__TRECHO__
const casos = JSON.parse(process.argv[1]);
const fora = [];
for(const c of casos){
  const el = new Rotulo(c.texto, c.filhos.map(function(f){ return new Filho(f, false); }));
  const n1 = escrever(el, c.texto);
  const n2 = escrever(el, c.texto);
  fora.push({n1: n1, n2: n2, filhos: el.children.length});
}
console.log(JSON.stringify(fora));
"""


def test_o_rotulo_igual_com_o_ponto_por_dentro_e_reescrito_uma_vez() -> None:
    """`P3 <span class="pt">•</span> Desconectado` vira texto uma vez, e só.

    A MORDIDA: tire o `|| so_o_ponto` do `escrever()` e o primeiro caso volta
    a `n1 = 0` — o rótulo do lugar que nasce vazio fica espremido.
    """
    roteiro = _DOM_DO_ESCREVER.replace("__TRECHO__", _trecho(
        "  function escrever(el, v){", "  // OS TRÊS VOCABULÁRIOS DE ENDEREÇO"))
    casos = [
        {"texto": "P3 • Desconectado", "filhos": ["pt"]},
        {"texto": "USB • Navega o PC", "filhos": ["bolinha", "pt"]},
        {"texto": "—", "filhos": []},
    ]
    so_o_ponto, com_bolinha, sem_filho = _node(roteiro, json.dumps(casos))
    assert so_o_ponto == {"n1": 1, "n2": 0, "filhos": 0}, so_o_ponto
    assert com_bolinha == {"n1": 0, "n2": 0, "filhos": 2}, (
        "o texto igual apagou a bolinha — um filho que o texto não devolve")
    assert sem_filho == {"n1": 0, "n2": 0, "filhos": 0}, sem_filho
