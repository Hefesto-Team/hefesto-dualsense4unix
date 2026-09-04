#!/usr/bin/env python3
"""A RÉGUA DA CURA DE 01/09/2026: o que está no perfil chega à tela.

POR QUE ELA EXISTE, e a pergunta dela é o enunciado: *"vc tá corrigindo na
origem esses problemas que tá relatando né?"*

Não estava. Dezessete valores desta interface mostravam travessão com uma frase
dizendo que o produto não sabia aquilo. **Doze tinham dono** — o perfil no disco
dela — e o erro tinha uma forma só: *eu perguntei ao `state_full` do daemon, ele
não publica gatilho nem brilho, e li a ausência como inexistência.*

O QUE ESTA RÉGUA MEDE, e é a parte que a cura pode perder de novo: que os
valores do perfil ATRAVESSEM até o pacote. Ela não olha texto de tela nem
docstring — monta um perfil com gatilho e brilho, chama as funções de pacote, e
cobra os valores de volta.

A MORDIDA (arranque a cura e veja reprovar): apague o `_do_lado` do
`a03_gatilhos.py`, ou faça `perfil.ativo()` devolver `{}` sempre. Os dois casos
reprovam aqui — o primeiro com `Desligado` no lugar de `Rígido`, o segundo com
`brilho: None` no lugar de `0.7`.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: O perfil de mentira, com a forma EXATA do disco dela — medida em 01/09/2026
#: no perfil "Ação". Os dois lados de propósito diferentes: um escalar
#: (`Rigid`) e um que a tela mostra com três ajustes (`Vibration`).
PERFIL = {
    "name": "Régua", "version": 1, "priority": 50,
    "match": {"type": "manual"},
    "triggers": {
        "left": {"mode": "Rigid", "params": [0, 180]},
        "right": {"mode": "Vibration", "params": [3, 8, 20]},
    },
    "leds": {"lightbar": [255, 80, 0], "player_leds": [True] * 5,
             "lightbar_brightness": 0.7},
    "rumble": {"passthrough": True},
}

#: A CURVA é a segunda forma que o disco guarda, e ela quebrou o pacote na
#: primeira execução: `MultiPositionFeedback` grava `[[1], [2], ...]`, dez
#: posições em listas de um. `[1] - 0` não é uma subtração que exista.
PERFIL_CURVA = {
    **PERFIL, "name": "Curva",
    "triggers": {
        "left": {"mode": "MultiPositionFeedback",
                 "params": [[i] for i in (1, 2, 3, 4, 5, 6, 7, 8, 8, 8)]},
        "right": {"mode": "Off", "params": []},
    },
}

#: A mesa, na língua do DESENHO — `pref`, `jogador`, `nome`, `via`.
MESA = [{"pref": "p1", "jogador": 1, "uniq": "aa:bb:cc:00:00:01", "nome": "Régua",
         "via": "USB", "cor": "starlight-blue", "mascara": "DualSense", "alvo": True}]

#: Um controle com a forma do que o daemon devolve. MAC da faixa sintética da
#: casa — há dois portões de anonimato nesta árvore e eles não perdoam.
FALSO = {
    "uniq": "aa:bb:cc:00:00:01", "player": 1, "connected": True, "is_primary": True,
    "battery_pct": 95, "transport": "usb", "vpad_backend": "uhid",
    "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
    "inputs": {"lx": 127, "ly": 128, "rx": 127, "ry": 128,
               "l2_raw": 0, "r2_raw": 0, "buttons": []},
    "audio": {"mic_mudo": False}, "speaker": {"volume": 102, "muted": False},
}


@pytest.fixture
def com_perfis(tmp_path, monkeypatch):
    """Grava os perfis num lar de mentira e aponta o leitor para lá.

    O `conftest.py` desta casa já desvia `HOME` e os quatro `XDG_*`; o que falta
    é a pasta existir com os arquivos dentro, e é o que esta fixture faz. Nada
    aqui toca o disco dela.
    """
    from pacotes import perfil

    pasta = tmp_path / "profiles"
    pasta.mkdir(parents=True)
    for p in (PERFIL, PERFIL_CURVA):
        nome = p["name"].lower()
        (pasta / f"{nome}.json").write_text(json.dumps(p), encoding="utf-8")
    monkeypatch.setattr(perfil, "pasta", lambda: pasta)
    return pasta


@pytest.fixture
def ctx_com(com_perfis):
    """Um `Contexto` com um controle na mesa e o perfil que se pedir."""
    from pacotes import Contexto

    def montar(nome: str) -> Contexto:
        # A MESA TEM OUTRA FORMA QUE O CONTROLE: `pref`/`jogador`/`nome`/`via`
        # (a língua do desenho) contra `player`/`transport` (a do daemon).
        # Passar o controle como mesa dá `KeyError: 'jogador'` dentro da camada
        # do produto, e só na suíte completa.
        return Contexto(state={"active_profile": nome, "rumble_policy": "balanceado"},
                        mesa=MESA, conectados=[FALSO], estados={})
    return montar


def test_o_leitor_acha_os_perfis(com_perfis):
    """Zero perfis com dois no disco é ERRO, não silêncio.

    Esta régua nasceu de um zero exatamente assim: a primeira versão do
    `perfil.py` cacheava a pasta com `@lru_cache`, o primeiro chamador não tinha
    `HEFESTO_VARIANTE` posta, e `lista()` devolveu **0 com 33 perfis no disco**.
    """
    from pacotes import perfil

    achados = perfil.lista()
    assert len(achados) == 2, (
        f"o leitor achou {len(achados)} perfis em {com_perfis}, que tem "
        f"{len(list(com_perfis.glob('*.json')))} arquivos. Zero aqui é a cura "
        f"arrancada, não uma pasta vazia.")


def test_o_gatilho_do_perfil_chega_traduzido(ctx_com):
    """`Rigid` no disco vira `Rígido` na tela — e os ajustes vêm junto."""
    from pacotes import pacote_da_pagina

    r = pacote_da_pagina("03-gatilhos.html", ctx_com("régua"))
    col = next(iter(r["colunas"].values()))

    assert col["modo-e"] == "Rígido", (
        f"o L2 saiu {col['modo-e']!r}. O disco diz `Rigid` e a tela fala "
        f"português — a tradução é `app/actions/trigger_specs.PRESETS`. "
        f"`Desligado` aqui é o pacote ignorando o perfil, que é o defeito "
        f"que esta régua existe para pegar.")
    assert col["modo-e-chave" if "modo-e-chave" in col else "modo-chave-e"] == "Rigid"
    assert col["modo-d"] == "Vibração"

    # OS AJUSTES, com os valores DELA — não os padrões do preset.
    #
    # ELES CHEGAM DENTRO DE UM BLOCO desde 02/09/2026, e a mudança é a decisão
    # 2 dela: *"os ajustes viram lista e a caixa acompanha o modo"*. O número de
    # barras é o do MODO — de zero (`Off`) a onze (`MultiPositionVibration`) — e
    # não há endereço de pintura para um filho que ainda não existe, então a
    # caixa é trocada inteira. Cobrar `col["aj-val-e-1"]` aqui reprovaria a cura.
    caixa_e = r["blocos"]['[data-controle="p1"] .ajustes.e']
    assert '<span class="num" data-campo="aj-val-e-1">180</span>' in caixa_e, (
        f"a Força do L2 não chegou com o 180 que o perfil guarda. Um padrão do "
        f"preset aqui é o pacote lendo a tabela e não o disco:\n{caixa_e}")
    assert '"aj-nome-e-1">Força<' in caixa_e
    caixa_d = r["blocos"]['[data-controle="p1"] .ajustes.d']
    valores_d = re.findall(r'data-campo="aj-val-d-\d+">(\d+)<', caixa_d)
    assert valores_d == ["3", "8", "20"], (
        f"o R2 do perfil guarda [3, 8, 20] e a caixa trouxe {valores_d}")

    #: A PORCENTAGEM É DA FAIXA DAQUELE AJUSTE. `force` vai a 255 e `position`
    #: a 9; dividir os dois por 255 pintaria a barra da posição sempre no chão.
    #: Ela viaja no `style` do próprio bloco: a caixa é trocada inteira, então a
    #: largura chega com ela em vez de esperar uma segunda pintura.
    assert f'style="width:{round(180 / 255 * 100)}%"' in caixa_e, (
        f"a barra da Força não veio na porcentagem da FAIXA dela:\n{caixa_e}")


def test_a_curva_de_dez_posicoes_nao_derruba_a_aba(ctx_com):
    """A segunda forma do disco — e ela quebrou o pacote de verdade."""
    from pacotes import pacote_da_pagina

    r = pacote_da_pagina("03-gatilhos.html", ctx_com("curva"))
    col = next(iter(r["colunas"].values()))
    assert col["modo-e"] == "Curva de força"
    assert col["curva-e"] == [1, 2, 3, 4, 5, 6, 7, 8, 8, 8], (
        "a curva não chegou achatada. `[[1], [2], ...]` é o que o disco guarda "
        "e `[1, 2, ...]` é o que a tela desenha.")
    assert col["curva-pct-e"][0] == round(1 / 8 * 100)


def test_o_brilho_do_perfil_chega_em_porcentagem(ctx_com):
    """`0.7` no disco vira `70%` na tela — o valor que eu jurei não existir."""
    from pacotes import pacote_da_pagina

    r = pacote_da_pagina("04-iluminacao.html", ctx_com("régua"))
    col = next(iter(r["colunas"].values()))
    #: A RÉGUA COBRAVA O CONTRÁRIO DO QUE O NOME DELA PROMETE, e foi assim até
    #: 02/09/2026: o título diz *"vira 70% na tela"* e a linha exigia `0.7`. A
    #: tela obedeceu à linha e não ao título — a foto de 02/09 mostra `1` ao
    #: lado da barra de brilho, nas duas colunas, que é o `1.0` do disco escrito
    #: cru. O `%` é da TELA (o desenho escreve `82%` nesta caixa) e a conversão
    #: mora no pacote, porque o JS não sabe se um número é porcentagem.
    assert col["brilho"] == "70%", (
        f"o brilho saiu {col.get('brilho')!r}. `leds.lightbar_brightness` está "
        f"no schema com faixa declarada e preenchido nos 33 perfis dela; "
        f"`—` aqui é o travessão de volta, e `0.7` é o disco cru na tela.")
    assert col["brilho-pct"] == 70, "o disco guarda 0..1 e a barra pede 0..100"

    #: A COR CONTINUA VINDO DO DAEMON, não do perfil: o brilho é o que está
    #: SALVO, a cor é o que está ACESO, e quando discordam manda o vivo.
    assert col["hex"] == "#0000FF", (
        "o hex veio do perfil (255,80,0) em vez do daemon (0,0,255). O vivo "
        "vence o salvo para a cor — é o contrário do brilho, de propósito.")


def test_nenhuma_aba_declara_orfao_que_tem_dono(ctx_com):
    """O saldo da cura, e ele é a régua contra a recaída.

    Era 17 órfãos; em 01/09 ficou UM — `plugins`, que não é erro de ninguém: a
    `gui/aba_sistema.py:95` já tinha medido que o IPC `plugin.list` existe e que
    **só a CLI o chama**. Um número maior que este é alguém tendo voltado a
    escrever travessão em cima de dado que existe.

    ATUALIZADA EM 02/09/2026, na integração da leva das treze frentes, e os
    SETE novos foram conferidos um a um contra a exigência desta régua — *prove
    que perguntou ao perfil, ao IPC e à `gui/aba_*.py` antes*. Nenhum é
    travessão sobre dado que existe; **cada um é um caminho que o produto não
    tem**, e a razão de cada um está escrita no `SEM_DONO` do próprio pacote:

    **DE SETE PARA CINCO — 03/09/2026, e a régua ENVELHECEU: os três que
    saíram saíram porque foram CURADOS.** Ela tinha a lista de 02/09 congelada e
    reprovava a melhora em vez do defeito. Cada saída foi conferida no pacote
    que a declarava:

      * `degrau-aceso` e `mult-teto` — o motivo escrito aqui (*"o pintor não
        alcança classe"*) caducou: o alvo `classe` existe no pintor desde
        02/09, e o que faltava eram o ENDEREÇO no desenho e a EMISSÃO no
        pacote. As duas metades entraram juntas (`aba05._coluna` e
        `aba05._teto_do_multiplicador`), e `a05_vibracao.SEM_DONO` registra:
        *"Mantê-los depois de pintados seria dívida fantasma — a próxima pessoa
        esperaria por uma cura que já chegou."*
      * `abrir-lancador` — o motivo era a PERGUNTA ERRADA. *"O daemon não tem
        método para isso"* é verdade pelo IPC, e irrelevante: o produto sabe
        abrir a Steam desde 23/08 por outro caminho
        (`steam_launch_options.reopen_steam`, que tinha zero chamadores vindos
        de `interface/`). Decisão 17 dela, 03/09: o botão liga, e o gesto entra
        em `hefesto_vivo.PERIGOSOS` para a `--prova-gesto` não abrir a Steam na
        tela dela.

    OS CINCO QUE FICAM, com a razão no `SEM_DONO` do próprio pacote:
      * `barra:motor` — o dono do gesto ESTÁ escrito
        (`app/telas/vibracao.DONOS_DOS_GESTOS`); o que falta é o NÚMERO: a
        linha é um `<div>`, e um `<div>` não tem `value`. Trocar a barra por um
        controle arrastável é decisão DELA;
      * `lado:ligado` — os oito interruptores de punho são desenho, e o produto
        concorda por escrito em `app/telas/vibracao.SEM_FONTE`: não há campo no
        esquema, nem método de IPC, nem chave no `state_full`;
      * `criar-perfil` — é da aba Perfis, e dois caminhos para o mesmo disco é
        como duas telas passam a discordar;
      * `heroic` — **medido**: o produto PROCURA os seis lançadores
        (`_onde_estao_os_lancadores`) mas não LÊ a biblioteca de nenhum deles;
      * `plugins` — o IPC `plugin.list` existe e **só a CLI o chama**.

    O `sem_dono` é o oposto de esconder: é a tela dizendo *"isto eu não sei"*
    em vez de mostrar o desenho como se fosse dado.

    **A RÉGUA MORDE NOS DOIS SENTIDOS, e é por isso que a igualdade é exata:**
    um órfão a MAIS é alguém voltando a escrever travessão sobre dado que
    existe; um a MENOS sem esta lista mudar junto é uma cura que ninguém
    registrou — e a dívida fantasma faz a próxima pessoa esperar por algo que
    já chegou.
    """
    from pacotes import PACOTES, pacote_da_pagina

    ctx = ctx_com("régua")
    orfaos = {}
    for pagina in PACOTES:
        r = pacote_da_pagina(pagina, ctx)
        n = r["cobertura"]["sem_dono"]
        if n:
            orfaos[pagina] = sorted(r.get("sem_dono") or {})
    assert orfaos == {
        # OS DOIS `forca:*` ENTRARAM À TARDE DE 03/09/2026, e nasceram de uma
        # decisão dela — *"construir por controle"*. Nenhum é travessão sobre
        # dado que existe; os dois foram perguntados ao esquema, ao IPC e ao
        # produto antes de entrarem, e o que sobra em cada um é UMA FRASE DELA:
        #
        #   `forca:auto-da-mesa`    pôr a MESA em `Auto` perdeu o botão nesta
        #                           aba, porque `ControllerRumbleOverride`
        #                           RECUSA `auto` por unidade (ele escala pela
        #                           bateria do controle PRIMÁRIO) e
        #                           `draft_config.with_controller_rumble`
        #                           traduz o clique em "limpa o override e
        #                           devolve a peça ao global". Um caminho novo
        #                           para o degrau da mesa é desenho dela.
        #
        # E `barra:forca` SAIU no mesmo dia, curada: a barra "Personalizado"
        # virou `<input type=range>` e grava (`a05_vibracao.intensidade`).
        #
        # `forca:global-em-auto` SAIU EM 04/09/2026, curado. Ele dizia *"a
        # escolha dela fica gravada e não chega ao motor; o que falta é a tela
        # AVISAR"* — e a tela avisa em dois tempos: no clique
        # (`a05_vibracao._aplicar_a_forca`, frase no cartão daquele controle) e
        # no TEMPO (`a05_vibracao._ressalva_da_mesa`, linha no `#vib-estado`
        # enquanto a mesa estiver em `Auto` com alguma peça a perder). A prova
        # está em `test_a05_a_vibracao_aplica_e_fala.py`.
        "05-vibracao.html": ["barra:motor", "forca:auto-da-mesa",
                             "lado:ligado"],
        "07-lancadores.html": ["criar-perfil", "heroic"],
        "09-sistema.html": ["plugins"],
    }, (
        f"os órfãos mudaram: {orfaos}. Cada um aqui é um valor que a tela mostra "
        f"como travessão — e a lição de 01/09 é que doze deles tinham dono e "
        f"ninguém tinha ido olhar. Se acrescentou um, prove que perguntou ao "
        f"perfil, ao IPC e à `gui/aba_*.py` antes. Se TIROU um, a cura tem de "
        f"estar escrita no `SEM_DONO` do pacote — senão a dívida vira fantasma.")
