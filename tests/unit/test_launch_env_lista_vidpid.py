"""MÁSCARA-01, entrega 3 (metade segura): o VALOR das envs vira uma LISTA.

O `SDL_GAMECONTROLLER_IGNORE_DEVICES` e o `PROTON_DISABLE_HIDRAW` carregavam
**um par VID/PID cravado** dentro de uma string (`daemon/launch_env.py:83` e
`:91`). Agora eles são COMPOSTOS a partir de uma lista, e a lista de hoje tem
um item só: o DualSense físico. A função nasce testada e **não ligada** — quem
a alimentaria com mais pares é a `E4` da LUGAR-À-MESA-01 (cobertura POR PAR),
que vem depois da adoção dos externos, que ela adiou.

Esta bateria vigia o que quebraria em silêncio:

1. **o valor de hoje continua byte a byte o mesmo** — inclusive a CAIXA, que é
   contrato com o `IGNORE_SIGNATURE` do `steam_launch_options`;
2. **o formato do separador** — vírgula e nada mais. Um separador errado faz o
   consumidor ignorar a variável inteira, e ninguém percebe;
3. **a agulha do winebus casa** — reproduzimos aqui o algoritmo MEDIDO no
   Proton 10 da máquina dela (molde `0x%04X/0x%04X` + `wcscasestr`, isto é,
   substring sem caixa);
4. **par inválido é descartado, nunca corrigido** — a assimetria da casa manda
   errar para o lado do controle DUPLICADO, jamais para o do controle sumido;
5. **nenhum par de controle FÍSICO entra sem cobertura** — era "a lista não
   cresceu"; virou isto em 10/08/2026, quando o espelho VIRTUAL do Steam Input
   (`28de:11ff`) entrou. Ver a nota datada no teste 5.

Nenhum aparelho, nenhum GTK, nenhum Xvfb: tudo é função pura sobre inteiros.
"""
from __future__ import annotations

import re

from hefesto_dualsense4unix.daemon.launch_env import (
    PAR_DUALSENSE_FISICO,
    compor_lista_vidpid,
    compose_env,
    valor_disable_hidraw,
    valor_ignore_devices,
)

_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"
_DISABLE = "PROTON_DISABLE_HIDRAW"

#: O que estava cravado no código até 07/08/2026 — o alvo de regressão.
_IGNORE_DE_HOJE = "0x054c/0x0ce6"
_DISABLE_DE_HOJE = "0x054C/0x0CE6"

#: Três pares de bancada. `054c:05c4` é real e serve de lembrete: é o par do
#: 8BitDo em modo PS4 **e** o de um DualShock 4 Sony genuíno — o par que a
#: cobertura POR PAR da `E4` existe para não emitir por engano.
_TRES = [(0x054C, 0x0CE6), (0x057E, 0x2009), (0x054C, 0x05C4)]

#: Um token `0xVVVV/0xPPPP` em minúsculas, sem nada em volta.
_TOKEN_MINUSCULO = re.compile(r"^0x[0-9a-f]{4}/0x[0-9a-f]{4}$")


# --- 1. o valor de hoje, byte a byte ----------------------------------------


def test_um_par_devolve_exatamente_o_valor_cravado_ate_ontem():
    """A composição com UM par tem de ser indistinguível do literal antigo.

    É o que garante que esta entrega não muda uma vírgula do que a máquina
    dela já roda: o daemon compõe, mas compõe o mesmo.
    """
    assert valor_ignore_devices([PAR_DUALSENSE_FISICO]) == _IGNORE_DE_HOJE
    assert valor_disable_hidraw([PAR_DUALSENSE_FISICO]) == _DISABLE_DE_HOJE


def test_a_caixa_do_ignore_e_contrato_com_a_assinatura_do_veneno():
    """Minúscula no IGNORE não é gosto: é o token que o strip procura.

    `steam_launch_options.IGNORE_SIGNATURE` compara a LaunchOptions
    envenenada byte a byte. Se a caixa mudar aqui, o `has_poison` deixa de
    reconhecer o veneno que as versões antigas persistiram — e veneno com o
    vpad fora de cena é ZERO controles.
    """
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        IGNORE_SIGNATURE,
    )

    composta = f"{_IGNORE}={valor_ignore_devices([PAR_DUALSENSE_FISICO])}"
    assert composta == IGNORE_SIGNATURE


def test_o_par_do_dualsense_e_o_mesmo_que_o_vpad_conhece():
    """Fonte única sem import de topo: as duas cópias não podem divergir.

    `launch_env` repete o par de propósito (importar `uhid_gamepad` no topo
    criaria a aresta `daemon -> integrations -> core` só para ler dois
    inteiros). Quem impede a divergência é este teste.
    """
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        DUALSENSE_PRODUCT,
        DUALSENSE_VENDOR,
    )

    assert PAR_DUALSENSE_FISICO == (DUALSENSE_VENDOR, DUALSENSE_PRODUCT)


# --- 2. o formato: um par, três pares, nenhum -------------------------------


def test_tres_pares_saem_separados_por_virgula_e_por_mais_nada():
    """Vírgula, sem espaço, na ordem em que chegaram."""
    assert valor_ignore_devices(_TRES) == "0x054c/0x0ce6,0x057e/0x2009,0x054c/0x05c4"
    assert valor_disable_hidraw(_TRES) == "0x054C/0x0CE6,0x057E/0x2009,0x054C/0x05C4"


def test_zero_pares_devolve_string_vazia_para_o_chamador_omitir_a_variavel():
    """Lista vazia não vira `VAR=`: vira nada, e quem chama omite a linha.

    `VAR=` no arquivo tem a mesma cara de quem escondeu alguém, e o `.env` é a
    primeira coisa que se lê ao diagnosticar controle demais no jogo.
    """
    assert valor_ignore_devices([]) == ""
    assert valor_disable_hidraw(()) == ""
    assert compor_lista_vidpid(iter([]), maiusculas=True) == ""


def test_nenhum_espaco_e_nenhuma_quebra_de_linha_no_valor():
    """O wrapper passa a LINHA inteira como um argumento do `env(1)`.

    Espaço não quebra esse caminho (não há word-split), mas quebra de linha
    partiria o arquivo `VAR=VAL` em duas linhas e a segunda viraria lixo. O
    valor composto não pode ter nem um nem outro.
    """
    for valor in (valor_ignore_devices(_TRES), valor_disable_hidraw(_TRES)):
        assert not any(c.isspace() for c in valor), repr(valor)


def test_cada_token_tem_prefixo_0x_e_quatro_digitos_com_zero_a_esquerda():
    """O `0x` e os quatro dígitos fazem parte da AGULHA do winebus.

    E o zero à esquerda é o que impede `0x1/0x2` de existir: o consumidor
    procura `0x0001/0x0002`, e um token curto simplesmente nunca casa.
    """
    valor = valor_ignore_devices([(0x1, 0x2), *_TRES])
    tokens = valor.split(",")
    assert tokens[0] == "0x0001/0x0002"
    for token in tokens:
        assert _TOKEN_MINUSCULO.match(token), token


# --- 3. o consumidor MEDIDO: a agulha do winebus ----------------------------


def test_a_agulha_do_winebus_casa_em_todos_os_pares_da_lista():
    """Reproduz o `is_hidraw_enabled` do Proton 10 (MEDIDO em 07/08/2026).

    O `winebus.sys` monta a agulha com o molde WIDE `0x%04X/0x%04X` e procura
    com `wcscasestr` — substring, sem caixa. Aqui a busca é feita nos DOIS
    valores compostos (o de caixa alta e o de caixa baixa): se algum dia o
    separador, o prefixo ou o preenchimento mudarem, a agulha para de casar e
    este teste cai antes de o jogo dela ficar com o físico exposto.
    """
    for valor in (valor_ignore_devices(_TRES), valor_disable_hidraw(_TRES)):
        for vid, pid in _TRES:
            agulha = f"0x{vid:04X}/0x{pid:04X}"
            assert agulha.lower() in valor.lower(), (agulha, valor)


def test_a_agulha_de_quem_nao_esta_na_lista_nao_casa():
    """O par que ninguém pediu continua fora — inclusive o vpad Edge 0x0DF2.

    É o contraponto do teste acima: casar sempre seria tão inútil quanto não
    casar nunca.
    """
    valor = valor_disable_hidraw([PAR_DUALSENSE_FISICO])
    assert "0x054c/0x0df2" not in valor.lower()
    assert "0x057e/0x2009" not in valor.lower()


# --- 4. par inválido é descartado, nunca corrigido --------------------------


def test_par_fora_da_faixa_de_16_bits_e_descartado_e_os_bons_sobrevivem():
    """`0x1054C` formatado por `%04x` sai com cinco dígitos e gruda no vizinho.

    Descartar é o lado seguro: um par a menos é o controle DUPLICADO (pior
    caso aceito por escrito); um par errado a mais some com o controle de
    alguém.
    """
    valor = valor_ignore_devices(
        [(0x1054C, 0x0CE6), PAR_DUALSENSE_FISICO, (0x054C, -1)]
    )
    assert valor == _IGNORE_DE_HOJE


def test_lixo_no_lugar_de_par_nao_levanta_e_nao_entra():
    """Nenhuma dessas formas pode virar token — e nenhuma pode explodir."""
    valor = valor_ignore_devices(
        [
            None,  # type: ignore[list-item]
            "0x054c/0x0ce6",  # type: ignore[list-item]
            (0x054C,),  # type: ignore[list-item]
            (0x054C, 0x0CE6, 0x0DF2),  # type: ignore[list-item]
            ("054c", "0ce6"),  # type: ignore[list-item]
            (True, False),  # type: ignore[list-item]
            PAR_DUALSENSE_FISICO,
        ]
    )
    assert valor == _IGNORE_DE_HOJE


def test_par_repetido_entra_uma_vez_so_e_a_ordem_de_chegada_sobrevive():
    """Repetir não muda o que o consumidor faz, mas mente na leitura humana."""
    valor = valor_ignore_devices(
        [(0x057E, 0x2009), PAR_DUALSENSE_FISICO, (0x057E, 0x2009)]
    )
    assert valor == "0x057e/0x2009,0x054c/0x0ce6"


# --- 5. a função NÃO está ligada --------------------------------------------


def test_compose_env_nao_esconde_controle_fisico_sem_cobertura_por_par():
    """A trava original desta bateria, com o alvo dito por extenso.

    NOTA DATADA — 10/08/2026 (TRES-CONTROLES-01)
    ============================================
    Este teste se chamava `test_compose_env_continua_emitindo_um_par_so` e
    afirmava, literalmente, que a lista tinha um item e que não podia haver
    vírgula. **A razão continua inteira e não foi revogada**: somar o par de um
    controle FÍSICO ao IGNORE sem a cobertura POR PAR da `E4` esconde aquele
    aparelho do jogo sem haver vpad que o devolva — e a assimetria desta casa
    manda errar para o lado do DUPLICADO, nunca para o do controle sumido.

    O que mudou é que um segundo par entrou, e ele **não é um controle da
    mesa**: `28de:11ff` é o espelho VIRTUAL que o Steam Input cria a partir dos
    controles que ele enxerga. Escondê-lo não subtrai aparelho nenhum — subtrai
    uma CÓPIA de um aparelho que continua chegando ao jogo pelo nosso vpad. O
    perigo que a trava vigiava não existe nesse par, e por isso ela deixou de
    ser "um par só" e passou a ser o que sempre quis dizer: **nenhum par de
    controle físico sem cobertura**.

    O `PROTON_DISABLE_HIDRAW` continua com um par só, e esse "um" é literal: ele
    nega hidraw, e negar hidraw ao vpad Edge `0df2` cortaria rumble, gatilhos e
    lightbar do jogo (ver a constante em `launch_env.py`).
    """
    env = compose_env(
        native_mode=False,
        emulation_enabled=True,
        flavor="dualsense",
        backends=["uhid"],
    )
    pares = env[_IGNORE].split(",")
    # O físico continua lá, byte a byte, na caixa que é contrato.
    assert _IGNORE_DE_HOJE in pares
    # E nenhum par de controle FÍSICO além dele — que é o que a trava protege.
    assert set(pares) == {_IGNORE_DE_HOJE, "0x28de/0x11ff"}, (
        "entrou um par novo no IGNORE. Se for de um controle FÍSICO, ele "
        "precisa da cobertura POR PAR da E4 antes — senão some do jogo dela."
    )
    assert env[_DISABLE] == _DISABLE_DE_HOJE
    assert "," not in env[_DISABLE]
