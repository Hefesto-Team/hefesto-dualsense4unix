"""Cada faixa tem dono — CADA-FAIXA-TEM-DONO-01.

Nenhuma régua confere a saída contra ela mesma: a entrada é uma cena de mentira, e o
esperado sai da entrada (dos evitados de cada adaptador, do padrão de frequências, das
classes do `:root` da página gerada).
"""

from __future__ import annotations

import itertools
import math
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import faixa_do_wifi as fw
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from hefesto_dualsense4unix.utils import maquina

RAIZ = Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup/08-conexoes.html"

ADAPTADORES = (("L1", "Direita"), ("L2", "Esquerda"), ("L3", "Meio"), ("L4", "Fundo"))
EVITADOS = {"L1": (0, 10), "L2": (30, 40), "L3": (60, 79), "L4": (45, 50)}
CORES_DOS_PLASTICOS = ("#ae335a", "#7eb8d4", "#e35b8c", "#74588e")
LIDO = "(lido)"
ENDERECO_DO_TECLADO = "/sys/forjado/3-1.1.4"


class No:
    def __init__(self, tag: str, attrs: dict[str, str], pai: No | None) -> None:
        self.tag, self.attrs, self.pai = tag, attrs, pai
        self.filhos: list[No] = []
        self.texto: list[str] = []

    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def todos(self) -> list[No]:
        achados = [self]
        for f in self.filhos:
            achados += f.todos()
        return achados

    def achar(self, tag: str | None = None, classe: str | None = None, **attrs: str) -> list[No]:
        return [n for n in self.todos()
                if (tag is None or n.tag == tag)
                and (classe is None or classe in n.classes())
                and all(n.attrs.get(k.replace("_", "-")) == v for k, v in attrs.items())]

    def dito(self) -> str:
        return "".join(self.texto) + "".join(f.dito() for f in self.filhos)

    def ancestrais(self) -> list[No]:
        quem, pai = [], self.pai
        while pai is not None:
            quem.append(pai)
            pai = pai.pai
        return quem


class _Arvore(HTMLParser):
    VAZIOS = frozenset({"input", "br", "img", "use", "path", "circle", "rect", "link", "meta"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.raiz = No("#raiz", {}, None)
        self.atual = self.raiz

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        no = No(tag, {k: v or "" for k, v in attrs}, self.atual)
        self.atual.filhos.append(no)
        if tag not in self.VAZIOS:
            self.atual = no

    def handle_startendtag(self, tag: str, attrs: Any) -> None:
        self.atual.filhos.append(No(tag, {k: v or "" for k, v in attrs}, self.atual))

    def handle_endtag(self, tag: str) -> None:
        quem = self.atual
        while quem is not self.raiz and quem.tag != tag:
            quem = quem.pai or self.raiz
        if quem is not self.raiz:
            self.atual = quem.pai or self.raiz

    def handle_data(self, dado: str) -> None:
        self.atual.texto.append(dado)


def _ler(html: str) -> No:
    p = _Arvore()
    p.feed(html)
    return p.raiz


def _controle(ident: str, lugar: str, cor: str) -> dict[str, Any]:
    return {"id": ident, "tipo": "controle", "lugar": lugar, "nome": ident, "rotulo": ident,
            "cor": cor, "mic": False, "ponte": None, "alem": False, "esperando": False,
            "fixo": False, "luz": False, "hz_mov": 250.0}


def _outro(ident: str, lugar: str, **marcas: Any) -> dict[str, Any]:
    return {"id": ident, "tipo": "outro", "lugar": lugar, "nome": "Aparelho", "rotulo": "Aparelho",
            "cor": "", "esperando": False, "fixo": False, **marcas}


def _cena(n_adaptadores: int = 3, *, ordem: tuple[str, ...] | None = None,
          vizinhos: list[dict[str, Any]] | None = None, wifi: list[dict[str, Any]] | None = None,
          com_outros: bool = False) -> dict[str, Any]:
    ids = ordem or tuple(i for i, _ in ADAPTADORES[:n_adaptadores])
    nomes = dict(ADAPTADORES)
    lugares = [{"id": i, "lugar": i, "nome": nomes[i], "entrada": f"Entrada {i}", "sabido": True,
                "face": "", "hub": False, "varrendo": False, "junto": "", "usb3": False,
                "conectando": False, "chegou": [], "quedas": []} for i in ids]
    # 2, 1 e 1 controles nos três primeiros adaptadores
    aparelhos = [_controle("c1", "L1", CORES_DOS_PLASTICOS[0]),
                 _controle("c2", "L1", CORES_DOS_PLASTICOS[1]),
                 _controle("c3", "L2", CORES_DOS_PLASTICOS[2]),
                 _controle("c4", "L3", CORES_DOS_PLASTICOS[3])]
    if com_outros:
        aparelhos += [_outro("o1", "L1"), _outro("o2", "L1", desligado=True)]
    aparelhos = [a for a in aparelhos if a["lugar"] in ids]
    portas = [{"id": f"porta-{i}", "caminho": f"1-{k}", "usb": "2.0", "ocupa": i,
               "grupo": "Traseira", "rotulo": f"1-{k}"} for k, i in enumerate(ids, 1)]
    for v in vizinhos or ():
        portas.append({"id": f"porta-{v['id']}", "caminho": f"2-{v['id'][-1]}", "usb": "2.0",
                       "ocupa": v["id"], "grupo": "Traseira", "rotulo": "x"})
    return {
        "lido": True, "lugares": lugares, "aparelhos": aparelhos,
        "evitados": [{"lugar": i, "ini": EVITADOS[i][0], "fim": EVITADOS[i][1]} for i in ids],
        "canais_medidos": dict.fromkeys(ids, True), "vizinhos": vizinhos or [],
        "wifi": wifi or [], "portas": portas, "pedido": None, "proposta": None,
        "ocupado": False, "aberto": None, "perto": [], "procurando": a08.PROCURAR_DESLIGADO,
    }


def _viz(ident: str, **campos: Any) -> dict[str, Any]:
    return {"id": ident, "tipo": "", "nome": "", "sugestao": "", "sugestao_tipo": "",
            "lido": "", "produto": "", "no": f"/sys/forjado/{ident}", **campos}


def _pistas(cena: dict[str, Any]) -> dict[str, No]:
    arvore = _ler(a08.html_dos_canais(cena))
    return {p.attrs["data-grupo"]: p for p in arvore.achar("div", "pista")}


def _canais_do_trilho(pista: No, classe: str) -> list[tuple[int, int]]:
    achados = []
    for peca in pista.achar("div", classe):
        m = re.fullmatch(r"left:([\d.e+-]+)%;width:([\d.e+-]+)%", peca.attrs["style"])
        assert m, peca.attrs
        ini = round(float(m.group(1)) * 79 / 100)
        achados.append((ini, round((float(m.group(1)) + float(m.group(2))) * 79 / 100)))
    return achados


def test_uma_pista_por_adaptador_com_os_canais_dele() -> None:
    pistas = _pistas(_cena())
    assert list(pistas) == ["L1", "L2", "L3"]
    for lid, (ini, fim) in ((i, EVITADOS[i]) for i in ("L1", "L2", "L3")):
        assert _canais_do_trilho(pistas[lid], "evitado") == [(ini, fim)], lid
    ditos = {lid: p.achar("span", "no-ar-dele")[0].dito() for lid, p in pistas.items()}
    assert ditos == {"L1": "2 no ar", "L2": "1 no ar", "L3": "1 no ar"}
    todo = "".join(p.dito() for p in pistas.values())
    assert "4 no ar" not in todo


def test_o_salto_de_cada_pista_e_da_lista_dela_e_nao_da_uniao() -> None:
    pistas = _pistas(_cena())
    livres = {i: [c for c in range(79) if not EVITADOS[i][0] <= c < EVITADOS[i][1]]
              for i in ("L1", "L2", "L3")}
    for lid, p in pistas.items():
        cobertos = {c for a, b in _canais_do_trilho(p, "salto") for c in range(a, b)}
        assert cobertos == set(livres[lid]), lid


def _conta(no: No) -> tuple[str, str]:
    c = no.achar("span", "canais-do-lugar")
    assert len(c) == 1
    return c[0].dito().strip(), c[0].attrs["data-nivel"]


def test_o_numero_da_pista_e_o_da_caixa() -> None:
    cena = _cena()
    pistas = _pistas(cena)
    sala = _ler(a08.html_da_sala(cena))
    caixas = {c.attrs["data-id"]: c for c in sala.achar("div", "lugar")}
    for lid in ("L1", "L2", "L3"):
        da_pista = _conta(pistas[lid].achar("div", "rotulo")[0])
        da_caixa = [(c.dito().strip(), c.attrs["data-nivel"])
                    for c in caixas[lid].achar("span", "canais-do-lugar")
                    if "data-nivel" in c.attrs]
        assert da_caixa == [da_pista], lid
    assert _conta(pistas["L2"])[0] == f"{79 - 10}/79"
    nas_caixas = {s.dito().strip() for c in caixas.values()
                  for s in c.achar("span", "canais-do-lugar") if "data-nivel" in s.attrs}
    campo = a08.campos_da_secao(cena)["espectro-canais"]
    assert set(re.findall(r"\d+/79", _ler(campo).dito())) <= nas_caixas


def _cor(no: No) -> str:
    cores = [c for c in no.classes() if c.startswith("cor-")]
    assert len(cores) == 1, (no.tag, no.attrs)
    return cores[0]


def _tres_cores(cena: dict[str, Any]) -> dict[str, tuple[str, str, str]]:
    pistas = _pistas(cena)
    caixas = {c.attrs["data-id"]: c
              for c in _ler(a08.html_da_sala(cena)).achar("div", "lugar")}
    portas = _ler(a08.html_das_portas(cena))
    achado = {}
    for lug in cena["lugares"]:
        lid = lug["id"]
        porta = next(b for b in portas.achar("button", "porta")
                     if b.attrs["data-alvo"] == f"porta-{lid}")
        glifo = porta.achar("svg")[0]
        achado[lid] = (_cor(pistas[lid]), _cor(caixas[lid].achar("input", "lugar-nome")[0]),
                       _cor(glifo))
    return achado


@pytest.mark.parametrize("ordem", [("L1", "L2", "L3"), ("L3", "L1", "L2"), ("L2", "L3", "L1")])
def test_a_cor_segue_o_adaptador_nas_tres_pecas_e_a_posicao_dele(ordem: tuple[str, ...]) -> None:
    achado = _tres_cores(_cena(ordem=ordem))
    for posicao, lid in enumerate(ordem):
        esperada = f"cor-{a08.CORES_DOS_ADAPTADORES[posicao]}"
        assert achado[lid] == (esperada,) * 3, (lid, achado[lid])


def test_o_quinto_adaptador_em_diante_fica_comment() -> None:
    cena = _cena(4)
    cena["lugares"].append({**cena["lugares"][0], "id": "L5", "nome": "Quinto"})
    assert a08.cor_do_adaptador(cena, "L5") == a08.COR_DO_QUINTO_EM_DIANTE == "comment"


def _pares_de_glifo_e_nome(cena: dict[str, Any]) -> list[tuple[str, str]]:
    html = re.sub(r'\scor-\w+|style="[^"]*"', "", a08.html_dos_canais(cena))
    pares = []
    for p in _ler(html).achar("div", "pista"):
        rotulo = p.achar(None, "rotulo")[0]
        pares.append((rotulo.achar("use")[0].attrs["href"], rotulo.achar("span", "nome")[0].dito()))
    return pares


def _cena_variada(n: int = 3) -> dict[str, Any]:
    return _cena(n, com_outros=True, vizinhos=[
        _viz("3554:fa09", sugestao="Teclado", sugestao_tipo="teclado", lido="Teclado"),
        _viz("25a7:fa07", sugestao="Mouse", sugestao_tipo="mouse", lido="Mouse"),
        _viz("2357:012d"),
    ], wifi=[{"no": "", "mhz": 5805, "largura": 80}])


def test_a_cor_nao_e_o_unico_sinal_glifo_e_nome_separam_toda_pista() -> None:
    pares = _pares_de_glifo_e_nome(_cena_variada())
    assert len(pares) == len(set(pares)) == 7, pares


def _usos_da_antena(html: str) -> list[No]:
    return [u for u in _ler(html).achar("use") if u.attrs.get("href") == "#rd-radio"]


def test_a_antena_e_so_do_adaptador_em_todo_campo_que_a_secao_emite() -> None:
    cena = _cena_variada()
    campos = a08.campos_da_secao(cena)
    portas_de_adaptador = {f"porta-{i}" for i in ("L1", "L2", "L3")}
    permitidos = 0
    for chave, valor in campos.items():
        if not isinstance(valor, str):
            continue
        for uso in _usos_da_antena(valor):
            quem = uso.ancestrais()
            na_pista = any({"pista", "adaptador"} <= q.classes() for q in quem)
            na_conta = any("canais-do-lugar" in q.classes() for q in quem)
            na_porta = any(q.tag == "button" and q.attrs.get("data-alvo") in portas_de_adaptador
                           for q in quem)
            assert na_pista or na_conta or na_porta, (chave, [q.attrs for q in quem[:3]])
            permitidos += 1
    assert permitidos >= 3 + 3 + 3, "a régua ficou cega: faltam as antenas dos adaptadores"
    # o rádio sem tipo e o aparelho `outro` (no ar e desligado) levam o «?»
    sala = campos["radio-sala"]
    assert sala.count("#rd-ajuda") >= 2
    assert not [u for u in _usos_da_antena(campos["vizinhanca-das-portas"])
                if not any(q.attrs.get("data-alvo") in portas_de_adaptador for q in u.ancestrais())]


def _hex_de(token: str) -> str:
    raiz = MOCKUP.read_text(encoding="utf-8")
    m = re.search(rf"--{token}:\s*(#[0-9a-fA-F]{{6}})", raiz)
    assert m, token
    return m.group(1)


def _linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = (_linear(min(1.0, max(0.0, c))) for c in rgb)
    x = 0.4124 * r + 0.3576 * g + 0.1805 * b
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = 0.0193 * r + 0.1192 * g + 0.9505 * b

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116

    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


#: Machado, Oliveira e Fernandes (2009), severidade 1, em RGB linear
MACHADO = {
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216),
                   (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413),
                     (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602),
                   (0.004733, 0.691367, 0.303900)),
}


def _simulada(hexa: str, modo: str) -> tuple[float, float, float]:
    lin = [_linear(int(hexa[i:i + 2], 16) / 255) for i in (1, 3, 5)]
    mat = MACHADO[modo]
    sim = [min(1.0, max(0.0, sum(m * c for m, c in zip(linha, lin, strict=True)))) for linha in mat]
    # volta a sRGB para entrar em `_lab`, que lineariza
    return tuple(  # type: ignore[return-value]
        12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055 for c in sim)


def _de(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.dist(_lab(a), _lab(b))


def test_as_cores_se_separam_para_quem_nao_ve_cor() -> None:
    pistas = _pistas(_cena(4, wifi=[{"no": "", "mhz": 2437, "largura": 20}]))
    tokens = sorted({_cor(p).removeprefix("cor-") for p in pistas.values() if p.classes() & {
        f"cor-{t}" for t in (*a08.CORES_DOS_ADAPTADORES, a08.COR_DO_WIFI)}})
    assert len(tokens) == 5, tokens
    assert "green" not in tokens and "red" not in tokens
    hexes = {t: _hex_de(t) for t in tokens}
    for modo in MACHADO:
        for a, b in itertools.combinations(tokens, 2):
            d = _de(_simulada(hexes[a], modo), _simulada(hexes[b], modo))
            assert d >= 12, f"{a} e {b} em {modo}: ΔE {d:.1f}"


def test_o_lido_sai_com_o_selo_e_sem_interrogacao_e_o_dela_sem_selo() -> None:
    lido = _viz("3554:fa09", sugestao="Teclado", sugestao_tipo="teclado", lido="Teclado")
    dela = _viz("25a7:fa07", tipo="teclado", nome="Teclado")
    camera = _viz("0c45:6366", sugestao="Webcam", sugestao_tipo="webcam", lido="Câmera")
    cena = _cena(vizinhos=[lido, dela, camera])
    pistas = _pistas(cena)
    r_lido = pistas["3554:fa09"].achar(None, "rotulo")[0]
    assert r_lido.achar("span", "nome")[0].dito() == "Teclado"
    assert [s.dito() for s in r_lido.achar("span", "selo-lido")] == [a08.SELO_LIDO] == [LIDO]
    assert "?" not in r_lido.dito()
    r_dela = pistas["25a7:fa07"].achar(None, "rotulo")[0]
    assert not r_dela.achar("span", "selo-lido")
    assert r_dela.achar("span", "nome")[0].dito() == "Teclado"
    r_cam = pistas["0c45:6366"].achar(None, "rotulo")[0]
    assert r_cam.achar("span", "nome")[0].dito() == "Webcam?"
    assert not r_cam.achar("span", "selo-lido")
    assert "lido pelo computador" in r_lido.attrs["title"]


def test_o_ff_com_produto_leva_o_produto_e_sem_produto_a_palavra_do_censo() -> None:
    com = _viz("2357:012d", produto="802.11ac NIC")
    sem = _viz("1234:5678")
    pistas = _pistas(_cena(vizinhos=[com, sem]))
    r_com = pistas["2357:012d"].achar(None, "rotulo")[0]
    assert r_com.achar("span", "nome")[0].dito() == "802.11ac NIC"
    assert r_com.achar("use")[0].attrs["href"] == "#rd-ajuda"
    r_sem = pistas["1234:5678"].achar(None, "rotulo")[0]
    assert r_sem.achar("span", "nome")[0].dito() == a08.ESPECIE_DESCONHECIDA == "Não identificado"
    assert "Sem nome" not in a08.html_dos_canais(_cena(vizinhos=[com, sem]))


def test_pintar_a_secao_nao_grava_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    gravou: list[str] = []
    for nome in ("_escrever", "gravar_maquina", "gravar_rascunho_da_mesa", "gravar_o_computador",
                 "gravar_maquina_com_descartes"):
        monkeypatch.setattr(maquina, nome, lambda *a, _n=nome, **k: gravou.append(_n) or True)
    cena = _cena_variada()
    a08.campos_da_secao(cena)
    a08.grupos_do_ar(cena)
    assert gravou == []


def test_o_wifi_do_nm_e_o_vizinho_do_mesmo_no_sao_uma_pista_so() -> None:
    no = ENDERECO_DO_TECLADO
    cena = _cena(vizinhos=[_viz("2357:012d", no=no)],
                 wifi=[{"no": no, "mhz": 5805, "largura": 80},
                       {"no": "", "mhz": 2437, "largura": 20}])
    grupos = [g for g in a08.grupos_do_ar(cena) if g["tipo"] != "adaptador"]
    assert [g["id"] for g in grupos] == ["2357:012d", "wifi-1"]
    assert [g["nome"] for g in grupos] == [a08.NOME_DO_WIFI] * 2
    assert grupos[0]["faixas"][0]["como"] == fw.FORA
    assert (grupos[1]["faixas"][0]["ini"], grupos[1]["faixas"][0]["fim"]) == (25, 46)
    pistas = _pistas(cena)
    assert "5 GHz: fora desta faixa" in pistas["2357:012d"].dito()
    assert f"25{a08.TRACO_CURTO}45" in pistas["wifi-1"].dito()


def test_o_receptor_e_o_wifi_sem_leitura_dizem_que_nao_se_le() -> None:
    cena = _cena(vizinhos=[_viz("3554:fa09", tipo="teclado", nome="Teclado"),
                           _viz("2357:012d", tipo="wifi", nome="Wi-Fi")])
    pistas = _pistas(cena)
    assert a08.CANAL_DO_RADIO_NAO_SE_LE in pistas["3554:fa09"].dito()
    assert a08.FAIXA_DO_WIFI_NAO_SE_LE in pistas["2357:012d"].dito()
    assert not pistas["3554:fa09"].achar("div", "evitado")


def test_adaptador_sem_mapa_diz_que_nao_se_mede_e_nunca_zero_evitados() -> None:
    cena = _cena(2)
    cena["evitados"] = [v for v in cena["evitados"] if v["lugar"] != "L2"]
    cena["canais_medidos"]["L2"] = False
    pistas = _pistas(cena)
    assert a08.SEM_MEDIDA in pistas["L2"].dito()
    assert "/79" not in pistas["L2"].dito() and not pistas["L2"].achar("div", "evitado")
    assert "sem-medida" in pistas["L2"].classes() and "sem-medida" not in pistas["L1"].classes()


def test_com_zero_adaptadores_nao_ha_regua() -> None:
    cena = _cena(3)
    cena["lugares"] = []
    assert a08.html_dos_canais(cena) == "" and a08.grupos_do_ar(cena) == []


def test_o_rotulo_de_vizinho_e_botao_e_o_de_adaptador_nao() -> None:
    pistas = _pistas(_cena(vizinhos=[_viz("3554:fa09", sugestao="Teclado", lido="Teclado",
                                          sugestao_tipo="teclado")]))
    assert pistas["L1"].achar("button") == []
    botao = pistas["3554:fa09"].achar("button", "rotulo")[0]
    assert botao.attrs["data-gesto"] == "vizinho-o-que-e"
    assert botao.attrs["data-alvo"] == "3554:fa09"


def test_adaptador_medido_sem_canal_evitado_tem_a_pista_inteira_livre() -> None:
    """Medido e sem nenhum evitado (79/79) é um fato, e não «não se mede»."""
    cena = _cena(2)
    cena["evitados"] = [v for v in cena["evitados"] if v["lugar"] != "L2"]
    pistas = _pistas(cena)
    assert _conta(pistas["L2"].achar(None, "rotulo")[0])[0] == "79/79"
    assert not pistas["L2"].achar("div", "evitado")
    assert _canais_do_trilho(pistas["L2"], "salto") == [(0, 79)]
    assert a08.SEM_MEDIDA not in pistas["L2"].dito()
    assert "sem-medida" not in pistas["L2"].classes()
