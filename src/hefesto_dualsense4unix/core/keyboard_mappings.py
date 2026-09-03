"""Mapeamentos default de botão do DualSense para sequência de teclas.

Introduzido em FEAT-KEYBOARD-EMULATOR-01 (sub-sprint 1 de
FEAT-MOUSE-TECLADO-COMPLETO-01). Define `DEFAULT_BUTTON_BINDINGS` hardcoded
cobrindo Options, Share/Create, L1, R1, L3, R3.

Formato de binding: `tuple[str, ...]` com nomes canônicos `KEY_*` do
`evdev.ecodes`. Uma tupla com 1 elemento é tecla única; múltiplos elementos
representam combo (todos os modificadores pressionados junto com a tecla
final, emitidos em ordem de press e liberados em ordem reversa).

Exemplos:
- `("KEY_LEFTMETA",)` — tecla Super.
- `("KEY_LEFTALT", "KEY_TAB")` — Alt+Tab.
- `("KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_TAB")` — Alt+Shift+Tab.

Botões cobertos nesta sprint (baseados em `evdev_reader._BUTTONS`):
    options, create (Share), l1, r1, l3, r3.

Fora desta sprint-1:
- touchpad_press — evdev ainda não expõe keycode consistente (ver comentário
  em `src/hefesto_dualsense4unix/core/evdev_reader.py` linha 89).
- cross/circle/triangle/square — reservados para mouse (FEAT-MOUSE-01/02);
  serão reconfiguráveis via UI em FEAT-KEYBOARD-UI-01.
- dpad_* — reservados para mouse (setas); mesma razão.
- L2/R2 inversão — pertence à sub-sprint UI (depende de persistência).

Persistência por perfil e UI de edição entram em sub-sprints filhas.
"""
from __future__ import annotations

KeyBinding = tuple[str, ...]

# Tokens virtuais reservados (FEAT-KEYBOARD-UI-01). Não são teclas reais:
# o `UinputKeyboardDevice` reconhece o prefixo `__`/sufixo `__` e delega ao
# callback do subsystem em vez de emitir via uinput. Mantê-los em constantes
# evita literais mágicos espalhados pelo código.
TOKEN_OPEN_OSK = "__OPEN_OSK__"
TOKEN_CLOSE_OSK = "__CLOSE_OSK__"
#: O TERCEIRO, e é o preset do L3 desde 02/09/2026. DECISÃO DELA, verbatim:
#: *"deixar no preset do botão L3, no mapeamento, abrir o teclado virtual e
#: fechar o teclado virtual caso apertado novamente."*
#:
#: POR QUE UM TOKEN NOVO, e não `__OPEN_OSK__` passando a alternar: quem
#: escolhe "Abrir" numa das vinte e uma linhas da tela pede ABRIR, e um botão
#: que fecha o que a pessoa acabou de abrir seria outra coisa com o mesmo nome.
#: Os dois antigos continuam valendo — o que muda é qual deles o L3 recebe de
#: fábrica.
TOKEN_TOGGLE_OSK = "__TOGGLE_OSK__"

DEFAULT_BUTTON_BINDINGS: dict[str, KeyBinding] = {
    "options": ("KEY_LEFTMETA",),
    "create": ("KEY_SYSRQ",),
    "l1": ("KEY_LEFTALT", "KEY_LEFTSHIFT", "KEY_TAB"),
    "r1": ("KEY_LEFTALT", "KEY_TAB"),
    # L3 ALTERNA o teclado virtual do sistema (onboard/wvkbd-mobintl) desde
    # 02/09/2026; R3 continua fechando. O token virtual é interceptado pelo
    # UinputKeyboardDevice e delegado ao keyboard subsystem — não emite evento
    # real de tecla. Previne colisão com R3=BTN_MIDDLE do mouse porque este
    # último só atua quando `mouse_emulation_enabled=True`. Quem habilita
    # mouse+teclado juntos pode sobrescrever l3/r3 via UI (FEAT-KEYBOARD-UI-01)
    # removendo o conflito explicitamente.
    #
    # ANTES o L3 era `__OPEN_OSK__` puro, e o único jeito de fechar era o R3 —
    # que em modo mouse é o Botão do meio, e por isso a pessoa que joga não o
    # tem livre. Um botão que só abre deixa a janela do teclado por cima do
    # jogo, e o produto não oferecia saída no mesmo dedo.
    "l3": (TOKEN_TOGGLE_OSK,),
    "r3": (TOKEN_CLOSE_OSK,),
    # Regiões do touchpad (click firme, não toque leve) — emitidas pelo
    # `TouchpadReader` no device separado expose pelo kernel hid_playstation.
    # O dispatcher (`dispatch_keyboard`) mescla `regions_pressed()` ao
    # frozenset de botões antes de passar ao device, permitindo que as 3
    # regiões sejam tratadas como "botões" virtuais aqui — API uniforme.
    "touchpad_left_press": ("KEY_BACKSPACE",),
    "touchpad_middle_press": ("KEY_ENTER",),
    "touchpad_right_press": ("KEY_DELETE",),
}

#: O PADRÃO QUE A TELA PUBLICADA AINDA NÃO SABE DIZER — e ele GRAVA no perfil
#: dela uma escolha que ela não fez. Botão -> (o que o produto faz de fábrica,
#: o que a página publicada mostra no lugar).
#:
#: MEDIDO em 02/09/2026, na base `onda/abas-0209` (242c3e0c), repetindo a conta
#: de `interface/pacotes/a06_navegacao.guardar_definicoes` sobre a forma que a
#: página publicada devolve ao piloto:
#:
#:     PUBLICADA  padrao_l3 = __TOGGLE_OSK__ · tela_l3 = 'Abrir o teclado na
#:                tela' -> grava_no_perfil = {'l3': '__OPEN_OSK__'}
#:     BANCADA    padrao_l3 = __TOGGLE_OSK__ · tela_l3 = 'Abrir e fechar o
#:                teclado na tela' -> grava_no_perfil = None
#:
#: A CADEIA, e ela tem quatro elos: (1) o L3 nasce alternador aqui;
#: (2) `acoes_de_botao.padrao()` deriva o padrão das 21 linhas DESTE mapa;
#: (3) a página que o produto renderiza foi congelada antes do alternador
#: existir, não tem a `<option>` do rótulo novo, e por isso a pintura do
#: `acao-l3` é RECUSADA em silêncio (`hefesto_vivo.escrever`, alvo `valor`:
#: um `<select>` só aceita o texto exato de uma opção que ele oferece);
#: (4) o "Guardar" recolhe o `select.value` das 21 linhas, compara com o padrão
#: e grava a diferença — que aqui não é escolha dela, é o desenho congelado.
#: Ela não precisa tocar na linha do L3: basta clicar em "Guardar" para mudar
#: qualquer OUTRA linha.
#:
#: O QUE ISSO CUSTA, medido pelo fio do daemon
#: (`acoes_de_botao.resolver` -> `profiles.manager.resolve_key_bindings`):
#: sem override o device recebe `['__TOGGLE_OSK__']`, com o que o "Guardar"
#: grava ele recebe `['__OPEN_OSK__']` — **o L3 para de alternar naquele
#: perfil**, e no tique seguinte a pintura volta a casar, o campo sai da lista
#: de endereços mortos da régua do mockup e não sobra rastro em lugar nenhum.
#: A saída existe e fica a dois centímetros na tela: o "Voltar ao padrão"
#: (`a06_navegacao.padrao_definicoes`) zera `button_actions` e `key_bindings`.
#:
#: ESTA DECLARAÇÃO NÃO É A CURA — é o que a torna VISÍVEL e datada. A cura mora
#: fora deste módulo, em três lugares possíveis, e nenhum deles é aqui:
#:   * a PUBLICAÇÃO da `06-navegacao.html` (`check_o_desenho_aprovado.py
#:     --publicar 06`), que é ato DELA e fecha o caso inteiro;
#:   * `interface/pacotes/a06_navegacao.guardar_definicoes`, gravando só as
#:     linhas que a pintura conseguiu escrever, ou dizendo antes o que vai
#:     gravar;
#:   * `interface/hefesto_vivo.escrever`, que hoje recusa um valor fora do
#:     `<select>` sem contar a ninguém.
#:
#: A REGRA QUE ELA DEIXA, e vale para toda aba: **um padrão de fábrica fora do
#: vocabulário da tela publicada vira escolha dela no disco.** Trocar um padrão
#: e publicar a página são o mesmo trabalho, e a ordem importa.
#:
#: `tests/unit/test_o_padrao_de_fabrica_cabe_na_tela_publicada.py` cobra esta
#: tabela contra a MEDIÇÃO, nos dois sentidos: padrão novo fora da tela sem
#: declaração reprova na hora, e declaração que caducou (ela publicou) reprova
#: também — é o sino que manda apagar a linha.
# A DECLARAÇÃO DO `l3` MORREU EM 03/09/2026, e morreu do jeito certo: ela
# existia porque a `06-navegacao.html` publicada tinha sido congelada ANTES de o
# L3 virar alternador, e não oferecia a `<option>` do rótulo novo. A página de
# hoje traz *"Abrir e fechar o teclado"* nos 28 seletores — o defeito acabou por
# PUBLICAÇÃO, que é ato dela.
#
# `test_o_padrao_de_fabrica_cabe_na_tela_publicada.py` cobra os dois sentidos e
# foi ele que apontou a caducidade, com a frase que é a regra: *declaração que
# sobrevive ao defeito é lápide*. O mecanismo que a consome
# (`a06_navegacao._congelado_na_tela`) fica de pé, vazio, para a próxima linha
# que alguém congelar.
PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ: dict[str, tuple[str, str]] = {}


def is_virtual_token(token: str) -> bool:
    """True se `token` é um marcador `__XXX__` (delegado ao callback)."""
    return len(token) >= 4 and token.startswith("__") and token.endswith("__")


def parse_binding(spec: str) -> KeyBinding:
    """Converte `"KEY_LEFTALT+KEY_TAB"` em `("KEY_LEFTALT", "KEY_TAB")`.

    Formato aceito:
    - Tecla única: `"KEY_ENTER"`.
    - Combo: `"KEY_LEFTALT+KEY_TAB"`, `"KEY_LEFTCTRL+KEY_LEFTSHIFT+KEY_T"`.
    - Token virtual OSK: `"__TOGGLE_OSK__"`, `"__OPEN_OSK__"`,
      `"__CLOSE_OSK__"` — aceitos COMO ESTÃO (marcadores `__*__` do
      `is_virtual_token`), sem exigir `KEY_*`. O primeiro é o default de l3 e o
      terceiro o de r3; a legenda da UI manda digitá-los. O downstream
      (`UinputKeyboardDevice` / keyboard subsystem) os intercepta via
      `is_virtual_token` e delega ao callback de OSK em vez de emitir tecla.

    Tokens são stripped e uppercased. Vazio retorna tupla vazia. Strings que
    não sejam `KEY_*` nem token virtual `__*__` levantam `ValueError` —
    validação completa contra `evdev.ecodes` fica a cargo do loader de perfil
    (sub-sprint 2).
    """
    if not spec or not spec.strip():
        return ()
    tokens = [tok.strip().upper() for tok in spec.split("+") if tok.strip()]
    for tok in tokens:
        if is_virtual_token(tok):
            # Marcador `__TOGGLE_OSK__`/`__OPEN_OSK__`/`__CLOSE_OSK__` —
            # preservado como está.
            continue
        if not tok.startswith("KEY_"):
            raise ValueError(
                f"token {tok!r} fora do padrão 'KEY_*' "
                f"(binding recebido: {spec!r})"
            )
    return tuple(tokens)


def format_binding(binding: KeyBinding) -> str:
    """Inverso de `parse_binding`. Útil para serialização e UI."""
    return "+".join(binding)


__all__ = [
    "DEFAULT_BUTTON_BINDINGS",
    "PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ",
    "TOKEN_CLOSE_OSK",
    "TOKEN_OPEN_OSK",
    "TOKEN_TOGGLE_OSK",
    "KeyBinding",
    "format_binding",
    "is_virtual_token",
    "parse_binding",
]

# "O homem é a medida de todas as coisas." — Protágoras
