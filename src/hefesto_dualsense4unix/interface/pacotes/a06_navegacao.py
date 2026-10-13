#!/usr/bin/env python3
"""O pacote da aba `06` Navegação.

Quem tem dono: o PRIMÁRIO (`is_primary`) navega o PC, e vem do daemon (o `NAVEGA` do gerador tirava
o MENOR número da mesa, que só acertava enquanto o P1 estivesse na frente).

Os seis gestos (PS+Options, PS+↑…) têm dono desde 01/10/2026
(OS-GESTOS-DO-CONTROLE-FAZEM-O-QUE-DIZEM-01): a tabela mora no `maquina.json`
(`core/acoes_do_gesto.tabela`), o daemon despacha por ela e a lista da tela grava e pinta por ela
(ver `acao_do_gesto`, no fim do módulo). Os cinco gestos NÃO moram no perfil: ele guarda
`key_bindings`, que são BOTÕES (options, create, l1, r1, l3, r3 e as três regiões do touchpad),
nunca combo.

O `ps_button_action` escreve-se por `daemon.reload` (`config_overrides` com qualquer campo do
`DaemonConfig`; não grava em disco, então a escolha morre no próximo start do daemon) e NÃO é o
único ajustável: o toque solo no PS tem dono no PERFIL (`Profile.button_actions["ps"]`,
ONDA5-06-01), que VENCE o degrau da máquina (tabela em `hotkey._a_metade_da_maquina`). Ele viaja só
na resposta de `daemon.reload` (`_config_que_viaja`), nunca no estado do tique; por isso a tira
desta aba não NOMEIA o ato da máquina (`_o_que_o_ps_faz`).

**Os 29 endereços desta aba estão vivos** (02/09/2026): a `--prova-de-mockup` classificava 28 deles
como INDECIDÍVEL porque o valor pintado COINCIDE com o do desenho. A cura foi fazer o valor MUDAR,
com um DUBLÊ no lugar do daemon (três controles sintéticos, `speed=11`, `scroll_speed=4`, teclado
desligado, `button_actions` trocando as 21 linhas), e ver a tela acompanhar: bancada 1/0/28
(produto/mockup/ indecidível), dublê 29/0/0. A régua que reproduz sem janela é
`tests/unit/test_a_06_o_duble_decide_o_indecidivel.py`.

**A pintura não desfaz a escolha de quem clica** (02/09/2026, decisão de produto: *"as 21 listas
param de ser repintadas enquanto ela está mexendo, até guardar ou sair"*). Medido com dublê,
escolhendo como uma pessoa (evento `change`): a pintura punha «Botão direito», o clique «F11», +100
ms «F11», +1500 ms «Botão direito». Duas causas desta aba: os 21 `<select>` não casavam com nenhum
endereço clicável do ouvinte (`manda_do_alvo`, em `hefesto_vivo.py`), logo a escolha não chegava ao
Python, e o tique seguinte reescrevia o valor do perfil por cima (o "Guardar" nunca recebia forma
diferente do perfil). O gerador marca as 21 linhas com `data-gesto` (`aba06.LINHA_DE_BOTAO`), o
gesto `linha-de-botao` anota a escolha em `_MEXENDO` e a pintura CONCORDA com a tela
(`_o_que_a_tabela_mostra`). A mesma forma de defeito vale para toda lista e campo digitável das
outras abas (editor da Perfis, `<select>` da Conexões); a cura geral é o `escrever()` não sobrepor o
que a pessoa edita.

**Recusa na tela** (FRASES-E-DICAS-01, 13/09/2026): nenhuma frase de recusa fala com o usuário na
tela. `RuntimeError` e `ValueError` vão ao mesmo diário e o botão pisca `hef-recusou`; o `desfechos`
guarda a classe da exceção. Opção de VERDADE que caia em `ValueError` segue sendo defeito: pisca
recusa para escolha que devia valer.

**Nenhum `return` mudo** (02/09/2026): o "Guardar" e o "Voltar ao padrão" saíam sem uma palavra
quando não havia o que fazer, e a trava contra o apagador manda *"espere a tabela se preencher e
clique de novo"* para cair no mesmo `return`. Recusar DIZENDO: `guardar_definicoes` e
`padrao_definicoes`.

**A «Função do teclado» tem três opções** (decisão de 02/09/2026): `Só dentro do jogo` · `Só fora do
jogo` · `Desativado`; o padrão de um perfil novo é `Só fora do jogo` (no jogo o L3 é o clique do
analógico e o teclado atrapalha; no desktop é onde serve), e esse padrão é do esquema, não desta
aba. Duas têm dono e uma recusa dizendo; qual é qual está medido no corpo de `teclado()`.

**A aba fala a língua da página CARREGADA** (02/09/2026): os geradores escrevem em `mockup/`, o
produto lê `interface/paginas/` e só recebe quando ela publica. Trocar as três palavras na bancada e
falar só elas deixou duas das três opções como clique morto E mudo (o `_recusou_dizendo` do piloto
leva à tela a frase do `RuntimeError`, não a do `ValueError`, que fala com quem programa) e, com o
teclado desligado, a linha AFIRMAVA `Ligada — atalhos e teclado na tela`, pois o `escrever()`
descarta o texto que não casa com nenhuma `<option>`. Os sinônimos da travessia saíram em 03/09/2026
(`test_os_sinonimos_da_travessia_tem_prazo`); fica `PALAVRAS_DO_TECLADO`, que confere a palavra
contra a página carregada. **Mudar rótulo, opção ou número de casas na bancada obriga a perguntar o
que acontece na tela do usuário HOJE.**

**Mudança não é pintura**: o `--passear` imprime `06-navegacao.html  1  3`, e o `3` conta MUDANÇA (o
`escrever()` devolve `1` só quando o valor novo difere do mostrado); a aba pinta os OITO elementos
endereçados, cinco já coincidiam com o daemon. Ler "mudança" como "pintura" escondeu defeitos reais:
metade da linha do cartão indo para a tela (`_linha_do_cartao`), 8 chaves de 14 emitidas para o
vazio (`SEM_ENDERECO`) e um "Guardar" que apagava o perfil (`guardar_definicoes`).
"""
from __future__ import annotations

import html
import re
import time
from typing import Any

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.core import remapeamento_de_botao as remap
from hefesto_dualsense4unix.core.keyboard_mappings import (
    PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ,
)

from . import (
    LUGAR_VAZIO,
    MARCAS_DO_LUGAR,
    NOME_SEM_LEITURA,
    SEM_NINGUEM_AQUI,
    TODOS_OS_LUGARES,
    TRAVESSAO,
    Contexto,
    identidade_de,
    jogador_de,
    perfil,
    registrar,
)

#: O daemon publica as duas (rolagem inclusive); ver `SEM_ENDERECO` abaixo.
SEM_DONO: dict[str, str] = {}

#:                     traduzida por `BLOQUEIO_DO_MOUSE_EM_PORTUGUES`;
#:                     `input_actions.frase_do_teclado_na_tela`;
#:                     `emulation_actions.descrever_teclado_emulado`.
SEM_ENDERECO: dict[str, str] = {
    "rato-despachando": "a GTK não tem frase para 'o daemon está despachando' — "
                        "as quatro dela falam do device, que `rato-estado` já "
                        "diz. Inventar a frase é decisão dela",
    "gestos": "a tabela da tela é a dos seis GESTOS, e `key_bindings` são os "
              "nove BOTÕES — não é o mesmo dado, e não há linha para ele",
    "gestos-lista": "idem; e a lista é estrutura, que o piloto pula",
}

TECLADO_SO_FORA = "Só fora do jogo"
TECLADO_DESATIVADO = "Desativado"
TECLADO_SO_DENTRO = "Só dentro do jogo"

#: A chave «Também no jogo» no topo das Definições (O-GATILHO-VIRA-CLIQUE-SEM-LIGAR-O-CURSOR-01,
#: opção b). O endereço pinta o interruptor (`Sim`/`Não`); o segundo acende o cinza no modo nativo,
#: em que o jogo lê o controle direto e a tabela não toca em nada (o cinza da Mira,
#: `a02_controles.MIRA_NO_NATIVO`). O endereço de CADA chip da fita é o do `monta.fita()` e da 09:
#: sem ele o `--plastico` do chip é cor cravada para `check_identidade_vem_de_cima.py`.
CAMPO_DO_CHIP = "fita-chip"
ENDERECO_DA_CHAVE = "tabela-no-jogo"
ENDERECO_DA_CHAVE_FORA = "tabela-no-jogo-fora"
CHAVE_LIGADA = "Sim"
CHAVE_DESLIGADA = "Não"
CHAVE_NO_NATIVO = "NATIVO"
CHAVE_CINZA_NO_NATIVO = (
    "Em modo nativo o jogo lê este controle direto, e a tabela não age junto "
    "com ele.")

PALAVRAS_DO_TECLADO: dict[bool, tuple[str, ...]] = {
    True: (TECLADO_SO_FORA,),
    False: (TECLADO_DESATIVADO,),
}

PONTO = ' <span class="pt">•</span> '

BOLINHA = '<span class="bolinha"></span>'

PAPEL_QUE_NAVEGA = "Navega o PC"
PAPEL_SO_A_JANELA = "Só a janela"
PAPEL_DO_CURSOR = "Move o cursor"

#: A lista «Tipo de navegação» (A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01): o
#: tipo que o daemon guarda (`navegacao.interna.set {tipo}`) e o rótulo mostrado, na ordem do pedido
#: (Interna primeiro).
TIPO_INTERNA = "interna"
TIPO_COMPUTADOR = "computador"
ROTULOS_DO_TIPO: dict[str, str] = {
    TIPO_INTERNA: "Interna — cada controle ajusta o seu",
    TIPO_COMPUTADOR: "O computador — mouse e teclado",
}

#: A lista «Modo Big Picture na Steam»
#: (A-ABA-NAVEGACAO-FAZ-O-QUE-DIZ-E-O-MODO-STEAM-NAVEGA-O-BIG-PICTURE-01): dois valores; o dono é o
#: `navegacao.big_picture.set`.
BIG_PICTURE_DESLIGADO = "Desligado"
BIG_PICTURE_LIGADO = "Ligado — o controle navega o Big Picture"


def _navegacao(estado: dict[str, Any] | None) -> dict[str, Any]:
    """O bloco `navegacao` do `state_full` (o dono é o daemon), ou vazio."""
    bloco = (estado or {}).get("navegacao")
    return bloco if isinstance(bloco, dict) else {}


def big_picture_ligado(estado: dict[str, Any] | None) -> bool | None:
    """O que o daemon diz do Modo Big Picture, ou ``None`` sem o bloco (a tela não afirma)."""
    bloco = _navegacao(estado).get("big_picture")
    ligado = bloco.get("ligado") if isinstance(bloco, dict) else None
    return ligado if isinstance(ligado, bool) else None


def tipo_de_navegacao(estado: dict[str, Any] | None) -> str:
    """O tipo escolhido na lista. Sem o bloco do daemon, só o computador existe."""
    tipo = _navegacao(estado).get("tipo")
    return tipo if tipo in ROTULOS_DO_TIPO else TIPO_COMPUTADOR


def interna_ligada(estado: dict[str, Any] | None) -> bool:
    """A Navegação Interna está ligada, pelo bloco do daemon; sem ele, não."""
    return _navegacao(estado).get("interna_ligada") is True

#: `core/acoes_de_botao.BOTOES` — a lista é do produto, e não se digita aqui.
PREFIXO_DA_ACAO = "acao-"  # (noqa-acento) prefixo de endereço, não é prosa

PREFIXO_DA_TECLA = "tecla-"  # (noqa-acento) prefixo de endereço, não é prosa

PREFIXO_DA_TROCA = "troca-"  # (noqa-acento) prefixo de endereço, não é prosa

SEM_TROCA = "— Sem troca —"

ROTULOS_DA_TROCA: dict[str, str] = {
    "Triângulo": "triangle",
    "Círculo": "circle",
    "Quadrado": "square",
    "Cruz": "cross",
    "L1": "l1",
    "R1": "r1",
    "L2": "l2",
    "R2": "r2",
    "L3 (clique)": "l3",
    "L3 (direção)": acoes.EIXO_ESQUERDO,
    "R3 (clique)": "r3",
    "R3 (direção)": acoes.EIXO_DIREITO,
    "D-pad cima": "dpad_up",
    "D-pad direita": "dpad_right",
    "D-pad baixo": "dpad_down",
    "D-pad esquerda": "dpad_left",
    "Share": "create",
    "Options": "options",
    "Touchpad (clique)": remap.DESTINO_TOUCHPAD,
    "PS": remap.BOTAO_PS,
}

_SELECT_DO_TECLADO = re.compile(
    r'<select[^>]*data-campo="teclado-estado"[^>]*>(.*?)</select>', re.S)
_OPCAO = re.compile(r"<option[^>]*>(.*?)</option>", re.S)

_OFERTAS: tuple[tuple[int, int], frozenset[str]] | None = None


def _o_que_a_pagina_oferece() -> frozenset[str]:
    """As `<option>` da "Função do teclado" NA PÁGINA QUE O PILOTO CARREGA.

    `publicado=True` é deliberado (a mesma exceção de `a03_gatilhos._pagina_publicada`): o padrão de
    `onde.pagina` é a BANCADA, mas quem pinta pinta no que está no `WebView`, e o piloto abre SEMPRE
    o publicado. Lê uma vez por versão do arquivo, selo `(mtime_ns, tamanho)`: a página tem 385 KB e
    a pintura roda a cada 100 ms (reler a cada tique seria 3,8 MB/s). `frozenset()` quando o arquivo
    não abre: aí `_o_teclado_em_palavras` cai na palavra de produto, o destino correto para produto
    instalado sem a página.

    Janela que isto não fecha, estreita: publicar com o aplicativo ABERTO e sem trocar de aba (o
    arquivo muda, o pacote emite a palavra nova e o DOM carregado ainda é o antigo, então a escrita
    é descartada até o próximo carregamento; trocar de aba ou reabrir recarrega, em
    `hefesto_vivo.Piloto._ir`).
    """
    global _OFERTAS
    from hefesto_dualsense4unix.interface import onde

    try:
        arquivo = onde.pagina(PAGINA, publicado=True)
        st = arquivo.stat()
        selo = (st.st_mtime_ns, st.st_size)
    except OSError:
        return frozenset()
    if _OFERTAS is not None and _OFERTAS[0] == selo:
        return _OFERTAS[1]
    try:
        doc = arquivo.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    bloco = _SELECT_DO_TECLADO.search(doc)
    ofertas = frozenset(_OPCAO.findall(bloco.group(1))) if bloco else frozenset()
    _OFERTAS = (selo, ofertas)
    return ofertas


def _o_teclado_em_palavras(ligado: bool, so_dentro: bool = False) -> str:
    """A palavra daquele estado que a página CARREGADA sabe receber.

    «Só dentro do jogo» é o teclado LIGADO com o campo do perfil que troca o
    sinal do portão (`teclado_so_no_jogo`): sem ele, ligado é «Só fora».
    """
    candidatas = (TECLADO_SO_DENTRO,) if ligado and so_dentro else PALAVRAS_DO_TECLADO[ligado]
    ofertas = _o_que_a_pagina_oferece()
    for palavra in candidatas:
        if palavra in ofertas:
            return palavra
    return candidatas[0]


#: (`data-hef-quando="Ligado"` no rótulo — ver `aba06.STATUS_MODO`). Por isso
LIGADO = "Ligado"
DESLIGADO = "Desligado"

NADA_A_DIZER = '<i class="nada"></i>'

PRONTO_PARA_MOUSE = "Pronto para usar como mouse"


def _o_mouse_virtual_em_uma_linha(rato: dict[str, Any]) -> str:
    """A linha "o mouse virtual está pronto?", com a MESMA hierarquia da GTK: *device no ar segundo
    o daemon → pronto; senão, o motivo*.

    O dono é `app/actions/mouse_actions._refresh_mouse_view`; copia-se a ORDEM, não a frase (a do
    bloqueio vem da tabela importada `BLOQUEIO_DO_MOUSE_EM_PORTUGUES`). **A sonda local não vem
    junto**: a GTK faz `import uinput` + `os.access("/dev/uinput")` na janela, que *"erra nos dois
    sentidos"* (num Flatpak a janela olha o sandbox e grita "sem permissão" sobre um nó que o daemon
    abre); quem abre o device é o daemon e a resposta vem de quem executa, o que torna esta linha
    mais confiável que a da GTK.

    Vazia quando o daemon não respondeu ou diz `desligada`, escolha do usuário e não defeito (o
    `_anotar_mouse_virtual` a classifica como "não sei" para não mandá-lo consertar um interruptor
    que ele baixou).
    """
    from hefesto_dualsense4unix.app.actions.mouse_actions import (
        BLOQUEIO_DO_MOUSE_EM_PORTUGUES,
    )
    from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

    if not rato:
        return NADA_A_DIZER
    if rato.get("device_ativo") is True:
        return f'<span class="verde">{PRONTO_PARA_MOUSE}</span>'
    bloqueio = rato.get("bloqueio")
    if not isinstance(bloqueio, str) or not bloqueio or bloqueio == "desligada":
        return NADA_A_DIZER
    motivo = BLOQUEIO_DO_MOUSE_EM_PORTUGUES.get(bloqueio)
    if motivo is None:
        # Feio e honesto; a GTK faz o mesmo em `frase_da_recusa_do_mouse`.
        motivo = f"o Hefesto está bloqueando o mouse (motivo: {bloqueio})"
    motivo = motivo.replace("{gesto}", como_atualizar_esta_instalacao())
    return f'<span class="laranja">O cursor não anda: {motivo}.</span>'


def _o_teclado_em_uma_linha(tecla: dict[str, Any]) -> str:
    """"Ligado, em pausa agora: …" — o ESTADO do teclado, e ele é do produto.

    Chama `app/actions/emulation_actions.descrever_teclado_emulado` (pura, devolve `(posição,
    frase)`); a posição já está na lista "Função do teclado" e faltava a FRASE: a diferença entre
    *desligado por você* e *ligado e calado agora porque um jogo assumiu*. Sem o bloco, a frase é a
    de "não sei" da própria GTK (`TECLADO_SEM_ESTADO` fala do Hefesto, não do teclado).
    """
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        descrever_teclado_emulado,
    )

    _posicao, frase = descrever_teclado_emulado(tecla or None)
    return f'<span class="laranja">{frase}</span>' if frase else NADA_A_DIZER


def _o_teclado_na_tela_em_uma_linha(tecla: dict[str, Any]) -> str:
    """"Neste computador: o teclado na tela está instalado — o L3 abre."

    Chama `app/actions/input_actions.frase_do_teclado_na_tela`, TRI-ESTADO: `None` devolve `""`, sem
    afirmar sobre máquina que ninguém olhou. Ela decide se existe ALGUM caminho para escrever texto
    com o controle (nenhum atalho de fábrica digita letra); a dica desta aba mandava abrir o teclado
    na tela com o L3 sem dizer se há um instalado.
    """
    from hefesto_dualsense4unix.app.actions.input_actions import (
        frase_do_teclado_na_tela,
    )

    bruto = (tecla or {}).get("osk_disponivel")
    return frase_do_teclado_na_tela(
        bruto if isinstance(bruto, bool) else None) or NADA_A_DIZER


O_QUE_SAI_COM_O_TECLADO = ("o teclado na tela (L3/R3) e as três regiões do "
                           "touchpad")


def _o_custo_de_desligar_o_teclado(tecla: dict[str, Any]) -> str:
    """"Com o teclado desativado saem também …", e só enquanto ele estiver.

    TRI-ESTADO como as outras três linhas: sem o bloco `keyboard_emulation` não afirma nada; ligado,
    não há o que dizer (o custo é o de DESLIGAR). Não substitui o `teclado-bloqueio`; as duas
    convivem: aquela diz *ligado e calado agora porque um jogo assumiu* (o presente), esta *você o
    desligou, e isto saiu junto* (a escolha).
    """
    ligado = (tecla or {}).get("enabled")
    if not isinstance(ligado, bool) or ligado:
        return NADA_A_DIZER
    return ('<span class="laranja">Com a “Função do teclado” em “'
            f'{TECLADO_DESATIVADO}” saem também {O_QUE_SAI_COM_O_TECLADO}.'
            "</span>")


#: `key_bindings`, `button_actions`, `teclado_emulado` e
ENDERECO_DA_RESSALVA = "ativacao-ressalva"

RESSALVA_DOS_GLOBAIS = (
    "O cursor, a rolagem e o teclado são um só para o computador inteiro: "
    "mudar aqui vale para <b>todos os controles ligados</b>, e não só para o "
    "que está escolhido em cima.")


def _a_ressalva_dos_globais(ctx: Contexto) -> str:
    """A linha da D3, só quando há mais de um controle a ressalvar (D-02): *"Linha fixa só quando HÁ
    ressalva."*

    Com UM controle o ajuste global É o ajuste dele e a frase diria verdade sem consequência; com
    DOIS, a fileira de cartões passa a oferecer uma escolha que as sete linhas não honram. O número
    sai de `conectados`, NUNCA da mesa do desenho (quatro lugares sempre, dois vazios no mockup):
    *"Toda frase que promete alcance conta os CONECTADOS"*, regra do `Contexto`, pois nomear
    controle ausente apareceu quatro vezes em 31/08.
    """
    return RESSALVA_DOS_GLOBAIS if len(ctx.conectados) > 1 else NADA_A_DIZER


#:
RAZAO_DO_PORTAO = (
    "O mouse e o teclado só se ligam fora do jogo — ligar agora derrubaria o "
    "controle no meio da partida. O Modo se troca na aba Jogar.")


def _a_razao_do_portao(estado: dict[str, Any]) -> str:
    """Por que o «Status da navegação» vai recusar agora, ou nada a dizer. O portão só vale no tipo
    «O computador», o que derruba o pad virtual; a Interna liga em qualquer modo
    (A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01).
    """
    if not estado or tipo_de_navegacao(estado) == TIPO_INTERNA:
        return NADA_A_DIZER
    if mode_of_state(estado) == MODE_DESKTOP:
        return NADA_A_DIZER
    return f'<span class="laranja">{RAZAO_DO_PORTAO}</span>'


def _nome_do_botao(botao: str) -> str:
    """`"l2"` → `"L2 (gatilho esquerdo)"`. O nome que o usuário lê, e é do MOTOR.

    A tabela não se escreve aqui: `app/actions/input_actions.humanize_button` é dona dos vinte nomes
    (KBD-01), e a GTK mostra os mesmos; as frases de recusa do "Guardar" mandavam o id cru (*"…sem
    quem as atenda: touchpad_left_press"*).

    **Os dois eixos continuam crus** (02/09/2026): `_nome_do_botao('r3_direcao')` e `('l3_direcao')`
    devolvem o id, pois são 22 botões em `acoes.BOTOES` e 20 nomes em `_BUTTON_LABELS` (falta a
    DIREÇÃO dos analógicos). A cura mora no MOTOR, não aqui: copiar duas linhas criaria a segunda
    tabela que `test_o_nome_do_botao_e_o_do_motor_e_nao_uma_segunda_tabela` impede (o mesmo botão
    com dois nomes). O dano de hoje é de forma: `acoes.resolver()` pula os eixos, então nunca chegam
    ao `sem_dono`; só o `nao_reconhecidas` do "Guardar" os exporia.

    O import é tardio porque `input_actions` puxa GTK no topo (e `mouse_actions` junto), e os
    pacotes são puros, importáveis sem janela; custa uma vez, no caminho da recusa. Sem GTK no
    ambiente o id cru volta (feio e honesto, como `acoes.rotulo()` para token sem nome).
    """
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_button
    except Exception:
        return botao
    return humanize_button(botao)


# Os `--plastico` das duas bordas, os chips da fita e as telas de botões, todos por
# `a04_iluminacao.um_botao_de_player`, que o gerador `aba06.py` chama.

SEM_LEITURA = ""


def _monta() -> Any:
    """O `monta`, importado tarde. O `pacotes/__init__` põe `interface/` no path."""
    import monta

    return monta


def cor_do_plastico(slug: str) -> str:
    """O hex da casca daquele modelo, LIDO do mapa — ou `""` sem leitura."""
    if not slug:
        return SEM_LEITURA
    try:
        # Os modelos sem hexa amostrado devolvem `url(#hachura-sem-hex)`, que
        return str(_monta().cor_de_css(slug))
    except Exception:
        return SEM_LEITURA
    except SystemExit:
        return SEM_LEITURA


_ZONAS_DE_IDENTIDADE: frozenset[str] | None = None
_FOLHA: dict[str, dict[str, str]] | None = None


def _ler_a_folha() -> dict[str, dict[str, str]]:
    """As zonas de cada modelo, lidas do `ds_limpo.svg` que o gerador pinta."""
    global _FOLHA, _ZONAS_DE_IDENTIDADE
    if _FOLHA is not None:
        return _FOLHA
    folha: dict[str, dict[str, str]] = {}
    for slug, corpo in re.findall(
            r'svg\[data-colorway="([^"]+)"\]\{([^}]*)\}', _monta().DS):
        zonas = {}
        for par in corpo.split(";"):
            chave, _, valor = par.partition(":")
            if chave.strip().startswith("--z-"):
                zonas[chave.strip()] = valor.strip()
        folha[slug] = zonas
    vistos: dict[str, set[str]] = {}
    for zonas in folha.values():
        for chave, valor in zonas.items():
            vistos.setdefault(chave, set()).add(valor)
    _ZONAS_DE_IDENTIDADE = frozenset(k for k, v in vistos.items() if len(v) > 1)
    _FOLHA = folha
    return folha


def colorway_do_aparelho(slug: str) -> str:
    """O `data-colorway` daquele lugar da mesa — o id do modelo, ou `""`."""
    if not slug:
        return SEM_LEITURA
    return slug if slug in _ler_a_folha() else SEM_LEITURA


def folha_do_plastico(mesa: list[dict[str, Any]], caixa: str = ".nav-ctl") -> str:
    """A folha de estilo VIVA que pinta o casco de cada lugar da mesa.

    Ela é o cinto e o alvo `atributo` é o suspensório (03/09/2026): com o alvo, o `data-colorway` de
    cada `<svg>` é um campo (`colorway_do_aparelho`) e a página publica os 28 modelos; a folha fica
    por pintar o casco numa árvore em que o alvo ainda não chegou, e sai quando ele estiver no `dev`
    e provado na tela.

    Por que folha e não campo: as peças do SVG leem `var(--z-casca)`, escrita por regra
    `svg[data-colorway="…"]`, e o piloto (texto, valor, classe, cor, largura, fundo, `innerHTML`,
    atributo) **não alcança variável CSS de elemento**. Reescrever o SVG por `innerHTML` custaria
    370 linhas por cartão a cada meio segundo e nunca sossegaria, pois o navegador NORMALIZA
    marcação e o `escrever()` acusaria mudança em todo tique; o `innerHTML` de um `<style>` é texto
    e volta como foi escrito. Vence a folha de dentro do SVG por especificidade:
    `.nav-ctl[data-controle="p1"] .ds-svg` (0,3,0) contra `svg[data-colorway="cosmic-red"]` (0,1,1).

    Sem leitura, o casco fica NEUTRO (regra de produto): controle no rádio não entrega a cor, e o
    casco do mockup afirmaria aparelho que não está na mesa. As zonas que não são identidade ficam:
    pintá-las apagaria o desenho em vez de calar a cor.

    :param caixa: o seletor da CAIXA de um lugar da mesa, que muda de aba (`.nav-ctl` aqui, `.ctrl`
    na Iluminação). Parâmetro desde 03/09/2026, quando a aba 04 precisou da mesma folha (o desenho
    GRANDE dela mostrava o Cosmic Red e o Starlight Blue do mockup sob um rótulo `P1 • White • USB`,
    `rgb(174,51,90)` no corpo contra `rgb(228,224,216)` na moldura da MESMA célula); duas cópias
    divergiriam no primeiro modelo novo. O seletor precisa vencer o `svg[data-colorway="…"]` de
    dentro do SVG (0,1,1); `.nav-ctl[…] .ds-svg` e `.ctrl[…] .ds-svg` valem (0,3,0).
    """
    folha = _ler_a_folha()
    identidade = _ZONAS_DE_IDENTIDADE or frozenset()
    regras = []
    ocupados: set[str] = set()
    for lugar in mesa:
        pref = str(lugar.get("pref") or "")
        if not pref:
            continue
        ocupados.add(pref)
        zonas = folha.get(str(lugar.get("cor") or ""))
        if zonas:
            corpo = ";".join(f"{k}:{v}" for k, v in zonas.items())
        else:
            corpo = ";".join(f"{k}:var(--border-forte)" for k in sorted(identidade))
        if corpo:
            regras.append(f'{caixa}[data-controle="{pref}"] .ds-svg{{{corpo}}}')
    regras.extend(_apagar_os_lugares_sem_dono(caixa, ocupados, identidade))
    return "".join(regras)


LUGARES_DO_DESENHO = 4


def _apagar_os_lugares_sem_dono(
    caixa: str, ocupados: set[str], identidade: frozenset[str],
) -> list[str]:
    """As regras que APAGAM o aparelho do mockup nos lugares que ficaram vazios.

    Medido no produto em 03/09/2026 com UM controle no cabo e a aba aberta no WebKit (DOM vivo): P1
    White casco `rgb(68,71,90)`; **P2 «—» casco `rgb(126,184,212)` (o Starlight Blue do mockup) e
    lightbar `rgb(255,0,0)` (o `style="--luz:#ff0000"` do `monta.svg()`)**; P3 e P4 desconectados em
    `rgb(83,87,111)`. Lugar SEM controle saía mais colorido e aceso que o único de verdade.

    Causa: P3 e P4 nascem `class="nav-ctl vazia"` e a folha do desenho já desenha lugar vazio
    (`.nav-ctl.vazia .ds-svg …{fill:var(--linha)!important}`); o P2 nasce OCUPADO e fica vazio em
    execução, e quem o esvazia (`pacotes.apagar_os_lugares_sem_dono` + passo `vazios` do piloto)
    escreve a classe **`off`**, que folha nenhuma menciona: duas palavras para o mesmo estado nunca
    se encontraram. É a lei da `folha_do_plastico` onde estava calada: lugar sem dono é, com mais
    razão que sem leitura de cor, lugar sobre o qual a tela nada afirma. O neutro é o `var(--linha)`
    do desenho (o do `.vazia`), não cinza digitado aqui. O `!important` é necessário: a `--luz`
    chega como `style="--luz:#ff0000"` no elemento (`monta.py`), e estilo de linha vence qualquer
    regra de folha que não o traga.
    """
    if not identidade:
        return []
    zonas = ";".join(f"{k}:var(--linha)" for k in sorted(identidade))
    regras = []
    for n in range(1, LUGARES_DO_DESENHO + 1):
        pref = f"p{n}"
        if pref in ocupados:
            continue
        regras.append(f'{caixa}[data-controle="{pref}"] .ds-svg{{{zonas}}}')
        regras.append(f'{caixa}[data-controle="{pref}"] [id$="-lightbar"]'
                      f'{{--luz:var(--linha) !important}}')
    return regras


def rotulo_de_quem_navega(numero: int | None, nome: str, via: str) -> str:
    """`"P1 White USB"` — quem navega o PC, como as duas dicas o dizem.

    Só a FORMA: o número é de `pacotes.jogador_de` e o nome de `pacotes.identidade_de` (os donos da
    ROTA-A). O gerador chama com a mesa do desenho e o pacote com a mesa viva, uma escrita só para
    as duas. Pedaço que não se sabe NÃO ENTRA (sem primário a dica termina em "o **.**", feio e
    verdadeiro); inventar número repetiria o defeito que a ROTA-A mediu (o mesmo controle mudando de
    nome quando o segundo entra).
    """
    if nome == NOME_SEM_LEITURA:
        nome = SEM_LEITURA
    partes = [f"P{numero}" if numero else "", nome, via]
    return " ".join(p for p in partes if p)


def chips_da_fita(mesa: list[dict[str, Any]]) -> str:
    """Os chips da fita do topo, para a `06`, com os controles da MESA.

    Por que esta aba tem os seus, e não os de `monta.fita()`: o piloto troca a fita INTEIRA
    (`hefesto_vivo._fita`), mas ela **desiste** quando um controle da mesa não tem cor (`if not mesa
    or any(not c.get("cor") …): return ""`), e pelo rádio a cor não se lê. Medido em 03/09/2026 com
    os dois controles do usuário e o daemon no ar: a fita da `06` mostrava `P1 · Cosmic Red · USB` e
    `P2 · Starlight Blue · BT` (os do mockup) ao lado de um cabeçalho certo. Este endereço salva a
    fita quando o dono dela desiste; quando `_fita` responde, ele troca o bloco antes (primeiro
    passo do `pintar`) e os dois dizem a mesma coisa.

    Acesos e borda (O-SELECIONAR-ACENDE-QUEM-ESTA-ESCOLHIDO-01, 09/10/2026): a aba não escolhe
    controle e o que mostra vale para todos, então `monta.acesos_da_fita(…, escolhe=False)` acende o
    `Todos` e todos da mesa. O chip leva `--plastico` quando a cor foi lida, pela regra do
    `monta.fita()` (sem cor lida, nem a classe nem o `style`). Cada chip tem endereço próprio,
    `data-campo="fita-chip"`, como no `monta.fita()`, na 03 e na 09: o do bloco não basta para a
    régua da identidade, que lê o `--plastico` no `style` do próprio elemento.
    """
    monta = _monta()
    mostra_todos, _ = monta.escolha_da_fita("todos", mesa)
    acesos = monta.acesos_da_fita("todos", mesa, escolhe=False)
    chips = [f"<span>{monta.ROTULO_DA_FITA}</span>"]
    if mostra_todos:
        chips.append(f'<label class="chip{" on" if "todos" in acesos else ""}">Todos</label>')
    for lugar in mesa:
        nome = str(lugar.get("nome") or "")
        if nome == NOME_SEM_LEITURA:
            nome = SEM_LEITURA
        partes = [f'P{lugar["jogador"]}' if lugar.get("jogador") else "",
                  nome, str(lugar.get("via") or "")]
        rotulo = monta.SEPARADOR.join(p for p in partes if p)
        aceso = " on" if str(lugar.get("pref") or "") in acesos else ""
        slug = str(lugar.get("cor") or "")
        if slug and monta.o_desenho_conhece(slug):
            chips.append(f'<label class="chip plastico{aceso}" data-campo="{CAMPO_DO_CHIP}"'
                         f' style="--plastico:{monta.cor_da_zona(slug)}"'
                         ' title="A borda é a cor do plástico">'
                         f"{rotulo}</label>")
        else:
            chips.append(f'<label class="chip{aceso}" data-campo="{CAMPO_DO_CHIP}">'
                         f"{rotulo}</label>")
    return "".join(chips)


def _linha_do_cartao(c: dict[str, Any], primario: bool, cursor: bool = False,
                     estado: dict[str, Any] | None = None) -> str:
    """A linha inteira do cartão: `"BT • Navega o PC"`."""
    return linha_do_cartao(str(c.get("via") or ""), primario, cursor, estado=estado)


#: A linha da mira sem nada a dizer — o lugar vazio, o chip apagado e o Nativo escrevem isto.
MIRA_VAZIA = {"mira-resumo": "", "mira-resumo-dica": ""}


def a_mira_do_cartao(dele: dict[str, Any], ctx: Contexto) -> dict[str, str]:
    """Os dois campos da linha da mira do cartão: o resumo curto e a dica com o inteiro.

    A-MIRA-DA-CALIBRAR-E-A-MESMA-DAS-OUTRAS-ABAS-01 (29/09/2026, ela: *«isso aqui tem que tá
    sincronizado com a aba Conexões, Navegação. e Perfis»*). Na Navegação o giro vira cursor pelos
    quatro ajustes da Calibrar; o cartão os diz quando a Mira dele está acesa, pelo MESMO leitor da
    Calibrar (`a11.resumo_da_mira`, sobre o bloco `mira`) e pelo mesmo `ligada` do chip
    (`a02._mira_ligada`). Apagada, sem leitura ou no modo nativo, a linha fica vazia (afirmação sem
    leitura é chute). O resumo vai pelo alvo `html` (escapado aqui) porque o `texto` vazio vira
    travessão no piloto, o sinal de leitura que falta.
    """
    from .a02_controles import _mira_ligada, _nativo
    from .a11_calibrar_sensores import resumo_da_mira

    bloco = dele.get("mira")
    if _mira_ligada(dele) is not True or _nativo(ctx):
        return dict(MIRA_VAZIA)
    return {"mira-resumo": html.escape(resumo_da_mira(bloco, curto=True) or ""),
            "mira-resumo-dica": resumo_da_mira(bloco) or ""}


def move_o_cursor(dele: dict[str, Any], ctx: Contexto, primario: bool) -> bool:
    """Este controle, que NÃO navega o PC, move o cursor agora pelo giro?

    A-MIRA-NA-NAVEGACAO-02, 25/09/2026, decisão de produto. É o que o daemon faz
    (`mouse.mover_o_cursor_pelo_giro` leva ao cursor o giro de TODA peça com a Mira acesa), e o
    cartão dizia «Só a janela» sobre controle que movia o cursor da máquina. Cinco perguntas, cada
    uma do dono da resposta:

    1. **não é quem navega** — o primário já diz «Navega o PC»;
    2. **a Mira dele está acesa** — bloco `mira`, pelo leitor do chip da aba Controles
    (`a02_controles._mira_ligada`); sem leitura é não; 3. **o modo vivo é a Navegação** — leitor da
    dica do Giroscópio (`a02_controles._na_navegacao`, o `mode_of_state`); no Virtual e no Xbox a
    Mira vai ao analógico direito do controle virtual, e no Nativo não anda; 4. **o giroscópio dele
    chega** — o interruptor do chip (`sensores.giroscopio_ligado`, `a02_controles._sensor_ligado`) e
    o leitor de movimento aberto (`inputs.gyro`, `controller_card.gyro_do_inputs`); o motor pergunta
    as duas coisas (`gamepad.aplicar_o_movimento`), e sem uma o cursor não anda; sem leitura é não;
    5. **o mouse move o cursor AGORA** — `mouse_emulation.despachando`, dono único no daemon
    (`ipc_handlers._bloqueio_da_emulacao_de_desktop`): «Status do Modo» ligado, mouse virtual de pé,
    nem modo jogo nem jogo calando o desktop; é a conjunção com que o `lifecycle._poll_loop` decide
    rodar o tique da Navegação. O `enabled` sozinho é fraco: com o PS segurado (modo jogo) segue
    `true`, a linha do mouse diz «em pausa» e o cartão afirmaria o cursor (a conferência
    fotografou).

    Os leitores são da aba Controles de propósito: o chip e a dica do Giroscópio de lá falam do
    MESMO fato, e duas leituras divergiriam na primeira correção.
    """
    if primario:
        return False
    from hefesto_dualsense4unix.interface.cartao_do_controle import gyro_do_inputs

    from .a02_controles import _mira_ligada, _na_navegacao, _sensor_ligado

    if _mira_ligada(dele) is not True or not _na_navegacao(ctx):
        return False
    if (_sensor_ligado(dele, "giroscopio") is not True
            or gyro_do_inputs(dele.get("inputs")) is None):
        return False
    rato = (getattr(ctx, "state", None) or {}).get("mouse_emulation") or {}
    return rato.get("despachando") is True


def o_mouse_navega(estado: dict[str, Any] | None) -> bool:
    """O primário navega o PC: o mouse não está desligado (sem bloco, o de nascença).

    Um dono, dois leitores: o cartão (a bolinha e «Navega o PC») e a janela da Navegação Interna,
    que não dá seleção a quem navega o PC com o mouse ligado
    (`D-2909-O-CURSOR-DE-QUEM-NAVEGA-O-PC-E-O-DO-PC`).
    """
    rato = (estado or {}).get("mouse_emulation")
    return not (isinstance(rato, dict) and rato.get("enabled") is False)


def linha_do_cartao(via: str, primario: bool, cursor: bool = False, *,
                    estado: dict[str, Any] | None = None) -> str:
    """A linha de estado do cartão, em HTML — UM DONO, DOIS CHAMADORES: o gerador (`aba06.controle`)
    desenha a bancada com ela e o pacote pinta o produto a cada tique (o arranjo do `desenho_da_luz`
    da 04).

    Virou HTML em 21/09/2026 por causa da BOLINHA: o alvo `texto` não devolve o `<span
    class="bolinha">`, o molde poupava a linha para não apagá-la (`enderecos_que_o_texto_apaga`), e
    um lugar ESVAZIADO dizia `● USB • Navega o PC` em verde com a mesa vazia. Com `html` o lugar
    vazio recebe o travessão (`LUGAR_VAZIO`) e a bolinha VOLTA com o controle.

    Terceiro papel (A-MIRA-NA-NAVEGACAO-02, 25/09/2026): `cursor` diz que o controle, sem navegar o
    PC, move o cursor pelo giro (`move_o_cursor`); não acende a bolinha, o verde é de quem navega e
    esse é um só.

    Papel da hora (A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01): `estado` é o
    `state_full`; o primário só diz «Navega o PC» (e só ele tem a bolinha) com o mouse ligado, «Só a
    janela» só sai com a Navegação Interna ligada, e no resto o cartão diz só o transporte. Sem
    `estado` (o desenho da bancada) vale o de nascença: mouse ligado, Interna desligada.
    """
    st = estado or {}
    navega = primario and o_mouse_navega(st)
    papel = (PAPEL_QUE_NAVEGA if navega
             else PAPEL_DO_CURSOR if cursor and not primario
             else PAPEL_SO_A_JANELA if interna_ligada(st) else "")
    corpo = PONTO.join(p for p in (via, papel) if p)
    return (BOLINHA if navega else "") + corpo


def _linhas_dos_botoes(p: dict[str, Any]) -> dict[str, str]:
    """As 21 linhas de *o que cada botão faz*, com o RÓTULO que o desenho mostra.

    O vocabulário é o do motor: `acoes.BOTOES` diz quais linhas existem, `acoes.padrao()` o de
    fábrica, `acoes.rotulo()` o texto da `<option>`; o gerador monta as mesmas listas do mesmo lugar
    (`aba06.ACOES_UNI = por_grupo()`), então o valor emitido SEMPRE existe como opção (condição do
    `escrever()` com `data-hef-alvo="valor"`, que se cala quando não casa). O perfil vence o de
    fábrica linha a linha: `button_actions` guarda DIFERENÇA (`None` = herda), e linha ausente é o
    de fábrica.

    **São três camadas, não duas** (06/09/2026): o de fábrica, os atalhos da janela antiga
    (`key_bindings`) e a escolha desta tela, nessa ordem, por `acoes.tabela_efetiva` (o
    `resolver()`, a MESMA chamada que alimenta o device). A função montava fábrica +
    `button_actions` e nunca olhava `key_bindings`, a cegueira que o `resolver()` tinha antes da
    ONDA3-MOTOR-01: perfil com `Super` no Options pela janela antiga fazia a tabela mostrar o de
    fábrica sobre botão que digitava outra coisa.

    O que a lista não tem como dizer não é dito AQUI: combinação livre não é `<option>`,
    `acoes.rotulo()` devolve o token cru e o `escrever()` a recusa em silêncio. Quem nomeia essas
    linhas é a TIRA (`linhas_que_a_lista_nao_sabe_dizer`).
    """
    perfil_ = p or {}
    tabela = acoes.tabela_efetiva(
        perfil_.get("button_actions") or None,
        perfil_.get("key_bindings") or None)
    return {
        f"{PREFIXO_DA_ACAO}{botao}": acoes.rotulo(str(tabela.get(botao) or ""))
        for botao in acoes.BOTOES
    }


# `input_actions.frase_dos_atalhos_fora_da_lista` termina com.
# "Guardar" faz `apply_button_actions` reescrever o conjunto todo a partir do de
# fábrica (`profiles/manager.py:581`, `core/acoes_de_botao.resolver`, que nunca
# cada linha faz sai de `core/acoes_de_botao`.
# ---------------------------------------------------------------------------


def _colado(ligacao: Any) -> str:
    """A ligação do perfil na forma com `+`, que é a que o produto lê de volta."""
    if isinstance(ligacao, (list, tuple)):
        return "+".join(str(t) for t in ligacao)
    return str(ligacao)


def _atalho_em_palavras(colado: str) -> str:
    """`"KEY_LEFTCTRL+KEY_W"` → `"Ctrl + W"`, pelo dono do produto. Import tardio pela razão de
    `_nome_do_botao`; sem GTK volta o token cru."""
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_binding
    except Exception:
        return colado
    return str(humanize_binding(colado))


def _dois_donos() -> list[tuple[str, str, str]]:
    """Os botões que o mouse E o teclado atendem ao mesmo tempo, DE FÁBRICA: `(botão, o que a tabela
    mostra, o que o teclado faz no mesmo botão)`.

    Medido, não digitado: `acoes.padrao()` mostra o do MOUSE quando os dois opinam (é o que se vê
    acontecer com o cursor) e `DEFAULT_BUTTON_BINDINGS` diz o do teclado. Onde discordam o produto
    faz OS DOIS e a tabela conta metade. Hoje é um botão só, o R3 («Botão do meio» no mouse, «Fechar
    o teclado na tela» no teclado; colisão escrita em `core/keyboard_mappings.py`); derivar em vez
    de digitar acompanha o dia em que entrar um segundo.
    """
    from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS

    de_fabrica = acoes.padrao()
    fora: list[tuple[str, str, str]] = []
    for botao in acoes.BOTOES:
        ligacao = DEFAULT_BUTTON_BINDINGS.get(botao)
        if not ligacao:
            continue
        colado = "+".join(ligacao)
        na_tabela = str(de_fabrica.get(botao) or "")
        if na_tabela and na_tabela != colado:
            fora.append((botao, acoes.rotulo(na_tabela), acoes.rotulo(colado)))
    return fora


def _mapas_que_sobrevivem_ao_nada() -> frozenset[str]:
    """Os botões cujo som de fábrica o `— Nada —` da tela não desliga."""
    from hefesto_dualsense4unix.integrations.uinput_mouse import (
        DPAD_TO_KEY,
        EDGE_KEY_MAP,
    )

    return frozenset(DPAD_TO_KEY) | frozenset(EDGE_KEY_MAP)


def _o_que_a_tabela_diz_de_cada_botao(p: dict[str, Any]) -> dict[str, str]:
    """Botão -> token que VALE agora: o de fábrica com o perfil por cima."""
    escolhas = (p.get("button_actions") or None) if p else None
    tabela = acoes.padrao()
    if escolhas:
        tabela.update({b: a for b, a in escolhas.items() if b in tabela})
    return tabela


def _linhas_que_nao_acendem(p: dict[str, Any]) -> tuple[list[str], list[str]]:
    """`(as que calaram de verdade, as que o "— Nada —" NÃO calou)`."""
    tabela = _o_que_a_tabela_diz_de_cada_botao(p)
    escolhas = (p.get("button_actions") or None) if p else None
    mudos = {b for b in acoes.BOTOES if tabela.get(b) == acoes.TOKEN_NADA}
    teimosos = mudos & _mapas_que_sobrevivem_ao_nada()
    _do_mouse, _do_teclado, sem_dono = acoes.resolver(escolhas)
    return sorted((mudos - teimosos) | set(sem_dono)), sorted(teimosos)


def atalhos_que_param_de_valer(p: dict[str, Any]) -> list[tuple[str, str]]:
    """Os `key_bindings` do perfil que o "Guardar" desta tela faz parar de valer.

    **Metade visível do defeito §3-1, que é do produto**: `apply_button_actions`
    (`profiles/manager.py`) roda DEPOIS do `apply_keyboard` e chama `teclado.set_bindings(...)` com
    o conjunto INTEIRO que `acoes_de_botao.resolver()` deriva; sem o campo passado, `resolver()`
    parte de `acoes.padrao()` e ignora `profile.key_bindings`, então perfil com `button_actions`
    apaga em silêncio, na próxima ativação, o que o usuário escreveu à mão na janela antiga.
    Compara-se contra o que o daemon VAI aplicar (`resolver(button_actions)`, a mesma chamada);
    atalho que COINCIDA sobrevive e não entra (nomear o que não se perde é ruído). Sem device de
    mouse vivo o `apply_button_actions` sai antes e nada é reescrito, por isso a tira diz *"quando o
    mouse virtual estiver de pé"*.

    **Não morreu sozinha** (06/09/2026): a nota antiga dizia que morreria quando `resolver()`
    herdasse `key_bindings`; ele herdou (ONDA3-MOTOR-01), mas o CHAMADOR seguia chamando
    `resolver(button_actions)` com um argumento (a assinatura preservada de propósito). Com o campo
    passado, a lista nomeia só o que ainda se perde: o escrito na janela antiga FORA do
    `DOMINIO_DO_TECLADO` (`cross`, `triangle`, `r3`).

    :returns: `[(botão, o binding colado), …]`, em ordem de botão.
    """
    atalhos = (p.get("key_bindings") or {}) if p else {}
    if not atalhos:
        return []
    _do_mouse, do_teclado, _sem = acoes.resolver(
        (p or {}).get("button_actions"), atalhos)
    fora: list[tuple[str, str]] = []
    for botao, ligacao in sorted(atalhos.items()):
        agora = (tuple(ligacao) if isinstance(ligacao, (list, tuple))
                 else (str(ligacao),))
        if do_teclado.get(botao) == agora:
            continue
        fora.append((botao, _colado(agora)))
    return fora


# `Super`, e `dehumanize_binding` traduz —, e a tela nova só oferecia uma LISTA
#   `input_actions.dehumanize_binding` o que o usuário digita -> token cru
# mudança não pegou". Ver `_tabela_efetiva` em `core/acoes_de_botao.py`.


def _traduzir(texto: str) -> str:
    """`"Ctrl + W"` → `"KEY_LEFTCTRL+KEY_W"`, pelo dono da janela antiga. Sem GTK o texto volta como
    veio, e a etapa seguinte recusa dizendo; tradução aqui seria a segunda tabela que este bloco
    existe para não ter.
    """
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import (
            dehumanize_binding,
        )
    except Exception:
        return texto.strip()
    return str(dehumanize_binding(texto.strip()))


def _desfazer_o_humanize(cru: str) -> str:
    """O `humanize_binding` ao contrário — uma DELEGAÇÃO, não uma tabela.

    **Era contorno e virou cura no dono (06/09/2026).** `humanize` faz `tok[4:]` para todo `KEY_*`
    fora de `_KEY_LABELS`, então a coluna mostrava `F5` e `dehumanize_binding("F5")` devolvia `F5`,
    que o `parse_binding` recusa (F1..F12, Home, End, Insert, PageUp, PageDown, Comma, Dot e as três
    de volume). O contorno daqui era um SEGUNDO DONO do fato e a janela antiga seguia com o buraco;
    a cura foi para `input_actions.dehumanize_binding`, onde decide o vocabulário do `evdev`, e
    fecha os dois lados. Esta função fica como PORTA (o nome é citado em prosa desta aba). A recusa
    de CAPACIDADE nunca foi daqui: `tokens_da_tecla` a pede a `uinput_keyboard.SUPPORTED_KEYS`.
    """
    from hefesto_dualsense4unix.app.actions.input_actions import (
        dehumanize_binding,
    )

    return dehumanize_binding(cru)


def _teclas_que_o_device_sabe() -> frozenset[str]:
    """O que o teclado virtual SABE EMITIR — perguntado ao dono."""
    from hefesto_dualsense4unix.integrations.uinput_keyboard import SUPPORTED_KEYS

    return frozenset(SUPPORTED_KEYS)


def tokens_da_tecla(texto: str) -> tuple[str, ...]:
    """O que o usuário digitou, virado tokens do produto — ou `ValueError` DIZENDO.

    Vazio devolve `()` = **este botão não digita nada** (o `— Nada —` da lista ao lado, dito pelo
    campo em branco); tratá-lo como erro recusaria o gesto mais natural, apagar o que está escrito.
    As três recusas são dos donos, nenhuma frase de tecla é redigida aqui:

    1. a FORMA, de `keyboard_mappings.parse_binding` (`ValueError` com o token que não entendeu);
    2. a CAPACIDADE, de `uinput_keyboard.SUPPORTED_KEYS` (a tecla existe no vocabulário e o device
    virtual não a declara); 3. a MISTURA, de `uinput_keyboard._delegate_virtual_tokens`
    (`__OPEN_OSK__` junto com `KEY_*` é rejeitado LÁ com `warning`, sem emitir nada); recusar aqui é
    dizer na tela o que o daemon diria no journal.
    """
    cru = _desfazer_o_humanize(_traduzir(texto))
    if not cru:
        return ()
    from hefesto_dualsense4unix.core.keyboard_mappings import (
        is_virtual_token,
        parse_binding,
    )

    tokens = parse_binding(cru)
    virtuais = [t for t in tokens if is_virtual_token(t)]
    if virtuais and len(virtuais) != len(tokens):
        raise ValueError(
            f"{texto.strip()!r} mistura um comando (“{virtuais[0]}”) com teclas "
            "comuns, e o teclado do Hefesto recusa a mistura sem digitar nada. "
            "Escolha um ou outro.")
    if not virtuais:
        sabe = _teclas_que_o_device_sabe()
        faltam = [t for t in tokens if t not in sabe]
        if faltam:
            raise ValueError(
                "o teclado do Hefesto não sabe digitar "
                + ", ".join(f"“{_atalho_em_palavras(t)}”" for t in faltam)
                + f" (de {texto.strip()!r}). Ele só emite as teclas que declara "
                  "ao sistema quando nasce, e essa não está entre elas.")
    return tokens


def _o_que_cada_botao_digita(p: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Botão -> as teclas que ele digita AGORA, perguntado ao motor.

    É a segunda sacola do `resolver()` com as TRÊS camadas na ordem do produto (de fábrica,
    `key_bindings`, `button_actions`), a mesma chamada de `profiles/manager.apply_button_actions`:
    impede a tela de mostrar uma coisa e o aparelho digitar outra.
    """
    perfil_ = p or {}
    _do_mouse, do_teclado, _sem = acoes.resolver(
        perfil_.get("button_actions") or None,
        perfil_.get("key_bindings") or None)
    return do_teclado


def teclas_dos_botoes(p: dict[str, Any]) -> dict[str, str]:
    """Os oito campos da tela "Teclas do teclado", com o texto que ela lê. Vazio quando o botão não
    digita nada (regra de produto da casa: *campo sem informação não mostra nada*), o que dá ao
    campo em branco o mesmo sentido na leitura e na escrita.
    """
    digita = _o_que_cada_botao_digita(p)
    return {
        f"{PREFIXO_DA_TECLA}{botao}": _atalho_em_palavras(
            "+".join(digita.get(botao) or ()))
        for botao in sorted(acoes.DOMINIO_DO_TECLADO)
    }


def linhas_que_a_lista_nao_sabe_dizer(p: dict[str, Any]) -> list[tuple[str, str]]:
    """As linhas cuja tecla o `<select>` das 22 NÃO tem como mostrar."""
    digita = _o_que_cada_botao_digita(p)
    fora: list[tuple[str, str]] = []
    for botao in acoes.BOTOES:
        colado = "+".join(digita.get(botao) or ())
        if not colado or colado in acoes.ACOES:
            continue
        fora.append((botao, _atalho_em_palavras(colado)))
    return fora


def _o_ps_digita(token: str | None) -> bool | None:
    """O token escolhido é coisa que o PS sabe entregar? — PERGUNTADO AO DONO."""
    try:
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
            _o_ps_digita as do_dono,
        )
    except Exception:
        return None
    return bool(do_dono(token))


def _o_que_o_ps_faz(p: dict[str, Any]) -> str:
    """A quinta frase da tira: as DUAS coisas que o botão PS faz ao mesmo tempo.

    Decisão de 06/09/2026 (06-Q3): o PS ganha a mesma lista das outras 21 linhas; com uma tecla,
    passa a digitar SEM parar de abrir a Steam, e a tabela precisava avisar. Nasce só quando há o
    que dizer (sem escolha no perfil o PS é o que sempre foi). A linha do PS só digita desde
    01/10/2026 (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01): `— Nada —` e «Abrir a Steam» saíram
    dela, e perfil que ainda os guarde não ganha frase (a migração os leva ao ⑥ dos gestos).

    **A tira não nomeia o ato da máquina**: o estado do daemon NÃO traz `ps_button_action` (só a
    resposta de `daemon.reload` o devolve), e "continua abrindo a Steam" afirmaria o degrau de
    fábrica sobre máquina que ninguém perguntou (ajustável: `steam` · `none` · `custom`). A frase
    afirma o que vale nos três casos: o PS **continua sendo a saída de emergência**, pois os gestos
    e o segurar-para-alternar não passam por aquele campo. Publicar `ps_button_action` no estado é o
    que deixaria nomear as duas metades, e é de quem for dono do IPC.

    O segundo ramo é o silêncio que a 06-01 deixou declarado: o `resolver()` tira o PS das três
    sacolas, então escolha que ninguém atende (um `BTN_*`, papel de eixo, "Abrir um programa") não
    entra em `sem_dono` nem na frase "Não acendem nada hoje"; o daemon a registra no journal como
    `ps_solo_escolha_sem_atendente`, e sem esta linha a tela seria o único lugar calado.

    :returns: a frase, ou `""` quando não há o que dizer.
    """
    escolha = acoes.acao_do_ps((p or {}).get("button_actions"))
    if not escolha or escolha == acoes.TOKEN_NADA:
        return ""
    digita = _o_ps_digita(escolha)
    if digita is None:
        return ""
    nome = _nome_do_botao(acoes.BOTAO_PS)
    rotulo = acoes.rotulo(escolha)
    if digita:
        return (f"<b>{nome}: duas coisas ao mesmo tempo.</b> Ele digita "
                f"“{rotulo}” <b>e</b> continua sendo a saída de emergência — os "
                "gestos desta aba saem dele, e segurá-lo alterna o modo jogo. "
                "Dentro de um jogo ele não faz nenhuma das duas.")
    if escolha == acoes.TOKEN_STEAM:
        return ""
    return (f"O <b>{nome}</b> digita teclas e abre o teclado na tela. "
            f"A escolha “{rotulo}” fica guardada no perfil.")


def _aviso_da_tabela(p: dict[str, Any]) -> str:
    """A tira sob a tabela de botões — vazia quando não há o que perder."""
    partes: list[str] = []
    donos = _dois_donos()
    if donos:
        quais = "; ".join(
            f"{_nome_do_botao(b)} faz “{do_mouse}” para o mouse e “{do_teclado}” "
            f"para o teclado"
            for b, do_mouse, do_teclado in donos)
        partes.append(
            f"<b>Dois donos:</b> {quais}. A tabela mostra só o do mouse, e "
            "guardar aqui deixa valendo só o que ela mostra.")
    mudos, teimosos = _linhas_que_nao_acendem(p)
    if mudos:
        partes.append(
            "<b>Guardadas no perfil, e sem efeito hoje:</b> "
            + ", ".join(_nome_do_botao(b) for b in mudos)
            + ".")
    if teimosos:
        partes.append(
            "O <b>“— Nada —”</b> não cala estes: "
            + ", ".join(_nome_do_botao(b) for b in teimosos)
            + ". Eles continuam digitando o de fábrica.")
    perdidos = atalhos_que_param_de_valer(p)
    if perdidos:
        quais = ", ".join(f"{_nome_do_botao(b)} = {_atalho_em_palavras(t)}"
                          for b, t in perdidos)
        partes.append(
            f"<b>O perfil guarda atalhos que esta lista não diz:</b> {quais}. "
            "Guardar aqui substitui o conjunto inteiro de atalhos pelo que a "
            "tabela mostra, e esses param de valer assim que o mouse virtual "
            "estiver de pé.")
    # texto, e sem ela a tela de texto CRIARIA um defeito: uma combinação livre
    mudas = linhas_que_a_lista_nao_sabe_dizer(p)
    if mudas:
        partes.append(
            "<b>A lista não sabe mostrar a tecla destas linhas:</b> "
            + ", ".join(f"{_nome_do_botao(b)} digita {t}" for b, t in mudas)
            + ". Elas valem assim mesmo; o que a lista mostra nelas não é o que "
              "o botão faz. Use <b>Teclas do teclado</b> para ver e trocar.")
    do_ps = _o_que_o_ps_faz(p)
    if do_ps:
        partes.append(do_ps)
    if not partes:
        return NADA_A_DIZER
    return "".join(f"<div>{x}</div>" for x in partes)


#: escolha de quem clica em ≤1,5 s (quinze tiques de `hefesto_vivo.TIQUE_MS`),
_MEXENDO: dict[str, str] = {}

_ULTIMA_PINTURA = 0.0

#: (`hefesto_vivo.TIQUE_MS`), e enquanto ela estiver nesta página o `pacote()`
#: NÃO SE IMPORTA `TIQUE_MS` DAQUI: `hefesto_vivo` puxa GTK no topo, e os
PAUSA_DE_OUTRA_ABA = 5.0


def _largar_o_que_ela_mexeu() -> None:
    """Solta a trava. Chamado pelo "Guardar", pelo "Voltar ao padrão" e pelo sair."""
    _MEXENDO.clear()


def _o_que_a_tabela_mostra(p: dict[str, Any]) -> dict[str, str]:
    """As 21 linhas: o perfil, com as que ela está mexendo por cima."""
    global _ULTIMA_PINTURA

    agora = time.monotonic()
    if _MEXENDO and _ULTIMA_PINTURA and agora - _ULTIMA_PINTURA > PAUSA_DE_OUTRA_ABA:
        _largar_o_que_ela_mexeu()
    _ULTIMA_PINTURA = agora
    linhas = _linhas_dos_botoes(p)
    linhas.update(teclas_dos_botoes(p))
    for campo in list(_MEXENDO):
        if campo not in linhas or linhas[campo] == _MEXENDO[campo]:
            del _MEXENDO[campo]
    linhas.update(_MEXENDO)
    return linhas


_TROCANDO: dict[str, str] = {}

_ULTIMA_TROCA = 0.0


def _rotulo_do_destino(botao: str) -> str:
    """O id de destino → o texto da `<option>`. Sem rótulo, o id cru."""
    for rotulo, alvo in ROTULOS_DA_TROCA.items():
        if alvo == botao:
            return rotulo
    return botao


def _linhas_da_troca(p: dict[str, Any] | None) -> dict[str, str]:
    """As linhas que a troca alcança, com o destino que o PERFIL guarda."""
    mapa = (p or {}).get("remapeamento") or {}
    return {
        f"{PREFIXO_DA_TROCA}{botao}": (
            _rotulo_do_destino(str(mapa[botao])) if mapa.get(botao) else SEM_TROCA)
        for botao in remap.REMAPEAVEIS
    }


def _o_que_a_troca_mostra(p: dict[str, Any] | None) -> dict[str, str]:
    """As linhas da troca: o perfil, com as que ela está mexendo por cima. Mesmo desenho de
    `_o_que_a_tabela_mostra` (a pintura CONCORDA com a escolha, a linha que o perfil passou a dizer
    sai da trava sozinha, e cinco segundos sem tique = saiu da aba).
    """
    global _ULTIMA_TROCA

    agora = time.monotonic()
    if _TROCANDO and _ULTIMA_TROCA and agora - _ULTIMA_TROCA > PAUSA_DE_OUTRA_ABA:
        _TROCANDO.clear()
    _ULTIMA_TROCA = agora
    linhas = _linhas_da_troca(p)
    for campo in list(_TROCANDO):
        if campo not in linhas or linhas[campo] == _TROCANDO[campo]:
            del _TROCANDO[campo]
    linhas.update(_TROCANDO)
    return linhas


@registrar("06-navegacao.html")
def pacote(ctx: Contexto) -> dict[str, Any]:
    st = ctx.state
    rato = st.get("mouse_emulation") or {}
    tecla = st.get("keyboard_emulation") or {}
    p = perfil.ativo_que_vale(st.get("active_profile"))
    atalhos = (p.get("key_bindings") or {}) if p else {}

    cards = {}
    for c in ctx.conectados:
        uniq = str(c.get("uniq") or "")
        # `mesa_viva.mesa_do_estado`. Sem casa na mesa (um controle que entrou
        na_mesa = next((m for m in ctx.mesa if str(m.get("uniq") or "") == uniq), {})
        primario = bool(c.get("is_primary"))
        cards[uniq] = {
            "navega": _linha_do_cartao(na_mesa, primario,
                                       move_o_cursor(c, ctx, primario), estado=st),
            "identidade": identidade_de(c, ctx.mesa),
            **a_mira_do_cartao(c, ctx),
        }
        # O número do cartão é o VIVO (`casa["jogador"]`, o das lâmpadas da 02 e do chip da fita),
        # não o assento que o gerador cravou; sem número vivo ele não sai.
        numero = na_mesa.get("jogador")
        if isinstance(numero, int) and not isinstance(numero, bool) and numero > 0:
            cards[uniq]["jogador"] = str(numero)
    plastico = [cor_do_plastico(str(m.get("cor") or "")) for m in ctx.mesa]
    # pede, teria QUEBRADO o desenho — e foi por isso que a página passou a
    desenho = [colorway_do_aparelho(str(m.get("cor") or "")) for m in ctx.mesa]
    # Quem navega o PC é o primário, marcado pelo daemon (`is_primary`).
    chefe = next((c for c in ctx.conectados if c.get("is_primary")), None)
    do_chefe = next((m for m in ctx.mesa
                     if str(m.get("uniq") or "") == str((chefe or {}).get("uniq") or "")),
                    {}) if chefe else {}
    mesa = {
        "fita-chips": chips_da_fita(ctx.mesa),
        "plastico": plastico + [""] * max(0, 4 - len(plastico)),
        "desenho": desenho + [""] * max(0, 4 - len(desenho)),
        "quem-navega": rotulo_de_quem_navega(
            jogador_de(chefe) if chefe else None,
            identidade_de(chefe, ctx.mesa) if chefe else "",
            str(do_chefe.get("via") or "")),
        "vel-cursor": rato.get("speed"),
        "vel-rolagem": rato.get("scroll_speed"),
        "rato-despachando": bool(rato.get("despachando")),
        "gestos": len(atalhos),
        "gestos-lista": {k: v for k, v in list(atalhos.items())[:12]},
    }
    # O interruptor mostra o estado do TIPO escolhido na lista (D-2909-O-INTERRUPTOR-
    # LIGA-O-TIPO-ESCOLHIDO): a Interna pelo bloco `navegacao`, o computador pelo mouse.
    if tipo_de_navegacao(st) == TIPO_INTERNA:
        mesa["rato-ligado"] = LIGADO if interna_ligada(st) else DESLIGADO
    elif isinstance(rato.get("enabled"), bool):
        mesa["rato-ligado"] = LIGADO if rato["enabled"] else DESLIGADO
    if _navegacao(st):
        mesa["navegacao-tipo"] = ROTULOS_DO_TIPO[tipo_de_navegacao(st)]
    bp = big_picture_ligado(st)
    if bp is not None:
        mesa["modo-big-picture"] = BIG_PICTURE_LIGADO if bp else BIG_PICTURE_DESLIGADO
    mesa["rato-estado"] = _o_mouse_virtual_em_uma_linha(rato)
    mesa["teclado-bloqueio"] = _o_teclado_em_uma_linha(tecla)
    mesa["teclado-osk"] = _o_teclado_na_tela_em_uma_linha(tecla)
    mesa["modo-portao"] = _a_razao_do_portao(st)
    mesa["teclado-custo"] = _o_custo_de_desligar_o_teclado(tecla)
    mesa["aviso-da-tabela"] = _aviso_da_tabela(p)
    mesa[ENDERECO_DA_RESSALVA] = _a_ressalva_dos_globais(ctx)
    mesa.update(_o_que_a_tabela_mostra(p))
    mesa.update({**_o_que_a_troca_mostra(p), **_o_que_os_gestos_fazem()})
    # `keyboard_emulation` (daemon mudo, ou config inacessível — o `state_full`
    # chega ao cartão dela na hora (`hefesto_vivo._recusou_dizendo`, pelo
    if "keyboard_emulation" in st:
        mesa["teclado-estado"] = _o_teclado_em_palavras(
            bool(tecla.get("enabled")), so_dentro=bool((p or {}).get("teclado_so_no_jogo")))
    mesa[ENDERECO_DA_CHAVE] = CHAVE_LIGADA if (p or {}).get("tabela_no_jogo") else CHAVE_DESLIGADA
    mesa[ENDERECO_DA_CHAVE_FORA] = CHAVE_NO_NATIVO if _no_nativo(ctx) else ""
    return {
        "colunas": cards,
        "mesa": mesa,
        LUGAR_VAZIO: {"identidade": SEM_NINGUEM_AQUI, "navega": TRAVESSAO, **MIRA_VAZIA},
        MARCAS_DO_LUGAR: {
            "navega": [str(chefe.get("uniq") or "")] if chefe else [],
            "vazia": sorted(TODOS_OS_LUGARES - {str(m.get("pref") or "") for m in ctx.mesa}),
        },
        "blocos": {"#plastico-vivo": folha_do_plastico(ctx.mesa)},
        "sem_dono": {},
        "cobertura": {"pintados": (sum(len(v) for v in cards.values())
                                   + len(set(mesa) - set(SEM_ENDERECO))),
                      "sem_dono": len(SEM_DONO)},
    }


# métodos do daemon aceita um: `mouse.emulation.set`, `mouse.emulation.restore`,
# `keyboard.emulation.set` e `desktop.status.set` valem para a MÁQUINA.
# TIQUE (100 ms, `hefesto_vivo.TIQUE_MS`). Ler o daemon a cada clique custaria um
# `daemon.state_full` por clique (57 ms medidos, e HARM-15 já registra que ele
from hefesto_dualsense4unix.app.actions.mode_transition import (  # noqa: E402
    MODE_DESKTOP,
    mode_of_state,
)
from hefesto_dualsense4unix.integrations.uinput_mouse import (  # noqa: E402
    MOUSE_SPEED_MAX,
    MOUSE_SPEED_MIN,
    SCROLL_SPEED_MAX,
    SCROLL_SPEED_MIN,
)

from . import gesto  # noqa: E402

MANUAL = "manual"


def _rato(ctx: Contexto) -> dict[str, Any]:
    """O bloco `mouse_emulation` do último tique — o que está VALENDO agora."""
    return ctx.state.get("mouse_emulation") or {}


def _no_nativo(ctx: Contexto) -> bool:
    """O modo nativo está ligado? É GLOBAL no daemon (`state_full.native_mode`).

    A mesma pergunta de `a02_controles._nativo`, escrita aqui porque um pacote
    de aba não importa o privado de outro; sem estado, a resposta é «não».
    """
    return (getattr(ctx, "state", None) or {}).get("native_mode") is True


# DISCO, E SÓ — NUNCA `perfil.gravar_e_reaplicar`. O preço está medido em 03/09
# ainda não salvou. O aparelho já recebeu a mudança pelo `mouse.emulation.set`

_DO_RATO: dict[str, str] = {
    "mouse_speed": "speed",
    "mouse_scroll": "scroll_speed",
}


def _secao_do_mouse(prof: Any, ctx: Contexto, campos: dict[str, Any]) -> Any:
    """A seção `mouse` do perfil com o que este clique mudou, ou `None`.

    `None` = **não há o que gravar**: o perfil já diz isto (gravar de novo escreveria o mesmo
    arquivo a cada passagem do arraste) ou o daemon ainda não falou. A seção nasce com o que está
    VALENDO: `enabled` é obrigatório no `ProfileMouseConfig`, e a única coisa verdadeira é o estado
    vivo (inventar `False` faria o perfil DESLIGAR, na próxima ativação, emulação que estava
    ligada). Sem o bloco do daemon a seção não nasce: valor chutado valeria para todo jogo que casar
    com o perfil, para sempre.
    """
    from hefesto_dualsense4unix.profiles.schema import ProfileMouseConfig

    atual = getattr(prof, "mouse", None)
    if atual is not None:
        base = {"enabled": atual.enabled, "speed": atual.speed,
                "scroll_speed": atual.scroll_speed}
    else:
        vivo = _rato(ctx)
        if vivo.get("speed") is None:
            return None
        base = {"enabled": bool(vivo.get("enabled")),
                "speed": int(vivo["speed"]),
                "scroll_speed": int(vivo.get("scroll_speed") or SCROLL_SPEED_MIN)}
    novo = {**base, **campos}
    if atual is not None and novo == base:
        return None
    return ProfileMouseConfig(**novo)


def _o_que_nao_guardou(nome: str) -> str:
    """A frase de quando o aparelho mudou e o perfil não guardou. Um dono."""
    if not nome:
        return ("mudei agora, mas não guardei: não há perfil ativo. "
                "Escolha um na aba Perfis.")
    return (f"mudei agora, mas não guardei: não consegui abrir o "
            f"perfil “{nome}” para gravar.")


def _guardar_no_perfil(ctx: Contexto, **campos: Any) -> str:
    """Grava o que ESTE clique mudou onde a marca do cartão diz. Disco, e nada mais.

    Aceita `teclado_emulado=` e `teclado_so_no_jogo=` (lista «Função do teclado»), `tabela_no_jogo=`
    («Também no jogo») e os dois do rato (`mouse_speed`, `mouse_scroll`, ver `_DO_RATO`).

    :return: `""` quando gravou ou não havia o que gravar (o disco já dizia isso); senão a frase do
    que NÃO deu (sem perfil ativo, ou arquivo que não abre).

    Frase e não `RuntimeError`: o aparelho JÁ mudou (a chamada ao daemon vem antes e deu certo);
    levantar pintaria a RECUSA laranja sobre gesto que fez metade do que prometeu. Quem chama
    devolve a frase pelo canal de AVISO (`{"recado": …}`), no mesmo cartão com tom de sucesso.

    **O arraste chega duas vezes e grava uma**: o ouvinte do piloto escuta `change` **e** `click`, e
    soltar o polegar de um `<input type=range>` dispara os dois com o MESMO valor; a segunda
    passagem acha o disco igual, `_secao_do_mouse` devolve `None` e nada é escrito. O guarda é a
    IGUALDADE, não um relógio (mais forte que o `_so_abriu_o_seletor` da aba 04: cobre também
    arrastar e voltar ao valor de origem).
    """
    nome = perfil.nome_do_ativo(ctx.state).strip()
    loader = perfil._com_o_src()
    if nome:
        try:
            loader.load_profile(nome)
        except Exception:
            return _o_que_nao_guardou(nome)

    def _com_o_que_mudou(prof: Any) -> Any:
        mudanca: dict[str, Any] = {}
        for campo in ("teclado_emulado", "teclado_so_no_jogo", "tabela_no_jogo"):
            if campo in campos:
                quer = bool(campos[campo])
                if getattr(prof, campo, None) is not quer:
                    mudanca[campo] = quer
        do_rato = {_DO_RATO[k]: v for k, v in campos.items() if k in _DO_RATO}
        if do_rato:
            secao = _secao_do_mouse(prof, ctx, do_rato)
            if secao is not None:
                mudanca["mouse"] = secao
        return prof.model_copy(update=mudanca) if mudanca else None

    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    cartao = "teclado" if "teclado_emulado" in campos else "mouse"
    try:
        gravar_pelo_gesto(cartao, nome, _com_o_que_mudou, origem="interface-nova")
    except (OSError, ValueError):
        return _o_que_nao_guardou(nome)
    return ""


def _numero_da_barra(o: dict[str, Any], oque: str) -> int:
    """O inteiro que a barra mandou, ou uma frase que chega ao cartão dela.

    O `data-hef-alvo="valor"` do `<input type=range>` faz o ouvinte mandar `valor: alvo.value`; um
    `<div>` não teria `value` e o gesto chegaria com a chave vazia (defeito que a aba Vibração
    nomeou em 03/09/2026 antes de o trilho virar `<input>`). `RuntimeError` e não `ValueError`
    porque o contrato do piloto leva a frase do primeiro ao cartão e deixa o segundo no `stderr`
    (`hefesto_vivo._recusou_dizendo`).
    """
    bruto = str(o.get("valor") or "").strip()
    if not bruto:
        raise RuntimeError(
            f"{oque} ficou como estava. "
            "Arraste o cursor da barra em vez de clicar no rótulo ao lado.")
    try:
        return round(float(bruto))
    except ValueError as erro:
        raise RuntimeError(
            f"a barra mandou {bruto!r}, que não é um número — {oque} ficou "
            "como estava") from erro


def _recusa_do_mouse(resposta: Any) -> str:
    """A frase da recusa, TRADUZIDA, ou `""` quando o daemon aceitou.

    Traduz `app/actions/mouse_actions.frase_da_recusa_do_mouse` (cinco motivos, fallback honesto
    para motivo novo e recusa sem motivo). **A ponte entrega o corpo desde 01/09/2026**:
    `ponte.resultado` (`interface/pacotes/ponte.py`) devolve o `result` do daemon e levanta quando
    ninguém responde; um `{"status": "failed", "bloqueio": "sem_device"}` voltava como sucesso e a
    tela ficava sem uma palavra. `status` AUSENTE conta como aceito (`set_mouse_speed` responde
    `{"status": "ok", "enabled": …}` e só), senão toda troca de velocidade acusaria um "não" que não
    houve.
    """
    from hefesto_dualsense4unix.app.actions.mouse_actions import (
        frase_da_recusa_do_mouse,
    )

    if not isinstance(resposta, dict) or resposta.get("status") != "failed":
        return ""
    return frase_da_recusa_do_mouse(resposta)


def _recusa_do_teclado(resposta: Any) -> str:
    """O motivo de o teclado não ter ligado, do bloco que o próprio daemon devolve.

    `keyboard.emulation.set` responde com o bloco `keyboard_emulation` inteiro, *"para a janela não
    precisar de uma segunda chamada só para saber se o device subiu"* (`daemon/ipc_handlers.py`);
    quem o traduz é `emulation_actions.descrever_teclado_emulado`, o dono da linha de estado desta
    aba. Sem bloco e sem frase, diz-se só que ele recusou. A frase de "não sei" da GTK
    (`TECLADO_SEM_ESTADO`, *"o Hefesto pode estar desligado"*) NÃO serve: o Hefesto respondeu, ele é
    que disse não.
    """
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        descrever_teclado_emulado,
    )

    bloco = resposta.get("keyboard_emulation") if isinstance(resposta, dict) else None
    if isinstance(bloco, dict) and isinstance(bloco.get("enabled"), bool):
        _posicao, frase = descrever_teclado_emulado(bloco)
        if frase:
            return frase
    return "o Hefesto recusou e não disse por quê"


_PEDIDO: dict[str, tuple[int, int, int, float]] = {}

#: (`hefesto_vivo.TIQUE_MS`). Um segundo é folga de sobra para um daemon lento
#: NÃO SE IMPORTA `TIQUE_MS` DAQUI, pela mesma razão de `PAUSA_DE_OUTRA_ABA`:
MEMORIA_DE_UM_CLIQUE = 2.0


def _partir_de(chave: str, atual: int, sentido: int) -> int:
    """De onde o clique parte: o daemon, ou o último valor que ele CONFIRMOU.

    Três condições, e as três desligam a memória sozinhas:

    1. **o daemon ainda diz o mesmo número** (se já publica outro, por aplicar, aparar ou mexida
    pela GTK, a partida volta a ser ele); 2. **o clique vai para o mesmo lado**: dois `+` seguidos
    somam; `+` seguido de `-` parte do DAEMON (repetir é *ande mais*, inverter em meio segundo é
    ambíguo, e a leitura conservadora é a que o `PROVAS` desta aba cobra). O interruptor manda
    `sentido=0` e cai sempre aqui: o segundo clique é *desfaça*, nunca *ande mais*; 3. **o relógio
    ainda está na janela do tique** (`MEMORIA_DE_UM_CLIQUE`).

    Fica só com o que o Hefesto não recusou (`_reservar`): alvo guardado de clique RECUSADO
    (`sem_device`) fazia o seguinte partir de número que nunca existiu (pedia 8 com o daemon em 6,
    pulando o 7), medido em 03/09/2026.
    """
    pendente = _PEDIDO.get(chave)
    if pendente is None:
        return atual
    visto, confirmado, sentido_antes, quando = pendente
    if visto != atual or sentido_antes != sentido:
        return atual
    if time.monotonic() - quando > MEMORIA_DE_UM_CLIQUE:
        del _PEDIDO[chave]
        return atual
    return confirmado


def _reservar(chave: str, atual: int, valor: int,
              sentido: int) -> tuple[int, int, int, float] | None:
    """Anota o alvo ANTES de mandar, e devolve o que estava lá para o desfazer.

    A reserva vem antes da chamada, medido: os gestos rodam em THREAD (`hefesto_vivo.trabalhar`,
    *"um gesto síncrono congelaria a janela inteira por nove segundos e meio"*), então dois cliques
    rápidos são duas threads. Anotar só DEPOIS da resposta deixaria a segunda ler a memória vazia e
    repetir o pedido da primeira, dentro do tempo de ida e volta do IPC, que é a janela em que se
    clica duas vezes. Desfeita na falha por `_largar_a_reserva` (reservar não é confirmar).
    """
    antes = _PEDIDO.get(chave)
    _PEDIDO[chave] = (atual, valor, sentido, time.monotonic())
    return antes


def _largar_a_reserva(chave: str,
                      antes: tuple[int, int, int, float] | None) -> None:
    """O Hefesto recusou ou ficou mudo: a reserva volta ao que era."""
    if antes is None:
        _PEDIDO.pop(chave, None)
    else:
        _PEDIDO[chave] = antes


def _velocidade(p: Any, o: dict[str, Any], campo: str,
                minimo: int, maximo: int, oque: str) -> int:
    """O corpo comum das duas barras de velocidade. `mouse.emulation.set`.

    Sem `enabled` de propósito: o handler manda o pedido sem `enabled` para `set_mouse_speed`
    (`daemon/ipc_handlers.py`), que atualiza a config e o device vivo **sem start/stop e sem gravar
    o flag**, o que impede ajuste de velocidade de RELIGAR a emulação e matar o gamepad virtual
    (BUG-MOUSE-GUI-SYNC-01, A4; a GUI estável manda o mesmo payload em `_send_mouse_param_async`).

    Não lê o `ctx`: os `-`/`+` liam o estado do último tique porque um passo precisa saber de ONDE
    parte (`_partir_de`, a memória `_PEDIDO` e as três condições); a barra manda o número inteiro. A
    memória segue de pé com um cliente, o interruptor "Status do Modo", que tem UM gesto e depende
    dela para o segundo clique ser *desfaça*.

    A faixa não é digitada aqui: quem chama passa `MOUSE_SPEED_MIN`/`MOUSE_SPEED_MAX`
    (`integrations/uinput_mouse.py`), de onde `set_speed` tira a sua. A barra já nasce com esses
    `min`/`max` (`aba06.trilho`), então aparar aqui é a rede para página publicada sem regerar o
    desenho; o daemon apara por último.

    O arraste chega duas vezes e é inócuo (como em `a05_vibracao.intensidade`): `change` **e**
    `click` disparam com o MESMO valor, e `set_mouse_speed` é idempotente. Filtrar por evento aqui
    seria regra sobre o ouvinte, que mora em outro arquivo.

    :return: o número que FOI ao daemon, já aparado. Quem chama o leva ao perfil (D2) e tem de ser
    este, nunca o do `ctx` (estado do tique ANTERIOR: gravaria a velocidade velha enquanto a nova
    roda no aparelho).
    """
    alvo = max(minimo, min(maximo, _numero_da_barra(o, oque)))
    _mandar(p, origin=MANUAL, **{campo: alvo})
    return alvo


def _mandar(p: Any, **params: Any) -> None:
    """`mouse.emulation.set`, e diz POR QUE quando o daemon recusa. `p.chamar` devolve `bool` e joga
    fora o corpo (era ele que trazia a recusa como sucesso); `p.resultado` traz o corpo e levanta
    quando ninguém responde, os dois desfechos a separar: *o Hefesto não falou* e *o Hefesto disse
    não, por isto*.
    """
    try:
        resposta = p.resultado("mouse.emulation.set", **params)
    except RuntimeError as erro:
        raise RuntimeError(
            "o Hefesto não respondeu — a velocidade não mudou") from erro
    recusa = _recusa_do_mouse(resposta)
    if recusa:
        raise RuntimeError(recusa)


@gesto("06-navegacao.html", "modo", grava="desktop.status.set")
def modo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Status do Modo": o interruptor que liga mouse E teclado.

    Os dois porque o usuário pediu em 27/08 este interruptor no lugar de dois botões (*"Suspender
    Mouse e Teclado, Sair do Modo Jogo, deixam de existir devido ao botão status na parte
    superior"*), e a dica diz *"nada desta aba chega ao PC"*. O daemon tem dois interruptores (o do
    teclado nasceu porque desligar o mouse deixava o teclado emitindo Alt+Tab dentro da partida);
    `desktop.status.set` aciona os dois numa chamada. O MOUSE vai primeiro: ligá-lo PARA o vpad
    (`set_mouse_emulation`, exclusão mútua), e se falhar o teclado não fica ligado sozinho num modo
    que não é dele. A ordem mora no daemon desde 29/09/2026
    (`Daemon.definir_o_status_da_navegacao`).

    O lado para onde ir sai do DAEMON, nunca da caixinha: o piloto não sabe escrever `checked` e o
    desenho nasce `checked` com o daemon `enabled=false`, então ler a tela inverteria o gesto no
    primeiro clique.

    O portão do modo é copiado do produto: `_sync_mouse_mode_gate` (`app/actions/mouse_actions.py`)
    faz `blocked = mode != MODE_DESKTOP` nos DOIS sentidos, inclusive com modo desconhecido, porque
    *"Ligar o switch durante 'Jogar pelo Hefesto' derrubava o vpad e os jogadores do co-op SEM AVISO
    (a exclusão mútua do daemon é silenciosa)"*. A frase é outra: a do produto (`MODE_GATE_HINT`)
    manda à **aba Início**, que não existe nas dez abas (o modo mudou para a **Jogar**); reusar o
    módulo não dá, `mouse_actions.py` importa GTK no topo.

    Os dois lados vão ao perfil juntos (05/09/2026, D2): o interruptor mexe em `mouse.enabled` **e**
    `teclado_emulado`, e gravar só o primeiro deixaria *mouse desligado, teclado ligado*, estado que
    ele não produz e a próxima ativação imporia.

    Quem grava é o daemon, depois do aparelho — O-MOUSE-SEGUE-A-NAVEGACAO-01 (29/09/2026): manda
    `desktop.status.set` uma vez, e o ato, a ordem e a gravação dos dois lados moram em
    `Daemon.definir_o_status_da_navegacao`. Se o teclado recusar, o daemon não grava e o gesto
    levanta dizendo por quê.
    """
    if not ctx.state:
        raise RuntimeError(
            "não consegui falar com o Hefesto agora, então não sei se ligar o "
            "mouse derrubaria um jogo em andamento. Tente de novo em instantes.")
    if tipo_de_navegacao(ctx.state) == TIPO_INTERNA:
        return _ligar_a_interna(ctx, p)
    modo_agora = mode_of_state(ctx.state)
    if modo_agora != MODE_DESKTOP:
        # passaram a ser o mesmo texto: duas grafias do mesmo fato divergiriam
        raise RuntimeError(RAZAO_DO_PORTAO)

    ligado = bool(_rato(ctx).get("enabled"))
    novo = not bool(_partir_de("modo", int(ligado), 0))
    reserva = _reservar("modo", int(ligado), int(novo), 0)
    try:
        try:
            resposta = p.resultado("desktop.status.set", enabled=novo,
                                   origin=MANUAL)
        except RuntimeError as erro:
            raise RuntimeError(
                "o Hefesto não respondeu — o mouse ficou como estava") from erro
        # recusa, na forma que o `mouse.emulation.set` devolvia. Sem o bloco, a
        corpo = resposta if isinstance(resposta, dict) else {}
        recusa = _recusa_do_mouse(corpo.get("mouse_emulation", corpo))
        if recusa:
            raise RuntimeError(recusa)
    except Exception:
        _largar_a_reserva("modo", reserva)
        raise
    if (corpo.get("keyboard_emulation") or {}).get("status") == "failed":
        raise RuntimeError(f"o mouse mudou e o teclado não: {_recusa_do_teclado(corpo)}")
    if corpo.get("gravado") is False:
        return {"recado": _o_que_nao_guardou(str(corpo.get("perfil") or ""))}
    return None


def _ligar_a_interna(ctx: Contexto, p: Any) -> dict[str, Any] | None:
    """O «Status da navegação» no tipo Interna: liga ou desliga, em qualquer modo
    (A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01). Sem portão: a Interna não mexe
    no pad virtual nem no mouse (D-20), e o foco da janela decide o R1. O lado sai do bloco
    `navegacao` do daemon.
    """
    ligada = interna_ligada(ctx.state)
    nova = not bool(_partir_de("modo", int(ligada), 0))
    reserva = _reservar("modo", int(ligada), int(nova), 0)
    try:
        resposta = p.resultado("navegacao.interna.set", ligada=nova, origin=MANUAL)
    except Exception as erro:
        _largar_a_reserva("modo", reserva)
        raise RuntimeError(
            "o Hefesto não respondeu — a Navegação Interna ficou como estava") from erro
    if isinstance(resposta, dict) and resposta.get("status") != "ok":
        _largar_a_reserva("modo", reserva)
        raise RuntimeError("a Navegação Interna ficou como estava")
    return None


@gesto("06-navegacao.html", "navegacao-tipo", grava="navegacao.interna.set")
def navegacao_tipo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A lista «Tipo de navegação»: só grava o tipo, e o interruptor passa a mostrá-lo
    (A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01). O tipo é da máquina, nunca do
    perfil (`D-2909-A-NAVEGACAO-INTERNA-E-DA-JANELA`); trocar a lista não desliga o outro tipo, e o
    foco decide o R1.
    """
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip()
    tipo = next((t for t, rotulo in ROTULOS_DO_TIPO.items() if rotulo == escolhido), None)
    if tipo is None:
        raise ValueError(
            f"navegacao-tipo: não reconheci a opção escolhida ({escolhido!r}); as duas "
            f"são as de `ROTULOS_DO_TIPO`.")
    try:
        resposta = p.resultado("navegacao.interna.set", tipo=tipo, origin=MANUAL)
    except RuntimeError as erro:
        raise RuntimeError(
            "o Hefesto não respondeu — o tipo de navegação ficou como estava") from erro
    if isinstance(resposta, dict) and resposta.get("status") != "ok":
        raise RuntimeError("o tipo de navegação ficou como estava")
    return None


@gesto("06-navegacao.html", "modo-steam", grava="navegacao.big_picture.set")
def modo_big_picture(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A lista «Modo Big Picture na Steam»: liga ou desliga, e o daemon é o dono
    (A-ABA-NAVEGACAO-FAZ-O-QUE-DIZ-E-O-MODO-STEAM-NAVEGA-O-BIG-PICTURE-01). O nome do gesto segue
    `modo-steam` para a página publicada não mudar; na 01-jogar o mesmo nome é o chip do Steam
    Input, outro gesto. É da máquina, nunca do perfil, como a Navegação Interna.
    """
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip()
    if escolhido not in (BIG_PICTURE_DESLIGADO, BIG_PICTURE_LIGADO):
        raise ValueError(
            f"modo-steam: não reconheci a opção escolhida ({escolhido!r}); as duas "
            f"são «{BIG_PICTURE_DESLIGADO}» e «{BIG_PICTURE_LIGADO}».")
    try:
        resposta = p.resultado(
            "navegacao.big_picture.set",
            ligado=escolhido == BIG_PICTURE_LIGADO, origin=MANUAL)
    except RuntimeError as erro:
        raise RuntimeError(
            "o Hefesto não respondeu — o Modo Big Picture ficou como estava") from erro
    if isinstance(resposta, dict) and resposta.get("status") != "ok":
        raise RuntimeError("o Modo Big Picture ficou como estava")
    return None


#: (teclado ligado, só dentro do jogo) de cada palavra da lista.
_ESCOLHA_DELA: dict[str, tuple[bool, bool]] = {
    "fora": (True, False), "desativado": (False, False), "dentro": (True, True)}

_ESCOLHA: dict[str, tuple[bool, bool]] = _ESCOLHA_DELA


@gesto("06-navegacao.html", "teclado", grava="gravar_pelo_gesto")
def teclado(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A lista "Função do teclado". `keyboard.emulation.set`.

    O valor vem em `valor`: o ouvinte do piloto escuta `change` além de `click` e manda o `value` do
    alvo (antes só chegava `texto`, que num `<select>` é a lista INTEIRA concatenada). O `rotulo` é
    o segundo caminho: as `<option>` não têm `value`, então `select.value` **é** o texto, mas um
    `<option value=…>` futuro mandaria a chave em `valor` e a frase em `rotulo`, que seguiria
    casando com o desenho.

    As três opções têm dono (O-TECLADO-SO-DENTRO-DO-JOGO-TEM-DONO-01, 08/10/2026): «Só fora do jogo»
    → `enabled=True`; «Desativado» → `enabled=False`; «Só dentro do jogo» → `enabled=True` mais o
    campo `teclado_so_no_jogo` do perfil, que troca o sinal do portão no laço do daemon (digita só
    com jogo aberto). Medido em 02/09/2026: com o gamepad virtual despachando o daemon já cala a
    emulação de desktop (`gamepad_dispatched`), logo teclado ligado sem o campo é «só fora do jogo».

    **Sem portão de modo, ao contrário do gesto `modo`**: o de lá existe porque ligar o MOUSE
    derruba o gamepad virtual (`set_mouse_emulation`); o teclado nunca mexe nele
    (`set_keyboard_emulation` só cria ou destrói o teclado virtual), e com o gamepad despachando nem
    é consultado (`if not gamepad_dispatched`, em `lifecycle.py`). Copiar o portão bloquearia,
    dentro do jogo, o único interruptor que cala o Alt+Tab do R1, o defeito que este método nasceu
    para curar (queixa de 29/07).

    Ainda não diz: desligar tira também o teclado na tela do L3/R3 e as três regiões do touchpad (o
    handler manda a interface repassar), e o piloto não tem canal de aviso (um gesto só imprime no
    terminal). Entende SÓ as três palavras de produto (03/09/2026: houve cinco, com os dois rótulos
    que a página publicada ainda oferecia; publicada a 06, a régua da travessia mandou apagar os
    sinônimos). Diz por que não deu (`p.resultado` traz o corpo; `p.chamar` devolvia `True` para
    `{"status": "failed"}` e a lista voltava sozinha sem uma palavra).

    **Passou a lembrar — 05/09/2026**: `keyboard.emulation.set` grava na flag GLOBAL da sessão
    (`utils/session.py`), nunca no perfil, e `DraftConfig.to_profile` emite `teclado_emulado` por
    PASSTHROUGH do disco; medido em `HOME` de mentira, com o perfil `True` e a escolha
    `TECLADO_DESATIVADO`, o Salvar do rodapé devolvia **`True`**, por cima da escolha, sem uma
    palavra (ver `_guardar_no_perfil`).
    """
    escolhido = str(o.get("valor") or o.get("rotulo") or "").strip()
    palavras = {x.strip(".,;:—-").lower() for x in escolhido.split()}
    chaves = palavras & set(_ESCOLHA)
    if len(chaves) != 1:
        raise ValueError(
            f"teclado: não reconheci a opção escolhida ({escolhido!r}). As três "
            f"do desenho estão em `src/hefesto_dualsense4unix/interface/aba06.py:OPCOES_TECLADO`, "
            f"e cada uma tem de trazer exatamente uma destas palavras: "
            f"{', '.join(sorted(_ESCOLHA))}.")
    ligar, so_dentro = _ESCOLHA[chaves.pop()]
    nome = perfil.nome_do_ativo(ctx.state).strip()
    era_so_dentro = bool((perfil.ativo_que_vale(nome) or {}).get("teclado_so_no_jogo"))
    try:
        resposta = p.resultado("keyboard.emulation.set", enabled=ligar)
    except RuntimeError as erro:
        raise RuntimeError(
            "o Hefesto não respondeu — o teclado ficou como estava") from erro
    if isinstance(resposta, dict) and resposta.get("status") == "failed":
        raise RuntimeError(
            f"o teclado ficou como estava: {_recusa_do_teclado(resposta)}")
    recado = _guardar_no_perfil(ctx, teclado_emulado=ligar, teclado_so_no_jogo=so_dentro)
    if not recado and nome and era_so_dentro != so_dentro:
        # O sinal do portão é travado pelo daemon a cada ATIVAÇÃO do perfil.
        perfil.reaplicar(nome, ctx, p)
    return {"recado": recado} if recado else None


@gesto("06-navegacao.html", "tabela-no-jogo", grava="gravar_pelo_gesto")
def tabela_no_jogo(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A chave «Também no jogo». Grava `tabela_no_jogo` no perfil e manda reaplicar
    (O-GATILHO-VIRA-CLIQUE-SEM-LIGAR-O-CURSOR-01, opção b).

    Ligada, a tabela inteira age junto com o jogo (cada controle aperta as próprias linhas; cursor e
    rolagem só andam pelo P1); desligada, as linhas só agem fora do jogo. Não obedece à função do
    teclado (a chave é da tabela inteira, o teclado é uma das metades). No nativo RECUSA DIZENDO: o
    jogo lê o controle direto e o tique congela, a chave aparece apagada e o clique explica. Só o
    perfil: o daemon trava a chave a cada ativação (`apply_profile_suppression`) e o
    `profile.reaplicar` faz o valor novo valer na hora.
    """
    if _no_nativo(ctx):
        raise RuntimeError(CHAVE_CINZA_NO_NATIVO)
    nome = perfil.nome_do_ativo(ctx.state).strip()
    atual = bool((perfil.ativo_que_vale(nome) or {}).get("tabela_no_jogo"))
    recado = _guardar_no_perfil(ctx, tabela_no_jogo=not atual)
    if not recado and nome:
        perfil.reaplicar(nome, ctx, p)
    return {"recado": recado} if recado else None


@gesto("06-navegacao.html", "vel-cursor", grava="gravar_pelo_gesto")
def vel_cursor(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A barra da Velocidade de cursor, arrastada. `mouse_emulation.speed`.

    Decisão de 05/09/2026: *"velocidade do cursor e da rolagem coloca um slicer pra cada"*. Os
    gestos `vel-cursor-menos`/`-mais` somavam ±1 ao número do ÚLTIMO TIQUE e saíram com os botões: a
    barra manda o número INTEIRO, sem de onde partir nem passo engolido a curar. A paridade com a
    janela GTK fechou junto: lá é um `Gtk.Scale` de `mouse_speed_adj` (`gui/main.glade`, 1..12,
    passo 1), a MESMA faixa, pois ambas leem o dono (`integrations/uinput_mouse.py`); ver
    `docs/data/paridade-gtk-html.csv`, linha "Velocidade do cursor".

    O alcance é o de um número só (medido em 01/09): `mouse_speed` move o analógico esquerdo **e** o
    cursor do touchpad (`emit_touchpad_move` escala por `TOUCHPAD_SENSITIVITY * (mouse_speed /
    DEFAULT_MOUSE_SPEED)`). Dura além da janela desde 05/09/2026 (decisão D2): o número ia ao daemon
    e ao `session.json`, e o perfil só o recebia no "Salvar" do rodapé, então fechar depois de
    arrastar perdia a escolha calada (`_guardar_no_perfil`).
    """
    alvo = _velocidade(p, o, "speed", MOUSE_SPEED_MIN, MOUSE_SPEED_MAX,
                       "a velocidade do cursor")
    recado = _guardar_no_perfil(ctx, mouse_speed=alvo)
    return {"recado": recado} if recado else None


@gesto("06-navegacao.html", "vel-rolagem", grava="gravar_pelo_gesto")
def vel_rolagem(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A barra da Velocidade da rolagem, arrastada. `scroll_speed`."""
    alvo = _velocidade(p, o, "scroll_speed", SCROLL_SPEED_MIN, SCROLL_SPEED_MAX,
                       "a velocidade da rolagem")
    recado = _guardar_no_perfil(ctx, mouse_scroll=alvo)
    return {"recado": recado} if recado else None


@gesto("06-navegacao.html", "linha-de-botao")
def linha_de_botao(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Ela trocou UMA das 21 linhas de *o que cada botão faz*. NÃO grava nada.

    Existe para a tela parar de desfazer a escolha do usuário (decisão de 02/09/2026: *"as 21 listas
    param de ser repintadas enquanto ela está mexendo, até guardar ou sair. Não vira gravação
    automática: ela quer escolher várias, conferir e aplicar de uma vez."*). Não chama o daemon nem
    escreve em disco; o "Guardar" grava, e este gesto anota em `_MEXENDO` para a pintura seguinte
    concordar com a tela.

    Sem ele a escolha não chegava aqui: o ouvinte do piloto só olha alvo que case com o `closest` de
    `manda_do_alvo` (`hefesto_vivo.py`), e os 21 `<select>` tinham só `data-campo`, `data-linha` e
    `data-hef-alvo`, então o `change` morria no navegador (a pintura repunha «Botão direito» sobre o
    «F11» escolhido). O `data-gesto` do gerador (`aba06.LINHA_DE_BOTAO`) abre o caminho.

    A recusa é de clique inválido (`ValueError`), não do produto: rótulo desconhecido só chega se o
    desenho andou sem o gerador (lista da tela e do produto saem do mesmo `core/acoes_de_botao`).
    Devolve a própria linha pelo endereço da pintura: na tela é no-op, mas gesto que volta com
    `None` não toca o DOM (`hefesto_vivo._deu_certo`) e sai do relato como "aplicado" sem nada a
    mostrar; assim o desfecho é verificável e a linha volta ao lugar certo se a página foi repintada
    entre o clique e a volta da thread.
    """
    botao = str(o.get("linha") or o.get("campo") or "").removeprefix(PREFIXO_DA_ACAO)
    if botao not in acoes.BOTOES:
        raise ValueError(
            f"linha-de-botao: o clique não disse qual botão (veio {botao!r}). O "
            "`data-linha` de cada `<select>` é o id do botão, e ele vem do "
            "gerador — sem ele não há o que anotar.")
    rotulo = str(o.get("valor") or o.get("rotulo") or "").strip()
    if acoes.token_do_rotulo(rotulo) is None:
        raise ValueError(
            f"{_nome_do_botao(botao)}: a opção {rotulo!r} não é do produto. A "
            "lista da tela e a do produto saem do mesmo lugar "
            "(`core/acoes_de_botao.ACOES`) — se divergiram, foi o desenho que "
            "andou sem o gerador.")
    campo = f"{PREFIXO_DA_ACAO}{botao}"
    do_perfil = _linhas_dos_botoes(
        perfil.ativo_que_vale((ctx.state or {}).get("active_profile")))
    if do_perfil.get(campo) == rotulo:
        _MEXENDO.pop(campo, None)
    else:
        _MEXENDO[campo] = rotulo
    return {"mesa": {campo: rotulo}}


@gesto("06-navegacao.html", "fechar-definicoes")
def fechar_definicoes(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O fechar e o "Cancelar" da tela de definições: LARGAM o que ela não guardou."""
    _largar_o_que_ela_mexeu()
    return {"mesa": _linhas_dos_botoes(
        perfil.ativo_que_vale((ctx.state or {}).get("active_profile")))}


@gesto("06-navegacao.html", "fechar-ponto")
def fechar_ponto(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O fechar e o "Cancelar" do *Estilo point-and-click*. Mesmo ato do irmão.

    Um segundo NOME, não um segundo comportamento: o piloto recusa gesto não registrado, e pendurar
    esta tela no `fechar-definicoes` faria o relato nomear a pop-up errada. O ato é o mesmo porque
    as duas telas dividem a trava (escrevem o MESMO campo, `Profile.button_actions`). A mordida está
    em `test_a_06_o_ponto_guarda_o_que_ela_escolhe.py`: com o corpo `return None` o caso do
    "Cancelar" reprova, pois a linha abandonada volta a ser oferecida ao "Guardar" seguinte.
    """
    _largar_o_que_ela_mexeu()
    return {"mesa": _linhas_dos_botoes(
        perfil.ativo_que_vale((ctx.state or {}).get("active_profile")))}


@gesto("06-navegacao.html", "tecla-escrita")
def tecla_escrita(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O usuário mexeu num dos oito campos de *Teclas do teclado*. NÃO grava nada.

    Irmão do `linha-de-botao`, pela mesma decisão de 02/09/2026; quem grava é o "Guardar" da tela.
    Atende o **CLIQUE**, não só o `change`, para o campo de texto ser editável de verdade: o
    `escrever()` do piloto escreve `el.value = t` sempre que diferem, e o campo em edição difere já
    na primeira letra (o tique de 100 ms apagaria o que se digita); o `change` de `<input>` só chega
    quando o campo PERDE o foco. O clique dentro do campo chega na hora e abre a trava; o `change`
    depois a atualiza.

    Recusa é `RuntimeError`, não `ValueError`: o `_recusou_dizendo` do piloto guarda a classe da
    exceção no relato, e `ValueError` é a língua de quem programa. Desde 13/09/2026 nenhuma das duas
    chega à tela: a combinação inválida pisca a recusa no campo (FRASES-E-DICAS-01). A anterior
    sobrevive à recusa: o gesto não escreve em disco e ao recusar LARGA a trava do campo, e no tique
    seguinte a pintura devolve o que o perfil guarda (segurar a trava deixaria o erro na tela para
    sempre e o "Guardar" recusaria a cada clique).
    """
    campo = str(o.get("campo") or "")
    botao = campo.removeprefix(PREFIXO_DA_TECLA)
    if not campo.startswith(PREFIXO_DA_TECLA) or botao not in acoes.DOMINIO_DO_TECLADO:
        raise ValueError(
            f"tecla-escrita: o clique não disse qual botão (veio {campo!r}). O "
            f"`data-campo` de cada campo é `{PREFIXO_DA_TECLA}<botão>`, e ele "
            "vem do gerador.")
    texto = str(o.get("valor") or "")
    try:
        tokens = tokens_da_tecla(texto)
    except ValueError as erro:
        _MEXENDO.pop(campo, None)
        raise RuntimeError(
            f"{_nome_do_botao(botao)}: {erro} O que estava guardado continua "
            "valendo — nada foi gravado.") from erro
    _MEXENDO[campo] = texto
    return {"mesa": {campo: texto}} if tokens or not texto else None


@gesto("06-navegacao.html", "fechar-teclas")
def fechar_teclas(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O fechar e o "Cancelar" da tela de teclas: LARGAM o que ela não guardou."""
    _largar_o_que_ela_mexeu()
    return {"mesa": teclas_dos_botoes(
        perfil.ativo_que_vale((ctx.state or {}).get("active_profile")))}


def _atalhos_de_hoje(prof: Any) -> dict[str, list[str]]:
    """`Profile.key_bindings` MATERIALIZADO, com o mesmo alcance de hoje.

    `None` = *"herda `DEFAULT_BUTTON_BINDINGS` inteiro"* (`profiles/manager.resolve_key_bindings`).
    Para trocar UMA linha é preciso um dicionário, e o que **não muda nada** é a cópia do de fábrica
    (medido: `resolve_key_bindings(None)` e `resolve_key_bindings(dict(DEFAULT_ BUTTON_BINDINGS))`
    devolvem o mesmo objeto). Volta: quando o dicionário termina igual ao de fábrica, quem grava
    devolve `None`, senão o perfil congelaria o padrão de HOJE; mesma disciplina do `button_actions`
    (razão em `guardar_definicoes`).
    """
    from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS

    atual = getattr(prof, "key_bindings", None)
    if atual is None:
        return {b: list(t) for b, t in DEFAULT_BUTTON_BINDINGS.items()}
    return {b: list(t) for b, t in atual.items()}


def _de_fabrica_vira_none(atalhos: dict[str, list[str]]) -> dict[str, list[str]] | None:
    """`None` quando o dicionário é o de fábrica — ver `_atalhos_de_hoje`."""
    from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS

    de_fabrica = {b: list(t) for b, t in DEFAULT_BUTTON_BINDINGS.items()}
    return None if atalhos == de_fabrica else atalhos


@gesto("06-navegacao.html", "guardar-teclas", grava="gravar_pelo_gesto")
def guardar_teclas(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Guardar" da tela *Teclas do teclado*. `Profile.key_bindings`.

    **A metade que faltava da paridade** (`paridade-gtk-html.csv`, linha 208): a janela antiga deixa
    digitar qualquer combinação de `KEY_*` na coluna "Tecla do teclado"; a tela nova só tinha a
    lista fechada de 26 ações e tocava `key_bindings` só para zerá-lo.

    Grava o alcance do produto, os oito botões de `acoes.DOMINIO_DO_TECLADO` (nos outros catorze
    `key_bindings` não manda: vale o mapa fixo do `UinputMouseDevice`, e gravar poria no disco
    escolha que o `resolver()` não lê). **NÃO apaga** as chaves FORA dos oito (Passo 2 da sprint): o
    `Ctrl + W` no Cross escrito pela janela antiga não é alcançado por esta tela, que não tem
    direito de apagá-lo; o dicionário de partida é o do perfil (`_atalhos_de_hoje`) e só as oito
    chaves são reescritas. Campo em branco é `— Nada —`: a chave sai do dicionário, e
    `tabela_efetiva` lê a ausência dentro do domínio como silêncio, o que `resolve_key_bindings`
    entrega ao device.

    Recusa dizendo, uma linha por vez, e nada é gravado quando alguma recusa (gravar sete de oito e
    calar sobre a oitava é botão que responde calado).

    Onde grava (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01): as teclas são do cartão «Teclado», do
    computador. No perfil só quando ele já tem teclas próprias; senão no ``maquina.json``, e o
    perfil não muda.
    """
    nome = _nome_do_ativo_ou_nada(ctx)
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler os campos da tela. O botão precisa do "
            "`data-hef-forma` para o piloto recolher o que você escreveu — se "
            "ele sumiu do desenho, o Guardar não tem o que gravar.")

    escritos: dict[str, tuple[str, ...]] = {}
    recusas: list[str] = []
    for chave, texto in forma.items():
        if not str(chave).startswith(PREFIXO_DA_TECLA):
            continue
        botao = str(chave)[len(PREFIXO_DA_TECLA):]
        if botao not in acoes.DOMINIO_DO_TECLADO:
            continue
        try:
            escritos[botao] = tokens_da_tecla(str(texto))
        except ValueError as erro:
            recusas.append(f"{_nome_do_botao(botao)}: {erro}")
    if recusas:
        raise RuntimeError(
            "não gravei nada — " + " ".join(recusas)
            + " O que estava guardado continua valendo.")
    if not escritos:
        raise RuntimeError(
            "não achei nenhum campo de tecla na tela. Os oito campos vêm do "
            "gerador com `data-campo=\"tecla-<botão>\"`; sem eles não há o que "
            "gravar.")

    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    perfil._com_o_src()
    visto: dict[str, Any] = {}

    def _com_as_teclas(prof: Any) -> Any:
        atalhos = _atalhos_de_hoje(prof)
        for botao, tokens in escritos.items():
            if tokens:
                atalhos[botao] = list(tokens)
            else:
                atalhos.pop(botao, None)
        novo = _de_fabrica_vira_none(atalhos)
        visto["escolhas"] = getattr(prof, "button_actions", None) or {}
        visto["igual"] = getattr(prof, "key_bindings", None) == novo
        if visto["igual"]:
            return None
        return prof.model_copy(update={"key_bindings": novo})

    # `profile.switch` no meio de uma partida cobra.
    onde, _novo = gravar_pelo_gesto("teclado", nome, _com_as_teclas,
                                    origem="interface-nova")
    if visto.get("igual"):
        _largar_o_que_ela_mexeu()
        raise RuntimeError(
            f"não havia o que guardar — {_quem_guarda(onde, nome)} já digita "
            "exatamente o que estes campos mostram. Está guardado. Para mudar "
            "alguma coisa, escreva outra tecla e clique aqui de novo.")
    # tela DIZ em vez de gravar por cima: `button_actions` é a camada de cima
    escolhas = visto.get("escolhas") or {}
    mascarados = sorted(b for b, t in escritos.items()
                        if b in escolhas and "+".join(t) != str(escolhas[b]))
    perfil.reaplicar(nome, ctx, p)
    _largar_o_que_ela_mexeu()
    if mascarados:
        raise RuntimeError(
            "guardei as teclas, e estas linhas continuam fazendo o que a lista "
            "de <b>Definições controle e mouse</b> diz, que vence: "
            + ", ".join(f"{_nome_do_botao(b)} = "
                        f"{acoes.rotulo(str(escolhas[b]))}" for b in mascarados)
            + ". Para a tecla que você escreveu valer, ponha essas linhas de "
              "volta no de fábrica lá.")
    return {"mesa": teclas_dos_botoes(
        perfil.ativo_que_vale((ctx.state or {}).get("active_profile")))}


@gesto("06-navegacao.html", "padrao-da-tecla", grava="gravar_pelo_gesto")
def padrao_da_tecla(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Voltar ao padrão" de **UMA** linha — Passo 2 da sprint.

    Regra de produto: *"'Voltar ao padrão' devolve a LINHA ao padrão; ele não é um apagador de tudo
    o que o usuário escreveu na janela antiga."* O botão da tela inteira segue zerando os dois
    campos (e DIZ o que apaga, na confirmação e no recibo), mas era o ÚNICO caminho: trocar uma
    linha de volta custava perder todas as outras.

    O padrão da linha é perguntado ao dono: `acoes.padrao()[botão]`, que no `DOMINIO_DO_TECLADO` é o
    que `DEFAULT_BUTTON_BINDINGS` diz. **ESCREVER é o certo e APAGAR o errado**, medido: dentro de
    um `key_bindings` que já é dicionário, chave AUSENTE não é "de fábrica", é `— Nada —`
    (`acoes.tabela_efetiva`; `resolve_key_bindings` não mescla com os defaults), e apagar devolveria
    a linha ao SILÊNCIO com o botão dizendo "padrão". Tira a linha das DUAS camadas:
    `button_actions` vence `key_bindings`, e devolver só a de baixo deixaria o botão fazendo o que a
    lista escolheu.
    """
    botao = str(o.get("tecla") or o.get("linha") or "")
    if botao not in acoes.DOMINIO_DO_TECLADO:
        raise ValueError(
            f"padrao-da-tecla: o clique não disse qual linha (veio {botao!r}). "
            "O `data-tecla` de cada botão é o id do botão, e ele vem do gerador.")
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    nome = _nome_do_ativo_ou_nada(ctx)
    perfil._com_o_src()
    de_fabrica = acoes.padrao()[botao].split("+")
    visto: dict[str, Any] = {}

    def _a_tecla_de_fabrica(prof: Any) -> Any:
        atalhos = _atalhos_de_hoje(prof)
        visto["antes"] = list(atalhos.get(botao) or ())
        atalhos[botao] = list(de_fabrica)
        novas_teclas = _de_fabrica_vira_none(atalhos)
        mudou = (prof.key_bindings is None) != (novas_teclas is None) or (
            (prof.key_bindings or {}) != (novas_teclas or {}))
        visto["mudou_tecla"] = mudou
        return prof.model_copy(update={"key_bindings": novas_teclas}) if mudou else None

    def _sem_a_escolha(prof: Any) -> Any:
        escolhas = dict(getattr(prof, "button_actions", None) or {})
        visto["tirado"] = escolhas.pop(botao, None)
        if visto["tirado"] is None:
            return None
        return prof.model_copy(update={"button_actions": escolhas or None})

    onde, _ = gravar_pelo_gesto("teclado", nome, _a_tecla_de_fabrica,
                                origem="interface-nova")
    gravar_pelo_gesto("mouse", nome, _sem_a_escolha, origem="interface-nova")
    antes = visto.get("antes") or []
    tirado = visto.get("tirado")
    if not visto.get("mudou_tecla") and tirado is None:
        _MEXENDO.pop(f"{PREFIXO_DA_TECLA}{botao}", None)
        raise RuntimeError(
            f"não havia o que voltar — {_nome_do_botao(botao)} já está no de "
            f"fábrica {_em_quem(onde, nome)}. Não gravei nada e não incomodei "
            "o serviço.")
    perfil.reaplicar(nome, ctx, p)
    _MEXENDO.pop(f"{PREFIXO_DA_TECLA}{botao}", None)
    _MEXENDO.pop(f"{PREFIXO_DA_ACAO}{botao}", None)
    saiu = []
    if antes and antes != de_fabrica:
        saiu.append(f"a tecla “{_atalho_em_palavras('+'.join(antes))}”")
    if tirado is not None:
        saiu.append(f"a escolha “{acoes.rotulo(str(tirado))}” da lista")
    recado = (f"{_nome_do_botao(botao)} voltou ao de fábrica "
              f"(“{acoes.rotulo(acoes.padrao()[botao])}”)"
              + (", e com ele saiu " + " e ".join(saiu) if saiu else "")
              + ". As outras linhas não foram tocadas.")
    return {"recado": recado,
            "mesa": teclas_dos_botoes(
                perfil.ativo_que_vale((ctx.state or {}).get("active_profile")))}


def _o_desenho_congelado(diferentes: dict[str, str]) -> dict[str, tuple[str, str]]:
    """As linhas de `diferentes` que são o DESENHO CONGELADO, e não escolha do usuário.

    Defeito medido em 02/09/2026, declarado em
    `core/keyboard_mappings.PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ`: o L3 nasceu ALTERNADOR
    (`__TOGGLE_OSK__`, decisão 6 dela, *"aperta abre o teclado virtual, aperta de novo fecha"*), a
    página que o produto RENDERIZA foi congelada antes e não tem a `<option>` do rótulo novo, então
    a pintura do `acao-l3` é RECUSADA EM SILÊNCIO (`hefesto_vivo.escrever`, alvo `valor`: o
    `<select>` só aceita texto exato de opção que oferece). A linha mostrava *"Abrir o teclado na
    tela"* (`__OPEN_OSK__`) e o "Guardar" a recolhia como escolha do usuário. Custo, pelo fio do
    daemon (`acoes_de_botao.resolver` → `profiles.manager.resolve_key_bindings`): sem override o
    device recebe `['__TOGGLE_OSK__']`, com o que o "Guardar" gravava recebe `['__OPEN_OSK__']`, **o
    L3 para de alternar naquele perfil**, sem rastro (bastava um clique em qualquer OUTRA linha).

    O que separa o congelado da escolha é `_MEXENDO`, não um literal: só tem linha que ELA trocou
    pelo gesto `linha-de-botao`; se o `acao-l3` está lá, foi escolha com o dedo e o "Guardar" a
    grava. Morre sozinha na publicação: a tabela que a alimenta é a declaração, e
    `test_o_padrao_de_fabrica_cabe_na_tela_publicada` reprova a que caducou; publicada a `06` a
    linha do L3 sai, esta função devolve `{}` e o "Guardar" volta a gravar as 21.

    :returns: `{botão: (o token de fábrica, o token que a tela pôs no lugar)}`.
    """
    fora: dict[str, tuple[str, str]] = {}
    for botao, (de_fabrica, da_tela) in PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ.items():
        if diferentes.get(botao) != da_tela:
            continue
        if f"{PREFIXO_DA_ACAO}{botao}" in _MEXENDO:
            continue
        fora[botao] = (de_fabrica, da_tela)
    return fora


def _frase_do_congelado(congelado: dict[str, tuple[str, str]]) -> str:
    """O que NÃO foi gravado e por quê — a frase vai para a tela do usuário."""
    partes = []
    for botao, (de_fabrica, da_tela) in sorted(congelado.items()):
        rotulo_certo = acoes.ACOES.get(de_fabrica, ("", de_fabrica))[1]
        rotulo_tela = acoes.ACOES.get(da_tela, ("", da_tela))[1]
        partes.append(
            f"{_nome_do_botao(botao)} (a tela mostra “{rotulo_tela}”; de fábrica "
            f"ele faz “{rotulo_certo}”)")
    return (
        "não guardei estas linhas, porque o que a tela mostra nelas não é a sua "
        "escolha: " + ", ".join(partes) + ". A lista desta versão da página não "
        "tem a opção do que o produto faz de fábrica, então ela abre no rótulo "
        "mais próximo — gravar isso trocaria o comportamento do controle sem "
        "você pedir. Se você QUER essa opção, escolha-a na linha e clique aqui "
        "de novo: aí é escolha sua e eu gravo.")


def _perfil_ativo_ou_recusa(ctx: Contexto) -> str:
    """O nome do perfil ativo, ou a recusa com o motivo."""
    nome = perfil.nome_do_ativo(ctx.state).strip()
    if not nome:
        raise RuntimeError(
            "não há perfil ativo agora, e o que cada botão faz é do perfil — não "
            "da máquina. Escolha um perfil na aba Perfis e tente de novo.")
    return nome


def _nome_do_ativo_ou_nada(ctx: Contexto) -> str:
    """O nome do perfil ativo, ou ``""``."""
    return perfil.nome_do_ativo(ctx.state).strip()


def _quem_guarda(onde: str, nome: str) -> str:
    """O sujeito da frase: o perfil, quando ele sobrepõe o cartão, ou o computador."""
    return f"o perfil “{nome}”" if onde == "jogo" and nome else "o computador"


def _em_quem(onde: str, nome: str) -> str:
    return f"neste perfil (“{nome}”)" if onde == "jogo" and nome else "neste computador"


@gesto("06-navegacao.html", "guardar-definicoes", grava="gravar_pelo_gesto")
def guardar_definicoes(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Guardar" das 21 linhas de *o que cada botão faz*. `Profile.button_actions`.

    Ganhou dono em 01/09/2026, por decisão de produto (*"ganha campo. essa é a parte das features
    que precisam ou serem ajustadas ou desenvolvidas."*): a tela deixava escolher 21 linhas e o
    perfil alcançava 9; a cura foi o campo nascer, não o botão fingir.

    Grava a `forma`, que o piloto recolhe quando o botão traz `data-hef-forma` (o ouvinte manda o
    valor do elemento CLICADO, e o Guardar é outro elemento). **Só o que mudou vai ao disco**:
    gravar as 21 encheria o perfil de linhas iguais ao padrão e, quando o padrão do produto mudasse,
    ele congelaria o VELHO sem escolha de ninguém; `button_actions` guarda diferença e o `None` do
    campo é: herda. O campo zerado é `None`, nunca `{}` (`None` = perfil nunca editado; `{}` =
    "nenhum botão faz nada"); depois das duas recusas abaixo, só o perfil que já tinha `{}` ainda
    grava `None` (normalização de estado que o esquema não pretende).

    **Era um apagador com rótulo de "Guardar"** (medido em 02/09/2026): as 21 opções da tela eram
    **exatamente** `acoes.padrao()`, logo `diferentes` saía `{}` e o gesto gravava `button_actions =
    None`, apagando em silêncio qualquer escolha do perfil. Hoje nada mudou deixa de gravar coisa
    alguma: com o perfil guardando escolhas a trava recusa, com o perfil já igual à tela a recusa
    diz que já está guardado.

    A trava FICA: as 21 `<select>` têm `data-campo` e `data-hef-alvo="valor"` na página publicada (o
    usuário mandou publicar em 02/09/2026), e a forma toda no de fábrica com o perfil guardando
    escolhas deixou de ser o estado permanente e virou JANELA, os 100 ms entre a página carregar e o
    primeiro tique pintar (`hefesto_vivo.TIQUE_MS`), em que um clique leria o desenho como escolha e
    apagaria. É o que separa "ela zerou" de "a tela ainda não falou".

    **O que a tela oferece e o produto não atende é dito, não engolido**: "Abrir a Steam", "Sair do
    modo jogo" e "Escolher um programa…", os dois papéis de eixo pedidos a um botão, e os gatilhos
    L2/R2 (espelho do cross e do triangle, `uinput_mouse._resolve_emulated_set`). O gesto GRAVA o
    resto e LEVANTA nomeando o que não pousou. O que a tela NÃO sabe oferecer também é dito e deixou
    de ser gravado (02/09/2026, `_o_desenho_congelado`): recolher o L3 congelado gravava `{'l3':
    '__OPEN_OSK__'}` no perfil ATIVO e **o L3 parava de alternar**.

    Onde grava (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01): as linhas são do cartão «Mouse», do
    computador. No perfil só quando ele já tem escolhas próprias aqui; senão no ``maquina.json``, e
    o perfil não muda.
    """
    nome = _nome_do_ativo_ou_nada(ctx)
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler as linhas da tela. O botão precisa do "
            "`data-hef-forma` para o piloto recolher os campos — se ele sumiu do "
            "desenho, o Guardar não tem o que gravar.")

    escolhas: dict[str, str] = {}
    nao_reconhecidas: list[str] = []
    for botao, rotulo in forma.items():
        if botao not in acoes.BOTOES:
            continue
        token = acoes.token_do_rotulo(str(rotulo))
        if token is None:
            nao_reconhecidas.append(f"{_nome_do_botao(botao)}={rotulo!r}")
            continue
        escolhas[botao] = token
    if nao_reconhecidas:
        raise ValueError(
            "estas linhas trazem uma opção que o produto não conhece: "
            + ", ".join(nao_reconhecidas)
            + ". A lista da tela e a do produto saem do mesmo lugar "
              "(`core/acoes_de_botao.ACOES`) — se divergiram, foi o desenho que "
              "andou sem o gerador.")

    de_fabrica = acoes.padrao()
    diferentes = {b: a for b, a in escolhas.items() if de_fabrica.get(b) != a}
    congelado = _o_desenho_congelado(diferentes)
    for botao in congelado:
        del diferentes[botao]
    aviso = _frase_do_congelado(congelado) if congelado else ""

    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    perfil._com_o_src()
    novo = diferentes or None
    visto: dict[str, Any] = {}

    def _com_as_linhas(prof: Any) -> Any:
        visto["guardadas"] = dict(prof.button_actions or {})
        if prof.button_actions == novo:
            visto["desfecho"] = "igual"
            return None
        if novo is None and prof.button_actions and not _MEXENDO:
            visto["desfecho"] = "trava"
            return None
        visto["perdidos"] = atalhos_que_param_de_valer(
            {"key_bindings": getattr(prof, "key_bindings", None) or {},
             "button_actions": novo})
        return prof.model_copy(update={"button_actions": novo})

    onde, _gravado = gravar_pelo_gesto("mouse", nome, _com_as_linhas,
                                       origem="interface-nova")
    if visto.get("desfecho") == "igual":
        guardadas = (f"nenhuma escolha sua: as {len(acoes.BOTOES)} linhas estão "
                     "no de fábrica"
                     if not novo else
                     f"{len(novo)} escolha(s) sua(s)")
        _largar_o_que_ela_mexeu()
        raise RuntimeError(
            f"não havia o que guardar — {_quem_guarda(onde, nome)} já tem "
            f"exatamente o que a tabela mostra ({guardadas}). Está guardado. Para mudar "
            "alguma coisa, troque a linha e clique aqui de novo; para voltar "
            "tudo ao de fábrica, use o “Voltar ao padrão” ao lado."
            + (f" E {aviso}" if aviso else ""))
    # (`hefesto_vivo.TIQUE_MS`) em que a tela ainda é o desenho, e nessa janela
    if visto.get("desfecho") == "trava":
        raise RuntimeError(
            "não guardei: a tela está no de fábrica e "
            f"{_quem_guarda(onde, nome)} guarda "
            f"{len(visto['guardadas'])} escolha(s) sua(s) — gravar isto as "
            "apagaria. Espere a tabela se preencher e tente de novo."
            + (f" E {aviso}" if aviso else ""))
    perdidos = visto.get("perdidos") or []
    perfil.reaplicar(nome, ctx, p)
    _largar_o_que_ela_mexeu()

    _, _, sem_dono = acoes.resolver(novo)
    recados = []
    if perdidos:
        # ela mora em `core/acoes_de_botao.py` — está no relato desta frente.
        recados.append(
            "guardei, e estes atalhos que você escreveu na janela antiga param "
            "de valer neste perfil: "
            + ", ".join(f"{_nome_do_botao(b)} = {_atalho_em_palavras(t)}"
                        for b, t in perdidos)
            + ". O perfil ainda os guarda no arquivo, mas o que passa a valer é "
              "o que esta tabela mostra — use o “Voltar ao padrão” para devolver "
              "tudo ao de fábrica.")
    if sem_dono:
        recados.append(
            "guardei o que o produto sabe fazer, e estas linhas ficaram sem "
            "quem as atenda: " + ", ".join(_nome_do_botao(b) for b in sem_dono)
            + ". Elas estão no perfil e não acendem nada hoje — é feature que "
              "falta, não erro seu.")
    if aviso:
        recados.append(aviso)
    if recados:
        raise RuntimeError(" ".join(recados))


@gesto("06-navegacao.html", "padrao-definicoes", grava="gravar_pelo_gesto")
def padrao_definicoes(ctx: Contexto, o: dict[str, Any],
                      p: Any) -> dict[str, Any] | None:
    """"Voltar ao padrão" das 21 linhas de *o que cada botão faz*.

    Grava `key_bindings = None` no perfil ATIVO e manda o daemon reaplicá-lo. `None` não é "vazio":
    o esquema o define como *"herda `DEFAULT_BUTTON_BINDINGS` do core"* (`profiles/schema.py`), e
    `{}` é teclado silencioso (devolveria controle MUDO com o botão dizendo "de fábrica"). **Devolve
    as VINTE E UMA**, contado em 01/09/2026: 9 linhas que `key_bindings` alcança (l1, r1, l3, r3,
    options, create e as três regiões do touchpad, `core/keyboard_mappings.py`) e 12 de mapas FIXOS
    do produto (`BUTTON_TO_UINPUT`, `DPAD_TO_KEY`, `EDGE_KEY_MAP` em `integrations/uinput_mouse.py`,
    mais L2/R2 e a DIREÇÃO dos analógicos), sempre de fábrica; zerar as 9 devolve a tabela inteira,
    por isso este botão fecha inteiro e o "Guardar" ao lado não (guardar 9 de 21 e perder 12 caladas
    é botão que responde calado).

    Zera os DOIS campos desde 01/09/2026, `key_bindings` e `button_actions` (zerar só um deixaria a
    tabela metade de fábrica com o botão dizendo o contrário). O alvo é o perfil ATIVO e é dito (os
    dois são campo de perfil, não da máquina); sem perfil ativo RECUSA. Grava por
    `perfil.gravar_e_reaplicar`, a mesma da aba Perfis (`save_profile` em disco + `profile.switch`
    se for o ativo; `profiles/loader.save_profile` existe, o `SEM_GESTO` que dizia "gravar perfil
    não tem método" estava errado).

    **Dá recibo do que apagou** (04/09/2026, canal de SUCESSO da D-01): apagava os `key_bindings` da
    janela antiga e voltava sem uma palavra (o piloto imprimia `aplicado` no terminal, que quem
    clica não lê); o `recado` nomeia quantos atalhos saíram, no cartão, em verde.

    Um degrau (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01): as teclas são do cartão «Teclado» e as
    linhas do «Mouse», os dois do computador. Cada um volta onde a marca dele diz: no jogo que o
    sobrepõe sai a sobreposição e volta a valer o computador; sem sobreposição o computador volta ao
    de fábrica. Sem perfil ativo, é o computador que volta.
    """
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import gravar_pelo_gesto

    nome = _nome_do_ativo_ou_nada(ctx)
    perfil._com_o_src()
    visto: dict[str, Any] = {}

    def _sem_as_teclas(prof: Any) -> Any:
        visto["atalhos"] = dict(getattr(prof, "key_bindings", None) or {})
        if prof.key_bindings is None:
            return None
        visto["mudou"] = True
        return prof.model_copy(update={"key_bindings": None})

    def _sem_as_linhas(prof: Any) -> Any:
        if prof.button_actions is None:
            return None
        visto["mudou"] = True
        return prof.model_copy(update={"button_actions": None})

    onde, _ = gravar_pelo_gesto("teclado", nome, _sem_as_teclas,
                                origem="interface-nova")
    gravar_pelo_gesto("mouse", nome, _sem_as_linhas, origem="interface-nova")
    # OS DOIS CAMPOS, e não só um — 01/09/2026, quando o `button_actions`
    # `button_actions` (as vinte e uma linhas da tela). Um "Voltar ao padrão"
    if not visto.get("mudou"):
        # `profile.switch` no meio de uma partida não é de graça. **Mas não
        _largar_o_que_ela_mexeu()
        raise RuntimeError(
            f"não havia o que voltar — {_quem_guarda(onde, nome)} já está no de "
            f"fábrica nas {len(acoes.BOTOES)} linhas de o que cada botão faz. "
            "Não gravei nada e não incomodei o daemon.")
    atalhos = visto.get("atalhos") or {}
    perfil.reaplicar(nome, ctx, p)
    _largar_o_que_ela_mexeu()
    if not atalhos:
        return None
    quais = ", ".join(f"{_nome_do_botao(b)} = {_atalho_em_palavras(_colado(v))}"
                      for b, v in sorted(atalhos.items()))
    return {"recado": (
        f"Voltei as {len(acoes.BOTOES)} linhas ao de fábrica, e com elas saíram "
        f"{len(atalhos)} atalho(s) de teclado que "
        f"{'este perfil' if onde == 'jogo' and nome else 'o computador'} guardava: "
        f"{quais}.")}


@gesto("06-navegacao.html", "padrao-da-aba", grava="voltar_o_computador_ao_de_fabrica")
def padrao_da_aba(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """O «Voltar ao padrão» da aba: o mouse e o teclado voltam UM DEGRAU."""
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
    from hefesto_dualsense4unix.profiles.schema import ProfileMouseConfig

    nome = _nome_do_ativo_ou_nada(ctx)
    loader = perfil._com_o_src()
    cru = None
    if nome:
        try:
            cru = loader.load_profile(nome)
        except Exception:
            cru = None
    no_jogo = cru is not None and not opc.e_o_freestyle(cru.name)
    for cartao in ("mouse", "teclado"):
        if cru is not None and no_jogo and opc.sobrepoe(cru, cartao):
            opc.voltar_ao_do_computador(cartao, None, cru.name)
        else:
            opc.voltar_o_computador_ao_de_fabrica(cartao)
    if not no_jogo:
        ok, motivo = _ok_e_motivo(
            p.machine_declare({"gestos": dict.fromkeys(ag.GESTOS)}))
        if not ok:
            raise RuntimeError(
                "o mouse e o teclado voltaram, e os gestos não: "
                + (motivo or "o Hefesto não respondeu"))
    vista = opc.carregar_o_que_vale(nome) if no_jogo else None
    mouse = vista.mouse if vista is not None else None
    speed, scroll = opc.velocidades_do_computador()
    if mouse is not None:
        speed, scroll = mouse.speed, mouse.scroll_speed
    campos = ProfileMouseConfig.model_fields
    _mandar(p, origin=MANUAL,
            speed=speed if speed is not None else campos["speed"].default,
            scroll_speed=scroll if scroll is not None else campos["scroll_speed"].default)
    perfil.reaplicar(nome, ctx, p)
    _largar_o_que_ela_mexeu()


@gesto("06-navegacao.html", "guardar-ponto", grava="gravar_e_reaplicar")
def guardar_ponto(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Guardar" do *Estilo point-and-click*. Escreve `Profile.button_actions`.

    Ganhou dono em 11/09/2026 (F2-POINT-AND-CLICK); o que o segurava era um fato que a medição
    derrubou: o `SEM_GESTO` dizia *"'Estilo de Jogo' não existe em campo, widget ou preset nenhum do
    produto"*, verdade sobre um campo chamado "estilo" e pergunta errada. As sete linhas perguntam
    **o que cada peça do controle faz**, o que `Profile.button_actions` guarda desde 01/09/2026
    (*"ganha campo"*). Seis das sete são botões de `acoes.BOTOES`, com o id que as Definições já
    gravam; a sétima não é botão em lugar nenhum do produto (`PONTO_MAPA` do gerador).

    É a mesma tabela vista por janela menor, então **junta em vez de substituir**: a forma recolhida
    é recortada pelo `id` da pop-up e traz SEIS linhas, e gravar só o recebido apagaria as outras
    dezesseis escolhas (o apagador com rótulo de "Guardar", pago em 02/09/2026). Voltar ao de
    fábrica é TIRAR do perfil, não gravar o valor de fábrica (`button_actions` guarda diferença;
    gravar congelaria o padrão VELHO).

    A trava contra o desenho é a do irmão, mais larga sem custo: lá só dispara com a forma inteira
    no de fábrica; aqui, sem NENHUMA linha em `_MEXENDO`, **qualquer** divergência entre a forma e o
    perfil quer dizer *o piloto ainda não falou* (nos 100 ms entre a página carregar e o primeiro
    tique a tela é o desenho). Com `_MEXENDO` cheio a forma é escolha do usuário e o gesto grava,
    inclusive devolvendo tudo ao de fábrica. O que se perde é nomeado só do que ESTE clique escreveu
    (`resolver()` devolve os botões que ninguém atende, mas nomear os outros dezesseis seria
    responder sobre o que não fez).
    """
    nome = _perfil_ativo_ou_recusa(ctx)
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler as linhas da tela. O botão precisa do "
            "`data-hef-forma` para o piloto recolher os campos — se ele sumiu do "
            "desenho, o Guardar não tem o que gravar.")

    escolhas: dict[str, str] = {}
    nao_reconhecidas: list[str] = []
    for botao, rotulo in forma.items():
        if botao not in acoes.BOTOES:
            continue
        token = acoes.token_do_rotulo(str(rotulo))
        if token is None:
            nao_reconhecidas.append(f"{_nome_do_botao(botao)}={rotulo!r}")
            continue
        escolhas[botao] = token
    if nao_reconhecidas:
        raise ValueError(
            "estas linhas trazem uma opção que o produto não conhece: "
            + ", ".join(nao_reconhecidas)
            + ". A lista da tela e a do produto saem do mesmo lugar "
              "(`core/acoes_de_botao.ACOES`) — se divergiram, foi o desenho que "
              "andou sem o gerador.")
    if not escolhas:
        raise RuntimeError(
            "não consegui ler as linhas desta tela: nenhuma delas disse de que "
            "botão é. O `data-linha` de cada lista vem do gerador — sem ele o "
            "Guardar não tem o que gravar.")

    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    mostra = _linhas_dos_botoes({"button_actions": prof.button_actions,
                                 "key_bindings": prof.key_bindings})
    divergem = [b for b, token in escolhas.items()
                if mostra.get(f"{PREFIXO_DA_ACAO}{b}") != acoes.rotulo(token)]
    if divergem and not _MEXENDO:
        raise RuntimeError(
            f"não guardei: o que estas linhas mostram não é o que o perfil "
            f"“{nome}” guarda — "
            + ", ".join(_nome_do_botao(b) for b in sorted(divergem))
            + ". Espere a tabela se preencher e tente de novo.")

    de_fabrica = acoes.padrao()
    diferentes = {b: t for b, t in escolhas.items() if de_fabrica.get(b) != t}
    congelado = _o_desenho_congelado(diferentes)
    for botao in congelado:
        del diferentes[botao]
    aviso = _frase_do_congelado(congelado) if congelado else ""

    novo: dict[str, str] = dict(prof.button_actions or {})
    for botao in escolhas:
        if botao in congelado:
            continue
        if botao in diferentes:
            novo[botao] = diferentes[botao]
        else:
            novo.pop(botao, None)
    novo_ou_nada = novo or None
    if prof.button_actions == novo_ou_nada:
        _largar_o_que_ela_mexeu()
        raise RuntimeError(
            f"não havia o que guardar — o perfil “{nome}” já faz exatamente o "
            "que estas linhas mostram. Está guardado. Para mudar alguma coisa, "
            "troque a linha e clique aqui de novo."
            + (f" E {aviso}" if aviso else ""))
    perdidos = atalhos_que_param_de_valer(
        {"key_bindings": getattr(prof, "key_bindings", None) or {},
         "button_actions": novo_ou_nada})
    perfil.gravar_e_reaplicar(
        prof.model_copy(update={"button_actions": novo_ou_nada}), ctx, p)
    _largar_o_que_ela_mexeu()

    _, _, sem_dono = acoes.resolver(novo_ou_nada)
    recados = []
    if perdidos:
        recados.append(
            "guardei, e estes atalhos que você escreveu na janela antiga param "
            "de valer neste perfil: "
            + ", ".join(f"{_nome_do_botao(b)} = {_atalho_em_palavras(t)}"
                        for b, t in perdidos)
            + ". O perfil ainda os guarda no arquivo, mas o que passa a valer é "
              "o que estas listas mostram.")
    daqui = [b for b in sem_dono if b in escolhas]
    if daqui:
        recados.append(
            "guardei o que o produto sabe fazer, e estas linhas ficaram sem "
            "quem as atenda: " + ", ".join(_nome_do_botao(b) for b in daqui)
            + ". Elas estão no perfil e não acendem nada hoje — é feature que "
              "falta, não erro seu.")
    if aviso:
        recados.append(aviso)
    if recados:
        raise RuntimeError(" ".join(recados))


# recolhe a `forma` e grava com `perfil.gravar_e_reaplicar`, e a trava contra o
def _destino_do_rotulo(rotulo: str) -> str | None:
    """O texto da `<option>` → o id de destino. `None` é o "— Sem troca —"."""
    texto = str(rotulo or "").strip()
    if texto == SEM_TROCA:
        return None
    if texto not in ROTULOS_DA_TROCA:
        raise ValueError(
            f"a opção {texto!r} não está na tabela da troca de botões — a lista "
            "da tela e `a06_navegacao.ROTULOS_DA_TROCA` saem do mesmo mapa das "
            "peças; se divergiram, foi o desenho que andou sem o gerador.")
    return ROTULOS_DA_TROCA[texto]


def _nome_na_troca(botao: str) -> str:
    """O nome da linha como a tela "Trocar os botões" o escreve."""
    rotulo = _rotulo_do_destino(botao)
    return rotulo if rotulo != botao else _nome_do_botao(botao)


def _frase_da_troca(exc: remap.RemapeamentoRecusadoError) -> str:
    """A recusa do motor, com os nomes que ela lê na tela."""
    if exc.motivo == remap.MOTIVO_COLISAO:
        *origens, destino = exc.botoes
        return (
            "não guardei: " + " e ".join(_nome_na_troca(b) for b in origens)
            + f" passam a ser o mesmo botão, {_nome_na_troca(destino)} — cada "
              "botão do jogo recebe uma linha só.")
    nomes = ", ".join(_nome_na_troca(b) for b in exc.botoes)
    if exc.motivo == remap.MOTIVO_PS:
        return (f"não guardei: o PS não se troca, nem troca outro botão ({nomes})"
                " — os gestos desta aba começam nele, e ele é a saída de "
                "emergência.")
    if exc.motivo == remap.MOTIVO_FORA:
        return (f"não guardei: {nomes} — a direção dos analógicos e o clique do "
                "touchpad ficam fora da troca de botões.")
    return f"não guardei: a troca traz um botão desconhecido ({nomes})."


@gesto("06-navegacao.html", "linha-de-troca")
def linha_de_troca(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Ela trocou UMA linha da tela "Trocar os botões". NÃO grava nada."""
    botao = (str(o.get("linha") or "").strip()
             or str(o.get("campo") or "").removeprefix(PREFIXO_DA_TROCA))
    if botao not in acoes.BOTOES:
        raise ValueError(
            f"linha-de-troca: o clique não disse qual botão (veio {botao!r}). O "
            "`data-linha` de cada `<select>` é o id do botão, e ele vem do "
            "gerador.")
    rotulo = str(o.get("valor") or o.get("rotulo") or "").strip()
    destino = _destino_do_rotulo(rotulo)
    if destino is None and botao not in remap.REMAPEAVEIS:
        return None
    if destino is not None:
        try:
            remap.resolver({botao: destino})
        except remap.RemapeamentoRecusadoError as exc:
            raise RuntimeError(_frase_da_troca(exc)) from None
    campo = f"{PREFIXO_DA_TROCA}{botao}"
    do_perfil = _linhas_da_troca(perfil.ativo((ctx.state or {}).get("active_profile")))
    if do_perfil.get(campo) == rotulo:
        _TROCANDO.pop(campo, None)
    else:
        _TROCANDO[campo] = rotulo
    return {"mesa": {campo: rotulo}}


@gesto("06-navegacao.html", "fechar-troca")
def fechar_troca(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O fechar e o "Cancelar" da troca: LARGAM o que ela não guardou."""
    _TROCANDO.clear()
    return {"mesa": _linhas_da_troca(
        perfil.ativo((ctx.state or {}).get("active_profile")))}


@gesto("06-navegacao.html", "guardar-remapeamento", grava="gravar_e_reaplicar")
def guardar_remapeamento(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """"Guardar" da tela "Trocar os botões". Escreve `Profile.remapeamento`."""
    nome = _perfil_ativo_ou_recusa(ctx)
    forma = o.get("forma")
    if not isinstance(forma, dict) or not forma:
        raise RuntimeError(
            "não consegui ler as linhas da tela. O botão precisa do "
            "`data-hef-forma` para o piloto recolher os campos — se ele sumiu do "
            "desenho, o Guardar não tem o que gravar.")
    fora = tuple(b for b in acoes.BOTOES
                 if b in forma and b not in remap.REMAPEAVEIS
                 and str(forma[b] or "").strip() != SEM_TROCA)
    if fora:
        recusa = (remap.RemapeamentoRecusadoError(remap.MOTIVO_PS, (remap.BOTAO_PS,))
                  if remap.BOTAO_PS in fora
                  else remap.RemapeamentoRecusadoError(remap.MOTIVO_FORA, fora))
        raise RuntimeError(_frase_da_troca(recusa))
    declarado: dict[str, str] = {}
    for botao, rotulo in forma.items():
        if botao not in acoes.BOTOES:
            continue
        destino = _destino_do_rotulo(str(rotulo))
        if destino is not None:
            declarado[botao] = destino
    try:
        novo = remap.resolver(declarado) or None
    except remap.RemapeamentoRecusadoError as exc:
        raise RuntimeError(_frase_da_troca(exc)) from None

    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    atual = prof.remapeamento or None
    if atual == novo:
        _TROCANDO.clear()
        raise RuntimeError(
            f"não havia o que guardar — o perfil “{nome}” já troca exatamente o "
            "que a tabela mostra. Está guardado.")
    if novo is None and atual and not _TROCANDO:
        raise RuntimeError(
            f"não guardei: a tela está sem troca nenhuma e o perfil “{nome}” "
            f"guarda {len(atual)} troca(s) — gravar isto as apagaria. Espere a "
            "tabela se preencher e tente de novo.")
    perfil.gravar_e_reaplicar(prof.model_copy(update={"remapeamento": novo}), ctx, p)
    _TROCANDO.clear()


@gesto("06-navegacao.html", "padrao-remapeamento", grava="gravar_e_reaplicar")
def padrao_remapeamento(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Confirmar" do "Voltar ao padrão" da troca: `remapeamento = None`."""
    nome = _perfil_ativo_ou_recusa(ctx)
    loader = perfil._com_o_src()
    prof = loader.load_profile(nome)
    if not prof.remapeamento:
        _TROCANDO.clear()
        raise RuntimeError(
            f"não havia o que voltar — o perfil “{nome}” não troca botão "
            "nenhum. Não gravei nada e não incomodei o daemon.")
    perfil.gravar_e_reaplicar(prof.model_copy(update={"remapeamento": None}), ctx, p)
    _TROCANDO.clear()
    return {"mesa": _linhas_da_troca({})}


#: ERAM SEIS ATÉ 13/09/2026: `guardar-remapeamento` e `padrao-remapeamento`
#: `mouse.emulation.restore` NÃO virou botão, e a segunda leva reconfirmou a
SEM_GESTO: dict[str, str] = {
    # `modo-steam` SAIU DAQUI em 08/10/2026 (A-ABA-NAVEGACAO-FAZ-O-QUE-DIZ-E-O-MODO-
    # STEAM-NAVEGA-O-BIG-PICTURE-01): o `navegacao.big_picture.set` é o dono dele.
    # do `DEFAULT_BUTTON_BINDINGS`, e combo nenhum aparece lá.
    # de IPC nenhum escreve" o `ps_button_action`. Escreve — `daemon.reload`
    # `acao-do-gesto` SAIU DAQUI em 01/10/2026 (OS-GESTOS-DO-CONTROLE-01): a
    # `Profile.button_actions` nasceu, o
    # `core/acoes_de_botao` virou o dono do vocabulário e do padrão, e o device
    # (`Profile.button_actions`): seis das sete linhas são botões de
    # `guardar-remapeamento` e `padrao-remapeamento` SAÍRAM DAQUI em 13/09/2026
}


#: O `state_full` do daemon publica `active_profile` — o NOME — e mais nada do
#: conteúdo do perfil. Nem `button_actions` nem `key_bindings` aparecem entre as
#: `profile.switch` do `gravar_e_reaplicar`, e nenhum eco. Quem cobra são
#: `keyboard.emulation.set`, e `keyboard_emulation.enabled` VOLTA no
#: `state_full` — é o que pinta o `teclado-estado`. Declará-lo aqui calaria a
#: 13/09/2026. `guardar-remapeamento` e `padrao-remapeamento` gravam no perfil,
#: e o `state_full` não publica `remapeamento` (nem o mapa ativo, que mora no
SEM_ECO = ("guardar-definicoes", "padrao-definicoes",
           "linha-de-botao", "fechar-definicoes",
           "guardar-remapeamento", "padrao-remapeamento",
           "linha-de-troca", "fechar-troca")


PONTE = {"chamar", "machine_declare", "escolher_arquivo", "profile_reaplicar"}
#: O `desktop.status.set` é o «Status do Modo» desde 29/09/2026
METODOS = {"mouse.emulation.set", "keyboard.emulation.set", "desktop.status.set",
           "machine.declare", "navegacao.interna.set", "navegacao.big_picture.set"}


PAGINA = "06-navegacao.html"
PISO_DA_ABA = 8


def _prova(nome: str, clique: dict[str, Any], chama: list[Any]) -> dict[str, Any]:
    """Uma linha do `PROVAS`, para a chave da régua ser escrita UMA vez."""
    return {"pagina": PAGINA, "gesto": nome,  # (noqa-acento) chave do contrato
            "clique": clique, "chama": chama}


_MOUSE = "mouse.emulation.set"
PROVAS = [
    _prova("modo", {},
           [("resultado", ["desktop.status.set"],
             {"enabled": True, "origin": "manual"})]),
    _prova("navegacao-tipo", {"valor": ROTULOS_DO_TIPO[TIPO_COMPUTADOR]},
           [("resultado", ["navegacao.interna.set"],
             {"tipo": TIPO_COMPUTADOR, "origin": "manual"})]),
    _prova("modo-steam", {"valor": BIG_PICTURE_LIGADO},
           [("resultado", ["navegacao.big_picture.set"],
             {"ligado": True, "origin": "manual"})]),
    _prova("modo-steam", {"valor": BIG_PICTURE_DESLIGADO},
           [("resultado", ["navegacao.big_picture.set"],
             {"ligado": False, "origin": "manual"})]),
    _prova("vel-cursor", {"valor": "9"},
           [("resultado", [_MOUSE], {"speed": 9, "origin": "manual"})]),
    _prova("vel-cursor", {"valor": "99"},
           [("resultado", [_MOUSE],
             {"speed": MOUSE_SPEED_MAX, "origin": "manual"})]),
    _prova("vel-rolagem", {"valor": "4"},
           [("resultado", [_MOUSE], {"scroll_speed": 4, "origin": "manual"})]),
    _prova("vel-rolagem", {"valor": "0"},
           [("resultado", [_MOUSE],
             {"scroll_speed": SCROLL_SPEED_MIN, "origin": "manual"})]),
    _prova("teclado", {"valor": TECLADO_SO_FORA},
           [("resultado", ["keyboard.emulation.set"], {"enabled": True})]),
    _prova("teclado", {"valor": TECLADO_DESATIVADO},
           [("resultado", ["keyboard.emulation.set"], {"enabled": False})]),
    _prova("acao-do-gesto", {"linha": "ps_l3", "rotulo": "— Nada —", "valor": "— Nada —"},
           [("machine_declare", [{"gestos": {"ps_l3": {"faz": "nada"}}}], {})]),
]


PREFIXO_DO_GESTO = "faz-"
PREFIXO_DO_SCRIPT = "script-"
ENDERECO_DA_DICA_DOS_GESTOS = "gestos-dica"
TITULO_DO_SELETOR_DO_SCRIPT = "Escolher um script"
FILTRO_DO_SCRIPT = "*.sh"

_A_MAQUINA: Any = None
_SELO_DA_MAQUINA: Any = None


def _selo_da_maquina() -> tuple[int, int, int] | None:
    """`(inode, mtime_ns, tamanho)` do `maquina.json`: a mesma regra da 08."""
    try:
        perfil._com_o_src()
        from hefesto_dualsense4unix.utils.maquina import caminho_da_maquina

        st = caminho_da_maquina().stat()
    except Exception:
        return None
    return (st.st_ino, st.st_mtime_ns, st.st_size)


def _a_maquina() -> Any:
    """O `maquina.json` validado, RELIDO QUANDO O ARQUIVO MUDA (um `stat` por tique)."""
    global _A_MAQUINA, _SELO_DA_MAQUINA
    selo = _selo_da_maquina()
    if _A_MAQUINA is None or selo != _SELO_DA_MAQUINA:
        try:
            perfil._com_o_src()
            from hefesto_dualsense4unix.utils.maquina import carregar_maquina

            _A_MAQUINA, _SELO_DA_MAQUINA = carregar_maquina(), selo
        except Exception:
            return None
    return _A_MAQUINA


def _a_dica_dos_gestos(escolhas: dict[str, Any]) -> str:
    """O que a dica da tabela diz sobre a escolha de hoje, ou o «nada a dizer»."""
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    frases = [f"Nenhum gesto faz <b>{ag.rotulo(t)}</b>, uma das saídas de emergência."
              for t in ag.saidas_sem_gesto(escolhas)]
    if any(e.faz == ag.PARAR_O_SERVICO for e in escolhas.values()):
        frases.append("<b>Parar o serviço</b> não volta pelo controle: a volta é "
                      "pela bandeja ou pela aba Sistema.")
    return "<br><br>".join(frases) if frases else NADA_A_DIZER


def _o_que_os_gestos_fazem() -> dict[str, str]:
    """As seis listas da tabela, a opção do script de cada uma, e a dica viva."""
    perfil._com_o_src()
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    escolhas = ag.tabela(_a_maquina())
    fora: dict[str, str] = {}
    for chave, escolha in escolhas.items():
        fora[PREFIXO_DO_SCRIPT + chave] = (
            ag.nome_do_script(escolha.script) if escolha.faz == ag.SCRIPT and escolha.script
            else ag.rotulo(ag.SCRIPT))
        fora[PREFIXO_DO_GESTO + chave] = ag.rotulo_da_escolha(escolha)
    fora[ENDERECO_DA_DICA_DOS_GESTOS] = _a_dica_dos_gestos(escolhas)
    return fora


def _ok_e_motivo(resposta: Any) -> tuple[bool, str | None]:
    """`(ok, motivo)`, seja tupla ou `bool` o que a ponte devolveu (a régua usa `bool`)."""
    if isinstance(resposta, tuple) and len(resposta) == 2:
        return bool(resposta[0]), resposta[1]
    return bool(resposta), None


@gesto("06-navegacao.html", "acao-do-gesto", grava="machine_declare")
def acao_do_gesto(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """Uma das seis listas da tabela: grava na MÁQUINA o que o gesto faz.

    `data-linha` diz qual gesto (chaves de `acoes_do_gesto.GESTOS`); a página publicada antes desta
    sprint não o tem, e o clique recusa como antes. O rótulo vira token pelo dono do vocabulário.
    «Escolher um script…» (ou o nome de um já escolhido) abre o seletor do sistema
    (`D-2909-O-SCRIPT-E-UM-ARQUIVO-ESCOLHIDO`): cancelar não grava e a pintura devolve a lista ao
    que era; o arquivo é conferido aqui (`conferir_o_script`) e de novo pelo daemon na hora de
    rodar. A recusa pisca na lista e a frase vai ao diário.
    """
    global _A_MAQUINA
    perfil._com_o_src()
    import os

    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    qual = str(o.get("linha") or "").strip()
    if qual not in ag.GESTOS:
        raise ValueError(f"a lista não disse de qual gesto ela é ({qual!r})")
    texto = str(o.get("rotulo") or o.get("valor") or "").strip()
    faz = ag.token_do_rotulo(texto)
    if faz is None or faz == ag.SCRIPT:
        caminho = p.escolher_arquivo(TITULO_DO_SELETOR_DO_SCRIPT, padrao=FILTRO_DO_SCRIPT)
        if not caminho:
            return None
        real = os.path.realpath(str(caminho))
        motivo = ag.conferir_o_script(real)
        if motivo is not None:
            raise RuntimeError(f"Não dá para usar {ag.nome_do_script(real)}: {motivo}.")
        declarado: dict[str, Any] = {"faz": ag.SCRIPT, "script": real}
    else:
        declarado = {"faz": faz}
    ok, motivo_da_recusa = _ok_e_motivo(p.machine_declare({"gestos": {qual: declarado}}))
    if not ok:
        raise RuntimeError(motivo_da_recusa or "Não consegui guardar o que o gesto faz.")
    _A_MAQUINA = None
    return None
