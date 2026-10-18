#!/usr/bin/env python3
"""A RÉGUA DE PRONTO de toda feature da tela — CABO-BT-PERFIL-CONTROLE-01."""
from __future__ import annotations

import ast
import csv
import functools
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
SRC = RAIZ / "src"
PAGINAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"
PACOTES = RAIZ / "src/hefesto_dualsense4unix/interface/pacotes"
MAPA = RAIZ / "docs/data/mapa-controles.csv"
ESQUEMA = RAIZ / "src/hefesto_dualsense4unix/profiles/schema.py"
MAQUINA = RAIZ / "src/hefesto_dualsense4unix/utils/maquina.py"

_SIM = {"sim", "1", "true"}

#: deles toca o DualSense: são gestos de TELA (abrir, fechar, voltar ao
_DO_EXTERNO = ("declara o controle externo (a cor do plástico, a chave de modo, a ordem dos "
               "botões) no `maquina.json` (`ControleDeclarado`) — é da máquina, e nada muda no "
               "aparelho")

NAO_E_DO_APARELHO: dict[str, str] = {
    "escolher-na-fita": "escolhe qual controle a aba edita — não muda o aparelho",
    "padrao-da-aba": "devolve a aba ao desenho — é da tela",
    "vizinho-o-que-e": "abre a explicação de um vizinho de porta — é texto",
    "detectar": "detecta o jogo aberto — é leitura da máquina",
    "procurar": "reprocura os lançadores — é leitura do disco",
    "abrir-lancador": "abre um programa da máquina dela",
    "adicionar-lancador": "registra onde um lançador está — é da máquina",
    "procurar-o-arquivo": "abre o seletor do sistema para ela apontar o "
                          "`.desktop` — é da máquina, e nada aqui toca o "
                          "controle",
    "copiar-registro": "copia o registro técnico para a área de transferência "
                       "— é leitura (o «Ver detalhes» saiu em 25/09/2026)",
    "criar-perfil-para-um-jogo": "abre a escolha do jogo para um perfil novo — "
                                 "é da tela",
    "mic-retorno": "liga e desliga o RETORNO do microfone — um `pw-loopback` "
                   "entre o nó de captura deste controle e a saída padrão. É "
                   "leitura do microfone mais uma tocada na saída, e não muda "
                   "estado nenhum: nem no aparelho, nem no perfil. **E NÃO "
                   "PERSISTE DE PROPÓSITO** — ela pediu *\"POR DEFAULT SEGUE "
                   "DESLIGADO\"* (21/09/2026), e um retorno que renascesse "
                   "ligado poria a voz dela no ar sem ninguém ter clicado. O "
                   "volume e o ganho que ele reflete são dos deslizantes ao "
                   "lado, que têm as quatro respostas por conta deles "
                   "(TESTAR-O-MICROFONE-01, 20/09/2026)",
    "hefesto": "liga e desliga o MODO do produto — é do serviço",
    "parar-ou-retomar": "para, retoma ou ativa o serviço — é systemd (o "
                        "«Parar» e o «Retomar» viraram um botão só em 25/09/2026)",
    "reiniciar": "reinicia o serviço — é systemd",
    "atualizar": "atualiza o produto — é da máquina",
    "menu-atualizar": "o mesmo «atualizar» da aba Sistema, pelo menu do botão direito — é da máquina",
    "menu-desligar": "o mesmo «parar-ou-retomar» da aba Sistema, pelo menu do botão direito — é systemd",
    "menu-reiniciar": "o mesmo «reiniciar» da aba Sistema, pelo menu do botão direito — é systemd",
    "menu-fechar": "fecha a janela do Hefesto — é da tela",
    "autostart": "liga junto com o computador — é do sistema",
    "corrigir-modo": "conserta o modo de execução do serviço — é da máquina",
    "restaurar-de-fabrica": "devolve o perfil de fábrica — é do perfil",
    "perfil-da-mesa": "escolhe o perfil de energia — é do daemon",
    "correcoes-automaticas": "liga ou desliga as correções automáticas do computador a cada jogo "
                             "novo — é da máquina, e nada muda no aparelho",
    "salvar-registro": "grava o registro técnico num arquivo — é leitura do diário",
    "tamanho-da-interface": "escolhe o tamanho da interface — é da tela",
    "bandeja": "mostra ou esconde o ícone do Hefesto na bandeja da sessão — é do sistema",
    "examinar-portas": "examina as portas USB — é leitura do barramento",
    "escolher-aparelho": "escolhe o aparelho da aba Conexões — é da tela",
    "escolher-entrada": "escolhe a entrada — é da tela",
    "nova-entrada": "declara uma entrada nova — é da máquina",
    "nova-extensao": "declara uma extensão nova — é da máquina",
    "nova-face": "declara uma face do gabinete — é da máquina",
    "sala-altura": "a altura do gabinete no desenho — é da máquina",
    "sala-visada": "a visada do desenho — é da tela",
    "tirar-daqui": "tira uma declaração da máquina",
    "ignorar": "ignora um aparelho — é da máquina",
    "alvo": "escolhe o alvo do exame — é da tela",
    "luz-nao-acende": "declara que a luz não acende — é da máquina",
    "dono-renomear": "dá nome a quem joga com o controle, na memória dos controles "
                     "— é da máquina",
    "mapear-comecar": "o Mapear Entradas começa a olhar as portas — é da máquina",
    "mapear-gravar": "grava o nome e o lugar da porta da vez no mapa das portas do "
                     "`maquina.json` — é da máquina",
    "mapear-parar": "o Mapear Entradas para de olhar as portas — é da máquina",
    "modo": "o efeito do gatilho (03) e o modo de navegação (06) — o gesto tem "
            "dois donos, e os dois caem em linhas do mapa por outro gesto",
    "modo-dualsense": "o modo é UM para todos — decisão dela de 08/09 "
                      "(`D-0809-O-MODO-E-UM-PARA-TODOS-OS-CONTROLES`)",
    "modo-navegacao": "idem",
    "modo-point-and-click": "idem: é o mesmo modo `desktop` da Navegação, no lado Ligado da tela",
    "modo-steam": "idem",
    "modo-xbox": "idem",
    "modo-nativo": "idem: o Nativo tira o Hefesto do meio para todos, e a Steam do jogo da vez",
    "configurar-lancador": "abre a janela do lançador — é da tela",
    "identificar-lancador": "procura o lançador de novo no disco — é leitura da máquina",
    "criar-perfil-do-jogo": "cria o perfil do jogo escolhido na janela dos lançadores — é do perfil",
    "ligar-modificacao": "liga ou desliga uma extensão — é do supervisor da máquina",
    "configurar-modificacao": "abre a janela de uma extensão — é da tela",
    "guardar-opcao-da-modificacao": "guarda uma opção da extensão no `opcoes.json` dela — é da máquina",
    "mais-da-modificacao": "o ⋮ da extensão (atualizar, ver as permissões, remover) — é da máquina",
    "instalar-modificacao": "instala uma extensão de um endereço git ou de uma pasta — é da máquina",
    "escolher-arquivo-da-modificacao": "abre o seletor do sistema para apontar o "
                                       "`hefesto-mod.json` — é da máquina",
    "ver-impedimentos": "abre a lista do que a Steam impede no jogo — é leitura da máquina",
    "resolver-impedimento": "cura um impedimento do jogo na Steam — é do disco da máquina",
    "resolver-todos-os-impedimentos": "cura todos os impedimentos do jogo — é do disco da máquina",
    "cadeado": "trava o perfil ativo — é do perfil",
    "reconectar": "reconcilia os jogadores — é da mesa, não de um controle",
    "novo-hub": "abre a pergunta curta do hub na 08 — estado de tela, é da máquina",
    "novo-hub-cancelar": "idem",
    "novo-hub-gravar": "declara o hub na máquina (`machine_declare`) — é da máquina, não de um controle",
    "teclado": "escolhe a Função do teclado (Sempre, Só fora do jogo, Só dentro do jogo, "
               "Desativado) — é do perfil e do serviço, e o ATO no aparelho é o de cada linha",
    "linha-de-botao": "grava o que uma linha de botão faz no perfil ou no computador — o ATO "
                      "no aparelho é o de cada linha, que já responde as quatro",
    "permitir-navegacao": "escolhe a navegação (Interna, Steam ou Uso geral) — é do serviço "
                          "(o Big Picture do `modo-steam` e o tipo da Interna), nunca do perfil",
    "na-steam": "escolhe o que a Steam navega (o Big Picture) — é do serviço, nunca do perfil",
    "point-and-click-perfil": "escolhe o perfil que o point and click usa — é da máquina "
                              "(`mouse.point_and_click` do `maquina.json`)",
    "mapa-perfil": "escolhe qual perfil o mapa do controle edita — é da tela",
    "mapa-nome": "o nome do perfil em edição no mapa — é do perfil, vale no Guardar",
    "mapa-usar-em": "o jogo a que o perfil em edição se liga — é do perfil, vale no Guardar",
    "mapa-botao": "escolhe a linha de botão que o mapa vai mudar — é da tela",
    "mapa-escolher": "escolhe no que o botão vira — é do perfil, vale no Guardar",
    "mapa-gravar-tecla": "grava a tecla, o botão do mouse ou o botão do controle apertado — é do perfil, vale no Guardar",
    "mapa-mover-com": "escolhe o analógico que move o cursor — é do perfil, vale no Guardar",
    "mapa-padrao": "devolve o mapa ao padrão — é da tela, vale no Guardar",
    "mapa-cancelar": "larga o que o mapa não guardou — é da tela",
    "mapa-guardar": "grava o perfil em edição no mapa — é do perfil",
    "acao-do-gesto": "escolhe a ação de um gesto — é do perfil",
    "novo-gesto": "acrescenta um gesto do PS — é da máquina (`maquina.json`), nunca do perfil",
    "remover-gesto": "tira um gesto do PS — é da máquina (`maquina.json`), nunca do perfil",
    "vel-cursor": "a velocidade do cursor — é da emulação de mouse, global (decisão dela)",
    "vel-rolagem": "idem",
    "modo-dos-gatilhos": "o par Automático | Personalizado dos gatilhos grava `triggers.modo` "
                         "no perfil — o ATO no aparelho é o do gesto `modo` da 03",
    "modo-da-vibracao": "o par Automático | Personalizado da vibração grava `rumble.modo` no "
                        "perfil — o ATO no aparelho é o de cada ajuste da 05",
    "modo-dos-controles": "o par Automático | Personalizado dos controles grava "
                          "`controles_modo` no perfil — o ATO no aparelho é o de cada ajuste da 02",
    "criar-efeito": "guarda no `gui_prefs` um efeito que ela criou, com a chave da feature — é "
                    "da tela; o ATO no aparelho é o do gesto que aplica o efeito",
    # O desenho aprovado virou a cx8-3. Nenhum destes muda o DualSense:
    "abrir-adaptador": "abre um adaptador no acordeão — é da tela",
    "adaptador-reordenar": "grava a ordem em que ela arrastou as caixas dos adaptadores, "
                           "no `gui_prefs` — é da tela",
    "adaptador-historico": "abre o sino de um adaptador — é leitura do diário do rádio",
    "sugerir-alocacao": "mostra a sugestão da central para um adaptador — é da tela",
    "aceitar-sugestao": "abre a pergunta de mover a partir do balão — é da tela; "
                        "quem move é o `confirmar-mudanca`",
    "cancelar-mudanca": "fecha a pergunta de mover — é da tela",
    "escolher-adaptador": "escolhe o adaptador do próximo «Conectar» — é da tela",
    "equilibrar-radio": "abre a proposta da central de rádio — é da tela",
    "confirmar-mudanca": "move um aparelho de adaptador (`radio.mover`) — é o rádio "
                         "da máquina: o controle continua o mesmo, com o mesmo perfil",
    "conectar-aparelho": "abre o painel do «Conectar» (sem alvo, nada vai ao rádio); "
                         "com alvo, conecta um aparelho conhecido — é o rádio da máquina",
    "parear-aparelho": "pareia um aparelho achado num adaptador — é o rádio da máquina",
    "parear-o-pedido": "leva o controle conhecido que pede para parear ao adaptador que o ouve "
                       "(`radio.mover`) — é o rádio da máquina, para P1–P4",
    "tentar-de-novo": "liga a busca no mesmo adaptador da linha que não chegou "
                      "(`radio.busca.set`), ou refaz o mover do aparelho que não é "
                      "controle — é o rádio da máquina",
    "parear-de-novo": "esquece o par velho do controle que não conectou "
                      "(`esquecer_o_pareamento`) e liga a busca no mesmo adaptador — é o "
                      "rádio da máquina",
    "esquecer-aparelho": "o «Esquecer» do «⋮» abre a pergunta de esquecer — é da "
                         "tela",
    "confirmar-esquecer": "esquece o pareamento deste aparelho NESTE adaptador "
                          "(`esquecer_o_pareamento`) — é o rádio da máquina: os "
                          "outros adaptadores não se tocam",
    "radio-procurar": "liga e desliga a busca do rádio (`radio.busca.set`) — é o "
                      "rádio da máquina: o controle que já está no ar não muda",
    "aparelho-menu": "abre o «⋮» de um pareado — é da tela; quem esquece é o "
                     "`confirmar-esquecer`",
    "dispensar-linha": "tira a linha «Não Conectou» (`radio.dispensar`), lembrada "
                       "pela central — é do rádio da máquina, sem perfil nem controle",
    "ligar-mesmo-assim": "sobe a ponte de som além do limite do adaptador "
                         "(`radio.ponte.ligar_aqui`) — é do rádio da máquina, e o "
                         "som em si responde pelas linhas do `rota` e do `volume`",
    "adaptador-renomear": "dá nome ao LUGAR do adaptador no `maquina.json` — é da máquina",
    "aparelho-renomear": "dá nome a um aparelho no BlueZ (`Alias`) — é da máquina",
    "entrada-comecar": "começa o «Mapear Entrada a Entrada» — é da máquina "
                       "(as entradas do gabinete dela)",
    "entrada-face": "grava a face de uma entrada no `maquina.json` — é da máquina",
    "entrada-pular": "pula uma entrada da cerimônia — é da tela",
    "entrada-levantar": "passa a cerimônia para a fase em pé — é da tela",
    "entrada-nao-alcanco": "tira uma entrada da conta no `maquina.json` — é da máquina",
    "entrada-parar": "fecha a cerimônia — é da tela",
    "receptor-descobrir": "descobre a faixa do receptor 2.4G por eliminação e a grava no "
                          "`maquina.json` — é da máquina",
    "externo-cor": _DO_EXTERNO,
    "externo-modo": _DO_EXTERNO,
    "externo-botoes": _DO_EXTERNO,
    # Os gestos que só o registro dos pacotes mostra (a página os gera em JS, ou não é
    # uma das dez): AS-REGUAS-DO-RAMO-INTEIRO-E-DAS-QUATRO-RESPOSTAS-MORDEM-01.
    "todos": "volta as ações da 08 para a mesa inteira (o «▴») — é da tela",
    "selecionar": "abre um perfil no editor — é da tela",
    "ativar": "troca o perfil ativo (`profile.switch`) — é do perfil; o ATO no aparelho é o "
              "de cada feature do perfil, que responde as quatro por conta própria",
    "aplicar": "manda o perfil ativo inteiro aos controles, sem gravar — é do perfil; o ATO "
               "no aparelho é o de cada feature do perfil",
    "salvar": "regrava o perfil ativo — é do perfil",
    "exportar": "escreve o perfil ativo num `.json` da pasta pessoal — é do disco",
    "importar": "carrega um perfil de um `.json` escolhido — é do perfil",
    "voltar-a-de-ontem": "desfaz a última gravação do perfil aberto — é do perfil",
    "editor.nome": "renomeia o perfil — é do perfil",
    "editor.prioridade": "a prioridade entre dois perfis que servem — é do perfil",
    "editor.ambiente": "a regra que faz o perfil entrar — é do perfil",
    "editor.estilo": "aplica a receita de um Estilo de Jogo no perfil — é do perfil; o ATO "
                     "no aparelho é o de cada feature da receita",
    "editor.jogo": "o jogo que faz o perfil entrar — é do perfil",
    "editor.ordem": "a ordem entre os perfis do mesmo jogo — é do perfil",
    "editor.alvo": "onde o perfil se aplica, nos controles ou num evento — é do perfil",
    "editor.quando": "o evento e o comando gravados no perfil — é do perfil; quem roda o "
                     "comando é a sprint do motor dos eventos",
    "novo": "cria um perfil em branco — é do perfil",
    "duplicar": "copia um perfil — é do perfil",
    "remover": "apaga um perfil do disco — é do perfil",
    "recarregar": "relê a lista de perfis do disco — é leitura",
    "ordenar": "ordena a tabela dos perfis — é da tela",
    "largura-da-coluna": "grava a largura de uma coluna da tabela dos perfis — é da tela",
    "adicionar-a-exclusao": "abre a escolha do jogo para a lista de exclusão — é da tela",
    "confirmar-exclusao": "põe o jogo na lista de exclusão e tira dele o que o Hefesto pôs "
                          "no disco — é da máquina",
    "tirar-da-exclusao": "devolve o jogo ao Hefesto — é da máquina",
    "confirmar-perfil": "cria o perfil do jogo marcado — é do perfil",
    "esquecer-lancador": "desfaz o que o usuário declarou sobre um lançador "
                         "(`machine_declare`) — é da máquina",
    "voltar-a-usar": "tira o jogo do `jogos_sem_wrapper.txt` — é do disco",
    "voltar-a-perguntar": "tira o jogo da lista dos avisos dispensados — é do disco",
    "entrada-o-que-tem": "declara «Direto» ou «Hub» numa entrada do `maquina.json` — é da "
                         "máquina",
    "entrada-extensor": "declara o cabo de extensão de uma entrada — é da máquina",
    "entrada-lugar": "declara a face do gabinete de uma entrada — é da máquina",
    "entrada-velocidade": "declara USB 3.0 ou 2.0 numa entrada — é da máquina",
    "entrada-nome": "dá nome a uma entrada — é da máquina",
    "entrada-trocar": "troca duas entradas de posição no mapa das portas — é da máquina",
    "entrada-ensinar": "ensina em qual entrada um aparelho está — é da máquina",
    "aparelho-tipo": "o tipo que o usuário dá a um aparelho USB pelo `vid:pid` — é da máquina",
    "aparelho-nome": "o nome que o usuário dá a um aparelho USB pelo `vid:pid` — é da máquina",
    "voltar-ao-automatico": "tira o que o usuário declarou do aparelho e da entrada — é da "
                            "máquina",
    "reexaminar": "relê as portas da máquina — é leitura do barramento",
}

DO_APARELHO: dict[str, tuple[str, ...]] = {
    "mascara": ("plataforma.vpad",),
    "mudo": ("audio.microfone.mudo",),
    "volume": ("audio.microfone.volume", "audio.alto_falante.volume"),
    "rota": ("audio.alto_falante.rota",),
    "volume-padrao": ("audio.alto_falante.volume",),
    "sensor": ("movimento.giroscopio",),
    "cor": ("luz.lightbar.cor",),
    "brilho": ("luz.lightbar.cor",),
    "apagar": ("luz.lightbar.cor",),
    "efeito-da-luz": ("luz.lightbar.cor",),
    "player": ("luz.led_jogador.escrita_hefesto",),
    "brilho-luzes": ("luz.led_jogador.brilho",),
    "modo-da-luz": ("luz.lightbar.cor", "luz.led_jogador.escrita_hefesto"),
    "lado": ("vibracao.rumble.esquerdo", "vibracao.rumble.direito"),
    "custo-mic": ("audio.microfone.mudo",),
    # O-ANALOGICO-VIRTUAL-E-UM-SO-COM-O-LADO-ESCOLHIDO-01: o chip «Inclinação» saiu da
    # 02, e o lado do Analógico Virtual leva o giro e a inclinação juntos.
    "analogico-lado": ("movimento.giroscopio", "movimento.acelerometro"),
    "touchpad": ("toque.touchpad.cursor", "toque.touchpad.dedos"),
    "haptica": ("vibracao.haptics_vcm",),
    "efeito-haptico": ("vibracao.haptics_vcm",),
    "efeito-imersao": ("vibracao.rumble.esquerdo", "vibracao.rumble.direito"),
    "testar-haptica": ("vibracao.haptics_vcm",),
    "imersao": ("gatilho.esquerdo.adaptativo", "gatilho.direito.adaptativo"),
    "sentir": ("gatilho.esquerdo.adaptativo", "gatilho.direito.adaptativo"),
    "forca": ("vibracao.rumble.esquerdo", "vibracao.rumble.direito"),
    "intensidade": ("vibracao.rumble.esquerdo", "vibracao.rumble.direito"),
    "motor": ("vibracao.rumble.esquerdo", "vibracao.rumble.direito"),
    "testar": ("vibracao.rumble.esquerdo", "vibracao.rumble.direito"),
    "parar": ("vibracao.rumble.esquerdo", "vibracao.rumble.direito"),
    "mira-sensibilidade": ("movimento.giroscopio",),
    "mira-tremor": ("movimento.giroscopio",),
    "mira-segurar": ("movimento.giroscopio",),
    "mira-inverter": ("movimento.giroscopio",),
    "calibrar-comecar": ("movimento.giroscopio",),
    "mic-existe": ("audio.microfone",),
}

#: aplica na troca de perfil é `ProfileManager._aplicar_ganho_do_mic`. O campo
A_DIVIDA_CONHECIDA: dict[str, tuple[str, str]] = {
}

NO_PERFIL: dict[str, tuple[str | None, str | None]] = {
    "mascara": ("mode", None),
    "volume": ("mic", "mic"),
    "rota": ("speaker", "speaker"),
    "volume-padrao": ("speaker", "speaker"),
    "sensor": (None, "sensores"),
    "touchpad": (None, "sensores"),
    "cor": ("leds", "leds"),
    "brilho": ("leds", "leds"),
    "apagar": ("leds", "leds"),
    "efeito-da-luz": ("leds", "leds"),
    "player": ("leds", "leds"),
    "brilho-luzes": ("leds", "leds"),
    "modo-da-luz": ("leds", "leds"),
    "lado": ("rumble", "rumble"),
    "analogico-lado": ("movimento", "movimento"),
    "haptica": (None, "rumble"),
    "efeito-haptico": (None, "rumble"),
    "efeito-imersao": (None, "rumble"),
    "testar-haptica": (None, "rumble"),
    "imersao": ("triggers", "triggers"),
    "sentir": (None, "triggers"),
    "forca": ("rumble", "rumble"),
    "intensidade": ("rumble", "rumble"),
    "motor": ("rumble", "rumble"),
    "testar": (None, "rumble"),
    "parar": (None, "rumble"),
    "mira-sensibilidade": ("movimento", "movimento"),
    "mira-tremor": ("movimento", "movimento"),
    "mira-segurar": ("movimento", "movimento"),
    "mira-inverter": ("movimento", "movimento"),
}


NO_CONTROLE: dict[str, str] = {
    "mudo": "microfone_mudo",
    "custo-mic": "microfone_mudo",
    "mic-existe": "microfone",
}

#: Gestos cujo valor é de cada controle, pelo `uniq`, num arquivo próprio e fora do perfil por
#: desenho (o zero do sensor é daquela unidade, não do jogo): `{gesto: (fonte, função que grava)}`.
#: A régua confere que a função existe no fonte.
NO_ARQUIVO_DO_CONTROLE: dict[str, tuple[str, str]] = {
    "calibrar-comecar": ("src/hefesto_dualsense4unix/utils/session.py", "gravar_os_zeros"),
}

_NO_CONTROLE = "no controle"
_SO_POR_CONTROLE = "só por controle"


def _grava_no_fonte(fonte: pathlib.Path, funcao: str) -> bool:
    """A função que grava existe no fonte (lida, não importada)."""
    try:
        texto = fonte.read_text(encoding="utf-8")
    except OSError:
        return False
    return re.search(rf"^def {re.escape(funcao)}\(", texto, re.M) is not None


def _aba(pagina: str) -> str:
    """`01-jogar.html` → `01`; `calibrar-sensores.html` → `calibrar-sensores`; `*` → `*`."""
    nome = pagina.removesuffix(".html")
    return nome[:2] if re.match(r"^\d\d-", nome) else nome


def gestos_das_paginas(pasta: pathlib.Path = PAGINAS) -> dict[str, list[str]]:
    """`{gesto: [abas]}` das dez páginas publicadas, SEM os blocos `<style>`.

    Um `data-gesto` dentro do CSS (`select.pronto[data-gesto="externo-cor"]`) é um seletor
    de estilo, não um botão: lido com o estilo, ele entrava na régua por acidente.
    """
    fora: dict[str, list[str]] = {}
    for pagina in sorted(pasta.glob("*.html")):
        if not re.match(r"^\d\d-", pagina.name):
            continue
        texto = _SEM_ESTILO.sub("", pagina.read_text(encoding="utf-8"))
        for gesto in sorted(set(re.findall(r'data-gesto="([a-z0-9_@:.-]+)"', texto))):
            fora.setdefault(gesto, []).append(_aba(pagina.name))
    return fora


_SEM_ESTILO = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.S | re.I)


def _modulo_do_arquivo(arquivo: pathlib.Path, src: pathlib.Path) -> str:
    partes = arquivo.relative_to(src).with_suffix("").parts
    return ".".join(partes[:-1] if partes[-1] == "__init__" else partes)


def _arquivo_do_modulo(modulo: str, src: pathlib.Path) -> pathlib.Path | None:
    base = src.joinpath(*modulo.split("."))
    for candidato in (base.with_suffix(".py"), base / "__init__.py"):
        if candidato.is_file():
            return candidato
    return None


@functools.cache
def _arvore(arquivo: pathlib.Path) -> ast.Module:
    return ast.parse(arquivo.read_text(encoding="utf-8"), filename=str(arquivo))


@functools.cache
def _constantes(arquivo: pathlib.Path) -> dict[str, str | None]:
    """As constantes de texto do módulo: `NOME = "..."`. Atribuída duas vezes com valores
    diferentes, a constante vale `None` (ambígua): a régua não escolhe entre as duas."""
    fora: dict[str, str | None] = {}
    for no in _arvore(arquivo).body:
        alvos: list[ast.expr] = []
        valor: ast.expr | None = None
        if isinstance(no, ast.Assign):
            alvos, valor = no.targets, no.value
        elif isinstance(no, ast.AnnAssign):
            alvos, valor = [no.target], no.value
        if not (isinstance(valor, ast.Constant) and isinstance(valor.value, str)):
            continue
        for alvo in alvos:
            if isinstance(alvo, ast.Name):
                antes = fora.get(alvo.id, valor.value)
                fora[alvo.id] = valor.value if antes == valor.value else None
    return fora


@functools.cache
def _importados(arquivo: pathlib.Path, src: pathlib.Path) -> dict[str, tuple[str, str | None]]:
    """`{apelido: (módulo, nome)}`: `nome` é `None` quando o apelido é o próprio módulo."""
    pacote = _modulo_do_arquivo(arquivo, src)
    if arquivo.name != "__init__.py":
        pacote = pacote.rpartition(".")[0]
    fora: dict[str, tuple[str, str | None]] = {}
    for no in ast.walk(_arvore(arquivo)):
        if isinstance(no, ast.Import):
            for a in no.names:
                if a.asname:
                    fora[a.asname] = (a.name, None)
        elif isinstance(no, ast.ImportFrom):
            if no.level:
                raiz = pacote.split(".")
                raiz = raiz[: len(raiz) - (no.level - 1)]
                modulo = ".".join([*raiz, *([no.module] if no.module else [])])
            else:
                modulo = no.module or ""
            for a in no.names:
                inteiro = f"{modulo}.{a.name}"
                if _arquivo_do_modulo(inteiro, src) is not None:
                    fora[a.asname or a.name] = (inteiro, None)
                else:
                    fora[a.asname or a.name] = (modulo, a.name)
    return fora


def _no_modulo(modulo: str, nome: str, src: pathlib.Path, fundo: int) -> str | None:
    arquivo = _arquivo_do_modulo(modulo, src)
    if arquivo is None or fundo > 4:
        return None
    if nome in _constantes(arquivo):
        return _constantes(arquivo)[nome]
    de_onde = _importados(arquivo, src).get(nome)
    if de_onde is None or de_onde[1] is None:
        return None
    return _no_modulo(de_onde[0], de_onde[1], src, fundo + 1)


def _texto(expr: ast.expr, arquivo: pathlib.Path, src: pathlib.Path) -> str | None:
    """O texto de um argumento de `@gesto(...)`: literal, constante do módulo, constante
    importada (`from x import NOME`) ou atributo de módulo importado (`desenho.ABRIR`)."""
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.Name):
        if expr.id in _constantes(arquivo):
            return _constantes(arquivo)[expr.id]
        de_onde = _importados(arquivo, src).get(expr.id)
        if de_onde is not None and de_onde[1] is not None:
            return _no_modulo(de_onde[0], de_onde[1], src, 1)
        return None
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        de_onde = _importados(arquivo, src).get(expr.value.id)
        if de_onde is not None and de_onde[1] is None:
            return _no_modulo(de_onde[0], expr.attr, src, 1)
    return None


def _e_o_decorador(func: ast.expr) -> bool:
    if isinstance(func, ast.Name):
        return func.id == "gesto"
    return (isinstance(func, ast.Attribute) and func.attr == "gesto"
            and isinstance(func.value, ast.Name) and func.value.id == "pacotes")


def registro_do_fonte(
    pasta: pathlib.Path = PACOTES, src: pathlib.Path = SRC
) -> tuple[set[tuple[str, str]], list[str]]:
    """Os pares `(página, gesto)` de todo `gesto(...)` dos pacotes, LIDOS do fonte por `ast`.

    É o mesmo registro que `interface.pacotes.GESTOS` monta ao importar, sem importar: os
    pacotes carregam o GTK, e o job do CI que roda esta régua só tem o `pytest`. A régua
    da régua (`test_os_gestos_lidos_do_fonte_sao_os_do_registro.py`) confere os dois.
    Devolve também os que não se resolvem (`arquivo:linha`): argumento montado em tempo
    de execução é um gesto que esta leitura não vê, e a régua reprova em vez de calar.
    """
    pares: set[tuple[str, str]] = set()
    sem_texto: list[str] = []
    for arquivo in sorted(pasta.glob("*.py")):
        for no in ast.walk(_arvore(arquivo)):
            if not (isinstance(no, ast.Call) and _e_o_decorador(no.func)):
                continue
            textos = [_texto(a, arquivo, src) for a in no.args[:2]]
            if len(textos) == 2 and textos[0] is not None and textos[1] is not None:
                pares.add((textos[0], textos[1]))
            else:
                onde = arquivo.relative_to(RAIZ) if arquivo.is_relative_to(RAIZ) else arquivo
                sem_texto.append(f"{onde}:{no.lineno} {ast.unparse(no)}")
    return pares, sem_texto


def gestos_da_tela() -> dict[str, list[str]]:
    """`{gesto: [abas]}`: a união das páginas publicadas (sem o estilo) com o registro dos
    pacotes (`@gesto`, lido do fonte). Nunca digitado."""
    fora = gestos_das_paginas()
    pares, _sem_texto = registro_do_fonte()
    for pagina, gesto in sorted(pares):
        abas = fora.setdefault(gesto, [])
        if _aba(pagina) not in abas:
            abas.append(_aba(pagina))
    return {g: sorted(abas) for g, abas in fora.items()}


def _linhas_do_mapa() -> dict[str, list[dict[str, str]]]:
    with MAPA.open(newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    fora: dict[str, list[dict[str, str]]] = {}
    for linha in linhas:
        fora.setdefault(linha.get("chave", ""), []).append(linha)
    return fora


def _campos_do_esquema(classe: str, fonte: pathlib.Path = ESQUEMA) -> set[str]:
    """Os campos declarados numa classe do `schema.py` (ou de `fonte`), lidos do fonte."""
    texto = fonte.read_text(encoding="utf-8")
    corpo = texto.split(f"class {classe}(", 1)[-1].split("\nclass ", 1)[0]
    return set(re.findall(r"^    ([a-z_]+):\s", corpo, re.M))


#: vez de doze `noqa-acento` espalhados: duas leituras independentes chegaram a
NAO = "nao"  # noqa-acento: valor cru do mapa (`*_aciona`), não prosa
_SEM_LINHA = "sem linha"
_RESSALVA = "com ressalva"
_SIM_ = "sim"

_NAO_EXISTE = "nao existe no aparelho"  # noqa-acento: valor cru do mapa
_ESCADA = (_SEM_LINHA, NAO, _NAO_EXISTE, _RESSALVA, _SIM_)

#: A tela é dos quatro DualSense (decisão de 06/09).
_O_APARELHO_DELA = "dualsense"


def _resposta_de_transporte(linhas: list[dict[str, str]], lado: str) -> str:
    """A resposta de um transporte: uma das quatro de `_ESCADA`."""
    minhas = [l for l in linhas if l.get("controle") == _O_APARELHO_DELA]
    if not minhas:
        return _SEM_LINHA
    melhor = NAO
    for linha in minhas:
        aciona = linha.get(f"{lado}_aciona", "").strip().lower()
        porque = linha.get(f"{lado}_por_que_nao_aciona", "").strip().lower()
        if aciona not in _SIM and aciona != "parcial" and porque == "nada-a-acionar":
            resposta = _NAO_EXISTE
        elif aciona == "parcial":
            resposta = _RESSALVA
        elif aciona in _SIM:
            resposta = (_RESSALVA if linha.get(f"{lado}_ressalva", "").strip()
                        else _SIM_)
        else:
            continue
        if _ESCADA.index(resposta) > _ESCADA.index(melhor):
            melhor = resposta
    return melhor


def _pior(respostas: list[str]) -> str:
    """A pior de várias respostas — o gesto responde pela metade que falta."""
    return min(respostas, key=_ESCADA.index) if respostas else _SEM_LINHA


def tabela() -> list[tuple[str, str, str, str, str, str, str]]:
    """`(gesto, abas, cabo, radio, no_perfil, por_controle, o_que_falta)`."""
    mapa = _linhas_do_mapa()
    do_perfil = _campos_do_esquema("Profile")
    do_controle = _campos_do_esquema("ControllerOverrides")
    do_controle_declarado = _campos_do_esquema("ControleDeclarado", MAQUINA)
    fora = []
    for gesto, abas in sorted(gestos_da_tela().items()):
        if gesto in NAO_E_DO_APARELHO:
            continue
        chaves = DO_APARELHO.get(gesto)
        if chaves is None:
            fora.append((gesto, ",".join(abas), "?", "?", "?", "?",
                         "gesto sem classificação — nem feature de aparelho "
                         "nem gesto de tela"))
            continue
        cabo = _pior([_resposta_de_transporte(mapa.get(c, []), "cabo")
                      for c in chaves])
        radio = _pior([_resposta_de_transporte(mapa.get(c, []), "radio")
                       for c in chaves])
        if gesto in NO_CONTROLE:
            existe = NO_CONTROLE[gesto] in do_controle_declarado
            perfil = _NO_CONTROLE if existe else NAO
            controle = _SIM_ if existe else NAO
        elif gesto in NO_ARQUIVO_DO_CONTROLE:
            fonte, funcao = NO_ARQUIVO_DO_CONTROLE[gesto]
            existe = _grava_no_fonte(RAIZ / fonte, funcao)
            perfil = _SO_POR_CONTROLE if existe else NAO
            controle = _SIM_ if existe else NAO
        else:
            campo, campo_ctrl = NO_PERFIL.get(gesto, ("", None))
            perfil = (_SO_POR_CONTROLE if campo is None
                      else _SIM_ if campo in do_perfil else NAO)
            controle = ("global" if campo_ctrl is None
                        else (_SIM_ if campo_ctrl in do_controle else NAO))
        falta = "; ".join(
            p for p in (
                f"cabo: {cabo}" if cabo in (NAO, _SEM_LINHA) else "",
                f"rádio: {radio}" if radio in (NAO, _SEM_LINHA) else "",
                "não está no perfil" if perfil == NAO else "",
                "não é por controle" if controle == NAO else "",
            ) if p)
        fora.append((gesto, ",".join(abas), cabo, radio, perfil, controle, falta))
    return fora


def classificacao_morta() -> list[str]:
    """Gestos DECLARADOS aqui que a tela já não oferece."""
    na_tela = set(gestos_da_tela())
    return sorted((set(NAO_E_DO_APARELHO) | set(DO_APARELHO)) - na_tela)


def main() -> int:
    linhas = tabela()
    mortas = classificacao_morta()
    if "--tabela" in sys.argv:
        print(f"{'gesto':18} {'abas':6} {'cabo':13} {'rádio':13} "
              f"{'perfil':16} {'controle':9} o que falta")
        print("-" * 110)
        for g, abas, cabo, radio, perfil, ctrl, falta in linhas:
            print(f"{g:18} {abas:6} {cabo:13} {radio:13} {perfil:16} "
                  f"{ctrl:9} {falta}")
        print()

    _pares, sem_texto = registro_do_fonte()
    if sem_texto:
        print(f"VERMELHO: {len(sem_texto)} `gesto(...)` dos pacotes com página ou nome que "
              f"a leitura do fonte não resolve — um gesto que esta régua não vê:")
        for linha in sem_texto:
            print(f"  {linha}")
        print()
        print("Use um literal ou uma constante de texto do módulo (`NOME = \"...\"`), "
              "própria ou importada.")
        return 1

    if mortas:
        print(f"VERMELHO: {len(mortas)} gesto(s) classificados aqui que a tela "
              f"já não oferece — a razão ficou sem dono:")
        for gesto in mortas:
            print(f"  {gesto}")
        return 1

    faltando = {linha[0]: linha[6] for linha in linhas if linha[6]}
    nova = {g: f for g, f in faltando.items() if g not in A_DIVIDA_CONHECIDA}
    fechou = [g for g in A_DIVIDA_CONHECIDA if g not in faltando]

    if nova:
        print(f"VERMELHO: {len(nova)} feature(s) da tela sem as quatro "
              f"respostas, e nenhuma delas está declarada:")
        for gesto, falta in sorted(nova.items()):
            abas = next(l[1] for l in linhas if l[0] == gesto)
            print(f"  [{abas}] {gesto}: {falta}")
        print()
        print("Toda feature que a tela oferece responde: cabo? rádio? no "
              "perfil? por controle? Quem não responde as quatro não está "
              "pronta — é a régua dela de 08/09/2026. Cure, ou declare em "
              "`A_DIVIDA_CONHECIDA` com a sprint que é dona.")
        return 1

    if fechou:
        print(f"VERMELHO: {len(fechou)} dívida(s) declarada(s) já respondem as "
              f"quatro — a declaração ficou velha e vira propaganda:")
        for gesto in sorted(fechou):
            sprint, _razao = A_DIVIDA_CONHECIDA[gesto]
            print(f"  {gesto}: tire a linha de `A_DIVIDA_CONHECIDA` e feche a "
                  f"{sprint}")
        return 1

    print(f"VERDE: {len(linhas)} feature(s) de aparelho na tela · "
          f"{len(linhas) - len(faltando)} com as quatro respostas · "
          f"{len(faltando)} em dívida declarada · "
          f"{len(NAO_E_DO_APARELHO)} gesto(s) que não são do aparelho")
    for gesto, falta in sorted(faltando.items()):
        sprint, razao = A_DIVIDA_CONHECIDA[gesto]
        print(f"  dívida: {gesto} — {falta} · {razao} · dona: {sprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
