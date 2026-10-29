"""Toda escolha da janela da extensão vale na hora e fica gravada.

A-ESCOLHA-DA-JANELA-DA-EXTENSAO-GRAVA-NA-HORA-01 (28/10/2026). Medido no ``interface.log``: a janela
da Lovense mostrava o Touchpad, o Sacudir e o Inclinar em «Direto» e a barra «Força» dos toques
mais baixa, e o ``opcoes.json`` seguia com «Nenhum» e 100: a escolha ia ao rascunho e esperava um
Guardar que ela nunca apertou. Agora cada gesto de escolha grava na hora, e a régua percorre todo
controle que a janela desenha, de todo tipo, nas abas todas, inclusive o que só aparece quando
outro o pede.

E a faixa «Ao vivo» depois de trocar de aba: a série do gesto vivo recomeça em cada página, e o
arrastar caía inteiro como fora de ordem até a série nova passar a antiga.

MORDIDAS (28/10/2026, executadas sobre a cura e devolvidas):

- o ``_guardar_a_opcao_da_modificacao`` tirado do ``guardar_opcao_da_modificacao`` reprova
  ``test_todo_controle_da_janela_grava_o_que_mostra``;
- o mesmo tirado do ``modo_do_livre_da_modificacao`` e do ``gravar_o_livre_da_modificacao``
  reprova ``test_o_modo_e_a_forma_do_ao_vivo_gravam_na_hora``;
- a ordem do arrastar pela série do vivo (``vivo <= ultimo_vivo``) reprova
  ``test_a_faixa_ao_vivo_segue_depois_de_trocar_de_aba``.
"""

from __future__ import annotations

import json
import re
from typing import Any

from hefesto_dualsense4unix.interface.desenho_da_experimental import janela_pintada
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _Ponte,
    janela,
)

MOD = "toque"
FORMAS = {"Pulso": [[1.0, 0.2], [0.0, 0.2]], "Onda": [[0.5, 0.3]], "Nenhum": []}
PADRAO, MINIMO, MAXIMO = "padrao", "minimo", "maximo"  # (noqa-acento)


def _opcao(id_: str, rotulo: str, tipo: str, grupo: str, de_fabrica: Any,
           **extra: Any) -> dict[str, Any]:
    return {"id": id_, "rotulo": rotulo, "tipo": tipo, "grupo": grupo, PADRAO: de_fabrica, **extra}


SUAVE = {"escolhas": ["Nenhum", "Direto", "Suave"]}
OPCOES = [
    _opcao("ligar", "Ligar", "ligado", "Brinquedos", True),
    _opcao("servidor", "Servidor", "escolha", "Ligação", "Adaptador USB",
           escolhas=["Adaptador USB", "Intiface Central"]),
    _opcao("endereco", "Endereço", "endereco", "Ligação", "127.0.0.1:12345",
           aparece_com={"servidor": "Intiface Central"}),
    _opcao("toques", "Toque de cada botão", "por_botao", "Toques", {"cross": "Pulso"},
           botoes=["cross", "circle"], formas=FORMAS),
    _opcao("touchpad", "Touchpad", "escolha", "Toques", "Nenhum", **SUAVE),
    _opcao("sacudir", "Sacudir", "escolha", "Toques", "Nenhum", **SUAVE),
    _opcao("forca", "Força", "deslizante", "Toques", 100, passo=5, unidade="%",
           **{MINIMO: 0, MAXIMO: 100}),
    _opcao("teto", "Teto", "numero", "Força", 3),
    _opcao("cor", "Cor", "cor", "Luz", "#ff0000"),
    {"id": "ao-vivo", "rotulo": "Ao vivo", "tipo": "livre", "modos": True},
]
CONTROLE = re.compile(
    r'<(select|input|span)\b([^>]*\bdata-gesto="guardar-opcao-da-modificacao"[^>]*)>')


def _atributo(atributos: str, nome: str) -> str | None:
    achado = re.search(rf'\b{nome}="([^"]*)"', atributos)
    return achado.group(1) if achado else None


def _controles(html: str) -> dict[str, tuple[str, str, str]]:
    """``{data-v: (tag, atributos, miolo)}`` de cada controle de escolha na janela."""
    return {str(_atributo(m.group(2), "data-v")): (
        m.group(1), m.group(2),
        html[m.end():html.index("</select>", m.end())] if m.group(1) == "select" else "")
        for m in CONTROLE.finditer(html)}


def _gesto(tag: str, atributos: str, miolo: str) -> tuple[dict[str, Any], Any]:
    """O evento que a ponte manda para mudar o controle, e o valor que a janela deve mostrar."""
    if tag == "span":
        return {"evento": "click"}, "inverte"
    if tag == "select":
        escolhas = re.findall(r"<option( selected)?>([^<]*)</option>", miolo)
        nova = next(nome for marcada, nome in escolhas if not marcada)
        return {"evento": "change", "valor": nova}, nova
    tipo = _atributo(atributos, "type")
    if tipo == "range":
        atual = float(_atributo(atributos, "value") or 0)
        minimo = float(_atributo(atributos, "min") or 0)
        novo = minimo + 5 if atual != minimo + 5 else minimo + 10
        return {"evento": "change", "valor": f"{novo:g}"}, novo
    if tipo == "color":
        return {"evento": "change", "valor": "#123456"}, "#123456"
    if "ext-end" in atributos:
        return {"evento": "change", "valor": "10.0.0.2:4321"}, "10.0.0.2:4321"
    return {"evento": "change", "valor": "7"}, 7.0


def _guardado(a07: Any) -> dict[str, Any]:
    from hefesto_dualsense4unix.mods import opcoes

    arquivo = opcoes.caminho(MOD, a07._lugares())
    return dict(json.loads(arquivo.read_text(encoding="utf-8"))) if arquivo.exists() else {}


def _janela(abrir: Any, ponte: _Ponte) -> str:
    return janela_pintada(abrir(ponte)["blocos"])


def test_todo_controle_da_janela_grava_o_que_mostra(janela: Any, ctx: Any) -> None:  # noqa: F811
    """Prova da D-2810-TODA-ESCOLHA-DA-JANELA-DA-EXTENSAO-GRAVA-NA-HORA.

    A MORDIDA da sprint: sem gravar na hora, o ``opcoes.json`` não vê a escolha.
    """
    a07, instalar, abrir = janela
    instalar(opcoes=OPCOES)
    ponte = _Ponte(VIVO)
    feitos: list[str] = []
    while True:
        html = _janela(abrir, ponte)
        faltam = {v: c for v, c in _controles(html).items() if v not in feitos}
        if not faltam:
            break
        data_v, (tag, atributos, miolo) = next(iter(faltam.items()))
        opcao_id, _, botao = data_v.split(":", 1)[1].partition(":")
        antes = _guardado(a07).get(opcao_id)
        evento, esperado = _gesto(tag, atributos, miolo)
        a07.guardar_opcao_da_modificacao(ctx, {"v": data_v, **evento}, ponte)
        feitos.append(data_v)
        guardado = _guardado(a07).get(opcao_id)
        if esperado == "inverte":
            esperado = not (antes if antes is not None else
                            next(o[PADRAO] for o in OPCOES if o["id"] == opcao_id))
        if botao:
            assert isinstance(guardado, dict) and guardado.get(botao) == esperado, \
                f"{data_v}: a janela mostra {esperado!r}, o disco tem {guardado!r}"
        else:
            assert guardado == esperado, \
                f"{data_v}: a janela mostra {esperado!r}, o disco tem {guardado!r}"
        assert "Guarde" not in json.dumps(ponte.chamadas, ensure_ascii=False)
    ids = {v.split(":")[1] for v in feitos}
    assert ids == {o["id"] for o in OPCOES if o["tipo"] != "livre"}, ids
    assert f"{MOD}:toques:circle" in feitos, "o botão de cada linha do por_botao"


def test_o_modo_e_a_forma_do_ao_vivo_gravam_na_hora(janela: Any, ctx: Any) -> None:  # noqa: F811
    """Prova da D-2810-TODA-ESCOLHA-DA-JANELA-DA-EXTENSAO-GRAVA-NA-HORA."""
    a07, instalar, abrir = janela
    instalar(opcoes=OPCOES)
    ponte = _Ponte(VIVO)
    abrir(ponte)
    a07.modo_do_livre_da_modificacao(ctx, {"v": f"{MOD}:ao-vivo:segurar"}, ponte)
    assert _guardado(a07).get("ao-vivo:modo") == "segurar", _guardado(a07)
    a07.gravar_o_livre_da_modificacao(ctx, {"v": f"{MOD}:ao-vivo"}, ponte)
    for n, valor in enumerate((20, 80, 50), start=1):
        a07.mover_o_livre_da_modificacao(
            ctx, {"v": f"{MOD}:ao-vivo", "valor": str(valor), "vivo": str(n),
                  "carimbo": str(n)}, ponte)
    carga = a07.gravar_o_livre_da_modificacao(ctx, {"v": f"{MOD}:ao-vivo"}, ponte)
    assert "Guarde" not in carga["recado"], carga["recado"]
    assert "Meu 1" in _guardado(a07).get("ao-vivo", {}), _guardado(a07)
    a07.esquecer_a_forma_do_livre(ctx, {"v": f"{MOD}:ao-vivo:Meu 1"}, ponte)
    assert "Meu 1" not in _guardado(a07).get("ao-vivo", {}), _guardado(a07)


def test_a_faixa_ao_vivo_segue_depois_de_trocar_de_aba(janela: Any, ctx: Any) -> None:  # noqa: F811
    """A página nova recomeça a série do vivo; o carimbo do evento segue subindo."""
    a07, instalar, abrir = janela
    instalar(opcoes=OPCOES)
    ponte = _Ponte(VIVO)
    abrir(ponte)

    def mover(valor: int, vivo: int, carimbo: float) -> None:
        a07.mover_o_livre_da_modificacao(
            ctx, {"v": f"{MOD}:ao-vivo", "valor": str(valor), "vivo": str(vivo),
                  "carimbo": str(carimbo), "evento": "input"}, ponte)

    mover(30, 500, 1000.0)
    a07.soltar_o_livre_da_modificacao(
        ctx, {"v": f"{MOD}:ao-vivo", "valor": "30", "carimbo": "1001", "evento": "change"}, ponte)
    mover(60, 1, 90_000.0)
    mover(70, 2, 90_010.0)
    feitas = [(p["valor"], p["soltou"]) for m, p in ponte.chamadas if m == "mods.livre"]
    assert feitas == [(0.3, False), (0.3, True), (0.6, False), (0.7, False)], feitas
