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
   Proton 10 da máquina do usuário (molde `0x%04X/0x%04X` + `wcscasestr`, isto é,
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

_IGNORE_DE_HOJE = "0x054c/0x0ce6"
_DISABLE_DE_HOJE = "0x054C/0x0CE6"

_TRES = [(0x054C, 0x0CE6), (0x057E, 0x2009), (0x054C, 0x05C4)]

_TOKEN_MINUSCULO = re.compile(r"^0x[0-9a-f]{4}/0x[0-9a-f]{4}$")


def test_um_par_devolve_exatamente_o_valor_cravado_ate_ontem():
    """A composição com UM par tem de ser indistinguível do literal antigo."""
    assert valor_ignore_devices([PAR_DUALSENSE_FISICO]) == _IGNORE_DE_HOJE
    assert valor_disable_hidraw([PAR_DUALSENSE_FISICO]) == _DISABLE_DE_HOJE


def test_a_caixa_do_ignore_e_contrato_com_a_assinatura_do_veneno():
    """Minúscula no IGNORE não é gosto: é o token que o strip procura."""
    from hefesto_dualsense4unix.integrations.steam_launch_options import (
        IGNORE_SIGNATURE,
    )

    composta = f"{_IGNORE}={valor_ignore_devices([PAR_DUALSENSE_FISICO])}"
    assert composta == IGNORE_SIGNATURE


def test_o_par_do_dualsense_e_o_mesmo_que_o_vpad_conhece():
    """Fonte única sem import de topo: as duas cópias não podem divergir."""
    from hefesto_dualsense4unix.integrations.uhid_gamepad import (
        DUALSENSE_PRODUCT,
        DUALSENSE_VENDOR,
    )

    assert PAR_DUALSENSE_FISICO == (DUALSENSE_VENDOR, DUALSENSE_PRODUCT)


def test_tres_pares_saem_separados_por_virgula_e_por_mais_nada():
    """Vírgula, sem espaço, na ordem em que chegaram."""
    assert valor_ignore_devices(_TRES) == "0x054c/0x0ce6,0x057e/0x2009,0x054c/0x05c4"
    assert valor_disable_hidraw(_TRES) == "0x054C/0x0CE6,0x057E/0x2009,0x054C/0x05C4"


def test_zero_pares_devolve_string_vazia_para_o_chamador_omitir_a_variavel():
    """Lista vazia não vira `VAR=`: vira nada, e quem chama omite a linha."""
    assert valor_ignore_devices([]) == ""
    assert valor_disable_hidraw(()) == ""
    assert compor_lista_vidpid(iter([]), maiusculas=True) == ""


def test_nenhum_espaco_e_nenhuma_quebra_de_linha_no_valor():
    """O wrapper passa a LINHA inteira como um argumento do `env(1)`."""
    for valor in (valor_ignore_devices(_TRES), valor_disable_hidraw(_TRES)):
        assert not any(c.isspace() for c in valor), repr(valor)


def test_cada_token_tem_prefixo_0x_e_quatro_digitos_com_zero_a_esquerda():
    """O `0x` e os quatro dígitos fazem parte da AGULHA do winebus."""
    valor = valor_ignore_devices([(0x1, 0x2), *_TRES])
    tokens = valor.split(",")
    assert tokens[0] == "0x0001/0x0002"
    for token in tokens:
        assert _TOKEN_MINUSCULO.match(token), token


def test_a_agulha_do_winebus_casa_em_todos_os_pares_da_lista():
    """Reproduz o `is_hidraw_enabled` do Proton 10 (MEDIDO em 07/08/2026)."""
    for valor in (valor_ignore_devices(_TRES), valor_disable_hidraw(_TRES)):
        for vid, pid in _TRES:
            agulha = f"0x{vid:04X}/0x{pid:04X}"
            assert agulha.lower() in valor.lower(), (agulha, valor)


def test_a_agulha_de_quem_nao_esta_na_lista_nao_casa():
    """O par que ninguém pediu continua fora — inclusive o vpad Edge 0x0DF2."""
    valor = valor_disable_hidraw([PAR_DUALSENSE_FISICO])
    assert "0x054c/0x0df2" not in valor.lower()
    assert "0x057e/0x2009" not in valor.lower()


def test_par_fora_da_faixa_de_16_bits_e_descartado_e_os_bons_sobrevivem():
    """`0x1054C` formatado por `%04x` sai com cinco dígitos e gruda no vizinho."""
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


def test_compose_env_nao_esconde_controle_fisico_sem_cobertura_por_par():
    """A trava original desta bateria, com o alvo dito por extenso."""
    env = compose_env(
        native_mode=False,
        emulation_enabled=True,
        flavor="dualsense",
        backends=["uhid"],
    )
    pares = env[_IGNORE].split(",")
    assert _IGNORE_DE_HOJE in pares
    assert set(pares) == {_IGNORE_DE_HOJE, "0x28de/0x11ff"}, (
        "entrou um par novo no IGNORE. Se for de um controle FÍSICO, ele "
        "precisa da cobertura POR PAR da E4 antes — senão some do jogo dela."
    )
    assert env[_DISABLE] == _DISABLE_DE_HOJE
    assert "," not in env[_DISABLE]
