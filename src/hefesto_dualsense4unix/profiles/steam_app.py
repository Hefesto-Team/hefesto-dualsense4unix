"""Fonte ÚNICA do predicado "esta `wm_class` é uma janela de jogo da Steam".

UNIFICA-PREDICADO-01 (05/08/2026). A mesma pergunta era respondida por CINCO
implementações independentes — `daemon/launch_env.py`, `profiles/manager.py`,
`profiles/simple_match.py`, `profiles/schema.py` e
`app/actions/launch_wrapper_dialog.py` — e elas já discordavam entre si: três
eram sensíveis a caixa, uma não; duas limpavam espaço, três não. A divergência
entre predicados que deveriam ser o mesmo é o buraco que o R-01 e o R-21
fecharam à mão, um de cada vez.

**A caixa é INSENSÍVEL, e isso é medido, não gosto.** `schema._casa_sem_caixa`
já documenta que a ``wm_class`` chega do X/XWayland com a caixa que o toolkit
escolheu e **muda de grafia entre backends de detecção**. Um predicado
sensível aqui reabriria o veto R-21 para uma janela que se anunciasse
``Steam_App_2111190``: o matcher de perfil casaria (ele compara sem caixa) e o
veto do catch-all NÃO reconheceria a janela como jogo — o genérico de desktop
voltaria a entrar por cima da regra do jogo.

**Por que este módulo mora em `profiles/` e não em `daemon/`.** A fonte tinha de
descer, não subir. `profiles/simple_match.py` é `profiles/` puro e é usado pelo
editor da GUI e pela CLI; se ele importasse `daemon.launch_env`, hoje não
fecharia ciclo (o `launch_env` só toca `profiles/` dentro de função), mas
ficaria a UM commit de distância de fechar
``profiles.simple_match -> daemon.launch_env -> profiles.manager ->
daemon.state_store -> daemon.launch_env``. Com a fonte aqui, o grafo tem só
``daemon -> profiles`` e ``app -> profiles``, que é a disciplina que
`profiles/sanidade.py` já descreve. Por isso este módulo **não importa nada do
projeto** — só `re`. Manter assim é o que garante que ninguém possa fechar o
ciclo por baixo.

`daemon/launch_env.py` REEXPORTA `steam_appid_from_wm_class` para que os
callsites históricos (e `tests/unit/test_wrapper_used.py`) continuem valendo.
"""
from __future__ import annotations

import re

#: `wm_class` que a Steam dá a TODA janela de jogo lançado por ela, sob Proton
#: ou nativo. IGNORECASE por medida (ver docstring do módulo).
_STEAM_APP_WC_RE = re.compile(r"^steam_app_(\d+)$", re.IGNORECASE)


#: As `wm_class` do CLIENTE Steam — a loja, a biblioteca, o Big Picture. Não
#: são jogo (não têm appid), e é justamente por isso que o
#: `steam_appid_from_wm_class` é cego para elas.
#:
#: VPAD-NA-JANELA-DA-STEAM-01 (17/08/2026). Essa cegueira tinha endereço e
#: preço: `lifecycle._janela_de_jogo_em_foco` protege a partida perguntando
#: "a janela em foco é um jogo?", e a resposta para o cliente Steam era
#: **não** — então alternar para a Steam no meio do jogo autorizava um perfil
#: de desktop a reverter o modo e **destruir o vpad**. Medido com par fechado:
#: ativar `Dont Scream` cria `/dev/hidraw4`, ativar `Navegação` (que casa com
#: `steam`) o faz sumir, e o jogo fica com um descritor órfão.
#:
#: `steamwebhelper` entra porque a Steam moderna é CEF: a loja e partes da
#: biblioteca se anunciam por ele, e do ponto de vista desta pergunta são a
#: mesma janela.
_WC_CLIENTE_STEAM = frozenset({"steam", "steamwebhelper"})


def e_janela_do_cliente_steam(wm_class: str | None) -> bool:
    """True se `wm_class` é o CLIENTE Steam (loja/biblioteca/Big Picture).

    Irmã de `steam_appid_from_wm_class`, e mora ao lado dela pela razão que
    fez este módulo nascer: a pergunta "que janela da Steam é esta?" já teve
    cinco donos que discordavam entre si. Mesmo contrato — insensível a caixa
    e tolerante a espaço em volta.

    **Não substitui a irmã, complementa.** Jogo tem appid e é `steam_app_N`;
    o cliente não tem. Quem precisa proteger a PARTIDA precisa das duas, e é
    exatamente essa soma que faltava.
    """
    if not isinstance(wm_class, str):
        return False
    return wm_class.strip().lower() in _WC_CLIENTE_STEAM


def steam_appid_from_wm_class(wm_class: str | None) -> int | None:
    """Appid do jogo a partir da wm_class (`steam_app_N`), ou None.

    Insensível a caixa e tolerante a espaço em volta — as duas coisas
    explícitas, porque dois dos cinco lugares unificados aqui já faziam
    `.strip()` e a fonte não fazia; decidir isso em silêncio seria mudar
    comportamento em silêncio. Devolve `int`: quem precisa de `str` (o diálogo
    do wrapper, o editor simples) converte no callsite.
    """
    if not isinstance(wm_class, str):
        return None
    m = _STEAM_APP_WC_RE.match(wm_class.strip())
    return int(m.group(1)) if m is not None else None


# --- O que ela COLA no campo "Nome do jogo:" (13/08/2026) -------------------
# Pedido dela: *"ou aplicamos um regex automático só de colar o link da loja do
# jogo e ele pega o id"*. O campo pedia o appid CRU, e o appid cru é a única
# coisa que ninguém tem em mãos — o que se tem em mãos é o endereço da loja,
# copiado do navegador com o `?snr=` que a Steam gruda em tudo.
#
# Mora AQUI, e não no editor, pela mesma razão que fez este módulo nascer: a
# pergunta "que appid é este texto?" já tinha cinco donos uma vez. O
# `simple_match.normalize_appid` delega para cá, então o caminho do Salvar
# aceita o endereço mesmo que a janela não tenha chegado a reescrever o campo.

#: Só a LOJA. `steamcommunity.com/app/<id>` fica de fora de propósito: o pedido
#: dela manda recusar "um link da Steam que não seja de `app/` (perfil,
#: comunidade, workshop)", e distinguir uma página de comunidade DE JOGO de uma
#: de perfil pelo caminho é adivinhação. O host da loja é o critério que não
#: exige adivinhar.
#:
#: `(?:[^/?#]+/)*` antes de `app/` cobre o `/agecheck/app/<id>/` que a própria
#: loja usa em jogo com aviso de idade; `(?:[/?#].*)?` no fim é o que joga o
#: `?snr=1_7_7_230_150_1` e o `/Sea_of_Stars/` para FORA do número.
_LOJA_STEAM_RE = re.compile(
    r"^(?:https?://)?(?:[\w-]+\.)*store\.steampowered\.com(?::\d+)?"
    r"/(?:[^/?#]+/)*app/(\d+)(?:[/?#].*)?$",
    re.IGNORECASE,
)

#: O endereço que a própria Steam escreve no `Exec=` dos atalhos `.desktop`
#: que ela gera — é o que o `catalogo_de_jogos` lê do disco, e é o que ela
#: copia do menu "Copiar endereço da página da loja" do cliente.
_RUNGAMEID_RE = re.compile(
    r"^steam://rungameid/(\d+)(?:[/?#].*)?$",
    re.IGNORECASE,
)

#: O appid já digitado, e a `wm_class` inteira colada de um journal/doctor.
#: Era o `_APPID_RE` de `simple_match`, que passou a delegar para cá.
_APPID_CRU_RE = re.compile(r"^(?:steam_app_)?(\d+)$", re.IGNORECASE)


def steam_appid_de_texto(texto: str | None) -> int | None:
    """Appid do que ela COLOU no campo, ou ``None`` quando não dá para saber.

    Reconhece, e só:

    - ``851100`` e ``steam_app_851100`` (o que o campo já aceitava);
    - ``https://store.steampowered.com/app/851100/Sea_of_Stars/``;
    - ``https://store.steampowered.com/app/851100``;
    - ``store.steampowered.com/app/851100/?snr=1_7_7_230_150_1`` (sem esquema);
    - ``steam://rungameid/851100``.

    Recusa — devolvendo ``None``, sem adivinhar — endereço de outra loja,
    endereço da Steam que não seja da página do jogo, e texto qualquer. E
    **appid é numérico**: um ``/app/sea_of_stars`` não vira id nenhum.

    Não normaliza nada além de espaço em volta: quem decide se ``None`` é erro
    é quem chamou (o editor levanta a frase de gente; a detecção de round-trip
    só ignora), exatamente como já era em `normalize_appid`.
    """
    if not isinstance(texto, str):
        return None
    limpo = texto.strip()
    if not limpo:
        return None
    for regex in (_APPID_CRU_RE, _RUNGAMEID_RE, _LOJA_STEAM_RE):
        achado = regex.match(limpo)
        if achado is not None:
            return int(achado.group(1))
    return None


def parece_endereco(texto: str | None) -> bool:
    """O texto parece um endereço COLADO — e não um nome sendo digitado?

    É o gatilho da frase "não reconheci" da janela, e ele é estreito de
    propósito. Enquanto ela digita ``Sea`` atrás do jogo na lista, um alerta
    piscando a cada tecla seria pior que silêncio; quando ela cola
    ``https://www.gog.com/game/...``, o silêncio é que seria pior.

    O critério é a barra: nome de jogo não tem ``/``, endereço tem sempre.
    """
    if not isinstance(texto, str):
        return False
    return "/" in texto.strip()


__all__ = [
    "parece_endereco",
    "steam_appid_de_texto",
    "steam_appid_from_wm_class",
]
