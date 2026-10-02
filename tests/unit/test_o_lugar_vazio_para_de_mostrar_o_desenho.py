#!/usr/bin/env python3
"""O LUGAR SEM DONO ganha travessão — e o molde nunca alcança o DESENHO."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

UNIQ = "aa:bb:cc:00:00:01"
COM_DONO = {"uniq": UNIQ, "connected": True, "transport": "usb",
            "battery_pct": 95, "inputs": {}, "audio": {}, "speaker": {}}
MESA_COM_DONO = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
                  "via": "USB", "cor": "starlight-blue", "mascara": "DualSense"}]

ESTADO = {"active_profile": "regua", "rumble_policy": "balanceado",
          "controllers": []}

LUGARES = {"p1", "p2", "p3", "p4"}


@pytest.fixture
def pacotes_mod():
    import pacotes

    pacotes._MOLDE.clear()
    pacotes._ALVOS.clear()
    pacotes._LUGARES.clear()
    return pacotes


def test_o_molde_nao_roda_a_pintura_de_quem_nao_tem_lugar(pacotes_mod):
    """FATO DERRUBADO: as funções de pacote NÃO são todas puras."""
    from pacotes import a10_perfis

    ctx = pacotes_mod.Contexto(state=ESTADO, mesa=[], conectados=[], estados={})
    antes = (a10_perfis._PINTADO_PARA, a10_perfis._ULTIMO_TIQUE,
             a10_perfis._ESCOLHIDO)
    assert pacotes_mod.molde_do_lugar("10-perfis.html", ctx, {}) == {}
    depois = (a10_perfis._PINTADO_PARA, a10_perfis._ULTIMO_TIQUE,
              a10_perfis._ESCOLHIDO)
    assert antes == depois, (
        "o molde rodou a pintura da 10-perfis e mexeu na memória dela — no "
        f"tique seguinte o produto repinta o que ela digita. antes={antes} "
        f"depois={depois}")
    assert not pacotes_mod.lugares_da_pagina("10-perfis.html"), (
        "a 10-perfis ganhou lugar de controle — a trava precisa de outra razão")


def _mesa_vazia(pacotes_mod):
    return pacotes_mod.Contexto(state=ESTADO, mesa=[], conectados=[], estados={})


def _o_que_o_piloto_faz(pacotes_mod, carga):
    """A CONTA DE VERDADE, chamada — não replicada."""
    return pacotes_mod.apagar_os_lugares_sem_dono(carga)


def test_com_controle_na_mesa_o_molde_se_cala(pacotes_mod):
    """Com UMA coluna viva, a união das chaves dela é melhor que o molde."""
    ctx = pacotes_mod.Contexto(state=ESTADO, mesa=MESA_COM_DONO,
                               conectados=[COM_DONO], estados={})
    for pagina in sorted(pacotes_mod.PACOTES):
        assert pacotes_mod.molde_do_lugar(pagina, ctx, {}) == {}, (
            f"{pagina}: o molde falou com um controle na mesa — e aí ele "
            "duplica o que a coluna viva já diz")


def test_a_pagina_sem_pacote_continua_devolvendo_none(pacotes_mod):
    """`None` é o estado honesto de uma aba que ninguém pinta — e não mudou."""
    ctx = _mesa_vazia(pacotes_mod)
    assert pacotes_mod.pacote_da_pagina("99-nao-existe.html", ctx) is None
    assert "07-lancadores.html" in pacotes_mod.PACOTES, (
        "a 07 perdeu o pacote — e aí o comentário do piloto voltou a valer")


def test_o_molde_e_o_que_a_aba_pinta_menos_barra_e_html(pacotes_mod):
    """O molde ⊆ o que a aba emite por controle. Nunca um endereço a mais."""
    import casamento

    ctx = _mesa_vazia(pacotes_mod)
    olhadas = []
    for pagina in sorted(pacotes_mod.PACOTES):
        if not pacotes_mod.lugares_da_pagina(pagina):
            continue
        olhadas.append(pagina)
        molde = pacotes_mod.molde_do_lugar(pagina, ctx, {})
        _mesa, da_aba = casamento.do_pacote(pagina, ESTADO)
        assert set(molde) <= set(da_aba), (
            f"{pagina}: o molde alcança {sorted(set(molde) - set(da_aba))}, que "
            "a aba NÃO pinta — é endereço de desenho, não de dado")
    assert len(olhadas) >= 7, (
        f"só {len(olhadas)} páginas com lugar de controle — este teste está "
        "medindo quase nada")


PISO_DO_MOLDE = {
    "01-jogar.html": 3,
    "02-controles.html": 8,
    "03-gatilhos.html": 10,
    "04-iluminacao.html": 4,
    "05-vibracao.html": 4,
    "06-navegacao.html": 0,
    "08-conexoes.html": 6,
    "calibrar-sensores.html": 12,
}


def test_o_molde_de_cada_pagina_nao_encolhe(pacotes_mod):
    """O molde de uma aba inteira podia ir a ZERO sem um teste piscar."""
    ctx = _mesa_vazia(pacotes_mod)
    com_lugar = [p for p in sorted(pacotes_mod.PACOTES)
                 if pacotes_mod.lugares_da_pagina(p)]
    assert set(com_lugar) == set(PISO_DO_MOLDE), (
        f"as páginas com lugar de controle mudaram: {sorted(com_lugar)} — o "
        "piso do molde precisa acompanhar")
    for pagina in com_lugar:
        molde = pacotes_mod.molde_do_lugar(pagina, ctx, {})
        assert len(molde) >= PISO_DO_MOLDE[pagina], (
            f"{pagina}: o molde caiu de {PISO_DO_MOLDE[pagina]} para "
            f"{len(molde)} campos. O lugar vazio voltou a mostrar o desenho "
            f"em {PISO_DO_MOLDE[pagina] - len(molde)} endereços, e nenhuma "
            "outra régua acusaria")


def test_o_travessao_nao_pousa_em_marca_que_o_texto_nao_devolve(pacotes_mod):
    """A CONTENÇÃO NÃO ERA A GARANTIA QUE O TEXTO DIZIA."""
    ctx = _mesa_vazia(pacotes_mod)
    for pagina in sorted(pacotes_mod.PACOTES):
        if not pacotes_mod.lugares_da_pagina(pagina):
            continue
        apaga = pacotes_mod.enderecos_que_o_texto_apaga(pagina)
        molde = pacotes_mod.molde_do_lugar(pagina, ctx, {})
        assert not (set(molde) & apaga), (
            f"{pagina}: o molde alcança {sorted(set(molde) & apaga)} — o "
            "travessão apagaria uma marca que o texto não sabe devolver, e ela "
            "não volta nem quando o controle volta")

    alvos_06 = pacotes_mod.alvos_da_pagina("06-navegacao.html")
    assert "navega" not in pacotes_mod.enderecos_que_o_texto_apaga("06-navegacao.html"), (
        "o `navega` da 06 voltou a ser texto com a bolinha dentro — o travessão "
        "e a bolinha voltam a brigar")
    assert alvos_06.get("navega") == {"html"}, (
        f"o `navega` da 06 perdeu o alvo `html`: {alvos_06.get('navega')}")
    onde_ha_mudo = {
        pagina: sorted(pacotes_mod.enderecos_que_o_texto_apaga(pagina))
        for pagina in sorted(pacotes_mod.PACOTES)
    }
    com_mudo = {k: v for k, v in onde_ha_mudo.items() if v}
    assert com_mudo, (
        "NENHUMA página tem filho mudo sob alvo `texto` — o teste acima passa "
        "por vacuidade, e a exceção que ele mede deixou de ter caso. Se isso é "
        "verdade de propósito (todo elemento com filho mudo ganhou outro alvo), "
        "apague os dois; se não é, alguém apagou desenho.\n"
        f"medido: {onde_ha_mudo}")


def test_o_travessao_nao_pousa_no_fundo_nem_na_barra(pacotes_mod):
    """A composição do conjunto é cobrada, e cada nome tem a sua razão."""
    medidos = {"largura", "altura", "html", "fundo"}
    assert medidos == pacotes_mod.ALVOS_QUE_O_TRAVESSAO_NAO_ATENDE, (
        "o conjunto mudou: cada alvo aqui custou uma medição, e sair dele "
        "devolve um defeito de contador ou de marcação à tela")

    piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
              ).read_text(encoding="utf-8")
    assert "if(el.style.background !== t){ el.style.background = t; return 1; }" \
        in piloto, (
        "o ramo `fundo` do `escrever()` mudou — se ele passou a escrever e "
        "COMPARAR (como o `cor` faz), o travessão deixou de mentir no contador "
        "e este nome pode sair do conjunto")


def test_o_molde_da_gatilhos_muda_com_o_perfil_e_o_cache_sabe(pacotes_mod):
    """O perfil está na chave do cache PORQUE ele muda o molde — medido."""
    pacotes_mod._MOLDE.clear()
    for perfil in ("um-perfil", "outro-perfil"):
        ctx = pacotes_mod.Contexto(
            state={**ESTADO, "active_profile": perfil}, mesa=[], conectados=[],
            estados={})
        pacotes_mod.molde_do_lugar("03-gatilhos.html", ctx, {})
    guardadas = [k for k in pacotes_mod._MOLDE if k[0] == "03-gatilhos.html"]
    assert sorted(guardadas) == [("03-gatilhos.html", "outro-perfil"),
                                 ("03-gatilhos.html", "um-perfil")], (
        "o cache do molde deixou de separar por perfil — a Gatilhos passa a "
        f"servir o molde do perfil anterior. guardadas={sorted(guardadas)}")


def test_a_aba_que_ja_emite_coluna_dispensa_o_molde(pacotes_mod):
    """A segunda guarda de `molde_do_lugar`, que não tinha régua nenhuma."""
    ctx = _mesa_vazia(pacotes_mod)
    ja_tem = {"colunas": {"p1": {"bateria": "95%"}}}
    assert pacotes_mod.molde_do_lugar("02-controles.html", ctx, ja_tem) == {}, (
        "a aba já emitiu coluna sem controle nenhum — o molde tem de se calar, "
        "senão ele compete com o dado de verdade pelo mesmo endereço")
    assert pacotes_mod.molde_do_lugar("02-controles.html", ctx, {})


def test_a_barra_e_o_html_ficam_de_fora(pacotes_mod):
    """`largura` e `html` não aceitam travessão, e as duas foram medidas.

    `bateria-barra` da `02-controles` é `data-hef-alvo="largura"`: o piloto
    monta `el.style.width = "—%"`, o CSSOM recusa, a barra fica na largura do
    mockup e o contador de pintura soma +1 por tique para sempre.
    `players` da `04-iluminacao` é `html`: o travessão APAGA os quatro botões
    de jogador.
    """
    ctx = _mesa_vazia(pacotes_mod)
    controles = pacotes_mod.molde_do_lugar("02-controles.html", ctx, {})
    assert "bateria" in controles, "a bateria é TEXTO e tem de ganhar travessão"
    assert "bateria-barra" not in controles, (
        "a barra entrou no molde: `width: \"—%\"` é recusado pelo CSSOM e o "
        "contador de pintura passa a mentir a cada tique")

    ilumina = pacotes_mod.molde_do_lugar("04-iluminacao.html", ctx, {})
    assert "hex" in ilumina
    assert "players" not in ilumina, (
        "`players` é `data-hef-alvo=\"html\"` — travessão ali apaga os quatro "
        "botões de jogador")


def test_o_molde_nao_toca_o_desenho_da_vibracao(pacotes_mod):
    """O achado que derruba o caminho ÓBVIO desta cura."""
    ctx = _mesa_vazia(pacotes_mod)
    molde = pacotes_mod.molde_do_lugar("05-vibracao.html", ctx, {})
    assert molde, "a Vibração ficou sem molde — ver `_LUGAR_DE_MENTIRA`"
    for endereco in ("testar", "parar", "forca", "desenho", "lado", "motor"):
        assert endereco not in molde, (
            f"o molde alcançou `{endereco}`, que é DESENHO e não dado — a tela "
            "perderia um botão ou o controle inteiro")

    from hefesto_dualsense4unix.interface import onde

    doc = onde.pagina("05-vibracao.html", publicado=True).read_text(encoding="utf-8")
    for endereco in ("testar", "parar", "forca", "desenho"):
        assert (f'data-papel="{endereco}"' in doc
                or f'data-hef="{endereco}"' in doc), (
            f"a página publicada não tem mais `{endereco}` — este teste virou "
            "vácuo e a razão dele mudou")


def test_o_molde_escreve_o_travessao_do_desenho(pacotes_mod):
    """O texto do vazio é DELA, e já está no desenho — nada novo nasce aqui."""
    from hefesto_dualsense4unix.interface import onde

    doc = onde.pagina("02-controles.html", publicado=True).read_text(encoding="utf-8")
    vazio = re.search(r'data-controle="p3".*?</div>\s*</div>', doc, re.S)
    assert vazio is not None, "o lugar P3 sumiu da página publicada"
    assert f">{pacotes_mod.TRAVESSAO}<" in vazio.group(0), (
        "o desenho deixou de usar o travessão no lugar vazio — o texto de tela "
        "é dela, e esta cura tem de seguir o que o desenho faz")

    ctx = _mesa_vazia(pacotes_mod)
    molde = pacotes_mod.molde_do_lugar("02-controles.html", ctx, {})
    assert set(molde.values()) == {pacotes_mod.TRAVESSAO}


@pytest.mark.parametrize("pagina",  # (noqa-acento): nome do argumento
                         ["01-jogar.html", "02-controles.html",
                          "04-iluminacao.html", "05-vibracao.html"])
def test_os_quatro_lugares_ficam_no_travessao_e_marcados(pacotes_mod, pagina):
    """O desfecho que a foto cobra: nada de dado, e a moldura de vazio acesa.

    A `carga["vazios"]` é o que faz o piloto marcar `data-conectado="nao"` e a
    classe `off`. Emitir o molde nas colunas de `p1`…`p4` a esvaziaria — é por
    isso que ele mora em `LUGAR_SEM_DONO`.
    """
    ctx = _mesa_vazia(pacotes_mod)
    bruto = pacotes_mod.pacote_da_pagina(pagina, ctx)
    assert bruto is not None
    carga = pacotes_mod.normalizar(bruto, {})

    assert pacotes_mod.LUGAR_SEM_DONO in carga["colunas"], (
        f"{pagina}: o molde não chegou à carga")
    assert not (LUGARES & set(carga["colunas"])), (
        f"{pagina}: um lugar do desenho veio ocupado na carga — o piloto vai "
        "deixar de marcá-lo como vazio e a moldura fica de CONECTADO")

    carga = _o_que_o_piloto_faz(pacotes_mod, carga)
    assert sorted(carga["vazios"]) == sorted(LUGARES), (
        f"{pagina}: os quatro lugares tinham de estar na lista de vazios")
    for pref in LUGARES:
        campos = dict(carga["colunas"][pref])
        identidade = campos.pop(pacotes_mod.IDENTIDADE_DO_LUGAR, None)
        if identidade is not None:
            esperado = (f"P{pref[1:]} {pacotes_mod.PONTO_DO_ROTULO} "
                        f"{pacotes_mod.SEM_NINGUEM_AQUI}")
            assert identidade == esperado, (
                f"{pagina}/{pref}: a identidade do lugar vazio diz "
                f"{identidade!r} e devia dizer {esperado!r}")
        declarado = dict(bruto.get(pacotes_mod.LUGAR_VAZIO) or {})
        for campo, valor in declarado.items():
            assert campos.pop(campo, None) == valor, (
                f"{pagina}/{pref}: o `{campo}` do lugar vazio não é o que a aba "
                "declarou em `LUGAR_VAZIO`")
        valores = set(campos.values())
        assert valores == {pacotes_mod.TRAVESSAO}, (
            f"{pagina}/{pref}: sobrou valor que não é travessão: {valores}")
    assert carga["colunas"]["p1"], (
        f"{pagina}: o lugar P1 ficou sem campo nenhum — é o estado de ANTES "
        "desta cura, em que o desenho continuava na tela")


def test_o_molde_nao_pousa_em_lugar_nenhum_da_pagina(pacotes_mod):
    """`LUGAR_SEM_DONO` não pode ser um `data-controle` de nenhuma página."""
    from hefesto_dualsense4unix.interface import onde

    for caminho in onde.paginas(publicado=True):
        doc = caminho.read_text(encoding="utf-8")
        alvo = f'data-controle="{pacotes_mod.LUGAR_SEM_DONO}"'
        assert alvo not in doc, f"{caminho.name} tem {alvo} — o molde pousaria nele"


def test_a_coluna_reservada_entra_na_uniao_das_chaves(pacotes_mod):
    """A LINHA QUE NENHUM LITERAL ALCANÇAVA, e é a que sustenta a cura inteira."""
    molde = {"bateria": pacotes_mod.TRAVESSAO, "via": pacotes_mod.TRAVESSAO}
    carga = {"colunas": {pacotes_mod.LUGAR_SEM_DONO: dict(molde)}, "mesa": {}}
    pacotes_mod.apagar_os_lugares_sem_dono(carga)
    for pref in LUGARES:
        assert carga["colunas"][pref] == molde, (
            f"{pref} não recebeu as chaves do molde — a coluna reservada ficou "
            "de fora da união e a cura morreu inteira")
    assert sorted(carga["vazios"]) == sorted(LUGARES)


def test_a_coluna_viva_manda_e_o_lugar_dela_nao_e_apagado(pacotes_mod):
    """Quem tem dono não recebe travessão — e a união vem das colunas VIVAS."""
    carga = {"colunas": {"p1": {"bateria": "95%", "via": "USB"}}, "mesa": {}}
    pacotes_mod.apagar_os_lugares_sem_dono(carga)
    assert carga["colunas"]["p1"] == {"bateria": "95%", "via": "USB"}
    assert carga["vazios"] == ["p2", "p3", "p4"]
    assert set(carga["colunas"]["p2"].values()) == {pacotes_mod.TRAVESSAO}
    assert set(carga["colunas"]["p2"]) == {"bateria", "via"}


def test_o_piloto_ainda_chama_a_conta_do_despachante():
    """As duas pontas continuam ligadas — e agora o elo é uma CHAMADA."""
    import ast

    piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
              ).read_text(encoding="utf-8")
    chamadas = [
        n for n in ast.walk(ast.parse(piloto))
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "apagar_os_lugares_sem_dono"
    ]
    assert chamadas, (
        "o piloto deixou de CHAMAR `apagar_os_lugares_sem_dono` — o molde do "
        "despachante ficou sem quem o aplique, e as colunas sem dono voltam a "
        "mostrar o desenho")
    assert any(c.args and isinstance(c.args[0], ast.Name) and c.args[0].id == "carga"
               for c in chamadas), (
        "a chamada existe mas não recebe a `carga` do tique como primeiro "
        "argumento — o molde aplicado seria outro")
