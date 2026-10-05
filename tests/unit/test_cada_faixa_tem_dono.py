"""Cada faixa tem dono — CADA-FAIXA-TEM-DONO-01, na régua por aparelho do desenho 1.

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

from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from hefesto_dualsense4unix.utils import maquina

RAIZ = Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup/08-conexoes.html"

ADAPTADORES = (("L1", "Direita"), ("L2", "Esquerda"), ("L3", "Meio"), ("L4", "Fundo"))
EVITADOS = {"L1": (0, 10), "L2": (30, 40), "L3": (60, 79), "L4": (45, 50)}
CORES_DOS_PLASTICOS = ("#ae335a", "#7eb8d4", "#e35b8c", "#74588e")
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


def _linhas(cena: dict[str, Any]) -> dict[str, No]:
    """As linhas da régua, por `data-id`: um aparelho (ou rádio da casa) por linha."""
    arvore = _ler(a08.html_dos_canais(cena))
    return {p.attrs["data-id"]: p for p in arvore.achar("div", "ar-linha")}


def _celulas(linha: No) -> list[No]:
    return [c for c in linha.achar("i") if c.pai is not None and "ar-faixa" in c.pai.classes()]


def _perdidos(linha: No) -> set[int]:
    """Os canais perdidos de uma linha, lidos do `title` de cada célula."""
    achados = set()
    for c in _celulas(linha):
        m = re.match(r"Canal (\d+) .* perdido para", c.attrs.get("title", ""))
        if m:
            achados.add(int(m.group(1)))
    return achados


def test_uma_linha_por_aparelho_com_os_canais_dele() -> None:
    linhas = _linhas(_cena())
    assert list(linhas) == ["c1", "c2", "c3", "c4"]
    for ident, lid in (("c1", "L1"), ("c2", "L1"), ("c3", "L2"), ("c4", "L3")):
        ini, fim = EVITADOS[lid]
        assert _perdidos(linhas[ident]) == set(range(ini, fim)), ident
        assert len(_celulas(linhas[ident])) == a08.CANAIS_DO_BT == 79
    grupos = {g.attrs["data-grupo"]: g.dito() for g in _ler(a08.html_dos_canais(_cena())).achar(
        "div", "ar-grupo") if "data-grupo" in g.attrs}
    # sem a frase «N aparelhos dividem o tempo deste rádio» (desenho aprovado de 05/10/2026)
    assert grupos["L1"].strip() and "dividem o tempo" not in grupos["L1"]
    assert "aparelho neste rádio" not in grupos["L2"]


def _fala(no: No) -> str:
    """O que a linha diz a quem não vê a cor: o texto, os `aria-label` e os `title` dela."""
    partes = [no.dito()]

    def andar(n: No) -> None:
        partes.extend(n.attrs.get(a, "") or "" for a in ("aria-label", "title"))
        for f in n.filhos:
            andar(f)

    andar(no)
    return " ".join(p for p in partes if p)


def _selo(linha: No) -> tuple[str, str]:
    """O ponto da linha: a palavra que ele diz ao leitor de tela e o nível (a classe)."""
    s = linha.achar(None, "ar-selo")
    assert len(s) == 1
    fala = s[0].attrs.get("aria-label", "").split(" · ")[0]
    return fala, next(c for c in s[0].classes() if c not in ("ar-selo", "sem"))


def test_o_numero_da_linha_e_o_da_caixa() -> None:
    cena = _cena()
    linhas = _linhas(cena)
    sala = _ler(a08.html_da_sala(cena))
    caixas = {c.attrs["data-id"]: c for c in sala.achar("div", "lugar")}
    for ident, lid in (("c1", "L1"), ("c3", "L2"), ("c4", "L3")):
        da_caixa = [c.dito().strip() for c in caixas[lid].achar("span", "canais-do-lugar")
                    if "data-nivel" in c.attrs]
        assert da_caixa == [re.search(r"\d+/79", _selo(linhas[ident])[0]).group(0)], lid
    assert _selo(linhas["c3"])[0] == f"Boa {79 - 10}/79"
    campo = a08.campos_da_secao(cena)["espectro-canais"]
    nas_caixas = {s.dito().strip() for c in caixas.values()
                  for s in c.achar("span", "canais-do-lugar") if "data-nivel" in s.attrs}
    assert set(re.findall(r"\d+/79", _ler(campo).dito())) <= nas_caixas


def test_o_selo_diz_a_palavra_pelo_mesmo_piso_do_adaptador() -> None:
    """Liso, médio e engasga do `nivel_dos_canais` viram boa, apertada e sofrendo."""
    cena = _cena()
    cena["evitados"] = [{"lugar": "L1", "ini": 0, "fim": 5}, {"lugar": "L2", "ini": 0, "fim": 25},
                        {"lugar": "L3", "ini": 0, "fim": 70}]
    linhas = _linhas(cena)
    assert _selo(linhas["c1"]) == ("Boa 74/79", "boa")
    assert _selo(linhas["c3"]) == ("Apertada 54/79", "apertada")
    assert _selo(linhas["c4"]) == ("Sofrendo 9/79", "sofrendo")


def _cor(no: No) -> str:
    cores = [c for c in no.classes() if c.startswith("cor-")]
    assert len(cores) == 1, (no.tag, no.attrs)
    return cores[0]


def _duas_cores(cena: dict[str, Any]) -> dict[str, tuple[str, str]]:
    cabecas = {g.attrs["data-grupo"]: g for g in _ler(a08.html_dos_canais(cena)).achar(
        "div", "ar-grupo") if "data-grupo" in g.attrs}
    caixas = {c.attrs["data-id"]: c
              for c in _ler(a08.html_da_sala(cena)).achar("div", "lugar")}
    return {lug["id"]: (_cor(cabecas[lug["id"]]),
                        _cor(caixas[lug["id"]].achar("input", "lugar-nome")[0]))
            for lug in cena["lugares"]}


@pytest.mark.parametrize("ordem", [("L1", "L2", "L3"), ("L3", "L1", "L2"), ("L2", "L3", "L1")])
def test_a_cor_segue_o_adaptador_na_cabeca_e_na_caixa_e_a_posicao_dele(
        ordem: tuple[str, ...]) -> None:
    achado = _duas_cores(_cena(ordem=ordem))
    for posicao, lid in enumerate(ordem):
        esperada = f"cor-{a08.CORES_DOS_ADAPTADORES[posicao]}"
        assert achado[lid] == (esperada,) * 2, (lid, achado[lid])


def test_o_quinto_adaptador_em_diante_fica_comment() -> None:
    cena = _cena(4)
    cena["lugares"].append({**cena["lugares"][0], "id": "L5", "nome": "Quinto"})
    assert a08.cor_do_adaptador(cena, "L5") == a08.COR_DO_QUINTO_EM_DIANTE == "comment"


def _cena_variada(n: int = 3) -> dict[str, Any]:
    return _cena(n, com_outros=True, vizinhos=[
        _viz("3554:fa09", sugestao="Teclado", sugestao_tipo="teclado", lido="Teclado"),
        _viz("25a7:fa07", sugestao="Mouse", sugestao_tipo="mouse", lido="Mouse"),
        _viz("2357:012d"),
    ], wifi=[{"no": "", "mhz": 5805, "largura": 80}])


def test_a_cor_nao_e_o_unico_sinal_toda_linha_tem_glifo_e_palavra() -> None:
    linhas = _linhas(_cena_variada())
    assert len(linhas) >= 7
    for ident, linha in linhas.items():
        rotulo = linha.achar(None, "ar-rot")[0]
        assert rotulo.achar("use"), ident
        # a palavra mora no tooltip e no `aria-label` do ícone (desenho aprovado de 05/10/2026)
        assert _fala(rotulo).strip(), ident
        assert linha.achar("div", "ar-faixa")[0].attrs.get("aria-label"), ident


def _usos_da_antena(html: str) -> list[No]:
    return [u for u in _ler(html).achar("use") if u.attrs.get("href") == "#rd-radio"]


def test_a_antena_e_so_do_adaptador_em_todo_campo_que_a_secao_emite() -> None:
    cena = _cena_variada()
    campos = a08.campos_da_secao(cena)
    permitidos = 0
    for chave, valor in campos.items():
        if not isinstance(valor, str):
            continue
        for uso in _usos_da_antena(valor):
            quem = uso.ancestrais()
            na_cabeca = any({"ar-grupo"} <= q.classes() and "data-grupo" in q.attrs for q in quem)
            na_conta = any("canais-do-lugar" in q.classes() for q in quem)
            assert na_cabeca or na_conta, (chave, [q.attrs for q in quem[:3]])
            permitidos += 1
    assert permitidos >= 3 + 3, "a régua ficou cega: faltam as antenas dos adaptadores"
    # o rádio sem tipo e o aparelho `outro` (no ar e desligado) levam o «?»
    assert campos["radio-sala"].count("#rd-ajuda") >= 2


def test_pintar_a_secao_nao_grava_nada(monkeypatch: pytest.MonkeyPatch) -> None:
    gravou: list[str] = []
    for nome in ("_escrever", "gravar_maquina", "gravar_rascunho_da_mesa", "gravar_o_computador",
                 "gravar_maquina_com_descartes"):
        monkeypatch.setattr(maquina, nome, lambda *a, _n=nome, **k: gravou.append(_n) or True)
    cena = _cena_variada()
    a08.campos_da_secao(cena)
    a08.html_dos_canais(cena)
    assert gravou == []


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


def test_as_cores_dos_adaptadores_se_separam_para_quem_nao_ve_cor() -> None:
    cena = _cena(4)
    tokens = sorted({a08.cor_do_adaptador(cena, lug["id"]) for lug in cena["lugares"]})
    assert len(tokens) == 4, tokens
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
    linhas = _linhas(cena)
    r_lido = linhas["3554:fa09"].achar(None, "rotulo")[0]
    assert r_lido.attrs["aria-label"] == "Teclado" and "?" not in r_lido.attrs["aria-label"]
    assert "lido pelo computador" in r_lido.attrs["title"]
    r_dela = linhas["25a7:fa07"].achar(None, "rotulo")[0]
    assert r_dela.attrs["aria-label"] == "Teclado"
    assert "lido pelo computador" not in r_dela.attrs["title"]
    # a webcam não é rádio (desenho aprovado de 05/10/2026): não ganha linha entre os sem fio
    assert "0c45:6366" not in linhas


def test_o_ff_com_produto_leva_o_produto_e_sem_produto_a_palavra_do_censo() -> None:
    com = _viz("2357:012d", produto="802.11ac NIC")
    sem = _viz("1234:5678")
    linhas = _linhas(_cena(vizinhos=[com, sem]))
    r_com = linhas["2357:012d"].achar(None, "rotulo")[0]
    assert r_com.attrs["aria-label"] == "802.11ac NIC"
    assert r_com.achar("use")[0].attrs["href"] == "#rd-ajuda"
    r_sem = linhas["1234:5678"].achar(None, "rotulo")[0]
    assert r_sem.attrs["aria-label"] == a08.ESPECIE_DESCONHECIDA == "Não identificado"
    assert "Sem nome" not in a08.html_dos_canais(_cena(vizinhos=[com, sem]))


def test_o_wifi_do_nm_e_o_vizinho_do_mesmo_no_sao_uma_linha_so() -> None:
    no = ENDERECO_DO_TECLADO
    cena = _cena(vizinhos=[_viz("2357:012d", no=no)],
                 wifi=[{"no": no, "mhz": 5805, "largura": 80},
                       {"no": "", "mhz": 2437, "largura": 20}])
    linhas = _linhas(cena)
    outros = [i for i in linhas if i not in ("c1", "c2", "c3", "c4")]
    # o Wi-Fi de 5 GHz fica fora da faixa e não atrapalha: sem linha (desenho de 05/10/2026)
    assert outros == ["wifi-1"]
    assert _fala(linhas["wifi-1"]).count(a08.NOME_DO_WIFI) >= 1
    banda = {int(m.group(1)) for c in _celulas(linhas["wifi-1"])
             if (m := re.match(r"Canal (\d+) .* ocupado aqui", c.attrs.get("title", "")))}
    assert (min(banda), max(banda) + 1) == (25, 46)
    assert "2,4 GHz" in _fala(linhas["wifi-1"]) and "canal 6" in _fala(linhas["wifi-1"])


def test_o_receptor_e_o_wifi_sem_leitura_dizem_a_verdade() -> None:
    cena = _cena(vizinhos=[_viz("3554:fa09", tipo="teclado", nome="Teclado"),
                           _viz("2357:012d", tipo="wifi", nome="Wi-Fi")])
    linhas = _linhas(cena)
    assert a08.faixas_do_ar.NAO_DESCOBERTA in _fala(linhas["3554:fa09"])
    assert a08.faixas_do_ar.SEM_REDE in _fala(linhas["2357:012d"])
    assert not _celulas(linhas["3554:fa09"]) and not _celulas(linhas["2357:012d"])


def test_adaptador_sem_mapa_diz_que_nao_se_mede_e_nunca_zero_evitados() -> None:
    cena = _cena(2)
    cena["evitados"] = [v for v in cena["evitados"] if v["lugar"] != "L2"]
    cena["canais_medidos"]["L2"] = False
    linhas = _linhas(cena)
    assert a08.faixas_do_ar.NAO_SE_MEDE in _fala(linhas["c3"])
    assert "/79" not in _fala(linhas["c3"]) and not _celulas(linhas["c3"])
    assert "/79" in _fala(linhas["c1"])


def test_com_zero_adaptadores_nao_ha_regua() -> None:
    cena = _cena(3)
    cena["lugares"] = []
    assert a08.html_dos_canais(cena) == ""


def test_o_rotulo_de_vizinho_e_botao_e_o_de_aparelho_nao() -> None:
    linhas = _linhas(_cena(vizinhos=[_viz("3554:fa09", sugestao="Teclado", lido="Teclado",
                                          sugestao_tipo="teclado")]))
    assert linhas["c1"].achar("button") == []
    botao = linhas["3554:fa09"].achar("button", "rotulo")[0]
    assert botao.attrs["data-gesto"] == "vizinho-o-que-e"
    assert botao.attrs["data-alvo"] == "3554:fa09"


def test_adaptador_medido_sem_canal_evitado_tem_a_faixa_inteira_boa() -> None:
    """Medido e sem nenhum evitado (79/79) é um fato, e não «não se mede»."""
    cena = _cena(2)
    cena["evitados"] = [v for v in cena["evitados"] if v["lugar"] != "L2"]
    linhas = _linhas(cena)
    assert _selo(linhas["c3"]) == ("Boa 79/79", "boa")
    assert _perdidos(linhas["c3"]) == set()
    assert a08.faixas_do_ar.NAO_SE_MEDE not in _fala(linhas["c3"])
