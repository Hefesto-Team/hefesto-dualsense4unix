#!/usr/bin/env python3
"""A 08 não desenha botão que ninguém atende (AS-QUATRO-LINHAS-DA-08-SEM-DONO-01, 08/10/2026).

Os três gestos que ficavam sem atendente (`custo-som`, `custo-vibracao`,
`custo-luz`) SAÍRAM do desenho: o som, a vibração e a luz da linha viraram marcas que só
mostram (`<span data-ligada>`). O quarto, `novo-hub`, VOLTOU em 08/10/2026 (A-08-MOSTRA-O-DESENHO…
-01) com dono: abre a pergunta curta, e o ato é da `LogicaDoMapa`. Cada caso diz a mordida.
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

SAIRAM = ("custo-som", "custo-vibracao", "custo-luz")
VOLTARAM = ("novo-hub", "novo-hub-gravar", "novo-hub-cancelar")


def _gestos(html: str) -> set[str]:
    return set(re.findall(r'data-gesto="([^"]+)"', html))


def test_a_lista_dos_sem_gesto_ficou_vazia() -> None:
    """MORDIDA: ponha `"novo-hub": "razão"` em `a08_conexoes.SEM_GESTO`."""
    assert a08_conexoes.SEM_GESTO == {}, sorted(a08_conexoes.SEM_GESTO)
    assert a06_navegacao.SEM_GESTO == {}, sorted(a06_navegacao.SEM_GESTO)


def test_os_tres_nao_estao_na_camada_nem_no_registro() -> None:
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
    """A luz da linha é a que o motor das outras abas diz; sem fonte, acesa (nunca «desligada»).

    MORDIDA: devolva ``"luz": True`` fixo em ``_aparelhos_da_cena`` — o P2 de barra apagada volta
    a aparecer aceso.
    """
    estado = _estado()
    por_uniq = {c["uniq"]: c for c in estado["controllers"]}
    por_uniq[U2].update(lightbar_on=False, lightbar_source="sysfs", lightbar_rgb=[0, 0, 255])
    por_uniq[U3].update(lightbar_on=True, lightbar_source="desired", lightbar_rgb=[0, 0, 255])
    sala = request.getfixturevalue("mesa").campos_do_radio(_ctx(estado))["radio-sala"]
    assert "data-ligada" in _a_marca_da_luz(sala, U1) and ": ligada" in _a_marca_da_luz(sala, U1)
    assert "data-ligada" not in _a_marca_da_luz(sala, U2)
    assert ": desligada" in _a_marca_da_luz(sala, U2)
    assert "data-ligada" in _a_marca_da_luz(sala, U3) and ": ligada" in _a_marca_da_luz(sala, U3)


def _a_marca_da_luz(sala: str, uniq: str) -> str:
    achadas = re.findall(rf'<span class="selo-zero"[^>]*data-alvo="{uniq}"[^>]*>', sala)
    assert len(achadas) == 1, f"{uniq}: {achadas}"
    return achadas[0]


def test_a_marca_da_luz_e_a_mesma_resposta_das_outras_abas(
    request: pytest.FixtureRequest,
) -> None:
    """A barra preta com fonte nossa é «apagada» na Iluminação e na Perfis; na 08 também.

    E a Steam segurando o controle não vira «desligada»: o motor diz que não sabe.
    MORDIDA: troque, em ``_a_luz_acesa``, a pergunta ao motor por ``bool(c.get("lightbar_on"))``
    — o P2 de barra preta volta a aparecer aceso.
    """
    from hefesto_dualsense4unix.interface.cartao_do_controle import rotulo_lightbar
    from hefesto_dualsense4unix.interface.pacotes import a04_iluminacao

    estado = _estado()
    por_uniq = {c["uniq"]: c for c in estado["controllers"]}
    por_uniq[U2].update(lightbar_on=True, lightbar_source="desired", lightbar_rgb=[0, 0, 0])
    por_uniq[U3].update(lightbar_on=False, lightbar_source="sysfs", lightbar_rgb=[0, 0, 255],
                        lightbar_disputada=True)
    assert a04_iluminacao.estado_da_tira(
        rotulo_lightbar(por_uniq[U2], estado)[0]) == a04_iluminacao.APAGADA
    sala = request.getfixturevalue("mesa").campos_do_radio(_ctx(estado))["radio-sala"]
    assert "data-ligada" not in _a_marca_da_luz(sala, U2), _a_marca_da_luz(sala, U2)
    assert "data-ligada" in _a_marca_da_luz(sala, U3), _a_marca_da_luz(sala, U3)


def test_nenhum_gesto_da_sala_fica_sem_atendente(request: pytest.FixtureRequest) -> None:
    """MORDIDA: acrescente `data-gesto="inventado"` a uma marca da linha."""
    sala = _campos(request.getfixturevalue("mesa"))["radio-sala"]
    sem_dono = {g for g in _gestos(sala) if ("08-conexoes.html", g) not in GESTOS}
    assert not sem_dono, f"gesto sem atendente na sala: {sorted(sem_dono)}"


def test_o_microfone_continua_botao_com_dono(request: pytest.FixtureRequest) -> None:
    """O `custo-mic` TEM atendente e fica clicável (mordida: tire-lhe o `@gesto`)."""
    assert ("08-conexoes.html", "custo-mic") in GESTOS
    assert 'data-gesto="custo-mic"' in _campos(request.getfixturevalue("mesa"))["radio-sala"]


def test_os_tres_do_hub_tem_dono_na_camada_e_no_registro() -> None:
    """MORDIDA: tire `novo-hub-gravar` do `camada.py` ou o `@gesto` dele do pacote."""
    for g in VOLTARAM:
        assert ("08-conexoes.html", g) in camada.CAMADA, f"{g} saiu da tabela da camada"
        assert ("08-conexoes.html", g) in GESTOS, f"{g} ficou sem atendente"


def test_a_face_dos_hubs_tem_o_botao_de_acrescentar_com_ou_sem_extensao() -> None:
    """MORDIDA: faça `html_do_mapa` só desenhar a face dos hubs `if houver_extensao:` (o defeito
    de antes)."""
    for extensoes in ({}, {"1": "1a"}):
        html = tela.html_do_mapa(
            [{"nome": "Traseira", "portas": [1, 2]}],
            quem_esta={}, extensoes=extensoes,
            veredito_de=lambda numero, esticada: ("", numero, ""),
            rotulos={"vazia": "vazia", "por_extensao": "ext", "nova_entrada": "nova"},
            dicas={"esticada": "", "enumera": "", "nova_entrada": ""})
        assert "Hubs e extensões" in html, "a face dos hubs sumiu"
        cabecalho = html.split("Hubs e extensões")[1].split("mm-grade")[0]
        assert 'data-gesto="novo-hub"' in cabecalho and "Acrescentar hub" in cabecalho
        assert 'aria-expanded="false"' in cabecalho and "hub-pergunta" not in html


def test_a_pagina_da_bancada_nao_tem_os_tres_que_sairam() -> None:
    """MORDIDA: rode o gerador com o botão devolvido (`aba08.py`) e regenere o mockup."""
    pagina = (RAIZ / "mockup" / "08-conexoes.html").read_text(encoding="utf-8")
    achados = _gestos(pagina) & set(SAIRAM)
    assert not achados, f"a bancada voltou a desenhar {sorted(achados)}"
    assert set(VOLTARAM) <= _gestos(pagina), "o desenho perdeu o botão do hub ou a pergunta"


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
