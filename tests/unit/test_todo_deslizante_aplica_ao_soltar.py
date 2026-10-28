"""Todo deslizante e toda lista da interface aplicam ao soltar (27/10/2026).

A ponte manda o gesto no `change`, que no `<input type=range>` dispara ao soltar e no `<select>` ao
escolher. Um campo desses sem gesto que o pacote atende só pinta o número ao lado: a pessoa mexe e o
controle não sente. Esta régua passa por todo desenho de aba (`mockup/NN-*.html`) e por toda página
publicada, e as exceções moram em :data:`EXCECOES`, cada uma com o motivo.

O criador do gatilho é o caso que faltava: as quatro barras e a lista «Partir de» mandam o `sentir`
com o que está na área de criar, no controle escolhido, sem gravar.

MORDIDAS: tirar o gesto de uma barra do criador (no desenho ou na publicada), tirar uma exceção do
formulário da 08 ou trocar o `data-hef-gesto` de um `<select>` da 10 por nada reprova a régua; o
`sentir` que não lê a barra nova, ou que toca de novo no `click` do mesmo arrasto, reprova o caso do
criador.
"""

from __future__ import annotations

import pathlib
import re
import sys
from html.parser import HTMLParser
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

from hefesto_dualsense4unix.interface import onde

DESENHO = onde.BANCADA
PAGINA_DO_CRIADOR = "03-gatilhos.html"
UNIQ = "aa:bb:cc:00:00:01"

ATRIBUTOS_DE_GESTO = ("data-gesto", "data-papel", "data-hef-vivo", "data-hef-gesto")

FORMULARIO_DA_08 = ("campo de formulário: o botão do diálogo o lê ao confirmar, e o desenho da 08 "
                    "não se toca nesta leva")

EXCECOES: dict[tuple[str, str, str], str] = {
    # fica: o campo do diálogo da 08 se lê ao confirmar, e não ao soltar
    **{(lado, "08-conexoes.html", c): FORMULARIO_DA_08
       for lado in ("desenho", "publicado")
       for c in ("hub-entrada", "acionador-quem", "lugar")},
}


class _Campos(HTMLParser):
    """Os `<input type=range>` e os `<select>` não desabilitados, com a linha e os atributos."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.campos: list[tuple[int, str, dict[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if "disabled" in a:
            return
        if tag == "select" or (tag == "input" and a.get("type", "").lower() == "range"):
            self.campos.append((self.getpos()[0], tag, a))


def _nome(a: dict[str, str]) -> str:
    return a.get("data-linha") or a.get("data-campo") or a.get("data-hef") or a.get("class", "")


def _paginas() -> list[tuple[str, pathlib.Path]]:
    """O desenho e o publicado de cada página, menos a que saiu do produto e não tem mais pacote."""
    from monta import PAGINAS_QUE_SAIRAM

    desenhos = [p for p in onde.paginas()
                if re.match(r"\d\d-", p.name) and p.name not in PAGINAS_QUE_SAIRAM]
    publicadas = [p for p in onde.paginas(publicado=True) if p.name not in PAGINAS_QUE_SAIRAM]
    return [("desenho", p) for p in desenhos] + [("publicado", p) for p in publicadas]


def _sem_quem_atenda() -> dict[tuple[str, str, str], str]:
    """`(lado, página, campo)` → o que falta, para todo campo sem gesto que o pacote atenda."""
    import pacotes

    fora: dict[tuple[str, str, str], str] = {}
    for lado, arq in _paginas():
        leitor = _Campos()
        leitor.feed(arq.read_text(encoding="utf-8"))
        for linha, tag, a in leitor.campos:
            gestos = [a[k] for k in ATRIBUTOS_DE_GESTO if a.get(k)]
            atendidos = [g for g in gestos if pacotes.gesto_da_pagina(arq.name, g) is not None]
            if atendidos:
                continue
            falta = (f"{tag} sem gesto" if not gestos
                     else f"{tag} com {gestos} que nenhum pacote de {arq.name} atende")
            fora[(lado, arq.name, _nome(a))] = f"{lado}/{arq.name}:{linha}: {falta}"
    return fora


def test_as_paginas_existem_para_a_regua_ler() -> None:
    nomes = {(lado, p.name) for lado, p in _paginas()}
    assert ("desenho", PAGINA_DO_CRIADOR) in nomes and ("publicado", PAGINA_DO_CRIADOR) in nomes
    assert len([n for n in nomes if n[0] == "desenho"]) >= 9, nomes


def test_todo_deslizante_e_toda_lista_tem_gesto_que_o_pacote_atende() -> None:
    fora = _sem_quem_atenda()
    sem_motivo = sorted(v for k, v in fora.items() if k not in EXCECOES)
    assert not sem_motivo, (
        "campo que a pessoa mexe e o controle não sente; dê o gesto, ou ponha em EXCECOES "
        "com o motivo:\n  " + "\n  ".join(sem_motivo))


def test_nenhuma_excecao_sobra() -> None:
    """A exceção que não falta mais sai da tabela: senão ela esconde o próximo campo mudo."""
    fora = _sem_quem_atenda()
    sobra = sorted(f"{k}: {m}" for k, m in EXCECOES.items() if k not in fora)
    assert not sobra, "a exceção não é mais preciso; tire-a de EXCECOES:\n  " + "\n  ".join(sobra)


def test_os_selects_da_10_aplicam_pelo_data_hef_gesto() -> None:
    """Os dois `<select>` estreitos da 10 levam o gesto em `data-hef-gesto`, e a régua os aceita."""
    leitor = _Campos()
    leitor.feed((DESENHO / "10-perfis.html").read_text(encoding="utf-8"))
    pelo_hef = [a for _l, tag, a in leitor.campos if tag == "select" and a.get("data-hef-gesto")]
    assert len(pelo_hef) >= 2, pelo_hef


def _criador(doc: str) -> dict[str, dict[str, str]]:
    """`data-linha` → atributos de cada campo da área de criar, com o `value` que a ponte lê."""
    inicio = doc.index('id="criar-gatilhos"')
    trecho = doc[inicio:doc.index('class="g2-sentir"', inicio)]
    campos: dict[str, dict[str, str]] = {}
    for tag in re.finditer(r"<(input|select)\b[^>]*>", trecho):
        a = dict(re.findall(r'([a-z-]+)="([^"]*)"', tag.group(0)))
        if "data-linha" not in a:
            continue
        if tag.group(1) == "select":
            resto = trecho[tag.end():trecho.index("</select>", tag.end())]
            marcada = re.search(r'<option value="([^"]*)" selected', resto)
            a["value"] = marcada.group(1) if marcada else ""
        campos[a["data-linha"]] = a
    return campos


def _carga(campos: dict[str, dict[str, str]], linha: str, valor: str,
           evento: str) -> dict[str, Any]:
    """O que a ponte manda quando a pessoa solta aquele campo, como `carga_do_alvo` monta."""
    a = campos[linha]
    forma = {k: v.get("value", "") for k, v in campos.items()}
    forma[linha] = valor
    tipo = "select" if linha == "partir" else "input"
    return {"gesto": a.get("data-gesto", ""), "hefForma": a.get("data-hef-forma", ""),
            "tipo": tipo, "evento": evento, "valor": valor, "uniq": UNIQ,
            "forma": forma if a.get("data-hef-forma") == "criar-gatilhos" else None}


class _Ponte:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def trigger_set_detalhado(self, *a: Any, **k: Any) -> tuple[bool, str, dict[str, Any]]:
        self.chamadas.append(("set", a))
        return True, "", {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}

    def trigger_reset_detalhado(self, *a: Any, **k: Any) -> tuple[bool, str, dict[str, Any]]:
        self.chamadas.append(("reset", a))
        return True, "", {"status": "ok", "aplicado_em": [UNIQ], "guardado_em": []}


def _ctx() -> Any:
    from pacotes import Contexto

    mesa = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua", "via": "USB",
             "cor": "starlight-blue", "mascara": "DualSense"}]
    falso = {"uniq": UNIQ, "player": 1, "transport": "usb", "is_primary": True}
    return Contexto(state={"active_profile": ""}, mesa=mesa, conectados=[falso], estados={})


class _Soltar:
    """Solta um campo do criador do desenho e devolve o que o controle recebeu."""

    def __init__(self, campos: dict[str, dict[str, str]]) -> None:
        self.campos = campos

    def __call__(self, linha: str, valor: str,
                 evento: str = "change") -> list[tuple[str, tuple[Any, ...]]]:
        import pacotes

        o = _carga(self.campos, linha, valor, evento)
        assert o["gesto"], f"o campo {linha!r} do criador não manda gesto nenhum ao soltar"
        quem = pacotes.gesto_da_pagina(PAGINA_DO_CRIADOR, o["gesto"])
        assert quem is not None, o["gesto"]
        ponte = _Ponte()
        quem(_ctx(), o, ponte)
        return ponte.chamadas


@pytest.fixture
def soltar(monkeypatch: pytest.MonkeyPatch) -> _Soltar:
    """O criador do desenho, com o toque sem espera."""
    from pacotes import a03_gatilhos

    monkeypatch.setattr(a03_gatilhos, "SENTIR_S", 0.0)
    return _Soltar(_criador((DESENHO / PAGINA_DO_CRIADOR).read_text(encoding="utf-8")))


def test_soltar_a_forca_toca_o_gatilho_com_a_forca_nova(soltar: _Soltar) -> None:
    forca = soltar.campos["forca"]
    baixa, alta = forca["min"], forca["max"]
    com_a_baixa = soltar("forca", baixa)
    com_a_alta = soltar("forca", alta)
    tocou = com_a_alta[:2]
    assert [c[0] for c in tocou] == ["set", "set"], com_a_alta
    assert {c[1][0] for c in tocou} == {"left", "right"}, "o toque vai aos dois gatilhos"
    assert com_a_alta[0][1][1] == soltar.campos["partir"]["value"]
    assert com_a_alta[0][1][2] != com_a_baixa[0][1][2], (
        "a força nova não chegou ao gatilho: o toque leva a barra de antes")


@pytest.mark.parametrize("linha", ["inicio", "fim", "forca", "freq", "partir"])
def test_todo_campo_do_criador_toca_ao_soltar(soltar: _Soltar, linha: str) -> None:
    a = soltar.campos[linha]
    valor = a.get("max") or a["value"]
    chamadas = soltar(linha, valor)
    assert [c[0] for c in chamadas[:2]] == ["set", "set"], (linha, chamadas)


def test_soltar_a_lista_toca_o_efeito_escolhido(soltar: _Soltar) -> None:
    chamadas = soltar("partir", "Weapon")
    assert chamadas[0][1][1] == "Weapon", chamadas


def test_o_click_do_mesmo_arrasto_nao_toca_de_novo(soltar: _Soltar) -> None:
    assert soltar("forca", soltar.campos["forca"]["max"], evento="click") == []
    assert soltar("partir", "Weapon", evento="click") == []
