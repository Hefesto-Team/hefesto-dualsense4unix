#!/usr/bin/env python3
"""O lugar sem controle diz o que o desenho diz — O-LUGAR-VAZIO-DIZ-O-QUE-O-DESENHO-DIZ-01.

A QUEIXA DELA, 23/09/2026, com a foto da aba Conexões e nenhum controle na mesa:
o topo dizia «Nenhum controle» e a Gestão de Controles dizia «Sony • Player 1 •
Cosmic Red • USB» e «Sony • Player 2 • Starlight Blue • BT», com a barra rosa
do P1 acesa. Não era cache: o nome do cartão é alvo `html` (fora do molde) e a
barra é alvo `cor` (o `—` é recusado pelo CSSOM e a cor de antes FICA).

ESTA RÉGUA MEDE A TELA, e não a chave. As réguas do molde perguntavam *"o
molde alcança este campo?"* — e o `cor` era alcançado por um travessão que o
navegador joga fora. Aqui o caminho é o do tique inteiro: o pacote de verdade,
o `normalizar`, o `apagar_os_lugares_sem_dono` com a página, e o `escrever()`
DO PILOTO, recortado do fonte e rodado no `node` contra elementos de mentira
cujo `style.color` recusa o que não é cor, como o CSSOM. O ponto de partida de
cada elemento é o ARQUIVO publicado, lido pela régua do mockup — e o juiz é a
função que a `--prova-de-mockup` usa: nenhum dos dois é o leitor da cura.

AS MORDIDAS, cada uma com a saída na entrega:

* arranque a regra geral (`diz = {}` em `apagar_os_lugares_sem_dono`) —
  :func:`test_as_sete_paginas_com_a_mesa_vazia` reprova na 08 com
  `p1·nome [html] = 'Sony • Player 1 • Cosmic Red • USB'`;
* arranque só o alvo `cor` (tire-o de `ALVOS_QUE_O_DESENHO_DIZ`) — a mesma
  reprova com `p1·plastico [cor] = 'rgb(174, 51, 90)'`: a barra acesa;
* arranque a lista `CAMPOS_DO_LUGAR` do `pacote_da_pagina` —
  :func:`test_o_p2_sai_e_volta_a_desconectado_no_tique_seguinte` reprova com o
  P2 dizendo o nome do controle que saiu;
* arranque a troca do número (`_a_palavra_do_desenho` devolvendo `""` no
  molde) — :func:`test_os_quatro_cartoes_da_08_dizem_player_n_desconectado`
  reprova;
* arranque o `pagina=self.pagina` do `Piloto._tique` —
  :func:`test_o_tique_do_piloto_leva_a_pagina_ao_apagador` reprova com o P1
  dizendo `Sony • Player 1 • Cosmic Red • USB`. As outras réguas chamam a
  conta elas mesmas e ficavam verdes sem a cura do produto.
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import subprocess
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
_INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
if str(_INTERFACE) not in sys.path:
    sys.path.insert(0, str(_INTERFACE))

import pacotes
import regua_do_mockup

from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva, onde

PILOTO = _INTERFACE / "hefesto_vivo.py"

#: AS SETE PÁGINAS COM LUGAR DE CONTROLE, da tabela de quem pinta — nunca
#: digitadas. A calibração avulsa tem lugar e não é aba; ela fica de fora.
SETE = sorted(p for p in pacotes.PACOTES
              if p[:2].isdigit() and pacotes.lugares_da_pagina(p))

#: Os alvos que a simulação escreve pelo motor — os três da cura
#: (`pacotes.ALVOS_QUE_O_DESENHO_DIZ`), escritos aqui para a régua não ler pela
#: lista da cura. Os outros entram como vazio, que a prova do lugar vazio nunca
#: acusa; o `texto` é do travessão, e quem o cobra na tela é a
#: `--prova-de-mockup` do piloto, com o DOM de verdade.
SIMULADOS = frozenset({"html", "cor", "atributo"})

#: Um bloco que mira UM campo de UM lugar — a forma que o `innerHTML` do passo 0
#: do piloto troca inteiro (o chip da 03). Bloco de classe (`.ajustes.e`) não
#: alcança campo `html`, `cor` nem `atributo` em página nenhuma de hoje.
_BLOCO_DE_UM_CAMPO = re.compile(
    r'\[data-controle="(p\d+)"\]\s*\[data-campo="([^"]+)"\]')

#: Um controle de mentira, da faixa sintética da casa — há dois portões de
#: anonimato. `player_slot` 2 é o que o põe no P2.
UNIQ = "aa:bb:cc:00:00:02"
NO_P2: dict[str, Any] = {
    "uniq": UNIQ, "connected": True, "transport": "usb", "player": 2,
    "player_slot": 2, "battery_pct": 80, "is_primary": True, "inputs": {},
    "audio": {}, "speaker": {}}


# ---------------------------------------------------------------------------
# o tique, do jeito do piloto
# ---------------------------------------------------------------------------
def _contexto(controles: list[dict[str, Any]]) -> tuple[pacotes.Contexto, dict[str, str]]:
    """O `Piloto._contexto`, sem o leitor de cor e sem os externos."""
    st: dict[str, Any] = {"connected": True,
                          "controllers": [dict(c) for c in controles]}
    mesa = mesa_viva.mesa_do_estado(st, {})
    para_pref = {str(c.get("uniq") or ""): c["pref"] for c in mesa}
    ctx = pacotes.Contexto(state=st, mesa=mesa, conectados=list(st["controllers"]),
                           estados={})
    return ctx, para_pref


def _carga(pagina: str, controles: list[dict[str, Any]]) -> dict[str, Any]:
    """O que o tique manda pintar: pacote → normalizar → apagar, COM a página."""
    ctx, para_pref = _contexto(controles)
    bruto = pacotes.pacote_da_pagina(pagina, ctx)
    assert bruto is not None, f"{pagina} não tem pacote"
    carga = pacotes.normalizar(bruto, para_pref)
    apagada: dict[str, Any] = pacotes.apagar_os_lugares_sem_dono(
        carga, hefesto_vivo._com_dono(ctx), pagina=pagina)
    return apagada


# ---------------------------------------------------------------------------
# o motor, rodado no node
# ---------------------------------------------------------------------------
def _motor() -> str:
    """O `escrever()` do piloto e o que ele usa — do FONTE, recortado por marcador."""
    fonte = PILOTO.read_text(encoding="utf-8")
    i = fonte.index("  function ligado(t){")
    j = fonte.index("  // OS TRÊS VOCABULÁRIOS DE ENDEREÇO", i)
    return fonte[i:j]


_TELA = r"""
const window = {__hef: {}};
const document = {activeElement: null};
__MOTOR__
// O CSSOM DE MENTIRA: o `color` recusa CALADO o que não é cor — é o que faz o
// travessão num alvo `cor` deixar a cor de antes na tela.
const COR = /^(#[0-9a-f]{3,8}|(rgb|rgba|hsl|hsla)\(.*\)|var\(--[\w-]+\)|[a-z]+)$/i;
function Estilo(cor){ this._cor = cor || ''; this._props = {}; }
Object.defineProperty(Estilo.prototype, 'color', {
  get: function(){ return this._cor; },
  set: function(v){ const s = String(v); if(s === '' || COR.test(s)) this._cor = s; },
});
Estilo.prototype.getPropertyValue = function(n){ return this._props[n] || ''; };
Estilo.prototype.setProperty = function(n, v){ this._props[n] = String(v); };
Estilo.prototype.removeProperty = function(n){ delete this._props[n]; };
function El(e){
  this.dataset = {hefAlvo: e.alvo};
  if(e.atributo) this.dataset.hefAtributo = e.atributo;
  this.tagName = 'SPAN';
  this.children = [];
  this.firstElementChild = null;
  this.style = new Estilo(e.alvo === 'cor' ? e.inicial : '');
  this._attrs = {};
  if(e.alvo === 'atributo' && e.inicial !== '') this._attrs[e.atributo] = e.inicial;
  this._html = e.alvo === 'html' ? e.inicial : '';
}
El.prototype.getAttribute = function(n){
  return Object.prototype.hasOwnProperty.call(this._attrs, n) ? this._attrs[n] : null; };
El.prototype.setAttribute = function(n, v){ this._attrs[n] = String(v); };
El.prototype.removeAttribute = function(n){ delete this._attrs[n]; };
El.prototype.hasAttribute = function(n){
  return Object.prototype.hasOwnProperty.call(this._attrs, n); };
El.prototype.matches = function(){ return false; };
Object.defineProperty(El.prototype, 'innerHTML', {
  get: function(){ return this._html; }, set: function(v){ this._html = String(v); }});
Object.defineProperty(El.prototype, 'textContent', {
  get: function(){ return this._html; }, set: function(v){ this._html = String(v); }});
const pedido = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const els = pedido.elementos.map(function(e){ return new El(e); });
const fora = [];
for(const tique of pedido.tiques){
  for(const [i, v, bloco] of tique){
    if(bloco){ els[i]._html = String(v); continue; }
    escrever(els[i], v);
  }
  fora.push(els.map(function(el, i){
    const e = pedido.elementos[i];
    if(e.alvo === 'cor') return el.style.color;
    if(e.alvo === 'atributo') return el.getAttribute(e.atributo) || '';
    return el._html;
  }));
}
console.log(JSON.stringify(fora));
"""


def _node() -> str:
    node = shutil.which("node") or shutil.which("nodejs")
    if not node:
        pytest.skip("sem `node` nesta máquina — a régua mede o motor rodando")
    return node


def _a_tela(pagina: str, cargas: list[dict[str, Any]]
            ) -> tuple[list[regua_do_mockup._Campo], list[list[str]], str]:
    """Os campos do ARQUIVO e o que a tela mostra neles depois de cada carga.

    O vivo sai na língua da régua do mockup — `html` pelo texto, `cor` pela
    forma do navegador —, que é a mesma que a `--prova-de-mockup` compara.
    """
    texto = onde.pagina(pagina, publicado=True).read_text(encoding="utf-8")
    cravados = regua_do_mockup._campos_cravados(texto)
    simulados = [i for i, c in enumerate(cravados)
                 if c.dono in pacotes.TODOS_OS_LUGARES and c.alvo in SIMULADOS]
    elementos = []
    atributo_de: dict[int, str] = {}
    for i in simulados:
        c = cravados[i]
        nome = ""
        if c.alvo == "atributo":
            nome = _atributo_do_campo(texto, c)
            atributo_de[i] = nome
        elementos.append({"alvo": c.alvo, "atributo": nome, "inicial": c.valor})
    tiques = []
    for carga in cargas:
        # A ORDEM DO PILOTO: 0 os blocos, 1 a mesa (solta no documento, e a
        # lista se distribui na ordem), 2 as colunas de cada lugar.
        escritas: list[list[Any]] = []
        for seletor, bloco in (carga.get("blocos") or {}).items():
            achado = _BLOCO_DE_UM_CAMPO.fullmatch(str(seletor).strip())
            for n, i in enumerate(simulados):
                c = cravados[i]
                if achado and (c.dono, c.chave) == achado.groups():
                    escritas.append([n, bloco, "bloco"])
        vistos: dict[str, int] = {}
        for n, i in enumerate(simulados):
            c = cravados[i]
            if c.chave not in (carga.get("mesa") or {}):
                continue
            v = carga["mesa"][c.chave]
            k = vistos.get(c.chave, 0)
            vistos[c.chave] = k + 1
            if isinstance(v, list):
                v = v[k] if k < len(v) else ""
            if not isinstance(v, dict):
                escritas.append([n, v])
        for n, i in enumerate(simulados):
            c = cravados[i]
            campos = (carga.get("colunas") or {}).get(c.dono) or {}
            if c.chave in campos and not isinstance(campos[c.chave], (dict, list)):
                escritas.append([n, campos[c.chave]])
        tiques.append(escritas)
    r = subprocess.run(
        [_node(), "-e", _TELA.replace("__MOTOR__", _motor())],
        input=json.dumps({"elementos": elementos, "tiques": tiques}),
        capture_output=True, text=True, cwd=str(RAIZ))
    assert r.returncode == 0, f"o motor não rodou:\n{r.stderr[-2000:]}"
    brutos = json.loads(r.stdout)
    telas: list[list[str]] = []
    for bruto in brutos:
        vivos = ["" for _ in cravados]
        for n, i in enumerate(simulados):
            c, v = cravados[i], bruto[n]
            if c.alvo == "html":
                v = regua_do_mockup._so_o_texto(v)
            elif c.alvo == "cor":
                v = regua_do_mockup._cor_css(v)
            vivos[i] = v
        telas.append(vivos)
    return cravados, telas, texto


def _atributo_do_campo(texto: str, campo: regua_do_mockup._Campo) -> str:
    """O `data-hef-atributo` de um campo — lido do arquivo, pela chave."""
    achado = re.search(
        r'data-(?:campo|papel|hef)="' + re.escape(campo.chave) + r'"[^>]*?'
        r'data-hef-atributo="([^"]+)"', texto)
    if achado is None:
        pytest.fail(f"o arquivo não diz qual atributo `{campo.endereco}` escreve")
    return achado.group(1).strip().lower()


def _o_que_diz(cravados: list[regua_do_mockup._Campo], vivos: list[str],
               pref: str, chave: str) -> list[str]:
    return [v for c, v in zip(cravados, vivos, strict=True)
            if c.dono == pref and c.chave == chave]


# ---------------------------------------------------------------------------
# 1. AS SETE PÁGINAS — nenhum lugar vazio com o desenho de um lugar cheio
# ---------------------------------------------------------------------------
def test_as_sete_paginas_sao_as_sete() -> None:
    """A parametrização abaixo não pode passar por vacuidade."""
    assert SETE == ["01-jogar.html", "02-controles.html", "03-gatilhos.html",
                    "04-iluminacao.html", "05-vibracao.html", "06-navegacao.html",
                    "08-conexoes.html"], SETE


@pytest.mark.parametrize("pagina", SETE)  # (noqa-acento): nome de parâmetro
def test_as_sete_paginas_com_a_mesa_vazia(pagina: str) -> None:
    """Zero controles: nenhum dos quatro lugares mostra o que o desenho pôs
    num lugar COM controle — nem o nome, nem a cor, nem o atributo."""
    carga = _carga(pagina, [])
    cravados, (vivos,), texto = _a_tela(pagina, [carga])
    vazaram = hefesto_vivo._o_desenho_cheio_no_lugar_vazio(
        cravados, vivos, carga["vazios"], texto)
    assert not vazaram, (
        f"{pagina}: lugar SEM controle mostrando o desenho de um lugar COM "
        "controle — a foto dela de 23/09/2026:\n  " + "\n  ".join(vazaram))


@pytest.mark.parametrize("pagina", SETE)  # (noqa-acento): nome de parâmetro
def test_as_sete_paginas_com_um_controle_no_p2(pagina: str) -> None:
    """Um controle no P2: o P1, o P3 e o P4 continuam dizendo o lugar vazio."""
    carga = _carga(pagina, [NO_P2])
    cravados, (vivos,), texto = _a_tela(pagina, [carga])
    vazaram = hefesto_vivo._o_desenho_cheio_no_lugar_vazio(
        cravados, vivos, carga["vazios"], texto)
    assert not vazaram, f"{pagina}:\n  " + "\n  ".join(vazaram)


# ---------------------------------------------------------------------------
# 2. A 08 — a foto dela
# ---------------------------------------------------------------------------
PONTO = pacotes.PONTO_DO_ROTULO


def test_os_quatro_cartoes_da_08_dizem_player_n_desconectado() -> None:
    """«Player N • Desconectado» nos quatro, e nenhuma barra acesa."""
    pagina = "08-conexoes.html"
    carga = _carga(pagina, [])
    cravados, (vivos,), _ = _a_tela(pagina, [carga])
    for n in range(1, 5):
        pref = f"p{n}"
        assert _o_que_diz(cravados, vivos, pref, "nome") == [
            f"Player {n} {PONTO} Desconectado"], pref
        assert _o_que_diz(cravados, vivos, pref, "plastico") == [""], (
            f"{pref}: a barra ficou acesa com zero controles na mesa")


def test_o_p2_sai_e_volta_a_desconectado_no_tique_seguinte() -> None:
    """O P2 cheio, depois a mesa vazia: UM tique basta, sem recarregar a página.

    Medido no piloto oculto antes da cura: três segundos depois de o controle
    sair, o cartão do P2 ainda dizia o nome dele.
    """
    pagina = "08-conexoes.html"
    cheio, vazio = _carga(pagina, [NO_P2]), _carga(pagina, [])
    cravados, (com, sem), texto = _a_tela(pagina, [cheio, vazio])
    assert cheio["vazios"] == ["p1", "p3", "p4"], cheio["vazios"]
    nome_cheio = _o_que_diz(cravados, com, "p2", "nome")
    assert nome_cheio and "Desconectado" not in nome_cheio[0], nome_cheio
    for n in (1, 3, 4):
        assert _o_que_diz(cravados, com, f"p{n}", "nome") == [
            f"Player {n} {PONTO} Desconectado"]
    assert vazio["vazios"] == ["p1", "p2", "p3", "p4"]
    assert _o_que_diz(cravados, sem, "p2", "nome") == [
        f"Player 2 {PONTO} Desconectado"], (
        "o controle saiu e o cartão do P2 continuou dizendo o nome dele — o "
        "«cache» que ela fotografou")
    assert _o_que_diz(cravados, sem, "p2", "plastico") == [""]
    assert not hefesto_vivo._o_desenho_cheio_no_lugar_vazio(
        cravados, sem, vazio["vazios"], texto)


# ---------------------------------------------------------------------------
# 3. O LUGAR QUE ESVAZIA NÃO GUARDA NADA DO CONTROLE, e o que chega apaga o vazio
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pagina", SETE)  # (noqa-acento): nome de parâmetro
def test_o_que_a_regra_escreve_no_vazio_a_aba_reescreve_no_cheio(pagina: str) -> None:
    """A trava da regra: ela só escreve onde a aba escreve.

    Um campo que o desenho diz no lugar vazio e que a aba NÃO pinta quando o
    controle chega ficaria com o vazio num lugar cheio. Medido para a 06: o
    `desenho` (o colorway do SVG) não é pintado pela aba, e apagá-lo acenderia
    a regra `.ds-svg:not([data-colorway])` no controle de verdade.
    """
    vazio = _carga(pagina, [])
    cheio = _carga(pagina, [NO_P2])
    diz = pacotes.o_que_o_desenho_diz_do_lugar_vazio(pagina).get("p2", {})
    escritos = {k for k in diz if vazio["colunas"].get("p2", {}).get(k) == diz[k]}
    pintados = set(cheio["colunas"].get("p2", {}))
    blocos = pacotes._o_que_o_bloco_ja_escreveu(cheio).get("p2", set())
    assert escritos <= pintados | blocos, (
        f"{pagina}: a regra escreve {sorted(escritos - pintados - blocos)} no "
        "lugar vazio e a aba não os reescreve quando o controle chega")


def test_a_lista_do_lugar_nao_chega_a_pagina() -> None:
    """`CAMPOS_DO_LUGAR` é instrução para a conta — nunca valor de tela."""
    ctx, para_pref = _contexto([])
    bruto = pacotes.pacote_da_pagina("08-conexoes.html", ctx)
    assert bruto and pacotes.CAMPOS_DO_LUGAR in bruto, (
        "com a mesa vazia o despachante deixou de mandar o que a aba pinta — o "
        "nome `html` volta a ficar de fora")
    assert "nome" in bruto[pacotes.CAMPOS_DO_LUGAR]
    carga = pacotes.normalizar(bruto, para_pref)
    assert pacotes.CAMPOS_DO_LUGAR not in carga["mesa"]
    fora = pacotes.apagar_os_lugares_sem_dono(carga, [], pagina="08-conexoes.html")
    assert pacotes.CAMPOS_DO_LUGAR not in fora


def test_sem_a_pagina_a_conta_e_a_de_antes() -> None:
    """Quem chama sem a página recebe só o travessão — nenhum desenho."""
    carga = {"colunas": {"p1": {"nome": "Régua", "plastico": "#fff"}}}
    fora = pacotes.apagar_os_lugares_sem_dono(carga, ["p1"])
    assert fora["colunas"]["p2"] == {"nome": pacotes.TRAVESSAO,
                                     "plastico": pacotes.TRAVESSAO}


def test_o_que_a_aba_declara_vence_o_desenho() -> None:
    """A linha LEDs apagada da 04 é pedido dela que o desenho não tem."""
    carga = _carga("04-iluminacao.html", [])
    from pacotes import a04_iluminacao

    for pref in sorted(pacotes.TODOS_OS_LUGARES):
        assert carga["colunas"][pref]["luz"] == a04_iluminacao.o_lugar_vazio()["luz"]


# ---------------------------------------------------------------------------
# 4. A PALAVRA DO DESENHO — a troca do número e o que ela recusa
# ---------------------------------------------------------------------------
def test_a_troca_do_numero_so_pega_o_numero_do_jogador() -> None:
    troca = pacotes._o_numero_trocado
    assert troca('Player 3 <span class="pt">•</span> Desconectado', 3, 1) == (
        'Player 1 <span class="pt">•</span> Desconectado')
    assert troca("P3 • Desconectado", 3, 4) == "P4 • Desconectado"
    for intocado in ("#74588e", "3px", "0.3", "gc-p3", "p3-outline-filter-0", "33"):
        assert troca(intocado, 3, 1) == intocado, intocado


def test_a_palavra_do_desenho() -> None:
    palavra = pacotes._a_palavra_do_desenho
    assert palavra("cor", {3: ["#74588e"], 4: ["#e4e0d8"]})(1) == ""
    assert palavra("html", {3: ["—"], 4: ["—"]})(1) == "—"
    assert palavra("html", {3: ["Player 3 • x"], 4: ["Player 4 • x"]})(2) == "Player 2 • x"
    # exemplos diferentes em cada lugar vazio: o desenho não diz UMA coisa
    assert palavra("atributo", {3: ["galactic-purple"], 4: ["white"]})(1) == ""
    # UM lugar vazio com o número dentro não se confere — e não se adivinha
    assert palavra("html", {3: ["Cor do Player 3"]})(1) == ""
    assert palavra("html", {3: ["—"]})(1) == "—"
    # o mesmo texto com o número nos DOIS lugares é paleta, não lugar
    assert palavra("html", {3: ["Cor do Player 3"], 4: ["Cor do Player 3"]})(1) == (
        "Cor do Player 3")


# ---------------------------------------------------------------------------
# 5. A PROVA DO MOCKUP — a pergunta nova, sem janela
# ---------------------------------------------------------------------------
_PAGINA_DE_MENTIRA = """
<div data-controle="p1"><span data-campo="nome" data-hef-alvo="html">Sony <b>P1</b></span>
  <i data-campo="barra" data-hef-alvo="cor" style="color:#ae335a"></i></div>
<div data-controle="p3" data-conectado="nao">
  <span data-campo="nome" data-hef-alvo="html">P3 vazio</span>
  <i data-campo="barra" data-hef-alvo="cor"></i></div>
<div data-controle="p4" data-conectado="nao" data-campo="casca" data-hef-alvo="cor"
     style="color:#fff"><span data-campo="nome" data-hef-alvo="html">P4 vazio</span></div>
"""


def test_a_prova_acusa_o_desenho_cheio_e_poupa_o_vazio() -> None:
    """A pergunta nova da `--prova-de-mockup`, sobre uma página de mentira."""
    cravados = regua_do_mockup._campos_cravados(_PAGINA_DE_MENTIRA)
    enderecos = [c.endereco for c in cravados]
    # a tela: o P1 esvaziou e ficou com o desenho; o P4 mostra o vazio certo
    tela = {"p1·nome": "Sony P1", "p1·barra": "rgb(174, 51, 90)",
            "p3·nome": "P3 vazio", "p3·barra": "",
            "p4·casca": "rgb(255, 255, 255)", "p4·nome": "P4 vazio"}
    vivos = [tela[e] for e in enderecos]
    acusa = hefesto_vivo._o_desenho_cheio_no_lugar_vazio(
        cravados, vivos, ["p1", "p3", "p4"], _PAGINA_DE_MENTIRA)
    assert acusa == ["p1·nome [html] = 'Sony P1'",
                     "p1·barra [cor] = 'rgb(174, 51, 90)'"], acusa
    # com o P1 cheio, a mesma tela é o controle dele — nada a acusar
    assert not hefesto_vivo._o_desenho_cheio_no_lugar_vazio(
        cravados, vivos, ["p3", "p4"], _PAGINA_DE_MENTIRA)
    # o travessão e o vazio nunca são o desenho de ninguém
    limpos = ["" if "barra" in e else pacotes.TRAVESSAO for e in enderecos]
    assert not hefesto_vivo._o_desenho_cheio_no_lugar_vazio(
        cravados, limpos, ["p1", "p3", "p4"], _PAGINA_DE_MENTIRA)


def test_o_elemento_do_proprio_lugar_nao_e_cobrado() -> None:
    """O `achar()` procura DENTRO do lugar; o próprio elemento não é endereço."""
    vazios, proprios = hefesto_vivo._o_lugar_no_arquivo(_PAGINA_DE_MENTIRA)
    assert vazios == {"p3", "p4"}
    assert proprios == {("p4", "casca")}


# ---------------------------------------------------------------------------
# 6. O TIQUE DO PILOTO — a cura mora numa linha dele, e ela também morde
# ---------------------------------------------------------------------------
class _PonteQueGuarda:
    """A ponte do piloto sem WebView: guarda a pintura e devolve a contagem."""

    def __init__(self) -> None:
        self.pinturas: list[str] = []

    def perguntar(self, js: str, volta: Any) -> None:
        self.pinturas.append(js)
        volta("1", None)

    def rodar(self, js: str) -> None:
        self.pinturas.append(js)


def _tiques_do_piloto(pagina: str, mesas: list[list[dict[str, Any]]],
                      monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Roda o `Piloto._tique` DE VERDADE, uma vez por mesa, e devolve cada carga.

    Sem janela e SEM DAEMON: o estado, o contexto e os corações são dublês. O
    `XDG_RUNTIME_DIR` da suíte é o real (`tests/conftest.py`), e o que falasse
    com o socket falaria com o daemon dela — por isso nada aqui abre socket.
    """
    import types

    # O `pacotes` DO PILOTO, pelo nome longo: o `import pacotes` desta régua é
    # outro objeto de módulo, e o dublê dos corações tem de cair no do tique.
    from hefesto_dualsense4unix.interface import pacotes as pac
    monkeypatch.setattr(pac, "bater_os_coracoes", lambda *_a, **_k: None)
    agora: dict[str, Any] = {}

    def contexto(st: dict[str, Any]) -> tuple[Any, dict[str, str]]:
        mesa = mesa_viva.mesa_do_estado(st, {})
        para_pref = {str(c.get("uniq") or ""): c["pref"] for c in mesa}
        return pac.Contexto(state=st, mesa=mesa, conectados=list(st["controllers"]),
                            estados={}), para_pref

    ponte = _PonteQueGuarda()
    piloto: Any = types.SimpleNamespace(
        pronto=True, _pintura_no_ar=False, _pular=0, _pulados_por_voo=0,
        _pulados_por_custo=0, pagina=pagina, ponte=ponte,
        args=types.SimpleNamespace(prova_de_mockup=False, conta_mutacoes=0),
        _estado_do_tique=lambda: agora["st"], _contexto=contexto,
        trocas={}, tiques={}, pinturas={}, voltas=0, custos=[], custo_do_ipc=[],
        _contar_mutacoes=lambda: None)
    cargas = []
    for controles in mesas:
        agora["st"] = {"connected": True, "controllers": [dict(c) for c in controles]}
        # O PRIMEIRO TIQUE LÊ O DESENHO e pode passar do teto; o `_pular` que
        # ele deixa calaria o segundo, que é justamente o que se mede.
        piloto._pular = 0
        antes = len(ponte.pinturas)
        assert hefesto_vivo.Piloto._tique(piloto) is True
        assert len(ponte.pinturas) == antes + 1, "o tique não pintou"
        assert hefesto_vivo._json(piloto._carga_de_agora) in ponte.pinturas[-1]
        cargas.append(piloto._carga_de_agora)
    return cargas


def test_o_tique_do_piloto_leva_a_pagina_ao_apagador(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O `Piloto._tique` DE VERDADE pinta a 08 como o desenho pinta o vazio.

    AS RÉGUAS DE CIMA CHAMAM A CONTA ELAS MESMAS, com `pagina=` — e por isso
    ficavam verdes com o piloto chamando SEM a página. Medido na conferência de
    23/09/2026: arrancado o `pagina=self.pagina` do `_tique`, 82 testes das
    quatro réguas do lugar vazio passavam, e a tela voltava à foto dela.

    O caminho é o do produto inteiro: a mesa vazia, um controle no P2, e a mesa
    vazia de novo — três tiques, e a TELA simulada com o `escrever()` do piloto.

    A MORDIDA: tire `pagina=self.pagina` da chamada em `Piloto._tique` — esta
    régua reprova com o P1 mostrando o nome do desenho.
    """
    pagina = "08-conexoes.html"
    cargas = _tiques_do_piloto(pagina, [[], [NO_P2], []], monkeypatch)
    cravados, telas, texto = _a_tela(pagina, cargas)
    esperado_vazio = [f"Player {n} {PONTO} Desconectado" for n in range(1, 5)]
    for rotulo, vivos, carga in zip(("vazia", "P2", "P2 saiu"), telas, cargas, strict=True):
        vazaram = hefesto_vivo._o_desenho_cheio_no_lugar_vazio(
            cravados, vivos, carga["vazios"], texto)
        assert not vazaram, f"{rotulo}:\n  " + "\n  ".join(vazaram)
        for n in range(1, 5):
            pref = f"p{n}"
            if pref in carga["vazios"]:
                assert _o_que_diz(cravados, vivos, pref, "nome") == [
                    esperado_vazio[n - 1]], (rotulo, pref)
                assert _o_que_diz(cravados, vivos, pref, "plastico") == [""], (
                    f"{rotulo}: a barra do {pref} ficou acesa sem controle")
    assert cargas[1]["vazios"] == ["p1", "p3", "p4"], cargas[1]["vazios"]
    assert cargas[2]["vazios"] == ["p1", "p2", "p3", "p4"], cargas[2]["vazios"]
