"""A máscara Nintendo Pro existe e ATRAVESSA a casa inteira (07/09/2026).

Ordem dela: *"tem que mandar um agente construir só o do pro controller da
Nintendo"*. A máscara é de EMULAÇÃO — o Hefesto faz o DualSense dela se
apresentar ao jogo como um Pro; não é suporte a aparelho Nintendo físico.

O QUE ESTE PORTÃO EXISTE PARA IMPEDIR, e é o defeito que a sprint nomeou:
*um sabor que só existe no catálogo é um chip que continua cinza*. Um sabor
novo tem SEIS pernas fora do `FLAVORS`, e cada uma delas já foi, em algum
momento desta casa, uma lista digitada que divergiu do catálogo em silêncio.
Cada teste abaixo arranca uma perna.

A MORDIDA, conferida uma a uma em 07/09/2026 (apagar a linha citada reprova o
teste que a acompanha):

  * tirar `"nintendo"` do `FLAVORS`               -> reprova `test_o_catalogo_*`
  * `_MASCARAS_SO_EVDEV = frozenset({"xbox"})`    -> reprova `test_o_launch_env_*`
  * `MascaraDeGamepad = Literal["dualsense","xbox"]` -> reprova `test_o_esquema_*`
  * tirar o `if valor == "nintendo"`              -> reprova `test_o_normalizador_*`
  * `BOTOES_POR_FLAVOR` sem a entrada             -> reprova `test_cada_mascara_*`
  * `CAPACIDADES_POR_FLAVOR` sem a entrada        -> reprova `test_cada_mascara_*`
  * `NOME_DA_MASCARA` sem `"nintendo"`            -> reprova `test_a_tela_*`
"""
from __future__ import annotations

from typing import get_args

import pytest

from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    mascaras_validas,
    normalizar_mascara,
)
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    BOTOES_POR_FLAVOR,
    CAPACIDADES_POR_FLAVOR,
    FLAVORS,
    NINTENDO_PROCON_PRODUCT,
    NINTENDO_VENDOR,
    UinputGamepad,
    nomes_de_flavor_aceitos,
    normalize_flavor,
    resolver_flavor,
)

MASCARA = "nintendo"


# -- 1. o catálogo -------------------------------------------------------


def test_o_catalogo_tem_a_terceira_mascara_com_o_par_do_driver() -> None:
    """VID/PID lidos no fonte C: `hid-ids.h:1068,1073`.

    O par TEM de ser 057e:2009: medido em 07/09/2026 contra a libSDL2 desta
    máquina, é o único que devolve `SDL_GameControllerGetType = 5`
    (NINTENDO_SWITCH_PRO). Com outro PID a máscara não mostra prompt de
    Nintendo nenhum, que é a máscara inteira.
    """
    assert MASCARA in FLAVORS
    assert FLAVORS[MASCARA]["vendor"] == NINTENDO_VENDOR == 0x057E
    assert FLAVORS[MASCARA]["product"] == NINTENDO_PROCON_PRODUCT == 0x2009
    assert "Pro Controller" in FLAVORS[MASCARA]["name"]


def test_o_par_do_vpad_nao_e_o_par_que_o_produto_esconde() -> None:
    """VPAD-04/VPAD-06 para a máscara nova, medido no valor real do IGNORE.

    O invariante da casa é que o vpad nunca divida VID/PID com o aparelho que
    o produto manda a SDL esconder. Para o Nintendo não há segundo PID (ver
    o teste acima), então o invariante se verifica pelo outro lado: o par
    057e/2009 NÃO pode estar no `SDL_GAMECONTROLLER_IGNORE_DEVICES` que este
    produto emite.
    """
    from hefesto_dualsense4unix.daemon.launch_env import _IGNORE_VALUE

    assert "0x057e" not in _IGNORE_VALUE.lower()


# -- 2. o resolvedor, a CLI e o IPC --------------------------------------


@pytest.mark.parametrize("palavra", ["nintendo", "NINTENDO", " switch ", "pro", "procon"])
def test_o_resolvedor_estrito_aceita_a_palavra(palavra: str) -> None:
    """`resolver_flavor` é o portão do IPC (`gamepad.emulation.set`).

    Sem isto, pedir a máscara pela CLI ou pela tela devolve `invalid params`.
    """
    assert resolver_flavor(palavra) == MASCARA


def test_o_normalizador_tolerante_nao_troca_a_mascara_por_outra() -> None:
    """O caminho do disco: perfil e `DaemonConfig.gamepad_flavor`.

    `normalize_flavor` é tolerante de propósito, e é justamente por isso que
    ele já entregou CALADO uma máscara que ninguém pediu (o defeito de
    10/08/2026 com `"sony"`). Aqui ele não pode devolver `DEFAULT_FLAVOR`.
    """
    assert normalize_flavor(MASCARA) == MASCARA
    assert MASCARA in nomes_de_flavor_aceitos()


def test_o_registro_por_aparelho_aceita_a_mascara() -> None:
    """`external_mask` — a máscara por JOGADOR, que grava no disco.

    `mascaras_validas` deriva do `FLAVORS` e `normalizar_mascara` é ESTRITA:
    se a derivação quebrar, a escolha dela é recusada na gravação.
    """
    assert MASCARA in mascaras_validas()
    assert normalizar_mascara(" Nintendo ") == MASCARA


# -- 3. o esquema de perfil ----------------------------------------------


def test_o_esquema_de_perfil_conhece_as_mesmas_mascaras_do_catalogo() -> None:
    """Nos DOIS sentidos — sobrar aqui também é divergência.

    O `Literal` do pydantic é a única lista de máscaras digitada nesta casa
    (anotação não se calcula), e por ser digitada ela diverge calada: um
    perfil pedindo a máscara nova era recusado pelo pydantic com a máscara já
    viva no catálogo.
    """
    from hefesto_dualsense4unix.profiles.schema import MascaraDeGamepad

    assert set(get_args(MascaraDeGamepad)) == set(mascaras_validas())


def test_o_perfil_guarda_a_mascara_e_o_normalizador_a_devolve() -> None:
    from hefesto_dualsense4unix.profiles.schema import (
        ProfileModeConfig,
        normalizar_gamepad_flavor,
    )

    assert normalizar_gamepad_flavor(MASCARA) == MASCARA
    assert ProfileModeConfig(kind="gamepad", gamepad_flavor=MASCARA).gamepad_flavor == MASCARA


# -- 4. o env de lançamento ----------------------------------------------


def test_o_launch_env_esconde_o_fisico_sob_a_mascara_nova() -> None:
    """A perna que NENHUMA lista de catálogo alcança, e é a que dói.

    `compose_env` decide por `if flavor == ...`; um sabor fora dos dois ramos
    saía sem `SDL_GAMECONTROLLER_IGNORE_DEVICES` nenhum — e aí o jogo veria o
    DualSense físico E o vpad, com o sintoma de "controle dobrado" e nada
    apontando para a máscara nova.
    """
    from hefesto_dualsense4unix.daemon.launch_env import compose_env

    env = compose_env(
        native_mode=False,
        emulation_enabled=True,
        flavor=MASCARA,
        backends=["uinput"],
        fisicos=1,
    )
    xbox = compose_env(
        native_mode=False,
        emulation_enabled=True,
        flavor="xbox",
        backends=["uinput"],
        fisicos=1,
    )
    assert env["SDL_GAMECONTROLLER_IGNORE_DEVICES"]
    assert env["SDL_JOYSTICK_HIDAPI"] == "0"
    assert env["PROTON_DISABLE_HIDRAW"]
    # As duas sobem sempre em uinput e são evdev puro: mesmo tratamento.
    assert env == xbox


# -- 5. as tabelas por sabor ---------------------------------------------


@pytest.mark.parametrize("sabor", sorted(FLAVORS))
def test_cada_mascara_do_catalogo_tem_botoes_e_capacidades(sabor: str) -> None:
    """Fonte única de verdade: quem entra no `FLAVORS` entra nas duas tabelas.

    Sem isto, um sabor novo herda por `.get(..., padrão)` o conjunto de outro
    aparelho — que foi exatamente o defeito medido em 07/09/2026: com as
    capabilities do Xbox sob o par 057e:2009, a SDL aplica a tabela do Pro e
    o analógico DIREITO passa a ler o gatilho esquerdo.
    """
    assert sabor in BOTOES_POR_FLAVOR
    assert sabor in CAPACIDADES_POR_FLAVOR


def test_a_mascara_nintendo_imita_o_aparelho_que_o_driver_descreve() -> None:
    """Os 14 botões e os 4 eixos do `procon`, lidos em `hid-nintendo.c`.

    `procon_button_mappings` (14 entradas) + `joycon_config_left_stick`/
    `_right_stick`/`_dpad`. Os 14 têm de ser DECLARADOS mesmo os que nunca
    são pressionados (o Capture, `BTN_Z`): `bN` na tabela da SDL é a POSIÇÃO
    na ordem de código, e faltar um empurra todos os seguintes.

    E o Pro NÃO tem gatilho analógico — `ABS_Z`/`ABS_RZ` não podem estar aqui,
    senão `rightx` cai em cima do L2.
    """
    ecodes = pytest.importorskip("evdev").ecodes
    caps = CAPACIDADES_POR_FLAVOR[MASCARA](with_ff=False)

    botoes = set(caps[ecodes.EV_KEY])
    assert len(botoes) == 14
    assert ecodes.BTN_Z in botoes, "o Capture é o `misc1:b4` — sem ele tudo desloca"
    assert {ecodes.BTN_TL2, ecodes.BTN_TR2} <= botoes, "ZL/ZR são DIGITAIS no Pro"

    eixos = {codigo for codigo, _info in caps[ecodes.EV_ABS]}
    assert ecodes.ABS_Z not in eixos and ecodes.ABS_RZ not in eixos
    assert {ecodes.ABS_X, ecodes.ABS_Y, ecodes.ABS_RX, ecodes.ABS_RY} <= eixos
    assert {ecodes.ABS_HAT0X, ecodes.ABS_HAT0Y} <= eixos


def test_os_botoes_da_frente_seguem_a_posicao_como_a_casa_ja_decidiu() -> None:
    """8BIT-03: o `compose_env` crava `USE_BUTTON_LABELS=0` em toda variante.

    Com `=0` a SDL mapeia o Pro por POSIÇÃO (`a:b0,b:b1,x:b3,y:b2`), então a
    tabela desta máscara tem de ser a identidade dos códigos que o kernel já
    usa para o DualSense físico (`evdev_reader.BUTTON_MAP`). Uma tabela por
    RÓTULO faria o **cross** chegar ao jogo como `b` — medido em 07/09/2026,
    e "confirmar" viraria "voltar".
    """
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
    from hefesto_dualsense4unix.daemon.launch_env import compose_env

    env = compose_env(
        native_mode=False, emulation_enabled=True, flavor=MASCARA,
        backends=["uinput"], fisicos=1,
    )
    assert env["SDL_GAMECONTROLLER_USE_BUTTON_LABELS"] == "0"

    fisico = {nome: cod for cod, nome in EvdevReader.BUTTON_MAP.items()}
    for face in ("cross", "circle", "square", "triangle"):
        assert BOTOES_POR_FLAVOR[MASCARA][face] == fisico[face], (
            f"{face}: a máscara nintendo é POSICIONAL — o código tem de ser o "
            "mesmo que o kernel usa no DualSense físico"
        )


def test_os_gatilhos_digitais_tem_um_escritor_so() -> None:
    """`l2_btn`/`r2_btn` fora da tabela: quem escreve BTN_TL2/TR2 é o analógico.

    Dois escritores do mesmo código é um código cujo estado ninguém sabe.
    """
    assert "l2_btn" not in BOTOES_POR_FLAVOR[MASCARA]
    assert "r2_btn" not in BOTOES_POR_FLAVOR[MASCARA]
    assert UinputGamepad._gatilho_apertado(255, False) is True
    assert UinputGamepad._gatilho_apertado(0, True) is False
    # Histerese: parado em cima do ponto não oscila.
    assert UinputGamepad._gatilho_apertado(20, False) is False
    assert UinputGamepad._gatilho_apertado(20, True) is True


# -- 6. a tela -----------------------------------------------------------


def test_a_tela_sabe_nomear_a_mascara_e_o_chip_acende() -> None:
    """O chip do cartão: `mascaras_montaveis` é a interseção catálogo x rótulo.

    Enquanto `mesa_viva.NOME_DA_MASCARA` não tivesse a chave, o chip
    continuaria cinza com a máscara já viva no daemon — que é o defeito que
    esta sprint tinha por nome.
    """
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA
    from hefesto_dualsense4unix.interface.pacotes.a01_jogar import mascaras_montaveis

    assert NOME_DA_MASCARA[MASCARA] == "Nintendo Pro"
    assert "Nintendo Pro" in mascaras_montaveis()
    assert set(NOME_DA_MASCARA) >= set(mascaras_validas()), (
        "toda máscara do catálogo precisa de rótulo, senão o chip nasce cinza"
    )


def test_a_tela_diz_o_preco_da_mascara_nova() -> None:
    """O gatilho analógico é a perda, e ela tem de estar ESCRITA.

    Escolher entre três botões sem saber o que cada um custa não é escolher
    (MASCARA-QUE-GRUDA-01, decisão dela).
    """
    from hefesto_dualsense4unix.app.actions.home_actions import (
        texto_do_custo_da_mascara,
    )

    preco = texto_do_custo_da_mascara(MASCARA)
    assert preco, "máscara com perda e sem frase de preço é escolha às cegas"
    assert "gatilho" in preco.lower()


def test_a_tela_diz_o_quinto_preco_o_dos_botoes_da_frente() -> None:
    """Fora do lançador, os quatro botões da frente chegam trocados aos pares.

    A CONFERÊNCIA DE 07/09/2026 ACHOU A METADE QUE FALTAVA. A frase de preço
    declarava quatro perdas — giroscópio, acelerômetro, touchpad e o gatilho
    analógico — e calava a quinta, que a mesma medição tinha encontrado. Esta é
    a pior das cinco justamente porque **não parece defeito**: um jogo com
    confirmar e cancelar trocados responde a tudo, só responde errado.

    MEDIDO consultando a libSDL2 (2.30.0) desta máquina pelo GUID das TRÊS
    máscaras que o produto emite, com e sem a env que o
    `daemon.launch_env.compose_env` materializa
    (`SDL_GAMECONTROLLER_USE_BUTTON_LABELS=0`):

        057e:2009 (nintendo)  sem a env -> a:b1,b:b0,x:b2,y:b3
        057e:2009 (nintendo)  com  =0   -> a:b0,b:b1,x:b3,y:b2
        045e:028e (xbox)                -> a:b0,b:b1,x:b2,y:b3  nos DOIS
        054c:0df2 (dualsense)           -> a:b0,b:b1,x:b3,y:b2  nos DOIS

    O mapeamento de fábrica do Pro traz `hint:…USE_BUTTON_LABELS:=1` — a
    etiqueta da Nintendo, em que confirmar fica à direita. É a ÚNICA máscara do
    catálogo cujo mapa depende do lançador; por isso o preço é dela sozinha, e
    por isso a frase manda abrir o jogo pelo Hefesto.

    A MORDIDA: tirar da frase a menção aos botões da frente reprova aqui.
    """
    from hefesto_dualsense4unix.app.actions.home_actions import (
        TEXTO_CUSTO_MASCARA_NINTENDO,
        TEXTO_CUSTO_MASCARA_XBOX,
        texto_do_custo_da_mascara,
    )

    preco = texto_do_custo_da_mascara(MASCARA)

    assert "botões da frente" in preco, (
        "a frase cala a perda que não acusa: sem o lançador, X (Cruz) e "
        "Círculo trocam de papel, e o jogo não dá sinal nenhum de que trocou"
    )
    assert "Hefesto" in preco, (
        "dizer que trocam sem dizer o que fazer é alarme sem saída — a frase "
        "tem de mandar abrir o jogo pelo lançador, que é onde chegam certos"
    )
    for palavra in ("X (Cruz)", "Círculo"):
        assert palavra in preco, (
            f"{palavra!r} é o nome que esta casa dá ao botão "
            "(`input_actions.NOME_DO_BOTAO`); a frase tem de nomear os dois "
            "que trocam, senão quem lê não sabe o que testar"
        )

    assert "botões da frente" not in TEXTO_CUSTO_MASCARA_XBOX, (
        "o preço é da Nintendo SOZINHA — medido: sob 045e:028e a SDL entrega "
        "o mesmo mapa com e sem a env. Xbox herdar esta frase seria alarme "
        "sobre nada, que é a família de erro que `frases_que_ela_baniu` mata"
    )
    assert texto_do_custo_da_mascara("dualsense") == "", (
        "e sob DualSense também não muda nada (054c:0df2 medido nos dois) — "
        "a máscara sem perda continua sem frase"
    )
    assert preco == TEXTO_CUSTO_MASCARA_NINTENDO, (
        "a frase que a tela mostra saiu de sincronia com a constante que a "
        "nomeia — um dono, um texto: quem mudar a frase muda a constante"
    )
