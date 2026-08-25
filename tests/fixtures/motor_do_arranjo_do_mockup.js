/* motor_do_arranjo_do_mockup.js — o ORÁCULO da porta para Python.
 *
 * Ele não copia o motor: EXTRAI o `<script>` de `mapa-das-portas.html` (a
 * especificação executável, 1058 linhas de lógica), corta fora a camada de
 * interação e desenho, e chama as funções puras sobre os mesmos cenários que
 * `tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py` dá ao Python.
 *
 * Copiar o motor para cá seria a segunda verdade que esta leva existe para
 * matar: a cópia envelheceria em silêncio no dia em que o mockup mudasse.
 *
 *   node tests/fixtures/motor_do_arranjo_do_mockup.js > saida.json
 *
 * `Infinity` não existe em JSON: sai como a string "Infinity", e o lado Python
 * a lê de volta como `math.inf`.
 */
"use strict";
var fs = require("fs");
var path = require("path");

var HTML = path.join(__dirname, "..", "..", "docs", "process", "sprints",
                     "2026-08-24-ABA-CONEXOES", "mockup", "mapa-das-portas.html");

var linhas = fs.readFileSync(HTML, "utf8").split("\n");
var ini = linhas.findIndex(function (l) { return l.trim() === "(function () {"; });
var fim = linhas.findIndex(function (l) { return l.indexOf('document.addEventListener("click"') !== -1; });
if (ini === -1 || fim === -1 || fim <= ini) {
  console.error("não achei os limites do motor dentro do mockup");
  process.exit(2);
}

/* o motor, sem a camada de interação, mais o bloco que o exporta */
var motor = linhas.slice(ini, fim).join("\n") + "\n" + [
  "  global.__motor = {",
  "    set MAPA(v){ MAPA = v; },",
  "    get MAPA(){ return MAPA; },",
  "    set APARELHOS(v){ APARELHOS = v; },",
  "    get APARELHOS(){ return APARELHOS; },",
  "    set LEITURAS(v){ LEITURAS = v; },",
  "    get LEITURAS(){ return LEITURAS; },",
  "    set leituraAtual(v){ leituraAtual = v; },",
  "    set naMao(v){ naMao = v; },",
  "    set segurando(v){ segurando = v; },",
  "    set CONTROLES(v){ CONTROLES = v; },",
  "    get CONTROLES(){ return CONTROLES; },",
  "    set quantos(v){ quantos = v; },",
  "    VARIANTES: VARIANTES,",
  "    FACES: FACES,",
  "    alocacao: function(){ return alocacaoDerivada(); },",
  "    regiaoDoCaminho: function(c){ return regiaoDoCaminho(c); },",
  "    semEntrada: function(){ return semEntrada().map(function (x) {",
  "      return { id: x.ap.id, caminho: x.caminho, regiao: x.regiao }; }); },",
  "    candidatas: function(r){ return candidatas(r).map(function (p) { return p.n; }); },",
  "    planejar: function(op){ return planejar(op); },",
  "    receita: function(op){ return receita(op); },",
  "    julgar: function(n){ alocacao = alocacaoDerivada(); return julgar(porNum(n)); },",
  "    reexame: function(a, b){ return reexame(a, b).map(function (x) {",
  "      return { id: x.ap.id, antes: x.antes, agora: x.agora,",
  "               entradaAntes: x.entradaAntes, entradaAgora: x.entradaAgora }; }); },",
  "    consequencias: function(op){ return consequencias(op); },",
  "    qualidade: function(op){ return qualidade(op); },",
  "    planoDosControles: function(){ return planoDosControles(); },",
  "    todasPortas: function(){ return todasPortas().map(function (p) { return p.n; }); }",
  "  };",
  "})();",
].join("\n");

/* o motor define funções de desenho que tocam `document`; nenhuma delas roda
   aqui, mas a referência precisa existir para o `eval` não estourar */
global.document = { getElementById: function () { return null; },
                    addEventListener: function () {}, querySelector: function () { return null; } };
eval(motor);
var m = global.__motor;

var copia = function (x) { return JSON.parse(JSON.stringify(x)); };
var APARELHOS_PADRAO = copia(m.APARELHOS);
var MAPA_PADRAO = copia(m.MAPA);
var LEITURAS_PADRAO = copia(m.LEITURAS);
var CONTROLES_PADRAO = copia(m.CONTROLES);

function reset() {
  m.APARELHOS = copia(APARELHOS_PADRAO);
  m.MAPA = copia(MAPA_PADRAO);
  m.LEITURAS = copia(LEITURAS_PADRAO);
  m.CONTROLES = copia(CONTROLES_PADRAO);
  m.leituraAtual = "agora";
  m.naMao = null;
  m.segurando = null;
  m.quantos = 4;
}

/* a mesa dela às 02:36 de 25/08/2026: o hub saiu do barramento e levou os três
   adaptadores Bluetooth com ele. Estado de primeira classe, não borda. */
var SEM_HUB_APARELHOS = [
  { id: "wifi",    tipo: "Wi-Fi",   nome: "Archer T3U",       cor: "#ff5555", classe: "wifi",    usb: 3, mA: 504 },
  { id: "teclado", tipo: "Teclado", nome: "Receptor 2,4 GHz", cor: "#ffb86c", classe: "teclado", usb: 2, mA: 100 },
  { id: "mouse",   tipo: "Mouse",   nome: "Receptor 2,4 GHz", cor: "#f1fa8c", classe: "mouse",   usb: 2, mA:  98 },
];
var SEM_HUB_LEITURA = { "teclado": "1-3", "mouse": "1-6", "wifi": "4-4" };

var out = {};

reset();
out["alocacao/agora"] = m.alocacao();
m.leituraAtual = "antes";
out["alocacao/antes"] = m.alocacao();

reset();
["3-1.2", "3-1.1.1", "4-1.1.2", "4-2", "1-3", "1-6", "1-4", "3-1", null]
  .forEach(function (c) { out["regiao/" + c] = m.regiaoDoCaminho(c); });

out["semEntrada/agora"] = m.semEntrada();
m.leituraAtual = "antes";
out["semEntrada/antes"] = m.semEntrada();

reset();
out["candidatas/pc"] = m.candidatas("pc");
out["candidatas/hub"] = m.candidatas("hub");
out["todasPortas"] = m.todasPortas();

m.VARIANTES.forEach(function (v) {
  reset();
  out["planejar/" + v.id] = m.planejar(v.op);
  out["receita/" + v.id] = m.receita(v.op);
  out["consequencias/" + v.id] = m.consequencias(v.op);
  out["qualidade/" + v.id] = m.qualidade(v.op);
});

/* a regra "ficar parado vale bônus", arrancada */
reset();
out["receita/sem-bonus-parado"] = m.receita({ bonusParado: 0 });
out["planejar/sem-bonus-parado"] = m.planejar({ bonusParado: 0 });

/* ponto fixo: aplicar o plano e replanejar dá zero movimentos */
m.VARIANTES.forEach(function (v) {
  reset();
  var plano = m.planejar(v.op).plano;
  /* aplicar = o mapa passa a dizer que cada entrada do plano é o caminho de
     quem foi para lá; a leitura não muda, só o cabo mudou de soquete */
  var leitura = LEITURAS_PADRAO.agora.caminho;
  var novoMapa = {};
  Object.keys(plano).forEach(function (n) { novoMapa[n] = leitura[plano[n]]; });
  m.MAPA = novoMapa;
  out["ponto-fixo/" + v.id] = m.receita(v.op);
});

["1", "2", "3", "7", "9", "10", "13", "15", "15a"].forEach(function (n) {
  ["bt", "wifi", "teclado", "mouse", "webcam", null].forEach(function (mao) {
    reset();
    m.naMao = mao;
    out["julgar/" + n + "/" + mao] = m.julgar(n);
  });
});

/* segurando: o filtro de região entra antes do veredito por classe */
reset();
m.segurando = "bt-c";
m.naMao = "bt";
["1", "2", "10", "15a"].forEach(function (n) { out["julgar-segurando/bt-c/" + n] = m.julgar(n); });

reset();
out["reexame/antes-agora"] = m.reexame("antes", "agora");
out["reexame/agora-agora"] = m.reexame("agora", "agora");

/* os controles: o padrão, e os casos da mordida da MOTOR-4 */
reset();
out["controles/padrao"] = m.planoDosControles();
[1, 2, 3, 4].forEach(function (q) {
  reset();
  m.quantos = q;
  out["controles/quantos=" + q] = m.planoDosControles();
});
reset();
m.CONTROLES = CONTROLES_PADRAO.map(function (c) { return Object.assign({}, c, { mic: false }); });
out["controles/sem-mic"] = m.planoDosControles();
reset();
m.CONTROLES = CONTROLES_PADRAO.map(function (c) { return Object.assign({}, c, { onde: "bt-a" }); });
out["controles/todos-no-bt-a"] = m.planoDosControles();
reset();
m.CONTROLES = CONTROLES_PADRAO.map(function (c) { return Object.assign({}, c, { onde: "sumiu" }); });
out["controles/adaptador-sumiu"] = m.planoDosControles();

/* mapa vazio e mapa com entrada inexistente — dois estados da fumaça */
reset();
m.MAPA = {};
out["mapa-vazio/alocacao"] = m.alocacao();
out["mapa-vazio/planejar"] = m.planejar({});
out["mapa-vazio/receita"] = m.receita({});
out["mapa-vazio/candidatas-pc"] = m.candidatas("pc");
reset();
m.MAPA = { "99": "9-9" };
out["mapa-inexistente/alocacao"] = m.alocacao();
out["mapa-inexistente/receita"] = m.receita({});

/* A MESA DELA DE AGORA: o hub sumiu, e com ele os três adaptadores */
reset();
m.APARELHOS = copia(SEM_HUB_APARELHOS);
m.LEITURAS = { agora: { rotulo: "02h36 — sem o hub", caminho: copia(SEM_HUB_LEITURA) },
               antes: { rotulo: "02h36 — sem o hub", caminho: copia(SEM_HUB_LEITURA) } };
out["sem-hub/alocacao"] = m.alocacao();
out["sem-hub/regiao-1-3"] = m.regiaoDoCaminho("1-3");
out["sem-hub/regiao-4-4"] = m.regiaoDoCaminho("4-4");
out["sem-hub/semEntrada"] = m.semEntrada();
out["sem-hub/planejar"] = m.planejar({});
out["sem-hub/receita"] = m.receita({});
out["sem-hub/consequencias"] = m.consequencias({});
out["sem-hub/controles"] = m.planoDosControles();

function serializar(_k, v) {
  if (v === Infinity) return "Infinity";
  if (v === -Infinity) return "-Infinity";
  return v;
}
process.stdout.write(JSON.stringify(out, serializar, 1) + "\n");
