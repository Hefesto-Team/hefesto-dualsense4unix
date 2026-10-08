#!/usr/bin/env python3
"""A 08 não desenha botão que ninguém atende (AS-QUATRO-LINHAS-DA-08-SEM-DONO-01, 08/10/2026).

Os quatro gestos que ficavam sem atendente (`custo-som`, `custo-vibracao`,
`custo-luz`, `novo-hub`) SAÍRAM do desenho: o som, a vibração e a luz da linha
viraram marcas que só mostram (`<span data-ligada>`), e a face «Hubs e
extensões» não tem o botão «Acrescentar hub». Cada caso diz a mordida.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.interface import conexoes as tela
from hefesto_dualsense4unix.interface.pacotes import GESTOS, a06_navegacao, a08_conexoes, camada

# as fixtures e os ajudantes da régua vizinha: a mesa declarada da seção do rádio
from tests.unit.test_a_secao_do_radio_transplantada import (  # noqa: F401
    U1,
    U2,
    U3,
    _campos,
    _ctx,
    _estado,
    a08,
    mesa,
)

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

SAIRAM = ("custo-som", "custo-vibracao", "custo-luz", "novo-hub")


def _gestos(html: str) -> set[str]:
    return set(re.findall(r'data-gesto="([^"]+)"', html))


def test_a_lista_dos_sem_gesto_ficou_vazia() -> None:
    """MORDIDA: ponha `"novo-hub": "razão"` em `a08_conexoes.SEM_GESTO`."""
    assert a08_conexoes.SEM_GESTO == {}, sorted(a08_conexoes.SEM_GESTO)
    assert a06_navegacao.SEM_GESTO == {}, sorted(a06_navegacao.SEM_GESTO)


def test_os_quatro_nao_estao_na_camada_nem_no_registro() -> None:
    """MORDIDA: devolva `("08-conexoes.html", "custo-som"): _T` à tabela da `camada`."""
    for g in SAIRAM:
        assert ("08-conexoes.html", g) not in camada.CAMADA, f"{g} voltou à tabela da camada"
        assert ("08-conexoes.html", g) not in GESTOS, f"{g} ganhou atendente"


def test_a_linha_do_controle_mostra_som_vibracao_e_luz_sem_botao(
    request: pytest.FixtureRequest,
) -> None:
    """MORDIDA: troque o `<span class="vaga">` do gerador por `<button data-gesto=...>`."""
    sala = _campos(request.getfixturevalue("mesa"))["radio-sala"]
    assert not (_gestos(sala) & set(SAIRAM)), _gestos(sala) & set(SAIRAM)
    vagas = re.findall(r'<span class="vaga (?:som|haptica)[^"]*"[^>]*>', sala)
    assert vagas, "a linha perdeu as marcas de som e vibração"
    for tag in vagas:
        assert 'role="img"' in tag and "aria-label=" in tag and "aria-pressed" not in tag, tag
    assert any("data-ligada" in t for t in vagas), "nenhuma marca acesa: a ponte não aparece"
    assert 'class="vaga som alem"' in sala, "a marca além do limite sumiu"


def test_a_marca_da_luz_diz_o_que_o_daemon_publica(request: pytest.FixtureRequest) -> None:
    """A luz da linha é a do ``lightbar_on`` de cada controle; sem fonte, acesa (nunca «desligada»).

    MORDIDA: devolva ``"luz": True`` fixo em ``_aparelhos_da_cena`` — o P2 de barra apagada volta
    a aparecer aceso.
    """
    estado = _estado()
    por_uniq = {c["uniq"]: c for c in estado["controllers"]}
    por_uniq[U2].update(lightbar_on=False, lightbar_source="sysfs")
    por_uniq[U3].update(lightbar_on=True, lightbar_source="desired")
    sala = request.getfixturevalue("mesa").campos_do_radio(_ctx(estado))["radio-sala"]

    def marca(uniq: str) -> str:
        achadas = re.findall(rf'<span class="selo-zero"[^>]*data-alvo="{uniq}"[^>]*>', sala)
        assert len(achadas) == 1, f"{uniq}: {achadas}"
        return achadas[0]

    assert "data-ligada" in marca(U1) and ": ligada" in marca(U1), marca(U1)
    assert "data-ligada" not in marca(U2) and ": desligada" in marca(U2), marca(U2)
    assert "data-ligada" in marca(U3) and ": ligada" in marca(U3), marca(U3)


def test_nenhum_gesto_da_sala_fica_sem_atendente(request: pytest.FixtureRequest) -> None:
    """MORDIDA: acrescente `data-gesto="inventado"` a uma marca da linha."""
    sala = _campos(request.getfixturevalue("mesa"))["radio-sala"]
    sem_dono = {g for g in _gestos(sala) if ("08-conexoes.html", g) not in GESTOS}
    assert not sem_dono, f"gesto sem atendente na sala: {sorted(sem_dono)}"


def test_o_microfone_continua_botao_com_dono(request: pytest.FixtureRequest) -> None:
    """O `custo-mic` TEM atendente e fica clicável (mordida: tire-lhe o `@gesto`)."""
    assert ("08-conexoes.html", "custo-mic") in GESTOS
    assert 'data-gesto="custo-mic"' in _campos(request.getfixturevalue("mesa"))["radio-sala"]


def test_a_face_dos_hubs_so_mostra_e_nao_tem_o_botao_de_acrescentar() -> None:
    """MORDIDA: devolva o `<button ... data-gesto="novo-hub">` a `conexoes.html_do_mapa`."""
    html = tela.html_do_mapa(
        [{"nome": "Traseira", "portas": [1, 2]}],
        quem_esta={}, extensoes={"1": "2"}, veredito_de=lambda numero, esticada: ("", numero, ""),
        rotulos={"vazia": "vazia", "por_extensao": "ext", "nova_entrada": "nova"},
        dicas={"esticada": "", "enumera": "", "nova_entrada": ""})
    assert "Hubs e extensões" in html, "a face dos hubs sumiu"
    assert "Acrescentar hub" not in html and "novo-hub" not in html
    assert "<button" not in html.split("Hubs e extensões")[1].split("mm-grade")[0]


def test_a_pagina_da_bancada_nao_tem_os_quatro() -> None:
    """MORDIDA: rode o gerador com o botão devolvido (`aba08.py`) e regenere o mockup."""
    from hefesto_dualsense4unix.interface import onde

    pagina = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    achados = _gestos(pagina) & set(SAIRAM)
    assert not achados, f"a bancada voltou a desenhar {sorted(achados)}"
    assert "Acrescentar hub" not in pagina


def test_a_marca_acesa_se_distingue_da_apagada_e_nao_parece_botao(
    request: pytest.FixtureRequest,
) -> None:
    """No WebKit: a marca ligada é de borda cheia, a apagada tracejada, e as duas só dizem.

    MORDIDA: apague do CSS (`aba08.py`) o bloco `.radio span.vaga[data-ligada]`, ou o
    `cursor:help` — a marca acesa volta a parecer apagada, ou a parecer botão.
    """
    import json

    from hefesto_dualsense4unix.interface import onde
    from tests.unit.test_a_conexoes_cabe_na_tela import _no_webkit

    sala = _campos(request.getfixturevalue("mesa"))["radio-sala"]
    marca = r'<span class="(?:vaga|selo-zero)[^>]*>.*?</span>(?:</span>)?'
    pedaco = "".join(re.findall(marca, sala))
    assert pedaco, "a sala não trouxe nenhuma marca"
    pedaco += ('<span class="vaga haptica" role="img" aria-label="x" data-alvo="z">v</span>'
               '<span class="selo-zero" role="img" aria-label="y" data-alvo="z">l</span>')
    js = ("(function(){const d=document.createElement('div');d.className='radio';"
          f"d.innerHTML={json.dumps(pedaco)};document.body.appendChild(d);"
          "const e=(s)=>[...d.querySelectorAll(s)].map(x=>{const c=getComputedStyle(x);"
          "return [x.className,x.hasAttribute('data-ligada'),c.borderTopStyle,c.cursor]});"
          "return JSON.stringify({vagas:e('.vaga'),selos:e('.selo-zero')})})()")
    lidas = _no_webkit(onde.pagina("08-conexoes.html"), (1200, 800), [js])
    dados = lidas[-1] if isinstance(lidas[-1], dict) else json.loads(lidas[-1])
    for grupo in ("vagas", "selos"):
        acesas = [x for x in dados[grupo] if x[1]]
        apagadas = [x for x in dados[grupo] if not x[1]]
        assert acesas and apagadas, f"{grupo}: faltou uma acesa e uma apagada: {dados[grupo]}"
        assert {x[2] for x in acesas} == {"solid"}, acesas
        assert {x[2] for x in apagadas} == {"dashed"}, apagadas
        assert {x[3] for x in acesas + apagadas} == {"help"}, dados[grupo]
