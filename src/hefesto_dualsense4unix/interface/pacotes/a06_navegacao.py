#!/usr/bin/env python3
"""O pacote da aba `06` Navegação.

O QUE TEM DONO: quem é o PRIMÁRIO (`is_primary`) — e é ele quem navega o PC.
O daemon marca um controle como primário, e a tela já dizia isso à mão: o
`NAVEGA` do gerador tirava o MENOR número da mesa, que acerta por coincidência
enquanto o P1 estiver na frente. Agora sai do daemon.

OS SEIS GESTOS (PS+Options, PS+↑…) TÊM DONO DESDE 01/10/2026: a tabela mora no
`maquina.json` (`core/acoes_do_gesto.tabela`), o daemon despacha por ela e a
lista da tela grava e pinta por ela — ver `acao_do_gesto`, no fim do módulo
(OS-GESTOS-DO-CONTROLE-FAZEM-O-QUE-DIZEM-01).

FATO SUBSTITUÍDO (06/09/2026): esta linha dizia que o `ps_button_action` da
config é *"o único pedaço ajustável"* e que *"método de IPC nenhum escreve"*.
As duas metades caíram. **Escreve** — `daemon.reload` aceita `config_overrides`
com qualquer campo do `DaemonConfig` (`ipc_handlers.py:4542`, a leitura dos
overrides) e aplica com `replace(config, **overrides)` + `reload_config`
(`:4553-4554`); o que ele NÃO faz é gravar em disco, então a escolha morre no
próximo start do daemon. E **deixou de ser o único ajustável**: desde a
ONDA5-06-01 o toque solo no PS tem dono no PERFIL
(`Profile.button_actions["ps"]`), que VENCE o degrau da máquina — a precedência
está em tabela em `hotkey._a_metade_da_maquina`. Os números antigos (`:4556` /
`:4567`) apontavam para o cache de órfãos HID quando foram remedidos.

O QUE O ESTADO AINDA NÃO TRAZ: o `ps_button_action`. Ele viaja só na resposta de
`daemon.reload` (`_config_que_viaja`), nunca no estado do tique — e é por isso
que a tira desta aba não NOMEIA o ato da máquina. Ver `_o_que_o_ps_faz`.

FATO SUBSTITUÍDO (01/09/2026, segunda leva): esta linha dizia que os cinco
gestos "moram no PERFIL". Não moram — o perfil guarda `key_bindings`, que são
os BOTÕES (options, create, l1, r1, l3, r3 e as três regiões do touchpad), e
combo nenhum. A frase sobre as velocidades de cursor e rolagem, que estava na
mesma linha, já tinha caído na primeira leva (ver o `SEM_DONO` logo abaixo).

OS VINTE E OITO INDECIDÍVEIS DESTA ABA ESTÃO DECIDIDOS — 02/09/2026, à tarde.
A `--prova-de-mockup` classificava 28 dos 29 campos como INDECIDÍVEL: o valor que
o produto pinta COINCIDE com o que o desenho cravou, e ler a tela não separa
"pintou igual" de "não pintou". Era a maior concentração da casa. A cura foi
fazer o valor MUDAR — um DUBLÊ no lugar do daemon (três controles sintéticos,
`speed=11`, `scroll_speed=4`, teclado desligado, e um `button_actions` que troca
as 21 linhas) — e ver se a tela acompanha:

    bancada (2 controles)   produto  1 · mockup 0 · indecidível 28
    DUBLÊ                     produto 29 · mockup 0 · indecidível  0

**Os 29 endereços desta aba estão vivos.** Nenhum é endereço morto, e nenhum
campo depende do desenho. A régua que reproduz isso sem abrir janela é
`tests/unit/test_a_06_o_duble_decide_o_indecidivel.py`.

A PINTURA DESFAZIA A ESCOLHA DE QUEM CLICA — CURADO EM 02/09/2026, por decisão
de produto. O defeito estava medido com dublê, escolhendo uma opção como uma pessoa
escolheria (evento `change`):

    ANTES  (o que a pintura pôs) : Botão direito
    CLIQUE (a escolha do usuário)      : F11
    +100 ms                      : F11
    +1500 ms                     : Botão direito

Eram DUAS causas, e as duas eram desta aba: os 21 `<select>` não casavam com
nenhum endereço clicável do ouvinte (`hefesto_vivo.py:189`, o `closest` de
`manda_do_alvo`) — logo a escolha não chegava ao Python —, e o tique seguinte
reescrevia o valor do perfil por cima. Enquanto isso valeu, **o "Guardar" nunca
recebeu uma forma diferente do perfil**, e a recusa dele mandava trocar a linha
antes de clicar, um caminho que este mesmo arquivo declarava não existir.

A cura é a decisão de produto: *"as 21 listas param de ser repintadas enquanto ela
está mexendo, até guardar ou sair"*. O gerador passou a marcar as 21 linhas com
`data-gesto` (`aba06.LINHA_DE_BOTAO`), o gesto `linha-de-botao` anota a escolha
em `_MEXENDO`, e a pintura passa a CONCORDAR com a tela em vez de reescrevê-la.
Ver `_o_que_a_tabela_mostra`.

O QUE SOBRA PARA O PILOTO, e continua relatado: a mesma forma de defeito vale
para TODA lista e TODO campo digitável das outras abas (o editor da Perfis, os
`<select>` da Conexões). A cura geral é o `escrever()` não sobrepor campo que a
pessoa está editando; a daqui resolve esta aba com o vocabulário que o piloto já
tem, sem tocar arquivo de fora.

FATO SUBSTITUÍDO — 02/09/2026, corretivo. Aqui estava escrito que **a frase de
recusa NÃO CHEGA À TELA DO USUÁRIO**, e que toda frase deste arquivo era escrita para
um dia futuro. **Isso caducou no mesmo dia:** o piloto ganhou
`_recusou_dizendo` (`hefesto_vivo.py:2786`), e o `except` de `trabalhar()` põe a
frase no cartão pelo `idle_add`, na hora do clique e não no tique seguinte.

O QUE MUDOU EM 13/09/2026 (FRASES-E-DICAS-01): **nenhuma frase de recusa fala
com ela na tela.** `RuntimeError` e `ValueError` vão ao mesmo diário, e o botão
pisca `hef-recusou`; o `desfechos` guarda a classe da exceção para o relato. A
distinção entre *clique inválido* e *o produto recusou* continua valendo para
quem lê o diário, e uma opção de VERDADE que caia em `ValueError` segue sendo
defeito: ela pisca a recusa para uma escolha que devia valer, que é o que este
corretivo fechou.

OS DOIS `return` MUDOS MORRERAM — 02/09/2026, corretivo. O "Guardar" e o "Voltar
ao padrão" saíam sem gravar, sem chamar e **sem uma palavra** quando não havia o
que fazer. No "Guardar" isso era cruel: a trava contra o apagador manda *"espere
a tabela se preencher e clique de novo"*, e o segundo clique caía exatamente
nesse `return`. Uma recusa que instrui a repetir o gesto e depois não responde
nada promete que a segunda tentativa funciona. Os dois passaram a RECUSAR
DIZENDO — ver `guardar_definicoes` e `padrao_definicoes`.

A "FUNÇÃO DO TECLADO" TEM TRÊS OPÇÕES — decisão, 02/09/2026: *"`Só dentro
do jogo` · `Só fora do jogo` · `Desativado`. O padrão de um perfil novo é `Só
fora do jogo` — no jogo o L3 é o clique do analógico e o teclado atrapalha; no
desktop é onde ele serve."* Duas têm dono e uma recusa dizendo; **qual é qual
está invertido em tudo o que esta casa escreveu até hoje**, e a medição está no
corpo de `teclado()`. O padrão de PERFIL NOVO não é desta aba — é do esquema, e
está no relato.

E ELA FALA A LÍNGUA DA PÁGINA CARREGADA — 02/09/2026, corretivo, e é a
armadilha que esta casa paga toda vez que mexe na bancada. **Os geradores
escrevem em `mockup/`; o produto lê `interface/paginas/`, e só recebe quando ela
publica.** Trocar as três palavras na bancada e falar só elas fez duas coisas ao
mesmo tempo, medidas contra a página que o produto renderiza:

* das TRÊS opções que a tela do usuário oferece, DUAS viraram clique morto — e uma
  delas era a única forma de desligar o teclado por esta aba. Morto **e mudo,
  por contrato**: `_recusou_dizendo` (`hefesto_vivo.py:2786`) levava à tela a
  frase do `RuntimeError` e NÃO a do `ValueError`, porque clique-inválido fala
  com quem programa. Transformar uma opção de verdade em clique-inválido é
  justamente pedir esse silêncio para o clique do usuário;
* com o teclado desligado, a linha passou a AFIRMAR `Ligada — atalhos e teclado
  na tela`, porque o `escrever()` descarta em silêncio o texto que não casa com
  nenhuma `<option>` e o que fica é a que o desenho crava.

A cura foram duas linhas de vocabulário, e as duas tinham prazo: **ela publicou
a 06, e em 03/09/2026 os sinônimos saíram** — a régua da travessia
(`test_os_sinonimos_da_travessia_tem_prazo`) ficou vermelha nomeando o que
apagar, que é o único trabalho que ela tinha. Ficou `PALAVRAS_DO_TECLADO`, que
continua conferindo a palavra contra a página CARREGADA. **A regra que fica:
mudar rótulo, opção ou número de casas na bancada obriga a perguntar o que
acontece na tela do usuário HOJE.**

FATO SUBSTITUÍDO (02/09/2026): **"esta aba MENCIONA 7 campos e PINTA 3"** —
escrito a partir do `--passear`, que imprime `06-navegacao.html  1  3`. Ela
pinta os OITO elementos endereçados. O `3` é contagem de MUDANÇA: o `escrever()`
do piloto devolve `1` só quando o valor novo difere do que a tela já mostra, e
cinco dos oito já coincidiam com o daemon do usuário (`2 controles:`, `1 USB · 1 BT`,
`6`, `1`, `Ligada — atalhos e teclado na tela`). Ler "mudança" como "pintura" é
a mesma confusão entre a PALAVRA e o ATO que produziu o "77%" falso, com o sinal
trocado — e aqui ela escondia os defeitos REAIS da aba, que a medição achou:
metade da linha do cartão indo para a tela (`_linha_do_cartao`), 8 chaves de 14
emitidas para o vazio (`SEM_ENDERECO`) e um "Guardar" que apagava o perfil
(`guardar_definicoes`).
"""
from __future__ import annotations

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

#: rolagem "mora no perfil, não no state_full". **O daemon publica as duas**, em
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

PALAVRAS_DO_TECLADO: dict[bool, tuple[str, ...]] = {
    True: (TECLADO_SO_FORA,),
    False: (TECLADO_DESATIVADO,),
}

PONTO = ' <span class="pt">•</span> '

BOLINHA = '<span class="bolinha"></span>'

PAPEL_QUE_NAVEGA = "Navega o PC"
PAPEL_SO_A_JANELA = "Só a janela"
PAPEL_DO_CURSOR = "Move o cursor"

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
    "D-pad Cima": "dpad_up",
    "D-pad Direita": "dpad_right",
    "D-pad Baixo": "dpad_down",
    "D-pad Esquerda": "dpad_left",
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

    `publicado=True` É DELIBERADO, e é a mesma exceção que
    `a03_gatilhos._pagina_publicada` documenta: o padrão de `onde.pagina` é a
    BANCADA porque todo instrumento desta casa mede o desenho de hoje. Aqui
    não — quem pinta pinta no que está no `WebView`, e o piloto abre SEMPRE o
    publicado (`hefesto_vivo.py:758, 1418, 1458, 1646, 1818`).

    LÊ UMA VEZ POR VERSÃO DO ARQUIVO, e o selo é `(mtime_ns, tamanho)`: a
    página tem 385 KB e a pintura roda a cada 100 ms — reler a cada tique seria
    3,8 MB/s por uma resposta que só muda quando ela publica.

    `frozenset()` quando o arquivo não abre. Aí `_o_teclado_em_palavras` cai na
    profissão de fé — a palavra de produto —, que é o destino: um produto instalado
    sem a página é um produto que não tem tela nenhuma para mentir.

    A JANELA QUE ISTO NÃO FECHA, e ela é estreita: publicar com o aplicativo
    ABERTO e sem trocar de aba. O arquivo muda, o selo muda, o pacote passa a
    emitir a palavra nova — e o DOM carregado ainda é o antigo, então a escrita
    volta a ser descartada até o próximo carregamento. Trocar de aba já
    recarrega (`hefesto_vivo.Piloto._ir`), e reabrir também. Ler o DOM em vez do
    arquivo exigiria uma pergunta ao piloto que o `Contexto` não tem.
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


def _o_teclado_em_palavras(ligado: bool) -> str:
    """A palavra daquele estado que a página CARREGADA sabe receber."""
    candidatas = PALAVRAS_DO_TECLADO[ligado]
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
    """A linha "o mouse virtual está pronto?" — a MESMA hierarquia da GTK.

    O DONO É `app/actions/mouse_actions._refresh_mouse_view`, e o que se copia
    dele é a ORDEM, não a frase: a frase do bloqueio vem inteira da tabela
    `BLOQUEIO_DO_MOUSE_EM_PORTUGUES`, que é importada. A hierarquia da GTK, no
    corpo dela, é: *device no ar segundo o daemon → pronto; senão, o motivo*.

    **A SONDA LOCAL NÃO VEM JUNTO, e é decisão medida.** A GTK ainda faz
    `import uinput` + `os.access("/dev/uinput")` dentro do processo da JANELA, e
    o próprio docstring dela diz que isso *"erra nos dois sentidos"* — num
    Flatpak a janela olha o sandbox e grita "sem permissão" sobre um nó que o
    daemon abre sem dificuldade. O primeiro ramo dela, o que o `_anotar_mouse_
    virtual` criou em 25/08, é justamente o que dispensa a sonda: **quem abre o
    device é o daemon, e a resposta vem de quem executa.** Aqui só existe esse
    ramo, o que torna esta linha mais confiável que a da GTK, não menos.

    Vazia quando o daemon não respondeu, ou quando ele diz `desligada` — que é
    escolha do usuário, não defeito, e é o que o `_anotar_mouse_virtual` classifica
    como "não sei" para não mandá-la consertar um interruptor que ela baixou.
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
        # é feio e é honesto — a GTK faz o mesmo em `frase_da_recusa_do_mouse`.
        motivo = f"o Hefesto está bloqueando o mouse (motivo: {bloqueio})"
    motivo = motivo.replace("{gesto}", como_atualizar_esta_instalacao())
    return f'<span class="laranja">O cursor não anda: {motivo}.</span>'


def _o_teclado_em_uma_linha(tecla: dict[str, Any]) -> str:
    """"Ligado, em pausa agora: …" — o ESTADO do teclado, e ele é do produto.

    Chamada direta de `app/actions/emulation_actions.descrever_teclado_emulado`,
    que é pura *"de propósito: é o miolo que decide o que ela vê"*. Ela devolve
    `(posição, frase)`; a posição já está na lista "Função do teclado", e o que
    faltava nesta tela era a FRASE.

    O que ela responde e a lista sozinha não: a diferença entre *desligado por
    você* e *ligado e calado agora porque um jogo assumiu*. Sem ela, com o
    teclado suspenso pelo modo jogo, a tela continua dizendo "Só fora do jogo" —
    verdade sobre a configuração, e não sobre o que está acontecendo.

    Sem o bloco a frase é a de "não sei" da própria GTK, e é a coisa certa a
    dizer: `TECLADO_SEM_ESTADO` fala do Hefesto, não do teclado.
    """
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        descrever_teclado_emulado,
    )

    _posicao, frase = descrever_teclado_emulado(tecla or None)
    return f'<span class="laranja">{frase}</span>' if frase else NADA_A_DIZER


def _o_teclado_na_tela_em_uma_linha(tecla: dict[str, Any]) -> str:
    """"Neste computador: o teclado na tela está instalado — o L3 abre."

    Chamada direta de `app/actions/input_actions.frase_do_teclado_na_tela`, que
    já é TRI-ESTADO: `None` devolve `""` — não afirma sobre uma máquina que
    ninguém olhou. É a frase que decide se existe ALGUM caminho para escrever
    texto com o controle, porque nenhum atalho de fábrica digita letra.

    A dica desta aba manda abrir o teclado na tela com o L3 e nunca disse se há
    um instalado; numa máquina sem `wvkbd-mobintl`/`onboard` a tela prometia o
    que não entrega, e a GTK avisava.
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
    """"Com o teclado desativado saem também …" — e só enquanto ele estiver.

    TRI-ESTADO como as outras três linhas: sem o bloco `keyboard_emulation` a
    linha não afirma nada, porque ninguém perguntou ao Hefesto. Ligado, também
    não há o que dizer — o custo é o de DESLIGAR.

    ELA NÃO SUBSTITUI O `teclado-bloqueio`, e as duas convivem de propósito:
    aquela diz *o teclado está ligado e calado agora porque um jogo assumiu*;
    esta diz *você o desligou, e isto saiu junto*. São o presente e a escolha.
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
    """A linha da D3 — e só quando há mais de um controle a ressalvar (D-02).

    *"Linha fixa só quando HÁ ressalva."* Com UM controle ligado não há
    promessa quebrada: o ajuste global É o ajuste daquele controle, e a frase
    ocuparia uma linha da tela para dizer uma verdade sem consequência. Com
    DOIS, a fileira de cartões em cima passa a oferecer uma escolha que estas
    sete linhas não honram — e é aí que a ressalva tem o que ressalvar.

    O NÚMERO SAI DE `conectados`, NUNCA DA MESA DO DESENHO: a mesa tem quatro
    lugares sempre, dois deles vazios no mockup, e contá-la faria a frase nascer
    numa tela com um controle só. *"Toda frase que promete alcance conta os
    CONECTADOS"* — a regra é do `Contexto`, e o defeito de nomear um controle
    que não está apareceu quatro vezes em 31/08.
    """
    return RESSALVA_DOS_GLOBAIS if len(ctx.conectados) > 1 else NADA_A_DIZER


#:
RAZAO_DO_PORTAO = (
    "O mouse e o teclado só se ligam fora do jogo — ligar agora derrubaria o "
    "controle no meio da partida. O Modo se troca na aba Jogar.")


def _a_razao_do_portao(estado: dict[str, Any]) -> str:
    """Por que o "Status do Modo" vai recusar agora — ou nada a dizer."""
    if not estado:
        return NADA_A_DIZER
    if mode_of_state(estado) == MODE_DESKTOP:
        return NADA_A_DIZER
    return f'<span class="laranja">{RAZAO_DO_PORTAO}</span>'


def _nome_do_botao(botao: str) -> str:
    """`"l2"` → `"L2 (gatilho esquerdo)"`. O nome que ELA lê, e é do MOTOR.

    NÃO SE ESCREVE A TABELA AQUI. `app/actions/input_actions.humanize_button`
    (`:181`) é dona dos vinte nomes desde o KBD-01, e a GTK que ela usa mostra
    exatamente estes. As duas frases de recusa do "Guardar" mandavam o id cru
    para a tela — ela lia *"estas linhas ficaram sem quem as atenda:
    touchpad_left_press"*, que é jargão de kernel na cara de quem clicou.

    FATO SUBSTITUÍDO — 02/09/2026, corretivo. Este parágrafo citava TRÊS ids
    como curados: `l2`, `touchpad_left_press` e `r3_direcao`. **Os dois eixos
    continuam crus**, e a medição é de um comando:

        _nome_do_botao('l2')                  → 'L2 (gatilho esquerdo)'
        _nome_do_botao('touchpad_left_press') → 'Touchpad — lado esquerdo'
        _nome_do_botao('r3_direcao')          → 'r3_direcao'
        _nome_do_botao('l3_direcao')          → 'l3_direcao'

    São 22 botões em `acoes.BOTOES` e 20 nomes em `_BUTTON_LABELS`, e os dois
    que faltam são a DIREÇÃO dos analógicos. A cura mora no MOTOR
    (`app/actions/input_actions.py:85`), não aqui — copiar duas linhas para
    dentro deste arquivo criaria a segunda tabela que o
    `test_o_nome_do_botao_e_o_do_motor_e_nao_uma_segunda_tabela` existe para
    impedir, e a tela passaria a chamar o mesmo botão por dois nomes.

    O DANO HOJE É DE FORMA, e por isso não se força a cura: `acoes.resolver()`
    (`core/acoes_de_botao.resolver`) pula os eixos, então eles nunca chegam ao
    `sem_dono` — medido, trocando o `cross`: `sem_dono == ['l2']`. O único
    caminho que ainda os exporia é o `nao_reconhecidas` do "Guardar", que exige
    a tela oferecer um rótulo que o produto não conhece.

    O IMPORT É TARDIO, E É POR ISSO: `input_actions` puxa GTK no topo (e
    `mouse_actions` junto). Os pacotes são puros de propósito — importáveis sem
    janela, testáveis sem display —, e um import no topo deste arquivo faria a
    aba inteira depender da camada da janela ANTIGA para escrever um rótulo.
    Aqui ele custa uma vez, no caminho da recusa, que não é o do tique.

    E ELE CAI DE PÉ: sem GTK no ambiente, o id cru volta. Um rótulo bonito não
    vale derrubar a aba — o cru é feio e é honesto, que é a mesma escolha do
    `acoes.rotulo()` para um token sem nome.
    """
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_button
    except Exception:
        return botao
    return humanize_button(botao)


# telas de botões, os dois `--plastico` das bordas e os chips da fita. Todos
# `a04_iluminacao.um_botao_de_player`: o gerador `aba06.py` as chama para

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
        # dela não têm hexa amostrado e devolvem `url(#hachura-sem-hex)`, que
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

    ELA É O CINTO, E O ALVO `atributo` É O SUSPENSÓRIO — 03/09/2026. Desde que
    o piloto ganhou o alvo `atributo`, o `data-colorway` de cada `<svg>` é um
    campo (ver `colorway_do_aparelho`) e a página publica os 28 modelos: com o
    alvo em voo, esta folha escreve as MESMAS variáveis que a regra já traz.
    Ela fica porque é o que pinta o casco numa árvore em que o alvo ainda não
    chegou — e sai no dia em que ele estiver no `dev` e provado na tela.

    POR QUE UMA FOLHA, e não um campo: o casco do desenho não é `style` de
    elemento — as peças do SVG leem `var(--z-casca)`, escrita por uma regra
    `svg[data-colorway="…"]`. O piloto escreve texto, valor, classe, cor,
    largura, fundo, `innerHTML` e atributo, e **nenhum deles alcança uma
    variável CSS de um elemento**. Reescrever o SVG inteiro pelo `innerHTML`
    custaria 370 linhas por cartão a cada meio segundo — e nunca sossegaria: o
    navegador NORMALIZA marcação, então a comparação do `escrever()` acusaria
    mudança em todo tique, para sempre. O `innerHTML` de um `<style>` é TEXTO,
    e texto volta como foi escrito.

    A especificidade é o que faz esta folha vencer a de dentro do SVG:
    `.nav-ctl[data-controle="p1"] .ds-svg` (0,3,0) contra
    `svg[data-colorway="cosmic-red"]` (0,1,1).

    SEM LEITURA, O CASCO FICA NEUTRO — e é a regra de produto. Um controle no rádio
    hoje não entrega a cor; deixá-lo com o casco do mockup seria a tela
    afirmando um aparelho que não está na mesa. As zonas que não são identidade
    ficam como estão: pintá-las apagaria o desenho em vez de calar a cor.

    :param caixa: o seletor da CAIXA de um lugar da mesa, que muda de aba para
        aba — `.nav-ctl` aqui, `.ctrl` na Iluminação. Ele ganhou parâmetro em
        03/09/2026, quando a aba 04 precisou da mesma folha: o desenho GRANDE
        dela continuava com o Cosmic Red e o Starlight Blue do mockup embaixo de
        um rótulo que já dizia `P1 • White • USB` — medido nos pixels da tela
        do usuário, `rgb(174,51,90)` no corpo contra `rgb(228,224,216)` na moldura da
        MESMA célula. Duas cópias desta função divergiriam no primeiro modelo
        novo; um parâmetro não.

        **O seletor precisa vencer o `svg[data-colorway="…"]` de dentro do
        SVG** (0,1,1). `.nav-ctl[data-controle="p1"] .ds-svg` e
        `.ctrl[data-controle="p1"] .ds-svg` valem os dois (0,3,0).
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

    O DEFEITO, MEDIDO NO PRODUTO EM 03/09/2026, com UM controle no cabo e a aba
    Navegação aberta no WebKit — os quatro cartões, lidos pelo DOM vivo::

        P1 • White         casco rgb(68, 71, 90)     lightbar rgb(0, 0, 255)
        P2 • —             casco rgb(126, 184, 212)  lightbar rgb(255, 0, 0)
        P3 • Desconectado  casco rgb(83, 87, 111)    lightbar rgb(83, 87, 111)
        P4 • Desconectado  casco rgb(83, 87, 111)    lightbar rgb(83, 87, 111)

    `rgb(126, 184, 212)` é `#7eb8d4`, o **Starlight Blue do mockup**, e
    `rgb(255, 0, 0)` é o `style="--luz:#ff0000"` que o `monta.svg()` cravou no
    `<g id="p2-lightbar">`. Num lugar onde NÃO HÁ CONTROLE, o cartão saía mais
    colorido — e mais aceso — que o do único controle de verdade na mesa.

    POR QUE O P3 E O P4 ESCAPARAM, e é o que nomeia a causa: eles nascem
    `class="nav-ctl vazia"` no HTML, e a folha do desenho já sabe desenhar um
    lugar vazio (`.nav-ctl.vazia .ds-svg …{fill:var(--linha)!important}`). O P2
    nasce OCUPADO e fica vazio em tempo de execução — e quem o esvazia
    (`pacotes.apagar_os_lugares_sem_dono` + o passo `vazios` do piloto) escreve
    a classe **`off`**, que folha de estilo nenhuma menciona. As duas palavras
    para o mesmo estado nunca se encontraram, e o desenho do mockup ficou.

    É A MESMA LEI DA `folha_do_plastico`, aplicada onde ela estava calada: um
    lugar SEM DONO é, com mais razão que um lugar sem leitura de cor, um lugar
    sobre o qual a tela não tem o que afirmar. O neutro é o `var(--linha)` do
    próprio desenho — o mesmo que o `.vazia` usa —, e não um cinza digitado
    aqui.

    O `!important` NÃO É ZELO: a `--luz` chega como `style="--luz:#ff0000"` no
    próprio elemento (`monta.py:790`), e estilo de linha vence qualquer regra
    de folha que não o traga.
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

    É SÓ A FORMA, e é de propósito: quem responde *"qual número"* é
    `pacotes.jogador_de` e quem responde *"qual nome"* é
    `pacotes.identidade_de`, os dois donos que a ROTA-A deixou prontos. O
    gerador chama esta função com a mesa do desenho e o pacote com a mesa viva
    — uma escrita só para as duas, que é o que impede o desenho e o produto de
    divergirem calados.

    Cada pedaço que não se sabe simplesmente NÃO ENTRA: sem primário na mesa a
    frase da dica termina em "o **.**", que é feio e é verdadeiro. Inventar um
    número aqui seria repetir o defeito que a ROTA-A mediu — o mesmo controle
    mudando de nome quando o segundo entra na mesa.
    """
    if nome == NOME_SEM_LEITURA:
        nome = SEM_LEITURA
    partes = [f"P{numero}" if numero else "", nome, via]
    return " ".join(p for p in partes if p)


def chips_da_fita(mesa: list[dict[str, Any]]) -> str:
    """Os chips da fita do topo, para a `06`, com os controles da MESA.

    POR QUE ESTA ABA TEM OS SEUS, e não os de `monta.fita()`: a fita é de todas
    as dez e o piloto a troca INTEIRA (`hefesto_vivo._fita`) — mas `_fita`
    **desiste** quando um controle da mesa não tem cor (`if not mesa or any(not
    c.get("cor") …): return ""`), e pelo rádio a cor não se lê. Medido em
    03/09/2026, com os dois controles do usuário na mesa e o daemon no ar: a fita da
    `06` mostrava `P1 · Cosmic Red · USB` e `P2 · Starlight Blue · BT`, os dois
    do mockup, ao lado de um cabeçalho que já contava certo. Treze tiques, uma
    pintura.

    Este endereço é o que salva a fita **no caso em que o dono dela desiste**.
    Quando `_fita` responde, ele troca o bloco antes desta escrita (a fita é o
    primeiro passo do `pintar`), e o que fica na tela é o dele — que também é
    lido do aparelho. Os dois dizem a mesma coisa; um deles diz sempre.

    SEM `--plastico`, e o desenho não muda: nesta aba a fita nasce `inerte`
    (fora de `monta.ABAS_QUE_ESCOLHEM`), e `.fita.inerte .chip.plastico` já
    sobrepõe a borda com
    `var(--border-sutil)`. O hex do plástico ali nunca pintou um pixel — era só
    identidade congelada esperando alguém acreditar nela.
    """
    monta = _monta()
    mostra_todos, escolhido = monta.escolha_da_fita("todos", mesa)
    chips = [f"<span>{monta.ROTULO_DA_FITA}</span>"]
    if mostra_todos:
        chips.append('<label class="chip on">Todos</label>')
    for lugar in mesa:
        nome = str(lugar.get("nome") or "")
        if nome == NOME_SEM_LEITURA:
            nome = SEM_LEITURA
        partes = [f'P{lugar["jogador"]}' if lugar.get("jogador") else "",
                  nome, str(lugar.get("via") or "")]
        rotulo = monta.SEPARADOR.join(p for p in partes if p)
        aceso = " on" if str(lugar.get("pref") or "") == escolhido else ""
        chips.append(f'<label class="chip plastico{aceso}"'
                     ' title="a borda é a cor do plástico">'
                     f"{rotulo}</label>")
    return "".join(chips)


def _linha_do_cartao(c: dict[str, Any], primario: bool, cursor: bool = False) -> str:
    """A linha inteira do cartão: `"BT • Navega o PC"`."""
    return linha_do_cartao(str(c.get("via") or ""), primario, cursor)


def move_o_cursor(dele: dict[str, Any], ctx: Contexto, primario: bool) -> bool:
    """Este controle, que NÃO navega o PC, move o cursor agora pelo giro?

    A-MIRA-NA-NAVEGACAO-02, 25/09/2026, por delegação de produto. É o que o daemon
    faz, e não uma frase nova: na Navegação o `mouse.mover_o_cursor_pelo_giro`
    leva ao cursor o giro de TODA peça com a Mira acesa, e o cartão dizia «Só
    a janela» sobre um controle que movia o cursor da máquina.

    AS CINCO PERGUNTAS, e cada uma é a do dono da resposta:

    1. **não é quem navega** — o primário já diz «Navega o PC», que cobre o
       giro dele;
    2. **a Mira dele está acesa** — o bloco `mira` do daemon, lido pelo mesmo
       leitor do chip da aba Controles (`a02_controles._mira_ligada`). Sem
       leitura é não: afirmação sem leitura é chute;
    3. **o modo vivo é a Navegação** — pelo mesmo leitor da dica do Giroscópio
       (`a02_controles._na_navegacao`, que é o `mode_of_state`). No Virtual e
       no Xbox a Mira vai ao analógico direito do controle virtual, e no
       Nativo ela não anda: o cursor da máquina fica onde está;
    4. **o giroscópio dele chega** — o interruptor que ela liga e desliga no
       chip Giroscópio (`sensores.giroscopio_ligado`, pelo leitor do chip,
       `a02_controles._sensor_ligado`) e o leitor de movimento aberto
       (`inputs.gyro`, pelo `controller_card.gyro_do_inputs`). O motor pergunta
       as duas coisas antes de mover (`gamepad.aplicar_o_movimento`: o
       `REGISTRO.estado(uniq).giroscopio` e a `velocidade_do_movimento`), e
       sem qualquer uma o cursor não anda. Sem leitura é não, como na 2;
    5. **o mouse está movendo o cursor AGORA** — `mouse_emulation.despachando`,
       o dono único da resposta no daemon
       (`ipc_handlers._bloqueio_da_emulacao_de_desktop`): o «Status do Modo»
       ligado, o mouse virtual de pé, e nem o modo jogo nem o jogo com a
       entrada calando o desktop. É a mesma conjunção com que o
       `lifecycle._poll_loop` decide rodar o tique da Navegação, e sem ele o
       giro não chega a cursor nenhum. O `enabled` sozinho é o sinal mais
       fraco: com o PS segurado (modo jogo) ele segue `true`, a linha do mouse
       diz «em pausa», e o cartão afirmaria o cursor — foi o que a conferência
       fotografou.

    OS LEITORES SÃO DA ABA CONTROLES DE PROPÓSITO: o chip e a dica do
    Giroscópio de lá e este cartão falam do MESMO fato, e duas leituras dele
    divergiriam na primeira correção.
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


def linha_do_cartao(via: str, primario: bool, cursor: bool = False) -> str:
    """A linha de estado do cartão, em HTML — UM DONO, DOIS CHAMADORES.

    O gerador (`aba06.controle`) desenha a bancada com ela e o pacote pinta o
    produto com ela a cada tique; é o mesmo arranjo do `desenho_da_luz` da 04.

    ELA VIROU HTML EM 21/09/2026, e a razão é a BOLINHA. O endereço tinha alvo
    `texto`, e o texto não sabe devolver o `<span class="bolinha">`: o molde
    poupava a linha para não apagá-la (`enderecos_que_o_texto_apaga`), e por
    isso um lugar ESVAZIADO continuava dizendo `● USB • Navega o PC` em verde
    com a mesa vazia — foi o que ela fotografou. Com o alvo `html` o lugar
    vazio recebe o travessão (`LUGAR_VAZIO`) e a bolinha VOLTA quando o
    controle volta, porque quem a desenha passa a ser esta função.

    O TERCEIRO PAPEL — A-MIRA-NA-NAVEGACAO-02, 25/09/2026. `cursor` diz que
    este controle, sem navegar o PC, move o cursor pelo giro (ver
    `move_o_cursor`). Ele não acende a bolinha: o verde é de quem navega, e
    quem navega continua sendo um só.
    """
    papel = (PAPEL_QUE_NAVEGA if primario
             else PAPEL_DO_CURSOR if cursor else PAPEL_SO_A_JANELA)
    corpo = f"{via}{PONTO}{papel}" if via else papel
    return (BOLINHA if primario else "") + corpo


def _linhas_dos_botoes(p: dict[str, Any]) -> dict[str, str]:
    """As 21 linhas de *o que cada botão faz*, com o RÓTULO que o desenho mostra.

    O VOCABULÁRIO É O DO MOTOR, inteiro: `acoes.BOTOES` diz quais linhas
    existem, `acoes.padrao()` diz o que cada uma faz de fábrica e
    `acoes.rotulo()` traduz o token no texto da `<option>`. O gerador monta as
    mesmas listas do mesmo lugar (`aba06.ACOES_UNI = por_grupo()`), e é por isso
    que o valor emitido aqui SEMPRE existe como opção — condição do
    `escrever()` com `data-hef-alvo="valor"`, que se cala quando não casa.

    O PERFIL VENCE O DE FÁBRICA linha a linha, e não em bloco: `button_actions`
    guarda DIFERENÇA (`None` quer dizer "herda"), então uma linha ausente não é
    "nada" — é o de fábrica.

    SÃO TRÊS CAMADAS DESDE 06/09/2026, e não duas: esta função montava o de
    fábrica com `button_actions` por cima e **nunca olhava `key_bindings`** —
    a mesma cegueira que o `resolver()` tinha antes da ONDA3-MOTOR-01, e com o
    mesmo desfecho, um degrau adiante. Um perfil em que o usuário escreveu
    `Super` no Options pela janela antiga fazia a tabela mostrar o de fábrica,
    sobre um botão que digitava outra coisa. Agora quem responde é
    `acoes.tabela_efetiva`, pelo `resolver()` — a MESMA chamada que alimenta o
    device —, e as três camadas são o de fábrica, os atalhos da janela antiga e
    a escolha desta tela, nessa ordem.

    O QUE ELA NÃO TEM COMO DIZER continua sem ser dito AQUI, e é de propósito:
    uma combinação livre não é `<option>` de lista nenhuma, `acoes.rotulo()`
    devolve o token cru e o `escrever()` do piloto o recusa em silêncio. Quem
    nomeia essas linhas é a TIRA (`linhas_que_a_lista_nao_sabe_dizer`), porque
    o lugar de dizer o que a tabela não alcança é o texto ao lado dela, e não
    uma opção nova por tecla que ela invente.
    """
    perfil_ = p or {}
    tabela = acoes.tabela_efetiva(
        perfil_.get("button_actions") or None,
        perfil_.get("key_bindings") or None)
    return {
        f"{PREFIXO_DA_ACAO}{botao}": acoes.rotulo(str(tabela.get(botao) or ""))
        for botao in acoes.BOTOES
    }


# `input_actions.frase_dos_atalhos_fora_da_lista` termina com *"nada nesta aba
# "Guardar" faz `apply_button_actions` reescrever o conjunto todo a partir do de
# fábrica (`profiles/manager.py:570`, `core/acoes_de_botao.resolver`, que nunca
# cada linha faz sai de `core/acoes_de_botao`.
# ---------------------------------------------------------------------------


def _colado(ligacao: Any) -> str:
    """A ligação do perfil na forma com `+`, que é a que o produto lê de volta."""
    if isinstance(ligacao, (list, tuple)):
        return "+".join(str(t) for t in ligacao)
    return str(ligacao)


def _atalho_em_palavras(colado: str) -> str:
    """`"KEY_LEFTCTRL+KEY_W"` → `"Ctrl + W"`, pelo dono do produto.

    O IMPORT É TARDIO pela mesma razão de `_nome_do_botao`: `input_actions` puxa
    GTK no topo, e os pacotes são puros de propósito. Sem GTK no ambiente volta
    o token cru, que é feio e é honesto.
    """
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import humanize_binding
    except Exception:
        return colado
    return str(humanize_binding(colado))


def _dois_donos() -> list[tuple[str, str, str]]:
    """Os botões que o mouse E o teclado atendem ao mesmo tempo, DE FÁBRICA.

    `(botão, o que a tabela mostra, o que o teclado faz no mesmo botão)`.

    MEDIDO, NÃO DIGITADO: `acoes.padrao()` mostra o do MOUSE quando os dois têm
    opinião (o docstring dele diz por quê — é o que a pessoa vê acontecer com o
    cursor na frente do usuário), e `DEFAULT_BUTTON_BINDINGS` diz o do teclado. Onde
    os dois discordam, o produto faz OS DOIS e a tabela conta metade.

    Hoje isso dá um botão só — o R3, "Botão do meio" para o mouse e "Fechar o
    teclado na tela" para o teclado —, e a colisão já está escrita em
    `core/keyboard_mappings.py:37-42`. Derivar em vez de digitar é o que faz
    esta tira acompanhar o dia em que um segundo botão entrar na mesma situação.
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


#: OS DOIS MAPAS QUE O `set_button_actions` RECONSTRÓI DO DE FÁBRICA, e é deles
#:     "— Nada —" no circle   -> AINDA emite KEY_ENTER
#: Quadrado. A cura é do MOTOR (`uinput_mouse.set_button_actions` precisa saber
#: quais botões foram calados de propósito, e hoje não sabe: `do_mouse` não
#: Enquanto ela não vem, **a tela diz**, que é o contrário de um botão que
#: `set_button_actions` DE VERDADE e compara com o que esta função responde.


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

    **É A METADE VISÍVEL DO DEFEITO §3-1**, e o defeito é do produto, não desta
    aba: `apply_button_actions` (`profiles/manager.py:570`) roda DEPOIS do
    `apply_keyboard` e chama `teclado.set_bindings(...)` com o conjunto INTEIRO
    que `acoes_de_botao.resolver()` deriva — e `resolver()` parte de
    `acoes.padrao()` e **nunca consulta `profile.key_bindings`**. Logo, um perfil com
    `button_actions` preenchido apaga o efeito do que o usuário escreveu à mão na
    janela antiga, em silêncio, na próxima ativação.

    A COMPARAÇÃO É CONTRA O QUE O DAEMON VAI APLICAR, e não contra a lista da
    tela: `resolver(button_actions)` é literalmente a chamada que o
    `apply_button_actions` faz. Um atalho que COINCIDA com o resultado sobrevive
    — por coincidência, e não por cuidado — e não entra aqui, porque nomear o
    que não se perde é ruído.

    A RESSALVA QUE A FRASE CARREGA, e ela é medida: sem device de mouse vivo o
    `apply_button_actions` sai antes (`manager.py:628-633`) e nada é reescrito. Por
    isso a tira diz *"quando o mouse virtual estiver de pé"* em vez de prometer
    o desastre em todo caso.

    ELA NÃO MORREU SOZINHA, e o fato estava errado AQUI — 06/09/2026. Esta
    linha dizia *"ela morre sozinha no dia em que `resolver()` passar a herdar
    `key_bindings`"*. O `resolver()` herdou (ONDA3-MOTOR-01) **e a função não
    morreu**: quem precisava passar o campo era o CHAMADOR, e ele continuava
    chamando `resolver(button_actions)` com um argumento só — a assinatura de
    antes, byte a byte, que é o contrato que aquela frente preservou de
    propósito. Com o campo passado, a lista deixa de nomear os oito botões do
    `DOMINIO_DO_TECLADO` (que agora sobrevivem) e passa a nomear **só os que
    ainda se perdem de verdade**: os que o usuário escreveu na janela antiga FORA
    daquele domínio — o `cross`, o `triangle`, o `r3` —, para os quais o
    `apply_button_actions` reescreve o teclado inteiro sem consultá-los.

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
#   `input_actions.dehumanize_binding` o que ela digita -> token cru
# mudança não pegou". Ver `_tabela_efetiva` em `core/acoes_de_botao.py`.


def _traduzir(texto: str) -> str:
    """`"Ctrl + W"` → `"KEY_LEFTCTRL+KEY_W"`, PELO DONO DA JANELA ANTIGA.

    Sem GTK no ambiente o `input_actions` não importa, e aí o texto volta como
    veio: quem valida é a etapa seguinte, e ela recusa dizendo. Inventar uma
    tradução aqui seria a segunda tabela que este bloco existe para não ter.
    """
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import (
            dehumanize_binding,
        )
    except Exception:
        return texto.strip()
    return str(dehumanize_binding(texto.strip()))


def _desfazer_o_humanize(cru: str) -> str:
    """O `humanize_binding` ao contrário — hoje uma DELEGAÇÃO, não uma tabela.

    **ERA UM CONTORNO, E VIROU CURA NO DONO — 06/09/2026.** Aqui morava o ramo
    de fallback do `humanize_binding` escrito do lado de cá: `humanize` faz
    `tok[4:]` para todo `KEY_*` fora de `_KEY_LABELS`, então a coluna "Tecla do
    teclado" mostrava `F5`, e `dehumanize_binding("F5")` devolvia `F5`, que o
    `parse_binding` recusa. Alcançava F1..F12, Home, End, Insert, PageUp,
    PageDown, Comma, Dot e as três de volume.

    O contorno funcionava e era um SEGUNDO DONO do mesmo fato — a janela antiga
    continuava com o buraco vivo, mostrando `F5` e recusando `F5` digitado de
    volta. A cura foi para `input_actions.dehumanize_binding`, onde quem decide
    é o vocabulário do `evdev`, e fecha os dois lados de uma vez. Esta função
    fica como PORTA: o nome é citado em prosa desta aba e a delegação diz para
    onde a pergunta foi.

    A recusa de CAPACIDADE não se perdeu com a mudança de dono: ela nunca foi
    daqui. `tokens_da_tecla` a pede a `uinput_keyboard.SUPPORTED_KEYS`, logo
    abaixo, e uma tecla que o `evdev` conhece e o device virtual não declara cai
    lá, com a frase do dono.
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

    Vazio devolve `()`, e isso quer dizer **este botão não digita nada**: é o
    mesmo `— Nada —` da lista ao lado, dito pelo campo em branco. Não é erro, e
    tratá-lo como erro faria a tela recusar o gesto mais natural de todos —
    apagar o que está escrito.

    AS TRÊS RECUSAS SÃO DOS DONOS, e nenhuma frase de tecla é redigida aqui:

    1. a FORMA, de `keyboard_mappings.parse_binding` — ele levanta `ValueError`
       com o token que não entendeu;
    2. a CAPACIDADE, de `uinput_keyboard.SUPPORTED_KEYS` — a tecla existe no
       vocabulário e o device virtual não a declara;
    3. a MISTURA, de `uinput_keyboard._delegate_virtual_tokens` — um
       `__OPEN_OSK__` junto com um `KEY_*` é rejeitado LÁ com um `warning` e
       sem emitir nada. Recusar aqui é dizer na tela o que o daemon diria no
       journal.
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

    É a segunda sacola do `resolver()`, com as TRÊS camadas já aplicadas na
    ordem do produto (de fábrica, `key_bindings`, `button_actions`) — a mesma
    chamada que `profiles/manager.apply_button_actions` faz para alimentar o
    device. Ler daqui é o que impede esta tela de mostrar uma coisa e o
    aparelho digitar outra.
    """
    perfil_ = p or {}
    _do_mouse, do_teclado, _sem = acoes.resolver(
        perfil_.get("button_actions") or None,
        perfil_.get("key_bindings") or None)
    return do_teclado


def teclas_dos_botoes(p: dict[str, Any]) -> dict[str, str]:
    """Os oito campos da tela "Teclas do teclado", com o texto que ela lê.

    Vazio quando o botão não digita nada — é a regra de produto para toda a casa
    (*campo sem informação não mostra nada*), e é o que faz o campo em branco
    querer dizer a mesma coisa na leitura e na escrita.
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

    DECISÃO, 06/09/2026 (06-Q3): *"O PS ganha a mesma lista das outras 21
    linhas; se você der uma tecla a ele, ele passa a digitar SEM parar de abrir
    a Steam, **e a tabela não avisa isso**."* Esta função é a última oração —
    ela existe para fazê-la deixar de ser verdade.

    ELA NASCE SÓ QUANDO HÁ O QUE DIZER, como as outras quatro. Sem escolha no
    perfil o PS é só o que sempre foi, e uma tira que fala sempre é uma tira que
    ninguém lê. A linha do PS só digita desde 01/10/2026
    (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01): o `— Nada —` e o «Abrir a
    Steam» saíram dela, e um perfil que ainda os guarde não ganha frase (a
    migração os leva ao ⑥ dos gestos).

    A TIRA NÃO NOMEIA O ATO DA MÁQUINA, e a razão é medida: o estado que o
    daemon publica à tela **não traz `ps_button_action`** (`ipc_handlers` só o
    devolve na resposta de `daemon.reload`). Escrever "continua abrindo a
    Steam" seria afirmar o degrau de fábrica sobre uma máquina que ninguém
    perguntou — e ele é ajustável (`steam` · `none` · `custom`). O que a frase
    afirma é o que vale nos três casos: o PS **continua sendo a saída de
    emergência**, porque os gestos e o segurar-para-alternar não passam por
    aquele campo. RELATO: publicar `ps_button_action` no estado é o que deixa a
    tira nomear as duas metades, e é de quem for dono do IPC.

    O SEGUNDO RAMO É O SILÊNCIO QUE A 06-01 DEIXOU DECLARADO: o `resolver()`
    tira o PS das três sacolas, então uma escolha que ninguém atende (um
    `BTN_*`, um papel de eixo, "Abrir um programa") **não entra em `sem_dono`**
    e não aparece na frase "Não acendem nada hoje". O daemon a registra no
    journal como `ps_solo_escolha_sem_atendente`; sem esta linha, a tela seria o
    único lugar calado.

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
    """As linhas da troca: o perfil, com as que ela está mexendo por cima.

    Mesmo desenho de `_o_que_a_tabela_mostra`, e pelas mesmas razões: a pintura
    CONCORDA com o que o usuário escolheu em vez de parar, a linha que o perfil
    passou a dizer sai da trava sozinha, e cinco segundos sem tique querem
    dizer que ela saiu da aba.
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
                                       move_o_cursor(c, ctx, primario)),
            "identidade": identidade_de(c, ctx.mesa),
        }
    plastico = [cor_do_plastico(str(m.get("cor") or "")) for m in ctx.mesa]
    # pede, teria QUEBRADO o desenho — e foi por isso que a página passou a
    desenho = [colorway_do_aparelho(str(m.get("cor") or "")) for m in ctx.mesa]
    # QUEM NAVEGA O PC É O PRIMÁRIO, e quem o marca é o daemon (`is_primary`).
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
    if isinstance(rato.get("enabled"), bool):
        mesa["rato-ligado"] = LIGADO if rato["enabled"] else DESLIGADO
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
        mesa["teclado-estado"] = _o_teclado_em_palavras(bool(tecla.get("enabled")))
    return {
        "colunas": cards,
        "mesa": mesa,
        LUGAR_VAZIO: {"identidade": SEM_NINGUEM_AQUI, "navega": TRAVESSAO},
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


# DISCO, E SÓ — NUNCA `perfil.gravar_e_reaplicar`. O preço está medido em 03/09
# ainda não salvou. O aparelho já recebeu a mudança pelo `mouse.emulation.set`

_DO_RATO: dict[str, str] = {
    "mouse_speed": "speed",
    "mouse_scroll": "scroll_speed",
}


def _secao_do_mouse(prof: Any, ctx: Contexto, campos: dict[str, Any]) -> Any:
    """A seção `mouse` do perfil com o que este clique mudou — ou `None`.

    `None` quer dizer **não há o que gravar**, e ele tem dois donos: o perfil
    que já diz exatamente isto (gravar de novo seria escrever o mesmo arquivo a
    cada passagem do arraste), e o daemon que ainda não falou.

    A SEÇÃO NASCE COM O QUE ESTÁ VALENDO quando o perfil não a tinha: `enabled` é
    campo OBRIGATÓRIO do `ProfileMouseConfig`, então uma seção que nasce por um
    arraste de velocidade precisa dizer alguma coisa sobre o liga/desliga — e a
    única coisa verdadeira que existe é o estado vivo. Inventar `False` faria o
    perfil, na próxima ativação, DESLIGAR uma emulação que estava ligada.

    SEM O BLOCO DO DAEMON A SEÇÃO NÃO NASCE. Um perfil sem `mouse` mais um
    daemon mudo não têm de onde tirar o `enabled`, e um valor chutado aqui vale
    para todo jogo que casar com este perfil, para sempre.
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

    Aceita `teclado_emulado=` (a lista «Função do teclado») e os dois do rato
    (`mouse_speed`, `mouse_scroll`) — ver `_DO_RATO`.

    :return: `""` quando gravou, e também quando não havia o que gravar (o
        disco já dizia isso). A frase do que NÃO deu quando não há perfil ativo
        ou quando o arquivo não abre.

    POR QUE UMA FRASE E NÃO UM `RuntimeError`: o aparelho JÁ mudou quando esta
    função é chamada — a chamada ao daemon vem antes, e ela deu certo. Levantar
    aqui pintaria o cartão laranja da RECUSA sobre um gesto que fez metade do
    que prometeu, e ela leria *"não deu"* sobre um cursor que acabou de ficar
    mais rápido. Quem chama devolve a frase pelo canal de AVISO
    (`{"recado": …}`), que deposita no mesmo cartão com tom de sucesso.

    O ARRASTE CHEGA DUAS VEZES E GRAVA UMA. O ouvinte do piloto escuta `change`
    **e** `click`, e soltar o polegar de um `<input type=range>` dispara os dois
    com o MESMO valor. A segunda passagem encontra o disco já igual, `_secao_do_mouse`
    devolve `None` e nada é escrito — o guarda é a IGUALDADE, e não um relógio.
    É mais forte que o `_so_abriu_o_seletor` da aba 04, porque também cobre o
    caso de ela arrastar a barra e voltar ao valor de origem.
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
        if "teclado_emulado" in campos:
            quer = bool(campos["teclado_emulado"])
            if getattr(prof, "teclado_emulado", None) is not quer:
                mudanca["teclado_emulado"] = quer
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

    O `data-hef-alvo="valor"` do `<input type=range>` faz o ouvinte do piloto
    mandar `valor: alvo.value` (`hefesto_vivo.py`, o ouvinte de `change`). Um
    `<div>` não teria `value` e o gesto chegaria com a chave vazia — foi o
    defeito que a aba Vibração nomeou em 03/09/2026 antes de o trilho dela
    virar `<input>`, e a frase abaixo é para ele.

    `RuntimeError` E NÃO `ValueError` porque é ELA quem tem de ler: o contrato
    do piloto leva a frase de um `RuntimeError` ao cartão e deixa o `ValueError`
    no `stderr` de quem lançou a janela (`hefesto_vivo._recusou_dizendo`).
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
    """A frase da recusa, TRADUZIDA — ou `""` quando o daemon aceitou.

    A tradução é do produto: `app/actions/mouse_actions.frase_da_recusa_do_mouse`
    lê o `bloqueio` do corpo e cobre cinco motivos, com fallback honesto para
    motivo novo e para recusa sem motivo. Ela existe desde 25/08 e nunca tinha
    sido chamada por esta aba.

    FATO SUBSTITUÍDO — 03/09/2026. Aqui estava escrito que *"a ponte não expõe o
    `_call_checked_detalhado`, que é o único que entrega o corpo"*, e por isso
    um `{"status": "failed", "bloqueio": "sem_device"}` voltava como sucesso e a
    tela do usuário ficava sem uma palavra. A ponte entrega o corpo desde 01/09:
    `ponte.resultado` (`interface/pacotes/ponte.py:191`) devolve o `result` do
    daemon e levanta quando ninguém responde. Era um caminho que já existia e
    esta aba não chamava.

    `status` AUSENTE conta como aceito: o `set_mouse_speed` responde
    `{"status": "ok", "enabled": …}` e nenhum outro campo, e tratar a ausência
    como recusa faria toda troca de velocidade acusar um "não" que não houve.
    """
    from hefesto_dualsense4unix.app.actions.mouse_actions import (
        frase_da_recusa_do_mouse,
    )

    if not isinstance(resposta, dict) or resposta.get("status") != "failed":
        return ""
    return frase_da_recusa_do_mouse(resposta)


def _recusa_do_teclado(resposta: Any) -> str:
    """O motivo de o teclado não ter ligado, do bloco que o próprio daemon devolve.

    `keyboard.emulation.set` responde com o bloco `keyboard_emulation` inteiro —
    *"para a janela não precisar de uma segunda chamada só para saber se o
    device subiu"* (`daemon/ipc_handlers.py:5162`). Quem o traduz é
    `emulation_actions.descrever_teclado_emulado`, o mesmo dono da linha de
    estado desta aba.

    Sem bloco e sem frase, o que sobra de verdadeiro é que ele recusou — e é o
    que se diz, em vez de inventar um motivo. A frase de "não sei" da GTK
    (`TECLADO_SEM_ESTADO`, *"o Hefesto pode estar desligado"*) NÃO serve aqui e
    é por isso que o bloco é conferido antes: o Hefesto respondeu, ele é que
    disse não.
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

    TRÊS CONDIÇÕES, e as três desligam a memória sozinhas:

    1. **o daemon ainda diz o mesmo número.** Se ele já publica outro — porque
       aplicou, porque aparou, ou porque o usuário mexeu pela janela GTK —, a memória
       é largada e a partida volta a ser ele;
    2. **o clique vai para o mesmo lado.** Dois `+` seguidos somam de verdade;
       um `+` seguido de um `-` parte do DAEMON, não do alvo pendente. A razão é
       que os dois gestos querem coisas diferentes: repetir é *ande mais*, e
       inverter dentro de meio segundo é ambíguo — a leitura conservadora é a de
       sempre, e é a que o `PROVAS` desta aba já cobrava. O interruptor manda
       `sentido=0` e cai sempre neste ramo: ele tem UM gesto, e o segundo
       clique é *desfaça*, nunca *ande mais*;
    3. **o relógio ainda está na janela do tique** — ver `MEMORIA_DE_UM_CLIQUE`.

    ELA SÓ FICA COM O QUE O HEFESTO NÃO RECUSOU — ver `_reservar`. Guardar o
    alvo e deixá-lo lá era o defeito medido em 03/09/2026: um clique RECUSADO
    (`sem_device`) deixava o alvo na memória, e o clique seguinte partia de um
    número que nunca existiu — pedia 8 tendo o daemon em 6, pulando o 7.
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

    A RESERVA VEM ANTES DA CHAMADA, e isto é medido: os gestos rodam em THREAD
    (`hefesto_vivo.trabalhar`, `:1384` — *"um gesto síncrono congelaria a janela
    inteira por nove segundos e meio"*), então dois cliques rápidos são duas
    threads. Anotar só DEPOIS da resposta deixaria a segunda ler a memória vazia
    e repetir o pedido da primeira — o defeito que esta memória cura voltaria
    dentro do tempo de ida e volta do IPC, que é justamente a janela em que ela
    clica duas vezes.

    E ELA É DESFEITA NA FALHA, por `_largar_a_reserva`: reservar não é
    confirmar. Sem o desfazer, a reserva seria o mesmo defeito com outro nome.
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

    SEM `enabled` DE PROPÓSITO, e é a rota que o produto criou para isto: o
    handler manda o pedido sem `enabled` para `set_mouse_speed`
    (`daemon/ipc_handlers.py:3670`), que atualiza a config e o device vivo **sem
    start/stop e sem gravar o flag**. É o que impede um ajuste de velocidade de
    RELIGAR a emulação e matar o gamepad virtual — a regressão que o
    BUG-MOUSE-GUI-SYNC-01 (A4) fechou. O `_send_mouse_param_async` da GUI
    estável (`app/actions/mouse_actions.py`) manda exatamente este payload.

    ELE NÃO LÊ O `ctx`, E É A DIFERENÇA QUE A BARRA TROUXE. Os `-`/`+` liam o
    estado do último tique porque um passo precisa saber de ONDE parte — e daí
    vinham `_partir_de`, a memória `_PEDIDO` e as três condições que a
    desligam. Uma barra manda o número inteiro: a partida é o polegar dela, e
    não há clique engolido a curar. A memória continua de pé, e continua com um
    cliente — o interruptor "Status do Modo", que tem UM gesto e por isso
    depende dela para o segundo clique ser *desfaça*.

    A FAIXA NÃO É DIGITADA AQUI: quem chama passa as constantes
    `MOUSE_SPEED_MIN`/`MOUSE_SPEED_MAX`
    (`integrations/uinput_mouse.py:72-73`), o mesmo módulo de onde
    `set_speed` (`:279`) tira a sua. A barra já nasce com esses `min`/`max`
    (`aba06.trilho`), então aparar aqui é a rede para o dia em que alguém
    publicar a página sem regerar o desenho — não é a segunda verdade que esta
    casa persegue. O daemon continua aparando por último.

    O ARRASTE CHEGA DUAS VEZES, e é inócuo de propósito — a mesma medição de
    `a05_vibracao.intensidade`: o ouvinte do piloto escuta `change` **e**
    `click`, e soltar o polegar de um `<input type=range>` dispara os dois com o
    MESMO valor. `set_mouse_speed` é idempotente — grava o mesmo número e
    reconfigura o mesmo device —, então a segunda passagem não muda nada.
    Filtrar por evento aqui seria escrever, neste arquivo, uma regra sobre o
    ouvinte que mora em outro.

    :return: o número que FOI ao daemon, já aparado. Quem chama o leva ao
        perfil (D2) — e o valor tem de ser este, nunca o do `ctx`: o `ctx` é o
        estado do tique ANTERIOR, e gravar dali guardaria a velocidade velha no
        disco enquanto a nova roda no aparelho.
    """
    alvo = max(minimo, min(maximo, _numero_da_barra(o, oque)))
    _mandar(p, origin=MANUAL, **{campo: alvo})
    return alvo


def _mandar(p: Any, **params: Any) -> None:
    """`mouse.emulation.set`, e diz POR QUE quando o daemon recusa.

    `p.chamar` devolve `bool` e joga fora o corpo — é ele que trazia a recusa de
    volta como sucesso. `p.resultado` traz o corpo e levanta quando ninguém
    responde, que são exatamente os dois desfechos que esta função precisa
    separar: *o Hefesto não falou* e *o Hefesto disse não, por isto*.
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

    POR QUE OS DOIS, e não só o mouse: este interruptor é o que o usuário pediu em
    27/08 no lugar de dois botões — *"Suspender Mouse e Teclado, Sair do Modo
    Jogo, deixam de existir devido ao botão status na parte superior"* —, e a
    dica dele diz o alcance: *"nada desta aba chega ao PC"*. Teclado é desta
    aba. O daemon tem dois interruptores separados, e o do teclado nasceu
    justamente porque desligar o mouse deixava o teclado emitindo Alt+Tab dentro
    da partida (`daemon/ipc_handlers.py:5272`); o `desktop.status.set` aciona
    os dois, numa chamada só.

    O MOUSE VAI PRIMEIRO de propósito. É ele que tem exclusão mútua com o
    gamepad virtual: ligá-lo PARA o vpad (`set_mouse_emulation`,
    `daemon/lifecycle.py:1163`). Se o mouse falhar, o teclado não é tocado e
    não fica ligado sozinho num modo que não é dele. A ordem mora no daemon
    desde 29/09/2026 (`Daemon.definir_o_status_da_navegacao`).

    O LADO PARA ONDE IR SAI DO DAEMON, nunca da caixinha: o piloto não sabe
    escrever `checked` (o `escrever()` dele cobre texto, largura, fundo e
    `value`), então o desenho nasce `checked` e o daemon do usuário nasce
    `enabled=false` — ler a tela inverteria o gesto no primeiro clique.

    O PORTÃO DO MODO É DO PRODUTO, e está copiado dele: `_sync_mouse_mode_gate`
    (`app/actions/mouse_actions.py`) faz `blocked = mode != MODE_DESKTOP` e
    desliga o interruptor nos DOIS sentidos, inclusive com o modo desconhecido.
    A razão está escrita lá e é o que este gesto herda: *"Ligar o switch durante
    'Jogar pelo Hefesto' derrubava o vpad e os jogadores do co-op SEM AVISO (a
    exclusão mútua do daemon é silenciosa)"*.

    A FRASE É OUTRA, e tem de ser: a do produto (`MODE_GATE_HINT`) manda ir à
    **aba Início**, que não existe no desenho das dez abas — o modo mudou para a
    aba **Jogar**. Reusá-la mandaria ela a uma aba que não está lá. Reusar o
    módulo também não dá: `mouse_actions.py` importa GTK no topo, e os pacotes
    são puros de propósito.

    OS DOIS LADOS VÃO AO PERFIL JUNTOS — 05/09/2026, decisão D2. Este
    interruptor mexe em `mouse.enabled` **e** em `teclado_emulado`, e gravar só
    o primeiro deixaria o perfil dizendo *mouse desligado, teclado ligado* — um
    estado que este botão não sabe produzir e que a próxima ativação imporia.

    QUEM GRAVA É O DAEMON, DEPOIS DO APARELHO — O-MOUSE-SEGUE-A-NAVEGACAO-01
    (29/09/2026). Este gesto mandava as duas chamadas e gravava o perfil pela
    própria mão (`_guardar_no_perfil`); agora manda `desktop.status.set` uma
    vez, e o ato, a ordem (o mouse primeiro) e a gravação dos dois lados moram
    em `Daemon.definir_o_status_da_navegacao`. Se o teclado recusar, o daemon
    não grava, e o gesto levanta dizendo por quê.
    """
    if not ctx.state:
        raise RuntimeError(
            "não consegui falar com o Hefesto agora, então não sei se ligar o "
            "mouse derrubaria um jogo em andamento. Tente de novo em instantes.")
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


_ESCOLHA_DELA: dict[str, bool | None] = {
    "fora": True, "desativado": False, "dentro": None}

_ESCOLHA: dict[str, bool | None] = _ESCOLHA_DELA


@gesto("06-navegacao.html", "teclado", grava="gravar_pelo_gesto")
def teclado(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A lista "Função do teclado". `keyboard.emulation.set`.

    O VALOR VEM EM `valor`, E ISSO É O QUE MUDOU DESDE A PRIMEIRA LEVA: o
    ouvinte do piloto passou a escutar `change` além de `click` e a mandar o
    `value` do alvo (`hefesto_vivo.py:75` e `:230`). Antes só chegava `texto`,
    que num `<select>` é a lista INTEIRA de opções concatenada — foi por isso
    que esta lista ficou sem dono na primeira leva, e não por falta de método.

    O `rotulo` É O SEGUNDO CAMINHO, não um enfeite: as `<option>` desta lista
    não têm atributo `value` (`value` não está entre os que o portão do desenho
    ignora), então `select.value` **é** o texto — mas um `<option value=…>` que
    nasça amanhã mandaria a chave em `valor` e a frase em `rotulo`, e é o
    `rotulo` que continuaria casando com o desenho.

    DUAS DAS TRÊS OPÇÕES TÊM DONO, e a terceira RECUSA DIZENDO — que é a regra
    da casa, não uma falha desta ligação:

    * "Só fora do jogo" → `enabled=True`; "Desativado" → `enabled=False`. O
      handler (`daemon/ipc_handlers.py:3732`) só lê `enabled`, e ele é bool.
    * "Só dentro do jogo" **não existe do outro lado**, e nem poderia: ele é o
      INVERSO de tudo o que o produto faz hoje.

    FATO DERRUBADO — 02/09/2026, e ele estava escrito NESTE arquivo e no
    enunciado do trabalho: *"'Só fora do jogo' não existe do outro lado"* e
    *"'Só dentro do jogo' já existe, e é o `suppress_desktop_emulation`"*. **Os
    dois estão invertidos**, e a medição é de três leituras:

    1. `Profile.suppress_desktop_emulation` (`profiles/schema.py:1215`) diz, no
       próprio comentário: *"True = ativar o perfil suprime a emulação de
       mouse/teclado no desktop (jogos de GAMEPAD que leem o controle cru)"*.
       O perfil é ativado quando o jogo casa; logo a supressão vale **durante o
       jogo** — o teclado funciona FORA dele.
    2. `apply_profile_suppression` (`daemon/lifecycle.py:1985`) recebe esse
       campo a cada ativação de perfil e liga a supressão com `desired=True`.
    3. Sem perfil nenhum a dizer o contrário, o daemon **já** cala a emulação de
       desktop no tique em que o gamepad virtual despachou (o
       `gamepad_dispatched` do laço de `daemon/lifecycle.py`).

    Logo o teclado emulado ligado **é** "só fora do jogo", e a etiqueta velha
    ("Ligada — atalhos e teclado na tela") é que afirmava um alcance maior do
    que o produto tem. O que falta é o INVERSO: um teclado que só valha DENTRO
    do jogo. Ele exigiria um portão por perfil com o sinal trocado — campo novo
    no esquema, e ele **não existe**. Enquanto não existir, esta opção recusa
    dizendo, que é o contrário de um botão que aceita o clique e não faz nada.

    SEM PORTÃO DE MODO, ao contrário do gesto `modo` logo acima, e é medido: o
    portão de lá existe porque ligar o MOUSE derruba o gamepad virtual — o
    `set_mouse_emulation` (`daemon/lifecycle.py:1137`).

    Do outro lado, o teclado não mexe no gamepad virtual em momento nenhum.
    Quem o liga e desliga é o
    `set_keyboard_emulation` (`daemon/lifecycle.py:1494`): ele cria ou destrói o
    teclado virtual e nada mais.

    E COM O GAMEPAD DESPACHANDO, o teclado nem chega a ser consultado — a
    guarda está em `lifecycle.py:4225`, no `if not gamepad_dispatched`. Copiar o
    portão daqui bloquearia, dentro do jogo, o único interruptor que existe
    para calar o Alt+Tab do R1 — que é o defeito que este método nasceu para
    curar (queixa, 29/07).

    O QUE ESTE BOTÃO AINDA NÃO DIZ, e está no relato: desligar tira também o
    teclado na tela do L3/R3 e as três regiões do touchpad (o handler manda a
    interface repassar isso). O piloto não tem canal de aviso — um gesto só
    imprime no terminal —, então o recado não tem onde aparecer.

    ELE ENTENDE AS TRÊS PALAVRAS DE PRODUTO, E VOLTOU A ENTENDER SÓ ELAS — 03/09/2026.
    Entre 02/09 e a publicação foram CINCO: as três da bancada mais os dois
    rótulos que a página publicada ainda oferecia, porque aceitar só as três
    transformou duas das três opções da tela do usuário em clique morto — e calado, por
    contrato. A 06 foi publicada, os dois rótulos velhos não existem mais em
    `<option>` nenhuma, e a régua da travessia mandou apagar os sinônimos.

    E DIZ POR QUE NÃO DEU, desde o mesmo dia: a chamada passou a ser
    `p.resultado`, que traz o corpo — o `p.chamar` devolvia `True` para um
    `{"status": "failed"}` e a lista voltava sozinha sem uma palavra.

    E ELE PASSOU A LEMBRAR — 05/09/2026, e este era o buraco INTEIRO desta aba.
    `keyboard.emulation.set` grava na flag GLOBAL da sessão
    (`utils/session.py:306`), nunca no perfil; e `DraftConfig.to_profile` emite
    `teclado_emulado` por PASSTHROUGH do que veio do disco. Medido no ciclo
    completo em `HOME` de mentira: com o perfil dizendo `True` e ela escolhendo
    a opção `TECLADO_DESATIVADO`, o Salvar do rodapé devolvia **`True`** — o
    valor velho, por cima da escolha do usuário, sem uma palavra. Ver
    `_guardar_no_perfil`.
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
    ligar = _ESCOLHA[chaves.pop()]
    if ligar is None:
        raise RuntimeError(
            f"“{TECLADO_SO_DENTRO}” ainda não tem dono, e é o INVERSO do que o "
            "Hefesto faz: ele cala o teclado emulado quando um jogo assume o "
            "controle, e o que sobra é justamente o “"
            f"{TECLADO_SO_FORA}”. Um teclado que valha SÓ dentro do jogo pede um "
            "campo novo no perfil — o portão com o sinal trocado —, e ele ainda "
            "não existe. A lista volta sozinha para o que está valendo.")
    try:
        resposta = p.resultado("keyboard.emulation.set", enabled=ligar)
    except RuntimeError as erro:
        raise RuntimeError(
            "o Hefesto não respondeu — o teclado ficou como estava") from erro
    if isinstance(resposta, dict) and resposta.get("status") == "failed":
        raise RuntimeError(
            f"o teclado ficou como estava: {_recusa_do_teclado(resposta)}")
    recado = _guardar_no_perfil(ctx, teclado_emulado=ligar)
    return {"recado": recado} if recado else None


@gesto("06-navegacao.html", "vel-cursor", grava="gravar_pelo_gesto")
def vel_cursor(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """A barra da Velocidade de cursor, arrastada. `mouse_emulation.speed`.

    DECISÃO, 05/09/2026: *"velocidade do cursor e da rolagem coloca um
    slicer pra cada"*. Até aqui a linha era um par de botões `-`/`+`, e os dois
    gestos que os atendiam (`vel-cursor-menos`/`-mais`) somavam ±1 ao número do
    ÚLTIMO TIQUE. Os dois saíram com os botões: uma barra manda o número
    INTEIRO, e não uma direção — não há de onde partir, e por isso não há passo
    engolido a curar.

    E A PARIDADE COM A JANELA GTK FECHOU NO MESMO MOVIMENTO: lá esta linha é um
    `Gtk.Scale` de `mouse_speed_adj` (`gui/main.glade:79`, 1..12, passo 1), que
    é a MESMA faixa que a barra oferece agora — porque as duas leem o dono
    (`integrations/uinput_mouse.py:72`). Ver `docs/data/paridade-gtk-html.csv`,
    linha "Velocidade do cursor".

    O ALCANCE É O DE UM NÚMERO SÓ, e a medição é de 01/09: `mouse_speed` move o
    analógico esquerdo **e** o cursor do touchpad — `emit_touchpad_move` escala
    por `TOUCHPAD_SENSITIVITY * (mouse_speed / DEFAULT_MOUSE_SPEED)`
    (`integrations/uinput_mouse.py:440`).

    E ELE PASSOU A DURAR ALÉM DA JANELA — 05/09/2026, decisão D2. Até aqui o
    número ia ao daemon e ao `session.json`, e o perfil só o recebia se ela
    clicasse "Salvar" no rodapé: fechar a janela depois de arrastar a barra
    perdia a escolha, calada. Ver `_guardar_no_perfil`.
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

    ELE EXISTE PARA A TELA PARAR DE DESFAZER A ESCOLHA DO USUÁRIO — decisão de
    02/09/2026: *"as 21 listas param de ser repintadas enquanto ela está
    mexendo, até guardar ou sair. Não vira gravação automática: ela quer
    escolher várias, conferir e aplicar de uma vez."*

    Por isso ele **não chama o daemon e não escreve em disco**. O ponto de
    gravação continua sendo o "Guardar" ao lado; o que este gesto faz é anotar
    a escolha em `_MEXENDO`, e é a anotação que faz a pintura do tique seguinte
    concordar com a tela em vez de reescrevê-la.

    SEM ELE A ESCOLHA NÃO CHEGAVA AQUI, e a medição é do mesmo dia: o ouvinte do
    piloto só olha um alvo que case com o `closest` de `manda_do_alvo`
    (`hefesto_vivo.py:189`), e os 21 `<select>` tinham só `data-campo`,
    `data-linha` e `data-hef-alvo`. O `change` morria no navegador:

        ANTES  (o que a pintura pôs) : Botão direito
        CLIQUE (a escolha do usuário)      : F11
        +1500 ms                     : Botão direito

    O `data-gesto` que o gerador passou a pôr (`aba06.LINHA_DE_BOTAO`) é o que
    abre este caminho.

    A RECUSA É DE CLIQUE INVÁLIDO (`ValueError`), e não do produto: um rótulo
    que o produto não conhece só chega aqui se o desenho andou sem o gerador —
    a lista da tela e a do produto saem do mesmo `core/acoes_de_botao`.

    O QUE ELE DEVOLVE é a própria linha, pelo endereço da pintura. Na tela isso
    é um no-op (o `<select>` já está nela), e é de propósito: um gesto que volta
    com `None` não toca o DOM (`hefesto_vivo._deu_certo`) e sai do relato como
    "aplicado" sem nada a mostrar. Devolvendo o endereço, o desfecho do gesto
    passa a ser verificável — e a linha volta ao lugar certo se a página tiver
    sido repintada entre o clique e a volta da thread.
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
    """O fechar e o "Cancelar" do *Estilo Point-and-click*. Mesmo ato do irmão.

    ELE É UM SEGUNDO NOME E NÃO UM SEGUNDO COMPORTAMENTO, e a razão de existir
    é de ENDEREÇO: o piloto recusa gesto que não esteja registrado, e pendurar
    esta tela no `fechar-definicoes` faria o relato do clique nomear a pop-up
    errada — quem for triar um desfecho leria "definições" sobre um botão da
    tela do estilo. O ATO é o mesmo porque as duas telas dividem a mesma trava:
    elas escrevem o MESMO campo do perfil (`Profile.button_actions`), e uma
    escolha pendente numa é uma escolha pendente na outra.

    A MORDIDA está em `test_a_06_o_ponto_guarda_o_que_ela_escolhe.py`: troque o
    corpo por `return None` e o caso do "Cancelar" reprova, porque a linha que
    ela abandonou volta a ser oferecida ao "Guardar" seguinte.
    """
    _largar_o_que_ela_mexeu()
    return {"mesa": _linhas_dos_botoes(
        perfil.ativo_que_vale((ctx.state or {}).get("active_profile")))}


@gesto("06-navegacao.html", "tecla-escrita")
def tecla_escrita(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """O usuário mexeu num dos oito campos de *Teclas do teclado*. NÃO grava nada.

    É O IRMÃO DO `linha-de-botao`, e existe pela mesma decisão de
    02/09/2026 — *"não vira gravação automática: ela quer escolher várias,
    conferir e aplicar de uma vez"*. Quem grava é o "Guardar" da tela.

    ELE TEM DE ATENDER O **CLIQUE**, e não só o `change`, e isso é o que faz o
    campo de texto ser editável de verdade. Medido no motor: o `escrever()` do
    piloto escreve `el.value = t` sempre que os dois diferem, e um campo em
    edição difere já na primeira letra — o tique de 100 ms apagaria o que ela
    está digitando. O `change` de um `<input>` só chega quando o campo PERDE o
    foco, tarde demais. O clique dentro do campo chega na hora
    (`hefesto_vivo`, o ouvinte de `click` no documento), e é ele que abre a
    trava; o `change` que vem depois a atualiza com o texto final.

    A RECUSA É `RuntimeError`, e não `ValueError`, de propósito: o
    `_recusou_dizendo` do piloto (`hefesto_vivo.py:2786`) guarda a classe da
    exceção no relato, e `ValueError` é a linguagem de quem programa. Desde
    13/09/2026 nenhuma das duas chega à tela: a combinação que o usuário digitou e o
    produto não sabe digitar pisca a recusa no campo (FRASES-E-DICAS-01).

    E A ANTERIOR SOBREVIVE À RECUSA, sem ninguém a devolver: este gesto não
    escreve em disco, e ao recusar ele LARGA a trava daquele campo — no tique
    seguinte (100 ms) a pintura devolve o que o perfil guarda, por cima do texto
    inválido. Segurar a trava faria a tela ficar mostrando o erro dela para
    sempre, e o "Guardar" recusaria a cada clique por causa dele.
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

    `None` quer dizer *"herda `DEFAULT_BUTTON_BINDINGS` inteiro"*, e o produto o
    resolve assim (`profiles/manager.resolve_key_bindings`). Para trocar UMA
    linha é preciso um dicionário, e o dicionário que **não muda nada** é a
    cópia do de fábrica — medido, e não escolhido: `resolve_key_bindings(None)`
    devolve `dict(DEFAULT_BUTTON_BINDINGS)`, exatamente o mesmo objeto que
    `resolve_key_bindings(dict(DEFAULT_BUTTON_BINDINGS))` devolve.

    O CAMINHO DE VOLTA EXISTE: quando o dicionário terminar igual ao de fábrica,
    quem grava devolve `None` — senão o perfil do usuário congelaria o padrão de HOJE
    e deixaria de acompanhar uma troca no produto. É a mesma disciplina do
    `button_actions`, e a razão está escrita em `guardar_definicoes`.
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

    **É A METADE QUE FALTAVA DA PARIDADE** — `paridade-gtk-html.csv:208`. A
    janela antiga deixa ela digitar qualquer combinação de `KEY_*` na coluna
    "Tecla do teclado"; a tela nova só tinha a lista fechada de 26 ações, e
    `key_bindings` só era tocado **para ser zerado**.

    O QUE ELE GRAVA, e o alcance é o do produto: os oito botões de
    `acoes.DOMINIO_DO_TECLADO`. Os outros catorze não estão aqui porque
    `key_bindings` não manda neles — o que vale ali é o mapa fixo do
    `UinputMouseDevice`, e gravar seria pôr no disco uma escolha que o
    `resolver()` não lê.

    O QUE ELE **NÃO** APAGA, e é o Passo 2 da sprint: as chaves de
    `key_bindings` que estão FORA desses oito. Ela pode ter escrito `Ctrl + W`
    no Cross pela janela antiga, e nada nesta tela alcança essa linha — logo
    nada nesta tela tem o direito de apagá-la. O dicionário de partida é o do
    perfil (`_atalhos_de_hoje`), e só as oito chaves são reescritas.

    CAMPO EM BRANCO É `— Nada —`, e não "sem opinião": a chave sai do
    dicionário, e `tabela_efetiva` lê a ausência dentro do domínio como
    silêncio, que é o que `resolve_key_bindings` entrega ao device. É a mesma
    palavra que a lista ao lado usa, dita pelo campo vazio.

    ELE RECUSA DIZENDO, uma linha por vez, e nada é gravado quando alguma
    recusa: gravar sete de oito e calar sobre a oitava é o botão que responde
    calado.

    ONDE GRAVA (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01): as teclas são do
    cartão «Teclado», que é do computador. Grava no perfil só quando ele já
    tem teclas próprias; senão, no ``maquina.json``, e o perfil não muda.
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
            "de <b>Definições Controle e Mouse</b> diz, que vence: "
            + ", ".join(f"{_nome_do_botao(b)} = "
                        f"{acoes.rotulo(str(escolhas[b]))}" for b in mascarados)
            + ". Para a tecla que você escreveu valer, ponha essas linhas de "
              "volta no de fábrica lá.")
    return {"mesa": teclas_dos_botoes(
        perfil.ativo_que_vale((ctx.state or {}).get("active_profile")))}


@gesto("06-navegacao.html", "padrao-da-tecla", grava="gravar_pelo_gesto")
def padrao_da_tecla(ctx: Contexto, o: dict[str, Any], p: Any) -> dict[str, Any] | None:
    """"Voltar ao padrão" de **UMA** linha — o Passo 2 da sprint.

    A REGRA DE PRODUTO, e é a razão de este gesto existir: *"'Voltar ao padrão'
    devolve a LINHA ao padrão; ele não é um apagador de tudo o que o usuário escreveu
    na janela antiga."* O botão da tela inteira continua existindo e continua
    zerando os dois campos — ele DIZ o que apaga, na confirmação e no recibo —,
    mas até hoje era o ÚNICO caminho: trocar uma linha de volta custava perder
    todas as outras.

    O QUE É "O PADRÃO DESTA LINHA", perguntado ao dono: `acoes.padrao()[botão]`,
    que dentro do `DOMINIO_DO_TECLADO` é por construção o que
    `DEFAULT_BUTTON_BINDINGS` diz. **ESCREVER É O CERTO, e APAGAR seria o
    errado** — e a diferença é medida: dentro de um `key_bindings` que já é
    dicionário, uma chave AUSENTE não é "de fábrica", é `— Nada —`
    (`acoes.tabela_efetiva`, e `resolve_key_bindings` não mescla com os
    defaults). Apagar a chave devolveria a linha ao SILÊNCIO com o botão
    dizendo "padrão".

    ELE TIRA A LINHA DAS DUAS CAMADAS, e tem de tirar: `button_actions` vence
    `key_bindings`, então devolver só a de baixo deixaria o botão fazendo o que
    a lista escolheu, com este gesto dizendo que voltou ao de fábrica.
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

    O DEFEITO QUE ELA CURA, medido em 02/09/2026 e declarado em
    `core/keyboard_mappings.PADRAO_QUE_A_TELA_PUBLICADA_NAO_DIZ`: o L3 nasceu
    ALTERNADOR (`__TOGGLE_OSK__`, decisão 6 dela — *"aperta abre o teclado
    virtual, aperta de novo fecha"*), a página que o produto RENDERIZA foi
    congelada antes disso e não tem a `<option>` do rótulo novo, e por isso a
    pintura do `acao-l3` é RECUSADA EM SILÊNCIO (`hefesto_vivo.escrever`, alvo
    `valor`: um `<select>` só aceita o texto exato de uma opção que ele
    oferece). A linha fica mostrando *"Abrir o teclado na tela"*, que é
    `__OPEN_OSK__` — e o "Guardar" recolhia isso como se fosse escolha do usuário.

    O CUSTO, medido pelo fio do daemon (`acoes_de_botao.resolver` →
    `profiles.manager.resolve_key_bindings`): sem override o device recebe
    `['__TOGGLE_OSK__']`; com o que o "Guardar" gravava ele recebe
    `['__OPEN_OSK__']` — **o L3 para de alternar naquele perfil**, e no tique
    seguinte a pintura volta a casar e não sobra rastro em lugar nenhum.
    Bastava um clique para mudar qualquer OUTRA linha.

    O QUE SEPARA O CONGELADO DA ESCOLHA DO USUÁRIO É `_MEXENDO`, e não um literal:
    ele só tem linha que ELA trocou, pelo gesto `linha-de-botao`. Se o `acao-l3`
    está lá, o usuário escolheu *"Abrir o teclado na tela"* com o dedo do usuário — e isso
    o "Guardar" grava, como grava qualquer outra escolha. É a mesma distinção
    que a trava contra o apagador já usa logo abaixo.

    ELA MORRE SOZINHA NO DIA DA PUBLICAÇÃO: a tabela que a alimenta é a
    declaração, e `test_o_padrao_de_fabrica_cabe_na_tela_publicada` reprova a
    declaração que caducou. Publicada a `06`, a linha do L3 sai da tabela, esta
    função devolve `{}` e o "Guardar" volta a gravar as 21 sem exceção — sem
    ninguém precisar lembrar de apagar nada daqui.

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

    ELE PASSOU A TER DONO EM 01/09/2026, por decisão de produto: *"ganha campo. essa é
    a parte das features que precisam ou serem ajustadas ou desenvolvidas."* O
    que o segurava era medido e verdadeiro — a tela deixava escolher 21 linhas e
    o perfil alcançava 9 —, e a cura foi o campo nascer, não o botão fingir.

    DE ONDE VEM O QUE ELE GRAVA: da `forma`, que o piloto recolhe quando o botão
    traz `data-hef-forma`. O ouvinte manda o valor do elemento CLICADO, e o
    Guardar é outro elemento — sem a forma, ele não teria como saber o que está
    escolhido em cada linha, e era por isso que só podia recusar.

    SÓ O QUE MUDOU VAI PARA O DISCO. Gravar as 21 sempre encheria o perfil de
    linhas iguais ao padrão, e no dia em que o padrão do produto mudasse o perfil
    congelaria o padrão VELHO sem ninguém ter escolhido isso. `button_actions`
    guarda diferença, e é o que o `None` do campo quer dizer: herda.

    O CAMPO ZERADO É `None`, e nunca `{}`: `None` é o mesmo estado de um perfil
    que nunca foi editado, e `{}` seria "nenhum botão faz nada". Depois das duas
    recusas abaixo, o único caminho que ainda grava `None` é o perfil que já
    tinha `{}` — a normalização de um estado que o esquema não pretende.

    FATO SUBSTITUÍDO (02/09/2026, corretivo): esta linha dizia *"e quando nada
    mudou, ele grava `None` — que apaga o campo"*. **Nada mudou deixou de gravar
    coisa alguma.** Com o perfil guardando escolhas, a trava recusa; com o perfil
    já igual à tela, a recusa nova diz que já está guardado. Nenhum dos dois
    chega ao disco.

    ELE ERA UM APAGADOR COM RÓTULO DE "GUARDAR", e isso foi medido em
    02/09/2026: as 21 opções que a tela mostrava eram **exatamente**
    `acoes.padrao()`, logo `diferentes` saía `{}` e o gesto gravava
    `button_actions = None` — apagando, em silêncio, qualquer escolha que o
    perfil do usuário guardasse. O botão dizia "Guardar" e fazia o contrário.

    FATO SUBSTITUÍDO, e ele estava escrito AQUI: *"as 21 `<select>` têm
    `data-linha` e nenhum `data-campo`, então nada nunca as pintou"*. Isso valia
    contra a página publicada da manhã. **O usuário mandou publicar** no mesmo dia
    (commit `70b58116`), e a página publicada de agora traz `data-campo` e
    `data-hef-alvo="valor"` nas 21 — medido com dublê: os 21 campos saem
    PRODUTO, e o valor que a tela mostra é o do perfil.

    O QUE SOBRA DA TRAVA, e por que ela FICA: a forma toda no de fábrica com o
    perfil guardando escolhas deixou de ser o estado permanente e virou uma
    JANELA — os 100 ms entre a página carregar e o primeiro tique pintar
    (`hefesto_vivo.TIQUE_MS`). Um clique ali dentro ainda leria o desenho como
    se fosse a escolha do usuário, e ainda apagaria. Enquanto o piloto não marcar o
    que já foi pintado, esta trava é o que separa "ela zerou" de "a tela ainda
    não falou".

    O QUE A TELA OFERECE E O PRODUTO NÃO ATENDE **é dito, não engolido**: os
    comandos "Abrir a Steam", "Sair do modo jogo" e "Escolher um programa…", os
    dois papéis de eixo pedidos a um botão, e os gatilhos L2/R2, que são espelho
    do cross e do triangle (`uinput_mouse._resolve_emulated_set`). O gesto GRAVA
    o resto e LEVANTA nomeando o que não pousou — quem clicou fica sabendo, em
    vez de descobrir pelo botão que não responde.

    E O QUE A TELA **NÃO SABE** OFERECER TAMBÉM É DITO, e deixou de ser gravado
    — 02/09/2026. Ver `_o_desenho_congelado`: o L3 nasceu ALTERNADOR e a página
    publicada não tem a `<option>` desse rótulo, então a linha abre mostrando
    "Abrir o teclado na tela". Recolher isso gravava `{'l3': '__OPEN_OSK__'}` no
    perfil ATIVO — **o L3 parava de alternar** — em silêncio, bastando um clique
    para mudar qualquer OUTRA linha.

    ONDE GRAVA (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01): as linhas são do
    cartão «Mouse», que é do computador. Grava no perfil só quando ele já tem
    escolhas próprias aqui; senão, no ``maquina.json``, e o perfil não muda.
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

    O QUE ELE FAZ: grava `key_bindings = None` no perfil ATIVO e manda o daemon
    reaplicá-lo. `None` não é "vazio" — o esquema o define como *"herda
    `DEFAULT_BUTTON_BINDINGS` do core"* (`profiles/schema.py:1172`), e `{}` é
    outra coisa (teclado silencioso). Escrever `{}` aqui devolveria um controle
    MUDO com o botão dizendo "de fábrica".

    E ELE DEVOLVE AS VINTE E UMA, ao contrário do que parece. Contadas na tela e
    no fonte, em 01/09/2026:

        9 linhas   `key_bindings` as alcança — l1, r1, l3, r3, options, create
                   e as três regiões do touchpad (`core/keyboard_mappings.py:36`)
        12 linhas  mapas FIXOS do produto — `BUTTON_TO_UINPUT`, `DPAD_TO_KEY` e
                   `EDGE_KEY_MAP` (`integrations/uinput_mouse.py:78,99,105`),
                   mais o L2/R2 e a DIREÇÃO dos analógicos, que binding nenhum
                   alcança

    As 12 não têm onde ser mudadas — logo estão **sempre** de fábrica, e zerar as
    9 devolve a tabela inteira ao de fábrica. É por isso que este botão fecha
    inteiro, enquanto o "Guardar" ao lado dele não fecha: guardar 9 de 21
    escolhas e perder 12 caladas é o botão que responde calado.

    ELE ZERA OS DOIS CAMPOS desde 01/09/2026: o `key_bindings` (as nove teclas)
    e o `button_actions` (as vinte e uma linhas da tela, que nasceu no mesmo
    dia). Zerar só um deixaria a tabela metade de fábrica, com o botão dizendo
    o contrário.

    O ALVO É O PERFIL ATIVO, e ele é dito: os dois são campo de perfil
    (`profiles/schema.py`), não da máquina. Sem perfil ativo o botão RECUSA —
    devolver ao padrão "o perfil nenhum" não quer dizer nada.

    A GRAVAÇÃO É A DA CASA: `perfil.gravar_e_reaplicar`, a mesma que a aba
    Perfis usa. O `save_profile` grava em disco e o `profile.switch` reaplica se
    for o ativo.

    FATO SUBSTITUÍDO, e é o que destravou este botão: o `SEM_GESTO` abaixo dizia
    que "gravar perfil não tem método". Tem — `profiles/loader.save_profile`, e
    o `a10_perfis` já o usava desde a mesma leva que escreveu a frase.

    E ELE DÁ RECIBO DO QUE APAGOU — 04/09/2026, pelo canal de SUCESSO da D-01.
    Até hoje ele apagava os `key_bindings` que o usuário escreveu na janela antiga e
    voltava sem uma palavra: o piloto imprimia `aplicado` no terminal de quem
    lançou a janela, e quem clica não lê terminal. O `recado` que este gesto
    devolve nomeia quantos atalhos saíram, no cartão dela, em verde — o que
    apaga tem de dizer o que apagou.

    UM DEGRAU (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01): as teclas são do
    cartão «Teclado» e as linhas, do «Mouse», os dois do computador. Cada um
    volta onde a marca dele diz: no jogo que o sobrepõe, sai a sobreposição e
    volta a valer o computador; sem sobreposição, o computador volta ao de
    fábrica. Sem perfil ativo, é o computador que volta.
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
    """"Guardar" do *Estilo Point-and-click*. Escreve `Profile.button_actions`.

    ELE PASSOU A TER DONO EM 11/09/2026, F2-POINT-AND-CLICK, e o que o segurava
    era um FATO que a medição derrubou. O `SEM_GESTO` dizia: *"'Estilo de Jogo'
    não existe em campo, widget ou preset nenhum do produto"*. Isso continua
    verdade sobre um campo chamado "estilo" — e é a pergunta errada. As sete
    linhas desta tela não perguntam que ESTILO o perfil tem: elas perguntam **o
    que cada peça do controle faz**, que é exatamente o que
    `Profile.button_actions` guarda desde 01/09/2026, por decisão de produto
    (*"ganha campo"*). Seis das sete são botões de `acoes.BOTOES`, com o mesmo
    id que a tela de Definições já grava; a sétima não é botão em lugar nenhum
    do produto — ver o `PONTO_MAPA` do gerador.

    É A MESMA TABELA VISTA POR UMA JANELA MENOR, e é por isso que ele **junta em
    vez de substituir**: a forma que o piloto recolhe aqui é recortada pelo `id`
    da pop-up e traz SEIS linhas. Um `Guardar` que gravasse só o que recebeu
    apagaria as outras dezesseis escolhas do perfil sem uma palavra — o
    apagador com rótulo de "Guardar", que esta casa já pagou uma vez nesta
    mesma aba (02/09/2026).

    E VOLTAR AO DE FÁBRICA É TIRAR DO PERFIL, não gravar o valor de fábrica:
    `button_actions` guarda DIFERENÇA, e `None` quer dizer "herda". Gravar o
    padrão congelaria o padrão VELHO no dia em que o produto mudasse o dele.

    A TRAVA CONTRA O DESENHO é a mesma do irmão e um pouco mais larga, e a
    largura não custa nada: lá ela só dispara quando a forma inteira está no de
    fábrica; aqui, sem NENHUMA linha em `_MEXENDO`, **qualquer** divergência
    entre a forma e o que o perfil guarda já quer dizer *o piloto ainda não
    falou* — nos 100 ms entre a página carregar e o primeiro tique pintar
    (`hefesto_vivo.TIQUE_MS`) a tela é o desenho, e gravar o desenho é gravar
    escolha que ninguém fez. Com `_MEXENDO` cheio, a forma é escolha do usuário e o
    gesto grava, inclusive quando ela devolve tudo ao de fábrica.

    O QUE SE PERDE É NOMEADO, e só o desta tela: `resolver()` devolve os botões
    que ninguém atende hoje, e a frase fala apenas dos que ESTE clique escreveu
    — nomear os outros dezesseis seria o gesto respondendo sobre o que não fez.
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
SEM_GESTO = {
    "navegacao-interna": "navegar a janela do Hefesto com o controle não tem "
                         "método no daemon — nenhum dos 39, e o "
                         "`core/disputa_de_botao.py` que as sprints citam não "
                         "existe no disco",
    "modo-steam": "não há método de Modo Steam no daemon — nenhum dos 39",
    # do `DEFAULT_BUTTON_BINDINGS`, e combo nenhum aparece lá.
    # de IPC nenhum escreve" o `ps_button_action`. Escreve — `daemon.reload`
    # `acao-do-gesto` SAIU DAQUI em 01/10/2026 (OS-GESTOS-DO-CONTROLE-01): a
    # ou desenvolvidas."* `Profile.button_actions` nasceu, o
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


PONTE = {"chamar", "machine_declare", "escolher_arquivo"}
#: O `desktop.status.set` é o «Status do Modo» desde 29/09/2026
METODOS = {"mouse.emulation.set", "keyboard.emulation.set", "desktop.status.set",
           "machine.declare"}


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

    `data-linha` diz qual gesto (as chaves de `acoes_do_gesto.GESTOS`); a página
    publicada antes desta sprint não o tem, e o clique do usuário recusa como antes.
    O rótulo vira o token pelo dono do vocabulário. «Escolher um script…» (ou o
    nome de um já escolhido) abre o seletor do sistema
    (`D-2909-O-SCRIPT-E-UM-ARQUIVO-ESCOLHIDO`): cancelar não grava nada e a
    pintura devolve a lista ao que era; o arquivo é conferido aqui
    (`conferir_o_script`) e de novo pelo daemon na hora de rodar.

    A recusa pisca na lista, e a frase vai ao diário, como todo gesto da casa.
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
