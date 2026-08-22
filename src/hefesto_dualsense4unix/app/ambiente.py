"""Qual é a área de trabalho desta sessão — e o que dizer sobre a barra do sistema.

Por que um módulo público, se quatro lugares já leem `XDG_CURRENT_DESKTOP`: os
quatro leitores de hoje são privados e nenhum devolve um NOME. `tray.py:90
_desktop_is_cosmic` responde sim/não; `main.py:33-38` decide o `GDK_BACKEND`;
`integrations/window_backends/wayland_portal.py:149` escolhe o portal. A aba
Configurações precisa de outra coisa: o nome do ambiente para mostrar na tela, e
a correção dela quando a leitura erra.

**A regra que governa o módulo inteiro: o ambiente informa a MENSAGEM, nunca o
comportamento.** Nada aqui decide o que o produto faz — decide o que a tela diz.
É o que permite a aba abrir igual nos três casos que a variável entrega de
verdade: vazia (sessão sem área de trabalho, e é o caso de todo teste headless),
composta (`pop:GNOME`, medido nesta bancada) ou com um nome só (`COSMIC`).

A correção manual mora em `gui_preferences.json`, e não em `maquina.json`: é
preferência de JANELA — o serviço em segundo plano nunca a lê, e nenhuma outra
tela depende dela.
"""
from __future__ import annotations

import os
from collections.abc import Mapping

from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs, set_pref

#: Chave da correção manual em `~/.config/hefesto-dualsense4unix/gui_preferences.json`.
CHAVE_AMBIENTE = "ambiente_corrigido"

#: As três escolhas da tela, `(id, rótulo)`, na ordem do desenho aprovado.
#:
#: A capitalização é a do desenho e não é descuido: COSMIC e GNOME são siglas,
#: "Outro" é palavra comum. O portão de redação da aba cobra a inicial
#: maiúscula das três (`test_config_a_palavra_de_tela_da_aba_montada.py`).
AMBIENTES: tuple[tuple[str, str], ...] = (
    ("cosmic", "COSMIC"),
    ("gnome", "GNOME"),
    ("outro", "Outro"),
)

#: O nome de tela de cada id, derivado de `AMBIENTES` — nunca uma segunda lista.
NOMES_DE_TELA: dict[str, str] = dict(AMBIENTES)

#: As duas variáveis que descrevem a sessão, na ordem em que `tray.py:92-97` as
#: concatena. São duas porque nenhuma das duas basta: o COSMIC declara a
#: primeira, e há sessão que só preenche a segunda.
_VARIAVEIS_DA_SESSAO = ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP")


def ambiente_lido(*, variaveis: Mapping[str, str] | None = None) -> str:
    """O que a sessão declara, cru, como `tray.py:92-97` já lê.

    Devolve as duas variáveis unidas por `:` — `"COSMIC:cosmic"`, `"pop:GNOME:pop"`
    — e **string vazia quando nenhuma das duas existe**, que é o caso de toda
    sessão headless e o primeiro caso do aceite desta seção.

    `variaveis` entra por argumento com o ambiente real como padrão (a regra F4
    da leva): é o que permite ao teste declarar uma sessão falsa sem tocar no
    `os.environ` do processo, que é global e vaza para os testes vizinhos.
    """
    fonte = os.environ if variaveis is None else variaveis
    partes = [fonte.get(nome, "") for nome in _VARIAVEIS_DA_SESSAO]
    return ":".join(parte for parte in partes if parte)


def ambiente_normalizado(bruto: str | None) -> str:
    """Reduz a declaração crua a um dos três ids de `AMBIENTES`.

    Casa por SUBSTRING e sem diferenciar maiúscula, porque a variável é uma
    lista: `pop:GNOME` é o que esta bancada mede num Pop!_OS, e um `==` a
    classificaria como "outro" — que é o defeito que faz a instrução da extensão
    nunca aparecer justamente em quem precisa dela.

    COSMIC é conferido primeiro: uma sessão COSMIC pode carregar `GNOME` na
    lista por compatibilidade, e a recíproca não acontece.

    `None` e `""` devolvem `"outro"` sem levantar — ausência de resposta é uma
    resposta, e não pode derrubar a montagem da aba.
    """
    texto = (bruto or "").lower()
    if "cosmic" in texto:
        return "cosmic"
    if "gnome" in texto:
        return "gnome"
    return "outro"


def ambiente_efetivo(*, variaveis: Mapping[str, str] | None = None) -> str:
    """O ambiente que vale para a tela: a correção dela vence a detecção.

    Correção fora dos três ids é ignorada em silêncio — o arquivo de
    preferências é texto editável à mão, e um valor inventado ali não pode
    fazer a aba mentir nem levantar.
    """
    escolha = load_gui_prefs().get(CHAVE_AMBIENTE)
    if isinstance(escolha, str) and escolha in NOMES_DE_TELA:
        return escolha
    return ambiente_normalizado(ambiente_lido(variaveis=variaveis))


def gravar_correcao_de_ambiente(escolha: str) -> None:
    """Grava a correção manual. Id desconhecido não grava nada.

    Sem rascunho e sem "Aplicar": esta seção é a exceção declarada ao
    deferimento da aba (decisão da execução, 22/08/2026), porque o "Aplicar" do
    rodapé envia gatilhos e vibração AOS CONTROLES — e ambiente não é ajuste de
    controle nenhum.
    """
    if escolha not in NOMES_DE_TELA:
        return
    set_pref(CHAVE_AMBIENTE, escolha)


def frase_do_detectado(bruto: str) -> str:
    """A linha que diz o que foi detectado, para a pessoa poder discordar.

    O texto com nome é o aprovado no desenho (`TOOLTIPS.md`, linha "Ambiente");
    a variante sem nome existe porque o desenho não previu o caso REAL de uma
    sessão que não declara nada — e afirmar "Outro" ali seria a tela inventando
    uma detecção que não houve.
    """
    if not bruto:
        return "A sessão não diz qual é o ambiente. Corrija se souber qual é."
    return f"Detectado: {NOMES_DE_TELA[ambiente_normalizado(bruto)]}. Corrija se estiver errado."


def mensagem_da_bandeja(ambiente: str, watcher_presente: bool) -> str:
    """O que a seção diz sobre o ícone na barra do sistema.

    Esta função existe separada da tela por um motivo de portão: o aceite desta
    sprint é *"num GNOME sem a extensão, a seção mostra a instrução"*, e não há
    GNOME nesta bancada. Com a decisão aqui dentro, os quatro casos viram teste
    que morde sem depender de sessão nenhuma.

    Nenhum dos textos foi copiado de `tray.py:326-331`, e isso é deliberado: lá
    a frase está sem acento em "Area de status" e usa "Tray icon", que é jargão.
    A forma acentuada e sem jargão é a de `app.py:1428`.

    Quando o ambiente não é nenhum dos dois conhecidos, a mensagem diz o que
    houve e **não afirma o que falta** — o produto não sabe, e chutar uma
    instrução manda a pessoa mexer no lugar errado.
    """
    if watcher_presente:
        return "A barra do sistema desta sessão recebe o ícone do Hefesto."
    if ambiente == "gnome":
        return (
            "A barra do sistema desta sessão não recebe o ícone. No GNOME ele depende "
            "de uma extensão: ligue a extensão ubuntu-appindicators@ubuntu.com, saia "
            "da sua conta e entre de novo."
        )
    if ambiente == "cosmic":
        return (
            "A barra do sistema desta sessão não recebe o ícone. No COSMIC, ligue o "
            "applet 'Área de status' em Configurações > Painel."
        )
    return (
        "A barra do sistema desta sessão não recebe o ícone, e neste ambiente o Hefesto "
        "não sabe dizer o motivo. A janela continua abrindo normalmente."
    )


__all__ = [
    "AMBIENTES",
    "CHAVE_AMBIENTE",
    "NOMES_DE_TELA",
    "ambiente_efetivo",
    "ambiente_lido",
    "ambiente_normalizado",
    "frase_do_detectado",
    "gravar_correcao_de_ambiente",
    "mensagem_da_bandeja",
]
