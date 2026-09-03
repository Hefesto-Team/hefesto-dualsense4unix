#!/usr/bin/env python3
"""O cartão de um controle que CHEGA reabre — e a marca deixa de ser de mão única.

QUEBRA-CARTAO-QUE-NAO-REABRE-01, achada em 03/09/2026 pela leva que clicou as
dez abas como usuária. O piloto tinha um passo `1b` que FECHA o cartão de um
lugar sem dono — `data-conectado="nao"` e a classe `off` — e não tinha o passo
simétrico. Medido no fonte: duas ocorrências de `classList.add('off')` e
`dataset.conectado = 'nao'`, ZERO de `remove` ou de `'sim'`.  (noqa-acento)

O QUE ISSO FAZIA COM ELA: bastava um controle sair e voltar — ou ligar o segundo
controle com a aba já aberta. O cabeçalho passava a contar `2 controles`, o
pacote mandava a coluna inteira do P2 com bateria, cor e bateria, e o cartão
continuava fechado: **24 px de altura contra os 358 de um cartão aberto**. O
dado dela chegava e ficava invisível. Só recarregar a página desfazia.

POR QUE O DESENHO NÃO RESOLVIA: o P3 e o P4 nascem com a marca cravada no HTML,
por decisão dela de 31/08. Uma marca que o HTML crava e o produto só sabe
acrescentar é uma marca de mão única.

**ESTA RÉGUA RODA O JS, e não o lê.** O passo `1b`/`1c` é extraído do
`hefesto_vivo.py` e executado no `node` contra um DOM de mentira. Medir o TEXTO
do piloto seria a forma exata do defeito que esta casa mais paga: *a régua
confunde a PALAVRA com o ATO* — um `grep` por `remove('off')` daria verde no dia
em que alguém escrevesse a linha dentro de um `if` que nunca corre.

A MORDIDA: apague o bloco `1c` do piloto (ou o `carga["ocupados"]` do pacote) e
:func:`test_o_cartao_fechado_reabre_quando_o_controle_volta` reprova.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

#: OS MARCADORES DO TRECHO, e eles são os comentários do próprio piloto. Recortar
#: por número de linha faria a régua envelhecer no primeiro `import` novo.
ABRE = "    // 1b. OS LUGARES VAZIOS"
FECHA = "    // 2. OS CAMPOS POR CONTROLE"


def _trecho_do_piloto() -> str:
    """Os passos 1b e 1c, do FONTE — nunca uma cópia dentro deste arquivo."""
    fonte = PILOTO.read_text(encoding="utf-8")
    i = fonte.index(ABRE)
    j = fonte.index(FECHA, i)
    return fonte[i:j]


#: O DOM DE MENTIRA. Ele implementa só o que o trecho usa — `querySelectorAll`
#: por `[data-controle="pN"]`, `dataset` e `classList` —, e é de propósito:
#: um DOM completo esconderia, atrás de mil comportamentos, qual deles a cura
#: precisa. O que ele devolve no fim é o estado de cada lugar, para o Python ler.
_DOM = """
function Elemento(controle, fechado){
  this.dataset = {controle: controle};
  this._cls = new Set();
  // O LUGAR CHEIO NASCE `sim`, como no HTML das abas 01, 03, 04 e 06 — e a
  // string `nada` é o TERCEIRO estado, o das abas 02, 05 e 08, cujo lugar
  // cheio nasce SEM o atributo. Os três precisam ser distinguíveis aqui,
  // senão a régua nunca vê o caso que o DOM vivo mostrou.
  if(fechado === 'nada'){ /* sem data-conectado, como nas abas 02/05/08 */ }
  else if(fechado){ this.dataset.conectado = 'nao';  // noqa-acento: atributo
    this._cls.add('off'); }
  else { this.dataset.conectado = 'sim'; }
  const cls = this._cls;
  this.classList = {
    contains: function(c){ return cls.has(c); },
    add: function(c){ cls.add(c); },
    remove: function(c){ cls.delete(c); },
  };
}
const LUGARES = JSON.parse(process.argv[1]);
const p = JSON.parse(process.argv[2]);
const todos = {};
for(const [pref, fechado] of Object.entries(LUGARES)){
  todos[pref] = new Elemento(pref, fechado);
}
const document = {
  querySelectorAll: function(sel){
    const m = /\\[data-controle="([^"]+)"\\]/.exec(sel);
    const el = m ? todos[m[1]] : null;
    return el ? [el] : [];
  }
};
let n = 0;
__TRECHO__
const fora = {};
for(const [pref, el] of Object.entries(todos)){
  fora[pref] = {conectado: el.dataset.conectado || null,
                off: el._cls.has('off')};
}
console.log(JSON.stringify({lugares: fora, pintados: n}));
"""


def _rodar(lugares: dict[str, bool], carga: dict) -> dict:
    """Roda o trecho do piloto no `node` e devolve o estado de cada lugar.

    :param lugares: prefixo -> o cartão começa FECHADO?
    :param carga: o que o pacote manda (`vazios` e `ocupados`).
    """
    node = shutil.which("node") or shutil.which("nodejs")
    if not node:
        pytest.skip("sem `node` nesta máquina — a régua mede o JS rodando")
    roteiro = _DOM.replace("__TRECHO__", _trecho_do_piloto())
    r = subprocess.run(
        [node, "-e", roteiro, "--", json.dumps(lugares), json.dumps(carga)],
        capture_output=True, text=True, cwd=str(RAIZ))
    assert r.returncode == 0, f"o trecho do piloto não roda:\n{r.stderr}"
    return json.loads(r.stdout)


def test_o_cartao_fechado_reabre_quando_o_controle_volta() -> None:
    """É O DEFEITO. O P2 fechou numa volta; na volta seguinte ele tem dono.

    Sem o passo `1c` o cartão fica `data-conectado="nao"` para sempre, e é o que
    ela via: o cabeçalho contando o controle e o cartão em 24 px.
    """
    fora = _rodar({"p1": False, "p2": True},
                  {"vazios": [], "ocupados": ["p1", "p2"]})
    assert fora["lugares"]["p2"] == {"conectado": "sim", "off": False}, (
        "o cartão do P2 não reabriu — o dado do controle que chegou continua "
        f"invisível: {fora['lugares']['p2']}")


def test_o_lugar_sem_dono_continua_fechando() -> None:
    """A metade que já existia não pode morrer com a cura nova."""
    fora = _rodar({"p1": False, "p2": False},
                  {"vazios": ["p2"], "ocupados": ["p1"]})
    assert fora["lugares"]["p2"] == {"conectado": "nao", "off": True}  # noqa-acento: valor de atributo
    assert fora["lugares"]["p1"]["off"] is False


def test_o_cartao_ja_aberto_nao_conta_pintura() -> None:
    """Reabrir o que já está aberto não pode somar ao contador de pintura.

    O `n` é o que a régua do mockup lê para dizer "o produto escreveu aqui".
    Somar a cada tique sobre um cartão que ninguém mexeu faria o número subir
    para sempre — é o defeito 2 da lista de mordidas do
    `test_o_lugar_vazio_para_de_mostrar_o_desenho`, repetido.
    """
    fora = _rodar({"p1": False}, {"vazios": [], "ocupados": ["p1"]})
    assert fora["pintados"] == 0, (
        f"reabrir um cartão já aberto somou {fora['pintados']} ao contador")


def test_o_lugar_cheio_sem_o_atributo_ganha_a_marca() -> None:
    """O TERCEIRO ESTADO, medido no DOM vivo em 03/09/2026.

    Nas abas `02-controles`, `05-vibracao` e `08-conexoes` o lugar CHEIO nasce
    sem `data-conectado` nenhum. A primeira versão do passo `1c` só trocava um
    valor pelo outro, e os três ficavam em `null` para sempre — a folha não tem
    como vestir de conectado um lugar sobre o qual a tela não afirma nada.

    O ensaio que pegou isto imprimia `?` nas três colunas, e o `?` era a
    ausência do atributo, não um erro de leitura.
    """
    fora = _rodar({"p1": "nada"}, {"vazios": [], "ocupados": ["p1"]})
    assert fora["lugares"]["p1"]["conectado"] == "sim", (
        "o lugar cheio sem o atributo não ganhou a marca: "
        f"{fora['lugares']['p1']}")


def test_sem_ocupados_nada_reabre() -> None:
    """Uma carga velha, sem a chave nova, não pode explodir nem reabrir sozinha.

    O `p.ocupados || []` é o que segura isto: uma aba que ainda não passe pelo
    `apagar_os_lugares_sem_dono` continua funcionando como antes.
    """
    fora = _rodar({"p1": True}, {"vazios": []})
    assert fora["lugares"]["p1"] == {"conectado": "nao", "off": True}  # noqa-acento: valor de atributo


def test_o_pacote_diz_quem_tem_dono() -> None:
    """A outra metade: `apagar_os_lugares_sem_dono` emite `ocupados`.

    E ELE VEM DA MESA, não das colunas. O `com_dono` é a lista de `pN` que têm
    aparelho agora, perguntada a `hefesto_vivo._com_dono(ctx)`.
    """
    from hefesto_dualsense4unix.interface.pacotes import apagar_os_lugares_sem_dono

    carga = apagar_os_lugares_sem_dono(
        {"colunas": {"p1": {"bateria": "88%"}, "*": {"bateria": ""}}},
        com_dono=["p1"])
    assert carga["ocupados"] == ["p1"], carga.get("ocupados")
    assert carga["vazios"] == ["p2", "p3", "p4"]


def test_ter_coluna_nao_e_ter_dono() -> None:
    """A REGRESSÃO DE 03/09/2026, e ela é a razão de o `com_dono` existir.

    A primeira versão fazia `ocupados = set(colunas)`. Medido no DOM VIVO com
    UM controle na bancada: a `03-gatilhos` emite coluna para os QUATRO lugares
    — as vazias levam travessão de propósito, para as barras de ajuste nascerem
    no lugar —, e p3 e p4 entraram em `ocupados`. O passo `1c` os REABRIU, e a
    tela passou a dizer `data-conectado="sim"` em dois lugares vazios.

    É a oitava aparição do defeito que esta casa já nomeou — *a tela afirmando
    um controle que não está na mesa* — e desta vez quem a introduziu foi a
    cura do defeito anterior.
    """
    from hefesto_dualsense4unix.interface.pacotes import apagar_os_lugares_sem_dono

    # a carga EXATA da `03-gatilhos`: coluna para os quatro, dono só do p1
    carga = apagar_os_lugares_sem_dono(
        {"colunas": {"p1": {"modo": "Off"}, "p2": {"modo": "—"},
                     "p3": {"modo": "—"}, "p4": {"modo": "—"},
                     "*": {"modo": ""}}},
        com_dono=["p1"])
    assert carga["ocupados"] == ["p1"], (
        "um lugar que só recebeu COLUNA entrou em `ocupados` — o piloto vai "
        f"reabrir cartão vazio: {carga['ocupados']}")


def test_sem_a_mesa_nada_reabre() -> None:
    """Sem `com_dono`, o caminho antigo — e ele é o SEGURO.

    Nenhum lugar reabre, que é o comportamento anterior à cura. A tela pode
    ficar atrasada; nunca mentindo a mais. Um `com_dono` opcional que
    ADIVINHASSE a mesa seria a porta pela qual a regressão voltaria.
    """
    from hefesto_dualsense4unix.interface.pacotes import apagar_os_lugares_sem_dono

    carga = apagar_os_lugares_sem_dono(
        {"colunas": {"p1": {"x": "1"}, "p3": {"x": "—"}, "*": {"x": ""}}})
    assert carga["ocupados"] == []


def test_o_com_dono_do_piloto_le_a_mesa() -> None:
    """`_com_dono(ctx)` traduz os conectados em `pN` pela mesa.

    Sem esta prova a função poderia devolver `uniq` cru — e o piloto procuraria
    `[data-controle="14:3a:…"]`, que não casa com elemento nenhum. Falha
    CALADA: nada reabre, e a régua do pacote continua verde.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo
    from hefesto_dualsense4unix.interface import pacotes

    ctx = pacotes.Contexto(
        state={},
        mesa=[{"uniq": "aa", "pref": "p1"}, {"uniq": "bb", "pref": "p2"},
              {"uniq": "cc", "pref": "p3"}],
        conectados=[{"uniq": "aa"}, {"uniq": "cc"}],
        estados={})
    assert hefesto_vivo._com_dono(ctx) == ["p1", "p3"]


def test_o_com_dono_ignora_quem_a_mesa_nao_conhece() -> None:
    """Um conectado sem lugar na mesa não inventa endereço.

    Acontece de verdade na janela entre o controle chegar e a mesa remontar. O
    certo é ficar de fora — reabrir um `pN` adivinhado abriria o cartão errado.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo
    from hefesto_dualsense4unix.interface import pacotes

    ctx = pacotes.Contexto(state={}, mesa=[{"uniq": "aa", "pref": "p1"}],
                           conectados=[{"uniq": "aa"}, {"uniq": "zz"}],
                           estados={})
    assert hefesto_vivo._com_dono(ctx) == ["p1"]


def test_ocupados_e_vazios_nunca_se_cruzam() -> None:
    """Um lugar em AMBAS as listas faria o piloto fechar e abrir no mesmo tique.

    A ordem dos passos decidiria o resultado, e isso é um defeito que só aparece
    depois de alguém trocar duas linhas de lugar.
    """
    from hefesto_dualsense4unix.interface.pacotes import apagar_os_lugares_sem_dono

    for vivas in ([], ["p1"], ["p1", "p3"], ["p1", "p2", "p3", "p4"]):
        carga = apagar_os_lugares_sem_dono(
            {"colunas": {p: {"x": "1"} for p in vivas} | {"*": {"x": ""}}},
            com_dono=vivas)
        assert not set(carga["ocupados"]) & set(carga["vazios"]), (
            f"com {vivas} vivas, um lugar caiu nas duas listas: {carga}")
        assert carga["ocupados"] == sorted(vivas), f"com {vivas}: {carga}"
