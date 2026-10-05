"""O aparelho que o plano não sabe arrumar fica onde está — nas duas gêmeas do motor.

AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01 (04/10/2026), item 6, absorvido da
AS-SUGESTOES-NAO-MANDAM-PARA-ENTRADA-NENHUMA-01: um pendrive, uma placa de captura ou um Wi-Fi que
ninguém classificou tem classe fora de ``ORDEM_DE_DECISAO``. Antes, o plano o ignorava, a entrada
dele valia como livre, outro aparelho a recebia e o mapa dizia «sai daqui» sem destino. Como cada
cartão de dica leva o botão «Mostrar a entrada boa», nenhum cartão pode apontar para entrada
nenhuma.

TUDO É DE MENTIRA: a mesa do mockup (``tests/unit/mesa_do_mockup``) mais um pendrive sem classe na
entrada 2.

AS MORDIDAS: tirar ``_o_que_o_plano_nao_sabe_arrumar_fica`` do ``planejar`` Python reprova a
régua 1;
tirar a ``Edicao`` da gêmea JS (a reserva no ``planejar`` da página) reprova a régua 2.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import arranjo_da_mesa as motor
from hefesto_dualsense4unix.interface import pagina_do_mapa
from tests.unit import mesa_do_mockup as mock

PENDRIVE = motor.Aparelho("pen", "Armazenamento", "Pendrive de prova", "")
ENTRADA_DO_PENDRIVE = "2"
CAMINHO_DO_PENDRIVE = "1-5"


def _mesa() -> motor.Mesa:
    return mock.mesa(
        mapa={**mock.MAPA, ENTRADA_DO_PENDRIVE: CAMINHO_DO_PENDRIVE},
        leitura={**mock.LEITURA_AGORA, "pen": CAMINHO_DO_PENDRIVE},
        aparelhos=(*mock.APARELHOS, PENDRIVE),
    )


def test_o_plano_python_deixa_o_pendrive_na_entrada_dele_nas_quatro_variantes() -> None:
    mesa = _mesa()
    for variante in motor.VARIANTES:
        plano = motor.planejar(mesa, variante.opcoes)
        assert plano.plano.get(ENTRADA_DO_PENDRIVE) == "pen", (
            f"{variante.id}: o plano deu a entrada do pendrive a outro aparelho: {plano.plano}")
        assert plano.motivo["pen"].ganho == 0 and not plano.motivo["pen"].forcado
        receita = motor.receita(mesa, variante.opcoes)
        titulos = " ".join(m.titulo.lower() for m in receita)
        assert "pendrive" not in titulos and "armazenamento" not in titulos, (
            f"{variante.id}: a receita manda mexer no pendrive: {titulos}")


def test_a_entrada_do_pendrive_nao_vira_a_vaga_de_ninguem() -> None:
    """Sem a reserva, a entrada 2 (de uma face perto) é livre e outro aparelho a toma."""
    mesa = _mesa()
    plano = motor.planejar(mesa).plano
    assert [n for n, quem in plano.items() if quem == "pen"] == [ENTRADA_DO_PENDRIVE]


_HARNESS = r"""
"use strict";
var fs = require("fs");
var linhas = fs.readFileSync(process.argv[2], "utf8").split("\n");
var ini = linhas.findIndex(function (l) { return l.trim() === "(function () {"; });
var fim = linhas.findIndex(function (l) {
  return l.indexOf('document.addEventListener("click"') !== -1; });
if (ini === -1 || fim === -1 || fim <= ini) { console.error("sem limites"); process.exit(2); }
var motor = linhas.slice(ini, fim).join("\n") + "\n" + [
  "  global.__m = {",
  "    set MAPA(v){ MAPA = v; }, get MAPA(){ return MAPA; },",
  "    set APARELHOS(v){ APARELHOS = v; }, get APARELHOS(){ return APARELHOS; },",
  "    set LEITURAS(v){ LEITURAS = v; }, get LEITURAS(){ return LEITURAS; },",
  "    set leituraAtual(v){ leituraAtual = v; },",
  "    VARIANTES: VARIANTES,",
  "    planejar: function(op){ return planejar(op); },",
  "    receita: function(op){ return receita(op); }",
  "  };",
  "})();",
].join("\n");
global.document = { getElementById: function () { return null; },
                    addEventListener: function () {}, querySelector: function () { return null; },
                    querySelectorAll: function () { return []; } };
eval(motor);
var m = global.__m;
m.APARELHOS = m.APARELHOS.concat([{ id: "pen", tipo: "Armazenamento", nome: "Pendrive de prova",
                                    cor: "#888", classe: "", usb: 2, mA: 100 }]);
var mapa = JSON.parse(JSON.stringify(m.MAPA));
mapa[process.argv[3]] = process.argv[4]; m.MAPA = mapa;
var leituras = JSON.parse(JSON.stringify(m.LEITURAS));
leituras.agora.caminho.pen = process.argv[4]; m.LEITURAS = leituras;
m.leituraAtual = "agora";
var saida = {};
m.VARIANTES.forEach(function (v) {
  saida[v.id] = { plano: m.planejar(v.op).plano,
                  receita: m.receita(v.op).map(function (x) { return x.titulo; }) };
});
console.log(JSON.stringify(saida));
"""


def _a_gemea_js(tmp_path: Path) -> dict[str, Any]:
    pagina = tmp_path / "pagina.html"
    pagina.write_text(pagina_do_mapa.pagina(), encoding="utf-8")
    harness = tmp_path / "harness.js"
    harness.write_text(_HARNESS, encoding="utf-8")
    feito = subprocess.run(
        [shutil.which("node") or "node", str(harness), str(pagina),
         ENTRADA_DO_PENDRIVE, CAMINHO_DO_PENDRIVE],
        capture_output=True, text=True, timeout=120, check=False,
    )
    assert feito.returncode == 0, f"o motor da página não rodou no node: {feito.stderr[-600:]}"
    return dict(json.loads(feito.stdout))


@pytest.mark.skipif(shutil.which("node") is None, reason="node não está nesta máquina")
def test_o_motor_da_pagina_tambem_deixa_o_pendrive_e_concorda_com_o_python(
    tmp_path: Path,
) -> None:
    js = _a_gemea_js(tmp_path)
    mesa = _mesa()
    assert set(js) == {v.id for v in motor.VARIANTES}
    for variante in motor.VARIANTES:
        do_js = js[variante.id]
        assert do_js["plano"].get(ENTRADA_DO_PENDRIVE) == "pen", (
            f"{variante.id}: o JavaScript da página deu a entrada do pendrive a outro: "
            f"{do_js['plano']}")
        em_python = motor.planejar(mesa, variante.opcoes).plano
        assert do_js["plano"] == dict(em_python), (
            f"{variante.id}: as duas gêmeas planejam diferente: js={do_js['plano']} "
            f"python={dict(em_python)}")
        assert not [t for t in do_js["receita"] if "endrive" in t or "rmazenamento" in t]


def test_a_pagina_publicada_tem_a_reserva() -> None:
    """Publicada em 05/10/2026: a bancada e o produto têm a mesma cura do JavaScript."""
    marca = "AS-DICAS-SAO-CARTOES-COM-UM-GESTO-01"
    assert "O APARELHO QUE O PLANO NÃO SABE ARRUMAR FICA ONDE ESTÁ" in pagina_do_mapa.pagina()
    assert "O APARELHO QUE O PLANO NÃO SABE ARRUMAR FICA ONDE ESTÁ" in pagina_do_mapa.pagina(
        com_as_que_esperam=False), marca
